"""Bounded, source-constrained semantic screening; never a calibrated truth guarantee."""
from __future__ import annotations
import json
import re
import unicodedata
from urllib.parse import urlparse
from .structured_llm import call_structured

def enabled(llm):
    return str(getattr(llm,'model','')) in {'kimi-k2.5','kimi-k2.6'} and urlparse(str(getattr(llm,'base_url',''))).hostname in {'api.moonshot.cn','api.moonshot.ai'}

def parse_result(raw):
    if not raw or str(raw).startswith('❌'):return None
    try:
        match=re.search(r'\{.*\}',raw,re.S)
        value=json.loads(match.group(0)) if match else None
        return value if isinstance(value,dict) else None
    except (ValueError,TypeError):return None

def _numbers(text):
    text=re.sub(r'\[Ref-\d+\]','',unicodedata.normalize('NFKC',text))
    text=re.sub(r'(?<=\d)\s+(?=\d)','',text)
    # Comparison-only OCR normalization; original source text remains immutable.
    text=re.sub(r'(?<=\d)\s*\.\s*(?=\d)','.',text)
    return set(re.findall(r'\d+(?:\.\d+)?',text))

def evidence_catalog(sources,context,refs):
    catalog={}
    # Parse summary markers once. A greedy line-prefix regex on long prose with
    # no marker has quadratic backtracking and must not run for every chunk.
    summary_quotes=[]
    for line in context.splitlines():
        if '原句=' not in line:
            continue
        prefix,encoded=line.split('原句=',1)
        bound_ids=re.findall(r'SRC:[A-Za-z0-9]+',prefix)
        bound_refs={int(n) for n in re.findall(r'Ref-(\d+)',prefix)}
        try:
            text=json.JSONDecoder().raw_decode(encoded)[0]
        except (ValueError,TypeError):
            text=encoded.rsplit(')',1)[0]
        if isinstance(text,str) and len(text)>=8:
            summary_quotes.append((bound_ids,bound_refs,text))
    for doc in sources:
        if doc.get('ref_id') not in refs:continue
        for chunk in doc.get('chunks') or [doc]:
            content=str(chunk.get('content') or '')
            # Audit only text actually present in this generation context, including E2.
            for offset in range(0,len(content),900):
                text=content[max(0,offset-120):offset+900]
                if text not in context:
                    continue
                key=f'Q{len(catalog)+1:04d}'
                catalog[key]={'source_id':chunk.get('source_id'),'ref_id':doc['ref_id'],
                              'title':doc.get('source_label') or doc.get('source'), 'quote':text}
            # Graph summaries supply an exact quoted portion, not the whole original chunk.
            for bound_ids,bound_refs,text in summary_quotes:
                if bound_ids and chunk.get('source_id') not in bound_ids:
                    continue
                if bound_refs and doc['ref_id'] not in bound_refs:
                    continue
                if len(text)>=8 and text in content and not any(c['quote']==text and c['source_id']==chunk.get('source_id') and c['ref_id']==doc['ref_id'] for c in catalog.values()):
                    key=f'Q{len(catalog)+1:04d}'
                    catalog[key]={'source_id':chunk.get('source_id'),'ref_id':doc['ref_id'],
                                  'title':doc.get('source_label') or doc.get('source'), 'quote':text}
    return catalog

