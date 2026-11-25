"""section_parser.py — 按章节解析 full.md, 保留全部原文与字符位置.

设计原则:
  - 纯本地解析, 不调用 LLM, 不写数据库
  - 章节覆盖率必须为 100%, 即所有 section.char_end - char_start 之和 == len(text)
  - 不分类的内容一律落到 other_sections, 不丢弃
  - 段落级保留 para_id + 绝对字符偏移, 用于后续证据校验

识别策略:
  1. 仅识别 markdown 标题 (行首 #..., 后跟空白与标题文本), 不强行解读 OCR 噪声里的伪标题
  2. 按标题文本匹配章节关键词 (中英) → 标准化 section_type
  3. 未匹配的标题:
     - 若有 numbering (1.2 / 2.1 等), 尝试从同顶层编号的兄弟章节继承类型
     - 第一个未匹配的标题视为文档 title
     - 其余落到 other_sections
  4. 标题前的 preamble 也保留为 other_sections
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

# 版本号 (供下游 paper_type_rules 等在输出里记录溯源)
# 1.1.1 (2026-07-01): 在关键词严格白名单里追加 3 个完整标题:
#   - conclusion:      结语与展望
#   - methods:         研究方法及数据范围
#   - case_analysis:   模型验证
# 不再扩大其他关键词.
SECTION_PARSER_VERSION = "1.1.1"


# ============================================================
# 标题与章节正则
# ============================================================

# Markdown 标题行
HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*$", re.MULTILINE)

# 标准章节类型枚举 (与 paper_type/storage_taxonomy/method_type 正交)
STANDARD_SECTION_TYPES = (
    "title", "abstract", "introduction",
    "theory_model", "system_design", "simulation_calculation",
    "methods", "case_analysis",
    "results_discussion", "results", "discussion",
    "conclusion", "references", "patent_analysis",
    "other_sections",
)

# 章节类型识别 (严格 ^...$ 锚定; 子标题靠 numbering 继承, 不靠子串匹配)
# v1.1 修正:
#   - conclusion 严格白名单 (避免 "机理总结与分析" 误判为结论)
#   - 新增 theory_model / system_design / simulation_calculation / case_analysis / patent_analysis
#   - 所有正则都用 ^...\s*$ 锚定
SECTION_PATTERNS = [
    ("abstract", re.compile(
        r"^(摘\s*要|中文\s*摘要|英文\s*摘要|Abstract|ABSTRACT)\s*$",
        re.IGNORECASE,
    )),
    ("introduction", re.compile(
        r"^(引\s*言|前\s*言|绪\s*论|简\s*介|Introduction)\s*$",
        re.IGNORECASE,
    )),
    ("theory_model", re.compile(
        r"^("
        r"理\s*论(?:分析|基础|与方法|与模型)?"
        r"|理\s*论\s*模\s*型"
        r"|(?:数\s*学|物\s*理|动\s*力\s*学|热\s*力\s*学|流\s*体\s*力\s*学|传\s*热|两\s*相\s*流|流\s*场)\s*模\s*型"
        r"|模\s*型\s*(?:建\s*立|描\s*述|构\s*建|推\s*导|与\s*方\s*法)"
        r"|建\s*立\s*模\s*型"
        r"|控\s*制\s*方\s*程"
        r"|Theoretical?\s+(?:model|analysis)"
        r"|Mathematical?\s+model"
        r")\s*$",
        re.IGNORECASE,
    )),
    ("system_design", re.compile(
        r"^("
        r"系\s*统\s*(?:描\s*述|设\s*计|构\s*建|介\s*绍|结\s*构|组\s*成|集\s*成|流\s*程|构\s*成|原\s*理)"
        r"|流\s*程\s*(?:设\s*计|介\s*绍|说\s*明)"
        r"|工\s*艺\s*流\s*程"
        r"|装\s*置\s*(?:设\s*计|描\s*述|介\s*绍|结\s*构)"
        r"|实\s*验\s*装\s*置"
        r"|System\s+(?:design|description|architecture)"
        r")\s*$",
        re.IGNORECASE,
    )),
    ("simulation_calculation", re.compile(
        r"^("
        r"仿\s*真\s*(?:方\s*法|模\s*型|分\s*析|计\s*算|与\s*分\s*析)?"
        r"|数\s*值\s*(?:模\s*拟|计\s*算|方\s*法|仿\s*真)"
        r"|计\s*算\s*(?:方\s*法|模\s*型|流\s*程)"
        r"|边\s*界\s*条\s*件"
        r"|网\s*格\s*划\s*分"
        r"|Simulation"
        r"|Numerical\s+(?:simulation|method|calculation|model)"
        r")\s*$",
        re.IGNORECASE,
    )),
    ("methods", re.compile(
        r"^("
        r"实\s*验"
        r"|实\s*验\s*(?:方\s*法|部\s*分|过\s*程|步\s*骤|原\s*理|系\s*统|材\s*料)"
        r"|材\s*料\s*(?:与|和)\s*方\s*法"
        r"|测\s*试\s*方\s*法"
        r"|研\s*究\s*方\s*法\s*及\s*数\s*据\s*范\s*围"   # v1.1.1: 完整标题白名单
        r"|Experimental(?:\s+section)?"
        r"|Materials\s+and\s+Methods"
        r"|Methodology"
        r"|Methods?"
        r")\s*$",
        re.IGNORECASE,
    )),
    ("case_analysis", re.compile(
        r"^("
        r"算\s*例(?:\s*分\s*析|\s*计\s*算)?"
        r"|案\s*例\s*分\s*析"
        r"|性\s*能\s*分\s*析"
        r"|参\s*数\s*(?:分\s*析|影\s*响\s*分\s*析|研\s*究)"
        r"|敏\s*感\s*性?\s*分\s*析"
        r"|工\s*况\s*分\s*析"
        r"|模\s*型\s*验\s*证"                             # v1.1.1: 完整标题白名单
        r"|Case\s+stud(?:y|ies)"
        r"|Parametric\s+(?:study|analysis)"
        r")\s*$",
        re.IGNORECASE,
    )),
    ("results_discussion", re.compile(
        r"^("
        r"结\s*果\s*(?:与|和)\s*讨\s*论"
        r"|测\s*试\s*结\s*果\s*(?:与|和)?\s*分\s*析"
        r"|实\s*验\s*结\s*果\s*(?:与|和)?\s*讨\s*论"
        r"|Results?\s+and\s+Discussion"
        r")\s*$",
        re.IGNORECASE,
    )),
    ("results", re.compile(
        r"^("
        r"结\s*果"
        r"|实\s*验\s*结\s*果"
        r"|测\s*试\s*结\s*果"
        r"|计\s*算\s*结\s*果"
        r"|仿\s*真\s*结\s*果"
        r"|Results?"
        r")\s*$",
        re.IGNORECASE,
    )),
    ("discussion", re.compile(
        r"^(讨\s*论|分\s*析(?:与|和)\s*讨\s*论|Discussion)\s*$",
        re.IGNORECASE,
    )),
    ("conclusion", re.compile(
        # 严格白名单: 仅以下完整标题判为结论
        r"^("
        r"结\s*论"
        r"|结\s*语"
        r"|总\s*结"
        r"|总\s*结\s*与\s*展\s*望"
        r"|结\s*论\s*与\s*展\s*望"
        r"|结\s*语\s*与\s*展\s*望"                        # v1.1.1: 完整标题白名单
        r"|Conclusion[s]?"
        r")\s*$",
        re.IGNORECASE,
    )),
    ("references", re.compile(
        r"^(参\s*考\s*文\s*献|引\s*用\s*文\s*献|References)\s*$",
        re.IGNORECASE,
    )),
    ("patent_analysis", re.compile(
        r"^("
        r"专\s*利\s*(?:分\s*析|数\s*据|检\s*索|路\s*线|信\s*息|概\s*况|统\s*计)"
        r"|技\s*术\s*路\s*线\s*分\s*析"
        r"|Patent\s+(?:analysis|search)"
        r")\s*$",
        re.IGNORECASE,
    )),
]

NUMBERING_RE = re.compile(r"^(\d+(?:\.\d+)*)")

# ---- 内联摘要识别 ----
# 起始标记: 必须明显 (冒号 / 方括号 / 双空格), 不接受裸 "摘要" 作起点
INLINE_ABSTRACT_START_PATTERNS = [
    (re.compile(r"【\s*摘\s*要\s*】\s*"), "cn_brackets"),
    (re.compile(r"摘\s*要\s*[：:]\s*"), "cn_colon"),
    (re.compile(r"摘\s*要(?=[ \t]{2,}\S)[ \t]+", re.MULTILINE), "cn_double_space"),
    (re.compile(r"Abstract\s*[：:]\s*", re.IGNORECASE), "en_colon"),
    (re.compile(r"\bABSTRACT\b[ \t\:：]+(?!\.)"), "en_caps"),
]
# 结束边界: 关键词 / 关键字 / Keywords / Key words
INLINE_ABSTRACT_END_PATTERNS = [
    re.compile(r"关\s*键\s*[词字]\s*[：:]\s*"),
    re.compile(r"Key\s*[Ww]ords?\s*[：:]\s*", re.IGNORECASE),
    re.compile(r"Keywords?\s*[：:]\s*", re.IGNORECASE),
]
# 摘要内容最少字符数 (低于此视为误命中)
INLINE_ABSTRACT_MIN_CHARS = 30


# ============================================================
# 数据结构
# ============================================================

@dataclass
class Paragraph:
    para_id: str
    text: str
    char_start: int
    char_end: int


@dataclass
class Section:
    section_index: int
    section_type: str
    raw_heading: str
    heading_level: int           # 0 表示 preamble (无 markdown 标题)
    char_start: int
    char_end: int
    confidence: str              # high / medium / low / none
    matched_by_markdown_heading: bool
    inferred_by_regex: bool
    inference_source: str        # keyword / numbering_inherit / title_first_unmatched
                                 # / preamble / no_match / no_heading_found
    paragraphs: list = field(default_factory=list)


@dataclass
class ParseResult:
    paper_id: str
    source_md_path: str
    source_md_chars: int
    parse_time_iso: str
    document_title: Optional[str]
    sections: list                       # list[Section]
    section_coverage_chars: int
    section_coverage_ratio: float
    paragraph_coverage_chars: int
    paragraph_coverage_ratio: float
    has_text_loss: bool
    notes: list


# ============================================================
# 辅助函数
# ============================================================

def _find_headings(text: str) -> list[dict]:
    return [
        {
            "level": len(m.group(1)),
            "raw_heading": m.group(2).strip(),
            "line_start": m.start(),
            "line_end": m.end(),
        }
        for m in HEADING_RE.finditer(text)
    ]


def _strip_numbering(heading_text: str) -> str:
    """去掉前导数字编号 + 尾部标点, 如 '1.2 实验方法。' -> '实验方法'."""
    s = re.sub(r"^\s*[0-9]+(?:\.[0-9]+)*[.\s]*", "", heading_text).strip()
    s = s.rstrip("。.:：、,，;；")
    return s.strip()


def classify_heading_text(raw_heading: str) -> Optional[str]:
    """返回 section_type 或 None.

    严格 ^...$ 锚定匹配 (去除前导编号 + 尾标点后). 子标题靠 numbering 继承.
    """
    stripped = _strip_numbering(raw_heading)
    if not stripped:
        return None
    for sec_type, patt in SECTION_PATTERNS:
        if patt.match(stripped):
            return sec_type
    return None


# ============================================================
# 内联摘要识别
# ============================================================

def _detect_inline_abstract(text: str, search_start: int, search_end: int) -> Optional[dict]:
    """在 text[search_start:search_end] 范围内找内联摘要.

    返回 {marker_start, marker_end, abs_end, pattern_type} 或 None.
    要求摘要内容 >= INLINE_ABSTRACT_MIN_CHARS 字, 否则视为误命中.
    """
    region = text[search_start:search_end]
    if not region:
        return None

    for start_re, pat_type in INLINE_ABSTRACT_START_PATTERNS:
        m = start_re.search(region)
        if not m:
            continue
        marker_start_local = m.start()
        marker_end_local = m.end()
        # 找最近的结束边界
        end_local = None
        for end_re in INLINE_ABSTRACT_END_PATTERNS:
            em = end_re.search(region, marker_end_local)
            if em:
                e = em.start()
                if end_local is None or e < end_local:
                    end_local = e
        if end_local is None:
            end_local = len(region)
        content = region[marker_end_local:end_local].strip()
        if len(content) < INLINE_ABSTRACT_MIN_CHARS:
            continue
        return {
            "marker_start": search_start + marker_start_local,
            "marker_end": search_start + marker_end_local,
            "abs_end": search_start + end_local,
            "pattern_type": pat_type,
        }
    return None


# 标准"实质章节"集合: 一旦出现这些类型, 表示已进入正文, 不再扫摘要
_REAL_BODY_TYPES = {
    "introduction", "methods", "results", "results_discussion", "discussion",
    "conclusion", "references",
    "theory_model", "system_design", "simulation_calculation",
    "case_analysis", "patent_analysis",
}


def _splice_inline_abstract(text: str, sections: list) -> list:
    """扫描首批非实质章节, 找到内联摘要, 把容器 section 分裂成 [before, abstract, after].

    若已有 markdown abstract 章节, 直接返回原列表.
    """
    if any(s.section_type == "abstract" for s in sections):
        return sections

    # 找第一个实质章节的位置 — 摘要必须出现在它之前
    first_real_idx = len(sections)
    for i, s in enumerate(sections):
        if s.section_type in _REAL_BODY_TYPES:
            first_real_idx = i
            break

    # 在 [0, first_real_idx) 范围内扫描
    for i in range(first_real_idx):
        sec = sections[i]
        ab = _detect_inline_abstract(text, sec.char_start, sec.char_end)
        if not ab:
            continue
        new_parts = _split_section_for_abstract(sec, ab, text)
        new_sections = list(sections[:i]) + new_parts + list(sections[i + 1:])
        for k, s in enumerate(new_sections):
            s.section_index = k
        return new_sections

    return sections


def _split_section_for_abstract(sec, ab: dict, text: str) -> list:
    """把单个 section 按 ab(marker_start/marker_end/abs_end) 拆为最多 3 段.

    before:  [sec.char_start, ab.marker_start)  — 保留原 heading 与原类型
    abstract: [ab.marker_start, ab.abs_end)     — 新 abstract section, heading_level=0
    after:    [ab.abs_end, sec.char_end)        — 原类型 (通常 other_sections), 无 heading
    """
    out = []
    if ab["marker_start"] > sec.char_start:
        before = Section(
            section_index=-1,
            section_type=sec.section_type,
            raw_heading=sec.raw_heading,
            heading_level=sec.heading_level,
            char_start=sec.char_start,
            char_end=ab["marker_start"],
            confidence=sec.confidence,
            matched_by_markdown_heading=sec.matched_by_markdown_heading,
            inferred_by_regex=sec.inferred_by_regex,
            inference_source=sec.inference_source + "+split_before_inline_abstract",
        )
        out.append(before)

    marker_text = text[ab["marker_start"]:ab["marker_end"]].strip()
    if "colon" in ab["pattern_type"] or "brackets" in ab["pattern_type"]:
        conf = "high"
    else:
        conf = "medium"
    abstract_sec = Section(
        section_index=-1,
        section_type="abstract",
        raw_heading=marker_text,
        heading_level=0,
        char_start=ab["marker_start"],
        char_end=ab["abs_end"],
        confidence=conf,
        matched_by_markdown_heading=False,
        inferred_by_regex=True,
        inference_source=f"inline_abstract_{ab['pattern_type']}",
    )
    out.append(abstract_sec)

    if ab["abs_end"] < sec.char_end:
        after = Section(
            section_index=-1,
            section_type=sec.section_type,
            raw_heading="",
            heading_level=0,
            char_start=ab["abs_end"],
            char_end=sec.char_end,
            confidence=sec.confidence,
            matched_by_markdown_heading=False,
            inferred_by_regex=False,
            inference_source=sec.inference_source + "+split_after_inline_abstract",
        )
        out.append(after)

    return out


def _numbering_top(heading_text: str) -> Optional[str]:
    m = NUMBERING_RE.match(heading_text.strip())
    if not m:
        return None
    return m.group(1).split(".")[0]


def _split_paragraphs(
    section_text: str, abs_section_start: int, body_offset_local: int
) -> list[tuple[str, int, int]]:
    """切段落. body_offset_local 是 heading 行结束后的本地偏移.

    返回 [(para_text, abs_start, abs_end), ...].
    para_text 不包含前导/末尾空白; abs_start/abs_end 是原始文档绝对字符偏移.
    """
    body = section_text[body_offset_local:]
    out = []
    pos = 0
    SPLIT = re.compile(r"\n[ \t]*\n+")
    while pos < len(body):
        m_ws = re.match(r"\s+", body[pos:])
        if m_ws:
            pos += len(m_ws.group(0))
        if pos >= len(body):
            break
        m_split = SPLIT.search(body, pos)
        end = m_split.start() if m_split else len(body)
        chunk = body[pos:end]
        if chunk.strip():
            abs_s = abs_section_start + body_offset_local + pos
            abs_e = abs_section_start + body_offset_local + end
            out.append((chunk, abs_s, abs_e))
        pos = end
        if m_split:
            pos = m_split.end()
        else:
            break
    return out


# ============================================================
# 主解析入口
# ============================================================

def parse_text(paper_id: str, text: str, source_md_path: str = "") -> ParseResult:
    """对给定原始文本进行章节解析. 不读盘. 用于单元测试."""
    n = len(text)
    headings = _find_headings(text)
    sections: list[Section] = []
    notes: list[str] = []

    if not headings:
        sections.append(Section(
            section_index=0,
            section_type="other_sections",
            raw_heading="",
            heading_level=0,
            char_start=0,
            char_end=n,
            confidence="low",
            matched_by_markdown_heading=False,
            inferred_by_regex=False,
            inference_source="no_heading_found",
        ))
        notes.append("no_markdown_heading_detected: whole file kept as a single other_sections")
    else:
        # preamble (第一个 heading 之前)
        if headings[0]["line_start"] > 0:
            sections.append(Section(
                section_index=0,
                section_type="other_sections",
                raw_heading="",
                heading_level=0,
                char_start=0,
                char_end=headings[0]["line_start"],
                confidence="low",
                matched_by_markdown_heading=False,
                inferred_by_regex=False,
                inference_source="preamble",
            ))

        # 每个 heading 一个 section, 边界到下一 heading 之前
        for i, h in enumerate(headings):
            start = h["line_start"]
            end = headings[i + 1]["line_start"] if i + 1 < len(headings) else n
            sec_type = classify_heading_text(h["raw_heading"])
            if sec_type:
                conf = "high"
                inferred = False
                src = "keyword"
            else:
                conf = "low"
                inferred = False
                src = "no_match"
                sec_type = "other_sections"

            sections.append(Section(
                section_index=len(sections),
                section_type=sec_type,
                raw_heading=h["raw_heading"],
                heading_level=h["level"],
                char_start=start,
                char_end=end,
                confidence=conf,
                matched_by_markdown_heading=True,
                inferred_by_regex=False,
                inference_source=src,
            ))

        # 编号继承: 未匹配但有数字前缀的, 沿用同顶层数字的已分类章节
        for i, sec in enumerate(sections):
            if sec.heading_level == 0 or sec.section_type != "other_sections":
                continue
            top = _numbering_top(sec.raw_heading)
            if not top:
                continue
            for j in range(i - 1, -1, -1):
                prev = sections[j]
                if prev.heading_level == 0 or prev.section_type == "other_sections":
                    continue
                prev_top = _numbering_top(prev.raw_heading)
                if prev_top == top:
                    sec.section_type = prev.section_type
                    sec.confidence = "medium"
                    sec.inferred_by_regex = True
                    sec.inference_source = "numbering_inherit"
                    break

        # title 启发: 第一个 markdown 标题如果未匹配关键词且无数字前缀, 视为文档标题
        for sec in sections:
            if sec.heading_level == 0:
                continue
            if sec.section_type == "other_sections" and not _numbering_top(sec.raw_heading):
                sec.section_type = "title"
                sec.confidence = "high"
                sec.inferred_by_regex = True
                sec.inference_source = "title_first_unmatched"
            break  # 仅处理第一个 heading 后立即停

    # 内联摘要识别 (v1.1 新增): 仅当没有 markdown abstract 章节时执行
    sections = _splice_inline_abstract(text, sections)

    # 段落切分
    for sec in sections:
        body_text = text[sec.char_start:sec.char_end]
        if sec.heading_level > 0:
            nl = body_text.find("\n")
            body_offset = (nl + 1) if nl != -1 else len(body_text)
        else:
            body_offset = 0
        for k, (ptext, abs_s, abs_e) in enumerate(
            _split_paragraphs(body_text, sec.char_start, body_offset), 1
        ):
            pid = f"{sec.section_type}_{sec.section_index:02d}_p{k:02d}"
            sec.paragraphs.append(Paragraph(
                para_id=pid, text=ptext, char_start=abs_s, char_end=abs_e
            ))

    # 文档标题
    document_title = None
    for sec in sections:
        if sec.section_type == "title":
            document_title = sec.raw_heading
            break
    if document_title is None:
        document_title = paper_id

    # 覆盖率
    sec_cov = sum(s.char_end - s.char_start for s in sections)
    para_cov = sum(p.char_end - p.char_start for s in sections for p in s.paragraphs)

    has_loss = sec_cov != n

    return ParseResult(
        paper_id=paper_id,
        source_md_path=source_md_path,
        source_md_chars=n,
        parse_time_iso=datetime.now().isoformat(timespec="seconds"),
        document_title=document_title,
        sections=sections,
        section_coverage_chars=sec_cov,
        section_coverage_ratio=(sec_cov / n) if n > 0 else 0.0,
        paragraph_coverage_chars=para_cov,
        paragraph_coverage_ratio=(para_cov / n) if n > 0 else 0.0,
        has_text_loss=has_loss,
        notes=notes,
    )


def parse_file(paper_id: str, md_path: str) -> ParseResult:
    """读盘 + 解析."""
    with open(md_path, "r", encoding="utf-8", errors="strict") as f:
        text = f.read()
    return parse_text(paper_id, text, source_md_path=md_path)


def get_title_info(parse_result: ParseResult) -> dict:
    """区分 source_title 与 canonical_title, 不把 paper_id 伪装为解析出来的标题.

    返回字段(spec v1.1.1):
      - source_title:      从 markdown 结构里可靠解析出来的标题 (第一个 section_type='title'
                           的 raw_heading), 找不到则为 ''
      - canonical_title:   有 source_title 用 source_title, 否则 fallback 到 paper_id
      - title_source:      'source_markdown' | 'paper_id_fallback'
      - title_confidence:  'high' (source_markdown) | 'medium' (paper_id_fallback)

    绝不把 paper_id 声称为 source_markdown, 保持来源可追溯.
    """
    source_title = ""
    for s in parse_result.sections:
        if s.section_type == "title" and s.raw_heading:
            source_title = s.raw_heading.strip()
            break
    pid = parse_result.paper_id or ""
    if source_title:
        return {
            "source_title": source_title,
            "canonical_title": source_title,
            "title_source": "source_markdown",
            "title_confidence": "high",
        }
    return {
        "source_title": "",
        "canonical_title": pid,
        "title_source": "paper_id_fallback",
        "title_confidence": "medium",
    }


def to_dict(result: ParseResult) -> dict:
    return {
        "paper_id": result.paper_id,
        "source_md_path": result.source_md_path,
        "source_md_chars": result.source_md_chars,
        "parse_time_iso": result.parse_time_iso,
        "document_title": result.document_title,
        "section_coverage_chars": result.section_coverage_chars,
        "section_coverage_ratio": round(result.section_coverage_ratio, 6),
        "paragraph_coverage_chars": result.paragraph_coverage_chars,
        "paragraph_coverage_ratio": round(result.paragraph_coverage_ratio, 6),
        "has_text_loss": result.has_text_loss,
        "notes": result.notes,
        "sections": [
            {
                "section_index": s.section_index,
                "section_type": s.section_type,
                "raw_heading": s.raw_heading,
                "heading_level": s.heading_level,
                "char_start": s.char_start,
                "char_end": s.char_end,
                "confidence": s.confidence,
                "matched_by_markdown_heading": s.matched_by_markdown_heading,
                "inferred_by_regex": s.inferred_by_regex,
                "inference_source": s.inference_source,
                "paragraphs": [
                    {
                        "para_id": p.para_id,
                        "text": p.text,
                        "char_start": p.char_start,
                        "char_end": p.char_end,
                    }
                    for p in s.paragraphs
                ],
            }
            for s in result.sections
        ],
    }


def write_json(result: ParseResult, out_path: str) -> None:
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(to_dict(result), f, ensure_ascii=False, indent=2)


# ============================================================
# CLI (仅用于手工排查; run_test_01.py 才是正式 driver)
# ============================================================

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("usage: python section_parser.py <paper_id> <full.md path>")
        sys.exit(2)
    pid, path = sys.argv[1], sys.argv[2]
    r = parse_file(pid, path)
    print(json.dumps(to_dict(r), ensure_ascii=False, indent=2)[:4000])
