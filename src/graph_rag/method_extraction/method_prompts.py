"""方法演化抽取 prompt 模板. 单独成文件方便调参不动主脚本."""

SYSTEM_PROMPT = (
    "你是储能材料领域的方法演化分析专家。任务是从一篇中文学术论文中"
    "抽取'提出的方法'和'方法之间的演化关系'。只能返回严格的 JSON 对象, "
    "不能有任何 markdown 围栏 (如 ```json) 或额外说明。"
)

USER_PROMPT_TEMPLATE = """# 任务
从下面这篇储能领域中文学术论文中抽取:
1. 本文提出的核心方法 (own_methods, 通常 1-2 个)
2. 本文引用并与之比较/扩展的前人方法 (referenced_methods, 0-5 个)
3. 这些方法之间的演化关系 (evolution_edges)

# 方法 (Method) 定义
"方法" 是论文提出或对比的**具体技术方案/工艺路线/材料设计策略**, 不是表征手段.
- 例 (是方法): "SPEEK 磺酸基交联离子选择膜", "高熵钙钛矿氧化物 LCHFMNCu 阳离子空位调控", "碳毡浸渍 ZIF-67 电极改性"
- 例 (不是方法): XRD/SEM/DFT (表征/计算); 锂离子电池/液流电池 (装置类型); Li+/Fe2+ (物种)

# 方法命名规则 (严格)
- 必须**具有辨识度**, 写成 "材料/工艺 + 关键特征" 的短语 (15-30 字)
- 严禁使用 "本方法 / 本研究方法 / 该方法" 这种无信息名
- 引用的前人方法也要尽量具名 (如 "Smith2018 的多孔碳模板法"); 实在不知道作者就写 "传统 X 方法 + 关键特征"

# 4 种演化关系定义 (选其一)
- EXTENDS  : 在前人方法**基础上增加新模块/新机理**, 保留主框架. 触发语 "在 X 基础上引入", "扩展 X 至", "以 X 为骨架并加入"
- IMPROVES : 同类方法的**参数/性能优化**, 主框架不变. 触发语 "相比 X 本方法在 Y 指标上提升 N%", "优化 X 的"
- ADAPTS   : 把**其他领域**的方法搬过来用. 触发语 "借鉴 X 领域的 Y 思想", "将 Z 中的方法迁移到本领域"
- REPLACES : 用**全新方法**替代旧的解决同一问题. 触发语 "传统 X 存在 Y 问题, 本研究用 Z 替代", "突破 X 的局限"

# 严格性要求
- evidence 必须是原文片段引用, 不超过 150 字, 用 \"...\" 包裹
- 找不到明确演化关系就**不要硬编**, 宁缺勿滥
- "本文方法在 X 之后发表" 不等于演化关系, 必须有 4 种语义之一
- 实在不确定的关系标 confidence: "low"

# 综述类论文的特殊规则 (题目含 "进展" / "综述" / "现状" / "发展" / "review")
- own_methods **可以为空数组** (综述本身不提出新方法)
- 此时 evolution_edges **不必从 own_method 出发**, 可以是任意两个 referenced_method 之间的演化关系
- 例: 综述提到 "传统 A 方法存在 X 问题, B 改进了 Y, C 在 B 基础上扩展加入 Z" 时, 应生成:
  - {{"from_method": "B", "to_method": "A", "relation": "IMPROVES", ...}}
  - {{"from_method": "C", "to_method": "B", "relation": "EXTENDS", ...}}
- 方向规则: from_method 一定是**后出现 / 改进 / 扩展者**, to_method 一定是**被改进 / 被扩展的前者**
- 综述类目标: 抽出 5-15 条 referenced_methods 之间的演化边, 体现这个方向的方法演进史

# 输出格式 (严格 JSON, 无 markdown 围栏)
{{
  "own_methods": [
    {{
      "name": "<辨识度强的方法名>",
      "innovation": "<这个方法的核心创新, 50-100 字>",
      "problem_solved": "<解决的核心问题, 30-80 字>",
      "key_components": ["<组件1>", "<组件2>"]
    }}
  ],
  "referenced_methods": [
    {{
      "name": "<被引用的前人方法名>",
      "citation_clue": "<参考文献编号或作者年份, 如 [12]/Smith 2018>"
    }}
  ],
  "evolution_edges": [
    {{
      "from_method": "<本文方法名>",
      "to_method": "<被引用的前人方法名>",
      "relation": "EXTENDS",
      "evidence": "<原文片段, 不超过 150 字>",
      "confidence": "high",
      "reason": "<为什么这样判断, 不超过 80 字>"
    }}
  ]
}}

# 输入: 论文文本 (头 + 尾拼接, 中间正文实验细节已省略)
<<<
{paper_text}
>>>
"""


def build_user_prompt(paper_text: str) -> str:
    """填充用户 prompt. 单引号转义防 .format 报错."""
    return USER_PROMPT_TEMPLATE.format(paper_text=paper_text)
