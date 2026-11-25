"""Candidate70 regressions: OCR unit/range parsing and gap-statement cleanup."""
from __future__ import annotations

import unittest

from agent.grounded_formatting import format_grounded_notes
from agent.quantity_grounding import (
    _table_header_unit,
    _unit_expression_metrics,
    audit_quantities,
    comparison_text,
    quantities,
)


def catalog(text, ref_id=1, quote_id='Q0001'):
    return {quote_id: {
        'ref_id': ref_id,
        'source_id': f'SRC:{ref_id}',
        'title': f'原文{ref_id}',
        'quote': text,
    }}


def statuses(answer, text, ref_id=1):
    return [row['status'] for row in audit_quantities(answer, catalog(text, ref_id=ref_id))]


class LetterSpacedUnitRepair(unittest.TestCase):
    def test_stray_backslashes_inside_letter_spaced_unit_keep_the_unit(self):
        text = (r'delivering a cumulative plating capacity of 80 Ah '
                r'$\mathrm { c m } ^ { - 2 }$ —about 11.4-fold improvement over the '
                r'baseline system $( 7 . 0 \mathrm { \ A h \ c m } ^ { - 2 } )$ This work')
        answer = '- 累积镀覆容量相对基准提升约11.4倍（基准7.0 Ah cm⁻²）[Ref-1]。'
        rows = audit_quantities(answer, catalog(text))
        self.assertEqual([row['status'] for row in rows], ['matched_quantity'])
        self.assertIn('7.0', rows[0]['quantity'])

    def test_multi_letter_tex_command_is_not_treated_as_spaced_unit(self):
        # \circ must still become a degree glyph, not a compacted unit list.
        self.assertIn('°C', comparison_text(r'$80^{\circ}\mathrm{C}$'))
        self.assertEqual(
            [q.dimension for q in quantities(r'样品在 $8 0 \mathrm { { ^ \circ C } }$ 干燥')],
            ['temperature:C^1'],
        )


class BracedRangeSeparatorRepair(unittest.TestCase):
    def test_braced_hyphen_between_digits_is_a_range(self):
        text = r'small $1 0 { - } 2 0 ~ \mathrm { k W }$ flow battery systems'
        answer = '- 小型10–20 kW液流电池系统具有重要潜力[Ref-1]。'
        rows = audit_quantities(answer, catalog(text))
        self.assertEqual([row['status'] for row in rows], ['matched_quantity'] * 2)
        self.assertEqual({row['dimension'] for row in rows}, {'power^1'})

    def test_braced_negative_sign_is_still_negative(self):
        text = r'过电位为 $- 5 9 \mathrm { m V }$ 。'
        answer = '- 过电位为-59 mV[Ref-1]。'
        self.assertEqual(statuses(answer, text), ['matched_quantity'])


class TableHeaderUnitRepair(unittest.TestCase):
    def test_dotted_slash_prefixed_header_unit_is_accepted(self):
        text = ('<table><tr><td></td><td>/g.m-2</td><td>/mm</td></tr>'
                '<tr><td>PXFB PW03</td><td>122</td><td>0.39</td></tr></table>')
        answer = '- PXFB PW03面密度122 g·m⁻²，厚度0.39 mm[Ref-1]。'
        rows = audit_quantities(answer, catalog(text))
        self.assertEqual([row['status'] for row in rows], ['matched_quantity'] * 2)

    def test_numeric_table_cells_never_become_headers(self):
        self.assertIsNone(_table_header_unit('80%'))
        self.assertIsNone(_table_header_unit('122'))
        metrics = _unit_expression_metrics(_table_header_unit('/g.m-2') or '')
        self.assertIsNotNone(metrics)
        self.assertTrue(metrics[0].startswith('length^-2'))
        self.assertIn('mass^1', metrics[0])


class PotentialWindowRepair(unittest.TestCase):
    def test_citation_number_is_not_read_as_a_voltage(self):
        text = 'Nonaqueous flow batteries offer a wide voltage window.'
        answer = '- 非水液流电池电压窗口宽，被认为适用于电网长时储能[Ref-5]。'
        rows = audit_quantities(answer, catalog(text, ref_id=5))
        self.assertEqual(rows, [])

    def test_window_inference_still_works_without_citation_digits(self):
        text = 'the potential window is confined to 1.23'
        answer = '- 电位窗口约1.23 V[Ref-1]。'
        rows = audit_quantities(answer, catalog(text))
        self.assertEqual([row['status'] for row in rows], ['matched_quantity'])
        self.assertEqual(rows[0]['matches'][0]['unit_origin'], 'context_inferred')


