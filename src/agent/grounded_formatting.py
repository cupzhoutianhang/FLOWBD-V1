"""Narrow formatting repairs with explicit existing source links; no citation guess."""
import re
from .quantity_grounding import audit_quantities, quantities, comparison_text, _UNIT


def format_grounded_notes(answer, catalog, notes, sources=None):
    changes = []
    if sources:
        from .source_guidance import relabel_scope_guidance
        answer,changes=relabel_scope_guidance(answer,sources,catalog)
    lines = answer.splitlines()
    for index, line in enumerate(lines):
        refs = {int(n) for n in re.findall(r'\[Ref-(\d+)\]', line)}
        for note in notes:
            resolutions = note.get('resolved_by_pdf', [])
            if not resolutions or note['ref_id'] in refs:
                continue
            compact = re.sub(r'\s+', '', comparison_text(line))
            old_value = re.escape(note['value']) + r'[%‰]'
            if (refs & {r['ref_id'] for r in resolutions}
                    and re.search(r'原OCR.{0,8}识别', line, re.I)
                    and re.search(r'(?:原)?PDF.{0,8}核对', line, re.I)
                    and re.search(old_value, compact)
                    and note['value']+'°C' in compact):
                # This source is the origin of the quoted OCR transcription,
                # not an inferred source for the corrected temperature.
                marker=f"[Ref-{note['ref_id']}]"
                line += marker
                refs.add(note['ref_id'])
                changes.append(dict(kind='cite_existing_ocr_record',line=index+1,ref_id=note['ref_id'],
                                    source_id=note['source_id'],value=note['value']))
        lines[index]=line
    answer='\n'.join(lines)
    checked=audit_quantities(answer,catalog)
    supported=[q for q in checked if q['status']=='matched_quantity' and q['citation_resolution']=='explicit_line']
    # Rate-gap statements need not repeat endpoint temperatures already
    # supported in the named process step. Replace only the duplicate numeric
    # endpoints, and only when every endpoint is backed by an explicit line.
    def supported_temperature(text):
        values=quantities(text)
        if len(values)!=1:
            return None
        target=values[0]
        backing=[q for q in supported
                 if any(v.dimension==target.dimension and v.base_value==target.base_value
                        for v in quantities(q['quantity']))]
        return backing or None
    gap_negation=r'(?:尚未|未被|未|并未)(?:在[^，,。；;\n]{0,24})?(?:明确|给出|提供|说明)'
    ramp_pattern=re.compile(r'(?P<prefix>[^，,。；;\n]{2,24}?)(?:从室温)?升至(?P<target>\d+(?:\.\d+)?\s*(?:℃|°\s*C))(?P<suffix>的?(?:升温|加热)速率'+gap_negation+r')$')
    parenthetical_ramp=re.compile(r'（从室温到(?P<target>\d+(?:\.\d+)?\s*(?:℃|°\s*C))的加热速率）')
    cooling_pattern=re.compile(r'从(?P<start>\d+(?:\.\d+)?\s*(?:℃|°\s*C))(?P<mode>自然)?冷却至(?P<end>\d+(?:\.\d+)?\s*(?:℃|°\s*C))(?P<suffix>的冷却速率'+gap_negation+r')')
    for index,line in enumerate(lines):
        if re.search(r'\[Ref-\d+\]',line):
            continue
        parts=re.split(r'([。；;])',line)
        for position in range(0,len(parts),2):
            fragment=parts[position]
            match=ramp_pattern.search(fragment)
            if match:
                backing=supported_temperature(match['target'])
                if backing:
                    replacement=match.group().replace(match['target'],'目标温度',1)
                    fragment=fragment[:match.start()]+replacement+fragment[match.end():]
                    changes.append(dict(kind='simplify_duplicate_ramp_gap',line=index+1,
                                        original=match.group(),replacement=replacement,
                                        supported_claim_ids=[q['claim_id'] for q in backing]))
            match=parenthetical_ramp.search(fragment)
            if match:
                backing=supported_temperature(match['target'])
                if backing:
                    replacement='（从室温到目标温度的加热速率）'
                    fragment=fragment[:match.start()]+replacement+fragment[match.end():]
                    changes.append(dict(kind='simplify_duplicate_parenthetical_ramp_gap',line=index+1,
                                        original=match.group(),replacement=replacement,
                                        supported_claim_ids=[q['claim_id'] for q in backing]))
            match=cooling_pattern.search(fragment)
            if match:
                start_backing=supported_temperature(match['start'])
                end_backing=supported_temperature(match['end'])
                if start_backing and end_backing:
                    mode=match['mode'] or ''
                    replacement='从熔融温度'+mode+'冷却至目标温度'+match['suffix']
                    fragment=fragment[:match.start()]+replacement+fragment[match.end():]
                    changes.append(dict(kind='simplify_duplicate_cooling_gap',line=index+1,
                                        original=match.group(),replacement=replacement,
                                        supported_claim_ids=sorted({q['claim_id'] for q in start_backing+end_backing})))
            parts[position]=fragment
        lines[index]=''.join(parts)

    # A bullet that explicitly says a value is unconfirmed must not repeat the
    # unconfirmed value as if it were a local factual claim. Keep the gap
    # statement, but remove only the numeric/unit duplicate from that sentence.
    gap_value = r'[-+]?\d+(?:\.\d+)?\s*(?:[%‰℃]|' + _UNIT + r')'
    gap_phrase = re.compile(
        r'(?P<lead>(?:无法|不能|未能|尚未)(?:确认|核实|明确)(?:为|是)?)\s*'
        r'(?P<value>' + gap_value + r')')
    only_known_gap = re.compile(
        r'[（(]\s*仅知\s*(?P<value>' + gap_value + r')\s*(?:为|是)'
        r'[^）)\n]{0,80}[）)]')
    for index,line in enumerate(lines):
        if re.search(r'\[Ref-\d+\]',line):
            continue
        if not re.match(r'\s*(?:[-*]|\d+[.)])\s*',line):
            continue
        if not re.search(r'缺口|存疑|不确定|OCR|识别|未确认|无法确认|不能确认|未核实|未明确|未在|未给出|未提供|未说明',line,re.I):
            continue
        rewritten,count=gap_phrase.subn(
            lambda m: m['lead']+'其原文数值与单位',line)
        if count:
            lines[index]=rewritten
            changes.append(dict(kind='simplify_unconfirmed_numeric_gap',line=index+1,
                                original=line,replacement=rewritten,replacements=count))
            line=rewritten
        match=only_known_gap.search(line)
        if match:
            values=quantities(match['value'])
            if values:
                target=values[0]
                backing=[q for q in supported
                         if any(v.dimension==target.dimension and v.base_value==target.base_value
                                for v in quantities(q['quantity']))]
                if backing:
                    rewritten=line[:match.start()]+line[match.end():]
                    lines[index]=rewritten
                    changes.append(dict(kind='remove_redundant_supported_gap_value',line=index+1,
                                        original=line,replacement=rewritten,
                                        supported_claim_ids=[q['claim_id'] for q in backing]))

    # An answer that asserts a Celsius reading while quoting the source's
    # percent glyph is not supported: the source only ever said "80%". Keep the
    # decisive statement but restore the glyph the source actually used. The
    # percent form must repeat the same number right next to the claim.
    celsius_claim = re.compile(r'(?<![\d.])(?P<value>\d+(?:\.\d+)?)\s*℃(?P<rest>[^。\n]{0,60})')
    def restore_glyph(match):
        value = match['value']
        if re.search(r'(?<![\d.])' + re.escape(value) + r'\s*[%‰]', match['rest']):
            return value + '%' + match['rest']
        return match.group()
    for index, line in enumerate(lines):
        if not re.search(r'存疑|不确定|未确认|不可肯定', line):
            continue
        rewritten, count = celsius_claim.subn(restore_glyph, line)
        if count and rewritten != line:
            changes.append(dict(kind='restore_uncertain_percent_glyph', line=index+1,
                                original=line, replacement=rewritten))
            lines[index] = rewritten

    # A gap bullet that is not cited must not repeat an "uncertain" OCR token
    # (for example a quoted 80% unit that the source never gave as a value).
    # Drop only the parenthetical that carries the unconfirmed value.
    from .quantity_grounding import _section_single_source_refs
    uncertain_gap = re.compile(r'缺口|存疑|不确定|OCR|识别|未确认|无法确认|不能确认|未核实|未明确|未获得|未提供|未给出')
    parenthetical = re.compile(r'[（(][^（）()\n]{0,120}[）)]')
    for index,line in enumerate(lines):
        if not re.match(r'\s*(?:[-*]|\d+[.)])\s*',line):
            continue
        if re.search(r'\[Ref-\d+\]',line) or _section_single_source_refs(lines,index):
            continue
        if not uncertain_gap.search(line):
            continue
        fragments=[]
        position=0
        for match in parenthetical.finditer(line):
            inner=match.group()
            if quantities(inner) and re.search(r'存疑|不确定|OCR|识别|未确认|无法确认|不可肯定',inner):
                fragments.append(line[position:match.start()])
                position=match.end()
                changes.append(dict(kind='drop_uncited_uncertain_gap_value',line=index+1,
                                    original=line,replacement=match.group()))
        if fragments:
            lines[index]=''.join(fragments)+line[position:]
            line=lines[index]

    # An example value inside a "we did not find this" statement must be backed
    # by the cited sources. Unbacked values such as (如"潜热衰减<10%即合格") are
    # model-invented thresholds: remove that parenthetical, keep the gap text.
    # Only absence-marked sentences qualify, so an asserted threshold keeps its
    # true quantity finding.
    checked_after = audit_quantities('\n'.join(lines), catalog)
    unsupported_by_line = {}
    for row in checked_after:
        if row['status'] in {'unsupported_quantity_or_unit','missing_local_citation'}:
            unsupported_by_line.setdefault(row['line_number'], []).append(row)
    absence = re.compile(r'未找到|未检索到|未提供|未给出|未明确|未涉及|未获得|缺乏|缺口|没有给出')
    example_paren = re.compile(
        r'(?:如|例如|比如|诸如|像是|像)\s*[（(][^（）()\n]{0,120}[）)]'
        r'|[（(]\s*(?:如|例如|比如|诸如)[^（）()\n]{0,120}[）)]')
    for index,line in enumerate(lines):
        rows=unsupported_by_line.get(index+1)
        if not rows or not absence.search(line):
            continue
        fragments=[]
        position=0
        for match in example_paren.finditer(line):
            inside = quantities(match.group())
            unbacked=[row for row in rows
                      if any(quantity.dimension==value.dimension
                             and quantity.base_value==value.base_value
                             for quantity in inside
                             for value in quantities(row['quantity']))]
            if not unbacked:
                continue
            fragments.append(line[position:match.start()])
            position=match.end()
            changes.append(dict(kind='drop_unsupported_example_value',line=index+1,
                                original=line,replacement=match.group(),
                                claim_ids=[row['claim_id'] for row in unbacked]))
        if fragments:
            lines[index]=''.join(fragments)+line[position:]

    # A line with no citation at all must not carry an illustrative or
    # threshold value (如潜热下降9.5%, 通常<10%). The fact stays, the uncited
    # example number goes. Table rows are covered by per-column sources.
    example_or_threshold = (r'(?:如|例如|比如|诸如|像是|像') + r'|[<>≤≥]|通常|一般|约)'
    uncited_value_paren = re.compile(
        example_or_threshold + r'\s*[（(][^（）()\n]{0,120}[）)]'
        r'|[（(][^（）()\n]{0,120}' + example_or_threshold + r'[^（）()\n]{0,120}[）)]')
    for index,line in enumerate(lines):
        if not line.strip() or re.search(r'\[Ref-\d+\]',line):
            continue
        if line.lstrip().startswith('|'):
            continue
        if _section_single_source_refs(lines,index):
            continue
        fragments=[]
        position=0
        for match in uncited_value_paren.finditer(line):
            if not quantities(match.group()):
                continue
            fragments.append(line[position:match.start()])
            position=match.end()
            changes.append(dict(kind='drop_uncited_example_value',line=index+1,
                                original=line,replacement=match.group()))
        if fragments:
            lines[index]=''.join(fragments)+line[position:]
    return '\n'.join(lines),changes
