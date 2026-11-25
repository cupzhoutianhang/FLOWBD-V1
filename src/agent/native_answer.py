"""Complete native JSON generation with conservative source checks, not a truth guarantee."""
from __future__ import annotations
from decimal import Decimal, InvalidOperation
import os
import json
import re
import unicodedata
from .answer_grounding import check_citations, normalize_citations
from .grounding_audit import _numbers, evidence_catalog
from .structured_llm import call_structured
from .quantity_grounding import audit_quantities

class NativeAnswerError(RuntimeError):
    def __init__(self,message,metadata):
        super().__init__(message)
        self.generation_metadata=metadata

JSON_RULE = '''只返回完整JSON对象 {"answer":"最终中文答案"}。answer包含用户实际需要的完整回答及就近[Ref-n]引用，不输出思考或来源列表。聚焦3–6项有据的核心方法/步骤/机理，通常600–1000汉字，详细步骤或对照表可适当增加。未要求性能数值时，不额外堆砌各论文的全部效率、孔隙率和形貌参数；解释改善机理即可。不能把可选数值的篇幅挤占核心需求。
先逐项检查用户实际需求：有来源支持的步骤、条件、路线与机理必须进入正文，缺证项明确写缺口。不要为了减少数值而删掉必要工艺信息，也不要额外展开无关的外体系数值、对照方法和性能参数。
JSON可同时返回coverage数组，每项为{"need":"需求","status":"answered或gap","answer_quote":"正文中逐字对应片段","ref_ids":[1]}。coverage只作自报覆盖诊断，不替代原文验证；不要为填满coverage补造事实。
coverage仅放在顶层JSON字段，不把诊断数组或字段名写进answer正文。
含数值的编号步骤、列表项、表格行、注意事项与缺口说明优先在本行给出支持的[Ref-n]。同一连续段落只有一个明确引用时可覆盖该段列表；不能跨空行/标题沿用，混合多个来源时不能猜。单位存疑说明也要引用。
按来源自己的体系和条件组织结论；同种添加剂在酸性、近中性或全铁中的值不得移植到另一体系，后文补充不同体系不能替代当前主张的就近限定。
原句谓词或句首截断时，不能自行补成肯定机制；保留能确认的事实并指出缺口。抑制析氢不能写成促进H+还原来抑制产氢。文献may/might的因果保留可能性；纯HCl析氢模型、Bi沉积实验、全铁与铁铬等条件分别说明，不当通用阈值或通用策略。降解与再生、充电与放电、储热与放热分开；regeneration/recomposition的恢复氧化步骤不能写成降解路线。
传统铁铬电池负极进行Cr³⁺/Cr²⁺氧化还原，不以Fe金属沉积为负极过程。镉与铁共沉积、Mg/Ca促进Fe沉积等结果只能在其铁沉积型外体系范围讨论，不得列成传统铁铬负极已验证策略；来源不足时省略外推并说明缺口。
OCR温度写作百分号/千分号时，明确给出原文识别和单位存疑；同篇其他工序的正常℃不证明该工序的识别值。带单位数值须来自实际证据，不可按常见值扩大或缩小原文数值；可选不明数值可省略，但有据的步骤、配比、时间和机制不能省去。
'''

STRICT_NUMERIC_RULE = (
    '结论、小结、判别句和对比表格中的每个数值都必须在同一句或同一行给出支持的[Ref-n]；'
    '语料没有写出的阈值（例如“相变温度偏移<7%”“通常<10%”）不得写入，'
    '只能写“未设定统一量化阈值”或省略该数值。'
    '质量比、摩尔比等配比不得反算为百分数（7:1不得写成87.5%）；只能保留原文给出的数值形式。'
    '对比表的每个数据列必须在表头注明该列来源[Ref-n]，没有来源的列删除数值。'
)

BASELINE_JSON_RULE = '只返回完整JSON对象 {"answer":"最终中文答案"}。answer包含用户实际需要的完整回答及就近[Ref-n]引用，不输出思考或来源列表。聚焦3–6项有据的核心方法/步骤/机理，通常600–1000汉字，详细步骤或对照表可适当增加。未要求性能数值时，不额外堆砌各论文的全部效率、孔隙率和形貌参数；解释改善机理即可。不能把可选数值的篇幅挤占核心需求。\n原句谓词或句首截断时，不能自行补成肯定机制；保留能确认的事实并指出缺口。抑制析氢不能写成促进H+还原来抑制产氢。文献may/might的因果保留可能性；纯HCl析氢模型、Bi沉积实验、全铁与铁铬等条件分别说明，不当通用阈值或通用策略。降解与再生、充电与放电、储热与放热分开；regeneration/recomposition的恢复氧化步骤不能写成降解路线。\nOCR温度写作百分号/千分号时，明确给出原文识别和单位存疑；同篇其他工序的正常℃不证明该工序的识别值。带单位数值须来自实际证据，不可按常见值扩大或缩小原文数值；可选不明数值可省略，但有据的步骤、配比、时间和机制不能省去。\n'


