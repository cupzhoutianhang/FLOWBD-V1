import streamlit as st
import json
import requests
import sys
import os

# 【核心修复】解决程序崩溃与网络连接问题
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
# 彻底清理无效的代理环境变量（防止 requests 误将其识别为有效代理）
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
USER_AVATAR_SVG = "data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 width=%2224%22 height=%2224%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22%2366C5F2%22 stroke-width=%222%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22 class=%22lucide lucide-user-search-icon lucide-user-search%22%3E%3Ccircle cx=%2210%22 cy=%227%22 r=%224%22/%3E%3Cpath d=%22M10.3 15H7a4 4 0 0 0-4 4v2%22/%3E%3Ccircle cx=%2217%22 cy=%2217%22 r=%223%22/%3E%3Cpath d=%22m21 21-1.9-1.9%22/%3E%3C/svg%3E"
# 助手自定义头像 (SVG Data URI, stroke设置为 #E6E6E6)
ASSISTANT_AVATAR_SVG = "data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 width=%2224%22 height=%2224%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22%2366C5F2%22 stroke-width=%222%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22 class=%22lucide lucide-bot-message-square-icon lucide-bot-message-square%22%3E%3Cpath d=%22M12 6V2H8%22/%3E%3Cpath d=%22M15 11v2%22/%3E%3Cpath d=%22M2 12h2%22/%3E%3Cpath d=%22M20 12h2%22/%3E%3Cpath d=%22M20 16a2 2 0 0 1-2 2H8.828a2 2 0 0 0-1.414.586l-2.202 2.202A.71.71 0 0 1 4 20.286V8a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2z%22/%3E%3Cpath d=%22M9 11v2%22/%3E%3C/svg%3E"

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
import agent.part5_glm # 【新增】显式导入以确保补丁生效

# 【核心同步】用于跨线程同步 RAG 思考状态 (解决 st.session_state 在子线程不稳定的问题)
THREAD_STATES = {} 
ANSWER_GEN_STATE = threading.local()

# 【核心同步】用于解析流式输出并同步到 State 对象
# 强制对齐 app2.py 的初始化路径补丁
import multi_turn_chat
import contextlib
import io
multi_turn_chat.contextlib = contextlib
multi_turn_chat.io = io

class NullContext:
    def __init__(self, *args, **kwargs): pass
    def __enter__(self): return self
    def __exit__(self, *args): pass

# 拦截重定向逻辑，让初始化日志重回终端 (透传后端错误)
contextlib.redirect_stdout = lambda x: NullContext()
contextlib.redirect_stderr = lambda x: NullContext()

# 强制校准后端所有路径变量
true_root = PROJECT_ROOT
multi_turn_chat.PROJECT_ROOT = true_root
multi_turn_chat.AGENT_DIR = os.path.join(true_root, 'src', 'agent')
print(f"🔧 [系统] 后端路径校准完成: {multi_turn_chat.PROJECT_ROOT}")

def patched_handle_streaming_response(self, response, **kwargs) -> str:
    full_answer = ""
    full_reasoning = ""
    reasoning_started = False
    is_answer_mode = False 
    
    on_chunk = kwargs.get('on_chunk')
    on_reasoning = kwargs.get('on_reasoning')
    state_obj = kwargs.get('state_obj')
    
    THINK_START = "\n" + ">" * 30 + " [RAG 深度思考] " + ">" * 30 + "\n"
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
                    
                    if content and not is_answer_mode:
                        is_answer_mode = True
                        if reasoning_started:
                            print(THINK_END, end='', flush=True)
                            reasoning_started = False
                    
                    if reasoning:
                        if is_answer_mode:
                            full_answer += reasoning
                            if on_chunk: on_chunk(reasoning)
                        else:
                            if not reasoning_started:
                                print(THINK_START, end='', flush=True)
                                reasoning_started = True
                            full_reasoning += reasoning
                            
                            # 同步到 State 对象 (优先使用直传的对象，其次使用线程ID查找)
                            target = state_obj
                            if not target:
                                tid = threading.get_ident()
                                target = THREAD_STATES.get(tid)
                            
                            if target:
                                if hasattr(target, 'answer_reasoning'):
                                    target.answer_reasoning += reasoning
                                elif hasattr(target, 'llm_reasoning'):
                                    target.llm_reasoning += reasoning
                            
                            if on_reasoning: on_reasoning(reasoning)
                            
                        print(reasoning, end='', flush=True)
                        continue
                    
                    if content:
                        full_answer += content
                        print(content, end='', flush=True)
                        if on_chunk: on_chunk(content)
            except Exception:
                pass
        
        if reasoning_started:
            print(THINK_END, end='', flush=True)
        print() 
            
        return full_answer if full_answer.strip() else full_reasoning
    except Exception as e:
        print(f"\n❌ [RAG补丁] 异常: {e}")
        return ""

def patched_call_llm(self, prompt, **kwargs):
    """通用的 call_llm 补丁，支持 **kwargs 以防止 TypeError"""
    import time
    import requests
    
    temperature = kwargs.get('temperature', 0.0)
    max_tokens = kwargs.get('max_tokens', 50000)
    model = kwargs.get('model') or self.model
    stream = kwargs.get('stream', False)
    system_prompt = kwargs.get('system_prompt')
    repetition_penalty = kwargs.get('repetition_penalty', 1.0)
    on_chunk = kwargs.get('on_chunk')
    
    api_url = f"{self.base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {self.api_key}",
        "Content-Type": "application/json"
    }
    
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    
    data = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "repetition_penalty": repetition_penalty,
        "stream": stream
    }
    
    try:
        # 尝试从线程局部变量获取 state (由 AnswerGenerationAgent 补丁注入)
        if hasattr(ANSWER_GEN_STATE, 'current_state') and ANSWER_GEN_STATE.current_state:
            kwargs['state_obj'] = ANSWER_GEN_STATE.current_state
            
        # 增加对网络波动（如 ProxyError）的防御性配置
        response = requests.post(api_url, headers=headers, json=data, timeout=(30, 300), stream=stream, proxies={'http': None, 'https': None})
        if response.status_code == 200:
            if stream:
                return self._handle_streaming_response(response, **kwargs)
            else:
                res_json = response.json()
                return res_json['choices'][0]['message']['content'].strip()
        return f"❌ LLM调用失败 ({response.status_code})"
    except requests.exceptions.ProxyError:
        return "❌ 代理连接异常：请检查本地 VPN/代理设置或尝试关闭代理环境变量。"
    except Exception as e:
        return f"❌ LLM调用异常: {e}"

