"""Read-only lexical supplement over existing parsed papers; no vector index writes."""
from __future__ import annotations

from functools import lru_cache
import json
import collections
from pathlib import Path
import re

BASE = Path(__file__).resolve().parents[2] / "paper/method_evolution_v2"
ALIASES = {"ostwald": "奥氏熟化", "奥氏熟化": "Ostwald", "渗出圈": "扩散-渗出圈",
           "dhaq": "蒽醌", "eg": "膨胀石墨", "高温熔融": "纳米熔盐"}


def norm(text):
    return re.sub(r"[^\w\u4e00-\u9fff]", "", str(text).lower())


@lru_cache(maxsize=1)
def paragraphs():
    rows = []
    for path in (BASE / "corpus_preprocess_v1_1/sections").glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        title = data.get("document_title") or data["paper_id"]
        for section in data.get("sections", []):
            if section.get("section_type") in {"references", "title"}:
                continue
            for p in section.get("paragraphs", []):
                text = p.get("text", "")
                if len(text.strip()) < 20:
                    continue
                rows.append({"source": title, "doc_id": data["paper_id"],
                             "parent_id": p["para_id"], "content": text,
                             "location": f"{path.name}:{p['para_id']}",
                             "corpus_version": "corpus_preprocess_v1_1",
                             "section_type": section.get("section_type", ""),
                             "_norm": norm(text), "_title": norm(title)})
    return rows


def _search_corpus_legacy(question, entities=(), limit=6):
    q = norm(question)
    terms = [norm(e) for e in entities if len(norm(e)) >= 3]
    for key, value in ALIASES.items():
        if (re.search(r"(?<![a-z])" + re.escape(key) + r"(?![a-z])", question.lower())
                if key.isascii() else norm(key) in q):
            terms.extend([norm(key), norm(value)])
    grams = {q[i:i + 3] for i in range(len(q) - 2)}
    method_question = any(w in question for w in ("制备", "合成", "工艺", "参数", "温度", "时间"))
    scored = []
    for p in paragraphs():
        text = p["_norm"]
        hits = sum(g in text for g in grams)
        exact = sum(min(len(t), 15) for t in terms if t in text)
        title_hits = sum(g in p["_title"] for g in grams)
        score = hits + exact * 2 + title_hits
        if hits < 5 and not exact:
            continue
        if method_question and p["section_type"] == "methods":
            score *= 3
        scored.append((score, p))
    scored.sort(key=lambda v: v[0], reverse=True)
    picked = []
    per_paper = {}
    for score, p in scored:
        if per_paper.get(p["doc_id"], 0) >= 3:
            continue
        per_paper[p["doc_id"]] = per_paper.get(p["doc_id"], 0) + 1
        picked.append({k: v for k, v in p.items() if not k.startswith("_")})
        picked[-1]["retrieval_channel"] = "local_lexical"
        picked[-1]["lexical_score"] = score
        picked[-1]["rerank_score"] = 0  # lexical scores are not calibrated reranker logits
        if len(picked) >= limit:
            break
    # A procedural paragraph often defers durations to the immediately next paragraph.
    # Preserve that real neighbor rather than concluding the parameter is absent.
    if method_question and picked and picked[0].get("section_type") == "methods":
        best = picked[0]
        rows = paragraphs()
        index = next((i for i, row in enumerate(rows) if row["doc_id"] == best["doc_id"] and
                      row["parent_id"] == best["parent_id"]), -1)
        if index >= 0 and index + 1 < len(rows):
            neighbor = rows[index + 1]
            prefix = best["parent_id"].rsplit("_p", 1)[0]
            if (neighbor["doc_id"] == best["doc_id"] and neighbor["section_type"] == "methods" and
                    neighbor["parent_id"].rsplit("_p", 1)[0] == prefix and
                    not any(r["parent_id"] == neighbor["parent_id"] and r["doc_id"] == neighbor["doc_id"] for r in picked)):
                picked.append({k: v for k, v in neighbor.items() if not k.startswith("_")})
                picked[-1].update({"retrieval_channel": "section_neighbor", "lexical_score": 0, "rerank_score": 0})
    return picked


def title_filtered_recall(collection, question, limit=6):
    """Read-only fallback when multilingual semantic recall loses a named battery scope."""
    if not collection or not any(term in question.lower() for term in ("铁铬", "iron-chromium", "iron chromium", "icfb")):
        return []
    fields = {f.name for f in collection.schema.fields}
    required = {"id", "block_type", "original_filename", "content", "doc_id"}
    if not required.issubset(fields):
        return []
    rows = collection.query(expr='block_type == "parent" and original_filename like "%chromium%"',
                            output_fields=sorted(required), limit=256, timeout=15)
    terms = ["iron", "chromium"]
    if "析氢" in question or "hydrogen" in question.lower():
        terms += ["hydrogen evolution", "her", "suppress", "inhibit"]
    scored = []
    for row in rows:
        title = row["original_filename"].lower()
        if "iron" not in title or "chromium" not in title:
            continue
        content = row["content"].lower()
        score = sum(12 * title.count(t) + content.count(t) for t in terms if t != "her")
        score += len(re.findall(r"\bher\b", content))
        scored.append((score, row))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    result, per_paper = [], {}
    for score, row in scored:
        doc = row["doc_id"]
        if per_paper.get(doc, 0) >= 2:
            continue
        per_paper[doc] = per_paper.get(doc, 0) + 1
        result.append({"source": row["original_filename"], "doc_id": doc, "parent_id": row["id"],
                       "content": row["content"], "corpus_version": collection.name,
                       "location": f"{collection.name}:parent_id={row['id']}",
                       "retrieval_channel": "milvus_title_scope", "lexical_score": score, "rerank_score": 0})
        if len(result) >= limit:
            break
    return result


