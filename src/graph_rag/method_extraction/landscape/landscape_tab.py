"""
landscape_tab.py — 储能方法演化版图 (Stage C, Streamlit + ECharts, Atlas 风格)

实现: streamlit.components.v1.html 直嵌 ECharts CDN (不依赖 streamlit-echarts).
用笛卡尔坐标系 (cartesian2d) 承载: 凸包晕染 + 边 + 散点 + landmark + 簇标签,
全部随缩放/平移联动.

==================== 怎么跑 ====================
1. 不需要装额外包 (streamlit/neo4j 已装; ECharts 走浏览器 CDN; scipy 阶段B已装)
2. 确认 Neo4j 在跑 (bolt://localhost:7687, neo4j/neo4j123), 阶段B数据已写入
3. 启动 (端口自己挑一个没被占的):
     streamlit run src/graph_rag/method_extraction/landscape/landscape_tab.py --server.port 8520
4. 浏览器开 http://localhost:8520

==================== 环境变量 (可选) ====================
   NEO4J_URI / NEO4J_USER / NEO4J_PWD  (默认 bolt://localhost:7687 / neo4j / neo4j123)

==================== 常见问题 ====================
- 图空白: a) 浏览器连不上 ECharts CDN -> 联网或换本地 echarts.min.js;
          b) Neo4j 没数据 -> 重跑 write_neo4j_final.py
- 端口被占: --server.port 换个数字
- 中文乱码: ECharts 用浏览器字体, 一般正常
==================================================
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if THIS_DIR not in sys.path:
    sys.path.insert(0, THIS_DIR)

import streamlit as st
import streamlit.components.v1 as components

from atlas_data import compute_atlas

ECHARTS_SRC = "https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"
EDGE_COLORS = {"EXTENDS": "#f58231", "IMPROVES": "#4363d8",
               "ADAPTS": "#3cb44b", "REPLACES": "#e6194B"}
NOISE_COLOR = "#cfcfcf"
PERIPHERAL_COLOR = "#8a8a8a"

# 年份连续色阶 (plasma: 早=深紫, 晚=亮黄)
YEAR_COLORS = ["#0d0887", "#46039f", "#7201a8", "#9c179e", "#bd3786",
               "#d8576b", "#ed7953", "#fb9f3a", "#fdca26", "#f0f921"]

# tooltip: 节点 vs 边
TOOLTIP_JS = """
function(p){
  var d = p.data || {};
  if (p.seriesName === 'edges'){
    return '<b>演化: ' + (d._rel||'') + '</b> ('+(d._conf||'')+')<br/>'
         + '<div style="max-width:340px;white-space:normal">' + (d._ev||'') + '</div>';
  }
  if (d._name === undefined) return '';
  var s = '<b>' + d._name + '</b><br/>';
  s += '聚类: ' + (d._clabel||'未归类') + '<br/>';
  if (d._sec) s += '细分: ' + d._sec + '<br/>';
  s += '年份: ' + (d._year||'?') + (d._lm ? '  <b>[landmark]</b>' : '') + '<br/>';
  if (d._inno) s += '<div style="max-width:340px;white-space:normal;color:#888">'
       + d._inno + '</div>';
  return s;
}
"""

# 凸包 custom series 的 renderItem
HULL_RENDER_JS = """
function(params, api){
  var h = __HULLS__[params.dataIndex];
  if(!h) return;
  var pts = h.points.map(function(pt){ return api.coord(pt); });
  var op = h.dim ? 0.04 : 0.16;
  return {
    type: 'polygon',
    shape: { points: pts },
    style: { fill: h.color, opacity: op, stroke: h.color, lineWidth: 1 },
    z: 1, silent: true
  };
}
"""


@st.cache_data(show_spinner="从 Neo4j 计算版图...")
def load_atlas(include_peripheral: bool):
    return compute_atlas(include_peripheral=include_peripheral)


def _axis_range(nodes):
    xs = [n["x"] for n in nodes]; ys = [n["y"] for n in nodes]
    padx = (max(xs) - min(xs)) * 0.05; pady = (max(ys) - min(ys)) * 0.05
    return (min(xs) - padx, max(xs) + padx, min(ys) - pady, max(ys) + pady)


def _stable_jitter(key: str, lo: float, hi: float) -> float:
    """对同一 key 返回稳定的伪随机值, 保证多次 rerun 布局不抖动."""
    h = int(hashlib.md5(key.encode("utf-8")).hexdigest()[:8], 16)
    return lo + (h % 100000) / 100000.0 * (hi - lo)


def _evolution_layout(atlas):
    """按'演化代际'(方法进化进度)给节点分簇并布局.

    代际定义: 演化有向图里 source 衍生自 target (source 更新, target 更早/源头).
      - 无出边(不衍生自任何方法) => 第0代·起源
      - 衍生自前人 => 代际 = max(各 target 代际) + 1
    仅保留有演化边的节点 (孤立方法丢弃); 每个代际聚成一个圆形 blob, 左(早)→右(新).
    节点最终用'年份'上色, 故 blob 内颜色是杂的 (此函数只管布局, 不定色).

    返回 pos, gen_of, gen_labels, hull_payload
    """
    import numpy as np

    edges = atlas["edges"]; id2 = atlas["id2node"]

    out_adj: dict[str, list] = {}
    incident: set[str] = set()
    for e in edges:
        s, t = e["source"], e["target"]
        if s not in id2 or t not in id2:
            continue
        out_adj.setdefault(s, []).append(t)
        incident.add(s); incident.add(t)

    gen_cache: dict[str, int] = {}

    def gen(nid, stack):
        if nid in gen_cache:
            return gen_cache[nid]
        outs = out_adj.get(nid, [])
        if not outs:
            gen_cache[nid] = 0
            return 0
        best = 0
        for t in outs:
            if t in stack:        # 防环
                continue
            best = max(best, gen(t, stack | {nid}) + 1)
        gen_cache[nid] = best
        return best

    gen_of = {nid: gen(nid, set()) for nid in incident}

    groups: dict[int, list] = {}
    for nid, g in gen_of.items():
        groups.setdefault(g, []).append(nid)
    max_gen = max(groups) if groups else 0

    # 团半径随节点数自适应 (sqrt 缩放, 截断), 按累计间距左→右排开
    radii = {g: max(4.0, min(14.0, 1.6 * (len(m) ** 0.5))) for g, m in groups.items()}
    GAP = 7.0
    cy = 0.0
    pos, gen_labels, hull_payload = {}, [], []
    xcur = 0.0
    for g in range(max_gen + 1):
        members = groups.get(g, [])
        if not members:
            continue
        Rg = radii[g]
        cx = xcur + Rg
        xcur = cx + Rg + GAP
        pts = []
        for nid in members:
            r = Rg * (_stable_jitter(nid, 0.0, 1.0) ** 0.5)   # sqrt → 均匀填充圆面
            th = _stable_jitter(nid + "_t", 0.0, 6.28318)
            x = cx + r * float(np.cos(th)); y = cy + r * float(np.sin(th))
            pos[nid] = [x, y]
            pts.append([x, y])
        lbl = "第0代·起源" if g == 0 else f"第{g}代"
        gen_labels.append({
            "center": [cx, cy + Rg + 1.8],
            "label": f"{lbl} ({len(members)})", "color": "#888",
        })
        if len(pts) >= 3:
            try:
                from scipy.spatial import ConvexHull
                arr = np.array(pts)
                hull = ConvexHull(arr)
                hull_payload.append({
                    "points": [[float(arr[v, 0]), float(arr[v, 1])] for v in hull.vertices],
                    "color": "#9aa0a6",   # 中性灰晕染, 不抢节点的年份配色
                })
            except Exception:
                pass
    return pos, gen_of, gen_labels, hull_payload


def _edge_series(atlas, edge_strategy: str, pos=None):
    """pos 为 None 时用 UMAP 坐标 (聚类视图); 否则用时间轴坐标 (年份视图)."""
    edges = atlas["edges"]; id2 = atlas["id2node"]; prec = atlas["precision_keys"]
    data = []
    for e in edges:
        if edge_strategy == "精选" and (e["source"], e["target"], e["relation"]) not in prec:
            continue
        s = id2.get(e["source"]); t = id2.get(e["target"])
        if not s or not t:
            continue
        if pos is not None:
            sc = pos.get(e["source"]); tc = pos.get(e["target"])
            if not sc or not tc:
                continue
        else:
            sc = [s["x"], s["y"]]; tc = [t["x"], t["y"]]
        data.append({
            "coords": [sc, tc],
            "lineStyle": {"color": EDGE_COLORS.get(e["relation"], "#aaa"),
                          "opacity": 0.4, "width": 1, "curveness": 0.1},
            "_rel": e["relation"], "_conf": e["confidence"], "_ev": e["evidence"][:200],
        })
    return {
        "name": "edges", "type": "lines", "coordinateSystem": "cartesian2d",
        "data": data, "z": 2, "symbol": ["none", "arrow"], "symbolSize": 5,
        "tooltip": {"show": True},
    }


def _node_series(atlas, mode: str, show_landmarks: bool, pos=None, highlight_ids=None):
    """返回多个 scatter series: noise / cluster / landmark / cluster-label.

    landmark 名字默认不显示, 仅悬停 (emphasis) 时弹出, 避免黑框遮挡.
    年份视图 (mode=='year') 用 pos 时间轴坐标, 且不画主题簇标签 (改由 X 轴年份刻度承担).
    highlight_ids 为 None 时行为不变 (独立页面); 非 None 时命中节点高亮, 其余淡化 (问答联动).
    """
    nodes = atlas["nodes"]; cof = atlas["cluster_of"]
    lm = atlas["landmark_ids"]; colors = atlas["cluster_colors"]
    clusters = atlas["clusters"]; centroids = atlas["centroids"]
    hl_active = highlight_ids is not None

    # 悬停才显示的名字标签 (浅色, 不遮挡)
    hover_label = {
        "show": True, "fontSize": 11, "color": "#222",
        "backgroundColor": "rgba(255,255,255,0.92)",
        "borderColor": "#999", "borderWidth": 1,
        "padding": [3, 5], "borderRadius": 3, "position": "top",
    }

    noise_data, cluster_data, lm_data = [], [], []
    for n in nodes:
        cid = cof[n["id"]]
        is_lm = n["id"] in lm and show_landmarks
        peripheral = n["peripheral"]
        hit = hl_active and (n["id"] in highlight_ids)
        dim = hl_active and not hit
        base = {
            "_name": n["name"], "_clabel": n["cluster_label"],
            "_sec": n["secondary_topic"], "_year": n["year"],
            "_inno": (n["innovation"] or "")[:120], "_lm": (n["id"] in lm),
        }
        if mode == "year":
            p = pos.get(n["id"], [0, 0]) if pos else [n["x"], n["y"]]
            val = [p[0], p[1], n["year"] if n["year"] else None]
        else:
            val = [n["x"], n["y"]]
        emph = {"label": {**hover_label, "formatter": n["name"][:24]}}

        if is_lm:
            if dim:
                item = {**base, "value": val, "symbol": "pin", "symbolSize": 12,
                        "itemStyle": {"color": "#d9d9d9", "opacity": 0.2,
                                      "borderColor": "#fff", "borderWidth": 1},
                        "label": {"show": False}, "emphasis": emph}
            else:
                item = {**base, "value": val, "symbol": "diamond" if peripheral else "pin",
                        "symbolSize": 24 if hit else 20,
                        "itemStyle": {"color": "#111" if mode == "cluster" else None,
                                      "borderColor": "#fff", "borderWidth": 1},
                        "label": {"show": False}, "emphasis": emph}
            lm_data.append(item)
        elif peripheral:
            it = ({"color": "#dcdcdc", "opacity": 0.12} if dim
                  else {"color": PERIPHERAL_COLOR, "opacity": 0.7})
            noise_data.append({**base, "value": val, "symbol": "diamond",
                               "symbolSize": 6, "itemStyle": it, "emphasis": emph})
        elif cid < 0:
            it = ({"color": "#dcdcdc", "opacity": 0.12} if dim
                  else {"color": NOISE_COLOR, "opacity": 0.4})
            noise_data.append({**base, "value": val, "symbolSize": 5,
                               "itemStyle": it, "emphasis": emph})
        else:
            color = colors.get(cid, NOISE_COLOR)
            sz = 11 if n["kind"] == "own" else 8
            if dim:
                it = {"color": "#dcdcdc", "opacity": 0.12}
            else:
                it = {"opacity": 0.95 if hl_active else 0.85}
                if mode == "cluster":
                    it["color"] = color
                if hit:
                    sz += 4; it["borderColor"] = "#fff"; it["borderWidth"] = 1
            cluster_data.append({**base, "value": val, "symbolSize": sz,
                                 "itemStyle": it, "emphasis": emph})

    # 主题簇标签 (中位数处, 隐形点 + label) — 仅聚类视图; 年份视图用 X 轴年份刻度
    # 高亮模式下: 只有命中节点所在的大陆标签鲜亮, 其余标签淡化
    label_data = []
    if mode == "cluster":
        active_cids = None
        if hl_active:
            active_cids = {cof[i] for i in highlight_ids if i in cof and cof[i] >= 0}
        for cid, c in clusters.items():
            cx, cy = centroids.get(cid, [0, 0])
            is_active = active_cids is None or cid in active_cids
            if is_active:
                lbl = {"show": True, "formatter": c["label"], "fontSize": 14,
                       "fontWeight": "bold", "color": "#222",
                       "backgroundColor": "rgba(255,255,255,0.72)",
                       "borderColor": c["color"], "borderWidth": 2,
                       "padding": [4, 7], "borderRadius": 5}
            else:
                lbl = {"show": True, "formatter": c["label"], "fontSize": 11,
                       "fontWeight": "normal", "color": "#9aa0a6",
                       "backgroundColor": "rgba(255,255,255,0.25)",
                       "borderColor": "#cccccc", "borderWidth": 1,
                       "padding": [2, 5], "borderRadius": 4}
            label_data.append({"value": [cx, cy], "symbolSize": 0, "label": lbl, "_name": None})

    series = []
    series.append({"name": "noise", "type": "scatter", "coordinateSystem": "cartesian2d",
                   "data": noise_data, "z": 3, "tooltip": {"show": True}})
    series.append({"name": "cluster", "type": "scatter", "coordinateSystem": "cartesian2d",
                   "data": cluster_data, "z": 4, "tooltip": {"show": True}})
    if show_landmarks:
        series.append({"name": "landmark", "type": "scatter", "coordinateSystem": "cartesian2d",
                       "data": lm_data, "z": 6, "tooltip": {"show": True},
                       "labelLayout": {"hideOverlap": True}})  # 缩放时自动避让重叠标签
    series.append({"name": "clabel", "type": "scatter", "coordinateSystem": "cartesian2d",
                   "data": label_data, "z": 8, "silent": True, "tooltip": {"show": False}})
    return series


def _evo_node_series(atlas, show_landmarks, pos):
    """演化代际视图的节点系列: 颜色由 visualMap 按'年份'连续上色 (此处不设固定 color);
    landmark 名字仅悬停显示. 只画 pos 里的节点 (在演化链上的)."""
    nodes = atlas["nodes"]; lm = atlas["landmark_ids"]
    hover_label = {
        "show": True, "fontSize": 11, "color": "#222",
        "backgroundColor": "rgba(255,255,255,0.92)",
        "borderColor": "#999", "borderWidth": 1,
        "padding": [3, 5], "borderRadius": 3, "position": "top",
    }
    node_data, lm_data = [], []
    for n in nodes:
        nid = n["id"]
        if nid not in pos:
            continue
        base = {
            "_name": n["name"], "_clabel": n["cluster_label"],
            "_sec": n["secondary_topic"], "_year": n["year"],
            "_inno": (n["innovation"] or "")[:120], "_lm": (nid in lm),
        }
        # value[2] = 年份, 供 visualMap 上色
        val = [pos[nid][0], pos[nid][1], n["year"] if n["year"] else None]
        emph = {"label": {**hover_label, "formatter": n["name"][:24]}}
        if nid in lm and show_landmarks:
            lm_data.append({**base, "value": val, "symbol": "pin", "symbolSize": 20,
                            "itemStyle": {"borderColor": "#fff", "borderWidth": 1},
                            "label": {"show": False}, "emphasis": emph})
        else:
            sz = 11 if n["kind"] == "own" else 8
            node_data.append({**base, "value": val, "symbolSize": sz,
                              "itemStyle": {"opacity": 0.9}, "emphasis": emph})

    series = [{"name": "evonodes", "type": "scatter", "coordinateSystem": "cartesian2d",
               "data": node_data, "z": 4, "tooltip": {"show": True}}]
    if show_landmarks:
        series.append({"name": "landmark", "type": "scatter", "coordinateSystem": "cartesian2d",
                       "data": lm_data, "z": 6, "tooltip": {"show": True},
                       "labelLayout": {"hideOverlap": True}})
    return series


def _stage_label_series(stage_labels):
    """各团顶部的阶段标签 (隐形点 + label)."""
    data = []
    for s in stage_labels:
        data.append({
            "value": s["center"], "symbolSize": 0,
            "label": {"show": True, "formatter": s["label"], "fontSize": 15,
                      "fontWeight": "bold", "color": "#222",
                      "backgroundColor": "rgba(255,255,255,0.80)",
                      "borderColor": s["color"], "borderWidth": 2,
                      "padding": [4, 8], "borderRadius": 5},
            "_name": None,
        })
    return {"name": "stagelabel", "type": "scatter", "coordinateSystem": "cartesian2d",
            "data": data, "z": 8, "silent": True, "tooltip": {"show": False}}


def _base_option(x0, x1, y0, y1, series):
    return {
        "tooltip": {"trigger": "item", "confine": True, "enterable": True},
        "animation": False,
        "xAxis": {"type": "value", "show": False, "min": x0, "max": x1, "scale": True},
        "yAxis": {"type": "value", "show": False, "min": y0, "max": y1, "scale": True},
        "grid": {"left": 10, "right": 10, "top": 30, "bottom": 10},
        "dataZoom": [
            {"type": "inside", "xAxisIndex": 0, "filterMode": "none"},
            {"type": "inside", "yAxisIndex": 0, "filterMode": "none"},
        ],
        "series": series,
    }


def _build_option(atlas, mode, show_halos, show_landmarks, edge_strategy, highlight_ids=None):
    if mode == "year":
        # 演化代际视图: 按方法进化进度(代际)分团, 节点按年份连续上色 (团内杂色)
        pos, gen_of, gen_labels, hull_payload = _evolution_layout(atlas)
        series = []
        if show_halos and hull_payload:
            series.append({
                "name": "hulls", "type": "custom", "coordinateSystem": "cartesian2d",
                "data": [[i] for i in range(len(hull_payload))], "z": 1, "silent": True,
            })
        series.append(_edge_series(atlas, edge_strategy, pos))
        series.extend(_evo_node_series(atlas, show_landmarks, pos))
        series.append(_stage_label_series(gen_labels))

        if not pos:
            return _base_option(-1, 1, -1, 1, series), hull_payload

        xs = [p[0] for p in pos.values()]; ys = [p[1] for p in pos.values()]
        padx = (max(xs) - min(xs)) * 0.06 + 2; pady = (max(ys) - min(ys)) * 0.12 + 2
        x0, x1 = min(xs) - padx, max(xs) + padx
        y0, y1 = min(ys) - pady, max(ys) + pady
        option = {
            "tooltip": {"trigger": "item", "confine": True, "enterable": True},
            "animation": False,
            "xAxis": {"type": "value", "show": False, "min": x0, "max": x1, "scale": True},
            "yAxis": {"type": "value", "show": False, "min": y0, "max": y1, "scale": True},
            "grid": {"left": 10, "right": 10, "top": 30, "bottom": 60},
            "dataZoom": [
                {"type": "inside", "xAxisIndex": 0, "filterMode": "none"},
                {"type": "inside", "yAxisIndex": 0, "filterMode": "none"},
            ],
            "series": series,
        }
        # 年份连续色阶 + 底部色条
        yrs = [atlas["id2node"][nid]["year"] for nid in pos if atlas["id2node"][nid].get("year")]
        ymin, ymax = (min(yrs), max(yrs)) if yrs else (2008, 2025)
        vm_idx = [i for i, s in enumerate(series) if s["name"] in ("evonodes", "landmark")]
        option["visualMap"] = {
            "type": "continuous", "min": ymin, "max": ymax, "dimension": 2,
            "seriesIndex": vm_idx, "calculable": True,
            "orient": "horizontal", "left": "center", "bottom": 12,
            "itemWidth": 14, "itemHeight": 180, "text": [str(ymax), str(ymin)],
            "textStyle": {"color": "#555"}, "inRange": {"color": YEAR_COLORS},
        }
        return option, hull_payload

    # 聚类视图 (原样)
    series = []
    hull_payload = []
    active_cids = None
    if highlight_ids is not None:
        cof = atlas["cluster_of"]
        active_cids = {cof[i] for i in highlight_ids if i in cof and cof[i] >= 0}
    if show_halos:
        for cid, pts in atlas["hulls"].items():
            col = atlas["cluster_colors"].get(cid, "#ccc")
            dim = active_cids is not None and cid not in active_cids
            hull_payload.append({"points": pts, "color": ("#d0d0d0" if dim else col),
                                 "dim": bool(dim)})
        series.append({
            "name": "hulls", "type": "custom", "coordinateSystem": "cartesian2d",
            "data": [[i] for i in range(len(hull_payload))], "z": 1, "silent": True,
        })
    series.append(_edge_series(atlas, edge_strategy))
    series.extend(_node_series(atlas, mode, show_landmarks, highlight_ids=highlight_ids))
    x0, x1, y0, y1 = _axis_range(atlas["nodes"])
    return _base_option(x0, x1, y0, y1, series), hull_payload


def _render(atlas, mode, show_halos, show_landmarks, edge_strategy, height, key, highlight_ids=None):
    option, hull_payload = _build_option(atlas, mode, show_halos, show_landmarks,
                                         edge_strategy, highlight_ids=highlight_ids)
    option_json = json.dumps(option, ensure_ascii=False)
    hulls_json = json.dumps(hull_payload, ensure_ascii=False)
    hull_render = HULL_RENDER_JS.replace("__HULLS__", "HULLS_" + key)
    html = f"""
    <div id="{key}" style="width:100%;height:{height}px;"></div>
    <script src="{ECHARTS_SRC}"></script>
    <script>
      (function(){{
        var el = document.getElementById("{key}");
        if(!window.echarts){{ el.innerHTML="<p style='color:red'>ECharts CDN 加载失败</p>"; return; }}
        var HULLS_{key} = {hulls_json};
        var chart = echarts.init(el);
        var option = {option_json};
        option.tooltip.formatter = {TOOLTIP_JS};
        // 给 custom hull series 挂 renderItem
        for (var i=0;i<option.series.length;i++){{
          if(option.series[i].name === 'hulls'){{ option.series[i].renderItem = {hull_render}; }}
          if(option.series[i].name === 'edges'){{ option.series[i].tooltip = {{formatter: {TOOLTIP_JS}}}; }}
        }}
        chart.setOption(option);
        window.addEventListener('resize', function(){{ chart.resize(); }});
      }})();
    </script>
    """
    components.html(html, height=height + 10, scrolling=False)


# ==================== 问答联动: 问题向量 → 命中方法节点 ====================

EMB_PKL = os.path.join(THIS_DIR, "embeddings_v2.pkl")


@st.cache_resource(show_spinner=False)
def _match_index():
    """加载方法 bge-m3 向量索引 (与 Neo4j 节点 id 对齐). 返回 (归一化向量矩阵, id列表)."""
    import pickle
    import numpy as np

    with open(EMB_PKL, "rb") as f:
        d = pickle.load(f)
    kept = d["kept"]
    emb = np.asarray(d["embeddings"], dtype=np.float32)
    # 防御性归一化 (embed_methods 已归一, 这里再保证一次)
    norms = np.linalg.norm(emb, axis=1, keepdims=True)
    emb = emb / np.clip(norms, 1e-9, None)
    ids = [f"{m['paper_id']}::{m['name']}" for m in kept]
    return emb, ids


def match_nodes(query_vec, top_k: int = 30, min_sim: float = 0.30):
    """问题向量 → Top-K 命中方法节点 id (cosine). query_vec: list/np.ndarray (bge-m3, 1024维)."""
    import numpy as np

    emb, ids = _match_index()
    q = np.asarray(query_vec, dtype=np.float32).reshape(-1)
    if q.shape[0] != emb.shape[1]:
        return [], []
    q = q / max(float(np.linalg.norm(q)), 1e-9)
    sims = emb @ q
    order = np.argsort(-sims)[:top_k]
    hits = [(ids[i], float(sims[i])) for i in order if sims[i] >= min_sim]
    return [h[0] for h in hits], [h[1] for h in hits]


def render_atlas_panel(highlight_ids=None, height: int = 560, key: str = "qa_atlas",
                       include_peripheral: bool = False, show_landmarks: bool = True,
                       show_halos: bool = True, edge_strategy: str = "精选"):
    """供问答前端 (app.py) 嵌入: 渲染"按聚类"语义大陆, 可传 highlight_ids 高亮相关节点.

    不含 set_page_config / sidebar, 只画图本身.
    """
    atlas = load_atlas(include_peripheral)
    hl = set(highlight_ids) if highlight_ids else None
    _render(atlas, "cluster", show_halos, show_landmarks, edge_strategy, height, key,
            highlight_ids=hl)


def render_landscape():
    st.set_page_config(page_title="方法演化版图", layout="wide")
    st.title("储能方法演化版图")

    with st.sidebar:
        st.header("视图控制")
        view = st.radio("配色方案", ["按聚类", "按演化进度", "双视图并排"], index=0)
        show_landmarks = st.checkbox("高亮 landmark", value=True)
        show_halos = st.checkbox("显示大陆晕染", value=True)
        edge_strategy = st.radio("边显示策略", ["精选", "全部"], index=0,
                                 help="精选=真大陆桥+landmark高置信边(~113); 全部=1042")
        include_peri = st.checkbox("显示 peripheral (超疏水)", value=False)

    atlas = load_atlas(include_peri)
    n_edges_all = len(atlas["edges"])
    n_edges_prec = len(atlas["precision_keys"])

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("方法节点", len(atlas["nodes"]))
    c2.metric("演化边", f"{n_edges_prec if edge_strategy=='精选' else n_edges_all}")
    c3.metric("主聚类", len(atlas["clusters"]))
    c4.metric("landmark", len(atlas["landmark_ids"]))

    with st.expander("图例: 主簇 / 演化进度 / 边色", expanded=False):
        st.markdown("**主题聚类 (按聚类视图)**", unsafe_allow_html=True)
        for cid, c in atlas["clusters"].items():
            st.markdown(f"<span style='color:{c['color']};font-size:18px'>●</span> "
                        f"**C{cid}** {c['label']} ({c['size']})", unsafe_allow_html=True)
        st.markdown("---")
        st.markdown("**演化进度 (按演化进度视图)**: 按方法进化代际分团 (第0代·起源 → 第1/2…代), "
                    "团内节点按**年份**连续上色 (深紫=早, 亮黄=晚), 故同一团颜色不统一. "
                    "仅显示在演化链上的方法 (孤立方法不画).", unsafe_allow_html=True)
        st.markdown("---")
        st.markdown("边色: <span style='color:#f58231'>橙 EXTENDS</span> · "
                    "<span style='color:#4363d8'>蓝 IMPROVES</span> · "
                    "<span style='color:#3cb44b'>绿 ADAPTS</span> · "
                    "<span style='color:#e6194B'>红 REPLACES</span>", unsafe_allow_html=True)

    if view == "双视图并排":
        a, b = st.columns(2)
        with a:
            st.caption("按主题聚类")
            _render(atlas, "cluster", show_halos, show_landmarks, edge_strategy, 600, "viewC")
        with b:
            st.caption("按演化进度 (代际分团, 节点按年份上色, 团内杂色)")
            _render(atlas, "year", show_halos, show_landmarks, edge_strategy, 600, "viewY")
        st.caption("注: 左图按主题聚类, 右图按演化代际重新分团 (节点按年份上色); 两图独立")
    elif view == "按演化进度":
        _render(atlas, "year", show_halos, show_landmarks, edge_strategy, 760, "yearOnly")
    else:
        _render(atlas, "cluster", show_halos, show_landmarks, edge_strategy, 760, "clusterOnly")

    st.caption("操作: 滚轮缩放 / 拖拽平移 / 悬停节点或边看详情. landmark=pin 标记 (悬停显示名字).")


if __name__ == "__main__":
    render_landscape()
