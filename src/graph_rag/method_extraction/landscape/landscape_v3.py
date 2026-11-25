"""
landscape_v3.py — 相变材料稳定性评价方法谱系 (FlowBD-V1)

数据边界 (严格只读, 只用 v2):
    - lineage_methods_normalized_v2.csv          → 8 节点
    - lineage_edges_confirmed_v2.csv             → 1 条 confirmed 边
    - lineage_graph_data_v2.json                 → 补充 branches 顺序
    - excluded_lineage_candidates.csv (审计用)   → 只放折叠面板, **不进图**

绝不:
    - 混用 v1 lineage 文件
    - 把 `lineage_edges_candidate.csv` 的 2 条 excluded 边作为 candidate 画出
    - 出现小数年份/标签重叠

页面结构 (论文展示级):
    H1 「相变材料稳定性评价方法谱系」 (FlowBD-V1 方法演化追踪案例)
    一行指标:  8 节点 · 1 条 confirmed · 2004–2021 · 4 分支
    ┌─────────────────────────────┬──────────────┐
    │  横向地铁线路时间轴 (matplotlib) │  节点详情抽屉 │
    │  高度 450–550 px               │  (selectbox +│
    │                               │   完整信息卡) │
    └─────────────────────────────┴──────────────┘
    一行图例   |   导出 PNG   |   导出 CSV
    审计记录折叠 (excluded 2 条)
    (可选) 储能方法全景 · 开发者/实验视图 均已放在页面底部折叠

启动:
    streamlit run src/graph_rag/method_extraction/landscape/landscape_v3.py --server.port 8511
"""
from __future__ import annotations

import ast
import html
import io
import json
import os
import sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if THIS_DIR not in sys.path:
    sys.path.insert(0, THIS_DIR)

import matplotlib
matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

# 中文字体
for _f in ("Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "PingFang SC",
           "WenQuanYi Micro Hei", "sans-serif"):
    plt.rcParams["font.sans-serif"] = [_f] + plt.rcParams["font.sans-serif"]
plt.rcParams["axes.unicode_minus"] = False


# ==================== 常量 ====================

_PROJECT_ROOT = os.path.abspath(
    os.path.join(THIS_DIR, "..", "..", "..", "..")
)
_LINEAGE_DIR = os.path.join(
    _PROJECT_ROOT, "paper", "method_evolution_v2",
    "article_minimal_results", "lineage_mvp",
)
_FIGURE_DATA_DIR = os.path.join(
    _PROJECT_ROOT, "paper", "method_evolution_v2",
    "article_minimal_results", "figure_data",
)
_UNIFIED_DIR = os.path.join(
    _PROJECT_ROOT, "paper", "method_evolution_v2",
    "article_minimal_results", "lineage_cases_unified",
)

# 4 条分支的固定顺序 (spec 二·3)
BRANCHES_ORDER = ["渗透/扩散评价法", "观察法", "称重法", "综合判定法"]

# 分支配色: 低饱和度 蓝/青/橙/绿 (spec 四·3)
BRANCH_COLORS = {
    "渗透/扩散评价法": "#5B9BD5",   # 低饱和蓝
    "观察法":         "#4CB5C7",   # 低饱和青
    "称重法":         "#E8A555",   # 低饱和橙
    "综合判定法":     "#7CB878",   # 低饱和绿
}
BRANCH_LIGHT = {
    "渗透/扩散评价法": "#E7F0F9",
    "观察法":         "#E1F0F3",
    "称重法":         "#FBEEDD",
    "综合判定法":     "#EAF3E3",
}

# 只画数据里实际出现的整数年份 (spec 二·2)
YEAR_TICKS = [2004, 2013, 2014, 2020, 2021]

# confirmed 深蓝粗实线 (spec 四·4)
CONFIRMED_COLOR = "#1F3A93"

REL_LABEL_CN = {
    "ADAPTS": "借鉴", "EXTENDS": "延展",
    "IMPROVES": "改进", "REPLACES": "替代",
}

# ---- 复用 QA 页皮肤 (ui_style.PALETTE + inject_global_css, --fb-* 变量) ----
# 找不到 ui_style 时降级为本地等价色值, 页面功能不受影响
_KG_UI_DIR = os.path.join(_PROJECT_ROOT, "src", "KnowledgeGraph-Streamlit-main")
try:
    if _KG_UI_DIR not in sys.path:
        sys.path.insert(0, _KG_UI_DIR)
    import ui_style as _ui_style
    PAL = _ui_style.PALETTE
except Exception:
    _ui_style = None
    PAL = {
        "bg": "#f6f5f2", "surface": "#ffffff", "surface_2": "#faf9f6",
        "ink": "#1c1917", "ink_2": "#57534e", "ink_3": "#a8a29e",
        "line": "#e8e5df", "line_2": "#f0eee8",
        "teal": "#0f766e", "amber": "#b45309", "rose": "#be3455",
    }


# ==================== 数据加载 (只读) ====================

@st.cache_data(show_spinner="加载 lineage_mvp v2 数据 (只读)...")
def load_lineage_v2() -> dict:
    """严格只加载 spec 里指定的 3 个 v2 文件. 不碰 v1."""
    methods_csv = os.path.join(_LINEAGE_DIR, "lineage_methods_normalized_v2.csv")
    edges_confirmed_csv = os.path.join(_LINEAGE_DIR, "lineage_edges_confirmed_v2.csv")
    graph_json = os.path.join(_LINEAGE_DIR, "lineage_graph_data_v2.json")

    methods_df = pd.read_csv(methods_csv)
    edges_confirmed_df = pd.read_csv(edges_confirmed_csv)
    with open(graph_json, "r", encoding="utf-8") as f:
        graph_data = json.load(f)

    def _parse_ev(x):
        if pd.isna(x) or not isinstance(x, str):
            return []
        try:
            return json.loads(x)
        except Exception:
            try:
                return ast.literal_eval(x)
            except Exception:
                return []

    methods_df["evidence_sentence_ids_parsed"] = (
        methods_df["evidence_sentence_ids"].apply(_parse_ev)
    )
    return {
        "methods_df": methods_df,
        "edges_confirmed_df": edges_confirmed_df,
        "graph_data": graph_data,
    }


@st.cache_data(show_spinner=False)
def load_excluded_audit() -> pd.DataFrame:
    """excluded_lineage_candidates.csv 只用于审计面板, 不进图."""
    p = os.path.join(_LINEAGE_DIR, "excluded_lineage_candidates.csv")
    if not os.path.exists(p):
        return pd.DataFrame()
    try:
        return pd.read_csv(p)
    except Exception:
        return pd.DataFrame()


# ==================== 三案例统一交付包 ====================

@st.cache_data(show_spinner="加载三案例方法谱系数据...")
def load_unified_manifest() -> dict:
    """读取统一交付包索引；专题 JSON 是前端的唯一主接口。"""
    p = os.path.join(_UNIFIED_DIR, "all_cases_manifest.json")
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


