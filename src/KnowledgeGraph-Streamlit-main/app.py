import streamlit as st
import json
import re
import sys
import os
import copy
import hashlib
import html
import math

# 【核心修复】解决程序崩溃与网络连接问题
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
# 彻底清理无效的代理环境变量（防止 requests 误将其识别为有效代理导致 SiliconFlow 连接失败）
for key in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]:
    if key in os.environ:
        del os.environ[key]

import threading
import time
import traceback
import llm_utils
import utils
from utils import generate_graph_data, get_local_ip
from llm_utils import call_llm
from streamlit_agraph import agraph, Node, Edge, Config
from streamlit.runtime.scriptrunner import add_script_run_ctx
import streamlit.components.v1 as components

# 图标 URL 数据 (用于按钮背景 - 采用标准编码以确保显示)
SVG_MSG_PLUS = "data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 width=%2224%22 height=%2224%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22white%22 stroke-width=%222%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22%3E%3Cpath d=%22M2.992 16.342a2 2 0 0 1 .094 1.167l-1.065 3.29a1 1 0 0 0 1.236 1.168l3.413-.998a2 2 0 0 1 1.099.092 10 10 0 1 0-4.777-4.719%22/%3E%3Cpath d=%22M8 12h8%22/%3E%3Cpath d=%22M12 8v8%22/%3E%3C/svg%3E"
# 用户自定义头像 (SVG Data URI, stroke设置为 #E6E6E6 琥珀色以匹配主题)
USER_AVATAR_SVG = "data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 width=%2224%22 height=%2224%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22%230f766e%22 stroke-width=%222%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22 class=%22lucide lucide-user-search-icon lucide-user-search%22%3E%3Ccircle cx=%2210%22 cy=%227%22 r=%224%22/%3E%3Cpath d=%22M10.3 15H7a4 4 0 0 0-4 4v2%22/%3E%3Ccircle cx=%2217%22 cy=%2217%22 r=%223%22/%3E%3Cpath d=%22m21 21-1.9-1.9%22/%3E%3C/svg%3E"
# 助手自定义头像 (SVG Data URI, stroke设置为 #E6E6E6)
ASSISTANT_AVATAR_SVG = "data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 width=%2224%22 height=%2224%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22%230f766e%22 stroke-width=%222%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22 class=%22lucide lucide-bot-message-square-icon lucide-bot-message-square%22%3E%3Cpath d=%22M12 6V2H8%22/%3E%3Cpath d=%22M15 11v2%22/%3E%3Cpath d=%22M2 12h2%22/%3E%3Cpath d=%22M20 12h2%22/%3E%3Cpath d=%22M20 16a2 2 0 0 1-2 2H8.828a2 2 0 0 0-1.414.586l-2.202 2.202A.71.71 0 0 1 4 20.286V8a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2z%22/%3E%3Cpath d=%22M9 11v2%22/%3E%3C/svg%3E"

# 配置Agent系统路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Lucide 图标集 (SVG)
ICON_CLOCK = '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle; margin-right: 8px;"><path d="M12 6v6l4 2"/><circle cx="12" cy="12" r="10"/></svg>'
ICON_SETTINGS = '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle; margin-right: 8px;"><path d="M9.671 4.136a2.34 2.34 0 0 1 4.659 0 2.34 2.34 0 0 0 3.319 1.915 2.34 2.34 0 0 1 2.33 4.033 2.34 2.34 0 0 0 0 3.831 2.34 2.34 0 0 1-2.33 4.033 2.34 2.34 0 0 0-3.319 1.915 2.34 2.34 0 0 1-4.659 0 2.34 2.34 0 0 0-3.32-1.915 2.34 2.34 0 0 1-2.33-4.033 2.34 2.34 0 0 0 0-3.831A2.34 2.34 0 0 1 6.35 6.051a2.34 2.34 0 0 0 3.319-1.915"/><circle cx="12" cy="12" r="3"/></svg>'
ICON_PLUS = '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle; margin-right: 8px;"><path d="M22 17a2 2 0 0 1-2 2H6.828a2 2 0 0 0-1.414.586l-2.202 2.202A.71.71 0 0 1 2 21.286V5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2z"/><path d="M12 8v6"/><path d="M9 11h6"/></svg>'
ICON_BRAIN = '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle; margin-right: 8px;"><path d="M12 18V5"/><path d="M15 13a4.17 4.17 0 0 1-3-4 4.17 4.17 0 0 1-3 4"/><path d="M17.598 6.5A3 3 0 1 0 12 5a3 3 0 1 0-5.598 1.5"/><path d="M17.997 5.125a4 4 0 0 1 2.526 5.77"/><path d="M18 18a4 4 0 0 0 2-7.464"/><path d="M19.967 17.483A4 4 0 1 1 12 18a4 4 0 1 1-7.967-.517"/><path d="M6 18a4 4 0 0 1-2-7.464"/><path d="M6.003 5.125a4 4 0 0 0-2.526 5.77"/></svg>'
ICON_SETTINGS2 = '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle; margin-right: 8px;"><path d="M14 17H5"/><path d="M19 7h-9"/><circle cx="17" cy="17" r="3"/><circle cx="7" cy="7" r="3"/></svg>'
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))  
SRC_DIR = os.path.join(PROJECT_ROOT, 'src')
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

# 关键：必须显式加入 agent 目录，确保多入口下的兼容性
AGENT_DIR = os.path.join(SRC_DIR, 'agent')
if AGENT_DIR not in sys.path:
    sys.path.insert(0, AGENT_DIR)

# ========== 猴子补丁 (Monkey Patch) 前置注入 ==========
# 必须在导入 MultiTurnConversation 之前应用补丁，以防止模块路径冲突
from agent.part1_knowledge_arsenal import LLMConfig

def patched_handle_streaming_response(self, response, on_chunk: callable = None, on_reasoning: callable = None) -> str:
    full_answer = ""
    full_reasoning = ""
    reasoning_started = False
    is_answer_mode = False 
    
    # 定义终端标识符（与后端保持 100% 一致）
    THINK_START = "\n" + ">" * 30 + " [GLM 思考过程] " + ">" * 30 + "\n"
    THINK_END = "\n" + "<" * 30 + " [结束思考] " + "<" * 30 + "\n\n"
    
    try:
        for line in response.iter_lines():
            if not line: continue
            if line.startswith(b'data: '): line = line[6:]
            if line == b'[DONE]': break
            try:
                data = json.loads(line)
                if 'choices' in data and len(data['choices']) > 0:
                    delta = data['choices'][0].get('delta', {})
                    
                    reasoning = delta.get('reasoning_content', '')
                    content = delta.get('content', '')

                    # 【重构】严格分离: reasoning_content 永远归"深度思考", content 永远归"正文"
                    # 原来那套 "reasoning 里出现 [Ref- 就切入回答模式" 的启发式会让
                    # K2.6 等 thinking 模型的草稿泄漏到答案流, 现在禁用
                    if content and not is_answer_mode:
                        is_answer_mode = True
                        if reasoning_started:
                            print(THINK_END, end='', flush=True)
                            reasoning_started = False

                    if reasoning:
                        if not reasoning_started:
                            print(THINK_START, end='', flush=True)
                            reasoning_started = True
                        full_reasoning += reasoning
                        try: st.session_state.streaming_reasoning += reasoning
                        except: pass
                        print(reasoning, end='', flush=True)
                        if on_reasoning: on_reasoning(reasoning)
                        continue

                    if content:
                        full_answer += content
                        try: st.session_state.streaming_answer += content
                        except: pass
                        print(content, end='', flush=True)
                        if on_chunk: on_chunk(content)
            except Exception:
                pass
        
        # 4. 结果收尾与最终打印
        if reasoning_started:
            print(THINK_END, end='', flush=True)
        
        # 补齐最后的换行，对齐后端手感
        print() 
            
        final_ret = full_answer if full_answer.strip() else full_reasoning
        return final_ret
    except Exception as e:
        print(f"\n❌ [补丁流] 核心异常: {e}")
        return ""

# 补丁 2: 强化电池类型识别 (修复 RAG 检索为空、回答“无法回答”的问题)
def patched_identify_battery_type(title, debug=False):
    if not title: return 'other'
    t = str(title).lower()
    # 对铁铬电池电解液配方进行强诱导识别
    if any(kw in t for kw in ["铁", "铬", "iron", "chromium"]) and any(kw in t for kw in ["配方", "优化", "电解液", "formula", "electrolyte", "优化"]):
        return 'iron_chromium'
    if any(kw in t for kw in ["铁铬", "iron-chromium", "icrfb"]):
        return 'iron_chromium'
    return 'other'

# 同步强化两个潜在的分类模块
for mod_name in ['rag.class_query', 'rag.classification', 'class_query', 'classification']:
    try:
        if mod_name in sys.modules:
            sys.modules[mod_name].identify_battery_type = patched_identify_battery_type
        import importlib
        mod = importlib.import_module(mod_name)
        mod.identify_battery_type = patched_identify_battery_type
        print(f"🚀 [系统] 已强化识别引擎: {mod_name}")
    except Exception:
        pass

# 最终补丁应用：全量扫描大模型流处理
def apply_robust_patches():
    count = 0
    target_methods = {'_handle_streaming_response': patched_handle_streaming_response}
    
    # 【强制】直接修改 LLMConfig 类定义，增加 **kwargs 兼容所有参数（处理 on_reasoning 等新参数）
    orig_call = LLMConfig.call_llm
    def robust_call_llm(self, prompt, *args, **kwargs):
        """绝对不会报错的 call_llm 包装器"""
        try:
            return orig_call(self, prompt, *args, **kwargs)
        except TypeError as e:
            # 如果底层代码还没更新（如模块缓存），则手动剥离不支持的参数
            if "unexpected keyword argument" in str(e):
                # 递归清理不支持的参数
                supported_args = ['temperature', 'max_tokens', 'model', 'stream', 'system_prompt', 'repetition_penalty', 'on_chunk']
                new_kwargs = {k: v for k, v in kwargs.items() if k in supported_args}
                return orig_call(self, prompt, *args, **new_kwargs)
            raise e
    
    # 应用全局类补丁
    LLMConfig.call_llm = robust_call_llm
    LLMConfig._handle_streaming_response = patched_handle_streaming_response
    
    # 扫描所有已加载模块，确保所有引用处都被覆盖
    for mod_name, module in list(sys.modules.items()):
        if 'part1_knowledge_arsenal' in mod_name or 'agent' in mod_name:
            if hasattr(module, 'LLMConfig'):
                cls_obj = getattr(module, 'LLMConfig')
                # 覆盖流处理方法
                cls_obj._handle_streaming_response = patched_handle_streaming_response
                # 覆盖调用方法
                cls_obj.call_llm = robust_call_llm
                count += 1
                
    print(f"🚀 [系统] 终端打印与参数容错补丁已全量生效 (覆盖 {count} 个模块引用)")

apply_robust_patches()

# 补丁 3: 路径校正与日志穿透
import multi_turn_chat
import contextlib
import io

# 解决 AttributeError: module 'multi_turn_chat' has no attribute 'contextlib'
multi_turn_chat.contextlib = contextlib
multi_turn_chat.io = io

# 定义空上下文管理器，解除后端初始化时的“静默模式”
class NullContext:
    def __init__(self, *args, **kwargs): pass
    def __enter__(self): return self
    def __exit__(self, *args): pass

# 拦截重定向逻辑，让初始化日志重回终端
contextlib.redirect_stdout = lambda x: NullContext()
contextlib.redirect_stderr = lambda x: NullContext()

# 强制校准后端所有路径变量
if hasattr(multi_turn_chat, 'PROJECT_ROOT'):
    true_root = os.path.dirname(SRC_DIR)
    multi_turn_chat.PROJECT_ROOT = true_root
    # 同步修正 AGENT_DIR 确保绝对路径一致
    multi_turn_chat.AGENT_DIR = os.path.join(true_root, 'src', 'agent')
    print(f"🔧 [系统] 路径/日志补丁已就绪: {multi_turn_chat.PROJECT_ROOT}")

