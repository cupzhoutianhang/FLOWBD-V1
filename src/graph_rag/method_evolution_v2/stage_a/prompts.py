"""Stage A v2 - 句子 ID 引用协议 (spec 六).

关键变化(v2):
  - LLM **不复制**原文证据, **不生成** char_start/end / evidence_quote
  - LLM 只返回 evidence_sentence_ids: 从输入索引里挑 1-3 个真实 sentence_id
  - 未提供的 ID 视为伪造 -> 本地校验必然拒绝该方法
  - 找不到支持句 -> 不输出该方法, 不为凑数
"""
from __future__ import annotations

# spec 四: 用于全量 runner 的 SHA 版本锁 (改 prompt 时同步升级)
PROMPT_VERSION = "stage_a_v2.0_sentence_ids"


SYSTEM_PROMPT = (
    "你是储能材料与系统方向的方法演化分析专家。任务是从一篇论文中抽取"
    "'方法节点', **只抽方法, 不抽任何演化关系**。"
    "\n"
    "本轮特别约定 (v2):"
    "\n- **不要复制原文证据, 不要写 evidence_quote**"
    "\n- 只填写 evidence_sentence_ids, 引用输入中真实存在的 sentence_id"
    "\n- 若找不到支持句, 就不要输出该方法 (宁空不假)"
    "\n"
    "必须严格按 JSON 对象返回, 不能有任何 markdown 围栏 (```json 等) 或额外说明."
)


