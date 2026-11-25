"""
Agent 定义与状态管理
整合 code.ipynb 中的 Agent 框架与 Graph RAG + RAG 系统

包含：
1. AgentState - 所有Agent共享的状态结构
2. 基础Agent节点实现（Planning Agent, Retrieval Agent等）
3. Agent执行工具函数
"""

import json
import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class QueryIntent(Enum):
    """查询意图枚举"""
    SYNTHESIS = "synthesis"                  # 合成方法
    REACTION = "reaction"                    # 反应过程
    PROPERTY = "property"                    # 物理/化学性质
    STRUCTURE = "structure"                  # 结构/官能团
    CHARACTERIZATION = "characterization"    # 表征方法
    APPLICATION = "application"              # 应用场景
    PERFORMANCE = "performance"              # 性能参数
    COMPARISON = "comparison"                # 对比分析
    GENERAL = "general"                      # 通用问题
    OFF_TOPIC = "off_topic"                  # 领域外问题


@dataclass
class AgentState:
    """Agent系统状态 - 所有Agent共享的状态结构
    
    这个数据结构对应 code.ipynb 中的 GuildState，但优化为
    支持 Graph RAG + Traditional RAG 的混合系统
    """
    
    # 基本信息
    request_id: str                          # 请求ID
    initial_request: str                     # 用户初始请求
    
    # 问题解析结果
    parsed_question: Optional[str] = None    # 解析后的问题
    parsed_entities: List[str] = field(default_factory=list)        # 提取的实体
    parsed_intent: QueryIntent = QueryIntent.GENERAL                # 查询意图
    domain_relevant: bool = True                                    # 领域相关性
    
    # 检索结果（多源）
    md_blocks: List[Dict] = field(default_factory=list)             # Markdown检索结果
    graph_entities: Dict[str, Any] = field(default_factory=dict)    # 图谱实体
    graph_relations: List[Dict] = field(default_factory=list)       # 图谱关系
    structured_data: Dict[str, Any] = field(default_factory=dict)   # 结构化数据
    
    # 融合结果
    fused_context: str = ""                  # 融合后的上下文
    fusion_confidence: float = 0.0           # 融合置信度
    
    # 最终输出
    final_answer: str = ""                   # 最终答案
    answer_confidence: float = 0.0           # 答案置信度
    sources_cited: List[str] = field(default_factory=list)          # 引用来源
    
    # 调试信息
    debug_log: List[str] = field(default_factory=list)              # 调试日志
    execution_steps: List[str] = field(default_factory=list)        # 执行步骤记录
    
    def log_step(self, step: str):
        """记录执行步骤"""
        self.execution_steps.append(f"[{datetime.now().isoformat()}] {step}")
        logger.info(f"  {step}")
    
    def log_debug(self, msg: str):
        """记录调试信息"""
        self.debug_log.append(f"[{datetime.now().isoformat()}] {msg}")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "request_id": self.request_id,
            "initial_request": self.initial_request,
            "parsed_question": self.parsed_question,
            "parsed_entities": self.parsed_entities,
            "parsed_intent": self.parsed_intent.value,
            "domain_relevant": self.domain_relevant,
            "final_answer": self.final_answer,
            "answer_confidence": self.answer_confidence,
            "sources_cited": self.sources_cited,
            "execution_steps": self.execution_steps
        }


@dataclass
class ParsedQuestion:
    """解析后的问题结构"""
    original: str                     # 原始问题
    entities: List[str]               # 提取的实体
    intent: QueryIntent               # 查询意图
    target_properties: List[str]      # 目标属性
    is_domain_related: bool           # 是否领域相关
    confidence: float = 0.0           # 解析置信度