from multi_turn_chat import MultiTurnConversation, PENDING_SESSION_ID
import agent.part5_glm

# 第一性原理 Agent 流式生成补丁
def patched_fp_generate_stream(self, question: str):
    """流式生成第一性原理回答 (带分隔符注入)"""
    base_url = getattr(self, 'base_url', None) or (self.llm_config.base_url if hasattr(self, 'llm_config') else "https://api.moonshot.cn/v1")
    api_url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
    model = getattr(self, 'model', self.llm_config.model)
    # 【补丁】kimi-k2.x thinking 系列硬要求 temperature=1.0
    _fp_temp = 1.0 if isinstance(model, str) and model.startswith("kimi-k2.") else 0.2
    data = {
        "model": model,
        "messages": [{"role": "system", "content": self.SYSTEM_PROMPT}, {"role": "user", "content": question}],
        "temperature": _fp_temp, "stream": True
    }
    max_retries = 2
    for attempt in range(max_retries + 1):
        try:
            response = requests.post(api_url, headers=headers, json=data, stream=True, timeout=(10, 60), proxies={'http': None, 'https': None})
            if response.status_code != 200:
                if attempt < max_retries: time.sleep(1); continue
                yield f"❌ GLM调用失败 ({response.status_code}): {response.text}"
                return
            for line in response.iter_lines():
                if not line: continue
                line_str = line.decode('utf-8')
                if line_str.startswith('data: '): line_str = line_str[6:]
                if line_str == '[DONE]': break
                try:
                    chunk = json.loads(line_str)
                    if 'choices' in chunk and len(chunk['choices']) > 0:
                        delta = chunk['choices'][0].get('delta', {})
                        reasoning = delta.get('reasoning_content', '')
                        if reasoning: yield {"type": "reasoning", "content": reasoning}
                        content = delta.get('content', '')
                        if content: yield {"type": "content", "content": content}
                except json.JSONDecodeError: continue
            return
        except Exception:
            if attempt < max_retries: time.sleep(1); continue
            yield f"❌ 第一性原理生成异常 (Patch)"

# 强制应用第一性原理补丁
agent.part5_glm.FirstPrinciplesAgent.generate_stream = patched_fp_generate_stream

# 补丁 3: 图谱生成驱动迁移 (迁移至 Kimi 以提升响应速度)
def patched_graph_llm_call(system_msg, user_msg, supplier=None):
    # 使用后端 Kimi 专用配置
    llm = LLMConfig(
        api_key=__import__("os").environ.get("MOONSHOT_API_KEY", ""),
        base_url="https://api.moonshot.cn/v1",
        model="kimi-k2.6"
    )
    # K2.6 强制 temperature=1.0 (LLMConfig 内部亦有兜底覆盖)
    return llm.call_llm(user_msg, system_prompt=system_msg, temperature=1.0)

# 双重覆盖，确保 utils.py 内部也能感知到补丁
llm_utils.call_llm = patched_graph_llm_call
utils.call_llm = patched_graph_llm_call

# 补丁 4: Neo4j 认证对齐 (处理 AuthenticationRateLimit)
try:
    from agent.part1_knowledge_arsenal import KnowledgeArsenal
    orig_arsenal_init = KnowledgeArsenal.__init__
    def patched_arsenal_init(self, *args, **kwargs):
        # 强制将默认密码从 "neo4j" 改为 "neo4j123" 以对齐 GraphQA
        if 'neo4j_password' not in kwargs:
            kwargs['neo4j_password'] = __import__("os").environ.get("NEO4J_PASSWORD", "")
        return orig_arsenal_init(self, *args, **kwargs)
    KnowledgeArsenal.__init__ = patched_arsenal_init
    print("🚀 [系统] Neo4j 认证对齐补丁已加载")
except Exception:
    pass

# 补丁 5: 网络传输兼容性增强 (处理 Brotli 解码崩溃)
try:
    import requests
    orig_request = requests.Session.request
    def patched_request(self, method, url, *args, **kwargs):
        headers = kwargs.get('headers', {})
        # 强制移除 br (Brotli) 编码申明，防止服务端返回无法解码的压缩流
        if 'Accept-Encoding' in headers:
            headers['Accept-Encoding'] = headers['Accept-Encoding'].replace(', br', '').replace('br, ', '').replace('br', '')
        else:
            # 如果没设，显式指定稳健的编码
            headers['Accept-Encoding'] = 'gzip, deflate'
        kwargs['headers'] = headers
        return orig_request(self, method, url, *args, **kwargs)
    requests.Session.request = patched_request
    print("🚀 [系统] 网络传输兼容性补丁已加载 (Brotli -> Gzip)")
except Exception:
    pass
# 【新增】前端渲染兜底清洗器 — 加载失败时优雅退化到原样输出
try:
    from agent.answer_cleaner import clean_final_answer as _clean_final_answer
except Exception:
    def _clean_final_answer(text, sources=None):
        return text


def format_markdown(text):
    if not text: return text
    return text.replace('\n', '  \n')


def clean_and_format(text, sources=None):
    """主答案渲染专用: 先跑清洗器 (剥元评论/修区间符号/清空文献来源标题) 再做换行处理.
    不用于 reasoning 面板 (那里要保留完整思考过程)."""
    if not text:
        return text
    try:
        text = _clean_final_answer(text, sources=sources)
    except Exception:
        pass
    # 渲染层包装: 先转义 LLM 文本中的 HTML 特殊字符，再把 [Ref-n] 替换为琥珀引用 chip
    text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    text = re.sub(r'\[Ref-(\d+)\]', r'<span class="fb-cite">\1</span>', text)
    return text.replace('\n', '  \n')


def _make_history_id(question, answer="", timestamp=None):
    """为历史记录生成稳定、可用于 Streamlit key 的 ID。

    从 JSONL 加载时使用持久化 timestamp；新建会话时使用纳秒时间戳避免
    相同问题生成重复按钮 key。历史 JSONL 格式本身不增加新字段。
    """
    seed = "\x1f".join((str(timestamp or time.time_ns()), str(question or ""), str(answer or "")))
    return "hist-" + hashlib.sha1(seed.encode("utf-8", errors="replace")).hexdigest()[:16]


def _history_record_from_messages(messages, timestamp=None):
    """将当前消息列表包装为内存中的历史记录，不改变持久化 JSONL 结构。"""
    question = next((m.get("content", "") for m in messages or [] if m.get("role") == "user"), "新对话")
    answer = next((m.get("content", "") for m in messages or [] if m.get("role") == "assistant"), "")
    title = question[:15] + ("..." if len(question) > 15 else "")
    return {
        "history_id": _make_history_id(question, answer, timestamp=timestamp),
        "title": title,
        "messages": copy.deepcopy(messages or []),
    }


def _history_id_for_item(history_item, position=None):
    """读取历史记录 ID，并兼容旧会话中尚未带 history_id 的字典。"""
    existing = history_item.get("history_id") if isinstance(history_item, dict) else None
    if existing:
        return str(existing)
    messages = history_item.get("messages") if isinstance(history_item, dict) else []
    question = next((m.get("content", "") for m in messages or [] if m.get("role") == "user"),
                    history_item.get("title", "历史记录") if isinstance(history_item, dict) else "历史记录")
    answer = next((m.get("content", "") for m in messages or [] if m.get("role") == "assistant"), "")
    base = _make_history_id(question, answer, timestamp="legacy")
    return f"{base}-{position}" if position is not None else base

def prepare_graph_visualization(nodes_data, edges_data, height=850):
    # 定义类别与浅色系的映射（扩充关键词，增加中英文兼容性）
    category_colors = {
        "材料": "#A0C4FF", "Material": "#A0C4FF",      # 浅蓝色
        "化合物": "#A0C4FF", "Chemical": "#A0C4FF",
        "物质": "#A0C4FF", "Substance": "#A0C4FF",
        "溶液": "#A0C4FF", "Electrolyte": "#A0C4FF",
        "性能指标": "#FFADAD", "Property": "#FFADAD",   # 浅红色
        "性能": "#FFADAD", "Performance": "#FFADAD",
        "指标": "#FFADAD", "Metrics": "#FFADAD",
        "效率": "#FFADAD", "Efficiency": "#FFADAD",
        "活性": "#FFADAD", "Activity": "#FFADAD",
        "化学": "#CAFFBF", "Reaction": "#CAFFBF",      # 浅绿色
        "反应": "#CAFFBF", "Mechanism": "#CAFFBF",
        "机理": "#CAFFBF", "Process": "#CAFFBF",
        "过程": "#CAFFBF",
        "添加剂": "#D7BDE2", "Additive": "#D7BDE2",    # 浅紫色
        "溶剂": "#D7BDE2", "Solvent": "#D7BDE2",
        "参数": "#FDFFB6", "Parameter": "#FDFFB6",     # 浅黄色
        "条件": "#FDFFB6", "Condition": "#FDFFB6",
        "工艺": "#FDFFB6", "Technique": "#FDFFB6",
        "设备": "#FFD6A5", "Device": "#FFD6A5",        # 浅橘色
        "组件": "#FFD6A5", "Component": "#FFD6A5",
        "系统": "#FFD6A5", "System": "#FFD6A5",
    }
    default_color = "#44475A"   # 深靛灰

    nodes = []
    for n in nodes_data:
        group_name = str(n.get('group', ''))
        node_color = default_color
        
        # 简单关键词匹配映射颜色
        for keyword, color_code in category_colors.items():
            if keyword in group_name:
                node_color = color_code
                break
        
        nodes.append(Node(
            id=str(n['id']), 
            label=str(n['label']), 
            size=30,  # 稍微增大节点以匹配大字体
            color=node_color,
            font={
                'size': 18, 
                'color': ui_style.PALETTE['ink'],  # 浅色主题: 墨色文字 + 白色描边保证可读
                'face': 'Inter', 
                'strokeWidth': 3,
                'strokeColor': '#FFFFFF',
                'align': 'center'
            }
        ))
    
    edges = [
        Edge(
            source=str(e['from']), 
            target=str(e['to']), 
            label=str(e['label']),
            color=ui_style.PALETTE['teal'],  # 浅色主题: 青绿边（demo 主色）
            width=2,
            font={
                'size': 12, 
                'color': ui_style.PALETTE['ink_2'],
                'face': 'Inter', 
                'strokeWidth': 3,
                'strokeColor': ui_style.PALETTE['surface_2'],
                'align': 'middle'
            },
            # 增加边的默认长度，物理引擎在静止时会自动把节点推得更开
            length=250 
        ) for e in edges_data
    ]
    
    # 核心配置优化：取消层级，增强动力学排斥空间
    config = Config(
        width='100%', 
        height=height,  # 动态高度
        directed=True, 
        physics=True, 
        nodeHighlightBehavior=True, 
        highlightColor=ui_style.PALETTE['amber'],
        collapsible=False,
        node={'labelProperty': 'label'}, 
        link={'labelProperty': 'label', 'renderLabel': True},
        hierarchical=False,
        backgroundColor=ui_style.PALETTE['surface_2']  # 浅色暖纸（demo surface-2）
    )
    return nodes, edges, config


# 【证据图闭环 M4】证据图节点类型配色(计划 4.2, 沿用浅色系家族)
EG_TYPE_COLORS = {
    "PAPER": "#A0C4FF", "METHOD": "#CAFFBF", "MATERIAL": "#D7BDE2",
    "PROPERTY": "#FFADAD", "MECHANISM": "#FDFFB6", "FINDING": "#FFD6A5", "TASK": "#FFD6A5",
}
EG_EDGE_COLORS = {
    "SUPPORTS": "#7CC08B", "REFUTES": "#E48B8B",
    "INCONCLUSIVE_FOR": "#B8AFA6", "CITES": "#9BB8D9",
}


