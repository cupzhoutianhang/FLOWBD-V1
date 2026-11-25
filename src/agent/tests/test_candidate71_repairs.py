"""Candidate71 regressions: negative ranges, formulas, per-column table sources, OCR units."""
from __future__ import annotations

import unittest

from agent.grounded_formatting import format_grounded_notes
from agent.native_answer import STRICT_NUMERIC_RULE
from agent.quantity_grounding import audit_quantities, comparison_text, quantities


def catalog(text, ref_id=1, quote_id='Q0001'):
    return {quote_id: {
        'ref_id': ref_id,
        'source_id': f'SRC:{ref_id}',
        'title': f'原文{ref_id}',
        'quote': text,
    }}


def statuses(answer, text, ref_id=1):
    return [row['status'] for row in audit_quantities(answer, catalog(text, ref_id=ref_id))]


class NegativeVoltageRange(unittest.TestCase):
    def test_spaced_power_does_not_swallow_the_next_negative_number(self):
        text = (r'the HER potential also slightly increased '
                r'$( - 1 . 6 6 0 \mathrm { V }  $ -1.766 V) as the pH increased')
        answer = '- HER电位由-1.660 V变为-1.766 V[Ref-1]。'
        rows = audit_quantities(answer, catalog(text))
        self.assertEqual([row['status'] for row in rows], ['matched_quantity'] * 2)
        self.assertEqual({row['dimension'] for row in rows}, {'voltage^1'})

    def test_signed_unit_power_still_parses(self):
        parsed = quantities('面积为3 m-2 与 5 m-2')
        self.assertEqual({q.dimension for q in parsed}, {'length^-2'})
        self.assertEqual(sorted(str(q.base_value) for q in parsed), ['3', '5'])


class FormulaPercent(unittest.TestCase):
    def test_percent_multiplier_in_a_formula_is_not_a_claim(self):
        answer = '- 质量损失率η=(m₀−m₁)/m₀×100%，当η接近0时最佳[Ref-1]。'
        self.assertEqual(audit_quantities(answer, catalog('质量损失率按公式计算。')), [])

    def test_plain_percent_claim_is_still_audited(self):
        answer = '- 质量损失率低于100%[Ref-1]。'
        rows = audit_quantities(answer, catalog('质量损失率控制在低水平。'))
        self.assertEqual([row['status'] for row in rows], ['unsupported_quantity_or_unit'])


class TableColumnSources(unittest.TestCase):
    def test_each_column_header_can_supply_its_own_source(self):
        catalog_items = {
            'Q0001': {'ref_id': 1, 'source_id': 'SRC:1', 'title': '原文1',
                      'quote': 'CA-PC/EG体系在干燥箱加热2 h，转速300 r/min。'},
            'Q0002': {'ref_id': 4, 'source_id': 'SRC:4', 'title': '原文4',
                      'quote': 'PW/PA/SA-EG体系搅拌30 min，成型压力4 MPa。'},
        }
        answer = (
            '| 参数 | CA-PC/EG体系[Ref-1] | PW/PA/SA-EG体系[Ref-4] |\n'
            '|---|---|---|\n'
            '| 加热时间 | 2 h | 30 min |\n'
            '| 转速 | 300 r/min | — |\n'
            '| 成型压力 | — | 4 MPa |'
        )
        rows = audit_quantities(answer, catalog_items)
        self.assertTrue(rows)
        self.assertTrue(all(row['status'] == 'matched_quantity' for row in rows), rows)
        self.assertTrue({row['citation_resolution'] for row in rows} <=
                        {'same_table_column_source', 'explicit_line'})

    def test_wrong_value_in_a_column_still_fails(self):
        catalog_items = {
            'Q0001': {'ref_id': 1, 'source_id': 'SRC:1', 'title': '原文1',
                      'quote': 'CA-PC/EG体系在干燥箱加热2 h。'},
            'Q0002': {'ref_id': 4, 'source_id': 'SRC:4', 'title': '原文4',
                      'quote': 'PW/PA/SA-EG体系搅拌30 min。'},
        }
        answer = (
            '| 参数 | CA-PC/EG体系[Ref-1] | PW/PA/SA-EG体系[Ref-4] |\n'
            '|---|---|---|\n'
            '| 加热时间 | 9 h | 30 min |'
        )
        rows = audit_quantities(answer, catalog_items)
        by_value = {row['quantity']: row['status'] for row in rows}
        self.assertEqual(by_value.get('9 h'), 'unsupported_quantity_or_unit')


