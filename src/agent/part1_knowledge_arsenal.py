"""
Part 1: Assembling the Knowledge Arsenal - 知识武库组装
整合了数据管理、LLM配置、知识库连接、向量化等核心功能

核心模块：
1. DataManager - Markdown文件加载和预处理
2. LLMConfig - GLM API 调用管理（使用硅基流动API）
3. EmbeddingManager - 向量化和Milvus管理
4. KnowledgeBaseConnector - Neo4j 和 Milvus 连接管理
5. KnowledgeArsenal - Part 1 主接口
"""

import os
import sys
import json
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import requests
import logging

# 日志配置（必须在GPU配置之前）
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 项目路径配置
# 此文件在 src/agent/ 目录
# 向上1级到 src/，再上1级到项目根目录
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))  # src/agent/
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))  # d:\flowbd_v5
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# GPU设备配置 - 强制使用CPU（避免CUDA sm_120兼容性问题）
try:
    import torch
    # 自动检测GPU是否可用
    if torch.cuda.is_available():
        DEVICE = torch.device("cuda")
        GPU_AVAILABLE = True
        GPU_NAME = torch.cuda.get_device_name(0)
        logger.info(f"GPU模式 - 使用GPU: {GPU_NAME}")
    else:
        DEVICE = torch.device("cpu")
        GPU_AVAILABLE = False
        GPU_NAME = "N/A"
        logger.info(f"CPU模式 - 未检测到GPU，使用CPU计算")
except ImportError:
    DEVICE = "cpu"
    GPU_AVAILABLE = False
    GPU_NAME = "N/A"
    logger.info(f"CPU模式（PyTorch未声明）")


@dataclass
class KnowledgeSource:
    """知识源元数据"""
    doc_id: str              # 文档ID
    title: str               # 文档标题
    content: str             # 文档内容
    source_type: str         # 源类型: 'markdown' | 'graph' | 'structured'
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None


