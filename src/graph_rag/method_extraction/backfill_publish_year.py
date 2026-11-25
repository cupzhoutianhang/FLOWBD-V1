"""
backfill_publish_year.py — 三级降级抽取文献发表年份

数据源: pdf_to_md/extraction_results/downloaded_files/<paper>/full.md
输出:
  - publish_year_report.csv  : paper_id, filename, year, source, match_text, note,
                               llm_confidence, llm_evidence, llm_reason
  - 控制台日志              : 每篇命中情况 + 末尾汇总覆盖率

抽取策略:
  L1  filename_regex   文件名里的 4 位年份 (1990–2026)
  L2  content_regex    正文前 ~2000 字符:
                         P1 文章编号...（YYYY）
                         P2 DOI 中 issn 后年份 (兼容 OCR 空格 + 增刊号)
                         P3 收稿日期: YYYY
  L3  llm              兜底, 仅当 --use-llm 时启用; GLM-4.7 严格 JSON 输出:
                         {year, confidence: high|medium|low, evidence, reason}
                       year 必须在 [LLM_YEAR_MIN, LLM_YEAR_MAX] 区间
                       source 落在 llm_high / llm_medium / llm_low / failed

用法:
  python backfill_publish_year.py                  # 只跑 L1 + L2
  python backfill_publish_year.py --use-llm        # 对前两级未命中的篇调 LLM 兜底
  python backfill_publish_year.py --limit 20       # 仅处理前 20 篇 (调试)
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Any

# ---------- 路径配置 ----------
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(THIS_DIR)))
DOWNLOADED_DIR = os.path.join(
    PROJECT_ROOT, "pdf_to_md", "extraction_results", "downloaded_files"
)
REPORT_CSV = os.path.join(THIS_DIR, "publish_year_report.csv")

# ---------- 合法年份区间 ----------
YEAR_MIN = 1990
YEAR_MAX = datetime.now().year  # 2026

# LLM 用更紧的区间, 符合用户要求 (2005-2025)
LLM_YEAR_MIN = 2005
LLM_YEAR_MAX = 2025
LLM_HEAD_CHARS = 3200  # 喂给 LLM 的最大字符数 (头 1500 + 尾 1500 + 分隔符)

# ---------- 正则 (按优先级) ----------
# L1: 文件名 4 位年份
RE_FILENAME_YEAR = re.compile(r"(?<!\d)(19[9]\d|20[0-2]\d)(?!\d)")

# 连字符变体: ASCII hyphen, en-dash, em-dash, 全角连字符
DASH = r"\-–—－"

# L2-P1: 文章编号 ... (YYYY) | （YYYY）
#   样例: 文章编号：1000-6613 （2021） 09-4853-16
#         文章编号：1000–6613（2018）08–3056–11
#         文章编号：0438—1157（2016）04—1453—06
RE_ARTICLE_NO_YEAR = re.compile(
    rf"文章编号[\s：:]*[\d{DASH}]+\s*[（(]\s*(\d{{4}})\s*[）)]"
)

# L2-P2: DOI 中 issn.<jrn>.YYYY{-期号 | .期号}
#   样例（紧凑）  : DOI：10.16085/j.issn.1000-6613.2017-1761
#   样例（含空格） : DOI: 10. 16085/j. issn. 1000-6613. 2016. s2. 012
#   样例（增刊）  : issn.0438-1157.2014.z1.001
RE_DOI_YEAR = re.compile(
    rf"issn[\s\.]*\d[\d\s\.{DASH}]*\.\s*(\d{{4}})\s*[\.{DASH}]\s*[a-z]?\d"
)

# L2-P3: 收稿日期 YYYY
#   样例: 收稿日期：2022-03-15  /  收稿日期: 2022 年 3 月
RE_RECEIVED_YEAR = re.compile(
    rf"收稿日期[\s：:]*(\d{{4}})\s*[{DASH}/年]"
)

CONTENT_HEAD_CHARS = 2500  # 前多少字符里找


@dataclass
class YearResult:
    paper_id: str
    filename: str
    year: Optional[int]
    # regex_filename / regex_article_no / regex_doi / regex_received
    # / llm_high / llm_medium / llm_low / failed
    source: str
    match_text: str = ""
    note: str = ""
    llm_confidence: str = ""
    llm_evidence: str = ""
    llm_reason: str = ""


def _valid_year(y: int) -> bool:
    return YEAR_MIN <= y <= YEAR_MAX


def try_level1_filename(filename: str) -> Optional[YearResult]:
    """文件名 regex."""
    matches = RE_FILENAME_YEAR.findall(filename)
    valid = [int(m) for m in matches if _valid_year(int(m))]
    if not valid:
        return None
    # 文件名里出现多个年份的极少, 取最大
    year = max(valid)
    return YearResult(
        paper_id=filename,
        filename=filename,
        year=year,
        source="regex_filename",
        match_text=filename,
    )


def try_level2_content(filename: str, head: str) -> Optional[YearResult]:
    """正文前 N 字符的优先级匹配."""
    # P1 文章编号 — 最稳, 直接拿
    m = RE_ARTICLE_NO_YEAR.search(head)
    if m:
        year = int(m.group(1))
        if _valid_year(year):
            return YearResult(
                paper_id=filename,
                filename=filename,
                year=year,
                source="regex_article_no",
                match_text=m.group(0),
            )

    # P2 DOI
    m = RE_DOI_YEAR.search(head)
    if m:
        year = int(m.group(1))
        if _valid_year(year):
            return YearResult(
                paper_id=filename,
                filename=filename,
                year=year,
                source="regex_doi",
                match_text=m.group(0),
            )

    # P3 收稿日期
    m = RE_RECEIVED_YEAR.search(head)
    if m:
        year = int(m.group(1))
        if _valid_year(year):
            return YearResult(
                paper_id=filename,
                filename=filename,
                year=year,
                source="regex_received",
                match_text=m.group(0),
            )

    return None


LLM_SYSTEM_PROMPT = (
    "你是文献年份判断助手。只能返回一个 JSON 对象，不能有任何其他文字或 markdown。"
)

LLM_USER_PROMPT_TEMPLATE = """从下面这段中文学术文献首页文本中, 判断该论文的发表年份.

