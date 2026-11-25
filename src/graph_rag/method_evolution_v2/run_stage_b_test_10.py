"""run_stage_b_test_10.py — Stage B driver (10 篇, 两阶段: 提取 + 独立审查).

严格约束(spec 九/十一):
  - 只用 MOONSHOT_API_KEY 环境变量; 只调 Moonshot 端点; 无 DMXAPI
  - 只跑固定 10 篇, 输出 test_run_04_stage_b/ (不覆盖任何旧结果)
  - 每篇: 1 次抽取 + 1 次审查 = 2 次 API 调用; 全局 ≤20 次
  - JSON 失败每篇最多重试 1 次 (超过则单篇失败继续)
  - 预飞打印 model + 预计调用 + 预算; >¥20 停下
  - 不进 Stage 全量; 不写 DB
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
from method_evolution_v2.stage_a.method_extraction import parse_llm_json        # noqa: E402
from method_evolution_v2.stage_b import (                                       # noqa: E402
    pair_generator as pg,
    edge_validation as ev,
    STAGE_B_VERSION,
)
from method_evolution_v2.stage_b import prompts as prompts_b                    # noqa: E402


# 每篇最多 2 调用 (1 抽取 + 1 审查)
MAX_CALLS_PER_PAPER = 2
BUDGET_HARD_STOP_CNY = 20.0

# 32k tier 参考价
INPUT_CNY_PER_M = 24.0
OUTPUT_CNY_PER_M = 24.0

# 每次调用估算 (Stage B 输入包含 methods+pairs+sentences, 通常 8-15k tokens)
EST_INPUT_TOKENS_PER_CALL = 15000
EST_OUTPUT_TOKENS_PER_CALL = 2500


# ---- CSV schemas ----

CAND_PAIR_FIELDS = [
    "pair_id", "paper_id",
    "method_a_id", "method_b_id",
    "method_a_name", "method_b_name",
    "method_a_kind", "method_b_kind",
    "method_a_status", "method_b_status",
    "method_a_citation_clue", "method_b_citation_clue",
    "pair_source", "min_para_diff", "trigger_para_count",
    "connector_sentence_ids", "para_span",
]

EDGE_FIELDS = [
    "paper_id", "pair_id",
    "from_method_id", "to_method_id",
    "from_method_name", "to_method_name",
    "relation",
    "relation_evidence_sentence_ids", "evidence_missing_ids", "evidence_spans",
    "evidence_quote", "evidence_section", "evidence_para_id",
    "evidence_char_start", "evidence_char_end",
    "direction_basis", "relation_reason", "confidence_llm",
    "audit_support", "audit_direction", "audit_relation_check",
    "audit_suggested_relation", "audit_reason",
    "endpoint_a_status", "endpoint_b_status",
    "from_year", "to_year", "temporal_status",
    "validation_status", "rejected_reason",
]

PER_PAPER_FIELDS = [
    "paper_id", "canonical_title", "paper_type",
    "n_methods", "n_theoretical_pairs", "n_filtered_pairs",
    "n_relations_proposed",
    "n_accepted_edges", "n_candidate_edges", "n_rejected_edges",
    "extract_call_ok", "audit_call_ok",
    "extract_prompt_tokens", "extract_completion_tokens",
    "audit_prompt_tokens", "audit_completion_tokens",
    "estimated_cost_cny", "duration_sec", "note",
]


# ============================================================
# helpers
# ============================================================

def _j(v):
    if isinstance(v, (list, dict)):
        return json.dumps(v, ensure_ascii=False)
    return "" if v is None else str(v)


def _load_json(p):
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_csv_rows(p):
    with open(p, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _write_csv(path, fields, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow({k: _j(row.get(k)) for k in fields})


def _est_cost(pt, ct):
    return pt / 1_000_000 * INPUT_CNY_PER_M + ct / 1_000_000 * OUTPUT_CNY_PER_M


def _accum(agg, u):
    for k in ("prompt_tokens", "completion_tokens", "total_tokens"):
        agg[k] = agg.get(k, 0) + int(u.get(k, 0) or 0)


# ============================================================
# 加载 Stage A 结果
# ============================================================

def load_stage_a_methods():
    """加载 Stage A v03 的 accepted + candidate 方法.

    Returns: {paper_id: [method dict, ...]}, method dicts have kind + validation_status.
    """
    out = defaultdict(list)
    for status, path in [
        ("accepted", config.STAGE_A_TEST_03_METHODS_ACCEPTED),
        ("candidate", config.STAGE_A_TEST_03_METHODS_CANDIDATE),
    ]:
        if not os.path.isfile(path):
            continue
        for r in _load_csv_rows(path):
            try:
                sids = json.loads(r.get("evidence_sentence_ids", "[]"))
            except Exception:
                sids = []
            out[r["paper_id"]].append({
                "paper_id": r["paper_id"],
                "method_id": r["method_id"],
                "kind": r.get("kind", ""),
                "name": r.get("method_name", ""),
                "validation_status": status,
                "method_type": r.get("method_type", ""),
                "problem_solved": r.get("problem_solved", ""),
                "key_components": r.get("key_components", ""),
                "citation_clue": r.get("citation_clue", ""),
                "evidence_sentence_ids": sids,
                "evidence_section": r.get("evidence_section", ""),
                "evidence_para_id": r.get("evidence_para_id", ""),
            })
    return out


def load_sentence_index(paper_id: str) -> dict:
    p = os.path.join(config.STAGE_A_TEST_03_SENTENCE_IDX_DIR, f"{paper_id}.json")
    if not os.path.isfile(p):
        return {}
    d = _load_json(p)
    return {s["sentence_id"]: s for s in d.get("sentences", [])}


# ============================================================
# LLM I/O 组装
# ============================================================

def build_extractor_pack(paper_id, canonical_title, paper_type,
                          primary_domain, subfield, pairs, sentence_index):
    """构造 Stage B.1 输入.

    sentence pack 只包含与候选对相关的段落 (集合并 + 触发句).
    """
    # 汇集所有相关 sids: 每对的两方法 evidence + connector_sentence_ids
    relevant_sids = set()
    for pair in pairs:
        for sid in pair.get("method_a_evidence_sids", []):
            relevant_sids.add(sid)
        for sid in pair.get("method_b_evidence_sids", []):
            relevant_sids.add(sid)
        for sid in pair.get("connector_sentence_ids", []):
            relevant_sids.add(sid)

    # 邻域扩展: 相关 sid 所在 paragraph 的所有句子 (提供上下文)
    para_nums = set()
    for sid in relevant_sids:
        parsed = pg.parse_sentence_id(sid)
        if parsed:
            para_nums.add(parsed[1])
    for sid, s in sentence_index.items():
        parsed = pg.parse_sentence_id(sid)
        if parsed and parsed[1] in para_nums:
            relevant_sids.add(sid)

    # 排序输出
    relevant = sorted(
        (sentence_index[sid] for sid in relevant_sids if sid in sentence_index),
        key=lambda s: (s["char_start"], s["char_end"])
    )
    prev_sec = None
    lines = []
    for s in relevant:
        sec_key = (s["section_type"], s["section_name"])
        if sec_key != prev_sec:
            lines.append(f"\n### [{s['section_type']}] {s['section_name']}")
            prev_sec = sec_key
        text = s["sentence_text"].replace("\n", " ").strip()
        lines.append(f"- {s['sentence_id']}: 「{text}」")
    sentence_pack = "\n".join(lines) if lines else "(无相关句子)"

    # pair 列表
    pair_lines = []
    for p in pairs:
        pair_lines.append(
            f"\n#### {p['pair_id']} (来源: {p['pair_source']}, "
            f"min_para_diff={p['min_para_diff']})\n"
            f"- method_a: method_id={p['method_a_id']}, "
            f"kind={p['method_a_kind']}, status={p['method_a_status']}, "
            f"name={p['method_a_name']!r}, "
            f"citation_clue={p['method_a_citation_clue']!r}, "
            f"evidence_sids={p['method_a_evidence_sids']}\n"
            f"- method_b: method_id={p['method_b_id']}, "
            f"kind={p['method_b_kind']}, status={p['method_b_status']}, "
            f"name={p['method_b_name']!r}, "
            f"citation_clue={p['method_b_citation_clue']!r}, "
            f"evidence_sids={p['method_b_evidence_sids']}"
        )
    pair_list = "\n".join(pair_lines) if pair_lines else "(无候选对)"

    return prompts_b.EXTRACTOR_USER_TEMPLATE.format(
        paper_id=paper_id,
        canonical_title=canonical_title,
        paper_type=paper_type or "unclear",
        primary_storage_domain=primary_domain or "(空)",
        technology_subfield=subfield or "(空)",
        pair_list=pair_list,
        sentence_pack=sentence_pack,
    )


def build_auditor_pack(proposals, methods_by_id, sentence_index):
    """构造 Stage B.2 blind auditor 输入.

    每个 proposal 只带: method_a/b 简要信息 + resolved evidence text + relation + direction.
    不带 relation_reason / confidence_llm.
    """
    if not proposals:
        return None

    blocks = []
    for i, prop in enumerate(proposals, 1):
        pair_id = prop.get("pair_id", "")
        from_id = prop.get("from_method_id", "")
        to_id = prop.get("to_method_id", "")
        rel = prop.get("relation", "")
        sids = prop.get("relation_evidence_sentence_ids") or []

        m_from = methods_by_id.get(from_id, {})
        m_to = methods_by_id.get(to_id, {})

        # 解析证据 (只显示已存在的 sid)
        ev_lines = []
        for sid in sids:
            s = sentence_index.get(sid)
            if s:
                text = s["sentence_text"].replace("\n", " ").strip()
                ev_lines.append(f"  - {sid} [{s['section_type']}]: 「{text}」")
            else:
                ev_lines.append(f"  - {sid} (⚠ NOT FOUND in sentence index)")
        ev_block = "\n".join(ev_lines) if ev_lines else "  (无证据句 -- 请标 unsupported)"

        blocks.append(
            f"\n#### {pair_id}\n"
            f"- from_method: id={from_id}, kind={m_from.get('kind','?')}, "
            f"name={m_from.get('name','')!r}\n"
            f"- to_method:   id={to_id}, kind={m_to.get('kind','?')}, "
            f"name={m_to.get('name','')!r}\n"
            f"- 提议 relation: {rel}\n"
            f"- 关系证据句 (只这些, 无其他):\n{ev_block}"
        )

    return prompts_b.AUDITOR_USER_TEMPLATE.format(
        proposal_list="\n".join(blocks)
    )


def call_and_parse(system, user, model, tag="", log_sink=None):
    """一次调用 + JSON 解析. 返回 (parsed_obj, ok, err, usage, raw_text)."""
    r = llm_client.call_chat(system, user, model=model)
    usage = r.get("usage") or {}
    if not r["ok"]:
        if log_sink is not None:
            log_sink.append({"tag": tag, "ok": False, "err": r.get("error", ""),
                             "usage": usage})
        return {}, False, r.get("error", ""), usage, ""
    text = r.get("text", "")
    ok, obj, err = parse_llm_json(text)
    if log_sink is not None:
        log_sink.append({"tag": tag, "ok": ok, "err": err, "usage": usage})
    return obj, ok, err, usage, text


# ============================================================
# 主循环
# ============================================================

def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    # ---- pre-flight ----
    try:
        key = llm_client.get_api_key()
    except RuntimeError as e:
        print("PRE-FLIGHT FAIL:", e)
        return 2

    model = os.environ.get("MOONSHOT_MODEL", llm_client.DEFAULT_MODEL)
    n_papers = len(config.TEST_RUN_01_PAPER_IDS)
    max_calls = n_papers * MAX_CALLS_PER_PAPER
    est_per = _est_cost(EST_INPUT_TOKENS_PER_CALL, EST_OUTPUT_TOKENS_PER_CALL)
    est_max = est_per * max_calls

    print("=" * 70)
    print("Stage B (two-stage relation extraction) - 预飞检查")
    print(f"  model:            {model}")
    print(f"  api endpoint:     {llm_client.MOONSHOT_API_URL}")
    print(f"  key present:      yes (len={len(key)}, "
          f"prefix={key[:6]}..., suffix=...{key[-4:]})")
    print(f"  papers to run:    {n_papers}")
    print(f"  max calls:        {max_calls} (1 extractor + 1 auditor per paper)")
    print(f"  est input/call:   {EST_INPUT_TOKENS_PER_CALL}")
    print(f"  est output/call:  {EST_OUTPUT_TOKENS_PER_CALL}")
    print(f"  est cost/call:    ¥{est_per:.3f} (32k tier rate)")
    print(f"  est cost max:     ¥{est_max:.2f}")
    print(f"  budget hard stop: ¥{BUDGET_HARD_STOP_CNY:.2f}")
    if est_max > BUDGET_HARD_STOP_CNY:
        print(f"STOP: est_cost_max ¥{est_max:.2f} > threshold "
              f"¥{BUDGET_HARD_STOP_CNY:.2f}.")
        return 3
    print(f"  budget check:     OK")
    print("=" * 70)

    os.makedirs(config.STAGE_B_TEST_04_DIR, exist_ok=True)
    os.makedirs(config.STAGE_B_TEST_04_LOGS_DIR, exist_ok=True)

    # ---- 加载 Stage A + taxonomy 上下文 ----
    methods_by_paper = load_stage_a_methods()
    tax_rows = {r["paper_id"]: r for r in _load_csv_rows(
        config.CORPUS_PP_V1_1_PAPER_TAXONOMY_CSV)}
    pt_rows = {r["paper_id"]: r for r in _load_csv_rows(
        config.CORPUS_PP_V1_1_PAPER_TYPES_CSV)}

    started_iso = datetime.now().isoformat(timespec="seconds")
    t0 = time.time()

    all_pairs = []
    all_raw_records = []
    all_audit_records = []
    all_edges = []
    per_paper_rows = []
    total_calls = 0
    total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    for i, pid in enumerate(config.TEST_RUN_01_PAPER_IDS, 1):
        methods = methods_by_paper.get(pid, [])
        sentence_index = load_sentence_index(pid)
        tax_r = tax_rows.get(pid, {})
        pt_r = pt_rows.get(pid, {})
        canonical_title = tax_r.get("canonical_title", pid)
        paper_type = pt_r.get("paper_type", "unclear")
        primary = tax_r.get("primary_storage_domain", "")
        subfield = tax_r.get("technology_subfield", "")

        t_paper = time.time()
        methods_by_id = {m["method_id"]: m for m in methods}
        pairs, stats = pg.generate_candidate_pairs(pid, methods, sentence_index)
        for p in pairs:
            all_pairs.append(p)

        note = ""
        extract_ok, audit_ok = False, False
        e_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        a_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        proposals = []
        audit_by_pair = {}
        log_sink = []

        # ---- 抽取 (只在有 pair 时调用) ----
        if pairs:
            extract_pack = build_extractor_pack(
                pid, canonical_title, paper_type, primary, subfield,
                pairs, sentence_index,
            )
            obj, ok, err, u, raw = call_and_parse(
                prompts_b.EXTRACTOR_SYSTEM, extract_pack, model,
                tag="extractor", log_sink=log_sink,
            )
            total_calls += 1
            _accum(e_usage, u)
            _accum(total_usage, u)
            extract_ok = ok
            if ok:
                relations = obj.get("relations") if isinstance(obj, dict) else None
                if isinstance(relations, list):
                    proposals = [r for r in relations if isinstance(r, dict)]

            all_raw_records.append({
                "paper_id": pid,
                "n_pairs_sent": len(pairs),
                "ok": ok,
                "error": err,
                "usage": u,
                "proposals": proposals,
                "raw_text_last": raw[:8000],
            })

            # ---- 审查 (只在有 proposals 时调用) ----
            if proposals:
                audit_pack = build_auditor_pack(
                    proposals, methods_by_id, sentence_index)
                if audit_pack:
                    audit_obj, audit_call_ok, audit_err, u2, raw2 = call_and_parse(
                        prompts_b.AUDITOR_SYSTEM, audit_pack, model,
                        tag="auditor", log_sink=log_sink,
                    )
                    total_calls += 1
                    _accum(a_usage, u2)
                    _accum(total_usage, u2)
                    audit_ok = audit_call_ok
                    audits_list = []
                    if audit_call_ok:
                        arr = audit_obj.get("audits") if isinstance(audit_obj, dict) else None
                        if isinstance(arr, list):
                            audits_list = [a for a in arr if isinstance(a, dict)]
                    audit_by_pair = {a.get("pair_id", ""): a for a in audits_list
                                     if a.get("pair_id")}
                    all_audit_records.append({
                        "paper_id": pid, "ok": audit_call_ok,
                        "error": audit_err, "usage": u2,
                        "audits": audits_list,
                        "raw_text_last": raw2[:8000],
                    })
        else:
            note = "no_candidate_pairs"

        # ---- 每条 proposal → validated edge ----
        edges = []
        for prop in proposals:
            e = ev.validate_and_classify_edge(prop, methods_by_id,
                                               sentence_index, audit_by_pair)
            # 保证 paper_id 存在
            if not e.get("paper_id"):
                e["paper_id"] = pid
            edges.append(e)
        all_edges.extend(edges)

        dt = time.time() - t_paper
        acc = sum(1 for e in edges if e["validation_status"] == "accepted")
        cand = sum(1 for e in edges if e["validation_status"] == "candidate")
        rej = sum(1 for e in edges if e["validation_status"] == "rejected")

        cost = _est_cost(e_usage["prompt_tokens"] + a_usage["prompt_tokens"],
                         e_usage["completion_tokens"] + a_usage["completion_tokens"])

        per_paper_rows.append({
            "paper_id": pid,
            "canonical_title": canonical_title,
            "paper_type": paper_type,
            "n_methods": stats["n_methods"],
            "n_theoretical_pairs": stats["theoretical_pairs"],
            "n_filtered_pairs": stats["filtered_pairs"],
            "n_relations_proposed": len(proposals),
            "n_accepted_edges": acc,
            "n_candidate_edges": cand,
            "n_rejected_edges": rej,
            "extract_call_ok": extract_ok,
            "audit_call_ok": audit_ok,
            "extract_prompt_tokens": e_usage["prompt_tokens"],
            "extract_completion_tokens": e_usage["completion_tokens"],
            "audit_prompt_tokens": a_usage["prompt_tokens"],
            "audit_completion_tokens": a_usage["completion_tokens"],
            "estimated_cost_cny": round(cost, 4),
            "duration_sec": round(dt, 2),
            "note": note,
        })

        # 每篇 log
        with open(os.path.join(config.STAGE_B_TEST_04_LOGS_DIR, f"{pid}.log.json"),
                  "w", encoding="utf-8") as f:
            json.dump({
                "paper_id": pid, "duration_sec": round(dt, 2),
                "stats": stats, "n_proposals": len(proposals),
                "n_edges_accepted": acc, "n_edges_candidate": cand,
                "n_edges_rejected": rej,
                "extract_usage": e_usage, "audit_usage": a_usage,
                "estimated_cost_cny": round(cost, 4),
                "llm_calls_log": log_sink,
            }, f, ensure_ascii=False, indent=2)

        print(f"  [{i:>2}/10] {pid[:36]:<36} "
              f"pairs={len(pairs)}/{stats['theoretical_pairs']} "
              f"proposed={len(proposals)} acc={acc} cand={cand} rej={rej} "
              f"calls={1 if pairs else 0}+{1 if proposals else 0}")

    dur = time.time() - t0

    # ---- 写产物 ----
    _write_csv(config.STAGE_B_TEST_04_CANDIDATE_PAIRS_CSV,
                CAND_PAIR_FIELDS, all_pairs)

    with open(config.STAGE_B_TEST_04_RELATION_RAW, "w", encoding="utf-8") as f:
        for r in all_raw_records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    with open(config.STAGE_B_TEST_04_AUDIT_JSONL, "w", encoding="utf-8") as f:
        for r in all_audit_records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    _write_csv(config.STAGE_B_TEST_04_EDGES_ACCEPTED, EDGE_FIELDS,
                [e for e in all_edges if e["validation_status"] == "accepted"])
    _write_csv(config.STAGE_B_TEST_04_EDGES_CANDIDATE, EDGE_FIELDS,
                [e for e in all_edges if e["validation_status"] == "candidate"])
    _write_csv(config.STAGE_B_TEST_04_EDGES_REJECTED, EDGE_FIELDS,
                [e for e in all_edges if e["validation_status"] == "rejected"])
    _write_csv(config.STAGE_B_TEST_04_PER_PAPER_CSV, PER_PAPER_FIELDS,
                per_paper_rows)

    total_cost = _est_cost(total_usage["prompt_tokens"],
                            total_usage["completion_tokens"])

    # ============================================================
    # 报告
    # ============================================================
    n_theoretical = sum(r["n_theoretical_pairs"] for r in per_paper_rows)
    n_filtered = sum(r["n_filtered_pairs"] for r in per_paper_rows)
    n_proposed = sum(r["n_relations_proposed"] for r in per_paper_rows)
    n_acc = sum(r["n_accepted_edges"] for r in per_paper_rows)
    n_cand = sum(r["n_candidate_edges"] for r in per_paper_rows)
    n_rej = sum(r["n_rejected_edges"] for r in per_paper_rows)
    relation_counter = Counter(e["relation"] for e in all_edges)
    accepted_relation_counter = Counter(
        e["relation"] for e in all_edges if e["validation_status"] == "accepted")

    # 证据 ID 有效率 + 切片一致率
    total_ids = 0
    valid_ids = 0
    for e in all_edges:
        sids = e.get("relation_evidence_sentence_ids") or []
        missing = e.get("evidence_missing_ids") or []
        total_ids += len(sids)
        valid_ids += len(sids) - len(missing)
    id_valid_rate = (valid_ids / total_ids) if total_ids else 1.0
    slice_pass = sum(1 for e in all_edges if e.get("evidence_char_start", -1) >= 0
                     and not e.get("evidence_missing_ids"))
    slice_rate = slice_pass / max(len(all_edges), 1) if all_edges else 1.0

    # 审查支持率
    support_counter = Counter(e["audit_support"] for e in all_edges)
    dir_wrong_counter = Counter(e["audit_direction"] for e in all_edges)
    type_wrong_counter = Counter(e["audit_relation_check"] for e in all_edges)
    n_temporal_conflict = sum(1 for e in all_edges
                               if e["temporal_status"] == "conflict")
    no_edge_papers = [r["paper_id"] for r in per_paper_rows
                      if r["n_accepted_edges"] == 0 and r["n_candidate_edges"] == 0]

    val_report = {
        "run_started_at": started_iso,
        "duration_sec": round(dur, 2),
        "model": model,
        "stage_b_version": STAGE_B_VERSION,
        "counts": {
            "n_papers": n_papers,
            "n_theoretical_pairs": n_theoretical,
            "n_filtered_pairs": n_filtered,
            "n_relations_proposed": n_proposed,
            "n_accepted_edges": n_acc,
            "n_candidate_edges": n_cand,
            "n_rejected_edges": n_rej,
            "papers_with_no_edge": len(no_edge_papers),
        },
        "relations_distribution": dict(relation_counter),
        "accepted_relations_distribution": dict(accepted_relation_counter),
        "evidence_ids_total": total_ids,
        "evidence_ids_valid": valid_ids,
        "evidence_id_valid_rate": round(id_valid_rate, 4),
        "evidence_slice_consistent_rate": round(slice_rate, 4),
        "audit_support_distribution": dict(support_counter),
        "audit_direction_distribution": dict(dir_wrong_counter),
        "audit_relation_check_distribution": dict(type_wrong_counter),
        "temporal_conflict_count": n_temporal_conflict,
        "no_edge_papers": no_edge_papers,
        "usage_total": total_usage,
        "actual_api_calls": total_calls,
        "actual_cost_cny": round(total_cost, 4),
        "budget_hard_stop_cny": BUDGET_HARD_STOP_CNY,
    }
    with open(config.STAGE_B_TEST_04_VALIDATION_JSON, "w", encoding="utf-8") as f:
        json.dump(val_report, f, ensure_ascii=False, indent=2)

    # ---- Markdown ----
    ml = []
    ml.append(f"# Stage B 校验报告 (test_run_04_stage_b)\n\n")
    ml.append(
        f"> 运行时间: {started_iso} · 耗时 {round(dur, 1)}s\n"
        f"> 模型: `{model}`\n"
        f"> API 调用: **{total_calls}** / 上限 {max_calls}\n"
        f"> tokens: prompt={total_usage['prompt_tokens']} completion="
        f"{total_usage['completion_tokens']} total={total_usage['total_tokens']}\n"
        f"> 预算: **¥{round(total_cost, 3)}** (硬门限 ¥{BUDGET_HARD_STOP_CNY})\n\n"
    )
    ml.append(f"## 一、候选对数量\n")
    ml.append(f"- 理论全排列: **{n_theoretical}**\n")
    ml.append(f"- 规则筛选后: **{n_filtered}**\n")
    ml.append(f"- 实际送模型 (等于 filtered): **{n_filtered}**\n")

    ml.append(f"\n## 二、关系抽取汇总\n")
    ml.append(f"- 模型提出的关系: **{n_proposed}**\n")
    ml.append(f"- accepted edges: **{n_acc}**\n")
    ml.append(f"- candidate edges: {n_cand}\n")
    ml.append(f"- rejected edges: {n_rej}\n")

    ml.append(f"\n## 三、四类关系分布\n\n| 关系 | 总提议 | accepted |\n|---|---:|---:|\n")
    for r in ("EXTENDS", "IMPROVES", "ADAPTS", "REPLACES"):
        ml.append(f"| {r} | {relation_counter.get(r, 0)} "
                  f"| {accepted_relation_counter.get(r, 0)} |\n")

    ml.append(f"\n## 四、证据质量\n")
    ml.append(f"- 证据 ID 有效率: **{round(id_valid_rate * 100, 2)}%** "
              f"({valid_ids}/{total_ids})\n")
    ml.append(f"- 原文切片一致率: **{round(slice_rate * 100, 2)}%**\n")

    ml.append(f"\n## 五、审查模型统计\n\n")
    ml.append(f"### support\n| 值 | 数量 |\n|---|---:|\n")
    for k in ("supported", "weak", "unsupported", "unknown"):
        ml.append(f"| {k} | {support_counter.get(k, 0)} |\n")
    ml.append(f"\n### direction\n| 值 | 数量 |\n|---|---:|\n")
    for k in ("correct", "reversed", "unclear", "unknown"):
        ml.append(f"| {k} | {dir_wrong_counter.get(k, 0)} |\n")
    ml.append(f"\n### relation_check\n| 值 | 数量 |\n|---|---:|\n")
    for k in ("correct", "wrong_type", "unclear", "unknown"):
        ml.append(f"| {k} | {type_wrong_counter.get(k, 0)} |\n")

    ml.append(f"\n## 六、年份冲突\n")
    ml.append(f"- temporal_status=conflict 的关系: **{n_temporal_conflict}**\n")

    ml.append(f"\n## 七、每篇关系数量\n\n")
    ml.append("| # | paper_id | methods | 理论对 | 筛后 | 提议 | acc | cand | rej | 调用 | ¥ |\n"
              "|--:|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|\n")
    for i, r in enumerate(per_paper_rows, 1):
        calls = (1 if r["extract_call_ok"] or r["extract_prompt_tokens"] > 0 else 0) + \
                (1 if r["audit_call_ok"] or r["audit_prompt_tokens"] > 0 else 0)
        ml.append(
            f"| {i} | `{r['paper_id'][:36]}` | {r['n_methods']} "
            f"| {r['n_theoretical_pairs']} | {r['n_filtered_pairs']} "
            f"| {r['n_relations_proposed']} "
            f"| {r['n_accepted_edges']} | {r['n_candidate_edges']} "
            f"| {r['n_rejected_edges']} | {calls} "
            f"| {r['estimated_cost_cny']} |\n"
        )

    if no_edge_papers:
        ml.append(f"\n## 八、无关系论文 (0 accepted + 0 candidate)\n")
        for pid in no_edge_papers:
            row = next((r for r in per_paper_rows if r["paper_id"] == pid), {})
            reason = row.get("note", "") or (
                "无候选对" if row.get("n_filtered_pairs", 0) == 0
                else "模型提议 0 或全部被审查拒绝"
            )
            ml.append(f"- `{pid}` — {reason}\n")

    # 每条 accepted edge
    ml.append(f"\n## 九、每条 accepted 关系及原文证据\n\n")
    if n_acc == 0:
        ml.append("*(无)*\n")
    else:
        for e in all_edges:
            if e["validation_status"] != "accepted":
                continue
            ml.append(f"\n### `{e['paper_id']}` — {e['relation']}\n")
            ml.append(f"- from: `{e['from_method_id']}` — {e['from_method_name']}\n")
            ml.append(f"- to:   `{e['to_method_id']}` — {e['to_method_name']}\n")
            ml.append(f"- direction_basis: {e['direction_basis']}\n")
            ml.append(f"- audit_reason: {e['audit_reason']}\n")
            ml.append(f"- evidence_section: {e['evidence_section']}\n")
            ml.append(f"- evidence_sids: {e['relation_evidence_sentence_ids']}\n")
            ev_text = e['evidence_quote']
            if len(ev_text) > 300:
                ev_text = ev_text[:300] + "..."
            ml.append(f"- evidence_quote:\n\n> {ev_text}\n")

    with open(config.STAGE_B_TEST_04_VALIDATION_MD, "w", encoding="utf-8") as f:
        f.writelines(ml)

    print()
    print("=" * 70)
    print(f"Stage B done: {n_papers} papers, {total_calls} calls, "
          f"~¥{round(total_cost, 3)}, {round(dur, 1)}s")
    print(f"  proposed={n_proposed} accepted={n_acc} candidate={n_cand} rejected={n_rej}")
    print(f"  id_valid_rate={round(id_valid_rate * 100, 2)}% "
          f"slice_rate={round(slice_rate * 100, 2)}%")
    print(f"outputs: {config.relative_path(config.STAGE_B_TEST_04_DIR)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
