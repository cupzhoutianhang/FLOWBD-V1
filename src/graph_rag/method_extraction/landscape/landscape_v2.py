"""
landscape_v2.py — 储能方法演化版图 (V2)

改造点(相对 landscape_tab.py):
  - 默认视图从"聚类岛屿"改为"时间轴泳道 + 地铁线路式演化图"
  - 顶部 tab 切换: [时间演化 / 语义聚类]
  - 时间演化: 横轴 2005-2026, 纵轴按 cluster_label 分泳道, 只显示 landmark + confirmed 关系节点
  - 语义聚类: 保留原来的 UMAP + 聚类岛屿 (改名"语义聚类视图")
  - 严格数据边界: 无年份节点默认隐藏; 不根据年份/相似度自动画边; candidate 不计入 confirmed

依赖:
  - atlas_data.compute_atlas() 拉取 Neo4j 中已存在的方法节点/边 (只读)
  - 不调用 LLM API, 不写数据库

启动:
  streamlit run src/graph_rag/method_extraction/landscape/landscape_v2.py --server.port 8512
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from collections import defaultdict

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if THIS_DIR not in sys.path:
    sys.path.insert(0, THIS_DIR)

import streamlit as st
import streamlit.components.v1 as components

from atlas_data import compute_atlas

# ==================== 常量 ====================
ECHARTS_SRC = "https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"

# 用户指定的边配色(与 V1 不同): EXTENDS 蓝, IMPROVES 绿, ADAPTS 橙, REPLACES 红
EDGE_COLORS_V2 = {
    "EXTENDS":  "#2E7CF6",   # 蓝
    "IMPROVES": "#22C55E",   # 绿
    "ADAPTS":   "#F59E0B",   # 橙
    "REPLACES": "#EF4444",   # 红
}
REL_LABEL_CN = {"EXTENDS": "继承", "IMPROVES": "改进", "ADAPTS": "适配", "REPLACES": "替代"}

# own vs referenced 填充色
KIND_FILL = {"own": "#1F4A8A", "referenced": "#E6F0FA"}
KIND_STROKE = {"own": "#0F2A55", "referenced": "#1F4A8A"}

YEAR_MIN, YEAR_MAX = 2005, 2026
DEFAULT_MAX_NODES = 80


# ==================== 数据加载 & 派生 ====================
@st.cache_data(show_spinner="从 Neo4j 拉取版图数据 (只读)...")
def load_atlas_cached(include_peripheral: bool = False):
    return compute_atlas(include_peripheral=include_peripheral)


def _stable_jitter(key: str, lo: float, hi: float) -> float:
    h = int(hashlib.md5(key.encode("utf-8")).hexdigest()[:8], 16)
    return lo + (h % 100000) / 100000.0 * (hi - lo)


def _short_name(name: str, n: int = 14) -> str:
    if not name:
        return "?"
    return name if len(name) <= n else name[:n] + "…"


def derive_swimlanes(atlas):
    """按 cluster_label 生成泳道; 顺序按 cluster_id 稳定."""
    lanes = []
    for cid, c in sorted(atlas["clusters"].items()):
        lanes.append({
            "cid": cid,
            "label": c["label"],
            "color": c["color"],
            "size": c["size"],
        })
    return lanes


def confirmed_edges(atlas):
    """confirmed = confidence == 'high'; 用户明确要求不计入 candidate."""
    return [e for e in atlas["edges"] if e.get("confidence") == "high"]


def candidate_edges(atlas):
    return [e for e in atlas["edges"] if e.get("confidence") in ("medium", "low", "")]


def default_visible_nodes(atlas, max_nodes: int = DEFAULT_MAX_NODES):
    """默认可见: landmark ∪ confirmed 边端点; 上限 max_nodes."""
    keep = set(atlas["landmark_ids"])
    for e in confirmed_edges(atlas):
        keep.add(e["source"])
        keep.add(e["target"])
    # 只保留有年份的
    id2 = atlas["id2node"]
    keep_with_year = {i for i in keep if id2.get(i, {}).get("year")}
    if len(keep_with_year) <= max_nodes:
        return keep_with_year
    # 优先 landmark, 其次按 in-degree 排序
    indeg = defaultdict(int)
    for e in atlas["edges"]:
        indeg[e["target"]] += 1
    ranked = sorted(keep_with_year,
                    key=lambda i: (i not in atlas["landmark_ids"], -indeg.get(i, 0)))
    return set(ranked[:max_nodes])


def earliest_by_cluster(atlas, node_ids):
    """每泳道最早节点(星号标记). node_ids: 用于筛选可见节点."""
    id2 = atlas["id2node"]
    cof = atlas["cluster_of"]
    per = defaultdict(list)
    for i in node_ids:
        n = id2.get(i)
        if not n or not n.get("year"):
            continue
        cid = cof.get(i, -1)
        if cid < 0:
            continue
        per[cid].append((n["year"], i))
    return {cid: sorted(v)[0][1] for cid, v in per.items() if v}


# ==================== 时间演化视图 ECharts 选项 ====================

TOOLTIP_JS_TIME = """
function(p){
  var d = p.data || {};
  if (p.seriesName === '关系'){
    var rel = d._rel || '';
    var conf = d._conf || '';
    var ev = d._ev || '';
    return '<b>'+ rel +'</b> · '+ conf +
           (ev ? '<div style="max-width:340px;white-space:normal;color:#555;margin-top:4px">'+ ev +'</div>' : '');
  }
  if (d._name === undefined) return '';
  var star = d._earliest ? ' ★<span style="color:#B91C1C">最早</span>' : '';
  var lm = d._lm ? '  <span style="background:#111;color:#fff;padding:1px 5px;border-radius:3px;font-size:11px">landmark</span>' : '';
  var s = '<b>'+ d._name +'</b>'+ star + lm +'<br/>';
  s += '<span style="color:#666">领域:</span> '+ (d._clabel||'-') +'<br/>';
  if (d._sec) s += '<span style="color:#666">子领域:</span> '+ d._sec +'<br/>';
  s += '<span style="color:#666">年份:</span> '+ (d._year||'?') +'<br/>';
  s += '<span style="color:#666">来源:</span> '+ (d._kind==='own' ? '本文提出' : '引用/参考') +'<br/>';
  if (d._paper) s += '<span style="color:#666">论文:</span> '+ d._paper;
  return s;
}
"""


def build_time_evolution_option(atlas, filters):
    """构造 ECharts option (泳道时间轴).

    filters: {
      year_range: (a, b),
      rel_types: set of "EXTENDS"...,
      only_confirmed: bool,   # True 只画 confidence==high
      show_candidate: bool,   # True 时把 candidate 边画成虚线
      only_landmark: bool,    # True 只显示 landmark 节点
      show_all_nodes: bool,   # True 显示全部有年份节点 (含 non-landmark, non-confirmed 端点)
      focus_cluster_id: int|None,  # 展开某条主线时限定 cluster
      picked_clusters: set,   # 泳道过滤 (cluster_id)
      search: str,
    }
    """
    id2 = atlas["id2node"]
    cof = atlas["cluster_of"]
    lanes_all = derive_swimlanes(atlas)

    # 泳道过滤
    picked = filters.get("picked_clusters")
    if picked is not None and len(picked) > 0:
        lanes = [ln for ln in lanes_all if ln["cid"] in picked]
    else:
        lanes = lanes_all
    lane_cids = [ln["cid"] for ln in lanes]
    lane_of = {ln["cid"]: idx for idx, ln in enumerate(lanes)}
    n_lanes = max(1, len(lanes))

    # 默认可见节点集
    if filters.get("show_all_nodes"):
        base_ids = set(atlas["id2node"].keys())
    else:
        base_ids = default_visible_nodes(atlas, DEFAULT_MAX_NODES)

    if filters.get("only_landmark"):
        base_ids = base_ids & set(atlas["landmark_ids"])

    # 年份 & 搜索 & 泳道过滤
    y0, y1 = filters["year_range"]
    search = (filters.get("search") or "").strip().lower()

    def keep_node(nid):
        n = id2.get(nid)
        if not n:
            return False
        if not n.get("year"):
            return False   # 严格边界: 无年份节点不进图
        if not (y0 <= int(n["year"]) <= y1):
            return False
        cid = cof.get(nid, -1)
        if cid < 0:
            return False   # 噪声不放泳道
        if cid not in lane_of:
            return False
        if search and search not in (n["name"] or "").lower():
            return False
        return True

    visible_ids = {i for i in base_ids if keep_node(i)}

    # 每泳道每年做垂直偏移, 避免同点堆叠 (哈希 stable)
    def y_coord(nid):
        cid = cof[nid]
        lane_idx = lane_of[cid]
        base_y = (n_lanes - 1 - lane_idx)   # 让 lane_idx=0 在最上方
        j = _stable_jitter(nid, -0.32, 0.32)
        return base_y + j

    def x_coord(n):
        # 微小 x 抖动避免同年重叠 (最多 ±0.25 年)
        j = _stable_jitter(n["id"] + "_x", -0.25, 0.25)
        return float(n["year"]) + j

    earliest = earliest_by_cluster(atlas, visible_ids)

    # ---- 节点 series (own / referenced / landmark) ----
    own_data, ref_data, lm_data, star_data = [], [], [], []
    for nid in visible_ids:
        n = id2[nid]
        is_lm = nid in atlas["landmark_ids"]
        is_earliest = earliest.get(cof[nid]) == nid
        base = {
            "_name": n["name"],
            "_clabel": n["cluster_label"],
            "_sec": n["secondary_topic"],
            "_year": n["year"],
            "_kind": n["kind"],
            "_paper": n["paper_id"],
            "_lm": is_lm,
            "_earliest": is_earliest,
            "_id": nid,
        }
        val = [x_coord(n), y_coord(nid)]
        emph = {"label": {"show": True, "formatter": _short_name(n["name"]),
                          "backgroundColor": "rgba(255,255,255,0.95)",
                          "borderColor": "#666", "borderWidth": 1,
                          "padding": [3, 5], "color": "#111",
                          "borderRadius": 3, "position": "top"}}
        label = {"show": True, "formatter": _short_name(n["name"], 10),
                 "color": "#333", "fontSize": 10, "position": "top"} if is_lm else {"show": False}

        if is_lm:
            item = {**base, "value": val, "symbol": "pin",
                    "symbolSize": 22,
                    "itemStyle": {"color": KIND_FILL.get(n["kind"], "#1F4A8A"),
                                  "borderColor": "#fff", "borderWidth": 1.5},
                    "label": label, "emphasis": emph}
            lm_data.append(item)
        elif n["kind"] == "own":
            own_data.append({**base, "value": val, "symbol": "circle", "symbolSize": 10,
                             "itemStyle": {"color": KIND_FILL["own"], "opacity": 0.9,
                                           "borderColor": KIND_STROKE["own"], "borderWidth": 1},
                             "label": {"show": False}, "emphasis": emph})
        else:
            ref_data.append({**base, "value": val, "symbol": "circle", "symbolSize": 8,
                             "itemStyle": {"color": KIND_FILL["referenced"], "opacity": 0.95,
                                           "borderColor": KIND_STROKE["referenced"], "borderWidth": 1},
                             "label": {"show": False}, "emphasis": emph})

        if is_earliest:
            star_data.append({**base, "value": [val[0], val[1] + 0.18],
                              "symbol": "diamond",
                              "symbolSize": 14,
                              "itemStyle": {"color": "#B91C1C", "opacity": 0.9},
                              "label": {"show": True, "formatter": "★",
                                        "color": "#B91C1C", "fontSize": 14,
                                        "position": "inside"}})

    # ---- 边 series ----
    rel_filter = filters.get("rel_types") or set(EDGE_COLORS_V2.keys())
    edges_all = confirmed_edges(atlas)
    if filters.get("show_candidate"):
        cand = candidate_edges(atlas)
    else:
        cand = []

    def edge_item(e, is_confirmed):
        s, t = id2.get(e["source"]), id2.get(e["target"])
        if not s or not t:
            return None
        if e["source"] not in visible_ids or e["target"] not in visible_ids:
            return None
        # 时间箭头方向: 早 → 晚 (若 target 更早, 反转)
        s_year = s.get("year") or 0
        t_year = t.get("year") or 0
        if t_year < s_year:
            s, t = t, s
        sc = [x_coord(s), y_coord(s["id"])]
        tc = [x_coord(t), y_coord(t["id"])]
        col = EDGE_COLORS_V2.get(e["relation"], "#999")
        return {
            "coords": [sc, tc],
            "lineStyle": {
                "color": col,
                "opacity": 0.75 if is_confirmed else 0.35,
                "width": 1.8 if is_confirmed else 1,
                "curveness": 0.15,
                "type": "solid" if is_confirmed else "dashed",
            },
            "_rel": e["relation"],
            "_conf": "confirmed(高置信)" if is_confirmed else "candidate(候选)",
            "_ev": (e.get("evidence") or "")[:220],
        }

    edge_data = []
    for e in edges_all:
        if e["relation"] not in rel_filter:
            continue
        it = edge_item(e, True)
        if it:
            edge_data.append(it)
    for e in cand:
        if e["relation"] not in rel_filter:
            continue
        it = edge_item(e, False)
        if it:
            edge_data.append(it)

    # ---- 泳道背景条 & 标签 ----
    lane_bg_marks = []
    lane_label_data = []
    for idx, ln in enumerate(lanes):
        lane_top = (n_lanes - 1 - idx) + 0.48
        lane_bot = (n_lanes - 1 - idx) - 0.48
        band_color = ln["color"]
        lane_bg_marks.append({
            "type": "custom_band",
            "y0": lane_bot, "y1": lane_top,
            "color": band_color,
        })
        # 泳道左侧标签
        lane_label_data.append({
            "value": [YEAR_MIN - 0.6, (n_lanes - 1 - idx)],
            "symbolSize": 0,
            "label": {
                "show": True,
                "formatter": f"{ln['label']}\n({ln['size']})",
                "align": "right",
                "color": "#222",
                "fontSize": 12,
                "fontWeight": "bold",
                "backgroundColor": band_color,
                "borderColor": "#333",
                "borderWidth": 1,
                "padding": [4, 8],
                "borderRadius": 4,
                "position": "inside",
            },
            "_name": None,
        })

    series = [
        # 泳道背景 (custom polygon)
        {"name": "lanes", "type": "custom", "coordinateSystem": "cartesian2d",
         "data": [[i] for i in range(len(lane_bg_marks))], "z": 1, "silent": True},
        # 关系边
        {"name": "关系", "type": "lines", "coordinateSystem": "cartesian2d",
         "data": edge_data, "z": 3, "symbol": ["none", "arrow"], "symbolSize": 6,
         "tooltip": {"show": True}},
        # 引用节点
        {"name": "引用方法", "type": "scatter", "coordinateSystem": "cartesian2d",
         "data": ref_data, "z": 4, "tooltip": {"show": True}},
        # 本文提出节点
        {"name": "本文提出方法", "type": "scatter", "coordinateSystem": "cartesian2d",
         "data": own_data, "z": 5, "tooltip": {"show": True}},
        # landmark
        {"name": "landmark", "type": "scatter", "coordinateSystem": "cartesian2d",
         "data": lm_data, "z": 6, "tooltip": {"show": True},
         "labelLayout": {"hideOverlap": True}},
        # 最早标记 (★)
        {"name": "最早节点", "type": "scatter", "coordinateSystem": "cartesian2d",
         "data": star_data, "z": 7, "tooltip": {"show": True}},
        # 泳道左侧标签
        {"name": "泳道", "type": "scatter", "coordinateSystem": "cartesian2d",
         "data": lane_label_data, "z": 8, "silent": True,
         "tooltip": {"show": False}},
    ]

    # X 轴年份区间
    x0 = YEAR_MIN - 2.4   # 留出左侧泳道标签空间
    x1 = YEAR_MAX + 0.6

    option = {
        "tooltip": {"trigger": "item", "confine": True, "enterable": True,
                    "backgroundColor": "rgba(255,255,255,0.98)",
                    "borderColor": "#ccc", "borderWidth": 1,
                    "textStyle": {"color": "#111", "fontSize": 12}},
        "animation": False,
        "grid": {"left": 60, "right": 30, "top": 40, "bottom": 60},
        "xAxis": {
            "type": "value",
            "min": x0, "max": x1,
            "interval": 1,
            "axisLabel": {
                "color": "#333", "fontSize": 11,
                "formatter": "{value}",
            },
            "axisLine": {"lineStyle": {"color": "#888"}},
            "splitLine": {"show": True, "lineStyle": {"color": "#eee"}},
            "name": "年份", "nameLocation": "middle", "nameGap": 30,
            "nameTextStyle": {"color": "#555", "fontSize": 12},
        },
        "yAxis": {
            "type": "value",
            "min": -0.7, "max": n_lanes - 0.3,
            "show": False, "scale": True,
        },
        "dataZoom": [
            {"type": "inside", "xAxisIndex": 0, "filterMode": "none"},
            {"type": "slider", "xAxisIndex": 0, "height": 18,
             "bottom": 6, "showDetail": False, "brushSelect": False,
             "backgroundColor": "rgba(0,0,0,0.02)"},
        ],
        "series": series,
    }
    return option, lane_bg_marks, lanes


# ==================== 语义聚类视图 (V1 逻辑简化后复用) ====================

TOOLTIP_JS_CLUSTER = """
function(p){
  var d = p.data || {};
  if (p.seriesName === '关系'){
    return '<b>'+ (d._rel||'') +'</b> · '+ (d._conf||'') +
           (d._ev ? '<div style="max-width:340px;white-space:normal;margin-top:4px;color:#555">'+ d._ev +'</div>' : '');
  }
  if (d._name === undefined) return '';
  var lm = d._lm ? '  <span style="background:#111;color:#fff;padding:1px 5px;border-radius:3px;font-size:11px">landmark</span>' : '';
  var s = '<b>'+ d._name +'</b>'+ lm +'<br/>';
  s += '<span style="color:#666">领域:</span> '+ (d._clabel||'-') +'<br/>';
  if (d._sec) s += '<span style="color:#666">子领域:</span> '+ d._sec +'<br/>';
  s += '<span style="color:#666">年份:</span> '+ (d._year||'?') +'<br/>';
  if (d._paper) s += '<span style="color:#666">论文:</span> '+ d._paper;
  return s;
}
"""

HULL_RENDER_JS = """
function(params, api){
  var h = __HULLS__[params.dataIndex];
  if(!h) return;
  var pts = h.points.map(function(pt){ return api.coord(pt); });
  return {
    type: 'polygon',
    shape: { points: pts },
    style: { fill: h.color, opacity: 0.14, stroke: h.color, lineWidth: 1 },
    z: 1, silent: true
  };
}
"""

LANE_RENDER_JS = """
function(params, api){
  var b = __LANES__[params.dataIndex];
  if(!b) return;
  var xMin = api.coord([__XMIN__, b.y0]);
  var xMax = api.coord([__XMAX__, b.y1]);
  return {
    type: 'rect',
    shape: {
      x: xMin[0], y: xMax[1],
      width: xMax[0] - xMin[0],
      height: xMin[1] - xMax[1]
    },
    style: { fill: b.color, opacity: 0.08, stroke: b.color, lineWidth: 0 },
    z: 0, silent: true
  };
}
"""


def build_semantic_cluster_option(atlas, show_halos: bool, show_landmarks: bool,
                                   edge_strategy: str, rel_filter: set):
    """精简版语义聚类视图 (保留原视觉)."""
    nodes = atlas["nodes"]
    edges = atlas["edges"]
    cof = atlas["cluster_of"]
    colors = atlas["cluster_colors"]
    lm = atlas["landmark_ids"]
    prec = atlas["precision_keys"]

    # 凸包
    hull_payload = []
    if show_halos:
        for cid, pts in atlas["hulls"].items():
            hull_payload.append({"points": pts, "color": colors.get(cid, "#ccc")})

    # 边
    edge_data = []
    for e in edges:
        if e["relation"] not in rel_filter:
            continue
        if edge_strategy == "精选" and (e["source"], e["target"], e["relation"]) not in prec:
            continue
        s = atlas["id2node"].get(e["source"])
        t = atlas["id2node"].get(e["target"])
        if not s or not t:
            continue
        edge_data.append({
            "coords": [[s["x"], s["y"]], [t["x"], t["y"]]],
            "lineStyle": {"color": EDGE_COLORS_V2.get(e["relation"], "#999"),
                          "opacity": 0.5 if e.get("confidence") == "high" else 0.25,
                          "width": 1.4 if e.get("confidence") == "high" else 0.9,
                          "curveness": 0.1},
            "_rel": e["relation"], "_conf": e.get("confidence", ""),
            "_ev": (e.get("evidence") or "")[:200],
        })

    # 节点
    noise_data, cluster_data, lm_data = [], [], []
    for n in nodes:
        cid = cof[n["id"]]
        is_lm = n["id"] in lm and show_landmarks
        base = {
            "_name": n["name"], "_clabel": n["cluster_label"],
            "_sec": n["secondary_topic"], "_year": n["year"],
            "_lm": (n["id"] in lm), "_paper": n["paper_id"],
        }
        val = [n["x"], n["y"]]
        emph = {"label": {"show": True, "formatter": _short_name(n["name"], 22),
                          "backgroundColor": "rgba(255,255,255,0.95)",
                          "borderColor": "#666", "borderWidth": 1,
                          "padding": [3, 5], "color": "#111", "borderRadius": 3}}
        if is_lm:
            lm_data.append({**base, "value": val, "symbol": "pin", "symbolSize": 20,
                            "itemStyle": {"color": "#111", "borderColor": "#fff", "borderWidth": 1},
                            "label": {"show": False}, "emphasis": emph})
        elif cid < 0:
            noise_data.append({**base, "value": val, "symbolSize": 5,
                               "itemStyle": {"color": "#cfcfcf", "opacity": 0.4},
                               "emphasis": emph})
        else:
            sz = 10 if n["kind"] == "own" else 7
            cluster_data.append({**base, "value": val, "symbolSize": sz,
                                 "itemStyle": {"color": colors.get(cid, "#999"),
                                               "opacity": 0.85},
                                 "emphasis": emph})

    # 簇标签
    label_data = []
    for cid, c in atlas["clusters"].items():
        cx, cy = atlas["centroids"].get(cid, [0, 0])
        label_data.append({
            "value": [cx, cy], "symbolSize": 0,
            "label": {"show": True, "formatter": c["label"], "fontSize": 13,
                      "fontWeight": "bold", "color": "#222",
                      "backgroundColor": "rgba(255,255,255,0.75)",
                      "borderColor": c["color"], "borderWidth": 2,
                      "padding": [3, 6], "borderRadius": 4},
            "_name": None,
        })

    series = []
    if show_halos:
        series.append({"name": "hulls", "type": "custom",
                       "coordinateSystem": "cartesian2d",
                       "data": [[i] for i in range(len(hull_payload))],
                       "z": 1, "silent": True})
    series.append({"name": "关系", "type": "lines",
                   "coordinateSystem": "cartesian2d",
                   "data": edge_data, "z": 2,
                   "symbol": ["none", "arrow"], "symbolSize": 5,
                   "tooltip": {"show": True}})
    series.append({"name": "noise", "type": "scatter",
                   "coordinateSystem": "cartesian2d",
                   "data": noise_data, "z": 3, "tooltip": {"show": True}})
    series.append({"name": "cluster", "type": "scatter",
                   "coordinateSystem": "cartesian2d",
                   "data": cluster_data, "z": 4, "tooltip": {"show": True}})
    if show_landmarks:
        series.append({"name": "landmark", "type": "scatter",
                       "coordinateSystem": "cartesian2d",
                       "data": lm_data, "z": 6, "tooltip": {"show": True},
                       "labelLayout": {"hideOverlap": True}})
    series.append({"name": "clabel", "type": "scatter",
                   "coordinateSystem": "cartesian2d",
                   "data": label_data, "z": 8, "silent": True,
                   "tooltip": {"show": False}})

    xs = [n["x"] for n in nodes]; ys = [n["y"] for n in nodes]
    padx = (max(xs) - min(xs)) * 0.05; pady = (max(ys) - min(ys)) * 0.05
    option = {
        "tooltip": {"trigger": "item", "confine": True, "enterable": True,
                    "backgroundColor": "rgba(255,255,255,0.98)",
                    "borderColor": "#ccc", "borderWidth": 1,
                    "textStyle": {"color": "#111", "fontSize": 12}},
        "animation": False,
        "xAxis": {"type": "value", "show": False, "scale": True,
                  "min": min(xs) - padx, "max": max(xs) + padx},
        "yAxis": {"type": "value", "show": False, "scale": True,
                  "min": min(ys) - pady, "max": max(ys) + pady},
        "grid": {"left": 10, "right": 10, "top": 30, "bottom": 10},
        "dataZoom": [
            {"type": "inside", "xAxisIndex": 0, "filterMode": "none"},
            {"type": "inside", "yAxisIndex": 0, "filterMode": "none"},
        ],
        "series": series,
    }
    return option, hull_payload


# ==================== 渲染函数 ====================

def render_echarts(option, hull_payload, lane_payload, key: str, height: int,
                    tooltip_js: str, x_min=None, x_max=None):
    option_json = json.dumps(option, ensure_ascii=False, default=str)
    hulls_json = json.dumps(hull_payload, ensure_ascii=False)
    lanes_json = json.dumps(lane_payload, ensure_ascii=False)
    hull_render = HULL_RENDER_JS.replace("__HULLS__", f"HULLS_{key}")
    lane_render = (LANE_RENDER_JS
                   .replace("__LANES__", f"LANES_{key}")
                   .replace("__XMIN__", str(x_min if x_min is not None else 0))
                   .replace("__XMAX__", str(x_max if x_max is not None else 1)))
    html = f"""
    <div id="{key}" style="width:100%;height:{height}px;background:#FAFAFB;
         border-radius:8px;border:1px solid #E5E7EB"></div>
    <script src="{ECHARTS_SRC}"></script>
    <script>
      (function(){{
        var el = document.getElementById("{key}");
        if(!window.echarts){{ el.innerHTML="<p style='color:red;padding:20px'>ECharts CDN 加载失败, 检查网络</p>"; return; }}
        var HULLS_{key} = {hulls_json};
        var LANES_{key} = {lanes_json};
        var chart = echarts.init(el);
        var option = {option_json};
        option.tooltip.formatter = {tooltip_js};
        for (var i=0;i<option.series.length;i++){{
          if(option.series[i].name === 'hulls'){{ option.series[i].renderItem = {hull_render}; }}
          if(option.series[i].name === 'lanes'){{ option.series[i].renderItem = {lane_render}; }}
          if(option.series[i].name === '关系'){{ option.series[i].tooltip = {{formatter: {tooltip_js}}}; }}
        }}
        chart.setOption(option);
        window.addEventListener('resize', function(){{ chart.resize(); }});
      }})();
    </script>
    """
    components.html(html, height=height + 12, scrolling=False)


# ==================== 详情面板 ====================

def build_details(atlas, nid: str):
    n = atlas["id2node"].get(nid)
    if not n:
        return None
    id2 = atlas["id2node"]
    cof = atlas["cluster_of"]

    predecessors, successors = [], []
    for e in atlas["edges"]:
        if e["confidence"] != "high":
            continue
        s_year = id2.get(e["source"], {}).get("year") or 0
        t_year = id2.get(e["target"], {}).get("year") or 0
        # 时间流向: 早→晚
        if s_year > t_year:
            src, tgt = e["target"], e["source"]
        else:
            src, tgt = e["source"], e["target"]
        if tgt == nid and src in id2:
            predecessors.append((src, e["relation"], (e.get("evidence") or "")[:180]))
        elif src == nid and tgt in id2:
            successors.append((tgt, e["relation"], (e.get("evidence") or "")[:180]))

    return {
        "name": n["name"],
        "canonical": n["name"],
        "author": "— (数据集未收录作者字段, 参见来源论文)",
        "year": n["year"],
        "year_source": ("Neo4j 属性 m.year (由抽取管线补全, 详见 backfill_publish_year.py)"
                        if n["year"] else "缺失"),
        "paper": n["paper_id"],
        "kind": "本文提出 (own)" if n["kind"] == "own" else "引用 / 参考 (referenced)",
        "cluster": n["cluster_label"],
        "cluster_id": cof.get(nid, -1),
        "secondary": n["secondary_topic"] or "-",
        "landmark": nid in atlas["landmark_ids"],
        "innovation": n["innovation"] or "-",
        "problem": n["problem_solved"] or "-",
        "predecessors": predecessors,
        "successors": successors,
    }


def render_details_panel(atlas, nid: str):
    d = build_details(atlas, nid)
    if not d:
        st.info("请从下拉框选择一个方法节点查看详情。")
        return

    lm_tag = " 🏛 **Landmark**" if d["landmark"] else ""
    st.markdown(f"### {d['name']}{lm_tag}")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"**Canonical name**: `{d['canonical']}`")
        st.markdown(f"**年份**: `{d['year'] or '—'}`")
        st.markdown(f"**年份来源**: {d['year_source']}")
        st.markdown(f"**来源类型**: {d['kind']}")
    with c2:
        st.markdown(f"**领域(泳道)**: {d['cluster']} · C{d['cluster_id']}")
        st.markdown(f"**技术子领域**: {d['secondary']}")
        st.markdown(f"**作者**: {d['author']}")
        st.markdown(f"**来源论文**: {d['paper']}")

    st.markdown("**创新点**"); st.write(d["innovation"])
    st.markdown("**解决的问题**"); st.write(d["problem"])

    ce1, ce2 = st.columns(2)
    with ce1:
        st.markdown("**前驱方法 (confirmed only)**")
        if d["predecessors"]:
            for sid, rel, ev in d["predecessors"]:
                nm = atlas["id2node"][sid]["name"]
                st.markdown(f"- **{REL_LABEL_CN.get(rel, rel)}** ← {nm}")
                if ev:
                    st.caption(f"证据: {ev}")
        else:
            st.caption("(无 confirmed 前驱)")

    with ce2:
        st.markdown("**后续方法 (confirmed only)**")
        if d["successors"]:
            for tid, rel, ev in d["successors"]:
                nm = atlas["id2node"][tid]["name"]
                st.markdown(f"- **{REL_LABEL_CN.get(rel, rel)}** → {nm}")
                if ev:
                    st.caption(f"证据: {ev}")
        else:
            st.caption("(无 confirmed 后续)")

    st.caption("说明: 原文 sentence-ID 字段当前数据抽取管线未落库; "
               "此处显示的\"证据(evidence)\"来自 Neo4j 边属性 r.evidence, "
               "如需 sentence-ID 需在方法抽取管线里补字段。")

    if d["cluster_id"] == 2:
        st.info("📚 **相变材料 MVP 谱系** — 此节点所在的\"石蜡基复合相变材料\"是当前"
                "V2 数据完整度最高的方法主线, 可作为完整谱系案例研究。")
    else:
        st.warning("⚠️ 当前 V2 只有石蜡基相变材料一条完整谱系 (cluster 2); "
                   "其他领域为无边时间点集, 尚未构建完整谱系。")


# ==================== 侧边栏控件 ====================

def sidebar_controls(atlas):
    lanes = derive_swimlanes(atlas)
    st.sidebar.markdown("### 🎛 视图控件")

    # 年份范围
    y_lo, y_hi = st.sidebar.slider(
        "年份范围", YEAR_MIN, YEAR_MAX, (YEAR_MIN, YEAR_MAX), 1,
        help="固定 2005-2026; 无年份节点默认不参与绘图。"
    )

    # 储能领域 (cluster 多选)
    lane_labels = [f"C{ln['cid']} · {ln['label']}" for ln in lanes]
    picked_labels = st.sidebar.multiselect(
        "储能领域 (泳道)", lane_labels, default=lane_labels,
        help="按 9 大方法聚类分泳道; 默认全选。"
    )
    picked_cids = {int(l.split("·")[0].strip()[1:]) for l in picked_labels}

    # 技术子领域 (secondary_topic)
    all_sub = sorted({n["secondary_topic"] for n in atlas["nodes"]
                      if n["secondary_topic"]})
    picked_sub = st.sidebar.multiselect(
        "技术子领域 (secondary_topic)", all_sub, default=[],
        help="留空 = 不过滤; 选择后仅显示命中子领域的节点。"
    )

    # 关系类型
    rel_types = st.sidebar.multiselect(
        "关系类型", list(EDGE_COLORS_V2.keys()),
        default=list(EDGE_COLORS_V2.keys()),
    )

    st.sidebar.markdown("---")
    only_lm = st.sidebar.checkbox("仅看 landmark", value=False)
    only_conf = st.sidebar.checkbox(
        "仅看 confirmed (confidence=high)", value=True,
        help="confirmed 实线; candidate 虚线; 默认不显示 candidate。"
    )
    show_cand = st.sidebar.checkbox(
        "显示 candidate 关系 (虚线)", value=False,
        help="candidate = confidence 为 medium/low 或缺失; 不计入统计。"
    )
    show_all = st.sidebar.checkbox(
        "显示全部节点 (含无关系普通节点)", value=False,
        help="默认只显示 landmark ∪ confirmed 边端点 (≤80 节点); 打开后加载全部有年份节点。"
    )

    st.sidebar.markdown("---")
    search = st.sidebar.text_input("方法搜索", "", help="按名称模糊匹配")

    st.sidebar.markdown("---")
    st.sidebar.caption("**高级 (语义聚类视图)**")
    show_halos = st.sidebar.checkbox("大陆晕染 (仅语义聚类)", value=False,
                                     help="V2 默认关闭, 避免过密。")
    edge_strategy = st.sidebar.radio(
        "边策略 (仅语义聚类)", ["精选", "全部"], index=0,
        help="精选 ≈ 113 条真大陆桥 + landmark 高置信; 全部 ≈ 1054。"
    )

    return {
        "year_range": (y_lo, y_hi),
        "picked_clusters": picked_cids,
        "picked_sub": set(picked_sub),
        "rel_types": set(rel_types),
        "only_landmark": only_lm,
        "only_confirmed": only_conf,
        "show_candidate": show_cand,
        "show_all_nodes": show_all,
        "search": search,
        "show_halos": show_halos,
        "edge_strategy": edge_strategy,
    }


# ==================== 图例 ====================

def render_legend():
    with st.expander("图例说明", expanded=False):
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("**关系类型**")
            for r, c in EDGE_COLORS_V2.items():
                st.markdown(
                    f"<span style='display:inline-block;width:24px;height:3px;"
                    f"background:{c};vertical-align:middle;margin-right:6px'></span>"
                    f"**{r}** · {REL_LABEL_CN[r]}",
                    unsafe_allow_html=True)
            st.caption("实线 = confirmed(高置信) / 虚线 = candidate(候选, 默认不画)")
        with c2:
            st.markdown("**节点类型**")
            st.markdown("🔵 大深蓝 = 本文提出方法 (own)")
            st.markdown("🔷 浅蓝 = 引用/参考方法 (referenced)")
            st.markdown("📍 pin 标记 = landmark 代表方法")
            st.markdown("🔴◆ = 泳道内数据集最早节点 (★)")
        with c3:
            st.markdown("**布局**")
            st.markdown("- 横轴 = 年份 2005–2026 (固定)")
            st.markdown("- 纵轴 = 9 大聚类分泳道")
            st.markdown("- 无年份节点不参与绘图")
            st.markdown("- 箭头方向 = 早期方法 → 后续方法")


# ==================== 首页统计 ====================

def render_stats(atlas):
    id2 = atlas["id2node"]
    n_total = len(atlas["nodes"])
    n_with_year = sum(1 for n in atlas["nodes"] if n.get("year"))
    n_clusters = len(atlas["clusters"])
    n_confirmed = sum(1 for e in atlas["edges"] if e.get("confidence") == "high")
    years = [n["year"] for n in atlas["nodes"] if n.get("year")]
    y_min = min(years) if years else "-"
    y_max = max(years) if years else "-"

    cols = st.columns(6)
    cols[0].metric("方法节点", n_total)
    cols[1].metric("有年份节点", f"{n_with_year}",
                   f"{100 * n_with_year / max(1, n_total):.1f}%")
    cols[2].metric("方法主线", n_clusters)
    cols[3].metric("confirmed 关系", n_confirmed,
                   help="candidate 不计入")
    cols[4].metric("最早年份", y_min)
    cols[5].metric("最晚年份", y_max)


# ==================== 主入口 ====================

def main():
    st.set_page_config(
        page_title="储能方法演化版图 V2",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.markdown("<h2 style='margin-bottom:4px'>储能方法演化版图 <span style='color:#888;font-size:0.6em'>V2 · 时间轴泳道</span></h2>",
                unsafe_allow_html=True)
    st.caption("默认视图: 横轴年份 (2005–2026) × 纵轴 9 大聚类泳道; "
               "只显示 landmark ∪ confirmed 关系端点 (≤80 节点)。"
               "严格数据边界: 不根据年份/相似度自动画边, 无年份节点不参与绘图。")

    atlas = load_atlas_cached(include_peripheral=False)

    render_stats(atlas)
    st.markdown("---")

    filters = sidebar_controls(atlas)

    tab_time, tab_semantic = st.tabs(["🕐 时间演化 (默认)", "🌐 语义聚类"])

    # ---- Tab 1: 时间演化 ----
    with tab_time:
        render_legend()
        option, lane_marks, lanes_used = build_time_evolution_option(atlas, filters)
        render_echarts(
            option, hull_payload=[], lane_payload=lane_marks,
            key="timeEvo", height=560, tooltip_js=TOOLTIP_JS_TIME,
            x_min=YEAR_MIN - 2.4, x_max=YEAR_MAX + 0.6,
        )
        # 2026 数据空缺提示
        has_2026 = any((n.get("year") == 2026) for n in atlas["nodes"])
        if not has_2026:
            st.caption("⚠️ 2026 年目前**暂无数据**入库 (语料截至 2025)。")

        # 主线快速展开 (点击进入子分支)
        st.markdown("### 主线展开 — 查看某条主线的子分支")
        col_pick, col_hint = st.columns([2, 3])
        with col_pick:
            focus = st.selectbox(
                "选择主线",
                ["(不展开)"] + [f"C{ln['cid']} · {ln['label']}"
                                 for ln in derive_swimlanes(atlas)],
            )
        with col_hint:
            st.caption("展开后仅显示该主线内节点, 按 secondary_topic 分子分支列出。"
                       "V2 只有 C2 石蜡基相变材料具备完整谱系。")

        if focus != "(不展开)":
            cid_focus = int(focus.split("·")[0].strip()[1:])
            _render_cluster_expand(atlas, cid_focus)

        # 节点详情面板
        st.markdown("---")
        st.markdown("### 节点详情")
        _render_node_picker(atlas, filters, "time")

    # ---- Tab 2: 语义聚类 (原视图) ----
    with tab_semantic:
        st.caption("原始 UMAP + HDBSCAN 聚类视图 (保留自 V1)。"
                   "关系边继承 V2 配色方案 (EXTENDS 蓝 / IMPROVES 绿 / ADAPTS 橙 / REPLACES 红)。")
        option, hulls = build_semantic_cluster_option(
            atlas,
            show_halos=filters["show_halos"],
            show_landmarks=True,
            edge_strategy=filters["edge_strategy"],
            rel_filter=filters["rel_types"],
        )
        render_echarts(
            option, hull_payload=hulls, lane_payload=[],
            key="semantic", height=620, tooltip_js=TOOLTIP_JS_CLUSTER,
        )
        st.caption("(泳道 X/Y 由 UMAP 投影确定, 非年份轴)")

        st.markdown("---")
        st.markdown("### 节点详情")
        _render_node_picker(atlas, filters, "semantic")


def _render_cluster_expand(atlas, cid: int):
    """展开某条主线, 按 secondary_topic 分子分支列出可见节点."""
    id2 = atlas["id2node"]
    cof = atlas["cluster_of"]
    ids = [nid for nid, c in cof.items() if c == cid]
    label = atlas["clusters"].get(cid, {}).get("label", "?")
    st.markdown(f"#### C{cid} · {label} · {len(ids)} 节点")

    by_sub = defaultdict(list)
    for nid in ids:
        n = id2[nid]
        sub = n["secondary_topic"] or "(未标注子领域)"
        by_sub[sub].append(nid)

    for sub, sub_ids in sorted(by_sub.items(), key=lambda kv: -len(kv[1])):
        with st.expander(f"{sub} · {len(sub_ids)} 节点", expanded=False):
            landmarks_here = [i for i in sub_ids if i in atlas["landmark_ids"]]
            if landmarks_here:
                st.markdown("**Landmarks**: " +
                            " · ".join(f"`{id2[i]['name']}` ({id2[i]['year'] or '?'})"
                                       for i in landmarks_here))
            names = [(id2[i]["year"] or 0, id2[i]["name"]) for i in sub_ids]
            names.sort()
            preview = ", ".join(f"{y or '?'}: {nm}" for y, nm in names[:15])
            more = f" … 还有 {len(names) - 15}" if len(names) > 15 else ""
            st.caption(preview + more)


def _render_node_picker(atlas, filters, key_prefix: str):
    """详情面板选择器. 从"当前过滤集"或搜索结果里选一个节点."""
    id2 = atlas["id2node"]
    if filters.get("show_all_nodes"):
        pool = list(id2.keys())
    else:
        pool = list(default_visible_nodes(atlas, DEFAULT_MAX_NODES))
    if filters.get("only_landmark"):
        pool = [i for i in pool if i in atlas["landmark_ids"]]

    y0, y1 = filters["year_range"]
    pool = [i for i in pool
            if id2[i].get("year") and y0 <= int(id2[i]["year"]) <= y1]
    picked_c = filters.get("picked_clusters") or set()
    if picked_c:
        pool = [i for i in pool if atlas["cluster_of"].get(i, -1) in picked_c]

    search = (filters.get("search") or "").strip().lower()
    if search:
        pool = [i for i in pool if search in (id2[i]["name"] or "").lower()]

    pool.sort(key=lambda i: (id2[i].get("year") or 9999, id2[i]["name"]))
    if not pool:
        st.info("当前筛选下无节点可选; 放宽过滤条件或勾选 \"显示全部节点\"。")
        return

    def lbl(i):
        n = id2[i]
        tag = " 🏛" if i in atlas["landmark_ids"] else ""
        return f"[{n['year'] or '?'}] {n['name']} · C{atlas['cluster_of'].get(i, '?')}{tag}"

    picked = st.selectbox(
        f"选择方法节点 (筛选结果 {len(pool)} 个)",
        pool, format_func=lbl, key=f"picker_{key_prefix}",
    )
    render_details_panel(atlas, picked)


if __name__ == "__main__":
    main()
