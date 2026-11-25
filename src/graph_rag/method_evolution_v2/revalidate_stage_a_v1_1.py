"""revalidate_stage_a_v1_1.py — 本地重校验器 (无 API).

按 v1.1 放宽的规则重新分级 test_run_03 + batch 1 raw LLM 输出.
不改原 raw. 不覆盖原结果. 输出到 stage_a_validation_v1_1/.
"""
from __future__ import annotations

import csv
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_GRAPH_RAG_DIR = os.path.dirname(THIS_DIR)
if SRC_GRAPH_RAG_DIR not in sys.path:
    sys.path.insert(0, SRC_GRAPH_RAG_DIR)

from method_evolution_v2 import config
from method_evolution_v2.stage_a import (
    evidence_validation as ev1,
    evidence_validation_v2 as ev2,
    provenance_v2 as pv2,
)
from method_evolution_v2.stage_a.method_extraction import _make_method_id


CSV_METHOD_FIELDS = [
    "paper_id", "method_id", "kind",
    "method_name", "normalized_name", "method_type",
    "problem_solved", "key_components",
    "evidence_quote", "evidence_section", "evidence_para_id",
    "evidence_char_start", "evidence_char_end",
    "evidence_sentence_ids", "evidence_missing_ids", "evidence_spans",
    "evidence_sufficiency",
    "citation_clue", "citation_clue_raw",
    "cited_author", "cited_year", "cited_reference_number",
    "external_stub_id",
    "support_scope", "source_provenance",
    "evidence_paper_id", "original_source_paper_id",
    "confidence_llm",
    "evidence_match_status", "validation_status",
    "rejected_reason",
]

STATUS_CHANGE_FIELDS = [
    "paper_id", "method_id", "kind", "method_name",
    "old_status", "new_status",
    "old_reason", "new_reason",
    "transition",
]

PER_PAPER_FIELDS = [
    "paper_id", "paper_type",
    "n_own_raw", "n_ref_raw",
    "old_accepted", "old_candidate", "old_rejected",
    "new_accepted", "new_candidate", "new_rejected",
    "delta_accepted", "delta_candidate", "delta_rejected",
]


def _j(v):
    if isinstance(v, (list, dict)):
        return json.dumps(v, ensure_ascii=False)
    return "" if v is None else str(v)


