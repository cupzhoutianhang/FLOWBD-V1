# -*- coding: utf-8 -*-
"""
尾段 6 题 governed 补跑（R-D3, R-D4, E1, E2, E3, E4）
——因正式跑批尾段 Milvus 于 2026-11-06 23:23:35 停止，这 6 题向量通道不可用（vector 8/5/0/0/0/1）。

严格约束（遵用户指令）：
  - 题目/证据/代码路径/模型参数全部沿用冻结版，**temperature 不改（=1.0）**，补跑不做任何配置优化。
  - 复用冻结 run_governance_experiment.py 的同一引导、同一 tiered_governance 注入、同一 fuse 包裹(rerank=0.99)。
  - **开跑前已确认** Milvus 健康 + 集合 Loaded 100%（见脚本外健康检查）。
  - **每题记录检索状态**；若该题 run_status!=ok 或 vector==0（无检索证据）→ **立即暂停**，不接受该回答、不继续后续题。
  - 每题采用**第一次通过健康检查的完整结果**，不按回答质量挑选（通过即收，不通过即停）。
  - 另存独立文件，**不覆盖** governed_answers.jsonl / retrieval_evidence/；保留原始失败运行与诊断记录。
  - 不打印/不写入密钥。
"""
import os, sys, json, time, traceback, re

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

PROJECT_ROOT = r"D:\个人工作\邀稿\FlowBD系统"
APP_DIR = os.path.join(PROJECT_ROOT, "src", "KnowledgeGraph-Streamlit-main")
OUT_DIR = os.path.join(PROJECT_ROOT, "outputs", "governance_comparison_20261106")
PATCH_EVID = os.path.join(OUT_DIR, "retrieval_evidence_patch")   # 独立目录，不覆盖原始
os.makedirs(PATCH_EVID, exist_ok=True)
ANS_PATCH = os.path.join(OUT_DIR, "governed_answers_patch_tail.jsonl")
STATUS_LOG = os.path.join(OUT_DIR, "logs", "patch_tail_retrieval_status.json")

TAIL_QIDS = ["R-D3", "R-D4", "E1", "E2", "E3", "E4"]   # 仅尾段 6 题
GROUP = "governed"

os.chdir(PROJECT_ROOT)
for p in (APP_DIR, os.path.join(PROJECT_ROOT, "src"), os.path.join(PROJECT_ROOT, "src", "agent")):
    if p not in sys.path:
        sys.path.insert(0, p)

# ---------- 开跑前健康门（强制） ----------
def health_gate():
    from pymilvus import connections, utility, Collection
    connections.connect(alias="hc", host="localhost", port=19530)
    st = str(utility.load_state("CHUneng", using="hc"))
    pg = utility.loading_progress("CHUneng", using="hc")
    ok = (st == "Loaded") and (str(pg.get("loading_progress")).replace("%", "") == "100")
    print(f"[health] load_state={st} progress={pg} -> {'OK' if ok else 'FAIL'}", flush=True)
    return ok, {"load_state": st, "loading_progress": pg}

ok, hc = health_gate()
if not ok:
    print("[FATAL] 集合未就绪，终止补跑（不生成无检索证据的回答）", flush=True)
    sys.exit(3)

# ---------- 复用冻结引导（与正式跑批同一代码路径） ----------
print(f"🔧 [patch] 加载 app.py 引导 ...", flush=True)
app_py = os.path.join(APP_DIR, "app.py")
_src = open(app_py, encoding="utf-8").read()
_boot = _src[:_src.rfind("\n", 0, _src.index("st.set_page_config")) + 1]
_ns = {"__name__": "__app_boot__", "__file__": app_py}
exec(compile(_boot, app_py, "exec"), _ns)
MultiTurnConversation = _ns["MultiTurnConversation"]

import importlib
_tg = importlib.import_module("agent.tiered_governance")

# ---------- 题集（冻结 questions_governance.jsonl，题面不变） ----------
qrows = [json.loads(l) for l in open(os.path.join(OUT_DIR, "questions_governance.jsonl"), encoding="utf-8") if l.strip()]
qmap = {r["no"]: r for r in qrows}
qrows = [qmap[no] for no in TAIL_QIDS]   # 保持 TAIL 顺序

print(f"📋 [patch] 补跑题目: {[r['no'] for r in qrows]}", flush=True)
conv = MultiTurnConversation()
print("✅ [patch] 后端就绪\n", flush=True)

def _src_titles(doc_sources):
    out = []
    for s in (doc_sources or []):
        if isinstance(s, dict):
            t = (s.get("title") or s.get("source") or s.get("doc_name") or s.get("name") or
                 s.get("file") or s.get("paper") or "")
            out.append(str(t))
        else:
            out.append(str(s))
    return [t for t in out if t]

def _vec_count(es):
    for s in (es or []):
        m = re.match(r"vector\((\d+)\)", str(s))
        if m: return int(m.group(1))
    return None

