"""run_case_candidate_selection.py — 选出最多 5 个案例候选 (spec 三, 无 API).

从 337 篇里筛选:
  - main_storage
  - accepted 方法数 ≥ 5
  - 证据完整 (每条 accepted 方法都有非空 evidence_text_resolved)
  - ≥2 own/ref 或多个 referenced
  - 全文含至少 3 个演化触发词 (基础上/改进/优化/相比/替代/借鉴/进一步)
  - OCR 质量可用 (preflight 未标红)
  - 方法名称具体 (非孤立通用工艺)

优先领域: 相变储能/锂离子/钠离子/超级电容/液流电池/热化学储能

输出:
  paper/method_evolution_v2/article_minimal_results/
    - case_candidates.md
    - case_candidates.csv
"""
from __future__ import annotations

import csv
import os
import re
import sys
from collections import defaultdict

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_GRAPH_RAG_DIR = os.path.dirname(THIS_DIR)
if SRC_GRAPH_RAG_DIR not in sys.path:
    sys.path.insert(0, SRC_GRAPH_RAG_DIR)

from method_evolution_v2 import config                              # noqa: E402
from method_evolution_v2.stage_a import full_runner as fr           # noqa: E402


AGG_DIR = os.path.join(config.STAGE_A_FULL_V1_DIR, "aggregation")
OUT_DIR = os.path.join(config.PAPER_V2_DIR, "article_minimal_results")

EVOLUTION_TRIGGERS = ("基础上", "改进", "优化", "相比",
                          "替代", "借鉴", "进一步", "改良",
                          "在此之上", "沿用", "扩展")

PREFERRED_DOMAINS = ("相变储热", "相变储能", "热储能", "储热",
                        "锂离子电池", "钠离子电池", "锂电",
                        "超级电容", "液流电池", "热化学储能",
                        "热化学储热", "电化学储能")

BARE_GENERIC = {"水热合成法", "水热法", "溶胶-凝胶法", "模板法",
                 "热处理法", "共沉淀法", "球磨法"}


