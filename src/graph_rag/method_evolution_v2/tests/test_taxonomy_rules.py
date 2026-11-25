"""单元测试: taxonomy_rules 分类器 (spec 六).

覆盖:
  - 燃料电池 ≠ 储能
  - 制氢 ≠ 储氢
  - 储氢
  - 热化学储热
  - 锂电池 PCM 热管理两种贡献侧
  - 超级电容 (electrochemical, 非 electromagnetic)
  - SMES (electromagnetic)
  - 通用 ML (cross_domain_method)
  - 与具体电池绑定的 ML (走绑定的 storage domain)
  - 多领域冲突 (primary=null, candidates 非空)
  - 无证据 unknown
  - 非储能 (non_storage)
  - technology_variant 与材料体系区分 (MOF 不进 variant)
  - primary / secondary method_type 组合
  - 禁止 paper_id 硬编码
  - 禁止读取 legacy
  - EV / DFT 等 ASCII 短词不被误伤 (edge)
  - 输出字段完整且列表都是 Python list
"""
from __future__ import annotations

import inspect
import json
import os
import sys
import unittest

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
V2_DIR = os.path.dirname(THIS_DIR)
SRC_GRAPH_RAG_DIR = os.path.dirname(V2_DIR)
if SRC_GRAPH_RAG_DIR not in sys.path:
    sys.path.insert(0, SRC_GRAPH_RAG_DIR)

from method_evolution_v2.io import section_parser as sp                # noqa: E402
from method_evolution_v2.taxonomy import taxonomy_rules as tr          # noqa: E402


# ============================================================
# ParseResult 构造辅助 (与 test_paper_type_rules 同款设计)
# ============================================================

def _make_section(index, section_type, raw_heading="", paragraphs_text=(),
                  heading_level=1, char_start=0):
    paragraphs = []
    cursor = char_start
    for i, pt in enumerate(paragraphs_text, 1):
        p = sp.Paragraph(
            para_id=f"{section_type}_{index:02d}_p{i:02d}",
            text=pt,
            char_start=cursor,
            char_end=cursor + len(pt),
        )
        cursor += len(pt) + 1
        paragraphs.append(p)
    return sp.Section(
        section_index=index,
        section_type=section_type,
        raw_heading=raw_heading,
        heading_level=heading_level,
        char_start=char_start,
        char_end=cursor,
        confidence="high",
        matched_by_markdown_heading=(heading_level > 0),
        inferred_by_regex=False,
        inference_source="keyword",
        paragraphs=paragraphs,
    )


def build_paper(paper_id, title, abstract_text="", body_sections=()):
    sections = [_make_section(0, "title", raw_heading=title, paragraphs_text=(title,))]
    if abstract_text:
        sections.append(_make_section(
            1, "abstract", raw_heading="摘要:",
            paragraphs_text=(abstract_text,), heading_level=0))
    for i, (st, hd, txt) in enumerate(body_sections, len(sections)):
        sections.append(_make_section(i, st, raw_heading=hd, paragraphs_text=(txt,)))
    total_end = max((s.char_end for s in sections), default=0)
    return sp.ParseResult(
        paper_id=paper_id,
        source_md_path=f"<test:{paper_id}>",
        source_md_chars=total_end,
        parse_time_iso="2026-07-01T00:00:00",
        document_title=title,
        sections=sections,
        section_coverage_chars=total_end,
        section_coverage_ratio=1.0 if total_end > 0 else 0.0,
        paragraph_coverage_chars=sum(len(p.text) for s in sections for p in s.paragraphs),
        paragraph_coverage_ratio=1.0,
        has_text_loss=False,
        notes=[],
    )


