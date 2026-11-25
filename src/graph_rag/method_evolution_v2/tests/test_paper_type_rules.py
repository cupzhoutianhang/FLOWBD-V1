"""单元测试: paper_type_rules 分类器.

覆盖 spec 七的全部场景:
  - 典型综述标题
  - "应用" 标题不能单独判综述
  - 实验研究论文
  - 系统建模论文
  - 仿真论文
  - 专利分析
  - 信号冲突
  - 证据不足返回 unclear
  - 缺少摘要时不崩溃
  - 不允许根据 paper_id 白名单硬编码结果 (源码扫描)
"""
from __future__ import annotations

import inspect
import os
import re
import sys
import unittest

# import 路径
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
V2_DIR = os.path.dirname(THIS_DIR)
SRC_GRAPH_RAG_DIR = os.path.dirname(V2_DIR)
SRC_DIR = os.path.dirname(SRC_GRAPH_RAG_DIR)
PROJECT_ROOT = os.path.dirname(SRC_DIR)
if SRC_GRAPH_RAG_DIR not in sys.path:
    sys.path.insert(0, SRC_GRAPH_RAG_DIR)

from method_evolution_v2.io import section_parser as sp  # noqa: E402
from method_evolution_v2.paper_type import paper_type_rules as ptr  # noqa: E402


# ============================================================
# 构造 ParseResult 的辅助 (借直接组装, 避开对文件的依赖)
# ============================================================

def make_section(index, section_type, raw_heading="", paragraphs_text=(),
                 heading_level=1, char_start=0, char_end=0,
                 confidence="high", inference_source="keyword"):
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
        confidence=confidence,
        matched_by_markdown_heading=(heading_level > 0),
        inferred_by_regex=(inference_source != "keyword"),
        inference_source=inference_source,
        paragraphs=paragraphs,
    )


def make_parse_result(paper_id, title, sections):
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


# 便捷: 生成 [title, abstract, ...body sections] 的 ParseResult
def build_paper(paper_id, title, abstract_text="", body_sections=()):
    sections = [make_section(0, "title", raw_heading=title,
                             paragraphs_text=(title,))]
    if abstract_text:
        sections.append(make_section(1, "abstract", raw_heading="摘要：",
                                     paragraphs_text=(abstract_text,),
                                     heading_level=0,
                                     inference_source="inline_abstract_cn_colon"))
    idx = len(sections)
    for section_type, heading, text in body_sections:
        sections.append(make_section(idx, section_type,
                                     raw_heading=heading,
                                     paragraphs_text=(text,)))
        idx += 1
    return make_parse_result(paper_id, title, sections)


# ============================================================
# 测试
# ============================================================

