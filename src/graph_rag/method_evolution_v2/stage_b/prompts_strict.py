"""Stage B v2 (strict) prompts.

对上一轮的修正:
  - 抽取器: 默认 NO_RELATION, 加负例, 明确"依次介绍不是演化"等
  - 审查器: 加 linkage_type (independent_methods / whole_component / duplicate_or_alias / other)
           + endpoint_linkage (explicit_both / adjacent_coreference / ambiguous)
           + coreference_explanation
  - 审查器仍不看抽取器的 relation_reason / confidence_llm
"""
from __future__ import annotations


# ============================================================
# EXTRACTOR (Stage B.1 strict)
# ============================================================

EXTRACTOR_SYSTEM_STRICT = (
    "你是储能领域方法演化分析专家。任务是**判定两个方法之间是否存在**"
    "4 类演化关系。**默认答案是 NO_RELATION** —— 只有原文有明确直接的关系证据句时"
    "才能输出关系, 且必须给出真实的证据 sentence_id。严格按 JSON 对象返回, 不带 markdown 围栏。"
)


EXTRACTOR_USER_TEMPLATE_STRICT = """# 任务
针对下面给出的**候选方法对**, 逐对判定它们之间是否存在下列关系之一:

1. **EXTENDS**   — 后方法**保留前方法主框架**, 且**明确原文写出**新增模块/材料/机制/步骤/适用范围
2. **IMPROVES**  — 两方法**解决同一具体问题**, 原文**直接对比**并给出性能/参数/稳定性/效率/成本/缺陷优化
3. **ADAPTS**    — 原文明确指出**从其他领域/材料体系/应用场景迁移**
4. **REPLACES**  — 原文明确出现**替代/淘汰/避免/克服局限**等替换语义

# ⛔ 硬性禁令 - 出现下列情况必须输出 NO_RELATION

1. 同一综述**依次介绍**两个方法 → 只是并列, 不是演化
2. **性能数字不同**但原文没有直接比较 → 不代表 IMPROVES
3. **材料或配方不同**但原文没有明确"改进/扩展"表述 → 不代表 EXTENDS
4. **发表时间先后**但无文本关联 → 不代表演化
5. 两方法只是**语义相似**或使用**相同材料** → 不是关系
6. 只有 "**可能是在此基础上**" 之类推测 → NO_RELATION
7. 两方法**其中一个是另一个的组成模块** (整体 vs 子系统 / 材料 vs 制备步骤 / 系统 vs 换热器)
   → **NO_RELATION** (标注 note="whole_component" 以便审查)
8. 两方法**实际描述同一技术** (只是名称长短不同, 或后者是前者的更具体命名)
   → **NO_RELATION** (标注 note="duplicate_or_alias")
9. **不为凑候选对而强行给关系** —— 大部分候选对的正确答案是 NO_RELATION

# 关系方向 (硬性)
- from_method_id: **后**出现 / 改进 / 扩展 / 迁移后 / 替代者
- to_method_id:   被改进 / 被扩展 / 被借鉴 / 被替代的**旧**方法
- 方向从原文无法确定 → **NO_RELATION**

# 证据句 ID 规则
- 每条关系必须给 `relation_evidence_sentence_ids`(1-3 个); NO_RELATION 时留空数组
- 每个 ID **必须**是输入正文中真实存在的 sentence_id
- **证据句必须**明确表达两方法的**连接/比较/继承/迁移/替代**
- 只是分别介绍两方法的孤立句**不算连接证据**
- 找不到 → NO_RELATION

# 论文信息
- paper_id: {paper_id}
- canonical_title: {canonical_title}
- paper_type: {paper_type}
- primary_storage_domain: {primary_storage_domain}
- technology_subfield: {technology_subfield}

# 候选方法对
{pair_list}

# 供检索的证据句索引
{sentence_pack}

# 输出 Schema (严格 JSON, 无 markdown 围栏)

{{
  "relations": [
    {{
      "pair_id":                        "<对应 pair_id>",
      "verdict":                        "EXTENDS | IMPROVES | ADAPTS | REPLACES | NO_RELATION",
      "from_method_id":                 "<verdict != NO_RELATION 时必填>",
      "to_method_id":                   "<verdict != NO_RELATION 时必填>",
      "relation_evidence_sentence_ids": ["<真实 sid>", "..."],
      "note":                           "whole_component | duplicate_or_alias | \\"\\"",
      "direction_basis":                "<30-80 字>",
      "relation_reason":                "<50-120 字>",
      "confidence_llm":                 "high | medium | low"
    }}
  ]
}}

# 强制要求
- 对**每一个** pair_id 都必须输出**一条**结果 (verdict=NO_RELATION 也算一条)
- 输出的 pair_id 集合 = 输入的 pair_id 集合 (不多不少)
- 保守优先: **拿不准就 NO_RELATION**
"""


