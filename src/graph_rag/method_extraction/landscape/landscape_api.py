"""
landscape_api.py — 方法演化版图数据接口 (阶段 B Step 6 / 供阶段 C 前端调用)

核心函数:
  get_method_landscape(include_peripheral=True, min_confidence=None)
    -> {
         "nodes": [ {id, name, year, cluster_id, cluster_label, secondary_topic,
                     peripheral, x, y, kind, innovation, problem_solved, paper_id}, ... ],
         "edges": [ {source, target, relation, confidence, evidence, reason}, ... ],
         "clusters": { cluster_id: {label, size, color}, ... },
         "meta": {...}
       }

节点 id = f"{paper_id}::{name}" (与 Neo4j 唯一键一致).
坐标直接取 Neo4j 里的 umap_x / umap_y.
"""
from __future__ import annotations

import os
from typing import Any, Optional

NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PWD = os.environ.get("NEO4J_PWD", __import__("os").environ.get("NEO4J_PASSWORD", ""))

# 9 主簇配色 (鲜明区分色, 给前端 cluster 配色版本用)
CLUSTER_COLORS = {
    0: "#e6194B",   # 红 - 能源系统集成
    1: "#3cb44b",   # 绿 - 吸附式化学储热
    2: "#4363d8",   # 蓝 - 石蜡基相变
    3: "#f58231",   # 橙 - 物理储能
    4: "#911eb4",   # 紫 - 潜热储热换热
    5: "#42d4f4",   # 青 - 生物质多孔碳
    6: "#f032e6",   # 品红 - 金属氧化物复合电极
    7: "#bfef45",   # 黄绿 - 电化学制备分离
    8: "#fabed4",   # 粉 - MOF 衍生电极
}
NOISE_COLOR = "#cccccc"       # 噪声 淡灰
PERIPHERAL_COLOR = "#999999"  # peripheral 深灰

REL_TYPES = ["EXTENDS", "IMPROVES", "ADAPTS", "REPLACES"]
NEO_PREFIX = "METHOD_"


def _node_id(paper_id: str, name: str) -> str:
    return f"{paper_id}::{name}"


def get_method_landscape(
    include_peripheral: bool = True,
    min_confidence: Optional[str] = None,
) -> dict[str, Any]:
    """从 Neo4j 拉版图数据.

    Args:
        include_peripheral: 是否包含 peripheral=True 节点
        min_confidence: 'high'|'medium'|'low' 之一; 只保留 >= 该置信度的边
    """
    from neo4j import GraphDatabase, basic_auth

    conf_rank = {"low": 0, "medium": 1, "high": 2}
    min_rank = conf_rank.get(min_confidence, -1) if min_confidence else -1

    driver = GraphDatabase.driver(NEO4J_URI, auth=basic_auth(NEO4J_USER, NEO4J_PWD))
    nodes: list[dict] = []
    edges: list[dict] = []
    cluster_sizes: dict[int, int] = {}
    try:
        with driver.session() as session:
            # ---- 节点 ----
            node_q = "MATCH (m:ProposedMethod) "
            if not include_peripheral:
                node_q += "WHERE m.peripheral = false "
            node_q += (
                "RETURN m.paper_id AS paper_id, m.name AS name, m.year AS year, "
                "m.cluster_id AS cluster_id, m.cluster_label AS cluster_label, "
                "m.secondary_topic AS secondary_topic, m.peripheral AS peripheral, "
                "m.umap_x AS x, m.umap_y AS y, m.kind AS kind, "
                "coalesce(m.innovation,'') AS innovation, "
                "coalesce(m.problem_solved,'') AS problem_solved"
            )
            for r in session.run(node_q):
                cid = r["cluster_id"]
                peripheral = bool(r["peripheral"])
                # 颜色
                if peripheral:
                    color = PERIPHERAL_COLOR
                elif cid is not None and cid >= 0:
                    color = CLUSTER_COLORS.get(cid, NOISE_COLOR)
                else:
                    color = NOISE_COLOR
                nodes.append({
                    "id": _node_id(r["paper_id"], r["name"]),
                    "name": r["name"],
                    "year": r["year"],
                    "cluster_id": cid,
                    "cluster_label": r["cluster_label"],
                    "secondary_topic": r["secondary_topic"] or "",
                    "peripheral": peripheral,
                    "x": r["x"],
                    "y": r["y"],
                    "kind": r["kind"],
                    "innovation": r["innovation"],
                    "problem_solved": r["problem_solved"],
                    "paper_id": r["paper_id"],
                    "cluster_color": color,
                })
                if cid is not None and cid >= 0:
                    cluster_sizes[cid] = cluster_sizes.get(cid, 0) + 1

            valid_ids = {n["id"] for n in nodes}

            # ---- 边 ----
            rel_pattern = "|".join(f"{NEO_PREFIX}{r}" for r in REL_TYPES)
            edge_q = (
                f"MATCH (a:ProposedMethod)-[r:{rel_pattern}]->(b:ProposedMethod) "
                "RETURN a.paper_id AS sp, a.name AS sn, "
                "b.paper_id AS tp, b.name AS tn, "
                "type(r) AS rel, coalesce(r.confidence,'') AS confidence, "
                "coalesce(r.evidence,'') AS evidence, coalesce(r.reason,'') AS reason"
            )
            for r in session.run(edge_q):
                sid = _node_id(r["sp"], r["sn"])
                tid = _node_id(r["tp"], r["tn"])
                if sid not in valid_ids or tid not in valid_ids:
                    continue  # peripheral 被排除时, 关联边也去掉
                conf = r["confidence"]
                if min_rank >= 0 and conf_rank.get(conf, -1) < min_rank:
                    continue
                edges.append({
                    "source": sid,
                    "target": tid,
                    "relation": r["rel"].replace(NEO_PREFIX, ""),
                    "confidence": conf,
                    "evidence": r["evidence"],
                    "reason": r["reason"],
                })
    finally:
        driver.close()

    # cluster 元信息
    from collections import Counter
    label_of: dict[int, str] = {}
    for nd in nodes:
        if nd["cluster_id"] is not None and nd["cluster_id"] >= 0:
            label_of[nd["cluster_id"]] = nd["cluster_label"]
    clusters = {
        cid: {
            "label": label_of.get(cid, "?"),
            "size": cluster_sizes.get(cid, 0),
            "color": CLUSTER_COLORS.get(cid, NOISE_COLOR),
        }
        for cid in sorted(cluster_sizes.keys())
    }

    n_noise = sum(1 for n in nodes if (n["cluster_id"] is None or n["cluster_id"] < 0) and not n["peripheral"])
    n_peri = sum(1 for n in nodes if n["peripheral"])
    return {
        "nodes": nodes,
        "edges": edges,
        "clusters": clusters,
        "meta": {
            "n_nodes": len(nodes),
            "n_edges": len(edges),
            "n_clusters": len(clusters),
            "n_noise": n_noise,
            "n_peripheral": n_peri,
        },
    }


if __name__ == "__main__":
    import json
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    data = get_method_landscape()
    print(json.dumps(data["meta"], ensure_ascii=False, indent=2))
    print("\nclusters:")
    for cid, c in data["clusters"].items():
        print(f"  C{cid} {c['label']}: {c['size']} ({c['color']})")
    print(f"\nnodes 示例:")
    for n in data["nodes"][:2]:
        print(f"  {json.dumps(n, ensure_ascii=False)[:160]}")
    print(f"\nedges 示例:")
    for e in data["edges"][:2]:
        print(f"  {json.dumps(e, ensure_ascii=False)[:160]}")
