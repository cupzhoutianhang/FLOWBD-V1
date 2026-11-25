"""
weak_relevance.py — 抽出疑似误抽/弱关联子簇供人工校对

输入  : coords_v2.pkl
逻辑  : 在 v80 噪声 (1021 个) 上跑 sub-HDBSCAN(min_size=15) — 与 probe_clusters.py 一致
        然后定位 Sub 10/11/12/14 (从之前的探查里看到的:
          - Sub 10: 皮胶原/压敏胶 (~16 节点)
          - Sub 11: 杂(实验方法/烧结/数值) (~27 节点)
          - Sub 12: 超疏水/油水分离 (~87 节点)
          - Sub 14: 微流控/液滴 (~37 节点)
        )
输出  : weak_relevance.csv
"""
from __future__ import annotations

import csv
import os
import pickle
import sys
from collections import Counter

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
COORDS_PKL = os.path.join(THIS_DIR, "coords_v2.pkl")
OUT_CSV = os.path.join(THIS_DIR, "weak_relevance.csv")

# 由 probe_clusters.py 已识别的 4 个弱关联子簇 (sub_id 在 noise 重聚后的编号)
WEAK_SUB_IDS = {
    10: ("皮胶原/压敏胶", "完全跟储能无关, 大概率误抽"),
    11: ("实验方法/数值/烧结混杂", "建模 + 表征 + 烧结实验混杂, 非材料/工艺"),
    12: ("超疏水/油水分离涂层", "跟储能弱关联, 主要在膜污染/分离领域"),
    14: ("微流控/液滴", "微流控装置/液滴生成, 是表征/制造工具非储能方法"),
}


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    with open(COORDS_PKL, "rb") as f:
        d = pickle.load(f)
    kept = d["kept"]
    coords = d["coords_2d"]
    labels = d["cluster_labels"]
    n = len(kept)
    print(f"加载 {n} 节点, 当前噪声 {(labels == -1).sum()} 个")

    # 把噪声拎出来再跑一次子聚类 (跟 probe_clusters.py 同参数)
    import hdbscan
    import numpy as np

    noise_idx = np.where(labels == -1)[0]
    noise_coords = coords[noise_idx]
    print(f"对 {len(noise_idx)} 噪声跑 HDBSCAN(min_size=15)...")
    sub = hdbscan.HDBSCAN(min_cluster_size=15, min_samples=3, metric="euclidean")
    sub_labels = sub.fit_predict(noise_coords)
    sub_cnt = Counter(sub_labels.tolist())
    print(f"  -> 子簇 {sum(1 for k in sub_cnt if k>=0)} 个, 残余噪声 {sub_cnt.get(-1, 0)}")
    for sc in sorted(set(sub_labels.tolist())):
        if sc == -1: continue
        marker = "  <-- 弱关联候选" if sc in WEAK_SUB_IDS else ""
        print(f"    sub {sc:>2}: {(sub_labels == sc).sum()} 节点{marker}")

    # 抽出目标子簇
    print(f"\n抽出 {len(WEAK_SUB_IDS)} 个弱关联子簇成员...")
    rows = []
    for sc, (topic, reason) in WEAK_SUB_IDS.items():
        mask = sub_labels == sc
        members_local = noise_idx[mask]  # 回到 kept 的全局索引
        print(f"  Sub {sc} ({topic}): {mask.sum()} 个")
        for gi in members_local:
            m = kept[int(gi)]
            rows.append({
                "sub_id": sc,
                "sub_topic": topic,
                "filter_reason": reason,
                "method_name": m["name"],
                "cleaned_name": m["cleaned_name"],
                "kind": m["kind"],
                "year": m.get("year") or "",
                "source_paper": m["paper_id"],
            })

    # 排序: 按 sub_id 然后 source_paper
    rows.sort(key=lambda r: (r["sub_id"], r["source_paper"]))

    with open(OUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[
            "sub_id", "sub_topic", "filter_reason",
            "method_name", "cleaned_name", "kind", "year", "source_paper",
        ])
        w.writeheader()
        w.writerows(rows)

    print(f"\n[done] 共 {len(rows)} 条 -> {OUT_CSV}")
    # 各 sub 计数
    by_sub = Counter(r["sub_id"] for r in rows)
    for sc, cnt in sorted(by_sub.items()):
        print(f"  Sub {sc} ({WEAK_SUB_IDS[sc][0]}): {cnt}")
    print(f"\n若全部过滤, 节点 1880 -> {1880 - len(rows)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
