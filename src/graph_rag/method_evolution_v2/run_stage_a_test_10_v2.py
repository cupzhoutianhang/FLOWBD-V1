"""run_stage_a_test_10_v2.py — Stage A v2 driver (sentence-id 引用协议, 10 篇).

严格遵守本轮 spec (spec 二/三/四/五/六/七/八/九):
  - 只用 MOONSHOT_API_KEY 环境变量; 只调 Moonshot 端点; 无 DMXAPI 分支
  - 只跑固定 10 篇, 输出 test_run_03_stage_a_sentence_ids/ (不覆盖 test_02)
  - 每篇 1 主 + 至多 1 重试 (JSON 失败); 全局 ≤20 调用
  - 预飞打印 model + 预计调用 + 预算; > ¥20 停下
  - 无演化关系; 不进 Stage B; 不写 DB
  - 附带生成 v02 vs v03 diff CSV/MD
"""
from __future__ import annotations

import csv
import json
import os
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_GRAPH_RAG_DIR = os.path.dirname(THIS_DIR)
if SRC_GRAPH_RAG_DIR not in sys.path:
    sys.path.insert(0, SRC_GRAPH_RAG_DIR)

from method_evolution_v2 import config                                        # noqa: E402
from method_evolution_v2.io import section_parser as sp                       # noqa: E402
from method_evolution_v2.stage_a import llm_client                            # noqa: E402
from method_evolution_v2.stage_a import method_extraction as me               # noqa: E402
from method_evolution_v2.stage_a import sentence_indexer as si                # noqa: E402


# 经验估算 (基于 v02 实际 usage): 10 篇平均 ~10k tokens/call. v03 sentence pack 加 ID 前缀
# 后约 +40%. 单调用 ~15k tokens 输入 + ~3k 输出 = ~18k 合计, 对应 moonshot-v1-auto 32k tier.
EST_INPUT_TOKENS_PER_CALL = 18000
EST_OUTPUT_TOKENS_PER_CALL = 3000

# Moonshot 32k tier 参考价: ¥24/M in/out (真实付费按官方账单)
MOONSHOT_AUTO_32K_INPUT_CNY_PER_M = 24.0
MOONSHOT_AUTO_32K_OUTPUT_CNY_PER_M = 24.0
MAX_CALLS_PER_PAPER = 2       # 硬上限 (1 primary + 1 retry)
BUDGET_HARD_STOP_CNY = 20.0


METHOD_CSV_FIELDS = [
    "paper_id", "method_id", "kind",
    "method_name", "normalized_name", "method_type",
    "problem_solved", "key_components",
    "evidence_quote", "evidence_section", "evidence_para_id",
    "evidence_char_start", "evidence_char_end",
    "evidence_sentence_ids", "evidence_missing_ids", "evidence_spans",
    "evidence_sufficiency",
    "citation_clue", "confidence_llm",
    "evidence_match_status", "validation_status", "rejected_reason",
]

PER_PAPER_FIELDS = [
    "paper_id", "canonical_title", "paper_type",
    "primary_storage_domain", "technology_subfield",
    "paper_context_status",
    "own_count", "referenced_count",
    "accepted_count", "candidate_count", "rejected_count",
    "call_count", "json_parse_ok", "json_parse_error",
    "prompt_tokens", "completion_tokens", "total_tokens",
    "estimated_cost_cny",
    "sentence_count", "sentence_pack_chars",
    "slice_verify_ok", "slice_mismatch_count",
    "note",
]

DIFF_FIELDS = [
    "paper_id",
    "v02_extracted", "v03_extracted",
    "v02_accepted", "v03_accepted",
    "v02_candidate", "v03_candidate",
    "v02_rejected", "v03_rejected",
    "v02_own", "v03_own",
    "v02_ref", "v03_ref",
    "v02_evidence_match_summary", "v03_evidence_match_summary",
    "recovered_from_v02_notfound",
    "v02_names",
    "v03_names",
    "name_overlap",
]


def _j(v) -> str:
    if isinstance(v, (list, dict)):
        return json.dumps(v, ensure_ascii=False)
    return "" if v is None else str(v)


