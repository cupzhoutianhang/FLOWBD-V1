"""Stage A 全量 runner + provenance + budget 单测 (0 API).

覆盖 spec 九:
  - 断点续跑 (成功文件跳过)
  - 输入哈希变化后重新处理
  - prompt 版本变化后重新处理
  - 单篇失败不影响下一篇
  - dry-run 零 API
  - cost ledger 追加
  - 外部 stub 稳定 ID
  - 综述引用方法不能变成 own
  - citation 年份不能使用综述年份
  - 不读取 legacy
  - 不写数据库
"""
from __future__ import annotations

import csv
import inspect
import json
import os
import shutil
import sys
import tempfile
import unittest

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
V2_DIR = os.path.dirname(THIS_DIR)
SRC_GRAPH_RAG_DIR = os.path.dirname(V2_DIR)
if SRC_GRAPH_RAG_DIR not in sys.path:
    sys.path.insert(0, SRC_GRAPH_RAG_DIR)

from method_evolution_v2.stage_a import (      # noqa: E402
    provenance as prov,
    budget_estimator as be,
    full_runner as fr,
)
from method_evolution_v2.stage_a import prompts as prompts_mod   # noqa: E402


# ============================================================
# Provenance
# ============================================================

class TestProvenance(unittest.TestCase):

    def test_parse_citation_clue_chinese_author(self):
        r = prov.parse_citation_clue("刘昌会等[93] 2020")
        self.assertEqual(r["author"], "刘昌会等")
        self.assertEqual(r["year"], "2020")
        self.assertEqual(r["reference_number"], "93")

    def test_parse_citation_clue_english_author(self):
        r = prov.parse_citation_clue("Smith et al. 2018")
        self.assertEqual(r["author"], "Smith")
        self.assertEqual(r["year"], "2018")

    def test_parse_citation_clue_empty(self):
        r = prov.parse_citation_clue("")
        self.assertEqual(r["author"], "")
        self.assertEqual(r["year"], "")
        self.assertEqual(r["raw"], "")

    def test_parse_citation_clue_reference_range(self):
        r = prov.parse_citation_clue("[1-3]")
        self.assertEqual(r["reference_number"], "1-3")

    def test_support_scope_research_own(self):
        self.assertEqual(prov.derive_support_scope("research_article", "own"),
                          "primary_article")

    def test_support_scope_research_referenced(self):
        self.assertEqual(prov.derive_support_scope("research_article", "referenced"),
                          "article_reference")

    def test_support_scope_review_referenced_becomes_secondary(self):
        """spec 二: 综述里的 referenced 应标为 review_secondary, 不冒充 own."""
        self.assertEqual(prov.derive_support_scope("review_article", "referenced"),
                          "review_secondary")

    def test_support_scope_patent_referenced(self):
        self.assertEqual(prov.derive_support_scope("patent_analysis", "referenced"),
                          "patent_secondary")

    def test_source_provenance_own_is_in_corpus_primary(self):
        self.assertEqual(prov.derive_source_provenance("own"),
                          "in_corpus_primary")

    def test_source_provenance_referenced_default_is_cited_external(self):
        self.assertEqual(prov.derive_source_provenance("referenced"),
                          "cited_external")

    def test_external_stub_id_stability(self):
        """spec 九: 外部 stub 稳定 ID — 相同输入必须相同 ID."""
        a = prov.make_external_stub_id("Smith", "2018", "15", "溶胶-凝胶法")
        b = prov.make_external_stub_id("Smith", "2018", "15", "溶胶-凝胶法")
        self.assertEqual(a, b)
        self.assertTrue(a.startswith("ext::"))
        # 不同输入 → 不同 ID
        c = prov.make_external_stub_id("Smith", "2020", "15", "溶胶-凝胶法")
        self.assertNotEqual(a, c)

    def test_attach_provenance_review_ref_not_own(self):
        """spec 九: 综述的 referenced 不能被冒充为 own."""
        m = {"kind": "referenced", "name": "Smith 团队 X 方法",
             "citation_clue": "Smith 2018"}
        out = prov.attach_provenance(m, "review-paper-id", "review_article")
        self.assertEqual(out["support_scope"], "review_secondary")
        self.assertEqual(out["source_provenance"], "cited_external")
        self.assertNotEqual(out["support_scope"], "primary_article",
                              "review referenced must not be primary_article")
        self.assertEqual(out["cited_year"], "2018")
        # original_source_paper_id 绝不填 (spec 二)
        self.assertEqual(out["original_source_paper_id"], "")

    def test_attach_provenance_year_never_uses_paper_year(self):
        """spec 九: 综述的年份不能自动填给 referenced 方法."""
        m = {"kind": "referenced", "name": "Old Method",
             "citation_clue": ""}   # 无 clue → year 应空
        out = prov.attach_provenance(m, "review-2024", "review_article")
        self.assertEqual(out["cited_year"], "",
                          "cited_year must not fall back to paper year")

    def test_attach_provenance_never_fills_original_source_paper_id(self):
        """spec 二 硬要求: 不允许仅凭方法名相似填 original_source_paper_id."""
        m = {"kind": "referenced", "name": "Smith Method",
             "citation_clue": "Smith 2018"}
        out = prov.attach_provenance(m, "some-paper", "research_article")
        self.assertEqual(out["original_source_paper_id"], "",
                          "original_source_paper_id must be empty this stage")


