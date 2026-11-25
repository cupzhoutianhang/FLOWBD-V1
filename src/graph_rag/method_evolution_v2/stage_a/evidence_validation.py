"""Stage A 证据校验(本地, 无 LLM).

v1 (旧协议): 校验 LLM 抄写的 evidence_quote 是否在原文中定位.
v2 (本轮 spec 二~五): LLM 只返回 evidence_sentence_ids;
  代码通过 sentence 索引:
    1. 校验 ID 全部存在(存在性)
    2. 从索引里取原文 -> 自动生成 evidence_quote / evidence_spans
    3. 独立跑"证据充分性"检查(存在性 ≠ 充分性)
    4. 冒 fail 就 rejected; 支撑力弱就 candidate; 全通过才 accepted

保留 v1 的工具函数(name_looks_like_material_only 等) 供 v2 复用.
"""
from __future__ import annotations

import re
import unicodedata


MIN_EVIDENCE_CHARS = 20   # v1 语义: LLM 抄写的 evidence 长度; v2 已不用

# 无信息名: 命中即拒
NONINFO_NAME_PATTERNS = [
    re.compile(r"^(本|该|所提|所述|上述|前述|下述)?方法$"),
    re.compile(r"^方法\d?$"),
    re.compile(r"^本(研究|工作|课题|文)?方法$"),
    re.compile(r"^本(研究|工作|课题|文)$"),
    re.compile(r"^Method\s*\d*$", re.IGNORECASE),
    re.compile(r"^Our\s+Method$", re.IGNORECASE),
]

# 疑似材料名 (排除): 短且形如化学式/单一材料词
SUSPECT_MATERIAL_PATTERNS = [
    re.compile(r"^[A-Z][a-zA-Z0-9]{1,4}(?:O|N|S|C)?\d*$"),   # NCM / LFP / LiFePO4 / MnO2
    re.compile(r"^[A-Za-z0-9]{1,6}$"),                        # 3-6 char pure ascii
    re.compile(r"^(锂|钠|钾|钙|镁|铝|锌|铁|铜|镍|钴|锰|钒)(离子)?电池$"),
    re.compile(r"^(石蜡|水合盐|锂离子|钠离子|多孔碳|生物质炭|MOF|MOFs)$"),
]

# 疑似表征手段 (排除)
SUSPECT_CHARACTERIZATION_PATTERNS = [
    re.compile(r"^(XRD|SEM|TEM|XPS|BET|FTIR|Raman|EDS|EDX|TGA|DSC|CV|EIS)"
               r"(\s*(表征|测试|测量|分析))?$", re.IGNORECASE),
    re.compile(r"^(密度泛函|DFT|分子动力学|MD)(\s*(计算|模拟))?$", re.IGNORECASE),
]

# 宽泛概念 (排除)
SUSPECT_VAGUE_PATTERNS = [
    re.compile(r"^(提高|提升|改进|改善|增强|优化)(性能|效率|结构|材料)?$"),
    re.compile(r"^(结构|材料|工艺|系统|方案)(设计|优化|改进|研究)?$"),
    re.compile(r"^(储能|储热|储氢)(技术|方案|方法)?$"),
]


def _normalize_for_match(s: str) -> str:
    """归一化: 剥去连续空白 + 中英文标点差异, 用于 normalized_exact 匹配."""
    if not s:
        return ""
    # NFKC 归一 (全角/半角)
    s = unicodedata.normalize("NFKC", s)
    # 中英标点大致互换 (保留最松的允许集)
    s = s.translate(str.maketrans({
        "，": ",", "。": ".", "；": ";", "：": ":",
        "（": "(", "）": ")", "【": "[", "】": "]",
        "《": "<", "》": ">", "、": ",", "！": "!",
        "？": "?", "—": "-", "–": "-",
        "“": '"', "”": '"',
    }))
    # spec 四.3: 完全剥掉所有空白 (含 CJK 全角空格 / nbsp), 只保留可视字符
    import re as _re
    s = _re.sub(r"\s+", "", s)
    return s.lower()


