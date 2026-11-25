"""run_stage_a_full.py — Stage A 全量 337 篇 CLI.

命令形态 (spec 四):
  # dry-run: 预检 + 预算, 零 API 调用
  python -m src.graph_rag.method_evolution_v2.run_stage_a_full --dry-run

  # 只跑批次 1 (25 篇), 结束停止不进入下一批
  python -m ... --batch 1

  # 全部批次连跑
  python -m ... --continue-all

  # 只跑失败的
  python -m ... --retry-failed

  # 单篇 (用于调试)
  python -m ... --paper-id "全钒液流电池电堆的均一性"

  # 全局最大篇数上限
  python -m ... --batch 1 --max 5

  # 覆盖 batch size
  python -m ... --batch 1 --batch-size 10

严格约束:
  - --dry-run 保证 0 API 调用
  - key 只从 MOONSHOT_API_KEY 环境变量读
  - resume: 已成功 且 (SHA256 + prompt_version + model) 一致 → skip
  - 单篇失败继续, 记 failed_papers.csv
  - JSON 失败每篇最多 1 次重试
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

from method_evolution_v2 import config                                        # noqa: E402
from method_evolution_v2.stage_a import (                                     # noqa: E402
    full_runner as fr,
    recovery_runner as rr,
    budget_estimator as be,
    preflight as pf,
    llm_client,
)
from method_evolution_v2.stage_a import prompts as prompts_mod                # noqa: E402
from method_evolution_v2.stage_a.method_extraction import parse_llm_json      # noqa: E402


DEFAULT_BATCH_SIZE = fr.DEFAULT_BATCH_SIZE


def build_arg_parser():
    p = argparse.ArgumentParser(
        description="Stage A full-corpus runner (337 papers, resumable)")
    mode = p.add_mutually_exclusive_group(required=False)
    mode.add_argument("--dry-run", action="store_true",
                        help="Preflight + budget only, ZERO API calls")
    mode.add_argument("--batch", type=int, default=None,
                        help="Run only batch N (1-indexed). Stops after batch.")
    mode.add_argument("--continue-all", action="store_true",
                        help="Run ALL batches sequentially")
    mode.add_argument("--retry-failed", action="store_true",
                        help="Rerun papers from failed_papers.csv only")
    mode.add_argument("--paper-id", type=str, default=None,
                        help="Run one specific paper_id (for debug)")
    mode.add_argument("--paper-ids-file", type=str, default=None,
                        help="File with one paper_id per line; run only those")

    p.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE,
                    help=f"Papers per batch (default {DEFAULT_BATCH_SIZE})")
    p.add_argument("--max", type=int, default=None,
                    help="Global cap on number of papers processed")
    p.add_argument("--model", type=str, default=None,
                    help="Override MOONSHOT_MODEL env var")
    p.add_argument("--budget-hard-stop", type=float, default=20.0,
                    help="Halt if per-batch est cost exceeds this (CNY)")
    return p


def load_all_paper_ids() -> list:
    """从 corpus_preprocess_v1_1 sections 目录列出全部 337 paper_id (sorted)."""
    d = config.CORPUS_PP_V1_1_SECTIONS_DIR
    if not os.path.isdir(d):
        return []
    ids = [f[:-len(".json")] for f in os.listdir(d) if f.endswith(".json")]
    return sorted(ids)


def load_context_maps():
    """加载 canonical_titles / paper_types / taxonomy 三张表."""
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


def build_run_spec(paper_id, ctitles, ptypes, tax_rows) -> fr.RunSpec:
    tax_r = tax_rows.get(paper_id, {})
    try:
        apps = json.loads(tax_r.get("application_contexts", "[]"))
    except Exception:
        apps = []
    return fr.RunSpec(
        paper_id=paper_id,
        canonical_title=ctitles.get(paper_id, ""),
        paper_type=ptypes.get(paper_id, "unclear"),
        primary_storage_domain=tax_r.get("primary_storage_domain", ""),
        technology_subfield=tax_r.get("technology_subfield", ""),
        application_contexts=apps,
        paper_context_status=tax_r.get("paper_context_status", ""),
    )


# ============================================================
# Dry-run: preflight + budget
# ============================================================

def run_dry_run(paper_ids, batch_size, model) -> int:
    """0 API 调用. 只做 preflight + budget 估算 + batches 写盘."""
    os.makedirs(config.STAGE_A_FULL_V1_DIR, exist_ok=True)
    os.makedirs(config.STAGE_A_FULL_V1_CHECKPOINTS_DIR, exist_ok=True)

    print("=" * 70)
    print(f"Stage A full v1 DRY-RUN — model={model} batch_size={batch_size}")
    print(f"  papers scanned: {len(paper_ids)}")
    print("=" * 70)

    # ---- run_config.json ----
    with open(config.STAGE_A_FULL_V1_RUN_CONFIG_JSON, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "n_papers": len(paper_ids),
            "batch_size": batch_size,
            "model_configured": model,
            "prompt_version": prompts_mod.PROMPT_VERSION,
            "stage_a_engine_version": fr.STAGE_A_FULL_VERSION,
            "moonshot_api_url": llm_client.MOONSHOT_API_URL,
            "moonshot_api_key_source": "env:MOONSHOT_API_KEY (checked at runtime, not stored)",
        }, f, ensure_ascii=False, indent=2)

    # ---- batches.csv + paper_id_to_dir.csv ----
    fr.write_batches_csv(paper_ids, batch_size,
                          config.STAGE_A_FULL_V1_BATCHES_CSV)
    fr.write_paper_id_map(paper_ids,
                            config.STAGE_A_FULL_V1_PAPER_ID_MAP_CSV)

    # ---- Pre-flight (质量检查) ----
    print("\nRunning preflight quality checks (no API)...")
    preflight_result = pf.run_preflight(paper_ids)
    with open(config.STAGE_A_FULL_V1_PREFLIGHT_JSON, "w", encoding="utf-8") as f:
        json.dump(preflight_result, f, ensure_ascii=False, indent=2)

    # Preflight MD
    _write_preflight_md(preflight_result,
                         config.STAGE_A_FULL_V1_PREFLIGHT_MD)

    print(f"  preflight summary: {preflight_result['summary']}")

    # ---- Budget estimate ----
    print("\nComputing budget estimate (three modes)...")
    per_paper_chars = [entry.get("pack_char_count", 0)
                        for entry in preflight_result["per_paper"]]
    n_papers = len(per_paper_chars)
    report = be.build_budget_report(per_paper_chars, n_papers=n_papers,
                                      batch_size=batch_size, model=model)
    with open(config.STAGE_A_FULL_V1_BUDGET_JSON, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # ---- 综合 manifest ----
    manifest = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "phase": "dry_run",
        "n_papers": len(paper_ids),
        "n_batches": (len(paper_ids) + batch_size - 1) // batch_size,
        "batch_size": batch_size,
        "model": model,
        "prompt_version": prompts_mod.PROMPT_VERSION,
        "outputs": {
            "batches_csv": config.relative_path(config.STAGE_A_FULL_V1_BATCHES_CSV),
            "preflight_json": config.relative_path(config.STAGE_A_FULL_V1_PREFLIGHT_JSON),
            "budget_json": config.relative_path(config.STAGE_A_FULL_V1_BUDGET_JSON),
            "run_config_json": config.relative_path(config.STAGE_A_FULL_V1_RUN_CONFIG_JSON),
        },
    }
    with open(config.STAGE_A_FULL_V1_MANIFEST_JSON, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    # ---- 打印摘要 ----
    print()
    print("=" * 70)
    print(f"DRY-RUN complete. NO API calls made.")
    print(f"  n_papers: {n_papers}")
    print(f"  n_batches: {manifest['n_batches']}")
    print(f"  issues_count: {preflight_result['summary']['issues_count']}")
    print()
    print("Budget estimates:")
    for k, v in report["estimates"].items():
        cost = v.get("estimated_total_cost_cny", "n/a")
        print(f"  {k}: ¥{cost}")
    print()
    print(f"Outputs: {config.relative_path(config.STAGE_A_FULL_V1_DIR)}")
    print("Use --batch 1 to actually run batch 1 (WILL call API).")
    return 0


def _write_preflight_md(preflight, path):
    s = preflight["summary"]
    md = []
    md.append("# Stage A Full v1 Preflight Report\n\n")
    md.append(f"> Generated: {datetime.now().isoformat(timespec='seconds')}\n\n")
    md.append("## Summary\n")
    md.append(f"- Papers scanned: {s['n_papers_input']}\n")
    md.append(f"- Missing full.md: {s['n_missing_full_md']}\n")
    md.append(f"- Missing sections JSON: {s['n_missing_sections_json']}\n")
    md.append(f"- Empty sentence index: {s['n_empty_input']}\n")
    md.append(f"- Sentence-ID duplicates (papers): {s['n_sentence_id_dup_papers']}\n")
    md.append(f"- Slice-mismatch papers: {s['n_slice_mismatch_papers']}\n")
    md.append(f"- Papers over 128k tokens: {s['n_over_context_tokens_papers']}\n")
    md.append(f"- Missing canonical_title: {s['n_missing_canonical_title']}\n")
    md.append(f"- Missing paper_type: {s['n_missing_paper_type']}\n")
    md.append(f"- Missing taxonomy row: {s['n_missing_taxonomy']}\n")
    md.append(f"- Total sentences: {s['total_sentences']}\n")
    md.append(f"- Avg sentences/paper: {round(s['avg_sentences_per_paper'], 1)}\n")
    md.append(f"- Avg pack chars/paper: {round(s['avg_pack_chars_per_paper'], 0)}\n")
    if s["papers_over_128k_tokens_list"]:
        md.append(f"\n### Over-context papers\n")
        for pid in s["papers_over_128k_tokens_list"]:
            md.append(f"- `{pid}`\n")

    md.append(f"\n## Issues ({s['issues_count']})\n")
    if not preflight["issues"]:
        md.append("- None\n")
    else:
        issue_counter = Counter(issue[1].split(":", 1)[0]
                                 for issue in preflight["issues"])
        for k, v in issue_counter.most_common():
            md.append(f"- `{k}`: {v}\n")

    with open(path, "w", encoding="utf-8") as f:
        f.writelines(md)


# ============================================================
# 真实运行 (--batch / --continue-all / --retry-failed / --paper-id)
# ============================================================

class _AuthenticationError(RuntimeError):
    """LLM 认证异常, 立即中断整批."""


class _Consecutive429Stop(RuntimeError):
    """连续 5 次请求 429, 立即中断整批 (spec 三)."""


class _RateLimitFinalError(RuntimeError):
    """同一篇 4 次 429 重试后仍失败 (spec 三)."""


def _run_papers_live(paper_ids, ctitles, ptypes, tax_rows, model,
                       batch_num=0, hard_stop=20.0,
                       consecutive_failure_limit=3) -> int:
    """真实调用 LLM 跑一批 paper_ids. 需要 MOONSHOT_API_KEY.

    安全阀:
      - 预算 > hard_stop → 立即停
      - 连续 consecutive_failure_limit 篇失败 → 立即停
      - HTTP 401/403 (认证异常) → 立即停
    """
    # spec 七: 启动日志只输出 configured yes/no; 不打印长度/前缀/后缀
    try:
        _ = llm_client.get_api_key()
        print("MOONSHOT_API_KEY configured: yes")
    except RuntimeError:
        print("MOONSHOT_API_KEY configured: no")
        return 2

    # spec 三: 429 追踪只在 "论文粒度" 追加 consec_papers_429 → 5 才停
    # 单篇内部的 4 次 429 重试不触发全局 stop (由 per-paper _RateLimitFinalError 触发)
    global_state = {"consec_papers_429": 0, "total_429": 0}

    def _observe_429(_attempt):
        global_state["total_429"] += 1
        return False   # 从不请求 backoff 提前退出

    def _caller(sys_prompt, user_prompt, model=None):
        r = llm_client.call_chat_with_backoff(
            sys_prompt, user_prompt, model=model,
            on_429_response=_observe_429)
        usage = r.get("usage") or {}
        err_type = r.get("error_type", "")
        # 认证异常仍立即停
        if err_type == llm_client.ERROR_AUTH:
            raise _AuthenticationError(r.get("error", ""))
        # 4 次 429 后仍失败 → per-paper fatal (spec 三)
        if err_type == llm_client.ERROR_RATE_LIMIT:
            global_state["consec_papers_429"] += 1
            if global_state["consec_papers_429"] >= 5:
                raise _Consecutive429Stop(
                    f"5 consecutive papers hit final 429 failure")
            raise _RateLimitFinalError(
                f"paper hit 4x 429 backoff and still failed: "
                f"{r.get('error','')}")
        if not r["ok"]:
            return {}, False, r.get("error", ""), usage, ""
        # 成功: 重置连续 429 论文计数
        global_state["consec_papers_429"] = 0
        text = r.get("text", "")
        ok, obj, err = parse_llm_json(text)
        if not ok:
            return {}, False, err, usage, text
        return obj, True, "", usage, text

    total_cost_est = 0.0
    n_processed = 0
    n_ok = 0
    n_skipped = 0
    n_revalidated = 0
    n_failed = 0
    n_recovery_ran = 0
    n_recovery_success = 0
    consecutive_failures = 0

    for pid in paper_ids:
        md_path = config.full_md_path(pid)
        if not os.path.isfile(md_path):
            fr.append_failed(pid, batch_num, "MissingFullMD",
                               f"full.md not found: {md_path}",
                               config.STAGE_A_FULL_V1_FAILED_CSV)
            n_failed += 1
            continue

        # 3-way resume dispatch
        spec = build_run_spec(pid, ctitles, ptypes, tax_rows)
        current_manifest = fr.build_input_manifest(pid, md_path, model)
        action, reason = fr.decide_run_action(pid, current_manifest)
        if action == "skip":
            fr.append_skipped(pid, batch_num, reason,
                                config.STAGE_A_FULL_V1_SKIPPED_CSV)
            n_skipped += 1
            print(f"  SKIP  {pid[:40]:<40} ({reason})")
            continue
        if action == "revalidate":
            # 本地重校验, 不烧钱
            try:
                result = fr.revalidate_one_paper(spec)
            except Exception as e:
                fr.append_failed(pid, batch_num,
                                    f"RevalidateError:{type(e).__name__}",
                                    str(e),
                                    config.STAGE_A_FULL_V1_FAILED_CSV)
                n_failed += 1
                consecutive_failures += 1
                print(f"  REVAL FAIL {pid[:40]} — {e}")
                continue
            n_revalidated += 1
            consecutive_failures = 0
            acc = len(result["methods_accepted"])
            cand = len(result["methods_candidate"])
            rej = len(result["methods_rejected"])
            # cost ledger: 记 0 cost, tag="revalidate_no_api"
            fr.append_cost_ledger({
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "paper_id": pid,
                "call_count": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "estimated_cost_cny": 0.0,
                "model": model + " (revalidate_no_api)",
            }, config.STAGE_A_FULL_V1_COST_LEDGER_CSV)
            print(f"  REVAL {pid[:40]:<40} acc={acc} cand={cand} rej={rej} "
                  f"({reason})")
            continue

        # action == "run_api"
        try:
            result = fr.run_one_paper(spec, md_path, _caller, model=model)
        except _AuthenticationError as e:
            fr.append_failed(pid, batch_num, "authentication_error",
                               str(e), config.STAGE_A_FULL_V1_FAILED_CSV)
            n_failed += 1
            print(f"  AUTH FAIL {pid[:40]} — {e}")
            print(f"  AUTHENTICATION EXCEPTION: stopping batch immediately.")
            print(f"Batch {batch_num} halted: processed={n_processed} ok={n_ok} "
                  f"skipped={n_skipped} failed={n_failed} "
                  f"total_429={global_state['total_429']} "
                  f"est_cost=¥{round(total_cost_est, 3)}")
            return 3
        except _Consecutive429Stop as e:
            fr.append_failed(pid, batch_num, "rate_limit_429_streak",
                               str(e), config.STAGE_A_FULL_V1_FAILED_CSV)
            n_failed += 1
            print(f"  429 STREAK {pid[:40]} — {e}")
            print(f"Batch {batch_num} halted: processed={n_processed} ok={n_ok} "
                  f"skipped={n_skipped} failed={n_failed} "
                  f"total_429={global_state['total_429']} "
                  f"est_cost=¥{round(total_cost_est, 3)}")
            return 6
        except _RateLimitFinalError as e:
            fr.append_failed(pid, batch_num, "rate_limit_429",
                               str(e), config.STAGE_A_FULL_V1_FAILED_CSV)
            n_failed += 1
            consecutive_failures += 1
            print(f"  429 FAIL {pid[:40]} — {e}")
            # spec 三: 同一篇 4 次 429 后仍失败 → 立即停止后续
            print(f"Batch {batch_num} halted: processed={n_processed} ok={n_ok} "
                  f"skipped={n_skipped} failed={n_failed} "
                  f"total_429={global_state['total_429']} "
                  f"est_cost=¥{round(total_cost_est, 3)}")
            return 7
        except Exception as e:
            import traceback
            fr.append_failed(pid, batch_num, "network_error",
                               str(e) + "\n" + traceback.format_exc(),
                               config.STAGE_A_FULL_V1_FAILED_CSV)
            n_failed += 1
            consecutive_failures += 1
            print(f"  FAIL {pid[:40]} — {type(e).__name__}: {e}")
            if consecutive_failures >= consecutive_failure_limit:
                print(f"  CONSECUTIVE FAILURES = {consecutive_failures}, "
                      f"stopping batch immediately.")
                print(f"Batch {batch_num} halted: processed={n_processed} ok={n_ok} "
                      f"skipped={n_skipped} failed={n_failed} "
                      f"total_429={global_state['total_429']} "
                      f"est_cost=¥{round(total_cost_est, 3)}")
                return 4
            continue

        # cost ledger
        pt = result["usage_total"].get("prompt_tokens", 0)
        ct = result["usage_total"].get("completion_tokens", 0)
        est = be.per_paper_cost_estimate(pt, ct)
        cost_cny = est["cost_cny"]
        total_cost_est += cost_cny
        fr.append_cost_ledger({
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "paper_id": pid,
            "call_count": result["call_count"],
            "prompt_tokens": pt,
            "completion_tokens": ct,
            "total_tokens": result["usage_total"].get("total_tokens", 0),
            "estimated_cost_cny": round(cost_cny, 6),
            "model": model,
        }, config.STAGE_A_FULL_V1_COST_LEDGER_CSV)

        n_processed += 1
        n_ok += 1
        acc = len(result["methods_accepted"])
        cand = len(result["methods_candidate"])
        rej = len(result["methods_rejected"])

        # spec 一: 主 Stage A 成功后, 自动触发 Recovery (research+own=0)
        # 每篇最多 1 次: manifest.recovery_used 兜底
        try:
            prev_manifest = fr.load_previous_input_manifest(pid) or {}
            if (result["json_parse_ok"]
                    and fr.paper_needs_recovery(spec.paper_type,
                                                     result["methods_accepted"],
                                                     prev_manifest)):
                try:
                    rec_result = rr.run_recovery_one_paper(
                        spec, md_path, _caller, model=model,
                        write_output=False)   # 不写 recovery 独立目录
                    merged = fr.merge_recovery_into_paper(pid, rec_result)
                    rec_pt = rec_result["usage_total"].get("prompt_tokens", 0)
                    rec_ct = rec_result["usage_total"].get("completion_tokens", 0)
                    rec_est = be.per_paper_cost_estimate(rec_pt, rec_ct)
                    rec_cost = rec_est["cost_cny"]
                    total_cost_est += rec_cost
                    fr.append_cost_ledger({
                        "timestamp": datetime.now().isoformat(timespec="seconds"),
                        "paper_id": pid,
                        "call_count": rec_result["call_count"],
                        "prompt_tokens": rec_pt,
                        "completion_tokens": rec_ct,
                        "total_tokens": rec_result["usage_total"].get(
                            "total_tokens", 0),
                        "estimated_cost_cny": round(rec_cost, 6),
                        "model": model + " (recovery)",
                    }, config.STAGE_A_FULL_V1_COST_LEDGER_CSV)
                    acc = merged["n_accepted"]
                    cand = merged["n_candidate"]
                    rej = merged["n_rejected"]
                    n_recovery_ran += 1
                    if merged["n_accepted"] > len(result["methods_accepted"]):
                        n_recovery_success += 1
                    print(f"       RECOVERY: added acc/cand/rej now "
                          f"{acc}/{cand}/{rej} cost=¥{round(rec_cost, 4)}")
                except _AuthenticationError as e:
                    raise
                except Exception as e:
                    print(f"       RECOVERY FAIL (non-fatal): {type(e).__name__}: {e}")
        except _AuthenticationError:
            raise
        except Exception as e:
            print(f"       recovery-check failed: {e}")
        # 判定是否算"有效产出"用来重置连续失败计数
        no_useful_output = (
            not result["json_parse_ok"]
            and acc == 0 and cand == 0 and rej == 0
        )
        if no_useful_output:
            consecutive_failures += 1
            if consecutive_failures >= consecutive_failure_limit:
                print(f"  NO USEFUL OUTPUT — CONSECUTIVE = {consecutive_failures}, "
                      f"stopping batch immediately.")
                print(f"Batch {batch_num} halted: processed={n_processed} ok={n_ok} "
                      f"skipped={n_skipped} failed={n_failed} "
                      f"est_cost=¥{round(total_cost_est, 3)}")
                return 4
        else:
            consecutive_failures = 0
        print(f"  OK   {pid[:40]:<40} acc={acc} cand={cand} rej={rej} "
              f"tokens={result['usage_total'].get('total_tokens', 0)} "
              f"cost=¥{round(cost_cny, 4)}")

        if total_cost_est > hard_stop:
            print(f"BUDGET HARD STOP: total est cost ¥{total_cost_est:.2f} "
                  f"> ¥{hard_stop:.2f}. Stopping batch.")
            break

    print()
    print(f"Batch {batch_num} done: processed={n_processed} ok={n_ok} "
          f"revalidated={n_revalidated} skipped={n_skipped} "
          f"failed={n_failed} recovery_ran={n_recovery_ran} "
          f"recovery_success={n_recovery_success} "
          f"total_429={global_state['total_429']} "
          f"est_cost=¥{round(total_cost_est, 3)}")
    return 0


def _load_failed_paper_ids() -> list:
    p = config.STAGE_A_FULL_V1_FAILED_CSV
    if not os.path.isfile(p):
        return []
    out = []
    with open(p, "r", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            pid = r.get("paper_id", "")
            if pid and pid not in out:
                out.append(pid)
    return out


# ============================================================
# main
# ============================================================

def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    args = build_arg_parser().parse_args()
    model = args.model or os.environ.get("MOONSHOT_MODEL", fr.DEFAULT_MODEL)
    batch_size = args.batch_size

    all_ids = load_all_paper_ids()
    if not all_ids:
        print("ERROR: no paper_ids found in corpus_preprocess_v1_1/sections")
        return 2

    ctitles, ptypes, tax_rows = load_context_maps()

    if args.dry_run:
        return run_dry_run(all_ids, batch_size, model)

    # 选定要跑的 paper_ids
    if args.paper_id:
        selected = [args.paper_id]
    elif args.paper_ids_file:
        with open(args.paper_ids_file, "r", encoding="utf-8") as f:
            selected = [line.strip() for line in f
                          if line.strip() and not line.startswith("#")]
        if not selected:
            print("No paper_ids in file.")
            return 0
    elif args.retry_failed:
        selected = _load_failed_paper_ids()
        if not selected:
            print("No failed papers to retry.")
            return 0
    elif args.batch is not None:
        batches = fr.compute_batches(all_ids, batch_size)
        if args.batch < 1 or args.batch > len(batches):
            print(f"ERROR: batch must be 1..{len(batches)}")
            return 2
        selected = batches[args.batch - 1]
    elif args.continue_all:
        selected = all_ids
    else:
        print("Must specify one of: --dry-run, --batch N, --continue-all, "
                "--retry-failed, --paper-id ID")
        return 2

    if args.max:
        selected = selected[:args.max]

    os.makedirs(config.STAGE_A_FULL_V1_DIR, exist_ok=True)
    os.makedirs(config.STAGE_A_FULL_V1_PER_PAPER_DIR, exist_ok=True)
    os.makedirs(config.STAGE_A_FULL_V1_CHECKPOINTS_DIR, exist_ok=True)

    batch_label = args.batch if args.batch is not None else 0
    return _run_papers_live(selected, ctitles, ptypes, tax_rows,
                              model=model, batch_num=batch_label,
                              hard_stop=args.budget_hard_stop)


if __name__ == "__main__":
    sys.exit(main())
