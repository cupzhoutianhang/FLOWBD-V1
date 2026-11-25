"""Answer-side citation validation and bounded per-claim source support checks."""
from __future__ import annotations
import json
import re
import unicodedata

SYSTEM_PROMPT = """你是储能文献问答助手。直接回答用户实际问题，篇幅和结构服从信息需求，不强制写综述。
只使用给出的证据作事实依据。制备题按实际步骤、配比、温度、时间回答；机理题解释有据因果；谱系题严格按审计记录的端点、类型、方向和状态回答。
每个关键事实就近引用[Ref-n]，引用必须支持事实。引用编号只能来自当前来源目录。
文献未提供的参数、条件、路线和数值明确说明未获得支持，禁止按常见做法补造。
区分本次未检索到与语料根本没有；明确可回答部分和剩余缺口。
若只拿到片段，只能说“本次提供的片段未明确”，不能断言整篇文献未给出。PDF识别错乱的单位须注明不确定，不把推断修复当逐字原文。
专业推断只能单独标注（专业推断），不能借用不支持它的引用；不需要强行提供推断或展望。
用户前提错误时指出并给依据；accepted或综述可定位关系不等于confirmed，语义相似不能证明演化。
比较数值时保留体系、样品、条件和单位；不混用Wh/kg、Wh/L或不同效率指标。
不同研究的酸性铁铬与近中性CrEDTA等体系分别描述，不能拼成一个统一配方。除非有同条件直接比较证据，不把某篇文献的优化浓度或策略写成“最有效”“最佳途径”或通用最优。
只输出最终答案，不输出计划、自检、思考过程或虚构文献来源列表。"""

SEMANTIC_PROMPT = """你是独立的逐引用支持核验器。只判断答案中的每个事实主张是否被其就近引用的原文片段支持，不使用常识补全，不因编号合法就判支持。
逐项核对主体、体系、样品、条件、单位、数值、比较方向和因果方向。原文只支持部分内容时为partial；原文相反或属于其他体系时为unsupported；缺少可核对原文时为unverified。
缺口陈述不是事实主张，可返回gap_statement。不得新增原文没有的引用或事实。只输出JSON：
{"review_complete":true,"claims":[{"claim_id":"S0001","verdict":"supported|partial|unsupported|unverified|gap_statement","supported_refs":[1],"reason":"简短依据"}]}
必须覆盖输入中的全部claim_id，且每个claim_id只出现一次。"""

_GAP_CLAIM = re.compile(
    r'缺口|未(?:获得|检索到|明确|在|给出|提供|直接|验证|证实)|缺乏|需查阅|不能按|'
    r'本次(?:提供|检索|片段)|当前片段|尚无|待验证|无法确认', re.I)


def citation_catalog(sources):
    return "\n".join(f"[Ref-{s['ref_id']}][{s.get('type', 'vector')}] "
                     f"{s.get('source_label') or s.get('source', '')}"
                     for s in sources if s.get("ref_id"))


def normalize_citations(answer):
    """Canonicalize identifiable Ref markers before auditing and footer creation.

    Models sometimes emit bare, parenthesized or explanatory markers despite the
    requested format. They must enter the same source check, including unknown
    numbers. A bracket such as ``[Ref-12仅确认电位关系]`` is a citation plus a
    note, not a malformed unknown reference: the note is preserved verbatim
    outside the normalized marker and is never treated as factual support.
    This changes citation punctuation only, never the associated factual text.
    """
    text = str(answer or "")
    ref_list = r"Ref-\d+(?:\s*[,，、;；/／]\s*(?:Ref-)?\d+)*"
    delimiters = ((r"\[", r"\]"), (r"\(", r"\)"), ("（", "）"), ("［", "］"))
    for opening, closing in delimiters:
        pattern = re.compile(opening + r"\s*(?P<refs>" + ref_list + r")(?P<note>[^" + closing + r"]*?)" + r"\s*" + closing)
        def expand(match):
            refs = "".join(f"[Ref-{n}]" for n in re.findall(r"\d+", match.group("refs")))
            note = match.group("note")
            if re.match(r"\s*[,，、;；/／\-–—]\s*(?!\d)", note):
                return match.group(0)
            return refs + note
        text = pattern.sub(expand, text)
    return re.sub(r"(?<![A-Za-z0-9_\[-])Ref-(\d+)(?![A-Za-z0-9_-])", r"[Ref-\1]", text)


