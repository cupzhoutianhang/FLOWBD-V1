"""Stage A 证据校验层单测 (不调 LLM).

覆盖:
  - exact / normalized_exact / not_found 三档
  - 名字为无信息词 → rejected
  - 疑似材料名 / 表征 / 宽泛概念 → rejected
  - evidence 短于 20 字 → rejected
  - char_start/end 切片可回原文 (spec 四.5)
  - 同名去重保留证据最完整的一条
  - method_id 稳定生成 (相同输入 → 相同 id)
  - LLM markdown 围栏可被 parse_llm_json 剥掉
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

from method_evolution_v2.stage_a import evidence_validation as ev            # noqa: E402
from method_evolution_v2.stage_a import method_extraction as me              # noqa: E402


def _make_sections(text: str, heading: str = "1 实验部分"):
    """构造最小 sections 结构: 单个 section, 单段落, 有 char offset."""
    para = {
        "para_id": "methods_01_p01",
        "text": text,
        "char_start": 0,
        "char_end": len(text),
    }
    sec = {
        "section_index": 0,
        "section_type": "methods",
        "raw_heading": heading,
        "heading_level": 1,
        "char_start": 0,
        "char_end": len(text),
        "confidence": "high",
        "matched_by_markdown_heading": True,
        "inferred_by_regex": False,
        "inference_source": "keyword",
        "paragraphs": [para],
    }
    return [sec]


class TestEvidenceValidation(unittest.TestCase):

    def test_exact_evidence_locates_char_offsets(self):
        text = "本文采用溶胶-凝胶法制备 LiFePO4 正极材料, 并通过煅烧优化晶粒尺寸。"
        sec = _make_sections(text)
        r = ev.validate_evidence("采用溶胶-凝胶法制备 LiFePO4 正极材料", sec)
        self.assertEqual(r["match_status"], "exact")
        self.assertGreaterEqual(r["char_start"], 0)
        self.assertEqual(r["char_end"] - r["char_start"], len("采用溶胶-凝胶法制备 LiFePO4 正极材料"))
        # 切片能拿回原文
        self.assertEqual(text[r["char_start"]:r["char_end"]],
                         "采用溶胶-凝胶法制备 LiFePO4 正极材料")

    def test_normalized_exact_via_whitespace_diff(self):
        """evidence 里有连续多空格, 原文只有单空格 → normalized_exact."""
        text = "采用溶胶-凝胶法制备正极材料"
        sec = _make_sections(text)
        r = ev.validate_evidence("采用  溶胶-凝胶法  制备  正极材料", sec)
        self.assertEqual(r["match_status"], "normalized_exact")

    def test_not_found_when_evidence_fabricated(self):
        text = "本文研究了电池热管理"
        sec = _make_sections(text)
        r = ev.validate_evidence("完全不存在的一段话来自捏造", sec)
        self.assertEqual(r["match_status"], "not_found")
        self.assertEqual(r["char_start"], -1)

    def test_slice_back_check_exact(self):
        text = "本文提出了一种新型电解液添加剂"
        # text[2:7] = "提出了一种"
        self.assertTrue(ev.slice_back_check(text, 2, 7, "提出了一种"))
        self.assertFalse(ev.slice_back_check(text, 2, 7, "wrong"))
        self.assertFalse(ev.slice_back_check(text, -1, 5, "abc"))
        self.assertFalse(ev.slice_back_check(text, 0, 999, "abc"))   # out of range

    # ---- classify_method 层 ----

    def test_classify_accepted_when_all_good(self):
        text = "本文提出了一种基于溶胶-凝胶法的钙钛矿高熵氧化物 Cu 空位调控设计, 显著提升储锂性能。"
        sec = _make_sections(text)
        m = ev.classify_method({
            "name": "钙钛矿高熵氧化物 Cu 空位调控设计",
            "method_type": "material_design",
            "problem_solved": "提升 Li 存储比容量与循环寿命",
            "key_components": ["Cu 空位", "钙钛矿结构"],
            "evidence_quote": "本文提出了一种基于溶胶-凝胶法的钙钛矿高熵氧化物 Cu 空位调控设计",
            "evidence_section": "1 实验部分",
            "citation_clue": "",
            "confidence_llm": "high",
        }, sec)
        self.assertEqual(m["validation_status"], "accepted")
        self.assertEqual(m["evidence_match_status"], "exact")
        self.assertEqual(m["rejected_reason"], "")

    def test_classify_rejected_noninfo_name(self):
        sec = _make_sections("本文提出了一种全新的方法, 具体内容如下所述。")
        m = ev.classify_method({
            "name": "本方法", "evidence_quote": "本文提出了一种全新的方法, 具体内容如下所述。",
        }, sec)
        self.assertEqual(m["validation_status"], "rejected")
        self.assertIn("noninfo_name", m["rejected_reason"])

    def test_classify_rejected_looks_like_material_only(self):
        sec = _make_sections("研究了 LFP 的循环性能与倍率行为, 具备良好稳定性。")
        m = ev.classify_method({
            "name": "LFP", "evidence_quote": "研究了 LFP 的循环性能与倍率行为, 具备良好稳定性。",
        }, sec)
        self.assertEqual(m["validation_status"], "rejected")
        self.assertIn("looks_like_material_only", m["rejected_reason"])

    def test_classify_rejected_characterization(self):
        sec = _make_sections("采用 XRD 表征分析材料的晶体结构与相纯度。")
        m = ev.classify_method({
            "name": "XRD 表征",
            "evidence_quote": "采用 XRD 表征分析材料的晶体结构与相纯度。",
        }, sec)
        self.assertEqual(m["validation_status"], "rejected")
        self.assertIn("looks_like_characterization", m["rejected_reason"])

    def test_classify_rejected_vague(self):
        sec = _make_sections("本工作旨在提高储能性能, 具体方案有待后续讨论。")
        m = ev.classify_method({
            "name": "提高性能",
            "evidence_quote": "本工作旨在提高储能性能, 具体方案有待后续讨论。",
        }, sec)
        self.assertEqual(m["validation_status"], "rejected")
        self.assertIn("looks_vague", m["rejected_reason"])

    def test_classify_rejected_short_evidence(self):
        sec = _make_sections("测试样品是电极材料。")
        m = ev.classify_method({
            "name": "SPEEK 磺酸基交联离子选择膜",
            "evidence_quote": "太短的证据",   # 少于 20 字
        }, sec)
        self.assertEqual(m["validation_status"], "rejected")
        self.assertIn("evidence_too_short", m["rejected_reason"])

    def test_classify_rejected_evidence_not_locatable(self):
        sec = _make_sections("这是原文里真实存在的一段文本, 足够作为证据。")
        m = ev.classify_method({
            "name": "SPEEK 磺酸基交联离子选择膜",
            "evidence_quote": "完全捏造的证据文本, 不存在于原文当中, 属于假信息证据",
        }, sec)
        self.assertEqual(m["validation_status"], "rejected")
        self.assertIn("evidence_not_locatable", m["rejected_reason"])

    def test_candidate_when_only_normalized_match(self):
        """evidence 因空白差异只能 normalized_exact 命中 → candidate."""
        text = "溶胶-凝胶法制备钙钛矿高熵氧化物 Cu 空位电极的详细工艺流程"
        sec = _make_sections(text)
        m = ev.classify_method({
            "name": "溶胶-凝胶法制备高熵氧化物 Cu 空位电极",
            "evidence_quote": "溶胶-凝胶法  制备钙钛矿高熵氧化物 Cu 空位电极的详细工艺流程",
        }, sec)
        self.assertEqual(m["validation_status"], "candidate")
        self.assertEqual(m["evidence_match_status"], "normalized_exact")

    # ---- 去重 ----

    def test_dedupe_prefers_longer_evidence(self):
        long_ev = "本文提出了一种新型全钒液流电池均一性优化方案, 显著改善电堆电压均一性。"
        short_ev = "本文提出了一种新型全钒液流电池均一性优化方案。"
        sec = _make_sections(long_ev)
        m1 = ev.classify_method({
            "name": "全钒液流电池均一性优化", "evidence_quote": short_ev,
        }, sec)
        m2 = ev.classify_method({
            "name": "全钒液流电池均一性优化", "evidence_quote": long_ev,
        }, sec)
        # 手动设为 accepted 让去重比较
        m1["validation_status"] = "accepted"
        m2["validation_status"] = "accepted"
        deduped = ev.dedupe_methods_prefer_longer_evidence([m1, m2])
        statuses = [x["validation_status"] for x in deduped]
        reasons = [x["rejected_reason"] for x in deduped]
        # 一个 rejected 且 reason 含 duplicate_method, 另一个仍是 accepted
        self.assertEqual(statuses.count("accepted"), 1)
        self.assertEqual(statuses.count("rejected"), 1)
        self.assertTrue(any("duplicate_method" in r for r in reasons))

    # ---- parse_llm_json ----

    def test_parse_llm_json_plain(self):
        ok, obj, err = me.parse_llm_json(
            '{"own_methods":[{"name":"X","evidence_quote":"abcdefghijklmnopqrstuv"}],"referenced_methods":[]}'
        )
        self.assertTrue(ok)
        self.assertIn("own_methods", obj)

    def test_parse_llm_json_with_markdown_fence(self):
        ok, obj, err = me.parse_llm_json(
            '```json\n{"own_methods":[],"referenced_methods":[]}\n```'
        )
        self.assertTrue(ok)
        self.assertEqual(obj["own_methods"], [])

    def test_parse_llm_json_bad(self):
        ok, obj, err = me.parse_llm_json("not json")
        self.assertFalse(ok)
        self.assertTrue(err.startswith("json_decode_error"))

    # ---- method_id 稳定 ----

    def test_method_id_stable(self):
        a = me._make_method_id("p1", "own", 0, "X 方法")
        b = me._make_method_id("p1", "own", 0, "X 方法")
        c = me._make_method_id("p1", "own", 1, "X 方法")
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)

    # ---- v2: sentence-id pack ----

    def test_build_sentence_index_for_llm_covers_key_types_and_hints(self):
        sj = {
            "sections": [
                {"section_type": "title", "raw_heading": "T",
                 "paragraphs": [{"para_id": "title_00_p01", "text": "标题.",
                                 "char_start": 0, "char_end": 3}]},
                {"section_type": "abstract", "raw_heading": "摘要",
                 "paragraphs": [{"para_id": "abstract_01_p01", "text": "摘要正文.",
                                 "char_start": 3, "char_end": 8}]},
                {"section_type": "methods", "raw_heading": "1 实验",
                 "paragraphs": [{"para_id": "methods_02_p01",
                                 "text": "本文采用溶胶-凝胶法制备了正极。",
                                 "char_start": 8, "char_end": 24}]},
                {"section_type": "other_sections", "raw_heading": "3 表征方法",
                 "paragraphs": [{"para_id": "other_sections_03_p01",
                                 "text": "包含 方法 关键字的段落。",
                                 "char_start": 24, "char_end": 40}]},
                {"section_type": "other_sections", "raw_heading": "致谢",
                 "paragraphs": [{"para_id": "other_sections_04_p01",
                                 "text": "感谢各位审稿人。",
                                 "char_start": 40, "char_end": 48}]},
            ]
        }
        sentence_index, pack, sents = me.build_sentence_index_for_llm(sj, "p-test")
        self.assertIn("[title]", pack)
        self.assertIn("[abstract]", pack)
        self.assertIn("[methods]", pack)
        self.assertIn("表征方法", pack)     # method hint 命中
        self.assertNotIn("致谢", pack)       # 未命中
        # sentence_index 必须以 sentence_id 为 key
        self.assertTrue(all(isinstance(k, str) for k in sentence_index.keys()))
        # 每个句子都有 sentence_id / char_start / char_end
        for sid, s in sentence_index.items():
            self.assertEqual(s["sentence_id"], sid)
            self.assertIn("char_start", s)
            self.assertIn("char_end", s)

    # ---- llm_client key policy ----

    def test_llm_client_raises_without_env_key(self):
        # 备份 & 清 env
        from method_evolution_v2.stage_a import llm_client as lc
        prev = os.environ.pop("MOONSHOT_API_KEY", None)
        try:
            with self.assertRaises(RuntimeError):
                lc.get_api_key()
        finally:
            if prev is not None:
                os.environ["MOONSHOT_API_KEY"] = prev


if __name__ == "__main__":
    unittest.main(verbosity=2)
