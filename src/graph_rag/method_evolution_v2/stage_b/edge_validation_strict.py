"""Stage B v2 strict edge validation.

11 硬性 accepted 条件 (spec 五):
  1. 两端都是 accepted 方法
  2. 两端是**两个独立方法**, 不是整体-组件 (audit.linkage_type=independent_methods)
  3. evidence sentence_id 全部存在
  4. 原文切片一致 (由 sentence_index 保证 exact)
  5. 有明确关系触发语 (含 trigger word in evidence 或 audit 认可)
  6. endpoint_linkage ≠ ambiguous
  7. audit.support = supported
  8. audit.direction = correct
  9. audit.relation_check = correct
 10. auditor 完整返回 (audit_by_pair 命中)
 11. 无年份明确冲突
 加: 12. 非 duplicate / alias (audit.linkage_type != duplicate_or_alias)
"""
from __future__ import annotations

from method_evolution_v2.stage_b.year_utils import (
    extract_year_from_citation_clue,
    temporal_status_for_pair,
)
from method_evolution_v2.stage_b.duplicate_detection import looks_like_alias
from method_evolution_v2.stage_b.pair_generator import TRIGGER_WORDS


VALID_RELATIONS = ("EXTENDS", "IMPROVES", "ADAPTS", "REPLACES")


def _resolve_evidence(sids: list, sentence_index: dict) -> tuple:
    """(spans, missing_ids, quote, cs, ce, section, para_id). 与 Stage A / v1 一致."""
    if not sids:
        return [], [], "", -1, -1, "", ""
    found, missing = [], []
    for sid in sids:
        s = sentence_index.get(sid)
        if s is None:
            missing.append(sid)
        else:
            found.append(s)
    if not found:
        return [], missing, "", -1, -1, "", ""

    found_sorted = sorted(found, key=lambda x: (x["char_start"], x["char_end"]))
    spans = []
    cur = None
    for s in found_sorted:
        if cur is None:
            cur = {"char_start": s["char_start"], "char_end": s["char_end"],
                   "text": s["sentence_text"],
                   "section_type": s["section_type"], "section_name": s["section_name"],
                   "para_id": s["para_id"], "sentence_ids": [s["sentence_id"]]}
            continue
        if s["para_id"] == cur["para_id"] and s["char_start"] == cur["char_end"]:
            cur["char_end"] = s["char_end"]
            cur["text"] += s["sentence_text"]
            cur["sentence_ids"].append(s["sentence_id"])
        else:
            spans.append(cur)
            cur = {"char_start": s["char_start"], "char_end": s["char_end"],
                   "text": s["sentence_text"],
                   "section_type": s["section_type"], "section_name": s["section_name"],
                   "para_id": s["para_id"], "sentence_ids": [s["sentence_id"]]}
    if cur:
        spans.append(cur)
    if len(spans) == 1:
        quote = spans[0]["text"]
        cs, ce = spans[0]["char_start"], spans[0]["char_end"]
        sec = spans[0]["section_name"] or spans[0]["section_type"]
        pid = spans[0]["para_id"]
    else:
        quote = " ... ".join(s["text"] for s in spans)
        cs = min(s["char_start"] for s in spans)
        ce = max(s["char_end"] for s in spans)
        main = max(spans, key=lambda x: x["char_end"] - x["char_start"])
        sec = main["section_name"] or main["section_type"]
        pid = main["para_id"]
    return spans, missing, quote, cs, ce, sec, pid


REJECT_REASONS_STRICT = {
    # 硬性拒绝 (rejected)
    "invalid_relation_type": "关系不在 4 类之列",
    "endpoint_method_not_found": "端点 method_id 不存在",
    "same_method_endpoints": "from == to 自环",
    "no_evidence_ids": "无证据 sentence_id",
    "all_evidence_ids_missing": "所有 sentence_id 都不在索引",
    "audit_missing": "auditor 没返回该 pair",
    "whole_component_relation": "两方法是整体-组件, 不构成演化关系",
    "duplicate_or_alias": "两方法实际是同一技术",
    "endpoint_linkage_ambiguous": "证据没明确点名两方法, 属模糊指代",
    "no_explicit_trigger": "证据句无明确关系触发语 (相比/基础上/借鉴/替代 等)",
    # 降级 candidate 的软条件
    "partial_evidence_ids_missing": "部分 sentence_id 不存在",
    "endpoint_is_candidate": "至少一端方法是 candidate",
    "audit_unsupported": "审查 support=unsupported",
    "audit_weak_support": "审查 support=weak",
    "audit_direction_reversed": "审查 direction=reversed",
    "audit_direction_unclear": "审查 direction=unclear",
    "audit_wrong_relation_type": "审查 relation_check=wrong_type",
    "audit_relation_unclear": "审查 relation_check=unclear",
    "temporal_conflict": "from_year < to_year",
    "audit_linkage_other": "审查 linkage_type=other",
    "extractor_no_relation": "抽取器已判 NO_RELATION",
    "heuristic_alias_flag": "本地启发式判定疑似别名",
}