USER_PROMPT_TEMPLATE = """# 任务
从下面这篇储能领域论文中抽取:
1. own_methods: 本文提出/建立/改性/制备/构建的具体方法
2. referenced_methods: 与本文有**直接**比较、继承或对照关系的前人方法

**不抽任何演化关系。不为凑数强抽。宁可空数组, 不要造假 sentence_id。**

# "方法" 的严格定义 (与 v1 相同)
"方法" 必须是**具体的技术方案**:
- material_design         材料设计: 组分设计/空位调控/结构工程/掺杂策略等
- synthesis_process       制备工艺: 溶胶-凝胶法/水热法/静电纺丝/熔融共混等
- interface_engineering   界面工程: SEI 层设计/涂层/表面修饰
- electrode_engineering   电极工程: 具体电极结构/3D 电极/复合电极
- electrolyte_engineering 电解质工程: 具体电解液组成/添加剂/固态电解质配方
- membrane_engineering    膜工程: 离子选择膜/离子交换膜/隔膜具体结构
- device_design           装置设计: 具体反应器/电堆/储热器/换热器结构
- system_design           系统设计: 具体流程/系统集成/耦合方案
- model_simulation        建模仿真: 具体的数学模型/CFD/有限元/边界条件方案
- control_strategy        控制策略: 具体控制律/调度策略
- optimization_algorithm  优化算法: 具体优化算法在储能问题上的应用
- other                   以上都不合适, 但确属可辨识的技术方案

**严格排除** (以下不算方法, 不要输出):
- 材料名称本身 (如 "锂离子电池"/"MOF"/"石蜡")
- 性能指标 (如 "比容量 200 mAh/g")
- 研究对象 (如 "钠离子电池正极材料")
- 普通表征 (XRD/SEM/TEM/XPS/BET/DFT 单独存在)
- 普通实验操作 (如 "称取"/"搅拌"/"洗涤")
- 宽泛概念 (如 "提高性能"/"结构优化" 无具体技术路径)
- 只描述问题/限制/机理但没有技术方案的内容

# 命名规则
- name: 15-40 字, "材料/工艺 + 关键特征" 短语, 具备辨识度
- 严禁: "本方法" / "该方法" / "所提方法" 等无信息名
- referenced_methods 尽量具名: "Smith 2018 多孔碳模板法"

# 本文类型与抽取侧重
- **research_article**: 重点抽 own_methods; referenced 只抽**明确比较/继承**的; 若证据不足 own 也可为空
- **review_article**: own_methods **允许 []** ; referenced 只抽综述**明确描述具体技术方案**的
- **patent_analysis / non_storage**: 正常处理, 下游会单独标记

# taxonomy 上下文 (供你判定方法边界)
- primary_storage_domain: {primary_storage_domain}
- technology_subfield:    {technology_subfield}
- application_contexts:   {application_contexts}
- paper_type:             {paper_type}

# ⭐ 证据机制 (核心变化)

输入下面提供了**按句子 ID 索引的正文**, 每句形如:
   `- methods_p3_s2: 「本文采用溶胶-凝胶法制备 LiFePO4 正极材料。」`

规则:
- 每条 method 必须提供 `evidence_sentence_ids` 数组, **≥1 且 ≤3**
- 每个 ID **必须**是输入正文中**真实出现**的 sentence_id
- **禁止**编造不存在的 ID; 禁止修改 ID
- 优先引用**直接描述该方法**的句子; 次选相邻上下文句
- 若找不到能支持某方法的真实句 ID, **不要输出该方法**
- 无需复制原文 - 代码会用 ID 自动拼接原文证据

# 输出 Schema (严格 JSON 对象, 无 markdown 围栏)

{{
  "own_methods": [
    {{
      "name":                 "<辨识度强的方法名, 15-40 字>",
      "proposed_method_type": "<12 类枚举之一>",
      "problem_solved":       "<30-100 字, 解决什么核心问题>",
      "key_components":       ["<组件 1>", "<组件 2>"],
      "evidence_sentence_ids":["<真实 ID>", "..."],
      "citation_clue":        "",
      "confidence_llm":       "high | medium | low"
    }}
  ],
  "referenced_methods": [
    {{
      "name":                 "<被引用方法名>",
      "proposed_method_type": "<12 类枚举>",
      "problem_solved":       "<...>",
      "key_components":       ["..."],
      "evidence_sentence_ids":["<真实 ID>", "..."],
      "citation_clue":        "<参考文献编号/作者年份>",
      "confidence_llm":       "..."
    }}
  ]
}}

# 示例 (仅示范格式, 请勿把示例内容抄进结果)

## 例 1: 单句证据支持一条 own_method
假设正文含 `methods_p3_s2: 「本文采用溶胶-凝胶法制备了钙钛矿高熵氧化物 Cu 空位电极。」`, 则:
{{
  "own_methods": [
    {{
      "name": "溶胶-凝胶法制备钙钛矿高熵氧化物 Cu 空位电极",
      "proposed_method_type": "synthesis_process",
      "problem_solved": "在钙钛矿高熵结构中引入 Cu 空位以提升储锂比容量与倍率性能",
      "key_components": ["Cu 空位", "钙钛矿高熵氧化物", "溶胶-凝胶法"],
      "evidence_sentence_ids": ["methods_p3_s2"],
      "citation_clue": "",
      "confidence_llm": "high"
    }}
  ],
  "referenced_methods": []
}}

## 例 2: 相邻两句连续证据
若 `methods_p5_s1: 「BANERJEE 等将 rGO 与 Ni 掺杂的 MOF-5 复合。」` 与
    `methods_p5_s2: 「产物在 400°C 碳化 2 小时得到 rGO/Ni-MOC 电极。」`
连续出现且共同描述一个前人方法, 则:
{{
  "own_methods": [],
  "referenced_methods": [
    {{
      "name": "BANERJEE 等 rGO/Ni 掺杂 MOF-5 复合碳化电极",
      "proposed_method_type": "synthesis_process",
      "problem_solved": "构筑 rGO/MOF 复合前驱体后碳化得到高比容量电极",
      "key_components": ["rGO", "Ni 掺杂 MOF-5", "碳化"],
      "evidence_sentence_ids": ["methods_p5_s1", "methods_p5_s2"],
      "citation_clue": "BANERJEE 等",
      "confidence_llm": "medium"
    }}
  ]
}}

## 例 3: 只有宽泛描述时不输出
若只找得到 `introduction_p1_s3: 「MOFs 因高比表面积在储能领域受到广泛关注。」`,
这只是宽泛引言, 无具体技术方案 → **不输出**任何方法, 返回:
{{ "own_methods": [], "referenced_methods": [] }}

# 论文正文 (按句子 ID 索引)
<<<
{sentence_pack}
>>>

# 只输出符合上面 Schema 的 JSON 对象. 不要输出示例内容, 不要 markdown 围栏.
"""
