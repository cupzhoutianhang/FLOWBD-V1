# -*- coding: utf-8 -*-
"""FlowBD 342篇范围化学实体 只读统计。绝不写库。仅 MATCH ... RETURN。
输出: 342清单 / 逐篇覆盖核对表 / 统计JSON+CSV。不打印凭据。"""
import sys, os, json, csv, re, datetime
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass

ROOT = os.environ.get("FLOWBD_PROJECT_ROOT", os.getcwd())
OUT  = os.path.join(ROOT, "outputs", "KG实体入库核对_20261117")
os.makedirs(OUT, exist_ok=True)
LLM_DIR = os.path.join(ROOT, "src", "graph_rag", "llm_responses")
URI = "bolt://localhost:7687"
CANDS = [(os.environ.get("NEO4J_USER", "neo4j"), os.environ["NEO4J_PASSWORD"])]

CHEM_LABELS = ["Material","Value","Property","Condition","Method","Component",
               "Reaction","Device","Mechanism","FunctionalGroup","Catalyst","Species"]
METHOD_LABELS = ["ProposedMethod","ProposedMethodCandidate"]

def merged_docid(fn):
    if fn.endswith("_improved_merged.json"): return fn[:-len("_improved_merged.json")]
    m=re.match(r"(.+?)_iteration_(\d+)_merged\.json$", fn)
    if m: return m.group(1)
    if fn.endswith("_merged.json"): return fn[:-len("_merged.json")]
    return None

