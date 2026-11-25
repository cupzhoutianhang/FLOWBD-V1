"""
write_neo4j_final.py — 阶段 B 最终写库 (clear + 重建 :ProposedMethod 命名空间)

输入:
  - landscape/final_state.pkl       (1713 keep + 87 peripheral 的 coords/labels)
  - landscape/coords_v2.pkl         (老 v80 噪声 - 用于 Part 2 sub-cluster 重算)
  - method_outputs/*.json           (原始 evolution_edges)

操作 (不动老图谱! 只动 :ProposedMethod 命名空间):
  1. DETACH DELETE 所有现有 :ProposedMethod 节点
  2. 写入 1800 个新节点 (1713 main + 87 peripheral)
  3. 写入演化边 (两端都在 1800 集合里的才保留)
  4. 验证 + 抽样 3 个节点

节点属性:
  name, original_name, year, innovation, problem_solved,
  paper_id, source_doc,
  umap_x, umap_y,
  cluster_id, cluster_label, peripheral, secondary_topic

边类型 + 属性:
  METHOD_EXTENDS / METHOD_IMPROVES / METHOD_ADAPTS / METHOD_REPLACES
  + evidence, confidence, reason, from_paper
"""
from __future__ import annotations

import json
import os
import pickle
import sys
import time
from collections import Counter

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
ME_DIR = os.path.dirname(THIS_DIR)
METHOD_OUT = os.path.join(ME_DIR, "method_outputs")
FINAL_STATE = os.path.join(THIS_DIR, "final_state.pkl")
COORDS_V2 = os.path.join(THIS_DIR, "coords_v2.pkl")

NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PWD = __import__("os").environ.get("NEO4J_PASSWORD", "")

# 用户最终标签
CLUSTER_LABELS = {
    0: "能源系统集成与优化",
    1: "吸附式化学储热材料",
    2: "石蜡基复合相变材料",
    3: "物理储能(液态空气/CO2储能)",
    4: "潜热储热换热结构设计",
    5: "生物质衍生多孔碳电极",
    6: "金属氧化物/碳基复合电极",
    7: "电化学制备与分离工艺",
    8: "MOF 衍生储能电极材料",
}

# Part 2 sub-cluster -> secondary_topic (供 v_final 噪声节点细化)
# 注: Sub 3/4/8 内容已大多并入主簇, 极少留在噪声; Sub 10/11/14 已删除; Sub 12 是 peripheral
SUB_TOPIC_MAP = {
    0:  "Ni 基电极 (Ni3S2/泡沫镍)",
    1:  "PANI 聚苯胺纳米阵列",
    2:  "相变微胶囊封装",
    3:  "物理储能 CAES/LAES",
    4:  "石蜡复合 PCM",
    5:  "静电纺丝碳纳米纤维",
    6:  "锂电池家族 (锂硫/锂氧/锂离子电容器)",
    7:  "电池管理 BMS / 故障诊断",
    8:  "能源系统集成",
    9:  "离子交换膜 (Nafion/SPEEK)",
    13: "制氢/电解水/电转气",
    15: "多孔碳模板法",
    16: "生物质热解碳化",
}

VALID_REL = {"EXTENDS", "IMPROVES", "ADAPTS", "REPLACES"}
NEO_REL_PREFIX = "METHOD_"


