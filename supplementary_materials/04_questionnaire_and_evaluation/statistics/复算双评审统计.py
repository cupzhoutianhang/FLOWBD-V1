from pathlib import Path
import csv,json,statistics,sys
sys.stdout.reconfigure(encoding="utf-8")
p=Path(__file__).resolve().parent
rows=list(csv.DictReader((p/"两名评审逐项评分与合并结果.csv").open(encoding="utf-8-sig")))
dims=["正确性","完整性","引用支撑","对象与条件匹配"]
assert len(rows)==len({r["匿名编号"] for r in rows})==100
for r in rows:
 for d in dims:
  assert float(r["平均_"+d])==(float(r["评审1_"+d])+float(r["评审2_"+d]))/2
result={g:{"n":len(rr),"dimensions":{d:statistics.mean(float(r["平均_"+d]) for r in rr) for d in dims},"overall":statistics.mean(float(r["平均_"+d]) for r in rr for d in dims)} for g in ["baseline","governed"] if (rr:=[r for r in rows if r["组别"]==g])}
gaps=[abs(float(r["评审1_"+d])-float(r["评审2_"+d])) for r in rows for d in dims]
result["agreement"]={"exact":sum(v==0 for v in gaps)/400,"within1":sum(v<=1 for v in gaps)/400,"mae":statistics.mean(gaps)}
print(json.dumps(result,ensure_ascii=False,indent=2))
