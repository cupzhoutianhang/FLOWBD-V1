"""EvidenceExtractor — 从检索上下文与回答中抽取候选证据(M2, 计划 3.5)。

任何异常都被兜底为空 ExtractionResult: 写回失败绝不打断主管道。
红线: 产出的一切状态都是 candidate; quote 无法在 doc_sources 逐字定位的候选直接丢弃。
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from .schema import (
    NODE_TYPES,
    MAX_NAME_CHARS,
    MAX_OBS_WORDS,
    Provenance,
    normalize_name,
    word_count,
)
try:
    from ..structured_llm import call_structured
except ImportError:
    from structured_llm import call_structured

logger = logging.getLogger(__name__)


class ExtractionResult:
    """抽取产物(entities/relations 为清洗后的 dict, "_prov" 键承载 Provenance)。"""

    def __init__(self, entities: Optional[List[dict]] = None,
                 relations: Optional[List[dict]] = None):
        self.entities = entities or []
        self.relations = relations or []

    def __bool__(self) -> bool:
        return bool(self.entities or self.relations)


# 抽取 prompt 模板全文见《FlowBD_证据图闭环_制作计划.md》3.5, 施工时照抄
EXTRACT_PROMPT = """你是储能领域文献证据抽取器。从下面的【上下文】与【回答】中抽取"实体-结论-证据"三元组, 输出严格 JSON。

规则:
1. 实体类型只能是: PAPER(文献), METHOD(方法/工艺), MATERIAL(材料), PROPERTY(性能指标), MECHANISM(机理), TASK(应用场景)。
2. 每个实体最多 2 条 observations; 每条观察为对象，含 text、quote_id、source_id。text 是≤30词(中文≤60字)事实；quote_id 从原文证据目录选择，原文含PDF公式时不要重写；禁止补写数字、条件或因果。
3. 关系类型只能是: MECHANISM_OF, ATTRIBUTED_TO, ASSOCIATED_WITH, SUPPORTS, REFUTES, INCONCLUSIVE_FOR, CITES。
4. 每条关系必须给 quote_id，选择直接支持关系的原句；没有合适原句就不输出。若使用 evidence_quote，必须逐字复制，禁止改写或用省略号拼接。
5. 总量上限: 实体 ≤10 个, 关系 ≤16 条。宁可少而准。
6. 无法给出逐字原文的关系直接不要输出。
7. 只输出 JSON, 不要解释。格式:
{{"entities":[{{"name":"...","type":"METHOD","observations":[{{"text":"...","quote_id":"Q0001","source_id":"SRC:..."}}]}}],
 "relations":[{{"src":"实体名1","dst":"实体名2","type":"ASSOCIATED_WITH","quote_id":"Q0001","source_id":"SRC:...","obs":"≤30词结论短句"}}]}}
8. SUPPORTS/REFUTES只用于支持/反驳具体命题，不把工艺使用原料或设备误写成支持关系。
9. MECHANISM_OF的源端必须是MECHANISM；ATTRIBUTED_TO的源端必须是PROPERTY/FINDING。工艺使用原料不是因果归因，原句只说明使用时保留观察或有据的ASSOCIATED_WITH；CITES只能连接PAPER。
9. 仅抽取与本题体系直接相关的证据；不得用锌电池析氢证据替代铁铬体系等跨体系类比。没有本题证据就输出空数组。每条观察只写选中原句支持的事实，不能把整段其他句的步骤汇总到一个不支持它的句号编号。

