"""paper_type — 论文类型规则分类器 (纯本地, 不调 LLM).

对外仅暴露:
  - classify_paper_type(parse_result)
  - PAPER_TYPES
  - PAPER_TYPE_RULES_VERSION
"""
from method_evolution_v2.paper_type.paper_type_rules import (   # noqa: F401
    PAPER_TYPES,
    PAPER_TYPE_RULES_VERSION,
    classify_paper_type,
)
