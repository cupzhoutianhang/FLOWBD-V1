"""
answer_cleaner.py — 最终答案输出清洗器

用途:
    LLM (Kimi K2.6 等 thinking 模型) 有时会把"草稿/自检/字数确认"这类元评论
    (meta-commentary) 泄漏到 content 字段. 本模块在最终输出前做一遍清洗, 保证:

    1. 只保留最终成稿, 剥离规划/草稿/自检/"现在写最终回答"等内部过程
    2. 修复流式过程中丢失的区间符号 (40%60% -> 40%~60%, 1.42.0倍 -> 1.4~2.0倍)
    3. 【文献来源】为空时不显示裸标题; 若有 [Ref-n] 则可补充题名

设计原则:
    - 只处理"输出层", 不动检索、不动原始文献
    - idempotent: clean_final_answer(clean_final_answer(x)) == clean_final_answer(x)
    - 保守: 宁可放过一小段可疑元评论, 也不误删真答案

使用:
    from agent.answer_cleaner import clean_final_answer
    final = clean_final_answer(raw_answer, sources=state.doc_sources)
"""
from __future__ import annotations

import re
from typing import List, Optional


# ============ 元评论识别 ============

# 出现在行首的规划/自检语气词 (整行删除)
_META_LINE_STARTS = (
    "我需要", "让我", "首先我", "首先，我", "首先, 我",
    "或者:", "或者：",
    "现在，我", "现在,我", "现在写", "现在整合", "现在给",
    "重新审视", "重新组织", "重新写", "重新构思",
    "再看看", "再想想", "再检查",
    "检查:", "检查：",
    "确认字数", "字数：", "字数:", "字数检查",
    "这样应该", "这样是不是", "这样更", "这样看",
    "这个版本", "这个更", "这个应该",
    "更简洁", "更精炼", "更好的版本", "更合适",
    "以下是最终", "以下是修订", "以下是精修",
    "最终版本", "最终版:", "最终版：",
    "草稿:", "草稿：",
    "OK,", "OK，", "好的,", "好的，",
)

# 出现在任意位置就删除该行的字符串
_META_LINE_SUBSTRINGS = (
    "草稿", "让我重新写", "让我重新组织", "让我先组织", "让我梳理",
    "现在写最终回答", "现在整合最终答案", "现在给出最终",
    "我需要确保", "我需要检查", "我需要重新", "我需要修改",
    "我需要保证", "我需要注意",
    "重新审视", "重新组织语言",
    "检查格式", "检查字数", "检查一下",
    "这样更好", "这样应该更", "这样是不是更",
    "确认字数", "确认格式",
    "让我改", "让我梳理", "让我重构",
)

# 出现在段落任意处的元评论标记 (若某段包含 >=2 处, 整段作为元评论删除)
_META_SEGMENT_MARKERS = (
    "我需要", "让我", "草稿", "重新", "检查", "字数", "或者",
    "这样", "现在写", "最终版", "修订",
)

# 明确的"最终答案分界"标记 — 之前的内容全部丢弃
_FINAL_BOUNDARY_PATTERNS = (
    r"^\s*(?:以下是|最后[，,]?)\s*(?:最终|正式)\s*(?:回答|答案|输出|版本)\s*[:：]?\s*$",
    r"^\s*=+\s*最终\s*(?:回答|答案|输出)\s*=+\s*$",
    r"^\s*【\s*最终\s*(?:回答|答案|输出)\s*】\s*$",
    r"^\s*最终\s*(?:回答|答案|输出)\s*[:：]\s*$",
)


def _is_meta_line(line: str) -> bool:
    """判定单行是否是元评论 (planning/self-check)."""
    stripped = line.strip()
    if not stripped:
        return False
    # 只有 markdown 标记 (---, ===, ***) 不算元评论
    if re.fullmatch(r"[-=*_\s]+", stripped):
        return False
    for start in _META_LINE_STARTS:
        if stripped.startswith(start):
            return True
    for sub in _META_LINE_SUBSTRINGS:
        if sub in stripped:
            return True
    return False


def _paragraph_meta_score(paragraph: str) -> int:
    """段落里出现的元评论标记数. >=2 视为元评论段."""
    score = 0
    for marker in _META_SEGMENT_MARKERS:
        if marker in paragraph:
            score += 1
    return score


def _find_final_boundary(text: str) -> Optional[int]:
    """若文本里有明确的'最终答案'分界标记, 返回其后位置; 否则 None."""
    for pat in _FINAL_BOUNDARY_PATTERNS:
        m = re.search(pat, text, flags=re.MULTILINE)
        if m:
            return m.end()
    return None


# ============ 主清洗步骤 ============

def strip_meta_commentary(text: str) -> str:
    """剥离规划/草稿/自检等元评论行与段落."""
    if not text:
        return text

    # 1) 明确的"最终回答:"分界标记 — 优先, 一刀切
    boundary = _find_final_boundary(text)
    if boundary is not None:
        text = text[boundary:].lstrip("\n")

    # 2) 逐行删除元评论行
    lines = text.split("\n")
    kept_lines = [l for l in lines if not _is_meta_line(l)]

    # 3) 按段落 (空行分隔) 二次过滤: 一段里元评论标记 >=2 视为元评论段
    paragraphs = "\n".join(kept_lines).split("\n\n")
    kept_paragraphs = [p for p in paragraphs if _paragraph_meta_score(p) < 2]

    result = "\n\n".join(kept_paragraphs)

    # 4) 压缩连续空行
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()


# ============ 区间符号修复 ============

