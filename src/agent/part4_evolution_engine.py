"""
Part 4: The Outer Loop - AI Research Director Evolution Engine
进化引擎 - 自适应优化系统

实现基于 Part 3 评估反馈的自动演化机制：
1. 性能诊断 (Performance Diagnostician) - 分析评估结果
2. SOP 演化 (SOP Architect) - 生成改进方案
3. 基因池管理 (Gene Pool) - 跟踪演化历史
4. 完整演化循环 (Evolution Cycle) - 协调整个过程

"""

import json
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
from agent.part2_guild_system import GuildSOP, create_default_guild_sop
from agent.part3_evaluation_gauntlet import EvaluationResult

logger = logging.getLogger(__name__)


# ============================================================================
# Part 4.1: 性能诊断数据结构
# ============================================================================

class WeaknessType(Enum):
    """性能弱点类型枚举"""
    ACCURACY = "accuracy"
    GRAPH_UTILIZATION = "graph_utilization"
    SOURCE_ATTRIBUTION = "source_attribution"
    COHERENCE = "coherence"
    EFFICIENCY = "efficiency"


@dataclass
class Diagnosis:
    """性能诊断结果"""
    primary_weakness: WeaknessType
    root_cause_analysis: str
    recommendation: str
    secondary_weakness: Optional[WeaknessType] = None
    confidence: float = 0.8
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class EvolvedSOP:
    """演化的SOP方案"""
    sop: GuildSOP
    mutation_strategy: str  # 变异策略描述
    expected_improvement: Dict[str, float]  # 预期改进
    retrieval_config: Dict[str, int] = field(default_factory=dict)  # 检索配置（如metaso_search_topk等）
    confidence: float = 0.7


@dataclass
class GenePoolEntry:
    """基因池条目 - SOP及其评估结果"""
    version: int
    sop: GuildSOP
    evaluation: Optional[EvaluationResult] = None
    parent_version: Optional[int] = None
    diagnosis: Optional[Diagnosis] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    overall_fitness: float = 0.0  # 综合适应度


# ============================================================================
# Part 4.2: 性能诊断器 Agent
# ============================================================================

class PerformanceDiagnostician:
    """
    性能诊断 Agent - 分析5维评估结果，诊断主要问题
    
    对应 code.ipynb 的 Performance Diagnostician，但针对5维度优化
    """
    
    def __init__(self, llm_config: LLMConfig):
        """初始化诊断器"""
        self.llm = llm_config
        logger.info("✓ Performance Diagnostician 初始化")
    
    def diagnose(self, evaluation: EvaluationResult) -> Diagnosis:
        """诊断性能问题"""
        logger.info("🔬 [Diagnostician] 分析性能向量...")
        
        # 识别最弱的维度
        dimensions = {
            WeaknessType.ACCURACY: evaluation.accuracy.score,
            WeaknessType.GRAPH_UTILIZATION: evaluation.graph_utilization.score,
            WeaknessType.SOURCE_ATTRIBUTION: evaluation.source_attribution.score,
            WeaknessType.COHERENCE: evaluation.coherence.score,
            WeaknessType.EFFICIENCY: evaluation.efficiency.score,
        }
        
        sorted_dims = sorted(dimensions.items(), key=lambda x: x[1])
        primary = sorted_dims[0]
        secondary = sorted_dims[1] if len(sorted_dims) > 1 else None
        
        logger.info(f"  主要弱点: {primary[0].value} ({primary[1]:.2f})")
        if secondary:
            logger.info(f"  次要弱点: {secondary[0].value} ({secondary[1]:.2f})")
        
        # 生成诊断
        prompt = f"""你是一个系统优化专家。请分析以下系统性能评估结果，识别主要问题并提供改进建议。

【5维度评分】
- 领域准确性: {evaluation.accuracy.score:.2f}
  理由: {evaluation.accuracy.reasoning}
  
- 知识图谱利用度: {evaluation.graph_utilization.score:.2f}
  理由: {evaluation.graph_utilization.reasoning}
  
- 来源归属: {evaluation.source_attribution.score:.2f}
  理由: {evaluation.source_attribution.reasoning}
  
- 连贯性与一致性: {evaluation.coherence.score:.2f}
  理由: {evaluation.coherence.reasoning}
  
- 操作效率: {evaluation.efficiency.score:.2f}
  理由: {evaluation.efficiency.reasoning}

【任务】
1. 确认主要弱点是什么（应该是分数最低的维度）
2. 进行根本原因分析
3. 提供具体的改进建议

请以自然语言回答，不需要JSON格式。"""
        
        try:
            response = self.llm.call_llm(prompt, temperature=0.0, max_tokens=800)
            root_cause = response
            confidence = 0.8
        except Exception as e:
            logger.warning(f"  ⚠️ 诊断失败: {e}")
            root_cause = str(e)
            confidence = 0.5
        
        recommendation = f"基于{primary[0].value}分数为{primary[1]:.2f}的诊断，建议优化该维度"
        
        diagnosis = Diagnosis(
            primary_weakness=primary[0],
            root_cause_analysis=root_cause,
            recommendation=recommendation,
            secondary_weakness=secondary[0] if secondary else None,
            confidence=confidence
        )
        
        logger.info("  ✓ 诊断完成")
        return diagnosis


