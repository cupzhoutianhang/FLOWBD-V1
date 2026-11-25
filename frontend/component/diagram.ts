import template from './archify-viewer.template.html?raw';
import bridge from './diagram-viewer.js?raw';
import diagramCSS from './diagram-viewer.css?raw';

type Row = Record<string, any>;
export type DiagramLayout = {
  version: 1;
  kind_labels?: Record<string,string>;
  evidence_caption?: string;
  width: number;
  height: number;
  columns: {label:string; x:number}[];
  groups: {id:string; label:string; x?:number; y:number; width?:number; height:number; subgroups?:{label:string;y:number}[]}[];
  nodes: Record<string,{group:string;x:number;y:number;title?:string;subtitle?:string}>;
  edges?: Record<string,{via?:number[][];label?:string;labelAt?:number[]}>;
  chapters: {id:string;label:string;focus:string[];note:string}[];
};
const esc = (v:unknown) => String(v ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]!));
const json = (v:unknown) => JSON.stringify(v).replace(/</g,'\\u003c').replace(/\u2028/g,'\\u2028').replace(/\u2029/g,'\\u2029');
const yes = (v:unknown) => String(v).toLowerCase()==='true';
const palette:Row = {baseline:'external',track_primary:'frontend',track_secondary:'backend',track_tertiary:'cloud',track_quaternary:'database'};
const relationLabels:Row = {direct_evolution:'直接演化',baseline_comparison:'基线比较',node_performance_comparison:'性能比较',route_association:'路线归类',candidate_evolution:'候选承接（待审核）'};

function automatic(nodes:Row[]):DiagramLayout {
  const groups=[...new Set(nodes.map(n=>String(n.branch_id||'unassigned')))];
  const years=[...new Set(nodes.map(n=>String(n.year_label||'年份未记录')))];
  const occupancy=new Map<string,number>();
  const rowHeights=groups.map(g=>{
    const counts:Row={}; nodes.filter(n=>String(n.branch_id||'unassigned')===g).forEach(n=>counts[n.year_label]=(counts[n.year_label]||0)+1);
    return Math.max(150,Math.max(1,...Object.values(counts).map(Number))*110+55);
  });
  let top=65;
  const lanes=groups.map((g,i)=>{const lane={id:g,label:String(nodes.find(n=>String(n.branch_id||'unassigned')===g)?.branch_name||g),y:top,height:rowHeights[i]};top+=rowHeights[i]+20;return lane;});
  const positions:DiagramLayout['nodes']={};
  nodes.forEach(n=>{const g=String(n.branch_id||'unassigned'),key=g+':'+n.year_label,slot=occupancy.get(key)||0;occupancy.set(key,slot+1);positions[n.node_id]={group:g,x:165+years.indexOf(String(n.year_label||'年份未记录'))*260,y:lanes[groups.indexOf(g)].y+95+slot*110};});
  return {version:1,width:Math.max(1050,years.length*260+70),height:top+140,columns:years.map((label,i)=>({label,x:165+i*260})),groups:lanes,nodes:positions,chapters:lanes.map(g=>({id:g.id,label:g.label,focus:nodes.filter(n=>String(n.branch_id||'unassigned')===g.id).map(n=>String(n.node_id)),note:'同一分支的节点按记录展示；未记录关系的节点保持独立。'}))};
}

