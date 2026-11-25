import os
import sys
import json
import time
import hashlib
import numpy as np
import torch
import torch.nn.functional as F
from typing import List, Dict, Set, Tuple
import requests
from transformers import (
    AutoTokenizer, 
    AutoModelForMaskedLM, 
    AutoModelForSequenceClassification,
    PreTrainedModel,
    PreTrainedTokenizer
)
from pymilvus import connections, Collection, FieldSchema, CollectionSchema, DataType, utility
from class_query import identify_battery_type  # 导入改进的电池类型分类（支持中英文）

# ==============================================================================
# 召回模块 V2（核心：子块召回→父块关联→Reranker精排）
# ==============================================================================
class DocumentRecallerV2:
    def __init__(self,
                 embedding_model: PreTrainedModel,
                 embedding_tokenizer: PreTrainedTokenizer,
                 milvus_collection: Collection,
                 reranker_model: PreTrainedModel = None,
                 reranker_tokenizer: PreTrainedTokenizer = None,
                 min_similarity: float = 0.3,
                 child_top_k: int = 200,  # 子块召回数量（覆盖足够相关父块）
                 debug: bool = False):
        self.embedding_model = embedding_model
        self.embedding_tokenizer = embedding_tokenizer
        self.milvus_collection = milvus_collection
        self.reranker_model = reranker_model
        self.reranker_tokenizer = reranker_tokenizer
        self.min_similarity = min_similarity
        self.child_top_k = child_top_k
        self.debug = debug
        self.device = embedding_model.device if hasattr(embedding_model, 'device') else torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        # 确保Milvus集合加载到内存
        if not self.milvus_collection.is_loaded:
            self.milvus_collection.load()
            if self.debug:
                print(f"[RecallerV2] Milvus集合已加载到内存")

    def _log(self, message: str):
        if self.debug:
            print(f"[RecallerV2] {message}")

    def _embed_query(self, query: str) -> Tuple[List[float], Dict[int, float]]:
        """Query编码（与存储时BGE-M3逻辑完全一致：Dense+Sparse向量）"""
        self.embedding_model.eval()
        inputs = self.embedding_tokenizer(
            query,
            padding=True,
            truncation=True,
            max_length=1024,
            return_tensors='pt'
        ).to(self.device)

        with torch.no_grad():
            outputs = self.embedding_model(**inputs, output_hidden_states=True, return_dict=True)
            
            # 1. Dense向量（最后一层CLS token + L2归一化）
            dense_vec = outputs.hidden_states[-1][:, 0, :]
            dense_vec = F.normalize(dense_vec, p=2, dim=1)
            dense_embedding = dense_vec.float().cpu().tolist()[0]
            
            # 2. Sparse向量（logits→relu→过滤特殊Token→top-k筛选）
            logits = outputs.logits
            weights = torch.relu(logits)[0]  # 单Query取第0维
            weights[:4] = 0.0  # MASK CLS/PAD/SEP/UNK特殊Token
            
            # 取top10%或最多20个高权重Token（与存储逻辑一致）
            top_k = min(20, int(weights.shape[0] * 0.1))
            top_vals, top_indices = torch.topk(weights, top_k, largest=True)
            
            # 过滤低权重（阈值0.05）
            mask = top_vals > 0.05
            if mask.any():
                indices = top_indices[mask].tolist()
                values = top_vals[mask].tolist()
                sparse_embedding = dict(zip(indices, values))
            else:
                sparse_embedding = {int(top_indices[0].item()): float(top_vals[0].item())}

        return dense_embedding, sparse_embedding

    def _search_child_blocks(self, query_dense: List[float], query_sparse: Dict[int, float], battery_type_filter: str = None) -> List[Dict]:
        """第一步：检索高相似度子块（block_type=child）
        
        参数：
            battery_type_filter: 电池类型过滤（可选，None表示不过滤）
        """
        self._log(f"检索子块：top_k={self.child_top_k}，最小相似度={self.min_similarity}")
        
        # Milvus混合检索（Dense+Sparse，与存储时索引类型匹配）
        expr = "block_type == 'child'"  # 仅检索子块
        
        # 【新增】按电池类型过滤（如果指定了过滤类型且不是'other'）
        if battery_type_filter and battery_type_filter != 'other':
            expr += f" and battery_type == '{battery_type_filter}'"
            self._log(f"应用电池类型过滤：{battery_type_filter}")
        
        search_params = {
            "data": [query_dense],
            "anns_field": "embedding",
            "param": {"metric_type": "IP", "ef": 300},  # IP相似度（与存储一致）
            "limit": self.child_top_k,
            "expr": expr,
            "sparse_anns_field": "sparse_embedding",
            "sparse_data": [query_sparse]
        }

        results = self.milvus_collection.search(**search_params)
        valid_child_blocks = []
        
        # 过滤低相似度子块，保留父块ID关联信息
        for hit in results[0]:
            similarity = hit.score
            if similarity >= self.min_similarity:
                valid_child_blocks.append({
                    "child_id": hit.entity.id,
                    "parent_block_id": hit.entity.parent_block_id,
                    "similarity": similarity,
                    "doc_id": hit.entity.doc_id,
                    "original_filename": hit.entity.original_filename
                })
        
        self._log(f"有效子块数量：{len(valid_child_blocks)}（原始召回{len(results[0])}个）")
        return valid_child_blocks

    def _get_unique_parent_ids(self, child_blocks: List[Dict]) -> Dict[int, float]:
        """【改进】从子块中提取不重复的有效父块ID与最大相似度
        
        返回: {parent_id: max_child_sim} 字典
        """
        parent_sims = {}
        for child in child_blocks:
            p_id = child["parent_block_id"]
            if p_id != -1:
                sim = child["similarity"]
                if p_id not in parent_sims:
                    parent_sims[p_id] = sim
                else:
                    parent_sims[p_id] = max(parent_sims[p_id], sim)
        self._log(f"提取到不重复父块ID：{len(parent_sims)}个（带体池相似度）")
        return parent_sims

    def _search_parent_blocks(self, parent_sims: Dict[int, float], query_dense: List[float]) -> List[Dict]:
        """第二步：根据父块ID检索对应的父块（block_type=parent）"""
        if not parent_sims:
            self._log("无有效父块ID，跳过父块检索")
            return []
        
        self._log(f"检索父块：ID数量={len(parent_sims)}")
        parent_id_list = list(parent_sims.keys())
        expr = f"block_type == 'parent' and id in {parent_id_list}"  # 精准过滤父块
        
        # 父块检索（按向量相似度排序）
        search_params = {
            "data": [query_dense],
            "anns_field": "embedding",
            "param": {"metric_type": "IP", "ef": 100},
            "limit": len(parent_id_list),
            "expr": expr
        }

        results = self.milvus_collection.search(**search_params)
        parent_blocks = []
        
        for hit in results[0]:
            parent_id = hit.entity.id
            max_child_sim = parent_sims.get(parent_id, 0.0)  # 从序号常数中获取
            
            parent_blocks.append({
                "parent_id": parent_id,
                "content": hit.entity.content,
                "battery_type": hit.entity.battery_type,
                "doc_id": hit.entity.doc_id,
                "original_filename": hit.entity.original_filename,
                "vector_similarity": hit.score,  # 父块与Query的向量相似度
                "max_child_similarity": max_child_sim  # 子块最大相似度
            })
        
        self._log(f"成功检索父块：{len(parent_blocks)}个")
        return parent_blocks

    def _rerank_parent_blocks(self, query: str, parent_blocks: List[Dict]) -> List[Dict]:
        """第三步：Reranker二次精排（语义匹配度排序）"""
        if not self.reranker_model or not self.reranker_tokenizer:
            self._log("未加载Reranker，按向量相似度加权排序")
            # 降级逻辑：子块最大相似度（0.7）+ 父块向量相似度（0.3）
            return sorted(
                parent_blocks,
                key=lambda x: 0.7 * x["max_child_similarity"] + 0.3 * x["vector_similarity"],
                reverse=True
            )
        
        self._log("开始Reranker精排父块")
        # 构建Query-父块文本对
        pairs = [[query, block["content"]] for block in parent_blocks]
        inputs = self.reranker_tokenizer(
            pairs,
            padding=True,
            truncation=True,
            max_length=1024,
            return_tensors="pt"
        ).to(self.device)

        # 计算精排分数（sigmoid归一化到[0,1]）
        self.reranker_model.eval()
        with torch.no_grad():
            outputs = self.reranker_model(**inputs)
            scores = torch.sigmoid(outputs.logits).cpu().numpy().flatten()

        # 为父块添加精排分数并排序
        for idx, block in enumerate(parent_blocks):
            block["rerank_score"] = float(scores[idx])
        
        reranked_blocks = sorted(parent_blocks, key=lambda x: x["rerank_score"], reverse=True)
        
        # 调试输出Top5分数
        if self.debug:
            top_scores = ", ".join([f"{b['rerank_score']:.3f}" for b in reranked_blocks[:5]])
            self._log(f"Top5父块精排分数：{top_scores}")
        
        return reranked_blocks

    def recall_parent_blocks(self, query: str, top_k: int = 5, use_reranker: bool = True, battery_type_filter: str = None) -> Tuple[List[Dict], Dict[str, List[int]]]:
        """主召回流程：子块→父块→精排
        
        参数：
            battery_type_filter: 电池类型过滤（可选，None表示不过滤）
        """
        self._log("="*50)
        self._log(f"召回流程启动：query={query}")
        
        # 1. Query编码
        query_dense, query_sparse = self._embed_query(query)
        self._log("Query编码完成（Dense+Sparse向量）")
        
        # 2. 检索子块（【新增】支持电池类型过滤）
        self.child_blocks = self._search_child_blocks(query_dense, query_sparse, battery_type_filter=battery_type_filter)
        if not self.child_blocks:
            self._log("未检索到有效子块")
            return [], {}
        
        # 3. 提取唯一父块ID
        parent_sims = self._get_unique_parent_ids(self.child_blocks)
        if not parent_sims:
            self._log("无有效父块ID")
            return [], {}
        
        # 4. 检索父块
        parent_blocks = self._search_parent_blocks(parent_sims, query_dense)
        if not parent_blocks:
            self._log("未检索到对应父块")
            return [], {}
        
        # 5. 二次精排
        if use_reranker:
            parent_blocks = self._rerank_parent_blocks(query, parent_blocks)
        
        # 6. 截取Top-K父块
        final_blocks = parent_blocks[:top_k]
        self._log(f"最终返回父块：{len(final_blocks)}个（请求top_k={top_k}）")
        
        # 7. 构建父子块关联索引（用于来源展示）
        block_indices = {}
        for block in final_blocks:
            p_id = str(block["parent_id"])
            block_indices[p_id] = [c["child_id"] for c in self.child_blocks if c["parent_block_id"] == block["parent_id"]]
        
        self._log("召回流程完成")
        return final_blocks, block_indices

