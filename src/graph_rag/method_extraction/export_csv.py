"""
export_csv.py — 把 method_outputs/*.json 导出为两份 CSV 供人工校对

输入  : src/graph_rag/method_extraction/method_outputs/*.json
        publish_year_report.csv  (附加 year 字段)
输出  :
  methods.csv : 每个方法一行 (own + referenced)
                paper_id, year, kind, method_name, innovation, problem_solved,
                key_components, citation_clue
  edges.csv   : 每条演化边一行
                from_paper, from_paper_year, from_method, to_method,
                relation, confidence, evidence, reason

用法:
  python export_csv.py                    # 全量导出
  python export_csv.py --since 锂枝晶     # 只看 paper_id 含 "锂枝晶" 的
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from typing import Optional

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(THIS_DIR, "method_outputs")
METHODS_CSV = os.path.join(THIS_DIR, "methods.csv")
EDGES_CSV = os.path.join(THIS_DIR, "edges.csv")
YEAR_REPORT_CSV = os.path.join(THIS_DIR, "publish_year_report.csv")


def load_year_map() -> dict[str, Optional[int]]:
    out: dict[str, Optional[int]] = {}
    if not os.path.isfile(YEAR_REPORT_CSV):
        return out
    with open(YEAR_REPORT_CSV, "r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            y = row["year"].strip()
            out[row["paper_id"]] = int(y) if y.isdigit() else None
    return out


def export(filter_substring: str = "") -> tuple[int, int]:
    """返回 (methods_n, edges_n)."""
    if not os.path.isdir(OUTPUT_DIR):
        print(f"[ERR] {OUTPUT_DIR} 不存在", file=sys.stderr)
        return 0, 0

    files = sorted(
        f for f in os.listdir(OUTPUT_DIR) if f.endswith(".json")
    )
    if filter_substring:
        files = [f for f in files if filter_substring in f]

    year_map = load_year_map()

    methods_rows: list[list] = []
    edges_rows: list[list] = []

    for fn in files:
        path = os.path.join(OUTPUT_DIR, fn)
        try:
            with open(path, "r", encoding="utf-8") as f:
                d = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            print(f"  [skip] {fn}: {exc}", file=sys.stderr)
            continue

        paper_id = d.get("paper_id") or fn[:-5]
        # year 优先从 method JSON 取, 退化用 year_map
        year = d.get("year")
        if year is None:
            year = year_map.get(paper_id)

        # own_methods
        for m in d.get("own_methods", []) or []:
            methods_rows.append(
                [
                    paper_id,
                    year if year is not None else "",
                    "own",
                    m.get("name", ""),
                    m.get("innovation", ""),
                    m.get("problem_solved", ""),
                    " | ".join(m.get("key_components", []) or []),
                    "",  # citation_clue 仅 ref 有
                ]
            )

        # referenced_methods
        for m in d.get("referenced_methods", []) or []:
            methods_rows.append(
                [
                    paper_id,
                    year if year is not None else "",
                    "ref",
                    m.get("name", ""),
                    "",
                    "",
                    "",
                    m.get("citation_clue", ""),
                ]
            )

        # evolution_edges
        for e in d.get("evolution_edges", []) or []:
            edges_rows.append(
                [
                    paper_id,
                    year if year is not None else "",
                    e.get("from_method", ""),
                    e.get("to_method", ""),
                    e.get("relation", ""),
                    e.get("confidence", ""),
                    e.get("evidence", ""),
                    e.get("reason", ""),
                ]
            )

    # 写 methods.csv
    with open(METHODS_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "paper_id",
                "year",
                "kind",
                "method_name",
                "innovation",
                "problem_solved",
                "key_components",
                "citation_clue",
            ]
        )
        w.writerows(methods_rows)

    # 写 edges.csv
    with open(EDGES_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "from_paper",
                "from_paper_year",
                "from_method",
                "to_method",
                "relation",
                "confidence",
                "evidence",
                "reason",
            ]
        )
        w.writerows(edges_rows)

    return len(methods_rows), len(edges_rows)


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="", help="只导出 paper_id 含此字串的篇 (调试)")
    args = ap.parse_args()

    n_m, n_e = export(args.since)

    print(f"导出完成:")
    print(f"  methods.csv : {n_m} 行  -> {METHODS_CSV}")
    print(f"  edges.csv   : {n_e} 行  -> {EDGES_CSV}")
    print()
    # 简要分布
    if n_e:
        from collections import Counter

        rel_counter: Counter[str] = Counter()
        conf_counter: Counter[str] = Counter()
        with open(EDGES_CSV, "r", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                rel_counter[row["relation"]] += 1
                conf_counter[row["confidence"]] += 1
        print("relation 分布:", dict(rel_counter))
        print("confidence 分布:", dict(conf_counter))
    return 0


if __name__ == "__main__":
    sys.exit(main())
