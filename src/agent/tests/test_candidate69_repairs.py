"""Candidate69 regressions for citation scope, units and reviewer no-ops."""
from __future__ import annotations

import unittest
from decimal import Decimal

from agent.grounding_audit import discard_explicitly_cancelled_issues
from agent.quantity_grounding import audit_quantities, comparison_text, quantities


def catalog(text, ref_id=1, quote_id='Q0001'):
    return {quote_id: {
        'ref_id': ref_id,
        'source_id': f'SRC:{ref_id}',
        'title': f'原文{ref_id}',
        'quote': text,
    }}


def statuses(answer, text):
    return [row['status'] for row in audit_quantities(answer, catalog(text))]


class SingleSourceListInheritance(unittest.TestCase):
    def test_cited_section_covers_its_contiguous_single_source_list(self):
        text = '先置于干燥箱加热2 h，再磁力搅拌0.5 h，随后继续干燥24 h。'
        answer = (
            '**一、工艺参数**[Ref-1]\n\n'
            '- 薄膜封口后加热2 h；\n'
            '- 搅拌0.5 h；\n'
            '- 继续干燥24 h。'
        )
        rows = audit_quantities(answer, catalog(text))
        self.assertEqual([row['status'] for row in rows], ['matched_quantity'] * 3)
        self.assertEqual(
            {row['citation_resolution'] for row in rows},
            {'same_section_single_source'},
        )

    def test_inheritance_stops_at_the_next_uncited_heading(self):
        text = '先置于干燥箱加热2 h，再继续干燥3 h。'
        answer = (
            '**一、工艺参数**[Ref-1]\n\n'
            '- 加热2 h。\n\n'
            '**二、附加参数**\n\n'
            '- 继续干燥3 h。'
        )
        rows = audit_quantities(answer, catalog(text))
        by_seconds = {(row['quantity'], row['status']) for row in rows}
        self.assertIn(('2 h', 'matched_quantity'), by_seconds)
        self.assertIn(('3 h', 'missing_local_citation'), by_seconds)

    def test_multiple_sources_disable_list_inheritance(self):
        text = '先置于干燥箱加热2 h，再继续干燥3 h。'
        answer = (
            '**一、工艺参数**[Ref-1][Ref-2]\n\n'
            '- 加热2 h；\n'
            '- 继续干燥3 h。'
        )
        rows = audit_quantities(answer, catalog(text))
        self.assertTrue(rows)
        self.assertTrue(all(row['status'] == 'missing_local_citation' for row in rows))

    def test_cited_section_does_not_cover_a_separate_prose_paragraph(self):
        text = '样品置于干燥箱中加热2 h。'
        answer = (
            '**一、工艺参数**[Ref-1]\n\n'
            '本段只描述设备。\n\n'
            '样品置于干燥箱中加热2 h。'
        )
        rows = audit_quantities(answer, catalog(text))
        self.assertEqual(rows[0]['status'], 'missing_local_citation')

    def test_single_source_table_header_covers_its_rows(self):
        text = '样品在80℃干燥箱中加热2 h。'
        answer = (
            '| 参数 | 数值 | 来源[Ref-1] |\n'
            '|---|---|---|\n'
            '| 温度 | 80℃ |  |\n'
            '| 时间 | 2 h |  |'
        )
        rows = audit_quantities(answer, catalog(text))
        self.assertTrue(rows)
        self.assertEqual(
            {row['citation_resolution'] for row in rows},
            {'same_table_single_source'},
        )

    def test_multiple_table_sources_disable_row_inheritance(self):
        text = '样品在80℃干燥箱中加热2 h。'
        answer = (
            '| 参数 | 数值 | 来源[Ref-1][Ref-2] |\n'
            '|---|---|---|\n'
            '| 温度 | 80℃ |  |\n'
            '| 时间 | 2 h |  |'
        )
        rows = audit_quantities(answer, catalog(text))
        self.assertTrue(rows)
        self.assertTrue(all(row['status'] == 'missing_local_citation' for row in rows))

    def test_same_number_does_not_supply_a_missing_local_citation(self):
        text = '样品A在80℃下处理。'
        answer = '- 样品B在80℃下处理。'
        rows = audit_quantities(answer, catalog(text))
        self.assertEqual(rows[0]['status'], 'missing_local_citation')


