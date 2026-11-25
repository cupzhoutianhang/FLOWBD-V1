"""evidence_graph 包单元测试(M1, 计划第 5 章验收 A1/A5).

跑法(与 test_answer_cleaner 同口径):
    cd src/agent && python -m unittest tests.test_evidence_graph -v
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_AGENT_DIR = os.path.dirname(_THIS_DIR)
if _AGENT_DIR not in sys.path:
    sys.path.insert(0, _AGENT_DIR)

from evidence_graph import (                      # noqa: E402
    MERGE_CAPS,
    Observation,
    Provenance,
    EdgeNode,
    EdgeRel,
    EvidenceGraphStore,
    EvidenceExtractor,
    ExtractionResult,
    IterativeCoordinator,
    edge_id,
    finding_id,
    merge_round,
    node_id,
    normalize_name,
    word_count,
)


def _prov(ref_id=1, quote="原文逐字片段用于测试", round_no=1):
    return Provenance(ref_id=ref_id, paper_title="测试论文", quote=quote, round=round_no, source_id="SRC:unitfixture")


def _entity(name, ntype="METHOD", obs=("循环1000圈容量保持率87%",)):
    return {"name": name, "type": ntype, "observations": list(obs), "_prov": _prov()}


def _relation(src, dst, rtype="ASSOCIATED_WITH", obs="容量保持率提升10%", quote="原文逐字片段用于测试"):
    return {"src": src, "dst": dst, "type": rtype, "obs": obs,
            "evidence_quote": quote, "_prov": _prov(quote=quote)}


# =====================================================================
# schema
# =====================================================================

class TestSchema(unittest.TestCase):

    def test_word_count_english(self):
        self.assertEqual(word_count("capacity retention of 87 percent after 1000 cycles"), 8)

    def test_word_count_chinese(self):
        # 中文 2 字符折 1 词: 17 字 → 9 词
        self.assertEqual(word_count("循环一千圈后容量保持率为百分之八十七"), 9)

    def test_normalize_name(self):
        self.assertEqual(normalize_name("  LiFePO4 正极 材料 "), "lifepo4正极材料")

    def test_node_id_idempotent(self):
        self.assertEqual(node_id("METHOD", "喷雾热解法"), node_id("METHOD", " 喷雾热解法 "))
        self.assertNotEqual(node_id("METHOD", "A法"), node_id("METHOD", "B法"))
        self.assertNotEqual(node_id("METHOD", "A法"), node_id("MATERIAL", "A法"))

    def test_node_id_illegal_type(self):
        with self.assertRaises(ValueError):
            node_id("NOT_A_TYPE", "x")

    def test_edge_id_stable_on_same_payload(self):
        p = "PAPER:abc", "METHOD:def"
        self.assertEqual(edge_id(*p, "SUPPORTS", "同payload"), edge_id(*p, "SUPPORTS", "同payload"))
        self.assertNotEqual(edge_id(*p, "SUPPORTS", "x"), edge_id(*p, "SUPPORTS", "y"))
        with self.assertRaises(ValueError):
            edge_id("a", "b", "BAD_TYPE")

    def test_finding_id_idempotent(self):
        self.assertEqual(finding_id("容量保持率 87%"), finding_id("容量保持率87%"))

    def test_provenance_empty_quote_rejected(self):
        with self.assertRaises(ValueError):
            Provenance(ref_id=1, paper_title="t", quote="  ", round=1)

    def test_observation_over_30_words_rejected(self):
        long_text = " ".join(["word"] * 31)
        with self.assertRaises(ValueError):
            Observation(text=long_text, prov=_prov())

    def test_observation_without_provenance_rejected(self):
        with self.assertRaises(ValueError):
            Observation(text="合法观察", prov=None)

    def test_observation_illegal_status_rejected(self):
        with self.assertRaises(ValueError):
            Observation(text="合法观察", status="confirmed_by_llm", prov=_prov())

    def test_observation_confirmed_status_is_legal_enum(self):
        # confirmed 是合法枚举, 但只允许 Stage B 导入路径设置(schema 层不区分来源)
        obs = Observation(text="合法观察", status="confirmed", prov=_prov())
        self.assertEqual(obs.status, "confirmed")

    def test_node_append_observation_dup_and_full(self):
        node = EdgeNode(id=node_id("MATERIAL", "电解液"), ntype="MATERIAL", name="电解液")
        self.assertEqual(node.append_observation(Observation(text="粘度较低", prov=_prov())), "appended")
        self.assertEqual(node.append_observation(Observation(text="粘度 较低", prov=_prov())), "dup")
        self.assertEqual(node.append_observation(Observation(text="闪点高", prov=_prov())), "appended")
        self.assertEqual(node.append_observation(Observation(text="成本低", prov=_prov())), "appended")
        self.assertEqual(node.append_observation(Observation(text="第五条观察", prov=_prov())), "full")

    def test_node_roundtrip(self):
        node = EdgeNode(id=node_id("METHOD", "A法"), ntype="METHOD", name="A法",
                        observations=[Observation(text="效率90%", prov=_prov())], created_round=2)
        clone = EdgeNode.from_dict(node.to_dict())
        self.assertEqual(clone.id, node.id)
        self.assertEqual(clone.observations[0].prov.quote, "原文逐字片段用于测试")

    def test_edge_roundtrip(self):
        e = EdgeRel(eid="E1", src="A", dst="B", etype="SUPPORTS", prov=_prov(),
                    obs="obs", conflict_group="cg_x", last_seen_round=3)
        clone = EdgeRel.from_dict(e.to_dict())
        self.assertEqual((clone.eid, clone.etype, clone.conflict_group), ("E1", "SUPPORTS", "cg_x"))


# =====================================================================
# store
# =====================================================================

class TestStore(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = self._tmp.name
        self.store = EvidenceGraphStore("sess_ut", base_dir=self.base)

    def tearDown(self):
        self._tmp.cleanup()

    def _seed(self):
        n1 = EdgeNode(id=node_id("MATERIAL", "电解液"), ntype="MATERIAL", name="电解液")
        n1.observations.append(Observation(text="粘度较低", prov=_prov()))
        n2 = EdgeNode(id=node_id("PROPERTY", "离子电导率"), ntype="PROPERTY", name="离子电导率")
        n2.observations.append(Observation(text="离子电导率提升到10 mS/cm", prov=_prov()))
        self.store.upsert_node(n1)
        self.store.upsert_node(n2)
        self.store.upsert_edge(EdgeRel(
            eid=edge_id(n1.id, n2.id, "ASSOCIATED_WITH", "p1"),
            src=n1.id, dst=n2.id, etype="ASSOCIATED_WITH", prov=_prov(), obs="电导率10mS/cm"))

    def test_missing_file_loads_empty(self):
        self.assertEqual(len(self.store.nodes), 0)

    def test_save_load_roundtrip(self):
        self._seed()
        self.store.save()
        other = EvidenceGraphStore("sess_ut", base_dir=self.base)
        self.assertEqual(len(other.nodes), 2)
        self.assertEqual(len(other.edges), 1)
        self.assertEqual(other.find_node("电解液"), node_id("MATERIAL", "电解液"))

    def test_corrupt_file_loads_empty(self):
        self._seed()
        self.store.save()
        with open(self.store.path, "w", encoding="utf-8") as f:
            f.write("{broken json")
        other = EvidenceGraphStore("sess_ut", base_dir=self.base)
        self.assertEqual(len(other.nodes), 0)

    def test_retrieve_hit_with_line_cap(self):
        self._seed()
        text = self.store.retrieve_from_graph(["电解液"], max_lines=10)
        self.assertIn("MATERIAL|电解液", text)
        self.assertIn("候选", text) if False else None   # candidate 状态在括号里
        self.assertIn("candidate", text)
        short = self.store.retrieve_from_graph(["电解液"], max_lines=1)
        self.assertEqual(len(short.splitlines()), 1)

    def test_retrieve_empty_graph_placeholder(self):
        self.assertTrue(self.store.retrieve_from_graph(["任意"]).startswith("("))

    def test_retrieve_one_hop_neighbors(self):
        self._seed()
        text = self.store.retrieve_from_graph(["电解液"], max_lines=10)
        self.assertIn("PROPERTY|离子电导率", text)   # 1 跳邻域可达

    def test_conflict_detection_needs_direction_and_delta(self):
        self._seed()
        n2_id = node_id("PROPERTY", "离子电导率")
        cg = self.store.detect_conflict_group(n2_id, "离子电导率下降至2 mS/cm")
        self.assertTrue(cg.startswith("cg_"))
        # 数值相近 → 不冲突
        self.assertEqual(self.store.detect_conflict_group(n2_id, "离子电导率提升至10.5 mS/cm"), "")
        # 无方向词 → 不判冲突
        self.assertEqual(self.store.detect_conflict_group(n2_id, "离子电导率约5 mS/cm"), "")

    def test_import_confirmed_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            self.store.import_confirmed("stage_b.csv")

    def test_snapshot_shape(self):
        self._seed()
        snap = self.store.snapshot()
        self.assertEqual(snap["stats"]["nodes"], 2)
        self.assertEqual(snap["meta"]["schema"], "flowbd-eg-2")

    def test_rebind_renames_removes_old_and_keeps_data(self):
        self._seed()
        self.store.save()
        old_path = self.store.path
        self.store.rebind("sess_new")
        self.assertFalse(os.path.exists(old_path))            # 旧文件已删
        self.assertTrue(os.path.exists(self.store.path))      # 新文件落盘
        self.assertEqual(self.store.meta["session_id"], "sess_new")
        self.assertEqual(len(self.store.nodes), 2)            # 数据保留
        self.assertEqual(len(self.store.edges), 1)

    def test_rebind_roundtrip_with_new_session(self):
        self._seed()
        self.store.save()
        self.store.rebind("sess_new2")
        other = EvidenceGraphStore("sess_new2", base_dir=self.base)
        self.assertEqual(len(other.nodes), 2)
        self.assertEqual(len(other.edges), 1)

    def test_fresh_skips_stale_pending_file(self):
        # 模拟上个未完成会话残留: 磁盘上已有一份带节点的 pending_iterative.json
        stale = EvidenceGraphStore("pending_iterative", base_dir=self.base)
        stale_node = EdgeNode(id=node_id("METHOD", "旧会话方法"), ntype="METHOD", name="旧会话方法")
        stale_node.observations.append(Observation(text="旧会话的证据观察", prov=_prov()))
        stale.upsert_node(stale_node)
        stale.save()
        # 新会话以 fresh 挂载同名临时 id → 残留不得混入
        fresh = EvidenceGraphStore("pending_iterative", base_dir=self.base, fresh=True)
        self.assertEqual(len(fresh.nodes), 0)
        self.assertEqual(len(fresh.edges), 0)

    def test_entity_name_length_limit(self):
        """R8 实体命名闸门: 非 PAPER/FINDING 超 40 字符拒收; PAPER 题名豁免。"""
        with self.assertRaises(ValueError):
            EdgeNode(id=node_id("METHOD", "超长实体名称" * 8), ntype="METHOD",
                     name="超长实体名称" * 8)
        paper = EdgeNode(id=node_id("PAPER", "A" * 80), ntype="PAPER", name="A" * 80)
        self.assertEqual(self.store.upsert_node(paper), "created")


# =====================================================================
# merge
# =====================================================================

class TestMerge(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.store = EvidenceGraphStore("sess_merge", base_dir=self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_new_nodes_and_edges_counted(self):
        ex = ExtractionResult(
            entities=[_entity("A法"), _entity("B材料", "MATERIAL")],
            relations=[_relation("A法", "B材料")])
        report = merge_round(self.store, ex, 1)
        self.assertEqual((report.new_nodes, report.new_edges), (2, 1))
        self.assertEqual(len(self.store.nodes), 2)

    def test_duplicate_entity_updates_not_creates(self):
        merge_round(self.store, ExtractionResult(entities=[_entity("A法")]), 1)
        report = merge_round(self.store, ExtractionResult(entities=[_entity("A法")]), 2)
        self.assertEqual(report.new_nodes, 0)
        self.assertEqual(report.updated_nodes, 1)
        self.assertEqual(len(self.store.nodes), 1)
        node = self.store.nodes[node_id("METHOD", "A法")]
        self.assertEqual(len(node.observations), 1)   # 同观察 → dup, 不重复 append
        self.assertEqual(report.dup_skipped, 1)

    def test_merge_caps_enforced(self):
        ents = [_entity(f"实体{i}") for i in range(MERGE_CAPS["new_nodes"] + 3)]
        report = merge_round(self.store, ExtractionResult(entities=ents), 1)
        self.assertEqual(report.new_nodes, MERGE_CAPS["new_nodes"])
        self.assertGreaterEqual(len(report.dropped), 3)

    def test_entity_without_provenance_rejected(self):
        bad = {"name": "X法", "type": "METHOD", "observations": ["某观察"]}
        report = merge_round(self.store, ExtractionResult(entities=[bad]), 1)
        self.assertEqual(report.new_nodes, 0)
        self.assertTrue(any("provenance" in d for d in report.dropped))

    def test_merge_drops_overlong_entity_name(self):
        """R8: 超长实体名在 merge 层被拒收并记入 dropped。"""
        report = merge_round(self.store, ExtractionResult(entities=[_entity("超长实体名称" * 8)]), 1)
        self.assertEqual(report.new_nodes, 0)
        self.assertTrue(any("超" in d for d in report.dropped))

    def test_relation_endpoints_must_exist(self):
        ex = ExtractionResult(relations=[_relation("未入图A", "未入图B")])
        report = merge_round(self.store, ex, 1)
        self.assertEqual(report.new_edges, 0)
        self.assertTrue(any("未入图" in d for d in report.dropped))

    def test_duplicate_edge_refreshes_round_only(self):
        merge_round(self.store, ExtractionResult(
            entities=[_entity("A法"), _entity("B材料", "MATERIAL")],
            relations=[_relation("A法", "B材料")]), 1)
        eid = list(self.store.edges)[0]
        merge_round(self.store, ExtractionResult(relations=[
            _relation("A法", "B材料", quote="原文逐字片段用于测试")]), 2)
        self.assertEqual(len(self.store.edges), 1)
        self.assertEqual(self.store.edges[eid].last_seen_round, 2)

    def test_conflict_keeps_both_sides_grouped(self):
        merge_round(self.store, ExtractionResult(
            entities=[_entity("容量保持率", "PROPERTY", obs=("保持率90%",)),
                      _entity("A法"), _entity("B法")]), 1)
        r1 = merge_round(self.store, ExtractionResult(relations=[
            _relation("A法", "容量保持率", obs="保持率提升至90%", quote="25℃条件下保持率提升至90%")]), 2)
        self.assertEqual(len(r1.conflicts), 0)
        r2 = merge_round(self.store, ExtractionResult(relations=[
            _relation("A法", "容量保持率", obs="保持率下降至40%", quote="25℃条件下保持率下降至40%")]), 3)
        self.assertEqual(len(r2.conflicts), 1)
        self.assertEqual(len(self.store.edges), 2)      # 双边保留
        groups = {e.conflict_group for e in self.store.edges.values() if e.conflict_group}
        self.assertEqual(len(groups), 1)                # 同组

    def test_empty_extraction_returns_zero_report(self):
        report = merge_round(self.store, ExtractionResult(), 1)
        self.assertEqual((report.new_nodes, report.new_edges, report.updated_nodes,
                          report.dup_skipped, report.dropped, report.conflicts),
                         (0, 0, 0, 0, [], []))
        self.assertEqual(merge_round(self.store, None, 1).new_nodes, 0)


# =====================================================================
# extractor(mock LLM, 零网络)
# =====================================================================

_VALID_JSON = json.dumps({
    "entities": [
        {"name": "A法", "type": "METHOD", "observations": ["循环1000圈容量保持率87%"]},
        {"name": "X电极", "type": "MATERIAL", "observations": ["循环后出现裂纹"]},
    ],
    "relations": [
        {"src": "A法", "dst": "X电极", "type": "SUPPORTS",
         "evidence_quote": "原文逐字片段用于测试, 容量保持率87%", "obs": "容量保持率87%"},
    ],
}, ensure_ascii=False)


class _MockLLM:

    def __init__(self, reply=None, raise_exc=None):
        self.reply = reply if reply is not None else _VALID_JSON
        self.raise_exc = raise_exc
        self.calls = []

    def call_llm(self, prompt=None, **kwargs):
        self.calls.append(prompt)
        if self.raise_exc:
            raise self.raise_exc
        return self.reply


_DOC_SOURCES = [{"ref_id": 3, "type": "vector", "source": "paper_a.pdf",
                 "source_label": "Paper A",
                 "content": "本文提出A法。循环1000圈容量保持率87%。原文逐字片段用于测试, 容量保持率87%。循环后出现裂纹。",
                 "score": 0.9}]


class TestExtractor(unittest.TestCase):

    def test_valid_json_and_quote_binding(self):
        ex = EvidenceExtractor(_MockLLM())
        result = ex.extract("问题", "上下文", "回答", _DOC_SOURCES, 1)
        self.assertEqual(len(result.entities), 2)
        self.assertEqual(len(result.relations), 1)
        self.assertEqual(result.relations[0]["_prov"].ref_id, 3)
        self.assertEqual(result.relations[0]["_prov"].paper_title, "Paper A")

    def test_untraceable_quote_drops_relation(self):
        ex = EvidenceExtractor(_MockLLM())
        result = ex.extract("问题", "上下文", "回答",
                            [{"ref_id": 1, "content": "完全无关的内容", "source_label": "P"}], 1)
        self.assertEqual(result.relations, [])
        self.assertTrue(any("逐字定位" in e for e in ex.last_errors))

    def test_over_30_word_observation_dropped(self):
        bad = json.dumps({"entities": [
            {"name": "A法", "type": "METHOD",
             "observations": [" ".join(["word"] * 31), "短观察"]}]}, ensure_ascii=False)
        ex = EvidenceExtractor(_MockLLM(reply=bad))
        # context 与观察完全无关 → "短观察" snap 不到原文 → 实体整体被丢
        result = ex.extract("问题", "这里没有任何相关语句", "回答", _DOC_SOURCES, 1)
        self.assertEqual(len(result.entities), 0)   # 唯一合法观察 snap 失败 → 实体被丢

    def test_non_json_output_returns_empty(self):
        ex = EvidenceExtractor(_MockLLM(reply="我不是 JSON"))
        result = ex.extract("q", "c", "a", _DOC_SOURCES, 1)
        self.assertFalse(result)
        self.assertTrue(ex.last_errors)

    def test_json_fence_parsed(self):
        fenced = "```json\n" + _VALID_JSON + "\n```"
        ex = EvidenceExtractor(_MockLLM(reply=fenced))
        result = ex.extract("问题", "上下文", "回答", _DOC_SOURCES, 1)
        self.assertEqual(len(result.entities), 2)

    def test_llm_exception_bounded(self):
        ex = EvidenceExtractor(_MockLLM(raise_exc=RuntimeError("网络断")))
        result = ex.extract("q", "c", "a", _DOC_SOURCES, 1)
        self.assertFalse(result)
        self.assertTrue(any("兜底" in e for e in ex.last_errors))

    def test_extractor_drops_overlong_name(self):
        """R8: 抽取层提前过滤超长实体名(不占 10 实体名额)。"""
        bad = json.dumps({"entities": [
            {"name": "这是一个远超四十个字符限制的整句问题充当实体名的典型例子对吧" * 2, "type": "METHOD",
             "observations": ["合法观察"]}]}, ensure_ascii=False)
        ex = EvidenceExtractor(_MockLLM(reply=bad))
        result = ex.extract("问题", "合法观察出自原文", "回答", _DOC_SOURCES, 1)
        self.assertEqual(result.entities, [])
        self.assertTrue(any("超" in e for e in ex.last_errors))


# =====================================================================
# coordinator(mock pipeline + mock LLM, 零网络)
# =====================================================================

class _MockParsingAgent:
    def parse(self, state):
        state.parsed_question = state.original_question
        state.extracted_entities = ["A法"]


class _MockRetrievalAgent:
    def __init__(self):
        self.calls = []

    def retrieve(self, state):
        self.calls.append(state.parsed_question)
        state.vector_chunks = list(state.vector_chunks) + [{"content": "检索块内容"}]
        state.doc_sources = list(state.doc_sources or []) + [
            {"ref_id": 1, "content": "检索原文:循环1000圈容量保持率87%。原文逐字片段用于测试。",
             "source_label": "P", "type": "vector"}]


class _MockFusionAgent:
    def fuse(self, state):
        state.fused_context = (state.fused_context or "") + "融合上下文"


class _MockAnswerAgent:
    def generate(self, state):
        state.final_answer = "最终答案"


class _MockPipeline:

    def __init__(self):
        self.parsing_agent = _MockParsingAgent()
        self.retrieval_agent = _MockRetrievalAgent()
        self.fusion_agent = _MockFusionAgent()
        self.answer_agent = _MockAnswerAgent()


_PLAN_JSON = json.dumps({"plan": [{"step": "找证据", "done": False}]}, ensure_ascii=False)
_STOP_JSON = json.dumps({
    "updated_plan": [{"step": "找证据", "done": True}],
    "next_action": "TERMINATE", "sufficiency_reason": "证据已足"}, ensure_ascii=False)


class _RouteLLM:
    """按 prompt 特征路由: 初始计划 / 判停(含 next_action) / 其余(抽取)。

    extractor 与协调器共用同一个 llm, mock 必须按 prompt 三分, 否则
    抽取调用会吃掉判停的返回值。
    """

    def call_llm(self, prompt=None, **kwargs):
        p = str(prompt or "")
        if "信息需求清单" in p:
            return self._plan_reply()
        if "next_action" in p:
            return self._decide_reply()
        return self._extract_reply()

    def _plan_reply(self):
        return _PLAN_JSON

    def _decide_reply(self):
        return _STOP_JSON

    def _extract_reply(self):
        return _VALID_JSON


class _PlanThenStopLLM(_RouteLLM):
    """初始计划返回计划 JSON; 判停返回 TERMINATE; 抽取返回合法 JSON。"""


class _BudgetLLM(_RouteLLM):
    """判停永远要求 BFRS — 用于验证预算耗尽强制终止。"""

    def _decide_reply(self):
        return json.dumps({"updated_plan": [{"step": "s", "done": False}],
                           "next_action": "BFRS", "sufficiency_reason": "还不够",
                           "action_args": {"query": "第二轮不同查询"}}, ensure_ascii=False)


class _IllegalLLM(_RouteLLM):
    def _decide_reply(self):
        return "不是 JSON"


def _make_store(tmp):
    return EvidenceGraphStore("sess_coord", base_dir=str(tmp.name))


def _drain(gen):
    states = list(gen)
    return states[-1]


class TestCoordinator(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.store = _make_store(self._tmp)
        self.pipeline = _MockPipeline()

    def tearDown(self):
        self._tmp.cleanup()

    def test_full_loop_produces_answer_and_snapshot(self):
        coord = IterativeCoordinator(self.pipeline, _PlanThenStopLLM(), self.store, max_rounds=3)
        final = _drain(coord.run("测试问题"))
        self.assertTrue(final.stage_4_complete)
        self.assertEqual(final.final_answer, "最终答案")
        self.assertIsNotNone(final.evidence_graph_snapshot)
        self.assertEqual(final.evidence_graph_snapshot["meta"]["schema"], "flowbd-eg-2")
        self.assertEqual(coord.last_state.stop_reason, "证据已足")
        # 写回确实进了图
        self.assertGreater(len(self.store.nodes), 0)

    def test_budget_exhausted_forces_stop(self):
        llm = _BudgetLLM()
        coord = IterativeCoordinator(self.pipeline, llm, self.store, max_rounds=2)
        final = _drain(coord.run("测试问题"))
        self.assertIn("预算耗尽", coord.last_state.stop_reason)
        self.assertEqual(len(self.pipeline.retrieval_agent.calls), 2)   # BFRS 轮1 + DFRS 轮2, 不超预算

    def test_illegal_action_forces_stop(self):
        coord = IterativeCoordinator(self.pipeline, _IllegalLLM(), self.store, max_rounds=3)
        _drain(coord.run("测试问题"))
        self.assertIn("非法", coord.last_state.stop_reason)

    def test_write_graph_action_stops_with_accurate_reason(self):
        """WRITE_GRAPH 是合法动作, 但检索结果已入库(图为空=无新增) → 终止措辞不含'非法'。

        注: _decide 内部在图非空时会把 WRITE_GRAPH 近似转换为 TERMINATE;
        本用例构造抽取为空(图保持为空)的边缘情形, 使主循环 WRITE_GRAPH 分支可达。
        """
        class _WriteGraphLLM(_RouteLLM):
            def _decide_reply(self):
                return json.dumps({"updated_plan": [{"step": "s", "done": False}],
                                   "next_action": "WRITE_GRAPH",
                                   "action_args": {}, "sufficiency_reason": "先入库"},
                                  ensure_ascii=False)

            def _extract_reply(self):
                return "不是 JSON"   # 抽取产空 → 图保持为空 → _pending_unwritten 为真

        coord = IterativeCoordinator(self.pipeline, _WriteGraphLLM(), self.store, max_rounds=3)
        _drain(coord.run("测试问题"))
        self.assertIn("写回", coord.last_state.stop_reason)
        self.assertNotIn("非法", coord.last_state.stop_reason)

    def test_dfrs_uses_directed_query(self):
        llm_reply = json.dumps({"updated_plan": [{"step": "s", "done": False}],
                                "next_action": "DFRS",
                                "action_args": {"query": "定向检索词"},
                                "sufficiency_reason": "需要深查"}, ensure_ascii=False)

        class _OneDFRS(_RouteLLM):
            def __init__(self):
                self.n = 0

            def _decide_reply(self):
                self.n += 1
                return llm_reply if self.n == 1 else _STOP_JSON

        coord = IterativeCoordinator(self.pipeline, _OneDFRS(), self.store, max_rounds=3)
        _drain(coord.run("测试问题"))
        self.assertIn("定向检索词", self.pipeline.retrieval_agent.calls)

    def test_retrieval_failure_still_answers(self):
        class _BrokenRetrieval(_MockRetrievalAgent):
            def retrieve(self, state):
                raise RuntimeError("Milvus 不可用")

        self.pipeline.retrieval_agent = _BrokenRetrieval()
        coord = IterativeCoordinator(self.pipeline, _PlanThenStopLLM(), self.store, max_rounds=2)
        final = _drain(coord.run("测试问题"))
        self.assertTrue(final.stage_4_complete)
        self.assertEqual(final.final_answer, "最终答案")

    def test_graph_summary_survives_fusion_overwrite(self):
        """B1 回归: fusion_agent 覆盖 fused_context 后, 图摘要仍须在其中(供答案引用)。"""
        class _OverwritingFusion:
            def fuse(self, state):
                state.fused_context = "融合重新生成的上下文(覆盖一切)"   # 真实融合代理行为

        self.pipeline.fusion_agent = _OverwritingFusion()
        coord = IterativeCoordinator(self.pipeline, _PlanThenStopLLM(), self.store, max_rounds=3)
        final = _drain(coord.run("测试问题"))
        self.assertIn("融合重新生成的上下文", final.fused_context)
        self.assertIn("证据图摘要", final.fused_context)
        self.assertIn("容量保持率", final.fused_context)   # 图内观察句进入摘要

    def test_default_mode_keeps_full_context(self):
        """模式关(现状): 融合文本与图摘要并存于 fused_context。"""
        coord = IterativeCoordinator(self.pipeline, _PlanThenStopLLM(), self.store, max_rounds=3)
        final = _drain(coord.run("测试问题"))
        self.assertIn("融合上下文", final.fused_context)
        self.assertIn("证据图摘要", final.fused_context)

    def test_summarized_answer_falls_back_when_requirement_sources_are_missing(self):
        """请求摘要但计划未绑定来源时保留完整证据，不虚报摘要收益。"""
        coord = IterativeCoordinator(self.pipeline, _PlanThenStopLLM(), self.store,
                                     max_rounds=3, summarized_answer=True)
        final = _drain(coord.run("测试问题"))
        self.assertIn("相关证据图记忆", final.fused_context)
        self.assertIn("容量保持率", final.fused_context)     # 图内观察句进入上下文
        self.assertIn("融合上下文", final.fused_context)
        self.assertTrue(final.answer_quality['graph_context']['fallback_to_full_context'])
        self.assertEqual(final.answer_quality['graph_context']['mode'],'full_context')
        self.assertGreater(len(final.doc_sources or []), 0)  # R9: 引用锚点保留

    def test_write_graph_prompt_contains_type_legend(self):
        """借鉴②: 判停 prompt 必须含摘要行格式图例(防误删)。"""
        from evidence_graph import coordinator as _coord
        self.assertIn("摘要行格式", _coord.PLAN_PROMPT)
        self.assertIn("MECHANISM", _coord.PLAN_PROMPT)

    def test_write_back_failure_does_not_break_loop(self):
        class _BrokenExtractor:
            last_errors = []

            def extract(self, *a, **k):
                raise RuntimeError("抽取崩了")

        coord = IterativeCoordinator(self.pipeline, _PlanThenStopLLM(), self.store,
                                     max_rounds=2, extractor=_BrokenExtractor())
        final = _drain(coord.run("测试问题"))
        self.assertTrue(final.stage_4_complete)


if __name__ == "__main__":
    unittest.main(verbosity=2)