ANSWER_PROMPT='''审查储能问答草稿。只用下面编号原文，不使用常识补全OCR缺字或文献没有写出的名称、数值、条件和因果。逐一核查体系、单位、效率指标、比较对象与工艺路线。每个实质错误返回对应答案行A编号、该行中需要调整的连续逐字最小片段original_fragment，以及仅由选定Q原文支持的replacement。程序只替换这个片段，其余原句原样保留；不得为了删掉一个括号的缩写全称而删去整段有据机理和引用。不要对只有措辞差异或已注明OCR不确定的内容过度改写。不把禁止错误想象成答案说过，不把正确同义表述判错（6g:4g=6:4；十组实验时长不等于连续十步）。部分有据的行保留有据事实，删除无据细节。replacement可以为空以删除局部无据修饰，但不可新增无证事实。
先判断是否确有错误，再生成issue；理由承认“此条无误/无实质错误”时不要返回该issue。reason最多100字，不输出反复自问或推理过程。原文“按比例称取”即支持该称量步骤，比例未给出只需另列缺口，不能删掉步骤。may/might/可能不能改为确定的因果或协同机制。
核查一行时阅读该行已引用文献的所有Q片段。同一实验的材料段、表格、步骤段和参数段可以共同支持回答，不能仅因粒径来自材料段、时长来自参数段而删除。仍须核对材料主体、制备路线及样品条件，不能把别的体系或单一样品参数推广。局部修订要放回整行检查：不得留下空括号，不得把前文已有的参数或分句再插入一遍；删除无据括号内容时应把该对括号一并纳入最小片段。
“使用边界/不是原句”等范围说明是本系统的分析约束，不是论文主张。不得把它写成“文献明确规定/不得/禁止”；应保留实际样品条件，并以“本次证据不足以推广为通用配比”说明推断边界。每个真正需要修订的issue必须给出有效quote_ids，没有实质错误的条目直接不列出。
结合用户问题列出最多6项requirements，每项说明哪些Q编号支持（supported）或当前片段不足（gap）。不要因为缺证就编造回答。图中候选观察不等于确认事实；只有其原句能支撑才使用。没有问题时issues为空。JSON：
{"review_complete":true,"requirements":[{"need":"用户信息需求","status":"supported|gap","quote_ids":["Q0001"]}],"issues":[{"fragment_id":"F0001","reason":"实质问题","replacement":"仅有据表述或删除用空字符串","quote_ids":["Q0001"]}]}
answer_fragments提供F编号、所属A行和不可变原文。需要修订时选包含问题的最小F片段，只返回fragment_id，不复述span_id或original_fragment，避免公式转义改变原句。程序从F编号绑定精确原句，不猜测位置。replacement应覆盖所选完整片段并保留其中其余有据内容；无错误不列issue，不输出逐条自问过程。answer_spans是完整回答上下文，answer_fragments是同一内容的定位视图，不是回答又重复了一遍。不得以跨视图重复为理由删除原句；每个问题只选一个现有F片段，不把多个F重新拼接成整行。
'''


def repair_text_issue(issue, selected, original):
    """Reject self-withdrawn edits and structurally destructive local deletions.

    These checks preserve text; they do not certify the original claim as true.
    A literal-match safeguard is bounded to deletions without a scope objection.
    """
    reason = str(issue.get('reason') or '')
    if re.search(r'(?:此条|该条|本条|此处)(?:实际上|实际)?(?:并)?(?:无误|无(?:实质)?错误|无实质问题)|(?:答案|表述|转述)[^。；;\n]{0,10}(?:无误|正确|准确)[。\s]*$', reason[-240:]):
        return 'critic withdrew its own error claim; original preserved'
    fragment = str(issue.get('original_fragment') or '')
    replacement = str(issue.get('replacement') or '').strip()
    if not fragment or fragment not in original:
        return None
    remaining = original.replace(fragment, replacement, 1).strip()
    empty_pairs = r'[（(]\s*[）)]'
    if len(re.findall(empty_pairs, remaining)) > len(re.findall(empty_pairs, original)):
        return 'repair leaves empty parentheses; revise the complete parenthetical instead'
    def repeated_clauses(text):
        text = re.sub(r'\[Ref-\d+\]', '', unicodedata.normalize('NFKC', text))
        clauses = [re.sub(r'\s+', '', part) for part in re.split(r'[，,。；;]', text) if part.strip()]
        # A short linking clause (e.g. 按照预设时间) can separate duplicates.
        return {left for i, left in enumerate(clauses) if len(left) >= 6
                and left in clauses[i+1:i+4]}
    if repeated_clauses(remaining) - repeated_clauses(original):
        return 'repair introduces an adjacent repeated factual clause; original preserved'
    if replacement:
        return None
    if remaining and re.fullmatch(r'(?:[①-⑳]|\d+[.、)])\s*(?:\*\*)?[^：:。]{1,30}?(?:\*\*)?[：:]\s*', remaining):
        return 'local deletion leaves an empty numbered step; revise the whole step instead'
    if re.search(r'[：:]\s*[，,。；;]', remaining) and not re.search(r'[：:]\s*[，,。；;]', original):
        return 'local deletion leaves broken step punctuation; revise the whole clause instead'
    if re.search(r'体系|错配|主体|对象|适用范围|不适用|外推|scope|subject', reason, re.I):
        return None
    from .quantity_grounding import comparison_text
    def literal(text):
        text = re.sub(r'\[Ref-\d+\]', '', text)
        return re.sub(r'[\s*，,。.;；:：、“”\"\'（）()]+', '', comparison_text(text))
    compact = literal(fragment)
    if len(compact) >= 16 and any(compact in literal(q['quote']) for q in selected):
        return 'literal source-supported text cannot be deleted merely for an unspecified detail'
    return None


