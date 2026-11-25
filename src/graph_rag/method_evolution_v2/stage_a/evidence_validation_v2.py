"""Stage A v2.1 - 放宽本地充分性判定 (spec 一/三/四).

对上一版 (evidence_validation.py) 的问题:
  - 过度依赖具体"数值参数" (温度 / 浓度 / 流速)
  - 章节位置(introduction/abstract)自动降级 candidate
  - 忽略了"命名工艺 + 明确对象"的强信号

修正后的判定 (spec 一):
  一个方法**不要求包含**具体浓度/温度/流速数值.
  满足以下之一即视为**具体方法**:
    1. 命名工艺(溶胶-凝胶法/水热法/分步水热...) + 明确对象
    2. 明确调控动作(调控/优化/掺杂...) + 明确目标
    3. 明确模型/仿真方法(分子动力学/CFD/有限元/DFT) + 明确研究对象
    4. 结构设计/系统设计/控制策略 + 名称
    5. 综述中"作者/[N] + 具体材料/工艺/结构/技术路线"

仍然拒绝 (spec 二):
  - 单纯材料名 / 性能指标 / 表征手段 / 命名法 / 分类法
  - "受到关注/前景/性能优异" 类宽泛描述
  - 只有研究对象无技术动作
  - 只有"采用某方法"无对象/目的
  - evidence sentence ID 不存在

章节位置 (spec 三):
  - 只作辅助风险信号, 不单独降级
  - own 出现在 abstract/introduction, 只要 evidence 明写"本文提出/建立/采用/构建"具体方法 → 可 accepted
  - review referenced 出现在正文/introduction, 只要有作者/引用线索 + 具体技术方案 → 可 accepted
"""
from __future__ import annotations

import re


# spec 一: 版本锁, 用于 full_runner input_manifest 的 3-way resume 判定
EVIDENCE_VALIDATION_VERSION = "v2.1_relaxed_2026-07-01"

from method_evolution_v2.stage_a.evidence_validation import (
    name_is_noninfo,
    name_looks_like_material_only,
    name_looks_like_characterization,
    name_looks_vague,      # noqa: F401 - kept for downstream use
)


# ============================================================
# Tier1: 强信号 (单独出现即算 sufficient, 若配合对象更好)
# 命名工艺 / 命名模型 / 命名结构 / 命名策略
# ============================================================

TIER1_NAMED_PROCESS = (
    # 制备工艺 (命名法)
    "溶胶-凝胶", "溶胶凝胶", "溶液燃烧法", "溶液燃烧",
    "水热法", "分步水热", "溶剂热", "熔融共混",
    "静电纺丝", "化学气相沉积", "cvd",
    "煅烧法", "碳化法", "热解法", "沉积法",
    "喷雾热解", "固相反应法", "稀溶液法", "原位生长",
    "液相还原", "回流法", "还原法", "水浴法",
    "电沉积", "电化学沉积", "水解法",
    "溶剂蒸发", "冻干法", "冷冻干燥",
    "浸渍法", "浸渍-煅烧", "共沉淀",
    "涂覆", "涂布", "喷涂",
    "改性制备", "熔融共混",
    "球磨法", "球磨",
    "自组装", "模板法", "软模板", "硬模板",
    # 命名模型 / 仿真
    "分子动力学", "分子动力学模拟",
    "第一性原理", "密度泛函", "dft",
    "cfd", "有限元", "数值模拟", "数值仿真",
    "aspen hysys", "aspen plus",
    "蒙特卡罗", "蒙特卡洛",
    "多孔介质模型", "湍流模型", "k-ε 模型", "两相流模型",
    # 控制/优化命名策略
    "mpc", "pid",
    "遗传算法", "粒子群", "nsga",
    # 命名结构设计
    "梯级蓄冷", "翅片强化",
    "共格结构", "异质结",
)

# ============================================================
# Tier2: 动作动词 (需配合对象才算 sufficient)
# ============================================================

TIER2_ACTION_VERBS = (
    # 制备/合成动作
    "制备", "合成", "构建", "建立", "设计", "开发", "搭建", "提出",
    "构筑", "组装", "编织",
    # 改性/调控
    "改性", "修饰", "掺杂", "调控", "优化", "调节", "调整",
    "增强", "强化", "稳定化",
    # 生长/沉积
    "生长", "沉积", "涂覆", "包覆",
    # 处理
    "煅烧", "碳化", "热解", "焙烧", "水解",
    # 仿真/建模
    "模拟", "仿真", "计算", "推导",
    # 系统设计
    "集成", "耦合", "串联",
)

