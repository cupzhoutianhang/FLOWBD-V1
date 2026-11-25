"""Bounded checks for observed material-scope and mechanism overstatements."""
import re

HEO=re.compile(r'高熵|\bHEOs?\b|high[- ]entropy',re.I)
EG=re.compile(r'膨胀石墨|expanded graphite|\bEG\b',re.I)
QUALIFIED=re.compile(r'可能|推测|推断|可解释|假设|尚无|未直接|未证明|未证实|未明确|未详细(?:描述|说明)|是否|缺乏|待验证|不能|不可|不宜|仅供参考|未在.{0,12}验证')
METHODS={'溶胶-凝胶':r'溶胶[-– ]?凝胶|sol[-– ]?gel','热解':r'(?<!喷雾)热解|(?<!spray )(?<!spray-)pyrolysis','电沉积':r'电沉积|electrodeposition'}
INTERFACE=re.compile(r'(?:降低|减小|减少|改善|缓解)[^。；;，,\n]{0,12}(?:界面|接触)热阻|(?:界面|接触)热阻[^。；;，,\n]{0,10}(?:降低|减小|减少)',re.I)
NETWORK=re.compile(r'(?:三维|连续)[^。；;，,\n]{0,8}(?:导热网络|导热通路|导热通道)|导热(?:网络|通路|通道)[^。；;，,\n]{0,8}(?:连续|三维)|3D[^.;\n]{0,20}(?:thermal|conduct)',re.I)
CONTACT=re.compile(r'(?:确保|保证)[^。；;，,\n]{0,25}紧密接触')
ROUTE_ASSERTION=re.compile(r'采用|使用|制备了|合成了|可制备|可合成|提高|提升|改善|降低|增强|促进|适用|能够|可以|实现|属于|导致|形成|维持|构建|确保|保证|存在局限|均匀性差')
ICRFB=re.compile(r'铁铬|iron[-– ]chromium|ICRFB',re.I)
ALL_IRON=re.compile(r'全铁|all[-– ]iron|AIRFB',re.I)
SOC=re.compile(r'(?<![A-Za-z])SOC(?![A-Za-z])|荷电状态',re.I)
SOH=re.compile(r'(?<![A-Za-z])SOH(?![A-Za-z])|健康状态',re.I)
SILICA_GEL=re.compile(r'硅凝胶|silica[- ]gel',re.I)
N2_ADSORPTION=re.compile(r'N\s*2|氮气|nitrogen',re.I)
CARBON_FELT=re.compile(r'碳毡|碳布|carbon[- ]felt',re.I)
NAFION=re.compile(r'Nafion|全氟磺酸',re.I)
CHANNEL=re.compile(r'通道|channel',re.I)
PARTICLE_SIZE=re.compile(r'粒径|颗粒尺寸|particle[- ]size',re.I)


def _nominal_gap(text):
    """A missing-parameter topic is not an assertion that a route was validated."""
    if not ROUTE_ASSERTION.search(text):return True
    # In an explicitly missing-evidence list, "降低机制的实验验证" names
    # unavailable evidence; it does not assert that a reduction was measured.
    topic=re.sub(r'\[Ref-\d+\]|[*\s。；;：:]','',text).rstrip('）)')
    if re.search(r'显著|明显|有效|确保|保证|使得|导致|实现|已经|证实|表明|显示|必然',topic):return False
    return bool(re.search(r'(?:数值|机制|机理|策略|证据|表征|数据|参数|条件|规律|过程|途径|方案|方法|关系|效应|影响|阈值|程度|关联|分布|窗口|模型|细节|验证)$',topic))


def guidance(question):
    notes=[]
    if HEO.search(question):
        notes.append('高熵氧化物制备路线只列原文明确针对HEO的实例；同一综述中一般金属化合物的溶胶-凝胶、热解或电沉积介绍不能自动算HEO已验证路线。缺直接HEO实例时省略该方法，不额外列外体系的探索方法清单来凑路线。仅报道固相法不能推出其元素均匀性差或工艺局限。')
    if EG.search(question):
        notes.append('膨胀石墨的多孔形貌、毛细吸附、定形与导热/蓄放热改善可按原句陈述；形貌及性能提升本身不证明连续三维热流通路或界面热阻降低，防泄漏也不证明导热网络连续性，物理包封不能直接写成确保紧密接触。原文未直接说明的机制只能在同一句用“可能/可解释为”标明推断，或写明缺证；标题也属于科学主张，不能在正文说未证明却把标题写成“形成连续导热网络”。推断的标题和正文均须有可能/推断标记。不能为评分举例补造机制，也不能把CNT等其他填料的机理归给EG。')
    return '\n'.join(notes)


def _direct_route(pattern, quotes):
    for quote in quotes:
        for match in re.finditer(pattern,quote,re.I):
            if HEO.search(quote[max(0,match.start()-180):match.end()+100]):return True
    return False


