"""
final_pipeline.py — 阶段 B 最终管线 (v40 final)

操作:
  1. 删除 Sub 10/11/14 (皮胶原/烧结混杂/微流控) 共 80 个
  2. Sub 12 (超疏水 87 个) 标 peripheral=True, 不参与 UMAP fit
  3. 对 1713 个非 peripheral 节点重跑 UMAP (n_neighbors=15, min_dist=0.3)
  4. 对 1713 个跑 HDBSCAN (min_cluster_size=40, leaf)
  5. 用 UMAP.transform 把 87 peripheral 投影到同一空间
  6. 输出 umap_v40_final.png + cluster_labels.csv (供人工校验标签)

注意:
  - 输入 embeddings 复用 embeddings_v2.pkl (已清洗 + 剥前缀)
  - 弱关联节点列表从 weak_relevance.csv 读
"""
from __future__ import annotations

import csv
import os
import pickle
import sys
import time
from collections import Counter

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
COORDS_PKL = os.path.join(THIS_DIR, "coords_v2.pkl")
EMB_PKL = os.path.join(THIS_DIR, "embeddings_v2.pkl")
WEAK_CSV = os.path.join(THIS_DIR, "weak_relevance.csv")

FINAL_STATE = os.path.join(THIS_DIR, "final_state.pkl")
FINAL_PNG = os.path.join(THIS_DIR, "umap_v40_final.png")
LABEL_CSV = os.path.join(THIS_DIR, "cluster_labels.csv")
SUMMARY_MD = os.path.join(THIS_DIR, "final_summary.md")

DELETE_SUBS = {10, 11, 14}
PERIPHERAL_SUBS = {12}


# ============ 主题字典 (同 recluster_compare.py, 但顺序更稳) ============
TOPIC_DICT = [
    ("液流电池-离子膜", ["nafion", "spsf", "speek", "全氟磺酸", "磺化聚芳醚", "质子交换膜", "离子选择"]),
    ("液流电池-电堆/电极", ["全钒", "vrfb", "电堆", "流场", "石墨毡", "碳毡", "液流电池"]),
    ("锂硫电池", ["锂硫", "li2s", "硫化锂", "多硫化物", "穿梭"]),
    ("锂氧/锂二氧化碳电池", ["锂-二氧化碳", "锂二氧化碳", "锂氧", "li-co2", "锂空气"]),
    ("固态电解质-硫化物", ["硫化物固态", "硫银锗矿", "lgps", "li6ps5", "li10gep2s12", "固态电解质"]),
    ("退役电池-修复/回收", ["退役锂", "lfp 回收", "电池回收", "正极修复", "回收处理"]),
    ("钠离子电池-正负极", ["钠离子", "p2-na", "硬碳钠电", "na3v2", "Na2/3MnO2", "层状钠"]),
    ("钾离子电池", ["钾离子", "k0.45mn", "k0.48mn", "p3-k"]),
    ("锌离子/锌空气", ["锌离子", "zn²", "锌空气", "zn 沉积"]),
    ("超电容-PANI/PPy", ["pani", "聚苯胺", "聚吡咯", "ppy"]),
    ("超电容-Ni电极", ["ni3s2", "泡沫镍", "nico2o4", "氢氧化镍"]),
    ("超电容-MnO2复合", ["mno2", "mno₂", "二氧化锰", "石墨烯/mno"]),
    ("电极-MOF多孔碳", ["mof", "金属有机框架", "iso mof", "多孔碳/mof"]),
    ("电极-生物质碳", ["生物质", "木质素", "纤维素衍生", "果壳", "松花粉", "甘蔗渣", "稻壳"]),
    ("电极-多孔碳模板", ["软模板", "硬模板", "f127", "pmma模板", "活化炭", "活性炭", "多孔碳"]),
    ("电极-碳纳米纤维", ["静电纺丝", "碳纳米纤维", "湿法纺丝"]),
    ("能源系统集成", ["电-氢", "电氢", "风光制氢", "退役电池配置", "容量配置", "费用最小化", "氢储能", "光储充"]),
    ("电池管理BMS", ["故障诊断", "soc", "短路检测", "电池一致性", "电池包"]),
    ("制氢-电解水/重整", ["电解水", "甲烷化", "甲烷重整", "co2 还原", "碱性电解", "pem 电解"]),
    ("物理储能-CAES/LAES", ["caes", "压缩空气", "液态空气", "laes", "液氢", "lng 冷能", "超临界 co₂", "超临界co₂", "ccpes", "lces"]),
    ("热化学储能-钙基", ["钙基", "热化学储能", "ca(oh)2", "caco3"]),
    ("相变-石蜡/共熔", ["石蜡", "膨胀石墨", "共熔", "脂肪酸", "硬脂酸", "癸酸", "月桂酸", "棕榈酸"]),
    ("相变-微胶囊", ["微胶囊", "原位聚合", "复凝聚", "壁材"]),
    ("储热-换热系统", ["翅片", "换热器", "管壳式", "热管", "蓄热", "壳管", "螺旋管", "填充床", "梯级储热"]),
    ("模型/建模", ["数值模型", "数学模型", "关联式", "有限元", "数值模拟"]),
    ("剥离/分离工艺", ["剥离", "纳滤", "电渗析", "双极膜"]),
]


