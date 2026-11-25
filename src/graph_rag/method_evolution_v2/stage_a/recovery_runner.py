"""Stage A recovery runner (spec 二 + 五).

对首轮 Stage A 完成但 accepted own = 0 的 research 论文, 用 recovery prompt
再抽一次. 每篇最多一次, 不循环重试.

设计原则:
  - 输出到独立目录 (STAGE_A_RECOVERY_TEST_V1_PER_PAPER_DIR), 不覆盖原有 raw / methods
  - 复用 v2 evidence_validation + v2 provenance (name-fallback)
  - 额外 post-processing:
      * 附加 method_role (5-way 分类)
      * 附加 raw_method_name / normalized_method_name / source_organization
      * 孤立通用方法名 accepted → candidate
  - 不写 v1 目录, 不改任何 batch 1/2 产物
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import time
from datetime import datetime

from method_evolution_v2 import config
from method_evolution_v2.io import section_parser as sp
from method_evolution_v2.stage_a import method_extraction as me
from method_evolution_v2.stage_a import evidence_validation_v2 as ev2
from method_evolution_v2.stage_a import evidence_validation as ev1
from method_evolution_v2.stage_a import provenance_v2 as pv2
from method_evolution_v2.stage_a import prompts_recovery as prompts_rec
from method_evolution_v2.stage_a import method_role as mrole
from method_evolution_v2.stage_a import name_normalization as nn
from method_evolution_v2.stage_a import full_runner as fr


RECOVERY_ENGINE_VERSION = "recovery_v1.0_2026-07-02"


def find_recovery_candidates(paper_types: dict,
                                batches_csv: str,
                                per_paper_base_dir: str,
                                allowed_batches=("1", "2")) -> list:
    """从指定 batch 里筛出 research_article + accepted_own_count=0.

    Returns:
      List of paper_id (sorted by discovery order = batch order).
    """
    ids_in_scope = []
    with open(batches_csv, "r", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r["batch_num"] in allowed_batches:
                ids_in_scope.append(r["paper_id"])

    candidates = []
    for pid in ids_in_scope:
        if paper_types.get(pid, "") != "research_article":
            continue
        d = fr.per_paper_dir(pid, per_paper_base_dir)
        acc_p = os.path.join(d, "methods_accepted.json")
        if not os.path.isfile(acc_p):
            continue
        with open(acc_p, "r", encoding="utf-8") as f:
            acc = json.load(f)
        has_own = any(m.get("kind") == "own" for m in acc)
        if not has_own:
            candidates.append(pid)
    return candidates


def recovery_per_paper_dir(paper_id: str, base_dir: str = None) -> str:
    base_dir = base_dir or config.STAGE_A_RECOVERY_TEST_V1_PER_PAPER_DIR
    return os.path.join(base_dir, fr.paper_id_to_dir_name(paper_id))


def apply_post_processing(classified: list) -> tuple:
    """给已 classified 的方法加 method_role / name_normalization / 通用名降级.

    Returns:
      (new_methods, demoted_count) — new_methods 里保留全部条目, 只有状态可能变;
      demoted_count 是被 accepted → candidate 的条数.
    """
    for m in classified:
        nn.attach_name_normalization(m)   # raw/normalized/org
        mrole.attach_method_role(m)        # method_role
        # 若能拆出机构, external_stub_id 需基于规范名重算
        if (m.get("kind") == "referenced"
                and m.get("source_organization")):
            org = m["source_organization"]
            normalized = m.get("normalized_method_name", "")
            # 稳定 hash: org + normalized_name
            base = f"org::{org}::name::{normalized}"
            m["external_stub_id"] = "extstub_" + hashlib.sha1(
                base.encode("utf-8")).hexdigest()[:16]

    classified, demoted = nn.demote_bare_generic_methods(classified)
    return classified, demoted


def run_recovery_one_paper(spec: fr.RunSpec,
                              full_md_path: str,
                              llm_caller,
                              model: str = fr.DEFAULT_MODEL,
                              recovery_base_dir: str = None,
                              write_output: bool = True,
                              allow_retry: bool = False) -> dict:
    """跑单篇 recovery 抽取, 使用 recovery prompt + v2 validator.

    与主 run_one_paper 的区别:
      - 用 prompts_recovery.SYSTEM_PROMPT / USER_PROMPT_TEMPLATE
      - referenced_methods 一律不接受 (recovery 只关心 own)
      - 输出目录独立
      - allow_retry 默认 False (spec: 每篇最多一次)
      - 额外附加 method_role / raw_method_name / normalized_method_name / source_organization
      - 孤立通用方法名 accepted → candidate
    """
    t0 = time.time()
    recovery_base_dir = (recovery_base_dir
                            or config.STAGE_A_RECOVERY_TEST_V1_PER_PAPER_DIR)

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

    from method_evolution_v2.stage_a.method_extraction import (
        build_sentence_index_for_llm, _make_method_id,
    )
    sentence_index, pack_text, all_kept_sents = build_sentence_index_for_llm(
        sections_json, spec.paper_id)

    apps_repr = json.dumps(list(spec.application_contexts)
                            if spec.application_contexts else [],
                            ensure_ascii=False)
    user_prompt = prompts_rec.USER_PROMPT_TEMPLATE.format(
        paper_type=(spec.paper_type or "unclear"),
        primary_storage_domain=(spec.primary_storage_domain or "(空)"),
        technology_subfield=(spec.technology_subfield or "(空)"),
        application_contexts=apps_repr,
        sentence_pack=pack_text,
    )
    sys_prompt = prompts_rec.SYSTEM_PROMPT

    llm_calls = []
    usage_total = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    call_count = 0

    call_count += 1
    obj, ok, err, usage, raw = llm_caller(sys_prompt, user_prompt, model=model)
    llm_calls.append({"attempt": "recovery", "ok": ok, "error": err,
                        "usage": usage})
    _accum_usage(usage_total, usage)
    text_used = raw if ok else ""
    parse_ok, parse_err = (True, "") if ok else (False, err)

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
    own_raw = own_raw if isinstance(own_raw, list) else []
    # recovery 明确: referenced 不用, 忽略
    ref_raw = []

    # 2. classify + provenance
    classified = []
    for idx, m in enumerate(own_raw):
        if not isinstance(m, dict):
            continue
        c = ev2.resolve_method_by_sentence_ids_v2(m, sentence_index,
                                                    kind="own",
                                                    paper_type=spec.paper_type)
        c["paper_id"] = spec.paper_id
        c["method_id"] = _make_method_id(spec.paper_id, "own_recovery", idx,
                                           c.get("name") or "unnamed")
        c = pv2.attach_provenance_v2(c, spec.paper_id, spec.paper_type)
        c["recovery_source"] = "stage_a_recovery_v1"
        classified.append(c)

    classified = ev1.dedupe_methods_prefer_longer_evidence(classified)

    # 3. 补救专属 post-processing
    classified, demoted_count = apply_post_processing(classified)

    duration = time.time() - t0

    accepted = [x for x in classified if x["validation_status"] == "accepted"]
    candidate = [x for x in classified if x["validation_status"] == "candidate"]
    rejected = [x for x in classified if x["validation_status"] == "rejected"]

    result = {
        "paper_id": spec.paper_id,
        "canonical_title": spec.canonical_title,
        "paper_type": spec.paper_type,
        "primary_storage_domain": spec.primary_storage_domain,
        "technology_subfield": spec.technology_subfield,
        "recovery_engine_version": RECOVERY_ENGINE_VERSION,
        "recovery_prompt_version": prompts_rec.RECOVERY_PROMPT_VERSION,
        "call_count": call_count,
        "json_parse_ok": parse_ok,
        "json_parse_error": parse_err,
        "llm_calls": llm_calls,
        "usage_total": usage_total,
        "duration_sec": round(duration, 3),
        "sentence_pack_chars": len(pack_text),
        "sentence_count": len(sentence_index),
        "n_own_raw": len(own_raw),
        "methods_accepted": accepted,
        "methods_candidate": candidate,
        "methods_rejected": rejected,
        "own_methods_raw": own_raw,
        "raw_llm_text_last": (text_used or "")[:16000],
        "demoted_bare_generic_count": demoted_count,
    }

    if write_output:
        d = recovery_per_paper_dir(spec.paper_id, recovery_base_dir)
        os.makedirs(d, exist_ok=True)

        # recovery manifest (不同名, 避免与 full v1 目录冲突理解)
        manifest = {
            "paper_id": spec.paper_id,
            "canonical_title": spec.canonical_title,
            "paper_type": spec.paper_type,
            "full_md_path": os.path.relpath(full_md_path,
                                               start=config.PROJECT_ROOT)
                if full_md_path.startswith(config.PROJECT_ROOT)
                else full_md_path,
            "full_md_sha256": fr.compute_full_md_sha256(full_md_path),
            "recovery_prompt_version": prompts_rec.RECOVERY_PROMPT_VERSION,
            "recovery_engine_version": RECOVERY_ENGINE_VERSION,
            "evidence_validation_version": ev2.EVIDENCE_VALIDATION_VERSION,
            "provenance_version": pv2.PROVENANCE_VERSION,
            "method_role_version": mrole.METHOD_ROLE_VERSION,
            "name_normalization_version": nn.NAME_NORM_VERSION,
            "section_parser_version": sp.SECTION_PARSER_VERSION,
            "stage_a_engine_version": me.STAGE_A_VERSION,
            "model": model,
            "run_at_iso": datetime.now().isoformat(timespec="seconds"),
        }
        with open(os.path.join(d, "recovery_manifest.json"),
                    "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

        with open(os.path.join(d, "sentence_index.json"),
                    "w", encoding="utf-8") as f:
            json.dump({
                "paper_id": spec.paper_id,
                "sentence_count": len(all_kept_sents),
                "sentences": [(s.to_dict() if hasattr(s, "to_dict") else s)
                                for s in all_kept_sents],
            }, f, ensure_ascii=False, indent=2)

        with open(os.path.join(d, "recovery_raw_response.json"),
                    "w", encoding="utf-8") as f:
            json.dump({
                "own_methods_raw": own_raw,
                "raw_llm_text_last": text_used[:16000],
                "json_parse_ok": parse_ok,
                "json_parse_error": parse_err,
                "llm_calls": llm_calls,
                "usage_total": usage_total,
            }, f, ensure_ascii=False, indent=2)

        for bucket_name, rows in (("accepted", accepted),
                                    ("candidate", candidate),
                                    ("rejected", rejected)):
            with open(os.path.join(d, f"recovery_methods_{bucket_name}.json"),
                        "w", encoding="utf-8") as f:
                json.dump(rows, f, ensure_ascii=False, indent=2)

        with open(os.path.join(d, "recovery_report.json"),
                    "w", encoding="utf-8") as f:
            json.dump({
                "paper_id": spec.paper_id,
                "n_own_raw": len(own_raw),
                "n_accepted": len(accepted),
                "n_candidate": len(candidate),
                "n_rejected": len(rejected),
                "n_demoted_bare_generic": demoted_count,
                "call_count": call_count,
                "usage_total": usage_total,
                "duration_sec": result["duration_sec"],
                "role_distribution": _role_distribution(
                    accepted + candidate + rejected),
            }, f, ensure_ascii=False, indent=2)

    return result


def _role_distribution(methods: list) -> dict:
    dist = {}
    for m in methods:
        role = m.get("method_role", "unclear")
        dist[role] = dist.get(role, 0) + 1
    return dist


def _accum_usage(agg: dict, u: dict) -> None:
    for k in ("prompt_tokens", "completion_tokens", "total_tokens"):
        agg[k] = agg.get(k, 0) + int(u.get(k, 0) or 0)
