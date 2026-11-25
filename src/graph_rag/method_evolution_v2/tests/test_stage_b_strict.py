"""Stage B v2 (strict) 单测: audit_batching + duplicate_detection + edge_validation_strict."""
from __future__ import annotations

import os
import sys
import unittest

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
V2_DIR = os.path.dirname(THIS_DIR)
SRC_GRAPH_RAG_DIR = os.path.dirname(V2_DIR)
if SRC_GRAPH_RAG_DIR not in sys.path:
    sys.path.insert(0, SRC_GRAPH_RAG_DIR)

from method_evolution_v2.stage_b import (                       # noqa: E402
    audit_batching as ab,
    duplicate_detection as dd,
    edge_validation_strict as evs,
    pair_generator as pg,
)


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


class TestDuplicateDetection(unittest.TestCase):
    def test_identical(self):
        ok, _ = dd.looks_like_alias("溶胶-凝胶法", "溶胶-凝胶法")
        self.assertTrue(ok)

    def test_qualifier_prefix(self):
        # 尿素/氯化胆碱 是限定前缀, 剥掉后剩下相同
        ok, reason = dd.looks_like_alias(
            "低共熔溶剂基纳米流体制备方法",
            "尿素/氯化胆碱低共熔溶剂基纳米流体制备方法")
        self.assertTrue(ok)
        self.assertIn("qualifier", reason)

    def test_distinct_methods_not_alias(self):
        ok, _ = dd.looks_like_alias(
            "溶胶-凝胶法制备正极", "水热法合成负极")
        self.assertFalse(ok)

    def test_similar_but_different_aspects_not_alias(self):
        """'均一性优化' 与 '均一性设计' 是同技术的不同侧面, 不算 alias."""
        ok, _ = dd.looks_like_alias(
            "液流电池均一性优化",
            "液流电池均一性设计")
        self.assertFalse(ok)

    def test_short_extra_content(self):
        """长者 = 短者 + ≤4 字额外 → alias."""
        ok, reason = dd.looks_like_alias(
            "溶胶-凝胶法",
            "溶胶-凝胶法制备")
        self.assertTrue(ok)
        self.assertIn("short_extra", reason)