def claim_issues(question, claim, quotes, gap_context=False):
    """Check explicit overstatements only, not arbitrary scientific truth."""
    out=[]
    external_reference=(re.search(r'其他|一般|钙基|别的|非高熵|非HEO',claim) and re.search(r'参考|参照|借鉴|未验证|背景|探索',claim))
    external_reference=external_reference or (re.search(r'该描述针对钙基材料',claim) and re.search(r'HEO[^。；;]{0,45}本次片段未明确',claim))
    for sentence in re.split(r'[。；;\n]',claim):
      tail_gap=re.search(r'本次[^。；;]{0,12}(?:片段|证据)[^。；;]{0,6}(?:未明确|未给出)',sentence)
      topic=sentence[:tail_gap.start()].rstrip('，,：: ') if tail_gap else sentence
      scoped_gap=(gap_context or tail_gap) and bool(topic.strip()) and all(_nominal_gap(part) for part in re.split(r'[，,]',topic) if part.strip())
      for clause in re.split(r'[，,]|但是|然而|不过|但',sentence):
        if QUALIFIED.search(clause):continue
        if scoped_gap:continue
        if HEO.search(question) and not external_reference:
            uniformity_limit = re.search(
                r'(?:均匀性|均匀度|元素分布)[^。；;，,\n]{0,8}(?:差|较差|不佳|不均|不均匀|不足)|'
                r'(?:元素|组分)[^。；;，,\n]{0,6}分布不均|局限|不足|较差|难以|难于|受限',
                clause)
            uniformity_claim = re.search(r'均匀|不均|元素分布|组分分布', clause)
            if re.search(r'固相',sentence) and uniformity_claim and uniformity_limit:
                if not any(re.search(r'固相',q) and re.search(r'均匀',q) and re.search(
                        r'(?:均匀性|均匀度|元素分布)[^。；;，,\n]{0,8}(?:差|较差|不佳|不均|不均匀|不足)|'
                        r'(?:元素|组分)[^。；;，,\n]{0,6}分布不均|局限|不足|较差|难以|难于|受限',q) for q in quotes):
                    out.append('固相法的均匀性局限未获所引原句支持；保留已报道路线，删除无据评价或明确推断。')
            for label,pattern in METHODS.items():
                if not scoped_gap and re.search(pattern,clause,re.I) and not _direct_route(pattern,quotes):
                    out.append(label+'的一般前驱体介绍不足以证明HEO路线；需材料实例、就近限定为探索参考，或省略。')
        if EG.search(question):
            if INTERFACE.search(clause) and not any(INTERFACE.search(q) for q in quotes):
                out.append('界面热阻降低不是形貌/热导率观察的直接结论；缺直接原句时须标为推断或缺口。')
            if NETWORK.search(clause) and not any(NETWORK.search(q) for q in quotes):
                out.append('连续/三维导热通路未被所引原句直接证明；只能作为明确标注的解释，不能写成已证机制。')
            if CONTACT.search(clause) and not any(CONTACT.search(q) for q in quotes):
                out.append('物理包封不能直接证明确保紧密接触；无直接原句时须标为推断或省略。')
        if ICRFB.search(question) and re.search(r'Bi|铋',clause,re.I) and re.search(r'析氢|hydrogen evolution',clause,re.I):
            direct=any(ICRFB.search(q) and re.search(r'Bi|铋',q,re.I) and re.search(r'析氢|hydrogen evolution',q,re.I) for q in quotes)
            all_iron_only=any(ALL_IRON.search(q) and not ICRFB.search(q) for q in quotes)
            if not direct and all_iron_only:
                out.append('全铁体系的Bi沉积析氢证据不能直接外推到铁铬体系；须限定为外体系背景或补充铁铬原句。')
        if SOH.search(question) and SOC.search(clause) and SOH.search(clause) and re.search(r'采用|使用|方法|估算|估计|迁移|套用',clause):
            if not any(SOH.search(q) and SOC.search(q) for q in quotes):
                out.append('SOC估计方法不能直接作为SOH已验证方法；须补充SOH原句或明确标注迁移未验证。')
        if CARBON_FELT.search(question) and SILICA_GEL.search(clause) and N2_ADSORPTION.search(clause) and re.search(r'孔|孔径|孔隙|pore',clause,re.I):
            if not any(CARBON_FELT.search(q) and SILICA_GEL.search(q) and N2_ADSORPTION.search(q) for q in quotes):
                out.append('硅凝胶的N2吸附结果不能证明碳毡/碳布孔结构；须限定为外体系背景或补充目标材料原句。')
        if NAFION.search(question) and CHANNEL.search(question) and PARTICLE_SIZE.search(clause) and NAFION.search(clause) and CHANNEL.search(clause):
            if not any(PARTICLE_SIZE.search(q) and NAFION.search(q) and CHANNEL.search(q) for q in quotes):
                out.append('活性物质粒径不能外推到Nafion膜通道尺寸；须补充膜通道的直接证据。')
    return list(dict.fromkeys(out))


def answer_boundary_issues(question, answer, catalog):
    if not (HEO.search(question) or EG.search(question)):return []
    out=[]
    gap_context=False
    for number,line in enumerate(answer.splitlines(),1):
        if re.match(r'^\s*(?:#{1,6}\s|\*\*)',line):
            gap_context=bool(re.search(r'缺口|待核|待验证|未获.{0,6}支持',line))
        if re.search(r'本次.{0,12}(?:片段|证据).{0,6}(?:未明确|未提供|未给出).{0,12}(?:以下|如下)',line):
            gap_context=True
        refs={int(v) for v in re.findall(r'\[Ref-(\d+)\]',line)}
        quotes=[q['quote'] for q in catalog.values() if q['ref_id'] in refs]
        out.extend(f'L{number:04d} 证据边界：'+s for s in claim_issues(question,line,quotes,gap_context=gap_context))
    return out