class LLMConfig:
    """GLM API 配置（通过硅基流动）"""
    
    def __init__(self, api_key: str = None, base_url: str = None, model: str = None):
        """初始化LLM配置
        
        Args:
            api_key: LLM API密钥，默认从环境变量或写死值
            base_url: API端点
            model: 模型名称
        """
        self.api_key = api_key or os.environ.get("MOONSHOT_API_KEY") or __import__("os").environ.get("MOONSHOT_API_KEY", "")
        self.base_url = base_url or "https://api.moonshot.cn/v1"
        self.model = model or "kimi-k2.6"
        self.timeout = (30, 300)  # (连接超时=30秒, 读取超时=300秒=5分钟)
        self.max_retries = 2  # 最多重试2次（保守策略避免限流加重）
        self.retry_delay = 10  # 重试间隔10秒（给API更多恢复时间）
        
        logger.info(f"✓ LLM配置完成 (模型: {self.model}, 端点: {self.base_url}, 超时: {self.timeout}秒)")
        
    def _handle_streaming_response(self, response, on_chunk: callable = None) -> str:
        """处理流式响应 - 实时打印答案内容
        
        Args:
            response: requests.Response对象（流式）
            on_chunk: 【新增】回调函数，接收 chunk 内容
            
        Returns:
            完整的答案文本
        """
        import json
        
        full_answer = ""
        full_reasoning = ""
        reasoning_started = False
        chunk_count = 0
        try:
            for line in response.iter_lines():
                if not line:
                    continue
                
                chunk_count += 1
                # 处理 SSE 格式数据
                if line.startswith(b'data: '):
                    line = line[6:]  # 移除 'data: ' 前缀
                elif isinstance(line, str) and line.startswith('data: '):
                    line = line[6:]
                
                if line == b'[DONE]' or line == '[DONE]':
                    break
                
                try:
                    if isinstance(line, bytes):
                        line = line.decode('utf-8')
                    
                    data = json.loads(line)
                    
                    # 提取流式响应中的内容
                    if 'choices' in data and len(data['choices']) > 0:
                        delta = data['choices'][0].get('delta', {})
                        
                        # 【新增】处理思考过程 (Reasoning Content)
                        reasoning = delta.get('reasoning_content', '')
                        if reasoning:
                            if not reasoning_started:
                                print("\n" + ">" * 30 + " [思考过程] " + ">" * 30 + "\n", end='', flush=True)
                                reasoning_started = True
                            print(reasoning, end='', flush=True)
                            full_reasoning += reasoning
                            continue

                        content = delta.get('content', '')
                        
                        if content:
                            if reasoning_started:
                                print("\n" + "<" * 30 + " [结束思考] " + "<" * 30 + "\n", end='', flush=True)
                                reasoning_started = False
                            
                            # 【关键】实时打印内容，改善用户体感
                            print(content, end='', flush=True)
                            full_answer += content
                            
                            # 【新增】调用回调
                            if on_chunk:
                                on_chunk(content)
                
                except json.JSONDecodeError:
                    # 忽略无效的JSON行
                    pass
            
            if chunk_count == 0:
                logger.warning("⚠️ 流式响应未接收到任何有效数据块")
            
            # 打印换行符完成答案
            print()  # 新起一行
            logger.debug(f"流式返回: {len(full_answer)} 字符")
            return full_answer
        
        except Exception as e:
            logger.error(f"流式响应处理失败: {e}")
            return f"❌ 流式处理异常: {str(e)}"

    def call_llm(self,
                 prompt: str,
                 temperature: float = 0.0,
                 max_tokens: int = 50000,
                 model: str = None,
                 stream: bool = False,
                 system_prompt: str = None,
                 repetition_penalty: float = 1.0,
                 on_chunk: callable = None,
                 on_reasoning: callable = None,
                 **kwargs) -> str:
        """调用Kimi LLM（带重试机制和流式输出）
        
        Args:
            prompt: 提示词
            temperature: 温度参数
            max_tokens: 最大输出token数
            model: 使用的模型
            stream: 是否启用流式输出（流式时实时打印答案）
            system_prompt: 【新增】系统级提示词，用于禁用记忆或设置行为约束
            repetition_penalty: 【新增】重复惩罚参数 (建议 1.05-1.2)
            on_chunk: 【新增】流式块回调函数
            
        Returns:
            LLM返回的文本
        """
        import time
        
        # 【调试日志】不再打印到终端，只保存到文件（通过run_part5_enhanced.py）
        
        for attempt in range(self.max_retries):
            try:
                # 【新增】构建 API URL，处理可能的重复斜杠
                api_url = f"{self.base_url.rstrip('/')}/chat/completions"
                
                # 【新增】处理 Authorization 头部
                # 书生浦语 (InternLM) 某些情况下可能不需要 Bearer 前缀
                auth_header = f"Bearer {self.api_key}"
                if "intern-ai.org.cn" in self.base_url:
                    # 如果 key 已经包含 Bearer (虽然逻辑上不应该)，或者根据 sy.py 的提示
                    auth_header = self.api_key if self.api_key.startswith("Bearer ") else f"Bearer {self.api_key}"
                
                headers = {
                    "Authorization": auth_header,
                    "Content-Type": "application/json"
                }
                # 【新增】构建 messages 列表：支持 system prompt
                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": prompt})

                effective_model = model or self.model
                # 【补丁】Kimi K2.x thinking 系列强制 temperature=1.0
                # 否则 reasoning_content 会吃掉全部 token, content 为空
                effective_temp = temperature
                if isinstance(effective_model, str) and effective_model.startswith("kimi-k2."):
                    effective_temp = 1.0

                data = {
                    "model": effective_model,
                    "messages": messages,  # 【修改】使用动态消息列表
                    "temperature": effective_temp,
                    "max_tokens": max_tokens,
                    "repetition_penalty": repetition_penalty,
                    "stream": stream  # 【新增】启用流式输出
                }
                
                logger.debug(f"调用LLM: {data['model']}, tokens={max_tokens}, stream={stream} (尝试 {attempt+1}/{self.max_retries})")
                
                response = requests.post(
                    api_url,
                    headers=headers,
                    json=data,
                    timeout=self.timeout,
                    stream=stream  # 启用流式接收
                )
                
                if response.status_code == 200:
                    if stream:
                        # 【流式处理】签名容错:
                        #  - 原生方法接受 (response, on_chunk)
                        #  - app2.py 的 monkey patch 只吃 (response), 靠 session_state 传值
                        #  - 未来若加 on_reasoning, 优先尝试完整签名
                        try:
                            return self._handle_streaming_response(
                                response, on_chunk=on_chunk, on_reasoning=on_reasoning)
                        except TypeError:
                            try:
                                return self._handle_streaming_response(
                                    response, on_chunk=on_chunk)
                            except TypeError:
                                return self._handle_streaming_response(response)
                    else:
                        # 非流式处理
                        try:
                            response_json = response.json()
                            # 检查choices列表是否为空
                            if 'choices' not in response_json or not response_json['choices']:
                                error_msg = f"❌ GLM返回异常: choices列表为空"
                                logger.error(error_msg)
                                return error_msg
                            
                            # 【新增】打印并返回思考过程 (Reasoning Content)
                            message = response_json['choices'][0]['message']
                            reasoning = message.get('reasoning_content', '')
                            if reasoning:
                                print("\n" + ">" * 30 + " [GLM 思考过程] " + ">" * 30)
                                print(reasoning)
                                print("<" * 30 + " [结束思考] " + "<" * 30 + "\n")
                            
                            result = message['content'].strip()
                            logger.debug(f"GLM返回: {len(result)} 字符")
                            return result
                        except (KeyError, IndexError) as e:
                            error_msg = f"❌ GLM响应解析失败: {str(e)}"
                            logger.error(error_msg)
                            return error_msg
                elif response.status_code == 429:  # Too Many Requests
                    if attempt < self.max_retries - 1:
                        # 429限流：使用更长的等待时间，避免继续冲击API
                        wait_time = 20 + self.retry_delay * (2 ** attempt)  # 基础20秒+指数退避
                        logger.warning(f"⚠️  GLM限流 (429)，{wait_time}秒后重试...")
                        time.sleep(wait_time)
                        continue
                    else:
                        error_msg = f"❌ GLM调用失败 (429-已重试{self.max_retries}次，API服务器限流)"
                        logger.error(error_msg)
                        return error_msg
                else:
                    error_msg = f"❌ GLM调用失败 ({response.status_code})"
                    logger.error(error_msg)
                    return error_msg
                    
            except requests.exceptions.Timeout as e:
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)
                    logger.warning(f"⚠️  GLM超时，{wait_time}秒后重试... (错误: {str(e)[:100]})")
                    time.sleep(wait_time)
                    continue
                else:
                    error_msg = f"❌ GLM调用超时（已重试{self.max_retries}次）: {str(e)[:100]}"
                    logger.error(error_msg)
                    return error_msg
            except requests.exceptions.ConnectionError as e:
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)
                    logger.warning(f"⚠️  网络连接失败，{wait_time}秒后重试... (错误: {str(e)[:100]})")
                    time.sleep(wait_time)
                    continue
                else:
                    error_msg = f"❌ 网络连接失败（已重试{self.max_retries}次）: {str(e)[:100]}"
                    logger.error(error_msg)
                    return error_msg
            except Exception as e:
                error_msg = f"❌ GLM调用异常: {str(e)}"
                logger.error(error_msg)
                return error_msg
        
        return f"❌ GLM调用失败（已重试{self.max_retries}次）"

