"""Stage A v2.1 单测: 放宽后的充分性判定 + 章节位置 + citation 兜底."""
from __future__ import annotations

import os
import sys
import unittest

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
V2_DIR = os.path.dirname(THIS_DIR)
SRC_GRAPH_RAG_DIR = os.path.dirname(V2_DIR)
if SRC_GRAPH_RAG_DIR not in sys.path:
    sys.path.insert(0, SRC_GRAPH_RAG_DIR)

from method_evolution_v2.stage_a import evidence_validation_v2 as ev2
from method_evolution_v2.stage_a import provenance_v2 as pv2


class TestSufficiencyV2Upgrades(unittest.TestCase):
    """spec 六 明列的"预期倾向可升级 accepted"的方法."""

    def test_tio2_md_simulation_upgrades(self):
        """预期: TiO2 分子动力学模拟应升 accepted."""
        r = ev2.check_evidence_sufficiency_v2(
            "本文采用分子动力学方法模拟 TiO2 纳米颗粒烧结行为，探讨温度对颗粒结合的影响。",
            method_name="分子动力学模拟研究 TiO2 纳米颗粒烧结行为",
            kind="own",
        )
        self.assertTrue(r["sufficient"], f"got reason={r['reason']}")

    def test_ammonia_control_particle_size_upgrades(self):
        """预期: 氨水流速调控四氧化三锰粒径 应升 accepted."""
        r = ev2.check_evidence_sufficiency_v2(
            "通过调节氨水的滴加流速控制反应界面, 从而实现对四氧化三锰粒径的调控。",
            method_name="通过氨水流速调控四氧化三锰粒径的方法",
            kind="own",
        )
        self.assertTrue(r["sufficient"], f"got reason={r['reason']}")

    def test_dilute_solution_pani_upgrades(self):
        """预期: 稀溶液法原位生长 PANI 阵列 应升 accepted."""
        r = ev2.check_evidence_sufficiency_v2(
            "Chen 课题组采用稀溶液法在导电基底上原位生长有序的聚苯胺纳米阵列结构。",
            method_name="Chen 课题组稀溶液法原位生长 PANI 阵列结构",
            kind="referenced",
        )
        self.assertTrue(r["sufficient"], f"got reason={r['reason']}")

    def test_stepwise_hydrothermal_znwo3_upgrades(self):
        """预期: 分步水热构建 ZnO/WO3 异质结 应升 accepted."""
        r = ev2.check_evidence_sufficiency_v2(
            "作者采用分步水热法先制备 ZnO 纳米棒再引入 WO3 前驱体形成异质结光催化剂。",
            method_name="分步水热法构建 ZnO/WO3 异质结光催化剂",
            kind="own",
        )
        self.assertTrue(r["sufficient"], f"got reason={r['reason']}")


class TestSufficiencyV2StillExcludes(unittest.TestCase):
    """spec 六 明列的"应保持 candidate/rejected"的方法."""

    def test_rheometer_characterization_stays_insufficient(self):
        """毛细管流变仪/旋转流变仪 属表征, 保持不足."""
        r = ev2.check_evidence_sufficiency_v2(
            "利用毛细管流变仪和旋转流变仪测量聚丙烯熔体的流变特性。",
            method_name="毛细管流变仪和旋转流变仪研究聚丙烯熔体流变特性",
            kind="own",
        )
        self.assertFalse(r["sufficient"], f"unexpected sufficient: {r}")
        self.assertEqual(r["reason"], "characterization_instrument_only")

    def test_mof_naming_convention_rejected(self):
        """MOF 命名法 属分类/命名, 保持不足."""
        r = ev2.check_evidence_sufficiency_v2(
            "Yaghi 等提出的金属有机框架命名法奠定了 MOF 研究基础。",
            method_name="Yaghi 等金属有机框架命名法",
            kind="referenced",
        )
        self.assertFalse(r["sufficient"])
        self.assertEqual(r["reason"], "naming_or_classification")

    def test_hydrophobic_treatment_no_object_stays_insufficient(self):
        """'疏水化处理' 无具体对象/技术内容 → 不足."""
        r = ev2.check_evidence_sufficiency_v2(
            "有机配体经过疏水化处理可以提高 MOFs 的水稳定性。",
            method_name="疏水化处理提高 MOFs 水稳定性",
            kind="referenced",
        )
        # "水稳定性" 是性能, 也无 tier2 动作词; 应算 object_without_action 或 no_signal
        self.assertFalse(r["sufficient"], f"unexpected sufficient: {r}")

    def test_vague_only_stays_insufficient(self):
        """'具有前景/受到关注' 保持不足."""
        r = ev2.check_evidence_sufficiency_v2(
            "MOFs 材料因高比表面积在储能领域受到广泛关注具有前景。",
            method_name="MOFs 电极材料",
            kind="own",
        )
        self.assertFalse(r["sufficient"])

    def test_pure_material_name_rejected(self):
        r = ev2.check_evidence_sufficiency_v2(
            "本文使用 LFP 作为正极材料。",
            method_name="LFP",
            kind="own",
        )
        self.assertFalse(r["sufficient"])
        self.assertEqual(r["reason"], "pure_material_name")

    def test_only_study_verb_stays_insufficient(self):
        """只有'研究/分析' + 对象, 无制备/构建/仿真类动词 → 不足."""
        r = ev2.check_evidence_sufficiency_v2(
            "本文研究电池管理系统的性能表现。",
            method_name="研究电池管理系统性能",
            kind="own",
        )
        self.assertFalse(r["sufficient"])

    def test_only_citation_number_rejected(self):
        r = ev2.check_evidence_sufficiency_v2(
            "[15]", method_name="Smith 等 [15]",
            kind="referenced",
        )
        self.assertFalse(r["sufficient"])
        self.assertEqual(r["reason"], "only_citation_numbers")