def _locate_exact(evidence: str, full_text: str) -> tuple:
    """(idx, end) or (-1, -1) — 原文精确定位."""
    if not evidence or not full_text:
        return -1, -1
    idx = full_text.find(evidence)
    if idx < 0:
        return -1, -1
    return idx, idx + len(evidence)


def _locate_normalized(evidence: str, full_text: str) -> tuple:
    """归一化后模糊定位; 返回归一后的 (idx, end) 供 status 报告用.
    注意: 这里返回的是**归一化坐标**, 不能直接切原文; 若命中, 视为 normalized_exact.
    """
    ne = _normalize_for_match(evidence)
    nf = _normalize_for_match(full_text)
    if not ne or not nf:
        return -1, -1
    idx = nf.find(ne)
    if idx < 0:
        return -1, -1
    return idx, idx + len(ne)


def name_is_noninfo(name: str) -> bool:
    if not name or not name.strip():
        return True
    s = name.strip()
    return any(p.match(s) for p in NONINFO_NAME_PATTERNS)


def name_looks_like_material_only(name: str) -> bool:
    """启发式判定: 疑似材料名(不算方法)."""
    if not name:
        return False
    s = name.strip()
    if len(s) <= 8 and any(p.match(s) for p in SUSPECT_MATERIAL_PATTERNS):
        return True
    return False


def name_looks_like_characterization(name: str) -> bool:
    if not name:
        return False
    s = name.strip()
    return any(p.match(s) for p in SUSPECT_CHARACTERIZATION_PATTERNS)


def name_looks_vague(name: str) -> bool:
    if not name:
        return False
    s = name.strip()
    return any(p.match(s) for p in SUSPECT_VAGUE_PATTERNS)


def validate_evidence(evidence_quote: str, sections: list) -> dict:
    """在整篇 sections(list[Section-like dict]) 内定位 evidence_quote.

    Args:
      evidence_quote: LLM 输出的证据文本
      sections: list of section dicts, each with 'char_start', 'char_end', 'paragraphs',
                and 'raw_heading'. paragraphs are dicts with 'char_start'/'char_end'/'text'/'para_id'.

    Returns:
      {
        "match_status": "exact" | "normalized_exact" | "not_found",
        "char_start": int,
        "char_end": int,
        "para_id": str,   # 命中所在的 para_id, 找不到则空
        "section_heading": str,
      }
    """
    if not evidence_quote or not sections:
        return {"match_status": "not_found", "char_start": -1, "char_end": -1,
                "para_id": "", "section_heading": ""}

    # 拼接全文, 保留 char offsets
    # section.char_start/end 已经是全局绝对偏移; para 亦然
    # 因此可以拼一份"参考全文"用于粗匹配
    # 但为拿回原文全局 offset, 我们对每个 paragraph 各做一次精确匹配
    for sec in sections:
        for p in sec.get("paragraphs", []) or []:
            text = p.get("text", "") or ""
            if not text:
                continue
            idx = text.find(evidence_quote)
            if idx >= 0:
                abs_start = p.get("char_start", 0) + idx
                abs_end = abs_start + len(evidence_quote)
                return {
                    "match_status": "exact",
                    "char_start": abs_start,
                    "char_end": abs_end,
                    "para_id": p.get("para_id", ""),
                    "section_heading": sec.get("raw_heading", ""),
                }

    # 归一化匹配 — 仅逐段判断"是否含", 不返回精确 offset (归一化会破坏偏移)
    ne = _normalize_for_match(evidence_quote)
    if not ne:
        return {"match_status": "not_found", "char_start": -1, "char_end": -1,
                "para_id": "", "section_heading": ""}
    for sec in sections:
        for p in sec.get("paragraphs", []) or []:
            text = p.get("text", "") or ""
            if not text:
                continue
            if _normalize_for_match(text).find(ne) >= 0:
                # 报告段落级 offset, 但明确标 normalized_exact (证据无法精准切回)
                return {
                    "match_status": "normalized_exact",
                    "char_start": p.get("char_start", -1),
                    "char_end": p.get("char_end", -1),
                    "para_id": p.get("para_id", ""),
                    "section_heading": sec.get("raw_heading", ""),
                }
    return {"match_status": "not_found", "char_start": -1, "char_end": -1,
            "para_id": "", "section_heading": ""}


