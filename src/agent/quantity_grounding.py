"""Deterministic quantity/source diagnostics; never a semantic truth certificate.

Original source strings are immutable. Normalization is comparison-only; bounded
unit conversions keep signs and dimensions, and diagnostics retain original spans.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re
import unicodedata


_TEMPERATURE_CONTEXT = re.compile(r'温度|烘箱|水浴|干燥箱|加热|冷却|保温|退火|预热|烘干')


def comparison_text(text):
    original = str(text or '')
    text = unicodedata.normalize('NFKC', str(text or ''))
    # TeX spells the degree sign as \textdegree or \degree.
    text = text.replace(r'\textdegree', '°').replace(r'\degree', '°')
    # Invisible TeX layout commands must not leak their contents into comparison
    # text. In particular, \phantom{-} is not a visible minus sign.
    text = re.sub(r'\\(?:h|v)?phantom\s*\{[^{}]*\}', ' ', text)
    wrapper_names = (
        'textnormal|textsf|textrm|textbf|texttt|operatorname|'
        'mathrm|mathsf|mathbf|mathit|text'
    )
    wrapper = re.compile(r'\\+(?:' + wrapper_names + r')\s*\{([^{}]*)\}')

    def tex_visible(match):
        content = match.group(1)
        compact = re.sub(r'\s+', '', content).replace('μ', 'µ')
        letters = re.findall(r'[A-Za-z]+', content)
        # Unit and chemical wrappers are commonly letter-spaced by OCR
        # (for example m V, K O H). Preserve real multi-word prose.
        if compact and (len(compact) <= 4 or all(len(part) <= 1 for part in letters)):
            # OCR sometimes leaves stray TeX escapes inside a letter-spaced
            # unit (\\ A h \\ c m). Compacting them keeps the backslashes, and
            # the TeX-command stripper below would then delete every letter.
            if all(len(part) <= 1 for part in letters):
                compact = re.sub(r'\\(?=[A-Za-z])', '', compact)
            return compact
        return re.sub(r'\s+', ' ', content).strip()

    for _ in range(3):
        replaced = wrapper.sub(tex_visible, text)
        if replaced == text:
            break
        text = replaced
    text = re.sub(r'\\+(?:' + wrapper_names + r')\s*', '', text)
    # TeX spells the micro prefix as \mu before the unit. Preserve it only
    # when a recognized unit follows; a bare \mu may still be a variable.
    text = re.sub(r'\\mu\s*(?=' + _UNIT + r'(?![A-Za-z]))', 'µ', text, flags=re.I)
    text = text.replace(r'\circ', '°').replace(r'\times', '×').replace(r'\cdot', '·').replace(r'\sim', '–')
    text = re.sub(r'\\[,;!%]', lambda m: '%' if m.group() == r'\%' else ' ', text)
    text = re.sub(r'\\[A-Za-z]+', ' ', text)
    text = re.sub(r'\\\s*', ' ', text)
    # Source slices can begin inside a math block. Explicit powers and the
    # multiplication-by-ten notation still bind their spaced OCR digits;
    # normalize them without joining unrelated numeric lists or changing signs.
    text = re.sub(r'\^\s*\{\s*([-+−]?\s*\d+(?:\s+\d+)*)\s*\}',
                  lambda m: '^' + re.sub(r'\s+', '', m.group(1)), text)
    text = re.sub(r'\{\s*×\s*\}', '×', text)
    scientific = (r'(?<![A-Za-z0-9_.])(?P<m>[-+−]?[ \t]*\d+(?:[ \t]+\d+)*'
                  r'(?:[ \t]*\.[ \t]*\d+(?:[ \t]+\d+)*)?)[ \t]*[×x][ \t]*1[ \t]*0'
                  r'[ \t]*\^?[ \t]*(?P<e>[-+−]?[ \t]*\d+(?:[ \t]+\d+)*)')
    text = re.sub(scientific, lambda m: re.sub(r'\s+', '', m['m']).replace('−', '-')
                  + 'e' + re.sub(r'\s+', '', m['e']).replace('−', '-'), text)
    # OCR/TeX sometimes wraps a range separator in braces (10 { - } 20 kW).
    # Convert it before braces are stripped and before a math block can read
    # the hyphen as the sign of the following number.
    text = re.sub(r'(?<=\d)[ \t]*\{[ \t]*[-–—~][ \t]*\}[ \t]*(?=[+-]?\d)', ' – ', text)
    # Both endpoints already carry percent units (1.77%~11.21%). This must run
    # before the generic rule below, whose ~ → space rewrite would otherwise
    # glue "11" onto the first percent as an exponent.
    text = re.sub(r'(?<=[%‰])\s*[-–—~]\s*(?=[-+]?\d)', '–', text)
    # In TeX, ~ before a unit is a nonbreaking space. Only a separator
    # between two numeric endpoints denotes a range.
    text = re.sub(r'(?<=\d)\s*[~-]\s*(?=[+-]?\d)', '–', text).replace('~', ' ')
    text = text.translate(str.maketrans({'{': '', '}': '', '−': '-', 'μ': 'µ', '℃': '°C'}))
    # Normalize the degree glyph before spaced OCR digits are joined. Some
    # evidence slices start mid-formula and therefore have unbalanced dollars.
    text = re.sub(r'\^\s*(?:°\s*C|(?:circ|c|o)\s*C)', '°C', text, flags=re.I)
    text = re.sub(r'°\s*C', '°C', text)
    # OCR splits compound energy/charge units (W h L-1, m A h). Join only the
    # known compound forms, never arbitrary adjacent units.
    text = re.sub(r'(?<![A-Za-z])(k?W)\s+h(?![A-Za-z])', r'\1h', text)
    text = re.sub(r'(?<![A-Za-z])(m?A)\s+h(?![A-Za-z])', r'\1h', text)
    text = re.sub(r'(?<![A-Za-z])([kµμm])\s+(?=[AW]h(?![A-Za-z]))', r'\1', text)
    # OCR occasionally renders ℃ as 9C. Repair it only inside an explicit
    # temperature list that already carries a real degree glyph, and only
    # before spaced digits are joined (otherwise 75 9 C becomes 759 C).
    if _TEMPERATURE_CONTEXT.search(original) and '°C' in text:
        text = re.sub(r'(?<=\d)[ \t]+9[ \t]*C(?![A-Za-z0-9])', ' °C', text)

    def math_block(match):
        part = match.group(1)
        part = re.sub(
            r'(?P<sign>[-+]?)\s*(?P<whole>\d+(?:[ \t]+\d+)*)[ \t]*\.[ \t]*'
            r'(?P<fraction>\d+(?:[ \t]+\d+)*)',
            lambda m: m['sign'] + re.sub(r'\s+', '', m['whole']) + '.'
            + re.sub(r'\s+', '', m['fraction']), part)
        part = re.sub(r'(?<=\d)\s+(?=\d)', '', part)
        part = re.sub(r'(?<![A-Za-z0-9_.])([-+])[ \t]+(?=\d)', r'\1', part)
        return re.sub(r'(?<=[A-Za-z])\s+(?=[A-Za-z])', '', part)

    text = re.sub(r'\$([^$]*)\$', math_block, text)
    text = re.sub(r'(?P<label>(?:时间|时长)(?:分别为|分别是|取值为|为|[:：\s]){0,6})'
                  r'(?P<values>[-+]?\d+(?:\.\d+)?(?:\s*_\s*[-+]?\d+(?:\.\d+)?){1,31})'
                  r'\s*(?P<unit>min|h|s)(?![A-Za-z])',
                  lambda m: m['label'] + m['values'].replace('_', '、') + m['unit'], text)
    text = re.sub(r'(?<=\d)\s*\.\s*(?=\d)', '.', text)
    # Evidence catalog slices may start inside a TeX block. Normalize a spaced
    # decimal only when its complete digit sequence is followed by a unit;
    # this also works without a balanced $...$ wrapper. Never drop its sign.
    decimal = (r'(?<![A-Za-z0-9_.])(?P<sign>[-+]?)[ \t]*'
               r'(?P<whole>\d+(?:[ \t]+\d+)*)[ \t]*\.[ \t]*'
               r'(?P<fraction>\d+(?:[ \t]+\d+)*)(?=\s*(?:' + _UNIT + r')(?![A-Za-z]))')
    text = re.sub(decimal, lambda m: m['sign'] + re.sub(r'\s+', '', m['whole']) + '.'
                  + re.sub(r'\s+', '', m['fraction']), text)
    # OCR sometimes splits every integer digit. Join only when a recognizable
    # unit follows; a Markdown bullet remains a bullet because its sign stays
    # separated from the digits.
    ocr_integer = (r'(?<![A-Za-z0-9_.])(?P<whole>\d+(?:[ \t]+\d+)+)'
                   r'(?=[ \t]*(?:' + _UNIT + r'|°C|%|‰))')
    text = re.sub(ocr_integer, lambda m: re.sub(r'\s+', '', m['whole']), text)
    # A spaced sign is a minus only in explicit math/equation context. This
    # handles $- 5 9 mV without turning a Markdown "- 300 C" bullet negative.
    text = re.sub(
        r'(?P<prefix>\$|[=:])\s*(?P<sign>[-+])\s+(?P<number>\d+(?:\.\d+)?)'
        r'(?=\s*(?:' + _UNIT + r'|°C|%|‰))',
        lambda m: m['prefix'] + m['sign'] + m['number'], text)
    # Outside math, a leading "- 300 C" can be a Markdown bullet. Only
    # unambiguous equation signs and signed decimals above are joined.
    text = re.sub(r'(?P<equals>[=:])[ \t]*(?P<sign>[-+])[ \t]+(?=\d)',
                  r'\g<equals>\g<sign>', text)
    # Reference-electrode notation is prose, not an extra seconds unit. OCR
    # sometimes renders "vs." as "\nu s ."; the stripped form is "s .".
    # Requiring SHE (including its explicit OCR form 5HE) keeps V s intact.
    text = re.sub(r'\bV\s+(?:v\s*s\s*\.?|s\s*\.)\s*(?:S\s*H\s*E|5\s*H\s*E)\b',
                  'V (vs. SHE)', text, flags=re.I)
    # Known OCR/TeX degree glyph and multiplication between scalar and unit.
    # Comparison only: the stored quote remains literal and reviewable.
    text = re.sub(r'\^\s*(?:circ|c|o|°)\s*C', '°C', text)
    text = re.sub(r'(?<=\d)\s*[*·]\s*(?=[A-Za-zµ°%‰])', ' ', text)
    # OCR can separate the atoms of an area-normalized current density. Only
    # normalize the complete mA cm^-2 shape; partial forms retain their own
    # dimensions and are never silently promoted to current density.
    text = re.sub(
        r'(?<=\d)\s+m\s+A\s+(?:[·*]\s*)?c\s+m\s*\^?\s*-\s*2(?![A-Za-z0-9])',
        ' mA cm^-2', text)
    text = re.sub(r'mol\s*(?:/\s*L|[· ]\s*L\s*\^?\s*-\s*1)(?![A-Za-z])', 'M', text)
    # OCR math spacing can join a concentration unit to a chemical formula.
    text = re.sub(r'mol\s*/\s*L(?=[A-Z](?:[A-Z0-9_]|\s*_))', 'M ', text)
    text = re.sub(r'(?<![A-Za-z])(?P<prefix>k?)W\s*[·*]\s*h',
                  lambda m: m['prefix'] + 'Wh', text)
    text = re.sub(r'\br\s*/\s*min(?![A-Za-z])', 'r/min', text)
    # OCR occasionally renders molar M as lowercase m/w in an electrolyte
    # formula. Restrict this normalization to explicit chemical formulae.
    electrolyte = (r'(?:KOH|NaOH|LiOH|K2HPO4|KH2PO4|H2SO4|HCl|KCl|NaCl|'
                   r'LiPF6|ZnSO4|FeCl3|FeCl2)(?![A-Za-z0-9])')
    text = re.sub(r'(?<=\d)\s*[mw](?=\s*' + electrolyte + r')', ' M ', text)

    def inverse_group(match):
        body = match.group(1)
        atoms = list(_UNIT_ATOM.finditer(body))
        remainder = _UNIT_ATOM.sub('', body)
        if not atoms or re.sub(r'[\s·*]', '', remainder):
            return match.group()
        return ' ' + ' '.join(
            atom['unit'] + '^' + str(-int(re.sub(r'[\s^]', '', atom['power'] or '') or '1'))
            for atom in atoms)

    text = re.sub(r'/\s*\(([^()]+)\)', inverse_group, text)
    return _repair_raman_ocr_ranges(text)


def _repair_raman_ocr_ranges(text):
    """Repair only OCR-broken Raman/wavenumber ranges, never generic digits."""
    context = re.compile(r'Raman|拉曼|波数|wavenumber', re.I)
    unit = r'cm\s*\^?\s*(?:[-−]\s*)?1(?![A-Za-z0-9])'
    parts = re.split(r'([。!?；;\n])', text)
    for index in range(0, len(parts), 2):
        segment = parts[index]
        if not context.search(segment):
            continue
        # A shared unit may appear only after the second range. Both endpoints
        # still belong to the same bounded wavenumber expression.
        segment = re.sub(
            r'(?<![\d.])(\d{3})(\d{3})(?=\s*(?:and|、|和|,|，|\s)'
            r'[^。!?；;\n]{0,55}?' + unit + r')',
            r'\1–\2', segment, flags=re.I,
        )
        segment = re.sub(
            r'(?<![\d.])(\d{2,4})\s*[-–—~]\s*(\d{2,4})(?=\s*' + unit + r')',
            r'\1–\2', segment, flags=re.I,
        )
        # When several ranges share one trailing wavenumber unit, make that
        # bounded unit explicit on the earlier range as well.
        segment = re.sub(
            r'(?P<first>\d{2,4}–\d{2,4})(?P<middle>\s*(?:and|、|和|,|，)\s*'
            r'\d{2,4}–\d{2,4}\s*)(?P<unit>' + unit + r')',
            lambda match: (match['first'] + ' ' + match['unit'] +
                           match['middle'] + match['unit']),
            segment, flags=re.I,
        )
        parts[index] = segment
    return ''.join(parts)

# Longer compound units precede their prefixes. Conversions are deliberately small
# and explicit; unsupported dimensions never borrow a same-valued scalar elsewhere.
_BASE = {
    '°C': ('temperature:C', '1'), 'K': ('temperature:K', '1'),
    '%': ('ratio', '.01'), '‰': ('ratio', '.001'),
    'nm': ('length', '.000000001'), 'µm': ('length', '.000001'),
    'mm': ('length', '.001'), 'cm': ('length', '.01'), 'm': ('length', '1'),
    'ms': ('time', '.001'), 's': ('time', '1'), 'min': ('time', '60'), 'h': ('time', '3600'),
    'µg': ('mass', '.000001'), 'mg': ('mass', '.001'), 'g': ('mass', '1'), 'kg': ('mass', '1000'),
    'µL': ('volume', '.000001'), 'mL': ('volume', '.001'), 'L': ('volume', '1'),
    'mM': ('concentration', '.001'), 'M': ('concentration', '1'),
    'J': ('energy', '1'), 'kJ': ('energy', '1000'), 'MJ': ('energy', '1000000'), 'GJ': ('energy','1000000000'),
    'Wh': ('energy', '3600'), 'kWh': ('energy', '3600000'),
    'µV': ('voltage', '.000001'), 'mV': ('voltage', '.001'), 'V': ('voltage', '1'),
    'µA': ('current', '.000001'), 'mA': ('current', '.001'), 'A': ('current', '1'),
    'eV': ('electron_energy', '1'), 'meV': ('electron_energy', '.001'),
    'Pa': ('pressure', '1'), 'kPa': ('pressure', '1000'), 'MPa': ('pressure', '1000000'),
    'bar': ('pressure', '100000'), 'atm': ('pressure', '101325'),
    'mol': ('amount', '1'), 'mmol': ('amount', '.001'),
    'rpm': ('rotation_rate', '1'), 'r/min': ('rotation_rate', '1'),
    'mAh': ('charge', '3.6'), 'Ah': ('charge', '3600'),
    'W': ('power','1'), 'mW': ('power','.001'), 'kW': ('power','1000'),
}
_UNIT = '|'.join(re.escape(u) for u in sorted(_BASE, key=len, reverse=True))
_NUMBER = r'[-+]?\d+(?:\.\d+)?(?:\s*(?:[eE]\s*[-+]?\d+|[×x]\s*10\s*\^?\s*[-+]?\d+))?'
_POWER=(r'(?:\s*\^\s*[-+]?\s*\d+'
        r'|\s+[-+]\s*\d+(?!\.\d)'
        r'|[-+]?\d+)?(?!\d)')
_ATOM=r'(?:'+_UNIT+r')'+_POWER
_MEASURE = re.compile(r'(?<![A-Za-z0-9_.])(?P<number>'+_NUMBER+r')\s*'
    r'(?P<expression>'+_ATOM+r'(?:\s*[/·*]?\s*'+_ATOM+r'){0,3})(?![A-Za-z])')
_UNIT_ATOM=re.compile(r'(?P<separator>[/·*]?)\s*(?P<unit>'+_UNIT+r')(?P<power>\s*\^\s*[-+]?\s*\d+|\s*[-+]\s*\d+|\d+)?')
_UNCERTAIN = re.compile(r'存疑|未确认|未核实|未明确|无法确认|不能确认|不确定|不应.*归|不足.*支持|未能支持|未在.*验证|OCR')
_UNIT_UNCERTAIN = re.compile(
    r'(?:单位|温度)[^。;\n]{0,16}(?:存疑|不确定|未确认|未核实|无法确认)|'
    r'(?:原文|OCR)[^。;\n]{0,24}(?:识别|单位)|不可肯定改写', re.I)


def _unit_expression_metrics(expression):
    """Return dimension/factor for a complete unit expression, never a suffix guess."""
    normalized = comparison_text(expression).strip()
    normalized = re.sub(r'^[\[\(（]+|[\]\)）]+$', '', normalized).strip()
    normalized = normalized.replace('·', ' ').replace('*', ' ')
    atoms = list(_UNIT_ATOM.finditer(normalized))
    remainder = _UNIT_ATOM.sub('', normalized)
    if not atoms or re.sub(r'[\s/]', '', remainder):
        return None
    dimensions = {}
    factor = Decimal(1)
    for atom in atoms:
        dimension, atom_factor = _BASE[atom['unit']]
        power = re.sub(r'[\s^]', '', atom['power'] or '')
        exponent = int(power or '1')
        if atom['separator'] == '/':
            exponent = -abs(exponent)
        if abs(exponent) > 12:
            return None
        dimensions[dimension] = dimensions.get(dimension, 0) + exponent
        factor *= Decimal(atom_factor) ** exponent
    dimension = '|'.join(f'{name}^{power}' for name, power in sorted(dimensions.items()) if power)
    if not dimension:
        return None
    return dimension, factor, normalized


def _table_header_unit(cell):
    """Infer a column unit only from an explicit, non-numeric table header."""
    plain = re.sub(r"<[^>]+>", " ", str(cell or ""))
    plain = comparison_text(plain).strip()
    # A numeric data cell such as "80%" must never become a new header.
    if re.fullmatch(r"\s*" + _NUMBER + r"\s*(?:[%‰]|" + _UNIT + r")\s*", plain):
        return None
    bracketed = None
    for match in re.finditer(r"[\[\(（]\s*([^\]\)）]+?)\s*[\]\)）]", plain):
        candidate = match.group(1).strip()
        if _unit_expression_metrics(candidate):
            bracketed = candidate
            break
    voltage_label = re.search(r"\bvoltage\b|电压|电位", plain, re.I)
    if voltage_label:
        # OCR frequently renders [V] as M]. A voltage label is stronger than
        # that one-character OCR artifact, while explicit V/mV still wins.
        if bracketed in {'µV', 'mV', 'V'}:
            return bracketed
        return 'V'
    if bracketed:
        return bracketed
    if re.search(r"[%‰]\s*(?:[\]\)）])?\s*$", plain):
        return "‰" if "‰" in plain[-3:] else "%"
    # A header that is only a unit expression may be written with a leading
    # slash and dots between atoms (/g.m-2, g.m-2). Drop the leading slash
    # first: it marks "per area", not an inverted first atom.
    candidates = [plain.lstrip('/').strip()]
    if not plain.startswith('/'):
        candidates.append(plain)
    # Chinese tables often write "相变焓/kJ·kg-1": the label and unit share a
    # cell. Try the substring after the last slash as well.
    if '/' in plain:
        candidates.append(plain.rsplit('/', 1)[1].strip())
    for candidate in candidates:
        dotted = re.sub(r'(?<=[A-Za-z])\s*\.\s*(?=[A-Za-z])', '·', candidate)
        metrics = _unit_expression_metrics(dotted)
        if metrics:
            return metrics[2]
    match = re.search(r"(?:^|[/\[\(（\s])(?P<unit>" + _UNIT + r")\s*(?:[\]\)）])?\s*$", plain)
    return match["unit"] if match else None


def _table_cell_looks_like_data(cell):
    """Distinguish numeric table data from labels that merely end in a unit."""
    plain = re.sub(r"<[^>]+>", " ", str(cell or ""))
    plain = re.sub(r"\s+", " ", comparison_text(plain)).strip()
    if not plain:
        return False
    # Chemical locants such as 2,6-DHAQ are labels, not numeric observations.
    if re.match(r"^\s*" + _NUMBER + r"\s*,", plain):
        return False
    if re.fullmatch(r"\s*[<>≤≥≈~]?\s*" + _NUMBER + r"\s*", plain):
        return True
    return bool(re.match(r"^\s*[<>≤≥≈~]?\s*" + _NUMBER
                         + r"\s*(?:[%‰]|[A-Za-zµμΩ°])", plain))


def _markdown_table_cells(line, base=0):
    pipes = [match.start() for match in re.finditer(r"\|", line)]
    return [(line[pipes[i] + 1:pipes[i + 1]], base + pipes[i] + 1)
            for i in range(len(pipes) - 1)]


def _is_markdown_separator(cells):
    return bool(cells) and all(re.fullmatch(r"\s*:?-{3,}:?\s*", cell) for cell, _ in cells)


def _table_cell_quantity(cell, start, unit):
    """Read one bare numeric cell, optionally followed by a local citation."""
    match = re.fullmatch(r"\s*(?P<number>" + _NUMBER + r")\s*(?:\[Ref-\d+\]\s*)*", cell)
    metrics = _unit_expression_metrics(unit)
    if not match or not metrics:
        return None
    number = re.sub(r'\s+', '', match["number"])
    dimension, factor, normalized_unit = metrics
    try:
        value = Decimal(number)
    except (InvalidOperation, ArithmeticError):
        return None
    return Quantity(number + normalized_unit, value, dimension, value * factor,
                    start + match.start("number"), start + match.end("number"),
                    unit_origin="table_header")

def _table_inferred_quantities(text):
    """Return bare table cells whose unit comes only from their column header."""
    out = []

    headers = None
    line_matches = list(re.finditer(r"^.*$", text, re.M))
    for line_index, line_match in enumerate(line_matches):
        line = line_match.group()
        if not line.lstrip().startswith("|"):
            headers = None
            continue
        cells = _markdown_table_cells(line, line_match.start())
        if not cells or _is_markdown_separator(cells):
            continue
        units = [_table_header_unit(cell) for cell, _ in cells]
        next_cells = (_markdown_table_cells(line_matches[line_index + 1].group())
                      if line_index + 1 < len(line_matches) else [])
        if any(units) and _is_markdown_separator(next_cells):
            headers = units
            continue
        if headers and len(cells) == len(headers):
            for (cell, start), unit in zip(cells, headers):
                if unit and (quantity := _table_cell_quantity(cell, start, unit)):
                    out.append(quantity)

    # Retrieved evidence can be truncated before </table>; parse a table start
    # through its closing tag, the next table, or the end of the excerpt.
    table_pattern = r"<table\b[^>]*>(.*?)(?=</table>|<table\b|\Z)"
    for table in re.finditer(table_pattern, text, re.I | re.S):
        headers = None
        row_pattern = r"<tr\b[^>]*>(.*?)(?:</tr>|(?=<tr\b)|\Z)"
        for row in re.finditer(row_pattern, table.group(1), re.I | re.S):
            cells = []
            has_th = False
            cell_pattern = r"<(t[dh])\b[^>]*>(.*?)</\1>"
            for cell in re.finditer(cell_pattern, row.group(1), re.I | re.S):
                has_th = has_th or cell.group(1).lower() == "th"
                plain = re.sub(r"<[^>]+>", " ", cell.group(2))
                plain = re.sub(r"\s+", " ", plain).strip()
                absolute = table.start(1) + row.start(1) + cell.start(2)
                cells.append((plain, absolute))
            units = [_table_header_unit(cell) for cell, _ in cells]
            # A data row may contain >0.6 M, 1 m KOH, 99%, etc. Those values
            # must not replace the preceding column headers. Explicit <th>
            # markup is authoritative; otherwise only a label-only unit row is
            # a header.
            data_cells = [cell for cell, _ in cells if _table_cell_looks_like_data(cell)]
            if has_th or (any(units) and not data_cells):
                headers = units
                continue
            if headers and len(cells) == len(headers):
                for (cell, start), unit in zip(cells, headers):
                    if unit and (quantity := _table_cell_quantity(cell, start, unit)):
                        out.append(quantity)
    return out


def _markdown_table_units_for_line(lines, line_number):
    """Return a row's column units from the nearest preceding table header."""
    index = int(line_number) - 1
    if index < 0 or index >= len(lines) or not lines[index].lstrip().startswith("|"):
        return None
    start = index
    while start > 0 and lines[start - 1].lstrip().startswith("|"):
        start -= 1
    for row_index in range(start, index + 1):
        cells = _markdown_table_cells(lines[row_index])
        if not cells or _is_markdown_separator(cells):
            continue
        units = [_table_header_unit(cell) for cell, _ in cells]
        next_cells = (_markdown_table_cells(lines[row_index + 1])
                      if row_index + 1 < len(lines) else [])
        if any(units) and _is_markdown_separator(next_cells):
            return units
    return None


