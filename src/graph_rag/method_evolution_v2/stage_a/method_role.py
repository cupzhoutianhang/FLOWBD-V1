"""method_role — 方法角色本地分类 (spec 一).

给每条 Stage A 抽出的方法附加 method_role, 不替代 method_type. 5 分类:

  - technology_solution: 材料 / 工艺 / 装置 / 系统 / 控制 等技术方案 (工程实现)
  - research_method: 实验设计 / 测试流程 / 测量方法 / 工况扫描方案
  - modeling_method: 数学模型 / 仿真模型 / 计算框架
  - analysis_method: 数据分析 / 评价方法 / 优化方法
  - unclear

优先级 (同时命中): modeling > technology > analysis > research > unclear

后续演化主图应优先使用 technology_solution 与 modeling_method;
research_method / analysis_method 保留但单独统计.
"""
from __future__ import annotations

import re


METHOD_ROLE_VERSION = "v1.1_modeling_triad_2026-07-02"


# ============================================================
# 关键词 (顺序: 先建模, 再工艺, 再分析, 再实验方法)
# ============================================================

# 强命名建模工艺: 出现即可判 modeling (无需三元组), 因它们自身已隐含
# 研究对象 + 建模动作 + 用途 (spec 二: 明确研究对象 + 建立动作 + 描述过程).
STRONG_MODELING_KEYWORDS = (
    "分子动力学", "MD 模拟", "MD模拟",
    "CFD", "有限元", "FEM",
    "第一性原理", "DFT",
    "多物理场耦合", "phase-field", "kinetic model",
    "机器学习模型",
)

# 建模目标词 (仅作三元组的"用途/载体"信号, 不能单独判 modeling)
MODELING_TARGETS = (
    "模型", "仿真", "模拟", "计算框架",
    "数学模型", "仿真模型", "计算模型",
    "传热模型", "流动模型", "反应模型",
    "热力学模型", "动力学模型",
    "数值模拟", "数值模型", "数值方法",
)

# 建模动作动词 (spec 二: 建立/构建/提出/耦合/求解 等)
BUILD_VERBS = (
    "建立", "构建", "构造", "提出", "开发",
    "耦合", "求解", "推导", "拟合", "标定",
    "编制", "编写",
)

# 兼容旧 API: MODELING_KEYWORDS 保留 (作为兼容变量供其他模块使用)
MODELING_KEYWORDS = STRONG_MODELING_KEYWORDS

TECHNOLOGY_KEYWORDS = (
    # 材料 / 工艺
    "制备", "合成", "改性", "掺杂", "复合材料",
    "涂层", "阵列", "结构设计", "沉积",
    "共沉淀", "水热", "溶胶-凝胶", "溶胶凝胶", "微乳",
    "球磨", "煅烧", "退火", "碳化",
    # 装置 / 系统 / 控制
    "装置", "系统", "反应器", "膜组件", "电堆",
    "电池包", "电解池", "换热器", "冷却器", "热管理",
    "液冷", "风冷", "直冷", "自建装置",
    "控制策略", "系统集成", "系统架构",
    "隔膜", "电极", "电解液",
)

ANALYSIS_KEYWORDS = (
    "评价方法", "评价指标", "评价体系",
    "优化方法", "参数优化", "响应面", "响应面法",
    "遗传算法", "粒子群", "多目标优化",
    "数据分析", "统计分析", "回归分析", "灰关联",
    "敏感性分析", "灵敏度分析",
    "拟合", "曲线拟合",
    "经济性分析", "全生命周期", "LCA",
    "熵产分析", "㶲分析", "能效评价",
)

RESEARCH_METHOD_KEYWORDS = (
    "实验设计", "工况扫描", "工况研究", "参数扫描",
    "变工况", "温度扫描", "压力扫描", "流量扫描",
    "循环测试", "加载方案", "步进",
    "测试流程", "测试方法", "测量方法",
    "实验方案", "研究方案", "工况方案",
    "实验流程", "耦合实验",
)

# 出现即强烈指示 research_method, 优先于 technology 的模糊信号 (装置/系统).
_STRONG_RESEARCH_MARKERS = (
    "工况扫描", "工况研究", "工况方案", "变工况",
    "温度扫描", "压力扫描", "流量扫描",
    "测试流程", "测试方案", "实验方案", "实验流程",
    "研究方案", "参数扫描",
)


def _matches(keywords, text):
    return any(k in text for k in keywords)


def _modeling_triad_ok(text: str) -> bool:
    """spec 二: modeling_method 判定需要三元同时命中.

    - 强命名工艺 (CFD/有限元/分子动力学 等) 直接 True (自身含全部语义)
    - 否则需要: 建模动作动词 + 建模目标词 同时命中
      (研究对象在 problem_solved / name 里通常已存在, 若也需要显式判定
       可再收紧, 目前信任 build_verb + target 组合足以排除 "分析模型" 类)
    """
    if _matches(STRONG_MODELING_KEYWORDS, text):
        return True
    has_verb = _matches(BUILD_VERBS, text)
    has_target = _matches(MODELING_TARGETS, text)
    return has_verb and has_target


def assign_method_role(method: dict) -> str:
    """基于 name + problem_solved + evidence text 命中关键词.

    Args:
      method: 已经过 evidence_validation 处理的 method dict.
              需含 name / problem_solved / evidence_text (可缺, 视为空).

    Returns:
      one of 'technology_solution', 'research_method', 'modeling_method',
             'analysis_method', 'unclear'.
    """
    name = (method.get("name") or method.get("method_name") or "")
    problem = (method.get("problem_solved") or "")
    evidence = (method.get("evidence_text") or "")
    method_type = (method.get("proposed_method_type") or "").lower()

    # 用 name + problem 判角色 (evidence 太杂, 只做补充信号)
    text_primary = f"{name} {problem}"
    text_full = f"{text_primary} {evidence}"

    # method_type 是 LLM 给的类型, 用作先验 (需要满足三元组 or 强关键词)
    if method_type in ("simulation_model", "model", "mathematical_model",
                          "modeling", "simulation", "cfd_model",
                          "model_simulation"):
        if _modeling_triad_ok(text_full):
            return "modeling_method"
        # LLM 说是模型但三元组不齐 → unclear (保守; 避免"分析模型"孤立词误升)

    # 1. modeling (name+problem 上判定三元组)
    if _modeling_triad_ok(text_primary):
        return "modeling_method"

    # 1b. 强 research 标记 (工况扫描/测试流程等) 优先于 technology
    if _matches(_STRONG_RESEARCH_MARKERS, text_primary):
        return "research_method"

    # 2. technology
    if _matches(TECHNOLOGY_KEYWORDS, text_primary):
        return "technology_solution"

    # 3. analysis
    if _matches(ANALYSIS_KEYWORDS, text_primary):
        return "analysis_method"

    # 4. research method (弱标记)
    if _matches(RESEARCH_METHOD_KEYWORDS, text_primary):
        return "research_method"

    # 5. evidence 补充命中 (name/problem 都不含时才看 evidence)
    if _modeling_triad_ok(evidence):
        return "modeling_method"
    if _matches(TECHNOLOGY_KEYWORDS, evidence):
        return "technology_solution"
    if _matches(ANALYSIS_KEYWORDS, evidence):
        return "analysis_method"
    if _matches(RESEARCH_METHOD_KEYWORDS, evidence):
        return "research_method"

    return "unclear"


def attach_method_role(method: dict) -> dict:
    """把 method_role 写回 method dict (返回原对象; 原地修改)."""
    method["method_role"] = assign_method_role(method)
    method["method_role_version"] = METHOD_ROLE_VERSION
    return method
