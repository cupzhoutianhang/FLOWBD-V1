"""
extract_methods.py — 方法 + 演化关系抽取主脚本 (Kimi K2-0905, 2 路并发)

输入  : pdf_to_md/extraction_results/downloaded_files/<paper>/full.md
        + publish_year_report.csv (附加 year)
输出  : method_outputs/<paper>.json  每篇一个
        extract_failures.json       记录抽取失败的篇
日志  : 控制台逐篇打印 + 末尾汇总

用法:
  python extract_methods.py --limit 5                # 试跑 5 篇 (顺序)
  python extract_methods.py --parallel 2             # 全量 2 路并发
  python extract_methods.py --resume                 # 跳过已有输出的篇
  python extract_methods.py --limit 5 --resume       # 试跑+resume
"""
from __future__ import annotations

import argparse
import csv
import itertools
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Any, Optional

# ---------- 路径 ----------
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(THIS_DIR)))
DOWNLOADED_DIR = os.path.join(
    PROJECT_ROOT, "pdf_to_md", "extraction_results", "downloaded_files"
)
YEAR_REPORT_CSV = os.path.join(THIS_DIR, "publish_year_report.csv")
OUTPUT_DIR = os.path.join(THIS_DIR, "method_outputs")
FAILURES_PATH = os.path.join(THIS_DIR, "extract_failures.json")

# ---------- 模型 + Key ----------
KIMI_MODEL = "kimi-k2-0905-preview"
KIMI_BASE_URL = "https://api.moonshot.cn/v1"
# 两个 Moonshot key, 轮询使用
MOONSHOT_KEYS = [
    __import__("os").environ.get("MOONSHOT_API_KEY", ""),
    __import__("os").environ.get("MOONSHOT_API_KEY", ""),
]

# ---------- 输入策略 ----------
HEAD_CHARS = 8000  # 头 8K: 摘要 + 引言 + 方法学开头
TAIL_CHARS = 4000  # 尾 4K: 结论 + 参考文献
SEPARATOR = "\n\n[...中间正文 (实验数据/图表) 已省略...]\n\n"

# ---------- 调用参数 ----------
LLM_TEMPERATURE = 0.1  # 略带创造性识别同义方法, 但保持判断稳定
LLM_MAX_TOKENS = 4096
LLM_TIMEOUT = 120  # 单次最大 2 分钟


# ---------- 数据结构 ----------
@dataclass
class ExtractionResult:
    paper_id: str
    year: Optional[int]
    status: str  # success / json_fail / api_fail / skip
    elapsed_sec: float = 0.0
    own_methods_n: int = 0
    refs_n: int = 0
    edges_n: int = 0
    error: str = ""


# ---------- 工具 ----------
def read_paper_text(md_path: str) -> str:
    """读论文 markdown 并拼成 头 + 分隔符 + 尾."""
    with open(md_path, "r", encoding="utf-8", errors="ignore") as f:
        txt = f.read()
    if len(txt) <= HEAD_CHARS + TAIL_CHARS:
        return txt
    return txt[:HEAD_CHARS] + SEPARATOR + txt[-TAIL_CHARS:]