class RamanWavenumberRepair(unittest.TestCase):
    def test_raman_joined_and_spaced_ranges_bind_both_endpoints(self):
        text = (
            'Raman spectroscopy reveals regions at 300400 and '
            '$6 0 0 { - } 7 0 0 ~ \\mathrm { c m ^ { - 1 } }$.'
        )
        answer = (
            'Raman光谱中300–400 cm⁻¹和600–700 cm⁻¹区域分别对应'
            'Mn–O键伸缩与弯曲振动[Ref-1]。'
        )
        rows = audit_quantities(answer, catalog(text))
        self.assertEqual(
            [row['status'] for row in rows],
            ['matched_quantity'] * 4,
        )
        self.assertEqual(
            [row['quantity'].split()[0] for row in rows],
            ['300', '400', '600', '700'],
        )

    def test_plain_hyphenated_raman_range_is_normalized(self):
        text = 'Raman regions at 300400 and 600 - 700 cm^-1.'
        answer = 'Raman区域为300–400 cm⁻¹和600–700 cm⁻¹[Ref-1]。'
        self.assertEqual(statuses(answer, text), ['matched_quantity'] * 4)

    def test_wavenumber_label_allows_the_same_narrow_range_repair(self):
        text = '波数区间为300400和600–700 cm^{-1}。'
        answer = '波数区间为300–400 cm⁻¹和600–700 cm⁻¹[Ref-1]。'
        self.assertEqual(statuses(answer, text), ['matched_quantity'] * 4)

    def test_non_raman_digit_join_is_not_split_into_a_range(self):
        text = 'The pore length was 300400 cm^-1 in the table.'
        answer = '孔径对应300–400 cm⁻¹[Ref-1]。'
        self.assertNotIn('300–400', comparison_text(text))
        self.assertTrue(all(
            row['status'] != 'matched_quantity'
            for row in audit_quantities(answer, catalog(text))
        ))

    def test_raman_repair_requires_a_wavenumber_unit(self):
        text = 'Raman regions at 300400 m and 600–700 m.'
        answer = 'Raman区域为300–400 m[Ref-1]。'
        self.assertNotIn('300–400', comparison_text(text))
        self.assertEqual(
            audit_quantities(answer, catalog(text))[0]['status'],
            'unsupported_quantity_or_unit',
        )


class DimensionBoundaries(unittest.TestCase):
    def test_ph_does_not_inherit_a_following_temperature_unit(self):
        rows = quantities('洗涤至pH≈7，100℃烘干3h。')
        temperature_values = {
            row.value for row in rows if row.dimension == 'temperature:C^1'
        }
        self.assertNotIn(Decimal('7'), temperature_values)
        self.assertIn(Decimal('100'), temperature_values)

    def test_ph_does_not_inherit_a_following_voltage_unit(self):
        rows = quantities('体系pH 7.5、1.6 V放电。')
        voltage_values = {row.value for row in rows if row.dimension == 'voltage^1'}
        self.assertEqual(voltage_values, {Decimal('1.6')})

    def test_ratio_endpoint_is_not_rewritten_as_a_percent(self):
        text = (
            'CA-PC与EG的比例分别为5:1、10:1、15:1、20:1、25:1；'
            '最佳质量配比在(6:1)~(10:1)之间。'
        )
        answer = (
            'CA-PC与EG质量分数为6%~10%，优化值为7:1[Ref-1]。'
        )
        rows = audit_quantities(answer, catalog(text))
        ratios = [row for row in rows if row['quantity'] in {'6%', '10%'}]
        self.assertEqual(
            [row['status'] for row in ratios],
            ['unsupported_quantity_or_unit'] * 2,
        )

    def test_ratio_is_not_converted_to_a_fatty_acid_fraction(self):
        text = 'CA-PC与EG的最佳质量配比为7:1。'
        rows = audit_quantities(
            'CA-PC与EG最佳质量配比为7:1，即脂肪酸低共熔物占87.5%[Ref-1]。',
            catalog(text),
        )
        self.assertEqual(rows[0]['quantity'], '87.5%')
        self.assertEqual(rows[0]['status'], 'unsupported_quantity_or_unit')

    def test_unsupported_voltage_is_not_excused_by_an_uncertainty_note(self):
        text = '该体系在pH 7.5下实现97%库仑效率和76%能量效率。'
        rows = audit_quantities(
            '该体系在pH 7.5、1.6 V（单位存疑）下实现97%库仑效率'
            '和76%能量效率[Ref-1]。',
            catalog(text),
        )
        voltage = next(row for row in rows if row['dimension'] == 'voltage^1')
        self.assertEqual(voltage['status'], 'unsupported_quantity_or_unit')