def cited_line_catalog(original, catalog):
    """Keep quote IDs stable and expose only already-visible, locally cited text."""
    refs = {int(v) for v in re.findall(r'\[Ref-(\d+)\]', original)}
    return {qid: quote for qid, quote in catalog.items() if quote['ref_id'] in refs}


def repair_section_issue(issue, original, catalog):
    """A section-location objection alone cannot remove supported parameters.

    Quantity matches are only a bounded safeguard for this editorial rationale,
    never evidence that a claim's mechanism or scientific scope is correct.
    """
    reason = str(issue.get('reason') or '')
    if not re.search(r'材料段|材料表|实验材料|参数段|步骤段|步骤原文|工序原文|'
                     r'(?:非|不是|不属|不在|未在|未提及).{0,12}(?:步骤|工序)|'
                     r'(?:仅|只).{0,12}(?:材料表|材料段|实验材料|参数段|表格|其他章节)|'
                     r'(?:材料|参数|时长).{0,12}(?:非步骤|不是步骤)', reason):
        return None
    if re.search(r'体系|错配|主体|对象|不适用|外推|矛盾|数值不符|scope|subject', reason, re.I):
        return None
    fragment = str(issue.get('original_fragment') or '')
    if not fragment or fragment not in original:
        return None
    replacement = str(issue.get('replacement') or '').strip()
    from .quantity_grounding import quantities, audit_quantities
    remaining = original.replace(fragment, replacement, 1)
    retained = {(q.value, q.dimension) for q in quantities(remaining)}
    # This guard preserves text, without adding a reference. A source-supported
    # uncited parameter must be checked for citation separately, not erased to
    # satisfy an editorial objection. Catalog text was already visible and
    # cited elsewhere in the answer; no new source is retrieved here.
    line_catalog=cited_line_catalog(original,catalog)
    supported = audit_quantities(original,line_catalog or catalog)
    for check in supported:
        if (check['status'] != 'matched_quantity' and not
                (check['status']=='missing_local_citation' and check.get('uncited_candidate_matches'))):
            continue
        values = quantities(check['quantity'].split('（列表共享单位）')[0])
        if any((q.value, q.dimension) not in retained for q in values):
            return 'section location alone cannot justify deleting a cited source-supported parameter'
    return None


def repair_quantity_issue(fragment,replacement,selected,original):
    """Reject unsupported unit changes and destructive format-only repairs."""
    from .quantity_grounding import comparison_text, audit_quantities
    def comparable(text):
        # Preserve a useful literal-source annotation instead of replacing its
        # entire numeric phrase merely to change a degree glyph.
        text=re.sub(r'[（(]原文(?:识别为|为|写作)[^）)]*[）)]','',text)
        return re.sub(r'[\s"\'“”]','',comparison_text(text))
    if replacement and comparable(fragment)==comparable(replacement):
        return 'format-only repair; original presentation preserved'
    if not replacement:return None
    refs={int(v) for v in re.findall(r'\[Ref-(\d+)\]',original)}
    selected_refs={q['ref_id'] for q in selected}
    inherited=refs & selected_refs
    probe=replacement
    if not re.search(r'\[Ref-\d+\]',probe):
        if refs and not inherited:
            return 'repair leaves an original citation pointing to a different selected source'
        probe+=''.join(f'[Ref-{ref}]' for ref in sorted(inherited or selected_refs))
    catalog={f'Q{i+1:04d}':q for i,q in enumerate(selected)}
    checks=audit_quantities(probe,catalog)
    if any(q['status'] not in {'matched_quantity','qualified_uncertainty'} for q in checks):
        return 'repair quantity/unit/subject lacks selected-source support'
    return None