class InternLMConfig(LLMConfig):
    """书生·浦语 (InternLM) API 配置"""
    
    def __init__(self, api_key: str = None, base_url: str = None, model: str = None):
        """初始化InternLM配置"""
        # 使用sy.py中的默认配置
        self.api_key = api_key or __import__("os").environ.get("MOONSHOT_API_KEY", "")
        self.base_url = base_url or "https://api.moonshot.cn/v1"
        self.model = model or "kimi-k2.6"
        self.timeout = (30, 300)
        self.max_retries = 2
        self.retry_delay = 10
        
        logger.info(f"✓ InternLM配置完成 (模型: {self.model}, 端点: {self.base_url})")
    
    def call_llm(self, *args, **kwargs) -> str:
        """调用InternLM（继承自LLMConfig，逻辑通用）"""
        return super().call_llm(*args, **kwargs)
    
class ParallelLLMManager:
    """并行LLM管理器 - 支持8个GLM API并行调用"""
    
    def __init__(self, api_keys: List[str] = None):
        """初始化并行LLM管理器
        
        Args:
            api_keys: API密钥列表，默认使用8个硅基流动GLM密钥
        """
        if api_keys is None:
            # 【切换】原 8 个硅基流动 key 全部欠费失效, 复用同一个 Moonshot key
            # Moonshot 单 key 并发限速由服务端 QPS 控制, 冲高并发时会 429 重试
            _moonshot_key = __import__("os").environ.get("MOONSHOT_API_KEY", "")
            api_keys = [_moonshot_key] * 8
        
        self.api_keys = api_keys
        self.llms = []
        for i, api_key in enumerate(api_keys, 1):
            llm = LLMConfig(api_key=api_key)
            self.llms.append(llm)
            logger.info(f"✓ 并行LLM-{i} 初始化完成")
        
        self.call_count = 0  # 追踪调用次数
        logger.info(f"✓ 并行LLM管理器已配置8个GLM API密钥")
    
    def call_llm_async(self, prompt: str, temperature: float = 0.0, max_tokens: int = 50000,
                       model: str = None, stream: bool = False, llm_index: int = 0,
                       repetition_penalty: float = 1.0) -> str:
        """同步模式的"异步"调用（实际是顺序调用）
        
        Args:
            prompt: 提示词
            temperature: 温度参数
            max_tokens: 最大输出token数
            model: 使用的模型
            stream: 是否启用流式输出
            llm_index: 使用的LLM索引 (0-7)
            repetition_penalty: 重复惩罚参数
            
        Returns:
            LLM返回的文本
        """
        if llm_index >= len(self.llms):
            llm_index = llm_index % len(self.llms)
        
        self.call_count += 1
        logger.info(f"[GLM-{llm_index+1}] 第{self.call_count}次并行调用")
        
        return self.llms[llm_index].call_llm(
            prompt=prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            model=model,
            stream=stream,
            repetition_penalty=repetition_penalty
        )
    
    def call_llm_parallel(self, prompts: List[str], temperatures: List[float] = None,
                         max_tokens: int = 50000, model: str = None,
                         stream: bool = False, repetition_penalties: List[float] = None) -> List[str]:
        """真正的并行调用 - 使用threading并发多个LLM
        
        Args:
            prompts: 多个提示词列表（最多8个）
            temperatures: 温度参数列表
            max_tokens: 最大输出token数
            model: 使用的模型
            stream: 是否启用流式输出
            repetition_penalties: 重复惩罚参数列表
            
        Returns:
            返回结果列表，与输入prompts的长度相同
        """
        import threading
        
        if temperatures is None:
            temperatures = [0.0] * len(prompts)
        
        if repetition_penalties is None:
            repetition_penalties = [1.0] * len(prompts)
        
        # 限制最多8个并行任务
        num_prompts = min(len(prompts), len(self.llms))
        prompts = prompts[:num_prompts]
        temperatures = temperatures[:num_prompts]
        repetition_penalties = repetition_penalties[:num_prompts]
        
        results = [None] * len(prompts)
        threads = []
        
        def call_llm_task(index, prompt, temperature, r_penalty):
            """单个LLM调用任务"""
            try:
                result = self.llms[index].call_llm(
                    prompt=prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    model=model,
                    stream=stream,
                    repetition_penalty=r_penalty
                )
                results[index] = result
                logger.info(f"[GLM-{index+1}] 调用完成 (获得{len(result)}字符)")
            except Exception as e:
                logger.error(f"[GLM-{index+1}] 调用失败: {e}")
                results[index] = f"❌ GLM-{index+1} 调用失败: {str(e)}"
        
        # 启动并行线程
        logger.info(f"🚀 启动{num_prompts}个并行GLM调用")
        for i in range(num_prompts):
            t = threading.Thread(
                target=call_llm_task,
                args=(i, prompts[i], temperatures[i], repetition_penalties[i])
            )
            t.start()
            threads.append(t)
        
        # 等待所有线程完成
        for t in threads:
            t.join()
        
        logger.info(f"✓ 所有{num_prompts}个并行GLM调用完成")
        return results[:len(prompts)]