class TestPaperTypeRules(unittest.TestCase):

    # ---------- spec 七.1: 典型综述标题 ----------

    def test_typical_review_title_yanjiu_jinzhan(self):
        pr = build_paper(
            paper_id="p-review-1",
            title="钠离子电池正极材料研究进展",
            abstract_text=("本文对现有的钠离子电池正极材料进行了系统性的归纳, "
                           "首先介绍了各类正极材料的结构和电化学特性..."),
            body_sections=(
                ("other_sections", "1 层状氧化物材料", "层状氧化物内容"),
                ("other_sections", "2 磷酸盐正极材料", "磷酸盐内容"),
                ("conclusion", "4 结语", "结语内容"),
                ("references", "参考文献", "[1] ..."),
            ),
        )
        r = ptr.classify_paper_type(pr)
        self.assertEqual(r["paper_type"], "review_article")
        self.assertEqual(r["rule_confidence"], "high")
        keys = [m["key"] for m in r["matched_signals"]]
        self.assertIn("review_title_strong", keys)
        self._assert_evidence_valid(r, {"title", "abstract", "section_heading"})

    def test_typical_review_zongshu_in_title(self):
        pr = build_paper(
            paper_id="p-review-2",
            title="锂硫电池正极综述",
            abstract_text=("本文综述了近五年锂硫电池正极的研究进展, "
                           "阐述了硫载体材料的类型与改进方向..."),
        )
        r = ptr.classify_paper_type(pr)
        self.assertEqual(r["paper_type"], "review_article")
        self.assertEqual(r["rule_confidence"], "high")

    # ---------- spec 七.2: "应用" 标题不能单独判综述 ----------

    def test_yingyong_title_alone_is_not_review(self):
        pr = build_paper(
            paper_id="p-app-1",
            title="MOFs 材料在超级电容器中的应用",
            abstract_text="本文考察了 MOFs 若干性能指标.",
            body_sections=(
                ("other_sections", "1 一些子标题", "内容"),
            ),
        )
        r = ptr.classify_paper_type(pr)
        # 关键: 不应输出 review_article
        self.assertNotEqual(r["paper_type"], "review_article",
                            "应用 单独不能判 review")
        # 应为 unclear
        self.assertEqual(r["paper_type"], "unclear")

    def test_fazhan_qushi_title_alone_is_not_review(self):
        pr = build_paper(
            paper_id="p-fz-1",
            title="液流电池的发展趋势",
            abstract_text="综合分析液流电池未来的技术走向.",
        )
        r = ptr.classify_paper_type(pr)
        self.assertNotEqual(r["paper_type"], "review_article",
                            "发展趋势 单独不能判 review")
        self.assertEqual(r["paper_type"], "unclear")

    # ---------- spec 七.3: 实验研究论文 ----------

    def test_experimental_research_high(self):
        """典型实验-结果-结论结构 → research high."""
        pr = build_paper(
            paper_id="p-exp-1",
            title="某种新型电极材料的制备与储能性能研究",
            abstract_text=("本研究采用溶胶-凝胶法制备了某材料, 结果表明其比容量达 200 mAh/g."),
            body_sections=(
                ("methods", "1 实验", "实验部分"),
                ("results_discussion", "2 结果与讨论", "结果分析"),
                ("conclusion", "3 结论", "结论内容"),
            ),
        )
        r = ptr.classify_paper_type(pr)
        self.assertEqual(r["paper_type"], "research_article")
        self.assertEqual(r["rule_confidence"], "high")
        keys = [m["key"] for m in r["matched_signals"]]
        self.assertIn("R1_methods_and_results", keys)

    # ---------- spec 七.4: 系统建模论文 (无 实验 章节) ----------

    def test_system_modeling_paper_no_experiment(self):
        """系统建模: theory_model + case_analysis (模型验证) + conclusion → research high."""
        pr = build_paper(
            paper_id="p-sys-1",
            title="光热-跨临界压缩二氧化碳储能循环动态特性研究",
            abstract_text=("提出了一种光热跨临界压缩二氧化碳储能循环, "
                           "分别建立TC-CCES系统与光热系统的动态数学模型."),
            body_sections=(
                ("theory_model", "2 数学模型", "模型方程"),
                ("case_analysis", "3 模型验证", "模型对比实测"),
                ("case_analysis", "4 动态特性分析", "参数扫描"),
                ("conclusion", "5 结论", "结论内容"),
            ),
        )
        r = ptr.classify_paper_type(pr)
        self.assertEqual(r["paper_type"], "research_article")
        self.assertEqual(r["rule_confidence"], "high")
        keys = [m["key"] for m in r["matched_signals"]]
        self.assertIn("R2_theory_and_verify", keys)

    # ---------- spec 七.5: 仿真论文 ----------

    def test_simulation_paper(self):
        """仿真: simulation_calculation + 标题含 '仿真分析' → research medium (无 R1/R2)."""
        pr = build_paper(
            paper_id="p-sim-1",
            title="SMES超导磁体动态载荷温度场仿真分析",
            abstract_text="",   # 摘要缺失也不能崩
            body_sections=(
                ("simulation_calculation", "3 温度场数值模拟及其分析", "模拟结果"),
                ("conclusion", "9 结论", "结论"),
            ),
        )
        r = ptr.classify_paper_type(pr)
        self.assertEqual(r["paper_type"], "research_article")
        # R3 或 R4_title 满足 (仿真分析)
        keys = [m["key"] for m in r["matched_signals"]]
        self.assertTrue(
            "R3_system_or_simulation" in keys or "R4_title_research_verbs" in keys,
            f"expected R3 or R4_title in {keys}",
        )

    # ---------- spec 七.6: 专利分析 ----------

    def test_patent_analysis_by_title(self):
        pr = build_paper(
            paper_id="p-pat-1",
            title="二氧化硅基气凝胶材料及其制备技术的专利分析",
            abstract_text=("本文梳理了近20年全球二氧化硅基气凝胶材料及其制备技术的相关专利, "
                           "从市场流向和重点申请人的维度分析当前的市场竞争格局."),
            body_sections=(
                ("methods", "研究方法及数据范围", "检索式与范围"),
                ("patent_analysis", "2 专利分析", "IPC 分类 / 申请人分布 / 技术路线"),
                ("conclusion", "3 结语", "结语"),
            ),
        )
        r = ptr.classify_paper_type(pr)
        self.assertEqual(r["paper_type"], "patent_analysis")
        self.assertEqual(r["rule_confidence"], "high")
        keys = [m["key"] for m in r["matched_signals"]]
        self.assertIn("patent_title_strong", keys)

    def test_patent_analysis_by_section_and_body(self):
        """标题无专利强信号, 但存在 patent_analysis 章节 + 正文有多个专利关键词."""
        pr = build_paper(
            paper_id="p-pat-2",
            title="某材料的技术演进",
            abstract_text="综述性介绍",
            body_sections=(
                ("patent_analysis", "2 专利统计",
                 "本节按 IPC 分类统计申请人, 分析技术路线, 授权公告数量对比."),
                ("conclusion", "3 结论", "结论"),
            ),
        )
        r = ptr.classify_paper_type(pr)
        self.assertEqual(r["paper_type"], "patent_analysis")
        keys = [m["key"] for m in r["matched_signals"]]
        self.assertIn("patent_section_and_body", keys)

    # ---------- spec 七.7: 信号冲突 ----------

    def test_conflict_review_title_but_research_structure(self):
        """title 有 '研究进展', 但结构有 methods+results — 记录冲突, 判 review medium."""
        pr = build_paper(
            paper_id="p-conflict-1",
            title="某新方法研究进展",
            abstract_text="本研究提出了一种新方法, 通过实验验证其性能.",
            body_sections=(
                ("methods", "1 实验", "实验"),
                ("results_discussion", "2 结果与讨论", "结果"),
                ("conclusion", "3 结论", "结论"),
            ),
        )
        r = ptr.classify_paper_type(pr)
        self.assertEqual(r["paper_type"], "review_article")
        self.assertEqual(r["rule_confidence"], "medium")
        conflict_keys = [c["key"] for c in r["conflicting_signals"]]
        self.assertIn("review_title_strong_vs_research_structure", conflict_keys)

    def test_conflict_research_but_abstract_review_markers(self):
        """结构 = methods+results, 但摘要里 ≥2 个 review 标记 — 降为 research medium 并记录冲突."""
        pr = build_paper(
            paper_id="p-conflict-2",
            title="某材料的制备与性能",
            abstract_text=("本文综述了近年来的研究进展, 阐述了主流路线; 本工作制备了 X 材料."),
            body_sections=(
                ("methods", "1 实验", "实验"),
                ("results", "2 结果", "结果"),
                ("conclusion", "3 结论", "结论"),
            ),
        )
        r = ptr.classify_paper_type(pr)
        self.assertEqual(r["paper_type"], "research_article")
        self.assertEqual(r["rule_confidence"], "medium")
        conflict_keys = [c["key"] for c in r["conflicting_signals"]]
        self.assertIn("research_structure_vs_abstract_review_markers", conflict_keys)

    # ---------- spec 七.8: 证据不足返回 unclear ----------

    def test_unclear_when_no_signals(self):
        pr = build_paper(
            paper_id="p-empty-1",
            title="一个模糊的标题",
            abstract_text="一段中性描述, 没有研究动作也没有综述标记.",
            body_sections=(
                ("other_sections", "1 某个小节", "内容"),
            ),
        )
        r = ptr.classify_paper_type(pr)
        self.assertEqual(r["paper_type"], "unclear")
        self.assertEqual(r["rule_confidence"], "low")

    # ---------- spec 七.9: 缺少摘要时不崩溃 ----------

    def test_missing_abstract_does_not_crash(self):
        pr = build_paper(
            paper_id="p-no-abs-1",
            title="某仿真研究",
            abstract_text="",   # 完全没有摘要
            body_sections=(
                ("simulation_calculation", "2 数值模拟", "内容"),
                ("conclusion", "3 结论", "结论"),
            ),
        )
        # 应该正常输出一个结果 dict, 不抛异常
        r = ptr.classify_paper_type(pr)
        self.assertIn(r["paper_type"], ptr.PAPER_TYPES)
        # 版本号 & 时间戳字段必须存在
        self.assertIn("parser_version", r)
        self.assertIn("classified_at", r)

    def test_missing_abstract_pure_conclusion_only(self):
        """只有 conclusion + 无摘要 + 标题无关键词 → unclear."""
        pr = build_paper(
            paper_id="p-only-concl",
            title="模糊的标题",
            abstract_text="",
            body_sections=(
                ("conclusion", "结论", "结论内容"),
            ),
        )
        r = ptr.classify_paper_type(pr)
        self.assertEqual(r["paper_type"], "unclear")

    # ---------- spec 七.10: 不允许根据 paper_id 白名单硬编码 ----------

    def test_no_paper_id_hardcoding_in_source(self):
        """源码不能出现试运行 10 篇 paper_id 中的任何一个作为字符串常量."""
        src = inspect.getsource(ptr)
        forbidden = [
            "全钒液流电池电堆的均一性",
            "钠离子电池正极材料研究进展",
            "Cu阳离子空位提升钙钛矿型高熵氧化物储锂性能",
            "三水醋酸钠相变储能复合材料改性制备及储_放热特性",
            "光热-跨临界压缩二氧化碳储能循环动态特性研究",
            "基于液氖液氮梯级蓄冷的液氢储能中冷能回收利用研究",
            "MOFs基材料在超级电容器中的应用",
            "MOFs 基材料在超级电容器中的应用",
            "低共熔溶剂在储能与传热方面的研究进展",
            "SMES超导磁体动态载荷温度场仿真分析",
            "二氧化硅基气凝胶材料及其制备技术的专利分析",
        ]
        for pid in forbidden:
            self.assertNotIn(
                pid, src,
                f"paper_type_rules.py must not hardcode paper_id '{pid}'",
            )

    def test_no_paper_id_hardcoding_swap_paper_id_does_not_change_verdict(self):
        """把两篇不同类型论文的 paper_id 互换, 结果不应跟着 paper_id 走."""
        # 一个明显 research
        pr_r = build_paper(
            paper_id="全钒液流电池电堆的均一性",   # 拿一个 test_run_01 里的名字
            title="任意标题",
            abstract_text="",
            body_sections=(
                ("methods", "1 实验", "实验"),
                ("results", "2 结果", "结果"),
                ("conclusion", "3 结论", "结论"),
            ),
        )
        # 一个明显 review
        pr_v = build_paper(
            paper_id="钠离子电池正极材料研究进展",  # 另一个
            title="某方向的研究进展",
            abstract_text="本文综述了...",
        )
        r_r = ptr.classify_paper_type(pr_r)
        r_v = ptr.classify_paper_type(pr_v)
        # 尽管 paper_id 名字暗示相反, 分类完全由内容决定
        self.assertEqual(r_r["paper_type"], "research_article")
        self.assertEqual(r_v["paper_type"], "review_article")

    # ---------- 输出字段完整性 ----------

    def test_output_has_all_required_fields(self):
        pr = build_paper(
            paper_id="p-fields",
            title="某论文",
            abstract_text="内容",
        )
        r = ptr.classify_paper_type(pr)
        for k in ("paper_id", "paper_type", "rule_confidence",
                  "matched_signals", "conflicting_signals", "type_evidence",
                  "decision_reason", "parser_version", "classified_at"):
            self.assertIn(k, r, f"missing field {k}")
        self.assertIsInstance(r["matched_signals"], list)
        self.assertIsInstance(r["conflicting_signals"], list)
        self.assertIsInstance(r["type_evidence"], list)
        # 版本串包含 section_parser + paper_type_rules
        self.assertIn("section_parser=", r["parser_version"])
        self.assertIn("paper_type_rules=", r["parser_version"])

    def test_output_evidence_source_whitelist(self):
        """type_evidence 每条的 source 必须来自白名单."""
        pr = build_paper(
            paper_id="p-ev",
            title="某新方法研究进展",
            abstract_text="本文综述了近年进展",
            body_sections=(
                ("methods", "1 实验", "实验"),
                ("results", "2 结果", "结果"),
            ),
        )
        r = ptr.classify_paper_type(pr)
        allowed = {"title", "abstract", "section_heading"}
        for ev in r["type_evidence"]:
            self.assertIn(ev["source"], allowed,
                          f"evidence source '{ev['source']}' not in {allowed}")

    # ---------- 决策优先级 ----------

    def test_patent_beats_review_when_title_has_both(self):
        """标题同时含 '专利分析' + '研究进展' → patent 优先."""
        pr = build_paper(
            paper_id="p-both-1",
            title="某领域的研究进展及专利分析",
            abstract_text="",
        )
        r = ptr.classify_paper_type(pr)
        self.assertEqual(r["paper_type"], "patent_analysis")

    # ---------- 辅助 ----------

    def _assert_evidence_valid(self, result, allowed_sources):
        self.assertGreater(len(result["type_evidence"]), 0,
                           "must have at least one evidence entry")
        for ev in result["type_evidence"]:
            self.assertIn(ev["source"], allowed_sources)
            self.assertIn("matched_for", ev)
            self.assertIn("excerpt", ev)
            # excerpt 允许为空 (若原文缺失), 但不能是 None
            self.assertIsNotNone(ev["excerpt"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