def slice_back_check(text: str, char_start: int, char_end: int, expected: str) -> bool:
    """spec 四.5: char_start/end 必须切片回原文一致.

    Args:
      text: 全篇原文 (source_md_chars 长的字符串)
    """
    if not text or char_start < 0 or char_end < 0 or char_end <= char_start:
        return False
    if char_end > len(text):
        return False
    slice_ = text[char_start:char_end]
    return slice_ == expected


REJECT_REASONS = {
    "missing_name": "方法 name 缺失或空",
    "noninfo_name": "方法 name 是 '本方法/该方法' 类无信息词",
    "looks_like_material_only": "name 疑似材料名, 不构成方法",
    "looks_like_characterization": "name 是普通表征手段 (XRD/SEM/DFT 等)",
    "looks_vague": "name 是宽泛概念, 无具体技术路径",
    "evidence_too_short": f"evidence_quote 长度 < {MIN_EVIDENCE_CHARS} 字",
    "evidence_missing": "evidence_quote 缺失或空",
    "evidence_not_locatable": "evidence_quote 在原文中定位失败",
    "duplicate_method": "已存在同名或高度相似方法且证据更完整",
}


def classify_method(raw: dict, sections: list) -> dict:
    """对一条 LLM 输出的 method dict 打校验状态.

    Returns:
      {
        # 原字段透传:
        "name": ..., "method_type": ..., "problem_solved": ..., "key_components": [...],
        "evidence_quote": ..., "evidence_section": ..., "citation_clue": ...,
        "confidence_llm": ...,
        # 新增字段:
        "normalized_name": <name 去空白/换行后>,
        "evidence_match_status": "exact" | "normalized_exact" | "not_found",
        "evidence_para_id": ..., "evidence_char_start": ..., "evidence_char_end": ...,
        "validation_status": "accepted" | "candidate" | "rejected",
        "rejected_reason": <逗号分隔 REJECT_REASONS 键或空>,
      }
    """
    name = (raw.get("name") or "").strip()
    evidence = (raw.get("evidence_quote") or "").strip()

    reasons = []
    if not name:
        reasons.append("missing_name")
    else:
        if name_is_noninfo(name):
            reasons.append("noninfo_name")
        if name_looks_like_material_only(name):
            reasons.append("looks_like_material_only")
        if name_looks_like_characterization(name):
            reasons.append("looks_like_characterization")
        if name_looks_vague(name):
            reasons.append("looks_vague")

    if not evidence:
        reasons.append("evidence_missing")
    elif len(evidence) < MIN_EVIDENCE_CHARS:
        reasons.append("evidence_too_short")

    # 尝试定位 evidence (即使 name 有问题也定位, 便于后续人工审)
    loc = validate_evidence(evidence, sections) if evidence else {
        "match_status": "not_found", "char_start": -1, "char_end": -1,
        "para_id": "", "section_heading": "",
    }
    if evidence and loc["match_status"] == "not_found":
        reasons.append("evidence_not_locatable")

    # 决策:
    #   - 有任何 reject reason → rejected
    #   - evidence 是 normalized_exact 但 name/长度都过 → candidate (可疑证据)
    #   - 全部通过且 exact 匹配 → accepted
    if reasons:
        status = "rejected"
    elif loc["match_status"] == "normalized_exact":
        status = "candidate"
    else:  # exact
        status = "accepted"

    return {
        "name": name,
        "normalized_name": _normalize_name(name),
        "method_type": (raw.get("method_type") or "other").strip() or "other",
        "problem_solved": (raw.get("problem_solved") or "").strip(),
        "key_components": raw.get("key_components") or [],
        "evidence_quote": evidence,
        "evidence_section": (raw.get("evidence_section") or loc["section_heading"]).strip(),
        "evidence_para_id": loc["para_id"],
        "evidence_char_start": loc["char_start"],
        "evidence_char_end": loc["char_end"],
        "evidence_match_status": loc["match_status"],
        "citation_clue": (raw.get("citation_clue") or "").strip(),
        "confidence_llm": (raw.get("confidence_llm") or "medium").strip(),
        "validation_status": status,
        "rejected_reason": ",".join(reasons),
    }


