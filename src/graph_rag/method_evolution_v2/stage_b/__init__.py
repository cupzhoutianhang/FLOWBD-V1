"""Stage B — 演化关系抽取(两阶段: 提取 + 独立审查).

只抽 4 类关系: EXTENDS / IMPROVES / ADAPTS / REPLACES.
证据统一走 sentence_id 引用协议(与 Stage A 同款).
"""
from method_evolution_v2.stage_b.pair_generator import (      # noqa: F401
    generate_candidate_pairs,
    parse_sentence_id,
    scan_trigger_sentences,
    TRIGGER_WORDS,
)
from method_evolution_v2.stage_b.edge_validation import (      # noqa: F401
    validate_and_classify_edge,
)
from method_evolution_v2.stage_b.year_utils import (           # noqa: F401
    extract_year_from_citation_clue,
    temporal_status_for_pair,
)

STAGE_B_VERSION = "1.0"
