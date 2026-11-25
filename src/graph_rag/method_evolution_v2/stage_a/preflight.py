"""Stage A 全量前的输入质量预检 (spec 八, 无 API 调用).

检查项:
  - 337 篇输入齐全 (每个 paper_id 都有 full.md)
  - sentence index 能否全部生成
  - sentence_id 是否唯一
  - 原文切片是否全部一致 (spec 二: 硬性 100%)
  - 是否有空输入
  - 是否有超出 128k tier 上下文
  - 每篇实际送入哪些章节 (SECTION_PACK_ORDER 覆盖 + other_sections hit)
  - other_sections 是否被保留
  - canonical_title 是否全部存在
  - paper_type / taxonomy 是否能正确关联
  - 输出路径是否存在冲突
"""
from __future__ import annotations

import os

from method_evolution_v2 import config
from method_evolution_v2.io import section_parser as sp
from method_evolution_v2.stage_a import sentence_indexer as si
from method_evolution_v2.stage_a.method_extraction import (
    SECTION_PACK_ORDER, OTHER_SECTIONS_METHOD_HINTS,
)
from method_evolution_v2.stage_a.budget_estimator import (
    estimate_tokens_from_chars, PROMPT_OVERHEAD_CHARS,
)


CONTEXT_LIMIT_TOKENS = 128_000    # moonshot-v1-128k tier 上限


def _filter_sentences_for_pack(all_sents):
    """与 build_sentence_index_for_llm 同样的过滤规则."""
    keep = []
    for s in all_sents:
        st = s.section_type
        if st in SECTION_PACK_ORDER:
            keep.append(s)
            continue
        if st == "other_sections" and s.section_name \
                and OTHER_SECTIONS_METHOD_HINTS.search(s.section_name):
            keep.append(s)
    return keep


