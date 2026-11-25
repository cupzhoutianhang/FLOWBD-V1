"""Offline regression gates for candidate67 citation-scoped OCR validation."""
from __future__ import annotations

import unittest

from agent.grounded_formatting import format_grounded_notes
from agent.native_answer import draft_issues


def source(ref_id, content, source_id=None):
    return {
        'ref_id': ref_id,
        'source_id': source_id or f'SRC:{ref_id}',
        'chunks': [{'source_id': source_id or f'SRC:{ref_id}', 'content': content}],
    }


def catalog(ref_id, text, source_id=None):
    source_id = source_id or f'SRC:{ref_id}'
    return {f'Q{ref_id:04d}': {
        'ref_id': ref_id, 'source_id': source_id,
        'title': f'原文{ref_id}', 'quote': text,
    }}


def resolved_note():
    return [{
        'ref_id': 1,
        'source_id': 'SRC:1',
        'value': '170',
        'quote': r'放入真空干燥箱，温度设定 $1 7 0 \mathrm{‰}$，干燥不少于 $2 4\mathrm{h}$。',
        'resolved_by_pdf': [{
            'ref_id': 17,
            'source_id': 'SRC:17',
            'value': '170',
            'corrected_literal': '170℃',
            'matched_left': '燥箱温度设定',
            'matched_right': '干燥不少于2',
        }],
    }]


class DuplicateEndpointGapFormatting(unittest.TestCase):
    def test_supported_endpoint_temperatures_are_removed_from_rate_gaps(self):
        text = '设定加热温度300℃，加热至熔融，随后自然冷却至200℃。'
        evidence = catalog(1, text)
        answer = ('设定加热温度300℃[Ref-1]，加热至熔融，随后自然冷却至200℃[Ref-1]。\n\n'
                  '- 升温速率（从室温到300℃的加热速率）未在提供的片段中明确；\n'
                  '- 搅拌完成后从300℃自然冷却至200℃的冷却速率未明确。')
        formatted, changes = format_grounded_notes(answer, evidence, [], sources=None)
        gap = formatted.split('\n\n', 1)[1]
        self.assertNotIn('300℃', gap)
        self.assertNotIn('200℃', gap)
        self.assertIn('目标温度', gap)
        self.assertIn('simplify_duplicate_parenthetical_ramp_gap', {c['kind'] for c in changes})
        self.assertIn('simplify_duplicate_cooling_gap', {c['kind'] for c in changes})

    def test_long_gap_negation_is_simplified_when_endpoint_is_supported(self):
        text = '设定加热温度300℃，加热至熔融状态。'
        evidence = catalog(1, text)
        answer = ('设定加热温度300℃[Ref-1]，加热至熔融状态。\n\n'
                  '- 从室温升至300℃的升温速率未在提供的片段中明确；')
        formatted, changes = format_grounded_notes(answer, evidence, [], sources=None)
        gap = formatted.split('\n\n', 1)[1]
        self.assertNotIn('300℃', gap)
        self.assertIn('从室温升至目标温度的升温速率未在提供的片段中明确', gap)
        self.assertIn('simplify_duplicate_ramp_gap', {c['kind'] for c in changes})

    def test_supported_only_known_value_is_removed_from_gap_line(self):
        text = '仅对90 min搅拌、SiO2质量含量1.0%的样品讨论微观形貌。'
        evidence = catalog(1, text)
        answer = ('仅对90 min搅拌、SiO2质量含量1.0%的样品讨论微观形貌[Ref-1]。\n\n'
                  '- SiO2纳米颗粒与基盐的具体质量比例（仅知1.0%为文中讨论样品之一）'
                  '未在工艺步骤中完整给出通用配比；')
        formatted, changes = format_grounded_notes(answer, evidence, [], sources=None)
        gap = formatted.split('\n\n', 1)[1]
        self.assertNotIn('1.0%', gap)
        self.assertIn('remove_redundant_supported_gap_value', {c['kind'] for c in changes})

    def test_unsupported_only_known_value_stays_in_gap_line(self):
        answer = ('- SiO2纳米颗粒与基盐的具体质量比例（仅知1.0%为文中讨论样品之一）'
                  '未在工艺步骤中完整给出通用配比；')
        formatted, changes = format_grounded_notes(answer, {}, [], sources=None)
        self.assertEqual(formatted, answer)
        self.assertEqual(changes, [])

    def test_unbacked_endpoint_temperature_is_not_removed(self):
        answer = '- 从300℃自然冷却至200℃的冷却速率未明确。'
        formatted, changes = format_grounded_notes(answer, {}, [], sources=None)
        self.assertEqual(formatted, answer)
        self.assertEqual(changes, [])


