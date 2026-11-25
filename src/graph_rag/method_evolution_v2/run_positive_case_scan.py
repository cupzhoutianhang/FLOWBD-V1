"""run_positive_case_scan.py — local scan of 337 papers for relation-evidence
strong method pairs (spec 一 + 二 + 三, no API).

Emits:
  - relation_sentence_candidates.csv  (all raw matches)
  - positive_case_candidates.csv      (top-10 papers ranked)
  - positive_case_candidates.md       (top-10 detailed review)

Priority (spec 二):
  1. Same-sentence: trigger + 2 methods anchored in the SAME sentence
  2. Adjacent-sentence coreference: trigger sentence + method anchors in ±2 sentences
  3. own↔referenced pairing preferred over ref↔ref
  4. Explicit direction basis
  5. Complete evidence_sentence_ids
  6. Good OCR (paper not flagged by preflight)

Exclude:
  - Trigger only about "domain evolution" (无具名方法)
  - Method enumeration lists
  - Chronological order alone
  - Whole-component pairs (name substring)
  - Alias pairs
  - Different-material-system pairs
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys
from collections import defaultdict, Counter

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_GRAPH_RAG_DIR = os.path.dirname(THIS_DIR)
if SRC_GRAPH_RAG_DIR not in sys.path:
    sys.path.insert(0, SRC_GRAPH_RAG_DIR)

from method_evolution_v2 import config                              # noqa: E402
from method_evolution_v2.stage_a import full_runner as fr           # noqa: E402


OUT_DIR = os.path.join(config.PAPER_V2_DIR, "article_minimal_results",
                          "positive_case_scan")
os.makedirs(OUT_DIR, exist_ok=True)


# ============================================================
# 触发规则 (spec 一: 明确关系句)
# 每项: (regex, category, score, direction_hint)
# ============================================================

STRONG_TRIGGERS = [
    # EXTENDS: "在 A 基础上", "在此基础上", "沿用/延伸", "由 A 发展到 B", "从 A 扩展到 B"
    (re.compile(r"在.{2,25}?基础上"), "EXTENDS", 6, "prev→curr"),
    (re.compile(r"在此基础上"), "EXTENDS", 4, "prev→curr"),
    (re.compile(r"由.{1,15}?发展到"), "EXTENDS", 6, "from→to"),
    (re.compile(r"从.{1,15}?扩展到|从.{1,15}?到"), "EXTENDS", 4, "from→to"),
    (re.compile(r"进一步(引入|增加|优化|拓展|扩展|发展)"), "EXTENDS", 5, "prev→curr"),

    # IMPROVES: "相比 A", "对 A 进行改进", "对 A 改进", "B 优于 A", "相较于 A"
    (re.compile(r"相比[^,。]{0,30}?"), "IMPROVES", 5, "ref→own"),
    (re.compile(r"相较(于)?[^,。]{0,30}?"), "IMPROVES", 5, "ref→own"),
    (re.compile(r"对.{2,25}?进行改进"), "IMPROVES", 6, "ref→own"),
    (re.compile(r"对.{2,20}?改进"), "IMPROVES", 4, "ref→own"),
    (re.compile(r"[优胜]于[^,。]{2,25}"), "IMPROVES", 5, "ref→own"),
    (re.compile(r"较.{2,15}?(提高|改善|提升)"), "IMPROVES", 4, "ref→own"),

    # REPLACES: "替代 A", "取代 A", "用 B 替代 A", "克服 A", "摆脱 A"
    (re.compile(r"用.{1,15}?替代"), "REPLACES", 6, "ref→own"),
    (re.compile(r"取代|替代"), "REPLACES", 4, "ref→own"),
    (re.compile(r"克服.{2,20}?(缺点|不足|问题|局限)"), "REPLACES", 5, "ref→own"),
    (re.compile(r"摆脱|摒弃"), "REPLACES", 4, "ref→own"),

    # ADAPTS: "借鉴 A", "迁移", "参考 A 的", "引入 A 到"
    (re.compile(r"借鉴.{2,25}?(方法|思路|策略|工艺|设计)"), "ADAPTS", 6, "ref→own"),
    (re.compile(r"迁移到|移植"), "ADAPTS", 5, "ref→own"),
    (re.compile(r"参考.{2,20}?(方法|工艺|设计|策略)"), "ADAPTS", 4, "ref→own"),
    (re.compile(r"引入.{2,20}?到"), "ADAPTS", 4, "ref→own"),

    # 传统 A + 本文 B (对比明确 own↔ref)
    (re.compile(r"传统[^,。]{2,30}"), "IMPROVES", 4, "ref→own_with_trad"),
]

# NEGATIVE / WEAK — 命中后额外**减分** (领域整体/连续枚举)
WEAK_PATTERNS = [
    re.compile(r"(领域|技术)[^,。]{0,15}(发展|进步|进展|突破)"),  # 领域整体发展
    re.compile(r"(近年来|近来).{0,15}(进展|突破|发展)"),
    re.compile(r"其中|以下|包括[^,。]{0,20}(方法|工艺|路线)"),  # 枚举语
]

# 自我参照 (增加 own↔ref 判定的信心)
OWN_MARKERS = ("本文", "本研究", "该研究", "我们", "该论文", "作者", "笔者")


def has_own_marker(text):
    return any(m in text for m in OWN_MARKERS)


def is_weak_trigger_only(text, matched_triggers):
    """若命中的全都是弱域进展语, 视为弱证据."""
    if any(rgx.search(text) for rgx in WEAK_PATTERNS):
        # only weak if no method-specific direction
        return True
    return False


def is_name_substring(a, b):
    """判整体-组件: 一个名字是另一个的子串 → 疑似整体/组件, 或 alias."""
    if not a or not b: return False
    a, b = a.strip(), b.strip()
    if a == b: return True
    if len(a) >= 4 and a in b: return True
    if len(b) >= 4 and b in a: return True
    return False


def jaccard_words(a, b):
    """粗略 Jaccard 相似 (按中文 bi-gram)."""
    def _grams(s):
        s = re.sub(r"\s+", "", s)
        return {s[i:i+2] for i in range(len(s) - 1)}
    ga, gb = _grams(a), _grams(b)
    if not ga or not gb: return 0.0
    return len(ga & gb) / len(ga | gb)


# ============================================================
# Loading
# ============================================================

def load_paper_context():
    ptypes, ctitles, tax = {}, {}, {}
    with open(config.CORPUS_PP_V1_1_PAPER_TYPES_CSV, "r",
                encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            ptypes[r["paper_id"]] = r.get("paper_type", "")
    ctp = os.path.join(config.CORPUS_PP_V1_1_DIR, "canonical_titles.csv")
    if os.path.isfile(ctp):
        with open(ctp, "r", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                ctitles[r["paper_id"]] = r.get("canonical_title", "")
    if os.path.isfile(config.CORPUS_PP_V1_1_PAPER_TAXONOMY_CSV):
        with open(config.CORPUS_PP_V1_1_PAPER_TAXONOMY_CSV, "r",
                    encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                tax[r["paper_id"]] = r
    return ptypes, ctitles, tax


def load_per_paper(pid):
    d = fr.per_paper_dir(pid)
    if not os.path.isdir(d):
        return None
    try:
        with open(os.path.join(d, "methods_accepted.json"),
                    "r", encoding="utf-8") as f:
            acc = json.load(f)
        with open(os.path.join(d, "sentence_index.json"),
                    "r", encoding="utf-8") as f:
            sidx_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    sentence_index = {s["sentence_id"]: s for s in sidx_data.get("sentences", [])}
    return acc, sentence_index


# ============================================================
# Core scan per paper
# ============================================================

def scan_paper(pid, ptypes, tax):
    """Return list of candidate pair records for this paper."""
    loaded = load_per_paper(pid)
    if loaded is None: return []
    accepted, sentence_index = loaded
    if not accepted or not sentence_index: return []

    # sid → methods anchored there
    sid_to_methods = defaultdict(list)
    for m in accepted:
        for sid in (m.get("evidence_sentence_ids") or []):
            sid_to_methods[sid].append(m)

    # order sentences by char_start; also para_id list
    sids_ordered = sorted(sentence_index.keys(),
                             key=lambda s: sentence_index[s].get("char_start", 0))
    # sids by paragraph (in order)
    para_sids = defaultdict(list)
    for sid in sids_ordered:
        para = sentence_index[sid].get("para_id", "")
        para_sids[para].append(sid)

    candidates = []
    seen_pairs = set()   # dedupe (paper, min_id, max_id)

    for sid in sids_ordered:
        s = sentence_index[sid]
        text = s.get("sentence_text", "")
        if not text: continue

        # Find trigger hits
        hits = []
        for rgx, category, base_score, dir_hint in STRONG_TRIGGERS:
            for match in rgx.finditer(text):
                hits.append({"category": category,
                               "score_base": base_score,
                               "direction_hint": dir_hint,
                               "trigger": match.group(0)})
        if not hits: continue

        # weak-only check
        weak = is_weak_trigger_only(text, hits)

        # Collect candidate methods in ±2 sentences within same paragraph
        para = s.get("para_id", "")
        this_para_sids = para_sids.get(para, [])
        try:
            idx = this_para_sids.index(sid)
        except ValueError:
            idx = -1
        adjacent = this_para_sids[max(0, idx-2): idx+3] if idx >= 0 else [sid]

        method_ids_nearby = []
        for asid in adjacent:
            for m in sid_to_methods.get(asid, []):
                if m["method_id"] not in method_ids_nearby:
                    method_ids_nearby.append(m["method_id"])

        if len(method_ids_nearby) < 2: continue

        methods_by_id = {m["method_id"]: m for m in accepted}

        for i in range(len(method_ids_nearby)):
            for j in range(i + 1, len(method_ids_nearby)):
                m_a = methods_by_id[method_ids_nearby[i]]
                m_b = methods_by_id[method_ids_nearby[j]]
                key = (pid, min(m_a["method_id"], m_b["method_id"]),
                         max(m_a["method_id"], m_b["method_id"]))
                if key in seen_pairs: continue
                seen_pairs.add(key)

                # exclusions (spec 二)
                if is_name_substring(m_a.get("name",""), m_b.get("name","")):
                    continue    # 整体-组件 或 alias
                jw = jaccard_words(m_a.get("name",""), m_b.get("name",""))
                if jw >= 0.7: continue   # 高相似度视为 alias

                # kind combination priority
                kinds = tuple(sorted([m_a.get("kind","?"), m_b.get("kind","?")]))
                own_ref = kinds == ("own", "referenced")
                ref_ref = kinds == ("referenced", "referenced")
                own_own = kinds == ("own", "own")

                # 是否同句 (best evidence)
                a_sids = set(m_a.get("evidence_sentence_ids") or [])
                b_sids = set(m_b.get("evidence_sentence_ids") or [])
                same_sent = bool(a_sids & b_sids) or (sid in a_sids and sid in b_sids)
                a_in_trigger = sid in a_sids
                b_in_trigger = sid in b_sids
                both_in_trigger = a_in_trigger and b_in_trigger

                # score
                score = 0.0
                score += max(h["score_base"] for h in hits)
                if both_in_trigger: score += 5      # 同句锚定
                elif a_in_trigger or b_in_trigger: score += 2   # 一端在触发句
                if own_ref: score += 3
                elif own_own: score += 2
                elif ref_ref: score += 0
                if has_own_marker(text): score += 1
                if weak: score -= 3
                # 有具体动作/对象/材料信号加分
                if any(kw in text for kw in ("材料", "结构", "工艺", "策略",
                                                "路线", "方法", "技术")):
                    score += 0.5
                # 若纯粹 "领域发展" 语气过强, 已扣分

                candidates.append({
                    "paper_id": pid,
                    "paper_type": ptypes.get(pid, ""),
                    "primary_storage_domain": tax.get(pid, {}).get(
                        "primary_storage_domain", ""),
                    "method_a_id": m_a["method_id"],
                    "method_a_name": m_a.get("name", ""),
                    "method_a_kind": m_a.get("kind", ""),
                    "method_b_id": m_b["method_id"],
                    "method_b_name": m_b.get("name", ""),
                    "method_b_kind": m_b.get("kind", ""),
                    "kind_combo": "-".join(kinds),
                    "relation_type_hint": hits[0]["category"],
                    "relation_trigger": "; ".join(sorted({h["trigger"]
                                                              for h in hits})),
                    "direction_hint": hits[0]["direction_hint"],
                    "evidence_sentence_ids": [sid],
                    "trigger_sentence_text": text,
                    "trigger_sentence_id": sid,
                    "both_methods_in_trigger": both_in_trigger,
                    "one_method_in_trigger": bool(a_in_trigger ^ b_in_trigger),
                    "own_marker_present": has_own_marker(text),
                    "weak_pattern_flag": weak,
                    "name_jaccard": round(jw, 2),
                    "score": round(score, 2),
                })
    return candidates


# ============================================================
# Rank & emit
# ============================================================

def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError): pass

    ptypes, ctitles, tax = load_paper_context()

    # Load 337 paper_ids
    with open(config.STAGE_A_FULL_V1_BATCHES_CSV, "r",
                encoding="utf-8-sig") as f:
        pids = [r["paper_id"] for r in csv.DictReader(f)]

    print(f"scanning {len(pids)} papers for relation-evidence candidates...")
    all_candidates = []
    for i, pid in enumerate(pids, 1):
        if i % 50 == 0:
            print(f"  ... scanned {i}/{len(pids)}")
        all_candidates.extend(scan_paper(pid, ptypes, tax))

    print(f"raw candidates: {len(all_candidates)}")

    # emit raw csv
    if all_candidates:
        fields = list(all_candidates[0].keys())
        with open(os.path.join(OUT_DIR, "relation_sentence_candidates.csv"),
                    "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            for c in all_candidates:
                row = {k: (json.dumps(v, ensure_ascii=False)
                            if isinstance(v, (list, dict)) else v)
                        for k, v in c.items()}
                w.writerow(row)

    # rank per paper: use paper's TOP-score pair as its representative score
    by_paper = defaultdict(list)
    for c in all_candidates:
        by_paper[c["paper_id"]].append(c)

    paper_reports = []
    for pid, cands in by_paper.items():
        # Sort candidates by score desc
        cands_sorted = sorted(cands, key=lambda x: -x["score"])
        # Deduplicate pairs (keep highest-scoring instance)
        seen = set()
        unique = []
        for c in cands_sorted:
            key = (min(c["method_a_id"], c["method_b_id"]),
                   max(c["method_a_id"], c["method_b_id"]))
            if key in seen: continue
            seen.add(key)
            unique.append(c)
        # Paper score = sum of top-3 pair scores + own_ref bonus + research bonus
        top3 = unique[:3]
        paper_score = sum(c["score"] for c in top3)
        own_ref_count = sum(1 for c in unique if c["kind_combo"] == "own-referenced")
        both_in_trig_count = sum(1 for c in unique if c["both_methods_in_trigger"])
        one_in_trig_count = sum(1 for c in unique if c["one_method_in_trigger"])

        # Bonus for research_article (spec 三)
        if ptypes.get(pid) == "research_article":
            paper_score += 3
        # own_ref bonus
        paper_score += own_ref_count * 2
        # both-in-trigger bonus
        paper_score += both_in_trig_count * 3

        paper_reports.append({
            "paper_id": pid,
            "canonical_title": ctitles.get(pid, ""),
            "paper_type": ptypes.get(pid, ""),
            "primary_storage_domain": tax.get(pid, {}).get(
                "primary_storage_domain", ""),
            "n_unique_pairs": len(unique),
            "n_own_referenced_pairs": own_ref_count,
            "n_both_methods_in_trigger": both_in_trig_count,
            "n_one_method_in_trigger": one_in_trig_count,
            "top1_score": unique[0]["score"] if unique else 0,
            "top3_sum_score": round(sum(c["score"] for c in top3), 2),
            "paper_score": round(paper_score, 2),
            "sample_trigger": unique[0]["trigger_sentence_text"][:120]
                if unique else "",
            "sample_pair": f"{unique[0]['method_a_name'][:30]} ↔ "
                           f"{unique[0]['method_b_name'][:30]}" if unique else "",
            "unique_pairs_data": unique,   # for MD detail
        })

    paper_reports.sort(key=lambda r: -r["paper_score"])
    top10 = paper_reports[:10]

    # emit positive_case_candidates.csv
    csv_fields = ["paper_id", "canonical_title", "paper_type",
                    "primary_storage_domain", "n_unique_pairs",
                    "n_own_referenced_pairs", "n_both_methods_in_trigger",
                    "n_one_method_in_trigger",
                    "top1_score", "top3_sum_score", "paper_score",
                    "sample_trigger", "sample_pair"]
    with open(os.path.join(OUT_DIR, "positive_case_candidates.csv"),
                "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=csv_fields, extrasaction="ignore")
        w.writeheader()
        for r in top10: w.writerow(r)

    # emit positive_case_candidates.md
    md = ["# 正面案例候选 (基于关系句证据的本地扫描, 无 API)\n\n"]
    md.append(f"> 扫描 {len(pids)} 篇, 命中 {len(all_candidates)} 对触发候选, "
                f"独立方法对 {sum(r['n_unique_pairs'] for r in paper_reports)}\n")
    md.append(f"> 只保留前 10 名 (按论文总分排序). 无 API 调用.\n\n")

    md.append("## 排名\n\n")
    md.append("| # | paper_id | 类型 | 领域 | 独立对 | own-ref | 同句锚定 | 单端锚定 | top1 分 | 总分 |\n")
    md.append("|:-:|---|---|---|---:|---:|---:|---:|---:|---:|\n")
    for i, r in enumerate(top10, 1):
        md.append(f"| {i} | {r['paper_id'][:32]} "
                    f"| {r['paper_type']} "
                    f"| {r['primary_storage_domain'] or '-'} "
                    f"| {r['n_unique_pairs']} "
                    f"| {r['n_own_referenced_pairs']} "
                    f"| {r['n_both_methods_in_trigger']} "
                    f"| {r['n_one_method_in_trigger']} "
                    f"| {r['top1_score']} "
                    f"| {r['paper_score']} |\n")

    md.append("\n---\n\n## 每候选的详情\n\n")
    for i, r in enumerate(top10, 1):
        md.append(f"### {i}. {r['paper_id']}\n\n")
        md.append(f"- **canonical_title**: {r['canonical_title']}\n")
        md.append(f"- **paper_type**: {r['paper_type']}\n")
        md.append(f"- **primary_storage_domain**: "
                    f"{r['primary_storage_domain']}\n")
        md.append(f"- **独立方法对**: {r['n_unique_pairs']} "
                    f"(其中 own↔ref {r['n_own_referenced_pairs']}, "
                    f"同句锚定 {r['n_both_methods_in_trigger']})\n")
        md.append(f"- **paper_score**: **{r['paper_score']}**\n\n")
        md.append(f"#### 前 5 强关系候选\n\n")
        for j, c in enumerate(r["unique_pairs_data"][:5], 1):
            md.append(f"**{j}. score {c['score']} — "
                        f"{c['relation_type_hint']} ({c['direction_hint']})**\n")
            md.append(f"- method_a ({c['method_a_kind']}): "
                        f"`{c['method_a_name']}`\n")
            md.append(f"- method_b ({c['method_b_kind']}): "
                        f"`{c['method_b_name']}`\n")
            md.append(f"- 触发词: `{c['relation_trigger']}` "
                        f"(both_in_trigger={c['both_methods_in_trigger']}, "
                        f"one_in_trigger={c['one_method_in_trigger']})\n")
            md.append(f"- 触发句 `{c['trigger_sentence_id']}`:\n")
            md.append(f"  > 「{c['trigger_sentence_text'].strip()}」\n\n")
        md.append("\n")

    with open(os.path.join(OUT_DIR, "positive_case_candidates.md"),
                "w", encoding="utf-8") as f:
        f.writelines(md)

    print(f"\nwrote {len(top10)} top papers to positive_case_candidates.csv + .md")
    if top10:
        print(f"top1: {top10[0]['paper_id']} score={top10[0]['paper_score']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
