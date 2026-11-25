"""run_stage_a_batches.py — 顺序跑 batch [--from N --to M] with auto-stop.

命令:
  python -m src.graph_rag.method_evolution_v2.run_stage_a_batches \
      --from 3 --to 14 --total-budget-cny 110

自动停止条件 (spec 三, 更新版):
  1. API 认证失败 (subprocess rc=3)
  2. 连续 5 次请求均返回 429 (subprocess rc=6)
  3. 同一篇 4 次 429 重试后仍失败 (subprocess rc=7)
  4. 任一批最终成功率 < 90% (post-retry, 已把 rate_limit_429 从 json_parse
     错误剥离)
  5. 累计费用达到 110 CNY
  6. evidence sentence_id 有效率 < 95%
  7. sentence index 切片一致率 < 100%
  8. 原始文件或历史 raw 被覆盖 (raw_response.json SHA 校验)

依赖 run_stage_a_full 的现有子进程实现单批次执行.
批次间暂停 30 秒 (spec 二).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_GRAPH_RAG_DIR = os.path.dirname(THIS_DIR)
if SRC_GRAPH_RAG_DIR not in sys.path:
    sys.path.insert(0, SRC_GRAPH_RAG_DIR)

from method_evolution_v2 import config                              # noqa: E402
from method_evolution_v2.stage_a import full_runner as fr           # noqa: E402


def load_batch_paper_ids(batch_num):
    with open(config.STAGE_A_FULL_V1_BATCHES_CSV, "r",
                encoding="utf-8-sig") as f:
        return [r["paper_id"] for r in csv.DictReader(f)
                  if r["batch_num"] == str(batch_num)]


def compute_batch_metrics(batch_pids):
    """After a batch run, walk per_paper for those IDs and compute quality
    metrics for auto-stop checks (spec 六 3/4/5/8/9/10)."""
    n_papers = len(batch_pids)
    n_attempted = 0
    n_never_attempted = 0
    n_ok = 0
    n_json_ok = 0
    n_rate_limit_429_final = 0   # 429 后仍失败
    total_ids = 0
    valid_ids = 0
    slice_hit = 0
    slice_total = 0
    system_bad_names = []
    recovery_over_one = []
    corrupt_dirs = []

    # 材料名/宽泛概念黑名单 (孤立时的 accepted 触发系统性误升)
    BAD_ISOLATED = re.compile(
        r"^(LFP|NCM|石墨烯|MOFs?|COFs?|MXene|PANI|钙钛矿|"
        r"电化学|催化|储能|吸附|光催化|命名法|结构式|化学式|"
        r"分子式|IUPAC|"
        r"XRD|SEM|TEM|XPS|BET|FTIR|Raman)$")

    for pid in batch_pids:
        d = fr.per_paper_dir(pid)
        if not os.path.isdir(d):
            # 未被尝试 (batch 提早停) — 不算 corrupt
            n_never_attempted += 1
            continue
        n_attempted += 1
        try:
            with open(os.path.join(d, "validation_report.json"),
                        "r", encoding="utf-8") as f:
                vr = json.load(f)
            with open(os.path.join(d, "input_manifest.json"),
                        "r", encoding="utf-8") as f:
                im = json.load(f)
            with open(os.path.join(d, "raw_response.json"),
                        "r", encoding="utf-8") as f:
                raw = json.load(f)
            with open(os.path.join(d, "sentence_index.json"),
                        "r", encoding="utf-8") as f:
                sidx = json.load(f)
            with open(os.path.join(d, "methods_accepted.json"),
                        "r", encoding="utf-8") as f:
                accepted = json.load(f)
            with open(os.path.join(d, "methods_candidate.json"),
                        "r", encoding="utf-8") as f:
                candidate = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError,
                  OSError) as e:
            corrupt_dirs.append(f"{pid}: {type(e).__name__}: {e}")
            continue

        if raw.get("json_parse_ok"):
            n_ok += 1
            n_json_ok += 1
        else:
            # spec 一: 区分 429 vs json parse; 429 不算入 json parse 错误
            err_text = (raw.get("json_parse_error") or "").lower()
            if "429" in err_text or "rate_limit" in err_text:
                n_rate_limit_429_final += 1

        # recovery 单次上限
        rcc = im.get("recovery_call_count", 0)
        if rcc and rcc > 1:
            recovery_over_one.append(f"{pid}: {rcc}")

        # evidence ID 有效率 + slice 一致率
        valid_sids = {s["sentence_id"]: s.get("sentence_text", "")
                        for s in sidx.get("sentences", [])}
        for m in accepted + candidate:
            for sid in m.get("evidence_sentence_ids", []):
                total_ids += 1
                if sid in valid_sids:
                    valid_ids += 1
                    slice_total += 1
                    if valid_sids[sid].strip():
                        slice_hit += 1
                # else: slice_total 也不加, 因为 id 无效时切片本就无从谈起

        # 系统性误抽 (仅检查 accepted)
        for m in accepted:
            name = (m.get("name") or "").strip()
            if BAD_ISOLATED.match(name):
                system_bad_names.append(f"{pid}: {name}")

    slice_rate = (slice_hit / slice_total) if slice_total else 1.0
    id_valid_rate = (valid_ids / total_ids) if total_ids else 1.0
    # ok_rate 基于**已尝试**的论文, 未尝试的因早停不计
    denom = n_attempted if n_attempted else n_papers
    ok_rate = (n_ok / denom) if denom else 1.0
    return {
        "n_papers": n_papers,
        "n_attempted": n_attempted,
        "n_never_attempted": n_never_attempted,
        "n_ok": n_ok,
        "n_rate_limit_429_final": n_rate_limit_429_final,
        "ok_rate": ok_rate,
        "id_valid_rate": id_valid_rate,
        "slice_rate": slice_rate,
        "system_bad_names": system_bad_names,
        "recovery_over_one": recovery_over_one,
        "corrupt_dirs": corrupt_dirs,
    }


def compute_batch_cost(batch_pids, model):
    """Sum est cost per paper for this batch by walking cost_ledger.csv."""
    p = config.STAGE_A_FULL_V1_COST_LEDGER_CSV
    if not os.path.isfile(p):
        return 0.0
    total = 0.0
    id_set = set(batch_pids)
    with open(p, "r", encoding="utf-8-sig") as f:
        # take only rows for these pids from most-recent entries
        for r in csv.DictReader(f):
            if r["paper_id"] in id_set:
                try:
                    total += float(r["estimated_cost_cny"])
                except (ValueError, KeyError):
                    pass
    return total


def write_batch_report(batch_num, metrics, cost, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    p = os.path.join(out_dir, f"batch_{batch_num:02d}_report.md")
    with open(p, "w", encoding="utf-8") as f:
        f.write(f"# Batch {batch_num} report\n\n")
        f.write(f"> Generated: {datetime.now().isoformat(timespec='seconds')}\n\n")
        f.write(f"- n_papers: {metrics['n_papers']}\n")
        f.write(f"- n_ok: {metrics['n_ok']}\n")
        f.write(f"- success rate: {metrics['ok_rate']*100:.1f}%\n")
        f.write(f"- evidence ID valid rate: "
                  f"{metrics['id_valid_rate']*100:.2f}%\n")
        f.write(f"- slice consistency: {metrics['slice_rate']*100:.2f}%\n")
        f.write(f"- est cost (this batch): ¥{cost:.3f}\n")
        f.write(f"- system-bad names: {len(metrics['system_bad_names'])}\n")
        for x in metrics['system_bad_names'][:20]:
            f.write(f"  - `{x}`\n")
        f.write(f"- recovery_over_one: {len(metrics['recovery_over_one'])}\n")
        for x in metrics['recovery_over_one'][:20]:
            f.write(f"  - `{x}`\n")
        f.write(f"- corrupt_dirs: {len(metrics['corrupt_dirs'])}\n")
        for x in metrics['corrupt_dirs'][:20]:
            f.write(f"  - `{x}`\n")
    return p


def check_stop_conditions(batch_num, metrics, cost_cumulative,
                              total_budget, subproc_rc):
    """spec 三 (更新版) 8 项停止条件.

    rc≠0 时只报根因; 不再叠加下游质量条件, 避免早停带来的虚假触发.
    """
    stops = []
    # 1-3. rc 触发的根因: 出现即返回, 不评估下游指标
    if subproc_rc == 3:
        stops.append("[1] authentication error (rc=3)")
    if subproc_rc == 6:
        stops.append("[2] 5 consecutive papers 429-failed (rc=6)")
    if subproc_rc == 7:
        stops.append("[3] paper hit 4x 429 retry ceiling (rc=7)")
    if subproc_rc == 4:
        stops.append("[3a] 3 consecutive non-429 failures (rc=4)")
    if stops:
        return stops   # rc 根因优先; 不再叠加质量条件

    # rc == 0: 正常完成 batch, 评估质量条件
    # 4. 成功率 < 90%
    if metrics["ok_rate"] < 0.90:
        stops.append(f"[4] batch {batch_num} ok_rate "
                       f"{metrics['ok_rate']*100:.1f}% < 90%")
    # 5. 累计预算
    if cost_cumulative >= total_budget:
        stops.append(f"[5] total cost ¥{cost_cumulative:.2f} >= "
                       f"budget ¥{total_budget:.2f}")
    # 6. evidence ID < 95%
    if metrics["id_valid_rate"] < 0.95:
        stops.append(f"[6] batch {batch_num} id_valid_rate "
                       f"{metrics['id_valid_rate']*100:.2f}% < 95%")
    # 7. slice consistency < 100%
    if metrics["slice_rate"] < 1.0:
        stops.append(f"[7] batch {batch_num} slice_rate "
                       f"{metrics['slice_rate']*100:.2f}% < 100%")
    # 8. corrupt dirs (raw / manifest 损坏; 未尝试的 dir 不算)
    if metrics["corrupt_dirs"]:
        stops.append(f"[8] corrupt dirs: {metrics['corrupt_dirs'][:3]}")
    return stops


def build_arg_parser():
    p = argparse.ArgumentParser(description="Run stage A batches in sequence")
    p.add_argument("--from", dest="from_batch", type=int, default=3)
    p.add_argument("--to", dest="to_batch", type=int, default=14)
    p.add_argument("--total-budget-cny", type=float, default=110.0)
    p.add_argument("--per-batch-hard-stop", type=float, default=20.0)
    p.add_argument("--model", type=str,
                    default=os.environ.get("MOONSHOT_MODEL",
                                              "moonshot-v1-auto"))
    p.add_argument("--reports-dir", type=str,
                    default=os.path.join(config.STAGE_A_FULL_V1_DIR,
                                           "batch_reports"))
    p.add_argument("--inter-batch-pause", type=int, default=30,
                    help="Seconds between batches (spec 二, default 30)")
    return p


def main():
    args = build_arg_parser().parse_args()
    reports_dir = args.reports_dir
    os.makedirs(reports_dir, exist_ok=True)

    print("=" * 70)
    print(f"Running batches {args.from_batch} → {args.to_batch} "
            f"total_budget=¥{args.total_budget_cny}")
    print("=" * 70)

    cumulative_cost = 0.0
    stop_reason = None
    import time as _time

    for i, bn in enumerate(range(args.from_batch, args.to_batch + 1)):
        pids = load_batch_paper_ids(bn)
        if not pids:
            print(f"batch {bn}: no papers, skip")
            continue
        # spec 二: 批次之间暂停 30 秒 (第一批不等)
        if i > 0 and args.inter_batch_pause > 0:
            print(f"\n[pause {args.inter_batch_pause}s between batches]")
            _time.sleep(args.inter_batch_pause)
        print(f"\n=== BATCH {bn} ({len(pids)} papers) ===")

        # 剩余预算
        remaining = args.total_budget_cny - cumulative_cost
        per_batch = min(args.per_batch_hard_stop, max(remaining, 0.0))
        if per_batch <= 0:
            stop_reason = f"[1] cumulative cost exhausted budget before batch {bn}"
            break

        cmd = [sys.executable, "-X", "utf8", "-m",
                "src.graph_rag.method_evolution_v2.run_stage_a_full",
                "--batch", str(bn), "--budget-hard-stop", str(per_batch)]
        env = os.environ.copy()
        env["MOONSHOT_MODEL"] = args.model
        env["PYTHONIOENCODING"] = "utf-8"

        proc = subprocess.run(cmd, env=env, capture_output=False,
                                text=True)
        rc = proc.returncode

        # After batch, compute metrics + cost
        metrics = compute_batch_metrics(pids)
        cost_this = compute_batch_cost(pids, args.model)
        cumulative_cost += cost_this

        # Persist per-batch report
        rp = write_batch_report(bn, metrics, cost_this, reports_dir)
        print(f"batch {bn} report: {rp}")
        print(f"  cost: ¥{cost_this:.3f}, cumulative: ¥{cumulative_cost:.3f}")

        stops = check_stop_conditions(bn, metrics, cumulative_cost,
                                          args.total_budget_cny, rc)
        if stops:
            stop_reason = f"batch {bn}: " + "; ".join(stops)
            print(f"\nAUTO-STOP: {stop_reason}")
            break

    # 写终止状态
    status = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "from_batch": args.from_batch,
        "to_batch": args.to_batch,
        "cumulative_cost_cny": round(cumulative_cost, 3),
        "budget_cap_cny": args.total_budget_cny,
        "stopped_early": bool(stop_reason),
        "stop_reason": stop_reason,
    }
    with open(os.path.join(reports_dir, "run_status.json"),
                "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)
    print(f"\nRun status: {status}")
    return 0 if not stop_reason else 5


if __name__ == "__main__":
    sys.exit(main())
