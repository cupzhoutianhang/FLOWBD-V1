"""
check_quality.py — 抽取质量体检

扫描 method_outputs/*.json 找可疑/可能错的数据, 给你看:
  1. 命名问题: 方法名含 "本方法" / 过短 / 过长 / 重复
  2. 内容问题: own_method 缺 innovation/problem_solved
  3. 关系问题: confidence=low / evidence 过短 / from==to
  4. 抽取失败: paper 既无 own 也无 ref (LLM 输出全空)
  5. 抽样检查: 随机挑 10 条边给你看 evidence 是否支持 relation

用法:
  python check_quality.py                # 全部扫描
  python check_quality.py --sample 20    # 随机抽 20 条边校对
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
from collections import Counter, defaultdict
from typing import Any

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(THIS_DIR, "method_outputs")

# ---------- 启发式阈值 ----------
NAME_TOO_SHORT = 4   # 方法名 < 4 字符 = 可疑
NAME_TOO_LONG = 60   # 方法名 > 60 字符 = 可能 LLM 把整段塞进去了
BAD_NAMES = {"本方法", "本研究方法", "该方法", "本文方法", "新方法", "方法",
             "提出方法", "改进方法", "新型方法"}
EVIDENCE_TOO_SHORT = 15


def load_all() -> list[dict]:
    out = []
    if not os.path.isdir(OUTPUT_DIR):
        return out
    for fn in sorted(os.listdir(OUTPUT_DIR)):
        if not fn.endswith(".json"):
            continue
        try:
            with open(os.path.join(OUTPUT_DIR, fn), "r", encoding="utf-8") as f:
                out.append(json.load(f))
        except (json.JSONDecodeError, OSError):
            pass
    return out


def section(title: str) -> None:
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def check_naming(records: list[dict]) -> None:
    section("1. 命名质量")
    issues = []
    name_count: Counter[str] = Counter()
    for d in records:
        pid = d.get("paper_id", "")
        for kind, ms in (("own", d.get("own_methods") or []),
                         ("ref", d.get("referenced_methods") or [])):
            for m in ms:
                name = (m.get("name") or "").strip()
                if not name:
                    issues.append(("无名", pid, kind, "(empty)"))
                    continue
                name_count[name] += 1
                if name in BAD_NAMES:
                    issues.append(("无信息名", pid, kind, name))
                elif len(name) < NAME_TOO_SHORT:
                    issues.append(("过短", pid, kind, name))
                elif len(name) > NAME_TOO_LONG:
                    issues.append(("过长", pid, kind, name[:80] + "..."))

    if not issues:
        print("  无可疑命名 ✓")
    else:
        print(f"  发现 {len(issues)} 处可疑命名:")
        for typ, pid, kind, name in issues[:20]:
            print(f"    [{typ:<8}] {kind} | {pid[:30]:<30} | {name}")
        if len(issues) > 20:
            print(f"    ... 还有 {len(issues) - 20} 处")

    # 跨篇高频同名 = 后续 embedding 去重时该合并的, 现在先看一下
    print()
    cross_paper_dups = [(n, c) for n, c in name_count.items() if c >= 3]
    if cross_paper_dups:
        cross_paper_dups.sort(key=lambda x: -x[1])
        print(f"  跨篇出现 >=3 次的方法名 ({len(cross_paper_dups)} 个, 后续会自动去重合并):")
        for n, c in cross_paper_dups[:10]:
            print(f"    {c}x  {n[:60]}")


def check_content(records: list[dict]) -> None:
    section("2. own_methods 内容完整性")
    miss_inno = 0
    miss_prob = 0
    no_components = 0
    for d in records:
        for m in d.get("own_methods") or []:
            if not (m.get("innovation") or "").strip():
                miss_inno += 1
            if not (m.get("problem_solved") or "").strip():
                miss_prob += 1
            if not (m.get("key_components") or []):
                no_components += 1
    print(f"  缺 innovation     : {miss_inno}")
    print(f"  缺 problem_solved : {miss_prob}")
    print(f"  缺 key_components : {no_components}")


def check_edges(records: list[dict]) -> None:
    section("3. 演化边质量")
    confs = Counter()
    rels = Counter()
    self_loops = 0
    short_evidence = 0
    no_evidence = 0
    for d in records:
        for e in d.get("evolution_edges") or []:
            confs[e.get("confidence", "")] += 1
            rels[e.get("relation", "")] += 1
            fm = (e.get("from_method") or "").strip()
            tm = (e.get("to_method") or "").strip()
            if fm and fm == tm:
                self_loops += 1
            ev = (e.get("evidence") or "").strip()
            if not ev:
                no_evidence += 1
            elif len(ev) < EVIDENCE_TOO_SHORT:
                short_evidence += 1

    print(f"  关系类型分布 : {dict(rels)}")
    print(f"  置信度分布   : {dict(confs)}")
    print(f"  self-loop (from==to)    : {self_loops} {'(异常!)' if self_loops else ''}")
    print(f"  evidence 缺失           : {no_evidence}")
    print(f"  evidence 过短 (<{EVIDENCE_TOO_SHORT}字) : {short_evidence}")
    print(f"  low confidence 总数     : {confs.get('low', 0)}  (这些建议人工核)")


def check_silent_failures(records: list[dict]) -> None:
    section("4. 静默失败 (LLM 输出全空)")
    silent = []
    for d in records:
        own_n = len(d.get("own_methods") or [])
        ref_n = len(d.get("referenced_methods") or [])
        edge_n = len(d.get("evolution_edges") or [])
        if own_n == 0 and ref_n == 0 and edge_n == 0:
            silent.append(d.get("paper_id", ""))
    if not silent:
        print(f"  无静默失败 ✓ ({len(records)} 篇全部有产出)")
    else:
        print(f"  ⚠️  {len(silent)} 篇 LLM 输出全空, 需重抽:")
        for pid in silent:
            print(f"    - {pid}")


def sample_edges(records: list[dict], n: int) -> None:
    section(f"5. 随机抽 {n} 条边人工校对")
    pool = []
    for d in records:
        pid = d.get("paper_id", "")
        for e in d.get("evolution_edges") or []:
            pool.append((pid, e))
    if not pool:
        print("  (无边可抽)")
        return

    n = min(n, len(pool))
    samples = random.sample(pool, n)
    for i, (pid, e) in enumerate(samples, 1):
        rel = e.get("relation", "")
        conf = e.get("confidence", "")
        print(f"\n  [{i}] {pid}")
        print(f"      {e.get('from_method','')[:60]}")
        print(f"      --[{rel:<8} conf={conf}]-->")
        print(f"      {e.get('to_method','')[:60]}")
        print(f"      evidence: {e.get('evidence','')[:200]}")
        print(f"      reason  : {e.get('reason','')[:150]}")
        print(f"      [你判断] 这条边对吗? Y / N / 改成什么关系 ?")


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=10, help="随机抽 N 条边校对")
    ap.add_argument("--seed", type=int, default=42, help="随机种子")
    args = ap.parse_args()
    random.seed(args.seed)

    records = load_all()
    if not records:
        print("[ERR] method_outputs/ 为空", file=sys.stderr)
        return 1

    # 总览
    total_own = sum(len(d.get("own_methods") or []) for d in records)
    total_ref = sum(len(d.get("referenced_methods") or []) for d in records)
    total_edge = sum(len(d.get("evolution_edges") or []) for d in records)
    print(f"总览: {len(records)} 篇  |  {total_own} own_methods  |  "
          f"{total_ref} ref_methods  |  {total_edge} edges")

    check_naming(records)
    check_content(records)
    check_edges(records)
    check_silent_failures(records)
    sample_edges(records, args.sample)
    return 0


if __name__ == "__main__":
    sys.exit(main())
