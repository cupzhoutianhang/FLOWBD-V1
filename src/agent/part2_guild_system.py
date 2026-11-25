"""
Part 2: The Inner Loop - The "Trial Design Guild" - A Collaborative Agent Team

多智能体协作系统，结合 Graph RAG + RAG 的知识武库，
实现领域问题的自动分析和综合回答。

核心概念（借鉴code.ipynb）：
1. Planner Agent - 任务规划和分解
2. Retrieval Agents - 多源信息检索（Markdown、Milvus、Neo4j）
3. Analyst Agent - 数据分析和关系提取
4. Synthesizer Agent - 信息融合和最终生成

数据源配置：
- Markdown文档：已转换的PDF内容
- Milvus向量库：传统RAG检索
- Neo4j图数据库：知识图谱关系
- Kimi API：大模型调用
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

# 此文件位于 src/agent/graphrag_and_rag/agent/ 目录
# 不需要重新配置 sys.path（已由 run_part5_enhanced.py 配置）

# 导入 Part 1 的知识武库
from agent.part1_knowledge_arsenal import (
    KnowledgeArsenal,
    LLMConfig,
    DataManager,
    EmbeddingManager,
    KnowledgeBaseConnector,
    GPU_AVAILABLE,
    DEVICE
)

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# Part 2.1: Guild SOP 和 State 定义
# ============================================================================

@dataclass
class SpecialistFinding:
    """专家Agent的发现结构"""
    agent_name: str
    task_description: str
    findings: str
    confidence: float = 0.8
    data_sources: List[str] = field(default_factory=list)
    execution_time: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class GuildSOP:
    """Guild的标准操作流程 - 可演化的配置"""
    planner_prompt: str
    retriever_prompt_template: str
    synthesizer_prompt: str
    analyst_prompt: str
    researcher_retriever_k: int = 3
    use_graph_rag: bool = True
    use_analyst: bool = True
    confidence_threshold: float = 0.5
    max_iterations: int = 1
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "planner_prompt": self.planner_prompt[:100] + "...",
            "researcher_retriever_k": self.researcher_retriever_k,
            "use_graph_rag": self.use_graph_rag,
            "use_analyst": self.use_analyst,
            "confidence_threshold": self.confidence_threshold,
            "max_iterations": self.max_iterations
        }


@dataclass
class GuildState:
    """Guild工作流的状态"""
    initial_request: str
    request_id: str
    plan: Optional[Dict[str, Any]] = None
    specialist_outputs: List[SpecialistFinding] = field(default_factory=list)
    final_synthesis: Optional[str] = None
    sop: Optional[GuildSOP] = None
    execution_log: List[str] = field(default_factory=list)
    graph_context: Dict[str, Any] = field(default_factory=dict)
    
    def log(self, message: str):
        """记录执行日志"""
        timestamp = datetime.now().isoformat()
        log_msg = f"[{timestamp}] {message}"
        self.execution_log.append(log_msg)
        logger.info(f"[Guild-{self.request_id[:8]}] {message}")


# ============================================================================
# Part 2.2: 规划Agent - Planner
# ============================================================================

class PlannerAgent:
    """
    规划Agent - 将用户请求分解为具体的specialist任务
    
    对应 code.ipynb 中的 Planner Agent，但针对液流电池/电化学领域优化
    """
    
    def __init__(self, llm_config: LLMConfig):
        """初始化规划Agent"""
        self.llm = llm_config
        logger.info("✓ Planner Agent 初始化")
    
    def create_plan(self, request: str, sop: GuildSOP) -> Dict[str, Any]:
        """为请求创建任务计划"""
        logger.info(f"📋 [Planner] 分析请求并创建计划...")
        
        prompt = f"""{sop.planner_prompt}

用户请求：{request}

