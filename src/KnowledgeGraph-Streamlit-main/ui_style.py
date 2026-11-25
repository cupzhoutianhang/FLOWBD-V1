# -*- coding: utf-8 -*-
"""
ui_style.py — FlowBD 全局 UI 样式模块（唯一样式来源）

设计稿: ui-demo/index.html（2026-09-03 定稿）
色板全部走 CSS 变量，组件内禁止散落硬编码色值。
"""

import streamlit as st

import math

# demo 色板
PALETTE = {
    "bg": "#f6f5f2",
    "surface": "#ffffff",
    "surface_2": "#faf9f6",
    "ink": "#1c1917",
    "ink_2": "#57534e",
    "ink_3": "#a8a29e",
    "line": "#e8e5df",
    "line_2": "#f0eee8",
    "teal": "#0f766e",
    "teal_dark": "#115e59",
    "teal_soft": "#e7f3f1",
    "amber": "#b45309",
    "amber_soft": "#fbf1e2",
    "rose": "#be3455",
    "rose_soft": "#fbeaee",
    "green": "#16a34a",
}


def inject_global_css(svg_msg_plus: str = "") -> None:
    """注入全局 CSS（浅色暖纸主题）。svg_msg_plus 用于侧栏"新建对话"按钮图标。"""
    p = PALETTE
    st.markdown(f"""
<style>
    /* ===== FlowBD 全局皮肤 · 浅色暖纸主题（对齐 ui-demo） ===== */
    :root {{
        --fb-bg: {p["bg"]}; --fb-surface: {p["surface"]}; --fb-surface-2: {p["surface_2"]};
        --fb-ink: {p["ink"]}; --fb-ink-2: {p["ink_2"]}; --fb-ink-3: {p["ink_3"]};
        --fb-line: {p["line"]}; --fb-line-2: {p["line_2"]};
        --fb-teal: {p["teal"]}; --fb-teal-dark: {p["teal_dark"]}; --fb-teal-soft: {p["teal_soft"]};
        --fb-amber: {p["amber"]}; --fb-amber-soft: {p["amber_soft"]};
        --fb-rose: {p["rose"]}; --fb-rose-soft: {p["rose_soft"]};
        --fb-green: {p["green"]};
    }}

    html, body, .stApp {{
        font-family: "Inter", -apple-system, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif !important;
    }}
    .stApp {{
        background-color: var(--fb-bg) !important;
        background-image: none !important;
        color: var(--fb-ink);
    }}

    /* 侧栏 */
    [data-testid="stSidebar"] {{
        background-color: var(--fb-surface) !important;
        border-right: 1px solid var(--fb-line);
    }}
    [data-testid="stSidebar"] .stMarkdown p {{
        color: var(--fb-ink-2);
    }}

    /* 品牌标题（沿用 .brand-title 钩子） */
    .brand-title {{
        font-size: 17px !important;
        font-weight: 650 !important;
        letter-spacing: 0 !important;
        color: var(--fb-teal-dark) !important;
        margin-bottom: 14px !important;
        text-shadow: none !important;
    }}

    /* 按钮：白底墨字细边，hover 青边 */
    div.stButton > button {{
        background-color: var(--fb-surface) !important;
        color: var(--fb-ink-2) !important;
        border: 1px solid var(--fb-line) !important;
        border-radius: 7px !important;
        font-weight: 500 !important;
        box-shadow: none !important;
        transition: border-color .15s, background .15s !important;
    }}
    div.stButton > button:hover {{
        border-color: var(--fb-teal) !important;
        color: var(--fb-teal-dark) !important;
        background-color: var(--fb-teal-soft) !important;
        transform: none !important;
    }}

    /* 侧栏 primary 按钮（新建对话）：实心青 */
    [data-testid="stSidebar"] button[data-testid="stBaseButton-primary"] {{
        background-color: var(--fb-teal) !important;
        color: #fff !important;
        border: 1px solid var(--fb-teal) !important;
    }}
    [data-testid="stSidebar"] button[data-testid="stBaseButton-primary"]:hover {{
        background-color: var(--fb-teal-dark) !important;
        color: #fff !important;
    }}
    [data-testid="stSidebar"] button[data-testid="stBaseButton-primary"] p::before {{
        content: "" !important;
        display: inline-block !important;
        width: 15px !important;
        height: 15px !important;
        margin-right: 7px !important;
        background-color: currentColor !important;
        vertical-align: middle !important;
        -webkit-mask: url("{svg_msg_plus}") no-repeat center !important;
        mask: url("{svg_msg_plus}") no-repeat center !important;
        mask-size: contain !important;
    }}

    /* 图标行（沿用 .icon-box 钩子） */
    .icon-box {{
        display: flex !important;
        align-items: center !important;
        gap: 8px !important;
        color: var(--fb-ink-2) !important;
    }}
    .icon-box svg {{
        stroke: var(--fb-teal) !important;
    }}

    /* 正文 Markdown */
    .stMarkdown p, .stMarkdown li {{
        color: var(--fb-ink) !important;
        line-height: 1.65 !important;
    }}
    .stMarkdown h3 {{
        color: var(--fb-ink) !important;
        font-size: 1.1rem !important;
        margin-top: 18px !important;
        margin-bottom: 12px !important;
    }}

    /* Expander：白卡细边 */
    div[data-testid="stExpander"],
    div[data-testid="stExpander"] details,
    div[data-testid="stExpander"] summary {{
        background-color: var(--fb-surface) !important;
        border: none !important;
        border-radius: 8px !important;
    }}
    div[data-testid="stExpander"] {{
        border: 1px solid var(--fb-line) !important;
    }}
    div[data-testid="stExpander"] details + div,
    div[data-testid="stExpander"] div[role="region"] {{
        background-color: var(--fb-surface) !important;
    }}

    /* 对话气泡：白卡细边小圆角 */
    div[data-testid="stChatMessage"] {{
        background-color: var(--fb-surface) !important;
        border: 1px solid var(--fb-line) !important;
        border-radius: 8px !important;
        padding: 14px 16px !important;
        margin-bottom: 10px !important;
    }}

    /* 代码块 / JSON：浅底墨字 */
    pre, code, .stCodeBlock, .stJson,
    div[data-testid="stCodeBlock"],
    div[data-testid="stJson"],
    div[data-testid="stCodeBlock"] pre,
    div[data-testid="stJson"] div {{
        background-color: var(--fb-surface-2) !important;
        background: var(--fb-surface-2) !important;
        color: var(--fb-ink) !important;
    }}
    div[data-testid="stJson"] span {{
        color: var(--fb-teal-dark) !important;
    }}
    div[data-testid="stJson"] span[class*="string"] {{
        color: #3f6212 !important;
    }}
    div[data-testid="stJson"] span[class*="number"] {{
        color: var(--fb-amber) !important;
    }}

    iframe {{
        background-color: var(--fb-surface) !important;
    }}
    header[data-testid="stHeader"] {{
        background-color: transparent !important;
    }}

    /* 成功/警告/提示框：浅色化 */
    div[data-testid="stAlert"] {{
        border-radius: 8px !important;
    }}

    /* ===== FlowBD 自有组件 ===== */
    /* 顶栏品牌区 */
    .fb-topbar {{
        position: fixed; top: 0; left: 0; right: 0; z-index: 999999;
        height: 52px; box-sizing: border-box;
        display: flex; align-items: center; gap: 10px;
        padding: 0 16px;
        background: var(--fb-surface);
        border-bottom: 1px solid var(--fb-line);
        margin-bottom: 0;
    }}
    .fb-brand-mark {{
        width: 28px; height: 28px; border-radius: 7px;
        background: var(--fb-teal); color: #fff;
        font-weight: 700; font-size: 13px;
        display: inline-flex; align-items: center; justify-content: center;
    }}
    .fb-brand-name {{ font-weight: 650; font-size: 15px; color: var(--fb-ink); }}
    .fb-brand-sub {{ font-size: 12px; color: var(--fb-ink-3); }}
    .fb-pills {{ margin-left: auto; display: flex; gap: 8px; flex-wrap: wrap; }}

    /* 状态胶囊 */
    .fb-pill {{
        display: inline-flex; align-items: center; gap: 6px;
        height: 24px; padding: 0 10px;
        border: 1px solid var(--fb-line);
        border-radius: 999px;
        background: var(--fb-surface-2);
        font-size: 12px; color: var(--fb-ink-2);
        white-space: nowrap;
    }}
    .fb-dot {{
        width: 7px; height: 7px; border-radius: 50%;
        background: var(--fb-green); flex: none;
        display: inline-block;
    }}
    .fb-dot.warn {{ background: var(--fb-amber); }}
    .fb-dot.down {{ background: var(--fb-rose); }}

    /* 引用 chip（阶段 2 会用到，先定义） */
    .fb-cite {{
        display: inline-flex; align-items: center; justify-content: center;
        min-width: 17px; height: 17px; padding: 0 4px;
        border-radius: 4px;
        background: var(--fb-amber-soft); color: var(--fb-amber);
        font-size: 11px; font-weight: 650;
        font-family: "JetBrains Mono", Consolas, monospace;
        vertical-align: 2px; margin: 0 1px;
    }}
    /* 流水线阶段条（demo 同款 chip） */
    .fb-pipe {{
        display: flex; align-items: center; flex-wrap: wrap; gap: 6px;
        margin: 2px 0 12px;
    }}
    .fb-chip {{
        display: inline-flex; align-items: center; gap: 6px;
        height: 26px; padding: 0 10px;
        border: 1px solid var(--fb-line); border-radius: 999px;
        background: var(--fb-surface);
        font-size: 12px; color: var(--fb-ink-2);
        white-space: nowrap;
    }}
    .fb-chip .fb-chip-ms {{
        font-family: "JetBrains Mono", Consolas, monospace;
        font-size: 11px; color: var(--fb-ink-3);
    }}
    .fb-chip.done {{ border-color: #d3e8e4; background: var(--fb-teal-soft); color: var(--fb-teal-dark); }}
    .fb-chip.done .fb-chip-ms {{ color: var(--fb-teal); }}
    .fb-chip.running {{ border-color: var(--fb-amber); background: var(--fb-amber-soft); color: var(--fb-amber); }}
    .fb-arrow {{ color: var(--fb-ink-3); font-size: 12px; }}
    /* ===== 阶段3: 检视列 · 证据卡（demo src-card 同款） ===== */
    .fb-src-card {{
        border: 1px solid var(--fb-line);
        border-radius: 8px;
        padding: 10px 12px;
        margin-bottom: 10px;
        background: var(--fb-surface);
    }}
    .fb-src-card.cited {{ border-color: var(--fb-amber); background: var(--fb-amber-soft); }}
    .fb-src-head {{ display: flex; align-items: center; gap: 8px; margin-bottom: 5px; }}
    .fb-src-no {{
        font-family: "JetBrains Mono", Consolas, monospace;
        font-size: 11px; font-weight: 700;
        color: var(--fb-amber); background: var(--fb-amber-soft);
        border-radius: 4px; padding: 1px 5px;
    }}
    .fb-src-card.cited .fb-src-no {{ color: #fff; background: var(--fb-amber); }}
    .fb-src-cited-tag {{ font-size: 11px; color: var(--fb-amber); font-weight: 650; }}
    .fb-src-type {{
        font-size: 11px; color: var(--fb-ink-3); margin-left: auto;
        font-family: "JetBrains Mono", Consolas, monospace;
    }}
    .fb-src-title {{ font-size: 13px; font-weight: 600; line-height: 1.45; margin-bottom: 6px; color: var(--fb-ink); }}
    .fb-src-snippet {{
        font-size: 12px; color: var(--fb-ink-2); line-height: 1.55;
        display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
        margin-bottom: 8px;
    }}
    .fb-score-row {{ display: flex; align-items: center; gap: 8px; }}
    .fb-score-label {{ font-size: 11px; color: var(--fb-ink-3); flex: none; }}
    .fb-score-track {{ flex: 1; height: 4px; border-radius: 2px; background: var(--fb-line-2); overflow: hidden; }}
    .fb-score-fill {{ height: 100%; border-radius: 2px; background: var(--fb-teal); }}
    .fb-score-val {{
        font-size: 11px; color: var(--fb-ink-2); flex: none;
        font-family: "JetBrains Mono", Consolas, monospace;
    }}
    .fb-src-more {{ margin-top: 6px; }}
    .fb-src-more summary {{ color: var(--fb-teal-dark); cursor: pointer; font-size: 12px; }}
    .fb-src-more > div {{
        color: var(--fb-ink-2); font-size: 12px; line-height: 1.55;
        margin-top: 6px; white-space: pre-wrap; word-break: break-word;
    }}
    /* ===== 阶段3: 检视列 · 流程明细（demo flow-step 同款） ===== */
    .fb-flow-step {{
        border: 1px solid var(--fb-line);
        border-radius: 8px;
        padding: 10px 12px;
        margin-bottom: 10px;
        background: var(--fb-surface);
    }}
    .fb-flow-head {{ display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }}
    .fb-flow-no {{
        width: 18px; height: 18px; border-radius: 50%; flex: none;
        background: var(--fb-teal-soft); color: var(--fb-teal-dark);
        font-size: 11px; font-weight: 700;
        display: inline-flex; align-items: center; justify-content: center;
    }}
    .fb-flow-step.pending .fb-flow-no {{ background: var(--fb-line-2); color: var(--fb-ink-3); }}
    .fb-flow-step.running .fb-flow-no {{ background: var(--fb-amber-soft); color: var(--fb-amber); }}
    .fb-flow-name {{ font-size: 13px; font-weight: 600; color: var(--fb-ink); }}
    .fb-flow-ms {{
        margin-left: auto; font-size: 11px; color: var(--fb-ink-3);
        font-family: "JetBrains Mono", Consolas, monospace;
    }}
    .fb-flow-kv {{ display: flex; gap: 8px; font-size: 12px; line-height: 1.6; }}
    .fb-flow-k {{ color: var(--fb-ink-3); flex: none; }}
    .fb-flow-v {{ color: var(--fb-ink-2); word-break: break-word; }}
    /* 第一性原理固定高度滚动容器 (Marker 版本，浅色主题) */
    div[data-testid="stVerticalBlock"]:has(> div.element-container:first-child > .stMarkdown .fp-box-marker) {{
        max-height: 420px !important;
        overflow-y: auto !important;
        scroll-behavior: smooth !important;
        padding: 14px 16px !important;
        background-color: var(--fb-surface) !important;
        border: 1px solid var(--fb-line) !important;
        border-radius: 8px !important;
        box-shadow: none !important;
        line-height: 1.65 !important;
        box-sizing: border-box !important;
        margin-bottom: 20px !important;
        scrollbar-width: thin !important;
        scrollbar-color: #d8d4cc var(--fb-surface-2) !important;
    }}
    div[data-testid="stVerticalBlock"]:has(> div.element-container:first-child > .stMarkdown .fp-box-marker)::-webkit-scrollbar {{
        width: 8px;
    }}
    div[data-testid="stVerticalBlock"]:has(> div.element-container:first-child > .stMarkdown .fp-box-marker)::-webkit-scrollbar-track {{
        background: var(--fb-surface-2);
    }}
    div[data-testid="stVerticalBlock"]:has(> div.element-container:first-child > .stMarkdown .fp-box-marker)::-webkit-scrollbar-thumb {{
        background: #d8d4cc;
        border-radius: 4px;
    }}
    div[data-testid="stVerticalBlock"]:has(> div.element-container:first-child > .stMarkdown .fp-box-marker)::-webkit-scrollbar-thumb:hover {{
        background: var(--fb-ink-3);
    }}
    /* 隐藏 marker */
    .fp-box-marker {{
        display: none !important;
    }}
    /* 容器内思考过程 expander 去框 */
    div[data-testid="stVerticalBlock"]:has(> div.element-container:first-child > .stMarkdown .fp-box-marker) div[data-testid="stExpander"] {{
        background-color: transparent !important;
        border: none !important;
        padding: 0 !important;
        margin-top: -10px !important;
    }}
    div[data-testid="stVerticalBlock"]:has(> div.element-container:first-child > .stMarkdown .fp-box-marker) div[data-testid="stExpander"] summary p {{
        color: var(--fb-teal-dark) !important;
        font-weight: 650 !important;
    }}
    div[data-testid="stVerticalBlock"]:has(> div.element-container:first-child > .stMarkdown .fp-box-marker) div[data-testid="stExpander"] details + div {{
        background-color: transparent !important;
        padding: 5px 0 !important;
    }}
    div[data-testid="stVerticalBlock"]:has(> div.element-container:first-child > .stMarkdown .fp-box-marker) .stMarkdown p {{
        color: var(--fb-ink) !important;
        opacity: 1;
    }}
</style>
""", unsafe_allow_html=True)


