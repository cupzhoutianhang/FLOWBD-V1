"""Stage B 两阶段 prompts (spec 六).

第一步 EXTRACTOR: 从候选对中提出关系 + 证据句 ID.
第二步 AUDITOR:   独立审查, 不看 extractor 的 relation_reason / confidence_llm.
两步同一模型 (moonshot-v1-auto), 但 prompt 明显不同.
"""
from __future__ import annotations


# ============================================================
# EXTRACTOR (Stage B.1)
# ============================================================

EXTRACTOR_SYSTEM = (
    "你是储能领域的方法演化分析专家。任务是**判定两个方法之间**"
    "是否存在 4 类演化关系之一, 并给出**原文证据句 ID**。"
    "必须严格按 JSON 对象返回, 不能有任何 markdown 围栏或额外说明。"
)


EXTRACTOR_USER_TEMPLATE = """# 任务
针对下面给出的**候选方法对**列表, 逐对判定它们之间是否存在下列 4 类关系之一:

1. **EXTENDS**  — 后出现的方法**保留前方法主框架, 并新增模块/材料/机制/步骤/适用范围**
2. **IMPROVES** — 两方法**解决同一问题**, 后出现的针对性能/参数/稳定性/效率/成本/缺陷做**优化**
3. **ADAPTS**   — 把**其他领域/材料体系/应用场景**的方法**迁移**到当前领域
4. **REPLACES** — 用**不同技术路线**替代旧方法, 且原文含**替代/避免/克服局限/淘汰**等语义

**方向规则** (硬性):
- from_method_id: **后**出现 / 改进 / 扩展 / 迁移后 / 替代者
- to_method_id: 被改进 / 被扩展 / 被借鉴 / 被替代的**旧**方法
- 方向从原文无法确定 → **不输出**这条关系 (宁空不错)

**禁止**推断为关系 (spec 三):
- 只是语义相似 / 使用相同材料 / 在同一综述里 / 只是发表时间前后
- 性能数字不同但原文没直接比较
- "可能是在此基础上" 类推测
- 只有各自的证据句, 没有连接两者的证据句

# 证据句 ID 规则 (spec 四, 与 Stage A 同款)
- 每条关系必须给出 `relation_evidence_sentence_ids`, **1-3 个** ID
- 每个 ID 必须来自输入正文中真实出现的 sentence_id
- **禁止编造 ID, 禁止修改 ID**
- **证据句必须**表达两个方法之间的**连接/比较/继承/迁移/替代**
- 只是分别介绍两个方法的孤立句不算连接证据
- 找不到连接证据 → **不输出该关系**

# 论文信息
- paper_id: {paper_id}
- canonical_title: {canonical_title}
- paper_type: {paper_type}
- primary_storage_domain: {primary_storage_domain}
- technology_subfield: {technology_subfield}

# 候选方法对 (你只对这些 pair_id 做判定)
{pair_list}

# 供检索的证据句索引 (只列出与候选方法段落 / 触发词覆盖范围相关的句子)
{sentence_pack}

# 输出 Schema (严格 JSON 对象, 无 markdown 围栏)

{{
  "relations": [
    {{
      "pair_id":                        "<对应 pair_id, 如 'P003'>",
      "from_method_id":                 "<后出现/改进/扩展/迁移后/替代者的 method_id>",
      "to_method_id":                   "<被改进/被扩展/被借鉴/被替代者的 method_id>",
      "relation":                       "EXTENDS | IMPROVES | ADAPTS | REPLACES",
      "relation_evidence_sentence_ids": ["<真实 sid>", "..."],
      "direction_basis":                "<30-80 字, 说明为什么方向是 from → to>",
      "relation_reason":                "<50-120 字, 说明为什么是这种关系>",
      "confidence_llm":                 "high | medium | low"
    }}
  ]
}}

# 注意
- pair_id 必须来自上面候选对列表, 不能新增
- 每个 pair 最多输出 1 条关系; 找不到就跳过
- 不输出 relations 字段以外的任何字段
- 输出**允许 relations 为空数组**
"""


# ============================================================
# AUDITOR (Stage B.2) - blind to extractor's reason/confidence
# ============================================================

AUDITOR_SYSTEM = (
    "你是储能领域的方法演化关系**独立审查专家**。"
    "任务是**独立判断**别人提议的关系是否成立, 不受任何'置信度/理由'先入影响。"
    "必须严格按 JSON 对象返回, 不能有任何 markdown 围栏或额外说明。"
)


AUDITOR_USER_TEMPLATE = """# 审查任务

下面列出一批**已被提议**的方法关系. 请对每一条**独立**判断:
1. **support**: 证据句是否真正支持该关系?
   - supported: 证据句明确表达两方法的关系
   - weak: 证据句相关但支撑力弱, 需人工二审
   - unsupported: 证据句无法支持, 或只是分别提及两方法
2. **direction**: from → to 的方向是否正确?
   - correct: 方向对
   - reversed: 方向反了 (应对调)
   - unclear: 从证据无法判方向
3. **relation_check**: 关系类型是否正确?
   - correct: 类型对
   - wrong_type: 应为其他 3 类之一 → 请填 suggested_relation
   - unclear: 说不清
4. **suggested_relation**: 若 relation_check!=correct, 建议的关系(EXTENDS/IMPROVES/ADAPTS/REPLACES/NONE); 否则填 ""

# 关系定义 (与提议者同款; 不接受额外类型)

1. **EXTENDS**  — 后方法**保留主框架 + 新增模块/材料/机制/步骤/适用范围**
2. **IMPROVES** — 两方法**同一问题**, 后方针对性能/参数/稳定性/效率/成本/缺陷**优化**
3. **ADAPTS**   — 把**其他领域**方法**迁移**到当前领域
4. **REPLACES** — 用**不同技术路线**替代, 且原文含**替代/避免/克服局限/淘汰**语义

**方向硬规则**:
- from_method: 后出现 / 改进 / 扩展 / 迁移后 / 替代者
- to_method:   被改进 / 被扩展 / 被借鉴 / 被替代者

**否定条件** (下列都不成立):
- 只是语义相似, 或只用同种材料
- 只是发表时间先后 (无比较原文)
- 性能数字不同但原文没直接对比
- 只有各方法各自的介绍句, 无连接证据句

# 待审查的关系列表

{proposal_list}

# 输出 Schema (严格 JSON 对象, 无 markdown 围栏)

{{
  "audits": [
    {{
      "pair_id":            "<对应 pair_id>",
      "support":            "supported | weak | unsupported",
      "direction":          "correct | reversed | unclear",
      "relation_check":     "correct | wrong_type | unclear",
      "suggested_relation": "EXTENDS | IMPROVES | ADAPTS | REPLACES | NONE | \\"\\"",
      "audit_reason":       "<30-100 字, 说明判定的依据>"
    }}
  ]
}}

# 注意
- 不要看提议者的 relation_reason 或 confidence — 只看证据句和关系定义
- 对每个 pair_id 都要给一条审查结果
- 输出**至少覆盖**所有输入 pair_id
"""
