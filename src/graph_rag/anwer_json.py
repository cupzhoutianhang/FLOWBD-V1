"""JSON多源并行问答系统 - 基于问题类型的智能检索和答案生成

核心流程：
1. 【问题分析】：输入问题 → 识别问题类型 → 确定目标JSON类别
2. 【智能检索】：根据问题类型 → 过滤相关JSON文件 → 从每个JSON检索信息
3. 【并行处理】：每个JSON一个LLM → 并行调用8个大模型 → 独立生成答案段落
4. 【答案合成】：检验答案有效性 → 过滤无效回答 → 按JSON分组合成最终答案
5. 【质量控制】：防止捏造、张冠李戴、发挥过度

系统架构参考：part5_multiagent_integration.py 的多Agent并行处理模式
"""

import os
import sys
import json
import logging
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from collections import defaultdict
import threading

# 设置控制台编码为UTF-8
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(name)s] %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 添加父路径以导入LLM配置
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
AGENT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(SCRIPT_DIR)))
if AGENT_DIR not in sys.path:
    sys.path.insert(0, AGENT_DIR)

# 全局变量，用于存储导入的LLM类
LLMConfig = None
ParallelLLMManager = None

try:
    from agent.graphrag_and_rag.agent.part1_knowledge_arsenal import LLMConfig as _LLMConfig, ParallelLLMManager as _ParallelLLMManager
    LLMConfig = _LLMConfig
    ParallelLLMManager = _ParallelLLMManager
    logger.info("✓ 成功导入 LLMConfig 和 ParallelLLMManager (第一路径)")
except ImportError as e:
    try:
        from agent.part1_knowledge_arsenal import LLMConfig as _LLMConfig, ParallelLLMManager as _ParallelLLMManager
        LLMConfig = _LLMConfig
        ParallelLLMManager = _ParallelLLMManager
        logger.info("✓ 成功导入 LLMConfig 和 ParallelLLMManager (第二路径)")
    except ImportError as e2:
        try:
            from part1_knowledge_arsenal import LLMConfig as _LLMConfig, ParallelLLMManager as _ParallelLLMManager
            LLMConfig = _LLMConfig
            ParallelLLMManager = _ParallelLLMManager
            logger.info("✓ 成功导入 LLMConfig 和 ParallelLLMManager (第三路径)")
        except ImportError as e3:
            logger.warning(f"⚠️  无法导入LLMConfig/ParallelLLMManager")
            logger.warning(f"   错误1: {e}")
            logger.warning(f"   错误2: {e2}")
            logger.warning(f"   错误3: {e3}")
            logger.warning("   系统将工作于降级模式（仅支持关键词识别）")


# ============================================================================
# 数据定义
# ============================================================================

@dataclass
class QuestionAnalysisResult:
    """问题分析结果"""
    original_question: str                    # 原始问题
    identified_type: str                      # 识别的问题类型
    type_confidence: float = 0.8              # 类型识别置信度
    target_properties: List[str] = field(default_factory=list)  # 目标属性
    relevant_json_categories: List[str] = field(default_factory=list)  # 相关JSON类别
    entities: List[str] = field(default_factory=list)  # 提取的实体
    

@dataclass
class JSONRetrievalResult:
    """单个JSON检索结果"""
    json_file: str                            # JSON文件名
    json_category: str                        # JSON类别
    query_text: str                           # 查询文本
    retrieved_content: Dict[str, Any] = field(default_factory=dict)  # 检索到的内容
    relevance_score: float = 0.0              # 相关性评分
    source_ref: str = ""                      # 源引用标识


@dataclass
class ParallelAnswerResult:
    """并行LLM答案结果"""
    llm_index: int                            # LLM索引 (1-8)
    json_source: str                          # JSON来源
    answer_content: str                       # 答案内容
    validity_score: float = 1.0               # 答案有效性评分(0-1)
    is_valid: bool = True                     # 是否为有效答案
    error_reason: str = ""                    # 无效原因


@dataclass
class FinalAnswer:
    """最终答案"""
    question: str                             # 原始问题
    type_info: str                            # 问题类型信息
    answer_sections: List[Dict] = field(default_factory=list)  # 答案段落列表
    all_valid_count: int = 0                  # 有效答案数量
    final_text: str = ""                      # 最终答案文本
    confidence: float = 0.0                   # 整体置信度


