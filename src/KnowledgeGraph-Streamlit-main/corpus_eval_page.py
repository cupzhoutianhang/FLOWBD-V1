"""
corpus_eval_page.py — 语料库 / 评测报告 (FlowBD-V1, 前端美化阶段6 · 纯新增只读页)

数据边界 (严格只读, 不写任何文件/数据库):
    - Stage A 产出: methods.csv / edges.csv / publish_year_report.csv
    - 语料: pdf_to_md/extraction_results/downloaded_files (只数目录, 不读文件内容)
    - Milvus: 只读 list_collections + get_collection_stats
    - 人工复核: <repo>/人工复核记录表_模板.csv
    - 单测回归: subprocess 跑 tests.test_answer_cleaner (纯函数测试, 无副作用)
    - A3 bad case: 静态摘录自 ui-demo/工作日志_2026-09-03/04.md (页内注明出处)

启动:
    streamlit run src/KnowledgeGraph-Streamlit-main/corpus_eval_page.py --server.port 8513
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from datetime import datetime

import pandas as pd
import streamlit as st

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if THIS_DIR not in sys.path:
    sys.path.insert(0, THIS_DIR)

import ui_style

ROOT = os.path.abspath(os.path.join(THIS_DIR, "..", ".."))       # FlowBD系统
REPO = os.path.abspath(os.path.join(ROOT, ".."))                # chunengtupu
ME_DIR = os.path.join(ROOT, "src", "graph_rag", "method_extraction")
PDF_DIR = os.path.join(ROOT, "pdf_to_md", "extraction_results", "downloaded_files")
REVIEW_CSV = os.path.join(REPO, "人工复核记录表_模板.csv")

PAL = ui_style.PALETTE


# ==================== 数据加载 (全部只读) ====================

@st.cache_data(ttl=300, show_spinner=False)
def load_stage_a():
    methods = pd.read_csv(os.path.join(ME_DIR, "methods.csv"))
    edges = pd.read_csv(os.path.join(ME_DIR, "edges.csv"))
    pyr = pd.read_csv(os.path.join(ME_DIR, "publish_year_report.csv"))
    return methods, edges, pyr


@st.cache_data(ttl=300, show_spinner=False)
def count_corpus():
    if not os.path.isdir(PDF_DIR):
        return 0, 0
    dirs = [d for d in os.listdir(PDF_DIR) if os.path.isdir(os.path.join(PDF_DIR, d))]
    with_md = sum(1 for d in dirs if os.path.exists(os.path.join(PDF_DIR, d, "full.md")))
    return len(dirs), with_md


@st.cache_data(ttl=120, show_spinner=False)
def load_milvus_stats():
    """返回 ([(collection, row_count), ...], error). row_count=-1 表示统计失败."""
    try:
        from pymilvus import MilvusClient
        client = MilvusClient(uri="http://localhost:19530")
        out = []
        for c in sorted(client.list_collections()):
            try:
                n = int(client.get_collection_stats(c).get("row_count", 0))
            except Exception:
                n = -1
            out.append((c, n))
        client.close()
        return out, None
    except Exception as e:
        return [], str(e)


@st.cache_data(ttl=300, show_spinner="运行 answer_cleaner 回归单测...")
def run_unit_tests():
    """返回 ({run, fail, err} | None, error)."""
    cmd = [
        sys.executable, "-c",
        "import sys; sys.path.insert(0, r'src/agent'); import unittest; "
        "r = unittest.TextTestRunner(verbosity=1).run("
        "unittest.TestLoader().loadTestsFromName('tests.test_answer_cleaner')); "
        "print('TESTS_RUN', r.testsRun, 'FAILURES', len(r.failures), 'ERRORS', len(r.errors))",
    ]
    try:
        p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                           timeout=120, encoding="utf-8", errors="replace")
        m = re.search(r"TESTS_RUN (\d+) FAILURES (\d+) ERRORS (\d+)", p.stdout or "")
        if not m:
            return None, ((p.stdout or "") + (p.stderr or ""))[-400:]
        return {"run": int(m.group(1)), "fail": int(m.group(2)), "err": int(m.group(3))}, None
    except Exception as e:
        return None, str(e)


@st.cache_data(ttl=300, show_spinner=False)
def load_review_progress():
    """模板表存在未加引号的逗号导致列数不齐, 用 csv 模块手解并补/裁到表头列数."""
    if not os.path.exists(REVIEW_CSV):
        return None
    try:
        import csv as _csv
        with open(REVIEW_CSV, encoding="utf-8-sig", newline="") as f:
            rows = list(_csv.reader(f))
        if len(rows) < 2:
            return None
        header, ncol = rows[0], len(rows[0])
        data = []
        for r in rows[1:]:
            if not any(cell.strip() for cell in r):
                continue
            data.append((r + [""] * ncol)[:ncol])
        return pd.DataFrame(data, columns=header)
    except Exception:
        return None


def _file_info(name):
    p = os.path.join(ME_DIR, name)
    if not os.path.exists(p):
        return None
    stat = os.stat(p)
    return {
        "name": name,
        "size_kb": round(stat.st_size / 1024, 1),
        "mtime": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
    }


# ==================== 页面组件 (demo 同款, 色值全走 --fb-* 变量) ====================

_PAGE_CSS = """
<style>
.ce-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:10px 0 16px}
.ce-card{background:var(--fb-surface);border:1px solid var(--fb-line);border-radius:12px;padding:14px 16px}
.ce-num{font-size:26px;font-weight:700;color:var(--fb-ink)}
.ce-num.good{color:var(--fb-teal)} .ce-num.warn{color:var(--fb-amber)} .ce-num.bad{color:var(--fb-rose)}
.ce-name{font-size:13px;color:var(--fb-ink-2);margin-top:2px}
.ce-note{font-size:11px;color:var(--fb-ink-3);margin-top:2px}
.ce-panel{background:var(--fb-surface);border:1px solid var(--fb-line);border-radius:12px;padding:16px 18px;margin-bottom:16px}
.ce-title{font-size:15px;font-weight:600;color:var(--fb-ink)}
.ce-sub{font-size:12px;color:var(--fb-ink-3);margin:2px 0 10px}
.hbar-row{display:flex;align-items:center;gap:8px;margin:6px 0;font-size:12px;color:var(--fb-ink-2)}
.hbar-k{width:96px;text-align:right;flex:none}
.hbar-track{flex:1;height:8px;background:var(--fb-line-2);border-radius:4px;overflow:hidden}
.hbar-fill{height:100%;background:var(--fb-teal);border-radius:4px}
.hbar-v{width:44px;font-family:Consolas,monospace;color:var(--fb-ink-2)}
table.ce-tbl{width:100%;border-collapse:collapse;font-size:12.5px}
.ce-tbl th{text-align:left;color:var(--fb-ink-3);font-weight:600;padding:6px 8px;border-bottom:1px solid var(--fb-line)}
.ce-tbl td{padding:6px 8px;border-bottom:1px solid var(--fb-line-2);color:var(--fb-ink-2)}
.ce-tbl td:first-child{color:var(--fb-ink)}
.ce-mono{font-family:Consolas,monospace}
.ce-tag{display:inline-block;padding:1px 8px;border-radius:8px;font-size:11px;font-weight:600}
.ce-tag.ok{background:var(--fb-teal-soft);color:var(--fb-teal)}
.ce-tag.warn{background:var(--fb-amber-soft);color:var(--fb-amber)}
.ce-tag.bad{background:var(--fb-rose-soft);color:var(--fb-rose)}
</style>
"""


def _metric_card(num, name, note, cls=""):
    return (f'<div class="ce-card"><div class="ce-num {cls}">{num}</div>'
            f'<div class="ce-name">{name}</div><div class="ce-note">{note}</div></div>')


def _hbar_rows(pairs):
    """pairs: [(label, value)], 按最大值归一化."""
    vmax = max((v for _, v in pairs), default=1) or 1
    rows = []
    for k, v in pairs:
        pct = round(v / vmax * 100)
        rows.append(
            f'<div class="hbar-row"><span class="hbar-k">{k}</span>'
            f'<div class="hbar-track"><div class="hbar-fill" style="width:{pct}%"></div></div>'
            f'<span class="hbar-v">{v}</span></div>'
        )
    return "".join(rows)


def _panel(title, sub, body_html):
    return (f'<div class="ce-panel"><div class="ce-title">{title}</div>'
            f'<div class="ce-sub">{sub}</div>{body_html}</div>')


# ==================== 语料库 tab ====================

def render_corpus_tab():
    methods, edges, pyr = load_stage_a()
    n_pdf, n_md = count_corpus()
    milvus_stats, milvus_err = load_milvus_stats()
    v5_entities = next((n for c, n in milvus_stats if "v5" in c and n >= 0), None)

    n_own = int((methods["kind"] == "own").sum())
    n_ref = int((methods["kind"] == "ref").sum())
    conf = edges["confidence"].value_counts().to_dict()

    st.markdown(
        '<div class="ce-grid">'
        + _metric_card(n_pdf, "文献总数", f"PDF + Markdown 双格式 (full.md × {n_md})")
        + _metric_card(len(methods), "Stage A 方法条目", f"own {n_own} · ref {n_ref}", "good")
        + _metric_card(f"{v5_entities:,}" if v5_entities is not None else "—",
                       "Milvus 向量块", "collection v5 · bge-m3")
        + _metric_card(len(edges), "方法演化边",
                       f"high {conf.get('high', 0)} · medium {conf.get('medium', 0)} · low {conf.get('low', 0)}")
        + "</div>",
        unsafe_allow_html=True,
    )

    col_l, col_r = st.columns(2)

    with col_l:
        years = methods["year"].dropna().astype(int)
        bins = [
            ("≤ 2015", int((years <= 2015).sum())),
            ("2016-2018", int(((years >= 2016) & (years <= 2018)).sum())),
            ("2019-2021", int(((years >= 2019) & (years <= 2021)).sum())),
            ("2022-2024", int(((years >= 2022) & (years <= 2024)).sum())),
            ("≥ 2025", int((years >= 2025).sum())),
        ]
        st.markdown(
            _panel("发表年份分布", f"methods.csv 方法条目年份 · {years.min()} - {years.max()}",
                   _hbar_rows(bins)),
            unsafe_allow_html=True,
        )

    with col_r:
        if milvus_err:
            body = f'<div style="color:var(--fb-rose);font-size:12px">Milvus 连接失败: {milvus_err}</div>'
        else:
            rows = "".join(
                f'<tr><td class="ce-mono">{c}</td><td class="ce-mono">{n:,}</td>'
                f'<td>{"<span class=ce-tag.ok>在</span>" if n > 0 else "<span class=ce-tag.warn>空</span>"}</td></tr>'
                for c, n in milvus_stats
            )
            body = ('<table class="ce-tbl"><thead><tr><th>collection</th><th>向量块数</th><th>状态</th></tr></thead>'
                    f"<tbody>{rows}</tbody></table>")
        st.markdown(
            _panel("Milvus 集合统计", "只读实时查询 · localhost:19530", body),
            unsafe_allow_html=True,
        )

    # 文献明细 top 15 (按方法条目数)
    top = (methods.groupby("paper_id").size().rename("n")
           .reset_index().sort_values("n", ascending=False).head(15))
    year_of = pyr.set_index("paper_id")["year"].to_dict()
    trs = []
    for _, r in top.iterrows():
        pid = str(r["paper_id"])
        pid_show = pid if len(pid) <= 40 else pid[:39] + "…"
        yr = year_of.get(r["paper_id"], "—")
        trs.append(
            f"<tr><td>{pid_show}</td>"
            f'<td class="ce-mono">{int(yr) if pd.notna(yr) and str(yr).strip() not in ("", "—") else "—"}</td>'
            f'<td class="ce-mono">{int(r["n"])}</td>'
            f'<td><span class="ce-tag ok">已入库</span></td></tr>'
        )
    st.markdown(
        _panel("文献明细 (方法条目数 Top 15)", f"共 {methods['paper_id'].nunique()} 篇文献有方法抽取",
               '<table class="ce-tbl"><thead><tr><th>文献 (paper_id)</th><th>年份</th><th>方法条目数</th><th>状态</th></tr></thead>'
               f"<tbody>{''.join(trs)}</tbody></table>"),
        unsafe_allow_html=True,
    )


# ==================== 评测报告 tab ====================

def render_eval_tab():
    test_res, test_err = run_unit_tests()
    milvus_stats, milvus_err = load_milvus_stats()
    review_df = load_review_progress()

    if test_res:
        t_ok = test_res["fail"] == 0 and test_res["err"] == 0
        t_txt = f"{test_res['run'] - test_res['fail'] - test_res['err']}/{test_res['run']}"
        t_cls = "good" if t_ok else "bad"
        t_note = "answer_cleaner 回归 · 页面加载时实时运行"
    else:
        t_txt, t_cls, t_note = "—", "bad", f"运行失败: {(test_err or '')[:60]}"

    n_review = len(review_df) if review_df is not None else 0

    st.markdown(
        '<div class="ce-grid">'
        + _metric_card(t_txt, "单测通过", t_note, t_cls)
        + _metric_card(len(milvus_stats) if milvus_stats else "—", "Milvus 集合",
                       "连接失败" if milvus_err else "只读实时查询", "" if milvus_stats else "bad")
        + _metric_card(n_review, "人工复核对象", "人工复核记录表_模板.csv · 均待复核", "warn")
        + _metric_card(2, "A3 bad case 记录", "详见下方表格", "bad")
        + "</div>",
        unsafe_allow_html=True,
    )

    # 单测明细
    if test_res:
        ok = test_res["fail"] == 0 and test_res["err"] == 0
        tag = '<span class="ce-tag ok">全部通过</span>' if ok else '<span class="ce-tag bad">存在失败</span>'
        body = (f'<div style="font-size:13px;color:var(--fb-ink-2)">'
                f'tests.test_answer_cleaner · 运行 {test_res["run"]} 个用例, '
                f'失败 {test_res["fail"]}, 错误 {test_res["err"]} &nbsp;{tag}</div>')
    else:
        body = (f'<div style="font-size:12px;color:var(--fb-rose)">单测运行异常: '
                f'{(test_err or "未知错误")}</div>')
    st.markdown(
        _panel("回归单测", "每次页面加载实时运行 (5 分钟缓存)", body),
        unsafe_allow_html=True,
    )

    # 人工复核进度
    if review_df is not None:
        trs = []
        for _, r in review_df.iterrows():
            obj = str(r.get("复核对象", ""))
            content = str(r.get("关系／节点内容", ""))
            content = content if len(content) <= 42 else content[:41] + "…"
            done = any(str(r.get(c, "")).strip() for c in review_df.columns
                       if str(c).startswith(("①", "②", "③", "复核结论")))
            tag = '<span class="ce-tag ok">已复核</span>' if done else '<span class="ce-tag warn">待复核</span>'
            trs.append(f'<tr><td class="ce-mono">{obj}</td><td>{content}</td><td>{tag}</td></tr>')
        body = ('<table class="ce-tbl"><thead><tr><th>复核对象</th><th>关系/节点内容</th><th>状态</th></tr></thead>'
                f"<tbody>{''.join(trs)}</tbody></table>")
    else:
        body = '<div style="font-size:12px;color:var(--fb-ink-3)">未找到 人工复核记录表_模板.csv</div>'
    st.markdown(
        _panel("人工复核进度", "数据源: 仓库根目录 人工复核记录表_模板.csv (只读)", body),
        unsafe_allow_html=True,
    )

    # A3 bad case (静态摘录, 注明出处)
    bad_rows = [
        ("1", "幻觉题「什么是量子隧穿储热材料?」有实质输出",
         "检索无有效命中时系统未硬拒答; 回答已标注「专业推断」降权, 未编造 [Ref-n] 引用",
         "工作日志 2026-09-03 · A3 记录"),
        ("2", "钙基储热题检索跑偏 (rerank 全负)",
         "LLM 未生成 [Ref-n], 证据卡如实低分展示; 属检索召回质量问题, 非 UI 缺陷",
         "工作日志 2026-09-04 · 阶段3验收"),
    ]
    trs = "".join(
        f'<tr><td class="ce-mono">{i}</td><td>{phen}</td><td>{note}</td>'
        f'<td style="color:var(--fb-ink-3)">{src}</td></tr>'
        for i, phen, note, src in bad_rows
    )
    st.markdown(
        _panel("A3 bad case 记录", "静态摘录自工作日志 (页内注明出处), 非实时评测",
               '<table class="ce-tbl"><thead><tr><th style="width:34px">#</th><th>现象</th><th>处理/结论</th><th>出处</th></tr></thead>'
               f"<tbody>{trs}</tbody></table>"),
        unsafe_allow_html=True,
    )

    # Stage A 产出文件清单
    infos = [fi for fi in (_file_info(n) for n in
                           ("methods.csv", "edges.csv", "publish_year_report.csv")) if fi]
    rows_n = {"methods.csv": "1,951 行", "edges.csv": "1,271 行", "publish_year_report.csv": "337 行"}
    trs = "".join(
        f'<tr><td class="ce-mono">{fi["name"]}</td><td class="ce-mono">{rows_n.get(fi["name"], "—")}</td>'
        f'<td class="ce-mono">{fi["size_kb"]} KB</td><td class="ce-mono">{fi["mtime"]}</td></tr>'
        for fi in infos
    )
    st.markdown(
        _panel("Stage A 产出清单", "src/graph_rag/method_extraction/ (只读)",
               '<table class="ce-tbl"><thead><tr><th>文件</th><th>规模</th><th>体积</th><th>修改时间</th></tr></thead>'
               f"<tbody>{trs}</tbody></table>"),
        unsafe_allow_html=True,
    )


# ==================== 主入口 ====================

def main():
    st.set_page_config(
        page_title="语料库与评测报告",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    ui_style.inject_global_css()
    st.markdown(_PAGE_CSS, unsafe_allow_html=True)

    st.markdown(
        f"<h2 style='margin-bottom:2px;color:{PAL['ink']}'>语料库与评测报告</h2>"
        f"<div style='color:{PAL['ink_2']};font-size:0.95em;margin-bottom:12px'>"
        "FlowBD-V1 · Stage A 产出 / Milvus 索引 / 回归与人工复核 · 全部只读</div>",
        unsafe_allow_html=True,
    )

    tab_corpus, tab_eval = st.tabs(["  语料库", "  评测报告"])
    with tab_corpus:
        render_corpus_tab()
    with tab_eval:
        render_eval_tab()


if __name__ == "__main__":
    main()