def _load_json(p):
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_csv(p):
    with open(p, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _write_csv(path, fields, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow({k: _j(row.get(k)) for k in fields})


def load_old_methods_test_run_03() -> dict:
    """test_run_03: {paper_id: {method_id: old_row(dict, with kind & old_status)}}"""
    out = defaultdict(dict)
    for status, path in [
        ("accepted", config.STAGE_A_TEST_03_METHODS_ACCEPTED),
        ("candidate", config.STAGE_A_TEST_03_METHODS_CANDIDATE),
        ("rejected", config.STAGE_A_TEST_03_METHODS_REJECTED),
    ]:
        if not os.path.isfile(path):
            continue
        for r in _load_csv(path):
            r["_old_status"] = status
            out[r["paper_id"]][r["method_id"]] = r
    return out


def load_old_methods_batch_1() -> dict:
    """batch 1: {paper_id: {method_id: old_row}} from per_paper JSON."""
    out = defaultdict(dict)
    ppd = config.STAGE_A_FULL_V1_PER_PAPER_DIR
    if not os.path.isdir(ppd):
        return out
    for d in os.listdir(ppd):
        dp = os.path.join(ppd, d)
        if not os.path.isdir(dp):
            continue
        for bucket in ("accepted", "candidate", "rejected"):
            p = os.path.join(dp, f"methods_{bucket}.json")
            if not os.path.isfile(p):
                continue
            for m in _load_json(p):
                m["_old_status"] = bucket
                m.setdefault("method_name", m.get("name", ""))
                pid = m.get("paper_id", "")
                mid = m.get("method_id", "")
                if pid and mid:
                    out[pid][mid] = m
    return out


def load_raw_test_run_03() -> list:
    """Load test_run_03 methods_raw.jsonl. Each line = 1 paper."""
    p = config.STAGE_A_TEST_03_METHODS_RAW
    out = []
    if not os.path.isfile(p):
        return out
    with open(p, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def load_sentence_index_test_run_03(paper_id: str) -> dict:
    p = os.path.join(config.STAGE_A_TEST_03_SENTENCE_IDX_DIR, f"{paper_id}.json")
    if not os.path.isfile(p):
        return {}
    d = _load_json(p)
    return {s["sentence_id"]: s for s in d.get("sentences", [])}


def load_batch_1_per_paper() -> list:
    """Batch 1: return list of {paper_id, paper_type, own_raw, ref_raw, sentence_index}."""
    out = []
    ppd = config.STAGE_A_FULL_V1_PER_PAPER_DIR
    if not os.path.isdir(ppd):
        return out
    # 加载 paper_type 关联
    pt_map = {}
    if os.path.isfile(config.CORPUS_PP_V1_1_PAPER_TYPES_CSV):
        with open(config.CORPUS_PP_V1_1_PAPER_TYPES_CSV, "r",
                    encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                pt_map[r["paper_id"]] = r.get("paper_type", "")
    for d in sorted(os.listdir(ppd)):
        dp = os.path.join(ppd, d)
        if not os.path.isdir(dp):
            continue
        im = os.path.join(dp, "input_manifest.json")
        rr = os.path.join(dp, "raw_response.json")
        si = os.path.join(dp, "sentence_index.json")
        if not (os.path.isfile(im) and os.path.isfile(rr) and os.path.isfile(si)):
            continue
        im_d = _load_json(im)
        rr_d = _load_json(rr)
        si_d = _load_json(si)
        pid = im_d["paper_id"]
        out.append({
            "paper_id": pid,
            "paper_type": pt_map.get(pid, "unclear"),
            "own_raw": rr_d.get("own_methods_raw") or [],
            "ref_raw": rr_d.get("referenced_methods_raw") or [],
            "sentence_index": {s["sentence_id"]: s for s in si_d.get("sentences", [])},
            "source": "batch_1",
        })
    return out


def load_test_run_03_records() -> list:
    """test_run_03: [{paper_id, paper_type, own_raw, ref_raw, sentence_index}]."""
    out = []
    pt_map = {}
    if os.path.isfile(config.CORPUS_PP_V1_1_PAPER_TYPES_CSV):
        with open(config.CORPUS_PP_V1_1_PAPER_TYPES_CSV, "r",
                    encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                pt_map[r["paper_id"]] = r.get("paper_type", "")
    for rec in load_raw_test_run_03():
        pid = rec.get("paper_id", "")
        if not pid:
            continue
        out.append({
            "paper_id": pid,
            "paper_type": pt_map.get(pid, "unclear"),
            "own_raw": rec.get("own_methods_raw") or [],
            "ref_raw": rec.get("referenced_methods_raw") or [],
            "sentence_index": load_sentence_index_test_run_03(pid),
            "source": "test_run_03",
        })
    return out


def revalidate_paper(rec: dict) -> list:
    """对一篇论文的 raw own/ref 列表跑 v2 resolver + v2 provenance."""
    paper_id = rec["paper_id"]
    paper_type = rec["paper_type"]
    sidx = rec["sentence_index"]

    methods = []
    for idx, m in enumerate(rec["own_raw"]):
        if not isinstance(m, dict):
            continue
        c = ev2.resolve_method_by_sentence_ids_v2(m, sidx, kind="own",
                                                    paper_type=paper_type)
        c["paper_id"] = paper_id
        c["method_id"] = _make_method_id(paper_id, "own", idx,
                                           c.get("name") or "unnamed")
        c = pv2.attach_provenance_v2(c, paper_id, paper_type)
        methods.append(c)
    for idx, m in enumerate(rec["ref_raw"]):
        if not isinstance(m, dict):
            continue
        c = ev2.resolve_method_by_sentence_ids_v2(m, sidx, kind="referenced",
                                                    paper_type=paper_type)
        c["paper_id"] = paper_id
        c["method_id"] = _make_method_id(paper_id, "referenced", idx,
                                           c.get("name") or "unnamed")
        c = pv2.attach_provenance_v2(c, paper_id, paper_type)
        methods.append(c)

    # 去重 (与 v1 同款: 保留证据最长的一条)
    methods = ev1.dedupe_methods_prefer_longer_evidence(methods)
    return methods


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    os.makedirs(config.STAGE_A_REVALID_V1_1_DIR, exist_ok=True)

    # 加载
    records = load_test_run_03_records() + load_batch_1_per_paper()
    print(f"records: test_run_03={sum(1 for r in records if r['source']=='test_run_03')} "
          f"batch_1={sum(1 for r in records if r['source']=='batch_1')}")

    # 旧结果 (paper_id → method_id → old_row)
    old_test_03 = load_old_methods_test_run_03()
    old_batch_1 = load_old_methods_batch_1()

    new_accepted = []
    new_candidate = []
    new_rejected = []
    status_changes = []
    per_paper_rows = []

    counters_all = Counter()

    for rec in records:
        pid = rec["paper_id"]
        source = rec["source"]
        old_map = old_test_03.get(pid, {}) if source == "test_run_03" \
                    else old_batch_1.get(pid, {})

        new_methods = revalidate_paper(rec)

        n_own_raw = sum(1 for m in rec["own_raw"] if isinstance(m, dict))
        n_ref_raw = sum(1 for m in rec["ref_raw"] if isinstance(m, dict))

        # 统计
        old_counts = Counter(old_map[k]["_old_status"] for k in old_map)
        new_counts = Counter(m["validation_status"] for m in new_methods)

        per_paper_rows.append({
            "paper_id": pid,
            "paper_type": rec["paper_type"],
            "n_own_raw": n_own_raw,
            "n_ref_raw": n_ref_raw,
            "old_accepted": old_counts.get("accepted", 0),
            "old_candidate": old_counts.get("candidate", 0),
            "old_rejected": old_counts.get("rejected", 0),
            "new_accepted": new_counts.get("accepted", 0),
            "new_candidate": new_counts.get("candidate", 0),
            "new_rejected": new_counts.get("rejected", 0),
            "delta_accepted": new_counts.get("accepted", 0) - old_counts.get("accepted", 0),
            "delta_candidate": new_counts.get("candidate", 0) - old_counts.get("candidate", 0),
            "delta_rejected": new_counts.get("rejected", 0) - old_counts.get("rejected", 0),
        })

        # 状态变化 (按 method_id 匹配)
        for m in new_methods:
            mid = m["method_id"]
            old = old_map.get(mid)
            if old is None:
                # 新方法 (可能是 dedupe 差异)
                continue
            old_status = old["_old_status"]
            new_status = m["validation_status"]
            if old_status != new_status:
                status_changes.append({
                    "paper_id": pid,
                    "method_id": mid,
                    "kind": m["kind"],
                    "method_name": m["name"],
                    "old_status": old_status,
                    "new_status": new_status,
                    "old_reason": old.get("rejected_reason", ""),
                    "new_reason": m["rejected_reason"],
                    "transition": f"{old_status}->{new_status}",
                })

        # 分桶
        for m in new_methods:
            row = {
                "paper_id": pid,
                "method_id": m["method_id"],
                "kind": m["kind"],
                "method_name": m["name"],
                "normalized_name": m["normalized_name"],
                "method_type": m["method_type"],
                "problem_solved": m["problem_solved"],
                "key_components": m["key_components"],
                "evidence_quote": m["evidence_quote"],
                "evidence_section": m["evidence_section"],
                "evidence_para_id": m["evidence_para_id"],
                "evidence_char_start": m["evidence_char_start"],
                "evidence_char_end": m["evidence_char_end"],
                "evidence_sentence_ids": m["evidence_sentence_ids"],
                "evidence_missing_ids": m["evidence_missing_ids"],
                "evidence_spans": m["evidence_spans"],
                "evidence_sufficiency": m["evidence_sufficiency"],
                "citation_clue": m.get("citation_clue", ""),
                "citation_clue_raw": m.get("citation_clue_raw", ""),
                "cited_author": m.get("cited_author", ""),
                "cited_year": m.get("cited_year", ""),
                "cited_reference_number": m.get("cited_reference_number", ""),
                "external_stub_id": m.get("external_stub_id", ""),
                "support_scope": m.get("support_scope", ""),
                "source_provenance": m.get("source_provenance", ""),
                "evidence_paper_id": m.get("evidence_paper_id", ""),
                "original_source_paper_id": m.get("original_source_paper_id", ""),
                "confidence_llm": m["confidence_llm"],
                "evidence_match_status": m["evidence_match_status"],
                "validation_status": m["validation_status"],
                "rejected_reason": m["rejected_reason"],
            }
            if m["validation_status"] == "accepted":
                new_accepted.append(row)
            elif m["validation_status"] == "candidate":
                new_candidate.append(row)
            else:
                new_rejected.append(row)

        counters_all["papers"] += 1
        for s in new_counts:
            counters_all[s] += new_counts[s]

    _write_csv(config.STAGE_A_REVALID_V1_1_ACCEPTED_CSV,
                CSV_METHOD_FIELDS, new_accepted)
    _write_csv(config.STAGE_A_REVALID_V1_1_CANDIDATE_CSV,
                CSV_METHOD_FIELDS, new_candidate)
    _write_csv(config.STAGE_A_REVALID_V1_1_REJECTED_CSV,
                CSV_METHOD_FIELDS, new_rejected)
    _write_csv(config.STAGE_A_REVALID_V1_1_STATUS_CHANGES_CSV,
                STATUS_CHANGE_FIELDS, status_changes)
    _write_csv(config.STAGE_A_REVALID_V1_1_PER_PAPER_CSV,
                PER_PAPER_FIELDS, per_paper_rows)

    # 汇总数字
    trans = Counter(sc["transition"] for sc in status_changes)

    # 综合旧 vs 新总数
    old_total = Counter()
    for pid, mm in {**old_test_03, **old_batch_1}.items():
        for m in mm.values():
            old_total[m["_old_status"]] += 1

    # research 无 accepted own / review 无 accepted referenced
    pt_map = {r["paper_id"]: r.get("paper_type", "")
              for r in _load_csv(config.CORPUS_PP_V1_1_PAPER_TYPES_CSV)}
    new_by_paper = defaultdict(list)
    for m in new_accepted:
        new_by_paper[m["paper_id"]].append(m)
    research_no_own_new = []
    review_no_ref_new = []
    for pid in {r["paper_id"] for r in per_paper_rows}:
        ptype = pt_map.get(pid, "")
        own_acc = sum(1 for m in new_by_paper[pid] if m["kind"] == "own")
        ref_acc = sum(1 for m in new_by_paper[pid] if m["kind"] == "referenced")
        if ptype == "research_article" and own_acc == 0:
            research_no_own_new.append(pid)
        if ptype == "review_article" and ref_acc == 0:
            review_no_ref_new.append(pid)

    # 作者/年份/编号解析率
    all_new = new_accepted + new_candidate + new_rejected
    n_ref = sum(1 for m in all_new if m["kind"] == "referenced")
    w_author = sum(1 for m in all_new if m["kind"] == "referenced" and m["cited_author"])
    w_year = sum(1 for m in all_new if m["kind"] == "referenced" and m["cited_year"])
    w_ref = sum(1 for m in all_new if m["kind"] == "referenced"
                and m["cited_reference_number"])

    # evidence 有效性
    total_ids = valid_ids = 0
    n_exact = 0
    for m in all_new:
        sids = m["evidence_sentence_ids"] or []
        missing = m["evidence_missing_ids"] or []
        total_ids += len(sids)
        valid_ids += len(sids) - len(missing)
        if m["evidence_match_status"] == "sentence_id_exact":
            n_exact += 1

    id_valid = valid_ids / total_ids * 100 if total_ids else 100.0
    slice_rate = n_exact / len(all_new) * 100 if all_new else 100.0

    # 材料名/表征/宽泛冒充升级检查
    error_upgrades = []
    for m in new_accepted:
        # 若 accepted 却含疑似材料名/表征/宽泛信号
        s = (m.get("evidence_sufficiency") or {}).get("reason", "")
        if s in ("pure_material_name", "characterization_instrument_only",
                  "only_weak_or_generic_signals", "naming_or_classification"):
            error_upgrades.append(m)

    # ---- MD 报告 ----
    md = []
    md.append("# Stage A 本地重校验 v1.1 (无 API)\n\n")
    md.append(f"> 生成: {datetime.now().isoformat(timespec='seconds')}\n")
    md.append(f"> 输入: test_run_03 (10 篇) + stage_a_full_v1/batch_1 (25 篇) = 35 篇\n")
    md.append(f"> 规则: v2.1 放宽后的 sufficiency + section rule + citation name fallback\n\n")

    md.append("## 一、修正前后总数对比\n\n")
    md.append("| 状态 | old (v1) | new (v1.1) | Δ |\n|---|---:|---:|---:|\n")
    for s in ("accepted", "candidate", "rejected"):
        old_n = old_total.get(s, 0)
        new_n = counters_all.get(s, 0)
        md.append(f"| {s} | {old_n} | {new_n} | {new_n - old_n:+} |\n")

    md.append("\n## 二、状态转移分布\n\n")
    md.append("| 转移 | 数量 |\n|---|---:|\n")
    for k, v in trans.most_common():
        md.append(f"| `{k}` | {v} |\n")

    md.append(f"\n## 三、research_article 无 accepted own\n")
    md.append(f"- old: 见 batch_1 报告(5 篇)\n")
    md.append(f"- new: **{len(research_no_own_new)}**\n")
    for p in research_no_own_new:
        md.append(f"  - `{p}`\n")

    md.append(f"\n## 四、review_article 无 accepted referenced\n")
    md.append(f"- old: 1 篇 (batch_1 报告 MOFs分离膜)\n")
    md.append(f"- new: **{len(review_no_ref_new)}**\n")
    for p in review_no_ref_new:
        md.append(f"  - `{p}`\n")

    md.append(f"\n## 五、证据 ID + 切片一致率\n")
    md.append(f"- evidence ID valid rate: **{id_valid:.2f}%** ({valid_ids}/{total_ids})\n")
    md.append(f"- slice consistent (sentence_id_exact): **{slice_rate:.2f}%** "
                f"({n_exact}/{len(all_new)})\n")

    md.append(f"\n## 六、引用线索解析(referenced 方法)\n")
    md.append(f"- 总 referenced 方法: {n_ref}\n")
    if n_ref:
        md.append(f"- 有作者: {w_author} ({w_author/n_ref*100:.1f}%)\n")
        md.append(f"- 有年份: {w_year} ({w_year/n_ref*100:.1f}%)\n")
        md.append(f"- 有编号: {w_ref} ({w_ref/n_ref*100:.1f}%)\n")

    md.append(f"\n## 七、疑似错误升级(材料名/表征/宽泛/命名法被错升 accepted)\n")
    md.append(f"- **{len(error_upgrades)}** 条\n")
    for m in error_upgrades[:10]:
        md.append(f"  - [{m['paper_id']}] {m['method_name'][:60]}\n")

    md.append("\n## 八、Top 20 candidate→accepted 变更(升级样本)\n")
    upgrades_ca = [sc for sc in status_changes
                    if sc["transition"] == "candidate->accepted"]
    md.append(f"共 **{len(upgrades_ca)}** 条 candidate→accepted 变更。\n\n")
    for sc in upgrades_ca[:20]:
        md.append(f"- [{sc['paper_id'][:30]}] {sc['method_name'][:70]}\n"
                    f"  - old_reason: {sc['old_reason'][:120]}\n"
                    f"  - new_reason: {sc['new_reason'][:120]}\n")

    md.append("\n## 九、accepted→candidate 或 accepted→rejected(潜在质量退化)\n")
    downgrades = [sc for sc in status_changes
                    if sc["transition"] in ("accepted->candidate",
                                              "accepted->rejected")]
    md.append(f"共 **{len(downgrades)}** 条降级. \n\n")
    for sc in downgrades[:20]:
        md.append(f"- [{sc['paper_id'][:30]}] {sc['method_name'][:70]}\n"
                    f"  - {sc['transition']} · new_reason: {sc['new_reason'][:120]}\n")

    with open(config.STAGE_A_REVALID_V1_1_VALIDATION_DIFF_MD,
                "w", encoding="utf-8") as f:
        f.writelines(md)

    # 打印摘要
    print()
    print("=" * 70)
    print(f"Revalidation done. Papers: {sum(1 for _ in per_paper_rows)}")
    print(f"  old total: acc={old_total.get('accepted',0)} "
          f"cand={old_total.get('candidate',0)} rej={old_total.get('rejected',0)}")
    print(f"  new total: acc={counters_all.get('accepted',0)} "
          f"cand={counters_all.get('candidate',0)} rej={counters_all.get('rejected',0)}")
    print(f"  transitions: {dict(trans)}")
    print(f"  ID valid: {id_valid:.2f}% · slice consistent: {slice_rate:.2f}%")
    print(f"  research_no_own_new: {len(research_no_own_new)}")
    print(f"  review_no_ref_new: {len(review_no_ref_new)}")
    print(f"  error upgrades: {len(error_upgrades)}")
    if n_ref:
        print(f"  ref author: {w_author}/{n_ref} ({w_author/n_ref*100:.1f}%)")
        print(f"  ref year:   {w_year}/{n_ref} ({w_year/n_ref*100:.1f}%)")
        print(f"  ref refnum: {w_ref}/{n_ref} ({w_ref/n_ref*100:.1f}%)")
    print(f"outputs: {config.relative_path(config.STAGE_A_REVALID_V1_1_DIR)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
