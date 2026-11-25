"""Stage B 单测: pair_generator + year_utils + edge_validation (纯本地, 无 LLM)."""
from __future__ import annotations

import os
import sys
import unittest

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
V2_DIR = os.path.dirname(THIS_DIR)
SRC_GRAPH_RAG_DIR = os.path.dirname(V2_DIR)
if SRC_GRAPH_RAG_DIR not in sys.path:
    sys.path.insert(0, SRC_GRAPH_RAG_DIR)

from method_evolution_v2.stage_b import pair_generator as pg      # noqa: E402
from method_evolution_v2.stage_b import year_utils as yu          # noqa: E402
from method_evolution_v2.stage_b import edge_validation as ev     # noqa: E402


def _sid(sec, p, s):
    return f"{sec}_p{p}_s{s}"


def _mk_sent(sid, text, cs, ce):
    parsed = pg.parse_sentence_id(sid)
    return {
        "sentence_id": sid,
        "paper_id": "p",
        "section_type": parsed[0],
        "section_name": parsed[0],
        "para_id": f"{parsed[0]}_p{parsed[1]}",
        "sentence_text": text,
        "char_start": cs,
        "char_end": ce,
    }


class TestSidParse(unittest.TestCase):
    def test_parse_simple(self):
        self.assertEqual(pg.parse_sentence_id("methods_p3_s2"), ("methods", 3, 2))

    def test_parse_multi_underscore_section_type(self):
        self.assertEqual(pg.parse_sentence_id("results_discussion_p15_s4"),
                         ("results_discussion", 15, 4))
        self.assertEqual(pg.parse_sentence_id("other_sections_p9_s1"),
                         ("other_sections", 9, 1))

    def test_parse_invalid(self):
        self.assertIsNone(pg.parse_sentence_id(""))
        self.assertIsNone(pg.parse_sentence_id("not_a_sid"))
        self.assertIsNone(pg.parse_sentence_id("methods_p3"))


class TestTriggerScan(unittest.TestCase):
    def test_scan_triggers(self):
        idx = {
            _sid("methods", 1, 1): _mk_sent(_sid("methods", 1, 1),
                                            "本文提出了溶胶-凝胶法.", 0, 10),
            _sid("methods", 1, 2): _mk_sent(_sid("methods", 1, 2),
                                            "相比之下, 传统方法效率较低.", 10, 20),
            _sid("methods", 1, 3): _mk_sent(_sid("methods", 1, 3),
                                            "该方法在此基础上引入新材料.", 20, 30),
            _sid("methods", 1, 4): _mk_sent(_sid("methods", 1, 4),
                                            "结果表明性能良好.", 30, 40),
        }
        trigs = pg.scan_trigger_sentences(idx)
        # 相比 / 传统方法 / 在此基础上 触发
        self.assertIn(_sid("methods", 1, 2), trigs)
        self.assertIn(_sid("methods", 1, 3), trigs)
        self.assertNotIn(_sid("methods", 1, 4), trigs)


class TestCandidatePairs(unittest.TestCase):
    def test_same_paragraph_pair(self):
        methods = [
            {"method_id": "m1", "kind": "own", "name": "A",
             "validation_status": "accepted",
             "evidence_sentence_ids": ["methods_p3_s1"]},
            {"method_id": "m2", "kind": "referenced", "name": "B",
             "validation_status": "accepted",
             "evidence_sentence_ids": ["methods_p3_s2"]},
        ]
        idx = {
            "methods_p3_s1": _mk_sent("methods_p3_s1", "本文提出方法 A.", 0, 10),
            "methods_p3_s2": _mk_sent("methods_p3_s2", "相比 B, A 更优.", 10, 20),
        }
        pairs, stats = pg.generate_candidate_pairs("p", methods, idx)
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0]["pair_source"], "same_paragraph")
        self.assertEqual(stats["theoretical_pairs"], 1)
        self.assertEqual(stats["filtered_pairs"], 1)

    def test_far_apart_dropped_without_trigger(self):
        methods = [
            {"method_id": "m1", "kind": "own", "name": "A",
             "validation_status": "accepted",
             "evidence_sentence_ids": ["methods_p3_s1"]},
            {"method_id": "m2", "kind": "referenced", "name": "B",
             "validation_status": "accepted",
             "evidence_sentence_ids": ["conclusion_p50_s1"]},
        ]
        idx = {
            "methods_p3_s1": _mk_sent("methods_p3_s1", "本文提出方法 A.", 0, 10),
            "conclusion_p50_s1": _mk_sent("conclusion_p50_s1",
                                          "该方法效果显著。", 500, 510),
        }
        pairs, stats = pg.generate_candidate_pairs("p", methods, idx)
        self.assertEqual(len(pairs), 0)   # 无 trigger, 相隔太远 -> 丢弃

    def test_far_apart_kept_with_trigger(self):
        methods = [
            {"method_id": "m1", "kind": "own", "name": "A",
             "validation_status": "accepted",
             "evidence_sentence_ids": ["methods_p3_s1"]},
            {"method_id": "m2", "kind": "referenced", "name": "B",
             "validation_status": "accepted",
             "evidence_sentence_ids": ["methods_p5_s1"]},
        ]
        idx = {
            "methods_p3_s1": _mk_sent("methods_p3_s1", "方法 A 描述。", 0, 8),
            "methods_p4_s1": _mk_sent("methods_p4_s1",
                                       "本文在 A 的基础上引入 B。", 8, 20),
            "methods_p5_s1": _mk_sent("methods_p5_s1", "方法 B 描述。", 20, 28),
        }
        pairs, stats = pg.generate_candidate_pairs("p", methods, idx)
        self.assertEqual(len(pairs), 1)
        self.assertTrue(pairs[0]["pair_source"].startswith("trigger"))


