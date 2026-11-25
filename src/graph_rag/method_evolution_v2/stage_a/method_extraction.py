"""Stage A 单篇论文抽取编排.

v1 (旧): LLM 复制 evidence_quote, 本地做 exact/normalized 定位.
v2 (本轮 spec): LLM 只返回 evidence_sentence_ids, 本地用句子索引解析证据.
  - 严格 1 主调用 + 最多 1 重试 (JSON 解析失败时)
  - 每篇 ≤2 次调用, 全局 ≤20 次
  - 单篇失败继续
  - 无演化关系

只抽方法。
"""
from __future__ import annotations

import hashlib
import json
import re

from method_evolution_v2.stage_a import llm_client
from method_evolution_v2.stage_a import prompts as prompts_mod
from method_evolution_v2.stage_a import evidence_validation as ev
from method_evolution_v2.stage_a import sentence_indexer as si


STAGE_A_VERSION = "2.0"    # v2 = sentence-id protocol


# ============================================================
# Section pack 用于给 LLM 上下文 (v2 从 sentence_index 里生成)
# ============================================================

# 用于组建 section pack 的顺序 (按学术阅读顺序)
SECTION_PACK_ORDER = (
    "title",
    "abstract",
    "introduction",
    "theory_model",
    "system_design",
    "simulation_calculation",
    "methods",
    "case_analysis",
    "results_discussion",
    "results",
    "discussion",
    "conclusion",
    "patent_analysis",
)

OTHER_SECTIONS_METHOD_HINTS = re.compile(
    r"(方法|方案|技术|工艺|装置|系统|模型|流程|结构|设计|优化|策略|路线|材料|机理|表征|实验|分析|讨论)"
)


def build_sentence_index_for_llm(sections_json: dict, paper_id: str) -> tuple:
    """v2 输入构建: 出 sentence index (dict by sentence_id) + LLM prompt 的 pack text.

    只保留实质章节 + 相关 other_sections; 目的是控制 prompt 体积.
    """
    all_sents = si.build_sentence_index(sections_json, paper_id)
    # 过滤: 保留 SECTION_PACK_ORDER + method-hinted other_sections
    keep = []
    for s in all_sents:
        st = s.section_type
        if st in SECTION_PACK_ORDER:
            keep.append(s)
            continue
        if st == "other_sections" and s.section_name \
                and OTHER_SECTIONS_METHOD_HINTS.search(s.section_name):
            keep.append(s)
    sentence_index = {s.sentence_id: s.to_dict() for s in keep}
    pack_text = si.sentence_index_to_pack(keep)
    return sentence_index, pack_text, keep


# ============================================================
# 工具
# ============================================================

def _make_method_id(paper_id: str, kind: str, index: int, name: str) -> str:
    h = hashlib.sha1(f"{paper_id}|{kind}|{index}|{name}".encode("utf-8")).hexdigest()[:8]
    return f"{paper_id}::{kind}::{index:02d}::{h}"


def parse_llm_json(text: str) -> tuple:
    """尝试解析 LLM 返回为 JSON 对象.

    Returns: (ok: bool, obj: dict, error: str)
    """
    if not text:
        return False, {}, "empty_response"
    s = text.strip()
    if s.startswith("```"):
        m = re.match(r"^```(?:json)?\s*(.*?)```", s, re.DOTALL | re.IGNORECASE)
        if m:
            s = m.group(1).strip()
    try:
        obj = json.loads(s)
        if not isinstance(obj, dict):
            return False, {}, f"json_top_level_not_object: {type(obj).__name__}"
        return True, obj, ""
    except json.JSONDecodeError as e:
        return False, {}, f"json_decode_error: {e}"


# ============================================================
# 主入口 (v2)
# ============================================================

