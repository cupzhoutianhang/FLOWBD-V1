import sys
import os
from typing import Optional

# 配置项目路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

AGENT_DIR = os.path.join(PROJECT_ROOT, 'src', 'agent')
if AGENT_DIR not in sys.path:
    sys.path.insert(0, AGENT_DIR)

from agent.part5_multiagent_integration import AgentPipelineState, SimpleMultiAgentSystem
from agent.part1_knowledge_arsenal import KnowledgeArsenal, LLMConfig, ensure_milvus_loaded

# 【证据图闭环】首轮提问时正式会话 ID 未定型的临时挂载名(回答落库后 rebind 到正式 ID)
PENDING_SESSION_ID = "pending_iterative"
from molecule_tools.molecule_property_tool import MoleculeQueryAgent
from retrieval_logger import RetrievalLogger


class AgentMilvusConnector:
    """
    Agent专用的Milvus连接器
    
    职责：仅负责连接已有的Milvus集合，进行检索
    不包含文档加载、分块、索引构建等存储逻辑
    
    存储逻辑由 TraditionalRAGV3（storage_mode=True）单独负责
    """
    
    def __init__(self, milvus_host: str = "localhost", milvus_port: int = 19530,
                 collection_name: str = "traditional_rag_collection_v5",
                 embedding_model=None, embedding_tokenizer=None,
                 reranker_model=None, reranker_tokenizer=None):
        """
        初始化Agent Milvus连接器
        
        Args:
            milvus_host: Milvus服务器主机
            milvus_port: Milvus服务器端口
            collection_name: 集合名称
            embedding_model: 【新增】共享的BGE-M3模型（避免重复加载）
            embedding_tokenizer: 【新增】共享的BGE-M3分词器
            reranker_model: 【新增】共享的BGE-Reranker模型
            reranker_tokenizer: 【新增】共享的BGE-Reranker分词器
        """
        self.milvus_host = milvus_host
        self.milvus_port = milvus_port
        if collection_name == 'traditional_rag_collection_v5':
            from rag.sparse_encoding import active_collection
            collection_name = active_collection(collection_name)
        self.collection_name = collection_name
        self.milvus_collection = None
        
        # 【修改】如果提供了共享模型，直接使用；否则为None
        self.embedding_model = embedding_model
        self.embedding_tokenizer = embedding_tokenizer
        self.reranker_model = reranker_model
        self.reranker_tokenizer = reranker_tokenizer
        
        # 初始化连接
        self._init_connection()
    
    def _init_connection(self):
        """初始化Milvus连接"""
        try:
            from pymilvus import Collection, connections
            
            connections.connect(host=self.milvus_host, port=self.milvus_port)
            
            # 检查集合是否存在
            from pymilvus import utility
            if not utility.has_collection(self.collection_name):
                return False
            
            # 加载集合（异步加载，避免阻塞初始化；检索前由 ensure_milvus_loaded 等待完成）
            self.milvus_collection = Collection(name=self.collection_name)
            self.milvus_collection.load(_async=True)
            
            return True
        except Exception as e:
            print(f"❌ Milvus连接失败: {e}")
            print("   请确保:")
            print("   1. Milvus服务正在运行 (端口19530)")
            print("   2. 集合已通过存储程序创建和填充")
            return False
    
    def load_embedding_models(self, model_path: str):
        """加载嵌入模型用于检索
        
        【修改】增加对 meta tensor 的检查，防止权重未加载导致崩溃
        """
        # 如果已经有共享模型，检查其是否处于可用状态（非 meta tensor）
        if self.embedding_model and self.embedding_tokenizer:
            try:
                # 检查 device 是否为 meta
                if hasattr(self.embedding_model, 'device') and str(self.embedding_model.device) == 'meta':
                    print("⚠️  检测到共享模型为 Meta Tensor (权重未加载)，将强制从本地路径重新加载...")
                else:
                    return True
            except Exception:
                return True # 异常则认为可用，交由后续逻辑处理
        
        # 【降级方案】重新从路径加载，并显式禁用 low_cpu_mem_usage
        try:
            from transformers import AutoTokenizer, AutoModel
            
            bge_m3_path = os.path.join(model_path, "bge-m3")
            if os.path.exists(bge_m3_path):
                self.embedding_model = AutoModel.from_pretrained(
                    bge_m3_path, 
                    local_files_only=True,
                    low_cpu_mem_usage=False  # 强制加载权重，解决 meta tensor 问题
                )
                self.embedding_tokenizer = AutoTokenizer.from_pretrained(bge_m3_path, local_files_only=True)
            else:
                return False
            
            # 加载Reranker模型
            bge_reranker_path = os.path.join(model_path, "bge-reranker-base")
            if os.path.exists(bge_reranker_path):
                from transformers import AutoModelForSequenceClassification
                self.reranker_model = AutoModelForSequenceClassification.from_pretrained(
                    bge_reranker_path, 
                    local_files_only=True,
                    low_cpu_mem_usage=False  # 强制加载权重
                )
                self.reranker_tokenizer = AutoTokenizer.from_pretrained(
                    bge_reranker_path, local_files_only=True
                )
            else:
                pass
            
            return True
        except Exception as e:
            print(f"⚠️  加载嵌入模型失败: {e}")
            return False
    
    def is_connected(self) -> bool:
        """检查是否连接成功"""
        return self.milvus_collection is not None
    
    def get_models(self) -> dict:
        """
        返回加载的模型和Milvus集合
        用于与recall_document_v2兼容
        """
        return {
            'embedding_model': self.embedding_model,
            'embedding_tokenizer': self.embedding_tokenizer,
            'milvus_collection': self.milvus_collection,
            'reranker_model': self.reranker_model,  # 【修改】提供实际加载的Reranker
            'reranker_tokenizer': self.reranker_tokenizer  # 【修改】提供实际加载的分词器
        }


