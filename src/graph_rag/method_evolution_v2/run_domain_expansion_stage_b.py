"""run_domain_expansion_stage_b.py — 严格 Stage B 第二轮: 域扩展 (B 阶段).

与 run_positive_case_stage_b.py 的关系:
  - 复用其全部管线函数 (extractor / auditor / 12条硬性验证), 逻辑一字不改
  - 仅改: (1) 目标论文显式指定 (非 top-3)  (2) 输出到独立目录, 不触碰第一轮产物

目标论文 (B1 筛选, 来自 positive_case_candidates.csv 排名 4-10):
  - 钠离子电池沥青基碳负极材料制备技术研究进展   (9 对, electrochemical_storage)
  - 氟化物熔盐的制备及其应用进展               (10 对, domain 空 → 潜在新域)
  - 一维有序聚苯胺纳米阵列在超级电容器中的研究进展 (6 对, electrochemical_storage)
  - 固体氧化物电池空气电极铬中毒机理及抗铬性能研究进展 (3 对, domain 空 → 潜在新域)

Env: MOONSHOT_API_KEY + MOONSHOT_MODEL 必须在 process env, 否则 rc=2.
"""
from __future__ import annotations

import json
import os
import sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_GRAPH_RAG_DIR = os.path.dirname(THIS_DIR)
if SRC_GRAPH_RAG_DIR not in sys.path:
    sys.path.insert(0, SRC_GRAPH_RAG_DIR)

from method_evolution_v2 import config                                       # noqa: E402
from method_evolution_v2.stage_a import llm_client                           # noqa: E402
from method_evolution_v2 import run_positive_case_stage_b as base            # noqa: E402


TARGET_PIDS = [
    "钠离子电池沥青基碳负极材料制备技术研究进展",
    "氟化物熔盐的制备及其应用进展",
    "一维有序聚苯胺纳米阵列在超级电容器中的研究进展",
    "固体氧化物电池空气电极铬中毒机理及抗铬性能研究进展",
]

# 第三轮: thermal 域补充 (B 阶段用户决策, 2026-08-08)
TARGET_PIDS_ROUND3_THERMAL = [
    "制备方法对纳米熔盐储热性能及形成机理的影响",
    "十二水磷酸氢二钠相变储能材料研究进展",
    "低品位能源化学储热材料研究进展",
    "相变储热技术用于被动式建筑节能的研究进展",
    "钙基热化学储能体系装备与系统研究进展",
]

# 第一轮 (run_positive_case_stage_b.py, top-3) — 仅用于 round4 的排除集
TARGET_PIDS_ROUND1 = [
    "低模量、高弹性、高剥离强度丙烯酸酯压敏胶",
    "脂肪类复合相变储能材料中脂肪酸最佳质量含量的确定方法",
    "表面化学反应控制制备多级结构电极材料及性能",
]

TARGET_PIDS_ROUND2 = TARGET_PIDS  # 第二轮集合另存, 供 round4 排除用

ROUND_TARGET_SETS = {
    "": TARGET_PIDS,  # 第二轮 (默认, 域扩展)
    "round3_thermal": TARGET_PIDS_ROUND3_THERMAL,
    "round4_remaining": [],  # 占位; 实际列表在 main 里动态计算 (扫描全集 - 前三轮)
}

# STAGE_B_ROUND 环境变量选择轮次; 非默认轮次输出到独立子目录, 不覆盖前轮 CSV
ROUND = os.environ.get("STAGE_B_ROUND", "")
if ROUND not in ROUND_TARGET_SETS:
    raise SystemExit(f"unknown STAGE_B_ROUND={ROUND!r}, "
                     f"valid: {sorted(ROUND_TARGET_SETS)}")
TARGET_PIDS = ROUND_TARGET_SETS[ROUND]

OUT_DIR = os.path.join(config.PAPER_V2_DIR, "article_minimal_results",
                       "domain_expansion_stage_b")
if ROUND:
    OUT_DIR = os.path.join(OUT_DIR, ROUND)
os.makedirs(OUT_DIR, exist_ok=True)