@dataclass(frozen=True)
class Quantity:
    raw: str
    value: Decimal
    dimension: str
    base_value: Decimal
    start: int
    end: int
    unit_origin: str = 'explicit'


def quantities(text, table_units=None):
    """Return comparison spans, never offsets falsely attributed to original OCR."""
    normalized = comparison_text(text)
    out = _table_inferred_quantities(normalized)
    if table_units:
        cells = _markdown_table_cells(normalized)
        if len(cells) == len(table_units):
            for (cell, start), unit in zip(cells, table_units):
                if unit and (quantity := _table_cell_quantity(cell, start, unit)):
                    out.append(quantity)
    for match in _MEASURE.finditer(normalized):
        number = re.sub(r'\s+', '', match['number'])
        number = re.sub(r'[×x]10\^?', 'e', number)
        try:
            value = Decimal(number)
        except InvalidOperation:
            continue
        # "3 M L-his" is a concentration followed by a chemical label, not
        # 3 M multiplied by a litre.  Do not let a chemical abbreviation's
        # leading L become a volume unit and silently change the dimension.
        expression = match['expression']
        # The regex is greedy enough to consume the L of L-his as a litre.
        # The chemical abbreviation itself is still visible after the match.
        trailing = normalized[match.end():]
        if re.fullmatch(r'\s*M\s+L', expression) and re.match(r'[-_][A-Za-z0-9]', trailing):
            expression = re.sub(r'\s+L$', '', expression)
        # A concentration is often followed by a formula whose metal locant
        # looks like a unit power: 0.4 M K4[Fe(CN)6] is not 0.4 M·K^4.
        if re.fullmatch(r'\s*M\s+[A-Z][a-z]?\d+', expression) and re.match(r'[\[(（]', trailing):
            expression = re.sub(r'\s+[A-Z][a-z]?\d+$', '', expression)
        # A percent sign never carries a bare numeric exponent. "80%11" is an
        # OCR join of two percentages, not a ratio to the eleventh power.
        if re.match(r'\s*[%‰]\s*\d', expression):
            continue
        # "×100%" in a formula is a unit conversion factor, not a claim.
        before = normalized[:match.start()].rstrip()
        if (before.endswith(('×', '*'))
                and re.match(r'[%‰]', expression.strip())
                and value in (Decimal(100), Decimal(1000))):
            continue
        dimensions={}
        factor=Decimal(1)
        for atom in _UNIT_ATOM.finditer(expression):
            d,f=_BASE[atom['unit']]
            power=re.sub(r'[\s^]','',atom['power'] or '')
            exponent=int(power or '1')
            if atom['separator']=='/':
                exponent=-abs(exponent)
            # Refuse absurd OCR powers rather than huge Decimal allocations.
            if abs(exponent)>12:
                dimensions={'unparsed_unit':1};factor=Decimal(1);break
            dimensions[d]=dimensions.get(d,0)+exponent
            factor*=Decimal(f)**exponent
        dimension='|'.join(f'{d}^{n}' for d,n in sorted(dimensions.items()) if n)
        lower=re.search(r'(?<![A-Za-z0-9_.])(?P<lower>'+_NUMBER+r')\s*(?:–|—|~|至|到|to)\s*$',normalized[:match.start()])
        if lower:
            low_number=re.sub(r'\s+','',lower['lower'])
            low_number=re.sub(r'[×x]10\^?','e',low_number)
            try:
                low_value=Decimal(low_number)
                out.append(Quantity(lower['lower']+' '+expression+'（区间下界共享单位）',
                    low_value,dimension,low_value*factor,lower.start('lower'),lower.end('lower')))
            except InvalidOperation:
                pass
        else:
            # Explicit lists can share one trailing unit, e.g. 30、45、60min.
            # OCR underscores require an explicit time-list context, so chemical
            # subscripts cannot turn into measurements.
            prefix=normalized[:match.start()]
            listed=re.search(r'(?<![A-Za-z0-9_.])(?P<list>'+_NUMBER+r'(?:\s*(?:、|,|，|_|and)\s*'+_NUMBER+r')*)\s*(?:、|,|，|_|and)\s*$',prefix)
            if listed:
                values=listed['list']
                underscore_ok='_' not in listed.group() or (
                    dimension=='time^1' and re.search(r'时间|时长|time|duration',prefix[max(0,listed.start()-60):listed.start()],re.I))
                if underscore_ok:
                    for value_match in list(re.finditer(_NUMBER,values))[-32:]:
                        # pH is explicitly dimensionless: "pH 7.5、1.6 V"
                        # lists different conditions, not two voltage values.
                        if value_match.start()==0 and re.search(
                                r'(?<![A-Za-z])pH\s*(?:≈|~|=|为|等于|<|>|≤|≥)?\s*$',
                                prefix[:listed.start()], re.I):
                            continue
                        number=re.sub(r'\s+','',value_match.group())
                        number=re.sub(r'[×x]10\^?','e',number)
                        try:
                            listed_value=Decimal(number)
                        except InvalidOperation:
                            continue
                        start=listed.start('list')+value_match.start()
                        end=listed.start('list')+value_match.end()
                        out.append(Quantity(value_match.group()+' '+expression+'（列表共享单位）',
                            listed_value,dimension,listed_value*factor,start,end))
        out.append(Quantity(match.group(), value, dimension, value * factor, match.start(), match.end()))
    # A potential/electrochemical window is a voltage even when OCR loses the
    # trailing unit (e.g. "the potential window is confined to 1.23, ^29").
    # Infer only inside that explicit label, never from a bare number alone.
    window_label = re.compile(
        r'potential\s+window|electrochemical\s+window|voltage\s+window|'
        r'电位窗口|电压窗口|电化学窗口', re.I)
    relation = re.compile(
        r'confined|limited|between|from|of|is|为|约|仅|达|至|是|[:：]', re.I)
    for label in window_label.finditer(normalized):
        tail = normalized[label.end():label.end() + 100]
        # Citation markers such as [Ref-5] carry digits that are not a voltage.
        # Blank them out at equal length so recorded offsets stay valid.
        tail = re.sub(r'\[[^\]\n]*\d[^\]\n]*\]', lambda m: ' ' * len(m.group()), tail)
        number = re.search(r'(?<![A-Za-z0-9_.])(?P<number>' + _NUMBER + r')', tail)
        if not number:
            continue
        between = tail[:number.start()]
        after = tail[number.end():]
        if not relation.search(between):
            continue
        if re.match(r'\s*(?:' + _UNIT + r'|[%‰])(?![A-Za-z])', after):
            continue
        raw_number = re.sub(r'\s+', '', number['number'])
        raw_number = re.sub(r'[×x]10\^?', 'e', raw_number)
        try:
            value = Decimal(raw_number)
        except InvalidOperation:
            continue
        start = label.end() + number.start('number')
        end = label.end() + number.end('number')
        out.append(Quantity(number['number'] + ' V（窗口语境推断单位）',
                            value, 'voltage^1', value, start, end,
                            unit_origin='context_inferred'))
    # A cell may be discovered both explicitly and through its header. Keep one
    # stable record and preserve source order for claim ids.
    deduped = {}
    for quantity in out:
        key = (quantity.start, quantity.end, quantity.dimension, quantity.base_value)
        deduped.setdefault(key, quantity)
    return sorted(deduped.values(), key=lambda quantity: (quantity.start, quantity.end))


