"""
classify_v2.py — 更严格的方法分类器 (基于 100 样本人工审查后改进)

新增识别:
  other_modeling   建模/数值方法/理论/关联式 (借鉴模型, 不是材料方法)
  characterization 计算/表征工具 (MD/DFT/PNM 等)
  generic_problem  问题陈述 / 局限性描述 (不是方法)
  other_mechanism  机理研究 (有作者名+机理 但无工艺动词)
  device_only      搅拌桨/反应器等设备本身

输出: 更新 method_sample.csv 的 your_judgment 列
"""
from __future__ import annotations

import csv
import os
import re
import sys
from collections import Counter

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLE_CSV = os.path.join(THIS_DIR, "method_sample.csv")

# 工艺/制备/操作动词 — 含这些通常是 real_method
PROCESS_VERBS = [
    "合成", "制备", "复合", "改性", "掺杂", "包覆", "涂层", "处理", "活化",
    "退火", "热处理", "气相", "水热", "溶剂", "电沉积", "电镀", "喷雾",
    "纺丝", "球磨", "剥离", "插层", "模板", "原位", "浸渍", "封装", "微胶囊",
    "聚合", "凝胶", "凝固", "破乳", "焊接", "组装", "刻蚀", "蚀刻", "光刻",
    "炭化", "碳化", "煅烧", "烧结", "冷却", "蒸馏", "提纯", "过滤", "纯化",
    "改进", "优化", "调控", "调节", "构筑", "设计", "构建", "增强", "强化",
    "method", "synthesis", "process", "modification",
    "诱导", "驱动", "选择性", "策略", "工艺", "途径", "方案", "路径",
    "可控", "原子层", "化学气相", "物理气相", "湿化学",
]

# 表征/计算工具
CHAR_TOOLS_V2 = [
    "xrd", "sem", "tem", "xps", "ftir", "raman", "dsc", "tga", "icp",
    "cv ", " cv", "eis", "gitt", "lsv", "edx", "eds", "afm", "bet",
    "密度泛函", "dft", "分子动力学", "md模拟", "md 模拟",
    "蒙特卡洛", "monte carlo",
    "充放电测试", "电化学阻抗", "循环伏安", "热重", "差示扫描", "比表面积测",
    "拉曼光谱", "x射线衍射",
    "ab initio", "第一性原理",
]

# 模型/理论 关键词
MODELING_KW = [
    "数值模型", "数学模型", "关联式", "经典模型", "理论模型", "解析模型",
    "经典理论", "理论框架",
    "model", "theory", "theoretical", "analytical",
    "球-柱简化", "球柱简化", "网络模型",
    "概率模型", "动力学模型", "经验公式",
    "离散单元法", "离散元",
    "综合计算法", "计算法模型",
    "关联理论",
    "经典双电层模型",
    "数值模拟方法",  # 注意: "数值模拟" 单独不算; 是方法时算 real (如 "微气泡数值模拟")
    "快速预测法", "预测公式", "预测模型", "拟合公式",
    "无量纲", "尺度分析",
    "蓄热时间无量纲",
]

# 机理类 (无工艺动词时归此)
MECHANISM_KW_NO_PROCESS = ["机理", "mechanism"]

# 问题陈述
PROBLEM_KW = [
    "低导电率限制", "限制应用", "存在问题", "导致", "瓶颈",
]

# 装置本体
DEVICE_ONLY_KW = [
    "搅拌桨", "搅拌器", "反应器本体", "反应釜本身",
    "扣式电池", "三电极体系", "cr2025", "cr2032",
    "工作电极", "对电极", "参比电极",
]

# 过于通用 (整名命中且 ≤ 12 字)
GENERIC_ONLY = {
    "锂离子电池", "钠离子电池", "锌离子电池", "钾离子电池", "锂硫电池",
    "锂氧电池", "超级电容器", "液流电池", "燃料电池", "固态电池",
    "相变材料", "储能技术", "电极材料", "电解液", "隔膜",
    "集流体", "活性物质", "正极材料", "负极材料",
    "锂电池", "钠电池", "电池", "储能",
}


def classify_v2(name: str, innovation: str, problem: str) -> tuple[str, str]:
    name_s = name.strip()
    if not name_s:
        return "unclear", "name 为空"
    text = (name + " " + innovation + " " + problem).lower()
    name_l = name_s.lower()

    has_process_verb = any(v in text for v in PROCESS_VERBS)

    # 1. 表征/计算工具 (强信号)
    for kw in CHAR_TOOLS_V2:
        if kw in name_l:
            return "characterization", f'含表征术语 "{kw}"'

    # 2. 建模/理论 (注意: 有工艺动词时不算)
    for kw in MODELING_KW:
        if kw in name_l:
            return "other_modeling", f'含模型术语 "{kw}"'

    # 3. 机理研究 (没工艺动词, 只有"机理")
    if any(kw in name_l for kw in MECHANISM_KW_NO_PROCESS) and not has_process_verb:
        return "other_mechanism", "name 含'机理' 但无工艺动词"

    # 4. 问题陈述
    for kw in PROBLEM_KW:
        if kw in name_l:
            return "generic_problem", f'name 是问题陈述 "{kw}"'

    # 5. 装置本体
    for kw in DEVICE_ONLY_KW:
        if kw in name_l:
            return "device_only", f'装置/组件 "{kw}"'

    # 6. 过短 + 过通用
    if name_s in GENERIC_ONLY:
        return "generic_term", f'整名 = "{name_s}" 通用概念'
    if len(name_s) < 8:
        return "generic_term", f"过短 ({len(name_s)} 字), 无具体特征"

    # 7. 短英文化学式 + 无工艺动词
    if (len(name_s) <= 18 and
            re.match(r"^[A-Za-z0-9\s\-+/\(\)\[\]\._@]+$", name_s) and
            not has_process_verb):
        return "material_only", "短化学式/材料名, 无工艺动词"

    # 8. 默认: 真方法
    return "real_method", ""


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    if not os.path.isfile(SAMPLE_CSV):
        print(f"[ERR] {SAMPLE_CSV} 不存在", file=sys.stderr)
        return 1

    rows = []
    with open(SAMPLE_CSV, "r", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            label, reason = classify_v2(
                r["method_name"], r["innovation"], r["problem_solved"]
            )
            r["your_judgment"] = label
            r["auto_reason"] = reason if reason else r["auto_reason"]
            rows.append(r)

    with open(SAMPLE_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)

    cnt = Counter(r["your_judgment"] for r in rows)
    print(f"\n=== v2 分类结果 (n={len(rows)}) ===")
    for k, v in cnt.most_common():
        print(f"  {k:<22}: {v:>3}  ({v}%)")

    # 各类示例
    print(f"\n=== 各类前 5 个示例 ===")
    by_class = {}
    for r in rows:
        by_class.setdefault(r["your_judgment"], []).append(r)
    for cls in ["characterization", "other_modeling", "other_mechanism",
                "generic_problem", "device_only", "generic_term", "material_only",
                "real_method"]:
        if cls not in by_class:
            continue
        items = by_class[cls]
        print(f"\n[{cls}] ({len(items)} 个):")
        for r in items[:5]:
            print(f"  - [{r['kind']}] {r['method_name'][:60]}  | {r['auto_reason'][:50]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