# ============ Part 1: 重算 Part 2 sub-cluster -> 拿到 (paper_id, name) -> sub_id 映射 ============
def build_sub_topic_lookup() -> dict[tuple[str, str], str]:
    """对 v80 噪声 (1021 节点) 重跑 HDBSCAN(min_size=15) -- 同 probe_clusters.py 配置.
    返回 (paper_id, name) -> secondary_topic 字符串."""
    import hdbscan
    import numpy as np

    with open(COORDS_V2, "rb") as f:
        d = pickle.load(f)
    kept = d["kept"]
    coords_v2 = d["coords_2d"]
    labels_v2 = d["cluster_labels"]
    n = len(kept)

    noise_idx = np.where(labels_v2 == -1)[0]
    print(f"  [sub-cluster] v80 噪声: {len(noise_idx)}, 重跑 HDBSCAN(min_size=15)")
    sub = hdbscan.HDBSCAN(min_cluster_size=15, min_samples=3, metric="euclidean")
    sub_labels = sub.fit_predict(coords_v2[noise_idx])

    lookup: dict[tuple[str, str], str] = {}
    for local_idx, gi in enumerate(noise_idx):
        sub_id = int(sub_labels[local_idx])
        topic = SUB_TOPIC_MAP.get(sub_id)
        if topic:
            m = kept[int(gi)]
            lookup[(m["paper_id"], m["name"])] = topic

    print(f"  [sub-cluster] 命中 {len(lookup)} 个节点带 secondary_topic")
    return lookup


# ============ Part 2: 装配节点 + 边 ============
def assemble_nodes_and_edges():
    print("[1/4] 加载 final_state...")
    with open(FINAL_STATE, "rb") as f:
        fs = pickle.load(f)
    keep_kept = fs["keep_kept"]
    peri_kept = fs["peri_kept"]
    coords_keep = fs["coords_keep"]
    coords_peri = fs["coords_peri"]
    labels_keep = fs["labels_keep"]
    n_keep = len(keep_kept)
    n_peri = len(peri_kept)
    print(f"      keep={n_keep}, peripheral={n_peri}")

    print("[2/4] 重算 secondary_topic 查找表...")
    sub_lookup = build_sub_topic_lookup()

    print("[3/4] 装配节点 props...")
    nodes = []
    cluster_size: Counter = Counter()
    secondary_count: Counter = Counter()

    # 1713 主聚类节点
    for i, m in enumerate(keep_kept):
        cid = int(labels_keep[i])
        x, y = float(coords_keep[i, 0]), float(coords_keep[i, 1])
        if cid >= 0:
            secondary = None
        else:
            secondary = sub_lookup.get((m["paper_id"], m["name"]))
            if secondary:
                secondary_count[secondary] += 1
        cluster_size[cid] += 1
        nodes.append({
            "paper_id": m["paper_id"],
            "name": m["name"],
            "original_name": m["name"],  # 原始 LLM 抽出来的名字 (含 "Tang2003" 等前缀)
            "cleaned_name": m["cleaned_name"],
            "year": m.get("year"),
            "kind": m["kind"],
            "innovation": m.get("innovation", ""),
            "problem_solved": m.get("problem", ""),
            "source_doc": m["paper_id"],
            "umap_x": x,
            "umap_y": y,
            "cluster_id": cid,
            "cluster_label": CLUSTER_LABELS.get(cid, "未归类") if cid >= 0 else "未归类",
            "peripheral": False,
            "secondary_topic": secondary or "",
        })

    # 87 peripheral
    for i, m in enumerate(peri_kept):
        x, y = float(coords_peri[i, 0]), float(coords_peri[i, 1])
        nodes.append({
            "paper_id": m["paper_id"],
            "name": m["name"],
            "original_name": m["name"],
            "cleaned_name": m["cleaned_name"],
            "year": m.get("year"),
            "kind": m["kind"],
            "innovation": m.get("innovation", ""),
            "problem_solved": m.get("problem", ""),
            "source_doc": m["paper_id"],
            "umap_x": x,
            "umap_y": y,
            "cluster_id": -2,  # 区别于 noise (-1)
            "cluster_label": "peripheral (超疏水/油水分离)",
            "peripheral": True,
            "secondary_topic": "超疏水涂层/油水分离",
        })
        cluster_size[-2] += 1

    # 有效 (paper_id, name) 集合, 用于 edge 过滤
    valid_keys = {(n["paper_id"], n["name"]) for n in nodes}
    print(f"      装配 {len(nodes)} 节点, valid keys: {len(valid_keys)}")

    print("[4/4] 装配边 (两端都在 valid keys 内才保留)...")
    edges = []
    dropped_dangling = 0
    rel_count: Counter = Counter()
    for fn in sorted(os.listdir(METHOD_OUT)):
        if not fn.endswith(".json"):
            continue
        with open(os.path.join(METHOD_OUT, fn), "r", encoding="utf-8") as f:
            d = json.load(f)
        pid = d.get("paper_id", "")
        for e in d.get("evolution_edges") or []:
            rel = (e.get("relation") or "").upper().strip()
            if rel not in VALID_REL:
                continue
            fm = (e.get("from_method") or "").strip()
            tm = (e.get("to_method") or "").strip()
            if not fm or not tm:
                continue
            if (pid, fm) not in valid_keys or (pid, tm) not in valid_keys:
                dropped_dangling += 1
                continue
            edges.append({
                "from_paper": pid,
                "from_method": fm,
                "to_method": tm,
                "relation": rel,
                "evidence": (e.get("evidence") or "")[:500],
                "confidence": (e.get("confidence") or "").lower(),
                "reason": (e.get("reason") or "")[:500],
            })
            rel_count[rel] += 1
    print(f"      装配 {len(edges)} 条边 (丢弃 {dropped_dangling} 条悬挂边)")
    print(f"      边类型分布: {dict(rel_count)}")

    return nodes, edges, cluster_size, secondary_count


