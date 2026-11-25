"""EvidenceGraphStore — 单会话证据图的落盘与回读(计划 2.7 / 3.3)。

文件协议: src/data/evidence_graphs/<session_id>.json, 每个侧栏会话一张图,
会话内逐轮合并(单题证据图 + 会话内复用)。跨会话全局记忆库属 M5, 本期不做。
"""

from __future__ import annotations

import json
import logging
import os
import re
import unicodedata
from typing import Any, Dict, List, Optional

from .schema import (
    EdgeNode,
    EdgeRel,
    Observation,
    Provenance,
    STATUS_CANDIDATE,
    conflict_group_id,
    normalize_name,
    node_id as make_node_id,
)
from .relevance import canonical, retrieval_score

logger = logging.getLogger(__name__)

DEFAULT_KG_VERSION = "traditional_rag_collection_v5"   # 计划 2.7: DERIVED_FROM_KG@version
SCHEMA_VERSION = "flowbd-eg-2"


class EvidenceGraphStore:
    """内存证据图 + JSON 原子落盘 + 回读摘要。纯标准库, 无服务依赖。"""

    def __init__(self, session_id: str, base_dir: Optional[str] = None,
                 fresh: bool = False):
        """fresh=True 时跳过磁盘载入(临时挂载名专用): 防止上个未完成会话
        残留的 pending 文件跨会话污染本会话证据图。"""
        self.session_id = str(session_id)
        if base_dir is None:
            # 与 part5 AgentPipelineState.save_retrieval_data(L111-115)同口径定位 src/data
            agent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # src/agent
            project_root = os.path.dirname(os.path.dirname(agent_dir))               # FlowBD系统
            base_dir = os.path.join(project_root, "src", "data", "evidence_graphs")
        self.base_dir = base_dir
        safe = re.sub(r"[^\w\-.]", "_", self.session_id) or "session"
        self.path = os.path.join(base_dir, f"{safe}.json")

        self.nodes: Dict[str, EdgeNode] = {}
        self.edges: Dict[str, EdgeRel] = {}
        self.meta: Dict[str, Any] = {
            "session_id": self.session_id,
            "kg_version": DEFAULT_KG_VERSION,
            "schema": SCHEMA_VERSION,
        }
        self._by_norm_name: Dict[str, str] = {}   # 归一化名 → node_id
        if not fresh:
            self.load()

    # ------------------------------------------------------------------ 持久化

    def load(self) -> None:
        """文件缺失/损坏 = 空图(不抛异常, 闭环不因历史脏数据阻断)。"""
        self.nodes.clear()
        self.edges.clear()
        self._by_norm_name.clear()
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:                                   # noqa: BLE001
            self.meta['load_error'] = type(e).__name__
            logger.warning(f"[EvidenceGraph] 载入失败(按空图继续): {self.path} — {e}")
            return
        if not isinstance(data, dict) or not isinstance(data.get('nodes', []), list) or not isinstance(data.get('edges', []), list):
            self.meta['load_error'] = 'invalid_graph_schema'
            logger.warning('[EvidenceGraph] 图文件结构无效，按空图继续')
            return
        for nd in data.get("nodes") or []:
            try:
                node = EdgeNode.from_dict(nd)
                self.nodes[node.id] = node
                self._by_norm_name.setdefault(node.norm_name, node.id)
            except Exception as e:                               # noqa: BLE001
                logger.warning(f"[EvidenceGraph] 跳过坏节点: {e}")
        for ed in data.get("edges") or []:
            try:
                rel = EdgeRel.from_dict(ed)
                if rel.src in self.nodes and rel.dst in self.nodes:
                    self.edges[rel.eid] = rel
            except Exception as e:                               # noqa: BLE001
                logger.warning(f"[EvidenceGraph] 跳过坏边: {e}")
        if isinstance(data.get("meta"), dict):
            self.meta.update(data["meta"])
        self.meta["schema"] = SCHEMA_VERSION

    def save(self) -> None:
        """tmp + os.replace 原子写(计划 2.7)。"""
        os.makedirs(self.base_dir, exist_ok=True)
        payload = {"meta": self.meta, "nodes": [n.to_dict() for n in self.nodes.values()],
                   "edges": [e.to_dict() for e in self.edges.values()]}
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)

    def rebind(self, session_id: str) -> None:
        """更换会话 ID 并把当前图落盘到新文件(首轮迭代后 pending → 正式会话 ID)。

        旧文件一并删除, 防止后续新会话复用 "pending" 残留脏数据。
        """
        old_path = self.path
        self.session_id = str(session_id)
        safe = re.sub(r"[^\w\-.]", "_", self.session_id) or "session"
        self.path = os.path.join(self.base_dir, f"{safe}.json")
        self.meta["session_id"] = self.session_id
        self.save()
        try:
            if old_path != self.path and os.path.exists(old_path):
                os.remove(old_path)
        except OSError as e:                                     # noqa: PERF203
            logger.warning(f"[EvidenceGraph] 旧文件清理失败(无害): {e}")

    # ------------------------------------------------------------------ 写入

    def upsert_node(self, node: EdgeNode) -> str:
        """返回 "created" | "updated"。同 ID 幂等。"""
        existing = self.nodes.get(node.id)
        if existing is None:
            self.nodes[node.id] = node
            self._by_norm_name.setdefault(node.norm_name, node.id)
            return "created"
        # 同 ID 异名(理论罕见): 以先到者为准, 不覆盖
        return "updated"

    def find_node(self, name: str) -> Optional[str]:
        """按归一化名查节点 ID(合并器将关系绑定到已入图实体)。"""
        matches = [n.id for n in self.nodes.values() if n.norm_name == normalize_name(name)]
        return matches[0] if len(matches) == 1 else None

    def append_observation(self, node_key: str, obs: Observation) -> str:
        node = self.nodes.get(node_key)
        if node is None:
            raise KeyError(f"节点不存在: {node_key}")
        return node.append_observation(obs)

    def upsert_edge(self, rel: EdgeRel) -> str:
        """返回 "created" | "updated"(重复写入只刷新 last_seen_round, 不新增)。"""
        existing = self.edges.get(rel.eid)
        if existing is None:
            self.edges[rel.eid] = rel
            return "created"
        existing.last_seen_round = max(existing.last_seen_round, rel.last_seen_round)
        seen = {(p.source_id or p.paper_title) + normalize_name(p.quote)
                for p in [existing.prov] + existing.supporting_sources if p}
        for p in [rel.prov] + rel.supporting_sources:
            if p and ((p.source_id or p.paper_title) + normalize_name(p.quote)) not in seen:
                existing.supporting_sources.append(p)
                seen.add((p.source_id or p.paper_title) + normalize_name(p.quote))
        if rel.conflict_group and not existing.conflict_group:
            existing.conflict_group = rel.conflict_group
        return "updated"

    # ------------------------------------------------------------------ 回读(结构化记忆核心, 计划 3.3)

    def retrieve_from_graph(self, query_entities: List[str], max_lines: int = 10) -> str:
        """按查询实体做 1 跳邻域展开, 输出 ≤max_lines 行结构化摘要。

        该摘要是协调器判停依据 / 答案生成补充上下文 / 前端图谱说明三处共用的
        唯一传话介质——不注入任何原始检索文本(计划 1.3 机制二)。
        """
        if not self.nodes:
            return "(证据图为空)"
        qnorms = [canonical(q) for q in (query_entities or []) if str(q).strip()]
        query_text = ' '.join(map(str,query_entities or []))
        hit_ids = []
        for node in self.nodes.values():
            if retrieval_score(query_text,node)>0:
                hit_ids.append(node.id)
        # 1 跳邻域
        neighbor_ids = []
        for rel in self.edges.values():
            if rel.src in hit_ids or rel.dst in hit_ids:
                for end in (rel.src, rel.dst):
                    if end not in hit_ids and end not in neighbor_ids:
                        neighbor_ids.append(end)

        candidates = []
        scope = set(hit_ids + neighbor_ids)

        def relevance(text):
            value = canonical(text)
            score = 0
            for q in qnorms:
                grams = {q[i:i + 3] for i in range(max(0, len(q) - 2))}
                score += sum(g in value for g in grams)
            return score

        def provenance(prov):
            # JSON keeps the actual whitespace while retaining a single summary line.
            quote = json.dumps(prov.quote[:600], ensure_ascii=False)
            return (f"Ref-{prov.ref_id}, {prov.paper_title}, {prov.source_id}; "
                    f"位置={prov.location}; 原句={quote}")

        for nid in hit_ids + neighbor_ids:
            node = self.nodes[nid]
            usable = False
            for obs in node.observations:
                if not obs.prov or not obs.prov.source_id:
                    continue  # legacy unbound memory cannot supply a current citation
                usable = True
                line = f"[{node.ntype}|{node.name}] 观察: {obs.text} ({obs.status}, {provenance(obs.prov)})"
                candidates.append((relevance(obs.text + obs.prov.quote), line))
            if not usable:
                candidates.append((-1, f"[{node.ntype}|{node.name}] 仅实体；无可解析的原文来源，不作为答案证据"))
        for rel in self.edges.values():
            if rel.src not in scope or rel.dst not in scope or not rel.prov or not rel.prov.source_id:
                continue
            src, dst = self.nodes[rel.src], self.nodes[rel.dst]
            line = (f"[关系|{rel.etype}] {src.name} → {dst.name}: {rel.obs} "
                    f"({rel.status}, {provenance(rel.prov)})")
            candidates.append((relevance(rel.obs + rel.prov.quote) + 0.5, line))
        candidates.sort(key=lambda item: item[0], reverse=True)
        lines = [line for _, line in candidates[:max_lines]]
        return "\n".join(lines) if lines else "(证据图中无与查询相关且有来源身份的证据)"

    # ------------------------------------------------------------------ 冲突检测(计划 2.5)

    _UP_WORDS = ("提升", "提高", "增加", "增强", "改善", "上升", "gain", "increase", "improve", "enhance")
    _DOWN_WORDS = ("降低", "下降", "减少", "抑制", "衰减", "减弱", "decrease", "reduce", "suppress", "degrade")
    _NUM_RE = re.compile(r"\d+(?:\.\d+)?")


    @classmethod
    def _direction(cls, text: str) -> str:
        t = str(text or "").lower()
        has_up = any(w in t for w in cls._UP_WORDS)
        has_down = any(w in t for w in cls._DOWN_WORDS)
        if has_up and not has_down:
            return "up"
        if has_down and not has_up:
            return "down"
        return ""

    @classmethod
    def _conflicting(cls, text_a: str, text_b: str) -> bool:
        """方向相反且量化数值相差 >20% 才算冲突(计划 2.5)。"""
        da, db = cls._direction(text_a), cls._direction(text_b)
        if not da or not db or da == db:
            return False
        nums_a = [float(x) for x in cls._NUM_RE.findall(text_a)]
        nums_b = [float(x) for x in cls._NUM_RE.findall(text_b)]
        for a in nums_a:
            for b in nums_b:
                base = max(abs(a), abs(b))
                if base > 0 and abs(a - b) / base > 0.2:
                    return True
        return False

    def detect_conflict_group(self, dst_id: str, new_text: str) -> str:
        """若 new_text 与 dst 节点上既有观察矛盾, 返回冲突组 ID, 否则空串。"""
        node = self.nodes.get(dst_id)
        if node is None:
            return ""
        for o in node.observations:
            if self._conflicting(o.text, new_text):
                return conflict_group_id(node.name)
        return ""

    @staticmethod
    def _conditions(text: str) -> tuple:
        """Only explicit measured conditions can establish a comparable scope."""
        normalized = re.sub(r"\s+", "", str(text)).lower()
        values = re.findall(r"\d+(?:\.\d+)?(?:℃|°c|k|cycles|次循环|ma/cm2|mol/l|moll-1)", normalized)
        return tuple(sorted(values))

    def comparable_conflict(self, old: EdgeRel, new: EdgeRel) -> bool:
        if old.src != new.src or old.dst != new.dst or old.etype != new.etype:
            return False
        old_scope = self._conditions(old.prov.quote if old.prov else "")
        new_scope = self._conditions(new.prov.quote if new.prov else "")
        if not old_scope or old_scope != new_scope:
            return False
        def metric_units(value):
            text = re.sub(r'\s+', '', unicodedata.normalize('NFKC', str(value)))
            return set(re.findall(r'\d+(?:\.\d+)?(mAh(?:/g)?|Ah(?:/g)?|mS/cm|S/cm|kWh/m3|Wh/L|Wh/kg|mW/cm2|W/mK|kJ/mol|%|倍)', text))
        old_units, new_units = metric_units(old.obs), metric_units(new.obs)
        if not old_units or old_units != new_units:
            return False
        return self._conflicting(old.obs, new.obs)

    # ------------------------------------------------------------------ 快照与统计

    def snapshot(self) -> Dict[str, Any]:
        """给前端/状态对象用的纯数据快照(app.py 持久化 message_data["evidence_graph"])。"""
        return {"meta": dict(self.meta), "nodes": [n.to_dict() for n in self.nodes.values()],
                "edges": [e.to_dict() for e in self.edges.values()], "stats": self.stats()}

    def stats(self) -> Dict[str, Any]:
        by_type: Dict[str, int] = {}
        for n in self.nodes.values():
            by_type[n.ntype] = by_type.get(n.ntype, 0) + 1
        conflicts = sorted({e.conflict_group for e in self.edges.values() if e.conflict_group})
        return {
            "nodes": len(self.nodes), "edges": len(self.edges),
            "by_type": by_type, "conflict_groups": conflicts,
        }

    # ------------------------------------------------------------------ M5 接口占位(计划 0.3 红线 7)

    def import_confirmed(self, *_args, **_kwargs):
        """Stage B 审计数据只读导入 confirmed 边 — 本期不实现(计划 M5 另行评审)。

        唯一的 confirmed 合法来源: paper/method_evolution_v2/ 下 Stage B 审计产物。
        任何代码路径不得绕过此接口把 LLM 产出升级为 confirmed。
        """
        raise NotImplementedError("confirmed 只读导入属 M5(另行评审); LLM 写回一律 candidate")