class DataManager:
    """数据管理器 - 处理Markdown文件加载和预处理"""
    
    def __init__(self, md_folder: str = None):
        """初始化数据管理器
        
        Args:
            md_folder: Markdown文件夹路径，默认为项目的转换输出目录
        """
        if md_folder is None:
            md_folder = os.path.join(
                PROJECT_ROOT, 
                "pdf_to_md", 
                "extraction_results", 
                "downloaded_files"
            )
        
        self.md_folder = md_folder
        self.documents: Dict[str, KnowledgeSource] = {}
        logger.info(f"✓ 数据管理器初始化 (文件夹: {md_folder})")
        
    def load_markdown_files(self) -> Dict[str, KnowledgeSource]:
        """加载Markdown文件 - 使用懒加载避免内存溢出"""
        logger.info(f"📂 扫描Markdown文件: {self.md_folder}")
        
        if not os.path.exists(self.md_folder):
            logger.warning(f"⚠️ 文件夹不存在: {self.md_folder}")
            return {}
        
        md_files = []
        for root, dirs, files in os.walk(self.md_folder):
            for file in files:
                if file.endswith('.md') and file == 'full.md':
                    md_files.append(os.path.join(root, file))
        
        logger.info(f"  找到 {len(md_files)} 个Markdown文件")
        
        for idx, filepath in enumerate(md_files, 1):
            try:
                parent_folder = os.path.basename(os.path.dirname(filepath))
                logger.info(f"  [{idx}/{len(md_files)}] 正在加载 {parent_folder}...")
                
                # 获取文件大小
                file_size = os.path.getsize(filepath)
                logger.info(f"      ⚡ 文件大小: {file_size//1024}KB")
                
                # 只读取前部分内容用于提取标题和元数据
                with open(filepath, 'r', encoding='utf-8') as f:
                    # 只读前5000字符来提取标题
                    preview_content = f.read(5000)
                
                # 从内容中提取标题
                title = self._extract_title(preview_content) or parent_folder
                logger.info(f"      ⚡ 标题: {title[:50]}")
                
                # 不读取完整内容，只存储文件路径和元数据
                # 块数通过文件大小估算
                estimated_chunks = file_size // 1000
                logger.info(f"      ⚡ 估算块数: {estimated_chunks}")
                
                # 创建KnowledgeSource，但不加载完整内容
                source = KnowledgeSource(
                    doc_id=parent_folder,
                    title=title,
                    content="",  # 不加载完整内容到内存
                    source_type="markdown",
                    metadata={
                        "filepath": filepath,
                        "folder": parent_folder,
                        "file_size": file_size,
                        "chunks": estimated_chunks,
                        "loaded_at": datetime.now().isoformat(),
                        "lazy_loaded": True  # 标记为懒加载
                    }
                )
                
                self.documents[parent_folder] = source
                logger.info(f"  ✓ 加载完成: {title}")
                
            except Exception as e:
                logger.error(f"  ❌ 加载失败 {filepath}: {e}")
        
        logger.info(f"\n✅ 共扫描 {len(self.documents)} 个文档\n")
        return self.documents
    
    def load_document_content(self, doc_id: str, chunk_size: int = 1000) -> List[str]:
        """按需加载文档内容并分块 - 用于检索时调用"""
        source = self.documents.get(doc_id)
        if not source:
            return []
        
        try:
            filepath = source.metadata.get('filepath')
            if not filepath:
                return []
            
            # 流式读取并分块，避免一次性加载大文件
            chunks = []
            with open(filepath, 'r', encoding='utf-8') as f:
                buffer = ""
                while True:
                    # 每次读1MB
                    chunk_data = f.read(1024 * 1024)
                    if not chunk_data:
                        if buffer:
                            chunks.append(buffer)
                        break
                    
                    buffer += chunk_data
                    
                    # 当缓冲区足够大时，进行分块
                    while len(buffer) >= chunk_size:
                        chunks.append(buffer[:chunk_size])
                        buffer = buffer[chunk_size - 100:]  # 保留重叠部分
            
            logger.info(f"✓ 已流式加载文档 {doc_id}: {len(chunks)} 块")
            return chunks
            
        except Exception as e:
            logger.error(f"❌ 流式加载失败 {doc_id}: {e}")
            return []

    def _extract_title(self, content: str) -> Optional[str]:
        """从Markdown内容中提取标题"""
        lines = content.split('\n')
        for line in lines[:20]:  # 只查看前20行
            if line.startswith('# '):
                return line.replace('# ', '').strip()
        return None
    
    def _chunk_document(self, content: str, chunk_size: int = 1000, overlap: int = 100) -> List[str]:
        """分割文档为块用于向量化
        
        Args:
            content: 文档内容
            chunk_size: 块大小
            overlap: 块间重叠
            
        Returns:
            分割后的块列表
        """
        chunks = []
        start = 0
        while start < len(content):
            end = min(start + chunk_size, len(content))
            chunks.append(content[start:end])
            start = end - overlap
        return chunks
    
    def get_document(self, doc_id: str) -> Optional[KnowledgeSource]:
        """获取单个文档"""
        return self.documents.get(doc_id)
    
    def get_all_documents(self) -> List[KnowledgeSource]:
        """获取所有文档"""
        return list(self.documents.values())


