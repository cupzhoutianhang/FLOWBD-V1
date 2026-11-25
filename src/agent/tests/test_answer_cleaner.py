"""answer_cleaner.py 单元测试.

跑法(项目根目录):
    python -m unittest src.agent.tests.test_answer_cleaner -v
或
    cd src/agent && python -m unittest tests.test_answer_cleaner -v
"""
from __future__ import annotations

import os
import sys
import unittest

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_AGENT_DIR = os.path.dirname(_THIS_DIR)
if _AGENT_DIR not in sys.path:
    sys.path.insert(0, _AGENT_DIR)

from answer_cleaner import (
    clean_final_answer,
    clean_empty_sources,
    fix_range_symbols,
    strip_meta_commentary,
)


BANNED_PHRASES = ("我需要确保", "草稿", "检查格式", "现在写最终回答")


class TestStripMetaCommentary(unittest.TestCase):
    """核心 spec: 最终答案里不出现规划/自检/草稿短语."""

    def test_removes_banned_phrases_verbatim(self):
        raw = (
            "我需要确保回答严谨。\n"
            "草稿: 石蜡在实际封装中会遇到泄漏问题。\n"
            "让我检查格式一下。\n"
            "现在写最终回答:\n"
            "石蜡类相变材料在实际封装中主要面临泄漏问题。\n"
            "多孔碳基质通过毛细管力将其物理限域, 抑制固-液泄漏。"
        )
        out = clean_final_answer(raw)
        for phrase in BANNED_PHRASES:
            self.assertNotIn(phrase, out,
                             f"清洗后仍包含 banned phrase: {phrase!r}")
        # 真答案要保留
        self.assertIn("石蜡类相变材料", out)
        self.assertIn("多孔碳", out)

    def test_final_boundary_marker_cuts_prefix(self):
        raw = (
            "让我先梳理一下要点。\n"
            "首先，我需要理清 A、B、C 三个方面。\n"
            "这样应该更清晰了。\n\n"
            "以下是最终回答:\n\n"
            "石蜡的 melting point 约 40-60°C, 直接封装易泄漏。"
        )
        out = clean_final_answer(raw)
        self.assertNotIn("我需要", out)
        self.assertNotIn("让我", out)
        self.assertNotIn("这样应该", out)
        self.assertIn("石蜡", out)

    def test_multi_draft_dropped(self):
        raw = (
            "或者: 石蜡的关键问题是 A。\n"
            "这样更好: 石蜡的问题主要在 B。\n\n"
            "石蜡类相变材料的核心问题是固-液相变过程中的泄漏, "
            "并可通过多孔碳基质加以解决。"
        )
        out = clean_final_answer(raw)
        self.assertNotIn("或者", out)
        self.assertNotIn("这样更好", out)
        self.assertIn("固-液相变", out)

    def test_idempotent(self):
        raw = "我需要确保准确。\n草稿: X。\n现在写最终回答:\n真正的答案。"
        once = clean_final_answer(raw)
        twice = clean_final_answer(once)
        self.assertEqual(once, twice)

    def test_empty_input_safe(self):
        self.assertEqual(clean_final_answer(""), "")
        self.assertEqual(clean_final_answer(None), None)

    def test_pure_answer_untouched(self):
        raw = (
            "石蜡类相变材料的核心挑战是固-液相变过程中的泄漏与体积膨胀问题 [Ref-1]。\n"
            "复合多孔碳基质通过毛细管力实现物理限域, 显著抑制泄漏 [Ref-2]。"
        )
        out = clean_final_answer(raw)
        self.assertIn("石蜡", out)
        self.assertIn("[Ref-1]", out)
        self.assertIn("[Ref-2]", out)


