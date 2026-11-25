"""run_stage_b_test_10_strict.py — Stage B v2 strict driver.

对 v04 的修正 (spec 一/二/三/四/五/六):
  - 抽取器默认 NO_RELATION, 加负例
  - 审查器加 linkage_type / endpoint_linkage / coreference_explanation
  - 审查以 ≤8 pair/batch 拆分, 覆盖缺失补调一次
  - 11 条 accepted 硬性条件
  - 使用 Stage A v03 的方法(不重新调 Stage A)
  - 输出到 test_run_05_stage_b_strict/ (不覆盖 test_run_04)

API:
  - 仅 Moonshot; MOONSHOT_API_KEY 环境变量
  - 总调用 ≤30 (10 抽取 + 至多 20 审查, 含 recovery)
  - 费用 ≤¥20 (硬门限)
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
    audit_batching as ab,
    edge_validation_strict as evs,
    STAGE_B_VERSION,
)
from method_evolution_v2.stage_b import prompts_strict                          # noqa: E402


MAX_CALLS_TOTAL = 30
BUDGET_HARD_STOP_CNY = 20.0
AUDIT_BATCH_SIZE = 8

INPUT_CNY_PER_M = 24.0
OUTPUT_CNY_PER_M = 24.0

# 估算 (基于 v04 实际)
EST_EXTRACT_INPUT = 15000
EST_EXTRACT_OUTPUT = 2500
EST_AUDIT_INPUT_PER_BATCH = 4000
EST_AUDIT_OUTPUT_PER_BATCH = 2000


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
    "extractor_verdict", "relation",
    "from_method_id", "to_method_id",
    "from_method_name", "to_method_name",
    "relation_evidence_sentence_ids", "evidence_missing_ids", "evidence_spans",
    "evidence_quote", "evidence_section", "evidence_para_id",
    "evidence_char_start", "evidence_char_end",
    "explicit_trigger_hit",
    "heuristic_alias_flag", "heuristic_alias_reason",
    "direction_basis", "relation_reason", "extractor_note",
    "confidence_llm",
    "audit_linkage_type", "audit_endpoint_linkage",
    "audit_coreference_explanation",
    "audit_support", "audit_direction", "audit_relation_check",
    "audit_suggested_relation", "audit_reason",
    "endpoint_a_status", "endpoint_b_status",
    "from_year", "to_year", "temporal_status",
    "validation_status", "rejected_reason",
]

PER_PAPER_FIELDS = [
    "paper_id", "canonical_title", "paper_type",
    "n_methods", "n_theoretical_pairs", "n_filtered_pairs",
    "n_relations_proposed", "n_no_relation_verdicts",
    "n_accepted_edges", "n_candidate_edges", "n_rejected_edges",
    "extract_call_ok", "audit_batches", "audit_recovery_runs",
    "audit_input_count", "audit_covered_count", "audit_missing_count",
    "audit_coverage_rate",
    "extract_prompt_tokens", "extract_completion_tokens",
    "audit_prompt_tokens", "audit_completion_tokens",
    "estimated_cost_cny", "duration_sec", "note",
]

DIFF_FIELDS = [
    "paper_id",
    "v04_extracted", "v05_extracted",
    "v04_accepted", "v05_accepted",
    "v04_candidate", "v05_candidate",
    "v04_rejected", "v05_rejected",
    "v04_wrong_type", "v05_wrong_type",
    "v04_audit_missing", "v05_audit_missing",
    "v04_accepted_edges_kept", "v04_accepted_edges_dropped",
    "v05_new_accepted",
]


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
# Stage A / taxonomy 加载
# ============================================================

def load_stage_a_methods():
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


def load_v04_edges():
    """加载 v04 结果供 diff."""
    out = defaultdict(list)
    for label, path in [
        ("accepted", config.STAGE_B_TEST_04_EDGES_ACCEPTED),
        ("candidate", config.STAGE_B_TEST_04_EDGES_CANDIDATE),
        ("rejected", config.STAGE_B_TEST_04_EDGES_REJECTED),
    ]:
        if not os.path.isfile(path):
            continue
        for r in _load_csv_rows(path):
            r["_v04_bucket"] = label
            out[r.get("paper_id", "")].append(r)
    return out


# ============================================================
# LLM 输入构造
# ============================================================

def build_extractor_pack(paper_id, canonical_title, paper_type,
                          primary_domain, subfield, pairs, sentence_index):
    relevant_sids = set()
    for pair in pairs:
        relevant_sids.update(pair.get("method_a_evidence_sids", []))
        relevant_sids.update(pair.get("method_b_evidence_sids", []))
        relevant_sids.update(pair.get("connector_sentence_ids", []))

    para_nums = set()
    for sid in relevant_sids:
        parsed = pg.parse_sentence_id(sid)
        if parsed:
            para_nums.add(parsed[1])
    for sid, s in sentence_index.items():
        parsed = pg.parse_sentence_id(sid)
        if parsed and parsed[1] in para_nums:
            relevant_sids.add(sid)

    relevant = sorted(
        (sentence_index[sid] for sid in relevant_sids if sid in sentence_index),
        key=lambda s: (s["char_start"], s["char_end"]),
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

    pair_lines = []
    for p in pairs:
        pair_lines.append(
            f"\n#### {p['pair_id']}\n"
            f"- method_a: id={p['method_a_id']} kind={p['method_a_kind']} "
            f"status={p['method_a_status']} name={p['method_a_name']!r} "
            f"cite={p['method_a_citation_clue']!r} sids={p['method_a_evidence_sids']}\n"
            f"- method_b: id={p['method_b_id']} kind={p['method_b_kind']} "
            f"status={p['method_b_status']} name={p['method_b_name']!r} "
            f"cite={p['method_b_citation_clue']!r} sids={p['method_b_evidence_sids']}\n"
            f"- pair_source={p['pair_source']} min_para_diff={p['min_para_diff']}"
        )
    pair_list = "\n".join(pair_lines) if pair_lines else "(无候选对)"

    return prompts_strict.EXTRACTOR_USER_TEMPLATE_STRICT.format(
        paper_id=paper_id,
        canonical_title=canonical_title,
        paper_type=paper_type or "unclear",
        primary_storage_domain=primary_domain or "(空)",
        technology_subfield=subfield or "(空)",
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


def call_and_parse(system, user, model):
    r = llm_client.call_chat(system, user, model=model)
    usage = r.get("usage") or {}
    if not r["ok"]:
        return {}, False, r.get("error", ""), usage, ""
    text = r.get("text", "")
    ok, obj, err = parse_llm_json(text)
    return obj, ok, err, usage, text


# ============================================================
# 主
# ============================================================

def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    try:
        key = llm_client.get_api_key()
    except RuntimeError as e:
        print("PRE-FLIGHT FAIL:", e)
        return 2

    model = os.environ.get("MOONSHOT_MODEL", llm_client.DEFAULT_MODEL)
    n_papers = len(config.TEST_RUN_01_PAPER_IDS)
    est_extract = _est_cost(EST_EXTRACT_INPUT, EST_EXTRACT_OUTPUT) * n_papers
    # audit: 假设平均 2 batch/paper
    est_audit = _est_cost(EST_AUDIT_INPUT_PER_BATCH, EST_AUDIT_OUTPUT_PER_BATCH) * n_papers * 2
    est_max = est_extract + est_audit

    print("=" * 70)
    print("Stage B v2 (strict) - 预飞检查")
    print(f"  model:            {model}")
    print(f"  api endpoint:     {llm_client.MOONSHOT_API_URL}")
    print(f"  key present:      yes (len={len(key)}, "
          f"prefix={key[:6]}..., suffix=...{key[-4:]})")
    print(f"  papers:           {n_papers}")
    print(f"  max calls total:  {MAX_CALLS_TOTAL} (extract + audit batches + recovery)")
    print(f"  audit batch size: {AUDIT_BATCH_SIZE}")
    print(f"  est extract:      ¥{est_extract:.2f}")
    print(f"  est audit:        ¥{est_audit:.2f}")
    print(f"  est total:        ¥{est_max:.2f}")
    print(f"  budget hard stop: ¥{BUDGET_HARD_STOP_CNY:.2f}")
    if est_max > BUDGET_HARD_STOP_CNY:
        print(f"STOP: est total exceeds ¥{BUDGET_HARD_STOP_CNY:.2f}. Aborting.")
        return 3
    print(f"  budget check:     OK")
    print("=" * 70)

    os.makedirs(config.STAGE_B_TEST_05_DIR, exist_ok=True)
    os.makedirs(config.STAGE_B_TEST_05_LOGS_DIR, exist_ok=True)

    methods_by_paper = load_stage_a_methods()
    tax_rows = {r["paper_id"]: r for r in _load_csv_rows(
        config.CORPUS_PP_V1_1_PAPER_TAXONOMY_CSV)}
    pt_rows = {r["paper_id"]: r for r in _load_csv_rows(
        config.CORPUS_PP_V1_1_PAPER_TYPES_CSV)}
    v04_edges = load_v04_edges()

    started_iso = datetime.now().isoformat(timespec="seconds")
    t0 = time.time()

    all_pairs = []
    all_raw_records = []
    all_audit_records = []
    all_edges = []
    per_paper_rows = []
    total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    total_calls = 0

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
        extract_ok = False
        e_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        a_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        proposals = []
        proposals_to_audit = []
        audit_out = {"audits_by_pair": {}, "input_pair_ids": [],
                     "covered_pair_ids": [], "missing_pair_ids": [],
                     "batches_run": 0, "recovery_runs": 0, "call_count": 0,
                     "raw_calls": []}

        # ---- 抽取 ----
        if pairs and total_calls < MAX_CALLS_TOTAL:
            extract_pack = build_extractor_pack(
                pid, canonical_title, paper_type, primary, subfield,
                pairs, sentence_index,
            )
            obj, ok, err, u, raw = call_and_parse(
                prompts_strict.EXTRACTOR_SYSTEM_STRICT, extract_pack, model,
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
                "ok": ok, "error": err, "usage": u,
                "proposals": proposals,
                "raw_text_last": (raw or "")[:8000],
            })

            # 只把 verdict != NO_RELATION 送审
            proposals_to_audit = [
                p for p in proposals
                if (p.get("verdict") or p.get("relation") or "").upper() not in
                   ("NO_RELATION", "NONE", "")
            ]

            # ---- 审查 (batch + coverage) ----
            if proposals_to_audit and total_calls < MAX_CALLS_TOTAL:
                def _bp(batch, bs):
                    return build_auditor_pack(batch, methods_by_id, sentence_index, bs)
                def _llm(prompt):
                    return call_and_parse(
                        prompts_strict.AUDITOR_SYSTEM_STRICT, prompt, model)

                audit_out = ab.run_audit_with_coverage(
                    proposals_to_audit, methods_by_id, sentence_index,
                    build_prompt=_bp, call_llm=_llm,
                    batch_size=AUDIT_BATCH_SIZE, max_recovery_calls=1,
                )
                total_calls += audit_out["call_count"]
                _accum(a_usage, audit_out["audit_usage"])
                _accum(total_usage, audit_out["audit_usage"])
                all_audit_records.append({
                    "paper_id": pid,
                    "input_count": len(audit_out["input_pair_ids"]),
                    "covered_count": len(audit_out["covered_pair_ids"]),
                    "missing_count": len(audit_out["missing_pair_ids"]),
                    "batches_run": audit_out["batches_run"],
                    "recovery_runs": audit_out["recovery_runs"],
                    "call_count": audit_out["call_count"],
                    "raw_calls": audit_out["raw_calls"],
                    "audits_by_pair": audit_out["audits_by_pair"],
                })
        else:
            note = "no_candidate_pairs" if not pairs else "budget_exhausted"

        # ---- edge 校验 ----
        edges = []
        for prop in proposals:
            e = evs.validate_and_classify_edge_strict(
                prop, methods_by_id, sentence_index, audit_out["audits_by_pair"])
            if not e.get("paper_id"):
                e["paper_id"] = pid
            edges.append(e)
        all_edges.extend(edges)

        dt = time.time() - t_paper
        acc = sum(1 for e in edges if e["validation_status"] == "accepted")
        cand = sum(1 for e in edges if e["validation_status"] == "candidate")
        rej = sum(1 for e in edges if e["validation_status"] == "rejected")
        no_rel = sum(1 for p in proposals
                     if (p.get("verdict") or p.get("relation") or "").upper()
                     in ("NO_RELATION", "NONE"))

        cost = _est_cost(e_usage["prompt_tokens"] + a_usage["prompt_tokens"],
                         e_usage["completion_tokens"] + a_usage["completion_tokens"])
        coverage = (len(audit_out["covered_pair_ids"]) /
                    max(len(audit_out["input_pair_ids"]), 1)) \
                   if audit_out["input_pair_ids"] else 1.0

        per_paper_rows.append({
            "paper_id": pid,
            "canonical_title": canonical_title,
            "paper_type": paper_type,
            "n_methods": stats["n_methods"],
            "n_theoretical_pairs": stats["theoretical_pairs"],
            "n_filtered_pairs": stats["filtered_pairs"],
            "n_relations_proposed": len(proposals),
            "n_no_relation_verdicts": no_rel,
            "n_accepted_edges": acc,
            "n_candidate_edges": cand,
            "n_rejected_edges": rej,
            "extract_call_ok": extract_ok,
            "audit_batches": audit_out["batches_run"],
            "audit_recovery_runs": audit_out["recovery_runs"],
            "audit_input_count": len(audit_out["input_pair_ids"]),
            "audit_covered_count": len(audit_out["covered_pair_ids"]),
            "audit_missing_count": len(audit_out["missing_pair_ids"]),
            "audit_coverage_rate": round(coverage, 4),
            "extract_prompt_tokens": e_usage["prompt_tokens"],
            "extract_completion_tokens": e_usage["completion_tokens"],
            "audit_prompt_tokens": a_usage["prompt_tokens"],
            "audit_completion_tokens": a_usage["completion_tokens"],
            "estimated_cost_cny": round(cost, 4),
            "duration_sec": round(dt, 2),
            "note": note,
        })

        # 每篇 log
        with open(os.path.join(config.STAGE_B_TEST_05_LOGS_DIR, f"{pid}.log.json"),
                  "w", encoding="utf-8") as f:
            json.dump({
                "paper_id": pid, "duration_sec": round(dt, 2),
                "stats": stats,
                "n_proposals": len(proposals),
                "n_no_relation": no_rel,
                "n_edges_accepted": acc,
                "n_edges_candidate": cand,
                "n_edges_rejected": rej,
                "extract_usage": e_usage,
                "audit_usage": a_usage,
                "audit_batches": audit_out["batches_run"],
                "audit_recovery_runs": audit_out["recovery_runs"],
                "audit_coverage_rate": round(coverage, 4),
                "estimated_cost_cny": round(cost, 4),
            }, f, ensure_ascii=False, indent=2)

        print(f"  [{i:>2}/10] {pid[:36]:<36} "
              f"pairs={len(pairs)}/{stats['theoretical_pairs']} "
              f"proposed={len(proposals)}(NO_REL={no_rel}) "
              f"acc={acc} cand={cand} rej={rej} "
              f"audit_cov={round(coverage*100, 1)}% "
              f"calls={1 if extract_ok else 0}+{audit_out['call_count']}")

    dur = time.time() - t0

    # ---- 写产物 ----
    _write_csv(config.STAGE_B_TEST_05_CANDIDATE_PAIRS_CSV,
                CAND_PAIR_FIELDS, all_pairs)

    with open(config.STAGE_B_TEST_05_RELATION_RAW, "w", encoding="utf-8") as f:
        for r in all_raw_records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    with open(config.STAGE_B_TEST_05_AUDIT_JSONL, "w", encoding="utf-8") as f:
        for r in all_audit_records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    _write_csv(config.STAGE_B_TEST_05_EDGES_ACCEPTED, EDGE_FIELDS,
                [e for e in all_edges if e["validation_status"] == "accepted"])
    _write_csv(config.STAGE_B_TEST_05_EDGES_CANDIDATE, EDGE_FIELDS,
                [e for e in all_edges if e["validation_status"] == "candidate"])
    _write_csv(config.STAGE_B_TEST_05_EDGES_REJECTED, EDGE_FIELDS,
                [e for e in all_edges if e["validation_status"] == "rejected"])
    _write_csv(config.STAGE_B_TEST_05_PER_PAPER_CSV, PER_PAPER_FIELDS,
                per_paper_rows)

    total_cost = _est_cost(total_usage["prompt_tokens"],
                            total_usage["completion_tokens"])

    # ============================================================
    # 统计 + 报告
    # ============================================================
    n_theoretical = sum(r["n_theoretical_pairs"] for r in per_paper_rows)
    n_filtered = sum(r["n_filtered_pairs"] for r in per_paper_rows)
    n_proposed = sum(r["n_relations_proposed"] for r in per_paper_rows)
    n_no_rel = sum(r["n_no_relation_verdicts"] for r in per_paper_rows)
    n_acc = sum(r["n_accepted_edges"] for r in per_paper_rows)
    n_cand = sum(r["n_candidate_edges"] for r in per_paper_rows)
    n_rej = sum(r["n_rejected_edges"] for r in per_paper_rows)

    relation_counter = Counter(e["relation"] for e in all_edges if e["relation"])
    accepted_relation_counter = Counter(
        e["relation"] for e in all_edges
        if e["validation_status"] == "accepted" and e["relation"])

    # 拒绝原因分布
    reject_reasons = Counter()
    for e in all_edges:
        if e["validation_status"] == "rejected":
            for x in (e["rejected_reason"] or "").split(","):
                x = x.strip()
                if x:
                    reject_reasons[x] += 1
    candidate_reasons = Counter()
    for e in all_edges:
        if e["validation_status"] == "candidate":
            for x in (e["rejected_reason"] or "").split(","):
                x = x.strip()
                if x:
                    candidate_reasons[x] += 1

    # 证据 ID 有效率
    total_ids = 0
    valid_ids = 0
    for e in all_edges:
        sids = e.get("relation_evidence_sentence_ids") or []
        missing = e.get("evidence_missing_ids") or []
        total_ids += len(sids)
        valid_ids += len(sids) - len(missing)
    id_valid_rate = (valid_ids / total_ids) if total_ids else 1.0
    # 全局审查覆盖率
    audit_input_total = sum(r["audit_input_count"] for r in per_paper_rows)
    audit_covered_total = sum(r["audit_covered_count"] for r in per_paper_rows)
    audit_coverage_global = (audit_covered_total / audit_input_total) \
                            if audit_input_total else 1.0

    wrong_type_count = sum(1 for e in all_edges
                            if e["audit_relation_check"] == "wrong_type")
    whole_comp_count = sum(1 for e in all_edges
                            if "whole_component_relation" in (e["rejected_reason"] or ""))
    ambiguous_count = sum(1 for e in all_edges
                           if "endpoint_linkage_ambiguous" in (e["rejected_reason"] or ""))
    dup_count = sum(1 for e in all_edges
                     if "duplicate_or_alias" in (e["rejected_reason"] or ""))
    reversed_count = sum(1 for e in all_edges
                         if e["audit_direction"] == "reversed")

    val_report = {
        "run_started_at": started_iso,
        "duration_sec": round(dur, 2),
        "model": model,
        "stage_b_version": STAGE_B_VERSION + "+strict",
        "counts": {
            "n_papers": n_papers,
            "n_theoretical_pairs": n_theoretical,
            "n_filtered_pairs": n_filtered,
            "n_relations_proposed": n_proposed,
            "n_no_relation_verdicts": n_no_rel,
            "n_accepted_edges": n_acc,
            "n_candidate_edges": n_cand,
            "n_rejected_edges": n_rej,
        },
        "audit_coverage_input": audit_input_total,
        "audit_coverage_covered": audit_covered_total,
        "audit_coverage_rate": round(audit_coverage_global, 4),
        "evidence_id_total": total_ids,
        "evidence_id_valid": valid_ids,
        "evidence_id_valid_rate": round(id_valid_rate, 4),
        "relations_distribution": dict(relation_counter),
        "accepted_relations_distribution": dict(accepted_relation_counter),
        "reject_reasons_distribution": dict(reject_reasons),
        "candidate_reasons_distribution": dict(candidate_reasons),
        "wrong_type_count": wrong_type_count,
        "whole_component_reject_count": whole_comp_count,
        "endpoint_linkage_ambiguous_count": ambiguous_count,
        "duplicate_or_alias_count": dup_count,
        "direction_reversed_count": reversed_count,
        "actual_api_calls": total_calls,
        "actual_cost_cny": round(total_cost, 4),
        "budget_hard_stop_cny": BUDGET_HARD_STOP_CNY,
    }
    with open(config.STAGE_B_TEST_05_VALIDATION_JSON, "w", encoding="utf-8") as f:
        json.dump(val_report, f, ensure_ascii=False, indent=2)

    # ---- diff v04 vs v05 ----
    diff_rows = []
    for pid in config.TEST_RUN_01_PAPER_IDS:
        v04_list = v04_edges.get(pid, [])
        v05_list = [e for e in all_edges if e["paper_id"] == pid]

        v04_acc = [x for x in v04_list if x["_v04_bucket"] == "accepted"]
        v04_cand = [x for x in v04_list if x["_v04_bucket"] == "candidate"]
        v04_rej = [x for x in v04_list if x["_v04_bucket"] == "rejected"]

        v05_acc = [e for e in v05_list if e["validation_status"] == "accepted"]
        v05_cand = [e for e in v05_list if e["validation_status"] == "candidate"]
        v05_rej = [e for e in v05_list if e["validation_status"] == "rejected"]

        v04_wrong_type = sum(1 for x in v04_list
                              if x.get("audit_relation_check") == "wrong_type")
        v05_wrong_type = sum(1 for e in v05_list
                              if e["audit_relation_check"] == "wrong_type")
        v04_am = sum(1 for x in v04_list
                     if "audit_missing" in (x.get("rejected_reason") or ""))
        v05_am = sum(1 for e in v05_list
                     if "audit_missing" in (e["rejected_reason"] or ""))

        # v04 accepted 是否在 v05 里仍 accepted (按 method_name 对匹配)
        def _acc_key(row):
            return (row.get("from_method_name", "").strip(),
                    row.get("to_method_name", "").strip())
        v04_acc_keys = {_acc_key(x) for x in v04_acc}
        v05_acc_keys = {_acc_key(e) for e in v05_acc}
        kept = sorted(v04_acc_keys & v05_acc_keys)
        dropped = sorted(v04_acc_keys - v05_acc_keys)
        newly = sorted(v05_acc_keys - v04_acc_keys)

        diff_rows.append({
            "paper_id": pid,
            "v04_extracted": len(v04_list),
            "v05_extracted": len(v05_list),
            "v04_accepted": len(v04_acc),
            "v05_accepted": len(v05_acc),
            "v04_candidate": len(v04_cand),
            "v05_candidate": len(v05_cand),
            "v04_rejected": len(v04_rej),
            "v05_rejected": len(v05_rej),
            "v04_wrong_type": v04_wrong_type,
            "v05_wrong_type": v05_wrong_type,
            "v04_audit_missing": v04_am,
            "v05_audit_missing": v05_am,
            "v04_accepted_edges_kept": [f"{a}→{b}" for a, b in kept],
            "v04_accepted_edges_dropped": [f"{a}→{b}" for a, b in dropped],
            "v05_new_accepted": [f"{a}→{b}" for a, b in newly],
        })
    _write_csv(config.STAGE_B_TEST_05_DIFF_CSV, DIFF_FIELDS, diff_rows)

    # ---- Markdown 报告 ----
    ml = []
    ml.append("# Stage B v2 strict 校验报告 (test_run_05_stage_b_strict)\n\n")
    ml.append(
        f"> 运行时间: {started_iso} · 耗时 {round(dur, 1)}s\n"
        f"> 模型: `{model}` · API 调用: **{total_calls}** / 上限 {MAX_CALLS_TOTAL}\n"
        f"> tokens: prompt={total_usage['prompt_tokens']} completion="
        f"{total_usage['completion_tokens']} total={total_usage['total_tokens']}\n"
        f"> 费用: **¥{round(total_cost, 3)}** (硬门限 ¥{BUDGET_HARD_STOP_CNY})\n\n"
    )

    ml.append("## 一、汇总\n")
    ml.append(f"- 候选对: 理论 {n_theoretical} → 筛后 **{n_filtered}**\n")
    ml.append(f"- 抽取器输出: **{n_proposed}** 条 (含 NO_RELATION={n_no_rel})\n")
    ml.append(f"- 送审对: {n_proposed - n_no_rel}\n")
    ml.append(f"- accepted edges: **{n_acc}**\n")
    ml.append(f"- candidate: {n_cand} · rejected: {n_rej}\n")

    ml.append("\n## 二、审查覆盖率 (spec 一 重点)\n")
    ml.append(f"- 送审 pair 总数: {audit_input_total}\n")
    ml.append(f"- 审查覆盖到的: {audit_covered_total}\n")
    ml.append(f"- **审查覆盖率: {round(audit_coverage_global * 100, 2)}%**\n")

    ml.append("\n## 三、证据 ID 有效性\n")
    ml.append(f"- 证据 ID 总数: {total_ids}\n")
    ml.append(f"- 有效: {valid_ids}\n")
    ml.append(f"- **证据 ID 有效率: {round(id_valid_rate * 100, 2)}%**\n")

    ml.append("\n## 四、四类关系分布\n\n| 关系 | 总提议 | accepted |\n|---|---:|---:|\n")
    for r in ("EXTENDS", "IMPROVES", "ADAPTS", "REPLACES"):
        ml.append(f"| {r} | {relation_counter.get(r, 0)} "
                  f"| {accepted_relation_counter.get(r, 0)} |\n")

    ml.append("\n## 五、拒绝原因分布 (rejected)\n\n| reason | count |\n|---|---:|\n")
    for k, v in sorted(reject_reasons.items(), key=lambda kv: -kv[1]):
        ml.append(f"| `{k}` | {v} |\n")
    ml.append("\n## 六、降级原因分布 (candidate)\n\n| reason | count |\n|---|---:|\n")
    for k, v in sorted(candidate_reasons.items(), key=lambda kv: -kv[1]):
        ml.append(f"| `{k}` | {v} |\n")

    ml.append("\n## 七、关键指标\n\n| 指标 | 值 |\n|---|---:|\n")
    ml.append(f"| wrong_type 数 | {wrong_type_count} |\n")
    ml.append(f"| whole_component 拒绝数 | {whole_comp_count} |\n")
    ml.append(f"| ambiguous 指代拒绝数 | {ambiguous_count} |\n")
    ml.append(f"| duplicate/alias 拒绝数 | {dup_count} |\n")
    ml.append(f"| 方向 reversed 数 | {reversed_count} |\n")

    ml.append("\n## 八、每篇统计\n\n")
    ml.append("| # | paper_id | methods | 理论 | 筛后 | 提议 | NO_REL | acc | cand | rej | audit_cov | ¥ |\n"
              "|--:|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|\n")
    for i, r in enumerate(per_paper_rows, 1):
        cov_str = f"{round(r['audit_coverage_rate']*100, 1)}%"
        ml.append(
            f"| {i} | `{r['paper_id'][:36]}` | {r['n_methods']} "
            f"| {r['n_theoretical_pairs']} | {r['n_filtered_pairs']} "
            f"| {r['n_relations_proposed']} | {r['n_no_relation_verdicts']} "
            f"| {r['n_accepted_edges']} | {r['n_candidate_edges']} "
            f"| {r['n_rejected_edges']} | {cov_str} "
            f"| {r['estimated_cost_cny']} |\n"
        )

    ml.append(f"\n## 九、每条 accepted 关系及原文证据\n")
    if n_acc == 0:
        ml.append("*(无)*\n")
    else:
        for e in all_edges:
            if e["validation_status"] != "accepted":
                continue
            ml.append(f"\n### `{e['paper_id']}` — {e['relation']}\n")
            ml.append(f"- **from**: `{e['from_method_id']}` — {e['from_method_name']}\n")
            ml.append(f"- **to**:   `{e['to_method_id']}` — {e['to_method_name']}\n")
            ml.append(f"- audit.linkage_type: `{e['audit_linkage_type']}`\n")
            ml.append(f"- audit.endpoint_linkage: `{e['audit_endpoint_linkage']}`\n")
            ml.append(f"- audit.coreference_explanation: {e['audit_coreference_explanation']}\n")
            ml.append(f"- direction_basis: {e['direction_basis']}\n")
            ml.append(f"- evidence_section: {e['evidence_section']}\n")
            ml.append(f"- evidence_sids: {e['relation_evidence_sentence_ids']}\n")
            ml.append(f"- explicit_trigger_hit: {e['explicit_trigger_hit']}\n")
            ev_text = e['evidence_quote']
            if len(ev_text) > 300:
                ev_text = ev_text[:300] + "..."
            ml.append(f"- **evidence_quote**:\n\n> {ev_text}\n")

    ml.append("\n## 十、v04 accepted 4 条在 v05 的去向\n\n")
    ml.append("| paper_id | v04 accepted | v05 kept | v05 dropped | v05 new |\n"
              "|---|---|---|---|---|\n")
    for d in diff_rows:
        if d["v04_accepted"] == 0 and d["v05_accepted"] == 0:
            continue
        ml.append(
            f"| `{d['paper_id'][:32]}` "
            f"| {d['v04_accepted']} "
            f"| {d['v04_accepted_edges_kept']} "
            f"| {d['v04_accepted_edges_dropped']} "
            f"| {d['v05_new_accepted']} |\n"
        )

    # ---- 进入全量条件评估 ----
    conditions = [
        ("audit 覆盖率 100%", audit_coverage_global >= 0.999),
        ("证据 ID + 切片一致率 100%", id_valid_rate >= 0.999),
        ("accepted 无整体-组件", not any(
            "whole_component_relation" in (e["rejected_reason"] or "")
            for e in all_edges if e["validation_status"] == "accepted"
        )),
        ("accepted 无模糊指代", not any(
            e["audit_endpoint_linkage"] == "ambiguous"
            for e in all_edges if e["validation_status"] == "accepted"
        )),
        ("accepted 无同义重复", not any(
            "duplicate_or_alias" in (e["rejected_reason"] or "")
            for e in all_edges if e["validation_status"] == "accepted"
        )),
        ("wrong_type 数下降", wrong_type_count < 40),  # v04 = 40
    ]
    ml.append("\n## 十一、进入全量条件\n\n")
    ml.append("| 条件 | 状态 |\n|---|:---:|\n")
    for name, ok in conditions:
        ml.append(f"| {name} | {'✅' if ok else '❌'} |\n")

    with open(config.STAGE_B_TEST_05_VALIDATION_MD, "w", encoding="utf-8") as f:
        f.writelines(ml)

    # ---- diff MD ----
    dml = []
    dml.append("# v04 vs v05 对比\n\n")
    dml.append("| paper_id | v04_acc | v05_acc | v04_cand | v05_cand | v04_rej | v05_rej | "
               "v04_wrong_type | v05_wrong_type | v04_audit_miss | v05_audit_miss |\n"
               "|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|\n")
    for d in diff_rows:
        dml.append(f"| `{d['paper_id'][:32]}` | {d['v04_accepted']} | {d['v05_accepted']} "
                   f"| {d['v04_candidate']} | {d['v05_candidate']} "
                   f"| {d['v04_rejected']} | {d['v05_rejected']} "
                   f"| {d['v04_wrong_type']} | {d['v05_wrong_type']} "
                   f"| {d['v04_audit_missing']} | {d['v05_audit_missing']} |\n")

    dml.append("\n## v04 accepted 逐条追踪\n\n")
    for d in diff_rows:
        if d["v04_accepted"] > 0:
            dml.append(f"\n### {d['paper_id']}\n")
            dml.append(f"- 保留: {d['v04_accepted_edges_kept']}\n")
            dml.append(f"- 丢弃: {d['v04_accepted_edges_dropped']}\n")
            dml.append(f"- 新增: {d['v05_new_accepted']}\n")

    with open(config.STAGE_B_TEST_05_DIFF_MD, "w", encoding="utf-8") as f:
        f.writelines(dml)

    print()
    print("=" * 70)
    print(f"Stage B strict done: 10 papers, {total_calls} calls, "
          f"~¥{round(total_cost, 3)}, {round(dur, 1)}s")
    print(f"  proposed={n_proposed}(NO_REL={n_no_rel}) "
          f"acc={n_acc} cand={n_cand} rej={n_rej}")
    print(f"  audit_coverage={round(audit_coverage_global*100, 2)}% "
          f"id_valid={round(id_valid_rate*100, 2)}%")
    print(f"  wrong_type={wrong_type_count} whole_comp={whole_comp_count} "
          f"ambiguous={ambiguous_count} dup={dup_count} reversed={reversed_count}")
    print(f"outputs: {config.relative_path(config.STAGE_B_TEST_05_DIR)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
