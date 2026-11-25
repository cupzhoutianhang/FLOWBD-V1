"""Offline regression gates for candidate66 quantity/unit OCR repairs."""
from __future__ import annotations

import unittest
from decimal import Decimal

from agent.quantity_grounding import audit_quantities, comparison_text, quantities


def catalog(text):
    return {'Q0001': {'ref_id': 1, 'source_id': 'SRC:test', 'title': '原文', 'quote': text}}


class QuantityUnitOCRRepairs(unittest.TestCase):
    def test_spaced_ocr_area_current_density_is_one_compound_quantity(self):
        rows = quantities('电流密度从0.36    m A   c m ^-2降至0.05    m A   c m ^-2。')
        self.assertEqual([row.raw for row in rows], ['0.36 mA cm^-2', '0.05 mA cm^-2'])
        self.assertTrue(all(row.dimension == 'current^1|length^-2' for row in rows))

    def test_partial_area_current_forms_do_not_invent_the_missing_power(self):
        current_times_length = quantities('0.36 mA cm')[0]
        self.assertEqual(current_times_length.dimension, 'current^1|length^1')
        current = quantities('0.36 mA')[0]
        self.assertEqual(current.dimension, 'current^1')
        self.assertEqual(quantities('cm^-2'), [])

    def test_tex_wrappers_preserve_visible_unit_content(self):
        self.assertEqual(comparison_text(r'$1 . 2 \textbf { M }$').strip(), '1.2 M')
        self.assertEqual(comparison_text(r'$1 . 0 \textrm { w } \mathrm { K O H }$').strip(),
                         '1.0 M KOH')
        self.assertEqual(comparison_text(r'$2 . 2 \mathsf { V }$').strip(), '2.2 V')

    def test_phantom_negative_does_not_flip_shared_range_unit(self):
        text = r'$- 0 . 7 2 }$ to $\phantom { - } 0 . 8 5 { \mathsf { V } }$'
        values = quantities(text)
        self.assertIn(Decimal('-0.72'), {row.value for row in values})
        self.assertIn(Decimal('0.85'), {row.value for row in values})
        self.assertNotIn(Decimal('-0.85'), {row.value for row in values})

    def test_signed_spaced_ocr_quantity_keeps_its_sign(self):
        rows = quantities(r'$- 5 9 \mathrm { m V } \mathrm { p H')
        voltage = next(row for row in rows if row.dimension == 'voltage^1')
        self.assertEqual(voltage.value, Decimal('-59'))
        self.assertEqual(voltage.base_value, Decimal('-0.059'))

    def test_markdown_bullet_is_not_turned_into_negative_temperature(self):
        rows = quantities('- 300°C')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].value, Decimal('300'))

    def test_spaced_ocr_temperature_after_unmatched_math_slice(self):
        text = (r'} } )$ [131] For instance, $0 . 4 \mathrm { M }$ in alkaline. '
                r'The solubility increased to $1 . 2 \textbf { M }$ at '
                r'$2 0 ~ ^ { \circ } \mathrm { C }$ Employing N212.')
        temperatures = [row for row in quantities(text) if row.dimension == 'temperature:C^1']
        self.assertEqual([(row.value, row.raw) for row in temperatures], [(Decimal('20'), '20   °C')])

    def test_potential_window_bare_number_infers_voltage_dimension(self):
        rows = quantities('the aqueous potential window is confined to 1.23, as reported elsewhere.')
        voltage = next(row for row in rows if row.dimension == 'voltage^1')
        self.assertEqual(voltage.value, Decimal('1.23'))
        self.assertIn('窗口语境', voltage.raw)

    def test_lowercase_m_is_molar_only_in_an_electrolyte_context(self):
        koh = quantities('1 m KOH')[0]
        self.assertEqual(koh.dimension, 'concentration^1')
        self.assertEqual(koh.value, Decimal('1'))
        metre = quantities('1 m sample')[0]
        self.assertEqual(metre.dimension, 'length^1')


class HtmlTableUnitInference(unittest.TestCase):
    def test_voltage_power_density_and_energy_density_headers(self):
        source = (
            '<table><tr><td>Material</td><td>Voltage M]</td>'
            '<td>Power Density [W cm-2]</td><td>Energy Density [Wh L-1]</td></tr>'
            '<tr><td>2,6-DHAQ</td><td>1.2</td><td>0.4</td><td>8.04</td></tr></table>'
        )
        answer = '电压为1.2 V，功率密度为0.4 W·cm-2，能量密度为8.04 Wh·L-1[Ref-1]。'
        rows = audit_quantities(answer, catalog(source))
        self.assertEqual([row['status'] for row in rows], ['matched_quantity'] * 3)
        self.assertTrue(all(row['matches'][0]['unit_origin'] == 'table_header' for row in rows))

    def test_truncated_table_with_percent_columns_keeps_numeric_data_rows(self):
        source = (
            '<table><tr><td>Anode</td><td>Cathode</td><td>Anode Electrolyte</td>'
            '<td>Solubility</td><td colspan="5">AORFBs Performance</td><td>Ref.</td></tr>'
            '<tr><td></td><td></td><td></td><td></td><td>Voltage M]</td>'
            '<td>Power Density [W cm-2]</td><td>Energy Density [Wh L-1]</td>'
            '<td>Current Efficiency</td><td>Energy Efficiency</td><td></td></tr>'
            '<tr><td>2,6-DHAQ</td><td>KFe(CN)6</td><td>1 m KOH</td><td>&gt; 0.6 M</td>'
            '<td>1.2</td><td>0.4</td><td>8.04</td><td>99%</td><td>84%</td>'
            '<td>[19]</td></tr><tr><td>2,6-DBEAQ</td><td>Fe(CN) 3-/-</td>'
            '<td>0.01 M KOH</td><td>0.6 M</td><td>&gt; 1.0</td><td>0.24</td>'
            '<td>2.61</td>'
        )
        answer = '电压为1.2 V，功率密度为0.4 W·cm-2，能量密度为8.04 Wh·L-1[Ref-1]。'
        rows = audit_quantities(answer, catalog(source))
        self.assertEqual([row['status'] for row in rows], ['matched_quantity'] * 3)
        self.assertTrue(all(row['matches'][0]['unit_origin'] == 'table_header' for row in rows))

    def test_ocr_molar_cell_matches_normalized_concentration(self):
        source = ('<table><tr><td>Material</td><td>Electrolyte</td></tr>'
                  '<tr><td>2,6-DHAQ</td><td>1 m KOH</td></tr></table>')
        rows = audit_quantities('电解液为1 M KOH[Ref-1]。', catalog(source))
        concentration = next(row for row in rows if row['dimension'] == 'concentration^1')
        self.assertEqual(concentration['status'], 'matched_quantity')


if __name__ == '__main__':
    unittest.main()