def _has_explicit_trigger(evidence_quote: str) -> bool:
    """证据句是否含明确关系触发语."""
    if not evidence_quote:
        return False
    return any(w in evidence_quote for w in TRIGGER_WORDS)


def validate_and_classify_edge_strict(
    rel: dict, methods_by_id: dict,
    sentence_index: dict, audit_by_pair: dict,
) -> dict:
    """v2 strict 分级. rel 是抽取器输出的一条 (含 verdict / from / to / sids ...)."""
    reasons = []
    pair_id = rel.get("pair_id", "")
    verdict = (rel.get("verdict") or rel.get("relation") or "").strip().upper()
    from_id = (rel.get("from_method_id") or "").strip()
    to_id = (rel.get("to_method_id") or "").strip()
    sids = rel.get("relation_evidence_sentence_ids") or []
    if not isinstance(sids, list):
        sids = []
    sids = [str(x).strip() for x in sids if str(x).strip()]

    # ---- verdict = NO_RELATION 直接 rejected (记录, 不占用 candidate 池) ----
    if verdict in ("NO_RELATION", "NONE", ""):
        # 也解析证据 (若有) 便于人工看
        spans, missing, quote, cs, ce, sec, pid = _resolve_evidence(sids, sentence_index)
        return _build_result(rel, verdict, from_id, to_id, sids,
                              spans, missing, quote, cs, ce, sec, pid,
                              methods_by_id, audit_by_pair, pair_id,
                              temporal_status="unknown",
                              from_year=None, to_year=None,
                              endpoint_a_status="", endpoint_b_status="",
                              validation_status="rejected",
                              reasons=["extractor_no_relation"],
                              has_trigger=False, alias_flag=("", ""))

    # ---- 关系类型合法性 ----
    if verdict not in VALID_RELATIONS:
        reasons.append("invalid_relation_type")

    # ---- 端点存在 ----
    m_from = methods_by_id.get(from_id)
    m_to = methods_by_id.get(to_id)
    if m_from is None or m_to is None:
        reasons.append("endpoint_method_not_found")
    if from_id and to_id and from_id == to_id:
        reasons.append("same_method_endpoints")

    endpoint_a_status = (m_from or {}).get("validation_status", "unknown")
    endpoint_b_status = (m_to or {}).get("validation_status", "unknown")
    both_accepted = endpoint_a_status == "accepted" and endpoint_b_status == "accepted"

    # ---- 证据解析 ----
    spans, missing, quote, cs, ce, sec, para_id = _resolve_evidence(sids, sentence_index)
    if not sids:
        reasons.append("no_evidence_ids")
    elif missing and not spans:
        reasons.append("all_evidence_ids_missing")
    elif missing:
        reasons.append("partial_evidence_ids_missing")

    # ---- 触发语检查 ----
    has_trigger = _has_explicit_trigger(quote)
    if not has_trigger and not missing and spans:
        # 找不到 trigger 但 evidence 存在 → 硬性拒绝 (spec 五)
        reasons.append("no_explicit_trigger")

    # ---- 年份 ----
    from_year = extract_year_from_citation_clue((m_from or {}).get("citation_clue", ""))
    to_year = extract_year_from_citation_clue((m_to or {}).get("citation_clue", ""))
    temporal = temporal_status_for_pair(from_year, to_year)
    if temporal == "conflict":
        reasons.append("temporal_conflict")

    # ---- 名字启发式 alias ----
    a_name = (m_from or {}).get("name", "")
    b_name = (m_to or {}).get("name", "")
    alias_flag = ("", "")
    if a_name and b_name:
        is_alias, alias_reason = looks_like_alias(a_name, b_name)
        if is_alias:
            alias_flag = (is_alias, alias_reason)
            reasons.append("heuristic_alias_flag")

    # ---- 审查器结果 ----
    audit = audit_by_pair.get(pair_id) if pair_id else None
    if audit is None:
        reasons.append("audit_missing")
        linkage_type = "unknown"
        endpoint_linkage = "unknown"
        coreference_explanation = ""
        support = "unknown"
        direction = "unknown"
        relation_check = "unknown"
        suggested = ""
        audit_reason = ""
    else:
        linkage_type = (audit.get("linkage_type") or "").strip().lower()
        endpoint_linkage = (audit.get("endpoint_linkage") or "").strip().lower()
        coreference_explanation = (audit.get("coreference_explanation") or "").strip()
        support = (audit.get("support") or "").strip().lower()
        direction = (audit.get("direction") or "").strip().lower()
        relation_check = (audit.get("relation_check") or "").strip().lower()
        suggested = (audit.get("suggested_relation") or "").strip().upper()
        audit_reason = (audit.get("audit_reason") or "").strip()

        if linkage_type == "whole_component":
            reasons.append("whole_component_relation")
        elif linkage_type == "duplicate_or_alias":
            reasons.append("duplicate_or_alias")
        elif linkage_type == "other":
            reasons.append("audit_linkage_other")

        if endpoint_linkage == "ambiguous":
            reasons.append("endpoint_linkage_ambiguous")

        if support == "unsupported":
            reasons.append("audit_unsupported")
        elif support == "weak":
            reasons.append("audit_weak_support")

        if direction == "reversed":
            reasons.append("audit_direction_reversed")
        elif direction == "unclear":
            reasons.append("audit_direction_unclear")

        if relation_check == "wrong_type":
            reasons.append("audit_wrong_relation_type")
        elif relation_check == "unclear":
            reasons.append("audit_relation_unclear")

    if not both_accepted:
        reasons.append("endpoint_is_candidate")

    # ---- 分级决策 ----
    # 硬性拒绝
    HARD_REJECT = (
        "invalid_relation_type", "endpoint_method_not_found",
        "same_method_endpoints", "no_evidence_ids",
        "all_evidence_ids_missing", "audit_missing",
        "whole_component_relation", "duplicate_or_alias",
        "endpoint_linkage_ambiguous", "no_explicit_trigger",
        "extractor_no_relation",
    )
    hard = any(r in reasons for r in HARD_REJECT)

    # 11 硬条件全通过 → accepted
    if (
        not hard
        and not reasons  # 没有任何 reason
        and both_accepted
        and linkage_type == "independent_methods"
        and endpoint_linkage in ("explicit_both", "adjacent_coreference")
        and support == "supported"
        and direction == "correct"
        and relation_check == "correct"
        and temporal != "conflict"
        and not missing
        and has_trigger
    ):
        status = "accepted"
    elif hard:
        status = "rejected"
    else:
        status = "candidate"

    return _build_result(rel, verdict, from_id, to_id, sids,
                          spans, missing, quote, cs, ce, sec, para_id,
                          methods_by_id, audit_by_pair, pair_id,
                          temporal_status=temporal,
                          from_year=from_year, to_year=to_year,
                          endpoint_a_status=endpoint_a_status,
                          endpoint_b_status=endpoint_b_status,
                          validation_status=status,
                          reasons=reasons,
                          has_trigger=has_trigger,
                          alias_flag=alias_flag)