def _quote_short(quote, limit=60):
    q = str(quote or "").strip()
    return (q[:limit] + "…") if len(q) > limit else q


def render_evidence_graph(snapshot, key="eg_live", height=420, interactive=True):
    """渲染证据图快照(计划 4.2): 节点按类型着色, 点击节点查看观察句与来源证据。

    snapshot: EvidenceGraphStore.snapshot() 结构 {meta, nodes, edges, stats}。
    返回 True 表示已渲染(调用方据此跳过旧版本体抽取图)。
    术语红线: 图内一切条目为 LLM 抽取"候选", 一律不得标注 confirmed。
    """
    nodes_raw = (snapshot or {}).get("nodes") or []
    edges_raw = (snapshot or {}).get("edges") or []
    if not nodes_raw:
        return False

    st.markdown(
        '<div class="fb-eg-legend">证据图（逐轮累积）· 节点按类型着色 · 点击节点查看观察与来源 · '
        '红虚线 = 同条件下疑似冲突 · 全部条目均为 '
        '<span class="fb-eg-candidate-tag">候选</span>'
        '（未过 Stage B 核验, 非 confirmed）</div>',
        unsafe_allow_html=True,
    )

    node_by_id = {}
    a_nodes = []
    for n in nodes_raw:
        try:
            nid = str(n.get("id"))
            ntype = str(n.get("type") or "")
            name = str(n.get("name") or nid)
        except Exception:
            continue
        obs_count = len(n.get("observations") or [])
        node_by_id[nid] = n
        a_nodes.append(Node(
            id=nid, label=name + (f" ·{obs_count}" if obs_count else ""),
            size=26 + min(14, obs_count * 6),
            color=EG_TYPE_COLORS.get(ntype, "#44475A"),
            font={'size': 14, 'color': ui_style.PALETTE['ink'], 'face': 'Inter',
                  'strokeWidth': 3, 'strokeColor': '#FFFFFF'},
        ))

    a_edges = []
    for e in edges_raw:
        try:
            src, dst = str(e.get("src")), str(e.get("dst"))
            etype = str(e.get("type") or "ASSOCIATED_WITH")
        except Exception:
            continue
        if src not in node_by_id or dst not in node_by_id:
            continue
        is_conflict = bool(e.get("conflict_group"))
        color = "#D96A6A" if is_conflict else EG_EDGE_COLORS.get(etype, ui_style.PALETTE['teal'])
        a_edges.append(Edge(
            source=src, target=dst,
            label=(etype + " ⚡冲突") if is_conflict else etype,
            color=color, width=2 if is_conflict else 1.5, dashed=is_conflict, length=180,
            font={'size': 10, 'color': ui_style.PALETTE['ink_2'], 'strokeWidth': 2,
                  'strokeColor': ui_style.PALETTE['surface_2']},
        ))

    config = Config(width='100%', height=height, directed=True, physics=True,
                    nodeHighlightBehavior=True, highlightColor=ui_style.PALETTE['amber'],
                    collapsible=False, node={'labelProperty': 'label'},
                    link={'labelProperty': 'label', 'renderLabel': True},
                    hierarchical=False, backgroundColor=ui_style.PALETTE['surface_2'])
    if interactive:
        # Installed streamlit-agraph's public function has no key argument.
        from streamlit_agraph import _agraph
        selected = _agraph(data=json.dumps({"nodes": [n.to_dict() for n in a_nodes],
                                            "edges": [e.to_dict() for e in a_edges]}),
                           config=json.dumps(config.__dict__), key=key)
    else:
        render_static_history_graph({
            "nodes": [{"id": n["id"], "label": n.get("name"), "group": n.get("type")} for n in nodes_raw],
            "edges": [{"from": e["src"], "to": e["dst"], "label": e.get("type")} for e in edges_raw],
        }, key=key, height=height)
        selected = None

    # 点击节点 → 观察句 + provenance(Ref-n + 论文 + 逐字原文)
    if isinstance(selected, list):
        sel_ids = [str(s) for s in selected]
    elif selected:
        sel_ids = [str(selected)]
    else:
        sel_ids = []
    for nid in sel_ids[:3]:
        n = node_by_id.get(nid) or {}
        obs_list = n.get("observations") or []
        if not obs_list:
            continue
        with st.expander(f"🔍 {n.get('name', nid)} · 观察与来源证据", expanded=True):
            for o in obs_list:
                prov = o.get("prov") or {}
                st.markdown(
                    f"- {html.escape(str(o.get('text', '')))}  \n"
                    f"  <span style='color:var(--fb-ink-3);font-size:12px'>"
                    f"Ref-{prov.get('ref_id', '?')} · {html.escape(str(prov.get('paper_title') or '未知来源'))} · "
                    f"原文: {html.escape(_quote_short(prov.get('quote')))} · {o.get('status', 'candidate')}</span>",
                    unsafe_allow_html=True,
                )

    with st.expander("查看逐条原文与关系依据", expanded=False):
        evidence_items = []
        for n in nodes_raw:
            for o in n.get("observations") or []:
                evidence_items.append((f"{n.get('name')}：{o.get('text')}", o))
        for e in edges_raw:
            src_name = (node_by_id.get(e.get("src")) or {}).get("name", e.get("src"))
            dst_name = (node_by_id.get(e.get("dst")) or {}).get("name", e.get("dst"))
            evidence_items.append((f"{src_name} → {dst_name} · {e.get('type')}：{e.get('obs')}", e))
        if evidence_items:
            index = st.selectbox("选择证据", range(len(evidence_items)),
                                 format_func=lambda i: evidence_items[i][0], key=f"{key}_source")
            label, item = evidence_items[index]
            st.write(label)
            st.caption(f"状态：{item.get('status', 'candidate')}；原文可定位不代表结论已审定。")
            for prov in [item.get("prov") or {}] + (item.get("supporting_sources") or []):
                st.write(f"[Ref-{prov.get('ref_id', '?')}] {prov.get('paper_title', '')}")
                st.caption(f"原文位置：{prov.get('location') or '来源段落'} · 来源标识：{prov.get('source_id') or '旧版记录'}")
                st.text(prov.get("quote") or "未记录原文")

    stats = (snapshot or {}).get("stats") or {}
    conflict_n = len(stats.get("conflict_groups") or [])
    st.caption(f"证据图统计: {stats.get('nodes', len(a_nodes))} 节点 · "
               f"{stats.get('edges', len(a_edges))} 边"
               + (f" · 冲突组 {conflict_n}" if conflict_n else ""))
    return True


def render_static_history_graph(graph_data, key="history_graph", height=420):
    """渲染历史记录用的静态 SVG 图谱。

    历史记录切换时不再挂载 streamlit_agraph/vis-network，避免 React
    rerun 卸载组件时与第三方 DOM 清理发生 removeChild 竞态。图谱数据
    仍来自已保存的 graph 字段；无效数据只降级为提示，不阻断页面。
    """
    if not isinstance(graph_data, dict):
        st.info("该历史记录未保存知识图谱数据。")
        return False

    raw_nodes = graph_data.get("nodes") or []
    raw_edges = graph_data.get("edges") or []
    if not isinstance(raw_nodes, list) or not raw_nodes:
        st.info("该历史记录未生成可展示的知识图谱。")
        return False

    nodes = []
    node_ids = set()
    for raw in raw_nodes:
        if not isinstance(raw, dict) or raw.get("id") is None:
            continue
        node_id = str(raw.get("id"))
        if node_id in node_ids:
            continue
        node_ids.add(node_id)
        nodes.append({
            "id": node_id,
            "label": str(raw.get("label") or node_id),
            "group": str(raw.get("group") or ""),
        })

    if not nodes:
        st.info("该历史记录的图谱节点数据无效。")
        return False

    edges = []
    for raw in raw_edges if isinstance(raw_edges, list) else []:
        if not isinstance(raw, dict):
            continue
        source = str(raw.get("from")) if raw.get("from") is not None else ""
        target = str(raw.get("to")) if raw.get("to") is not None else ""
        if source not in node_ids or target not in node_ids:
            continue
        edges.append({
            "from": source,
            "to": target,
            "label": str(raw.get("label") or ""),
        })

    # 统一使用项目主题变量；布局本身为确定性网格，不依赖浏览器脚本。
    cols = min(3, max(1, int(math.ceil(math.sqrt(len(nodes))))))
    rows = max(1, int(math.ceil(len(nodes) / cols)))
    canvas_w = max(760, cols * 250)
    canvas_h = max(int(height), rows * 155)
    x_gap = (canvas_w - 240) / max(1, cols - 1)
    y_gap = (canvas_h - 160) / max(1, rows - 1)
    positions = {}
    for index, node in enumerate(nodes):
        row, col = divmod(index, cols)
        x = 120 + (col * x_gap if cols > 1 else (canvas_w - 240) / 2)
        y = 80 + (row * y_gap if rows > 1 else (canvas_h - 160) / 2)
        positions[node["id"]] = (round(x, 1), round(y, 1))

    safe_key = re.sub(r"[^A-Za-z0-9_-]", "_", str(key))[:48] or "history_graph"
    marker_id = f"fbHistoryArrow_{safe_key}"
    esc = lambda value: html.escape(str(value), quote=True)
    edge_markup = []
    for edge_index, edge in enumerate(edges):
        sx, sy = positions[edge["from"]]
        tx, ty = positions[edge["to"]]
        distance=max(math.hypot(tx-sx,ty-sy),1)
        ux,uy=(tx-sx)/distance,(ty-sy)/distance
        sx,sy=sx+ux*32,sy+uy*32
        tx,ty=tx-ux*35,ty-uy*35
        offset=min(28+(edge_index%3)*19,max(12,min(sy,ty)-22)) if abs(sy-ty)<2 else 0
        cx,cy=(sx+tx)/2,(sy+ty)/2-offset
        edge_markup.append(
            f'<path d="M {sx},{sy} Q {cx},{cy} {tx},{ty}" fill="none" '
            f'stroke="var(--fb-teal)" stroke-width="1.6" opacity=".65" '
            f'marker-end="url(#{marker_id})" />'
        )
        if edge["label"]:
            lx, ly = round((sx+2*cx+tx)/4,1),round((sy+2*cy+ty)/4-5,1)
            label=edge['label'][:30]
            label_width=max(20,len(label)*7.5)
            edge_markup.append(
                f'<rect x="{lx-label_width/2}" y="{ly-12}" width="{label_width}" height="17" rx="3" fill="var(--fb-surface-2)" opacity=".94" />'
                f'<text x="{lx}" y="{ly}" text-anchor="middle" '
                f'font-size="13" fill="var(--fb-ink-2)"><title>{esc(edge["label"])}</title>{esc(label)}</text>'
            )

    node_markup = []
    for node in nodes:
        x, y = positions[node["id"]]
        full_label = node['label']
        label_lines = [full_label[i:i+13] for i in range(0, min(len(full_label),39),13)] or ['']
        if len(full_label)>39:
            label_lines[-1] += '…'
        label_markup = ''.join(
            f'<tspan x="{x}" dy="{0 if i==0 else 18}">{esc(line)}</tspan>'
            for i,line in enumerate(label_lines))
        node_markup.append(
            f'<g><title>{esc(full_label)} · {esc(node["group"])}</title><circle cx="{x}" cy="{y}" r="29" '
            f'fill="var(--fb-teal-soft)" stroke="var(--fb-teal)" stroke-width="1.4" />'
            f'<text x="{x}" y="{y - 8}" text-anchor="middle" '
            f'font-size="14" font-weight="600" fill="var(--fb-ink)">{label_markup}</text>'
            f'<text x="{x}" y="{y + 53}" text-anchor="middle" '
            f'font-size="12" fill="var(--fb-ink-3)">{esc(node["group"][:18])}</text></g>'
        )

    svg = (
        f'<div class="fb-history-graph" tabindex="0" style="width:100%;overflow:auto;max-height:{max(300,int(height))}px;'
        f'border:1px solid var(--fb-line);border-radius:8px;background:var(--fb-surface-2);">'
        f'<svg role="img" aria-label="历史记录知识图谱" viewBox="0 0 {canvas_w} {canvas_h}" '
        f'width="{canvas_w}" height="{canvas_h}" style="min-width:{canvas_w}px;max-width:none" preserveAspectRatio="xMidYMid meet">'
        f'<defs><marker id="{marker_id}" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">'
        f'<path d="M0,0 L8,4 L0,8 Z" fill="var(--fb-teal)" /></marker></defs>'
        + "".join(edge_markup)
        + "".join(node_markup)
        + "</svg></div>"
    )
    st.markdown(svg, unsafe_allow_html=True)
    st.caption(f"静态图谱：{len(nodes)} 个节点，{len(edges)} 条关系。可横向/纵向滚动，悬停节点查看完整名称。")
    return True

