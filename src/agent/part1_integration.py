"""
Part 1 与 Graph RAG + RAG 混合系统集成桥接

提供了两种集成方式：
1. Part1ToHybrid - 使用Part 1的Agent框架增强HybridQAOptimized
2. HybridWithPart1 - 在混合系统中集成Part 1的数据源和Agent能力
"""

import os
import sys
from typing import Dict, Any, List, Optional

# 此文件位于 src/agent/graphrag_and_rag/agent/ 目录
# 不需要重新配置 sys.path（已由 run_part5_enhanced.py 配置）

from agent.part1_knowledge_arsenal import KnowledgeArsenal
from agent.agent_definitions import (
    QuestionParsingAgent,
    DocumentRetrievalAgent,
    GraphRetrievalAgent,
    InformationFusionAgent,
    AnswerGenerationAgent,
    ParsedQuestion,
    QueryIntent
)
# 注意：HybridQAOptimized已与Part 5集成，此导入已弃用
# from hybrid_qa_optimized import (
#     HybridQAOptimized,
#     QueryResult,
#     RetrievalResult
# )

import logging

logger = logging.getLogger(__name__)


class IntegratedQASystem:
    """集成的问答系统 - Part 1 Agent框架 + Graph RAG + Traditional RAG
    
    这个系统结合了：
    1. Part 1的知识武库和多Agent框架
    2. Graph RAG的知识图谱检索
    3. Traditional RAG的向量库检索
    
    通过Agent框架进行编排，比原始HybridQAOptimized更灵活高效
    """
    
    def __init__(self,
                 api_key: str = None,
                 md_folder: str = None,
                 embedding_model=None,
                 embedding_tokenizer=None,
                 reranker_model=None,
                 reranker_tokenizer=None,
                 milvus_host: str = "localhost",
                 milvus_port: int = 19530,
                 neo4j_uri: str = "bolt://localhost:7687",
                 neo4j_user: str = "neo4j",
                 neo4j_password: str = __import__("os").environ.get("NEO4J_PASSWORD", ""),
                 debug: bool = False):
        """初始化集成的问答系统
        
        Args:
            api_key: Kimi API密钥
            md_folder: Markdown文件夹路径
            embedding_model: BGE-M3嵌入模型
            embedding_tokenizer: BGE-M3 tokenizer
            reranker_model: Reranker模型
            reranker_tokenizer: Reranker tokenizer
            milvus_host: Milvus主机
            milvus_port: Milvus端口
            neo4j_uri: Neo4j连接URI
            neo4j_user: Neo4j用户名
            neo4j_password: Neo4j密码
            debug: 调试模式
        """
        
        print("\n" + "="*80)
        print("🔧 初始化集成问答系统 (Part 1 + Graph RAG + Traditional RAG)")
        print("="*80 + "\n")
        
        self.debug = debug
        
        # 初始化Part 1知识武库
        self.arsenal = KnowledgeArsenal(
            api_key=api_key,
            md_folder=md_folder,
            milvus_host=milvus_host,
            milvus_port=milvus_port,
            neo4j_uri=neo4j_uri,
            neo4j_user=neo4j_user,
            neo4j_password=neo4j_password,
            embedding_model=embedding_model,
            embedding_tokenizer=embedding_tokenizer
        )
        
        # 初始化Agent框架
        self._init_agents(embedding_model, embedding_tokenizer)
        
        # 初始化HybridQAOptimized（用于兼容性） - 已弃用
        self.hybrid_qa = None
        # self.hybrid_qa = HybridQAOptimized(
        #     embedding_model=embedding_model,
        #     embedding_tokenizer=embedding_tokenizer,
        #     milvus_collection=self.arsenal.kb_connector.milvus_collection,
        #     reranker_model=reranker_model,
        #     reranker_tokenizer=reranker_tokenizer,
        #     neo4j_uri=neo4j_uri,
        #     neo4j_user=neo4j_user,
        #     neo4j_password=neo4j_password,
        #     api_key=api_key,
        #     debug=debug
        # )
        
        # 组装知识武库
        self.arsenal.assemble()
        
        print("✅ 集成系统初始化完成\n")
    
    def _init_agents(self, embedding_model, embedding_tokenizer):
        """初始化所有Agent"""
        print("初始化Agent框架...")
        
        llm = self.arsenal.get_llm()
        kb_connector = self.arsenal.get_kb_connector()
        
        self.parsing_agent = QuestionParsingAgent(llm)
        self.doc_retrieval_agent = DocumentRetrievalAgent(kb_connector, self.arsenal.embedding_manager)
        self.graph_retrieval_agent = GraphRetrievalAgent(kb_connector)
        self.fusion_agent = InformationFusionAgent()
        self.answer_agent = AnswerGenerationAgent(llm)
        
        logger.info("✓ 所有Agent初始化完成\n")
    
    def query(self, question: str, method: str = "integrated", top_k: int = 5) -> Dict[str, Any]:
        """执行查询
        
        Args:
            question: 用户问题
            method: 查询方法
                - "integrated": 使用Part 1 Agent框架（推荐）
                - "hybrid": 使用原始HybridQAOptimized系统（兼容性）
                - "comparison": 对比两种方法
            top_k: 检索文档数量
            
        Returns:
            查询结果字典
        """
        
        if method == "integrated":
            return self._query_with_agents(question, top_k)
        elif method == "hybrid":
            return self._query_with_hybrid(question, top_k)
        elif method == "comparison":
            return self._query_comparison(question, top_k)
        else:
            raise ValueError(f"未知的查询方法: {method}")
    
    def _query_with_agents(self, question: str, top_k: int = 5) -> Dict[str, Any]:
        """使用Part 1 Agent框架的查询流程"""
        
        print(f"\n{'='*80}")
        print(f"【查询】{question}")
        print('='*80)
        
        print("\n[Step 1] 问题解析...")
        parsed = self.parsing_agent.parse_question(question)
        print(f"  • 实体: {parsed.entities}")
        print(f"  • 意图: {parsed.intent.value}")
        print(f"  • 领域相关: {parsed.is_domain_related}")
        
        print("\n[Step 2] 并行检索...")
        print("  [2a] 文档库检索...")
        doc_blocks = self.doc_retrieval_agent.retrieve_documents(parsed, top_k)
        print(f"    → {len(doc_blocks)} 个文档块")
        
        print("  [2b] 知识图谱查询...")
        graph_entities, graph_relations = self.graph_retrieval_agent.retrieve_from_graph(parsed)
        print(f"    → {len(graph_entities)} 个实体, {len(graph_relations)} 条关系")
        
        print("\n[Step 3] 信息融合...")
        fused_context, confidence = self.fusion_agent.fuse_information(
            parsed, doc_blocks, graph_entities, graph_relations
        )
        print(f"  • 置信度: {confidence:.2f}")
        
        print("\n[Step 4] 答案生成...")
        answer = self.answer_agent.generate_answer(parsed, fused_context, confidence)
        
        print(f"\n{'='*80}")
        print("【答案】")
        print('='*80)
        print(answer)
        print('='*80)
        
        return {
            "question": question,
            "method": "integrated",
            "answer": answer,
            "confidence": confidence,
            "entities": parsed.entities,
            "intent": parsed.intent.value,
            "doc_blocks": len(doc_blocks),
            "graph_entities": len(graph_entities),
            "graph_relations": len(graph_relations)
        }
    
    def _query_with_hybrid(self, question: str, top_k: int = 5) -> Dict[str, Any]:
        """使用原始HybridQAOptimized的查询流程 - 已弃用"""
        
        if self.hybrid_qa is None:
            raise NotImplementedError("HybridQAOptimized已弃用，请使用Part 5增强版系统")
        
        result = self.hybrid_qa.query(question, top_k=top_k)
        
        return {
            "question": question,
            "method": "hybrid",
            "answer": result.answer,
            "confidence": result.confidence,
            "entities": result.parsed.entities,
            "intent": result.parsed.intent.value,
            "doc_blocks": len(result.retrieval.doc_blocks),
            "graph_entities": len(result.retrieval.graph_data.get("entities", {}))
        }
    
    def _query_comparison(self, question: str, top_k: int = 5) -> Dict[str, Any]:
        """对比两种查询方法"""
        
        print("\n对比两种查询方法...\n")
        
        result1 = self._query_with_agents(question, top_k)
        print("\n" + "-"*80 + "\n")
        result2 = self._query_with_hybrid(question, top_k)
        
        print("\n" + "="*80)
        print("【对比总结】")
        print('='*80)
        print(f"\nPart 1 Agent框架:")
        print(f"  • 置信度: {result1['confidence']:.2f}")
        print(f"  • 检索: {result1['doc_blocks']} 文档 + {result1['graph_entities']} 图谱实体")
        print(f"\nHybridQAOptimized:")
        print(f"  • 置信度: {result2['confidence']:.2f}")
        print(f"  • 检索: {result2['doc_blocks']} 文档 + {result2['graph_entities']} 图谱实体")
        
        return {
            "question": question,
            "method": "comparison",
            "agent_framework": result1,
            "hybrid_qa": result2
        }
    
    def close(self):
        """关闭系统"""
        self.arsenal.close()
        if self.hybrid_qa is not None:
            self.hybrid_qa.close()
        logger.info("✓ 集成系统已关闭")


