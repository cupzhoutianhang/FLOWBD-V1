"""
Part 5 增强版: Graph RAG + RAG + 多智能体 + Pareto前沿导航 + 自进化系统

完整的自进化系统包含：
1. Part 1: 知识武库组装 (数据管理、LLM配置、知识库连接)
2. Part 2: 多智能体协作系统 (问题解析、多源检索、信息融合、答案生成)
3. Part 3: 多维度评估 (5维度性能评分)
4. Part 4: 自进化引擎 (诊断弱点、生成变异SOP、测试改进)
5. Part 5: Pareto前沿导航 (识别最优权衡、可视化决策)

工作流程（完整的自进化循环）：
1. 初始化系统 (Part 1)
2. 多智能体处理 (Part 2: 问题解析 → 多源检索 → 信息融合 → 答案生成)
3. 性能评估 (Part 3: 5维评分)
4. 自进化 (Part 4: 诊断 → 变异 → 评估)
5. Pareto前沿分析 (Part 5: 识别最优解 → 可视化 → 决策)
"""

import os
import sys
import logging
import argparse
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import uuid4

# 项目路径配置
# run_part5_enhanced.py 位于 src/ 目录
# 需要找到项目根目录 (d:\flowbd_v5)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))  # 当前脚本目录: src/
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)  # 向上一级到项目根目录
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# 也要添加 src/agent 到路径（为agent模块）
AGENT_DIR = os.path.join(PROJECT_ROOT, 'src', 'agent')
if AGENT_DIR not in sys.path:
    sys.path.insert(0, AGENT_DIR)

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # 控制台处理器
    ]
)
# 压制其他库的DEBUG日志
logging.getLogger('neo4j').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('requests').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy').setLevel(logging.WARNING)
for handler in logging.root.handlers:
    handler.setLevel(logging.INFO)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ... 导入所有必需模块
try:
    # 从 src/agent 目录下导入
    from agent.part1_knowledge_arsenal import KnowledgeArsenal
    from agent.part5_multiagent_integration import (
        MultiAgentPipeline,
        SimpleMultiAgentSystem,
        AgentPipelineState
    )
    from agent.part5_pareto_navigator import (
        ParetoFrontier,
        DimensionScore,
        FiveDAchievements,
        SOPCandidate,
        ParetoVisualizer,
        TradeoffAnalyzer,
        ParetoFrontierNavigator
    )
    
    # 【新增】导入分子工具
    from molecule_tools.molecule_property_tool import (
        MoleculePropertyTool,
        MoleculeQueryAgent
    )
    from molecule_tools.kg_molecule_processor import KGMoleculeProcessor
    
    logger.info("✓ 所有模块导入成功")
    
except ImportError as e:
    logger.error(f"❌ 导入失败: {e}")
    logger.error("请确保以下文件存在：")
    logger.error("  - src/agent/graphrag_and_rag/agent/part1_knowledge_arsenal.py")
    logger.error("  - src/agent/graphrag_and_rag/agent/part5_multiagent_integration.py")
    logger.error("  - src/agent/graphrag_and_rag/agent/part5_pareto_navigator.py")
    logger.error("  - src/agent/molecule_tools/molecule_property_tool.py")
    logger.error("  - src/agent/molecule_tools/kg_molecule_processor.py")
    sys.exit(1)


# ============================================================================
# Part 4: 自进化引擎 (Evolution Engine)
# ============================================================================

class PerformanceDiagnostician:
    """性能诊断器 - 识别系统的主要弱点"""
    
    def __init__(self, llm):
        self.llm = llm
    
    def diagnose(self, metrics: dict) -> dict:
        """诊断性能问题"""
        scores = {
            'accuracy': metrics.accuracy,
            'coverage': metrics.coverage,
            'source_attribution': metrics.source_attribution,
            'coherence': metrics.coherence,
            'efficiency': metrics.efficiency
        }
        
        # 找到最低的维度
        primary_weakness = min(scores.items(), key=lambda x: x[1])
        weakness_name = primary_weakness[0]
        weakness_score = primary_weakness[1]
        
        diagnosis = {
            'primary_weakness': weakness_name,
            'weakness_score': weakness_score,
            'root_cause': f"在{weakness_name}维度表现不足（评分：{weakness_score:.3f}）",
            'recommendation': self._get_recommendation(weakness_name)
        }
        
        return diagnosis
    
    def _get_recommendation(self, weakness: str) -> str:
        """根据弱点提供改进建议"""
        recommendations = {
            'accuracy': "增加检索文档数量，改进提示词精度",
            'coverage': "扩大检索范围，使用更多知识源",
            'source_attribution': "明确标注信息来源，改进引用格式",
            'coherence': "优化答案生成提示词，增加逻辑连贯性",
            'efficiency': "优化检索算法，减少处理时间"
        }
        return recommendations.get(weakness, "改进系统配置")


class SOPEvolver:
    """SOP进化器 - 生成改进的系统配置"""
    
    def __init__(self, llm):
        self.llm = llm
        self.sop_versions = {}
    
    def evolve(self, current_sop: dict, diagnosis: dict) -> list:
        """根据诊断生成变异的SOP"""
        mutations = []
        weakness = diagnosis['primary_weakness']
        
        # 基于不同弱点生成不同的变异
        if weakness == 'accuracy':
            mutations = [
                {'name': '增强检索精度', 'researcher_retriever_k': 8, 'vector_chunks': 5},
                {'name': '优化合成提示词', 'synthesizer_focus': 'accuracy'}
            ]
        elif weakness == 'coverage':
            mutations = [
                {'name': '更多信源', 'vector_chunks': 8, 'markdown_blocks': 6, 'researcher_retriever_k': 8},
                {'name': '更广泛查询', 'retrieval_k': 10, 'vector_chunks': 10}
            ]
        elif weakness == 'source_attribution':
            mutations = [
                {'name': '扩大秘塔搜索召回量', 'metaso_search_topk': 5, 'markdown_blocks': 5, 'researcher_retriever_k': 7},
                {'name': '增加多源融合', 'metaso_search_topk': 4, 'vector_chunks': 6, 'graph_entities': 8, 'researcher_retriever_k': 7}
            ]
        elif weakness == 'coherence':
            mutations = [
                {'name': '增强逻辑检查', 'coherence_check': True},
                {'name': '优化信息融合', 'synthesis_method': 'structured'}
            ]
        else:  # efficiency
            mutations = [
                {'name': '减少检索数', 'researcher_retriever_k': 3, 'vector_chunks': 2},
                {'name': '并行化Specialists', 'parallel_specialists': True}
            ]
        
        return mutations