def _subjects(text):
    # These are explicit, source-visible subject labels, not inferred identities.
    groups = {
        'L-his': r'(?<![A-Za-z0-9])L[- ]?(?:his|histidine)(?![A-Za-z0-9])|L[- ]?组氨酸',
        '2mIm': r'(?<![A-Za-z0-9])(?:2[- ]?(?:mIm|MI)|2[- ]?methylimidazole)(?![A-Za-z0-9])|2[- ]?甲基咪唑',
    }
    return {label for label, pattern in groups.items() if re.search(pattern, text, re.I)}


def _scopes(text):
    return {label for label,pattern in {
        'near_neutral':r'近中性|near[- ]neutral',
        'acidic':r'酸性|(?<![A-Za-z])acidic(?![A-Za-z])',
        'all_iron':r'全铁|all[- ]iron|(?<![A-Za-z])AIRFB(?![A-Za-z])',
        'iron_chromium':r'铁铬|iron[-– ]chromium|(?<![A-Za-z])ICRFB(?![A-Za-z])',
    }.items() if re.search(pattern,text,re.I)}


_SAMPLE_LABEL = re.compile(r'(?:样品|试样|样本|sample)\s*([A-Za-z](?:\d+)?|\d+)', re.I)
_SAMPLE_CONTRAST = re.compile(r'未加|未添加|未处理|不含|空白|对照|未掺杂|未引入|without|untreated|control', re.I)
_GENERAL_SCOPE = re.compile(
    r'所有(?:的)?(?:样品|试样|样本)|全部(?:样品|试样|样本)|各(?:样品|试样|样本)|'
    r'(?:样品|试样|样本)(?:均|都)|均(?:加入|添加|采用|含|使用)|一律|普遍|通用',
    re.I)
