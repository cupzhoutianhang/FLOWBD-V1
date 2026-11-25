"""Offline regression gates for candidate64 repair work."""
from __future__ import annotations

import json
import math
import unittest
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from frontend import controller
from agent.answer_grounding import check_citations, verify_semantic_support
from agent.evidence_graph.coordinator import IterativeCoordinator
from agent.grounding_audit import bind_review_fragments, discard_explicitly_cancelled_issues
from agent.grounded_formatting import format_grounded_notes
from agent.mechanism_boundaries import claim_issues
from agent.native_answer import NativeAnswerError
from agent.part5_multiagent_integration import _post_audit_native_result
from agent.quantity_grounding import audit_quantities


def catalog(text):
    return {'Q0001': {'ref_id': 1, 'source_id': 'SRC:test', 'title': '原文', 'quote': text}}


class NativeFinalizationStateMachine(unittest.TestCase):
    def test_reviewer_structure_failure_degrades_without_discarding_valid_draft(self):
        metadata = {'strict_validation_enabled': True, 'structured_calls': []}
        semantic = {'status': 'review_failed', 'review_structure_valid': False,
                    'repair_confirmation_status': 'review_failed'}
        answer, result = _post_audit_native_result(
            '有原文支持的有效草稿[Ref-1]。', metadata, semantic, [], [])
        self.assertEqual(answer, '有原文支持的有效草稿[Ref-1]。')
        self.assertIs(result, metadata)
        self.assertTrue(result['post_audit_validation']['passed'])
        self.assertTrue(result['post_audit_validation']['reviewer_degraded'])
        self.assertFalse(result['post_audit_validation']['semantic_support_verified'])
        self.assertNotIn('post_audit_rejected_draft', result)

    def test_deterministic_issue_is_annotated_instead_of_discarding_the_draft(self):
        metadata = {'strict_validation_enabled': True, 'structured_calls': []}
        semantic = {'status': 'review_failed', 'review_structure_valid': False,
                    'repair_confirmation_status': 'review_failed'}
        answer, result = _post_audit_native_result(
            '无据草稿。', metadata, semantic, [], ['unsupported_quantity'])
        self.assertTrue(answer.startswith('无据草稿。'))
        self.assertEqual(result['post_audit_rejected_draft'], '无据草稿。')
        self.assertTrue(result['post_audit_annotated'])
        self.assertFalse(result['post_audit_validation']['passed'])
        self.assertTrue(result['post_audit_validation']['reviewer_degraded'])
        self.assertIn('待核实声明', answer)


class FrontendJsonSafety(unittest.TestCase):
    def test_nested_failure_payload_is_json_safe_and_replay_equal(self):
        class Opaque:
            def __str__(self):
                return 'opaque-value'

        raw = {
            'content': '失败态', 'nan': float('nan'), 'inf': float('inf'),
            'decimal': Decimal('1.25'), 'path': Path('evidence/graph.json'),
            'tuple': (1, 2), 'set': {'a', 'b'}, 'error': RuntimeError('boom'),
            'opaque': Opaque(), 'raw_response': 'x' * 50000,
            'structured_calls': [{'raw_response': 'y' * 50000, 'usage': {'total_tokens': 9}}],
            'evidence_graph': {'nodes': [{'id': 'n1', 'observations': [{'value': Decimal('2.0')}]}],
                               'edges': [], 'stats': {'nodes': 1}},
        }
        clean = controller.json_safe(raw)
        encoded = json.dumps(clean, ensure_ascii=False, allow_nan=False)
        restored = json.loads(encoded)
        self.assertEqual(restored, clean)
        self.assertIsNone(clean['nan'])
        self.assertIsNone(clean['inf'])
        self.assertEqual(clean['decimal'], '1.25')
        self.assertEqual(clean['path'], 'evidence/graph.json')
        self.assertEqual(clean['tuple'], [1, 2])
        self.assertEqual(sorted(clean['set']), ['a', 'b'])
        self.assertIn('boom', clean['error'])
        self.assertLessEqual(len(clean['raw_response']), 40000)
        self.assertLessEqual(len(clean['structured_calls'][0]['raw_response']), 40000)
        self.assertEqual(clean['evidence_graph']['nodes'][0]['observations'][0]['value'], '2.0')