# ============================================================
# Tier3: 具体对象 (材料/结构/系统/单元 + 明确目标)
# ============================================================

TIER3_CONCRETE_OBJECTS = (
    # 材料
    "电极", "正极", "负极", "阳极", "阴极", "电极材料",
    "电解液", "电解质", "隔膜", "离子选择膜", "离子交换膜",
    "相变材料", "pcm", "复合相变", "储热材料", "储氢材料",
    "催化剂", "载体", "前驱体",
    "纳米材料", "复合材料", "多孔碳", "多孔材料", "多孔电极",
    "介孔", "微孔",
    "颗粒", "薄膜", "纳米线", "纳米管", "纳米片", "纳米颗粒",
    "氧化物", "硫化物", "碳化物", "氮化物", "氢氧化物",
    # 结构
    "阵列", "异质结", "复合结构", "多孔结构", "核壳",
    "储热器", "储能器", "换热器", "反应器",
    "电堆", "电池", "电容器", "液流框",
    "流场", "管路", "储气室",
    # 单元
    "储能单元", "储热单元", "换热单元",
    # 系统/流程
    "系统", "流程", "循环", "回路",
    "蓄冷", "储放热",
    # 关键性能属性 (作为 target 与 action 配)
    "粒径", "晶粒", "空位",
    "微观结构", "晶体结构", "介孔结构",
)

# ============================================================
# 排除关键词 (即使有 tier2/tier3 也拒绝)
# ============================================================

# 命名法 / 分类法 → 硬拒
NAMING_OR_CLASSIFICATION = (
    "命名法", "命名规则", "分类法", "分类规则", "定义法",
    "术语",
)

# 表征仪器/手段 (专用词) → 硬拒
CHARACTERIZATION_INSTRUMENTS = (
    "毛细管流变仪", "旋转流变仪", "流变仪",
    "扫描电镜", "透射电镜",
    "热重分析仪", "差示扫描量热仪",
    "紫外可见分光光度计",
)

# 弱信号 (广泛存在, 若只有它们视为不充分)
WEAK_ONLY_SIGNALS = (
    "受到关注", "受到广泛关注", "引起了关注", "引起了广泛关注",
    "具有前景", "具有广阔的应用前景", "被广泛研究",
    "已被广泛研究", "得到广泛研究",
    "有望", "是一种", "作为一种",
    "得到了发展",
    # 只描述性能不算支撑
    "性能优异", "性能良好", "性能提高", "性能提升", "效率提高",
)

# 需要具体研究对象/技术方案的动词, 只有它们(无对象)时不算方法
STUDY_ONLY_VERBS = (
    "研究", "分析", "考察", "评估", "测试", "评价",
)


# ============================================================
# 辅助
# ============================================================

def _lower(s: str) -> str:
    return (s or "").lower()


def _contains_any(text: str, kws) -> list:
    tl = _lower(text)
    return [k for k in kws if k.lower() in tl]


# ============================================================
# 主判定
# ============================================================

