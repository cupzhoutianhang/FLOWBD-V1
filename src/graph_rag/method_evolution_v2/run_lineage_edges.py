"""run_lineage_edges.py — spec 四 + 五: earliest source + edges (confirmed/candidate).

对已归一化 + 年份解析后的方法家族:
  - 找出最早可追溯来源节点
  - confirmed edges: 从 final_case/final_storage_case_edges.csv 里拿 family 内的
  - candidate edges: 家族内方法之间, 满足 core_process/core_material 相同 + 年份
    顺序合理 + 无直接原文关系句 → candidate (虚线)

无 API. 输出:
  lineage_earliest_source.json
  lineage_edges_confirmed.csv
  lineage_edges_candidate.csv
  lineage_evidence.md
"""
from __future__ import annotations

import csv
import json
import os
import sys
from collections import defaultdict

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_GRAPH_RAG_DIR = os.path.dirname(THIS_DIR)
if SRC_GRAPH_RAG_DIR not in sys.path:
    sys.path.insert(0, SRC_GRAPH_RAG_DIR)

from method_evolution_v2 import config                                # noqa: E402
from method_evolution_v2.stage_a import full_runner as fr             # noqa: E402


OUT_DIR = os.path.join(config.PAPER_V2_DIR, "article_minimal_results",
                          "lineage_mvp")
FINAL_CASE_DIR = os.path.join(config.PAPER_V2_DIR, "article_minimal_results",
                                   "final_case")


def _parse_sids(s):
    try: return json.loads(s) if s else []
    except Exception: return []