# ==============================================================================
# RAG问答系统 V2（整合召回+回答，保留原有领域判断、大模型交互）
# ==============================================================================
class RAGQAV2:
    def __init__(self, 
                 embedding_model, 
                 embedding_tokenizer, 
                 milvus_collection: Collection,
                 reranker_model=None,
                 reranker_tokenizer=None,
                 api_key: str = None,
                 debug: bool = False,
                 document_titles: Dict[str, str] = None):
        self.debug = debug
        self.api_key = api_key or __import__("os").environ.get("MOONSHOT_API_KEY", "")
        self.document_titles = document_titles or {}
        
        print("正在初始化RAG问答系统 V2...")
        
        # 初始化召回器（核心依赖）
        self.recaller = DocumentRecallerV2(
            embedding_model=embedding_model,
            embedding_tokenizer=embedding_tokenizer,
            milvus_collection=milvus_collection,
            reranker_model=reranker_model,
            reranker_tokenizer=reranker_tokenizer,
            min_similarity=0.3,
            child_top_k=200,
            debug=debug
        )
        
        print("✓ RAG问答系统 V2 初始化完成")
    
    def _log(self, message: str):
        if self.debug:
            print(f"[RAGQA] {message}")
    
    def is_domain_related(self, query: str) -> Dict:
        """【改进】领域相关性判断：使用class_query.identify_battery_type()进行问题识别
        
        规则：
        - 如果identify_battery_type()返回 'other'，说明不是领域问题
        - 否则返回相关领域问题
        """
        from class_query import identify_battery_type
        
        battery_type = identify_battery_type(query, debug=False)
        
        # 如果识别到电池类型（非'other'），说明是领域问题
        is_related = (battery_type != 'other')
        
        reasoning = f"【类型识别】识别到电池类型: {battery_type}" if is_related else "【类型识别】问题不属于液流电池领域"
        
        return {
            "is_related": is_related,
            "reasoning": reasoning,
            "battery_type": battery_type,
            "success": True
        }
    
    def answer_query(self, query: str, top_k: int = 30) -> Dict:
        """【改进】主问答流程：电池类型识别→启发式域判断→召回→大模型生成答案
        
        【修改】召回父块数量改为30个（从5个提升到30个，获取更多相关信息）
        """
        print(f"\n===== 处理查询: {query} =====")
        
        # 【新增】步骤1：电池类型识别（支持中英文）
        print(f"\n【步骤1】电池类型识别...")
        detected_battery_type = identify_battery_type(query)
        self._log(f"检测到电池类型: {detected_battery_type}")
        
        # 步骤2：领域相关性判断（使用class_query.identify_battery_type()）
        print(f"\n【步骤2】领域相关性判断（使用识别引擎）...")
        # 【改进】直接使用is_domain_related()，内部已使用identify_battery_type()
        domain_check = self.is_domain_related(query)
        is_related = domain_check['is_related']
        reasoning = domain_check['reasoning']
        print(f"判断结果: {reasoning}")
        
        # 不相关问题直接调用大模型回答
        if not is_related:
            print(f"\n【步骤3】非领域问题，直接生成答案...")
            answer = self._generate_general_answer(query)
            return {
                "answer": answer,
                "parent_blocks": [],
                "battery_type": detected_battery_type,  # 【新增】返回识别的电池类型
                "confidence": 0.6,
                "is_domain_related": False,
                "reasoning": reasoning
            }
        
        # 步骤3：RAG召回（子块→父块→精排，【新增】按电池类型过滤）
        print(f"\n【步骤3】领域相关，启动RAG检索...")
        # 【重要】recall_parent_blocks 返回 Tuple[List[Dict], Dict[str, List[int]]]
        # 第一个元素：父块列表
        # 第二个元素：块索引映射 {parent_id: [child_ids]}
        result = self.recaller.recall_parent_blocks(
            query, top_k=top_k, use_reranker=True, battery_type_filter=detected_battery_type
        )  # 【使用方法参数top_k】现在默认为30
        
        # 【防御性编程】判断返回值是否为tuple（新版本）还是list（旧版本）
        if isinstance(result, tuple) and len(result) == 2:
            parent_blocks, block_indices = result
        elif isinstance(result, list):
            # 降级处理：如果返回的是列表，直接使用
            parent_blocks = result
            block_indices = {}
        else:
            parent_blocks = []
            block_indices = {}
        
        if not parent_blocks:
            print("未检索到相关父块")
            return {
                "answer": "抱歉，未能在文献中找到与您问题相关的内容。",
                "parent_blocks": [],
                "battery_type": detected_battery_type,  # 【新增】返回识别的电池类型
                "confidence": 0.1,
                "is_domain_related": True,
                "reasoning": reasoning
            }
        
        # 调试输出召回详情
        if self.debug:
            print(f"\n【召回详情】")
            for i, block in enumerate(parent_blocks, 1):
                print(f"  {i}. 父块ID={block['parent_id']} | 向量分={block['vector_similarity']:.4f} | "
                      f"子块最高分={block['max_child_similarity']:.4f} | Rerank分={block.get('rerank_score', 'N/A')}")
        
        # 步骤4：大模型生成答案（带来源标注）
        print(f"\n【步骤4】调用大模型生成答案...")
        answer = self._generate_answer_with_llm(query, parent_blocks, block_indices)
        
        return {
            "answer": answer,
            "parent_blocks": parent_blocks,
            "battery_type": detected_battery_type,  # 【新增】返回识别的电池类型
            "confidence": 0.85,
            "is_domain_related": True,
            "reasoning": reasoning
        }
    
    def _generate_answer_with_llm(self, query: str, parent_blocks: List[Dict], block_indices: Dict[str, List[int]]) -> str:
        """用Kimi大模型生成答案（含相关内容引用+文献来源）"""
        # 组织检索上下文
        context_parts = []
        for i, block in enumerate(parent_blocks, 1):
            rerank_info = f"(相关度: {block['rerank_score']:.2f})" if 'rerank_score' in block else ""
            context_parts.append(f"""【相关内容 {i}】{rerank_info}
父块ID: {block['parent_id']}
{block['content']}""")
        
        context = "\n\n".join(context_parts)
        prompt = f"""你是液流电池和化工领域的知识专家。用户提出了一个问题，我为你提供了从相关文献中检索到的内容块（已按相关度排序）。
【检索到的相关内容】
{context}
【用户问题】
{query}
【回答要求】
1. 优先参考相关度高的内容块，引用时必须明确标注“【相关内容 X】”（X为序号）
   示例：**电解液稳定性提升**：【相关内容 1】提到，添加0.1mol/L的Ce³⁺离子可抑制钒离子的歧化反应，延长电解液循环寿命。
2. 严格基于检索内容回答，不得编造文献中没有的信息
3. 若检索内容无相关信息，直接说明“未检索到相关文献支持该问题的答案”
4. 保持专业学术风格，逻辑清晰、表述准确
"""
        
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        data = {
            "model": "kimi-k2.6",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 1.0,
            "max_tokens": 1500
        }
        
        try:
            response = requests.post("https://api.moonshot.cn/v1/chat/completions", headers=headers, json=data, timeout=30)
            if response.status_code == 200:
                answer = response.json()['choices'][0]['message']['content'].strip()
                # 拼接文献来源
                return self._append_sources_to_answer(answer, parent_blocks)
            else:
                return f"大模型调用失败，错误代码: {response.status_code}"
        except Exception as e:
            return f"答案生成失败：{str(e)}"
    
    def _append_sources_to_answer(self, answer: str, parent_blocks: List[Dict]) -> str:
        """为答案添加文献来源标注"""
        if not parent_blocks:
            return answer
        
        # 按文献标题分组（同一文献的多个父块合并）
        source_map = {}
        for i, block in enumerate(parent_blocks, 1):
            title = block.get('original_filename', '未知文献')
            if title not in source_map:
                source_map[title] = []
            source_map[title].append(i)
        
        # 构建来源section
        sources_section = "\n\n——— 文献来源 ———"
        for title, indices in sorted(source_map.items()):
            idx_str = "、".join(map(str, indices))
            sources_section += f"\n【相关内容 {idx_str}】来源于：{title}"
        
        return answer + sources_section
    
    def _generate_general_answer(self, query: str) -> str:
        """非领域问题的通用回答"""
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        data = {
            "model": "kimi-k2.6",
            "messages": [
                {"role": "system", "content": "你是通用助手，简洁回答非液流电池/化工领域的问题，或告知超出专业范围"},
                {"role": "user", "content": query}
            ],
            "temperature": 1.0,
            "max_tokens": 500
        }
        
        try:
            response = requests.post("https://api.moonshot.cn/v1/chat/completions", headers=headers, json=data, timeout=200)
            if response.status_code == 200:
                answer = response.json()['choices'][0]['message']['content'].strip()
                return f"【提示：该问题不属于液流电池/化工领域】\n\n{answer}"
            else:
                return "抱歉，该问题超出本系统的专业范围。"
        except Exception as e:
            return f"处理失败：{str(e)}"
