"""Stable corpus identities and session citation numbers, shared by retrieval and fusion."""
from __future__ import annotations

import hashlib
import re
from typing import Iterable


def _hash(text):
    return hashlib.sha256(str(text).encode("utf-8")).hexdigest()[:20]


def _norm(text):
    return re.sub(r"\s+", "", str(text or "")).lower()


class SourceRegistry:
    def __init__(self, payload=None):
        payload = payload or {}
        self.chunks = dict(payload.get("chunks") or {})
        self.references = dict(payload.get("references") or {})

    def register(self, chunks: Iterable[dict]):
        self.last_registered_ids = set()
        for chunk in chunks:
            content = str(chunk.get("content") or chunk.get("text") or "")
            title = str(chunk.get("source_label") or chunk.get("source") or
                        chunk.get("original_filename") or "").strip()
            if not content.strip() or not title or title == "unknown":
                continue
            kind = chunk.get("type", "vector")
            version = str(chunk.get("corpus_version") or "traditional_rag_collection_v5")
            document = str(chunk.get("doc_id") or title)
            paper_id = f"DOC:{_hash(kind + ':' + version + ':' + document)}"
            parent = str(chunk.get("parent_id") or chunk.get("chunk_id") or
                         _hash(_norm(content)))
            # Include content identity so a changed block cannot silently replace old evidence.
            sid = f"SRC:{_hash(paper_id + ':' + parent + ':' + _hash(content))}"
            self.last_registered_ids.add(sid)
            if paper_id not in self.references:
                self.references[paper_id] = max(self.references.values(), default=0) + 1
            self.chunks.setdefault(sid, {
                "source_id": sid, "paper_id": paper_id,
                "ref_id": self.references[paper_id], "type": kind,
                "source": str(chunk.get("source") or title), "source_label": title,
                "doc_id": document, "parent_id": parent, "content": content,
                "content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                "score": chunk.get("rerank_score", chunk.get("score", chunk.get("similarity", 0))),
                "corpus_version": version,
                "location": str(chunk.get("location") or f"parent_block:{parent}"),
            })
            if chunk.get("audit_record"):
                self.chunks[sid]["audit_record"] = chunk["audit_record"]
        return self

    def documents(self, source_ids=None):
        docs = {}
        for chunk in self.chunks.values():
            if source_ids is not None and chunk["source_id"] not in source_ids:
                continue
            key = chunk["paper_id"]
            if key not in docs:
                docs[key] = {k: chunk[k] for k in ("ref_id", "type", "source", "source_label", "doc_id")}
                docs[key].update({"source_id": key, "content": "", "score": chunk.get("score", 0),
                                  "chunks": []})
            docs[key]["chunks"].append(dict(chunk))
        for doc in docs.values():
            doc["content"] = "\n---\n".join(c["content"] for c in doc["chunks"])
        return sorted(docs.values(), key=lambda d: d["ref_id"])

    def to_dict(self):
        return {"chunks": self.chunks, "references": self.references, 'identity_algorithm': 'literal_content_sha256_v2'}


def prepare_sources(state, registry=None):
    registry = registry or getattr(state, "source_registry", None) or SourceRegistry()
    active = set(getattr(state, "active_source_ids", None) or [])
    registry.register(getattr(state, "vector_chunks", None) or [])
    active.update(registry.last_registered_ids)
    registry.register(getattr(state, "lineage_sources", None) or [])
    active.update(registry.last_registered_ids)
    try:
        from .pdf_supplements import matching_sources
    except ImportError:
        from pdf_supplements import matching_sources
    supplemental = matching_sources(getattr(state, 'original_question', ''),
                                    [c['source'] for sid,c in registry.chunks.items() if sid in active])
    registry.register(supplemental)
    active.update(registry.last_registered_ids)
    state.source_supplement_diagnostics = {
        'count': len(supplemental),
        'versions': sorted({c['corpus_version'] for c in supplemental}),
        'manifest_sha256': sorted({c['audit_record']['manifest_sha256'] for c in supplemental}),
        'independent_human_review': False}
    state.source_registry = registry
    docs = registry.documents(active)
    # Legacy/test callers may supply sources without vector block metadata.
    if not docs and getattr(state, "doc_sources", None):
        registry.register(state.doc_sources)
        active.update(registry.last_registered_ids)
        docs = registry.documents(active)
    state.active_source_ids = active
    state.doc_sources = docs
    return registry


def context_from_sources(sources):
    blocks = []
    for s in sources:
        if not s.get('content'):
            continue
        scopes = ''
        if s.get('type') == 'pdf_supplement':
            records = [c['audit_record'] for c in s.get('chunks', []) if c.get('audit_record')]
            scopes = '\n【原PDF核对补充的使用边界；不是原句】\n' + '\n'.join(
                f"页{r['page']} {r['section']}：{r['scope']}" for r in records)
            scopes += '\n仅对应原页可修正旧OCR读数，须引用本补充Ref；不是独立人工验收，不把样品条件改写成通用配方。\n【PDF提取原句】\n'
        blocks.append(f"[Ref-{s['ref_id']}][{s['source_label']}] {scopes}{s['content']}")
    return '\n\n'.join(blocks)