class MultiTurnConversation:
    def __init__(self):
        import warnings
        import logging
        import contextlib
        import io
        
        # 禁用日志和警告
        warnings.filterwarnings('ignore')
        logging.disable(logging.CRITICAL)
        
        # 初始化检索结果记录器
        self.retrieval_logger = RetrievalLogger()
        
        # 抑制初始化时的输出
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            # 初始化知识武库
            self.arsenal = KnowledgeArsenal()
            if not self.arsenal.assemble():
                raise RuntimeError("知识武库初始化失败")
            
            llm = self.arsenal.get_llm()
            
            # 【新增】专门为 Stage 1 配置的 Moonshot LLM
            # 模型: kimi-k2-0905-preview, 端点: https://api.moonshot.cn/v1
            parsing_llm = LLMConfig(
                api_key=__import__("os").environ.get("MOONSHOT_API_KEY", ""),
                base_url="https://api.moonshot.cn/v1",
                model="kimi-k2.6"
            )

            # 【新增】专门为最终回答配置的 GLM
            internlm = llm  # 使用主LLM配置，即GLM
            
            # 初始化图谱RAG
            self.graph_rag = None
            try:
                from graph_rag.graph_qa_v2 import GraphQA
                self.graph_rag = GraphQA()
                print(f"[初始化] ✓ 图谱RAG初始化成功")
                if hasattr(self.graph_rag, 'graph') and self.graph_rag.graph:
                    if isinstance(self.graph_rag.graph, dict):
                        nodes = len(self.graph_rag.graph.get('nodes', {}))
                        edges = len(self.graph_rag.graph.get('edges', {}))
                        print(f"         📊 Neo4j图谱: {nodes} 个节点, {edges} 条边")
            except Exception:
                print(f"[初始化] ✗ 图谱RAG初始化失败")
                pass
            
            # 初始化传统RAG - 仅连接Milvus，不进行存储
            # 【修改】先从知识武库获取已加载的共享模型，避免重复加载
            self.traditional_rag = None
            try:
                model_path = os.path.join(PROJECT_ROOT, "src", "rag", "models")
                
                # 【新增】从KnowledgeArsenal获取已加载的共享模型
                shared_embedding_model = None
                shared_embedding_tokenizer = None
                if hasattr(self.arsenal, 'embedding_manager') and self.arsenal.embedding_manager:
                    shared_embedding_model = self.arsenal.embedding_manager.embedding_model
                    shared_embedding_tokenizer = self.arsenal.embedding_manager.embedding_tokenizer
                
                shared_reranker_model = None
                shared_reranker_tokenizer = None
                if hasattr(self.arsenal, 'reranker_model') and self.arsenal.reranker_model:
                    shared_reranker_model = self.arsenal.reranker_model
                if hasattr(self.arsenal, 'reranker_tokenizer') and self.arsenal.reranker_tokenizer:
                    shared_reranker_tokenizer = self.arsenal.reranker_tokenizer
                
                # 【修改】将共享模型传入Connector，避免第二次加载
                milvus_connector = AgentMilvusConnector(
                    embedding_model=shared_embedding_model,
                    embedding_tokenizer=shared_embedding_tokenizer,
                    reranker_model=shared_reranker_model,
                    reranker_tokenizer=shared_reranker_tokenizer
                )
                if milvus_connector.is_connected():
                    # 【修改】如果没有共享模型，才从路径加载（降级方案）
                    load_result = milvus_connector.load_embedding_models(model_path)
                    
                    if load_result:
                        self.traditional_rag = milvus_connector
                        print(f"[初始化] ✓ 传统RAG初始化成功")
                        try:
                            print(f"         📊 Milvus集合实体数: {self.traditional_rag.milvus_collection.num_entities}")
                        except Exception:
                            print(f"         ⏳ Milvus集合正在后台异步加载，首次检索前将就绪")
                    else:
                        print(f"[初始化] ✗ 模型加载失败")
                else:
                    print(f"[初始化] ✗ Milvus连接失败")
            except Exception as e:
                print(f"⚠️  传统RAG初始化失败: {e}")
                import traceback
                traceback.print_exc()
                pass
            
            # 初始化分子查询Agent
            molecule_agent = None
            try:
                molecule_agent = MoleculeQueryAgent(
                    llm_config=llm,
                    enable_deepchem=False
                )
            except Exception:
                pass
            
            # 初始化简化的多智能体系统
            self.system = SimpleMultiAgentSystem(
                llm,
                graph_rag=self.graph_rag,
                traditional_rag=self.traditional_rag,
                molecule_agent=molecule_agent,
                parsing_llm=parsing_llm,
                internlm=internlm  # 【新增】传入InternLM
            )
        
        # 【证据图闭环 M3】迭代模式的证据图存储(惰性创建, 不影响普通模式)
        self._evidence_store = None

        self.current_state: Optional[AgentPipelineState] = None

    def run_conversation(self, question: str, enable_first_principles: bool = False):
        """执行对话"""
        # 修改为迭代生成器并保存状态
        for state in self.system.process(question, enable_first_principles=enable_first_principles):
            self.current_state = state
            yield state  # 透传状态给前端
            
        # 保存检索数据到JSON
        if self.current_state:
            self.current_state.save_retrieval_data()

    # ------------------------------------------------------------------
    # 【证据图闭环 M3】迭代闭环模式(计划 3.8)
    # ------------------------------------------------------------------

    def _ensure_evidence_store(self, session_id: str):
        """按侧栏会话惰性创建证据图存储(一个会话一张图, 会话内复用)。

        PENDING_SESSION_ID 为临时挂载名: fresh=True 不读磁盘, 防止上一个
        未完成会话残留的 pending 文件跨会话污染本会话证据图。
        """
        from agent.evidence_graph import EvidenceGraphStore
        sid = str(session_id)
        if self._evidence_store is None or self._evidence_store.session_id != sid:
            self._evidence_store = EvidenceGraphStore(
                session_id=sid, fresh=(sid == PENDING_SESSION_ID))
        return self._evidence_store

    def _migrate_evidence_store(self, new_session_id: str) -> bool:
        """pending 证据图迁移挂到正式会话 ID; 返回是否发生迁移。

        注: 迁移发生在 save_chat_log 之后, jsonl 中快照 meta.session_id 显示
        迁移前的 pending 值属预期(仅信息性字段, nodes/edges/stats 不受影响)。
        """
        if self._evidence_store is None or self._evidence_store.session_id == str(new_session_id):
            return False
        self._evidence_store.rebind(new_session_id)
        return True

    def run_iterative_conversation(self, question: str, session_id: str, max_rounds: int = 3,
                                   summarized_answer: bool = False):
        """迭代闭环模式(证据图驱动): 生成器, 逐轮 yield AgentPipelineState。

        最终轮含 final_answer 与 evidence_graph_snapshot; 每轮动作记录在
        state.iterations(前端逐轮时间线数据源)。store 落盘由本方法兜底。
        summarized_answer=True 时答案生成用图摘要替代全量融合上下文(R9: doc_sources 不裁剪)。
        """
        from agent.evidence_graph import IterativeCoordinator

        store = self._ensure_evidence_store(session_id)
        store.load()   # 会话内复用: 载入本会话此前的证据
        coordinator = IterativeCoordinator(
            self.system.pipeline, self.system.llm, store, max_rounds=max_rounds,
            summarized_answer=summarized_answer)
        final_state = None
        for state in coordinator.run(question):
            final_state = state
            self.current_state = state
            yield state
        if final_state is not None:
            store.save()
            # 与普通模式一致: 检索数据留档(rag.json / graph_rag.json / web_search.json)
            try:
                final_state.save_retrieval_data()
            except Exception:
                pass

    def get_conversation_state(self):
        """获取当前对话状态 - 用于Streamlit前端获取数据"""
        return self.current_state
    
    def get_llm_intermediate_answers(self) -> list:
        """提取中间答案 - 各个LLM生成的单独答案
        
        返回格式:
        [
            {"source": "paper1.pdf", "answer": "LLM1的答案内容"},
            {"source": "paper2.pdf", "answer": "LLM2的答案内容"},
            ...
        ]
        """
        if not self.current_state or not hasattr(self.current_state, 'final_answer'):
            return []
        
        # 从final_answer中提取各个部分
        final_answer = self.current_state.final_answer
        intermediate_answers = []
        
        import re
        
        # 1. 拆分正文和来源列表
        parts = final_answer.split('\n\n---\n\n')
        if len(parts) < 2:
            # 兼容旧格式或无来源格式
            parts = final_answer.split('\n\n---\n')
            
        if len(parts) < 2:
            # 兼容最初的 【source】 格式
            pattern = r'\【(.+?)\】\n(.+?)(?=\n\n\【|$)'
            matches = re.findall(pattern, final_answer, re.DOTALL)
            for source, answer in matches:
                intermediate_answers.append({
                    "source": source.strip(),
                    "answer": answer.strip()
                })
            return intermediate_answers

        body_text = parts[0]
        sources_section = parts[1]
        
        # 2. 解析来源列表 [Ref-n]: Title
        ref_map = {}
        source_pattern = r'\[(?:Ref-|Source)(\d+)?\]: (.+)'
        for line in sources_section.split('\n'):
            match = re.search(source_pattern, line)
            if match:
                ref_id = match.group(1) or "unknown"
                title = match.group(2).strip()
                ref_map[ref_id] = title
        
        # 3. 解析正文段落，提取引用标记并映射回标题
        # 段落通常由 \n\n 分隔
        paragraphs = body_text.split('\n\n')
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            # 提取段尾的 [Ref-n]
            ref_match = re.search(r'\[Ref-(\d+)\]$', para)
            if ref_match:
                ref_id = ref_match.group(1)
                source_title = ref_map.get(ref_id, f"Source Ref-{ref_id}")
                # 移除段尾的引用标记作为纯答案
                clean_answer = para[:ref_match.start()].strip()
                intermediate_answers.append({
                    "source": source_title,
                    "answer": clean_answer
                })
            else:
                intermediate_answers.append({
                    "source": "Unknown Source",
                    "answer": para
                })
        
        return intermediate_answers
    
    def _log_rag_retrieval(self, question: str):
        """
        【已禁用】不再记录RAG的检索结果
        """
        pass
    
    def _log_graph_rag_retrieval(self, question: str):
        """
        【已禁用】不再记录GraphRAG的检索结果
        """
        pass
    
    def _embed_question_directly(self, question: str):
        """【新增】直接向量化用户原始问题，不经过大模型处理
        
        Args:
            question: 用户问题
            
        Returns:
            np.ndarray: 问题的向量表示（numpy float32）
        """
        try:
            # 获取嵌入模型
            if not self.traditional_rag or not self.traditional_rag.embedding_model:
                return None
            
            embedding_model = self.traditional_rag.embedding_model
            embedding_tokenizer = self.traditional_rag.embedding_tokenizer
            
            if not embedding_model or not embedding_tokenizer:
                return None
            
            # 对问题进行向量化
            import torch
            import numpy as np
            
            inputs = embedding_tokenizer(
                [question],
                padding=True,
                truncation=True,
                return_tensors="pt",
                max_length=512
            )
            
            with torch.no_grad():
                outputs = embedding_model(**inputs)
                question_embedding = outputs.last_hidden_state[:, 0, :].cpu().numpy()[0]
            
            # 确保向量类型为float32
            question_embedding = question_embedding.astype(np.float32)
            question_embedding = np.nan_to_num(question_embedding, nan=0.0, posinf=0.0, neginf=0.0)
            
            return question_embedding
        
        except Exception as e:
            print(f"⚠️  问题向量化失败: {e}")
            return None