请返回JSON格式的任务计划，包含：
{{
    "analysis": "对请求的简短分析",
    "tasks": [
        {{
            "task_id": 1,
            "specialist": "Researcher|Analyst|GraphExplorer",
            "description": "具体任务描述",
            "priority": "high|medium|low",
            "required": true
        }}
    ],
    "reasoning": "任务规划的原因"
}}

仅返回JSON，不要其他内容。"""
        
        try:
            response = self.llm.call_llm(
                prompt,
                temperature=0.0,
                max_tokens=1000
            )
            
            # 清理代码标记
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            
            plan = json.loads(response.strip())
            logger.info(f"  ✓ 规划完成: {len(plan.get('tasks', []))} 个任务")
            return plan
            
        except json.JSONDecodeError as e:
            logger.warning(f"  ⚠️ JSON解析失败: {e}，使用默认计划")
            return {
                "analysis": "使用默认计划",
                "tasks": [
                    {"task_id": 1, "specialist": "Researcher", "description": request, "priority": "high", "required": True},
                    {"task_id": 2, "specialist": "Analyst", "description": f"分析相关信息", "priority": "medium", "required": True}
                ],
                "reasoning": "默认计划"
            }
        except Exception as e:
            logger.error(f"  ❌ 规划失败: {e}")
            return {"analysis": "规划失败", "tasks": [], "reasoning": str(e)}


# ============================================================================
# Part 2.3: 多源检索Agent - Retriever
# ============================================================================

class ResearcherAgent:
    """
    研究Agent - 从Markdown和Milvus检索相关信息
    
    对应 code.ipynb 中的 Medical Researcher Agent，但用于通用领域
    """
    
    def __init__(self, data_manager: DataManager, kb_connector: KnowledgeBaseConnector,
                 embedding_manager: EmbeddingManager):
        """初始化研究Agent"""
        self.data_manager = data_manager
        self.kb = kb_connector
        self.embedding = embedding_manager
        logger.info("✓ Researcher Agent 初始化")
    
    def research(self, query: str, top_k: int = 5) -> SpecialistFinding:
        """执行多源检索"""
        logger.info(f"🔍 [Researcher] 检索: {query[:60]}...")
        
        import time
        import torch
        import numpy as np
        
        start_time = time.time()
        
        try:
            # 检查embedding模型是否可用
            if not self.embedding.embedding_model or not self.embedding.embedding_tokenizer:
                logger.warning("  ⚠️ Embedding模型未加载，跳过向量化查询")
                # 直接使用基于关键词的检索或返回空结果
                doc_blocks = []
            else:
                # 生成查询向量
                try:
                    if not hasattr(self, '_model_on_device'):
                        self.embedding.embedding_model = self.embedding.embedding_model.to(DEVICE)
                        self._model_on_device = True
                    
                    inputs = self.embedding.embedding_tokenizer(
                        query,
                        return_tensors="pt",
                        padding=True,
                        truncation=True,
                        max_length=512
                    )
                    
                    inputs = {k: v.to(DEVICE) for k, v in inputs.items()}
                    
                    with torch.no_grad():
                        outputs = self.embedding.embedding_model(**inputs)
                        query_vector = outputs.last_hidden_state[:, 0, :].cpu().numpy().flatten()
                    
                    # L2归一化
                    query_vector = query_vector / (np.linalg.norm(query_vector) + 1e-8)
                    query_vector = query_vector.tolist()
                    
                    # 从Milvus检索
                    doc_blocks = self.kb.search_milvus(query_vector, top_k)
                except RuntimeError as cuda_err:
                    # CUDA错误，降级处理
                    logger.warning(f"  ⚠️ CUDA错误，跳过向量化查询: {str(cuda_err)[:50]}")
                    doc_blocks = []
            
            if GPU_AVAILABLE:
                torch.cuda.empty_cache()
            
            # 组织发现
            findings_parts = []
            sources = []
            confidences = []
            
            for i, block in enumerate(doc_blocks, 1):
                content = block.get("content", "")
                distance = block.get("distance", 0)
                doc_id = block.get("doc_id", "unknown")
                
                findings_parts.append(
                    f"\n【来源{i}】({doc_id}, 相关度: {distance:.2f})\n"
                    f"{content[:400]}\n"
                )
                sources.append(doc_id)
                confidences.append(distance)
            
            findings_text = "".join(findings_parts) if findings_parts else "暂无检索结果（Embedding模型未加载或未找到相关文档）"
            confidence = np.mean(confidences) if confidences else 0.2
            
            execution_time = time.time() - start_time
            
            logger.info(f"  ✓ 检索完成: {len(doc_blocks)} 个结果，置信度: {confidence:.2f}")
            
            return SpecialistFinding(
                agent_name="Researcher",
                task_description=query,
                findings=findings_text,
                confidence=confidence,
                data_sources=sources,
                execution_time=execution_time
            )
            
        except Exception as e:
            logger.error(f"  ❌ 检索失败: {e}")
            return SpecialistFinding(
                agent_name="Researcher",
                task_description=query,
                findings=f"检索失败: {str(e)}",
                confidence=0.0,
                data_sources=[]
            )


# ============================================================================
# Part 2.4: 图谱分析Agent - Graph Explorer
# ============================================================================

class GraphExplorerAgent:
    """
    图谱探索Agent - 从Neo4j知识图谱提取关系和实体
    
    对应 code.ipynb 中的领域特定Agent，但专注于图关系
    """
    
    def __init__(self, kb_connector: KnowledgeBaseConnector, llm_config: LLMConfig):
        """初始化图谱探索Agent"""
        self.kb = kb_connector
        self.llm = llm_config
        logger.info("✓ Graph Explorer Agent 初始化")
    
    def explore_graph(self, entities: List[str]) -> SpecialistFinding:
        """探索知识图谱"""
        logger.info(f"🔗 [GraphExplorer] 查询实体: {entities}")
        
        import time
        start_time = time.time()
        
        try:
            findings_parts = []
            all_entities = {}
            all_relations = []
            
            for entity in entities[:5]:  # 限制查询实体数
                # 查询实体
                cypher = f"""
                    MATCH (n) 
                    WHERE toLower(n.name) CONTAINS toLower('{entity}')
                    RETURN n.name as name, n.type as type, properties(n) as props
                    LIMIT 5
                """
                
                try:
                    results = self.kb.query_neo4j(cypher)
                    
                    if results:
                        findings_parts.append(f"\n【实体: {entity}】\n")
                        for record in results:
                            name = record.get('name', 'unknown')
                            entity_type = record.get('type', 'unknown')
                            findings_parts.append(f"  - {name} ({entity_type})\n")
                            all_entities[name] = entity_type
                    
                    # 查询关系
                    rel_cypher = f"""
                        MATCH (n)-[r]->(m)
                        WHERE toLower(n.name) CONTAINS toLower('{entity}')
                        RETURN type(r) as rel_type, m.name as target
                        LIMIT 10
                    """
                    
                    rel_results = self.kb.query_neo4j(rel_cypher)
                    
                    if rel_results:
                        findings_parts.append(f"  【关系】\n")
                        for rel in rel_results:
                            rel_type = rel.get('rel_type', 'unknown')
                            target = rel.get('target', 'unknown')
                            findings_parts.append(f"    → {rel_type} → {target}\n")
                            all_relations.append((entity, rel_type, target))
                
                except Exception as e:
                    logger.warning(f"    查询实体 {entity} 失败: {e}")
            
            findings_text = "".join(findings_parts) if findings_parts else "未找到相关实体"
            confidence = 0.8 if all_entities else 0.3
            
            execution_time = time.time() - start_time
            
            logger.info(f"  ✓ 图谱探索完成: {len(all_entities)} 个实体, {len(all_relations)} 条关系")
            
            return SpecialistFinding(
                agent_name="GraphExplorer",
                task_description=f"探索实体: {', '.join(entities)}",
                findings=findings_text,
                confidence=confidence,
                data_sources=["Neo4j图数据库"],
                execution_time=execution_time
            )
            
        except Exception as e:
            logger.error(f"  ❌ 图谱探索失败: {e}")
            return SpecialistFinding(
                agent_name="GraphExplorer",
                task_description=f"探索实体: {', '.join(entities)}",
                findings=f"图谱查询失败: {str(e)}",
                confidence=0.0
            )


# ============================================================================
# Part 2.5: 综合Agent - Synthesizer
# ============================================================================

class SynthesizerAgent:
    """
    综合Agent - 融合多个specialist的发现，生成最终回答
    
    对应 code.ipynb 中的 Criteria Synthesizer Agent
    """
    
    def __init__(self, llm_config: LLMConfig):
        """初始化综合Agent"""
        self.llm = llm_config
        logger.info("✓ Synthesizer Agent 初始化")
    
    def synthesize(self, state: GuildState) -> str:
        """综合所有发现生成最终答案"""
        logger.info("📝 [Synthesizer] 综合信息并生成答案...")
        
        # 收集所有发现
        findings_context = ""
        for output in state.specialist_outputs:
            findings_context += f"\n【{output.agent_name}】(置信度: {output.confidence:.2f})\n"
            findings_context += f"任务: {output.task_description}\n"
            findings_context += f"发现:\n{output.findings}\n"
            findings_context += "-" * 60 + "\n"
        
        prompt = f"""{state.sop.synthesizer_prompt}