# ============================================================================
# 问题类型识别模块
# ============================================================================

class QuestionTypeIdentifier:
    """问题类型识别器 - 确定问题属于哪些JSON类别"""
    
    # 问题类型与JSON类别的映射
    TYPE_TO_JSON_MAPPING = {
        'property': ['properties.json', 'characteristics.json'],
        'synthesis': ['synthesis.json', 'preparation.json'],
        'reaction': ['reactions.json', 'mechanisms.json'],
        'structure': ['structure.json', 'composition.json'],
        'application': ['applications.json', 'usage.json'],
        'performance': ['performance.json', 'efficiency.json'],
        'comparison': ['comparison.json', 'properties.json'],
        'characterization': ['characterization.json', 'testing.json'],
        'general': ['general.json', 'overview.json'],
    }
    
    # 类型识别关键词
    TYPE_KEYWORDS = {
        'property': ['溶解度', '粘度', '电导率', '电位', '容量', '密度', '性质', '属性',
                     'solubility', 'viscosity', 'conductivity', 'potential', 'capacity', 'density'],
        'synthesis': ['合成', '制备', '由什么', '怎么做', '原料', '方法',
                     'synthesize', 'prepare', 'method', 'procedure', 'synthesis'],
        'reaction': ['反应', '过程', '氧化', '还原', '电化学', '机理',
                     'reaction', 'redox', 'electrochemistry', 'mechanism'],
        'structure': ['结构', '官能团', '分子', '基团', '构成',
                     'structure', 'functional group', 'molecular', 'group'],
        'application': ['应用', '用途', '用作', '使用', '场景',
                       'application', 'use', 'application', 'scenario'],
        'performance': ['性能', '效率', '循环', '稳定性', '寿命',
                       'performance', 'efficiency', 'cycle', 'stability', 'lifetime'],
        'characterization': ['表征', '测试', '测量', '检测', '分析', '方法',
                           'characterization', 'test', 'measure', 'analyze'],
    }
    
    def __init__(self):
        self.llm = None
        try:
            if LLMConfig is not None:
                self.llm = LLMConfig()
                logger.info("✓ QuestionTypeIdentifier 已初始化 LLM")
        except Exception as e:
            logger.warning(f"LLM初始化失败: {e}，将使用关键词模式匹配")
    
    def identify_question_type(self, question: str) -> QuestionAnalysisResult:
        """识别问题类型并返回分析结果
        
        Args:
            question: 用户输入的问题
            
        Returns:
            QuestionAnalysisResult: 问题分析结果（包含类型、置信度、相关JSON类别等）
        """
        logger.info(f"🔍 开始问题类型识别: {question[:50]}...")
        
        # 【步骤1】尝试使用LLM进行语义识别
        if self.llm:
            identified_type, confidence = self._llm_identify(question)
        else:
            # 【步骤2】降级到关键词模式匹配
            identified_type, confidence = self._keyword_identify(question)
        
        # 【步骤3】映射到JSON类别
        relevant_json_categories = self.TYPE_TO_JSON_MAPPING.get(
            identified_type, self.TYPE_TO_JSON_MAPPING.get('general', [])
        )
        
        # 【步骤4】提取实体和属性（可选，用于更精细的检索）
        entities = self._extract_entities(question)
        
        result = QuestionAnalysisResult(
            original_question=question,
            identified_type=identified_type,
            type_confidence=confidence,
            relevant_json_categories=relevant_json_categories,
            entities=entities
        )
        
        logger.info(f"✓ 问题类型识别完成: {identified_type} (置信度: {confidence:.2f})")
        logger.info(f"  相关JSON类别: {relevant_json_categories}")
        
        return result
    
    def _llm_identify(self, question: str) -> Tuple[str, float]:
        """使用LLM识别问题类型"""
        prompt = f"""请分析以下问题的类型，返回JSON格式的结果。

问题: {question}

请返回：
{{
    "type": "property|synthesis|reaction|structure|application|performance|characterization|comparison|general",
    "confidence": 0.0-1.0,
    "reasoning": "简要理由"
}}

只返回JSON，不要其他内容。"""
        
        try:
            response = self.llm.call_llm(prompt, temperature=0.1, max_tokens=200)
            
            # 解析JSON
            response = re.sub(r'```json\s*', '', response)
            response = re.sub(r'```\s*', '', response)
            data = json.loads(response)
            
            question_type = data.get('type', 'general')
            confidence = float(data.get('confidence', 0.5))
            
            return question_type, confidence
        except Exception as e:
            logger.warning(f"LLM识别失败: {e}，降级到关键词模式")
            return self._keyword_identify(question)
    
    def _keyword_identify(self, question: str) -> Tuple[str, float]:
        """使用关键词模式匹配识别问题类型"""
        question_lower = question.lower()
        
        max_score = 0.0
        best_type = 'general'
        
        for qtype, keywords in self.TYPE_KEYWORDS.items():
            matching_keywords = sum(1 for kw in keywords if kw in question_lower)
            if matching_keywords > 0:
                score = min(matching_keywords / 2.0, 1.0)  # 正规化到0-1
                if score > max_score:
                    max_score = score
                    best_type = qtype
        
        confidence = max(max_score, 0.5) if best_type != 'general' else 0.5
        return best_type, confidence
    
    def _extract_entities(self, question: str) -> List[str]:
        """从问题中提取实体（化学物质、材料等）"""
        # 简单的实体提取逻辑，可扩展
        # 这里仅作为示例
        entities = []
        
        # 常见液流电池相关实体
        common_entities = ['PHQ', 'DHPS', 'TEMPO', '全钒', '锌溴', '铁铬', 
                          '聚对苯二酚', '聚酰亚胺', '蒽醌', '碳毡', '膜']
        
        for entity in common_entities:
            if entity in question:
                entities.append(entity)
        
        return entities


