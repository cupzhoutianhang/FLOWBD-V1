"""
dedup_methods.py — 跨篇方法去重 (阶段 B Step 3)

输入  : landscape/embeddings.pkl
输出  : landscape/dedup_map.json
        每个原始 (paper_id, name) -> canonical_id (int)
        canonical_id 0..K-1, 每个簇取最长 / 最具体的 name 做规范代表

逻辑:
  1. 用 cos 相似度 (embedding 已 normalize, dot product = cosine)
  2. 阈值 THRESH 以上的对, 用并查集合并
  3. 每簇代表 = 簇内最长 name (倾向具体而非简称)

策略:
  - 同 paper_id 内的方法不合并 (LLM 在同一篇 paper 里抽到的不同方法名一般真是不同方法)
  - 不真合并 Neo4j 节点; 只输出映射给 UMAP / API 用
"""
from __future__ import annotations

import argparse
import json
import os
import pickle
import sys
from collections import Counter, defaultdict
from typing import Optional

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
EMB_PKL = os.path.join(THIS_DIR, "embeddings.pkl")
DEDUP_JSON = os.path.join(THIS_DIR, "dedup_map.json")
DEDUP_REPORT = os.path.join(THIS_DIR, "dedup_report.md")


# ---------- 并查集 ----------
class UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]  # 路径压缩
            x = self.parent[x]
        return x

    def union(self, x: int, y: int) -> None:
        rx, ry = self.find(x), self.find(y)
        if rx == ry:
            return
        if self.rank[rx] < self.rank[ry]:
            rx, ry = ry, rx
        self.parent[ry] = rx
        if self.rank[rx] == self.rank[ry]:
            self.rank[rx] += 1


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--threshold", type=float, default=0.92,
                    help="cosine 合并阈值 (默认 0.92)")
    ap.add_argument("--cross-paper-only", action="store_true", default=True,
                    help="只合并跨 paper 的方法 (默认 True)")
    args = ap.parse_args()

    if not os.path.isfile(EMB_PKL):
        print(f"[ERR] {EMB_PKL} 不存在, 先跑 embed_methods.py", file=sys.stderr)
        return 1

    print("[1/5] 加载 embeddings...")
    with open(EMB_PKL, "rb") as f:
        d = pickle.load(f)
    ids: list[tuple[str, str]] = d["ids"]  # (paper_id, name)
    texts: list[str] = d["texts"]
    kinds: list[str] = d["kinds"]
    import numpy as np

    emb: np.ndarray = d["embeddings"]
    n = len(ids)
    print(f"      {n} 条向量, 维度 {emb.shape[1]}")

    print(f"[2/5] 计算 cos 相似度矩阵 ({n}x{n})...")
    # emb 已 L2 normalize, dot = cosine
    sim = emb @ emb.T  # (n, n) float32, ~15 MB
    np.fill_diagonal(sim, -1.0)  # 对角不算

    print(f"[3/5] 阈值 {args.threshold} 以上的对, 并查集合并 (cross_paper_only={args.cross_paper_only})...")
    uf = UnionFind(n)
    # 只看上三角避免重复
    rows, cols = np.where(np.triu(sim, k=1) >= args.threshold)
    pair_count = 0
    skipped_same_paper = 0
    for i, j in zip(rows, cols):
        i, j = int(i), int(j)
        if args.cross_paper_only and ids[i][0] == ids[j][0]:
            skipped_same_paper += 1
            continue
        uf.union(i, j)
        pair_count += 1
    print(f"      合并对: {pair_count}  (同 paper 跳过: {skipped_same_paper})")

    # 簇
    cluster_members: dict[int, list[int]] = defaultdict(list)
    for i in range(n):
        cluster_members[uf.find(i)].append(i)

    print(f"[4/5] 簇统计...")
    n_clusters = len(cluster_members)
    n_merged = n - n_clusters
    sizes = Counter(len(v) for v in cluster_members.values())
    print(f"      去重前: {n}")
    print(f"      去重后: {n_clusters}")
    print(f"      合并掉: {n_merged}  ({n_merged/n*100:.1f}%)")
    print(f"      簇大小分布:")
    for size in sorted(sizes.keys()):
        print(f"        {size} 个成员的簇: {sizes[size]} 个")

    # 选每簇代表: 最长 name
    print(f"[5/5] 选规范名 + 输出...")
    canonical_id_of: dict[int, int] = {}  # 原始 idx -> canonical_id (0..K-1)
    canonical_info: list[dict] = []  # canonical_id -> info
    cid = 0
    for root, members in sorted(cluster_members.items()):
        # 取 name 最长的成员作代表 (一般最具体)
        rep_idx = max(members, key=lambda x: len(ids[x][1]))
        rep_paper, rep_name = ids[rep_idx]
        canonical_info.append({
            "canonical_id": cid,
            "name": rep_name,
            "rep_paper": rep_paper,
            "size": len(members),
            "members": [
                {"paper_id": ids[m][0], "name": ids[m][1], "kind": kinds[m]}
                for m in members
            ],
        })
        for m in members:
            canonical_id_of[m] = cid
        cid += 1

    # dedup_map: (paper_id, name) -> canonical_id
    out_map = [
        {
            "paper_id": ids[i][0],
            "name": ids[i][1],
            "canonical_id": canonical_id_of[i],
        }
        for i in range(n)
    ]
    with open(DEDUP_JSON, "w", encoding="utf-8") as f:
        json.dump(
            {"threshold": args.threshold, "n_input": n, "n_canonical": n_clusters,
             "map": out_map, "canonical_info": canonical_info},
            f, ensure_ascii=False, indent=2,
        )
    print(f"      写入 {DEDUP_JSON} ({os.path.getsize(DEDUP_JSON)/1024:.1f} KB)")

    # 报告: 列前 20 个最大的簇 (说明合并质量)
    big_clusters = sorted(canonical_info, key=lambda x: -x["size"])[:20]
    lines = [f"# 方法去重报告 (threshold={args.threshold})\n"]
    lines.append(f"- 输入 {n} 个原始方法\n")
    lines.append(f"- 去重后 {n_clusters} 个独立方法\n")
    lines.append(f"- 合并 {n_merged} 个 ({n_merged/n*100:.1f}%)\n")
    lines.append(f"\n## 前 20 个最大簇 (人工抽查这些是不是该合并)\n")
    for c in big_clusters:
        if c["size"] < 2:
            continue
        lines.append(f"\n### 簇 #{c['canonical_id']}  ({c['size']} 个成员)\n")
        lines.append(f"**规范名**: {c['name']}\n\n")
        lines.append(f"成员:\n")
        for m in c["members"][:10]:
            lines.append(f"- [{m['kind']}] {m['paper_id'][:30]}: {m['name'][:80]}\n")
        if len(c["members"]) > 10:
            lines.append(f"- ... 还有 {len(c['members'])-10} 个\n")
    with open(DEDUP_REPORT, "w", encoding="utf-8") as f:
        f.writelines(lines)
    print(f"      去重报告 {DEDUP_REPORT}")

    print(f"\n[done]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