class EmbeddingManager:
    """向量化管理 - 处理文本向量化"""
    
    def __init__(self, embedding_model=None, embedding_tokenizer=None):
        """初始化向量化管理器
        
        Args:
            embedding_model: BGE-M3模型
            embedding_tokenizer: 对应的tokenizer
        """
        self.embedding_model = embedding_model
        self.embedding_tokenizer = embedding_tokenizer
        logger.info(f"✓ 向量化管理器初始化")
        
    def embed_text(self, text: str) -> Optional[List[float]]:
        """对文本进行向量化"""
        if not self.embedding_model or not self.embedding_tokenizer:
            logger.warning("⚠️ 向量化模型未加载")
            return None
        
        try:
            import torch
            import numpy as np
            
            # 将模型移到设备(一次性)
            if not hasattr(self, '_device_set'):
                self.embedding_model = self.embedding_model.to(DEVICE)
                self._device_set = True
            
            inputs = self.embedding_tokenizer(
                text,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=512
            )
            
            # 将输入移到设备
            inputs = {k: v.to(DEVICE) for k, v in inputs.items()}
            
            with torch.no_grad():
                outputs = self.embedding_model(**inputs)
                # 提取[CLS]令符作为embedding
                embedding = outputs.last_hidden_state[:, 0, :].cpu().numpy().flatten()
            
            # L2归一化
            embedding = embedding / (np.linalg.norm(embedding) + 1e-8)
            
            # 清理GPU中间结果
            if GPU_AVAILABLE:
                torch.cuda.empty_cache()
            
            return embedding.tolist()
            
        except Exception as e:
            logger.error(f"向量化失败: {e}")
            return None