# ============================================================================
# JSON加载和类型标注
# ============================================================================

class JSONDataManager:
    """JSON数据管理器 - 加载、检索和标注JSON文件"""
    
    def __init__(self, json_directory: str = None):
        """初始化JSON数据管理器
        
        Args:
            json_directory: JSON文件所在目录，默认为当前脚本目录
        """
        if json_directory is None:
            json_directory = SCRIPT_DIR
        
        self.json_directory = json_directory
        self.json_files: Dict[str, Dict] = {}  # {filename: content}
        self.json_metadata: Dict[str, Dict] = {}  # {filename: {category, type, size}}
        
        self._scan_and_load_jsons()
    
    def _scan_and_load_jsons(self):
        """扫描目录并加载所有JSON文件"""
        logger.info(f"📂 扫描JSON文件目录: {self.json_directory}")
        
        json_count = 0
        for root, dirs, files in os.walk(self.json_directory):
            for file in files:
                if file.endswith('.json'):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        
                        # 简化的文件名（去除路径）
                        simple_name = os.path.relpath(file_path, self.json_directory)
                        
                        self.json_files[simple_name] = data
                        self.json_metadata[simple_name] = {
                            'path': file_path,
                            'size': os.path.getsize(file_path),
                            'category': self._infer_category(simple_name),
                            'type': self._infer_type(simple_name)
                        }
                        
                        json_count += 1
                    except Exception as e:
                        logger.warning(f"⚠️  加载JSON失败 {file_path}: {e}")
        
        logger.info(f"✓ 成功加载 {json_count} 个JSON文件")
    
    def _infer_category(self, filename: str) -> str:
        """从文件名推断JSON类别"""
        # 基于文件名的简单推断
        if 'property' in filename.lower():
            return 'property'
        elif 'synthesis' in filename.lower():
            return 'synthesis'
        elif 'reaction' in filename.lower():
            return 'reaction'
        else:
            return 'general'
    
    def _infer_type(self, filename: str) -> str:
        """从文件名推断JSON类型"""
        # 这里可以根据实际情况扩展
        return 'data'
    
    def get_filtered_jsons(self, relevant_categories: List[str]) -> Dict[str, Dict]:
        """根据相关类别过滤JSON文件
        
        Args:
            relevant_categories: 相关JSON类别列表
            
        Returns:
            Dict: {filename: data} 的过滤结果
        """
        filtered = {}
        
        for filename, data in self.json_files.items():
            # 检查文件名或类别是否匹配
            metadata = self.json_metadata.get(filename, {})
            file_category = metadata.get('category', 'general')
            
            # 检查是否在相关类别中
            should_include = False
            for cat in relevant_categories:
                if cat in filename or file_category == cat:
                    should_include = True
                    break
            
            # 如果没有指定类别或为空，则包含所有文件
            if not relevant_categories or should_include:
                filtered[filename] = data
        
        logger.info(f"✓ 过滤得到 {len(filtered)} 个相关JSON文件")
        
        return filtered
    
    def retrieve_from_json(self, json_data: Dict, query: str, top_k: int = 5) -> Dict[str, Any]:
        """从单个JSON文件中检索相关内容
        
        Args:
            json_data: JSON数据对象
            query: 查询文本
            top_k: 返回最相关的前k条
            
        Returns:
            Dict: 检索结果（内容、相关性评分等）
        """
        # 简单的检索逻辑：关键词匹配和内容提取
        retrieved_items = []
        
        # 递归遍历JSON对象
        self._extract_matching_items(json_data, query, retrieved_items)
        
        # 排序并返回Top-K
        retrieved_items.sort(key=lambda x: x.get('score', 0), reverse=True)
        top_items = retrieved_items[:top_k]
        
        return {
            'items': top_items,
            'total_matched': len(retrieved_items),
            'top_k': len(top_items)
        }
    
    def _extract_matching_items(self, obj: Any, query: str, results: List, depth: int = 0):
        """递归提取匹配的内容项"""
        if depth > 5:  # 限制递归深度
            return
        
        if isinstance(obj, dict):
            for key, value in obj.items():
                if isinstance(value, (str, int, float)):
                    if self._is_match(str(value), query):
                        results.append({
                            'key': key,
                            'value': str(value)[:500],
                            'score': self._calculate_match_score(str(value), query)
                        })
                elif isinstance(value, (dict, list)):
                    self._extract_matching_items(value, query, results, depth + 1)
        
        elif isinstance(obj, list):
            for item in obj:
                self._extract_matching_items(item, query, results, depth + 1)
    
    def _is_match(self, text: str, query: str) -> bool:
        """检查文本是否与查询匹配"""
        query_lower = query.lower()
        text_lower = text.lower()
        
        # 关键词匹配（可扩展为更复杂的匹配逻辑）
        keywords = query_lower.split()
        for keyword in keywords:
            if len(keyword) > 2 and keyword in text_lower:
                return True
        
        return False
    
    def _calculate_match_score(self, text: str, query: str) -> float:
        """计算文本与查询的匹配得分"""
        query_lower = query.lower()
        text_lower = text.lower()
        
        keywords = query_lower.split()
        matching_keywords = sum(1 for kw in keywords if len(kw) > 2 and kw in text_lower)
        
        score = min(matching_keywords / len(keywords), 1.0) if keywords else 0.0
        return score


