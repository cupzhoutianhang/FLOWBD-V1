"""run_lineage_normalize.py — spec 二 + 三: normalize names + resolve years.

对选中的 MVP 家族的 37 条方法:
  - 抽 canonical_method_name (去作者/机构前缀; 保留材料/工艺/结构/目标)
  - 抽 core_process / core_material / target_problem / application
  - 解析年份 (spec 三 优先级) + author + reference_number + source_status
  - **不回写 Stage A 全量方法表**

无 API. 输出:
  lineage_methods_normalized.csv
  lineage_name_mapping.csv
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_GRAPH_RAG_DIR = os.path.dirname(THIS_DIR)
if SRC_GRAPH_RAG_DIR not in sys.path:
    sys.path.insert(0, SRC_GRAPH_RAG_DIR)

from method_evolution_v2 import config                                # noqa: E402
from method_evolution_v2.lineage import reference_parser as rp        # noqa: E402


AGG_DIR = os.path.join(config.STAGE_A_FULL_V1_DIR, "aggregation")
OUT_DIR = os.path.join(config.PAPER_V2_DIR, "article_minimal_results",
                          "lineage_mvp")


# ============================================================
# Author / prefix cleanup for canonical_method_name
# ============================================================

AUTHOR_PREFIX_RES = [
    re.compile(r"^([一-鿿]{1,10})等[\s,\-—:：]*"),   # 王五等 / 孙建忠等
    re.compile(r"^([A-Z][A-Za-z\-]{2,20})(?:等|\s+et\s+al)?[\s,\-—:：]*"),
    re.compile(r"^\[?(\d{1,3})\]?[\s,\-—:：]+"),      # [16]xxx
    re.compile(r"^[一-鿿]{2,20}(大学|学院|公司|研究所|研究院|集团|中心|"
                    r"实验室)[\s,\-—:：]*"),  # 厦门大学...
]


def strip_author_prefix(name):
    """Iteratively strip author/inst/refnum prefixes; return cleaned name."""
    n = (name or "").strip()
    changed = True
    while changed:
        changed = False
        for rgx in AUTHOR_PREFIX_RES:
            m = rgx.match(n)
            if m:
                n = n[m.end():].strip()
                changed = True
                break
    return n


# ============================================================
# Extract core process / material / target / application
# ============================================================

# ordered material tokens (specific first)
CORE_MATERIAL_TOKENS = [
    # PCM-specific materials
    ("肉豆蔻酸/膨胀石墨", ["肉豆蔻酸/膨胀石墨", "MA/EG"]),
    ("月桂酸-肉豆蔻酸-棕榈酸/膨胀石墨", ["月桂酸-肉豆蔻酸-棕榈酸/膨胀石墨"]),
    ("石蜡", ["石蜡"]),
    ("三聚氰胺脲醛树脂石蜡微胶囊", ["三聚氰胺脲醛树脂石蜡微胶囊"]),
    ("十二水磷酸氢二钠", ["十二水磷酸氢二钠"]),
    ("三水醋酸钠", ["三水醋酸钠"]),
    ("癸酸-十六醇", ["癸酸-十六醇"]),
    ("癸酸-石蜡", ["癸酸-石蜡"]),
    ("PEG/PLA/Al2O3", ["PEG/PLA/Al2O3"]),
    ("癸酸-月桂酸/膨胀石墨", ["癸酸-月桂酸/膨胀石墨"]),
    ("脂肪酸", ["脂肪酸"]),
    ("月桂酸", ["月桂酸"]),
    ("肉豆蔻酸", ["肉豆蔻酸"]),
    ("棕榈酸", ["棕榈酸"]),
    ("癸酸", ["癸酸"]),
    ("PEG", ["PEG", "聚乙二醇"]),
    ("石墨烯", ["石墨烯"]),
    ("膨胀石墨", ["膨胀石墨"]),
    ("水凝胶", ["水凝胶"]),
    ("气凝胶", ["气凝胶"]),
    ("陶瓷", ["陶瓷"]),
    ("水泥基", ["水泥基"]),
    ("柔性相变薄膜", ["柔性相变薄膜"]),
    ("微胶囊", ["微胶囊"]),
    ("相变材料", ["相变材料", "PCM"]),
]

CORE_PROCESS_TOKENS = [
    ("扩散-渗出圈法", ["扩散-渗出圈法", "扩散—渗出圈法", "渗出圈法"]),
    ("步冷曲线法", ["步冷", "step cooling"]),
    ("原位聚合法", ["原位聚合"]),
    ("微胶囊化法", ["微胶囊化", "封装", "包覆"]),
    ("熔融共混法", ["熔融共混", "熔融"]),
    ("溶液共混法", ["溶液共混"]),
    ("最佳含量测定", ["最佳含量", "最佳质量含量", "最佳质量分数"]),
    ("定形封装", ["定形", "封装"]),
    ("渗漏评定", ["渗漏", "渗出", "泄漏"]),
    ("正交实验优化", ["正交实验"]),
    ("等效显热容法", ["等效显热容"]),
    ("直接接触式测量", ["直接接触"]),
    ("DSC 测试", ["DSC", "示差扫描量热"]),
    ("热导率测试", ["热导率测试"]),
    ("循环稳定性测试", ["循环稳定性", "循环性能"]),
]

TARGET_PROBLEM_TOKENS = [
    ("渗漏防治", ["渗漏", "渗出", "泄漏", "外流"]),
    ("最佳含量测定", ["最佳含量", "最佳质量含量", "最佳质量分数",
                        "含量优化"]),
    ("热导率提升", ["热导率", "导热"]),
    ("循环稳定性", ["循环稳定", "循环性能"]),
    ("过冷抑制", ["过冷"]),
    ("相分离控制", ["相分离"]),
    ("定形/形态保持", ["定形", "形态"]),
    ("封装", ["封装", "包覆", "微胶囊"]),
    ("热存储密度", ["存储密度", "储能密度"]),
    ("测试方法建立", ["测试方法", "评价方法", "评定方法"]),
]

APPLICATION_TOKENS = [
    ("建材节能", ["建材", "被动式建筑", "建筑节能", "水泥"]),
    ("工业蓄热", ["工业蓄热", "储热系统"]),
    ("低温冷链", ["冷链", "低温"]),
    ("智慧穿戴", ["柔性", "可穿戴"]),
    ("热管理", ["热管理", "电子器件热管理"]),
    ("热能储存", ["储热", "蓄热", "热储能"]),
    ("PCM 通用", ["相变材料", "PCM"]),
]


def extract_first_token(text, groups):
    t = text or ""
    for label, kws in groups:
        if any(kw in t for kw in kws):
            return label
    return ""


# ============================================================
# Main
# ============================================================

def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError): pass

    with open(os.path.join(OUT_DIR, "lineage_selected_family.json"),
                "r", encoding="utf-8") as f:
        sel = json.load(f)
    mid_set = set(sel["method_ids"])
    pid_set = set(sel["paper_ids"])
    print(f"family: {sel['selected_family_name']}")
    print(f"methods: {len(mid_set)}, papers: {len(pid_set)}")

    # Load accepted rows for selected methods
    fam_rows = []
    with open(os.path.join(AGG_DIR, "methods_accepted.csv"),
                "r", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r["method_id"] in mid_set:
                fam_rows.append(r)

    # Pre-parse references + publish years for these papers
    ref_by_paper = {}
    py_by_paper = {}
    for pid in pid_set:
        py_by_paper[pid] = rp.load_publish_year(pid)
        p = config.full_md_path(pid)
        if os.path.isfile(p):
            with open(p, "r", encoding="utf-8") as f:
                text = f.read()
            ref_by_paper[pid] = rp.parse_references(text)
        else:
            ref_by_paper[pid] = {}

    # ---- 2 output rows ----
    normalized_rows = []
    mapping_rows = []

    for m in fam_rows:
        raw = m.get("name", "")
        canonical = strip_author_prefix(raw)
        # If citation_clue has [N] but name still has it, keep in raw only
        core_material = extract_first_token(
            (canonical + " " + m.get("evidence_text_resolved", "")),
            CORE_MATERIAL_TOKENS)
        core_process = extract_first_token(
            (canonical + " " + m.get("evidence_text_resolved", "")),
            CORE_PROCESS_TOKENS)
        target_problem = extract_first_token(
            (canonical + " " + m.get("evidence_text_resolved", "")),
            TARGET_PROBLEM_TOKENS)
        application = extract_first_token(
            (canonical + " " + m.get("evidence_text_resolved", "")),
            APPLICATION_TOKENS)

        pid = m["paper_id"]
        kind = m.get("kind", "")
        clue = m.get("citation_clue", "") or ""

        # Year resolution priority
        year, year_source, author_str, ref_txt = None, "unresolved", "", ""
        if kind == "own":
            y, s = py_by_paper.get(pid, (None, "unresolved"))
            year, year_source = y, s
            source_status = ("in_corpus_primary"
                                if y else "unresolved")
            source_ref_num = ""
        else:
            # citation_clue → author+year → ref number
            y, s, refnum = rp.parse_citation_clue_for_year(
                clue, canonical)
            # spec 三: Stage A 已抽 cited_reference_number 字段, 直接用
            if not refnum:
                cited_rn = (m.get("cited_reference_number") or "").strip()
                if cited_rn.isdigit():
                    refnum = int(cited_rn)
            if y:
                year, year_source = y, s
                source_ref_num = refnum or ""
                source_status = "cited_in_corpus"
                a_m = re.match(r"([一-鿿A-Za-z][\S\s]{0,20}?)"
                                    r"(?:等|et\s+al|,)", clue)
                if a_m: author_str = a_m.group(1).strip()
            else:
                # try ref list lookup
                if refnum and refnum in ref_by_paper.get(pid, {}):
                    entry = ref_by_paper[pid][refnum]
                    if entry.get("year"):
                        year = entry["year"]
                        year_source = "reference_list_entry"
                        author_str = entry.get("author", "")
                        ref_txt = entry.get("raw_text", "")[:200]
                        source_status = "cited_in_corpus"
                    else:
                        source_status = "unresolved"
                else:
                    source_status = "unresolved"
                source_ref_num = refnum or ""

        normalized_rows.append({
            "method_id": m["method_id"],
            "raw_method_name": m.get("raw_method_name") or raw,
            "canonical_method_name": canonical,
            "core_process": core_process,
            "core_material": core_material,
            "target_problem": target_problem,
            "application": application,
            "paper_id": pid,
            "kind": kind,
            "author": (m.get("cited_author") or author_str),
            "year": year if year else "",
            "reference_number": (m.get("cited_reference_number")
                                    or source_ref_num or ""),
            "evidence_sentence_ids": m.get("evidence_sentence_ids", ""),
            "year_source": year_source,
            "source_author": author_str,
            "source_reference_text": ref_txt,
            "source_status": source_status,
        })

        mapping_rows.append({
            "method_id": m["method_id"],
            "raw_method_name": raw,
            "canonical_method_name": canonical,
            "prefix_stripped": (raw != canonical),
            "note": ("author/institution prefix stripped"
                       if raw != canonical else ""),
        })

    # Write CSVs
    with open(os.path.join(OUT_DIR, "lineage_methods_normalized.csv"),
                "w", encoding="utf-8-sig", newline="") as f:
        fields = list(normalized_rows[0].keys())
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in normalized_rows: w.writerow(r)

    with open(os.path.join(OUT_DIR, "lineage_name_mapping.csv"),
                "w", encoding="utf-8-sig", newline="") as f:
        fields = ["method_id", "raw_method_name", "canonical_method_name",
                    "prefix_stripped", "note"]
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in mapping_rows: w.writerow(r)

    # Stats
    n_year_ok = sum(1 for r in normalized_rows if r["year"])
    n_own = sum(1 for r in normalized_rows if r["kind"] == "own")
    n_ref = sum(1 for r in normalized_rows if r["kind"] == "referenced")
    src_dist = {}
    for r in normalized_rows:
        src_dist[r["source_status"]] = src_dist.get(r["source_status"], 0) + 1
    print(f"\nnormalized: {len(normalized_rows)} methods "
            f"(own {n_own}, ref {n_ref})")
    print(f"year resolved: {n_year_ok}/{len(normalized_rows)}")
    print(f"source_status dist: {src_dist}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