【问题】{question}
【上下文】{context}
【回答】{answer}"""


def _grams(text: str, n: int = 3) -> set:
    s = normalize_name(text)
    if len(s) < n:
        return {s} if s else set()
    return {s[i:i + n] for i in range(len(s) - n + 1)}


def _sentence_split(text: str) -> List[str]:
    parts = re.split(r"(?<=[。．.!?;!；])\s*", str(text or ""))
    return [p.strip() for p in parts if len(p.strip()) >= 6]


class EvidenceExtractor:
    """LLM 抽取器。llm 为 part1.LLMConfig 实例(只做调用方, 不改其签名——红线 5)。"""

    MAX_ENTITIES = 10
    MAX_RELATIONS = 16

    def __init__(self, llm, extractor_name: str = "kimi-k2.6"):
        self.llm = llm
        self.extractor_name = extractor_name
        self.last_errors: List[str] = []
        self.quote_catalog = {}
        self.last_semantic_audit = {}

    # ------------------------------------------------------------------ 对外入口

    def extract(self, question: str, context: str, answer: str,
                doc_sources: List[dict], round_no: int) -> ExtractionResult:
        self.last_errors = []
        self.quote_catalog = {}
        self.last_semantic_audit = {}
        try:
            catalog_lines = []
            for doc in sorted(doc_sources or [],key=lambda d:{'lineage':0,'pdf_supplement':1}.get(d.get('type'),2)):
                for chunk in doc.get("chunks") or [doc]:
                    source_id = str(chunk.get("source_id") or "")
                    if source_id and source_id not in context:
                        continue
                    text=str(chunk.get('content') or '')[:1100]
                    if doc.get('type')=='pdf_supplement' and chunk.get('audit_record'):
                        audit=chunk['audit_record']
                        catalog_lines.append(f"[来源范围说明，非原句][{source_id}] 页{audit.get('page')}：{audit.get('scope')}。主张须保留样品/工序条件，不能把范围说明当原句。")
                    sentences=[text] if doc.get('type')=='pdf_supplement' else re.findall(r'[^。；]+[。；]?',text)
                    for sentence in sentences:
                        if len(sentence.strip()) < 8:
                            continue
                        qid = f"Q{len(self.quote_catalog) + 1:04d}"
                        self.quote_catalog[qid] = {"quote": sentence, "source_id": source_id}
                        catalog_lines.append(f"[{qid}][{source_id}][Ref-{doc.get('ref_id')}] {sentence}")
                    if sum(map(len, catalog_lines)) > 5600:
                        break
                if sum(map(len, catalog_lines)) > 5600:
                    break
            if catalog_lines:
                context = "【原文证据目录；用quote_id引用整条原文】\n" + "\n".join(catalog_lines)
            prompt = EXTRACT_PROMPT.format(
                question=str(question or "")[:600],
                context=str(context or "")[:7500],
                answer=str(answer or "")[:4000],
            )
            raw = call_structured(self.llm, prompt, max_tokens=4000)
            data = self._parse_json(raw)
            if not isinstance(data, dict):
                self.last_errors.append(f"LLM 输出非 JSON, 丢弃本轮抽取: {str(raw)[:120]}")
                return ExtractionResult()
        except Exception as e:                                   # noqa: BLE001
            self.last_errors.append(f"extract 兜底(写回失败不影响主管道): {e}")
            return ExtractionResult()

        ents = self._clean_entities(data.get("entities"), context, doc_sources, round_no)
        rels = self._clean_relations(data.get("relations"), doc_sources, round_no)
        try:
            from ..grounding_audit import enabled, screen_graph
        except ImportError:
            enabled = lambda llm: False  # legacy top-level tests; production imports the package
        if enabled(self.llm):
            claims = {}
            for ei, ent in enumerate(ents):
                for oi, obs in enumerate(ent['observation_records']):
                    claims[f'N{ei:02d}_{oi:02d}'] = {'entity': ent['name'], 'type': ent['type'],
                        'claim': obs['text'], 'provenance': obs['_prov'].to_dict()}
            for ri, rel in enumerate(rels):
                claims[f'R{ri:02d}'] = {'src': rel['src'], 'dst': rel['dst'], 'type': rel['type'],
                    'claim': rel['obs'], 'provenance': rel['_prov'].to_dict()}
            if claims:
                accepted, self.last_semantic_audit = screen_graph(self.llm, claims,question=question)
                filtered = []
                for ei, ent in enumerate(ents):
                    kept = [obs for oi, obs in enumerate(ent['observation_records']) if f'N{ei:02d}_{oi:02d}' in accepted]
                    if kept:
                        ent['observation_records'] = kept
                        ent['observations'] = [obs['text'] for obs in kept]
                        ent['_prov'] = kept[0]['_prov']
                        filtered.append(ent)
                ents = filtered
                rels = [rel for ri, rel in enumerate(rels) if f'R{ri:02d}' in accepted]
                if len(accepted) < len(claims):
                    self.last_errors.append(f'原句语义筛查拒收 {len(claims)-len(accepted)} 条候选主张')
        return ExtractionResult(ents, rels)

    # ------------------------------------------------------------------ JSON 解析(容错)

    @staticmethod
    def _parse_json(raw: str) -> Optional[dict]:
        if not raw or str(raw).startswith("❌"):
            return None
        text = str(raw).strip()
        m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
        if m:
            text = m.group(1)
        else:
            start, end = text.find("{"), text.rfind("}")
            if start < 0 or end <= start:
                return None
            text = text[start:end + 1]
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None

    # ------------------------------------------------------------------ provenance 绑定

    def _resolve_record(self, record, doc_sources, round_no):
        qid = str(record.get("quote_id") or "")
        if qid:
            item = self.quote_catalog.get(qid)
            if not item or (record.get("source_id") and record["source_id"] != item["source_id"]):
                return None
            return self._resolve_quote(item["quote"], doc_sources, round_no, item["source_id"])
        return self._resolve_quote(str(record.get("evidence_quote") or ""), doc_sources,
                                   round_no, str(record.get("source_id") or ""))

    def _resolve_quote(self, quote: str, doc_sources: List[dict],
                       round_no: int, source_id: str = "") -> Optional[Provenance]:
        """quote 必须在某 doc_source.content 中逐字(归一化后子串)存在, 否则拒收。"""
        q = normalize_name(quote)
        if not q:
            return None
        for doc in doc_sources or []:
          for ds in doc.get("chunks") or [doc]:
            if source_id and source_id != ds.get("source_id"):
                continue
            content = str(ds.get("content") or "")
            if not content:
                continue
            if q in normalize_name(content) and int(ds.get("ref_id", 0)) > 0:
                # Store the actual corpus slice, preserving case, whitespace and punctuation.
                chars, indexes = [], []
                for i, c in enumerate(content):
                    if not c.isspace():
                        for lower in c.lower():
                            chars.append(lower)
                            indexes.append(i)
                start = "".join(chars).find(q)
                actual = content[indexes[start]:indexes[start + len(q) - 1] + 1]
                return Provenance(
                    ref_id=int(ds.get("ref_id", 0)),
                    paper_title=str(ds.get("source_label") or ds.get("source") or ""),
                    quote=actual,
                    round=round_no,
                    extractor=self.extractor_name,
                    source_id=str(ds.get("source_id") or ""),
                    location=str(ds.get("location") or ""),
                )
        return None

    def _snap_quote(self, obs_text: str, context: str, doc_sources: List[dict],
                    round_no: int) -> Optional[Provenance]:
        """观察短句回查原文: 在上下文句子里找 3-gram 重叠最高者作为逐字 quote。

        重叠过低(程序无法从原文带出依据)则返回 None, 由调用方丢弃该观察。
        """
        obs_g = _grams(obs_text)
        if not obs_g:
            return None
        best, best_score, best_ds = None, 0.0, None
        pools: List[tuple] = []
        for doc in doc_sources or []:
            for ds in doc.get("chunks") or [doc]:
                content = str(ds.get("content") or "")
                if content and int(ds.get("ref_id", 0)) > 0:
                    pools.append((ds, content))
        for ds, pool in pools:
            for sent in _sentence_split(pool):
                sent_g = _grams(sent)
                union = len(obs_g | sent_g)
                score = len(obs_g & sent_g) / union if union else 0.0
                if score > best_score:
                    best, best_score, best_ds = sent, score, ds
        if best is None or best_score < 0.12:        # 阈值: 重叠过低视为无原文依据
            return None
        ds = best_ds or {}
        return Provenance(
            ref_id=int(ds.get("ref_id", 0)),
            paper_title=str(ds.get("source_label") or ds.get("source") or ""),
            quote=best,
            round=round_no,
            extractor=self.extractor_name,
            source_id=str(ds.get("source_id") or ""),
            location=str(ds.get("location") or ""),
        )

    # ------------------------------------------------------------------ 清洗

    def _clean_entities(self, raw_entities: Any, context: str,
                        doc_sources: List[dict], round_no: int) -> List[dict]:
        out: List[dict] = []
        for ent in (raw_entities or [])[: self.MAX_ENTITIES + 4]:
            try:
                name = str(ent.get("name") or "").strip()
                ntype = str(ent.get("type") or "").strip().upper()
                if not name or ntype not in NODE_TYPES:
                    self.last_errors.append(f"实体非法(名/类型): {name!r}/{ntype!r}")
                    continue
                # R8 实体命名闸门: 提前过滤超长名, 不占 10 实体名额
                if ntype not in ("PAPER", "FINDING") and len(name) > MAX_NAME_CHARS:
                    self.last_errors.append(
                        f"实体名超 {MAX_NAME_CHARS} 字符, 丢弃: {name[:40]}…")
                    continue
                prov = None
                kept_obs: List[str] = []
                observations = []
                for raw_obs in (ent.get("observations") or [])[:4]:
                    obs_text = raw_obs.get("text", "") if isinstance(raw_obs, dict) else raw_obs
                    obs_text = str(obs_text or "").strip()
                    if not obs_text:
                        continue
                    if word_count(obs_text) > MAX_OBS_WORDS:
                        self.last_errors.append(f"观察超 {MAX_OBS_WORDS} 词, 丢弃: {obs_text[:30]}…")
                        continue
                    if isinstance(raw_obs, dict):
                        o_prov = self._resolve_record(raw_obs, doc_sources, round_no)
                    else:
                        o_prov = self._snap_quote(obs_text, context, doc_sources, round_no)
                    if o_prov is None:
                        self.last_errors.append(f"观察无原文依据, 丢弃: {obs_text[:30]}…")
                        continue
                    numbers = set(re.findall(r"\d+(?:\.\d+)?", normalize_name(obs_text)))
                    quoted = set(re.findall(r"\d+(?:\.\d+)?", normalize_name(o_prov.quote)))
                    if not numbers.issubset(quoted):
                        self.last_errors.append(f"观察数值不受引文支持, 丢弃: {obs_text[:30]}")
                        continue
                    if self._quantity_issue(obs_text,o_prov,entity=name):
                        continue
                    if prov is None:
                        prov = o_prov
                    kept_obs.append(obs_text)
                    observations.append({"text": obs_text, "_prov": o_prov})
                if not kept_obs or prov is None:
                    continue
                out.append({"name": name, "type": ntype,
                            "observations": kept_obs, "_prov": prov,
                            "observation_records": observations})
            except Exception as e:                               # noqa: BLE001
                self.last_errors.append(f"实体清洗兜底: {e}")
        return out

    def _clean_relations(self, raw_relations: Any, doc_sources: List[dict],
                         round_no: int) -> List[dict]:
        out: List[dict] = []
        for rel in (raw_relations or [])[: self.MAX_RELATIONS + 6]:
            try:
                src = str(rel.get("src") or "").strip()
                dst = str(rel.get("dst") or "").strip()
                rtype = str(rel.get("type") or "").strip().upper()
                quote = str(rel.get("evidence_quote") or "").strip()
                obs = str(rel.get("obs") or "").strip()
                if not src or not dst:
                    self.last_errors.append(f"关系缺端点: {src!r}->{dst!r}")
                    continue
                if rtype not in ("MECHANISM_OF", "ATTRIBUTED_TO", "ASSOCIATED_WITH",
                                 "SUPPORTS", "REFUTES", "INCONCLUSIVE_FOR", "CITES"):
                    self.last_errors.append(f"关系类型非法: {rtype!r}")
                    continue
                prov = self._resolve_record(rel, doc_sources, round_no)
                if prov is None:
                    self.last_errors.append(f"关系 quote 无法逐字定位, 丢弃: {quote[:30]}…")
                    continue
                if obs and word_count(obs) > MAX_OBS_WORDS:
                    self.last_errors.append(f"关系 obs 超 {MAX_OBS_WORDS} 词, 置空保留关系")
                    obs = ""
                numbers = set(re.findall(r"\d+(?:\.\d+)?", normalize_name(obs)))
                quoted = set(re.findall(r"\d+(?:\.\d+)?", normalize_name(prov.quote)))
                if not numbers.issubset(quoted):
                    self.last_errors.append(f"关系数值不受引文支持, 丢弃: {obs[:30]}")
                    continue
                if self._quantity_issue(obs,prov):
                    continue
                out.append({"src": src, "dst": dst, "type": rtype,
                            "evidence_quote": prov.quote, "obs": obs, "_prov": prov})
            except Exception as e:                               # noqa: BLE001
                self.last_errors.append(f"关系清洗兜底: {e}")
        return out

    def _quantity_issue(self,text,prov,entity=''):
        """A bound quote cannot license a different unit/sign/explicit subject."""
        if __package__=='evidence_graph':
            from agent.quantity_grounding import audit_quantities
        else:
            from ..quantity_grounding import audit_quantities
        catalog={'Q0001':{'quote':prov.quote,'source_id':prov.source_id,
                         'ref_id':prov.ref_id,'title':prov.paper_title}}
        checks=audit_quantities((entity+'：' if entity else '')+text+f'[Ref-{prov.ref_id}]',catalog)
        bad=[q for q in checks if q['status'] not in {'matched_quantity','qualified_uncertainty'}]
        if bad:
            self.last_errors.append('图主张量值/单位/主体不受绑定原句支持，丢弃: '+str([q['status'] for q in bad]))
        return bool(bad)
