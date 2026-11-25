"""Stage A 全量 runner 核心逻辑 (spec 四).

包含:
  - paper_id → 目录名 hash 映射
  - input_manifest 生成与比对 (SHA256 版本锁)
  - 单篇 skip / re-run 决策
  - 单篇执行封装 (可注入 llm_caller, 便于测试)
  - batch 划分
  - cost ledger 追加
  - failed / skipped CSV 追加

设计原则:
  - **零副作用直到 write_output=True**: 便于 dry-run 与单测
  - **LLM caller 可注入**: 单测用 mock, 真实运行用 llm_client
  - **禁止读 legacy**: 只从 sections_dir / paper_types_csv / taxonomy_csv 加载
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime

from method_evolution_v2 import config
from method_evolution_v2.io import section_parser as sp
from method_evolution_v2.stage_a import method_extraction as me
from method_evolution_v2.stage_a import sentence_indexer as si
from method_evolution_v2.stage_a import evidence_validation_v2 as ev2   # v2 validator
from method_evolution_v2.stage_a import provenance_v2 as pv2             # v2 provenance
from method_evolution_v2.stage_a import method_role as mrole             # spec 二 role
from method_evolution_v2.stage_a import name_normalization as nn         # spec 六 + 七
from method_evolution_v2.stage_a import prompts as prompts_mod


DEFAULT_MODEL = "moonshot-v1-auto"
DEFAULT_BATCH_SIZE = 25
STAGE_A_FULL_VERSION = "1.2"     # bump: 接 name_norm + demote + role + recovery integration


# ============================================================
# 版本锁 & 路径
# ============================================================

def paper_id_to_dir_name(paper_id: str) -> str:
    """把 paper_id 转成安全的短目录名 (12 位 sha1).

    避免路径里出现 CJK / 特殊字符 / 过长. 反查靠 paper_id_to_dir.csv.
    """
    if not paper_id:
        return "unknown"
    return hashlib.sha1(paper_id.encode("utf-8")).hexdigest()[:12]


def compute_full_md_sha256(md_path: str) -> str:
    h = hashlib.sha256()
    with open(md_path, "rb") as f:
        while True:
            chunk = f.read(1 << 16)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def build_input_manifest(paper_id: str, md_path: str,
                          model: str = DEFAULT_MODEL) -> dict:
    """给一篇论文构造输入 manifest — 供 3-way resume 决策 + 后期审计.

    字段分两类 (spec 一):
      - API 层字段: 变化时必须重跑 LLM (烧钱)
        {full_md_sha256, prompt_version, model,
         section_parser_version, stage_a_engine_version}
      - 验证器层字段: 变化时只需本地重校验 (零成本)
        {evidence_validation_version, provenance_version}
    """
    return {
        "paper_id": paper_id,
        "full_md_path": os.path.relpath(md_path, start=config.PROJECT_ROOT)
            if md_path.startswith(config.PROJECT_ROOT) else md_path,
        # ---- API 层 ----
        "full_md_sha256": compute_full_md_sha256(md_path),
        "prompt_version": prompts_mod.PROMPT_VERSION,
        "model": model,
        "section_parser_version": sp.SECTION_PARSER_VERSION,
        "stage_a_engine_version": me.STAGE_A_VERSION,
        # ---- 验证器层 (spec 一: 只影响本地校验, 不影响 API 结果) ----
        "evidence_validation_version": ev2.EVIDENCE_VALIDATION_VERSION,
        "provenance_version": pv2.PROVENANCE_VERSION,
        "method_role_version": mrole.METHOD_ROLE_VERSION,
        "name_normalization_version": nn.NAME_NORM_VERSION,
        # ---- 元 ----
        "stage_a_full_version": STAGE_A_FULL_VERSION,
    }


API_HASH_KEYS = ("full_md_sha256", "prompt_version", "model",
                  "section_parser_version", "stage_a_engine_version")

VALIDATOR_KEYS = ("evidence_validation_version", "provenance_version",
                    "method_role_version", "name_normalization_version")


def paper_needs_recovery(paper_type: str, methods_accepted: list,
                            manifest: dict) -> bool:
    """spec 一: research_article + accepted_own=0 + 未跑过 recovery."""
    if (paper_type or "").strip().lower() != "research_article":
        return False
    if manifest and manifest.get("recovery_used"):
        return False
    own_acc = sum(1 for m in methods_accepted if m.get("kind") == "own")
    return own_acc == 0


def merge_recovery_into_paper(paper_id: str, recovery_result: dict,
                                  base_dir: str = None) -> dict:
    """spec 一: 把 recovery 的方法追加到主 methods_*.json;
    recovery raw 单独文件; input_manifest 加 recovery_* 字段.

    - 主 raw_response.json **不改动**
    - 主 methods_accepted.json 追加 recovery 的 accepted (kind='own_recovery' 标记)
    - 主 methods_candidate/rejected 同样追加
    - validation_report 计数更新

    Returns 更新后的 stats dict.
    """
    base_dir = base_dir or config.STAGE_A_FULL_V1_PER_PAPER_DIR
    d = per_paper_dir(paper_id, base_dir)

    def _load(name):
        p = os.path.join(d, name)
        if not os.path.isfile(p): return []
        with open(p, "r", encoding="utf-8") as f: return json.load(f)

    def _dump(name, obj):
        with open(os.path.join(d, name), "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)

    # 追加 (不覆盖原 raw)
    for bucket_key, methods_key in (
            ("methods_accepted.json", "methods_accepted"),
            ("methods_candidate.json", "methods_candidate"),
            ("methods_rejected.json", "methods_rejected")):
        existing = _load(bucket_key)
        add = recovery_result.get(methods_key, [])
        for m in add:
            m["recovery_source"] = "stage_a_recovery_v1"
        _dump(bucket_key, existing + add)

    # recovery raw 单独文件
    _dump("recovery_raw_response.json", {
        "own_methods_raw": recovery_result.get("own_methods_raw", []),
        "raw_llm_text_last": recovery_result.get("raw_llm_text_last", ""),
        "json_parse_ok": recovery_result.get("json_parse_ok", False),
        "json_parse_error": recovery_result.get("json_parse_error", ""),
        "llm_calls": recovery_result.get("llm_calls", []),
        "usage_total": recovery_result.get("usage_total", {}),
        "recovery_engine_version": recovery_result.get(
            "recovery_engine_version", ""),
        "recovery_prompt_version": recovery_result.get(
            "recovery_prompt_version", ""),
    })

    # 更新 manifest
    im_path = os.path.join(d, "input_manifest.json")
    if os.path.isfile(im_path):
        with open(im_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    else:
        manifest = {}
    manifest["recovery_used"] = True
    manifest["recovery_run_at"] = datetime.now().isoformat(timespec="seconds")
    manifest["recovery_call_count"] = recovery_result.get("call_count", 0)
    manifest["recovery_engine_version"] = recovery_result.get(
        "recovery_engine_version", "")
    manifest["recovery_prompt_version"] = recovery_result.get(
        "recovery_prompt_version", "")
    with open(im_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    # 更新 validation_report
    vp = os.path.join(d, "validation_report.json")
    if os.path.isfile(vp):
        with open(vp, "r", encoding="utf-8") as f:
            vrep = json.load(f)
    else:
        vrep = {"paper_id": paper_id}
    all_acc = _load("methods_accepted.json")
    all_cand = _load("methods_candidate.json")
    all_rej = _load("methods_rejected.json")
    vrep["n_accepted"] = len(all_acc)
    vrep["n_candidate"] = len(all_cand)
    vrep["n_rejected"] = len(all_rej)
    vrep["recovery_used"] = True
    vrep["recovery_at"] = manifest["recovery_run_at"]
    with open(vp, "w", encoding="utf-8") as f:
        json.dump(vrep, f, ensure_ascii=False, indent=2)

    # 追加 run_log
    log_path = os.path.join(d, "run_log.json")
    if os.path.isfile(log_path):
        with open(log_path, "r", encoding="utf-8") as f:
            log = json.load(f)
    else:
        log = {"paper_id": paper_id}
    recs = log.setdefault("recoveries", [])
    recs.append({
        "at_iso": manifest["recovery_run_at"],
        "recovery_engine_version": manifest["recovery_engine_version"],
        "recovery_prompt_version": manifest["recovery_prompt_version"],
        "call_count": manifest["recovery_call_count"],
        "n_own_raw": len(recovery_result.get("own_methods_raw", [])),
        "n_accepted_added": len(recovery_result.get("methods_accepted", [])),
        "n_candidate_added": len(recovery_result.get("methods_candidate", [])),
        "n_rejected_added": len(recovery_result.get("methods_rejected", [])),
    })
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)

    return {"n_accepted": len(all_acc),
            "n_candidate": len(all_cand),
            "n_rejected": len(all_rej)}


def apply_stage_a_postprocessing(classified: list) -> tuple:
    """spec 二 + 六 + 七: 在 dedup 之后对每条 method 施加:

      1) name_normalization: raw_method_name / normalized_method_name /
         source_organization; 若拆出机构且 kind=referenced, 重算 external_stub_id.
      2) bare_generic 降级: accepted → candidate (若名字为孤立通用工艺, 无对象).
      3) method_role 分类.

    Returns:
      (new_methods, demoted_count)
    """
    for m in classified:
        nn.attach_name_normalization(m)
        mrole.attach_method_role(m)
        if (m.get("kind") == "referenced"
                and m.get("source_organization")):
            org = m["source_organization"]
            normalized = m.get("normalized_method_name", "")
            base = f"org::{org}::name::{normalized}"
            m["external_stub_id"] = "extstub_" + hashlib.sha1(
                base.encode("utf-8")).hexdigest()[:16]
    classified, demoted = nn.demote_bare_generic_methods(classified)
    return classified, demoted


def per_paper_dir(paper_id: str,
                    base_dir: str = None) -> str:
    base_dir = base_dir or config.STAGE_A_FULL_V1_PER_PAPER_DIR
    return os.path.join(base_dir, paper_id_to_dir_name(paper_id))


def per_paper_input_manifest_path(paper_id: str, base_dir: str = None) -> str:
    return os.path.join(per_paper_dir(paper_id, base_dir), "input_manifest.json")


def load_previous_input_manifest(paper_id: str, base_dir: str = None) -> dict | None:
    p = per_paper_input_manifest_path(paper_id, base_dir)
    if not os.path.isfile(p):
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def should_skip(paper_id: str, current_manifest: dict,
                 base_dir: str = None) -> tuple:
    """向后兼容 (v1 二档): 只用于旧代码路径 / 单测.

    新代码请用 decide_run_action.

    Returns:
      (skip: bool, reason: str) — skip=True 仅当 skip 档
    """
    action, reason = decide_run_action(paper_id, current_manifest, base_dir)
    return (action == "skip"), reason


def decide_run_action(paper_id: str, current_manifest: dict,
                       base_dir: str = None) -> tuple:
    """3-way resume 决策 (spec 一).

    Returns:
      (action, reason) — action ∈ {'skip', 'revalidate', 'run_api'}
        - 'skip': 输入与验证器版本都一致, 直接用上次结果
        - 'revalidate': API 层未变, 但验证器版本变了 → 复用 raw_response.json 本地重跑
        - 'run_api': 需要真的 API 调用
    """
    prev = load_previous_input_manifest(paper_id, base_dir)
    if prev is None:
        return "run_api", "no_previous_run"
    d = per_paper_dir(paper_id, base_dir)
    if not os.path.isfile(os.path.join(d, "validation_report.json")):
        return "run_api", "previous_run_incomplete"
    # raw_response.json 必须存在, 否则无法本地重校验
    raw_p = os.path.join(d, "raw_response.json")
    if not os.path.isfile(raw_p):
        return "run_api", "raw_response_missing"

    # spec 一: 之前是 429 失败 → 强制重跑 (不视为完成)
    try:
        with open(raw_p, "r", encoding="utf-8") as f:
            _raw = json.load(f)
        if not _raw.get("json_parse_ok"):
            err_txt = (_raw.get("json_parse_error") or "").lower()
            if "429" in err_txt or "rate_limit" in err_txt:
                return "run_api", "prior_call_rate_limited"
    except (json.JSONDecodeError, OSError):
        return "run_api", "raw_response_unreadable"

    # 1. API 层版本任一变化 → 必须重跑
    for k in API_HASH_KEYS:
        if prev.get(k) != current_manifest.get(k):
            return "run_api", f"api_hash_change:{k}"

    # 2. 验证器层任一变化 → 只本地重校验, 不烧钱
    for k in VALIDATOR_KEYS:
        if prev.get(k) != current_manifest.get(k):
            return "revalidate", f"validator_version_change:{k}"

    return "skip", "input_hash_matches_previous_success"


# ============================================================
# 单篇执行
# ============================================================

@dataclass
class RunSpec:
    paper_id: str
    canonical_title: str = ""
    paper_type: str = "unclear"
    primary_storage_domain: str = ""
    technology_subfield: str = ""
    application_contexts: list = field(default_factory=list)
    paper_context_status: str = ""


def run_one_paper(spec: RunSpec,
                    full_md_path: str,
                    llm_caller,
                    model: str = DEFAULT_MODEL,
                    base_dir: str = None,
                    write_output: bool = True,
                    allow_retry: bool = True) -> dict:
    """跑一篇 Stage A 抽取, 附着 provenance, 分桶落盘.

    Args:
      spec: RunSpec — 论文元信息
      full_md_path: 原文 md 路径
      llm_caller: callable(system, user, model) → (parsed_dict, ok, err, usage, raw)
                 允许注入用于测试的 mock caller
      write_output: True 时落 per_paper/<hash>/ 各 JSON;
                    False 用于 dry-run / 单测
      allow_retry: JSON 失败允许 1 次重试
    Returns: 完整结果 dict (含 methods_accepted/candidate/rejected 等)
    """
    t0 = time.time()
    base_dir = base_dir or config.STAGE_A_FULL_V1_PER_PAPER_DIR

    # 1. 章节解析
    pr = sp.parse_file(spec.paper_id, full_md_path)
    sections_json = {"sections": []}
    for s in pr.sections:
        sections_json["sections"].append({
            "section_index": s.section_index,
            "section_type": s.section_type,
            "raw_heading": s.raw_heading,
            "char_start": s.char_start,
            "char_end": s.char_end,
            "paragraphs": [{
                "para_id": p.para_id, "text": p.text,
                "char_start": p.char_start, "char_end": p.char_end,
            } for p in s.paragraphs],
        })

    # 2. Stage A 抽取 (LLM 通过 llm_caller 注入)
    # v1.1: 用 v2 validator + v2 provenance (spec 一 要求)
    from method_evolution_v2.stage_a import prompts as prompts_mod
    from method_evolution_v2.stage_a import evidence_validation as ev1   # for dedupe helper
    from method_evolution_v2.stage_a.method_extraction import (
        build_sentence_index_for_llm, parse_llm_json, _make_method_id,
    )

    sentence_index, pack_text, all_kept_sents = build_sentence_index_for_llm(
        sections_json, spec.paper_id)

    apps_repr = json.dumps(list(spec.application_contexts)
                            if spec.application_contexts else [],
                            ensure_ascii=False)
    user_prompt = prompts_mod.USER_PROMPT_TEMPLATE.format(
        paper_type=(spec.paper_type or "unclear"),
        primary_storage_domain=(spec.primary_storage_domain or "(空)"),
        technology_subfield=(spec.technology_subfield or "(空)"),
        application_contexts=apps_repr,
        sentence_pack=pack_text,
    )
    sys_prompt = prompts_mod.SYSTEM_PROMPT

    llm_calls = []
    usage_total = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    call_count = 0

    call_count += 1
    obj, ok, err, usage, raw = llm_caller(sys_prompt, user_prompt, model=model)
    llm_calls.append({"attempt": "primary", "ok": ok, "error": err, "usage": usage})
    _accum_usage(usage_total, usage)
    text_used = raw if ok else ""
    if not ok:
        parse_ok, parse_err = False, err
    else:
        parse_ok = True
        parse_err = ""

    # 若解析失败(caller 返回 obj={} + ok=False), retry once
    if not parse_ok and allow_retry:
        call_count += 1
        obj, ok, err, usage, raw = llm_caller(
            sys_prompt,
            user_prompt + "\n\n注意: 只输出 JSON 对象, 不要 markdown 围栏.",
            model=model,
        )
        llm_calls.append({"attempt": "retry", "ok": ok, "error": err,
                          "usage": usage})
        _accum_usage(usage_total, usage)
        text_used = raw if ok else text_used
        parse_ok, parse_err = (ok, err) if not ok else (True, "")

    own_raw = obj.get("own_methods") if isinstance(obj, dict) else None
    ref_raw = obj.get("referenced_methods") if isinstance(obj, dict) else None
    own_raw = own_raw if isinstance(own_raw, list) else []
    ref_raw = ref_raw if isinstance(ref_raw, list) else []

    # 3. classify + 附着 provenance (v1.1: 用 v2 resolver + v2 provenance)
    classified = []
    for idx, m in enumerate(own_raw):
        if not isinstance(m, dict):
            continue
        c = ev2.resolve_method_by_sentence_ids_v2(m, sentence_index,
                                                    kind="own",
                                                    paper_type=spec.paper_type)
        c["paper_id"] = spec.paper_id
        c["method_id"] = _make_method_id(spec.paper_id, "own", idx,
                                           c.get("name") or "unnamed")
        c = pv2.attach_provenance_v2(c, spec.paper_id, spec.paper_type)
        classified.append(c)
    for idx, m in enumerate(ref_raw):
        if not isinstance(m, dict):
            continue
        c = ev2.resolve_method_by_sentence_ids_v2(m, sentence_index,
                                                    kind="referenced",
                                                    paper_type=spec.paper_type)
        c["paper_id"] = spec.paper_id
        c["method_id"] = _make_method_id(spec.paper_id, "referenced", idx,
                                           c.get("name") or "unnamed")
        c = pv2.attach_provenance_v2(c, spec.paper_id, spec.paper_type)
        classified.append(c)

    classified = ev1.dedupe_methods_prefer_longer_evidence(classified)

    # 4. spec 二 + 六 + 七 post-processing
    classified, demoted_count = apply_stage_a_postprocessing(classified)

    duration = time.time() - t0

    # 5. 分桶
    accepted = [x for x in classified if x["validation_status"] == "accepted"]
    candidate = [x for x in classified if x["validation_status"] == "candidate"]
    rejected = [x for x in classified if x["validation_status"] == "rejected"]

    result = {
        "paper_id": spec.paper_id,
        "canonical_title": spec.canonical_title,
        "paper_type": spec.paper_type,
        "primary_storage_domain": spec.primary_storage_domain,
        "technology_subfield": spec.technology_subfield,
        "paper_context_status": spec.paper_context_status,
        "call_count": call_count,
        "json_parse_ok": parse_ok,
        "json_parse_error": parse_err,
        "llm_calls": llm_calls,
        "usage_total": usage_total,
        "duration_sec": round(duration, 3),
        "sentence_pack_chars": len(pack_text),
        "sentence_count": len(sentence_index),
        "methods_accepted": accepted,
        "methods_candidate": candidate,
        "methods_rejected": rejected,
        "own_methods_raw": own_raw,
        "referenced_methods_raw": ref_raw,
        "raw_llm_text_last": (text_used or "")[:16000],
        "storage_scope": _derive_storage_scope(spec.paper_context_status),
        "stage_a_full_version": STAGE_A_FULL_VERSION,
        "demoted_bare_generic_count": demoted_count,
    }

    # 5. 写盘
    if write_output:
        d = per_paper_dir(spec.paper_id, base_dir)
        os.makedirs(d, exist_ok=True)
        # input_manifest
        manifest = build_input_manifest(spec.paper_id, full_md_path, model)
        with open(os.path.join(d, "input_manifest.json"),
                    "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
        # sentence_index
        with open(os.path.join(d, "sentence_index.json"),
                    "w", encoding="utf-8") as f:
            json.dump({
                "paper_id": spec.paper_id,
                "sentence_count": len(all_kept_sents),
                "sentences": [(s.to_dict() if hasattr(s, "to_dict")
                                 else s) for s in all_kept_sents],
            }, f, ensure_ascii=False, indent=2)
        # raw_response
        with open(os.path.join(d, "raw_response.json"),
                    "w", encoding="utf-8") as f:
            json.dump({
                "own_methods_raw": own_raw,
                "referenced_methods_raw": ref_raw,
                "raw_llm_text_last": text_used[:16000],
                "json_parse_ok": parse_ok,
                "json_parse_error": parse_err,
                "llm_calls": llm_calls,
                "usage_total": usage_total,
            }, f, ensure_ascii=False, indent=2)
        # methods 分桶
        for bucket_name, rows in (("accepted", accepted),
                                    ("candidate", candidate),
                                    ("rejected", rejected)):
            with open(os.path.join(d, f"methods_{bucket_name}.json"),
                        "w", encoding="utf-8") as f:
                json.dump(rows, f, ensure_ascii=False, indent=2)
        # validation_report
        with open(os.path.join(d, "validation_report.json"),
                    "w", encoding="utf-8") as f:
            json.dump({
                "paper_id": spec.paper_id,
                "n_accepted": len(accepted),
                "n_candidate": len(candidate),
                "n_rejected": len(rejected),
                "json_parse_ok": parse_ok,
                "call_count": call_count,
                "usage_total": usage_total,
                "duration_sec": result["duration_sec"],
                "storage_scope": result["storage_scope"],
            }, f, ensure_ascii=False, indent=2)
        # run_log
        with open(os.path.join(d, "run_log.json"),
                    "w", encoding="utf-8") as f:
            json.dump({
                "paper_id": spec.paper_id,
                "run_at_iso": datetime.now().isoformat(timespec="seconds"),
                "call_count": call_count,
                "duration_sec": result["duration_sec"],
                "sentence_pack_chars": len(pack_text),
                "sentence_count": len(sentence_index),
                "usage_total": usage_total,
                "storage_scope": result["storage_scope"],
                "n_accepted": len(accepted),
                "n_candidate": len(candidate),
                "n_rejected": len(rejected),
            }, f, ensure_ascii=False, indent=2)

    return result


def revalidate_one_paper(spec: RunSpec,
                          base_dir: str = None) -> dict:
    """本地重校验一篇论文 (spec 一, 无 API 调用).

    - **只读** raw_response.json 与 sentence_index.json (batch 1 raw 不被覆盖)
    - 用 v2 resolver + v2 provenance 重新分级
    - **覆盖** methods_{accepted,candidate,rejected}.json + validation_report.json
    - **更新** input_manifest.json 里的验证器版本 (SHA/prompt/model 保持原样)
    - **追加** run_log.json 里的 revalidations 事件

    Raises:
      FileNotFoundError: 若 raw_response.json 或 sentence_index.json 缺失
    """
    base_dir = base_dir or config.STAGE_A_FULL_V1_PER_PAPER_DIR
    d = per_paper_dir(spec.paper_id, base_dir)
    raw_path = os.path.join(d, "raw_response.json")
    sidx_path = os.path.join(d, "sentence_index.json")
    im_path = os.path.join(d, "input_manifest.json")
    for p in (raw_path, sidx_path, im_path):
        if not os.path.isfile(p):
            raise FileNotFoundError(f"revalidate: missing {p}")

    t0 = time.time()

    with open(raw_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    with open(sidx_path, "r", encoding="utf-8") as f:
        sidx_data = json.load(f)
    with open(im_path, "r", encoding="utf-8") as f:
        old_manifest = json.load(f)

    sentence_index = {s["sentence_id"]: s
                        for s in sidx_data.get("sentences", [])}
    own_raw = raw.get("own_methods_raw") or []
    ref_raw = raw.get("referenced_methods_raw") or []

    from method_evolution_v2.stage_a.method_extraction import _make_method_id
    from method_evolution_v2.stage_a import evidence_validation as ev1

    classified = []
    for idx, m in enumerate(own_raw):
        if not isinstance(m, dict):
            continue
        c = ev2.resolve_method_by_sentence_ids_v2(m, sentence_index,
                                                    kind="own",
                                                    paper_type=spec.paper_type)
        c["paper_id"] = spec.paper_id
        c["method_id"] = _make_method_id(spec.paper_id, "own", idx,
                                           c.get("name") or "unnamed")
        c = pv2.attach_provenance_v2(c, spec.paper_id, spec.paper_type)
        classified.append(c)
    for idx, m in enumerate(ref_raw):
        if not isinstance(m, dict):
            continue
        c = ev2.resolve_method_by_sentence_ids_v2(m, sentence_index,
                                                    kind="referenced",
                                                    paper_type=spec.paper_type)
        c["paper_id"] = spec.paper_id
        c["method_id"] = _make_method_id(spec.paper_id, "referenced", idx,
                                           c.get("name") or "unnamed")
        c = pv2.attach_provenance_v2(c, spec.paper_id, spec.paper_type)
        classified.append(c)

    classified = ev1.dedupe_methods_prefer_longer_evidence(classified)
    classified, demoted_count = apply_stage_a_postprocessing(classified)
    duration = time.time() - t0

    accepted = [x for x in classified if x["validation_status"] == "accepted"]
    candidate = [x for x in classified if x["validation_status"] == "candidate"]
    rejected = [x for x in classified if x["validation_status"] == "rejected"]

    # 更新 input_manifest: 保留原 SHA/prompt/model, 只覆盖验证器版本
    new_manifest = dict(old_manifest)
    new_manifest["evidence_validation_version"] = ev2.EVIDENCE_VALIDATION_VERSION
    new_manifest["provenance_version"] = pv2.PROVENANCE_VERSION
    new_manifest["method_role_version"] = mrole.METHOD_ROLE_VERSION
    new_manifest["name_normalization_version"] = nn.NAME_NORM_VERSION
    new_manifest["stage_a_full_version"] = STAGE_A_FULL_VERSION
    new_manifest["last_revalidated_at"] = datetime.now().isoformat(timespec="seconds")
    with open(im_path, "w", encoding="utf-8") as f:
        json.dump(new_manifest, f, ensure_ascii=False, indent=2)

    # 覆写 methods 分桶
    for bucket_name, rows in (("accepted", accepted),
                                ("candidate", candidate),
                                ("rejected", rejected)):
        with open(os.path.join(d, f"methods_{bucket_name}.json"),
                    "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)

    # 覆写 validation_report
    with open(os.path.join(d, "validation_report.json"),
                "w", encoding="utf-8") as f:
        json.dump({
            "paper_id": spec.paper_id,
            "n_accepted": len(accepted),
            "n_candidate": len(candidate),
            "n_rejected": len(rejected),
            "revalidated_at": new_manifest["last_revalidated_at"],
            "evidence_validation_version": ev2.EVIDENCE_VALIDATION_VERSION,
            "provenance_version": pv2.PROVENANCE_VERSION,
            "duration_sec_local_revalidate": round(duration, 3),
            "storage_scope": _derive_storage_scope(spec.paper_context_status),
        }, f, ensure_ascii=False, indent=2)

    # 追加 run_log: revalidation 事件
    log_path = os.path.join(d, "run_log.json")
    if os.path.isfile(log_path):
        with open(log_path, "r", encoding="utf-8") as f:
            log = json.load(f)
    else:
        log = {"paper_id": spec.paper_id}
    revents = log.setdefault("revalidations", [])
    revents.append({
        "at_iso": new_manifest["last_revalidated_at"],
        "evidence_validation_version": ev2.EVIDENCE_VALIDATION_VERSION,
        "provenance_version": pv2.PROVENANCE_VERSION,
        "n_accepted": len(accepted),
        "n_candidate": len(candidate),
        "n_rejected": len(rejected),
        "duration_sec": round(duration, 3),
    })
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)

    return {
        "paper_id": spec.paper_id,
        "canonical_title": spec.canonical_title,
        "paper_type": spec.paper_type,
        "action": "revalidated_no_api",
        "call_count": 0,
        "usage_total": {"prompt_tokens": 0, "completion_tokens": 0,
                          "total_tokens": 0},
        "duration_sec": round(duration, 3),
        "methods_accepted": accepted,
        "methods_candidate": candidate,
        "methods_rejected": rejected,
        "demoted_bare_generic_count": demoted_count,
        "stage_a_full_version": STAGE_A_FULL_VERSION,
    }


def _accum_usage(agg: dict, u: dict) -> None:
    for k in ("prompt_tokens", "completion_tokens", "total_tokens"):
        agg[k] = agg.get(k, 0) + int(u.get(k, 0) or 0)


def _derive_storage_scope(paper_context_status: str) -> str:
    """spec 三: 337 篇按 taxonomy 结果分桶 (main / uncertain / non_storage)."""
    s = (paper_context_status or "").strip().lower()
    if s == "confirmed":
        return "main_storage"
    if s == "non_storage":
        return "non_storage"
    # candidate / unknown / empty
    return "uncertain"


# ============================================================
# batches / bookkeeping
# ============================================================

def compute_batches(paper_ids: list, batch_size: int = DEFAULT_BATCH_SIZE) -> list:
    """按 paper_id 排序后切 batch. 保证批次划分**确定**."""
    sorted_ids = sorted(paper_ids)
    return [sorted_ids[i:i + batch_size]
            for i in range(0, len(sorted_ids), batch_size)]


def write_batches_csv(paper_ids: list, batch_size: int, path: str) -> None:
    batches = compute_batches(paper_ids, batch_size)
    rows = []
    for bi, batch in enumerate(batches, 1):
        for pos, pid in enumerate(batch, 1):
            rows.append({
                "paper_id": pid,
                "batch_num": bi,
                "position_in_batch": pos,
                "paper_id_hash": paper_id_to_dir_name(pid),
            })
    _write_csv(path, ["paper_id", "batch_num", "position_in_batch",
                        "paper_id_hash"], rows)


def write_paper_id_map(paper_ids: list, path: str) -> None:
    rows = [{"paper_id": pid,
             "paper_id_hash": paper_id_to_dir_name(pid)}
            for pid in sorted(paper_ids)]
    _write_csv(path, ["paper_id", "paper_id_hash"], rows)


def append_cost_ledger(row: dict, path: str) -> None:
    """追加一行到 cost_ledger.csv, 自动写表头."""
    fields = ["timestamp", "paper_id", "call_count",
              "prompt_tokens", "completion_tokens", "total_tokens",
              "estimated_cost_cny", "model"]
    new_file = not os.path.isfile(path)
    with open(path, "a", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if new_file:
            w.writeheader()
        w.writerow({k: row.get(k, "") for k in fields})


def append_failed(paper_id: str, batch_num: int,
                    error_type: str, error_message: str, path: str) -> None:
    fields = ["paper_id", "batch_num", "attempted_at", "error_type", "error_message"]
    new_file = not os.path.isfile(path)
    with open(path, "a", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if new_file:
            w.writeheader()
        w.writerow({
            "paper_id": paper_id, "batch_num": batch_num,
            "attempted_at": datetime.now().isoformat(timespec="seconds"),
            "error_type": error_type,
            "error_message": (error_message or "")[:2000],
        })


def append_skipped(paper_id: str, batch_num: int, reason: str,
                     path: str) -> None:
    fields = ["paper_id", "batch_num", "skipped_at", "reason"]
    new_file = not os.path.isfile(path)
    with open(path, "a", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if new_file:
            w.writeheader()
        w.writerow({
            "paper_id": paper_id, "batch_num": batch_num,
            "skipped_at": datetime.now().isoformat(timespec="seconds"),
            "reason": reason,
        })


def _write_csv(path, fields, rows):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in fields})
