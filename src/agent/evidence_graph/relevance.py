"""Small explicit aliases; conservative deduplication never merges unknown meaning."""
import re
import unicodedata

_ALIASES = (
    ('析氢',r'析氢|氢气副反应|氢气析出|产氢副反应|hydrogen\s+evolution|\bHER\b'),
    ('铁铬',r'铁铬|铁/铬|iron[- ]chromium|\bICRFB\b'),
    ('全铁',r'全铁|all[- ]iron|\bAIRFB\b'),
    ('钒液流',r'全钒|钒液流|钒电池|vanadium|\bVRFB\b'),
    ('膨胀石墨',r'膨胀石墨|expanded\s+graphite|\bEG\b'),
    ('蒽醌',r'蒽醌|anthraquinone|\bDHAQ\b'),
    ('2甲基咪唑',r'2[- ]?甲基咪唑|2[- ]?methylimidazole|\b2[- ]?(?:mIm|MI)\b'),
    ('咪唑',r'咪唑|imidazole'),
    ('甘氨酸',r'甘氨酸|\bglycine\b'),
)


def canonical(text):
    value=unicodedata.normalize('NFKC',str(text or ''))
    for name, pattern in _ALIASES:
        # Python \b treats adjacent Chinese as a word character; boundaries for
        # Latin aliases must exclude Latin/digits only (e.g. "VRFB的机制").
        parts=pattern.split(r'\b')
        pattern=parts[0]+''.join((r'(?<![A-Za-z0-9])' if i%2 else r'(?![A-Za-z0-9])')+part
                                for i,part in enumerate(parts[1:],1))
        value=re.sub(pattern,name,value,flags=re.I)
    return re.sub(r'\s+','',value).lower()


def fact_key(text):
    value=canonical(text)
    for old,new in (('提高','提升'),('导热性能','导热性'),('容量保留率','容量保持率')):
        value=value.replace(old,new)
    return value


def same_evidence(left,right):
    return bool(left and right and left.source_id and left.source_id==right.source_id
                and left.quote==right.quote and left.ref_id==right.ref_id)


def retrieval_score(query,node):
    q=canonical(query)
    pieces=[node.name]
    for obs in node.observations:
        if obs.prov and obs.prov.source_id:
            pieces.extend([obs.text,obs.prov.quote,obs.prov.paper_title])
    text=canonical(' '.join(pieces))
    if not q or not text:
        return 0
    query_topics={term for term in ('钒液流','铁铬','全铁') if term in q}
    node_topics={term for term in ('钒液流','铁铬','全铁') if term in text}
    if query_topics and node_topics and query_topics.isdisjoint(node_topics):
        return 0
    # Do not pull iron/thermal history into an explicit vanadium topic switch.
    if '钒液流' in q and '钒液流' not in text and any(term in text for term in ('铁铬','全铁','膨胀石墨')):
        return 0
    if any(term in q for term in ('铁铬','全铁')) and '钒液流' in text and not any(term in text for term in ('铁铬','全铁')):
        return 0
    concepts=[name for name,_ in _ALIASES if name in q and name in text]
    name=canonical(node.name)
    name_hit=len(name)>=2 and name in q
    grams={q[i:i+3] for i in range(max(0,len(q)-2))}
    # Common question fragments are not scientific entity matches.
    grams-={'有什么','有哪些','是什么','的方法','的机制','为什么','如何在','请说明'}
    overlap=sum(g in text for g in grams)
    return 8*len(concepts)+6*int(name_hit)+overlap
