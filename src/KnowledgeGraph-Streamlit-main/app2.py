import streamlit as st
import json
import sys
import os

# 【核心修复】解决程序崩溃 (forrtl: error (200)/OMP: Error #15)
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

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

def patched_handle_streaming_response(self, response) -> str:
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
                    
                    # 1. 模式转换判定
                    if content or "[Ref-" in reasoning or ("第" in reasoning and "段" in reasoning):
                        if not is_answer_mode:
                            is_answer_mode = True
                            # 【核心修复】一旦切入回答模式，如果思考还没结束，立即在终端打印结束标识
                            if reasoning_started:
                                print(THINK_END, end='', flush=True)
                                reasoning_started = False
                    
                    # 2. 推理流处理
                    if reasoning:
                        if is_answer_mode:
                            # 已切入回答模式，此时的推理内容被视为正文
                            full_answer += reasoning
                            try: st.session_state.streaming_answer += reasoning
                            except: pass
                        else:
                            # 真正的深度思考
                            if not reasoning_started:
                                print(THINK_START, end='', flush=True)
                                reasoning_started = True
                            full_reasoning += reasoning
                            try: st.session_state.streaming_reasoning += reasoning
                            except: pass
                        print(reasoning, end='', flush=True)
                        continue
                    
                    # 3. 正式回答流处理
                    if content:
                        # (is_answer_mode 和 THINK_END 已在上面预处理)
                        full_answer += content
                        try: st.session_state.streaming_answer += content
                        except: pass
                        print(content, end='', flush=True)
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
    for mod_name, module in list(sys.modules.items()):
        if 'part1_knowledge_arsenal' in mod_name:
            if hasattr(module, 'LLMConfig'):
                cls_obj = getattr(module, 'LLMConfig')
                for m_name, m_func in target_methods.items():
                    setattr(cls_obj, m_name, m_func)
                    count += 1
    LLMConfig._handle_streaming_response = patched_handle_streaming_response
    print(f"🚀 [系统] 终端打印对齐补丁已生效 (覆盖 {count+1} 处)")

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
        model="moonshot-v1-32k"
    )
    # 调用 Kimi 进行极速图谱提取
    return llm.call_llm(user_msg, system_prompt=system_msg, temperature=0.0)

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
def format_markdown(text):
    if not text: return text
    return text.replace('\n', '  \n')

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
st.set_page_config(page_title="FlowBD AI - 专家对话系统", layout="wide", initial_sidebar_state="auto")

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

    /* 9. 彻底消除页眉与输入框白色残留 */
    header[data-testid="stHeader"] {{
        background-color: transparent !important;
    }}

    /* 强制去除底部输入容器的所有背景和边框 */
    /* 12. 底部固定栏终极修复：容器本身必须实心 */
    div[data-testid="stBottom"] {{
        background-color: #0A0A0B !important; 
        border-top: none !important; /* 去掉顶部边框 */
        z-index: 1000000 !important;
    }}

    /* 内部容器透明，避免双重背景 */
    div[data-testid="stBottom"] > div {{
        background-color: transparent !important;
        border: none !important;
    }}
    
    /* 防止内容被底部固定栏遮挡 - 进一步加大留白 */
    .main .block-container {{
        padding-bottom: 250px !important; 
    }}

    /* 深度修复：消除输入框“套娃”白底并强制文字显色 */
    div[data-testid="stChatInput"] {{
        background-color: #141416 !important;
        border: 1px solid #FF8C00 !important;
        border-radius: 12px !important;
        padding: 0px !important; 
        box-shadow: none !important;
        overflow: hidden !important;
    }}
    
    /* 终极去边框：针对内部所有容器、baseweb以及带有边框的嵌套元素 */
    div[data-testid="stChatInput"] * {{
        border: none !important;
        box-shadow: none !important;
        background-color: transparent !important;
        outline: none !important;
    }}

    /* 暴力确保文字颜色和光标颜色 */
    div[data-testid="stChatInput"] textarea {{
        background-color: transparent !important;
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
        caret-color: #FF8C00 !important;
        padding: 15px !important;
        width: 100% !important;
    }}

    /* 针对输入文字的特殊覆盖 */
    div[data-testid="stChatInput"] textarea {{
        -webkit-text-fill-color: #FFFFFF !important;
        padding: 15px !important; /* 给打字区域一点内部呼吸空间 */
    }}

    /* 发送按钮颜色适配 */
    div[data-testid="stChatInput"] button svg {{
        fill: #FF8C00 !important;
    }}

    /* 修复底部输入框容器 */
    [data-testid="stBottom"] > div {{
        background-color: transparent !important;
    }}

    /* 确保主内容区域无白底 */
    .main .block-container {{
        background-color: transparent !important;
    }}

    /* 10. 全局文字可读性补丁 */
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