@lru_cache(maxsize=1)
def audited_lineage():
    """Only the human-corrected final table; machine-accepted intermediates are excluded."""
    import csv
    path = BASE / "article_minimal_results/final_case/final_storage_case_edges.csv"
    with path.open(encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    return rows


@lru_cache(maxsize=1)
def sentence_evidence():
    index = {}
    for path in (BASE / "stage_a_full_v1/per_paper").glob("*/sentence_index.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        for sentence in data.get("sentences", []):
            index[(data["paper_id"], sentence["sentence_id"])] = sentence["sentence_text"]
    return index


@lru_cache(maxsize=1)
def confirmed_lineage():
    import csv
    path = BASE / "article_minimal_results/lineage_mvp/lineage_edges_confirmed_v2.csv"
    with path.open(encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def lineage_sources(question):
    from .lineage_answer import lineage_requested
    if not lineage_requested(question):
        return []
    sources = []
    for row in audited_lineage():
        if "扩散" in question and "之外" not in question and "扩散" not in row["from_method_name"] + row["to_method_name"]:
            continue
        sid_list = row["relation_evidence_sentence_ids"]
        original_sentences = [
            f"{sid}：{sentence_evidence().get((row['paper_id'], sid), '原句未能定位；只允许引用审计记录')}"
            for sid in json.loads(sid_list)]
        content = (f"关系记录 {row['edge_id']}；状态 accepted（人工规则校正的案例，不自动称 confirmed）。\n"
                   f"类型 {row['relation']}；数据方向：{row['from_method_name']} → {row['to_method_name']}。\n"
                   f"证据位置 {sid_list}；方向依据：{row['direction_basis']}。\n"
                   f"边界：{row['data_boundary']}。")
        content += "\n原文逐句证据：\n" + "\n".join(original_sentences)
        matching_confirmed = []
        for confirmed in confirmed_lineage():
            if (confirmed["paper_id"] == row["paper_id"] and
                    confirmed["relation"] == row["relation"] and
                    json.loads(confirmed["relation_evidence_sentence_ids"]) == json.loads(sid_list)):
                matching_confirmed.append(confirmed)
                content += (f"\n同一证据另有 {confirmed['edge_id']} 正式 confirmed 文件记录；"
                            f"校验状态 {confirmed['validation_status']}；不重复计数。"
                            f"数据方向 {confirmed['data_edge_direction']}，图示方向 {confirmed['visualization_direction']}。"
                            "来自 article_minimal_results/lineage_mvp/lineage_edges_confirmed_v2.csv。")
        sources.append({"source": "审计记录：" + row["paper_id"], "doc_id": "AUDIT:" + row["edge_id"],
                        "parent_id": row["edge_id"], "content": content,
                        "location": "article_minimal_results/final_case/final_storage_case_edges.csv:" + row["edge_id"],
                        "corpus_version": "stage_b_human_corrected", "type": "lineage",
                        "audit_record": {"edge": dict(row), "confirmed_records": matching_confirmed,
                                         "original_sentences": original_sentences}})
    # State explicitly what authoritative lookup found, without pretending corpus-wide absence.
    sources.append({"source": "FlowBD 人工校正谱系查询范围说明", "doc_id": "AUDIT:SCOPE",
                    "parent_id": "scope", "type": "lineage", "corpus_version": "stage_b_human_corrected",
                    "location": "article_minimal_results/final_case/final_storage_case_edges.csv",
                    "content": "本次只读查询范围是人工校正后的五条案例及其中ADAPTS对应的正式confirmed记录。"
                               "未命中的关系只能说本次权威查询未记录；不得把legacy相似度边当演化证据。"})
    return sources


def _search_scoped_corpus(question, entities=(), limit=6):
    q = norm(question)
    groups = [{norm(e)} for e in entities if len(norm(e)) >= 2]
    for topic, synonyms in {'钙基': ('钙基材料',), '蒽醌': ('anthraquinone', 'DHAQ')}.items():
        if topic in q:
            matches=[g for g in groups if any(topic in t for t in g)]
            if not matches:
                groups.append({topic});matches=[groups[-1]]
            for g in matches:
                g.update([topic]+[norm(s) for s in synonyms])
    synonyms = {'膨胀石墨': ('expanded graphite', 'EG'),
                '高熵氧化物': ('high entropy oxide', 'HEO', 'HEOs')}
    acronyms = {'eg': 'EG', 'heo': 'HEO', 'heos': 'HEOs'}
    for group in groups:
        for key, values in synonyms.items():
            if norm(key) in group:
                group.update(norm(v) for v in values)
    expanded = list(q[i:i+3] for i in range(len(q)-2))
    for key, value in ALIASES.items():
        if norm(key) in q:
            expanded.append(norm(value))
    concepts = ['构型熵', '自由能'] if '高熵稳定' in q else []

    def contains(p, term):
        if term in acronyms:
            return bool(re.search(r'(?<![A-Za-z])' + re.escape(acronyms[term]) + r'(?![A-Za-z])', p['content']))
        return term in p['_norm'] + p['_title']

    docs = collections.defaultdict(list)
    for p in paragraphs():
        docs[p['doc_id']].append(p)
    coverage = {doc: sum(any(contains(p, t) for p in ps for t in group)
                         for group in groups) for doc, ps in docs.items()}
    method_question = any(w in question for w in ('制备', '合成', '工艺', '参数', '温度', '时间'))
    ranked = []
    for p in paragraphs():
        hits = sum(g in p['_norm'] for g in expanded)
        exact = sum(any(contains(p, t) for t in group) for group in groups)
        concept_hits = sum(t in p['_norm'] for t in concepts)
        if hits < 5 and not exact and not (concept_hits and coverage[p['doc_id']]):
            continue
        actions = sum(w in p['content'] for w in ('称取', '加热', '搅拌', '滴加', '冷却', '洗涤', '干燥', '煅烧'))
        procedural = actions >= 2 and any(w in p['content'] for w in ('制备', '制得', '得到'))
        score = hits + exact * 12 + sum(g in p['_title'] for g in expanded) + concept_hits * 18
        if method_question and (p['section_type'] == 'methods' or procedural):
            score *= 3
        topic_hits = sum(any(contains(p,norm(t)) for t in terms)
                         for topic,terms in {'钙基':('钙基',), '蒽醌':('蒽醌','anthraquinone','DHAQ')}.items()
                         if topic in q)
        intent_hits = sum(t in p['_norm'] for t in ('降解','反应','制备','合成','循环','储热','放热') if t in q)
        ranked.append((topic_hits, intent_hits, coverage[p['doc_id']], score, p))
    ranked.sort(key=lambda v: v[:4], reverse=True)
    result = []
    per = collections.Counter()
    for _, _, cov, score, p in ranked:
        if per[p['doc_id']] >= 3:
            continue
        per[p['doc_id']] += 1
        result.append((cov, score, p))
        if len(result) == limit:
            break
    # A parsing error can place successive experimental subsections under `other_sections`.
    # Supply two real adjacent paragraphs for selected procedural anchors, never inferred text.
    if method_question:
        extras = []
        rows = paragraphs()
        selected = {(p['doc_id'], p['parent_id']) for _, _, p in result}
        for cov, score, p in result:
            actions = sum(w in p['content'] for w in ('称取', '加热', '搅拌', '滴加', '冷却', '洗涤', '干燥', '煅烧'))
            if actions < 2 or not any(w in p['content'] for w in ('制备', '制得', '得到')):
                continue
            pos = rows.index(p)
            for neighbor in rows[pos+1:pos+3]:
                key = (neighbor['doc_id'], neighbor['parent_id'])
                if neighbor['doc_id'] != p['doc_id'] or key in selected:
                    continue
                neighbor_actions = sum(w in neighbor['content'] for w in ('称取', '加热', '搅拌', '滴加', '冷却', '洗涤', '干燥', '煅烧'))
                if neighbor_actions < 2 or not any(w in neighbor['content'] for w in ('制备', '制得', '得到')):
                    continue
                selected.add(key)
                extras.append((cov, 0, neighbor))
            if extras:
                break
        result += extras
        # An abstract can supply a reported formulation omitted from procedural prose.
        if result:
            best_doc=result[0][2]['doc_id']
            abstracts=[p for p in docs[best_doc] if p['section_type']=='abstract' and
                       (p['doc_id'],p['parent_id']) not in selected]
            if abstracts:
                result.append((coverage[best_doc],0,abstracts[0]))
    return result


def search_corpus(question, entities=(), limit=6):
    """Preserve legacy recall except compound procedural scopes and entropy queries.

    Document term coverage and real operation verbs compensate for incorrect section
    classification. Added neighboring paragraphs are exact existing source text.
    """
    method_question = any(w in question for w in ('制备', '合成', '工艺', '参数', '温度', '时间'))
    compound_scope = method_question and len(entities) >= 2 and any(w in question for w in ('/', '／', '复合'))
    if not compound_scope and not any(t in norm(question) for t in ('高熵稳定','钙基')):
        return _search_corpus_legacy(question, entities, limit)
    ranked = _search_scoped_corpus(question, entities, limit)
    results = []
    for coverage, score, p in ranked:
        row = {k: v for k, v in p.items() if not k.startswith('_')}
        channel = 'local_compound_scope' if score else 'document_abstract' if p['section_type']=='abstract' else 'section_neighbor'
        row.update(retrieval_channel=channel,
                   lexical_score=score, document_term_coverage=coverage, rerank_score=0)
        results.append(row)
    return results
