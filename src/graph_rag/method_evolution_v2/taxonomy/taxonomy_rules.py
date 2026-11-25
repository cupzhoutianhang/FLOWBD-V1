"""taxonomy_rules.py — 论文级储能分类规则引擎 (v1.0, 纯本地, 无 LLM).

设计要点见 `paper/method_evolution_v2/taxonomy_design_v1.md` (v1.1 版):

  - storage_domain 拆为 primary / secondary / candidates 三字段
  - method_type 拆为 primary / secondary 两字段
  - cross_domain_method 只用于"方法本身跨域"; 不代表两储能域并存
  - electromagnetic_storage 只含 SMES 类; supercapacitor 归 electrochemical
  - technology_variant 只放技术路线/化学体系变体; 材料体系不进
  - paper_context_status ∈ {confirmed, candidate, unknown, non_storage}
  - method_label_state 不在本轮生成

严格约束:
  - 不读 legacy 产物 (V2 与 legacy 完全解耦, 详见 method_evolution_v2/README.md)
  - 不硬编码 paper_id
  - 不调用 LLM
  - evidence 只能来自 title / abstract / heading
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import yaml


TAXONOMY_VERSION = "1.1.1"
# v1.1.1 (2026-07-01): 移除 application_contexts 的 laboratory_material 兜底;
#                      YAML 关键词表同步升级(补齐 蓄冷/蓄热/热化学储能/电池包热管理 等短语).
PAPER_CONTEXT_STATES = ("confirmed", "candidate", "unknown", "non_storage")

_HERE = os.path.dirname(os.path.abspath(__file__))
_KW_PATH = os.path.join(_HERE, "taxonomy_keywords_v1.yaml")

_LOCATION_LABELS = ("title", "abstract", "heading")


# ============================================================
# YAML 加载 (进程内 cache)
# ============================================================

_KW_CACHE: dict | None = None


def load_keywords(force: bool = False) -> dict:
    """加载 taxonomy_keywords_v1.yaml. 只有本文件里的 YAML 会被读."""
    global _KW_CACHE
    if _KW_CACHE is None or force:
        with open(_KW_PATH, "r", encoding="utf-8") as f:
            _KW_CACHE = yaml.safe_load(f)
    return _KW_CACHE


# ============================================================
# 辅助: 从 ParseResult 拆出 title / abstract / heading 文本
# ============================================================

def _get_title(pr) -> str:
    return (pr.document_title or "").strip()


def _get_abstract(pr) -> str:
    parts = []
    for s in pr.sections:
        if s.section_type != "abstract":
            continue
        for p in s.paragraphs:
            if p.text:
                parts.append(p.text)
    return "\n".join(parts)


def _get_headings(pr) -> str:
    return "\n".join(s.raw_heading for s in pr.sections if s.raw_heading)


def _build_text_map(pr) -> dict:
    return {
        "title": _get_title(pr),
        "abstract": _get_abstract(pr),
        "heading": _get_headings(pr),
    }


# ============================================================
# 打分
# ============================================================

_ASCII_KW_RE_CACHE: dict = {}


def _is_ascii(s: str) -> bool:
    return all(ord(c) < 128 for c in s)


def _compile_ascii_kw(kw: str) -> re.Pattern:
    """对 ASCII 关键词编译带非字母数字边界的正则, 避免 'EV' 匹到 'dEVelopment'.

    对含 CJK 或其他非 ASCII 字符的关键词, 不走此路径 (调用方用 substring 匹配).
    """
    if kw not in _ASCII_KW_RE_CACHE:
        _ASCII_KW_RE_CACHE[kw] = re.compile(
            rf"(?<![A-Za-z0-9]){re.escape(kw)}(?![A-Za-z0-9])",
            re.IGNORECASE,
        )
    return _ASCII_KW_RE_CACHE[kw]


def _kw_hit_location(text: str, kw: str) -> bool:
    """kw 是否在 text 中命中. ASCII kw 走词边界正则; CJK kw 走 substring."""
    if not kw or not text:
        return False
    if _is_ascii(kw):
        return _compile_ascii_kw(kw).search(text) is not None
    return kw.lower() in text.lower()


def _score_keywords(text_map: dict, kws: list, weights: dict) -> tuple:
    """扫一组关键词, 返回 (total_score, evidence_list).

    单个 (location, kw) 只计一次 (同 kw 在同一 location 多次出现不重复加分).
    """
    if not kws:
        return 0, []
    total = 0
    evs = []
    seen = set()
    for kw in kws:
        if not kw:
            continue
        for loc, text in text_map.items():
            if _kw_hit_location(text, kw) and (loc, kw.lower()) not in seen:
                seen.add((loc, kw.lower()))
                w = weights.get(loc, 0)
                total += w
                evs.append({
                    "location": loc,
                    "matched": kw,
                    "weight": w,
                    "excerpt": _excerpt(text, kw),
                    "strength": _strength_of(w),
                })
    return total, evs


def _excerpt(text: str, needle: str, window: int = 40) -> str:
    if not text or not needle:
        return ""
    if _is_ascii(needle):
        m = _compile_ascii_kw(needle).search(text)
        if not m:
            return ""
        idx, end = m.start(), m.end()
    else:
        idx = text.lower().find(needle.lower())
        if idx < 0:
            return ""
        end = idx + len(needle)
    lo = max(0, idx - window // 2)
    hi = min(len(text), end + window // 2)
    return text[lo:hi].replace("\n", " ").strip()


def _strength_of(weight: int) -> str:
    return {3: "strong", 2: "medium", 1: "weak"}.get(weight, "weak")


def _text_contains_any_kw(text: str, kws: list) -> bool:
    return any(_kw_hit_location(text, k) for k in kws)


def _text_contains_all_kws(text: str, kws: list) -> bool:
    return all(_kw_hit_location(text, k) for k in kws)


def _exclusion_fires(text_map: dict, ex: dict) -> bool:
    """判断 exclusion 是否应触发 (if_all_of 全命中 且 unless_any_of 全不命中).

    合并 title+abstract+heading 后按边界感知的方式匹配, 避免 ASCII 短词误伤.
    """
    if_all = ex.get("if_all_of", []) or []
    unless = ex.get("unless_any_of", []) or []
    combined = "\n".join(text_map.values())
    if not _text_contains_all_kws(combined, if_all):
        return False
    if _text_contains_any_kw(combined, unless):
        return False
    return True


# ============================================================
# 主入口
# ============================================================

def classify_taxonomy(parse_result,
                      paper_type_result: dict | None = None,
                      now_iso: str | None = None) -> dict:
    """按规则给一篇论文打 taxonomy 标签.

    Args:
      parse_result: section_parser.ParseResult
      paper_type_result: 可选, paper_type_rules.classify_paper_type() 的输出.
                        用来给 primary_method_type 加一个 review→general_method 的软偏置.
                        分类结果本身仍由 keyword scoring 决定.
      now_iso: 可选, 时间戳字符串. 默认当前时间.
    """
    kw = load_keywords()
    weights = kw["weights"]
    thr = kw["thresholds"]
    text_map = _build_text_map(parse_result)
    now_iso = now_iso or datetime.now().isoformat(timespec="seconds")
    paper_type = (paper_type_result or {}).get("paper_type")

    matched_signals: list = []
    conflicting_signals: list = []
    all_evidence: list = []

    # -------- Step 1: storage_domain 打分 --------
    domain_scores: dict = {}
    domain_ev_indices: dict = {}
    for dom, dom_cfg in (kw.get("storage_domains") or {}).items():
        d_score, d_evs = _score_keywords(text_map, dom_cfg.get("keywords", []), weights)
        # exclusion: 命中 exclusion 则把 if_all_of 里那些 kw 的 hits 从本 domain 扣除
        excl_fired = []
        for ex in dom_cfg.get("exclusions") or []:
            if _exclusion_fires(text_map, ex):
                excl_fired.append(ex)
                # 扣除: 从 evs 里剔除 if_all_of 里的 kw 命中
                excl_kws = {k.lower() for k in ex.get("if_all_of", [])}
                keep = []
                for e in d_evs:
                    if e["matched"].lower() in excl_kws:
                        d_score -= e["weight"]
                    else:
                        keep.append(e)
                d_evs = keep
                conflicting_signals.append({
                    "key": f"exclusion_fired:{dom}",
                    "detail": (f"if_all_of={ex.get('if_all_of')} "
                               f"unless_any_of={ex.get('unless_any_of')} "
                               f"note={ex.get('note', '')}"),
                })
        if d_score > 0:
            base_idx = len(all_evidence)
            for e in d_evs:
                e["for"] = f"storage_domain:{dom}"
                all_evidence.append(e)
            domain_scores[dom] = d_score
            domain_ev_indices[dom] = list(range(base_idx, base_idx + len(d_evs)))

    # -------- Step 2: cross_domain_method gate --------
    # 若存在其他任何真实 storage domain 分数 > 0, cross_domain_method 一律清零
    real_storage_domains = {d for d in domain_scores.keys() if d != "cross_domain_method"}
    if real_storage_domains and "cross_domain_method" in domain_scores:
        # 移除 cross_domain_method 的分数 + evidence
        for i in domain_ev_indices["cross_domain_method"]:
            all_evidence[i]["for"] = f"suppressed:{all_evidence[i]['for']}"
        conflicting_signals.append({
            "key": "cross_domain_method_suppressed",
            "detail": ("other storage domains matched; cross_domain_method is only "
                       "for method-itself-cross-domain, not multi-domain papers"),
        })
        del domain_scores["cross_domain_method"]
        del domain_ev_indices["cross_domain_method"]

    # -------- Step 3: non_storage 信号 --------
    non_storage_hits: list = []
    combined_text = "\n".join(text_map.values())
    for ns_key, ns_cfg in (kw.get("non_storage_signals") or {}).items():
        kws = ns_cfg.get("keywords", []) or []
        unless = ns_cfg.get("unless_any_of", []) or []
        if _text_contains_any_kw(combined_text, kws) and \
           not _text_contains_any_kw(combined_text, unless):
            hit_kw = next(k for k in kws if _kw_hit_location(combined_text, k))
            location = ("title" if _kw_hit_location(text_map["title"], hit_kw) else
                        ("abstract" if _kw_hit_location(text_map["abstract"], hit_kw)
                         else "heading"))
            ev = {
                "location": location,
                "matched": hit_kw,
                "weight": 0,
                "excerpt": _excerpt(text_map[location], hit_kw),
                "strength": "non_storage_signal",
                "for": f"non_storage:{ns_key}",
            }
            all_evidence.append(ev)
            matched_signals.append({
                "key": f"non_storage_signal:{ns_key}",
                "detail": f"matched '{hit_kw}' at {location}",
            })
            non_storage_hits.append(ns_key)

    # -------- Step 4: primary / secondary / candidates 决策 --------
    ranked = sorted(domain_scores.items(), key=lambda kv: kv[1], reverse=True)
    primary = None
    secondary: list = []
    candidates: list = []
    status: str
    reason_bits: list = []

    if not ranked:
        # 没有任何储能领域信号
        if non_storage_hits:
            status = "non_storage"
            reason_bits.append(
                f"no storage-domain keyword scored; non_storage signals fired: {non_storage_hits}"
            )
        else:
            status = "unknown"
            reason_bits.append("no storage keyword scored; no non_storage signal either")
    else:
        top_dom, top_score = ranked[0]
        second_score = ranked[1][1] if len(ranked) > 1 else 0

        matched_signals.append({
            "key": "storage_domain_ranking",
            "detail": "; ".join(f"{d}={s}" for d, s in ranked),
        })

        if top_score < thr["min_primary_score"]:
            # 太弱; non_storage 强则退到 non_storage, 否则 unknown
            if non_storage_hits and top_score < thr["non_storage_override_score"]:
                status = "non_storage"
                reason_bits.append(
                    f"top storage score {top_score} < min_primary_score={thr['min_primary_score']} "
                    f"and non_storage signal(s) present: {non_storage_hits}"
                )
                candidates = [{"domain": d, "score": s} for d, s in ranked
                              if s >= thr["min_candidate_score"]]
            else:
                status = "unknown"
                reason_bits.append(
                    f"top storage score {top_score} < min_primary_score={thr['min_primary_score']}; "
                    "insufficient evidence"
                )
                candidates = [{"domain": d, "score": s} for d, s in ranked
                              if s >= thr["min_candidate_score"]]
        else:
            # top 有资格; 看是否与 second 拉开距离
            margin_denom = max(second_score, 0.5)
            margin = top_score / margin_denom
            if margin >= thr["primary_margin_ratio"]:
                primary = top_dom
                secondary = [d for d, s in ranked[1:] if s >= thr["min_secondary_score"]]
                status = "confirmed"
                reason_bits.append(
                    f"primary={top_dom} (score={top_score}), second={ranked[1][0] if len(ranked)>1 else '-'}"
                    f" (score={second_score}), margin={margin:.2f} >= {thr['primary_margin_ratio']}"
                )
                if secondary:
                    reason_bits.append(f"secondary_domains={secondary}")
            else:
                # 拉不开: primary=null, 全部进 candidates
                primary = None
                candidates = [{"domain": d, "score": s} for d, s in ranked
                              if s >= thr["min_candidate_score"]]
                status = "candidate"
                reason_bits.append(
                    f"top={top_dom}({top_score}) vs second={ranked[1][0]}({second_score}), "
                    f"margin={margin:.2f} < {thr['primary_margin_ratio']}; primary left empty, "
                    "candidates saved"
                )
                conflicting_signals.append({
                    "key": "domain_tie",
                    "detail": f"top {top_dom} vs {ranked[1][0]} within margin threshold",
                })

    # -------- Step 5: technology_subfield (只在 primary 已定时) --------
    subfield = None
    if primary and primary in (kw.get("storage_domains") or {}):
        sub_cfg = (kw["storage_domains"][primary] or {}).get("subfields") or {}
        sub_scores = {}
        for sub_name, sub_conf in sub_cfg.items():
            sub_kws = sub_conf.get("keywords", []) if isinstance(sub_conf, dict) else sub_conf
            s, s_evs = _score_keywords(text_map, sub_kws, weights)
            if s > 0:
                sub_scores[sub_name] = s
                base = len(all_evidence)
                for e in s_evs:
                    e["for"] = f"subfield:{sub_name}"
                    all_evidence.append(e)
        if sub_scores:
            subfield = max(sub_scores.items(), key=lambda kv: kv[1])[0]
            matched_signals.append({
                "key": "subfield_ranking",
                "detail": "; ".join(f"{s}={v}" for s, v in
                                    sorted(sub_scores.items(), key=lambda kv: -kv[1])),
            })

    # -------- Step 6: technology_variant (多标签; 仅储能路线/化学体系变体) --------
    variants: list = []
    for var_name, var_cfg in (kw.get("technology_variants") or {}).items():
        var_kws = var_cfg.get("keywords", [])
        s, v_evs = _score_keywords(text_map, var_kws, weights)
        if s > 0:
            variants.append(var_name)
            for e in v_evs:
                e["for"] = f"technology_variant:{var_name}"
                all_evidence.append(e)

    # -------- Step 7: application_contexts (多标签) --------
    # v1.1.1 修正: 不再有 laboratory_material 兜底默认;
    #             application_context 必须由 evidence 支撑, 无证据 → 空数组.
    apps: list = []
    for app_name, app_cfg in (kw.get("application_contexts") or {}).items():
        app_kws = app_cfg.get("keywords", [])
        if not app_kws:
            continue
        s, a_evs = _score_keywords(text_map, app_kws, weights)
        if s > 0:
            apps.append(app_name)
            for e in a_evs:
                e["for"] = f"application_context:{app_name}"
                all_evidence.append(e)

    # -------- Step 8: method_type primary + secondary --------
    method_scores = {}
    for mt_name, mt_cfg in (kw.get("method_types") or {}).items():
        mt_kws = mt_cfg.get("keywords", [])
        if not mt_kws:
            continue
        s, m_evs = _score_keywords(text_map, mt_kws, weights)
        if s > 0:
            method_scores[mt_name] = s
            for e in m_evs:
                e["for"] = f"method_type:{mt_name}"
                all_evidence.append(e)

    # 软偏置: 若 paper_type=review_article, 强制 primary_method=general_method
    primary_method = None
    secondary_methods: list = []
    if paper_type == "review_article":
        primary_method = "general_method"
        method_reason = ("paper_type_result.paper_type == review_article "
                         "→ primary_method_type forced to general_method")
        # secondary = 其它命中且分够
        secondary_methods = [
            m for m, s in sorted(method_scores.items(), key=lambda kv: -kv[1])
            if m != "general_method" and s >= thr["method_type_secondary_min"]
        ][:3]
    elif method_scores:
        sorted_methods = sorted(method_scores.items(), key=lambda kv: -kv[1])
        primary_method = sorted_methods[0][0]
        secondary_methods = [
            m for m, s in sorted_methods[1:]
            if s >= thr["method_type_secondary_min"]
        ][:3]
        method_reason = (
            f"primary_method_type={primary_method} (score={sorted_methods[0][1]}); "
            f"ranking={'; '.join(f'{m}={s}' for m, s in sorted_methods)}"
        )
    else:
        method_reason = "no method_type keywords hit"

    reason_bits.append(method_reason)

    # -------- Step 9: 组装 --------
    return {
        "paper_id": parse_result.paper_id,
        "paper_type": paper_type,
        "primary_storage_domain": primary,
        "secondary_storage_domains": secondary,
        "domain_candidates": candidates,
        "technology_subfield": subfield,
        "technology_variant": variants,
        "application_contexts": apps,
        "primary_method_type": primary_method,
        "secondary_method_types": secondary_methods,
        "paper_context_status": status,
        "matched_signals": matched_signals,
        "conflicting_signals": conflicting_signals,
        "evidence": all_evidence,
        "decision_reason": " | ".join(reason_bits),
        "taxonomy_version": (
            f"taxonomy_rules={TAXONOMY_VERSION}; "
            f"keywords_yaml={(load_keywords().get('version') or 'unknown')}"
        ),
        "classified_at": now_iso,
    }
