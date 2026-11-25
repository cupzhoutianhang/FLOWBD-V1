"""参考文献解析 (spec 三) — 从 full.md 抽 references section 并把 [N] → year 建映射.

无 API, 纯正则.
"""
from __future__ import annotations

import os
import re


# Reference section start markers
REF_SECTION_STARTS = (
    re.compile(r"^\s*References\s*$", re.M),
    re.compile(r"^\s*REFERENCES\s*$", re.M),
    re.compile(r"^\s*参\s*考\s*文\s*献\s*$", re.M),
    re.compile(r"^\s*#+\s*(References|参考文献)\s*$", re.M),
)

# Entry pattern: [N] ... , YEAR, ...
ENTRY_RE = re.compile(r"\[\s*(\d{1,3})\s*\]\s*(.+?)(?=\[\s*\d{1,3}\s*\]|\Z)",
                          re.DOTALL)
YEAR_RE = re.compile(r"(?<!\d)(19\d{2}|20\d{2})(?!\d)")

# Author first-tokens (before first period or "et al")
AUTHOR_RE = re.compile(r"^([^.\[\d]{2,80}?)(?:\s+et al|,\s+et al|\.)")


def find_references_section(full_md: str) -> str:
    """Return the substring from References/参考文献 to end of file."""
    for rgx in REF_SECTION_STARTS:
        m = rgx.search(full_md)
        if m:
            return full_md[m.end():]
    return ""


def parse_references(full_md: str) -> dict:
    """Parse [N] entries from references section.

    Returns:
      {ref_number (int) → {
        "year": int or None,
        "author": str,
        "raw_text": str,
        "year_source": "reference_list_entry" or "unresolved",
      }}
    """
    section = find_references_section(full_md)
    if not section: return {}
    out = {}
    for m in ENTRY_RE.finditer(section):
        num = int(m.group(1))
        body = m.group(2).strip()
        year = None
        y = YEAR_RE.search(body)
        if y:
            try:
                year = int(y.group(1))
            except ValueError: pass
        author = ""
        a = AUTHOR_RE.match(body)
        if a:
            author = a.group(1).strip().rstrip(",")
        out[num] = {
            "year": year,
            "author": author,
            "raw_text": body[:400],
            "year_source": "reference_list_entry" if year else "unresolved",
        }
    return out


def load_publish_year(paper_id: str, publish_year_csv: str = None) -> tuple:
    """Return (year, source) for a paper's publish year.

    Uses the legacy publish_year_report.csv only as an already-extracted
    regex derivative of the same full.md (no external download).
    """
    if publish_year_csv is None:
        from method_evolution_v2 import config
        publish_year_csv = config.LEGACY_YEAR_REPORT_CSV
    if not os.path.isfile(publish_year_csv):
        return None, "unresolved"
    import csv
    with open(publish_year_csv, "r", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r.get("paper_id") == paper_id:
                y = r.get("year", "").strip()
                try:
                    year = int(y)
                    return year, "primary_paper_publish_year"
                except ValueError:
                    return None, "unresolved"
    return None, "unresolved"


# Regex to find "作者 YEAR" or "作者等 YEAR" in method_name or citation_clue
CN_AUTHOR_YEAR_RE = re.compile(r"([一-鿿]{1,10}(?:等)?)\s*(19\d{2}|20\d{2})")
EN_AUTHOR_YEAR_RE = re.compile(r"([A-Z][A-Za-z]{2,20}\s*(?:et al|等)?)\s*"
                                    r"[,\s]*\(?(19\d{2}|20\d{2})\)?")
REF_NUM_RE = re.compile(r"\[\s*(\d{1,3})\s*\]")


def parse_citation_clue_for_year(clue: str, method_name: str = "") -> tuple:
    """Return (year, source, ref_number).

    Priority: (作者+年份 in clue) → (作者+年份 in name) → (数字 [N] number).
    Never guess.
    """
    for source_str, source_tag in ((clue or "", "citation_clue"),
                                        (method_name or "", "method_name_fallback")):
        m = CN_AUTHOR_YEAR_RE.search(source_str)
        if m:
            try:
                return int(m.group(2)), f"author_year_in_{source_tag}", None
            except ValueError: pass
        m = EN_AUTHOR_YEAR_RE.search(source_str)
        if m:
            try:
                return int(m.group(2)), f"author_year_in_{source_tag}", None
            except ValueError: pass
    # No year in clue; extract reference number
    m = REF_NUM_RE.search(clue or "") or REF_NUM_RE.search(method_name or "")
    if m:
        return None, "ref_number_only", int(m.group(1))
    return None, "unresolved", None
