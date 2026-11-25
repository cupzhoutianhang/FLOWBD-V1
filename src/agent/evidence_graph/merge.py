"""merge_round — 每轮证据写回的查重/限额/冲突编组(计划 3.4 / 2.5 / 2.6)。

顺序固定: 实体归一 → 节点查重 → 观察去重 → 限额裁剪 → 边幂等 → 冲突编组。
M2 写回路径不产 FINDING 节点: 关系级结论短句(obs)挂边与目标实体,
证据级 FINDING→实体 连接由关系级 obs 承载(计划 2.1/2.2 的 FINDING 类型保留给 Stage B 导入)。
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import List

from .schema import (
    MERGE_CAPS,
    NODE_TYPES,
    Observation,
    Provenance,
    EdgeNode,
    EdgeRel,
    edge_id,
    node_id,
)
from .store import EvidenceGraphStore

logger = logging.getLogger(__name__)


@dataclass
class MergeReport:
    """单轮合并报告: 供日志与 50 题评测统计截断率/去重率。"""

    round_no: int = 0
    new_nodes: int = 0
    new_edges: int = 0
    updated_nodes: int = 0
    dup_skipped: int = 0
    dropped: List[str] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)

    def summary(self) -> str:
        return (f"+{self.new_nodes}节点/+{self.new_edges}边, 更新{self.updated_nodes}, "
                f"去重跳过{self.dup_skipped}, 截断丢弃{len(self.dropped)}, 冲突{len(self.conflicts)}")


def merge_round(store: EvidenceGraphStore, extraction, round_no: int) -> MergeReport:
    """把一轮 ExtractionResult 合并进 store。extraction 为 None/空时返回零报告。"""
    report = MergeReport(round_no=round_no)
    if extraction is None:
        return report
    cap_nodes, cap_edges = MERGE_CAPS["new_nodes"], MERGE_CAPS["new_edges"]

    # ---------------- 1) 实体 ----------------
    for ent in getattr(extraction, "entities", None) or []:
        try:
            name = str(ent.get("name") or "").strip()
            ntype = str(ent.get("type") or "").strip().upper()
            obs_texts = [str(t or "").strip() for t in (ent.get("observations") or [])]
            obs_texts = [t for t in obs_texts if t]
            prov = ent.get("_prov")
            records = ent.get("observation_records") or [
                {"text": t, "_prov": prov} for t in obs_texts]
            by_text = {r["text"]: r["_prov"] for r in records}
            if not name or ntype not in NODE_TYPES:
                report.dropped.append(f"实体非法: {name!r}/{ntype!r}")
                continue
            if not obs_texts:
                report.dropped.append(f"实体无观察, 丢弃: {name}")
                continue
            if not isinstance(prov, Provenance):
                report.dropped.append(f"实体无 provenance, 拒收: {name}")
                continue

            nid = node_id(ntype, name)
            node = store.nodes.get(nid)
            if node is None:
                if report.new_nodes >= cap_nodes:
                    report.dropped.append(f"实体超每轮限额({cap_nodes}), 丢弃: {name}")
                    continue
                first = Observation(text=obs_texts[0], prov=by_text[obs_texts[0]])
                node = EdgeNode(id=nid, ntype=ntype, name=name, created_round=round_no)
                node.observations.append(first)
                store.upsert_node(node)
                report.new_nodes += 1
                rest = obs_texts[1:]
            else:
                report.updated_nodes += 1
                rest = obs_texts

            for text in rest:
                try:
                    outcome = store.append_observation(nid, Observation(text=text, prov=by_text[text]))
                    if outcome == "dup":
                        report.dup_skipped += 1
                    elif outcome == "full":
                        report.dropped.append(f"观察超每节点上限, 丢弃: {name} — {text[:24]}…")
                except ValueError as e:
                    report.dropped.append(str(e))
        except ValueError as e:                                  # noqa: PERF203
            report.dropped.append(str(e))
        except Exception as e:                                   # noqa: BLE001
            report.dropped.append(f"实体合并兜底: {e}")

    # ---------------- 2) 关系 ----------------
    for rel in getattr(extraction, "relations", None) or []:
        try:
            src_name = str(rel.get("src") or "").strip()
            dst_name = str(rel.get("dst") or "").strip()
            rtype = str(rel.get("type") or "").strip().upper()
            obs = str(rel.get("obs") or "").strip()
            prov = rel.get("_prov")

            src_id = store.find_node(src_name)
            dst_id = store.find_node(dst_name)
            if not src_id or not dst_id:
                report.dropped.append(f"关系端点未入图: {src_name} -> {dst_name}")
                continue
            if not isinstance(prov, Provenance):
                report.dropped.append(f"关系无 provenance, 拒收: {src_name}->{dst_name}")
                continue
            if rtype in {"SUPPORTS", "REFUTES", "INCONCLUSIVE_FOR"} and store.nodes[dst_id].ntype not in {"FINDING", "PROPERTY"}:
                report.dropped.append(f"关系语义端点不符: {rtype} 不能将工艺/材料作为被支持或反驳的结论: {dst_name}")
                continue
            if rtype == "CITES" and (store.nodes[src_id].ntype != "PAPER" or store.nodes[dst_id].ntype != "PAPER"):
                report.dropped.append(f"CITES 必须连接文献: {src_name}->{dst_name}")
                continue

            if (rtype=='ATTRIBUTED_TO' and store.nodes[dst_id].ntype=='MATERIAL'
                and store.nodes[src_id].ntype in {'METHOD','MATERIAL','TASK'}
                and re.search(r'原料|使用|采用|制备于|prepared\s+(?:with|from)|uses?\b',obs,re.I)):
                if obs:
                    store.append_observation(src_id,Observation(text=obs,prov=prov))
                report.dropped.append(f'归因类型不能代替原料使用关系，保留候选观察而拒收错误边: {src_name}->{dst_name}')
                continue
            if rtype=='MECHANISM_OF' and store.nodes[src_id].ntype!='MECHANISM':
                report.dropped.append(f'MECHANISM_OF源端必须是机理节点，不将制备方法当机理: {src_name}->{dst_name}')
                continue
            if rtype=='ATTRIBUTED_TO' and store.nodes[src_id].ntype not in {'PROPERTY','FINDING'}:
                report.dropped.append(f'ATTRIBUTED_TO源端必须是属性或发现: {src_name}->{dst_name}')
                continue
            from .relevance import fact_key, same_evidence
            eid = edge_id(src_id, dst_id, rtype, payload=obs or prov.quote)
            for prior in store.edges.values():
                if (prior.src==src_id and prior.dst==dst_id and prior.etype==rtype
                    and prior.status=='candidate' and same_evidence(prior.prov,prov)
                    and fact_key(prior.obs)==fact_key(obs)):
                    eid=prior.eid
                    if obs!=prior.obs and obs not in prior.text_variants:
                        prior.text_variants.append(obs)
                    break
            if eid in store.edges:
                store.upsert_edge(EdgeRel(
                    eid=eid, src=src_id, dst=dst_id, etype=rtype,
                    prov=prov, obs=obs, last_seen_round=round_no))
                report.dup_skipped += 1
                continue
            if report.new_edges >= cap_edges:
                report.dropped.append(f"关系超每轮限额({cap_edges}), 丢弃: {src_name}->{dst_name}")
                continue

            # 冲突编组(计划 2.5): 新边与 dst 既有观察矛盾 → 双边保留
            conflict_group = ""
            edge = EdgeRel(eid=eid, src=src_id, dst=dst_id, etype=rtype,
                           prov=prov, obs=obs, conflict_group=conflict_group,
                           last_seen_round=round_no)
            peers = [other for other in store.edges.values() if store.comparable_conflict(other, edge)]
            if peers:
                from .schema import conflict_group_id
                conflict_group = conflict_group_id(src_id + dst_id + str(store._conditions(prov.quote)))
                edge.conflict_group = conflict_group
                for other in peers:
                    other.conflict_group = conflict_group
            store.upsert_edge(edge)
            report.new_edges += 1

            if conflict_group:
                report.conflicts.append(f"{conflict_group}: {src_name}->{dst_name} — {obs[:24]}…")
                _mark_conflict_peers(store, dst_id, edge)

            if obs:
                try:
                    outcome = store.append_observation(dst_id, Observation(text=obs, prov=prov))
                    if outcome == "dup":
                        report.dup_skipped += 1
                except ValueError as e:
                    report.dropped.append(str(e))
        except ValueError as e:                                  # noqa: PERF203
            report.dropped.append(str(e))
        except Exception as e:                                   # noqa: BLE001
            report.dropped.append(f"关系合并兜底: {e}")

    if report.dropped or report.conflicts:
        logger.info(f"[EvidenceGraph] round{round_no} 合并: {report.summary()}; "
                    f"dropped={report.dropped[:5]} conflicts={report.conflicts[:3]}")
    else:
        logger.info(f"[EvidenceGraph] round{round_no} 合并: {report.summary()}")
    return report


def _mark_conflict_peers(store: EvidenceGraphStore, dst_id: str, new_edge: EdgeRel) -> None:
    """把同 dst 上方向相反的既有候选边编入同组(冲突双边保留, 不覆盖)。"""
    for other in store.edges.values():
        if other.eid == new_edge.eid or other.dst != dst_id:
            continue
        if other.conflict_group:
            continue
        if store.comparable_conflict(other, new_edge):
            other.conflict_group = new_edge.conflict_group