class QuestionParsingAgent:
    """问题解析Agent - 对应code.ipynb中的Planner Agent
    
    职责：
    - 提取问题中的实体
    - 判断查询意图
    - 评估领域相关性
    - 确定目标属性
    """
    
    # 意图关键词映射
    INTENT_KEYWORDS = {
        QueryIntent.SYNTHESIS: ["合成", "制备", "synthesis", "prepare", "制造", "生产"],
        QueryIntent.REACTION: ["反应", "机理", "过程", "reaction", "mechanism", "氧化还原"],
        QueryIntent.PROPERTY: ["溶解度", "密度", "粘度", "电导率", "property", "性质"],
        QueryIntent.STRUCTURE: ["结构", "官能团", "分子", "structure", "functional group"],
        QueryIntent.CHARACTERIZATION: ["表征", "测试", "分析", "characterization", "测量"],
        QueryIntent.APPLICATION: ["应用", "用途", "application", "使用"],
        QueryIntent.PERFORMANCE: ["性能", "效率", "容量", "performance", "循环"],
        QueryIntent.COMPARISON: ["对比", "比较", "区别", "comparison", "vs"],
    }
    
    def __init__(self, llm_config):
        """初始化问题解析Agent
        
        Args:
            llm_config: LLM配置对象
        """
        self.llm = llm_config
    
    def parse_question(self, question: str) -> ParsedQuestion:
        """解析问题 - 使用LLM"""
        
        prompt = f"""你是一个专业的液流电池/电化学领域问题解析器。请分析以下问题并提取关键信息。

问题：{question}

请以JSON格式返回，包含以下字段：
{{
    "entities": ["实体1", "实体2"],
    "intent": "synthesis|reaction|property|structure|characterization|application|performance|comparison|general|off_topic",
    "target_properties": ["属性1"],
    "is_domain_related": true/false,
    "confidence": 0.0-1.0
}}

实体提取规则：
- 识别化学物质名称（如PHQ、DHPS、全钒等）
- 识别材料名称（如聚酰亚胺、碳毡、离子交换膜等）
- 识别设备名称（如电解槽、泵等）

意图分类：
- synthesis: 合成方法、制备工艺
- reaction: 反应机理、电化学过程
- property: 物理化学性质
- structure: 分子结构、官能团
- characterization: 表征方法、测试手段
- application: 应用场景、用途
- performance: 性能参数、循环稳定性
- comparison: 对比分析
- general: 领域内通用问题
- off_topic: 与液流电池/化工领域无关

只返回JSON，不要其他内容。"""
        
        logger.info("📝 [Agent] 解析问题...")
        response = self.llm.call_llm(prompt, temperature=0.0, max_tokens=500)
        
        try:
            # 清理代码标记
            response = re.sub(r'```json\s*', '', response)
            response = re.sub(r'```\s*', '', response)
            data = json.loads(response)
            
            intent_str = data.get("intent", "general")
            try:
                intent = QueryIntent(intent_str)
            except ValueError:
                intent = QueryIntent.GENERAL
            
            result = ParsedQuestion(
                original=question,
                entities=data.get("entities", []),
                intent=intent,
                target_properties=data.get("target_properties", []),
                is_domain_related=data.get("is_domain_related", True),
                confidence=data.get("confidence", 0.5)
            )
            
            logger.info(f"  ✓ 实体: {result.entities}")
            logger.info(f"  ✓ 意图: {result.intent.value}")
            logger.info(f"  ✓ 领域相关: {result.is_domain_related}")
            
            return result
            
        except json.JSONDecodeError:
            logger.warning("  ⚠️ JSON解析失败，使用关键词匹配降级方案")
            return self._fallback_parse(question)
    
    def _fallback_parse(self, question: str) -> ParsedQuestion:
        """降级解析 - 基于关键词匹配"""
        question_lower = question.lower()
        
        # 判断意图
        intent = QueryIntent.GENERAL
        for intent_type, keywords in self.INTENT_KEYWORDS.items():
            if any(kw in question_lower for kw in keywords):
                intent = intent_type
                break
        
        # 简单实体提取
        entities = []
        common_entities = ["phq", "dhps", "pi", "pi1", "pi2", "vrfb", "钒", "醌", "聚酰亚胺"]
        for entity in common_entities:
            if entity in question_lower:
                entities.append(entity.upper())
        
        # 领域相关性
        domain_keywords = ["电池", "液流", "电解", "氧化还原", "电极", "电化学", "合成"]
        is_related = any(kw in question for kw in domain_keywords) or len(entities) > 0
        
        return ParsedQuestion(
            original=question,
            entities=entities,
            intent=intent,
            target_properties=[],
            is_domain_related=is_related,
            confidence=0.3
        )


