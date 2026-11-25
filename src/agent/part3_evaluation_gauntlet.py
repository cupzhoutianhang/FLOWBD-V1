"""
Part 3: The Multi-Dimensional Evaluation Gauntlet - 多维度评估系统

实现5维度的性能评估框架：
1. Domain Accuracy (领域准确性) - 基于知识库内容的准确性
2. Knowledge Graph Utilization (知识图谱利用度) - 图谱关系使用程度
3. Source Attribution (来源归属) - 回答的来源追踪能力
4. Coherence & Consistency (一致性和连贯性) - 答案的逻辑一致性
5. Operational Efficiency (操作效率) - 执行时间和资源使用

"""

import json
import re
import os
import sys
import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import time

# 此文件位于 src/agent/graphrag_and_rag/agent/ 目录
# 不需要重新配置 sys.path（已由 run_part5_enhanced.py 配置）

from agent.part1_knowledge_arsenal import LLMConfig
from agent.part2_guild_system import GuildState, SpecialistFinding

logger = logging.getLogger(__name__)


# ============================================================================
# Part 3.1: 评分数据结构
# ============================================================================

@dataclass
class DimensionScore:
    """单个维度的评分"""
    dimension_name: str
    score: float  # 0.0-1.0
    reasoning: str
    evidence: List[str] = field(default_factory=list)
    weight: float = 1.0  # 权重因子
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class EvaluationResult:
    """完整的评估结果 - 5维度向量"""
    request_id: str
    accuracy: DimensionScore
    graph_utilization: DimensionScore
    source_attribution: DimensionScore
    coherence: DimensionScore
    efficiency: DimensionScore
    
    # 聚合指标
    overall_score: float = 0.0
    evaluation_timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def calculate_overall_score(self) -> float:
        """计算加权综合评分"""
        scores = [
            self.accuracy.score * self.accuracy.weight,
            self.graph_utilization.score * self.graph_utilization.weight,
            self.source_attribution.score * self.source_attribution.weight,
            self.coherence.score * self.coherence.weight,
            self.efficiency.score * self.efficiency.weight,
        ]
        total_weight = (
            self.accuracy.weight +
            self.graph_utilization.weight +
            self.source_attribution.weight +
            self.coherence.weight +
            self.efficiency.weight
        )
        self.overall_score = sum(scores) / total_weight if total_weight > 0 else 0.0
        return self.overall_score
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "request_id": self.request_id,
            "dimensions": {
                "accuracy": {"score": self.accuracy.score, "reasoning": self.accuracy.reasoning},
                "graph_utilization": {"score": self.graph_utilization.score, "reasoning": self.graph_utilization.reasoning},
                "source_attribution": {"score": self.source_attribution.score, "reasoning": self.source_attribution.reasoning},
                "coherence": {"score": self.coherence.score, "reasoning": self.coherence.reasoning},
                "efficiency": {"score": self.efficiency.score, "reasoning": self.efficiency.reasoning},
            },
            "overall_score": self.overall_score,
            "timestamp": self.evaluation_timestamp
        }


# ============================================================================
# Part 3.2: 多维度评估器
# ============================================================================

class DomainAccuracyEvaluator:
    """
    维度1: 领域准确性评估
    
    评估回答是否与知识库中的内容一致，是否有事实错误
    """
    
    def __init__(self, llm_config: LLMConfig):
        """初始化准确性评估器"""
        self.llm = llm_config
        logger.info("✓ Domain Accuracy Evaluator 初始化")
    
    def evaluate(self, answer: str, specialist_findings: List[SpecialistFinding]) -> DimensionScore:
        """评估领域准确性"""
        logger.info("🎯 [Accuracy] 评估答案的领域准确性...")
        
        # 收集所有来源信息
        sources_context = ""
        for finding in specialist_findings:
            if finding.agent_name == "Researcher":
                sources_context += f"\n【检索到的信息】\n{finding.findings[:1000]}\n"
        
        prompt = f"""你是一个液流电池/电化学领域的专家。请评估以下答案与提供的知识库内容的一致性。

【用户的答案】
{answer}

【知识库信息】
{sources_context}

请评分（0.0-1.0），其中：
- 1.0：答案完全准确，与知识库信息一致
- 0.7-0.9：答案大多正确，有个别小错误或不完整
- 0.4-0.6：答案有一些不准确的地方
- 0.0-0.3：答案包含明显错误或与知识库矛盾

仅返回JSON，格式为：
{{
    "score": 0.0-1.0,
    "reasoning": "评分原因"
}}"""
        
        try:
            response = self.llm.call_llm(prompt, temperature=0.0, max_tokens=500)
            
            # 清理和解析
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            
            # 清理无效的控制字符
            response = response.strip()
            response = ''.join(char for char in response if ord(char) >= 32 or char in '\n\r\t')
            
            data = json.loads(response.strip())
            score = min(1.0, max(0.0, float(data.get("score", 0.5))))
            reasoning = data.get("reasoning", "无法评估")
            
            logger.info(f"  ✓ 准确性评分: {score:.2f}")
            
            return DimensionScore(
                dimension_name="Domain Accuracy",
                score=score,
                reasoning=reasoning,
                evidence=[sources_context[:500]],
                weight=1.2  # 准确性权重较高
            )
            
        except Exception as e:
            logger.warning(f"  ⚠️ 评估失败: {e}")
            return DimensionScore(
                dimension_name="Domain Accuracy",
                score=0.5,
                reasoning=f"评估失败（使用默认分数）",
                weight=1.2
            )


