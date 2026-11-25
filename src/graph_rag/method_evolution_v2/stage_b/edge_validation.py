"""Stage B edge 校验 + 分级.

acceptance 硬性条件(spec 六):
  1. 两端方法均 accepted (candidate 参与 → 结果最多是 candidate)
  2. relation_evidence_sentence_ids 全部有效
  3. 原文切片一致 (由 sentence_index 保证)
  4. audit.support == 'supported'
  5. audit.direction == 'correct'
  6. audit.relation_check == 'correct'

任一失败 → candidate 或 rejected.
"""
from __future__ import annotations

from method_evolution_v2.stage_b.year_utils import (
    extract_year_from_citation_clue,
    temporal_status_for_pair,
)


VALID_RELATIONS = ("EXTENDS", "IMPROVES", "ADAPTS", "REPLACES")


def _resolve_evidence(sids: list, sentence_index: dict) -> tuple:
    """(evidence_spans, missing_ids, evidence_quote, char_start, char_end,
        section, para_id) — 与 Stage A 同款合并逻辑."""
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

    # 排序 & 合并连续段
    found_sorted = sorted(found, key=lambda x: (x["char_start"], x["char_end"]))
    spans = []
    cur = None
    for s in found_sorted:
        if cur is None:
            cur = {
                "char_start": s["char_start"],
                "char_end": s["char_end"],
                "text": s["sentence_text"],
                "section_type": s["section_type"],
                "section_name": s["section_name"],
                "para_id": s["para_id"],
                "sentence_ids": [s["sentence_id"]],
            }
            continue
        if s["para_id"] == cur["para_id"] and s["char_start"] == cur["char_end"]:
            cur["char_end"] = s["char_end"]
            cur["text"] += s["sentence_text"]
            cur["sentence_ids"].append(s["sentence_id"])
        else:
            spans.append(cur)
            cur = {
                "char_start": s["char_start"],
                "char_end": s["char_end"],
                "text": s["sentence_text"],
                "section_type": s["section_type"],
                "section_name": s["section_name"],
                "para_id": s["para_id"],
                "sentence_ids": [s["sentence_id"]],
            }
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


REJECT_REASONS_B = {
    "invalid_relation_type": "relation 不在 EXTENDS/IMPROVES/ADAPTS/REPLACES",
    "endpoint_method_not_found": "from_method_id 或 to_method_id 未在方法列表",
    "no_evidence_ids": "relation_evidence_sentence_ids 为空",
    "all_evidence_ids_missing": "所有 sentence_id 都不在索引",
    "partial_evidence_ids_missing": "部分 sentence_id 不在索引",
    "endpoint_is_candidate": "至少一端方法是 candidate, 关系最多 candidate",
    "audit_unsupported": "审查 support=unsupported",
    "audit_weak_support": "审查 support=weak",
    "audit_direction_reversed": "审查 direction=reversed",
    "audit_direction_unclear": "审查 direction=unclear",
    "audit_wrong_relation_type": "审查 relation_check=wrong_type",
    "audit_relation_unclear": "审查 relation_check=unclear",
    "temporal_conflict": "from_year < to_year, 时间冲突",
    "audit_missing": "未找到对应 pair_id 的审查结果",
    "same_method_endpoints": "from_method_id == to_method_id (自环)",
}