def strict_grounding_enabled():
    """Experimental validation must be explicitly enabled for each process."""
    return os.environ.get("FLOWBD_STRICT_GROUNDING", "").strip().lower() in {"1", "true", "yes", "on"}


def split_embedded_coverage(answer):
    """Relocate only a trailing, schema-valid diagnostic array, never factual prose."""
    for match in re.finditer(r'(?m)^[ \t]*\[\s*\{',answer):
        try:items=json.loads(answer[match.start():])
        except (ValueError,TypeError):continue
        if not isinstance(items,list) or not 1<=len(items)<=8:continue
        if not all(isinstance(item,dict) and set(item)=={'need','status','answer_quote','ref_ids'}
                   and isinstance(item['need'],str) and item['status'] in {'answered','gap'}
                   and isinstance(item['answer_quote'],str) and isinstance(item['ref_ids'],list)
                   and all(isinstance(ref,int) for ref in item['ref_ids']) for item in items):continue
        prefix=answer[:match.start()].rstrip()
        prefix=re.sub(r'\n(?:\*\*)?(?:需求覆盖(?:记录|诊断)?|coverage)(?:\*\*)?[：:]?\s*$','',prefix,flags=re.I).rstrip()
        if prefix:return prefix,items
    return answer,None


def scalar(value):
    try:
        return str(abs(Decimal(value)).normalize())
    except InvalidOperation:
        return value


MEASURE = re.compile(r'(?<![A-Za-z0-9_.])[-+−]?\d+(?:\.\d+)?\s*(?:°\s*C|℃|kJ|MJ|mAh|Wh|eV|mV|kPa|MPa|mA|mL|mm|cm|nm|μm|µm|mg|kg|mol|mM|bar|atm|min|V|A|J|M|g|L|h|s|%|‰)(?![A-Za-z])')


def plain(text):
    text=unicodedata.normalize('NFKC',text)
    text=re.sub(r'\^\s*\\circ\s*C','℃',text)
    text=re.sub(r'\\[A-Za-z]+',' ',text)
    return text.translate(str.maketrans('','', '{}$'))

def uncertainty_notes(catalog):
    notes=[]
    for item in catalog.values():
        quote=item['quote']
        for match in re.finditer(r'(?P<value>\d[\d\s.]*)[\s\\{}^A-Za-z]{0,35}[%‰]',quote):
            before=plain(quote[max(0,match.start()-65):match.start()])
            after=plain(quote[match.end():match.end()+35])
            thermal_before=bool(re.search(r'(?:温度|加热|干燥|temperature)[^。\n]{0,25}$',before,re.I))
            metric_before=bool(re.search(r'效率|保持率|含量|分数|湿度|efficiency|retention|humidity',before[-35:],re.I))
            dry_after='干燥箱' in after[:15]
            if (thermal_before and not metric_before) or dry_after:
                values=_numbers(match.group('value'))
                if not values:
                    continue
                notes.append({'ref_id':item['ref_id'],'source_id':item['source_id'],
                    'value':next(iter(values)), 'quote':quote[max(0,match.start()-45):match.end()+45],
                    'note':'本工序温度单位识别为百分号/千分号，单位存疑，不可肯定改写为℃。'})
    return list({(n['source_id'],n['quote']):n for n in notes}.values())[:16]


def source_uncertainty_notes(catalog,sources):
    """One policy for initial generation and final post-audit validation."""
    from .pdf_supplements import resolve_ocr_notes
    return resolve_ocr_notes(uncertainty_notes(catalog),sources)

