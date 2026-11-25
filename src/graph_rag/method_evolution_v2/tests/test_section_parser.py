"""单元测试: 章节解析器.

覆盖:
  - 空输入
  - 无 markdown 标题: 整篇 -> 单个 other_sections
  - preamble (第一个 heading 之前) 保留
  - 关键词命中: 摘要 / 引言 / 实验 / 结果 / 结论 / 参考文献
  - 编号继承: '# 1 实验' + '# 1.1 实验对象' -> 都是 methods
  - 第一个未匹配 heading 视为 title
  - 中文空格容忍: '引 言' -> introduction
  - 段落 char_offset 可重建原文
  - 章节覆盖率 100% (无文本丢失)
"""
from __future__ import annotations

import os
import sys
import unittest

# 让 import 在仓库根目录运行也能找到模块
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
V2_DIR = os.path.dirname(THIS_DIR)
SRC_GRAPH_RAG_DIR = os.path.dirname(V2_DIR)
SRC_DIR = os.path.dirname(SRC_GRAPH_RAG_DIR)
PROJECT_ROOT = os.path.dirname(SRC_DIR)
if SRC_GRAPH_RAG_DIR not in sys.path:
    sys.path.insert(0, SRC_GRAPH_RAG_DIR)

from method_evolution_v2.io import section_parser as sp  # noqa: E402


