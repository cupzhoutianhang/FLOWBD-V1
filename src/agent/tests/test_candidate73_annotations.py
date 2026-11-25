"""Answers with unresolved checks are annotated, never replaced by a refusal."""
from __future__ import annotations

import unittest

from agent.answer_annotation import MARK, annotate_unverified, strip_annotations


def check(claim, quantity, status, line=1):
    return {'claim_id': claim, 'line_number': line, 'quantity': quantity, 'status': status}


class AnnotateUnverified(unittest.TestCase):
    def test_missing_citation_is_marked_and_declared(self):
        answer = '- HER电位由-1.766 V变为-1.660 V[Ref-18]。'
        checks = [check('L0001.Q1', '-1.766 V', 'unsupported_quantity_or_unit')]
        annotated, rows = annotate_unverified(answer, [], checks)
        self.assertIn(f'-1.766 V{MARK}', annotated)
        self.assertIn('待核实声明', annotated)
        self.assertIn('L0001.Q1', annotated)
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]['marked_inline'])

    def test_clean_checks_leave_the_answer_untouched(self):
        answer = '- 加热2 h[Ref-1]。'
        annotated, rows = annotate_unverified(
            answer, [], [check('L0001.Q1', '2 h', 'matched_quantity')])
        self.assertEqual(annotated, answer)
        self.assertEqual(rows, [])

    def test_repeated_values_are_marked_separately(self):
        answer = '- 80℃加热；另一工序80℃干燥[Ref-1]。'
        checks = [check('L0001.Q1', '80℃', 'unsupported_quantity_or_unit'),
                  check('L0001.Q2', '80℃', 'missing_local_citation')]
        annotated, rows = annotate_unverified(answer, [], checks)
        self.assertEqual(annotated.count(MARK), 2)
        self.assertTrue(all(row['marked_inline'] for row in rows))

    def test_non_quantity_issues_are_declared_without_inline_marks(self):
        answer = '- 结论[Ref-99]。'
        annotated, rows = annotate_unverified(answer, ['引用编号无效或格式不完整：[99]'], [])
        self.assertIn('引用编号无效', annotated)
        self.assertEqual(annotated.count(MARK), 0)
        self.assertEqual(rows[0]['status'], 'other_check')

    def test_declaration_can_be_stripped_for_diagnostics(self):
        answer = '- 加热2 h[Ref-1]。'
        annotated, _ = annotate_unverified(
            answer, [], [check('L0001.Q1', '2 h', 'missing_local_citation')])
        self.assertIn('待核实声明', annotated)
        self.assertNotIn('待核实声明', strip_annotations(annotated))
        self.assertNotIn(MARK, strip_annotations(annotated))

    def test_value_missing_from_the_answer_still_yields_a_declaration(self):
        answer = '- 结论。'
        annotated, rows = annotate_unverified(
            answer, [], [check('L0001.Q1', '4 MPa', 'unsupported_quantity_or_unit')])
        self.assertIn('4 MPa', annotated)
        self.assertFalse(rows[0]['marked_inline'])


if __name__ == '__main__':
    unittest.main()