def review_structure_errors(result, spans, catalog):
    """Validate source bindings without guessing missing Q IDs for the model."""
    if not isinstance(result, dict) or result.get('review_complete') is not True or not isinstance(result.get('issues'), list):
        return ['review_complete=true and an issues array are required']
    errors=[]
    for i, issue in enumerate(result['issues']):
        if not isinstance(issue, dict):
            errors.append(f'issues[{i}] must be an object');continue
        sid=issue.get('span_id')
        fragment=issue.get('original_fragment')
        if not isinstance(sid,str) or sid not in spans or not isinstance(fragment,str) or not fragment or fragment not in spans[sid]:
            errors.append(f'issues[{i}] must identify an existing answer span and exact fragment')
        if not isinstance(issue.get('replacement'),str):
            errors.append(f'issues[{i}].replacement must be a string')
        ids=issue.get('quote_ids')
        if not isinstance(ids,list) or not ids or any(not isinstance(q,str) or q not in catalog for q in ids):
            errors.append(f'issues[{i}].quote_ids must contain existing Q IDs')
    return errors


def answer_fragments(spans):
    fragments={}
    for sid,line in spans.items():
        # Keep mathematical lines atomic: splitting TeX and stripping their
        # whitespace would change the literal text selected by the critic.
        mathematical=bool(re.search(r'\$|\\[\[(]',line))
        candidates=[line] if mathematical else [part.strip() for part in re.findall(r'[^。；;]+[。；;]?',line) if part.strip()]
        # Whole-line context remains in answer_spans; the action catalogue lists
        # each literal fragment once, never the same text at two granularities.
        for text in dict.fromkeys(candidates or [line]):
            fragments[f'F{len(fragments)+1:04d}']={'span_id':sid,'text':text}
    return fragments


def discard_explicitly_cancelled_issues(result, fragments):
    """Discard only valid-ID no-action entries whose critic explicitly withdrew them.

    Real edits/deletions, unknown IDs, contradictory instructions and missing evidence
    on substantive issues remain invalid and must still fail the existing gate.
    """
    if not isinstance(result,dict) or not isinstance(result.get('issues'),list):return result,[]
    kept=[];cancelled=[]
    for issue in result['issues']:
        if not isinstance(issue,dict):kept.append(issue);continue
        bound=fragments.get(issue.get('fragment_id')) if isinstance(issue.get('fragment_id'),str) else None
        reason=str(issue.get('reason',''))
        # Q IDs are evidence labels, not other pending answer issues.
        other_ids={value for value in re.findall(r'\b(?:F|A)\d{3,}\b',reason,re.I)
                   if value.upper()!=str(issue.get('fragment_id','')).upper()}
        explicit=bool(re.search(
            r'(?:此条|该条|本条|此处)(?:实际上|实际)?'
            r'(?:无误|无(?:实质)?错误|无实质问题|有据)|'
            r'(?:实际|原句|原文)(?:上)?(?:有据|无误)|'
            r'原文差异[^。；\n]{0,12}(?:非|不是)(?:答案)?错误',reason
        ))
        action_text=re.sub(
            r'(?:无需|不需|无须|不必|不用)(?:删除|修正|修订|替换|改写|修改)|'
            r'非(?:答案)?错误|不(?:是|为)(?:答案)?错误',
            '',reason,
        )
        contradictory=bool(re.search(
            r'(?:应|须|需|必须|请|仍然?)(?:删除|修正|修订|替换|改写|修改)|'
            r'(?:删除|修正|修订|替换|改为|改写)',action_text
        ))
        no_action=issue.get('replacement') in (None,'') and issue.get('quote_ids') in (None,[])
        compatible=bound and ('span_id' not in issue or issue['span_id']==bound['span_id']) and ('original_fragment' not in issue or issue['original_fragment']==bound['text'])
        if explicit and not contradictory and not other_ids and no_action and compatible:cancelled.append(issue)
        else:kept.append(issue)
    return dict(result,issues=kept),cancelled