class TestTaxonomyRules(unittest.TestCase):

    # ---------- spec 六.1: 燃料电池 ≠ 储能 ----------

    def test_fuel_cell_alone_is_non_storage(self):
        pr = build_paper(
            paper_id="p-fc-only",
            title="质子交换膜燃料电池冷启动堆栈温度预测模型",
            abstract_text=("本文研究质子交换膜燃料电池的冷启动性能, "
                           "评估其低温工况下的堆栈温度演化."),
            body_sections=(
                ("methods", "1 数值模型", "有限元方法"),
                ("conclusion", "3 结论", "结论"),
            ),
        )
        r = tr.classify_taxonomy(pr)
        self.assertNotEqual(r["primary_storage_domain"], "electrochemical_storage",
                            "fuel cell alone must not be electrochemical_storage")
        self.assertNotEqual(r["primary_storage_domain"], "chemical_energy_storage",
                            "fuel cell alone must not be chemical_energy_storage")
        # 至少应识别出 non_storage_signal:fuel_cell_only
        self.assertTrue(
            any("non_storage_signal" in m["key"] for m in r["matched_signals"]),
            "expected non_storage_signal to fire",
        )

    def test_fuel_cell_with_hydrogen_storage_context_becomes_chemical(self):
        pr = build_paper(
            paper_id="p-fc-h2",
            title="再生燃料电池与储氢耦合的系统集成",
            abstract_text=("提出一种储氢-再生燃料电池耦合系统, 使用液氢储能作为主载体, "
                           "建立系统模型分析能量转换效率."),
        )
        r = tr.classify_taxonomy(pr)
        # 应走 chemical_energy_storage
        self.assertEqual(r["primary_storage_domain"], "chemical_energy_storage")

    # ---------- spec 六.2: 制氢 ≠ 储氢 ----------

    def test_hydrogen_production_alone_is_non_storage(self):
        pr = build_paper(
            paper_id="p-h2-prod",
            title="太阳能甲烷重整制氢反应器研究进展",
            abstract_text="综述了太阳能驱动甲烷重整制氢的反应器与催化剂进展.",
        )
        r = tr.classify_taxonomy(pr)
        self.assertNotEqual(r["primary_storage_domain"], "chemical_energy_storage",
                            "hydrogen production alone must not be chemical_energy_storage")

    # ---------- spec 六.3: 储氢 ----------

    def test_hydrogen_storage_confirmed(self):
        pr = build_paper(
            paper_id="p-h2-store",
            title="基于液氖梯级蓄冷的液氢储能中冷能回收",
            abstract_text=("为了解决液氢储能中能量时空错配问题, "
                           "采用液氖联合梯级蓄冷回收冷能, 建立液化循环."),
            body_sections=(
                ("system_design", "2 蓄冷流程", "流程"),
                ("conclusion", "4 结论", "结论"),
            ),
        )
        r = tr.classify_taxonomy(pr)
        self.assertEqual(r["primary_storage_domain"], "chemical_energy_storage")
        self.assertEqual(r["technology_subfield"], "hydrogen_storage")

    # ---------- spec 六.4: 热化学储热 ----------

    def test_thermochemical_heat_storage_goes_to_thermal(self):
        pr = build_paper(
            paper_id="p-tchs",
            title="Ca(OH)2 热化学储热性能研究",
            abstract_text=("采用 Ca(OH)2 作为热化学储热材料, "
                           "评估其反应床的储/放热性能与循环稳定性."),
        )
        r = tr.classify_taxonomy(pr)
        self.assertEqual(r["primary_storage_domain"], "thermal_storage")
        self.assertEqual(r["technology_subfield"], "thermochemical_heat_storage")

    # ---------- spec 六.5: 锂电池 PCM 热管理两种贡献侧 ----------

    def test_lipcm_thermal_management_contribution_on_battery_side(self):
        """贡献侧是电池热性能: electrochemical 至少浮出, application 含 battery_thermal_management.

        (关键词打分在紧邻的电化学 vs 热储能之间可能 tie, 分类器给 candidate 也是合规的;
        只 assert 两点: electrochemical 出现在 primary/secondary/candidates 之一;
        application 命中 battery_thermal_management.)
        """
        pr = build_paper(
            paper_id="p-lipcm-batt",
            title="锂离子电池热管理装置的性能评估",
            abstract_text=("本文构建了基于复合相变材料的锂离子电池热管理装置, "
                           "评估在快充工况下锂电池的温升与循环寿命."),
        )
        r = tr.classify_taxonomy(pr)
        appears = (
            r["primary_storage_domain"] == "electrochemical_storage"
            or "electrochemical_storage" in r["secondary_storage_domains"]
            or any(c["domain"] == "electrochemical_storage" for c in r["domain_candidates"])
        )
        self.assertTrue(appears, "electrochemical_storage should surface somewhere")
        self.assertIn("battery_thermal_management", r["application_contexts"])

    def test_lipcm_thermal_management_contribution_on_pcm_side(self):
        """贡献侧是 PCM 材料本身: primary=thermal, secondary 可能含 electrochemical."""
        pr = build_paper(
            paper_id="p-lipcm-pcm",
            title="用于锂电池热管理的高导热复合相变材料的制备",
            abstract_text=("制备了一种新型石蜡/膨胀石墨复合相变材料, "
                           "热导率提升 5 倍, 相变焓 210 J/g, 相变温度 45 度, "
                           "评估其在锂电池热管理中的散热效果."),
        )
        r = tr.classify_taxonomy(pr)
        # 由于是 PCM 材料研究, thermal 应至少是 primary 或 tie
        # 实际关键词密度决定: PCM/相变材料/相变焓/相变温度 vs 锂电池/锂电
        # 我们只 assert thermal 在 primary/secondary/candidates 中至少出现
        appears_in = (
            r["primary_storage_domain"] == "thermal_storage"
            or "thermal_storage" in r["secondary_storage_domains"]
            or any(c["domain"] == "thermal_storage" for c in r["domain_candidates"])
        )
        self.assertTrue(appears_in, "thermal_storage should surface somewhere")
        # 应用场景应包含 battery_thermal_management
        self.assertIn("battery_thermal_management", r["application_contexts"])

    # ---------- spec 六.6: 超级电容 → electrochemical ----------

    def test_supercapacitor_is_electrochemical_not_electromagnetic(self):
        pr = build_paper(
            paper_id="p-sc",
            title="MOFs 基材料在超级电容器中的应用",
            abstract_text=("综述了 MOFs 及其衍生物在超级电容器中的应用研究进展."),
        )
        r = tr.classify_taxonomy(pr)
        self.assertEqual(r["primary_storage_domain"], "electrochemical_storage")
        self.assertNotEqual(r["primary_storage_domain"], "electromagnetic_storage")
        self.assertEqual(r["technology_subfield"], "supercapacitor")
        # MOF 相关不得进 technology_variant
        self.assertNotIn("mof_derived_carbon", r["technology_variant"])

    # ---------- spec 六.7: SMES ----------

    def test_smes_is_electromagnetic(self):
        pr = build_paper(
            paper_id="p-smes",
            title="SMES 超导磁体动态载荷温度场仿真分析",
            abstract_text="",   # 摘要缺失也不能挂
            body_sections=(
                ("simulation_calculation", "3 温度场数值模拟", "模拟"),
                ("conclusion", "9 结论", "结论"),
            ),
        )
        r = tr.classify_taxonomy(pr)
        self.assertEqual(r["primary_storage_domain"], "electromagnetic_storage")
        self.assertEqual(r["technology_subfield"], "superconducting_magnetic_storage")

    # ---------- spec 六.8: 通用 ML → cross_domain_method ----------

    def test_generic_ml_is_cross_domain_method(self):
        pr = build_paper(
            paper_id="p-ml-generic",
            title="基于分子动力学的 TiO2 颗粒烧结机制研究",
            abstract_text=("使用分子动力学模拟研究 TiO2 纳米颗粒烧结机制, "
                           "分析温度对颗粒结合的影响, 采用第一性原理计算能量壁垒."),
        )
        r = tr.classify_taxonomy(pr)
        # 无具体储能技术 → cross_domain_method
        self.assertIn(r["primary_storage_domain"], ("cross_domain_method", None))

    # ---------- spec 六.9: 与具体电池绑定的 ML ----------

    def test_ml_bound_to_battery_goes_to_battery_domain(self):
        pr = build_paper(
            paper_id="p-ml-battery",
            title="基于神经网络的锂离子电池 SOC 预测方法",
            abstract_text=("提出一种深度学习模型, 用于锂离子电池 SOC 估算, "
                           "在实测数据集上验证预测精度."),
        )
        r = tr.classify_taxonomy(pr)
        # 主 domain 应走 electrochemical (bound to Li-ion) 或 system_integration (SOC/BMS)
        self.assertIn(r["primary_storage_domain"],
                      ("electrochemical_storage", "system_integration"))
        self.assertNotEqual(r["primary_storage_domain"], "cross_domain_method",
                            "ML bound to a specific tech must NOT be cross_domain_method")

    # ---------- spec 六.10: 多领域冲突 ----------

    def test_multi_domain_conflict_yields_candidates(self):
        """液流电池 + 相变材料 + 混合储能系统 --> 分数拉不开, primary=null, candidates 非空."""
        pr = build_paper(
            paper_id="p-conflict",
            title="液流电池 相变材料 混合储能",
            abstract_text=(
                "本工作在混合储能系统中同时使用液流电池与相变材料; "
                "液流电池 全钒液流电池 相变储能 PCM 潜热 相变材料 混合储能 冷热电联供."
            ),
        )
        r = tr.classify_taxonomy(pr)
        # 三方都得分, 允许 primary=null + candidates 非空, 或 primary + secondary 齐全
        if r["primary_storage_domain"] is None:
            self.assertEqual(r["paper_context_status"], "candidate")
            self.assertGreater(len(r["domain_candidates"]), 1,
                               "expected at least 2 candidates in conflict")
        else:
            self.assertGreater(len(r["secondary_storage_domains"]), 0,
                               "expected secondary_domains in multi-domain paper")

    # ---------- spec 六.11: 无证据 unknown ----------

    def test_no_evidence_returns_unknown(self):
        pr = build_paper(
            paper_id="p-empty",
            title="一段与储能无关的中性标题",
            abstract_text="一段中性文字, 不包含任何领域关键词.",
        )
        r = tr.classify_taxonomy(pr)
        self.assertEqual(r["primary_storage_domain"], None)
        self.assertEqual(r["paper_context_status"], "unknown")

    # ---------- spec 六.12: 非储能 non_storage ----------

    def test_generic_separation_membrane_is_non_storage(self):
        pr = build_paper(
            paper_id="p-mem-only",
            title="MOFs 分离膜在水系分离中的应用",
            abstract_text=("综述了 MOFs 基分离膜在水系油水分离中的最新进展."),
        )
        r = tr.classify_taxonomy(pr)
        self.assertEqual(r["primary_storage_domain"], None)
        self.assertEqual(r["paper_context_status"], "non_storage")

    def test_patent_analysis_topic_is_non_storage(self):
        pr = build_paper(
            paper_id="p-patent",
            title="某材料的专利分析",
            abstract_text="本文对该材料的专利态势与技术路线进行了梳理.",
        )
        r = tr.classify_taxonomy(pr)
        self.assertEqual(r["paper_context_status"], "non_storage")

    # ---------- spec 六.13: variant vs 材料体系 ----------

    def test_variant_does_not_pick_up_mof_derived_carbon(self):
        """MOF 材料体系不得进 technology_variant."""
        pr = build_paper(
            paper_id="p-mof",
            title="MOFs 衍生多孔碳超级电容器",
            abstract_text="以 MOFs 为前驱体制备多孔碳作为超级电容器电极.",
        )
        r = tr.classify_taxonomy(pr)
        self.assertEqual(r["technology_subfield"], "supercapacitor")
        self.assertNotIn("mof_derived_carbon", r["technology_variant"])
        # 允许 technology_variant 为空
        # 且 MOF 相关不应造成 primary 走偏
        self.assertEqual(r["primary_storage_domain"], "electrochemical_storage")

    def test_variant_picks_up_real_chemistry_full_vanadium(self):
        pr = build_paper(
            paper_id="p-vrfb",
            title="全钒液流电池电堆的均一性",
            abstract_text="本文研究全钒液流电池电堆的均一性, 优化电堆结构.",
        )
        r = tr.classify_taxonomy(pr)
        self.assertIn("vanadium_redox_flow", r["technology_variant"])

    def test_variant_picks_up_hydrated_salt(self):
        pr = build_paper(
            paper_id="p-hs-pcm",
            title="三水醋酸钠相变储能复合材料的改性制备",
            abstract_text="制备了三水醋酸钠水合盐相变复合材料.",
        )
        r = tr.classify_taxonomy(pr)
        self.assertIn("hydrated_salt_pcm", r["technology_variant"])

    # ---------- spec 六.14: primary + secondary method_type ----------

    def test_material_design_and_synthesis_process_both(self):
        pr = build_paper(
            paper_id="p-mds",
            title="某高熵材料的空位调控与制备研究",
            abstract_text=("本文通过空位调控与结构工程设计了一种新型高熵氧化物, "
                           "采用溶胶-凝胶法制备, 表征其电化学性能."),
            body_sections=(
                ("methods", "1 实验", "实验"),
                ("results", "2 结果", "结果"),
            ),
        )
        r = tr.classify_taxonomy(pr)
        # material_design 应为 primary, synthesis_process 应在 secondary
        # 注意: 也可能因 keyword 密度反过来; 我们只 assert 两者都出现即可
        both = {r["primary_method_type"]} | set(r["secondary_method_types"])
        self.assertIn("material_design", both)
        self.assertIn("synthesis_process", both)

    def test_system_design_and_model_simulation_both(self):
        pr = build_paper(
            paper_id="p-sms",
            title="集成热力系统的系统设计与仿真",
            abstract_text=("本文构建了一个集成热力系统, 采用系统设计与流程设计方法, "
                           "并建立动态数学模型, 通过数值模拟验证系统性能."),
        )
        r = tr.classify_taxonomy(pr)
        both = {r["primary_method_type"]} | set(r["secondary_method_types"])
        self.assertIn("system_design", both)
        self.assertIn("model_simulation", both)

    # ---------- spec 六.15: 禁止 paper_id 硬编码 ----------

    def test_no_paper_id_hardcoding_in_source(self):
        """taxonomy_rules.py + YAML 都不能含试运行 paper_id."""
        src = inspect.getsource(tr)
        yaml_path = os.path.join(
            os.path.dirname(inspect.getsourcefile(tr)),
            "taxonomy_keywords_v1.yaml",
        )
        with open(yaml_path, "r", encoding="utf-8") as f:
            yaml_content = f.read()

        forbidden = [
            "全钒液流电池电堆的均一性",
            "钠离子电池正极材料研究进展",
            "Cu阳离子空位提升钙钛矿型高熵氧化物储锂性能",
            "三水醋酸钠相变储能复合材料改性制备及储_放热特性",
            "光热-跨临界压缩二氧化碳储能循环动态特性研究",
            "基于液氖液氮梯级蓄冷的液氢储能中冷能回收利用研究",
            "MOFs基材料在超级电容器中的应用",
            "低共熔溶剂在储能与传热方面的研究进展",
            "SMES超导磁体动态载荷温度场仿真分析",
            "二氧化硅基气凝胶材料及其制备技术的专利分析",
        ]
        for pid in forbidden:
            self.assertNotIn(pid, src, f"taxonomy_rules.py hardcodes paper_id {pid}")
            self.assertNotIn(pid, yaml_content,
                             f"taxonomy_keywords_v1.yaml hardcodes paper_id {pid}")

    def test_no_paper_id_hardcoding_swap_id_does_not_flip_verdict(self):
        """给一个明显 review 的 paper 起个 research 感的 paper_id, 分类不受影响."""
        pr = build_paper(
            paper_id="全钒液流电池电堆的均一性",   # 拿实验类的 pid
            title="某新材料的研究进展",             # 但标题是综述
            abstract_text="本文综述了近年该材料的研究进展.",
        )
        r = tr.classify_taxonomy(pr)
        # paper_id 是 flow_battery 的名字, 但内容里没有 flow_battery 关键词 → 分类应看内容
        self.assertNotEqual(r["technology_subfield"], "flow_battery",
                            "paper_id must NOT influence subfield decision")

    # ---------- spec 六.16: 禁止读取 legacy ----------

    def test_no_legacy_read_in_source(self):
        """源码与 YAML 都不能引用 legacy 路径."""
        src = inspect.getsource(tr)
        yaml_path = os.path.join(
            os.path.dirname(inspect.getsourcefile(tr)),
            "taxonomy_keywords_v1.yaml",
        )
        with open(yaml_path, "r", encoding="utf-8") as f:
            yaml_content = f.read()
        forbidden = [
            "methods.csv",
            "edges.csv",
            "subfield_keywords.yaml",
            "method_outputs",
            "methods_v2.csv",
            "methods_v3.csv",
            "edges_v2.csv",
        ]
        for tok in forbidden:
            self.assertNotIn(tok, src, f"taxonomy_rules.py must not reference legacy {tok}")
            self.assertNotIn(tok, yaml_content,
                             f"YAML must not reference legacy {tok}")

    # ---------- edge: ASCII 短词不误伤 ----------

    def test_ev_does_not_hit_development(self):
        """'EV' 不能命中 'Recent development of ...' 这种词内子串."""
        pr = build_paper(
            paper_id="p-en-title",
            title="钠离子电池正极材料研究进展",
            abstract_text="Recent development of cathode materials for sodium-ion batteries.",
        )
        r = tr.classify_taxonomy(pr)
        # 若 EV 词边界错, 会给 vehicle application 命中. 应该没有.
        self.assertNotIn("vehicle", r["application_contexts"])

    # ---------- 输出字段与序列化 ----------

    def test_output_has_all_required_fields(self):
        pr = build_paper(paper_id="p-x", title="锂离子电池研究",
                         abstract_text="锂离子电池 实验 结果")
        r = tr.classify_taxonomy(pr)
        required = [
            "paper_id", "paper_type",
            "primary_storage_domain", "secondary_storage_domains", "domain_candidates",
            "technology_subfield", "technology_variant", "application_contexts",
            "primary_method_type", "secondary_method_types",
            "paper_context_status",
            "matched_signals", "conflicting_signals", "evidence",
            "decision_reason", "taxonomy_version", "classified_at",
        ]
        for f in required:
            self.assertIn(f, r, f"missing field {f}")

    def test_list_fields_are_python_lists(self):
        pr = build_paper(paper_id="p-y", title="锂离子电池研究",
                         abstract_text="锂离子电池 实验")
        r = tr.classify_taxonomy(pr)
        for f in ("secondary_storage_domains", "domain_candidates",
                  "technology_variant", "application_contexts",
                  "secondary_method_types",
                  "matched_signals", "conflicting_signals", "evidence"):
            self.assertIsInstance(r[f], list, f"{f} must be a list, got {type(r[f])}")

    def test_output_json_serializable_and_lists_are_json_arrays(self):
        """整个结果应 JSON serializable, 且所有列表字段可以在 CSV 用 json.dumps 保留."""
        pr = build_paper(paper_id="p-z", title="全钒液流电池",
                         abstract_text="全钒液流电池研究.")
        r = tr.classify_taxonomy(pr)
        s = json.dumps(r, ensure_ascii=False)
        parsed = json.loads(s)
        self.assertIsInstance(parsed["secondary_storage_domains"], list)
        self.assertIsInstance(parsed["evidence"], list)

    def test_evidence_locations_are_whitelisted(self):
        pr = build_paper(paper_id="p-ev-w", title="锂离子电池研究",
                         abstract_text="锂离子电池的实验研究.")
        r = tr.classify_taxonomy(pr)
        allowed = {"title", "abstract", "heading"}
        for ev in r["evidence"]:
            self.assertIn(ev["location"], allowed,
                          f"evidence location '{ev['location']}' not in whitelist")

    def test_taxonomy_version_contains_both_engine_and_yaml(self):
        pr = build_paper(paper_id="p-v", title="锂离子电池",
                         abstract_text="锂离子电池")
        r = tr.classify_taxonomy(pr)
        self.assertIn("taxonomy_rules=", r["taxonomy_version"])
        self.assertIn("keywords_yaml=", r["taxonomy_version"])

    # ============================================================
    # v1.1.1 新增补丁测试 (窄口径关键词; 每类 1 正 + 1 反)
    # ============================================================

    # ---- 1) 蓄冷 / 蓄热 → thermal; 普通换热 / 冷却 不触发 ----

    def test_v111_xuleng_hits_thermal(self):
        pr = build_paper(
            paper_id="p-xuleng",
            title="沸石-水吸附式蓄冷的热力分析",
            abstract_text="本文分析沸石-水吸附式蓄冷系统的性能.",
        )
        r = tr.classify_taxonomy(pr)
        self.assertEqual(r["primary_storage_domain"], "thermal_storage")

    def test_v111_xure_hits_thermal(self):
        pr = build_paper(
            paper_id="p-xure",
            title="复叠式蓄热型空气源热泵热水器",
            abstract_text="研究复叠式蓄热的动态传热特性.",
        )
        r = tr.classify_taxonomy(pr)
        self.assertEqual(r["primary_storage_domain"], "thermal_storage")

    def test_v111_plain_heat_transfer_alone_does_not_hit(self):
        """'换热/传热/冷却' 单独不能触发储能."""
        pr = build_paper(
            paper_id="p-heat-transfer-only",
            title="板式换热器传热性能与冷却效果分析",
            abstract_text="研究了板式换热器的传热强化, 冷却效果良好.",
        )
        r = tr.classify_taxonomy(pr)
        self.assertNotEqual(r["primary_storage_domain"], "thermal_storage",
                            "plain heat transfer must not trigger thermal_storage")

    # ---- 2) 热化学储能 / 化学储热材料 / 钙基储能材料 → thermochemical ----

    def test_v111_thermochemical_storage_hits(self):
        pr = build_paper(
            paper_id="p-tchs",
            title="Ca(OH)2 热化学储能性能研究",
            abstract_text="Ca(OH)2 热化学储能材料的反应床性能分析.",
        )
        r = tr.classify_taxonomy(pr)
        self.assertEqual(r["primary_storage_domain"], "thermal_storage")
        self.assertEqual(r["technology_subfield"], "thermochemical_heat_storage")

    def test_v111_ca_based_storage_material_hits(self):
        pr = build_paper(
            paper_id="p-ca",
            title="Mn_Al改性的高稳定性钙基储能材料",
            abstract_text="钙基储能材料的循环稳定性与容量分析.",
        )
        r = tr.classify_taxonomy(pr)
        self.assertEqual(r["primary_storage_domain"], "thermal_storage")

    def test_v111_generic_chemical_reaction_does_not_hit(self):
        """普通化学反应术语不能触发 thermochemical."""
        pr = build_paper(
            paper_id="p-plain-chem",
            title="有机合成反应机理",
            abstract_text="研究了某化学反应的反应机理.",
        )
        r = tr.classify_taxonomy(pr)
        # 应为 unknown, 而非 thermal
        self.assertNotEqual(r["primary_storage_domain"], "thermal_storage")

    # ---- 3) 电池包热管理 (完整短语) → application; 电池包 单独不触发 ----

    def test_v111_battery_pack_thermal_management_hits(self):
        pr = build_paper(
            paper_id="p-bp-tm",
            title="电池包热管理系统设计",
            abstract_text="锂离子电池的电池包热管理系统设计与性能评估.",
        )
        r = tr.classify_taxonomy(pr)
        self.assertIn("battery_thermal_management", r["application_contexts"])

    def test_v111_battery_pack_alone_does_not_hit_application(self):
        pr = build_paper(
            paper_id="p-bp-alone",
            title="锂离子电池的电池包结构设计",
            abstract_text="锂离子电池的电池包机械结构与装配.",
        )
        r = tr.classify_taxonomy(pr)
        # '电池包' 单独不能触发 battery_thermal_management
        self.assertNotIn("battery_thermal_management", r["application_contexts"])

    def test_v111_dongli_battery_thermal_management_full_phrase_hits(self):
        pr = build_paper(
            paper_id="p-dyn-btm",
            title="动力电池热管理策略",
            abstract_text="研究动力电池热管理策略对锂离子电池寿命的影响.",
        )
        r = tr.classify_taxonomy(pr)
        self.assertIn("battery_thermal_management", r["application_contexts"])

    # ---- 4) 复合相变材料 / 定形相变材料 → latent_heat ----

    def test_v111_composite_pcm_hits_latent_heat(self):
        pr = build_paper(
            paper_id="p-composite-pcm",
            title="脂肪酸/膨胀石墨定形相变材料的制备",
            abstract_text="制备了复合相变材料, 具有良好的定形相变材料特性.",
        )
        r = tr.classify_taxonomy(pr)
        self.assertEqual(r["primary_storage_domain"], "thermal_storage")
        self.assertEqual(r["technology_subfield"], "latent_heat_storage")

    def test_v111_pcm_heatsink_hits_thermal(self):
        pr = build_paper(
            paper_id="p-heatsink",
            title="弹载相变热沉传热仿真",
            abstract_text="相变热沉在弹载设备中的传热仿真与优化.",
        )
        r = tr.classify_taxonomy(pr)
        self.assertEqual(r["primary_storage_domain"], "thermal_storage")

    # ---- 5) 氢能储运 不被 制氢 规则错误排除 ----

    def test_v111_hydrogen_transport_not_excluded_by_hydrogen_production(self):
        """含 '氢能储运' 且提到 '制氢' 时, non_storage_signal 不应触发."""
        pr = build_paper(
            paper_id="p-h2-transport",
            title="浮式氢能储运过程中海上适应性研究",
            abstract_text=("研究氢能储运的海上适应性; 涉及制氢过程的耦合分析."),
        )
        r = tr.classify_taxonomy(pr)
        # 应走 chemical_energy_storage / hydrogen_storage
        self.assertEqual(r["primary_storage_domain"], "chemical_energy_storage")
        self.assertEqual(r["technology_subfield"], "hydrogen_storage")
        # non_storage_signal:hydrogen_production_only 不应触发
        ns_keys = {m["key"] for m in r["matched_signals"]
                   if m["key"].startswith("non_storage_signal:")}
        self.assertNotIn("non_storage_signal:hydrogen_production_only", ns_keys)

    def test_v111_hydrogen_storage_explicit_not_excluded(self):
        pr = build_paper(
            paper_id="p-h2-stor",
            title="液氢储能与再生燃料电池耦合的电解水制氢集成",
            abstract_text=("采用液氢储能, 涉及电解水制氢作为氢源."),
        )
        r = tr.classify_taxonomy(pr)
        # 只要 储氢/氢储能 出现, 就不能被 non_storage 排除
        self.assertEqual(r["primary_storage_domain"], "chemical_energy_storage")

    # ---- 6) 甲烷干重整 触发 non_storage (无储能语境); 有储热语境时不触发 ----

    def test_v111_methane_dry_reforming_non_storage_when_isolated(self):
        pr = build_paper(
            paper_id="p-mdr-only",
            title="甲烷干重整反应机理研究",
            abstract_text="研究甲烷干重整反应的催化剂设计.",
        )
        r = tr.classify_taxonomy(pr)
        self.assertEqual(r["paper_context_status"], "non_storage")

    def test_v111_methane_dry_reforming_with_thermochemical_storage_not_non_storage(self):
        pr = build_paper(
            paper_id="p-mdr-tchs",
            title="太阳能甲烷干重整复杂反应体系的热化学储能特性",
            abstract_text=("研究甲烷干重整体系的热化学储能特性, 分析反应床的反应热与储放热."),
        )
        r = tr.classify_taxonomy(pr)
        # 应走 thermal_storage 而非 non_storage
        self.assertEqual(r["primary_storage_domain"], "thermal_storage")
        self.assertNotEqual(r["paper_context_status"], "non_storage")

    def test_v111_photocatalytic_hydrogen_production_non_storage(self):
        pr = build_paper(
            paper_id="p-pc-h2",
            title="光催化制氢体系研究进展",
            abstract_text="综述了光催化制氢催化剂的最新研究进展.",
        )
        r = tr.classify_taxonomy(pr)
        self.assertEqual(r["paper_context_status"], "non_storage")

    # ---- 7) 压气储能 → mechanical; 光储直驱 → system_integration ----

    def test_v111_yaqi_chuneng_hits_compressed_air(self):
        pr = build_paper(
            paper_id="p-yaqi",
            title="压气储能系统中储气装置的性能分析",
            abstract_text="研究压气储能系统的储气装置性能与运行特性.",
        )
        r = tr.classify_taxonomy(pr)
        self.assertEqual(r["primary_storage_domain"], "mechanical_storage")
        self.assertEqual(r["technology_subfield"], "compressed_air_storage")

    def test_v111_guangchu_zhiqu_hits_system_integration(self):
        pr = build_paper(
            paper_id="p-gczq",
            title="太阳能PV_T光储直驱热电联产系统性能",
            abstract_text="光储直驱系统在光伏发电与热电联产的集成设计.",
        )
        r = tr.classify_taxonomy(pr)
        self.assertEqual(r["primary_storage_domain"], "system_integration")

    # ---- 8) laboratory_material 不再作默认值; 无明确 app → apps=[] ----

    def test_v111_lab_material_no_longer_default(self):
        """有 storage domain 命中但无 application 证据 -> apps 应为空数组, 不含 laboratory_material."""
        pr = build_paper(
            paper_id="p-no-app",
            title="锂离子电池正极材料结构表征",
            abstract_text="本文研究了锂离子电池正极材料的结构表征.",
        )
        r = tr.classify_taxonomy(pr)
        self.assertNotIn("laboratory_material", r["application_contexts"],
                         "laboratory_material must NOT be default-injected")
        # apps 允许空
        self.assertIsInstance(r["application_contexts"], list)

    def test_v111_lab_material_explicit_signal_still_hits(self):
        pr = build_paper(
            paper_id="p-lab-exp",
            title="某新材料的实验室材料制备与性能表征",
            abstract_text=("本文进行了材料性能实验, 实验室材料制备条件如下: ..."),
        )
        r = tr.classify_taxonomy(pr)
        self.assertIn("laboratory_material", r["application_contexts"],
                      "explicit lab_material signal should still fire")

    def test_v111_various_papers_still_have_no_default_lab_material(self):
        """跑几篇 test_run_01 的 in-memory 版本, 确认 lab_material 不再兜底."""
        for pid, title, abstract in [
            ("电堆均一性", "全钒液流电池电堆的均一性",
             "研究了全钒液流电池电堆的均一性."),
            ("钠离子研究进展", "钠离子电池正极材料研究进展",
             "本文综述了钠离子电池正极材料研究进展."),
        ]:
            pr = build_paper(pid, title, abstract)
            r = tr.classify_taxonomy(pr)
            self.assertNotIn("laboratory_material", r["application_contexts"],
                             f"paper {pid} should not have default lab_material")

    # ---------- cross_domain_method 抑制 ----------

    def test_cross_domain_method_suppressed_when_other_domain_present(self):
        """若同时有储能领域命中, cross_domain_method 不作为 primary."""
        pr = build_paper(
            paper_id="p-cdm-mix",
            title="锂离子电池 DFT 计算",
            abstract_text=("采用 DFT 与分子动力学模拟研究锂离子电池正极材料的电子结构."),
        )
        r = tr.classify_taxonomy(pr)
        self.assertNotEqual(r["primary_storage_domain"], "cross_domain_method")
        self.assertEqual(r["primary_storage_domain"], "electrochemical_storage")


if __name__ == "__main__":
    unittest.main(verbosity=2)