def draft_issues(answer,sources,catalog,notes,question='',diagnostics=None,strict_validation=None):
    issues=[]
    citation=check_citations(answer,sources)
    if not citation['citation_mapping_valid']:
        issues.append('引用编号无效或格式不完整：'+str(citation['invalid_refs']+citation['malformed_markers']))
    strict = strict_grounding_enabled() if strict_validation is None else strict_validation
    try:
        quantity_checks=audit_quantities(answer,catalog)
    except Exception as exc:
        if strict:
            raise
        # Optional diagnostics must not change the baseline acceptance path.
        quantity_checks=[{'status':'diagnostic_failed','error_type':type(exc).__name__,
                          'semantic_support_verified':False}]
    if diagnostics is not None:
        diagnostics.extend(quantity_checks)
    if strict:
        from .source_guidance import scope_attribution_issues
        issues.extend(scope_attribution_issues(answer,sources,catalog))
        from .mechanism_boundaries import answer_boundary_issues
        issues.extend(answer_boundary_issues(question,answer,catalog))
        from .claim_sections import her_direction_issues
        issues.extend(her_direction_issues(answer))
        for item in quantity_checks:
            if item['status'] not in {'matched_quantity','qualified_uncertainty'}:
                issues.append(f"{item['claim_id']} 数值/单位/主体引用检查未通过({item['status']})：{item['quantity']}")
    else:
        by_ref={}
        for quote in catalog.values():
            raw=re.sub(r'\[\d+(?:\s*[,，–-]\s*\d+)*\]','',quote['quote'])
            by_ref.setdefault(quote['ref_id'],set()).update(scalar(n) for n in _numbers(raw))
        all_numbers=set().union(*by_ref.values()) if by_ref else set()
        for line in answer.splitlines():
            refs={int(n) for n in re.findall(r'\[Ref-(\d+)\]',line)}
            available=set().union(*(by_ref.get(ref,set()) for ref in refs)) if refs else all_numbers
            for match in MEASURE.finditer(plain(line)):
                value=re.search(r'\d+(?:\.\d+)?',match.group()).group()
                if scalar(value) not in available:
                    issues.append('带单位数值未在本行所引实际证据中出现：'+match.group())
    # An explicit Celsius value is not justified by an OCR-only temperature.
    from .quantity_grounding import comparison_text
    def compact(text):
        return re.sub(r'[^A-Za-z0-9\u3400-\u9fff°%‰.]','',comparison_text(text))
    connector=r'(?:为|约|约为|达到|至|到|设定为|控制为|保持为|在|于)'
    def context_matches(line,value,left,right,allow_resolved_summary=False):
        # Connectors may be inserted by prose, but both source neighbors must
        # remain on this line around the exact reading.
        left=compact(left or '')
        right=compact(right or '')
        if not left or not right:
            return False
        citation_free=re.sub(r'\[Ref-\d+\]','',line)
        candidates=[citation_free]
        # A resolved PDF reading may carry a short, explicit source-check
        # annotation before the procedure context resumes. Keep this narrow:
        # the annotation must be parenthesized, bounded, and say "原PDF核对".
        annotation=re.search(
            re.escape(str(value))+r'\s*(?:°C|℃)\s*'
            r'([（(][^（）()\n]{1,32}[）)])',citation_free,re.I)
        if annotation and '原PDF核对' in annotation.group(1):
            candidates.append(citation_free[:annotation.start(1)]+
                              citation_free[annotation.end(1):])
        if allow_resolved_summary:
            # The same resolved procedure may be summarized with the bounded
            # phrase "作为后续制备..."; do not generalize this to arbitrary
            # prose insertion.
            candidates.append(citation_free.replace('作为后续','作为'))
        for candidate in candidates:
            literal=compact(candidate)
            pattern=(re.escape(left)+connector+r'{0,2}'+re.escape(str(value))+
                     r'\s*(?:°C|℃)'+connector+r'{0,2}'+re.escape(right))
            if re.search(pattern,literal):
                return True
        if allow_resolved_summary:
            # A markdown summary row can omit the full source sentence. Accept
            # only a row whose label carries both the procedure's temperature
            # and drying anchors; an unrelated "熔点温度" row must still fail.
            summary=re.search(
                r'\|\s*([^|\n]*?(?:温度|干燥)[^|\n]*?)\s*\|\s*'+
                re.escape(str(value))+r'\s*(?:°C|℃)\s*\|',
                citation_free,re.I)
            if summary:
                summary_label=compact(summary.group(1))
                procedure_context=compact(left+right)
                if ('温度' in summary_label and '干燥' in summary_label and
                        '温度' in procedure_context and '干燥' in procedure_context):
                    return True
        return False
    def unresolved_context(note,value):
        original=compact(note.get('quote') or '')
        marker=re.search(re.escape(value)+r'[%‰]',original)
        if not marker:
            return None
        left=original[max(0,marker.start()-6):marker.start()]
        right=original[marker.end():marker.end()+6]
        return (left,right) if len(left)>=4 and len(right)>=4 else None
    for note in notes:
        value=str(note['value'])
        known=re.compile(re.escape(value)+r'\s*(?:°\s*C|℃)')
        resolved=note.get('resolved_by_pdf') or []
        # The same OCR Ref can contain several procedures. A resolved context
        # from a sibling note for the same old Ref is valid for this line too.
        resolved_items=[item for sibling in notes
                        if str(sibling.get('value'))==value and
                        int(sibling.get('ref_id'))==int(note['ref_id'])
                        for item in (sibling.get('resolved_by_pdf') or [])]
        resolved_refs={int(r['ref_id']) for r in resolved_items if r.get('ref_id') is not None}
        allowed_refs={int(note['ref_id']),*resolved_refs}
        original_context=unresolved_context(note,value)
        for line in answer.splitlines():
            line_refs={int(n) for n in re.findall(r'\[Ref-(\d+)\]',line)}
            # A different procedure citing another Ref cannot inherit this
            # OCR warning. Only the OCR source or its PDF resolution is in scope.
            if not line_refs & allowed_refs:
                continue
            if line_refs & resolved_refs and any(
                    context_matches(line,value,item.get('matched_left'),item.get('matched_right'),
                                    allow_resolved_summary=True)
                    for item in resolved_items):
                continue
            if not known.search(plain(line)):
                continue
            if not resolved and original_context and not context_matches(
                    line,value,original_context[0],original_context[1]):
                continue  # Same Ref, but a different procedure in the paper.
            if not any(t in line for t in ('存疑','不确定','未确认','未明确','OCR','识别','推断')):
                issues.append('温度'+value+'的℃单位未经原文确认，需保留OCR存疑说明。')
    if re.search(r'铁.?铬|iron.?chromium|ICRFB',question,re.I):
        if strict:
            from .claim_sections import iron_deposition_issues
            issues.extend(iron_deposition_issues(answer))
        # Classic ICRFB negolytes reduce chromium ions, not metallic iron.
        # Fe-plating results remain useful background only when explicitly scoped.
        for block in ([] if strict else re.split(r'\n\s*\n',answer)):
            deposition=re.search(r'(?:Fe|铁|iron)\s*(?:共|电)?沉积|(?:Fe|iron)\s*(?:plating|deposition)',block,re.I)
            scoped=re.search(r'全铁|all[- ]iron|AIRFB|铁沉积型|非铁铬|未在铁铬|尚未.*验证|不可.*外推|仅作参考',block,re.I)
            if deposition and not scoped:
                issues.append('Fe金属沉积/与Fe共沉积的证据未限定为全铁等外体系，不可当传统Cr负极铁铬方案；需就近标注未验证或省略该外推。')
    return list(dict.fromkeys(issues))[:12]