_TIME_TOKEN = r'(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>min|h|s)(?![A-Za-z])'
_TIME_CONDITION = re.compile(_TIME_TOKEN, re.I)
_FIGURE_TIME_CONDITION = re.compile(
    r'(?:图|Fig(?:ure)?)\s*\d+(?:\s*\([^)]*\))?[^。;\n]{0,100}?' + _TIME_TOKEN, re.I)
_LOCAL_TIME_CONDITION = re.compile(
    r'(?:在|经|于|搅拌|保温|反应|处理|煅烧|加热|干燥|静置)[^。;\n]{0,25}?' + _TIME_TOKEN, re.I)
_TIME_SAMPLE_CONDITION = re.compile(_TIME_TOKEN + r'[^。;\n]{0,15}?(?:的)?(?:样品|试样|sample)', re.I)


def _sample_labels(text):
    return {match.group(1).upper() for match in _SAMPLE_LABEL.finditer(str(text or ''))}


def _nearest_sample_label(text, position):
    label = None
    for match in _SAMPLE_LABEL.finditer(str(text or '')[:max(0, int(position))]):
        label = match.group(1).upper()
    return label


def _time_base(value, unit):
    from decimal import Decimal
    factor = {'s': Decimal(1), 'min': Decimal(60), 'h': Decimal(3600)}.get(str(unit).lower())
    try:
        return Decimal(str(value)) * factor if factor is not None else None
    except (ArithmeticError, ValueError):
        return None


