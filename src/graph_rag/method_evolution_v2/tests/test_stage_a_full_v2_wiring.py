"""Stage A full_runner v1.1 wiring tests (spec 二).

覆盖:
  1. full_runner 确实调 v2 validator
  2. full_runner 确实调 v2 provenance
  3. 仅验证器版本变化时 → decide_run_action='revalidate' (无 API)
  4. prompt/model/SHA 变化时 → decide_run_action='run_api'
  5. batch 1 原始 raw_response.json 不被覆盖 (revalidate 只读)
  6. 新批次输出记录完整版本 (evidence_validation_version + provenance_version)
"""
from __future__ import annotations

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

from method_evolution_v2.stage_a import full_runner as fr
from method_evolution_v2.stage_a import evidence_validation_v2 as ev2
from method_evolution_v2.stage_a import provenance_v2 as pv2


class TestV2WiringInManifest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.pid = "wire-test-1"
        self.md_path = os.path.join(self.tmp, "full.md")
        with open(self.md_path, "w", encoding="utf-8") as f:
            f.write("# 论文标题\n\n# 摘要\n本文提出溶液燃烧法制备钙钛矿型高熵氧化物。\n"
                     "\n# 1 实验\n采用溶液燃烧法制备了钙钛矿高熵氧化物。\n"
                     "\n# 2 结果\n结果表明储锂比容量提升。\n")
        self.base = os.path.join(self.tmp, "per_paper")
        os.makedirs(self.base, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_manifest_contains_both_api_and_validator_versions(self):
        """spec 二.6: 新批次输出必须记录完整版本."""
        m = fr.build_input_manifest(self.pid, self.md_path, model="test-model")
        # API 层
        for k in fr.API_HASH_KEYS:
            self.assertIn(k, m, f"missing api_hash key {k}")
        # 验证器层
        for k in fr.VALIDATOR_KEYS:
            self.assertIn(k, m, f"missing validator key {k}")
        self.assertEqual(m["evidence_validation_version"],
                          ev2.EVIDENCE_VALIDATION_VERSION)
        self.assertEqual(m["provenance_version"], pv2.PROVENANCE_VERSION)


class TestDecideRunAction(unittest.TestCase):
    """spec 二.3, 二.4: 3-way resume dispatcher."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.pid = "action-test-1"
        self.md = os.path.join(self.tmp, "full.md")
        with open(self.md, "w", encoding="utf-8") as f:
            f.write("some content")
        self.base = os.path.join(self.tmp, "per_paper")
        os.makedirs(self.base, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _seed_prev_run(self, prev_manifest, with_raw=True):
        d = fr.per_paper_dir(self.pid, self.base)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "input_manifest.json"), "w",
                    encoding="utf-8") as f:
            json.dump(prev_manifest, f)
        with open(os.path.join(d, "validation_report.json"), "w",
                    encoding="utf-8") as f:
            json.dump({}, f)
        if with_raw:
            with open(os.path.join(d, "raw_response.json"), "w",
                        encoding="utf-8") as f:
                json.dump({"own_methods_raw": [], "referenced_methods_raw": []}, f)

    def test_no_previous_returns_run_api(self):
        current = fr.build_input_manifest(self.pid, self.md, model="x")
        action, reason = fr.decide_run_action(self.pid, current, self.base)
        self.assertEqual(action, "run_api")
        self.assertEqual(reason, "no_previous_run")

    def test_same_hashes_returns_skip(self):
        current = fr.build_input_manifest(self.pid, self.md, model="x")
        self._seed_prev_run(current)
        action, _ = fr.decide_run_action(self.pid, current, self.base)
        self.assertEqual(action, "skip")

    def test_only_validator_change_returns_revalidate(self):
        current = fr.build_input_manifest(self.pid, self.md, model="x")
        prev = dict(current)
        prev["evidence_validation_version"] = "v2.0_old"    # 变
        prev["provenance_version"] = pv2.PROVENANCE_VERSION  # 不变
        self._seed_prev_run(prev)
        action, reason = fr.decide_run_action(self.pid, current, self.base)
        self.assertEqual(action, "revalidate")
        self.assertIn("evidence_validation_version", reason)

    def test_provenance_change_only_returns_revalidate(self):
        current = fr.build_input_manifest(self.pid, self.md, model="x")
        prev = dict(current)
        prev["provenance_version"] = "v1.0_old"
        self._seed_prev_run(prev)
        action, reason = fr.decide_run_action(self.pid, current, self.base)
        self.assertEqual(action, "revalidate")
        self.assertIn("provenance_version", reason)

    def test_prompt_version_change_returns_run_api(self):
        current = fr.build_input_manifest(self.pid, self.md, model="x")
        prev = dict(current)
        prev["prompt_version"] = "different_prompt_v0"
        self._seed_prev_run(prev)
        action, reason = fr.decide_run_action(self.pid, current, self.base)
        self.assertEqual(action, "run_api")
        self.assertIn("prompt_version", reason)

    def test_full_md_sha_change_returns_run_api(self):
        current = fr.build_input_manifest(self.pid, self.md, model="x")
        prev = dict(current)
        prev["full_md_sha256"] = "0" * 64
        self._seed_prev_run(prev)
        action, reason = fr.decide_run_action(self.pid, current, self.base)
        self.assertEqual(action, "run_api")
        self.assertIn("full_md_sha256", reason)

    def test_model_change_returns_run_api(self):
        current = fr.build_input_manifest(self.pid, self.md, model="new-model")
        prev = dict(current)
        prev["model"] = "old-model"
        self._seed_prev_run(prev)
        action, reason = fr.decide_run_action(self.pid, current, self.base)
        self.assertEqual(action, "run_api")
        self.assertIn("model", reason)

    def test_missing_raw_response_returns_run_api(self):
        current = fr.build_input_manifest(self.pid, self.md, model="x")
        self._seed_prev_run(current, with_raw=False)
        action, reason = fr.decide_run_action(self.pid, current, self.base)
        self.assertEqual(action, "run_api")
        self.assertEqual(reason, "raw_response_missing")


class TestRevalidateOnePaper(unittest.TestCase):
    """spec 二.3, 二.5: revalidate 无 API + 不覆盖 raw_response.json."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.pid = "revalidate-test-1"
        self.md = os.path.join(self.tmp, "full.md")
        full_md = ("# 测试论文\n\n# 摘要\n本文提出了溶液燃烧法制备钙钛矿型高熵氧化物。\n"
                     "\n# 1 实验\n采用溶液燃烧法制备。\n")
        with open(self.md, "w", encoding="utf-8") as f:
            f.write(full_md)
        self.base = os.path.join(self.tmp, "per_paper")
        os.makedirs(self.base, exist_ok=True)

        # 预先 seed 一个 per_paper 目录 (模拟上次成功的产物)
        d = fr.per_paper_dir(self.pid, self.base)
        os.makedirs(d, exist_ok=True)

        # 一个真实的 sentence_index (与 full_md 对齐, 简化用 offset 0)
        self.raw_response = {
            "own_methods_raw": [{
                "name": "溶液燃烧法制备钙钛矿型高熵氧化物",
                "proposed_method_type": "synthesis_process",
                "problem_solved": "构建 Cu 空位提升储锂性能",
                "key_components": ["Cu 空位"],
                "evidence_sentence_ids": ["methods_p1_s1"],
                "citation_clue": "",
                "confidence_llm": "high",
            }],
            "referenced_methods_raw": [],
            "raw_llm_text_last": "{}",
            "json_parse_ok": True,
            "json_parse_error": "",
            "llm_calls": [{"attempt": "primary", "ok": True, "error": "",
                             "usage": {"prompt_tokens": 100, "completion_tokens": 20,
                                        "total_tokens": 120}}],
            "usage_total": {"prompt_tokens": 100, "completion_tokens": 20,
                              "total_tokens": 120},
        }
        with open(os.path.join(d, "raw_response.json"), "w",
                    encoding="utf-8") as f:
            json.dump(self.raw_response, f, ensure_ascii=False)

        with open(os.path.join(d, "sentence_index.json"), "w",
                    encoding="utf-8") as f:
            json.dump({
                "paper_id": self.pid,
                "sentence_count": 1,
                "sentences": [{
                    "sentence_id": "methods_p1_s1",
                    "paper_id": self.pid,
                    "section_type": "methods",
                    "section_name": "1 实验",
                    "para_id": "methods_p1",
                    "sentence_text": "采用溶液燃烧法制备钙钛矿型高熵氧化物。",
                    "char_start": 0,
                    "char_end": 20,
                }],
            }, f, ensure_ascii=False)

        with open(os.path.join(d, "input_manifest.json"), "w",
                    encoding="utf-8") as f:
            json.dump({
                "paper_id": self.pid,
                "full_md_sha256": "test_sha",
                "prompt_version": "stage_a_v2.0_sentence_ids",
                "model": "test-model",
                "section_parser_version": "1.1.1",
                "stage_a_engine_version": "2.0",
                "evidence_validation_version": "v1_old",
                "provenance_version": "v1_old",
                "stage_a_full_version": "1.0",
            }, f, ensure_ascii=False)

        # 记录 raw_response.json 的原始 hash 用于比较
        import hashlib
        with open(os.path.join(d, "raw_response.json"), "rb") as f:
            self._raw_sha_before = hashlib.sha256(f.read()).hexdigest()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_revalidate_produces_v2_result_no_api(self):
        spec = fr.RunSpec(paper_id=self.pid,
                            canonical_title="测试论文",
                            paper_type="research_article",
                            paper_context_status="confirmed")
        result = fr.revalidate_one_paper(spec, base_dir=self.base)
        # 无 API 调用
        self.assertEqual(result["call_count"], 0)
        self.assertEqual(result["action"], "revalidated_no_api")
        # v2 应把 "溶液燃烧法制备钙钛矿" 判 accepted (tier1_named_process)
        self.assertGreaterEqual(len(result["methods_accepted"]), 1)

    def test_revalidate_does_not_overwrite_raw_response(self):
        """spec 二.5 硬性要求: raw_response.json 不能被覆盖."""
        import hashlib
        spec = fr.RunSpec(paper_id=self.pid, paper_type="research_article")
        fr.revalidate_one_paper(spec, base_dir=self.base)
        d = fr.per_paper_dir(self.pid, self.base)
        with open(os.path.join(d, "raw_response.json"), "rb") as f:
            after = hashlib.sha256(f.read()).hexdigest()
        self.assertEqual(self._raw_sha_before, after,
                          "raw_response.json 内容被改动了")

    def test_revalidate_updates_manifest_validator_versions(self):
        spec = fr.RunSpec(paper_id=self.pid, paper_type="research_article")
        fr.revalidate_one_paper(spec, base_dir=self.base)
        d = fr.per_paper_dir(self.pid, self.base)
        with open(os.path.join(d, "input_manifest.json"), "r",
                    encoding="utf-8") as f:
            m = json.load(f)
        # 保留原始 API 层
        self.assertEqual(m["full_md_sha256"], "test_sha")
        self.assertEqual(m["prompt_version"], "stage_a_v2.0_sentence_ids")
        # 更新验证器
        self.assertEqual(m["evidence_validation_version"],
                          ev2.EVIDENCE_VALIDATION_VERSION)
        self.assertEqual(m["provenance_version"], pv2.PROVENANCE_VERSION)
        self.assertIn("last_revalidated_at", m)

    def test_revalidate_logs_event_in_run_log(self):
        spec = fr.RunSpec(paper_id=self.pid, paper_type="research_article")
        fr.revalidate_one_paper(spec, base_dir=self.base)
        d = fr.per_paper_dir(self.pid, self.base)
        with open(os.path.join(d, "run_log.json"), "r", encoding="utf-8") as f:
            log = json.load(f)
        self.assertIn("revalidations", log)
        self.assertEqual(len(log["revalidations"]), 1)
        self.assertEqual(log["revalidations"][0]["evidence_validation_version"],
                          ev2.EVIDENCE_VALIDATION_VERSION)


class TestRunOnePaperUsesV2(unittest.TestCase):
    """spec 二.1, 二.2: run_one_paper 必须走 v2 resolver + v2 provenance."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.pid = "run-test-1"
        self.md = os.path.join(self.tmp, "full.md")
        # 用一个只有"具体命名工艺 + 明确对象"的场景;
        # v1 会认为不充分 (无 concrete_method_signal), v2 应升级
        full_md = ("# 测试论文\n\n# 摘要\n"
                     "MOFs 材料因高比表面积在储能领域受到广泛关注。\n"
                     "\n# 1 引言\n"
                     "Chen 课题组采用稀溶液法在导电基底上原位生长有序的聚苯胺纳米阵列结构。\n")
        with open(self.md, "w", encoding="utf-8") as f:
            f.write(full_md)
        self.base = os.path.join(self.tmp, "per_paper")
        os.makedirs(self.base, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_run_one_paper_writes_v2_versions_to_manifest(self):
        """spec 二.1, 二.6: run_one_paper 走完整路径后, per_paper 输出目录里的
        input_manifest.json 必须记录 v2 验证器与 provenance 版本 —
        证明 run_one_paper 已挂入 v2 (而不是走了 v1 路径)."""
        def mock_llm(sys_prompt, user_prompt, model=None):
            import re
            match = re.search(r"(\w+_p\d+_s\d+)", user_prompt)
            sid = match.group(1) if match else ""
            return ({
                "own_methods": [],
                "referenced_methods": [{
                    "name": "Chen 课题组稀溶液法原位生长 PANI 阵列结构",
                    "proposed_method_type": "synthesis_process",
                    "problem_solved": "构建有序 PANI 阵列结构以提升超电容性能",
                    "key_components": ["PANI", "稀溶液法"],
                    "evidence_sentence_ids": [sid] if sid else [],
                    "citation_clue": "Chen 课题组",
                    "confidence_llm": "high",
                }],
            }, True, "", {"prompt_tokens": 100, "completion_tokens": 30,
                            "total_tokens": 130}, "{}")

        spec = fr.RunSpec(paper_id=self.pid,
                            canonical_title="MOFs 综述",
                            paper_type="review_article",
                            paper_context_status="confirmed")
        fr.run_one_paper(spec, self.md, mock_llm,
                             base_dir=self.base, write_output=True)
        d = fr.per_paper_dir(self.pid, self.base)
        with open(os.path.join(d, "input_manifest.json"), "r",
                    encoding="utf-8") as f:
            m = json.load(f)
        self.assertEqual(m["evidence_validation_version"],
                          ev2.EVIDENCE_VALIDATION_VERSION)
        self.assertEqual(m["provenance_version"], pv2.PROVENANCE_VERSION)
        self.assertEqual(m["stage_a_full_version"], fr.STAGE_A_FULL_VERSION)

    def test_run_one_paper_attaches_v2_provenance_fields(self):
        """spec 二.2: provenance_v2 抽 author 从 method_name 兜底."""
        def mock_llm(sys_prompt, user_prompt, model=None):
            import re
            match = re.search(r"(introduction_p\d+_s\d+)", user_prompt)
            sid = match.group(1) if match else "introduction_p1_s1"
            return ({
                "own_methods": [],
                "referenced_methods": [{
                    "name": "Chen 课题组稀溶液法原位生长 PANI 阵列结构",
                    "proposed_method_type": "synthesis_process",
                    "problem_solved": "PANI 阵列结构",
                    "key_components": ["PANI"],
                    "evidence_sentence_ids": [sid],
                    "citation_clue": "",   # 空; v2 应从 name 兜底
                    "confidence_llm": "medium",
                }],
            }, True, "", {"prompt_tokens": 100, "completion_tokens": 20,
                            "total_tokens": 120}, "{}")

        spec = fr.RunSpec(paper_id=self.pid, paper_type="review_article")
        result = fr.run_one_paper(spec, self.md, mock_llm,
                                      base_dir=self.base)
        # 所有 methods 里应有 "Chen" 作者被兜底抽出
        all_methods = (result["methods_accepted"]
                        + result["methods_candidate"]
                        + result["methods_rejected"])
        chen = [m for m in all_methods if "Chen" in m.get("name", "")]
        self.assertEqual(len(chen), 1)
        self.assertIn(chen[0]["cited_author"], ("Chen", "Chen 课题组", "陈"),
                        msg=f"expected Chen-ish author, got {chen[0]['cited_author']!r}")
        # spec 七: 年份严格空
        self.assertEqual(chen[0]["cited_year"], "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
