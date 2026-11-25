"""
recluster_clean.py — 完整清洗 + 重聚类管线 (阶段 B Step 4 v2)

流程:
  1. 加载全部 1951 个方法
  2. v2 分类器过滤掉 ~13% 非方法 (建模/表征/通用/装置/机理/问题陈述)
  3. 剥离方法名前缀: "Tang2003 ..." -> "...", "本文作者课题组..." -> "..."
  4. 用 bge-m3 重新 embedding (清洗后的 name + innovation + problem)
  5. UMAP 2D (min_dist=0.3, n_neighbors=15) — 更松散, 易形成大陆
  6. HDBSCAN (min_cluster_size=80) — 只保留主簇
  7. 输出 coords_clean.pkl + PNG 预览

环境变量在 import transformers 前设, 避开 Keras 3 / TF 兼容问题.
"""
from __future__ import annotations

import argparse
import json
import os
import pickle
import re
import sys
import time

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_FLAX", "0")
os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
ME_DIR = os.path.dirname(THIS_DIR)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(ME_DIR)))
METHOD_OUT = os.path.join(ME_DIR, "method_outputs")
BGE_M3_PATH = os.path.join(PROJECT_ROOT, "src", "rag", "models", "bge-m3")

CLEAN_PKL = os.path.join(THIS_DIR, "cleaned_methods.pkl")
EMB_V2_PKL = os.path.join(THIS_DIR, "embeddings_v2.pkl")
COORDS_PKL = os.path.join(THIS_DIR, "coords_v2.pkl")
PNG = os.path.join(THIS_DIR, "umap_preview_v2.png")
DROP_REPORT = os.path.join(THIS_DIR, "filter_drop_report.md")


# ============ v2 分类规则 (从 classify_v2.py 复制+精简) ============
PROCESS_VERBS = [
    "合成", "制备", "复合", "改性", "掺杂", "包覆", "涂层", "处理", "活化",
    "退火", "热处理", "气相", "水热", "溶剂", "电沉积", "电镀", "喷雾",
    "纺丝", "球磨", "剥离", "插层", "模板", "原位", "浸渍", "封装", "微胶囊",
    "聚合", "凝胶", "凝固", "破乳", "焊接", "组装", "刻蚀", "蚀刻",
    "炭化", "碳化", "煅烧", "烧结", "蒸馏", "提纯", "过滤", "纯化",
    "改进", "优化", "调控", "调节", "构筑", "设计", "构建", "增强", "强化",
    "method", "synthesis", "process", "modification",
    "诱导", "驱动", "策略", "工艺", "途径", "方案", "路径",
    "可控", "原子层", "化学气相", "物理气相", "湿化学",
]
CHAR_TOOLS = [
    "xrd", "sem", "tem", "xps", "ftir", "raman", "dsc", "tga", "icp",
    "cv ", " cv", "eis", "gitt", "lsv", "edx", "eds", "afm", "bet",
    "密度泛函", "dft", "分子动力学", "md模拟", "md 模拟",
    "蒙特卡洛", "monte carlo",
    "充放电测试", "电化学阻抗", "循环伏安", "热重", "差示扫描", "比表面积测",
    "拉曼光谱", "x射线衍射",
    "ab initio", "第一性原理",
]
MODELING_KW = [
    "数值模型", "数学模型", "关联式", "经典模型", "理论模型", "解析模型",
    "经典理论", "理论框架",
    "model", "theory", "theoretical", "analytical",
    "球-柱简化", "球柱简化", "网络模型",
    "概率模型", "动力学模型", "经验公式",
    "离散单元法", "离散元",
    "综合计算法", "计算法模型",
    "关联理论", "经典双电层模型",
    "快速预测法", "预测公式", "预测模型", "拟合公式",
    "无量纲", "尺度分析",
]
MECHANISM_KW = ["机理", "mechanism"]
PROBLEM_KW = ["低导电率限制", "限制应用", "存在问题", "导致容量", "瓶颈"]
DEVICE_ONLY = ["搅拌桨", "搅拌器", "反应器本体", "反应釜本身",
               "扣式电池", "三电极体系", "cr2025", "cr2032",
               "工作电极", "对电极", "参比电极"]