class EvolutionCycle:
    """自进化循环 - 完整的诊断-变异-评估流程"""
    
    def __init__(self, llm, navigator: 'ParetoFrontierNavigator'):
        self.llm = llm
        self.navigator = navigator
        self.diagnostician = PerformanceDiagnostician(llm)
        self.evolver = SOPEvolver(llm)
        self.evolution_history = []
    
    def run_cycle(self, question: str, current_metrics: dict, cycle_num: int = 1) -> tuple:
        """运行一个完整的进化循环"""
        print(f"\n{'='*80}")
        print(f"🧬 进化循环 #{cycle_num}: 诊断 → 变异 → 评估")
        print(f"{'='*80}\n")
        print(f"  【本轮初始配置】 vector_chunks={self.navigator._vector_chunks}, markdown_blocks={self.navigator._markdown_blocks}")
        print(f"  【上轮基准评分】 综合评分: {current_metrics.composite_score():.3f}\n")
        
        # 阶段1: 性能诊断
        print("📋 【阶段1】性能诊断器 (PerformanceDiagnostician)")
        print("  分析当前 5 维度性能指标...")
        diagnosis = self.diagnostician.diagnose(current_metrics)
        
        print(f"\n  📊 当前性能分析:")
        print(f"    - 准确性 (accuracy):      {current_metrics.accuracy:.3f}")
        print(f"    - 覆盖率 (coverage):      {current_metrics.coverage:.3f}")
        print(f"    - 来源归属 (attribution): {current_metrics.source_attribution:.3f}")
        print(f"    - 连贯性 (coherence):     {current_metrics.coherence:.3f}")
        print(f"    - 效率 (efficiency):      {current_metrics.efficiency:.3f}")
        print(f"    - 综合评分:               {current_metrics.composite_score():.3f}")
        
        print(f"\n  🔍 主要弱点识别:")
        print(f"    - 弱点维度: {diagnosis['primary_weakness']}")
        print(f"    - 弱点评分: {diagnosis['weakness_score']:.3f}")
        print(f"    - 根本原因: {diagnosis['root_cause']}")
        print(f"    - 改进建议: {diagnosis['recommendation']}\n")
        
        # 阶段2: 变异生成器
        print("🔬 【阶段2】SOP进化器 (SOPEvolver)")
        print(f"  根据弱点 '{diagnosis['primary_weakness']}' 生成改进方案...\n")
        mutations = self.evolver.evolve({}, diagnosis)
        
        print(f"  生成的变异SOP候选:")
        for i, mutation in enumerate(mutations, 1):
            print(f"    [{i}] {mutation.get('name')}")
            # 显示配置变化
            for key, value in mutation.items():
                if key != 'name':
                    print(f"        - {key}: {value}")
        print()
        
        # 阶段3: 变异评估
        print("📈 【阶段3】变异评估与选择")
        print(f"  测试每个变异，计算改进幅度...\n")
        best_mutation = None
        best_improvement = 0
        mutation_results = []
        
        for i, mutation in enumerate(mutations):
            print(f"  🧪 变异 {i+1}/{len(mutations)}: {mutation.get('name')}")
            
            # 【关键步骤】应用变异配置到管道
            try:
                # 保存原始配置
                original_config = self._save_pipeline_config()
                
                # 应用变异配置
                self._apply_mutation_config(mutation)
                
                # 使用新配置处理问题
                state = self.navigator.process_multi_agent(question)
                new_metrics = self.navigator.evaluator.evaluate_agent_response(
                    question,
                    state,
                    answer_type="optimized"  # 这是优化过的答案
                )
                
                # 计算各维度的改进
                delta_accuracy = new_metrics.accuracy - current_metrics.accuracy
                delta_coverage = new_metrics.coverage - current_metrics.coverage
                delta_attribution = new_metrics.source_attribution - current_metrics.source_attribution
                delta_coherence = new_metrics.coherence - current_metrics.coherence
                delta_efficiency = new_metrics.efficiency - current_metrics.efficiency
                
                # 计算综合改进
                improvement = (
                    delta_accuracy +
                    delta_coverage +
                    delta_attribution +
                    delta_coherence +
                    delta_efficiency
                ) / 5.0
                
                print(f"    📊 性能变化（相对上轮基准）:")
                print(f"       准确性:      {delta_accuracy:+.3f} ({new_metrics.accuracy:.3f})")
                print(f"       覆盖率:      {delta_coverage:+.3f} ({new_metrics.coverage:.3f})")
                print(f"       来源归属:    {delta_attribution:+.3f} ({new_metrics.source_attribution:.3f})")
                print(f"       连贯性:      {delta_coherence:+.3f} ({new_metrics.coherence:.3f})")
                print(f"       效率:        {delta_efficiency:+.3f} ({new_metrics.efficiency:.3f})")
                print(f"    📈 综合改进:     {improvement:+.3f}")
                print(f"    ⭐ 本方案评分:   {new_metrics.composite_score():.3f}")
                print()
                
                mutation_results.append({
                    'name': mutation.get('name'),
                    'improvement': improvement,
                    'metrics': new_metrics,
                    'config': mutation
                })
                
                if improvement > best_improvement:
                    best_improvement = improvement
                    best_mutation = {
                        'config': mutation,
                        'metrics': new_metrics,
                        'improvement': improvement,
                        'state': state  # 【新增】保存优化循环中得到的state
                    }
            except Exception as e:
                logger.debug(f"变异评估失败: {e}")
            finally:
                # 【修复】恢复原始配置 - 但不恢复最优方案的参数
                if 'original_config' in locals():
                    self._restore_pipeline_config(original_config)
        
        # 显示本轮评估结果
        print(f"✨ 【第{cycle_num}轮评估结果】")
        if mutation_results:
            # 排序结果：按综合评分排序（而非改进值）
            sorted_results = sorted(mutation_results, key=lambda x: x['metrics'].composite_score(), reverse=True)
            print(f"  方案排名（按综合评分）:")
            for rank, result in enumerate(sorted_results, 1):
                composite = result['metrics'].composite_score()
                improvement = result['improvement']
                status = "🏆" if rank == 1 else "  "
                print(f"    {status} {rank}. {result['name']:<30} 评分: {composite:.3f}  改进: {improvement:+.3f}")
        
        print()
        if best_mutation:
            best_composite = best_mutation['metrics'].composite_score()
            print(f"✅ 第{cycle_num}轮最优方案: {best_mutation['config'].get('name')}")
            print(f"   综合评分: {best_composite:.3f}")
            print(f"   相对改进: {best_improvement:+.3f}")
            if best_improvement > 0:
                print(f"   ↗️  有改进，此配置将作为第{cycle_num+1}轮的初始值\n")
            else:
                print(f"   ⚠️  无改进，保持当前配置为基准\n")
        else:
            print(f"⚠️  所有方案评分均未超过基准，保持当前配置\n")
            best_mutation = None
        
        self.evolution_history.append({
            'cycle': cycle_num,
            'diagnosis': diagnosis,
            'best_mutation': best_mutation,
            'improvement': best_improvement if best_mutation else 0,
            'best_metrics': best_mutation['metrics'] if best_mutation else current_metrics
        })
        
        return best_mutation, diagnosis
    
    def _save_pipeline_config(self) -> Dict[str, Any]:
        """
        保存当前管道的配置
        
        返回：配置字典
        """
        return {
            'researcher_retriever_k': getattr(self.navigator, '_researcher_retriever_k', 5),
            'vector_chunks': getattr(self.navigator, '_vector_chunks', 3),
            'markdown_blocks': getattr(self.navigator, '_markdown_blocks', 0),
            'graph_entities': getattr(self.navigator, '_graph_entities', 5),
            'retrieval_k': getattr(self.navigator, '_retrieval_k', 5),
            'synthesizer_focus': getattr(self.navigator, '_synthesizer_focus', 'default'),  # 【新增】保存 synthesizer_focus
        }
    
    def _apply_mutation_config(self, mutation: Dict[str, Any]):
        """
        应用变异配置到管道
        
        变异配置示例：
        {
            'name': 'increased_retrieval',
            'researcher_retriever_k': 8,
            'vector_chunks': 8,
            'markdown_blocks': 6,
            'metaso_search_topk': 5,
            'graph_entities': 15,
            'retrieval_k': 10
        }
        """
        # 【新增】应用 researcher_retriever_k 配置
        if 'researcher_retriever_k' in mutation:
            old_val = getattr(self.navigator, '_researcher_retriever_k', 5)
            self.navigator._researcher_retriever_k = mutation['researcher_retriever_k']
            print(f"       • researcher_retriever_k: {old_val} → {mutation['researcher_retriever_k']}")
        
        # 应用向量块配置
        if 'vector_chunks' in mutation:
            old_val = self.navigator._vector_chunks
            self.navigator._vector_chunks = mutation['vector_chunks']
            print(f"       • vector_chunks: {old_val} → {mutation['vector_chunks']}")
        
        # 应用markdown块配置
        if 'markdown_blocks' in mutation:
            old_val = self.navigator._markdown_blocks
            self.navigator._markdown_blocks = mutation['markdown_blocks']
            print(f"       • markdown_blocks: {old_val} → {mutation['markdown_blocks']}")
        
        # 应用秘塔搜索top_k配置
        if 'metaso_search_topk' in mutation:
            old_val = self.navigator._markdown_blocks
            self.navigator._markdown_blocks = mutation['metaso_search_topk']
            print(f"       • metaso_search_topk: {old_val} → {mutation['metaso_search_topk']}")
        
        # 应用图谱实体配置
        if 'graph_entities' in mutation:
            old_val = self.navigator._graph_entities
            self.navigator._graph_entities = mutation['graph_entities']
            print(f"       • graph_entities: {old_val} → {mutation['graph_entities']}")
        
        # 应用检索k配置
        if 'retrieval_k' in mutation:
            old_val = self.navigator._retrieval_k
            self.navigator._retrieval_k = mutation['retrieval_k']
            print(f"       • retrieval_k: {old_val} → {mutation['retrieval_k']}")
        
        # 应用其他prompt相关配置
        if 'enhance_answer_prompt' in mutation and mutation['enhance_answer_prompt']:
            self.navigator._enhance_prompts = True
        
        # 应用缓存配置
        if 'enable_caching' in mutation and mutation['enable_caching']:
            self.navigator._enable_caching = True
        
        # 【新增】应用 synthesizer_focus 配置
        if 'synthesizer_focus' in mutation:
            old_val = getattr(self.navigator, '_synthesizer_focus', 'default')
            self.navigator._synthesizer_focus = mutation['synthesizer_focus']
            print(f"       • synthesizer_focus: {old_val} → {mutation['synthesizer_focus']}")
        
        # 【日志】打印应用的配置
        logger.info(f"  ☯️  已应用变异配置: researcher_retriever_k={getattr(self.navigator, '_researcher_retriever_k', 5)}, vector_chunks={self.navigator._vector_chunks}, markdown_blocks={self.navigator._markdown_blocks}, graph_entities={self.navigator._graph_entities}, synthesizer_focus={getattr(self.navigator, '_synthesizer_focus', 'default')}")
        logger.info(f"  🔍 Navigator当前值: researcher_retriever_k={getattr(self.navigator, '_researcher_retriever_k', 5)}, vector_chunks={self.navigator._vector_chunks}, markdown_blocks={self.navigator._markdown_blocks}, graph_entities={self.navigator._graph_entities}, synthesizer_focus={getattr(self.navigator, '_synthesizer_focus', 'default')}")
    
    def _restore_pipeline_config(self, original_config: Dict[str, Any]):
        """
        恢复原始配置
        """
        # 【新增】恢复 researcher_retriever_k
        if 'researcher_retriever_k' in original_config:
            self.navigator._researcher_retriever_k = original_config['researcher_retriever_k']
        
        self.navigator._vector_chunks = original_config['vector_chunks']
        self.navigator._markdown_blocks = original_config['markdown_blocks']
        self.navigator._graph_entities = original_config['graph_entities']
        self.navigator._retrieval_k = original_config['retrieval_k']
        
        # 【新增】恢复 synthesizer_focus
        if 'synthesizer_focus' in original_config:
            self.navigator._synthesizer_focus = original_config['synthesizer_focus']
        
        self.navigator._enhance_prompts = False
        self.navigator._enable_caching = False