def _time_conditions(text):
    """Return every explicit time, including members of a shared-unit list."""
    found = {}
    # The quantity parser resolves forms such as "30、45、...、165 min"
    # into one span per member. Treating only the final explicit match as the
    # claim time made a valid list member look like a different condition.
    for value in quantities(text):
        if value.dimension == 'time^1':
            found[value.base_value] = value.raw
    for match in _TIME_CONDITION.finditer(str(text or '')):
        base = _time_base(match.group('value'), match.group('unit'))
        if base is not None:
            found.setdefault(base, match.group('value') + ' ' + match.group('unit'))
    return found


def _source_time_conditions(before, sentence, position=None):
    """Return explicit time/sample conditions tied to the matched quantity.

    A time earlier in another comma-separated clause (for example a 90 min
    addition followed by a 300 C calcination) is not a condition on the later
    quantity.  The local clause is therefore the primary window; a preceding
    clause is included only when it ends in an explicit time connective.
    """
    sentence = str(sentence or '')
    if position is None:
        windows = [sentence]
    else:
        position = max(0, min(len(sentence), int(position)))
        left = max(sentence.rfind(s, 0, position) for s in ('，', ',', '；', ';', '。', '\n')) + 1
        rights = [sentence.find(s, position) for s in ('，', ',', '；', ';', '。', '\n')]
        right = min([n for n in rights if n >= 0] or [len(sentence)])
        windows = [sentence[left:right]]
        # "在90 min时，加入..." places the condition immediately before a
        # comma.  Keep that clause only for this explicit connective form.
        prior = sentence[:left].rstrip()
        if re.search(r'(?:时|后|min|h|s)\s*$', prior, re.I) and position-left <= 80:
            prior_left = max(prior.rfind(s, 0, len(prior)) for s in ('，', ',', '；', ';', '。', '\n')) + 1
            windows.insert(0, prior[prior_left:])
    found = {}
    for window in windows:
        for pattern in (_LOCAL_TIME_CONDITION, _TIME_SAMPLE_CONDITION):
            for match in pattern.finditer(window):
                base = _time_base(match.group('value'), match.group('unit'))
                if base is not None:
                    found[base] = match.group('value') + ' ' + match.group('unit')
        for pattern in (_FIGURE_TIME_CONDITION, _TIME_SAMPLE_CONDITION):
            for match in pattern.finditer(str(before or '')[-500:]):
                base = _time_base(match.group('value'), match.group('unit'))
                if base is not None:
                    found[base] = match.group('value') + ' ' + match.group('unit')
    return found


