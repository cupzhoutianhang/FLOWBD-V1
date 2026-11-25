"""
sample_for_review.py — 从 1951 个方法节点抽样 + 自动分类, 供人工审查

输出:
  landscape/method_sample.csv
    method_name, kind, source_paper, year, innovation, problem_solved,
    auto_class, auto_reason, your_judgment (空, 待人工填)

分类标签 (auto_class):
  real_method          论文真提出/改进/对比的核心方法 (我们要的)
  characterization     表征/计算工具 (XRD/SEM/DFT/CV/...) - 应归老 :Method label
  generic_term         过于通用的概念 (锂离子电池/相变材料 单字)
  condition            实验条件/参数值
  material_only        只是化学式/材料名, 无工艺特征
  device_component     装置或组件 (扣式电池/三电极体系)
  unclear              难判断, 留人工

用法:
  python sample_for_review.py --n 100 --seed 42
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import random
import re
import sys
from collections import Counter

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
ME_DIR = os.path.dirname(THIS_DIR)
METHOD_OUT = os.path.join(ME_DIR, "method_outputs")
OUT_CSV = os.path.join(THIS_DIR, "method_sample.csv")


# ---------- 分类规则 ----------
CHAR_TOOLS = [
    "xrd", "sem", "tem", "xps", "ftir", "raman", "dsc", "tga", "icp",
    "cv ", "eis", "gitt", "lsv", "edx", "eds", "afm", "bet", "ssa",
    "密度泛函", "dft", "分子动力学", "md模拟", "蒙特卡洛", "monte carlo",
    "充放电测试", "电化学阻抗", "循环伏安", "热重", "差示扫描", "n2 吸附", "n2吸附",
    "拉曼光谱", "x射线衍射", "电子显微镜", "热分析", "比表面积测",
    "线性扫描伏安",
]

GENERIC_NAMES = {
    "锂离子电池", "钠离子电池", "锌离子电池", "钾离子电池", "锂硫电池",
    "锂氧电池", "超级电容器", "液流电池", "燃料电池", "固态电池",
    "相变材料", "储能技术", "电极材料", "电解液", "隔膜",
    "集流体", "活性物质", "正极材料", "负极材料",
    "锂电池", "钠电池", "电池", "储能",
}

DEVICE_COMPONENT_KW = [
    "扣式电池", "三电极体系", "cr2025", "cr2032", "swagelok",
    "ag/agcl", "饱和甘汞", "工作电极", "对电极", "参比电极",
    "膜电极组件", "mea",
]


def auto_classify(name: str, innovation: str, problem: str) -> tuple[str, str]:
    """返回 (label, reason)."""
    name_s = name.strip()
    if not name_s:
        return "unclear", "name 为空"
    text = (name + " " + innovation + " " + problem).lower()
    name_l = name_s.lower()

    # 1. 表征/计算工具
    for kw in CHAR_TOOLS:
        if kw in name_l:
            return "characterization", f'name 含表征术语 "{kw}"'

    # 2. 通用术语 (整名落在 generic 集合)
    if name_s in GENERIC_NAMES:
        return "generic_term", f'整名 = "{name_s}" 通用概念'
    # 通用 + 法
    if name_s.rstrip("法") in GENERIC_NAMES and len(name_s) < 12:
        return "generic_term", f'通用概念+法 "{name_s}"'

    # 3. 装置/组件
    for kw in DEVICE_COMPONENT_KW:
        if kw in name_l:
            return "device_component", f'name 含装置/组件 "{kw}"'

    # 4. 条件/数值
    # 全是数字/单位
    if re.match(r"^[\d\.\-+°℃%\s]+(c|℃|°c|v|a|ma|mah|%|s|h|min)?$", name_l):
        return "condition", "name 像数值参数"

    # 5. 化学式 / 材料名 only (无工艺动词)
    # 短 + 全英文化学字符
    if len(name_s) <= 20 and re.match(r"^[A-Za-z0-9\s\-+/\(\)\[\]\.]+$", name_s):
        proc_words = ["合成", "制备", "method", "synthesis", "modification",
                      "coating", "doping", "process", "法", "工艺"]
        if not any(w in name_l for w in proc_words):
            return "material_only", "只是化学式/材料名, 无工艺动词"

    # 6. 太短 (<8 字) 且没有具体特征 -> 可疑通用
    if len(name_s) < 8:
        return "generic_term", f"过短 ({len(name_s)} 字), 无具体特征"

    # 7. 默认: 真方法
    return "real_method", ""


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    random.seed(args.seed)

    print("[1/3] 收集所有方法节点...")
    all_methods = []
    for fn in sorted(os.listdir(METHOD_OUT)):
        if not fn.endswith(".json"):
            continue
        with open(os.path.join(METHOD_OUT, fn), "r", encoding="utf-8") as f:
            d = json.load(f)
        pid = d.get("paper_id", "")
        year = d.get("year")
        for m in d.get("own_methods", []) or []:
            all_methods.append({
                "paper_id": pid, "year": year, "kind": "own",
                "name": m.get("name", ""),
                "innovation": m.get("innovation", ""),
                "problem_solved": m.get("problem_solved", ""),
            })
        for m in d.get("referenced_methods", []) or []:
            all_methods.append({
                "paper_id": pid, "year": year, "kind": "ref",
                "name": m.get("name", ""),
                "innovation": "",
                "problem_solved": "",
            })
    print(f"      总 {len(all_methods)} 个 (own={sum(1 for m in all_methods if m['kind']=='own')}, "
          f"ref={sum(1 for m in all_methods if m['kind']=='ref')})")

    print(f"[2/3] 随机抽样 {args.n} 个 (seed={args.seed})...")
    samples = random.sample(all_methods, args.n)

    print(f"[3/3] 自动预分类...")
    classified = []
    for m in samples:
        label, reason = auto_classify(m["name"], m["innovation"], m["problem_solved"])
        classified.append({**m, "auto_class": label, "auto_reason": reason})

    # 写 CSV
    with open(OUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "auto_class", "auto_reason", "your_judgment",
            "kind", "method_name",
            "innovation", "problem_solved",
            "year", "source_paper",
        ])
        for m in classified:
            w.writerow([
                m["auto_class"], m["auto_reason"], "",
                m["kind"], m["name"],
                m["innovation"][:200], m["problem_solved"][:200],
                m["year"] or "",
                m["paper_id"],
            ])

    # 统计
    cnt = Counter(c["auto_class"] for c in classified)
    print(f"\n=== 100 样本自动分类结果 ===")
    for k, v in cnt.most_common():
        print(f"  {k:<22}: {v:>3}  ({v}%)")

    # 各类前 5 个示例
    print(f"\n=== 各类前 5 个示例 ===")
    by_class = {}
    for c in classified:
        by_class.setdefault(c["auto_class"], []).append(c)
    for cls, items in by_class.items():
        print(f"\n[{cls}] ({len(items)} 个):")
        for m in items[:5]:
            note = f" — {m['auto_reason']}" if m["auto_reason"] else ""
            print(f"  - [{m['kind']}] {m['name'][:55]}{note}")

    print(f"\n[done] CSV: {OUT_CSV}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