def _get_landscape_module():
    """惰性导入方法版图模块 (src/graph_rag/method_extraction/landscape/landscape_tab.py)."""
    import sys as _sys, os as _os
    _root = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
    _lp = _os.path.join(_root, "src", "graph_rag", "method_extraction", "landscape")
    if _lp not in _sys.path:
        _sys.path.insert(0, _lp)
    import landscape_tab as _atlas
    return _atlas

# ========== 方法版图 · demo 同款散点小版图 (components.html canvas) ==========
# 配色一律取 atlas["cluster_colors"]（landscape_api 真实接口），主题色取 ui_style.PALETTE，不再本地硬编码


def _atlas_data_for_qa():
    """惰性加载 compute_atlas 数据; Streamlit 层缓存."""
    if "_qa_atlas_cache" in st.session_state:
        return st.session_state["_qa_atlas_cache"]
    import sys as _sys, os as _os
    _root = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
    _lp = _os.path.join(_root, "src", "graph_rag", "method_extraction", "landscape")
    if _lp not in _sys.path:
        _sys.path.insert(0, _lp)
    from atlas_data import compute_atlas
    data = compute_atlas(include_peripheral=False)
    st.session_state["_qa_atlas_cache"] = data
    return data


def render_qa_atlas(hit_ids, key="qa_atlas", height=340):
    """方案D「雾屿」小版图: components.html 内嵌 canvas。
       - 大陆: 逐簇离屏低分辨率径向渐变累积, 裁剪进凸包后放大模糊成有机雾团
       - 边界: 凸包中点二次曲线平滑细描边（atlas_render.py 同款语汇）
       - 叠加: landmark 星标 + 簇质心药丸标签（真实聚类标签）
       - 高亮: 命中节点（最多 30）琥珀圆点 + 白色描边 + 光晕
       - 底部: 数据来源脚注 + 命中提示
    """
    try:
        atlas = _atlas_data_for_qa()
    except Exception as e:
        st.error(f"方法版图数据加载失败: {e}")
        return

    nodes = atlas["nodes"]
    id2 = atlas["id2node"]
    cof = atlas["cluster_of"]
    colors = atlas["cluster_colors"]
    clusters = atlas["clusters"]
    pal = ui_style.PALETTE

    hits = [i for i in (hit_ids or []) if i in id2][:30]

    # 簇索引映射: pts 只带簇序号, 颜色/标签/凸包/质心按序号对齐, 减小 payload
    cids = sorted(colors.keys())
    idx_of = {cid: i for i, cid in enumerate(cids)}
    pts = [{"x": round(n["x"], 4), "y": round(n["y"], 4), "g": idx_of.get(cof.get(n["id"], -1), -1)}
           for n in nodes]
    cents = atlas["centroids"]
    # 注: 后端 hulls 依赖 scipy（本环境未必装）, 凸包改为前端 JS 计算（88 分位裁剪 + 单调链）
    payload = json.dumps({
        "pts": pts,
        "hits": [{"x": round(id2[i]["x"], 4), "y": round(id2[i]["y"], 4)} for i in hits],
        "cols": [colors[c] for c in cids],
        "labels": [clusters.get(c, {}).get("label", f"C{c}") for c in cids],
        "cents": [[round(cents[c][0], 4), round(cents[c][1], 4)] if c in cents else None for c in cids],
        "lms": [{"x": round(id2[i]["x"], 4), "y": round(id2[i]["y"], 4)}
                for i in atlas["landmark_ids"] if i in id2],
    }, ensure_ascii=False)
    canvas_html = """
<canvas id="fbAtlasCv" style="width:100%;height:__H__px;border:1px solid __LINE__;border-radius:8px;background:__BG__"></canvas>
<script>
const data = __DATA__;
const cv = document.getElementById('fbAtlasCv');
function drawAtlas() {
  // Streamlit components.html iframe 里脚本可能先于布局执行, clientWidth=0 时直接跳过等重绘
  const dpr = window.devicePixelRatio || 1;
  const w = cv.clientWidth, h = cv.clientHeight;
  if (!w || !h) return;
  cv.width = w * dpr; cv.height = h * dpr;
  const ctx = cv.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  const pad = 14;
  let minx = Infinity, maxx = -Infinity, miny = Infinity, maxy = -Infinity;
  data.pts.forEach(p => {
    if (p.x < minx) minx = p.x; if (p.x > maxx) maxx = p.x;
    if (p.y < miny) miny = p.y; if (p.y > maxy) maxy = p.y;
  });
  const sx = v => pad + (v - minx) / (maxx - minx) * (w - 2 * pad);
  const sy = v => pad + (1 - (v - miny) / (maxy - miny)) * (h - 2 * pad);
  // 簇成员预分组, 避免雾团/离散度反复全表扫描
  const byCluster = data.cols.map(() => []);
  data.pts.forEach(p => { if (p.g >= 0) byCluster[p.g].push(p); });
  // 凸包前端计算: 88 分位离群裁剪 + 单调链 (atlas_data.py 同款, 不依赖 scipy)
  function hullOf(mem) {
    if (mem.length < 3) return [];
    const xs = mem.map(p => p.x).sort((a, b) => a - b);
    const ys = mem.map(p => p.y).sort((a, b) => a - b);
    const cx = xs[Math.floor(xs.length / 2)], cy = ys[Math.floor(ys.length / 2)];
    const ds = mem.map(p => Math.hypot(p.x - cx, p.y - cy)).sort((a, b) => a - b);
    const cut = ds[Math.min(ds.length - 1, Math.floor(ds.length * 0.88))];
    const keep = mem.filter(p => Math.hypot(p.x - cx, p.y - cy) <= cut);
    const use = keep.length >= 3 ? keep : mem;
    const sp = use.map(p => [p.x, p.y]).sort((a, b) => a[0] - b[0] || a[1] - b[1]);
    const cross = (o, a, b) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
    const lower = [], upper = [];
    for (const pt of sp) {
      while (lower.length >= 2 && cross(lower[lower.length - 2], lower[lower.length - 1], pt) <= 0) lower.pop();
      lower.push(pt);
    }
    for (let i = sp.length - 1; i >= 0; i--) {
      const pt = sp[i];
      while (upper.length >= 2 && cross(upper[upper.length - 2], upper[upper.length - 1], pt) <= 0) upper.pop();
      upper.push(pt);
    }
    lower.pop(); upper.pop();
    return lower.concat(upper);
  }
  const hulls = byCluster.map(mem => hullOf(mem));
  // 凸包中点二次曲线平滑路径 (demo/atlas_render.py 同款大陆手感)
  function smoothPath(hull) {
    const n = hull.length;
    ctx.beginPath();
    for (let i = 0; i < n; i++) {
      const p0 = hull[i], p1 = hull[(i + 1) % n];
      const mx = (sx(p0[0]) + sx(p1[0])) / 2, my = (sy(p0[1]) + sy(p1[1])) / 2;
      if (i === 0) ctx.moveTo(mx, my);
      else ctx.quadraticCurveTo(sx(p0[0]), sy(p0[1]), mx, my);
    }
    const pl = hull[0], pn = hull[n - 1];
    ctx.quadraticCurveTo(sx(pn[0]), sy(pn[1]), (sx(pn[0]) + sx(pl[0])) / 2, (sy(pn[1]) + sy(pl[1])) / 2);
    ctx.closePath();
  }
  // 1. 逐簇雾团: 离屏低分辨率径向渐变累积, 裁剪进凸包, 放大模糊成有机大陆
  const ms = 0.22;
  const lowW = Math.max(2, Math.round(w * ms)), lowH = Math.max(2, Math.round(h * ms));
  hulls.forEach((hull, ci) => {
    if (!hull.length) return;
    const mem = byCluster[ci];
    const col = data.cols[ci];
    let mx = 0;
    mem.forEach(p => { mx += sx(p.x); });
    mx /= mem.length;
    let varx = 0;
    mem.forEach(p => { const d = sx(p.x) - mx; varx += d * d; });
    const R = Math.max(3, Math.sqrt(varx / mem.length) * ms * 0.9);
    const off = document.createElement('canvas');
    off.width = lowW; off.height = lowH;
    const octx = off.getContext('2d');
    mem.forEach(p => {
      const X = sx(p.x) * ms, Y = sy(p.y) * ms;
      const g = octx.createRadialGradient(X, Y, 0, X, Y, R);
      g.addColorStop(0, col + '14');
      g.addColorStop(0.55, col + '08');
      g.addColorStop(1, col + '00');
      octx.fillStyle = g;
      octx.beginPath(); octx.arc(X, Y, R, 0, Math.PI * 2); octx.fill();
    });
    ctx.save();
    smoothPath(hull);
    ctx.clip();
    ctx.filter = 'blur(4px)';
    ctx.globalAlpha = 0.5;
    ctx.drawImage(off, 0, 0, lowW, lowH, 0, 0, w, h);
    ctx.restore();
  });
  // 2. 凸包细描边, 保住边界结构感
  hulls.forEach((hull, ci) => {
    if (!hull.length) return;
    smoothPath(hull);
    ctx.globalAlpha = 0.45; ctx.lineWidth = 1.1;
    ctx.strokeStyle = data.cols[ci]; ctx.stroke();
  });
  ctx.globalAlpha = 1;
  // 3. 节点散点
  data.pts.forEach(p => {
    ctx.globalAlpha = p.g >= 0 ? 0.8 : 0.22;
    ctx.fillStyle = p.g >= 0 ? data.cols[p.g] : '__INK3__';
    ctx.beginPath(); ctx.arc(sx(p.x), sy(p.y), p.g >= 0 ? 1.8 : 1.5, 0, Math.PI * 2); ctx.fill();
  });
  ctx.globalAlpha = 1;
  // 4. landmark 星标
  ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  data.lms.forEach(p => {
    const x = sx(p.x), y = sy(p.y);
    ctx.font = '11px Inter, sans-serif';
    ctx.lineWidth = 2.5; ctx.strokeStyle = '#ffffff';
    ctx.strokeText('★', x, y);
    ctx.fillStyle = '__INK__';
    ctx.fillText('★', x, y);
  });
  // 5. 簇质心药丸标签 (半透明白底 + 簇色描边)
  data.cents.forEach((cpos, ci) => {
    if (!cpos) return;
    const x = sx(cpos[0]), y = sy(cpos[1]);
    ctx.font = '600 10px Inter, sans-serif';
    const tw = ctx.measureText(data.labels[ci]).width + 14;
    ctx.beginPath();
    ctx.roundRect(x - tw / 2, y - 9, tw, 18, 9);
    ctx.fillStyle = 'rgba(255,255,255,.8)'; ctx.fill();
    ctx.lineWidth = 1.2; ctx.strokeStyle = data.cols[ci]; ctx.stroke();
    ctx.fillStyle = '__INK__';
    ctx.fillText(data.labels[ci], x, y + 0.5);
  });
  // 6. 检索命中: 琥珀圆点 + 白描边 + 光晕
  data.hits.forEach(p => {
    const x = sx(p.x), y = sy(p.y);
    ctx.beginPath(); ctx.arc(x, y, 5, 0, Math.PI * 2);
    ctx.fillStyle = '__AMBER__'; ctx.fill();
    ctx.lineWidth = 2; ctx.strokeStyle = '#ffffff'; ctx.stroke();
    ctx.beginPath(); ctx.arc(x, y, 9, 0, Math.PI * 2);
    ctx.strokeStyle = '__AMBER__'; ctx.lineWidth = 1.1; ctx.stroke();
  });
}
drawAtlas();
setTimeout(drawAtlas, 120);
setTimeout(drawAtlas, 600);
if (window.ResizeObserver) { new ResizeObserver(drawAtlas).observe(cv); }
window.addEventListener('resize', drawAtlas);
</script>
"""
    canvas_html = (
        canvas_html
        .replace("__DATA__", payload)
        .replace("__H__", str(height))
        .replace("__AMBER__", pal["amber"])
        .replace("__INK__", pal["ink"])
        .replace("__INK3__", pal["ink_3"])
        .replace("__BG__", pal["surface_2"])
        .replace("__LINE__", pal["line"])
    )
    components.html(canvas_html, height=height + 24)

    src_note = f"数据来源: Stage A/B 方法演进图谱 · {len(nodes)} 节点 {len(atlas['edges'])} 边 {len(clusters)} 聚类"
    if hits:
        st.caption(f"已定位 {len(hits)} 个相关方法（琥珀色高亮）· {src_note}")
    else:
        st.caption(f"未匹配到相关方法 · {src_note}")

    present = sorted({cof.get(i, -1) for i in hits if cof.get(i, -1) >= 0})
    if present:
        legend = '<div style="display:flex;flex-wrap:wrap;gap:10px;font-size:11px;color:var(--fb-ink-2);margin-top:2px">'
        for cid in present:
            col = colors.get(cid, pal["ink_3"])
            lbl = clusters.get(cid, {}).get("label", f"C{cid}")
            legend += (
                '<span style="display:inline-flex;align-items:center">'
                f'<span style="display:inline-block;width:9px;height:9px;border-radius:50%;'
                f'background:{col};margin-right:4px"></span>{lbl}</span>'
            )
        legend += "</div>"
        st.markdown(legend, unsafe_allow_html=True)

