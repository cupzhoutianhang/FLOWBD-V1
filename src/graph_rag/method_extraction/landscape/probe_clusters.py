"""
probe_clusters.py — 探查 3 大簇内容 + 噪声子簇

Part 1: 对每个主簇取距质心最近的 top N 方法名
Part 2: 对噪声集合 (cluster=-1) 在 UMAP 2D 上再跑 HDBSCAN(min_size=15)
"""
from __future__ import annotations

import argparse
import os
import pickle
import sys
from collections import Counter

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
COORDS_PKL = os.path.join(THIS_DIR, "coords_v2.pkl")
EMB_PKL = os.path.join(THIS_DIR, "embeddings_v2.pkl")
PROBE_OUT = os.path.join(THIS_DIR, "cluster_probe.md")


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--topn", type=int, default=15)
    ap.add_argument("--sub-min-size", type=int, default=15)
    args = ap.parse_args()

    import numpy as np

    with open(COORDS_PKL, "rb") as f:
        d = pickle.load(f)
    with open(EMB_PKL, "rb") as f:
        e = pickle.load(f)

    kept = d["kept"]
    coords = d["coords_2d"]
    labels = d["cluster_labels"]
    emb = e["embeddings"]

    n = len(kept)
    print(f"加载: {n} 个节点, {emb.shape[1]} 维向量")
    print(f"  cluster_labels 分布: {Counter(labels.tolist())}")

    md_lines = ["# 聚类探查\n\n"]

    # ============ Part 1: 3 大簇 ============
    print("\n" + "=" * 70)
    print("Part 1: 主簇 top-N 代表方法")
    print("=" * 70)
    md_lines.append("## Part 1: 3 大簇内容\n\n")

    for c in sorted(set(labels.tolist())):
        if c == -1:
            continue
        mask = labels == c
        sub_emb = emb[mask]
        # 簇质心 (embedding 空间), L2 normalize 后做 cosine
        centroid = sub_emb.mean(axis=0)
        centroid = centroid / np.linalg.norm(centroid)
        sims = sub_emb @ centroid  # 已 L2 normalize, 点乘 = cosine
        sub_kept = [kept[i] for i in range(n) if mask[i]]
        sorted_idx = np.argsort(-sims)

        title = f"### Cluster {c}  ({mask.sum()} 节点)\n\n"
        print(f"\n{title.strip()}")
        md_lines.append(title)
        md_lines.append(f"距质心最近 top {args.topn}:\n\n")

        # kind 分布
        kinds = Counter(m["kind"] for m in sub_kept)
        years = [m["year"] for m in sub_kept if m.get("year") is not None]
        year_range = f"{min(years)}-{max(years)}" if years else "?"
        md_lines.append(f"- kind: {dict(kinds)}\n")
        md_lines.append(f"- 年份范围: {year_range}\n\n")
        print(f"  kind: {dict(kinds)}  | 年份: {year_range}")

        for rank, idx in enumerate(sorted_idx[: args.topn], 1):
            m = sub_kept[idx]
            line = (f"{rank:>2}. [{m['kind']}] sim={sims[idx]:.3f}  "
                    f"{m['cleaned_name'][:60]}")
            print(f"  {line}")
            md_lines.append(f"{rank}. **{m['cleaned_name'][:80]}**  ({m['kind']}, {m.get('year', '?')})\n")
            md_lines.append(f"   - paper: {m['paper_id']}\n")

    # ============ Part 2: 噪声子聚类 ============
    print("\n" + "=" * 70)
    print(f"Part 2: 噪声子聚类 (min_cluster_size={args.sub_min_size})")
    print("=" * 70)
    md_lines.append("\n## Part 2: 噪声内部子聚类\n\n")

    noise_mask = labels == -1
    noise_coords = coords[noise_mask]
    noise_emb = emb[noise_mask]
    noise_kept = [kept[i] for i in range(n) if noise_mask[i]]
    print(f"\n噪声总数: {noise_mask.sum()}")

    import hdbscan

    sub = hdbscan.HDBSCAN(
        min_cluster_size=args.sub_min_size,
        min_samples=3,
        metric="euclidean",
    )
    sub_labels = sub.fit_predict(noise_coords)
    sub_cnt = Counter(sub_labels.tolist())
    n_sub = sum(1 for k in sub_cnt if k >= 0)
    residual = sub_cnt.get(-1, 0)
    print(f"  -> {n_sub} 个子簇 + {residual} 残余噪声 ({residual/noise_mask.sum()*100:.0f}%)")
    md_lines.append(f"原始噪声 {noise_mask.sum()} 个, "
                    f"用 HDBSCAN(min_size={args.sub_min_size}) 重聚成 **{n_sub} 个子簇**, "
                    f"残余 {residual} 个真噪声.\n\n")

    md_lines.append("各子簇 top 10:\n\n")
    for sc in sorted(set(sub_labels.tolist())):
        if sc == -1:
            continue
        sub_mask = sub_labels == sc
        sub_sub_emb = noise_emb[sub_mask]
        sub_centroid = sub_sub_emb.mean(axis=0)
        sub_centroid /= np.linalg.norm(sub_centroid)
        sub_sims = sub_sub_emb @ sub_centroid
        sub_members = [noise_kept[i] for i in range(len(noise_kept)) if sub_mask[i]]
        sorted_idx = np.argsort(-sub_sims)

        title = f"\n### Sub-cluster {sc}  ({sub_mask.sum()} 节点)\n\n"
        print(f"\n--- Sub-cluster {sc}  ({sub_mask.sum()} 节点) ---")
        md_lines.append(title)
        for rank, idx in enumerate(sorted_idx[:10], 1):
            m = sub_members[idx]
            print(f"  {rank:>2}. {m['cleaned_name'][:55]}  | {m['paper_id'][:30]}")
            md_lines.append(f"{rank}. **{m['cleaned_name'][:80]}**  ({m['kind']})\n")
            md_lines.append(f"   - paper: {m['paper_id']}\n")

    with open(PROBE_OUT, "w", encoding="utf-8") as f:
        f.writelines(md_lines)
    print(f"\n[done] markdown 报告: {PROBE_OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
