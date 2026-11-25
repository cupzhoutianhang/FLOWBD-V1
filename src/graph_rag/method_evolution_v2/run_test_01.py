"""run_test_01.py — MVP 步 1 驱动脚本.

对 config.TEST_RUN_01_PAPER_IDS 中的 10 篇执行章节解析,
写以下产物到 paper/method_evolution_v2/test_run_01/:
  - sections/<paper_id>.json
  - section_parse_report.csv
  - section_parse_report.md
并更新 source_version_lock.json (含 SHA256/大小/解析时间).

不调用任何 LLM, 不写数据库, 不读 legacy 数据.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
from datetime import datetime

# Ensure import path
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_GRAPH_RAG_DIR = os.path.dirname(THIS_DIR)
if SRC_GRAPH_RAG_DIR not in sys.path:
    sys.path.insert(0, SRC_GRAPH_RAG_DIR)

from method_evolution_v2 import config  # noqa: E402
from method_evolution_v2.io import section_parser as sp  # noqa: E402


def sha256_of_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1 << 16)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    os.makedirs(config.TEST_RUN_01_SECTIONS_DIR, exist_ok=True)

    lock_entries = []
    report_rows = []
    md_lines = []
    md_lines.append("# 章节解析报告 — test_run_01\n")
    md_lines.append(
        f"> 运行时间: {datetime.now().isoformat(timespec='seconds')}\n"
        f"> 解析 10 篇试运行论文\n"
        f"> 解析器: `src/graph_rag/method_evolution_v2/io/section_parser.py`\n"
        f"> 输入根目录: `{config.relative_path(config.DOWNLOADED_FILES_DIR)}`\n"
    )

    md_lines.append("## 概览表\n")
    md_lines.append(
        "| # | paper_id | 字节 | 字符 | 段落数 | 覆盖率 | abstract | methods | results | conclusion |\n"
        "|---|----------|----:|----:|----:|------:|:---:|:---:|:---:|:---:|\n"
    )

    for idx, paper_id in enumerate(config.TEST_RUN_01_PAPER_IDS, 1):
        md_path = config.full_md_path(paper_id)
        exists = os.path.isfile(md_path)
        size_bytes = os.path.getsize(md_path) if exists else 0
        sha = sha256_of_file(md_path) if exists else ""

        if not exists:
            lock_entries.append({
                "paper_id": paper_id,
                "full_md_relative_path": config.relative_path(md_path),
                "full_md_absolute_path_at_lock_time": md_path,
                "exists": False,
                "size_bytes": 0,
                "sha256": "",
                "parsed_at_iso": "",
            })
            report_rows.append({
                "paper_id": paper_id,
                "exists": False,
                "size_bytes": 0,
                "source_md_chars": 0,
                "n_sections": 0,
                "n_paragraphs": 0,
                "section_coverage_ratio": 0.0,
                "paragraph_coverage_ratio": 0.0,
                "has_text_loss": True,
                "abstract_recognized": False,
                "methods_recognized": False,
                "results_recognized": False,
                "conclusion_recognized": False,
                "other_chars_ratio": 1.0,
                "document_title": "",
                "notes": "FULL_MD_MISSING",
            })
            md_lines.append(
                f"| {idx} | {paper_id} | — | — | — | — | ✗ | ✗ | ✗ | ✗ |\n"
            )
            print(f"  [{idx:>2}/10] MISS  {paper_id}")
            continue

        result = sp.parse_file(paper_id, md_path)
        out_path = os.path.join(config.TEST_RUN_01_SECTIONS_DIR, f"{paper_id}.json")
        sp.write_json(result, out_path)

        section_types = [s.section_type for s in result.sections]
        type_counts = {}
        for t in section_types:
            type_counts[t] = type_counts.get(t, 0) + 1

        # 各章节是否识别 (只看是否存在该类型 markdown heading)
        abstract_ok = "abstract" in section_types
        methods_ok = "methods" in section_types
        results_ok = ("results" in section_types) or ("results_discussion" in section_types)
        concl_ok = "conclusion" in section_types

        n_para = sum(len(s.paragraphs) for s in result.sections)
        other_chars = sum(
            (s.char_end - s.char_start)
            for s in result.sections
            if s.section_type == "other_sections"
        )
        other_ratio = (other_chars / result.source_md_chars) if result.source_md_chars else 0.0

        lock_entries.append({
            "paper_id": paper_id,
            "full_md_relative_path": config.relative_path(md_path),
            "full_md_absolute_path_at_lock_time": md_path,
            "exists": True,
            "size_bytes": size_bytes,
            "sha256": sha,
            "parsed_at_iso": result.parse_time_iso,
        })

        report_rows.append({
            "paper_id": paper_id,
            "exists": True,
            "size_bytes": size_bytes,
            "source_md_chars": result.source_md_chars,
            "n_sections": len(result.sections),
            "n_paragraphs": n_para,
            "section_coverage_ratio": round(result.section_coverage_ratio, 6),
            "paragraph_coverage_ratio": round(result.paragraph_coverage_ratio, 6),
            "has_text_loss": result.has_text_loss,
            "abstract_recognized": abstract_ok,
            "methods_recognized": methods_ok,
            "results_recognized": results_ok,
            "conclusion_recognized": concl_ok,
            "other_chars_ratio": round(other_ratio, 6),
            "document_title": result.document_title or "",
            "notes": ";".join(result.notes),
        })

        md_lines.append(
            f"| {idx} | {paper_id[:36]} | {size_bytes} | {result.source_md_chars} | "
            f"{n_para} | {result.section_coverage_ratio:.3f} | "
            f"{'✓' if abstract_ok else '—'} | {'✓' if methods_ok else '—'} | "
            f"{'✓' if results_ok else '—'} | {'✓' if concl_ok else '—'} |\n"
        )
        print(
            f"  [{idx:>2}/10] OK    sections={len(result.sections):<3} "
            f"para={n_para:<3} coverage={result.section_coverage_ratio:.3f} "
            f"{paper_id[:50]}"
        )

    # 写 CSV 报告
    with open(config.TEST_RUN_01_REPORT_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(report_rows[0].keys()))
        w.writeheader()
        for row in report_rows:
            w.writerow(row)

    # ---------- markdown 详情 ----------
    md_lines.append("\n## 每篇章节明细\n")
    for paper_id in config.TEST_RUN_01_PAPER_IDS:
        json_path = os.path.join(config.TEST_RUN_01_SECTIONS_DIR, f"{paper_id}.json")
        if not os.path.isfile(json_path):
            md_lines.append(f"\n### {paper_id}\n\n_FULL_MD_MISSING — 已跳过_\n")
            continue
        with open(json_path, "r", encoding="utf-8") as f:
            d = json.load(f)
        md_lines.append(f"\n### {paper_id}\n")
        md_lines.append(
            f"- source_md_chars: **{d['source_md_chars']}**\n"
            f"- section_coverage_ratio: **{d['section_coverage_ratio']:.4f}**\n"
            f"- paragraph_coverage_ratio: **{d['paragraph_coverage_ratio']:.4f}**\n"
            f"- has_text_loss: **{d['has_text_loss']}**\n"
            f"- document_title: `{d['document_title']}`\n"
            f"- 章节列表:\n"
        )
        for s in d["sections"]:
            md_lines.append(
                f"  - [{s['section_index']:02d}] `{s['section_type']:<22}` "
                f"H{s['heading_level']} "
                f"conf={s['confidence']:<6} "
                f"by={'MD' if s['matched_by_markdown_heading'] else '--'}/"
                f"{'INF' if s['inferred_by_regex'] else '---'} "
                f"src={s['inference_source']:<48} "
                f"[{s['char_start']:>6}, {s['char_end']:>6}) "
                f"paras={len(s['paragraphs']):<3} "
                f"head={s['raw_heading'][:40]!r}\n"
            )

    # ---------- 章节标题审计 (v1.1 新增) ----------
    md_lines.append("\n## 章节标题审计\n")
    md_lines.append(
        "> 全部原始标题 (含无 markdown 标题的 inline 段) + 标准类型 + 推断来源 + 置信度.\n"
        "> 用于排查为什么部分内容落到 other_sections.\n\n"
    )
    md_lines.append(
        "| paper_id | idx | H | confidence | section_type | inference_source | raw_heading |\n"
        "|----------|----:|--:|:----------:|--------------|------------------|-------------|\n"
    )
    for paper_id in config.TEST_RUN_01_PAPER_IDS:
        json_path = os.path.join(config.TEST_RUN_01_SECTIONS_DIR, f"{paper_id}.json")
        if not os.path.isfile(json_path):
            continue
        with open(json_path, "r", encoding="utf-8") as f:
            d = json.load(f)
        for s in d["sections"]:
            head = (s["raw_heading"] or "(no_heading)").replace("|", "\\|")[:60]
            md_lines.append(
                f"| {paper_id[:24]} | {s['section_index']:>2} | {s['heading_level']} "
                f"| {s['confidence']} | `{s['section_type']}` "
                f"| {s['inference_source']} | {head} |\n"
            )

    with open(config.TEST_RUN_01_REPORT_MD, "w", encoding="utf-8") as f:
        f.writelines(md_lines)

    # ---------- 写版本锁 ----------
    lock = {
        "lock_created_at": datetime.now().isoformat(timespec="seconds"),
        "lock_purpose": "freeze V2 test_run_01 inputs: paths/size/sha256/parse_time",
        "v2_authoritative_inputs": {
            "downloaded_files_dir": config.relative_path(config.DOWNLOADED_FILES_DIR),
            "publish_year_report_csv_reference_only": config.relative_path(
                config.LEGACY_YEAR_REPORT_CSV
            ),
        },
        "v2_input_papers_test_run_01": lock_entries,
        "legacy_files_not_v2_input": {
            k: config.relative_path(v)
            for k, v in config.LEGACY_PATHS_DO_NOT_INPUT.items()
        },
        "legacy_inputs_declaration": (
            "These legacy files are NOT V2 inputs. They are only kept as comparison "
            "targets for diffing V1 vs V2. V2 extraction/relation/classification "
            "scripts MUST NOT read them."
        ),
    }
    with open(config.SOURCE_VERSION_LOCK_JSON, "w", encoding="utf-8") as f:
        json.dump(lock, f, ensure_ascii=False, indent=2)

    print()
    print("=" * 60)
    print(f"section JSONs : {config.relative_path(config.TEST_RUN_01_SECTIONS_DIR)}")
    print(f"CSV 报告      : {config.relative_path(config.TEST_RUN_01_REPORT_CSV)}")
    print(f"MD 报告       : {config.relative_path(config.TEST_RUN_01_REPORT_MD)}")
    print(f"版本锁        : {config.relative_path(config.SOURCE_VERSION_LOCK_JSON)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