def status_pill(label: str, ok: bool | None) -> str:
    """单个状态胶囊。ok=True 绿点 / False 红点 / None 灰点(未初始化)。"""
    if ok is True:
        dot, state = "fb-dot", "正常"
    elif ok is False:
        dot, state = "fb-dot down", "异常"
    else:
        dot, state = "fb-dot warn", "未初始化"
    return f'<span class="fb-pill"><span class="{dot}"></span>{label} · {state}</span>'


def render_header(conv=None) -> None:
    """页面顶栏：品牌 + 核心组件真实健康状态胶囊。"""
    if conv is None:
        milvus_ok = neo4j_ok = None
    else:
        milvus_ok = bool(getattr(conv, "traditional_rag", None))
        neo4j_ok = bool(getattr(conv, "graph_rag", None))
    pills = status_pill("Milvus", milvus_ok) + status_pill("Neo4j", neo4j_ok)
    st.markdown(
        f'<div class="fb-topbar">'
        f'<span class="fb-brand-mark">F</span>'
        f'<span class="fb-brand-name">FlowBD-V1</span>'
        f'<span class="fb-brand-sub">储能方法知识问答 · V1</span>'
        f'<span class="fb-pills">{pills}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )


def pipeline_chips(labels, stages, ends, t0) -> str:
    """四阶段流水线 chip 条。

    labels: 4 个阶段名; stages: (bool, ...) 是否完成;
    ends: {阶段号: 完成时间戳}; t0: 流水线起点时间戳。
    每阶段耗时 = 本阶段完成时刻 - 上一阶段完成时刻（首阶段相对 t0）。
    """
    chips = []
    first_open = next((i for i, d in enumerate(stages) if not d), None)
    for i, (label, done) in enumerate(zip(labels, stages), start=1):
        if done:
            prev = ends.get(i - 1, t0) if i > 1 else t0
            ms = max(0, int((ends.get(i, prev) - prev) * 1000))
            chips.append(
                f'<span class="fb-chip done">✓ {label}'
                f'<span class="fb-chip-ms">{ms}ms</span></span>'
            )
        elif first_open is not None and i - 1 == first_open:
            chips.append(f'<span class="fb-chip running">{label}…</span>')
        else:
            chips.append(f'<span class="fb-chip">{label}</span>')
    return '<div class="fb-pipe">' + '<span class="fb-arrow">›</span>'.join(chips) + '</div>'


def _esc(text) -> str:
    """HTML 转义（证据卡/流程面板渲染 LLM 与检索文本前的安全前提）。"""
    return str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def evidence_cards_html(doc_sources, cited_ids=None, max_snippet: int = 160, max_full: int = 1500) -> str:
    """证据卡列表 HTML（demo src-card 同款）。

    doc_sources: 真实 AgentPipelineState.doc_sources
        [{ref_id, type, source, source_label, content, score(rerank)}]
    cited_ids: 正文 [Ref-n] 实际引用到的编号集合 → 卡片琥珀高亮（chip↔卡片编号联动）
    """
    cited = set(cited_ids or [])
    cards = []
    for src in doc_sources or []:
        ref = src.get('ref_id')
        try:
            logit = float(src.get('score', 0) or 0)
        except (TypeError, ValueError):
            logit = 0.0
        # rerank_score 是 BGE reranker 原始 logit（可正可负），sigmoid 归一化到 0~1 展示
        score = 1.0 / (1.0 + math.exp(-logit))
        width = int(round(score * 100))
        title = src.get('source_label') or src.get('source') or 'unknown'
        content = str(src.get('content') or '').strip()
        snippet = content if len(content) <= max_snippet else content[:max_snippet] + '…'
        is_cited = ref in cited
        card_cls = 'fb-src-card cited' if is_cited else 'fb-src-card'
        cited_tag = '<span class="fb-src-cited-tag">正文已引用</span>' if is_cited else ''
        full_html = ''
        if len(content) > max_snippet:
            full_text = content if len(content) <= max_full else content[:max_full] + '…'
            full_html = (
                '<details class="fb-src-more"><summary>查看片段全文</summary>'
                f'<div>{_esc(full_text)}</div></details>'
            )
        cards.append(
            f'<div class="{card_cls}">'
            f'<div class="fb-src-head"><span class="fb-src-no">Ref-{_esc(ref)}</span>{cited_tag}'
            f'<span class="fb-src-type">{_esc(src.get("type", "?"))}</span></div>'
            f'<div class="fb-src-title">{_esc(title)}</div>'
            f'<div class="fb-src-snippet">{_esc(snippet)}</div>'
            f'<div class="fb-score-row"><span class="fb-score-label">rerank</span>'
            f'<div class="fb-score-track"><div class="fb-score-fill" style="width:{width}%"></div></div>'
            f'<span class="fb-score-val">{score:.2f}</span></div>'
            f'{full_html}</div>'
        )
    if not cards:
        return '<div style="color:var(--fb-ink-3);font-size:12px">本次回答未使用文献来源</div>'
    return ''.join(cards)


def flow_steps_html(rows, kv=None) -> str:
    """流程明细 HTML（demo flow-step 同款）。

    rows: [(label, status, ms)]，status ∈ done/running/pending，ms=None 表示无耗时数据
    kv:   [(k, v)] 追加的真实 state 字段（证据来源/融合置信度/文献数等）
    """
    out = []
    for i, (label, status, ms) in enumerate(rows, start=1):
        if ms is not None:
            ms_txt = f'{ms}ms'
        elif status == 'running':
            ms_txt = '…'
        else:
            ms_txt = ''
        out.append(
            f'<div class="fb-flow-step {status}"><div class="fb-flow-head">'
            f'<span class="fb-flow-no">{i}</span>'
            f'<span class="fb-flow-name">{_esc(label)}</span>'
            f'<span class="fb-flow-ms">{ms_txt}</span></div></div>'
        )
    if kv:
        out.append('<div class="fb-flow-step"><div class="fb-flow-head">'
                   '<span class="fb-flow-name">状态字段</span></div>')
        for k, v in kv:
            out.append(
                f'<div class="fb-flow-kv"><span class="fb-flow-k">{_esc(k)}</span>'
                f'<span class="fb-flow-v">{_esc(v)}</span></div>'
            )
        out.append('</div>')
    return ''.join(out)


# ---------------------------------------------------------------------------
# 证据图闭环: 迭代时间线 + 证据图说明(《FlowBD_证据图闭环_制作计划.md》第 4 章)
# ---------------------------------------------------------------------------

EG_ACTION_LABELS = {
    "BFRS": "广度检索", "DFRS": "定向深查",
    "WRITE_GRAPH": "证据写回", "TERMINATE": "终止作答",
}


def iteration_timeline_html(iterations, stop_reason=None) -> str:
    """迭代闭环逐轮时间线(计划 4.1)。

    iterations: [{round, action, query, writes, reason}](AgentPipelineState.iterations)
    按轮次分组渲染卡片; 每事件一个动作徽标 + 明细行。
    """
    if not iterations:
        return ""
    rounds: dict = {}
    order: list = []
    for it in iterations or []:
        try:
            r = int(it.get("round", 0) or 0)
        except (TypeError, ValueError):
            r = 0
        if r not in rounds:
            rounds[r] = []
            order.append(r)
        rounds[r].append(it)
    cards = []
    for r in order:
        rows = []
        for ev in rounds[r]:
            action = str(ev.get("action") or "?").upper()
            label = EG_ACTION_LABELS.get(action, action)
            badge = f'<span class="fb-eg-badge {action.lower()}">{_esc(label)}</span>'
            bits = []
            if ev.get("query"):
                bits.append(f'查询: {_esc(ev["query"])}')
            if ev.get("writes"):
                bits.append(f'图更新: {_esc(ev["writes"])}')
            if ev.get("reason"):
                bits.append(f'理由: {_esc(ev["reason"])}')
            detail = ('<div class="fb-eg-detail">' + ' · '.join(bits) + '</div>') if bits else ''
            rows.append(f'<div class="fb-eg-event">{badge}{detail}</div>')
        cards.append(
            f'<div class="fb-eg-round"><div class="fb-eg-round-head">第 {r} 轮</div>'
            + ''.join(rows) + '</div>')
    stop = f'<div class="fb-eg-stop">判停: {_esc(stop_reason)}</div>' if stop_reason else ''
    return '<div class="fb-eg-tl">' + ''.join(cards) + stop + '</div>'


def inject_evidence_graph_css() -> None:
    """证据图闭环前端样式(时间线卡片/动作徽标/候选徽标说明)。色值走 --fb-* 变量。"""
    st.markdown("""
<style>
/* 迭代时间线 */
.fb-eg-tl { display: flex; flex-direction: column; gap: 8px; margin: 6px 0; }
.fb-eg-round { border: 1px solid var(--fb-line); border-radius: 9px; padding: 8px 10px;
  background: var(--fb-surface-2); }
.fb-eg-round-head { font-size: 12px; font-weight: 700; color: var(--fb-ink-2);
  margin-bottom: 6px; letter-spacing: .04em; }
.fb-eg-event { display: flex; align-items: flex-start; gap: 8px; margin: 4px 0; }
.fb-eg-badge { flex: none; font-size: 11px; font-weight: 600; padding: 2px 8px;
  border-radius: 999px; border: 1px solid var(--fb-line-2); color: var(--fb-ink-2); }
.fb-eg-badge.bfrs { background: #E7F0FE; color: #3B6EA5; border-color: #C7DBF7; }
.fb-eg-badge.dfrs { background: #F1EAFB; color: #6C4BB4; border-color: #DFD0F3; }
.fb-eg-badge.write_graph { background: var(--fb-teal-soft); color: var(--fb-teal-dark); border-color: transparent; }
.fb-eg-badge.terminate { background: #FFEFDB; color: #A3660A; border-color: #F6DFBC; }
.fb-eg-detail { font-size: 12px; color: var(--fb-ink-2); line-height: 1.55; padding-top: 2px; }
.fb-eg-stop { font-size: 12px; color: var(--fb-ink-3); margin-top: 2px; }

/* 证据图候选徽标说明 */
.fb-eg-legend { font-size: 12px; color: var(--fb-ink-3); margin-bottom: 4px; }
.fb-eg-candidate-tag { display: inline-block; font-size: 11px; padding: 1px 7px;
  border-radius: 999px; background: #FFEFDB; color: #A3660A; font-weight: 600; }
</style>
""", unsafe_allow_html=True)


def inject_sidebar_demo_css() -> None:
    """侧栏 demo 对齐样式: 导航项 / 历史纯文本行(悬停显删除) / 底部统计条。
    与 inject_global_css 叠加使用; 历史行选择器限定在 stHorizontalBlock 内,
    不影响侧栏其他按钮(初始化系统等保持 boxed 样式)。"""
    st.markdown("""
<style>
/* 导航 (demo 同款: 当前页 teal-soft 高亮) */
.fb-nav { display: flex; flex-direction: column; gap: 2px; margin: 14px 0 16px; }
.fb-nav-item { display: flex; align-items: center; gap: 9px; padding: 7px 10px;
  border-radius: 7px; font-size: 13px; color: var(--fb-ink-2) !important; text-decoration: none !important; }
.fb-nav-item svg { flex: none; }
.fb-nav-item:hover { background: var(--fb-line-2); color: var(--fb-ink) !important; text-decoration: none !important; }
.fb-nav-item.active { background: var(--fb-teal-soft); color: var(--fb-teal-dark) !important; font-weight: 600; }

/* 历史区标签 */
.fb-hist-label { font-size: 12px; color: var(--fb-ink-3); margin: 4px 0 6px 4px; }

/* 历史行: 纯文本样式 (覆盖全局 boxed 按钮, 仅限水平块内的历史两列) */
[data-testid="stSidebar"] [data-testid="stHorizontalBlock"] div.stButton > button[data-testid="stBaseButton-secondary"] {
  background: transparent !important; border: none !important; border-radius: 8px !important;
  box-shadow: none !important; padding: 5px 10px !important; min-height: 0 !important;
  color: var(--fb-ink-2) !important; font-weight: 400 !important;
  justify-content: flex-start !important; text-align: left !important;
}
[data-testid="stSidebar"] [data-testid="stHorizontalBlock"] div.stButton > button[data-testid="stBaseButton-secondary"]:hover {
  background: var(--fb-line-2) !important; color: var(--fb-ink) !important; border: none !important;
}
[data-testid="stSidebar"] [data-testid="stHorizontalBlock"] div.stButton > button[data-testid="stBaseButton-secondary"] p {
  white-space: nowrap !important; overflow: hidden !important;
  text-overflow: ellipsis !important; font-size: 13.5px !important;
}
/* 删除按钮: 默认隐藏, 行悬停显现 (demo 同款) */
[data-testid="stSidebar"] [data-testid="stHorizontalBlock"] [data-testid="column"]:last-child div.stButton > button {
  opacity: 0 !important; transition: opacity .15s !important;
}
[data-testid="stSidebar"] [data-testid="stHorizontalBlock"]:hover [data-testid="column"]:last-child div.stButton > button {
  opacity: 1 !important;
}
/* 历史行两列间距紧凑 */
[data-testid="stSidebar"] [data-testid="stHorizontalBlock"] { gap: 0.15rem !important; }

/* 底部统计条 (demo 同款) */
.fb-side-stats { display: flex; border-top: 1px solid var(--fb-line); margin-top: 16px; padding-top: 12px; }
.fb-side-stats .fb-stat { flex: 1; text-align: center; }
.fb-side-stats .fb-stat b { display: block; font-size: 17px; color: var(--fb-ink); font-weight: 700; }
.fb-side-stats .fb-stat span { font-size: 11px; color: var(--fb-ink-3); }
</style>
""", unsafe_allow_html=True)


def inject_topbar_layout_css() -> None:
    """固定顶栏布局：保留 Streamlit 原生侧栏切换按钮，主区/侧栏为 52px 顶栏让位。"""
    st.markdown(
        """
<style>
/* 自定义品牌顶栏覆盖原生顶栏视觉，但不干预侧栏的原生开关逻辑。 */
/*
 * Streamlit 的展开按钮（stExpandSidebarButton）挂在 stHeader 里面。
 * 不能把 stHeader 设为 display:none，否则侧栏收起后按钮会一起消失，
 * 或者落在品牌顶栏下面无法点击。保留一个零高度、可溢出的容器，
 * 再把按钮本身提到品牌栏之上。
 */
header[data-testid="stHeader"] {
  display: flex !important;
  height: 0 !important;
  min-height: 0 !important;
  background: transparent !important;
  overflow: visible !important;
  pointer-events: none !important;
  z-index: 1000000 !important;
}
header[data-testid="stHeader"] [data-testid="stToolbar"] {
  height: 0 !important;
  min-height: 0 !important;
  overflow: visible !important;
  pointer-events: none !important;
}
.main .block-container { padding-top: 72px !important; }
section[data-testid="stSidebar"] { top: 0 !important; height: 100vh !important; }
[data-testid="stSidebar"] [data-testid="stSidebarContent"] { padding-top: 60px !important; }

/*
 * 两个原生开关统一为 32px 高。
 * 展开按钮只在侧栏收起时出现，固定到品牌顶栏下方，避免被顶栏遮挡；
 * 收起按钮仍留在侧栏标题行内，不改变侧栏宽度或布局。
 */
[data-testid="stExpandSidebarButton"] {
  position: fixed !important;
  top: 62px !important;
  left: 8px !important;
  margin: 0 !important;
  z-index: 1000001 !important;
  width: 32px !important;
  min-width: 32px !important;
  height: 32px !important;
  min-height: 32px !important;
  box-sizing: border-box !important;
  pointer-events: auto !important;
}
[data-testid="stExpandSidebarButton"] button,
[data-testid="stExpandSidebarButton"] [data-testid="stBaseButton-headerNoPadding"] {
  width: 32px !important;
  min-width: 32px !important;
  height: 32px !important;
  min-height: 32px !important;
  box-sizing: border-box !important;
  pointer-events: auto !important;
}

[data-testid="stSidebarCollapseButton"],
[data-testid="stSidebarCollapseButton"] button {
  height: 32px !important;
  min-height: 32px !important;
  width: 32px !important;
  min-width: 32px !important;
  box-sizing: border-box !important;
}
</style>
""", unsafe_allow_html=True)
