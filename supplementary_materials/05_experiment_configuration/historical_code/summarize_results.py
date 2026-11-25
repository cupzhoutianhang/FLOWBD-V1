# -*- coding: utf-8 -*-
"""
summarize_results.py — 读取【已完成的人工/辅助评分】后输出两组对比表。
本脚本**不制造任何评分**: 若评分列为空, 只报告"评分未完成", 输出空对比表骨架。

输入:
  - review_scored.csv : 在 review_blinded.csv 基础上填入评分后另存 (见下方列约定)。
                        未提供时, 回退读取 review_blinded.csv 并报告未评分。
  - group_mapping.json: 盲审行 -> (题号, 组别) 映射。
评分列 (每维 0-5): 正确性 完整性 引用支撑 对象与条件匹配
输出:
  - comparison_table.csv : 逐题配对差值 + 两组各维均值/标准差 (仅在有评分时)。
  - comparison_summary.md : 文字小结 (五分制"提高/降低多少分", 不称准确率/百分点)。
用法:
  python outputs/governance_comparison_20261106/summarize_results.py
"""
import os, csv, json, statistics, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
DIMS = ["正确性", "完整性", "引用支撑", "对象与条件匹配"]


def load_scores():
    scored = os.path.join(OUT_DIR, "review_scored.csv")
    path = scored if os.path.isfile(scored) else os.path.join(OUT_DIR, "review_blinded.csv")
    if not os.path.isfile(path):
        return None, None, "缺少 review_blinded.csv / review_scored.csv"
    rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
    return rows, os.path.basename(path), None


def main():
    rows, src, err = load_scores()
    if err:
        print("[阻点]", err); return 1
    mapping_path = os.path.join(OUT_DIR, "group_mapping.json")
    if not os.path.isfile(mapping_path):
        print("[阻点] 缺少 group_mapping.json"); return 1
    mapping = json.load(open(mapping_path, encoding="utf-8"))
    # 判断是否已评分
    def scored_val(r, d):
        v = (r.get(d) or "").strip()
        try:
            return float(v)
        except ValueError:
            return None
    any_scored = any(scored_val(r, d) is not None for r in rows for d in DIMS)
    print(f"评分来源: {src} | 盲审行数: {len(rows)} | 是否已评分: {any_scored}")
    if not any_scored:
        print("[状态] 评分未完成 —— 交付空对比表骨架与可运行统计脚本; 评分完成后重跑本脚本即出对比。")
        with open(os.path.join(OUT_DIR, "comparison_table.csv"), "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["题号"] + [f"baseline_{d}" for d in DIMS] + [f"governed_{d}" for d in DIMS]
                       + [f"diff_{d}(governed-baseline)" for d in DIMS])
        with open(os.path.join(OUT_DIR, "comparison_summary.md"), "w", encoding="utf-8") as f:
            f.write("# 治理前后对比小结\n\n**评分未完成**，无法计算对比。请完成 review_scored.csv 的四维评分(每维0-5)后重跑 summarize_results.py。\n")
        return 0

    # 有评分: 用 group_mapping 还原组别, 按题号配对
    # review 行以 blind_id 标识; mapping: blind_id -> {no, group}
    by_key = {}  # (no, group) -> {dim: score}
    for r in rows:
        bid = (r.get("blind_id") or "").strip()
        m = mapping.get(bid)
        if not m:
            continue
        key = (m["no"], m["group"])
        by_key[key] = {d: scored_val(r, d) for d in DIMS}

    nos = sorted({k[0] for k in by_key}, key=lambda x: int(x) if str(x).isdigit() else x)
    table_rows = []
    group_dim_scores = {"baseline": {d: [] for d in DIMS}, "governed": {d: [] for d in DIMS}}
    for no in nos:
        b = by_key.get((no, "baseline"), {})
        g = by_key.get((no, "governed"), {})
        row = [no]
        for d in DIMS:
            row.append(b.get(d))
        for d in DIMS:
            row.append(g.get(d))
        for d in DIMS:
            bv, gv = b.get(d), g.get(d)
            row.append(round(gv - bv, 2) if (bv is not None and gv is not None) else "")
            if bv is not None:
                group_dim_scores["baseline"][d].append(bv)
            if gv is not None:
                group_dim_scores["governed"][d].append(gv)
        table_rows.append(row)

    with open(os.path.join(OUT_DIR, "comparison_table.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["题号"] + [f"baseline_{d}" for d in DIMS] + [f"governed_{d}" for d in DIMS]
                   + [f"diff_{d}(governed-baseline)" for d in DIMS])
        w.writerows(table_rows)

    lines = ["# 治理前后对比小结\n", f"题目数(双组均有评分): {len(nos)}\n", "## 各维均值/标准差 (0-5 分)\n",
             "| 维度 | baseline 均值 | baseline 标准差 | governed 均值 | governed 标准差 | 配对均值差(governed-baseline) |",
             "|---|---|---|---|---|---|"]
    for d in DIMS:
        bs = group_dim_scores["baseline"][d]
        gs = group_dim_scores["governed"][d]
        bm = statistics.mean(bs) if bs else None
        gm = statistics.mean(gs) if gs else None
        bsd = statistics.pstdev(bs) if len(bs) > 1 else 0.0
        gsd = statistics.pstdev(gs) if len(gs) > 1 else 0.0
        # 逐题配对差均值
        pdiffs = [by_key[(no, "governed")][d] - by_key[(no, "baseline")][d]
                  for no in nos
                  if by_key.get((no, "governed"), {}).get(d) is not None
                  and by_key.get((no, "baseline"), {}).get(d) is not None]
        pm = statistics.mean(pdiffs) if pdiffs else None
        def fmt(x): return f"{x:+.2f}" if isinstance(x, float) else "—"
        bmf = f"{bm:.2f}" if bm is not None else "—"
        gmf = f"{gm:.2f}" if gm is not None else "—"
        lines.append(f"| {d} | {bmf} | {bsd:.2f} | {gmf} | {gsd:.2f} | {fmt(pm)} 分 |")
    lines.append("\n注: 差值为五分制下的分数变化(提高/降低多少分), 不是准确率或百分点。AI 评分仅辅助初评, 最终以人评分为准。")
    with open(os.path.join(OUT_DIR, "comparison_summary.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("已输出 comparison_table.csv 与 comparison_summary.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