class ChemicalFormulaAfterConcentration(unittest.TestCase):
    def test_concentration_followed_by_a_formula_keeps_its_unit(self):
        answer = '- 与0.4 M K₄[Fe(CN)₆]组装成液流电池[Ref-1]。'
        text = 'the derivative was combined with 0.4 M K4[Fe(CN)6] in a flow cell.'
        rows = audit_quantities(answer, catalog(text))
        self.assertEqual([row['status'] for row in rows], ['matched_quantity'])
        self.assertEqual(rows[0]['dimension'], 'concentration^1')


class OcrDegreeForms(unittest.TestCase):
    def test_textdegree_command_is_a_celsius_reading(self):
        text = r'复合材料的相变温度为 $6 4 . 1 3 \mathrm { ~ \textdegree C }$ 和81.56℃'
        answer = '- 相变温度为64.13℃和81.56℃[Ref-1]。'
        rows = audit_quantities(answer, catalog(text))
        self.assertEqual([row['status'] for row in rows], ['matched_quantity'] * 2)

    def test_letter_spaced_energy_density_matches_the_compact_form(self):
        text = r'was reported to achieve $1 2 . 5 \mathrm { \ W h \ L ^ { - 1 } }$ for 300 cycles'
        answer = '- 能量密度为12.5 Wh L⁻¹，循环300圈[Ref-1]。'
        rows = audit_quantities(answer, catalog(text))
        self.assertEqual([row['status'] for row in rows], ['matched_quantity'])
        self.assertEqual(rows[0]['dimension'], 'energy^1|volume^-1')


class UncertainPercentGlyph(unittest.TestCase):
    def test_celsius_assertion_with_percent_disclaimer_is_rewritten(self):
        text = r'复合相变材料置于 $8 0 \%$ 的干燥箱中干燥24 h。'
        answer = '- 石蜡为80℃（原文一处识别为"80%"，单位存疑）[Ref-1]。'
        cleaned, changes = format_grounded_notes(answer, catalog(text, ref_id=1), notes=[])
        self.assertIn('80%', cleaned)
        self.assertNotIn('80℃', cleaned)
        self.assertTrue(any(change['kind'] == 'restore_uncertain_percent_glyph' for change in changes))
        rows = audit_quantities(cleaned, catalog(text, ref_id=1))
        self.assertTrue(rows)
        self.assertTrue(all(row['status'] == 'qualified_uncertainty' for row in rows), rows)

    def test_confirmed_celsius_reading_is_kept(self):
        text = r'样品在 $8 0 \mathrm { { ^ \circ C } }$ 干燥箱中干燥24 h。'
        answer = '- 石蜡在80℃（干燥箱）加热24 h[Ref-1]。'
        cleaned, _ = format_grounded_notes(answer, catalog(text, ref_id=1), notes=[])
        self.assertIn('80℃', cleaned)


class UncitedParentheticalValues(unittest.TestCase):
    def test_uncited_parenthetical_threshold_is_removed(self):
        answer = '- DSC参数变化率（通常<10%）用于热性能保持，质量损失率用于形状稳定。'
        cleaned, changes = format_grounded_notes(answer, catalog('相变材料来回循环。'), notes=[])
        self.assertNotIn('10%', cleaned)
        self.assertIn('DSC参数变化率', cleaned)
        self.assertTrue(any(change['kind'] == 'drop_uncited_example_value' for change in changes))

    def test_cited_parenthetical_threshold_is_kept(self):
        answer = '- DSC参数变化率（通常<10%）用于热性能保持[Ref-1]。'
        cleaned, _ = format_grounded_notes(answer, catalog('判定标准为变化率<10%。'), notes=[])
        self.assertIn('10%', cleaned)


class StrictNumericGuidance(unittest.TestCase):
    def test_guidance_covers_conclusions_and_invented_thresholds(self):
        self.assertIn('结论', STRICT_NUMERIC_RULE)
        self.assertIn('表格', STRICT_NUMERIC_RULE)
        self.assertIn('[Ref-n]', STRICT_NUMERIC_RULE)
        self.assertIn('未设定统一量化阈值', STRICT_NUMERIC_RULE)


if __name__ == '__main__':
    unittest.main()
