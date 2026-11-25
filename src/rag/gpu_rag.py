import os
import sys
import json
import time
import hashlib
import numpy as np
import torch
import torch.nn.functional as F
import traceback
from typing import List, Dict
from transformers import AutoTokenizer, AutoModelForMaskedLM, pipeline
from pymilvus import connections, Collection, FieldSchema, CollectionSchema, DataType, utility
from classification import identify_battery_type

class TraditionalRAGV5_Stable:
    COLLECTION_NAME = "traditional_rag_collection_v6"
    
    def __init__(self, data_directory: str, milvus_host: str = "localhost", milvus_port: int = 19530, 
                 model_path: str = None, force_rebuild: bool = False):
        
        self.data_directory = data_directory
        self.milvus_host = milvus_host
        self.milvus_port = milvus_port
        self.model_path = model_path
        self.force_rebuild = force_rebuild
        
        # --- 性能配置 ---
        self.global_buffer_size = 50   # 增大到100，减少flush次数
        self.gpu_batch_size = 4        # 增大GPU批次，充分利用显存
        self.milvus_upsert_timeout = 120 # 增加超时容限
        
        # --- 分块配置（满足需求）---
        self.parent_chunk_size = 1500    # 父块大小
        self.parent_overlap = 100        # 父块重叠
        self.child_chunk_size = 500      # 子块大小
        self.child_overlap = 100         # 子块重叠
        
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"🚀 [V5 Stable] 启动 | Device: {self.device} | Mode: Bulk Load | 父子块存储模式")
        print(f"   分块配置: 父块{self.parent_chunk_size}字符(重叠{self.parent_overlap}) | 子块{self.child_chunk_size}字符(重叠{self.child_overlap})")
        self.documents = {}
        self.document_original_names = {}
        self.milvus_collection = None
        self.model = None
        self.tokenizer = None
        
        self._run_storage_pipeline()
    
    def _run_storage_pipeline(self):
        print("\n" + "="*70)
        # 1. 加载资源
        self._load_documents()
        self._initialize_models_and_db()
        
        # 2. 处理数据（写入时暂不建索引，速度最快）
        print(f"\n[Step 1] 处理并写入文档 (总数: {len(self.documents)})...")
        total_chunks = self._process_all_documents()
        
        # 3. 收尾工作
        print("\n" + "-"*30)
        print("[Step 2] 正在强制数据落盘 (Flush)...")
        if self.milvus_collection:
            self.milvus_collection.flush()
            num = self.milvus_collection.num_entities
            print(f"   -> 数据已落盘，当前条数: {num} (父块+子块)")
            print("[Step 3] 开始构建索引 (CPU密集型操作，请耐心等待)...")
            t0 = time.time()
            self._build_index_now()
            print(f"   -> 索引构建完成 (耗时 {time.time()-t0:.2f}s)")
            
            # 加载到内存供查询
            print("[Step 4] 加载集合到内存...")
            self.milvus_collection.load()
        
        print("="*70)
        print(f"✓ 全部完成！有效入库 Chunk: {total_chunks} (父块+子块)")
    
    def _initialize_models_and_db(self):
        try:
            print(f"1. 加载模型 (BGE-M3)...")
            if self.model_path:
                # 兼容路径逻辑
                bge_path = os.path.join(self.model_path, "bge-m3")
                if not os.path.exists(bge_path): bge_path = self.model_path
                self.tokenizer = AutoTokenizer.from_pretrained(bge_path, local_files_only=True)
                self.model = AutoModelForMaskedLM.from_pretrained(bge_path, local_files_only=True)
                self.model.to(self.device)
                if self.device.type == 'cuda': self.model.half()
                self.model.eval()
            
            print(f"2. 连接 Milvus ({self.milvus_host}:{self.milvus_port})...")
            try:
                connections.connect(alias="default", host=self.milvus_host, port=self.milvus_port, timeout=30)
            except Exception:
                print("   ⚠️ 连接超时，重试中...")
                time.sleep(2)
                connections.connect(alias="default", host=self.milvus_host, port=self.milvus_port, timeout=30)
            
            # 定义Schema（兼容父子块存储）
            fields = [
                FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=False),
                FieldSchema(name="block_type", dtype=DataType.VARCHAR, max_length=20),  # parent/child
                FieldSchema(name="battery_type", dtype=DataType.VARCHAR, max_length=50),
                FieldSchema(name="parent_block_id", dtype=DataType.INT64),  # 子块关联父块ID，父块填-1
                FieldSchema(name="child_block_id", dtype=DataType.INT64),   # 子块序号（父块填-1）
                FieldSchema(name="doc_id", dtype=DataType.VARCHAR, max_length=256),
                FieldSchema(name="original_filename", dtype=DataType.VARCHAR, max_length=512),
                FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=1024),
                FieldSchema(name="sparse_embedding", dtype=DataType.SPARSE_FLOAT_VECTOR)
            ]
            
            # 删除旧表逻辑
            if self.force_rebuild and utility.has_collection(self.COLLECTION_NAME):
                print(f"   -> 删除旧集合 {self.COLLECTION_NAME}...")
                utility.drop_collection(self.COLLECTION_NAME)
                time.sleep(1)
            
            # 创建新表
            if not utility.has_collection(self.COLLECTION_NAME):
                schema = CollectionSchema(fields=fields, description="Traditional RAG V7")
                self.milvus_collection = Collection(name=self.COLLECTION_NAME, schema=schema)
                print("   -> 集合已创建 (暂未创建索引，将在写入后统一创建)")
            else:
                self.milvus_collection = Collection(name=self.COLLECTION_NAME)
                print("   -> 加载已有集合")
                
        except Exception as e:
            print(f"❌ 初始化失败: {e}")
            raise
    
    def _detect_battery_type(self, filename: str) -> str:
        """使用 classification.py 中的规则识别液流电池类型（基于文献标题）"""
        if not filename or not isinstance(filename, str):
            return 'other'
        battery_type = identify_battery_type(filename)
        return battery_type
    
    def _build_index_now(self):
        """写入完成后统一建索引"""
        try:
            # 1. Dense Index (HNSW) - 更强的索引质量
            print("   -> 构建 Dense Index (HNSW)...")
            self.milvus_collection.create_index(
                "embedding", 
                {"metric_type": "IP", "index_type": "HNSW", "params": {"M": 24, "efConstruction": 400}}
            )
            # 2. Sparse Index (Inverted)
            print("   -> 构建 Sparse Index...")
            self.milvus_collection.create_index(
                "sparse_embedding", 
                {"metric_type": "IP", "index_type": "SPARSE_INVERTED_INDEX", "params": {"drop_ratio_build": 0.1}}
            )
        except Exception as e:
            print(f"⚠️ 索引构建警告 (可能已存在): {e}")
    
    def _process_all_documents(self):
        global_buffer = []
        total_processed = 0
        doc_ids = list(self.documents.keys())
        
        for i, doc_id in enumerate(doc_ids):
            # 生成父子块（核心修改）
            chunks = self._chunk_single_document(doc_id)
            global_buffer.extend(chunks)
            
            # 进度打印
            sys.stdout.write(f"\rProcessing: {i+1}/{len(doc_ids)} | Buffer: {len(global_buffer)} | Total: {total_processed}")
            sys.stdout.flush()
            
            if len(global_buffer) >= self.global_buffer_size:
                print(f"\n>> 写入批次 (Size={len(global_buffer)})...")
                processed = self._flush_buffer_sync(global_buffer)
                total_processed += processed
                global_buffer = [] 
        if global_buffer:
            print(f"\n>> 写入剩余批次 (Size={len(global_buffer)})...")
            processed = self._flush_buffer_sync(global_buffer)
            total_processed += processed
            
        return total_processed
    
    def _flush_buffer_sync(self, buffer: List[Dict]) -> int:
        if not buffer: return 0
        
        # 【改进】根据记忆 Embedding 需注入文档上下文
        # 池化文本为: "Title: {original_filename}\nContent: {content}"
        enriched_texts = []
        for item in buffer:
            title = item.get('original_filename', '')
            content = item.get('content', '')[:2000]  # 保持原有的需塞上限
            # 带标题的上下文帮助模型理解
            enriched = f"Title: {title}\nContent: {content}"
            enriched_texts.append(enriched)
        
        texts = enriched_texts
        
        # GPU 推理
        all_dense = []
        all_sparse = []
        bs = self.gpu_batch_size
        
        print("   [GPU] Calculating Embeddings...", end="")
        for i in range(0, len(texts), bs):
            batch_texts = texts[i : i + bs]
            try:
                dense, sparse = self._embed_batch(batch_texts)
                all_dense.extend(dense)
                all_sparse.extend(sparse)
            except Exception as e:
                print(f"\n❌ 推理错误: {e}")
                # 填充空值防止错位
                for _ in batch_texts:
                    all_dense.append([0.0]*1024)
                    all_sparse.append({0:0.0})
        
        if torch.cuda.is_available(): torch.cuda.empty_cache()
        print("Done.")
        
        # 回填数据
        valid_buffer = []
        for idx, item in enumerate(buffer):
            if idx < len(all_dense):
                item['embedding'] = all_dense[idx]
                item['sparse_embedding'] = all_sparse[idx]
                valid_buffer.append(item)
            
        if valid_buffer:
            self._insert_with_retry(valid_buffer)
                
        return len(valid_buffer)
    
    def _embed_batch(self, texts: List[str]):
        """生成 BGE-M3 向量 (Dense + Sparse)"""
        inputs = self.tokenizer(texts, padding=True, truncation=True, max_length=1024, return_tensors='pt')
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        
        with torch.no_grad():
            outputs = self.model(**inputs, output_hidden_states=True, return_dict=True)
            
            # --- Dense ---
            dense_vecs = outputs.hidden_states[-1][:, 0, :]
            dense_vecs = F.normalize(dense_vecs, p=2, dim=1)
            dense_vecs_np = dense_vecs.float().cpu().numpy()
            # 【关键修复】将numpy.float32转为纯Python float
            dense_list = [[float(v) for v in row] for row in dense_vecs_np.tolist()]
            # --- Sparse (关键修复) ---
            logits = outputs.logits
            weights = torch.relu(logits)
            
            # 🚨 MASK 特殊 Token: [CLS], [PAD], [SEP], [UNK] (通常是 ID 0-4)
            # 这能防止稀疏向量只包含这些无意义的高频 Token
            weights[:, 0:4] = 0.0 
            
            max_weights, _ = torch.max(weights, dim=1)
            max_weights_cpu = max_weights.float().cpu()
            
            sparse_list = []
            for i in range(len(texts)):
                row = max_weights_cpu[i]
                
                # 改进：选择top-k高权重token，而不是固定阈值
                top_k = min(20, int(row.shape[0] * 0.1))  # 取top10%，最多20个
                top_vals, top_indices = torch.topk(row, top_k, largest=True)
                
                # 【关键修复】归一化权重到0-1范围
                # 使用softmax或min-max归一化确保权重在合理范围
                if top_vals.max() > 0:
                    top_vals = (top_vals - top_vals.min()) / (top_vals.max() - top_vals.min() + 1e-8)
                
                # 过滤低权重，避免数据体积过大
                mask = top_vals > 0.05
                if mask.any():
                    indices = top_indices[mask].tolist()
                    values = top_vals[mask].tolist()
                    # 【修复】确保indices是Python int（使用.item()确保类型），values是Python float
                    sp_dict = {}
                    for idx_val, val_val in zip(indices, values):
                        # 强制转换为Python原生类型
                        k = int(idx_val) if isinstance(idx_val, (int, float, np.integer)) else None
                        v = float(val_val) if isinstance(val_val, (int, float, np.number)) else None
                        if k is not None and v is not None and isinstance(k, int) and isinstance(v, float):
                            sp_dict[k] = v
                else:
                    # 至少保留最高的那个
                    sp_dict = {int(top_indices[0].item()): float(top_vals[0].item())}
                
                sparse_list.append(sp_dict if sp_dict else {0: 0.00001})
        
        return dense_list, sparse_list
    
    def _insert_with_retry(self, buf, max_retries=3):
        sanitized = self._sanitize_data(buf)
        
        # 字段拆包（兼容父子块字段）
        data = [
            [c['id'] for c in sanitized],
            [str(c['block_type']) for c in sanitized],
            [str(c['battery_type']) for c in sanitized],
            [int(c['parent_block_id']) for c in sanitized],
            [int(c['child_block_id']) for c in sanitized],
            [str(c['doc_id']) for c in sanitized],
            [str(c['original_filename'])[:500] for c in sanitized],
            [c['content'] for c in sanitized],
            [c['embedding'] for c in sanitized],
            [c['sparse_embedding'] for c in sanitized]
        ]
        
        print(f"   [DB] Writing {len(sanitized)} rows...", end="", flush=True)
        for attempt in range(max_retries):
            try:
                t0 = time.time()
                self.milvus_collection.upsert(data, timeout=self.milvus_upsert_timeout)
                elapsed = time.time() - t0
                print(f" Done ({elapsed:.2f}s).")
                return True
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f" Retry({attempt+1})...", end="", flush=True)
                    time.sleep(3)
                else:
                    print(f"\n❌ Failed after {max_retries} retries: {str(e)[:60]}")
                    return False
        return False
    
    def _sanitize_data(self, batch: List[Dict]):
        """数据类型清洗，防止Milvus报错"""
        clean_batch = []
        for item in batch:
            # Clean Sparse - 【超级关键】确保所有key和value都是正确类型
            sp = item['sparse_embedding']
            clean_sp = {}
            if isinstance(sp, dict):
                for k, v in sp.items():
                    try:
                        # 严格转换：key必须是int，value必须是float
                        k_int = int(k) if isinstance(k, (int, float, np.integer)) else None
                        v_float = float(v) if isinstance(v, (int, float, np.number)) else None
                        
                        if k_int is not None and v_float is not None and k_int >= 0:
                            # 双重确认类型
                            if isinstance(k_int, int) and isinstance(v_float, float):
                                clean_sp[k_int] = v_float
                    except (TypeError, ValueError):
                        pass  # 跳过无法转换的项
            
            if not clean_sp:
                clean_sp = {0: 0.00001}
            
            # Clean Content
            c_str = str(item['content'])
            if len(c_str.encode('utf-8')) > 60000: c_str = c_str[:15000]
            clean_item = item.copy()
            clean_item['id'] = int(item['id'])
            clean_item['sparse_embedding'] = clean_sp
            clean_item['content'] = c_str
            clean_batch.append(clean_item)
        return clean_batch
    
    def _chunk_single_document(self, doc_id: str) -> List[Dict]:
        """核心修改：生成父子块（父块包含子块，子块关联父块）"""
        content = self.documents[doc_id]
        title = self.document_original_names.get(doc_id, doc_id)
        all_chunks = []
        battery_type = self._detect_battery_type(title)
        
        # 生成文档级唯一标识（用于父块ID生成）
        doc_hash = hashlib.md5(doc_id.encode()).hexdigest()[:8]
        
        # --------------------------
        # 第一步：切分父块（1500字符，重叠100）
        # --------------------------
        parent_chunks = []
        parent_step = self.parent_chunk_size - self.parent_overlap  # 实际步长：1500-100=1400
        parent_idx = 0
        
        while parent_idx < len(content):
            # 计算父块边界
            start = parent_idx
            end = min(start + self.parent_chunk_size, len(content))
            parent_content = content[start:end]
            
            # 跳过空块
            if not parent_content.strip():
                parent_idx += parent_step
                continue
            
            # 生成父块唯一ID
            parent_raw_hash = hashlib.md5(f"{doc_hash}_parent_{parent_idx}".encode()).hexdigest()
            parent_id = int(parent_raw_hash[:15], 16)
            
            # 父块数据结构
            parent_chunk = {
                'id': parent_id,
                'block_type': 'parent',  # 标记为父块
                'battery_type': battery_type,
                'parent_block_id': -1,   # 父块无父块，填-1
                'child_block_id': -1,    # 父块无子块序号，填-1
                'doc_id': doc_id,
                'original_filename': title,
                'content': parent_content,
                'embedding': [],
                'sparse_embedding': {}
            }
            parent_chunks.append(parent_chunk)
            
            # 移动到下一个父块（考虑重叠）
            parent_idx += parent_step
        
        # --------------------------
        # 第二步：为每个父块切分子块（500字符，重叠100）
        # --------------------------
        for parent_chunk in parent_chunks:
            parent_id = parent_chunk['id']
            parent_content = parent_chunk['content']
            child_step = self.child_chunk_size - self.child_overlap  # 实际步长：500-100=400
            child_idx = 0
            
            while child_idx < len(parent_content):
                # 计算子块边界（基于父块内容，确保父块包含子块）
                start = child_idx
                end = min(start + self.child_chunk_size, len(parent_content))
                child_content = parent_content[start:end]
                
                # 跳过空块
                if not child_content.strip():
                    child_idx += child_step
                    continue
                
                # 生成子块唯一ID（基于父块ID+子块序号，确保全局唯一）
                child_raw_hash = hashlib.md5(f"{parent_id}_child_{child_idx}".encode()).hexdigest()
                child_id = int(child_raw_hash[:15], 16)
                
                # 子块数据结构（关联父块ID）
                child_chunk = {
                    'id': child_id,
                    'block_type': 'child',  # 标记为子块
                    'battery_type': battery_type,
                    'parent_block_id': parent_id,  # 关联对应的父块ID
                    'child_block_id': child_idx,   # 子块在父块中的序号
                    'doc_id': doc_id,
                    'original_filename': title,
                    'content': child_content,
                    'embedding': [],
                    'sparse_embedding': {}
                }
                all_chunks.append(child_chunk)
                
                # 移动到下一个子块（考虑重叠）
                child_idx += child_step
        
        # --------------------------
        # 第三步：合并父子块（父块+子块一起存储）
        # --------------------------
        all_chunks = parent_chunks + all_chunks
        return all_chunks
    
    def _load_documents(self):
        print("   加载本地数据...")
        if not os.path.exists(self.data_directory): return
        
        search_dir = os.path.join(self.data_directory, "downloaded_files")
        if not os.path.exists(search_dir): search_dir = self.data_directory
        try:
            folders = os.listdir(search_dir)
        except:
            folders = []
            
        for folder in folders:
            path = os.path.join(search_dir, folder)
            if os.path.isdir(path):
                # 【改进】从JSON文件中获取 text_level=1 的文本作为文献标题
                title = folder  # 默认使用文件夹名
                title_found = False  # 标记是否找到了有效标题
                try:
                    # 查找文件夹下的所有JSON文件
                    files = os.listdir(path)
                    for f in files:
                        if f.endswith(".json") and "content_list" in f:
                            try:
                                with open(os.path.join(path, f), 'r', encoding='utf-8') as jf:
                                    d = json.load(jf)
                                    # 查找 text_level=1 的条目作为文献标题（优先）
                                    if isinstance(d, list) and len(d) > 0:
                                        for item in d:
                                            if isinstance(item, dict):
                                                # 首先查找 text_level=1 的条目
                                                if item.get('text_level') == 1 and 'text' in item:
                                                    title = item['text'].strip()
                                                    title_found = True
                                                    break
                                        # 如果没找到 text_level=1，则查找第一个有 'text' 字段的条目
                                        if not title_found:
                                            for item in d:
                                                if isinstance(item, dict) and 'text' in item:
                                                    title = item['text'].strip()
                                                    title_found = True
                                                    break
                                    elif isinstance(d, dict) and 'text' in d:
                                        title = d['text'].strip()
                                        title_found = True
                                    # 找到第一个有效的JSON就停止
                                    if title_found:
                                        break
                            except Exception as e:
                                continue
                except:
                    pass
                
                # 读取正文
                md = os.path.join(path, "full.md")
                if os.path.exists(md):
                    with open(md, 'r', encoding='utf-8') as f:
                        content = f.read()
                        # 只存储非空文档
                        if content.strip():
                            self.documents[folder] = content
                            # 【改进】存储提取的文献标题（来自JSON的 text_level=1）
                            self.document_original_names[folder] = title
                        else:
                            print(f"   ⚠️ 跳过空文档: {folder}")

if __name__ == "__main__":
    # 配置区域 - 动态计算路径
    CURRENT_FILE_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(os.path.dirname(CURRENT_FILE_DIR))
    
    # 模型路径：e:\flowbd_v5\src\rag\models
    MODEL_PATH = os.path.join(CURRENT_FILE_DIR, "models")
    
    # 数据路径：e:\flowbd_v5\pdf_to_md\extraction_results
    DATA_PATH = os.path.join(PROJECT_ROOT, "pdf_to_md", "extraction_results")
    
    print(f"DEBUG: PROJECT_ROOT = {PROJECT_ROOT}")
    print(f"DEBUG: MODEL_PATH   = {MODEL_PATH}")
    print(f"DEBUG: DATA_PATH    = {DATA_PATH}")
    
    rag = TraditionalRAGV5_Stable(
        data_directory=DATA_PATH, 
        model_path=MODEL_PATH, 
        force_rebuild=True
    )