def _table_condition_context(lines, line_no):
    """Bind a table value to same-process rows such as temperature and time."""
    if not (0 < line_no <= len(lines)):
        return ''
    line = lines[line_no - 1]
    if not line.lstrip().startswith('|'):
        return line

    def cells(value):
        return [cell.strip() for cell in value.strip().strip('|').split('|')]

    current = cells(line)
    if not current:
        return line
    label = re.sub(r'\s+', '', current[0])
    if not label or re.fullmatch(r'[-:]+', label):
        return line
    selected = {line_no - 1}
    for direction in (-1, 1):
        index = line_no - 2 if direction < 0 else line_no
        while 0 <= index < len(lines) and lines[index].lstrip().startswith('|'):
            other = cells(lines[index])
            other_label = re.sub(r'\s+', '', other[0]) if other else ''
            common_length = 0
            for left, right in zip(label, other_label):
                if left != right:
                    break
                common_length += 1
            if common_length >= 4:
                selected.add(index)
            index += direction
    return '\n'.join(lines[index] for index in sorted(selected))


def _condition_binding_issue(claim, match):
    """Flag only explicit sample/time restrictions that the claim drops or changes."""
    sentence = str(match.get('source_sentence') or '')
    before = str(match.get('source_before') or '')
    source_labels = _sample_labels(sentence)
    claim_labels = _sample_labels(claim)
    source_label = _nearest_sample_label(sentence, match.get('source_quantity_start', 0))
    claim_generalizes = bool(_GENERAL_SCOPE.search(claim))
    source_times = _source_time_conditions(before, sentence, match.get('source_quantity_start'))
    claim_times = _time_conditions(claim)
    reasons = []
    codes = []
    conditions = []
    # A single generic mention of "样品" is not a restriction. Require either
    # multiple labelled samples or an explicit contrast such as "样品B未加".
    if source_label and (len(source_labels) >= 2 or _SAMPLE_CONTRAST.search(sentence)):
        conditions.append('sample:' + source_label)
        if claim_generalizes:
            reasons.append('source limits this quantity to sample ' + source_label + '; claim generalizes to all samples')
            codes.append('sample_generalization')
        elif claim_labels:
            if source_label not in claim_labels:
                reasons.append('source binds this quantity to sample ' + source_label + ', not ' + ', '.join(sorted(claim_labels)))
                codes.append('sample_mismatch')
            elif claim_labels - {source_label}:
                reasons.append('claim extends this quantity from sample ' + source_label +
                               ' to ' + ', '.join(sorted(claim_labels - {source_label})))
                codes.append('sample_extension')
        else:
            reasons.append('source limits this quantity to sample ' + source_label + '; claim does not identify the sample')
            codes.append('sample_omission')
    if source_times:
        conditions.extend('time:' + value for value in source_times.values())
        if not claim_times:
            reasons.append('source ties this quantity to a stated time/sample condition; claim omits it')
            codes.append('time_omission')
        elif not (set(source_times) & set(claim_times)):
            reasons.append('claim time condition differs from the source condition')
            codes.append('time_mismatch')
    if not reasons:
        return None
    return {'reason': '; '.join(reasons), 'codes': sorted(set(codes)),
            'source_conditions': conditions,
            'claim_conditions': ['sample:' + x for x in sorted(claim_labels)] +
                                ['time:' + value for value in claim_times.values()]}


def _claim_subjects(claim, position=None):
    """A comparison object is not a co-subject sharing the preceding value."""
    comparison=re.search(r'优于|高于|低于|劣于|better\s+than|higher\s+than|lower\s+than',claim,re.I)
    if comparison:
        focused=_subjects(claim[:comparison.start()])
        if len(focused)==1:return focused
    stop = len(claim) if position is None else max(0, min(len(claim), int(position)))
    prefix = claim[:stop]
    # An explicit "among these, X ..." selects X only for values after it.
    # It must never back-propagate to an earlier L-his value in the sentence.
    focus = list(re.finditer(r'其中', prefix))
    if focus:
        scope = prefix[focus[-1].end():]
        focused = _subjects(scope)
        if len(focused) == 1:
            return focused
    # Prefer the nearest explicit subject before the value. If the subject
    # follows the number (for example "0.2 M 2-mIm"), inspect a short suffix.
    nearest = None
    for label, pattern in {
        'L-his': r'(?<![A-Za-z0-9])L[- ]?(?:his|histidine)(?![A-Za-z0-9])|L[- ]?组氨酸',
        '2mIm': r'(?<![A-Za-z0-9])(?:2[- ]?(?:mIm|MI)|2[- ]?methylimidazole)(?![A-Za-z0-9])|2[- ]?甲基咪唑',
    }.items():
        for match in re.finditer(pattern, prefix, re.I):
            if nearest is None or match.start() > nearest[0]:
                nearest = (match.start(), label)
    if nearest:
        return {nearest[1]}
    following = _subjects(claim[stop:stop + 45])
    if len(following) == 1:
        return following
    return _subjects(claim)