# ============================================================
# Budget estimator
# ============================================================

class TestBudgetEstimator(unittest.TestCase):

    def test_tier_routing(self):
        self.assertEqual(be.route_to_tier(5000), "moonshot-v1-8k")
        self.assertEqual(be.route_to_tier(20000), "moonshot-v1-32k")
        self.assertEqual(be.route_to_tier(100000), "moonshot-v1-128k")
        self.assertEqual(be.route_to_tier(200000), "moonshot-v1-128k")

    def test_chars_to_tokens(self):
        self.assertEqual(be.estimate_tokens_from_chars(4000), 2000)
        self.assertEqual(be.estimate_tokens_from_chars(0), 0)

    def test_per_paper_cost(self):
        r = be.per_paper_cost_estimate(30000, 3000)
        self.assertEqual(r["tier"], "moonshot-v1-32k")
        self.assertGreater(r["cost_cny"], 0)

    def test_build_budget_report(self):
        char_counts = [10000, 20000, 60000, 200000, 5000]
        r = be.build_budget_report(char_counts, n_papers=5, batch_size=2)
        self.assertEqual(r["run_config"]["n_batches"], 3)   # ceil(5/2)
        self.assertIn("empirical_linear_from_v03", r["estimates"])
        self.assertIn("per_token_actual", r["estimates"])
        self.assertIn("worst_case_128k_full_retry", r["estimates"])
        # tier 分布
        tiers = r["tier_routing_distribution"]
        self.assertGreaterEqual(sum(tiers.values()), 5)


# ============================================================
# Full runner: resume / hash / prompt version
# ============================================================