class SharedUnitAndConditionBinding(unittest.TestCase):
    def test_shared_unit_time_list_is_fully_bound(self):
        source = '该实验考察的搅拌时间分别为30、45、60、75、90、105、120、135、150、165 min共10种时长。'
        answer = '该实验考察的搅拌时间分别为30、45、60、75、90、105、120、135、150、165 min共10种时长[Ref-1]。'
        rows = audit_quantities(answer, catalog(source))
        time_rows = [row for row in rows if row['dimension'] == 'time^1']
        self.assertEqual(len(time_rows), 10)
        self.assertTrue(all(row['status'] == 'matched_quantity' for row in time_rows))

    def test_unrelated_prior_process_times_do_not_bind_to_later_quantity(self):
        source = '先在0.5 h内混合，随后静置8 h。样品在80%条件下处理。'
        rows = audit_quantities('样品在80%条件下处理[Ref-1]。', catalog(source))
        self.assertEqual(rows[0]['status'], 'matched_quantity')

    def test_shared_list_member_and_figure_time_are_condition_compatible(self):
        source = ('搅拌时间分别为30、45、60、75、90、105、120、135、150、165 min。'
                  '图5为90 min搅拌样品。')
        answer = ('搅拌时间分别为30、45、60、75、90、105、120、135、150、165 min；'
                  '其中90 min样品见讨论[Ref-1]。')
        rows = audit_quantities(answer, catalog(source))
        time_rows = [row for row in rows if row['dimension'] == 'time^1']
        self.assertTrue(time_rows)
        self.assertTrue(all(row['status'] == 'matched_quantity' for row in time_rows))

    def test_same_scalar_uses_the_condition_compatible_source_occurrence(self):
        source = ('CA-PC在80%干燥箱中加热2 h。'
                  'EG在80%干燥箱中加热24 h。'
                  '复合物在80%干燥箱中加热8 h。')
        answer = 'EG在80%干燥箱中加热24 h（原文单位存疑）[Ref-1]。'
        rows = audit_quantities(answer, catalog(source))
        ratio = next(row for row in rows if row['dimension'] == 'ratio^1')
        self.assertEqual(ratio['status'], 'qualified_uncertainty')
        self.assertEqual(ratio['blocking_condition_binding_issues'], [])

    def test_unit_uncertainty_disclaimer_can_span_multiple_process_times(self):
        source = ('CA-PC在80%干燥箱中加热2 h。'
                  'EG在80%干燥箱中加热24 h。'
                  '复合物在80%干燥箱中加热8 h。')
        answer = '多处温度原文识别为"80%"，单位存疑[Ref-1]。'
        rows = audit_quantities(answer, catalog(source))
        self.assertEqual(rows[0]['status'], 'qualified_uncertainty')

    def test_table_temperature_binds_to_same_process_time_row(self):
        source = '将CA-PC在80°C干燥箱中加热2 h。'
        answer = ('| 工序 | 参数 | 数值 |\n'
                  '|---|---|---|\n'
                  '| 低共熔物熔化 | 温度 | 80°C[Ref-1] |\n'
                  '| 低共熔物熔化 | 时间 | 2 h[Ref-1] |')
        rows = audit_quantities(answer, catalog(source))
        temperature = next(row for row in rows if row['dimension'] == 'temperature:C^1')
        self.assertEqual(temperature['status'], 'matched_quantity')

    def test_unit_uncertainty_does_not_excuse_a_conflicting_time(self):
        source = 'EG在80%干燥箱中加热24 h。'
        answer = 'EG在80%干燥箱中加热2 h（单位存疑）[Ref-1]。'
        rows = audit_quantities(answer, catalog(source))
        ratio = next(row for row in rows if row['dimension'] == 'ratio^1')
        self.assertEqual(ratio['status'], 'unsupported_condition_binding')

    def test_ocr_percent_can_match_same_time_celsius_occurrence(self):
        source = 'CA-PC在80°C干燥箱中加热2 h。'
        answer = '原文该处温度识别为80%（单位存疑）[Ref-1]，加热2 h。'
        rows = audit_quantities(answer, catalog(source))
        ratio = next(row for row in rows if row['dimension'] == 'ratio^1')
        self.assertEqual(ratio['status'], 'qualified_uncertainty')

    def test_ocr_percent_cannot_borrow_a_different_time_celsius_occurrence(self):
        source = 'CA-PC在80°C干燥箱中加热2 h。'
        answer = '原文该处温度识别为80%（单位存疑）[Ref-1]，加热3 h。'
        rows = audit_quantities(answer, catalog(source))
        ratio = next(row for row in rows if row['dimension'] == 'ratio^1')
        self.assertEqual(ratio['status'], 'unsupported_condition_binding')

    def test_per_mille_disclaimer_can_match_a_temperature_ocr_candidate(self):
        source = 'CA-PC在80°C干燥箱中加热2 h。'
        answer = '| 温度参数 | 多处识别为"80‰" | 单位存疑，不可确认为80℃[Ref-1] |'
        rows = audit_quantities(answer, catalog(source))
        ratio = next(row for row in rows if row['dimension'] == 'ratio^1')
        self.assertEqual(ratio['status'], 'qualified_uncertainty')

    def test_html_table_header_percent_unit_matches_bare_source_cell(self):
        source = ('<table><tr><td>m</td><td>C=O/%</td><td>C-OH/%</td></tr>'
                  '<tr><td>PXFB PW03</td><td>0.78</td><td>12.92</td></tr></table>')
        rows = audit_quantities('羰基含量由0.78%增至1.38%[Ref-1]。', catalog(source))
        ratio = next(row for row in rows if row['quantity'] == '0.78%')
        self.assertEqual(ratio['status'], 'matched_quantity')
        self.assertEqual(ratio['matches'][0]['unit_origin'], 'table_header')

    def test_markdown_table_header_unit_applies_to_answer_row(self):
        source = ('| 样品 | 效率/% |\n'
                  '|---|---|\n'
                  '| A | 80 |')
        answer = ('| 样品 | 效率/% |\n'
                  '|---|---|\n'
                  '| A | 80[Ref-1] |')
        rows = audit_quantities(answer, catalog(source))
        ratio = next(row for row in rows if row['dimension'] == 'ratio^1')
        self.assertEqual(ratio['quantity'], '80%')
        self.assertEqual(ratio['unit_origin'], 'table_header')
        self.assertEqual(ratio['status'], 'matched_quantity')

    def test_table_without_header_unit_does_not_guess_percent(self):
        source = ('| 样品 | 数值 |\n'
                  '|---|---|\n'
                  '| A | 80 |')
        rows = audit_quantities('样品A的效率为80%[Ref-1]。', catalog(source))
        self.assertEqual(rows[0]['status'], 'unsupported_quantity_or_unit')

    def test_table_unit_must_come_from_the_matching_column(self):
        source = ('| 样品 | 温度/°C | 效率/% |\n'
                  '|---|---|---|\n'
                  '| A | 80 | 0.8 |')
        rows = audit_quantities('样品A的效率为80%[Ref-1]。', catalog(source))
        self.assertEqual(rows[0]['status'], 'unsupported_quantity_or_unit')

    def test_ordinary_prose_bare_number_does_not_guess_a_unit(self):
        rows = audit_quantities('样品A的效率为80%[Ref-1]。', catalog('样品A的数值为80。'))
        self.assertEqual(rows[0]['status'], 'unsupported_quantity_or_unit')

    def test_tex_micro_prefix_is_compared_as_micrometre(self):
        source = r'宽度 $2 0 0 \mu \mathrm { m }$，间距 $1 \mathrm { m m }$。'
        rows = audit_quantities('宽度200 μm[Ref-1]。', catalog(source))
        length = next(row for row in rows if row['dimension'] == 'length^1')
        self.assertEqual(length['status'], 'matched_quantity')
        self.assertEqual(length['matches'][0]['unit_origin'], 'explicit')

    def test_plain_metre_is_not_silently_treated_as_micrometre(self):
        rows = audit_quantities('宽度200 μm[Ref-1]。', catalog('宽度200 m。'))
        length = next(row for row in rows if row['dimension'] == 'length^1')
        self.assertEqual(length['status'], 'unsupported_quantity_or_unit')
        self.assertTrue(length['same_scalar_other_units'])

    def test_unconfirmed_bullet_drops_repeated_numeric_without_losing_gap(self):
        answer = ('- **温度单位确认**：多处温度参数OCR识别为百分号/千分号，'
                  '但上述工序的具体温度值无法确认为80℃，须以原文识别值为准并注明单位不确定')
        formatted, changes = format_grounded_notes(
            answer, catalog('样品在80°C干燥箱中处理。'), [])
        self.assertNotIn('80℃', formatted)
        self.assertIn('其原文数值与单位', formatted)
        self.assertEqual(changes[0]['kind'], 'simplify_unconfirmed_numeric_gap')
        self.assertEqual(audit_quantities(formatted, catalog('样品在80°C干燥箱中处理。')), [])

    def test_qualified_celsius_cannot_be_created_from_a_percent_ocr_candidate(self):
        source = 'CA-PC在80%干燥箱中加热2 h。'
        answer = '原文该处温度识别为80°C（单位存疑）[Ref-1]，加热2 h。'
        rows = audit_quantities(answer, catalog(source))
        temperature = next(row for row in rows if row['dimension'] == 'temperature:C^1')
        self.assertEqual(temperature['status'], 'unsupported_quantity_or_unit')


