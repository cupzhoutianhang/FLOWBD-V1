"""run_lineage_family_selection.py — spec 一 家族候选 + auto-pick MVP.

从 1147 accepted 方法里, 按 4 个预定义方法家族筛候选:
  1. 锰基/氧化锰电极结构
  2. 相变材料渗漏/最佳含量测定
  3. 钠离子电池层状氧化物改性
  4. 液流电池流场结构优化

家族硬门槛 (spec 一):
  - ≥5 相关方法
  - ≥3 年份
  - ≥1 confirmed 关系 (来自 final_case)
  - 作者/引用编号较完整
  - 原文证据可回溯
  - 方法之间共享技术核心 (非仅同域)

无 API. 输出:
  lineage_family_candidates.csv
  lineage_family_candidates.md
  lineage_selected_family.json  (auto-pick #1)
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys
from collections import defaultdict

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_GRAPH_RAG_DIR = os.path.dirname(THIS_DIR)
if SRC_GRAPH_RAG_DIR not in sys.path:
    sys.path.insert(0, SRC_GRAPH_RAG_DIR)

from method_evolution_v2 import config                                # noqa: E402
from method_evolution_v2.lineage import reference_parser as rp        # noqa: E402


OUT_DIR = os.path.join(config.PAPER_V2_DIR, "article_minimal_results",
                          "lineage_mvp")
os.makedirs(OUT_DIR, exist_ok=True)

AGG_DIR = os.path.join(config.STAGE_A_FULL_V1_DIR, "aggregation")
FINAL_CASE_DIR = os.path.join(config.PAPER_V2_DIR, "article_minimal_results",
                                   "final_case")


FAMILY_DEFS = [
    {
        "id": "mn_electrode_structure",
        "name": "锰基/氧化锰电极结构 (锂离子/超级电容/负极)",
        "material_kws": ["锰氧化物", "氧化锰", "MnO2", "Mn2O3", "Mn3O4",
                            "锰酸锂", "LiMn2O4", "锰基", "锰"],
        "process_kws": ["水热", "沉淀", "电沉积", "溶胶-凝胶", "熔融", "空心",
                          "圆锥", "纳米", "复合", "碳"],
        "application_kws": ["电极", "锂离子电池", "超级电容", "赝电容",
                              "负极", "储能"],
        "anchor_paper": "表面化学反应控制制备多级结构电极材料及性能",
    },
    {
        "id": "pcm_leakage_optimization",
        "name": "相变材料渗漏/最佳含量测定/定形封装",
        "material_kws": ["相变", "PCM", "石蜡", "脂肪酸", "月桂酸",
                            "肉豆蔻酸", "棕榈酸", "膨胀石墨", "MA/EG"],
        "process_kws": ["渗漏", "渗出", "最佳含量", "定形", "封装",
                          "测定", "评定", "含量", "复合相变"],
        "application_kws": ["储热", "蓄热", "热储能", "储能", "建材"],
        "anchor_paper": "脂肪类复合相变储能材料中脂肪酸最佳质量含量的确定方法",
    },
    {
        "id": "sodium_layered_oxide_modification",
        "name": "钠离子电池层状氧化物改性方法",
        "material_kws": ["Na", "钠离子", "钠", "层状氧化物", "NaMnO",
                            "P2型", "O3型", "Na正极", "钠电"],
        "process_kws": ["改性", "掺杂", "包覆", "结构调控", "表面处理"],
        "application_kws": ["钠离子电池", "钠电", "储钠", "储能", "正极"],
        "anchor_paper": None,
    },
    {
        "id": "flow_battery_flow_field",
        "name": "液流电池流场结构/流道优化",
        "material_kws": ["流场", "流道", "碳毡", "石墨毡", "液流",
                            "全钒", "PEM", "膜电极"],
        "process_kws": ["优化", "设计", "均一性", "分布", "结构"],
        "application_kws": ["液流电池", "钒", "储能", "电堆"],
        "anchor_paper": None,
    },
]


def contains_any(text, kws):
    t = text or ""
    return any(k in t for k in kws)


def method_matches_family(m, fam):
    name = (m.get("name") or "") + " " + (m.get("normalized_method_name") or "")
    combined = name + " " + (m.get("evidence_text_resolved") or "")
    material_hit = contains_any(combined, fam["material_kws"])
    proc_hit = contains_any(combined, fam["process_kws"])
    app_hit = contains_any(combined, fam["application_kws"])
    # spec 一: 共享技术核心, 而非仅同域 →
    #   要求 material AND process, 保证方法在同一技术子机制内
    #   (anchor 论文的方法可豁免 process 要求, 依然可入)
    if not material_hit: return False
    if fam.get("anchor_paper") and m.get("paper_id") == fam["anchor_paper"]:
        return True
    return proc_hit and (app_hit or fam.get("anchor_paper") is None)


def load_accepted_methods():
    with open(os.path.join(AGG_DIR, "methods_accepted.csv"),
                "r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def load_confirmed_edges():
    """From final_case/final_storage_case_edges.csv"""
    p = os.path.join(FINAL_CASE_DIR, "final_storage_case_edges.csv")
    if not os.path.isfile(p): return []
    with open(p, "r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def resolve_year_for_method(m, ref_by_paper, publish_year_by_paper):
    """spec 三 优先级."""
    pid = m.get("paper_id", "")
    kind = m.get("kind", "")
    citation_clue = m.get("citation_clue", "") or ""
    method_name = m.get("name", "") or ""

    # own: use paper publish year (priority 1)
    if kind == "own":
        y, s = publish_year_by_paper.get(pid, (None, "unresolved"))
        if y: return y, s, "", ""
        return None, "unresolved", "", ""

    # referenced: try author+year in citation_clue / method_name
    y, s, refnum = rp.parse_citation_clue_for_year(citation_clue, method_name)
    if y: return y, s, "", ""

    # try to look up reference number in that paper's reference list
    if refnum and pid in ref_by_paper:
        entry = ref_by_paper[pid].get(refnum)
        if entry and entry.get("year"):
            return (entry["year"], "reference_list_entry",
                     entry.get("author", ""),
                     entry.get("raw_text", ""))
    return None, "unresolved", "", ""


def evaluate_family(fam, methods, confirmed_edges, ref_by_paper,
                       publish_year_by_paper):
    fam_methods = [m for m in methods if method_matches_family(m, fam)]
    if not fam_methods:
        return None

    # Resolve years
    year_info = {}
    for m in fam_methods:
        y, s, author, ref_txt = resolve_year_for_method(
            m, ref_by_paper, publish_year_by_paper)
        year_info[m["method_id"]] = {
            "year": y, "year_source": s,
            "source_author": author, "source_reference_text": ref_txt}
    resolved_years = [year_info[m["method_id"]]["year"]
                        for m in fam_methods if year_info[m["method_id"]]["year"]]
    n_year_resolved = len(resolved_years)
    year_span = len(set(resolved_years))

    # Confirmed edges within this family
    fam_method_ids = {m["method_id"] for m in fam_methods}
    fam_paper_ids = {m["paper_id"] for m in fam_methods}
    conf_in_fam = [e for e in confirmed_edges
                     if e.get("paper_id") in fam_paper_ids
                     and (e.get("from_method_id") in fam_method_ids
                            or e.get("to_method_id") in fam_method_ids)]

    # scoring
    n_methods = len(fam_methods)
    n_papers = len(fam_paper_ids)
    n_confirmed = len(conf_in_fam)
    if n_methods < 5 or year_span < 3 or n_confirmed < 1:
        # 仍返回, 但标 pass_gates=False
        pass_gates = False
    else:
        pass_gates = True

    score = 0.0
    score += min(n_methods, 20) * 1.0
    score += n_year_resolved * 1.5
    score += year_span * 2.0
    score += n_confirmed * 6.0
    score += n_papers * 0.8

    return {
        "family_id": fam["id"],
        "family_name": fam["name"],
        "n_methods": n_methods,
        "n_papers": n_papers,
        "n_year_resolved": n_year_resolved,
        "year_span": year_span,
        "years_resolved_set": sorted(set(resolved_years)),
        "n_confirmed_edges": n_confirmed,
        "confirmed_edges_summary": [
            f"{e.get('paper_id','')[:15]}::{e.get('relation','')}::"
            f"{e.get('from_method_name','')[:20]}→"
            f"{e.get('to_method_name','')[:20]}"
            for e in conf_in_fam[:5]],
        "pass_gates": pass_gates,
        "score": round(score, 2),
        "fam_methods": fam_methods,
        "year_info": year_info,
        "confirmed_edges": conf_in_fam,
    }


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError): pass

    methods = load_accepted_methods()
    confirmed_edges = load_confirmed_edges()

    # Preload all papers' reference lists + publish years
    ref_by_paper = {}
    publish_year_by_paper = {}
    seen_pids = set()
    for m in methods:
        pid = m["paper_id"]
        if pid in seen_pids: continue
        seen_pids.add(pid)
        publish_year_by_paper[pid] = rp.load_publish_year(pid)
        md_path = config.full_md_path(pid)
        if os.path.isfile(md_path):
            with open(md_path, "r", encoding="utf-8") as f:
                text = f.read()
            ref_by_paper[pid] = rp.parse_references(text)

    print(f"loaded {len(methods)} accepted methods across "
            f"{len(seen_pids)} papers")
    print(f"papers with parsed references: "
            f"{sum(1 for v in ref_by_paper.values() if v)}")

    # Evaluate each family
    results = []
    for fam in FAMILY_DEFS:
        r = evaluate_family(fam, methods, confirmed_edges,
                                 ref_by_paper, publish_year_by_paper)
        if r: results.append(r)

    results.sort(key=lambda x: (-x["pass_gates"], -x["score"]))

    # Take top 3 as candidates
    top3 = results[:3]

    # Write CSV
    csv_fields = ["family_id", "family_name", "n_methods", "n_papers",
                    "n_year_resolved", "year_span", "years_resolved_set",
                    "n_confirmed_edges", "pass_gates", "score"]
    with open(os.path.join(OUT_DIR, "lineage_family_candidates.csv"),
                "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=csv_fields, extrasaction="ignore")
        w.writeheader()
        for r in top3:
            row = dict(r)
            row["years_resolved_set"] = json.dumps(
                r["years_resolved_set"], ensure_ascii=False)
            w.writerow(row)

    # Write MD
    md = ["# 方法家族候选 (MVP 谱系筛选)\n\n"]
    md.append(f"> 从 337 篇 1147 条 accepted 方法里, 按 4 个预定义家族硬门槛筛选;\n")
    md.append(f"> 硬门槛: ≥5 方法 + ≥3 年份 + ≥1 confirmed 关系 + 共享技术核心.\n\n")

    md.append("## 排名\n\n")
    md.append("| # | family_id | n_methods | n_papers | n_year_resolved | "
                "year_span | n_confirmed | 硬门槛通过 | score |\n")
    md.append("|:-:|---|---:|---:|---:|---:|---:|:-:|---:|\n")
    for i, r in enumerate(top3, 1):
        md.append(f"| {i} | {r['family_id']} | {r['n_methods']} "
                    f"| {r['n_papers']} | {r['n_year_resolved']} "
                    f"| {r['year_span']} | {r['n_confirmed_edges']} "
                    f"| {'YES' if r['pass_gates'] else 'NO'} "
                    f"| {r['score']} |\n")

    md.append("\n---\n\n## 每个家族详情\n\n")
    for i, r in enumerate(top3, 1):
        md.append(f"### {i}. {r['family_name']}\n\n")
        md.append(f"- **family_id**: `{r['family_id']}`\n")
        md.append(f"- **相关方法数**: {r['n_methods']}\n")
        md.append(f"- **覆盖论文数**: {r['n_papers']}\n")
        md.append(f"- **有年份的方法**: {r['n_year_resolved']}\n")
        md.append(f"- **年份分布**: {r['years_resolved_set']}\n")
        md.append(f"- **confirmed 关系数**: {r['n_confirmed_edges']}\n")
        if r["confirmed_edges_summary"]:
            md.append(f"  - 示例:\n")
            for s in r["confirmed_edges_summary"]:
                md.append(f"    - {s}\n")
        md.append(f"- **硬门槛通过**: {'YES' if r['pass_gates'] else 'NO'}\n")
        md.append(f"- **paper_score**: {r['score']}\n\n")

    with open(os.path.join(OUT_DIR, "lineage_family_candidates.md"),
                "w", encoding="utf-8") as f:
        f.writelines(md)

    # Auto-pick #1 (must pass gates)
    passing = [r for r in top3 if r["pass_gates"]]
    if not passing:
        # 仍选 top 1, 标 warn
        chosen = top3[0] if top3 else None
        warn = "no_family_passes_all_gates_using_top1_anyway"
    else:
        chosen = passing[0]
        warn = ""

    if chosen:
        sel = {
            "selected_family_id": chosen["family_id"],
            "selected_family_name": chosen["family_name"],
            "n_methods": chosen["n_methods"],
            "n_papers": chosen["n_papers"],
            "n_confirmed_edges": chosen["n_confirmed_edges"],
            "pass_gates": chosen["pass_gates"],
            "warning": warn,
            "method_ids": [m["method_id"] for m in chosen["fam_methods"]],
            "paper_ids": sorted({m["paper_id"] for m in chosen["fam_methods"]}),
            "year_info": chosen["year_info"],
        }
        with open(os.path.join(OUT_DIR, "lineage_selected_family.json"),
                    "w", encoding="utf-8") as f:
            json.dump(sel, f, ensure_ascii=False, indent=2)
        print(f"\nAUTO-PICKED: {chosen['family_id']} "
                f"({chosen['n_methods']} methods, "
                f"{chosen['n_confirmed_edges']} confirmed, "
                f"pass_gates={chosen['pass_gates']}, warn={warn})")

    print(f"outputs: {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