# ============================================================================
# Part 4.3: SOP 演化器 Agent
# ============================================================================

class SOPArchitect:
    """
    SOP 演化 Agent - 基于诊断生成改进的SOP配置
    
    对应 code.ipynb 的 SOP Architect，但针对Graph RAG + RAG优化
    """
    
    def __init__(self, llm_config: LLMConfig):
        """初始化演化器"""
        self.llm = llm_config
        logger.info("✓ SOP Architect 初始化")
    
    def evolve(self, diagnosis: Diagnosis, current_sop: GuildSOP) -> List[EvolvedSOP]:
        """根据诊断生成演化的SOP"""
        logger.info(f"🧬 [Architect] 生成演化方案...")
        
        weakness = diagnosis.primary_weakness.value
        
        # 根据弱点类型生成不同的变异策略
        strategies = self._get_strategies(weakness)
        
        evolved_sops = []
        
        for i, strategy in enumerate(strategies, 1):
            logger.info(f"  生成方案 {i}: {strategy['name']}")
            
            evolved_sop = self._apply_mutation(current_sop, strategy, weakness)
            
            # 提取检索配置
            retrieval_config = {}
            changes = strategy.get("changes", {})
            if "metaso_search_topk" in changes:
                retrieval_config["metaso_search_topk"] = changes["metaso_search_topk"]
            if "markdown_blocks" in changes:
                retrieval_config["markdown_blocks"] = changes["markdown_blocks"]
            if "vector_chunks" in changes:
                retrieval_config["vector_chunks"] = changes["vector_chunks"]
            if "graph_entities" in changes:
                retrieval_config["graph_entities"] = changes["graph_entities"]
            
            evolved = EvolvedSOP(
                sop=evolved_sop,
                mutation_strategy=strategy['name'],
                expected_improvement=strategy['expected_improvement'],
                retrieval_config=retrieval_config,
                confidence=strategy.get('confidence', 0.7)
            )
            evolved_sops.append(evolved)
        
        logger.info(f"  ✓ 生成 {len(evolved_sops)} 个演化方案")
        return evolved_sops
    
    def _get_strategies(self, weakness: str) -> List[Dict[str, Any]]:
        """获取针对特定弱点的演化策略"""
        
        strategies = {
            "accuracy": [
                {
                    "name": "增强检索精度",
                    "changes": {"researcher_retriever_k": 8},
                    "expected_improvement": {"accuracy": 0.15, "coherence": 0.05},
                    "confidence": 0.8
                },
                {
                    "name": "优化合成提示词",
                    "changes": {"synthesizer_focus": "accuracy"},
                    "expected_improvement": {"accuracy": 0.12, "coherence": 0.08},
                    "confidence": 0.7
                }
            ],
            
            "graph_utilization": [
                {
                    "name": "增强图探索权重",
                    "changes": {"use_graph_rag": True, "graph_weight": 1.5},
                    "expected_improvement": {"graph_utilization": 0.20},
                    "confidence": 0.75
                },
                {
                    "name": "扩展实体查询范围",
                    "changes": {"graph_query_depth": 2},
                    "expected_improvement": {"graph_utilization": 0.18, "efficiency": -0.05},
                    "confidence": 0.7
                }
            ],
            
            "source_attribution": [
                {
                    "name": "扩大秘塔搜索召回量",
                    "changes": {"metaso_search_topk": 5, "markdown_blocks": 5},
                    "expected_improvement": {"source_attribution": 0.30, "accuracy": 0.15},
                    "confidence": 0.85
                },
                {
                    "name": "增加多源融合",
                    "changes": {"metaso_search_topk": 4, "vector_chunks": 6, "graph_entities": 8},
                    "expected_improvement": {"source_attribution": 0.25, "coverage": 0.10},
                    "confidence": 0.8
                }
            ],
            
            "coherence": [
                {
                    "name": "增强逻辑检查",
                    "changes": {"coherence_check": True},
                    "expected_improvement": {"coherence": 0.15},
                    "confidence": 0.75
                },
                {
                    "name": "优化信息融合",
                    "changes": {"synthesis_method": "structured"},
                    "expected_improvement": {"coherence": 0.18, "source_attribution": 0.05},
                    "confidence": 0.7
                }
            ],
            
            "efficiency": [
                {
                    "name": "减少检索数",
                    "changes": {"researcher_retriever_k": 3},
                    "expected_improvement": {"efficiency": 0.30, "accuracy": -0.05},
                    "confidence": 0.8
                },
                {
                    "name": "并行化Specialists",
                    "changes": {"parallel_specialists": True},
                    "expected_improvement": {"efficiency": 0.25},
                    "confidence": 0.75
                }
            ]
        }
        
        return strategies.get(weakness, strategies["accuracy"])
    
    def _apply_mutation(self, sop: GuildSOP, strategy: Dict, weakness: str) -> GuildSOP:
        """应用变异策略到SOP"""
        
        # 创建SOP副本
        new_sop = GuildSOP(
            planner_prompt=sop.planner_prompt,
            retriever_prompt_template=sop.retriever_prompt_template,
            synthesizer_prompt=sop.synthesizer_prompt,
            analyst_prompt=sop.analyst_prompt,
            researcher_retriever_k=sop.researcher_retriever_k,
            use_graph_rag=sop.use_graph_rag,
            use_analyst=sop.use_analyst,
            confidence_threshold=sop.confidence_threshold,
            max_iterations=sop.max_iterations
        )
        
        # 应用变异
        changes = strategy.get("changes", {})
        
        if "researcher_retriever_k" in changes:
            new_sop.researcher_retriever_k = changes["researcher_retriever_k"]
        
        if "use_graph_rag" in changes:
            new_sop.use_graph_rag = changes["use_graph_rag"]
        
        if "confidence_threshold" in changes:
            new_sop.confidence_threshold = changes["confidence_threshold"]
        
        if "max_iterations" in changes:
            new_sop.max_iterations = changes["max_iterations"]
        
        return new_sop


