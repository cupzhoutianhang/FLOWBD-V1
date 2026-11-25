"""run_positive_case_stage_b.py — 严格 Stage B on top-3 positive candidates.

关键差异 vs. run_case_stage_b.py:
  - **只送**本地扫描已确定有关系句证据的 pair (来自 relation_sentence_candidates.csv),
    不做整篇方法两两组合
  - top-3 篇, 每篇最多 top-10 局部对, **总对数 ≤ 30**
  - **总预算 ≤ ¥5**

Env: MOONSHOT_API_KEY + MOONSHOT_MODEL 必须在 process env, 否则 rc=2.
"""
from __future__ import annotations

import csv
import json
import os
import sys
import time
from collections import defaultdict, Counter
from datetime import datetime

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_GRAPH_RAG_DIR = os.path.dirname(THIS_DIR)
if SRC_GRAPH_RAG_DIR not in sys.path:
    sys.path.insert(0, SRC_GRAPH_RAG_DIR)

from method_evolution_v2 import config                                       # noqa: E402
from method_evolution_v2.stage_a import llm_client, full_runner as fr        # noqa: E402
from method_evolution_v2.stage_a.method_extraction import parse_llm_json     # noqa: E402
from method_evolution_v2.stage_b import (                                     # noqa: E402
    audit_batching as ab, edge_validation_strict as evs,
)
from method_evolution_v2.stage_b import prompts_strict                       # noqa: E402


SCAN_DIR = os.path.join(config.PAPER_V2_DIR, "article_minimal_results",
                          "positive_case_scan")
OUT_DIR = os.path.join(config.PAPER_V2_DIR, "article_minimal_results",
                         "positive_case_stage_b")
os.makedirs(OUT_DIR, exist_ok=True)

TOP_N_PAPERS = 3
TOP_N_PAIRS_PER_PAPER = 10
MAX_TOTAL_PAIRS = 30
BUDGET_HARD_STOP = 5.0
AUDIT_BATCH_SIZE = 8
EXTRACT_MAX_TOKENS = 6000
INPUT_CNY_PER_M = 24.0
OUTPUT_CNY_PER_M = 24.0


def _est_cost(pt, ct):
    return pt / 1_000_000 * INPUT_CNY_PER_M + ct / 1_000_000 * OUTPUT_CNY_PER_M


def _j(v):
    if isinstance(v, (list, dict)):
        return json.dumps(v, ensure_ascii=False)
    return "" if v is None else str(v)