# 页面标题
st.markdown("<h1 style='text-align: center; color: #FF8C00; margin-top: -30px; text-shadow: 0 0 15px rgba(255,140,0,0.3);'> FlowBD 铁铬液流电池科研智能平台</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: rgba(255,255,255,0.6); font-size: 1.1em;'>铁铬液流电池科研知识库</p>", unsafe_allow_html=True)

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
                st.markdown("###  回答")
                # 渲染历史记录中的思考过程
                if message.get("reasoning"):
                    #st.markdown(f'<div class="icon-box" style="margin-bottom: -10px;">{ICON_BRAIN} 深度思考过程</div>', unsafe_allow_html=True)
                    with st.expander("点击查看内容", expanded=False):
                        st.markdown(f'<div style="color: #CCCCCC; font-style: italic; line-height: 1.6;">{message["reasoning"]}</div>', unsafe_allow_html=True)
                st.markdown(format_markdown(message["content"]))
                if "logs" in message:
                    with st.expander(" 完整处理链路日志", expanded=False):
                        st.code("\n".join(message["logs"]), language="text")
            with col_r:
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
            st.markdown("###  回答")
            
            # 思考过程占位符
            think_placeholder = st.empty()
            ans_placeholder = st.empty()
            
            # 状态与日志占位符 (独立于思考框)
            # 状态与日志占位符 (封装在可折叠面板中)
            st.divider()
            with st.expander("详细执行过程", expanded=True):
                prog_placeholder = st.empty()
                log_placeholder = st.empty()
        
        with col_2:
            st.markdown("###  本体（Ontology）")
            graph_placeholder = st.empty()
            graph_placeholder.info("等待 Agent 识别知识实体...")

        # 启动后台处理逻辑
        def run_backend():
            try:
                # 显式注入 context 至子线程
                for state in st.session_state.agent_conversation.run_conversation(last_user_msg):
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
        last_log_size = 0
        while not st.session_state.streaming_complete:
            state = st.session_state.get('current_agent_state')
            
            # 1. 深度思考显示 (折叠面板模式)
            reasoning_txt = st.session_state.streaming_reasoning
            # 优先从 state 中获取，因为 state.final_answer 包含了后端处理后的 [Ref] 来源列表
            current_ans = st.session_state.streaming_answer
            
            # 如果后端 Stage 4 已经跑完，state.final_answer 会包含完整的【文献来源】列表
            if state and state.stage_4_complete and hasattr(state, 'final_answer') and state.final_answer:
                 # 当后端处理完最终答案（含参考文献表格）时，切换到最终答案展示
                 current_ans = state.final_answer
            
            # 1. 深度思考显示 (折叠面板模式 - 纯文本标题，无图标)
            if reasoning_txt:
                if not bool(st.session_state.streaming_answer.strip()):
                    with think_placeholder.expander("深度思考过程", expanded=True):
                        st.markdown(f'<div style="color: #CCCCCC; font-style: italic; line-height: 1.6;">{reasoning_txt}</div>', unsafe_allow_html=True)
                else:
                    with think_placeholder.expander("深度思考过程"):
                        st.markdown(f'<div style="color: #CCCCCC; font-style: italic; line-height: 1.6;">{reasoning_txt}</div>', unsafe_allow_html=True)
            else:
                think_placeholder.empty()
            
            # 2. 正式回答显示
            if current_ans:
                ans_placeholder.markdown(format_markdown(current_ans))
            
            # 2. 进度与日志显示 (修正缩进，确保实时更新)
            if state:
                with prog_placeholder.container():
                    render_stage_progress_metrics(state)
                if len(state.agent_logs) > last_log_size:
                    log_placeholder.code("\n".join(state.agent_logs), language="text")
                    last_log_size = len(state.agent_logs)
            
            time.sleep(0.1)

        # 最终校准与保存
        final_state = st.session_state.current_agent_state
        if final_state:
            # 强化：如果最终也没答出来，确保有一个空状态回退
            final_ans = final_state.final_answer or st.session_state.streaming_answer or "抱歉，系统处理逻辑中断，未能生成有效答案。"
            ans_placeholder.markdown(format_markdown(final_ans))
            
            # 遵循 app.py 的图谱提取时机
            graph_save = None
            try:
                nodes_data, edges_data = generate_graph_data(final_ans)
                if nodes_data and edges_data:
                    with graph_placeholder.container():
                        # 显示 JSON 数据
                        with st.expander(" 提取的 JSON 数据", expanded=False):
                            st.json({"nodes": nodes_data, "edges": edges_data})
                        # 动态计算图谱高度
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
                "reasoning": final_state.llm_reasoning or st.session_state.streaming_reasoning,
                "logs": final_state.agent_logs,
                "graph": graph_save
            })
            st.session_state.streaming_complete = True
            st.rerun()

# [Hotfix] 强制注入 JS 修复图谱背景白屏问题
def inject_graph_style_fix():
    js_code = """
    <script>
    function fixGraphBackground() {
        // 1. 查找所有 streamlit-agraph 的 iframe
        const iframes = parent.document.querySelectorAll('iframe[title="streamlit_agraph.agraph"]');
        
        iframes.forEach(function(iframe) {
            // 强制设置 iframe 容器背景
            iframe.style.backgroundColor = '#0A0A0B';
            
            // 尝试修改 iframe 内部 body 背景 (仅在同源下生效，Streamlit组件通常同源)
            try {
                if (iframe.contentDocument && iframe.contentDocument.body) {
                   iframe.contentDocument.body.style.backgroundColor = '#0A0A0B';
                   // 同时也设置 html 节点，防止 body 高度不够
                   iframe.contentDocument.documentElement.style.backgroundColor = '#0A0A0B';
                }
            } catch(e) {
                // 跨域限制忽略
            }
        });
    }

    // 立即执行并持续监控（适配动态加载）
    fixGraphBackground();
    setInterval(fixGraphBackground, 500);
    </script>
    """
    components.html(js_code, height=0, width=0)

# 执行注入
inject_graph_style_fix()
