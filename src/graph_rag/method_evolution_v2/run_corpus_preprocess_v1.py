"""run_corpus_preprocess_v1.py — 全语料 337 篇纯本地预处理.

数据流:
  full.md
    → section_parser  (v1.1.1)
    → paper_type_rules (v1.0)
    → taxonomy_rules  (v1.0 引擎 + taxonomy_keywords_v1.yaml v1.0)
  之后:
    - 每篇写 sections/<paper_id>.json
    - 汇总: paper_types.csv, paper_taxonomy.csv, source_manifest.json
    - 派生: failed_papers.csv, taxonomy_candidates.csv, taxonomy_unknown.csv,
            non_storage_papers.csv, taxonomy_conflicts.csv
    - 报告: preprocessing_report.json + preprocessing_report.md

CSV 列表 / 对象字段统一 JSON 序列化 (ensure_ascii=False).

严格约束(spec 七):
  - 不调用 LLM / 外部 API
  - 不做方法抽取 / 关系抽取
  - 不读 legacy 数据(旧 methods / edges / method_outputs / 旧 subfield)
  - 不修改关键词与规则
  - 不修改原始 PDF / full.md
  - 不写 Neo4j / Milvus
  - 不删除任何文件
  - 单篇失败不中断整体; 记录错误
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
    "paper_id",
    "paper_type",
    "rule_confidence",
    "matched_signals",
    "conflicting_signals",
    "type_evidence",
    "decision_reason",
    "parser_version",
    "classified_at",
    "section_coverage_ratio",
    "has_text_loss",
    "abstract_present",
]

TAXONOMY_FIELDS = [
    "paper_id",
    "paper_type",
    "primary_storage_domain",
    "secondary_storage_domains",
    "domain_candidates",
    "technology_subfield",
    "technology_variant",
    "application_contexts",
    "primary_method_type",
    "secondary_method_types",
    "paper_context_status",
    "matched_signals",
    "conflicting_signals",
    "evidence",
    "decision_reason",
    "taxonomy_version",
    "classified_at",
    "section_coverage_ratio",
    "has_text_loss",
    "abstract_present",
    "year",
    "year_source",
]

FAILED_FIELDS = [
    "paper_id", "full_md_path", "size_bytes", "sha256",
    "stage_failed", "error_type", "error_message",
    "section_coverage_ratio", "has_text_loss",
]

CANDIDATES_FIELDS = [
    "paper_id", "title", "domain_candidates", "matched_signals",
    "conflicting_signals", "decision_reason",
]

UNKNOWN_FIELDS = [
    "paper_id", "title", "abstract_present",
    "non_storage_hits", "decision_reason",
]

NON_STORAGE_FIELDS = [
    "paper_id", "title", "paper_type",
    "non_storage_hits", "storage_evidence_count",
    "decision_reason",
]

CONFLICTS_FIELDS = [
    "paper_id", "title", "anomaly_code", "detail",
    "paper_type", "primary_storage_domain", "technology_subfield",
    "paper_context_status",
]


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
            out[pid] = {
                "year": r.get("year", ""),
                "year_source": r.get("source", ""),
            }
    return out


# ============================================================
# 规则异常扫描 (只识别, 不修复)
# ============================================================

def _domain_of_subfield(kw_yaml: dict, subfield: str) -> str | None:
    """反查 subfield 属于哪个 primary_storage_domain."""
    if not subfield:
        return None
    for dom, dcfg in (kw_yaml.get("storage_domains") or {}).items():
        subs = (dcfg or {}).get("subfields") or {}
        if subfield in subs:
            return dom
    return None


def scan_anomalies(tax_row: dict, pt_row: dict, kw_yaml: dict) -> list:
    """返回该篇论文的 anomaly 列表 [{code, detail}, ...]."""
    out = []
    primary = tax_row.get("primary_storage_domain")
    subfield = tax_row.get("technology_subfield")
    status = tax_row.get("paper_context_status")
    variants = tax_row.get("technology_variant") or []
    secondary = tax_row.get("secondary_storage_domains") or []
    candidates = tax_row.get("domain_candidates") or []
    paper_type = tax_row.get("paper_type")
    p_method = tax_row.get("primary_method_type")
    evidence = tax_row.get("evidence") or []

    # 1. subfield 与 primary 不兼容
    if subfield:
        expected_dom = _domain_of_subfield(kw_yaml, subfield)
        if expected_dom and primary and expected_dom != primary:
            out.append({
                "code": "A1_subfield_incompatible_with_primary",
                "detail": f"subfield={subfield} belongs to {expected_dom}, "
                          f"but primary_storage_domain={primary}",
            })

    # 2. non_storage 但同时有强储能 evidence
    if status == "non_storage":
        strong_storage_ev = [
            e for e in evidence
            if e.get("weight", 0) >= 3
               and e.get("for", "").startswith("storage_domain:")
               and not e["for"].startswith("suppressed:")
        ]
        if strong_storage_ev:
            out.append({
                "code": "A2_non_storage_with_strong_storage_signal",
                "detail": f"{len(strong_storage_ev)} strong storage kw hit(s): "
                          + ", ".join(e["matched"] for e in strong_storage_ev[:5]),
            })

    # 3. paper_type=patent_analysis 但被判为强储能
    if paper_type == "patent_analysis" and status == "confirmed" and primary:
        out.append({
            "code": "A3_patent_analysis_but_storage_confirmed",
            "detail": f"paper_type=patent_analysis, but primary={primary}, status=confirmed",
        })

    # 4. review_article 却被 method_type 判为具体实验工艺
    experimental_method_types = {"synthesis_process", "material_design",
                                  "interface_engineering", "electrode_engineering",
                                  "electrolyte_engineering", "membrane_engineering"}
    if paper_type == "review_article" and p_method in experimental_method_types:
        out.append({
            "code": "A4_review_but_experimental_method_type",
            "detail": f"paper_type=review_article, primary_method_type={p_method}",
        })

    # 5. 命中 3+ storage domain (primary + secondary + candidates 去重)
    all_domains = set()
    if primary:
        all_domains.add(primary)
    all_domains.update(secondary)
    all_domains.update(c["domain"] for c in candidates if isinstance(c, dict))
    if len(all_domains) >= 3:
        out.append({
            "code": "A5_three_or_more_storage_domains",
            "detail": f"domains touched: {sorted(all_domains)}",
        })

    # 6. primary=null 但 status=confirmed (invariant, 应恒 False)
    if primary is None and status == "confirmed":
        out.append({
            "code": "A6_confirmed_without_primary",
            "detail": "primary_storage_domain is null but paper_context_status=confirmed",
        })

    # 7. subfield 存在但 primary=null (invariant)
    if subfield and primary is None:
        out.append({
            "code": "A7_subfield_without_primary",
            "detail": f"subfield={subfield} but primary_storage_domain is null",
        })

    # 8. fuel_cell / hydrogen_production / hydrogen_storage 同现
    ns_keys = {m["key"].split(":", 1)[1] for m in tax_row.get("matched_signals") or []
               if m["key"].startswith("non_storage_signal:")}
    fc = "fuel_cell_only" in ns_keys
    hp = "hydrogen_production_only" in ns_keys
    hs = subfield == "hydrogen_storage" or primary == "chemical_energy_storage"
    if (fc or hp) and hs:
        out.append({
            "code": "A8_fuelcell_or_h2production_vs_h2storage",
            "detail": (f"fuel_cell_only={fc}, hydrogen_production_only={hp}, "
                       f"h2_storage_context={hs}; needs manual review"),
        })

    # 9. supercapacitor 被归入 electromagnetic_storage (invariant, 应恒 False)
    if subfield == "supercapacitor" and primary == "electromagnetic_storage":
        out.append({
            "code": "A9_supercapacitor_under_electromagnetic",
            "detail": "supercapacitor must be under electrochemical_storage",
        })

    # 10. cross_domain_method 与 subfield 同时存在
    if primary == "cross_domain_method" and subfield:
        out.append({
            "code": "A10_cross_domain_method_with_subfield",
            "detail": f"primary=cross_domain_method but subfield={subfield}",
        })

    return out


# ============================================================
# 误判风险打分 (启发式, 仅用于提示人工优先审)
# ============================================================

def risk_score(tax_row: dict, pt_row: dict, anomalies: list) -> tuple:
    """返回 (score, reasons) — 得分越高越可能需要人工审."""
    score = 0
    reasons = []
    if tax_row.get("paper_context_status") == "candidate":
        score += 3
        reasons.append("status=candidate")
    if tax_row.get("paper_context_status") == "unknown" and \
       tax_row.get("abstract_present") is False:
        score += 2
        reasons.append("unknown+no_abstract")
    if tax_row.get("paper_context_status") == "unknown":
        score += 2
        reasons.append("status=unknown")
    conflicts = tax_row.get("conflicting_signals") or []
    if conflicts:
        score += len(conflicts) * 2
        reasons.append(f"conflicts={len(conflicts)}")
    if anomalies:
        score += len(anomalies) * 3
        reasons.append(f"anomalies={[a['code'] for a in anomalies]}")
    # secondary domain 存在 (跨方向)
    if tax_row.get("secondary_storage_domains"):
        score += 1
        reasons.append("has_secondary_domain")
    # non_storage 但有储能 evidence
    for a in anomalies:
        if a["code"] == "A2_non_storage_with_strong_storage_signal":
            score += 2
    return score, reasons


# ============================================================
# 主流程
# ============================================================

def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    os.makedirs(config.CORPUS_PP_V1_DIR, exist_ok=True)
    os.makedirs(config.CORPUS_PP_V1_SECTIONS_DIR, exist_ok=True)

    year_map = load_year_map()
    kw_yaml = tr.load_keywords()

    started_iso = datetime.now().isoformat(timespec="seconds")
    t0 = time.time()

    if not os.path.isdir(DOWNLOADED):
        print(f"ERROR: downloaded_files not found: {DOWNLOADED}")
        return 2

    all_folders = sorted(os.listdir(DOWNLOADED))
    total_folders = len(all_folders)
    paper_ids = [f for f in all_folders
                 if os.path.isfile(os.path.join(DOWNLOADED, f, "full.md"))]
    n_input = len(paper_ids)
    print(f"scan folders={total_folders}, with_full_md={n_input}")

    manifest_entries = []
    pt_rows = []
    tax_rows = []
    failed_rows = []
    tax_anomalies = []              # [{paper_id, title, code, detail, ...}]
    per_paper_anomalies = {}        # paper_id → [anomalies]

    n_ok = 0
    n_fail = 0
    n_abs_present = 0
    coverage_lt1 = []
    text_loss = []
    parse_errs = []

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
            "processing_status": "ok",
            "error_message": "",
        }

        # Stage 1: 章节解析
        pr = None
        try:
            pr = sp.parse_file(pid, md_path)
            entry["parsed_at_iso"] = pr.parse_time_iso
        except Exception as e:
            n_fail += 1
            entry["processing_status"] = "parse_failed"
            entry["error_message"] = f"{type(e).__name__}: {e}"
            manifest_entries.append(entry)
            failed_rows.append({
                "paper_id": pid,
                "full_md_path": md_path,
                "size_bytes": entry["size_bytes"],
                "sha256": entry["sha256"],
                "stage_failed": "section_parser",
                "error_type": type(e).__name__,
                "error_message": (str(e) + "\n" + traceback.format_exc())[:2000],
                "section_coverage_ratio": 0.0,
                "has_text_loss": True,
            })
            parse_errs.append(pid)
            print(f"  [{i:>3}/{n_input}] FAIL parser  {pid}")
            continue

        # 写 sections JSON
        try:
            sp.write_json(pr, os.path.join(config.CORPUS_PP_V1_SECTIONS_DIR, f"{pid}.json"))
        except Exception as e:
            n_fail += 1
            entry["processing_status"] = "section_json_write_failed"
            entry["error_message"] = f"{type(e).__name__}: {e}"
            manifest_entries.append(entry)
            failed_rows.append({
                "paper_id": pid,
                "full_md_path": md_path,
                "size_bytes": entry["size_bytes"],
                "sha256": entry["sha256"],
                "stage_failed": "write_sections_json",
                "error_type": type(e).__name__,
                "error_message": str(e)[:2000],
                "section_coverage_ratio": round(pr.section_coverage_ratio, 6),
                "has_text_loss": pr.has_text_loss,
            })
            print(f"  [{i:>3}/{n_input}] FAIL wjson   {pid}")
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

        # has_text_loss=True 视为失败 (spec 四硬性要求)
        if loss:
            n_fail += 1
            entry["processing_status"] = "text_loss"
            entry["error_message"] = (
                f"section_coverage_ratio={coverage}, has_text_loss=True")
            manifest_entries.append(entry)
            failed_rows.append({
                "paper_id": pid,
                "full_md_path": md_path,
                "size_bytes": entry["size_bytes"],
                "sha256": entry["sha256"],
                "stage_failed": "section_parser_text_loss",
                "error_type": "TextLoss",
                "error_message": entry["error_message"],
                "section_coverage_ratio": coverage,
                "has_text_loss": True,
            })
            print(f"  [{i:>3}/{n_input}] FAIL textloss  {pid}")
            continue

        # Stage 2: paper_type
        try:
            pt_r = ptr.classify_paper_type(pr)
        except Exception as e:
            n_fail += 1
            entry["processing_status"] = "paper_type_failed"
            entry["error_message"] = f"{type(e).__name__}: {e}"
            manifest_entries.append(entry)
            failed_rows.append({
                "paper_id": pid,
                "full_md_path": md_path,
                "size_bytes": entry["size_bytes"],
                "sha256": entry["sha256"],
                "stage_failed": "paper_type_rules",
                "error_type": type(e).__name__,
                "error_message": (str(e) + "\n" + traceback.format_exc())[:2000],
                "section_coverage_ratio": coverage,
                "has_text_loss": loss,
            })
            print(f"  [{i:>3}/{n_input}] FAIL ptype   {pid}")
            continue

        # Stage 3: taxonomy
        try:
            tax_r = tr.classify_taxonomy(pr, paper_type_result=pt_r)
        except Exception as e:
            n_fail += 1
            entry["processing_status"] = "taxonomy_failed"
            entry["error_message"] = f"{type(e).__name__}: {e}"
            manifest_entries.append(entry)
            failed_rows.append({
                "paper_id": pid,
                "full_md_path": md_path,
                "size_bytes": entry["size_bytes"],
                "sha256": entry["sha256"],
                "stage_failed": "taxonomy_rules",
                "error_type": type(e).__name__,
                "error_message": (str(e) + "\n" + traceback.format_exc())[:2000],
                "section_coverage_ratio": coverage,
                "has_text_loss": loss,
            })
            print(f"  [{i:>3}/{n_input}] FAIL taxonomy {pid}")
            continue

        # 组装 paper_types 行
        pt_row = {
            "paper_id": pid,
            "paper_type": pt_r["paper_type"],
            "rule_confidence": pt_r["rule_confidence"],
            "matched_signals": pt_r["matched_signals"],
            "conflicting_signals": pt_r["conflicting_signals"],
            "type_evidence": pt_r["type_evidence"],
            "decision_reason": pt_r["decision_reason"],
            "parser_version": pt_r["parser_version"],
            "classified_at": pt_r["classified_at"],
            "section_coverage_ratio": coverage,
            "has_text_loss": loss,
            "abstract_present": has_abstract,
        }
        pt_rows.append(pt_row)

        # 组装 taxonomy 行
        y = year_map.get(pid) or {}
        tax_row = dict(tax_r)
        tax_row["section_coverage_ratio"] = coverage
        tax_row["has_text_loss"] = loss
        tax_row["abstract_present"] = has_abstract
        tax_row["year"] = y.get("year", "")
        tax_row["year_source"] = y.get("year_source", "")
        tax_rows.append(tax_row)

        # anomaly 扫描
        an = scan_anomalies(tax_row, pt_row, kw_yaml)
        per_paper_anomalies[pid] = an
        for a in an:
            tax_anomalies.append({
                "paper_id": pid,
                "title": pr.document_title or "",
                "anomaly_code": a["code"],
                "detail": a["detail"],
                "paper_type": tax_row.get("paper_type"),
                "primary_storage_domain": tax_row.get("primary_storage_domain"),
                "technology_subfield": tax_row.get("technology_subfield"),
                "paper_context_status": tax_row.get("paper_context_status"),
            })

        n_ok += 1
        manifest_entries.append(entry)
        if i % 50 == 0 or i == n_input:
            print(f"  [{i:>3}/{n_input}] progress ok={n_ok} fail={n_fail}")

    dur = time.time() - t0

    # ---- 派生 CSV: candidates / unknown / non_storage / conflicts ----
    cand_rows = []
    unknown_rows = []
    non_storage_rows = []
    conflict_rows = []

    for r in tax_rows:
        pid = r["paper_id"]
        title = ""
        # heading 取标题: 从 sections JSON 无需再读; 用 evidence 或 fallback
        # 保守: 从 kw_yaml scan 中已丢, 用 evidence 里 title=... 之类还原 title 太麻烦, 直接从 sections/json 读
        # 简化: title 不在 tax_r 里, 我们回读一次 sections/<pid>.json
        json_path = os.path.join(config.CORPUS_PP_V1_SECTIONS_DIR, f"{pid}.json")
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                d = json.load(f)
            title = d.get("document_title") or ""
        except Exception:
            pass

        status = r.get("paper_context_status")
        if status == "candidate":
            cand_rows.append({
                "paper_id": pid,
                "title": title,
                "domain_candidates": r.get("domain_candidates") or [],
                "matched_signals": r.get("matched_signals") or [],
                "conflicting_signals": r.get("conflicting_signals") or [],
                "decision_reason": r.get("decision_reason", ""),
            })
        if status == "unknown":
            ns_hits = [m["key"].split(":", 1)[1] for m in r.get("matched_signals") or []
                       if m["key"].startswith("non_storage_signal:")]
            unknown_rows.append({
                "paper_id": pid,
                "title": title,
                "abstract_present": r.get("abstract_present", False),
                "non_storage_hits": ns_hits,
                "decision_reason": r.get("decision_reason", ""),
            })
        if status == "non_storage":
            ns_hits = [m["key"].split(":", 1)[1] for m in r.get("matched_signals") or []
                       if m["key"].startswith("non_storage_signal:")]
            storage_ev = [e for e in (r.get("evidence") or [])
                          if e.get("for", "").startswith("storage_domain:")
                          and not e.get("for", "").startswith("suppressed:")]
            non_storage_rows.append({
                "paper_id": pid,
                "title": title,
                "paper_type": r.get("paper_type"),
                "non_storage_hits": ns_hits,
                "storage_evidence_count": len(storage_ev),
                "decision_reason": r.get("decision_reason", ""),
            })
        # conflicts (通用): 只要 conflicting_signals 非空 就进
        cf = r.get("conflicting_signals") or []
        if cf:
            for c in cf:
                conflict_rows.append({
                    "paper_id": pid,
                    "title": title,
                    "anomaly_code": f"conflict_signal:{c.get('key','')}",
                    "detail": c.get("detail", ""),
                    "paper_type": r.get("paper_type"),
                    "primary_storage_domain": r.get("primary_storage_domain"),
                    "technology_subfield": r.get("technology_subfield"),
                    "paper_context_status": status,
                })
        # 追加 anomaly-scan 的条目
        for an in per_paper_anomalies.get(pid, []):
            conflict_rows.append({
                "paper_id": pid,
                "title": title,
                "anomaly_code": an["code"],
                "detail": an["detail"],
                "paper_type": r.get("paper_type"),
                "primary_storage_domain": r.get("primary_storage_domain"),
                "technology_subfield": r.get("technology_subfield"),
                "paper_context_status": status,
            })

    # ---- 写 CSVs ----
    def _write_csv(path, fields, rows):
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for row in rows:
                w.writerow({k: _j(row.get(k)) for k in fields})

    _write_csv(config.CORPUS_PP_V1_PAPER_TYPES_CSV, PAPER_TYPES_FIELDS, pt_rows)
    _write_csv(config.CORPUS_PP_V1_PAPER_TAXONOMY_CSV, TAXONOMY_FIELDS, tax_rows)
    _write_csv(config.CORPUS_PP_V1_FAILED_CSV, FAILED_FIELDS, failed_rows)
    _write_csv(config.CORPUS_PP_V1_CANDIDATES_CSV, CANDIDATES_FIELDS, cand_rows)
    _write_csv(config.CORPUS_PP_V1_UNKNOWN_CSV, UNKNOWN_FIELDS, unknown_rows)
    _write_csv(config.CORPUS_PP_V1_NON_STORAGE_CSV, NON_STORAGE_FIELDS, non_storage_rows)
    _write_csv(config.CORPUS_PP_V1_CONFLICTS_CSV, CONFLICTS_FIELDS, conflict_rows)

    # ---- 写 manifest ----
    manifest = {
        "manifest_created_at": datetime.now().isoformat(timespec="seconds"),
        "run_started_at": started_iso,
        "duration_sec": round(dur, 2),
        "input_root": config.relative_path(DOWNLOADED),
        "note": {
            "raw_corpus_size": 337,
            "legacy_method_outputs_size": 334,
            "difference_semantics": (
                "337 = V2 raw corpus (folders with full.md). "
                "334 = legacy V1 method_outputs (旧抽取成功数). "
                "两者不再混用; V2 只吃 337 篇 full.md."
            ),
        },
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
    with open(config.CORPUS_PP_V1_MANIFEST_JSON, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    # ============================================================
    # 分布与统计
    # ============================================================

    paper_type_counter = Counter(r["paper_type"] for r in pt_rows)
    paper_type_conf_matrix = defaultdict(Counter)
    for r in pt_rows:
        paper_type_conf_matrix[r["paper_type"]][r["rule_confidence"]] += 1

    primary_domain_counter = Counter(r["primary_storage_domain"] for r in tax_rows)
    subfield_counter = Counter(r["technology_subfield"] for r in tax_rows)
    status_counter = Counter(r["paper_context_status"] for r in tax_rows)
    secondary_count_counter = Counter(len(r["secondary_storage_domains"] or []) for r in tax_rows)
    cand_size_counter = Counter(len(r["domain_candidates"] or []) for r in tax_rows)
    variants_flat = Counter()
    for r in tax_rows:
        for v in r.get("technology_variant") or []:
            variants_flat[v] += 1
    apps_flat = Counter()
    for r in tax_rows:
        for a in r.get("application_contexts") or []:
            apps_flat[a] += 1
    p_method_counter = Counter(r["primary_method_type"] for r in tax_rows)

    # coverage 分布
    cov_bins = Counter()
    for r in tax_rows:
        c = r.get("section_coverage_ratio", 1.0)
        if c >= 1.0:
            cov_bins["1.0"] += 1
        elif c >= 0.99:
            cov_bins["[0.99, 1.0)"] += 1
        elif c >= 0.95:
            cov_bins["[0.95, 0.99)"] += 1
        elif c >= 0.90:
            cov_bins["[0.90, 0.95)"] += 1
        else:
            cov_bins["<0.90"] += 1

    # 无摘要
    no_abstract = [r["paper_id"] for r in tax_rows if not r.get("abstract_present")]
    n_no_abstract = len(no_abstract)

    # 无标题
    no_title = []
    for r in tax_rows:
        pid = r["paper_id"]
        json_path = os.path.join(config.CORPUS_PP_V1_SECTIONS_DIR, f"{pid}.json")
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                d = json.load(f)
            if not d.get("document_title") or d["document_title"] == pid:
                no_title.append(pid)
        except Exception:
            pass

    # OCR 异常 (启发式): 标题里非 CJK 且 abstract 缺失
    ocr_suspicious = []
    for r in tax_rows:
        pid = r["paper_id"]
        json_path = os.path.join(config.CORPUS_PP_V1_SECTIONS_DIR, f"{pid}.json")
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                d = json.load(f)
            t = d.get("document_title") or ""
            if not r.get("abstract_present") and t:
                if any(c in t for c in ('!', '"', '#', '$', '%', '&', "'", '(', ')', '*', '+')):
                    ocr_suspicious.append(pid)
        except Exception:
            pass

    # ============================================================
    # 代表性样本
    # ============================================================

    rng = random.Random(SAMPLE_SEED)
    samples_by_domain = defaultdict(list)
    for r in tax_rows:
        d = r.get("primary_storage_domain") or "(空)"
        samples_by_domain[d].append(r["paper_id"])
    domain_samples = {}
    for d, ids in samples_by_domain.items():
        picks = list(ids)
        rng.shuffle(picks)
        domain_samples[d] = picks[:SAMPLES_PER_DOMAIN]

    # 多领域论文: secondary 非空 OR candidates 非空
    multi_domain_ids = [
        r["paper_id"] for r in tax_rows
        if (r.get("secondary_storage_domains") or []) or (r.get("domain_candidates") or [])
    ]

    # 最可能误判 top-N
    risk_scored = []
    for r in tax_rows:
        pid = r["paper_id"]
        # 找 pt_row
        pt = next((p for p in pt_rows if p["paper_id"] == pid), None)
        an = per_paper_anomalies.get(pid, [])
        s, reasons = risk_score(r, pt, an)
        if s > 0:
            risk_scored.append((s, pid, reasons))
    risk_scored.sort(key=lambda x: -x[0])
    top_risk = risk_scored[:TOP_RISK_N]

    # ============================================================
    # 报告 (json + md)
    # ============================================================

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
            "parse_errors_count": len(parse_errs),
            "no_document_title_count": len(no_title),
            "ocr_suspicious_count": len(ocr_suspicious),
        },
        "distributions": {
            "paper_type": dict(paper_type_counter),
            "paper_type_by_confidence": {
                k: dict(v) for k, v in paper_type_conf_matrix.items()
            },
            "primary_storage_domain": {
                (k if k is not None else "(null)"): v
                for k, v in primary_domain_counter.items()
            },
            "technology_subfield": {
                (k if k is not None else "(null)"): v
                for k, v in subfield_counter.items()
            },
            "paper_context_status": dict(status_counter),
            "secondary_domains_size": dict(secondary_count_counter),
            "domain_candidates_size": dict(cand_size_counter),
            "technology_variant": dict(variants_flat),
            "application_contexts": dict(apps_flat),
            "primary_method_type": {
                (k if k is not None else "(null)"): v
                for k, v in p_method_counter.items()
            },
            "section_coverage_bins": dict(cov_bins),
        },
        "rule_anomalies_by_code": dict(Counter(a["anomaly_code"] for a in tax_anomalies)),
        "samples": {
            "by_primary_domain": {k: v for k, v in domain_samples.items()},
            "unknown_ids": [r["paper_id"] for r in unknown_rows],
            "candidate_ids": [r["paper_id"] for r in cand_rows],
            "non_storage_ids": [r["paper_id"] for r in non_storage_rows],
            "multi_domain_ids": multi_domain_ids,
            "top_risk": [
                {"paper_id": pid, "risk_score": s, "reasons": r}
                for s, pid, r in top_risk
            ],
        },
    }
    with open(config.CORPUS_PP_V1_REPORT_JSON, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # ---- Markdown 报告 ----
    ml = []
    ml.append("# 全语料预处理报告 corpus_preprocess_v1\n")
    ml.append(
        f"> 运行开始: {started_iso}\n"
        f"> 耗时: {round(dur,1)} 秒\n"
        f"> 引擎: section_parser v{sp.SECTION_PARSER_VERSION} / "
        f"paper_type v{ptr.PAPER_TYPE_RULES_VERSION} / "
        f"taxonomy v{tr.TAXONOMY_VERSION} (kw yaml v{kw_yaml.get('version','unknown')})\n"
        f"> 输入: `{config.relative_path(DOWNLOADED)}` (337 篇 full.md)\n"
        f"> 无 LLM. 无 legacy 读取. 无数据库写入.\n"
        f"\n"
    )

    ml.append("## 一、语料清点\n")
    ml.append(
        f"- 输入论文数: **{n_input}**\n"
        f"- 成功处理: **{n_ok}**\n"
        f"- 失败: **{n_fail}**\n"
        f"- 摘要识别: **{n_abs_present}** / 缺失: **{n_input - n_abs_present - n_fail}**\n"
        f"- 无 document_title: **{len(no_title)}**\n"
        f"- OCR 可疑(标题含 !\"#等符号 + 摘要缺失): **{len(ocr_suspicious)}**\n"
    )

    ml.append("\n## 二、章节覆盖率\n")
    ml.append("| 区间 | 篇数 |\n|---|---:|\n")
    for k in ("1.0", "[0.99, 1.0)", "[0.95, 0.99)", "[0.90, 0.95)", "<0.90"):
        ml.append(f"| {k} | {cov_bins.get(k, 0)} |\n")
    ml.append(f"\n- coverage < 1.0 篇数: **{len(coverage_lt1)}**\n")
    ml.append(f"- has_text_loss=True 篇数: **{len(text_loss)}**\n")
    if coverage_lt1:
        ml.append(f"- coverage < 1.0 明细:\n")
        for pid, c in coverage_lt1[:30]:
            ml.append(f"  - `{pid}` → {c}\n")
    if text_loss:
        ml.append(f"- has_text_loss=True 列表:\n")
        for pid in text_loss:
            ml.append(f"  - `{pid}`\n")

    ml.append("\n## 三、paper_type 分布\n")
    ml.append("| paper_type | 数量 | high | medium | low |\n|---|---:|---:|---:|---:|\n")
    for pt in ("research_article", "review_article", "patent_analysis", "unclear"):
        cnt = paper_type_counter.get(pt, 0)
        conf = paper_type_conf_matrix.get(pt, {})
        ml.append(f"| {pt} | {cnt} | {conf.get('high', 0)} | {conf.get('medium', 0)} | {conf.get('low', 0)} |\n")

    ml.append("\n## 四、taxonomy 分布\n")
    ml.append("### 4.1 primary_storage_domain\n")
    ml.append("| 值 | 篇数 |\n|---|---:|\n")
    for k, v in sorted(report["distributions"]["primary_storage_domain"].items(),
                       key=lambda kv: -kv[1]):
        ml.append(f"| `{k}` | {v} |\n")

    ml.append("\n### 4.2 technology_subfield (top 20)\n")
    ml.append("| 值 | 篇数 |\n|---|---:|\n")
    for k, v in sorted(report["distributions"]["technology_subfield"].items(),
                       key=lambda kv: -kv[1])[:20]:
        ml.append(f"| `{k}` | {v} |\n")

    ml.append("\n### 4.3 paper_context_status\n")
    ml.append("| 状态 | 篇数 |\n|---|---:|\n")
    for k in ("confirmed", "candidate", "unknown", "non_storage"):
        ml.append(f"| {k} | {status_counter.get(k, 0)} |\n")

    ml.append("\n### 4.4 secondary_storage_domains 大小分布\n")
    ml.append("| 大小 | 篇数 |\n|---|---:|\n")
    for k in sorted(secondary_count_counter.keys()):
        ml.append(f"| {k} | {secondary_count_counter[k]} |\n")

    ml.append("\n### 4.5 domain_candidates 大小分布\n")
    ml.append("| 大小 | 篇数 |\n|---|---:|\n")
    for k in sorted(cand_size_counter.keys()):
        ml.append(f"| {k} | {cand_size_counter[k]} |\n")

    ml.append("\n### 4.6 technology_variant (命中次数)\n")
    if variants_flat:
        ml.append("| variant | 命中 |\n|---|---:|\n")
        for k, v in sorted(variants_flat.items(), key=lambda kv: -kv[1]):
            ml.append(f"| `{k}` | {v} |\n")
    else:
        ml.append("*(无 variant 命中)*\n")

    ml.append("\n### 4.7 application_contexts (命中次数)\n")
    ml.append("| context | 命中 |\n|---|---:|\n")
    for k, v in sorted(apps_flat.items(), key=lambda kv: -kv[1]):
        ml.append(f"| `{k}` | {v} |\n")

    ml.append("\n### 4.8 primary_method_type (Stage A 提示, 非最终标签)\n")
    ml.append("| method | 数量 |\n|---|---:|\n")
    for k, v in sorted(report["distributions"]["primary_method_type"].items(),
                       key=lambda kv: -kv[1]):
        ml.append(f"| `{k}` | {v} |\n")
    ml.append("\n> **注意**: 论文级 primary/secondary method_type 仅作为 Stage A 提示, "
              "不作为最终方法节点标签, 也不进入方法演化统计。最终 method_type 需要在方法抽取后重新判断。\n")

    ml.append("\n## 五、规则异常扫描 (只识别, 不修改规则)\n")
    if not tax_anomalies:
        ml.append("*(未发现异常)*\n")
    else:
        ml.append("| 异常代码 | 数量 |\n|---|---:|\n")
        for k, v in sorted(report["rule_anomalies_by_code"].items(),
                           key=lambda kv: -kv[1]):
            ml.append(f"| `{k}` | {v} |\n")
        ml.append(f"\n**共 {len(tax_anomalies)} 条异常记录**, 详见 `taxonomy_conflicts.csv`.\n")
        # 分组前 10 例
        for code, items in _group_by(tax_anomalies, "anomaly_code").items():
            ml.append(f"\n#### `{code}` (共 {len(items)})\n")
            for it in items[:8]:
                ml.append(f"- `{it['paper_id']}` — {it['detail']}\n")

    ml.append("\n## 六、代表性样本\n")
    ml.append("### 6.1 每 primary_storage_domain 抽样 (至多 5)\n")
    for dom in sorted(domain_samples.keys()):
        picks = domain_samples[dom]
        ml.append(f"\n**{dom}** ({primary_domain_counter.get(None if dom == '(空)' else dom, 0)} 篇, 抽样 {len(picks)}):\n")
        for pid in picks:
            r = next(x for x in tax_rows if x["paper_id"] == pid)
            ml.append(
                f"- `{pid}` → subfield=`{r.get('technology_subfield') or '(空)'}`, "
                f"status={r.get('paper_context_status')}, "
                f"variants={r.get('technology_variant') or []}, "
                f"paper_type={r.get('paper_type')}\n"
            )

    ml.append(f"\n### 6.2 unknown (共 {len(unknown_rows)})\n")
    for u in unknown_rows[:50]:
        ml.append(f"- `{u['paper_id']}` — abstract={u['abstract_present']}, "
                  f"non_storage_hits={u['non_storage_hits']}\n")
    if len(unknown_rows) > 50:
        ml.append(f"- ... 余 {len(unknown_rows) - 50} 条见 `taxonomy_unknown.csv`\n")

    ml.append(f"\n### 6.3 candidate (共 {len(cand_rows)})\n")
    for c in cand_rows[:50]:
        doms = [d.get("domain") for d in c["domain_candidates"] if isinstance(d, dict)]
        ml.append(f"- `{c['paper_id']}` — candidates={doms}\n")
    if len(cand_rows) > 50:
        ml.append(f"- ... 余 {len(cand_rows) - 50} 条见 `taxonomy_candidates.csv`\n")

    ml.append(f"\n### 6.4 non_storage (共 {len(non_storage_rows)})\n")
    for n in non_storage_rows[:50]:
        ml.append(f"- `{n['paper_id']}` — non_storage_hits={n['non_storage_hits']}, "
                  f"storage_evidence_count={n['storage_evidence_count']}\n")
    if len(non_storage_rows) > 50:
        ml.append(f"- ... 余 {len(non_storage_rows) - 50} 条见 `non_storage_papers.csv`\n")

    ml.append(f"\n### 6.5 多领域论文 (secondary 或 candidates 非空, 共 {len(multi_domain_ids)})\n")
    for pid in multi_domain_ids[:50]:
        r = next(x for x in tax_rows if x["paper_id"] == pid)
        sec = r.get("secondary_storage_domains") or []
        cands = [c.get("domain") for c in (r.get("domain_candidates") or []) if isinstance(c, dict)]
        ml.append(f"- `{pid}` — primary=`{r.get('primary_storage_domain')}`, "
                  f"secondary={sec}, candidates={cands}\n")
    if len(multi_domain_ids) > 50:
        ml.append(f"- ... 余 {len(multi_domain_ids) - 50} 条\n")

    ml.append(f"\n### 6.6 最可能误判 top {TOP_RISK_N}\n")
    ml.append("| # | paper_id | risk_score | reasons |\n|--:|---|---:|---|\n")
    for i, (s, pid, reasons) in enumerate(top_risk, 1):
        ml.append(f"| {i} | `{pid}` | {s} | {'; '.join(reasons)} |\n")

    ml.append("\n## 七、失败清单\n")
    if failed_rows:
        for r in failed_rows:
            ml.append(f"- `{r['paper_id']}` — stage={r['stage_failed']}, "
                      f"err={r['error_type']}: {r['error_message'][:200]}\n")
    else:
        ml.append("*(0 失败)*\n")

    with open(config.CORPUS_PP_V1_REPORT_MD, "w", encoding="utf-8") as f:
        f.writelines(ml)

    # ---- 终端简报 ----
    print()
    print("=" * 70)
    print(f"processed_ok={n_ok}/{n_input}  failed={n_fail}  duration={round(dur,1)}s")
    print(f"paper_type: {dict(paper_type_counter)}")
    print(f"primary_domain: {dict(primary_domain_counter)}")
    print(f"status: {dict(status_counter)}")
    print(f"anomalies: {sum(1 for _ in tax_anomalies)} entries; "
          f"conflicts CSV: {len(conflict_rows)} rows")
    print(f"unknown={len(unknown_rows)} candidate={len(cand_rows)} "
          f"non_storage={len(non_storage_rows)}")
    print(f"output dir: {config.relative_path(config.CORPUS_PP_V1_DIR)}")
    return 0


def _group_by(items, key):
    d = defaultdict(list)
    for it in items:
        d[it[key]].append(it)
    return d


if __name__ == "__main__":
    sys.exit(main())
