"""Stage A 全量: 方法节点的溯源属性 (spec 二).

计算并附着到每条方法的字段:
  - support_scope        : primary_article / article_reference / review_secondary /
                           patent_secondary
  - source_provenance    : in_corpus_primary / cited_external / corpus_match_candidate / unknown
  - citation_clue_raw    : 保留原文引用线索, 不清洗
  - cited_author         : 若能解析
  - cited_year           : 若能解析
  - cited_reference_number : 若能解析
  - external_stub_id     : 对 cited_external 生成的稳定 ID
  - evidence_paper_id    : 提供证据的当前论文 id
  - original_source_paper_id : 只在明确匹配到库内原论文时填, 否则空

严格禁令 (spec 二):
  - 不允许仅凭方法名相似就填写 original_source_paper_id
  - 不允许把综述发表年份当作被引方法年份
  - 不允许把综述里的方法冒充为综述自己提出
  - 解析不了时**保留原始 citation_clue**, 不猜测
"""
from __future__ import annotations

import hashlib
import re
import unicodedata


# ---- citation_clue 解析器 ----

# 参考文献编号 [15] / [1-3] / [1,2,3]
_REF_NUM_RE = re.compile(r"\[(\d+(?:\s*[-,]\s*\d+)*)\]")

# 4-位年份 (仅 19xx / 20xx, 避免误匹到方程编号)
_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")

# 常见中文作者前缀 (单字姓氏 或 姓+名 后跟 "等")
# 例: "王等", "刘昌会等", "CHEN 团队"
_ZH_AUTHOR_RE = re.compile(r"([一-鿿]{1,10})\s*(?:等|团队)")

# 英文作者: "Smith" 或 "Smith et al."
_EN_AUTHOR_RE = re.compile(
    r"\b([A-Z][a-zA-Z]{2,20})(?:\s+et\s+al\.?)?\b"
)


def parse_citation_clue(raw_clue: str) -> dict:
    """从 citation_clue 提取结构化字段, 不清洗原文.

    Returns:
      {
        "raw": <原文>,
        "author": <str, 未识别为空>,
        "year": <str, 未识别为空>,
        "reference_number": <str, 未识别为空>
      }
    """
    result = {"raw": raw_clue or "", "author": "", "year": "",
              "reference_number": ""}
    if not raw_clue:
        return result

    s = raw_clue.strip()

    m = _REF_NUM_RE.search(s)
    if m:
        result["reference_number"] = m.group(1)

    m = _YEAR_RE.search(s)
    if m:
        result["year"] = m.group(0)

    # 中文优先
    m = _ZH_AUTHOR_RE.search(s)
    if m:
        result["author"] = m.group(1) + "等"
    else:
        m = _EN_AUTHOR_RE.search(s)
        if m:
            result["author"] = m.group(1)

    return result


# ---- Provenance / support_scope 派生 ----

# support_scope 允许值 (spec 二)
SUPPORT_SCOPES = (
    "primary_article",       # 研究论文中的本文方法
    "article_reference",     # 研究论文引用的外部方法
    "review_secondary",      # 综述中介绍的外部方法
    "patent_secondary",      # 专利分析中介绍的方法
)

# source_provenance 允许值 (spec 二)
SOURCE_PROVENANCES = (
    "in_corpus_primary",         # 库内原始研究论文直接提出
    "cited_external",            # 引用/综述中介绍, 原始来源尚未确认
    "corpus_match_candidate",    # 疑似与库内其他论文对应, 未对齐
    "unknown",
)


def derive_support_scope(paper_type: str, kind: str) -> str:
    """基于 paper_type 与 method.kind (own/referenced) 派生 support_scope.

    - research_article + own       → primary_article
    - research_article + referenced → article_reference
    - review_article   + own       → primary_article (综述作者自提, 罕见)
    - review_article   + referenced → review_secondary  (综述引用的外部方法)
    - patent_analysis  + own       → primary_article
    - patent_analysis  + referenced → patent_secondary
    - unclear / non_storage 等     → 按 kind 走通用
    """
    pt = (paper_type or "").strip().lower()
    kd = (kind or "").strip().lower()

    if pt == "review_article":
        return "primary_article" if kd == "own" else "review_secondary"
    if pt == "patent_analysis":
        return "primary_article" if kd == "own" else "patent_secondary"
    # research_article, unclear, non_storage 等按通用
    return "primary_article" if kd == "own" else "article_reference"


def derive_source_provenance(kind: str,
                              corpus_match: bool = False) -> str:
    """派生 source_provenance.

    - own                          → in_corpus_primary  (库内论文自己提)
    - referenced (无 corpus 匹配)   → cited_external
    - referenced (可能匹配, 未对齐) → corpus_match_candidate
    - 其他                         → unknown

    corpus_match 参数是给后续跨论文对齐阶段用的; 本轮 Stage A 全量默认 False.
    """
    kd = (kind or "").strip().lower()
    if kd == "own":
        return "in_corpus_primary"
    if kd == "referenced":
        return "corpus_match_candidate" if corpus_match else "cited_external"
    return "unknown"


# ---- 外部方法稳定 ID ----

def _normalize_for_hash(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"\s+", "", s)
    return s.lower()


def make_external_stub_id(cited_author: str,
                            cited_year: str,
                            cited_reference_number: str,
                            method_name: str) -> str:
    """基于 (author, year, ref#, method_name) 生成稳定 ID.

    保证跨批次/跨运行相同. 前缀 'ext::' 便于识别.
    """
    parts = [
        _normalize_for_hash(cited_author),
        (cited_year or "").strip(),
        (cited_reference_number or "").strip(),
        _normalize_for_hash(method_name),
    ]
    key = "|".join(parts)
    return f"ext::{hashlib.sha1(key.encode('utf-8')).hexdigest()[:12]}"


# ---- 主入口: 给一条 method 附着 provenance 字段 ----

def attach_provenance(method: dict, paper_id: str, paper_type: str) -> dict:
    """给一条 classify_method / resolve_method_by_sentence_ids 输出的 method dict
    附着 provenance 字段. 不改动原字段, 仅新增.

    对 kind='referenced' 的方法**始终**生成 external_stub_id (即便原始论文可能在库内也生成; 未来跨论文匹配后再更新 original_source_paper_id).

    严格禁令 (spec 二):
      - 不基于 method_name 相似度填 original_source_paper_id (本函数不填, 恒为空)
      - 不用当前论文年份代替被引方法年份 (year 只从 citation_clue 解析)
      - 综述里的 referenced 不能被冒充为 own (kind 已由上游决定, 本函数不改)
    """
    kind = method.get("kind", "")
    raw_clue = method.get("citation_clue", "") or ""
    parsed = parse_citation_clue(raw_clue)

    support_scope = derive_support_scope(paper_type, kind)
    source_prov = derive_source_provenance(kind, corpus_match=False)

    ext_stub_id = ""
    if kind == "referenced":
        ext_stub_id = make_external_stub_id(
            parsed["author"], parsed["year"],
            parsed["reference_number"],
            method.get("name", "") or method.get("method_name", "")
        )

    # 附着; 不改原字段
    out = dict(method)
    out.setdefault("citation_clue_raw", raw_clue)
    out.setdefault("cited_author", parsed["author"])
    out.setdefault("cited_year", parsed["year"])
    out.setdefault("cited_reference_number", parsed["reference_number"])
    out["support_scope"] = support_scope
    out["source_provenance"] = source_prov
    out["external_stub_id"] = ext_stub_id
    out["evidence_paper_id"] = paper_id
    # spec 二 硬要求: 本阶段绝不填此字段
    out["original_source_paper_id"] = ""
    return out