def _source_chunks(sources):
    out = []
    for source in sources or []:
        if not source.get('ref_id'):
            continue
        for index, chunk in enumerate(source.get('chunks') or [source]):
            content = str(chunk.get('content') or '')
            if content.strip():
                out.append({'ref_id': int(source['ref_id']),
                            'source_id': chunk.get('source_id') or source.get('source_id'),
                            'content': content})
    return out


def _compact(text):
    value = unicodedata.normalize('NFKC', str(text or ''))
    value = re.sub(r'\[Ref-\d+\]', '', value)
    return re.sub(r'[^0-9A-Za-z\u4e00-\u9fff.%‰]+', '', value).lower()


def _support_units(text):
    compact = _compact(text)
    units = set(re.findall(r'[a-z]+|\d+(?:\.\d+)?[%‰]?', compact))
    cjk = re.sub(r'[^\u4e00-\u9fff]', '', compact)
    if len(cjk) == 1:
        units.add(cjk)
    units.update(cjk[i:i + 2] for i in range(max(0, len(cjk) - 1)))
    return units


def _overlap(claim, source):
    claim_units = _support_units(claim)
    if not claim_units:
        return 0.0
    source_units = _support_units(source)
    return len(claim_units & source_units) / len(claim_units)


def _answer_claims(answer):
    body = normalize_citations(answer).split('【文献来源】')[0]
    claims = []
    for line_no, line in enumerate(body.splitlines(), 1):
        value = line.strip()
        if not value:
            continue
        heading = bool(re.match(r'^(?:#{1,6}\s|\*\*[^*]+\*\*\s*$)', value))
        separator = bool(re.fullmatch(r'\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?', value))
        if separator:
            continue
        parts = re.split(r'(?<=[。！？!?；;])', value)
        for part in parts:
            text = part.strip()
            if not text:
                continue
            refs = sorted({int(n) for n in re.findall(r'\[Ref-(\d+)\]', text)})
            gap = bool(_GAP_CLAIM.search(re.sub(r'\[Ref-\d+\]', '', text)))
            if heading:
                kind = 'heading'
            elif gap:
                kind = 'gap_statement'
            else:
                kind = 'factual'
            claims.append({'claim_id': f'S{len(claims)+1:04d}', 'line_number': line_no,
                           'text': text, 'refs': refs, 'kind': kind})
    return claims


def _model_semantic_review(llm, claims, source_chunks):
    if llm is None:
        return None, 'not_run_no_model'
    try:
        from .structured_llm import call_structured
        payload = {'claims': [
            {'claim_id': claim['claim_id'], 'claim': claim['text'], 'refs': claim['refs'],
             'sources': [dict(chunk, content=chunk['content'][:1800])
                         for chunk in source_chunks if chunk['ref_id'] in claim['refs']][:8]}
            for claim in claims if claim['kind'] == 'factual'
        ]}
        if not payload['claims']:
            return {'review_complete': True, 'claims': []}, 'no_factual_claims'
        raw = call_structured(llm, SEMANTIC_PROMPT + '\n' + json.dumps(payload, ensure_ascii=False),
                              max_tokens=3600)
        match = re.search(r'\{.*\}', str(raw or ''), re.S)
        if not match:
            return None, 'invalid_json'
        result = json.loads(match.group(0))
        if not isinstance(result, dict) or result.get('review_complete') is not True or not isinstance(result.get('claims'), list):
            return None, 'incomplete_review'
        return result, 'model_reviewed'
    except Exception as error:  # A failed verifier must remain visibly unverified.
        return None, f'verifier_error:{type(error).__name__}'


