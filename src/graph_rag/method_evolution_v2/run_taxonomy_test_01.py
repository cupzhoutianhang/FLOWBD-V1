"""run_taxonomy_test_01.py — 试运行 10 篇的 taxonomy 分类器 driver.

产物:
  - paper/method_evolution_v2/test_run_01/taxonomy_test.csv
  - paper/method_evolution_v2/test_run_01/taxonomy_test.md

数据流:
  full.md → section_parser (v1.1.1)
         → paper_type_rules (v1.0)  [提供 paper_type 给 taxonomy 做软偏置]
         → taxonomy_rules   (v1.0)  [输出 taxonomy 五维标签]

CSV 中的列表 / 对象字段一律用合法 JSON 字符串序列化 (json.dumps, ensure_ascii=False).

安全约束:
  - 不调用 LLM
  - 不写 Neo4j / Milvus
  - 不读 legacy 数据
  - 只运行 10 篇
"""
from __future__ import annotations

import csv
import json
import os
import sys
from datetime import datetime

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_GRAPH_RAG_DIR = os.path.dirname(THIS_DIR)
if SRC_GRAPH_RAG_DIR not in sys.path:
    sys.path.insert(0, SRC_GRAPH_RAG_DIR)

from method_evolution_v2 import config                                     # noqa: E402
from method_evolution_v2.io import section_parser as sp                    # noqa: E402
from method_evolution_v2.paper_type import paper_type_rules as ptr         # noqa: E402
from method_evolution_v2.taxonomy import taxonomy_rules as tr              # noqa: E402


CSV_FIELDS = [
    "paper_id",
    "paper_type",
    "primary_storage_domain",
    "secondary_storage_domains",
    "domain_candidates",
    "technology_subfield",
    "technology_variant",
    "application_contexts",
    "primary_method_type",
    "secondary_method_types",
    "paper_context_status",
    "matched_signals",
    "conflicting_signals",
    "evidence",
    "decision_reason",
    "taxonomy_version",
    "classified_at",
    # 辅助
    "section_coverage_ratio",
    "abstract_present",
]