def patched_answer_generate(self, state):
    """AnswerGenerationAgent.generate 的包装补丁，用于在调用链中注入 state"""
    ANSWER_GEN_STATE.current_state = state
    try:
        # 执行原始 generate 方法 (该方法由 apply_robust_patches 备份)
        return self._original_generate(state)
    finally:
        ANSWER_GEN_STATE.current_state = None


# 【新增】补丁 1.5: 第一性原理 Agent 流式生成补丁 (注入分隔符以支持前端分离显示)
def patched_fp_generate_stream(self, question: str):
    """流式生成第一性原理回答 (带分隔符注入)"""
    # 优先使用本地设置
    base_url = getattr(self, 'base_url', self.llm_config.base_url)
    api_url = f"{base_url.rstrip('/')}/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {self.api_key}",
        "Content-Type": "application/json"
    }
    
    # 优先使用本地设置
    model = getattr(self, 'model', self.llm_config.model)
    
    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": question}
        ],
        "temperature": 0.2,
        "stream": True # 强制流式
    }
    
    # 增加重试机制和更稳健的超时处理
    max_retries = 2
    for attempt in range(max_retries + 1):
        try:
            # 增加对网络波动（如 ProxyError）的防御性配置
            response = requests.post(api_url, headers=headers, json=data, stream=True, timeout=(10, 60), proxies={'http': None, 'https': None})
            if response.status_code != 200:
                if attempt < max_retries:
                    time.sleep(1)
                    continue
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
                        
                        # 1. 处理 Reasoning
                        reasoning = delta.get('reasoning_content', '')
                        if reasoning:
                            yield {"type": "reasoning", "content": reasoning}
                            
                        # 2. 处理 Content
                        content = delta.get('content', '')
                        if content:
                            yield {"type": "content", "content": content}
                except json.JSONDecodeError:
                    continue
            return # 成功退出
                 
        except Exception as e:
            if attempt < max_retries:
                time.sleep(1)
                continue
            yield f"❌ 第一性原理生成异常 (Patch): {str(e)}"

# 【核心修复】强制直接应用补丁，不依赖 apply_robust_patches 的遍历
agent.part5_glm.FirstPrinciplesAgent.generate_stream = patched_fp_generate_stream
print("🚀 [系统] FirstPrinciplesAgent.generate_stream 补丁已强制应用")

# ========== 补丁 2: 意图识别与 RAG 检索链路强化 ==========

# 1. 强制重载模块，抹除之前可能残留在内存中的错误补丁
import importlib
try:
    import agent.part5_multiagent_integration as ami
    import rag.class_query as cq
    importlib.reload(ami)
    importlib.reload(cq)
    print("🧹 [系统] 检索模块已强制重置，正在重新应用清洁补丁...")
except Exception as e:
    print(f"⚠️ [系统] 模块重置警告: {e}")

# 2. 彻底清理类属性中可能存在的旧备份（防止递归死循环）
for attr in ['_original_recall_bak', '_original_recall_method', '_patched']:
    if hasattr(ami.MultiSourceRetrievalAgent, attr):
        delattr(ami.MultiSourceRetrievalAgent, attr)

# 3. 增强的识别引擎
def patched_identify_battery_type(title, debug=False):
    if not title: return 'other'
    t = str(title).lower()
    # 铁铬电池识别
    if any(kw in t for kw in ["铁", "铬", "iron", "chromium"]) and any(kw in t for kw in ["配方", "优化", "电解液", "formula", "electrolyte"]):
        return 'iron_chromium'
    if any(kw in t for kw in ["铁铬", "iron-chromium", "icrfb"]):
        return 'iron_chromium'
    return 'other'

# 拦截所有可能的分类入口
for mod in [cq, sys.modules.get('rag.classification'), sys.modules.get('classification')]:
    if mod: mod.identify_battery_type = patched_identify_battery_type

# 4. 高可靠 RAG 检索补丁 (集成核心 Fallback 逻辑)
# 直接通过 class 获取重载后的原始方法引用
ORIGINAL_RECALL = ami.MultiSourceRetrievalAgent._retrieve_with_document_recall

def high_reliability_retrieve(self, question, top_k=30, rerank_top_k=30, state=None):
    """鲁棒检索逻辑"""
    try:
        # 第一次尝试：按识别类型检索
        res = ORIGINAL_RECALL(self, question, top_k, rerank_top_k, state)
        count = len(res) if res else 0
        
        # 核心 Fallback：如果铁铬电池专项搜索结果为 0，自动降级为全库检索
        if count == 0 and any(kw in question for kw in ["铁", "铬", "iron", "chromium"]):
            print("💡 [RAG补丁] 特定类型无结果，正在触发全库 Fallback 检索...")
            if state: state.log("RAG", "特定领域召回为空，正在全库重试...")
            
            import rag.class_query as tmp_cq
            old_func = tmp_cq.identify_battery_type
            try:
                tmp_cq.identify_battery_type = lambda x, **kw: 'other'
                res = ORIGINAL_RECALL(self, question, top_k, rerank_top_k, state)
                count = len(res) if res else 0
            finally:
                tmp_cq.identify_battery_type = old_func
        
        final_msg = f"📊 [检索监控] 最终召回结果: {count} 个块"
        print(final_msg)
        if state: state.log("Retrieval", final_msg)
        
        return res
    except Exception as e:
        print(f"❌ [检索监控] 执行重大异常: {e}")
        return []

# 注入新补丁
ami.MultiSourceRetrievalAgent._retrieve_with_document_recall = high_reliability_retrieve
print("🚀 [系统] 高可靠 RAG 检索补丁已激活 (具备自动降级修复能力)")

# ========== 补丁 3: 图谱提取驱动迁移 (解决 Invalid edge format) ==========
def patched_graph_llm_call(system_msg, user_msg, supplier=None):
    """
    专门用于图谱提取的 LLM 调用。
    强制使用 Kimi K2 模型以确保 JSON 结构的严谨性，解决 GLM 偶尔输出 source/target 而非 from/to 的问题。
    """
    from agent.part1_knowledge_arsenal import LLMConfig
    # 使用 Kimi 专用配置
    kimi_llm = LLMConfig(
        api_key=__import__("os").environ.get("MOONSHOT_API_KEY", ""),
        base_url="https://api.moonshot.cn/v1",
        model="kimi-k2-0905-preview"
    )
    # 直接调用（由于 LLMConfig.call_llm 已被 patched_call_llm 全局拦截，这里会自动使用 requests 请求）
    return kimi_llm.call_llm(user_msg, system_prompt=system_msg, temperature=0.0)