class TestSectionContextV2(unittest.TestCase):

    def test_own_from_core_section_ok(self):
        ok, note = ev2.check_section_context_v2(
            "own", {"methods"}, "本文用 CFD 模型仿真管路系统")
        self.assertTrue(ok)
        self.assertEqual(note, "core_section_hit")

    def test_own_from_abstract_with_declarative_ok(self):
        """spec 三: abstract 里有 '本文提出' 声明, 允许 accepted."""
        ok, note = ev2.check_section_context_v2(
            "own", {"abstract"},
            "本文提出了一种基于 CFD 的仿真模型...")
        self.assertTrue(ok)
        self.assertIn("declarative", note)

    def test_own_from_intro_without_declarative_not_ok(self):
        """intro-only 且无 '本文提出' → 不 OK."""
        ok, note = ev2.check_section_context_v2(
            "own", {"introduction"},
            "很多研究者对此开展了工作。")
        self.assertFalse(ok)

    def test_referenced_from_introduction_ok(self):
        ok, _ = ev2.check_section_context_v2(
            "referenced", {"introduction"},
            "Smith 等[4]采用溶胶-凝胶法制备了...")
        self.assertTrue(ok)

    def test_referenced_from_other_sections_ok(self):
        ok, _ = ev2.check_section_context_v2(
            "referenced", {"other_sections"}, "irrelevant")
        self.assertTrue(ok)


class TestCitationParseWithNameFallback(unittest.TestCase):

    def test_fallback_extracts_author_from_name(self):
        r = pv2.parse_citation_clue_with_name_fallback(
            citation_clue="",
            method_name="Sarkar 等调控尖晶石结构 A 位组成法",
        )
        self.assertEqual(r["author"], "Sarkar")

    def test_fallback_extracts_ref_number_from_name(self):
        r = pv2.parse_citation_clue_with_name_fallback(
            citation_clue="",
            method_name="Sarkar 等[4]调控尖晶石结构 A 位组成法",
        )
        self.assertEqual(r["reference_number"], "4")

    def test_fallback_extracts_zh_author(self):
        r = pv2.parse_citation_clue_with_name_fallback(
            citation_clue="",
            method_name="刘昌会等尿素/氯化胆碱低共熔溶剂基纳米流体制备方法",
        )
        self.assertEqual(r["author"], "刘昌会等")

    def test_never_guesses_year_from_name(self):
        """spec 七: 年份**绝不**从 name 猜, 也不从当前论文年份代入."""
        r = pv2.parse_citation_clue_with_name_fallback(
            citation_clue="",
            method_name="Sarkar 等[4]调控尖晶石结构 A 位组成法",
        )
        self.assertEqual(r["year"], "")

    def test_year_from_clue_preserved(self):
        r = pv2.parse_citation_clue_with_name_fallback(
            citation_clue="Smith 2018 [15]",
            method_name="",
        )
        self.assertEqual(r["year"], "2018")

    def test_excludes_chemical_formula_as_author(self):
        """化学式类短词 (LFP/NCM) 不能被当作作者."""
        r = pv2.parse_citation_clue_with_name_fallback(
            citation_clue="",
            method_name="LFP 正极材料",
        )
        self.assertEqual(r["author"], "")


