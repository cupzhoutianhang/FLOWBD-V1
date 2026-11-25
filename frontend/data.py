"""Read-only view adapters. No model imports, network calls or data migrations."""
from __future__ import annotations

import csv
import ast
import json
import re
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
REPO = PROJECT.parent
CORPUS = PROJECT / 'pdf_to_md/extraction_results/downloaded_files'
METHODS = PROJECT / 'src/graph_rag/method_extraction'
LINEAGE = PROJECT / 'paper/method_evolution_v2/article_minimal_results'
SUITE = REPO / 'qa_runs/evidence_quality_20261010/suites/completion_final_27'


def read_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def read_csv(path: Path):
    with path.open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))


def optional_csv(path: Path):
    """Missing auxiliary metadata must not hide existing local full texts."""
    return read_csv(path) if path.is_file() else []


def annotate_method(row, identity, name_keys):
    """Apply PDF-supported display corrections without rewriting source identities."""
    path = METHODS / 'display_annotations/20261023_pdf_review.json'
    correction = read_json(path).get('nodes', {}).get(identity) if path.is_file() else None
    if not correction:
        return row
    item = dict(row, original_extraction_name=correction['original_extraction_name'],
                display_correction=correction, display_annotation=correction['annotation'])
    for key in name_keys:
        item[key] = correction['display_name']
    item['notes'] = (str(item.get('notes') or '') + ' ' + correction['annotation']).strip()
    return item


def papers():
    methods = optional_csv(METHODS / 'methods.csv')
    years = {r['paper_id']: r.get('year', '') for r in optional_csv(METHODS / 'publish_year_report.csv')}
    # Incremental candidates retain their own provenance instead of rewriting audited CSVs.
    known = {(r['paper_id'], r.get('method_name', '')) for r in methods}
    for folder in sorted(METHODS.glob('method_outputs_import_*')):
        for path in sorted(folder.glob('*.json')):
            record = read_json(path)
            pid = record['paper_id']
            years.setdefault(pid, str(record.get('year', '')))
            for kind, key in [('own', 'own_methods'), ('ref', 'referenced_methods')]:
                for method in record.get(key, []):
                    if (pid, method['name']) in known:
                        continue
                    methods.append({**method, 'paper_id': pid, 'method_name': method['name'], 'kind': kind,
                                    'status': 'candidate', 'review_status': 'unreviewed',
                                    'source_batch': folder.name})
                    known.add((pid, method['name']))
    by_paper = {}
    for row in methods:
        row = annotate_method(row, row['paper_id'] + '::' + str(row.get('method_name', '')), ('method_name', 'name'))
        by_paper.setdefault(row['paper_id'], []).append(row)
    result = []
    for directory in sorted(CORPUS.iterdir(), key=lambda p: p.name.casefold()):
        if not directory.is_dir():
            continue
        title = re.sub(r'^\d+[.、\s]+', '', directory.name).strip()
        records = by_paper.get(directory.name, by_paper.get(title, []))
        own = next((m for m in records if m.get('kind') == 'own'), {})
        category = own.get('primary_storage_domain') or own.get('subfield')
        inferred = not bool(category)
        if not category:
            category = ('相变材料' if re.search(r'相变|phase.change|PCM', title, re.I) else
                        '液流电池' if re.search(r'液流|flow.batter|redox', title, re.I) else
                        '催化与反应' if re.search(r'催化|加氢|cataly|hydrogenation', title, re.I) else '未分类')
        year = years.get(directory.name, years.get(title, own.get('year', '')))
        if year and re.fullmatch(r'\d{4}(?:\.0)?', str(year)):
            year = str(int(float(year)))
        else:
            year = ''
        result.append({'id': directory.name, 'title': title, 'year': year, 'category': category,
                       'inferred_category': inferred, 'has_text': (directory / 'full.md').is_file(),
                       'methods': records, 'search': title + ' ' + ' '.join(str(v) for r in records for v in r.values())})
    return result


def paper_text(paper_id: str):
    path = (CORPUS / paper_id / 'full.md').resolve()
    if not path.is_relative_to(CORPUS.resolve()) or not path.is_file():
        raise FileNotFoundError('该文献没有可读取的本地 Markdown 原文。')
    return path.read_text(encoding='utf-8-sig')