def verify_semantic_support(answer, sources, llm=None):
    """Verify every factual claim/ref against actual source spans.

    The deterministic layer proves span identity, reference mapping and coverage.
    A successful model review is additionally required before the global flag can
    be true; lexical similarity alone never upgrades the answer to verified.
    """
    claims = _answer_claims(answer)
    chunks = _source_chunks(sources)
    available = {chunk['ref_id'] for chunk in chunks}
    deterministic_issues = []
    for claim in claims:
        claim['deterministic_ref_mapping'] = all(ref in available for ref in claim['refs'])
        candidates = [chunk for chunk in chunks if chunk['ref_id'] in claim['refs']]
        scores = {ref: max((_overlap(claim['text'], chunk['content'])
                            for chunk in candidates if chunk['ref_id'] == ref), default=0.0)
                  for ref in claim['refs']}
        claim['lexical_overlap'] = {str(ref): round(score, 4) for ref, score in scores.items()}
        claim['source_span_ids'] = sorted({chunk['source_id'] for chunk in candidates if chunk.get('source_id')})
        if claim['kind'] == 'factual' and not claim['refs']:
            deterministic_issues.append({'claim_id': claim['claim_id'], 'issue': 'missing_local_citation'})
        if not claim['deterministic_ref_mapping']:
            deterministic_issues.append({'claim_id': claim['claim_id'], 'issue': 'unknown_or_unmapped_ref'})
    review, review_status = _model_semantic_review(llm, claims, chunks)
    reviewed = {}
    if review:
        for row in review.get('claims', []):
            if isinstance(row, dict) and isinstance(row.get('claim_id'), str):
                reviewed[row['claim_id']] = row
    factual = [claim for claim in claims if claim['kind'] == 'factual']
    coverage_complete = all(
        claim['refs'] and claim['deterministic_ref_mapping'] for claim in factual
    ) and not any(issue['issue'] == 'missing_local_citation' for issue in deterministic_issues)
    exact_coverage = set(reviewed) == {claim['claim_id'] for claim in factual} if review else False
    all_supported = True
    for claim in factual:
        row = reviewed.get(claim['claim_id'])
        if not row:
            claim['verdict'] = 'unverified'
            claim['verification_reason'] = 'not_reviewed'
            all_supported = False
            continue
        verdict = str(row.get('verdict') or 'unverified')
        refs = row.get('supported_refs')
        valid_refs = isinstance(refs, list) and all(isinstance(ref, int) and ref in claim['refs'] for ref in refs)
        if verdict == 'supported' and valid_refs and set(refs) == set(claim['refs']):
            claim['verdict'] = 'supported'
        elif verdict in {'supported', 'partial', 'unsupported', 'unverified'}:
            claim['verdict'] = verdict if verdict != 'supported' else 'partial'
        else:
            claim['verdict'] = 'unverified'
        claim['supported_refs'] = refs if isinstance(refs, list) else []
        claim['verification_reason'] = str(row.get('reason') or '')[:300]
        if claim['verdict'] != 'supported':
            all_supported = False
    for claim in claims:
        if claim['kind'] == 'gap_statement':
            claim['verdict'] = 'gap_statement'
            claim['supported_refs'] = []
            claim['verification_reason'] = 'explicit evidence gap; no factual support required'
        elif claim['kind'] == 'heading':
            claim['verdict'] = 'not_factual'
            claim['supported_refs'] = []
            claim['verification_reason'] = 'section heading'
    verified = bool(review and review_status == 'model_reviewed' and coverage_complete and exact_coverage and all_supported)
    return {
        'semantic_support_verified': verified,
        'verification_method': 'deterministic_span_ref_mapping_plus_model_claim_review',
        'review_status': review_status,
        'coverage_complete': coverage_complete,
        'claim_coverage_exact': exact_coverage,
        'claims': claims,
        'issues': deterministic_issues,
        'note': 'Only an explicit per-claim supported verdict with mapped source spans upgrades this flag.',
    }


def check_citations(answer, sources, semantic=None):
    body = normalize_citations(answer).split("【文献来源】")[0]
    cited = sorted(set(int(n) for n in re.findall(r"\[Ref-(\d+)\]", body)))
    available = {int(s["ref_id"]) for s in sources if s.get("ref_id")}
    invalid = sorted(set(cited) - available)
    malformed = [m for m in re.findall(r"\[Ref-[^\]]+\]", body) if not re.fullmatch(r"\[Ref-\d+\]", m)]
    semantic = semantic if isinstance(semantic, dict) else verify_semantic_support(answer, sources)
    return {"cited_refs": cited, "invalid_refs": invalid,
            "malformed_markers": malformed, "citation_mapping_valid": not invalid and not malformed,
            "semantic_support_verified": bool(semantic.get('semantic_support_verified')),
            "semantic_support": semantic,
            "note": "编号检查不等于事实支撑核验；语义核验逐claim/span/ref记录"}