用户原始请求：{state.initial_request}

收集到的专家发现：
{findings_context}

请基于以上信息，生成一个全面、准确、结构清晰的回答。"""
        
        try:
            response = self.llm.call_llm(
                prompt,
                temperature=0.0,
                max_tokens=2000
            )
            
            logger.info("  ✓ 综合完成，生成最终答案")
            return response
            
        except Exception as e:
            logger.error(f"  ❌ 综合失败: {e}")
            return f"综合信息失败，原因: {str(e)}"


# ============================================================================
# Part 2.6: Guild 主协调器
# ============================================================================

class TrialDesignGuild:
    """
    试验设计Guild - 多智能体协作系统的主协调器
    
    对应 code.ipynb 中的完整 Guild Graph，但集成到了 Part 1 的知识武库
    """
    
    def __init__(self, arsenal: KnowledgeArsenal, sop: GuildSOP):
        """初始化Guild"""
        self.arsenal = arsenal
        self.sop = sop
        self.llm = arsenal.get_llm()
        
        # 初始化各个Agent
        self.planner = PlannerAgent(arsenal.get_llm())
        self.researcher = ResearcherAgent(
            arsenal.data_manager,
            arsenal.get_kb_connector(),
            arsenal.get_embedding_manager()
        )
        self.graph_explorer = GraphExplorerAgent(
            arsenal.get_kb_connector(),
            arsenal.get_llm()
        )
        self.synthesizer = SynthesizerAgent(arsenal.get_llm())
        
        logger.info("✓ Trial Design Guild 初始化完成")
    
    def process_request(self, request: str) -> Tuple[str, GuildState]:
        """
        处理用户请求的完整流程
        
        步骤：
        1. Planner Agent - 分解任务
        2. Specialist Agents - 并行执行任务
        3. Synthesizer Agent - 融合结果
        """
        
        # 创建State
        request_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        state = GuildState(
            initial_request=request,
            request_id=request_id,
            sop=self.sop
        )
        
        state.log(f"开始处理请求")
        
        # 步骤1: 规划
        state.log("👤 步骤1: Planner Agent 创建任务计划")
        plan = self.planner.create_plan(request, self.sop)
        state.plan = plan
        state.log(f"  生成 {len(plan.get('tasks', []))} 个任务")
        
        # 步骤2: 执行specialist任务
        state.log("👥 步骤2: 并行执行Specialist Agent")
        tasks = plan.get('tasks', [])
        
        for task in tasks:
            specialist = task.get('specialist', 'Researcher')
            description = task.get('description', '')
            
            if specialist == "Researcher":
                state.log(f"  [Researcher] 执行: {description[:50]}...")
                result = self.researcher.research(description, self.sop.researcher_retriever_k)
                state.specialist_outputs.append(result)
                
            elif specialist == "GraphExplorer":
                state.log(f"  [GraphExplorer] 执行: {description[:50]}...")
                # 用LLM从描述中提取关键实体
                entity_prompt = f"""从以下查询中提取最多5个关键实体名称，用逗号分隔，不需要其他说明。