class GraphUtilizationEvaluator:
    """
    维度2: 知识图谱利用度评估
    
    评估回答中是否利用了知识图谱的关系和结构
    """
    
    def evaluate(self, answer: str, specialist_findings: List[SpecialistFinding]) -> DimensionScore:
        """评估知识图谱利用程度"""
        logger.info("🔗 [Graph] 评估知识图谱的利用程度...")
        
        # 检查是否有GraphExplorer的输出
        graph_findings = [f for f in specialist_findings if f.agent_name == "GraphExplorer"]
        
        if not graph_findings:
            logger.info("  ℹ️ 未使用GraphExplorer Agent")
            return DimensionScore(
                dimension_name="Graph Utilization",
                score=0.3,
                reasoning="未从知识图谱中检索信息",
                weight=1.0
            )
        
        graph_content = graph_findings[0].findings if graph_findings else ""
        
        # 简单的启发式评估：检查答案中是否引用了实体关系
        keywords = ["关系", "相关", "结构", "连接", "相互作用", "组成", "包含"]
        keyword_count = sum(1 for kw in keywords if kw in answer.lower())
        
        # 检查是否提到了多个相关概念
        concept_references = len(re.findall(r'[\u4e00-\u9fff]+', answer))
        
        score = min(1.0, (keyword_count / 3 + min(concept_references / 50, 1.0)) / 2)
        
        reasoning = f"答案中包含 {keyword_count} 个关系相关的关键词，提及 {concept_references} 个概念"
        
        logger.info(f"  ✓ 图谱利用度: {score:.2f}")
        
        return DimensionScore(
            dimension_name="Graph Utilization",
            score=score,
            reasoning=reasoning,
            evidence=[graph_content[:500]] if graph_content else [],
            weight=1.0
        )


class SourceAttributionEvaluator:
    """
    维度3: 答案完整性评估
    
    评估答案是否包含缺失信息的表述（改造为缺失信息检测）
    当答案中有「缺失」、「未找到」、「暂无」等表述时，评分较低
    这样可以驱动SOP变异方案扩大秘塔搜索来改进答案
    """
    
    def evaluate(self, answer: str, specialist_findings: List[SpecialistFinding]) -> DimensionScore:
        """评估答案的完整性（是否包含缺失信息）"""
        logger.info("📚 [Completeness] 评估答案的完整性（是否缺失信息）...")
        
        # 缺失信息的关键词
        missing_keywords = [
            '缺失', '缺少', '未找到', '暂无', '信息不足',
            'missing', 'not found', 'no information', 'insufficient',
            '没有找到', '无相关', '无法获取', '未发现',
            '信息有限', '资料有限', '资源有限',
            '找不到', '不清楚', '不明确', '无法确定'
        ]
        
        # 统计答案中缺失信息的出现次数
        answer_lower = answer.lower()
        missing_count = sum(1 for keyword in missing_keywords if keyword in answer_lower)
        
        # 答案总长度
        answer_length = len(answer)
        
        # 缺失信息的比例（缺失信息出现次数 / 答案长度）
        if missing_count == 0:
            # 没有缺失信息表述 → 答案完整 → 评分高（0.9-1.0）
            score = 0.95
            reasoning = "答案完整，未检测到缺失信息的表述"
        elif missing_count == 1:
            # 有1处缺失信息表述 → 答案基本完整，部分信息不足 → 评分中等（0.6-0.7）
            score = 0.65
            reasoning = f"答案中检测到1处缺失信息表述，存在部分信息不足"
        elif missing_count <= 3:
            # 有2-3处缺失信息表述 → 答案信息不足 → 评分较低（0.4-0.5）
            score = 0.45
            reasoning = f"答案中检测到{missing_count}处缺失信息表述，多个方面信息不足"
        else:
            # 有4处及以上缺失信息表述 → 答案严重不完整 → 评分很低（0.2-0.3）
            score = 0.25
            reasoning = f"答案中检测到{missing_count}处缺失信息表述，信息严重不足，需要扩大搜索范围"
        
        logger.info(f"  ✓ 答案完整性评分: {score:.2f} (缺失{missing_count}处)")
        
        return DimensionScore(
            dimension_name="Answer Completeness",
            score=score,
            reasoning=reasoning,
            evidence=[f"缺失信息出现次数: {missing_count}"],
            weight=0.9  # 权重保持为0.9，用于Pareto分析
        )


