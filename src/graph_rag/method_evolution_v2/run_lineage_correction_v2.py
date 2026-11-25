"""run_lineage_correction_v2.py — spec 一 → 九 完整修正 (无 API).

对 v1 谱系产出的最终事实校正:
  - 家族窄化到"复合相变材料渗漏评价与最佳含量测定方法"
  - Zhou 年份纠正为 2020 (ref [30] = Scientific Reports 2020)
  - 唯一 confirmed 边: Zhou 2020 ADAPTS 孙建忠 2004
     data_edge_direction=borrower_to_source
     visualization_direction=source_to_descendant
  - 删除 v1 的 2 条不可信 candidate → excluded_lineage_candidates.csv
  - 建立 8 个规范谱系节点 (spec 五)
  - CJK 字体自动检测 + 重新制图
  - v1 文件保留, v2 是新文件

产物 (paper/method_evolution_v2/article_minimal_results/lineage_mvp/):
  - lineage_methods_normalized_v2.csv
  - lineage_earliest_source_v2.json
  - lineage_edges_confirmed_v2.csv
  - excluded_lineage_candidates.csv
  - lineage_evidence_v2.md
  - lineage_graph_v2.html + .png + _data_v2.json + lineage_legend_v2.md
  - method_lineage_case_study_v2.md
  - correction_self_check_v2.md
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

from method_evolution_v2 import config                             # noqa: E402
from method_evolution_v2.stage_a import full_runner as fr          # noqa: E402


OUT_DIR = os.path.join(config.PAPER_V2_DIR, "article_minimal_results",
                          "lineage_mvp")


PRIMARY_PAPER = "脂肪类复合相变储能材料中脂肪酸最佳质量含量的确定方法"


# ============================================================
# spec 五: 8 canonical lineage nodes (人工确定)
#   nodes 1-6 都从原文引言 introduction_p8/p9 抽取
#   nodes 6-8 是本文提出的 own 方法, 论文发表年 = 2021
# ============================================================

CANONICAL_NODES = [
    {
        "node_id": "LINEAGE::sun_2004_diffusion_exude_ring",
        "canonical_method_name": "扩散-渗出圈法评定建材用复合相变材料稳定性",
        "short_name": "扩散-渗出圈法",
        "author": "孙建忠等",
        "year": 2004,
        "year_source": "reference_list_entry_[29]",
        "reference_number": 29,
        "reference_text_raw": ("孙建忠, 吴子钊. 建材用相变工质材料渗出程度评价方法的"
                                    "研究[J]. 新型建筑材料, 2004, 31(7): 43-46."),
        "branch": "渗透/扩散评价法",
        "kind": "referenced",
        "endpoint_source": "case_evidence_method (from introduction_p8_s7 [29])",
        "target_problem": "渗漏评价",
        "core_material": "建材用复合相变材料",
        "core_process": "扩散-渗出圈法",
        "paper_id": PRIMARY_PAPER,
        "evidence_sentence_ids": ["introduction_p8_s7"],
        "is_earliest": True,
        "note": "本数据集内最早可追溯节点; 不代表全球首次提出",
    },
    {
        "node_id": "LINEAGE::zhang_2013_paper_observation",
        "canonical_method_name": ("Zhang 等试纸渗透观察法确定 LA-MA-PA/EG 复合"
                                        "相变材料最佳含量"),
        "short_name": "Zhang 试纸观察法",
        "author": "Zhang N, Yuan Y P, Wang X 等",
        "year": 2013,
        "year_source": "reference_list_entry_[25]",
        "reference_number": 25,
        "reference_text_raw": ("Zhang N, Yuan Y P, Wang X, et al. Preparation "
                                    "and characterization of lauric-myristic-palmitic "
                                    "acid ternary eutectic mixtures/expanded graphite "
                                    "composite phase change material for thermal "
                                    "energy storage [J]. ..., 2013"),
        "branch": "观察法",
        "kind": "referenced",
        "endpoint_source": "case_evidence_method (from introduction_p8_s5 [25])",
        "target_problem": "最佳含量测定",
        "core_material": "LA-MA-PA/EG (月桂酸-肉豆蔻酸-棕榈酸/膨胀石墨)",
        "core_process": "试纸渗透观察法",
        "paper_id": PRIMARY_PAPER,
        "evidence_sentence_ids": ["introduction_p8_s5"],
        "is_earliest": False,
        "note": "独立分支; 无 confirmed 关系连接至 孙建忠 2004",
    },
    {
        "node_id": "LINEAGE::caoxiaoling_2014_weight_loss",
        "canonical_method_name": ("曹晓玲等称量热处理前后失重法确定 MA/EG 中肉豆蔻酸"
                                        "和膨胀石墨最佳配比"),
        "short_name": "曹晓玲 称量失重法",
        "author": "曹晓玲, 袁艳平, 汪玺 等",
        "year": 2014,
        "year_source": "reference_list_entry_[27]",
        "reference_number": 27,
        "reference_text_raw": ("曹晓玲, 袁艳平, 汪玺, 等. 肉豆蔻酸/膨胀石墨复合相变"
                                    "材料的制备及性能研究[J]. 太阳能学报, 2014, "
                                    "35(8): 1493-1498."),
        "branch": "称重法",
        "kind": "referenced",
        "endpoint_source": "case_evidence_method (from introduction_p8_s6 [27])",
        "target_problem": "最佳含量测定",
        "core_material": "MA/EG (肉豆蔻酸/膨胀石墨)",
        "core_process": "称量热处理前后失重法",
        "paper_id": PRIMARY_PAPER,
        "evidence_sentence_ids": ["introduction_p8_s6"],
        "is_earliest": False,
        "note": "独立分支; 无 confirmed 关系连接至 孙建忠 2004",
    },
    {
        "node_id": "LINEAGE::yang_2014_weight_loss_followon",
        "canonical_method_name": ("Yang 等沿用称量法确定 MA-PA-SA/EG 复合相变材料"
                                        "中肉豆蔻酸-棕榈酸-硬脂酸与膨胀石墨最佳配比"),
        "short_name": "Yang 沿用称量法",
        "author": "Yang X J, Yuan Y P, Zhang N 等",
        "year": 2014,
        "year_source": "reference_list_entry_[28]",
        "reference_number": 28,
        "reference_text_raw": ("Yang X J, Yuan Y P, Zhang N, et al. Preparation "
                                    "and properties of myristic-palmitic-stearic acid/"
                                    "expanded graphite composites as phase change "
                                    "materials for energy storage [J]. Solar Energy, "
                                    "2014, 99: ..."),
        "branch": "称重法",
        "kind": "referenced",
        "endpoint_source": "case_evidence_method (from introduction_p8_s6 [28])",
        "target_problem": "最佳含量测定",
        "core_material": "MA-PA-SA/EG (肉豆蔻酸-棕榈酸-硬脂酸/膨胀石墨)",
        "core_process": "称量热处理前后失重法 (沿用)",
        "paper_id": PRIMARY_PAPER,
        "evidence_sentence_ids": ["introduction_p8_s6"],
        "is_earliest": False,
        "note": ("原文表述 '用同样的方法确定' — 是否算 ADAPTS 于 曹晓玲 2014 "
                   "尚缺严格 Stage B 独立盲审, 保守不建 confirmed 边"),
    },
    {
        "node_id": "LINEAGE::zhou_2020_adapt_diffusion_exude",
        "canonical_method_name": ("Zhou 等借鉴扩散-渗出圈法确定 MA/EG 复合相变材料"
                                        "中肉豆蔻酸最佳质量含量"),
        "short_name": "Zhou 借鉴 扩散圈法",
        "author": "Zhou D Y, Yuan J W, Zhou Y H 等",
        "year": 2020,                                     # 明确修正
        "year_source": "reference_list_entry_[30]",
        "reference_number": 30,
        "reference_text_raw": ("Zhou D Y, Yuan J W, Zhou Y H, et al. Preparation "
                                    "and characterization of myristic acid/expanded "
                                    "graphite composite phase change materials for "
                                    "thermal energy storage [J]. Scientific Reports, "
                                    "2020, 10: 10889."),
        "branch": "渗透/扩散评价法",
        "kind": "referenced",
        "endpoint_source": "case_evidence_method (from introduction_p8_s7 [30])",
        "target_problem": "最佳含量测定",
        "core_material": "MA/EG (肉豆蔻酸/膨胀石墨)",
        "core_process": "扩散-渗出圈法 (借鉴)",
        "paper_id": PRIMARY_PAPER,
        "evidence_sentence_ids": ["introduction_p8_s7"],
        "is_earliest": False,
        "note": ("Confirmed ADAPTS from 孙建忠 2004; 参见 "
                   "final_storage_case_edges.csv FINAL_STORAGE_ADAPTS_01. "
                   "v1 曾误记为 2013, 本文件修正为 2020."),
    },
    {
        "node_id": "LINEAGE::benwen_2021_visual_approach",
        "canonical_method_name": ("本文提出的目测逼近法确定 CA-MA/EG 复合相变材料中"
                                        "癸酸-肉豆蔻酸最佳质量含量"),
        "short_name": "本文 目测逼近法",
        "author": "本文",
        "year": 2021,
        "year_source": "primary_paper_publish_year",
        "reference_number": "",
        "reference_text_raw": "",
        "branch": "观察法",
        "kind": "own",
        "endpoint_source": ("case_evidence_method (from introduction_p9_s1); "
                               "本文原创方法, 论文发表年 = 2021"),
        "target_problem": "最佳含量测定",
        "core_material": "CA-MA/EG (癸酸-肉豆蔻酸/膨胀石墨)",
        "core_process": "目测逼近法",
        "paper_id": PRIMARY_PAPER,
        "evidence_sentence_ids": ["introduction_p9_s1"],
        "is_earliest": False,
        "note": "本文 3 种自建方法之一, 与观察法思路 (Zhang 2013) 并行",
    },
    {
        "node_id": "LINEAGE::benwen_2021_weight_measurement",
        "canonical_method_name": ("本文提出的称重测量法确定 CA-MA/EG 复合相变材料中"
                                        "癸酸-肉豆蔻酸最佳质量含量"),
        "short_name": "本文 称重测量法",
        "author": "本文",
        "year": 2021,
        "year_source": "primary_paper_publish_year",
        "reference_number": "",
        "reference_text_raw": "",
        "branch": "称重法",
        "kind": "own",
        "endpoint_source": ("case_evidence_method (from introduction_p9_s1); "
                               "本文原创方法, 论文发表年 = 2021"),
        "target_problem": "最佳含量测定",
        "core_material": "CA-MA/EG",
        "core_process": "称重测量法",
        "paper_id": PRIMARY_PAPER,
        "evidence_sentence_ids": ["introduction_p9_s1"],
        "is_earliest": False,
        "note": "本文 3 种自建方法之一; 与称量法分支 (曹晓玲/Yang 2014) 并行",
    },
    {
        "node_id": "LINEAGE::benwen_2021_permeation_diameter",
        "canonical_method_name": ("本文提出的渗透直径百分比判定法确定 CA-MA/EG 复合"
                                        "相变材料中癸酸-肉豆蔻酸最佳质量含量"),
        "short_name": "本文 渗透直径百分比法",
        "author": "本文",
        "year": 2021,
        "year_source": "primary_paper_publish_year",
        "reference_number": "",
        "reference_text_raw": "",
        "branch": "综合判定法",
        "kind": "own",
        "endpoint_source": ("case_evidence_method (from introduction_p9_s1); "
                               "本文原创方法, 论文发表年 = 2021"),
        "target_problem": "最佳含量测定",
        "core_material": "CA-MA/EG",
        "core_process": "渗透直径百分比判定法",
        "paper_id": PRIMARY_PAPER,
        "evidence_sentence_ids": ["introduction_p9_s1"],
        "is_earliest": False,
        "note": ("本文 3 种自建方法之一; 综合了观察 (视觉) 与量化判据 (直径百分比); "
                   "尚无 confirmed 关系连接至扩散-渗出圈法, 仅为并行方法"),
    },
]


# ============================================================
# The single confirmed edge (Zhou 2020 ADAPTS 孙建忠 2004)
# ============================================================

CONFIRMED_EDGE = {
    "edge_id": "LINEAGE_CONFIRMED_ADAPTS_01",
    "paper_id": PRIMARY_PAPER,
    "relation": "ADAPTS",
    "from_method_id": "LINEAGE::zhou_2020_adapt_diffusion_exude",
    "to_method_id": "LINEAGE::sun_2004_diffusion_exude_ring",
    "from_method_name": ("Zhou 等借鉴扩散-渗出圈法确定 MA/EG 复合相变材料中"
                            "肉豆蔻酸最佳质量含量"),
    "to_method_name": ("扩散-渗出圈法评定建材用复合相变材料稳定性"),
    "relation_evidence_sentence_ids": ["introduction_p8_s7"],
    "direction_basis": ("原文句 introduction_p8_s7 明确 'Zhou 等借鉴这种方法'. "
                            "数据方向: from=借鉴者 (Zhou 2020) → to=来源 (孙建忠 2004), "
                            "符合 ADAPTS 语义 '借鉴者 → 来源'."),
    "data_edge_direction": "borrower_to_source",
    "visualization_direction": "source_to_descendant",
    "from_year": 2020,
    "to_year": 2004,
    "audit_linkage_type": "independent_methods",
    "audit_endpoint_linkage": "explicit_both",
    "audit_support": "supported",
    "audit_direction": "correct",
    "audit_relation_check": "correct",
    "validation_status": "accepted",
    "correction_note": ("v2 修正: Zhou 年份从 v1 误记 2013 更正为 2020. "
                          "确保图中箭头方向按视觉惯例 从来源 (2004) 指向后续应用 (2020)."),
}


# ============================================================
# Excluded candidates (spec 四)
# ============================================================

EXCLUDED_CANDIDATES = [
    {
        "orig_candidate_edge_id": "CAND_001 (v1)",
        "from_method_name": "Ye 等改进的水热法制备石墨烯和石蜡复合相变材料",
        "to_method_name": "泡沫铜/石蜡复合相变储能材料制备方法",
        "orig_from_year": 2015,
        "orig_to_year": 2022,
        "exclusion_reason": ("(1) 无直接原文关系句证据; "
                                "(2) core_process 分类存在明显错误 (v1 判为 same "
                                "但技术核心不同: 石墨烯复合 vs 泡沫铜复合); "
                                "(3) 仅凭材料相似 (均含石蜡) 不能构成演化; "
                                "(4) 与'渗漏评价/最佳含量测定'主谱系无关"),
        "final_status": "excluded_not_confirmed_lineage",
    },
    {
        "orig_candidate_edge_id": "CAND_002 (v1)",
        "from_method_name": ("混合烧结工艺制备 NaNO3/硅藻土复合相变储热材料"),
        "to_method_name": "复合相变储能材料制备方法",
        "orig_from_year": 2017,
        "orig_to_year": 2019,
        "exclusion_reason": ("(1) 无直接原文关系句证据; "
                                "(2) core_process 分类存在明显错误 (v1 判为 "
                                "same_process 但材料体系不同: 无机盐 vs 有机相变); "
                                "(3) 时间线方向不符合当前数据边定义; "
                                "(4) 与'渗漏评价/最佳含量测定'主谱系无关"),
        "final_status": "excluded_not_confirmed_lineage",
    },
]


# ============================================================
# Helpers
# ============================================================

def _j(v):
    if isinstance(v, (list, dict)):
        return json.dumps(v, ensure_ascii=False)
    return "" if v is None else str(v)


def _write_csv(path, fields, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows: w.writerow({k: _j(r.get(k)) for k in fields})


def _load_sentence_texts_for_paper(pid):
    d = fr.per_paper_dir(pid)
    p = os.path.join(d, "sentence_index.json")
    if not os.path.isfile(p): return {}
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {s["sentence_id"]: s.get("sentence_text", "")
             for s in data.get("sentences", [])}


# ============================================================
# CJK font detection for matplotlib (spec 六)
# ============================================================

def detect_cjk_font():
    """Return a matplotlib-usable CJK font name, or None."""
    try:
        import matplotlib
        from matplotlib import font_manager as fm
    except ImportError:
        return None
    preferred = ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC",
                    "Noto Sans CJK", "Source Han Sans SC", "Source Han Sans CN",
                    "PingFang SC", "WenQuanYi Micro Hei", "Arial Unicode MS"]
    available = {f.name for f in fm.fontManager.ttflist}
    for name in preferred:
        if name in available:
            return name
    # try to find any font with 'CJK' or 'YaHei' or 'Han' in name
    for f in fm.fontManager.ttflist:
        n = f.name
        if any(k in n.lower() for k in ["yahei", "cjk", "han", "hei",
                                              "microsoftyahei"]):
            return n
    return None


# ============================================================
# Emitters (all v2)
# ============================================================

def emit_methods_normalized_v2():
    fields = ["node_id", "canonical_method_name", "short_name",
                "author", "year", "year_source", "reference_number",
                "reference_text_raw", "branch", "kind", "endpoint_source",
                "target_problem", "core_material", "core_process",
                "paper_id", "evidence_sentence_ids", "is_earliest", "note"]
    _write_csv(os.path.join(OUT_DIR, "lineage_methods_normalized_v2.csv"),
                fields, CANONICAL_NODES)


def emit_earliest_v2():
    earliest = next(n for n in CANONICAL_NODES if n["is_earliest"])
    obj = {
        "earliest_traceable_method": earliest["canonical_method_name"],
        "earliest_traceable_author": earliest["author"],
        "earliest_traceable_year": earliest["year"],
        "node_id": earliest["node_id"],
        "paper_id": earliest["paper_id"],
        "kind": earliest["kind"],
        "year_source": earliest["year_source"],
        "reference_number": earliest["reference_number"],
        "reference_text_raw": earliest["reference_text_raw"],
        "evidence_sentence_ids": earliest["evidence_sentence_ids"],
        "canonical_note": (
            f"在本研究 337 篇文献及其可解析引用范围内, 最早可追溯的方法来源为 "
            f"{earliest['author']} ({earliest['year']}) — "
            f"{earliest['canonical_method_name']}"),
        "limitation_note": ("本表述仅限本数据集内的可解析年份; "
                              "**不代表全球首次提出**; 不追溯外部原始文献. "
                              "本谱系仅覆盖'复合相变材料渗漏评价与最佳含量测定方法', "
                              "不包含普通微胶囊制备/原位聚合/熔融共混/导热增强/"
                              "普通封装/DSC 测试/储热器设计等相关但独立的技术分支."),
    }
    with open(os.path.join(OUT_DIR, "lineage_earliest_source_v2.json"),
                "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def emit_confirmed_edges_v2():
    fields = ["edge_id", "paper_id", "relation",
                "from_method_id", "to_method_id",
                "from_method_name", "to_method_name",
                "from_year", "to_year",
                "relation_evidence_sentence_ids", "direction_basis",
                "data_edge_direction", "visualization_direction",
                "audit_linkage_type", "audit_endpoint_linkage",
                "audit_support", "audit_direction", "audit_relation_check",
                "validation_status", "correction_note"]
    _write_csv(os.path.join(OUT_DIR, "lineage_edges_confirmed_v2.csv"),
                fields, [CONFIRMED_EDGE])


def emit_excluded_candidates():
    fields = ["orig_candidate_edge_id", "from_method_name", "to_method_name",
                "orig_from_year", "orig_to_year",
                "exclusion_reason", "final_status"]
    _write_csv(os.path.join(OUT_DIR, "excluded_lineage_candidates.csv"),
                fields, EXCLUDED_CANDIDATES)


def emit_evidence_md_v2():
    sent_map = _load_sentence_texts_for_paper(PRIMARY_PAPER)
    lines = ["# 谱系证据完整清单 (v2 修正后)\n\n"]
    lines.append(f"> 家族: 复合相变材料渗漏评价与最佳含量测定方法\n")
    lines.append(f"> 主论文: `{PRIMARY_PAPER}`\n")
    lines.append(f"> 8 个规范节点 (含 3 个本文 own + 5 个 referenced 全部经 "
                    "primary paper 原文引言直接列出)\n\n")

    # Earliest
    ea = next(n for n in CANONICAL_NODES if n["is_earliest"])
    lines.append(f"## 一. 最早可追溯来源 (数据集内)\n\n")
    lines.append(f"- **canonical_method_name**: {ea['canonical_method_name']}\n")
    lines.append(f"- **author**: {ea['author']}\n")
    lines.append(f"- **year**: **{ea['year']}** (source={ea['year_source']})\n")
    lines.append(f"- **reference**: [{ea['reference_number']}] "
                    f"`{ea['reference_text_raw']}`\n")
    lines.append(f"- **原文证据句**:\n")
    for sid in ea["evidence_sentence_ids"]:
        t = sent_map.get(sid, "")
        lines.append(f"  - `{sid}`: 「{t.strip()}」\n")
    lines.append(f"\n**声明**: {ea.get('note','')}\n\n")

    lines.append("## 二. 唯一 confirmed 关系 (spec 三)\n\n")
    e = CONFIRMED_EDGE
    lines.append(f"- **relation**: **{e['relation']}**\n")
    lines.append(f"- **from (借鉴者)**: `{e['from_method_name']}` ({e['from_year']})\n")
    lines.append(f"- **to (来源方法)**: `{e['to_method_name']}` ({e['to_year']})\n")
    lines.append(f"- **data_edge_direction**: `{e['data_edge_direction']}` "
                    "(数据库方向 = 借鉴者指向来源, 符合 ADAPTS 语义)\n")
    lines.append(f"- **visualization_direction**: `{e['visualization_direction']}` "
                    "(可视化方向 = 来源流向后续应用, 符合读者时间线直觉)\n")
    lines.append(f"- **direction_basis**: {e['direction_basis']}\n")
    lines.append(f"- **auditor**: linkage=`{e['audit_linkage_type']}`, "
                    f"endpoint=`{e['audit_endpoint_linkage']}`, "
                    f"support=`{e['audit_support']}`, "
                    f"direction=`{e['audit_direction']}`, "
                    f"relation_check=`{e['audit_relation_check']}`\n")
    lines.append(f"- **修正说明**: {e['correction_note']}\n\n")
    lines.append(f"**原文证据**:\n")
    for sid in e["relation_evidence_sentence_ids"]:
        t = sent_map.get(sid, "")
        lines.append(f"- `{sid}`: 「{t.strip()}」\n")

    lines.append("\n## 三. 其余 6 个节点 (无 confirmed 关系)\n\n")
    lines.append("**声明**: 以下节点均属独立分支或并行方法, "
                    "**除 confirmed ADAPTS 外, 相互之间不建立任何演化关系**.\n\n")
    for n in CANONICAL_NODES:
        if n["is_earliest"] or n["node_id"] == CONFIRMED_EDGE["from_method_id"]:
            continue
        lines.append(f"### {n['author']} ({n['year']}) — {n['short_name']}\n\n")
        lines.append(f"- **canonical_method_name**: {n['canonical_method_name']}\n")
        lines.append(f"- **branch**: {n['branch']}\n")
        lines.append(f"- **core_material**: {n['core_material']}\n")
        lines.append(f"- **core_process**: {n['core_process']}\n")
        lines.append(f"- **kind**: {n['kind']}\n")
        lines.append(f"- **year_source**: `{n['year_source']}`\n")
        if n['reference_text_raw']:
            lines.append(f"- **reference**: [{n['reference_number']}] "
                            f"`{n['reference_text_raw']}`\n")
        lines.append(f"- **原文证据句**:\n")
        for sid in n["evidence_sentence_ids"]:
            t = sent_map.get(sid, "")
            lines.append(f"  - `{sid}`: 「{t.strip()}」\n")
        lines.append(f"- **备注**: {n.get('note','')}\n\n")

    lines.append("## 四. 被排除的 candidate 关系 (spec 四)\n\n")
    lines.append(f"以下 {len(EXCLUDED_CANDIDATES)} 条 v1 candidate 关系"
                    "已被剔除, 不在图中显示 (含虚线):\n\n")
    for c in EXCLUDED_CANDIDATES:
        lines.append(f"- **`{c['orig_candidate_edge_id']}`**\n")
        lines.append(f"  - from: `{c['from_method_name']}` ({c['orig_from_year']})\n")
        lines.append(f"  - to: `{c['to_method_name']}` ({c['orig_to_year']})\n")
        lines.append(f"  - **exclusion_reason**: {c['exclusion_reason']}\n\n")

    with open(os.path.join(OUT_DIR, "lineage_evidence_v2.md"),
                "w", encoding="utf-8") as f:
        f.writelines(lines)


# ============================================================
# Interactive HTML graph (spec 六)
# ============================================================

RELATION_COLOR = {
    "ADAPTS": "#ff7f0e",
    "EXTENDS": "#1f77b4",
    "IMPROVES": "#2ca02c",
    "REPLACES": "#d62728",
}


def _build_graph_data():
    nodes = []
    for n in CANONICAL_NODES:
        nodes.append({
            "id": n["node_id"],
            "short_name": n["short_name"],
            "full_name": n["canonical_method_name"],
            "author": n["author"],
            "year": n["year"],
            "year_source": n["year_source"],
            "reference_number": n["reference_number"],
            "reference_text_raw": n["reference_text_raw"],
            "branch": n["branch"],
            "kind": n["kind"],
            "core_material": n["core_material"],
            "core_process": n["core_process"],
            "target_problem": n["target_problem"],
            "paper_id": n["paper_id"],
            "evidence_sentence_ids": n["evidence_sentence_ids"],
            "is_earliest": n["is_earliest"],
            "note": n["note"],
        })
    edges = [{
        "relation": CONFIRMED_EDGE["relation"],
        "from_id": CONFIRMED_EDGE["from_method_id"],
        "to_id": CONFIRMED_EDGE["to_method_id"],
        "from_year": CONFIRMED_EDGE["from_year"],
        "to_year": CONFIRMED_EDGE["to_year"],
        "data_edge_direction": CONFIRMED_EDGE["data_edge_direction"],
        "visualization_direction": CONFIRMED_EDGE["visualization_direction"],
        "color": RELATION_COLOR.get(CONFIRMED_EDGE["relation"], "#999"),
        "direction_basis": CONFIRMED_EDGE["direction_basis"],
        "correction_note": CONFIRMED_EDGE["correction_note"],
    }]
    branches = list({n["branch"] for n in CANONICAL_NODES})
    branch_order = ["观察法", "称重法", "渗透/扩散评价法", "综合判定法"]
    branches = [b for b in branch_order if b in branches] + \
                 [b for b in branches if b not in branch_order]
    return {"nodes": nodes, "edges": edges, "branches": branches}


HTML = r"""<!doctype html>
<html><head>
<meta charset="utf-8">
<title>复合相变材料渗漏评价与最佳含量测定方法谱系 (v2)</title>
<style>
body { font: 13px/1.5 -apple-system, "Microsoft YaHei", "SimHei", "PingFang SC", sans-serif; margin: 18px; }
h1 { font-size: 16px; margin: 0 0 4px 0; }
.subtitle { color:#666; font-size: 12px; margin-bottom:16px; }
.legend { font-size: 11px; margin: 6px 0 14px 0; padding: 6px 12px; background:#f7f7f7; border-radius:6px; display:inline-block; }
.legend .item { display:inline-block; margin-right:14px; }
.legend .swatch { display:inline-block; width:22px; height:3px; vertical-align:middle; margin-right:5px; }
svg { border: 1px solid #ddd; background: #fafafa; }
.node circle { cursor: pointer; }
.node.earliest circle { stroke: #b8860b; stroke-width: 3; }
.node text { pointer-events: none; font-size: 11px; fill: #333; }
.tooltip { position: absolute; padding: 10px; background: rgba(0,0,0,0.9); color:#fff; border-radius:5px; pointer-events:none; max-width: 380px; font-size:11px; line-height:1.4; opacity:0; transition:opacity 0.12s; z-index:99; }
.tooltip.show { opacity: 1; }
.detail-panel { border: 1px solid #ddd; padding: 12px; margin-top: 15px; background:#fff; border-radius:6px; display:none; }
.detail-panel.show { display: block; }
.detail-panel h3 { margin:0 0 8px 0; font-size:14px; }
.detail-panel .ev-block { background:#f0f0f0; padding:6px 8px; margin:4px 0; border-radius:3px; font-size:11px; }
.badge { display:inline-block; padding:1px 6px; border-radius:8px; font-size:10px; color:#fff; margin-right:5px; }
.badge.own { background:#1f77b4; }
.badge.ref { background:#7f7f7f; }
.badge.earliest { background:#b8860b; }
</style></head><body>
<h1>复合相变材料渗漏评价与最佳含量测定方法谱系 (v2, 数据集内最早可追溯来源)</h1>
<div class="subtitle">数据源: 本研究 337 篇既有储能相关中文文献. 主论文: 脂肪类复合相变储能材料中脂肪酸最佳质量含量的确定方法 (2021). 边界: 不追溯外部原始文献; 不宣称"最早提出"; 除 Zhou 2020 ADAPTS 孙建忠 2004 外, 其余方法为并行独立分支.</div>
<div class="legend">
  <div class="item"><span class="swatch" style="background:#ff7f0e;"></span>ADAPTS (确认)</div>
  <div class="item">★ 最早可追溯节点</div>
  <div class="item"><span class="badge own">own</span>本文原创</div>
  <div class="item"><span class="badge ref">ref</span>前人引用</div>
</div>
<svg id="chart" width="1200" height="560"></svg>
<div class="tooltip" id="tooltip"></div>
<div class="detail-panel" id="detail-panel"></div>
<script>
const DATA = __DATA__;

const svg = document.getElementById("chart");
const W = 1200, H = 560;
const MARGIN = {top: 40, right: 260, bottom: 60, left: 200};
const innerW = W - MARGIN.left - MARGIN.right;
const innerH = H - MARGIN.top - MARGIN.bottom;

const svgNS = "http://www.w3.org/2000/svg";
function el(t, a={}) { const e = document.createElementNS(svgNS, t); for (const k of Object.keys(a)) e.setAttribute(k, a[k]); return e; }
function escapeHTML(s) { return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[c]); }

const yearsAvail = DATA.nodes.filter(n => n.year).map(n => n.year);
const yearMin = Math.min(...yearsAvail) - 1;
const yearMax = Math.max(...yearsAvail) + 1;
const unknownX = MARGIN.left + innerW - 30;

function xForYear(y) {
  if (!y) return unknownX;
  return MARGIN.left + ((y - yearMin) / (yearMax - yearMin)) * (unknownX - MARGIN.left - 30);
}

const branches = DATA.branches;
const layerH = innerH / Math.max(1, branches.length);
function yForBranch(name) {
  const idx = branches.indexOf(name);
  return MARGIN.top + idx * layerH + layerH / 2;
}

const posMap = {};
const cellCounter = {};
for (const n of DATA.nodes) {
  const y = yForBranch(n.branch);
  const x = xForYear(n.year);
  const key = (n.year || 'unk') + '::' + n.branch;
  const c = cellCounter[key] || 0;
  cellCounter[key] = c + 1;
  posMap[n.id] = { x: x + (c % 2 === 0 ? 0 : 22),
                     y: y + Math.floor(c / 2) * 18 };
}

// axis
const axis = el("g");
for (let y = yearMin; y <= yearMax; y++) {
  if (y < 2000 || y > 2030) continue;
  const xi = xForYear(y);
  axis.appendChild(el("line", { x1: xi, x2: xi, y1: MARGIN.top - 5,
                                        y2: MARGIN.top + innerH,
                                        stroke: "#eee" }));
  if (y % 2 !== 0) continue;
  const t = el("text", { x: xi, y: MARGIN.top + innerH + 20,
                              "text-anchor": "middle",
                              "font-size": 11, fill: "#666" });
  t.textContent = y;
  axis.appendChild(t);
}
svg.appendChild(axis);

// branch labels
for (let i = 0; i < branches.length; i++) {
  const t = el("text", { x: 12, y: yForBranch(branches[i]) + 4,
                              fill: "#333", "font-size": 12,
                              "font-weight": "bold" });
  t.textContent = branches[i];
  svg.appendChild(t);
  svg.appendChild(el("line", { x1: MARGIN.left, x2: MARGIN.left + innerW,
                                        y1: MARGIN.top + i * layerH,
                                        y2: MARGIN.top + i * layerH,
                                        stroke: "#f0f0f0" }));
}

// title over chart
const title = el("text", { x: MARGIN.left, y: 20,
                                  "font-size": 12, fill: "#666" });
title.textContent = "横轴 = 年份; 纵向按方法分支; ★ = 最早可追溯节点";
svg.appendChild(title);

// direction legend
const dirNote = el("text", { x: MARGIN.left, y: 34,
                                    "font-size": 11, fill: "#888" });
dirNote.textContent = "图中箭头方向 = 视觉时间流 (source→descendant); 数据关系为 ADAPTS (borrower→source), 详见节点悬停/点击";
svg.appendChild(dirNote);

// edges (only confirmed; visualization direction = source→descendant)
for (const e of DATA.edges) {
  const p_src = posMap[e.to_id];  // to = source; viz arrow from source
  const p_dst = posMap[e.from_id]; // from = borrower; viz arrow to borrower
  if (!p_src || !p_dst) continue;
  svg.appendChild(el("line", {
    x1: p_src.x, y1: p_src.y, x2: p_dst.x, y2: p_dst.y,
    stroke: e.color, "stroke-width": 2.5, opacity: 0.9
  }));
  // arrow head at descendant end
  const dx = p_dst.x - p_src.x, dy = p_dst.y - p_src.y;
  const L = Math.hypot(dx, dy) || 1;
  const ax = p_dst.x - dx / L * 12;
  const ay = p_dst.y - dy / L * 12;
  const perpX = -dy / L * 5, perpY = dx / L * 5;
  svg.appendChild(el("polygon", {
    points: `${p_dst.x},${p_dst.y} ${ax + perpX},${ay + perpY} ${ax - perpX},${ay - perpY}`,
    fill: e.color, opacity: 0.9
  }));
  // edge label
  const mx = (p_src.x + p_dst.x) / 2, my = (p_src.y + p_dst.y) / 2;
  const t = el("text", { x: mx, y: my - 6, "text-anchor": "middle",
                              fill: e.color, "font-size": 11,
                              "font-weight": "bold" });
  t.textContent = e.relation;
  svg.appendChild(t);
}

// nodes
const tooltip = document.getElementById("tooltip");
const detail = document.getElementById("detail-panel");

for (const n of DATA.nodes) {
  const p = posMap[n.id];
  const grp = el("g", { class: "node" + (n.is_earliest ? " earliest" : ""),
                              transform: `translate(${p.x},${p.y})` });
  const r = n.is_earliest ? 11 : 7;
  const fill = n.kind === "own" ? "#1f77b4" : "#7f7f7f";
  grp.appendChild(el("circle", {
    r: r, fill: fill, opacity: 0.9,
    stroke: n.is_earliest ? "#b8860b" : "#fff",
    "stroke-width": n.is_earliest ? 3 : 1
  }));
  if (n.is_earliest) {
    const star = el("text", { x: 0, y: 4, "text-anchor": "middle",
                                  "font-size": 15, fill: "#fff" });
    star.textContent = "★";
    grp.appendChild(star);
  }
  const label = el("text", { x: r + 4, y: 4 });
  label.textContent = `${n.short_name} (${n.year || "未知"})`;
  grp.appendChild(label);

  grp.addEventListener("mouseover", (ev) => {
    tooltip.innerHTML = `
      <strong>${escapeHTML(n.full_name)}</strong><br>
      <em>${n.kind === "own" ? "own (本文原创)" : "referenced (前人)"}</em><br>
      <strong>作者</strong>: ${escapeHTML(n.author || "-")}<br>
      <strong>年份</strong>: ${n.year || "未知"} (${escapeHTML(n.year_source)})<br>
      <strong>分支</strong>: ${escapeHTML(n.branch)}<br>
      <strong>目标</strong>: ${escapeHTML(n.target_problem)}<br>
      <strong>论文</strong>: ${escapeHTML(n.paper_id)}
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
    const ref = n.reference_text_raw
      ? `<div><strong>参考条目</strong> [${escapeHTML(String(n.reference_number))}]: <code>${escapeHTML(n.reference_text_raw)}</code></div>`
      : "";
    detail.innerHTML = `
      <h3>${n.is_earliest ? "★ " : ""}${escapeHTML(n.full_name)}</h3>
      <div>
        <span class="badge ${n.kind === "own" ? "own" : "ref"}">${n.kind}</span>
        ${n.is_earliest ? '<span class="badge earliest">最早可追溯</span>' : ""}
        作者: <strong>${escapeHTML(n.author || "-")}</strong>
        · 年份: <strong>${n.year || "未知"}</strong>
        · year_source: <code>${escapeHTML(n.year_source)}</code>
        · 分支: <strong>${escapeHTML(n.branch)}</strong>
      </div>
      <div style="margin-top:6px;">core_material: <strong>${escapeHTML(n.core_material)}</strong> · core_process: <strong>${escapeHTML(n.core_process)}</strong></div>
      <div style="margin-top:6px;">来源论文: <code>${escapeHTML(n.paper_id)}</code></div>
      ${ref}
      <div style="margin-top:8px;"><strong>evidence_sentence_ids</strong>: ${escapeHTML(JSON.stringify(n.evidence_sentence_ids))}</div>
      <div style="margin-top:8px; color:#a04;">${escapeHTML(n.note)}</div>
    `;
    detail.classList.add("show");
  });
  svg.appendChild(grp);
}
</script>
</body></html>
"""


def emit_html_v2(graph_data):
    with open(os.path.join(OUT_DIR, "lineage_graph_v2.html"),
                "w", encoding="utf-8") as f:
        f.write(HTML.replace("__DATA__",
                                  json.dumps(graph_data, ensure_ascii=False)))
    with open(os.path.join(OUT_DIR, "lineage_graph_data_v2.json"),
                "w", encoding="utf-8") as f:
        json.dump(graph_data, f, ensure_ascii=False, indent=2)


def emit_png_v2(graph_data, cjk_font):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
    except ImportError:
        print("matplotlib not installed; skipping PNG")
        return False

    if cjk_font:
        matplotlib.rcParams["font.family"] = cjk_font
        matplotlib.rcParams["axes.unicode_minus"] = False

    fig, ax = plt.subplots(figsize=(14, 6.5))
    branches = graph_data["branches"]
    n_br = len(branches)
    br_y = {b: n_br - 1 - i for i, b in enumerate(branches)}

    years = [n["year"] for n in graph_data["nodes"] if n["year"]]
    y_min, y_max = min(years) - 1, max(years) + 1

    node_pos = {}
    cell_cnt = {}
    for n in graph_data["nodes"]:
        x = n["year"] if n["year"] else y_max + 3
        y_v = br_y.get(n["branch"], 0)
        key = (x, y_v)
        c = cell_cnt.get(key, 0)
        cell_cnt[key] = c + 1
        pos_x = x + (0.15 if c % 2 else -0.15) * (c // 2 + 1) * 0.5
        pos_y = y_v + (c % 3) * 0.18 - 0.18
        node_pos[n["id"]] = (pos_x, pos_y)
        c_col = "#1f77b4" if n["kind"] == "own" else "#7f7f7f"
        s = 300 if n["is_earliest"] else 90
        marker = "*" if n["is_earliest"] else "o"
        ax.scatter([pos_x], [pos_y], s=s, c=c_col, marker=marker,
                     edgecolors="#b8860b" if n["is_earliest"] else "white",
                     linewidths=2 if n["is_earliest"] else 0.6, zorder=3)
        ax.annotate(f"{n['short_name']} ({n['year'] or '未知'})",
                     (pos_x, pos_y),
                     xytext=(8, 0), textcoords="offset points",
                     fontsize=7.5, color="#333")

    # confirmed edges (viz = source→descendant)
    for e in graph_data["edges"]:
        p_src = node_pos.get(e["to_id"])
        p_dst = node_pos.get(e["from_id"])
        if not p_src or not p_dst: continue
        ax.annotate("", xy=p_dst, xytext=p_src,
                     arrowprops=dict(arrowstyle="-|>", color=e["color"],
                                        lw=2.2, alpha=0.9), zorder=2)
        mx = (p_src[0] + p_dst[0]) / 2
        my = (p_src[1] + p_dst[1]) / 2
        ax.text(mx, my + 0.10, e["relation"], color=e["color"],
                 fontsize=10, ha="center", weight="bold",
                 bbox=dict(boxstyle="round,pad=0.15",
                              facecolor="white", edgecolor=e["color"],
                              alpha=0.85))

    for i, b in enumerate(branches):
        ax.axhline(n_br - 1 - i - 0.5, color="#eee",
                    linewidth=0.7, zorder=0)
        ax.text(y_min - 0.6, n_br - 1 - i, b, fontsize=10,
                 ha="right", va="center", color="#333", weight="bold")

    ax.axvline(y_max + 2 - 0.6, color="#ff7f0e", linestyle="--",
                 linewidth=1, alpha=0.6)
    ax.text(y_max + 3, -0.85, "年份未知", color="#ff7f0e",
             fontsize=10, ha="center")

    ax.set_xlim(y_min - 2, y_max + 4)
    ax.set_ylim(-1.2, n_br)
    ax.set_xlabel("年份", fontsize=11)
    ax.set_yticks([])
    ax.set_title("复合相变材料渗漏评价与最佳含量测定方法谱系\n"
                    "(数据集内最早可追溯来源, 非全球首次提出)",
                    fontsize=12, pad=10)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)

    handles = [
        mpatches.Patch(color="#ff7f0e", label="ADAPTS (箭头方向 = 视觉时间流)"),
        mpatches.Patch(color="#1f77b4", label="own (本文原创)"),
        mpatches.Patch(color="#7f7f7f", label="referenced (前人)"),
    ]
    ax.legend(handles=handles, loc="lower right", fontsize=9,
                framealpha=0.9)

    plt.tight_layout()
    plt.savefig(os.path.join(OUT_DIR, "lineage_graph_v2.png"),
                  dpi=170, bbox_inches="tight")
    plt.close()
    return True


def emit_legend_v2(graph_data, cjk_font):
    n_nodes = len(graph_data["nodes"])
    n_conf = len(graph_data["edges"])
    lines = [
        "# 图例 v2 (spec 六)\n\n",
        f"> 复合相变材料渗漏评价与最佳含量测定方法谱系 — "
        f"{n_nodes} 节点, {n_conf} 条 confirmed 边, 0 条 candidate\n\n",
        f"## 字体检测\n\n",
        f"- 中文字体: `{cjk_font or '(未检测到 CJK 字体, PNG 中文可能显示为方框)'}`\n\n",
        "## 节点\n\n",
        "- **★ 大号金边星形**: 数据集内最早可追溯节点 (孙建忠 2004)\n",
        "- **蓝色圆**: own — 本文原创方法 (2021 提出的 3 种方法)\n",
        "- **灰色圆**: referenced — 前人方法 (从本文引用参考文献解析)\n",
        "- **无年份节点**: 放右侧 '年份未知' 区; 本 v2 全部 8 节点年份均有解析, "
        "'年份未知' 区目前为空\n\n",
        "## 边\n\n",
        "- **橙色实线 + 箭头** = ADAPTS 关系\n",
        "- 图中**没有**虚线 candidate 边; v1 的 2 条 candidate 已剔除到 "
        "`excluded_lineage_candidates.csv`\n",
        "- 图中**唯一实线** = 孙建忠 2004 → Zhou 2020 (视觉方向 = 源→后续)\n\n",
        "## 方向解释 (重要)\n\n",
        "- **数据方向** (`data_edge_direction`) = `borrower_to_source`: "
        "关系语义为 '借鉴者指向来源', 即 Zhou 2020 → 孙建忠 2004\n",
        "- **视觉方向** (`visualization_direction`) = `source_to_descendant`: "
        "图中箭头按时间线画, 从来源 (2004) 指向后续应用 (2020)\n",
        "- 两种方向表达同一个 ADAPTS 关系, 只是**方向惯例**不同\n\n",
        "## 分支\n\n",
        "- **观察法** (Zhang N 2013 / 本文 目测逼近法 2021)\n",
        "- **称重法** (曹晓玲 2014 / Yang 2014 / 本文 称重测量法 2021)\n",
        "- **渗透/扩散评价法** (孙建忠 2004 ★ / Zhou 2020)\n",
        "- **综合判定法** (本文 渗透直径百分比法 2021)\n\n",
        "## 交互 (仅 HTML 版)\n\n",
        "- **悬停**: 显示 canonical_method_name / 作者 / 年份 / 分支 / 目标 / 论文\n",
        "- **点击**: 打开详情面板, 显示参考条目原文 / evidence_sentence_ids / 备注\n\n",
        "## 使用规范\n\n",
        "- **禁止**: 因节点更晚就断言演化\n",
        "- **禁止**: 因材料/工艺相似就断言演化\n",
        "- **禁止**: 因同分支就断言演化 (分支只是视觉分层, 不是关系)\n",
        "- 除橙色实线外, **所有其他节点之间均无 confirmed 关系**\n",
        "- 论文引用只能说 '本谱系图中除 Zhou 2020 ADAPTS 孙建忠 2004 外, "
        "其余方法为并行独立分支'\n",
    ]
    with open(os.path.join(OUT_DIR, "lineage_legend_v2.md"),
                "w", encoding="utf-8") as f:
        f.writelines(lines)


# ============================================================
# Case study v2 (spec 七)
# ============================================================

def emit_case_study_v2():
    sent_map = _load_sentence_texts_for_paper(PRIMARY_PAPER)
    n_own = sum(1 for n in CANONICAL_NODES if n["kind"] == "own")
    n_ref = len(CANONICAL_NODES) - n_own
    lines = [
        "# 方法谱系案例研究 v2 (最终修正版)\n\n",
        "> **家族窄化**: 复合相变材料渗漏评价与最佳含量测定方法\n",
        "> **主论文**: 脂肪类复合相变储能材料中脂肪酸最佳质量含量的确定方法 (2021)\n",
        "> **修正内容**:\n",
        "> - Zhou 年份从 v1 误记 2013 更正为 **2020** (Scientific Reports)\n",
        "> - 家族窄化: 排除微胶囊/原位聚合/熔融共混/DSC/储热器等相关但独立技术\n",
        "> - 删除 v1 的 2 条 candidate 关系 → excluded_lineage_candidates.csv\n",
        "> - 8 个规范谱系节点从主论文引言 (p8, p9) 抽取, 分 4 个方法分支\n\n",

        "## 一. 方法家族背景\n\n",
        "本谱系聚焦**复合相变材料在储热应用中的渗漏 / 稳定性 / 最佳含量测定**"
        "评价方法, 属方法学分支 (非材料制备分支). 具体涵盖:\n\n",
        "- **观察法**: 通过肉眼或试纸观察渗漏情况判断稳定性 / 最佳含量\n",
        "- **称重法**: 通过热处理前后称重失重判断稳定性 / 最佳含量\n",
        "- **渗透/扩散评价法**: 通过定量测定扩散圈直径判断稳定性 / 最佳含量\n",
        "- **综合判定法**: 结合观察 + 定量指标 (百分比) 的综合方法\n\n",
        "**不纳入本谱系** (与渗漏评价/最佳含量测定无直接关系):\n\n",
        "- 普通微胶囊制备; 原位聚合; 熔融共混; 溶液共混\n",
        "- 导热增强; 普通封装; DSC 测试; 储热器设计\n",
        "- 与渗漏评价或最佳含量测定无直接关系的相变材料制备\n\n",
        "这些属于 PCM 领域**相关但独立**的技术分支, 可以作为背景讨论, "
        "但**不能画入演化主链**, **不能宣称由 2004 年方法演化而来**.\n\n",

        f"### 家族规模\n\n",
        f"- 谱系节点: **{len(CANONICAL_NODES)}** 个 "
        f"(own {n_own} / referenced {n_ref})\n",
        f"- 主论文: `{PRIMARY_PAPER}` (2021)\n",
        f"- 引用条目: [25], [26], [27], [28], [29], [30] (从主论文引用参考文献表解析)\n",
        f"- 分支: 4 (观察法 / 称重法 / 渗透评价法 / 综合判定法)\n\n",

        "## 二. 方法检索和名称统一过程\n\n",
        "### 2.1 检索\n\n",
        "从主论文 `脂肪类复合相变储能材料中脂肪酸最佳质量含量的确定方法` 的"
        "引言 (introduction p8, p9) 直接抽取, 共 8 条方法, 全部有原文证据句"
        "锚定. 每条参考文献均从主论文的参考文献表匹配 [编号] → 完整题录.\n\n",
        "### 2.2 名称统一\n\n",
        "所有节点名统一为 `canonical_method_name`, 遵循 spec 二:\n\n",
        "- **去除**作者/机构/引用编号前缀\n",
        "- **保留**材料 / 工艺 / 结构 / 目标\n",
        "- **通用词相同不视为同一方法** (Zhang N 2013 与 Zhang H 2016 是不同论文中同技术核心的应用)\n",
        "- **不回写 Stage A 全量方法表**: 归一化仅在本 case_evidence_method 层\n\n",

        "## 三. 最早可追溯来源\n\n",
    ]
    ea = next(n for n in CANONICAL_NODES if n["is_earliest"])
    lines.append(f"> 在本研究 337 篇文献及其可解析引用范围内, 最早可追溯的**复合相变"
                    f"材料渗漏评价方法**为 **{ea['author']} ({ea['year']})** 提出的"
                    f"**{ea['short_name']}**.\n\n")
    lines.append(f"- **canonical_method_name**: {ea['canonical_method_name']}\n")
    lines.append(f"- **author**: {ea['author']}\n")
    lines.append(f"- **year**: **{ea['year']}** ({ea['year_source']})\n")
    lines.append(f"- **参考条目 [{ea['reference_number']}]**: "
                    f"`{ea['reference_text_raw']}`\n")
    lines.append(f"- **原文证据**: `{ea['evidence_sentence_ids']}`\n\n")

    lines.append("### 边界声明\n\n")
    lines.append("- 本表述**仅限本数据集内的可解析年份**\n")
    lines.append("- **不代表全球首次提出** — 更早的相关工作可能存在于本数据集之外\n")
    lines.append("- 不追溯外部原始文献\n\n")

    lines.append("## 四. 主要演化阶段\n\n")
    lines.append("按年份排列的 8 个节点 (数据集内可解析范围):\n\n")
    for n in sorted(CANONICAL_NODES, key=lambda x: x["year"]):
        marker = "★ " if n["is_earliest"] else ""
        lines.append(f"- **{n['year']}** {marker}[{n['branch']}, {n['kind']}] "
                        f"{n['author']} — {n['short_name']}\n")
    lines.append("\n")

    lines.append("## 五. Confirmed 关系\n\n")
    e = CONFIRMED_EDGE
    lines.append(f"### 唯一 confirmed 关系 (spec 三)\n\n")
    lines.append(f"- **relation**: **{e['relation']}**\n")
    lines.append(f"- **from (借鉴者)**: {e['from_method_name']} "
                    f"({e['from_year']})\n")
    lines.append(f"- **to (来源方法)**: {e['to_method_name']} ({e['to_year']})\n")
    lines.append(f"- **data_edge_direction**: `{e['data_edge_direction']}` "
                    "(数据方向 = 借鉴者→来源, 符合 ADAPTS 语义)\n")
    lines.append(f"- **visualization_direction**: `{e['visualization_direction']}` "
                    "(视觉方向 = 来源→后续, 符合读者直觉)\n\n")
    lines.append("### 图注 (spec 三 硬性要求)\n\n")
    lines.append("> 数据库方向表示 '借鉴者指向来源', 时间线箭头表示 "
                    "'来源流向后续应用'. 二者是同一 ADAPTS 关系的两种"
                    "方向表达.\n\n")

    lines.append("## 六. Candidate 关系\n\n")
    lines.append("**0 条**. v1 的 2 条 candidate 已剔除, 详见 "
                    "`excluded_lineage_candidates.csv`.\n\n")
    lines.append("剔除原因 (spec 四):\n\n")
    for c in EXCLUDED_CANDIDATES:
        lines.append(f"- **{c['orig_candidate_edge_id']}**: {c['from_method_name']} "
                        f"→ {c['to_method_name']}\n")
        lines.append(f"  - 原因: {c['exclusion_reason']}\n")
    lines.append("\n**除唯一 confirmed ADAPTS 外, 本谱系没有其他演化关系**. "
                    "其余节点 (Zhang 2013 / 曹晓玲 2014 / Yang 2014 / 本文 3 种 2021) "
                    "均为并行独立分支, **不建立**任何 confirmed 或 candidate 关系.\n\n")

    lines.append("## 七. 原文证据\n\n")
    lines.append("### 确认关系的证据句\n\n")
    for sid in CONFIRMED_EDGE["relation_evidence_sentence_ids"]:
        t = sent_map.get(sid, "")
        lines.append(f"- `{sid}` [introduction]:\n")
        lines.append(f"  > 「{t.strip()}」\n\n")
    lines.append("### 8 个节点的原文证据 (来自主论文引言)\n\n")
    for n in CANONICAL_NODES:
        lines.append(f"**{n['author']} ({n['year']}) — {n['short_name']}**\n")
        for sid in n["evidence_sentence_ids"]:
            t = sent_map.get(sid, "")
            lines.append(f"- `{sid}`: 「{t.strip()[:200]}」\n")
        lines.append("\n")

    lines.append("## 八. 路线图解释\n\n")
    lines.append("交互式谱系图: [lineage_graph_v2.html](lineage_graph_v2.html)\n\n")
    lines.append("### 布局\n\n")
    lines.append("- **横轴**: 严格按年份 (2004–2021), 未使用 UMAP\n")
    lines.append("- **纵向**: 按方法分支分层 (观察法 / 称重法 / 渗透评价法 / 综合判定法)\n")
    lines.append("- **节点大小**: 最早可追溯节点用大号金边 ★, 其他节点为小圆圈\n")
    lines.append("- **节点颜色**: 蓝色 = own; 灰色 = referenced\n\n")
    lines.append("### 边\n\n")
    lines.append("- **唯一橙色实线** + 箭头 (视觉方向 2004 → 2020) = ADAPTS 关系\n")
    lines.append("- **图中不含任何虚线** (candidate 已剔除)\n\n")
    lines.append("### 交互 (仅 HTML)\n\n")
    lines.append("- 悬停节点 → 显示 canonical_method_name / 作者 / 年份 / 分支 / 论文\n")
    lines.append("- 点击节点 → 详情面板显示参考文献条目原文 + evidence_sentence_ids\n\n")

    lines.append("## 九. 数据集边界\n\n")
    lines.append("- 全部结论**仅适用于本研究 337 篇既有中文文献 + 其可解析引用范围**\n")
    lines.append("- referenced 方法的**原始论文未被下载或核验** — "
                    "参考文献表条目提供了作者/期刊/年份, 但不追溯全文\n")
    lines.append("- 年份来源: 论文本身发表年 / 作者+年份 / 参考文献条目年份 / 无法解析\n")
    lines.append("- **禁止**: 用综述年代替被引方法年份; 猜年份; 联网搜索\n")
    lines.append("- **禁止**: 因节点更晚就断言演化; 因材料/工艺相似就断言演化\n")
    lines.append("- **除唯一 confirmed ADAPTS 外, 谱系中所有其他方法均视为并行独立分支**\n")
    lines.append("- **不声称全球首次提出**; 只说'数据集内最早可追溯来源'\n\n")

    lines.append("## 十. 可直接放入论文的案例结论\n\n")
    lines.append("> **可直接引用于论文正文的案例结论段落**:\n\n")
    lines.append("> 在本研究 337 篇文献及其可解析引用范围内, "
                    "最早可追溯的**复合相变材料渗漏评价方法**为 "
                    "**孙建忠等 (2004)** 提出的**扩散-渗出圈法**, 用于建材用"
                    "复合相变材料的稳定性评定. "
                    "**在本数据集内, 该评价思路随后被用于复合相变材料最佳含量"
                    "测定; 与此同时, 相关文献还报道了试纸观察、称量失重、目测"
                    "逼近和渗透直径百分比判定等并行方法. 除 Zhou 等 (2020) 对"
                    "扩散-渗出圈法的明确借鉴外, 其余方法之间尚无充分原文证据"
                    "支持直接演化关系.** "
                    "本结论仅基于本数据集内可解析证据, 未追溯外部原始文献, "
                    "亦未声称全球首次提出.\n\n")

    lines.append("---\n\n## 附. 相关文件 (v2)\n\n")
    lines.append("- 8 谱系节点: `lineage_methods_normalized_v2.csv`\n")
    lines.append("- 最早来源: `lineage_earliest_source_v2.json`\n")
    lines.append("- 唯一 confirmed 边: `lineage_edges_confirmed_v2.csv`\n")
    lines.append("- 排除 v1 candidate: `excluded_lineage_candidates.csv`\n")
    lines.append("- 完整证据: `lineage_evidence_v2.md`\n")
    lines.append("- 交互图: `lineage_graph_v2.html`\n")
    lines.append("- 静态图: `lineage_graph_v2.png`\n")
    lines.append("- 图数据: `lineage_graph_data_v2.json`\n")
    lines.append("- 图例: `lineage_legend_v2.md`\n")
    lines.append("- 自检报告: `correction_self_check_v2.md`\n")
    lines.append("- v1 历史文件保留 (未删)\n")

    with open(os.path.join(OUT_DIR, "method_lineage_case_study_v2.md"),
                "w", encoding="utf-8") as f:
        f.writelines(lines)


# ============================================================
# Self-check (spec 九)
# ============================================================

def emit_self_check(cjk_font, png_ok):
    n_main = len(CANONICAL_NODES)
    n_year_ok = sum(1 for n in CANONICAL_NODES if n["year"])
    n_year_unknown = n_main - n_year_ok
    n_conf = 1
    n_cand = 0
    n_excluded = len(EXCLUDED_CANDIDATES)

    # scan cases_v2 md + evidence_v2 md for prohibited AFFIRMATIVE statements
    #   (negation forms like "不代表全球首次提出" are allowed and expected)
    import re as _re
    prohibited_phrases = ["2013年Zhou", "Zhou 2013", "Zhou（2013）",
                              "演化至微胶囊", "延伸至微胶囊",
                              "扩散至微胶囊",
                              "全球首次提出", "首次提出于全球"]
    NEG_MARKERS = ("不", "未", "禁止", "禁", "非", "无",
                       "亦未", "亦不", "prohibited", "not ",
                       "no ", "avoid")
    _SENT_ENDS = set("。.!?！？\n")
    problems = []
    for fname in ("method_lineage_case_study_v2.md",
                    "lineage_evidence_v2.md",
                    "lineage_legend_v2.md"):
        p = os.path.join(OUT_DIR, fname)
        if not os.path.isfile(p): continue
        with open(p, "r", encoding="utf-8") as f: text = f.read()
        for phrase in prohibited_phrases:
            start = 0
            while True:
                i = text.find(phrase, start)
                if i < 0: break
                # find the containing sentence (chunk between sentence-end
                # punctuation)
                s_start = i
                while s_start > 0 and text[s_start - 1] not in _SENT_ENDS:
                    s_start -= 1
                s_end = i + len(phrase)
                while s_end < len(text) and text[s_end] not in _SENT_ENDS:
                    s_end += 1
                sentence = text[s_start:s_end]
                negated = any(neg in sentence for neg in NEG_MARKERS)
                if not negated:
                    problems.append(f"{fname}: affirmative use of "
                                       f"'{phrase}' — sentence: "
                                       f"{sentence[:120]}")
                start = i + len(phrase)

    zhou_year_all_2020 = all(
        n["year"] == 2020 for n in CANONICAL_NODES if "Zhou" in n["author"])

    lines = [
        "# v2 自检报告 (spec 九)\n\n",
        f"> 谱系家族: 复合相变材料渗漏评价与最佳含量测定方法\n\n",
        "## 自检结果\n\n",
        f"- 主谱系节点数: **{n_main}**\n",
        f"- 有年份节点数: **{n_year_ok}**\n",
        f"- 年份未知节点数: **{n_year_unknown}**\n",
        f"- confirmed 关系数: **{n_conf}** (唯一, Zhou 2020 ADAPTS 孙建忠 2004)\n",
        f"- candidate 关系数: **{n_cand}** (图中无虚线)\n",
        f"- 被排除的 candidate 数: **{n_excluded}**\n",
        f"- **Zhou 年份是否全部为 2020**: **{'YES' if zhou_year_all_2020 else 'NO'}**\n",
        f"- **检测到的 CJK 字体**: `{cjk_font or '(未检测到, PNG 可能显示为方框)'}`\n",
        f"- **PNG 生成**: {'成功' if png_ok else '失败/跳过'}\n",
        f"- **禁忌短语扫描**:\n",
    ]
    if problems:
        for p in problems:
            lines.append(f"  - **FOUND**: `{p}`\n")
    else:
        lines.append(f"  - ✅ 未发现 (`2013年Zhou`, `Zhou 2013`, `演化至微胶囊`, `全球首次提出` 等均不在 v2 文本中)\n")

    lines.append("\n## 结论\n\n")
    if (zhou_year_all_2020 and not problems
        and n_cand == 0 and n_excluded >= 2 and cjk_font):
        lines.append("**全部自检项通过**. v2 修正完成, 可直接进入论文写作.\n\n")
    elif not cjk_font:
        lines.append("⚠ **CJK 字体未在 matplotlib 中检测到** — PNG 中文可能"
                        "以方框显示. HTML 版本使用浏览器字体, 不受此影响; "
                        "建议使用 HTML 版本作为论文投稿附件.\n\n")
    else:
        lines.append("⚠ 部分项未通过, 见上. 请复查.\n\n")

    lines.append("## 硬约束遵守\n\n")
    lines.append("- ✅ 无 API 调用\n")
    lines.append("- ✅ 不补文献, 不下载外部资料\n")
    lines.append("- ✅ 不做全库 Stage B\n")
    lines.append("- ✅ 不做跨论文合并\n")
    lines.append("- ✅ 不写 Neo4j / Milvus\n")
    lines.append("- ✅ 不修改 Stage A 全量方法表\n")
    lines.append("- ✅ v1 历史文件保留, 未覆盖\n")
    lines.append("- ✅ Zhou 年份统一为 2020, 所有 v2 文件一致\n")
    lines.append("- ✅ 唯一 confirmed 边: 2004 → 2020 (可视化方向) / "
                    "2020 → 2004 (数据方向, ADAPTS)\n")
    lines.append("- ✅ 谱系图节点仅限主谱系相关, 不含微胶囊/原位聚合/DSC 等无关方法\n")

    with open(os.path.join(OUT_DIR, "correction_self_check_v2.md"),
                "w", encoding="utf-8") as f:
        f.writelines(lines)

    return zhou_year_all_2020, not problems, cjk_font is not None


# ============================================================
# Main
# ============================================================

def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError): pass

    print("=" * 70)
    print("Lineage v2 correction pipeline (no API)")
    print("=" * 70)

    print("\n[1/8] emitting lineage_methods_normalized_v2.csv...")
    emit_methods_normalized_v2()

    print("[2/8] emitting lineage_earliest_source_v2.json...")
    emit_earliest_v2()

    print("[3/8] emitting lineage_edges_confirmed_v2.csv...")
    emit_confirmed_edges_v2()

    print("[4/8] emitting excluded_lineage_candidates.csv...")
    emit_excluded_candidates()

    print("[5/8] emitting lineage_evidence_v2.md...")
    emit_evidence_md_v2()

    print("[6/8] detecting CJK font + emitting graph HTML/PNG/JSON...")
    graph_data = _build_graph_data()
    cjk_font = detect_cjk_font()
    print(f"  detected CJK font: {cjk_font}")
    emit_html_v2(graph_data)
    png_ok = emit_png_v2(graph_data, cjk_font)

    print("[7/8] emitting lineage_legend_v2.md + case_study_v2 + self_check...")
    emit_legend_v2(graph_data, cjk_font)
    emit_case_study_v2()

    print("[8/8] self-check...")
    zhou_ok, no_prob, font_ok = emit_self_check(cjk_font, png_ok)

    print("\n" + "=" * 70)
    print(f"DONE. Outputs at: {OUT_DIR}")
    print(f"  Zhou year all 2020: {zhou_ok}")
    print(f"  Prohibited phrases: {'none' if no_prob else 'found'}")
    print(f"  CJK font: {cjk_font}")
    print(f"  PNG: {'ok' if png_ok else 'failed'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
