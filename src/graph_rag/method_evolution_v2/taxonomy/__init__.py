"""taxonomy — 论文级储能分类规则引擎 (纯本地, 无 LLM).

对外暴露:
  - classify_taxonomy(parse_result, paper_type_result=None)
  - TAXONOMY_VERSION
  - PAPER_CONTEXT_STATES
"""
from method_evolution_v2.taxonomy.taxonomy_rules import (      # noqa: F401
    TAXONOMY_VERSION,
    PAPER_CONTEXT_STATES,
    classify_taxonomy,
    load_keywords,
)