def check_evidence_sufficiency_v2(evidence_text: str,
                                    method_name: str = "",
                                    kind: str = "") -> dict:
    """v2 充分性判定, 综合 evidence + method_name 两处.

    Args:
      evidence_text: 从 sentence_ids 拼出的 evidence
      method_name:   LLM 输出的方法名
      kind:          'own' | 'referenced' (referenced 有更宽松的规则)
    """
    combined = (evidence_text or "") + " || " + (method_name or "")
    if not combined.strip():
        return {"sufficient": False,
                "concrete_signal_hits": [], "weak_only_signal_hits": [],
                "reason": "empty"}

    # 硬拒: 命名法 / 分类法
    if _contains_any(method_name, NAMING_OR_CLASSIFICATION):
        return {"sufficient": False,
                "concrete_signal_hits": [], "weak_only_signal_hits": [],
                "reason": "naming_or_classification",
                "hits": _contains_any(method_name, NAMING_OR_CLASSIFICATION)}

    # 硬拒: 表征仪器为主 (name 里出现且没有非表征动作)
    charac_hits = _contains_any(method_name, CHARACTERIZATION_INSTRUMENTS)
    if charac_hits:
        # 若还有 tier1 强信号(如 CFD/分子动力学), 保留;
        # 否则视为表征
        if not _contains_any(combined, TIER1_NAMED_PROCESS):
            return {"sufficient": False,
                    "concrete_signal_hits": [], "weak_only_signal_hits": [],
                    "reason": "characterization_instrument_only",
                    "hits": charac_hits}

    # 只是引用编号
    stripped = re.sub(r"[\s\[\]()（）,，、.。]", "", evidence_text or "")
    if evidence_text and re.fullmatch(r"[\d,\-\s]+", stripped or ""):
        return {"sufficient": False,
                "concrete_signal_hits": [], "weak_only_signal_hits": [],
                "reason": "only_citation_numbers"}

    # 只是材料名短词 (name 短且是化学式类)
    if method_name and len(method_name) <= 10 \
            and name_looks_like_material_only(method_name):
        return {"sufficient": False,
                "concrete_signal_hits": [], "weak_only_signal_hits": [],
                "reason": "pure_material_name"}

    # ---- 命中分层 ----
    tier1 = _contains_any(combined, TIER1_NAMED_PROCESS)
    tier2 = _contains_any(combined, TIER2_ACTION_VERBS)
    tier3 = _contains_any(combined, TIER3_CONCRETE_OBJECTS)
    weak = _contains_any(combined, WEAK_ONLY_SIGNALS)
    study_only = _contains_any(combined, STUDY_ONLY_VERBS)

    # Rule A: Tier1 命中 (命名工艺/模型/结构等) → sufficient
    #        (即便对象不很清晰也认为足够, 因为工艺名本身就是方法)
    if tier1:
        return {"sufficient": True,
                "reason": "tier1_named_process_or_model",
                "concrete_signal_hits": (tier1 + tier2 + tier3)[:8],
                "weak_only_signal_hits": weak[:4]}

    # Rule B: Tier2 (动作动词) + Tier3 (具体对象) 都命中 → sufficient
    if tier2 and tier3:
        return {"sufficient": True,
                "reason": "action_verb_plus_object",
                "concrete_signal_hits": (tier2 + tier3)[:8],
                "weak_only_signal_hits": weak[:4]}

    # Rule C: referenced + 有引用编号/作者痕迹 + 有 Tier2 或 Tier3 → sufficient
    #        综述里描述前人方法, 只有"作者[N]…材料/工艺"就够
    if kind == "referenced":
        has_ref = bool(re.search(r"\[\d+", evidence_text or "")) or \
                  bool(re.search(r"等\s*\[", (evidence_text or "") + method_name)) or \
                  bool(re.search(r"[a-zA-Z]{3,}\s*等", method_name))
        if has_ref and (tier2 or tier3):
            return {"sufficient": True,
                    "reason": "referenced_with_citation_and_action_or_object",
                    "concrete_signal_hits": (tier2 + tier3)[:8],
                    "weak_only_signal_hits": weak[:4]}

    # Rule D: 只有"研究/分析"动词 + tier3 对象 → 不算方法 (是研究行为)
    if study_only and tier3 and not tier2:
        return {"sufficient": False,
                "concrete_signal_hits": tier3[:6],
                "weak_only_signal_hits": weak[:4],
                "reason": "study_verb_without_method_action",
                "study_verbs": study_only[:3]}

    # Rule E: 只有对象无动作 → 不足
    if tier3 and not tier2:
        return {"sufficient": False,
                "concrete_signal_hits": tier3[:6],
                "weak_only_signal_hits": weak[:4],
                "reason": "object_without_action"}

    # Rule F: 只有动作无对象 (太空泛)
    if tier2 and not tier3:
        return {"sufficient": False,
                "concrete_signal_hits": tier2[:6],
                "weak_only_signal_hits": weak[:4],
                "reason": "action_without_specific_object"}

    # Rule G: 只有弱信号
    if weak and not (tier1 or tier2 or tier3):
        return {"sufficient": False,
                "concrete_signal_hits": [],
                "weak_only_signal_hits": weak[:6],
                "reason": "only_weak_or_generic_signals"}

    return {"sufficient": False,
            "concrete_signal_hits": [], "weak_only_signal_hits": weak[:4],
            "reason": "no_concrete_method_signal"}


