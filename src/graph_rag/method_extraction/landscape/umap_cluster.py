"""
umap_cluster.py — UMAP 降 2D + HDBSCAN 聚类 (阶段 B Step 4)

输入  : landscape/embeddings.pkl  (1951 个 1024 维)
输出  : landscape/coords.pkl
        {ids, coords_2d (n,2), cluster_labels (n,)}
        cluster_label = -1 表示噪声 (未聚到任何簇)

参数 (用户原话):
  - UMAP: n_neighbors=15, min_dist=0.1, metric=cosine
  - HDBSCAN: min_cluster_size 是关键, 决定"大陆"粗细

调参指南:
  --min-cluster-size 20  -> 偏少大簇, 干净
  --min-cluster-size 50  -> 只剩 3-5 个大簇
  --min-cluster-size 10  -> 多 10-20 个小簇
"""
from __future__ import annotations

import argparse
import os
import pickle
import sys
import time

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
EMB_PKL = os.path.join(THIS_DIR, "embeddings.pkl")
OUT_PKL = os.path.join(THIS_DIR, "coords.pkl")
PNG = os.path.join(THIS_DIR, "umap_preview.png")


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--n-neighbors", type=int, default=15)
    ap.add_argument("--min-dist", type=float, default=0.1)
    ap.add_argument("--min-cluster-size", type=int, default=20,
                    help="HDBSCAN min_cluster_size, 决定大陆粗细")
    ap.add_argument("--min-samples", type=int, default=5)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--preview", action="store_true",
                    help="存一张 PNG 散点图预览 (需 matplotlib)")
    args = ap.parse_args()

    if not os.path.isfile(EMB_PKL):
        print(f"[ERR] {EMB_PKL} 不存在", file=sys.stderr)
        return 1

    print("[1/4] 加载 embeddings...")
    with open(EMB_PKL, "rb") as f:
        d = pickle.load(f)
    import numpy as np

    emb = d["embeddings"]
    ids = d["ids"]
    kinds = d["kinds"]
    n = len(ids)
    print(f"      {n} 条向量, 维度 {emb.shape[1]}")

    print(f"[2/4] UMAP 降到 2D (n_neighbors={args.n_neighbors}, min_dist={args.min_dist}, metric=cosine)...")
    import umap

    t0 = time.time()
    reducer = umap.UMAP(
        n_neighbors=args.n_neighbors,
        min_dist=args.min_dist,
        n_components=2,
        metric="cosine",
        random_state=args.seed,
        verbose=False,
    )
    coords = reducer.fit_transform(emb)
    print(f"      shape={coords.shape}  用时 {time.time()-t0:.1f}s")
    print(f"      坐标范围: x in [{coords[:,0].min():.2f}, {coords[:,0].max():.2f}], "
          f"y in [{coords[:,1].min():.2f}, {coords[:,1].max():.2f}]")

    print(f"[3/4] HDBSCAN 聚类 (min_cluster_size={args.min_cluster_size}, "
          f"min_samples={args.min_samples})...")
    import hdbscan

    t0 = time.time()
    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=args.min_cluster_size,
        min_samples=args.min_samples,
        metric="euclidean",  # 在 2D 坐标上, 用欧氏距离
    )
    labels = clusterer.fit_predict(coords)
    print(f"      用时 {time.time()-t0:.1f}s")

    from collections import Counter

    cnt = Counter(labels.tolist())
    n_noise = cnt.get(-1, 0)
    n_clusters = sum(1 for k in cnt if k >= 0)
    print(f"      簇数: {n_clusters}  | 噪声节点: {n_noise} ({n_noise/n*100:.1f}%)")
    print(f"      簇大小分布:")
    for label in sorted(cnt.keys()):
        if label == -1:
            continue
        print(f"        cluster {label:>2}: {cnt[label]} 个节点")
    if n_noise:
        print(f"        noise   -1: {n_noise} 个节点")

    print(f"[4/4] 写入 {OUT_PKL}")
    with open(OUT_PKL, "wb") as f:
        pickle.dump(
            {
                "ids": ids,
                "coords_2d": coords,
                "cluster_labels": labels,
                "kinds": kinds,
                "params": {
                    "umap_n_neighbors": args.n_neighbors,
                    "umap_min_dist": args.min_dist,
                    "hdbscan_min_cluster_size": args.min_cluster_size,
                    "hdbscan_min_samples": args.min_samples,
                    "seed": args.seed,
                },
            },
            f,
        )

    if args.preview:
        try:
            print(f"\n[preview] 画 PNG 预览 -> {PNG}")
            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            fig, ax = plt.subplots(figsize=(12, 10), dpi=100)
            # 噪声画灰色, 簇用 colormap
            noise_mask = labels == -1
            ax.scatter(coords[noise_mask, 0], coords[noise_mask, 1],
                       c="lightgray", s=5, alpha=0.3, label="noise")
            non_noise = ~noise_mask
            scat = ax.scatter(coords[non_noise, 0], coords[non_noise, 1],
                              c=labels[non_noise], cmap="tab20", s=15, alpha=0.7)
            ax.set_title(f"UMAP 2D + HDBSCAN (n={n}, clusters={n_clusters}, noise={n_noise})")
            ax.set_xlabel("UMAP-1")
            ax.set_ylabel("UMAP-2")
            plt.colorbar(scat, ax=ax, label="cluster")
            plt.tight_layout()
            plt.savefig(PNG)
            print(f"          已存 {PNG} ({os.path.getsize(PNG)/1024:.0f} KB)")
        except ImportError:
            print(f"          (matplotlib 未装, 跳过预览)")

    print(f"\n[done]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
