import re

def identify_battery_type(title):
    """
    根据文献标题识别液流电池类型
    
    参数:
        title: 文献标题字符串
    
    返回:
        battery_type: 电池类型字符串
    """
    
    # 标准化处理：转小写，移除标点，统一分隔符
    text = title.lower()
    text = re.sub(r'[^\w\s-]', ' ', text)  # 保留连字符
    text = re.sub(r'[-/_\s]+', ' ', text)  # 统一所有分隔符为空格
    
    # 按优先级进行规则匹配（从最具体到最通用）
    rules = [
        # ===== 具体化学体系组合 =====
        {
            'type': 'Sn-I',
            'pattern': r'\bsn\s*i\b|锡碘',
            'desc': '锡碘液流电池'
        },
        {
            'type': 'iron_chromium',
            'pattern': r'\biron\s*chromium\b|铁铬',
            'desc': '铁铬液流电池 (处理连字符、空格等分隔符变体)'
        },
        {
            'type': 'all-iron',
            'pattern': r'\ball\s*iron\b|全铁',
            'desc': '全铁液流电池 (要求 "all" 和 "iron" 同时出现)'
        },
        {
            'type': 'iron_vanadium',
            'pattern': r'\biron\s*vanadium\b|铁钒',
            'desc': '铁钒液流电池'
        },
        {
            'type': 'iron_oxygen',
            'pattern': r'\biron\s*(and)?\s*oxygen\b|铁氧',
            'desc': '铁氧气液流电池 (处理 "iron and oxygen" 和 "iron-oxygen")'
        },
        {
            'type': 'zinc_bromine',
            'pattern': r'\bzinc\s*bromine\b|锌溴',
            'desc': '锌溴液流电池 (支持 Zinc-Bromine, zinc bromine 等变体)'
        },
        {
            'type': 'zinc_iodine',
            'pattern': r'\bzinc\s*(iodine|lodine)\b|锌碘',
            'desc': '锌碘液流电池 (支持 zinc iodine, Zinc-lodine 拼写错误等变体)'
        },
        {
            'type': 'zinc_manganese',
            'pattern': r'\bzinc\s*manganese\b|锌锰',
            'desc': '锌锰液流电池 (支持锌锰、Zinc-Manganese 等变体)'
        },
        {
            'type': 'alkaline_zinc_iron',
            'pattern': r'\balkaline\s*zinc\s*iron\b|碱性锌铁',
            'desc': '碱性锌铁液流电池'
        },
        {
            'type': 'polysulfide_iodide',
            'pattern': r'\bpolysulfide\s*iodide\b|多硫化(物)?碘',
            'desc': '多硫化物碘液流电池'
        },
        {
            'type': 'polysulfide_air',
            'pattern': r'\bpolysulfide\s*air\b|多硫化(物)?空气',
            'desc': '多硫化物空气液流电池'
        },
        
        # ===== 单一元素/体系 =====
        {
            'type': 'vanadium',
            'pattern': r'\bvanadium\b|钒',
            'desc': '钒液流电池 (优先级高，必须在 vanadium-based 之前)'
        },
        {
            'type': 'manganese_based',
            'pattern': r'\bmanganese\s*based\b|锰基',
            'desc': '锰基液流电池 (不匹配 zinc_manganese)'
        },
        {
            'type': 'zinc_based',
            'pattern': r'(?!.*?\balkaline\s*zinc\b)\bzinc\s*based\b|锌基(?!.*?碱性锌)',
            'desc': '锌基液流电池 (排除 alkaline_zinc 和 alkaline_zinc_iron)'
        },
        {
            'type': 'alkaline_zinc',
            'pattern': r'(?!.*?\balkaline\s*zinc\s*iron\b)\balkaline\s*zinc\b|碱性锌(?!.*?铁)',
            'desc': '碱性锌液流电池 (排除 alkaline_zinc_iron)'
        },
        {
            'type': 'chlorine',
            'pattern': r'\bchlorine\b|氯',
            'desc': '氯液流电池'
        },
        {
            'type': 'lithium_based',
            'pattern': r'\blithium\s*based\b|锂基',
            'desc': '锂基液流电池'
        },
        {
            'type': 'iron_based',
            'pattern': r'((?=.*\biron\b)(?=.*\bbased\b)(?!.*?\biron\s*chromium\b)(?!.*?\biron\s*vanadium\b)(?!.*?\ball\s*iron\b)(?!.*?\biron\s*and\s*oxygen\b))|铁基(?!.*?[铬钒氧])(?!.*?全铁)',
            'desc': '铁基液流电池 (排除 iron_chromium, iron_vanadium, all-iron, iron_oxygen)'
        },
        
        # ===== 有机/水系/非水系 =====
        {
            'type': 'aqueous_organic',
            'pattern': r'\baorfb\b|((?=.*\baqueous\b)(?=.*\borganic\b)(?=.*?(flow|redox)\b))|水系有机',
            'desc': '水系有机液流电池 (AORFB 或 aqueous organic flow/redox)'
        },
        {
            'type': 'all_organic',
            'pattern': r'\ball\s*organic\s*aqueous\b|全有机',
            'desc': '全有机液流电池 (all organic aqueous)'
        },
        {
            'type': 'non_aqueous',
            'pattern': r'\bnon\s*aqueous\b|非水',
            'desc': '非水液流电池 (排除 aqueous_organic, all_organic)'
        },
        {
            'type': 'polysulfide',
            'pattern': r'(?!.*?\bpolysulfide\s*(iodide|air)\b)\bpolysulfide\b|多硫化(物)?',
            'desc': '多硫化物液流电池 (排除 polysulfide_iodide, polysulfide_air)'
        },
        {
            'type': 'aqueous',
            'pattern': r'((?=.*\baqueous\b)(?=.*?(flow|redox)\b)(?!.*?\baorfb\b)(?!.*?\baqueous\s*organic\b)(?!.*?\biron\s*based\b)(?!.*?\bvanadium\b)(?!.*?\bpolysulfide\b))|水系',
            'desc': '水系液流电池 (排除 aqueous_organic, iron_based, vanadium)'
        },
    ]
    
    # 按顺序匹配规则
    for rule in rules:
        if re.search(rule['pattern'], text):
            return rule['type']
    
    return 'other'
