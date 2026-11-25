"""
召回结果记录器 - 用于记录RAG和GraphRAG的检索结果

功能：
1. 记录RAG的召回文本，包括original_filename来源标记
2. 记录GraphRAG的实体信息，包括source_docs来源标记
3. 将结果持久化到JSON文件
4. 支持多问题累积（不覆盖）
"""

import os
import json
from typing import List, Dict, Any
from datetime import datetime


class RetrievalLogger:
    """检索结果记录器"""
    
    def __init__(self, data_dir: str = None):
        """
        初始化记录器
        
        Args:
            data_dir: 数据保存目录，默认为 src/agent/data
        """
        if data_dir is None:
            # 获取项目根目录
            current_dir = os.path.dirname(os.path.abspath(__file__))
            data_dir = os.path.join(current_dir, "data")
        
        self.data_dir = data_dir
        
        # 确保目录存在
        os.makedirs(self.data_dir, exist_ok=True)
        
        self.rag_file = os.path.join(self.data_dir, "rag.json")
        self.graph_rag_file = os.path.join(self.data_dir, "graph_rag.json")
    
    def _load_existing_data(self, file_path: str) -> List[Dict]:
        """
        加载现有的JSON文件数据
        
        Args:
            file_path: 文件路径
            
        Returns:
            列表，如果文件不存在则返回空列表
        """
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data if isinstance(data, list) else []
            except Exception as e:
                return []
        return []
    
    def _save_data(self, file_path: str, data: List[Dict]):
        """
        保存数据到JSON文件
        
        Args:
            file_path: 文件路径
            data: 数据列表
        """
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"❌ 保存文件失败 {file_path}: {e}")
    
    def log_rag_retrieval(self, question: str, parent_blocks: List[Dict], 
                         confidence: float = 0.0):
        """
        记录RAG的检索结果
        
        Args:
            question: 用户问题
            parent_blocks: 召回的父块列表
            confidence: 置信度
        """
        # 加载现有数据
        existing_data = self._load_existing_data(self.rag_file)
        
        # 构建本次查询的记录
        retrieval_record = {
            "timestamp": datetime.now().isoformat(),
            "question": question,
            "confidence": confidence,
            "retrieved_texts": []
        }
        
        # 处理每个父块
        for i, block in enumerate(parent_blocks, 1):
            text_record = {
                "index": i,
                "content": block.get('content', ''),
                "original_filename": block.get('original_filename', 'unknown'),
                "doc_id": block.get('doc_id', ''),
                "similarity": block.get('similarity', block.get('max_similarity', 0)),
                "rerank_score": block.get('rerank_score', 0)
            }
            retrieval_record["retrieved_texts"].append(text_record)
        
        # 添加到列表
        existing_data.append(retrieval_record)
        
        # 保存到文件
        self._save_data(self.rag_file, existing_data)
    
    def log_graph_rag_retrieval(self, question: str, graph_entities: Dict[str, Any],
                               graph_relations: List[Dict] = None, 
                               extracted_entities: List[str] = None):
        """
        记录GraphRAG的检索结果
        
        Args:
            question: 用户问题
            graph_entities: 知识图谱实体字典
            graph_relations: 知识图谱关系列表
            extracted_entities: 提取的实体列表
        """
        # 加载现有数据
        existing_data = self._load_existing_data(self.graph_rag_file)
        
        # 构建本次查询的记录
        retrieval_record = {
            "timestamp": datetime.now().isoformat(),
            "question": question,
            "extracted_entities": extracted_entities or [],
            "retrieved_entities": []
        }
        
        # 处理每个实体
        for i, (entity_name, entity_data) in enumerate(graph_entities.items(), 1):
            if isinstance(entity_data, dict):
                entity_record = {
                    "index": i,
                    "name": entity_name,
                    "type": entity_data.get('type', 'unknown'),
                    "source_docs": entity_data.get('source_docs', []),
                    "properties": entity_data.get('properties', {})
                }
            else:
                entity_record = {
                    "index": i,
                    "name": entity_name,
                    "type": "unknown",
                    "source_docs": [],
                    "data": str(entity_data)
                }
            
            retrieval_record["retrieved_entities"].append(entity_record)
        
        # 处理关系
        if graph_relations:
            retrieval_record["retrieved_relations"] = []
            for relation in graph_relations:
                retrieval_record["retrieved_relations"].append(relation)
        
        # 添加到列表
        existing_data.append(retrieval_record)
        
        # 保存到文件
        self._save_data(self.graph_rag_file, existing_data)
    
    def print_rag_summary(self):
        """打印RAG记录的总结"""
        data = self._load_existing_data(self.rag_file)
        print(f"\n{'='*70}")
        print(f"[RAG 召回历史统计]")
        print(f"{'='*70}")
        print(f"总问题数: {len(data)}")
        
        if data:
            print(f"\n问题列表:")
            for i, record in enumerate(data, 1):
                print(f"  {i}. {record['question']}")
                print(f"     召回文本数: {len(record.get('retrieved_texts', []))}")
        
        print(f"{'='*70}\n")
    
    def print_graph_rag_summary(self):
        """打印GraphRAG记录的总结"""
        data = self._load_existing_data(self.graph_rag_file)
        print(f"\n{'='*70}")
        print(f"[GraphRAG 召回历史统计]")
        print(f"{'='*70}")
        print(f"总问题数: {len(data)}")
        
        if data:
            print(f"\n问题列表:")
            for i, record in enumerate(data, 1):
                print(f"  {i}. {record['question']}")
                print(f"     实体数: {len(record.get('retrieved_entities', []))}")
                if 'retrieved_relations' in record:
                    print(f"     关系数: {len(record.get('retrieved_relations', []))}")
        
        print(f"{'='*70}\n")
    
    def get_rag_file_path(self) -> str:
        """获取RAG结果文件路径"""
        return self.rag_file
    
    def get_graph_rag_file_path(self) -> str:
        """获取GraphRAG结果文件路径"""
        return self.graph_rag_file