def bind_review_fragments(result, fragments):
    """Resolve model-selected IDs exactly; conflicts are diagnostic, not fatal."""
    if not isinstance(result,dict) or not isinstance(result.get('issues'),list):return result,[]
    normalized=dict(result,issues=[])
    errors=[]
    diagnostics=[]
    for i,raw in enumerate(result['issues']):
        if not isinstance(raw,dict):normalized['issues'].append(raw);continue
        issue=dict(raw)
        if 'fragment_id' in issue:
            fid=issue['fragment_id']
            bound=fragments.get(fid) if isinstance(fid,str) else None
            if bound is None:
                errors.append(f'issues[{i}].fragment_id must identify an existing F fragment')
            else:
                if ('span_id' in issue and issue['span_id']!=bound['span_id']) or ('original_fragment' in issue and issue['original_fragment']!=bound['text']):
                    diagnostics.append({
                        'issue_index': i,
                        'fragment_id': fid,
                        'conflicting_span_id': issue.get('span_id'),
                        'conflicting_original_fragment': issue.get('original_fragment'),
                        'resolved_span_id': bound['span_id'],
                    })
                issue.update(span_id=bound['span_id'],original_fragment=bound['text'])
        normalized['issues'].append(issue)
    if diagnostics:
        normalized['binding_diagnostics']=diagnostics
    return normalized,errors