export function validateLayout(layout:DiagramLayout,nodes:Row[],edges:Row[]) {
  if(layout.version!==1)throw new Error('布局版本应为 1');
  if(!Number.isFinite(layout.width)||!Number.isFinite(layout.height)||layout.width<500||layout.height<250)throw new Error('画布尺寸无效');
  const ids=new Set(nodes.map(n=>String(n.node_id))),edgeIds=new Set(edges.map(e=>String(e.edge_id)));
  if(ids.size!==nodes.length||edgeIds.size!==edges.length)throw new Error('主图节点或关系 ID 重复');
  const groups=new Set(layout.groups.map(g=>g.id));
  if(groups.size!==layout.groups.length)throw new Error('分区 ID 重复');
  for(const g of layout.groups){const x=g.x??28,w=g.width??layout.width-56;if([x,w,g.y,g.height].some(v=>!Number.isFinite(v))||x<0||w<=0||x+w>layout.width||g.y<0||g.height<=0||g.y+g.height>layout.height-120)throw new Error(`分区 ${g.id} 的坐标或尺寸无效`);}
  for(const col of layout.columns)if(!Number.isFinite(col.x)||col.x<0||col.x>layout.width)throw new Error('年份列坐标无效');
  for(const n of nodes){const p=layout.nodes[n.node_id];if(!p||!groups.has(p.group))throw new Error(`节点 ${n.node_id} 缺少有效分区或位置`);if(!Number.isFinite(p.x)||!Number.isFinite(p.y)||p.x<112||p.x>layout.width-112||p.y<50||p.y>layout.height-130)throw new Error(`节点 ${n.node_id} 超出画布`);}
  for(const id of Object.keys(layout.nodes))if(!ids.has(id))throw new Error(`布局引用未知主图节点 ${id}`);
  for(const id of Object.keys(layout.edges||{}))if(!edgeIds.has(id))throw new Error(`布局引用未知主图关系 ${id}`);
  for(const e of edges)if(!ids.has(String(e.source_id))||!ids.has(String(e.target_id)))throw new Error(`关系 ${e.edge_id} 的端点不在主图`);
  for(const chapter of layout.chapters){if(!chapter.focus.length||chapter.focus.some(id=>!ids.has(id)))throw new Error(`章节 ${chapter.id} 包含未知或空节点`);}
  for(const e of Object.values(layout.edges||{}))for(const p of [...(e.via||[]),...(e.labelAt?[e.labelAt]:[])])if(p.length!==2||p.some(v=>!Number.isFinite(v)))throw new Error('连线路由坐标无效');
}

