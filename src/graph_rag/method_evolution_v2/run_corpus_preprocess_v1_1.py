"""run_corpus_preprocess_v1_1.py — 全语料 337 篇纯本地预处理 v1.1.

相较 v1 的变化(全部由 spec 决定):
  1. 标题分离: 输出 source_title / canonical_title / title_source / title_confidence
  2. laboratory_material 兜底移除 (无证据 → application_contexts=[])
  3. taxonomy_keywords v1.1.1 (窄口径 kw 补丁)
  4. 加 diff CSV/MD 对比 v1 与 v1.1

不覆盖 corpus_preprocess_v1/, 一律写 corpus_preprocess_v1_1/.

严格约束(spec 七): 不调 LLM · 不读 legacy · 不修改原文 · 不写库 · 不删文件 · 不自动进 Stage A.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import random
import sys
import time
import traceback
from collections import Counter, defaultdict
from datetime import datetime

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_GRAPH_RAG_DIR = os.path.dirname(THIS_DIR)
if SRC_GRAPH_RAG_DIR not in sys.path:
    sys.path.insert(0, SRC_GRAPH_RAG_DIR)

from method_evolution_v2 import config                                    # noqa: E402
from method_evolution_v2.io import section_parser as sp                   # noqa: E402
from method_evolution_v2.paper_type import paper_type_rules as ptr        # noqa: E402
from method_evolution_v2.taxonomy import taxonomy_rules as tr             # noqa: E402


SAMPLE_SEED = 20260701
SAMPLES_PER_DOMAIN = 5
TOP_RISK_N = 30

DOWNLOADED = config.DOWNLOADED_FILES_DIR
YEAR_CSV = config.LEGACY_YEAR_REPORT_CSV


PAPER_TYPES_FIELDS = [
    "paper_id", "paper_type", "rule_confidence",
    "matched_signals", "conflicting_signals", "type_evidence",
    "decision_reason", "parser_version", "classified_at",
    "section_coverage_ratio", "has_text_loss", "abstract_present",
]

TAXONOMY_FIELDS = [
    "paper_id",
    "source_title", "canonical_title", "title_source", "title_confidence",
    "paper_type",
    "primary_storage_domain", "secondary_storage_domains", "domain_candidates",
    "technology_subfield", "technology_variant", "application_contexts",
    "primary_method_type", "secondary_method_types",
    "paper_context_status",
    "matched_signals", "conflicting_signals", "evidence",
    "decision_reason", "taxonomy_version", "classified_at",
    "section_coverage_ratio", "has_text_loss", "abstract_present",
    "year", "year_source",
]

CANONICAL_TITLES_FIELDS = [
    "paper_id", "source_title", "canonical_title",
    "title_source", "title_confidence",
    "source_title_matches_paper_id",
]

FAILED_FIELDS = [
    "paper_id", "full_md_path", "size_bytes", "sha256",
    "stage_failed", "error_type", "error_message",
    "section_coverage_ratio", "has_text_loss",
]

CANDIDATES_FIELDS = [
    "paper_id", "canonical_title", "domain_candidates",
    "matched_signals", "conflicting_signals", "decision_reason",
]

UNKNOWN_FIELDS = [
    "paper_id", "canonical_title", "abstract_present",
    "non_storage_hits", "decision_reason",
]

NON_STORAGE_FIELDS = [
    "paper_id", "canonical_title", "paper_type",
    "non_storage_hits", "storage_evidence_count",
    "decision_reason",
]

CONFLICTS_FIELDS = [
    "paper_id", "canonical_title", "anomaly_code", "detail",
    "paper_type", "primary_storage_domain", "technology_subfield",
    "paper_context_status",
]

DIFF_FIELDS = [
    "paper_id",
    "v1_paper_type", "v11_paper_type",
    "v1_primary_domain", "v11_primary_domain",
    "v1_subfield", "v11_subfield",
    "v1_status", "v11_status",
    "v1_variants", "v11_variants",
    "v1_apps", "v11_apps",
    "v1_primary_method", "v11_primary_method",
    "v1_secondary_domains", "v11_secondary_domains",
    "v1_candidates", "v11_candidates",
    "unknown_transition",
    "status_transition",
    "primary_transition",
    "app_lab_material_change",
    "new_evidence_matched",       # v1.1 里新增命中的关键词
    "title_fallback_v11",
    "change_summary",
]


# ============================================================
# helpers
# ============================================================

def _j(v) -> str:
    if isinstance(v, (list, dict)):
        return json.dumps(v, ensure_ascii=False)
    return "" if v is None else str(v)


def sha256_of_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1 << 16)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def load_year_map() -> dict:
    out = {}
    if not os.path.isfile(YEAR_CSV):
        return out
    with open(YEAR_CSV, "r", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            pid = r.get("paper_id")
            if not pid:
                continue
            out[pid] = {"year": r.get("year", ""), "year_source": r.get("source", "")}
    return out


def _domain_of_subfield(kw_yaml: dict, subfield: str):
    if not subfield:
        return None
    for dom, dcfg in (kw_yaml.get("storage_domains") or {}).items():
        subs = (dcfg or {}).get("subfields") or {}
        if subfield in subs:
            return dom
    return None


def scan_anomalies(tax_row: dict, kw_yaml: dict) -> list:
    """与 v1 driver 完全一致的规则异常扫描 (10 类)."""
    out = []
    primary = tax_row.get("primary_storage_domain")
    subfield = tax_row.get("technology_subfield")
    status = tax_row.get("paper_context_status")
    secondary = tax_row.get("secondary_storage_domains") or []
    candidates = tax_row.get("domain_candidates") or []
    paper_type = tax_row.get("paper_type")
    p_method = tax_row.get("primary_method_type")
    evidence = tax_row.get("evidence") or []

    if subfield:
        expected = _domain_of_subfield(kw_yaml, subfield)
        if expected and primary and expected != primary:
            out.append({"code": "A1_subfield_incompatible_with_primary",
                        "detail": f"subfield={subfield} belongs to {expected}, "
                                   f"primary={primary}"})
    if status == "non_storage":
        strong = [e for e in evidence
                  if e.get("weight", 0) >= 3
                     and e.get("for", "").startswith("storage_domain:")
                     and not e["for"].startswith("suppressed:")]
        if strong:
            out.append({"code": "A2_non_storage_with_strong_storage_signal",
                        "detail": f"{len(strong)} strong storage kws: "
                                   + ", ".join(e["matched"] for e in strong[:5])})
    if paper_type == "patent_analysis" and status == "confirmed" and primary:
        out.append({"code": "A3_patent_analysis_but_storage_confirmed",
                    "detail": f"patent_analysis but primary={primary}, confirmed"})
    experimental = {"synthesis_process", "material_design", "interface_engineering",
                    "electrode_engineering", "electrolyte_engineering", "membrane_engineering"}
    if paper_type == "review_article" and p_method in experimental:
        out.append({"code": "A4_review_but_experimental_method_type",
                    "detail": f"review_article with primary_method_type={p_method}"})
    all_domains = set()
    if primary:
        all_domains.add(primary)
    all_domains.update(secondary)
    all_domains.update(c.get("domain") for c in candidates if isinstance(c, dict))
    all_domains.discard(None)
    if len(all_domains) >= 3:
        out.append({"code": "A5_three_or_more_storage_domains",
                    "detail": f"domains touched: {sorted(all_domains)}"})
    if primary is None and status == "confirmed":
        out.append({"code": "A6_confirmed_without_primary", "detail": ""})
    if subfield and primary is None:
        out.append({"code": "A7_subfield_without_primary",
                    "detail": f"subfield={subfield} but primary null"})
    ns_keys = {m["key"].split(":", 1)[1] for m in tax_row.get("matched_signals") or []
               if m["key"].startswith("non_storage_signal:")}
    fc = "fuel_cell_only" in ns_keys
    hp = "hydrogen_production_only" in ns_keys
    hs = subfield == "hydrogen_storage" or primary == "chemical_energy_storage"
    if (fc or hp) and hs:
        out.append({"code": "A8_fuelcell_or_h2production_vs_h2storage",
                    "detail": f"fuel_cell_only={fc}, hydrogen_production_only={hp}, h2_storage={hs}"})
    if subfield == "supercapacitor" and primary == "electromagnetic_storage":
        out.append({"code": "A9_supercapacitor_under_electromagnetic", "detail": ""})
    if primary == "cross_domain_method" and subfield:
        out.append({"code": "A10_cross_domain_method_with_subfield",
                    "detail": f"cross_domain_method + subfield={subfield}"})
    return out


def risk_score(tax_row: dict, anomalies: list) -> tuple:
    s = 0
    r = []
    if tax_row.get("paper_context_status") == "candidate":
        s += 3; r.append("candidate")
    if tax_row.get("paper_context_status") == "unknown":
        s += 2; r.append("unknown")
    if tax_row.get("paper_context_status") == "unknown" and not tax_row.get("abstract_present"):
        s += 1; r.append("no_abstract")
    conflicts = tax_row.get("conflicting_signals") or []
    if conflicts:
        s += 2 * len(conflicts); r.append(f"conflicts={len(conflicts)}")
    if anomalies:
        s += 3 * len(anomalies); r.append(f"anomalies={[a['code'] for a in anomalies]}")
    if tax_row.get("secondary_storage_domains"):
        s += 1; r.append("secondary")
    return s, r


# ============================================================
# v1 结果加载 (供 diff)
# ============================================================

def load_v1_rows() -> dict:
    """按 paper_id 索引 v1 的 paper_taxonomy 行. 找不到就返回 {}."""
    path = config.CORPUS_PP_V1_PAPER_TAXONOMY_CSV
    if not os.path.isfile(path):
        return {}
    out = {}
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            pid = row.get("paper_id")
            if not pid:
                continue
            out[pid] = row
    return out


def _parse_json_or(v, default):
    if not v:
        return default
    try:
        return json.loads(v)
    except (json.JSONDecodeError, TypeError):
        return default


def compute_diff(v1_row: dict | None, v11: dict) -> dict:
    """diff 一篇论文的 v1 vs v11 分类结果."""
    def g1(k, default=None):
        if not v1_row:
            return default
        v = v1_row.get(k)
        return v if v not in ("", None) else default

    v1_pt = g1("paper_type")
    v1_pd = g1("primary_storage_domain")
    v1_sub = g1("technology_subfield")
    v1_st = g1("paper_context_status")
    v1_var = _parse_json_or(g1("technology_variant"), [])
    v1_apps = _parse_json_or(g1("application_contexts"), [])
    v1_pm = g1("primary_method_type")
    v1_sec = _parse_json_or(g1("secondary_storage_domains"), [])
    v1_cand = _parse_json_or(g1("domain_candidates"), [])
    v1_ev = _parse_json_or(g1("evidence"), [])

    v11_var = v11.get("technology_variant") or []
    v11_apps = v11.get("application_contexts") or []
    v11_sec = v11.get("secondary_storage_domains") or []
    v11_cand = v11.get("domain_candidates") or []
    v11_ev = v11.get("evidence") or []

    # unknown transition
    if v1_st == "unknown" and v11.get("paper_context_status") != "unknown":
        ut = f"unknown -> {v11.get('paper_context_status')}"
    elif v1_st != "unknown" and v11.get("paper_context_status") == "unknown":
        ut = f"{v1_st} -> unknown"
    else:
        ut = ""

    status_transition = (
        f"{v1_st} -> {v11.get('paper_context_status')}"
        if v1_st != v11.get("paper_context_status") else ""
    )
    primary_transition = (
        f"{v1_pd} -> {v11.get('primary_storage_domain')}"
        if v1_pd != v11.get("primary_storage_domain") else ""
    )

    # lab_material 是否被移出 apps
    had_lab = "laboratory_material" in v1_apps
    now_lab = "laboratory_material" in v11_apps
    if had_lab and not now_lab:
        lab_change = "removed_default_lab_material"
    elif not had_lab and now_lab:
        lab_change = "added_explicit_lab_material"
    else:
        lab_change = ""

    # new evidence: v11 里出现的 (location, matched) 元组, 若 v1 evidence 无同名 matched, 视为新命中
    v1_matched = {e.get("matched") for e in v1_ev if isinstance(e, dict)}
    new_kws = sorted({
        e.get("matched") for e in v11_ev
        if isinstance(e, dict) and e.get("matched") not in v1_matched
    })

    summary_bits = []
    if status_transition: summary_bits.append(f"status[{status_transition}]")
    if primary_transition: summary_bits.append(f"primary[{primary_transition}]")
    if v1_sub != v11.get("technology_subfield"):
        summary_bits.append(f"subfield[{v1_sub} -> {v11.get('technology_subfield')}]")
    if lab_change:
        summary_bits.append(lab_change)
    if v1_var != v11_var:
        summary_bits.append(f"variants[{v1_var} -> {v11_var}]")
    if v1_apps != v11_apps:
        summary_bits.append(f"apps[{v1_apps} -> {v11_apps}]")
    if v1_pm != v11.get("primary_method_type"):
        summary_bits.append(f"method[{v1_pm} -> {v11.get('primary_method_type')}]")
    if v1_sec != v11_sec:
        summary_bits.append(f"secondary[{v1_sec} -> {v11_sec}]")
    if v1_cand != v11_cand:
        summary_bits.append(f"candidates[len {len(v1_cand)}->{len(v11_cand)}]")

    return {
        "paper_id": v11["paper_id"],
        "v1_paper_type": v1_pt, "v11_paper_type": v11.get("paper_type"),
        "v1_primary_domain": v1_pd, "v11_primary_domain": v11.get("primary_storage_domain"),
        "v1_subfield": v1_sub, "v11_subfield": v11.get("technology_subfield"),
        "v1_status": v1_st, "v11_status": v11.get("paper_context_status"),
        "v1_variants": v1_var, "v11_variants": v11_var,
        "v1_apps": v1_apps, "v11_apps": v11_apps,
        "v1_primary_method": v1_pm, "v11_primary_method": v11.get("primary_method_type"),
        "v1_secondary_domains": v1_sec, "v11_secondary_domains": v11_sec,
        "v1_candidates": v1_cand, "v11_candidates": v11_cand,
        "unknown_transition": ut,
        "status_transition": status_transition,
        "primary_transition": primary_transition,
        "app_lab_material_change": lab_change,
        "new_evidence_matched": new_kws,
        "title_fallback_v11": v11.get("title_source"),
        "change_summary": " | ".join(summary_bits),
    }


# ============================================================
# 主流程
# ============================================================

def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    # 强制重载 YAML (以防上轮 test 缓存)
    tr.load_keywords(force=True)

    os.makedirs(config.CORPUS_PP_V1_1_DIR, exist_ok=True)
    os.makedirs(config.CORPUS_PP_V1_1_SECTIONS_DIR, exist_ok=True)

    year_map = load_year_map()
    kw_yaml = tr.load_keywords()
    v1_rows = load_v1_rows()      # 供 diff 用

    started_iso = datetime.now().isoformat(timespec="seconds")
    t0 = time.time()

    if not os.path.isdir(DOWNLOADED):
        print(f"ERROR: no downloaded_files at {DOWNLOADED}")
        return 2

    folders = sorted(os.listdir(DOWNLOADED))
    total_folders = len(folders)
    paper_ids = [f for f in folders
                 if os.path.isfile(os.path.join(DOWNLOADED, f, "full.md"))]
    n_input = len(paper_ids)
    print(f"scan folders={total_folders}, with_full_md={n_input}")

    manifest_entries = []
    pt_rows = []
    tax_rows = []
    title_rows = []
    failed_rows = []
    tax_anomalies = []
    per_paper_anomalies = {}
    diff_rows = []

    n_ok = 0
    n_fail = 0
    n_abs_present = 0
    coverage_lt1 = []
    text_loss = []

    for i, pid in enumerate(paper_ids, 1):
        md_path = config.full_md_path(pid)
        entry = {
            "paper_id": pid,
            "full_md_relative_path": config.relative_path(md_path),
            "full_md_absolute_path_at_scan": md_path,
            "exists": True,
            "size_bytes": os.path.getsize(md_path),
            "sha256": sha256_of_file(md_path),
            "parsed_at_iso": "",
            "publish_year": (year_map.get(pid) or {}).get("year", ""),
            "publish_year_source": (year_map.get(pid) or {}).get("year_source", ""),
            "section_parser_version": sp.SECTION_PARSER_VERSION,
            "paper_type_rules_version": ptr.PAPER_TYPE_RULES_VERSION,
            "taxonomy_version": (
                f"taxonomy_rules={tr.TAXONOMY_VERSION}; "
                f"keywords_yaml={kw_yaml.get('version', 'unknown')}"
            ),
            "source_title": "",
            "canonical_title": "",
            "title_source": "",
            "title_confidence": "",
            "processing_status": "ok",
            "error_message": "",
        }

        # 章节解析
        pr = None
        try:
            pr = sp.parse_file(pid, md_path)
            entry["parsed_at_iso"] = pr.parse_time_iso
        except Exception as e:
            n_fail += 1
            entry.update({
                "processing_status": "parse_failed",
                "error_message": f"{type(e).__name__}: {e}",
            })
            manifest_entries.append(entry)
            failed_rows.append({
                "paper_id": pid, "full_md_path": md_path,
                "size_bytes": entry["size_bytes"], "sha256": entry["sha256"],
                "stage_failed": "section_parser",
                "error_type": type(e).__name__,
                "error_message": (str(e) + "\n" + traceback.format_exc())[:2000],
                "section_coverage_ratio": 0.0, "has_text_loss": True,
            })
            print(f"  [{i:>3}/{n_input}] FAIL parser {pid}")
            continue

        # 标题分离 (v1.1.1)
        ti = sp.get_title_info(pr)
        entry.update(ti)

        # sections JSON
        try:
            sp.write_json(pr, os.path.join(config.CORPUS_PP_V1_1_SECTIONS_DIR, f"{pid}.json"))
        except Exception as e:
            n_fail += 1
            entry.update({
                "processing_status": "section_json_write_failed",
                "error_message": f"{type(e).__name__}: {e}",
            })
            manifest_entries.append(entry)
            failed_rows.append({
                "paper_id": pid, "full_md_path": md_path,
                "size_bytes": entry["size_bytes"], "sha256": entry["sha256"],
                "stage_failed": "write_sections_json",
                "error_type": type(e).__name__,
                "error_message": str(e)[:2000],
                "section_coverage_ratio": round(pr.section_coverage_ratio, 6),
                "has_text_loss": pr.has_text_loss,
            })
            print(f"  [{i:>3}/{n_input}] FAIL wjson {pid}")
            continue

        coverage = round(pr.section_coverage_ratio, 6)
        loss = bool(pr.has_text_loss)
        has_abstract = any(s.section_type == "abstract" for s in pr.sections)
        if has_abstract:
            n_abs_present += 1
        if coverage < 1.0:
            coverage_lt1.append((pid, coverage))
        if loss:
            text_loss.append(pid)
        if loss:
            n_fail += 1
            entry.update({
                "processing_status": "text_loss",
                "error_message": f"coverage={coverage}, text_loss=True",
            })
            manifest_entries.append(entry)
            failed_rows.append({
                "paper_id": pid, "full_md_path": md_path,
                "size_bytes": entry["size_bytes"], "sha256": entry["sha256"],
                "stage_failed": "section_parser_text_loss",
                "error_type": "TextLoss",
                "error_message": entry["error_message"],
                "section_coverage_ratio": coverage, "has_text_loss": True,
            })
            print(f"  [{i:>3}/{n_input}] FAIL loss {pid}")
            continue

        # paper_type
        try:
            pt_r = ptr.classify_paper_type(pr)
        except Exception as e:
            n_fail += 1
            entry.update({
                "processing_status": "paper_type_failed",
                "error_message": f"{type(e).__name__}: {e}",
            })
            manifest_entries.append(entry)
            failed_rows.append({
                "paper_id": pid, "full_md_path": md_path,
                "size_bytes": entry["size_bytes"], "sha256": entry["sha256"],
                "stage_failed": "paper_type_rules",
                "error_type": type(e).__name__,
                "error_message": (str(e) + "\n" + traceback.format_exc())[:2000],
                "section_coverage_ratio": coverage, "has_text_loss": loss,
            })
            print(f"  [{i:>3}/{n_input}] FAIL ptype {pid}")
            continue

        # taxonomy
        try:
            tax_r = tr.classify_taxonomy(pr, paper_type_result=pt_r)
        except Exception as e:
            n_fail += 1
            entry.update({
                "processing_status": "taxonomy_failed",
                "error_message": f"{type(e).__name__}: {e}",
            })
            manifest_entries.append(entry)
            failed_rows.append({
                "paper_id": pid, "full_md_path": md_path,
                "size_bytes": entry["size_bytes"], "sha256": entry["sha256"],
                "stage_failed": "taxonomy_rules",
                "error_type": type(e).__name__,
                "error_message": (str(e) + "\n" + traceback.format_exc())[:2000],
                "section_coverage_ratio": coverage, "has_text_loss": loss,
            })
            print(f"  [{i:>3}/{n_input}] FAIL taxonomy {pid}")
            continue

        pt_row = {
            "paper_id": pid, "paper_type": pt_r["paper_type"],
            "rule_confidence": pt_r["rule_confidence"],
            "matched_signals": pt_r["matched_signals"],
            "conflicting_signals": pt_r["conflicting_signals"],
            "type_evidence": pt_r["type_evidence"],
            "decision_reason": pt_r["decision_reason"],
            "parser_version": pt_r["parser_version"],
            "classified_at": pt_r["classified_at"],
            "section_coverage_ratio": coverage, "has_text_loss": loss,
            "abstract_present": has_abstract,
        }
        pt_rows.append(pt_row)

        y = year_map.get(pid) or {}
        tax_row = dict(tax_r)
        tax_row.update({
            "source_title": ti["source_title"],
            "canonical_title": ti["canonical_title"],
            "title_source": ti["title_source"],
            "title_confidence": ti["title_confidence"],
            "section_coverage_ratio": coverage,
            "has_text_loss": loss,
            "abstract_present": has_abstract,
            "year": y.get("year", ""),
            "year_source": y.get("year_source", ""),
        })
        tax_rows.append(tax_row)

        title_rows.append({
            "paper_id": pid,
            "source_title": ti["source_title"],
            "canonical_title": ti["canonical_title"],
            "title_source": ti["title_source"],
            "title_confidence": ti["title_confidence"],
            "source_title_matches_paper_id": (ti["source_title"] == pid) if ti["source_title"] else "N/A",
        })

        an = scan_anomalies(tax_row, kw_yaml)
        per_paper_anomalies[pid] = an
        for a in an:
            tax_anomalies.append({
                "paper_id": pid,
                "canonical_title": ti["canonical_title"],
                "anomaly_code": a["code"], "detail": a["detail"],
                "paper_type": tax_row.get("paper_type"),
                "primary_storage_domain": tax_row.get("primary_storage_domain"),
                "technology_subfield": tax_row.get("technology_subfield"),
                "paper_context_status": tax_row.get("paper_context_status"),
            })

        # diff vs v1
        v1_row = v1_rows.get(pid)
        diff_rows.append(compute_diff(v1_row, tax_row))

        n_ok += 1
        manifest_entries.append(entry)
        if i % 50 == 0 or i == n_input:
            print(f"  [{i:>3}/{n_input}] ok={n_ok} fail={n_fail}")

    dur = time.time() - t0

    # ---- 派生 CSVs (candidates/unknown/non_storage/conflicts) ----
    cand_rows, unknown_rows, non_storage_rows, conflict_rows = [], [], [], []
    for r in tax_rows:
        pid = r["paper_id"]
        ct = r.get("canonical_title", "")
        status = r.get("paper_context_status")
        ns_hits = [m["key"].split(":", 1)[1] for m in r.get("matched_signals") or []
                   if m["key"].startswith("non_storage_signal:")]
        if status == "candidate":
            cand_rows.append({
                "paper_id": pid, "canonical_title": ct,
                "domain_candidates": r.get("domain_candidates") or [],
                "matched_signals": r.get("matched_signals") or [],
                "conflicting_signals": r.get("conflicting_signals") or [],
                "decision_reason": r.get("decision_reason", ""),
            })
        if status == "unknown":
            unknown_rows.append({
                "paper_id": pid, "canonical_title": ct,
                "abstract_present": r.get("abstract_present", False),
                "non_storage_hits": ns_hits,
                "decision_reason": r.get("decision_reason", ""),
            })
        if status == "non_storage":
            storage_ev = [e for e in (r.get("evidence") or [])
                          if e.get("for", "").startswith("storage_domain:")
                          and not e.get("for", "").startswith("suppressed:")]
            non_storage_rows.append({
                "paper_id": pid, "canonical_title": ct,
                "paper_type": r.get("paper_type"),
                "non_storage_hits": ns_hits,
                "storage_evidence_count": len(storage_ev),
                "decision_reason": r.get("decision_reason", ""),
            })
        for c in r.get("conflicting_signals") or []:
            conflict_rows.append({
                "paper_id": pid, "canonical_title": ct,
                "anomaly_code": f"conflict_signal:{c.get('key', '')}",
                "detail": c.get("detail", ""),
                "paper_type": r.get("paper_type"),
                "primary_storage_domain": r.get("primary_storage_domain"),
                "technology_subfield": r.get("technology_subfield"),
                "paper_context_status": status,
            })
        for an in per_paper_anomalies.get(pid, []):
            conflict_rows.append({
                "paper_id": pid, "canonical_title": ct,
                "anomaly_code": an["code"], "detail": an["detail"],
                "paper_type": r.get("paper_type"),
                "primary_storage_domain": r.get("primary_storage_domain"),
                "technology_subfield": r.get("technology_subfield"),
                "paper_context_status": status,
            })

    # ---- 写 CSVs ----
    def _wcsv(path, fields, rows):
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for row in rows:
                w.writerow({k: _j(row.get(k)) for k in fields})

    _wcsv(config.CORPUS_PP_V1_1_PAPER_TYPES_CSV, PAPER_TYPES_FIELDS, pt_rows)
    _wcsv(config.CORPUS_PP_V1_1_PAPER_TAXONOMY_CSV, TAXONOMY_FIELDS, tax_rows)
    _wcsv(config.CORPUS_PP_V1_1_TITLES_CSV, CANONICAL_TITLES_FIELDS, title_rows)
    _wcsv(config.CORPUS_PP_V1_1_FAILED_CSV, FAILED_FIELDS, failed_rows)
    _wcsv(config.CORPUS_PP_V1_1_CANDIDATES_CSV, CANDIDATES_FIELDS, cand_rows)
    _wcsv(config.CORPUS_PP_V1_1_UNKNOWN_CSV, UNKNOWN_FIELDS, unknown_rows)
    _wcsv(config.CORPUS_PP_V1_1_NON_STORAGE_CSV, NON_STORAGE_FIELDS, non_storage_rows)
    _wcsv(config.CORPUS_PP_V1_1_CONFLICTS_CSV, CONFLICTS_FIELDS, conflict_rows)
    _wcsv(config.CORPUS_PP_V1_1_DIFF_CSV, DIFF_FIELDS, diff_rows)

    # ---- source manifest ----
    manifest = {
        "manifest_created_at": datetime.now().isoformat(timespec="seconds"),
        "run_started_at": started_iso,
        "duration_sec": round(dur, 2),
        "input_root": config.relative_path(DOWNLOADED),
        "engine_versions": {
            "section_parser": sp.SECTION_PARSER_VERSION,
            "paper_type_rules": ptr.PAPER_TYPE_RULES_VERSION,
            "taxonomy_rules": tr.TAXONOMY_VERSION,
            "taxonomy_keywords_yaml": kw_yaml.get("version", "unknown"),
        },
        "counts": {
            "total_folders": total_folders,
            "input_papers": n_input,
            "processed_ok": n_ok,
            "failed": n_fail,
        },
        "papers": manifest_entries,
    }
    with open(config.CORPUS_PP_V1_1_MANIFEST_JSON, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    # ============================================================
    # 分布统计
    # ============================================================

    pt_counter = Counter(r["paper_type"] for r in pt_rows)
    pt_conf = defaultdict(Counter)
    for r in pt_rows:
        pt_conf[r["paper_type"]][r["rule_confidence"]] += 1

    primary_counter = Counter(r["primary_storage_domain"] for r in tax_rows)
    subfield_counter = Counter(r["technology_subfield"] for r in tax_rows)
    status_counter = Counter(r["paper_context_status"] for r in tax_rows)
    secondary_size = Counter(len(r["secondary_storage_domains"] or []) for r in tax_rows)
    cand_size = Counter(len(r["domain_candidates"] or []) for r in tax_rows)
    variants_flat = Counter()
    for r in tax_rows:
        for v in r.get("technology_variant") or []:
            variants_flat[v] += 1
    apps_flat = Counter()
    apps_empty = 0
    for r in tax_rows:
        apps = r.get("application_contexts") or []
        if not apps:
            apps_empty += 1
        for a in apps:
            apps_flat[a] += 1
    p_method_counter = Counter(r["primary_method_type"] for r in tax_rows)

    # 标题分布
    title_source_counter = Counter(r["title_source"] for r in title_rows)
    n_source_title_empty = sum(1 for r in title_rows if not r["source_title"])
    n_canonical_empty = sum(1 for r in title_rows if not r["canonical_title"])
    n_paper_id_fallback = title_source_counter.get("paper_id_fallback", 0)
    n_source_vs_pid_diff = sum(
        1 for r in title_rows
        if r["source_title"] and r["source_title"] != r["paper_id"]
    )

    # coverage bins
    cov_bins = Counter()
    for r in tax_rows:
        c = r.get("section_coverage_ratio", 1.0)
        key = ("1.0" if c >= 1.0 else "[0.99, 1.0)" if c >= 0.99
               else "[0.95, 0.99)" if c >= 0.95 else "[0.90, 0.95)" if c >= 0.90 else "<0.90")
        cov_bins[key] += 1

    # ============================================================
    # 代表性抽样 & risk
    # ============================================================
    rng = random.Random(SAMPLE_SEED)
    samples_by_domain = defaultdict(list)
    for r in tax_rows:
        d = r.get("primary_storage_domain") or "(空)"
        samples_by_domain[d].append(r["paper_id"])
    domain_samples = {}
    for d, ids in samples_by_domain.items():
        picks = list(ids); rng.shuffle(picks)
        domain_samples[d] = picks[:SAMPLES_PER_DOMAIN]

    risk_scored = []
    for r in tax_rows:
        pid = r["paper_id"]
        an = per_paper_anomalies.get(pid, [])
        s, reasons = risk_score(r, an)
        if s > 0:
            risk_scored.append((s, pid, reasons))
    risk_scored.sort(key=lambda x: -x[0])
    top_risk = risk_scored[:TOP_RISK_N]

    # ============================================================
    # v1 -> v11 变化摘要
    # ============================================================
    transitions = Counter()
    n_unknown_resolved = 0
    n_new_unknown = 0
    lab_removed = 0
    diff_by_summary_bucket = Counter()
    for d in diff_rows:
        if d["v1_status"] and d["v11_status"] and d["v1_status"] != d["v11_status"]:
            transitions[f"{d['v1_status']} -> {d['v11_status']}"] += 1
            if d["v1_status"] == "unknown" and d["v11_status"] != "unknown":
                n_unknown_resolved += 1
            if d["v1_status"] != "unknown" and d["v11_status"] == "unknown":
                n_new_unknown += 1
        if d["app_lab_material_change"] == "removed_default_lab_material":
            lab_removed += 1
        if d["change_summary"]:
            diff_by_summary_bucket["has_change"] += 1
        else:
            diff_by_summary_bucket["no_change"] += 1

    # 新命中关键词 (Counter)
    new_kw_hits_counter = Counter()
    for d in diff_rows:
        if d["v1_status"] == "unknown" and d["v11_status"] != "unknown":
            for kw in d["new_evidence_matched"] or []:
                new_kw_hits_counter[kw] += 1

    # ---- report JSON ----
    report = {
        "run_started_at": started_iso,
        "duration_sec": round(dur, 2),
        "engine_versions": manifest["engine_versions"],
        "counts": {
            "total_folders": total_folders,
            "input_papers": n_input,
            "processed_ok": n_ok,
            "failed": n_fail,
            "abstract_present": n_abs_present,
            "abstract_missing": n_input - n_abs_present - n_fail,
            "coverage_lt_1_count": len(coverage_lt1),
            "has_text_loss_count": len(text_loss),
            "app_contexts_empty_count": apps_empty,
            "source_title_empty": n_source_title_empty,
            "canonical_title_empty": n_canonical_empty,
            "title_paper_id_fallback": n_paper_id_fallback,
            "source_title_vs_paperid_inconsistent": n_source_vs_pid_diff,
        },
        "distributions": {
            "paper_type": dict(pt_counter),
            "paper_type_by_confidence": {k: dict(v) for k, v in pt_conf.items()},
            "primary_storage_domain": {
                (k if k is not None else "(null)"): v
                for k, v in primary_counter.items()
            },
            "technology_subfield": {
                (k if k is not None else "(null)"): v
                for k, v in subfield_counter.items()
            },
            "paper_context_status": dict(status_counter),
            "secondary_domains_size": dict(secondary_size),
            "domain_candidates_size": dict(cand_size),
            "technology_variant": dict(variants_flat),
            "application_contexts": dict(apps_flat),
            "primary_method_type": {
                (k if k is not None else "(null)"): v
                for k, v in p_method_counter.items()
            },
            "section_coverage_bins": dict(cov_bins),
            "title_source": dict(title_source_counter),
        },
        "rule_anomalies_by_code": dict(Counter(a["anomaly_code"] for a in tax_anomalies)),
        "diff_summary": {
            "status_transitions": dict(transitions),
            "unknown_resolved_count": n_unknown_resolved,
            "new_unknown_count": n_new_unknown,
            "lab_material_removed_count": lab_removed,
            "papers_with_any_change": diff_by_summary_bucket.get("has_change", 0),
            "papers_unchanged": diff_by_summary_bucket.get("no_change", 0),
            "new_kw_hits_when_unknown_resolved": dict(new_kw_hits_counter),
        },
        "samples": {
            "by_primary_domain": domain_samples,
            "unknown_ids": [r["paper_id"] for r in unknown_rows],
            "candidate_ids": [r["paper_id"] for r in cand_rows],
            "non_storage_ids": [r["paper_id"] for r in non_storage_rows],
            "top_risk": [
                {"paper_id": pid, "risk_score": s, "reasons": reasons}
                for s, pid, reasons in top_risk
            ],
        },
    }
    with open(config.CORPUS_PP_V1_1_REPORT_JSON, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # ---- Markdown 报告 ----
    ml = []
    ml.append("# 全语料预处理报告 corpus_preprocess_v1_1\n")
    ml.append(
        f"> 运行开始: {started_iso}\n"
        f"> 耗时: {round(dur, 1)} 秒\n"
        f"> 引擎: section_parser v{sp.SECTION_PARSER_VERSION} · "
        f"paper_type v{ptr.PAPER_TYPE_RULES_VERSION} · "
        f"taxonomy v{tr.TAXONOMY_VERSION} (kw yaml v{kw_yaml.get('version','unknown')})\n"
        f"> 输入: `{config.relative_path(DOWNLOADED)}` (337 篇 full.md)\n"
        f"> 无 LLM · 无 legacy · 无 DB · 未覆盖 corpus_preprocess_v1.\n\n"
    )

    ml.append("## 一、语料清点\n")
    ml.append(
        f"- 输入: **{n_input}** · 成功: **{n_ok}** · 失败: **{n_fail}**\n"
        f"- 摘要识别: **{n_abs_present}** / 缺失: **{n_input - n_abs_present - n_fail}**\n"
        f"- coverage < 1.0: **{len(coverage_lt1)}** · has_text_loss=True: **{len(text_loss)}**\n"
        f"- application_contexts 为空数组: **{apps_empty}** (v1.1.1 移除 lab_material 兜底后的直接反映)\n"
    )

    ml.append("\n## 二、标题分离统计 (v1.1.1)\n")
    ml.append(
        f"- source_title 缺失(paper_id fallback 触发): **{n_source_title_empty}**\n"
        f"- canonical_title 缺失: **{n_canonical_empty}**\n"
        f"- title_source=paper_id_fallback: **{n_paper_id_fallback}**\n"
        f"- title_source=source_markdown: **{title_source_counter.get('source_markdown', 0)}**\n"
        f"- source_title 与 paper_id 不一致(拼写/空格差异): **{n_source_vs_pid_diff}**\n"
    )

    ml.append("\n## 三、章节覆盖率\n| 区间 | 篇数 |\n|---|---:|\n")
    for k in ("1.0", "[0.99, 1.0)", "[0.95, 0.99)", "[0.90, 0.95)", "<0.90"):
        ml.append(f"| {k} | {cov_bins.get(k, 0)} |\n")

    ml.append("\n## 四、paper_type 分布\n| paper_type | 数量 | high | medium | low |\n|---|---:|---:|---:|---:|\n")
    for pt in ("research_article", "review_article", "patent_analysis", "unclear"):
        c = pt_counter.get(pt, 0)
        cc = pt_conf.get(pt, {})
        ml.append(f"| {pt} | {c} | {cc.get('high',0)} | {cc.get('medium',0)} | {cc.get('low',0)} |\n")

    ml.append("\n## 五、taxonomy 分布\n")
    ml.append("### 5.1 primary_storage_domain\n| 值 | 篇数 |\n|---|---:|\n")
    for k, v in sorted(report["distributions"]["primary_storage_domain"].items(),
                       key=lambda kv: -kv[1]):
        ml.append(f"| `{k}` | {v} |\n")

    ml.append("\n### 5.2 technology_subfield (top 20)\n| 值 | 篇数 |\n|---|---:|\n")
    for k, v in sorted(report["distributions"]["technology_subfield"].items(),
                       key=lambda kv: -kv[1])[:20]:
        ml.append(f"| `{k}` | {v} |\n")

    ml.append("\n### 5.3 paper_context_status\n| 状态 | 篇数 |\n|---|---:|\n")
    for k in ("confirmed", "candidate", "unknown", "non_storage"):
        ml.append(f"| {k} | {status_counter.get(k, 0)} |\n")

    ml.append("\n### 5.4 secondary_storage_domains 大小\n| 大小 | 篇数 |\n|---|---:|\n")
    for k in sorted(secondary_size.keys()):
        ml.append(f"| {k} | {secondary_size[k]} |\n")

    ml.append("\n### 5.5 domain_candidates 大小\n| 大小 | 篇数 |\n|---|---:|\n")
    for k in sorted(cand_size.keys()):
        ml.append(f"| {k} | {cand_size[k]} |\n")

    ml.append("\n### 5.6 technology_variant (命中)\n")
    if variants_flat:
        ml.append("| variant | 命中 |\n|---|---:|\n")
        for k, v in sorted(variants_flat.items(), key=lambda kv: -kv[1]):
            ml.append(f"| `{k}` | {v} |\n")
    else:
        ml.append("*(无)*\n")

    ml.append("\n### 5.7 application_contexts (命中)\n")
    if apps_flat:
        ml.append("| context | 命中 |\n|---|---:|\n")
        for k, v in sorted(apps_flat.items(), key=lambda kv: -kv[1]):
            ml.append(f"| `{k}` | {v} |\n")
    else:
        ml.append("*(无)*\n")
    ml.append(f"\n- 无 app_context (空数组) 论文数: **{apps_empty}**\n")

    ml.append("\n### 5.8 primary_method_type (Stage A 提示, 非最终标签)\n| method | 数量 |\n|---|---:|\n")
    for k, v in sorted(report["distributions"]["primary_method_type"].items(),
                       key=lambda kv: -kv[1]):
        ml.append(f"| `{k}` | {v} |\n")

    ml.append("\n## 六、规则异常\n")
    if not tax_anomalies:
        ml.append("*(未发现异常)*\n")
    else:
        ml.append("| 异常代码 | 数量 |\n|---|---:|\n")
        for k, v in sorted(report["rule_anomalies_by_code"].items(), key=lambda kv: -kv[1]):
            ml.append(f"| `{k}` | {v} |\n")

    ml.append("\n## 七、v1 → v1.1 变化摘要 (diff)\n")
    ml.append(f"- 有任何变化的论文: **{diff_by_summary_bucket.get('has_change', 0)}**\n")
    ml.append(f"- 完全无变化: **{diff_by_summary_bucket.get('no_change', 0)}**\n")
    ml.append(f"- unknown → 其他 (由新 kw 拉回来): **{n_unknown_resolved}**\n")
    ml.append(f"- 其他 → unknown: **{n_new_unknown}**\n")
    ml.append(f"- app 移除 laboratory_material 默认的论文: **{lab_removed}**\n")

    if transitions:
        ml.append("\n### 状态转移 (v1 → v1.1)\n| 转移 | 数量 |\n|---|---:|\n")
        for k, v in sorted(transitions.items(), key=lambda kv: -kv[1]):
            ml.append(f"| `{k}` | {v} |\n")

    if new_kw_hits_counter:
        ml.append("\n### unknown → 拉回时新命中的 kw (top)\n| kw | 次数 |\n|---|---:|\n")
        for k, v in sorted(new_kw_hits_counter.items(), key=lambda kv: -kv[1])[:30]:
            ml.append(f"| `{k}` | {v} |\n")

    ml.append("\n## 八、代表性样本\n")
    ml.append("### 8.1 每 primary_storage_domain 抽样\n")
    for dom in sorted(domain_samples.keys()):
        picks = domain_samples[dom]
        ml.append(f"\n**{dom}** ({primary_counter.get(None if dom == '(空)' else dom, 0)} 篇, 抽 {len(picks)}):\n")
        for pid in picks:
            r = next(x for x in tax_rows if x["paper_id"] == pid)
            ml.append(
                f"- `{pid}` → subfield=`{r.get('technology_subfield') or '(空)'}`, "
                f"status={r.get('paper_context_status')}, "
                f"variants={r.get('technology_variant') or []}, "
                f"apps={r.get('application_contexts') or []}\n"
            )

    ml.append(f"\n### 8.2 unknown (共 {len(unknown_rows)})\n")
    for u in unknown_rows[:60]:
        ml.append(f"- `{u['paper_id']}` — abstract={u['abstract_present']}, ns_hits={u['non_storage_hits']}\n")
    if len(unknown_rows) > 60:
        ml.append(f"- ... 余 {len(unknown_rows)-60} 条见 `taxonomy_unknown.csv`\n")

    ml.append(f"\n### 8.3 candidate (共 {len(cand_rows)})\n")
    for c in cand_rows[:30]:
        doms = [d.get("domain") for d in c["domain_candidates"] if isinstance(d, dict)]
        ml.append(f"- `{c['paper_id']}` — candidates={doms}\n")

    ml.append(f"\n### 8.4 non_storage (共 {len(non_storage_rows)})\n")
    for n in non_storage_rows[:60]:
        ml.append(f"- `{n['paper_id']}` — ns_hits={n['non_storage_hits']}, se_count={n['storage_evidence_count']}\n")
    if len(non_storage_rows) > 60:
        ml.append(f"- ... 余 {len(non_storage_rows)-60} 条\n")

    ml.append(f"\n### 8.5 最可能误判 top {TOP_RISK_N}\n")
    ml.append("| # | paper_id | risk | reasons |\n|--:|---|---:|---|\n")
    for i, (s, pid, reasons) in enumerate(top_risk, 1):
        ml.append(f"| {i} | `{pid}` | {s} | {'; '.join(reasons)} |\n")

    ml.append("\n## 九、失败清单\n")
    if failed_rows:
        for r in failed_rows:
            ml.append(f"- `{r['paper_id']}` — {r['stage_failed']}: {r['error_type']}: "
                      f"{r['error_message'][:200]}\n")
    else:
        ml.append("*(0 失败)*\n")

    with open(config.CORPUS_PP_V1_1_REPORT_MD, "w", encoding="utf-8") as f:
        f.writelines(ml)

    # ---- diff MD ----
    dml = []
    dml.append("# preprocessing_diff_v1_to_v1_1\n\n")
    dml.append(f"> v1: taxonomy_keywords v1.0, laboratory_material 兜底存在\n"
               f"> v1.1: taxonomy_keywords v1.1.1, 无 lab_material 兜底, 加窄口径 kw\n\n")
    dml.append(f"- 总论文: {n_ok}\n")
    dml.append(f"- 有任何变化: {diff_by_summary_bucket.get('has_change', 0)}\n")
    dml.append(f"- 完全无变化: {diff_by_summary_bucket.get('no_change', 0)}\n")
    dml.append(f"- unknown → 拉回: {n_unknown_resolved}\n")
    dml.append(f"- 拉回时最常见新 kw:\n")
    for k, v in sorted(new_kw_hits_counter.items(), key=lambda kv: -kv[1])[:20]:
        dml.append(f"  - `{k}`: {v}\n")
    dml.append("\n## 状态转移矩阵\n\n")
    if transitions:
        dml.append("| 转移 | 数量 |\n|---|---:|\n")
        for k, v in sorted(transitions.items(), key=lambda kv: -kv[1]):
            dml.append(f"| `{k}` | {v} |\n")
    else:
        dml.append("*(全部保持不变)*\n")

    dml.append("\n## 逐篇变化 (前 200 条 has_change)\n\n")
    changed = [d for d in diff_rows if d["change_summary"]]
    for d in changed[:200]:
        dml.append(f"### `{d['paper_id']}`\n")
        dml.append(f"- title_fallback_v11: `{d['title_fallback_v11']}`\n")
        dml.append(f"- {d['change_summary']}\n")
        if d["new_evidence_matched"]:
            dml.append(f"- new_kw: {d['new_evidence_matched']}\n")
        dml.append("\n")
    if len(changed) > 200:
        dml.append(f"*... 余 {len(changed)-200} 条见 `preprocessing_diff_v1_to_v1_1.csv`.*\n")

    with open(config.CORPUS_PP_V1_1_DIFF_MD, "w", encoding="utf-8") as f:
        f.writelines(dml)

    # ---- 终端简报 ----
    print()
    print("=" * 70)
    print(f"processed_ok={n_ok}/{n_input}  failed={n_fail}  duration={round(dur,1)}s")
    print(f"paper_type: {dict(pt_counter)}")
    print(f"primary_domain: {dict(primary_counter)}")
    print(f"status: {dict(status_counter)}")
    print(f"anomalies: {len(tax_anomalies)}")
    print(f"apps_empty (no default lab_material): {apps_empty}")
    print(f"title paper_id_fallback: {n_paper_id_fallback} / source_markdown: "
          f"{title_source_counter.get('source_markdown', 0)}")
    print(f"diff: unknown_resolved={n_unknown_resolved}  new_unknown={n_new_unknown}  "
          f"lab_material_removed={lab_removed}")
    print(f"output: {config.relative_path(config.CORPUS_PP_V1_1_DIR)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