def validate_and_classify_edge(rel: dict, methods_by_id: dict,
                                 sentence_index: dict,
                                 audit_by_pair: dict) -> dict:
    """给 extractor 输出的一条 relation 打校验状态.

    Args:
      rel: extractor 返回的关系 dict
      methods_by_id: {method_id: method_dict (含 validation_status, citation_clue, name, kind, evidence_sentence_ids)}
      sentence_index: {sid: sentence dict}
      audit_by_pair: {pair_id: audit dict (support/direction/relation_check/suggested_relation/audit_reason)}

    Returns:
      edge dict with:
        paper_id, pair_id, from_method_id, to_method_id, from_method_name, to_method_name,
        relation, relation_evidence_sentence_ids, evidence_missing_ids, evidence_spans,
        evidence_quote, evidence_section, evidence_char_start, evidence_char_end,
        direction_basis, relation_reason, confidence_llm,
        audit_support, audit_direction, audit_relation_check, audit_suggested_relation, audit_reason,
        endpoint_a_status, endpoint_b_status,
        from_year, to_year, temporal_status,
        validation_status: accepted | candidate | rejected,
        rejected_reason
    """
    reasons = []
    pair_id = rel.get("pair_id", "")
    from_id = (rel.get("from_method_id") or "").strip()
    to_id = (rel.get("to_method_id") or "").strip()
    relation = (rel.get("relation") or "").strip().upper()
    sids = rel.get("relation_evidence_sentence_ids") or []
    if not isinstance(sids, list):
        sids = []
    sids = [str(x).strip() for x in sids if str(x).strip()]

    # 端点方法必须都在
    m_from = methods_by_id.get(from_id)
    m_to = methods_by_id.get(to_id)
    if m_from is None or m_to is None:
        reasons.append("endpoint_method_not_found")
    if from_id and to_id and from_id == to_id:
        reasons.append("same_method_endpoints")

    # 关系类型
    if relation not in VALID_RELATIONS:
        reasons.append("invalid_relation_type")

    # 证据 ID 存在性 + 拼装
    spans, missing, quote, cs, ce, sec, para_id = _resolve_evidence(sids, sentence_index)
    if not sids:
        reasons.append("no_evidence_ids")
    elif missing and not spans:
        reasons.append("all_evidence_ids_missing")
    elif missing:
        reasons.append("partial_evidence_ids_missing")

    # 端点 accepted / candidate 检查
    endpoint_a_status = (m_from or {}).get("validation_status", "unknown")
    endpoint_b_status = (m_to or {}).get("validation_status", "unknown")
    both_accepted = endpoint_a_status == "accepted" and endpoint_b_status == "accepted"

    # 年份
    from_year = extract_year_from_citation_clue((m_from or {}).get("citation_clue", ""))
    to_year = extract_year_from_citation_clue((m_to or {}).get("citation_clue", ""))
    temporal = temporal_status_for_pair(from_year, to_year)
    if temporal == "conflict":
        # spec 七: 明确冲突进入 candidate/rejected; 但文本方向优先, 所以只降级不直接拒
        reasons.append("temporal_conflict")

    # 审查
    audit = audit_by_pair.get(pair_id) if pair_id else None
    if audit is None:
        reasons.append("audit_missing")
        support = "unknown"
        direction = "unknown"
        relation_check = "unknown"
        suggested = ""
        audit_reason = ""
    else:
        support = (audit.get("support") or "").strip().lower()
        direction = (audit.get("direction") or "").strip().lower()
        relation_check = (audit.get("relation_check") or "").strip().lower()
        suggested = (audit.get("suggested_relation") or "").strip().upper()
        audit_reason = (audit.get("audit_reason") or "").strip()

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

    # ---- 最终分级 ----
    # 硬性拒绝: 类型不合法 / 端点缺失 / ID 无效 / 自环 / audit missing
    hard_reject = any(r in reasons for r in (
        "invalid_relation_type", "endpoint_method_not_found",
        "no_evidence_ids", "all_evidence_ids_missing",
        "same_method_endpoints", "audit_missing",
    ))
    if hard_reject:
        status = "rejected"
    else:
        # accepted 严格全通过
        can_accept = (
            not reasons
            or (len(reasons) == 0)
        )
        if (
            both_accepted
            and support == "supported"
            and direction == "correct"
            and relation_check == "correct"
            and not missing
            and temporal != "conflict"
        ):
            status = "accepted"
        else:
            # 其余非硬性失败 → candidate
            status = "candidate"

    return {
        "paper_id": (m_from or m_to or {}).get("paper_id", ""),
        "pair_id": pair_id,
        "from_method_id": from_id,
        "to_method_id": to_id,
        "from_method_name": (m_from or {}).get("name", ""),
        "to_method_name": (m_to or {}).get("name", ""),
        "relation": relation,
        "relation_evidence_sentence_ids": sids,
        "evidence_missing_ids": missing,
        "evidence_spans": spans,
        "evidence_quote": quote,
        "evidence_section": sec,
        "evidence_para_id": para_id,
        "evidence_char_start": cs,
        "evidence_char_end": ce,
        "direction_basis": (rel.get("direction_basis") or "").strip(),
        "relation_reason": (rel.get("relation_reason") or "").strip(),
        "confidence_llm": (rel.get("confidence_llm") or "").strip(),
        "audit_support": support,
        "audit_direction": direction,
        "audit_relation_check": relation_check,
        "audit_suggested_relation": suggested,
        "audit_reason": audit_reason,
        "endpoint_a_status": endpoint_a_status,
        "endpoint_b_status": endpoint_b_status,
        "from_year": from_year,
        "to_year": to_year,
        "temporal_status": temporal,
        "validation_status": status,
        "rejected_reason": ",".join(reasons),
    }