# 后缀白名单 (物理单位 / 汉字量词) — 只有紧跟合法单位才判定为区间丢波浪线
_UNIT_SUFFIX = (
    r"(?:倍|℃|°C|℉|K\b|mm|cm|nm|μm|um|dm|m\b|km|"
    r"mV|kV|V\b|A\b|mA|kA|kW|MW|W\b|"
    r"mg|g\b|kg|t\b|mol|mmol|"
    r"kJ|MJ|GJ|J\b|Wh|kWh|MWh|mAh|Ah|"
    r"Pa|kPa|MPa|GPa|bar|atm|"
    r"h\b|s\b|min|d\b|"
    r"℃/min|W/mK|W/\(m·K\)|kJ/kg|J/g|"
    r"%|‰|℃~|次|周)"
)

# "40%60%" -> "40%~60%": 两个百分比数字紧贴
_RE_PERCENT = re.compile(r"(\d+(?:\.\d+)?%)(\d+(?:\.\d+)?%)")

# "1.42.0倍": 两个小数紧贴 + 单位
_RE_DECIMAL_RANGE = re.compile(
    r"(\d+\.\d+)(\d+\.\d+" + _UNIT_SUFFIX + r")"
)

# "300400℃": 两个整数紧贴 + 单位; 用回调按等长切分, 避免贪婪错位
_RE_INT_RANGE_GLOB = re.compile(
    r"(\d{4,})(" + _UNIT_SUFFIX + r")"
)


def _split_int_range_even(m: re.Match) -> str:
    """尝试把纯数字串按等长两半切开, 保证两半都是合法数字 (首位非 0)."""
    digits, unit = m.group(1), m.group(2)
    if len(digits) % 2 != 0:
        return m.group(0)
    half = len(digits) // 2
    left, right = digits[:half], digits[half:]
    # 首位为 0 (如 "300030" 切成 "300"+"030") 不像自然数, 放弃修复
    if right.startswith("0"):
        return m.group(0)
    return f"{left}～{right}{unit}"


def fix_range_symbols(text: str) -> str:
    """在流式输出丢失波浪线的位置补 ~ (使用中文全角"～").

    例子:
        40%60%     -> 40%～60%
        1.42.0倍    -> 1.4～2.0倍
        300400℃    -> 300～400℃
    """
    if not text:
        return text
    text = _RE_PERCENT.sub(r"\1～\2", text)
    text = _RE_DECIMAL_RANGE.sub(r"\1～\2", text)
    text = _RE_INT_RANGE_GLOB.sub(_split_int_range_even, text)
    return text


# ============ 【文献来源】 清理 ============

# 匹配文档末尾的"文献来源"节 (无论用【 】 --- 还是 === 分隔)
# 注意: 不用 MULTILINE, $ 意味着文档末端 → body 抓到文末为止
_RE_SOURCES_SECTION = re.compile(
    r"(?:\n|^)"
    r"[\s\-=—]*"
    r"(?:【\s*文献来源\s*】|"
    r"—+\s*文献来源\s*—+|"
    r"参考文献|"
    r"文献来源[:：]?)"
    r"(?P<body>[\s\S]*)$"
)


def _sources_body_is_empty(body: str) -> bool:
    """判定 body 是否是空的 (只有空格/分隔符)."""
    stripped = re.sub(r"[\s\-=—\n]", "", body)
    return len(stripped) == 0


def _extract_ref_ids(text: str) -> List[int]:
    """从答案里提取所有出现的 [Ref-n] 编号 (去重排序)."""
    ids = set()
    for m in re.finditer(r"\[\s*Ref[-\s]*(\d+)\s*\]", text):
        try:
            ids.add(int(m.group(1)))
        except ValueError:
            pass
    return sorted(ids)


def clean_empty_sources(text: str, sources: Optional[List[dict]] = None) -> str:
    """处理【文献来源】节:
       - body 为空 且 无 sources 补料 → 整节删除
       - body 为空 且 有 sources → 按 [Ref-n] 补齐条目
       - body 非空 → 保留原样
    """
    if not text:
        return text

    m = _RE_SOURCES_SECTION.search(text)
    if not m:
        return text

    body = m.group("body")
    if not _sources_body_is_empty(body):
        return text

    # body 空
    ref_ids = _extract_ref_ids(text[:m.start()])
    if not ref_ids or not sources:
        # 无 Ref, 直接砍掉标题节
        return text[:m.start()].rstrip()

    # 有 Ref + 有 sources → 补齐
    lines = ["", "——— 文献来源 ———"]
    for rid in ref_ids:
        try:
            src = sources[rid - 1]  # Ref-1 -> index 0
        except (IndexError, TypeError):
            src = None
        if isinstance(src, dict):
            title = (src.get("title") or src.get("filename") or
                     src.get("original_filename") or f"文献 {rid}")
        else:
            title = str(src) if src else f"文献 {rid}"
        lines.append(f"[Ref-{rid}] {title}")
    return text[:m.start()].rstrip() + "\n" + "\n".join(lines)


# ============ 编排 ============

def clean_final_answer(text: str,
                       sources: Optional[List[dict]] = None) -> str:
    """最终答案清洗主入口.

    Args:
        text: 原始最终答案 (可能含元评论/丢失区间符号/空文献来源节)
        sources: 若有, 用于补齐空【文献来源】节

    Returns:
        清洗后的答案. 若输入为空, 返回原值.
    """
    if not text:
        return text
    text = strip_meta_commentary(text)
    text = fix_range_symbols(text)
    text = clean_empty_sources(text, sources=sources)
    return text.strip()


__all__ = [
    "clean_final_answer",
    "strip_meta_commentary",
    "fix_range_symbols",
    "clean_empty_sources",
]
