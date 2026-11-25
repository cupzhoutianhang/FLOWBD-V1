"""Stage A v2.1 引用线索解析改进 (spec 七).

在 provenance.parse_citation_clue 之上, 允许**从 method_name 兜底**抽作者/引用编号.

严格禁令 (与 v1 一致):
  - 不猜年份
  - 不用当前论文年份代替
  - 不仅凭名字关联库内原始论文
  - external_stub_id 保持稳定
"""
from __future__ import annotations

import re


# spec 一: 版本锁
PROVENANCE_VERSION = "v2.1_name_fallback_2026-07-01"

from method_evolution_v2.stage_a.provenance import (
    parse_citation_clue as _v1_parse,
    make_external_stub_id,
    derive_support_scope,
    derive_source_provenance,
)


# 允许从 name 里读的作者形态:
# - "Sarkar 等" / "Sarkar等"
# - "刘昌会等"
# - "WEN 等"
# - "王 2020" - 但 year 不从 name 兜, 只从 clue
_NAME_ZH_AUTHOR_RE = re.compile(r"([一-鿿]{1,10})\s*(?:等|团队)")
_NAME_EN_AUTHOR_RE = re.compile(r"([A-Z][A-Za-z]{2,20}(?:\s*等)?)")
_NAME_REF_RE = re.compile(r"\[(\d+(?:\s*[-,]\s*\d+)*)\]")


def parse_citation_clue_with_name_fallback(citation_clue: str,
                                             method_name: str = "") -> dict:
    """先用 v1 从 citation_clue 解, 若字段仍空且 method_name 里有信息则兜底.

    **年份绝不从 name 猜** (spec 七).
    """
    result = _v1_parse(citation_clue)
    if not method_name:
        return result

    # 兜底: reference number
    if not result["reference_number"]:
        m = _NAME_REF_RE.search(method_name)
        if m:
            result["reference_number"] = m.group(1)

    # 兜底: 作者
    if not result["author"]:
        m = _NAME_ZH_AUTHOR_RE.search(method_name)
        if m:
            result["author"] = m.group(1) + "等"
        else:
            m = _NAME_EN_AUTHOR_RE.search(method_name)
            if m:
                candidate = m.group(1).strip()
                # 剥掉尾部 "等" 便于 hash 稳定; 需要时下游可再补
                candidate = re.sub(r"\s*等\s*$", "", candidate).strip()
                # 排除误抓: 只 3-4 字母的化学式类 (LFP, NCM 之类不算作者)
                if candidate and not re.fullmatch(r"[A-Z]{2,5}", candidate):
                    result["author"] = candidate

    # year 绝不猜; 保持 v1 结果
    return result


def attach_provenance_v2(method: dict, paper_id: str, paper_type: str) -> dict:
    """v2 版 attach_provenance: 使用 name-fallback 版本的 citation 解析.

    其他字段与 v1 attach_provenance 语义一致.
    """
    kind = method.get("kind", "")
    raw_clue = method.get("citation_clue", "") or ""
    parsed = parse_citation_clue_with_name_fallback(
        raw_clue, method.get("name", "") or method.get("method_name", ""))

    support_scope = derive_support_scope(paper_type, kind)
    source_prov = derive_source_provenance(kind, corpus_match=False)

    ext_stub_id = ""
    if kind == "referenced":
        ext_stub_id = make_external_stub_id(
            parsed["author"], parsed["year"], parsed["reference_number"],
            method.get("name", "") or method.get("method_name", "")
        )

    out = dict(method)
    out.setdefault("citation_clue_raw", raw_clue)
    out.setdefault("cited_author", parsed["author"])
    out.setdefault("cited_year", parsed["year"])
    out.setdefault("cited_reference_number", parsed["reference_number"])
    # v2 里显式覆盖 (即便 v1 attach 已跑过一次)
    out["cited_author"] = parsed["author"]
    out["cited_year"] = parsed["year"]
    out["cited_reference_number"] = parsed["reference_number"]
    out["support_scope"] = support_scope
    out["source_provenance"] = source_prov
    out["external_stub_id"] = ext_stub_id
    out["evidence_paper_id"] = paper_id
    out["original_source_paper_id"] = ""
    return out
