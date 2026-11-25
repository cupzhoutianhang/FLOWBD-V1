"""lineage_lookup.py — spec 八 系统功能入口 (方法谱系 CLI).

用户输入方法名或关键词, 系统返回:
  - 相关方法列表 (canonical_method_name)
  - 最早可追溯来源
  - 时间线 (按年份排序)
  - confirmed + candidate 关系
  - 原文证据
  - 数据范围提示 (spec 边界)

**MVP scope**: 只查询当前选中的 MVP 家族 (相变材料渗漏/最佳含量测定/定形封装).
若关键词不匹配家族, 提示不支持并说明扩展需要单独开发.

命令:
  python -m src.graph_rag.method_evolution_v2.lineage_lookup <keyword>
  # 或
  python -m src.graph_rag.method_evolution_v2.lineage_lookup --help
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_GRAPH_RAG_DIR = os.path.dirname(THIS_DIR)
if SRC_GRAPH_RAG_DIR not in sys.path:
    sys.path.insert(0, SRC_GRAPH_RAG_DIR)

from method_evolution_v2 import config                              # noqa: E402
from method_evolution_v2.stage_a import full_runner as fr           # noqa: E402


LINEAGE_DIR = os.path.join(config.PAPER_V2_DIR, "article_minimal_results",
                              "lineage_mvp")


BOUNDARY_NOTE = (
    "数据边界提示:\n"
    "  * 结果仅基于本研究 337 篇既有储能相关中文文献 + 可解析引用范围\n"
    "  * 不追溯外部原始文献, 不声称'全球首次提出'\n"
    "  * 无年份的方法不进入时间线判定\n"
    "  * candidate 关系是候选提示, 不进入正式关系统计\n"
    "  * 本 MVP 只接入 1 个方法家族: 相变材料渗漏/最佳含量测定/定形封装\n"
    "  * 其他方法家族的谱系查询需单独开发 (spec 九: 系统不再扩展)"
)


def _parse_sids(s):
    try: return json.loads(s) if s else []
    except Exception: return []


def load_all():
    with open(os.path.join(LINEAGE_DIR, "lineage_methods_normalized.csv"),
                "r", encoding="utf-8-sig") as f:
        methods = list(csv.DictReader(f))
    with open(os.path.join(LINEAGE_DIR, "lineage_edges_confirmed.csv"),
                "r", encoding="utf-8-sig") as f:
        confirmed = list(csv.DictReader(f))
    with open(os.path.join(LINEAGE_DIR, "lineage_edges_candidate.csv"),
                "r", encoding="utf-8-sig") as f:
        candidate = list(csv.DictReader(f))
    with open(os.path.join(LINEAGE_DIR, "lineage_earliest_source.json"),
                "r", encoding="utf-8") as f:
        earliest = json.load(f)
    with open(os.path.join(LINEAGE_DIR, "lineage_selected_family.json"),
                "r", encoding="utf-8") as f:
        sel = json.load(f)
    return methods, confirmed, candidate, earliest, sel


def keyword_matches(method, kws):
    """Case-insensitive substring match against multiple method fields."""
    fields = [
        method.get("canonical_method_name", ""),
        method.get("raw_method_name", ""),
        method.get("core_material", ""),
        method.get("core_process", ""),
        method.get("target_problem", ""),
        method.get("application", ""),
        method.get("author", ""),
    ]
    hay = " ".join(fields).lower()
    hits = sum(1 for kw in kws if kw.lower() in hay)
    return hits


def load_sentence_texts_for(paper_id):
    d = fr.per_paper_dir(paper_id)
    p = os.path.join(d, "sentence_index.json")
    if not os.path.isfile(p): return {}
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {s["sentence_id"]: s.get("sentence_text", "")
             for s in data.get("sentences", [])}


def lookup(keyword: str, top_n: int = 15):
    methods, confirmed, candidate, earliest, sel = load_all()
    kws = [k.strip() for k in keyword.split() if k.strip()]
    if not kws:
        return {"error": "empty keyword"}

    matches = []
    for m in methods:
        h = keyword_matches(m, kws)
        if h > 0:
            matches.append((h, m))
    matches.sort(key=lambda x: -x[0])
    matched = [m for _, m in matches[:top_n]]

    # Timeline: dated matches sorted by year
    def _y(m):
        try: return int(m.get("year", "") or 0)
        except ValueError: return 0
    timeline = sorted([m for m in matched if _y(m) > 0], key=_y)

    # Related confirmed & candidate edges (any endpoint in matched)
    matched_ids = {m["method_id"] for m in matched}
    matched_confirmed = [e for e in confirmed
                            if e.get("from_method_id") in matched_ids
                            or e.get("to_method_id") in matched_ids]
    matched_candidate = [e for e in candidate
                            if e.get("from_method_id") in matched_ids
                            or e.get("to_method_id") in matched_ids]

    return {
        "family_name": sel["selected_family_name"],
        "family_id": sel["selected_family_id"],
        "keyword": keyword,
        "n_matched": len(matched),
        "matched_methods": matched,
        "timeline": timeline,
        "earliest_family_source": earliest,
        "matched_confirmed_edges": matched_confirmed,
        "matched_candidate_edges": matched_candidate,
    }


def render_report(res):
    lines = []
    lines.append("=" * 70)
    lines.append(f"方法谱系查询 (MVP)")
    lines.append(f"  keyword: {res['keyword']}")
    lines.append(f"  MVP family: {res['family_name']} "
                    f"({res['family_id']})")
    lines.append(f"  matched methods: {res['n_matched']}")
    lines.append("=" * 70)
    if res["n_matched"] == 0:
        lines.append("\n[未在本 MVP 家族里找到匹配方法]")
        lines.append(f"\n{BOUNDARY_NOTE}\n")
        return "\n".join(lines)

    lines.append("\n[相关方法列表]")
    for m in res["matched_methods"]:
        yr = m.get("year", "?") or "未知"
        auth = m.get("author") or "(无)"
        lines.append(f"  - [{m.get('kind','?')}, {yr}] "
                        f"{m.get('canonical_method_name','')[:70]}")
        lines.append(f"      author={auth}, "
                        f"target={m.get('target_problem','')}, "
                        f"process={m.get('core_process','')}, "
                        f"material={m.get('core_material','')}, "
                        f"paper={m.get('paper_id','')[:35]}")

    lines.append(f"\n[MVP 家族最早可追溯来源]")
    e = res["earliest_family_source"]
    lines.append(f"  {e.get('canonical_note','')}")
    lines.append(f"  method: {e.get('earliest_traceable_method','')}")
    lines.append(f"  author: {e.get('earliest_traceable_author','')}")
    lines.append(f"  year:   {e.get('earliest_traceable_year','')}")
    lines.append(f"  year_source: {e.get('year_source','')}")
    lines.append(f"  边界: {e.get('limitation_note','')}")

    lines.append(f"\n[时间线 (按年份排序, {len(res['timeline'])} 条有年份的匹配方法)]")
    for m in res["timeline"]:
        lines.append(f"  {m['year']:>4}  {m.get('kind','?'):<10} "
                        f"{m.get('canonical_method_name','')[:60]}")

    lines.append(f"\n[Confirmed 关系 ({len(res['matched_confirmed_edges'])} 条)]")
    for e in res["matched_confirmed_edges"]:
        lines.append(f"  * {e.get('relation','?')}: "
                        f"{e.get('from_method_name','?')[:40]} → "
                        f"{e.get('to_method_name','?')[:40]}")
        sids = _parse_sids(e.get("relation_evidence_sentence_ids", ""))
        if sids:
            lines.append(f"    evidence sids: {sids}")

    lines.append(f"\n[Candidate 关系 ({len(res['matched_candidate_edges'])} 条, 虚线, 不进入正式统计)]")
    for e in res["matched_candidate_edges"]:
        lines.append(f"  ~ {e.get('from_method_name','')[:35]} "
                        f"({e.get('from_year','?')}) → "
                        f"{e.get('to_method_name','')[:35]} "
                        f"({e.get('to_year','?')}) "
                        f"[{e.get('similarity_hint','')}]")

    # Show original evidence for the earliest (or first matched) method
    lines.append("\n[原文证据示例]")
    src = res["matched_methods"][0]
    sids = _parse_sids(src.get("evidence_sentence_ids", ""))
    if sids:
        sent_map = load_sentence_texts_for(src["paper_id"])
        for sid in sids[:3]:
            t = sent_map.get(sid, "")
            if t:
                lines.append(f"  [{sid}] 「{t[:250]}」")

    lines.append(f"\n{BOUNDARY_NOTE}\n")
    return "\n".join(lines)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError): pass

    p = argparse.ArgumentParser(
        description="方法谱系查询 (MVP: 相变材料渗漏/最佳含量测定/定形封装)")
    p.add_argument("keyword", nargs="+",
                    help="方法名或关键词 (可多个空格分隔)")
    p.add_argument("--top", type=int, default=15,
                    help="返回匹配方法数 (default 15)")
    p.add_argument("--json", action="store_true",
                    help="以 JSON 形式输出 (给上游程序用)")
    args = p.parse_args()
    kw = " ".join(args.keyword)
    res = lookup(kw, top_n=args.top)
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        print(render_report(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
