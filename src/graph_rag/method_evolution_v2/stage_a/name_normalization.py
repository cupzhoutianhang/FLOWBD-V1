"""name_normalization — 方法名规范化 (spec 六 + 七).

两条独立规则, 均无 API 调用:

  1) 专利复合命名规范化 (spec 六): 从 method_name 前缀分离 source_organization,
     保留 raw_method_name, 生成 normalized_method_name.

  2) 通用方法名降级 (spec 七): 孤立的通用工艺名 (水热合成法 / 溶胶-凝胶法 /
     模板法 / 热处理法) 若无对象/材料/结构限定, 由 accepted 降为 candidate.

设计原则:
  - 全部为纯函数, 输入输出可测.
  - 不调用 LLM.
  - 不移除已有 method 内容; 保留 raw 字段供复盘.
"""
from __future__ import annotations

import re


NAME_NORM_VERSION = "v1.1_broadened_suffixes_2026-07-02"


# ============================================================
# spec 六: 专利机构前缀
# ============================================================

# 覆盖常见中文机构后缀. rfind 取每个 suffix 的最右侧出现位置, best_end 取所有
# suffix end 位置的 max, 因此长/短 suffix 都可放入 (同一位置的长短 suffix 结束
# 位置相同, 短 suffix 独立命中新位置时能兜底覆盖).
_ORG_SUFFIXES = (
    "股份有限公司", "有限责任公司", "有限公司", "股份公司",
    "科技集团", "科技有限公司", "科技公司",
    "科学技术大学", "科技大学", "工业大学", "理工大学",
    "研究中心", "工程中心",
    "研究所", "研究院",
    "国家实验室", "重点实验室", "实验室",
    "大学", "学院",
    "公司", "集团", "研究部",
)

# 特殊白名单: 不算机构 (会被误判为 XX 大学的常见前缀)
_ORG_BLACKLIST = ("本文", "本研究", "该研究", "作者", "该团队")

# 前缀窗口: 最长 30 char.
_MAX_ORG_WINDOW = 30


def normalize_patent_method_name(raw_name: str) -> tuple:
    """把 "厦门大学玻璃纤维增强..." 拆成 (org, normalized_name).

    实现: 扫描前 30 chars 找**最右侧**的机构后缀命中点, 前部作为 org, 后部作为
    normalized_name. 只在拆分后余下 ≥4 字符 (仍有技术内容) 才接受.

    Returns:
      (source_organization, normalized_method_name)
      当无法识别机构时 source_organization = "".
    """
    if not raw_name:
        return "", ""
    raw = raw_name.strip()
    if any(raw.startswith(b) for b in _ORG_BLACKLIST):
        return "", raw
    window = raw[:_MAX_ORG_WINDOW]
    best_end = -1  # 最右侧后缀结束位置
    for suf in _ORG_SUFFIXES:
        idx = window.rfind(suf)
        if idx < 0:
            continue
        end = idx + len(suf)
        if end > best_end:
            best_end = end
    if best_end <= 0:
        return "", raw
    org = raw[:best_end].strip()
    rest = raw[best_end:].strip()
    if len(rest) < 4:
        return "", raw
    # org 至少 2 字符
    if len(org) < 2:
        return "", raw
    return org, rest


def attach_name_normalization(method: dict) -> dict:
    """在 method dict 上附加 raw_method_name / normalized_method_name /
    source_organization. 若拆不出机构, 三者仍写入 (org 为 "").

    修改后 external_stub_id 需要基于 normalized_name 重算 (由调用方负责).
    """
    raw = method.get("name") or method.get("method_name") or ""
    method.setdefault("raw_method_name", raw)
    org, normalized = normalize_patent_method_name(raw)
    method["source_organization"] = org
    method["normalized_method_name"] = normalized
    return method


# ============================================================
# spec 七: 孤立通用方法名降级
# ============================================================

# 孤立的通用工艺名 (完全等于, 或仅以 "法"/"方法"结尾) → 需要对象/材料信号才能 accepted.
_BARE_GENERIC_NAMES = {
    "水热合成法", "水热法",
    "溶胶-凝胶法", "溶胶凝胶法", "溶胶凝胶", "溶胶-凝胶",
    "模板法", "硬模板法", "软模板法",
    "热处理法", "热处理",
    "煅烧法", "焙烧法",
    "共沉淀法",
    "水热合成", "水热工艺",
    "机械球磨法", "球磨法",
}

# 若名字/证据里出现这些对象/材料/结构信号, 表明并非孤立通用名.
_CONCRETE_SIGNALS = (
    # 具体对象/结构
    "纳米片", "纳米线", "纳米棒", "纳米颗粒", "纳米阵列",
    "微球", "介孔", "薄膜", "阵列", "多孔",
    "空心球", "核壳", "复合材料", "复合物",
    # 具体材料
    "MnO2", "Fe2O3", "CoFe2O4", "LiFePO4", "TiO2", "V2O5",
    "钙钛矿", "石墨烯", "碳纳米管", "MOF", "COF",
    # 目标结构 / 应用
    "电极", "隔膜", "电解质", "电解液", "储热材料",
    "催化剂", "催化材料", "相变材料",
    # 制备目标 (制备 xx / 合成 xx / 用于 xx)
    "制备 ", "合成 ", "用于",
)


def is_bare_generic_method_name(name: str) -> bool:
    """名字本身是否是孤立通用工艺名 (无对象限定)."""
    if not name:
        return False
    stripped = name.strip()
    if stripped in _BARE_GENERIC_NAMES:
        return True
    # 也覆盖 "法" 前无对象只有工艺名的情形
    return False


def has_concrete_signal(text: str) -> bool:
    """text 里是否含具体对象/材料/结构信号."""
    if not text:
        return False
    return any(sig in text for sig in _CONCRETE_SIGNALS)


def should_demote_bare_generic(method: dict) -> bool:
    """判断一条 method 是否属于 "孤立通用名, 无对象" 需要降级的场景.

    条件:
      - name 本身是孤立通用名 (在 _BARE_GENERIC_NAMES 中);
      - 且 name 与 evidence_text 都不含具体对象/材料/结构信号.
    """
    name = method.get("name") or method.get("method_name") or ""
    if not is_bare_generic_method_name(name):
        return False
    ev = method.get("evidence_text") or ""
    problem = method.get("problem_solved") or ""
    return not (has_concrete_signal(name)
                  or has_concrete_signal(ev)
                  or has_concrete_signal(problem))


def demote_bare_generic_methods(methods: list) -> tuple:
    """把 accepted 里的孤立通用方法降为 candidate.

    Returns:
      (new_methods_list, demoted_count) — 修改后的列表 + 降级数.
    """
    demoted = 0
    out = []
    for m in methods:
        if (m.get("validation_status") == "accepted"
                and should_demote_bare_generic(m)):
            m = dict(m)
            m["validation_status"] = "candidate"
            m["validation_reason"] = ("demoted_bare_generic_name"
                                        f" (was: {m.get('validation_reason','')})")
            demoted += 1
        out.append(m)
    return out, demoted