class TestSectionParser(unittest.TestCase):

    def _assert_full_coverage(self, text, result):
        self.assertEqual(
            result.section_coverage_chars, len(text),
            f"section coverage != len(text): {result.section_coverage_chars} vs {len(text)}",
        )
        self.assertFalse(result.has_text_loss, "has_text_loss must be False")

    def _assert_paragraphs_match_source(self, text, result):
        """每个 paragraph 的 [char_start, char_end) 切片必须正好等于 paragraph.text 之前的 raw 切片
        (允许末尾空白被剥离, 但范围内 stripped 后应等于 text)."""
        for sec in result.sections:
            for p in sec.paragraphs:
                slice_text = text[p.char_start:p.char_end]
                # paragraph.text 来自切片再 strip 边缘空白; 切片头尾允许有空白
                self.assertIn(
                    p.text, slice_text,
                    f"para {p.para_id} text mismatch: text={p.text!r} slice={slice_text!r}",
                )

    # ---------- 基础 ----------

    def test_empty_input(self):
        r = sp.parse_text("p", "")
        self.assertEqual(r.source_md_chars, 0)
        self.assertEqual(r.section_coverage_chars, 0)
        # 空输入既无 heading 又无内容: notes 提示
        self.assertTrue(len(r.sections) <= 1)

    def test_no_heading_at_all(self):
        text = "全篇没有 markdown 标题\n\n第二段也只是普通文字\n"
        r = sp.parse_text("p", text)
        self.assertEqual(len(r.sections), 1)
        self.assertEqual(r.sections[0].section_type, "other_sections")
        self.assertEqual(r.sections[0].heading_level, 0)
        self.assertEqual(r.sections[0].inference_source, "no_heading_found")
        self._assert_full_coverage(text, r)
        self._assert_paragraphs_match_source(text, r)
        # 至少识别两段
        self.assertEqual(len(r.sections[0].paragraphs), 2)

    # ---------- 关键词命中 ----------

    def test_abstract_keyword(self):
        text = "# 摘要\n\n这是摘要内容\n"
        r = sp.parse_text("p", text)
        types = [s.section_type for s in r.sections]
        self.assertIn("abstract", types)
        # 第一个 heading 是摘要, 因此没有 title; 上面也无 preamble
        self.assertNotIn("title", types)

    def test_introduction_with_space(self):
        text = "# 全钒电池论文标题\n# 引 言\n\n大容量储能...\n"
        r = sp.parse_text("p", text)
        types = [s.section_type for s in r.sections]
        self.assertEqual(types[0], "title")
        self.assertIn("introduction", types)

    def test_methods_and_results_and_conclusion(self):
        text = (
            "# 测试论文\n"
            "# 摘要\n摘要内容\n\n"
            "# 1 实验\n实验内容\n\n"
            "# 2 结果与讨论\n结果内容\n\n"
            "# 3 结论\n结论内容\n\n"
            "# 参考文献\n[1]...\n"
        )
        r = sp.parse_text("p", text)
        types = [s.section_type for s in r.sections]
        for t in ("title", "abstract", "methods", "results_discussion", "conclusion", "references"):
            self.assertIn(t, types, f"missing {t} in {types}")
        self._assert_full_coverage(text, r)

    def test_english_keywords(self):
        text = "# A Paper Title\n# Abstract\nabc\n\n# Introduction\nxyz\n\n# Conclusion\ndone\n"
        r = sp.parse_text("p", text)
        types = [s.section_type for s in r.sections]
        self.assertEqual(types[0], "title")
        self.assertIn("abstract", types)
        self.assertIn("introduction", types)
        self.assertIn("conclusion", types)

    # ---------- 编号继承 ----------

    def test_numbering_inheritance(self):
        text = (
            "# 论文标题\n"
            "# 1 实验\n父级实验内容\n\n"
            "# 1.1 设备清单\n仪器列表 (不匹配 methods 关键词)\n\n"
            "# 1.2 实验方法\n子级 (本身匹配关键词)\n\n"
            "# 2 测试结果与分析\n结果父级\n\n"
            "# 2.1 电极过程交流阻抗\n结果子级 (不匹配 results 关键词)\n"
        )
        r = sp.parse_text("p", text)
        sub_11 = next(s for s in r.sections if s.raw_heading.startswith("1.1"))
        sub_12 = next(s for s in r.sections if s.raw_heading.startswith("1.2"))
        sub_21 = next(s for s in r.sections if s.raw_heading.startswith("2.1"))

        # 1.2 自带关键词 '实验方法' -> 应为 keyword 路径
        self.assertEqual(sub_12.section_type, "methods")
        self.assertEqual(sub_12.inference_source, "keyword")

        # 1.1 '设备清单' 不匹配任何关键词, 应靠编号继承到 methods (1.x -> 1 实验)
        self.assertEqual(sub_11.section_type, "methods")
        self.assertEqual(sub_11.inference_source, "numbering_inherit")
        self.assertTrue(sub_11.inferred_by_regex)

        # 2.1 '电极过程交流阻抗' 不匹配 results 关键词, 应继承父 2 测试结果与分析
        self.assertIn(sub_21.section_type, ("results", "results_discussion"))
        self.assertEqual(sub_21.inference_source, "numbering_inherit")

    # ---------- title 启发 ----------

    def test_title_first_unmatched(self):
        text = "# 全钒液流电池电堆的均一性\n\n作者\n\n# 1 实验\n实验内容\n"
        r = sp.parse_text("p", text)
        self.assertEqual(r.sections[0].section_type, "title")
        self.assertEqual(r.document_title, "全钒液流电池电堆的均一性")

    def test_title_not_assigned_when_first_heading_is_abstract(self):
        text = "# 摘要\n内容\n\n# 1 实验\n方法\n"
        r = sp.parse_text("p", text)
        types = [s.section_type for s in r.sections]
        # 没有显式 title heading 时, document_title fallback 到 paper_id
        self.assertNotIn("title", types)
        self.assertEqual(r.document_title, "p")

    # ---------- preamble ----------

    def test_preamble_before_first_heading(self):
        text = "前置文字, 在第一个 heading 之前\n\n更多前置\n\n# 1 实验\n实验内容\n"
        r = sp.parse_text("p", text)
        first = r.sections[0]
        self.assertEqual(first.heading_level, 0)
        self.assertEqual(first.section_type, "other_sections")
        self.assertEqual(first.inference_source, "preamble")
        self._assert_full_coverage(text, r)

    # ---------- 覆盖率 / 位置回溯 ----------

    def test_coverage_and_para_offset_realistic(self):
        text = (
            "# 测试论文标题\n"
            "作者 abc\n\n"
            "# 摘要\n"
            "摘要第一段\n\n"
            "摘要第二段\n\n"
            "# 1 实验\n"
            "实验第一段\n\n"
            "实验第二段\n\n"
            "# 2 结果\n"
            "结果文本\n"
        )
        r = sp.parse_text("p", text)
        self._assert_full_coverage(text, r)
        self._assert_paragraphs_match_source(text, r)
        # 每段非空
        for sec in r.sections:
            for p in sec.paragraphs:
                self.assertTrue(p.text.strip(), f"empty paragraph in {sec.section_type}")

    def test_section_type_unmatched_no_numbering_falls_to_other(self):
        text = (
            "# 论文标题\n"
            "# 1 实验\n方法\n\n"
            "# 致谢\n感谢各位审稿人...\n"   # 不匹配任何关键词且无编号 -> other_sections
        )
        r = sp.parse_text("p", text)
        sec_thx = next(s for s in r.sections if "致谢" in s.raw_heading)
        self.assertEqual(sec_thx.section_type, "other_sections")
        self.assertEqual(sec_thx.inference_source, "no_match")

    # ============================================================
    # v1.1 新增测试
    # ============================================================

    # ---------- 内联摘要 ----------

    def test_inline_abstract_chinese_colon(self):
        """1. 中文内联摘要 (摘要：)."""
        text = (
            "# 某某论文的中文标题\n\n"
            "作者甲, 作者乙\n\n"
            "摘要：本文研究了一种新型相变储能复合材料的制备方法, 通过加入特定纳米颗粒"
            "改善其热导率与循环稳定性, 得到性能优于传统材料的复合相变材料。\n"
            "关键词：相变储能；热导率；纳米颗粒\n\n"
            "# 1 实验\n实验内容\n"
        )
        r = sp.parse_text("p", text)
        ab = [s for s in r.sections if s.section_type == "abstract"]
        self.assertEqual(len(ab), 1, "expected one inline abstract section")
        self.assertTrue(ab[0].inferred_by_regex)
        self.assertEqual(ab[0].inference_source, "inline_abstract_cn_colon")
        self.assertEqual(ab[0].confidence, "high")
        self._assert_full_coverage(text, r)

    def test_inline_abstract_with_space_in_marker(self):
        """2. 带空格的"摘 要："  ->  abstract."""
        text = (
            "# 论文标题\n\n"
            "摘 要：研究内容详细描述, 包含足够多的字以满足最小字符数要求, "
            "本文研究了 A 体系在 B 工况下的 C 行为。\n\n"
            "关键词：A；B；C\n\n"
            "# 1 实验\n实验内容\n"
        )
        r = sp.parse_text("p", text)
        ab = [s for s in r.sections if s.section_type == "abstract"]
        self.assertEqual(len(ab), 1)
        self.assertEqual(ab[0].inference_source, "inline_abstract_cn_colon")

    def test_inline_abstract_english_colon(self):
        """3. Abstract: inline format."""
        text = (
            "# A Research Paper Title\n\n"
            "Author One, Author Two\n\n"
            "Abstract: This paper presents a new approach to thermal energy storage "
            "using composite phase change materials with enhanced thermal conductivity.\n\n"
            "Keywords: thermal energy storage; PCM; composite\n\n"
            "# 1 Experimental\nfoo\n"
        )
        r = sp.parse_text("p", text)
        ab = [s for s in r.sections if s.section_type == "abstract"]
        self.assertEqual(len(ab), 1)
        self.assertEqual(ab[0].inference_source, "inline_abstract_en_colon")

    def test_inline_abstract_keywords_boundary(self):
        """4. 摘要内容到关键词之间精确截断."""
        text = (
            "# 论文标题\n\n"
            "摘要：摘要核心内容, 该论文研究了 X 在 Y 条件下的 Z 性质, 提出 W 方法。\n"
            "关键词：X；Y；Z\n\n"
            "# 1 引言\n引言内容\n"
        )
        r = sp.parse_text("p", text)
        ab = next(s for s in r.sections if s.section_type == "abstract")
        # abstract 章节切片必须含核心内容但不含 "关键词"
        slice_text = text[ab.char_start:ab.char_end]
        self.assertIn("摘要核心内容", slice_text)
        self.assertNotIn("关键词", slice_text)

    def test_inline_abstract_no_false_positive_when_no_marker(self):
        """额外: 正文中间出现 '摘要' 二字不应触发 (无冒号无方括号)."""
        text = (
            "# 论文标题\n\n"
            "本文综述了多种方法的研究情况。摘要内容来自原始论文。\n\n"
            "# 1 引言\n引言\n"
        )
        r = sp.parse_text("p", text)
        ab = [s for s in r.sections if s.section_type == "abstract"]
        self.assertEqual(len(ab), 0, "should not fabricate abstract from prose")

    # ---------- 严格 conclusion ----------

    def test_conclusion_strict_total_outlook(self):
        """5. '总结与展望' 应判 conclusion."""
        text = "# 论文标题\n# 1 引言\nfoo\n\n# 4 总结与展望\nbar\n"
        r = sp.parse_text("p", text)
        sec = next(s for s in r.sections if "总结与展望" in s.raw_heading)
        self.assertEqual(sec.section_type, "conclusion")
        self.assertEqual(sec.inference_source, "keyword")

    def test_conclusion_strict_not_when_modifier_present(self):
        """6. '机理总结与分析' 不应被判 conclusion."""
        text = (
            "# 论文标题\n# 1 引言\nfoo\n\n"
            "# 2.2 机理总结与分析\n这是综述里的一个子小节, 不是结论\n\n"
            "# 4 总结与展望\n这才是真正的结论\n"
        )
        r = sp.parse_text("p", text)
        sec_mid = next(s for s in r.sections if "机理总结" in s.raw_heading)
        sec_end = next(s for s in r.sections if s.raw_heading.endswith("总结与展望"))
        self.assertNotEqual(sec_mid.section_type, "conclusion",
                            f"mis-classified: {sec_mid.raw_heading} -> {sec_mid.section_type}")
        self.assertEqual(sec_end.section_type, "conclusion")

    # ---------- 新章节类型 ----------

    def test_theory_model_recognized(self):
        """7. '数学模型' 判为 theory_model."""
        text = "# 论文标题\n# 1 引言\nx\n\n# 2 数学模型\n模型推导\n"
        r = sp.parse_text("p", text)
        sec = next(s for s in r.sections if "数学模型" in s.raw_heading)
        self.assertEqual(sec.section_type, "theory_model")
        self.assertEqual(sec.inference_source, "keyword")

    def test_system_design_recognized(self):
        """8. '系统设计' / '装置设计' 判为 system_design."""
        text = (
            "# 论文标题\n# 1 引言\nx\n\n"
            "# 2 系统设计\n系统介绍\n\n"
            "# 3 装置设计\n装置说明\n"
        )
        r = sp.parse_text("p", text)
        sec1 = next(s for s in r.sections if s.raw_heading.endswith("系统设计"))
        sec2 = next(s for s in r.sections if s.raw_heading.endswith("装置设计"))
        self.assertEqual(sec1.section_type, "system_design")
        self.assertEqual(sec2.section_type, "system_design")

    def test_case_analysis_recognized(self):
        """9. '参数分析' / '算例分析' 判为 case_analysis."""
        text = (
            "# 论文标题\n# 1 系统设计\nx\n\n"
            "# 2 参数分析\n参数影响\n\n"
            "# 3 算例分析\n算例\n"
        )
        r = sp.parse_text("p", text)
        sec1 = next(s for s in r.sections if s.raw_heading.endswith("参数分析"))
        sec2 = next(s for s in r.sections if s.raw_heading.endswith("算例分析"))
        self.assertEqual(sec1.section_type, "case_analysis")
        self.assertEqual(sec2.section_type, "case_analysis")

    def test_patent_analysis_recognized(self):
        """额外: '专利分析' / '技术路线分析' 判为 patent_analysis."""
        text = (
            "# 某专利综述\n\n"
            "# 1 引言\nx\n\n"
            "# 2 专利分析\n专利统计\n\n"
            "# 3 技术路线分析\n技术演进\n"
        )
        r = sp.parse_text("p", text)
        sec1 = next(s for s in r.sections if s.raw_heading.endswith("专利分析"))
        sec2 = next(s for s in r.sections if "技术路线分析" in s.raw_heading)
        self.assertEqual(sec1.section_type, "patent_analysis")
        self.assertEqual(sec2.section_type, "patent_analysis")

    def test_simulation_calculation_recognized(self):
        """额外: '数值模拟' / '计算方法' 判为 simulation_calculation."""
        text = (
            "# 论文标题\n# 1 引言\nx\n\n"
            "# 2 数值模拟\nfoo\n\n"
            "# 3 计算方法\nbar\n"
        )
        r = sp.parse_text("p", text)
        sec1 = next(s for s in r.sections if s.raw_heading.endswith("数值模拟"))
        sec2 = next(s for s in r.sections if s.raw_heading.endswith("计算方法"))
        self.assertEqual(sec1.section_type, "simulation_calculation")
        self.assertEqual(sec2.section_type, "simulation_calculation")

    # ---------- 字符偏移 ----------

    # ============================================================
    # v1.1.1 微调测试 (2026-07-01)
    #   仅 3 个完整标题被追加, 其他关键词不扩展.
    # ============================================================

    def test_v1_1_1_conclusion_jieyu_yu_zhanwang(self):
        """结语与展望 → conclusion (与已有 '结语' / '总结与展望' 平级)."""
        text = (
            "# 论文标题\n# 1 引言\nx\n\n"
            "# 3 结语与展望\n综述性收尾内容, 展望方向。\n"
        )
        r = sp.parse_text("p", text)
        sec = next(s for s in r.sections if s.raw_heading.endswith("结语与展望"))
        self.assertEqual(sec.section_type, "conclusion")
        self.assertEqual(sec.inference_source, "keyword")
        self.assertEqual(sec.confidence, "high")
        self._assert_full_coverage(text, r)

    def test_v1_1_1_conclusion_jieyu_yu_zhanwang_no_numbering(self):
        """无编号的 '结语与展望' 也命中 (只看完整标题, 不看编号)."""
        text = "# 论文标题\n# 引言\nx\n\n# 结语与展望\n收尾\n"
        r = sp.parse_text("p", text)
        sec = next(s for s in r.sections if s.raw_heading == "结语与展望")
        self.assertEqual(sec.section_type, "conclusion")
        self.assertEqual(sec.inference_source, "keyword")

    def test_v1_1_1_case_analysis_moxing_yanzheng_exact(self):
        """完整标题 '模型验证' → case_analysis."""
        text = (
            "# 论文标题\n# 1 引言\nx\n\n"
            "# 2 数学模型\n方程\n\n"
            "# 3 模型验证\n对比实测数据\n"
        )
        r = sp.parse_text("p", text)
        sec = next(s for s in r.sections if s.raw_heading.endswith("模型验证"))
        self.assertEqual(sec.section_type, "case_analysis")
        self.assertEqual(sec.inference_source, "keyword")
        self.assertEqual(sec.confidence, "high")
        self._assert_full_coverage(text, r)

    def test_v1_1_1_case_analysis_moxing_yanzheng_child_inherits(self):
        """'3 模型验证' 是 case_analysis, 其子标题 '3.1 TC-CCES模型验证' 走编号继承.

        (子标题因为前后有其他字符, 严格锚定不命中 '模型验证' 完整标题白名单; 走 numbering_inherit.)
        """
        text = (
            "# 论文标题\n# 1 引言\nx\n\n"
            "# 3 模型验证\n父级说明\n\n"
            "# 3.1 TC-CCES模型验证\nA 子模型对比\n\n"
            "# 3.2 光热系统模型验证\nB 子模型对比\n"
        )
        r = sp.parse_text("p", text)
        parent = next(s for s in r.sections if s.raw_heading == "3 模型验证")
        s31 = next(s for s in r.sections if s.raw_heading.startswith("3.1"))
        s32 = next(s for s in r.sections if s.raw_heading.startswith("3.2"))
        self.assertEqual(parent.section_type, "case_analysis")
        self.assertEqual(parent.inference_source, "keyword")
        self.assertEqual(s31.section_type, "case_analysis")
        self.assertEqual(s31.inference_source, "numbering_inherit")
        self.assertEqual(s32.section_type, "case_analysis")
        self.assertEqual(s32.inference_source, "numbering_inherit")

    def test_v1_1_1_methods_yanjiu_fangfa_ji_shuju_fanwei_exact(self):
        """完整标题 '研究方法及数据范围' → methods (专利分析论文常见形态)."""
        text = (
            "# 论文标题\n\n"
            "摘要：本文分析了 XXX 领域近年的专利, 具备足够多的字数用于摘要识别的最小长度。\n"
            "关键词：A；B\n\n"
            "# 研究方法及数据范围\n"
            "本节说明检索式与数据边界。\n\n"
            "# 2 专利分析\n专利统计\n"
        )
        r = sp.parse_text("p", text)
        sec = next(s for s in r.sections if s.raw_heading == "研究方法及数据范围")
        self.assertEqual(sec.section_type, "methods")
        self.assertEqual(sec.inference_source, "keyword")
        self.assertEqual(sec.confidence, "high")
        self._assert_full_coverage(text, r)

    def test_v1_1_1_no_widening_gongzhi_xuanze(self):
        """v1.1.1 微调不扩大关键词: '工质选择' 仍应落 other_sections."""
        text = "# 论文标题\n# 引言\nx\n\n# 1 工质选择\n候选工质分析\n"
        r = sp.parse_text("p", text)
        sec = next(s for s in r.sections if s.raw_heading == "1 工质选择")
        self.assertEqual(sec.section_type, "other_sections")

    def test_v1_1_1_no_widening_xuleng_liucheng(self):
        """v1.1.1 微调不扩大关键词: '蓄冷流程' 仍应落 other_sections."""
        text = "# 论文标题\n# 引言\nx\n\n# 2 蓄冷流程\n流程说明\n"
        r = sp.parse_text("p", text)
        sec = next(s for s in r.sections if s.raw_heading == "2 蓄冷流程")
        self.assertEqual(sec.section_type, "other_sections")

    def test_v1_1_1_no_widening_yanjiu_duixiang_jieshao(self):
        """v1.1.1 微调不扩大关键词: '研究对象介绍' 仍应落 other_sections."""
        text = "# 论文标题\n# 引言\nx\n\n# 1 研究对象介绍\n对象描述\n"
        r = sp.parse_text("p", text)
        sec = next(s for s in r.sections if s.raw_heading == "1 研究对象介绍")
        self.assertEqual(sec.section_type, "other_sections")

    # ---------- get_title_info (v1.1.1 title 分离) ----------

    def test_get_title_info_from_source_markdown(self):
        """有明确 title heading -> source_markdown, high."""
        text = "# 全钒液流电池论文标题\n\n作者\n\n# 1 实验\n方法\n"
        r = sp.parse_text("some-paper-id", text)
        info = sp.get_title_info(r)
        self.assertEqual(info["source_title"], "全钒液流电池论文标题")
        self.assertEqual(info["canonical_title"], "全钒液流电池论文标题")
        self.assertEqual(info["title_source"], "source_markdown")
        self.assertEqual(info["title_confidence"], "high")

    def test_get_title_info_paper_id_fallback(self):
        """无 title heading -> canonical=paper_id, title_source=paper_id_fallback, medium."""
        text = "# 摘要\n摘要正文, 足够长, 保证不触发误动作\n\n# 1 实验\n方法\n"
        r = sp.parse_text("全钒液流电池电堆的均一性", text)
        info = sp.get_title_info(r)
        self.assertEqual(info["source_title"], "")
        self.assertEqual(info["canonical_title"], "全钒液流电池电堆的均一性")
        self.assertEqual(info["title_source"], "paper_id_fallback")
        self.assertEqual(info["title_confidence"], "medium")

    def test_get_title_info_never_pretends_paperid_is_markdown(self):
        """paper_id 永远不会被声称为 source_markdown."""
        text = "只有正文, 无任何 markdown 标题.\n"
        r = sp.parse_text("锂离子电池综述", text)
        info = sp.get_title_info(r)
        self.assertEqual(info["source_title"], "", "no markdown -> source_title empty")
        self.assertEqual(info["title_source"], "paper_id_fallback")
        # canonical fallback to paper_id
        self.assertEqual(info["canonical_title"], "锂离子电池综述")
        # 但 title_source 明确说明来源
        self.assertNotEqual(info["title_source"], "source_markdown")

    def test_get_title_info_inconsistency_kept_visible(self):
        """source_title 与 paper_id 不一致时, 两者都在字段中保留可对照."""
        text = "# MOFs 基材料在超级电容器中的应用\n\n作者\n\n# 1 引言\nx\n"
        r = sp.parse_text("MOFs基材料在超级电容器中的应用", text)   # paper_id 少了空格
        info = sp.get_title_info(r)
        self.assertEqual(info["source_title"], "MOFs 基材料在超级电容器中的应用")
        # canonical 用 source_title (可靠), paper_id 单独可从 pr.paper_id 读取
        self.assertEqual(info["canonical_title"], "MOFs 基材料在超级电容器中的应用")
        self.assertNotEqual(info["source_title"], r.paper_id,
                            "expected inconsistency between source_title and paper_id")

    # ---------- 回归 ----------

    def test_v1_1_1_regression_full_coverage_on_all_10_papers(self):
        """回归: v1.1.1 微调不应破坏 test_run_01 10 篇的 100% 章节覆盖率.

        直接对 10 篇 full.md 重跑内存解析, 覆盖率必须仍为 1.0.
        """
        import sys as _sys
        import os as _os
        this_dir = _os.path.dirname(_os.path.abspath(__file__))
        v2_dir = _os.path.dirname(this_dir)
        src_gr_dir = _os.path.dirname(v2_dir)
        if src_gr_dir not in _sys.path:
            _sys.path.insert(0, src_gr_dir)
        from method_evolution_v2 import config as _cfg  # noqa
        missing = []
        for pid in _cfg.TEST_RUN_01_PAPER_IDS:
            md_path = _cfg.full_md_path(pid)
            if not _os.path.isfile(md_path):
                missing.append(pid)
                continue
            r = sp.parse_file(pid, md_path)
            self.assertEqual(
                r.section_coverage_ratio, 1.0,
                f"coverage regressed for {pid}: {r.section_coverage_ratio}",
            )
            self.assertFalse(r.has_text_loss, f"has_text_loss True for {pid}")
        # 若在测试环境里没有 full.md, 跳过而不 Fail (方便离线跑单测)
        if missing == list(_cfg.TEST_RUN_01_PAPER_IDS):
            self.skipTest("no test_run_01 full.md present in this environment")

    # ============================================================
    # 原有 v1.1 测试 (向下继续)
    # ============================================================

    def test_char_offset_preserved_with_inline_abstract(self):
        """10. 即使内联摘要被 splice, 段落 char_offset 仍能精确回到原文."""
        text = (
            "# 论文标题\n\n"
            "作者\n\n"
            "摘要：摘要内容足够多以满足最小字符数, A B C D E F G H I J K L M N。\n"
            "关键词：A；B\n\n"
            "# 1 实验\n实验内容\n\n实验第二段\n"
        )
        r = sp.parse_text("p", text)
        self._assert_full_coverage(text, r)
        self._assert_paragraphs_match_source(text, r)
        # 找内联 abstract 段落, 验证其切片
        ab = next(s for s in r.sections if s.section_type == "abstract")
        slice_text = text[ab.char_start:ab.char_end]
        self.assertIn("摘要内容足够多", slice_text)
        # 段落切片回原文一致
        for p in ab.paragraphs:
            self.assertEqual(text[p.char_start:p.char_end][:len(p.text)] or p.text, p.text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
