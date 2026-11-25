"""
atlas_render.py — Intern-Atlas 风格静态渲染 (纯渲染层, 不动 UMAP/聚类/数据)

4 个改动:
  1. 簇标签浮在簇中心 (节点坐标中位数), 半透明白底描边, cluster_label 文字
  2. 自动选 landmark (每簇 3-5 个): 综合 入度 / 早年份 / innovation 长度
  3. 边减法: (high) ∩ (跨簇 ∪ 沾 landmark), 目标 200-300 条
  4. 簇半透明背景晕 (凸包, alpha 0.18), noise/peripheral 不画

输出:
  - atlas_preview.png       草图
  - landmarks_preview.csv   landmark 列表供人工审
"""
from __future__ import annotations

import csv
import os
import sys
from collections import defaultdict

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if THIS_DIR not in sys.path:
    sys.path.insert(0, THIS_DIR)

PNG = os.path.join(THIS_DIR, "atlas_preview_v2.png")
LM_CSV = os.path.join(THIS_DIR, "landmarks_v2_preview.csv")

# 下标/上标 Unicode -> ASCII (matplotlib 字体 Microsoft YaHei 缺这些字形会出 □)
_SUBSUP_TRANS = {}
for _i in range(10):
    _SUBSUP_TRANS[0x2080 + _i] = str(_i)   # ₀-₉
_SUBSUP_TRANS[0x2093] = "x"                # ₓ
_SUBSUP_TRANS[0x208B] = "-"                # ₋
for _code, _ch in [(0x2070, "0"), (0x00B9, "1"), (0x00B2, "2"), (0x00B3, "3"),
                   (0x2074, "4"), (0x2075, "5"), (0x2076, "6"), (0x2077, "7"),
                   (0x2078, "8"), (0x2079, "9"), (0x207A, "+"), (0x207B, "-")]:
    _SUBSUP_TRANS[_code] = _ch


def norm_sub(s: str) -> str:
    """下标/上标 Unicode 转普通字符, 避免 matplotlib 字体缺字形出 □."""
    return (s or "").translate(_SUBSUP_TRANS)


# 强制踢出 landmark 的串味节点 (按 name 子串匹配)
LANDMARK_EXCLUDE_SUBSTR = [
    "聚碳酸酯注塑制品",       # C2 退火工艺, 非相变
    "石墨板并行",             # C2 流场设计, 串味
    "齿形元件分散纳米CaCO",   # C7 聚合物混炼, 串味
    "FF 二肽六氟异丙醇",      # C8 多肽纳米管, 串味
    "Telkes 1940",            # C3 跨界相变
]


def _excluded(name: str) -> bool:
    return any(sub in name for sub in LANDMARK_EXCLUDE_SUBSTR)