class CoherenceEvaluator:
    """
    维度4: 连贯性与一致性评估
    
    评估答案的逻辑是否连贯，是否有矛盾
    """
    
    def __init__(self, llm_config: LLMConfig):
        """初始化连贯性评估器"""
        self.llm = llm_config
        logger.info("✓ Coherence Evaluator 初始化")
    
    def evaluate(self, answer: str) -> DimensionScore:
        """评估连贯性和一致性"""
        logger.info("🔀 [Coherence] 评估答案的连贯性...")
        
        prompt = f"""请评估以下答案的逻辑连贯性和内部一致性。

【答案】
{answer}

评分标准（0.0-1.0）：
- 1.0：逻辑清晰，层次分明，无矛盾
- 0.7-0.9：大体连贯，有小的逻辑跳跃
- 0.4-0.6：有一些逻辑不清或局部矛盾
- 0.0-0.3：逻辑混乱或存在明显矛盾

仅返回JSON：
{{
    "score": 0.0-1.0,
    "reasoning": "评分原因"
}}"""
        
        try:
            response = self.llm.call_llm(prompt, temperature=0.0, max_tokens=400)
            
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            
            # 清理无效的控制字符
            response = response.strip()
            # 移除非法的控制字符（0-31范围，除了常见的\n\r\t）
            response = ''.join(char for char in response if ord(char) >= 32 or char in '\n\r\t')
            
            data = json.loads(response.strip())
            score = min(1.0, max(0.0, float(data.get("score", 0.6))))
            reasoning = data.get("reasoning", "无法评估")
            
            logger.info(f"  ✓ 连贯性评分: {score:.2f}")
            
            return DimensionScore(
                dimension_name="Coherence",
                score=score,
                reasoning=reasoning,
                weight=1.1
            )
            
        except Exception as e:
            logger.warning(f"  ⚠️ 评估失败: {e}")
            return DimensionScore(
                dimension_name="Coherence",
                score=0.6,
                reasoning=f"评估失败（使用默认分数）",
                weight=1.1
            )


class OperationalEfficiencyEvaluator:
    """
    维度5: 操作效率评估
    
    评估Guild执行的效率（时间、资源使用）
    """
    
    def evaluate(self, specialist_findings: List[SpecialistFinding]) -> DimensionScore:
        """评估操作效率"""
        logger.info("⚡ [Efficiency] 评估系统操作效率...")
        
        # 统计执行时间
        total_time = sum(getattr(f, 'execution_time', 0.0) for f in specialist_findings)
        count = len([f for f in specialist_findings if getattr(f, 'execution_time', 0.0) > 0])
        
        avg_time = total_time / count if count > 0 else 0
        
        # 理想范围：3-5秒
        # 0-3秒：非常快 (1.0)
        # 3-5秒：很好 (0.9)
        # 5-10秒：正常 (0.7)
        # 10-20秒：较慢 (0.4)
        # 20秒以上：很慢 (0.2)
        
        if avg_time <= 3:
            score = 1.0
            status = "非常高效"
        elif avg_time <= 5:
            score = 0.9
            status = "高效"
        elif avg_time <= 10:
            score = 0.7
            status = "正常"
        elif avg_time <= 20:
            score = 0.4
            status = "较慢"
        else:
            score = 0.2
            status = "很慢"
        
        reasoning = f"总执行时间: {total_time:.2f}秒，平均: {avg_time:.2f}秒/任务，评估: {status}"
        
        logger.info(f"  ✓ 操作效率: {score:.2f} ({status})")
        
        return DimensionScore(
            dimension_name="Operational Efficiency",
            score=score,
            reasoning=reasoning,
            evidence=[f"总时间: {total_time:.2f}s", f"任务数: {count}"],
            weight=0.7  # 效率权重较低
        )