class TestV2ResolverIntegration(unittest.TestCase):
    """v2 resolver 端到端 (mock sentence_index) 验证放宽是否生效."""

    def _make_idx(self, pairs):
        idx = {}
        cur = 0
        for sid, text in pairs:
            idx[sid] = {
                "sentence_id": sid, "paper_id": "p",
                "section_type": sid.rsplit("_p", 1)[0] if "_p" in sid else "methods",
                "section_name": "sec",
                "para_id": sid.rsplit("_s", 1)[0] if "_s" in sid else "p0",
                "sentence_text": text,
                "char_start": cur, "char_end": cur + len(text),
            }
            cur += len(text)
        return idx

    def test_intro_with_bewnwen_declarative_accepted(self):
        """own from introduction + '本文提出' → accepted."""
        idx = self._make_idx([
            ("introduction_p1_s1",
             "本文提出了一种基于分步水热法构建 ZnO/WO3 异质结光催化剂。"),
        ])
        raw = {
            "name": "分步水热法构建 ZnO/WO3 异质结光催化剂",
            "evidence_sentence_ids": ["introduction_p1_s1"],
        }
        r = ev2.resolve_method_by_sentence_ids_v2(raw, idx, kind="own")
        self.assertEqual(r["validation_status"], "accepted",
                          msg=f"reasons={r['rejected_reason']}")

    def test_named_process_no_object_upgrades(self):
        """spec 一 case 1: 命名工艺 + 明确对象."""
        idx = self._make_idx([
            ("methods_p3_s1",
             "采用溶液燃烧法制备了钙钛矿型高熵氧化物。"),
        ])
        raw = {
            "name": "溶液燃烧法制备钙钛矿型高熵氧化物",
            "evidence_sentence_ids": ["methods_p3_s1"],
        }
        r = ev2.resolve_method_by_sentence_ids_v2(raw, idx, kind="own")
        self.assertEqual(r["validation_status"], "accepted")

    def test_action_and_object_no_named_process_still_accepted(self):
        """spec 一 case 2: 调控动作 + 明确目标."""
        idx = self._make_idx([
            ("methods_p3_s1",
             "通过调控氨水流速控制四氧化三锰的粒径分布。"),
        ])
        raw = {
            "name": "氨水流速调控四氧化三锰粒径的方法",
            "evidence_sentence_ids": ["methods_p3_s1"],
        }
        r = ev2.resolve_method_by_sentence_ids_v2(raw, idx, kind="own")
        self.assertEqual(r["validation_status"], "accepted")

    def test_pure_material_still_rejected_at_top(self):
        idx = self._make_idx([
            ("methods_p3_s1", "本文以 LFP 作为正极材料。"),
        ])
        raw = {"name": "LFP", "evidence_sentence_ids": ["methods_p3_s1"]}
        r = ev2.resolve_method_by_sentence_ids_v2(raw, idx, kind="own")
        # rejected (pure_material_name)
        self.assertEqual(r["validation_status"], "candidate")   # v2 未硬拒, 由 sufficiency 打 candidate

    def test_naming_convention_rejected(self):
        idx = self._make_idx([
            ("methods_p3_s1", "Yaghi 等提出金属有机框架命名法。"),
        ])
        raw = {
            "name": "Yaghi 等金属有机框架命名法",
            "evidence_sentence_ids": ["methods_p3_s1"],
        }
        r = ev2.resolve_method_by_sentence_ids_v2(raw, idx, kind="referenced")
        self.assertEqual(r["validation_status"], "candidate",
                          msg=f"reasons={r['rejected_reason']}")
        # 明确出现 naming_or_classification
        self.assertIn("naming_or_classification", r["rejected_reason"])

    def test_referenced_with_ref_num_and_action_ok(self):
        idx = self._make_idx([
            ("introduction_p1_s1",
             "Smith 等[4]采用溶胶-凝胶法制备了钙钛矿电极。"),
        ])
        raw = {
            "name": "Smith 等溶胶-凝胶法制备钙钛矿电极",
            "citation_clue": "Smith 等[4]",
            "evidence_sentence_ids": ["introduction_p1_s1"],
        }
        r = ev2.resolve_method_by_sentence_ids_v2(raw, idx, kind="referenced")
        self.assertEqual(r["validation_status"], "accepted",
                          msg=f"reasons={r['rejected_reason']}")

    def test_missing_evidence_ids_rejected(self):
        idx = self._make_idx([("methods_p1_s1", "actual text")])
        raw = {"name": "some method",
               "evidence_sentence_ids": ["fake_p9_s9"]}
        r = ev2.resolve_method_by_sentence_ids_v2(raw, idx, kind="own")
        self.assertEqual(r["validation_status"], "rejected")


if __name__ == "__main__":
    unittest.main(verbosity=2)