GENERIC_ONLY = {
    "锂离子电池", "钠离子电池", "锌离子电池", "钾离子电池", "锂硫电池",
    "锂氧电池", "超级电容器", "液流电池", "燃料电池", "固态电池",
    "相变材料", "储能技术", "电极材料", "电解液", "隔膜",
    "集流体", "活性物质", "正极材料", "负极材料",
    "锂电池", "钠电池", "电池", "储能",
}


def classify(name: str, innovation: str, problem: str) -> tuple[str, str]:
    name_s = name.strip()
    if not name_s:
        return "drop_empty", "name 为空"
    text = (name + " " + innovation + " " + problem).lower()
    name_l = name_s.lower()
    has_process = any(v in text for v in PROCESS_VERBS)

    for kw in CHAR_TOOLS:
        if kw in name_l:
            return "drop_characterization", f'"{kw}"'
    for kw in MODELING_KW:
        if kw in name_l:
            return "drop_modeling", f'"{kw}"'
    if any(kw in name_l for kw in MECHANISM_KW) and not has_process:
        return "drop_mechanism", "含'机理'无工艺动词"
    for kw in PROBLEM_KW:
        if kw in name_l:
            return "drop_problem", f'"{kw}"'
    for kw in DEVICE_ONLY:
        if kw in name_l:
            return "drop_device", f'"{kw}"'
    if name_s in GENERIC_ONLY:
        return "drop_generic", f'整名 = "{name_s}"'
    if len(name_s) < 8:
        return "drop_generic", f"过短 ({len(name_s)} 字)"
    if (len(name_s) <= 18 and
            re.match(r"^[A-Za-z0-9\s\-+/\(\)\[\]\._@]+$", name_s) and
            not has_process):
        return "drop_material_only", "短化学式无工艺"

    return "keep", ""


# ============ 方法名前缀剥离 ============
# 常见前缀样态:
#   "Tang2003 ..."           作者+年份
#   "Wang等2018 ..."          作者等+年份
#   "Šavija2017 ..."          带特殊字符的作者
#   "本文作者课题组 ..."     本文/本作者
#   "本课题组 ..."            本课题组
#   "Smith et al. ..."        英文 et al
#   "Smith等[12] ..."         作者+引用编号
#   "传统 ..." / "经典 ..."   修饰词 (保留前 2 个字符以保住语义)

PREFIX_PATTERNS = [
    # 中英文作者名 + 年份 (开头 1-3 个汉字/英文 + 4 位年)
    r"^[A-Za-z一-龥À-ſ][A-Za-z一-龥À-ſ\.\s]{0,15}\s*\d{4}\s+",
    # "作者 等 YYYY"
    r"^[A-Za-z一-龥À-ſ][一-龥A-Za-z\.\s]{0,15}等\s*\d{0,4}\s*",
    # "Smith et al. YYYY"
    r"^[A-Za-z]+\s+et\s*al\.?\s*\d{0,4}\s+",
    # "Smith[12]" / "Smith [12]"
    r"^[A-Za-z一-龥]+等?\s*\[\d+(-\d+)?\]\s*",
    # "本文作者" / "本课题组" / "本作者" / "本文"
    r"^本(文(作者(课题组)?)?|课题组|作者)\s*",
]


def strip_prefix(name: str) -> tuple[str, str]:
    """剥离作者+年份前缀. 返回 (cleaned_name, removed_prefix).
    若剥后过短 (<6 字) 则保留原 name."""
    original = name.strip()
    cleaned = original
    removed = ""
    for pat in PREFIX_PATTERNS:
        m = re.match(pat, cleaned)
        if m:
            removed += cleaned[: m.end()]
            cleaned = cleaned[m.end():].strip()
            break  # 一次只剥一层
    # 保护: 剥太狠就还原
    if len(cleaned) < 6:
        return original, ""
    return cleaned, removed