class TestFixRangeSymbols(unittest.TestCase):
    """区间符号修复."""

    def test_percent_range(self):
        self.assertIn("40%～60%", fix_range_symbols("熔化温度约 40%60% 之间"))

    def test_decimal_multiplier(self):
        self.assertIn("1.4～2.0倍",
                     fix_range_symbols("导热系数提升 1.42.0倍 显著"))

    def test_integer_temperature_range(self):
        self.assertIn("300～400℃",
                     fix_range_symbols("熔化温度处于 300400℃ 区间"))

    def test_does_not_break_single_number(self):
        self.assertEqual(fix_range_symbols("温度 350℃"), "温度 350℃")
        self.assertEqual(fix_range_symbols("提升 1.5 倍"), "提升 1.5 倍")
        self.assertEqual(fix_range_symbols("含量 30%"), "含量 30%")

    def test_idempotent_range(self):
        s = "40%～60%"
        self.assertEqual(fix_range_symbols(s), s)


class TestCleanEmptySources(unittest.TestCase):
    """空【文献来源】节的处理."""

    def test_empty_bracketed_header_removed(self):
        raw = "石蜡的问题包括泄漏。\n\n【文献来源】\n\n"
        out = clean_empty_sources(raw, sources=None)
        self.assertNotIn("【文献来源】", out)
        self.assertIn("石蜡", out)

    def test_empty_dashed_header_removed(self):
        raw = "石蜡的问题包括泄漏。\n\n——— 文献来源 ———\n"
        out = clean_empty_sources(raw, sources=None)
        self.assertNotIn("文献来源", out)

    def test_non_empty_body_preserved(self):
        raw = ("答案在此。\n\n【文献来源】\n"
               "[Ref-1] 石蜡相变材料研究进展")
        out = clean_empty_sources(raw, sources=None)
        self.assertIn("石蜡相变材料研究进展", out)
        self.assertIn("【文献来源】", out)

    def test_backfill_from_refs_and_sources(self):
        raw = "答案 [Ref-1] 和 [Ref-2] 支持之。\n\n【文献来源】\n"
        sources = [
            {"title": "石蜡基复合相变材料研究"},
            {"filename": "多孔碳导热强化文献.pdf"},
        ]
        out = clean_empty_sources(raw, sources=sources)
        self.assertIn("石蜡基复合相变材料研究", out)
        self.assertIn("多孔碳导热强化文献.pdf", out)
        self.assertIn("[Ref-1]", out)
        self.assertIn("[Ref-2]", out)


class TestIntegration(unittest.TestCase):
    """打包场景: 一段真实模型泄漏输出."""

    def test_realistic_leaked_draft(self):
        raw = (
            "我需要确保回答按四段式给出。\n"
            "草稿版本1:\n"
            "石蜡的泄漏问题主要是 40%60% 熔化后液态外溢。\n\n"
            "让我重新写一下:\n"
            "石蜡类相变材料 (PCM) 在实际封装中面临固-液相变泄漏, "
            "熔化温度 40%～60% 时液态石蜡易外溢 [Ref-1]。\n"
            "复合多孔碳基质 (膨胀石墨、生物质碳等) 通过毛细管力将石蜡物理限域, "
            "导热系数提升 1.42.0倍 [Ref-2]。\n\n"
            "检查一下格式对不对。\n\n"
            "【文献来源】\n"
        )
        sources = [
            {"title": "石蜡相变材料泄漏机理"},
            {"title": "膨胀石墨/石蜡复合导热研究"},
        ]
        out = clean_final_answer(raw, sources=sources)

        # 元评论全清
        for phrase in BANNED_PHRASES:
            self.assertNotIn(phrase, out, f"仍残留 {phrase!r}")
        self.assertNotIn("草稿版本", out)
        self.assertNotIn("让我重新写", out)
        self.assertNotIn("检查一下", out)

        # 区间修好
        self.assertIn("1.4～2.0倍", out)
        # 40%~60% 原文已有 ~, 应保留
        self.assertIn("40%～60%", out)

        # 文献补齐
        self.assertIn("石蜡相变材料泄漏机理", out)
        self.assertIn("膨胀石墨", out)

        # 真答案保留
        self.assertIn("[Ref-1]", out)
        self.assertIn("[Ref-2]", out)
        self.assertIn("多孔碳", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
