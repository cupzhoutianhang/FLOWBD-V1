"""Offline regressions for the Oct26 failure triage (items 9-12)."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from agent.answer_grounding import check_citations, normalize_citations
from agent.grounding_audit import discard_explicitly_cancelled_issues
from agent.mechanism_boundaries import claim_issues
from agent.quantity_grounding import audit_quantities
from agent.structured_llm import call_structured


def catalog(text):
    return {'Q0001': {'ref_id': 1, 'source_id': 'SRC:test', 'title': '原文', 'quote': text}}


def load_review_module():
    path = ROOT.parents[1] / 'qa_runs' / 'evidence_quality_20261022_resume6' / 'review_new_questions.py'
    spec = importlib.util.spec_from_file_location('review_new_questions_offline', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CancelledReviewIssues(unittest.TestCase):
    def setUp(self):
        self.fragments = {'F0001': {'span_id': 'A0001', 'text': '原句。'}}

    def test_explicit_cancellation_is_discarded(self):
        for reason in ('实际无误，此条取消', '此条无误'):
            with self.subTest(reason=reason):
                result, cancelled = discard_explicitly_cancelled_issues(
                    {'issues': [{'fragment_id': 'F0001', 'reason': reason,
                                 'replacement': '', 'quote_ids': []}]}, self.fragments)
                self.assertEqual(result['issues'], [])
                self.assertEqual(len(cancelled), 1)

    def test_unknown_fragment_is_kept(self):
        result, cancelled = discard_explicitly_cancelled_issues(
            {'issues': [{'fragment_id': 'F9999', 'reason': '此条无误',
                         'replacement': '', 'quote_ids': []}]}, self.fragments)
        self.assertEqual(len(result['issues']), 1)
        self.assertEqual(cancelled, [])

    def test_contradictory_or_actionable_issue_is_kept(self):
        for issue in (
            {'fragment_id': 'F0001', 'reason': '此条无误，但删除',
             'replacement': '', 'quote_ids': []},
            {'fragment_id': 'F0001', 'reason': '此条无误',
             'replacement': '替换', 'quote_ids': []},
            {'fragment_id': 'F0001', 'reason': '此条无误',
             'replacement': '', 'quote_ids': ['Q0001']},
        ):
            with self.subTest(issue=issue):
                result, cancelled = discard_explicitly_cancelled_issues(
                    {'issues': [issue]}, self.fragments)
                self.assertEqual(len(result['issues']), 1)
                self.assertEqual(cancelled, [])


class ExplanatoryCitations(unittest.TestCase):
    def test_explanatory_marker_is_normalized_and_note_preserved(self):
        cases = {
            '[Ref-12仅确认电位关系]': '[Ref-12]仅确认电位关系',
            '[Ref-5提及...]': '[Ref-5]提及...',
            '[Ref-1说明]': '[Ref-1]说明',
            '[Ref-1,2]': '[Ref-1][Ref-2]',
            '[Ref-4, Ref-13]': '[Ref-4][Ref-13]',
            '（Ref-8）': '[Ref-8]',
            'Ref-9': '[Ref-9]',
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(normalize_citations(raw), expected)

    def test_unknown_explanatory_ref_is_still_invalid(self):
        normalized = normalize_citations('[Ref-99未知说明]')
        self.assertEqual(normalized, '[Ref-99]未知说明')
        result = check_citations(normalized, [{'ref_id': 1}])
        self.assertEqual(result['invalid_refs'], [99])
        self.assertEqual(result['malformed_markers'], [])

    def test_comma_then_prose_remains_malformed(self):
        normalized = normalize_citations('[Ref-1,说明]')
        self.assertEqual(normalized, '[Ref-1,说明]')
        result = check_citations(normalized, [{'ref_id': 1}])
        self.assertTrue(result['malformed_markers'])


class QuantityAndConditionBinding(unittest.TestCase):
    def statuses(self, answer, source):
        return [row['status'] for row in audit_quantities(answer, catalog(source))]

    def test_ocr_temperature_and_percent_are_not_interchangeable(self):
        result = audit_quantities('原文170‰，是否170℃未确认[Ref-1]。', catalog('设定温度170‰。'))
        self.assertTrue(result)
        celsius = next(row for row in result if 'C' in row['dimension'])
        self.assertEqual(celsius['status'], 'unsupported_quantity_or_unit')
        result = audit_quantities('原文99.19%[Ref-1]。', catalog('设定温度170‰。'))
        self.assertEqual(result[0]['status'], 'unsupported_quantity_or_unit')

    def test_cited_and_uncited_temperatures(self):
        source = '样品A在90 min时加入1.0%添加剂，随后在300℃煅烧。'
        self.assertEqual(self.statuses('300℃[Ref-1]。', source), ['matched_quantity'])
        self.assertEqual(self.statuses('300℃。', source), ['missing_local_citation'])
        self.assertEqual(self.statuses('200℃[Ref-1]。', source), ['unsupported_quantity_or_unit'])

    def test_time_and_additive_need_local_citation(self):
        source = '样品A在90 min时加入1.0%添加剂。'
        self.assertEqual(self.statuses('90 min[Ref-1]。', source), ['matched_quantity'])
        self.assertEqual(self.statuses('90 min。', source), ['missing_local_citation'])
        self.assertEqual(self.statuses('1.0%[Ref-1]。', source), ['unsupported_condition_binding'])
        self.assertEqual(self.statuses('1.0%。', source), ['missing_local_citation'])

    def test_explicit_sample_contrast_binding(self):
        source = '样品A在90 min时加入1.0%添加剂，样品B未加。'
        wrong = '样品B在90 min时加入1.0%添加剂[Ref-1]。'
        self.assertTrue(all(s == 'unsupported_condition_binding' for s in self.statuses(wrong, source)))
        generalized = '所有样品均加入1.0%添加剂[Ref-1]。'
        self.assertEqual(self.statuses(generalized, source), ['unsupported_condition_binding'])
        omitted = '加入1.0%添加剂[Ref-1]。'
        self.assertEqual(self.statuses(omitted, source), ['unsupported_condition_binding'])
        extended = '样品A和样品B在90 min时加入1.0%添加剂[Ref-1]。'
        self.assertTrue(all(s == 'unsupported_condition_binding' for s in self.statuses(extended, source)))

    def test_correct_sample_and_single_sample_answer_pass(self):
        source = '样品A在90 min时加入1.0%添加剂，样品B未加。'
        answer = '样品A在90 min时加入1.0%添加剂[Ref-1]。'
        self.assertTrue(all(s == 'matched_quantity' for s in self.statuses(answer, source)))
        single = '样品A在90 min时加入1.0%添加剂。'
        self.assertTrue(all(s == 'matched_quantity' for s in self.statuses(answer, single)))

    def test_later_temperature_does_not_inherit_earlier_time(self):
        source = '样品A在90 min时加入1.0%添加剂，随后在300℃煅烧。'
        self.assertEqual(self.statuses('300℃[Ref-1]。', source), ['matched_quantity'])
        self.assertEqual(self.statuses('90 min[Ref-1]。', source), ['matched_quantity'])


class ConnectionRetry(unittest.TestCase):
    def test_connection_error_retries_once_and_is_recorded(self):
        llm = SimpleNamespace(model='kimi-k2.6', base_url='https://api.moonshot.cn/v1', api_key='test-key')
        with patch('requests.post', side_effect=__import__('requests').ConnectionError('offline')) as post:
            answer = call_structured(llm, '{}')
        self.assertEqual(post.call_count, 2)
        self.assertTrue(answer.startswith('❌'))
        self.assertEqual(len(llm.structured_calls), 2)
        self.assertTrue(all('error' in event for event in llm.structured_calls))


class GapStatements(unittest.TestCase):
    def test_historical_gap_samples_are_recognized(self):
        module = load_review_module()
        samples = [
            '当前文献缺口：未在本次片段中给出前驱体具体种类。',
            '本次检索缺口：未检索到该温度下的长期稳定性数据。',
            '本次提供的文献片段未明确结构导向剂的种类。',
            '未获得直接支持，不能按常见配比补造。',
            '需查阅原文确认具体参数。',
            '该体系的具体组成未明确。',
            '工艺参数未在片段中给出。',
            '缺乏直接证据证明该机理。',
            '未在片段中明确区分两种效率。',
            '未在本次片段中发现循环寿命数据。',
        ]
        self.assertTrue(all(module.is_explicit_gap_statement(text) for text in samples))

    def test_ordinary_fact_without_evidence_still_fails(self):
        module = load_review_module()
        row = {'doc_sources': [], 'evidence_graph': {}}
        review = {'claims': [{'answer_span': 'A0001', 'verdict': 'supported', 'evidence_quote_ids': []}]}
        spans = [{'span_id': 'A0001', 'text': '材料效率为87%。'}]
        module.verify_quotes(review, row, [], spans)
        self.assertTrue(review['quote_check_issues'])

    def test_gap_without_quote_passes_but_unknown_ids_fail(self):
        module = load_review_module()
        row = {'doc_sources': [], 'evidence_graph': {}}
        spans = [{'span_id': 'A0001', 'text': '当前文献缺口：未给出具体前驱体。'}]
        review = {'claims': [{'answer_span': 'A0001', 'verdict': 'supported', 'evidence_quote_ids': []}]}
        module.verify_quotes(review, row, [], spans)
        self.assertFalse(review['quote_check_issues'])
        self.assertTrue(review['claims'][0]['gap_statement_no_quote'])
        review = {'claims': [{'answer_span': 'A0001', 'verdict': 'supported',
                              'evidence_quote_ids': ['Q9999']}]}
        module.verify_quotes(review, row, [], spans)
        self.assertTrue(review['quote_check_issues'])

    def test_unknown_answer_span_still_fails(self):
        module = load_review_module()
        row = {'doc_sources': [], 'evidence_graph': {}}
        review = {'claims': [{'answer_span': 'A9999', 'verdict': 'supported', 'evidence_quote_ids': []}]}
        module.verify_quotes(review, row, [], [])
        self.assertTrue(review['quote_check_issues'])


class SubjectAndBoundaryChecks(unittest.TestCase):
    def test_three_molar_supports_only_named_subject(self):
        source = '3 M 2mIm电解液。'
        result = audit_quantities('3 M L-his电解液[Ref-1]。', catalog(source))
        self.assertEqual(result[0]['status'], 'unsupported_subject_binding')
        source = '3 M 2mIm与L-his电解液。'
        result = audit_quantities('3 M L-his电解液[Ref-1]。', catalog(source))
        self.assertEqual(result[0]['status'], 'matched_quantity')

    def test_heo_general_route_does_not_prove_heo(self):
        issues = claim_issues('高熵氧化物如何制备？', '可采用溶胶-凝胶法制备高熵氧化物。',
                              ['溶胶-凝胶法是一般金属氧化物前驱体的常用制备方法。'])
        self.assertTrue(issues)

    def test_heo_solid_state_uniformity_limit(self):
        source = ['采用固相法制备了高熵氧化物。']
        for claim in ('固相法制备的HEO元素均匀性差。', '固相法制备的HEO元素分布不均。',
                      '固相法制备的HEO元素均匀性较差。'):
            with self.subTest(claim=claim):
                self.assertTrue(claim_issues('高熵氧化物如何制备？', claim, source))
        self.assertFalse(claim_issues('高熵氧化物如何制备？',
                                      '固相法制备的HEO可能元素分布不均。', source))

    def test_eg_mechanism_requires_direct_quote(self):
        source = ['膨胀石墨具有多孔形貌，可吸附相变材料。']
        self.assertTrue(claim_issues('膨胀石墨如何改善导热？',
                                     '膨胀石墨形成连续三维导热网络，降低界面热阻。', source))
        self.assertFalse(claim_issues('膨胀石墨如何改善导热？',
                                      '膨胀石墨可能形成连续三维导热网络。', source))


class RepeatIndependence(unittest.TestCase):
    def test_stability_repeat_records_stay_independent(self):
        path = ROOT.parents[1] / 'qa_runs' / 'failure_triage_20261026' / 'failure_ledger_97_all.jsonl'
        rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
        repeats = [row for row in rows if str(row.get('case_id')) == '19' and row.get('mode') == 'Q1'
                   and row.get('_suite') == 'original_97' and row.get('_repeat') in (1, 2, 3)]
        self.assertEqual(len({row.get('_repeat') for row in repeats}), 3)
        r3 = next(row for row in repeats if row.get('_repeat') == 3)
        self.assertEqual(r3.get('mechanical_failure_type'), 'answer_validation_failure')


if __name__ == '__main__':
    unittest.main()