# ============================================================
# v2 章节位置规则 (spec 三 放宽)
# ============================================================

OWN_METHOD_CORE_SECTIONS = frozenset((
    "methods", "results", "results_discussion", "discussion",
    "theory_model", "system_design", "simulation_calculation",
    "case_analysis", "conclusion",
))

# own 出现在 abstract/intro 但含以下"本文自陈"语句时, 视同核心章节
OWN_DECLARATIVE_PHRASES = (
    "本文提出", "本文建立", "本文采用", "本文构建", "本文设计",
    "本文制备", "本文改性", "本文开发",
    "本工作提出", "本工作构建", "本工作建立",
    "本研究提出", "本研究建立", "本研究采用", "本研究通过",
    "提出了一种", "建立了", "构建了", "设计了", "制备了",
    "开发了", "搭建了",
)

REFERENCED_ALLOWED_SECTIONS_V2 = frozenset((
    "methods", "results", "results_discussion", "discussion",
    "theory_model", "system_design", "simulation_calculation",
    "case_analysis", "conclusion",
    "introduction", "abstract",
    "other_sections", "patent_analysis",
))


def check_section_context_v2(kind: str,
                                section_types_used: set,
                                evidence_text: str) -> tuple:
    """v2 章节位置检查. 章节不足单独降级, 仅在其他信号都缺时才降 candidate.

    Returns:
      (section_ok: bool, note: str)
    """
    section_types_used = set(section_types_used)
    if kind == "own":
        if section_types_used & OWN_METHOD_CORE_SECTIONS:
            return True, "core_section_hit"
        # abstract / introduction only — 看是否有 "本文提出" 声明
        if any(p in (evidence_text or "") for p in OWN_DECLARATIVE_PHRASES):
            return True, "abstract_or_intro_with_declarative_phrase"
        return False, f"own_method_in_non_core_sections_without_declarative:{sorted(section_types_used)}"
    else:   # referenced
        if section_types_used & REFERENCED_ALLOWED_SECTIONS_V2:
            return True, "referenced_in_allowed_section"
        return False, f"referenced_in_unusual_section:{sorted(section_types_used)}"


# ============================================================
# v2 resolver (完整) - 与 v1 保持字段布局兼容
# ============================================================

from method_evolution_v2.stage_a.evidence_validation import (
    _normalize_name as _v1_normalize_name,
)


def _resolve_evidence_by_ids(sids: list, sentence_index: dict) -> tuple:
    """与 v1 一样的合并逻辑, 但独立成函数便于 v2 使用."""
    if not sids:
        return [], [], "", -1, -1, "", ""
    found, missing = [], []
    for sid in sids:
        s = sentence_index.get(sid)
        if s is None:
            missing.append(sid)
        else:
            found.append(s)
    if not found:
        return [], missing, "", -1, -1, "", ""
    found_sorted = sorted(found, key=lambda x: (x["char_start"], x["char_end"]))
    spans = []
    cur = None
    for s in found_sorted:
        if cur is None:
            cur = {"char_start": s["char_start"], "char_end": s["char_end"],
                   "text": s["sentence_text"],
                   "section_type": s["section_type"],
                   "section_name": s["section_name"],
                   "para_id": s["para_id"],
                   "sentence_ids": [s["sentence_id"]]}
            continue
        if s["para_id"] == cur["para_id"] and s["char_start"] == cur["char_end"]:
            cur["char_end"] = s["char_end"]
            cur["text"] += s["sentence_text"]
            cur["sentence_ids"].append(s["sentence_id"])
        else:
            spans.append(cur)
            cur = {"char_start": s["char_start"], "char_end": s["char_end"],
                   "text": s["sentence_text"],
                   "section_type": s["section_type"],
                   "section_name": s["section_name"],
                   "para_id": s["para_id"],
                   "sentence_ids": [s["sentence_id"]]}
    if cur:
        spans.append(cur)
    if len(spans) == 1:
        quote = spans[0]["text"]
        cs, ce = spans[0]["char_start"], spans[0]["char_end"]
        sec = spans[0]["section_name"] or spans[0]["section_type"]
        pid = spans[0]["para_id"]
    else:
        quote = " ".join(s["text"] for s in spans)
        cs = min(s["char_start"] for s in spans)
        ce = max(s["char_end"] for s in spans)
        main = max(spans, key=lambda x: x["char_end"] - x["char_start"])
        sec = main["section_name"] or main["section_type"]
        pid = main["para_id"]
    return spans, missing, quote, cs, ce, sec, pid