def _write_csv(path, fields, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows: w.writerow({k: _j(r.get(k)) for k in fields})


def load_top3_papers():
    with open(os.path.join(SCAN_DIR, "positive_case_candidates.csv"),
                "r", encoding="utf-8-sig") as f:
        cands = list(csv.DictReader(f))[:TOP_N_PAPERS]
    return [c["paper_id"] for c in cands]


def load_all_candidate_pairs():
    """Return dict: paper_id -> list of pair records (sorted by score desc)."""
    with open(os.path.join(SCAN_DIR, "relation_sentence_candidates.csv"),
                "r", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    by_paper = defaultdict(list)
    for r in rows:
        r["score"] = float(r.get("score", 0) or 0)
        try: r["evidence_sentence_ids"] = json.loads(r["evidence_sentence_ids"])
        except Exception: r["evidence_sentence_ids"] = []
        by_paper[r["paper_id"]].append(r)
    for pid in by_paper:
        by_paper[pid].sort(key=lambda x: -x["score"])
    return by_paper


def load_paper_methods(pid):
    d = fr.per_paper_dir(pid)
    with open(os.path.join(d, "methods_accepted.json"),
                "r", encoding="utf-8") as f:
        acc = json.load(f)
    with open(os.path.join(d, "methods_candidate.json"),
                "r", encoding="utf-8") as f:
        cand = json.load(f)
    with open(os.path.join(d, "sentence_index.json"),
                "r", encoding="utf-8") as f:
        sidx_data = json.load(f)
    sentence_index = {s["sentence_id"]: s for s in sidx_data.get("sentences", [])}
    def _adapt(m, status):
        return {"paper_id": pid, "method_id": m.get("method_id",""),
                 "kind": m.get("kind",""), "name": m.get("name",""),
                 "validation_status": status,
                 "citation_clue": m.get("citation_clue","") or m.get("citation_clue_raw",""),
                 "evidence_sentence_ids": m.get("evidence_sentence_ids", []),
                 "evidence_section": m.get("evidence_section",""),
                 "evidence_para_id": m.get("evidence_para_id","")}
    methods = [_adapt(m,"accepted") for m in acc] + [_adapt(m,"candidate") for m in cand]
    return methods, sentence_index


def build_extractor_prompt(paper_id, meta, filtered_pairs, sentence_index):
    """比 case_stage_b 更简: 只列本地筛选出的少量对 + 其触发句."""
    relevant_sids = set()
    for p in filtered_pairs:
        # 触发句 ids
        for sid in p.get("evidence_sentence_ids", []):
            relevant_sids.add(sid)
        # 端点方法的 evidence sids
        for m in (p.get("method_a"), p.get("method_b")):
            if m: relevant_sids.update(m.get("evidence_sentence_ids", []))

    # Enrich neighbors within paragraph (±1)
    from method_evolution_v2.stage_b import pair_generator as pg
    para_nums = set()
    for sid in list(relevant_sids):
        parsed = pg.parse_sentence_id(sid)
        if parsed: para_nums.add(parsed[1])
    for sid, s in sentence_index.items():
        parsed = pg.parse_sentence_id(sid)
        if parsed and parsed[1] in para_nums:
            relevant_sids.add(sid)

    relevant = sorted(
        (sentence_index[sid] for sid in relevant_sids if sid in sentence_index),
        key=lambda s: (s["char_start"], s["char_end"]))
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

    pair_lines = []
    for p in filtered_pairs:
        m_a = p.get("method_a") or {}
        m_b = p.get("method_b") or {}
        pair_lines.append(
            f"\n#### {p['pair_id']}\n"
            f"- method_a: id={m_a.get('method_id','')} kind={m_a.get('kind','')} "
            f"status={m_a.get('validation_status','')} name={m_a.get('name','')!r}\n"
            f"- method_b: id={m_b.get('method_id','')} kind={m_b.get('kind','')} "
            f"status={m_b.get('validation_status','')} name={m_b.get('name','')!r}\n"
            f"- 本地扫描的关系触发句: {p.get('evidence_sentence_ids', [])}\n"
            f"- 本地关系类型提示 (仅供参考, 请独立判断): {p.get('relation_type_hint','')}"
        )
    pair_list = "\n".join(pair_lines)

    return prompts_strict.EXTRACTOR_USER_TEMPLATE_STRICT.format(
        paper_id=paper_id,
        canonical_title=meta["canonical_title"],
        paper_type=meta["paper_type"],
        primary_storage_domain=meta["primary_storage_domain"] or "(空)",
        technology_subfield=meta["technology_subfield"] or "(空)",
        pair_list=pair_list,
        sentence_pack=sentence_pack,
    )


def build_auditor_pack(proposals, methods_by_id, sentence_index, batch_size):
    blocks = []
    for prop in proposals:
        pair_id = prop.get("pair_id", "")
        from_id = prop.get("from_method_id", "")
        to_id = prop.get("to_method_id", "")
        verdict = prop.get("verdict", prop.get("relation", ""))
        sids = prop.get("relation_evidence_sentence_ids") or []
        m_from = methods_by_id.get(from_id, {})
        m_to = methods_by_id.get(to_id, {})
        ev_lines = []
        for sid in sids:
            s = sentence_index.get(sid)
            if s:
                text = s["sentence_text"].replace("\n", " ").strip()
                ev_lines.append(f"  - {sid} [{s['section_type']}]: 「{text}」")
            else:
                ev_lines.append(f"  - {sid} (⚠ NOT FOUND)")
        ev_block = "\n".join(ev_lines) if ev_lines else "  (无证据句)"
        blocks.append(
            f"\n#### {pair_id}\n"
            f"- from_method: id={from_id}, kind={m_from.get('kind','?')}, "
            f"name={m_from.get('name','')!r}\n"
            f"- to_method:   id={to_id}, kind={m_to.get('kind','?')}, "
            f"name={m_to.get('name','')!r}\n"
            f"- 提议 relation: {verdict}\n"
            f"- 关系证据句 (只这些):\n{ev_block}"
        )
    return prompts_strict.AUDITOR_USER_TEMPLATE_STRICT.format(
        batch_size=batch_size,
        proposal_list="\n".join(blocks),
    )


def call_llm(system, user, model, max_tokens=None):
    kw = {}
    if max_tokens is not None: kw["max_tokens"] = max_tokens
    r = llm_client.call_chat_with_backoff(
        system, user, model=model, request_pace_sec=1.0, **kw)
    usage = r.get("usage") or {}
    if not r["ok"]:
        return {}, False, r.get("error", ""), usage, ""
    text = r.get("text", "")
    ok, obj, err = parse_llm_json(text)
    return obj, ok, err, usage, text


def process_paper(pid, pairs_selected, model, cost_state):
    """跑一篇 (只用 pre-filtered pairs)."""
    t0 = time.time()
    methods, sentence_index = load_paper_methods(pid)
    methods_by_id = {m["method_id"]: m for m in methods if m["method_id"]}

    # 为每对加上 method_a, method_b 引用
    from_context = os.path.join(config.CORPUS_PP_V1_1_PAPER_TAXONOMY_CSV)
    tax_rows = {}
    if os.path.isfile(from_context):
        with open(from_context, "r", encoding="utf-8-sig") as f:
            tax_rows = {r["paper_id"]: r for r in csv.DictReader(f)}
    with open(config.CORPUS_PP_V1_1_PAPER_TYPES_CSV, "r",
                encoding="utf-8-sig") as f:
        pt_rows = {r["paper_id"]: r for r in csv.DictReader(f)}
    ctp = os.path.join(config.CORPUS_PP_V1_1_DIR, "canonical_titles.csv")
    ctitles = {}
    if os.path.isfile(ctp):
        with open(ctp, "r", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                ctitles[r["paper_id"]] = r.get("canonical_title", "")

    meta = {
        "canonical_title": ctitles.get(pid, pid),
        "paper_type": pt_rows.get(pid, {}).get("paper_type", "unclear"),
        "primary_storage_domain": tax_rows.get(pid, {}).get(
            "primary_storage_domain", ""),
        "technology_subfield": tax_rows.get(pid, {}).get("technology_subfield", ""),
    }

    stats = {"paper_id": pid, "n_pairs_input": len(pairs_selected),
             "n_relations_proposed": 0, "n_no_relation": 0,
             "n_accepted": 0, "n_candidate": 0, "n_rejected": 0,
             "extract_pt": 0, "extract_ct": 0,
             "audit_pt": 0, "audit_ct": 0,
             "audit_batches": 0, "audit_recovery_runs": 0,
             "audit_input_count": 0, "audit_covered_count": 0,
             "audit_missing_count": 0}

    # 组装 pair objects with method refs
    pair_objs = []
    for i, p in enumerate(pairs_selected, 1):
        m_a = methods_by_id.get(p.get("method_a_id"))
        m_b = methods_by_id.get(p.get("method_b_id"))
        if not m_a or not m_b:
            continue
        pair_objs.append({
            "pair_id": f"POS_{i:03d}",
            "method_a": m_a,
            "method_b": m_b,
            "evidence_sentence_ids": p.get("evidence_sentence_ids", []),
            "relation_type_hint": p.get("relation_type_hint", ""),
        })
    stats["n_pairs_input"] = len(pair_objs)

    if not pair_objs:
        return [], stats, methods_by_id, sentence_index

    # --- Extractor (single batch, since ≤10 pairs) ---
    system = prompts_strict.EXTRACTOR_SYSTEM_STRICT
    user = build_extractor_prompt(pid, meta, pair_objs, sentence_index)
    print(f"  [extractor] {len(pair_objs)} pairs, prompt {len(user)} chars",
            flush=True)
    obj, ok, err, usage, _ = call_llm(system, user, model=model,
                                          max_tokens=EXTRACT_MAX_TOKENS)
    stats["extract_pt"] = usage.get("prompt_tokens", 0)
    stats["extract_ct"] = usage.get("completion_tokens", 0)
    cost_state["cost"] += _est_cost(stats["extract_pt"], stats["extract_ct"])
    if cost_state["cost"] > BUDGET_HARD_STOP:
        raise RuntimeError(f"budget hard stop breached: ¥{cost_state['cost']:.2f}")
    if not ok:
        print(f"  [extractor] FAIL: {(err or '')[:100]}", flush=True)
        return [], stats, methods_by_id, sentence_index

    proposals = obj.get("relations") or []
    stats["n_relations_proposed"] = sum(1 for p in proposals
        if (p.get("verdict") or p.get("relation","")).upper() in evs.VALID_RELATIONS)
    stats["n_no_relation"] = sum(1 for p in proposals
        if (p.get("verdict") or p.get("relation","")).upper() == "NO_RELATION")
    print(f"  [extractor] proposals: {len(proposals)} "
            f"(proposed={stats['n_relations_proposed']}, "
            f"NO_REL={stats['n_no_relation']})", flush=True)

    # --- Auditor ---
    to_audit = [p for p in proposals
                if (p.get("verdict") or p.get("relation","")).upper()
                in evs.VALID_RELATIONS]
    audit_by_pair = {}
    if to_audit:
        def _build(props, bs):
            return build_auditor_pack(props, methods_by_id, sentence_index, bs)
        def _l(prompt):
            return call_llm(prompts_strict.AUDITOR_SYSTEM_STRICT,
                              prompt, model=model, max_tokens=EXTRACT_MAX_TOKENS)
        result = ab.run_audit_with_coverage(
            to_audit, methods_by_id, sentence_index,
            _build, _l, batch_size=AUDIT_BATCH_SIZE)
        audit_by_pair = result["audits_by_pair"]
        stats["audit_batches"] = result["batches_run"]
        stats["audit_recovery_runs"] = result["recovery_runs"]
        stats["audit_input_count"] = len(result["input_pair_ids"])
        stats["audit_covered_count"] = len(result["covered_pair_ids"])
        stats["audit_missing_count"] = len(result["missing_pair_ids"])
        au = result.get("audit_usage", {})
        stats["audit_pt"] = au.get("prompt_tokens", 0)
        stats["audit_ct"] = au.get("completion_tokens", 0)
        cost_state["cost"] += _est_cost(stats["audit_pt"], stats["audit_ct"])
        if cost_state["cost"] > BUDGET_HARD_STOP:
            raise RuntimeError(f"budget hard stop breached: "
                                 f"¥{cost_state['cost']:.2f}")
        print(f"  [auditor] {stats['audit_covered_count']}/"
                f"{stats['audit_input_count']} covered", flush=True)

    # --- Strict validation ---
    edges = []
    for prop in proposals:
        pair_id = prop.get("pair_id", "")
        rel_input = dict(prop)
        rel_input["verdict"] = (prop.get("verdict") or prop.get("relation", "")).upper()
        rel_input["pair_id"] = pair_id
        edge = evs.validate_and_classify_edge_strict(
            rel=rel_input,
            methods_by_id=methods_by_id,
            sentence_index=sentence_index,
            audit_by_pair=audit_by_pair,
        )
        edge["paper_id"] = pid
        edge["pair_id"] = pair_id
        edges.append(edge)

    for e in edges:
        s = e.get("validation_status", "")
        if s == "accepted": stats["n_accepted"] += 1
        elif s == "candidate": stats["n_candidate"] += 1
        else: stats["n_rejected"] += 1

    return edges, stats, methods_by_id, sentence_index


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError): pass

    try:
        _ = llm_client.get_api_key()
        print("MOONSHOT_API_KEY configured: yes")
    except RuntimeError:
        print("MOONSHOT_API_KEY configured: no")
        return 2

    model = os.environ.get("MOONSHOT_MODEL", llm_client.DEFAULT_MODEL)
    top_pids = load_top3_papers()
    if len(top_pids) < 3:
        print(f"ERROR: only {len(top_pids)} top papers, need 3")
        return 3

    by_paper_all = load_all_candidate_pairs()

    # 组装每篇的 top-N 局部对 (≤10 对, 全局 ≤30)
    selected_by_paper = {}
    total = 0
    for pid in top_pids:
        raw = by_paper_all.get(pid, [])
        # dedupe pair (a,b)
        seen = set()
        unique = []
        for r in raw:
            key = tuple(sorted([r["method_a_id"], r["method_b_id"]]))
            if key in seen: continue
            seen.add(key)
            unique.append(r)
        # Take top-N
        remaining = MAX_TOTAL_PAIRS - total
        take = min(TOP_N_PAIRS_PER_PAPER, len(unique), remaining)
        selected_by_paper[pid] = unique[:take]
        total += take
        print(f"  {pid[:30]}: {take} pairs (of {len(unique)} unique)")
    print(f"total pairs to Stage B: {total}")

    cost_state = {"cost": 0.0}
    all_edges = []
    all_stats = []
    for pid in top_pids:
        print(f"\n=== [{pid}] ===")
        try:
            edges, stats, mbid, sidx = process_paper(
                pid, selected_by_paper[pid], model, cost_state)
        except RuntimeError as e:
            print(f"  HALT: {e}")
            return 4
        except Exception as e:
            import traceback
            print(f"  ERROR: {type(e).__name__}: {e}")
            print(traceback.format_exc())
            return 5
        all_edges.extend(edges)
        all_stats.append(stats)
        print(f"  → acc={stats['n_accepted']} cand={stats['n_candidate']} "
                f"rej={stats['n_rejected']} cost=¥{cost_state['cost']:.3f}")

    # --- write outputs ---
    accepted = [e for e in all_edges if e.get("validation_status") == "accepted"]
    candidate = [e for e in all_edges if e.get("validation_status") == "candidate"]
    rejected = [e for e in all_edges if e.get("validation_status") == "rejected"]

    edge_fields = [
        "paper_id", "pair_id", "relation",
        "from_method_id", "to_method_id",
        "from_method_name", "to_method_name",
        "relation_evidence_sentence_ids", "evidence_missing_ids",
        "evidence_quote", "evidence_section", "evidence_para_id",
        "explicit_trigger_hit", "direction_basis",
        "audit_linkage_type", "audit_endpoint_linkage",
        "audit_support", "audit_direction", "audit_relation_check",
        "audit_suggested_relation", "audit_reason",
        "validation_status", "rejected_reason", "confidence_llm",
    ]
    _write_csv(os.path.join(OUT_DIR, "positive_case_edges_accepted.csv"),
                edge_fields, accepted)
    _write_csv(os.path.join(OUT_DIR, "positive_case_edges_rejected.csv"),
                edge_fields, rejected)
    if candidate:
        _write_csv(os.path.join(OUT_DIR, "positive_case_edges_candidate.csv"),
                    edge_fields, candidate)

    # --- summary + evidence ---
    print("\n" + "=" * 70)
    print(f"positive Stage B done:")
    print(f"  processed: {len(all_stats)} papers, "
            f"total pairs: {sum(s['n_pairs_input'] for s in all_stats)}")
    print(f"  accepted: {len(accepted)}, "
            f"candidate: {len(candidate)}, rejected: {len(rejected)}")
    print(f"  total est cost: ¥{cost_state['cost']:.3f} / ¥{BUDGET_HARD_STOP}")
    print(f"  outputs at: {OUT_DIR}")

    # Serialize per-paper details for downstream MD generation
    with open(os.path.join(OUT_DIR, "run_summary.json"),
                "w", encoding="utf-8") as f:
        json.dump({
            "top_pids": top_pids,
            "selected_per_paper": {k: len(v) for k, v in selected_by_paper.items()},
            "stats": all_stats,
            "cost": cost_state["cost"],
        }, f, ensure_ascii=False, indent=2)

    return 0


if __name__ == "__main__":
    sys.exit(main())