class CitationScopedOcrTemperature(unittest.TestCase):
    def test_pdf_resolved_value_passes_with_connector_in_same_context(self):
        sources = [
            source(1, '放入真空干燥箱，温度设定170‰，干燥不少于24 h。'),
            source(17, '放入真空干燥箱，温度设定为170℃，干燥不少于24 h。'),
        ]
        evidence = {}
        evidence.update(catalog(1, sources[0]['chunks'][0]['content']))
        evidence.update(catalog(17, sources[1]['chunks'][0]['content']))
        issues = draft_issues(
            '真空干燥箱温度设定为170℃[Ref-17]，干燥不少于24 h。',
            sources, evidence, resolved_note(), strict_validation=False)
        self.assertNotIn('温度170的℃单位未经原文确认，需保留OCR存疑说明。', issues)

    def test_bounded_pdf_check_parenthetical_keeps_same_procedure_context(self):
        sources = [
            source(1, '放入真空干燥箱，温度设定170‰，干燥不少于24 h。'),
            source(17, '放入真空干燥箱，温度设定为170℃，干燥不少于24 h。'),
        ]
        evidence = {}
        evidence.update(catalog(1, sources[0]['chunks'][0]['content']))
        evidence.update(catalog(17, sources[1]['chunks'][0]['content']))
        issues = draft_issues(
            '放入真空干燥箱，温度设定为170℃（原PDF核对值），干燥不少于24 h[Ref-17]。',
            sources, evidence, resolved_note(), strict_validation=False)
        self.assertNotIn('温度170的℃单位未经原文确认，需保留OCR存疑说明。', issues)

    def test_non_pdf_parenthetical_does_not_exempt_ocr(self):
        sources = [
            source(1, '放入真空干燥箱，温度设定170‰，干燥不少于24 h。'),
            source(17, '放入真空干燥箱，温度设定为170℃，干燥不少于24 h。'),
        ]
        evidence = {}
        evidence.update(catalog(1, sources[0]['chunks'][0]['content']))
        evidence.update(catalog(17, sources[1]['chunks'][0]['content']))
        issues = draft_issues(
            '放入真空干燥箱，温度设定为170℃（推测值），干燥不少于24 h[Ref-17]。',
            sources, evidence, resolved_note(), strict_validation=False)
        self.assertIn('温度170的℃单位未经原文确认，需保留OCR存疑说明。', issues)

    def test_resolved_value_allows_bounded_followup_modifier(self):
        sources = [
            source(1, '放入真空干燥箱，温度设定170‰，干燥不少于24 h。'),
            source(17, '放入真空干燥箱，温度设定为170℃，干燥不少于24 h。'),
        ]
        evidence = {}
        evidence.update(catalog(1, sources[0]['chunks'][0]['content']))
        evidence.update(catalog(17, sources[1]['chunks'][0]['content']))
        note = resolved_note()
        note[0]['resolved_by_pdf'].append({
            'ref_id': 17,
            'source_id': 'SRC:17',
            'value': '170',
            'corrected_literal': '170℃',
            'matched_left': '燥箱温度设定',
            'matched_right': '作为制备纳米',
        })
        issues = draft_issues(
            '放入真空干燥箱，温度设定170℃，作为后续制备纳米熔盐的基盐[Ref-17]。',
            sources, evidence, note, strict_validation=False)
        self.assertNotIn('温度170的℃单位未经原文确认，需保留OCR存疑说明。', issues)

    def test_resolved_table_summary_row_passes(self):
        sources = [
            source(1, '放入真空干燥箱，温度设定170‰，干燥不少于24 h。'),
            source(17, '放入真空干燥箱，温度设定为170℃，干燥不少于24 h。'),
        ]
        evidence = {}
        evidence.update(catalog(1, sources[0]['chunks'][0]['content']))
        evidence.update(catalog(17, sources[1]['chunks'][0]['content']))
        issues = draft_issues(
            '| 基盐干燥温度 | 170℃ | [Ref-17] |',
            sources, evidence, resolved_note(), strict_validation=False)
        self.assertNotIn('温度170的℃单位未经原文确认，需保留OCR存疑说明。', issues)

    def test_unrelated_table_label_does_not_exempt_ocr(self):
        sources = [
            source(1, '放入真空干燥箱，温度设定170‰，干燥不少于24 h。'),
            source(17, '放入真空干燥箱，温度设定为170℃，干燥不少于24 h。'),
        ]
        evidence = {}
        evidence.update(catalog(1, sources[0]['chunks'][0]['content']))
        evidence.update(catalog(17, sources[1]['chunks'][0]['content']))
        issues = draft_issues(
            '| 熔点温度 | 170℃ | [Ref-17] |',
            sources, evidence, resolved_note(), strict_validation=False)
        self.assertIn('温度170的℃单位未经原文确认，需保留OCR存疑说明。', issues)

    def test_unresolved_ocr_still_fails_even_when_another_ref_has_normal_celsius(self):
        sources = [
            source(1, '放入真空干燥箱，温度设定170‰。'),
            source(2, '同篇另一工序温度为170℃。'),
        ]
        evidence = {}
        evidence.update(catalog(1, sources[0]['chunks'][0]['content']))
        evidence.update(catalog(2, sources[1]['chunks'][0]['content']))
        note = resolved_note()
        note[0]['resolved_by_pdf'] = []
        issues = draft_issues(
            '真空干燥箱温度设定为170℃[Ref-1]，干燥不少于24 h。',
            sources, evidence, note, strict_validation=False)
        self.assertIn('温度170的℃单位未经原文确认，需保留OCR存疑说明。', issues)

    def test_resolved_value_needs_the_resolved_ref_on_the_line(self):
        sources = [
            source(1, '放入真空干燥箱，温度设定170‰，干燥不少于24 h。'),
            source(17, '放入真空干燥箱，温度设定为170℃，干燥不少于24 h。'),
        ]
        evidence = {}
        evidence.update(catalog(1, sources[0]['chunks'][0]['content']))
        evidence.update(catalog(17, sources[1]['chunks'][0]['content']))
        issues = draft_issues(
            '真空干燥箱温度设定为170℃[Ref-1]，干燥不少于24 h。',
            sources, evidence, resolved_note(), strict_validation=False)
        self.assertIn('温度170的℃单位未经原文确认，需保留OCR存疑说明。', issues)

    def test_resolved_ref_with_wrong_context_does_not_exempt_ocr(self):
        sources = [
            source(1, '放入真空干燥箱，温度设定170‰，干燥不少于24 h。'),
            source(17, '放入真空干燥箱，温度设定为170℃，干燥不少于24 h。'),
        ]
        evidence = {}
        evidence.update(catalog(1, sources[0]['chunks'][0]['content']))
        evidence.update(catalog(17, sources[1]['chunks'][0]['content']))
        issues = draft_issues(
            '另一工序温度设定为170℃[Ref-17]，随后自然冷却。',
            sources, evidence, resolved_note(), strict_validation=False)
        self.assertIn('温度170的℃单位未经原文确认，需保留OCR存疑说明。', issues)

    def test_same_ref_other_procedure_does_not_trigger_ocr_note(self):
        text = '将干燥箱加热温度升高至170‰，干燥纳米熔盐粉体不少于24 h。'
        sources = [source(1, text)]
        evidence = catalog(1, text)
        notes = [{'ref_id': 1, 'source_id': 'SRC:1', 'value': '170', 'quote': text}]
        issues = draft_issues(
            '真空干燥箱温度设定为170℃[Ref-1]，干燥不少于24 h。',
            sources, evidence, notes, strict_validation=False)
        self.assertNotIn('温度170的℃单位未经原文确认，需保留OCR存疑说明。', issues)

    def test_unrelated_ref_temperature_does_not_trigger_ocr_note(self):
        sources = [source(5, '80℃真空干燥12 h。')]
        evidence = catalog(5, sources[0]['chunks'][0]['content'])
        notes = [
            {'ref_id': 1, 'source_id': 'SRC:1', 'value': '80', 'quote': '加热温度80%。'},
            {'ref_id': 4, 'source_id': 'SRC:4', 'value': '80', 'quote': '置于80%干燥箱。'},
        ]
        issues = draft_issues(
            '80℃真空干燥12 h[Ref-5]。',
            sources, evidence, notes, strict_validation=False)
        self.assertNotIn('温度80的℃单位未经原文确认，需保留OCR存疑说明。', issues)


if __name__ == '__main__':
    unittest.main()