@st.cache_data(show_spinner=False)
def load_unified_case(case_id: str) -> dict:
    """读取单个 frontend_case.json，并保留原始字符串字段以免化学式/单位被改写。"""
    p = os.path.join(_UNIFIED_DIR, case_id, "frontend_case.json")
    with open(p, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def _unified_year(node: dict):
    try:
        return int(str(node.get("year", "")).strip())
    except (TypeError, ValueError):
        return None


def _unified_node_text(node: dict) -> str:
    label = str(node.get("display_name") or node.get("node_name") or node.get("node_id"))
    return label if len(label) <= 22 else label[:21] + "…"


def render_unified_case(case: dict, show_all: bool, line_classes: list[str]) -> None:
    """统一三案例交互视图：SVG 主图支持缩放/平移、节点/边点击详情，字段直读交付 JSON。"""
    manifest = case.get("manifest", {})
    all_nodes = list(case.get("nodes", []))
    all_edges = list(case.get("edges", []))
    nodes = all_nodes if show_all else [n for n in all_nodes if str(n.get("main_figure", "")).lower() == "true"]
    node_ids = {n.get("node_id") for n in nodes}
    edges = [e for e in all_edges
             if (show_all or str(e.get("main_figure", "")).lower() == "true")
             and e.get("relation_class") in line_classes
             and e.get("source_id") in node_ids and e.get("target_id") in node_ids]

    # 动态分支/年份布局：不假定案例一定是 4 分支，也不把无年份基线伪造为具体年份。
    branches = list(case.get("branches", []))
    branch_names = [str(b.get("branch_name") or b.get("branch_id")) for b in branches]
    for b in sorted({str(n.get("branch_name") or n.get("branch_id")) for n in nodes}):
        if b not in branch_names:
            branch_names.append(b)
    branch_colors = ["#2563EB", "#16A34A", "#DD6B20", "#7C3AED", "#0F766E", "#B45309", "#64748B"]
    bcol = {b: branch_colors[i % len(branch_colors)] for i, b in enumerate(branch_names)}
    years = sorted({_unified_year(n) for n in nodes if _unified_year(n) is not None})
    if not years:
        years = [0, 1]
    y0, y1 = min(years), max(years)
    if y0 == y1:
        y0, y1 = y0 - 1, y1 + 1
    W, H = 1180, max(500, 150 + 82 * len(branch_names))
    left, right, top, bottom = 155, 28, 54, 46
    plot_w, plot_h = W - left - right, H - top - bottom
    col_w = plot_w / max(1, len(branch_names))

    def x_of(n):
        br = str(n.get("branch_name") or n.get("branch_id"))
        x = left + (branch_names.index(br) + 0.5) * col_w
        yr = _unified_year(n)
        if yr is None:
            return x
        return x + ((yr - y0) / (y1 - y0) - 0.5) * min(col_w * 0.72, 88)

    def y_of(n):
        yr = _unified_year(n)
        if yr is None:
            return top + 24
        return top + (1 - (yr - y0) / (y1 - y0)) * plot_h

    pos = {n.get("node_id"): (x_of(n), y_of(n)) for n in nodes}
    svg = [f'<svg id="fbUnifiedSvg" viewBox="0 0 {W} {H}" role="img" aria-label="{html.escape(str(manifest.get("title_cn", "方法谱系")))}">']
    svg.append('<defs><filter id="fbShadow"><feDropShadow dx="0" dy="2" stdDeviation="2" flood-opacity=".15"/></filter></defs>')
    svg.append(f'<rect width="{W}" height="{H}" rx="12" fill="{PAL["surface_2"]}"/>')
    for i, yr in enumerate(years):
        yy = top + (1 - (yr - y0) / (y1 - y0)) * plot_h
        svg.append(f'<line x1="{left}" x2="{W-right}" y1="{yy:.1f}" y2="{yy:.1f}" stroke="{PAL["line"]}" stroke-dasharray="3 5"/>')
        svg.append(f'<text x="{left-14}" y="{yy+4:.1f}" text-anchor="end" font-size="12" fill="{PAL["ink_2"]}">{yr}</text>')
    for i, br in enumerate(branch_names):
        xx = left + (i + 0.5) * col_w
        svg.append(f'<line x1="{xx:.1f}" x2="{xx:.1f}" y1="{top-22}" y2="{H-bottom}" stroke="{bcol[br]}" stroke-opacity=".20"/>')
        svg.append(f'<text x="{xx:.1f}" y="25" text-anchor="middle" font-size="13" font-weight="600" fill="{bcol[br]}">{html.escape(br)}</text>')
    for e in edges:
        if e.get("source_id") not in pos or e.get("target_id") not in pos:
            continue
        x1, y1p = pos[e["source_id"]]; x2, y2p = pos[e["target_id"]]
        color = e.get("line_color") or "#111827"
        dash = {"dash_dot": "6 3 1 3", "dashed": "6 4"}.get(e.get("line_style"), "")
        marker = f'<marker id="arr{len(svg)}" markerWidth="8" markerHeight="8" refX="7" refY="3.5" orient="auto"><path d="M0,0 L0,7 L8,3.5 z" fill="{color}"/></marker>'
        svg.append(f'<defs>{marker}</defs><line class="fbEdge" data-id="{html.escape(str(e.get("edge_id")))}" x1="{x1:.1f}" y1="{y1p:.1f}" x2="{x2:.1f}" y2="{y2p:.1f}" stroke="{color}" stroke-width="2.4" stroke-dasharray="{dash}" marker-end="url(#arr{len(svg)-1})" opacity=".85"/>')
    for n in nodes:
        nid = str(n.get("node_id")); x, y = pos[nid]
        fill = n.get("node_color") or "#DBEAFE"
        border = bcol.get(str(n.get("branch_name") or n.get("branch_id")), "#2563EB")
        svg.append(f'<g class="fbNode" data-id="{html.escape(nid)}" tabindex="0" style="cursor:pointer"><rect x="{x-76:.1f}" y="{y-25:.1f}" width="152" height="50" rx="10" fill="{fill}" stroke="{border}" stroke-width="1.5" filter="url(#fbShadow)"/><text x="{x:.1f}" y="{y-4:.1f}" text-anchor="middle" font-size="11" font-weight="600" fill="{PAL["ink"]}">{html.escape(_unified_node_text(n))}</text><text x="{x:.1f}" y="{y+14:.1f}" text-anchor="middle" font-size="10" fill="{PAL["ink_2"]}">{html.escape(str(n.get("year_label") or "未提供"))}</text></g>')
    svg.append('</svg>')

    node_payload = {str(n.get("node_id")): n for n in nodes}
    edge_payload = {str(e.get("edge_id")): e for e in edges}
    payload = json.dumps({"nodes": node_payload, "edges": edge_payload}, ensure_ascii=False).replace("</", "<\\/")
    detail_fields = ["node_name", "source_paper", "source_authors", "method_or_material", "composition_or_structure", "problem_solved", "key_performance", "evidence_sentence", "evidence_location", "verification_status", "notes"]
    html_doc = f'''<style>
      #fbUnifiedWrap{{font-family:Inter,"Microsoft YaHei",sans-serif;color:{PAL["ink"]}}}
      #fbUnifiedSvg{{width:100%;height:auto;min-height:420px;border:1px solid {PAL["line"]};border-radius:12px;touch-action:none}}
      .fbNode:hover rect,.fbNode:focus rect{{stroke:#B45309;stroke-width:3}}
      #fbUnifiedDetail{{margin-top:10px;padding:12px 14px;border:1px solid {PAL["line"]};border-radius:10px;background:{PAL["surface"]};font-size:12px;line-height:1.55;max-height:220px;overflow:auto}}
      .fbDetailTitle{{font-size:14px;font-weight:700;margin-bottom:6px}} .fbDetailRow{{margin:3px 0}} .fbDetailKey{{color:{PAL["ink_2"]};font-weight:600}}
    </style><div id="fbUnifiedWrap"><div style="display:flex;gap:6px;margin:0 0 6px 2px"><button id="fbUnifiedFit" type="button">适应画布</button><button id="fbUnifiedFullscreen" type="button">全屏</button><span style="color:{PAL["ink_3"]};font-size:11px;align-self:center">滚轮缩放 · 拖拽平移</span></div>{''.join(svg)}<div id="fbUnifiedDetail"><span style="color:{PAL["ink_2"]}">点击节点或连线查看完整名称、来源、证据原句、定位、核验状态与备注。</span></div></div>
    <script>
    const FB_DATA={payload}; const detail=document.getElementById('fbUnifiedDetail');
    const esc=s=>String(s??'未提供').replace(/[&<>\"]/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}}[c]));
    function show(kind,id){{const o=FB_DATA[kind][id]; if(!o)return; let title=kind==='nodes'?(o.display_name||o.node_name||id):(o.display_label||o.relation_type||id); let h='<div class="fbDetailTitle">'+esc(title)+'</div>'; if(kind==='nodes'){{h+='<div class="fbDetailRow"><span class="fbDetailKey">年份/分支：</span>'+esc(o.year_label||'未提供')+' · '+esc(o.branch_name||'未提供')+'</div>';}} else {{h+='<div class="fbDetailRow"><span class="fbDetailKey">关系：</span>'+esc(o.relation_type)+' · '+esc(o.relation_class)+' · '+esc(o.line_style)+'</div>';}} {''.join([f'h+="<div class=\\"fbDetailRow\\"><span class=\\"fbDetailKey\\">{k}：</span>"+esc(o[{k!r}])+"</div>";' for k in detail_fields])} if(kind==='edges'){{h+='<div class="fbDetailRow"><span class="fbDetailKey">来源节点：</span>'+esc(o.source_name)+'</div><div class="fbDetailRow"><span class="fbDetailKey">目标节点：</span>'+esc(o.target_name)+'</div>';}} detail.innerHTML=h;}}
    document.querySelectorAll('.fbNode').forEach(el=>el.addEventListener('click',()=>show('nodes',el.dataset.id)));
    document.querySelectorAll('.fbEdge').forEach(el=>el.addEventListener('click',()=>show('edges',el.dataset.id)));
    const svg=document.getElementById('fbUnifiedSvg'); let vb={{x:0,y:0,w:{W},h:{H}}}; let drag=null;
    function applyVB(){{svg.setAttribute('viewBox',`${{vb.x}} ${{vb.y}} ${{vb.w}} ${{vb.h}}`);}}
    svg.addEventListener('wheel',ev=>{{ev.preventDefault(); const k=ev.deltaY<0?.88:1.12; const r=svg.getBoundingClientRect(); const px=(ev.clientX-r.left)/r.width*vb.w+vb.x, py=(ev.clientY-r.top)/r.height*vb.h+vb.y; vb.x=px-(px-vb.x)*k; vb.y=py-(py-vb.y)*k; vb.w*=k; vb.h*=k; applyVB();}},{{passive:false}});
    svg.addEventListener('pointerdown',ev=>{{drag={{x:ev.clientX,y:ev.clientY,vx:vb.x,vy:vb.y}}; svg.setPointerCapture(ev.pointerId);}});
    svg.addEventListener('pointermove',ev=>{{if(!drag)return; const r=svg.getBoundingClientRect(); vb.x=drag.vx-(ev.clientX-drag.x)/r.width*vb.w; vb.y=drag.vy-(ev.clientY-drag.y)/r.height*vb.h; applyVB();}});
    svg.addEventListener('pointerup',()=>drag=null); svg.addEventListener('pointercancel',()=>drag=null);
    document.getElementById('fbUnifiedFit').addEventListener('click',()=>{{vb={{x:0,y:0,w:{W},h:{H}}};applyVB();}});
    document.getElementById('fbUnifiedFullscreen').addEventListener('click',()=>{{const w=document.getElementById('fbUnifiedWrap'); if(w.requestFullscreen)w.requestFullscreen();}});
    </script>'''
    components.html(html_doc, height=H + 280, scrolling=True)

    audit = case.get("audit_summary", {})
    st.caption(f"证据边界：{manifest.get('evidence_boundary', '未提供')}  ·  主图节点 {len([n for n in all_nodes if str(n.get('main_figure','')).lower() == 'true'])} / 当前显示 {len(nodes)} · 当前关系 {len(edges)}")
    with st.expander("案例说明与审计口径", expanded=False):
        st.write(manifest.get("subtitle") or manifest.get("research_domain") or "")
        st.info(manifest.get("evidence_boundary", "未提供证据边界"))
        st.json(audit)


# ==================== 地铁图渲染 (matplotlib) ====================

def render_metro_figure(methods_df: pd.DataFrame,
                         edges_confirmed_df: pd.DataFrame,
                         highlight_id: str | None = None):
    """横向地铁线路式时间轴. 高度 500 px @ 100dpi (fig=(13,5)).

    - 4 条固定分支 → 4 条水平轨道 (低饱和度蓝/青/橙/绿)
    - 5 个整数年份 → 5 列刻度: 2004, 2013, 2014, 2020, 2021
    - 每节点 = 圆角信息卡: 年份 + 方法简称 + own/ref 徽标
    - ★ 金色星标 = 数据集内最早可追溯 (**不写"首次提出"**)
    - 唯一 confirmed 边: 深蓝粗实线箭头 + 中央文字 "ADAPTS · 借鉴"
    """
    fig, ax = plt.subplots(figsize=(13, 5), dpi=100)
    ax.set_facecolor(PAL["surface_2"])
    fig.patch.set_facecolor(PAL["surface"])

    n_years = len(YEAR_TICKS)
    n_branches = len(BRANCHES_ORDER)

    ax.set_xlim(-1.4, n_years - 0.5)
    ax.set_ylim(-0.6, n_branches - 0.4)
    ax.axis("off")

    x_of = {y: i for i, y in enumerate(YEAR_TICKS)}
    y_of = {b: (n_branches - 1 - i) for i, b in enumerate(BRANCHES_ORDER)}

    # ---- 分支水平轨道 + 左侧标签 ----
    for b, yy in y_of.items():
        col = BRANCH_COLORS[b]
        # 轨道
        ax.plot([-0.35, n_years - 0.5], [yy, yy],
                color=col, linewidth=10, alpha=0.28,
                solid_capstyle="round", zorder=1)
        # 左侧分支标签胶囊
        ax.text(-0.55, yy, b, fontsize=14, fontweight="bold",
                ha="right", va="center", color=PAL["ink"],
                bbox=dict(boxstyle="round,pad=0.45",
                          facecolor=col, edgecolor=PAL["ink_2"],
                          linewidth=1.0, alpha=0.95), zorder=2)

    # ---- 年份刻度 (顶部一条竖虚线 + 底部数字) ----
    for y, i in x_of.items():
        ax.axvline(i, color=PAL["line"], linewidth=0.8, linestyle=":",
                    zorder=0.5, alpha=0.75)
        ax.text(i, -0.45, str(y), fontsize=13, fontweight="bold",
                ha="center", va="top", color=PAL["ink_2"])

    # ---- 节点信息卡 ----
    # 处理同 (year, branch) 多节点 -> 垂直堆叠
    filled: dict[tuple, int] = {}
    for _, row in methods_df.iterrows():
        yr = int(row["year"])
        br = row["branch"]
        if yr not in x_of or br not in y_of:
            continue
        cell = (yr, br)
        filled[cell] = filled.get(cell, 0) + 1

    positions: dict[str, tuple[float, float]] = {}
    stacked: dict[tuple, int] = {}
    for _, row in methods_df.iterrows():
        yr = int(row["year"])
        br = row["branch"]
        if yr not in x_of or br not in y_of:
            continue
        cell = (yr, br)
        idx = stacked.get(cell, 0)
        stacked[cell] = idx + 1
        total = filled[cell]

        base_x = x_of[yr]
        base_y = y_of[br]
        # 同 cell 有多节点时上下错开
        if total == 1:
            off_y = 0.0
        else:
            # 均匀分布在 [-0.24, +0.24]
            step = 0.48 / max(1, total - 1)
            off_y = -0.24 + step * idx
        node_x, node_y = base_x, base_y + off_y
        positions[row["node_id"]] = (node_x, node_y)

        _draw_node_card(
            ax, node_x, node_y, row,
            is_highlighted=(highlight_id == row["node_id"]),
        )

    # ---- 唯一 confirmed 关系 (深蓝粗实线箭头) ----
    for _, e in edges_confirmed_df.iterrows():
        # 数据里 from=借鉴者(晚), to=来源(早); 视觉方向: 来源 → 后续
        src_id = e["to_method_id"]     # 视觉起点 = 更早节点
        tgt_id = e["from_method_id"]   # 视觉终点 = 后续节点
        if src_id not in positions or tgt_id not in positions:
            continue
        sx, sy = positions[src_id]
        tx, ty = positions[tgt_id]

        # 箭头从卡片右侧发出, 到目标卡片左侧收
        arrow = FancyArrowPatch(
            (sx + 0.36, sy), (tx - 0.36, ty),
            arrowstyle="-|>",
            mutation_scale=24,
            connectionstyle="arc3,rad=-0.18",
            color=CONFIRMED_COLOR,
            linewidth=3.4,
            zorder=2.8,
        )
        ax.add_patch(arrow)

        # 中央标注 "ADAPTS · 借鉴" 胶囊
        mx = (sx + tx) / 2
        my = (sy + ty) / 2 - 0.28   # 微上偏, 因为 arc 弧线在下方
        rel_cn = REL_LABEL_CN.get(e["relation"], e["relation"])
        ax.text(mx, my, f"{e['relation']} · {rel_cn}",
                fontsize=12, fontweight="bold",
                ha="center", va="center", color="#FFFFFF",
                bbox=dict(boxstyle="round,pad=0.35",
                          facecolor=CONFIRMED_COLOR,
                          edgecolor="#0F1F5F", linewidth=1.2),
                zorder=6)

    plt.subplots_adjust(left=0.13, right=0.99, top=0.98, bottom=0.06)
    return fig


def _draw_node_card(ax, x, y, row, is_highlighted=False):
    """单个节点卡片: 白底 + 分支色边框, 显示年份 + 简称 + own/ref 徽标; ★=最早."""
    branch = row["branch"]
    col = BRANCH_COLORS.get(branch, PAL["ink_3"])
    light = BRANCH_LIGHT.get(branch, PAL["surface_2"])
    is_own = row["kind"] == "own"
    is_earliest = bool(row["is_earliest"])

    w, h = 0.78, 0.36
    lw = 3.2 if is_highlighted else 2.2
    edge = PAL["rose"] if is_highlighted else col

    card = FancyBboxPatch(
        (x - w / 2, y - h / 2), w, h,
        boxstyle="round,pad=0.02,rounding_size=0.06",
        facecolor=light if is_own else PAL["surface"],
        edgecolor=edge, linewidth=lw, zorder=3,
    )
    ax.add_patch(card)

    # 简称 (14pt, spec 四·2)
    short = str(row["short_name"])
    if len(short) > 12:
        short = short[:11] + "…"
    ax.text(x, y + 0.06, short, fontsize=14, fontweight="bold",
            ha="center", va="center", color=PAL["ink"], zorder=5)

    # 年份 + own/ref 徽标 (下方一行)
    yr_txt = str(int(row["year"]))
    badge_txt = "本文" if is_own else "引用"
    badge_color = PAL["rose"] if is_own else PAL["ink_2"]
    ax.text(x - 0.24, y - 0.08, yr_txt,
            fontsize=11, fontweight="bold",
            ha="center", va="center", color=PAL["ink_2"], zorder=5)
    ax.text(x + 0.20, y - 0.08, badge_txt,
            fontsize=10, fontweight="bold",
            ha="center", va="center", color="#FFFFFF",
            bbox=dict(boxstyle="round,pad=0.18",
                      facecolor=badge_color, edgecolor="none"),
            zorder=5)

    # 最早节点 = 金星
    if is_earliest:
        ax.plot(x - w / 2 + 0.07, y + h / 2 - 0.04,
                marker="*", markersize=22,
                color=PAL["amber"], markeredgecolor=PAL["amber"],
                markeredgewidth=1.4, zorder=6)


# ==================== 详情面板 ====================

def render_detail_drawer(methods_df: pd.DataFrame,
                          edges_confirmed_df: pd.DataFrame,
                          picked_id: str | None):
    """右侧抽屉: 显示节点完整信息 (含 sentence_id, 原文证据)."""
    st.markdown("#### 节点详情")

    labels = {
        row["node_id"]: f"[{int(row['year'])}] {row['short_name']}"
        for _, row in methods_df.iterrows()
    }
    options = [None] + methods_df["node_id"].tolist()
    default_idx = 0 if picked_id is None else options.index(picked_id)

    selected = st.selectbox(
        "选择节点",
        options,
        index=default_idx,
        format_func=lambda x: "— 未选择 —" if x is None else labels.get(x, x),
        label_visibility="collapsed",
    )

    if selected is None:
        st.info("在下拉框里选择一个节点以查看:\n\n"
                "- 完整方法名\n- 年份 + 年份来源\n- 作者\n- 来源论文\n"
                "- 证据 sentence_id\n- 参考文献原文\n- 审查备注")
        return None

    row = methods_df[methods_df["node_id"] == selected].iloc[0]

    is_own = row["kind"] == "own"
    is_earliest = bool(row["is_earliest"])
    star = "🌟 " if is_earliest else ""
    tag_html = (f'<span style="background:{PAL["rose"]};color:#fff;padding:2px 8px;'
                'border-radius:10px;font-size:11px">本文提出</span>'
                if is_own else
                f'<span style="background:{PAL["ink_2"]};color:#fff;padding:2px 8px;'
                'border-radius:10px;font-size:11px">引用</span>')
    st.markdown(f"##### {star}{row['short_name']} {tag_html}",
                unsafe_allow_html=True)

    if is_earliest:
        st.caption("★ 数据集内最早可追溯 (不代表全球首次提出)")

    # 完整方法名
    st.markdown(f"**完整方法名**")
    st.write(row["canonical_method_name"])

    # 年份 + 来源
    st.markdown(f"**年份**: `{int(row['year'])}`  ")
    yr_src = row["year_source"]
    st.caption(f"年份来源: `{yr_src}`")
    if str(yr_src).startswith("reference_list_entry"):
        st.caption("✓ 引用方法 · 年份取自被引文献本身,不是本综述发表年")
    elif yr_src == "primary_paper_publish_year":
        st.caption("✓ 本文自建方法 · 年份 = 主论文发表年 (2021)")

    # 作者 + 来源论文
    st.markdown(f"**作者**: {row['author']}")
    st.markdown(f"**来源论文**")
    st.caption(row["paper_id"])

    # 参考文献原文
    ref_raw = row.get("reference_text_raw")
    if isinstance(ref_raw, str) and ref_raw.strip():
        st.markdown("**参考文献原文**")
        st.caption(ref_raw)

    # 证据 sentence_id + 原文
    ev_ids = row["evidence_sentence_ids_parsed"] or []
    st.markdown("**证据 sentence_id**")
    if ev_ids:
        st.code(", ".join(ev_ids), language=None)
    else:
        st.caption("(缺失)")

    # 分支 + 核心工艺/材料
    st.markdown(f"**分支**: {row['branch']}")
    if isinstance(row.get("core_process"), str):
        st.caption(f"核心工艺: {row['core_process']}")
    if isinstance(row.get("core_material"), str):
        st.caption(f"核心材料: {row['core_material']}")

    # 审查备注
    note = row.get("note")
    if isinstance(note, str) and note.strip():
        st.markdown("**审查备注**")
        st.caption(note)

    # 涉及的 confirmed 边
    out_e = edges_confirmed_df[edges_confirmed_df["from_method_id"] == selected]
    in_e = edges_confirmed_df[edges_confirmed_df["to_method_id"] == selected]
    if len(out_e) or len(in_e):
        st.markdown("**参与的 confirmed 关系**")
        for _, e in out_e.iterrows():
            rel_cn = REL_LABEL_CN.get(e["relation"], e["relation"])
            st.caption(f"该节点 →({e['relation']} · {rel_cn})→ "
                       f"{e['to_method_name'][:32]} · 审查: {e.get('validation_status','?')}")
        for _, e in in_e.iterrows():
            rel_cn = REL_LABEL_CN.get(e["relation"], e["relation"])
            st.caption(f"← ({e['relation']} · {rel_cn}) 于 "
                       f"{e['from_method_name'][:32]} · 审查: {e.get('validation_status','?')}")

    return selected


# ==================== 图例 (一行, 压缩) ====================

def render_legend_oneliner():
    parts = []
    for b, c in BRANCH_COLORS.items():
        parts.append(
            f'<span style="display:inline-flex;align-items:center;margin-right:14px">'
            f'<span style="display:inline-block;width:14px;height:6px;'
            f'background:{c};border-radius:3px;margin-right:4px"></span>{b}</span>'
        )
    parts.append(
        f'<span style="margin-right:14px"><span style="color:{PAL["amber"]}">★</span> '
        '数据集内最早可追溯</span>'
    )
    parts.append(
        '<span style="margin-right:14px">'
        f'<span style="background:{PAL["rose"]};color:#fff;padding:1px 6px;'
        'border-radius:8px;font-size:11px">本文</span> · '
        f'<span style="background:{PAL["ink_2"]};color:#fff;padding:1px 6px;'
        'border-radius:8px;font-size:11px">引用</span></span>'
    )
    parts.append(
        f'<span><span style="display:inline-block;width:22px;height:3px;'
        f'background:{CONFIRMED_COLOR};margin-right:4px;vertical-align:middle"></span>'
        f'confirmed 关系 (深蓝实线)</span>'
    )
    st.markdown(
        f'<div style="display:flex;flex-wrap:wrap;font-size:12px;color:{PAL["ink_2"]};'
        f'padding:8px 12px;background:{PAL["surface_2"]};border:1px solid {PAL["line"]};'
        'border-radius:8px;margin-top:4px">'
        + "".join(parts) + "</div>",
        unsafe_allow_html=True,
    )


# ==================== 年份谱系图 (纵轴 DAG, demo 同款 canvas) ====================

def render_lineage_dag(methods_df: pd.DataFrame,
                       edges_confirmed_df: pd.DataFrame,
                       height: int = 440):
    """纵轴年份谱系 DAG (ui-demo drawLineage 同款): components.html canvas。
    - 纵轴整数年份网格 (只出现整数年份), 4 分支列 (BRANCHES_ORDER/BRANCH_COLORS)
    - confirmed 边按 visualization_direction 来源→后续应用 绘制, 带箭头
    - 红线: candidate/excluded 边一律不画; 样式色值全部走 PAL
    """
    pal = PAL
    nodes = []
    for _, row in methods_df.iterrows():
        author = str(row["author"])
        if len(author) > 14:
            author = author[:13] + "…"
        nodes.append({
            "id": row["node_id"],
            "label": str(row["short_name"]),
            "who": f"{author} · {int(row['year'])}",
            "year": int(row["year"]),
            "branch": row["branch"],
            "own": bool(row["kind"] == "own"),
            "earliest": bool(row["is_earliest"]),
            "full": str(row["canonical_method_name"]),
            "process": str(row.get("core_process", "") or ""),
        })
    edges = []
    for _, e in edges_confirmed_df.iterrows():
        rel = str(e["relation"])
        edges.append({
            # visualization_direction: 来源 (to_method, 旧) → 后续应用 (from_method, 新)
            "a": e["to_method_id"],
            "b": e["from_method_id"],
            "label": f"{rel} · {REL_LABEL_CN.get(rel, '')}",
        })
    payload = json.dumps({
        "nodes": nodes,
        "edges": edges,
        "branches": [{"label": b, "color": BRANCH_COLORS[b]} for b in BRANCHES_ORDER],
        "yMin": int(methods_df["year"].min()) - 2,
        "yMax": int(methods_df["year"].max()) + 2,
    }, ensure_ascii=False)

    dag_html = """
<div style="position:relative">
<canvas id="fbLineageCv" style="width:100%;height:__H__px;border:1px solid __LINE__;border-radius:8px;background:__BG__"></canvas>
<div id="fbLineageTip" style="display:none;position:absolute;z-index:10;max-width:280px;background:#ffffff;border:1px solid __LINE__;border-radius:8px;padding:8px 10px;font:12px/1.5 Inter,sans-serif;color:__INK__;box-shadow:0 4px 14px rgba(0,0,0,.08);pointer-events:none"></div>
</div>
<script>
const data = __DATA__;
const cv = document.getElementById('fbLineageCv');
const tip = document.getElementById('fbLineageTip');
let px = [];
function drawDag() {
  // Streamlit components.html iframe 里脚本可能先于布局执行, clientWidth=0 时跳过等重绘
  const dpr = window.devicePixelRatio || 1;
  const w = cv.clientWidth, h = cv.clientHeight;
  if (!w || !h) return;
  cv.width = w * dpr; cv.height = h * dpr;
  const ctx = cv.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, w, h);
  const padL = 52, padT = 36, padB = 18, padR = 16;
  const plotW = w - padL - padR, plotH = h - padT - padB;
  const yearY = yr => padT + (1 - (yr - data.yMin) / (data.yMax - data.yMin)) * plotH;
  // 整数年份网格 (步长 1/2/4/5, 只标整数)
  const span = data.yMax - data.yMin;
  const step = span <= 8 ? 1 : (span <= 16 ? 2 : (span <= 28 ? 4 : 5));
  ctx.font = '10.5px Consolas, monospace';
  ctx.textAlign = 'right'; ctx.textBaseline = 'middle';
  for (let yr = Math.ceil(data.yMin / step) * step; yr <= data.yMax; yr += step) {
    const y = yearY(yr);
    ctx.strokeStyle = '__LINE__'; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(padL, y); ctx.lineTo(w - padR, y); ctx.stroke();
    ctx.fillStyle = '__INK3__';
    ctx.fillText(String(yr), padL - 8, y);
  }
  // 分支列: 顶部药丸表头
  const nb = data.branches.length, colW = plotW / nb;
  const colX = {}, bcol = {};
  data.branches.forEach((b, i) => {
    colX[b.label] = padL + (i + 0.5) * colW;
    bcol[b.label] = b.color;
    ctx.font = '600 11.5px Inter, sans-serif';
    ctx.textAlign = 'center'; ctx.textBaseline = 'top';
    const tw = ctx.measureText(b.label).width + 16;
    ctx.beginPath();
    ctx.roundRect(colX[b.label] - tw / 2, 6, tw, 18, 9);
    ctx.fillStyle = b.color + '22'; ctx.fill();
    ctx.lineWidth = 1; ctx.strokeStyle = b.color; ctx.stroke();
    ctx.fillStyle = '__INK2__';
    ctx.fillText(b.label, colX[b.label], 9);
  });
  // 节点位置: 分支内按年份排序, 奇偶错列; 同年多节点加大横向间距防文字重叠
  const pos = {};
  data.branches.forEach(b => {
    const mem = data.nodes.filter(n => n.branch === b.label).sort((p, q) => p.year - q.year);
    const yearCount = {}, yearSeen = {};
    mem.forEach(n => { yearCount[n.year] = (yearCount[n.year] || 0) + 1; });
    mem.forEach((n, i) => {
      let lane;
      if (yearCount[n.year] > 1) {
        const k = yearSeen[n.year] || 0;
        yearSeen[n.year] = k + 1;
        lane = (k - (yearCount[n.year] - 1) / 2) * 0.24 * plotW;
      } else {
        lane = (i % 2 === 0 ? -0.06 : 0.06) * plotW;
      }
      pos[n.id] = { x: colX[n.branch] + lane, y: yearY(n.year), n: n };
    });
  });
  // confirmed 边: 来源 → 后续应用 (二次曲线 + 箭头 + 标签药丸)
  data.edges.forEach(e => {
    const A = pos[e.a], B = pos[e.b];
    if (!A || !B) return;
    const dx = B.x - A.x, dy = B.y - A.y;
    const cpx = (A.x + B.x) / 2 - dy * (-0.16), cpy = (A.y + B.y) / 2 + dx * (-0.16);
    ctx.save();
    ctx.strokeStyle = '__CONF__'; ctx.lineWidth = 2.2;
    ctx.beginPath(); ctx.moveTo(A.x, A.y); ctx.quadraticCurveTo(cpx, cpy, B.x, B.y); ctx.stroke();
    // 箭头 (取 t=0.92 处曲线点与切线方向)
    const t = 0.92;
    const qx = 2 * (1 - t) * (cpx - A.x) + 2 * t * (B.x - cpx);
    const qy = 2 * (1 - t) * (cpy - A.y) + 2 * t * (B.y - cpy);
    const ang = Math.atan2(qy, qx);
    const ax = (1 - t) * (1 - t) * A.x + 2 * (1 - t) * t * cpx + t * t * B.x;
    const ay = (1 - t) * (1 - t) * A.y + 2 * (1 - t) * t * cpy + t * t * B.y;
    ctx.fillStyle = '__CONF__';
    ctx.beginPath();
    ctx.moveTo(ax + 8 * Math.cos(ang), ay + 8 * Math.sin(ang));
    ctx.lineTo(ax + 8 * Math.cos(ang + 2.6), ay + 8 * Math.sin(ang + 2.6));
    ctx.lineTo(ax + 8 * Math.cos(ang - 2.6), ay + 8 * Math.sin(ang - 2.6));
    ctx.closePath(); ctx.fill();
    // 关系标签药丸
    const mx = 0.25 * A.x + 0.5 * cpx + 0.25 * B.x;
    const my = 0.25 * A.y + 0.5 * cpy + 0.25 * B.y;
    ctx.font = '600 10px Consolas, monospace';
    const tw2 = ctx.measureText(e.label).width;
    ctx.beginPath();
    ctx.roundRect(mx - tw2 / 2 - 5, my - 8, tw2 + 10, 16, 8);
    ctx.fillStyle = 'rgba(255,255,255,.92)'; ctx.fill();
    ctx.lineWidth = 1; ctx.strokeStyle = '__CONF__'; ctx.stroke();
    ctx.fillStyle = '__CONF__';
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillText(e.label, mx, my);
    ctx.restore();
  });
  // 节点: 分支色圆点 + 白描边; 本文原创加 rose 外环; 最早可追溯加琥珀星
  px = [];
  Object.values(pos).forEach(p => {
    const n = p.n, col = bcol[n.branch] || '__INK3__';
    px.push({ X: p.x, Y: p.y, n: n });
    if (n.own) {
      ctx.beginPath(); ctx.arc(p.x, p.y, 10, 0, Math.PI * 2);
      ctx.lineWidth = 1.6; ctx.strokeStyle = '__ROSE__'; ctx.stroke();
    }
    ctx.beginPath(); ctx.arc(p.x, p.y, 7, 0, Math.PI * 2);
    ctx.fillStyle = col; ctx.fill();
    ctx.lineWidth = 2; ctx.strokeStyle = '#ffffff'; ctx.stroke();
    if (n.earliest) {
      ctx.font = '12px Inter, sans-serif';
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.lineWidth = 3; ctx.strokeStyle = '#ffffff';
      ctx.strokeText('★', p.x + 10, p.y - 10);
      ctx.fillStyle = '__AMBER__';
      ctx.fillText('★', p.x + 10, p.y - 10);
    }
    const label = n.label.length > 12 ? n.label.slice(0, 11) + '…' : n.label;
    ctx.textAlign = 'center';
    ctx.font = '600 11px Inter, sans-serif';
    ctx.fillStyle = '__INK__';
    ctx.fillText(label, p.x, p.y + 13);
    ctx.font = '10px Inter, sans-serif';
    ctx.fillStyle = '__INK3__';
    ctx.fillText(n.who, p.x, p.y + 26);
  });
}
// 悬停 tooltip: 完整方法名 + 作者年份 + 分支 + 工艺
cv.addEventListener('mousemove', e => {
  if (!px.length) return;
  const rect = cv.getBoundingClientRect();
  const mx = e.clientX - rect.left, my = e.clientY - rect.top;
  let best = null, bd = 16;
  px.forEach(p => {
    const d = Math.hypot(p.X - mx, p.Y - my);
    if (d < bd) { bd = d; best = p; }
  });
  if (best) {
    const n = best.n;
    tip.innerHTML = '<b>' + n.full + '</b><br><span style="color:__INK2__">' +
      n.who + ' · ' + n.branch + (n.own ? ' · 本文提出' : ' · 引用') +
      (n.process ? '<br>' + n.process : '') + '</span>';
    tip.style.display = 'block';
    tip.style.left = Math.min(mx + 14, cv.clientWidth - 290) + 'px';
    tip.style.top = Math.max(my - 60, 6) + 'px';
  } else {
    tip.style.display = 'none';
  }
});
cv.addEventListener('mouseleave', () => tip.style.display = 'none');
drawDag();
setTimeout(drawDag, 120);
setTimeout(drawDag, 600);
if (window.ResizeObserver) { new ResizeObserver(drawDag).observe(cv); }
window.addEventListener('resize', drawDag);
</script>
"""
    dag_html = (
        dag_html
        .replace("__DATA__", payload)
        .replace("__H__", str(height))
        .replace("__INK3__", pal["ink_3"])
        .replace("__INK2__", pal["ink_2"])
        .replace("__INK__", pal["ink"])
        .replace("__LINE__", pal["line"])
        .replace("__BG__", pal["surface_2"])
        .replace("__ROSE__", pal["rose"])
        .replace("__AMBER__", pal["amber"])
        .replace("__CONF__", CONFIRMED_COLOR)
    )
    components.html(dag_html, height=height + 24)
    st.caption("纵轴年份谱系图 · 数据: lineage_mvp v2 (只读) · 实线箭头 = confirmed 关系 (来源 → 后续应用) · 悬停节点查看详情")


# ==================== 审计记录 (excluded, 不进图) ====================

def render_audit_records():
    """spec 一·2: excluded 2 条只出现在此折叠面板, 不绘图."""
    excluded = load_excluded_audit()
    with st.expander(
        f"审计记录 · 已排除的候选关系 ({len(excluded)} 条, 不进入图谱)",
        expanded=False,
    ):
        st.caption(
            "以下候选关系**未通过严格核验**, 仅作透明度记录. "
            "文件: `paper/method_evolution_v2/article_minimal_results/lineage_mvp/excluded_lineage_candidates.csv`"
        )
        if excluded.empty:
            st.info("无 excluded 记录")
            return
        # 展示排除原因
        show_cols = [c for c in
                     ["orig_candidate_edge_id", "from_method_name",
                      "to_method_name", "orig_from_year", "orig_to_year",
                      "exclusion_reason", "final_status"]
                     if c in excluded.columns]
        st.dataframe(excluded[show_cols], use_container_width=True,
                     hide_index=True)


# ==================== 底部可选面板 (全景 + 开发者视图) ====================

@st.cache_data(show_spinner=False)
def _load_figure_data() -> dict:
    result = {}
    if not os.path.isdir(_FIGURE_DATA_DIR):
        return result
    for fname in sorted(os.listdir(_FIGURE_DATA_DIR)):
        if not fname.endswith(".csv"):
            continue
        try:
            result[fname.replace(".csv", "")] = pd.read_csv(
                os.path.join(_FIGURE_DATA_DIR, fname))
        except Exception:
            pass
    return result


def render_panorama_fold():
    with st.expander("📊 储能方法全景 (Stage A 统计, 不含演化关系)", expanded=False):
        st.caption("Stage A accepted 方法的统计分布 — 只做频率/分布, "
                   "**本折叠面板不呈现任何方法间演化关系**.")
        fig = _load_figure_data()
        if not fig:
            st.info("figure_data 目录为空")
            return
        cols = st.columns(2)
        with cols[0]:
            st.markdown("**主储能域 (n_papers)**")
            if "2_primary_storage_domain" in fig:
                st.bar_chart(fig["2_primary_storage_domain"]
                             .set_index("primary_storage_domain")["n_papers"])
            st.markdown("**own vs referenced**")
            if "4_kind_distribution" in fig:
                st.bar_chart(fig["4_kind_distribution"].set_index("kind"))
        with cols[1]:
            st.markdown("**技术子域 (top 15)**")
            if "3_technology_subfield" in fig:
                top = (fig["3_technology_subfield"]
                       .sort_values("n_papers", ascending=False).head(15))
                st.bar_chart(top.set_index("technology_subfield")["n_papers"])
            st.markdown("**方法角色**")
            if "5_method_role_main" in fig:
                st.bar_chart(fig["5_method_role_main"]
                             .set_index("method_role")["n"])


def render_dev_experimental_fold():
    with st.expander(
        "🧪 开发者 / 实验视图 — V1 UMAP+HDBSCAN 语义聚类 (不进入论文主结果)",
        expanded=False,
    ):
        st.warning(
            "⚠️ **仅供开发者查看**\n\n"
            "- 数据源: Neo4j `ProposedMethod` V1 UMAP+HDBSCAN 聚类结果\n"
            "- 9 个 HDBSCAN 聚簇 (C0-C8) **不是方法主线**\n"
            "- 边 `confidence=high` 只是 **高置信候选关系**, "
            "**不等同于 confirmed 关系**\n"
            "- 正式 confirmed 关系严格来自 lineage_edges_confirmed_v2.csv"
        )
        if not st.checkbox("我了解上述说明, 加载 V1 实验数据",
                            value=False, key="expand_dev_v1"):
            return
        try:
            from atlas_data import compute_atlas
            atlas = compute_atlas(include_peripheral=False)
        except Exception as e:
            st.error(f"V1 数据加载失败: {e}")
            return

        n_high = sum(1 for e in atlas["edges"] if e.get("confidence") == "high")
        n_med = sum(1 for e in atlas["edges"] if e.get("confidence") == "medium")
        n_low = sum(1 for e in atlas["edges"] if e.get("confidence") == "low")

        c = st.columns(3)
        c[0].metric("V1 节点", len(atlas["nodes"]))
        c[1].metric("V1 语义候选边", len(atlas["edges"]))
        c[2].metric("其中 high 置信 (候选)", n_high)

        rows = [{"C_id": cid,
                 "语义聚簇标签 (非方法主线)": c["label"],
                 "节点数": c["size"]}
                for cid, c in atlas["clusters"].items()]
        st.markdown("**HDBSCAN 语义聚簇分布** (实验参考, 非方法主线):")
        st.dataframe(pd.DataFrame(rows).sort_values("节点数", ascending=False),
                     use_container_width=True, hide_index=True)

        st.markdown("**边置信度分布** (**均为候选**, 无一进入 confirmed):")
        st.dataframe(pd.DataFrame([
            {"置信度": "high (高置信候选)", "边数": n_high},
            {"置信度": "medium (中置信候选)", "边数": n_med},
            {"置信度": "low (低置信候选)", "边数": n_low},
        ]), use_container_width=True, hide_index=True)


# ==================== 主入口 ====================

def main():
    st.set_page_config(
        page_title="相变材料稳定性评价方法谱系",
        layout="wide",
        initial_sidebar_state="collapsed",   # spec 三·3: 默认不显示复杂筛选
    )
    # 套用 QA 页同一套皮肤 (--fb-* 全局 CSS 变量)
    if _ui_style is not None:
        _ui_style.inject_global_css()

    # ---- 统一三案例入口（保留旧 lineage_mvp 文件作为历史兼容数据，不覆盖） ----
    # 新包存在时，8511 默认进入三案例专题页；若部署环境尚未迁移数据，则回退到原 PCM 页面。
    if os.path.isfile(os.path.join(_UNIFIED_DIR, "all_cases_manifest.json")):
        try:
            manifest_index = load_unified_manifest()
            cases = manifest_index.get("cases", [])
            if cases:
                labels = {c["case_id"]: f'{c.get("title_cn", c["case_id"])} · {c.get("year_range_main_figure", "")}' for c in cases}
                ids = [c["case_id"] for c in cases]
                selected_case = st.selectbox("专题案例", ids, format_func=lambda x: labels.get(x, x), key="unified_case_selector")
                case = load_unified_case(selected_case)
                cm = case.get("manifest", {})
                st.markdown(
                    f"<h2 style='margin-bottom:2px;color:{PAL['ink']}'>{html.escape(str(cm.get('title_cn') or selected_case))}</h2>"
                    f"<div style='color:{PAL['ink_2']};font-size:.95em;margin-bottom:12px'>{html.escape(str(cm.get('subtitle') or cm.get('research_domain') or '方法谱系专题'))}</div>",
                    unsafe_allow_html=True,
                )
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("主图节点", cm.get("main_figure_node_count", len(case.get("nodes", []))))
                m2.metric("直接演化", cm.get("direct_evolution_count", 0), f"主图 {cm.get('main_figure_direct_evolution', 0)}")
                yr_main = cm.get("year_range_main_figure") or (
                    f"{cm.get('main_figure_year_start')}—{cm.get('main_figure_year_end')}"
                    if cm.get('main_figure_year_start') is not None and cm.get('main_figure_year_end') is not None
                    else "未提供"
                )
                m3.metric("主图时间", yr_main)
                m4.metric("技术分支", cm.get("branch_count", len(case.get("branches", []))))
                ctl1, ctl2 = st.columns([1, 2])
                with ctl1:
                    show_all = st.checkbox("显示全部候选节点/关系", value=False, key=f"unified_all_{selected_case}")
                classes = ["direct_evolution", "baseline_comparison", "node_performance_comparison", "route_association"]
                class_labels = {"direct_evolution":"直接演化（实线）", "baseline_comparison":"基线比较（点划线）", "node_performance_comparison":"节点性能比较（点划线）", "route_association":"路线归类（虚线）"}
                with ctl2:
                    selected_classes = st.multiselect("关系类型", classes, default=classes, format_func=lambda x: class_labels[x], key=f"unified_lines_{selected_case}")
                render_unified_case(case, show_all, selected_classes)
                # 保留统一包中的静态出版物资产，作为专题页下载附件（图形本身仍使用可交互 SVG）。
                asset_cols = st.columns(4)
                assets = [
                    ("⬇ 主图 SVG", "main_figure.svg", "image/svg+xml"),
                    ("⬇ 主图 PNG", "main_figure_300dpi.png", "image/png"),
                    ("⬇ 主图 PDF", "main_figure.pdf", "application/pdf"),
                    ("⬇ 专题 JSON", "frontend_case.json", "application/json"),
                ]
                for col, (label, fname, mime) in zip(asset_cols, assets):
                    fp = os.path.join(_UNIFIED_DIR, selected_case, fname)
                    if os.path.isfile(fp):
                        with open(fp, "rb") as fh:
                            col.download_button(label, fh.read(), file_name=fname, mime=mime, use_container_width=True, key=f"asset_{selected_case}_{fname}")
                st.markdown("---")
                st.caption("数据接口：frontend_case.json · SVG/DOT/PNG/PDF 保留在统一交付目录，可用于下载与论文出图。原 lineage_mvp 单案例数据未被覆盖。")
                return
        except Exception as e:
            st.warning(f"三案例专题加载失败，回退到原 PCM 页面：{e}")

    # ---- 标题 ----
    st.markdown(
        f"<h2 style='margin-bottom:2px;color:{PAL['ink']}'>相变材料稳定性评价方法谱系</h2>"
        f"<div style='color:{PAL['ink_2']};font-size:0.95em;margin-bottom:12px'>"
        "FlowBD-V1 方法演化追踪案例</div>",
        unsafe_allow_html=True,
    )

    # ---- 数据加载 ----
    try:
        data = load_lineage_v2()
    except Exception as e:
        st.error(f"lineage_mvp v2 数据加载失败: {e}")
        return

    methods_df = data["methods_df"]
    edges_conf_df = data["edges_confirmed_df"]

    # ---- 一行指标 (spec 三·2) ----
    n_nodes = len(methods_df)
    n_conf = len(edges_conf_df)
    y_min = int(methods_df["year"].min())
    y_max = int(methods_df["year"].max())
    n_branch = methods_df["branch"].nunique()
    st.markdown(
        f'<div style="display:inline-block;padding:8px 16px;'
        f'background:{PAL["surface_2"]};border:1px solid {PAL["line"]};'
        f'border-radius:8px;font-size:14px;'
        f'color:{PAL["ink"]};margin-bottom:10px">'
        f'<b>{n_nodes}</b> 个方法节点 · '
        f'<b>{n_conf}</b> 条 confirmed 关系 · '
        f'<b>{y_min}—{y_max}</b> · '
        f'<b>{n_branch}</b> 个技术分支'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ---- 主视图: 地铁图 + 详情抽屉 (7:3) ----
    col_map, col_drawer = st.columns([7, 3])

    with col_map:
        # 记住上一次选中 (session_state)
        picked = st.session_state.get("_lineage_picked", None)
        tab_dag, tab_metro = st.tabs(["  年份谱系图 (纵轴 DAG)", "  地铁时间轴"])
        with tab_dag:
            render_lineage_dag(methods_df, edges_conf_df)
        with tab_metro:
            fig = render_metro_figure(methods_df, edges_conf_df, highlight_id=picked)
            st.pyplot(fig, use_container_width=True)

            # 导出按钮 (spec 三·7)
            exp_cols = st.columns(2)
            with exp_cols[0]:
                buf = io.BytesIO()
                fig.savefig(buf, format="png", dpi=180,
                            bbox_inches="tight", facecolor=PAL["surface"])
                st.download_button(
                    "⬇ 导出 PNG",
                    buf.getvalue(),
                    file_name="lineage_metro_v3.png",
                    mime="image/png",
                    use_container_width=True,
                )
            with exp_cols[1]:
                csv_bytes = methods_df.drop(
                    columns=["evidence_sentence_ids_parsed"],
                    errors="ignore"
                ).to_csv(index=False).encode("utf-8-sig")
                st.download_button(
                    "⬇ 导出 CSV (节点表)",
                    csv_bytes,
                    file_name="lineage_methods_normalized_v2.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
            plt.close(fig)
        render_legend_oneliner()

    with col_drawer:
        selected = render_detail_drawer(methods_df, edges_conf_df, picked)
        if selected != picked:
            st.session_state["_lineage_picked"] = selected

    # ---- 审计记录 ----
    st.markdown("---")
    render_audit_records()

    # ---- 底部可选面板 ----
    render_panorama_fold()
    render_dev_experimental_fold()


if __name__ == "__main__":
    main()