# ---------- 治理注入（与冻结 runner 完全一致） ----------
_CURRENT_GOV = []
from agent.part5_multiagent_integration import InformationFusionAgent as _IFA
_orig_fuse = _IFA.fuse
def _patched_fuse(self, state):
    if _CURRENT_GOV and isinstance(getattr(state, "vector_chunks", None), list):
        already = {c.get("doc_id") for c in state.vector_chunks}
        for c in _CURRENT_GOV:
            if c["doc_id"] in already:
                continue
            state.vector_chunks.insert(0, {
                "content": c["content"], "source": c["source"], "doc_id": c["doc_id"],
                "parent_id": c["record_id"], "original_filename": c["source"],
                "governance_injected": True, "governance_tier": c["tier"],
                "governance_located": c.get("located"),
                "rerank_score": 0.99, "similarity": 0.99,
            })
    return _orig_fuse(self, state)
_IFA.fuse = _patched_fuse
print("🔧 [patch] 已包裹 fuse 作为治理注入点（与冻结版一致）", flush=True)

# ---------- 逐题补跑（健康门 + 失败即暂停） ----------
# 新文件从空开始；保留原始失败运行(governed_answers.jsonl)与诊断记录不动。
open(ANS_PATCH, "w", encoding="utf-8").close()
status_records = []
paused = False

for i, row in enumerate(qrows, 1):
    no, q = row["no"], row["question"]
    cat = row.get("dimension", row.get("case", ""))
    print(f"\n===== [patch] [{i}/{len(qrows)}] 题{no} · {cat} =====\nQ: {q}", flush=True)

    # 每题前再查一次集合健康（服务异常则暂停）
    hok, hinfo = health_gate()
    if not hok:
        print(f"[PAUSE] 题{no} 开跑前集合不就绪，暂停补跑（不生成无检索证据的回答）", flush=True)
        status_records.append({"no": no, "action": "paused_before_run", "health": hinfo})
        paused = True
        break

    gov = _tg.select(q) or []
    gov_chunks = _tg.to_injection_chunks(gov) if gov else []
    injected_records = [{"record_id": c["record_id"], "tier": c["tier"], "located": c.get("located")} for c in gov_chunks]
    _CURRENT_GOV = gov_chunks
    injected_n = len(gov_chunks)

    t0 = time.time(); final = None; err = None
    try:
        for state in conv.run_conversation(q):
            final = state
    except Exception as e:
        err = f"{type(e).__name__}: {e}"; traceback.print_exc()
    dt = round(time.time() - t0, 1)

    g = lambda a, d=None: getattr(final, a, d) if final else d
    answer = g("final_answer", "") or ""
    ds = g("doc_sources", []) or []
    es = g("evidence_sources", []) or []
    conf = g("answer_confidence", 0.0)
    vec = _vec_count(es)

    # 健康判定：run_status ok 且 向量命中 > 0（有检索证据）
    run_status = "error" if err else "ok"
    passed = (run_status == "ok") and (vec is not None and vec > 0)
    status_records.append({"no": no, "run_status": run_status, "vector_hit": vec,
                           "channels": es, "doc_sources": len(_src_titles(ds)),
                           "governance_injected_count": injected_n, "elapsed_sec": dt,
                           "passed_health": passed, "error": err})

    # 检索证据留档（独立目录，不覆盖原始）
    try:
        json.dump({"no": no, "question": q, "group": GROUP, "doc_sources": ds,
                   "evidence_sources": es, "governance_records": injected_records,
                   "governance_injected_count": injected_n, "vector_hit": vec,
                   "note": "patch_rerun_tail; 故障修复后补跑"},
                  open(os.path.join(PATCH_EVID, f"{GROUP}_q{no}.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
    except Exception:
        pass

    print(f"⏱ {dt}s | vector={vec} | 来源={len(_src_titles(ds))} | 注入={injected_n} | 状态={run_status} | 健康={'通过' if passed else '未通过'}", flush=True)

    if not passed:
        print(f"[PAUSE] 题{no} 未通过健康检查（vector={vec}, status={run_status}）→ 暂停，不接受该回答、不继续后续题", flush=True)
        paused = True
        break

    # 通过：收录（第一次通过即收，不按质量挑选）
    rec = {"group": GROUP, "no": no, "category": cat, "question": q, "answer": answer,
           "source_titles": _src_titles(ds), "evidence_sources": es if isinstance(es, list) else [str(es)],
           "answer_confidence": conf, "governance_injected": (injected_n > 0),
           "governance_injected_count": injected_n, "governance_records": injected_records,
           "run_status": run_status, "error": None, "elapsed_sec": dt, "vector_hit": vec,
           "provenance": "patch_rerun_tail_故障修复后", "rerun_ts": time.strftime("%Y-%m-%d %H:%M:%S")}
    with open(ANS_PATCH, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

# ---------- 收尾 ----------
json.dump({"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "health_precheck": hc,
           "tail_qids": TAIL_QIDS, "paused": paused, "per_question": status_records,
           "note": "故障修复后补跑；每题须通过 vector>0 健康门；失败即暂停"},
          open(STATUS_LOG, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
done = sum(1 for r in status_records if r.get("passed_health"))
print(f"\n===== [patch] 结束：通过 {done}/{len(TAIL_QIDS)} 题 | 暂停={paused} =====")
print(f"回答: {ANS_PATCH}")
print(f"检索状态: {STATUS_LOG}")
print(f"检索留档: {PATCH_EVID}")