def load_norm():
    with open(os.path.join(OUT_DIR, "lineage_methods_normalized.csv"),
                "r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def load_confirmed_edges():
    p = os.path.join(FINAL_CASE_DIR, "final_storage_case_edges.csv")
    if not os.path.isfile(p): return []
    with open(p, "r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


# ============================================================
# Phase 4: earliest traceable source
# ============================================================

def find_earliest_traceable(norm_rows):
    """Return earliest node meeting all conditions."""
    dated = []
    for r in norm_rows:
        yr = r["year"]
        if not yr: continue
        try: y = int(yr)
        except ValueError: continue
        if y < 1970 or y > 2030: continue
        # spec 四: 不能是宽泛概念/材料名
        cn = (r.get("canonical_method_name") or "").strip()
        if len(cn) < 6: continue
        # 需属于同一家族 — 通过 core_process 或 core_material 存在
        if not (r.get("core_process") or r.get("core_material")):
            continue
        # 不是仅在后续论文中无来源地提到
        if r["source_status"] == "unresolved": continue
        dated.append((y, r))

    if not dated:
        return None
    dated.sort(key=lambda x: (x[0], x[1]["method_id"]))
    y_min = dated[0][0]
    candidates = [r for y, r in dated if y == y_min]
    chosen = candidates[0]
    return {
        "earliest_traceable_method": chosen["canonical_method_name"],
        "earliest_traceable_author": chosen.get("author", "")
                                          or chosen.get("source_author", ""),
        "earliest_traceable_year": y_min,
        "method_id": chosen["method_id"],
        "paper_id": chosen["paper_id"],
        "kind": chosen["kind"],
        "year_source": chosen["year_source"],
        "source_status": chosen["source_status"],
        "source_reference_text": chosen.get("source_reference_text", ""),
        "evidence_sentence_ids": chosen.get("evidence_sentence_ids", ""),
        "canonical_note": ("在本研究 337 篇文献及其可解析引用范围内, "
                             "最早可追溯的方法来源为: "
                             f"{chosen.get('author','')} "
                             f"({y_min}) "
                             f"— {chosen['canonical_method_name']}"),
        "limitation_note": ("本表述仅限本数据集内的可解析年份; "
                              "不代表全球首次提出; 不追溯外部原始文献; "
                              "若原始工作发表在数据集外或年份无法解析, "
                              "则不进入本追溯"),
    }


# ============================================================
# Phase 5: confirmed + candidate edges
# ============================================================

def build_confirmed_edges(norm_rows, confirmed_edges_raw, earliest_info):
    """Match confirmed edges from final_case with family method ids."""
    mid_set = {r["method_id"] for r in norm_rows}
    by_mid = {r["method_id"]: r for r in norm_rows}
    confirmed = []
    for e in confirmed_edges_raw:
        f_id = e.get("from_method_id", "")
        t_id = e.get("to_method_id", "")
        # Both endpoints must be in the family OR be case_evidence_method
        f_in = f_id in mid_set or f_id.startswith("case_evidence::")
        t_in = t_id in mid_set or t_id.startswith("case_evidence::")
        # At least one endpoint in family
        if not (f_in or t_in): continue
        # If both endpoints valid → confirmed
        e["from_year"] = ""
        e["to_year"] = ""
        if f_id in by_mid: e["from_year"] = by_mid[f_id]["year"]
        if t_id in by_mid: e["to_year"] = by_mid[t_id]["year"]
        confirmed.append(e)
    return confirmed


def build_candidate_edges(norm_rows, confirmed_edges):
    """spec 五 candidate:
        - 核心 (core_process 或 core_material) 高度相关
        - 年份顺序合理
        - 无直接关系句 (即不在 confirmed 里)
        - 禁止仅凭年份/名称相似/同材料判定
    """
    # Precompute a set of confirmed pair keys
    conf_keys = set()
    for e in confirmed_edges:
        f = e.get("from_method_id", "")
        t = e.get("to_method_id", "")
        conf_keys.add((f, t))
        conf_keys.add((t, f))

    # Only 2 or more year-resolved methods can form candidates
    dated = []
    for r in norm_rows:
        try: y = int(r["year"]) if r["year"] else 0
        except ValueError: y = 0
        if y > 0: dated.append((y, r))

    cand = []
    for i in range(len(dated)):
        y_i, r_i = dated[i]
        for j in range(len(dated)):
            if i == j: continue
            y_j, r_j = dated[j]
            if y_i >= y_j: continue   # 时间顺序: from 早, to 晚 (for EXTENDS-like); ADAPTS/IMPROVES from晚→to早的语义已由confirmed 表达
            # Skip if already confirmed
            if (r_i["method_id"], r_j["method_id"]) in conf_keys: continue
            if (r_j["method_id"], r_i["method_id"]) in conf_keys: continue

            # Core similarity - process AND material
            cp_i = (r_i.get("core_process") or "").strip()
            cp_j = (r_j.get("core_process") or "").strip()
            cm_i = (r_i.get("core_material") or "").strip()
            cm_j = (r_j.get("core_material") or "").strip()
            tgt_i = (r_i.get("target_problem") or "").strip()
            tgt_j = (r_j.get("target_problem") or "").strip()

            # 只做候选: 至少 process 或 material 精确相同 + target 相同
            proc_same = cp_i and cp_j and cp_i == cp_j
            mat_same = cm_i and cm_j and cm_i == cm_j
            tgt_same = tgt_i and tgt_j and tgt_i == tgt_j
            if not (proc_same or mat_same): continue
            if not tgt_same: continue

            # 相同论文的方法不作跨引用候选 (仅内部 own-ref 关系已在 confirmed)
            if r_i["paper_id"] == r_j["paper_id"]: continue

            # 猜测关系类型 (仅提示, 不认定)
            hint = "similar_core"
            if proc_same and mat_same and tgt_same: hint = "same_all"
            elif proc_same: hint = "same_process"
            elif mat_same: hint = "same_material"

            cand.append({
                "candidate_edge_id": f"CAND_{len(cand)+1:03d}",
                "from_method_id": r_i["method_id"],
                "to_method_id": r_j["method_id"],
                "from_method_name": r_i["canonical_method_name"],
                "to_method_name": r_j["canonical_method_name"],
                "from_year": y_i,
                "to_year": y_j,
                "from_paper_id": r_i["paper_id"],
                "to_paper_id": r_j["paper_id"],
                "similarity_hint": hint,
                "core_process": cp_i or cp_j,
                "core_material": cm_i or cm_j,
                "target_problem": tgt_i,
                "note": ("候选关系: 核心工艺/材料/目标高度相关且年份顺序合理, "
                          "但**缺少原文直接关系句**. 不进入正式关系统计; "
                          "图中显示为虚线."),
                "prohibition_flag": ("not_confirmed_evolution: "
                                      "prohibited to claim lineage "
                                      "based on year+similarity alone"),
            })
    # Cap candidates at 40 to keep the graph readable
    cand.sort(key=lambda x: (x["from_year"], x["to_year"]))
    return cand[:40]


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError): pass

    norm = load_norm()
    conf_raw = load_confirmed_edges()

    # Phase 4
    earliest = find_earliest_traceable(norm)
    if earliest is None:
        print("ERROR: no dated node meeting earliest criteria")
        return 3
    with open(os.path.join(OUT_DIR, "lineage_earliest_source.json"),
                "w", encoding="utf-8") as f:
        json.dump(earliest, f, ensure_ascii=False, indent=2)
    print(f"earliest: {earliest['earliest_traceable_author']} "
            f"({earliest['earliest_traceable_year']}) - "
            f"{earliest['earliest_traceable_method'][:50]}")

    # Phase 5.1 confirmed
    confirmed = build_confirmed_edges(norm, conf_raw, earliest)
    with open(os.path.join(OUT_DIR, "lineage_edges_confirmed.csv"),
                "w", encoding="utf-8-sig", newline="") as f:
        fields = (list(confirmed[0].keys()) if confirmed
                    else ["edge_id", "paper_id", "relation",
                            "from_method_id", "to_method_id"])
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for e in confirmed: w.writerow(e)
    print(f"confirmed edges: {len(confirmed)}")

    # Phase 5.2 candidate
    cand = build_candidate_edges(norm, confirmed)
    with open(os.path.join(OUT_DIR, "lineage_edges_candidate.csv"),
                "w", encoding="utf-8-sig", newline="") as f:
        if cand:
            fields = list(cand[0].keys())
        else:
            fields = ["candidate_edge_id", "from_method_id", "to_method_id"]
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for e in cand: w.writerow(e)
    print(f"candidate edges: {len(cand)}")

    # lineage_evidence.md
    lines = ["# 方法谱系 — 证据与关系清单\n\n"]
    lines.append(f"## 最早可追溯来源 (spec 四)\n\n")
    lines.append(f"> {earliest['canonical_note']}\n\n")
    lines.append(f"- **method**: `{earliest['earliest_traceable_method']}`\n")
    lines.append(f"- **author**: {earliest['earliest_traceable_author']}\n")
    lines.append(f"- **year**: {earliest['earliest_traceable_year']}\n")
    lines.append(f"- **year_source**: `{earliest['year_source']}`\n")
    lines.append(f"- **paper_id**: `{earliest['paper_id']}`\n")
    lines.append(f"- **kind**: {earliest['kind']}\n")
    if earliest.get("source_reference_text"):
        lines.append(f"- **参考条目文本**: {earliest['source_reference_text'][:200]}\n")
    lines.append(f"\n**边界说明**: {earliest['limitation_note']}\n\n")

    lines.append(f"## Confirmed 关系 (spec 五, 实线, {len(confirmed)} 条)\n\n")
    for e in confirmed:
        lines.append(f"- **{e.get('relation','?')}**: "
                       f"`{e.get('from_method_name','?')[:35]}` "
                       f"→ `{e.get('to_method_name','?')[:35]}`\n")
        sids = _parse_sids(e.get("relation_evidence_sentence_ids", ""))
        for sid in sids:
            lines.append(f"  - evidence: `{sid}`\n")
        if e.get("direction_basis"):
            lines.append(f"  - direction_basis: {e['direction_basis'][:200]}\n")
        lines.append("\n")

    lines.append(f"## Candidate 关系 (spec 五, 虚线, {len(cand)} 条; "
                   "**不进入正式关系统计**)\n\n")
    lines.append("> **禁止**: 因年份晚就判演化; 因名称相似就判演化; "
                   "因同材料就判演化.\n\n")
    lines.append("| from | to | 相似度 | from_year | to_year |\n")
    lines.append("|---|---|---|---:|---:|\n")
    for e in cand[:20]:
        lines.append(f"| {e['from_method_name'][:30]} "
                       f"| {e['to_method_name'][:30]} "
                       f"| {e['similarity_hint']} "
                       f"| {e['from_year']} | {e['to_year']} |\n")
    if len(cand) > 20:
        lines.append(f"\n*(仅显示前 20 条, 总 {len(cand)} 条见 CSV)*\n")

    with open(os.path.join(OUT_DIR, "lineage_evidence.md"),
                "w", encoding="utf-8") as f:
        f.writelines(lines)
    print(f"outputs: {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
