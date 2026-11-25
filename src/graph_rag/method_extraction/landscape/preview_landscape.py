"""
preview_landscape.py — 生成两版静态预览 PNG, 供选配色方案

  preview_by_cluster.png : 9 主簇 9 色 + 噪声灰 + peripheral x
  preview_by_year.png    : 节点按 year 紫->黄渐变 + 噪声灰 + peripheral x

两版都标簇中心 cluster_label. (真 ECharts 交互版在 landscape_tab.py)
"""
from __future__ import annotations

import os
import sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PNG_CLUSTER = os.path.join(THIS_DIR, "preview_by_cluster.png")
PNG_YEAR = os.path.join(THIS_DIR, "preview_by_year.png")


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    sys.path.insert(0, THIS_DIR)
    from landscape_api import get_method_landscape, CLUSTER_COLORS

    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

    print("[1/3] 拉数据...")
    data = get_method_landscape(include_peripheral=True)
    nodes = data["nodes"]
    clusters = data["clusters"]
    print(f"      {len(nodes)} 节点")

    xs = np.array([n["x"] for n in nodes])
    ys = np.array([n["y"] for n in nodes])
    cids = np.array([n["cluster_id"] if n["cluster_id"] is not None else -1 for n in nodes])
    peris = np.array([n["peripheral"] for n in nodes])
    years = np.array([n["year"] if n["year"] else -1 for n in nodes])

    main_mask = (cids >= 0) & (~peris)
    noise_mask = (cids < 0) & (~peris)
    peri_mask = peris

    # 簇中心
    centers = {}
    for cid in clusters:
        m = cids == cid
        centers[cid] = (xs[m].mean(), ys[m].mean())

    # ============ 版本 1: 按簇配色 ============
    print("[2/3] 画 preview_by_cluster.png ...")
    fig, ax = plt.subplots(figsize=(15, 11), dpi=120)
    # 噪声
    ax.scatter(xs[noise_mask], ys[noise_mask], c="#cccccc", s=6, alpha=0.3, label="未归类(噪声)", zorder=1)
    # 各簇
    for cid, info in clusters.items():
        m = (cids == cid) & (~peris)
        ax.scatter(xs[m], ys[m], c=info["color"], s=22, alpha=0.85,
                   label=f"C{cid} {info['label']} ({info['size']})", zorder=3,
                   edgecolors="white", linewidths=0.3)
    # peripheral
    ax.scatter(xs[peri_mask], ys[peri_mask], marker="x", c="#555555", s=40,
               alpha=0.7, label=f"peripheral 超疏水 ({peri_mask.sum()})", zorder=4)
    # 簇中心标签
    for cid, (cx, cy) in centers.items():
        ax.annotate(
            f"{cid}",
            (cx, cy), ha="center", va="center", fontsize=13, fontweight="bold",
            color="black",
            bbox=dict(boxstyle="circle,pad=0.3", facecolor="white",
                      edgecolor=clusters[cid]["color"], linewidth=2, alpha=0.95),
            zorder=5,
        )
    ax.set_title("方法演化版图 — 按聚类配色 (9 主簇)", fontsize=15, fontweight="bold")
    ax.set_xlabel("UMAP-1"); ax.set_ylabel("UMAP-2")
    ax.legend(loc="center left", bbox_to_anchor=(1.0, 0.5), fontsize=9, framealpha=0.9)
    plt.tight_layout()
    plt.savefig(PNG_CLUSTER, bbox_inches="tight")
    plt.close()
    print(f"      {PNG_CLUSTER}")

    # ============ 版本 2: 按年份配色 ============
    print("[3/3] 画 preview_by_year.png ...")
    fig, ax = plt.subplots(figsize=(15, 11), dpi=120)
    valid_year = main_mask & (years > 0)
    # 噪声 + 无年份
    ax.scatter(xs[noise_mask], ys[noise_mask], c="#dddddd", s=6, alpha=0.25,
               label="未归类(噪声)", zorder=1)
    # 主簇节点按年份上色 (plasma: 紫->黄)
    sc = ax.scatter(xs[valid_year], ys[valid_year], c=years[valid_year],
                    cmap="plasma", vmin=2008, vmax=2025, s=24, alpha=0.85,
                    zorder=3, edgecolors="white", linewidths=0.3)
    # peripheral
    ax.scatter(xs[peri_mask], ys[peri_mask], marker="x", c="#555555", s=40,
               alpha=0.7, label=f"peripheral ({peri_mask.sum()})", zorder=4)
    # 簇中心标 cluster_label (年份版需要标签辅助看主题)
    for cid, (cx, cy) in centers.items():
        ax.annotate(
            f"{cid}: {clusters[cid]['label']}",
            (cx, cy), ha="center", va="center", fontsize=8.5, fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                      edgecolor="black", alpha=0.85),
            zorder=5,
        )
    cbar = plt.colorbar(sc, ax=ax, label="发表年份", shrink=0.6)
    cbar.set_ticks([2008, 2012, 2016, 2020, 2025])
    ax.set_title("方法演化版图 — 按年份配色 (2008 紫 → 2025 黄)", fontsize=15, fontweight="bold")
    ax.set_xlabel("UMAP-1"); ax.set_ylabel("UMAP-2")
    ax.legend(loc="upper right", fontsize=9, framealpha=0.9)
    plt.tight_layout()
    plt.savefig(PNG_YEAR, bbox_inches="tight")
    plt.close()
    print(f"      {PNG_YEAR}")

    print("\n[done]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