class TestAuditBatching(unittest.TestCase):
    def test_no_proposals(self):
        r = ab.run_audit_with_coverage(
            [], {}, {}, build_prompt=lambda x, y: "", call_llm=lambda p: ({}, True, "", {}, "")
        )
        self.assertEqual(r["call_count"], 0)
        self.assertEqual(r["missing_pair_ids"], [])

    def test_full_coverage_single_batch(self):
        proposals = [{"pair_id": f"P{i:03d}"} for i in range(1, 6)]  # 5 pairs
        def _prompt(batch, bs):
            return f"prompt for {[p['pair_id'] for p in batch]}"
        def _llm(prompt):
            # 从 prompt 里回读 pair_ids
            pids = eval(prompt.split(" for ", 1)[1])
            return {"audits": [{"pair_id": pid, "support": "supported"} for pid in pids]}, True, "", {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}, ""
        r = ab.run_audit_with_coverage(proposals, {}, {},
                                        build_prompt=_prompt, call_llm=_llm,
                                        batch_size=8)
        self.assertEqual(r["call_count"], 1)   # 5 ≤ 8, 单 batch
        self.assertEqual(len(r["covered_pair_ids"]), 5)
        self.assertEqual(r["missing_pair_ids"], [])
        self.assertEqual(r["batches_run"], 1)

    def test_batching_when_exceeds_size(self):
        proposals = [{"pair_id": f"P{i:03d}"} for i in range(1, 20)]  # 19 pairs
        def _prompt(batch, bs):
            return f"prompt for {[p['pair_id'] for p in batch]}"
        def _llm(prompt):
            pids = eval(prompt.split(" for ", 1)[1])
            return {"audits": [{"pair_id": pid} for pid in pids]}, True, "", {}, ""
        r = ab.run_audit_with_coverage(proposals, {}, {},
                                        build_prompt=_prompt, call_llm=_llm,
                                        batch_size=8)
        # 19 / 8 = 3 batches
        self.assertEqual(r["batches_run"], 3)
        self.assertEqual(r["call_count"], 3)
        self.assertEqual(len(r["covered_pair_ids"]), 19)

    def test_recovery_when_missing(self):
        proposals = [{"pair_id": f"P{i:03d}"} for i in range(1, 6)]
        # 第一次只返回一半, 第二次返回完整
        call_seq = [0]
        def _prompt(batch, bs):
            return f"prompt for {[p['pair_id'] for p in batch]}"
        def _llm(prompt):
            call_seq[0] += 1
            pids = eval(prompt.split(" for ", 1)[1])
            if call_seq[0] == 1:
                # 第一次截断: 只返回前 2
                return {"audits": [{"pair_id": pid} for pid in pids[:2]]}, True, "", {}, ""
            else:
                # 第二次(recovery)返回全部
                return {"audits": [{"pair_id": pid} for pid in pids]}, True, "", {}, ""
        r = ab.run_audit_with_coverage(proposals, {}, {},
                                        build_prompt=_prompt, call_llm=_llm,
                                        batch_size=8)
        self.assertEqual(r["call_count"], 2)
        self.assertEqual(r["recovery_runs"], 1)
        self.assertEqual(len(r["covered_pair_ids"]), 5)
        self.assertEqual(r["missing_pair_ids"], [])

    def test_still_missing_after_recovery(self):
        proposals = [{"pair_id": f"P{i:03d}"} for i in range(1, 4)]
        # 两次都不完整
        def _prompt(batch, bs):
            return "p"
        def _llm(prompt):
            return {"audits": [{"pair_id": "P001"}]}, True, "", {}, ""
        r = ab.run_audit_with_coverage(proposals, {}, {},
                                        build_prompt=_prompt, call_llm=_llm,
                                        batch_size=8, max_recovery_calls=1)
        self.assertEqual(r["call_count"], 2)   # 1 batch + 1 recovery
        self.assertEqual(r["missing_pair_ids"], ["P002", "P003"])


