# -*- coding: utf-8 -*-
"""
FlowBD 治理前后两组对照实验 · 运行器 (import_batch: governance_comparison_20261106)

目标 (对齐 CC任务单_治理前后对照实验.md):
  - 同一可运行代码版本 (D 盘 app.py -> MultiTurnConversation, 旧 part5 主流程)。
  - 两组唯一区别: 是否向回答证据上下文注入【已有人工校正关系记录 + 查询范围说明】。
      baseline : 不注入, 不读人工校正谱系, 不走记录直出。
      governed : 在同一基础上, 注入 corpus_evidence.lineage_sources(question)
                 (= 5 条人工校正案例边 + 1 条 ADAPTS confirmed + 范围说明), 保留关系状态/方向/证据/适用范围。
  - 相同模型、参数、检索设置、通用引用/数值/修复检查 (都来自同一 conv, 不改)。
  - 生成路径两组相同 (同一 run_conversation); governed 仅多一段注入的证据上下文, 不走 lineage_answer 直出捷径。
  - 逐题记录治理是否实际触发、注入了哪些记录; 未触发的题保留在结果里, 不宣称 50 题全部受治理。
  - 不把 accepted 改成 confirmed/S2, 不自称 C1, 不编造关系, 不扩大核查范围。

用法 (两组都要跑; 先小批后全量):
  # 小批 3-5 题冒烟 (检查开关隔离 + 治理是否生效 + 输出保存):
  EXP_GROUP=baseline EXP_QIDS=1,3,2,25,44 python outputs/governance_comparison_20261106/run_governance_experiment.py
  EXP_GROUP=governed EXP_QIDS=1,3,2,25,44 python outputs/governance_comparison_20261106/run_governance_experiment.py
  # 全量 50:
  EXP_GROUP=baseline python outputs/governance_comparison_20261106/run_governance_experiment.py
  EXP_GROUP=governed python outputs/governance_comparison_20261106/run_governance_experiment.py

环境变量:
  EXP_GROUP = baseline | governed   (必填)
  EXP_QIDS  = 逗号分隔题号子集 (选填; 缺省=全部 50)
  不读取/不打印任何密钥; 使用 conv 内既有配置。
"""
import os, sys, csv, json, time, traceback

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

PROJECT_ROOT = r"D:\个人工作\邀稿\FlowBD系统"
APP_DIR = os.path.join(PROJECT_ROOT, "src", "KnowledgeGraph-Streamlit-main")
OUT_DIR = os.path.join(PROJECT_ROOT, "outputs", "governance_comparison_20261106")
LOG_DIR = os.path.join(OUT_DIR, "logs")
EVID_DIR = os.path.join(OUT_DIR, "retrieval_evidence")

GROUP = os.environ.get("EXP_GROUP", "").strip().lower()
if GROUP not in ("baseline", "governed"):
    print("[FATAL] 请设置 EXP_GROUP=baseline 或 governed"); sys.exit(2)
QIDS = [x.strip() for x in os.environ.get("EXP_QIDS", "").split(",") if x.strip()]

os.chdir(PROJECT_ROOT)
for p in (APP_DIR, os.path.join(PROJECT_ROOT, "src"), os.path.join(PROJECT_ROOT, "src", "agent")):
    if p not in sys.path:
        sys.path.insert(0, p)

# ---------- 1. 复用 app.py 引导段(与 run_eval.py 完全一致, 保证两组同一代码路径) ----------
print(f"🔧 [{GROUP}] 加载 app.py 引导补丁并初始化后端 ...", flush=True)
app_py = os.path.join(APP_DIR, "app.py")
with open(app_py, encoding="utf-8") as f:
    _src = f.read()
_idx = _src.index("st.set_page_config")
_line_start = _src.rfind("\n", 0, _idx) + 1
_boot = _src[:_line_start]
_ns = {"__name__": "__app_boot__", "__file__": app_py}
exec(compile(_boot, app_py, "exec"), _ns)
MultiTurnConversation = _ns["MultiTurnConversation"]

# ---------- 2. 分层治理证据注入 (仅 governed 组启用) ----------
# 使用分层选择器 tiered_governance.select: 返回 T1 人工校正 / T2 语料内 / T3 综述可定位 证据,
# 每条带真实核查状态与范围标签; struct_only(仅字段) 作为线索标注, 不作确定事实。
import importlib
_tg = importlib.import_module("agent.tiered_governance")