function lines(value:string,limit:number):string[] {
  const out:string[]=[];let line='',size=0;
  for(const ch of value){const weight=/[\u0020-\u007e]/.test(ch)?.56:1;if(size+weight>limit&&line){out.push(line);line='';size=0;}line+=ch;size+=weight;}
  if(line)out.push(line);return out;
}
function svg(caseData:Row,layout:DiagramLayout,nodes:Row[],edges:Row[]) {
  const W=layout.width,H=layout.height,cardW=204,cardH=88;
  const kind=(n:Row)=>palette[n.node_type]||'neutral';
  const title=caseData.manifest?.title_cn||caseData.title;
  const groupMarkup=layout.groups.map((g,i)=>`<rect data-graph-role="structural-frame" data-composition-frame-kind="lane" data-composition-frame-id="${esc(g.id)}" x="${g.x??28}" y="${g.y}" width="${g.width??W-56}" height="${g.height}" rx="12" class="c-lane" stroke-width="1"/><text x="${(g.x??28)+18}" y="${g.y+25}" class="t-muted" font-size="15" font-weight="600">${String(i+1).padStart(2,'0')} / ${esc(g.label)}</text>${(g.subgroups||[]).map(s=>`<text x="${(g.x??28)+20}" y="${s.y}" class="t-muted" font-size="12">${esc(s.label)}</text>`).join('')}`).join('');
  const columns=layout.columns.map(c=>`<text x="${c.x}" y="32" text-anchor="middle" class="t-muted" font-size="13">${esc(c.label)}</text>`).join('');
  const paths:string[]=[],labels:string[]=[];
  for(const e of edges){
    const a=layout.nodes[e.source_id],b=layout.nodes[e.target_id],cfg=layout.edges?.[e.edge_id]||{};
    const direct=e.relation_class==='direct_evolution',route=['route_association','candidate_evolution'].includes(e.relation_class);
    let points:number[][];
    if(cfg.via?.length){
      const first=cfg.via[0],last=cfg.via[cfg.via.length-1];
      const port=(n:typeof a,t:number[])=>Math.abs(t[0]-n.x)>=Math.abs(t[1]-n.y)?[n.x+Math.sign(t[0]-n.x)*cardW/2,n.y]:[n.x,n.y+Math.sign(t[1]-n.y)*cardH/2];
      points=[port(a,first),...cfg.via,port(b,last)];
    } else if(Math.abs(a.y-b.y)<2){points=[[a.x+cardW/2,a.y],[b.x-cardW/2,b.y]];}
    else if(a.x===b.x){points=[[a.x,a.y+cardH/2],[b.x,b.y-cardH/2]];}
    else {const sx=a.x+cardW/2,tx=b.x-cardW/2,mx=(sx+tx)/2;points=[[sx,a.y],[mx,a.y],[mx,b.y],[tx,b.y]];}
    const label=cfg.label||e.display_label||relationLabels[e.relation_class]||e.relation_type;
    const attrs=`data-edge-from="${esc(e.source_id)}" data-edge-to="${esc(e.target_id)}" data-edge-id="${esc(e.edge_id)}" data-edge-key="${esc(e.edge_id)}" data-edge-label="${esc(label)}" data-relation-class="${esc(e.relation_class)}"`;
    paths.push(`<path ${attrs} data-animate="edge" data-composition-points="${points.map(p=>p.join(',')).join(';')}" d="${points.map((p,i)=>(i?'L':'M')+p.join(' ')).join(' ')}" class="${direct?'a-default':route?'a-dashed':'a-comparison'}" stroke-width="1.7" fill="none" ${direct?'marker-end="url(#arrowhead)"':''}/>`);
    const longest=points.slice(1).map((p,i)=>({a:points[i],b:p,len:Math.abs(p[0]-points[i][0])+Math.abs(p[1]-points[i][1])})).sort((a,b)=>b.len-a.len)[0];
    const [x,y]=cfg.labelAt||[(longest.a[0]+longest.b[0])/2,(longest.a[1]+longest.b[1])/2-13];
    const labelWidth=lines(String(label),100)[0].split('').reduce((v,c)=>v+(/[\u0020-\u007e]/.test(c)?6.4:12),0)+12;
    labels.push(`<g ${attrs} data-detail="context"><rect x="${x-labelWidth/2}" y="${y-13}" width="${labelWidth}" height="20" rx="4" class="c-mask"/><text x="${x}" y="${y+1}" text-anchor="middle" class="${direct?'t-muted':route?'t-dim':'t-comparison'}" font-size="12">${esc(label)}</text></g>`);
  }
  const cards=nodes.map(n=>{
    const p=layout.nodes[n.node_id],k=kind(n),name=p.title||n.method_or_material||n.display_name||n.node_name;
    const allRows=lines(String(name),11.5),rows=allRows.length>2?[allRows[0],allRows[1]+'…']:allRows,subtitle=p.subtitle||`${n.year_label||'年份未记录'} · ${n.source_authors||n.branch_name||''}`;
    const display=rows.map((t,i)=>`<text x="${p.x}" y="${p.y-12-(rows.length-1)*9+i*20}" text-anchor="middle" class="t-primary" font-size="16" font-weight="600">${esc(t)}</text>`).join('');
    return `<g id="node-${esc(n.node_id)}" data-node-id="${esc(n.node_id)}" data-node-label="${esc(name)}" data-node-sublabel="${esc(subtitle)}" data-node-context="${esc(n.branch_name)}" data-node-tag="${esc(n.status==='candidate'?'自动候选 · 未经人工审核':n.verification_status==='in_corpus_verified'?'语料内一次论文可核验':'转引文本可定位')}" data-node-kind="${k}" tabindex="0" role="button" aria-pressed="false" aria-label="${esc(n.node_name)}，查看原文证据"><title>${esc(n.display_name||n.node_name)}</title><rect x="${p.x-cardW/2}" y="${p.y-cardH/2}" width="${cardW}" height="${cardH}" rx="8" class="c-${k}" data-animate="node" stroke-width="1.6"/>${display}<text x="${p.x}" y="${p.y+26}" text-anchor="middle" class="t-muted" font-size="11">${esc(subtitle)}</text></g>`;
  }).join('');
  const kinds=[...new Set(nodes.map(kind))];
  const kindLabels:Row={};for(const n of nodes)kindLabels[kind(n)]=n.node_type==='baseline'?'传统 / 无机基线':n.branch_name||'方法 / 材料';
  // A shared node colour can represent several sub-branches; the lane names carry the detail.
  for(const k of kinds){const ns=nodes.filter(n=>kind(n)===k);const bs=[...new Set(ns.map(n=>n.branch_name))];if(bs.length>1)kindLabels[k]=bs.join(' / ');if(layout.kind_labels?.[k])kindLabels[k]=layout.kind_labels[k];}
  let lx=35;
  const legend=kinds.map(k=>{const label=String(kindLabels[k]),x=lx;lx+=Math.max(170,label.length*12+44);return `<g data-legend-kind="${k}" data-legend-semantic-kind="${k}" data-legend-label="${esc(label)}" data-legend-x="${x}" data-legend-baseline="${H-102}" data-legend-width="${lx-x-16}"><rect x="${x}" y="${H-115}" width="17" height="11" rx="2" class="c-${k}"/><text x="${x+26}" y="${H-103}" class="t-muted" font-size="12">${esc(label)}</text></g>`;}).join('');
  const note=String(caseData.manifest?.evidence_boundary||'证据与核验状态以原始案例记录为准。');
  const caption=layout.evidence_caption||'核验范围以案例原始记录为准；原文可定位不代表独立核验。完整证据边界见节点与关系详情。';
  const boundary=lines('证据边界：'+caption,Math.floor((W-100)/12)).map((t,i)=>`<text x="35" y="${H-42+i*18}" class="t-muted" font-size="12">${esc(t)}</text>`).join('');
  return {markup:`<svg viewBox="0 0 ${W} ${H}" role="img" lang="zh-CN" aria-labelledby="archify-diagram-title archify-diagram-description" data-preset="classic" data-quality-profile="showcase" data-animation="trace"><title id="archify-diagram-title">${esc(title)}</title><desc id="archify-diagram-description">${esc(note)}；年份按列排列，间距不代表时间跨度。</desc><defs><marker id="arrowhead" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><path d="M0 0L8 3L0 6Z" class="m-default"/></marker><pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse"><path d="M40 0L0 0 0 40" class="c-grid" stroke-width=".5"/></pattern></defs><rect width="100%" height="100%" fill="url(#grid)"/>${columns}${groupMarkup}${paths.join('')}${cards}${labels.join('')}<g data-legend="" data-legend-bridge="">${legend}</g><g><path d="M35 ${H-76}h30" class="a-default" stroke-width="2"/><text x="73" y="${H-72}" class="t-muted" font-size="12">直接演化</text><path d="M205 ${H-76}h30" class="a-comparison" stroke-width="2"/><text x="243" y="${H-72}" class="t-muted" font-size="12">基线 / 性能比较</text><path d="M435 ${H-76}h30" class="a-dashed" stroke-width="2"/><text x="473" y="${H-72}" class="t-muted" font-size="12">${caseData.manifest?.recommended_use==='candidate_case'?'候选承接 · 不参与事实路径推断':'路线归类 · 展示连接不计入语料统计'}</text></g>${boundary}</svg>`,kindLabels};
}

