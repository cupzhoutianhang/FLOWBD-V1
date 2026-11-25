"""Candidate72 regressions: labelled table header units and stricter numeric guidance."""
from __future__ import annotations

import unittest

from agent.native_answer import STRICT_NUMERIC_RULE
from agent.quantity_grounding import _table_header_unit, _unit_expression_metrics, audit_quantities


def catalog(text, ref_id=1, quote_id='Q0001'):
    return {quote_id: {
        'ref_id': ref_id,
        'source_id': f'SRC:{ref_id}',
        'title': f'原文{ref_id}',
        'quote': text,
    }}


class LabelledTableHeaderUnit(unittest.TestCase):
    def test_label_and_unit_in_one_header_cell(self):
        text = ('<table><tr><td>循环次数</td><td>相变焓/kJ·kg-1</td><td>相变温度/℃</td></tr>'
                '<tr><td>150</td><td>126.5</td><td>66.38</td></tr></table>')
        answer = '- 150次循环后相变焓为126.5 kJ·kg⁻¹，相变温度为66.38℃[Ref-1]。'
        rows = audit_quantities(answer, catalog(text))
        self.assertEqual([row['status'] for row in rows], ['matched_quantity'] * 2)

    def test_header_lookup_returns_the_unit_expression(self):
        metrics = _unit_expression_metrics(_table_header_unit('相变焓/kJ·kg-1') or '')
        self.assertIsNotNone(metrics)
        self.assertIn('energy^1', metrics[0])
        self.assertIn('mass^-1', metrics[0])

    def test_plain_label_without_a_unit_is_still_rejected(self):
        self.assertIsNone(_table_header_unit('样品编号'))
        self.assertIsNone(_table_header_unit('A/B'))


class StricterNumericGuidance(unittest.TestCase):
    def test_rule_forbids_back_computed_ratios_and_uncited_columns(self):
        self.assertIn('不得反算为百分数', STRICT_NUMERIC_RULE)
        self.assertIn('每个数据列', STRICT_NUMERIC_RULE)
        self.assertIn('[Ref-n]', STRICT_NUMERIC_RULE)


if __name__ == '__main__':
    unittest.main()