class ReviewerCancellationAndBinding(unittest.TestCase):
    def setUp(self):
        self.fragments = {'F0016': {'span_id': 'A0016', 'text': '有据原句。'}}

    def test_noop_with_retain_language_is_cancelled(self):
        result, cancelled = discard_explicitly_cancelled_issues(
            {'issues': [{'fragment_id': 'F0016', 'reason': '此条无误，保留。',
                         'replacement': '', 'quote_ids': []}]}, self.fragments)
        self.assertEqual(result['issues'], [])
        self.assertEqual(len(cancelled), 1)

    def test_other_pending_fragment_in_reason_stays_actionable(self):
        result, cancelled = discard_explicitly_cancelled_issues(
            {'issues': [{'fragment_id': 'F0016',
                         'reason': 'F0016无误，但F0014的体系混淆需修正。',
                         'replacement': '', 'quote_ids': []}]}, self.fragments)
        self.assertEqual(len(result['issues']), 1)
        self.assertEqual(cancelled, [])

    def test_valid_fragment_id_wins_over_conflicting_span_and_fragment(self):
        result, errors = bind_review_fragments(
            {'issues': [{'fragment_id': 'F0016', 'span_id': 'A9999',
                         'original_fragment': '错误片段', 'replacement': '',
                         'quote_ids': []}]}, self.fragments)
        self.assertEqual(errors, [])
        self.assertEqual(result['issues'][0]['span_id'], 'A0016')
        self.assertEqual(result['issues'][0]['original_fragment'], '有据原句。')
        self.assertTrue(result['binding_diagnostics'])