def _normalize_name(name: str) -> str:
    """归一 name 用于跨条目去重比较."""
    if not name:
        return ""
    s = unicodedata.normalize("NFKC", name)
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s


# ============================================================
# v2: 基于 sentence_id 的证据解析 + 独立充分性检查
# ============================================================

# 具体技术信号 (存在即通过充分性; 允许有 1 条即可)
CONCRETE_METHOD_SIGNALS = (
    # material_design
    "掺杂", "空位", "调控", "高熵", "组分设计", "结构工程", "缺陷工程",
    "阳离子空位", "阴离子空位", "键合", "杂化",
    # synthesis_process
    "制备", "合成", "溶胶", "凝胶", "水热", "溶剂热", "熔融共混",
    "静电纺丝", "化学气相沉积", "cvd", "煅烧", "碳化", "热解", "沉积",
    "干燥", "浸渍", "涂覆", "复合", "复配", "封装",
    # interface / electrode / electrolyte / membrane
    "界面工程", "涂层", "sei", "电极结构", "3d 电极", "三维电极",
    "电解液添加剂", "固态电解质", "离子交换膜", "离子选择膜", "隔膜",
    # device / system
    "装置设计", "反应器", "储热器", "储能器", "电堆", "换热器",
    "系统设计", "系统集成", "流程设计", "循环设计", "耦合系统",
    "流场", "结构优化设计",
    # model / simulation
    "数学模型", "动态模型", "有限元", "cfd", "数值模拟", "模型验证",
    "边界条件", "控制方程", "初始条件", "网格划分", "湍流模型",
    # control / optimization
    "控制策略", "mpc", "pid", "调度策略",
    "遗传算法", "粒子群", "nsga", "元启发式", "优化算法",
    # 通用有力动词
    "提出了一种", "本文提出", "本文构建", "本文建立", "本文设计",
)

# 弱信号 / 无支撑 (若证据只含这些, 不足以支撑方法)
WEAK_ONLY_SIGNALS = (
    "受到关注", "受到广泛关注", "引起了关注", "引起了广泛关注",
    "具有前景", "具有广阔的应用前景", "被广泛研究", "已被广泛研究",
    "有望", "是一种", "作为一种", "得到了发展",
    "已经", "得到广泛",
    # 只描述性能不算支撑
    "性能提高", "性能提升", "效率提高",
)