def main():
    # ---- fixed 342 list ----
    base=json.load(open(os.path.join(ROOT,"scratch","import_batch_20261022","baseline_chuneng_docids.json"),encoding="utf-8"))
    new=[l.strip() for l in open(os.path.join(ROOT,"scratch","import_batch_20261022","canonical_docids.txt"),encoding="utf-8") if l.strip()]
    base_ids=list(base.keys())
    FIXED=base_ids+new
    assert len(FIXED)==len(set(FIXED))==342, (len(FIXED),len(set(FIXED)))
    NEWSET=set(new)
    # ---- merged-file (extraction完成) coverage ----
    merged_docids=set()
    if os.path.isdir(LLM_DIR):
        for fn in os.listdir(LLM_DIR):
            did=merged_docid(fn)
            if did: merged_docids.add(did)
    has_merged={p:(p in merged_docids) for p in FIXED}
    # ---- Neo4j live ----
    from neo4j import GraphDatabase, basic_auth
    drv=None
    for u,p in CANDS:
        try:
            d=GraphDatabase.driver(URI,auth=basic_auth(u,p),encrypted=False)
            with d.session() as s: s.run("RETURN 1").single()
            drv=d; break
        except Exception: pass
    if drv is None:
        print("DB_UNREACHABLE"); return
    stats={"query_time":datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
           "db":"Neo4j "+URI,"milvus_collection":"CHUneng","fixed_corpus":342}
    per_src_count={}   # source -> distinct chem-entity node count (sourced by that paper)
    with drv.session() as s:
        # global
        stats["total_nodes"]=s.run("MATCH (n) RETURN count(n) AS c").single()["c"]
        stats["total_rels"]=s.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
        stats["nodes_multi_label"]=s.run("MATCH (n) WHERE size(labels(n))>1 RETURN count(n) AS c").single()["c"]
        # label counts
        labels=[r["label"] for r in s.run("CALL db.labels() YIELD label RETURN label")]
        stats["all_label_counts"]={lb:s.run(f"MATCH (n:`{lb}`) RETURN count(n) AS c").single()["c"] for lb in labels}
        # chemistry entity set = nodes carrying any CHEM label OR generic Entity
        chem_pred="("+" OR ".join(f"n:`{l}`" for l in CHEM_LABELS+["Entity"])+")"
        stats["chem_entities_total_db"]=s.run(f"MATCH (n) WHERE {chem_pred} RETURN count(n) AS c").single()["c"]
        # per-class (12) + Entity, within chemistry
        stats["class_counts"]={l:stats["all_label_counts"].get(l,0) for l in CHEM_LABELS}
        stats["Entity_generic"]=stats["all_label_counts"].get("Entity",0)
        stats["method_nodes"]={l:stats["all_label_counts"].get(l,0) for l in METHOD_LABELS}
        # distinct source_docs
        srcs=[r["src"] for r in s.run("""MATCH (n) WHERE n.source_docs IS NOT NULL
            WITH n, CASE WHEN valueType(n.source_docs) STARTS WITH 'LIST' THEN n.source_docs ELSE [n.source_docs] END AS sd
            UNWIND sd AS x RETURN DISTINCT x AS src""")]
        sset=set(srcs)
        stats["distinct_source_docs_in_db"]=len(sset)
        stats["sources_outside_342"]=sorted(sset-set(FIXED))
        stats["papers_342_with_entities"]=len(sset & set(FIXED))
        stats["papers_342_without_entities"]=sorted(set(FIXED)-sset)
        # 342-range dedup chem entities: distinct chem-entity nodes whose source ∩ 342 != empty
        c342=s.run(f"""MATCH (n) WHERE {chem_pred} AND n.source_docs IS NOT NULL
            WITH n, CASE WHEN valueType(n.source_docs) STARTS WITH 'LIST' THEN n.source_docs ELSE [n.source_docs] END AS sd
            WHERE any(x IN sd WHERE x IN $fixed)
            RETURN count(DISTINCT n) AS c""", fixed=FIXED).single()["c"]
        stats["chem_entities_sourced_in_342_dedup"]=c342
        # per-class within-342
        stats["class_counts_in_342"]={}
        for l in CHEM_LABELS+["Entity"]:
            cc=s.run(f"""MATCH (n:`{l}`) WHERE n.source_docs IS NOT NULL
                WITH n, CASE WHEN valueType(n.source_docs) STARTS WITH 'LIST' THEN n.source_docs ELSE [n.source_docs] END AS sd
                WHERE any(x IN sd WHERE x IN $fixed) RETURN count(DISTINCT n) AS c""",fixed=FIXED).single()["c"]
            stats["class_counts_in_342"][l]=cc
        # relationships among chem entities sourced in 342 (both endpoints chem, non-method)
        rel342=s.run(f"""MATCH (a)-[r]->(b)
            WHERE {chem_pred.replace('n:','a:')} AND {chem_pred.replace('n:','b:')}
              AND NOT type(r) STARTS WITH 'METHOD_'
            RETURN count(r) AS c""").single()["c"]
        stats["rels_among_chem_entities"]=rel342
        stats["rel_types"]={r["t"]:r["c"] for r in s.run("MATCH ()-[r]->() RETURN type(r) AS t, count(r) AS c ORDER BY c DESC")}
        # chapter / paragraph nodes?
        stats["chapter_nodes"]=sum(stats["all_label_counts"].get(l,0) for l in ["Chapter","Section","章节"])
        stats["paragraph_nodes"]=sum(stats["all_label_counts"].get(l,0) for l in ["Paragraph","Sentence","段落","Evidence"])
        # per-paper entity count (sourced)
        for p in FIXED:
            cnt=s.run(f"""MATCH (n) WHERE {chem_pred} AND n.source_docs IS NOT NULL
                WITH n, CASE WHEN valueType(n.source_docs) STARTS WITH 'LIST' THEN n.source_docs ELSE [n.source_docs] END AS sd
                WHERE $p IN sd RETURN count(DISTINCT n) AS c""",p=p).single()["c"]
            per_src_count[p]=cnt
    drv.close()
    # ---- write artifacts ----
    with open(os.path.join(OUT,"fixed_342_corpus.txt"),"w",encoding="utf-8") as f:
        f.write("\n".join(FIXED)+"\n")
    with open(os.path.join(OUT,"stats_342.json"),"w",encoding="utf-8") as f:
        json.dump(stats,f,ensure_ascii=False,indent=2)
    # per-paper coverage CSV
    with open(os.path.join(OUT,"coverage_per_paper.csv"),"w",encoding="utf-8",newline="") as f:
        w=csv.writer(f); w.writerow(["doc_id","is_new_2026-10-23","has_merged_extraction","in_neo4j_entity_source","entity_nodes_sourced_dedup","status"])
        for p in FIXED:
            inn=p in sset
            cnt=per_src_count[p]
            if inn and cnt>0: st="OK"
            elif has_merged[p] and not inn: st="抽取完成未入库?"
            elif not has_merged[p] and not inn: st="未抽取(缺实体)"
            else: st="核对"
            w.writerow([p, p in NEWSET, has_merged[p], inn, cnt, st])
    # class CSV
    with open(os.path.join(OUT,"class_counts_342.csv"),"w",encoding="utf-8",newline="") as f:
        w=csv.writer(f); w.writerow(["label","count_in_342_dedup","count_whole_db"])
        for l in CHEM_LABELS: w.writerow([l,stats["class_counts_in_342"][l],stats["all_label_counts"].get(l,0)])
        w.writerow(["Entity(generic)",stats["class_counts_in_342"]["Entity"],stats["all_label_counts"].get("Entity",0)])
    # console summary
    print(json.dumps({k:stats[k] for k in ["query_time","total_nodes","total_rels","nodes_multi_label",
        "chem_entities_total_db","chem_entities_sourced_in_342_dedup","distinct_source_docs_in_db",
        "papers_342_with_entities","papers_342_without_entities","sources_outside_342",
        "Entity_generic","method_nodes","rels_among_chem_entities","chapter_nodes","paragraph_nodes"]},
        ensure_ascii=False,indent=2))
    print("class_counts_in_342:",json.dumps(stats["class_counts_in_342"],ensure_ascii=False))
    print("ARTIFACTS ->",OUT)

if __name__=="__main__": main()
