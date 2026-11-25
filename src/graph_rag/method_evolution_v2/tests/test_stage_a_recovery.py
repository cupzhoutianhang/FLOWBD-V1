"""Stage A recovery pipeline tests (spec 一 + 六 + 七).

覆盖:
  - method_role 5 分类 (含优先级 modeling > technology > analysis > research)
  - 专利名 normalize 拆机构 (spec 六)
  - 孤立通用方法名降级 (spec 七)
  - recovery_runner 单篇执行 (mock LLM, 无 API)
  - recovery 输出到独立目录, 不覆盖 stage_a_full_v1 产物
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

from method_evolution_v2.stage_a import method_role as mrole
from method_evolution_v2.stage_a import name_normalization as nn
from method_evolution_v2.stage_a import recovery_runner as rr
from method_evolution_v2.stage_a import full_runner as fr


# ============================================================
# method_role
# ============================================================

class TestMethodRole(unittest.TestCase):

    def test_modeling_wins_when_cfd_in_name(self):
        m = {"name": "储能电池包三维流固耦合 CFD 液冷模型",
              "problem_solved": "评估液冷板对电池包热特性影响"}
        self.assertEqual(mrole.assign_method_role(m), "modeling_method")

    def test_modeling_needs_build_verb_or_strong_kw(self):
        """spec 二: 只有强关键词 (CFD/有限元/分子动力学) 或 建模动作+目标
        才判 modeling. '仿真模型' 单独不够."""
        # 无 build_verb + 无强关键词 → 不归 modeling
        m = {"name": "储能电池包液冷装置仿真模型",
              "problem_solved": "热特性数值模拟"}
        self.assertNotEqual(mrole.assign_method_role(m), "modeling_method")

    def test_modeling_triad_pass_with_build_verb(self):
        """含 build_verb + target 一起 → modeling."""
        m = {"name": "构建储能电池包液冷装置仿真模型",
              "problem_solved": "评估热特性"}
        self.assertEqual(mrole.assign_method_role(m), "modeling_method")

    def test_modeling_via_strong_keyword(self):
        m = {"name": "TiO2 纳米颗粒烧结机制",
              "problem_solved": "研究烧结路径"}
        m["evidence_text"] = "本文采用分子动力学模拟研究烧结."
        self.assertEqual(mrole.assign_method_role(m), "modeling_method")

    def test_isolated_fen_xi_mo_xing_stays_unclear(self):
        """spec 二: 孤立 '分析模型' / '模型分析' 保持 unclear/candidate."""
        m = {"name": "三角转子膨胀机两级串联分析模型",
              "problem_solved": "分析工作机理"}
        # 无 build_verb, 无强关键词, "分析模型" 不作为无条件关键词
        # 名字里含"膨胀机" (装置词) → technology_solution
        # 只要不归 modeling 就通过 spec 二
        self.assertNotEqual(mrole.assign_method_role(m), "modeling_method")

    def test_technology_synthesis(self):
        m = {"name": "溶胶-凝胶法制备 MnO2 纳米片",
              "problem_solved": "制备高比容量电极材料"}
        self.assertEqual(mrole.assign_method_role(m), "technology_solution")

    def test_technology_device(self):
        m = {"name": "两级串联三角转子膨胀机试验台",
              "problem_solved": "构建自建装置研究串联特性"}
        self.assertEqual(mrole.assign_method_role(m), "technology_solution")

    def test_analysis_response_surface(self):
        m = {"name": "响应面法参数优化",
              "problem_solved": "优化压敏胶配方"}
        self.assertEqual(mrole.assign_method_role(m), "analysis_method")

    def test_analysis_lca(self):
        m = {"name": "全生命周期评价方法",
              "problem_solved": "评价能耗与碳足迹"}
        self.assertEqual(mrole.assign_method_role(m), "analysis_method")

    def test_research_method_workload_scan(self):
        m = {"name": "变工况温度扫描测试流程",
              "problem_solved": "识别系统稳定工作区间"}
        self.assertEqual(mrole.assign_method_role(m), "research_method")

    def test_unclear_when_no_signal(self):
        m = {"name": "本文所提方法",
              "problem_solved": "解决某些问题"}
        self.assertEqual(mrole.assign_method_role(m), "unclear")

    def test_attach_writes_field_and_version(self):
        m = {"name": "有限元电池热管理仿真", "problem_solved": ""}
        mrole.attach_method_role(m)
        self.assertEqual(m["method_role"], "modeling_method")
        self.assertEqual(m["method_role_version"],
                          mrole.METHOD_ROLE_VERSION)


# ============================================================
# name_normalization: 专利名规范化 (spec 六)
# ============================================================

class TestPatentNameNormalization(unittest.TestCase):

    def test_university_prefix_split(self):
        raw = "厦门大学玻璃纤维增强二氧化硅气凝胶复合材料制备法"
        org, name = nn.normalize_patent_method_name(raw)
        self.assertEqual(org, "厦门大学")
        self.assertEqual(name, "玻璃纤维增强二氧化硅气凝胶复合材料制备法")

    def test_company_prefix_split(self):
        raw = "气凝胶合成物有限公司金属颗粒分散气凝胶表面形成法"
        org, name = nn.normalize_patent_method_name(raw)
        self.assertEqual(org, "气凝胶合成物有限公司")
        self.assertEqual(name, "金属颗粒分散气凝胶表面形成法")

    def test_institute_prefix_split(self):
        raw = "中国科学院化学研究所SiO2纳米颗粒制备法"
        org, name = nn.normalize_patent_method_name(raw)
        self.assertTrue("研究所" in org)
        # 保留技术内容
        self.assertIn("SiO2", name)

    def test_no_org_returns_empty(self):
        raw = "溶胶-凝胶法制备钙钛矿高熵氧化物"
        org, name = nn.normalize_patent_method_name(raw)
        self.assertEqual(org, "")
        self.assertEqual(name, raw)

    def test_blacklist_prefix(self):
        raw = "本文自建单级压缩三角转子膨胀机试验台"
        org, name = nn.normalize_patent_method_name(raw)
        self.assertEqual(org, "")   # "本文" 不算机构
        self.assertEqual(name, raw)

    def test_attach_writes_raw_and_normalized(self):
        m = {"name": "厦门大学玻璃纤维增强二氧化硅气凝胶复合材料制备法"}
        nn.attach_name_normalization(m)
        self.assertEqual(m["raw_method_name"],
                          "厦门大学玻璃纤维增强二氧化硅气凝胶复合材料制备法")
        self.assertEqual(m["source_organization"], "厦门大学")
        self.assertEqual(m["normalized_method_name"],
                          "玻璃纤维增强二氧化硅气凝胶复合材料制备法")

    def test_split_preserves_technical_content(self):
        """spec 六: 不删除方法技术内容."""
        raw = "厦门大学玻璃纤维增强二氧化硅气凝胶复合材料制备法"
        _, name = nn.normalize_patent_method_name(raw)
        for kw in ("玻璃纤维", "二氧化硅", "气凝胶", "复合材料", "制备法"):
            self.assertIn(kw, name)

    def test_split_only_if_residual_has_content(self):
        """spec 六: 拆掉后必须仍有实质技术内容 (至少 4 字符)."""
        # 假想: "厦门大学法" 拆后只剩 "法" (1 字) → 不拆
        raw = "厦门大学法"
        org, name = nn.normalize_patent_method_name(raw)
        self.assertEqual(org, "")
        self.assertEqual(name, raw)


# ============================================================
# name_normalization: 孤立通用方法名 (spec 七)
# ============================================================

class TestBareGenericDemotion(unittest.TestCase):

    def test_bare_generic_names_detected(self):
        for n in ("水热合成法", "水热法", "溶胶-凝胶法", "模板法",
                    "热处理法", "热处理", "共沉淀法"):
            self.assertTrue(nn.is_bare_generic_method_name(n),
                             f"{n} 应被识别为孤立通用名")

    def test_named_process_with_object_not_bare(self):
        self.assertFalse(nn.is_bare_generic_method_name(
            "水热法制备MnO2纳米片"))

    def test_concrete_signal_detection(self):
        self.assertTrue(nn.has_concrete_signal("MnO2 纳米片"))
        self.assertTrue(nn.has_concrete_signal("钙钛矿电极"))
        self.assertFalse(nn.has_concrete_signal("提高性能"))

    def test_should_demote_true(self):
        m = {"name": "水热合成法",
              "validation_status": "accepted",
              "evidence_text": "本工作简要介绍水热合成法.",
              "problem_solved": "综述常见制备工艺."}
        self.assertTrue(nn.should_demote_bare_generic(m))

    def test_should_not_demote_when_object_in_evidence(self):
        m = {"name": "水热合成法",
              "validation_status": "accepted",
              "evidence_text": "采用水热合成法制备 MnO2 纳米片.",
              "problem_solved": "."}
        self.assertFalse(nn.should_demote_bare_generic(m))

    def test_should_not_demote_when_object_in_name(self):
        m = {"name": "水热法制备MnO2纳米片",
              "validation_status": "accepted",
              "evidence_text": "本文水热处理.",
              "problem_solved": "."}
        self.assertFalse(nn.should_demote_bare_generic(m))

    def test_demote_bare_generic_batch(self):
        methods = [
            {"name": "水热合成法", "validation_status": "accepted",
              "evidence_text": "简述工艺.", "problem_solved": "."},
            {"name": "水热法制备MnO2纳米片", "validation_status": "accepted",
              "evidence_text": "制备电极.", "problem_solved": "."},
            {"name": "溶胶-凝胶法", "validation_status": "candidate",
              "evidence_text": "泛描述.", "problem_solved": "."},   # 已是 cand, 不动
        ]
        new_methods, demoted = nn.demote_bare_generic_methods(methods)
        self.assertEqual(demoted, 1)
        self.assertEqual(new_methods[0]["validation_status"], "candidate")
        self.assertEqual(new_methods[1]["validation_status"], "accepted")
        # cand → 保持 cand (不动)
        self.assertEqual(new_methods[2]["validation_status"], "candidate")

    def test_demote_not_delete(self):
        """spec 七: 孤立通用方法降为 candidate, 不删除."""
        methods = [{"name": "水热合成法", "validation_status": "accepted",
                     "evidence_text": ".", "problem_solved": "."}]
        new_methods, _ = nn.demote_bare_generic_methods(methods)
        self.assertEqual(len(new_methods), 1)
        self.assertEqual(new_methods[0]["name"], "水热合成法")


# ============================================================
# recovery_runner: candidate finder
# ============================================================

class TestFindCandidates(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.per_paper = os.path.join(self.tmp, "per_paper")
        os.makedirs(self.per_paper, exist_ok=True)
        self.batches_csv = os.path.join(self.tmp, "batches.csv")
        import csv
        with open(self.batches_csv, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["paper_id", "batch_num",
                                                 "position_in_batch",
                                                 "paper_id_hash"])
            w.writeheader()
            for i, (pid, bn) in enumerate([
                ("研究1_有 own", "1"), ("研究2_没 own", "1"),
                ("综述1", "1"), ("研究3_没 own", "2"),
                ("研究4_未完成", "3"),
            ]):
                w.writerow({"paper_id": pid, "batch_num": bn,
                            "position_in_batch": i + 1,
                            "paper_id_hash": fr.paper_id_to_dir_name(pid)})

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _seed(self, pid, accepted_list):
        d = fr.per_paper_dir(pid, self.per_paper)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "methods_accepted.json"),
                    "w", encoding="utf-8") as f:
            json.dump(accepted_list, f)

    def test_only_research_with_zero_own_selected(self):
        # 研究1: 有 own
        self._seed("研究1_有 own",
                    [{"kind": "own", "name": "X"},
                     {"kind": "referenced", "name": "Y"}])
        # 研究2: 只有 referenced (own=0)
        self._seed("研究2_没 own", [{"kind": "referenced", "name": "Y"}])
        # 综述1: 有 own — 但类型 review, 不选
        self._seed("综述1", [{"kind": "own", "name": "Z"}])
        # 研究3: 空 accepted
        self._seed("研究3_没 own", [])
        # 研究4: batch 3, 不选
        self._seed("研究4_未完成", [])

        ptypes = {
            "研究1_有 own": "research_article",
            "研究2_没 own": "research_article",
            "综述1": "review_article",
            "研究3_没 own": "research_article",
            "研究4_未完成": "research_article",
        }
        cands = rr.find_recovery_candidates(
            ptypes, self.batches_csv, self.per_paper,
            allowed_batches=("1", "2"))
        self.assertEqual(set(cands), {"研究2_没 own", "研究3_没 own"})


# ============================================================
# recovery_runner: run one paper with mock LLM
# ============================================================

class TestRunRecoveryOnePaper(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.pid = "test-recovery-paper"
        self.md = os.path.join(self.tmp, "full.md")
        with open(self.md, "w", encoding="utf-8") as f:
            f.write("# 测试论文\n\n"
                     "# 摘要\n本文自建单级压缩三角转子膨胀机串联试验台。\n"
                     "\n# 1 实验装置\n"
                     "本文自建了单级压缩三角转子膨胀机串联试验台。\n"
                     "\n# 2 结果\n试验结果显示串联比单级效率高。\n")
        self.recovery_base = os.path.join(self.tmp, "recovery")
        os.makedirs(self.recovery_base, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_recovery_zero_api_via_mock(self):
        calls = []
        def mock(sys_prompt, user_prompt, model=None):
            import re
            m = re.search(r"(\w+_p\d+_s\d+)", user_prompt)
            sid = m.group(1) if m else ""
            calls.append(1)
            return ({
                "own_methods": [{
                    "name": "两级串联三角转子膨胀机自建试验台",
                    "proposed_method_type": "device_design",
                    "problem_solved": "研究两级串联三角转子膨胀机的运行特性",
                    "key_components": ["两级串联膨胀机", "蒸发器", "冷凝器"],
                    "evidence_sentence_ids": [sid] if sid else [],
                    "citation_clue": "",
                    "confidence_llm": "high",
                }],
                "referenced_methods": [],
            }, True, "", {"prompt_tokens": 200, "completion_tokens": 50,
                            "total_tokens": 250}, "{}")

        spec = fr.RunSpec(paper_id=self.pid,
                            canonical_title="三角转子膨胀机串联",
                            paper_type="research_article",
                            paper_context_status="confirmed")
        result = rr.run_recovery_one_paper(spec, self.md, mock,
                                                recovery_base_dir=self.recovery_base)
        self.assertEqual(len(calls), 1)   # exactly one API call
        self.assertEqual(result["call_count"], 1)
        # 至少 1 条方法
        total = (len(result["methods_accepted"])
                    + len(result["methods_candidate"])
                    + len(result["methods_rejected"]))
        self.assertGreaterEqual(total, 1)

    def test_recovery_writes_to_separate_dir(self):
        def mock(sys_prompt, user_prompt, model=None):
            return ({"own_methods": [], "referenced_methods": []},
                     True, "", {"prompt_tokens": 100, "completion_tokens": 10,
                                 "total_tokens": 110}, "{}")
        spec = fr.RunSpec(paper_id=self.pid, paper_type="research_article")
        rr.run_recovery_one_paper(spec, self.md, mock,
                                       recovery_base_dir=self.recovery_base)
        d = rr.recovery_per_paper_dir(self.pid, self.recovery_base)
        for fname in ("recovery_manifest.json",
                       "recovery_raw_response.json",
                       "recovery_methods_accepted.json",
                       "recovery_report.json",
                       "sentence_index.json"):
            self.assertTrue(os.path.isfile(os.path.join(d, fname)),
                             f"missing: {fname}")
        # 不写主 methods_accepted.json (不干扰 full_v1 目录)
        self.assertFalse(os.path.isfile(os.path.join(d, "methods_accepted.json")))
        self.assertFalse(os.path.isfile(os.path.join(d, "raw_response.json")))

    def test_recovery_manifest_records_all_versions(self):
        def mock(sys_prompt, user_prompt, model=None):
            return ({"own_methods": [], "referenced_methods": []},
                     True, "", {"prompt_tokens": 100, "completion_tokens": 10,
                                 "total_tokens": 110}, "{}")
        spec = fr.RunSpec(paper_id=self.pid, paper_type="research_article")
        rr.run_recovery_one_paper(spec, self.md, mock,
                                       recovery_base_dir=self.recovery_base)
        d = rr.recovery_per_paper_dir(self.pid, self.recovery_base)
        with open(os.path.join(d, "recovery_manifest.json"),
                    "r", encoding="utf-8") as f:
            m = json.load(f)
        for k in ("recovery_prompt_version", "recovery_engine_version",
                    "evidence_validation_version", "provenance_version",
                    "method_role_version", "name_normalization_version"):
            self.assertIn(k, m)

    def test_recovery_no_retry_by_default(self):
        """spec 二: 每篇最多一次, 不循环重试."""
        attempts = []
        def mock(sys_prompt, user_prompt, model=None):
            attempts.append(1)
            # 返回坏 JSON — 若允许 retry, 会调 2 次
            return ({}, False, "bad json",
                     {"prompt_tokens": 100, "completion_tokens": 10,
                       "total_tokens": 110}, "not-json")
        spec = fr.RunSpec(paper_id=self.pid, paper_type="research_article")
        rr.run_recovery_one_paper(spec, self.md, mock,
                                       recovery_base_dir=self.recovery_base,
                                       allow_retry=False)
        self.assertEqual(len(attempts), 1,
                          "recovery should not retry on JSON failure")

    def test_recovery_applies_method_role(self):
        def mock(sys_prompt, user_prompt, model=None):
            import re
            m = re.search(r"(\w+_p\d+_s\d+)", user_prompt)
            sid = m.group(1) if m else ""
            return ({
                "own_methods": [{
                    "name": "两级串联三角转子膨胀机自建试验台",
                    "proposed_method_type": "device_design",
                    "problem_solved": "研究串联特性, 构建自建装置",
                    "key_components": ["蒸发器"],
                    "evidence_sentence_ids": [sid] if sid else [],
                    "citation_clue": "",
                    "confidence_llm": "high",
                }],
                "referenced_methods": [],
            }, True, "", {"prompt_tokens": 100, "completion_tokens": 30,
                            "total_tokens": 130}, "{}")

        spec = fr.RunSpec(paper_id=self.pid, paper_type="research_article")
        result = rr.run_recovery_one_paper(spec, self.md, mock,
                                                recovery_base_dir=self.recovery_base)
        all_methods = (result["methods_accepted"]
                        + result["methods_candidate"]
                        + result["methods_rejected"])
        self.assertGreaterEqual(len(all_methods), 1)
        for m in all_methods:
            self.assertIn(m.get("method_role"),
                           ("technology_solution", "research_method",
                            "modeling_method", "analysis_method", "unclear"))


class TestPaperNeedsRecoveryAndMerge(unittest.TestCase):
    """spec 一: 触发条件 & merge 逻辑."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.pid = "merge-test-pid"
        self.base = os.path.join(self.tmp, "per_paper")
        os.makedirs(self.base, exist_ok=True)
        # seed a per_paper dir simulating a completed main call with 0 own accepted
        d = fr.per_paper_dir(self.pid, self.base)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "methods_accepted.json"),
                    "w", encoding="utf-8") as f:
            json.dump([{"kind": "referenced", "name": "X",
                         "validation_status": "accepted"}], f)
        with open(os.path.join(d, "methods_candidate.json"),
                    "w", encoding="utf-8") as f:
            json.dump([], f)
        with open(os.path.join(d, "methods_rejected.json"),
                    "w", encoding="utf-8") as f:
            json.dump([], f)
        with open(os.path.join(d, "input_manifest.json"),
                    "w", encoding="utf-8") as f:
            json.dump({"paper_id": self.pid,
                        "full_md_sha256": "x" * 64,
                        "prompt_version": "p",
                        "model": "m",
                        "section_parser_version": "1.0",
                        "stage_a_engine_version": "2.0",
                        "evidence_validation_version": "v2",
                        "provenance_version": "v2"}, f)
        with open(os.path.join(d, "validation_report.json"),
                    "w", encoding="utf-8") as f:
            json.dump({"paper_id": self.pid,
                        "n_accepted": 1}, f)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_paper_needs_recovery_true_for_research_zero_own(self):
        methods = [{"kind": "referenced", "name": "X"}]
        self.assertTrue(fr.paper_needs_recovery(
            "research_article", methods, manifest={}))

    def test_paper_needs_recovery_false_when_has_own(self):
        methods = [{"kind": "own", "name": "X"},
                    {"kind": "referenced", "name": "Y"}]
        self.assertFalse(fr.paper_needs_recovery(
            "research_article", methods, manifest={}))

    def test_paper_needs_recovery_false_when_not_research(self):
        methods = [{"kind": "referenced", "name": "X"}]
        self.assertFalse(fr.paper_needs_recovery(
            "review_article", methods, manifest={}))

    def test_paper_needs_recovery_false_when_recovery_used(self):
        methods = [{"kind": "referenced", "name": "X"}]
        self.assertFalse(fr.paper_needs_recovery(
            "research_article", methods,
            manifest={"recovery_used": True}))

    def test_merge_recovery_appends_and_marks(self):
        rec = {
            "methods_accepted": [{"kind": "own", "name": "REC1",
                                    "validation_status": "accepted"}],
            "methods_candidate": [{"kind": "own", "name": "REC2",
                                    "validation_status": "candidate"}],
            "methods_rejected": [],
            "own_methods_raw": [{"name": "REC1"}, {"name": "REC2"}],
            "call_count": 1,
            "usage_total": {"prompt_tokens": 100, "completion_tokens": 20,
                              "total_tokens": 120},
            "json_parse_ok": True, "json_parse_error": "",
            "llm_calls": [{"attempt": "recovery"}],
            "recovery_engine_version": "recovery_v1.0_2026-07-02",
            "recovery_prompt_version": "stage_a_recovery_v1.0_2026-07-02",
        }
        stats = fr.merge_recovery_into_paper(self.pid, rec, self.base)
        self.assertEqual(stats["n_accepted"], 2)   # 原 1 (ref X) + 1 (REC1)
        self.assertEqual(stats["n_candidate"], 1)  # REC2
        # 验证 recovery_source 标记写入
        d = fr.per_paper_dir(self.pid, self.base)
        with open(os.path.join(d, "methods_accepted.json"),
                    "r", encoding="utf-8") as f:
            acc = json.load(f)
        rec_acc = [m for m in acc if m.get("name") == "REC1"]
        self.assertEqual(len(rec_acc), 1)
        self.assertEqual(rec_acc[0]["recovery_source"], "stage_a_recovery_v1")

    def test_merge_recovery_updates_manifest(self):
        rec = {
            "methods_accepted": [], "methods_candidate": [],
            "methods_rejected": [], "own_methods_raw": [],
            "call_count": 1, "usage_total": {},
            "json_parse_ok": True, "json_parse_error": "",
            "llm_calls": [],
            "recovery_engine_version": "recovery_v1.0",
            "recovery_prompt_version": "prompt_recovery_v1.0",
        }
        fr.merge_recovery_into_paper(self.pid, rec, self.base)
        d = fr.per_paper_dir(self.pid, self.base)
        with open(os.path.join(d, "input_manifest.json"),
                    "r", encoding="utf-8") as f:
            m = json.load(f)
        self.assertTrue(m["recovery_used"])
        self.assertEqual(m["recovery_call_count"], 1)
        self.assertIn("recovery_run_at", m)

    def test_merge_recovery_does_not_touch_raw_response(self):
        """spec 一: 不覆盖主调用 raw_response."""
        d = fr.per_paper_dir(self.pid, self.base)
        with open(os.path.join(d, "raw_response.json"),
                    "w", encoding="utf-8") as f:
            json.dump({"main_raw": True}, f)
        import hashlib
        with open(os.path.join(d, "raw_response.json"), "rb") as f:
            before = hashlib.sha256(f.read()).hexdigest()

        rec = {
            "methods_accepted": [{"kind": "own", "name": "REC1"}],
            "methods_candidate": [], "methods_rejected": [],
            "own_methods_raw": [{"name": "REC1"}],
            "call_count": 1, "usage_total": {},
            "json_parse_ok": True, "json_parse_error": "",
            "llm_calls": [],
            "recovery_engine_version": "v",
            "recovery_prompt_version": "p",
        }
        fr.merge_recovery_into_paper(self.pid, rec, self.base)
        with open(os.path.join(d, "raw_response.json"), "rb") as f:
            after = hashlib.sha256(f.read()).hexdigest()
        self.assertEqual(before, after,
                          "raw_response.json 被改动了")
        # recovery raw 单独文件
        self.assertTrue(os.path.isfile(
            os.path.join(d, "recovery_raw_response.json")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
