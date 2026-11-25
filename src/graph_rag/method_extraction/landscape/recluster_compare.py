"""
recluster_compare.py — 同时跑 min_cluster_size=50 / 40 两版, 出对比 PNG + 报告

输入  : landscape/coords_v2.pkl + landscape/embeddings_v2.pkl
输出  :
  - umap_v50.png (min_size=50)
  - umap_v40.png (min_size=40)
  - cluster_compare_v50.md / cluster_compare_v40.md

每张 PNG 在每个簇中心标主题猜测 (基于关键词字典 + top-N 方法名).
"""
from __future__ import annotations

import json
import os
import pickle
import re
import sys
import time
from collections import Counter, defaultdict

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
COORDS_PKL = os.path.join(THIS_DIR, "coords_v2.pkl")
EMB_PKL = os.path.join(THIS_DIR, "embeddings_v2.pkl")


# ============ 主题关键词字典 (来自 Part 2 分析的真实子方向) ============
# 形式: 主题名 -> 命中关键词列表
# 顺序优先级: 更专门的主题在前
TOPIC_DICT = [
    ("液流电池-离子膜", ["nafion", "spsf", "speek", "全氟磺酸", "磺化聚芳醚", "质子交换膜", "离子交换膜", "离子选择"]),
    ("液流电池-电解液/电极", ["液流", "钒电池", "全钒", "vrfb", "电堆", "流场", "石墨毡", "碳毡"]),
    ("锂硫电池", ["锂硫", "li2s", "硫化锂", "多硫化物", "穿梭"]),
    ("锂氧/锂二氧化碳", ["锂-二氧化碳", "锂二氧化碳", "锂氧", "lioh", "li-co2", "锂空气"]),
    ("固态锂电-硫化物", ["硫化物固态", "硫银锗矿", "lgps", "li6ps5", "li10gep2s12", "固态电解质"]),
    ("锂电池-修复回收", ["退役电池", "修复 lfp", "lfp 回收", "电池回收", "活性物质回收", "正极材料回收"]),
    ("钠离子电池", ["钠离子", "nasicon", "p2-na", "naf", "硬碳钠电", "na3v2"]),
    ("钾离子电池", ["钾离子", "k0.45mn", "k0.48mn", "p3-k"]),
    ("锌离子/锌空气", ["锌离子", "zn²", "锌空气", "zn 沉积", "zn 负极"]),
    ("超电容-PANI", ["pani", "聚苯胺", "聚吡咯", "ppy"]),
    ("超电容-Ni电极", ["ni3s2", "泡沫镍", "nico2o4", "ni-co ldh", "氢氧化镍"]),
    ("超电容-MnO2", ["mno2", "mno₂", "二氧化锰"]),
    ("电极材料-MOF/多孔碳", ["mof", "金属有机框架", "多孔碳", "活化炭", "活性炭", "石墨烯-金属"]),
    ("电极材料-生物质碳", ["生物质", "木质素", "热解碳化", "纤维素衍生", "果壳"]),
    ("电极材料-碳纳米纤维", ["静电纺丝", "碳纳米纤维", "纺丝"]),
    ("电池管理BMS", ["故障诊断", "soc", "短路检测", "电池一致性", "电池管理"]),
    ("能源系统-电-氢", ["电-氢", "电氢", "风光制氢", "电解槽集群", "氢储能"]),
    ("能源系统-储能优化", ["容量优化", "储能调度", "光储", "退役电池配置", "费用优化"]),
    ("制氢-电解水/重整", ["电解水", "甲烷化", "甲烷重整", "co2 还原", "碱性电解", "pem 电解"]),
    ("物理储能-CAES/LAES", ["caes", "压缩空气", "液态空气", "laes", "液氢", "lng 冷能", "超临界 co₂", "超临界co2", "ccpes", "lces"]),
    ("热化学储能-钙基/盐基", ["钙基", "热化学储能", "ca(oh)2", "caco3", "molten salt"]),
    ("相变材料-石蜡", ["石蜡", "膨胀石墨", "共熔", "脂肪酸", "石膏", "硬脂酸", "癸酸", "月桂酸"]),
    ("相变材料-微胶囊", ["微胶囊", "原位聚合", "复凝聚", "壁材"]),
    ("储热系统-换热", ["翅片", "换热器", "管壳式", "热管", "蓄热", "壳管", "螺旋管"]),
    ("微流控/液滴", ["微流控", "pdms", "液滴", "毛细管"]),
    ("超疏水/油水分离", ["超疏水", "超疏油", "油水分离", "疏水涂层"]),
    ("皮胶原/胶粘", ["皮胶原", "压敏胶", "丙烯酸酯"]),
    ("模型/建模", ["数值模型", "数学模型", "关联式", "有限元", "数值模拟"]),
]

CN_WORD_RE = re.compile(r"[一-龥]{2,6}|[A-Za-z][A-Za-z0-9\-]{2,}")


def guess_topic(method_names: list[str]) -> str:
    """对一组方法名按关键词字典投票, 给出主题猜测."""
    text = " ".join(n.lower() for n in method_names)
    scores = []
    for topic, kws in TOPIC_DICT:
        score = sum(text.count(kw) for kw in kws)
        if score > 0:
            scores.append((score, topic))
    if not scores:
        # fallback: 直接从 top 1 中段抽取
        return method_names[0][:14] if method_names else "?"
    scores.sort(reverse=True)
    return scores[0][1]


