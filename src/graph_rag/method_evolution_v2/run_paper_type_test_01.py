"""run_paper_type_test_01.py — 试运行 10 篇的 paper_type 分类器 driver.

产物:
  - paper/method_evolution_v2/test_run_01/paper_type_test.csv
  - paper/method_evolution_v2/test_run_01/paper_type_test.md

不调用 LLM. 不写 Neo4j/Milvus. 不读 legacy 数据.
只依赖 io.section_parser + paper_type.paper_type_rules.

用法:
  python -X utf8 -m method_evolution_v2.run_paper_type_test_01
或
  python -X utf8 src/graph_rag/method_evolution_v2/run_paper_type_test_01.py
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

from method_evolution_v2 import config                                    # noqa: E402
from method_evolution_v2.io import section_parser as sp                   # noqa: E402
from method_evolution_v2.paper_type import paper_type_rules as ptr        # noqa: E402


CSV_FIELDS = [
    "paper_id",
    "paper_type",
    "rule_confidence",
    "matched_signals",
    "conflicting_signals",
    "type_evidence",
    "decision_reason",
    "parser_version",
    "classified_at",
    # 附加辅助字段, 便于人工排查
    "section_coverage_ratio",
    "has_text_loss",
    "abstract_present",
]


def _flatten_signals(sig_list) -> str:
    """把 [{"key": ..., "detail": ...}, ...] 压成分号分隔的字符串."""
    parts = []
    for s in sig_list:
        parts.append(f"{s['key']}({s['detail']})")
    return "; ".join(parts)


def _flatten_evidence(ev_list) -> str:
    parts = []
    for e in ev_list:
        excerpt = (e.get("excerpt") or "").replace("\n", " ")
        if len(excerpt) > 100:
            excerpt = excerpt[:100] + "…"
        parts.append(f"[{e['source']}/{e['matched_for']}] {excerpt}")
    return "; ".join(parts)


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    os.makedirs(config.TEST_RUN_01_DIR, exist_ok=True)

    rows = []
    details = []          # 每篇的完整结构化结果, 用于 MD 详情渲染 (避免 flatten 造成的切分错误)
    md_lines = []
    coverage_regressed = []
    ran_at = datetime.now().isoformat(timespec="seconds")
    md_lines.append("# paper_type 分类报告 — test_run_01\n")
    md_lines.append(
        f"> 运行时间: {ran_at}\n"
        f"> 输入: 10 篇试运行 full.md (章节解析 v{sp.SECTION_PARSER_VERSION})\n"
        f"> 分类器: `src/graph_rag/method_evolution_v2/paper_type/paper_type_rules.py` "
        f"(v{ptr.PAPER_TYPE_RULES_VERSION})\n"
        f"> 无 LLM 调用. 无 legacy 输入. 无数据库写入.\n"
    )
    md_lines.append("## 概览表\n")
    md_lines.append(
        "| # | paper_id | paper_type | 置信 | 冲突 | 摘要 | 覆盖率 |\n"
        "|---|----------|------------|:----:|:----:|:----:|-------:|\n"
    )

    for idx, paper_id in enumerate(config.TEST_RUN_01_PAPER_IDS, 1):
        md_path = config.full_md_path(paper_id)
        if not os.path.isfile(md_path):
            rows.append({
                "paper_id": paper_id,
                "paper_type": "unclear",
                "rule_confidence": "low",
                "matched_signals": "",
                "conflicting_signals": "FULL_MD_MISSING",
                "type_evidence": "",
                "decision_reason": "input full.md missing",
                "parser_version": (
                    f"section_parser={sp.SECTION_PARSER_VERSION}; "
                    f"paper_type_rules={ptr.PAPER_TYPE_RULES_VERSION}"
                ),
                "classified_at": ran_at,
                "section_coverage_ratio": 0.0,
                "has_text_loss": True,
                "abstract_present": False,
            })
            details.append({
                "paper_id": paper_id, "missing": True,
                "matched_signals": [], "conflicting_signals": [], "type_evidence": [],
            })
            md_lines.append(
                f"| {idx} | {paper_id} | unclear | low | MISS | — | — |\n"
            )
            print(f"  [{idx:>2}/10] MISS  {paper_id}")
            continue

        # 每次都实时解析, 保证吃的是最新 section_parser 输出 (v1.1.1)
        pr = sp.parse_file(paper_id, md_path)
        if pr.section_coverage_ratio != 1.0 or pr.has_text_loss:
            coverage_regressed.append((paper_id, pr.section_coverage_ratio, pr.has_text_loss))
        has_abstract = any(s.section_type == "abstract" for s in pr.sections)

        r = ptr.classify_paper_type(pr)

        rows.append({
            "paper_id": paper_id,
            "paper_type": r["paper_type"],
            "rule_confidence": r["rule_confidence"],
            "matched_signals": _flatten_signals(r["matched_signals"]),
            "conflicting_signals": _flatten_signals(r["conflicting_signals"]),
            "type_evidence": _flatten_evidence(r["type_evidence"]),
            "decision_reason": r["decision_reason"],
            "parser_version": r["parser_version"],
            "classified_at": r["classified_at"],
            "section_coverage_ratio": round(pr.section_coverage_ratio, 6),
            "has_text_loss": pr.has_text_loss,
            "abstract_present": has_abstract,
        })
        # MD 详情用结构化数据 (避免 ; 切分误伤)
        details.append({
            "paper_id": paper_id, "missing": False,
            "matched_signals": r["matched_signals"],
            "conflicting_signals": r["conflicting_signals"],
            "type_evidence": r["type_evidence"],
        })

        conflict_mark = "⚠" if r["conflicting_signals"] else "—"
        abs_mark = "✓" if has_abstract else "—"
        md_lines.append(
            f"| {idx} | {paper_id[:36]} | `{r['paper_type']}` "
            f"| {r['rule_confidence']} | {conflict_mark} | {abs_mark} "
            f"| {pr.section_coverage_ratio:.3f} |\n"
        )
        print(
            f"  [{idx:>2}/10] {r['paper_type']:<18} conf={r['rule_confidence']:<6} "
            f"conflicts={len(r['conflicting_signals'])} "
            f"coverage={pr.section_coverage_ratio:.3f} {paper_id[:50]}"
        )

    # ---------- 每篇详情 ----------
    md_lines.append("\n## 每篇详情\n")
    detail_by_pid = {d["paper_id"]: d for d in details}
    for row in rows:
        pid = row["paper_id"]
        d = detail_by_pid.get(pid, {})
        md_lines.append(f"\n### {pid}\n")
        md_lines.append(
            f"- **paper_type**: `{row['paper_type']}`\n"
            f"- **rule_confidence**: `{row['rule_confidence']}`\n"
            f"- **decision_reason**: {row['decision_reason']}\n"
            f"- **section_coverage_ratio**: {row['section_coverage_ratio']}\n"
            f"- **has_text_loss**: {row['has_text_loss']}\n"
            f"- **abstract_present**: {row['abstract_present']}\n"
            f"- **parser_version**: `{row['parser_version']}`\n"
            f"- **classified_at**: `{row['classified_at']}`\n"
        )
        matched = d.get("matched_signals") or []
        if matched:
            md_lines.append("- **matched_signals**:\n")
            for s in matched:
                md_lines.append(f"  - `{s['key']}` — {s['detail']}\n")
        conflicting = d.get("conflicting_signals") or []
        if conflicting:
            md_lines.append("- **conflicting_signals**:\n")
            for s in conflicting:
                md_lines.append(f"  - `{s['key']}` — {s['detail']}\n")
        evidence = d.get("type_evidence") or []
        if evidence:
            md_lines.append("- **type_evidence**:\n")
            for ev in evidence:
                excerpt = (ev.get("excerpt") or "").replace("\n", " ")
                if len(excerpt) > 220:
                    excerpt = excerpt[:220] + "…"
                md_lines.append(
                    f"  - [{ev['source']} / {ev['matched_for']}] {excerpt}\n"
                )

    # ---------- 章节覆盖率审计 ----------
    md_lines.append("\n## 章节覆盖率回归审计\n")
    if coverage_regressed:
        md_lines.append("⚠ 以下论文覆盖率非 100%:\n\n")
        for pid, ratio, loss in coverage_regressed:
            md_lines.append(f"- `{pid}`: coverage={ratio:.6f}, has_text_loss={loss}\n")
    else:
        md_lines.append("✓ 全部 10 篇章节覆盖率仍为 1.0, 无文本丢失.\n")

    # ---------- 写文件 ----------
    with open(config.TEST_RUN_01_PAPER_TYPE_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        for row in rows:
            w.writerow(row)

    with open(config.TEST_RUN_01_PAPER_TYPE_MD, "w", encoding="utf-8") as f:
        f.writelines(md_lines)

    print()
    print("=" * 60)
    print(f"CSV: {config.relative_path(config.TEST_RUN_01_PAPER_TYPE_CSV)}")
    print(f"MD : {config.relative_path(config.TEST_RUN_01_PAPER_TYPE_MD)}")
    if coverage_regressed:
        print(f"⚠ coverage regression: {len(coverage_regressed)} papers")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
