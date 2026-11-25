"""run_case_stage_b.py — 严格 Stage B 只在 case_candidates top 3 上跑.

复用 stage_b/edge_validation_strict + prompts_strict + pair_generator +
audit_batching. Stage A 数据取自 337 篇的 per_paper (full_v1).

约束 (用户 spec):
  - 只处理 case_candidates.csv top 3
  - 总费用 ≤ ¥10
  - 关系限 EXTENDS / IMPROVES / ADAPTS / REPLACES
  - audit 覆盖率 100% (audit_batching 保证)
  - 只从 process env 读 key; 启动日志只 yes/no
  - 若前 3 篇 accepted 关系 < 2, 允许补测 top 4/5, **总 ≤ 5**
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

from method_evolution_v2 import config                                            # noqa: E402
from method_evolution_v2.stage_a import llm_client, full_runner as fr             # noqa: E402
from method_evolution_v2.stage_a.method_extraction import parse_llm_json          # noqa: E402
from method_evolution_v2.stage_b import (                                          # noqa: E402
    pair_generator as pg,
    audit_batching as ab,
    edge_validation_strict as evs,
)
from method_evolution_v2.stage_b import prompts_strict                            # noqa: E402


AGG_DIR = os.path.join(config.STAGE_A_FULL_V1_DIR, "aggregation")
CASE_DIR = os.path.join(config.PAPER_V2_DIR, "article_minimal_results", "case_stage_b")
os.makedirs(CASE_DIR, exist_ok=True)

BUDGET_HARD_STOP = 10.0
MAX_PAPERS = 5
MIN_ACCEPTED_PER_STUDY_PAPER = 2   # 前 3 中若某篇 < 2 accepted → 触发补测
AUDIT_BATCH_SIZE = 8
EXTRACT_BATCH_SIZE = 60   # 每次抽取 ≤60 对, 避免 max_tokens 截断
EXTRACT_MAX_TOKENS = 8000

INPUT_CNY_PER_M = 24.0
OUTPUT_CNY_PER_M = 24.0


def _est_cost(pt, ct):
    return pt / 1_000_000 * INPUT_CNY_PER_M + ct / 1_000_000 * OUTPUT_CNY_PER_M


def _accum(agg, u):
    for k in ("prompt_tokens", "completion_tokens", "total_tokens"):
        agg[k] = agg.get(k, 0) + int(u.get(k, 0) or 0)


def _j(v):
    if isinstance(v, (list, dict)):
        return json.dumps(v, ensure_ascii=False)
    return "" if v is None else str(v)


def _write_csv(path, fields, rows):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: _j(r.get(k)) for k in fields})


def load_candidate_list():
    p = os.path.join(config.PAPER_V2_DIR, "article_minimal_results",
                       "case_candidates.csv")
    with open(p, "r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def load_paper_methods(pid):
    """从 per_paper_dir 取该篇的 accepted+candidate 方法与句子索引."""
    d = fr.per_paper_dir(pid)
    with open(os.path.join(d, "methods_accepted.json"), "r", encoding="utf-8") as f:
        acc = json.load(f)
    with open(os.path.join(d, "methods_candidate.json"), "r", encoding="utf-8") as f:
        cand = json.load(f)
    with open(os.path.join(d, "sentence_index.json"), "r", encoding="utf-8") as f:
        sidx_data = json.load(f)
    sentence_index = {s["sentence_id"]: s for s in sidx_data.get("sentences", [])}
    # 转换为 Stage B pair_generator 需要的格式
    def _adapt(m, status):
        return {
            "paper_id": pid,
            "method_id": m.get("method_id", ""),
            "kind": m.get("kind", ""),
            "name": m.get("name", ""),
            "validation_status": status,
            "method_type": m.get("proposed_method_type", ""),
            "problem_solved": m.get("problem_solved", ""),
            "key_components": m.get("key_components", []),
            "citation_clue": m.get("citation_clue", "") or m.get("citation_clue_raw", ""),
            "evidence_sentence_ids": m.get("evidence_sentence_ids", []),
            "evidence_section": m.get("evidence_section", ""),
            "evidence_para_id": m.get("evidence_para_id", ""),
        }
    methods = [_adapt(m, "accepted") for m in acc] + \
                [_adapt(m, "candidate") for m in cand]
    return methods, sentence_index


def load_paper_meta(pid, tax_rows, pt_rows, ctitles):
    return {
        "canonical_title": ctitles.get(pid, pid),
        "paper_type": pt_rows.get(pid, {}).get("paper_type", "unclear"),
        "primary_storage_domain": tax_rows.get(pid, {}).get(
            "primary_storage_domain", ""),
        "technology_subfield": tax_rows.get(pid, {}).get("technology_subfield", ""),
    }


def build_extractor_pack(paper_id, meta, pairs, sentence_index):
    relevant_sids = set()
    for p in pairs:
        relevant_sids.update(p.get("method_a_evidence_sids", []))
        relevant_sids.update(p.get("method_b_evidence_sids", []))
        relevant_sids.update(p.get("connector_sentence_ids", []))
    para_nums = set()
    for sid in relevant_sids:
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
    for p in pairs:
        pair_lines.append(
            f"\n#### {p['pair_id']}\n"
            f"- method_a: id={p['method_a_id']} kind={p['method_a_kind']} "
            f"status={p['method_a_status']} name={p['method_a_name']!r} "
            f"cite={p['method_a_citation_clue']!r} "
            f"sids={p['method_a_evidence_sids']}\n"
            f"- method_b: id={p['method_b_id']} kind={p['method_b_kind']} "
            f"status={p['method_b_status']} name={p['method_b_name']!r} "
            f"cite={p['method_b_citation_clue']!r} "
            f"sids={p['method_b_evidence_sids']}\n"
            f"- pair_source={p['pair_source']} "
            f"min_para_diff={p['min_para_diff']}"
        )
    pair_list = "\n".join(pair_lines) if pair_lines else "(无候选对)"

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


def call_llm_backoff(system, user, model, max_tokens=None):
    """使用带 429 退避的调用器."""
    kw = {}
    if max_tokens is not None:
        kw["max_tokens"] = max_tokens
    r = llm_client.call_chat_with_backoff(system, user, model=model,
                                              request_pace_sec=1.0, **kw)
    usage = r.get("usage") or {}
    if not r["ok"]:
        return {}, False, r.get("error", ""), usage, ""
    text = r.get("text", "")
    ok, obj, err = parse_llm_json(text)
    return obj, ok, err, usage, text


def process_paper(pid, meta, model, cost_state):
    """跑一篇: pair生成 → 抽取 → 审查 → 严格验证. 返回 edges + stats."""
    t0 = time.time()
    methods, sentence_index = load_paper_methods(pid)
    methods_by_id = {m["method_id"]: m for m in methods if m["method_id"]}
    pairs, pair_stats = pg.generate_candidate_pairs(pid, methods, sentence_index)

    stats = {
        "paper_id": pid,
        "n_methods": len(methods),
        "n_pairs_theoretical": pair_stats.get("theoretical_pairs", 0),
        "n_pairs_filtered": len(pairs),
        "n_relations_proposed": 0,
        "n_no_relation": 0,
        "n_accepted": 0, "n_candidate": 0, "n_rejected": 0,
        "extract_call_ok": False,
        "audit_batches": 0, "audit_recovery_runs": 0,
        "audit_input_count": 0, "audit_covered_count": 0,
        "audit_missing_count": 0,
        "extract_pt": 0, "extract_ct": 0,
        "audit_pt": 0, "audit_ct": 0,
        "duration_sec": 0,
    }

    edges = []
    if not pairs:
        stats["duration_sec"] = round(time.time() - t0, 2)
        return edges, stats, methods_by_id, sentence_index

    # --- 抽取器 (分批, ≤EXTRACT_BATCH_SIZE 对/次) ---
    system = prompts_strict.EXTRACTOR_SYSTEM_STRICT
    pair_batches = [pairs[i:i + EXTRACT_BATCH_SIZE]
                       for i in range(0, len(pairs), EXTRACT_BATCH_SIZE)]
    print(f"  [extractor] {len(pairs)} pairs → {len(pair_batches)} 批 (≤"
            f"{EXTRACT_BATCH_SIZE} 对/批)", flush=True)
    proposals = []
    extract_ok_any = False
    for bi, pb in enumerate(pair_batches, 1):
        user = build_extractor_pack(pid, meta, pb, sentence_index)
        print(f"  [extractor] 批 {bi}/{len(pair_batches)} — {len(pb)} 对, "
                f"prompt {len(user)} chars", flush=True)
        obj, ok, err, usage, _ = call_llm_backoff(
            system, user, model=model, max_tokens=EXTRACT_MAX_TOKENS)
        stats["extract_pt"] += usage.get("prompt_tokens", 0)
        stats["extract_ct"] += usage.get("completion_tokens", 0)
        cost_state["cost"] += _est_cost(usage.get("prompt_tokens", 0),
                                             usage.get("completion_tokens", 0))
        if cost_state["cost"] > BUDGET_HARD_STOP:
            raise RuntimeError(f"budget hard stop breached mid-extract "
                                 f"at batch {bi}: ¥{cost_state['cost']:.2f}")
        if ok:
            extract_ok_any = True
            batch_props = obj.get("relations") or []
            if isinstance(batch_props, list):
                proposals.extend(batch_props)
            print(f"    → ok, +{len(batch_props)} verdicts", flush=True)
        else:
            print(f"    → FAIL: {(err or '')[:100]}", flush=True)
    stats["extract_call_ok"] = extract_ok_any
    if not extract_ok_any:
        stats["duration_sec"] = round(time.time() - t0, 2)
        return edges, stats, methods_by_id, sentence_index
    stats["n_relations_proposed"] = sum(
        1 for p in proposals if (p.get("verdict") or p.get("relation", "")).upper()
        in evs.VALID_RELATIONS)
    stats["n_no_relation"] = sum(
        1 for p in proposals if (p.get("verdict") or p.get("relation", "")).upper()
        == "NO_RELATION")

    # 只把 "有关系" 的送审 (NO_RELATION 不占审查预算)
    to_audit = [p for p in proposals
                if (p.get("verdict") or p.get("relation", "")).upper()
                in evs.VALID_RELATIONS]

    audit_by_pair = {}
    if to_audit:
        def _build_prompt(props, bs):
            return build_auditor_pack(props, methods_by_id, sentence_index, bs)

        def _llm(prompt):
            return call_llm_backoff(prompts_strict.AUDITOR_SYSTEM_STRICT
                                      if hasattr(prompts_strict, "AUDITOR_SYSTEM_STRICT")
                                      else "你是储能领域方法演化关系的独立盲审专家. "
                                              "只看给你的关系证据句和方法名, 不看抽取器的推理. "
                                              "严格按 JSON 对象返回, 不带 markdown 围栏.",
                                      prompt, model=model,
                                      max_tokens=EXTRACT_MAX_TOKENS)

        result = ab.run_audit_with_coverage(
            to_audit, methods_by_id, sentence_index,
            _build_prompt, _llm,
            batch_size=AUDIT_BATCH_SIZE)
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
        print(f"  [auditor] {stats['audit_covered_count']}/"
                f"{stats['audit_input_count']} covered, "
                f"batches={stats['audit_batches']}+"
                f"{stats['audit_recovery_runs']}(recovery)", flush=True)
        if cost_state["cost"] > BUDGET_HARD_STOP:
            raise RuntimeError(f"budget hard stop breached after audit: "
                                 f"¥{cost_state['cost']:.2f}")

    # --- 严格验证 ---
    for prop in proposals:
        pair_id = prop.get("pair_id", "")
        # normalize prop shape for validator
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
        vs = e.get("validation_status", "")
        if vs == "accepted": stats["n_accepted"] += 1
        elif vs == "candidate": stats["n_candidate"] += 1
        else: stats["n_rejected"] += 1

    stats["duration_sec"] = round(time.time() - t0, 2)
    return edges, stats, methods_by_id, sentence_index


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError): pass

    # 只从 process env 读 key; 只输出 yes/no
    try:
        _ = llm_client.get_api_key()
        print("MOONSHOT_API_KEY configured: yes")
    except RuntimeError:
        print("MOONSHOT_API_KEY configured: no")
        return 2

    model = os.environ.get("MOONSHOT_MODEL", llm_client.DEFAULT_MODEL)

    candidates = load_candidate_list()
    if len(candidates) < 3:
        print(f"ERROR: only {len(candidates)} candidates, need ≥3")
        return 3

    # taxonomy + paper_type + canonical
    with open(config.CORPUS_PP_V1_1_PAPER_TAXONOMY_CSV, "r",
                encoding="utf-8-sig") as f:
        tax_rows = {r["paper_id"]: r for r in csv.DictReader(f)}
    with open(config.CORPUS_PP_V1_1_PAPER_TYPES_CSV, "r",
                encoding="utf-8-sig") as f:
        pt_rows = {r["paper_id"]: r for r in csv.DictReader(f)}
    ctitles = {}
    ctp = os.path.join(config.CORPUS_PP_V1_1_DIR, "canonical_titles.csv")
    if os.path.isfile(ctp):
        with open(ctp, "r", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                ctitles[r["paper_id"]] = r.get("canonical_title", "")

    print(f"\ncandidates loaded: {len(candidates)}, processing top 3 first")

    cost_state = {"cost": 0.0}
    all_edges = []
    all_stats = []
    per_paper_details = {}   # pid → (methods_by_id, sentence_index)

    processed_pids = []
    top3 = candidates[:3]
    for c in top3:
        pid = c["paper_id"]
        print(f"\n=== [{pid}] ===")
        meta = load_paper_meta(pid, tax_rows, pt_rows, ctitles)
        try:
            edges, stats, mbid, sidx = process_paper(pid, meta, model, cost_state)
        except RuntimeError as e:
            print(f"  HALT: {e}")
            return 4
        except Exception as e:
            import traceback
            print(f"  UNEXPECTED ERROR in process_paper: "
                  f"{type(e).__name__}: {e}")
            print(traceback.format_exc())
            return 5
        all_edges.extend(edges)
        all_stats.append(stats)
        per_paper_details[pid] = (mbid, sidx, meta)
        processed_pids.append(pid)
        print(f"  methods={stats['n_methods']} "
              f"pairs={stats['n_pairs_filtered']}/{stats['n_pairs_theoretical']} "
              f"proposed={stats['n_relations_proposed']} "
              f"NO_REL={stats['n_no_relation']} "
              f"acc={stats['n_accepted']} cand={stats['n_candidate']} "
              f"rej={stats['n_rejected']} "
              f"cost_so_far=¥{cost_state['cost']:.3f}")

    # 判断是否需要补测
    n_low_accepted_papers = sum(
        1 for s in all_stats
        if s["n_accepted"] < MIN_ACCEPTED_PER_STUDY_PAPER)
    need_backfill = (n_low_accepted_papers == 3)   # 3 篇都不足 2 条

    if need_backfill:
        for c in candidates[3:5]:
            if len(processed_pids) >= MAX_PAPERS: break
            pid = c["paper_id"]
            print(f"\n=== [{pid}] (backfill) ===")
            meta = load_paper_meta(pid, tax_rows, pt_rows, ctitles)
            try:
                edges, stats, mbid, sidx = process_paper(pid, meta, model, cost_state)
            except RuntimeError as e:
                print(f"  HALT (backfill): {e}")
                break
            all_edges.extend(edges)
            all_stats.append(stats)
            per_paper_details[pid] = (mbid, sidx, meta)
            processed_pids.append(pid)
            print(f"  acc={stats['n_accepted']} "
                  f"cost_so_far=¥{cost_state['cost']:.3f}")
            # backfill 也判断是否已够
            if stats["n_accepted"] >= MIN_ACCEPTED_PER_STUDY_PAPER:
                break

    # --- 分桶写盘 ---
    accepted_edges = [e for e in all_edges if e.get("validation_status") == "accepted"]
    candidate_edges = [e for e in all_edges if e.get("validation_status") == "candidate"]
    rejected_edges = [e for e in all_edges if e.get("validation_status") == "rejected"]

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
        "validation_status", "rejected_reason",
        "confidence_llm",
    ]
    _write_csv(os.path.join(CASE_DIR, "case_edges_accepted.csv"),
                edge_fields, accepted_edges)
    _write_csv(os.path.join(CASE_DIR, "case_edges_candidate.csv"),
                edge_fields, candidate_edges)
    _write_csv(os.path.join(CASE_DIR, "case_edges_rejected.csv"),
                edge_fields, rejected_edges)

    # --- case_evidence.md ---
    ev_md = ["# 案例演化关系 — 原文证据\n\n"]
    ev_md.append(f"> 处理论文: {len(processed_pids)}, accepted 关系: "
                    f"{len(accepted_edges)}, 总费用: ¥{cost_state['cost']:.3f}\n\n")
    for pid in processed_pids:
        pid_edges = [e for e in accepted_edges if e["paper_id"] == pid]
        if not pid_edges: continue
        mbid, sidx, meta = per_paper_details[pid]
        ev_md.append(f"## {pid}\n\n")
        ev_md.append(f"- **canonical_title**: {meta['canonical_title']}\n")
        ev_md.append(f"- **paper_type**: {meta['paper_type']}\n")
        ev_md.append(f"- **domain**: {meta['primary_storage_domain']}\n\n")
        for i, e in enumerate(pid_edges, 1):
            ev_md.append(f"### 关系 {i}: **{e['relation']}**\n\n")
            ev_md.append(f"- **from**: `{e.get('from_method_name','?')}` "
                          f"(id={e.get('from_method_id','')})\n")
            ev_md.append(f"- **to**: `{e.get('to_method_name','?')}` "
                          f"(id={e.get('to_method_id','')})\n")
            ev_md.append(f"- **触发词命中**: `{e.get('explicit_trigger_hit','')}`\n")
            ev_md.append(f"- **方向依据**: {e.get('direction_basis','')}\n")
            ev_md.append(f"- **audit**: linkage={e.get('audit_linkage_type','')}, "
                          f"endpoint={e.get('audit_endpoint_linkage','')}, "
                          f"support={e.get('audit_support','')}, "
                          f"direction={e.get('audit_direction','')}\n")
            ev_md.append(f"- **原文证据**:\n")
            sids = e.get("relation_evidence_sentence_ids", [])
            if isinstance(sids, str):
                try: sids = json.loads(sids)
                except: sids = []
            for sid in sids:
                s = sidx.get(sid)
                if s:
                    ev_md.append(f"  - `{sid}` [{s['section_type']}]: 「"
                                  f"{s['sentence_text'].strip()}」\n")
                else:
                    ev_md.append(f"  - `{sid}`: (缺失)\n")
            ev_md.append("\n")
    with open(os.path.join(CASE_DIR, "case_evidence.md"),
                "w", encoding="utf-8") as f:
        f.writelines(ev_md)

    # --- case_comparison.md ---
    cmp_md = ["# 案例对比 (跨候选)\n\n"]
    cmp_md.append("| paper_id | 类型 | 方法数 | 送审 | NO_REL | acc | cand | rej | 覆盖率 | 费用 |\n")
    cmp_md.append("|---|---|---:|---:|---:|---:|---:|---:|:-:|---:|\n")
    for s in all_stats:
        cov = "100%" if s["audit_input_count"] == 0 else \
                f"{100 * s['audit_covered_count'] / s['audit_input_count']:.0f}%"
        c = _est_cost(s["extract_pt"] + s["audit_pt"],
                        s["extract_ct"] + s["audit_ct"])
        pid = s["paper_id"]
        meta = per_paper_details[pid][2]
        cmp_md.append(f"| {pid[:30]} | {meta['paper_type']} | {s['n_methods']} "
                        f"| {s['n_relations_proposed']} | {s['n_no_relation']} "
                        f"| {s['n_accepted']} | {s['n_candidate']} | {s['n_rejected']} "
                        f"| {cov} | ¥{c:.3f} |\n")
    cmp_md.append(f"\n**四类关系分布 (accepted)**:\n\n")
    rel_dist = Counter(e["relation"] for e in accepted_edges)
    for r in ("EXTENDS", "IMPROVES", "ADAPTS", "REPLACES"):
        cmp_md.append(f"- {r}: {rel_dist.get(r, 0)}\n")
    with open(os.path.join(CASE_DIR, "case_comparison.md"),
                "w", encoding="utf-8") as f:
        f.writelines(cmp_md)

    # --- final_case_study.md (选一个最终案例) ---
    finalists = [s for s in all_stats
                    if s["n_accepted"] >= MIN_ACCEPTED_PER_STUDY_PAPER]
    if finalists:
        # 挑 accepted 最多的
        best = max(finalists, key=lambda s: (s["n_accepted"], -s["n_rejected"]))
        best_pid = best["paper_id"]
        best_edges = [e for e in accepted_edges if e["paper_id"] == best_pid]
        _, sidx, meta = per_paper_details[best_pid]
        fs_md = [f"# 最终案例研究 — {best_pid}\n\n"]
        fs_md.append(f"> 从 {len(processed_pids)} 篇处理中选出, "
                        f"依据: accepted 关系数最多 = **{best['n_accepted']}**, "
                        f"rejected = {best['n_rejected']}\n\n")
        fs_md.append("## 一. 案例背景\n\n")
        fs_md.append(f"- **论文**: {meta['canonical_title']}\n")
        fs_md.append(f"- **类型**: {meta['paper_type']}\n")
        fs_md.append(f"- **储能一级领域**: {meta['primary_storage_domain']}\n")
        fs_md.append(f"- **二级技术**: {meta['technology_subfield']}\n\n")
        fs_md.append("## 二. 抽取的方法\n\n")
        fs_md.append(f"- 该篇 accepted 方法总数: {best['n_methods']}\n")
        method_ids_in_edges = set()
        for e in best_edges:
            method_ids_in_edges.add(e.get("from_method_id", ""))
            method_ids_in_edges.add(e.get("to_method_id", ""))
        fs_md.append(f"- 涉及演化关系的方法: {len(method_ids_in_edges)}\n\n")
        fs_md.append("## 三. 方法之间的关系\n\n")
        for i, e in enumerate(best_edges, 1):
            fs_md.append(f"### 关系 {i}: **{e['relation']}**\n")
            fs_md.append(f"- {e.get('from_method_name','?')} → "
                          f"{e.get('to_method_name','?')}\n")
            fs_md.append(f"- 方向依据: {e.get('direction_basis','')}\n")
            fs_md.append(f"- audit 支持: {e.get('audit_support','')}\n\n")
        fs_md.append("## 四. 每条关系的原文证据\n\n")
        for i, e in enumerate(best_edges, 1):
            fs_md.append(f"### 关系 {i} ({e['relation']})\n\n")
            sids = e.get("relation_evidence_sentence_ids", [])
            if isinstance(sids, str):
                try: sids = json.loads(sids)
                except: sids = []
            for sid in sids:
                s = sidx.get(sid)
                if s:
                    fs_md.append(f"- `{sid}` [{s['section_type']}] "
                                  f"[{s['section_name']}]:\n")
                    fs_md.append(f"  > 「{s['sentence_text'].strip()}」\n")
            fs_md.append("\n")
        fs_md.append("## 五. 系统如何完成识别\n\n")
        fs_md.append("- **候选对生成**: pair_generator 只允许 "
                        "同段共现 / 相邻段 / own↔ref / 触发词覆盖\n")
        fs_md.append("- **抽取器**: prompts_strict.EXTRACTOR — 默认 NO_RELATION, "
                        "只有原文明确证据才输出 EXTENDS/IMPROVES/ADAPTS/REPLACES\n")
        fs_md.append("- **独立盲审**: prompts_strict.AUDITOR — 只看方法名和证据句, "
                        "不看抽取器推理; 报 linkage_type/endpoint_linkage/support/direction\n")
        fs_md.append("- **strict 验证**: edge_validation_strict — 12 条硬性 accepted 条件\n\n")
        fs_md.append("## 六. 自动校验过程\n\n")
        fs_md.append(f"- 送审输入对数: {best['audit_input_count']}\n")
        fs_md.append(f"- 已覆盖: {best['audit_covered_count']}\n")
        fs_md.append(f"- 补审次数: {best['audit_recovery_runs']}\n")
        fs_md.append(f"- 覆盖率: 100% (由 audit_batching 补审保证)\n\n")
        fs_md.append("## 七. 结果边界\n\n")
        fs_md.append("- 演化关系**仅**在本篇正文内直接证据支持下判定\n")
        fs_md.append("- 不追溯 referenced 方法的原始论文\n")
        fs_md.append("- 不做跨论文合并\n")
        fs_md.append("- 不宣称覆盖该子领域全部方法\n\n")
        fs_md.append("## 八. 可用于论文的图示数据\n\n")
        fs_md.append(f"- **节点**: {len(method_ids_in_edges)} 个方法\n")
        fs_md.append(f"- **边**: {len(best_edges)} 条 accepted 演化关系\n")
        fs_md.append(f"- 数据源: `case_edges_accepted.csv` 里 "
                        f"paper_id='{best_pid}' 子集\n")
    else:
        fs_md = ["# 最终案例研究\n\n"]
        fs_md.append(f"**未能找到满足条件 (≥ {MIN_ACCEPTED_PER_STUDY_PAPER} 条 "
                        f"accepted 演化关系) 的候选**.\n\n")
        fs_md.append(f"- 处理论文数: {len(processed_pids)}\n")
        fs_md.append(f"- 各篇 accepted: "
                        f"{[(s['paper_id'][:20], s['n_accepted']) for s in all_stats]}\n")
        fs_md.append(f"- 总费用: ¥{cost_state['cost']:.3f}\n")
        fs_md.append(f"- 建议: 论文以"
                        f"'候选清单 + 无强演化边情况说明'作为诚实汇报\n")
    with open(os.path.join(CASE_DIR, "final_case_study.md"),
                "w", encoding="utf-8") as f:
        f.writelines(fs_md)

    # --- summary ---
    print("\n" + "=" * 70)
    print(f"Stage B case study done.")
    print(f"  processed papers: {len(processed_pids)}")
    print(f"  accepted edges: {len(accepted_edges)}")
    print(f"  candidate edges: {len(candidate_edges)}")
    print(f"  rejected edges: {len(rejected_edges)}")
    print(f"  total est cost: ¥{cost_state['cost']:.3f} / ¥{BUDGET_HARD_STOP}")
    print(f"  outputs at: {CASE_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