def load_year_map() -> dict[str, Optional[int]]:
    """从 backfill 报告读 paper -> year 映射. 失败篇 year=None."""
    out: dict[str, Optional[int]] = {}
    if not os.path.isfile(YEAR_REPORT_CSV):
        return out
    with open(YEAR_REPORT_CSV, "r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            pid = row["paper_id"]
            y = row["year"].strip()
            out[pid] = int(y) if y.isdigit() else None
    return out


def _extract_json_object(text: str) -> Optional[dict]:
    """从 LLM 返回里抠 JSON. 容忍 markdown 围栏 + 前后噪声."""
    if not text:
        return None
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```$", "", t)
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass
    s, e = t.find("{"), t.rfind("}")
    if s == -1 or e <= s:
        return None
    try:
        return json.loads(t[s : e + 1])
    except json.JSONDecodeError:
        return None


# ---------- LLM 客户端 (轻量, 不依赖现有 LLMConfig) ----------
class KimiClient:
    """每个 thread worker 自己持有一个 client + 固定 key. 避免共享 OpenAI session."""

    def __init__(self, api_key: str):
        from openai import OpenAI  # 延迟导入

        self.api_key = api_key
        self.key_tag = api_key[-8:]  # 日志用
        self.client = OpenAI(api_key=api_key, base_url=KIMI_BASE_URL)

    def extract(self, system_prompt: str, user_prompt: str) -> tuple[str, dict]:
        """返回 (raw_text, usage). usage 含 prompt_tokens / completion_tokens."""
        resp = self.client.chat.completions.create(
            model=KIMI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=LLM_TEMPERATURE,
            max_tokens=LLM_MAX_TOKENS,
            timeout=LLM_TIMEOUT,
        )
        text = resp.choices[0].message.content.strip()
        usage = {
            "prompt_tokens": resp.usage.prompt_tokens,
            "completion_tokens": resp.usage.completion_tokens,
        }
        return text, usage


# ---------- 单篇处理 ----------
def process_one(
    paper_id: str,
    year: Optional[int],
    client: KimiClient,
    out_dir: str,
) -> ExtractionResult:
    """处理单篇: 读 markdown -> 调 Kimi -> 解析 JSON -> 写文件.
    返回轻量统计结构 (不含完整 JSON, 避免日志爆炸)."""
    from method_prompts import SYSTEM_PROMPT, build_user_prompt  # noqa: WPS433

    md_path = os.path.join(DOWNLOADED_DIR, paper_id, "full.md")
    if not os.path.isfile(md_path):
        return ExtractionResult(
            paper_id=paper_id, year=year, status="skip", error="no full.md"
        )

    text = read_paper_text(md_path)
    prompt = build_user_prompt(text)

    t0 = time.time()
    try:
        raw, usage = client.extract(SYSTEM_PROMPT, prompt)
    except Exception as exc:  # noqa: BLE001
        return ExtractionResult(
            paper_id=paper_id,
            year=year,
            status="api_fail",
            elapsed_sec=time.time() - t0,
            error=f"{type(exc).__name__}: {str(exc)[:200]}",
        )

    elapsed = time.time() - t0
    obj = _extract_json_object(raw)
    if not obj:
        # 保留 raw 供人工核查
        out_path = os.path.join(out_dir, f"{paper_id}.raw.txt")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(raw)
        return ExtractionResult(
            paper_id=paper_id,
            year=year,
            status="json_fail",
            elapsed_sec=elapsed,
            error=f"raw saved to {os.path.basename(out_path)}",
        )

    own = obj.get("own_methods", []) or []
    refs = obj.get("referenced_methods", []) or []
    edges = obj.get("evolution_edges", []) or []

    # 落盘: 完整 JSON + 元数据
    record = {
        "paper_id": paper_id,
        "year": year,
        "model": KIMI_MODEL,
        "extracted_at": datetime.now().isoformat(timespec="seconds"),
        "own_methods": own,
        "referenced_methods": refs,
        "evolution_edges": edges,
        "_meta": {
            "input_chars": len(text),
            "elapsed_seconds": round(elapsed, 2),
            "prompt_tokens": usage["prompt_tokens"],
            "completion_tokens": usage["completion_tokens"],
            "key_tag": client.key_tag,
        },
    }
    out_path = os.path.join(out_dir, f"{paper_id}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)

    return ExtractionResult(
        paper_id=paper_id,
        year=year,
        status="success",
        elapsed_sec=elapsed,
        own_methods_n=len(own),
        refs_n=len(refs),
        edges_n=len(edges),
    )


# ---------- 主流程 ----------
def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    # 允许 from method_prompts import ...
    if THIS_DIR not in sys.path:
        sys.path.insert(0, THIS_DIR)

    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="只处理前 N 篇 (调试)")
    ap.add_argument(
        "--parallel", type=int, default=1, help="并发 worker 数 (建议 1 = 试跑, 2 = 全量)"
    )
    ap.add_argument(
        "--resume", action="store_true", help="跳过已有输出 JSON 的篇 (断点续跑)"
    )
    ap.add_argument(
        "--samples",
        type=str,
        default="",
        help="只跑指定的篇 (逗号分隔的 paper_id), 调试用",
    )
    args = ap.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 1. 加载年份映射
    year_map = load_year_map()
    print(f"[init] year_map: {len(year_map)} 篇")

    # 2. 决定要处理的篇列表
    if args.samples:
        paper_ids = [s.strip() for s in args.samples.split(",") if s.strip()]
        print(f"[init] 指定篇模式: {len(paper_ids)} 篇")
    else:
        if not os.path.isdir(DOWNLOADED_DIR):
            print(f"[ERR] 找不到 {DOWNLOADED_DIR}", file=sys.stderr)
            return 1
        paper_ids = sorted(
            d for d in os.listdir(DOWNLOADED_DIR)
            if os.path.isdir(os.path.join(DOWNLOADED_DIR, d))
        )
        if args.limit:
            paper_ids = paper_ids[: args.limit]

    # 3. resume: 跳过已有 .json
    if args.resume:
        before = len(paper_ids)
        paper_ids = [
            p for p in paper_ids
            if not os.path.isfile(os.path.join(OUTPUT_DIR, f"{p}.json"))
        ]
        print(f"[init] resume: 跳过 {before - len(paper_ids)} 已有篇, 还剩 {len(paper_ids)} 篇待跑")

    if not paper_ids:
        print("[done] 无篇可处理")
        return 0

    # 4. 准备 worker 池: 每个 worker 绑定一个 key (轮询)
    n_workers = max(1, min(args.parallel, len(MOONSHOT_KEYS)))
    clients = [KimiClient(MOONSHOT_KEYS[i % len(MOONSHOT_KEYS)]) for i in range(n_workers)]
    print(f"[init] {n_workers} worker(s), keys = {[c.key_tag for c in clients]}")
    print(f"[init] 待处理 {len(paper_ids)} 篇, 输出到 {OUTPUT_DIR}\n")

    t_start = time.time()
    results: list[ExtractionResult] = []

    if n_workers == 1:
        # 顺序模式, 便于调试观察
        client = clients[0]
        for i, pid in enumerate(paper_ids, 1):
            year = year_map.get(pid)
            r = process_one(pid, year, client, OUTPUT_DIR)
            results.append(r)
            _print_progress(i, len(paper_ids), r)
    else:
        # 并发: 用 RR 把 paper_id 分配给固定的 worker
        # 注意 ThreadPoolExecutor 不保证 worker affinity, 我们用任务自带的 client_idx
        with ThreadPoolExecutor(max_workers=n_workers) as ex:
            futures = {}
            for i, pid in enumerate(paper_ids):
                client = clients[i % n_workers]
                year = year_map.get(pid)
                fut = ex.submit(process_one, pid, year, client, OUTPUT_DIR)
                futures[fut] = (i + 1, pid)
            for fut in as_completed(futures):
                _, _ = futures[fut]
                r = fut.result()
                results.append(r)
                _print_progress(len(results), len(paper_ids), r)

    total_elapsed = time.time() - t_start
    _summarize(results, total_elapsed)
    _write_failures(results)
    return 0


def _print_progress(i: int, total: int, r: ExtractionResult) -> None:
    tag = {
        "success": "OK    ",
        "json_fail": "JSON !",
        "api_fail": "API  !",
        "skip": "SKIP  ",
    }.get(r.status, r.status)
    line = (
        f"  [{i:>3}/{total}] {tag} {r.elapsed_sec:>5.1f}s  "
        f"own={r.own_methods_n} refs={r.refs_n} edges={r.edges_n}  "
        f"y={r.year if r.year else '----':<5}  {r.paper_id[:50]}"
    )
    if r.error:
        line += f"  | {r.error[:60]}"
    print(line)


def _summarize(results: list[ExtractionResult], total_elapsed: float) -> None:
    n = len(results)
    by = {"success": 0, "json_fail": 0, "api_fail": 0, "skip": 0}
    total_own = total_refs = total_edges = 0
    for r in results:
        by[r.status] = by.get(r.status, 0) + 1
        total_own += r.own_methods_n
        total_refs += r.refs_n
        total_edges += r.edges_n
    print("\n" + "=" * 70)
    print(f"总篇        : {n}")
    print(f"耗时        : {total_elapsed:.1f}s  ({total_elapsed/60:.1f} 分钟)")
    print(f"成功        : {by['success']}")
    print(f"JSON 失败   : {by['json_fail']}  (raw 已存盘, 可人工核)")
    print(f"API 失败    : {by['api_fail']}")
    print(f"跳过        : {by['skip']}")
    print("-" * 70)
    print(f"own_methods 总数       : {total_own}")
    print(f"referenced_methods 总数 : {total_refs}")
    print(f"evolution_edges 总数    : {total_edges}")
    print("=" * 70)
    print(f"输出目录: {OUTPUT_DIR}")


def _write_failures(results: list[ExtractionResult]) -> None:
    fails = [asdict(r) for r in results if r.status in ("json_fail", "api_fail")]
    with open(FAILURES_PATH, "w", encoding="utf-8") as f:
        json.dump(fails, f, ensure_ascii=False, indent=2)
    if fails:
        print(f"失败列表: {FAILURES_PATH}  ({len(fails)} 篇)")


if __name__ == "__main__":
    sys.exit(main())
