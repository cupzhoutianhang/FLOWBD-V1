import re

def identify_battery_type(title, debug=False):
    """
    根据文献标题或问题识别液流电池类型
    
    支持中文和英文两种方式识别
    
    参数:
        title: 文献标题或问题字符串
        debug: 是否输出调试信息
    
    返回:
        battery_type: 电池类型字符串
    """
    
    if not title:
        return 'other'
    
    # 标准化处理：转小写，移除标点，统一分隔符（英文处理）
    text_en = title.lower()
    text_en = re.sub(r'[^\w\s-]', ' ', text_en)  # 保留连字符
    text_en = re.sub(r'[-/_\s]+', ' ', text_en)  # 统一所有分隔符为空格
    
    # 保留原始中文文本用于中文识别
    text_cn = title
    
    # 按优先级进行规则匹配（从最具体到最通用）
    rules = [
        # ===== 中文电池类型 (优先级高，最先匹配) =====
        {'type': 'iron_chromium', 'pattern': r'铁\s*铬|铁铬', 'lang': 'cn'},  # 支持"铁 铬"和"铁铬"
        {'type': 'vanadium', 'pattern': r'钒|范迪奥姆', 'lang': 'cn'},
        {'type': 'zinc_bromine', 'pattern': r'锌\s*溴|锌溴', 'lang': 'cn'},  # 支持空格变体
        {'type': 'zinc_iodine', 'pattern': r'碘化锌|锌\s*碘|锌碘', 'lang': 'cn'},
        {'type': 'zinc_manganese', 'pattern': r'锌\s*锰|锌锰', 'lang': 'cn'},
        {'type': 'alkaline_zinc', 'pattern': r'碱性\s*锌|碱性锌', 'lang': 'cn'},
        {'type': 'zinc_based', 'pattern': r'锌液流|锌基|锌\s*基', 'lang': 'cn'},
        {'type': 'polysulfide', 'pattern': r'多硫化|多\s*硫', 'lang': 'cn'},
        {'type': 'lithium_based', 'pattern': r'锂基|锂\s*基|锂', 'lang': 'cn'},
        {'type': 'chlorine', 'pattern': r'氯', 'lang': 'cn'},
        {'type': 'iron_based', 'pattern': r'铁基|铁\s*基', 'lang': 'cn'},
        {'type': 'all-iron', 'pattern': r'全\s*铁|全铁', 'lang': 'cn'},  # 支持空格变体
        {'type': 'manganese_based', 'pattern': r'锰基|锰\s*基|锰', 'lang': 'cn'},
        {'type': 'bromine', 'pattern': r'溴', 'lang': 'cn'},
        
        # ===== 具体化学体系组合 (英文) =====
        {'type': 'Sn-I', 'pattern': r'\bsn\s*i\b', 'lang': 'en'},
        {'type': 'iron_chromium', 'pattern': r'\biron\s*chromium\b', 'lang': 'en'},
        {'type': 'all-iron', 'pattern': r'\ball\s*iron\b', 'lang': 'en'},
        {'type': 'iron_vanadium', 'pattern': r'\biron\s*vanadium\b', 'lang': 'en'},
        {'type': 'iron_oxygen', 'pattern': r'\biron\s*(and)?\s*oxygen\b', 'lang': 'en'},
        {'type': 'zinc_bromine', 'pattern': r'\bzinc\s*bromine\b', 'lang': 'en'},
        {'type': 'zinc_iodine', 'pattern': r'\bzinc\s*(iodine|lodine)\b', 'lang': 'en'},
        {'type': 'zinc_manganese', 'pattern': r'\bzinc\s*manganese\b', 'lang': 'en'},
        {'type': 'alkaline_zinc_iron', 'pattern': r'\balkaline\s*zinc\s*iron\b', 'lang': 'en'},
        {'type': 'polysulfide_iodide', 'pattern': r'\bpolysulfide\s*iodide\b', 'lang': 'en'},
        {'type': 'polysulfide_air', 'pattern': r'\bpolysulfide\s*air\b', 'lang': 'en'},
        
        # ===== 单一元素/体系 (英文) =====
        {'type': 'vanadium', 'pattern': r'\bvanadium\b', 'lang': 'en'},
        {'type': 'manganese_based', 'pattern': r'\bmanganese\s*based\b', 'lang': 'en'},
        {'type': 'zinc_based', 'pattern': r'(?!.*?\balkaline\s*zinc\b)\bzinc\s*based\b', 'lang': 'en'},
        {'type': 'alkaline_zinc', 'pattern': r'(?!.*?\balkaline\s*zinc\s*iron\b)\balkaline\s*zinc\b', 'lang': 'en'},
        {'type': 'chlorine', 'pattern': r'\bchlorine\b', 'lang': 'en'},
        {'type': 'lithium_based', 'pattern': r'\blithium\s*based\b', 'lang': 'en'},
        {'type': 'iron_based', 'pattern': r'(?=.*\biron\b)(?=.*\bbased\b)(?!.*?\biron\s*chromium\b)(?!.*?\biron\s*vanadium\b)(?!.*?\ball\s*iron\b)(?!.*?\biron\s*and\s*oxygen\b)', 'lang': 'en'},
        
        # ===== 有机/水系/非水系 (英文) =====
        {'type': 'aqueous_organic', 'pattern': r'\baorfb\b|(?=.*\baqueous\b)(?=.*\borganic\b)(?=.*?(flow|redox)\b)', 'lang': 'en'},
        {'type': 'all_organic', 'pattern': r'\ball\s*organic\s*aqueous\b', 'lang': 'en'},
        {'type': 'non_aqueous', 'pattern': r'\bnon\s*aqueous\b', 'lang': 'en'},
        {'type': 'polysulfide', 'pattern': r'(?!.*?\bpolysulfide\s*(iodide|air)\b)\bpolysulfide\b', 'lang': 'en'},
        {'type': 'aqueous', 'pattern': r'(?=.*\baqueous\b)(?=.*?(flow|redox)\b)(?!.*?\baorfb\b)(?!.*?\baqueous\s*organic\b)(?!.*?\biron\s*based\b)(?!.*?\bvanadium\b)(?!.*?\bpolysulfide\b)', 'lang': 'en'},
    ]
    
    # 按顺序匹配规则
    for rule in rules:
        if rule['lang'] == 'cn':
            # 中文匹配（在原始文本中搜索）
            if re.search(rule['pattern'], text_cn):
                if debug:
                    print(f"[identify_battery_type 调试] 匹配成功：{rule['pattern']} → {rule['type']}")
                return rule['type']
        else:
            # 英文匹配（在转换后的文本中搜索）
            if re.search(rule['pattern'], text_en):
                if debug:
                    print(f"[identify_battery_type 调试] 匹配成功：{rule['pattern']} → {rule['type']}")
                return rule['type']
    
    if debug:
        print(f"[identify_battery_type 调试] 未找到匹配，返回 'other'")
        print(f"  原始文本: {title}")
        print(f"  中文模式: {text_cn}")
        print(f"  英文模式: {text_en}")
    
    return 'other'