class DocumentRetrievalAgent:
    """文档检索Agent - 从Markdown和Milvus检索
    
    职责：
    - 从Markdown文档库检索相关内容
    - 从Milvus向量库检索相关块
    - 进行Reranking
    """
    
    def __init__(self, kb_connector, embedding_manager, data_manager=None):
        """初始化文档检索Agent
        
        Args:
            kb_connector: 知识库连接器
            embedding_manager: 向量化管理器
            data_manager: 数据管理器（用于流式加载文档）
        """
        self.kb = kb_connector
        self.embedding = embedding_manager
        self.data_manager = data_manager
    
    def retrieve_documents(self, parsed: ParsedQuestion, top_k: int = 5) -> List[Dict]:
        """检索相关文档块"""
        
        logger.info("📚 [Agent] 检索文档...")
        
        if not self.embedding.embedding_model:
            logger.warning("  ⚠️ 向量化模型未加载")
            return []
        
        try:
            import torch
            import numpy as np
            from agent.part1_knowledge_arsenal import DEVICE, GPU_AVAILABLE
            
            # 将模型移到设备（一次性）
            if not hasattr(self, '_device_set'):
                self.embedding.embedding_model = self.embedding.embedding_model.to(DEVICE)
                self._device_set = True
            
            # 生成查询向量
            inputs = self.embedding.embedding_tokenizer(
                parsed.original,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=512
            )
            
            # 将输入移到设备
            inputs = {k: v.to(DEVICE) for k, v in inputs.items()}
            
            with torch.no_grad():
                outputs = self.embedding.embedding_model(**inputs)
                query_vector = outputs.last_hidden_state[:, 0, :].cpu().numpy().flatten()
            
            # L2归一化
            query_vector = query_vector / (np.linalg.norm(query_vector) + 1e-8)
            query_vector = query_vector.tolist()
            
            # 清理GPU中间结果
            if GPU_AVAILABLE:
                torch.cuda.empty_cache()
            
            # 优先从Milvus检索（已预处理的向量库）
            doc_blocks = self.kb.search_milvus(query_vector, top_k)
            logger.info(f"  ✓ 检索到 {len(doc_blocks)} 个文档块")
            
            return doc_blocks
            
        except Exception as e:
            logger.error(f"  ❌ 文档检索失败: {e}")
            return []


class GraphRetrievalAgent:
    """图谱检索Agent - 从Neo4j检索结构化数据
    
    职责：
    - 检索实体属性
    - 检索实体关系
    - 构建上下文图
    """
    
    def __init__(self, kb_connector):
        """初始化图谱检索Agent
        
        Args:
            kb_connector: 知识库连接器
        """
        self.kb = kb_connector
    
    def retrieve_from_graph(self, parsed: ParsedQuestion) -> Tuple[Dict, List]:
        """从知识图谱检索数据"""
        
        logger.info("🔗 [Agent] 查询知识图谱...")
        
        if not self.kb.neo4j_driver:
            logger.warning("  ⚠️ Neo4j不可用")
            return {}, []
        
        entities_data = {}
        relations_data = []
        
        if not parsed.entities:
            return entities_data, relations_data
        
        try:
            for entity in parsed.entities:
                # 查询实体
                cypher = f"""
                    MATCH (n) 
                    WHERE toLower(n.name) CONTAINS toLower('{entity}')
                    RETURN n, labels(n) AS labels
                    LIMIT 5
                """
                
                results = self.kb.query_neo4j(cypher)
                for record in results:
                    if 'n' in record:
                        node = record['n']
                        entities_data[node['name']] = dict(node)
                
                # 查询关系（根据意图）
                rel_cypher = f"""
                    MATCH (n)-[r]->(m)
                    WHERE toLower(n.name) CONTAINS toLower('{entity}')
                    RETURN type(r) AS rel_type, properties(r) AS rel_props, m.name AS target
                    LIMIT 20
                """
                
                rel_results = self.kb.query_neo4j(rel_cypher)
                for record in rel_results:
                    relations_data.append(record)
            
            logger.info(f"  ✓ 检索到 {len(entities_data)} 个实体, {len(relations_data)} 条关系")
            
        except Exception as e:
            logger.error(f"  ❌ 图谱检索失败: {e}")
        
        return entities_data, relations_data