def render_stage_progress_metrics(state):
    # 状态可能在并行更新中为 None
    if not state: return
    c1, c2, c3, c4 = st.columns(4)
    # Stage 获取逻辑修复
    s1 = getattr(state, 'stage_1_complete', False)
    s2 = getattr(state, 'stage_2_complete', False)
    s3 = getattr(state, 'stage_3_complete', False)
    s4 = getattr(state, 'stage_4_complete', False)
    
    c1.metric("Stage 1", "问题解析", "✅" if s1 else "⏳")
    c2.metric("Stage 2", "多源检索", "✅" if s2 else "⏳")
    c3.metric("Stage 3", "信息融合", "✅" if s3 else "⏳")
    c4.metric("Stage 4", "答案生成", "✅" if s4 else "⏳")

# ST 页面配置
st.set_page_config(page_title="FlowBD AI - 专家对话系统", layout="wide", initial_sidebar_state="expanded")

# 自定义 CSS 提升 UI 质感 (仿豆包简约大气风格)
# 自定义 CSS 已迁移到 ui_style.py（浅色暖纸主题，对齐 ui-demo 设计稿）
import ui_style
ui_style.inject_global_css(SVG_MSG_PLUS)
ui_style.inject_sidebar_demo_css()
ui_style.inject_topbar_layout_css()
ui_style.inject_evidence_graph_css()   # 【证据图闭环 M4】迭代时间线/候选徽标样式

# 初始化 Session State (强化：确保所有变量都存在，防止属性缺失报错)
for key, default_val in {
    'messages': [],
    'history': [],            # 【新增】存储历史对话：[{"title": str, "messages": list}, ...]
    'current_supplier': 'glm_pro',
    'temperature': 0.0,
    'agent_initialized': False,
    'agent_conversation': None,
    'streaming_answer': "",
    'streaming_reasoning': "", # 【新增】存储深度思考过程
    'streaming_complete': True,
    'current_agent_state': None,
    '_conv_hist_idx': None,  # 旧版本兼容字段；新逻辑使用 _conv_hist_id
    '_conv_hist_id': None,
    '_history_view_mode': False,
    'iterative_mode': False,  # 【证据图闭环 M4】迭代闭环模式开关(实验, 默认关)
    'first_principles_enabled': False,
    'eg_summarized_answer': False,  # 【借鉴③(R9)】答案·图摘要模式开关(实验, 默认关)
}.items():
    if key not in st.session_state:
        st.session_state[key] = default_val

# 日志删除功能 (提前定义: 侧栏历史删除按钮在其下方调用, Streamlit 自上而下一次性执行)
def delete_chat_log_entry(messages):
    """从 chat_history.jsonl 删除与给定会话匹配的所有行。
    匹配口径: 会话内每个 (user, assistant) 消息对 ↔ jsonl 一行的 (question, answer)。
    多轮会话会删掉对应的多行; 找不到匹配行时静默跳过（例如仅存在会话状态的条目）。"""
    try:
        pairs = set()
        last_user = None
        for m in messages or []:
            if m.get("role") == "user":
                last_user = m.get("content", "")
            elif m.get("role") == "assistant" and last_user is not None:
                pairs.add((last_user, m.get("content", "")))
                last_user = None
        if not pairs:
            return
        log_file = os.path.join(PROJECT_ROOT, 'src', 'data', 'chat_history.jsonl')
        if not os.path.exists(log_file):
            return
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        kept = []
        for line in lines:
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                if (entry.get("question"), entry.get("answer")) in pairs:
                    continue  # 命中删除
            except Exception:
                pass
            kept.append(line)
        with open(log_file, 'w', encoding='utf-8') as f:
            f.writelines(kept)
    except Exception as e:
        print(f"⚠️ [历史删除] 失败: {e}")

# 侧栏底部统计 (demo 同款, 只读计数: 文献 / Stage A 方法条目 / confirmed 边)
@st.cache_data(ttl=600, show_spinner=False)
def _sidebar_stats():
    n_papers = n_methods = n_confirmed = 0
    try:
        pdf_dir = os.path.join(PROJECT_ROOT, 'pdf_to_md', 'extraction_results', 'downloaded_files')
        n_papers = sum(1 for d in os.listdir(pdf_dir) if os.path.isdir(os.path.join(pdf_dir, d)))
    except Exception:
        pass
    try:
        m_csv = os.path.join(PROJECT_ROOT, 'src', 'graph_rag', 'method_extraction', 'methods.csv')
        with open(m_csv, 'r', encoding='utf-8', errors='ignore') as f:
            n_methods = max(0, sum(1 for _ in f) - 1)   # 物理行数与 pandas 行数一致 (1952-1)
    except Exception:
        pass
    try:
        e_csv = os.path.join(PROJECT_ROOT, 'paper', 'method_evolution_v2',
                             'article_minimal_results', 'lineage_mvp', 'lineage_edges_confirmed_v2.csv')
        with open(e_csv, 'r', encoding='utf-8', errors='ignore') as f:
            n_confirmed = max(0, sum(1 for _ in f) - 1)
    except Exception:
        pass
    return n_papers, n_methods, n_confirmed

# Sidebar 配置廊
with st.sidebar:
    # 1. 新建对话 (demo 同款: 实心青置顶, 品牌见页面顶栏, 侧栏不再重复)
    if st.button(f" 新建对话", use_container_width=True, type="primary"):
        # 如果当前有聊天记录且尚未同步入库，则存入历史库（已同步的会话历史里已有条目，避免重复归档）
        if st.session_state.messages and st.session_state.get('_conv_hist_id') is None:
            st.session_state.history.insert(0, _history_record_from_messages(st.session_state.messages))
        
        # 重置当前会话
        st.session_state.messages = []
        st.session_state._conv_hist_id = None
        st.session_state._history_view_mode = False
        st.session_state.streaming_answer = ""
        st.session_state.streaming_complete = True
        st.rerun()

    # 2. 导航 (demo 同款: 当前页高亮, 其余跨页跳转)
    st.markdown(
        '<div class="fb-nav">'
        '<a class="fb-nav-item active" href="http://localhost:8510" target="_top">'
        '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>'
        '问答助手</a>'
        '<a class="fb-nav-item" href="http://localhost:8511" target="_top">'
        '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="6" cy="6" r="3"/><circle cx="18" cy="18" r="3"/><path d="M8.5 8.5 15 15"/><circle cx="18" cy="6" r="3"/><path d="M15.5 8.5 9 15"/></svg>'
        '方法谱系</a>'
        '<a class="fb-nav-item" href="http://localhost:8513" target="_top">'
        '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14a9 3 0 0 0 18 0V5"/><path d="M3 12a9 3 0 0 0 18 0"/></svg>'
        '语料库</a>'
        '<a class="fb-nav-item" href="http://localhost:8513" target="_top">'
        '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3v18h18"/><path d="m7 14 4-4 4 3 5-6"/></svg>'
        '评测报告</a>'
        '</div>',
        unsafe_allow_html=True,
    )

    # 3. 历史记录列表 (demo 同款: 小字标签 + 纯文本行, 悬停显删除)
    st.markdown('<div class="fb-hist-label">历史对话</div>', unsafe_allow_html=True)
    if not st.session_state.history:
        st.caption("暂无历史记录")
    else:
        # 显示最近的 15 条历史 (标题按钮 + 删除按钮)
        for i, hist in enumerate(st.session_state.history[:15]):
            _hid = _history_id_for_item(hist, i)
            if not hist.get("history_id"):
                hist["history_id"] = _hid
            _hpos = next((j for j, item in enumerate(st.session_state.history)
                          if str(item.get("history_id")) == _hid), None)
            _hc1, _hc2 = st.columns([6, 1])
            with _hc1:
                _active = (st.session_state.get('_conv_hist_id') == _hid)
                if st.button(("▍ " if _active else "") + f"{hist.get('title', '历史记录')}", key=f"hist_{_hid}", use_container_width=True):
                    st.session_state.messages = copy.deepcopy(hist.get("messages") or [])
                    st.session_state._conv_hist_id = _hid
                    st.session_state._history_view_mode = True
                    st.rerun()
            with _hc2:
                if st.button("🗑", key=f"hist_del_{_hid}", help="删除该条历史记录", use_container_width=True):
                    delete_chat_log_entry(hist.get("messages") or [])
                    if _hpos is not None:
                        del st.session_state.history[_hpos]
                    if st.session_state.get('_conv_hist_id') == _hid:
                        # 删的正是当前查看的会话 → 清空主区
                        st.session_state.messages = []
                        st.session_state._conv_hist_id = None
                        st.session_state._history_view_mode = False
                    st.rerun()

    st.divider()

    # 【证据图闭环 M4】迭代闭环模式开关(计划 3.9): 关闭时问答路径与 v3.0.0 完全一致
    st.toggle("🔁 迭代闭环模式（实验）", key="iterative_mode",
              help="证据图驱动的多轮检索-写回-判停闭环; 每问至多 3 轮检索, 证据跨轮累积于本会话证据图")

    # 【证据图闭环·借鉴③(R9)】答案·图摘要模式(仅迭代模式下生效, 默认关)
    st.toggle("✍️ 答案·图摘要模式（实验）", key="eg_summarized_answer",
              help="答案生成时用证据图摘要替代全量融合上下文(文献来源列表保留可引用); 需开启迭代闭环模式")

    st.toggle("探索性理论分析（实验）", key="first_principles_enabled",
              disabled=bool(st.session_state.get("iterative_mode")),
              help="普通模式可选；不使用本次检索原文核验，不作为实验参数或已证结论。")

    # 4. 核心组件状态 (带图标标题)
    st.markdown(f'<div class="icon-box" style="font-weight: 600; margin-top: 1rem; margin-bottom: 0.5rem;">{ICON_SETTINGS2} 核心组件状态</div>', unsafe_allow_html=True)
    with st.expander("详情", expanded=False):
        if st.session_state.agent_initialized and st.session_state.agent_conversation:
            conv = st.session_state.agent_conversation
            milvus_ok = bool(getattr(conv, 'traditional_rag', None))
            neo4j_ok = bool(getattr(conv, 'graph_rag', None))
        else:
            milvus_ok = neo4j_ok = None
        st.markdown(
            ui_style.status_pill("Milvus 向量库", milvus_ok) + " " + ui_style.status_pill("Neo4j 图谱库", neo4j_ok),
            unsafe_allow_html=True,
        )

        if st.button(" 初始化系统", use_container_width=True):
            # 强制清除所有状态，确保触发重新建立连接
            for k in ['agent_initialized', 'agent_conversation', 'current_agent_state']:
                if k in st.session_state:
                    del st.session_state[k]
            st.rerun()

    # 5. 底部统计条 (demo 同款, 真实只读计数)
    _n_papers, _n_methods, _n_confirmed = _sidebar_stats()
    st.markdown(
        f'<div class="fb-side-stats">'
        f'<div class="fb-stat"><b>{_n_papers}</b><span>文献</span></div>'
        f'<div class="fb-stat"><b>{_n_methods}</b><span>方法</span></div>'
        f'<div class="fb-stat"><b>{_n_confirmed}</b><span>confirmed 边</span></div>'
        f'</div>',
        unsafe_allow_html=True,
    )

