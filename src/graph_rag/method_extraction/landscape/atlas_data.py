"""
atlas_data.py — 版图计算层 (landmark / 凸包晕染 / 精选边), 供 matplotlib 和 Streamlit 共用

compute_atlas(include_peripheral=False) -> dict:
  nodes, edges, clusters        (同 landscape_api)
  landmark_ids   : set[str]
  hulls          : {cluster_id: [[x,y],...]}   凸包顶点 (已离群裁剪)
  centroids      : {cluster_id: [mx,my]}        簇标签位置 (中位数)
  precision_keys : set[(source,target,relation)] 精选边
"""
from __future__ import annotations

import os
import sys
from collections import defaultdict

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if THIS_DIR not in sys.path:
    sys.path.insert(0, THIS_DIR)

from landscape_api import get_method_landscape, CLUSTER_COLORS
from atlas_render import select_landmarks  # 复用 v2 权重 + 排除逻辑


def _cluster_landmark_k(size: int) -> int:
    return 3 if size < 60 else (5 if size > 150 else 4)


def compute_atlas(include_peripheral: bool = False) -> dict:
    import numpy as np

    data = get_method_landscape(include_peripheral=include_peripheral)
    nodes = data["nodes"]
    edges = data["edges"]
    clusters = data["clusters"]

    id2node = {n["id"]: n for n in nodes}
    cluster_of = {n["id"]: (n["cluster_id"] if n["cluster_id"] is not None else -1)
                  for n in nodes}

    # 入度
    indeg = defaultdict(int)
    for e in edges:
        indeg[e["target"]] += 1

    # 按簇分组 (仅真簇)
    by_cluster = defaultdict(list)
    for n in nodes:
        cid = cluster_of[n["id"]]
        if cid >= 0:
            by_cluster[cid].append(n)

    # landmark
    landmark_ids = set()
    for cid, cnodes in by_cluster.items():
        k = _cluster_landmark_k(len(cnodes))
        for nd, _, _ in select_landmarks(cnodes, indeg)[:k]:
            landmark_ids.add(nd["id"])

    # 凸包 (离群裁剪 88 分位)
    hulls = {}
    centroids = {}
    try:
        from scipy.spatial import ConvexHull
        for cid, cnodes in by_cluster.items():
            pts = np.array([[n["x"], n["y"]] for n in cnodes])
            centroids[cid] = [float(np.median(pts[:, 0])), float(np.median(pts[:, 1]))]
            if len(pts) < 3:
                continue
            c = np.median(pts, axis=0)
            dist = np.linalg.norm(pts - c, axis=1)
            keep = pts[dist <= np.percentile(dist, 88)]
            if len(keep) < 3:
                keep = pts
            try:
                hull = ConvexHull(keep)
                hulls[cid] = [[float(keep[v, 0]), float(keep[v, 1])] for v in hull.vertices]
            except Exception:
                pass
    except ImportError:
        for cid, cnodes in by_cluster.items():
            pts = np.array([[n["x"], n["y"]] for n in cnodes])
            centroids[cid] = [float(np.median(pts[:, 0])), float(np.median(pts[:, 1]))]

    # 精选边: (high ∩ cross ∩ both_real) ∪ (high ∩ touch_lm)
    def is_high(e):
        return e["confidence"] == "high"
    def cross(e):
        return cluster_of.get(e["source"], -9) != cluster_of.get(e["target"], -9)
    def both_real(e):
        return cluster_of.get(e["source"], -9) >= 0 and cluster_of.get(e["target"], -9) >= 0
    def touch_lm(e):
        return e["source"] in landmark_ids or e["target"] in landmark_ids

    precision_keys = set()
    for e in edges:
        if (is_high(e) and cross(e) and both_real(e)) or (is_high(e) and touch_lm(e)):
            precision_keys.add((e["source"], e["target"], e["relation"]))

    return {
        "nodes": nodes,
        "edges": edges,
        "clusters": clusters,
        "id2node": id2node,
        "cluster_of": cluster_of,
        "landmark_ids": landmark_ids,
        "hulls": hulls,
        "centroids": centroids,
        "precision_keys": precision_keys,
        "cluster_colors": CLUSTER_COLORS,
    }


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    a = compute_atlas()
    print(f"nodes={len(a['nodes'])} edges={len(a['edges'])} "
          f"landmarks={len(a['landmark_ids'])} hulls={len(a['hulls'])} "
          f"precision_edges={len(a['precision_keys'])}")
    for cid, c in a["clusters"].items():
        h = len(a["hulls"].get(cid, []))
        print(f"  C{cid} {c['label']}: size={c['size']} hull_pts={h} centroid={a['centroids'].get(cid)}")