# ============ Part 3: 写 Neo4j ============
CYPHER_CLEAR = "MATCH (n:ProposedMethod) DETACH DELETE n"

CYPHER_MERGE_NODE = """
MERGE (m:ProposedMethod {paper_id: $paper_id, name: $name})
SET m.original_name   = $original_name,
    m.cleaned_name    = $cleaned_name,
    m.year            = $year,
    m.kind            = $kind,
    m.innovation      = $innovation,
    m.problem_solved  = $problem_solved,
    m.source_doc      = $source_doc,
    m.umap_x          = $umap_x,
    m.umap_y          = $umap_y,
    m.cluster_id      = $cluster_id,
    m.cluster_label   = $cluster_label,
    m.peripheral      = $peripheral,
    m.secondary_topic = $secondary_topic
"""

CYPHER_EDGE_TEMPLATE = """
MATCH (src:ProposedMethod {paper_id: $from_paper, name: $from_method})
MATCH (dst:ProposedMethod {paper_id: $from_paper, name: $to_method})
MERGE (src)-[r:%s]->(dst)
SET r.evidence   = $evidence,
    r.confidence = $confidence,
    r.reason     = $reason,
    r.from_paper = $from_paper
"""


def write_to_neo4j(nodes, edges):
    from neo4j import GraphDatabase, basic_auth

    driver = GraphDatabase.driver(NEO4J_URI, auth=basic_auth(NEO4J_USER, NEO4J_PWD))
    try:
        with driver.session() as session:
            session.run("RETURN 1").consume()
            print(f"\n[neo4j] 已连接 {NEO4J_URI}")

            # 1. clear
            t0 = time.time()
            print("[clear] DETACH DELETE :ProposedMethod ...")
            session.run(CYPHER_CLEAR).consume()
            print(f"        用时 {time.time()-t0:.1f}s")

            # 2. nodes
            t0 = time.time()
            print(f"[nodes] 写入 {len(nodes)} 节点 ...")
            for i, n in enumerate(nodes):
                session.run(CYPHER_MERGE_NODE, **n).consume()
                if (i + 1) % 200 == 0:
                    print(f"        ... {i+1}/{len(nodes)}")
            print(f"        全部完成, 用时 {time.time()-t0:.1f}s")

            # 3. edges (按关系类型分组, 用模板化的 cypher)
            t0 = time.time()
            print(f"[edges] 写入 {len(edges)} 边 ...")
            for i, e in enumerate(edges):
                rel_full = f"{NEO_REL_PREFIX}{e['relation']}"
                cypher = CYPHER_EDGE_TEMPLATE % rel_full
                session.run(cypher, **e).consume()
                if (i + 1) % 200 == 0:
                    print(f"        ... {i+1}/{len(edges)}")
            print(f"        全部完成, 用时 {time.time()-t0:.1f}s")

            # 4. 验证 + 抽样
            print("\n[verify] Neo4j 计数:")
            r = session.run("MATCH (m:ProposedMethod) RETURN count(m) AS c").single()
            print(f"  :ProposedMethod 节点: {r['c']}")

            r = session.run(
                "MATCH (m:ProposedMethod) "
                "RETURN m.peripheral AS p, count(m) AS c"
            ).data()
            for row in r:
                print(f"    peripheral={row['p']}: {row['c']}")

            r = session.run(
                "MATCH (m:ProposedMethod) WHERE m.cluster_id >= 0 "
                "RETURN m.cluster_id AS c, m.cluster_label AS lbl, count(m) AS n "
                "ORDER BY c"
            ).data()
            print(f"  各簇大小:")
            for row in r:
                print(f"    C{row['c']} {row['lbl']}: {row['n']}")

            r = session.run(
                "MATCH (m:ProposedMethod) WHERE m.cluster_id = -1 "
                "RETURN count(m) AS c"
            ).single()
            print(f"    cluster_id=-1 (噪声): {r['c']}")
            r = session.run(
                "MATCH (m:ProposedMethod) "
                "WHERE m.cluster_id = -1 AND m.secondary_topic <> '' "
                "RETURN count(m) AS c"
            ).single()
            print(f"      其中含 secondary_topic 的: {r['c']}")

            r = session.run(
                f"MATCH ()-[r:{NEO_REL_PREFIX}EXTENDS|{NEO_REL_PREFIX}IMPROVES|"
                f"{NEO_REL_PREFIX}ADAPTS|{NEO_REL_PREFIX}REPLACES]->() "
                "RETURN type(r) AS t, count(r) AS c ORDER BY c DESC"
            ).data()
            print(f"  边类型:")
            for row in r:
                print(f"    {row['t']}: {row['c']}")

            # 抽样 3 个节点
            print(f"\n[sample] 抽 3 个节点的完整属性 (Cypher 验证):")
            samples = [
                ("MATCH (m:ProposedMethod {cluster_id: 0}) RETURN m LIMIT 1",
                 "簇 0 (能源系统集成与优化)"),
                ("MATCH (m:ProposedMethod {peripheral: true}) RETURN m LIMIT 1",
                 "peripheral (超疏水)"),
                ("MATCH (m:ProposedMethod) WHERE m.cluster_id = -1 AND m.secondary_topic <> '' "
                 "RETURN m LIMIT 1",
                 "噪声 + 含 secondary_topic"),
            ]
            for cy, desc in samples:
                r = session.run(cy).single()
                if r:
                    n = dict(r["m"])
                    print(f"\n  -- {desc} --")
                    for k in ["name", "year", "cluster_id", "cluster_label",
                              "peripheral", "secondary_topic", "umap_x", "umap_y",
                              "paper_id"]:
                        v = n.get(k, "")
                        if isinstance(v, float):
                            v = f"{v:.3f}"
                        if isinstance(v, str) and len(v) > 60:
                            v = v[:60] + "..."
                        print(f"    {k:<18}: {v}")
                else:
                    print(f"\n  -- {desc}: (无匹配)")

    finally:
        driver.close()


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    nodes, edges, cluster_size, secondary_count = assemble_nodes_and_edges()

    print("\n========== 装配汇总 ==========")
    print(f"节点总数: {len(nodes)}")
    print(f"  各簇大小:")
    for cid in sorted(cluster_size.keys()):
        label = CLUSTER_LABELS.get(cid) if cid >= 0 else (
            "peripheral" if cid == -2 else "噪声 (cluster_id=-1)"
        )
        print(f"    {cid:>3}  {label}: {cluster_size[cid]}")
    print(f"  secondary_topic 命中分布:")
    for topic, c in secondary_count.most_common():
        print(f"    {c:>3}  {topic}")
    print(f"边总数: {len(edges)}")

    write_to_neo4j(nodes, edges)
    print("\n[done] 写库完成. 等你确认进 Stage C 前端.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