_SECTION_HEADING = re.compile(
    r'^\s*(?:#{1,6}\s+|\*\*[一二三四五六七八九十\d]+[、.．])'
)
_LIST_ITEM = re.compile(
    r'^\s*(?:[-*+]\s+|\d+[.)、]\s*|[①②③④⑤⑥⑦⑧⑨⑩])'
)


def _line_refs(line):
    return {int(value) for value in re.findall(r'\[Ref-(\d+)\]', str(line or ''))}


def _section_single_source_refs(lines, line_index):
    """A cited list section may lend one unambiguous source to its list rows."""
    if not (0 <= line_index < len(lines)) or not _LIST_ITEM.match(lines[line_index]):
        return set()
    refs = set()
    for index in range(line_index, -1, -1):
        line = lines[index]
        if _SECTION_HEADING.match(line):
            refs.update(_line_refs(line))
            return refs if len(refs) == 1 else set()
        if not line.strip():
            continue
        if _LIST_ITEM.match(line) or line[:1].isspace():
            refs.update(_line_refs(line))
            continue
        # A separate prose paragraph breaks list-level source inheritance.
        return set()
    return set()


def _table_single_source_refs(lines, line_index):
    """A citation in one unambiguous table header may cover data rows."""
    if not (0 <= line_index < len(lines)) or not lines[line_index].lstrip().startswith('|'):
        return set()
    start = line_index
    end = line_index
    while start > 0 and lines[start - 1].lstrip().startswith('|'):
        start -= 1
    while end + 1 < len(lines) and lines[end + 1].lstrip().startswith('|'):
        end += 1
    refs = set().union(*(_line_refs(line) for line in lines[start:end + 1]))
    return refs if len(refs) == 1 else set()


def _table_column_refs(lines, line_index):
    """Per-column sources when a table header cites a different ref per column."""
    if not (0 <= line_index < len(lines)) or not lines[line_index].lstrip().startswith('|'):
        return None
    start = line_index
    while start > 0 and lines[start - 1].lstrip().startswith('|'):
        start -= 1
    header = lines[start].strip()
    if not header.startswith('|'):
        return None
    cells = header.split('|')
    if cells and not cells[0].strip():
        cells = cells[1:]
    if cells and not cells[-1].strip():
        cells = cells[:-1]
    refs_per_cell = [{int(n) for n in re.findall(r'\[Ref-(\d+)\]', cell)} for cell in cells]
    if sum(1 for refs in refs_per_cell if refs) < 2:
        return None
    return refs_per_cell


