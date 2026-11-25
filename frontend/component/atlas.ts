type Row = Record<string, any>;
const esc=(v:unknown)=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]!));
const colors=['#2463a1','#267566','#81579b','#a15a25','#4f7282','#8e5064','#626833','#5265a0','#75634c'];
const color=(n:Row)=>n.cluster_id>=0?colors[n.cluster_id%colors.length]:'#74747b';
let cleanup=()=>{};
let mountedPayload='';
export function atlas(root:HTMLElement,payload:Row) {
  const signature=JSON.stringify(payload);
  if(mountedPayload===signature&&root.querySelector('.atlas-canvas'))return;
  cleanup();
  mountedPayload=signature;
  const nodes:Row[]=payload.nodes||[],edges:Row[]=payload.edges||[];
  let selected:string|null=null,query='',onlyCandidates=false,cluster='',scale=1,offsetX=0,offsetY=0;
  const W=1100,H=650,pad=55;
  const finite=nodes.filter(n=>Number.isFinite(n.x)&&Number.isFinite(n.y));
  const xs=finite.map(n=>n.x),ys=finite.map(n=>n.y),xmin=Math.min(...xs),xmax=Math.max(...xs),ymin=Math.min(...ys),ymax=Math.max(...ys);
  const coords=new Map(finite.map(n=>[n.id,[pad+(n.x-xmin)/Math.max(1,xmax-xmin)*(W-2*pad),pad+(n.y-ymin)/Math.max(1,ymax-ymin)*(H-2*pad)]]));
  const clusters=[...new Set(nodes.map(n=>Number(n.cluster_id??-1)))].sort((a,b)=>a-b);
  root.innerHTML=`<section class="surface atlas-surface"><header class="toolbar"><span>全局方法版图 · ${esc(payload.version)}</span><div><button data-atlas-action="out" aria-label="缩小版图">缩小</button><button data-atlas-action="in" aria-label="放大版图">放大</button><button data-atlas-action="reset">适应画布</button></div></header><div class="atlas-controls"><label>查找方法或论文<input data-atlas="search" type="search" placeholder="输入名称后回车" aria-label="查找方法或论文"></label><label>语义分组<select data-atlas="cluster"><option value="">全部分组</option>${clusters.map(c=>`<option value="${c}">${c<0?'外围 / 未聚类':'语义分组 '+c}</option>`).join('')}</select></label><label class="atlas-candidate-filter"><input data-atlas="candidate" type="checkbox">只看新增候选</label></div><p class="note atlas-caption" aria-live="polite"></p><div class="atlas-layout"><div><canvas class="atlas-canvas" width="${W}" height="${H}" tabindex="0" role="img" aria-label="全局方法语义散点图，可拖动平移、滚轮缩放；下方方法列表可键盘选择"></canvas><p class="note atlas-caption">空心方点：新增候选；圆点：历史方法记录。颜色表示当前语义分组；相似位置不表示继承关系。</p><details class="atlas-methods"><summary>用列表选择方法</summary><div class="atlas-list"></div></details></div><aside class="inspector atlas-inspector" aria-label="方法与候选关系详情"><h3>查看方法记录</h3><p class="note">点击散点或从列表选择方法，查看原始来源、审核状态和已记录关系。</p></aside></div></section>`;
  const canvas=root.querySelector<HTMLCanvasElement>('canvas')!,context=canvas.getContext('2d')!;
  const inspector=root.querySelector<HTMLElement>('.atlas-inspector')!;
  const visible=()=>finite.filter(n=>(!onlyCandidates||n.candidate)&&(!cluster||String(n.cluster_id??-1)===cluster)&&(!query||`${n.name} ${n.paper_id}`.toLowerCase().includes(query.toLowerCase())));
  function details() {
    const n=nodes.find(n=>n.id===selected);if(!n)return;
    const rels=edges.filter(e=>e.source===selected||e.target===selected);
    const methodName=(id:string)=>nodes.find(row=>row.id===id)?.name||id;
    inspector.innerHTML=`<h3>${n.candidate?'自动候选方法':'历史方法记录'}</h3><h4>${esc(n.name)}</h4><dl><dt>来源论文</dt><dd>${esc(n.paper_id)}</dd><dt>方法身份</dt><dd>${n.kind==='own'?'本文方法':'引用方法'}</dd><dt>年份记录</dt><dd>${esc(n.year??'未提供')}</dd><dt>审核状态</dt><dd>${n.review_status==='not_recorded'?'未记录审核状态':esc(n.review_status)}</dd><dt>语义分组</dt><dd>${esc(n.cluster_label||'未提供')}</dd></dl><p class="note">${esc(n.innovation||n.problem_solved||n.citation_clue||'未保存补充描述。')}</p>${n.display_annotation?`<p class="note">${esc(n.display_annotation)} · 依据：原PDF第 ${esc(n.display_correction?.pdf_page)} 页。原抽取名称：${esc(n.original_extraction_name)}</p>`:''}<h3>已记录关系 · ${rels.length}</h3>${rels.length?rels.map(e=>`<details><summary>${esc(e.relation)} · ${e.candidate?'自动候选':'历史记录，待核'}</summary><p>${esc(methodName(e.source))} → ${esc(methodName(e.target))}</p><p class="note">${esc(e.direction)}；模型置信度 ${esc(e.confidence_llm||'未提供')}，不等于人工确认。</p><blockquote>${esc(e.evidence||'未记录证据原句')}</blockquote><p>${esc(e.reason)}</p></details>`).join(''):'<p class="note">此记录未保存关系，不补造连接。</p>'}<details><summary>完整方法记录</summary><pre>${esc(JSON.stringify(n,null,2))}</pre></details>`;
  }
  function draw() {
    const rows=visible(),ids=new Set(rows.map(n=>n.id));
    context.clearRect(0,0,W,H);context.fillStyle='#fff';context.fillRect(0,0,W,H);
    context.save();context.translate(W/2+offsetX,H/2+offsetY);context.scale(scale,scale);context.translate(-W/2,-H/2);
    if(selected){context.lineWidth=1/scale;for(const e of edges){
      if((e.source!==selected&&e.target!==selected)||!ids.has(e.source)||!ids.has(e.target))continue;
      const a=coords.get(e.source),b=coords.get(e.target);if(!a||!b)continue;
      context.strokeStyle=e.candidate?'#8a5900':'#89929c';context.setLineDash(e.candidate?[5/scale,4/scale]:[]);
      context.beginPath();context.moveTo(a[0],a[1]);context.lineTo(b[0],b[1]);context.stroke();}}
    context.setLineDash([]);
    for(const n of rows){const p=coords.get(n.id)!;context.fillStyle=color(n);context.strokeStyle=n.id===selected?'#1d1d1f':color(n);context.lineWidth=(n.id===selected?2.4:1.8)/scale;
      const r=(n.id===selected?6:n.candidate?4.8:2.8)/Math.sqrt(scale);
      context.beginPath();if(n.candidate)context.rect(p[0]-r,p[1]-r,2*r,2*r);else context.arc(p[0],p[1],r,0,Math.PI*2);
      if(n.candidate)context.stroke();else context.fill();
      if(n.id===selected){context.stroke();context.font=`${13/scale}px sans-serif`;context.fillStyle='#1d1d1f';context.fillText(String(n.name).slice(0,32),p[0]+10/scale,p[1]-12/scale);}}
    context.restore();root.querySelector('.atlas-caption')!.textContent=`当前显示 ${rows.length} / ${nodes.length} 条方法记录；新增候选 ${rows.filter(n=>n.candidate).length} 条。审核状态与语义分组分别保留。`;
    root.querySelector('.atlas-list')!.innerHTML=rows.slice(0,100).map(n=>`<button data-atlas-node="${esc(n.id)}" aria-pressed="${selected===n.id}">${esc(n.name)}${n.candidate?' · 候选':''}</button>`).join('')+(rows.length>100?'<p class="note">列表显示前100条，请用名称缩小范围。</p>':'');
  }
  const select=(id:string)=>{selected=id;details();draw();};
  const click=(event:Event)=>{const t=(event.target as Element).closest<HTMLElement>('[data-atlas-action],[data-atlas-node]');if(!t)return;
    if(t.dataset.atlasNode){select(t.dataset.atlasNode);return;}
    if(t.dataset.atlasAction==='in')scale=Math.min(8,scale*1.3);if(t.dataset.atlasAction==='out')scale=Math.max(.5,scale/1.3);
    if(t.dataset.atlasAction==='reset'){scale=1;offsetX=offsetY=0;}draw();};
  const change=(event:Event)=>{const t=event.target as HTMLInputElement;if(!t.dataset.atlas)return;
    if(t.dataset.atlas==='search')query=t.value;if(t.dataset.atlas==='cluster')cluster=t.value;if(t.dataset.atlas==='candidate')onlyCandidates=t.checked;draw();};
  let drag:{x:number;y:number;ox:number;oy:number;moved:boolean}|null=null;
  const point=(e:PointerEvent)=>{const r=canvas.getBoundingClientRect();return [(e.clientX-r.left)*W/r.width,(e.clientY-r.top)*H/r.height];};
  canvas.onpointerdown=e=>{const p=point(e);drag={x:p[0],y:p[1],ox:offsetX,oy:offsetY,moved:false};canvas.setPointerCapture(e.pointerId);};
  canvas.onpointermove=e=>{if(!drag)return;const p=point(e);if(Math.abs(p[0]-drag.x)+Math.abs(p[1]-drag.y)>4)drag.moved=true;offsetX=drag.ox+p[0]-drag.x;offsetY=drag.oy+p[1]-drag.y;draw();};
  canvas.onpointerup=e=>{if(!drag)return;if(!drag.moved){const p=point(e);let best:Row|undefined,bestDist=14;for(const n of visible()){const c=coords.get(n.id)!;const d=Math.hypot((c[0]-W/2)*scale+W/2+offsetX-p[0],(c[1]-H/2)*scale+H/2+offsetY-p[1]);if(d<bestDist){best=n;bestDist=d;}}if(best)select(best.id);}drag=null;};
  canvas.onpointercancel=()=>{drag=null;};
  const wheel=(e:WheelEvent)=>{e.preventDefault();scale=Math.max(.5,Math.min(8,scale*(e.deltaY<0?1.12:1/1.12)));draw();};
  canvas.addEventListener('wheel',wheel,{passive:false});root.addEventListener('click',click);root.addEventListener('change',change);
  cleanup=()=>{root.removeEventListener('click',click);root.removeEventListener('change',change);canvas.removeEventListener('wheel',wheel);};draw();
}
