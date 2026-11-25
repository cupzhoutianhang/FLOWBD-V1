"""审查器批处理 + 覆盖保证 (spec 一).

策略:
  1. 把 proposals 按 batch_size=8 切段
  2. 每段送审, 记录返回的 pair_id
  3. 若某段返回 pair_id 未覆盖输入, 单独补调 1 次针对缺失 pair_id
  4. 补调后仍缺失 → 记为 missing (下游 edge_validation 会打 audit_missing → rejected)
  5. 每段/每次补调独立算作 1 API call
"""
from __future__ import annotations

import json
from method_evolution_v2.stage_a.method_extraction import parse_llm_json


DEFAULT_AUDIT_BATCH_SIZE = 8


def batch_proposals(proposals: list, batch_size: int = DEFAULT_AUDIT_BATCH_SIZE) -> list:
    if batch_size <= 0:
        return [proposals]
    return [proposals[i:i + batch_size] for i in range(0, len(proposals), batch_size)]


def run_audit_with_coverage(
    proposals: list,
    methods_by_id: dict,
    sentence_index: dict,
    build_prompt,           # callable: (proposals, batch_size) -> user_prompt str
    call_llm,               # callable: (user_prompt) -> (obj, ok, err, usage, raw_text)
    batch_size: int = DEFAULT_AUDIT_BATCH_SIZE,
    max_recovery_calls: int = 1,
    log_sink: list = None,
) -> dict:
    """跑一遍完整审查(带覆盖保证).

    Args:
      proposals: extractor 提议的完整列表 (可能含 verdict=NO_RELATION 的 —— 那些也要审?)
                 实际调用方只把 verdict!=NO_RELATION 的送进来
      build_prompt(pairs_subset, batch_size): 生成一段 audit prompt
      call_llm(prompt): 返回 (audit_obj_dict, ok, err, usage_dict, raw_text)
    Returns:
      {
        "audits_by_pair":     {pair_id: audit dict},
        "input_pair_ids":     [...],
        "covered_pair_ids":   [...],
        "missing_pair_ids":   [...],
        "batches_run":        int,
        "recovery_runs":      int,
        "call_count":         int,
        "audit_usage":        {prompt_tokens, completion_tokens, total_tokens},
        "raw_calls":          [{tag, ok, err, usage, response_preview, expected_ids, got_ids}, ...],
      }
    """
    log_sink = log_sink if log_sink is not None else []

    if not proposals:
        return {
            "audits_by_pair": {}, "input_pair_ids": [], "covered_pair_ids": [],
            "missing_pair_ids": [], "batches_run": 0, "recovery_runs": 0,
            "call_count": 0,
            "audit_usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            "raw_calls": [],
        }

    audits_by_pair: dict = {}
    input_ids = [p.get("pair_id", "") for p in proposals]
    total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    raw_calls = []
    call_count = 0

    # ---- Round 1: 分批全部走一遍 ----
    batches = batch_proposals(proposals, batch_size)
    for bi, batch in enumerate(batches, 1):
        prompt = build_prompt(batch, batch_size)
        obj, ok, err, usage, raw = call_llm(prompt)
        call_count += 1
        for k in total_usage:
            total_usage[k] += int(usage.get(k, 0) or 0)
        got_ids = []
        if ok:
            arr = obj.get("audits") if isinstance(obj, dict) else None
            if isinstance(arr, list):
                for a in arr:
                    if not isinstance(a, dict):
                        continue
                    pid = a.get("pair_id", "")
                    if pid:
                        audits_by_pair[pid] = a
                        got_ids.append(pid)
        expected = [p.get("pair_id", "") for p in batch]
        raw_calls.append({
            "tag": f"audit_batch_{bi}",
            "ok": ok, "err": err, "usage": usage,
            "expected_pair_ids": expected,
            "got_pair_ids": got_ids,
            "response_preview": (raw or "")[:2000],
        })

    # ---- 覆盖率检查 ----
    covered = list(audits_by_pair.keys())
    missing = [pid for pid in input_ids if pid not in audits_by_pair]

    # ---- Round 2: 缺失 pair 补调 (只 1 次) ----
    recovery_runs = 0
    if missing and max_recovery_calls > 0:
        # 只补调缺失的 (仍分批)
        missing_props = [p for p in proposals if p.get("pair_id", "") in missing]
        recovery_batches = batch_proposals(missing_props, batch_size)
        for ri, batch in enumerate(recovery_batches, 1):
            prompt = build_prompt(batch, batch_size)
            obj, ok, err, usage, raw = call_llm(prompt)
            call_count += 1
            recovery_runs += 1
            for k in total_usage:
                total_usage[k] += int(usage.get(k, 0) or 0)
            got_ids = []
            if ok:
                arr = obj.get("audits") if isinstance(obj, dict) else None
                if isinstance(arr, list):
                    for a in arr:
                        if not isinstance(a, dict):
                            continue
                        pid = a.get("pair_id", "")
                        if pid and pid not in audits_by_pair:
                            audits_by_pair[pid] = a
                            got_ids.append(pid)
            expected = [p.get("pair_id", "") for p in batch]
            raw_calls.append({
                "tag": f"audit_recovery_{ri}",
                "ok": ok, "err": err, "usage": usage,
                "expected_pair_ids": expected,
                "got_pair_ids": got_ids,
                "response_preview": (raw or "")[:2000],
            })

    covered = list(audits_by_pair.keys())
    missing = [pid for pid in input_ids if pid not in audits_by_pair]

    log_sink.append({
        "input_count": len(input_ids),
        "covered_count": len(covered),
        "missing_count": len(missing),
        "batches_run": len(batches),
        "recovery_runs": recovery_runs,
        "total_audit_calls": call_count,
    })

    return {
        "audits_by_pair": audits_by_pair,
        "input_pair_ids": input_ids,
        "covered_pair_ids": covered,
        "missing_pair_ids": missing,
        "batches_run": len(batches),
        "recovery_runs": recovery_runs,
        "call_count": call_count,
        "audit_usage": total_usage,
        "raw_calls": raw_calls,
    }
