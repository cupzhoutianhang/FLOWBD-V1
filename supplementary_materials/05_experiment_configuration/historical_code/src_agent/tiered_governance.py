# -*- coding: utf-8 -*-
"""
tiered_governance.py — 分层治理证据选择器 (附加模块, 不覆盖 corpus_evidence.py)。

与 corpus_evidence.lineage_sources 的区别:
  - lineage_sources 只读 T1 人工校正 5 条边, 且受关键词门控。
  - 本模块按问题词法匹配, 返回**分层**证据 (T1 人工校正 / T2 语料内一次论文 / T3 综述可定位),
    每条都带真实核查状态、来源层级与范围限制标签。
  - T3 记录明确标注"综述可定位、一次文献未独立核验、不得升级 confirmed/S2、不得据此断言直接继承"。
  - 定位状态 (located_primary / located_review_text / struct_only) 取自 evidence_map.csv (自动定位结果),
    struct_only (仅字段未核对原文) 不作为确定事实注入, 仅作"结构化线索(待人工判断)"。

select(question) -> list[dict]:
  每条: {record_id, tier, source_scope, located, relation, direction, from, to,
         content, caveat, scope_note}
"""
import os, csv, json, re
from functools import lru_cache

ROOT = r"D:\个人工作\邀稿\FlowBD系统"
MEV = os.path.join(ROOT, "paper/method_evolution_v2")
LC = os.path.join(MEV, "article_minimal_results/lineage_cases_unified")
FINAL = os.path.join(MEV, "article_minimal_results/final_case/final_storage_case_edges.csv")
CONFIRMED = os.path.join(MEV, "article_minimal_results/lineage_mvp/lineage_edges_confirmed_v2.csv")
EVMAP = os.path.join(ROOT, "outputs/governance_comparison_20261106/evidence_map.csv")
SEMREV = os.path.join(ROOT, "outputs/governance_comparison_20261106/semantic_review_14edges.csv")

REL_KW = ("EXTENDS", "IMPROVES", "ADAPTS", "REPLACES", "谱系", "演化", "借鉴", "继承", "改进", "替代", "扩展")
SUCC_KW = ("在上述", "基础上", "基于此", "受", "启发", "进一步", "后续", "取代", "又提出", "又通过",
           "改进", "功能化", "衍生", "引入", "得到了", "设计并合成", "借鉴")

CAVEAT = {
    "T1_human_corrected": "状态 accepted（人工规则校正案例，不自动称 confirmed/S2）。",
    "T2_in_corpus": "语料内一次论文可核验（in_corpus_verified）。",
    "T3_review_locatable": "来源层级：综述转引可定位、一次文献未独立核验（review_text_locatable）；"
                            "不得升级为 confirmed/S2，不得据此断言直接继承关系；注意单源偏置。",
}


def _norm(s):
    return re.sub(r"\s+", "", (s or "").replace("，", ",").replace("　", " "))


@lru_cache(maxsize=1)
def _semantic_verdict():
    """逐条语义核对结论 (assistant_semantic_review, 非人工核实)。edge_id -> verdict。"""
    m = {}
    if os.path.isfile(SEMREV):
        for r in csv.DictReader(open(SEMREV, encoding="utf-8-sig")):
            m[r["edge_id"]] = r["assistant_verdict"]
    return m


@lru_cache(maxsize=1)
def _located_map():
    """定位层级 (location_tier) by record_id, 取自 evidence_map.csv。"""
    m = {}
    if os.path.isfile(EVMAP):
        for r in csv.DictReader(open(EVMAP, encoding="utf-8-sig")):
            loc = r.get("location_tier") or r.get("classification") or ""
            m[r["record_id"]] = loc
    return m


@lru_cache(maxsize=1)
def _t1_records():
    out = []
    final = list(csv.DictReader(open(FINAL, encoding="utf-8-sig")))
    confirmed = list(csv.DictReader(open(CONFIRMED, encoding="utf-8-sig")))
    for r in final:
        conf = [c for c in confirmed
                if c["paper_id"] == r["paper_id"] and c["relation"] == r["relation"]
                and json.loads(c["relation_evidence_sentence_ids"]) == json.loads(r["relation_evidence_sentence_ids"])]
        out.append({
            "record_id": r["edge_id"], "tier": "T1_human_corrected", "source_scope": "human_rule",
            "relation": r["relation"], "from": r["from_method_name"], "to": r["to_method_name"],
            "direction": r["direction_basis"], "scope_note": r["data_boundary"],
            "evidence_ids": r["relation_evidence_sentence_ids"], "paper_id": r["paper_id"],
            "confirmed": bool(conf), "correction_status": r["correction_status"],
            "evidence_text": r["direction_basis"],
        })
    return out