def run_one(min_cluster_size: int, kept, coords, embeddings, png_path: str, md_path: str) -> dict:
    import hdbscan
    import numpy as np

    n = len(kept)
    print(f"\n========== min_cluster_size={min_cluster_size} ==========")
    t0 = time.time()
    cl = hdbscan.HDBSCAN(
        min_cluster_size=min_cluster_size,
        min_samples=5,
        metric="euclidean",
        cluster_selection_method="leaf",  # 强制叶节点切分, 避免邻近小簇被合成大簇
    )
    labels = cl.fit_predict(coords)
    print(f"  HDBSCAN 用时 {time.time()-t0:.1f}s")

    cnt = Counter(labels.tolist())
    n_noise = cnt.get(-1, 0)
    n_clusters = sum(1 for k in cnt if k >= 0)
    print(f"  簇数 {n_clusters}  | 噪声 {n_noise} ({n_noise/n*100:.1f}%)")

    # 每簇 top-5 + 主题猜测
    cluster_info = {}
    for c in sorted(set(labels.tolist())):
        if c == -1:
            continue
        mask = labels == c
        sub_emb = embeddings[mask]
        centroid = sub_emb.mean(axis=0)
        centroid /= np.linalg.norm(centroid)
        sims = sub_emb @ centroid
        sub_kept = [kept[i] for i in range(n) if mask[i]]
        sorted_idx = np.argsort(-sims)
        top5 = [sub_kept[i] for i in sorted_idx[:5]]
        topic = guess_topic([m["cleaned_name"] for m in top5])
        # 2D 中心点 (用于 PNG 标签位置)
        sub_coords = coords[mask]
        center_2d = sub_coords.mean(axis=0)
        cluster_info[int(c)] = {
            "size": int(mask.sum()),
            "topic": topic,
            "top5": [{"name": m["cleaned_name"], "paper": m["paper_id"]} for m in top5],
            "center_2d": [float(center_2d[0]), float(center_2d[1])],
        }
        print(f"    cluster {c:>2} (n={mask.sum():>3}): {topic}")

    # ---------- PNG ----------
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

    fig, ax = plt.subplots(figsize=(14, 11), dpi=110)
    noise_mask = labels == -1
    ax.scatter(coords[noise_mask, 0], coords[noise_mask, 1],
               c="lightgray", s=4, alpha=0.25, label="noise")
    non_noise = ~noise_mask
    cmap = plt.cm.tab20
    scat = ax.scatter(coords[non_noise, 0], coords[non_noise, 1],
                      c=labels[non_noise], cmap=cmap, s=14, alpha=0.7)
    # 簇中心标签
    for c, info in cluster_info.items():
        cx, cy = info["center_2d"]
        ax.annotate(
            f"{c}: {info['topic']}\n({info['size']})",
            (cx, cy),
            ha="center", va="center",
            fontsize=9, fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                      edgecolor="black", alpha=0.85),
        )
    ax.set_title(
        f"UMAP + HDBSCAN (min_size={min_cluster_size}) | "
        f"n={n} clusters={n_clusters} noise={n_noise} ({n_noise/n*100:.0f}%)"
    )
    ax.set_xlabel("UMAP-1"); ax.set_ylabel("UMAP-2")
    plt.tight_layout()
    plt.savefig(png_path)
    plt.close()
    print(f"  PNG: {png_path}")

    # ---------- MD 报告 ----------
    md = [f"# 聚类报告 (min_cluster_size={min_cluster_size})\n\n"]
    md.append(f"- 总节点 {n}\n")
    md.append(f"- 簇数 {n_clusters}\n")
    md.append(f"- 噪声 {n_noise} ({n_noise/n*100:.1f}%)\n\n")
    md.append("## 各簇详情\n\n")
    for c, info in cluster_info.items():
        md.append(f"### Cluster {c} — **{info['topic']}** ({info['size']} 节点)\n\n")
        md.append("Top 5:\n\n")
        for i, t in enumerate(info["top5"], 1):
            md.append(f"{i}. {t['name']}  *(paper: {t['paper'][:40]})*\n")
        md.append("\n")
    with open(md_path, "w", encoding="utf-8") as f:
        f.writelines(md)
    print(f"  MD: {md_path}")

    return {
        "min_cluster_size": min_cluster_size,
        "n_clusters": n_clusters,
        "n_noise": n_noise,
        "labels": labels,
        "cluster_info": cluster_info,
    }


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    with open(COORDS_PKL, "rb") as f:
        d = pickle.load(f)
    with open(EMB_PKL, "rb") as f:
        e = pickle.load(f)
    kept = d["kept"]
    coords = d["coords_2d"]
    embeddings = e["embeddings"]

    print(f"加载 {len(kept)} 节点, 2D coords shape={coords.shape}")

    r50 = run_one(50, kept, coords, embeddings,
                  os.path.join(THIS_DIR, "umap_v50.png"),
                  os.path.join(THIS_DIR, "cluster_compare_v50.md"))
    r40 = run_one(40, kept, coords, embeddings,
                  os.path.join(THIS_DIR, "umap_v40.png"),
                  os.path.join(THIS_DIR, "cluster_compare_v40.md"))

    # 保存两版 labels 到 pkl, 后续选定 commit 用
    with open(os.path.join(THIS_DIR, "compare_results.pkl"), "wb") as f:
        pickle.dump({"v50": r50, "v40": r40, "kept": kept,
                     "coords_2d": coords}, f)

    # 双版对比汇总
    print("\n\n========== 对比汇总 ==========")
    print(f"{'参数':<10} {'簇数':>6} {'噪声':>6} {'噪声%':>8}")
    print(f"{'size=50':<10} {r50['n_clusters']:>6} {r50['n_noise']:>6} {r50['n_noise']/len(kept)*100:>7.1f}%")
    print(f"{'size=40':<10} {r40['n_clusters']:>6} {r40['n_noise']:>6} {r40['n_noise']/len(kept)*100:>7.1f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