export function diagramDocument(caseData:Row,options:{linkBase?:string;initialHash?:string}={}) {
  const nodes=(caseData.nodes||[]).filter((n:Row)=>yes(n.main_figure)&&!['excluded','rejected'].includes(n.verification_status));
  const edges=(caseData.edges||[]).filter((e:Row)=>yes(e.main_figure)&&!['excluded','rejected'].includes(e.verification_status));
  if(!nodes.length)throw new Error('此案例没有可展示的主图节点');
  const layout:DiagramLayout=caseData.diagram_layout||automatic(nodes);
  validateLayout(layout,nodes,edges);
  const {markup,kindLabels}=svg(caseData,layout,nodes,edges);
  const messages:Row={'viewer.passport.eyebrow':'方法 / 材料与证据','viewer.route.title':'直接演化路径','viewer.route.finder.source.title':'选择演化路径起点','viewer.route.finder.target.empty':'未找到由直接演化关系连接的后续节点。比较与路线归类不参与路径推断。','viewer.passport.reach.title':'直接演化可达范围','viewer.kind.node':'方法 / 材料','viewer.guided.explore':'探索此案例','viewer.guided.intro':'按章节查看方法、材料与已记录关系。','viewer.guide.title':'案例图指南'};
  for(const [kind,label] of Object.entries(kindLabels))messages['viewer.kind.'+kind]=label;
  messages['viewer.passport.reach']='直接演化可达范围';
  messages['viewer.passport.reach.trace']='仅追踪直接演化关系';
  messages['viewer.nav.route']='追踪直接演化路径';
  const payload={identity:caseData.identity,caseId:caseData.manifest?.case_id,nodes,edges,manifest:caseData.manifest||{},linkBase:options.linkBase||'',initialHash:options.initialHash||'',messages};
  const values:Row={TITLE:esc(caseData.manifest?.title_cn||caseData.title),SVG:markup,GUIDES:json(layout.chapters),PAYLOAD:json(payload),BRIDGE:bridge,CSS:diagramCSS};
  return template.replace(/__FLOWBD_(TITLE|SVG|GUIDES|PAYLOAD|BRIDGE|CSS)__/g,(_match,key)=>values[key]);
}

export function mountDiagram(root:HTMLElement,data:Row) {
  let base='';let hash='';
  try {const url=new URL(window.top!.location.href);hash=url.hash;url.hash='';url.searchParams.set('page','lineage');if(data.manifest?.case_id)url.searchParams.set('case',data.manifest.case_id);base=url.href;}catch {base=window.location.href.split('#')[0];}
  root.innerHTML='<iframe class="lineage-diagram-frame" title="案例交互谱系图" allow="clipboard-write; fullscreen" allowfullscreen></iframe>';
  const frame=root.querySelector<HTMLIFrameElement>('iframe')!;
  frame.srcdoc=diagramDocument(data,{linkBase:base,initialHash:hash});
}