TOP_N_PAIRS_PER_PAPER = 10
MAX_TOTAL_PAIRS = 80  # round4 剩余全集 58 对


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    try:
        _ = llm_client.get_api_key()
        print("MOONSHOT_API_KEY configured: yes")
    except RuntimeError:
        print("MOONSHOT_API_KEY configured: no")
        return 2

    model = os.environ.get("MOONSHOT_MODEL", llm_client.DEFAULT_MODEL)
    by_paper_all = base.load_all_candidate_pairs()

    target_pids = TARGET_PIDS
    if ROUND == "round4_remaining":
        done = set(TARGET_PIDS_ROUND1) | set(TARGET_PIDS_ROUND2) \
               | set(TARGET_PIDS_ROUND3_THERMAL)
        target_pids = [p for p in by_paper_all if p not in done]
        print(f"round4_remaining: {len(target_pids)} papers "
              f"(scan total {len(by_paper_all)} - done {len(done)})")

    # 校验目标论文在扫描结果里
    missing = [p for p in target_pids if p not in by_paper_all]
    if missing:
        print(f"ERROR: target papers not in relation_sentence_candidates.csv: {missing}")
        return 3

    # 组装每篇的 top-N 局部对 (与第一轮相同逻辑: (a,b) 去重 + 按 score 排序)
    selected_by_paper = {}
    total = 0
    for pid in target_pids:
        raw = by_paper_all.get(pid, [])
        seen = set()
        unique = []
        for r in raw:
            key = tuple(sorted([r["method_a_id"], r["method_b_id"]]))
            if key in seen:
                continue
            seen.add(key)
            unique.append(r)
        remaining = MAX_TOTAL_PAIRS - total
        take = min(TOP_N_PAIRS_PER_PAPER, len(unique), remaining)
        selected_by_paper[pid] = unique[:take]
        total += take
        print(f"  {pid[:30]}: {take} pairs (of {len(unique)} unique)")
    print(f"total pairs to Stage B: {total}")

    cost_state = {"cost": 0.0}
    all_edges = []
    all_stats = []
    for pid in target_pids:
        print(f"\n=== [{pid}] ===")
        try:
            edges, stats, mbid, sidx = base.process_paper(
                pid, selected_by_paper[pid], model, cost_state)
        except RuntimeError as e:
            print(f"  HALT: {e}")
            return 4
        except Exception as e:
            import traceback
            print(f"  ERROR: {type(e).__name__}: {e}")
            print(traceback.format_exc())
            return 5
        all_edges.extend(edges)
        all_stats.append(stats)
        print(f"  → acc={stats['n_accepted']} cand={stats['n_candidate']} "
              f"rej={stats['n_rejected']} cost=¥{cost_state['cost']:.3f}")

    # --- write outputs (独立目录, 文件名带 domain_expansion 前缀) ---
    accepted = [e for e in all_edges if e.get("validation_status") == "accepted"]
    candidate = [e for e in all_edges if e.get("validation_status") == "candidate"]
    rejected = [e for e in all_edges if e.get("validation_status") == "rejected"]

    edge_fields = [
        "paper_id", "pair_id", "relation",
        "from_method_id", "to_method_id",
        "from_method_name", "to_method_name",
        "relation_evidence_sentence_ids", "evidence_missing_ids",
        "evidence_quote", "evidence_section", "evidence_para_id",
        "explicit_trigger_hit", "direction_basis",
        "audit_linkage_type", "audit_endpoint_linkage",
        "audit_support", "audit_direction", "audit_relation_check",
        "audit_suggested_relation", "audit_reason",
        "validation_status", "rejected_reason", "confidence_llm",
    ]
    base._write_csv(os.path.join(OUT_DIR, "domain_expansion_edges_accepted.csv"),
                    edge_fields, accepted)
    base._write_csv(os.path.join(OUT_DIR, "domain_expansion_edges_rejected.csv"),
                    edge_fields, rejected)
    if candidate:
        base._write_csv(os.path.join(OUT_DIR, "domain_expansion_edges_candidate.csv"),
                        edge_fields, candidate)

    print("\n" + "=" * 70)
    print("domain-expansion Stage B done:")
    print(f"  processed: {len(all_stats)} papers, "
          f"total pairs: {sum(s['n_pairs_input'] for s in all_stats)}")
    print(f"  accepted: {len(accepted)}, "
          f"candidate: {len(candidate)}, rejected: {len(rejected)}")
    print(f"  total est cost: ¥{cost_state['cost']:.3f} / ¥{base.BUDGET_HARD_STOP}")
    print(f"  outputs at: {OUT_DIR}")

    with open(os.path.join(OUT_DIR, "run_summary.json"), "w", encoding="utf-8") as f:
        json.dump({
            "round": ROUND or "domain_expansion_r2",
            "target_pids": target_pids,
            "selected_per_paper": {k: len(v) for k, v in selected_by_paper.items()},
            "stats": all_stats,
            "cost": cost_state["cost"],
        }, f, ensure_ascii=False, indent=2)

    return 0


if __name__ == "__main__":
    sys.exit(main())