def guess_topic(method_names: list[str]) -> str:
    text = " ".join(n.lower() for n in method_names)
    scored = []
    for topic, kws in TOPIC_DICT:
        score = sum(text.count(kw) for kw in kws)
        if score > 0:
            scored.append((score, topic))
    if not scored:
        return f"未识别-请人工标 ({method_names[0][:20] if method_names else '?'})"
    scored.sort(reverse=True)
    return scored[0][1]


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    # ---------- 1. 加载 ----------
    print("[1/7] 加载数据...")
    with open(COORDS_PKL, "rb") as f:
        d = pickle.load(f)
    with open(EMB_PKL, "rb") as f:
        e = pickle.load(f)
    kept = d["kept"]
    embeddings = e["embeddings"]
    n_total = len(kept)
    print(f"      原始 kept: {n_total}, embeddings: {embeddings.shape}")

    # ---------- 2. 读弱关联 CSV, 标记 delete / peripheral ----------
    print("[2/7] 读 weak_relevance.csv 标记...")
    weak_records: dict[tuple[str, str], int] = {}
    with open(WEAK_CSV, "r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            sub_id = int(row["sub_id"])
            key = (row["source_paper"], row["method_name"])
            weak_records[key] = sub_id

    # 每个 kept 节点的状态: 'keep' / 'delete' / 'peripheral'
    status = []
    for m in kept:
        key = (m["paper_id"], m["name"])
        sub_id = weak_records.get(key)
        if sub_id is None:
            status.append("keep")
        elif sub_id in DELETE_SUBS:
            status.append("delete")
        elif sub_id in PERIPHERAL_SUBS:
            status.append("peripheral")
        else:
            status.append("keep")

    n_keep = sum(1 for s in status if s == "keep")
    n_del = sum(1 for s in status if s == "delete")
    n_peri = sum(1 for s in status if s == "peripheral")
    print(f"      keep={n_keep}  delete={n_del}  peripheral={n_peri}")
    print(f"      预期总节点 = {n_keep + n_peri} (删除 {n_del})")

    # ---------- 3. 切片 ----------
    print("[3/7] 切片 embeddings...")
    import numpy as np

    keep_idx = [i for i, s in enumerate(status) if s == "keep"]
    peri_idx = [i for i, s in enumerate(status) if s == "peripheral"]

    keep_kept = [kept[i] for i in keep_idx]
    peri_kept = [kept[i] for i in peri_idx]
    keep_emb = embeddings[keep_idx]
    peri_emb = embeddings[peri_idx]
    print(f"      keep_emb shape={keep_emb.shape}  peri_emb shape={peri_emb.shape}")

    # ---------- 4. 在 keep 上 fit UMAP ----------
    print("[4/7] UMAP fit on keep (n_neighbors=15, min_dist=0.3)...")
    import umap

    t0 = time.time()
    reducer = umap.UMAP(
        n_neighbors=15, min_dist=0.3, n_components=2,
        metric="cosine", random_state=42, verbose=False,
    )
    coords_keep = reducer.fit_transform(keep_emb)
    print(f"      fit_transform 用时 {time.time()-t0:.1f}s, shape={coords_keep.shape}")

    # transform peripheral
    print("[4b/7] UMAP transform peripheral into same space...")
    coords_peri = reducer.transform(peri_emb)
    print(f"      transform shape={coords_peri.shape}")

    # ---------- 5. HDBSCAN on keep only ----------
    print("[5/7] HDBSCAN on keep (min_cluster_size=40, leaf)...")
    import hdbscan

    t0 = time.time()
    cl = hdbscan.HDBSCAN(
        min_cluster_size=40,
        min_samples=5,
        metric="euclidean",
        cluster_selection_method="leaf",
    )
    labels_keep = cl.fit_predict(coords_keep)
    print(f"      用时 {time.time()-t0:.1f}s")
    cnt = Counter(labels_keep.tolist())
    n_noise = cnt.get(-1, 0)
    n_clusters = sum(1 for k in cnt if k >= 0)
    print(f"      簇数 {n_clusters}  噪声 {n_noise} ({n_noise/len(keep_kept)*100:.1f}%)")
    for c in sorted(cnt.keys()):
        marker = "" if c >= 0 else " (噪声)"
        print(f"        cluster {c:>2}: {cnt[c]}{marker}")

    # ---------- 6. 计算每个簇的 top10 + 自动标签 ----------
    print("[6/7] 计算每簇 top 10 + 自动标签...")
    cluster_info = {}
    for c in sorted(set(labels_keep.tolist())):
        if c == -1:
            continue
        mask = labels_keep == c
        sub_emb = keep_emb[mask]
        centroid = sub_emb.mean(axis=0)
        centroid /= np.linalg.norm(centroid)
        sims = sub_emb @ centroid
        sub_members = [keep_kept[i] for i in range(len(keep_kept)) if mask[i]]
        sorted_idx = np.argsort(-sims)
        top10 = [
            {
                "rank": rank + 1,
                "sim": float(sims[idx]),
                "name": sub_members[idx]["cleaned_name"],
                "paper": sub_members[idx]["paper_id"],
                "kind": sub_members[idx]["kind"],
                "year": sub_members[idx].get("year"),
            }
            for rank, idx in enumerate(sorted_idx[:10])
        ]
        topic = guess_topic([t["name"] for t in top10])
        # 2D 簇中心
        center = coords_keep[mask].mean(axis=0)
        cluster_info[int(c)] = {
            "size": int(mask.sum()),
            "auto_label": topic,
            "top10": top10,
            "center_2d": [float(center[0]), float(center[1])],
        }

    # ---------- 7. 输出 PNG / CSV / state ----------
    print("[7/7] 输出文件...")

    # cluster_labels.csv: 每簇一行, 加 my_label 空列
    with open(LABEL_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "cluster_id", "size", "auto_label", "my_label",
            "top1", "top2", "top3", "top4", "top5",
            "top6", "top7", "top8", "top9", "top10",
        ])
        for cid in sorted(cluster_info.keys()):
            info = cluster_info[cid]
            row = [cid, info["size"], info["auto_label"], ""]  # my_label 空
            for i in range(10):
                if i < len(info["top10"]):
                    row.append(f"[{info['top10'][i]['kind']}] {info['top10'][i]['name']}")
                else:
                    row.append("")
            w.writerow(row)
    print(f"      cluster_labels.csv ({len(cluster_info)} 行): {LABEL_CSV}")

    # PNG
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
        plt.rcParams["axes.unicode_minus"] = False

        fig, ax = plt.subplots(figsize=(14, 11), dpi=110)

        # 噪声 (keep 内 cluster=-1)
        noise_mask = labels_keep == -1
        ax.scatter(coords_keep[noise_mask, 0], coords_keep[noise_mask, 1],
                   c="lightgray", s=4, alpha=0.25, label="noise")
        # 簇
        non_noise = ~noise_mask
        scat = ax.scatter(coords_keep[non_noise, 0], coords_keep[non_noise, 1],
                          c=labels_keep[non_noise], cmap="tab20", s=14, alpha=0.7)
        # peripheral (Sub 12)
        ax.scatter(coords_peri[:, 0], coords_peri[:, 1],
                   marker="x", c="darkred", s=20, alpha=0.5,
                   label=f"peripheral Sub12 (n={len(coords_peri)})")
        # 簇中心标
        for cid, info in cluster_info.items():
            cx, cy = info["center_2d"]
            ax.annotate(
                f"{cid}: {info['auto_label']}\n({info['size']})",
                (cx, cy),
                ha="center", va="center",
                fontsize=9, fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.3",
                          facecolor="white", edgecolor="black", alpha=0.85),
            )
        ax.legend(loc="upper right", fontsize=9)
        ax.set_title(
            f"UMAP v40 FINAL | n_keep={len(keep_kept)} +peri={len(peri_kept)} "
            f"clusters={n_clusters} noise={n_noise} ({n_noise/len(keep_kept)*100:.0f}%)"
        )
        ax.set_xlabel("UMAP-1"); ax.set_ylabel("UMAP-2")
        plt.tight_layout()
        plt.savefig(FINAL_PNG)
        plt.close()
        print(f"      PNG: {FINAL_PNG}")
    except ImportError:
        print("      (matplotlib 未装, 跳过 PNG)")

    # final_state.pkl: 完整数据供 B5 写 Neo4j 用
    with open(FINAL_STATE, "wb") as f:
        pickle.dump({
            "keep_kept": keep_kept,
            "peri_kept": peri_kept,
            "coords_keep": coords_keep,
            "coords_peri": coords_peri,
            "labels_keep": labels_keep,
            "cluster_info": cluster_info,
            "deleted_count": n_del,
            "params": {
                "umap_n_neighbors": 15,
                "umap_min_dist": 0.3,
                "hdbscan_min_cluster_size": 40,
                "hdbscan_min_samples": 5,
                "hdbscan_selection": "leaf",
            },
        }, f)
    print(f"      final_state.pkl: {FINAL_STATE}")

    # 总结报告
    with open(SUMMARY_MD, "w", encoding="utf-8") as f:
        f.write("# 阶段 B 最终聚类总结\n\n")
        f.write(f"- 原始 1880 个方法节点\n")
        f.write(f"- **删除**: {n_del} 个 (Sub 10/11/14)\n")
        f.write(f"- **peripheral**: {n_peri} 个 (Sub 12)\n")
        f.write(f"- **主聚类节点**: {n_keep} 个\n\n")
        f.write(f"## HDBSCAN (min_size=40, leaf) 结果\n\n")
        f.write(f"- 簇数: {n_clusters}\n")
        f.write(f"- 噪声: {n_noise} ({n_noise/n_keep*100:.1f}%)\n")
        f.write(f"- 入簇: {n_keep - n_noise} ({(n_keep-n_noise)/n_keep*100:.1f}%)\n\n")
        f.write(f"## 各簇详情 (auto_label 待人工校验)\n\n")
        for cid in sorted(cluster_info.keys()):
            info = cluster_info[cid]
            f.write(f"### Cluster {cid} — auto: **{info['auto_label']}** ({info['size']} 节点)\n\n")
            f.write("Top 10:\n\n")
            for t in info["top10"]:
                f.write(f"{t['rank']:>2}. sim={t['sim']:.3f}  **{t['name']}**  *({t['paper'][:40]}, {t['kind']}, {t.get('year') or '?'})*\n")
            f.write("\n")
    print(f"      summary: {SUMMARY_MD}")

    print("\n[done] 等你人工校验 cluster_labels.csv 的 my_label 列, 然后我写 Neo4j")
    return 0


if __name__ == "__main__":
    sys.exit(main())
