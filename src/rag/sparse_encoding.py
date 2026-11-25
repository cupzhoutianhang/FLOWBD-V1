"""Deterministic lexical TF-IDF over pinned BGE tokenizer IDs (not learned SPLADE)."""
from collections import Counter
from functools import lru_cache
from pathlib import Path
import json, math, os

PROJECT = Path(__file__).resolve().parents[2]
ACTIVE = PROJECT / 'src/data/corpus_versions/active.json'

def active_corpus():
    path = Path(os.environ.get('FLOWBD_CORPUS_MANIFEST', str(ACTIVE)))
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}

def active_collection(default='traditional_rag_collection_v5'):
    return active_corpus().get('collection', default)

def token_counts(text, tokenizer):
    ids = tokenizer.encode(str(text), add_special_tokens=False, truncation=True, max_length=2048)
    special = set(tokenizer.all_special_ids)
    return Counter(int(i) for i in ids if int(i) not in special)

@lru_cache(maxsize=4)
def load_idf(path, digest):
    import hashlib
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != digest:
        raise RuntimeError('Sparse IDF fingerprint differs from the active corpus')
    return {int(k):float(v) for k,v in json.loads(raw)['idf'].items()}

def encode_counts(counts, idf, limit=256):
    values = [(int(k),(1 + math.log(v))*idf[k]) for k,v in counts.items() if v > 0 and k in idf]
    values.sort(key=lambda p:(-p[1],p[0])); values = values[:limit]
    norm = math.sqrt(sum(v*v for _,v in values))
    return {k:float(v/norm) for k,v in values} if norm else {}

def encode(text, tokenizer, manifest):
    path = (PROJECT / manifest['idf_path']).resolve()
    if not path.is_relative_to(PROJECT.resolve()): raise ValueError('IDF must be a project resource')
    return encode_counts(token_counts(text,tokenizer),load_idf(str(path),manifest['idf_sha256']))
