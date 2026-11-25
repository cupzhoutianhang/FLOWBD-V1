"""IterativeCoordinator — 证据图状态驱动的迭代研究规划(M3, 计划 3.6)。

纯 Python 生成器状态机等价实现 DeepEvidence 的 LangGraph 协调器(环境未装
langgraph, 且引入重依赖违背最小改动原则; 对应关系见计划 3.6 映射表):
  StateGraph ↔ run() 生成器; state channel ↔ CoordinatorState;
  conditional edge ↔ _decide() 返回动作; END ↔ TERMINATE。

每一步必须是"工具调用"(检索/写回/判停), LLM 输出非法动作时强制终止
(论文约束: 每步必须工具调用否则停止)。判停依据是回读图(机制二):
retrieve_from_graph 的 ≤10 行摘要, 不注入任何原始检索文本。

对 part5 的依赖延迟到 __init__ 内导入, 避免 part5 → evidence_graph → part5 循环。
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterator, List, Optional

from .extractor import EvidenceExtractor
from .store import EvidenceGraphStore
try:
    from ..evidence_sources import SourceRegistry, prepare_sources
    from ..structured_llm import call_structured
except ImportError:
    from evidence_sources import SourceRegistry, prepare_sources
    from structured_llm import call_structured

logger = logging.getLogger(__name__)

ACTIONS = ("BFRS", "DFRS", "WRITE_GRAPH", "TERMINATE")


@dataclass
class CoordinatorState:
    """计划 / 预算 / 轮次 —— 协调器自身的状态通道。"""

    plan: List[dict] = field(default_factory=list)   # [{"step": str, "done": bool}]
    round_no: int = 0
    budget_left: int = 3
    stop_reason: str = ""


# 初始计划 prompt(首轮, LLM 产出 checkbox 式研究计划)
INIT_PLAN_PROMPT = """你是储能领域研究规划器。针对研究问题, 给出 1-5 项可核验的信息需求清单(checkbox 计划)。
每项 step 是一个具体的信息需求(如"铁铬液流电池析氢反应的主导机理是什么"), 不要写成动作。
仅拆解用户实际要求，不为凑条目数添加气氛、模板、额外材料性能等假定需求。步骤题优先工序、必要配比/时间/温度和明确缺口；策略题区分问题体系与外体系参考。
只输出 JSON: {{"plan": [{{"step": "...", "done": false}}]}}

【研究问题】{question}"""

# 判停 prompt(全文见计划 3.6)
PLAN_PROMPT = """你是研究规划器。根据当前证据图摘要, 判断研究计划的完成度并决定下一步。

规则:
1. plan 数组逐项给出 done(该信息需求是否已有图内候选证据支撑)，保留当前step_id和原step，不新增、改写或删除需求。列出对应的 evidence_source_ids（摘要中的 SRC 标识）；无标识不能标 done。candidate不代表已确认结论。
2. next_action 只能是: BFRS(广度检索), DFRS(定向深查), WRITE_GRAPH(把上轮检索结果写入证据图), TERMINATE(证据已足, 终止作答)。
3. 证据不足且预算未尽时选检索; 上轮有新检索结果未入库时选 WRITE_GRAPH; 计划全 done 或检索已无新信息时选 TERMINATE。
4. 只输出 JSON: {{"updated_plan":[{{"step_id":"R1","step":"...","done":false,"evidence_source_ids":[]}}],
   "next_action":"BFRS","action_args":{{"query":"定向检索词, 仅DFRS需要"}},
   "sufficiency_reason":"≤30词理由"}}

