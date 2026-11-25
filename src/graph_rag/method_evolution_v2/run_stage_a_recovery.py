"""run_stage_a_recovery.py — Stage A 缺 own 补救测试 CLI (spec 五).

命令:
  python -m src.graph_rag.method_evolution_v2.run_stage_a_recovery \
      --budget-hard-stop 10

严格约束:
  - 只跑 batch 1 + 2 中 research_article 且 accepted own = 0 的论文
  - 每篇最多 1 次 API 调用, 不循环重试
  - 输出到 STAGE_A_RECOVERY_TEST_V1_DIR, 不覆盖 STAGE_A_FULL_V1 里任何东西
  - 认证异常 / 连续 3 篇失败 / 超预算 → 立即停
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_GRAPH_RAG_DIR = os.path.dirname(THIS_DIR)
if SRC_GRAPH_RAG_DIR not in sys.path:
    sys.path.insert(0, SRC_GRAPH_RAG_DIR)

from method_evolution_v2 import config                                     # noqa: E402
from method_evolution_v2.stage_a import (                                   # noqa: E402
    full_runner as fr,
    recovery_runner as rr,
    budget_estimator as be,
    llm_client,
)
from method_evolution_v2.stage_a.method_extraction import parse_llm_json    # noqa: E402


class _AuthenticationError(RuntimeError):
    pass


def build_arg_parser():
    p = argparse.ArgumentParser(
        description="Stage A recovery for research_article with no accepted own")
    p.add_argument("--budget-hard-stop", type=float, default=10.0,
                    help="Halt if total est cost exceeds this (CNY). Default 10.")
    p.add_argument("--model", type=str, default=None,
                    help="Override MOONSHOT_MODEL env var")
    p.add_argument("--max", type=int, default=None,
                    help="Cap on number of candidates processed")
    p.add_argument("--dry-run", action="store_true",
                    help="List candidates only, no API calls")
    return p


def load_context_maps():
    ctitles = {}
    ct_path = os.path.join(config.CORPUS_PP_V1_1_DIR, "canonical_titles.csv")
    if os.path.isfile(ct_path):
        with open(ct_path, "r", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                ctitles[r["paper_id"]] = r.get("canonical_title", "")
    ptypes = {}
    if os.path.isfile(config.CORPUS_PP_V1_1_PAPER_TYPES_CSV):
        with open(config.CORPUS_PP_V1_1_PAPER_TYPES_CSV, "r",
                    encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                ptypes[r["paper_id"]] = r.get("paper_type", "")
    tax = {}
    if os.path.isfile(config.CORPUS_PP_V1_1_PAPER_TAXONOMY_CSV):
        with open(config.CORPUS_PP_V1_1_PAPER_TAXONOMY_CSV, "r",
                    encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                tax[r["paper_id"]] = r
    return ctitles, ptypes, tax


def build_spec(pid, ctitles, ptypes, tax_rows):
    tr = tax_rows.get(pid, {})
    try:
        apps = json.loads(tr.get("application_contexts", "[]"))
    except Exception:
        apps = []
    return fr.RunSpec(
        paper_id=pid,
        canonical_title=ctitles.get(pid, ""),
        paper_type=ptypes.get(pid, "unclear"),
        primary_storage_domain=tr.get("primary_storage_domain", ""),
        technology_subfield=tr.get("technology_subfield", ""),
        application_contexts=apps,
        paper_context_status=tr.get("paper_context_status", ""),
    )


def write_candidates_csv(candidates, path):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["paper_id", "paper_id_hash"])
        w.writeheader()
        for pid in candidates:
            w.writerow({"paper_id": pid,
                          "paper_id_hash": fr.paper_id_to_dir_name(pid)})


def append_cost_row(row, path):
    fields = ["timestamp", "paper_id", "call_count",
              "prompt_tokens", "completion_tokens", "total_tokens",
              "estimated_cost_cny", "model"]
    new_file = not os.path.isfile(path)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if new_file:
            w.writeheader()
        w.writerow({k: row.get(k, "") for k in fields})


def append_failed_row(pid, err_type, err_msg, path):
    fields = ["paper_id", "attempted_at", "error_type", "error_message"]
    new_file = not os.path.isfile(path)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if new_file:
            w.writeheader()
        w.writerow({
            "paper_id": pid,
            "attempted_at": datetime.now().isoformat(timespec="seconds"),
            "error_type": err_type,
            "error_message": (err_msg or "")[:2000],
        })


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    args = build_arg_parser().parse_args()
    model = args.model or os.environ.get("MOONSHOT_MODEL", fr.DEFAULT_MODEL)

    ctitles, ptypes, tax_rows = load_context_maps()

    candidates = rr.find_recovery_candidates(
        ptypes,
        config.STAGE_A_FULL_V1_BATCHES_CSV,
        config.STAGE_A_FULL_V1_PER_PAPER_DIR,
        allowed_batches=("1", "2"),
    )
    if args.max:
        candidates = candidates[:args.max]

    os.makedirs(config.STAGE_A_RECOVERY_TEST_V1_DIR, exist_ok=True)
    os.makedirs(config.STAGE_A_RECOVERY_TEST_V1_PER_PAPER_DIR, exist_ok=True)
    write_candidates_csv(candidates,
                            config.STAGE_A_RECOVERY_TEST_V1_CANDIDATES_CSV)

    print("=" * 70)
    print(f"Stage A RECOVERY test v1 — model={model}")
    print(f"  candidates (research_article + own_accepted=0): {len(candidates)}")
    for pid in candidates:
        print(f"    - {pid}")
    print("=" * 70)
    print()

    if args.dry_run:
        print("DRY-RUN: no API calls made.")
        return 0

    # spec 七: 启动日志只输出 configured yes/no; 不打印长度/前缀/后缀
    try:
        _ = llm_client.get_api_key()
        print("MOONSHOT_API_KEY configured: yes")
    except RuntimeError:
        print("MOONSHOT_API_KEY configured: no")
        return 2

    def caller(sys_prompt, user_prompt, model=None):
        r = llm_client.call_chat(sys_prompt, user_prompt, model=model)
        usage = r.get("usage") or {}
        if not r["ok"]:
            err = r.get("error", "") or ""
            if ("http_status=401" in err or "http_status=403" in err
                    or "invalid_authentication" in err.lower()):
                raise _AuthenticationError(err)
            return {}, False, err, usage, ""
        text = r.get("text", "")
        ok, obj, err = parse_llm_json(text)
        if not ok:
            return {}, False, err, usage, text
        return obj, True, "", usage, text

    total_cost = 0.0
    n_ok = 0
    n_failed = 0
    consecutive_failures = 0

    for pid in candidates:
        md_path = config.full_md_path(pid)
        if not os.path.isfile(md_path):
            append_failed_row(pid, "MissingFullMD",
                                f"full.md not found: {md_path}",
                                config.STAGE_A_RECOVERY_TEST_V1_FAILED_CSV)
            n_failed += 1
            continue

        spec = build_spec(pid, ctitles, ptypes, tax_rows)
        try:
            result = rr.run_recovery_one_paper(spec, md_path, caller,
                                                    model=model)
        except _AuthenticationError as e:
            append_failed_row(pid, "AuthenticationError", str(e),
                                config.STAGE_A_RECOVERY_TEST_V1_FAILED_CSV)
            n_failed += 1
            print(f"  AUTH FAIL {pid[:40]} — {e}")
            print(f"  AUTHENTICATION EXCEPTION: stopping immediately.")
            return 3
        except Exception as e:
            import traceback
            append_failed_row(pid, type(e).__name__,
                                str(e) + "\n" + traceback.format_exc(),
                                config.STAGE_A_RECOVERY_TEST_V1_FAILED_CSV)
            n_failed += 1
            consecutive_failures += 1
            print(f"  FAIL {pid[:40]} — {type(e).__name__}: {e}")
            if consecutive_failures >= 3:
                print(f"  CONSECUTIVE FAILURES = {consecutive_failures}, stopping.")
                return 4
            continue

        pt = result["usage_total"].get("prompt_tokens", 0)
        ct = result["usage_total"].get("completion_tokens", 0)
        est = be.per_paper_cost_estimate(pt, ct)
        cost_cny = est["cost_cny"]
        total_cost += cost_cny
        append_cost_row({
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "paper_id": pid,
            "call_count": result["call_count"],
            "prompt_tokens": pt,
            "completion_tokens": ct,
            "total_tokens": result["usage_total"].get("total_tokens", 0),
            "estimated_cost_cny": round(cost_cny, 6),
            "model": model,
        }, config.STAGE_A_RECOVERY_TEST_V1_COST_LEDGER_CSV)

        n_ok += 1
        consecutive_failures = 0
        acc = len(result["methods_accepted"])
        cand = len(result["methods_candidate"])
        rej = len(result["methods_rejected"])
        print(f"  OK   {pid[:40]:<40} own_raw={result['n_own_raw']} "
                f"acc={acc} cand={cand} rej={rej} demoted={result['demoted_bare_generic_count']} "
                f"tokens={result['usage_total'].get('total_tokens', 0)} "
                f"cost=¥{round(cost_cny, 4)}")

        if total_cost > args.budget_hard_stop:
            print(f"BUDGET HARD STOP: ¥{total_cost:.2f} > "
                    f"¥{args.budget_hard_stop:.2f}. Stopping.")
            break

    print()
    print(f"Recovery done: ok={n_ok} failed={n_failed} "
            f"est_cost=¥{round(total_cost, 3)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
