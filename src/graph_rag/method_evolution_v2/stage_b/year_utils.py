"""年份抽取 & 时间态判定 (spec 七).

规则:
  - method_year 只从 citation_clue 里提, 不用论文发表年份代替
  - 找不到 → temporal_status='unknown', 不作为拒绝理由
  - from_year < to_year (从"后"的方法比被引"前"的方法年份还早) → temporal_conflict
  - 明确证据方向优先于缺失年份
"""
from __future__ import annotations
import re

_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")


def extract_year_from_citation_clue(clue: str) -> int | None:
    """从 citation_clue (如 'Smith 2018', '[15] 2020', 'CHEN 团队[29]') 中抽 4 位年份.

    只识别 19xx / 20xx; 没找到返回 None. 找到多个取第一个.
    """
    if not clue:
        return None
    m = _YEAR_RE.search(clue)
    return int(m.group(0)) if m else None


def temporal_status_for_pair(from_year, to_year) -> str:
    """判定时间态.

    from_method 在 (后来 / 改进者); to_method 在 (被改进 / 前人).
    正常时序: from_year >= to_year.

    Returns:
      'ok' - from_year >= to_year (符合"后 → 前"方向)
      'conflict' - from_year < to_year (明显冲突, 需人工/降级)
      'unknown' - 任一端年份未知 (spec 七: 不作为拒绝理由)
    """
    if from_year is None or to_year is None:
        return "unknown"
    if from_year >= to_year:
        return "ok"
    return "conflict"