【研究问题】{question}
【当前计划】{plan_json}
【证据图摘要(≤10行)】{graph_summary}
【摘要行格式】[类型|名称] 观察: <事实短句> (状态, Ref-n, 论文); 类型 ∈ PAPER/METHOD/MATERIAL/PROPERTY/MECHANISM/TASK/FINDING
【剩余检索预算】{budget_left}
【已完成轮次】{round_no}"""


class IterativeCoordinator:
    """迭代闭环协调器。pipeline 为 part5.MultiAgentPipeline(复用其四个子 Agent)。"""

    def __init__(self, pipeline, llm, store: EvidenceGraphStore,
                 max_rounds: int = 3, extractor: Optional[EvidenceExtractor] = None,
                 summarized_answer: bool = False):
        # 延迟导入: part5 顶部会 import evidence_graph(Stage 5 写回), 顶层导入会循环
        from .schema import normalize_name  # noqa: F401  (保持包内一致性)

        self.pipeline = pipeline
        self.llm = llm
        self.store = store
        self.max_rounds = max(1, int(max_rounds))
        self.extractor = extractor or EvidenceExtractor(llm)
        self.last_state: Optional[CoordinatorState] = None   # 最近一次 run 的协调器状态(测试/前端可读)
        # 借鉴③(R9): True 时终止作答用图摘要替换全量融合上下文(doc_sources 不裁剪);
        # 默认 False = 行为与 v3.0.0+M1-M4 一致
        self.summarized_answer = bool(summarized_answer)
        self.registry = SourceRegistry(store.meta.get("source_registry"))

    # ------------------------------------------------------------------ 对外入口

    def run(self, question: str) -> Iterator["object"]:
        """生成器: 逐轮 yield AgentPipelineState(复用现有前端协议字段)。

        最终轮 state.final_answer / evidence_graph_snapshot / round_no 就绪。
        任何子 Agent 异常都兜底为"如实说明证据不足", 不向上抛。

        part5 导入采用双路径: 生产以 `agent.part5_multiagent_integration` 前缀
        导入 → 相对导入命中同一实例; 单测(top-level 包)回落 AGENT_DIR 路径。
        """
        try:
            from ..part5_multiagent_integration import AgentPipelineState
        except ImportError:
            from part5_multiagent_integration import AgentPipelineState

        state = AgentPipelineState(
            request_id=f"iter_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            original_question=question,
        )
        state.round_no = 0
        state.source_registry = self.registry
        coord = CoordinatorState(budget_left=self.max_rounds)
        seen_queries = set()
        self.last_state = coord

        try:
            yield state
            # ---- 轮 1: 解析 + 广度检索 ----
            state.round_no = 1
            state.log("Coordinator", "轮1: 问题解析 + 广度检索(BFRS)")
            try:
                self.pipeline.parsing_agent.parse(state)
            except Exception as e:                               # noqa: BLE001
                state.log("Coordinator", f"解析失败(继续): {e}")
            state.stage_1_complete = True
            coord.plan = self._init_plan(question)
            yield state

            initial_query = str(state.parsed_question or question).strip()
            initial_retrieved = self._do_retrieval(state, initial_query, "BFRS")
            state.stage_2_complete = True
            state.round_no = 1
            if initial_retrieved:
                seen_queries.add(self._query_key(initial_query))
                coord.budget_left -= 1
            state.iterations.append({"round": 1, "action": "BFRS",
                                     "query": initial_query[:80],
                                     "writes": None,
                                     "reason": "初始计划广度检索" if initial_retrieved else "初始检索未执行"})
            yield state

            pending_results = initial_retrieved
            while True:
                # ---- 写回: 上轮检索结果 → 证据图 ----
                if pending_results:
                    state.round_no += 1
                    self._write_back(state, question)
                    pending_results = False
                    yield state

                # ---- 回读判停 ----
                summary = self.store.retrieve_from_graph(
                    self._plan_entities(coord, state))
                coord.round_no = state.round_no
                action, reason, dfrs_query = self._decide(question, coord, summary)
                state.log("Coordinator",
                          f"判停: next={action} 预算={coord.budget_left} 理由={reason}")
                if action in ("TERMINATE",) or action not in ("BFRS", "DFRS"):
                    state.iterations.append({"round": state.round_no, "action": action,
                                             "query": None, "writes": None,
                                             "reason": reason or None})
                yield state

                if action == "TERMINATE":
                    coord.stop_reason = reason or "计划完成或无新证据"
                    break
                if coord.budget_left <= 0:
                    coord.stop_reason = "检索预算耗尽, 强制终止"
                    break
                if action == "WRITE_GRAPH":
                    # 合法动作, 但检索结果已在判停前统一入库 → 无事可做, 按终止处理
                    coord.stop_reason = "规划器请求写回, 但检索结果已入库, 按终止处理"
                    break
                if action not in ("BFRS", "DFRS"):
                    coord.stop_reason = f"规划器输出非法动作({action}), 强制终止"
                    break

                # ---- 执行检索动作(每步都是工具调用) ----
                state.round_no += 1
                if action == "DFRS":
                    query = str(dfrs_query or '').strip()
                    if not query:
                        coord.stop_reason = "定向检索缺少有效查询词，没有新的检索方向，终止"
                        break
                else:
                    query = str(dfrs_query or question).strip()
                    if not query:
                        coord.stop_reason = "广度检索缺少有效查询词，没有新的检索方向，终止"
                        break
                query_key = self._query_key(query)
                if query_key in seen_queries:
                    coord.stop_reason = "规划器重复已执行的查询，没有新的检索方向，终止"
                    break
                if not self._do_retrieval(state, query, action):
                    coord.stop_reason = "检索动作未执行或失败，终止"
                    break
                seen_queries.add(query_key)
                coord.budget_left -= 1
                pending_results = True
                state.iterations.append({"round": state.round_no, "action": action,
                                         "query": str(query)[:80],
                                         "writes": None, "reason": reason or None})
                yield state

            # ---- 终止作答: 融合 + 生成(图摘要作为补充上下文, 不注入原始文本) ----
            state.log("Coordinator", f"终止作答: {coord.stop_reason}")
            graph_summary = self.store.retrieve_from_graph(
                self._plan_entities(coord, state))
            try:
                self.pipeline.fusion_agent.fuse(state)
            except Exception as e:                               # noqa: BLE001
                state.log("Coordinator", f"融合失败(继续): {e}")
            state.stage_3_complete = True
            full_context = state.fused_context or ''
            summary_used = False
            summary_check = {'passed': False, 'reason': 'not_requested' if not self.summarized_answer else 'no_source_bound_summary'}
            # 图摘要必须在 fuse 之后注入: fusion_agent 会从 vector_chunks 重新生成
            # fused_context 并覆盖, 提前 append 会被冲掉(B1 修复)
            if graph_summary and re.search(r"SRC:[A-Za-z0-9]+", graph_summary):
                # Reintroduce only referenced memory sources; unrelated past questions stay out.
                memory_refs = {int(v) for v in re.findall(r"Ref-(\d+)", graph_summary)}
                state.active_source_ids.update(c["source_id"] for c in self.registry.chunks.values()
                                               if c["ref_id"] in memory_refs)
                state.doc_sources = self.registry.documents(state.active_source_ids)
                if self.summarized_answer:
                    from .summary_coverage import check_summary_coverage
                    summary_check = check_summary_coverage(question, full_context, graph_summary, coord.plan)
                    # 借鉴③(R9·引用锚点完整性): 事实来自图摘要, 替代全量融合上下文;
                    # doc_sources 全量保留 → [Ref-n] 引用锚点不丢
                    if summary_check['passed']:
                        state.fused_context = (
                            "【证据图摘要(跨轮累积证据, 引用见文献来源列表)】\n" + graph_summary)
                        summary_used = True
                        state.log("Coordinator", "答案·图摘要模式: 必要事实保留检查通过，使用摘要；语义覆盖仍未保证")
                    else:
                        state.fused_context = full_context + "\n\n【相关证据图记忆】\n" + graph_summary
                        state.log("Coordinator", "摘要保留检查未通过，已回退完整融合证据，不计摘要压缩收益")
                else:
                    state.fused_context = (state.fused_context or "") + (
                        "\n\n【证据图摘要(跨轮累积证据, 可直接引用)】\n" + graph_summary)
            yield state
            generation_failed = False
            state.answer_requirements=[dict(item) for item in coord.plan]
            try:
                self.pipeline.answer_agent.generate(state)
            except Exception as e:                               # noqa: BLE001
                generation_failed = True
                state.log("Coordinator", f"答案生成失败: {e}")
                state.final_answer = state.final_answer or (
                    "抱歉, 本次迭代闭环未能生成有效答案(答案生成阶段异常)。")
            final_text = str(state.final_answer or '').strip()
            generation_failed = (generation_failed or not final_text or
                final_text.startswith(('❌', '无法生成答案', '本次迭代发生异常',
                                       '抱歉, 本次迭代闭环未能生成有效答案')) or
                state.answer_quality.get('generation_status') == 'failed')
            state.stage_4_complete = not generation_failed
            state.answer_quality['generation_status'] = 'failed' if generation_failed else 'returned_final_answer'
            state.evidence_graph_snapshot = self.store.snapshot()
            state.eg_stop_reason = ('答案生成失败；检索阶段判停：' if generation_failed else '') + coord.stop_reason
            category = ('generation_failure' if generation_failed
                        else 'planning_failure' if any(w in coord.stop_reason for w in ('异常', '非法', '失败'))
                        else 'budget_exhausted' if '预算' in coord.stop_reason
                        else 'no_new_evidence' if any(w in coord.stop_reason for w in ('重复', '无新'))
                        else 'evidence_sufficient' if coord.plan and all(item.get('done') for item in coord.plan)
                        else 'incomplete_evidence')
            if state.operation_errors and not generation_failed:
                category = 'degraded_' + category
            state.answer_quality['iterative_stop'] = {'category': category, 'errors': list(state.operation_errors),
                                                      'plan_all_done': bool(coord.plan) and all(item.get('done') for item in coord.plan)}
            state.answer_quality['graph_context'] = {
                'summarized_requested': self.summarized_answer,
                'mode': 'graph_summary' if summary_used else 'full_context',
                'summary_chars': len(graph_summary),
                'coverage_check': summary_check,
                'fallback_to_full_context': self.summarized_answer and not summary_used,
            }
            state.iterations.append({"round": state.round_no, "action": "TERMINATE",
                                     "reason": state.eg_stop_reason, "query": None, "writes": None})
            self.store.meta["last_plan"] = {"question": question, "items": coord.plan,
                                           "stop_reason": state.eg_stop_reason, 'stop_category': category,
                                           'operation_errors': list(state.operation_errors)}
            self.store.save()
            state.evidence_graph_snapshot = self.store.snapshot()
            state.log("Coordinator",
                      f"闭环完成: {self.store.stats()['nodes']}节点/"
                      f"{self.store.stats()['edges']}边; 停止原因: {state.eg_stop_reason}")
            yield state
        except Exception as e:                                   # noqa: BLE001
            state.log("Coordinator", f"协调器兜底异常(不影响单轮回答): {e}")
            state.eg_stop_reason = '协调器异常，未完成正常迭代'
            state.answer_quality['iterative_stop'] = {'category': 'coordinator_failure', 'errors': [type(e).__name__]}
            if not state.final_answer:
                state.final_answer = '本次迭代发生异常，未能生成可核查答案。'
            state.evidence_graph_snapshot = self.store.snapshot()
            yield state

    # ------------------------------------------------------------------ 工具化步骤

    def _do_retrieval(self, state, query: str, action: str) -> bool:
        """检索动作。DFRS 用定向 query 的临时 state, 结果并回主 state。"""
        query = str(query or '').strip()
        if not query:
            state.log("Coordinator", f"{action} 检索跳过: 查询词为空")
            return False
        try:
            # Every round uses a fresh request; retrieval cannot overwrite previous rounds.
            tmp = type(state)(
                request_id=f"{state.request_id}_dfrs{state.round_no}",
                original_question=str(query),
            )
            tmp.parsed_question = str(query)
            if action == "DFRS":
                self.pipeline.parsing_agent.parse(tmp)
            else:
                tmp.extracted_entities = list(state.extracted_entities)[:5]
                tmp.extracted_entities_en = list(state.extracted_entities_en)[:5]
                tmp.query_intent = state.query_intent
            self.pipeline.retrieval_agent.retrieve(tmp)
            # 累积到主 state(结构化记忆: 检索原文已落盘, 主 state 只累积结构化结果)
            keys = {(c.get("source"), c.get("parent_id"), c.get("content"))
                    for c in state.vector_chunks}
            for c in tmp.vector_chunks:
                key = (c.get("source"), c.get("parent_id"), c.get("content"))
                if key not in keys:
                    state.vector_chunks.append(c)
                    keys.add(key)
            state.markdown_blocks.extend(tmp.markdown_blocks)
            for k, v in (tmp.graph_entities or {}).items():
                state.graph_entities.setdefault(k, v)
            state.graph_relations.extend(
                r for r in (tmp.graph_relations or []) if r not in state.graph_relations)
            for v in (tmp.molecule_results or []):
                state.molecule_results.append(v)
            state.doc_sources.extend(tmp.doc_sources or [])
            state.lineage_sources = list(getattr(tmp, "lineage_sources", []) or [])
            prepare_sources(state, self.registry)
            state.log("Coordinator", f"{action} 检索完成: {str(query)[:60]}")
            return True
        except Exception as e:                                   # noqa: BLE001
            state.operation_errors.append('retrieval_failure:' + type(e).__name__)
            state.log("Coordinator", f"检索动作失败(本轮空手): {e}")
            return False

    def _write_back(self, state, question: str) -> None:
        """WRITE_GRAPH: 抽取 → 合并 → 落盘 → 快照。"""
        try:
            prepare_sources(state, self.registry)
            result = self.extractor.extract(
                question=question,
                context=self._chunks_brief(state),
                answer="",
                doc_sources=state.doc_sources or [],
                round_no=state.round_no,
            )
            from .merge import merge_round
            report = merge_round(self.store, result, state.round_no)
            self.store.meta["source_registry"] = self.registry.to_dict()
            self.store.save()
            state.evidence_graph_snapshot = self.store.snapshot()
            msg = f"轮{state.round_no} 写回: {report.summary()}"
            if self.extractor.last_errors:
                msg += f"; 抽取备注: {self.extractor.last_errors[:2]}"
                if not result:
                    state.operation_errors.append('extraction_failure')
            state.log("EvidenceGraph", msg)
            state.iterations.append({"round": state.round_no, "action": "WRITE_GRAPH",
                                     "query": None, "writes": report.summary(), "reason": None,
                                     "new_nodes": report.new_nodes, "new_edges": report.new_edges,
                                     "dropped": report.dropped, "extract_errors": self.extractor.last_errors,
                                     "semantic_audit": getattr(self.extractor, 'last_semantic_audit', {}),
                                     "source_count": len(state.doc_sources)})
        except Exception as e:                                   # noqa: BLE001
            state.operation_errors.append('write_failure:' + type(e).__name__)
            state.log("EvidenceGraph", f"写回失败(已忽略): {e}")

    @staticmethod
    def _chunks_brief(state) -> str:
        parts = []
        for doc in sorted(state.doc_sources or [], key=lambda d: {'lineage':0,'pdf_supplement':1}.get(d.get('type'),2)):
            for c in doc.get("chunks") or [doc]:
                brief = str(c.get("content") or "")[:1100]
                if brief:
                    parts.append(f"[{c.get('source_id', '')}][Ref-{doc['ref_id']}][{doc.get('source_label', '')}] {brief}")
                if sum(len(p) for p in parts) >= 5600:
                    return "\n".join(parts)[:6000]
        return "\n".join(parts)

    # ------------------------------------------------------------------ LLM 规划/判停

    def _init_plan(self, question: str) -> List[dict]:
        try:
            raw = call_structured(self.llm, INIT_PLAN_PROMPT.format(question=question[:600]), max_tokens=1200)
            data = self._parse_json(raw)
            plan = []
            for item in (data or {}).get("plan", [])[:5]:
                step = str(item.get("step") or "").strip()
                if step:
                    plan.append({"step_id":f'R{len(plan)+1}',"step": step, "done": False})
            if plan:
                return plan
        except Exception as e:                                   # noqa: BLE001
            logger.warning(f"[Coordinator] 初始计划生成失败, 用默认计划: {e}")
        return [{"step_id":"R1","step": f"围绕问题核心收集证据: {question[:40]}", "done": False}]

    def _decide(self, question: str, coord: CoordinatorState, graph_summary: str):
        """回读判停。返回 (action, sufficiency_reason, dfrs_query)。

        LLM 输出非法/异常 → 强制 TERMINATE(每步必须工具调用, 否则停止)。
        """
        try:
            raw = call_structured(self.llm,
                PLAN_PROMPT.format(
                    question=question[:600], plan_json=json.dumps(coord.plan, ensure_ascii=False),
                    graph_summary=graph_summary[:10000], budget_left=coord.budget_left,
                    round_no=coord.round_no),
                max_tokens=1200)
            data = self._parse_json(raw)
            action = str((data or {}).get("next_action") or "").strip().upper()
            reason = str((data or {}).get("sufficiency_reason") or "").strip()
            query = str(((data or {}).get("action_args") or {}).get("query") or "").strip()
            if action not in ACTIONS:
                return "TERMINATE", f"规划器输出非法动作({action!r})", ""
            updated = (data or {}).get("updated_plan")
            if isinstance(updated, list) and updated:
                valid_sources = set(re.findall(r"SRC:[A-Za-z0-9]+", graph_summary))
                # Completion updates cannot silently replace the user's frozen
                # needs with an easier checklist or add unrelated research.
                for item in coord.plan:
                    match=next((u for u in updated if isinstance(u,dict) and (
                        item.get('step_id') and u.get('step_id')==item['step_id'] and u.get('step') in (None,'',item.get('step')) or
                        not u.get('step_id') and u.get('step')==item.get('step'))),None)
                    if match is None:continue
                    source_ids=match.get('evidence_source_ids')
                    selected=(set(source_ids) & valid_sources) if isinstance(source_ids,list) and all(isinstance(s,str) for s in source_ids) else set()
                    item['done']=bool(match.get('done')) and bool(selected)
                    item['evidence_source_ids']=sorted(selected)
            return action, reason, query
        except Exception as e:                                   # noqa: BLE001
            logger.warning(f"[Coordinator] 判停兜底: {e}")
            return "TERMINATE", f"判停调用异常({e}), 强制终止", ""

    @staticmethod
    def _query_key(query: str) -> str:
        """Normalize semantically identical retrieval queries for deduplication."""
        normalized = unicodedata.normalize('NFKC', str(query or '')).casefold()
        return ''.join(char for char in normalized
                       if not char.isspace() and not unicodedata.category(char).startswith('P'))

    @staticmethod
    def _pending_unwritten(graph_summary: str) -> bool:
        # 简化近似: 图为空说明尚无任何入库结果, 存在未写回检索的可能
        return not graph_summary or graph_summary.startswith("(")

    # ------------------------------------------------------------------ 辅助

    @staticmethod
    def _parse_json(raw: str) -> Optional[dict]:
        if not raw or str(raw).startswith("❌"):
            return None
        text = str(raw).strip()
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            return None
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _plan_entities(coord: CoordinatorState, state) -> List[str]:
        ents = [str(e) for e in (state.extracted_entities or [])][:8]
        ents.extend(str(e) for e in (getattr(state, 'extracted_entities_en', []) or [])[:8])
        for item in coord.plan:
            step = str(item.get("step") or "")
            if step and step not in ents:
                ents.append(step[:30])
        return ents or [str(state.original_question)[:40]]