class TestYearUtils(unittest.TestCase):
    def test_extract_year_from_clue(self):
        self.assertEqual(yu.extract_year_from_citation_clue("Smith 2018"), 2018)
        self.assertEqual(yu.extract_year_from_citation_clue("[15]"), None)
        self.assertEqual(yu.extract_year_from_citation_clue("CHEN 团队[29] 2020"),
                         2020)
        self.assertEqual(yu.extract_year_from_citation_clue(""), None)

    def test_temporal_status(self):
        self.assertEqual(yu.temporal_status_for_pair(2022, 2018), "ok")
        self.assertEqual(yu.temporal_status_for_pair(2018, 2022), "conflict")
        self.assertEqual(yu.temporal_status_for_pair(None, 2020), "unknown")
        self.assertEqual(yu.temporal_status_for_pair(2020, None), "unknown")


class TestEdgeValidation(unittest.TestCase):
    def _fixture(self, override_audit=None, override_rel=None):
        idx = {
            "methods_p3_s1": _mk_sent("methods_p3_s1",
                                       "本文在 A 基础上引入 B, 优化性能.", 0, 20),
        }
        methods = {
            "m_a": {"paper_id": "p", "method_id": "m_a", "name": "A",
                    "kind": "referenced", "validation_status": "accepted",
                    "citation_clue": "Smith 2018",
                    "evidence_sentence_ids": ["methods_p3_s1"]},
            "m_b": {"paper_id": "p", "method_id": "m_b", "name": "B",
                    "kind": "own", "validation_status": "accepted",
                    "citation_clue": "",
                    "evidence_sentence_ids": ["methods_p3_s1"]},
        }
        rel = {
            "pair_id": "P001",
            "from_method_id": "m_b",   # 后者
            "to_method_id": "m_a",     # 前者
            "relation": "EXTENDS",
            "relation_evidence_sentence_ids": ["methods_p3_s1"],
            "direction_basis": "B 在 A 基础上",
            "relation_reason": "扩展",
            "confidence_llm": "high",
        }
        if override_rel:
            rel.update(override_rel)
        audit = {
            "support": "supported", "direction": "correct",
            "relation_check": "correct", "suggested_relation": "",
            "audit_reason": "证据句直接支持",
        }
        if override_audit:
            audit.update(override_audit)
        return methods, idx, rel, {"P001": audit}

    def test_accepted_happy_path(self):
        methods, idx, rel, audit_by_pair = self._fixture()
        r = ev.validate_and_classify_edge(rel, methods, idx, audit_by_pair)
        self.assertEqual(r["validation_status"], "accepted")
        self.assertEqual(r["rejected_reason"], "")
        # 证据 quote 由代码从索引拼出
        self.assertEqual(r["evidence_quote"],
                         "本文在 A 基础上引入 B, 优化性能.")

    def test_rejected_invalid_relation_type(self):
        methods, idx, rel, audit_by_pair = self._fixture(
            override_rel={"relation": "INHERITS"})
        r = ev.validate_and_classify_edge(rel, methods, idx, audit_by_pair)
        self.assertEqual(r["validation_status"], "rejected")
        self.assertIn("invalid_relation_type", r["rejected_reason"])

    def test_rejected_endpoint_missing(self):
        methods, idx, rel, audit_by_pair = self._fixture(
            override_rel={"from_method_id": "nonexistent"})
        r = ev.validate_and_classify_edge(rel, methods, idx, audit_by_pair)
        self.assertEqual(r["validation_status"], "rejected")
        self.assertIn("endpoint_method_not_found", r["rejected_reason"])

    def test_rejected_self_loop(self):
        methods, idx, rel, audit_by_pair = self._fixture(
            override_rel={"from_method_id": "m_a", "to_method_id": "m_a"})
        r = ev.validate_and_classify_edge(rel, methods, idx, audit_by_pair)
        self.assertEqual(r["validation_status"], "rejected")
        self.assertIn("same_method_endpoints", r["rejected_reason"])

    def test_candidate_when_endpoint_is_candidate(self):
        methods, idx, rel, audit_by_pair = self._fixture()
        methods["m_a"]["validation_status"] = "candidate"
        r = ev.validate_and_classify_edge(rel, methods, idx, audit_by_pair)
        self.assertEqual(r["validation_status"], "candidate")
        self.assertIn("endpoint_is_candidate", r["rejected_reason"])

    def test_candidate_when_audit_weak(self):
        methods, idx, rel, audit_by_pair = self._fixture(
            override_audit={"support": "weak"})
        r = ev.validate_and_classify_edge(rel, methods, idx, audit_by_pair)
        self.assertEqual(r["validation_status"], "candidate")

    def test_candidate_when_audit_direction_reversed(self):
        methods, idx, rel, audit_by_pair = self._fixture(
            override_audit={"direction": "reversed"})
        r = ev.validate_and_classify_edge(rel, methods, idx, audit_by_pair)
        self.assertEqual(r["validation_status"], "candidate")
        self.assertIn("audit_direction_reversed", r["rejected_reason"])

    def test_rejected_when_audit_missing(self):
        methods, idx, rel, _ = self._fixture()
        r = ev.validate_and_classify_edge(rel, methods, idx, {})
        self.assertEqual(r["validation_status"], "rejected")
        self.assertIn("audit_missing", r["rejected_reason"])

    def test_rejected_when_all_evidence_ids_missing(self):
        methods, idx, rel, audit_by_pair = self._fixture(
            override_rel={"relation_evidence_sentence_ids": ["fake_p9_s1"]})
        r = ev.validate_and_classify_edge(rel, methods, idx, audit_by_pair)
        self.assertEqual(r["validation_status"], "rejected")
        self.assertIn("all_evidence_ids_missing", r["rejected_reason"])

    def test_candidate_when_temporal_conflict(self):
        # from_year=2015, to_year=2020 → conflict
        methods, idx, rel, audit_by_pair = self._fixture()
        methods["m_b"]["citation_clue"] = "王 2015"
        methods["m_a"]["citation_clue"] = "Smith 2020"
        r = ev.validate_and_classify_edge(rel, methods, idx, audit_by_pair)
        self.assertEqual(r["temporal_status"], "conflict")
        self.assertEqual(r["validation_status"], "candidate")
        self.assertIn("temporal_conflict", r["rejected_reason"])

    def test_unknown_year_not_rejected(self):
        methods, idx, rel, audit_by_pair = self._fixture()
        # 两端都没年份
        methods["m_a"]["citation_clue"] = ""
        methods["m_b"]["citation_clue"] = ""
        r = ev.validate_and_classify_edge(rel, methods, idx, audit_by_pair)
        self.assertEqual(r["temporal_status"], "unknown")
        self.assertEqual(r["validation_status"], "accepted")

    def test_multi_span_evidence(self):
        # 两个 sid, 不在同一 paragraph → 两 span
        idx = {
            "methods_p3_s1": _mk_sent("methods_p3_s1",
                                       "本文改进了方法 A.", 0, 10),
            "results_discussion_p20_s2": _mk_sent(
                "results_discussion_p20_s2",
                "相比 A, 本方法效率提升 30%.", 500, 520),
        }
        methods = {
            "m_a": {"paper_id": "p", "method_id": "m_a", "name": "A",
                    "kind": "referenced", "validation_status": "accepted",
                    "citation_clue": "", "evidence_sentence_ids": []},
            "m_b": {"paper_id": "p", "method_id": "m_b", "name": "B",
                    "kind": "own", "validation_status": "accepted",
                    "citation_clue": "", "evidence_sentence_ids": []},
        }
        rel = {
            "pair_id": "P001",
            "from_method_id": "m_b", "to_method_id": "m_a",
            "relation": "IMPROVES",
            "relation_evidence_sentence_ids": ["methods_p3_s1",
                                                "results_discussion_p20_s2"],
        }
        audit = {
            "P001": {"support": "supported", "direction": "correct",
                     "relation_check": "correct", "suggested_relation": "",
                     "audit_reason": ""}
        }
        r = ev.validate_and_classify_edge(rel, methods, idx, audit)
        self.assertEqual(r["validation_status"], "accepted")
        self.assertEqual(len(r["evidence_spans"]), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
