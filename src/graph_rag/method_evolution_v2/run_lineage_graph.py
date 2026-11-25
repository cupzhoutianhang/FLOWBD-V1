"""run_lineage_graph.py — spec 六: 时间线布局的方法谱系图.

- 横轴严格按年份 (无年份放右侧独立"年份未知"区)
- 纵向按 target_problem 分层
- 星号 = 最早可追溯节点
- 实线 = confirmed, 虚线 = candidate
- 4 种关系颜色: EXTENDS/IMPROVES/ADAPTS/REPLACES
- 输出: lineage_graph.html (自包含 SVG + JS 悬停/点击), lineage_graph.png,
        lineage_graph_data.json, lineage_legend.md
"""
from __future__ import annotations

import csv
import json
import os
import sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_GRAPH_RAG_DIR = os.path.dirname(THIS_DIR)
if SRC_GRAPH_RAG_DIR not in sys.path:
    sys.path.insert(0, SRC_GRAPH_RAG_DIR)

from method_evolution_v2 import config                                # noqa: E402
from method_evolution_v2.stage_a import full_runner as fr             # noqa: E402


OUT_DIR = os.path.join(config.PAPER_V2_DIR, "article_minimal_results",
                          "lineage_mvp")


RELATION_COLORS = {
    "EXTENDS": "#1f77b4",    # blue
    "IMPROVES": "#2ca02c",   # green
    "ADAPTS": "#ff7f0e",     # orange
    "REPLACES": "#d62728",   # red
    "UNKNOWN": "#7f7f7f",
}


def _parse_sids(s):
    try: return json.loads(s) if s else []
    except Exception: return []


def load_all():
    with open(os.path.join(OUT_DIR, "lineage_methods_normalized.csv"),
                "r", encoding="utf-8-sig") as f:
        methods = list(csv.DictReader(f))
    with open(os.path.join(OUT_DIR, "lineage_edges_confirmed.csv"),
                "r", encoding="utf-8-sig") as f:
        confirmed = list(csv.DictReader(f))
    with open(os.path.join(OUT_DIR, "lineage_edges_candidate.csv"),
                "r", encoding="utf-8-sig") as f:
        candidate = list(csv.DictReader(f))
    with open(os.path.join(OUT_DIR, "lineage_earliest_source.json"),
                "r", encoding="utf-8") as f:
        earliest = json.load(f)
    with open(os.path.join(OUT_DIR, "lineage_selected_family.json"),
                "r", encoding="utf-8") as f:
        sel = json.load(f)
    return methods, confirmed, candidate, earliest, sel


def load_sentence_texts(paper_ids):
    """Bring back a dict paper_id -> sid -> sentence_text (for hover)."""
    out = {}
    for pid in paper_ids:
        d = fr.per_paper_dir(pid)
        p = os.path.join(d, "sentence_index.json")
        if not os.path.isfile(p):
            continue
        with open(p, "r", encoding="utf-8") as f:
            sidx = json.load(f)
        out[pid] = {s["sentence_id"]: s.get("sentence_text", "")
                     for s in sidx.get("sentences", [])}
    return out