# 强制替换 utils 中的默认 LLM 调用，确保 Ontology 逻辑使用 Kimi
import utils
utils.call_llm = patched_graph_llm_call
print("🚀 [系统] 图谱生成引擎已成功迁移回 Kimi (K2-Preview)")

# 最终补丁应用：全量扫描大模型流处理
def apply_robust_patches():
    count = 0
    target_methods = {
        '_handle_streaming_response': patched_handle_streaming_response,
        'call_llm': patched_call_llm
    }
    for mod_name, module in list(sys.modules.items()):
        if 'part1_knowledge_arsenal' in mod_name:
            if hasattr(module, 'LLMConfig'):
                cls_obj = getattr(module, 'LLMConfig')
                for m_name, m_func in target_methods.items():
                    setattr(cls_obj, m_name, m_func)
                    count += 1
        
        # 【新增】应用 AnswerGenerationAgent 补丁 (用于注入状态)
        if 'part5_multiagent_integration' in mod_name:
             if hasattr(module, 'AnswerGenerationAgent'):
                 cls_obj = getattr(module, 'AnswerGenerationAgent')
                 if not hasattr(cls_obj, '_original_generate'):
                     cls_obj._original_generate = cls_obj.generate
                     cls_obj.generate = patched_answer_generate
                     count += 1
        
        # 【新增】应用 FirstPrinciplesAgent 补丁
        if 'part5_glm' in mod_name:
             if hasattr(module, 'FirstPrinciplesAgent'):
                 cls_obj = getattr(module, 'FirstPrinciplesAgent')
                 setattr(cls_obj, 'generate_stream', patched_fp_generate_stream)
                 count += 1
    
    # 强制覆盖全局类
    LLMConfig._handle_streaming_response = patched_handle_streaming_response
    LLMConfig.call_llm = patched_call_llm
    
    print(f"🚀 [系统] 终端打印对齐与鲁棒接口补丁已生效 (覆盖 {count+2} 处)")

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

from multi_turn_chat import MultiTurnConversation

# 补丁 3: 图谱生成驱动迁移 (迁移至 Kimi 以提升响应速度)
def patched_graph_llm_call(system_msg, user_msg, supplier=None):
    # 使用后端 Kimi 专用配置
    llm = LLMConfig(
        api_key=__import__("os").environ.get("MOONSHOT_API_KEY", ""),
        base_url="https://api.moonshot.cn/v1",
        model="kimi-k2-0905-preview"
    )
    # 调用 Kimi 进行极速图谱提取
    return llm.call_llm(user_msg, system_prompt=system_msg, temperature=0.0)

# 双重覆盖，确保 utils.py 内部也能感知到补丁
llm_utils.call_llm = patched_graph_llm_call
utils.call_llm = patched_graph_llm_call

# 补丁 4: Neo4j 认证与路径对齐 (确保 127.0.0.1/neo4j123)
try:
    from agent.part1_knowledge_arsenal import KnowledgeArsenal, KnowledgeBaseConnector
    
    # 子补丁 A: 拦截 KnowledgeBaseConnector 底层初始化
    orig_connector_init = KnowledgeBaseConnector.__init__
    def patched_connector_init(self, *args, **kwargs):
        if 'neo4j_password' not in kwargs: kwargs['neo4j_password'] = __import__("os").environ.get("NEO4J_PASSWORD", "")
        if 'neo4j_uri' not in kwargs: kwargs['neo4j_uri'] = "bolt://127.0.0.1:7687"
        return orig_connector_init(self, *args, **kwargs)
    KnowledgeBaseConnector.__init__ = patched_connector_init
    
    # 子补丁 B: 拦截 KnowledgeArsenal 初始化
    orig_arsenal_init = KnowledgeArsenal.__init__
    def patched_arsenal_init(self, *args, **kwargs):
        if 'neo4j_password' not in kwargs: kwargs['neo4j_password'] = __import__("os").environ.get("NEO4J_PASSWORD", "")
        if 'neo4j_uri' not in kwargs: kwargs['neo4j_uri'] = "bolt://127.0.0.1:7687"
        return orig_arsenal_init(self, *args, **kwargs)
    KnowledgeArsenal.__init__ = patched_arsenal_init
    
    # 子补丁 C: 让底层错误显现
    orig_init_neo4j = KnowledgeBaseConnector.init_neo4j
    def verbose_init_neo4j(self):
        res = orig_init_neo4j(self)
        if not res:
            from neo4j import GraphDatabase, basic_auth
            try:
                # 在此处进行一次带报错捕获的强制连接尝试
                driver = GraphDatabase.driver(self.neo4j_uri, auth=basic_auth(self.neo4j_user, self.neo4j_password), encrypted=False)
                with driver.session() as session: session.run("RETURN 1").consume()
                print(f"✅ [补丁修复] 重连 Neo4j 成功 ({self.neo4j_uri})")
                return True
            except Exception as e:
                print(f"❌ [连接核心故障] 无法连接到 Neo4j ({self.neo4j_uri}): {e}")
        return res
    KnowledgeBaseConnector.init_neo4j = verbose_init_neo4j
    
    print("🚀 [系统] Neo4j 全局认证与 127.0.0.1 路径补丁已加载")
except Exception as e:
    print(f"⚠️ [系统] 认证补丁加载失败: {e}")

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

# 诊断补丁: 揭示 GraphQA 初始化内部错误
try:
    import graph_rag.graph_qa_v2
    orig_gqa_init = graph_rag.graph_qa_v2.GraphQA.__init__
    def debug_gqa_init(self, *args, **kwargs):
        # 强制对齐 GraphQA 的默认参数
        if 'neo4j_password' not in kwargs: kwargs['neo4j_password'] = __import__("os").environ.get("NEO4J_PASSWORD", "")
        if 'neo4j_uri' not in kwargs: kwargs['neo4j_uri'] = "bolt://127.0.0.1:7687"
        try:
            return orig_gqa_init(self, *args, **kwargs)
        except Exception as e:
            print(f"\n❌ [核心故障] GraphQA 初始化发生异常: {e}")
            import traceback
            traceback.print_exc()
            raise
    graph_rag.graph_qa_v2.GraphQA.__init__ = debug_gqa_init
    print("🧪 [系统] GraphQA 增强诊断补丁已挂载")
except Exception as e:
    print(f"⚠️ [系统] 诊断补丁加载失败: {e}")