def check_evidence_sufficiency(evidence_text: str) -> dict:
    """独立充分性检查 (spec 五).

    存在性 (ID 可解析) 只证明可定位, 不证明它支持方法.
    本函数看证据文字里有没有具体技术信号.

    Returns:
      {
        "sufficient": bool,
        "concrete_signal_hits": [...],   # 命中的具体信号
        "weak_only_signal_hits": [...],  # 命中的弱信号
        "only_citation": bool,           # 只是 [数字] 引用编号
        "only_material_name": bool,      # 只是一个材料名
        "reason": "..."                  # 若 not sufficient, 说明为什么
      }
    """
    if not evidence_text or not evidence_text.strip():
        return {
            "sufficient": False,
            "concrete_signal_hits": [], "weak_only_signal_hits": [],
            "only_citation": False, "only_material_name": False,
            "reason": "empty_evidence",
        }

    txt_lower = evidence_text.lower()

    # 只是 "[数字]" / "([数字])" / "文献 15" 之类
    stripped = re.sub(r"[\s\[\]()（）,，、.。]", "", evidence_text)
    if re.fullmatch(r"[\d,\-\s]+", stripped):
        return {
            "sufficient": False,
            "concrete_signal_hits": [], "weak_only_signal_hits": [],
            "only_citation": True, "only_material_name": False,
            "reason": "only_citation_numbers",
        }

    # 只是一个材料名 (短且是化学式/单一材料词)
    txt_no_space = re.sub(r"\s+", "", evidence_text)
    if len(txt_no_space) <= 10 and name_looks_like_material_only(txt_no_space):
        return {
            "sufficient": False,
            "concrete_signal_hits": [], "weak_only_signal_hits": [],
            "only_citation": False, "only_material_name": True,
            "reason": "only_material_name",
        }

    concrete_hits = [k for k in CONCRETE_METHOD_SIGNALS if k.lower() in txt_lower]
    weak_hits = [k for k in WEAK_ONLY_SIGNALS if k.lower() in txt_lower]

    if concrete_hits:
        return {
            "sufficient": True,
            "concrete_signal_hits": concrete_hits[:6],
            "weak_only_signal_hits": weak_hits[:6],
            "only_citation": False, "only_material_name": False,
            "reason": "",
        }

    # 无 concrete_signal
    if weak_hits:
        return {
            "sufficient": False,
            "concrete_signal_hits": [],
            "weak_only_signal_hits": weak_hits[:6],
            "only_citation": False, "only_material_name": False,
            "reason": "only_weak_or_generic_signals",
        }

    # 无 concrete 也无 weak: 中性描述, 视为不充分 (保守)
    return {
        "sufficient": False,
        "concrete_signal_hits": [], "weak_only_signal_hits": [],
        "only_citation": False, "only_material_name": False,
        "reason": "no_concrete_method_signal",
    }


# own 方法优先章节 (spec 五)
OWN_METHOD_PREFERRED_SECTIONS = {
    "methods", "results", "results_discussion", "discussion",
    "theory_model", "system_design", "simulation_calculation",
    "case_analysis", "conclusion",
}
# review 中 referenced 方法可来自的章节 (更宽松)
REFERENCED_ALLOWED_SECTIONS = {
    "methods", "results", "results_discussion", "discussion",
    "theory_model", "system_design", "simulation_calculation",
    "case_analysis", "conclusion", "introduction", "other_sections",
    "abstract",
    # patent_analysis 章节里的 referenced 也保留
    "patent_analysis",
}


def _merge_contiguous_spans(sentences: list) -> list:
    """把命中的 sentence(list of dict) 合并成 evidence_spans:
    连续 (char_end == next.char_start) 的合成一段.
    每段 {char_start, char_end, text, section_type, section_name, para_id, sentence_ids}
    """
    if not sentences:
        return []
    # 按 char_start 排序
    ss = sorted(sentences, key=lambda s: (s["char_start"], s["char_end"]))
    out = []
    cur = None
    for s in ss:
        if cur is None:
            cur = {
                "char_start": s["char_start"],
                "char_end": s["char_end"],
                "text": s["sentence_text"],
                "section_type": s["section_type"],
                "section_name": s["section_name"],
                "para_id": s["para_id"],
                "sentence_ids": [s["sentence_id"]],
            }
            continue
        # 完全紧邻 (para 内 & offset 相接) 且同 para -> 合并
        if s["para_id"] == cur["para_id"] and s["char_start"] == cur["char_end"]:
            cur["char_end"] = s["char_end"]
            cur["text"] += s["sentence_text"]
            cur["sentence_ids"].append(s["sentence_id"])
        else:
            out.append(cur)
            cur = {
                "char_start": s["char_start"],
                "char_end": s["char_end"],
                "text": s["sentence_text"],
                "section_type": s["section_type"],
                "section_name": s["section_name"],
                "para_id": s["para_id"],
                "sentence_ids": [s["sentence_id"]],
            }
    if cur is not None:
        out.append(cur)
    return out