if __name__ == "__main__":
    import warnings
    import logging
    import contextlib
    import io
    
    # 禁用日志和警告
    warnings.filterwarnings('ignore')
    logging.disable(logging.CRITICAL)
    
    # 初始化多轮对话系统
    print("="*80)
    print("简化版多智能体对话系统")
    print("="*80)
    print("\n初始化系统中...\n")
    
    conversation = None
    try:
        conversation = MultiTurnConversation()
        print("✓ 系统初始化完成\n")
    except Exception as e:
        print(f"✗ 系统初始化失败: {e}")
        sys.exit(1)
    
    # 多轮对话循环
    while True:
        try:
            print("="*80)
            question = input("\n请输入问题（或输入 'exit'/'quit'/'q' 退出）: ").strip()
            
            if question.lower() in ['exit', 'quit', 'q']:
                print("\n感谢使用，再见！")
                break
            
            if not question:
                print("\n请输入有效的问题")
                continue
            
            # 【修复】消费迭代器，触发对话处理
            for state in conversation.run_conversation(question):
                pass  # 迭代完成后，状态已保存在conversation.current_state中
            
        except KeyboardInterrupt:
            print("\n\n已中断，感谢使用！")
            break
        except Exception as e:
            print(f"\n处理问题时出错: {e}")
            continue