# ============================================================================
# Part 4.4: SOP 基因池
# ============================================================================

class SOPGenePool:
    """
    SOP 基因池 - 管理所有演化的SOP及其评估结果
    
    对应 code.ipynb 的 SOPGenePool，但更完整的追踪机制
    """
    
    def __init__(self):
        """初始化基因池"""
        self.pool: List[GenePoolEntry] = []
        self.version_counter = 0
        logger.info("✓ SOP Gene Pool 初始化")
    
    def add(self, sop: GuildSOP, evaluation: Optional[EvaluationResult] = None,
            diagnosis: Optional[Diagnosis] = None, parent_version: Optional[int] = None):
        """添加新的SOP到基因池"""
        self.version_counter += 1
        
        # 计算适应度
        fitness = 0.0
        if evaluation:
            fitness = evaluation.overall_score
        
        entry = GenePoolEntry(
            version=self.version_counter,
            sop=sop,
            evaluation=evaluation,
            parent_version=parent_version,
            diagnosis=diagnosis,
            overall_fitness=fitness
        )
        
        self.pool.append(entry)
        logger.info(f"  ✓ SOP v{self.version_counter} 添加到基因池 (适应度: {fitness:.2f})")
    
    def get_latest(self) -> Optional[GenePoolEntry]:
        """获取最新的SOP"""
        return self.pool[-1] if self.pool else None
    
    def get_best(self) -> Optional[GenePoolEntry]:
        """获取适应度最高的SOP"""
        if not self.pool:
            return None
        return max(self.pool, key=lambda x: x.overall_fitness)
    
    def get_by_version(self, version: int) -> Optional[GenePoolEntry]:
        """获取指定版本的SOP"""
        for entry in self.pool:
            if entry.version == version:
                return entry
        return None
    
    def get_history(self, limit: int = 10) -> List[GenePoolEntry]:
        """获取最近的SOP历史"""
        return self.pool[-limit:]
    
    def get_genealogy(self) -> Dict[int, List[int]]:
        """获取演化族系图"""
        genealogy = {}
        for entry in self.pool:
            if entry.parent_version is not None:
                if entry.parent_version not in genealogy:
                    genealogy[entry.parent_version] = []
                genealogy[entry.parent_version].append(entry.version)
        return genealogy
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典用于持久化"""
        return {
            "version_counter": self.version_counter,
            "pool_size": len(self.pool),
            "best_fitness": self.get_best().overall_fitness if self.get_best() else 0.0,
            "history": [
                {
                    "version": e.version,
                    "fitness": e.overall_fitness,
                    "parent": e.parent_version,
                    "created_at": e.created_at
                }
                for e in self.pool
            ]
        }


# ============================================================================
# Part 4.5: 完整演化引擎
# ============================================================================

class EvolutionEngine:
    """
    完整的演化引擎 - 协调诊断、演化、评估的完整循环
    
    这是 Part 4 的主协调器
    """
    
    def __init__(self, llm_config: LLMConfig):
        """初始化演化引擎"""
        self.llm = llm_config
        self.diagnostician = PerformanceDiagnostician(llm_config)
        self.architect = SOPArchitect(llm_config)
        self.gene_pool = SOPGenePool()
        
        logger.info("✓ Evolution Engine 初始化完成")
    
    def initialize_gene_pool(self, baseline_sop: GuildSOP, baseline_evaluation: EvaluationResult):
        """使用基线SOP初始化基因池"""
        logger.info("🧬 初始化基线SOP到基因池...")
        self.gene_pool.add(
            sop=baseline_sop,
            evaluation=baseline_evaluation,
            parent_version=None
        )
        logger.info(f"  ✓ 基线 v1 已添加 (适应度: {baseline_evaluation.overall_score:.2f})")
    
    def run_evolution_cycle(self) -> Tuple[List[EvolvedSOP], List[Diagnosis]]:
        """执行一个完整的演化循环"""
        
        logger.info("\n" + "=" * 80)
        logger.info("🔄 执行演化循环")
        logger.info("=" * 80 + "\n")
        
        # Step 1: 获取当前最佳SOP
        best_entry = self.gene_pool.get_best()
        if not best_entry or not best_entry.evaluation:
            logger.error("❌ 基因池为空或无评估数据")
            return [], []
        
        logger.info(f"📊 当前最佳: SOP v{best_entry.version} (适应度: {best_entry.overall_fitness:.2f})")
        
        # Step 2: 诊断问题
        logger.info("\n📋 Step 1: 性能诊断")
        diagnosis = self.diagnostician.diagnose(best_entry.evaluation)
        
        # Step 3: 生成演化方案
        logger.info("\n🧬 Step 2: 生成演化方案")
        evolved_sops = self.architect.evolve(diagnosis, best_entry.sop)
        
        logger.info(f"\n✅ 演化循环完成")
        logger.info(f"  • 诊断: {diagnosis.primary_weakness.value}")
        logger.info(f"  • 生成方案数: {len(evolved_sops)}")
        
        return evolved_sops, [diagnosis]
    
    def evaluate_candidates(self, evolved_sops: List[EvolvedSOP],
                           evaluator_func) -> List[GenePoolEntry]:
        """评估候选方案"""
        
        logger.info("\n📈 Step 3: 评估候选方案")
        
        evaluated_entries = []
        current_best = self.gene_pool.get_best()
        parent_version = current_best.version if current_best else None
        
        for i, evolved in enumerate(evolved_sops, 1):
            logger.info(f"\n  评估方案 {i}/{len(evolved_sops)}: {evolved.mutation_strategy}")
            
            try:
                # 调用评估函数
                evaluation = evaluator_func(evolved.sop)
                
                # 添加到基因池
                self.gene_pool.add(
                    sop=evolved.sop,
                    evaluation=evaluation,
                    parent_version=parent_version
                )
                
                entry = self.gene_pool.get_latest()
                evaluated_entries.append(entry)
                
                # 检查是否改进
                if current_best and evaluation.overall_score > current_best.overall_fitness:
                    improvement = (evaluation.overall_score - current_best.overall_fitness) * 100
                    logger.info(f"    ✨ 改进 +{improvement:.1f}% (v{current_best.version} → v{entry.version})")
                else:
                    logger.info(f"    ℹ️  适应度: {evaluation.overall_score:.2f}")
                    
            except Exception as e:
                logger.error(f"    ❌ 评估失败: {e}")
        
        return evaluated_entries
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取演化统计信息"""
        
        best = self.gene_pool.get_best()
        latest = self.gene_pool.get_latest()
        
        fitness_scores = [e.overall_fitness for e in self.gene_pool.pool]
        
        return {
            "total_generations": self.gene_pool.version_counter,
            "pool_size": len(self.gene_pool.pool),
            "best_fitness": best.overall_fitness if best else 0.0,
            "best_version": best.version if best else 0,
            "latest_fitness": latest.overall_fitness if latest else 0.0,
            "latest_version": latest.version if latest else 0,
            "average_fitness": sum(fitness_scores) / len(fitness_scores) if fitness_scores else 0.0,
            "max_fitness": max(fitness_scores) if fitness_scores else 0.0,
            "min_fitness": min(fitness_scores) if fitness_scores else 0.0,
            "genealogy": self.gene_pool.get_genealogy()
        }
    
    def print_statistics(self):
        """打印演化统计信息"""
        
        stats = self.get_statistics()
        
        logger.info("\n" + "=" * 80)
        logger.info("📊 演化统计")
        logger.info("=" * 80)
        logger.info(f"  总代数: {stats['total_generations']}")
        logger.info(f"  池大小: {stats['pool_size']}")
        logger.info(f"  \n  最佳适应度: {stats['best_fitness']:.3f} (v{stats['best_version']})")
        logger.info(f"  最新适应度: {stats['latest_fitness']:.3f} (v{stats['latest_version']})")
        logger.info(f"  平均适应度: {stats['average_fitness']:.3f}")
        logger.info(f"  最大适应度: {stats['max_fitness']:.3f}")
        logger.info(f"  最小适应度: {stats['min_fitness']:.3f}")
        logger.info("=" * 80)


if __name__ == "__main__":
    logger.info("=" * 80)
    logger.info("Part 4: Evolution Engine - AI Research Director 进化引擎")
    logger.info("=" * 80)
    
    print("\n✓ Part 4 进化引擎已定义")
    print("  - PerformanceDiagnostician: 性能诊断")
    print("  - SOPArchitect: SOP 演化")
    print("  - SOPGenePool: 基因池管理")
    print("  - EvolutionEngine: 主协调器")