def ensure_milvus_loaded(collection, timeout: int = 300) -> None:
    """确保Milvus集合已加载到内存，带超时

    异步触发加载并等待完成，避免同步load()长时间阻塞初始化。
    超时或失败时抛出RuntimeError，附带可操作的诊断提示。
    """
    from pymilvus import utility

    name = collection.name
    state = utility.load_state(name)
    if state.name == "Loaded":
        return
    if state.name == "NotLoad":
        collection.load(_async=True)
    logger.info(f"⏳ 等待Milvus集合加载: {name} (超时{timeout}s)")
    try:
        utility.wait_for_loading_complete(name, timeout=timeout)
    except Exception as e:
        raise RuntimeError(
            f"Milvus集合 {name} 加载超时({timeout}s): {e}\n"
            f"建议: 执行 Collection('{name}').release() 后重启 milvus-standalone 容器再试"
        )
    if utility.load_state(name).name != "Loaded":
        raise RuntimeError(f"Milvus集合 {name} 加载失败，当前状态: {utility.load_state(name)}")


class KnowledgeBaseConnector:
    """知识库连接器 - 管理Milvus和Neo4j连接"""
    
    def __init__(self,
                 milvus_host: str = "localhost",
                 milvus_port: int = 19530,
                 neo4j_uri: str = "bolt://localhost:7687",
                 neo4j_user: str = "neo4j",
                 neo4j_password: str = "neo4j"):
        """初始化知识库连接器"""
        self.milvus_host = milvus_host
        self.milvus_port = milvus_port
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password
        
        # 连接对象
        self.milvus_client = None
        self.milvus_collection = None
        self.neo4j_driver = None
        
        logger.info(f"✓ 知识库连接器初始化")
        
    def init_milvus(self) -> bool:
        """初始化Milvus连接"""
        try:
            from pymilvus import Collection, connections
            
            logger.info(f"🔗 连接Milvus: {self.milvus_host}:{self.milvus_port}")
            connections.connect("default",
                              host=self.milvus_host,
                              port=self.milvus_port)
            
            # 加载传统 RAG集合（异步加载，避免阻塞初始化；检索前由 ensure_milvus_loaded 等待完成）
            try:
                from rag.sparse_encoding import active_collection
                collection_name = active_collection()
                self.milvus_collection = Collection(name=collection_name)
                self.milvus_collection.load(_async=True)
                
                logger.info(f"✓ Milvus连接成功")
                logger.info(f"  集合: {collection_name}")
                logger.info(f"  加载方式: 异步（首次检索前等待就绪）")
                return True
                
            except Exception as e:
                logger.warning(f"⚠️ 无法加载集合: {e}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Milvus初始化失败: {e}")
            return False
    
    def init_neo4j(self) -> bool:
        """初始化Neo4j连接"""
        try:
            from neo4j import GraphDatabase, basic_auth
            
            logger.info(f"🔗 连接Neo4j: {self.neo4j_uri}")
            self.neo4j_driver = GraphDatabase.driver(
                self.neo4j_uri,
                auth=basic_auth(self.neo4j_user, self.neo4j_password),
                encrypted=False
            )
            
            # 测试连接
            with self.neo4j_driver.session() as session:
                session.run("RETURN 1").consume()
            
            logger.info(f"✓ Neo4j连接成功")
            return True
            
        except Exception as e:
            logger.warning(f"⚠️ Neo4j初始化失败: {e}")
            return False
    
    def query_neo4j(self, cypher: str) -> List[Dict]:
        """执行Neo4j查询"""
        if not self.neo4j_driver:
            return []
        
        try:
            with self.neo4j_driver.session() as session:
                result = session.run(cypher)
                return [dict(record) for record in result]
        except Exception as e:
            logger.error(f"Neo4j查询失败: {e}")
            return []
    
    def search_milvus(self, query_vector: List[float], top_k: int = 5) -> List[Dict]:
        """从Milvus搜索"""
        if not self.milvus_collection:
            return []
        
        try:
            # 异步加载模式下，搜索前确保集合已加载完成
            ensure_milvus_loaded(self.milvus_collection)
        except RuntimeError as e:
            logger.error(f"Milvus集合未就绪: {e}")
            return []
        
        try:
            search_params = {"metric_type": "IP", "params": {"nprobe": 10}}
            results = self.milvus_collection.search(
                data=[query_vector],
                anns_field="embedding",
                param=search_params,
                limit=top_k,
                output_fields=["content", "doc_id", "parent_block_id"]
            )
            
            documents = []
            for hits in results:
                for hit in hits:
                    documents.append({
                        "content": hit.entity.get("content", ""),
                        "doc_id": hit.entity.get("doc_id", ""),
                        "distance": hit.distance,
                        "parent_block_id": hit.entity.get("parent_block_id", "")
                    })
            
            return documents
            
        except Exception as e:
            logger.error(f"Milvus搜索失败: {e}")
            return []
    
    def close(self):
        """关闭所有连接"""
        if self.neo4j_driver:
            self.neo4j_driver.close()
            logger.info("✓ Neo4j连接已关闭")