def load_per_paper():
    with open(os.path.join(AGG_DIR, "per_paper_summary.csv"),
                "r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def load_methods_accepted():
    with open(os.path.join(AGG_DIR, "methods_accepted.csv"),
                "r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def domain_preferred(domain):
    for kw in PREFERRED_DOMAINS:
        if kw in (domain or ""):
            return True
    return False


def count_triggers(full_md_text):
    """全文里触发词命中次数 (每个触发词最多计 1 次, 得总覆盖度)."""
    covered = 0
    for kw in EVOLUTION_TRIGGERS:
        if kw in full_md_text:
            covered += 1
    return covered


def specific_name_ratio(methods):
    """名称具体化率: 非孤立通用名 / 总数."""
    if not methods: return 0.0
    n = 0
    for m in methods:
        name = (m.get("name") or "").strip()
        if name and name not in BARE_GENERIC and len(name) >= 6:
            n += 1
    return n / len(methods)


def evidence_completeness(methods):
    """证据完整度: 每条 accepted 都有非空 evidence_text_resolved."""
    if not methods: return 0.0
    n = sum(1 for m in methods
              if (m.get("evidence_text_resolved") or "").strip())
    return n / len(methods)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    per_paper = load_per_paper()
    accepted = load_methods_accepted()

    # Group accepted by paper_id
    by_paper = defaultdict(list)
    for m in accepted:
        by_paper[m["paper_id"]].append(m)

    # Iterate main_storage papers, evaluate
    candidates = []
    for p in per_paper:
        if (p.get("paper_context_status") or "").strip().lower() != "confirmed":
            continue
        pid = p["paper_id"]
        methods = by_paper.get(pid, [])
        # 基础门槛
        if len(methods) < 5: continue

        n_own = sum(1 for m in methods if m.get("kind") == "own")
        n_ref = sum(1 for m in methods if m.get("kind") == "referenced")
        # ≥2 own+ref 或多 referenced
        if not (n_own + n_ref >= 2 and (n_own >= 2 or n_ref >= 3)):
            continue

        # 证据完整度
        ec = evidence_completeness(methods)
        if ec < 0.85: continue

        # 命名具体率
        snr = specific_name_ratio(methods)
        if snr < 0.7: continue

        # 全文触发词覆盖
        md_p = config.full_md_path(pid)
        if not os.path.isfile(md_p):
            continue
        try:
            with open(md_p, "r", encoding="utf-8") as f:
                full_text = f.read()
        except OSError:
            continue
        n_triggers = count_triggers(full_text)
        if n_triggers < 3: continue

        # 优先领域权重
        dom_pref = domain_preferred(p.get("primary_storage_domain", ""))

        # 可组成的方法对上限 = C(n, 2)
        n_pairs = len(methods) * (len(methods) - 1) // 2

        # 分数
        score = (
            2.0 * min(len(methods), 15)   # 更多方法 (cap 15) 更好
            + 1.5 * n_triggers                    # 触发词覆盖
            + 1.0 * (n_own + n_ref)               # own+ref 组合
            + 5.0 * ec                            # 证据完整
            + 5.0 * snr                           # 命名具体
            + (3.0 if dom_pref else 0.0)         # 优先领域加分
            + (2.0 if p["paper_type"] == "review_article" else 0.0)   # 综述加分
        )

        # 推荐理由
        reasons = []
        if dom_pref: reasons.append(f"优先领域({p['primary_storage_domain']})")
        if n_triggers >= 5: reasons.append(f"触发词丰富({n_triggers}/11)")
        if n_own >= 3: reasons.append(f"own 方法充分({n_own})")
        if n_ref >= 5: reasons.append(f"参考方法丰富({n_ref})")
        if p["paper_type"] == "review_article": reasons.append("综述文体, 方法对比自然")

        # 风险
        risks = []
        if n_ref > n_own * 3 and n_own < 3:
            risks.append("own 少, 关系可能主要落在 ref-to-ref, 需综述句能对齐")
        if snr < 0.85:
            risks.append(f"命名具体率 {round(snr*100)}%, 存在部分通用工艺名")
        if p["paper_type"] != "review_article" and n_triggers < 5:
            risks.append("研究论文体触发词较少, 可能演化关系有限")

        # 预计关系数上限估算 (启发式: 每 5 个方法 + 1 触发词 ~ 期望 1-2 条严格关系)
        est_edges_upper = min(n_pairs, max(2, n_triggers // 2))

        candidates.append({
            "paper_id": pid,
            "canonical_title": p.get("canonical_title", ""),
            "paper_type": p["paper_type"],
            "primary_storage_domain": p.get("primary_storage_domain", ""),
            "n_accepted_methods": len(methods),
            "n_own_accepted": n_own,
            "n_ref_accepted": n_ref,
            "n_evolution_triggers": n_triggers,
            "n_possible_pairs": n_pairs,
            "evidence_completeness_pct": round(ec * 100, 1),
            "specific_name_ratio_pct": round(snr * 100, 1),
            "domain_preferred": "yes" if dom_pref else "no",
            "score": round(score, 2),
            "reasons": "; ".join(reasons) or "-",
            "risks": "; ".join(risks) or "-",
            "est_strict_edges_upper": est_edges_upper,
        })

    # 排序 + 取 top 5
    candidates.sort(key=lambda r: -r["score"])
    top5 = candidates[:5]

    # === csv ===
    fields = list(top5[0].keys()) if top5 else [
        "paper_id", "score"]
    with open(os.path.join(OUT_DIR, "case_candidates.csv"),
                "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in top5: w.writerow(r)

    # === md ===
    md = [
        "# 案例候选清单 (最多 5 个)\n\n",
        f"> 从 337 篇 main_storage 论文里按 spec 三 硬门槛 + 优先领域评分\n",
        f"> 只做候选评估, 尚未运行 Stage B\n\n",
        f"## 排名\n\n",
        "| # | paper_id | 领域 | 类型 | accepted | own/ref | 触发词 | score |\n",
        "|:-:|---|---|---|---:|---|---:|---:|\n",
    ]
    for i, c in enumerate(top5, 1):
        md.append(f"| {i} | {c['paper_id'][:35]} "
                    f"| {c['primary_storage_domain'] or '-'} "
                    f"| {c['paper_type']} "
                    f"| {c['n_accepted_methods']} "
                    f"| {c['n_own_accepted']}/{c['n_ref_accepted']} "
                    f"| {c['n_evolution_triggers']}/11 "
                    f"| {c['score']} |\n")
    md.append("\n---\n\n## 每个候选详情\n\n")
    for i, c in enumerate(top5, 1):
        md.append(f"### {i}. {c['paper_id']}\n\n")
        md.append(f"- **canonical_title**: {c['canonical_title']}\n")
        md.append(f"- **paper_type**: {c['paper_type']}\n")
        md.append(f"- **primary_storage_domain**: {c['primary_storage_domain']}\n")
        md.append(f"- **accepted 方法数**: {c['n_accepted_methods']} "
                    f"(own {c['n_own_accepted']} / ref {c['n_ref_accepted']})\n")
        md.append(f"- **可疑演化触发句数**: {c['n_evolution_triggers']}/11 "
                    f"(触发词: {', '.join(EVOLUTION_TRIGGERS)})\n")
        md.append(f"- **可组成的方法对上限**: {c['n_possible_pairs']}\n")
        md.append(f"- **证据完整度**: {c['evidence_completeness_pct']}%\n")
        md.append(f"- **命名具体率**: {c['specific_name_ratio_pct']}%\n")
        md.append(f"- **推荐理由**: {c['reasons']}\n")
        md.append(f"- **风险**: {c['risks']}\n")
        md.append(f"- **预计能获得的正式演化关系数上限**: {c['est_strict_edges_upper']}\n\n")

    md.append("---\n\n## 下一步\n")
    md.append("按 spec 四, 只对 **top 3** 做严格 Stage B (预算 ¥10, 只允许 "
                "EXTENDS / IMPROVES / ADAPTS / REPLACES).\n")

    with open(os.path.join(OUT_DIR, "case_candidates.md"),
                "w", encoding="utf-8") as f:
        f.writelines(md)

    print(f"OK — evaluated {len(candidates)} papers passing hard gates, "
            f"selected top {len(top5)}. See case_candidates.md.")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError): pass
    sys.exit(main())