# 日志保存功能
def save_chat_log(question, message_data):
    """保存对话日志到本地 JSONL 文件"""
    try:
        log_dir = os.path.join(PROJECT_ROOT, 'src', 'data')
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        log_file = os.path.join(log_dir, 'chat_history.jsonl')
        
        # 阶段3/4 字段一并持久化: 证据卡/阶段耗时/版图命中/执行日志
        # (doc_sources.content 截断到 1600 字符, 与证据卡"查看片段全文"显示口径一致, 控制文件体积)
        _ds = []
        for _s in (message_data.get("doc_sources") or []):
            _s2 = dict(_s)
            _s2["content"] = str(_s2.get("content") or "")[:1600]
            _ds.append(_s2)
        log_entry = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "question": question,
            "answer": message_data.get("content", ""),
            "reasoning": message_data.get("reasoning", ""),
            "fp_answer": message_data.get("fp_answer", ""),
            "fp_reasoning": message_data.get("fp_reasoning", ""),
            "graph": message_data.get("graph", None),
            "doc_sources": _ds,
            "stage_ms": message_data.get("stage_ms"),
            "atlas_hits": message_data.get("atlas_hits") or [],
            "logs": message_data.get("logs") or [],
            # 【证据图闭环 M4】迭代产物持久化(旧行无此键, 加载端 .get 兼容)
            "evidence_graph": message_data.get("evidence_graph"),
            "iterations": message_data.get("iterations"),
            "eg_stop_reason": message_data.get("eg_stop_reason"),
            "answer_quality": message_data.get("answer_quality"),
        }
        
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
            
    except Exception as e:
        print(f"⚠️ [日志保存] 失败: {e}")

def load_chat_history():
    """从本地 JSONL 文件加载历史对话"""
    history_data = []
    try:
        log_file = os.path.join(PROJECT_ROOT, 'src', 'data', 'chat_history.jsonl')
        if os.path.exists(log_file):
            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if not line.strip(): continue
                    try:
                        entry = json.loads(line)
                        # 构造侧边栏所需的消息格式
                        msgs = []
                        if entry.get("question"):
                            msgs.append({"role": "user", "content": entry["question"]})
                        if entry.get("answer"):
                            message_data = {
                                "role": "assistant",
                                "content": entry["answer"],
                                "reasoning": entry.get("reasoning", ""),
                                "fp_answer": entry.get("fp_answer", ""),
                                "fp_reasoning": entry.get("fp_reasoning", ""),
                                "graph": entry.get("graph", None),
                                "doc_sources": entry.get("doc_sources") or [],
                                "stage_ms": entry.get("stage_ms"),
                                "atlas_hits": entry.get("atlas_hits") or [],
                                "logs": entry.get("logs") or [],
                                # 【证据图闭环 M4】旧行无此键 → .get 返回 None, 历史渲染走旧分支
                                "evidence_graph": entry.get("evidence_graph"),
                                "iterations": entry.get("iterations"),
                                "eg_stop_reason": entry.get("eg_stop_reason"),
                                "answer_quality": entry.get("answer_quality"),
                            }
                            msgs.append(message_data)
                        
                        if msgs:
                            question = entry.get("question", "新对话")
                            answer = entry.get("answer", "")
                            title = question[:15] + ("..." if len(question) > 15 else "")
                            history_data.insert(0, {
                                "history_id": _make_history_id(
                                    question,
                                    answer,
                                    timestamp=entry.get("timestamp") or "legacy",
                                ),
                                "title": title,
                                "messages": msgs,
                            })
                    except:
                        continue
    except Exception as e:
        print(f"⚠️ [历史加载] 失败: {e}")
    return history_data

# 自动初始化流程 (包含 spinner 确保用户感知)
if not st.session_state.agent_initialized:
    with st.spinner(" 正在加载知识模型与建立数据库连接，请稍候..."):
        try:
            # 释放可能残留的旧连接（使用 get 安全访问）
            if st.session_state.get('agent_conversation'):
                del st.session_state['agent_conversation']
            st.session_state.agent_conversation = MultiTurnConversation()
            st.session_state.history = load_chat_history()
            st.session_state.agent_initialized = True
            st.toast("✅ 系统准备就绪")
            time.sleep(0.5) 
            st.rerun()
        except Exception as e:
            st.error(f"❌ 系统初始化严重失败: {e}")
            st.code(traceback.format_exc())

# 页面顶栏（品牌 + 核心组件真实健康状态胶囊，样式见 ui_style.py）
ui_style.render_header(st.session_state.get('agent_conversation'))

def _render_answer_quality(quality):
    """Display recorded checks without presenting an uncalibrated probability."""
    if not isinstance(quality, dict):
        return
    audit = quality.get('grounding_audit') or {}
    labels = {
        'model_screened': '已完成模型辅助原文核验，仍需结合原文判断',
        'authoritative_record_rendered': '按已保存的人工审计记录回答',
        'review_failed': '事实核验未完成，请核对证据原文',
        'no_auditable_context': '本次缺少可供核验的原文',
    }
    parts = []
    if quality.get('citation_mapping_valid') is False:
        parts.append('存在无法对应来源的引用')
    elif quality.get('citation_mapping_valid') is True:
        parts.append('引用编号可对应来源')
    if audit.get('status') in labels:
        parts.append(labels[audit['status']])
    if quality.get("operation_errors"):
        parts.append("部分检索未完成，本次证据范围受限")
    if audit.get('unresolved_repairs'):
        parts.append('有待进一步核对的内容')
    if parts:
        st.caption(' · '.join(parts))


def _render_history_message(message, message_key):
    """历史记录专用渲染：只创建静态内容，避免第三方图谱组件卸载竞态。"""
    role = message.get("role", "assistant")
    avatar_img = USER_AVATAR_SVG if role == "user" else ASSISTANT_AVATAR_SVG if role == "assistant" else None
    with st.chat_message(role, avatar=avatar_img):
        if role == "user":
            st.markdown(message.get("content", ""))
            return

        col_l, col_r = st.columns([2, 1])
        with col_l:
            st.markdown("###  回答")
            if message.get("reasoning"):
                with st.expander("点击查看内容", expanded=False):
                    st.markdown(
                        f'<div style="color:var(--fb-ink-2);font-style:italic;line-height:1.6;">'
                        f'{html.escape(str(message.get("reasoning")))}</div>',
                        unsafe_allow_html=True,
                    )
            st.markdown(clean_and_format(message.get("content", "")), unsafe_allow_html=True)
            _render_answer_quality(message.get('answer_quality'))

            if message.get("fp_answer") or message.get("fp_reasoning"):
                st.divider()
                st.markdown("###  探索性理论分析")
                st.caption("未按本次检索原文核验；不作为实验参数或已证结论。")
                with st.container():
                    st.markdown('<div class="fp-box-marker"></div>', unsafe_allow_html=True)
                    if message.get("fp_reasoning"):
                        with st.expander(" 深度思考过程 (First Principles Reasoning)", expanded=False):
                            st.markdown(format_markdown(message.get("fp_reasoning", "")))
                    if message.get("fp_answer"):
                        st.markdown(format_markdown(message.get("fp_answer", "")))

        with col_r:
            # 历史查看统一检视面板：证据、静态本体图谱和方法版图在同一容器内，
            # 不再创建 tabs，也不挂载 streamlit_agraph/vis-network。
            with st.container(border=True):
                st.markdown("#### 证据")
                history_sources = message.get("doc_sources") or []
                if history_sources:
                    history_cited = {int(ref) for ref in re.findall(r'\[Ref-(\d+)\]', message.get("content", ""))}
                    st.markdown(
                        ui_style.evidence_cards_html(history_sources, history_cited),
                        unsafe_allow_html=True,
                    )
                else:
                    st.caption("该记录未保存证据数据（阶段3之前的历史消息）")

                st.divider()
                st.markdown("#### 图谱")
                # 【证据图闭环 M4】优先证据图快照; 旧记录回退原静态图谱
                _eg = message.get("evidence_graph")
                if isinstance(_eg, dict) and _eg.get("nodes"):
                    render_evidence_graph(_eg, key=f"{message_key}_eg", height=420, interactive=False)
                else:
                    graph_data = message.get("graph")
                    if isinstance(graph_data, dict) and graph_data:
                        with st.expander(" 提取的 JSON 数据", expanded=False):
                            st.json(graph_data)
                        render_static_history_graph(graph_data, key=message_key, height=420)
                    else:
                        st.info("该回答未生成可视化图谱")

                # 【证据图闭环 M4】历史查看模式下的迭代时间线
                if message.get("iterations"):
                    st.divider()
                    st.markdown("#### 迭代时间线")
                    st.markdown(
                        ui_style.iteration_timeline_html(message.get("iterations"),
                                                         message.get("eg_stop_reason")),
                        unsafe_allow_html=True,
                    )

                # 方法版图本身是静态 canvas，不使用 streamlit_agraph。
                if "atlas_hits" in message:
                    st.divider()
                    st.markdown("方法版图（相关领域）")
                    render_qa_atlas(message.get("atlas_hits") or [], key=f"qa_atlas_{message_key}")