def _build_result(rel, verdict, from_id, to_id, sids,
                   spans, missing, quote, cs, ce, sec, para_id,
                   methods_by_id, audit_by_pair, pair_id,
                   temporal_status, from_year, to_year,
                   endpoint_a_status, endpoint_b_status,
                   validation_status, reasons,
                   has_trigger, alias_flag):
    m_from = methods_by_id.get(from_id, {}) or {}
    m_to = methods_by_id.get(to_id, {}) or {}
    audit = audit_by_pair.get(pair_id, {}) or {}

    return {
        "paper_id": (m_from.get("paper_id") or m_to.get("paper_id") or ""),
        "pair_id": pair_id,
        "extractor_verdict": verdict,
        "relation": verdict if verdict in VALID_RELATIONS else "",
        "from_method_id": from_id,
        "to_method_id": to_id,
        "from_method_name": m_from.get("name", ""),
        "to_method_name": m_to.get("name", ""),
        "relation_evidence_sentence_ids": sids,
        "evidence_missing_ids": missing,
        "evidence_spans": spans,
        "evidence_quote": quote,
        "evidence_section": sec,
        "evidence_para_id": para_id,
        "evidence_char_start": cs,
        "evidence_char_end": ce,
        "explicit_trigger_hit": has_trigger,
        "heuristic_alias_flag": alias_flag[0] if alias_flag else False,
        "heuristic_alias_reason": alias_flag[1] if alias_flag else "",
        "direction_basis": (rel.get("direction_basis") or "").strip(),
        "relation_reason": (rel.get("relation_reason") or "").strip(),
        "extractor_note": (rel.get("note") or "").strip(),
        "confidence_llm": (rel.get("confidence_llm") or "").strip(),
        "audit_linkage_type": (audit.get("linkage_type") or "").strip().lower(),
        "audit_endpoint_linkage": (audit.get("endpoint_linkage") or "").strip().lower(),
        "audit_coreference_explanation": (audit.get("coreference_explanation") or "").strip(),
        "audit_support": (audit.get("support") or "").strip().lower(),
        "audit_direction": (audit.get("direction") or "").strip().lower(),
        "audit_relation_check": (audit.get("relation_check") or "").strip().lower(),
        "audit_suggested_relation": (audit.get("suggested_relation") or "").strip().upper(),
        "audit_reason": (audit.get("audit_reason") or "").strip(),
        "endpoint_a_status": endpoint_a_status,
        "endpoint_b_status": endpoint_b_status,
        "from_year": from_year,
        "to_year": to_year,
        "temporal_status": temporal_status,
        "validation_status": validation_status,
        "rejected_reason": ",".join(reasons),
    }
