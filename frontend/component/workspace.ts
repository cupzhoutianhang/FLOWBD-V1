/* Research lists and reports, rendered from Python's read-only view adapters. */
type Row = Record<string, any>;
type Emit = (value:Row)=>void;
let payload:Row = {}, view:Row = {}, mode='', identity='';
let host:HTMLElement, emit:Emit;
let sequence=0, pending:ReturnType<typeof setTimeout>|undefined;
let lastData='';
const e=(v:unknown)=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]!));
const saveView=()=>sessionStorage.setItem('flowbd-view-'+identity,JSON.stringify(view));
const message=(action='state')=>{saveView();emit({identity:payload.identity,action,view:{...view},sequence:++sequence});};
function tableFields(row:Row){return `<pre>${e(JSON.stringify(row,null,2))}</pre>`;}
function library(){
  const all:Row[]=payload.papers||[];
  const query=String(view.query||'').trim().toLocaleLowerCase();
  const filtered=all.filter(p=>(!query||String(p.search).toLocaleLowerCase().includes(query))&&(!view.category||p.category===view.category));
  const pageCount=Math.max(1,Math.ceil(filtered.length/9));view.page=Math.min(Math.max(1,view.page||1),pageCount);
  const visible=filtered.slice((view.page-1)*9,view.page*9);
  if(!visible.some(p=>p.id===view.paper))view.paper=visible[0]?.id||null;
  const selected=visible.find(p=>p.id===view.paper);
  const categories=[...new Set(all.map(p=>p.category))].sort();
  host.innerHTML=`<section class="surface"><header class="toolbar"><span>语料库</span><span>本地文献与方法记录</span></header><div class="reading"><section class="page-column"><h2>语料库</h2><p class="note">${all.length} 篇本地文献 · ${payload.methodCount==null?'方法抽取记录暂不可用':`${payload.methodCount} 条方法抽取记录`}</p><div class="library-controls"><label class="search-field"><span aria-hidden="true">⌕</span><input id="library-search" data-action="lib-search" type="search" aria-label="搜索文献" placeholder="搜索题名或方法…" value="${e(view.query||'')}"></label><select data-action="lib-category" aria-label="研究分类"><option value="">全部分类</option>${categories.map(c=>`<option value="${e(c)}" ${view.category===c?'selected':''}>${e(c)}</option>`).join('')}</select><button data-action="lib-clear">清除</button></div><div class="results-summary"><span>${filtered.length} 篇${query||view.category?'匹配文献':'文献'}</span><span>题名与方法记录可检索</span></div><div class="paper-list">${visible.map(p=>`<button class="paper-row ${p.id===view.paper?'selected':''}" data-action="lib-paper" data-paper="${e(p.id)}" aria-pressed="${p.id===view.paper}"><span class="paper-title">${e(p.title)}</span><span class="paper-meta">${e(p.category)}<i>·</i>${e(p.year||'年份待核对')}${p.has_text?'<i>·</i>本地原文':''}</span><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="m9 5 7 7-7 7"/></svg></button>`).join('')||'<p class="empty">未找到匹配文献，试试其他关键词。</p>'}</div><div class="pagination"><span>第 ${view.page} / ${pageCount} 页</span><div><button data-action="lib-prev" ${view.page===1?'disabled':''}>上一页</button><button data-action="lib-next" ${view.page===pageCount?'disabled':''}>下一页</button></div></div><p class="note">辅助分类按题名关键词整理；方法记录未经全部人工确认。缺失年份不作推断。</p></section><aside class="inspector"><div class="inspector-heading"><h3>文献详情</h3></div>${selected?`<p class="note">${e(selected.category)}${selected.inferred_category?' · 题名辅助分类':''}</p><h4>${e(selected.title)}</h4><p class="note">${e(selected.year||'年份待核对')} · ${selected.has_text?'本地全文可用':'无本地全文'}</p><p class="note">已保存 ${selected.methods.length} 条方法记录</p>${selected.methods[0]?`<h3>方法记录摘录</h3><p class="original">${e(selected.methods[0].problem_solved||selected.methods[0].method_name||'未记录研究问题')}</p>`:''}<button data-action="lib-open" ${!selected.has_text?'disabled':''}>阅读本地原文</button><details><summary>查看完整方法抽取记录</summary>${tableFields(selected.methods)}</details>`:'<p class="note">当前筛选没有可选文献。</p>'}</aside></div></section>`;
}
function report(){
  const all:Row[]=payload.issues||[];
  const rows=all.filter(r=>!view.mode||r.mode===view.mode);
  if(!rows.some(r=>r.attempt===view.issue))view.issue=null;
  const selected=rows.find(r=>r.attempt===view.issue);
  const receipt=payload.receipt;
  host.innerHTML=`<section class="surface"><header class="toolbar"><span>评测报告</span><span>正式候选 27 · 历史执行记录</span></header><div class="reading"><section class="page-column"><h2>评测报告</h2><p class="note">候选 27 · ${e(String(receipt.completed_at||'').slice(0,10))}</p><div class="evaluation-summary"><h3>整体回答质量尚未验收通过</h3><p>共 ${receipt.formal_jobs} 项正式作业，${receipt.successful_jobs} 项成功返回，${receipt.failed_jobs} 项生成失败。<br>成功返回表示执行结果，不代表科学准确率。</p></div><div class="failure-heading"><h3>生成失败记录</h3><label>模式 <select data-action="report-mode" aria-label="模式"><option value="">全部</option>${['Q1','E1','E2'].map(m=>`<option ${view.mode===m?'selected':''}>${m}</option>`).join('')}</select></label></div><p class="note">${rows.length} 条生成失败记录</p><div class="table-scroll"><table class="failure-table"><thead><tr><th>题目</th><th>模式</th><th>阶段</th><th>记录原因</th><th><span class="sr-only">详情</span></th></tr></thead><tbody>${rows.map(r=>`<tr class="${r.attempt===view.issue?'selected':''}"><td>Q${e(r.case_id)}</td><td>${e(r.mode)}</td><td>${e(r.stage)}</td><td><span class="reason" title="${e(r.reason)}">${e(r.reason)}</span></td><td><button data-action="report-issue" data-issue="${e(r.attempt)}">查看</button></td></tr>`).join('')}</tbody></table></div><p class="note">原始失败保留在固定分母中，未因界面改造改写结果或评测结论。</p></section><aside class="inspector"><div class="inspector-heading"><h3>${selected?'失败记录详情':'如何阅读这份记录'}</h3></div>${selected?`<h4>Q${e(selected.case_id)} · ${e(selected.mode)}</h4><p class="original">${e(selected.reason)}</p><p class="note">${e(selected.question)}</p><p class="note">原始批次：${e(selected.run_id)}</p><p class="note">尝试标识：${e(selected.attempt)}</p><button data-action="report-original">查看原始失败记录</button>`:`<section class="evaluation-notes"><h4>成功返回</h4><p>说明结果已生成并返回，不能据此认定科学内容正确。</p><h4>离线回归</h4><p>后续回归属于另一批验证，不与旧正式作业合并计算。</p><h4>仍待核验</h4><p>回答中的主体、条件、单位与因果关系仍需独立复核。严格实验、E1/E2及探索性理论分析仍默认关闭。</p></section>`}</aside></div></section>`;
}
function render(){if(mode==='corpus')library();else report();}
export function workspace(kind:string,args:Row,root:HTMLElement,onEvent:Emit){
  host=root;emit=onEvent;payload=args;mode=kind;
  const fresh=identity!==args.identity;
  if(fresh){identity=args.identity;try{view=JSON.parse(sessionStorage.getItem('flowbd-view-'+identity)||'null')||{...(args.view||{})};}catch{view={...(args.view||{})};}}
  const signature=JSON.stringify({...args,view:undefined});
  if(fresh||signature!==lastData){lastData=signature;render();}
}
export function bindWorkspace(root:HTMLElement){
  root.addEventListener('click',event=>{
    const button=(event.target as Element).closest<HTMLButtonElement>('button[data-action]');if(!button||button.disabled)return;
    const action=button.dataset.action;
    if(action==='lib-paper')view.paper=button.dataset.paper;
    else if(action==='lib-next')view.page++;
    else if(action==='lib-prev')view.page--;
    else if(action==='lib-clear'){view.query='';view.category='';view.page=1;}
    else if(action==='lib-open'){message('open-paper');return;}
    else if(action==='report-issue')view.issue=button.dataset.issue;
    else if(action==='report-original'){message('open-issue');return;}
    else return;
    render();message();
  });
  root.addEventListener('input',event=>{
    const input=event.target as HTMLInputElement;if(input.dataset.action!=='lib-search')return;
    view.query=input.value;view.page=1;const cursor=input.selectionStart;render();
    saveView();
    const field=root.querySelector<HTMLInputElement>('#library-search');field?.focus();
    if(field&&field.type!=='search')field.setSelectionRange(cursor,cursor);
    clearTimeout(pending);pending=setTimeout(()=>message(),250);
  });
  root.addEventListener('change',event=>{
    const select=event.target as HTMLSelectElement;
    if(select.dataset.action==='lib-category'){view.category=select.value;view.page=1;}
    else if(select.dataset.action==='report-mode')view.mode=select.value;
    else return;
    render();message();
  });
}