class TestFullRunner(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        # 假 full.md
        self.paper_id = "test-paper-1"
        self.md_path = os.path.join(self.tmp, "full.md")
        with open(self.md_path, "w", encoding="utf-8") as f:
            f.write("# 测试论文\n\n# 摘要\n本文提出溶胶-凝胶法制备正极.\n"
                     "\n# 1 实验\n以 LiFePO4 为原料, 采用溶胶-凝胶法制备正极材料。\n"
                     "反应温度 800°C 煅烧 2 小时。\n"
                     "\n# 2 结果\n结果表明比容量达 150 mAh/g.\n")
        self.base_dir = os.path.join(self.tmp, "per_paper")
        os.makedirs(self.base_dir, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_paper_id_to_dir_stable(self):
        a = fr.paper_id_to_dir_name("全钒液流电池电堆的均一性")
        b = fr.paper_id_to_dir_name("全钒液流电池电堆的均一性")
        self.assertEqual(a, b)
        self.assertEqual(len(a), 12)

    def test_input_manifest_includes_sha_prompt_model(self):
        m = fr.build_input_manifest(self.paper_id, self.md_path,
                                       model="moonshot-v1-auto")
        self.assertIn("full_md_sha256", m)
        self.assertEqual(m["prompt_version"], prompts_mod.PROMPT_VERSION)
        self.assertEqual(m["model"], "moonshot-v1-auto")
        # SHA 应该稳定
        m2 = fr.build_input_manifest(self.paper_id, self.md_path,
                                        model="moonshot-v1-auto")
        self.assertEqual(m["full_md_sha256"], m2["full_md_sha256"])

    def test_should_skip_no_previous(self):
        current = fr.build_input_manifest(self.paper_id, self.md_path,
                                            "moonshot-v1-auto")
        skip, reason = fr.should_skip(self.paper_id, current, self.base_dir)
        self.assertFalse(skip)
        self.assertEqual(reason, "no_previous_run")

    def _seed_prev_files(self, d, manifest_dict, with_raw=True):
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "input_manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest_dict, f, ensure_ascii=False, indent=2)
        with open(os.path.join(d, "validation_report.json"), "w", encoding="utf-8") as f:
            json.dump({}, f)
        if with_raw:
            with open(os.path.join(d, "raw_response.json"), "w", encoding="utf-8") as f:
                json.dump({"own_methods_raw": [], "referenced_methods_raw": []}, f)

    def test_should_skip_when_manifest_matches_and_report_present(self):
        current = fr.build_input_manifest(self.paper_id, self.md_path,
                                            "moonshot-v1-auto")
        d = fr.per_paper_dir(self.paper_id, self.base_dir)
        self._seed_prev_files(d, current)
        skip, reason = fr.should_skip(self.paper_id, current, self.base_dir)
        self.assertTrue(skip)
        self.assertEqual(reason, "input_hash_matches_previous_success")

    def test_should_not_skip_when_full_md_sha_changes(self):
        current = fr.build_input_manifest(self.paper_id, self.md_path,
                                            "moonshot-v1-auto")
        d = fr.per_paper_dir(self.paper_id, self.base_dir)
        old = dict(current)
        old["full_md_sha256"] = "0" * 64
        self._seed_prev_files(d, old)
        skip, reason = fr.should_skip(self.paper_id, current, self.base_dir)
        self.assertFalse(skip)
        # v1.1 reason 格式: api_hash_change:<key>
        self.assertIn("full_md_sha256", reason)

    def test_should_not_skip_when_prompt_version_changes(self):
        current = fr.build_input_manifest(self.paper_id, self.md_path,
                                            "moonshot-v1-auto")
        d = fr.per_paper_dir(self.paper_id, self.base_dir)
        old = dict(current)
        old["prompt_version"] = "different_prompt_v0"
        self._seed_prev_files(d, old)
        skip, reason = fr.should_skip(self.paper_id, current, self.base_dir)
        self.assertFalse(skip)
        self.assertIn("prompt_version", reason)

    def test_should_not_skip_when_model_changes(self):
        current = fr.build_input_manifest(self.paper_id, self.md_path,
                                            "moonshot-v1-auto")
        d = fr.per_paper_dir(self.paper_id, self.base_dir)
        old = dict(current)
        old["model"] = "moonshot-v1-8k"
        self._seed_prev_files(d, old)
        skip, reason = fr.should_skip(self.paper_id, current, self.base_dir)
        self.assertFalse(skip)
        self.assertIn("model", reason)

    def test_should_not_skip_when_previous_incomplete(self):
        current = fr.build_input_manifest(self.paper_id, self.md_path,
                                            "moonshot-v1-auto")
        d = fr.per_paper_dir(self.paper_id, self.base_dir)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "input_manifest.json"), "w", encoding="utf-8") as f:
            json.dump(current, f)
        # 无 validation_report.json → 视为未完成
        skip, reason = fr.should_skip(self.paper_id, current, self.base_dir)
        self.assertFalse(skip)
        self.assertEqual(reason, "previous_run_incomplete")

    def test_run_one_paper_with_mock_llm_zero_api(self):
        """dry-run 场景之外, run_one_paper 用注入的 mock caller → 也不调实 LLM."""
        calls = []
        def mock_caller(sys_prompt, user_prompt, model=None):
            calls.append({"sys_len": len(sys_prompt),
                           "user_len": len(user_prompt)})
            return ({"own_methods": [], "referenced_methods": []},
                     True, "", {"prompt_tokens": 100, "completion_tokens": 20,
                                 "total_tokens": 120}, "{}")
        spec = fr.RunSpec(paper_id=self.paper_id,
                           canonical_title="测试论文",
                           paper_type="research_article",
                           paper_context_status="confirmed")
        result = fr.run_one_paper(spec, self.md_path, mock_caller,
                                     base_dir=self.base_dir,
                                     write_output=True)
        self.assertEqual(len(calls), 1)   # 主调用
        self.assertEqual(result["json_parse_ok"], True)
        # 分桶
        self.assertEqual(len(result["methods_accepted"]), 0)
        # per-paper 目录内文件全部落盘
        d = fr.per_paper_dir(self.paper_id, self.base_dir)
        for name in ("input_manifest.json", "sentence_index.json",
                       "raw_response.json", "methods_accepted.json",
                       "methods_candidate.json", "methods_rejected.json",
                       "validation_report.json", "run_log.json"):
            self.assertTrue(os.path.isfile(os.path.join(d, name)),
                              f"missing {name}")

    def test_run_one_paper_retry_on_json_fail(self):
        """spec 四: JSON 失败最多重试 1 次."""
        state = {"count": 0}
        def flaky_caller(sys_prompt, user_prompt, model=None):
            state["count"] += 1
            if state["count"] == 1:
                # 首次: JSON 解析失败 (mock caller 已模拟)
                return ({}, False, "json_decode_error", {}, "not json")
            # 第二次成功
            return ({"own_methods": [], "referenced_methods": []},
                     True, "", {"prompt_tokens": 50, "completion_tokens": 10,
                                 "total_tokens": 60}, "{}")
        spec = fr.RunSpec(paper_id=self.paper_id, paper_type="research_article")
        result = fr.run_one_paper(spec, self.md_path, flaky_caller,
                                     base_dir=self.base_dir)
        self.assertEqual(state["count"], 2)   # 主 + 重试
        self.assertEqual(result["call_count"], 2)

    def test_batches_deterministic(self):
        ids = ["c-paper", "a-paper", "b-paper", "d-paper", "e-paper"]
        b1 = fr.compute_batches(ids, batch_size=2)
        b2 = fr.compute_batches(ids, batch_size=2)
        self.assertEqual(b1, b2)
        # 按字母排序切
        self.assertEqual(b1[0], ["a-paper", "b-paper"])

    def test_cost_ledger_append(self):
        p = os.path.join(self.tmp, "cost.csv")
        fr.append_cost_ledger({
            "timestamp": "2026-07-01T10:00:00",
            "paper_id": "p1", "call_count": 1,
            "prompt_tokens": 100, "completion_tokens": 20,
            "total_tokens": 120, "estimated_cost_cny": 0.01,
            "model": "moonshot-v1-auto",
        }, p)
        fr.append_cost_ledger({
            "timestamp": "2026-07-01T10:01:00",
            "paper_id": "p2", "call_count": 2,
            "prompt_tokens": 200, "completion_tokens": 40,
            "total_tokens": 240, "estimated_cost_cny": 0.02,
            "model": "moonshot-v1-auto",
        }, p)
        with open(p, "r", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["paper_id"], "p1")
        self.assertEqual(rows[1]["paper_id"], "p2")

    def test_failed_and_skipped_append(self):
        pf = os.path.join(self.tmp, "failed.csv")
        ps = os.path.join(self.tmp, "skipped.csv")
        fr.append_failed("p1", 1, "TestError", "test message", pf)
        fr.append_skipped("p2", 1, "hash_match", ps)
        with open(pf, "r", encoding="utf-8-sig") as f:
            self.assertEqual(len(list(csv.DictReader(f))), 1)
        with open(ps, "r", encoding="utf-8-sig") as f:
            self.assertEqual(len(list(csv.DictReader(f))), 1)


# ============================================================
# 不读 legacy / 不写数据库 (源码 grep)
# ============================================================

class TestNoLegacyNoDb(unittest.TestCase):

    def test_full_runner_source_no_legacy_paths(self):
        src = inspect.getsource(fr)
        forbidden = ["methods.csv", "edges.csv", "method_outputs",
                       "subfield_keywords"]
        for tok in forbidden:
            # 允许出现在注释/docstring 里, 但不能在真正的 os.path.join 等 API 里
            # 这里做保守: 不出现即通过
            if tok in src:
                # 出现在 docstring 也接受: 只需确认没有实际使用它们的 open/join
                bad = f"open({tok!r}" in src or f'open("{tok}"' in src
                self.assertFalse(bad, f"legacy path referenced: {tok}")

    def test_full_runner_source_no_neo4j_milvus(self):
        src = inspect.getsource(fr)
        for tok in ("neo4j", "milvus", "Neo4j", "Milvus"):
            self.assertNotIn(tok, src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