class LocalSubjectAndOcrUnits(unittest.TestCase):
    def test_uncited_quantity_still_fails_inside_a_single_source_section(self):
        text = '分别称取一定质量的CA和PC，在80%干燥箱中加热8 h。'
        answer = (
            '**一、工艺参数**\n\n'
            '- 薄膜封口后置于干燥箱中加热8 h'
            '（原文识别为“80%”，单位存疑）。'
        )
        rows = audit_quantities(answer, catalog(text))
        self.assertEqual(rows[0]['status'], 'missing_local_citation')

    def test_local_scope_after_qizhong_binds_two_methylimidazole(self):
        text = (
            'The electrolyte containing 0.2 M 2-mIm reached a decay rate of '
            '1.79%. It achieves a CE of 97.8% at a current density of '
            '100 mA cm^-2.'
        )
        answer = (
            'L-组氨酸与2-甲基咪唑均有效，其中0.2 M 2-mIm使容量衰减率'
            '降至1.79%，库仑效率达97.8%（100 mA·cm⁻²）[Ref-1]。'
        )
        rows = audit_quantities(answer, catalog(text))
        subject_rows = [
            row for row in rows
            if row['quantity'] in {'1.79%', '97.8%'}
            or row['dimension'] == 'current^1|length^-2'
        ]
        self.assertEqual(
            [row['status'] for row in subject_rows],
            ['matched_quantity'] * 3,
        )

    def test_l_his_claim_still_fails_when_source_reports_two_methylimidazole(self):
        text = 'The electrolyte containing 0.2 M 2-mIm reached a decay rate of 1.79%.'
        rows = audit_quantities(
            'L-组氨酸使容量衰减率降至1.79%[Ref-1]。',
            catalog(text),
        )
        self.assertEqual(rows[0]['status'], 'unsupported_subject_binding')

    def test_qizhong_scope_does_not_retroactively_bind_earlier_l_his_values(self):
        text = '2-mIm使容量衰减率降至1.79%。'
        answer = (
            'L-组氨酸添加量为3 M；其中2-mIm使容量衰减率降至1.79%[Ref-1]。'
        )
        rows = audit_quantities(answer, catalog(text))
        by_quantity = {row['quantity']: row['status'] for row in rows}
        self.assertEqual(by_quantity['3 M'], 'unsupported_quantity_or_unit')
        self.assertEqual(by_quantity['1.79%'], 'matched_quantity')

    def test_explicit_celsius_cannot_be_created_from_a_percent_ocr_reading(self):
        text = '可膨胀石墨在80%干燥箱中加热24 h，再微波膨胀。'
        rows = audit_quantities(
            '可膨胀石墨在80℃（原文识别存疑）干燥箱中加热24 h[Ref-1]。',
            catalog(text),
        )
        celsius = next(
            row for row in rows if row['dimension'] == 'temperature:C^1'
        )
        self.assertNotIn(
            celsius['status'],
            {'matched_quantity', 'qualified_uncertainty'},
        )

    def test_percent_ocr_reading_remains_qualified_when_not_rewritten(self):
        text = '可膨胀石墨在80%干燥箱中加热24 h，再微波膨胀。'
        rows = audit_quantities(
            '可膨胀石墨在80%（单位存疑）干燥箱中加热24 h[Ref-1]。',
            catalog(text),
        )
        self.assertEqual(
            [row['status'] for row in rows],
            ['qualified_uncertainty', 'qualified_uncertainty'],
        )

    def test_celsius_from_another_process_in_the_same_ref_still_fails(self):
        text = (
            'CA-PC在80℃干燥箱中加热2 h。'
            '可膨胀石墨在80%干燥箱中加热24 h，再微波膨胀。'
        )
        rows = audit_quantities(
            '微波法中可膨胀石墨在80℃干燥箱中加热24 h[Ref-1]。',
            catalog(text),
        )
        celsius = next(
            row for row in rows if row['dimension'] == 'temperature:C^1'
        )
        self.assertEqual(celsius['status'], 'unsupported_condition_binding')

    def test_explicitly_supported_celsius_still_passes(self):
        text = '可膨胀石墨在80℃干燥箱中加热24 h。'
        rows = audit_quantities(
            '可膨胀石墨在80℃干燥箱中加热24 h[Ref-1]。',
            catalog(text),
        )
        self.assertEqual(
            [row['status'] for row in rows],
            ['matched_quantity', 'matched_quantity'],
        )


