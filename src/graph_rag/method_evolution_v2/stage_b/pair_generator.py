"""Stage B 候选对生成 (spec 五).

**禁止**全排列.

只生成有文本连接信号的方法对:
  A. 同段共现: 两方法至少有 1 条 evidence 落在同一 paragraph
  B. 相邻段: 两方法的 paragraph 全局编号差 ≤ 1
  C. own↔ref 且共处一段或有共同 trigger 覆盖
  D. 触发语共现: 两方法证据 paragraph 范围内含"基础上/相比/改进/借鉴/替代/传统方法"等触发词

pair_source 会记录到 CSV, 便于人工审. 无信号 → 不发给关系模型.
"""
from __future__ import annotations

import itertools
import re
from collections import defaultdict


# ---- 触发词 (spec 五 明确) ----
TRIGGER_WORDS = (
    # EXTENDS 类
    "基础上", "在此基础上", "扩展", "延伸", "拓展", "沿用", "沿袭",
    # IMPROVES 类
    "相比", "相较", "相较于", "与之相比", "改进", "优化", "提升", "优于", "对比",
    "较传统", "较之前", "比较", "相比于",
    # ADAPTS 类
    "借鉴", "迁移", "引入", "移植", "参考",
    # REPLACES 类
    "替代", "取代", "淘汰", "摆脱", "克服", "突破", "传统方法",
    "存在问题", "局限", "缺陷", "不足",
    # 通用比较
    "与...不同", "而不同", "不同于", "不同于以往", "而非", "而不是",
    # 时间线
    "早期", "近期", "最新",
)

# ---- sentence_id 解析 ----
# 格式: <section_type>_p<global_para_num>_s<sent_num>
# section_type 可能含下划线 (results_discussion / other_sections 等)
_SID_RE = re.compile(r"^(.+)_p(\d+)_s(\d+)$")


def parse_sentence_id(sid: str) -> tuple | None:
    """解析 sentence_id → (section_type, global_para_num, sent_num). 无法解析返回 None."""
    if not sid:
        return None
    m = _SID_RE.match(sid.strip())
    if not m:
        return None
    return m.group(1), int(m.group(2)), int(m.group(3))


def scan_trigger_sentences(sentence_index: dict) -> set:
    """扫描所有句子, 返回含 trigger 词的 sentence_id 集合."""
    out = set()
    for sid, s in sentence_index.items():
        text = s.get("sentence_text") or ""
        if any(w in text for w in TRIGGER_WORDS):
            out.add(sid)
    return out


def _para_nums(sids: list) -> set:
    """从 sid 列表提取 global paragraph numbers."""
    out = set()
    for sid in (sids or []):
        parsed = parse_sentence_id(sid)
        if parsed:
            out.add(parsed[1])
    return out


def _sids_in_para_range(sentence_index: dict, pmin: int, pmax: int) -> list:
    """返回落在 [pmin, pmax] 段落范围内的 sid 列表."""
    out = []
    for sid in sentence_index:
        parsed = parse_sentence_id(sid)
        if parsed and pmin <= parsed[1] <= pmax:
            out.append(sid)
    return out


def generate_candidate_pairs(paper_id: str, methods: list,
                              sentence_index: dict,
                              max_trigger_span: int = 5) -> tuple:
    """给一篇论文的方法列表生成候选对.

    Args:
      paper_id: 论文 ID
      methods:  list of dict {method_id, kind, name, validation_status,
                             evidence_sentence_ids: list of sid, ...}
      sentence_index: {sid: sentence dict}
      max_trigger_span: 允许两方法段落编号差 ≤ 此值 (只对 trigger-based pairing 生效)

    Returns:
      (candidate_pairs: list of dict, stats: dict)
    """
    n = len(methods)
    theoretical_all = n * (n - 1) // 2

    trigger_sids = scan_trigger_sentences(sentence_index)
    trigger_para_nums = {parse_sentence_id(s)[1] for s in trigger_sids
                          if parse_sentence_id(s)}

    pairs = []
    seen = set()

    for m1, m2 in itertools.combinations(methods, 2):
        pair_key = tuple(sorted([m1["method_id"], m2["method_id"]]))
        if pair_key in seen:
            continue
        seen.add(pair_key)

        p1 = _para_nums(m1.get("evidence_sentence_ids") or [])
        p2 = _para_nums(m2.get("evidence_sentence_ids") or [])
        if not p1 or not p2:
            continue

        # 最近段落差
        min_diff = min(abs(a - b) for a in p1 for b in p2)

        # 段落范围内的 trigger 数量
        pmin = min(min(p1), min(p2))
        pmax = max(max(p1), max(p2))
        span = pmax - pmin
        triggers_in_range = [pn for pn in trigger_para_nums if pmin <= pn <= pmax]
        has_trigger = len(triggers_in_range) > 0

        # 判定 pair_source (优先级从强到弱)
        pair_source = None
        if min_diff == 0:
            pair_source = "same_paragraph"
        elif min_diff == 1:
            pair_source = "adjacent_paragraph"
        elif has_trigger and span <= max_trigger_span:
            pair_source = f"trigger_in_span_{span}p"
        elif m1["kind"] != m2["kind"] and has_trigger:
            # own vs ref, 且中间有 trigger — 保留
            pair_source = "own_vs_ref_with_trigger"

        if not pair_source:
            continue

        # 相关连接句 (供 LLM 参考)
        connector_sids = [s for s in trigger_sids
                          if parse_sentence_id(s)
                          and pmin <= parse_sentence_id(s)[1] <= pmax]

        pairs.append({
            "pair_id": f"P{len(pairs) + 1:03d}",
            "paper_id": paper_id,
            "method_a_id": m1["method_id"],
            "method_b_id": m2["method_id"],
            "method_a_name": m1["name"],
            "method_b_name": m2["name"],
            "method_a_kind": m1["kind"],
            "method_b_kind": m2["kind"],
            "method_a_status": m1.get("validation_status", "accepted"),
            "method_b_status": m2.get("validation_status", "accepted"),
            "method_a_evidence_sids": m1.get("evidence_sentence_ids") or [],
            "method_b_evidence_sids": m2.get("evidence_sentence_ids") or [],
            "method_a_citation_clue": m1.get("citation_clue", ""),
            "method_b_citation_clue": m2.get("citation_clue", ""),
            "pair_source": pair_source,
            "min_para_diff": min_diff,
            "trigger_para_count": len(triggers_in_range),
            "connector_sentence_ids": connector_sids[:8],   # 上限 8 条给 LLM
            "para_span": span,
        })

    stats = {
        "n_methods": n,
        "theoretical_pairs": theoretical_all,
        "filtered_pairs": len(pairs),
        "trigger_sentences": len(trigger_sids),
    }
    return pairs, stats