def governance_evidence(question):
    """返回本题分层治理证据 (list[dict]); baseline 永远返回 []。"""
    if GROUP != "governed":
        return []
    try:
        return _tg.select(question) or []
    except Exception as exc:
        print(f"[warn] tiered_governance.select 失败: {type(exc).__name__}: {exc}", flush=True)
        return []

# ---------- 3. 题集 (冻结的 questions_governance.jsonl) ----------
qpath = os.path.join(OUT_DIR, "questions_governance.jsonl")
qrows = [json.loads(l) for l in open(qpath, encoding="utf-8") if l.strip()]
if QIDS:
    qrows = [r for r in qrows if r["no"] in QIDS]
    # 保持 EXP_QIDS 给定顺序
    order = {q: i for i, q in enumerate(QIDS)}
    qrows.sort(key=lambda r: order.get(r["no"], 999))
print(f"📋 [{GROUP}] 本次题目: {len(qrows)} 道", flush=True)

print(f"🚀 [{GROUP}] 初始化 MultiTurnConversation ...", flush=True)
conv = MultiTurnConversation()
print(f"✅ [{GROUP}] 后端就绪\n", flush=True)


def _src_titles(doc_sources):
    out = []
    for s in (doc_sources or []):
        if isinstance(s, dict):
            t = (s.get("title") or s.get("source") or s.get("doc_name")
                 or s.get("name") or s.get("file") or s.get("paper") or "")
            out.append(str(t))
        else:
            out.append(str(s))
    return [t for t in out if t]


# ---------- 4. 逐题运行 ----------
# 正式结果与小批结果分开保存:
#   全量 -> OUT_DIR/{group}_answers.jsonl ;  小批(EXP_QIDS) -> logs/{group}_smoke_answers.jsonl
ans_path = os.path.join(OUT_DIR, f"{GROUP}_answers.jsonl")
fail_path = os.path.join(OUT_DIR, f"{GROUP}_failures.jsonl")
if QIDS:
    ans_path = os.path.join(LOG_DIR, f"{GROUP}_smoke_answers.jsonl")
    fail_path = os.path.join(LOG_DIR, f"{GROUP}_smoke_failures.jsonl")

# 断点续跑: 读取已成功(run_status==ok)的题号, 跳过; 不截断已有结果, 仅 append。
done_ok = set()
if os.path.isfile(ans_path):
    kept = []
    for l in open(ans_path, encoding="utf-8"):
        if not l.strip():
            continue
        try:
            r = json.loads(l)
        except Exception:
            continue
        # 同题多行只保留最后一条成功记录; 失败行不计入 done, 允许重跑
        if r.get("run_status") == "ok":
            done_ok.add(r.get("no"))
        kept.append(l)
    # 去重重写: 每个已成功题号只留最后一条, 保证最终唯一
    if kept:
        last_ok = {}
        order = []
        for l in kept:
            try:
                r = json.loads(l)
            except Exception:
                continue
            no = r.get("no")
            if r.get("run_status") == "ok":
                if no not in last_ok:
                    order.append(no)
                last_ok[no] = l
        with open(ans_path, "w", encoding="utf-8") as f:
            for no in order:
                f.write(last_ok[no])
print(f"📝 [{GROUP}] 续跑: 已成功 {len(done_ok)} 题将跳过; 结果文件 {os.path.basename(ans_path)}", flush=True)
open(fail_path, "w", encoding="utf-8").close()  # 失败清单每轮重算

run_t0 = time.time()
total = len(qrows)

# ---------- 治理注入点: 确定性包裹 InformationFusionAgent.fuse ----------
# fuse() 从 state.vector_chunks 构建 fused_context + doc_sources(即模型输入)。
# 在 fuse 起始处把本题治理块预置进 vector_chunks, 保证证据确实进入模型输入(不受生成器时序影响)。
# baseline 组 _CURRENT_GOV 恒为 [], 绝不注入。
_CURRENT_GOV = []
if GROUP == "governed":
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
                    # 治理证据为"刻意供给"的证据(非语料相似度检索竞争), 赋高保留分,
                    # 确保进入 fuse 的 Top-K -> fused_context(模型输入); 与 baseline 唯一差别即此注入。
                    "rerank_score": 0.99, "similarity": 0.99,
                })
        return _orig_fuse(self, state)
    _IFA.fuse = _patched_fuse
    print("🔧 [governed] 已包裹 InformationFusionAgent.fuse 作为治理注入点", flush=True)