def build_graph_data(methods, confirmed, candidate, earliest, sent_texts):
    # Group by target_problem for y layering
    problems = []
    for m in methods:
        p = m.get("target_problem") or "(未分类)"
        if p not in problems: problems.append(p)
    prob_to_y = {p: i for i, p in enumerate(problems)}

    nodes = []
    for m in methods:
        try:
            y = int(m["year"]) if m["year"] else None
        except ValueError:
            y = None
        sids = _parse_sids(m.get("evidence_sentence_ids", ""))
        ev_texts = []
        for sid in sids[:3]:
            t = sent_texts.get(m["paper_id"], {}).get(sid, "")
            if t: ev_texts.append({"sid": sid, "text": t[:400]})
        target = m.get("target_problem") or "(未分类)"
        nodes.append({
            "id": m["method_id"],
            "name_short": (m.get("canonical_method_name") or "")[:40],
            "name_full": m.get("canonical_method_name", ""),
            "raw_name": m.get("raw_method_name", ""),
            "author": m.get("author", ""),
            "year": y,
            "paper_id": m["paper_id"],
            "kind": m.get("kind", ""),
            "target_problem": target,
            "core_process": m.get("core_process", ""),
            "core_material": m.get("core_material", ""),
            "application": m.get("application", ""),
            "year_source": m.get("year_source", ""),
            "source_status": m.get("source_status", ""),
            "reference_number": m.get("reference_number", ""),
            "layer_y": prob_to_y[target],
            "is_earliest": (m["method_id"] == earliest.get("method_id")),
            "evidence": ev_texts,
        })
    edges_c = []
    for e in confirmed:
        edges_c.append({
            "kind": "confirmed",
            "relation": e.get("relation", "UNKNOWN"),
            "from_id": e.get("from_method_id", ""),
            "to_id": e.get("to_method_id", ""),
            "from_name": e.get("from_method_name", ""),
            "to_name": e.get("to_method_name", ""),
            "evidence_sids": _parse_sids(
                e.get("relation_evidence_sentence_ids", "")),
            "direction_basis": e.get("direction_basis", "")[:300],
            "audit_support": e.get("audit_support", ""),
            "color": RELATION_COLORS.get(e.get("relation", ""), "#7f7f7f"),
        })
    edges_d = []
    for e in candidate:
        edges_d.append({
            "kind": "candidate",
            "relation": "candidate",
            "from_id": e.get("from_method_id", ""),
            "to_id": e.get("to_method_id", ""),
            "from_name": e.get("from_method_name", ""),
            "to_name": e.get("to_method_name", ""),
            "similarity_hint": e.get("similarity_hint", ""),
            "note": e.get("note", ""),
            "prohibition_flag": e.get("prohibition_flag", ""),
            "color": "#999999",
        })

    return {
        "nodes": nodes,
        "confirmed_edges": edges_c,
        "candidate_edges": edges_d,
        "layers": problems,
        "earliest": earliest,
    }