def _load_json(p: str) -> dict:
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_csv_rows(p: str) -> list:
    with open(p, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _row_to_method_csv(paper_id: str, m: dict) -> dict:
    return {
        "paper_id": paper_id,
        "method_id": m.get("method_id", ""),
        "kind": m.get("kind", ""),
        "method_name": m.get("name", ""),
        "normalized_name": m.get("normalized_name", ""),
        "method_type": m.get("method_type", ""),
        "problem_solved": m.get("problem_solved", ""),
        "key_components": _j(m.get("key_components", [])),
        "evidence_quote": m.get("evidence_quote", ""),
        "evidence_section": m.get("evidence_section", ""),
        "evidence_para_id": m.get("evidence_para_id", ""),
        "evidence_char_start": m.get("evidence_char_start", -1),
        "evidence_char_end": m.get("evidence_char_end", -1),
        "evidence_sentence_ids": _j(m.get("evidence_sentence_ids", [])),
        "evidence_missing_ids": _j(m.get("evidence_missing_ids", [])),
        "evidence_spans": _j(m.get("evidence_spans", [])),
        "evidence_sufficiency": _j(m.get("evidence_sufficiency", {})),
        "citation_clue": m.get("citation_clue", ""),
        "confidence_llm": m.get("confidence_llm", ""),
        "evidence_match_status": m.get("evidence_match_status", ""),
        "validation_status": m.get("validation_status", ""),
        "rejected_reason": m.get("rejected_reason", ""),
    }


def _estimate_cost(prompt_toks: int, completion_toks: int) -> float:
    return (prompt_toks / 1_000_000 * MOONSHOT_AUTO_32K_INPUT_CNY_PER_M
            + completion_toks / 1_000_000 * MOONSHOT_AUTO_32K_OUTPUT_CNY_PER_M)


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    # ---- 预飞 ----
    try:
        key = llm_client.get_api_key()
    except RuntimeError as e:
        print("PRE-FLIGHT FAIL:", e)
        return 2

    model = os.environ.get("MOONSHOT_MODEL", llm_client.DEFAULT_MODEL)
    n_papers = len(config.TEST_RUN_01_PAPER_IDS)
    max_calls = n_papers * MAX_CALLS_PER_PAPER
    est_cost_per_call = _estimate_cost(EST_INPUT_TOKENS_PER_CALL,
                                        EST_OUTPUT_TOKENS_PER_CALL)
    est_cost_max = est_cost_per_call * max_calls

    print("=" * 70)
    print("Stage A v2 (sentence-id protocol) - 预飞检查")
    print(f"  model:            {model}")
    print(f"  api endpoint:     {llm_client.MOONSHOT_API_URL}")
    print(f"  key present:      yes (len={len(key)}, prefix={key[:6]}..., suffix=...{key[-4:]})")
    print(f"  papers to run:    {n_papers}")
    print(f"  max calls:        {max_calls} (1 primary + 1 retry per paper)")
    print(f"  est input/call:   {EST_INPUT_TOKENS_PER_CALL} tokens")
    print(f"  est output/call:  {EST_OUTPUT_TOKENS_PER_CALL} tokens")
    print(f"  est cost/call:    ¥{est_cost_per_call:.3f}  (assumed 32k tier rate)")
    print(f"  est cost max:     ¥{est_cost_max:.2f}")
    print(f"  budget hard stop: ¥{BUDGET_HARD_STOP_CNY:.2f}")
    if est_cost_max > BUDGET_HARD_STOP_CNY:
        print(f"STOP: est_cost_max ¥{est_cost_max:.2f} > threshold ¥{BUDGET_HARD_STOP_CNY:.2f}.")
        return 3
    print(f"  budget check:     OK")
    print("=" * 70)

    os.makedirs(config.STAGE_A_TEST_03_DIR, exist_ok=True)
    os.makedirs(config.STAGE_A_TEST_03_LOGS_DIR, exist_ok=True)
    os.makedirs(config.STAGE_A_TEST_03_SENTENCE_IDX_DIR, exist_ok=True)

    # 加载 v1.1 上下文
    tax_rows = {r["paper_id"]: r for r in _load_csv_rows(
        config.CORPUS_PP_V1_1_PAPER_TAXONOMY_CSV)}
    pt_rows = {r["paper_id"]: r for r in _load_csv_rows(
        config.CORPUS_PP_V1_1_PAPER_TYPES_CSV)}

    started_iso = datetime.now().isoformat(timespec="seconds")
    t0 = time.time()

    all_methods = []
    all_raw = []
    per_paper_rows = []
    total_calls = 0
    total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    log_sink = []

    for i, pid in enumerate(config.TEST_RUN_01_PAPER_IDS, 1):
        sec_path = os.path.join(config.CORPUS_PP_V1_1_SECTIONS_DIR, f"{pid}.json")
        if not os.path.isfile(sec_path):
            print(f"  [{i:>2}/10] SKIP sections missing: {pid}")
            per_paper_rows.append({"paper_id": pid, "note": "sections_json_missing"})
            continue
        sections_json = _load_json(sec_path)

        tax_r = tax_rows.get(pid, {})
        pt_r = pt_rows.get(pid, {})
        canonical_title = tax_r.get("canonical_title", pid)
        paper_type = pt_r.get("paper_type", "unclear")
        primary = tax_r.get("primary_storage_domain", "")
        subfield = tax_r.get("technology_subfield", "")
        try:
            apps = json.loads(tax_r.get("application_contexts", "[]"))
        except Exception:
            apps = []
        status = tax_r.get("paper_context_status", "")

        # 构建 sentence index 并且校验 slice-back (spec 二.2)
        all_sents_for_paper = si.build_sentence_index(sections_json, pid)
        # 用 full.md 校验 (读 full.md 只做校验; 不参与 LLM)
        md_path = config.full_md_path(pid)
        if os.path.isfile(md_path):
            with open(md_path, "r", encoding="utf-8") as f:
                full_md = f.read()
            slice_ok, mismatches = si.verify_sentence_slices(all_sents_for_paper, full_md)
        else:
            slice_ok, mismatches = False, [("md_missing", 0, "")]

        # 持久化 sentence index (每篇一份 JSON)
        idx_path = os.path.join(config.STAGE_A_TEST_03_SENTENCE_IDX_DIR, f"{pid}.json")
        with open(idx_path, "w", encoding="utf-8") as f:
            json.dump({
                "paper_id": pid,
                "sentence_count": len(all_sents_for_paper),
                "slice_verify_ok": slice_ok,
                "slice_mismatch_count": len(mismatches),
                "sentences": [s.to_dict() for s in all_sents_for_paper],
            }, f, ensure_ascii=False, indent=2)

        # 抽取
        t_paper = time.time()
        try:
            result = me.extract_paper(
                paper_id=pid, sections_json=sections_json,
                paper_type=paper_type,
                primary_storage_domain=primary,
                technology_subfield=subfield,
                application_contexts=apps,
                model=model,
                allow_retry=True,
                log_sink=log_sink,
            )
        except Exception as e:
            print(f"  [{i:>2}/10] EXC {pid}: {type(e).__name__}: {e}")
            per_paper_rows.append({
                "paper_id": pid, "canonical_title": canonical_title,
                "paper_type": paper_type,
                "note": f"exception: {type(e).__name__}: {e}",
            })
            continue
        dt = time.time() - t_paper

        total_calls += result["call_count"]
        for k in total_usage:
            total_usage[k] += result["usage_total"].get(k, 0)

        cls = result["methods_classified"]
        own_ct = sum(1 for m in cls if m["kind"] == "own")
        ref_ct = sum(1 for m in cls if m["kind"] == "referenced")
        acc_ct = sum(1 for m in cls if m["validation_status"] == "accepted")
        cand_ct = sum(1 for m in cls if m["validation_status"] == "candidate")
        rej_ct = sum(1 for m in cls if m["validation_status"] == "rejected")

        all_methods.extend(cls)

        pt_toks = result["usage_total"].get("prompt_tokens", 0)
        ct_toks = result["usage_total"].get("completion_tokens", 0)
        cost = _estimate_cost(pt_toks, ct_toks)

        all_raw.append({
            "paper_id": pid,
            "canonical_title": canonical_title,
            "paper_type": paper_type,
            "primary_storage_domain": primary,
            "technology_subfield": subfield,
            "paper_context_status": status,
            "call_count": result["call_count"],
            "json_parse_ok": result["json_parse_ok"],
            "json_parse_error": result["json_parse_error"],
            "usage_total": result["usage_total"],
            "own_methods_raw": result["own_methods_raw"],
            "referenced_methods_raw": result["referenced_methods_raw"],
            "raw_llm_text_last": result.get("raw_llm_text_last", "")[:12000],
            "sentence_pack_chars": result["sentence_pack_chars"],
            "sentence_count": len(result["sentence_index"]),
            "stage_a_version": result["stage_a_version"],
            "duration_sec": round(dt, 2),
            "slice_verify_ok": slice_ok,
            "slice_mismatch_count": len(mismatches),
        })

        per_paper_rows.append({
            "paper_id": pid,
            "canonical_title": canonical_title,
            "paper_type": paper_type,
            "primary_storage_domain": primary,
            "technology_subfield": subfield,
            "paper_context_status": status,
            "own_count": own_ct,
            "referenced_count": ref_ct,
            "accepted_count": acc_ct,
            "candidate_count": cand_ct,
            "rejected_count": rej_ct,
            "call_count": result["call_count"],
            "json_parse_ok": result["json_parse_ok"],
            "json_parse_error": result["json_parse_error"],
            "prompt_tokens": pt_toks,
            "completion_tokens": ct_toks,
            "total_tokens": result["usage_total"].get("total_tokens", 0),
            "estimated_cost_cny": round(cost, 4),
            "sentence_count": len(result["sentence_index"]),
            "sentence_pack_chars": result["sentence_pack_chars"],
            "slice_verify_ok": slice_ok,
            "slice_mismatch_count": len(mismatches),
            "note": "",
        })

        with open(os.path.join(config.STAGE_A_TEST_03_LOGS_DIR, f"{pid}.log.json"),
                  "w", encoding="utf-8") as f:
            json.dump({
                "paper_id": pid,
                "call_count": result["call_count"],
                "llm_calls": result["llm_calls"],
                "json_parse_ok": result["json_parse_ok"],
                "json_parse_error": result["json_parse_error"],
                "duration_sec": round(dt, 2),
                "sentence_pack_chars": result["sentence_pack_chars"],
                "sentence_count": len(result["sentence_index"]),
                "slice_verify_ok": slice_ok,
                "slice_mismatch_count": len(mismatches),
                "usage_total": result["usage_total"],
                "estimated_cost_cny": round(cost, 4),
            }, f, ensure_ascii=False, indent=2)

        print(f"  [{i:>2}/10] {pid[:36]:<36} "
              f"own={own_ct} ref={ref_ct} acc={acc_ct} cand={cand_ct} rej={rej_ct} "
              f"calls={result['call_count']} tok={result['usage_total'].get('total_tokens', 0)} "
              f"slice_ok={slice_ok}")

    dur = time.time() - t0

    # ---- 写 raw jsonl ----
    with open(config.STAGE_A_TEST_03_METHODS_RAW, "w", encoding="utf-8") as f:
        for r in all_raw:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # ---- 分桶 CSV ----
    def _write_csv(path, fields, rows):
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for row in rows:
                w.writerow({k: _j(row.get(k)) for k in fields})

    accepted = [_row_to_method_csv(m["paper_id"], m) for m in all_methods
                if m["validation_status"] == "accepted"]
    candidate = [_row_to_method_csv(m["paper_id"], m) for m in all_methods
                 if m["validation_status"] == "candidate"]
    rejected = [_row_to_method_csv(m["paper_id"], m) for m in all_methods
                if m["validation_status"] == "rejected"]

    _write_csv(config.STAGE_A_TEST_03_METHODS_ACCEPTED, METHOD_CSV_FIELDS, accepted)
    _write_csv(config.STAGE_A_TEST_03_METHODS_CANDIDATE, METHOD_CSV_FIELDS, candidate)
    _write_csv(config.STAGE_A_TEST_03_METHODS_REJECTED, METHOD_CSV_FIELDS, rejected)
    _write_csv(config.STAGE_A_TEST_03_PER_PAPER_CSV, PER_PAPER_FIELDS, per_paper_rows)

    total_cost = _estimate_cost(total_usage["prompt_tokens"],
                                 total_usage["completion_tokens"])

    manifest = {
        "run_started_at": started_iso,
        "duration_sec": round(dur, 2),
        "model": model,
        "api_endpoint": llm_client.MOONSHOT_API_URL,
        "stage_a_version": me.STAGE_A_VERSION,
        "paper_count": n_papers,
        "total_calls": total_calls,
        "max_calls_allowed": max_calls,
        "usage_total": total_usage,
        "pricing_assumed_32k_tier": {
            "input_cny_per_1M_tokens": MOONSHOT_AUTO_32K_INPUT_CNY_PER_M,
            "output_cny_per_1M_tokens": MOONSHOT_AUTO_32K_OUTPUT_CNY_PER_M,
        },
        "estimated_total_cost_cny": round(total_cost, 4),
        "budget_hard_stop_cny": BUDGET_HARD_STOP_CNY,
        "outputs": {
            "methods_raw": config.relative_path(config.STAGE_A_TEST_03_METHODS_RAW),
            "methods_accepted": config.relative_path(config.STAGE_A_TEST_03_METHODS_ACCEPTED),
            "methods_candidate": config.relative_path(config.STAGE_A_TEST_03_METHODS_CANDIDATE),
            "methods_rejected": config.relative_path(config.STAGE_A_TEST_03_METHODS_REJECTED),
            "per_paper_summary": config.relative_path(config.STAGE_A_TEST_03_PER_PAPER_CSV),
            "sentence_index_dir": config.relative_path(config.STAGE_A_TEST_03_SENTENCE_IDX_DIR),
        },
    }
    with open(config.STAGE_A_TEST_03_MANIFEST_JSON, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    # ============================================================
    # validation report
    # ============================================================
    match_status_counter = Counter(m["evidence_match_status"] for m in all_methods)
    status_counter = Counter(m["validation_status"] for m in all_methods)
    sufficiency_counter = Counter()
    for m in all_methods:
        suff = m.get("evidence_sufficiency") or {}
        sufficiency_counter[str(suff.get("sufficient", False))] += 1
    reject_reason_counter = Counter()
    for m in all_methods:
        if m["validation_status"] == "rejected":
            for r in (m["rejected_reason"] or "").split(","):
                r = r.strip()
                if r:
                    reject_reason_counter[r] += 1

    # ID 有效率 & 切片一致率
    total_ids = 0
    valid_ids = 0
    for m in all_methods:
        ids = m.get("evidence_sentence_ids") or []
        missing = m.get("evidence_missing_ids") or []
        total_ids += len(ids)
        valid_ids += len(ids) - len(missing)
    id_valid_rate = (valid_ids / total_ids) if total_ids else 0.0

    slice_verify_pass = sum(1 for r in per_paper_rows if r.get("slice_verify_ok") is True)
    slice_consistent_rate = slice_verify_pass / max(len(per_paper_rows), 1)

    # own = 0 且 research 的
    own_zero_research = [r for r in per_paper_rows
                         if r.get("paper_type") == "research_article"
                         and r.get("own_count") == 0]
    # research 无 accepted own
    no_accepted_own_research = []
    for r in per_paper_rows:
        if r.get("paper_type") != "research_article":
            continue
        pid = r["paper_id"]
        own_acc = sum(1 for m in all_methods
                       if m["paper_id"] == pid and m["kind"] == "own"
                       and m["validation_status"] == "accepted")
        if own_acc == 0:
            no_accepted_own_research.append(pid)
    # 每篇 accepted ≥2
    papers_with_ge_2_accepted = [
        r["paper_id"] for r in per_paper_rows if r.get("accepted_count", 0) >= 2
    ]

    val_report = {
        "totals": {
            "methods_extracted": len(all_methods),
            "own_methods": sum(1 for m in all_methods if m["kind"] == "own"),
            "referenced_methods": sum(1 for m in all_methods if m["kind"] == "referenced"),
            "accepted": status_counter.get("accepted", 0),
            "candidate": status_counter.get("candidate", 0),
            "rejected": status_counter.get("rejected", 0),
        },
        "match_status": dict(match_status_counter),
        "sufficiency_pass_count": sufficiency_counter.get("True", 0),
        "sufficiency_fail_count": sufficiency_counter.get("False", 0),
        "evidence_id_total": total_ids,
        "evidence_id_valid": valid_ids,
        "evidence_id_valid_rate": round(id_valid_rate, 4),
        "slice_verify_pass_papers": slice_verify_pass,
        "slice_consistent_rate": round(slice_consistent_rate, 4),
        "reject_reasons": dict(reject_reason_counter),
        "research_papers_with_zero_own": [r["paper_id"] for r in own_zero_research],
        "research_papers_with_no_accepted_own": no_accepted_own_research,
        "papers_with_ge_2_accepted": papers_with_ge_2_accepted,
        "actual_api_calls": total_calls,
        "actual_cost_cny": round(total_cost, 4),
    }
    with open(config.STAGE_A_TEST_03_VALIDATION_JSON, "w", encoding="utf-8") as f:
        json.dump(val_report, f, ensure_ascii=False, indent=2)

    # ============================================================
    # v02 vs v03 diff
    # ============================================================
    diff_rows = []
    if os.path.isfile(config.STAGE_A_TEST_02_METHODS_ACCEPTED):
        v02_all = defaultdict(list)   # pid -> [method_row]
        for name, path in [
            ("accepted", config.STAGE_A_TEST_02_METHODS_ACCEPTED),
            ("candidate", config.STAGE_A_TEST_02_METHODS_CANDIDATE),
            ("rejected", config.STAGE_A_TEST_02_METHODS_REJECTED),
        ]:
            if os.path.isfile(path):
                for row in _load_csv_rows(path):
                    row["_bucket"] = name
                    v02_all[row["paper_id"]].append(row)

        v03_all = defaultdict(list)
        for m in all_methods:
            v03_all[m["paper_id"]].append(m)

        for pid in config.TEST_RUN_01_PAPER_IDS:
            v02 = v02_all.get(pid, [])
            v03 = v03_all.get(pid, [])

            def _count(bucket, in_v02):
                if in_v02:
                    return sum(1 for x in v02 if x["_bucket"] == bucket)
                return sum(1 for x in v03 if x["validation_status"] == bucket)

            v02_ms = Counter(x.get("evidence_match_status", "") for x in v02)
            v03_ms = Counter(x.get("evidence_match_status", "") for x in v03)

            # 恢复率: v02 里 not_found (rejected) 的 method_name, v03 里同 pid 里同名(归一)是否找到证据
            v02_notfound_names = {x.get("normalized_name", "") for x in v02
                                   if x.get("evidence_match_status") == "not_found"
                                      and x.get("normalized_name")}
            v03_recovered_names = set()
            for x in v03:
                if x["normalized_name"] in v02_notfound_names \
                        and x["validation_status"] in ("accepted", "candidate"):
                    v03_recovered_names.add(x["normalized_name"])

            v02_names = sorted(set(x.get("method_name", "") for x in v02 if x.get("method_name")))
            v03_names = sorted(set(x.get("name", "") for x in v03 if x.get("name")))
            overlap = sorted(set(v02_names) & set(v03_names))

            diff_rows.append({
                "paper_id": pid,
                "v02_extracted": len(v02),
                "v03_extracted": len(v03),
                "v02_accepted": _count("accepted", True),
                "v03_accepted": _count("accepted", False),
                "v02_candidate": _count("candidate", True),
                "v03_candidate": _count("candidate", False),
                "v02_rejected": _count("rejected", True),
                "v03_rejected": _count("rejected", False),
                "v02_own": sum(1 for x in v02 if x.get("kind") == "own"),
                "v03_own": sum(1 for x in v03 if x.get("kind") == "own"),
                "v02_ref": sum(1 for x in v02 if x.get("kind") == "referenced"),
                "v03_ref": sum(1 for x in v03 if x.get("kind") == "referenced"),
                "v02_evidence_match_summary": dict(v02_ms),
                "v03_evidence_match_summary": dict(v03_ms),
                "recovered_from_v02_notfound": sorted(v03_recovered_names),
                "v02_names": v02_names,
                "v03_names": v03_names,
                "name_overlap": overlap,
            })
        _write_csv(config.STAGE_A_TEST_03_DIFF_CSV, DIFF_FIELDS, diff_rows)

    # ============================================================
    # validation MD + diff MD
    # ============================================================
    ml = []
    ml.append("# Stage A v2 抽取校验报告 (test_run_03_stage_a_sentence_ids)\n")
    ml.append(
        f"> 运行时间: {started_iso} · 耗时 {round(dur, 1)}s\n"
        f"> 模型: `{model}`\n"
        f"> 论文: 10 · API 调用: **{total_calls}** / 上限 {max_calls}\n"
        f"> 实际 tokens: prompt={total_usage['prompt_tokens']} / "
        f"completion={total_usage['completion_tokens']} / total={total_usage['total_tokens']}\n"
        f"> 预算 (Moonshot 32k tier 参考价): **¥{round(total_cost, 3)}** "
        f"(硬门限 ¥{BUDGET_HARD_STOP_CNY})\n\n"
    )
    ml.append("## 一、汇总\n")
    ml.append(f"- 抽取方法总数: **{len(all_methods)}** (own={val_report['totals']['own_methods']}, "
              f"ref={val_report['totals']['referenced_methods']})\n")
    ml.append(f"- accepted: **{val_report['totals']['accepted']}** · "
              f"candidate: {val_report['totals']['candidate']} · "
              f"rejected: {val_report['totals']['rejected']}\n")

    ml.append("\n## 二、证据 ID 有效性 & 切片一致性 (spec 二/四关键指标)\n")
    ml.append(f"- 证据 ID 总数: **{total_ids}**\n")
    ml.append(f"- 有效 ID (存在于句子索引): **{valid_ids}**\n")
    ml.append(f"- **证据 ID 有效率**: **{round(id_valid_rate * 100, 2)}%**\n")
    ml.append(f"- **原文切片一致率**: **{round(slice_consistent_rate * 100, 2)}%** "
              f"({slice_verify_pass}/{len(per_paper_rows)} 篇 slice_verify_ok=True)\n")

    ml.append("\n## 三、evidence_match_status 分布\n")
    ml.append("| status | count |\n|---|---:|\n")
    for k, v in match_status_counter.most_common():
        ml.append(f"| `{k}` | {v} |\n")

    ml.append("\n## 四、充分性检查结果\n")
    ml.append(f"- sufficient=True (充分): **{val_report['sufficiency_pass_count']}**\n")
    ml.append(f"- sufficient=False (不充分): {val_report['sufficiency_fail_count']}\n")

    if reject_reason_counter:
        ml.append("\n## 五、拒绝原因分布\n| reason | count |\n|---|---:|\n")
        for k, v in sorted(reject_reason_counter.items(), key=lambda kv: -kv[1]):
            ml.append(f"| `{k}` | {v} |\n")

    ml.append("\n## 六、每篇 own / ref / accepted / candidate / rejected\n")
    ml.append("| # | paper_id | pt | own | ref | acc | cand | rej | calls | tokens | ¥ |\n"
              "|--:|---|---|--:|--:|--:|--:|--:|--:|--:|--:|\n")
    for i, r in enumerate(per_paper_rows, 1):
        ml.append(
            f"| {i} | `{r['paper_id'][:36]}` | {r.get('paper_type','')[:6]} "
            f"| {r.get('own_count', 0)} | {r.get('referenced_count', 0)} "
            f"| {r.get('accepted_count', 0)} | {r.get('candidate_count', 0)} "
            f"| {r.get('rejected_count', 0)} | {r.get('call_count', 0)} "
            f"| {r.get('total_tokens', 0)} | {r.get('estimated_cost_cny', 0)} |\n"
        )

    ml.append(f"\n## 七、research 无 accepted own 的论文 ({len(no_accepted_own_research)})\n")
    for pid in no_accepted_own_research:
        ml.append(f"- `{pid}`\n")
    ml.append(f"\n## 八、每篇 accepted ≥2 的论文 ({len(papers_with_ge_2_accepted)})\n")
    for pid in papers_with_ge_2_accepted:
        ml.append(f"- `{pid}`\n")

    with open(config.STAGE_A_TEST_03_VALIDATION_MD, "w", encoding="utf-8") as f:
        f.writelines(ml)

    # ---- diff MD ----
    if diff_rows:
        dml = []
        dml.append("# Stage A v02 vs v03 对比\n\n")
        dml.append("> v02: LLM 复制 evidence_quote, 本地做 exact/normalized 匹配\n"
                   "> v03: LLM 只返回 sentence_id, 本地用索引解析证据 + 独立充分性检查\n\n")
        # 汇总
        totals_v02_ext = sum(d["v02_extracted"] for d in diff_rows)
        totals_v03_ext = sum(d["v03_extracted"] for d in diff_rows)
        totals_v02_acc = sum(d["v02_accepted"] for d in diff_rows)
        totals_v03_acc = sum(d["v03_accepted"] for d in diff_rows)
        totals_v02_cand = sum(d["v02_candidate"] for d in diff_rows)
        totals_v03_cand = sum(d["v03_candidate"] for d in diff_rows)
        totals_v02_rej = sum(d["v02_rejected"] for d in diff_rows)
        totals_v03_rej = sum(d["v03_rejected"] for d in diff_rows)
        total_recovered = sum(len(d["recovered_from_v02_notfound"]) for d in diff_rows)
        dml.append("## 汇总\n\n")
        dml.append("| 指标 | v02 | v03 |\n|---|--:|--:|\n")
        dml.append(f"| 抽取总数 | {totals_v02_ext} | {totals_v03_ext} |\n")
        dml.append(f"| accepted | {totals_v02_acc} | {totals_v03_acc} |\n")
        dml.append(f"| candidate | {totals_v02_cand} | {totals_v03_cand} |\n")
        dml.append(f"| rejected | {totals_v02_rej} | {totals_v03_rej} |\n")
        dml.append(f"\n- 从 v02 not_found 状态被 v03 恢复(以归一名匹配)的方法数: **{total_recovered}**\n\n")

        dml.append("## 逐篇\n\n")
        for d in diff_rows:
            dml.append(f"### `{d['paper_id']}`\n")
            dml.append(f"- extracted: v02={d['v02_extracted']} → v03={d['v03_extracted']}\n")
            dml.append(f"- accepted:  v02={d['v02_accepted']} → v03={d['v03_accepted']}\n")
            dml.append(f"- candidate: v02={d['v02_candidate']} → v03={d['v03_candidate']}\n")
            dml.append(f"- rejected:  v02={d['v02_rejected']} → v03={d['v03_rejected']}\n")
            dml.append(f"- own: v02={d['v02_own']} → v03={d['v03_own']} · "
                       f"ref: v02={d['v02_ref']} → v03={d['v03_ref']}\n")
            dml.append(f"- v02 match_status: {d['v02_evidence_match_summary']}\n")
            dml.append(f"- v03 match_status: {d['v03_evidence_match_summary']}\n")
            if d["recovered_from_v02_notfound"]:
                dml.append(f"- **v03 恢复的 v02 not_found 方法**: {d['recovered_from_v02_notfound']}\n")
            dml.append(f"- name_overlap ({len(d['name_overlap'])}): {d['name_overlap']}\n\n")

        with open(config.STAGE_A_TEST_03_DIFF_MD, "w", encoding="utf-8") as f:
            f.writelines(dml)

    print()
    print("=" * 70)
    print(f"Stage A v2 done: 10 papers, {total_calls} calls, ~¥{round(total_cost, 3)}, {round(dur, 1)}s")
    print(f"  accepted={val_report['totals']['accepted']} "
          f"candidate={val_report['totals']['candidate']} "
          f"rejected={val_report['totals']['rejected']}")
    print(f"  id_valid_rate={round(id_valid_rate * 100, 2)}% "
          f"slice_consistent_rate={round(slice_consistent_rate * 100, 2)}%")
    print(f"outputs: {config.relative_path(config.STAGE_A_TEST_03_DIR)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
