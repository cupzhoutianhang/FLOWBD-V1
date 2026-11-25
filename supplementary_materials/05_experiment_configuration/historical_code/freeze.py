import re, json, os, sys, hashlib
sys.stdout.reconfigure(encoding="utf-8")
OUT = r"D:\个人工作\邀稿\FlowBD系统\outputs\governance_comparison_20261106"
draft = open(os.path.join(OUT, "题集草案_v2_50题.md"), encoding="utf-8").read()

CASE = {"P": "PCM_复合相变材料", "H": "HYD_热催化加氢", "R": "AORFB_水系有机液流", "E": "对照"}
DIM = {"A": "关系性质", "B": "关系方向", "C": "对象与条件", "D": "范围与边界", "E": "对照"}

rows = []
for m in re.finditer(r"\*\*((?:P|H|R)-[A-E]\d+|E\d+)\*\*〔([^〕]*)〕(?:题目：)?(.+)", draft):
    qid, tag, qtext = m.group(1), m.group(2).strip(), m.group(3).strip()
    c = qid[0] if qid[0] in "PHR" else "E"
    d = re.match(r"(?:P|H|R)-([A-E])", qid)
    dim = d.group(1) if d else "E"
    rows.append({"no": qid, "case": CASE[c], "dimension": DIM[dim],
                 "tier_tag": tag, "question": qtext})

assert len(rows) == 50, f"expected 50, got {len(rows)}"
fq = os.path.join(OUT, "questions_governance.jsonl")
with open(fq, "w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print(f"冻结题集 questions_governance.jsonl: {len(rows)} 题 (仅题面+元数据, 无评分要点/标准答案)")

# freeze manifest: sha256 of frozen artifacts
def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()[:16] if os.path.isfile(p) else "MISSING"
FROZEN = ["questions_governance.jsonl", "题集草案_v2_50题.md", "评分规则_scoring_rules.md",
          "evidence_map.csv", "semantic_review_14edges.csv", "需补核证据清单.csv",
          "注入示例_injection_examples.txt"]
CODE = [r"..\..\src\agent\tiered_governance.py", r"run_governance_experiment.py"]
man = {"frozen_at": __import__("time").strftime("%Y-%m-%d %H:%M:%S"),
       "question_count": len(rows),
       "artifacts": {p: sha(os.path.join(OUT, p)) for p in FROZEN},
       "code": {p: sha(os.path.join(OUT, p)) for p in CODE},
       "evidence_data": {
         "final_case": sha(r"D:\个人工作\邀稿\FlowBD系统\paper\method_evolution_v2\article_minimal_results\final_case\final_storage_case_edges.csv"),
         "confirmed_v2": sha(r"D:\个人工作\邀稿\FlowBD系统\paper\method_evolution_v2\article_minimal_results\lineage_mvp\lineage_edges_confirmed_v2.csv"),
       },
       "note": "冻结快照; 题面不含评分要点/标准答案; 评分要点在 评分规则_scoring_rules.md 与草案, 不进模型输入。"}
json.dump(man, open(os.path.join(OUT, "FREEZE_manifest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("写入 FREEZE_manifest.json (含 sha256 指纹)")