class SemanticCitationVerification(unittest.TestCase):
    def test_model_verified_claim_sets_true_only_after_complete_support(self):
        sources = [{'ref_id': 1, 'source': '文献', 'content': '电池效率为80%。'}]
        llm = SimpleNamespace(model='fake', base_url='https://example.invalid',
                              call_llm=lambda **kwargs: json.dumps({
                                  'review_complete': True,
                                  'claims': [{'claim_id': 'S0001', 'verdict': 'supported',
                                              'supported_refs': [1], 'reason': '原句直接支持'}]}, ensure_ascii=False))
        result = verify_semantic_support('电池效率为80%[Ref-1]。', sources, llm=llm)
        self.assertTrue(result['semantic_support_verified'])
        self.assertEqual(result['claims'][0]['verdict'], 'supported')
        quality = check_citations('电池效率为80%[Ref-1]。', sources, semantic=result)
        self.assertTrue(quality['semantic_support_verified'])

    def test_partial_or_missing_claim_verification_keeps_false(self):
        sources = [{'ref_id': 1, 'source': '文献', 'content': '电池效率为80%。'}]
        llm = SimpleNamespace(model='fake', base_url='https://example.invalid',
                              call_llm=lambda **kwargs: json.dumps({
                                  'review_complete': True,
                                  'claims': [{'claim_id': 'S0001', 'verdict': 'partial',
                                              'supported_refs': [1], 'reason': '只支持数值'}]}, ensure_ascii=False))
        result = verify_semantic_support('电池效率为80%且寿命十年[Ref-1]。', sources, llm=llm)
        self.assertFalse(result['semantic_support_verified'])
        quality = check_citations('电池效率为80%且寿命十年[Ref-1]。', sources, semantic=result)
        self.assertFalse(quality['semantic_support_verified'])