def resolve_method_by_sentence_ids(raw: dict, sentence_index: dict,
                                    kind: str, paper_type: str = "") -> dict:
    """v2 主校验: 用 LLM 返回的 evidence_sentence_ids 解析出 evidence, 再判 status.

    Args:
      raw: LLM 返回的 method dict (name/proposed_method_type/problem_solved/
           key_components/evidence_sentence_ids/citation_clue/confidence_llm)
      sentence_index: {sentence_id: Sentence dict} — 该论文的句子索引
      kind: "own" | "referenced"
      paper_type: "research_article" | "review_article" | "patent_analysis" | "unclear" | "non_storage"

    Returns:
      同 v1 classify_method 的字段布局(方便与旧 CSV 直接兼容), 但字段来源不同:
        - evidence_quote:  代码从 sentence 拼出来
        - evidence_char_start/end: 若单 span 则给 span 边界; 若多 span 则给整体 min/max
        - evidence_section: 主 span 的 section_name
        - evidence_para_id: 主 span 的 para_id
        - evidence_match_status: "sentence_id_exact" | "partial_ids_missing" | "no_ids"
        - validation_status: accepted | candidate | rejected
        - rejected_reason: 逗号分隔 REJECT_REASONS_V2 键
        - evidence_spans: 结构化多段 (spec 四.6)
        - evidence_sentence_ids: 原样透传
        - evidence_sufficiency: check_evidence_sufficiency 输出
    """
    name = (raw.get("name") or "").strip()
    ids_in = raw.get("evidence_sentence_ids") or []
    if not isinstance(ids_in, list):
        ids_in = []
    ids_in = [str(x).strip() for x in ids_in if str(x).strip()]
    reasons = []

    # ---- name 合法性 (复用 v1) ----
    if not name:
        reasons.append("missing_name")
    else:
        if name_is_noninfo(name):
            reasons.append("noninfo_name")
        if name_looks_like_material_only(name):
            reasons.append("looks_like_material_only")
        if name_looks_like_characterization(name):
            reasons.append("looks_like_characterization")
        if name_looks_vague(name):
            reasons.append("looks_vague")

    # ---- 存在性 ----
    if not ids_in:
        reasons.append("no_evidence_ids")
        return _build_v2_result(raw, name, kind, [], [],
                                 [], {"sufficient": False, "reason": "no_ids"},
                                 "no_ids", "rejected", reasons)

    found_sentences, missing_ids = [], []
    for sid in ids_in:
        s = sentence_index.get(sid)
        if s is None:
            missing_ids.append(sid)
        else:
            found_sentences.append(s)

    if missing_ids and not found_sentences:
        reasons.append("all_evidence_ids_missing")
        return _build_v2_result(raw, name, kind, ids_in, missing_ids,
                                 [], {"sufficient": False,
                                       "reason": "all_ids_missing"},
                                 "no_ids", "rejected", reasons)

    if missing_ids:
        # 部分 ID 不存在, 严格按 spec 四: rejected
        reasons.append("partial_evidence_ids_missing")
        # 但仍拼一份可用证据, 便于人工审
        spans = _merge_contiguous_spans(found_sentences)
        suff = check_evidence_sufficiency(_spans_text(spans))
        return _build_v2_result(raw, name, kind, ids_in, missing_ids,
                                 spans, suff, "partial_ids_missing",
                                 "rejected", reasons)

    # ---- 全部 ID 存在 ----
    spans = _merge_contiguous_spans(found_sentences)
    ev_text = _spans_text(spans)
    suff = check_evidence_sufficiency(ev_text)

    # 章节适配性检查
    section_types_used = {s["section_type"] for s in found_sentences}
    section_ok = True
    section_note = ""
    if kind == "own":
        # own 应优先来自 methods/results/model/system/conclusion
        if not (section_types_used & OWN_METHOD_PREFERRED_SECTIONS):
            section_ok = False
            section_note = ("own method 证据全部来自非核心章节 "
                            f"({sorted(section_types_used)})")
    else:  # referenced
        if not (section_types_used & REFERENCED_ALLOWED_SECTIONS):
            section_ok = False
            section_note = f"referenced 证据来自异常章节 ({sorted(section_types_used)})"

    # ---- 决策 ----
    if reasons:
        status = "rejected"
    elif not suff["sufficient"]:
        # 存在但不充分 → candidate
        status = "candidate"
        reasons.append(f"insufficient_evidence:{suff['reason']}")
    elif not section_ok:
        # 存在且充分, 但章节位置弱 → candidate
        status = "candidate"
        reasons.append(f"weak_section_context:{section_note}")
    else:
        status = "accepted"

    return _build_v2_result(raw, name, kind, ids_in, missing_ids,
                             spans, suff, "sentence_id_exact",
                             status, reasons)