# ============ 主流程 ============
def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--min-dist", type=float, default=0.3)
    ap.add_argument("--n-neighbors", type=int, default=15)
    ap.add_argument("--min-cluster-size", type=int, default=80)
    ap.add_argument("--min-samples", type=int, default=10)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--skip-embed", action="store_true",
                    help="如果 embeddings_v2.pkl 存在, 跳过 embedding 直接用")
    args = ap.parse_args()

    # ---------- 1. 过滤 + 剥离前缀 ----------
    print("[1/5] 加载 + 过滤 + 剥前缀...")
    kept = []           # 每条: dict(paper_id, name, cleaned_name, kind, innovation, problem)
    dropped_by_class: dict[str, list] = {}
    prefix_examples: list[tuple[str, str, str]] = []  # (orig, cleaned, removed)

    for fn in sorted(os.listdir(METHOD_OUT)):
        if not fn.endswith(".json"):
            continue
        with open(os.path.join(METHOD_OUT, fn), "r", encoding="utf-8") as f:
            d = json.load(f)
        pid = d.get("paper_id", "")
        year = d.get("year")
        for kind, key in (("own", "own_methods"), ("ref", "referenced_methods")):
            for m in d.get(key) or []:
                name = (m.get("name") or "").strip()
                inno = m.get("innovation", "") if kind == "own" else ""
                prob = m.get("problem_solved", "") if kind == "own" else ""
                label, reason = classify(name, inno, prob)
                if label != "keep":
                    dropped_by_class.setdefault(label, []).append(
                        {"paper_id": pid, "name": name, "reason": reason, "kind": kind}
                    )
                    continue
                cleaned_name, removed = strip_prefix(name)
                if removed and len(prefix_examples) < 30:
                    prefix_examples.append((name, cleaned_name, removed))
                kept.append({
                    "paper_id": pid,
                    "year": year,
                    "kind": kind,
                    "name": name,
                    "cleaned_name": cleaned_name,
                    "innovation": inno,
                    "problem": prob,
                })

    total_before = sum(len(v) for v in dropped_by_class.values()) + len(kept)
    print(f"      过滤前: {total_before}")
    print(f"      保留 (real_method): {len(kept)}")
    print(f"      过滤明细:")
    for cls in sorted(dropped_by_class.keys()):
        print(f"        {cls:<25}: {len(dropped_by_class[cls])}")

    # 报告
    with open(DROP_REPORT, "w", encoding="utf-8") as f:
        f.write(f"# 过滤报告\n\n")
        f.write(f"过滤前: {total_before}\n")
        f.write(f"保留:  {len(kept)} ({len(kept)/total_before*100:.1f}%)\n\n")
        for cls, items in sorted(dropped_by_class.items()):
            f.write(f"## {cls} ({len(items)})\n\n")
            for x in items[:30]:
                f.write(f"- [{x['kind']}] {x['name']}  | reason: {x['reason']}\n")
            if len(items) > 30:
                f.write(f"- ... 还有 {len(items)-30}\n")
            f.write("\n")
        f.write("## 前缀剥离样例 (前 30)\n\n")
        for orig, cleaned, removed in prefix_examples:
            f.write(f"- '{orig}' -> '{cleaned}'  (剥除: '{removed}')\n")
    print(f"      过滤报告: {DROP_REPORT}")

    # 落盘 cleaned methods (供后续 step)
    with open(CLEAN_PKL, "wb") as f:
        pickle.dump(kept, f)
    print(f"      cleaned methods: {CLEAN_PKL}")

    # ---------- 2. embedding ----------
    if args.skip_embed and os.path.isfile(EMB_V2_PKL):
        print(f"[2/5] 跳过 embedding (复用 {EMB_V2_PKL})...")
        with open(EMB_V2_PKL, "rb") as f:
            emb_data = pickle.load(f)
        embeddings = emb_data["embeddings"]
    else:
        print("[2/5] bge-m3 embedding (清洗后的 name + innovation + problem)...")
        import torch
        import torch.nn.functional as F
        from transformers import AutoModel, AutoTokenizer
        import numpy as np

        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"      device = {device}")
        t0 = time.time()
        tokenizer = AutoTokenizer.from_pretrained(BGE_M3_PATH)
        model = AutoModel.from_pretrained(BGE_M3_PATH).to(device)
        model.eval()
        print(f"      模型加载用时 {time.time()-t0:.1f}s")

        # 构造 embedding 文本
        texts = []
        for m in kept:
            parts = [m["cleaned_name"]]
            if m["innovation"]:
                parts.append(f"创新: {m['innovation'][:200]}")
            if m["problem"]:
                parts.append(f"解决: {m['problem'][:200]}")
            texts.append("。".join(parts)[:600])

        @torch.no_grad()
        def _encode(batch_texts):
            enc = tokenizer(batch_texts, padding=True, truncation=True,
                            max_length=512, return_tensors="pt").to(device)
            out = model(**enc)
            cls = out.last_hidden_state[:, 0]
            return F.normalize(cls, p=2, dim=1).cpu().numpy()

        t0 = time.time()
        chunks = []
        for i in range(0, len(texts), args.batch_size):
            chunk = _encode(texts[i: i + args.batch_size])
            chunks.append(chunk)
        embeddings = np.vstack(chunks)
        print(f"      shape={embeddings.shape}  用时 {time.time()-t0:.1f}s")

        with open(EMB_V2_PKL, "wb") as f:
            pickle.dump({"kept": kept, "texts": texts, "embeddings": embeddings}, f)
        print(f"      embeddings: {EMB_V2_PKL}")

    # ---------- 3. UMAP ----------
    print(f"[3/5] UMAP 2D (n_neighbors={args.n_neighbors}, min_dist={args.min_dist}, metric=cosine)...")
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
    coords = reducer.fit_transform(embeddings)
    print(f"      shape={coords.shape}  用时 {time.time()-t0:.1f}s")
    print(f"      坐标范围: x [{coords[:,0].min():.2f}, {coords[:,0].max():.2f}], "
          f"y [{coords[:,1].min():.2f}, {coords[:,1].max():.2f}]")

    # ---------- 4. HDBSCAN ----------
    print(f"[4/5] HDBSCAN (min_cluster_size={args.min_cluster_size}, "
          f"min_samples={args.min_samples})...")
    import hdbscan
    from collections import Counter

    t0 = time.time()
    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=args.min_cluster_size,
        min_samples=args.min_samples,
        metric="euclidean",
    )
    labels = clusterer.fit_predict(coords)
    print(f"      用时 {time.time()-t0:.1f}s")
    cnt = Counter(labels.tolist())
    n_noise = cnt.get(-1, 0)
    n_clusters = sum(1 for k in cnt if k >= 0)
    print(f"      簇数: {n_clusters}  | 噪声: {n_noise} ({n_noise/len(labels)*100:.1f}%)")
    for label in sorted(cnt.keys()):
        if label >= 0:
            print(f"        cluster {label:>2}: {cnt[label]} 个")
    if n_noise:
        print(f"        noise   -1: {n_noise} 个")

    # ---------- 5. 输出 + 预览 ----------
    print(f"[5/5] 输出 coords + PNG 预览...")
    with open(COORDS_PKL, "wb") as f:
        pickle.dump({
            "kept": kept,
            "coords_2d": coords,
            "cluster_labels": labels,
            "params": vars(args),
        }, f)
    print(f"      coords: {COORDS_PKL}")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np

        fig, ax = plt.subplots(figsize=(12, 10), dpi=100)
        noise_mask = labels == -1
        ax.scatter(coords[noise_mask, 0], coords[noise_mask, 1],
                   c="lightgray", s=4, alpha=0.3, label="noise")
        non_noise = ~noise_mask
        scat = ax.scatter(coords[non_noise, 0], coords[non_noise, 1],
                          c=labels[non_noise], cmap="tab20", s=18, alpha=0.75)
        ax.set_title(
            f"UMAP+HDBSCAN (clean) | n={len(kept)} clusters={n_clusters} noise={n_noise}\n"
            f"min_dist={args.min_dist} min_cluster_size={args.min_cluster_size}"
        )
        ax.set_xlabel("UMAP-1"); ax.set_ylabel("UMAP-2")
        plt.colorbar(scat, ax=ax, label="cluster")
        plt.tight_layout()
        plt.savefig(PNG)
        print(f"      PNG: {PNG} ({os.path.getsize(PNG)/1024:.0f} KB)")
    except ImportError:
        print("      (matplotlib 未装, 跳过预览)")

    print("\n[done]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