def audit_answer(llm,question,answer,sources,context,validation_issues=None):
    if not enabled(llm):return answer,{'status':'not_enabled','semantic_support_verified':False}
    from .answer_grounding import normalize_citations
    answer = normalize_citations(answer)
    lines=answer.splitlines()
    spans={f'A{i+1:04d}':line for i,line in enumerate(lines) if line.strip()}
    refs={int(v) for v in re.findall(r'\[Ref-(\d+)\]',answer)}
    catalog=evidence_catalog(sources,context,refs)
    if not catalog:return answer,{'status':'no_auditable_context','semantic_support_verified':False}
    fragments=answer_fragments(spans)
    payload={'question':question,'answer_spans':spans,'answer_fragments':fragments,'source_quotes':catalog}
    if validation_issues:
        payload['machine_checks_to_verify']=list(validation_issues)
    from .mechanism_boundaries import guidance
    prompt=ANSWER_PROMPT+guidance(question)+'\n'+json.dumps(payload,ensure_ascii=False)
    if validation_issues:
        prompt+='\n本次还须逐条处理machine_checks_to_verify。missing_local_citation表示该行漏了就近引用，不等于其内容错误：先从source_quotes核对完整工序、数值、主体和条件；确有支持时以该行原有连续片段为original_fragment，replacement原样保留该片段并在本行补上对应Q的Ref。禁止从别行复制或凭数字相同猜Ref；没有足够原句支持则保留缺口，不删掉有据核心参数来规避检查。其他数值/单位错误须对照原句修订，不能只添加引用。'
    raw=call_structured(llm,prompt,max_tokens=6000)
    result,binding_errors=bind_review_fragments(parse_result(raw),fragments)
    result,cancelled=discard_explicitly_cancelled_issues(result,fragments)
    errors=binding_errors+review_structure_errors(result,spans,catalog)
    structure_attempts=[{'errors':errors,'raw_response':str(raw),'cancelled_noop_items':cancelled}]
    if errors and not str(raw).startswith('❌'):
        raw=call_structured(llm,prompt+'\n上次来源审查结构不完整，不能视为筛查通过。重新独立对照相同F/A/Q原句输出完整JSON；问题片段仅选现有fragment_id，每项实际修订都须有有效quote_ids。无实质错误时issues为空。不要猜来源或复述公式，不要返回已承认无误的issue。\n'
                            +json.dumps({'structure_errors':errors},ensure_ascii=False),max_tokens=6000)
        result,binding_errors=bind_review_fragments(parse_result(raw),fragments)
        result,cancelled=discard_explicitly_cancelled_issues(result,fragments)
        errors=binding_errors+review_structure_errors(result,spans,catalog)
        structure_attempts.append({'errors':errors,'raw_response':str(raw),'cancelled_noop_items':cancelled})
    metadata={'status':'review_failed','semantic_support_verified':False,'input_chars':len(prompt),
              'review_structure_valid':not errors,'review_structure_attempts':structure_attempts,
              'method':'two-stage model-assisted screening with original-source IDs and deterministic repair constraints'}
    if not result:
        metadata['failure_reason']=str(raw)[:160] if str(raw).startswith('❌') else 'invalid JSON'
    if errors:
        metadata['failure_reason']='invalid source-screen structure: '+'; '.join(errors[:4])
        return answer,metadata
    proposals={}
    blocked={}
    for index, issue in enumerate(result['issues'][:12]):
        if not isinstance(issue,dict):continue
        selected=[catalog[q] for q in issue.get('quote_ids',[]) if q in catalog]
        if issue.get('span_id') in spans and selected:
            original=spans[issue['span_id']]
            rejection=(repair_section_issue(issue,original,catalog) or
                       repair_text_issue(issue,selected,original))
            if rejection:
                blocked[index]=rejection
                continue
            # The second screen compares source and text without being led by
            # the first critic's speculative rationale.
            proposals[f'I{index+1:04d}']={'answer_line':spans[issue['span_id']],
                'proposal':{key:value for key,value in issue.items() if key!='reason'},'original_quotes':selected,
                'cited_line_quotes':cited_line_catalog(original,catalog)}
    confirmed=set()
    confirmation_status='not_needed'
    if proposals:
        confirmation=parse_result(call_structured(llm,
            '复核修订建议，只使用各条绑定的原文。只有原答案确有实质无据/矛盾内容，且修改能准确解决该问题而保留其余有据事实，才允许修订。'
            '正确的同义概括不能删去。原文按比例称取但没给比例数值时，保留称量步骤并说明配比缺口；不得删空编号步骤。无据缩写全称只删括号，不删整句。'
            '同时阅读cited_line_quotes中该行已引用文献的全部原文，不能只看建议选中的original_quotes。相同实验的材料、步骤、时间梯度可跨段共同支持；核对主体、路线和样品条件后保留有据参数，不因其不在步骤段而删除。把替换放回整行，若丢失有据事实、留下空括号或重复前文分句则不批准。'
            '把分析使用边界误归给论文时，允许改回“本次证据不足以推广”的适用性说明，这不是新增论文声明；须保留原有样品条件和有据参数。'
            '不要照抄首轮审查意见，逐条比对实际原文。仅输出JSON {"review_complete":true,"verified_issue_ids":["I0001"]}。\n'
            +json.dumps(proposals,ensure_ascii=False),max_tokens=1800))
        if (confirmation and confirmation.get('review_complete') is True
                and isinstance(confirmation.get('verified_issue_ids'),list)
                and all(isinstance(q,str) and q in proposals for q in confirmation['verified_issue_ids'])):
            confirmed=set(confirmation['verified_issue_ids'])
            confirmation_status='model_screened'
        else:confirmation_status='review_failed'
    changes=[]
    unresolved=[]
    for issue_index, issue in enumerate(result['issues'][:12]):
        if not isinstance(issue,dict):continue
        sid=issue.get('span_id')
        if sid not in spans:continue
        if issue_index in blocked:
            unresolved.append({'span_id':sid,'reason':blocked[issue_index]})
            continue
        if f'I{issue_index+1:04d}' not in confirmed:
            unresolved.append({'span_id':sid,'reason':'repair not confirmed against its original quotes; original preserved'})
            continue
        original=spans[sid]
        fragment=str(issue.get('original_fragment') or '')
        if not fragment or fragment not in original:
            unresolved.append({'span_id':sid,'reason':'review repair did not identify an exact original fragment'})
            continue
        replacement=str(issue.get('replacement') or '').strip()
        uncertainty_terms=('存疑','单位不清','单位未明','OCR','识别不清','不确定','未确认','待核实','待核对','单位识别异常')
        if (any(term in fragment for term in uncertainty_terms) and
            not any(term in replacement for term in uncertainty_terms)):
            unresolved.append({'span_id':sid,'reason':'repair removes an existing uncertainty qualification; original preserved'})
            continue
        if (any(term in original for term in ('温度','干燥箱')) and '%' in replacement and
            not any(term in replacement for term in uncertainty_terms)):
            unresolved.append({'span_id':sid,'reason':'repair treats an OCR percentage as an unqualified temperature; original preserved'})
            continue
        selected=[catalog[q] for q in issue.get('quote_ids',[]) if q in catalog]
        quote='\n'.join(q['quote'] for q in selected)
        valid=bool(selected and _numbers(replacement).issubset(_numbers(quote)))
        replacement_refs={int(v) for v in re.findall(r'\[Ref-(\d+)\]',replacement)}
        valid=valid and replacement_refs.issubset({q['ref_id'] for q in selected})
        if not valid:
            all_quoted_text='\n'.join(q['quote'] for q in catalog.values())
            if selected and len(fragment)<=80 and not _numbers(fragment).issubset(_numbers(all_quoted_text)):
                replacement='本次提供的原文片段未能支持该条具体数值。'
            else:
                unresolved.append({'span_id':sid,'reason':'repair lacks valid source/number/ref constraints; original preserved'})
                continue
        repair_issue=repair_quantity_issue(fragment,replacement,selected,original)
        if repair_issue:
            unresolved.append({'span_id':sid,'reason':repair_issue})
            continue
        index=int(sid[1:])-1
        if fragment not in lines[index]:
            unresolved.append({'span_id':sid,'reason':'overlapping repair; original fragment no longer present'})
            continue
        # Earlier accepted edits can make a later proposal destructive even if
        # it was safe against the immutable original line.
        rejection=(repair_section_issue(issue,lines[index],catalog) or
                   repair_text_issue(dict(issue,replacement=replacement),selected,lines[index]))
        if rejection:
            unresolved.append({'span_id':sid,'reason':rejection})
            continue
        lines[index]=lines[index].replace(fragment,replacement,1)
        changes.append({'span_id':sid,'original':original,'original_fragment':fragment,'replacement':replacement,
                        'reason':str(issue.get('reason') or ''),'source_ids':[q['source_id'] for q in selected],
                        'repair_constraints_passed':valid})
    requirements=[]
    for item in result.get('requirements',[])[:6]:
        if not isinstance(item,dict):continue
        matched=[catalog[q] for q in item.get('quote_ids',[]) if q in catalog]
        requirements.append({'need':str(item.get('need') or ''),'status':'supported_candidate' if item.get('status')=='supported' and matched else 'gap',
                             'source_ids':list(dict.fromkeys(q['source_id'] for q in matched)),
                             'refs':sorted({q['ref_id'] for q in matched})})
    metadata.update(status='model_screened',changes=changes,requirements_evidence=requirements,
                    repair_confirmation_status=confirmation_status,
                    repair_proposals=[{k:v for k,v in issue.items() if k in {'span_id','original_fragment','replacement','reason','quote_ids'}}
                                      for issue in result['issues'][:12] if isinstance(issue,dict)],
                    unresolved_repairs=unresolved,
                    caveat='模型核验及编号/数值闸门不能替代独立原文语义复核')
    return '\n'.join(lines),metadata