def generate_native_answer(llm,prompt,system_prompt,sources,context,question='',strict_validation=None,requirements=None):
    strict = strict_grounding_enabled() if strict_validation is None else strict_validation
    refs={int(s['ref_id']) for s in sources if s.get('ref_id')}
    catalog=evidence_catalog(sources,context,refs)
    notes=source_uncertainty_notes(catalog,sources)
    effective=system_prompt+'\n'+(JSON_RULE if strict else BASELINE_JSON_RULE)+'\n'+prompt
    if strict:
        from .mechanism_boundaries import guidance
        if guidance(question):effective+='\n【材料与机理证据边界】\n'+guidance(question)
        if re.search(r'半反应|半电池反应',question) and not re.search(r'电势|电位|电压|能斯特|温度|浓度',question):
            effective+='\n本题只需所问半反应方程式、电子数及充放电方向，确保原子/电荷配平并逐式引用；不要附加未要求的标准电势、总电压、温度/浓度对比等可选参数。'
        if any(s.get('type')=='pdf_supplement' for s in sources):
            effective+='\n本次有原PDF核对补充：其明确的对应工序读数直接引用补充Ref，不再把已核对的温度称未知或存疑。若回顾旧OCR错误值，必须同时引用旧OCR Ref；可直接写原PDF读数，避免重复旧错误字形。不能用其他工序的正常读数替代当前工序。'
            effective+='\n“使用边界/不是原句”的范围说明是本系统的分析约束，不是论文原话。不得写成“文献明确规定/禁止/不得”；样品条件须就近保留，适用性结论写成“本次证据不足以推广为通用配比”，不替作者增加声明。'
        effective+='\n只在用户要求时展开方法对比或额外性能表。策略问答先给2–4项本体系直接有据的策略及机理，未要求效果数据时省略效率、衰减率、循环圈数和能垒对比等可选数值；必要剂量与工艺条件保留。外体系只在确有必要时以一小段背景说明，不列入本体系策略或写成“可配套”，不展开其性能数值。区分抑制反应发生与收集产物/缓解后果；may/might只写“可能”，不写已证明的协同因果。'
        effective+='\n'+STRICT_NUMERIC_RULE
        if re.search(r'工艺步骤|制备步骤|操作流程|具体.*步骤',question) and not re.search(r'对比|比较|区别|优缺点',question):
            effective+='\n本题只回答该方法的工序、必要参数与证据缺口；不要附加其他方法对比、其他材料配方或与步骤无关的性能汇总。'
            effective+='不要输出需求自检表。缺口仅说明缺少什么，不在缺口中重复正文已引用的温度、时长等数值；核心工艺数值仍须完整保留并就近引用。'
        if requirements:
            effective+='\n【待覆盖需求，不是事实证据；done仅表示候选来源存在】\n'+json.dumps(requirements,ensure_ascii=False)
    if notes:
        effective+='\n【实际证据单位存疑提醒】\n'+json.dumps(notes,ensure_ascii=False)
        if any(n.get('resolved_by_pdf') for n in notes):
            effective+='\n【同工序原PDF核对优先】带resolved_by_pdf的旧OCR读数已被本次原页证据解决：正文写“原PDF核对为相应℃值”并引用该补充Ref，不继续写“不可确认为℃/真实单位未明确”。仅对应所列工序，未解决的其他OCR提醒仍有效。'
    attempts=[]
    source_screening=None
    coverage=[]
    def metadata(complete=False):
        return {'method':'native_instant_json','completion_verified':complete,
            'semantic_support_verified':False,'prompt_chars':len(effective),'system_chars':0,
            'evidence_uncertainties':notes,'attempts':attempts,'source_screening':source_screening,
            'strict_validation_enabled':strict,
            'requirement_coverage':coverage,
            'planned_requirements':requirements or [],
            'validation_policy':'quantity_units_bounded_citation_scope_signals_v3' if strict else 'baseline_scalar_citation_ocr_scope_v1',
            'note':'诊断不构成完整科学语义确认；是否执行严格量值检查以strict_validation_enabled为准；全部实际输入在user消息中。'}
    for round_no,budget in enumerate((6000,10000),1):
        before=len(getattr(llm,'structured_calls',[]))
        raw=call_structured(llm,effective,max_tokens=budget,thinking=False)
        events=getattr(llm,'structured_calls',[])[before:]
        finish=events[-1].get('finish_reason') if events else None
        if str(raw).startswith('❌') and '长度上限' not in str(raw):
            attempts.append({'round':round_no,'max_tokens':budget,'prompt_chars':len(effective),
                             'finish_reason':finish,'issues':[str(raw)[:160]],'api_attempts':len(events)})
            raise NativeAnswerError('原生答案接口失败：'+str(raw)[:160],metadata())
        issues=[]
        quantity_checks=[]
        formatting_changes=[]
        try:
            data=json.loads(raw)
            answer=data.get('answer') if isinstance(data,dict) else None
            if not isinstance(answer,str) or not answer.strip() or answer.startswith('❌'):
                raise ValueError('missing final answer')
            answer=normalize_citations(answer.strip())
            if strict:
                answer,embedded_coverage=split_embedded_coverage(answer)
                if embedded_coverage and not data.get('coverage'):data=dict(data,coverage=embedded_coverage)
                from .grounded_formatting import format_grounded_notes
                answer,formatting_changes=format_grounded_notes(answer,catalog,notes,sources=sources)
                if embedded_coverage:formatting_changes.insert(0,{'kind':'relocated_schema_valid_coverage_array','items':len(embedded_coverage),'raw_response_preserved':True})
            coverage=[]
            coverage_items=data.get('coverage')
            for item in (coverage_items if isinstance(coverage_items,list) else [])[:8]:
                if not isinstance(item,dict):continue
                excerpt=str(item.get('answer_quote') or '')
                selected=item.get('ref_ids') or []
                coverage.append({'need':str(item.get('need') or ''),'status':item.get('status'),
                    'answer_quote':excerpt,'answer_span_present':bool(excerpt and excerpt in answer),
                    'ref_ids':selected,'refs_valid':isinstance(selected,list) and all(isinstance(ref,int) and ref in refs for ref in selected),
                    'semantic_support_verified':False,'method':'model_self_report_with_span_ref_checks',
                    'stage':'native_draft_before_main_source_screen'})
            if finish!='stop':
                issues.append('接口未证明完整结束，finish_reason='+str(finish))
            issues+=draft_issues(answer,sources,catalog,notes,question,quantity_checks,strict_validation=strict)
        except (ValueError,TypeError,AttributeError):
            issues=['最终JSON或answer字段不完整']
            answer=''
        original_draft=answer
        issues_before_screening=list(issues)
        # Use the existing bounded, two-stage source screen before giving up on
        # a structurally complete second draft. It cannot override the guard.
        if (strict and issues and round_no==2 and finish=='stop' and answer
            and not any('引用编号无效' in issue for issue in issues)):
            from .grounding_audit import enabled, audit_answer
            if enabled(llm):
                answer,source_screening=audit_answer(llm,question,answer,sources,context,
                                                    validation_issues=issues)
                quantity_checks=[]
                issues=draft_issues(answer,sources,catalog,notes,question,quantity_checks,strict_validation=strict)
        # Rejected drafts are diagnostic metadata only, never state.final_answer.
        # Preserve malformed JSON too, so future refusals can be explained offline.
        import hashlib
        attempts.append({'round':round_no,'max_tokens':budget,'prompt_chars':len(effective),
                         'finish_reason':finish,'issues':issues,'api_attempts':len(events),
                         'draft_answer':original_draft,'validated_answer':answer,'raw_response':str(raw),
                         'raw_response_sha256':hashlib.sha256(str(raw).encode('utf-8')).hexdigest(),
                         'quantity_checks':quantity_checks,
                         'formatting_changes':formatting_changes,
                         'evidence_catalog':catalog if issues or issues_before_screening else {},
                         'issues_before_screening':issues_before_screening,
                         'draft_rejected':bool(issues_before_screening),
                         'status':'rejected' if issues else 'accepted_after_source_screening' if issues_before_screening else 'accepted_structure'})
        if not issues:
            return answer,metadata(True)
        if round_no==2:
            break
        effective+='\n【上一轮不可通过的问题】\n'+json.dumps(issues,ensure_ascii=False)+\
            '\n请输出完整answer，优先所有核心需求；数值用原文字形或标明未确认，不补造；只用本次有效Ref。'
        if strict and any('missing_local_citation' in issue for issue in issues):
            effective+='\n逐行修复漏引文：表格行、总结行和缺口行只要出现数值，也必须有本行支持的Ref。不能只给上方工艺步骤加引用而漏掉下方表格。非用户要求的缺口表改为不重复数值的简短缺口说明，有据的核心步骤和参数保留。候选Ref只供核对，不能为未知数值随意补引文。'
        if strict:
            effective+='\n'+STRICT_NUMERIC_RULE
        hints=[{'claim_id':item['claim_id'],'line':item['answer_line'],
                'status':item['status'], 'claim_scope_signals':item['claim_scope_signals'],
                'source_scope_signals':item['source_scope_signals'],
                'unmatched_subjects':item['unmatched_subjects'],
                'possible_sources':(item.get('cross_ref_candidates')
                                    or item['uncited_candidate_matches']
                                    or item['matches'][:2])}
               for item in quantity_checks if item['status'] in {
                   'missing_local_citation','unsupported_quantity_or_unit',
                   'unsupported_subject_binding','unsupported_condition_binding'}][:6]
        if strict and hints:
            effective+='\n【数值/引用定位候选；仅数字匹配不证明整句，须核对实际原句和Ref后再引用】\n'+json.dumps(hints,ensure_ascii=False)
    # Every draft still has a check that failed. Refusing the whole answer helps
    # nobody: return the final draft with the suspect values marked in place and
    # a closing declaration, and keep the failures in metadata.
    if answer and str(answer).strip():
        from .answer_annotation import annotate_unverified
        annotated, declaration = annotate_unverified(
            answer, attempts[-1]['issues'], attempts[-1].get('quantity_checks') or [])
        attempts[-1]['annotation_rows'] = declaration
        attempts[-1]['status'] = 'accepted_with_annotations'
        result = metadata(False)
        result['annotated'] = True
        result['annotation_count'] = len(declaration)
        result['unresolved_issues'] = list(attempts[-1]['issues'])
        return annotated, result
    raise NativeAnswerError('两轮原生答案仍未通过完整性或来源约束：'+'；'.join(attempts[-1]['issues']),metadata())
