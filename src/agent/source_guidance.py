"""Keep analyst guidance separate from claims actually written in a source."""
import re

PROHIBITION=r'不得|禁止|不能|不应|不可|不允许|必须'
ATTRIBUTION=re.compile(r'(?:文献|论文|原文|作者)[^。；;\n]{0,12}(?:明确|规定|要求|强调|指出)[^。；;\n]{0,12}(?:'+PROHIBITION+r')')


def scope_attribution_issues(answer, sources, catalog):
    """Reject a narrow observed misattribution, not all interpretive language.

    A real cited prohibition leaves semantic judgment to source screening.
    This check applies only to documents with explicit analyst scope records.
    """
    scope_refs={d['ref_id'] for d in sources if any(
        (c.get('audit_record') or {}).get('scope') for c in d.get('chunks',[]))}
    issues=[]
    for i,line in enumerate(answer.splitlines(),1):
        refs={int(v) for v in re.findall(r'\[Ref-(\d+)\]',line)}
        if not refs & scope_refs or not ATTRIBUTION.search(line):
            continue
        original_quotes=[q['quote'] for q in catalog.values() if q['ref_id'] in refs]
        if not any(re.search(PROHIBITION,q) for q in original_quotes):
            issues.append(f'L{i:04d} 范围说明不是论文原句：不得把系统使用边界归为文献明确规定；保留样品事实并以本次证据的推断边界说明。')
    return issues


def relabel_scope_guidance(answer, sources, catalog):
    """Relabel one observed analyst restriction; never change scientific facts.

    Only the exact misattribution is changed, and only when its cited source
    has analyst scope metadata but no original prohibition. Values, conditions,
    references and the rest of the line stay byte-for-byte unchanged.
    """
    bad_lines={int(re.match(r'L(\d+)',issue)[1]) for issue in scope_attribution_issues(answer,sources,catalog)}
    lines=answer.splitlines();changes=[]
    original='文献明确不得写成'
    replacement='本次证据不足以支持将其写成'
    for i,line in enumerate(lines,1):
        if i not in bad_lines or original not in line:
            continue
        # The relabel is limited to generalization restrictions, not an
        # unrelated experimental prohibition or scientific negative claim.
        if not re.search(re.escape(original)+r'[^。；;\n]{0,24}(?:全部|通用|默认)',line):
            continue
        lines[i-1]=line.replace(original,replacement)
        changes.append(dict(kind='relabel_analyst_scope_guidance',line=i,original=original,replacement=replacement,
                            refs=sorted({int(v) for v in re.findall(r'\[Ref-(\d+)\]',line)})))
    return '\n'.join(lines),changes