# ============================================================
# AUDITOR (Stage B.2 strict) - 保持独立, 不看 relation_reason/confidence
# 增加: linkage_type + endpoint_linkage + coreference_explanation
# ============================================================

AUDITOR_SYSTEM_STRICT = (
    "你是储能领域方法演化关系的**独立审查专家**。"
    "任务是**独立判断**别人提议的关系是否成立, 不受 '置信度/理由' 影响。"
    "先看两方法**是不是独立的两个方法** (不能是整体-子模块或同义重复), "
    "再看证据是否能锚定两者之间的**演化关系**, 再看方向和类型。"
    "严格 JSON 对象返回, 不带 markdown 围栏。"
)


AUDITOR_USER_TEMPLATE_STRICT = """# 审查任务

请对每一条提议**独立**判断以下 5 个字段:

## 1) linkage_type — 两个方法是不是独立的两个方法?

- `independent_methods`     — 两方法确实是独立的技术方案, 可能有演化关系
- `whole_component`         — 一方是另一方的**组成模块**/子系统/子流程/元件; 例:
                              系统 vs 该系统内的换热器 / 蓄冷流程 / 优化模块;
                              材料体系 vs 该材料的制备步骤
- `duplicate_or_alias`      — 两方法实际是**同一技术**, 只是名字不同或后者是前者的具体命名
- `other`                   — 别的情况 (混合类型/无法判)

## 2) endpoint_linkage — 关系证据里两个方法是否被**明确点名**?

- `explicit_both`           — 证据句直接出现**两个方法名或明确别名**
- `adjacent_coreference`    — 一句提到 from, 相邻句提到 to, 且有明确指代词衔接(如 "基于此" 指向前一句已明说的方法)
- `ambiguous`               — 只能靠远距离上下文/主观推断确定指代, 无明确指代链

## 3) support / 4) direction / 5) relation_check

- support:        supported / weak / unsupported
- direction:      correct / reversed / unclear
- relation_check: correct / wrong_type / unclear

## 关系定义

1. **EXTENDS**  — 后方法保留主框架 + 新增模块/材料/机制/步骤/适用范围
2. **IMPROVES** — 同一具体问题, 后方针对性能/参数/稳定性/效率/成本/缺陷优化
3. **ADAPTS**   — 明确从其他领域/体系/场景迁移
4. **REPLACES** — 明确替代 (含避免/克服局限/淘汰语义)

## 硬性方向
- from: 后 / 改进 / 扩展 / 迁移后 / 替代者
- to:   被改 / 被扩展 / 被借鉴 / 被替代者

## 若干拒绝提示 (不影响你独立判断, 仅提醒常见坑)
- 综述里依次介绍 ≠ 演化
- 性能数字不同 + 无直接对比 ≠ IMPROVES
- 材料不同 + 无 "改进 / 扩展" 表述 ≠ EXTENDS
- 时间先后 + 无文本关联 ≠ 演化
- "基于此/进一步" 若没有清晰指代到 to 方法 → endpoint_linkage=ambiguous
- 一方是另一方的子模块 → linkage_type=whole_component

# 待审查的关系列表 (最多 {batch_size} 条)

{proposal_list}

# 输出 Schema (严格 JSON, 无 markdown 围栏)

{{
  "audits": [
    {{
      "pair_id":                 "<对应 pair_id>",
      "linkage_type":            "independent_methods | whole_component | duplicate_or_alias | other",
      "endpoint_linkage":        "explicit_both | adjacent_coreference | ambiguous",
      "coreference_explanation": "<50-120 字, 说明为什么 endpoint_linkage 是这个值; 或整体-组件说明>",
      "support":                 "supported | weak | unsupported",
      "direction":               "correct | reversed | unclear",
      "relation_check":          "correct | wrong_type | unclear",
      "suggested_relation":      "EXTENDS | IMPROVES | ADAPTS | REPLACES | NONE | \\"\\"",
      "audit_reason":            "<30-100 字, 总体判定依据>"
    }}
  ]
}}

# 强制要求
- 输出必须覆盖输入的**每一个** pair_id (顺序不限)
- 只输出 audits 字段, 不输出其他字段
"""
