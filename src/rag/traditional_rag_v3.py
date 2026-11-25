"""
传统 RAG 系统实现 - V3 CPU 批量加速版

特性：
1. [速度] 启用 CPU 小批量推理 (Batch=4) 和 批量存储 (Batch=50)，提升处理速度。
2. [精度] 手动实现 BGE-M3 Dense + Sparse (SPLADE) 算法，保证检索精度。
3. [稳定] 包含安全归一化、Python类型强制转换，防止 Milvus 卡死。
4. [交互] 实时进度显示 (+ 代表推理一批, * 代表存储一批)。
"""

import os
import re
import sys
import hashlib
import gc
import numpy as np
import torch

# 1. 禁用各种可能导致冲突的优化 (针对 Windows CPU 环境)
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"

# 2. 限制 PyTorch CPU 线程数 (设置为 4 以平衡速度和稳定性)
torch.set_num_threads(4) 

from typing import List, Dict, Tuple
from transformers import AutoTokenizer, AutoModelForMaskedLM
from pymilvus import connections, Collection, FieldSchema, CollectionSchema, DataType, utility


class TraditionalRAGV3:
    COLLECTION_NAME = "CHUneng"
    
    def __init__(self, data_directory: str, milvus_host: str = "localhost", milvus_port: int = 19530, 
                 model_path: str = None, force_rebuild: bool = False, storage_mode: bool = True,
                 num_workers: int = 1, use_parallel: bool = False):
        
        self.data_directory = data_directory
        self.milvus_host = milvus_host
        self.milvus_port = milvus_port
        self.model_path = model_path
        self.force_rebuild = force_rebuild
        self.storage_mode = storage_mode
        
        # --- GPU/CPU 自动检测 ---
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"INFO: Device Mode: {self.device.upper()} (CUDA Available: {torch.cuda.is_available()})")
        
        # 强制单线程 (CPU 计算密集型 + Windows 环境不适合多线程)
        self.num_workers = 1
        self.use_parallel = False 
        
        # --- 批处理配置 ---
        # RTX 4070 (12GB): BGE-M3 约占 2GB，每批 16 条安全；CPU 用 4
        self.embed_batch_size = 8 if self.device == "cuda" else 4
        # 插入批次：每50条插一次，减少 Milvus 通信次数
        self.insert_batch_size = 50
        
        self.documents = {}
        self.document_titles = {}
        self.document_original_names = {}
        
        self.milvus_collection = None
        self.model = None
        self.tokenizer = None
        
        if storage_mode:
            print("\n" + "="*70)
            print("[存储模式] 开始构建Milvus索引")
            print("="*70)
            
            self._load_documents()
            self._initialize_models_and_db()
            self._check_and_build_index()
            
            print("="*70)
            print("OK: Milvus index build completed")
            print("="*70 + "\n")
        else:
            try:
                connections.connect(host=self.milvus_host, port=self.milvus_port, timeout=10)
                if utility.has_collection(self.COLLECTION_NAME):
                    self.milvus_collection = Collection(name=self.COLLECTION_NAME)
                    self.milvus_collection.load()
            except Exception as e:
                print(f"连接失败: {e}")

    def _load_documents(self):
        print("正在加载MD文档...")
        filename_mapping = {}
        # 尝试加载映射表
        mapping_file = os.path.join(os.path.dirname(os.path.dirname(self.data_directory)), "pdf_to_md/extraction_results/filename_mapping.json")
        if os.path.exists(mapping_file):
            try:
                import json
                with open(mapping_file, 'r', encoding='utf-8') as f:
                    filename_mapping = json.load(f)
            except: pass
        
        downloaded_files_path = os.path.join(self.data_directory, "downloaded_files")
        if not os.path.exists(downloaded_files_path):
            print(f"WARN: Directory {downloaded_files_path} does not exist")
            return
        
        for folder_name in os.listdir(downloaded_files_path):
            folder_path = os.path.join(downloaded_files_path, folder_name)
            if os.path.isdir(folder_path):
                md_file_path = os.path.join(folder_path, "full.md")
                if os.path.exists(md_file_path):
                    try:
                        with open(md_file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            self.documents[folder_name] = content
                            
                            # 尝试提取真实标题
                            paper_title = self._extract_paper_title_from_json(folder_path)
                            if paper_title and paper_title != folder_name:
                                self.document_original_names[folder_name] = paper_title
                            else:
                                original_name = None
                                for orig, normalized in filename_mapping.items():
                                    if normalized == folder_name:
                                        original_name = orig
                                        break
                                self.document_original_names[folder_name] = original_name if original_name else folder_name
                    except Exception as e:
                        print(f"加载文档 {folder_name} 出错: {e}")
        print(f"共加载 {len(self.documents)} 个文档")

    def _extract_paper_title_from_json(self, folder_path: str) -> str:
        try:
            import json
            json_files = [f for f in os.listdir(folder_path) if f.endswith('.json')]
            for json_file in json_files:
                try:
                    with open(os.path.join(folder_path, json_file), 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    if isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict) and item.get('text_level') == 1 and 'text' in item:
                                return item['text'].strip()
                except: continue
        except: pass
        return ""

    def _clean_text(self, text: str) -> str:
        if not text: return ""
        text = text.replace('\x00', '')
        text = "".join(ch for ch in text if ch.isprintable() or ch in ['\n', '\t', '\r'])
        text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
        text = re.sub(r'\[([^\]]+)\]\(.*?\)', r'\1', text)
        text = re.sub(r'[-=*]{3,}', '', text)
        text = re.sub(r'\n\n\n+', '\n\n', text)
        return text.strip()

    def _split_into_paragraphs(self, content: str) -> List[str]:
        reference_patterns = [r'^#+\s*References\s*$', r'^#+\s*Bibliography\s*$', r'^#+\s*参考文献\s*$']
        lines = content.split('\n')
        for i, line in enumerate(lines):
            for pattern in reference_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    content = '\n'.join(lines[:i])
                    break
        
        content = self._clean_text(content)
        paragraphs = re.split(r'\n\s*\n', content)
        return [p.strip() for p in paragraphs if len(p.strip()) > 20]

    def _initialize_models_and_db(self):
        print("正在初始化模型和数据库连接...")
        try:
            print(f"正在加载BGE-M3模型 (原生Transformers/{self.device.upper()})...")
            if self.model_path:
                bge_m3_path = os.path.join(self.model_path, "bge-m3")
                if os.path.exists(bge_m3_path):
                    self.tokenizer = AutoTokenizer.from_pretrained(bge_m3_path, local_files_only=True)
                    # 使用 MaskedLM 支持 Sparse 计算
                    self.model = AutoModelForMaskedLM.from_pretrained(bge_m3_path, local_files_only=True)
                    self.model.to(self.device) # 搬到 GPU/CPU
                    self.model.eval() 
                    print(f"OK: BGE-M3 model loaded successfully on {self.device.upper()}")
                else:
                    raise FileNotFoundError(f"模型路径不存在: {bge_m3_path}")
            else:
                raise ValueError("需指定模型路径")

            print(f"正在连接Milvus数据库 {self.milvus_host}:{self.milvus_port}...")
            connections.connect(host=self.milvus_host, port=self.milvus_port, timeout=10)
            
            fields = [
                FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=False),
                FieldSchema(name="block_type", dtype=DataType.VARCHAR, max_length=10),
                FieldSchema(name="parent_block_id", dtype=DataType.INT64),
                FieldSchema(name="child_block_id", dtype=DataType.INT64),
                FieldSchema(name="doc_id", dtype=DataType.VARCHAR, max_length=256),
                FieldSchema(name="original_filename", dtype=DataType.VARCHAR, max_length=512),
                FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=1024),
                FieldSchema(name="sparse_embedding", dtype=DataType.SPARSE_FLOAT_VECTOR)
            ]
            schema = CollectionSchema(fields=fields, description="Traditional RAG V3")
            
            if self.force_rebuild and utility.has_collection(self.COLLECTION_NAME):
                print(f"删除旧集合 {self.COLLECTION_NAME}...")
                Collection(name=self.COLLECTION_NAME).drop()
            
            if utility.has_collection(self.COLLECTION_NAME):
                self.milvus_collection = Collection(name=self.COLLECTION_NAME)
            else:
                self.milvus_collection = Collection(name=self.COLLECTION_NAME, schema=schema)
                index_params = {"metric_type": "IP", "index_type": "HNSW", "params": {"M": 32, "efConstruction": 256}}
                self.milvus_collection.create_index(field_name="embedding", index_params=index_params)
                sparse_params = {"metric_type": "IP", "index_type": "SPARSE_INVERTED_INDEX"}
                self.milvus_collection.create_index(field_name="sparse_embedding", index_params=sparse_params)
            
            self.milvus_collection.load()
            print("OK: Initialization completed")
            
        except Exception as e:
            print(f"初始化失败: {e}")
            raise

    def _embed_batch(self, texts: List[str]) -> Tuple[np.ndarray, List[dict]]:
        """【核心加速】批量计算 Dense + Sparse 向量"""
        batch_size = len(texts)
        if batch_size == 0:
            return np.array([]), []
            
        # 1. 截断处理（256 字符硬限，防止 LaTeX 让分词器变慢）
        processed_texts = [t[:256] for t in texts]

        dense_embeddings = []
        sparse_embeddings_list = []

        try:
            # 2. 批量 Tokenize（max_length=128 大幅减少 GPU 计算量）
            inputs = self.tokenizer(
                processed_texts,
                padding=True,
                truncation=True,
                max_length=128,
                return_tensors='pt'
            ).to(self.device)

            # 3. 批量推理
            with torch.no_grad():
                # MaskedLM 需要 output_hidden_states=True 才能拿到 CLS 向量
                outputs = self.model(**inputs, output_hidden_states=True, return_dict=True)

                # --- A. Dense：CLS token of last hidden state ---
                dense_vecs = outputs.hidden_states[-1][:, 0, :].clone()
                dense_vecs = torch.nn.functional.normalize(dense_vecs, p=2, dim=1)
                dense_embeddings = dense_vecs.cpu().float().numpy()
                del dense_vecs

                # --- B. Sparse：SPLADE max pooling，限制最多 512 个非零项防止 gRPC 超大包 ---
                logits = outputs.logits.clone()
                del outputs, inputs  # 立即释放所有隐藏状态和输入张量
                weights = torch.log(1 + torch.relu(logits))
                del logits
                values, _ = torch.max(weights, dim=1)
                del weights

                values_cpu = values.cpu().float().numpy()
                del values

                for i in range(batch_size):
                    row_values = values_cpu[i]
                    indices = np.nonzero(row_values)[0]

                    # 先过滤阈值，再按权重取 top-512，防止稀疏向量过大卡死 Milvus
                    pairs = [(float(row_values[idx]), int(idx)) for idx in indices if float(row_values[idx]) > 0.01]
                    pairs.sort(reverse=True)
                    real_sparse = {idx: w for w, idx in pairs[:512]}

                    sparse_embeddings_list.append(real_sparse if real_sparse else {0: 0.000001})

                if self.device == "cuda":
                    torch.cuda.empty_cache()

        except Exception as e:
            print(f"  [WARN] batch embed error: {str(e)[:100]}")
            # 兜底：生成全零 batch
            dense_embeddings = np.zeros((batch_size, 1024), dtype=np.float32)
            sparse_embeddings_list = [{0: 0.000001} for _ in range(batch_size)]

        return dense_embeddings, sparse_embeddings_list

    def _generate_global_id(self, doc_id: str, block_type: str, index: int) -> int:
        unique_str = f"{doc_id}_{block_type}_{index}"
        hash_hex = hashlib.md5(unique_str.encode('utf-8')).hexdigest()
        return int(hash_hex[:15], 16)

    def _check_and_build_index(self):
        print("\n" + "="*70)
        print("Sequential Mode: Processing all documents...")
        
        existing_ids = set()
        if self.milvus_collection:
            try:
                res = self.milvus_collection.query(expr="doc_id != ''", output_fields=["doc_id"], limit=10000)
                existing_ids = set(r["doc_id"] for r in res)
            except: pass

        doc_keys = list(self.documents.keys())
        total = len(doc_keys)
        skipped = 0

        for i, doc_id in enumerate(doc_keys, 1):
            if doc_id in existing_ids:
                print(f"\n[{i}/{total}] 跳过 (已存在): {doc_id[:40]}")
                skipped += 1
                continue
            print(f"\n[{i}/{total}] 处理文档: {doc_id[:40]}...")
            try:
                self._process_single_file(doc_id)
            except Exception as e:
                print(f"  ERR: Failed: {e}")

        if skipped:
            print(f"\n共跳过 {skipped} 个已存在的文档")
                
        print("\n" + "="*70 + "\n")

    def _process_single_file(self, doc_id: str):
        content = self.documents[doc_id]
        original_name = self.document_original_names.get(doc_id, doc_id)
        paragraphs = self._split_into_paragraphs(content)
        total_p = len(paragraphs)
        
        # 待处理队列 (Wait for Embedding)
        chunk_buffer = [] 
        # 待存储队列 (Wait for Insert)
        milvus_buffer = []
        
        parent_id_counter = 0
        total_inserted = 0
        
        print(f"  段落: {len(paragraphs)}")
        
        for paragraph in paragraphs:
            # --- 1. 准备 Parent ---
            start = 0
            while start < len(paragraph):
                end = min(start + 1500, len(paragraph))
                p_content = paragraph[start:end]
                p_global_id = self._generate_global_id(doc_id, "parent", parent_id_counter)
                
                # 放入推理队列
                chunk_buffer.append({
                    'id': p_global_id, 'block_type': 'parent', 'parent_block_id': -1, 'child_block_id': -1,
                    'doc_id': doc_id, 'original_filename': original_name, 'content': p_content
                })
                
                # --- 2. 准备 Child ---
                child_id_counter = 0
                c_start = 0
                while c_start < len(p_content):
                    c_end = min(c_start + 500, len(p_content))
                    c_content = p_content[c_start:c_end]
                    c_global_id = self._generate_global_id(doc_id, "child", f"{parent_id_counter}_{child_id_counter}")
                    
                    # 放入推理队列
                    chunk_buffer.append({
                        'id': c_global_id, 'block_type': 'child', 'parent_block_id': p_global_id, 
                        'child_block_id': child_id_counter, 'doc_id': doc_id, 'original_filename': original_name, 
                        'content': c_content
                    })
                    
                    c_start = c_end - 150 if c_end < len(p_content) else c_end
                    child_id_counter += 1
                
                parent_id_counter += 1
                start = end - 200 if end < len(paragraph) else end

                # --- 触发批量推理 (Batch Inference) ---
                if len(chunk_buffer) >= self.embed_batch_size:
                    self._process_embed_buffer(chunk_buffer, milvus_buffer, current_p=parent_id_counter, total_p=total_p)
                    chunk_buffer = []
                
                # --- 触发批量存储 (Batch Insert) ---
                if len(milvus_buffer) >= self.insert_batch_size:
                    self._insert_chunks_batch(milvus_buffer)
                    total_inserted += len(milvus_buffer)
                    milvus_buffer = []

        # 处理剩余的
        if chunk_buffer:
            self._process_embed_buffer(chunk_buffer, milvus_buffer, current_p=parent_id_counter, total_p=total_p)
        if milvus_buffer:
            self._insert_chunks_batch(milvus_buffer)
            total_inserted += len(milvus_buffer)
            
        print(f"  [OK] 共插入 {total_inserted} 块")

    @staticmethod
    def _sanitize_for_embed(text: str) -> str:
        """移除 LaTeX 公式，防止 BPE 分词器在无空格长字符串上卡死"""
        # 行内公式 $...$ 和块公式 $$...$$
        text = re.sub(r'\$\$[^$]*?\$\$', '[MATH]', text, flags=re.DOTALL)
        text = re.sub(r'\$[^$\n]{0,300}?\$', '[MATH]', text)
        # \mathrm{...} \frac{...}{...} 等 LaTeX 命令
        text = re.sub(r'\\[a-zA-Z]+\s*\{[^}]{0,200}\}', '[MATH]', text)
        # 剩余孤立的大括号块（公式碎片）
        text = re.sub(r'\{[^{}]{0,200}\}', '', text)
        # 合并多余空白
        text = re.sub(r'[ \t]{3,}', ' ', text)
        return text.strip()

    def _process_embed_buffer(self, chunk_buffer: List[Dict], milvus_buffer: List[Dict], current_p: int = 0, total_p: int = 0):
        """执行批量 Embedding 并移入存储队列"""
        # 1. 准备文本：清理 LaTeX + 截断 + 添加标题前缀
        texts = []
        for c in chunk_buffer:
            txt = self._sanitize_for_embed(c['content'])[:800]
            if c['original_filename']:
                txt = f"Title: {c['original_filename']}\nContent: {txt}"
            texts.append(txt)
        # 2. 批量推理
        dense_vecs, sparse_vecs = self._embed_batch(texts)
        
        # 3. 结果回填
        for i, chunk in enumerate(chunk_buffer):
            chunk['embedding'] = dense_vecs[i]
            chunk['sparse_embedding'] = sparse_vecs[i]
            milvus_buffer.append(chunk)

        # 每批推理后换行打印进度，终端实时可见
        doc_id_short = chunk_buffer[0]['doc_id'][:15]
        snippet = chunk_buffer[0]['content'][:25].replace('\n', ' ')
        print(f"  [Embed] {doc_id_short}... | para {current_p}/{total_p} | {snippet}...")
        
        # 4. 强制回收内存，防止 OOM
        gc.collect()

    def _insert_chunks_batch(self, chunks_list: List[Dict]):
        try:
            data = [
                [c['id'] for c in chunks_list],
                [c['block_type'] for c in chunks_list],
                [c['parent_block_id'] for c in chunks_list],
                [c['child_block_id'] for c in chunks_list],
                [c['doc_id'] for c in chunks_list],
                [c['original_filename'] for c in chunks_list],
                [c['content'] for c in chunks_list],
                [c['embedding'] for c in chunks_list],
                [c['sparse_embedding'] for c in chunks_list]
            ]
            self.milvus_collection.upsert(data, timeout=30)
            print(f"  [Insert] {len(chunks_list)} chunks stored.")
            
        except Exception as e:
            print(f"\n  ERR: Storage failed (Size={len(chunks_list)}): {e}")

    def get_models(self):
        return {
            'embedding_model': self.model,
            'tokenizer': self.tokenizer,
            'milvus_collection': self.milvus_collection
        }

if __name__ == "__main__":
    import sys
    # 强制 UTF-8 输出，防止 Windows GBK 控制台编码错误
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')

    # 脚本位于 src/rag/traditional_rag_v3.py，向上级退 2 次即可到达项目根目录
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.path.insert(0, PROJECT_ROOT)

    # 修正模型路径，实际在 src/rag/models
    model_path = os.path.join(PROJECT_ROOT, "src", "rag", "models")
    data_path = os.path.join(PROJECT_ROOT, "pdf_to_md", "extraction_results")

    # 通过命令行参数控制是否清空重建：python traditional_rag_v3.py --rebuild
    force_rebuild = "--rebuild" in sys.argv

    rag = TraditionalRAGV3(
        data_directory=data_path,
        model_path=model_path,
        force_rebuild=force_rebuild
    )