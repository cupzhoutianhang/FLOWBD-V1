"""
inspect_edges.py — 把抽样的边和原文 markdown 对照, 让人 (或 LLM 助手) 校对

工作流:
1. 分层抽样 N 条边 (每种 relation 各 N/4 条)
2. 对每条边:
   a. 加载源 paper 的 full.md
   b. 尝试在 markdown 里找 evidence 字段
   c. 输出: 边数据 + evidence 是否找到 + 周边上下文
3. 把所有要核的边写入一个文本文件, 方便逐条看

用法:
  python inspect_edges.py --n 20            # 每种关系抽 5 条 = 20 条
  python inspect_edges.py --n 8             # 每种关系抽 2 条 = 8 条
  python inspect_edges.py --confidence low  # 只看 low confidence 边
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
from collections import defaultdict

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(THIS_DIR)))
DOWNLOADED_DIR = os.path.join(
    PROJECT_ROOT, "pdf_to_md", "extraction_results", "downloaded_files"
)
OUTPUT_DIR = os.path.join(THIS_DIR, "method_outputs")
REVIEW_OUTPUT = os.path.join(THIS_DIR, "edges_review.md")


def load_paper_md(paper_id: str) -> str:
    p = os.path.join(DOWNLOADED_DIR, paper_id, "full.md")
    if not os.path.isfile(p):
        return ""
    with open(p, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def find_evidence_in_paper(evidence: str, md: str) -> tuple[bool, str]:
    """在 md 里找 evidence. 返回 (是否找到, 周边上下文 ~400字)."""
    if not evidence or not md:
        return False, ""
    # LLM 经常把开头加 "..." 或省略号, 先去除
    ev = evidence.strip().lstrip(".").lstrip("…").strip()
    # 全文匹配先试
    if ev in md:
        i = md.find(ev)
        start = max(0, i - 100)
        end = min(len(md), i + len(ev) + 100)
        return True, "..." + md[start:end].replace("\n", " ") + "..."
    # 取 evidence 中段 (避开开头省略号导致的不匹配) 30 字滑窗
    for length in (40, 30, 20, 15):
        if len(ev) < length:
            continue
        for i in range(0, len(ev) - length, 5):
            chunk = ev[i:i + length]
            if chunk in md:
                j = md.find(chunk)
                start = max(0, j - 150)
                end = min(len(md), j + length + 150)
                return True, "(片段命中) ..." + md[start:end].replace("\n", " ") + "..."
    return False, ""


def collect_edges_with_paper(records: list[dict]) -> list[dict]:
    """把每条边和它的源 paper_id 关联."""
    out = []
    for d in records:
        pid = d.get("paper_id", "")
        year = d.get("year")
        for e in d.get("evolution_edges") or []:
            out.append(
                {
                    "paper_id": pid,
                    "paper_year": year,
                    **e,
                }
            )
    return out


def sample_stratified(edges: list[dict], n_per_relation: int, seed: int) -> list[dict]:
    """每种 relation 抽 n_per_relation 条 (分层抽样)."""
    rng = random.Random(seed)
    by_rel = defaultdict(list)
    for e in edges:
        by_rel[e.get("relation", "")].append(e)
    out = []
    for rel in ("EXTENDS", "IMPROVES", "ADAPTS", "REPLACES"):
        pool = by_rel.get(rel, [])
        if not pool:
            continue
        k = min(n_per_relation, len(pool))
        out.extend(rng.sample(pool, k))
    return out


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20,
                    help="总抽样数, 平均分到 4 种关系")
    ap.add_argument("--confidence", choices=["high", "medium", "low", "all"], default="all")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    # 加载全部 records
    records = []
    for fn in sorted(os.listdir(OUTPUT_DIR)):
        if not fn.endswith(".json"):
            continue
        with open(os.path.join(OUTPUT_DIR, fn), "r", encoding="utf-8") as f:
            records.append(json.load(f))

    edges = collect_edges_with_paper(records)
    if args.confidence != "all":
        edges = [e for e in edges if (e.get("confidence") or "").lower() == args.confidence]

    n_per = max(1, args.n // 4)
    samples = sample_stratified(edges, n_per, args.seed)

    # 写 review markdown
    lines = []
    lines.append(f"# 边抽样校对 ({len(samples)} 条)\n")
    lines.append(f"配置: n={args.n}, confidence={args.confidence}, seed={args.seed}\n")
    lines.append("---\n")

    found_n = 0
    for i, e in enumerate(samples, 1):
        md = load_paper_md(e["paper_id"])
        found, ctx = find_evidence_in_paper(e.get("evidence", ""), md)
        if found:
            found_n += 1

        lines.append(f"\n## 边 #{i}\n")
        lines.append(f"- **paper**: {e['paper_id']}  ({e.get('paper_year', '?')})\n")
        lines.append(f"- **from**: {e.get('from_method', '')}\n")
        lines.append(f"- **to**:   {e.get('to_method', '')}\n")
        lines.append(f"- **relation**: `{e.get('relation', '')}`  | confidence: `{e.get('confidence', '')}`\n")
        lines.append(f"- **evidence (LLM 抽的)**:\n")
        lines.append(f"  > {e.get('evidence', '')}\n")
        lines.append(f"- **reason (LLM 解释)**: {e.get('reason', '')}\n")
        lines.append(f"- **原文中找到 evidence?** {'✅ 是' if found else '❌ 否 (可能 LLM 改写过)'}\n")
        if ctx:
            lines.append(f"- **原文周边**:\n")
            lines.append(f"  > {ctx}\n")

    lines.append(f"\n---\n## 汇总\n")
    lines.append(f"- 抽样: {len(samples)} 条\n")
    lines.append(f"- evidence 在原文中找到: {found_n}/{len(samples)} = {found_n/max(1,len(samples))*100:.0f}%\n")
    lines.append(f"- 未找到的可能原因: LLM 把原文片段改写/截断/合并\n")

    with open(REVIEW_OUTPUT, "w", encoding="utf-8") as f:
        f.writelines(lines)

    print(f"抽样 {len(samples)} 条边")
    print(f"evidence 命中原文: {found_n}/{len(samples)}")
    print(f"评审文件写入: {REVIEW_OUTPUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