def select_landmarks(cluster_nodes, indeg):
    """对一个簇的节点列表选 landmark.
    v2 权重: 0.65*入度norm + 0.25*早年份norm + 0.10*innovation长度norm.
    强制排除 LANDMARK_EXCLUDE_SUBSTR 命中的节点.
    返回按分排序的节点列表 (已剔除被排除项)."""
    import numpy as np

    if not cluster_nodes:
        return []
    indegs = np.array([indeg.get(n["id"], 0) for n in cluster_nodes], dtype=float)
    years = np.array([n["year"] if n["year"] else 9999 for n in cluster_nodes], dtype=float)
    inno_len = np.array([len(n["innovation"] or "") for n in cluster_nodes], dtype=float)

    def norm(a, invert=False):
        rng = a.max() - a.min()
        if rng == 0:
            return np.zeros_like(a)
        v = (a - a.min()) / rng
        return 1 - v if invert else v

    score = 0.65 * norm(indegs) + 0.25 * norm(years, invert=True) + 0.10 * norm(inno_len)
    order = np.argsort(-score)
    out = []
    for i in order:
        if _excluded(cluster_nodes[i]["name"]):
            continue  # 强制排除
        out.append((cluster_nodes[i], float(score[i]), int(indegs[i])))
    return out


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    from landscape_api import get_method_landscape, CLUSTER_COLORS
    import numpy as np

    print("[1/6] 拉数据 (排除 peripheral)...")
    data = get_method_landscape(include_peripheral=False)
    nodes = data["nodes"]
    edges = data["edges"]
    clusters = data["clusters"]
    id2node = {n["id"]: n for n in nodes}
    cluster_of = {n["id"]: (n["cluster_id"] if n["cluster_id"] is not None else -1) for n in nodes}
    print(f"      {len(nodes)} 节点, {len(edges)} 边, {len(clusters)} 簇")

    print("[2/6] 算入度...")
    indeg = defaultdict(int)
    for e in edges:
        indeg[e["target"]] += 1

    print("[3/6] 每簇选 landmark...")
    # 簇大小决定 landmark 数: <60 -> 3, >150 -> 5, 否则 4
    by_cluster = defaultdict(list)
    for n in nodes:
        cid = cluster_of[n["id"]]
        if cid >= 0:
            by_cluster[cid].append(n)

    landmark_ids = set()
    landmark_rows = []
    for cid in sorted(by_cluster.keys()):
        cnodes = by_cluster[cid]
        size = len(cnodes)
        k = 3 if size < 60 else (5 if size > 150 else 4)
        ranked = select_landmarks(cnodes, indeg)[:k]
        for nd, score, ind in ranked:
            landmark_ids.add(nd["id"])
            # 选它的理由
            reasons = []
            if ind > 0:
                reasons.append(f"入度{ind}")
            if nd["year"]:
                reasons.append(f"年份{nd['year']}")
            if nd["innovation"]:
                reasons.append(f"innovation {len(nd['innovation'])}字")
            landmark_rows.append({
                "cluster_id": cid,
                "cluster_label": clusters[cid]["label"],
                "method_name": nd["name"],
                "year": nd["year"] or "",
                "in_degree": ind,
                "score": round(score, 3),
                "reason": " / ".join(reasons),
                "paper_id": nd["paper_id"],
            })
    print(f"      选出 {len(landmark_ids)} 个 landmark")

    # landmarks_preview.csv
    with open(LM_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[
            "cluster_id", "cluster_label", "method_name", "year",
            "in_degree", "score", "reason", "paper_id",
        ])
        w.writeheader()
        w.writerows(landmark_rows)
    print(f"      landmarks_preview.csv -> {LM_CSV}")

    print("[4/6] 边减法...")
    def is_high(e):
        return e["confidence"] == "high"
    def cross(e):
        return cluster_of.get(e["source"], -9) != cluster_of.get(e["target"], -9)
    def touch_lm(e):
        return e["source"] in landmark_ids or e["target"] in landmark_ids

    def both_real(e):
        return cluster_of.get(e["source"], -9) >= 0 and cluster_of.get(e["target"], -9) >= 0

    n_high = sum(1 for e in edges if is_high(e))
    n_cross_real = sum(1 for e in edges if cross(e) and both_real(e))
    n_lm = sum(1 for e in edges if touch_lm(e))
    # 精选集: 真大陆桥(高置信跨簇,两端真簇) ∪ 沾landmark的高置信边
    #   数据现实: 真跨簇边只有 ~46 条 (大部分跨簇另一端是噪声)
    visible = [e for e in edges
               if (is_high(e) and cross(e) and both_real(e)) or (is_high(e) and touch_lm(e))]
    print(f"      high={n_high}  真大陆桥(cross∩both_real)={n_cross_real}  touch_lm={n_lm}")
    print(f"      精选可见边 = {len(visible)}")

    print("[5/6] 渲染 PNG...")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon
    from scipy.spatial import ConvexHull
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

    EDGE_COLORS = {"EXTENDS": "#f58231", "IMPROVES": "#4363d8",
                   "ADAPTS": "#3cb44b", "REPLACES": "#e6194B"}

    fig, ax = plt.subplots(figsize=(17, 13), dpi=120)
    ax.set_facecolor("#fafafa")

    # --- 4. 簇背景晕 (凸包, 离群裁剪) ---
    for cid, cnodes in by_cluster.items():
        pts = np.array([[n["x"], n["y"]] for n in cnodes])
        if len(pts) < 3:
            continue
        # 裁掉离质心最远的 12% 防止气球
        c = np.median(pts, axis=0)
        dist = np.linalg.norm(pts - c, axis=1)
        keep = pts[dist <= np.percentile(dist, 88)]
        if len(keep) < 3:
            keep = pts
        try:
            hull = ConvexHull(keep)
            poly = keep[hull.vertices]
            ax.add_patch(Polygon(poly, closed=True,
                                 facecolor=CLUSTER_COLORS.get(cid, "#ccc"),
                                 alpha=0.16, edgecolor=CLUSTER_COLORS.get(cid, "#ccc"),
                                 linewidth=1.2, zorder=1))
        except Exception:
            pass

    # --- noise ---
    noise = [n for n in nodes if cluster_of[n["id"]] < 0]
    if noise:
        nx = [n["x"] for n in noise]; ny = [n["y"] for n in noise]
        ax.scatter(nx, ny, c="#cfcfcf", s=5, alpha=0.25, zorder=2)

    # --- 边 ---
    for e in visible:
        s = id2node.get(e["source"]); t = id2node.get(e["target"])
        if not s or not t:
            continue
        ax.annotate("", xy=(t["x"], t["y"]), xytext=(s["x"], s["y"]),
                    arrowprops=dict(arrowstyle="-|>", color=EDGE_COLORS.get(e["relation"], "#999"),
                                    alpha=0.4, lw=0.8, shrinkA=2, shrinkB=2),
                    zorder=3)

    # --- 簇节点 ---
    for cid, cnodes in by_cluster.items():
        cx = [n["x"] for n in cnodes]; cy = [n["y"] for n in cnodes]
        ax.scatter(cx, cy, c=CLUSTER_COLORS.get(cid, "#999"), s=16, alpha=0.75,
                   edgecolors="white", linewidths=0.3, zorder=4)

    # --- landmark 节点放大 + 黑框白字标签 (贪心防叠 + 引导线) ---
    # 先画所有 landmark 星标
    lm_nodes = []
    for row in landmark_rows:
        nd = id2node.get(f"{row['paper_id']}::{row['method_name']}")
        if nd:
            lm_nodes.append(nd)
            ax.scatter([nd["x"]], [nd["y"]], c="black", s=55, marker="*",
                       edgecolors="white", linewidths=0.6, zorder=6)

    # 贪心放置标签: 优先往"远离全局中心"方向外推, 避开已放置标签框
    placed = []  # (x, y) 已放置标签中心
    LBL_W, LBL_H = 1.7, 0.5  # 标签框估计尺寸 (放大一点更不容易叠)
    g_center = np.array([np.median([n["x"] for n in nodes]),
                         np.median([n["y"] for n in nodes])])

    def place_label(nx, ny):
        base = np.array([nx, ny])
        outward = base - g_center
        nrm = np.linalg.norm(outward)
        base_ang = np.arctan2(outward[1], outward[0]) if nrm > 1e-6 else 0.0
        # 先试外推方向(偏移角从小到大), radius 递增
        for radius in (0.4, 0.7, 1.05, 1.45, 1.9, 2.4, 3.0):
            for dang in (0, 25, -25, 50, -50, 80, -80, 115, -115, 150, -150, 180):
                ang = base_ang + np.radians(dang)
                pos = base + radius * np.array([np.cos(ang), np.sin(ang)])
                ok = all(
                    (abs(pos[0] - px) > LBL_W or abs(pos[1] - py) > LBL_H)
                    for px, py in placed
                )
                if ok:
                    placed.append((pos[0], pos[1]))
                    return pos
        placed.append((base[0] + 0.4, base[1] + 0.4))
        return base + 0.4

    for nd in lm_nodes:
        raw = norm_sub(nd["name"])  # 下标转 ASCII 防 □
        label = raw[:18] + ("…" if len(raw) > 18 else "")
        lx, ly = place_label(nd["x"], nd["y"])
        ax.plot([lx, nd["x"]], [ly, nd["y"]], color="#333", lw=0.4, alpha=0.5, zorder=6)
        ax.annotate(
            label, (lx, ly),
            ha="center", va="center",
            fontsize=6.5, color="white", fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.25", facecolor="black", alpha=0.82,
                      edgecolor="none"),
            zorder=7,
        )

    # --- 1. 簇标签浮中心 ---
    for cid, cnodes in by_cluster.items():
        mx = np.median([n["x"] for n in cnodes])
        my = np.median([n["y"] for n in cnodes])
        ax.annotate(
            norm_sub(clusters[cid]["label"]),
            (mx, my), ha="center", va="center",
            fontsize=15, fontweight="bold", color="#222",
            bbox=dict(boxstyle="round,pad=0.4", facecolor="white", alpha=0.7,
                      edgecolor=CLUSTER_COLORS.get(cid, "#888"), linewidth=2),
            zorder=8,
        )

    # 图例 (边色)
    from matplotlib.lines import Line2D
    legend_el = [Line2D([0], [0], color=c, lw=2, label=r)
                 for r, c in EDGE_COLORS.items()]
    legend_el.append(Line2D([0], [0], marker="*", color="w", markerfacecolor="black",
                            markersize=12, label="landmark"))
    ax.legend(handles=legend_el, loc="lower right", fontsize=9, framealpha=0.9)

    ax.set_title(f"储能方法演化版图 (Atlas 风格草图) | {len(nodes)} 节点 "
                 f"{len(by_cluster)} 大陆 · 可见边 {len(visible)} · landmark {len(landmark_ids)}",
                 fontsize=14, fontweight="bold")
    ax.set_xlabel("UMAP-1"); ax.set_ylabel("UMAP-2")
    plt.tight_layout()
    plt.savefig(PNG, bbox_inches="tight")
    plt.close()
    print(f"      {PNG}")

    print("[6/6] done.")
    print(f"\n可见边构成: 目标 200-300, 实际 {len(visible)}")
    print(f"landmark 数: {len(landmark_ids)} (9 簇)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