def format_markdown(text):
    if not text: return text
    
    # 【核心修复】Latex 语法对齐与爆红防御
    # 针对 GLM 偶尔输出不完整的 \text{...} 或未闭合的 $$ 情况
    processed = text.replace('\n', '  \n')
    
    # 自动闭合检测 (简单的括号匹配尝试)
    if r'\text{' in processed:
        open_count = processed.count(r'\text{')
        close_count = processed.count(r'}')
        if open_count > close_count:
            processed += '}' * (open_count - close_count)
            
    # 如果发现未闭合的 $$，进行补全防止全局渲染崩溃
    if processed.count('$$') % 2 != 0:
        processed += '\n$$'
        
    return processed

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
                'color': '#FFFFFF', # 反转为白色
                'face': 'Inter', 
                'strokeWidth': 0, 
                'align': 'center'
            }
        ))
    
    edges = [
        Edge(
            source=str(e['from']), 
            target=str(e['to']), 
            label=str(e['label']),
            color="#2E86C1", # 藏青色 (Visible Navy)
            width=2,
            font={
                'size': 12, 
                'color': '#FFFFFF', 
                'face': 'Inter', 
                'strokeWidth': 0, 
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
        highlightColor="#F7A7A6",
        collapsible=False,
        node={'labelProperty': 'label'}, 
        link={'labelProperty': 'label', 'renderLabel': True},
        hierarchical=False,
        backgroundColor="#0A0A0B" # 再次尝试十六进制，确保库能正确解析
    )
    return nodes, edges, config

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
st.markdown(f"""
<style>
    /* 1. 极黑背景与科技感网格 */
    .stApp {{
        background-color: #0A0A0B !important;
        background-image: 
            linear-gradient(rgba(255, 140, 0, 0.03) 1px, transparent 1px),
            linear-gradient(90deg, rgba(255, 140, 0, 0.03) 1px, transparent 1px);
        background-size: 30px 30px;
    }}
    
    /* 2. 侧边栏暗色调 */
    [data-testid="stSidebar"] {{
        background-color: #141416 !important;
        border-right: 1px solid rgba(255, 255, 255, 0.05);
    }}
    
    /* 3. Lumecoder 风格标题 */
    .brand-title {{
        font-family: 'Inter', sans-serif;
        font-size: 24px;
        font-weight: 800;
        letter-spacing: -0.5px;
        color: #FF8C00 !important; /* 琥珀色 */
        margin-bottom: 25px;
        text-shadow: 0 0 10px rgba(255, 140, 0, 0.2);
    }}
    
    /* 4. 按钮科技感重塑 */
    div.stButton > button {{
        background-color: transparent !important;
        color: #E6E6E6 !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 6px !important;
        font-weight: 500 !important;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }}
    
    /* 悬停发光 */
    div.stButton > button:hover {{
        border-color: #FF8C00 !important;
        box-shadow: 0 0 15px rgba(255, 140, 0, 0.1);
        transform: translateY(-1px);
    }}
    
    /* Primary 按钮（琥珀色高亮） */
    div[data-testid="stSidebar"] button[kind="primary"] {{
        background-color: rgba(255, 140, 0, 0.1) !important;
        color: #FF8C00 !important;
        border: 1px solid #FF8C00 !important;
    }}
    
    div[data-testid="stSidebar"] button[kind="primary"]:hover {{
        background-color: #FF8C00 !important;
        color: #000 !important;
    }}

    /* 5. 注入“新建对话”图标 */
    div[data-testid="stSidebar"] button[kind="primary"] p::before {{
        content: "" !important;
        display: inline-block !important;
        width: 18px !important;
        height: 18px !important;
        margin-right: 8px !important;
        background-color: currentColor !important;
        vertical-align: middle !important;
        -webkit-mask: url("{SVG_MSG_PLUS}") no-repeat center !important;
        mask: url("{SVG_MSG_PLUS}") no-repeat center !important;
        mask-size: contain !important;
    }}

    /* 6. 图案化对齐容器 */
    .icon-box {{
        display: flex !important;
        align-items: center !important;
        gap: 8px !important;
        color: rgba(255, 255, 255, 0.7) !important;
    }}
    
    .icon-box svg {{
        stroke: #FF8C00 !important;
    }}

    /* 7. Markdown 文字适配 */
    .stMarkdown p, .stMarkdown li {{
        color: #E6E6E6 !important;
        line-height: 1.7 !important;
    }}
    
    .stMarkdown h3 {{
        color: #FFFFFF !important;
        font-size: 1.15rem !important; /* 缩小字号 */
        margin-top: 20px !important;
        margin-bottom: 15px !important;
    }}
    
    /* 8. 下拉框与代码块 - 强化暗色一致性 */
    div[data-testid="stExpander"], 
    div[data-testid="stExpander"] details,
    div[data-testid="stExpander"] summary {{
        background-color: rgba(255, 255, 255, 0.02) !important;
        border: none !important;
        border-radius: 8px !important;
    }}
    
    div[data-testid="stExpander"] {{
        border: 1px solid rgba(255, 255, 255, 0.05) !important;
    }}

    /* 9. 优化对话气泡样式（用户提问与AI回答） */
    div[data-testid="stChatMessage"] {{
        background-color: #0A0A0B !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important; /* 微弱边框区分 */
        border-radius: 12px !important;
        padding: 15px !important;
        margin-bottom: 10px !important;
    }}

    /* 【最终方案】全局强制所有代码块、JSON、预格式文本及其容器为黑色 */
    pre, code, .stCodeBlock, .stJson, 
    div[data-testid="stCodeBlock"], 
    div[data-testid="stJson"], 
    div[data-testid="stCodeBlock"] pre,
    div[data-testid="stJson"] div {{
        background-color: #0A0A0B !important;
        background: #0A0A0B !important;
        color: #E6E6E6 !important;
    }}

    /* 针对 JSON 内部字体的深度优化 */
    div[data-testid="stJson"] span {{
        color: #A0C4FF !important; /* 浅蓝色高亮 Key */
    }}
    div[data-testid="stJson"] span[class*="string"] {{
        color: #CEF5D2 !important; /* 浅绿色高亮 String */
    }}
    div[data-testid="stJson"] span[class*="number"] {{
        color: #FFD6A5 !important; /* 浅橙色高亮 Number */
    }}
    
    /* 针对下拉框展开内容的特定修复 */

    /* 针对下拉框展开内容的特定修复 */
    div[data-testid="stExpander"] details + div {{
        background-color: #0A0A0B !important;
    }}
    
    div[data-testid="stExpander"] div[role="region"] {{
        background-color: #0A0A0B !important;
    }}

    /* 强制图谱 iframe 容器为黑色 */
    iframe {{
        background-color: #0A0A0B !important;
    }}

    /* 彻底消除页眉并压缩顶部空间 */
    /* 彻底消除页眉白色残留，但保留交互功能（如侧边栏开关、Stop按钮） */
    header[data-testid="stHeader"] {{
        background-color: transparent !important;
    }}
    
    /* 修复重复按钮：当侧边栏展开时，隐藏页眉中的多余折叠按钮 */
    [data-testid="stAppViewContainer"][data-sidebar-state="expanded"] header[data-testid="stHeader"] {{
        display: none !important;
    }}

    /* 12. 底部固定栏极致修复：回归极简原生逻辑，由系统自动对齐内容区 */
    div[data-testid="stBottom"] {{
        background-color: #0A0A0B !important; 
        border: none !important;
        position: fixed !important;
        bottom: 0 !important;
        /* 核心：展开状态下的偏移量 (21rem) */
        left: 21rem !important;
        right: 0 !important;
        width: auto !important;
        z-index: 99 !important;
        display: flex !important;
        justify-content: center !important;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }}

    div[data-testid="stBottom"] > div {{
        background-color: transparent !important;
        max-width: 1300px !important; /* 展开状态下的固定宽度，用户确认此时刚好 */
        width: 100% !important;
        margin: 0 auto !important;
        padding-bottom: 20px !important;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }}

    /* 核心：侧边栏收起时的状态适配 (兼容原生属性与 JS 注入类) */
    [data-testid="stAppViewContainer"][data-sidebar-state="collapsed"] div[data-testid="stBottom"],
    body.sidebar-collapsed div[data-testid="stBottom"] {{
        left: 0 !important;
    }}

    [data-testid="stAppViewContainer"][data-sidebar-state="collapsed"] div[data-testid="stBottom"] > div,
    body.sidebar-collapsed div[data-testid="stBottom"] > div {{
        max-width: 100% !important; /* 关键：收起时解除限制，跟随回答区域占满全屏 */
        padding-left: 5rem !important; /* 与上方 .block-container 默认边距对齐 */
        padding-right: 5rem !important;
    }}
    
    /* 核心输入框样式定制：仅保留边框和背景，宽度由系统按宽版布局自动撑开 */
    div[data-testid="stChatInput"] {{
        background-color: #141416 !important;
        border: 1px solid #FF8C00 !important;
        border-radius: 12px !important;
    }}

    /* 防止内容被底部固定栏遮挡 - 迁移 app2.py 的大留白 */
    .main .block-container {{
        padding-bottom: 250px !important; 
    }}

    /* 侧边栏样式优化：显式设置层级高于底栏 (999) */
    section[data-testid="stSidebar"] {{
        z-index: 1000 !important;
        background-color: #141416 !important;
        border-right: 1px solid rgba(255, 255, 255, 0.05) !important;
    }}

    /* 深度修复输入框：同步 app2.py 风格 */
    div[data-testid="stChatInput"] {{
        background-color: #141416 !important;
        border: 1px solid #FF8C00 !important;
        border-radius: 12px !important;
        padding: 0px !important; 
        box-shadow: none !important;
        overflow: hidden !important;
    }}
    
    div[data-testid="stChatInput"] * {{
        border: none !important;
        box-shadow: none !important;
        background-color: transparent !important;
        outline: none !important;
    }}

    div[data-testid="stChatInput"] textarea {{
        background-color: transparent !important;
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
        caret-color: #FF8C00 !important;
        padding: 10px 15px !important; /* 精调内边距，解决文字偏下问题 */
        line-height: 1.4 !important;    /* 优化行高 */
        width: 100% !important;
        min-height: 46px !important;    /* 保持高度稳定 */
    }}

    div[data-testid="stChatInput"] button svg {{
        fill: #FF8C00 !important;
    }}

    .stApp {{
        background-color: #0A0A0B !important;
    }}
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3, [data-testid="stSidebar"] p, [data-testid="stSidebar"] label {{
        color: #E6E6E6 !important;
    }}
    
    [data-testid="stSidebar"] .stCaption {{
        color: rgba(255, 255, 255, 0.5) !important;
    }}

    /* 修补 Metric 标签 */
    [data-testid="stMetricLabel"] {{
        color: rgba(255, 255, 255, 0.8) !important;
    }}
    [data-testid="stMetricValue"] {{
        color: #FFFFFF !important;
    }}

    /* 处理 Info/Success 等提示框内部文字 */
    .stAlert p, .stAlert div {{
        color: #FFFFFF !important;
    }}
    
    /* 折叠框标题提亮 */
    div[data-testid="stExpander"] summary p {{
        color: #FFFFFF !important;
        font-weight: 500 !important;
    }}

    /* 11. 修复 Spinner 和 Toast 的暗黑模式细节 */
    div[data-testid="stSpinner"] p {{
        color: #FF8C00 !important; /* 琥珀色显示加载文字 */
        font-weight: 500 !important;
    }}

    div[data-testid="stToast"] {{
        background-color: #141416 !important;
        color: white !important;
        border: 1px solid #FF8C00 !important;
        border-radius: 8px !important;
    }}
    
    div[data-testid="stToast"] [data-testid="stMarkdownContainer"] p {{
        color: white !important;
    }}

    /* 基础布局优化：大幅度上移内容并减小顶部空白 */
    .stApp {{
        background-color: #0A0A0B;
    }}
    /* 这里移除了重复的 block-container 定义以防冲突 */
    
    /* 调整标题区域间距 */
    h1 {{
        margin-top: -50px !important;
        margin-bottom: 5px !important;
        padding-top: 0 !important;
    }}
    .stMarkdown p {{
        margin-bottom: 5px !important;
    }}
    
    /* 12. 第一性原理固定高度容器样式 */
    .fp-scroll-container {{
        height: 350px !important;
        max-height: 350px !important;
        overflow-y: auto !important;
        scroll-behavior: smooth !important; /* 丝滑滚动 */
        padding: 15px !important;
        background-color: rgba(255, 255, 255, 0.02) !important;
        border: 1px solid rgba(255, 140, 0, 0.2) !important;
        border-radius: 10px !important;
        font-family: inherit !important;
        line-height: 1.6 !important;
        box-sizing: border-box !important;
    }}
    
    /* 自定义滚动条保持琥珀色风格 */
    .fp-scroll-container::-webkit-scrollbar {{
        width: 6px;
    }}
    .fp-scroll-container::-webkit-scrollbar-track {{
        background: rgba(0, 0, 0, 0.1);
    }}
    .fp-scroll-container::-webkit-scrollbar-thumb {{
        background: rgba(255, 140, 0, 0.3);
        border-radius: 10px;
    }}
    .fp-scroll-container::-webkit-scrollbar-thumb:hover {{
        background: rgba(255, 140, 0, 0.5);
    }}
</style>
""", unsafe_allow_html=True)

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
    'current_agent_state': None
}.items():
    if key not in st.session_state:
        st.session_state[key] = default_val

# Sidebar 配置廊
with st.sidebar:
    # 1. 顶部品牌与操作区 (仿豆包简约设计)
    st.markdown('<div class="brand-title"> FlowBD智能平台</div>', unsafe_allow_html=True)
    
    # 注入带有图标的“新建对话”标题感
    if st.button(f" 新建对话", use_container_width=True, type="primary"):
        # 如果当前有聊天记录，则存入历史库
        if st.session_state.messages:
            # 自动提取首个用户问题作为标题
            first_user_msg = next((m["content"] for m in st.session_state.messages if m["role"] == "user"), "新对话")
            title = first_user_msg[:15] + ("..." if len(first_user_msg) > 15 else "")
            st.session_state.history.insert(0, {"title": title, "messages": st.session_state.messages.copy()})
        
        # 重置当前会话
        st.session_state.messages = []
        st.session_state.streaming_answer = ""
        st.session_state.streaming_complete = True
        st.rerun()

    # 2. 历史记录列表 (带图标标题)
    st.markdown(f'<div class="icon-box" style="font-weight: 600; font-size: 1.1rem; margin-top: 1.5rem; margin-bottom: 0.8rem;">{ICON_CLOCK} 历史对话</div>', unsafe_allow_html=True)
    if not st.session_state.history:
        st.caption("暂无历史记录")
    else:
        # 显示最近的 15 条历史
        for i, hist in enumerate(st.session_state.history[:15]):
            if st.button(f"{hist['title']}", key=f"hist_{i}", use_container_width=True):
                st.session_state.messages = hist["messages"].copy()
                st.rerun()

    st.divider()

    # # 3. 系统配置 (带图标标题)
    # st.markdown(f'<div class="icon-box" style="font-weight: 600; margin-bottom: 0.5rem;">{ICON_SETTINGS} 系统配置</div>', unsafe_allow_html=True)
    # with st.expander("详情", expanded=True):
    #     st.markdown(f"**推理引擎**: GLM-4.7")

    # 4. 核心组件状态 (带图标标题)
    st.markdown(f'<div class="icon-box" style="font-weight: 600; margin-top: 1rem; margin-bottom: 0.5rem;">{ICON_SETTINGS2} 核心组件状态</div>', unsafe_allow_html=True)
    with st.expander("详情", expanded=False):
        if st.session_state.agent_initialized and st.session_state.agent_conversation:
            conv = st.session_state.agent_conversation
            if hasattr(conv, 'traditional_rag') and conv.traditional_rag:
                st.success("✅ Milvus 向量库: 已连接")
            else:
                st.warning("⚠️ Milvus 向量库: 未连接")
                
            if hasattr(conv, 'graph_rag') and conv.graph_rag:
                st.success("✅ Neo4j 图谱库: 已连接")
            else:
                st.warning("⚠️ Neo4j 图谱库: 未连接")
        else:
            st.info("尚未初始化系统")

        if st.button(" 初始化系统", use_container_width=True):
            # 强制清除所有状态，确保触发重新建立连接
            for k in ['agent_initialized', 'agent_conversation', 'current_agent_state']:
                if k in st.session_state:
                    del st.session_state[k]
            st.rerun()

        if st.button(" 清空所有记录", use_container_width=True):
            st.session_state.messages = []
            st.session_state.history = []
            st.rerun()

# 自动初始化流程 (包含 spinner 确保用户感知)
if not st.session_state.agent_initialized:
    with st.spinner(" 正在加载知识模型与建立数据库连接，请稍候..."):
        try:
            # 释放可能残留的旧连接（使用 get 安全访问）
            if st.session_state.get('agent_conversation'):
                del st.session_state['agent_conversation']
            st.session_state.agent_conversation = MultiTurnConversation()
            st.session_state.agent_initialized = True
            st.toast("✅ 系统准备就绪")
            time.sleep(0.5) # 给用户看一眼提示的时间
            st.rerun()
        except Exception as e:
            st.error(f"❌ 系统初始化严重失败: {e}")
            st.code(traceback.format_exc())

# 页面标题 (仅在无对话时显示，以节省空间)
if not st.session_state.messages:
    st.markdown("<h1 style='text-align: center; color: #FF8C00; margin-top: -10px; margin-bottom: 0px; text-shadow: 0 0 15px rgba(255,140,0,0.3);'> FlowBD 铁铬液流电池科研智能平台</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: rgba(255,255,255,0.6); font-size: 1.0em; margin-top: -10px;'>铁铬液流电池科研知识库</p>", unsafe_allow_html=True)

# 历史消息渲染
for message in st.session_state.messages:
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
            col_l, col_r = st.columns([1, 1])
            with col_l:
                st.markdown("### 回答", unsafe_allow_html=True)
                
                # 优先显示 RAG 思考过程
                rag_reasoning = message.get("reasoning")
                if rag_reasoning:
                    with st.expander("深度思考过程", expanded=False):
                        st.markdown(f'<div style="color: #CCCCCC; font-style: italic; line-height: 1.6;">{rag_reasoning}</div>', unsafe_allow_html=True)
                st.markdown(format_markdown(message["content"]))
                if "logs" in message:
                    with st.expander(" 完整处理链路日志", expanded=False):
                        st.code("\n".join(message["logs"]), language="text")
            with col_r:
                # 渲染历史记录中的第一性原理部分 (移动至右侧并固定大小)
                fp_answer = message.get("fp_answer")
                fp_reasoning = message.get("fp_reasoning")
                
                if fp_answer or fp_reasoning:
                    st.markdown("### <img src='https://img.icons8.com/isometric/50/idea.png' width='24' style='vertical-align: middle; margin-right: 8px;'/> 第一性原理分析", unsafe_allow_html=True)
                    st.caption("基于 GLM-4 的深度学科解剖")
                    
                    # 简化渲染：合并思考和答案，放入固定高度容器
                    fp_merged_html = '<div class="fp-scroll-container">'
                    if fp_reasoning:
                        # 历史记录默认折叠
                        fp_merged_html += f'<details><summary style="color: #FF8C00; font-weight: bold; margin-bottom: 10px; cursor: pointer; outline: none;"> 深度思考过程 (已完成)</summary><div style="color: #CCCCCC; font-style: italic; margin-bottom: 20px; font-size: 0.95rem; padding-left: 10px; border-left: 2px solid rgba(255, 140, 0, 0.2);">{format_markdown(fp_reasoning)}</div></details>'
                    if fp_answer:
                        fp_merged_html += f'<div style="color: #FFFFFF;">{format_markdown(fp_answer)}</div>'
                    fp_merged_html += '</div>'
                    st.markdown(fp_merged_html, unsafe_allow_html=True)
                    
                st.markdown("###  本体（Ontology）")
                if "graph" in message and message["graph"]:
                    # 显示 JSON 数据
                    with st.expander(" 提取的 JSON 数据", expanded=False):
                        st.json(message["graph"])
                    # 动态计算图谱高度
                    calc_height = max(850, len(message["content"]) * 0.8) # 估算因子
                    nodes, edges, config = prepare_graph_visualization(message["graph"]["nodes"], message["graph"]["edges"], height=calc_height)
                    agraph(nodes=nodes, edges=edges, config=config)
                else:
                    st.info("该回答未生成可视化图谱")

# 聊天输入
if prompt := st.chat_input("示例问题：如何抑制铁铬电池的析氢反应？"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.session_state.streaming_answer = ""
    st.session_state.streaming_reasoning = "" # 【重置】
    st.session_state.streaming_complete = False
    st.session_state.current_agent_state = None
    st.rerun()

# 处理待处理的提问
if st.session_state.messages and st.session_state.messages[-1]["role"] == "user" and not st.session_state.streaming_complete:
    last_user_msg = st.session_state.messages[-1]["content"]
    
    with st.chat_message("assistant", avatar=ASSISTANT_AVATAR_SVG):
        col_1, col_2 = st.columns([1, 1])
        with col_1:
            st.markdown("### 回答", unsafe_allow_html=True)
            
            # 思考过程占位符
            think_placeholder = st.empty()
            ans_placeholder = st.empty()
            
            # 状态与日志占位符 (封装在可折叠面板中 - 默认展开)
            st.divider()
            with st.expander("详细执行过程", expanded=True):
                prog_placeholder = st.empty()
                log_placeholder = st.empty()
        
        with col_2:
            # 第一性原理标题 (Static)
            st.markdown("### <img src='https://img.icons8.com/isometric/50/idea.png' width='24' style='vertical-align: middle; margin-right: 8px;'/> 第一性原理分析", unsafe_allow_html=True)
            st.caption("基于 GLM-4 的深度学科解剖")
            
            # 简化占位符
            fp_placeholder = st.empty()
            
            
            st.markdown("###  本体（Ontology）")
            graph_placeholder = st.empty()
            graph_placeholder.info("等待 Agent 识别知识实体...")

        # 启动后台处理逻辑
        def run_backend():
            tid = threading.get_ident()
            try:
                # 显式注入 context 至子线程
                for state in st.session_state.agent_conversation.run_conversation(last_user_msg):
                    st.session_state.current_agent_state = state
                    # 【核心同步】注册状态对象
                    THREAD_STATES[tid] = state
                st.session_state.streaming_complete = True
            except Exception as e:
                # 在后台线程记录异常
                st.session_state._error = str(e)
                st.session_state.streaming_complete = True
            finally:
                # 【核心同步】清理状态
                if tid in THREAD_STATES:
                    del THREAD_STATES[tid]

        back_thread = threading.Thread(target=run_backend)
        add_script_run_ctx(back_thread)
        back_thread.start()

        # 主线程实时监听与渲染
        last_log_size = 0
        graph_rendered = False
        
        # 自动滚动占位符
        scroller = st.empty()
        
        while not st.session_state.streaming_complete:
            state = st.session_state.get('current_agent_state')
            
            # 1. 第一性原理回答 (Line 2)
            if state:
                fp_reasoning = getattr(state, 'fp_reasoning', '')
                fp_answer = getattr(state, 'first_principles_answer', '')
                
                if fp_reasoning or fp_answer:
                    # 简化渲染：拼接 HTML，放入固定高度容器
                    fp_html = '<div class="fp-scroll-container">'
                    if fp_reasoning:
                        # 核心转换逻辑：当 fp_answer 开始有内容时，自动收起 details (移除了 open 属性)
                        # 同时为了让用户能“控制”，只有在 fp_answer 为空且没有手动折叠时才强制 open
                        # 这里简化处理：只要正式回答没开始，我们就保持 open 状态
                        is_open = 'open' if not fp_answer else ''
                        fp_html += f'<details {is_open}><summary style="color: #FF8C00; font-weight: bold; margin-bottom: 10px; cursor: pointer; outline: none;"> {"深度思考 (正在进行)" if not fp_answer else "深度思考过程 (已完成)"}</summary><div style="color: #CCCCCC; font-style: italic; margin-bottom: 20px; font-size: 0.95rem; padding-left: 10px; border-left: 2px solid rgba(255, 140, 0, 0.2);">{format_markdown(fp_reasoning)}</div></details>'
                    if fp_answer:
                        fp_html += f'<div style="color: #FFFFFF;">{format_markdown(fp_answer)}</div>'
                    fp_html += '</div>'
                    fp_placeholder.markdown(fp_html, unsafe_allow_html=True)
            
            # 2. RAG 深度思考与回答 (Line 1)
            # 优先从新的 state.answer_reasoning 读取，回退到 llm_reasoning 或 session_state
            reasoning_txt = getattr(state, 'answer_reasoning', '') if state else ''
            if not reasoning_txt:
                reasoning_txt = getattr(state, 'llm_reasoning', '') if state else ''
            if not reasoning_txt:
                reasoning_txt = st.session_state.streaming_reasoning
            
            current_ans = state.final_answer if state else st.session_state.streaming_answer

            # 【核心修复】防止 RAG 回答部分重复显示第一性原理的内容
            if current_ans and fp_answer and len(fp_answer) > 50:
                if fp_answer[:50].strip() in current_ans:
                     current_ans = current_ans.replace(fp_answer, "").strip()
            
            if reasoning_txt:
                if not current_ans.strip():
                    with think_placeholder.expander("深度思考过程", expanded=True):
                        st.markdown(f'<div style="color: #CCCCCC; font-style: italic; line-height: 1.6;">{reasoning_txt}</div>', unsafe_allow_html=True)
                else:
                    with think_placeholder.expander("深度思考过程", expanded=False):
                        st.markdown(f'<div style="color: #CCCCCC; font-style: italic; line-height: 1.6;">{reasoning_txt}</div>', unsafe_allow_html=True)

            if current_ans:
                ans_placeholder.markdown(format_markdown(current_ans))

            
            # 3. 进度与日志显示
            if state:
                with prog_placeholder.container():
                    render_stage_progress_metrics(state)
                if len(state.agent_logs) > last_log_size:
                    log_placeholder.code("\n".join(state.agent_logs), language="text")
                    last_log_size = len(state.agent_logs)
            
            # 4. 图谱触发 (Line 1 结束后立即展示，不等待 Line 2)
            if state and state.stage_4_complete and not graph_rendered:
                try:
                    final_ans = state.final_answer
                    if final_ans and len(final_ans) > 20:
                        with graph_placeholder.container():
                            nodes_data, edges_data = generate_graph_data(final_ans)
                            if nodes_data and edges_data:
                                with st.expander(" 提取的 JSON 数据", expanded=False):
                                    st.json({"nodes": nodes_data, "edges": edges_data})
                                nodes, edges, config = prepare_graph_visualization(nodes_data, edges_data)
                                agraph(nodes=nodes, edges=edges, config=config)
                                graph_rendered = True
                except Exception as e:
                    graph_placeholder.error(f"图谱生成异常: {e}")
                    graph_rendered = True
            
            # 移除手动滚动脚本，防止干扰 Streamlit 原生布局
            
            time.sleep(0.1)

        # 最终校准与保存
        final_state = st.session_state.current_agent_state
        if final_state:
            # 强化：如果最终也没答出来，确保有一个空状态回退
            final_ans = final_state.final_answer or st.session_state.streaming_answer or "抱歉，系统处理逻辑中断，未能生成有效答案。"
            
            # 解析最终状态以便持久化
            final_fp_answer = getattr(final_state, 'first_principles_answer', '')
            final_fp_reasoning = getattr(final_state, 'fp_reasoning', '')
            
            # 获取 RAG 思考过程
            final_rag_reasoning = getattr(final_state, 'answer_reasoning', '')
            if not final_rag_reasoning:
                final_rag_reasoning = getattr(final_state, 'llm_reasoning', '')
            if not final_rag_reasoning:
                final_rag_reasoning = st.session_state.streaming_reasoning

            # 【重要】最后一次手动渲染所有组件容器，防止 rerun 前白屏
            # 最终渲染：简化合并
            if final_fp_reasoning or final_fp_answer:
                fp_html = '<div class="fp-scroll-container">'
                if final_fp_reasoning:
                    # 最终结果通常是已完成状态，默认折叠
                    fp_html += f'<details><summary style="color: #FF8C00; font-weight: bold; margin-bottom: 10px; cursor: pointer; outline: none;"> 深度思考过程:</summary><div style="color: #CCCCCC; font-style: italic; margin-bottom: 20px; font-size: 0.95rem; padding-left: 10px; border-left: 2px solid rgba(255, 140, 0, 0.2);">{format_markdown(final_fp_reasoning)}</div></details>'
                if final_fp_answer:
                    fp_html += f'<div style="color: #FFFFFF;">{format_markdown(final_fp_answer)}</div>'
                fp_html += '</div>'
                fp_placeholder.markdown(fp_html, unsafe_allow_html=True)

            if final_rag_reasoning:
                with think_placeholder.expander("深度思考过程", expanded=False):
                    st.markdown(f'<div style="color: #CCCCCC; font-style: italic; line-height: 1.6;">{final_rag_reasoning}</div>', unsafe_allow_html=True)
            
            ans_placeholder.markdown(format_markdown(final_ans))
            
            # 遵循 app.py 的图谱提取时机
            graph_save = None
            try:
                nodes_data, edges_data = generate_graph_data(final_ans)
                if nodes_data and edges_data:
                    with graph_placeholder.container():
                        with st.expander(" 提取的 JSON 数据", expanded=False):
                            st.json({"nodes": nodes_data, "edges": edges_data})
                        calc_height = max(850, len(final_ans) * 0.8)
                        nodes, edges, config = prepare_graph_visualization(nodes_data, edges_data, height=calc_height)
                        agraph(nodes=nodes, edges=edges, config=config)
                    graph_save = {"nodes": nodes_data, "edges": edges_data}
                else:
                    graph_placeholder.info("回答中未提取到足够的实体关系，无法生成图谱。")
            except Exception as e:
                graph_placeholder.error(f"图谱渲染异常: {e}")

            # 持久化到会话历史
            st.session_state.messages.append({
                "role": "assistant",
                "content": final_ans,
                "reasoning": final_rag_reasoning,
                "fp_answer": final_fp_answer,     
                "fp_reasoning": final_fp_reasoning, 
                "logs": final_state.agent_logs,
                "graph": graph_save
            })
            st.session_state.streaming_complete = True
            st.rerun()

# [Hotfix] 强制注入 JS 修复图谱背景白屏问题
def inject_graph_style_fix():
    js_code = """
    <script>
    const observerCallback = function(mutationsList, observer) {
        // 1. 自动滚动逻辑
        window.requestAnimationFrame(() => {
            const fpContainers = parent.document.querySelectorAll('.fp-scroll-container');
            fpContainers.forEach(function(el) {
                const threshold = 100;
                const isAtBottom = el.scrollHeight - el.scrollTop - el.clientHeight < threshold;
                if (isAtBottom) {
                    el.scrollTop = el.scrollHeight;
                }
            });
        });

        // 2. 侧边栏状态监测与全局 CSS 类注入
        const sidebar = parent.document.querySelector('[data-testid="stSidebar"]');
        if (sidebar) {
            const isCollapsed = sidebar.getAttribute('data-collapsed') === 'true';
            // 同步注入到当前 document 和 parent.document 的 body
            const targetBodies = [document.body, parent.document.body];
            targetBodies.forEach(b => {
                if (isCollapsed) b.classList.add('sidebar-collapsed');
                else b.classList.remove('sidebar-collapsed');
            });
        }
    };

    const observer = new MutationObserver(observerCallback);
    
    function startObserving() {
        // 观察整个文档，因为 Streamlit 会动态创建和销毁元素
        observer.observe(parent.document.body, { attributes: false, childList: true, subtree: true, characterData: true });
        
        // 初始图谱修复
        const iframes = parent.document.querySelectorAll('iframe[title="streamlit_agraph.agraph"]');
        iframes.forEach(function(iframe) {
            iframe.style.backgroundColor = '#0A0A0B';
            try {
                if (iframe.contentDocument && iframe.contentDocument.body) {
                   iframe.contentDocument.body.style.backgroundColor = '#0A0A0B';
                   iframe.contentDocument.documentElement.style.backgroundColor = '#0A0A0B';
                }
            } catch(e) {}
        });
    }

    // 每一秒检查一次确保观察器在运行（应对页面刷新/Rerun）
    startObserving();
    setInterval(startObserving, 1000);
    </script>
    """
    components.html(js_code, height=0, width=0)

# 执行注入
inject_graph_style_fix()