def extract_paper(paper_id: str, sections_json: dict,
                  paper_type: str, primary_storage_domain: str,
                  technology_subfield: str, application_contexts,
                  model: str = None,
                  allow_retry: bool = True,
                  log_sink: list = None) -> dict:
    """v2 单篇抽取: sentence-id 引用协议.

    Returns:
      {
        "paper_id": ...,
        "call_count": int,
        "llm_calls": [{...}, ...],
        "json_parse_ok": bool,
        "json_parse_error": str,
        "own_methods_raw": [ ... ],
        "referenced_methods_raw": [ ... ],
        "methods_classified": [ ... resolve_method_by_sentence_ids 输出 ... ],
        "sentence_index": {sid: sentence_dict},   # 全部句子
        "sentence_pack_chars": int,
        "usage_total": {...},
        "stage_a_version": STAGE_A_VERSION,
      }
    """
    log_sink = log_sink if log_sink is not None else []

    # 构建 sentence index + LLM pack
    sentence_index, pack_text, _sent_list = build_sentence_index_for_llm(
        sections_json, paper_id
    )

    apps_repr = json.dumps(list(application_contexts) if application_contexts else [],
                          ensure_ascii=False)
    user_prompt = prompts_mod.USER_PROMPT_TEMPLATE.format(
        paper_type=(paper_type or "unclear"),
        primary_storage_domain=(primary_storage_domain or "(空)"),
        technology_subfield=(technology_subfield or "(空)"),
        application_contexts=apps_repr,
        sentence_pack=pack_text,
    )
    sys_prompt = prompts_mod.SYSTEM_PROMPT

    llm_calls = []
    usage_total = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    call_count = 0

    # 主
    call_count += 1
    log_sink.append({"paper_id": paper_id, "attempt": "primary", "model": model})
    r1 = llm_client.call_chat(sys_prompt, user_prompt, model=model)
    llm_calls.append({"attempt": "primary", "ok": r1["ok"],
                      "error": r1.get("error", ""), "usage": r1.get("usage") or {},
                      "model": r1.get("model")})
    _accum_usage(usage_total, r1.get("usage") or {})
    text_used = r1.get("text", "") if r1["ok"] else ""
    parse_ok, obj, parse_err = parse_llm_json(text_used) if r1["ok"] else \
        (False, {}, r1.get("error", ""))

    # 重试 (仅 JSON 失败)
    if not parse_ok and allow_retry:
        call_count += 1
        log_sink.append({"paper_id": paper_id, "attempt": "retry",
                         "reason": parse_err, "model": model})
        r2 = llm_client.call_chat(
            sys_prompt,
            user_prompt + "\n\n注意: 只输出 JSON 对象, 不要 markdown 围栏. "
                          "所有 evidence_sentence_ids 必须来自上面正文里真实出现的 ID.",
            model=model,
        )
        llm_calls.append({"attempt": "retry", "ok": r2["ok"],
                          "error": r2.get("error", ""), "usage": r2.get("usage") or {},
                          "model": r2.get("model")})
        _accum_usage(usage_total, r2.get("usage") or {})
        text_used = r2.get("text", "") if r2["ok"] else text_used
        parse_ok, obj, parse_err = parse_llm_json(text_used) if r2["ok"] else \
            (False, {}, r2.get("error", ""))

    own_raw = obj.get("own_methods") if isinstance(obj, dict) else None
    ref_raw = obj.get("referenced_methods") if isinstance(obj, dict) else None
    own_raw = own_raw if isinstance(own_raw, list) else []
    ref_raw = ref_raw if isinstance(ref_raw, list) else []

    classified = []
    for idx, m in enumerate(own_raw):
        if not isinstance(m, dict):
            continue
        c = ev.resolve_method_by_sentence_ids(m, sentence_index,
                                              kind="own", paper_type=paper_type or "")
        c["paper_id"] = paper_id
        c["method_id"] = _make_method_id(paper_id, "own", idx, c["name"] or "unnamed")
        classified.append(c)
    for idx, m in enumerate(ref_raw):
        if not isinstance(m, dict):
            continue
        c = ev.resolve_method_by_sentence_ids(m, sentence_index,
                                              kind="referenced", paper_type=paper_type or "")
        c["paper_id"] = paper_id
        c["method_id"] = _make_method_id(paper_id, "referenced", idx, c["name"] or "unnamed")
        classified.append(c)

    classified = ev.dedupe_methods_prefer_longer_evidence(classified)

    return {
        "paper_id": paper_id,
        "call_count": call_count,
        "llm_calls": llm_calls,
        "json_parse_ok": parse_ok,
        "json_parse_error": parse_err,
        "raw_llm_text_last": text_used,
        "own_methods_raw": own_raw,
        "referenced_methods_raw": ref_raw,
        "methods_classified": classified,
        "sentence_index": sentence_index,
        "sentence_pack_chars": len(pack_text),
        "usage_total": usage_total,
        "stage_a_version": STAGE_A_VERSION,
    }


def _accum_usage(agg: dict, u: dict) -> None:
    for k in ("prompt_tokens", "completion_tokens", "total_tokens"):
        agg[k] = agg.get(k, 0) + int(u.get(k, 0) or 0)