for i, row in enumerate(qrows, 1):
    no, cat, q = row["no"], row.get("dimension", row.get("case", "")), row["question"]
    if no in done_ok:
        print(f"[skip] 已成功, 跳过: 题{no}", flush=True)
        continue
    print(f"\n===== [{GROUP}] [{i}/{total}] 题{no} · {cat} =====", flush=True)
    print("Q:", q, flush=True)

    # 分层治理证据 (仅 governed 非空); 设为当前题注入源
    gov = governance_evidence(q)
    gov_chunks = _tg.to_injection_chunks(gov) if gov else []
    injected_records = [{"record_id": c["record_id"], "tier": c["tier"], "located": c.get("located")}
                        for c in gov_chunks]
    _CURRENT_GOV = gov_chunks   # fuse 包裹器读取
    injected_n = len(gov_chunks)

    t0 = time.time()
    final = None
    err = None
    try:
        for state in conv.run_conversation(q):
            final = state
    except Exception as e:
        err = f"{type(e).__name__}: {e}"
        traceback.print_exc()
    dt = time.time() - t0

    def g(attr, default):
        return getattr(final, attr, default) if final else default

    answer = g("final_answer", "") or ""
    ds = g("doc_sources", []) or []
    es = g("evidence_sources", []) or []
    conf = g("answer_confidence", 0.0)

    rec = {
        "group": GROUP, "no": no, "category": cat, "question": q,
        "answer": answer,
        "source_titles": _src_titles(ds),
        "evidence_sources": es if isinstance(es, list) else [str(es)],
        "answer_confidence": conf,
        "governance_injected": (GROUP == "governed" and injected_n > 0),
        "governance_injected_count": injected_n,
        "governance_records": injected_records,   # 注入了什么 + 层级 + 定位状态 (中性记录, 不判断效果)
        "run_status": "error" if err else "ok",
        "error": err,
        "elapsed_sec": round(dt, 1),
    }
    with open(ans_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    # 失败单独记录 (便于只重跑失败题; run_status!=ok 即记入, 不计入 done_ok)
    if rec["run_status"] != "ok":
        with open(fail_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"no": no, "question": q, "error": err}, ensure_ascii=False) + "\n")
    else:
        done_ok.add(no)
    # 检索证据留档 (每题一个)
    try:
        with open(os.path.join(EVID_DIR, f"{GROUP}_q{no}.json"), "w", encoding="utf-8") as f:
            json.dump({"no": no, "question": q, "group": GROUP,
                       "doc_sources": ds, "evidence_sources": es,
                       "governance_records": injected_records,
                       "governance_injected_count": injected_n}, f, ensure_ascii=False, indent=1)
    except Exception:
        pass
    print(f"A(前150字): {answer[:150]}", flush=True)
    _tiers = ",".join(sorted({r["tier"] for r in injected_records})) or "-"
    print(f"⏱ {dt:.0f}s | 来源 {len(rec['source_titles'])} | 注入 {injected_n} 条({_tiers}) "
          f"| 状态 {rec['run_status']}", flush=True)

# ---------- 5. 收尾: 唯一性 + 完整性核对 ----------
ok_nos, dup = [], []
seen = set()
for l in open(ans_path, encoding="utf-8"):
    if not l.strip():
        continue
    r = json.loads(l)
    if r.get("run_status") != "ok":
        continue
    no = r.get("no")
    if no in seen:
        dup.append(no)
    seen.add(no)
    ok_nos.append(no)
all_nos = [row["no"] for row in qrows] if not QIDS else QIDS
missing = [n for n in all_nos if n not in seen]
n_fail = sum(1 for _ in open(fail_path, encoding="utf-8") if _.strip()) if os.path.isfile(fail_path) else 0
print(f"\n===== [{GROUP}] 收尾核对 =====", flush=True)
print(f"  唯一成功题号: {len(seen)} / 目标 {len(all_nos)}", flush=True)
print(f"  重复题号: {sorted(set(dup)) or '无'}", flush=True)
print(f"  未完成题号: {missing or '无'}  (失败清单: {os.path.basename(fail_path)}, {n_fail} 条)", flush=True)
complete = (len(seen) == len(all_nos)) and not dup and not missing
print(f"  结论: {'✅ 本组 ' + str(len(all_nos)) + ' 题唯一且齐全' if complete else '⚠️ 未齐全/有重复, 重跑本命令可断点续跑补齐失败题'}", flush=True)
print(f"✅ [{GROUP}] 结束, 用时 {(time.time()-run_t0)/60:.1f} 分钟 | 回答: {ans_path}", flush=True)
