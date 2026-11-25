"""paper_type_rules.py — 论文类型规则分类器 (纯本地, 无 LLM).

输出类型:
  - research_article   原创研究 (含系统建模 / 仿真 / 流程设计)
  - review_article     综述 / 研究进展
  - patent_analysis    专利分析 / 专利态势 / 专利计量
  - unclear            证据冲突或不足

设计原则:
  1. 只吃 section_parser 的 ParseResult (标题 / 摘要文本 / 章节类型 / 原始标题 / 章节正文).
  2. 不读 legacy 数据, 不写数据库, 不调 API.
  3. 每条 matched_signals 都必须附上原文级 evidence (title / abstract / section_heading).
  4. 不允许 paper_id 白名单硬编码.
  5. 决策优先级:
       patent_strong > review_title_strong > research(structure + abstract) > unclear

核心规则 (对应 spec 三/五):

  Patent 强信号 (任一):
    - 标题含 "专利分析 / 专利态势 / 专利计量"
    - 存在 patent_analysis 章节 + 正文出现 ≥3 个专利相关关键词 (申请人 / IPC / 专利族 ...)

  Review 强信号 (标题命中即为强, 不看正文):
    - 标题完整语义包含: 研究进展 / 进展 / 综述 / 研究现状 / 现状与展望 / review / progress
  Review 辅助信号 (单独不足, 仅作辅证 / 冲突记录):
    - 标题含: 发展趋势 / 应用
    - 摘要含: 综述了 / 阐述了 / 本文主要介绍 / 本文对...进行了系统性的归纳 / 研究进展 ...

  Research 强信号 (R1 / R2 有其一即可认定 research):
    R1: 存在 methods 且存在 results / results_discussion / discussion
    R2: 存在 theory_model 且存在 (case_analysis / results / results_discussion / conclusion)
        (对应 spec "模型验证 / 性能分析 / 结论")
  Research 中等信号 (R3 / R4 单独存在, 需综合判断):
    R3: 存在 system_design / simulation_calculation, 或正文出现 ≥2 个研究结构关键词
        (实验材料 / 实验装置 / 模型方程 / 边界条件 / 仿真结果 / 网格划分 / 初始条件 / 控制方程)
    R4: 摘要明确出现研究动作句式 (本文提出 / 本文建立 / 建立...模型 / 制备了 / 构建了 / 提出了一种 ...);
        或标题含研究动作词 (制备 / 改性 / 构建 / 仿真分析 / 实验研究 / 模拟研究 / 建立)

  证据要求:
    - type_evidence 每一条都携带 source ∈ {title, abstract, section_heading}
    - 摘要 excerpt 取窗口, 不虚构

  Unclear 触发:
    - 无任何强信号且辅助信号亦不足
    - 或强信号相互冲突且无法拉开距离
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

PAPER_TYPE_RULES_VERSION = "1.0"

PAPER_TYPES = ("research_article", "review_article", "patent_analysis", "unclear")


# ============================================================
# 信号词表 (仅本地正则; 若要扩表, 请在这里修改并附单测)
# ============================================================

PATENT_TITLE_STRONG = ("专利分析", "专利态势", "专利计量")

PATENT_BODY_KEYWORDS = (
    "申请人", "IPC", "专利族", "技术路线",
    "专利数量", "专利检索", "授权公告", "公开号",
)
PATENT_BODY_MIN_HITS = 3

REVIEW_TITLE_STRONG_CN = ("研究进展", "综述", "研究现状", "现状与展望", "进展")
REVIEW_TITLE_STRONG_EN_RE = re.compile(r"\b(review|progress)\b", re.IGNORECASE)

REVIEW_TITLE_AUX = ("发展趋势", "应用")

# 摘要级 review 标记 (支持字符串 & 正则); 单条命中即算一个 hit
ABS_REVIEW_MARKERS: tuple = (
    "综述了", "综述", "阐述了", "本文主要介绍", "本文综述",
    "评述了", "本文归纳", "本文回顾", "本文总结了", "本文对现有的",
    "研究进展", "研究现状",
    re.compile(r"本文对.{0,30}进行了系统性(的)?归纳"),
)

# 摘要级 research 动作句式 (每条命中 = 1 hit; 用来判 R4_abs)
ABS_RESEARCH_VERB_RES = (
    re.compile(r"(本文|本研究|本工作)[,,]?[^\n。]{0,10}?(提出|建立|构建|制备|设计|开发|搭建)了?"),
    re.compile(r"提出了一种"),
    # 允许 "建立/构建/制备/搭建" 后不带 了; object 加入 器 / 电池 / 换热器 覆盖储热器等成果名词
    re.compile(r"(建立|构建|制备|搭建)(?:了)?[^\n。]{0,30}?(模型|流程|方法|系统|材料|装置|框架|循环|器|电池|反应器|换热器)"),
    re.compile(r"实验研究了"),
    re.compile(r"模拟研究了"),
    re.compile(r"数值(模拟|计算)了"),
)

# 标题级 research 动作词 (每条命中 = 1 hit)
TITLE_RESEARCH_KEYWORDS = (
    "制备", "改性", "构建", "仿真分析", "实验研究", "模拟研究", "建立",
)

# 正文级 research 结构关键词 (≥2 hits = R3_body 命中)
BODY_RESEARCH_STRUCT_KEYWORDS = (
    "实验材料", "实验装置", "模型方程", "边界条件",
    "仿真结果", "网格划分", "初始条件", "控制方程",
)
BODY_RESEARCH_STRUCT_MIN_HITS = 2

EXCERPT_WINDOW = 60   # 摘要 evidence 取词前后各 30 字


# ============================================================
# 数据结构
# ============================================================

@dataclass
class _Evidence:
    source: str          # title / abstract / section_heading
    matched_for: str     # 信号 key
    excerpt: str         # 原文片段

    def to_dict(self) -> dict:
        return {"source": self.source, "matched_for": self.matched_for, "excerpt": self.excerpt}


@dataclass
class _SignalBag:
    matched: list = field(default_factory=list)          # [(key, detail)]
    conflicting: list = field(default_factory=list)      # [(key, detail)]
    evidence: list = field(default_factory=list)         # [_Evidence]

    def add_matched(self, key: str, detail: str) -> None:
        self.matched.append((key, detail))

    def add_conflict(self, key: str, detail: str) -> None:
        self.conflicting.append((key, detail))

    def add_evidence(self, source: str, matched_for: str, excerpt: str) -> None:
        self.evidence.append(_Evidence(source=source, matched_for=matched_for, excerpt=excerpt))


# ============================================================
# 工具函数
# ============================================================

def _get_abstract_text(parse_result) -> str:
    """拼接所有 abstract 章节的段落文本. 无 abstract 时返回空串."""
    parts = []
    for s in parse_result.sections:
        if s.section_type != "abstract":
            continue
        for p in s.paragraphs:
            if p.text:
                parts.append(p.text)
    return "\n".join(parts)


def _get_body_text_excluding_references(parse_result) -> str:
    """拼接除 references 之外的正文文本 (用于关键词扫描)."""
    parts = []
    for s in parse_result.sections:
        if s.section_type == "references":
            continue
        for p in s.paragraphs:
            if p.text:
                parts.append(p.text)
    return "\n".join(parts)


def _get_section_type_set(parse_result) -> set:
    """返回已识别的实质章节类型集合 (剔除 other_sections / title / references)."""
    substantive = set()
    for s in parse_result.sections:
        if s.section_type in ("other_sections", "title"):
            continue
        substantive.add(s.section_type)
    return substantive


def _all_headings(parse_result) -> list:
    return [s.raw_heading for s in parse_result.sections if s.raw_heading]


def _excerpt_around(text: str, needle: str, window: int = EXCERPT_WINDOW) -> str:
    """从 text 中截取 needle 附近的一段作为 evidence excerpt.

    找不到时退化为返回前 window*2 字符.
    """
    if not text:
        return ""
    idx = text.find(needle)
    if idx < 0:
        return text[: window * 2].strip()
    lo = max(0, idx - window // 2)
    hi = min(len(text), idx + len(needle) + window // 2)
    return text[lo:hi].strip()


def _re_search_excerpt(text: str, pattern: re.Pattern, window: int = EXCERPT_WINDOW) -> tuple:
    """在 text 中搜索 pattern; 命中返回 (matched_str, excerpt), 否则 (None, "")."""
    m = pattern.search(text)
    if not m:
        return None, ""
    matched = m.group(0)
    lo = max(0, m.start() - window // 2)
    hi = min(len(text), m.end() + window // 2)
    return matched, text[lo:hi].strip()


# ============================================================
# 三大类信号采集 (无副作用, 只读 parse_result)
# ============================================================

def _detect_patent_signals(title: str, section_types: set, body: str, bag: _SignalBag) -> bool:
    """采集专利强信号; 命中即返回 True (调用方立刻收敛为 patent_analysis)."""
    hit = False
    for kw in PATENT_TITLE_STRONG:
        if kw in title:
            bag.add_matched("patent_title_strong", f"title contains '{kw}'")
            bag.add_evidence("title", "patent_title_strong", title)
            hit = True
            break

    if "patent_analysis" in section_types:
        body_hits = [kw for kw in PATENT_BODY_KEYWORDS if kw in body]
        if len(body_hits) >= PATENT_BODY_MIN_HITS:
            bag.add_matched(
                "patent_section_and_body",
                f"has patent_analysis section + body hits {body_hits}",
            )
            excerpt = _excerpt_around(body, body_hits[0])
            bag.add_evidence("section_heading", "patent_section_and_body",
                             f"section_type=patent_analysis; body_excerpt={excerpt!s}")
            hit = True
    return hit


def _detect_review_title_signals(title: str, bag: _SignalBag) -> tuple:
    """返回 (strong_hit: bool, aux_hit: bool). 中途向 bag 追加 matched + evidence."""
    strong = False
    aux = False
    # 强 CN
    for kw in REVIEW_TITLE_STRONG_CN:
        if kw in title:
            bag.add_matched("review_title_strong", f"title contains '{kw}'")
            bag.add_evidence("title", "review_title_strong", title)
            strong = True
            break
    # 强 EN
    if not strong:
        m = REVIEW_TITLE_STRONG_EN_RE.search(title)
        if m:
            bag.add_matched("review_title_strong", f"title contains English '{m.group(0)}'")
            bag.add_evidence("title", "review_title_strong", title)
            strong = True
    # 辅助
    for kw in REVIEW_TITLE_AUX:
        if kw in title and kw not in (m for m, _ in bag.matched):
            bag.add_matched("review_title_aux_only", f"title contains '{kw}' (aux only)")
            bag.add_evidence("title", "review_title_aux_only", title)
            aux = True
            break
    return strong, aux


def _detect_abstract_review_hits(abstract: str, bag: _SignalBag) -> int:
    """返回摘要级 review 标记 hit 数; 首个 hit 附 evidence."""
    if not abstract:
        return 0
    hits = []
    for marker in ABS_REVIEW_MARKERS:
        if isinstance(marker, re.Pattern):
            m = marker.search(abstract)
            if m:
                hits.append(m.group(0))
        else:
            if marker in abstract:
                hits.append(marker)
    if hits:
        bag.add_matched("abstract_review_markers", f"abstract markers: {hits}")
        excerpt = _excerpt_around(abstract, hits[0] if isinstance(hits[0], str) else hits[0])
        bag.add_evidence("abstract", "abstract_review_markers", excerpt)
    return len(hits)


def _detect_research_structure(parse_result, section_types: set, bag: _SignalBag) -> tuple:
    """
    返回 (R1, R2, R3_struct). 依据章节类型集合.
    并把有依据的 R1/R2/R3_struct 命中转成 evidence (只截取直接支撑该 R 的章节标题).
    """
    has_methods = "methods" in section_types
    has_results = any(t in section_types for t in ("results", "results_discussion", "discussion"))
    has_theory = "theory_model" in section_types
    has_case = "case_analysis" in section_types
    has_concl = "conclusion" in section_types
    has_sys = "system_design" in section_types
    has_sim = "simulation_calculation" in section_types

    R1 = has_methods and has_results
    R2 = has_theory and (has_case or has_results or has_concl)
    R3_struct = has_sys or has_sim

    def _headings_of(types: set) -> str:
        return "; ".join(
            s.raw_heading for s in parse_result.sections
            if s.section_type in types and s.raw_heading
        )[:200]

    if R1:
        bag.add_matched("R1_methods_and_results", "has methods AND results/discussion")
        bag.add_evidence(
            "section_heading", "R1_methods_and_results",
            _headings_of({"methods", "results", "results_discussion", "discussion"}),
        )
    if R2:
        details = []
        types_for_ev = {"theory_model"}
        if has_case: details.append("case_analysis"); types_for_ev.add("case_analysis")
        if has_results:
            details.append("results")
            types_for_ev.update({"results", "results_discussion", "discussion"})
        if has_concl: details.append("conclusion"); types_for_ev.add("conclusion")
        bag.add_matched("R2_theory_and_verify",
                        f"has theory_model AND {'/'.join(details)}")
        bag.add_evidence("section_heading", "R2_theory_and_verify",
                         _headings_of(types_for_ev))
    if R3_struct:
        bits = []
        types_for_ev = set()
        if has_sys: bits.append("system_design"); types_for_ev.add("system_design")
        if has_sim: bits.append("simulation_calculation"); types_for_ev.add("simulation_calculation")
        bag.add_matched("R3_system_or_simulation", f"has {'/'.join(bits)}")
        bag.add_evidence("section_heading", "R3_system_or_simulation",
                         _headings_of(types_for_ev))
    return R1, R2, R3_struct


def _detect_research_body_keywords(body: str, bag: _SignalBag) -> bool:
    if not body:
        return False
    hits = [kw for kw in BODY_RESEARCH_STRUCT_KEYWORDS if kw in body]
    if len(hits) >= BODY_RESEARCH_STRUCT_MIN_HITS:
        bag.add_matched("R3_body_research_kw",
                        f"body has research structure kws: {hits}")
        excerpt = _excerpt_around(body, hits[0])
        bag.add_evidence("abstract", "R3_body_research_kw",
                         f"body_excerpt: {excerpt!s}")
        return True
    return False


def _detect_abstract_research_verbs(abstract: str, bag: _SignalBag) -> bool:
    if not abstract:
        return False
    hits = []
    excerpt = ""
    for patt in ABS_RESEARCH_VERB_RES:
        matched, exc = _re_search_excerpt(abstract, patt)
        if matched:
            hits.append(matched)
            if not excerpt:
                excerpt = exc
    if hits:
        bag.add_matched("R4_abstract_research_verbs",
                        f"abstract research verbs: {hits}")
        bag.add_evidence("abstract", "R4_abstract_research_verbs", excerpt)
        return True
    return False


def _detect_title_research_verbs(title: str, bag: _SignalBag) -> bool:
    hits = [kw for kw in TITLE_RESEARCH_KEYWORDS if kw in title]
    if hits:
        bag.add_matched("R4_title_research_verbs",
                        f"title research verbs: {hits}")
        bag.add_evidence("title", "R4_title_research_verbs", title)
        return True
    return False


# ============================================================
# 主入口
# ============================================================

def classify_paper_type(parse_result,
                        section_parser_version: str = None,
                        now_iso: str = None) -> dict:
    """按规则给一篇论文打类型标签.

    输入: section_parser.ParseResult
    输出: 见 spec 四的字段.
    """
    # 尽量引本地版本号, 兼容测试传入
    if section_parser_version is None:
        try:
            from method_evolution_v2.io.section_parser import SECTION_PARSER_VERSION as _spv
            section_parser_version = _spv
        except Exception:
            section_parser_version = "unknown"
    if now_iso is None:
        now_iso = datetime.now().isoformat(timespec="seconds")

    title = (parse_result.document_title or "").strip()
    abstract = _get_abstract_text(parse_result)
    body = _get_body_text_excluding_references(parse_result)
    section_types = _get_section_type_set(parse_result)

    bag = _SignalBag()

    # -------- Patent 优先 --------
    if _detect_patent_signals(title, section_types, body, bag):
        return _build_result(
            paper_type="patent_analysis",
            confidence="high",
            reason="patent strong signal (title keyword or patent_analysis section + body keywords)",
            bag=bag,
            section_parser_version=section_parser_version,
            now_iso=now_iso,
            paper_id=parse_result.paper_id,
        )

    # -------- Review 标题强信号 --------
    review_strong, review_aux = _detect_review_title_signals(title, bag)

    # -------- Research 信号采集 --------
    abs_review_hits = _detect_abstract_review_hits(abstract, bag)
    R1, R2, R3_struct = _detect_research_structure(parse_result, section_types, bag)
    R3_body = _detect_research_body_keywords(body, bag)
    R3 = R3_struct or R3_body
    R4_abs = _detect_abstract_research_verbs(abstract, bag)
    R4_title = _detect_title_research_verbs(title, bag)
    R4 = R4_abs or R4_title

    strong_research_count = int(R1) + int(R2)
    research_signal_count = int(R1) + int(R2) + int(R3) + int(R4)

    # -------- 决策树 --------
    if review_strong:
        if strong_research_count >= 1:
            bag.add_conflict(
                "review_title_strong_vs_research_structure",
                "title has review strong signal but structure also matches R1/R2",
            )
            return _build_result(
                paper_type="review_article",
                confidence="medium",
                reason=("title has review strong signal; but paper also shows "
                        "R1/R2 research structure — recorded as conflict, kept as review"),
                bag=bag,
                section_parser_version=section_parser_version,
                now_iso=now_iso,
                paper_id=parse_result.paper_id,
            )
        return _build_result(
            paper_type="review_article",
            confidence="high",
            reason="title has review strong signal; no research structure conflict",
            bag=bag,
            section_parser_version=section_parser_version,
            now_iso=now_iso,
            paper_id=parse_result.paper_id,
        )

    if strong_research_count >= 1:
        confidence = "high"
        if abs_review_hits >= 2:
            bag.add_conflict(
                "research_structure_vs_abstract_review_markers",
                f"structure is R1/R2 but abstract has {abs_review_hits} review markers",
            )
            confidence = "medium"
        return _build_result(
            paper_type="research_article",
            confidence=confidence,
            reason=("R1 or R2 satisfied — has methods+results OR theory_model+verify"),
            bag=bag,
            section_parser_version=section_parser_version,
            now_iso=now_iso,
            paper_id=parse_result.paper_id,
        )

    # 仅有 R3 / R4 中等信号
    if R3 or R4:
        if abs_review_hits >= 2:
            if not (R4_abs and R4):
                bag.add_conflict(
                    "weak_research_vs_abstract_review_markers",
                    ("only weak research signals (R3/R4_title) but abstract has "
                     f"{abs_review_hits} review markers"),
                )
                return _build_result(
                    paper_type="review_article",
                    confidence="medium",
                    reason=("weak research signal (R3 or R4_title only) is dominated by "
                            "multiple abstract review markers"),
                    bag=bag,
                    section_parser_version=section_parser_version,
                    now_iso=now_iso,
                    paper_id=parse_result.paper_id,
                )
            # R4_abs 命中 + 摘要 review 标记也 ≥2: 双向拉扯, 回落 unclear
            bag.add_conflict(
                "abstract_has_both_review_markers_and_research_verbs",
                (f"abstract has {abs_review_hits} review markers AND a research verb — "
                 "cannot disambiguate without LLM"),
            )
            return _build_result(
                paper_type="unclear",
                confidence="low",
                reason="abstract has both review markers and research verbs; no structural anchor",
                bag=bag,
                section_parser_version=section_parser_version,
                now_iso=now_iso,
                paper_id=parse_result.paper_id,
            )

        if review_aux:
            bag.add_conflict(
                "weak_research_vs_review_aux_title",
                "only R3/R4 medium research + review aux title, insufficient to commit",
            )
            return _build_result(
                paper_type="unclear",
                confidence="low",
                reason=("only medium research signal and review aux title; "
                        "conflict without strong anchor"),
                bag=bag,
                section_parser_version=section_parser_version,
                now_iso=now_iso,
                paper_id=parse_result.paper_id,
            )

        return _build_result(
            paper_type="research_article",
            confidence="medium",
            reason=("only R3/R4 signals satisfied (system/simulation/body kw or "
                    "abstract/title research verb); no review or patent signal"),
            bag=bag,
            section_parser_version=section_parser_version,
            now_iso=now_iso,
            paper_id=parse_result.paper_id,
        )

    # 无 research 强 / 中信号
    if abs_review_hits >= 2:
        # 摘要有 ≥2 个 review 标记 = 正向 review 证据 (非"缺失论证"), 允许判 review medium.
        # 与 spec 3.1 "标题辅助信号不能单独判 review" 不冲突: 这里靠的是摘要多重标记.
        return _build_result(
            paper_type="review_article",
            confidence="medium",
            reason=(f"no research signal, but abstract has {abs_review_hits} review markers "
                    "— positive review evidence (independent of absence-of-methods argument)"),
            bag=bag,
            section_parser_version=section_parser_version,
            now_iso=now_iso,
            paper_id=parse_result.paper_id,
        )

    if review_aux or abs_review_hits >= 1:
        return _build_result(
            paper_type="unclear",
            confidence="low",
            reason=("only review aux / single abstract review marker, "
                    "no strong signal in any direction"),
            bag=bag,
            section_parser_version=section_parser_version,
            now_iso=now_iso,
            paper_id=parse_result.paper_id,
        )

    return _build_result(
        paper_type="unclear",
        confidence="low",
        reason="no title / abstract / structural signal matched",
        bag=bag,
        section_parser_version=section_parser_version,
        now_iso=now_iso,
        paper_id=parse_result.paper_id,
    )


def _build_result(paper_type: str, confidence: str, reason: str, bag: _SignalBag,
                  section_parser_version: str, now_iso: str, paper_id: str) -> dict:
    return {
        "paper_id": paper_id,
        "paper_type": paper_type,
        "rule_confidence": confidence,
        "matched_signals": [{"key": k, "detail": d} for (k, d) in bag.matched],
        "conflicting_signals": [{"key": k, "detail": d} for (k, d) in bag.conflicting],
        "type_evidence": [e.to_dict() for e in bag.evidence],
        "decision_reason": reason,
        "parser_version": (
            f"section_parser={section_parser_version}; "
            f"paper_type_rules={PAPER_TYPE_RULES_VERSION}"
        ),
        "classified_at": now_iso,
    }
