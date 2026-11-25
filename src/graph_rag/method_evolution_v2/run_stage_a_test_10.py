"""run_stage_a_test_10.py — Stage A 方法抽取 driver (只跑 10 篇, 用 Kimi K2).

严格遵守 spec:
  - 只抽方法, 不抽演化关系
  - 输入: corpus_preprocess_v1_1/sections/, paper_type CSV, paper_taxonomy CSV
  - LLM key: 仅从 MOONSHOT_API_KEY 环境变量读, 源码无 fallback key
  - 每篇最多 1 主 + 1 重试 = 2 次 API 调用
  - 单篇失败继续, 不中断
  - 开始前打印: 模型名 + 预计调用数 + 预算; > ¥20 停止等待确认
  - 无 Neo4j / Milvus / legacy 读取
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

from method_evolution_v2 import config                                          # noqa: E402
from method_evolution_v2.stage_a import llm_client                              # noqa: E402
from method_evolution_v2.stage_a import method_extraction as me                 # noqa: E402


# ============================================================
# 预算 & 预计调用
# ============================================================

# 保守估计: input ~40k / call, output ~5k / call
EST_INPUT_TOKENS_PER_CALL = 40000
EST_OUTPUT_TOKENS_PER_CALL = 5000

# Kimi K2 (kimi-k2-0711-preview) 参考单价 (人民币 / 百万 token)
# 说明: 若实际单价不同, 会在调用后从 usage 反算, 不影响运行
KIMI_K2_INPUT_PRICE_CNY_PER_M = 4.0
KIMI_K2_OUTPUT_PRICE_CNY_PER_M = 16.0

# 每篇论文最多 2 次调用 (1 主 + 1 重试)
MAX_CALLS_PER_PAPER = 2
BUDGET_HARD_STOP_CNY = 20.0


# ============================================================
# CSV schemas
# ============================================================

METHOD_CSV_FIELDS = [
    "paper_id", "method_id", "kind",
    "method_name", "normalized_name", "method_type",
    "problem_solved", "key_components",
    "evidence_quote", "evidence_section", "evidence_para_id",
    "evidence_char_start", "evidence_char_end",
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
    "section_pack_chars",
    "note",
]


# ============================================================
# helpers
# ============================================================

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
        "citation_clue": m.get("citation_clue", ""),
        "confidence_llm": m.get("confidence_llm", ""),
        "evidence_match_status": m.get("evidence_match_status", ""),
        "validation_status": m.get("validation_status", ""),
        "rejected_reason": m.get("rejected_reason", ""),
    }


def _estimate_cost(prompt_toks: int, completion_toks: int) -> float:
    return (
        prompt_toks / 1_000_000 * KIMI_K2_INPUT_PRICE_CNY_PER_M
        + completion_toks / 1_000_000 * KIMI_K2_OUTPUT_PRICE_CNY_PER_M
    )


# ============================================================
# 主
# ============================================================

def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    # ---- 预飞: 检查 key + 打印计划 ----
    try:
        key = llm_client.get_api_key()
    except RuntimeError as e:
        print("PRE-FLIGHT FAIL:", e)
        return 2

    model = llm_client.DEFAULT_MODEL
    n_papers = len(config.TEST_RUN_01_PAPER_IDS)
    max_calls = n_papers * MAX_CALLS_PER_PAPER
    est_cost_per_call = _estimate_cost(EST_INPUT_TOKENS_PER_CALL,
                                        EST_OUTPUT_TOKENS_PER_CALL)
    est_cost_max = est_cost_per_call * max_calls

    print("=" * 70)
    print("Stage A - 方法抽取, 预飞检查")
    print(f"  model:            {model}")
    print(f"  API endpoint:     {llm_client.MOONSHOT_API_URL}")
    print(f"  key present:      yes (len={len(key)}, prefix={key[:6]}..., suffix=...{key[-4:]})")
    print(f"  papers to run:    {n_papers} (10-paper test set)")
    print(f"  max calls:        {max_calls} (1 primary + 1 retry per paper)")
    print(f"  est/call:         ~{EST_INPUT_TOKENS_PER_CALL}in + {EST_OUTPUT_TOKENS_PER_CALL}out tokens")
    print(f"  est cost/call:    ¥{est_cost_per_call:.3f}")
    print(f"  est cost max:     ¥{est_cost_max:.2f}")
    print(f"  budget hard stop: ¥{BUDGET_HARD_STOP_CNY:.2f}")
    if est_cost_max > BUDGET_HARD_STOP_CNY:
        print(f"STOP: est_cost_max (¥{est_cost_max:.2f}) exceeds BUDGET_HARD_STOP_CNY "
              f"(¥{BUDGET_HARD_STOP_CNY:.2f}). Aborting per spec 五. Waiting for user.")
        return 3
    print(f"  budget check:     OK (well under ¥20 threshold)")
    print("=" * 70)

    # ---- 目录 ----
    os.makedirs(config.STAGE_A_TEST_02_DIR, exist_ok=True)
    os.makedirs(config.STAGE_A_TEST_02_LOGS_DIR, exist_ok=True)

    # ---- 加载 v1.1 上下文 ----
    tax_rows = {r["paper_id"]: r for r in _load_csv_rows(
        config.CORPUS_PP_V1_1_PAPER_TAXONOMY_CSV)}
    pt_rows = {r["paper_id"]: r for r in _load_csv_rows(
        config.CORPUS_PP_V1_1_PAPER_TYPES_CSV)}

    # ---- 主循环 ----
    started_iso = datetime.now().isoformat(timespec="seconds")
    t0 = time.time()
    all_methods = []
    all_raw_records = []      # 写 jsonl
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

        # 抽取
        t_paper = time.time()
        try:
            result = me.extract_paper(
                paper_id=pid,
                sections_json=sections_json,
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
                "paper_type": paper_type, "note": f"exception: {type(e).__name__}: {e}",
            })
            continue
        dt = time.time() - t_paper

        # 累计
        total_calls += result["call_count"]
        for k in total_usage:
            total_usage[k] += result["usage_total"].get(k, 0)

        cls = result["methods_classified"]
        own_ct = sum(1 for m in cls if m["kind"] == "own")
        ref_ct = sum(1 for m in cls if m["kind"] == "referenced")
        acc_ct = sum(1 for m in cls if m["validation_status"] == "accepted")
        cand_ct = sum(1 for m in cls if m["validation_status"] == "candidate")
        rej_ct = sum(1 for m in cls if m["validation_status"] == "rejected")

        # 每篇每方法追加
        all_methods.extend(cls)

        # 写 raw jsonl 记录
        all_raw_records.append({
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
            "section_pack_chars": result["section_pack_chars"],
            "stage_a_version": result["stage_a_version"],
            "duration_sec": round(dt, 2),
        })

        # per-paper summary
        pt_toks = result["usage_total"].get("prompt_tokens", 0)
        ct_toks = result["usage_total"].get("completion_tokens", 0)
        cost = _estimate_cost(pt_toks, ct_toks)
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
            "section_pack_chars": result["section_pack_chars"],
            "note": "",
        })

        # 单篇 log
        log_path = os.path.join(config.STAGE_A_TEST_02_LOGS_DIR, f"{pid}.log.json")
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump({
                "paper_id": pid,
                "call_count": result["call_count"],
                "llm_calls": result["llm_calls"],
                "json_parse_ok": result["json_parse_ok"],
                "json_parse_error": result["json_parse_error"],
                "duration_sec": round(dt, 2),
                "section_pack_chars": result["section_pack_chars"],
                "usage_total": result["usage_total"],
                "estimated_cost_cny": round(cost, 4),
            }, f, ensure_ascii=False, indent=2)

        print(f"  [{i:>2}/10] {pid[:36]:<36} "
              f"own={own_ct} ref={ref_ct} acc={acc_ct} cand={cand_ct} rej={rej_ct} "
              f"calls={result['call_count']} tok={result['usage_total'].get('total_tokens', 0)}")

    dur = time.time() - t0

    # ---- 写 raw jsonl ----
    with open(config.STAGE_A_TEST_02_METHODS_RAW, "w", encoding="utf-8") as f:
        for rec in all_raw_records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # ---- 分桶 CSV ----
    accepted_rows = [_row_to_method_csv(m["paper_id"], m) for m in all_methods
                     if m["validation_status"] == "accepted"]
    candidate_rows = [_row_to_method_csv(m["paper_id"], m) for m in all_methods
                      if m["validation_status"] == "candidate"]
    rejected_rows = [_row_to_method_csv(m["paper_id"], m) for m in all_methods
                     if m["validation_status"] == "rejected"]

    def _wcsv(path, fields, rows):
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for row in rows:
                w.writerow({k: _j(row.get(k)) for k in fields})

    _wcsv(config.STAGE_A_TEST_02_METHODS_ACCEPTED, METHOD_CSV_FIELDS, accepted_rows)
    _wcsv(config.STAGE_A_TEST_02_METHODS_CANDIDATE, METHOD_CSV_FIELDS, candidate_rows)
    _wcsv(config.STAGE_A_TEST_02_METHODS_REJECTED, METHOD_CSV_FIELDS, rejected_rows)
    _wcsv(config.STAGE_A_TEST_02_PER_PAPER_CSV, PER_PAPER_FIELDS, per_paper_rows)

    # ---- extraction manifest ----
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
        "pricing_assumed": {
            "input_cny_per_1M_tokens": KIMI_K2_INPUT_PRICE_CNY_PER_M,
            "output_cny_per_1M_tokens": KIMI_K2_OUTPUT_PRICE_CNY_PER_M,
            "note": "Kimi K2 参考价. 实际以官方账单为准.",
        },
        "estimated_total_cost_cny": round(total_cost, 4),
        "budget_hard_stop_cny": BUDGET_HARD_STOP_CNY,
        "outputs": {
            "methods_raw": config.relative_path(config.STAGE_A_TEST_02_METHODS_RAW),
            "methods_accepted": config.relative_path(config.STAGE_A_TEST_02_METHODS_ACCEPTED),
            "methods_candidate": config.relative_path(config.STAGE_A_TEST_02_METHODS_CANDIDATE),
            "methods_rejected": config.relative_path(config.STAGE_A_TEST_02_METHODS_REJECTED),
            "per_paper_summary": config.relative_path(config.STAGE_A_TEST_02_PER_PAPER_CSV),
        },
    }
    with open(config.STAGE_A_TEST_02_MANIFEST_JSON, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    # ---- validation report ----
    match_status_counter = Counter(m["evidence_match_status"] for m in all_methods)
    status_counter = Counter(m["validation_status"] for m in all_methods)
    reject_reason_counter = Counter()
    for m in all_methods:
        if m["validation_status"] == "rejected":
            for r in (m["rejected_reason"] or "").split(","):
                r = r.strip()
                if r:
                    reject_reason_counter[r] += 1
    own_no_own = [r for r in per_paper_rows
                  if r.get("paper_type") == "research_article" and r.get("own_count") == 0]
    json_fail_papers = [r for r in per_paper_rows if r.get("json_parse_ok") is False]
    exact_rate = (
        match_status_counter.get("exact", 0)
        / max(sum(match_status_counter.values()), 1)
    )
    normalized_rate = (
        match_status_counter.get("normalized_exact", 0)
        / max(sum(match_status_counter.values()), 1)
    )
    # 疑似材料/表征/宽泛在 rejected 里的抽样
    suspect_material = [m for m in all_methods
                        if "looks_like_material_only" in (m["rejected_reason"] or "")]
    suspect_charac = [m for m in all_methods
                      if "looks_like_characterization" in (m["rejected_reason"] or "")]
    suspect_vague = [m for m in all_methods
                     if "looks_vague" in (m["rejected_reason"] or "")]

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
        "exact_rate": round(exact_rate, 4),
        "normalized_exact_rate": round(normalized_rate, 4),
        "reject_reasons": dict(reject_reason_counter),
        "research_articles_with_zero_own": [r["paper_id"] for r in own_no_own],
        "json_parse_failed_papers": [r["paper_id"] for r in json_fail_papers],
        "suspect_material_only_examples": [
            {"paper_id": m["paper_id"], "name": m["name"]}
            for m in suspect_material[:10]
        ],
        "suspect_characterization_examples": [
            {"paper_id": m["paper_id"], "name": m["name"]}
            for m in suspect_charac[:10]
        ],
        "suspect_vague_examples": [
            {"paper_id": m["paper_id"], "name": m["name"]}
            for m in suspect_vague[:10]
        ],
        "actual_api_calls": total_calls,
        "actual_cost_cny": round(total_cost, 4),
    }
    with open(config.STAGE_A_TEST_02_VALIDATION_JSON, "w", encoding="utf-8") as f:
        json.dump(val_report, f, ensure_ascii=False, indent=2)

    # ---- validation MD ----
    ml = []
    ml.append("# Stage A 抽取校验报告 (test_run_02_stage_a)\n")
    ml.append(
        f"> 运行时间: {started_iso} · 耗时 {round(dur, 1)}s\n"
        f"> 模型: `{model}` · endpoint: `{llm_client.MOONSHOT_API_URL}`\n"
        f"> 论文: 10 · API 调用: **{total_calls}** / 上限 {max_calls}\n"
        f"> 实际 tokens: prompt={total_usage['prompt_tokens']} / "
        f"completion={total_usage['completion_tokens']} / "
        f"total={total_usage['total_tokens']}\n"
        f"> 预算(Kimi K2 参考价): **¥{round(total_cost, 3)}** (预算上限 ¥{BUDGET_HARD_STOP_CNY})\n\n"
    )
    ml.append("## 汇总\n")
    ml.append(f"- 抽取方法总数: **{len(all_methods)}**\n")
    ml.append(f"  - own_methods: {val_report['totals']['own_methods']}\n")
    ml.append(f"  - referenced_methods: {val_report['totals']['referenced_methods']}\n")
    ml.append(f"- 状态分布:\n")
    ml.append(f"  - accepted: **{val_report['totals']['accepted']}**\n")
    ml.append(f"  - candidate: {val_report['totals']['candidate']}\n")
    ml.append(f"  - rejected: {val_report['totals']['rejected']}\n")
    ml.append(f"- 证据匹配:\n")
    ml.append(f"  - exact:            {match_status_counter.get('exact', 0)}\n")
    ml.append(f"  - normalized_exact: {match_status_counter.get('normalized_exact', 0)}\n")
    ml.append(f"  - not_found:        {match_status_counter.get('not_found', 0)}\n")
    ml.append(f"  - exact 率:            {round(exact_rate * 100, 1)}%\n")
    ml.append(f"  - normalized_exact 率: {round(normalized_rate * 100, 1)}%\n")
    ml.append(f"- JSON 解析失败论文数: {len(val_report['json_parse_failed_papers'])}\n")
    ml.append(f"- research 却 own=0 的论文数: {len(val_report['research_articles_with_zero_own'])}\n")

    if reject_reason_counter:
        ml.append("\n## 拒绝原因分布\n| reason | count |\n|---|---:|\n")
        for k, v in sorted(reject_reason_counter.items(), key=lambda kv: -kv[1]):
            ml.append(f"| `{k}` | {v} |\n")

    ml.append("\n## 每篇 own / ref / accepted / candidate / rejected\n")
    ml.append("| # | paper_id | pt | own | ref | acc | cand | rej | calls | tokens | cost¥ |\n"
              "|--:|---|---|--:|--:|--:|--:|--:|--:|--:|--:|\n")
    for i, r in enumerate(per_paper_rows, 1):
        ml.append(
            f"| {i} | `{r['paper_id'][:36]}` | {r.get('paper_type','')[:6]} "
            f"| {r.get('own_count', 0)} | {r.get('referenced_count', 0)} "
            f"| {r.get('accepted_count', 0)} | {r.get('candidate_count', 0)} "
            f"| {r.get('rejected_count', 0)} | {r.get('call_count', 0)} "
            f"| {r.get('total_tokens', 0)} | {r.get('estimated_cost_cny', 0)} |\n"
        )

    if val_report["research_articles_with_zero_own"]:
        ml.append("\n## research_article 但 own=0 的论文\n")
        for pid in val_report["research_articles_with_zero_own"]:
            ml.append(f"- `{pid}`\n")

    if val_report["json_parse_failed_papers"]:
        ml.append("\n## JSON 解析失败的论文\n")
        for pid in val_report["json_parse_failed_papers"]:
            ml.append(f"- `{pid}`\n")

    ml.append("\n## 疑似材料名 / 表征 / 宽泛概念 (rejected 中的样本)\n")
    ml.append(f"- 疑似材料名: {len(suspect_material)}\n")
    for m in suspect_material[:15]:
        ml.append(f"  - `{m['paper_id']}` → name={m['name']!r}\n")
    ml.append(f"- 疑似表征手段: {len(suspect_charac)}\n")
    for m in suspect_charac[:15]:
        ml.append(f"  - `{m['paper_id']}` → name={m['name']!r}\n")
    ml.append(f"- 宽泛概念: {len(suspect_vague)}\n")
    for m in suspect_vague[:15]:
        ml.append(f"  - `{m['paper_id']}` → name={m['name']!r}\n")

    with open(config.STAGE_A_TEST_02_VALIDATION_MD, "w", encoding="utf-8") as f:
        f.writelines(ml)

    print()
    print("=" * 70)
    print(f"Stage A done: {n_papers} papers, {total_calls} API calls, "
          f"~¥{round(total_cost, 3)}, duration {round(dur, 1)}s")
    print(f"outputs: {config.relative_path(config.STAGE_A_TEST_02_DIR)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