查询: {description}

关键实体:"""
                entity_response = self.llm.call_llm(entity_prompt, temperature=0.0, max_tokens=100)
                # 提取实体
                entities = [e.strip() for e in entity_response.split(',') if e.strip()]
                entities = entities[:3] if entities else [""]
                result = self.graph_explorer.explore_graph(entities)
                state.specialist_outputs.append(result)
                
            elif specialist == "Analyst":
                state.log(f"  [Analyst] 执行数据分析")
                # 占位符
                result = SpecialistFinding(
                    agent_name="Analyst",
                    task_description=description,
                    findings="分析结果（待实现）",
                    confidence=0.5
                )
                state.specialist_outputs.append(result)
        
        # 步骤3: 综合
        state.log("🔗 步骤3: Synthesizer Agent 融合信息")
        final_answer = self.synthesizer.synthesize(state)
        state.final_synthesis = final_answer
        
        state.log("✅ 请求处理完成")
        
        return final_answer, state


# ============================================================================
# Part 2.7: 默认Guild SOP配置
# ============================================================================

def create_default_guild_sop() -> GuildSOP:
    """创建默认的Guild SOP配置"""
    
    return GuildSOP(
        planner_prompt="""你是一个化工和液流电池领域的智能任务规划器。分析用户请求，将其分解为具体的specialist任务。

