import { Streamlit, RenderData } from 'streamlit-component-lib';
import MarkdownIt from 'markdown-it';
import DOMPurify from 'dompurify';
import renderMathInElement from 'katex/contrib/auto-render';
import 'katex/dist/katex.min.css';
import './style.css';
import { workspace, bindWorkspace } from './workspace';
import { atlas } from './atlas';

type Row = Record<string, any>;
const root = document.querySelector<HTMLDivElement>('#root')!;
const md = new MarkdownIt({html:false,linkify:false,breaks:true});
const escape = (value:unknown) => String(value ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]!));
let current:Row = {};
let selectedRef:string|null = null;
let selectedNode:string|null = null;
let selectedEdge:string|null = null;
let paneOpen = true;
let identity = '';
let zoom = 1;
let graphAll=false, graphBranch='', graphClasses=['direct_evolution','baseline_comparison','node_performance_comparison','route_association','candidate_evolution'];
let graphSequence=0;
let graphCandidates=false;
let graphRender=0;
let diagramMountedPayload='';
const height = () => Streamlit.setFrameHeight(Math.max(60,Math.ceil(document.documentElement.getBoundingClientRect().height)));
const markdown = (text:string) => DOMPurify.sanitize(md.render(String(text || '')));
const textRule = md.renderer.rules.text!;
md.renderer.rules.text = (tokens,index,options,env,self) => {
  const rendered=textRule ? textRule(tokens,index,options,env,self) : escape(tokens[index].content);
  return rendered.replace(/\[Ref-(\d+)\]/g,(_match,id)=>`<button class="citation ${id===selectedRef?'selected':''}" data-ref="${id}" aria-label="查看 Ref-${id} 对应来源" aria-pressed="${id===selectedRef}">[${id}]</button>`);
};
function frame(title:string,tools:string,body:string) {
  return `<section class="surface"><header class="toolbar"><span>${escape(title)}</span><div>${tools}</div></header>${body}</section>`;
}
function payloadRow(value:unknown):Row {
  if(value===null||typeof value!=='object'||Array.isArray(value))throw new Error('Bad message format: payload must be an object');
  const row={...value as Row};
  for(const key of ['sources','nodes','edges','classes'])if(row[key]!=null&&!Array.isArray(row[key]))row[key]=[];
  row.answer=String(row.answer??'');
  row.question=String(row.question??'');
  return row;
}
function renderFailure(error:unknown) {
  const message=error instanceof Error?error.message:String(error||'未知页面数据错误');
  root.innerHTML=frame('页面数据异常','',`<div role="alert" class="diagram-error"><strong>无法显示这条消息</strong><p>${escape(message)}</p><p class="note">失败记录已保留；请展开“完整记录与原文”核对原始诊断。</p></div>`);
  height();
}
function sources():Row[] {return current.sources || [];}
function inspector() {
  const source=sources().find(s=>String(s.ref_id)===selectedRef);
  if(!source)return '<h3>对应原文</h3><p class="note">该引用未保存对应来源。请结合原始记录核对，不将其他文献作为替代证据。</p>';
  const quote=String(source.content || '');
  const recorded=String(source.evidence_quote || source.quote || '');
  let body=escape(quote);
  if(recorded && quote.includes(recorded))body=body.replace(escape(recorded),`<mark>${escape(recorded)}</mark>`);
  return `<div class="inspector-heading"><h3>对应原文 <span>[${escape(source.ref_id)}]</span></h3><span class="source-kind">${escape(source.type || '已保存来源')}</span></div><h4>${escape(source.title)}</h4><p class="note">${escape(source.location_label)}</p><div class="original">${body || '该记录未保存来源正文。'}</div><p class="note">显示完整已保存片段；旧历史可能已经截断。原文可定位不表示结论已审定。</p><details><summary>查看原始来源记录</summary><pre>${escape(JSON.stringify(source,null,2))}</pre></details>`;
}
function reader() {
  const cited=[...String(current.answer || '').matchAll(/\[Ref-(\d+)\]/g)].map(m=>m[1]);
  if(selectedRef===null)selectedRef=cited.find(id=>sources().some(s=>String(s.ref_id)===id)) || (sources()[0]?.ref_id!=null?String(sources()[0].ref_id):null);
  const tools=`<button data-action="sources">检索来源（${sources().length}）</button><button data-action="pane" aria-expanded="${paneOpen}">${paneOpen?'收起原文':'显示原文'}</button>`;
  root.innerHTML=frame(current.context || '研究回答',tools,`<div class="reading ${paneOpen?'':'pane-hidden'}"><article class="answer"><p class="question-label">研究问题</p><h2>${escape(current.question)}</h2><div class="markdown">${markdown(current.answer)}</div></article><aside class="inspector" aria-label="对应原文">${inspector()}</aside></div><dialog aria-label="全部检索来源"><div class="dialog-heading"><h2>检索来源</h2><button data-action="close" aria-label="关闭来源列表">关闭</button></div><p class="note">完整保留 ${sources().length} 条来源；召回记录不自动构成回答证据。</p>${sources().map(s=>`<details><summary>[${escape(s.ref_id??'未记录')}] ${escape(s.title)}</summary><div class="original">${escape(s.content)}</div><button data-select="${escape(s.ref_id)}">对照这条来源</button></details>`).join('')}</dialog>`);
  math();
}
function math() {
  renderMathInElement(root,{delimiters:[{left:'$$',right:'$$',display:true},{left:'$',right:'$',display:false},{left:'\\(',right:'\\)',display:false},{left:'\\[',right:'\\]',display:true}],throwOnError:false,trust:false,ignoredTags:['script','noscript','style','textarea','pre','code','option']});
}
function fields(row:Row,keys:[string,string][]) {
  return `<dl>${keys.filter(([key])=>row[key]!=null&&row[key]!=='').map(([key,label])=>`<dt>${label}</dt><dd>${escape(typeof row[key]==='object'?JSON.stringify(row[key]):row[key])}</dd>`).join('')}</dl>`;
}
async function lineage() {
  const generation=++graphRender;
  const signature=JSON.stringify(current);
  // Streamlit resends equal render args after iframe-height updates. Retain the
  // live viewer in that case: recreating srcdoc would discard playback/focus
  // and alternate between the loading height and the full diagram height.
  if(!graphCandidates&&diagramMountedPayload===signature&&root.querySelector('.lineage-diagram-frame')){height();return;}
  if(graphCandidates){lineageCandidates();root.insertAdjacentHTML('afterbegin','<div class="lineage-mode"><button data-action="graph-main">返回主图讲解</button><span>全部候选 · 保留原有筛选与证据浏览</span></div>');return;}
  root.innerHTML='<div class="lineage-mode"><span>主图讲解</span><button data-action="graph-candidates">浏览全部候选与筛选</button></div><div class="lineage-viewer"></div>';
  try {
    if(current.diagram_layout_error)throw new Error(current.diagram_layout_error);
    const {mountDiagram}=await import('./diagram');
    if(generation!==graphRender||graphCandidates)return;
    mountDiagram(root.querySelector<HTMLElement>('.lineage-viewer')!,current);
    diagramMountedPayload=signature;
    // Lazy loading can finish after Streamlit accepted the short loading height.
    // Explicitly publish the mounted document's height instead of depending on
    // a ResizeObserver notification that may be coalesced during iframe resize.
    height();
    requestAnimationFrame(height);
  } catch(error) {
    if(generation!==graphRender)return;
    lineageCandidates();
    root.insertAdjacentHTML('afterbegin',`<p class="diagram-error" role="alert">交互图暂不可用：${escape(error instanceof Error?error.message:error)}。下方保留原谱系浏览；原论文主图仍可从页面下载。</p>`);
  }
}
function lineageCandidates() {
  const nodes:Row[]=(current.nodes || []).filter((n:Row)=>(graphAll||String(n.main_figure).toLowerCase()==='true')&&(!graphBranch||(n.branch_name||n.branch_id)===graphBranch)&&!['excluded','rejected'].includes(n.verification_status));
  const ids=new Set(nodes.map(n=>n.node_id));
  const edges:Row[]=(current.edges || []).filter((edge:Row)=>(graphAll||String(edge.main_figure).toLowerCase()==='true')&&graphClasses.includes(edge.relation_class)&&ids.has(edge.source_id)&&ids.has(edge.target_id)&&!['excluded','rejected'].includes(edge.verification_status));
  const branches=[...new Set(nodes.map(n=>String(n.branch_name || n.branch_id || n.branch || '未分支')))];
  const years=[...new Set(nodes.map(n=>Number(n.year)).filter(y=>Number.isInteger(y)&&y>0))].sort((a,b)=>a-b);
  const start=years[0] || 0, end=years[years.length-1] || 1;
  const W=Math.max(1060,years.length*145+200), H=Math.max(420,branches.length*130+120);
  const positions=new Map<string,[number,number]>();const occupied=new Map<string,number>();
  for(const n of nodes){
    const branch=String(n.branch_name || n.branch_id || n.branch || '未分支');
    const yr=Number(n.year);const x=Number.isInteger(yr)&&yr>0?155+years.indexOf(yr)/Math.max(1,years.length-1)*(W-320):W-120;
    const k=branch+':'+yr;const slot=occupied.get(k)||0;occupied.set(k,slot+1);
    positions.set(String(n.node_id),[x,135+branches.indexOf(branch)*130+slot*34]);
  }
  const graph=`<svg role="group" aria-label="方法谱系，点击节点或关系查看原始证据" viewBox="0 0 ${W} ${H}" style="width:${W*zoom}px;height:${H*zoom}px"><defs><marker id="arrow" markerWidth="9" markerHeight="9" refX="8" refY="4" orient="auto"><path d="M1 1L8 4L1 7" fill="none" stroke="currentColor"/></marker></defs>${years.map((y,index)=>{const x=155+index/Math.max(1,years.length-1)*(W-320);return `<text x="${x}" y="35" class="year" text-anchor="middle">${y}</text><path d="M${x} 55V${H-25}" class="guide"/>`;}).join('')}${nodes.some(n=>!Number(n.year))?`<text x="${W-120}" y="35" class="year">年份未记录</text>`:''}${branches.map((b,i)=>`<text x="20" y="${88+i*130}" class="branch">${escape(b)}</text><path d="M20 ${190+i*130}H${W-20}" class="lane"/>`).join('')}${edges.map(e=>{
    const a=positions.get(String(e.source_id)),b=positions.get(String(e.target_id));if(!a||!b)return '';
    const direct=e.relation_class==='direct_evolution';const dash=direct?'':['route_association','candidate_evolution'].includes(e.relation_class)?'5 5':'8 4 2 4';
    return `<g class="edge ${selectedEdge===e.edge_id?'picked':''}" data-edge="${escape(e.edge_id)}" tabindex="0" role="button" aria-label="${escape(e.display_label || e.relation_type)}，查看关系证据"><path d="M${a[0]+8} ${a[1]}L${b[0]-9} ${b[1]}" stroke-dasharray="${dash}" ${direct?'marker-end="url(#arrow)"':''}/><text x="${(a[0]+b[0])/2}" y="${(a[1]+b[1])/2-14}" text-anchor="middle">${escape(e.display_label || e.relation_type)}</text></g>`;
  }).join('')}${nodes.map(n=>{const [x,y]=positions.get(String(n.node_id))!;const full=String(n.display_name||n.node_name);const label=full.length>16?full.slice(0,15)+'…':full;return `<g class="node ${selectedNode===n.node_id?'picked':''}" data-node="${escape(n.node_id)}" role="button" tabindex="0" aria-label="${escape(full)}，查看详情"><title>${escape(full)}</title><circle cx="${x}" cy="${y}" r="6"/><text x="${x+13}" y="${y+27}">${escape(label)}</text></g>`;}).join('')}</svg>`;
  const selected=nodes.find(n=>n.node_id===selectedNode)||edges.find(e=>e.edge_id===selectedEdge);
  let details='';
  if(selected)details=`<aside class="inspector"><div class="inspector-heading"><h3>${selectedNode?'方法详情':'关系详情'}</h3><button data-action="clear">关闭</button></div><h4>${escape(selected.node_name || selected.display_label || selected.relation_type)}</h4>${fields(selected,[['year_label','年份'],['branch_name','技术分支'],['source_paper','来源论文'],['source_authors','作者'],['verification_status','原始核验状态'],['evidence_level','证据层级'],['source_scope','支持范围'],['relation_class','关系类别'],['edge_scope','关系范围'],['problem_solved','研究问题'],['method_or_material','方法或材料'],['key_performance','性能记录'],['evidence_location','原文位置'],['sentence_id','句子编号']])}<h3>已记录的证据原句</h3><p class="original">${escape(selected.evidence_sentence || '未记录原句')}</p><p class="note">${escape(selected.notes || '')}</p><details><summary>完整原始记录</summary><pre>${escape(JSON.stringify(selected,null,2))}</pre></details></aside>`;
  const allBranches=[...new Set((current.nodes||[]).map((n:Row)=>String(n.branch_name||n.branch_id)))];
  const classLabels:Row={direct_evolution:'直接演化',baseline_comparison:'基线比较',node_performance_comparison:'性能比较',route_association:'路线归类',candidate_evolution:'候选承接（待审核）'};
  root.innerHTML=frame('方法谱系',`<button data-action="zoom-out" aria-label="缩小图谱">−</button><span>${Math.round(zoom*100)}%</span><button data-action="zoom-in" aria-label="放大图谱">＋</button><button data-action="reset">重置视图</button>`,`<div class="graph-layout ${selected?'':'pane-hidden'}"><section class="graph-area"><h2>${escape(current.title)}</h2><p class="note">${nodes.length} 个方法节点 · ${edges.length} 条当前关系 · ${years[0]||'年份未记录'}—${years[years.length-1]||'年份未记录'}</p><div class="graph-controls"><label>技术分支 <select data-graph="branch" aria-label="技术分支"><option value="">全部</option>${allBranches.map(b=>`<option value="${escape(b)}" ${b===graphBranch?'selected':''}>${escape(b)}</option>`).join('')}</select></label><label><input type="checkbox" data-graph="all" ${graphAll?'checked':''}> 显示全部候选</label><details class="relation-filter"><summary>关系类型</summary>${Object.entries(classLabels).map(([key,label])=>`<label><input type="checkbox" data-graph="class" value="${key}" ${graphClasses.includes(key)?'checked':''}> ${label}</label>`).join('')}</details></div><div class="graph-scroll" tabindex="0">${nodes.length?graph:'<p class="empty">当前筛选没有匹配节点，请切换分支或显示全部候选。</p>'}</div><p class="note">实线：直接演化；点划线：比较；虚线：路线归类。年份按列排列，间距不表示时间跨度。原文可定位不等于 confirmed。</p></section>${details}</div>`);
}
root.addEventListener('click',event=>{
  const t=(event.target as Element).closest<HTMLElement>('button,[data-node],[data-edge]');if(!t)return;
  if(t.dataset.ref || t.dataset.select){selectedRef=t.dataset.ref || t.dataset.select || null;paneOpen=true;reader();root.querySelector<HTMLButtonElement>(`.citation[data-ref="${selectedRef}"]`)?.focus({preventScroll:true});}
  else if(t.dataset.node){selectedNode=t.dataset.node;selectedEdge=null;lineage();}
  else if(t.dataset.edge){selectedEdge=t.dataset.edge;selectedNode=null;lineage();}
  else switch(t.dataset.action){
    case 'graph-candidates':graphCandidates=true;graphAll=true;lineage();break;
    case 'graph-main':graphCandidates=false;lineage();break;
    case 'pane':paneOpen=!paneOpen;reader();break;
    case 'sources':root.querySelector('dialog')?.showModal();break;
    case 'close':root.querySelector('dialog')?.close();break;
    case 'clear':selectedNode=selectedEdge=null;lineage();break;
    case 'zoom-in':zoom=Math.min(2,zoom+.15);lineage();break;
    case 'zoom-out':zoom=Math.max(.6,zoom-.15);lineage();break;
    case 'reset':zoom=1;selectedNode=selectedEdge=null;lineage();break;
  }
  height();
});
root.addEventListener('keydown',event=>{if((event.key==='Enter'||event.key===' ')&&(event.target as Element).matches('[data-node],[data-edge]')){event.preventDefault();(event.target as HTMLElement).dispatchEvent(new MouseEvent('click',{bubbles:true}));}});
root.addEventListener('change',event=>{
  const field=event.target as HTMLInputElement;
  if(!field.dataset.graph)return;
  if(field.dataset.graph==='branch')graphBranch=field.value;
  if(field.dataset.graph==='all')graphAll=field.checked;
  if(field.dataset.graph==='class')graphClasses=field.checked?[...graphClasses,field.value]:graphClasses.filter(c=>c!==field.value);
  selectedNode=selectedEdge=null;lineage();height();
  Streamlit.setComponentValue({identity:current.identity,action:'state',sequence:++graphSequence,view:{all:graphAll,branch:graphBranch,classes:graphClasses}});
});
let drag:{x:number,y:number,left:number,top:number,el:HTMLElement}|null=null;
root.addEventListener('mousedown',event=>{const el=(event.target as Element).closest<HTMLElement>('.graph-scroll');if(el&&!(event.target as Element).closest('.node,.edge'))drag={x:event.clientX,y:event.clientY,left:el.scrollLeft,top:el.scrollTop,el};});
window.addEventListener('mousemove',event=>{if(drag){drag.el.scrollLeft=drag.left+drag.x-event.clientX;drag.el.scrollTop=drag.top+drag.y-event.clientY;}});
window.addEventListener('mouseup',()=>{drag=null;});
Streamlit.events.addEventListener(Streamlit.RENDER_EVENT,(event:Event)=>{
  try {
    const data=(event as CustomEvent<RenderData>).detail;
    const args=(data as any)?.args;
    if(!args||typeof args!=='object')throw new Error('Bad message format: render args are missing');
    current=payloadRow(args.payload);
    graphRender++;
    const next=String(current.identity || '');if(next!==identity){identity=next;selectedRef=selectedNode=selectedEdge=null;paneOpen=true;zoom=1;graphCandidates=false;graphAll=!!current.view?.all;graphBranch=current.view?.branch||'';graphClasses=current.view?.classes||['direct_evolution','baseline_comparison','node_performance_comparison','route_association','candidate_evolution'];}
    if(args.mode==='reader')reader();
    else if(args.mode==='lineage')lineage();
    else if(args.mode==='atlas')atlas(root,current);
    else workspace(args.mode,current,root,(value)=>Streamlit.setComponentValue(value));
    height();
  } catch(error) {
    renderFailure(error);
  }
});
new ResizeObserver(height).observe(root);
window.addEventListener('message',event=>{
  const frame=root.querySelector<HTMLIFrameElement>('.lineage-diagram-frame');
  if(!frame||event.source!==frame.contentWindow||event.data?.identity!==current.identity)return;
  if(event.data.type==='flowbd-diagram-present'){
    frame.style.height=event.data.present?`${Math.max(760,screen.availHeight-80)}px`:'940px';
    height();
  }
});
bindWorkspace(root);
Streamlit.setComponentReady();
