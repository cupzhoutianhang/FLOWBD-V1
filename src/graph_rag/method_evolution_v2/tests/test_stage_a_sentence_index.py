"""Stage A v2 - 句子索引 + ID 引用 + 充分性检查 单测.

覆盖 spec 二/四/五 全部关键规则:
  - 句子索引 char_start/end 精确切回 full.md
  - 不改写原文
  - 无 CJK 句末标点的公式块保留为独立句子
  - resolve_method_by_sentence_ids 各种分支
  - check_evidence_sufficiency 各种边界
"""
from __future__ import annotations

import os
import sys
import unittest

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
V2_DIR = os.path.dirname(THIS_DIR)
SRC_GRAPH_RAG_DIR = os.path.dirname(V2_DIR)
if SRC_GRAPH_RAG_DIR not in sys.path:
    sys.path.insert(0, SRC_GRAPH_RAG_DIR)

from method_evolution_v2.stage_a import sentence_indexer as si          # noqa: E402
from method_evolution_v2.stage_a import evidence_validation as ev       # noqa: E402


def _make_sections_json(sections):
    """helper: 输入 list of (section_type, section_name, [(para_id, text, abs_char_start), ...])."""
    out = {"sections": []}
    for st, name, paras in sections:
        para_dicts = []
        for pid, text, cs in paras:
            para_dicts.append({
                "para_id": pid,
                "text": text,
                "char_start": cs,
                "char_end": cs + len(text),
            })
        out["sections"].append({
            "section_type": st,
            "raw_heading": name,
            "paragraphs": para_dicts,
        })
    return out


class TestSentenceIndexer(unittest.TestCase):

    def test_split_paragraph_basic(self):
        para = "本文采用溶胶-凝胶法制备正极。产物在 800°C 煅烧。"
        r = si.split_paragraph_to_sentences(para)
        texts = [t for t, _, _ in r]
        self.assertEqual(len(r), 2)
        self.assertEqual(texts[0], "本文采用溶胶-凝胶法制备正极。")
        self.assertEqual(texts[1], "产物在 800°C 煅烧。")

    def test_split_preserves_char_offsets_within_paragraph(self):
        para = "第一句。第二句。第三句。"
        r = si.split_paragraph_to_sentences(para)
        for text, s, e in r:
            self.assertEqual(para[s:e], text, "local slice must equal sentence")

    def test_split_keeps_punctuation_attached(self):
        para = "AAA。BBB。"
        r = si.split_paragraph_to_sentences(para)
        self.assertEqual(r[0][0], "AAA。")
        self.assertEqual(r[1][0], "BBB。")

    def test_split_no_cjk_period_keeps_whole_paragraph(self):
        """公式块保护: 无 CJK 句末标点 -> 整段作为单句."""
        para = "SiO2 + H2O -> ..."   # 无 。 / ！ / ？
        r = si.split_paragraph_to_sentences(para)
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0][0], para)

    def test_split_ignores_ascii_period(self):
        """避免误切 1.2.3 / SiO2·H2O / decimal 值."""
        para = "版本号 1.2.3, 温度 25.5 C. 没有中文句号."
        r = si.split_paragraph_to_sentences(para)
        # 无 CJK 句末标点, 应保留为单句
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0][0], para)

    def test_build_sentence_index_char_offsets_match_full_md(self):
        """spec 二.2 硬要求: char_start/end 必须精确切回 full.md."""
        # 构造 "full.md" 并让 paragraph.char_start 与之对齐
        full_md = (
            "# 论文标题\n"
            "\n"
            "# 摘要\n"
            "本文提出一种方法。测试性能。\n"
            "\n"
            "# 1 实验\n"
            "采用溶胶-凝胶法。煅烧 2 小时。\n"
        )
        # 段落绝对偏移
        p1_txt = "本文提出一种方法。测试性能。\n"
        p1_start = full_md.find(p1_txt)
        p2_txt = "采用溶胶-凝胶法。煅烧 2 小时。\n"
        p2_start = full_md.find(p2_txt)

        sj = _make_sections_json([
            ("abstract", "摘要", [("abstract_01_p01", p1_txt, p1_start)]),
            ("methods", "1 实验", [("methods_02_p01", p2_txt, p2_start)]),
        ])
        sents = si.build_sentence_index(sj, "p-x")
        # 每个 sentence 的 slice-back 必须 = sentence_text
        for s in sents:
            self.assertEqual(
                full_md[s.char_start:s.char_end], s.sentence_text,
                f"slice mismatch for {s.sentence_id}",
            )
        ok, mismatches = si.verify_sentence_slices(sents, full_md)
        self.assertTrue(ok, f"mismatches: {mismatches}")

    def test_verify_sentence_slices_detects_mismatch(self):
        sj = _make_sections_json([
            ("methods", "1 实验", [("methods_01_p01", "第一句。第二句。", 100)]),
        ])
        sents = si.build_sentence_index(sj, "p-y")
        # 我们没提供真正的 full_md_text; 用 "" 触发 out-of-range
        ok, mismatches = si.verify_sentence_slices(sents, "")
        self.assertFalse(ok)
        self.assertEqual(len(mismatches), len(sents))

    def test_sentence_ids_unique_and_stable(self):
        sj = _make_sections_json([
            ("abstract", "摘要", [("abstract_00_p01", "摘要。摘要 2。", 0)]),
            ("methods", "1 实验", [("methods_01_p01", "方法 1。方法 2。", 100)]),
        ])
        sents = si.build_sentence_index(sj, "pid")
        ids = [s.sentence_id for s in sents]
        self.assertEqual(len(ids), len(set(ids)), "sentence_ids must be unique")

    def test_sentence_index_to_pack_shape(self):
        sj = _make_sections_json([
            ("methods", "1 实验", [("methods_01_p01",
                                    "本文采用溶胶-凝胶法制备。", 0)]),
        ])
        sents = si.build_sentence_index(sj, "pid")
        pack = si.sentence_index_to_pack(sents)
        self.assertIn("[methods]", pack)
        self.assertIn(sents[0].sentence_id, pack)
        # 「」包裹保护
        self.assertIn("「", pack)
        self.assertIn("」", pack)