def _spans_text(spans: list) -> str:
    return " ".join(s["text"] for s in spans)


def _build_v2_result(raw: dict, name: str, kind: str,
                      ids_in: list, missing_ids: list,
                      spans: list, sufficiency: dict,
                      match_status: str,
                      validation_status: str,
                      reasons: list) -> dict:
    # 合成 evidence_quote / char_start / char_end (对齐旧 CSV schema)
    if spans:
        # 若单 span: quote = span.text; 多 span: 用 ' ... ' 分隔
        if len(spans) == 1:
            evidence_quote = spans[0]["text"]
            char_start = spans[0]["char_start"]
            char_end = spans[0]["char_end"]
            evidence_section = spans[0]["section_name"] or spans[0]["section_type"]
            evidence_para_id = spans[0]["para_id"]
        else:
            evidence_quote = " ... ".join(s["text"] for s in spans)
            char_start = min(s["char_start"] for s in spans)
            char_end = max(s["char_end"] for s in spans)
            # 主 span 取最长
            main_span = max(spans, key=lambda x: x["char_end"] - x["char_start"])
            evidence_section = main_span["section_name"] or main_span["section_type"]
            evidence_para_id = main_span["para_id"]
    else:
        evidence_quote = ""
        char_start, char_end = -1, -1
        evidence_section = ""
        evidence_para_id = ""

    return {
        "name": name,
        "normalized_name": _normalize_name(name),
        "method_type": (raw.get("proposed_method_type")
                        or raw.get("method_type") or "other").strip() or "other",
        "problem_solved": (raw.get("problem_solved") or "").strip(),
        "key_components": raw.get("key_components") or [],
        "evidence_quote": evidence_quote,
        "evidence_section": evidence_section,
        "evidence_para_id": evidence_para_id,
        "evidence_char_start": char_start,
        "evidence_char_end": char_end,
        "evidence_match_status": match_status,
        "evidence_sentence_ids": ids_in,
        "evidence_missing_ids": missing_ids,
        "evidence_spans": spans,
        "evidence_sufficiency": sufficiency,
        "citation_clue": (raw.get("citation_clue") or "").strip(),
        "confidence_llm": (raw.get("confidence_llm") or "medium").strip(),
        "kind": kind,
        "validation_status": validation_status,
        "rejected_reason": ",".join(reasons),
    }


def dedupe_methods_prefer_longer_evidence(methods: list) -> list:
    """spec 四.6: 同名(归一后)方法保留证据最完整的一条.

    保留原顺序, 但同名 group 内只保 evidence_quote 最长的.
    对每个被合并掉的重复项, 在返回列表里加一条 status=rejected + reason=duplicate_method.
    """
    if not methods:
        return methods
    by_name: dict = {}
    order: list = []
    for m in methods:
        key = m.get("normalized_name") or ""
        if not key:
            order.append(m)
            continue
        if key not in by_name:
            by_name[key] = m
            order.append(m)
        else:
            # 决定谁留
            cur = by_name[key]
            if len(m.get("evidence_quote", "")) > len(cur.get("evidence_quote", "")):
                # 新的更长: reject 旧的
                cur["validation_status"] = "rejected"
                prev_reason = cur.get("rejected_reason", "")
                cur["rejected_reason"] = (prev_reason + ",duplicate_method"
                                          if prev_reason else "duplicate_method")
                by_name[key] = m
                order.append(m)
            else:
                # 保留旧的, reject 新的
                m["validation_status"] = "rejected"
                prev_reason = m.get("rejected_reason", "")
                m["rejected_reason"] = (prev_reason + ",duplicate_method"
                                        if prev_reason else "duplicate_method")
                order.append(m)
    return order