def demo():
    """演示集成系统的使用"""
    
    print("\n" + "="*80)
    print("Part 1 集成系统演示")
    print("="*80)
    
    # 初始化系统（只加载LLM和Markdown，跳过Milvus/Neo4j）
    system = IntegratedQASystem(debug=True)
    
    # 测试问题
    test_questions = [
        "PHQ有什么官能团？",
        "DHPS的合成方法是什么？",
        "液流电池的工作原理",
    ]
    
    for i, question in enumerate(test_questions, 1):
        print(f"\n\n{'#'*80}")
        print(f"# 测试 {i}: {question}")
        print(f"{'#'*80}")
        
        try:
            # 使用Agent框架方法
            result = system.query(question, method="integrated")
            
            print(f"\n✓ 查询成功")
            print(f"  置信度: {result['confidence']:.2f}")
            
        except Exception as e:
            print(f"\n❌ 查询失败: {e}")
    
    system.close()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        demo()
    else:
        print("""
集成系统使用示例：

1. 从Part1系统导入并使用集成系统：
   from part1_integration import IntegratedQASystem
   
   system = IntegratedQASystem()
   result = system.query("你的问题", method="integrated")
   print(result['answer'])

2. 运行演示：
   python part1_integration.py --demo

3. 方法选择：
   - "integrated": 使用Part 1 Agent框架（推荐）
   - "hybrid": 使用HybridQAOptimized系统
   - "comparison": 对比两种方法
""")