class TestSufficiency(unittest.TestCase):

    def test_sufficient_when_concrete_signal(self):
        r = ev.check_evidence_sufficiency("本文采用溶胶-凝胶法制备了正极材料并煅烧成型。")
        self.assertTrue(r["sufficient"])
        self.assertTrue(any(k in r["concrete_signal_hits"]
                            for k in ("溶胶", "制备")))

    def test_insufficient_weak_only(self):
        r = ev.check_evidence_sufficiency("该方法受到广泛关注, 具有前景。")
        self.assertFalse(r["sufficient"])
        self.assertEqual(r["reason"], "only_weak_or_generic_signals")

    def test_insufficient_only_citation(self):
        r = ev.check_evidence_sufficiency("[15]")
        self.assertFalse(r["sufficient"])
        self.assertTrue(r["only_citation"])

    def test_insufficient_only_material_name(self):
        r = ev.check_evidence_sufficiency("LFP")
        self.assertFalse(r["sufficient"])
        self.assertTrue(r["only_material_name"])

    def test_insufficient_neutral_description(self):
        r = ev.check_evidence_sufficiency("很多研究者在这一方面开展了工作。")
        self.assertFalse(r["sufficient"])


class TestResolveByIds(unittest.TestCase):

    def _make_index(self, text_and_ids):
        """helper: 构造 sentence_index dict."""
        idx = {}
        cur = 0
        for sid, text in text_and_ids:
            idx[sid] = {
                "sentence_id": sid,
                "paper_id": "p",
                "section_type": "methods",
                "section_name": "1 实验",
                "para_id": "methods_00_p01",
                "sentence_text": text,
                "char_start": cur,
                "char_end": cur + len(text),
            }
            cur += len(text)
        return idx

    def test_accepted_single_id_sufficient(self):
        idx = self._make_index([
            ("methods_p1_s1", "本文采用溶胶-凝胶法制备了钙钛矿高熵氧化物 Cu 空位电极。"),
        ])
        raw = {
            "name": "钙钛矿高熵氧化物 Cu 空位电极溶胶-凝胶法",
            "proposed_method_type": "synthesis_process",
            "problem_solved": "构建 Cu 空位以提升储锂比容量",
            "key_components": ["Cu 空位", "钙钛矿"],
            "evidence_sentence_ids": ["methods_p1_s1"],
            "citation_clue": "", "confidence_llm": "high",
        }
        r = ev.resolve_method_by_sentence_ids(raw, idx, kind="own")
        self.assertEqual(r["validation_status"], "accepted")
        self.assertEqual(r["evidence_match_status"], "sentence_id_exact")
        self.assertEqual(r["rejected_reason"], "")
        # evidence_quote 由代码从索引拼出, 应等于句子文本
        self.assertEqual(r["evidence_quote"],
                         "本文采用溶胶-凝胶法制备了钙钛矿高熵氧化物 Cu 空位电极。")

    def test_rejected_when_all_ids_missing(self):
        idx = self._make_index([("methods_p1_s1", "real sentence.")])
        raw = {
            "name": "some method",
            "evidence_sentence_ids": ["fake_p9_s9", "another_fake"],
        }
        r = ev.resolve_method_by_sentence_ids(raw, idx, kind="own")
        self.assertEqual(r["validation_status"], "rejected")
        self.assertIn("all_evidence_ids_missing", r["rejected_reason"])
        self.assertEqual(r["evidence_missing_ids"], ["fake_p9_s9", "another_fake"])

    def test_rejected_when_partial_ids_missing(self):
        idx = self._make_index([
            ("methods_p1_s1", "本文采用溶胶-凝胶法制备了电极材料。"),
        ])
        raw = {
            "name": "some method",
            "evidence_sentence_ids": ["methods_p1_s1", "fake_id"],
        }
        r = ev.resolve_method_by_sentence_ids(raw, idx, kind="own")
        # spec 四: 部分 ID 不存在 → rejected
        self.assertEqual(r["validation_status"], "rejected")
        self.assertIn("partial_evidence_ids_missing", r["rejected_reason"])
        self.assertEqual(r["evidence_missing_ids"], ["fake_id"])

    def test_candidate_when_evidence_insufficient(self):
        """ID 都存在但证据只是"受到关注" → candidate."""
        idx = self._make_index([
            ("methods_p1_s1", "MOFs 材料因高比表面积在储能领域受到广泛关注具有前景。"),
        ])
        raw = {
            "name": "MOFs 电极材料设计",
            "evidence_sentence_ids": ["methods_p1_s1"],
        }
        r = ev.resolve_method_by_sentence_ids(raw, idx, kind="own")
        self.assertEqual(r["validation_status"], "candidate")
        self.assertTrue(any("insufficient_evidence" in x
                            for x in r["rejected_reason"].split(",")))

    def test_rejected_when_no_ids(self):
        idx = self._make_index([("methods_p1_s1", "some text with 溶胶-凝胶.")])
        raw = {"name": "some method", "evidence_sentence_ids": []}
        r = ev.resolve_method_by_sentence_ids(raw, idx, kind="own")
        self.assertEqual(r["validation_status"], "rejected")
        self.assertIn("no_evidence_ids", r["rejected_reason"])

    def test_multi_span_merges_contiguous(self):
        """连续两句应合成单 span; evidence_char_end - char_start = span 覆盖."""
        # 让两句在同一 para 内, offset 紧邻
        idx = {
            "methods_p1_s1": {
                "sentence_id": "methods_p1_s1", "paper_id": "p",
                "section_type": "methods", "section_name": "1 实验",
                "para_id": "methods_00_p01",
                "sentence_text": "本文提出了一种设计。",
                "char_start": 100, "char_end": 110,
            },
            "methods_p1_s2": {
                "sentence_id": "methods_p1_s2", "paper_id": "p",
                "section_type": "methods", "section_name": "1 实验",
                "para_id": "methods_00_p01",
                "sentence_text": "该设计通过溶胶-凝胶法实现。",
                "char_start": 110, "char_end": 125,
            },
        }
        raw = {
            "name": "溶胶-凝胶法某设计",
            "evidence_sentence_ids": ["methods_p1_s1", "methods_p1_s2"],
        }
        r = ev.resolve_method_by_sentence_ids(raw, idx, kind="own")
        self.assertEqual(r["validation_status"], "accepted")
        # 合并成一个 span
        self.assertEqual(len(r["evidence_spans"]), 1)
        self.assertEqual(r["evidence_char_start"], 100)
        self.assertEqual(r["evidence_char_end"], 125)

    def test_multi_span_non_contiguous_kept_separate(self):
        idx = {
            "methods_p1_s1": {
                "sentence_id": "methods_p1_s1", "paper_id": "p",
                "section_type": "methods", "section_name": "1 实验",
                "para_id": "methods_00_p01",
                "sentence_text": "本文提出了溶胶-凝胶法。",
                "char_start": 100, "char_end": 111,
            },
            "results_p5_s2": {
                "sentence_id": "results_p5_s2", "paper_id": "p",
                "section_type": "results", "section_name": "2 结果",
                "para_id": "results_01_p05",
                "sentence_text": "结果表明制备的电极循环稳定。",
                "char_start": 500, "char_end": 512,
            },
        }
        raw = {
            "name": "溶胶-凝胶法制备电极",
            "evidence_sentence_ids": ["methods_p1_s1", "results_p5_s2"],
        }
        r = ev.resolve_method_by_sentence_ids(raw, idx, kind="own")
        self.assertEqual(r["validation_status"], "accepted")
        # 两个 span (不同 para, 非相邻 offset)
        self.assertEqual(len(r["evidence_spans"]), 2)

    def test_own_from_only_introduction_becomes_candidate(self):
        """own method 只有 introduction 证据 → candidate (章节位置弱)."""
        idx = {
            "introduction_p1_s1": {
                "sentence_id": "introduction_p1_s1", "paper_id": "p",
                "section_type": "introduction", "section_name": "引言",
                "para_id": "introduction_00_p01",
                "sentence_text": "本文提出了一种全新的溶胶-凝胶法制备电极。",
                "char_start": 0, "char_end": 20,
            },
        }
        raw = {
            "name": "溶胶-凝胶法制备电极",
            "evidence_sentence_ids": ["introduction_p1_s1"],
        }
        r = ev.resolve_method_by_sentence_ids(raw, idx, kind="own")
        # own 应优先 methods/results/... 类章节; introduction 位置弱
        self.assertEqual(r["validation_status"], "candidate")
        self.assertTrue(any("weak_section_context" in x
                            for x in r["rejected_reason"].split(",")))

    def test_referenced_from_introduction_ok(self):
        """referenced 允许来自 introduction/other_sections."""
        idx = {
            "introduction_p1_s1": {
                "sentence_id": "introduction_p1_s1", "paper_id": "p",
                "section_type": "introduction", "section_name": "引言",
                "para_id": "introduction_00_p01",
                "sentence_text": "Smith 等人提出溶胶-凝胶法合成 MOF。",
                "char_start": 0, "char_end": 18,
            },
        }
        raw = {
            "name": "Smith 溶胶-凝胶法 MOF 合成",
            "evidence_sentence_ids": ["introduction_p1_s1"],
        }
        r = ev.resolve_method_by_sentence_ids(raw, idx, kind="referenced")
        self.assertEqual(r["validation_status"], "accepted")


if __name__ == "__main__":
    unittest.main(verbosity=2)
