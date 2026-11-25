"""多智能体协作系统 - 简化架构版本

核心架构：
1. 问题解析 Agent (Question Parsing Agent)
   - 提取问题中的实体
   - 判断查询意图
   - 检测分子相关查询

2. 多源检索 Agent (Multi-Source Retrieval Agent)
   - Graph RAG 检索（知识图谱）
   - Vector RAG 检索（Milvus向量库）
   - Web 搜索（秘塔搜索）
   - 分子查询（可选）

3. 信息融合 Agent (Information Fusion Agent)
   - 整合多源检索结果
   - 去重和对齐信息
   - 构建统一上下文

4. 答案生成 Agent (Answer Generation Agent)
   - 生成最终答案
   - 追踪信息来源
   - 格式化输出
"""

import os
import sys
import json
import logging
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def _safe_print(message: str = "") -> None:
    """Print without allowing a narrow console encoding to abort pipeline work."""
    try:
        print(message)
    except UnicodeError:
        encoding = getattr(sys.stdout, "encoding", None) or "ascii"
        print(str(message).encode(encoding, "backslashreplace").decode(encoding, "replace"))


# ============================================================================
def _post_audit_native_result(answer, native_generation, semantic_audit, final_checks, final_issues):
    """Apply deterministic post-audit gates before a draft can become final.

    A reviewer schema failure is recorded as a degraded audit, not used to throw
    away a draft that still passes all deterministic source constraints. A draft
    that still has deterministic issues is returned with those values marked and
    declared, never discarded: the reader sees the risk instead of a refusal.
    """
    review_invalid = (
        (semantic_audit or {}).get('review_structure_valid') is False
        or (semantic_audit or {}).get('repair_confirmation_status') == 'review_failed'
    )
    native_generation['source_screening'] = semantic_audit
    native_generation['post_audit_validation'] = {
        'passed': not final_issues,
        'issues': list(final_issues or []),
        'quantity_checks': final_checks,
        'semantic_support_verified': False,
        'reviewer_degraded': review_invalid,
        'reviewer_status': (semantic_audit or {}).get('status'),
    }
    if final_issues:
        from .answer_annotation import annotate_unverified
        native_generation['post_audit_rejected_draft'] = answer
        annotated, rows = annotate_unverified(answer, final_issues, final_checks)
        native_generation['post_audit_annotated'] = True
        native_generation['post_audit_annotation_rows'] = rows
        answer = annotated
    return answer, native_generation

# 多智能体系统核心定义
# ============================================================================

@dataclass
class AgentPipelineState:
    """多智能体管道状态"""
    request_id: str                                  # 请求ID
    original_question: str                           # 原始问题
    
    # Stage 1: 问题解析
    parsed_question: Optional[str] = None            # 解析后的问题
    extracted_entities: List[str] = field(default_factory=list)  # 提取的实体
    extracted_entities_en: List[str] = field(default_factory=list)  # 【新增】提取的实体（英文）
    query_intent: str = ""                           # 查询意图
    molecule_related: bool = False                   # 是否涉及分子相关查询
    molecule_names: List[str] = field(default_factory=list)  # 检测到的分子名称
    information_needs: List[str] = field(default_factory=list)
    
    # Stage 2: 多源检索
    graph_entities: Dict[str, Any] = field(default_factory=dict)  # 图谱实体
    graph_relations: List[Dict] = field(default_factory=list)     # 图谱关系
    vector_chunks: List[Dict] = field(default_factory=list)       # 向量检索块
    markdown_blocks: List[Dict] = field(default_factory=list)     # Markdown块
    molecule_context: str = ""                       # 分子性质上下文
    molecule_results: List[Dict] = field(default_factory=list)    # 分子查询结果
    
    # Stage 3: 信息融合
    fused_context: str = ""                          # 融合后的上下文
    fused_context_parts: List[Dict] = field(default_factory=list)  # 【新增】分割后的融合部分 {part_id, vector_source, context, doc_sources}
    fusion_confidence: float = 0.0                   # 融合置信度
    evidence_sources: List[str] = field(default_factory=list)     # 证据来源
    doc_sources: List[Dict] = field(default_factory=list)         # 文献来源列表
    
    # Stage 4: 答案生成
    final_answer: str = ""                           # 最终答案
    first_principles_answer: str = ""                # 【新增】第一性原理回答
    fp_reasoning: str = ""                           # 【新增】第一性原理思考过程
    answer_reasoning: str = ""                       # 【新增】最终答案生成的思考过程
    llm_reasoning: str = ""                          # 【保留】通用思考过程
    answer_confidence: float = 0.0                   # 答案置信度
    reasoning_chain: str = ""                        # 推理链
    
    # 执行信息
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    execution_time: float = 0.0                      # 执行时间(秒)
    agent_logs: List[str] = field(default_factory=list)  # Agent日志
    
    # 【新增】Stage完成状态 - 用于前端渐进式展开
    stage_1_complete: bool = False                   # Stage 1: 问题解析完成
    stage_2_complete: bool = False                   # Stage 2: 多源检索完成
    stage_3_complete: bool = False                   # Stage 3: 信息融合完成
    stage_4_complete: bool = False                   # Stage 4: 答案生成完成

    # 【证据图闭环 M2】Stage 5: 证据写回(可选, 仅当 MultiAgentPipeline 传入 evidence_store 时启用;
    # 详见《FlowBD_证据图闭环_制作计划.md》3.7。旧调用不传 → 字段保持默认, 前端 .get 兼容)
    stage_5_complete: bool = False                   # Stage 5: 证据图写回完成
    evidence_graph_snapshot: Optional[dict] = None   # 证据图快照(给前端/持久化)
    round_no: int = 0                                # 迭代轮次(单轮模式=1)
    iterations: List[Dict] = field(default_factory=list)  # 迭代时间线(协调器逐轮记录, 前端数据源)
    source_registry: Any = field(default=None, repr=False)
    lineage_sources: List[Dict] = field(default_factory=list)
    eg_stop_reason: str = ""
    answer_quality: Dict = field(default_factory=dict)
    operation_errors: List[str] = field(default_factory=list)

    def log(self, agent: str, message: str):
        """记录Agent日志"""
        log_entry = f"[{agent}] {message}"
        self.agent_logs.append(log_entry)
        try:
            logger.info(f"  {message}")
        except UnicodeError:
            logger.info("  " + message.encode("ascii", "backslashreplace").decode("ascii"))
    
    def save_retrieval_data(self, data_dir: str = None):
        """将检索数据保存为JSON格式（支持多次追加写入）
        
        【修复】确保保存20个父块的完整数据
        【新增】同时保存Graph RAG召回的实体和关系信息
        
        Args:
            data_dir: 数据保存目录，默认为项目的 data 文件夹
        """
        if data_dir is None:
            # 获取项目根目录
            script_dir = os.path.dirname(os.path.abspath(__file__))  # src/agent/
            project_root = os.path.dirname(os.path.dirname(script_dir))  # d:\flowbd_v5
            data_dir = os.path.join(project_root, 'src', 'data')
        
        # 确保目录存在
        Path(data_dir).mkdir(parents=True, exist_ok=True)
        
        # ========== 【新增】保存 Graph RAG 检索数据 - 包括路径信息 ==========
        if self.graph_entities or self.graph_relations:
            graph_file = os.path.join(data_dir, "graph_rag.json")
            graph_data = {
                'request_id': self.request_id,
                'timestamp': self.timestamp,
                'question': self.original_question,
                'entities_count': len(self.graph_entities),
                'relations_count': len(self.graph_relations),
                # 【新增】完整保存实体数据（包括扁源路径）
                'entities': [
                    {
                        'name': entity_name,
                        'type': entity_data.get('type', 'unknown'),
                        'properties': entity_data.get('properties', {}),
                        'source_docs': entity_data.get('source_docs', [])  # 【新增】文源路径
                    }
                    for entity_name, entity_data in (self.graph_entities.items() if self.graph_entities else [])
                ],
                'relations': self.graph_relations if self.graph_relations else []
            }
            
            # 读取现有数据并追加
            all_data = []
            if os.path.exists(graph_file):
                try:
                    with open(graph_file, 'r', encoding='utf-8') as f:
                        existing_data = json.load(f)
                        if isinstance(existing_data, list):
                            all_data = existing_data
                        else:
                            all_data = [existing_data]
                except Exception as e:
                    logger.warning(f"读取现有graph_rag.json失败: {e}，将创建新文件")
                    all_data = []
            
            all_data.append(graph_data)
            
            with open(graph_file, 'w', encoding='utf-8') as f:
                json.dump(all_data, f, ensure_ascii=False, indent=2)
            
            msg = f"✅ 【数据下载】成功保存Graph RAG数据到: {graph_file} (共{len(all_data)}条记录)"
            print(f"\n{msg}")
            self.log("System", msg)
            print(f"   • 文件位置: {graph_file}")
            print(f"   • 实体数量: {len(self.graph_entities)} 个")
            print(f"   • 关系数量: {len(self.graph_relations)} 条")
            print(f"   • 问答记录: 共{len(all_data)}条")
            print(f"   • 【新增】每个实体包含文源路径信息")
            logger.info(f"✓ Graph RAG数据已保存到: {graph_file} (共{len(all_data)}个问答记录, 本次{len(self.graph_entities)}个实体, {len(self.graph_relations)}条关系)")
        
        # ========== 保存 Milvus 检索数据 - 追加到 rag.json ==========
        if self.vector_chunks:
            rag_file = os.path.join(data_dir, "rag.json")
            milvus_data = {
                'request_id': self.request_id,
                'timestamp': self.timestamp,
                'question': self.original_question,
                'chunks_count': len(self.vector_chunks),  # 新增：块数量统计
                'chunks': self.vector_chunks
            }
            
            # 读取现有数据并追加
            all_data = []
            if os.path.exists(rag_file):
                try:
                    with open(rag_file, 'r', encoding='utf-8') as f:
                        existing_data = json.load(f)
                        if isinstance(existing_data, list):
                            all_data = existing_data
                        else:
                            all_data = [existing_data]
                except Exception as e:
                    logger.warning(f"读取现有rag.json失败: {e}，将创建新文件")
                    all_data = []
            
            all_data.append(milvus_data)
            
            with open(rag_file, 'w', encoding='utf-8') as f:
                json.dump(all_data, f, ensure_ascii=False, indent=2)
            
            msg = f"✅ 【数据下载】成功保存{len(self.vector_chunks)}个父块到: {rag_file} (共{len(all_data)}条记录)"
            print(f"\n{msg}")
            self.log("System", msg)
            print(f"   • 文件位置: {rag_file}")
            print(f"   • 块数量: {len(self.vector_chunks)} 个父块")
            print(f"   • 问答记录: 共{len(all_data)}条")
            logger.info(f"✓ Milvus数据已保存到: {rag_file} (共{len(all_data)}个问答记录, 本次{len(self.vector_chunks)}个块)")
        
        # ========== 【新增】保存 Web 搜索结果 ==========
        if self.markdown_blocks:
            web_file = os.path.join(data_dir, "web_search.json")
            web_data = {
                'request_id': self.request_id,
                'timestamp': self.timestamp,
                'question': self.original_question,
                'blocks_count': len(self.markdown_blocks),
                'blocks': self.markdown_blocks
            }
            
            # 读取现有数据并追加
            all_data = []
            if os.path.exists(web_file):
                try:
                    with open(web_file, 'r', encoding='utf-8') as f:
                        existing_data = json.load(f)
                        if isinstance(existing_data, list):
                            all_data = existing_data
                        else:
                            all_data = [existing_data]
                except Exception as e:
                    logger.warning(f"读取现有web_search.json失败: {e}，将创建新文件")
                    all_data = []
            
            all_data.append(web_data)
            
            with open(web_file, 'w', encoding='utf-8') as f:
                json.dump(all_data, f, ensure_ascii=False, indent=2)
            
            msg = f"✅ 【数据下载】成功保存{len(self.markdown_blocks)}个Web结果到: {web_file} (共{len(all_data)}条记录)"
            print(f"\n{msg}")
            self.log("System", msg)
            print(f"   • 文件位置: {web_file}")
            print(f"   • 结果数量: {len(self.markdown_blocks)} 条")
            print(f"   • 问答记录: 共{len(all_data)}条")
            logger.info(f"✓ Web搜索数据已保存到: {web_file} (共{len(all_data)}个问答记录, 本次{len(self.markdown_blocks)}条结果)")


class QuestionParsingAgent:
    """问题解析Agent - 提取问题的关键信息"""
    
    def __init__(self, llm):
        self.llm = llm
        self.name = "QuestionParsingAgent"
    
    def parse(self, state: AgentPipelineState) -> AgentPipelineState:
        """解析问题"""
        state.log(self.name, "🔍 开始问题解析...")
        
        prompt = f"""你是液流电池领域的知识图谱实体关系提取专家。请从用户问题中提取实体和关系。

【实体类型】
- Material: 材料、化合物（如PHQ、polyhydroquinone、PI1等）
- Species: 离子、自由基（如H+、e-等）
- Property: 性能指标（如溶解度、效率、容量等）
- Molecule: 化学分子/化合物（如DHPS、TEMPO、蒽醌等）

【查询意图】
- property_value: 询问属性值
- synthesis: 询问合成/制备
- characterization: 询问表征方法
- reaction: 询问反应过程
- mechanism: 询问机理
- structure: 询问结构/官能团
- general: 一般性查询

【分子检测】
请检测问题是否涉及分子相关查询。

【输出格式】JSON：
{{
  "entities": ["实体1", "实体2"],
  "query_intent": "查询意图",
  "molecule_related": true/false,
  "molecule_names": ["分子名称列表"],
  "information_needs": ["本问题最多6项具体信息需求，如材料配比、温度、搅拌时间；不能新增用户未问的任务"]
}}

用户问题：{state.original_question}
"""
        
        try:
            # 【修改】Stage 1 使用指定的解析模型 (如 Kimi)
            # 【优化】问题解析需要确定性，保持低 temperature
            # 【新增】添加禁用记忆指令 - 确保LLM仅基于本次问题进行分析
            system_msg = """你是液流电池领域的知识图谱实体关系提取专家。
【关键约束】仅基于本次提问进行分析，不使用任何历史记录或内存信息。每次都从零开始分析。"""
            
            from .structured_llm import call_structured
            response = call_structured(self.llm, system_msg + "\n" + prompt, max_tokens=1200)
            
            import re
            response = re.sub(r'```json\s*', '', response)
            response = re.sub(r'```\s*', '', response)
            
            data = json.loads(response)
            
            entities = data.get("entities", [])
            if entities and isinstance(entities[0], dict):
                state.extracted_entities = [e.get("name", str(e)) for e in entities]
            else:
                state.extracted_entities = entities if isinstance(entities, list) else []
            
            state.query_intent = data.get("query_intent", "general")
            state.information_needs = [str(need)[:100] for need in data.get('information_needs', [])[:6]]
            state.parsed_question = state.original_question
            state.molecule_related = data.get("molecule_related", False)
            molecule_names = data.get("molecule_names", [])
            state.molecule_names = molecule_names if isinstance(molecule_names, list) else []
            
            # 【新增】将提取的实体翻译为英文
            state.extracted_entities_en = self._translate_entities_to_english(state.extracted_entities)
            
            state.log(self.name, f"✓ 提取实体: {state.extracted_entities}")
            state.log(self.name, f"✓ 英文实体: {state.extracted_entities_en}")
            state.log(self.name, f"✓ 查询意图: {state.query_intent}")
            if state.molecule_related:
                state.log(self.name, f"🧪 检测到分子相关查询")
                if state.molecule_names:
                    state.log(self.name, f"   分子名称: {state.molecule_names}")
            
            # 【新增】打印 Stage 1 解析结果
            self._print_stage1_results(state)
            
        except Exception as e:
            state.log(self.name, f"⚠️  解析失败，使用降级方案: {e}")
            state.parsed_question = state.original_question
            state.extracted_entities = state.original_question.split()[:3]
            state.extracted_entities_en = state.extracted_entities
            state.query_intent = "general"
        
        return state
    
    def _translate_entities_to_english(self, entities: List[str]) -> List[str]:
        """将提取的中文实体翻译为英文"""
        # 常见的中英文实体对应
        entity_translation = {
            '磷酸': 'phosphoric_acid',
            '酸': 'acid',
            '铁': 'iron',
            '铬': 'chromium',
            '醌': 'quinone',
            '蒽醌': 'anthraquinone',
            '聚': 'poly',
            '液流电池': 'redox_flow_battery',
            '电池': 'battery',
            '电解质': 'electrolyte',
            '溶解度': 'solubility',
            '效率': 'efficiency',
            '容量': 'capacity',
            '性质': 'property',
            '官能团': 'functional_group',
            '合成': 'synthesis',
            '表征': 'characterization',
            '反应': 'reaction',
            '机理': 'mechanism',
            '结构': 'structure',
            '性能': 'performance',
        }
        
        translated = []
        for entity in entities:
            # 首先检查是否有直接对应的翻译
            if entity in entity_translation:
                translated.append(entity_translation[entity])
            # 如果已经是英文，保持不变
            elif entity.isascii():
                translated.append(entity)
            # 尝试逐个字符翻译
            else:
                translated_entity = entity
                for cn, en in entity_translation.items():
                    translated_entity = translated_entity.replace(cn, en)
                translated.append(translated_entity if translated_entity != entity else entity.upper())
        
        return translated
    
    def _print_stage1_results(self, state: AgentPipelineState):
        """打印 Stage 1 问题解析的详细结果"""
        _safe_print("\n" + "="*80)
        _safe_print("📍 Stage 1: 问题解析")
        _safe_print("="*80)
        _safe_print(f"  • 用户问题: {state.original_question}")
        _safe_print(f"  • 提取实体 (中文): {state.extracted_entities}")
        _safe_print(f"  • 提取实体 (英文): {state.extracted_entities_en}")
        _safe_print(f"  • 查询意图: {state.query_intent}")
        if state.molecule_related:
            _safe_print(f"  • 分子相关: 是")
            if state.molecule_names:
                _safe_print(f"    └─ 分子名称: {state.molecule_names}")
        else:
            _safe_print(f"  • 分子相关: 否")
        # _safe_print("="*80 + "\n")
        # _safe_print(f"        ✅ graph_rag检索: {len(state.extracted_entities)} 个实体, 意图: {state.query_intent}")
        
        # 打印提取的实体
        # if state.extracted_entities:
        #     # _safe_print(f"        【实体】({len(state.extracted_entities)} 个)")
        #     for idx, entity in enumerate(state.extracted_entities, 1):
        #         # _safe_print(f"          {idx}. {entity}")
        
        # 打印查询意图
        # _safe_print(f"        【查询意图】{state.query_intent}")
        
        # 打印分子相关信息
        if state.molecule_related:
            _safe_print(f"        【分子相关】是")
            if state.molecule_names:
                _safe_print(f"          分子名称: {', '.join(state.molecule_names)}")
        else:
            _safe_print(f"        【分子相关】否")
    
    def _detect_molecule_keywords(self, question: str) -> bool:
        """通过关键词检测问题是否涉及分子相关查询"""
        question_lower = question.lower()
        molecule_keywords = [
            'dhps', 'tempo', 'aq', 'anthraquinone', '蒽醌',
            'phz', 'phenazine', '吩嗪', 'viologen', '紫精',
            'ferrocene', '二茂铁', 'ferrocyanide', '亚铁氰',
            '溶解度', '分子量', '电位', '官能团'
        ]
        
        for keyword in molecule_keywords:
            if keyword in question_lower:
                return True
        
        return False