class KnowledgeArsenal:
    """知识武库 - Part 1 主接口"""
    
    def __init__(self,
                 api_key: str = None,
                 md_folder: str = None,
                 milvus_host: str = "localhost",
                 milvus_port: int = 19530,
                 neo4j_uri: str = "bolt://localhost:7687",
                 neo4j_user: str = "neo4j",
                 neo4j_password: str = "neo4j",
                 embedding_model=None,
                 embedding_tokenizer=None,
                 reranker_model=None,
                 reranker_tokenizer=None):
        """初始化知识武库"""
        
        print("\n" + "="*80)
        print("📚 Part 1: Assembling the Knowledge Arsenal - 知识武库组装 (GLM)")
        print("="*80 + "\n")
        
        # 初始化各组件 - 使用GLM API
        self.llm = LLMConfig(api_key)
        self.data_manager = DataManager(md_folder)
        
        # 自动加载BGE-M3模型（如果未提供）
        if embedding_model is None or embedding_tokenizer is None:
            logger.info("🔄 从本地路径加载BGE-M3模型...")  # 向量化模型，独立于LLM
            try:
                from transformers import AutoTokenizer, AutoModel
                import os
                
                # 本地模型路径
                model_path = os.path.join(PROJECT_ROOT, "src", "rag", "models", "bge-m3")
                
                if not os.path.exists(model_path):
                    logger.warning(f"  ⚠️ 模型路径不存在: {model_path}")
                    logger.warning("  将使用降级模式运行（不进行向量化）")
                    embedding_model = None
                    embedding_tokenizer = None
                else:
                    embedding_model = AutoModel.from_pretrained(
                        model_path,
                        trust_remote_code=True,
                        local_files_only=True
                    )
                    embedding_tokenizer = AutoTokenizer.from_pretrained(
                        model_path,
                        trust_remote_code=True,
                        local_files_only=True
                    )
                    logger.info("  ✓ BGE-M3 模型加载成功")
            except Exception as e:
                logger.warning(f"  ⚠️ BGE-M3 模型加载失败: {str(e)[:100]}")
                logger.warning("  将使用降级模式运行（不进行向量化）")
                embedding_model = None
                embedding_tokenizer = None
        
        self.embedding_manager = EmbeddingManager(embedding_model, embedding_tokenizer)
        self.kb_connector = KnowledgeBaseConnector(
            milvus_host=milvus_host,
            milvus_port=milvus_port,
            neo4j_uri=neo4j_uri,
            neo4j_user=neo4j_user,
            neo4j_password=neo4j_password
        )
        
        # 自动加载BGE-Reranker模型（如果未提供）- Reranker模型，独立于LLM
        if reranker_model is None or reranker_tokenizer is None:
            logger.info("🔄 从本地路径加载BGE-Reranker模型...")
            try:
                from transformers import AutoTokenizer, AutoModelForSequenceClassification
                import os
                
                # 本地模型路径
                reranker_path = os.path.join(PROJECT_ROOT, "src", "rag", "models", "bge-reranker-base")
                
                if not os.path.exists(reranker_path):
                    logger.warning(f"  ⚠️ Reranker模型路径不存在: {reranker_path}")
                    logger.warning("  将使用降级模式运行（不进行Reranking）")
                    reranker_model = None
                    reranker_tokenizer = None
                else:
                    reranker_model = AutoModelForSequenceClassification.from_pretrained(
                        reranker_path,
                        trust_remote_code=True,
                        local_files_only=True
                    )
                    reranker_tokenizer = AutoTokenizer.from_pretrained(
                        reranker_path,
                        trust_remote_code=True,
                        local_files_only=True
                    )
                    logger.info("  ✓ BGE-Reranker 模型加载成功")
            except Exception as e:
                logger.warning(f"  ⚠️ BGE-Reranker 模型加载失败: {str(e)[:100]}")
                logger.warning("  将使用降级模式运行（不进Reranking）")
                reranker_model = None
                reranker_tokenizer = None
        
        # 存储Reranker模型引用
        self.reranker_model = reranker_model
        self.reranker_tokenizer = reranker_tokenizer
        
        # 初始化知识库连接
        self._init_knowledge_bases()
    
    def _init_knowledge_bases(self):
        """初始化所有知识库连接"""
        print("\n🔧 初始化知识库连接（GLM模式）...\n")
        
        milvus_ok = self.kb_connector.init_milvus()
        neo4j_ok = self.kb_connector.init_neo4j()
        
        print()
        
        self.milvus_available = milvus_ok
        self.neo4j_available = neo4j_ok
    
    def assemble(self) -> bool:
        """组装知识武库的所有组件"""
        print("\n🔨 组装知识武库组件...\n")
        
        # 步骤1: 加载Markdown文档
        print("[步骤1] 加载Markdown文档")
        print("-" * 60)
        documents = self.data_manager.load_markdown_files()
        
        if not documents:
            logger.warning("⚠️ 未加载到任何文档")
            return False
        
        print(f"\n✅ 第1步完成 - 已加载 {len(documents)} 个文档\n")
        
        # 步骤2: 生成组装报告
        print("[步骤2] 生成组装报告")
        print("-" * 60)
        report = self._generate_assembly_report(documents)
        print(report)
        
        print("\n✅ 第2步完成\n")
        print("=" * 80)
        print("✅ 知识武库组装完成（已切换至GLM）！")
        print("=" * 80 + "\n")
        
        return True
    
    def _generate_assembly_report(self, documents: Dict[str, KnowledgeSource]) -> str:
        """生成组装报告"""
        report = []
        
        # 文档统计
        report.append("📄 文档库统计:")
        report.append(f"  • 已加载文档数: {len(documents)}")
        
        total_chars = sum(len(doc.content) for doc in documents.values())
        report.append(f"  • 总内容字符数: {total_chars:,}")
        report.append(f"\n  文档清单:")
        
        for doc_id, doc in documents.items():
            char_count = len(doc.content)
            chunk_count = doc.metadata.get('chunks', 0)
            report.append(f"    - {doc.title}")
            report.append(f"      ID: {doc_id}")
            report.append(f"      大小: {char_count:,} 字符, {chunk_count} 块")
        
        # 知识库状态
        report.append(f"\n🗄️ 知识库状态:")
        report.append(f"  • Milvus: {'✓ 可用' if self.milvus_available else '✗ 不可用'}")
        if self.milvus_available and self.kb_connector.milvus_collection:
            num = self.kb_connector.milvus_collection.num_entities
            report.append(f"    (数据: {num:,} 条)")
        
        report.append(f"  • Neo4j: {'✓ 可用' if self.neo4j_available else '✗ 不可用'}")
        
        # LLM状态
        report.append(f"\n🤖 LLM配置:")
        report.append(f"  • 模型: {self.llm.model}")
        report.append(f"  • 供应商: 硅基流动 (SiliconFlow API)")
        
        return "\n".join(report)
    
    def get_documents(self) -> List[KnowledgeSource]:
        """获取所有已加载的文档"""
        return self.data_manager.get_all_documents()
    
    def get_llm(self) -> LLMConfig:
        """获取LLM配置对象"""
        return self.llm
    
    def get_kb_connector(self) -> KnowledgeBaseConnector:
        """获取知识库连接器"""
        return self.kb_connector
    
    def get_embedding_manager(self) -> EmbeddingManager:
        """获取向量化管理器"""
        return self.embedding_manager
    
    def get_reranker_model(self):
        """获取Reranker模型"""
        return self.reranker_model
    
    def get_reranker_tokenizer(self):
        """获取Reranker tokenizer"""
        return self.reranker_tokenizer
    
    def close(self):
        """关闭所有资源"""
        self.kb_connector.close()
        logger.info("✓ 知识武库已关闭")


if __name__ == "__main__":
    # 测试代码
    arsenal = KnowledgeArsenal()
    arsenal.assemble()
    
    # 显示已加载的文档
    docs = arsenal.get_documents()
    print(f"\n📦 已加载 {len(docs)} 个文档:")
    for doc in docs:
        print(f"  • {doc.title}")
    
    arsenal.close()
