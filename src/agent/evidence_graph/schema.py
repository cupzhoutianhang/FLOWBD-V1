"""FlowBD 证据图 schema — DeepEvidence 机制的储能域适配。

对应《FlowBD_证据图闭环_制作计划.md》第 2 章 / 3.2 节。

红线(README 第四节 + 计划 0.3 第 7 条):
- LLM 新写回的一切观察/边状态一律 candidate;
- confirmed 仅允许从 Stage B 审计数据只读导入(本期接口占位, 见 store.import_confirmed)。
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from .relevance import fact_key, same_evidence

# ---------------------------------------------------------------------------
# 常量(计划 2.1 / 2.2 / 2.6)
# ---------------------------------------------------------------------------

NODE_TYPES = ("PAPER", "METHOD", "MATERIAL", "PROPERTY", "MECHANISM", "FINDING", "TASK")

EDGE_TYPES = (
    "MECHANISM_OF", "ATTRIBUTED_TO", "ASSOCIATED_WITH",
    "SUPPORTS", "REFUTES", "INCONCLUSIVE_FOR", "CITES",
    "DERIVED_FROM_KG",
)

STATUS_CANDIDATE = "candidate"
STATUS_CONFIRMED = "confirmed"
LEGAL_STATUSES = (STATUS_CANDIDATE, STATUS_CONFIRMED)

MAX_OBS_WORDS = 30          # 观察短句词数上限(计划 2.3)
MAX_OBS_PER_NODE = 3        # 每节点观察条数上限(计划 2.3)
MERGE_CAPS = {"new_nodes": 10, "new_edges": 16}   # 每轮合并限额(计划 2.6)
MAX_NAME_CHARS = 40         # 实体名字符上限(R8·实体命名闸门; 借鉴 DeepEvidence:
                            # names <=5 words or <=40 chars, 防整句问题当实体名入图)
NAME_EXEMPT_TYPES = ("PAPER", "FINDING")   # PAPER=论文题名合理超长; FINDING 由观察规则管理


# ---------------------------------------------------------------------------
# 词数 / 归一化 / 规范 ID(计划 2.1)
# ---------------------------------------------------------------------------

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def word_count(text: str) -> int:
    """英文按空格分词; 中文按 2 字符折 1 词(计划 2.3)。"""
    if not text:
        return 0
    cjk = len(_CJK_RE.findall(text))
    rest = _CJK_RE.sub(" ", text)
    return len(rest.split()) + (cjk + 1) // 2


def normalize_name(name: str) -> str:
    """实体归一化: 小写 + 去全部空白。同归一化名+同类型 ⇒ 必然同 ID。"""
    return re.sub(r"\s+", "", str(name or "").strip().lower())


def _sha12(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def node_id(node_type: str, name: str) -> str:
    if node_type not in NODE_TYPES:
        raise ValueError(f"非法节点类型: {node_type!r}")
    return f"{node_type}:{_sha12(normalize_name(name))}"


def finding_id(observation_text: str) -> str:
    """FINDING 节点按观察文本幂等(计划 2.6: 逐字幂等)。"""
    return f"FINDING:{_sha12(normalize_name(observation_text))}"


def edge_id(src: str, dst: str, etype: str, payload: str = "") -> str:
    if etype not in EDGE_TYPES:
        raise ValueError(f"非法边类型: {etype!r}")
    return f"{src}->{dst}:{etype}:{_sha12(payload)}"


def conflict_group_id(topic: str) -> str:
    return f"cg_{_sha12(normalize_name(topic))}"


# ---------------------------------------------------------------------------
# Provenance / Observation / 节点 / 边(计划 2.3)
# ---------------------------------------------------------------------------

@dataclass
class Provenance:
    """出处。quote 必须是原文逐字片段; 为空直接拒收(红线: 无 provenance 不入库)。"""

    ref_id: int
    paper_title: str
    quote: str
    round: int
    ts: str = ""
    extractor: str = "kimi-k2.6"
    source_id: str = ""
    location: str = ""

    def __post_init__(self):
        self.quote = str(self.quote or "").strip()
        if not self.quote:
            raise ValueError("provenance.quote 为空: 无逐字原文的证据不入库")
        if not self.ts:
            self.ts = datetime.now().isoformat(timespec="seconds")
        self.ref_id = int(self.ref_id)
        self.round = int(self.round)
        self.paper_title = str(self.paper_title or "").strip()
        if self.ref_id <= 0 or not self.paper_title:
            raise ValueError("provenance 来源未解析: Ref 必须为正数且题名非空")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ref_id": self.ref_id, "paper_title": self.paper_title,
            "quote": self.quote, "round": self.round,
            "ts": self.ts, "extractor": self.extractor,
            "source_id": self.source_id, "location": self.location,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Provenance":
        return cls(
            ref_id=d.get("ref_id", 0), paper_title=d.get("paper_title", ""),
            quote=d.get("quote", ""), round=d.get("round", 0),
            ts=d.get("ts", ""), extractor=d.get("extractor", "kimi-k2.6"),
            source_id=d.get("source_id", ""), location=d.get("location", ""),
        )


@dataclass
class Observation:
    """挂实体上的 ≤30 词事实短句(非自由文本段落)。"""

    text: str
    status: str = STATUS_CANDIDATE
    prov: Optional[Provenance] = None
    supporting_sources: List[Provenance] = field(default_factory=list)
    text_variants: List[str] = field(default_factory=list)

    def __post_init__(self):
        self.text = str(self.text or "").strip()
        if not self.text:
            raise ValueError("观察文本为空")
        if self.status not in LEGAL_STATUSES:
            raise ValueError(f"非法观察状态: {self.status!r}(LLM 写回一律 candidate)")
        if self.prov is None:
            raise ValueError("观察缺 provenance, 拒收")
        wc = word_count(self.text)
        if wc > MAX_OBS_WORDS:
            raise ValueError(f"观察超 {MAX_OBS_WORDS} 词(实测 {wc}): {self.text[:40]}…")

    @property
    def norm_text(self) -> str:
        return normalize_name(self.text)

    def to_dict(self) -> Dict[str, Any]:
        return {"text": self.text, "status": self.status, "prov": self.prov.to_dict(),
                "supporting_sources": [p.to_dict() for p in self.supporting_sources],
                "text_variants": self.text_variants}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Observation":
        return cls(
            text=d.get("text", ""), status=d.get("status", STATUS_CANDIDATE),
            prov=Provenance.from_dict(d.get("prov") or {}),
            supporting_sources=[Provenance.from_dict(p) for p in d.get("supporting_sources", [])],
            text_variants=list(d.get('text_variants') or []),
        )


@dataclass
class EdgeNode:
    """证据图节点。observations 即 DeepEvidence 的"实体观察短句"。"""

    id: str
    ntype: str
    name: str
    observations: List[Observation] = field(default_factory=list)
    created_round: int = 0

    def __post_init__(self):
        if self.ntype not in NODE_TYPES:
            raise ValueError(f"非法节点类型: {self.ntype!r}")
        self.name = str(self.name or "").strip()
        if not self.name:
            raise ValueError("节点名为空")
        if self.ntype not in NAME_EXEMPT_TYPES and len(self.name) > MAX_NAME_CHARS:
            raise ValueError(
                f"实体名超 {MAX_NAME_CHARS} 字符(实测 {len(self.name)}): {self.name[:40]}…")

    @property
    def norm_name(self) -> str:
        return normalize_name(self.name)

    def append_observation(self, obs: Observation) -> str:
        """返回 "appended" | "dup"(归一化文本重复) | "full"(超过每节点上限)。"""
        for existing in self.observations:
            alias_duplicate=(existing.status==obs.status and same_evidence(existing.prov,obs.prov)
                             and fact_key(existing.text)==fact_key(obs.text))
            if existing.norm_text == obs.norm_text or alias_duplicate:
                if obs.text!=existing.text and obs.text not in existing.text_variants:
                    existing.text_variants.append(obs.text)
                seen = {(p.source_id or p.paper_title) + normalize_name(p.quote)
                        for p in [existing.prov] + existing.supporting_sources}
                for p in [obs.prov] + obs.supporting_sources:
                    if ((p.source_id or p.paper_title) + normalize_name(p.quote)) not in seen:
                        existing.supporting_sources.append(p)
                        seen.add((p.source_id or p.paper_title) + normalize_name(p.quote))
                return "dup"
        if len(self.observations) >= MAX_OBS_PER_NODE:
            return "full"
        self.observations.append(obs)
        return "appended"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "type": self.ntype, "name": self.name,
            "observations": [o.to_dict() for o in self.observations],
            "created_round": self.created_round,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "EdgeNode":
        return cls(
            id=d["id"], ntype=d.get("type", ""), name=d.get("name", ""),
            observations=[Observation.from_dict(o) for o in (d.get("observations") or [])],
            created_round=int(d.get("created_round", 0)),
        )


@dataclass
class EdgeRel:
    """证据图边。conflict_group 非空表示该边处于一组未裁决冲突中(双边保留, 计划 2.5)。"""

    eid: str
    src: str
    dst: str
    etype: str
    status: str = STATUS_CANDIDATE
    prov: Optional[Provenance] = None
    obs: str = ""
    conflict_group: str = ""
    last_seen_round: int = 0
    supporting_sources: List[Provenance] = field(default_factory=list)
    text_variants: List[str] = field(default_factory=list)

    def __post_init__(self):
        if self.etype not in EDGE_TYPES:
            raise ValueError(f"非法边类型: {self.etype!r}")
        if self.status not in LEGAL_STATUSES:
            raise ValueError(f"非法边状态: {self.status!r}(LLM 写回一律 candidate)")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "edge_id": self.eid, "src": self.src, "dst": self.dst,
            "type": self.etype, "status": self.status,
            "prov": self.prov.to_dict() if self.prov else None,
            "obs": self.obs, "conflict_group": self.conflict_group,
            "last_seen_round": self.last_seen_round,
            "supporting_sources": [p.to_dict() for p in self.supporting_sources],
            "text_variants": self.text_variants,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "EdgeRel":
        prov = d.get("prov")
        return cls(
            eid=d["edge_id"], src=d["src"], dst=d["dst"], etype=d.get("type", ""),
            status=d.get("status", STATUS_CANDIDATE),
            prov=Provenance.from_dict(prov) if prov else None,
            obs=d.get("obs", ""), conflict_group=d.get("conflict_group", ""),
            last_seen_round=int(d.get("last_seen_round", 0)),
            supporting_sources=[Provenance.from_dict(p) for p in d.get("supporting_sources", [])],
            text_variants=list(d.get('text_variants') or []),
        )