# ... 导入部分完成


class EnhancedPart5System:
    """增强的Part 5系统 - 多智能体 + Graph RAG + Traditional RAG + Pareto导航"""
    
    def __init__(self, use_graph_rag: bool = True, use_traditional_rag: bool = True, 
                 use_molecule_tool: bool = True, enable_deepchem: bool = False, 
                 enable_kg_evolution: bool = False, debug: bool = False):
        """
        初始化增强的Part 5系统
        
        Args:
            use_graph_rag: 是否使用Graph RAG
            use_traditional_rag: 是否使用传统RAG
            use_molecule_tool: 是否使用分子查询工具 (【新增】)
            enable_deepchem: 是否启用DeepChem功能 (【新增】)
            enable_kg_evolution: 是否启用知识图谱自我进化 (【新增】)
            debug: 调试模式
        """
        self.debug = debug
        self.use_graph_rag = use_graph_rag
        self.use_traditional_rag = use_traditional_rag
        self.use_molecule_tool = use_molecule_tool
        self.enable_deepchem = enable_deepchem
        self.enable_kg_evolution = enable_kg_evolution
        
        # 初始化LLM调用日志系统
        self.llm_interactions = []  # 存储所有LLM交互
        self.llm_io_dir = os.path.join(PROJECT_ROOT, "agent")  # LLM交互日志目录改为agent
        os.makedirs(self.llm_io_dir, exist_ok=True)
        
        print("\n" + "=" * 80)
        print("🧭 Part 5 增强版: Multi-Agent Collaborative Pareto Frontier Navigation")
        print("   Graph RAG + Traditional RAG + Multi-Agent + Pareto Optimization")
        print("=" * 80 + "\n")
        
        # 初始化知识武库
        logger.info("📦 初始化 Part 1: Knowledge Arsenal...")
        self.arsenal = KnowledgeArsenal()
        if not self.arsenal.assemble():
            raise RuntimeError("知识武库组装失败")
        
        llm = self.arsenal.get_llm()
        
        # 初始化Graph RAG (从 Neo4j 查询)
        self.graph_rag = None
        if use_graph_rag:
            logger.info("🔗 初始化 Graph RAG (Neo4j)接口...")
            try:
                from graph_rag.graph_qa_v2 import GraphQA
                # 使用 GraphQA 从 Neo4j 查询
                self.graph_rag = GraphQA()
                
                # 加载内存图谱（用于回滚查询）
                kg_file = os.path.join(PROJECT_ROOT, "src", "graph_rag", "knowledge_graph.json")
                if os.path.exists(kg_file):
                    try:
                        import json
                        with open(kg_file, 'r', encoding='utf-8') as f:
                            kg_data = json.load(f)
                        self.graph_rag.graph = kg_data  # 添加内存图谱属性
                        logger.info(f"✓ 内存图谱已加载: {len(kg_data.get('nodes', {}))} 个节点")
                    except Exception as e:
                        logger.warning(f"⚠️  内存图谱加载失败: {e}")
                
                logger.info("✓ Graph RAG 从 Neo4j 初始化完成")
            except Exception as e:
                logger.warning(f"⚠️  Graph RAG 从 Neo4j 初始化失败: {e}")
                logger.warning("⚠️  请先运行 extract_and_store_knowledge.py 上传数据到 Neo4j")
                self.graph_rag = None
        
        # 初始化传统RAG (可选)
        self.traditional_rag = None
        if use_traditional_rag:
            logger.info("📖 初始化 Traditional RAG (Milvus)...")
            try:
                from rag.traditional_rag_v3 import TraditionalRAGV3
                data_dir = os.path.join(PROJECT_ROOT, "pdf_to_md", "extraction_results")
                model_path = os.path.join(PROJECT_ROOT, "src", "rag", "models")
                self.traditional_rag = TraditionalRAGV3(
                    data_directory=data_dir,
                    model_path=model_path
                )
                logger.info("✓ Traditional RAG初始化完成")
            except Exception as e:
                logger.warning(f"⚠️  Traditional RAG初始化失败: {e}")
                self.traditional_rag = None
        
        # 【新增】初始化分子查询工具 (可选)
        self.molecule_tool = None
        self.molecule_agent = None
        self.kg_processor = None
        
        if use_molecule_tool:
            logger.info("🧪 初始化分子性质查询工具...")
            try:
                self.molecule_tool = MoleculePropertyTool(
                    enable_deepchem=enable_deepchem
                )
                self.molecule_agent = MoleculeQueryAgent(
                    llm_config=llm,
                    enable_deepchem=enable_deepchem
                )
                logger.info("✓ 分子查询工具初始化完成")
                
                # 【新增】初始化知识图谱分子处理器（用于自我进化）
                if enable_kg_evolution and llm:
                    try:
                        self.kg_processor = KGMoleculeProcessor(
                            llm_config=llm,
                            use_pubchem=True,
                            max_workers=2
                        )
                        logger.info("✓ 知识图谱分子处理器初始化完成")
                    except Exception as e:
                        logger.warning(f"⚠️  KG处理器初始化失败: {e}")
                        self.kg_processor = None
                        
            except Exception as e:
                logger.warning(f"⚠️  分子查询工具初始化失败: {e}")
                self.molecule_tool = None
                self.molecule_agent = None
        
        # 初始化增强的Pareto导航器
        logger.info("🧠 初始化 Enhanced Pareto Navigator...")
        self.navigator = EnhancedParetoNavigator(
            llm,
            graph_rag=self.graph_rag,
            traditional_rag=self.traditional_rag,
            molecule_agent=self.molecule_agent  # 【新增】传递分子查询Agent
        )
        
        # 初始化Pareto前沿分析
        self.frontier = ParetoFrontier()
        self.trade_analyzer = TradeoffAnalyzer(self.frontier)
        
        # 初始化自进化引擎 (Part 4)
        logger.info("🧬 初始化自进化引擎 (Part 4)...")
        self.evolution_cycle = EvolutionCycle(llm, self.navigator)
        
        # 【新增】将分子工具注入到导航器中（供检索Agent使用）
        # 注意：EnhancedParetoNavigator已经接受了molecule_agent参数，并将其传给了MultiAgentPipeline
        # 所以不需要再手动注入
        if self.molecule_agent:
            logger.info("✓ 分子查询工具已注入到多智能体系统")
        
        print("\n✅ 增强的Part 5系统初始化完成（完整的自进化系统）\n")
    
    def _record_llm_interaction(self, prompt: str, response: str, question: str = "", 
                               interaction_type: str = "general", metadata: Dict[str, Any] = None) -> str:
        """
        记录LLM交互 - 保存输入提示词和输出回答
        
        Args:
            prompt: LLM的输入提示词
            response: LLM的输出回答
            question: 原始问题
            interaction_type: 交互类型 (e.g., 'answer_generation', 'diagnosis', 'mutation')
            metadata: 额外元数据
            
        Returns:
            interaction_id: 交互ID
        """
        interaction_id = str(uuid4())[:8]
        timestamp = datetime.now().isoformat()
        
        # 构造交互记录
        interaction = {
            'id': interaction_id,
            'timestamp': timestamp,
            'type': interaction_type,
            'original_question': question,
            'input_prompt': prompt,
            'output_response': response,
            'metadata': metadata or {}
        }
        
        self.llm_interactions.append(interaction)
        
        # 【已禁用】保存到文件 - 不再下载输入输出
        # self._save_llm_interaction_to_file(interaction)
        
        return interaction_id
    
    def _save_llm_interaction_to_file(self, interaction: Dict[str, Any]):
        """
        保存LLM交互到文件
        
        Args:
            interaction: 交互记录字典
        """
        interaction_type = interaction['type']
        input_filename = None
        output_filename = None
        
        # 根据不同的interaction_type确定文件名
        if 'answer_generation_baseline' in interaction_type:
            input_filename = 'initial_input.txt'
            output_filename = 'initial_output.txt'
        elif 'answer_generation_cycle' in interaction_type:
            # 例如: answer_generation_cycle1_improved
            import re
            match = re.search(r'cycle(\d+)', interaction_type)
            if match:
                cycle_num = match.group(1)
                input_filename = f'cycle{cycle_num}_input.txt'
                output_filename = f'cycle{cycle_num}_output.txt'
            else:
                # 默认方案 - 使用interaction_id作为唯一标识
                input_filename = f'interaction_{interaction["id"]}_input.txt'
                output_filename = f'interaction_{interaction["id"]}_output.txt'
        elif 'answer_generation_final' in interaction_type:
            input_filename = 'best_input.txt'
            output_filename = 'best_output.txt'
        else:
            # 默认使用interaction_id
            input_filename = f'interaction_{interaction["id"]}_input.txt'
            output_filename = f'interaction_{interaction["id"]}_output.txt'
        
        # 保存输入文件
        input_file = os.path.join(self.llm_io_dir, input_filename)
        # 确保目录存在
        os.makedirs(os.path.dirname(input_file), exist_ok=True)
        try:
            with open(input_file, 'w', encoding='utf-8') as f:
                f.write(f"【LLM交互 ID】: {interaction['id']}\n")
                f.write(f"【时间戳】: {interaction['timestamp']}\n")
                f.write(f"【交互类型】: {interaction['type']}\n")
                f.write(f"【原始问题】: {interaction['original_question']}\n")
                f.write("\n" + "="*80 + "\n")
                f.write("【LLM输入提示词】\n")
                f.write("="*80 + "\n\n")
                f.write(interaction['input_prompt'])
            logger.info(f"✓ 输入文件已保存: {input_file}")
        except Exception as e:
            logger.error(f"✗ 保存输入文件失败: {input_file} - {e}")
        
        # 保存输出文件
        output_file = os.path.join(self.llm_io_dir, output_filename)
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"【LLM交互 ID】: {interaction['id']}\n")
                f.write(f"【时间戳】: {interaction['timestamp']}\n")
                f.write(f"【交互类型】: {interaction['type']}\n")
                f.write(f"【原始问题】: {interaction['original_question']}\n")
                f.write("\n" + "="*80 + "\n")
                f.write("【LLM输出回答】\n")
                f.write("="*80 + "\n\n")
                f.write(interaction['output_response'])
            logger.info(f"✓ 输出文件已保存: {output_file}")
        except Exception as e:
            logger.error(f"✗ 保存输出文件失败: {output_file} - {e}")
        
        # 保存元数据文件
        metadata_file = os.path.join(
            self.llm_io_dir,
            f"interaction_{interaction['id']}_metadata.json"
        )
        try:
            metadata = {
                'id': interaction['id'],
                'timestamp': interaction['timestamp'],
                'type': interaction['type'],
                'original_question': interaction['original_question'],
                'input_file': input_filename,
                'output_file': output_filename,
                'input_length': len(interaction['input_prompt']),
                'output_length': len(interaction['output_response']),
                'custom_metadata': interaction['metadata']
            }
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
            logger.info(f"✓ 元数据文件已保存: {metadata_file}")
        except Exception as e:
            logger.error(f"✗ 保存元数据文件失败: {metadata_file} - {e}")
        
        logger.info(f"✓ LLM交互已保存: {interaction['id']}")
    
    def _copy_best_output_from_interaction(self, interaction_id: str, best_answer_state, question: str):
        """
        【已禁用】复制最优配置输出 - 不再下载文件
        
        原有逻辑中输出文件并复制到best_output.txt，但现在已禁用
        """
        logger.info(f"  ⏭️  最优配置输出保存已禁用: {interaction_id}")
        # 【已保存】原有的复制逻辑已被禁用
    
    def process_question(self, question: str, stage_label: str = "baseline") -> AgentPipelineState:
        """通过多智能体管道处理问题"""
        logger.info(f"\n📝 处理问题: {question[:60]}...")
        
        # 执行多智能体管道
        state = self.navigator.process_multi_agent(question)
        
        # 【关键】拦截LLM调用以记录交互
        # 从pipeline响应中提取生成的答案和用到的prompt
        if state.final_answer:
            # 构建生成答案时的prompt（从AnswerGenerationAgent）
            generation_prompt = self._build_answer_generation_prompt(state, question)
            
            # 记录交互
            interaction_id = self._record_llm_interaction(
                prompt=generation_prompt,
                response=state.final_answer,
                question=question,
                interaction_type=f'answer_generation_{stage_label}',
                metadata={
                    'stage_label': stage_label,
                    'evidence_sources': state.evidence_sources,
                    'num_vector_chunks': len(state.vector_chunks),
                    'num_graph_entities': len(state.graph_entities),
                    'fusion_confidence': state.fusion_confidence
                }
            )
            
            # 将交互ID附加到状态中
            state.llm_interaction_id = interaction_id
        
        # 打印结果
        self.navigator.print_agent_response_summary(state)
        
        return state
    
    def _build_answer_generation_prompt(self, state: AgentPipelineState, original_question: str) -> str:
        """
        重建答案生成时的prompt（用于记录）
        
        这个prompt是AnswerGenerationAgent用来生成最终答案的
        """
        # 融合后的信息
        fused_info = state.fused_context or "无融合信息"
        
        prompt = f"""【原始问题】
{original_question}

【融合的背景信息】
{fused_info}

【证据来源】
{', '.join(state.evidence_sources) if state.evidence_sources else '未检索到证据'}

【提取的关键实体】
{', '.join(state.extracted_entities[:10]) if state.extracted_entities else '无'}

请基于上述信息，提供一个清晰、准确、全面的答案。答案应该：
1. 直接回答原始问题
2. 引用相关的背景信息
3. 说明主要的证据来源
4. 保持逻辑清晰和连贯
"""
        return prompt
    
    def evaluate_response_quality(self, state: AgentPipelineState, answer_type: str = "baseline") -> dict:
        """评估响应质量
        
        Args:
            state: Agent管道状态
            answer_type: 答案类型 - "baseline" (基线) 或 "optimized" (优化后)
        """
        metrics = self.navigator.performance_metrics.get(state.request_id)
        if metrics is None:
            metrics = self.navigator.evaluator.evaluate_agent_response(
                state.original_question,
                state,
                answer_type=answer_type  # 传递答案类型
            )
            self.navigator.performance_metrics[state.request_id] = metrics
        
        print("\n" + "=" * 80)
        print("📈 性能评估指标")
        print("=" * 80)
        print(f"  准确性:       {metrics.accuracy:.3f}")
        print(f"  信息覆盖率:   {metrics.coverage:.3f}")
        print(f"  来源归属:     {metrics.source_attribution:.3f}")
        print(f"  连贯性:       {metrics.coherence:.3f}")
        print(f"  执行效率:     {metrics.efficiency:.3f}")
        print(f"  【综合评分】  {metrics.composite_score():.3f}\n")
        
        return metrics
    
    def add_response_to_frontier(self, 
                                state: AgentPipelineState,
                                metrics: dict,
                                variant_name: str = "",
                                answer_type: str = "baseline"):
        """将响应添加到Pareto前沿分析
        
        Args:
            state: Agent管道状态
            metrics: 性能指标
            variant_name: 方案名称
            answer_type: 答案类型标记 (baseline/optimized)
        """
        
        # 转换为FiveDAchievements
        five_d = FiveDAchievements(
            accuracy=DimensionScore(
                name="准确性",
                score=metrics.accuracy,
                weight=1.2,
                description="Answer accuracy"
            ),
            graph_utilization=DimensionScore(
                name="图谱利用度",
                score=metrics.coverage,
                weight=1.0,
                description="Graph utilization"
            ),
            source_attribution=DimensionScore(
                name="来源归属",
                score=metrics.source_attribution,
                weight=0.9,
                description="Source attribution"
            ),
            coherence=DimensionScore(
                name="连贯性",
                score=metrics.coherence,
                weight=1.1,
                description="Coherence"
            ),
            efficiency=DimensionScore(
                name="效率",
                score=metrics.efficiency,
                weight=0.7,
                description="Efficiency"
            )
        )
        
        # 创建候选方案
        candidate = SOPCandidate(
            version=variant_name or f"agent_{state.request_id[-6:]}",
            sop_config={
                "agent_config": {
                    "use_graph_rag": self.use_graph_rag,
                    "use_traditional_rag": self.use_traditional_rag,
                    "pipeline": "question_parsing → multi_source_retrieval → fusion → generation",
                    "answer_type": answer_type  # 记录答案类型
                },
                "retrieval_sources": state.evidence_sources,
                "fusion_confidence": state.fusion_confidence
            },
            evaluation=five_d,
            generation_method="Multi-Agent Collaborative System",
            reasoning=f"多智能体协作生成，融合来源: {', '.join(state.evidence_sources)}",
            pipeline_state=state  # 【关键】保存对应的AgentPipelineState
        )
        
        self.frontier.add_candidate(candidate)
        logger.info(f"✓ 方案 {candidate.version} 添加到Pareto前沿")
        
        return candidate
    
    def run_complete_evolution_cycle(self, question: str, num_cycles: int = 1) -> dict:
        """
        运行完整的自进化循环 (Part 2-5)
        
        流程：
        1. Part 2: 多智能体处理问题
        2. Part 3: 评估性能（5维评分）
        3. Part 4: 自进化循环（诊断→变异→评估）
        4. Part 5: Pareto前沿分析
        """
        print("\n" + "=" * 80)
        print("🎯 完整的自进化循环 (Part 2 → Part 3 → Part 4 → Part 5)")
        print("=" * 80)
        
        # ===== Part 1: 知识武库 - 展示已组装的知识 =====
        print("\n" + "="*80)
        print("📚 Part 1: 知识武库组装 (Knowledge Arsenal)")
        print("="*80)
        logger.info("✓ 知识武库已初始化")
        logger.info(f"  - LLM 模型: {self.arsenal.llm.model}")
        if self.graph_rag:
            logger.info("  - Graph RAG: ✅ Neo4j 已连接")
        if self.traditional_rag:
            logger.info("  - Traditional RAG: ✅ Milvus 已连接")
        print()
        
        evolution_results = {
            'question': question,
            'cycles': [],
            'pareto_front': None,
            'best_variant': None
        }
        
        # 第一次运行（基线）
        print("\n" + "="*80)
        print("📝 初始基线运行")
        print("="*80 + "\n")
        
        # Part 2: 多智能体处理
        print("📋 Part 2: 多智能体协作系统")
        print("  ├─ QuestionParsingAgent: 解析问题")
        print("  ├─ MultiSourceRetrievalAgent: 多源检索")
        print("  ├─ InformationFusionAgent: 信息融合")
        print("  └─ AnswerGenerationAgent: 答案生成")
        state = self.process_question(question)
        print(f"  ✓ Part 2 完成: {len(state.evidence_sources)} 个信息源\n")
        
        # Part 3: 多维度评估
        print("📊 Part 3: 多维度性能评估")
        metrics = self.evaluate_response_quality(state, answer_type="baseline")
        print(f"  ✓ Part 3 完成\n")
        
        self.add_response_to_frontier(state, metrics, "baseline", answer_type="baseline")
        
        best_metrics = metrics
        best_state = state
        
        evolution_results['baseline'] = {
            'metrics': {
                'accuracy': metrics.accuracy,
                'coverage': metrics.coverage,
                'source_attribution': metrics.source_attribution,
                'coherence': metrics.coherence,
                'efficiency': metrics.efficiency,
                'composite': metrics.composite_score()
            }
        }
        
        # 进化循环
        # 循环中记录每轮的诊断和改进
        for cycle in range(1, num_cycles + 1):
            print(f"\n{'='*80}")
            print(f"🧬 Part 4: 自进化引擎 - 循环 #{cycle}/{num_cycles}")
            print(f"{'='*80}\n")
            
            # Part 4: 自进化循环（诊断→变异→评估）
            # 【改进】每一轮都对标上一轮的最高评分
            best_mutation, diagnosis = self.evolution_cycle.run_cycle(
                question,
                best_metrics,  # 上一轮最高评分作为本轮基准
                cycle_num=cycle
            )
            
            cycle_result = {
                'cycle_num': cycle,
                'diagnosis': diagnosis,
                'mutation': best_mutation
            }
            
            # 【新增】记录诊断的LLM交互（来自PerformanceDiagnostician）
            if diagnosis and 'diagnosis_prompt' in diagnosis:
                self._record_llm_interaction(
                    prompt=diagnosis['diagnosis_prompt'],
                    response=diagnosis['diagnosis_response'],
                    question=question,
                    interaction_type=f'diagnosis_cycle{cycle}',
                    metadata={
                        'cycle': cycle,
                        'primary_weakness': diagnosis.get('primary_weakness'),
                        'weakness_score': diagnosis.get('weakness_score')
                    }
                )
            
            if best_mutation:
                # Part 2: 使用改进的配置重新处理
                print("\n📋 Part 2: 用改进配置重新处理")
                print(f"  配置: {best_mutation['config'].get('name')}")
                
                # 【改进】持久化第cycle轮的最优配置为下一轮的初始值
                print(f"\n  🔧 【循环衔接】应用第{cycle}轮最优配置作为第{cycle+1}轮的初始配置")
                self.evolution_cycle._apply_mutation_config(best_mutation['config'])
                print(f"  ✓ 配置已更新\n")
                
                logger.info(f"  ✅ 第{cycle}轮最优配置已应用: {best_mutation['config'].get('name')}")
                logger.info(f"  ✅ 当前检索配置: vector_chunks={self.evolution_cycle.navigator._vector_chunks}, markdown_blocks={self.evolution_cycle.navigator._markdown_blocks}")
                
                # 【修复】不在这里重新评估，而是在下一轮循环开始时作为基准
                best_metrics = best_mutation['metrics']
                # 【关键修复】直接使用优化循环中定到的state，而不是重新处理
                best_state = best_mutation['state']
                
                # 保存循环结果（不含改进值，因为改进值在run_cycle中已计算）
                self.add_response_to_frontier(best_state, best_metrics, f"variant_cycle{cycle}", answer_type="optimized")
                
                cycle_result['best_metrics'] = best_metrics
                cycle_result['best_state'] = best_state
            else:
                # 本轮没有改进方案，使用基准评分继续下一轮
                cycle_result['best_metrics'] = best_metrics
                cycle_result['best_state'] = best_state
            
            evolution_results['cycles'].append(cycle_result)
        
        # Part 5: Pareto前沿分析
        print(f"\n{'='*80}")
        print("🎯 Part 5: Pareto前沿导航")
        print(f"{'='*80}\n")
        
        self.analyze_and_visualize()
        
        # 【关键步骤】从 Pareto 前沿中选择最佳答案
        best_answer, best_answer_state, best_candidate = self._select_best_answer_from_pareto()
        
        # 【改进】最终的最优配置来自最后一轮循环
        # 直接使用best_metrics，无需重新评估
        if best_answer_state:
            logger.info(f"\n✅ 最终最优配置的性能指标（第{num_cycles}轮）：")
            logger.info(f"   准确性: {best_metrics.accuracy:.3f}")
            logger.info(f"   覆盖率: {best_metrics.coverage:.3f}")
            logger.info(f"   来源归属: {best_metrics.source_attribution:.3f}")
            logger.info(f"   连贯性: {best_metrics.coherence:.3f}")
            logger.info(f"   效率: {best_metrics.efficiency:.3f}")
            logger.info(f"   综合评分: {best_metrics.composite_score():.3f}")
            
            # 与基线对比
            baseline_composite = evolution_results['baseline']['metrics']['composite']
            final_composite = best_metrics.composite_score()
            total_improvement = final_composite - baseline_composite
            logger.info(f"\n📊 基线 vs 最终对比：")
            logger.info(f"   基线评分: {baseline_composite:.3f}")
            logger.info(f"   最终评分: {final_composite:.3f}")
            logger.info(f"   总体改进: {total_improvement:+.3f}")
        
        # 【关键修复】不重新生成新的LLM交互，而是直接复制最优配置对应的输出文件
        # 最优配置的答案已经在之前的处理中保存过了，我们需要找到并复制它
        if best_answer_state and best_answer_state.llm_interaction_id:
            # 从最优配置找到对应的输出文件
            best_interaction_id = best_answer_state.llm_interaction_id
            logger.info(f"  ✓ 最佳答案来自LLM交互: {best_interaction_id}")
            
            # 直接从对应的interaction文件中复制输出到best_output.txt
            self._copy_best_output_from_interaction(best_interaction_id, best_answer_state, question)
        else:
            logger.warning("⚠️  最优配置的状态中没有llm_interaction_id，使用标准流程记录")
            # 备用方案：重新记录一次
            if best_answer_state and best_answer_state.final_answer:
                final_prompt = self._build_answer_generation_prompt(best_answer_state, question)
                self._record_llm_interaction(
                    prompt=final_prompt,
                    response=best_answer_state.final_answer,
                    question=question,
                    interaction_type='answer_generation_final',
                    metadata={
                        'stage_label': 'final',
                        'best_candidate_version': best_candidate.version if best_candidate else 'unknown',
                        'evidence_sources': best_answer_state.evidence_sources,
                        'fusion_confidence': best_answer_state.fusion_confidence
                    }
                )
        
        
        evolution_results['best_variant'] = {
            'metrics': {
                'accuracy': best_metrics.accuracy,
                'coverage': best_metrics.coverage,
                'source_attribution': best_metrics.source_attribution,
                'coherence': best_metrics.coherence,
                'efficiency': best_metrics.efficiency,
                'composite': best_metrics.composite_score()
            },
            'cycle': num_cycles,
            'total_improvement': best_metrics.composite_score() - evolution_results['baseline']['metrics']['composite']
        }
        
        # 保存最佳答案和对应的状态
        evolution_results['best_answer'] = best_answer
        evolution_results['best_answer_state'] = best_answer_state
        evolution_results['best_candidate_version'] = best_candidate.version if best_candidate else "unknown"
        
        print(f"\n{'='*80}")
        print("✅ 完整的自进化循环完成 (Part 1-5)")
        print(f"{'='*80}\n")
        print(f"🔹 Part 1: 知识武库已应用")
        print(f"🔹 Part 2: 多智能体处理 1(基线) + {num_cycles}(循环) = {num_cycles + 1} 次")
        print(f"🔹 Part 3: 性能评估 {num_cycles + 1} 次")
        print(f"🔹 Part 4: 自进化循环 {num_cycles} 次")
        print(f"🔹 Part 5: Pareto前沿分析完成")
        print()
        baseline_score = evolution_results['baseline']['metrics']['composite']
        final_score = evolution_results['best_variant']['metrics']['composite']
        total_improvement = evolution_results['best_variant']['total_improvement']
        print(f"📊 【优化效果对比】")
        print(f"   基线评分: {baseline_score:.3f}")
        print(f"   最终评分: {final_score:.3f} (第{num_cycles}轮)")
        print(f"   总体改进: {total_improvement:+.3f}\n")
        
        # 打印最佳答案
        self._print_best_answer_summary(best_answer, best_answer_state, best_candidate)
        
        return evolution_results
    
    def _select_best_answer_from_pareto(self) -> tuple:
        """
        从Pareto前沿中选择最佳答案
        
        【关键改进】：最佳答案必须来自最优配置的输出
        选择策略：
        1. 确保Pareto前沿已被正确识别
        2. 从Pareto最优方案中选择综合评分最高的
        3. 从选定的方案对应的pipeline_state中获取最终答案
        
        返回：
            tuple: (best_answer, best_answer_state, best_candidate)
        """
        # 【关键修复】确保Pareto前沿已被正确识别
        if not self.frontier.pareto_front:
            logger.info("🔍 Pareto前沿尚未被识别，现在开始识别...")
            self.frontier.identify_pareto_front()
        
        # 从 Pareto 前沿中选择综合评分最高的
        if self.frontier.pareto_front:
            # 【优化】优先从优化方案（非基线）中选择
            optimized_candidates = [c for c in self.frontier.pareto_front if c.version != "baseline"]
            if optimized_candidates:
                best_candidate = max(
                    optimized_candidates,
                    key=lambda c: c.evaluation.composite_score()
                )
                logger.info(f"✅ 从 {len(optimized_candidates)} 个优化方案中选择最佳方案")
            else:
                # 备用：如果没有优化方案，从Pareto前沿中选择
                best_candidate = max(
                    self.frontier.pareto_front,
                    key=lambda c: c.evaluation.composite_score()
                )
                logger.info(f"✅ 从 {len(self.frontier.pareto_front)} 个Pareto最优方案中选择最佳方案")
        else:
            # 备用方案：如果Pareto前沿仍为空，选择所有候选中综合评分最高的
            logger.warning("⚠️  Pareto前沿识别失败，从所有候选方案中选择最优")
            best_candidate = max(
                self.frontier.candidates,
                key=lambda c: c.evaluation.composite_score()
            ) if self.frontier.candidates else None
        
        if not best_candidate:
            logger.error("❌ 没有可用的方案")
            return None, None, None
        
        # 【关键改进】从最优配置的pipeline_state中获取最终答案
        best_answer_state = best_candidate.pipeline_state
        best_answer = ""
        
        if best_answer_state and hasattr(best_answer_state, 'final_answer'):
            best_answer = best_answer_state.final_answer or ""
        else:
            logger.warning("⚠️  无法从最优配置的pipeline_state中获取答案")
        
        logger.info(f"\n🎆 选择了最佳方案: {best_candidate.version}")
        logger.info(f"  推理过程: {best_candidate.reasoning}")
        logger.info(f"  生成方法: {best_candidate.generation_method}")
        logger.info(f"  综合评分: {best_candidate.evaluation.composite_score():.3f}")
        
        # 【新增】打印选择的方案的详细信息
        scores = best_candidate.evaluation.to_dict()
        logger.info(f"  维度评分:")
        logger.info(f"    - 准确性:      {scores['accuracy']:.3f}")
        logger.info(f"    - 图谱利用度:  {scores['graph_utilization']:.3f}")
        logger.info(f"    - 来源归属:    {scores['source_attribution']:.3f}")
        logger.info(f"    - 连贯性:      {scores['coherence']:.3f}")
        logger.info(f"    - 效率:        {scores['efficiency']:.3f}")
        
        if best_answer_state and hasattr(best_answer_state, 'llm_interaction_id'):
            logger.info(f"  LLM交互ID: {best_answer_state.llm_interaction_id}")
        
        logger.info(f"  ✓ 最佳答案来自此方案的pipeline_state")
        
        return best_answer, best_answer_state, best_candidate
    
    def _print_best_answer_summary(self, best_answer: str, best_answer_state, best_candidate):
        """
        打印最佳答案摘要
        """
        if not best_candidate:
            logger.warning("⚠️  没有最佳答案可打印")
            return
        
        print(f"\n{'='*80}")
        print("🏆 最佳答案 (Best Answer from Pareto Frontier)")
        print(f"{'='*80}\n")
        
        # 方案信息
        print(f"💻 方案: {best_candidate.version}")
        print(f"🔗 生成方法: {best_candidate.generation_method}")
        print(f"⏰ 时间戳: {best_candidate.timestamp}")
        print()
        
        # 性能指标
        scores = best_candidate.evaluation.to_dict()
        composite = best_candidate.evaluation.composite_score()
        print(f"📊 性能指标:")
        print(f"  ✓ 准确性 (accuracy):        {scores['accuracy']:.3f}")
        print(f"  ✓ 图谱利用度 (graph_util):  {scores['graph_utilization']:.3f}")
        print(f"  ✓ 来源归属 (attribution):   {scores['source_attribution']:.3f}")
        print(f"  ✓ 连贯性 (coherence):       {scores['coherence']:.3f}")
        print(f"  ✓ 效率 (efficiency):        {scores['efficiency']:.3f}")
        print(f"  ⭐ 综合评分:               {composite:.3f}")
        print()
        
        # 答案内容
        if best_answer:
            print(f"💬 最佳答案内容:")
            print(f"{'-'*80}")
            # 只打印前500个字符预览
            if len(best_answer) > 500:
                print(best_answer)
            else:
                print(best_answer)
            print(f"{'-'*80}")
            
            # 添加文献来源
            if best_answer_state and best_answer_state.doc_sources:
                print(f"\n【文献来源】")
                sources_by_title = {}
                for source in best_answer_state.doc_sources:
                    title = source.get('source', '未知来源')
                    doc_id = source.get('doc_id', 0)
                    if title not in sources_by_title:
                        sources_by_title[title] = []
                    sources_by_title[title].append(doc_id)
                
                # 【修改】处理来源标题和去重
                processed_sources = []
                has_metaso = False
                
                for title in sorted(sources_by_title.keys()):
                    # 需求1：去除milvus前缀
                    clean_title = title
                    if title.startswith('milvus_'):
                        clean_title = title.replace('milvus_', '', 1)
                    
                    # 需求3：分子工具应该跳过
                    if clean_title == '分子工具':
                        continue  # 跳过分子工具
                    
                    # 需求4：秘塔搜索特殊处理
                    if clean_title == '秘塔搜索':
                        has_metaso = True
                        continue  # 暂时跳过，稍后加入末尾
                    
                    # 需求2：最多保留两个文献标题
                    if len(processed_sources) < 2:
                        processed_sources.append(clean_title)
                
                # 需求4：如果有秘塔搜索，加在末尾
                if has_metaso:
                    processed_sources.append('秘塔搜索')
                
                # 打印处理后的来源
                for source_title in processed_sources:
                    print(f"✓ {source_title}")
            
            print()
        
        # 来源信息
        if best_answer_state:
            print(f"📚 来源信息:")
            print(f"  └─ 证据来源: {', '.join(best_answer_state.evidence_sources)}")
            print(f"  └─ 提取实体: {', '.join(best_answer_state.extracted_entities[:5])}")
            print(f"  └─ 知识图谱: {len(best_answer_state.graph_entities)} 个实体")
            print(f"  └─ 向量块数: {len(best_answer_state.vector_chunks)} 个块")
            print(f"  └─ 融合置信度: {best_answer_state.fusion_confidence:.3f}")
            print()
        
        print(f"{'='*80}")
    
    def analyze_and_visualize(self, output_dir: Optional[str] = None):
        """分析Pareto前沿并生成可视化"""
        if not self.frontier.candidates:
            logger.warning("⚠️  没有候选方案，跳过Pareto分析")
            return
        
        logger.info("\n" + "=" * 80)
        logger.info("【Pareto前沿分析】")
        logger.info("=" * 80)
        
        # 识别Pareto前沿
        pareto_front = self.frontier.identify_pareto_front()
        
        # 打印摘要
        self.frontier.print_frontier_summary()
        
        # 权衡分析
        if len(pareto_front) >= 2:
            self.trade_analyzer.print_trade_off_summary()
        
        # 可视化
        if output_dir is None:
            output_dir = os.path.join(PROJECT_ROOT, "pareto_visualizations")
        
        os.makedirs(output_dir, exist_ok=True)
        
        logger.info(f"\n📊 生成可视化到 {output_dir}...")
        
        try:
            # 2D Pareto前沿
            ParetoVisualizer.plot_2d_frontier(
                self.frontier,
                dim1='accuracy',
                dim2='efficiency',
                output_path=os.path.join(output_dir, 'pareto_2d.png')
            )
            
            # 其他可视化
            ParetoVisualizer.plot_parallel_coordinates(
                self.frontier,
                output_path=os.path.join(output_dir, 'pareto_parallel.png')
            )
            
            logger.info("✓ 可视化完成")
        except Exception as e:
            logger.warning(f"⚠️  可视化失败: {e}")
    
    def interactive_demo(self):
        """交互式演示"""
        print("\n" + "=" * 80)
        print("【Part 5 增强版 - 交互式多智能体Pareto导航】")
        print("=" * 80)
        print("\n功能演示：")
        print("  1. 通过多智能体管道处理问题")
        print("  2. Graph RAG + Traditional RAG 混合检索")
        print("  3. 性能评估 (5维评分)")
        print("  4. Pareto前沿分析")
        print("  5. 交互式可视化和决策\n")
        
        variant_counter = 1
        
        while True:
            try:
                question = input("\n📝 请输入问题 (exit 退出): ").strip()
                
                if question.lower() in ['exit', 'quit', 'q']:
                    break
                
                if not question:
                    continue
                
                # 处理问题
                state = self.process_question(question)
                
                # 评估质量
                metrics = self.evaluate_response_quality(state)
                
                # 添加到Pareto前沿
                candidate = self.add_response_to_frontier(
                    state,
                    metrics,
                    variant_name=f"variant_{variant_counter}"
                )
                variant_counter += 1
                
                # Pareto分析
                if variant_counter > 2:
                    self.analyze_and_visualize()
                
                # 询问是否继续
                cont = input("\n是否继续分析? (y/n, 默认y): ").strip().lower()
                if cont == 'n':
                    break
                
            except KeyboardInterrupt:
                print("\n\n👋 已中止！")
                break
        
        # 最后的分析
        if self.frontier.candidates:
            logger.info("\n【最终Pareto前沿分析】")
            self.analyze_and_visualize()
            
            # 导出结果
            output_file = os.path.join(
                PROJECT_ROOT,
                f"part5_enhanced_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
            self._export_results(output_file)
    
    def _export_results(self, filepath: str):
        """导出结果到JSON"""
        results = {
            "timestamp": datetime.now().isoformat(),
            "system_config": {
                "use_graph_rag": self.use_graph_rag,
                "use_traditional_rag": self.use_traditional_rag
            },
            "candidates": [],
            "pareto_front": []
        }
        
        # 记录所有候选方案
        for candidate in self.frontier.candidates:
            results["candidates"].append({
                "version": candidate.version,
                "scores": candidate.evaluation.to_dict(),
                "composite": candidate.evaluation.composite_score(),
                "generation_method": candidate.generation_method
            })
        
        # 记录Pareto前沿
        for candidate in self.frontier.pareto_front:
            results["pareto_front"].append({
                "version": candidate.version,
                "scores": candidate.evaluation.to_dict(),
                "composite": candidate.evaluation.composite_score()
            })
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            logger.info(f"✓ 结果已导出到 {filepath}")
        except Exception as e:
            logger.error(f"❌ 导出失败: {e}")
    
    def close(self):
        """关闭系统"""
        self.arsenal.close()
        logger.info("✓ 增强的Part 5系统已关闭")
        
        # 【已禁用】生成LLM交互汇总报告 - 不再下载
        # if self.llm_interactions:
        #     self._generate_llm_interaction_report()
    
    def _generate_llm_interaction_report(self):
        """
        【已禁用】生成LLM交互汇总报告 - 不再下载汇总文件
        
        原有方法已被禁用，不再生成 llm_interactions_summary_*.json
        """
        logger.info("  ⏭️  LLM交互汇总报告已禁用")
        # 【已保存】原有的汇总逻辑已被禁用


def main():
    """主入口"""
    parser = argparse.ArgumentParser(
        description='Part 5 增强版: Multi-Agent Collaborative Pareto Frontier Navigation'
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        help='启用调试模式'
    )
    
    parser.add_argument(
        '--graph-rag',
        action='store_true',
        default=True,
        help='使用Graph RAG (默认)'
    )
    
    parser.add_argument(
        '--no-graph-rag',
        action='store_false',
        dest='graph_rag',
        help='禁用Graph RAG'
    )
    
    parser.add_argument(
        '--traditional-rag',
        action='store_true',
        default=True,
        help='使用传统RAG (默认)'
    )
    
    parser.add_argument(
        '--no-traditional-rag',
        action='store_false',
        dest='traditional_rag',
        help='禁用传统RAG'
    )
    
    parser.add_argument(
        '--demo-question',
        type=str,
        default=None,
        help='演示问题 (不指定则进入交互模式)'
    )
    
    parser.add_argument(
        '--evolution-cycles',
        type=int,
        default=0,
        help='自进化循环数。指定时自动进入自进化模式（例如 --evolution-cycles 2）'
    )
    
    args = parser.parse_args()
    
    try:
        # 初始化系统
        system = EnhancedPart5System(
            use_graph_rag=args.graph_rag,
            use_traditional_rag=args.traditional_rag,
            debug=args.debug
        )
        
        if args.demo_question:
            # 演示模式
            logger.info(f"\n📝 演示问题: {args.demo_question}")
            
            if args.evolution_cycles >= 2:
                # 自进化模式: 完整的 Part 1-5 流程并应用 Part 4 自进化
                logger.info(f"🧬 运行完整的自进化系统 ({args.evolution_cycles} 个循环)")
                evolution_results = system.run_complete_evolution_cycle(
                    args.demo_question,
                    num_cycles=args.evolution_cycles
                )
            else:
                # 标准演示模式（仅运行一次）
                logger.info("🎯 标准模式（仅运行一次处理）")
                logger.info("📋 提示: 使用 --evolution-cycles 2 或更高值来运行自进化并应用 Part 4")
                state = system.process_question(args.demo_question)
                metrics = system.evaluate_response_quality(state)
                system.add_response_to_frontier(state, metrics, "demo_response")
                system.analyze_and_visualize()
        
        else:
            # 交互模式
            system.interactive_demo()
        
        # 关闭系统
        system.close()
        
    except Exception as e:
        logger.error(f"❌ 系统错误: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
