"""名字启发式判定: 两个方法名是否疑似同义/别名 (spec 四).

只做**辅助信号**, 最终由审查器判定. 但当启发式命中 alias 时, 抽取器不该输出关系;
即便输出了, edge_validation 也会用此信号 + 审查器 linkage_type 联合裁决.
"""
from __future__ import annotations

import re
import unicodedata


def _normalize(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"\s+", "", s)
    return s.lower()


# 常见"限定前缀": 若把它们从长的一方剥掉, 剩余部分等于另一方 → 视为同一技术的更具体命名
_QUALIFIER_PREFIXES = (
    # 材料 / 组分限定
    "尿素", "氯化胆碱", "氯化钠", "醋酸钠", "石蜡", "生物质", "多孔碳",
    # 作者 / 单位限定
    "刘昌会等", "王等", "陈等", "smith等", "smith 等",
    # 特殊工艺限定
    "改性", "复合", "掺杂", "包覆",
    # 类别 / 数字限定
    "第一代", "第二代", "新型", "改进型", "优化型",
    # 常见分隔符
    "/", "-", "_",
)


def looks_like_alias(name_a: str, name_b: str) -> tuple:
    """启发式判定 name_b 是否是 name_a 的更具体命名 (或反之).

    返回 (bool, reason).
    """
    na = _normalize(name_a)
    nb = _normalize(name_b)
    if not na or not nb:
        return False, ""
    if na == nb:
        return True, "identical_after_normalization"

    # 谁更长
    long_n, short_n = (na, nb) if len(na) >= len(nb) else (nb, na)
    long_orig = name_a if len(na) >= len(nb) else name_b
    short_orig = name_b if len(na) >= len(nb) else name_a

    # 一方是另一方的完整子串
    if short_n in long_n:
        # 但要求长者只是在短者前后加了限定
        # 找出剩余部分
        idx = long_n.find(short_n)
        prefix = long_n[:idx]
        suffix = long_n[idx + len(short_n):]
        # 只要 prefix + suffix 中至少一段是常见 qualifier 前后缀 → alias
        for q in _QUALIFIER_PREFIXES:
            qn = _normalize(q)
            if qn and (qn in prefix or qn in suffix):
                return True, f"substring_with_qualifier:{q}"
        # 剩余部分很短 (≤4 chars) → 也算 alias
        if len(prefix) + len(suffix) <= 4:
            return True, "short_extra_content"
        return False, ""

    # Jaccard on char bi-grams 高度重合 → 可能同一技术不同表述
    bg_a = {na[i:i+2] for i in range(len(na) - 1)}
    bg_b = {nb[i:i+2] for i in range(len(nb) - 1)}
    if bg_a and bg_b:
        j = len(bg_a & bg_b) / len(bg_a | bg_b)
        # 高 Jaccard (>0.75) 且长度差 <30% → 疑似同一
        if j >= 0.75 and abs(len(na) - len(nb)) / max(len(na), len(nb)) < 0.3:
            return True, f"high_jaccard_{round(j, 2)}"

    return False, ""
