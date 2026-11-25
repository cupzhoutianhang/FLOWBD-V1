"""Opt-in, hash-pinned original-PDF text supplements; original OCR is immutable."""
from pathlib import Path
import hashlib
import json
import os
import re

ROOT = Path(__file__).resolve().parents[3]
DATA = Path(__file__).resolve().parent / 'source_supplements'


def enabled():
    return os.environ.get('FLOWBD_PDF_SUPPLEMENTS', '').strip().lower() in {'1', 'true', 'yes', 'on'}


def manifests():
    return sorted(DATA.glob('*.json'))


def load(path):
    raw = path.read_bytes()
    value = json.loads(raw)
    if value.get('schema') != 'flowbd-pdf-supplements-v1':
        raise ValueError('Unsupported PDF supplement schema')
    target = (ROOT / value['source_pdf']).resolve()
    if not target.is_relative_to(ROOT) or not target.is_file():
        raise ValueError('PDF supplement source missing or outside workspace')
    if hashlib.sha256(target.read_bytes()).hexdigest() != value['source_pdf_sha256']:
        raise ValueError('PDF supplement original-file fingerprint changed')
    if not value.get('version') or not value.get('paper_title'):
        raise ValueError('PDF supplement identity is incomplete')
    ids = set()
    for record in value['records']:
        if record['id'] in ids or not isinstance(record.get('page'), int) or record['page'] < 1:
            raise ValueError('Invalid PDF supplement page/record identity')
        ids.add(record['id'])
        if hashlib.sha256(record['content'].encode('utf-8')).hexdigest() != record['text_sha256']:
            raise ValueError('PDF supplement text fingerprint changed')
        if not record.get('scope') or not record.get('section'):
            raise ValueError('PDF supplement scope is required')
    value['_manifest_sha256'] = hashlib.sha256(raw).hexdigest()
    return value


def matching_sources(question, existing_titles):
    if not enabled():
        return []
    question = question.casefold()
    titles = set(existing_titles)
    chunks = []
    for path in manifests():
        item = load(path)
        # A known paper must actually be retrieved, and the question must fit
        # its declared topic. No case IDs or unrelated global injection.
        if item['paper_title'] not in titles:
            continue
        if not any(all(term.casefold() in question for term in group) for group in item['query_groups']):
            continue
        for record in item['records']:
            audit = dict(source_pdf=item['source_pdf'], source_pdf_sha256=item['source_pdf_sha256'],
                         page=record['page'], section=record['section'], scope=record['scope'],
                         supplement_version=item['version'], manifest_sha256=item['_manifest_sha256'],
                         method=item['review_method'], independent_human_review=False,
                         original_ocr_modified=False)
            chunks.append(dict(type='pdf_supplement', source=item['paper_title'],
                               source_label=item['paper_title'] + '（原PDF核对补充）',
                               doc_id=item['paper_title'], corpus_version=item['version'],
                               parent_id=record['id'], content=record['content'], audit_record=audit,
                               location=f"{item['source_pdf']}#page={record['page']};section={record['section']};sha256={item['source_pdf_sha256']}"))
    return chunks


def resolve_ocr_notes(notes, sources):
    """Link an old OCR warning only to a same-paper, same-context PDF value.

    Both literal neighbors must match. A normal temperature in another step
    or a different paper does not resolve the warning.
    """
    from .quantity_grounding import comparison_text
    def compact(text):
        return re.sub(r'[^A-Za-z0-9\u3400-\u9fff°%‰.]', '', comparison_text(text))
    docs = {d['ref_id']: d for d in sources}
    for note in notes:
        old = docs.get(note['ref_id'], {})
        original = compact(note['quote'])
        value = note['value']
        marker = re.search(re.escape(value) + r'[%‰]', original)
        if not marker:
            continue
        left = original[max(0, marker.start()-6):marker.start()]
        right = original[marker.end():marker.end()+6]
        if len(left) < 4 or len(right) < 4:
            continue
        resolved = []
        for doc in sources:
            if doc.get('type') != 'pdf_supplement' or doc.get('source') != old.get('source'):
                continue
            for chunk in doc.get('chunks', []):
                audit = chunk.get('audit_record') or {}
                if not re.fullmatch(r'[0-9a-f]{64}', audit.get('source_pdf_sha256', '')) or not audit.get('page'):
                    continue
                text = compact(chunk['content'])
                if left + value + '°C' + right not in text:
                    continue
                resolved.append(dict(ref_id=doc['ref_id'], source_id=chunk['source_id'], value=value,
                                     corrected_literal=value+'℃', page=audit['page'],
                                     source_pdf_sha256=audit['source_pdf_sha256'],
                                     matched_left=left, matched_right=right))
        if resolved:
            note['resolved_by_pdf'] = resolved
            note['note'] = ('此旧OCR片段的单位已由本次同论文、同工序上下文的原PDF核对为'
                            + value + '℃；应引用resolved_by_pdf的Ref说明核对结果，不能仍称该工序真实单位未知。'
                            '旧OCR不改写；不据此推及其他工序。')
    return notes
