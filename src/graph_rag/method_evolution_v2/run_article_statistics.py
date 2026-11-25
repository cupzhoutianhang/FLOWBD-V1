"""run_article_statistics.py — article minimal statistics (spec 二, 无 API).

只用现有 337 篇 + accepted 方法 (main_storage 主) 生成论文级 10 项统计.

输出到:
  paper/method_evolution_v2/article_minimal_results/
    - article_statistics.csv (10 blocks stacked)
    - methods_for_article.csv (只含 main_storage + accepted, 论文表格用)
    - figure_data/*.csv (每张图一份数据)
    - article_results_summary.md
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

from method_evolution_v2 import config                                # noqa: E402


AGG_DIR = os.path.join(config.STAGE_A_FULL_V1_DIR, "aggregation")
OUT_DIR = os.path.join(config.PAPER_V2_DIR, "article_minimal_results")
FIG_DIR = os.path.join(OUT_DIR, "figure_data")


def load_methods(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def load_per_paper():
    with open(os.path.join(AGG_DIR, "per_paper_summary.csv"),
                "r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def scope_of(p_context_status):
    s = (p_context_status or "").strip().lower()
    if s == "confirmed": return "main_storage"
    if s == "non_storage": return "non_storage"
    return "uncertain"


def _write_csv(path, fields, rows):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows: w.writerow(r)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(FIG_DIR, exist_ok=True)

    accepted_all = load_methods(os.path.join(AGG_DIR, "methods_accepted.csv"))
    candidate_all = load_methods(os.path.join(AGG_DIR, "methods_candidate.csv"))
    rejected_all = load_methods(os.path.join(AGG_DIR, "methods_rejected.csv"))
    per_paper = load_per_paper()

    # 主统计口径: main_storage + accepted; non_storage 不进入
    accepted_main = [m for m in accepted_all
                       if scope_of(m.get("paper_context_status")) == "main_storage"]
    accepted_all_incl = accepted_all  # 保留全量做对比

    # === 1. 论文类型分布 (全 337) ===
    ptype_all = Counter(p["paper_type"] for p in per_paper)
    ptype_main = Counter(p["paper_type"] for p in per_paper
                            if scope_of(p["paper_context_status"]) == "main_storage")
    _write_csv(os.path.join(FIG_DIR, "1_paper_type_distribution.csv"),
                ["paper_type", "n_all_337", "n_main_storage"],
                [{"paper_type": k,
                    "n_all_337": ptype_all.get(k, 0),
                    "n_main_storage": ptype_main.get(k, 0)}
                    for k in sorted(set(ptype_all) | set(ptype_main))])

    # === 2. 储能一级领域分布 (只用 main_storage 篇数) ===
    domain_papers = Counter(p["primary_storage_domain"] for p in per_paper
                                if scope_of(p["paper_context_status"]) == "main_storage")
    _write_csv(os.path.join(FIG_DIR, "2_primary_storage_domain.csv"),
                ["primary_storage_domain", "n_papers"],
                [{"primary_storage_domain": k or "(空)", "n_papers": v}
                    for k, v in sorted(domain_papers.items(),
                                          key=lambda x: -x[1])])

    # === 3. 储能二级技术分布 (仅 main_storage) ===
    # 从 taxonomy csv 拉 subfield
    tax = {}
    tp = config.CORPUS_PP_V1_1_PAPER_TAXONOMY_CSV
    if os.path.isfile(tp):
        with open(tp, "r", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                tax[r["paper_id"]] = r
    subfield_papers = Counter()
    for p in per_paper:
        if scope_of(p["paper_context_status"]) != "main_storage": continue
        r = tax.get(p["paper_id"], {})
        sf = r.get("technology_subfield", "") or "(未标注)"
        subfield_papers[sf] += 1
    _write_csv(os.path.join(FIG_DIR, "3_technology_subfield.csv"),
                ["technology_subfield", "n_papers"],
                [{"technology_subfield": k, "n_papers": v}
                    for k, v in sorted(subfield_papers.items(),
                                          key=lambda x: -x[1])])

    # === 4. own/referenced 分布 (main_storage + accepted) ===
    kind_main = Counter(m["kind"] for m in accepted_main)
    kind_all = Counter(m["kind"] for m in accepted_all_incl)
    _write_csv(os.path.join(FIG_DIR, "4_kind_distribution.csv"),
                ["kind", "n_main_storage_accepted", "n_all_accepted"],
                [{"kind": k,
                    "n_main_storage_accepted": kind_main.get(k, 0),
                    "n_all_accepted": kind_all.get(k, 0)}
                    for k in ("own", "referenced")])

    # === 5. method_role 分布 (main_storage + accepted) ===
    role_main = Counter(m["method_role"] for m in accepted_main)
    _write_csv(os.path.join(FIG_DIR, "5_method_role_main.csv"),
                ["method_role", "n"],
                [{"method_role": k, "n": v}
                    for k, v in sorted(role_main.items(), key=lambda x: -x[1])])

    # === 6. 每篇方法数分布 (accepted, main_storage 单列) ===
    per_paper_acc_main = Counter()
    for m in accepted_main:
        per_paper_acc_main[m["paper_id"]] += 1
    # 论文 main_storage 里 accepted 数 = 0 的也要含
    for p in per_paper:
        if scope_of(p["paper_context_status"]) == "main_storage":
            per_paper_acc_main.setdefault(p["paper_id"], 0)
    bins = [(0, 0), (1, 2), (3, 5), (6, 10), (11, 20), (21, 999)]
    bin_counts = Counter()
    for pid, n in per_paper_acc_main.items():
        for lo, hi in bins:
            if lo <= n <= hi:
                bin_counts[(lo, hi)] += 1
                break
    _write_csv(os.path.join(FIG_DIR, "6_methods_per_paper_hist.csv"),
                ["bin_lo", "bin_hi", "n_papers"],
                [{"bin_lo": lo, "bin_hi": hi, "n_papers": bin_counts.get((lo, hi), 0)}
                    for lo, hi in bins])

    # === 7. accepted / candidate / rejected 比例 (全 337 + main_storage) ===
    counts_all = {
        "accepted": len(accepted_all_incl),
        "candidate": len(candidate_all),
        "rejected": len(rejected_all),
    }
    cand_main = [m for m in candidate_all
                    if scope_of(m.get("paper_context_status")) == "main_storage"]
    rej_main = [m for m in rejected_all
                   if scope_of(m.get("paper_context_status")) == "main_storage"]
    counts_main = {
        "accepted": len(accepted_main),
        "candidate": len(cand_main),
        "rejected": len(rej_main),
    }
    _write_csv(os.path.join(FIG_DIR, "7_status_ratio.csv"),
                ["status", "n_all", "n_main_storage"],
                [{"status": k, "n_all": counts_all[k],
                    "n_main_storage": counts_main[k]}
                    for k in ("accepted", "candidate", "rejected")])

    # === 8. evidence ID 有效率 + 切片一致率 (from report json) ===
    with open(os.path.join(AGG_DIR, "stage_a_full_report.json"),
                "r", encoding="utf-8") as f:
        rep = json.load(f)
    _write_csv(os.path.join(FIG_DIR, "8_evidence_quality.csv"),
                ["metric", "value_pct"],
                [{"metric": "evidence_id_valid_rate",
                    "value_pct": rep["evidence_id_valid_rate_pct"]},
                 {"metric": "slice_consistency",
                    "value_pct": rep["slice_consistency_pct"]}])

    # === 9. 不同储能领域的方法数量 (accepted, main_storage) ===
    domain_methods = Counter()
    for m in accepted_main:
        d = m.get("primary_storage_domain") or "(空)"
        domain_methods[d] += 1
    _write_csv(os.path.join(FIG_DIR, "9_methods_by_domain.csv"),
                ["primary_storage_domain", "n_accepted_methods"],
                [{"primary_storage_domain": k,
                    "n_accepted_methods": v}
                    for k, v in sorted(domain_methods.items(),
                                          key=lambda x: -x[1])])

    # === 10. research vs review 方法抽取差异 (main_storage + accepted) ===
    diff = defaultdict(lambda: {"n_papers": 0, "n_own_accepted": 0,
                                    "n_ref_accepted": 0, "n_total_accepted": 0})
    for p in per_paper:
        if scope_of(p["paper_context_status"]) != "main_storage": continue
        pt = p["paper_type"] or "(空)"
        diff[pt]["n_papers"] += 1
    for m in accepted_main:
        pt = m.get("paper_type") or "(空)"
        if m.get("kind") == "own":
            diff[pt]["n_own_accepted"] += 1
        elif m.get("kind") == "referenced":
            diff[pt]["n_ref_accepted"] += 1
        diff[pt]["n_total_accepted"] += 1
    for pt in list(diff.keys()):
        n_papers = max(1, diff[pt]["n_papers"])
        diff[pt]["avg_own_per_paper"] = round(
            diff[pt]["n_own_accepted"] / n_papers, 2)
        diff[pt]["avg_ref_per_paper"] = round(
            diff[pt]["n_ref_accepted"] / n_papers, 2)
        diff[pt]["avg_total_per_paper"] = round(
            diff[pt]["n_total_accepted"] / n_papers, 2)
    _write_csv(os.path.join(FIG_DIR, "10_type_extraction_diff.csv"),
                ["paper_type", "n_papers", "n_own_accepted",
                  "n_ref_accepted", "n_total_accepted",
                  "avg_own_per_paper", "avg_ref_per_paper",
                  "avg_total_per_paper"],
                [{**{"paper_type": k}, **v}
                    for k, v in sorted(diff.items(),
                                          key=lambda x: -x[1]["n_papers"])])

    # === methods_for_article.csv (main_storage + accepted) ===
    keep = ["paper_id", "canonical_title", "paper_type", "batch_num",
              "primary_storage_domain", "kind", "name",
              "normalized_method_name", "source_organization",
              "proposed_method_type", "method_role",
              "cited_author", "cited_reference_number",
              "external_stub_id", "evidence_sentence_ids",
              "evidence_text_resolved"]
    _write_csv(os.path.join(OUT_DIR, "methods_for_article.csv"),
                keep, accepted_main)

    # === article_statistics.csv (10 blocks stacked; 汇总入口) ===
    def _stacked_row(block, key, val, meta=""):
        return {"block": block, "key": key, "value": val, "meta": meta}
    stacked = []
    for k, v in ptype_main.items():
        stacked.append(_stacked_row("1_paper_type_main", k, v))
    for k, v in domain_papers.most_common():
        stacked.append(_stacked_row("2_primary_domain_main", k, v))
    for k, v in subfield_papers.most_common(20):
        stacked.append(_stacked_row("3_subfield_main", k, v))
    for k, v in kind_main.items():
        stacked.append(_stacked_row("4_kind_main", k, v))
    for k, v in role_main.items():
        stacked.append(_stacked_row("5_role_main", k, v))
    for lo, hi in bins:
        stacked.append(_stacked_row("6_hist",
                                        f"[{lo},{hi}]",
                                        bin_counts.get((lo, hi), 0)))
    for k, v in counts_main.items():
        stacked.append(_stacked_row("7_status_main", k, v))
    stacked.append(_stacked_row("8_evidence_quality",
                                     "evidence_id_valid_rate_pct",
                                     rep["evidence_id_valid_rate_pct"]))
    stacked.append(_stacked_row("8_evidence_quality",
                                     "slice_consistency_pct",
                                     rep["slice_consistency_pct"]))
    for k, v in domain_methods.most_common():
        stacked.append(_stacked_row("9_methods_by_domain_main", k, v))
    for pt, d in diff.items():
        stacked.append(_stacked_row("10_type_diff_main", pt,
                                        d["n_total_accepted"],
                                        f"avg={d['avg_total_per_paper']}"))
    _write_csv(os.path.join(OUT_DIR, "article_statistics.csv"),
                ["block", "key", "value", "meta"], stacked)

    # === MD 汇总 ===
    md = [
        f"# 论文最小结果 — 基础统计 (v1)\n\n",
        f"> Generated: {datetime.now().isoformat(timespec='seconds')}\n",
        f"> 数据集: 337 篇 (固定, 不再扩充)\n",
        f"> 统计口径: main_storage + accepted 为主; candidate 只报数不进领域结论;"
        f" non_storage 不进主统计\n\n",
        f"## 边界声明\n",
        f"- 本研究基于 337 篇既有储能相关中文文献.\n",
        f"- 结果反映该数据集内的方法分布与演化证据.\n",
        f"- 不声称覆盖全部储能文献.\n",
        f"- 未收录的方法不在本研究结论范围内.\n",
        f"- referenced 方法只表示当前文献中的二手描述, 不补原始论文.\n",
        f"- 方法演化能力通过代表性案例验证, 不做全库演化网络穷举.\n\n",
        f"## 一. 论文类型分布\n",
        f"| paper_type | 全 337 | main_storage |\n",
        f"|---|---:|---:|\n",
    ]
    for k in sorted(set(ptype_all) | set(ptype_main)):
        md.append(f"| {k} | {ptype_all.get(k, 0)} | {ptype_main.get(k, 0)} |\n")

    md.append(f"\n## 二. 储能一级领域分布 (main_storage {sum(domain_papers.values())} 篇)\n")
    md.append("| primary_storage_domain | 篇数 |\n|---|---:|\n")
    for k, v in sorted(domain_papers.items(), key=lambda x: -x[1]):
        md.append(f"| {k or '(空)'} | {v} |\n")

    md.append(f"\n## 三. 储能二级技术分布 (main_storage) — top 15\n")
    md.append("| technology_subfield | 篇数 |\n|---|---:|\n")
    for k, v in subfield_papers.most_common(15):
        md.append(f"| {k} | {v} |\n")

    md.append(f"\n## 四. own / referenced 分布 (main_storage + accepted)\n")
    md.append("| kind | n |\n|---|---:|\n")
    for k in ("own", "referenced"):
        md.append(f"| {k} | {kind_main.get(k, 0)} |\n")

    md.append(f"\n## 五. method_role 分布 (main_storage + accepted)\n")
    md.append("| method_role | n |\n|---|---:|\n")
    for k, v in sorted(role_main.items(), key=lambda x: -x[1]):
        md.append(f"| {k} | {v} |\n")

    md.append(f"\n## 六. 每篇方法数分布 (main_storage, accepted 计数)\n")
    md.append("| 方法数区间 | 篇数 |\n|---|---:|\n")
    for lo, hi in bins:
        label = f"{lo}" if lo == hi else (f"[{lo},{hi}]" if hi < 999 else f"≥{lo}")
        md.append(f"| {label} | {bin_counts.get((lo, hi), 0)} |\n")

    md.append(f"\n## 七. accepted / candidate / rejected 比例\n")
    md.append("| status | 全 337 | main_storage |\n|---|---:|---:|\n")
    for k in ("accepted", "candidate", "rejected"):
        md.append(f"| {k} | {counts_all[k]} | {counts_main[k]} |\n")

    md.append(f"\n## 八. 证据质量\n")
    md.append(f"- evidence sentence_id 有效率: "
                f"**{rep['evidence_id_valid_rate_pct']}%**\n")
    md.append(f"- 原文切片一致率: **{rep['slice_consistency_pct']}%**\n")

    md.append(f"\n## 九. 不同储能领域的方法数量 (main_storage + accepted)\n")
    md.append("| primary_storage_domain | accepted 方法数 |\n|---|---:|\n")
    for k, v in sorted(domain_methods.items(), key=lambda x: -x[1]):
        md.append(f"| {k} | {v} |\n")

    md.append(f"\n## 十. 研究论文 vs 综述的方法抽取差异 (main_storage)\n")
    md.append("| paper_type | 篇数 | own accepted | ref accepted | 总数 | 均值/篇 |\n")
    md.append("|---|---:|---:|---:|---:|---:|\n")
    for pt, d in sorted(diff.items(), key=lambda x: -x[1]["n_papers"]):
        md.append(f"| {pt} | {d['n_papers']} | {d['n_own_accepted']} "
                    f"| {d['n_ref_accepted']} | {d['n_total_accepted']} "
                    f"| {d['avg_total_per_paper']} |\n")

    md.append(f"\n## 产物路径\n")
    md.append(f"- `article_statistics.csv` (10 块堆叠)\n")
    md.append(f"- `methods_for_article.csv` "
                f"({len(accepted_main)} 条 main_storage + accepted)\n")
    md.append(f"- `figure_data/1_paper_type_distribution.csv` ~ "
                f"`10_type_extraction_diff.csv`\n")

    with open(os.path.join(OUT_DIR, "article_results_summary.md"),
                "w", encoding="utf-8") as f:
        f.writelines(md)

    print(f"OK — wrote {len(accepted_main)} main_storage + accepted methods "
            f"to methods_for_article.csv, plus 10 figure_data CSVs & summary md.")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError): pass
    sys.exit(main())
