"""Explicit answer headings delimit scope; ordinary prose never licenses a section."""
import re
import unicodedata


def her_direction_issues(answer):
    """Bounded explicit contradiction signal, not a general mechanism grader."""
    value = unicodedata.normalize('NFKC', answer)
    issues = []
    pattern = re.compile(r'(?:降低|减小|减少)\s*(?:H\s*\+|氢离子|质子|析氢|HER)(?:的|还原|反应){0,3}过电位[^。！？；;\n]{0,40}?(?:抑制|减少|降低|缓解)(?:了)?(?:氢气析出|析氢|HER|产氢|氢析出)', re.I)
    for number, line in enumerate(value.splitlines(), 1):
        for match in pattern.finditer(line):
            prefix = re.split(r'[。！？；;]', line[:match.start()])[-1][-20:]
            if re.search(r'不能|不可|不应|并非|不是|不等于|错误|误写', prefix):
                continue
            issues.append(f'L{number:04d} 将降低H+还原/析氢过电位写成抑制HER，机制方向自相矛盾；核对原句，不能补全截断谓词。')
    return issues


def heading_contexts(answer):
    contexts={}
    headings={}
    for number,line in enumerate(answer.splitlines(),1):
        value=line.strip()
        markdown=re.match(r'^(#{1,6})\s+(.+)$',value)
        bold=re.fullmatch(r'(?:(?:\d+|[一二三四五六七八九十]+)[.、．]\s*)?\*\*(.+)\*\*',value)
        if markdown or bold:
            level=len(markdown[1]) if markdown else 3
            # Flat bold section labels are siblings, not descendants of old labels.
            headings={depth:text for depth,text in headings.items() if depth<level}
            headings[level]=markdown[2] if markdown else bold[1]
        contexts[number]=' '.join(headings.values())
    return contexts


def iron_deposition_issues(answer):
    contexts=heading_contexts(answer)
    issues=[]
    for number,line in enumerate(answer.splitlines(),1):
        header=contexts[number]
        sentence_scope=''
        for clause in re.split(r'[。；;]',line):
            # Same-item semicolon clauses may inherit an explicit leading
            # scope. A period closes it; prose in another sentence cannot.
            offset=line.find(clause)
            prefix=line[:max(0,offset)]
            same_sentence=prefix.rsplit('。',1)[-1]
            sentence_scope=same_sentence if re.search(r'全铁|all[- ]iron|(?:Fe|铁)沉积型',same_sentence,re.I) else ''
            match=re.search(r'(?:Fe|铁|iron)\s*(?:金属)?\s*(?:共|电)?沉积|(?:Fe|iron)\s*(?:plating|deposition)',clause,re.I)
            if not match:continue
            before=clause[max(0,match.start()-14):match.start()]
            # These explicitly deny the deposition claim rather than recommend it.
            negative=re.search(r'(?:不涉及|不发生|不进行|不以|并非|不是|不应将|不可将|不能将|不能把)\s*$',before)
            scoped=re.search(r'全铁|all[- ]iron|AIRFB|(?:Fe|铁)沉积型|非铁铬|未在铁铬|尚未.*验证|不可.*外推|仅作参考|不适用.{0,45}铁铬',clause,re.I)
            header_scoped=re.search(r'全铁|all[- ]iron|AIRFB|(?:Fe|铁)沉积型|非铁铬|外体系',header+' '+sentence_scope,re.I)
            # An explicit application to traditional ICRFB overrides a sibling
            # background heading; a global all-iron disclaimer cannot excuse it.
            local_icrfb=re.search(r'(?:传统)?铁铬(?:电池|负极)?(?:可以|可|能够|应)?(?:采用|用|利用|通过|进行)',clause)
            if not negative and (local_icrfb or not (scoped or header_scoped)):
                issues.append('Fe金属沉积/与Fe共沉积的证据未限定为全铁等外体系，不可当传统Cr负极铁铬方案；需就近标注未验证或省略该外推。')
    return list(dict.fromkeys(issues))
