"""run_lineage_case_study.py — spec 七 论文案例文字 (无 API).

生成 method_lineage_case_study.md.
"""
from __future__ import annotations

import csv
import json
import os
import sys
from collections import Counter, defaultdict

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_GRAPH_RAG_DIR = os.path.dirname(THIS_DIR)
if SRC_GRAPH_RAG_DIR not in sys.path:
    sys.path.insert(0, SRC_GRAPH_RAG_DIR)

from method_evolution_v2 import config                            # noqa: E402
from method_evolution_v2.stage_a import full_runner as fr         # noqa: E402


OUT_DIR = os.path.join(config.PAPER_V2_DIR, "article_minimal_results",
                          "lineage_mvp")


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


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError): pass

    methods, confirmed, candidate, earliest, sel = load_all()
    n_methods = len(methods)
    n_own = sum(1 for m in methods if m["kind"] == "own")
    n_ref = n_methods - n_own
    n_dated = sum(1 for m in methods if m.get("year"))
    year_span_set = sorted({int(m["year"]) for m in methods
                                 if m.get("year") and m["year"].isdigit()})

    tp_counter = Counter((m.get("target_problem") or "(未分类)")
                              for m in methods)
    process_counter = Counter((m.get("core_process") or "(未分类)")
                                   for m in methods)

    md = []
    md.append(f"# 方法谱系案例研究 (MVP): {sel['selected_family_name']}\n\n")
    md.append("> 数据源: 本研究 337 篇既有储能相关中文文献及其可解析引用范围.\n")
    md.append("> **不追溯外部原始文献, 不声称全球首次提出**.\n\n")

    md.append("## 一. 方法家族背景\n\n")
    md.append(f"选定的方法家族: **{sel['selected_family_name']}**"
                f" (`{sel['selected_family_id']}`)\n\n")
    md.append("该家族的技术核心为**相变材料 (PCM) 在储热应用中的**"
                "**渗漏防治与最佳含量测定/定形封装**类方法, 涉及:\n\n")
    md.append("- **材料**: 石蜡 / 脂肪酸 (月桂酸 / 肉豆蔻酸 / 棕榈酸) / 三水醋酸钠 / "
                "十二水磷酸氢二钠 / MA-EG (肉豆蔻酸-膨胀石墨) 复合体系等\n")
    md.append("- **工艺**: 扩散-渗出圈法 / 步冷曲线 / 微胶囊化 / 原位聚合 / "
                "熔融共混 / 定形封装 / 最佳含量测定 / DSC 测试等\n")
    md.append("- **目标问题**: 渗漏防治、最佳含量测定、热导率提升、循环稳定性、"
                "定形/形态保持、封装等\n")
    md.append("- **应用**: 建材节能、工业蓄热、低温冷链、柔性穿戴、热管理等\n\n")

    md.append("### 家族规模\n\n")
    md.append(f"- 相关 accepted 方法: **{n_methods}** 条 "
                f"(own {n_own} / referenced {n_ref})\n")
    md.append(f"- 覆盖论文数: **{len(sel['paper_ids'])}**\n")
    md.append(f"- 有年份的方法: **{n_dated}** 条 "
                f"({round(100 * n_dated / n_methods, 1)}%)\n")
    md.append(f"- 年份分布: {year_span_set} (跨度 "
                f"{max(year_span_set) - min(year_span_set) if year_span_set else 0} 年)\n\n")

    md.append("### 目标问题分布\n\n")
    md.append("| target_problem | 方法数 |\n|---|---:|\n")
    for tp, n in tp_counter.most_common():
        md.append(f"| {tp} | {n} |\n")

    md.append("\n### 核心工艺分布 (top 8)\n\n")
    md.append("| core_process | 方法数 |\n|---|---:|\n")
    for p, n in process_counter.most_common(8):
        md.append(f"| {p} | {n} |\n")

    md.append("\n## 二. 方法检索和名称统一过程\n\n")
    md.append("### 2.1 检索\n\n")
    md.append("从 337 篇的 1147 条 accepted 方法中, 按以下规则筛选家族相关方法:\n\n")
    md.append("- 名称/证据文本包含**材料词** (相变 / PCM / 石蜡 / 脂肪酸 / "
                "月桂酸 / 肉豆蔻酸 / 棕榈酸 / 膨胀石墨 / MA/EG)\n")
    md.append("- **且**包含**工艺词** (渗漏 / 渗出 / 最佳含量 / 定形 / 封装 / "
                "测定 / 评定 / 复合相变 等)\n")
    md.append("- 或来自 anchor 论文 (`" + str(sel.get(
        "selected_family_name", "")) + "`)\n\n")
    md.append("### 2.2 名称统一 (spec 二)\n\n")
    md.append("每条方法生成 `canonical_method_name`, 遵循:\n\n")
    md.append("- **去除**作者/机构/引用编号前缀 (例: '孙建忠等[29] 扩散-渗出圈法' → '扩散-渗出圈法评定相变材料稳定性')\n")
    md.append("- **保留**材料 / 工艺 / 结构 / 目标\n")
    md.append("- **通用词相同不视为同一方法**: 'DSC 测试' 在不同材料体系里保持独立\n")
    md.append("- **不回写 Stage A 全量方法表**: 归一化仅在案例层, 全量表保持不变\n\n")
    md.append("产物: `lineage_methods_normalized.csv` + `lineage_name_mapping.csv`\n\n")

    md.append("## 三. 最早可追溯来源 (spec 四)\n\n")
    md.append(f"> {earliest['canonical_note']}\n\n")
    md.append(f"### 节点属性\n\n")
    md.append(f"- **canonical_method_name**: `{earliest['earliest_traceable_method']}`\n")
    md.append(f"- **author**: {earliest['earliest_traceable_author']}\n")
    md.append(f"- **year**: **{earliest['earliest_traceable_year']}**\n")
    md.append(f"- **year_source**: `{earliest['year_source']}`\n")
    md.append(f"- **paper_id (本研究数据集内)**: `{earliest['paper_id']}`\n")
    md.append(f"- **kind**: {earliest['kind']}\n")
    md.append(f"- **source_status**: `{earliest['source_status']}`\n")
    if earliest.get("source_reference_text"):
        md.append(f"- **参考条目文本**: `{earliest['source_reference_text'][:250]}`\n")
    md.append(f"\n**边界声明**: {earliest['limitation_note']}\n\n")

    md.append("## 四. 主要演化阶段\n\n")
    md.append("按年份对该家族的方法归纳出以下阶段 (仅供论文叙述, "
                "非严格严格演化关系):\n\n")
    stages = defaultdict(list)
    for m in methods:
        y = m.get("year")
        if not y: continue
        try: yv = int(y)
        except ValueError: continue
        if yv < 2010: bucket = "早期 (~2010)"
        elif yv < 2016: bucket = "2010–2015"
        elif yv < 2020: bucket = "2016–2019"
        elif yv < 2023: bucket = "2020–2022"
        else: bucket = "2023–至今"
        stages[bucket].append((yv, m))
    stage_order = ["早期 (~2010)", "2010–2015", "2016–2019",
                     "2020–2022", "2023–至今"]
    for bucket in stage_order:
        rows = stages.get(bucket, [])
        if not rows: continue
        rows.sort(key=lambda x: x[0])
        md.append(f"### {bucket} ({len(rows)} 条)\n\n")
        for yv, m in rows[:6]:
            md.append(f"- **{yv}**: `{m.get('canonical_method_name','')[:60]}` "
                        f"[{m['kind']}, target={m.get('target_problem') or '-'}]\n")
        if len(rows) > 6:
            md.append(f"- *(该阶段还有 {len(rows) - 6} 条, 详见 "
                        "`lineage_methods_normalized.csv`)*\n")
        md.append("\n")

    md.append("## 五. Confirmed 关系\n\n")
    md.append(f"实线, 严格证据支持. 共 **{len(confirmed)}** 条.\n\n")
    for e in confirmed:
        md.append(f"- **{e.get('relation','?')}**: `"
                    f"{e.get('from_method_name','?')[:35]}` → `"
                    f"{e.get('to_method_name','?')[:35]}`\n")
        if e.get("from_year") or e.get("to_year"):
            md.append(f"  - 时序: from_year={e.get('from_year','?')}, "
                        f"to_year={e.get('to_year','?')}\n")
        if e.get("direction_basis"):
            md.append(f"  - direction_basis: {e['direction_basis'][:200]}\n")
        sids = _parse_sids(e.get("relation_evidence_sentence_ids", ""))
        if sids:
            md.append(f"  - evidence: {sids}\n")
        md.append("\n")

    md.append("## 六. Candidate 关系\n\n")
    md.append(f"虚线, 核心相关 + 年份合理但**无原文关系句**. 共 "
                f"**{len(candidate)}** 条.\n\n")
    md.append("**声明**: 候选关系**不进入正式关系统计**. "
                "禁止基于此宣称任何具体演化.\n\n")
    for e in candidate:
        md.append(f"- 从 `{e.get('from_method_name','')[:35]}` "
                    f"({e.get('from_year','?')}) → 到 "
                    f"`{e.get('to_method_name','')[:35]}` "
                    f"({e.get('to_year','?')})\n")
        md.append(f"  - 相似度提示: `{e.get('similarity_hint','')}` "
                    f"| core_process=`{e.get('core_process','')}` "
                    f"| core_material=`{e.get('core_material','')}`\n\n")

    md.append("## 七. 原文证据\n\n")
    md.append("Confirmed 关系的原文证据句请见 `lineage_evidence.md` 与 "
                "`final_case/final_storage_case_evidence.md`.\n\n")
    md.append("最早可追溯节点 `孙建忠等[29] 扩散-渗出圈法` "
                "的原文证据 (来源论文 `脂肪类复合相变储能材料中脂肪酸最佳质量含量的确定方法`):\n\n")
    md.append("- `introduction_p8_s7`:\n")
    md.append("  > 「孙建忠等[29]进行了建材用相变工质材料渗出程度评价方法的研究, "
                "提出了用扩散-渗出圈法来评定建材用复合相变材料的稳定性, "
                "Zhou等[30]借鉴这种方法确定了肉豆蔻酸/膨胀石墨(MA/EG)"
                "复合相变材料中肉豆蔻酸的最佳质量含量.」\n\n")
    md.append("- 参考文献表内条目 [29] (从原文引用参考文献表解析): "
                "作者 = 孙建忠, 年份 = 2004\n\n")

    md.append("## 八. 路线图解释\n\n")
    md.append("交互式谱系图: `lineage_graph.html` (自包含, 双击浏览器打开即可)\n\n")
    md.append("### 布局\n\n")
    md.append("- **横轴**: 严格按年份, 从 2004 到最新. 无年份节点放右侧独立'年份未知'区.\n")
    md.append("- **纵向**: 按 `target_problem` 分层 (渗漏防治 / 最佳含量测定 / 热导率提升 / 循环稳定性 / "
                "过冷抑制 / 相分离控制 / 定形封装 / 测试方法建立 / 热存储密度).\n")
    md.append("- **节点大小**: 最早可追溯节点用大号星形 ★, 其他节点为小圆圈.\n")
    md.append("- **节点颜色**: 蓝色 = own (本文原创); 灰色 = referenced (前人).\n\n")
    md.append("### 边\n\n")
    md.append("- 实线 (箭头) = confirmed (EXTENDS 蓝 / IMPROVES 绿 / ADAPTS 橙 / REPLACES 红)\n")
    md.append("- 虚线 (灰) = candidate\n\n")
    md.append("### 交互\n\n")
    md.append("- 悬停节点 → 完整方法名 / 作者 / 年份 / 来源论文\n")
    md.append("- 点击节点 → 下方面板显示原文证据句\n\n")

    md.append("## 九. 数据集边界\n\n")
    md.append("- 全部演化关系与最早可追溯来源, 仅适用于**本研究 337 篇既有中文文献 + 其可解析引用范围**\n")
    md.append("- referenced 方法的**原始论文未被下载或核验** — 只反映当前文献里的转述\n")
    md.append("- 年份来源**只有 4 类**: (1) 论文自身发表年 (2) 作者+年份直写 (3) 参考文献条目年份 (4) 无法解析\n")
    md.append("- **禁止**: 用综述发表年份代替被引方法年份; 猜年份; 联网搜索\n")
    md.append("- 无年份的方法**不进入时间线判定**, 仅列在图右侧独立区\n")
    md.append("- Candidate 关系**永不宣称**为演化, 只作图上标记 + 论文中透明汇报\n")
    md.append("- **不声称全球首次提出**; 只说'本数据集内最早可追溯来源'\n\n")

    md.append("## 十. 可直接放入论文的案例结论\n\n")
    md.append("> **可直接引用于论文正文的案例结论段落**:\n\n")
    md.append("> 在本研究 337 篇文献及其可解析引用范围内, "
                f"最早可追溯的**相变材料渗漏评定方法**为 **孙建忠等 (2004)** "
                "提出的**扩散-渗出圈法**, 用于建材用复合相变材料的稳定性评定. "
                "该方法在 2013 年被 Zhou 等借鉴 (ADAPTS 关系, 严格证据支持), "
                "用于确定 MA/EG (肉豆蔻酸/膨胀石墨) 复合相变材料中肉豆蔻酸的"
                "最佳质量含量; 相关技术分支在 2015–2025 期间延伸至微胶囊化、"
                "熔融共混、原位聚合等多种工艺分支, 覆盖建材节能、工业蓄热、"
                "冷链、热管理等应用. "
                "**该结论仅基于本数据集内可解析证据, 未追溯外部原始文献, "
                "亦未声称全球首次提出**.\n\n")

    md.append("---\n\n## 附. 数据文件\n\n")
    md.append("- 家族选择: `lineage_family_candidates.csv/.md`, "
                "`lineage_selected_family.json`\n")
    md.append("- 名称统一: `lineage_methods_normalized.csv`, "
                "`lineage_name_mapping.csv`\n")
    md.append("- 最早来源: `lineage_earliest_source.json`\n")
    md.append("- 关系: `lineage_edges_confirmed.csv`, "
                "`lineage_edges_candidate.csv`\n")
    md.append("- 证据: `lineage_evidence.md`\n")
    md.append("- 图: `lineage_graph.html` (交互), `lineage_graph.png` (静态), "
                "`lineage_graph_data.json`\n")
    md.append("- 图例: `lineage_legend.md`\n")
    md.append("- 系统入口: `lineage_lookup.py` (CLI, 见下)\n")

    with open(os.path.join(OUT_DIR, "method_lineage_case_study.md"),
                "w", encoding="utf-8") as f:
        f.writelines(md)
    print(f"wrote method_lineage_case_study.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