def audit_quantities(answer, catalog):
    """Per-claim citations, units and source windows; all results remain heuristic."""
    from .claim_sections import heading_contexts
    headings=heading_contexts(answer)
    answer_lines = answer.splitlines()
    indexed = [(qid, item, quantities(item['quote'])) for qid, item in catalog.items()]
    records = []
    blocks={}
    block=[]
    def flush():
        for n,_ in block:blocks[n]='\n'.join(value for _,value in block)
    for n,line in enumerate(answer_lines,1):
        if not line.strip():flush();block=[]
        else:
            if re.match(r'^\s*(?:#{1,6}\s|\*\*[一二三四五六七八九十\d]+[、.．])',line):
                flush();block=[]
            block.append((n,line))
    flush()
    for line_no, line in enumerate(answer_lines, 1):
        refs = {int(n) for n in re.findall(r'\[Ref-(\d+)\]', line)}
        citation_resolution='explicit_line' if refs else 'missing'
        # A single citation in one contiguous paragraph can cover its list.
        # Never infer among multiple sources, across blanks, or across headings.
        paragraph_refs={int(n) for n in re.findall(r'\[Ref-(\d+)\]',blocks.get(line_no,line))}
        if not refs and _LIST_ITEM.match(line):
            section_refs = _section_single_source_refs(answer_lines, line_no - 1)
            if len(section_refs) == 1:
                refs = section_refs
                citation_resolution = 'same_section_single_source'
        if not refs and line.lstrip().startswith('|'):
            table_refs = _table_single_source_refs(answer_lines, line_no - 1)
            if len(table_refs) == 1:
                refs = table_refs
                citation_resolution = 'same_table_single_source'
        if not refs and len(paragraph_refs)==1:
            refs=paragraph_refs
            citation_resolution='same_paragraph_single_source'
        normalized = comparison_text(line)
        table_units = _markdown_table_units_for_line(answer_lines, line_no)
        column_refs = (_table_column_refs(answer_lines, line_no - 1)
                       if not refs and line.lstrip().startswith('|') else None)
        for index, quantity in enumerate(quantities(line, table_units=table_units), 1):
            # A table may cite one source per column. Use the column's own source
            # for row cells instead of demanding a per-row marker.
            active_refs = refs
            active_resolution = citation_resolution
            if not active_refs and column_refs:
                column = normalized[:quantity.start].count('|') - 1
                if 0 <= column < len(column_refs) and column_refs[column]:
                    active_refs = column_refs[column]
                    active_resolution = 'same_table_column_source'
            # Restrict subject/qualification checks to the local sentence, not an
            # unrelated full-answer disclaimer. Ref resolution stays line-local.
            left = max(normalized.rfind(s, 0, quantity.start) for s in ('。', ';', '；', '!', '?')) + 1
            ends = [normalized.find(s, quantity.end) for s in ('。', ';', '；', '!', '?')]
            right = min([n for n in ends if n >= 0] or [len(normalized)])
            claim = normalized[left:right]
            condition_claim = _table_condition_context(answer_lines, line_no)
            wanted = _claim_subjects(claim, quantity.start - left)
            claim_scopes=_scopes(headings[line_no]+' '+blocks.get(line_no,line))
            matches, wrong_units, cross_ref_candidates = [], [], []
            for qid, item, source_values in indexed:
                text = comparison_text(item['quote'])
                if active_refs and item['ref_id'] not in active_refs:
                    # Diagnostic only: expose same-value sources outside the
                    # cited refs so a retry can correct an attribution error.
                    # These never count as support for the current draft.
                    for value in source_values:
                        if quantity.dimension != value.dimension or quantity.base_value != value.base_value:
                            continue
                        start = max([text.rfind(s, 0, value.start) for s in ('。', ';', '；', '\n')] + [-1]) + 1
                        ends = [text.find(s, value.end) for s in ('。', ';', '；', '\n')]
                        end = min([n for n in ends if n >= 0] or [len(text)])
                        cross_ref_candidates.append({
                            'quote_id':qid,'ref_id':item['ref_id'],'source_id':item.get('source_id'),
                            'quantity':value.raw,'unit_origin':value.unit_origin,
                            'source_sentence':text[start:end],
                            'source_before':text[max(0,value.start-45):value.start],
                            'source_quantity_start':value.start-start,
                            'subjects':sorted(_subjects(text[start:end])),
                            'scope_signals':sorted(_scopes(str(item.get('title') or '')+' '+text[start:end]))})
                    continue
                for value in source_values:
                    if quantity.dimension != value.dimension or quantity.base_value != value.base_value:
                        if quantity.value == value.value:
                            wrong_start = max([text.rfind(s, 0, value.start) for s in ('。', ';', '；', '\n')] + [-1]) + 1
                            wrong_ends = [text.find(s, value.end) for s in ('。', ';', '；', '\n')]
                            wrong_end = min([n for n in wrong_ends if n >= 0] or [len(text)])
                            wrong_units.append({'quote_id':qid,'source_id':item.get('source_id'), 'raw':value.raw,
                                                'dimension':value.dimension,
                                                'unit_origin':value.unit_origin,
                                                'source_before':text[max(0,value.start-45):value.start],
                                                'source_after':text[value.end:value.end+20],
                                                'source_sentence':text[wrong_start:wrong_end],
                                                'source_quantity_start':value.start-wrong_start,
                                                'subjects':sorted(_subjects(text[wrong_start:wrong_end])),
                                                'scope_signals':sorted(_scopes(str(item.get('title') or '')+' '+text[wrong_start:wrong_end]))})
                        continue
                    start = max([text.rfind(s, 0, value.start) for s in ('。', ';', '；', '\n')] + [-1]) + 1
                    ends = [text.find(s, value.end) for s in ('。', ';', '；', '\n')]
                    end = min([n for n in ends if n >= 0] or [len(text)])
                    matches.append({'quote_id':qid,'ref_id':item['ref_id'],'source_id':item.get('source_id'),
                        'quantity':value.raw,'comparison_start':value.start,'comparison_end':value.end,
                        'unit_origin':value.unit_origin,
                        'source_sentence':text[start:end],
                        'source_before':text[max(0,value.start-45):value.start],
                        'source_quantity_start':value.start-start,
                        'subjects':sorted(_subjects(text[start:end])),
                        'scope_signals':sorted(_scopes(str(item.get('title') or '')+' '+text[start:end]))})
            supported_subjects = set().union(*(set(m['subjects']) for m in matches)) if matches else set()
            missing_subjects = wanted - supported_subjects
            source_scopes=set().union(*(set(m['scope_signals']) for m in matches)) if matches else set()
            scope_conflict=(('acidic' in claim_scopes and 'near_neutral' not in claim_scopes and
                             'near_neutral' in source_scopes and 'acidic' not in source_scopes) or
                            ('iron_chromium' in claim_scopes and 'all_iron' not in claim_scopes and
                             'all_iron' in source_scopes and 'iron_chromium' not in source_scopes))
            condition_issues=[]
            condition_compatible_matches=0
            for match in matches:
                issue=_condition_binding_issue(condition_claim,match)
                if issue:
                    condition_issues.append(dict(issue,quote_id=match['quote_id'],ref_id=match['ref_id'],
                                                 quantity=match['quantity']))
                else:
                    condition_compatible_matches+=1
            # The same scalar can occur in several source processes.  A time
            # mismatch on one occurrence must not invalidate another occurrence
            # whose conditions match the claim.
            blocking_condition_issues=([] if condition_compatible_matches else condition_issues)
            # Only an actual ambiguous temperature OCR glyph can license a
            # qualified Celsius mention. "Uncertain" cannot excuse arbitrary
            # voltage/time/unit substitutions or wrong subjects/conditions.
            ocr_temperature_candidates=[
                m for m in wrong_units
                if ((quantity.dimension=='temperature:C^1' and m['dimension']=='ratio^1'
                     and re.search(r'[%‰]',m['raw']))
                    or (quantity.dimension=='ratio^1' and m['dimension']=='temperature:C^1'
                        and re.search(r'[%‰]',quantity.raw)))
                and (re.search(r'(?:温度|加热|temperature)[^。;\n]{0,25}$',m['source_before'],re.I)
                     or '干燥箱' in m['source_after'][:15])
                and not re.search(r'效率|湿度|efficiency|humidity',m['source_before'][-30:],re.I)
            ]
            ocr_temperature=bool(ocr_temperature_candidates)
            ocr_condition_issues=[
                dict(issue, quote_id=m['quote_id'], source_id=m.get('source_id'), quantity=m['raw'])
                for m in ocr_temperature_candidates
                if (issue := _condition_binding_issue(condition_claim,m)) is not None]
            ocr_temperature_condition_compatible=(bool(ocr_temperature_candidates)
                                                  and not ocr_condition_issues)
            # An explicit unit-uncertainty disclaimer may refer to several
            # process times without asserting one of them.  It can ignore only
            # time omissions, never a conflicting time or a sample mismatch.
            claim_times = _time_conditions(condition_claim)
            binding_issues = condition_issues + ocr_condition_issues
            unit_uncertainty_omission=(
                bool(_UNIT_UNCERTAIN.search(claim)) and not claim_times
                and bool(binding_issues)
                and all(set(issue.get('codes') or []) == {'time_omission'}
                        for issue in binding_issues)
                and (quantity.dimension == 'ratio^1' or ocr_temperature))
            ocr_condition_ok=(ocr_temperature_condition_compatible
                              and bool(_UNIT_UNCERTAIN.search(claim)))
            ocr_condition_conflict=(bool(ocr_temperature_candidates)
                                    and not ocr_temperature_condition_compatible)
            condition_blocked=((bool(blocking_condition_issues)
                                or (not matches and ocr_condition_conflict))
                               and not unit_uncertainty_omission
                               and not ocr_condition_ok)
            # A percent/per-mille OCR glyph may be reported as uncertain, but
            # it does not prove an explicit Celsius reading. Only the original
            # percent form may use that OCR escape hatch.
            qualified=(bool(_UNCERTAIN.search(claim)) and not scope_conflict
                       and not condition_blocked and not missing_subjects
                       and (bool(matches) or
                            (ocr_temperature and quantity.dimension == 'ratio^1')))
            if active_refs and qualified:
                status = 'qualified_uncertainty'
            elif not active_refs:
                status = 'missing_local_citation'
            elif not matches and not condition_blocked:
                status = 'unsupported_quantity_or_unit'
            elif scope_conflict or condition_blocked:
                status = 'unsupported_condition_binding'
            elif len(wanted) > 1 and missing_subjects:
                status = 'unsupported_subject_binding'
            elif wanted and supported_subjects and missing_subjects:
                status = 'unsupported_subject_binding'
            else:
                status = 'matched_quantity'
            records.append({'claim_id':f'L{line_no:04d}.Q{index}', 'line_number':line_no,
                'answer_line':line,'quantity':quantity.raw,'comparison_start':quantity.start,'comparison_end':quantity.end,
                'unit_origin':quantity.unit_origin,
                'ref_ids':sorted(active_refs),'dimension':quantity.dimension,'status':status,
                'citation_resolution':active_resolution,
                'matches':matches[:8] if active_refs else [],
                'uncited_candidate_matches':matches[:3] if not active_refs else [],
                'cross_ref_candidates':cross_ref_candidates[:3],
                'same_scalar_other_units':wrong_units[:5],
                'condition_binding_issues':condition_issues,
                'blocking_condition_binding_issues':blocking_condition_issues,
                'ocr_temperature_candidates':ocr_temperature_candidates[:5],
                'ocr_condition_binding_issues':ocr_condition_issues,
                'source_conditions':sorted({c for issue in condition_issues for c in issue['source_conditions']}),
                'claim_conditions':sorted({c for issue in condition_issues for c in issue['claim_conditions']}),
                'unmatched_subjects':sorted(missing_subjects),'claim_scope_signals':sorted(claim_scopes),
                'source_scope_signals':sorted(source_scopes),'semantic_support_verified':False})
    return records