def resolve_method_by_sentence_ids_v2(raw: dict,
                                        sentence_index: dict,
                                        kind: str,
                                        paper_type: str = "") -> dict:
    """v2 单条方法分级 (放宽后).

    与 v1 输出字段完全一致 (含 name/method_type/problem_solved/key_components/
    evidence_quote/evidence_section/evidence_para_id/evidence_char_start/end/
    evidence_match_status/evidence_sentence_ids/evidence_missing_ids/
    evidence_spans/evidence_sufficiency/citation_clue/confidence_llm/kind/
    validation_status/rejected_reason)
    以便与 test_run_03 / batch_1 已有的 CSV/JSON 结构无缝换.
    """
    name = (raw.get("name") or "").strip()
    ids_in = raw.get("evidence_sentence_ids") or []
    if not isinstance(ids_in, list):
        ids_in = []
    ids_in = [str(x).strip() for x in ids_in if str(x).strip()]
    reasons = []

    # ---- name 合法性 (硬性拒绝这些) ----
    if not name:
        reasons.append("missing_name")
    else:
        if name_is_noninfo(name):
            reasons.append("noninfo_name")
        if name_looks_like_characterization(name):
            reasons.append("looks_like_characterization")
        # v2 放宽: 材料名 / 宽泛 只作为一层过滤, 由 sufficiency 里再看

    # ---- 存在性 ----
    if not ids_in:
        reasons.append("no_evidence_ids")
    found_sentences, missing_ids = [], []
    for sid in ids_in:
        s = sentence_index.get(sid)
        if s is None:
            missing_ids.append(sid)
        else:
            found_sentences.append(s)
    if ids_in and missing_ids and not found_sentences:
        reasons.append("all_evidence_ids_missing")
    if ids_in and missing_ids and found_sentences:
        reasons.append("partial_evidence_ids_missing")

    spans, missing2, quote, cs, ce, sec, para_id = _resolve_evidence_by_ids(
        ids_in, sentence_index)

    # ---- v2 sufficiency ----
    suff = check_evidence_sufficiency_v2(quote, name, kind)

    # ---- v2 章节位置 ----
    section_types_used = {s["section_type"] for s in found_sentences}
    section_ok, section_note = check_section_context_v2(
        kind, section_types_used, quote)

    # ---- 决策 ----
    # 硬拒
    HARD_REJECT = ("missing_name", "noninfo_name", "looks_like_characterization",
                    "no_evidence_ids", "all_evidence_ids_missing")
    hard = any(r in reasons for r in HARD_REJECT)

    if hard:
        status = "rejected"
    elif not suff["sufficient"]:
        # 不充分 → candidate (标注原因)
        status = "candidate"
        reasons.append(f"insufficient_evidence:{suff['reason']}")
    elif not section_ok:
        # 充分但章节位置弱 → candidate
        status = "candidate"
        reasons.append(f"weak_section_context:{section_note}")
    elif "partial_evidence_ids_missing" in reasons:
        # 证据部分缺失, 但内容足够 → candidate
        status = "candidate"
    else:
        status = "accepted"

    return {
        "name": name,
        "normalized_name": _v1_normalize_name(name),
        "method_type": (raw.get("proposed_method_type")
                          or raw.get("method_type") or "other").strip() or "other",
        "problem_solved": (raw.get("problem_solved") or "").strip(),
        "key_components": raw.get("key_components") or [],
        "evidence_quote": quote,
        "evidence_section": sec,
        "evidence_para_id": para_id,
        "evidence_char_start": cs,
        "evidence_char_end": ce,
        "evidence_match_status": "sentence_id_exact" if (found_sentences and not missing_ids) else (
            "partial_ids_missing" if (found_sentences and missing_ids) else "no_ids"
        ),
        "evidence_sentence_ids": ids_in,
        "evidence_missing_ids": missing_ids,
        "evidence_spans": spans,
        "evidence_sufficiency": suff,
        "citation_clue": (raw.get("citation_clue") or "").strip(),
        "confidence_llm": (raw.get("confidence_llm") or "medium").strip(),
        "kind": kind,
        "validation_status": status,
        "rejected_reason": ",".join(reasons),
    }