GRAPH_PROMPT='''核查候选证据图主张是否被其绑定原句直接支持。不能借常识填补OCR缺字、具体名称、数值、单位、条件或因果；不能把另一材料/电池体系的结果绑定过来。节点名称与主张、关系端点/类型也须被原句支持，可接受同义词。节点观察必须描述entity自身的作用、性质或条件；原句同时提到两个实体，不代表两个实体都具有其中一个的性质。如果观察写实体A的性能提升却挂在实体B上，应拒收；比较观察必须明确本节点自身的角色，不能把比较对象的优势写成该节点的优势。只是提及共现时可支持ASSOCIATED_WITH，不能推出因果/改进/替代。只输出JSON {"review_complete":true,"accepted_ids":["N0001"],"rejected":[{"claim_id":"N0002","reason":"缺少原句支撑"}]}。没有支撑的主张拒收，仍保留candidate状态，不升级确认。
'''

def screen_graph(llm,claims,question=''):
    if not enabled(llm):return set(claims),{'status':'not_enabled'}
    from .mechanism_boundaries import guidance,claim_issues
    blocked={key:claim_issues(question,value.get('claim',''),[(value.get('provenance') or {}).get('quote','')])
             for key,value in claims.items()}
    blocked={key:reasons for key,reasons in blocked.items() if reasons}
    prompt=GRAPH_PROMPT+guidance(question)+'\n'+json.dumps(claims,ensure_ascii=False)
    result=parse_result(call_structured(llm,prompt,max_tokens=2200))
    if not result or result.get('review_complete') is not True or not isinstance(result.get('accepted_ids'),list):
        return set(),{'status':'review_failed','input_chars':len(prompt)}
    accepted=(set(result['accepted_ids']) & set(claims))-set(blocked)
    return accepted,{'status':'model_screened','input_chars':len(prompt),'accepted':len(accepted),
                     'rejected':result.get('rejected',[]),'boundary_rejected':blocked,'semantic_support_verified':False}