class ReviewerNoopBoundary(unittest.TestCase):
    def setUp(self):
        self.fragments = {
            'F0016': {'span_id': 'A0016', 'text': '有据原句。'},
            'F0014': {'span_id': 'A0014', 'text': '另一片段。'},
        }

    def test_noop_with_q_id_and_contrast_but_no_action_is_cancelled(self):
        result, cancelled = discard_explicitly_cancelled_issues(
            {'issues': [{
                'fragment_id': 'F0016',
                'reason': (
                    'Q0002与Q0006核对后此条无误。然而Q0002所称工具与'
                    '本句用词不同，此为原文差异，非答案错误。'
                ),
                'replacement': '',
                'quote_ids': [],
            }]},
            self.fragments,
        )
        self.assertEqual(result['issues'], [])
        self.assertEqual(len(cancelled), 1)

    def test_noop_with_another_pending_fragment_remains_actionable(self):
        result, cancelled = discard_explicitly_cancelled_issues(
            {'issues': [{
                'fragment_id': 'F0016',
                'reason': 'F0016无误，但F0014需修正。',
                'replacement': '',
                'quote_ids': [],
            }]},
            self.fragments,
        )
        self.assertEqual(len(result['issues']), 1)
        self.assertEqual(cancelled, [])

    def test_empty_replacement_still_needs_a_noop_decision(self):
        result, cancelled = discard_explicitly_cancelled_issues(
            {'issues': [{
                'fragment_id': 'F0016',
                'reason': '该论断没有直接证据，应删除无据推断。',
                'replacement': '',
                'quote_ids': [],
            }]},
            self.fragments,
        )
        self.assertEqual(len(result['issues']), 1)
        self.assertEqual(cancelled, [])

    def test_nonempty_replacement_is_never_a_noop(self):
        result, cancelled = discard_explicitly_cancelled_issues(
            {'issues': [{
                'fragment_id': 'F0016',
                'reason': '此条无误，但应改写措辞。',
                'replacement': '修订片段。',
                'quote_ids': [],
            }]},
            self.fragments,
        )
        self.assertEqual(len(result['issues']), 1)
        self.assertEqual(cancelled, [])

    def test_noop_with_quote_ids_is_not_silently_dropped(self):
        result, cancelled = discard_explicitly_cancelled_issues(
            {'issues': [{
                'fragment_id': 'F0016',
                'reason': '此条无误。',
                'replacement': '',
                'quote_ids': ['Q0001'],
            }]},
            self.fragments,
        )
        self.assertEqual(len(result['issues']), 1)
        self.assertEqual(cancelled, [])

    def test_contradictory_delete_instruction_keeps_issue(self):
        result, cancelled = discard_explicitly_cancelled_issues(
            {'issues': [{
                'fragment_id': 'F0016',
                'reason': '此条无误，但仍应删除多余括注。',
                'replacement': '',
                'quote_ids': [],
            }]},
            self.fragments,
        )
        self.assertEqual(len(result['issues']), 1)
        self.assertEqual(cancelled, [])

    def test_incompatible_fragment_stays_invalid(self):
        result, cancelled = discard_explicitly_cancelled_issues(
            {'issues': [{
                'fragment_id': 'F0016',
                'span_id': 'A9999',
                'original_fragment': '错误片段',
                'reason': '此条无误。',
                'replacement': '',
                'quote_ids': [],
            }]},
            self.fragments,
        )
        self.assertEqual(len(result['issues']), 1)
        self.assertEqual(cancelled, [])


if __name__ == '__main__':
    unittest.main()