def _json(v) -> str:
    """把 list / dict 转成 JSON 字符串; 标量原样返回."""
    if isinstance(v, (list, dict)):
        return json.dumps(v, ensure_ascii=False)
    return "" if v is None else str(v)


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    os.makedirs(config.TEST_RUN_01_DIR, exist_ok=True)

    rows = []
    details = []
    ran_at = datetime.now().isoformat(timespec="seconds")
    md_lines = []
    md_lines.append("# taxonomy 分类报告 — test_run_01\n")
    md_lines.append(
        f"> 运行时间: {ran_at}\n"
        f"> 输入: 10 篇试运行 full.md\n"
        f"> 章节解析: `section_parser` v{sp.SECTION_PARSER_VERSION}\n"
        f"> paper_type 分类器: `paper_type_rules` v{ptr.PAPER_TYPE_RULES_VERSION} (用于 method_type 软偏置)\n"
        f"> taxonomy 分类器: `taxonomy_rules` v{tr.TAXONOMY_VERSION}\n"
        f"> 关键词表: `taxonomy_keywords_v1.yaml` v{tr.load_keywords().get('version', 'unknown')}\n"
        f"> 无 LLM. 无 legacy 输入. 无数据库写入.\n"
    )
    md_lines.append("## 概览表\n")
    md_lines.append(
        "| # | paper_id | primary_domain | subfield | status | conf | variants | apps | primary_method |\n"
        "|---|----------|----------------|----------|:------:|:----:|----------|------|----------------|\n"
    )

    for idx, paper_id in enumerate(config.TEST_RUN_01_PAPER_IDS, 1):
        md_path = config.full_md_path(paper_id)
        if not os.path.isfile(md_path):
            row = {
                "paper_id": paper_id,
                "paper_type": None,
                "primary_storage_domain": None,
                "secondary_storage_domains": [],
                "domain_candidates": [],
                "technology_subfield": None,
                "technology_variant": [],
                "application_contexts": [],
                "primary_method_type": None,
                "secondary_method_types": [],
                "paper_context_status": "unknown",
                "matched_signals": [],
                "conflicting_signals": [{"key": "FULL_MD_MISSING", "detail": "input file not found"}],
                "evidence": [],
                "decision_reason": "input full.md missing",
                "taxonomy_version": (
                    f"taxonomy_rules={tr.TAXONOMY_VERSION}; "
                    f"keywords_yaml={tr.load_keywords().get('version', 'unknown')}"
                ),
                "classified_at": ran_at,
                "section_coverage_ratio": 0.0,
                "abstract_present": False,
            }
            rows.append(row)
            details.append(row)
            md_lines.append(
                f"| {idx} | {paper_id} | — | — | MISS | — | — | — | — |\n"
            )
            print(f"  [{idx:>2}/10] MISS {paper_id}")
            continue

        pr = sp.parse_file(paper_id, md_path)
        pt_r = ptr.classify_paper_type(pr)
        r = tr.classify_taxonomy(pr, paper_type_result=pt_r)

        row = dict(r)
        row["section_coverage_ratio"] = round(pr.section_coverage_ratio, 6)
        row["abstract_present"] = any(s.section_type == "abstract" for s in pr.sections)
        rows.append(row)
        details.append(row)

        md_lines.append(
            f"| {idx} | {paper_id[:36]} | `{r['primary_storage_domain'] or '(空)'}` "
            f"| `{r['technology_subfield'] or '(空)'}` "
            f"| {r['paper_context_status']} "
            f"| {'⚠' if r['conflicting_signals'] else '—'} "
            f"| {(', '.join(r['technology_variant']) or '—')} "
            f"| {(', '.join(r['application_contexts']) or '—')} "
            f"| `{r['primary_method_type'] or '(空)'}` |\n"
        )
        print(
            f"  [{idx:>2}/10] {r['paper_context_status']:<10} "
            f"primary={str(r['primary_storage_domain']):<24} "
            f"subfield={str(r['technology_subfield']):<32} "
            f"{paper_id[:40]}"
        )

    # -------- 详情 --------
    md_lines.append("\n## 每篇详情\n")
    for row in details:
        pid = row["paper_id"]
        md_lines.append(f"\n### {pid}\n")
        md_lines.append(
            f"- **paper_type**: `{row.get('paper_type')}`\n"
            f"- **primary_storage_domain**: `{row['primary_storage_domain'] or '(空)'}`\n"
            f"- **secondary_storage_domains**: `{json.dumps(row['secondary_storage_domains'], ensure_ascii=False)}`\n"
            f"- **domain_candidates**: `{json.dumps(row['domain_candidates'], ensure_ascii=False)}`\n"
            f"- **technology_subfield**: `{row['technology_subfield'] or '(空)'}`\n"
            f"- **technology_variant**: `{json.dumps(row['technology_variant'], ensure_ascii=False)}`\n"
            f"- **application_contexts**: `{json.dumps(row['application_contexts'], ensure_ascii=False)}`\n"
            f"- **primary_method_type**: `{row['primary_method_type'] or '(空)'}`\n"
            f"- **secondary_method_types**: `{json.dumps(row['secondary_method_types'], ensure_ascii=False)}`\n"
            f"- **paper_context_status**: `{row['paper_context_status']}`\n"
            f"- **decision_reason**: {row['decision_reason']}\n"
            f"- **taxonomy_version**: `{row['taxonomy_version']}`\n"
            f"- **classified_at**: `{row['classified_at']}`\n"
        )
        if row.get("matched_signals"):
            md_lines.append("- **matched_signals**:\n")
            for s in row["matched_signals"]:
                md_lines.append(f"  - `{s['key']}` — {s['detail']}\n")
        if row.get("conflicting_signals"):
            md_lines.append("- **conflicting_signals**:\n")
            for s in row["conflicting_signals"]:
                md_lines.append(f"  - `{s['key']}` — {s['detail']}\n")
        if row.get("evidence"):
            md_lines.append("- **evidence (top 12)**:\n")
            for ev in row["evidence"][:12]:
                exc = (ev.get("excerpt") or "").replace("\n", " ")
                if len(exc) > 160:
                    exc = exc[:160] + "…"
                md_lines.append(
                    f"  - [{ev['location']} / {ev.get('for', '?')} / "
                    f"{ev.get('strength', '')}] matched={ev['matched']!r}"
                    + (f" — {exc}" if exc else "")
                    + "\n"
                )

    # -------- 章节覆盖率审计 --------
    md_lines.append("\n## 章节覆盖率回归审计\n")
    regressed = [r for r in rows if r.get("section_coverage_ratio", 1.0) != 1.0]
    if regressed:
        for r in regressed:
            md_lines.append(f"- ⚠ `{r['paper_id']}`: coverage={r['section_coverage_ratio']}\n")
    else:
        md_lines.append("✓ 全部 10 篇章节覆盖率仍为 1.0.\n")

    # -------- 写 CSV (合法 JSON) --------
    with open(config.TEST_RUN_01_TAXONOMY_CSV, "w",
              encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        for row in rows:
            csv_row = {}
            for k in CSV_FIELDS:
                csv_row[k] = _json(row.get(k))
            w.writerow(csv_row)

    with open(config.TEST_RUN_01_TAXONOMY_MD, "w", encoding="utf-8") as f:
        f.writelines(md_lines)

    print()
    print("=" * 60)
    print(f"CSV: {config.relative_path(config.TEST_RUN_01_TAXONOMY_CSV)}")
    print(f"MD : {config.relative_path(config.TEST_RUN_01_TAXONOMY_MD)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