# ============================================================================
# Part 3.3: 评估Gauntlet主协调器
# ============================================================================

class EvaluationGauntlet:
    """
    多维度评估Gauntlet - 完整的5维度评估系统
    
    对应 code.ipynb 中的 EvaluationResult，但优化为5维度
    """
    
    def __init__(self, llm_config: LLMConfig):
        """初始化评估Gauntlet"""
        self.llm = llm_config
        
        # 初始化各维度评估器
        self.accuracy_evaluator = DomainAccuracyEvaluator(llm_config)
        self.graph_evaluator = GraphUtilizationEvaluator()
        self.source_evaluator = SourceAttributionEvaluator()
        self.coherence_evaluator = CoherenceEvaluator(llm_config)
        self.efficiency_evaluator = OperationalEfficiencyEvaluator()
        
        logger.info("✓ Evaluation Gauntlet 初始化完成")
    
    def evaluate(self, state: GuildState) -> EvaluationResult:
        """
        执行完整的5维度评估
        
        返回 EvaluationResult，包含所有维度的评分
        """
        
        logger.info("=" * 60)
        logger.info("🎯 执行多维度评估 Gauntlet")
        logger.info("=" * 60)
        
        # 准备数据
        answer = state.final_synthesis or ""
        specialist_findings = state.specialist_outputs
        
        # 执行5个维度的评估
        logger.info("\n📊 评估维度 1/5: 领域准确性...")
        accuracy = self.accuracy_evaluator.evaluate(answer, specialist_findings)
        
        logger.info("📊 评估维度 2/5: 知识图谱利用度...")
        graph = self.graph_evaluator.evaluate(answer, specialist_findings)
        
        logger.info("📊 评估维度 3/5: 来源归属...")
        sources = self.source_evaluator.evaluate(answer, specialist_findings)
        
        logger.info("📊 评估维度 4/5: 连贯性与一致性...")
        coherence = self.coherence_evaluator.evaluate(answer)
        
        logger.info("📊 评估维度 5/5: 操作效率...")
        efficiency = self.efficiency_evaluator.evaluate(specialist_findings)
        
        # 创建评估结果
        result = EvaluationResult(
            request_id=state.request_id,
            accuracy=accuracy,
            graph_utilization=graph,
            source_attribution=sources,
            coherence=coherence,
            efficiency=efficiency
        )
        
        # 计算综合评分
        overall = result.calculate_overall_score()
        
        logger.info("\n" + "=" * 60)
        logger.info("📈 评估结果汇总")
        logger.info("=" * 60)
        logger.info(f"  领域准确性:        {accuracy.score:.2f}/1.0")
        logger.info(f"  知识图谱利用度:    {graph.score:.2f}/1.0")
        logger.info(f"  来源归属:          {sources.score:.2f}/1.0")
        logger.info(f"  连贯性与一致性:    {coherence.score:.2f}/1.0")
        logger.info(f"  操作效率:          {efficiency.score:.2f}/1.0")
        logger.info(f"  \n综合评分:           {overall:.2f}/1.0")
        logger.info("=" * 60)
        
        return result


if __name__ == "__main__":
    logger.info("=" * 80)
    logger.info("Part 3: Evaluation Gauntlet - 多维度评估系统")
    logger.info("=" * 80)
    
    print("\n✓ Part 3 多维度评估系统已定义")
    print("  - DomainAccuracyEvaluator: 领域准确性")
    print("  - GraphUtilizationEvaluator: 知识图谱利用度")
    print("  - SourceAttributionEvaluator: 来源归属")
    print("  - CoherenceEvaluator: 连贯性与一致性")
    print("  - OperationalEfficiencyEvaluator: 操作效率")
    print("  - EvaluationGauntlet: 主协调器")