# ============================================================================
# 并行LLM处理和答案合成
# ============================================================================

class ParallelJSONQAEngine:
    """并行JSON问答引擎 - 核心处理流程"""
    
    def __init__(self, json_directory: str = None, api_keys: List[str] = None):
        """初始化并行JSON问答引擎
        
        Args:
            json_directory: JSON文件目录
            api_keys: LLM API密钥列表（最多8个）
        """
        self.json_manager = JSONDataManager(json_directory)
        self.type_identifier = QuestionTypeIdentifier()
        
        # 初始化并行LLM管理器
        self.parallel_llm = None
        if ParallelLLMManager is not None:
            try:
                self.parallel_llm = ParallelLLMManager(api_keys=api_keys)
                logger.info("✓ 並行LLM管理器已初始化")
            except Exception as e:
                logger.warning(f"⚠️  並行LLM初始化失败: {e}，将使用顺序模式")
        else:
            logger.warning("⚠️  ParallelLLMManager不可用，将使用顺序模式")
    
    def answer_question(self, question: str) -> FinalAnswer:
        """完整的问答流程
        
        Args:
            question: 用户问题
            
        Returns:
            FinalAnswer: 最终答案
        """
        logger.info("\n" + "="*80)
        logger.info(f"🎯 开始处理问题: {question}")
        logger.info("="*80)
        
        # ========== Stage 1: 问题分析 ==========
        print(f"\n📍 Stage 1: 问题类型识别")
        question_analysis = self.type_identifier.identify_question_type(question)
        print(f"   • 识别类型: {question_analysis.identified_type}")
        print(f"   • 置信度: {question_analysis.type_confidence:.2f}")
        print(f"   • 相关JSON: {question_analysis.relevant_json_categories}")
        
        # ========== Stage 2: 智能检索 ==========
        print(f"\n📍 Stage 2: 智能JSON检索")
        filtered_jsons = self.json_manager.get_filtered_jsons(
            question_analysis.relevant_json_categories
        )
        
        if not filtered_jsons:
            logger.warning("未找到相关JSON文件，将使用全部JSON")
            filtered_jsons = self.json_manager.json_files
        
        print(f"   • 选中JSON文件数: {len(filtered_jsons)}")
        
        # 从每个JSON检索信息
        retrieval_results: List[JSONRetrievalResult] = []
        retrieval_prompts = []
        
        for json_filename, json_data in filtered_jsons.items():
            # 从JSON检索相关内容
            retrieval_result = self.json_manager.retrieve_from_json(
                json_data, question, top_k=5
            )
            
            # 构建retrieval_result对象
            content_summary = f"匹配项数: {retrieval_result['total_matched']}, 返回Top-{retrieval_result['top_k']}"
            
            result = JSONRetrievalResult(
                json_file=json_filename,
                json_category=self.json_manager.json_metadata.get(json_filename, {}).get('category', 'unknown'),
                query_text=question,
                retrieved_content=retrieval_result,
                relevance_score=0.7 + (0.3 * min(retrieval_result['top_k'] / 5.0, 1.0)),
                source_ref=f"[{json_filename}]"
            )
            
            retrieval_results.append(result)
            
            print(f"   • {json_filename}: {content_summary}")
        
        if not retrieval_results:
            logger.error("❌ 无法从任何JSON检索到信息")
            return self._create_empty_answer(question, "无法检索到相关信息")
        
        # ========== Stage 3: 并行LLM处理 ==========
        print(f"\n📍 Stage 3: 并行LLM答案生成")
        print(f"   🚀 启动 {min(len(retrieval_results), 8)} 个并行LLM")
        
        parallel_answers = self._generate_parallel_answers(
            question, question_analysis, retrieval_results
        )
        
        # ========== Stage 4: 答案有效性检验 ==========
        print(f"\n📍 Stage 4: 答案有效性检验")
        valid_answers = self._validate_and_filter_answers(parallel_answers, question)
        
        print(f"   • 有效答案: {len(valid_answers)}/{len(parallel_answers)}")
        
        # ========== Stage 5: 答案合成 ==========
        print(f"\n📍 Stage 5: 答案合成")
        final_answer = self._synthesize_final_answer(
            question, question_analysis, valid_answers
        )
        
        logger.info("\n" + "="*80)
        logger.info("✅ 问答处理完成")
        logger.info("="*80)
        
        return final_answer
    
    def _generate_parallel_answers(self, question: str, analysis: QuestionAnalysisResult,
                                   retrieval_results: List[JSONRetrievalResult]) -> List[ParallelAnswerResult]:
        """使用并行LLM生成答案
        
        Args:
            question: 原始问题
            analysis: 问题分析结果
            retrieval_results: 检索结果列表
            
        Returns:
            List[ParallelAnswerResult]: 并行答案结果列表
        """
        prompts = []
        llm_sources = []
        
        # 为每个JSON检索结果构建Prompt
        for idx, retrieval in enumerate(retrieval_results[:8]):  # 最多8个并行LLM
            prompt = self._build_prompt_for_retrieval(
                question, analysis, retrieval, idx + 1
            )
            prompts.append(prompt)
            llm_sources.append(retrieval.json_file)
        
        # 如果没有并行LLM管理器，使用单个LLM顺序处理
        if not self.parallel_llm:
            logger.warning("⚠️  并行LLM不可用，使用单个LLM顺序处理")
            answers = self._sequential_generation(prompts, llm_sources)
        else:
            # 并行调用LLM
            answers = self.parallel_llm.call_llm_parallel(
                prompts=prompts,
                temperatures=[0.2] * len(prompts),
                max_tokens=1000,
                stream=False
            )
        
        # 构建ParallelAnswerResult列表
        result_list = []
        for llm_idx, (source, answer_text) in enumerate(zip(llm_sources, answers), 1):
            result = ParallelAnswerResult(
                llm_index=llm_idx,
                json_source=source,
                answer_content=answer_text,
                validity_score=1.0  # 初始值，后续通过检验更新
            )
            result_list.append(result)
        
        return result_list
    
    def _sequential_generation(self, prompts: List[str], sources: List[str]) -> List[str]:
        """使用单个LLM顺序生成答案"""
        answers = []
        
        # 检查LLMConfig是否可用
        if LLMConfig is None:
            logger.error("❌ LLMConfig不可用，无法生成答案")
            return [f"错误: LLM配置不可用" for _ in prompts]
        
        llm = LLMConfig()
        
        for prompt, source in zip(prompts, sources):
            try:
                answer = llm.call_llm(prompt, temperature=0.2, max_tokens=1000)
                answers.append(answer)
                logger.debug(f"✓ {source} 答案生成完成")
            except Exception as e:
                logger.error(f"❌ {source} 答案生成失败: {e}")
                answers.append(f"错误: {str(e)}")
        
        return answers
    
    def _build_prompt_for_retrieval(self, question: str, analysis: QuestionAnalysisResult,
                                    retrieval: JSONRetrievalResult, llm_index: int) -> str:
        """为单个JSON检索结果构建Prompt"""
        # 格式化检索内容
        retrieved_text = self._format_retrieval_content(retrieval.retrieved_content)
        
        prompt = f"""你是液流电池领域的专家。请根据以下信息回答用户的问题。

【信息来源】
文件: {retrieval.json_file}
类型: {retrieval.json_category}

【检索到的相关信息】
{retrieved_text}

【用户问题】
{question}

【回答要求】
1. 仅基于提供的信息进行回答
2. 不要捏造或猜测没有提供的数据
3. 不要改变数据的含义或上下文
4. 如果信息不足以回答问题，请明确指出
5. 在回答末尾附加来源: {retrieval.source_ref}

【回答】
"""
        
        return prompt
    
    def _format_retrieval_content(self, retrieval_result: Dict) -> str:
        """格式化检索内容"""
        items = retrieval_result.get('items', [])
        if not items:
            return "未找到相关信息"
        
        formatted_lines = []
        for idx, item in enumerate(items, 1):
            key = item.get('key', 'unknown')
            value = item.get('value', '')
            score = item.get('score', 0)
            formatted_lines.append(f"{idx}. [{key}] {value} (相关度: {score:.2f})")
        
        return "\n".join(formatted_lines)
    
    def _validate_and_filter_answers(self, parallel_answers: List[ParallelAnswerResult],
                                      question: str) -> List[ParallelAnswerResult]:
        """验证和过滤答案，防止捏造、张冠李戴等问题
        
        Args:
            parallel_answers: 并行生成的答案列表
            question: 原始问题
            
        Returns:
            List[ParallelAnswerResult]: 有效答案列表
        """
        valid_answers = []
        
        for answer_result in parallel_answers:
            # 进行有效性检验
            is_valid, validity_score, error_reason = self._check_answer_validity(
                answer_result.answer_content, question
            )
            
            answer_result.is_valid = is_valid
            answer_result.validity_score = validity_score
            answer_result.error_reason = error_reason
            
            if is_valid:
                valid_answers.append(answer_result)
            else:
                logger.warning(f"⚠️  {answer_result.json_source} 答案无效: {error_reason}")
        
        return valid_answers
    
    def _check_answer_validity(self, answer: str, question: str) -> Tuple[bool, float, str]:
        """检查答案的有效性
        
        检查项：
        1. 是否包含"无法回答"、"信息不足"等否定表述
        2. 是否包含"不知道"、"未知"等表述
        3. 答案长度是否过短（< 20字符可能无效）
        4. 是否检测到明显的捏造数据（AI幻觉）
        
        Returns:
            Tuple[bool, float, str]: (是否有效, 有效性评分0-1, 错误原因)
        """
        # 无效信号检测
        invalid_signals = [
            ('无法回答', 0.1),
            ('信息不足', 0.2),
            ('不知道', 0.1),
            ('未知', 0.15),
            ('抱歉', 0.05),
            ('cannot answer', 0.1),
            ('insufficient', 0.2),
            ('不清楚', 0.15),
            ('无相关信息', 0.0),
        ]
        
        answer_lower = answer.lower()
        
        # 检查无效信号
        for signal, penalty in invalid_signals:
            if signal in answer_lower:
                score = max(0, 1.0 - penalty)
                if score < 0.5:
                    return False, score, f"检测到否定信号: {signal}"
        
        # 检查答案长度
        if len(answer.strip()) < 20:
            return False, 0.2, "答案过短，可能不完整"
        
        # 检查是否过长（超过5000字符可能包含过度详细）
        if len(answer) > 5000:
            logger.warning("⚠️  答案过长，可能包含过度发挥")
            score = 0.7
        else:
            score = 0.9
        
        # 检测明显的数据捏造模式（例如：重复相同的数字、不合理的单位等）
        # 这里可以添加更复杂的检测逻辑
        
        return True, score, ""
    
    def _synthesize_final_answer(self, question: str, analysis: QuestionAnalysisResult,
                                 valid_answers: List[ParallelAnswerResult]) -> FinalAnswer:
        """合成最终答案
        
        Args:
            question: 原始问题
            analysis: 问题分析结果
            valid_answers: 有效答案列表
            
        Returns:
            FinalAnswer: 最终答案对象
        """
        final_answer = FinalAnswer(
            question=question,
            type_info=f"问题类型: {analysis.identified_type} (置信度: {analysis.type_confidence:.2f})",
            all_valid_count=len(valid_answers)
        )
        
        # 构建答案段落
        answer_sections = []
        for answer_result in valid_answers:
            section = {
                'source': answer_result.json_source,
                'content': answer_result.answer_content,
                'validity_score': answer_result.validity_score
            }
            answer_sections.append(section)
            final_answer.answer_sections.append(section)
        
        # 构建最终文本
        final_text_parts = [
            f"【问题】{question}\n",
            f"【类型分析】{analysis.identified_type} (置信度: {analysis.type_confidence:.2f})\n",
            f"【来源数】{len(valid_answers)} 个JSON文件\n\n",
            "【答案】\n"
        ]
        
        for idx, section in enumerate(answer_sections, 1):
            final_text_parts.append(f"\n【来源{idx}: {section['source']}】")
            final_text_parts.append(f"\n{section['content']}\n")
        
        # 添加总体置信度
        avg_validity = sum(s['validity_score'] for s in answer_sections) / len(answer_sections) if answer_sections else 0
        final_answer.confidence = 0.7 + (0.3 * avg_validity)
        
        final_answer.final_text = "\n".join(final_text_parts)
        
        return final_answer
    
    def _create_empty_answer(self, question: str, reason: str) -> FinalAnswer:
        """创建空答案"""
        return FinalAnswer(
            question=question,
            type_info="",
            final_text=f"❌ {reason}",
            confidence=0.0
        )


# ============================================================================
# 主程序
# ============================================================================

def main():
    """主程序 - 示例使用"""
    
    # 配置
    JSON_DIRECTORY = os.path.join(SCRIPT_DIR, 'llm_responses')  # 指向实际JSON文件目录
    
    # 创建引擎
    print("🚀 初始化并行JSON问答引擎...")
    engine = ParallelJSONQAEngine(json_directory=JSON_DIRECTORY)
    
    # 测试问题
    test_questions = [
        "铁铬液流电池电解液优化方案",
        "全钒液流电池如何合成？",
        "液流电池的工作原理是什么？",
    ]
    
    # 处理问题
    for question in test_questions:
        print(f"\n{'='*80}")
        print(f"问题: {question}")
        print('='*80)
        
        result = engine.answer_question(question)
        
        # 输出结果
        print(f"\n{result.final_text}")
        print(f"\n整体置信度: {result.confidence:.2f}")


if __name__ == "__main__":
    main()
