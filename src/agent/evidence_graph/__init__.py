"""FlowBD 证据图闭环包 — DeepEvidence 机制移植(计划 2/3 章)。

公共 API:
  EvidenceGraphStore            证据图存储/回读(3.3)
  EvidenceExtractor             LLM 候选证据抽取(3.5)
  merge_round / MergeReport     每轮合并(3.4)
  IterativeCoordinator          迭代协调器(3.6, M3)
  schema.*                      节点/边/观察/规范 ID(3.2)

红线: LLM 写回一律 candidate; confirmed 仅经 store.import_confirmed(本期 NotImplementedError)。
"""

from .schema import (
    EDGE_TYPES,
    LEGAL_STATUSES,
    MAX_NAME_CHARS,
    MAX_OBS_PER_NODE,
    MAX_OBS_WORDS,
    MERGE_CAPS,
    NAME_EXEMPT_TYPES,
    NODE_TYPES,
    STATUS_CANDIDATE,
    STATUS_CONFIRMED,
    EdgeNode,
    EdgeRel,
    Observation,
    Provenance,
    conflict_group_id,
    edge_id,
    finding_id,
    node_id,
    normalize_name,
    word_count,
)
from .store import EvidenceGraphStore
from .merge import MergeReport, merge_round
from .extractor import EvidenceExtractor, ExtractionResult
from .coordinator import ACTIONS, CoordinatorState, IterativeCoordinator

__all__ = [
    "EDGE_TYPES", "LEGAL_STATUSES", "MAX_NAME_CHARS", "MAX_OBS_PER_NODE", "MAX_OBS_WORDS",
    "MERGE_CAPS", "NAME_EXEMPT_TYPES", "NODE_TYPES", "STATUS_CANDIDATE", "STATUS_CONFIRMED",
    "EdgeNode", "EdgeRel", "Observation", "Provenance",
    "conflict_group_id", "edge_id", "finding_id", "node_id", "normalize_name", "word_count",
    "EvidenceGraphStore", "MergeReport", "merge_round",
    "EvidenceExtractor", "ExtractionResult",
    "ACTIONS", "CoordinatorState", "IterativeCoordinator",
]