class InformationFusionAgent:
    """信息融合Agent - 对应code.ipynb中的Synthesizer
    
    职责：
    - 融合多源信息（Markdown、向量库、图谱）
    - 去重和对齐
    - 构建结构化上下文
    """
    
    def __init__(self):
        """初始化信息融合Agent"""
        pass
    
    def fuse_information(self,
                        parsed: ParsedQuestion,
                        doc_blocks: List[Dict],
                        graph_entities: Dict,
                        graph_relations: List) -> Tuple[str, float]:
        """融合多源信息"""
        
        logger.info("🔄 [Agent] 融合信息...")
        
        context_parts = []
        confidence_factors = []
        
        # 1. 融合图谱信息
        if graph_entities:
            context_parts.append("## 知识图谱信息\n")
            
            for name, props in graph_entities.items():
                context_parts.append(f"**{name}**")
                for key, value in props.items():
                    if key != 'name' and value:
                        context_parts.append(f"  - {key}: {value}")
            
            confidence_factors.append(0.8 if len(graph_entities) > 0 else 0.3)
        
        # 2. 融合文档信息
        if doc_blocks:
            context_parts.append("\n## 文档检索结果\n")
            
            for i, block in enumerate(doc_blocks[:5], 1):
                content = block.get("content", "")
                score = block.get("distance", 0)
                context_parts.append(f"**[文档{i}]** (相关度: {score:.2f})")
                context_parts.append(content)
                context_parts.append("")
            
            if doc_blocks[0].get("distance", 0) > 0.8:
                confidence_factors.append(0.9)
            elif doc_blocks[0].get("distance", 0) > 0.5:
                confidence_factors.append(0.7)
            else:
                confidence_factors.append(0.4)
        
        # 计算综合置信度
        if confidence_factors:
            confidence = sum(confidence_factors) / len(confidence_factors)
        else:
            confidence = 0.1
        
        fused_text = "\n".join(context_parts)
        logger.info(f"  ✓ 融合完成 (置信度: {confidence:.2f})")
        
        return fused_text, confidence


class AnswerGenerationAgent:
    """答案生成Agent - 对应code.ipynb中的Medical Researcher/Drafter
    
    职责：
    - 生成最终答案
    - 追踪数据来源
    - 格式化输出
    """
    
    # 意图对应的Prompt模板
    INTENT_PROMPTS = {
        QueryIntent.SYNTHESIS: """请基于以下信息回答关于**合成方法**的问题。重点关注：
- 原料和试剂
- 反应条件（温度、时间、溶剂等）
- 反应步骤
- 产率和纯化方法
如有反应方程式，请给出；如有具体数值，带上单位。""",
        
        QueryIntent.REACTION: """请基于以下信息回答关于**反应过程**的问题。重点关注：
- 反应类型和机理
- 反应方程式
- 动力学参数
- 反应条件的影响""",
        
        QueryIntent.PROPERTY: """请基于以下信息回答关于**物化性质**的问题。重点关注：
- 具体数值和单位
- 测试条件
- 与结构的关系
- 影响因素""",
    }
    
    def __init__(self, llm_config):
        """初始化答案生成Agent
        
        Args:
            llm_config: LLM配置对象
        """
        self.llm = llm_config
    
    def generate_answer(self,
                       parsed: ParsedQuestion,
                       fused_context: str,
                       confidence: float) -> str:
        """生成最终答案"""
        
        logger.info("✍️ [Agent] 生成答案...")
        
        # 领域外问题直接回答
        if not parsed.is_domain_related or parsed.intent == QueryIntent.OFF_TOPIC:
            answer = self.llm.call_llm(
                f"请简洁友好地回答这个问题：{parsed.original}\n\n"
                "如果这不是你擅长的领域，请礼貌说明你是液流电池领域的专业助手。",
                temperature=0.0,
                max_tokens=500
            )
            return answer
        
        # 获取意图对应的Prompt
        intent_prompt = self.INTENT_PROMPTS.get(
            parsed.intent,
            "请基于以下信息专业、准确地回答问题。"
        )
        
        # 构建完整Prompt
        prompt = f"""你是液流电池领域的专业知识助手。

{intent_prompt}

---
{fused_context}
---

**用户问题**：{parsed.original}

**回答要求**：
1. 直接回答问题，开门见山，不要废话
2. 如有具体数值，必须带上单位和测试条件
3. 如有反应方程式，必须完整给出
4. 如果信息不足，在最后简短说明缺少什么信息
5. 保持专业学术风格，条理清晰
6. 总字数控制在500字以内

请回答："""
        
        answer = self.llm.call_llm(prompt, temperature=0.0, max_tokens=1200)
        logger.info(f"  ✓ 答案已生成 ({len(answer)} 字符)")
        
        return answer


if __name__ == "__main__":
    # 测试Agent初始化
    from agent.part1_knowledge_arsenal import LLMConfig
    
    llm = LLMConfig()
    
    # 测试问题解析Agent
    parser = QuestionParsingAgent(llm)
    
    test_question = "PHQ有什么官能团？"
    parsed = parser.parse_question(test_question)
    
    print(f"\n✓ 问题解析Agent测试通过")
    print(f"  实体: {parsed.entities}")
    print(f"  意图: {parsed.intent.value}")
    print(f"  领域相关: {parsed.is_domain_related}")
