"""run_stage_a_aggregate.py — Stage A 全量汇总 (spec 八 + 九).

产出全部 16 个 CSV / JSON / MD 到 STAGE_A_FULL_V1_DIR/aggregation/, 加上
external_literature_candidates.csv.

只读; 不改任何 per_paper 结果.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import Counter
from datetime import datetime

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_GRAPH_RAG_DIR = os.path.dirname(THIS_DIR)
if SRC_GRAPH_RAG_DIR not in sys.path:
    sys.path.insert(0, SRC_GRAPH_RAG_DIR)

from method_evolution_v2 import config                                # noqa: E402
from method_evolution_v2.stage_a import full_runner as fr             # noqa: E402


AGG_DIR = os.path.join(config.STAGE_A_FULL_V1_DIR, "aggregation")


def load_context_maps():
    ptypes, ctitles, tax = {}, {}, {}
    with open(config.CORPUS_PP_V1_1_PAPER_TYPES_CSV, "r",
                encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            ptypes[r["paper_id"]] = r.get("paper_type", "")
    ct_p = os.path.join(config.CORPUS_PP_V1_1_DIR, "canonical_titles.csv")
    if os.path.isfile(ct_p):
        with open(ct_p, "r", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                ctitles[r["paper_id"]] = r.get("canonical_title", "")
    if os.path.isfile(config.CORPUS_PP_V1_1_PAPER_TAXONOMY_CSV):
        with open(config.CORPUS_PP_V1_1_PAPER_TAXONOMY_CSV,
                    "r", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                tax[r["paper_id"]] = r
    return ptypes, ctitles, tax


def load_batches_csv():
    """Return {paper_id: batch_num}."""
    m = {}
    with open(config.STAGE_A_FULL_V1_BATCHES_CSV, "r",
                encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            m[r["paper_id"]] = int(r["batch_num"])
    return m


def _get_evidence_text(m, sid_map):
    ids = m.get("evidence_sentence_ids") or []
    parts = []
    for sid in ids:
        t = sid_map.get(sid, "")
        if t:
            parts.append(t)
    return " ".join(parts)[:1000]


def collect_all_methods_and_summary():
    """Walk every per_paper dir; return list of method dicts + per-paper summary."""
    ptypes, ctitles, tax = load_context_maps()
    batches = load_batches_csv()
    all_paper_ids = sorted(batches.keys())

    all_methods = []
    per_paper = []
    for pid in all_paper_ids:
        d = fr.per_paper_dir(pid)
        summary = {
            "paper_id": pid,
            "canonical_title": ctitles.get(pid, ""),
            "paper_type": ptypes.get(pid, ""),
            "batch_num": batches[pid],
            "primary_storage_domain": tax.get(pid, {}).get(
                "primary_storage_domain", ""),
            "paper_context_status": tax.get(pid, {}).get(
                "paper_context_status", ""),
            "processed": os.path.isdir(d),
            "n_accepted": 0, "n_candidate": 0, "n_rejected": 0,
            "n_own_accepted": 0, "n_ref_accepted": 0,
            "recovery_used": False,
        }
        if not summary["processed"]:
            per_paper.append(summary)
            continue

        # sentence index
        try:
            with open(os.path.join(d, "sentence_index.json"),
                        "r", encoding="utf-8") as f:
                sidx = json.load(f)
            sid_map = {s["sentence_id"]: s.get("sentence_text", "")
                        for s in sidx.get("sentences", [])}
        except (FileNotFoundError, json.JSONDecodeError):
            sid_map = {}

        try:
            with open(os.path.join(d, "input_manifest.json"),
                        "r", encoding="utf-8") as f:
                im = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            im = {}
        summary["recovery_used"] = bool(im.get("recovery_used"))

        for bucket, status_key in (
                ("methods_accepted.json", "n_accepted"),
                ("methods_candidate.json", "n_candidate"),
                ("methods_rejected.json", "n_rejected")):
            p = os.path.join(d, bucket)
            if not os.path.isfile(p):
                continue
            try:
                with open(p, "r", encoding="utf-8") as f:
                    rows = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                continue
            summary[status_key] = len(rows)
            for m in rows:
                m["paper_id"] = pid
                m["canonical_title"] = summary["canonical_title"]
                m["paper_type"] = summary["paper_type"]
                m["batch_num"] = summary["batch_num"]
                m["primary_storage_domain"] = summary["primary_storage_domain"]
                m["paper_context_status"] = summary["paper_context_status"]
                m["evidence_text_resolved"] = _get_evidence_text(m, sid_map)
                if m.get("validation_status") == "accepted":
                    if m.get("kind") == "own": summary["n_own_accepted"] += 1
                    elif m.get("kind") == "referenced":
                        summary["n_ref_accepted"] += 1
                all_methods.append(m)
        per_paper.append(summary)
    return all_methods, per_paper


CSV_FIELDS_FULL = [
    "paper_id", "canonical_title", "paper_type", "batch_num",
    "primary_storage_domain", "paper_context_status",
    "kind", "method_id", "name", "raw_method_name",
    "normalized_method_name", "source_organization",
    "proposed_method_type", "method_role",
    "validation_status", "validation_reason",
    "support_scope", "source_provenance",
    "cited_author", "cited_year", "cited_reference_number",
    "external_stub_id",
    "confidence_llm", "recovery_source",
    "evidence_sentence_ids", "evidence_text_resolved",
]


def _row(m, extra_keys=None):
    r = {}
    for k in CSV_FIELDS_FULL:
        v = m.get(k, "")
        if isinstance(v, list): v = json.dumps(v, ensure_ascii=False)
        r[k] = v
    if extra_keys:
        for k in extra_keys:
            v = m.get(k, "")
            if isinstance(v, list): v = json.dumps(v, ensure_ascii=False)
            r[k] = v
    return r


def _write_csv(path, fields, rows):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows: w.writerow(r)


def write_methods_csvs(all_methods):
    def rows(filter_fn):
        return [_row(m) for m in all_methods if filter_fn(m)]

    _write_csv(os.path.join(AGG_DIR, "methods_all.csv"),
                CSV_FIELDS_FULL, rows(lambda m: True))
    _write_csv(os.path.join(AGG_DIR, "methods_accepted.csv"),
                CSV_FIELDS_FULL,
                rows(lambda m: m.get("validation_status") == "accepted"))
    _write_csv(os.path.join(AGG_DIR, "methods_candidate.csv"),
                CSV_FIELDS_FULL,
                rows(lambda m: m.get("validation_status") == "candidate"))
    _write_csv(os.path.join(AGG_DIR, "methods_rejected.csv"),
                CSV_FIELDS_FULL,
                rows(lambda m: m.get("validation_status") == "rejected"))

    # storage_scope 分桶: main / uncertain / non_storage 基于 paper_context_status
    def _scope_of(m):
        s = (m.get("paper_context_status") or "").strip().lower()
        if s == "confirmed": return "main_storage"
        if s == "non_storage": return "non_storage"
        return "uncertain"
    _write_csv(os.path.join(AGG_DIR, "methods_storage_main.csv"),
                CSV_FIELDS_FULL,
                rows(lambda m: _scope_of(m) == "main_storage"))
    _write_csv(os.path.join(AGG_DIR, "methods_uncertain_scope.csv"),
                CSV_FIELDS_FULL,
                rows(lambda m: _scope_of(m) == "uncertain"))
    _write_csv(os.path.join(AGG_DIR, "methods_non_storage.csv"),
                CSV_FIELDS_FULL,
                rows(lambda m: _scope_of(m) == "non_storage"))

    # external stubs (referenced with external_stub_id)
    stubs = {}
    for m in all_methods:
        if m.get("kind") != "referenced": continue
        sid = m.get("external_stub_id", "")
        if not sid: continue
        stubs.setdefault(sid, []).append(m)
    stub_rows = []
    for sid, ms in stubs.items():
        first = ms[0]
        stub_rows.append({
            "external_stub_id": sid,
            "normalized_method_name": first.get("normalized_method_name",
                                                    first.get("name", "")),
            "raw_method_name": first.get("raw_method_name",
                                             first.get("name", "")),
            "cited_author": first.get("cited_author", ""),
            "cited_year": first.get("cited_year", ""),
            "cited_reference_number": first.get("cited_reference_number", ""),
            "source_organization": first.get("source_organization", ""),
            "occurrence_count": len(ms),
            "paper_ids": ";".join(sorted({m["paper_id"] for m in ms})),
        })
    _write_csv(os.path.join(AGG_DIR, "external_method_stubs.csv"),
                ["external_stub_id", "normalized_method_name",
                  "raw_method_name", "cited_author", "cited_year",
                  "cited_reference_number", "source_organization",
                  "occurrence_count", "paper_ids"], stub_rows)

    # research_methods / technology_methods / modeling_methods (all buckets)
    _write_csv(os.path.join(AGG_DIR, "research_methods.csv"),
                CSV_FIELDS_FULL,
                rows(lambda m: m.get("method_role") == "research_method"))
    _write_csv(os.path.join(AGG_DIR, "technology_methods.csv"),
                CSV_FIELDS_FULL,
                rows(lambda m: m.get("method_role") == "technology_solution"))
    _write_csv(os.path.join(AGG_DIR, "modeling_methods.csv"),
                CSV_FIELDS_FULL,
                rows(lambda m: m.get("method_role") == "modeling_method"))


def write_per_paper_summary(per_paper):
    fields = ["paper_id", "canonical_title", "paper_type", "batch_num",
                "primary_storage_domain", "paper_context_status",
                "processed", "n_accepted", "n_candidate", "n_rejected",
                "n_own_accepted", "n_ref_accepted", "recovery_used"]
    _write_csv(os.path.join(AGG_DIR, "per_paper_summary.csv"),
                fields, per_paper)


def copy_failed_and_cost():
    import shutil
    for src, dst in ((config.STAGE_A_FULL_V1_FAILED_CSV,
                      os.path.join(AGG_DIR, "failed_papers.csv")),
                     (config.STAGE_A_FULL_V1_COST_LEDGER_CSV,
                      os.path.join(AGG_DIR, "cost_ledger.csv"))):
        if os.path.isfile(src):
            shutil.copy2(src, dst)


def write_external_lit_candidates(all_methods):
    """spec 九: external_literature_candidates.csv from referenced_methods."""
    stubs = {}
    for m in all_methods:
        if m.get("kind") != "referenced": continue
        sid = m.get("external_stub_id", "")
        if not sid: continue
        stubs.setdefault(sid, {
            "external_stub_id": sid,
            "normalized_method_name": m.get("normalized_method_name",
                                               m.get("name", "")),
            "cited_author": "",
            "cited_year": "",
            "cited_reference_number": "",
            "evidence_paper_ids": set(),
            "evidence_quote_first": "",
            "support_scope": m.get("support_scope", ""),
            "occurrence_count": 0,
            "in_accepted_count": 0,
            "domains_seen": set(),
        })
        s = stubs[sid]
        # 保留任何非空的 author/year/ref number
        if m.get("cited_author") and not s["cited_author"]:
            s["cited_author"] = m["cited_author"]
        if m.get("cited_year") and not s["cited_year"]:
            s["cited_year"] = m["cited_year"]
        if m.get("cited_reference_number") and not s["cited_reference_number"]:
            s["cited_reference_number"] = m["cited_reference_number"]
        s["evidence_paper_ids"].add(m["paper_id"])
        if not s["evidence_quote_first"]:
            s["evidence_quote_first"] = m.get(
                "evidence_text_resolved", "")[:400]
        s["occurrence_count"] += 1
        if m.get("validation_status") == "accepted":
            s["in_accepted_count"] += 1
        if m.get("primary_storage_domain"):
            s["domains_seen"].add(m["primary_storage_domain"])

    rows = []
    for sid, s in stubs.items():
        # priority = 归一化到 [0, 1] 后加权
        # 重复引用 (最重): 每次占 5 分
        # 有作者+年份 (中): 6 分
        # accepted 至少 1 次 (中): 4 分
        # 主储能领域 (轻): 3 分
        # 参考编号存在 (轻): 2 分
        p = 0
        p += min(s["occurrence_count"], 5) * 5   # cap at 5
        if s["cited_author"]: p += 3
        if s["cited_year"]: p += 3
        if s["in_accepted_count"] > 0: p += 4
        if s["domains_seen"]: p += 3
        if s["cited_reference_number"]: p += 2
        rows.append({
            "external_stub_id": sid,
            "normalized_method_name": s["normalized_method_name"],
            "cited_author": s["cited_author"],
            "cited_year": s["cited_year"],
            "cited_reference_number": s["cited_reference_number"],
            "evidence_paper_id": ";".join(sorted(s["evidence_paper_ids"])),
            "evidence_quote": s["evidence_quote_first"],
            "support_scope": s["support_scope"],
            "occurrence_count": s["occurrence_count"],
            "priority_score": p,
            "retrieval_status": "not_retrieved",
        })
    rows.sort(key=lambda r: -r["priority_score"])
    _write_csv(os.path.join(AGG_DIR, "external_literature_candidates.csv"),
                ["external_stub_id", "normalized_method_name",
                  "cited_author", "cited_year", "cited_reference_number",
                  "evidence_paper_id", "evidence_quote", "support_scope",
                  "occurrence_count", "priority_score", "retrieval_status"],
                rows)
    return len(rows)


def summarize_metrics(all_methods, per_paper):
    ptypes, _, _ = load_context_maps()
    batches = load_batches_csv()

    # 21 项 metrics
    total_papers = len(per_paper)
    processed = [p for p in per_paper if p["processed"]]
    n_processed = len(processed)
    n_skipped = total_papers - n_processed

    # Load cost ledger for API calls / tokens
    api_main = 0
    api_recovery = 0
    total_prompt = 0
    total_completion = 0
    total_cost = 0.0
    if os.path.isfile(config.STAGE_A_FULL_V1_COST_LEDGER_CSV):
        with open(config.STAGE_A_FULL_V1_COST_LEDGER_CSV,
                    "r", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                if "recovery" in (r.get("model") or "").lower():
                    api_recovery += 1
                elif "revalidate" in (r.get("model") or "").lower():
                    pass   # 0-cost revalidate row
                else:
                    api_main += 1
                try:
                    total_prompt += int(r["prompt_tokens"])
                    total_completion += int(r["completion_tokens"])
                    total_cost += float(r["estimated_cost_cny"])
                except (ValueError, KeyError): pass

    failed = 0
    if os.path.isfile(config.STAGE_A_FULL_V1_FAILED_CSV):
        with open(config.STAGE_A_FULL_V1_FAILED_CSV,
                    "r", encoding="utf-8-sig") as f:
            failed = sum(1 for _ in csv.DictReader(f))

    accepted = [m for m in all_methods if m.get("validation_status") == "accepted"]
    candidate = [m for m in all_methods if m.get("validation_status") == "candidate"]
    rejected = [m for m in all_methods if m.get("validation_status") == "rejected"]

    role_dist = Counter(m.get("method_role", "unclear") for m in all_methods)
    support_dist = Counter(m.get("support_scope", "") for m in all_methods)
    scope_dist = Counter()
    for p in per_paper:
        s = (p["paper_context_status"] or "").strip().lower()
        if s == "confirmed": scope_dist["main_storage"] += 1
        elif s == "non_storage": scope_dist["non_storage"] += 1
        else: scope_dist["uncertain"] += 1

    # research 无 accepted own
    research_no_own = sum(1 for p in per_paper
                            if p["paper_type"] == "research_article"
                            and p["n_own_accepted"] == 0)
    # review 无 accepted referenced
    review_no_ref = sum(1 for p in per_paper
                          if p["paper_type"] == "review_article"
                          and p["n_ref_accepted"] == 0)

    # evidence + slice via re-walk
    total_ids = 0; valid_ids = 0; slice_hit = 0; slice_total = 0
    ptypes2, _, _ = load_context_maps()
    for pid in batches:
        d = fr.per_paper_dir(pid)
        try:
            with open(os.path.join(d, "sentence_index.json"),
                        "r", encoding="utf-8") as f:
                sidx = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError): continue
        sid_map = {s["sentence_id"]: s.get("sentence_text", "")
                    for s in sidx.get("sentences", [])}
        for m in all_methods:
            if m.get("paper_id") != pid: continue
            for sid in (m.get("evidence_sentence_ids") or []):
                total_ids += 1
                if sid in sid_map:
                    valid_ids += 1
                    slice_total += 1
                    if sid_map[sid].strip():
                        slice_hit += 1

    id_valid_rate = (valid_ids / total_ids) if total_ids else 0.0
    slice_rate = (slice_hit / slice_total) if slice_total else 0.0

    # external stubs
    stubs = {m["external_stub_id"] for m in all_methods
             if m.get("kind") == "referenced" and m.get("external_stub_id")}

    ref_methods = [m for m in all_methods if m.get("kind") == "referenced"]
    a_hit = sum(1 for m in ref_methods if m.get("cited_author"))
    y_hit = sum(1 for m in ref_methods if m.get("cited_year"))
    r_hit = sum(1 for m in ref_methods if m.get("cited_reference_number"))

    # 专利规范化数量
    patent_norm = sum(1 for m in all_methods if m.get("source_organization"))
    # 通用降级数量 (spec 七: reason contains demoted_bare_generic)
    demoted = sum(1 for m in all_methods
                    if "demoted_bare_generic_name" in (
                        m.get("validation_reason", "") or ""))

    # OCR 异常论文: preflight-based (n slice mismatch / n empty index)
    ocr_bad = 0
    if os.path.isfile(config.STAGE_A_FULL_V1_PREFLIGHT_JSON):
        with open(config.STAGE_A_FULL_V1_PREFLIGHT_JSON,
                    "r", encoding="utf-8") as f:
            pf = json.load(f)
        s = pf.get("summary", {})
        ocr_bad = s.get("n_slice_mismatch_papers", 0) + s.get(
            "n_empty_input", 0)

    # per-batch quality (each of 14 batches)
    per_batch_qual = {}
    for bn in range(1, 15):
        pids_bn = [pid for pid, b in batches.items() if b == bn]
        if not pids_bn: continue
        acc_n = sum(1 for m in accepted if m.get("batch_num") == bn)
        cand_n = sum(1 for m in candidate if m.get("batch_num") == bn)
        rej_n = sum(1 for m in rejected if m.get("batch_num") == bn)
        cost_bn = 0.0
        with open(config.STAGE_A_FULL_V1_COST_LEDGER_CSV,
                    "r", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                if r["paper_id"] in pids_bn:
                    try: cost_bn += float(r["estimated_cost_cny"])
                    except (ValueError, KeyError): pass
        per_batch_qual[bn] = {
            "n_papers": len(pids_bn),
            "n_accepted": acc_n, "n_candidate": cand_n, "n_rejected": rej_n,
            "est_cost_cny": round(cost_bn, 3),
        }

    # Stop conditions status
    status_p = os.path.join(config.STAGE_A_FULL_V1_DIR, "batch_reports",
                             "run_status.json")
    stopped_early = False; stop_reason = None
    if os.path.isfile(status_p):
        with open(status_p, "r", encoding="utf-8") as f:
            status = json.load(f)
        stopped_early = status.get("stopped_early", False)
        stop_reason = status.get("stop_reason")

    return {
        "total_papers": total_papers,
        "n_processed": n_processed,
        "n_failed": failed,
        "n_skipped": n_skipped,
        "api_main_calls": api_main,
        "api_recovery_calls": api_recovery,
        "prompt_tokens": total_prompt,
        "completion_tokens": total_completion,
        "estimated_cost_cny": round(total_cost, 3),
        "n_methods_total": len(all_methods),
        "n_accepted": len(accepted),
        "n_candidate": len(candidate),
        "n_rejected": len(rejected),
        "n_own": sum(1 for m in all_methods if m.get("kind") == "own"),
        "n_referenced": sum(1 for m in all_methods
                             if m.get("kind") == "referenced"),
        "role_distribution": dict(role_dist),
        "support_scope_distribution": dict(support_dist),
        "storage_scope_distribution": dict(scope_dist),
        "avg_methods_per_paper": round(len(all_methods) / max(1, n_processed), 2),
        "research_no_own_count": research_no_own,
        "review_no_ref_count": review_no_ref,
        "evidence_id_valid_rate_pct": round(id_valid_rate * 100, 2),
        "slice_consistency_pct": round(slice_rate * 100, 2),
        "external_stub_count": len(stubs),
        "cited_author_resolution_pct": round(
            100 * a_hit / max(1, len(ref_methods)), 2),
        "cited_year_resolution_pct": round(
            100 * y_hit / max(1, len(ref_methods)), 2),
        "cited_refnum_resolution_pct": round(
            100 * r_hit / max(1, len(ref_methods)), 2),
        "patent_normalized_count": patent_norm,
        "bare_generic_demoted_count": demoted,
        "ocr_bad_papers_count": ocr_bad,
        "per_batch": per_batch_qual,
        "stopped_early": stopped_early,
        "stop_reason": stop_reason,
    }


def write_report(metrics, ext_count):
    with open(os.path.join(AGG_DIR, "stage_a_full_report.json"),
                "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)
    md = [f"# Stage A 全量抽取 汇总报告 (v1.2)\n"]
    md.append(f"> Generated: {datetime.now().isoformat(timespec='seconds')}\n\n")

    md.append(f"## 一. 论文处理概览\n")
    md.append(f"- 总论文数: **{metrics['total_papers']}**\n")
    md.append(f"- 成功处理: **{metrics['n_processed']}**\n")
    md.append(f"- 失败: **{metrics['n_failed']}**\n")
    md.append(f"- 跳过 / 未处理: **{metrics['n_skipped']}**\n\n")

    md.append(f"## 二. API 调用统计\n")
    md.append(f"- 主 Stage A 调用: **{metrics['api_main_calls']}**\n")
    md.append(f"- Recovery 调用: **{metrics['api_recovery_calls']}**\n")
    md.append(f"- prompt_tokens: {metrics['prompt_tokens']:,}\n")
    md.append(f"- completion_tokens: {metrics['completion_tokens']:,}\n")
    md.append(f"- 估算费用累计: **¥{metrics['estimated_cost_cny']}**\n\n")

    md.append(f"## 三. 方法统计\n")
    md.append(f"- 方法总数: **{metrics['n_methods_total']}**\n")
    md.append(f"- accepted: **{metrics['n_accepted']}** / "
                f"candidate: **{metrics['n_candidate']}** / "
                f"rejected: **{metrics['n_rejected']}**\n")
    md.append(f"- own: **{metrics['n_own']}** / referenced: "
                f"**{metrics['n_referenced']}**\n")
    md.append(f"- 每篇平均方法数: **{metrics['avg_methods_per_paper']}**\n\n")

    md.append(f"## 四. method_role 分布\n")
    for k in ("technology_solution", "modeling_method",
                "research_method", "analysis_method", "unclear"):
        md.append(f"- {k}: {metrics['role_distribution'].get(k, 0)}\n")
    md.append("\n")

    md.append(f"## 五. support_scope / storage_scope 分布\n")
    md.append(f"### support_scope\n")
    for k, v in sorted(metrics["support_scope_distribution"].items(),
                        key=lambda x: -x[1]):
        md.append(f"- `{k}`: {v}\n")
    md.append(f"\n### storage_scope\n")
    for k, v in sorted(metrics["storage_scope_distribution"].items(),
                        key=lambda x: -x[1]):
        md.append(f"- `{k}`: {v}\n")
    md.append("\n")

    md.append(f"## 六. 质量与覆盖度指标\n")
    md.append(f"- research 无 accepted own: "
                f"**{metrics['research_no_own_count']}**\n")
    md.append(f"- review 无 accepted referenced: "
                f"**{metrics['review_no_ref_count']}**\n")
    md.append(f"- evidence sentence_id 有效率: "
                f"**{metrics['evidence_id_valid_rate_pct']}%**\n")
    md.append(f"- 原文切片一致率: **{metrics['slice_consistency_pct']}%**\n")
    md.append(f"- external_stub_id 数量: "
                f"**{metrics['external_stub_count']}**\n")
    md.append(f"- 作者解析率: {metrics['cited_author_resolution_pct']}%\n")
    md.append(f"- 年份解析率: {metrics['cited_year_resolution_pct']}%\n")
    md.append(f"- 引用编号解析率: "
                f"{metrics['cited_refnum_resolution_pct']}%\n")
    md.append(f"- 专利规范化条数: "
                f"**{metrics['patent_normalized_count']}**\n")
    md.append(f"- 孤立通用方法降级条数: "
                f"**{metrics['bare_generic_demoted_count']}**\n")
    md.append(f"- OCR 异常论文数: **{metrics['ocr_bad_papers_count']}**\n\n")

    md.append(f"## 七. 每个批次质量与费用\n")
    md.append("| batch | 篇数 | accepted | candidate | rejected | 费用 |\n")
    md.append("|:-----:|:----:|:--------:|:---------:|:--------:|:----:|\n")
    for bn in sorted(metrics["per_batch"].keys()):
        pb = metrics["per_batch"][bn]
        md.append(f"| {bn} | {pb['n_papers']} | {pb['n_accepted']} "
                    f"| {pb['n_candidate']} | {pb['n_rejected']} "
                    f"| ¥{pb['est_cost_cny']} |\n")
    md.append("\n")

    md.append(f"## 八. 停止条件是否触发\n")
    md.append(f"- 停止条件触发: "
                f"**{'YES' if metrics['stopped_early'] else 'NO'}**\n")
    if metrics["stop_reason"]:
        md.append(f"- 停止原因: `{metrics['stop_reason']}`\n")
    md.append("\n")

    md.append(f"## 九. 外部缺失文献清单\n")
    md.append(f"- 生成到 `external_literature_candidates.csv`, "
                f"共 **{ext_count}** 条 (按 priority_score 降序)\n\n")

    md.append(f"## 十. 汇总 CSV 清单\n")
    for fn in ("methods_all.csv", "methods_accepted.csv",
                "methods_candidate.csv", "methods_rejected.csv",
                "methods_storage_main.csv", "methods_uncertain_scope.csv",
                "methods_non_storage.csv", "external_method_stubs.csv",
                "research_methods.csv", "technology_methods.csv",
                "modeling_methods.csv", "per_paper_summary.csv",
                "failed_papers.csv", "cost_ledger.csv",
                "external_literature_candidates.csv"):
        md.append(f"- `{fn}`\n")
    md.append("\n")

    with open(os.path.join(AGG_DIR, "stage_a_full_report.md"),
                "w", encoding="utf-8") as f:
        f.writelines(md)


def main():
    global AGG_DIR
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=AGG_DIR)
    args = ap.parse_args()
    AGG_DIR = args.out_dir
    os.makedirs(AGG_DIR, exist_ok=True)

    print(f"aggregating to: {AGG_DIR}")
    all_methods, per_paper = collect_all_methods_and_summary()
    print(f"loaded {len(all_methods)} methods across {len(per_paper)} papers")

    write_methods_csvs(all_methods)
    write_per_paper_summary(per_paper)
    copy_failed_and_cost()
    ext_count = write_external_lit_candidates(all_methods)
    metrics = summarize_metrics(all_methods, per_paper)
    write_report(metrics, ext_count)

    print("done.")
    print(json.dumps({k: v for k, v in metrics.items()
                        if not isinstance(v, (dict, list))},
                        ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError): pass
    sys.exit(main())