# 历史消息渲染
for _mi, message in enumerate(st.session_state.messages):
    if st.session_state.get('_history_view_mode'):
        _render_history_message(
            message,
            f"{st.session_state.get('_conv_hist_id') or 'history'}_{_mi}",
        )
        continue

    # 自定义头像逻辑
    if message["role"] == "user":
        avatar_img = USER_AVATAR_SVG
    elif message["role"] == "assistant":
        avatar_img = ASSISTANT_AVATAR_SVG
    else:
        avatar_img = None
        
    with st.chat_message(message["role"], avatar=avatar_img):
        if message["role"] == "user":
            st.markdown(message["content"])
        else:
            col_l, col_r = st.columns([2, 1])
            with col_l:
                st.markdown("###  回答")
                # 渲染历史记录中的思考过程
                if message.get("reasoning"):
                    with st.expander("点击查看内容", expanded=False):
                        st.markdown(f'<div style="color: #78716c; font-style: italic; line-height: 1.6;">{message["reasoning"]}</div>', unsafe_allow_html=True)
                st.markdown(clean_and_format(message["content"]), unsafe_allow_html=True)
                _render_answer_quality(message.get("answer_quality"))
                # 【新增】历史记录中的第一性原理
                if message.get("fp_answer") or message.get("fp_reasoning"):
                    st.divider()
                    st.markdown("###  探索性理论分析")
                    st.caption("未按本次检索原文核验；不作为实验参数或已证结论。")
                    with st.container():
                        st.markdown('<div class="fp-box-marker"></div>', unsafe_allow_html=True)
                        if message.get("fp_reasoning"):
                            with st.expander(" 深度思考过程 (First Principles Reasoning)", expanded=False):
                                st.markdown(format_markdown(message["fp_reasoning"]))
                        if message.get("fp_answer"):
                            st.markdown(format_markdown(message["fp_answer"]))
            with col_r:
                # 阶段3: 检视列 = 证据 / 图谱 / 流程 三 tab（与实时布局一致）
                tab_ev, tab_graph, tab_flow = st.tabs(["  证据", "  图谱", "  流程"])
                with tab_ev:
                    _hist_sources = message.get("doc_sources") or []
                    if _hist_sources:
                        _hist_cited = {int(m) for m in re.findall(r'\[Ref-(\d+)\]', message["content"])}
                        st.markdown(
                            ui_style.evidence_cards_html(_hist_sources, _hist_cited),
                            unsafe_allow_html=True,
                        )
                    else:
                        st.caption("该记录未保存证据数据（阶段3之前的历史消息）")
                with tab_graph:
                    # 【证据图闭环 M4】优先证据图快照; 旧记录回退原 agraph 本体图
                    _hist_eg = message.get("evidence_graph")
                    if isinstance(_hist_eg, dict) and _hist_eg.get("nodes"):
                        render_evidence_graph(_hist_eg, key=f"hist_{_mi}_eg", height=420, interactive=False)
                    else:
                        st.markdown("本体（Ontology）")
                        if "graph" in message and message["graph"]:
                            # 显示 JSON 数据
                            with st.expander(" 提取的 JSON 数据", expanded=False):
                                st.json(message["graph"])
                            # 动态计算图谱高度
                            calc_height = 420  # demo 同款固定高（检视列 1/3 宽度适配）
                            nodes, edges, config = prepare_graph_visualization(message["graph"]["nodes"], message["graph"]["edges"], height=calc_height)
                            agraph(nodes=nodes, edges=edges, config=config)
                            st.caption(f"数据来源: 回答文本经 LLM 抽取（非 Neo4j 直接查询）· {len(message['graph']['nodes'])} 节点 {len(message['graph']['edges'])} 边")
                        else:
                            st.info("该回答未生成可视化图谱")

                    # 方法版图联动 (历史重渲染, 用已保存的命中节点)
                    if "atlas_hits" in message:
                        st.divider()
                        st.markdown("方法版图（相关领域）")
                        render_qa_atlas(message.get("atlas_hits") or [], key=f"qa_atlas_hist_{_mi}")
                with tab_flow:
                    # 【证据图闭环 M4】迭代时间线(存在时置顶)
                    _hist_iters = message.get("iterations")
                    if _hist_iters:
                        st.markdown(
                            ui_style.iteration_timeline_html(_hist_iters, message.get("eg_stop_reason")),
                            unsafe_allow_html=True,
                        )
                    _hist_ms = message.get("stage_ms")
                    if _hist_ms:
                        _hist_rows = [
                            (lbl, 'done', ms)
                            for lbl, ms in zip(("问题解析", "多源检索", "信息融合", "答案生成"), _hist_ms)
                        ]
                        st.markdown(ui_style.flow_steps_html(_hist_rows), unsafe_allow_html=True)
                    if message.get("logs"):
                        st.caption("执行日志")
                        st.code("\n".join(message["logs"]), language="text")
                    if not _hist_ms and not message.get("logs") and not _hist_iters:
                        st.caption("该记录未保存流程数据")

