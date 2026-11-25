"""Annotate an answer whose values could not be verified, never refuse it.

Strict grounding keeps finding problems in model drafts. Instead of returning an
empty "无法生成答案", the final draft is returned with the suspect values marked
in place and a closing declaration listing every unresolved check.
"""
from __future__ import annotations

import re

MARK = '〔待核〕'
DECLARATION_TITLE = '**待核实声明**'

STATUS_LABELS = {
    'missing_local_citation': '该处数值缺少就近来源引用',
    'unsupported_quantity_or_unit': '该数值或单位未在所引来源中找到',
    'unsupported_subject_binding': '来源中的主体与这句话不一致',
    'unsupported_condition_binding': '来源中的温度/条件/单位与本句不一致',
}


def _annotate_value(answer: str, quantity: str, used: set[int]) -> tuple[str, bool]:
    """Mark one occurrence of a raw quantity, skipping already annotated ones."""
    if not quantity:
        return answer, False
    start = 0
    while True:
        index = answer.find(quantity, start)
        if index < 0:
            return answer, False
        end = index + len(quantity)
        if end not in used:
            used.add(end)
            return answer[:end] + MARK + answer[end:], True
        start = index + 1


def annotate_unverified(answer, issues, quantity_checks, limit=12):
    """Return (annotated_answer, declaration_rows) for the remaining checks."""
    rows = []
    used: set[int] = set()
    annotated = str(answer or '')
    for item in quantity_checks or []:
        status = str(item.get('status') or '')
        if status in {'matched_quantity', 'qualified_uncertainty', 'diagnostic_failed'}:
            continue
        quantity = str(item.get('quantity') or '')
        line_number = item.get('line_number')
        annotated, marked = _annotate_value(annotated, quantity, used)
        rows.append({
            'claim_id': item.get('claim_id'),
            'line_number': line_number,
            'quantity': quantity,
            'status': status,
            'reason': STATUS_LABELS.get(status, '该处未通过来源校验'),
            'marked_inline': marked,
        })
        if len(rows) >= limit:
            break
    other = [str(issue) for issue in (issues or []) if str(issue) not in
             {f"{row['claim_id']} 数值/单位/主体引用检查未通过({row['status']})：{row['quantity']}"
              for row in rows}]
    for text in other[:limit]:
        rows.append({'claim_id': None, 'line_number': None, 'quantity': None,
                     'status': 'other_check', 'reason': text, 'marked_inline': False})
    if not rows:
        return annotated, []
    lines = ['', '---', DECLARATION_TITLE +
             '：以下内容未通过本系统的来源校验，采用前请核对原文；标注仅指出风险，不代表结论一定错误。']
    for row in rows:
        if row['claim_id'] and row['quantity']:
            lines.append(f"- {row['claim_id']}：{row['quantity']} —— {row['reason']}")
        else:
            lines.append(f"- {row['reason']}")
    return annotated.rstrip() + '\n' + '\n'.join(lines) + '\n', rows


def strip_annotations(answer):
    """Remove inline marks and the declaration block (for replay/diagnostics)."""
    text = str(answer or '')
    text = text.split('\n---\n' + DECLARATION_TITLE)[0]
    return re.sub(re.escape(MARK), '', text)