文本片段 (可能含 OCR 噪声):
<<<
{head}
>>>

判断规则:
1. 年份必须在 {ymin}-{ymax} 之间, 超出区间一律返回 null
2. 如文中明确出现 "文章编号年份 / 期刊卷年份 / 出版年份", confidence 标 "high"
3. 如只能从参考文献最新年份, 作者单位成立时间, 引用 "近年来 XX 年" 等间接信息反推, confidence 标 "medium"
4. 如文本是 OCR 严重乱码 / 无任何时间线索, 返回 year:null + confidence:"low" + reason 说明原因

严格按下面 JSON 格式返回, 字段必须齐全, 不要任何附加说明, 不要 markdown 代码块:
{{
  "year": <2005-2025 之间的整数, 或 null>,
  "confidence": "high" | "medium" | "low",
  "evidence": "<支持判断的原文片段, 不超过 50 字>",
  "reason": "<为什么这样判断, 不超过 80 字>"
}}
"""


_LLM_CLIENT: Optional[Any] = None  # 延迟初始化, 仅 --use-llm 时加载
_KIMI_CLIENT: Optional[Any] = None  # 延迟初始化, 仅 --use-kimi 时加载

# Kimi K2 配置 (年份兜底, 比 Qwen-7B 强很多, 单价仍便宜)
KIMI_MODEL = "kimi-k2-0905-preview"
KIMI_BASE_URL = "https://api.moonshot.cn/v1"
KIMI_API_KEY = __import__("os").environ.get("MOONSHOT_API_KEY", "")


def _get_llm():
    """延迟加载现有 LLMConfig (硅基流动).
    抽年份是轻量任务, 避开默认的思考型 GLM-4.7 (实测 >5 分钟超时),
    改用 Qwen2.5-7B 非思考模型, 同时把读超时压到 60 秒."""
    global _LLM_CLIENT
    if _LLM_CLIENT is None:
        src_dir = os.path.dirname(os.path.dirname(THIS_DIR))  # src/
        if src_dir not in sys.path:
            sys.path.insert(0, src_dir)
        from agent.part1_knowledge_arsenal import LLMConfig  # noqa: WPS433
        _LLM_CLIENT = LLMConfig(model="Qwen/Qwen2.5-7B-Instruct")
        _LLM_CLIENT.timeout = (15, 60)  # (connect, read)
    return _LLM_CLIENT


def _get_kimi_client():
    """延迟加载 Kimi K2 OpenAI 客户端 (绕开 LLMConfig 的 GLM 流式打印副作用)."""
    global _KIMI_CLIENT
    if _KIMI_CLIENT is None:
        from openai import OpenAI  # noqa: WPS433

        _KIMI_CLIENT = OpenAI(api_key=KIMI_API_KEY, base_url=KIMI_BASE_URL)
    return _KIMI_CLIENT


def _extract_json_object(text: str) -> Optional[dict]:
    """从 LLM 返回里抠出 JSON. 三级降级:
       1) 直接 json.loads
       2) 抠最外层 {...} 后 loads
       3) 正则 fallback: 单独抠 year / confidence / evidence / reason 四字段
    第 3 级容忍 Qwen 在严重乱码输入上吐出的畸形 JSON
    (如 `"year": 2` 截断, 缺逗号, null 不带引号)."""
    if not text:
        return None
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```$", "", t)

    # 1) 整段 loads
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass

    # 2) 抠 {...}
    s, e = t.find("{"), t.rfind("}")
    if s != -1 and e > s:
        try:
            return json.loads(t[s : e + 1])
        except json.JSONDecodeError:
            pass

    # 3) regex fallback - 字段单独抠
    out: dict = {}
    m = re.search(r'"year"\s*:\s*(\d{4}|null)', t)
    if m:
        v = m.group(1)
        out["year"] = None if v == "null" else int(v)
    m = re.search(r'"confidence"\s*:\s*"?(high|medium|low)"?', t, re.IGNORECASE)
    if m:
        out["confidence"] = m.group(1).lower()
    m = re.search(r'"evidence"\s*:\s*"([^"]{0,200})', t)
    if m:
        out["evidence"] = m.group(1)
    m = re.search(r'"reason"\s*:\s*"([^"]{0,300})', t)
    if m:
        out["reason"] = m.group(1)
    return out if out else None


def try_level3_llm(filename: str, head: str) -> YearResult:
    """LLM 兜底. 严格 JSON; 校验年份区间和 confidence 枚举.
    无论 LLM 返回什么, 这里一定返回一个 YearResult (可能 source=failed)."""
    prompt = LLM_USER_PROMPT_TEMPLATE.format(
        head=head[:LLM_HEAD_CHARS],
        ymin=LLM_YEAR_MIN,
        ymax=LLM_YEAR_MAX,
    )
    client = _get_llm()
    raw = client.call_llm(
        prompt=prompt,
        system_prompt=LLM_SYSTEM_PROMPT,
        temperature=0.0,
        max_tokens=512,
        stream=False,
    )

    # 网络/限流错误时 call_llm 返回 "❌ ..." 字符串
    if not raw or raw.startswith("❌"):
        return YearResult(
            paper_id=filename,
            filename=filename,
            year=None,
            source="failed",
            note=f"LLM 调用失败: {raw[:80] if raw else 'empty'}",
        )

    obj = _extract_json_object(raw)
    if not obj:
        return YearResult(
            paper_id=filename,
            filename=filename,
            year=None,
            source="failed",
            note=f"LLM 返回无法解析为 JSON: {raw[:80]}",
        )

    conf = str(obj.get("confidence", "")).lower().strip()
    if conf not in {"high", "medium", "low"}:
        conf = "low"

    evidence = str(obj.get("evidence", ""))[:120]
    reason = str(obj.get("reason", ""))[:200]

    raw_year = obj.get("year")
    year_int: Optional[int] = None
    if raw_year is not None and str(raw_year).lower() != "null":
        try:
            yi = int(str(raw_year).strip())
            if LLM_YEAR_MIN <= yi <= LLM_YEAR_MAX:
                year_int = yi
        except (ValueError, TypeError):
            year_int = None

    # year 抽到且区间合法 -> llm_<conf>
    if year_int is not None:
        return YearResult(
            paper_id=filename,
            filename=filename,
            year=year_int,
            source=f"llm_{conf}",
            match_text="",
            note="",
            llm_confidence=conf,
            llm_evidence=evidence,
            llm_reason=reason,
        )

    # year 为 null (LLM 自己判定无法确定) -> failed, 但保留 LLM 的解释
    return YearResult(
        paper_id=filename,
        filename=filename,
        year=None,
        source="failed",
        note="LLM 判定无法确定",
        llm_confidence=conf,
        llm_evidence=evidence,
        llm_reason=reason,
    )


def try_level3_kimi(filename: str, head: str) -> YearResult:
    """Kimi K2 兜底. 对 Qwen-7B 失败的篇用更强的模型重试.
    Kimi K2 是 1T MoE, 在 OCR 烂的篇上 JSON 输出更稳, 中文工程文档抽取质量更高."""
    client = _get_kimi_client()
    prompt = LLM_USER_PROMPT_TEMPLATE.format(
        head=head[:LLM_HEAD_CHARS],
        ymin=LLM_YEAR_MIN,
        ymax=LLM_YEAR_MAX,
    )
    try:
        resp = client.chat.completions.create(
            model=KIMI_MODEL,
            messages=[
                {"role": "system", "content": LLM_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            max_tokens=512,
            timeout=60,
        )
        raw = resp.choices[0].message.content.strip()
    except Exception as exc:  # noqa: BLE001
        return YearResult(
            paper_id=filename,
            filename=filename,
            year=None,
            source="failed",
            note=f"Kimi 调用失败: {type(exc).__name__}: {str(exc)[:80]}",
        )

    obj = _extract_json_object(raw)
    if not obj:
        return YearResult(
            paper_id=filename,
            filename=filename,
            year=None,
            source="failed",
            note=f"Kimi 返回无法解析为 JSON: {raw[:80]}",
        )

    conf = str(obj.get("confidence", "")).lower().strip()
    if conf not in {"high", "medium", "low"}:
        conf = "low"
    evidence = str(obj.get("evidence", ""))[:120]
    reason = str(obj.get("reason", ""))[:200]

    raw_year = obj.get("year")
    year_int: Optional[int] = None
    if raw_year is not None and str(raw_year).lower() != "null":
        try:
            yi = int(str(raw_year).strip())
            if LLM_YEAR_MIN <= yi <= LLM_YEAR_MAX:
                year_int = yi
        except (ValueError, TypeError):
            year_int = None

    if year_int is not None:
        return YearResult(
            paper_id=filename,
            filename=filename,
            year=year_int,
            source=f"kimi_{conf}",
            match_text="",
            note="",
            llm_confidence=conf,
            llm_evidence=evidence,
            llm_reason=reason,
        )

    return YearResult(
        paper_id=filename,
        filename=filename,
        year=None,
        source="failed",
        note="Kimi 判定无法确定",
        llm_confidence=conf,
        llm_evidence=evidence,
        llm_reason=reason,
    )


def read_head(md_path: str, n: int = CONTENT_HEAD_CHARS) -> str:
    with open(md_path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read(n)


def read_head_and_tail(md_path: str, head_n: int = 1500, tail_n: int = 1500) -> str:
    """喂给 LLM 的两段拼接: 头 (摘要/文章编号) + 尾 (参考文献年份).
    OCR 空括号的篇靠尾部参考文献年份反推发表年份."""
    with open(md_path, "r", encoding="utf-8", errors="ignore") as f:
        txt = f.read()
    if len(txt) <= head_n + tail_n:
        return txt
    return txt[:head_n] + "\n\n[...省略正文中段...]\n\n" + txt[-tail_n:]


def process_one(paper_dir: str) -> YearResult:
    filename = os.path.basename(paper_dir)
    md_path = os.path.join(paper_dir, "full.md")
    if not os.path.isfile(md_path):
        return YearResult(
            paper_id=filename,
            filename=filename,
            year=None,
            source="failed",
            note="full.md 不存在",
        )

    # L1
    r = try_level1_filename(filename)
    if r:
        return r

    # L2
    head = read_head(md_path)
    r = try_level2_content(filename, head)
    if r:
        return r

    return YearResult(
        paper_id=filename,
        filename=filename,
        year=None,
        source="failed",
        note="L1+L2 均未命中",
    )


def write_report(results: list[YearResult], path: str) -> None:
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "paper_id",
                "filename",
                "year",
                "source",
                "match_text",
                "note",
                "llm_confidence",
                "llm_evidence",
                "llm_reason",
            ]
        )
        for r in results:
            w.writerow(
                [
                    r.paper_id,
                    r.filename,
                    r.year if r.year is not None else "",
                    r.source,
                    r.match_text,
                    r.note,
                    r.llm_confidence,
                    r.llm_evidence,
                    r.llm_reason,
                ]
            )


def summarize(results: list[YearResult]) -> None:
    total = len(results)
    by_source: dict[str, int] = {}
    for r in results:
        by_source[r.source] = by_source.get(r.source, 0) + 1

    hit = total - by_source.get("failed", 0)
    print("\n" + "=" * 60)
    print(f"总篇数         : {total}")
    print(f"命中年份       : {hit}  ({hit / total * 100:.1f}%)")
    print(f"未命中 (failed): {by_source.get('failed', 0)}")
    print("-" * 60)
    print("命中来源分布:")
    for src in [
        "regex_filename",
        "regex_article_no",
        "regex_doi",
        "regex_received",
        "llm_high",
        "llm_medium",
        "llm_low",
        "kimi_high",
        "kimi_medium",
        "kimi_low",
    ]:
        n = by_source.get(src, 0)
        if n:
            print(f"  {src:<20} {n}")
    # LLM 兜底专项
    llm_total = sum(by_source.get(k, 0) for k in ("llm_high", "llm_medium", "llm_low"))
    if llm_total:
        print("-" * 60)
        print("Qwen-7B 兜底汇总:")
        print(f"  救回总数            {llm_total}")
        print(f"  high  (可信)         {by_source.get('llm_high', 0)}")
        print(f"  medium (反推)        {by_source.get('llm_medium', 0)}")
        print(f"  low   (需人工核验)   {by_source.get('llm_low', 0)}")
    kimi_total = sum(by_source.get(k, 0) for k in ("kimi_high", "kimi_medium", "kimi_low"))
    if kimi_total:
        print("-" * 60)
        print("Kimi K2 兜底汇总:")
        print(f"  救回总数            {kimi_total}")
        print(f"  high  (可信)         {by_source.get('kimi_high', 0)}")
        print(f"  medium (反推)        {by_source.get('kimi_medium', 0)}")
        print(f"  low   (需人工核验)   {by_source.get('kimi_low', 0)}")
    print("=" * 60)
    print(f"详细报告: {REPORT_CSV}")


def main() -> int:
    # Windows GBK 控制台不识别一些 unicode (如 U+2043), 强制 utf-8 + replace
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--use-llm",
        action="store_true",
        help="对 L1+L2 未命中的篇调 Qwen-7B (硅基) 兜底",
    )
    ap.add_argument(
        "--use-kimi",
        action="store_true",
        help="再用 Kimi K2 (Moonshot) 对仍 failed 的篇重试. 可与 --use-llm 组合.",
    )
    ap.add_argument("--limit", type=int, default=None, help="只处理前 N 篇 (调试)")
    args = ap.parse_args()

    if not os.path.isdir(DOWNLOADED_DIR):
        print(f"[ERR] 找不到文献目录: {DOWNLOADED_DIR}", file=sys.stderr)
        return 1

    paper_dirs = sorted(
        os.path.join(DOWNLOADED_DIR, d)
        for d in os.listdir(DOWNLOADED_DIR)
        if os.path.isdir(os.path.join(DOWNLOADED_DIR, d))
    )
    if args.limit:
        paper_dirs = paper_dirs[: args.limit]

    print(f"[scan] 扫描 {len(paper_dirs)} 篇文献...")
    print(f"       数据源: {DOWNLOADED_DIR}\n")

    results: list[YearResult] = []
    for i, pd in enumerate(paper_dirs, 1):
        r = process_one(pd)
        results.append(r)
        tag = f"{r.year}" if r.year else "----"
        print(f"  [{i:>3}/{len(paper_dirs)}] {tag} {r.source:<18} {r.filename[:60]}")

    # L3a 兜底: Qwen-7B (硅基)
    if args.use_llm:
        failed_idx = [i for i, r in enumerate(results) if r.source == "failed"]
        if failed_idx:
            print(
                f"\n[qwen] Qwen-7B 兜底 {len(failed_idx)} 篇 "
                f"(严格 JSON, head+tail 拼接)..."
            )
            for n, i in enumerate(failed_idx, 1):
                old = results[i]
                md_path = os.path.join(DOWNLOADED_DIR, old.filename, "full.md")
                if not os.path.isfile(md_path):
                    print(f"  [{n:>3}/{len(failed_idx)}] SKIP   {old.filename[:55]} (无 markdown)")
                    continue
                text = read_head_and_tail(md_path, head_n=1500, tail_n=1500)
                new = try_level3_llm(old.filename, text)
                results[i] = new
                year_tag = f"{new.year}" if new.year else "----"
                evid = (new.llm_evidence or new.note)[:40]
                print(
                    f"  [{n:>3}/{len(failed_idx)}] {year_tag} {new.source:<11} "
                    f"{old.filename[:40]:<40}  | {evid}"
                )

    # L3b 兜底: Kimi K2 (Moonshot) — 对仍 failed 的篇重试, 比 Qwen 强很多
    if args.use_kimi:
        failed_idx = [i for i, r in enumerate(results) if r.source == "failed"]
        if failed_idx:
            print(
                f"\n[kimi] Kimi K2 兜底 {len(failed_idx)} 篇 "
                f"(model={KIMI_MODEL}, head+tail 拼接)..."
            )
            for n, i in enumerate(failed_idx, 1):
                old = results[i]
                md_path = os.path.join(DOWNLOADED_DIR, old.filename, "full.md")
                if not os.path.isfile(md_path):
                    print(f"  [{n:>3}/{len(failed_idx)}] SKIP   {old.filename[:55]} (无 markdown)")
                    continue
                text = read_head_and_tail(md_path, head_n=1500, tail_n=1500)
                new = try_level3_kimi(old.filename, text)
                results[i] = new
                year_tag = f"{new.year}" if new.year else "----"
                evid = (new.llm_evidence or new.note)[:40]
                print(
                    f"  [{n:>3}/{len(failed_idx)}] {year_tag} {new.source:<11} "
                    f"{old.filename[:40]:<40}  | {evid}"
                )

    write_report(results, REPORT_CSV)
    summarize(results)
    return 0


if __name__ == "__main__":
    sys.exit(main())