class OcrDegreeGlyphRepair(unittest.TestCase):
    def test_nine_c_in_temperature_list_is_repaired(self):
        text = (r'分别在 $6 5 \mathrm { { ^ circ C } }$ 、 $7 0 \mathrm { { ^ \circ C } }$ '
                r'和 $7 5 \mathrm { { 9 C } }$ 的烘箱中充热 $3 0 \mathrm { m i n }$ ，有机质均未出现泄漏')
        answer = '- 在65℃、70℃、75℃的烘箱中充热30 min均未出现泄漏[Ref-1]。'
        rows = audit_quantities(answer, catalog(text))
        self.assertEqual([row['status'] for row in rows], ['matched_quantity'] * 4)

    def test_nine_c_outside_a_temperature_context_is_not_repaired(self):
        text = r'样品编号 $7 5 \mathrm { { 9 C } }$ 记录在案。'
        answer = '- 样品编号75℃记录在案[Ref-1]。'
        self.assertEqual(statuses(answer, text), ['unsupported_quantity_or_unit'])


class PercentRangeRepair(unittest.TestCase):
    def test_percent_range_keeps_two_ratios_and_no_absurd_power(self):
        text = (r'降低了 $1 . 7 7 \% \sim 1 0 . 9 4 \%$ 。'
                r'另一体系降低了 $3 . 0 0 \% \sim 1 1 . 2 1 \%$ 。')
        answer = '- 潜热随添加量增加而降低1.77%~11.21%[Ref-1]。'
        rows = audit_quantities(answer, catalog(text))
        self.assertEqual([row['status'] for row in rows], ['matched_quantity'] * 2)
        self.assertEqual({row['dimension'] for row in rows}, {'ratio^1'})


class GapStatementCleanup(unittest.TestCase):
    def test_uncited_uncertain_gap_bullet_drops_the_repeated_token(self):
        text = r'滴加后置于 $8 0 \%$ 的干燥箱中干燥24 h。'
        answer = (
            '**一、工艺参数**[Ref-1]\n\n'
            '- 薄膜封口后干燥24 h。\n\n'
            '**未获得支持的参数**\n\n'
            '- 干燥温度的准确数值（"80%"单位存疑，不可确认为℃）'
        )
        cleaned, changes = format_grounded_notes(answer, catalog(text), notes=[])
        self.assertNotIn('80%', cleaned)
        self.assertIn('干燥温度的准确数值', cleaned)
        self.assertTrue(any(change['kind'] == 'drop_uncited_uncertain_gap_value' for change in changes))

    def test_uncited_gap_bullet_with_supported_number_is_kept(self):
        text = r'样品在 $8 0 \mathrm { { ^ \circ C } }$ 干燥箱中干燥24 h。'
        answer = (
            '**一、工艺参数**[Ref-1]\n\n'
            '- 干燥24 h。\n\n'
            '**二、未获得支持的参数**[Ref-1]\n\n'
            '- 干燥温度的准确数值（80℃单位存疑）'
        )
        cleaned, _ = format_grounded_notes(answer, catalog(text), notes=[])
        self.assertIn('80℃', cleaned)

    def test_unsupported_example_threshold_parenthetical_is_removed(self):
        text = '各研究依据体系特点进行定性或相对定量判断。'
        answer = ('- 本次检索未找到文献明确给出DSC参数变化的统一量化阈值'
                  '（如"潜热衰减<10%即合格"），各研究依据体系特点进行定性判断[Ref-1]。')
        cleaned, changes = format_grounded_notes(answer, catalog(text), notes=[])
        self.assertNotIn('10%', cleaned)
        self.assertIn('统一量化阈值', cleaned)
        self.assertTrue(any(change['kind'] == 'drop_unsupported_example_value' for change in changes))

    def test_supported_example_parenthetical_is_kept(self):
        text = '文献给出的合格判据为潜热衰减<10%即合格。'
        answer = ('- 本次检索未找到文献明确给出统一量化阈值'
                  '（如"潜热衰减<10%即合格"），各研究依据体系特点进行定性判断[Ref-1]。')
        cleaned, _ = format_grounded_notes(answer, catalog(text), notes=[])
        self.assertIn('10%', cleaned)

    def test_uncited_example_value_in_prose_is_removed(self):
        text = '各研究依据体系特点进行定性或相对定量判断。'
        answer = ('**关键区分**：无泄漏证明的是宏观形态完整性。'
                  '即使热性能有所衰减（如潜热下降9.5%），只要无泄漏仍可判定为形状稳定。')
        cleaned, changes = format_grounded_notes(answer, catalog(text), notes=[])
        self.assertNotIn('9.5%', cleaned)
        self.assertIn('热性能有所衰减', cleaned)
        self.assertTrue(any(change['kind'] == 'drop_uncited_example_value' for change in changes))

    def test_cited_example_value_in_prose_is_kept(self):
        text = '潜热衰减<10%即合格。'
        answer = '即使热性能有所衰减（如潜热下降9.5%），仍可判定为形状稳定[Ref-1]。'
        cleaned, _ = format_grounded_notes(answer, catalog(text), notes=[])
        self.assertIn('9.5%', cleaned)


if __name__ == '__main__':
    unittest.main()