class CrossSystemBoundaries(unittest.TestCase):
    def test_icrfbi_hydrogen_evidence_cannot_be_relabelled_as_all_iron_bi_strategy(self):
        issue = claim_issues('铁铬液流电池如何抑制析氢？',
                             '铁铬液流电池可采用Bi沉积抑制析氢。',
                             ['全铁液流电池采用Bi沉积抑制析氢。'])
        self.assertTrue(issue)
        self.assertFalse(claim_issues('铁铬液流电池如何抑制析氢？',
                                      '全铁体系的Bi沉积策略仅作外体系背景，不能外推到铁铬。',
                                      ['全铁液流电池采用Bi沉积抑制析氢。']))

    def test_soc_method_cannot_be_silently_transferred_to_soh(self):
        self.assertTrue(claim_issues('如何估计SOH？',
                                     '采用SOC估计的卡尔曼滤波方法估算SOH。',
                                     ['采用卡尔曼滤波估计SOC。']))
        self.assertFalse(claim_issues('如何估计SOH？',
                                      'SOC估计方法不能直接用于SOH，本次片段未提供SOH验证。',
                                      ['采用卡尔曼滤波估计SOC。']))

    def test_silica_gel_n2_adsorption_cannot_prove_carbon_felt_pores(self):
        self.assertTrue(claim_issues('碳毡孔结构如何表征？',
                                     '硅凝胶的N2吸附结果可确定碳毡孔结构。',
                                     ['硅凝胶的N2吸附等温线用于孔径分析。']))
        self.assertFalse(claim_issues('碳毡孔结构如何表征？',
                                      '硅凝胶N2吸附仅为外体系背景，不能证明碳毡孔结构。',
                                      ['硅凝胶的N2吸附等温线用于孔径分析。']))

    def test_active_material_size_cannot_prove_nafion_channel_size(self):
        self.assertTrue(claim_issues('Nafion膜通道尺寸如何确定？',
                                     '活性物质粒径可确定Nafion膜通道尺寸。',
                                     ['活性物质平均粒径为50 nm。']))
        self.assertFalse(claim_issues('Nafion膜通道尺寸如何确定？',
                                      '活性物质粒径不能外推到Nafion膜通道尺寸。',
                                      ['活性物质平均粒径为50 nm。']))


class RetrievalPlannerSafety(unittest.TestCase):
    def test_query_identity_is_nfkc_punctuation_and_whitespace_normalized(self):
        self.assertEqual(IterativeCoordinator._query_key(' ＡＢＣ， 铁铬 电池！ '),
                         IterativeCoordinator._query_key('abc铁铬电池'))

    def test_empty_retrieval_query_is_not_executed(self):
        coordinator = object.__new__(IterativeCoordinator)
        state = SimpleNamespace(operation_errors=[], log=lambda *args: None)
        self.assertFalse(coordinator._do_retrieval(state, '   ', 'DFRS'))


if __name__ == '__main__':
    unittest.main()