【重要约束】
你的知识库专门针对液流电池和相关化工领域。只处理与以下相关的问题：
- 液流电池的工作原理、性能、材料
- 电解质、离子交换膜、电极材料等电池组件
- 电池化学、电化学、能量密度等技术指标
- 商业应用和发展趋势

如果用户问题与液流电池无关（如医疗、生物、医学工具等），礼貌地说明这不是你的专长领域。

考虑以下specialist类型：
- Researcher: 用于检索文献和文档信息
- GraphExplorer: 用于查询知识图谱中的实体和关系
- Analyst: 用于进行数据分析和统计

为每个任务明确指定specialist、优先级和描述。""",
        
        retriever_prompt_template="""基于以下查询，从知识库中检索相关信息：{query}

请提供：
1. 相关的文献或文档片段
2. 每个片段的相关性得分
3. 内容的简要总结""",
        
        synthesizer_prompt="""你是一个信息综合专家。你的任务是整合来自多个专家Agent的发现，
生成一个全面、准确、结构清晰的回答。

要求：
1. 基于所有提供的发现进行综合
2. 明确引用每个发现的来源
3. 标记置信度较低的信息
4. 逻辑清晰，层次分明""",
        
        analyst_prompt="""你是一个数据分析专家。基于提供的数据进行分析。""",
        
        researcher_retriever_k=5,
        use_graph_rag=True,
        use_analyst=False,
        confidence_threshold=0.5,
        max_iterations=1
    )


if __name__ == "__main__":
    # 快速测试
    logger.info("=" * 80)
    logger.info("Part 2: Trial Design Guild 系统")
    logger.info("=" * 80)
    
    print("\n✓ Part 2 多智能体协作系统已定义")
    print("  - PlannerAgent: 任务规划")
    print("  - ResearcherAgent: 多源信息检索")
    print("  - GraphExplorerAgent: 知识图谱查询")
    print("  - SynthesizerAgent: 信息融合")
    print("  - TrialDesignGuild: 主协调器")