class MultiSourceRetrievalAgent:
    """多源检索Agent - 从Graph RAG和传统RAG检索"""
    
    def __init__(self, graph_rag, traditional_rag, llm, molecule_agent=None):
        self.graph_rag = graph_rag
        self.traditional_rag = traditional_rag
        self.llm = llm
        self.molecule_agent = molecule_agent
        self.name = "MultiSourceRetrievalAgent"
    
    def retrieve(self, state: AgentPipelineState) -> AgentPipelineState:
        """从多个源检索 - 多线程并行执行"""
        import time
        import threading
        
        state.log(self.name, "📚 开始多源检索...")
        start_time = time.time()
        
        # 为每个检索任务计时
        task_times = {
            'molecules': {'start': None, 'elapsed': 0},
            'graph_rag': {'start': None, 'elapsed': 0},
            'vector_rag': {'start': None, 'elapsed': 0},
            'metaso': {'start': None, 'elapsed': 0},
        }
        
        # 定义各个检索任务
        def task_molecules():
            if state.molecule_related and self.molecule_agent:
                try:
                    task_times['molecules']['start'] = time.time()
                    state.log(self.name, "  🧪 执行分子查询...")
                    self._retrieve_molecules(state)
                    task_times['molecules']['elapsed'] = time.time() - task_times['molecules']['start']
                except Exception as e:
                    state.log(self.name, f"  ⚠️  分子查询失败: {e}")
        
        def task_graph_rag():
            if self.graph_rag:
                try:
                    task_times['graph_rag']['start'] = time.time()
                    state.log(self.name, "  🔗 查询知识图谱...")
                    # 【优化】使用 Stage 1 提取的实体和意图，而不是原始问题
                    state.log(self.name, f"     📍 使用Stage 1结果 - 中文实体: {state.extracted_entities[:5]}, 英文实体: {state.extracted_entities_en[:5]}, 意图: {state.query_intent}")
                    driver = getattr(self.graph_rag, 'driver', None)
                    if driver is not None and hasattr(driver, 'verify_connectivity'):
                        driver.verify_connectivity()
                    query = self._build_graph_query(state)
                    state.log(self.name, f"     ✨ 构建的查询词: {query}")
                    if state.extracted_entities and hasattr(self.graph_rag, 'get_raw_search_results_from_entities'):
                        search_results = self.graph_rag.get_raw_search_results_from_entities(
                            query, state.extracted_entities[:5] + state.extracted_entities_en[:5], state.query_intent)
                    else:
                        search_results = self.graph_rag.get_raw_search_results(query)
                    
                    if search_results:
                        # 【修改】不限制实体数量 - 将所有召回的实体都传给LLM
                        entities_list = search_results.get('entities', [])
                        if entities_list:
                            for entity in entities_list:  # 【修改】移除 限制，传递全部实体
                                if isinstance(entity, dict):
                                    entity_name = entity.get('name', '')
                                    if entity_name:
                                        state.graph_entities[entity_name] = {
                                            'name': entity_name,
                                            'type': entity.get('type', 'unknown'),
                                            'source_docs': entity.get('source_docs', []),
                                            'properties': entity.get('properties', {})
                                        }
                        
                        # 【修改】不限制关系数量 - 将所有召回的关系都传给LLM
                        state.graph_relations = []
                        # 【修改】移除 max_relations_per_type 限制，提取所有关系
                        for rel_type in ['property_values', 'reaction_info', 'synthesis_info', 'characterization_methods']:
                            items = search_results.get(rel_type, [])
                            if items and isinstance(items, list):
                                # 【修改】移除 [:max_relations_per_type] 限制，传递全部关系
                                for item in items:  # 传递全部关系，无数量限制
                                    if isinstance(item, dict):
                                        state.graph_relations.append(item)
                        
                        state.log(self.name, f"  ✓ 图谱检索完成: {len(state.graph_entities)} 个实体, {len(state.graph_relations)} 个关系")
                    task_times['graph_rag']['elapsed'] = time.time() - task_times['graph_rag']['start']
                except Exception as e:
                    state.operation_errors.append("graph_retrieval_failure:" + type(e).__name__)
                    state.log(self.name, f"  ⚠️  图谱检索失败: {e}")
                    import traceback
                    traceback.print_exc()
        
        def task_vector_rag():
            if self.traditional_rag:
                try:
                    task_times['vector_rag']['start'] = time.time()
                    state.log(self.name, "  📖 查询Milvus向量库...")
                    # 【优化】使用 Stage 1 提取的实体和意图
                    query = self._build_vector_query(state)
                    state.log(self.name, f"     查询词: {query}")
                    chunks = self._retrieve_with_document_recall(query, top_k=30, rerank_top_k=30, state=state)  # 【修改】传递state用于记录日志
                    state.vector_chunks = chunks
                    state.log(self.name, f"  ✓ 向量检索完成: {len(chunks)} 个块")
                    task_times['vector_rag']['elapsed'] = time.time() - task_times['vector_rag']['start']
                except Exception as e:
                    state.operation_errors.append("vector_retrieval_failure:" + type(e).__name__)
                    state.log(self.name, f"  ⚠️  向量检索失败: {e}")
                    state.vector_chunks = []
        
        def task_metaso():
            try:
                task_times['metaso']['start'] = time.time()
                state.log(self.name, "  🔍 查询网页搜索...")
                # 【优化】使用 Stage 1 提取的实体和意图
                query = self._build_web_query(state)
                state.log(self.name, f"     查询词: {query}")
                md_blocks = self._retrieve_markdown(query, top_k=0)
                state.markdown_blocks = md_blocks
                state.log(self.name, f"  ✓ 网页搜索完成: {len(md_blocks)} 个块")
                task_times['metaso']['elapsed'] = time.time() - task_times['metaso']['start']
            except Exception as e:
                state.log(self.name, f"  ⚠️  网页搜索失败: {e}")
        
        # 创建线程并并行执行
        threads = []
        if state.molecule_related and self.molecule_agent:
            t = threading.Thread(target=task_molecules, daemon=False)
            threads.append(t)
        # 【禁用】不启动 Graph RAG 检索线程
        if self.graph_rag:
             t = threading.Thread(target=task_graph_rag, daemon=False)
             threads.append(t)
        if self.traditional_rag:
            t = threading.Thread(target=task_vector_rag, daemon=False)
            threads.append(t)
        
        t = threading.Thread(target=task_metaso, daemon=False)
        threads.append(t)
        
        # 启动所有线程
        for t in threads:
            t.start()
        
        # 等待所有线程完成
        for t in threads:
            t.join()

        from .corpus_evidence import search_corpus, lineage_sources, title_filtered_recall
        from .evidence_sources import prepare_sources
        local = search_corpus(state.original_question, state.extracted_entities)
        try:
            scoped = title_filtered_recall(self.traditional_rag.get_models().get('milvus_collection'),
                                           state.original_question) if self.traditional_rag else []
        except Exception as exc:
            scoped = []
            state.log(self.name, f"题名范围补召回未完成：{type(exc).__name__}")
        local = scoped + local
        existing = {(c.get('source'), c.get('parent_id')) for c in state.vector_chunks}
        local = [c for c in local if (c.get('source'), c.get('parent_id')) not in existing]
        state.vector_chunks = local + state.vector_chunks
        state.lineage_sources = lineage_sources(state.original_question)
        prepare_sources(state)
        state.log(self.name, f"本地正文补召回 {len(local)} 块；审计谱系证据 {len(state.lineage_sources)} 条")
        
        # 【关闭】打印 RAG 文献块数量
        # if state.vector_chunks:
        #     print(f"\n        📄 RAG 文献块: {len(state.vector_chunks)} 个")
        #     print(f"           ✅ 【最终确认】成功召回 {len(state.vector_chunks)} 个父块")
        #     if len(state.vector_chunks) > 0:
        #         print(f"           • 块列表 (前5个示例):")
        #         for i, chunk in enumerate(state.vector_chunks[:5], 1):
        #             battery_type = chunk.get('battery_type', 'unknown')
        #             source = chunk.get('original_filename', chunk.get('source', 'unknown'))[:30]
        #             doc_id = chunk.get('doc_id', 'N/A')
        #             print(f"             {i}. doc_id={doc_id}, battery_type={battery_type}, source={source}")
        #         if len(state.vector_chunks) > 5:
        #             print(f"             ... (共{len(state.vector_chunks)}个块)")

        # 【关闭】报告 Graph RAG 的检索情况
        # if not state.graph_entities and not state.graph_relations:
        #     print(f"\n        ⚠️ [DEBUG] Graph RAG 检索为空！")
        #     print(f"           请检查：")
        #     print(f"           1. Graph RAG 是否正常初始化")
        #     print(f"           2. Neo4j 是否有数据")
        
        elapsed_time = time.time() - start_time
        state.log(self.name, f"✓ 多源检索完成")
        
        return state
    

    
    def _retrieve_markdown(self, question: str, top_k: int = 2) -> List[Dict]:
        """从网页搜索API获取内容"""
        blocks = []
        try:
            import requests
            
            metaso_api_url = "https://metaso.cn/api/v1/search"
            api_key = __import__("os").environ.get("METASO_API_KEY", "")
            
            payload = {
                "q": question,
                "scope": "webpage",
                "includeContent": True,
                "size": top_k * 2,
            }
            
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {api_key}'
            }
            
            response = requests.post(metaso_api_url, json=payload, headers=headers, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                results = result.get('webpages', [])
                
                for i, item in enumerate(results[:top_k]):
                    content = item.get('snippet', '') or item.get('title', '')
                    if content and len(content.strip()) > 0:
                        blocks.append({
                            'content': content[:500],
                            'source': '秘塔搜索',
                            'url': item.get('link', ''),
                            'title': item.get('title', ''),
                            'index': i + 1
                        })
        
        except Exception as e:
            logger.debug(f"秘塔搜索API失败: {e}")
        
        return blocks
    
    def _retrieve_with_document_recall(self, question: str, top_k: int = 30, rerank_top_k: int = 30, state: Optional[AgentPipelineState] = None) -> List[Dict]:
        """使用 DocumentRecallerV2 进行 Milvus 向量检索，召回top_k个块
        
        【修改】默认top_k从20提升至30，获取更多相关信息
        【修复】已移除rerank_top_k截断逻辑，确保返回top_k个块
        """
        blocks = []
        
        try:
            # 【修复】使用绝对导入路径
            import sys
            import os
            graphrag_and_rag_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # src/
            rag_module_path = os.path.join(graphrag_and_rag_dir, 'rag')
            # print(f"rag_module_path: {rag_module_path}")
            if rag_module_path not in sys.path:
                sys.path.insert(0, rag_module_path)
            from recall_document_v2 import DocumentRecallerV2
            
            models = self.traditional_rag.get_models()
            embedding_model = models.get('embedding_model')
            embedding_tokenizer = models.get('embedding_tokenizer')
            milvus_collection = models.get('milvus_collection')
            reranker_model = models.get('reranker_model')
            reranker_tokenizer = models.get('reranker_tokenizer')
            
            logger.debug(f"[RAG检索] embedding_model: {embedding_model is not None}")
            logger.debug(f"[RAG检索] embedding_tokenizer: {embedding_tokenizer is not None}")
            logger.debug(f"[RAG检索] milvus_collection: {milvus_collection is not None}")
            logger.debug(f"[RAG检索] milvus_collection 数量: {milvus_collection.num_entities if milvus_collection else 0}")
            
            if not embedding_model or not embedding_tokenizer or not milvus_collection:
                if state is not None:
                    state.operation_errors.append("vector_resource_unavailable")
                logger.error(f"⚠️  DocumentRecall 模型未初始化: embedding_model={embedding_model is not None}, embedding_tokenizer={embedding_tokenizer is not None}, milvus_collection={milvus_collection is not None}")
                return blocks
            
            # 【新增】异步加载模式下，检索前确保Milvus集合已加载完成（带超时）
            try:
                from .part1_knowledge_arsenal import ensure_milvus_loaded
            except ImportError:
                from part1_knowledge_arsenal import ensure_milvus_loaded
            try:
                ensure_milvus_loaded(milvus_collection)
            except RuntimeError as e:
                if state is not None:
                    state.operation_errors.append("vector_collection_not_ready")
                logger.error(f"⚠️  Milvus集合未就绪，跳过向量检索: {e}")
                return blocks
            
            recall_engine = DocumentRecallerV2(
                embedding_model=embedding_model,
                embedding_tokenizer=embedding_tokenizer,
                milvus_collection=milvus_collection,
                reranker_model=reranker_model,
                reranker_tokenizer=reranker_tokenizer,
                debug=False
            )
            
            logger.debug(f"[RAG检索] 开始调用recall_parent_blocks, query={question[:50]}, top_k={top_k}")
            
            # 【修复】先识别电池类型，然后传入召回层（避免重复识别）
            # 【改进】使用绝对路径导入，确保导入到正确版本
            import os
            import sys
            graphrag_and_rag_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # src/
            rag_module_path = os.path.join(graphrag_and_rag_dir, 'rag')
            if rag_module_path not in sys.path:
                sys.path.insert(0, rag_module_path)
            from class_query import identify_battery_type
            question_battery_type = identify_battery_type(question, debug=True)  # 【新增】启用调试
            
            # 【调试】打印并记录电池类型识别结果
            msg = ""
            if question_battery_type == 'other':
                msg = f"⚠️  【电池类型识别】未识别到特定类型，将进行全局搜索"
            else:
                msg = f"✅ 【电池类型识别】识别成功: {question_battery_type}"
            
            print(msg)
            if state:
                state.log(self.name, msg)
            
            # 【重要】recall_parent_blocks 返回 Tuple[List[Dict], Dict[str, List[int]]]
            # 但need根据实际导入的DocumentRecallerV2类版本确认返回类型
            # 第一个元素：父块列表
            # 第二个元素：块索引映射 {parent_id: [child_ids]} 
            result = recall_engine.recall_parent_blocks(
                query=question,
                top_k=top_k,
                use_reranker=True,
                battery_type_filter=question_battery_type  # 【新增】直接传入识别结果
            )
            
            # 【防御性编程】判断返回值是否为tuple（新版本）还是list（旧版本）
            if isinstance(result, tuple) and len(result) == 2:
                parent_blocks, block_indices = result
            else:
                # 降级处理：如果返回的是列表，直接使用
                parent_blocks = result if isinstance(result, list) else []
                block_indices = {}
            # 【关闭】Milvus搜索完成信息
            # logger.debug(f"[RAG检索] recall_parent_blocks返回{len(parent_blocks)}个块")
            
            # 【关闭】详细的块调试信息
            # if not parent_blocks:
            #     logger.warning(f"[RAG检索] ⬇️ 被召回为空！检查是否是选项问题")
            # else:
            #     logger.debug(f"[RAG检索] ✓ 检索到{len(parent_blocks)}个基块")
            #     for i, block in enumerate(parent_blocks[:3], 1):
            #         logger.debug(f"  块{i}: doc_id={block.get('doc_id', 'N/A')}, source={block.get('original_filename', 'N/A')[:30]}, battery_type={block.get('battery_type', 'N/A')}")
            
            for block in parent_blocks:
                # 查询block是否是元组
                if isinstance(block, tuple):
                    # 为了安全起见，检查是否是(Dict, float)的元组
                    block = block[0]
                
                blocks.append({
                    'content': block.get('content', ''),
                    'source': block.get('original_filename', block.get('doc_id', 'unknown')),
                    'original_filename': block.get('original_filename', 'unknown'),
                    'doc_id': block.get('doc_id', ''),
                    'parent_id': block.get('parent_id') or block.get('id'),
                    'battery_type': block.get('battery_type', 'unknown'),
                    'similarity': block.get('max_similarity', 0),
                    'rerank_score': block.get('rerank_score', 0)
                })
            
            # # 【新增】调试日志：打印前3个块的字符长度
            # if blocks:
            #     print(f"\n[RAG块大小检查]")
            #     print(f"  返回块数量: {len(blocks)} 个")
            #     for i, block in enumerate(blocks[:3]):
            #         content = block.get('content', '')
            #         print(f"  块{i+1}: {len(content)} 字符, source={block.get('source', 'N/A')[:20]}")
            #     if len(blocks) > 3:
            #         print(f"  ... (共{len(blocks)}个块)")
            # # logger.debug(f"[RAG检索] 最终返回{len(blocks)}个块 (要求top_k={top_k})")
            
        except Exception as e:
            if state is not None:
                state.operation_errors.append("vector_retrieval_failure:" + type(e).__name__)
            logger.error(f"DocumentRecall 检索失败: {e}")
            import traceback
            traceback.print_exc()
        
        return blocks
    
    def _query_graph_by_entity(self, entity: str) -> Dict:
        """从图谱中查询实体的相关节点和关系"""
        result = {"entities": {}, "relations": []}
        
        if not self.graph_rag:
            logger.debug(f"graph_rag 为空，无法查询: {entity}")
            return result
        
        try:
            # 尝试方法1: 调用 query_by_entity 方法
            if hasattr(self.graph_rag, 'query_by_entity'):
                logger.debug(f"尝试使用 query_by_entity 方法查询: {entity}")
                graph_results = self.graph_rag.query_by_entity(entity)
                if graph_results and (graph_results.get("entities") or graph_results.get("relations")):
                    result["entities"] = graph_results.get("entities", {})
                    result["relations"] = graph_results.get("relations", [])
                    logger.debug(f"query_by_entity 查询成功: {entity}")
                    return result
        
        except Exception as e:
            logger.debug(f"query_by_entity 方法调用失败: {e}")
        
        # 尝试方法2: 直接访问 graph 属性
        try:
            if hasattr(self.graph_rag, 'graph') and self.graph_rag.graph:
                logger.debug(f"尝试使用 graph 属性查询: {entity}")
                graph_obj = self.graph_rag.graph
                
                # 检查 graph 结构
                if isinstance(graph_obj, dict):
                    for node_id, node_data in graph_obj.get("nodes", {}).items():
                        node_name = node_data.get("name", "").lower()
                        if entity.lower() in node_name or node_name in entity.lower():
                            result["entities"][node_id] = {
                                "name": node_data.get("name", ""),
                                "type": node_data.get("type", "unknown"),
                                "properties": node_data.get("properties", {})
                            }
                    
                    if result["entities"]:
                        related_node_ids = set(result["entities"].keys())
                        for edge_id, edge_data in graph_obj.get("edges", {}).items():
                            source = edge_data.get("source")
                            target = edge_data.get("target")
                            if source in related_node_ids or target in related_node_ids:
                                result["relations"].append({
                                    "source": source,
                                    "target": target,
                                    "relationship": edge_data.get("relationship", ""),
                                    "properties": edge_data.get("properties", {})
                                })
                        logger.debug(f"graph 查询成功: {entity}")
                        return result
        
        except Exception as e:
            logger.debug(f"graph 属性查询失败: {e}")
        
        # 尝试方法3: 调用其他可能的查询方法
        try:
            # 查询是否有其他查询方法
            if hasattr(self.graph_rag, 'query'):
                logger.debug(f"尝试使用 query 方法查询: {entity}")
                graph_results = self.graph_rag.query(entity)
                if graph_results:
                    if isinstance(graph_results, dict):
                        result["entities"] = graph_results.get("entities", {})
                        result["relations"] = graph_results.get("relations", [])
                    logger.debug(f"query 方法查询成功: {entity}")
                    return result
            
            # 查询是否有 search 方法
            if hasattr(self.graph_rag, 'search'):
                logger.debug(f"尝试使用 search 方法查询: {entity}")
                graph_results = self.graph_rag.search(entity)
                if graph_results:
                    if isinstance(graph_results, dict):
                        result["entities"] = graph_results.get("entities", {})
                        result["relations"] = graph_results.get("relations", [])
                    logger.debug(f"search 方法查询成功: {entity}")
                    return result
        
        except Exception as e:
            logger.debug(f"其他查询方法失败: {e}")
        
        logger.debug(f"未找到有效的图谱查询方法，实体: {entity}")
        return result
    
    def _retrieve_molecules(self, state: AgentPipelineState) -> AgentPipelineState:
        """分子查询流程"""
        state.log(self.name, "🧪 执行分子查询...")
        
        try:
            # Step 1: 从问题中提取分子名称
            extracted_molecules = self._extract_molecule_names(state)
            state.log(self.name, f"   提取到分子: {extracted_molecules}")
            
            if not extracted_molecules:
                state.log(self.name, "⚠️  未从问题中提取到分子名称")
                return state
            
            # Step 2: 使用 molecule_agent 查询分子属性
            if self.molecule_agent:
                state.log(self.name, f"   使用分子查询Agent查询 {len(extracted_molecules)} 个分子...")
                try:
                    # 调用分子查询Agent的查询方法（使用 process_query 方法）
                    for molecule in extracted_molecules:
                        # 调用 MoleculeQueryAgent 的 tool.query() 方法
                        mol_result = self.molecule_agent.tool.query(molecule)
                        
                        if mol_result and mol_result.query_success:
                            # 将结果转换为字典格式，添加到 state.molecule_results
                            result_dict = {
                                'identifier': mol_result.molecule.identifier,
                                'formula': mol_result.molecule.molecular_formula or 'N/A',
                                'smiles': mol_result.molecule.canonical_smiles or 'N/A',
                                'success': True,
                            }
                            
                            # 添加计算的性质
                            for prop in mol_result.properties:
                                # 将属性值添加到结果字典
                                prop_name = prop.property_name
                                result_dict[prop_name] = f"{prop.value}{f' {prop.unit}' if prop.unit else ''}"
                            
                            # 添加液流电池相关信息
                            if mol_result.rfb_relevance.get('is_known_rfb_molecule'):
                                rfb = mol_result.rfb_relevance
                                result_dict['rfb_role'] = rfb.get('role')
                                result_dict['rfb_category'] = rfb.get('category')
                                result_dict['redox_potential'] = rfb.get('redox_potential')
                            
                            state.molecule_results.append(result_dict)
                            state.log(self.name, f"   ✓ 查询分子: {molecule}")
                        else:
                            errors = mol_result.errors if mol_result else ["未知错误"]
                            state.log(self.name, f"   ⚠️  分子查询失败或无结果: {molecule} ({', '.join(errors)})")
                    
                    if state.molecule_results:
                        state.log(self.name, f"🧪 分子查询: ✓ 查询到 {len(state.molecule_results)} 个分子结果")
                    else:
                        state.log(self.name, f"🧪 分子查询: ✗ 未查询到分子结果")
                
                except Exception as e:
                    state.log(self.name, f"   ⚠️  分子查询Agent调用失败: {e}")
            else:
                # 如果没有分子Agent，尝试简单的提取
                state.log(self.name, "⚠️  分子查询Agent未初始化，无法进行分子查询")
        
        except Exception as e:
            state.log(self.name, f"  ❌ 分子查询失败: {e}")
        
        return state
    
    def _extract_molecule_names(self, state: AgentPipelineState) -> list:
        """从问题和提取的实体中识别分子名称"""
        molecules = set()
        
        for entity in state.extracted_entities:
            entity_lower = entity.lower().strip()
            if len(entity) > 1 and not self._is_non_molecule_entity(entity):
                molecules.add(entity)
        
        return list(molecules)
    
    def _is_non_molecule_entity(self, entity: str) -> bool:
        """判断实体是否为非分子实体"""
        non_molecule_keywords = [
            'battery', 'electrode', 'cell', 'cathode', 'anode',
            'electrolyte', 'solution', 'flow', 'redox'
        ]
        
        entity_lower = entity.lower()
        return any(kw in entity_lower for kw in non_molecule_keywords)
    
    def _build_graph_query(self, state: AgentPipelineState) -> str:
        """基于 Stage 1 提取的实体和意图，构建 Neo4j 图谱查询语句
        
        【优化】关键词截断：
        1. Stage 1 提取的英文实体 - 仅取 Top 5
        2. 分子名称 - 仅取 Top 3
        3. 查询意图 (query_intent)
        4. 回退到原始问题
        """
        query_parts = []
        
        # 【新增】优先使用英文实体进行图谱查询
        if state.extracted_entities_en:
            query_parts.extend(state.extracted_entities_en)
        elif state.extracted_entities:
            # 备选：如果没有英文实体，使用中文实体
            query_parts.extend(state.extracted_entities)
        
        # 【优化】仅使用分子名称的 Top 3
        if state.molecule_names:
            query_parts.extend(state.molecule_names[:3])
        
        # 如果没有实体，根据意图构建查询
        if not query_parts:
            intent_keywords = {
                'property_value': 'property performance attribute',
                'synthesis': 'synthesis preparation manufacture',
                'characterization': 'characterization test analysis',
                'reaction': 'reaction mechanism electrochemistry',
                'mechanism': 'mechanism principle process',
                'structure': 'structure functional_group molecule',
                'general': state.original_question
            }
            intent_query = intent_keywords.get(state.query_intent, state.original_question)
            query_parts.append(intent_query)
        
        # 拼接查询语句
        final_query = ' '.join(query_parts) if query_parts else state.original_question
        return final_query
    
    def _build_vector_query(self, state: AgentPipelineState) -> str:
        """基于 Stage 1 提取的实体和意图，构建向量检索查询语句
        
        【优化】关键词截断：
        1. 优先使用实体 (Top 5) + 意图关键词
        2. 如果没有实体，使用意图关键词
        3. 回退到原始问题
        """
        # Keep the user's specific process/conditions; entity-only rewriting lost HER.
        query_parts = [state.original_question]
        aliases = {"铁铬": "iron chromium redox flow battery", "析氢": "hydrogen evolution reaction",
                   "抑制": "suppression inhibition", "导热": "thermal conductivity",
                   "膨胀石墨": "expanded graphite", "高温熔融": "high temperature melting molten salt"}
        query_parts.extend(value for key, value in aliases.items() if key in state.original_question)
        
        # 【优化】仅使用提取的实体的 Top 5
        if state.extracted_entities:
            query_parts.extend(state.extracted_entities)
        
        # 根据意图添加关键词
        if state.query_intent != 'general':
            intent_keywords = {
                'property_value': '性质 性能 属性 特性',
                'synthesis': '合成 制备 制造 工艺',
                'characterization': '表征 测试 分析 测量',
                'reaction': '反应 反应机理 电化学',
                'mechanism': '机理 原理 过程 机制',
                'structure': '结构 官能团 分子结构'
            }
            intent_kw = intent_keywords.get(state.query_intent)
            if intent_kw:
                query_parts.append(intent_kw)
        
        # 【优化】最后添加分子名称，也限制在 Top 3
        if state.molecule_names:
            query_parts.extend(state.molecule_names[:3])
        
        # 拼接查询语句
        final_query = ' '.join(query_parts) if query_parts else state.original_question
        return final_query
    
    def _build_web_query(self, state: AgentPipelineState) -> str:
        """基于 Stage 1 提取的实体和意图，构建 Web 搜索查询语句
        
        策略：
        1. 保留原始问题为主
        2. 补充提取的关键实体
        3. 根据意图调整搜索重点
        """
        # Web 搜索应该保持相对自然的问题形式
        # 只在关键处添加实体强调
        base_query = state.original_question
        
        # 如果有特定的分子，添加到搜索中
        if state.molecule_names:
            base_query = f"{base_query} {' '.join(state.molecule_names)}"
        
        # 根据意图调整搜索词
        intent_focus = {
            'synthesis': ' 合成方法 制备工艺',
            'characterization': ' 表征方法 测试',
            'reaction': ' 反应机理 电化学',
            'mechanism': ' 工作原理 机理分析',
            'structure': ' 结构特性 官能团'
        }
        
        if state.query_intent in intent_focus:
            base_query += intent_focus[state.query_intent]
        
        return base_query


class InformationFusionAgent:
    """信息融合Agent - 融合多源信息"""
    
    def __init__(self, llm):
        self.llm = llm
        self.name = "InformationFusionAgent"
    
    def fuse(self, state: AgentPipelineState) -> AgentPipelineState:
        """融合信息 - 极速规则融合（无LLM）
        
        融合策略：
        1. 多样性去重：按来源分组
        2. 混合重排序：使用BGE-Reranker统一打分
        3. 上下文拼接：直接拼接成字符串，标记Ref-ID
        
        目标：30ms内完成，无LLM调用
        """
        state.log(self.name, "🔀 开始信息融合（极速规则融合）...")
        
        if not (state.graph_entities or state.vector_chunks or state.markdown_blocks or state.molecule_results):
            state.log(self.name, "⚠️  无可用的检索结果")
            return state
        
        doc_sources = []
        ref_id = 1
        context_parts = []
        
        # ========== Step 1: 多样性去重 ==========
        state.log(self.name, "   [Step 1] 多样性去重...")
        deduplicated_chunks = self._diversity_dedup(state.vector_chunks)
        state.log(self.name, f"   ✓ Vector去重: {len(state.vector_chunks)} → {len(deduplicated_chunks)} 个块")
        
        # ========== Step 2: 混合重排序 ==========
        state.log(self.name, "   [Step 2] 混合重排序...")
        all_candidates = []
        
        # 【注释】暂时不融合Graph RAG和分子查询信息 - 后续会加入
        # 【只保留】Vector(Milvus)和Web搜索信息
        
        if state.graph_entities:
             for entity_name, entity_data in state.graph_entities.items():
                 all_candidates.append({
                     'ref_id': None,  # 后续分配
                     'type': 'graph',
                     'source': entity_name,
                     'content': f"{entity_name}: {entity_data.get('properties', {})}",
                     'score': 0.95  # 图谱实体得分较高
                 })
         
        # 【新增】将 Graph RAG 的关系也传递给大模型
        if state.graph_relations:
             for rel in state.graph_relations:
                 # 构造关系的可读内容
                 if 'source' in rel and 'target' in rel:
                     rel_content = f"{rel.get('source', 'unknown')} → {rel.get('target', 'unknown')} ({rel.get('relationship', 'relation')})"
                 else:
                     rel_content = str(rel)
                 
                 all_candidates.append({
                     'ref_id': None,
                     'type': 'graph_relation',
                     'source': 'Graph RAG',
                     'content': rel_content,
                     'score': 0.92  # 图谱关系得分略低于实体
                 })
        
        if deduplicated_chunks:
            # 【改进】按照原始source分组，合并相同source的content
            source_groups = {}
            for idx, chunk in enumerate(deduplicated_chunks, 1):
                original_source = chunk.get('source', 'unknown')
                content = chunk.get('content', '')
                score = chunk.get('rerank_score', chunk.get('similarity', 0))
                
                if original_source not in source_groups:
                    source_groups[original_source] = {
                        'contents': [],
                        'scores': [],
                        'chunk_ids': []
                    }
                
                source_groups[original_source]['contents'].append(content)
                source_groups[original_source]['scores'].append(score)
                source_groups[original_source]['chunk_ids'].append(idx)
            
            # 【改进】为每个source创建候选项
            # 保持多source结构：多个source，每个source对应多个content
            for original_source, group_data in source_groups.items():
                # 将同一source的多个content拼接
                merged_content = "\n---\n".join(group_data['contents'])
                # 使用最高得分
                max_score = max(group_data['scores']) if group_data['scores'] else 0
                # 构建source标识（保留原始source，用括号注明包含的块数）
                source_label = f"{original_source} (包含{len(group_data['contents'])}个块)"
                
                all_candidates.append({
                    'ref_id': None,
                    'type': 'vector',
                    'source': original_source,  # 保留原始source用于后续去重和引用
                    'source_label': source_label,  # 用于展示
                    'content': merged_content,  # 合并后的content
                    'chunk_ids': group_data['chunk_ids'],
                    'score': max_score
                })
        
        # if state.markdown_blocks:
        #     for block in state.markdown_blocks:
        #         all_candidates.append({
        #             'ref_id': None,
        #             'type': 'web',
        #             'source': block.get('source', 'web'),
        #             'content': block.get('content', ''),
        #             'score': 0.65  # Web结果得分较低
        #         })
        # 
        # 【注释】暂时不融合分子查询 - 后续会加入
        # if state.molecule_results:
        #     for mol in state.molecule_results:
        #         mol_id = mol.get('identifier', '未知')
        #         mol_formula = mol.get('formula', 'N/A')
        #         mol_info = f"{mol_id} (分子式: {mol_formula})"
        #         for key, value in mol.items():
        #             if key not in ['identifier', 'source_file', 'success', 'formula'] and value:
        #                 mol_info += f" | {key}: {value}"
        #         
        #         all_candidates.append({
        #             'ref_id': None,
        #             'type': 'molecule',
        #             'source': '分子查询工具',
        #             'content': mol_info,
        #             'score': 0.75  # 分子数据得分
        #         })
        
        # 按得分降序排序
        all_candidates.sort(key=lambda x: x['score'], reverse=True)
        
        # 【调试】打印融合前的候选数量统计
        vector_count = sum(1 for c in all_candidates if c['type'] == 'vector')
        graph_count = sum(1 for c in all_candidates if c['type'] == 'graph')
        rel_count = sum(1 for c in all_candidates if c['type'] == 'graph_relation')
        web_count = sum(1 for c in all_candidates if c['type'] == 'web')
        mol_count = sum(1 for c in all_candidates if c['type'] == 'molecule')
        state.log(self.name, f"   [融合前] 候选统计 - Vector: {vector_count}, Graph: {graph_count}, Relation: {rel_count}, Web: {web_count}, Molecule: {mol_count}")
        
        # ========== Step 3: 策略性选择 Top 35 ==========
        state.log(self.name, "   [Step 3] 策略性选择Top结果...")
        selected_candidates = self._select_candidates_strategically(all_candidates)
        state.log(self.name, f"   ✓ 选择 {len(selected_candidates)} 个候选作为融合源")
        
        # ========== Step 4: 上下文拼接 ==========
        state.log(self.name, "   [Step 4] 上下文拼接...")
        
        # 【关键修改】仅为 Milvus(vector) 资料分配 ref_id
        # 其他来源（graph, molecule, web）不分配 ref_id，不标记
        milvus_ref_id = 1  # 仅Milvus使用
        
        for candidate in selected_candidates:
            content = self._clean_content(candidate['content'])
            if content.strip():
                # 【关键修改】仅Vector类型标记 + Ref ID
                if candidate['type'] == 'vector':
                    # 仅Milvus接收 Ref-n 标记
                    candidate['ref_id'] = milvus_ref_id
                    source_display = candidate.get('source_label', candidate.get('source', 'unknown'))
                    context_parts.append(f"[Ref-{milvus_ref_id}][{source_display}] {content}")
                    
                    doc_sources.append({
                        'ref_id': milvus_ref_id,
                        'type': candidate['type'],
                        'source': candidate.get('source', 'unknown'),
                        'source_label': candidate.get('source_label', ''),
                        'content': content,
                        'score': candidate['score']
                    })
                    
                    milvus_ref_id += 1
                # 
                # 【注释】其他来源暂不融合
                # else:
                #     if candidate['type'] == 'graph':
                #         context_parts.append(f"[图谱] {content}")
                #     elif candidate['type'] == 'graph_relation':
                #         context_parts.append(f"[图谱关系] {content}")
                #     elif candidate['type'] == 'web':
                #         context_parts.append(f"[Web] {content}")
                #     elif candidate['type'] == 'molecule':
                #         context_parts.append(f"[分子] {content}")
        
        # 直接拼接，不做LLM摘要
        from .evidence_sources import prepare_sources, context_from_sources
        prepare_sources(state)
        state.fused_context = context_from_sources(state.doc_sources)
        state.fusion_confidence = 0.9  # 规则融合置信度较高
        state.evidence_sources = [
            f"graph_entities({len(state.graph_entities)})",
            f"graph_relations({len(state.graph_relations)})",
            f"vector({len(deduplicated_chunks)})",
            f"molecule({len(state.molecule_results)})",
            f"web({len(state.markdown_blocks)})"
        ]
        
        # 【调试】打印并记录融合后的doc_sources统计
        vector_in_sources = sum(1 for s in doc_sources if s.get('type') == 'vector')
        state.log(self.name, f"   [融合后] doc_sources中的Vector类型: {vector_in_sources} 个")
        state.log(self.name, f"   [融合后] doc_sources总数: {len(doc_sources)} 个")
        
        # 【修改】将原本的print输出改为state.log，以便前端显示
        if deduplicated_chunks:
            state.log(self.name, f"        │ ✅ Milvus RAG: {len(deduplicated_chunks):>2} 个块 → 合并为 {vector_count} 个source")
        if state.molecule_results:
            state.log(self.name, f"        │ 分子查询: {len(state.molecule_results):>3} 个结果")
        if state.markdown_blocks:
            state.log(self.name, f"        │ Web 搜索: {len(state.markdown_blocks):>1} 个结果")
        state.log(self.name, f"        ├───────────────────────────────────────┤")
        state.log(self.name, f"        │ 📤 总计写入 Prompt: {len(doc_sources):>2} 个Ref")
        state.log(self.name, f"        │ 📝 融合上下文: {len(state.fused_context):>5} 字符")
        state.log(self.name, f"        │ 💡 数据流: Milvus块 → 按source分组 → 合并content → 一个Ref")
        
        state.log(self.name, f"✓ 极速融合完成: {len(doc_sources)} 个来源, 置信度: {state.fusion_confidence:.2f}")
        
        # 【修改】不再分割context_parts - 直接使用单轮LLM处理所有source
        # 将fused_context_parts设为空列表，触发_generate_sequential()而不是_generate_parallel()
        state.fused_context_parts = []
        state.log(self.name, f"   ✓ 融合信息已准备，使用单轮LLM处理")
        
        return state
    
    def _diversity_dedup(self, chunks: List[Dict]) -> List[Dict]:
        """不去重：将所有块都返回
        
        【改进】完全不去重，将召回的所有块（20个）全部保留
        允许同一文献的多个块都参与融合，充分利用检索到的所有相关信息
        """
        if not chunks:
            return []
        
        # 【改进】直接返回所有块，不进行任何去重
        # 按rerank_score排序，保留全部20个块
        deduplicated = sorted(chunks, key=lambda x: x.get('rerank_score', x.get('similarity', 0)), reverse=True)
        
        state_log = f"[不去重策略] 保留全部{len(deduplicated)}个块"
        self._log(state_log)
        
        return deduplicated
    
    def _select_candidates_strategically(self, all_candidates: List[Dict]) -> List[Dict]:
        """策略性选择Top结果：全量传递
        
        【改进】将所有候选都传递给大模型，不进行削减
        
        策略调整：
        - Vector: 全量 (将所有向量块传递)
        - Graph: 全量 (保留所有实体)
        - Molecule: 全量 (保留所有分子结果)
        - Web: 全量 (保留所有Web结果)
        """
        if not all_candidates:
            return []
        
        # 【改进】直接返回所有候选，不进行任何削减
        selected = all_candidates
        
        # 统计信息用于调试
        type_counts = {'graph': 0, 'vector': 0, 'web': 0, 'molecule': 0}
        for candidate in selected:
            cand_type = candidate['type']
            if cand_type in type_counts:
                type_counts[cand_type] += 1
        
        # 【调试】打印选择统计
        self._log(f"\n【候选选择统计 - 全量模式】")
        self._log(f"  总候选数: {len(all_candidates)} → 选中: {len(selected)} 个（全部传递）")
        self._log(f"  分布: Graph={type_counts['graph']}, Vector={type_counts['vector']}, Molecule={type_counts['molecule']}, Web={type_counts['web']}")
        
        return selected
    
    def _log(self, message: str):
        """调试日志"""
        logger.debug(f"[{self.name}] {message}")
    
    def _clean_content(self, content: str) -> str:
        """清理内容"""
        import re
        content = re.sub(r'https?://[^\s]+', '', content)
        content = re.sub(r'www\.[^\s]+', '', content)
        content = re.sub(r'!\[[^\]]*\]\([^)]*\)', '', content)
        content = re.sub(r'<img[^>]*>', '', content)
        content = re.sub(r'\n\s*\n', '\n', content)
        content = re.sub(r'\s+', ' ', content)
        return content.strip()
    
    def _split_context_by_vector_source(self, state: 'AgentPipelineState', 
                                       doc_sources: List[Dict],
                                       context_parts: List[str]) -> List[Dict]:
        """按Milvus source分割融合上下文 - 每个Vector source一个部分 + Graph + 分子信息
        
        【新增】分割策略优化：
        1. 收集所有Vector type的doc_sources
        2. 按不同的source分组（最多3个）
        3. 为每个Vector source创建一个部分，附上Graph RAG + 分子查询信息
        4. 优先级：Milvus > Graph RAG > 分子查询
        5. 如果Milvus中有准确答案，则不需要参考其他两种
        
        输出效果：
        [
            {
                'part_id': 0,
                'vector_source': 'paper1.pdf',
                'context': '[Ref-1]...Milvus内容...[graph_rag]...分子信息...', 
                'doc_sources': [...],
                'supplementary_info': 'graph_rag...分子信息...'  # 辅助信息
            },
            ...
        ]
        """
        import re
        
        # 收集所有Vector类型
        vector_sources = [s for s in doc_sources if s.get('type') == 'vector']
        non_vector_sources = [s for s in doc_sources if s.get('type') != 'vector']
        
        if not vector_sources:
            # 没有Vector源，不分割
            return []
        
        # 按source分组Vector源（每个Vector源可能有多个块）
        vector_source_groups = {}
        for source in vector_sources:
            source_name = source.get('source', 'unknown')
            if source_name not in vector_source_groups:
                vector_source_groups[source_name] = []
            vector_source_groups[source_name].append(source)
        
        # 【优化】最多支持15个Vector source的并行处理（可根据API限制调整）
        max_parallel_sources = 15  # 可配置上限
        vector_sources_list = list(vector_source_groups.keys())[:max_parallel_sources]
        
        # 【新增调试】显示Source分割的详细情况
        # print(f"\n        📊 【Source分割统计】")
        # print(f"        • 总unique source数: {len(vector_source_groups)} 个")
        # print(f"        • 并行处理source数: {len(vector_sources_list)} 个")
        if len(vector_source_groups) > max_parallel_sources:
            print(f"        ⚠️  超出上限：将{len(vector_source_groups)}个source限制为{max_parallel_sources}个")
            print(f"           未处理的source将被丢弃，建议增加max_parallel_sources或减少top_k")
        
        # 【修改】仅准备分子查询的辅助信息，不再包含 Graph RAG 信息
        molecule_info = self._format_molecule_info(state)
        
        parts = []
        for part_id, vector_source_name in enumerate(vector_sources_list):
            # 收集此source的所有ref_id
            vector_refs_in_source = [s.get('ref_id') for s in vector_source_groups[vector_source_name]]
            
            # 构建此部分的context，仅标记vector的ref
            part_context_lines = []
            
            for line in context_parts:
                # 提取此行中的ref_id (例如 [Ref-1])
                ref_match = re.search(r'\[Ref-(\d+)\]', line)
                if not ref_match:
                    continue
                
                ref_id = int(ref_match.group(1))
                
                # 判断是否是此Vector source或其他源
                source_type = None
                for source in doc_sources:
                    if source.get('ref_id') == ref_id:
                        source_type = source.get('type')
                        break
                
                # 执行标记：仅标记此Vector source的块和非向量源
                if ref_id in vector_refs_in_source or source_type != 'vector':
                    if source_type == 'vector' and ref_id not in vector_refs_in_source:
                        # 此Vector块属于其他source，不显示
                        # 移除[Ref-n]标记
                        line_cleaned = re.sub(r'\[Ref-\d+\]', '', line).strip()
                        if line_cleaned:
                            part_context_lines.append(line_cleaned)
                    else:
                        # 是此source的Vector块或非向量源，保留[Ref-n]标记
                        part_context_lines.append(line)
            
            # 构建此部分的主context（Milvus内容）
            milvus_context = "\n".join(part_context_lines)
            
            # 【修改】仅添加分子查询辅助信息，移除 Graph RAG 实体关系参考
            supplementary_info = ""
            if molecule_info:
                supplementary_info += f"\n\n【参考信息 - 分子查询结果】\n{molecule_info}"
            
            # 完整context = Milvus主内容 + 辅助信息
            full_context = milvus_context + supplementary_info
            
            # 构建此部分的doc_sources：此source的vector + 所有非向量源
            part_doc_sources = []
            for source in doc_sources:
                if source.get('type') == 'vector' and source.get('source') == vector_source_name:
                    part_doc_sources.append(source)
                elif source.get('type') != 'vector':
                    part_doc_sources.append(source)
            
            parts.append({
                'part_id': part_id,
                'vector_source': vector_source_name,
                'context': full_context,  # 包含Milvus + 辅助信息
                'doc_sources': part_doc_sources,
                'vector_refs': vector_refs_in_source,
                'supplementary_info': supplementary_info  # 保存辅助信息供调试
            })
        
        # 打印分割详情
        state.log(self.name, f"\n   【分割量化】")
        for part in parts:
            vector_count = sum(1 for s in part['doc_sources'] if s.get('type') == 'vector')
            other_count = sum(1 for s in part['doc_sources'] if s.get('type') != 'vector')
            has_graph = '(含Graph)' if state.graph_entities or state.graph_relations else ''
            has_mol = '(含分子)' if state.molecule_results else ''
            state.log(self.name, f"   第{part['part_id']}部分: {part['vector_source']} + {other_count}个非向量源 {has_graph}{has_mol} = {vector_count + other_count}个Ref")
        
        return parts
    

    
    def _format_molecule_info(self, state: 'AgentPipelineState') -> str:
        """格式分子查询的结果为字符串
        
        仅在上Milvus中没有准确答案的情况下才追使用
        """
        if not state.molecule_results:
            return ""
        
        info_lines = []
        for mol in list(state.molecule_results)[:3]:  # 最多Top 3分子
            identifier = mol.get('identifier', 'Unknown')
            formula = mol.get('formula', 'N/A')
            smiles = mol.get('smiles', 'N/A')
            
            mol_info = f"• {identifier}"  # 分子名称
            if formula and formula != 'N/A':
                mol_info += f" (分子式: {formula})"
            
            info_lines.append(mol_info)
            
            # 添加主要性质（最多Top 5）
            prop_count = 0
            for key, value in mol.items():
                if key not in ['identifier', 'formula', 'smiles', 'success'] and value and value != 'N/A':
                    if prop_count < 5:
                        info_lines.append(f"  - {key}: {value}")
                        prop_count += 1
                    else:
                        break
        
        return "\n".join(info_lines) if info_lines else ""


class AnswerGenerationAgent:
    """答案生成Agent - 基于融合信息生成最终答案"""
    
    def __init__(self, llm, internlm=None):
        self.llm = llm
        self.internlm = internlm or llm  # 如果没有提供internlm，退回到默认llm
        self.name = "AnswerGenerationAgent"
        self.ref_id_map = {}  # 临时序号映射字典: {ref_id: {title, doc_id, filename}}
        self.parallel_llm_manager = None  # 【新增】并行LLM管理器
    
    def generate(self, state: AgentPipelineState) -> AgentPipelineState:
        """生成最终答案 - 支持多部分并行生成
        
        【新增】如果有分割后的融合部分（fused_context_parts），使用并行LLM生成答案
        否则使用原始的单轮生成逻辑
        """
        state.log(self.name, "💬 开始答案生成...")
        
        # 【关键】检查是否有分割后的融合部分
        # 【修改】现在Stage3不再分割，fused_context_parts为空，直接使用单轮生成
        return self._generate_sequential(state)
    
    def _generate_sequential(self, state: AgentPipelineState) -> AgentPipelineState:
        """原始的顺序生成模式 - 保持向后兼容"""
        # 【第一步】数据清洗与映射构建（预处理阶段）
        # 【关键】使用 Stage 3 的全局 doc_sources，不再过滤和重编号！
        all_sources = state.doc_sources if state.doc_sources else []
        
        # 【关键】构建临时序号映射机制（使用全局 doc_sources）
        self.ref_id_map = self._build_ref_id_map(all_sources)
        state.log(self.name, f"✓ 构建临时映射: {len(self.ref_id_map)} 个文献来源 (包含所有类型)")
        
        # 【第二步】Prompt上下文注入 - 使用全局的 Ref-序号
        citation_mapping = self._build_prompt_context(all_sources)
        
        # 【第二步续】明确的引用指令
        sources_hint = self._build_citation_instruction(len(all_sources))
        
        # 【第三步】构造最终Prompt
        prompt = self._build_final_prompt(
            sources_hint, 
            citation_mapping, 
            state.fused_context, 
            state.original_question,
            len(all_sources)
        )
        if state.information_needs:
            prompt += '\n【本题需求检查】\n' + '\n'.join('- ' + need for need in state.information_needs)
            prompt += '\n逐项给出实际原文支持的回答，缺口限定为当前检索范围；不得为了凑齐需求而补造。'
        
        try:
            state.log(self.name, "   根据证据准备答案...")
            # 【打开】打印 Prompt 中的内容统计
            print(f"\n" + "="*80)
            print(f"📊 融合后的信息统计")
            print(f"="*80)
            print(f"  • 引用指令长度: {len(sources_hint):,} 字符")
            print(f"  • 上下文映射长度: {len(citation_mapping):,} 字符")
            print(f"  • 融合上下文长度: {len(state.fused_context):,} 字符")
            print(f"  • 信息来源数量: {len(all_sources)} 个Ref")
            
            # 【新增调试】统计各类型的source
            vector_sources = [s for s in all_sources if s.get('type') == 'vector']
            graph_sources = [s for s in all_sources if s.get('type') == 'graph']
            relation_sources = [s for s in all_sources if s.get('type') == 'graph_relation']
            web_sources = [s for s in all_sources if s.get('type') == 'web']
            molecule_sources = [s for s in all_sources if s.get('type') == 'molecule']
            unique_vector_sources = set(s.get('source', '') for s in vector_sources if s.get('source'))
            
            # print(f"\n  📂  来源类型分布:")
            # print(f"    • Vector类型: {len(vector_sources)} 个Ref (来自 {len(unique_vector_sources)} 个文献)")
            # print(f"    • Graph类型: {len(graph_sources)} 个Ref")
            # print(f"    • Relation类型: {len(relation_sources)} 个Ref")
            # print(f"    • Web类型: {len(web_sources)} 个Ref")
            # print(f"    • Molecule类型: {len(molecule_sources)} 个Ref")
            
            if vector_sources:
                print(f"\n  📄 Vector文献样本 (前5个):")
                for i, s in enumerate(vector_sources[:5], 1):
                    content_preview = s.get('content', '')[:80].replace('\n', ' ')
                    print(f"    [Ref-{s.get('ref_id')}] {s.get('source', 'unknown')}")
                    # print(f"              预览: {content_preview}...")
                if len(vector_sources) > 5:
                    print(f"    ... 还有 {len(vector_sources) - 5} 个Ref")
            
            # print(f"\n" + "="*80)
            # print(f"📝 最终Prompt预览 (前50000字符)")
            # print(f"="*80)
            # prompt_preview = prompt[:50000].replace('\n', '\n  ')
            # print(f"  {prompt_preview}")
            # print(f"\n  ... (总长度: {len(prompt):,} 字符)")
            # print(f"="*80)
            
            # 【第四步】大模型生成与标记
            print("" + "="*80)
            print("💬 最终答案 (依据检索证据)")
            print("="*80 + "\n")
            
            # 【关键修改】使用 GLM 生成最终回答
            final_llm = self.internlm if self.internlm else self.llm
            
            # Stage 4 答案生成：四段式结构 + 文献增强 + 专业推理兜底
            from .answer_grounding import SYSTEM_PROMPT
            system_msg = SYSTEM_PROMPT
            
            # 【新增】定义流式更新回调
            def on_answer_chunk(chunk):
                state.final_answer += chunk
                
            def on_answer_reasoning(reasoning):
                state.answer_reasoning += reasoning

            from .lineage_answer import render_lineage_answer
            answer = render_lineage_answer(state.original_question, state.doc_sources)
            llm_generation = answer is None
            empty_answer_retry = False
            native_generation = None
            from .grounding_audit import enabled as native_enabled
            if answer is None and native_enabled(final_llm):
                from .native_answer import generate_native_answer
                answer, native_generation = generate_native_answer(
                    final_llm, prompt, system_msg, state.doc_sources, state.fused_context,
                    question=state.original_question,requirements=getattr(state,'answer_requirements',None))
                state.log(self.name, "最终正文以原生JSON完整返回；Thinking关闭，完整性/引用/量值来源约束不等于完整语义确认")
            if answer is None:
                answer = final_llm.call_llm(
                prompt, 
                temperature=0.0, 
                max_tokens=6000, 
                repetition_penalty=1.1,
                stream=True,
                system_prompt=system_msg,  # 【新增】禁用记忆+强制引用
                on_chunk=on_answer_chunk,  # 【新增】流式回调
                    on_reasoning=on_answer_reasoning # 【新增】思考过程回调
                )
                if not str(answer or '').strip():
                    empty_answer_retry = True
                    state.log(self.name, "生成接口未返回最终正文，进行一次有界重试")
                    state.final_answer = ''
                    state.answer_reasoning = ''
                    prompt += '\n请缩短分析并输出最终正文，按用户需求给出有原文引用的结论与缺口；不要只返回思考。'
                    answer = final_llm.call_llm(
                        prompt, temperature=0.0, max_tokens=10000,
                        repetition_penalty=1.1, stream=True, system_prompt=system_msg,
                        on_chunk=on_answer_chunk, on_reasoning=on_answer_reasoning)
                    if not str(answer or '').strip():
                        raise RuntimeError('生成接口两次未返回最终正文')
                if str(answer).startswith('❌'):
                    raise RuntimeError('生成接口返回失败：' + str(answer)[:120])
            elif not llm_generation:
                state.log(self.name, "谱系答复按人工校正记录直接渲染：保留端点、方向、状态与证据句编号")
            if llm_generation:
                from .grounding_audit import audit_answer
                semantic_audit=(native_generation or {}).get('source_screening')
                if not semantic_audit:
                    answer, semantic_audit = audit_answer(final_llm, state.original_question, answer,
                                                          state.doc_sources, state.fused_context)
                state.log(self.name, f"原文事实筛查：{semantic_audit['status']}，调整 {len(semantic_audit.get('changes', []))} 处")
                if native_generation and native_generation.get('strict_validation_enabled'):
                    from .grounding_audit import evidence_catalog
                    from .native_answer import draft_issues, source_uncertainty_notes
                    final_refs={int(s['ref_id']) for s in state.doc_sources if s.get('ref_id')}
                    final_catalog=evidence_catalog(state.doc_sources,state.fused_context,final_refs)
                    final_checks=[]
                    final_issues=draft_issues(answer,state.doc_sources,final_catalog,
                        source_uncertainty_notes(final_catalog,state.doc_sources),state.original_question,final_checks,strict_validation=True)
                    native_generation['post_audit_evidence_catalog']=final_catalog
                    answer,native_generation=_post_audit_native_result(
                        answer,native_generation,semantic_audit,final_checks,final_issues)
            else:
                semantic_audit = {'status': 'authoritative_record_rendered', 'semantic_support_verified': False}
            state.final_answer = answer
            # No calibrated probability of factual correctness is available.
            state.answer_confidence = 0.0
            state.reasoning_chain = "[Question Parsing] → [Multi-Source Retrieval] → [Information Fusion] → [Answer Generation]"
            state.log(self.name, "✓ 答案生成完成；引用定位与事实支撑分别核验")
            
            # 【第五步】后端还原与拼接（后处理阶段）
            final_answer = self._post_process_answer_new_format(answer, all_sources, state.doc_sources)

            # 【新增】最终输出清洗:剥离元评论、修复区间符号、清理空【文献来源】节
            try:
                try:
                    from .answer_cleaner import clean_final_answer
                except ImportError:
                    from answer_cleaner import clean_final_answer
                final_answer = clean_final_answer(final_answer, sources=state.doc_sources)
            except Exception as _e:
                state.log(self.name, f"⚠️ 最终输出清洗跳过: {_e}")

            # 【新增】手动打印文献来源到终端（解决流式输出不显示后处理内容的问题）
            sources_section = self._extract_sources_section(final_answer)
            if sources_section:
                print(f"\n{sources_section}")

            # 更新state的final_answer
            state.final_answer = final_answer
            from .answer_grounding import check_citations, verify_semantic_support
            semantic_support = verify_semantic_support(final_answer, state.doc_sources, llm=final_llm)
            state.answer_quality = check_citations(final_answer, state.doc_sources, semantic=semantic_support)
            state.answer_quality['grounding_audit'] = semantic_audit
            state.answer_quality['generation_status'] = 'returned_final_answer'
            state.answer_quality['operation_errors'] = list(state.operation_errors)
            state.answer_quality['confidence_calibrated'] = False
            state.answer_quality['generation_input'] = {
                'source_supplements': getattr(state, 'source_supplement_diagnostics', {}),
                'llm_called': llm_generation,
                'prompt_chars': native_generation['prompt_chars'] if native_generation else len(prompt) if llm_generation else 0,
                'system_chars': native_generation['system_chars'] if native_generation else len(system_msg) if llm_generation else 0,
                'evidence_chars': len(state.fused_context),
                'source_catalog_chars': len(citation_mapping),
                'empty_answer_retry': empty_answer_retry,
                'token_count': None, 'token_count_note': '既有流式客户端未暴露完整usage',
            }
            if native_generation:
                state.answer_quality['generation_input'].update(
                    method='native_instant_json', native_generation=native_generation,
                    token_count_note='原生生成各次实际usage见structured_calls；不推造未返回的token统计')
            if state.answer_quality['invalid_refs']:
                state.log(self.name, f"引用编号无法映射: {state.answer_quality['invalid_refs']}")
            
            # 【新增】不再需要打印文献来源部分（已经在后处理中包含）
            print("="*80 + "\n")
        
        except Exception as e:
            state.log(self.name, f"❌ 答案生成失败: {e}")
            state.final_answer = "无法生成答案"
            state.answer_confidence = 0.0
            state.operation_errors.append('generation_failure:' + type(e).__name__)
            state.answer_quality.update(generation_status='failed',
                                        operation_errors=list(state.operation_errors))
            failed_native = getattr(e, 'generation_metadata', None)
            if failed_native:
                state.answer_quality['generation_input'] = {
                    'llm_called': True, 'method': 'native_instant_json',
                    'prompt_chars': failed_native['prompt_chars'], 'system_chars': failed_native['system_chars'],
                    'evidence_chars': len(state.fused_context), 'source_catalog_chars': len(citation_mapping),
                    'native_generation': failed_native, 'token_count': None,
                    'token_count_note': '失败调用及实际usage见structured_calls；不推造未返回的token统计'}
        
        return state
    
    def _generate_parallel(self, state: AgentPipelineState) -> AgentPipelineState:
        """并行生成模式 - 每个source给一个LLM处理
        
        【核心逻辑】：
        1. 每个source对应一个LLM（最多8个）
        2. 全局统一ref_id：[Ref-1], [Ref-2], ...（全局顺序）
        3. 每个LLM仅看到本source的content和本source的ref_id范围
        4. 并行调用8个Kimi API
        5. 按ref_id顺序自动拼接（不手动插入分隔符）
        """
        # 加载并行LLM管理器
        try:
            from .part1_knowledge_arsenal import ParallelLLMManager
        except ImportError:
            from part1_knowledge_arsenal import ParallelLLMManager
        
        # 【第一步】获取全局所有source信息（用于显示全局ref_id）
        all_sources = state.doc_sources if state.doc_sources else []
        
        state.log(self.name, f"   【并行模式】为{len(state.fused_context_parts)}个source分别构建Prompt")
        print(f"\n" + "="*80)
        print(f"🚀 并行答案生成（每个source一个LLM，最多8个并行）")
        print(f"="*80)
        print(f"\n全局ref_id分配：")
        for part in state.fused_context_parts:
            vector_refs = part.get('vector_refs', [])
            vector_source = part.get('vector_source', '')
            print(f"  • Part {part.get('part_id')}: {vector_source}")
            if vector_refs:
                print(f"    └─ 对应ref范围: [Ref-{min(vector_refs)}] ~ [Ref-{max(vector_refs)}]")
        print()
        
        # 【第二步】为每个部分构建Prompt（每个LLM仅看到本source的内容）
        prompts = []
        part_infos = []
        
        for part in state.fused_context_parts:
            part_id = part.get('part_id')
            vector_source = part.get('vector_source')
            context = part.get('context')  # 此部分的context已包含该source的所有[Ref-n]
            doc_sources_in_part = part.get('doc_sources', [])
            vector_refs_in_part = part.get('vector_refs', [])
            
            # 【关键】为此部分构建Prompt上下文：仅包含此source的source列表
            part_citation_mapping = self._build_prompt_context_for_part(doc_sources_in_part)
            part_sources_hint = self._build_citation_instruction(len(doc_sources_in_part))
            
            # 构建此部分的最终Prompt
            part_prompt = self._build_final_prompt(
                part_sources_hint,
                part_citation_mapping,
                context,
                state.original_question,
                len(doc_sources_in_part)
            )
            
            prompts.append(part_prompt)
            part_infos.append({
                'part_id': part_id,
                'vector_source': vector_source,
                'doc_sources': doc_sources_in_part,
                'vector_refs': vector_refs_in_part,
                'all_sources': all_sources  # 保存全局sources用于后处理
            })
        
        state.log(self.name, f"   ✓ 已为{len(prompts)}个source构建了Prompt")
        
        # 【第三步】并行调用8个Kimi API（静默模式，不输出流式内容）
        state.log(self.name, f"   启动{len(prompts)}个并行LLM调用...")
        
        parallel_llm = ParallelLLMManager()
        answers = parallel_llm.call_llm_parallel(
            prompts=prompts,
            temperatures=[0.0] * len(prompts),
            max_tokens=50000,
            stream=False,  # 【关键】禁用流式输出，静默获取答案
            repetition_penalties=[1.1] * len(prompts)
        )
        
        state.log(self.name, f"   ✓ 所有{len(answers)}个并行调用完成")
        
        # 【第四步】检查并过滤答案（跳过无关内容）
        valid_answers_with_meta = []
        for part_info, answer in zip(part_infos, answers):
            part_id = part_info['part_id']
            vector_source = part_info['vector_source']
            vector_refs = part_info['vector_refs']
            
            # 检查答案是否有效（非空且不是"无信息"类回复）
            answer_clean = answer.strip()
            is_valid = self._is_valid_answer(answer_clean)
            
            valid_answers_with_meta.append({
                'part_id': part_id,
                'vector_source': vector_source,
                'vector_refs': vector_refs,
                'answer': answer_clean,
                'is_valid': is_valid
            })
        
        # 【第五步】拼接所有有效答案（过滤无效答案）
        print(f"\n" + "="*80)
        print(f"💬 各个LLM生成的答案")
        print(f"="*80 + "\n")
        
        import re
        final_answer_bodies = []
        source_labels = []
        valid_count = 0
        
        for idx, item in enumerate(valid_answers_with_meta):
            if not item['is_valid']:
                continue  # 跳过无关答案
            
            part_id = item['part_id']
            vector_source = item['vector_source']
            vector_refs = item['vector_refs']
            answer = item['answer']
            
            # 【关键】检查是否为"无信息"类答案（仅包含提示文本）
            answer_clean = re.sub(r'\[Ref-\d+(?:,\s*\d+)*\]', '', answer).strip()
            
            # 过滤掉纯提示类答案
            if answer_clean == "提供的文献中未涉及此内容":
                print(f"【Part {part_id}】⊘ 已跳过（无信息）")
                print(f"\n" + "-"*80 + "\n")
                continue
            
            answer_clean = answer_clean.rstrip('。').strip()
            valid_count += 1
            
            # 仅显示单个ref_id
            ref_id = vector_refs[0] if vector_refs else None
            
            # 格式：{LLM回答内容}[Ref-n]。
            if ref_id:
                formatted_body = f"{answer_clean}[Ref-{ref_id}]。"
                source_label = f"[Ref-{ref_id}]：{vector_source}"
            else:
                formatted_body = f"{answer_clean}。"
                source_label = f"[Source]：{vector_source}"
            
            # 打印每个有效LLM的答案正文
            print(f"【Part {part_id}】✓ 有效")
            print(f"{formatted_body}")
            print(f"\n" + "-"*80 + "\n")
            
            final_answer_bodies.append(formatted_body)
            source_labels.append(source_label)
        
        # 【第六步】使用LLM生成综合答案
        print(f"\n" + "="*80)
        print(f"🔄 使用LLM综合各部分答案")
        print(f"="*80 + "\n")
        print(f"   • 有效答案部分：{valid_count} 个")
        print(f"   • 无效/已跳过：{len(valid_answers_with_meta) - valid_count} 个")
        print()
        
        if final_answer_bodies:
            # 构建LLM综合提示
            merged_answer = self._synthesize_answers_with_llm(
                state.original_question,
                final_answer_bodies,
                source_labels
            )
        else:
            # 文献库无相关内容，回退到储能专业知识推理
            print("   ⚠️  文献库中未检索到相关内容，启用专业推理模式...")
            fallback_prompt = f"""你是储能领域专家，在电化学储能、液流电池、锂离子电池等方向有深厚积累。

用户问题：{state.original_question}

当前知识库中未检索到与该问题直接相关的文献。请基于你的储能专业知识，给出：
1. 对该问题的专业分析
2. 可行的技术路径或解决方案
3. 相关的研究方向建议

请直接作答，不要提及"数据库无内容"等字眼，给出有实质价值的专业回答。"""
            try:
                merged_answer = self.llm.call_llm(fallback_prompt, temperature=0.3, max_tokens=50000, repetition_penalty=1.05)
                if not merged_answer or not merged_answer.strip():
                    merged_answer = "暂时无法生成答案，请稍后重试。"
            except Exception:
                merged_answer = "暂时无法生成答案，请稍后重试。"
        
        print(f"\n" + "="*80)
        print(f"✨ 最终综合答案")
        print(f"="*80 + "\n")
        print(merged_answer)
        
        # 【第六步】后处理：整理文献来源
        self.ref_id_map = self._build_ref_id_map(all_sources)
        # 使用统一的后处理逻辑生成文献列表
        final_answer_with_sources = self._post_process_merged_answer(merged_answer, all_sources)
                    
        # 【新增】手动打印文献来源到终端
        sources_section = self._extract_sources_section(final_answer_with_sources)
        if sources_section:
            print(f"\n{sources_section}")
                    
        state.doc_sources = all_sources
        state.final_answer = final_answer_with_sources
        state.answer_confidence = 0.75
        state.reasoning_chain = "[Question Parsing] → [Multi-Source Retrieval] → [Information Fusion with Splitting] → [Parallel Answer Generation] → [Answer Merging]"
        state.log(self.name, f"✓ 并行答案生成完成，置信度: {state.answer_confidence:.2f}")
        
        print(f"="*80 + "\n")
        return state
    
    def _synthesize_answers_with_llm(self, question: str, answer_bodies: List[str], source_labels: List[str]) -> str:
        """直接拼接所有并行LLM的答案（不经过LLM重新生成）
        
        【改进】根据用户偏好规范，保留所有原始LLM回答内容
        不进行LLM总结或重新生成，直接拼接各部分答案
        """
        import re
        
        # 【第一步】按照规范要求拼接所有答案
        # 在拼接前，提供一个简短的客观综述开头
        synthesis_prompt = f"""根据以下多个LLM对液流电池问题的回答，生成一个简短的客观综述开头（仅综述，不捏造）。

用户问题：{question}

多个LLM的回答（去除Ref标记）：
"""
        
        pure_answers = []
        for answer_body in answer_bodies:
            # 去掉[Ref-n]标记
            pure_content = re.sub(r'\[Ref-\d+\]', '', answer_body).rstrip('。').strip()
            pure_answers.append(pure_content)
            synthesis_prompt += f"\n- {pure_content}\n"
        
        synthesis_prompt += """\n
请生成一个1-2句的客观综述开头，总结各回答的共同点或差异点，不要捏造信息。输出仅包含综述文本。"""
        
        # 【第二步】调用LLM生成简短的综述开头
        summary_intro = ""
        try:
            print("   📝 正在生成综述开头...")
            summary_intro = self.llm.call_llm(synthesis_prompt, temperature=0.0, max_tokens=50000, repetition_penalty=1.1)
            print("   ✓ 综述生成完成")
        except Exception as e:
            print(f"   ⚠️  综述生成失败: {e}，使用空综述")
            summary_intro = ""
        
        # 【第三步】构建最终答案：综述 + 所有原始答案
        final_parts = []
        
        # 添加综述（如果生成成功）
        if summary_intro.strip():
            final_parts.append(summary_intro.strip())
        
        # 添加所有原始LLM答案（保留Ref标记）
        for answer_body in answer_bodies:
            final_parts.append(answer_body)
        
        merged_answer = "\n\n".join(final_parts)
        
        # 【第四步】构建文献来源部分
        unique_sources = []
        seen_sources = set()
        for label in source_labels:
            if label not in seen_sources:
                unique_sources.append(label)
                seen_sources.add(label)
        
        sources_text = "\n\n".join(unique_sources) if unique_sources else ""
        
        # 【第五步】拼接最终答案
        if sources_text:
            final_answer = f"{merged_answer}\n\n---\n\n{sources_text}"
        else:
            final_answer = merged_answer
        
        return final_answer
    
    def _build_direct_merged_answer(self, answer_bodies: List[str], source_labels: List[str]) -> str:
        """直接拼接答案（备用方案）"""
        import re
        
        body_text = "\n\n".join(answer_bodies)
        
        unique_sources = []
        seen_sources = set()
        for s in source_labels:
            if s not in seen_sources:
                unique_sources.append(s)
                seen_sources.add(s)
        
        sources_text = "\n\n".join(unique_sources)
        merged_answer = f"{body_text}\n\n---\n\n{sources_text}"
        
        return merged_answer
    
    def _build_ref_id_map(self, doc_sources: List[Dict]) -> Dict[int, Dict[str, str]]:
        """【第一步】构建临时序号映射
        
        关键改进：直接使用 Stage 3 分配的全局 ref_id，不再重编号！
        
        输入示例（来自 Stage 3 融合）：
            [
                {'ref_id': 1, 'type': 'graph', 'source': '实体名', 'content': '...'},
                {'ref_id': 2, 'type': 'vector', 'source': 'paper.pdf', 'content': '...', 'doc_id': 9798},
                {'ref_id': 3, 'type': 'vector', 'source': 'paper.pdf', 'content': '...', 'doc_id': 1234},
                {'ref_id': 4, 'type': 'web', 'source': '秘塔搜索', 'content': '...'},
            ]
        
        输出示例（保持全局序号）：
            {
                1: {'title': '实体名', 'type': 'graph', 'doc_id': None},
                2: {'title': 'paper.pdf', 'type': 'vector', 'doc_id': 9798},
                3: {'title': 'paper.pdf', 'type': 'vector', 'doc_id': 1234},
                4: {'title': '秘塔搜索', 'type': 'web', 'doc_id': None},
            }
        """
        ref_id_map = {}
        
        for source in doc_sources:
            ref_id = source.get('ref_id')  # 使用 Stage 3 分配的全局 ref_id
            if not ref_id:
                continue  # 跳过没有 ref_id 的
            
            # 优先使用 source 字段作为标题，其次使用 content 的前 50 字
            title = source.get('source', '').strip()
            if not title:
                content = source.get('content', '').strip()
                title = content[:50] if content else f'Reference {ref_id}'
            
            ref_id_map[ref_id] = {
                'title': source.get('source_label') or title,
                'type': source.get('type', 'unknown'),
                'doc_id': source.get('doc_id', None)
            }
        
        return ref_id_map
    
    def _build_prompt_context(self, doc_sources: List[Dict]) -> str:
        from .answer_grounding import citation_catalog
        return citation_catalog(doc_sources)
    
    def _build_prompt_context_for_part(self, doc_sources: List[Dict]) -> str:
        """为单个并行部分构建Prompt上下文
        
        【关键】仅包含此部分的sources，不包含其他部分的sources
        """
        context_parts = []
        
        for source in doc_sources:
            ref_id = source.get('ref_id')
            if not ref_id:
                continue
            
            content = source.get('content', '').strip()
            if not content:
                continue
            
            title = source.get('source', '').strip() or 'Unknown'
            source_type = source.get('type', 'unknown')
            
            # 检测是否为参考文献列表（噪音数据清洗）
            is_bibliography = self._is_bibliography(content)
            bibliography_flag = "[参考文献列表，已清洗] " if is_bibliography else ""
            
            # 按类型标记
            type_prefix = f"[{source_type.upper()}]"
            
            # 构造 [Ref-序号] 格式
            context_parts.append(
                f"[Ref-{ref_id}]{type_prefix} {bibliography_flag}{content}\n(来源: {title})"
            )
        
        return "\n".join(context_parts)
    
    def _post_process_merged_answer(self, merged_answer: str, all_sources: List[Dict]) -> str:
        """后处理合并后的答案 - 整理文献来源
        
        【关键】使用全局的ref_id_map，将多个部分的答案合并成统一的答案
        """
        if not merged_answer:
            return merged_answer
        
        # 构建全局ref_id_map用于提取引用
        self.ref_id_map = self._build_ref_id_map(all_sources)
        
        # 提取答案中的所有[Ref-n]标记
        import re
        ref_pattern = r'\[Ref-(\d+)\]'
        cited_ids = set()
        for match in re.finditer(ref_pattern, merged_answer):
            ref_id = int(match.group(1))
            cited_ids.add(ref_id)
        
        # 构建文献来源列表
        sources_section = "\n\n【文献来源】\n"
        
        if cited_ids:
            for ref_id in sorted(cited_ids):
                if ref_id in self.ref_id_map:
                    title = self.ref_id_map[ref_id].get('title', f'Reference {ref_id}')
                    source_type = self.ref_id_map[ref_id].get('type', 'unknown')
                    sources_section += f"[Ref-{ref_id}]：{title}\n\n"
        
        # 添加其他信息来源
        other_sources = [s for s in all_sources if s.get('type') not in ['vector']]
        if other_sources:
            sources_section += "【其他信息来源】\n\n"
            for source in other_sources:
                source_type = source.get('type', '')
                title = source.get('source', 'Unknown')
                if source_type == 'molecule':
                    sources_section += f"  🧪 分子查询: {title}\n\n"
                elif source_type == 'web':
                    sources_section += f"  🔍 网页搜索: {title}\n\n"
                elif source_type in ['graph', 'graph_relation']:
                    sources_section += f"  🔗 知识图谱: {title}\n\n"
        
        # 合并答案和文献来源
        final_answer = merged_answer + sources_section
        return final_answer
    
    def _clean_latex_format(self, text: str) -> str:
        """【新增】清理 LaTeX 公式，提高文本可读性
        
        处理场景：
        1. LaTeX 公式中的 \\mathrm{{}} 等冗余修饰 → 纯文本
        2. 智能轮换下标为 Unicode 下标
        3. 分段的浓度条件 → 整理为表格式
        4. \\cdot → · （中心点）
        5. 【新增】化学公式的特殊处理：$...$ 格式
        """
        import re
        
        result = text
        
        # 【新增】处理内联数学公式 $...$ 中的 \\mathrm{}
        # 示例：$\\mathrm{Cr}(\\mathrm{H}_2\\mathrm{O})_6^{3+}$ → Cr(H₂O)₆³⁺
        def clean_inline_formula(match):
            formula = match.group(1)
            # 移除 \\mathrm{}
            formula = re.sub(r'\\mathrm\{([^}]+)\}', r'\1', formula)
            # 处理下标：_2 → ₂
            formula = re.sub(r'_([0-9])', lambda m: self._convert_to_subscript(m.group(1)), formula)
            # 处理上标：^{3+} → ³⁺
            formula = re.sub(r'\\\^\{([^}]+)\}', lambda m: self._convert_to_superscript(m.group(1)), formula)
            formula = re.sub(r'\^\{([^}]+)\}', lambda m: self._convert_to_superscript(m.group(1)), formula)
            return formula
        
        # 替换 $...$ 格式的公式
        result = re.sub(r'\$([^$]+)\$', clean_inline_formula, result)
        
        # 1. 清理 \\mathrm{{}} 格式：\\mathrm{{FeCl}} → FeCl
        result = re.sub(r'\\mathrm\{([^}]+)\}', r'\1', result)
        
        # 2. 清理 \\text{{}} 格式：\\text{{M}} → M
        result = re.sub(r'\\text\{([^}]+)\}', r'\1', result)
        
        # 3. 清理中心点：\\cdot → ·
        result = result.replace('\\cdot', '·')
        
        # 4. 清理 _{{}} 格式: _{{2}} → ₂
        result = re.sub(r'_\{(\d+)\}', lambda m: self._convert_to_subscript(m.group(1)), result)
        
        # 5. 清理 \\^ 上标: H\\^ → H
        result = result.replace('\\^', '')
        
        # 6. 【新增】分段浓度条件：检测"浓度"等关键词，整理为一个表格
        result = self._format_concentration_list(result)
        
        return result
    
    def _convert_to_subscript(self, digit: str) -> str:
        """将数字转换为 Unicode 下标"""
        subscript_digits = {
            '0': '₀', '1': '₁', '2': '₂', '3': '₃', '4': '₄',
            '5': '₅', '6': '₆', '7': '₇', '8': '₈', '9': '₉'
        }
        return ''.join(subscript_digits.get(d, d) for d in digit)
    
    def _convert_to_superscript(self, text: str) -> str:
        """【新增】将文本转换为 Unicode 上标
        
        支持数字、正负号、符号等
        """
        superscript_map = {
            '0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴',
            '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹',
            '+': '⁺', '-': '⁻', '=': '⁼', '(': '⁽', ')': '⁾'
        }
        return ''.join(superscript_map.get(c, c) for c in text)
    
    def _format_concentration_list(self, text: str) -> str:
        """保持浓度列表的原始格式
        
        不进行任何格式转换，简单保持原样：
        "浓度为 0.1 M、0.2 M、0.3 M" 就一直是这样
        """
        return text
    
    def _is_valid_answer(self, answer: str) -> bool:
        """检查答案是否有效（非空且包含实质内容）
        
        【修改】当LLM明确表示文献中没有相关内容时，判定为无效答案
        这样可以被上层逻辑过滤掉，不会出现在最终答案中
        
        认为无效的情况：
        - "不清楚", "无信息", "不知道", "上下文中没有", "未提供"
        - "提供的文献中未涉及此内容" 【新增】- 明确的无信息回答
        - "仅需要网搜", "应该聊天啊"
        - "cannot find", "no information", "unknown"
        """
        if not answer or len(answer.strip()) == 0:
            return False
        
        # 【修改】"提供的文献中未涉及此内容" 现在被视为无效答案（应该舍弃该source）
        if answer.strip() == "提供的文献中未涉及此内容":
            return False  # 改为False，这样会被过滤掉
        
        # 列表：不有效的关键词
        invalid_keywords = [
            "不清楚", "无信息", "不知道", 
            "上下文中没有", "未提供",
            "仅需要网搜", "应该聊天",
            "我无法回答", "没有提供",
            "cannot find", "no information", "unknown",
            "i don't know", "no data"
        ]
        
        answer_lower = answer.lower()
        # 判断是否为纯谢句（只是提示）
        for keyword in invalid_keywords:
            if keyword in answer_lower:
                return False
        
        # 如果答案太短（<20字）且是单句，也认为无效
        sentences = [s for s in answer.split('。') if s.strip()]
        if len(sentences) <= 1 and len(answer.strip()) < 20:
            return False
        
        return True
    
    def _is_bibliography(self, content: str) -> bool:
        """判断内容是否为参考文献列表（Bibliography）
        
        检查特征：
        1. 包含大量的 [数字] 格式
        2. 包含 Author, Title, Journal 等格式
        3. 行数较多但单行较短
        """
        import re
        
        # 统计 [数字] 的出现次数
        citation_matches = re.findall(r'\[\d+\]', content)
        
        # 如果有超过 3 个的 [数字] 格式，说明是参考文献列表
        if len(citation_matches) >= 3:
            return True
        
        # 检查是否包含常见的参考文献关键词
        bibliography_keywords = ['journal', 'author', 'pp.', '。', 'vol', 'pp']
        keyword_count = sum(1 for kw in bibliography_keywords if kw.lower() in content.lower())
        if keyword_count >= 3:
            return True
        
        return False
    
    def _build_citation_instruction(self, count: int) -> str:
        from .answer_grounding import SYSTEM_PROMPT
        return SYSTEM_PROMPT
    
    def _build_final_prompt(self, sources_hint: str, citation_mapping: str,
                           fused_context: str, question: str, count: int) -> str:
        if any(w in question.lower() for w in ("谱系", "借鉴", "extends", "improves", "adapts", "replaces")):
            sources_hint += ("\n本题涉及方法谱系：正式记录的关系仅按标注[lineage]的审计条目作答。"
                             "原文中其他改写或比较必须另列为尚未进入该审计表，不升级为已确认借鉴或演化。"
                             "关系的主语和作者严格按原句辨认，不能把‘本文改进’归给相邻引用的前人。")
        return (f"【用户问题】\n{question}\n\n【证据正文】\n{fused_context}"
                f"\n\n【完整引用目录】\n{citation_mapping}\n\n【回答规则】\n{sources_hint}")
    
    def _post_process_answer_new_format(self, answer: str, all_sources: List[Dict], 
                                         doc_sources: List[Dict]) -> str:
        """后处理新答案格式：综述+逐source回答+文献来源
        
        【新流程】：
        1. 从答案中提取所有[Ref-n]标记
        2. 针对每个[Ref-n]，提取对应的source信息
        3. 构建文献来源部分（仅包含Vector类型）
        4. 拼接最终答案
        """
        import re
        
        if not answer:
            return answer

        from .answer_grounding import normalize_citations
        answer = normalize_citations(answer)
        
        # 第一步：根据[Ref-n]提取引用，按出现顺序排序
        ref_pattern = r'\[Ref-(\d+)\]'
        cited_ids_raw = re.findall(ref_pattern, answer)
        cited_ids_unique = []
        seen = set()
        for x in cited_ids_raw:
            val = int(x)
            if val not in seen:
                cited_ids_unique.append(val)
                seen.add(val)
        
        # 第二步：提取Vector类型的source信息构建文献来源
        cited_sources = []
        for ref_id in cited_ids_unique:
            if ref_id in self.ref_id_map:
                source_info = self.ref_id_map[ref_id]
                # 【关键】仅保留vector类型的源
                if source_info.get('type') in ('vector', 'lineage', 'pdf_supplement'):
                    title = source_info.get('title', f'Reference {ref_id}')
                    cited_sources.append((ref_id, title))
        
        # 第三步：构建文献来源部分
        sources_section = ""
        if cited_sources:
            sources_section = "\n\n---\n\n【文献来源】\n"
            for ref_id, title in cited_sources:
                sources_section += f"[Ref-{ref_id}]：{title}\n"
        
        # 第四步：拼接最终答案
        return answer.strip() + sources_section
    
    def _post_process_answer(self, answer: str, all_sources: List[Dict], 
                            doc_sources: List[Dict]) -> str:
        """【第五步】后端还原与拼接（后处理阶段）- 仅显示 Milvus 文献
        
        关键改进：
        1. 正则提取答案中的所有 [x] 中的数字（文内引用）
        2. 清理非法引用（web、molecule 和 graph 类型的 [x] 标记）
        3. 过滤掉 web、molecule 和 graph 类型的引用（仅保留 vector - Milvus 文献）
        4. 去重并排序
        5. 使用全局 ref_id_map 查表（而不是过滤后的子集）
        6. 生成【文内引用】列表（仅包含 vector - Milvus 文献）
        7. 生成【延伸阅读】列表（凑齐15+条目，仅 Milvus 文献）
        8. 拼接正文 + 双重引用列表
        """
        import re
        
        # 【第一步】清理非法引用：移除所有指向 web/molecule/graph 类型的 [x] 标记
        # 正则匹配所有 [数字]
        citation_pattern = r'\[(\d+)\]'
        all_citations = re.findall(citation_pattern, answer)
        all_citation_ids = set([int(x) for x in all_citations])
        
        # 识别非法引用（指向 web/molecule/graph 的 [x]）
        illegal_ids = set()
        for ref_id in all_citation_ids:
            if ref_id in self.ref_id_map:
                source_type = self.ref_id_map[ref_id].get('type', 'unknown')
                if source_type in ['web', 'molecule', 'graph']:
                    illegal_ids.add(ref_id)
        
        # 从答案中移除非法引用
        cleaned_answer = answer
        for illegal_id in illegal_ids:
            cleaned_answer = re.sub(rf'\[{illegal_id}\]', '', cleaned_answer)
        
        # 清理多余空格和空行
        cleaned_answer = re.sub(r'\s+', ' ', cleaned_answer)  # 多个空格合并为一个
        cleaned_answer = re.sub(r'\n\s*\n\s*\n', '\n\n', cleaned_answer)  # 多个换行合并
        
        answer = cleaned_answer
        
        # 【第二步】正则提取答案中的所有 [x] 中的数字（文内引用，已过滤非法引用）
        citation_pattern = r'\[(\d+)\]'
        citations_found = re.findall(citation_pattern, answer)
        cited_ids_raw = sorted(set([int(x) for x in citations_found]))
        
        # 【新增】第二步续：过滤掉 web、molecule 和 graph 类型，只保留 vector（Milvus 文献）
        cited_ids = []
        for ref_id in cited_ids_raw:
            if ref_id in self.ref_id_map:
                source_type = self.ref_id_map[ref_id].get('type', 'unknown')
                # 仅保留 vector 类型（Milvus 文献）
                if source_type == 'vector':
                    cited_ids.append(ref_id)
        
        # 【调试】打印引用提取结果
        # logger.debug(f"[_post_process_answer] 原始引用: {cited_ids_raw}")
        # logger.debug(f"[_post_process_answer] 过滤后引用（仅vector）: {cited_ids}")
        
        # 【新增】如果答案中引用不足（少于总块数的1/2），自动为关键段落添加引用
        # 这确保了充分利用检索到的所有块
        vector_count = sum(1 for s in doc_sources if s.get('type') == 'vector')
        if len(cited_ids) < max(2, vector_count // 2):
            # 获取所有可用的向量块引用
            all_vector_refs = [ref_id for ref_id in self.ref_id_map.keys()
                              if self.ref_id_map[ref_id].get('type') == 'vector']
            
            if all_vector_refs:
                # 在答案末尾添加额外的引用
                # 选择前几个未被引用的块作为支撑
                uncited_vector_refs = [r for r in all_vector_refs if r not in cited_ids]
                if uncited_vector_refs:
                    # 添加到已引用列表（用于生成引用部分）
                    cited_ids.extend(uncited_vector_refs[:max(1, vector_count // 4)])
                    cited_ids = sorted(set(cited_ids))
        
        # 第三步：从账本中构建文内引用列表（仅包含 vector - Milvus 文献）
        cited_sources = []
        for ref_id in cited_ids:
            if ref_id in self.ref_id_map:
                title = self.ref_id_map[ref_id].get('title', f'Reference {ref_id}')
                cited_sources.append((ref_id, title))
        all_available_ids = set(self.ref_id_map.keys())
        # 过滤掉 web、molecule 和 graph 类型，只保留 vector
        available_vector_only = set()
        for ref_id in all_available_ids:
            if ref_id in self.ref_id_map:
                source_type = self.ref_id_map[ref_id].get('type', 'unknown')
                if source_type == 'vector':
                    available_vector_only.add(ref_id)
        
        uncited_ids = available_vector_only - set(cited_ids)
        
        # 【修改】仅显示引用的文献，不设延伸阅读
        # 第五步：生成文献来源列表（仅包含引用的文献）
        sources_section = "\n\n【文献来源】\n"
        
        # 辅助函数：按标题合并文献引用编号
        def merge_sources_by_title(source_list):
            """将多个引用合并为按标题分组的格式
            
            输入: [(1, 'Title A'), (2, 'Title B'), (3, 'Title A')]
            输出: {('Title A', set([1, 3])), ('Title B', set([2]))}
            """
            title_to_refs = {}  # title -> set of ref_ids
            for ref_id, title in source_list:
                if title not in title_to_refs:
                    title_to_refs[title] = []
                title_to_refs[title].append(ref_id)
            # 返回列表格式：[(title, [ref_ids]), ...]
            return [(title, ref_ids) for title, ref_ids in title_to_refs.items()]
        
        # 第一层：文内引用（仅 vector - Milvus 文献）
        if cited_sources:
            sources_section += "【文内引用】\n"
            merged_cited = merge_sources_by_title(cited_sources)
            for title, ref_ids in merged_cited:
                # 按顺序排列 ref_ids
                ref_str = "".join(f"[Ref-{rid}]" for rid in sorted(ref_ids))
                sources_section += f"{ref_str}：{title}\n\n"
        
        # 【修改】不设延伸阅读，仅显示答案中引用的文献
        
        # 第六步：拼接正文 + 双重引用列表
        final_answer = answer + sources_section
        # 【注意】web 和 molecule 来源 NOT 在【文内引用】中显示，仅在【其他信息来源】中显示
        other_sources = [s for s in doc_sources if s.get('type') in ['web', 'molecule']] if doc_sources else []
        if other_sources:
            other_section = "\n【其他信息来源】\n"
            
            molecule_sources = []
            web_sources = []
            
            for source in other_sources:
                source_type = source.get('type', '')
                if source_type == 'molecule':
                    mol_content = source.get('content', '')
                    molecule_sources.append(mol_content)
                elif source_type == 'web':
                    web_title = source.get('title', '秘塔搜索结果')
                    web_sources.append({'title': web_title})
            
            # 分子查询工具
            if molecule_sources:
                other_section += "  🧪 分子查询：\n"
                for mol_name in molecule_sources:
                    other_section += f"    - {mol_name}\n"
            
            # 网络掐索结果
            if web_sources:
                other_section += "  🔍 网页搜索\n\n"
            
            final_answer += other_section
        
        return final_answer
    
    def _extract_sources_section(self, full_answer: str) -> str:
        """从完整答案中提取文献来源部分"""
        import re
        
        # 优化正则：同时兼容带分隔符和不带分隔符的情况，且匹配【文献来源】或【其他信息来源】
        # 优先查找【文献来源】
        match = re.search(r'(---\s*)?【文献来源】.*', full_answer, re.DOTALL)
        if match:
            return match.group(0)
        
        # 兜底查找【其他信息来源】
        match = re.search(r'【其他信息来源】.*', full_answer, re.DOTALL)
        if match:
            return match.group(0)
        
        return ""
    
    def _generate_sources_chunk(self) -> str:
        """为流式输出生成独立的丢文献流次歜客（优化点四）
        
        在大模型生成结束后（[丢文献DONE]信号）立即输出
        带有丢文献列表的网络询啊。
        
        输出示例（流式输出丢文献）：
        ---
        【文献来源】
        [1] Simply designed sulfonated...
        [2] Catalyzing anode...
        
        【延伸阅读】(相关高质量文献)
        [20] Mitigation of hydrogen...
        ...
        ---
        """
        # 第一层：文内引用
        sources_chunk = ""
        cited_refs = [(ref_id, title) for ref_id, title in 
                      [(k, v.get('title')) for k, v in self.ref_id_map.items()] 
                      if ref_id and title]  # 殞方小樣
        
        # 实际上，只有在 _post_process_answer() 里才能痣定自实文内引用
        # 这个方法是为了延治输出提供一个更炎加粗的方案
        return ""
    
    def _create_reference_footer(self, cited_ids: List[int]) -> str:
        """制作参考文献页脚（可独立使用用于流式输出）
        
        输入：引用ID列表 [1, 3, 5, ...]
        输出：Markdown格式的参考文献寵
        """
        # 第一组：文内引用
        footer = ""
        cited_sources = []
        for ref_id in cited_ids:
            if ref_id in self.ref_id_map:
                title = self.ref_id_map[ref_id].get('title')
                cited_sources.append((ref_id, title))
        
        if cited_sources:
            footer += "【文内引用】\n"
            for ref_id, title in cited_sources:
                footer += f"[{ref_id}] {title}\n"
        
        # 第二组：延伸阅读
        all_ids = set(self.ref_id_map.keys())
        uncited_ids = sorted(all_ids - set(cited_ids))
        
        if uncited_ids and len(cited_sources) < 15:
            remaining = min(len(uncited_ids), 15 - len(cited_sources))
            uncited_sources = [(ref_id, self.ref_id_map[ref_id].get('title')) 
                              for ref_id in uncited_ids[:remaining]]
            
            if uncited_sources:
                footer += f"\n【延伸阅读】({len(uncited_sources)} 篇高质量文献)\n"
                for ref_id, title in uncited_sources:
                    footer += f"[{ref_id}] {title}\n"
        
        return footer
    
    def _append_sources_section_only(self, answer: str, milvus_sources: List[Dict], doc_sources: List[Dict]) -> str:
        """上标处理：同一段落合并上标 + 文献来源列表
        
        实现流程（上标合并策略老：后处理法）：
        1. 构建上标-文献映射表
        2. 按段落分组
        3. 每个段落中：提取所有上标 -> 去重 + 排序 -> 炭换到段尾
        4. 汇总全体上标 -> 生成文献来源列表
        """
        if not answer:
            return answer
        
        # 第一步：构建上标-文献映射表（同一文献去重）
        source_mapping = {}  # [1] -> 文献A
        original_to_new_mapping = {}  # 原来的上标号 -> 新的上标号是否是同一文献）
        seen_sources = {}  # 文献标题 -> 上标号
        label_counter = 1
        
        for idx, source in enumerate(milvus_sources, 1):
            source_title = source.get('source', '')
            clean_source = source_title
            
            # 检查该文献是否已经出现过
            if clean_source not in seen_sources:
                # 第一次出现，分配新的上标号
                seen_sources[clean_source] = label_counter
                source_mapping[label_counter] = clean_source
                label_counter += 1
            
            # 记录原始上标号 -> 新上标号的映射
            original_to_new_mapping[idx] = seen_sources[clean_source]
        
        # 第二步：按段落分组
        import re
        paragraphs = answer.split('\n')  # 按段落分组
        processed_paragraphs = []
        all_found_citations = set()  # 跟踪上文中所有出现的上标
        
        for para in paragraphs:
            if not para.strip():
                # 空段落保持
                processed_paragraphs.append(para)
                continue
            
            # 第三步：提取该段落中的上标
            para_citations = re.findall(r'\[(\d+)\]', para)
            para_citations = [int(x) for x in para_citations]
            
            if para_citations:
                # 该段落有上标
                # 改配上标：将每个原始上标映射成新上标（在映射表中）
                remapped_citations = [original_to_new_mapping.get(cite, cite) for cite in para_citations]
                all_found_citations.update(remapped_citations)  # 上文中所有上标
                
                # 第四步：去重 + 排序
                unique_para_citations = sorted(set(remapped_citations))
                
                # 第五步：模式替换：删除段落中间的旧上标，将去重后的新上标你接至段尾
                # 步骤2a: 使用正则削除中间的上标
                cleaned_para = re.sub(r'\[\d+\]', '', para)
                # 步骤2b: 附加去重后的新上标
                new_citations_str = ''.join(f'[{cite}]' for cite in unique_para_citations)
                processed_para = cleaned_para.rstrip() + new_citations_str
                processed_paragraphs.append(processed_para)
            else:
                # 该段落没有上标，保持不变
                processed_paragraphs.append(para)
        
        # 重新组组处理后的段落
        processed_answer = '\n'.join(processed_paragraphs)
        
        # 第六步：汇总上文中所有上标（按出现顺序去重）
        if all_found_citations:
            unique_all_citations = sorted(all_found_citations)
            
            # 第七步：生成文献来源列表
            sources_section = "\n\n【文献来源】\n"
            for cite_num in unique_all_citations:
                if cite_num in source_mapping:
                    sources_section += f"[{cite_num}]、{source_mapping[cite_num]}\n"
        else:
            sources_section = ""
        
        final_answer = processed_answer + sources_section.rstrip() if sources_section else processed_answer
        
        # 第八步：添加其他来源【不标记】
        other_sources = [s for s in doc_sources if s.get('type') != 'vector'] if doc_sources else []
        if other_sources:
            sources_section = "\n\n其他信息来源：\n"
            
            # 按类型分类
            molecule_sources = []
            web_sources = []
            
            for source in other_sources:
                source_type = source.get('type', '')
                if source_type == 'molecule':
                    mol_content = source.get('content', '')  # 格式: "分子名 (分子式: ...)"
                    molecule_sources.append(mol_content)
                elif source_type == 'web':
                    web_sources.append(source.get('source', ''))
            
            # 分子查询：列出所有分子名称
            if molecule_sources:
                for mol_name in molecule_sources:
                    sources_section += f"  - {mol_name}分子查询\n"
            
            # web搜索：统一顫为w"web搜索"
            if web_sources:
                # 去掉重复的web搜索条目，只显示一次
                sources_section += "  - web搜索\n"
            
            final_answer = final_answer + sources_section.rstrip()
        
        return final_answer
    
    def _add_missing_citations(self, answer: str, milvus_sources: List[Dict], doc_sources: List[Dict]) -> str:
        """如果答案中没有上标，为最后一句添加上标
        
        改句事：这表示我们的prompt超级不好，需要添加基本上标
        """
        if not milvus_sources:
            return answer
        
        # 窓有情况：添加最后一句的上标
        sources_section = "\n\n【文献来源】\n"
        for idx, source in enumerate(milvus_sources, 1):
            source_title = source.get('source', '')
            clean_source = source_title
            sources_section += f"[{idx}]、{clean_source}\n"
        
        answer = answer + sources_section.rstrip()
        
        # 添加其他来源【不标记】
        other_sources = [s for s in doc_sources if s.get('type') != 'vector'] if doc_sources else []
        if other_sources:
            sources_section = "\n\n其他信息来源：\n"
            
            # 按类型分类
            molecule_sources = []
            web_sources = []
            
            for source in other_sources:
                source_type = source.get('type', '')
                if source_type == 'molecule':
                    mol_content = source.get('content', '')  # 格式: "分子名 (分子式: ...)"
                    molecule_sources.append(mol_content)
                elif source_type == 'web':
                    web_sources.append(source.get('source', ''))
            
            # 分子查询：列出所有分子名称
            if molecule_sources:
                for mol_name in molecule_sources:
                    sources_section += f"  - {mol_name}分子查询\n"
            
            # web搜索：统一顫为w"web搜索"
            if web_sources:
                # 去掉重复的web搜索条目，只显示一次
                sources_section += "  - web搜索\n"
            
            answer = answer + sources_section.rstrip()
        
        return answer
    
    def _append_sources_section_with_labels(self, answer: str, doc_sources: List[Dict]) -> str:
        """在答案中标记milvus来源的上标，最多10个
        
        规则：
        - 仅标记milvus召回文本引用的信息
        - 最多标记10个
        - 按doc_sources顺序绑定上标，不需要匹配答案内容
        """
        if not doc_sources:
            return answer
        
        # 筛选milvus来源
        milvus_sources = [s for s in doc_sources if s.get('type') == 'vector']
        if not milvus_sources:
            return self._append_sources_section(answer, doc_sources)
        
        # 最多标记10个文献，按顺序绑定上标（不需要匹配答案内容）
        milvus_sources = milvus_sources[:10]
        
        # 直接返回答案+文献来源
        return self._append_sources_section_with_labels_direct(answer, milvus_sources, doc_sources)
    
    def _append_sources_section_with_labels_direct(self, answer: str, milvus_sources: List[Dict], doc_sources: List[Dict]) -> str:
        """直接添加上标和文献来源
        
        关键改进点：
        1. 去重了文献（不同的source仅计一次）
        2. 在答案最后添加所有上标 [1][2][3]...
        3. 不同的符不重复计数
        """
        if not milvus_sources:
            return self._append_sources_section(answer, doc_sources)
        
        # 第一步：去重文献并批号上标序号
        unique_sources = {}  # clean_source_title -> label_num
        unique_sources_list = []  # {source, label}
        current_label = 1
        
        for source in milvus_sources:
            source_title = source.get('source', '')
            if source_title:
                clean_source = source_title
                
                # 如果是第一次重遇，则批号一个新的上标编码
                if clean_source not in unique_sources:
                    unique_sources[clean_source] = current_label
                    unique_sources_list.append({'source': clean_source, 'label': current_label})
                    current_label += 1
        
        if not unique_sources:
            return self._append_sources_section(answer, doc_sources)
        
        # 第二步：在答案最后添加所有上标
        all_labels = "".join(f"[{label}]" for label in sorted(unique_sources.values()))
        answer_with_labels = answer + all_labels
        
        # 第三步：构建文献来源部分
        sources_section = "\n\n【文献来源】\n"
        for item in unique_sources_list:
            sources_section += f"[{item['label']}]、{item['source']}\n"
        
        # 添加其他来源【不标记】
        other_sources = [s for s in doc_sources if s.get('type') != 'vector']
        if other_sources:
            sources_section += "\n其他信息来源：\n"
            
            # 按类型分类
            molecule_sources = []
            web_sources = []
            
            for source in other_sources:
                source_type = source.get('type', '')
                if source_type == 'molecule':
                    mol_content = source.get('content', '')  # 格式: "分子名 (分子式: ...)"
                    molecule_sources.append(mol_content)
                elif source_type == 'web':
                    web_sources.append(source.get('source', ''))
            
            # 分子查询：列出所有分子名称
            if molecule_sources:
                for mol_name in molecule_sources:
                    sources_section += f"  - {mol_name}分子查询\n"
            
            # web搜索：统一顫为w"web搜索"
            if web_sources:
                # 去掉重复的web搜索条目，只显示一次
                sources_section += "  - web搜索\n"
        
        return answer_with_labels + sources_section.rstrip()
    
    def _append_sources_section(self, answer: str, doc_sources: List[Dict]) -> str:
        """没有上标的文献来源部分"""
        if not doc_sources:
            return answer
        
        # 按来源类型组织
        sources_by_type = {}
        for source in doc_sources:
            source_type = source.get("type", "vector")
            title = source.get("source", "未知来源")
            if title:
                if title not in sources_by_type:
                    sources_by_type[title] = source_type
        
        if not sources_by_type:
            return answer
        
        # 构建文献来源部分
        sources_section = "\n\n【文献来源】\n"
        
        # 按优先级排序
        priority_1_sources = []  # vector + graph
        priority_2_sources = []  # molecule
        priority_3_sources = []  # web
        
        for title, source_type in sources_by_type.items():
            if source_type in ["vector", "graph"]:
                priority_1_sources.append(title)
            elif source_type == "molecule":
                priority_2_sources.append(title)
            elif source_type == "web":
                priority_3_sources.append(title)
        
        # 优先级1（文献、知识图谱）
        if priority_1_sources:
            # 限制最多100个文献来源
            priority_1_sources_limited = sorted(priority_1_sources)[:100]
            sources_section += f"📈 主要信息源（优先级1）（共 {len(priority_1_sources_limited)} 个）\n"
            for title in priority_1_sources_limited:
                clean_title = title.replace('milvus_', '', 1) if title.startswith('milvus_') else title
                sources_section += f"  ✓ {clean_title}\n"
        
        # 优先级2（分子查询）
        if priority_2_sources:
            sources_section += "\n🦠 辅加信息源（优先级2）\n"
            for title in sorted(priority_2_sources):
                sources_section += f"  ✓ {title}\n"
        
        # 优先级3（网络搜索）
        if priority_3_sources:
            sources_section += "\n🔍 外部参考（优先级3）\n"
            for title in sorted(priority_3_sources):
                sources_section += f"  ✓ {title}\n"
        
        return answer + sources_section.rstrip()
    
    def _build_prompt_context_for_part(self, doc_sources: List[Dict]) -> str:
        """为单个部分构建上下文映射 - 与_build_prompt_context类似
        
        专为并行模式下的单个部分使用
        """
        context_parts = []
        
        for source in doc_sources:
            ref_id = source.get('ref_id')
            if not ref_id:
                continue
            
            content = source.get('content', '').strip()
            if not content:
                continue
            
            title = source.get('source', '').strip() or 'Unknown'
            source_type = source.get('type', 'unknown')
            
            is_bibliography = self._is_bibliography(content)
            bibliography_flag = "[参考文献列表、已清洗] " if is_bibliography else ""
            
            type_prefix = f"[{source_type.upper()}]"
            
            context_parts.append(
                f"[Ref-{ref_id}]{type_prefix} {bibliography_flag}{content}\n(来源: {title})"
            )
        
        return "\n".join(context_parts)
    
    def _post_process_merged_answer(self, merged_answer: str, all_doc_sources: List[Dict]) -> str:
        """后处理合并后的答案 - 整理文献来源
        
        【新增】此方法专为并行模式的合并答案使用
        """
        # 为各部分重新整体的ref_id
        self.ref_id_map = self._build_ref_id_map(all_doc_sources)
        
        # 使用原始的后处理逻辑
        return self._post_process_answer(merged_answer, all_doc_sources, all_doc_sources)


class MultiAgentPipeline:
    """多智能体管道 - 协调所有Agent"""
    
    def __init__(self, llm, graph_rag=None, traditional_rag=None, molecule_agent=None, parsing_llm=None, internlm=None, evidence_store=None):
        self.llm = llm
        self.molecule_agent = molecule_agent
        self.internlm = internlm  # 【新增】最终回答使用的模型
        # 【修改】如果提供了专门的解析LLM则使用，否则共用主LLM
        self.parsing_llm = parsing_llm or llm
        self.parsing_agent = QuestionParsingAgent(self.parsing_llm)
        self.retrieval_agent = MultiSourceRetrievalAgent(graph_rag, traditional_rag, llm, molecule_agent=molecule_agent)
        self.fusion_agent = InformationFusionAgent(llm)
        self.answer_agent = AnswerGenerationAgent(llm if internlm is None else internlm, internlm=internlm)

        # 【新增】初始化第一性原理 Agent
        from .part5_glm import FirstPrinciplesAgent
        self.first_principles_agent = FirstPrinciplesAgent(internlm or llm)

        # 【证据图闭环 M2】可选证据图存储: 传入时启用 Stage 5 写回, 不传时行为与 v3.0.0 完全一致
        self.evidence_store = evidence_store

        logger.info(f"✓ 多智能体管道初始化完成 (Parsing LLM: {self.parsing_llm.model})")

    def _write_evidence_graph(self, state: AgentPipelineState):
        """Stage 5: 从融合上下文与最终答案抽取候选证据并写回证据图(计划 3.7)。

        红线: 产出状态一律 candidate(合并器强制); 任何异常不得打断主管道。
        """
        from .evidence_graph import EvidenceExtractor, merge_round

        state.round_no = max(1, int(state.round_no or 0))
        extractor = EvidenceExtractor(self.llm)
        result = extractor.extract(
            question=state.original_question,
            context=(state.fused_context or "")[:6000],
            answer=(state.final_answer or "")[:6000],
            doc_sources=state.doc_sources or [],
            round_no=state.round_no,
        )
        report = merge_round(self.evidence_store, result, state.round_no)
        self.evidence_store.save()
        state.evidence_graph_snapshot = self.evidence_store.snapshot()
        msg = f"证据写回: {report.summary()}"
        if extractor.last_errors:
            msg += f"; 抽取备注: {extractor.last_errors[:2]}"
        state.log("EvidenceGraph", msg)
        print(f"\n📍 Stage 5: 证据图写回 — {report.summary()}")

    def process(self, question: str, enable_first_principles: bool = False):
        """处理问题 (生成器版本，支持实时进度)"""
        import time
        import threading
        total_start_time = time.time()
        
        state = AgentPipelineState(
            request_id=f"req_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            original_question=question
        )
        
        logger.info("\n" + "=" * 80)
        logger.info(f"🤝 多智能体管道处理: {question[:50]}...")
        logger.info("=" * 80)

        # 任务完成标志
        status = {"pipeline_finished": False, "fp_finished": not enable_first_principles, "error": None}

        # 【任务 1】第一性原理回答生成线程
        def run_fp():
            print("\n🚀 [第一性原理 Agent] 可选探索性推理启动")
            try:
                for chunk in self.first_principles_agent.generate_stream(question):
                    if isinstance(chunk, dict):
                        if chunk.get("type") == "reasoning":
                            state.fp_reasoning += chunk.get("content", "")
                        else:
                            state.first_principles_answer += chunk.get("content", "")
                        # 同步在控制台打印内容部分
                        print(chunk.get("content", ""), end='', flush=True)
                    else:
                        # 兼容旧版本或直接返回字符串的情况
                        state.first_principles_answer += str(chunk)
                        print(chunk, end='', flush=True)
            except Exception as e:
                error_msg = f"\n❌ 第一性原理生成失败: {e}"
                state.first_principles_answer += error_msg
                print(error_msg)
            finally:
                print(f"\n✅ [第一性原理 Agent] 生成结束")
                status["fp_finished"] = True

        # 【任务 2】主管道流水线线程 (包含 Stage 1-4)
        def run_main_pipeline():
            try:
                # 【新增】显式向量化提示 (响应用户并行需求)
                state.log("System", "⏳ 正在进行问题向量化处理...")
                
                # ========== Stage 1: 问题解析 ==========
                print("\n📍 Stage 1: 问题解析")
                self.parsing_agent.parse(state)
                state.stage_1_complete = True
                
                # ========== Stage 2: 多源检索 ==========
                print("\n📍 Stage 2: 多源检索")
                self.retrieval_agent.retrieve(state)
                state.stage_2_complete = True
                
                # ========== Stage 3: 信息融合 ==========
                print("\n📍 Stage 3: 信息融合")
                self.fusion_agent.fuse(state)
                state.stage_3_complete = True
                
                # ========== Stage 4: 答案生成 ==========
                print("\n📍 Stage 4: 答案生成")
                self.answer_agent.generate(state)
                state.stage_4_complete = True

                # ========== Stage 5: 证据图写回(可选, 证据闭环 M2) ==========
                # 仅当构造时传入 evidence_store 才启用; 写回失败绝不影响已生成的答案。
                if self.evidence_store is not None:
                    try:
                        self._write_evidence_graph(state)
                    except Exception as eg_err:  # 双保险: _write_evidence_graph 内部已兜底
                        state.log("EvidenceGraph", f"写回外层兜底: {eg_err}")
                    state.stage_5_complete = True

            except Exception as e:
                status["error"] = str(e)
                logger.error(f"Pipeline 执行异常: {e}")
            finally:
                status["pipeline_finished"] = True

        # 启动并行线程
        fp_thread = threading.Thread(target=run_fp, daemon=True)
        pipeline_thread = threading.Thread(target=run_main_pipeline, daemon=True)
        
        if enable_first_principles:
            fp_thread.start()
        pipeline_thread.start()
        
        # 【主循环】实时产出状态，驱动前端流式显示
        last_yield_time = 0
        while not (status["pipeline_finished"] and status["fp_finished"]):
            current_time = time.time()
            # 约 20fps 的刷新频率
            if current_time - last_yield_time > 0.05:
                yield state
                last_yield_time = current_time
            time.sleep(0.01)

        # 计算总耗时并产出最终状态
        state.execution_time = time.time() - total_start_time
        if status["error"]:
            state.log("System", f"⚠️ Pipeline 异常结束: {status['error']}")
        
        yield state  # 【产出】最终完成状态


class SimpleMultiAgentSystem:
    """简化的多智能体系统 - 核心4个Agent"""
    
    def __init__(self, llm, graph_rag=None, traditional_rag=None, molecule_agent=None, parsing_llm=None, internlm=None):
        """初始化多智能体系统"""
        self.llm = llm
        self.molecule_agent = molecule_agent
        self.pipeline = MultiAgentPipeline(llm, graph_rag, traditional_rag, molecule_agent=molecule_agent, parsing_llm=parsing_llm, internlm=internlm)
        logger.info("✓ 简化的多智能体系统初始化完成")
    
    def process(self, question: str, enable_first_principles: bool = False) -> AgentPipelineState:
        """处理问题，直接返回结果"""
        logger.info(f"🤝 处理问题: {question[:50]}...")
        state = self.pipeline.process(question, enable_first_principles=enable_first_principles)
        return state


# 向后兼容性别名
EnhancedParetoNavigator = SimpleMultiAgentSystem