class TestEdgeValidationStrict(unittest.TestCase):
    def _fixture(self, verdict="EXTENDS",
                  linkage_type="independent_methods",
                  endpoint_linkage="explicit_both",
                  support="supported", direction="correct",
                  relation_check="correct",
                  from_status="accepted", to_status="accepted",
                  quote_has_trigger=True,
                  sids=None,
                  from_name="B 方法", to_name="A 方法"):
        # 证据句
        base_text = "本文在 A 方法基础上改进得到 B 方法, 相比 A 效率提升."
        no_trigger_text = "A 方法是 X. B 方法是 Y."
        text = base_text if quote_has_trigger else no_trigger_text
        idx = {"methods_p3_s1": _mk_sent("methods_p3_s1", text, 0, len(text))}
        methods = {
            "m_a": {"paper_id": "p", "method_id": "m_a", "name": to_name,
                    "kind": "referenced", "validation_status": to_status,
                    "citation_clue": "Smith 2018",
                    "evidence_sentence_ids": ["methods_p3_s1"]},
            "m_b": {"paper_id": "p", "method_id": "m_b", "name": from_name,
                    "kind": "own", "validation_status": from_status,
                    "citation_clue": "",
                    "evidence_sentence_ids": ["methods_p3_s1"]},
        }
        rel = {
            "pair_id": "P001", "verdict": verdict,
            "from_method_id": "m_b", "to_method_id": "m_a",
            "relation_evidence_sentence_ids": sids or ["methods_p3_s1"],
            "note": "", "direction_basis": "", "relation_reason": "",
            "confidence_llm": "high",
        }
        audit = {"P001": {
            "linkage_type": linkage_type,
            "endpoint_linkage": endpoint_linkage,
            "coreference_explanation": "explanation",
            "support": support, "direction": direction,
            "relation_check": relation_check,
            "suggested_relation": "",
            "audit_reason": "",
        }}
        return methods, idx, rel, audit

    def test_accepted_happy_path(self):
        methods, idx, rel, audit = self._fixture()
        r = evs.validate_and_classify_edge_strict(rel, methods, idx, audit)
        self.assertEqual(r["validation_status"], "accepted",
                          msg=f"reasons={r['rejected_reason']}")

    def test_rejected_extractor_no_relation(self):
        methods, idx, rel, audit = self._fixture(verdict="NO_RELATION")
        r = evs.validate_and_classify_edge_strict(rel, methods, idx, audit)
        self.assertEqual(r["validation_status"], "rejected")
        self.assertIn("extractor_no_relation", r["rejected_reason"])

    def test_rejected_whole_component(self):
        methods, idx, rel, audit = self._fixture(linkage_type="whole_component")
        r = evs.validate_and_classify_edge_strict(rel, methods, idx, audit)
        self.assertEqual(r["validation_status"], "rejected")
        self.assertIn("whole_component_relation", r["rejected_reason"])

    def test_rejected_duplicate_alias(self):
        methods, idx, rel, audit = self._fixture(linkage_type="duplicate_or_alias")
        r = evs.validate_and_classify_edge_strict(rel, methods, idx, audit)
        self.assertEqual(r["validation_status"], "rejected")
        self.assertIn("duplicate_or_alias", r["rejected_reason"])

    def test_rejected_ambiguous_coreference(self):
        methods, idx, rel, audit = self._fixture(endpoint_linkage="ambiguous")
        r = evs.validate_and_classify_edge_strict(rel, methods, idx, audit)
        self.assertEqual(r["validation_status"], "rejected")
        self.assertIn("endpoint_linkage_ambiguous", r["rejected_reason"])

    def test_rejected_no_trigger(self):
        methods, idx, rel, audit = self._fixture(quote_has_trigger=False)
        r = evs.validate_and_classify_edge_strict(rel, methods, idx, audit)
        self.assertEqual(r["validation_status"], "rejected")
        self.assertIn("no_explicit_trigger", r["rejected_reason"])

    def test_rejected_audit_missing(self):
        methods, idx, rel, _ = self._fixture()
        r = evs.validate_and_classify_edge_strict(rel, methods, idx, {})
        self.assertEqual(r["validation_status"], "rejected")
        self.assertIn("audit_missing", r["rejected_reason"])

    def test_candidate_when_endpoint_is_candidate(self):
        methods, idx, rel, audit = self._fixture(from_status="candidate")
        r = evs.validate_and_classify_edge_strict(rel, methods, idx, audit)
        self.assertEqual(r["validation_status"], "candidate")
        self.assertIn("endpoint_is_candidate", r["rejected_reason"])

    def test_candidate_when_audit_weak_support(self):
        methods, idx, rel, audit = self._fixture(support="weak")
        r = evs.validate_and_classify_edge_strict(rel, methods, idx, audit)
        self.assertEqual(r["validation_status"], "candidate")

    def test_rejected_when_alias_heuristic_and_audit_confirms(self):
        methods, idx, rel, audit = self._fixture(
            from_name="尿素/氯化胆碱低共熔溶剂基纳米流体制备方法",
            to_name="低共熔溶剂基纳米流体制备方法",
            linkage_type="duplicate_or_alias",
        )
        r = evs.validate_and_classify_edge_strict(rel, methods, idx, audit)
        self.assertEqual(r["validation_status"], "rejected")
        # 两个信号都触发
        self.assertIn("heuristic_alias_flag", r["rejected_reason"])
        self.assertIn("duplicate_or_alias", r["rejected_reason"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