def emit_json(data):
    with open(os.path.join(OUT_DIR, "lineage_graph_data.json"),
                "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


HTML_TEMPLATE = r"""<!doctype html>
<html><head>
<meta charset="utf-8">
<title>方法谱系图 (MVP)</title>
<style>
body { font: 13px/1.5 -apple-system, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif; margin: 20px; }
h1 { font-size: 18px; margin-bottom: 6px; }
.subtitle { color:#666; margin-bottom:20px; }
.legend { margin: 10px 0 20px 0; font-size: 12px; padding: 8px 12px; background:#f7f7f7; border-radius:6px; display:inline-block; }
.legend .item { display:inline-block; margin-right:16px; }
.legend .swatch { display:inline-block; width:20px; height:3px; vertical-align:middle; margin-right:5px; }
svg { border: 1px solid #ddd; background: #fafafa; }
.node circle { cursor: pointer; }
.node.earliest circle { stroke: #b8860b; stroke-width: 3; }
.node text { pointer-events: none; font-size: 10px; fill: #333; }
.axis text { font-size: 11px; fill: #666; }
.axis line { stroke: #ccc; }
.tooltip { position: absolute; padding: 10px; background: rgba(0,0,0,0.85); color: #fff; border-radius: 5px; pointer-events: none; max-width: 320px; font-size: 11px; line-height: 1.4; opacity: 0; transition: opacity 0.15s; z-index: 999; }
.tooltip.show { opacity: 1; }
.detail-panel { border: 1px solid #ddd; padding: 12px; margin-top: 15px; background: #fff; border-radius: 6px; display: none; }
.detail-panel.show { display: block; }
.detail-panel h3 { margin: 0 0 8px 0; font-size: 14px; }
.detail-panel .evidence-block { background: #f0f0f0; padding: 6px 8px; margin: 4px 0; border-radius: 3px; font-size: 11px; }
.badge { display: inline-block; padding: 1px 6px; border-radius: 8px; font-size: 10px; color: #fff; margin-right: 6px; }
.badge.own { background: #1f77b4; }
.badge.ref { background: #7f7f7f; }
.badge.earliest { background: #b8860b; }
</style>
</head><body>
<h1>方法谱系图 — MVP: 相变材料渗漏/最佳含量测定/定形封装</h1>
<div class="subtitle">
  数据源: 337 篇既有储能相关中文文献 + 可解析引用范围. 边界: 不追溯外部原始文献; 不声称全球首次提出.
</div>
<div class="legend">
  <div class="item"><span class="swatch" style="background:#1f77b4;"></span>EXTENDS</div>
  <div class="item"><span class="swatch" style="background:#2ca02c;"></span>IMPROVES</div>
  <div class="item"><span class="swatch" style="background:#ff7f0e;"></span>ADAPTS</div>
  <div class="item"><span class="swatch" style="background:#d62728;"></span>REPLACES</div>
  <div class="item"><span class="swatch" style="background:#999;border:0;height:1px;border-top:2px dashed #999;"></span>candidate (虚线, 不进正式统计)</div>
  <div class="item">★ 最早可追溯节点</div>
</div>
<svg id="chart" width="1200" height="600"></svg>
<div class="tooltip" id="tooltip"></div>
<div class="detail-panel" id="detail-panel"></div>
<script>
const DATA = __DATA__;

const NODE_R_MIN = 5;
const NODE_R_EARLIEST = 10;
const MARGIN = {top: 40, right: 220, bottom: 60, left: 80};

const svg = document.getElementById("chart");
const W = 1200, H = 600;
const innerW = W - MARGIN.left - MARGIN.right;
const innerH = H - MARGIN.top - MARGIN.bottom;

// Year axis
const years = DATA.nodes.filter(n => n.year).map(n => n.year);
const yearMin = Math.min(...years) - 1;
const yearMax = Math.max(...years) + 1;
const unknownX = innerW - 60;

function xForYear(y) {
  if (!y) return unknownX;
  return MARGIN.left + ((y - yearMin) / (yearMax - yearMin)) * (unknownX - MARGIN.left - 30);
}

const layers = DATA.layers;
const layerH = innerH / Math.max(1, layers.length);

function yForLayer(idx) {
  return MARGIN.top + idx * layerH + layerH / 2;
}

// jitter within layer per node to prevent overlap
const layerCounter = {};
function nodePos(n) {
  const layerIdx = layers.indexOf(n.target_problem);
  const y = yForLayer(layerIdx);
  const x = xForYear(n.year);
  const key = n.year + '::' + layerIdx;
  const idx = (layerCounter[key] || 0);
  layerCounter[key] = idx + 1;
  return { x: x + (idx % 3 - 1) * 10, y: y + Math.floor(idx / 3) * 15 };
}

// SVG namespace helper
const svgNS = "http://www.w3.org/2000/svg";
function el(name, attrs = {}) {
  const e = document.createElementNS(svgNS, name);
  for (const k of Object.keys(attrs)) e.setAttribute(k, attrs[k]);
  return e;
}

// axis
const axis = el("g", { class: "axis" });
for (let y = yearMin + 1; y <= yearMax - 1; y++) {
  if (y % 2 !== 0) continue;
  const xi = xForYear(y);
  axis.appendChild(el("line", {
    x1: xi, x2: xi,
    y1: MARGIN.top, y2: MARGIN.top + innerH,
    stroke: "#eee"
  }));
  const t = el("text", { x: xi, y: H - MARGIN.bottom + 20,
                              "text-anchor": "middle" });
  t.textContent = y;
  axis.appendChild(t);
}
// unknown zone marker
axis.appendChild(el("line", {
  x1: unknownX - 15, x2: unknownX - 15,
  y1: MARGIN.top, y2: MARGIN.top + innerH,
  stroke: "#ff7f0e", "stroke-dasharray": "4,4"
}));
{
  const tu = el("text", { x: unknownX, y: H - MARGIN.bottom + 20,
                                "text-anchor": "middle", fill: "#ff7f0e" });
  tu.textContent = "年份未知";
  axis.appendChild(tu);
}
svg.appendChild(axis);

// layer labels
const labelG = el("g");
for (let i = 0; i < layers.length; i++) {
  const t = el("text", { x: 8, y: yForLayer(i) + 3,
                              fill: "#666", "font-size": 10 });
  t.textContent = layers[i];
  labelG.appendChild(t);
  labelG.appendChild(el("line", {
    x1: MARGIN.left, x2: MARGIN.left + innerW,
    y1: MARGIN.top + i * layerH,
    y2: MARGIN.top + i * layerH,
    stroke: "#f0f0f0"
  }));
}
svg.appendChild(labelG);

// compute node positions
const posMap = {};
for (const n of DATA.nodes) posMap[n.id] = nodePos(n);

// edges (dashed for candidate)
const edgeG = el("g");
for (const e of DATA.candidate_edges) {
  const p1 = posMap[e.from_id], p2 = posMap[e.to_id];
  if (!p1 || !p2) continue;
  edgeG.appendChild(el("line", {
    x1: p1.x, y1: p1.y, x2: p2.x, y2: p2.y,
    stroke: e.color, "stroke-width": 1,
    "stroke-dasharray": "5,4", opacity: 0.7
  }));
}
for (const e of DATA.confirmed_edges) {
  const p1 = posMap[e.from_id], p2 = posMap[e.to_id];
  if (!p1 || !p2) continue;
  edgeG.appendChild(el("line", {
    x1: p1.x, y1: p1.y, x2: p2.x, y2: p2.y,
    stroke: e.color, "stroke-width": 2.5, opacity: 0.85
  }));
  // arrow head
  const dx = p2.x - p1.x, dy = p2.y - p1.y;
  const L = Math.hypot(dx, dy) || 1;
  const ax = p2.x - dx / L * 12;
  const ay = p2.y - dy / L * 12;
  const perpX = -dy / L * 5, perpY = dx / L * 5;
  edgeG.appendChild(el("polygon", {
    points: `${p2.x},${p2.y} ${ax + perpX},${ay + perpY} ${ax - perpX},${ay - perpY}`,
    fill: e.color
  }));
}
svg.appendChild(edgeG);

// nodes
const tooltip = document.getElementById("tooltip");
const detail = document.getElementById("detail-panel");

const nodeG = el("g");
for (const n of DATA.nodes) {
  const p = posMap[n.id];
  const grp = el("g", {
    class: "node" + (n.is_earliest ? " earliest" : ""),
    transform: `translate(${p.x},${p.y})`
  });
  const r = n.is_earliest ? NODE_R_EARLIEST : NODE_R_MIN;
  const color = n.kind === "own" ? "#1f77b4" : "#7f7f7f";
  grp.appendChild(el("circle", {
    r: r, fill: color, opacity: 0.85,
    stroke: n.is_earliest ? "#b8860b" : "#fff",
    "stroke-width": n.is_earliest ? 3 : 1
  }));
  if (n.is_earliest) {
    const star = el("text", { x: 0, y: 4, "text-anchor": "middle",
                                  "font-size": 14, fill: "#fff" });
    star.textContent = "★";
    grp.appendChild(star);
  }
  const label = n.name_short.length > 22 ? n.name_short.slice(0, 22) + "…" : n.name_short;
  const t = el("text", { x: r + 4, y: 4 });
  t.textContent = label;
  grp.appendChild(t);

  grp.addEventListener("mouseover", (ev) => {
    tooltip.innerHTML = `
      <strong>${escapeHTML(n.name_full || n.raw_name)}</strong><br>
      <em>${n.kind === "own" ? "own (本文原创)" : "referenced (前人)"}</em><br>
      作者: ${escapeHTML(n.author || "-")} · 年份: ${n.year || "未知"} (${n.year_source})<br>
      来源: ${n.source_status}<br>
      论文: ${escapeHTML(n.paper_id)}<br>
      target: ${escapeHTML(n.target_problem)} · process: ${escapeHTML(n.core_process || "-")}
    `;
    tooltip.classList.add("show");
    tooltip.style.left = (ev.pageX + 15) + "px";
    tooltip.style.top = (ev.pageY + 10) + "px";
  });
  grp.addEventListener("mouseout", () => tooltip.classList.remove("show"));
  grp.addEventListener("mousemove", (ev) => {
    tooltip.style.left = (ev.pageX + 15) + "px";
    tooltip.style.top = (ev.pageY + 10) + "px";
  });
  grp.addEventListener("click", () => {
    let ev = n.evidence.map(e => `<div class="evidence-block"><code>${escapeHTML(e.sid)}</code>: 「${escapeHTML(e.text)}」</div>`).join("");
    if (!ev) ev = "<em>无原文证据句</em>";
    detail.innerHTML = `
      <h3>${n.is_earliest ? "★ " : ""}${escapeHTML(n.name_full)}</h3>
      <div><span class="badge ${n.kind === "own" ? "own" : "ref"}">${n.kind}</span>
      ${n.is_earliest ? '<span class="badge earliest">最早可追溯</span>' : ""}
      作者: <strong>${escapeHTML(n.author || "-")}</strong>
      · 年份: <strong>${n.year || "未知"}</strong> (${n.year_source})
      · 来源状态: <strong>${n.source_status}</strong>
      · 引用编号: ${n.reference_number || "-"}</div>
      <div style="margin-top:6px;">论文: <code>${escapeHTML(n.paper_id)}</code></div>
      <div style="margin-top:6px;">target_problem: <strong>${escapeHTML(n.target_problem)}</strong> · core_process: <strong>${escapeHTML(n.core_process || "-")}</strong> · core_material: <strong>${escapeHTML(n.core_material || "-")}</strong> · application: <strong>${escapeHTML(n.application || "-")}</strong></div>
      <div style="margin-top:10px;"><strong>原文证据:</strong></div>
      ${ev}
    `;
    detail.classList.add("show");
  });
  nodeG.appendChild(grp);
}
svg.appendChild(nodeG);

function escapeHTML(s) {
  return String(s).replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
}
</script>
</body></html>
"""


def emit_html(data):
    html = HTML_TEMPLATE.replace("__DATA__",
                                       json.dumps(data, ensure_ascii=False))
    with open(os.path.join(OUT_DIR, "lineage_graph.html"),
                "w", encoding="utf-8") as f:
        f.write(html)


def emit_png(data):
    """matplotlib static rendering (no seaborn)."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
    except ImportError:
        print("matplotlib not installed; skipping PNG")
        return

    fig, ax = plt.subplots(figsize=(14, 7))
    layers = data["layers"]
    n_layers = len(layers)
    layer_y = {p: n_layers - 1 - i for i, p in enumerate(layers)}
    years = [n["year"] for n in data["nodes"] if n["year"]]
    if not years:
        print("no years to plot")
        return
    y_min, y_max = min(years) - 1, max(years) + 1
    unknown_x = y_max + 2

    counter = {}
    node_pos = {}
    for n in data["nodes"]:
        x = n["year"] if n["year"] else unknown_x
        y = layer_y.get(n["target_problem"], 0)
        key = (x, y)
        idx = counter.get(key, 0)
        counter[key] = idx + 1
        pos_x = x + (idx % 3 - 1) * 0.15
        pos_y = y + (idx // 3) * 0.25
        node_pos[n["id"]] = (pos_x, pos_y)
        c = "#1f77b4" if n["kind"] == "own" else "#7f7f7f"
        s = 180 if n["is_earliest"] else 60
        marker = "*" if n["is_earliest"] else "o"
        ax.scatter([pos_x], [pos_y], s=s, c=c,
                     marker=marker, edgecolors="#b8860b" if n["is_earliest"] else "white",
                     linewidths=2 if n["is_earliest"] else 0.5, zorder=3)
        # label
        ax.annotate(n["name_short"][:18], (pos_x, pos_y),
                     xytext=(6, 0), textcoords="offset points",
                     fontsize=6, color="#333")

    for e in data["candidate_edges"]:
        if e["from_id"] not in node_pos or e["to_id"] not in node_pos: continue
        p1, p2 = node_pos[e["from_id"]], node_pos[e["to_id"]]
        ax.plot([p1[0], p2[0]], [p1[1], p2[1]],
                 linestyle="--", color="#999", linewidth=1, alpha=0.6, zorder=1)
    for e in data["confirmed_edges"]:
        if e["from_id"] not in node_pos or e["to_id"] not in node_pos: continue
        p1, p2 = node_pos[e["from_id"]], node_pos[e["to_id"]]
        ax.annotate("", xy=p2, xytext=p1,
                     arrowprops=dict(arrowstyle="-|>", color=e["color"],
                                        lw=2, alpha=0.85), zorder=2)

    # layer horizontal grid
    for i, p in enumerate(layers):
        ax.axhline(n_layers - 1 - i - 0.5, color="#eee",
                    linewidth=0.7, zorder=0)
        ax.text(y_min - 0.4, n_layers - 1 - i, p, fontsize=8,
                 ha="right", va="center", color="#666")

    # unknown zone
    ax.axvline(unknown_x - 0.6, color="#ff7f0e", linestyle="--",
                 linewidth=1, alpha=0.6)
    ax.text(unknown_x, -0.9, "年份未知", color="#ff7f0e",
             fontsize=9, ha="center")

    ax.set_xlim(y_min - 1, unknown_x + 1)
    ax.set_ylim(-1.2, n_layers)
    ax.set_xlabel("年份")
    ax.set_yticks([])
    ax.set_title("方法谱系图 — 相变材料渗漏/最佳含量测定/定形封装 (MVP)")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)

    # legend
    handles = [
        mpatches.Patch(color="#1f77b4", label="EXTENDS"),
        mpatches.Patch(color="#2ca02c", label="IMPROVES"),
        mpatches.Patch(color="#ff7f0e", label="ADAPTS"),
        mpatches.Patch(color="#d62728", label="REPLACES"),
        mpatches.Patch(color="#999", label="candidate (虚线)"),
    ]
    ax.legend(handles=handles, loc="upper right", fontsize=8,
                framealpha=0.9, ncol=2)

    plt.tight_layout()
    plt.savefig(os.path.join(OUT_DIR, "lineage_graph.png"),
                  dpi=160, bbox_inches="tight")
    plt.close()


def emit_legend(data):
    n_conf = len(data["confirmed_edges"])
    n_cand = len(data["candidate_edges"])
    n_nodes = len(data["nodes"])
    lines = [
        "# 谱系图图例 (spec 六)\n\n",
        f"> 方法谱系 MVP — {n_nodes} 个方法节点, "
        f"{n_conf} 条 confirmed 关系, {n_cand} 条 candidate 关系\n\n",
        "## 节点\n\n",
        "- **蓝色圆**: own (本文原创方法)\n",
        "- **灰色圆**: referenced (前人方法)\n",
        "- **金色边框 + 大号 ★**: 最早可追溯节点\n",
        "- **无年份节点**: 放在图右侧'年份未知'区\n\n",
        "## 边\n\n",
        "- 实线 + 箭头 = confirmed 关系\n",
        "  - <span style='color:#1f77b4'>■</span> 蓝色 = EXTENDS\n",
        "  - <span style='color:#2ca02c'>■</span> 绿色 = IMPROVES\n",
        "  - <span style='color:#ff7f0e'>■</span> 橙色 = ADAPTS\n",
        "  - <span style='color:#d62728'>■</span> 红色 = REPLACES\n",
        "- 虚线 = candidate 关系 (**不进入正式关系统计**)\n\n",
        "## 交互 (仅 HTML 版)\n\n",
        "- **鼠标悬停节点**: 显示完整方法名、作者、年份、论文\n",
        "- **点击节点**: 弹出下方详情面板, 显示原文证据句\n",
        "- **坐标轴**: 横轴为年份 (严格线性), 无年份的节点放在右侧独立区\n",
        "- **纵向分层**: 按 `target_problem` 分层 (spec 六: 技术分支/方法类型分层, 不用 UMAP)\n\n",
        "## 使用规范\n\n",
        "- **禁止**: 因为节点更靠右就断言演化 (只是年份晚); 因名称相似就断言演化; 因材料相同就断言演化\n",
        "- 只有实线才是 confirmed 演化关系\n",
        "- 虚线代表候选关系, 论文正文引用时必须说明**未确认**\n",
    ]
    with open(os.path.join(OUT_DIR, "lineage_legend.md"),
                "w", encoding="utf-8") as f:
        f.writelines(lines)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError): pass

    methods, confirmed, candidate, earliest, sel = load_all()
    print(f"loaded: {len(methods)} nodes, {len(confirmed)} confirmed, "
            f"{len(candidate)} candidate")
    pids = {m["paper_id"] for m in methods}
    sent_texts = load_sentence_texts(pids)
    data = build_graph_data(methods, confirmed, candidate, earliest, sent_texts)
    emit_json(data)
    emit_html(data)
    emit_png(data)
    emit_legend(data)
    print(f"wrote lineage_graph.html + .json + .png + lineage_legend.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
