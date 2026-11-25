"""Stage A v2 - 句子级证据索引.

把已解析的 sections 切成"可回溯句子":
  - sentence_text 必须是 full.md 的**原始连续切片**
  - char_start/end 必须精确切回 sentence_text
  - 不改写、不清洗、不去 OCR 乱码、不合并标点
  - 无法正常分句的公式/表格块保留为独立句子
  - 不丢失正文内容 (拼接所有 sentence.text 应能重构 paragraph.text)

设计约束(本轮 spec 二):
  只按 CJK 完整句号/问号/感叹号 (。！？) 切分, **不用**分号或英文句号.
  避免 chemical formula "SiO2·H2O" 或版本号 "1.2.3" 被误切.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


# ============================================================
# 分句
# ============================================================

# 仅 CJK 句末标点作为切分点; 分号 (；) 与英文 . ! ? 不作为切点(避免误切公式/编号)
_SENT_END_CHARS = "。！？"

# 紧跟句末标点的关闭引号 / 括号 / 书名号 尾符, 一起并入前句
_TRAILING_CLOSERS = '"”\'’)）】》』」〕〞〟'


def split_paragraph_to_sentences(text: str) -> list:
    """把段落文本切成句子, 保留标点, 返回 [(sentence_text, local_start, local_end), ...].

    句末字符 . 后跟 closers (引号/括号) 也归到前句.
    无 CJK 句末标点的段落整段作为单句返回 (公式/表格块保护).
    """
    if text is None:
        return []
    if not text:
        return []

    sents = []
    buf_start = 0
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c in _SENT_END_CHARS:
            end = i + 1
            while end < n and text[end] in _TRAILING_CLOSERS:
                end += 1
            frag = text[buf_start:end]
            if frag:
                sents.append((frag, buf_start, end))
            buf_start = end
            i = end
        else:
            i += 1

    if buf_start < n:
        frag = text[buf_start:]
        if frag:
            sents.append((frag, buf_start, n))

    # 空文本兜底
    if not sents and text:
        sents = [(text, 0, n)]

    return sents


# ============================================================
# 句子索引构建
# ============================================================

@dataclass
class Sentence:
    sentence_id: str
    paper_id: str
    section_type: str
    section_name: str
    para_id: str
    sentence_text: str
    char_start: int
    char_end: int

    def to_dict(self) -> dict:
        return {
            "sentence_id": self.sentence_id,
            "paper_id": self.paper_id,
            "section_type": self.section_type,
            "section_name": self.section_name,
            "para_id": self.para_id,
            "sentence_text": self.sentence_text,
            "char_start": self.char_start,
            "char_end": self.char_end,
        }


def build_sentence_index(sections_json: dict, paper_id: str) -> list:
    """输入 sections JSON (即 corpus_preprocess_v1_1/sections/<pid>.json 内容), 输出句子列表.

    sentence_id 格式: <section_type>_p<global_para_num>_s<sent_num>
    (paragraph 全局编号从 1 递增, 跨 section)
    """
    out = []
    global_para_num = 0
    for sec in sections_json.get("sections") or []:
        sec_type = sec.get("section_type", "unknown")
        sec_name = sec.get("raw_heading", "") or ""
        for p in sec.get("paragraphs") or []:
            ptxt = p.get("text") or ""
            if not ptxt:
                continue
            global_para_num += 1
            para_id = p.get("para_id", f"p{global_para_num:03d}")
            para_abs_start = int(p.get("char_start", 0))
            for s_idx, (s_text, s_local_start, s_local_end) in enumerate(
                split_paragraph_to_sentences(ptxt), 1
            ):
                out.append(Sentence(
                    sentence_id=f"{sec_type}_p{global_para_num}_s{s_idx}",
                    paper_id=paper_id,
                    section_type=sec_type,
                    section_name=sec_name,
                    para_id=para_id,
                    sentence_text=s_text,
                    char_start=para_abs_start + s_local_start,
                    char_end=para_abs_start + s_local_end,
                ))
    return out


# ============================================================
# 校验: 切片能否回原文 (spec 二.2 hard requirement)
# ============================================================

def verify_sentence_slices(sentences: list, full_md_text: str) -> tuple:
    """对每个 sentence 校验 full_md_text[char_start:char_end] == sentence_text.

    返回 (all_ok: bool, mismatches: [(sentence_id, expected_len, actual_slice_prefix), ...])
    """
    mismatches = []
    for s in sentences:
        if s.char_end > len(full_md_text) or s.char_start < 0:
            mismatches.append((s.sentence_id, len(s.sentence_text), "<out-of-range>"))
            continue
        actual = full_md_text[s.char_start:s.char_end]
        if actual != s.sentence_text:
            mismatches.append((
                s.sentence_id, len(s.sentence_text),
                actual[:40] + ("..." if len(actual) > 40 else "")
            ))
    return (len(mismatches) == 0), mismatches


def sentence_index_to_pack(sentences: list, max_chars: int = None) -> str:
    """把 sentence 列表拼成 LLM 输入的 '按句子 ID 索引' 文本块.

    按 section 分组; 每句一行: "- <sid>: 「<sentence_text>」".
    """
    if not sentences:
        return "(empty)"
    lines = []
    prev_sec_key = None
    for s in sentences:
        sec_key = (s.section_type, s.section_name)
        if sec_key != prev_sec_key:
            lines.append(f"\n### [{s.section_type}] {s.section_name}")
            prev_sec_key = sec_key
        # 一行一句, 用「」包裹避免与外部结构混淆; 若正文本身含「, 保留即可
        one_line = s.sentence_text.replace("\n", " ").strip()
        lines.append(f"- {s.sentence_id}: 「{one_line}」")
    text = "\n".join(lines)
    if max_chars is not None and len(text) > max_chars:
        text = text[:max_chars] + "\n...(sentence pack truncated to fit budget)"
    return text
