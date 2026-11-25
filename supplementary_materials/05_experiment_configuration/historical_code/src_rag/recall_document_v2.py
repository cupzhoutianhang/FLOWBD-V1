"""
文档检索和召回模块 V2 - 集成Reranker二次精排
改进内容：
1. 集成BGE-Reranker进行二次精排
2. 增加检索冗余度（5倍）
3. 父块得分聚合策略
4. 相似度阈值过滤
5. 详细的调试日志
6. 问题类型识别升级 - 支持40+种电池类型
"""
import os
import sys
from typing import List, Dict, Tuple, Optional
from collections import defaultdict
import numpy as np
import struct
from class_query import identify_battery_type

class DocumentRecallerV2:
    """
    文档检索和召回系统 V2 - 带Reranker精排
    
    检索流程：
    1. Query嵌入 → 向量检索子块
    2. 子块映射到父块 + 得分聚合
    3. Reranker对父块二次精排
    4. 返回Top-K父块
    """
    
    def __init__(self, 
                 embedding_model, 
                 embedding_tokenizer, 
                 milvus_collection=None,
                 reranker_model=None, 
                 reranker_tokenizer=None,
                 min_similarity: float = 0.3,
                 debug: bool = False):
        """
        初始化文档召回器 V2
        
        Args:
            embedding_model: BGE-M3嵌入模型
            embedding_tokenizer: BGE-M3分词器
            milvus_collection: Milvus集合
            reranker_model: BGE-Reranker模型
            reranker_tokenizer: BGE-Reranker分词器
            min_similarity: 最小相似度阈值
            debug: 是否输出调试信息
        """
        self.embedding_model = embedding_model
        self.embedding_tokenizer = embedding_tokenizer
        self.milvus_collection = milvus_collection
        self.reranker_model = reranker_model
        self.reranker_tokenizer = reranker_tokenizer
        self.min_similarity = min_similarity
        self.debug = debug
        
        # 检查Reranker是否可用
        self.reranker_available = (
            self.reranker_model is not None and 
            self.reranker_tokenizer is not None
        )
        
        if self.reranker_available:
            pass
        else:
            pass
    
    def _analyze_error(self, error: Exception) -> str:
        """分析错误原因（为降级提供线索）"""
        error_msg = str(error)
        if "required argument is not a float" in error_msg:
            return "稀疏或稠密向量中包含非浮点数类型的数据"
        elif "struct.error" in error_msg:
            return "向量结构打包失败"
        elif "Unexpected error" in error_msg:
            return "Milvus数据库内部异常（可能是存储的向量教据已损毅）"
        else:
            return f"未知错误：{error_msg[:100]}"
    
    def _log(self, message: str):
        """输出调试日志"""
        if self.debug:
            print(f"[DEBUG] {message}")
    
    def _diagnose_sparse_vector(self, sparse_dict: dict) -> str:
        """
        诊断Sparse向量的格式问题
        
        返回诊断结果字符串
        """
        if not sparse_dict:
            return "⚠️  Sparse向量为空"
        
        issues = []
        
        # 检查key的类型
        sample_keys = list(sparse_dict.keys())[:3]
        key_types = [type(k).__name__ for k in sample_keys]
        if 'str' in key_types:
            issues.append(f"❌ Key是字符串: {key_types}（应该是int）")
        elif 'int' not in key_types:
            issues.append(f"⚠️  Key类型非int: {set(key_types)}")
        
        # 检查value的类型  
        sample_vals = list(sparse_dict.values())[:3]
        val_types = [type(v).__name__ for v in sample_vals]
        if 'float' not in val_types:
            issues.append(f"❌ Value类型: {set(val_types)}（应该是float）")
        
        # 检查数值范围
        if sample_vals:
            max_val = max(sparse_dict.values())
            min_val = min(sparse_dict.values())
            if max_val > 1000:
                issues.append(f"⚠️  Value过大: max={max_val:.2f}（应该<50）")
        
        if issues:
            return " | ".join(issues)
        else:
            return "✅ Sparse向量格式正常"
    

    def _detect_question_battery_type(self, query: str) -> str:
        """
        根据问题判断液流电池类型 - 升级版（【修复】返回单个字符串而非列表）
        
        支持：
        1. 中英文混合识别
        2. 多种电池类型识别（返回优先度最高的类型）
        3. 调用 class_query.py 中的规则引擎识别40+种类型
        
        Args:
            query: 用户问题（可能包含中文、英文或混合）
            
        Returns:
            str: 识别到的电池类型字符串，无法识别则返回 'other'
                示例: 'vanadium', 'zinc_bromine', 'iron_chromium'
        """
        if not query or not isinstance(query, str):
            return 'other'
        
        detected_types = []
        
        # 【策略1】使用 class_query.py 的规则引擎识别
        # 先对原始问题尝试识别
        battery_type = identify_battery_type(query)
        if battery_type and battery_type != 'other':
            detected_types.append(battery_type)
            self._log(f"问题类型识别(规则1-原始): {battery_type}")
        
        # 【策略2】对问题的关键词部分单独识别
        # 提取可能是电池类型的关键词短语
        import re
        
        # 中英文混合提取可能的电池类型短语
        # 模式："XXX液流电池" 或 "XXX flow battery" 或 "XXX batteries"
        patterns = [
            r'[\w-]+液流电池',  # 中文
            r'[\w-]+\s*flow\s*batter(?:y|ies)',  # 英文flow battery
            r'[\w-]+\s*redox\s*flow\s*batter(?:y|ies)',  # 英文redox flow battery
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, query, re.IGNORECASE)
            for match in matches:
                # 对每个匹配的短语单独识别
                phrase_type = identify_battery_type(match)
                if phrase_type and phrase_type != 'other' and phrase_type not in detected_types:
                    detected_types.append(phrase_type)
                    self._log(f"问题类型识别(规则2-短语): {phrase_type} (from '{match}')")
        
        # 【策略3】分句识别（处理多个电池类型的问题）
        # 使用中文句号或英文句号分割
        sentences = re.split(r'[。,，;；]', query)
        for sentence in sentences:
            if len(sentence.strip()) < 3:  # 跳过太短的句子
                continue
            
            sent_type = identify_battery_type(sentence)
            if sent_type and sent_type != 'other' and sent_type not in detected_types:
                detected_types.append(sent_type)
                self._log(f"问题类型识别(规则3-分句): {sent_type} (from '{sentence[:20]}...')")
        
        # 如果没有识别到任何类型，返回 'other'
        if not detected_types:
            self._log("问题类型识别: 未识别到特定电池类型，将进行全局搜索")
            return 'other'
        
        # 去重并取第一个（优先度最高）的类型
        detected_types = list(dict.fromkeys(detected_types))  # 保持顺序的去重
        primary_type = detected_types[0]  # 【修复】取第一个识别到的类型
        self._log(f"问题识别类型列表: {detected_types} → 优先使用: {primary_type}")
        return primary_type
    
    def _embed_query(self, query: str) -> np.ndarray:
        """对query进行稠密向量嵌入，返回np.float32类型的ndarray"""
        if self.embedding_model is None or self.embedding_tokenizer is None:
            raise ValueError("嵌入模型未初始化")
        
        inputs = self.embedding_tokenizer(
            [query],
            padding=True,
            truncation=True,
            return_tensors="pt",
            max_length=512
        )
        
        import torch
        with torch.no_grad():
            outputs = self.embedding_model(**inputs)
            query_embedding = outputs.last_hidden_state[:, 0, :].cpu().numpy()[0]
        
        # 确保向量类型为float32，处理NaN/无穷值
        query_embedding = query_embedding.astype(np.float32)
        query_embedding = np.nan_to_num(query_embedding, nan=0.0, posinf=0.0, neginf=0.0)
        
        # 验证向量有效性
        if not isinstance(query_embedding, np.ndarray) or query_embedding.dtype != np.float32:
            raise ValueError(f"嵌入结果类型错误，需为np.float32的ndarray，实际为{type(query_embedding)}:{query_embedding.dtype}")
        if query_embedding.ndim != 1:
            raise ValueError(f"嵌入结果维度错误，需为1D向量，实际为{query_embedding.ndim}D")
        
        return query_embedding
    
    def _embed_query_sparse(self, query: str) -> dict:
        """对query进行稀疏向量嵌入"""
        sparse_embedding = self._generate_sparse_embedding(query)
        
        # 确保稀疏向量格式正确
        if 'indices' not in sparse_embedding or 'data' not in sparse_embedding:
            raise ValueError(f"稀疏向量格式不正确: {sparse_embedding}")
        
        # 【关键修复】确保indices和data中的值都是原生Python类型
        clean_indices = []
        clean_data = []
        
        for idx, val in zip(sparse_embedding['indices'], sparse_embedding['data']):
            # 强制转换为Python int和float
            try:
                idx_int = int(idx) if isinstance(idx, (int, float, np.integer)) else None
                val_float = float(val) if isinstance(val, (int, float, np.number)) else None
                
                # 双重验证类型
                if idx_int is not None and val_float is not None and isinstance(idx_int, int) and isinstance(val_float, float):
                    if np.isfinite(val_float):
                        clean_indices.append(idx_int)
                        clean_data.append(val_float)
            except (TypeError, ValueError):
                pass  # 跳过无法转换的项
        
        sparse_embedding['indices'] = clean_indices
        sparse_embedding['data'] = clean_data
        
        return sparse_embedding
    
    def _rerank_with_scores(self, query: str, parent_blocks: List[Dict]) -> List[Tuple[Dict, float]]:
        """
        使用Reranker对父块进行重排序，返回带分数的结果
        
        Args:
            query: 用户查询
            parent_blocks: 候选父块列表
            
        Returns:
            List[Tuple[Dict, float]]: (父块, reranker分数) 列表，按分数降序
        """
        if not self.reranker_available or not parent_blocks:
            # 没有Reranker，使用原始相似度分数
            return [(block, block.get('max_similarity', 0)) for block in parent_blocks]
        
        import torch
        
        self._log(f"Reranker精排: {len(parent_blocks)} 个候选父块")
        
        # 构建查询-文档对
        pairs = []
        for block in parent_blocks:
            content = block.get('content', '')
            # 截断过长的内容
            if len(content) > 1000:
                content = content[:1000]
            pairs.append([query, content])
        
        # 批量编码和计算分数
        try:
            inputs = self.reranker_tokenizer(
                pairs,
                padding=True,
                truncation=True,
                return_tensors="pt",
                max_length=512
            )
            
            with torch.no_grad():
                outputs = self.reranker_model(**inputs)
                scores = outputs.logits.squeeze(-1)
                
                # 处理单个结果的情况
                if scores.dim() == 0:
                    scores = scores.unsqueeze(0)
                
                scores = scores.cpu().numpy()
            
            # 组合结果并排序
            results = list(zip(parent_blocks, scores.tolist()))
            results.sort(key=lambda x: x[1], reverse=True)
            
            self._log(f"Reranker分数范围: [{min(scores):.4f}, {max(scores):.4f}]")
            
            return results
            
        except Exception as e:
            print(f"Reranker处理出错: {e}")
            # 出错时回退到原始排序
            return [(block, block.get('max_similarity', 0)) for block in parent_blocks]
    
    def recall_parent_blocks(self, query: str, top_k: int = 20, 
                             use_reranker: bool = True, use_hybrid_search: bool = True,
                             battery_type_filter: Optional[str] = None) -> List[Dict]:
        """
        基于查询召回相关的父块 - V2改进版
        
        【优化】强制启用混合检索（Dense + Sparse），确保稀疏向量参与检索
        这可以防止Dense向量的"语义越界"问题（如将"锌电池"误判为"铁铬电池"）
        
        【新增】根据问题类型过滤电池类型
        【修复】默认top_k从5改为20，确保返回20个父块
        【最新】如果hybrid_search失败，自动降级到dense_search
        【修复】battery_type_filter改为str类型（而非List[str]），与上游调用保持一致
        
        Args:
            query: 用户查询
            top_k: 返回最相关的前k个父块 (默认20)
            use_reranker: 是否使用Reranker进行重排序
            use_hybrid_search: 是否使用混合检索 (Dense + Sparse) [已强制启用，此参数保留向后兼容]
            battery_type_filter: 【修复】电池类型过滤字符串（单个类型，如'vanadium'；如提供则优先使用，否则内部识别）
            
        Returns:
            List[Dict]: 父块列表（已按RRF融合分数排序），包含battery_type和original_filename字段
        """
        # 【改进】如果未提供battery_type_filter，则内部识别
        if battery_type_filter is None:
            question_battery_type = self._detect_question_battery_type(query)
        else:
            question_battery_type = battery_type_filter
        
        # 【新增】在终端打印识别到的电池类型
        if question_battery_type and question_battery_type != 'other':
            print(f"\n✅ 【问题类型识别】识别到的电池类型: {question_battery_type}")
        else:
            print(f"\n⚠️  【问题类型识别】未识别到特定电池类型，将进行全局搜索")
        
        # 【最新修复】先尝试混合检索，如果失败则降级到Dense检索
        # print(f"\n\n🔍 【检索方案】尝试混合检索（Dense + Sparse）...")
        try:
            result = self._hybrid_search(query, top_k, use_reranker, question_battery_type)
            if result and len(result) > 0:
                return result
            else:
                print(f"\n⚠️  【混合检索】未返回结果，降级到纯Dense检索")
        except Exception as e:
            print(f"\n⚠️  【混合检索失败】{type(e).__name__}: {str(e)[:200]}")
            print(f"   原因分析：{self._analyze_error(e)}")
            print(f"   【降级方案】切换到纯Dense检索...")
        
        # 降级到纯Dense检索
        print(f"\n🔍 【检索方案】尝试纯Dense检索...")
        return self._dense_search(query, top_k, use_reranker, question_battery_type)
    
    def _dense_search(self, query: str, top_k: int, use_reranker: bool = True, 
                     battery_type_filter: Optional[str] = None) -> List[Dict]:
        """
        纯稠密向量检索（降级处理用）
        
        【修改】移除此方法中的Reranker精排逻辑
        - _dense_search 仅负责向量检索和子块聚合
        - 返回候选父块而非最终结果
        - 最终精排由 _hybrid_search 统一负责
        
        Args:
            battery_type_filter: 可选的电池类型过滤条件
        """
        self._log(f"开始检索: {query}")
        
        # 步骤1: Query嵌入（直接使用np.float32的ndarray）
        query_embedding = self._embed_query(query)
        
        if self.milvus_collection is None:
            print("⚠️  Milvus集合未初始化，无法进行文档检索")
            print("   请确保:")
            print("   1. Milvus服务正在运行 (默认端口: 19530)")
            print("   2. 集合 'traditional_rag_collection_v5' 已创建")
            print("   3. 集合中包含有效的文档数据")
            return []
        
        # 步骤2: 向量检索子块
        # 【改进】增加检索数量到5倍冗余
        search_limit = top_k * 5
        
        # 【改进】动态计算ef参数，确保 ef >= search_limit
        # ef参数是Milvus HNSW索引的搜索宽度，必须 >= limit（要检索的数量）
        ef_value = max(search_limit, 800)  # 至少800，确保足够的搜索范围
        search_params = {"metric_type": "IP", "params": {"ef": ef_value}}
        
        # 构建过滤表达式（CHUneng集合无battery_type字段，仅按block_type过滤）
        expr = "block_type == 'child'"
        print(f"\n🔍 【Dense检索过滤】全局检索所有类型")
        
        self._log(f"\n【Milvus搜索调试】")
        self._log(f"  top_k: {top_k}")
        self._log(f"  search_limit: {search_limit} (= top_k * 5)")
        self._log(f"  ef参数: {ef_value} (确保 >= search_limit)")
        self._log(f"  搜索参数: {search_params}")
        self._log(f"  向量类型: {type(query_embedding)}, 维度: {query_embedding.shape[0]}, dtype: {query_embedding.dtype}")
        
        try:
            child_results = self.milvus_collection.search(
                data=[query_embedding],  # 直接传入np.float32的ndarray
                anns_field="embedding",
                param=search_params,
                limit=search_limit,
                expr=expr,
                output_fields=["id", "parent_block_id", "child_block_id", "doc_id", "content", "original_filename"]
            )
            self._log(f"  搜索完成，返回结果数: {len(child_results)}")
        except Exception as e:
            print(f"⚠️  Milvus检索出错: {e}")
            print(f"   异常详情: {type(e).__name__}")
            self._log(f"Milvus搜索异常: {e}")
            return []
        
        # 收集子块结果
        candidates = []
        for hits in child_results:
            for hit in hits:
                candidates.append({
                    'child_id': hit.entity.get('id'),
                    'parent_id': hit.entity.get('parent_block_id'),
                    'doc_id': hit.entity.get('doc_id'),
                    'child_content': hit.entity.get('content'),
                    'battery_type': hit.entity.get('battery_type', 'unknown'),
                    'original_filename': hit.entity.get('original_filename', 'unknown'),
                    'similarity_score': hit.distance
                })
        
        if not candidates:
            return []
        
        # 步骤3: 子块聚合到父块
        # 【关键修复】将子块按parent_id分组，然后查询Milvus获取真实的父块内容（1500字符）
        # 原因：之前直接返回子块content（500字符），导致rag.json中数据是不完整的
        
        # 先对所有候选按相似度排序
        candidates_sorted = sorted(candidates, key=lambda x: x['similarity_score'], reverse=True)
        
        # 步骤3.1: 子块聚合到父块
        parent_scores = {}
        parent_doc_ids = {}
        parent_filenames = {}
        parent_battery_types = {}
        
        for c in candidates_sorted:
            parent_id = c['parent_id']
            if parent_id not in parent_scores:
                parent_scores[parent_id] = []
                parent_doc_ids[parent_id] = c['doc_id']
                parent_filenames[parent_id] = c.get('original_filename', 'unknown')
                parent_battery_types[parent_id] = c.get('battery_type', 'unknown')
            parent_scores[parent_id].append(c['similarity_score'])
        
        # 按最高子块相似度排序
        ranked_parents = sorted(
            parent_scores.items(),
            key=lambda x: max(x[1]),
            reverse=True
        )
        
        # 选择Top-K*5个父块ID（留给后续处理）
        rerank_parent_ids = [pid for pid, _ in ranked_parents[:min(top_k * 5, len(ranked_parents))]]
        
        # 步骤3.2: 从Milvus查询这些父块的真实内容
        # 【关键】直接查询block_type=='parent'的父块，获取完整的1500字符内容
        parent_blocks = []
        if rerank_parent_ids:
            try:
                # 构建查询表达式：查询这些特定parent_id对应的父块
                parent_filter = f"block_type == 'parent' and id in {rerank_parent_ids}"
                parent_results = self.milvus_collection.query(
                    expr=parent_filter,
                    output_fields=["id", "content", "original_filename", "doc_id"],
                    limit=len(rerank_parent_ids)
                )
                
                # 构建父块ID到内容的映射
                parent_content_map = {p['id']: p['content'] for p in parent_results}
                parent_filename_map = {p['id']: p.get('original_filename', 'unknown') for p in parent_results}
                parent_doc_map = {p['id']: p.get('doc_id', 'unknown') for p in parent_results}
                parent_battery_map = {p['id']: p.get('battery_type', 'unknown') for p in parent_results}
                
                # 构建最终的父块结果
                for parent_id, scores in ranked_parents:
                    if parent_id in parent_content_map:
                        parent_blocks.append({
                            'parent_id': parent_id,
                            'content': parent_content_map[parent_id],  # 【修复】使用真实的1500字符父块内容
                            'doc_id': parent_doc_map.get(parent_id, parent_doc_ids.get(parent_id, 'unknown')),
                            'original_filename': parent_filename_map.get(parent_id, parent_filenames.get(parent_id, 'unknown')),
                            'battery_type': parent_battery_map.get(parent_id, parent_battery_types.get(parent_id, 'unknown')),
                            'max_similarity': max(scores),
                            'avg_similarity': sum(scores) / len(scores) if scores else 0,
                            'hit_count': len(scores)
                        })
                        if len(parent_blocks) >= top_k * 5:
                            break
            except Exception as e:
                self._log(f"查询父块内容失败: {e}")
                # 降级处理：如果查询失败，返回子块作为fallback
                for parent_id, scores in ranked_parents[:top_k * 5]:
                    c = next((x for x in candidates_sorted if x['parent_id'] == parent_id), None)
                    if c:
                        parent_blocks.append({
                            'parent_id': parent_id,
                            'content': c['child_content'],  # 降级：使用子块内容
                            'doc_id': parent_doc_ids.get(parent_id, 'unknown'),
                            'original_filename': parent_filenames.get(parent_id, 'unknown'),
                            'battery_type': parent_battery_types.get(parent_id, 'unknown'),
                            'max_similarity': max(scores),
                            'avg_similarity': sum(scores) / len(scores) if scores else 0,
                            'hit_count': len(scores)
                        })
        
        # 步骤4: 相似度阈值过滤
        filtered_parents = parent_blocks  # 【修改】直接使用构建好的parent_blocks，跳过parent_id去重逻辑
        
        if len(filtered_parents) < len(parent_blocks):
            self._log(f"过滤后: {len(parent_blocks)} -> {len(filtered_parents)}")
        
        # 【改进】保留全部块用于混合检索阶段处理
        rerank_count = min(top_k * 5, len(parent_blocks))  # 保留5倍作为候选
        parent_blocks_for_rerank = parent_blocks[:rerank_count]
        self._log(f"【候选块】选择 {len(parent_blocks_for_rerank)} 个块作为候选")
        
        if not parent_blocks_for_rerank:
            print(f"[DEBUG] ⚠️ 没有选中的块！parent_blocks={len(parent_blocks)}, top_k={top_k}")
            return []
        
        # 使用parent_blocks_for_rerank作为最终的候选
        parent_blocks = parent_blocks_for_rerank
        
        # 为块分配索引号（仅用于标识）
        for idx, block in enumerate(parent_blocks, 1):
            block['block_index'] = idx
        
        # 直接返回候选块
        return parent_blocks
    
    def _print_final_stats(self, final_results: List[Dict]):
        """
        打印最终结果的统计信息，包括电池类型分布
        """
        if not final_results:
            return
        
        # 统计电池类型分布
        battery_type_count = {}
        for block in final_results:
            btype = block.get('battery_type', 'unknown')
            battery_type_count[btype] = battery_type_count.get(btype, 0) + 1
        
        # 统计来源文献
        source_count = {}
        for block in final_results:
            source = block.get('original_filename', 'unknown')
            source_count[source] = source_count.get(source, 0) + 1
        
        # 打印统计信息
        print(f"\n📊 【最终召回统计】")
        print(f"  📌 返回块数: {len(final_results)}")
        print(f"  🔋 电池类型分布:")
        for btype, count in sorted(battery_type_count.items(), key=lambda x: x[1], reverse=True):
            print(f"     - {btype}: {count} 个")
        print(f"  📚 来源文献分布:")
        for source, count in sorted(source_count.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"     - {source}: {count} 个")
                
    def _build_block_indices(self, parent_blocks: List[Dict]) -> Dict[str, List[int]]:
        """
        构建块索引映射：按doc_id分组块的索引号
        
        Args:
            parent_blocks: 父块列表
            
        Returns:
            Dict: {doc_id: [block_indices]}
        """
        indices_map = {}
        for block in parent_blocks:
            doc_id = block.get('doc_id', '')
            block_index = block.get('block_index', 0)
            if doc_id:
                if doc_id not in indices_map:
                    indices_map[doc_id] = []
                indices_map[doc_id].append(block_index)
        return indices_map
    
    def _hybrid_search(self, query: str, top_k: int, use_reranker: bool = True, 
                      battery_type_filter: Optional[str] = None) -> List[Dict]:
        """
        混合检索：使用Milvus原生混合检索（Dense + Sparse）
        
        【核心修复】稠密向量保持np.float32的ndarray类型，不转为list
        """
        try:
            # 步骤1: 生成查询的Dense和Sparse向量
            # 稠密向量：直接使用np.float32的ndarray（_embed_query已保证类型）
            query_dense = self._embed_query(query)
            # 稀疏向量：正常生成
            query_sparse = self._embed_query_sparse(query)
            
            # 步骤2: 构建过滤表达式（CHUneng集合无battery_type字段，仅按block_type过滤）
            expr = "block_type == 'child'"
            print(f"\n🔍 【混合检索过滤】全局检索所有类型")
            
            # 步骤3: 严格验证向量格式（关键修复）
            from pymilvus import AnnSearchRequest, RRFRanker
            
            # 验证稠密向量：必须是np.float32的1D ndarray
            if not isinstance(query_dense, np.ndarray) or query_dense.dtype != np.float32:
                raise ValueError(f"稠密向量格式错误：需为np.float32的ndarray，实际为{type(query_dense)}:{query_dense.dtype}")
            if query_dense.ndim != 1:
                raise ValueError(f"稠密向量维度错误：需为1D，实际为{query_dense.ndim}D")
            if np.any(np.isnan(query_dense)) or np.any(np.isinf(query_dense)):
                raise ValueError("稠密向量包含NaN或无穷值")
            self._log(f"稠密向量验证通过：维度={query_dense.shape[0]}, dtype={query_dense.dtype}")
            
            # 验证稀疏向量 - 【超级关键】检查indices和data的类型
            if not isinstance(query_sparse, dict) or 'indices' not in query_sparse or 'data' not in query_sparse:
                raise ValueError(f"稀疏向量格式错误：{query_sparse.keys()}")
            
            # 【超级关键修复】在验证前进行诊断输出
            # print(f"\n🔍 【Sparse向量类型诊断】")
            if len(query_sparse['indices']) > 0:
                # print(f"  indices类型样本：{[type(x).__name__ for x in query_sparse['indices'][:3]]}")
                # print(f"  indices值样本：{query_sparse['indices'][:3]}")
                # print(f"  data类型样本：{[type(x).__name__ for x in query_sparse['data'][:3]]}")
                # print(f"  data值样本：{query_sparse['data'][:3]}")
                
                # 如果发现类型问题，进行即时修复
                has_type_issue = False
                for i, idx in enumerate(query_sparse['indices'][:5]):
                    if not isinstance(idx, int):
                        has_type_issue = True
                        print(f"  ⚠️  【发现】indices[{i}]不是int类型：{type(idx).__name__}={idx!r}")
                    if i < len(query_sparse['data']) and not isinstance(query_sparse['data'][i], float):
                        has_type_issue = True
                        print(f"  ⚠️  【发现】data[{i}]不是float类型：{type(query_sparse['data'][i]).__name__}={query_sparse['data'][i]!r}")
                
                if has_type_issue:
                    print(f"  【自动修复】重新清洗Sparse向量...")
                    clean_indices = []
                    clean_data = []
                    for idx, val in zip(query_sparse['indices'], query_sparse['data']):
                        try:
                            idx_int = int(idx) if isinstance(idx, (int, float, np.integer)) else None
                            val_float = float(val) if isinstance(val, (int, float, np.number)) else None
                            if idx_int is not None and val_float is not None and isinstance(idx_int, int) and isinstance(val_float, float):
                                clean_indices.append(idx_int)
                                clean_data.append(val_float)
                        except (TypeError, ValueError):
                            pass
                    query_sparse['indices'] = clean_indices
                    query_sparse['data'] = clean_data
                    print(f"  ✅ 修复完成：indices={len(clean_indices)}, data={len(clean_data)}")
            
            # 【超级关键修复】最后的安全检查
            # 注意：前面已经进行过一次诊断和修复，这里再做最后的验证
            # print(f"\n🔍 【最终Sparse向量检查】indices={len(query_sparse['indices'])}, data={len(query_sparse['data'])}")
            if len(query_sparse['indices']) == 0:
                print("  ⚠️  警告：稀疏向量无有效关键词，生成默认稀疏向量")
                # 如果没有关键词，生成一个默认的稀疏向量（避免完全空的稀疏向量）
                query_sparse['indices'] = [0]
                query_sparse['data'] = [0.0001]
            
            # 步骤4: 创建搜索请求（关键修复：稠密向量必须转为list格式）
            # Dense搜索请求：data=[query_dense.tolist()]（转换为list格式）
            # 【超级关键】必须保留为嵌套列表 [[...]]，以满足Milvus AnnSearchRequest的格式要求
            query_dense_list = query_dense.tolist()  # 首先转为Python list
            
            # 【第一步】强制转换每个元素为原生Python float（处理numpy.float64等类型）
            query_dense_list_cleaned = []
            for x in query_dense_list:
                try:
                    # 强制转换为Python float
                    val = float(x)
                    # 检查是否是有限数
                    if np.isfinite(val):
                        query_dense_list_cleaned.append(val)
                    else:
                        query_dense_list_cleaned.append(0.0)
                except (TypeError, ValueError) as te:
                    print(f"  ⚠️  警告：无法转换向量元素{x!r}为float：{te}")
                    query_dense_list_cleaned.append(0.0)
            
            query_dense_list = query_dense_list_cleaned
            
            # 【第二步】关键验证：确保所有元素都是原生Python float类型
            # 这是struct.pack失败的根本原因
            for i, val in enumerate(query_dense_list):
                # 使用 isinstance 检查，不检查 numpy 类型
                if not isinstance(val, float) or isinstance(val, (bool, np.bool_)):
                    # 强制重新转换
                    print(f"  ⚠️  【修复】向量[{i}]类型错误：{type(val).__name__}={val!r}，正在强制转换")
                    query_dense_list[i] = float(val)
            
            # 【第三步】最终验证：检查是否所有元素都是Python原生类型
            # 关键：不能有任何numpy类型在列表中
            type_issues = []
            for i, val in enumerate(query_dense_list):
                val_type = type(val).__name__
                if not (isinstance(val, float) and not isinstance(val, bool)):
                    type_issues.append((i, val_type, val))
            
            if type_issues:
                print(f"  ⚠️  【类型检查】发现{len(type_issues)}个类型异常：")
                for idx, tname, v in type_issues[:5]:  # 只显示前5个
                    print(f"    [{idx}] {tname}: {v!r}")
                # 强制转换所有异常
                query_dense_list = [float(v) if isinstance(v, (int, float, np.number)) else 0.0 for v in query_dense_list]
            
            # 【第四步】在创建AnnSearchRequest之前进行struct.pack验证
            # 这是最后一次机会在向量被使用前发现问题
            # print(f"\n🔍 【关键验证】在创建AnnSearchRequest前进行struct.pack测试...")
            try:
                # 测试 struct.pack
                test_packed = struct.pack(f"{len(query_dense_list)}f", *query_dense_list)
                # print(f"   ✅ struct.pack测试通过（{len(test_packed)} bytes）")
            except struct.error as pack_error:
                print(f"   ❌ struct.pack测试失败：{pack_error}")
                print(f"   向量长度：{len(query_dense_list)}")
                
                # 【改进】全面检查所有元素类型
                type_counts = {}
                problem_indices = []
                for i, x in enumerate(query_dense_list):
                    t = type(x).__name__
                    type_counts[t] = type_counts.get(t, 0) + 1
                    if not isinstance(x, float) or isinstance(x, bool):
                        problem_indices.append(i)
                
                print(f"   类型统计：{type_counts}")
                print(f"   问题元素数量：{len(problem_indices)}个")
                
                # 显示问题元素的具体位置
                if problem_indices:
                    print(f"   问题元素位置：{problem_indices[:10]}" + (f"... 还有{len(problem_indices)-10}个" if len(problem_indices) > 10 else ""))
                    # 显示几个具体的问题元素
                    for idx in problem_indices[:5]:
                        print(f"     [{idx}] {type(query_dense_list[idx]).__name__}: {query_dense_list[idx]!r}")
                
                # 强制重构列表
                print(f"   正在重新构建向量...")
                query_dense_list = [float(v) if isinstance(v, (int, float, np.number)) else 0.0 for v in query_dense_list]
                try:
                    test_packed = struct.pack(f"{len(query_dense_list)}f", *query_dense_list)
                    print(f"   ✅ 修复后struct.pack测试通过")
                except struct.error as e:
                    print(f"   ❌ 修复后仍然失败，将降级到Dense检索")
                    raise
            
            # 【关键】确保 query_dense_list 是纯Python list，没有numpy类型
            # AnnSearchRequest 的 data 参数需要嵌套list格式
            dense_search_req = AnnSearchRequest(
                data=[query_dense_list],  # 【重要】这里是 [[...]]，data参数包裹一层
                anns_field="embedding",
                param={"metric_type": "IP", "params": {"ef": max(top_k * 6, 800)}},
                limit=top_k * 6,
                expr=expr
            )
            
            # Sparse搜索请求：需要确保sparse向量格式正确
            # 【关键】Milvus期望sparse向量是{int_index: float_value}格式
            # 我们需要从indices和data重新构建这个格式
            sparse_dict = {int(idx): float(val) for idx, val in zip(query_sparse['indices'], query_sparse['data'])}
            # print(f"  最终稀疏向量：{len(sparse_dict)}个词项")
            # print(f"    样本项：{list(sparse_dict.items())[:5]}")
            
            sparse_search_req = AnnSearchRequest(
                data=[sparse_dict],  # 【修复】直接传dict格式而不是indices/data分离
                anns_field="sparse_embedding",
                param={"metric_type": "IP", "params": {"drop_ratio_search": 0.2}},
                limit=top_k * 6,
                expr=expr
            )
            
            # 步骤5: 执行混合检索
            self._log(f"执行混合检索：Dense向量维度={query_dense.shape[0]}, Sparse关键词数={len(query_sparse['indices'])}")
            
            # 【超级关键】在执行hybrid_search前，确保向量已封装到data参数
            try:
                # 直接执行上hybrid_search
                # 此时向量已经经过了1次struct.pack验证，应该是安全的
                hybrid_results = self.milvus_collection.hybrid_search(
                    reqs=[dense_search_req, sparse_search_req],
                    rerank=RRFRanker(),
                    limit=top_k * 6,
                    output_fields=["id", "parent_block_id", "child_block_id", "doc_id", "content", "original_filename"]
                )
            except struct.error as se:
                print(f"  ❌ hybrid_search内部struct.error: {se}")
                print(f"  Dense向量类型: {[type(x).__name__ for x in query_dense_list[:10]]}...")
                print(f"  Dense向量值样本: {query_dense_list[:5]}")
                print(f"  Sparse向量indices类型: {[type(x).__name__ for x in query_sparse['indices'][:5] if len(query_sparse['indices']) > 0]}")
                print(f"  Sparse向量data类型: {[type(x).__name__ for x in query_sparse['data'][:5] if len(query_sparse['data']) > 0]}")
                print(f"  Sparse向量数据: indices={query_sparse['indices'][:5]}, data={query_sparse['data'][:5]}")
                raise
            except Exception as hybrid_error:
                print(f"  ❌ hybrid_search异常 ({type(hybrid_error).__name__}): {hybrid_error}")
                print(f"  Dense向量检查：type={type(query_dense_list)}, len={len(query_dense_list)}")
                print(f"  Sparse向量检查：indices={len(query_sparse['indices'])}, data={len(query_sparse['data'])}")
                if hasattr(hybrid_error, '__traceback__'):
                    import traceback
                    print(f"\n【完整堆栈追踪】")
                    traceback.print_exc()
                raise
            self._log(f"混合检索完成，返回结果组数：{len(hybrid_results)}")
            
            # 步骤6: 处理混合检索结果，收集子块
            candidates = []
            for hits in hybrid_results:
                for hit in hits:
                    candidates.append({
                        'child_id': hit.entity.get('id'),
                        'parent_id': hit.entity.get('parent_block_id'),
                        'doc_id': hit.entity.get('doc_id'),
                        'child_content': hit.entity.get('content'),
                        'battery_type': hit.entity.get('battery_type', 'unknown'),
                        'original_filename': hit.entity.get('original_filename', 'unknown'),
                        'hybrid_similarity': hit.distance  # 混合检索相似度分数
                    })
            
            if not candidates:
                print(f"[DEBUG] ⚠️ 没有检索到任何候选块！")
                return []
            
            # 步骤7: 按parent_id聚合子块
            parent_scores = {}
            parent_doc_ids = {}
            parent_filenames = {}
            parent_battery_types = {}
            
            for c in candidates:
                parent_id = c['parent_id']
                if parent_id not in parent_scores:
                    parent_scores[parent_id] = []
                    parent_doc_ids[parent_id] = c['doc_id']
                    parent_filenames[parent_id] = c.get('original_filename', 'unknown')
                    parent_battery_types[parent_id] = c.get('battery_type', 'unknown')
                parent_scores[parent_id].append(c['hybrid_similarity'])
            
            # 按最高相似度排序
            ranked_parents = sorted(
                parent_scores.items(),
                key=lambda x: max(x[1]),
                reverse=True
            )
            
            # 选择Top-K*6个父块ID
            rerank_parent_ids = [pid for pid, _ in ranked_parents[:min(top_k * 6, len(ranked_parents))]]
            
            # 步骤8: 从Milvus查询这些父块的真实内容（1500字符）
            parent_blocks = []
            if rerank_parent_ids:
                try:
                    # 构建查询表达式：查询这些特定parent_id对应的父块
                    parent_filter = f"block_type == 'parent' and id in {rerank_parent_ids}"
                    parent_results = self.milvus_collection.query(
                        expr=parent_filter,
                        output_fields=["id", "content", "original_filename", "doc_id"],
                        limit=len(rerank_parent_ids)
                    )
                    
                    # 构建父块ID到内容的映射
                    parent_content_map = {p['id']: p['content'] for p in parent_results}
                    parent_filename_map = {p['id']: p.get('original_filename', 'unknown') for p in parent_results}
                    parent_doc_map = {p['id']: p.get('doc_id', 'unknown') for p in parent_results}
                    parent_battery_map = {p['id']: p.get('battery_type', 'unknown') for p in parent_results}
                    
                    # 构建最终的父块结果
                    for parent_id, scores in ranked_parents:
                        if parent_id in parent_content_map:
                            parent_blocks.append({
                                'parent_id': parent_id,
                                'content': parent_content_map[parent_id],  # 使用真实的1500字符父块内容
                                'doc_id': parent_doc_map.get(parent_id, parent_doc_ids.get(parent_id, 'unknown')),
                                'original_filename': parent_filename_map.get(parent_id, parent_filenames.get(parent_id, 'unknown')),
                                'battery_type': parent_battery_map.get(parent_id, parent_battery_types.get(parent_id, 'unknown')),
                                'max_similarity': max(scores),
                                'avg_similarity': sum(scores) / len(scores) if scores else 0,
                                'hit_count': len(scores)
                            })
                            if len(parent_blocks) >= top_k * 6:
                                break
                except Exception as e:
                    self._log(f"查询父块内容失败: {e}")
                    # 降级处理：如果查询失败，返回子块作为fallback
                    for parent_id, scores in ranked_parents[:top_k * 6]:
                        c = next((x for x in candidates if x['parent_id'] == parent_id), None)
                        if c:
                            parent_blocks.append({
                                'parent_id': parent_id,
                                'content': c['child_content'],  # 降级：使用子块内容
                                'doc_id': parent_doc_ids.get(parent_id, 'unknown'),
                                'original_filename': parent_filenames.get(parent_id, 'unknown'),
                                'battery_type': parent_battery_types.get(parent_id, 'unknown'),
                                'max_similarity': max(scores),
                                'avg_similarity': sum(scores) / len(scores) if scores else 0,
                                'hit_count': len(scores)
                            })
            
            # 步骤9: 筛选候选块
            rerank_count = min(top_k * 6, len(parent_blocks))
            parent_blocks_for_rerank = parent_blocks[:rerank_count]
            self._log(f"【候选块】选择 {len(parent_blocks_for_rerank)} 个块作为候选")
            
            if not parent_blocks_for_rerank:
                print(f"[DEBUG] ⚠️ 没有选中的块！parent_blocks={len(parent_blocks)}, top_k={top_k}")
                return []
            
            # 为块分配索引号
            for idx, block in enumerate(parent_blocks_for_rerank, 1):
                block['block_index'] = idx
            
            # 步骤10: Reranker精排（可选）
            if use_reranker and self.reranker_available:
                self._log("执行Reranker二次精排（对混合检索候选）...")
                ranked_results = self._rerank_with_scores(query, parent_blocks_for_rerank)
                
                final_results = []
                for block, rerank_score in ranked_results[:top_k]:
                    block['rerank_score'] = rerank_score
                    final_results.append(block)
                
                # 重新分配最终索引号
                for idx, block in enumerate(final_results, 1):
                    block['block_index'] = idx
                
                self._log(f"【最终结果】Reranker精排后返回 {len(final_results)} 个块（共{len(parent_blocks_for_rerank)}个候选）")
                self._print_final_stats(final_results)
                return final_results
            else:
                # 直接返回Top-K
                final_results = parent_blocks_for_rerank[:top_k]
                for idx, block in enumerate(final_results, 1):
                    block['block_index'] = idx
                self._log(f"【最终结果】直接返回 {len(final_results)} 个块（无Reranker）")
                self._print_final_stats(final_results)
                return final_results
                
        except Exception as e:
            self._log(f"混合检索出错: {e}")
            print(f"\n混合检索失败: {e}")
            import traceback
            print(f"\n【错误追踪】")
            print(f"  Dense向量类型: {type(query_dense_list)}, 长度: {len(query_dense_list)}")
            
            # 【改进】改为全面检查
            if len(query_dense_list) > 0:
                # 检查类型分布
                type_counts = {}
                problem_indices = []
                sample_size = min(100, len(query_dense_list))  # 控制样本量
                
                for i in range(sample_size):
                    x = query_dense_list[i]
                    t = type(x).__name__
                    type_counts[t] = type_counts.get(t, 0) + 1
                    if not isinstance(x, float) or isinstance(x, bool):
                        problem_indices.append(i)
                
                print(f"  类型统计（前{sample_size}个元素）：{type_counts}")
                print(f"  问题元素（第1-{sample_size}个）：{len(problem_indices)}个")
                
                if problem_indices:
                    print(f"  问题位置（前5个）：{problem_indices[:5]}")
                    for idx in problem_indices[:3]:
                        val = query_dense_list[idx]
                        print(f"    [{idx}] {type(val).__name__}: {val!r}")
                
                # 检查中库位置
                mid_idx = len(query_dense_list) // 2
                print(f"  中库元素{mid_idx}：{type(query_dense_list[mid_idx]).__name__}: {query_dense_list[mid_idx]!r}")
                
                # 检查末尾元素
                if len(query_dense_list) > 1:
                    print(f"  末尾元素-1：{type(query_dense_list[-1]).__name__}: {query_dense_list[-1]!r}")
            
            traceback.print_exc()
            
            # 降级到纯Dense检索
            print("⚠️  尝试降级到纯Dense检索...")
            return self._dense_search(query, top_k, use_reranker, battery_type_filter)
    
    def _sparse_search(self, query: str, top_k: int, battery_type_filter: Optional[List[str]] = None) -> List[Dict]:
        """
        稀疏向量检索 - 关键词匹配（降级处理用）
        
        Args:
            query: 查询
            top_k: 返回数量
            battery_type_filter: 可选的电池类型过滤条件
            
        Returns:
            稀疏检索结果列表
        """
        if self.milvus_collection is None:
            return []
        
        try:
            # 生成查询的稀疏向量
            query_sparse = self._generate_sparse_embedding(query)
            
            self._log(f"\n【Sparse Search】")
            self._log(f"  查询长度: {len(query)} 字符")
            self._log(f"  查询稀疏向量: {len(query_sparse.get('indices', []))} 个关键词")
            
            # 使用Milvus稀疏搜索
            search_params = {"metric_type": "IP", "params": {"ef": 800}}
            
            # 构建过滤表达式（CHUneng集合无battery_type字段，仅按block_type过滤）
            expr = "block_type == 'child'"
            print(f"\n🔍 【Sparse检索过滤】全局检索所有类型")
            
            sparse_results = self.milvus_collection.search(
                data=[query_sparse],
                anns_field="sparse_embedding",
                param=search_params,
                limit=top_k,
                expr=expr,
                output_fields=["id", "parent_block_id", "doc_id", "content", "original_filename"]
            )
            
            # 处理结果
            candidates = []
            for hits in sparse_results:
                for hit in hits:
                    candidates.append({
                        'parent_id': hit.entity.get('parent_block_id'),
                        'doc_id': hit.entity.get('doc_id'),
                        'content': hit.entity.get('content'),
                        'battery_type': hit.entity.get('battery_type', 'unknown'),
                        'original_filename': hit.entity.get('original_filename', 'unknown'),
                        'sparse_similarity': hit.distance
                    })
            
            self._log(f"  稀疏检索返回: {len(candidates)} 个候选")
            
            # 【改进】聚合到父块 + 去重
            parent_map = {}
            for c in candidates:
                pid = c['parent_id']
                if pid not in parent_map:
                    parent_map[pid] = {'doc_id': c['doc_id'], 'battery_type': c.get('battery_type', 'unknown'), 'original_filename': c.get('original_filename', 'unknown'), 'scores': []}
                parent_map[pid]['scores'].append(c['sparse_similarity'])
            
            # 【改进】去重统计
            dedup_ratio = len(candidates) / len(parent_map) if parent_map else 0
            self._log(f"【父块去重】{len(candidates)} 个候选 → {len(parent_map)} 个唯一父块 (平均{dedup_ratio:.1f}个候选/父块)")
            
            # 【关键修复】从Milvus查询这些父块的真实内容（1500字符）而不是子块
            results = []
            parent_ids = list(parent_map.keys())
            if parent_ids:
                try:
                    # 构建查询表达式：查询这些特定parent_id对应的父块
                    parent_filter = f"block_type == 'parent' and id in {parent_ids}"
                    parent_results = self.milvus_collection.query(
                        expr=parent_filter,
                        output_fields=["id", "content", "original_filename", "doc_id"],
                        limit=len(parent_ids)
                    )
                    
                    # 构建父块ID到内容的映射
                    parent_content_map = {p['id']: p['content'] for p in parent_results}
                    parent_filename_map = {p['id']: p.get('original_filename', 'unknown') for p in parent_results}
                    parent_battery_map = {p['id']: p.get('battery_type', 'unknown') for p in parent_results}
                    
                    # 构建最终的父块结果
                    for pid, data in parent_map.items():
                        if pid in parent_content_map:
                            results.append({
                                'parent_id': pid,
                                'content': parent_content_map[pid],  # 【修复】使用真实的1500字符父块内容
                                'doc_id': data['doc_id'],
                                'battery_type': parent_battery_map.get(pid, data.get('battery_type', 'unknown')),
                                'original_filename': parent_filename_map.get(pid, data.get('original_filename', 'unknown')),
                                'sparse_similarity': max(data['scores']),
                                'search_type': 'sparse'
                            })
                except Exception as e:
                    self._log(f"查询Sparse父块内容失败: {e}")
                    # 降级处理：如果查询失败，返回子块作为fallback
                    for pid, data in parent_map.items():
                        for c in candidates:
                            if c['parent_id'] == pid:
                                results.append({
                                    'parent_id': pid,
                                    'content': c['content'],  # 降级：使用子块内容
                                    'doc_id': data['doc_id'],
                                    'battery_type': data.get('battery_type', 'unknown'),
                                    'original_filename': data.get('original_filename', 'unknown'),
                                    'sparse_similarity': max(data['scores']),
                                    'search_type': 'sparse'
                                })
                                break
            
            # 按稀疏相似度排序
            results.sort(key=lambda x: x['sparse_similarity'], reverse=True)
            self._log(f"【Sparse最终结果】返回 {min(top_k, len(results))} 个父块 (from {len(parent_map)} 个去重)")
            return results[:top_k]
            
        except Exception as e:
            self._log(f"稀疏搜索异常: {e}")
            return []
    
    def _generate_sparse_embedding(self, text: str) -> dict:
        """
        生成查询的稀疏向量
        
        与traditional_rag_v3.py中的实现一致
        """
        import re
        from collections import Counter
        
        words = re.findall(r'\w+|[\u4e00-\u9fff]+', text.lower())
        if not words:
            return {"indices": [], "data": []}
        
        word_counts = Counter(words)
        total_words = len(words)
        word_weights = []
        
        for word, count in word_counts.most_common():
            tf = count / total_words
            idf = 0.1 if self._is_stopword(word) else (0.3 if len(word) == 1 else 1.0)
            weight = tf * idf
            if weight > 0.01:
                word_weights.append((word, weight))
        
        top_words = sorted(word_weights, key=lambda x: x[1], reverse=True)[:100]
        indices = []
        data = []
        for word, weight in top_words:
            word_hash = hash(word) % 100000
            # 【关键修复】强制转换为Python int和float，确保类型纯正
            indices.append(int(word_hash))  # 显式转为Python int
            data.append(float(weight))  # 显式转为Python float
        
        return {"indices": indices, "data": data}
    
    def _validate_dense_vector(self, query_dense_list: list) -> bool:
        """
        严格校验Dense向量是否正常
        检查是否能被 struct.pack 打包
        
        这是 struct.error 的最后防线
        """
        if not isinstance(query_dense_list, list):
            print(f"\n⚠️  【类型错误】向量必须是list，实际为{type(query_dense_list).__name__}")
            return False
        
        # 第一层检查：类型校验
        print(f"\n🔍 【向量校验】开始校验Dense向量...")
        print(f"  向量长度: {len(query_dense_list)}")
        
        # 检查每个元素的类型
        type_errors = []
        for i, x in enumerate(query_dense_list):
            if not isinstance(x, float):
                type_errors.append((i, type(x).__name__, repr(x)))
                if len(type_errors) >= 5:  # 只记录前5个错误
                    break
        
        if type_errors:
            print(f"  ⚠️  【类型检查失败】发现{len(type_errors)}个非float元素：")
            for idx, tname, val in type_errors:
                print(f"    [{idx}] {tname}: {val}")
            return False
        
        # 第二层检查：struct.pack测试
        try:
            # 测试 struct.pack - 这是struct.error的最后症状
            packed = struct.pack(f"{len(query_dense_list)}f", *query_dense_list)
            print(f"  ✅ 向量校验通过")
            return True
        except struct.error as e:
            print(f"  ⚠️  【struct.error】{e}")
            print(f"     这表示列表中存在非float类型或其他无法打包的数据")
            # 进一步诊断
            for i in [0, 1, 2, len(query_dense_list)//2, -3, -2, -1]:
                if 0 <= i < len(query_dense_list) or i < 0:
                    try:
                        val = query_dense_list[i]
                        print(f"     [{i}] {type(val).__name__}: {val!r}")
                    except:
                        pass
            return False
        except Exception as e:
            print(f"  ⚠️  【未知错误】{type(e).__name__}: {e}")
            return False
    
    def _is_stopword(self, word: str) -> bool:
        """判断停用词"""
        stopwords = {
            'is', 'am', 'are', 'was', 'were', 'been', 'be',
            'have', 'has', 'had', 'do', 'does', 'did',
            'will', 'would', 'could', 'should', 'may', 'might',
            'can', 'of', 'in', 'on', 'at', 'to', 'for', 'and', 'or', 'but', 'not',
            'the', 'a', 'an', 'this', 'that', 'these', 'those',
            '是', '的', '一', '不', '了', '有', '和', '人', '这', '中', '大'
        }
        return word.lower() in stopwords
    
    def _rrf_merge(self, dense_results: List[Dict], sparse_results: List[Dict], top_k: int) -> List[Dict]:
        """
        RRF (Reciprocal Rank Fusion) - 互惠排名融合 + 质量增强
        
        改进：
        1. 动态权重：根据结果质量调整Dense和Sparse权重
        2. 相关性过滤：去除低相关性结果
        3. 多样性保证：避免重复doc_id过多
        
        公式: RRF(d) = Σ(1 / (k + rank(d))) + quality_bonus
        其中 k = 60, quality_bonus 基于相似度
        """
        k = 60  # RRF参数
        score_map = {}
        
        # 【改进1】计算Dense结果的平均相似度，作为质量基准
        dense_avg_sim = np.mean([r.get('max_similarity', 0) for r in dense_results]) if dense_results else 0
        sparse_avg_sim = np.mean([r.get('sparse_similarity', 0) for r in sparse_results]) if sparse_results else 0
        
        # 动态调整权重：如果Dense质量明显更好，增加其权重
        dense_weight = 0.75 if dense_avg_sim > sparse_avg_sim * 1.2 else 0.65
        sparse_weight = 1.0 - dense_weight
        
        self._log(f"【RRF权重】Dense: {dense_weight:.2f}, Sparse: {sparse_weight:.2f} (质量: Dense={dense_avg_sim:.4f}, Sparse={sparse_avg_sim:.4f})")
        
        # 处理Dense结果
        for rank, result in enumerate(dense_results, 1):
            pid = result['parent_id']
            rrf_score = 1 / (k + rank)
            # 【改进2】添加相似度奖励（高相似度获得更高分）
            similarity_bonus = result.get('max_similarity', 0) * 0.15
            final_score = (rrf_score * dense_weight) + similarity_bonus
            
            if pid not in score_map:
                score_map[pid] = {'data': result, 'rrf_score': 0, 'from_dense': True}
            score_map[pid]['rrf_score'] += final_score
        
        # 处理Sparse结果 - 【修复】统一使用max_similarity字段
        for rank, result in enumerate(sparse_results, 1):
            pid = result['parent_id']
            rrf_score = 1 / (k + rank)
            # 【修复】使用sparse_similarity作为质量度量，但在结果中统一为max_similarity
            similarity_bonus = result.get('sparse_similarity', 0) * 0.08
            final_score = (rrf_score * sparse_weight) + similarity_bonus
            
            # 【修复】为Sparse结果补充max_similarity字段（RRF融合后使用）
            if 'max_similarity' not in result:
                result['max_similarity'] = result.get('sparse_similarity', 0)
            
            if pid not in score_map:
                score_map[pid] = {'data': result, 'rrf_score': 0, 'from_dense': False}
            score_map[pid]['rrf_score'] += final_score
        
        # 【改进3】过滤低分结果
        min_score_threshold = 0.02
        filtered_map = {pid: data for pid, data in score_map.items() if data['rrf_score'] >= min_score_threshold}
        
        # 排序并实现多样性
        merged = sorted(filtered_map.values(), key=lambda x: x['rrf_score'], reverse=True)
        results = []
        seen_docs = {}  # 【改进4】跟踪doc_id出现次数
        
        for item in merged:
            doc_id = item['data'].get('doc_id', '')
            # 【修复】同一doc_id最多4个块（放宽限制以确保能达到top_k个）
            if doc_id and seen_docs.get(doc_id, 0) >= 4:
                self._log(f"跳过重复doc_id: {doc_id}")
                continue
            
            item['data']['rrf_score'] = item['rrf_score']
            results.append(item['data'])
            
            if doc_id:
                seen_docs[doc_id] = seen_docs.get(doc_id, 0) + 1
            
            if len(results) >= top_k:
                break
        
        filter_ratio = (1 - len(results)/len(score_map))*100 if score_map else 0
        self._log(f"RRF融合: {len(dense_results)} + {len(sparse_results)} -> {len(results)} 个结果 (过滤率: {filter_ratio:.1f}%)")
        return results
    
    def recall_with_keywords(self, query: str, keywords: List[str] = None,
                             top_k: int = 5) -> Tuple[List[Dict], Dict]:
        """
        混合检索：向量检索 + 关键词增强
        
        Args:
            query: 用户查询
            keywords: 优先匹配的关键词列表
            top_k: 返回数量
        """
        # 获取更多候选
        candidates = self.recall_parent_blocks(query, top_k=top_k * 3, use_reranker=True)
        
        if not keywords:
            return candidates[:top_k]
        
        # 关键词匹配加分
        for block in candidates:
            content_lower = block['content'].lower()
            keyword_hits = sum(1 for kw in keywords if kw.lower() in content_lower)
            block['keyword_hits'] = keyword_hits
        
        # 按关键词命中数和rerank分数综合排序
        candidates.sort(
            key=lambda x: (x.get('keyword_hits', 0), x.get('rerank_score', 0)),
            reverse=True
        )
        
        final_results = candidates[:top_k]
        return final_results

# 测试代码
if __name__ == "__main__":
    print("DocumentRecallerV2 模块测试")
    print("请通过 main.py 或 rag_qa_v2.py 调用此模块")