# 聊天输入
if prompt := st.chat_input("示例问题：如何抑制铁铬电池的析氢反应？"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    # 从历史记录继续提问时，切回实时问答布局；历史页面只用于查看。
    st.session_state._history_view_mode = False
    st.session_state.streaming_answer = ""
    st.session_state.streaming_reasoning = "" # 【重置】
    st.session_state.streaming_complete = False
    st.session_state.current_agent_state = None
    # 清除上一轮的后端错误标记，避免旧错误污染新一轮
    st.session_state.pop('_error', None)
    # 【新增】清理上一轮的稳定占位符引用（指向已失效的元素，必须重建）
    for _k in ('fp_box_created', 'fp_reasoning_md', 'fp_answer_ph', 'think_md_ph'):
        st.session_state.pop(_k, None)
    st.rerun()

# 处理待处理的提问
if st.session_state.messages and st.session_state.messages[-1]["role"] == "user" and not st.session_state.streaming_complete:
    last_user_msg = st.session_state.messages[-1]["content"]
    
    with st.chat_message("assistant", avatar=ASSISTANT_AVATAR_SVG):
        col_1, col_2 = st.columns([2, 1])
        with col_1:
            st.markdown("###  回答")
            
            prog_placeholder = st.empty()  # 流水线阶段条（demo 同款 chip）
            # 思考过程占位符
            think_placeholder = st.empty()
            ans_placeholder = st.empty()
            
            if st.session_state.get("first_principles_enabled") and not st.session_state.get("iterative_mode"):
                st.divider()
                st.markdown("###  探索性理论分析")
                st.caption("未按本次检索原文核验；不作为实验参数或已证结论。")
            # 外层占位符：首次出现内容时再惰性创建内部稳定结构（见循环内逻辑）
            fp_outer = st.empty()

        with col_2:
            # 阶段3: 检视列 = 证据 / 图谱 / 流程 三 tab（demo 右侧检视面板的 Streamlit 等价物）
            tab_ev, tab_graph, tab_flow = st.tabs(["  证据", "  图谱", "  流程"])
            with tab_ev:
                ev_placeholder = st.empty()
                ev_placeholder.info("等待检索融合完成后展示证据卡...")
            with tab_graph:
                st.markdown("本体（Ontology）")
                graph_placeholder = st.empty()
                graph_placeholder.info("等待 Agent 识别知识实体...")
                st.divider()
                st.markdown("方法版图（相关领域）")
                st.caption("基于问题语义，在方法大陆上高亮相关领域")
                atlas_placeholder = st.empty()
                atlas_placeholder.info("等待回答完成后定位相关领域...")
            with tab_flow:
                flow_stage_ph = st.empty()
                st.caption("执行日志")
                log_placeholder = st.empty()

        # 启动后台处理逻辑
        def run_backend():
            try:
                conv = st.session_state.agent_conversation
                # 【证据图闭环 M4】迭代闭环模式: 证据图驱动多轮检索-写回-判停(开关默认关)
                if st.session_state.get('iterative_mode') and hasattr(conv, 'run_iterative_conversation'):
                    # 正式会话 ID 未定型时用临时挂载名(fresh 不读磁盘残留);
                    # 回答落库后由最终保存区统一 rebind 到正式会话 ID
                    sid = st.session_state.get('_conv_hist_id') or PENDING_SESSION_ID
                    gen = conv.run_iterative_conversation(
                        last_user_msg, session_id=sid,
                        summarized_answer=bool(st.session_state.get('eg_summarized_answer')))
                else:
                    gen = conv.run_conversation(last_user_msg,
                        enable_first_principles=bool(st.session_state.get("first_principles_enabled")))
                for state in gen:
                    st.session_state.current_agent_state = state
                st.session_state.streaming_complete = True
            except Exception as e:
                # 在后台线程记录异常
                st.session_state._error = str(e)
                st.session_state.streaming_complete = True

        back_thread = threading.Thread(target=run_backend)
        add_script_run_ctx(back_thread)
        back_thread.start()

        # 主线程实时监听与渲染
        # 【修复】阶段指标骨架只创建一次（4列固定），后续仅在阶段状态变化时替换metric内容。
        # 原先每0.1s整组销毁重建8个组件，是前端 removeChild 崩溃的主要来源。
        _metric_labels = ("问题解析", "多源检索", "信息融合", "答案生成")
        _metric_state = {"last": None}
        _stage_end = {}
        _pipe_t0 = time.time()

        def _flow_rows(stages):
            """四阶段明细行（流程 tab 用，与 chip 条同一套耗时口径）"""
            rows = []
            first_open = next((i for i, d in enumerate(stages) if not d), None)
            for i, (label, done) in enumerate(zip(_metric_labels, stages), start=1):
                if done:
                    prev = _stage_end.get(i - 1, _pipe_t0) if i > 1 else _pipe_t0
                    ms = max(0, int((_stage_end.get(i, prev) - prev) * 1000))
                    rows.append((label, 'done', ms))
                elif first_open is not None and i - 1 == first_open:
                    rows.append((label, 'running', None))
                else:
                    rows.append((label, 'pending', None))
            return rows

        def _flow_kv(st):
            """流程 tab 追加展示的真实 state 字段"""
            kv = []
            es = getattr(st, 'evidence_sources', None)
            if es:
                kv.append(('证据来源', ', '.join(es)))
            context = getattr(st, 'fused_context', None)
            if context:
                kv.append(('证据文本长度', f'{len(context):,} 字符'))
            ds = getattr(st, 'doc_sources', None)
            if ds:
                kv.append(('文献来源数', str(len(ds))))
            return kv

        def _update_stage_metrics(st):
            """阶段状态变化时重绘 chip 条（单占位符 markdown，不增删组件）"""
            stages = tuple(bool(getattr(st, f'stage_{i}_complete', False)) for i in range(1, 5))
            _its = list(getattr(st, "iterations", None) or [])
            _now = time.time()
            for _i, _d in enumerate(stages, start=1):
                if _d and _i not in _stage_end:
                    _stage_end[_i] = _now
            _sig = (stages, len(_stage_end), len(_its))   # B2: 迭代轮次推进也触发重绘
            if _sig != _metric_state["last"]:
                prog_placeholder.markdown(
                    ui_style.pipeline_chips(_metric_labels, stages, _stage_end, _pipe_t0),
                    unsafe_allow_html=True,
                )
                flow_stage_ph.markdown(
                    ui_style.flow_steps_html(_flow_rows(stages), _flow_kv(st)),
                    unsafe_allow_html=True,
                )
                # 【证据图闭环 M4】迭代模式: 四阶段 chip 之下追加逐轮时间线
                if _its:
                    _stop = next((ev.get("reason") for ev in reversed(_its)
                                  if str(ev.get("action", "")).upper() == "TERMINATE"), None)
                    flow_stage_ph.markdown(
                        ui_style.iteration_timeline_html(_its, _stop),
                        unsafe_allow_html=True,
                    )
                _metric_state["last"] = _sig

        def _ensure_fp_box(has_reasoning: bool):
            """第一性原理滚动框只创建一次：expander骨架固定，内容经内部占位符更新"""
            if 'fp_box_created' not in st.session_state:
                with fp_outer.container():
                    st.markdown('<div class="fp-box-marker"></div>', unsafe_allow_html=True)
                    if has_reasoning:
                        with st.expander(" 深度思考过程 (First Principles Reasoning)", expanded=True):
                            st.session_state.fp_reasoning_md = st.empty()
                    st.session_state.fp_answer_ph = st.empty()
                st.session_state.fp_box_created = True

        def _reset_fp_box():
            """极少数'答案先于思考到达'的情况：重建一次以补上思考expander"""
            for _k in ('fp_box_created', 'fp_answer_ph', 'fp_reasoning_md'):
                st.session_state.pop(_k, None)
            fp_outer.empty()

        last_log_size = 0
        ev_live_rendered = False
        # 流式渲染去抖: 仅内容变化时才发 delta。高频重复 delta + empty()/container() 交替
        # 会触发 Streamlit 1.38 前端竞态 "Bad message format: 'setIn' cannot be called on an ElementNode"
        _last_ans = None
        _last_think = None
        _last_fp_r = None
        _last_fp_a = None
        while not st.session_state.streaming_complete:
            state = st.session_state.get('current_agent_state')
            
            # 1. 第一性原理显示
            if state:
                fp_reasoning = getattr(state, 'fp_reasoning', '')
                fp_answer = getattr(state, 'first_principles_answer', '')
                
                if fp_reasoning or fp_answer:
                    # 【修复】滚动框与expander骨架只创建一次；fp内容含大量LaTeX公式($...$)，
                    # 高频更新时KaTeX渲染与React元素替换竞态会导致 removeChild 崩溃，
                    # 故流式期间用纯文本(.text)显示，流程结束后一次性渲染为markdown（静态渲染安全）。
                    if fp_reasoning and 'fp_box_created' in st.session_state and 'fp_reasoning_md' not in st.session_state:
                        _reset_fp_box()
                    _ensure_fp_box(bool(fp_reasoning))
                    if fp_reasoning and fp_reasoning != _last_fp_r:
                        st.session_state.fp_reasoning_md.text(fp_reasoning)
                        _last_fp_r = fp_reasoning
                    if fp_answer and fp_answer != _last_fp_a:
                        st.session_state.fp_answer_ph.text(fp_answer)
                        _last_fp_a = fp_answer

            # 2. 深度思考显示 (折叠面板模式)
            reasoning_txt = st.session_state.streaming_reasoning
            # 优先从 state 中获取，因为 state.final_answer 包含了后端处理后的 [Ref] 来源列表
            current_ans = st.session_state.streaming_answer
            
            # 如果后端 Stage 4 已经跑完，state.final_answer 会包含完整的【文献来源】列表
            if state and state.stage_4_complete and hasattr(state, 'final_answer') and state.final_answer:
                 # 当后端处理完最终答案（含参考文献表格）时，切换到最终答案展示
                 current_ans = state.final_answer
            
            # 1. 深度思考显示 (折叠面板骨架只创建一次，流式期间仅更新内部内容)
            if reasoning_txt:
                if 'think_md_ph' not in st.session_state:
                    with think_placeholder.container():
                        with st.expander("深度思考过程", expanded=True):
                            st.session_state.think_md_ph = st.empty()
                if reasoning_txt != _last_think:
                    st.session_state.think_md_ph.markdown(f'<div style="color: #78716c; font-style: italic; line-height: 1.6;">{reasoning_txt}</div>', unsafe_allow_html=True)
                    _last_think = reasoning_txt
            # 注意: 不要对 think_placeholder 反复 .empty() 后再 .container() 建块 (setIn 竞态根因);
            # 无思考内容时占位符保持未使用即可, 与 empty 等效

            # 2. 正式回答显示 (内容变化时才重渲染)
            if current_ans and current_ans != _last_ans:
                ans_placeholder.markdown(clean_and_format(current_ans), unsafe_allow_html=True)
                _last_ans = current_ans
            
            # 2. 进度与日志显示 (指标骨架固定，仅在阶段状态变化时更新内容)
            if state:
                _update_stage_metrics(state)
                if len(state.agent_logs) > last_log_size:
                    log_placeholder.code("\n".join(state.agent_logs), language="text")
                    last_log_size = len(state.agent_logs)
            
            # 3. 证据卡：Stage 3 融合完成后 doc_sources 就绪，先渲染一次（最终再带引用高亮重绘）
            if state and not ev_live_rendered and getattr(state, 'doc_sources', None):
                ev_placeholder.markdown(
                    ui_style.evidence_cards_html(state.doc_sources),
                    unsafe_allow_html=True,
                )
                ev_live_rendered = True
            
            time.sleep(0.1)

        # 最终校准与保存
        final_state = st.session_state.current_agent_state
        if final_state:
            # 强化：如果最终也没答出来，确保有一个空状态回退
            final_ans = final_state.final_answer or st.session_state.streaming_answer or "抱歉，系统处理逻辑中断，未能生成有效答案。"
            # 【新增】统一清洗一次: 剥离元评论 + 修区间符号 + 清空文献来源标题 → 用清洗后版本供渲染 / 图谱 / 持久化
            try:
                final_ans = _clean_final_answer(final_ans, sources=getattr(final_state, 'doc_sources', None))
            except Exception:
                pass
            ans_placeholder.markdown(clean_and_format(final_ans), unsafe_allow_html=True)
            with col_1:
                _render_answer_quality(getattr(final_state, 'answer_quality', None))
            _update_stage_metrics(final_state)
            
            # 证据卡最终版：正文 [Ref-n] 引用到的卡片琥珀高亮（chip ↔ 卡片编号联动）
            final_doc_sources = getattr(final_state, 'doc_sources', []) or []
            cited_ids = {int(m) for m in re.findall(r'\[Ref-(\d+)\]', final_ans)}
            ev_placeholder.markdown(
                ui_style.evidence_cards_html(final_doc_sources, cited_ids),
                unsafe_allow_html=True,
            )
            
            # 第一性原理最终结果（复用流式阶段的稳定骨架，仅更新内容）
            final_fp_answer = getattr(final_state, 'first_principles_answer', '')
            final_fp_reasoning = getattr(final_state, 'fp_reasoning', '')
            if final_fp_answer or final_fp_reasoning:
                if final_fp_reasoning and 'fp_box_created' in st.session_state and 'fp_reasoning_md' not in st.session_state:
                    _reset_fp_box()
                _ensure_fp_box(bool(final_fp_reasoning))
                if final_fp_reasoning:
                    st.session_state.fp_reasoning_md.markdown(format_markdown(final_fp_reasoning))
                if final_fp_answer:
                    st.session_state.fp_answer_ph.markdown(format_markdown(final_fp_answer))

            # 遵循 app.py 的图谱提取时机
            graph_save = None
            # 【证据图闭环 M4】优先渲染证据图快照(迭代/写回模式产出); 已渲染则跳过旧版本体抽取
            eg_snapshot = getattr(final_state, "evidence_graph_snapshot", None)
            eg_rendered = False
            try:
                if isinstance(eg_snapshot, dict) and eg_snapshot.get("nodes"):
                    with graph_placeholder.container():
                        eg_rendered = render_evidence_graph(eg_snapshot, key="eg_live", height=420)
            except Exception as e:
                graph_placeholder.error(f"证据图渲染异常: {e}")
                eg_rendered = False
            if not eg_rendered:
                try:
                    nodes_data, edges_data = generate_graph_data(final_ans)
                    if nodes_data and edges_data:
                        with graph_placeholder.container():
                            # 显示 JSON 数据
                            with st.expander(" 提取的 JSON 数据", expanded=False):
                                st.json({"nodes": nodes_data, "edges": edges_data})
                            # 动态计算图谱高度
                            calc_height = 420  # demo 同款固定高（检视列 1/3 宽度适配）
                            nodes, edges, config = prepare_graph_visualization(nodes_data, edges_data, height=calc_height)
                            agraph(nodes=nodes, edges=edges, config=config)
                            st.caption(f"数据来源: 回答文本经 LLM 抽取（非 Neo4j 直接查询）· {len(nodes_data)} 节点 {len(edges_data)} 边")
                        graph_save = {"nodes": nodes_data, "edges": edges_data}
                    else:
                        graph_placeholder.info("回答中未提取到足够的实体关系，无法生成图谱。")
                except Exception as e:
                    graph_placeholder.error(f"图谱渲染异常: {e}")

            # 方法版图联动: 问题语义 → 命中相关方法 → 高亮对应大陆
            atlas_hits = []
            try:
                conv = st.session_state.agent_conversation
                ents = getattr(final_state, "extracted_entities", []) or []
                q_text = last_user_msg + ("。" + "，".join(ents) if ents else "")
                vec = conv.arsenal.embedding_manager.embed_text(q_text)
                if vec:
                    atlas_mod = _get_landscape_module()
                    atlas_hits, _sims = atlas_mod.match_nodes(vec, top_k=30)
                with atlas_placeholder.container():
                    render_qa_atlas(atlas_hits, key="qa_atlas_live")
            except Exception as e:
                atlas_placeholder.error(f"方法版图联动异常: {e}")

            # 持久化到会话历史
            _final_iterations = list(getattr(final_state, "iterations", None) or [])
            _eg_stop = getattr(final_state, "eg_stop_reason", "") or next((ev.get("reason") for ev in reversed(_final_iterations)
                             if str(ev.get("action", "")).upper() == "TERMINATE"), None)
            message_data = {
                "role": "assistant",
                "content": final_ans,
                "reasoning": final_state.llm_reasoning or st.session_state.streaming_reasoning,
                "fp_answer": final_fp_answer,
                "fp_reasoning": final_fp_reasoning,
                "logs": final_state.agent_logs,
                "graph": graph_save,
                # 【证据图闭环 M4】证据图快照 + 迭代时间线(旧记录无此键, 历史渲染 .get 兼容)
                "evidence_graph": eg_snapshot,
                "iterations": _final_iterations or None,
                "eg_stop_reason": _eg_stop,
                "answer_quality": getattr(final_state, "answer_quality", None),
                "atlas_hits": atlas_hits,
                "doc_sources": final_doc_sources,
                "stage_ms": [row[2] for row in _flow_rows(
                    tuple(bool(getattr(final_state, f'stage_{i}_complete', False)) for i in range(1, 5))
                )]
            }
            st.session_state.messages.append(message_data)
            
            # 【修复】恢复原始日志保存调用方式，确保稳定性
            save_chat_log(last_user_msg, message_data)

            # 同步到侧栏历史：回答完成即入库，无需点"新建对话"；同一对话后续问答更新同一条目
            _hid = st.session_state.get('_conv_hist_id')
            _hpos = next((j for j, item in enumerate(st.session_state.history)
                          if str(item.get("history_id")) == str(_hid)), None) if _hid else None
            if _hpos is None:
                _record = _history_record_from_messages(st.session_state.messages)
                st.session_state.history.insert(0, _record)
                st.session_state._conv_hist_id = _record["history_id"]
            else:
                st.session_state.history[_hpos]["messages"] = copy.deepcopy(st.session_state.messages)

            # 【证据图闭环】pending 证据图迁移挂到正式会话 ID(一轮即定型, 无残留)
            if st.session_state.get('iterative_mode') and hasattr(st.session_state.agent_conversation, '_migrate_evidence_store'):
                try:
                    st.session_state.agent_conversation._migrate_evidence_store(
                        st.session_state._conv_hist_id)
                except Exception as _mig_err:
                    print(f"⚠️ [证据图迁移] 失败(无害, 下轮自动重试): {_mig_err}")

            st.session_state.streaming_complete = True
            st.rerun()
        else:
            # 后端在产出任何状态前抛异常（原逻辑下 _error 被吞掉，界面无提示且不落盘）
            _backend_err = st.session_state.get('_error')
            _fail_text = f"抱歉，本次回答生成失败：{_backend_err}" if _backend_err else "抱歉，系统处理逻辑中断，未能生成有效答案。"
            ans_placeholder.error(_fail_text)
            _fail_msg = {"role": "assistant", "content": _fail_text}
            st.session_state.messages.append(_fail_msg)
            # 失败也落盘，保证提问记录不丢失
            save_chat_log(last_user_msg, _fail_msg)
            _record = _history_record_from_messages(st.session_state.messages)
            st.session_state.history.insert(0, _record)
            st.session_state._conv_hist_id = _record["history_id"]
            # 【证据图闭环】失败路径同样迁移, 避免 pending 文件残留
            if st.session_state.get('iterative_mode') and hasattr(st.session_state.agent_conversation, '_migrate_evidence_store'):
                try:
                    st.session_state.agent_conversation._migrate_evidence_store(
                        st.session_state._conv_hist_id)
                except Exception as _mig_err:
                    print(f"⚠️ [证据图迁移] 失败(无害, 下轮自动重试): {_mig_err}")
            st.session_state.streaming_complete = True
            st.rerun()

# 图谱背景由 prepare_graph_visualization 的配置和全局主题 CSS 负责。
# 不再注入会在每次 rerun 创建 iframe/定时器的 DOM 操作脚本。