def lineage_cases():
    return read_json(LINEAGE / 'lineage_cases_unified/all_cases_manifest.json')['cases']


def lineage_case(case_id: str):
    allowed = {c['case_id'] for c in lineage_cases()}
    if case_id not in allowed:
        raise ValueError('未知专题')
    directory = LINEAGE / 'lineage_cases_unified' / case_id
    case = read_json(directory / 'frontend_case.json')
    case['nodes'] = [annotate_method(row, row.get('source_node_id'), ('node_name', 'display_name', 'method_or_material'))
                     for row in case['nodes']]
    layout = directory / 'diagram_layout.json'
    if layout.is_file():
        try:
            case['diagram_layout'] = read_json(layout)
        except (OSError, ValueError) as error:
            case['diagram_layout_error'] = f'布局配置无法读取：{error}'
    return case


def atlas_versions():
    directory = METHODS / 'landscape/versions'
    manifest = read_json(directory / 'active.json')
    return manifest['active'], manifest['versions']


def method_atlas(version: str):
    _, allowed = atlas_versions()
    if version not in allowed:
        raise ValueError('未知方法版图版本')
    atlas = read_json(METHODS / 'landscape/versions' / version / 'atlas.json')
    atlas['nodes'] = [annotate_method(row, row['id'], ('name', 'display_name')) for row in atlas['nodes']]
    return atlas


def source_path(source):
    """Resolve only existing corpus files; never open arbitrary model-supplied paths."""
    for key in ('doc_id', 'source_label', 'source'):
        name = str(source.get(key) or '')
        if not name or Path(name).name != name:
            continue
        path = (CORPUS / name / 'full.md').resolve()
        if path.is_relative_to(CORPUS.resolve()) and path.is_file():
            return path
    return None


def evaluation():
    receipt = read_json(SUITE / 'completion_receipt_20261015.json')
    acceptance = read_json(SUITE / 'acceptance.json')
    jobs = acceptance.get('failed_latest_jobs', [])
    attempts = {str(j['attempt']): dict(j) for j in jobs}
    for run in sorted({j['run_id'] for j in jobs}):
        # Read each JSONL once. Never execute suites or import their runners.
        path = REPO / 'qa_runs/evidence_quality_20261010/runs' / run / 'results.jsonl'
        if not path.is_file():
            continue
        with path.open(encoding='utf-8') as handle:
            for line in handle:
                if not line.strip():
                    continue
                row = json.loads(line)
                identity = str(row.get('attempt') or row.get('attempt_id') or '')
                if identity in attempts:
                    attempts[identity]['record'] = row
                else:
                    # Some suites record the attempt identity below the result envelope.
                    for key in ('result', 'meta'):
                        nested = row.get(key)
                        if isinstance(nested, dict) and str(nested.get('attempt') or nested.get('attempt_id') or '') in attempts:
                            attempts[str(nested.get('attempt') or nested.get('attempt_id'))]['record'] = row
    return {'receipt': receipt, 'acceptance': acceptance, 'issues': list(attempts.values())}


def failure_reason(issue):
    record = issue.get('record') or {}
    for key in ('error', 'failure_reason', 'reason', 'exception'):
        if record.get(key):
            return str(record[key])
    logs = record.get('logs') or []
    if isinstance(logs, str):
        try:
            logs = ast.literal_eval(logs)
        except (ValueError, SyntaxError):
            logs = [logs]
    for line in reversed(logs):
        if '答案生成失败:' in str(line) or '答案生成失败：' in str(line):
            return re.split(r'答案生成失败[:：]', str(line), maxsplit=1)[-1].strip()
    errors = (record.get('answer_quality') or {}).get('operation_errors')
    if errors:
        return '；'.join(map(str, errors))
    return '查看原始记录；未提供可直接提取的失败原因。'


def source_views(sources):
    """Preserve ref identities and the complete source list, including legacy gaps."""
    result = []
    for source in sources or []:
        item = dict(source)
        item['ref_id'] = source.get('ref_id')  # No positional renumbering.
        item['title'] = str(source.get('source_label') or source.get('source') or '来源题名未记录')
        item['content'] = str(source.get('content') or '')
        item['location_label'] = str(source.get('location') or source.get('sentence_id') or '来源片段；未记录逐句定位')
        result.append(item)
    return result