def run_preflight(paper_ids: list,
                   sections_dir: str = None,
                   canonical_titles_csv: str = None,
                   paper_types_csv: str = None,
                   taxonomy_csv: str = None) -> dict:
    """对给定 paper_ids 跑全部预检.

    Args:
      paper_ids: list of paper_id
      sections_dir: sections JSON 目录 (默认 corpus_preprocess_v1_1/sections)
    Returns:
      { 'summary': {...}, 'per_paper': [ {...} ], 'issues': [...] }
    """
    import csv, json
    sections_dir = sections_dir or config.CORPUS_PP_V1_1_SECTIONS_DIR
    canonical_titles_csv = canonical_titles_csv or os.path.join(
        config.CORPUS_PP_V1_1_DIR, "canonical_titles.csv")
    paper_types_csv = paper_types_csv or config.CORPUS_PP_V1_1_PAPER_TYPES_CSV
    taxonomy_csv = taxonomy_csv or config.CORPUS_PP_V1_1_PAPER_TAXONOMY_CSV

    # 加载辅助表
    canonical_titles = {}
    if os.path.isfile(canonical_titles_csv):
        with open(canonical_titles_csv, "r", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                canonical_titles[r["paper_id"]] = r.get("canonical_title", "")

    paper_types = {}
    if os.path.isfile(paper_types_csv):
        with open(paper_types_csv, "r", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                paper_types[r["paper_id"]] = r.get("paper_type", "")

    taxonomy_by_pid = {}
    if os.path.isfile(taxonomy_csv):
        with open(taxonomy_csv, "r", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                taxonomy_by_pid[r["paper_id"]] = r

    per_paper = []
    issues = []
    n_missing_fullmd = 0
    n_missing_sections_json = 0
    n_empty_input = 0
    n_slice_mismatch = 0
    n_sid_dup = 0
    n_over_context = 0
    n_missing_canonical_title = 0
    n_missing_paper_type = 0
    n_missing_taxonomy = 0
    total_sents = 0
    total_pack_chars = 0
    over_context_ids = []

    for pid in paper_ids:
        entry = {"paper_id": pid}

        # 1. full.md exists
        md_path = config.full_md_path(pid)
        entry["full_md_exists"] = os.path.isfile(md_path)
        if not entry["full_md_exists"]:
            n_missing_fullmd += 1
            issues.append((pid, "missing_full_md"))
            per_paper.append(entry)
            continue

        # 2. sections JSON exists (or can be generated)
        sec_path = os.path.join(sections_dir, f"{pid}.json")
        entry["sections_json_exists"] = os.path.isfile(sec_path)
        if not entry["sections_json_exists"]:
            n_missing_sections_json += 1
            issues.append((pid, "missing_sections_json"))

        # 3. Parse full.md and build sentence index
        try:
            pr = sp.parse_file(pid, md_path)
        except Exception as e:
            entry["parse_error"] = f"{type(e).__name__}: {e}"
            issues.append((pid, entry["parse_error"]))
            per_paper.append(entry)
            continue

        with open(md_path, "r", encoding="utf-8") as f:
            full_md_text = f.read()

        # 用 section_parser 结果构造 sections_json dict
        sections_json = {"sections": []}
        for s in pr.sections:
            sections_json["sections"].append({
                "section_index": s.section_index,
                "section_type": s.section_type,
                "raw_heading": s.raw_heading,
                "char_start": s.char_start,
                "char_end": s.char_end,
                "paragraphs": [{
                    "para_id": p.para_id, "text": p.text,
                    "char_start": p.char_start, "char_end": p.char_end,
                } for p in s.paragraphs],
            })

        all_sents = si.build_sentence_index(sections_json, pid)
        entry["sentence_count"] = len(all_sents)
        total_sents += len(all_sents)
        if len(all_sents) == 0:
            n_empty_input += 1
            issues.append((pid, "empty_sentence_index"))

        # 4. sentence_id uniqueness within paper
        seen_sids = set()
        dupes = []
        for s in all_sents:
            if s.sentence_id in seen_sids:
                dupes.append(s.sentence_id)
            else:
                seen_sids.add(s.sentence_id)
        entry["sentence_id_dupes"] = dupes
        if dupes:
            n_sid_dup += 1
            issues.append((pid, f"sentence_id_dupes={dupes[:3]}"))

        # 5. slice-back verification
        slice_ok, mismatches = si.verify_sentence_slices(all_sents, full_md_text)
        entry["slice_verify_ok"] = slice_ok
        entry["slice_mismatch_count"] = len(mismatches)
        if not slice_ok:
            n_slice_mismatch += 1
            issues.append((pid, f"slice_mismatch_count={len(mismatches)}"))

        # 6. sentence pack size (LLM 输入)
        keep = _filter_sentences_for_pack(all_sents)
        entry["pack_sentence_count"] = len(keep)
        pack_text = si.sentence_index_to_pack(keep)
        pack_chars = len(pack_text) + PROMPT_OVERHEAD_CHARS
        entry["pack_char_count"] = pack_chars
        total_pack_chars += pack_chars
        est_tokens = estimate_tokens_from_chars(pack_chars)
        entry["estimated_input_tokens"] = est_tokens
        if est_tokens > CONTEXT_LIMIT_TOKENS:
            n_over_context += 1
            over_context_ids.append(pid)
            issues.append((pid, f"over_context_tokens={est_tokens}"))

        # 7. section-type coverage
        covered_types = set()
        for s in keep:
            covered_types.add(s.section_type)
        entry["covered_section_types"] = sorted(covered_types)

        # other_sections 保留数
        other_kept = [s for s in keep if s.section_type == "other_sections"]
        entry["other_sections_kept"] = len(other_kept)

        # 8. canonical_title
        entry["canonical_title"] = canonical_titles.get(pid, "")
        if not entry["canonical_title"]:
            n_missing_canonical_title += 1
            issues.append((pid, "missing_canonical_title"))

        # 9. paper_type / taxonomy
        entry["paper_type"] = paper_types.get(pid, "")
        if not entry["paper_type"]:
            n_missing_paper_type += 1
            issues.append((pid, "missing_paper_type"))
        entry["taxonomy_present"] = pid in taxonomy_by_pid
        if not entry["taxonomy_present"]:
            n_missing_taxonomy += 1
            issues.append((pid, "missing_taxonomy_row"))

        per_paper.append(entry)

    summary = {
        "n_papers_input": len(paper_ids),
        "n_missing_full_md": n_missing_fullmd,
        "n_missing_sections_json": n_missing_sections_json,
        "n_empty_input": n_empty_input,
        "n_sentence_id_dup_papers": n_sid_dup,
        "n_slice_mismatch_papers": n_slice_mismatch,
        "n_over_context_tokens_papers": n_over_context,
        "n_missing_canonical_title": n_missing_canonical_title,
        "n_missing_paper_type": n_missing_paper_type,
        "n_missing_taxonomy": n_missing_taxonomy,
        "total_sentences": total_sents,
        "avg_sentences_per_paper": (total_sents / max(len(paper_ids), 1)),
        "avg_pack_chars_per_paper": (total_pack_chars / max(len(paper_ids), 1)),
        "papers_over_128k_tokens_list": over_context_ids,
        "issues_count": len(issues),
    }
    return {"summary": summary, "per_paper": per_paper, "issues": issues}