@lru_cache(maxsize=1)
def _case_records():
    out = []
    for case in ("pcm_stability", "co_co2_hydrogenation", "aorfb_active_materials"):
        for e in csv.DictReader(open(f"{LC}/{case}/edges.csv", encoding="utf-8-sig")):
            if e["relation_class"] != "direct_evolution":
                continue
            out.append({
                "record_id": f"{case}:{e['edge_id']}", "tier": "T3_review_locatable",
                "source_scope": "review_cited_external", "relation": e["relation_type"],
                "from": e["source_name"], "to": e["target_name"],
                "direction": f"source→target ({e['source_name']}→{e['target_name']})",
                "scope_note": "仅本综述转引文本可定位；" + (e.get("notes") or ""),
                "evidence_text": e["evidence_sentence"], "evidence_loc": e["evidence_location"],
                "case": case,
            })
        for n in csv.DictReader(open(f"{LC}/{case}/nodes.csv", encoding="utf-8-sig")):
            if n["main_figure"] != "true":
                continue
            tier = "T2_in_corpus" if n["source_scope"] == "in_corpus_primary" else "T3_review_locatable"
            out.append({
                "record_id": f"{case}:{n['node_id']}", "tier": tier, "source_scope": n["source_scope"],
                "relation": None, "name": n["display_name"], "performance": n.get("key_performance", ""),
                "research_object": n.get("research_object", ""), "year": n.get("year", ""),
                "scope_note": "节点性能/结构字段；" + (n.get("notes") or ""),
                "evidence_text": n.get("evidence_sentence", ""), "case": case,
            })
    return out


def _tokens(name):
    # 抽取记录里可用于匹配的特征词 (方法/材料名的显著子串)
    name = name or ""
    toks = re.findall(r"[A-Za-z0-9,\-@/\.]{3,}|[\u4e00-\u9fa5]{2,}", name)
    return set(t for t in toks if len(t) >= 2)


def select(question, max_records=8):
    """按问题词法匹配, 返回分层证据 (带定位状态与范围标签)。
    - struct_only (仅字段未核对原文) 本轮不作为确定事实注入, 直接跳过。
    - direct_evolution 边若 evidence 无承接语言, 降级为"方案比较/未核实候选", 不以确定关系标签注入。"""
    q = question or ""
    qn = _norm(q)
    want_rel = any(k.upper() in q.upper() or k in q for k in REL_KW)
    loc = _located_map()
    picked = []
    for rec in _t1_records() + _case_records():
        toks = _tokens(rec.get("from", "") + rec.get("to", "") + rec.get("name", ""))
        hit = any(_norm(t) in qn for t in toks if len(t) >= 2)
        if not hit and want_rel and rec.get("relation") and rec["relation"].upper() in q.upper():
            hit = True
        if not hit:
            continue
        cls = loc.get(rec["record_id"], "unknown")
        if cls == "struct_only":
            continue  # 仅字段未核对原文 -> 不注入 (本轮)
        item = dict(rec)
        item["located"] = cls
        item["caveat"] = CAVEAT.get(rec["tier"], "")
        # 承接依据: 以逐条语义核对结论为准 (关键词仅作筛查)。candidate_unconfirmed -> 候选联系, 不作确定关系。
        if rec.get("relation"):
            eid = rec["record_id"].split(":")[-1]
            verdict = _semantic_verdict().get(eid)
            if verdict == "candidate_unconfirmed":
                item["relation_label_status"] = "候选联系，关系性质未确认（自动线索，未经人工确认；原文无成对承接依据）"
            elif verdict in ("paired_confirmed", "paired_confirmed_weak") or rec["tier"] == "T1_human_corrected":
                item["relation_label_status"] = "原文有成对承接依据" + ("（弱，端点按同谱系锚定）" if verdict == "paired_confirmed_weak" else "")
            else:
                ev = rec.get("evidence_text", "") or rec.get("direction", "")
                item["relation_label_status"] = "原文有承接依据" if any(k in ev for k in SUCC_KW) else \
                    "候选联系，关系性质未确认（自动线索，未经人工确认）"
        picked.append(item)
        if len(picked) >= max_records:
            break
    return picked


def to_injection_chunks(records):
    """把分层证据转为注入块 (content 带层级/状态/范围标签)。"""
    chunks = []
    for r in records:
        if r.get("relation"):
            _st = r.get("relation_label_status", "")
            if _st.startswith("候选联系"):
                rel_show = f"候选联系（{r['relation']} 为自动线索，关系性质未确认）"
            else:
                rel_show = r["relation"]
            head = f"【{r['tier']}｜{r.get('located','')}】{rel_show}：{r.get('from','')} → {r.get('to','')}"
            body = f"\n方向依据：{r.get('direction','')}\n适用范围：{r.get('scope_note','')}\n核查状态：{r['caveat']}"
            if r.get("relation_label_status"):
                body += f"\n关系标签依据：{r['relation_label_status']}"
            if r.get("confirmed"):
                body += "\n（同一证据另有正式 confirmed 文件记录，按一条计数，不重复。）"
            if r.get("evidence_text"):
                body += f"\n综述原文片段：{r['evidence_text'][:160]}"
        else:
            head = f"【{r['tier']}｜{r.get('located','')}】方法节点：{r.get('name','')}（{r.get('year','')}）"
            body = f"\n性能/对象：{r.get('performance','') or r.get('research_object','')}\n核查状态：{r['caveat']}"
        chunks.append({"record_id": r["record_id"], "tier": r["tier"], "located": r.get("located"),
                       "content": head + body, "source": "治理记录:" + r["record_id"],
                       "doc_id": "GOV:" + r["record_id"]})
    return chunks


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    for q in sys.argv[1:] or ["扩散-渗出圈法被哪些方法借鉴（ADAPTS）？其方向与适用范围？"]:
        recs = select(q)
        print(f"\nQ: {q}\n  命中 {len(recs)} 条:")
        for c in to_injection_chunks(recs):
            print(f"  - {c['record_id']} [{c['tier']}|{c['located']}]")
