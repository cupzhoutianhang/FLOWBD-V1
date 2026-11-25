var e=e=>String(e??``).replace(/[&<>"']/g,e=>({"&":`&amp;`,"<":`&lt;`,">":`&gt;`,'"':`&quot;`,"'":`&#39;`})[e]),t=e=>JSON.stringify(e).replace(/</g,`\\u003c`).replace(/\u2028/g,`\\u2028`).replace(/\u2029/g,`\\u2029`),n=e=>String(e).toLowerCase()===`true`,r={baseline:`external`,track_primary:`frontend`,track_secondary:`backend`,track_tertiary:`cloud`,track_quaternary:`database`},i={direct_evolution:`直接演化`,baseline_comparison:`基线比较`,node_performance_comparison:`性能比较`,route_association:`路线归类`};function a(e){let t=[...new Set(e.map(e=>String(e.branch_id||`unassigned`)))],n=[...new Set(e.map(e=>String(e.year_label||`年份未记录`)))],r=new Map,i=t.map(t=>{let n={};return e.filter(e=>String(e.branch_id||`unassigned`)===t).forEach(e=>n[e.year_label]=(n[e.year_label]||0)+1),Math.max(150,Math.max(1,...Object.values(n).map(Number))*110+55)}),a=65,o=t.map((t,n)=>{let r={id:t,label:String(e.find(e=>String(e.branch_id||`unassigned`)===t)?.branch_name||t),y:a,height:i[n]};return a+=i[n]+20,r}),s={};return e.forEach(e=>{let i=String(e.branch_id||`unassigned`),a=i+`:`+e.year_label,c=r.get(a)||0;r.set(a,c+1),s[e.node_id]={group:i,x:165+n.indexOf(String(e.year_label||`年份未记录`))*260,y:o[t.indexOf(i)].y+95+c*110}}),{version:1,width:Math.max(1050,n.length*260+70),height:a+140,columns:n.map((e,t)=>({label:e,x:165+t*260})),groups:o,nodes:s,chapters:o.map(t=>({id:t.id,label:t.label,focus:e.filter(e=>String(e.branch_id||`unassigned`)===t.id).map(e=>String(e.node_id)),note:`同一分支的节点按记录展示；未记录关系的节点保持独立。`}))}}function o(e,t,n){if(e.version!==1)throw Error(`布局版本应为 1`);if(!Number.isFinite(e.width)||!Number.isFinite(e.height)||e.width<500||e.height<250)throw Error(`画布尺寸无效`);let r=new Set(t.map(e=>String(e.node_id))),i=new Set(n.map(e=>String(e.edge_id)));if(r.size!==t.length||i.size!==n.length)throw Error(`主图节点或关系 ID 重复`);let a=new Set(e.groups.map(e=>e.id));if(a.size!==e.groups.length)throw Error(`分区 ID 重复`);for(let t of e.groups){let n=t.x??28,r=t.width??e.width-56;if([n,r,t.y,t.height].some(e=>!Number.isFinite(e))||n<0||r<=0||n+r>e.width||t.y<0||t.height<=0||t.y+t.height>e.height-120)throw Error(`分区 ${t.id} 的坐标或尺寸无效`)}for(let t of e.columns)if(!Number.isFinite(t.x)||t.x<0||t.x>e.width)throw Error(`年份列坐标无效`);for(let n of t){let t=e.nodes[n.node_id];if(!t||!a.has(t.group))throw Error(`节点 ${n.node_id} 缺少有效分区或位置`);if(!Number.isFinite(t.x)||!Number.isFinite(t.y)||t.x<112||t.x>e.width-112||t.y<50||t.y>e.height-130)throw Error(`节点 ${n.node_id} 超出画布`)}for(let t of Object.keys(e.nodes))if(!r.has(t))throw Error(`布局引用未知主图节点 ${t}`);for(let t of Object.keys(e.edges||{}))if(!i.has(t))throw Error(`布局引用未知主图关系 ${t}`);for(let e of n)if(!r.has(String(e.source_id))||!r.has(String(e.target_id)))throw Error(`关系 ${e.edge_id} 的端点不在主图`);for(let t of e.chapters)if(!t.focus.length||t.focus.some(e=>!r.has(e)))throw Error(`章节 ${t.id} 包含未知或空节点`);for(let t of Object.values(e.edges||{}))for(let e of[...t.via||[],...t.labelAt?[t.labelAt]:[]])if(e.length!==2||e.some(e=>!Number.isFinite(e)))throw Error(`连线路由坐标无效`)}function s(e,t){let n=[],r=``,i=0;for(let a of e){let e=/[\u0020-\u007e]/.test(a)?.56:1;i+e>t&&r&&(n.push(r),r=``,i=0),r+=a,i+=e}return r&&n.push(r),n}function c(t,n,a,o){let c=n.width,l=n.height,u=e=>r[e.node_type]||`neutral`,d=t.manifest?.title_cn||t.title,f=n.groups.map((t,n)=>`<rect data-graph-role="structural-frame" data-composition-frame-kind="lane" data-composition-frame-id="${e(t.id)}" x="${t.x??28}" y="${t.y}" width="${t.width??c-56}" height="${t.height}" rx="12" class="c-lane" stroke-width="1"/><text x="${(t.x??28)+18}" y="${t.y+25}" class="t-muted" font-size="15" font-weight="600">${String(n+1).padStart(2,`0`)} / ${e(t.label)}</text>${(t.subgroups||[]).map(n=>`<text x="${(t.x??28)+20}" y="${n.y}" class="t-muted" font-size="12">${e(n.label)}</text>`).join(``)}`).join(``),p=n.columns.map(t=>`<text x="${t.x}" y="32" text-anchor="middle" class="t-muted" font-size="13">${e(t.label)}</text>`).join(``),m=[],h=[];for(let t of o){let r=n.nodes[t.source_id],a=n.nodes[t.target_id],o=n.edges?.[t.edge_id]||{},c=t.relation_class===`direct_evolution`,l=t.relation_class===`route_association`,u;if(o.via?.length){let e=o.via[0],t=o.via[o.via.length-1],n=(e,t)=>Math.abs(t[0]-e.x)>=Math.abs(t[1]-e.y)?[e.x+Math.sign(t[0]-e.x)*204/2,e.y]:[e.x,e.y+Math.sign(t[1]-e.y)*88/2];u=[n(r,e),...o.via,n(a,t)]}else if(Math.abs(r.y-a.y)<2)u=[[r.x+102,r.y],[a.x-102,a.y]];else if(r.x===a.x)u=[[r.x,r.y+44],[a.x,a.y-44]];else{let e=r.x+102,t=a.x-102,n=(e+t)/2;u=[[e,r.y],[n,r.y],[n,a.y],[t,a.y]]}let d=o.label||t.display_label||i[t.relation_class]||t.relation_type,f=`data-edge-from="${e(t.source_id)}" data-edge-to="${e(t.target_id)}" data-edge-id="${e(t.edge_id)}" data-edge-key="${e(t.edge_id)}" data-edge-label="${e(d)}" data-relation-class="${e(t.relation_class)}"`;m.push(`<path ${f} data-animate="edge" data-composition-points="${u.map(e=>e.join(`,`)).join(`;`)}" d="${u.map((e,t)=>(t?`L`:`M`)+e.join(` `)).join(` `)}" class="${c?`a-default`:l?`a-dashed`:`a-comparison`}" stroke-width="1.7" fill="none" ${c?`marker-end="url(#arrowhead)"`:``}/>`);let p=u.slice(1).map((e,t)=>({a:u[t],b:e,len:Math.abs(e[0]-u[t][0])+Math.abs(e[1]-u[t][1])})).sort((e,t)=>t.len-e.len)[0],[g,_]=o.labelAt||[(p.a[0]+p.b[0])/2,(p.a[1]+p.b[1])/2-13],v=s(String(d),100)[0].split(``).reduce((e,t)=>e+(/[\u0020-\u007e]/.test(t)?6.4:12),0)+12;h.push(`<g ${f} data-detail="context"><rect x="${g-v/2}" y="${_-13}" width="${v}" height="20" rx="4" class="c-mask"/><text x="${g}" y="${_+1}" text-anchor="middle" class="${c?`t-muted`:l?`t-dim`:`t-comparison`}" font-size="12">${e(d)}</text></g>`)}let g=a.map(t=>{let r=n.nodes[t.node_id],i=u(t),a=r.title||t.method_or_material||t.display_name||t.node_name,o=s(String(a),11.5),c=o.length>2?[o[0],o[1]+`…`]:o,l=r.subtitle||`${t.year_label||`年份未记录`} · ${t.source_authors||t.branch_name||``}`,d=c.map((t,n)=>`<text x="${r.x}" y="${r.y-12-(c.length-1)*9+n*20}" text-anchor="middle" class="t-primary" font-size="16" font-weight="600">${e(t)}</text>`).join(``);return`<g id="node-${e(t.node_id)}" data-node-id="${e(t.node_id)}" data-node-label="${e(a)}" data-node-sublabel="${e(l)}" data-node-context="${e(t.branch_name)}" data-node-tag="${e(t.verification_status===`in_corpus_verified`?`语料内一次论文可核验`:`转引文本可定位`)}" data-node-kind="${i}" tabindex="0" role="button" aria-pressed="false" aria-label="${e(t.node_name)}，查看原文证据"><title>${e(t.display_name||t.node_name)}</title><rect x="${r.x-102}" y="${r.y-44}" width="204" height="88" rx="8" class="c-${i}" data-animate="node" stroke-width="1.6"/>${d}<text x="${r.x}" y="${r.y+26}" text-anchor="middle" class="t-muted" font-size="11">${e(l)}</text></g>`}).join(``),_=[...new Set(a.map(u))],v={};for(let e of a)v[u(e)]=e.node_type===`baseline`?`传统 / 无机基线`:e.branch_name||`方法 / 材料`;for(let e of _){let t=a.filter(t=>u(t)===e),r=[...new Set(t.map(e=>e.branch_name))];r.length>1&&(v[e]=r.join(` / `)),n.kind_labels?.[e]&&(v[e]=n.kind_labels[e])}let y=35,b=_.map(t=>{let n=String(v[t]),r=y;return y+=Math.max(170,n.length*12+44),`<g data-legend-kind="${t}" data-legend-semantic-kind="${t}" data-legend-label="${e(n)}" data-legend-x="${r}" data-legend-baseline="${l-102}" data-legend-width="${y-r-16}"><rect x="${r}" y="${l-115}" width="17" height="11" rx="2" class="c-${t}"/><text x="${r+26}" y="${l-103}" class="t-muted" font-size="12">${e(n)}</text></g>`}).join(``),x=String(t.manifest?.evidence_boundary||`证据与核验状态以原始案例记录为准。`),S=s(`证据边界：`+(n.evidence_caption||`核验范围以案例原始记录为准；原文可定位不代表独立核验。完整证据边界见节点与关系详情。`),Math.floor((c-100)/12)).map((t,n)=>`<text x="35" y="${l-42+n*18}" class="t-muted" font-size="12">${e(t)}</text>`).join(``);return{markup:`<svg viewBox="0 0 ${c} ${l}" role="img" lang="zh-CN" aria-labelledby="archify-diagram-title archify-diagram-description" data-preset="classic" data-quality-profile="showcase" data-animation="trace"><title id="archify-diagram-title">${e(d)}</title><desc id="archify-diagram-description">${e(x)}；年份按列排列，间距不代表时间跨度。</desc><defs><marker id="arrowhead" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><path d="M0 0L8 3L0 6Z" class="m-default"/></marker><pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse"><path d="M40 0L0 0 0 40" class="c-grid" stroke-width=".5"/></pattern></defs><rect width="100%" height="100%" fill="url(#grid)"/>${p}${f}${m.join(``)}${g}${h.join(``)}<g data-legend="" data-legend-bridge="">${b}</g><g><path d="M35 ${l-76}h30" class="a-default" stroke-width="2"/><text x="73" y="${l-72}" class="t-muted" font-size="12">直接演化</text><path d="M205 ${l-76}h30" class="a-comparison" stroke-width="2"/><text x="243" y="${l-72}" class="t-muted" font-size="12">基线 / 性能比较</text><path d="M435 ${l-76}h30" class="a-dashed" stroke-width="2"/><text x="473" y="${l-72}" class="t-muted" font-size="12">路线归类 · 展示连接不计入语料统计</text></g>${S}</svg>`,kindLabels:v}}function l(r,i={}){let s=(r.nodes||[]).filter(e=>n(e.main_figure)&&![`excluded`,`rejected`].includes(e.verification_status)),l=(r.edges||[]).filter(e=>n(e.main_figure)&&![`excluded`,`rejected`].includes(e.verification_status));if(!s.length)throw Error(`此案例没有可展示的主图节点`);let u=r.diagram_layout||a(s);o(u,s,l);let{markup:d,kindLabels:f}=c(r,u,s,l),p={"viewer.passport.eyebrow":`方法 / 材料与证据`,"viewer.route.title":`直接演化路径`,"viewer.route.finder.source.title":`选择演化路径起点`,"viewer.route.finder.target.empty":`未找到由直接演化关系连接的后续节点。比较与路线归类不参与路径推断。`,"viewer.passport.reach.title":`直接演化可达范围`,"viewer.kind.node":`方法 / 材料`,"viewer.guided.explore":`探索此案例`,"viewer.guided.intro":`按章节查看方法、材料与已记录关系。`,"viewer.guide.title":`案例图指南`};for(let[e,t]of Object.entries(f))p[`viewer.kind.`+e]=t;p[`viewer.passport.reach`]=`直接演化可达范围`,p[`viewer.passport.reach.trace`]=`仅追踪直接演化关系`,p[`viewer.nav.route`]=`追踪直接演化路径`;let m={identity:r.identity,caseId:r.manifest?.case_id,nodes:s,edges:l,manifest:r.manifest||{},linkBase:i.linkBase||``,initialHash:i.initialHash||``,messages:p},h={TITLE:e(r.manifest?.title_cn||r.title),SVG:d,GUIDES:t(u.chapters),PAYLOAD:t(m),BRIDGE:`/* Literature evidence is separate from Archify's verified-repository contract. */
(function () {
  'use strict';
  var svg = document.querySelector('.diagram-container > svg');
  var chip = document.getElementById('focus-chip');
  var evidence = document.createElement('section');
  evidence.className = 'flowbd-evidence';
  evidence.setAttribute('aria-label', '案例原文证据');
  chip.appendChild(evidence);
  var context = document.createElement('p');
  context.className = 'flowbd-context';
  context.textContent = FlowBD.nodes.length + ' 个主图节点 · ' + FlowBD.edges.length + ' 条展示关系 · 直接演化 ' + FlowBD.edges.filter(function(e){return e.relation_class === 'direct_evolution';}).length + ' 条。路径与上下游仅沿直接演化；年份列间距不代表时间跨度。';
  document.getElementById('guided-views').before(context);
  var fields = [['year_label','年份'],['branch_name','技术分支'],['source_paper','来源论文'],['source_authors','作者'],['verification_status','原始核验状态'],['evidence_level','证据层级'],['source_scope','支持范围'],['relation_class','关系类别'],['relation_type','原关系类型'],['edge_scope','关系范围'],['count_in_dataset','计入语料统计'],['problem_solved','研究问题'],['method_or_material','方法或材料'],['key_performance','性能记录'],['evidence_location','原文位置'],['sentence_id','句子编号']];
  var last = '';
  function element(tag, text) {var el=document.createElement(tag);el.textContent=text==null?'':String(text);return el;}
  function renderEvidence() {
    var rel=Archify.focus.relationship();
    var active=Archify.focus.active();
    var id=rel ? rel.id || rel.key : typeof active === 'string' ? active : '';
    var key=(rel?'edge:':'node:')+id;
    if(key===last)return;
    last=key;
    evidence.textContent='';
    var row=(rel?FlowBD.edges:FlowBD.nodes).find(function(r){return (rel?r.edge_id:r.node_id)===id;});
    if(!row)return;
    evidence.appendChild(element('h3',rel?'关系原文证据':'方法 / 材料原文证据'));
    if(rel){evidence.appendChild(element('p',row.source_id+' → '+row.target_id+' · '+row.display_label));}
    else evidence.appendChild(element('p',row.node_name));
    var dl=document.createElement('dl');
    fields.forEach(function(pair){var value=row[pair[0]];if(value==null||value==='')return;dl.appendChild(element('dt',pair[1]));dl.appendChild(element('dd',value));});
    evidence.appendChild(dl);
    if(row.edge_scope==='figure_only')evidence.appendChild(element('p','仅主图展示连接，不计入语料关系统计，不表示直接演化。'));
    evidence.appendChild(element('h3','已记录的证据原句'));
    evidence.appendChild(element('blockquote',row.evidence_sentence||'此记录未保存证据原句。'));
    if(row.notes)evidence.appendChild(element('p',row.notes));
    var full=document.createElement('details');full.appendChild(element('summary','完整原始记录'));full.appendChild(element('pre',JSON.stringify(row,null,2)));evidence.appendChild(full);
    evidence.appendChild(element('p',FlowBD.manifest.evidence_boundary||'原文可定位不等于独立核验；核验状态沿用原始记录。'));
    Archify.focus.reposition();
  }
  var pending=false;
  function schedule(){if(pending)return;pending=true;queueMicrotask(function(){pending=false;renderEvidence();});}
  new MutationObserver(schedule).observe(svg,{attributes:true,subtree:true,attributeFilter:['data-focus-active','data-focus-selected','data-relationship-direct-active','data-relationship-preview-active']});
  document.addEventListener('click',schedule,true);
  document.addEventListener('keydown',schedule,true);
  window.addEventListener('hashchange',schedule);
  // Store only reader view state, never case facts or evidence.
  var stateKey='flowbd-diagram-view:'+(FlowBD.caseId||FlowBD.identity);
  if(FlowBD.initialHash){try{location.hash=FlowBD.initialHash;}catch(_){}}
  else {try{var saved=sessionStorage.getItem(stateKey);if(saved)location.hash=saved;}catch(_){}}
  window.addEventListener('hashchange',function(){try{sessionStorage.setItem(stateKey,location.hash);}catch(_){}});
  window.addEventListener('pagehide',function(){if(Archify.guidedViews && Archify.guidedViews.pause)Archify.guidedViews.pause();});
  // Embedded presentation expands the host component as well as the local stage.
  function sendPresentation(){parent.postMessage({type:'flowbd-diagram-present',identity:FlowBD.identity,present:document.documentElement.getAttribute('data-present')==='true'},'*');}
  new MutationObserver(sendPresentation).observe(document.documentElement,{attributes:true,attributeFilter:['data-present']});
  // The source helper text describes software systems. Replace only UI copy.
  document.querySelectorAll('.diagram-guide small').forEach(function(el){el.textContent=el.textContent.replace(/系统/g,'案例').replace(/职责/g,'方法描述').replace(/真实关系/g,'已记录关系');});
  var reachTitle=document.querySelector('.focus-reachability-title');if(reachTitle)reachTitle.textContent='直接演化可达范围';
  renderEvidence();
})();
`,CSS:`/* The diagram lives in its own document: these rules never restyle the app. */
html { color-scheme: light; }
html[data-theme="dark"] { color-scheme: dark; }
body { padding: 20px 22px 12px; }
.container { max-width: 1600px; }
.header { margin-bottom: 18px; padding-right: 300px; }
.header h1 { font-family: "Microsoft YaHei", sans-serif; font-size: 22px; line-height: 1.55; }
.toolbar { top: 16px; right: 22px; }
.diagram-container { min-height: 540px; height: 660px; }
.diagram-container > svg { width: 100%; height: 100%; }
svg .a-comparison { fill: none; stroke: #b65b12; stroke-dasharray: 8 4 2 4; }
svg .t-comparison { fill: #9a4d0e; }
html[data-theme="dark"] svg .a-comparison { stroke: #f3b679; }
html[data-theme="dark"] svg .t-comparison { fill: #f3b679; }
svg .t-primary { fill: var(--text, #152238); font-family: "Microsoft YaHei", sans-serif; }
html[data-theme="dark"] svg .t-primary { fill: #f1f5f9; }
svg [data-node-id] text { pointer-events: none; }
.flowbd-context { color: var(--text-muted); font: 12px/1.8 "Microsoft YaHei", sans-serif; margin: 12px 0; }
.flowbd-context strong { color: var(--text); font-weight: 600; }
.focus-chip { max-height: calc(100% - 28px); overflow-y: auto; width: min(390px, calc(100% - 28px)); scrollbar-width: thin; }
.flowbd-evidence { border-top: 1px solid var(--border-color, #ccd6e5); margin-top: 12px; padding-top: 12px; font: 12px/1.85 "Microsoft YaHei", sans-serif; color: var(--text); }
.flowbd-evidence h3 { margin: 8px 0; font-size: 14px; }
.flowbd-evidence dl { display: grid; grid-template-columns: 72px minmax(0, 1fr); gap: 7px 10px; margin: 10px 0; }
.flowbd-evidence dt { color: var(--text-muted); }
.flowbd-evidence dd { margin: 0; overflow-wrap: anywhere; }
.flowbd-evidence blockquote { margin: 10px 0; padding: 10px 12px; background: var(--lane-fill, rgba(128,145,170,.08)); border-radius: 6px; white-space: pre-wrap; }
.flowbd-evidence p { white-space: pre-wrap; overflow-wrap: anywhere; }
.flowbd-evidence pre { white-space: pre-wrap; overflow-wrap: anywhere; font-size: 11px; }
.flowbd-evidence summary { cursor: pointer; }
.flowbd-evidence button { font: inherit; color: inherit; border: 1px solid var(--border-color, #ccd6e5); background: transparent; border-radius: 6px; padding: 5px 10px; cursor: pointer; }
.flowbd-evidence button:focus-visible { outline: 2px solid #0794ad; outline-offset: 3px; }
html[data-present="true"] body { padding: 8px; }
html[data-present="true"] .diagram-container { height: calc(100vh - 125px); min-height: 400px; }
@media (max-width: 800px) {
  body { padding: 12px 10px; }
  .header { padding-right: 0; margin-top: 54px; }
  .header h1 { font-size: 18px; }
  .toolbar { top: 10px; right: 10px; }
  .diagram-container { height: 610px; }
}
\r
`};return`<!DOCTYPE html>\r
<html lang="zh-CN" data-theme="dark" data-preset="classic">\r
<head>\r
  <meta charset="UTF-8">\r
  <meta name="viewport" content="width=device-width, initial-scale=1.0">\r
  <meta name="generator" content="archify 2.17.0-dev.1">\r
  <title>__FLOWBD_TITLE__</title>\r
  <script>\r
    // Resolve the theme before first paint so light-preference users don't\r
    // see a dark flash. The toolbar script below re-applies with UI state.\r
    (function () {\r
      try {\r
        var theme = null;\r
        try {\r
          var param = new URLSearchParams(window.location.search).get('theme');\r
          if (param === 'light' || param === 'dark') theme = param;\r
          if (new URLSearchParams(window.location.search).get('embed') === '1') {\r
            document.documentElement.setAttribute('data-embed', 'true');\r
          }\r
          if (new URLSearchParams(window.location.search).get('present') === '1') {\r
            document.documentElement.setAttribute('data-present', 'true');\r
          }\r
        } catch (_) {}\r
        if (!theme) {\r
          try { theme = localStorage.getItem('flowbd-diagram-theme'); } catch (_) {}\r
        }\r
        if (theme !== 'light' && theme !== 'dark') {\r
          theme = 'light';\r
        }\r
        document.documentElement.setAttribute('data-theme', theme);\r
      } catch (_) {}\r
    })();\r
  <\/script>\r
  <style id="archify-fonts">\r
/*\r
JetBrains Mono variable WOFF2 subsets from Google Fonts service revision v24.\r
These fixed bytes are shared by the viewer and its SVG/raster exports.\r
No local() source: an installed copy must not override the bundled font.\r
Uncovered characters (including CJK) still use the system fallback stack.\r
Upstream: https://github.com/JetBrains/JetBrainsMono\r
\r
cyrillic-ext    1664 bytes  sha256 9343de2ca5d9549f792e7962375af8efb0f320c7643bfd36c884b5a30e5c396f\r
cyrillic        8892 bytes  sha256 4995a9a43ac659ec32fcd8b463755cd6a07b31a6e6b3894a6a153b661cf490e2\r
greek           6800 bytes  sha256 49c3da6c9a2b279b0f1f860f5cfb1f5dc38d88a5c7be9c9b1837bbc4e3db6111\r
vietnamese      5872 bytes  sha256 d44eb1936043a56038eb02dd70b243f379bef65783f94ec12f277550720411f1\r
latin-ext      11596 bytes  sha256 9c38cb2d0d2d93c1ee6e21fa78db76f13ea7e15e15cc64214c7ca89b6aaa35c4\r
latin          31340 bytes  sha256 2c32b9b3ee358c119e210f6f5195f9bd34894d78a785ff2e95d60e718e400af4\r
\r
Copyright 2020 The JetBrains Mono Project Authors (https://github.com/JetBrains/JetBrainsMono)\r
\r
This Font Software is licensed under the SIL Open Font License, Version 1.1.\r
This license is copied below, and is also available with a FAQ at:\r
https://openfontlicense.org\r
\r
\r
-----------------------------------------------------------\r
SIL OPEN FONT LICENSE Version 1.1 - 26 February 2007\r
-----------------------------------------------------------\r
\r
PREAMBLE\r
The goals of the Open Font License (OFL) are to stimulate worldwide\r
development of collaborative font projects, to support the font creation\r
efforts of academic and linguistic communities, and to provide a free and\r
open framework in which fonts may be shared and improved in partnership\r
with others.\r
\r
The OFL allows the licensed fonts to be used, studied, modified and\r
redistributed freely as long as they are not sold by themselves. The\r
fonts, including any derivative works, can be bundled, embedded,\r
redistributed and/or sold with any software provided that any reserved\r
names are not used by derivative works. The fonts and derivatives,\r
however, cannot be released under any other type of license. The\r
requirement for fonts to remain under this license does not apply\r
to any document created using the fonts or their derivatives.\r
\r
DEFINITIONS\r
"Font Software" refers to the set of files released by the Copyright\r
Holder(s) under this license and clearly marked as such. This may\r
include source files, build scripts and documentation.\r
\r
"Reserved Font Name" refers to any names specified as such after the\r
copyright statement(s).\r
\r
"Original Version" refers to the collection of Font Software components as\r
distributed by the Copyright Holder(s).\r
\r
"Modified Version" refers to any derivative made by adding to, deleting,\r
or substituting -- in part or in whole -- any of the components of the\r
Original Version, by changing formats or by porting the Font Software to a\r
new environment.\r
\r
"Author" refers to any designer, engineer, programmer, technical\r
writer or other person who contributed to the Font Software.\r
\r
PERMISSION & CONDITIONS\r
Permission is hereby granted, free of charge, to any person obtaining\r
a copy of the Font Software, to use, study, copy, merge, embed, modify,\r
redistribute, and sell modified and unmodified copies of the Font\r
Software, subject to the following conditions:\r
\r
1) Neither the Font Software nor any of its individual components,\r
in Original or Modified Versions, may be sold by itself.\r
\r
2) Original or Modified Versions of the Font Software may be bundled,\r
redistributed and/or sold with any software, provided that each copy\r
contains the above copyright notice and this license. These can be\r
included either as stand-alone text files, human-readable headers or\r
in the appropriate machine-readable metadata fields within text or\r
binary files as long as those fields can be easily viewed by the user.\r
\r
3) No Modified Version of the Font Software may use the Reserved Font\r
Name(s) unless explicit written permission is granted by the corresponding\r
Copyright Holder. This restriction only applies to the primary font name as\r
presented to the users.\r
\r
4) The name(s) of the Copyright Holder(s) or the Author(s) of the Font\r
Software shall not be used to promote, endorse or advertise any\r
Modified Version, except to acknowledge the contribution(s) of the\r
Copyright Holder(s) and the Author(s) or with their explicit written\r
permission.\r
\r
5) The Font Software, modified or unmodified, in part or in whole,\r
must be distributed entirely under this license, and must not be\r
distributed under any other license. The requirement for fonts to\r
remain under this license does not apply to any document created\r
using the Font Software.\r
\r
TERMINATION\r
This license becomes null and void if any of the above conditions are\r
not met.\r
\r
DISCLAIMER\r
THE FONT SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,\r
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO ANY WARRANTIES OF\r
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT\r
OF COPYRIGHT, PATENT, TRADEMARK, OR OTHER RIGHT. IN NO EVENT SHALL THE\r
COPYRIGHT HOLDER BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,\r
INCLUDING ANY GENERAL, SPECIAL, INDIRECT, INCIDENTAL, OR CONSEQUENTIAL\r
DAMAGES, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING\r
FROM, OUT OF THE USE OR INABILITY TO USE THE FONT SOFTWARE OR FROM\r
OTHER DEALINGS IN THE FONT SOFTWARE.\r
*/\r
    /* cyrillic-ext */\r
    @font-face { font-family: 'JetBrains Mono'; font-style: normal; font-weight: 400 800; font-display: swap;\r
      src: url(data:font/woff2;base64,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) format('woff2');\r
      unicode-range: U+0460-052F, U+1C80-1C8A, U+20B4, U+2DE0-2DFF, U+A640-A69F, U+FE2E-FE2F; }\r
    /* cyrillic */\r
    @font-face { font-family: 'JetBrains Mono'; font-style: normal; font-weight: 400 800; font-display: swap;\r
      src: url(data:font/woff2;base64,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) format('woff2');\r
      unicode-range: U+0301, U+0400-045F, U+0490-0491, U+04B0-04B1, U+2116; }\r
    /* greek */\r
    @font-face { font-family: 'JetBrains Mono'; font-style: normal; font-weight: 400 800; font-display: swap;\r
      src: url(data:font/woff2;base64,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) format('woff2');\r
      unicode-range: U+0370-0377, U+037A-037F, U+0384-038A, U+038C, U+038E-03A1, U+03A3-03FF; }\r
    /* vietnamese */\r
    @font-face { font-family: 'JetBrains Mono'; font-style: normal; font-weight: 400 800; font-display: swap;\r
      src: url(data:font/woff2;base64,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) format('woff2');\r
      unicode-range: U+0102-0103, U+0110-0111, U+0128-0129, U+0168-0169, U+01A0-01A1, U+01AF-01B0, U+0300-0301, U+0303-0304, U+0308-0309, U+0323, U+0329, U+1EA0-1EF9, U+20AB; }\r
    /* latin-ext */\r
    @font-face { font-family: 'JetBrains Mono'; font-style: normal; font-weight: 400 800; font-display: swap;\r
      src: url(data:font/woff2;base64,d09GMgABAAAAAC1MABIAAAAAdAQAACzjAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAGoJLG4ouHIM+BmA/U1RBVIEgJx4AhTovTBEICuBkzjkLhAwAMMVKATYCJAOIEgQgBYdGB5FVG4xnNXjTMeV2EEi463Muilo1Semz//9z0jFkDP0YgPnK6IQkTGZVRXZVMlEhJrRAsqq2tIQeZfVhf0qr17jt0HuNqAthhO/aPDdxgAtjFWuBDJd7eOb6YRSNJoVoApre9AOKGEQaSY8rp20yx+r3B4Hkct+7VO3Onuv/+YAPXOfnBs8qtx2hsU9yefja7/Xc3RdkVWJUX5VYkkJyGd/6WgQhy5Id2YSPp239PNYAjDwbxACVEIlell0QRUDBVRRXQsTC6Dvvzqv2Ir0q735l86PrKmfZPa2RRiPZsr1aIK9rHQD6vvBFAm8If3mFf6n8EJ/hI9IBycnKMJYsS0OVDWB1zZ5HgCbgDBZFPEEghCf+1Qv/yj3z5lYfxMrYvmGFEV9x+aJ60/v4+cvh/v9VTMYcW0jrpEBaSFtCG/6f/mLn/l20wDJOmkkpsBQCfpM6Uw7asmUZSLLAsULPPBWmXuduU/JK5/W/CDCwbW7Xcpypj4o2uhqCyR6/WcNmLn0v+dIKKAZhUJLB4f//XPlewNw7f0vMwjTwM7zAM7O65cRm7CKosuqpqmbFy6Z2L/vKAs0FmaRg/Pwezl1hck9JvEXu1hBAMR2P3M1zALeHgi9dmWql02gsBVEO8uBbqF74x3so+nQBUlV4b6L7IPqPdmcADBa7ABdLQgQBUgLN3YHHM6C7B89yAUFamlfhpHPO7HlK7/jG+twYE3obZC6NvnKXuyAOXkV0hey4hS1wOvetf/8dpubhELe3Oy+im4VW5DHn54dRSohDLnael205OfUWzgN+sBsxCEwfn/pzCphszb8/YnQsMkgShCsNkiETki0PUoAHKSWAlBNBqlVDxMQQqTqIkhqiY4KYmSEWFMSmEeLSAvHqgPh1Q4KikH6DkJhRyLhxyKQZyJx5yDqbITvsgey3H3LQIuSYk5AzLkCWLEEuuxJyteshN7kVcrt7Ifd7CPKIJyFPexbyoQ9hPvYJzNe+hfne9zC/No38Xh75DwIMAoZAQC0OEODPXzGyuTmfIAgsR4IAqlVSYq3+5m6H9BM/Z8chXQJgcBAgIuMGNjWgJvS4A/vLWrx447GK0VIdvy+/a/FUN32j0t0I8DTzoeuQsMPzImZfnTrvDNQxjaeujr3ycu3UdPHXQCwOnipXYqPP4t0fpK59Jw2l7RXF098XwWN/3eyyPwNGuenBqZG7+l2rXMc2gdFOt8S16cyOicd5cLufKkjXmH1uxQZUFfEoDdaRQxKo7iUu6CulE4HeiKGunVp5Oo9s74CUBMrHYz47qXLBHf6KDFQriWCjwRBrTYFWTo5FomZ4R9T1zavDnFSwkHhHkI46yjuc54IKNSqTAcuUoW4eRR3xyjsDTCppNhR1oMiziLZ7CJiEXEzFLMzHQuRjKQpQiNUow1pUoBaNSKEd3ejBNmxHPwYxijEcxgmcwZW4CtfgRtyKu3H/0EXpwC6HEuyct6sTcQus9S0HFjIwcx5FerhU59wpbQtMKEKRjD7pPty2Lv3aN/nv/bpFHVunA1BkypWkXkEsP0ds+e4W4OZLWDJlzskoi47O+3+NTULRfMRrIjoKudCSrMfJki1a8VaVVXcmlGVVVj4e2ajF9W4lHGvX7Fq3DPtxUoILg1RCwQUQQBkMCH+EsiGggHD8OTnCUALD9E/2Ra6EMyR7kcv7JCzLnB+sxJaUgAiejCmYhtlYgEVYigIoW64BEYpRDnXLm0CFRiTQjk2tXneEbFXlEh5WiOHL9lPjjOS3v0SQbs0f2KT8YlfKyMEEqjTee+C8RdX+ZWx8AngjbcTH/M//H5D7SL9Ad/97AyCNXTwwXCIEYWMBrZKA0Vhnfg/NIgBHP5FRlAHIkHYkqRKpMAgrMgMEkIEUCWh/kF4EEiAqMEGQ/gV5+KuJ8j4jlUxcuMvQL0a8AwOnaY9dIiNYsolvegPcbqOcx3TCNwkkezU7nscg5U5Il5mzf7wT5UojQDnnoQ5ptd4+B513o+fJimr+Z5tTTbeu3b1798T+W3bmfj+EJWAcrOLzVXFG/Fn0ht8vri/uKx5o5Qz+L8J7ATRb+/M+5wbPkWiq/lnBlJPgu9YAljE2XAj1063846Y9SDmqZrcH/qy+noEftcrsv9aTdVLH1Yt+sZ8/7QT0/wu+fwF8++XFt4ekD+L7+4DAa7PR1T4BxFx6RjgCycqhxbC9zVWZWNqStWb8Z6LMCExMklFck1JNSzMjxZQMszItt8xq2ebkWiXPvBwrFduo0Ho8m5XYRGCbUluJLKi0U7kdhHapUG0PsX32kzqo1mEyh8gdUWeR0jFqJ6mccJzGKUbn6ZxhcI7FZZQrka5gc7UG17G7Vr1rNLuF281cbtLhXm3u4nU7n3vQ7tTubl0eEPSIkH5PG/SsAc+4gd5Zre6QYFiRDUwuKLAO2zizJY2u1+JWvZ7wgfd86FvdHuJ3P8aDejwm7FERj4t6EgIasSC5EnDHG9lPBRsvewuo0D1RgxLZKOmqRUljrD/qULKVEfXSO6h9kIDXn1QN4CmoGRLUnwnKNwbFyQAZa7CJdB3odDbpEKk4JrGNCYoq9vwqeQaCxVjbuYpZ0JZTcdOEuelFRb3D/BAwjnqsKwvrqiJ1nRNV6s2rm0WxBGs98SophpEmnyXQxAwadn7Flbm2otBzmyozKkoKwiqjNvz4DdoB3ooY4oJCDjajzo1H61FCstdsMtey9/h9Xrs2HesIo/u1fBsDlH7Ddm2eodhW/uke39efiA8d2avVbP/GQ2ef40+Mm0rMjta3tdaUe99hbzZvC+O2S1vguWlC4GhFkQQGao0iWz6S5MdrUG+/nf7+QdRYZxUxwjLj5d/G0c/urvyn2foW1w8SSUNSRhJLWTcCoRPHKCg17eKAZK+dm/3/s/39K9XZD/lHUvpl+69MP3/oD5RUG4gpijt/mVFWI0mki366IE6cymis3TGbXamuuGgy/gIduvTgwqnrKhm8/3RR6UONwGMllWI0vpK4LuOxUUmZSRElyK0DeUas9kjvWe4a1WlYa+ihNjU6Rcr2W68WJFCeOQNcDIl4whnRG5oasZIT8kAlG2PgUuofjuUQVhsuH2Zqcin9BbnxlI9smVHlSUENWU24MpBnGGx1r0zovX4xTjQtIRnpQQptF6JcbX8iDsZnJ1iedo+f+0cSbEGDfuTelFC/PGwEFIChNptaiLBLjeabspqRgmJT7b+IaZPZXfQ6AdWiKywZ06ko8z49eCyc/FFE5QSz6CssTOtbZ43VKXVOJvSFbfWLc8NLUEFtWpvfOKrMbq7QLbE4FbnrbWUmDrVRUCODRqJcRjoZldezbTuYHCsJik3NqZ4/LPk05tYHoy1RBKJoKpI1TQTZ8OM7wpn8R+Yil3RaJuZuLcm403uKyeRr3E1oRnlaKR+CWcQ1uT5xWbXI7eMfMbaHg/XQMm9nImOlB8UxJKks63PdlYJq01RX31+Beubfd6XKqdQuEa2tneop95x9XF7fSHgek2V1X7ZjMNnCiFQivWpxaM7xpscyyANracPcaR+RONxSQKyZydto6zKt44s43V3LZ/H582Knkk4ibZFUjB22J4aYfzcamZ+SbdMUySMFYBrBK+anYmgmIZn7qgZFJq6sA2TmSbYoWZlfyxs0mDl94UqDg6ihTMaTM8zwKD11HfD7tZNTV+5+12zW2gCLezA9gpGJMJwOvmqbxUXlBx1RSt4zucDzVHaaaqqI4zAS0p5JwzKsTN/VclbOQB81dn0srPvY25g+8gs4lmmWujlPJS91NcUpc8uMva0cfmIVlKatjaPG5iSyNf8UHwyOAdJLZc9NMOUDPDWRWDH1Y8LvsmMDfjZ6pBIcLH6e//jsch5EoJA4peEMerzCaYRqxDOoYtJMXlG1GIFAYgbdR4UeVXdJH1Xg5f3coNFQ7ZH1C31iJSQdka8BzWtsETAU8pgwtp/W6gkTjse81fGbTdHk5E9XPnr9uvJy1+zN9vDVq6jJDjNQLjMZcCjQq7UhHStIUGN4zKhuGdpOshCQem+EOKTTEfvwQqaJu8+mdwyiHLoftufopDDTBqaSuhppBK2+rA6t8RIat5+GsMqb3FUmGZOIDBLDymeSM3mehUnzVxkwL8xr8/Cd8+s/39J5mF88b3M8Z4JOK5gzE1+KBxVSk+X/CaMUlPe9teret7rlD737saHS7tR98L/vKymx73T/wV9Pm1Vdzev6wHVl8TvL8t4uxPG8pzO++/j731qgb//kNH0abqdTn9lT9bRm2fppPcg51h6FOkQ5repgj8JqDStVQYohSKvJZKUIF2EtpdbcCIZUhcJKCMTvaxzQ6CO2Cpu+FzfT2OuJWp1N1goqXv9R4LS4ClyPtSR/GfriS7Tro+rWasxFw/3w6698elMjMrARW/9h+rtr0ZUG44z+Kz2TfTLer7zASXXVu35IfRwZo49oj9DbyA5AWfdh8p+OtU3jxOaWDzC2BgdJ+tvSdvsNNIc9sHI5BOKMYfS8vvfW0P2rB69qjdEwE2d2OGnI+dQ79ac3+/07eya+8r3JggQHy1t5orNpencyH7td4Qn4/haa0ryj/juyVTpXOSpfgtbK5s5nTMrObjkBEo41pFAy7lYGQ/RGgu6iBpKUUV4TYSWcRMyZjJZQwtc82Leays0sz3S5vJLNdWu2FFNXC+Gypj+4ORNLxlajTeKu2BMpp+Szg1NZhQeqij/Oa/cj71ZepX/CGYh/REXUmqDF6Y5ROccswwua5drtO/S2BqPJZtfvADnHMSDXdaUxOqfFZmkw66S11L29fGeed6TJpO4I11E9M8PgZ7QkbjKSOqVMTj0XLXXkecacuK6rTwHPPq1ryLuclhVTlocM7oMzbUXlVJ027cEyPxYDqYQqEFJaPvbf/OOmDT5lbZAkNT1hDWWjDbi90Yzb7bis5eIHW3QkZUwFCYcKqpQhy5POzQRuNRnNNoKhFMGg0moLKBRBq9OiDAVVpJMw2KlNvw/soox2+H/ngf6KfnInjIlca1xfiW6tv3Oz+M+bNzQ/nbRzCWdgZDKSzWTjRrsZN9nx+lC9wxNw8zFKaRw7vu9CikpW4A4qFDLWIcxWowm3EvWmajJ3GGt7q0NbvIyoSefVtAhtxUFzsbClKS2t9eZepi+mfW9NmYV5Lk1Kit0ksgrh/6y3nwzul9z5cn7+R3fukQTffjILfIxDVk+fzT5QbTT8zbFRv7s52um7Wqd6XK+gqq0Mu2GmrTM8Fmlf7Y9lfIcH7NoGstWibLlSppDUfgIfNd+uP/O3R0eu+sES3rxXcQiHi8QJ2tHgdEp/rygp4/ksDjdeZVgSJAgOc4T1bp/zwHsxYTNf0Dp+Xx43JSzc8pK/GstzC9YKY47SbD7OK7sd7XSJ3GWluKjdcvcqNN5FqybYO3t4pp/VyVSSer3JbiWOEvZQqicNFQyrc3Q2+Fd4K8O5JSZ3+0e6rwnEnboJRxORm4vWnGPiTCw7t11W2qzUWvFzOHJKhS6U8HwghUOHx0L94dBYW70ntfMdO4vHIWzWm+0EQ8Bfb8BtJEPuxf7VFXKZobtHpS4skupgmaBuXusgGenQUFS9Wf1LH8Oun/VWWYUUaSfMlJ3iJcKseG8h/+WnWEksKqRSFXOrgiE6kEG8QJBH93CW9v7jRfWij29Fs50wE3kHT2D8u4y4NZSpnlAfnmXY9RPezoiNQXJxRUx+vL8HhRT+Kp67hb5B3F/dgKLZ6bjHbvNFxkOzociYz+ax4+lhli6jk/G1VlbqLXYiRkR/vYGwkTGSeuafDLfGciqp5gZ7W6TfP80MmQhSqyftZAh89CObrqYTXr2LBsrzE2Ms7qPj+x1lrTw+XVZG83mt0H5L20ai3mq+7TOaTI7MTfVDOM4cHT770eCdifeUxs7+0vgV5uoahVV2+bd30TmW8g7BDTREe4Lth96nHltAxIBTvgvERnsFsBS6TDg5cBF2jUkHLhJORfuFXLI13CnCQQjLLQnFQ5Q6FNZAj4miyIMkRSWsoRRLYOFFqjyLdHjmHZJve7OYOkMeMG8vH2EYK2hxf0cJGXPVjPT0I5m4L4pcJAmKhlK8riC7faT7jpHrc3JGeoUSD26tNy+GrA3HPUssmjsvNUyI/LFlJWSXm3F3DowGy5hCiqg3GhT4G7woWU+XZ7iYACUVa4yVFV+83pTiTWtxNDiD3pDIE246w3T9VyNSfSoqX3+5KcWf5nU53D0dvfB6R3BUZD5c1k/QS6bGQKf7Ru+NFfdUGmGoscVlt52kT55kTr5Dv2Oz4Is0tH/n2uaa/o6enRnpap9m9GT3yHp6Nsodcp7OtnMxJzw1GQkxIcJSr9OT9UR9CZGZSeh64jnZoPzOi3LejBJeX0GtPb0TE73PA5BmymjCKTKfVaLU2WG+U+jVbhX2ZmZuEuJbO/DasemXRr/V3S2MGudNR0tL51zmebjpFu9rz2B969t67rdY7vfOtUXS3wKGUa2S0gcYwyo7DRER83HIbUh9l0ZXwMf4rnRd6Y2hAZfJ0iA2ahmpy75K5YwRJBzRM8Kq50Si56qEz8DNC7s74h178D0N/p44bMtwBR3Vp7k1q6f4Trm3fdCVdgDf3bDb8M4ai8NqxB1Oy5qWFUarWaOhzMY5SFH4zBA1wpnhv270LnlfeaHlbOAD32O8yyV9PW6lY5p31OJz9LlHrV5H03nvecG//Ec+pD8UO2V2/KSXis/tnO9be5SabsKsCRS3bN3q+8z72cn9Ww1Wm4GUbgW44wa5K6h984uPv+L5z/PKw0839wL8N7biBu8NnzGf4aNlBbSqnKLqRsVVDZ3tjqaOtkafrWXEXvhDN8/7k//sCxJfhaa8zF5xlXBHZb7tnlFbzZbnKQFMvcRvPzmblQbZfIovy6q+W5D+w60iWHrRo920UQtNxwItShYsHbeFEzt4ZTx+OY9Xzi+tf88PCxKvOIfqLdMLfWML8MqW2EJkfAHsW27xQF/lvr3ccK+Qc4sv5xZYsWXXQtvCQrS12dMMrC3neP/IrCBZ7+j0UI1V//drMqoaqaYMJGEtRahUntQG5e3FUFKCiotRdroBpnby8yOwcNpFugBt4b+clivwUjHRZxWCxBko/HnS89XajV+B5FXcpZI/tZRWJvOkNviO1VvCzSv6nVfEzc/jwn3fh/bHhvZD4S0KMRSzH6kroxvpxt76IfuQeNmVZhM7gTxGblQsj548Iw7B0TNVYnns2Y8IZYv/Pd75FXKZYz/ikCWZFYLnX0m1a+OivPJj5SXsCv+5h58ISwRo4wAADbC7XVgDxBQZJjfa/dCcMMrFdSTWdDrMqmv4EFMxQWbNd7Ehn0NMRfWjITNMSKz8/lQZBa/ERMzQw6rG+iNaDbUDUFJnv40l0ierkPmDTZgHb16nFJ5wEUYBMWrFDbGDzIpTTEGA04kJq7W/wcqFuI4YnWLaiE+gJ6wBYkfMxC56qU5+jrA6iGuNVpIKVBzi2pIyZ7INR2hgnL+hj4swCkhwKEwNiRVEONYo9DgnRANhSjBMBghxhVgVK2KICNeGCZ1hqitWxLK4BDBvwiyRuiUV18jszd7Vtl93tEIlRljE3Y1yEvcaGIAz2oFgWlIRJoEm7ANoafrjDI+2C4OgxvtgfeXeW6SEeCLiaasqxCIi68VoOC9ZjmCRkmBMS58K8Ko6YRfCFE4sN+Kp80YGvM2qQiyKkVjDYuo+JznCZCAuNPIQH14sg32aUAbv1hUtBJ07ICtnXQKeiiFMAQDdFsyljWYKlS4Tqn5F7RgYUs64+alm89tHGt9/+uArb+OzmfUo5smBH0dTX8v07W+DtjcGMF8BYCZIY+92tfRQfGVh9/z5tyWh88YCW4DSh9CVwo0zPETBQXSwPqEkwfnRq8Qw77/wqfBR52fJALybD8zqFm8QpI5TYgauxSVQcF1hBAa4kJZc/mOcSXAFMiO6f2cVezMdZz5aRijGBWWaw7aaIHbfp+mAOvfbMVFOhqiePKSEjzpvqvAILDNjogkqWueA3OSaZHuLI/kqhENLb8r3uDJ2e/7GKM4psuDZl1XIR0iWjJYlISeOoRKcnDLWl/mXv1ELhEkJOSAmxt+CiLqsTFImMvtSJ6myKH9NrRueyRYvoo06rmCpzJRr8QXLXMMF6TQJMB9VQGuergZSQalT9T5QJWSqWCjwo7NPgNQOd+Ey5SPAALsKiLuyatMlH4pxMisFnFmL9qVQn0zFVFlVK0cf1M29MhBJ3URgcBoy+xJdqcD4WEm8dhx4qyBa7+puXRIu/X3e7nPGs1M7dLa6Fp/DfB9y0/xLTG6X4PIh/+Tb/7VBGi4RgDQyQLsS5arV8hk365gzllztRs94yff+k4C4KFMeg7B+I6bMWWuzg5Zc7S4PeMyUkupSWdmrnHia4bOtad6Ft3zz27jtu3LPb/mCGBfLvKaburk7fCfu3F2+Ny57/Nv5ZE/1ut+2d/Cdf1e8J9/ck99Z1qmVplRMDmqhdlpLmwkknFiKqKAeTWhF/9IsLRNPKpWpxj0WsZSVPMn38opFRmxywRq7Qssa2SSAYMLIU6jeqmo1KqkN6lZaR3VaV+o2RZXRpf6rGeW1pqWhzYxnlSY2hTmtz4Zt0lbYGjtjW5sy18nNf3zYJ32XE8654g9f9UwMRk3UhTX8MR17oh/T+EY6KBCCLxhgQS+GMI5ZrMYe0JBgwEeKNlb4F7NYhtQjfdkFd39nvH1Dt/qpK93K61KarmzLYEZzPLclm2q6mWc/VzmTuaxUqwqrtrRlr2D110hN1VztK7PCKmtcu1ooWNVBZC6uWNneTAAGRGGwB8C7mOknt5WtbfGQaD94ZMcDh+eB553887sfv/s1N2YHgSPp+F4HNwqtA3PT9IMSPl409aHmVZY0W0vTjBIdxKHFYDuVqV4tm03JnsE0F3xMEBzK0E1S3JZ9K0+jiT1thHKl7f4+EE+B/MCKG+RSd+6SIQYYMkZxnMEQl34iAb8AQI6IxaOWXuEmPbEZ8JAtlVWGskHOzdXkHBSG/3BgaHyWb8/KPu67zEIZ/kdxVtrqmDdqmefw0D4HbxdnqT+nHhsMx2ak5fkkwkFFQba0J/HHq4en3HXvq0BgLLY9POAHnC+wqyKkn72wPvksncAl6efkdV1Uexpva9RaXGzzHhYOTI8IyNXtLvOjkODxnNq/nMRJp1OYf98FzSS3bmcO0W2e77/feb9/AL0QpQnpHGRb4Ke+VCjbWaKugehz0kVeTnJSv+MC+POQK+RCEdi0jOjnN9t/4qGOpHueyzzvSRLOt6+Xg1wK7rjjwvwIQSqmHpGRXaNSHfAhe3azDANJ5EEVvMtm8am3NTPlztwcN38DYhjpsgfnvNjf+rPYPo//YuWnRUfYI4bAQuR5HtJsYMz30emueoBngIGELxMMwI73ND6QG4U12PIyDS1OKnLXXdiLA3YOPDqKZ9YZYajMT2DyOxln9O92n3NOw/uaE0fGucM9k+ObjT9//OTDjwchhzOjqZRcQUgygVZS/6hWjgX2xbZxusjnF7P7A7MUxBCGjLMNV+HqhkF3Le4B4TNdE5lgnG4ywe3lURymcwkpI5+SxMbicPhODpUwJ5dBIJLPacBjJRNDPe46IA+coJYH6G+0cGKSQuNslsfcwRuF+YuFnJ6rudTvJoxFZGQeh64bXmnZCZGa++NpS2a7147tkc268V+d7GSt7gTcPC+VGn7Tu7R5njKUTZy4TrznFRwpTc+LJepE8GMquo177ndKeg5KqU/HnDnVWZaOOLkc8OiZ64W5bTOWOPCE7fjCSiV5UPn/y1kYAgq+fZYv2yJNbqU0yyTwujQMrdsFjTi8Piik3JqjLbd1UVpfg+XqQtNbEnV29rPitl73YtWWnmMMWGG4ZEsRIBMBQEsHdXJ1pGV4RbKm5uBr1bzQIzYhi2qRj/evaCu3+VO4pZen5QCSMW+3/xtuNitzKgONWTGNAM2aTq84DNnFATPtKhJTsp/+CExHzb0e5lRlV+uBdsHkgHsG21gUIW7eRLdXPBH0Oporgt4U4hS6OsUteDpsBizZ8r66+nILROVV1KKWkk2CXTdk8JKiccv9JCFtRgLlrOtCCfZE9Vf2Vy43FGfO1/03dfXcUTTNVpgwwLOdLi8nFrJ9+WiHZJJZxCO8qkVAEfz6F2NuHc98Qgk7C4OWBUl6ugLw3b2dGYcYaYZm6/Y8LhPHIbbYqQFnj84dJ1tUpuD5oVYqcwcPTupmBO0qWRcC435iTjBlAWC9ocltr03HhKF7W8MYgzuHts/gFYOQLyEZbBL773mACO7ifOvWR6/WrP1CoBFH4tjm6oSaWN1cHL78nK/FL1/+khJTf373/eD4gAwcENwEon3fHfDhO+qBhBA6gHFo3u8oy24d9m6EMenWPzohSPBzkvquiB3ghu7aA7+fAbl3VOGawRBbVrOF/d6GGCGuva3s6y33ciWwu/uaENqgD9dh/OTWcnIg/cK2S2VtLS+bkU1tyHgv+W4xVvJuEVa0Q+h1PUq5nkaef6lX2KhUmsakbLIVoBSfjVFeid259g5yMuBOcyNNnzNUUikbwWzo4TRbhZ2XNJylXWi9l0rwfpnBKF6NukMegBhWJ/hSLRMmW2qWFEEVWS2yDptXEji2xfxLWoFd60u5DnF7bpIt12m5LA69iAQfh9vJUVxP51CLuN/g3GCRG5QlVSxCmSulGW16jbZ7UUO2oijGayCbfp3Les9xu1If6Q1wbeuylOu2bt5kD/KVXOkji3Sl2dCVHy0Qq6Rt4+zUrOT4mtxUTyGxJ7KGoLlWU3HWnr+SBm3EzjV6XkaEK79bn6sslXO5mcxGHNLltWEbG6wz3+UhZwaKUQgyslqsm+Bs1ZJE6n0ZIS1BEnmcKC7z+XwXU+mSkH2gHqVburxlV5G9kMKOciKkC7Hda7eYcOweDhU/jYMXiJSLH0cgy8nkrn5QWISm6KC1RIQSlNEom92CKIGniqg7/OlYyAOWzO/la66txmOZ9hBIobQgmGups0IhRqOMhbcKy2NdwzrNdy4QoygKfkUHrWVGcluXRvl8Mkr5r5hP3RYefwpPFdFmbn/MWn/3tXgv23UteHeT18FH8JOGnOSed2lLC+hBcdXk4mnJ1bu5nsTU5oS+hTBuCzSKjYZSNxCXEC/CEte+96JRy4w8PQwm9yvHM3EatsDzoiD5IsW42EgXJacDvyGr5NhU0S09rxsHrR0B471vtPRq5csBfOpEaKExHAiGjYMzWf1pOzmnMzr5Qogt38E+++SCNFDyZc6lyKlSp7JVo8Qseg8NK0KCQxNl/mddgeTfhzMakPaeRAMZikaGcLc55X2nwX3FCfAq1+TBXNE6yJm8ETO79V/VLLPsFaOVMR/gNdpPsDKqRobWX2lGiaa+Wtpl+oU8rzrhIL2lgEq6wVMupeUN3o4OzNPXqNzf/h7BmFEggeTFmf0FaaCsHNi8FF8Bu7snN7aHzRfmwED/Hq7Hp0uzVQJ7cWjEt/unp/LsrpklThrxoW/WqhdvwopjN2mZFx87javOAXtPM74gdT/V4gFLNQlbPp3g3KAwTZpsk3JVozh6zHbmi58eKXLGEUGlGAucQi+6VrEkIwYv8/B6LCc1gtBJiDQ+wSYMXv8nEY53PI+aIrcrVmGVPRNNqg/dwc1cmJ+fF2zBZ6/hqV54pkBBbjhiwZBBkr1GAaP+eU1cNV+yLHeu7csrysLuGf0VzW4G+BHLMHhOvBtCjRXo/j0khzaD7iPzUoezjEM8lJx/BpUhsaPRDHIduStGBbwytL3veyvfmvYplWW3TXLPg1xHuvUAAyPJbIRIMrfN+DSC5+wn56X00nrCNeaN/YvwVhRcSZcXrVmjk98XS4XOA3gtoFLcrL0Yu8XzzIAQoXhzCaKp+X+pXCsZ10xUlc/aaBaDrtdybVxXS4RgYhc7GS5rNLAkyjQb+4IjMYSrw09FLPeVe1vPQT7yBQc6dTuhf721TmguAnSAi+qoMZtZWAo1GcqnSMimDnolA9uEEMEe3MVeyBLq9AhNDS7F8mxpLjK0PJmbtYL6GLj89pxVsH8gEXXXdVtkk0wyGUo30m3QADIW0ebs1AR3y2AGgrun6wS36gKql80VFlg5RLCz4GMmkQx4XBzlSEfKK+v0nQUkJJozyck9sloAez+eQUz9bICtZwNl7cDXnymi+sbIGF+Umm1zY2GBNsAHoRMxCoESCu63dsa9VnVsBQY88dK0qatY0CV2DkUp+MZeG+BCiTglt4KfgcStnPtJq9pPV5LXfAzoDGDbriPzSU9t5fQRZmNp3yKrmD7KbDa//+rP1HzcCqUW9Hx3QVdFfuCrVWtgyaS7rwMoQvNlBldvHuvbls7g1WCsuXD7nJD+W0psR/UbLoDDhyZ87253TugrnFO9O/IeV1YBnDGGm9HSoXQXlxV2nNLkJzkG2R5iHIE+XKKH2XykFgbSLtFjg90JsOJQxH3W7maRDRI6G4wgj98nWZytvfOiK6QeITrSD01U0xVNgSko1/2P9xElukeAn85ALuegX3X8czwpue+bFuGgvQsegrRKNnkqU3V9IrU2Xk6ElOjml/5vvJryhm5uE0h6gmbpYn0WarEAjXjo2CKpl/LlHNMi5bmEs8XhRqKe0a1U5g+mH9HuVJqQOEKFMA7kAYD+RBgt3tFGnVnVl7O11G7ljsPgVraVop2RtlCibsQAtCjt6mPvBvc7OR2XO3PRgQVhiKcoEe0uM0r2hwh+IZ5A4OcrSnuL6RSO7ZtekIhq7yHhBp1NB/biOpgfh5zx8x8j9unat8FECcN6bvz9VN6EJD1w7eEEyD0Mj/b2BZQey1yN43ANjdDlbGOSssnhnphbaOKsrCfT0IlNQioZPSqPdjfbk2I2uRBZiaoKbszDuwETxUSxK/Mf1oap4yNKOFE+IM+t6oFAEmgBI2IDSgRYsQvh7fS6vpYqS+XSqBmwJEYLChmtJiQQTVQ/zNGmn9ehaa9mhvv9dvv6ZabWZts0MVrjj3fUIcPzcagMhHn4VtRd/jd+/B2ZVw7b2Fy3RWjyHu6OJ8n3s4n6MQr9uXvrLKybbrq2EDR4/91TNKig5RNrXBK6sy+eoweQDwy3dVZpYtNtWzoCkXtI8g1INsHHGBos4ERuh8Nko6TgrIH/YKT2cAQSXybkDGmGYv5IWJz/L9rUQQszPRmDkk2M/9Nk8ZdUnKnKS3RKSD0Nyg2Sxgbh2H7lbGnC8D++DyybVTKCcmlO5xJFl9bzKYhdwIoqcM/1dZIyVA/t/aVUmCUiO41UxxP2/gfAcQvCYWQw8C53lAtFUeYLHm1eAHFThru+ORWqd7Vfj/oIGg3A81jGHWRbiOwuZ+X6Ckt2Y7dGjuU2rcJIia2UAo3Enngl8eNvlxlG82C1BDRZ4KWJXkYbCDCGhIjiULpU9tkrpVhUM16fV0cLiHjtEXwtAIDKfbUff3hqPJxx7mu0SpcAAHB78eN31Muemjd0gYXZkxh0eQTKsQACfIM4PZUWXP3CMUMaPYrJdIy3RCnwm/MLAeC2pK+lfggmuWomMQgyIQAz2iA4ILc5piV+oSJUoCUOCADTnG59mOYK16cilC80Vd2OAywzYczoryEmEGDJYhpWrRXCEAnF17iKh9UK3QxDbnGfrBPtTAtDu80vxaR6yPmw2qkgApB8qxVDMtgPAHyQgRca4FbrbpdZ1wOcVfgNj+Aj6XTFy0XOwB14INwR3id/m5RXCodgbtrdVLXQpH4Plxc/dQhEGTglaJGQLV6+hAW0+AoGFRwAL46g8yElJ8HHkh6/+TB4d/sSSNvrS1TUrC+JOOfadNpyHwgB1AZbS6Bj8CVCqn98ScD2iy8Zsn3kSwG1632poLTGlwa1WnzpoJenZEDg/nJmxgV2mjAmYlyTWRGjYqKc+s2ymhYRM25GswnjJmxHytitNNvfaTVxaBv0zbak5eeKZv36xCw3Zg20Mpgoo91pph3kykQKnUrsQH7IbCsl/pNmGMnlYiBqWmygzKZKrXfGjKoyMXF9DpLzaOB2q7IzSkdHmV7C2ICAUq0fl4JieKugDiGYOEAxpap1vkXYzdrmMyo233fSKtOBYa6qdaJToH0A/TW43Ok1XQwO6xcdmqcsDzANHbWaujrY+UGx3s7leu9qNK7TyRlmKve3rwZL8+wNHkwJhP/PjzIAoz2VH2EoASXC/pJA5N90WIgNVXEQF6pLQakoDaWjDBCX2R+yZMuRm6Rl8pKW318KFCpKVnG1lSSPh6+UoI8oKlOuQmXKhESqVKvpQOI0SUjJ0lbbJ/4mV0dBmS4VNQ1t+nT0DIxMcOaMESxIVHjW7smmnl2Dxsw5+qw7qs/Jxa25c7XU4D+AtvFqhcARrU07nw6dOfP3py6MboFcBYV6o+f0iOgV1VdL/QbyNGhIzHAfa23EqDHjJqKbNGXajNnOtzxfK8xZWUer+tQ/Vpu3ps7WWme9DfnbaJPNtthqm+0x7bDTLgsF2m2PvfbZ70DBDvZ5HznsSFkegcWio455ttjHJHIRhUqjM5gsNofL4wuEIrFEKpMrlCrtTilI1dHV0zcwNDI2MTUzt7C0guVHgMJ393cIyxTueaA2U3MfO2rrcOzdgppFzfd20vibCGL/e4qiMOjxTtAffdEDJqGNci6FOHVUi0ZS9kCHsF4ngxahYDGmvsXgWNVJZ8GRh/dEfDkDs4aLN9RJd9YOnrtJj9DpSWOX9prWtpM+UR8phB5IOeOKGg4S15AeL8Rhujg+EMvFWgZIqig1E3ncu51JUjrQ/W0rrU1j8rOcFKfL5Bxrf8aXJPP3iaX1i0Ihw6kKYDnce9AfzTHTFfu6lvhQPZR5M4rZuhwqPFgFV0KlVaKQlulXgkirmUDaoala1JyTN3TqfoWaNOMRN/2iLoKnb6XQraK3Wg4hQ7jMl9CXWSd6a5iEbGnlRCSghYiJiYg4qcaMyMlETGBi1o0ylisERGjxGPQSDimWTiUoQaGKMnzs9h6MKm+f8RNGov+fXlcDk9YnTRa2LK8TLnGZ008ikV7Zc+z6JmtbqhfmXHENXoPXxwy5Oo+gY4XBGfo0xu1LT3KPcdlY0CXQigBACAYBBEBwgvMRP/Me5xP6e6wMPqEQaEUF/7yfJXYxebBAYljzdjbyeTFusYyVmX1Ya8dwgc/MvjOZWsRpiyKdvjCHM1ZS6232xGr+PZkqh0XP0ej2eAf7ZPn93+ckEiEFNfwpMlPBEfyV67F8ss2EiBE7fuj6fq3NhFEGJcjoBxj9jZvRG7RWB2JkzXGa0k2KmyAMyiBFVx3kFV+F3BrwwJOs/obXzjaMTPJNjD2pwjDZBQAAAA==) format('woff2');\r
      unicode-range: U+0100-02BA, U+02BD-02C5, U+02C7-02CC, U+02CE-02D7, U+02DD-02FF, U+0304, U+0308, U+0329, U+1D00-1DBF, U+1E00-1E9F, U+1EF2-1EFF, U+2020, U+20A0-20AB, U+20AD-20C0, U+2113, U+2C60-2C7F, U+A720-A7FF; }\r
    /* latin */\r
    @font-face { font-family: 'JetBrains Mono'; font-style: normal; font-weight: 400 800; font-display: swap;\r
      src: url(data:font/woff2;base64,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) format('woff2');\r
      unicode-range: U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0304, U+0308, U+0329, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD; }\r
  </style>\r
  <style>\r
    /* ==========================================================\r
       THEME VARIABLES — switch by toggling [data-theme] on <html>\r
       ========================================================== */\r
    :root,\r
    [data-theme="dark"] {\r
      --bg: #020617;\r
      --grid: #1e293b;\r
      --text: #ffffff;\r
      --text-muted: #94a3b8;\r
      --text-dim: #475569;\r
      /* UI chrome and menu hints need more contrast than SVG .t-dim accents */\r
      --text-faint: #7d8da1;\r
\r
      --panel: rgba(15, 23, 42, 0.5);\r
      --panel-border: #1e293b;\r
      --lane-fill: rgba(15, 23, 42, 0.22);\r
      --lane-stroke: #334155;\r
\r
      --arrow: #64748b;\r
      --arrow-emphasis: #34d399;\r
\r
      /* Opaque mask color used behind semi-transparent component fills\r
         so the arrows drawn underneath are properly hidden. */\r
      --mask: #0f172a;\r
\r
      --frontend-fill:    rgba(8, 51, 68, 0.4);\r
      --frontend-stroke:  #22d3ee;\r
      --backend-fill:     rgba(6, 78, 59, 0.4);\r
      --backend-stroke:   #34d399;\r
      --database-fill:    rgba(76, 29, 149, 0.4);\r
      --database-stroke:  #a78bfa;\r
      --cloud-fill:       rgba(120, 53, 15, 0.3);\r
      --cloud-stroke:     #fbbf24;\r
      --security-fill:    rgba(136, 19, 55, 0.4);\r
      --security-stroke:  #fb7185;\r
      --messagebus-fill:  rgba(251, 146, 60, 0.3);\r
      --messagebus-stroke:#fb923c;\r
      --external-fill:    rgba(30, 41, 59, 0.5);\r
      --external-stroke:  #94a3b8;\r
\r
      --toolbar-bg:       rgba(15, 23, 42, 0.8);\r
      --toolbar-border:   #334155;\r
      --toolbar-text:     #e2e8f0;\r
      --toolbar-hover:    rgba(15, 23, 42, 0.95);\r
      --toolbar-menu-bg:  #0f172a;\r
    }\r
\r
    [data-theme="light"] {\r
      --bg: #f8fafc;\r
      --grid: #e2e8f0;\r
      --text: #0f172a;\r
      --text-muted: #64748b;\r
      --text-dim: #94a3b8;\r
      --text-faint: #64748b;\r
\r
      --panel: #ffffff;\r
      --panel-border: #e2e8f0;\r
      --lane-fill: rgba(248, 250, 252, 0.65);\r
      --lane-stroke: #cbd5e1;\r
\r
      --arrow: #94a3b8;\r
      --arrow-emphasis: #059669;\r
\r
      --mask: #ffffff;\r
\r
      --frontend-fill:    rgba(34, 211, 238, 0.15);\r
      --frontend-stroke:  #0891b2;\r
      --backend-fill:     rgba(52, 211, 153, 0.18);\r
      --backend-stroke:   #059669;\r
      --database-fill:    rgba(167, 139, 250, 0.2);\r
      --database-stroke:  #7c3aed;\r
      --cloud-fill:       rgba(251, 191, 36, 0.18);\r
      --cloud-stroke:     #d97706;\r
      --security-fill:    rgba(251, 113, 133, 0.15);\r
      --security-stroke:  #e11d48;\r
      --messagebus-fill:  rgba(251, 146, 60, 0.15);\r
      --messagebus-stroke:#ea580c;\r
      --external-fill:    rgba(148, 163, 184, 0.18);\r
      --external-stroke:  #64748b;\r
\r
      --toolbar-bg:       rgba(255, 255, 255, 0.92);\r
      --toolbar-border:   #cbd5e1;\r
      --toolbar-text:     #334155;\r
      --toolbar-hover:    #ffffff;\r
      --toolbar-menu-bg:  #ffffff;\r
    }\r
\r
    /* ==========================================================\r
       SIGNAL FLOW — an opt-in, motion-forward visual preset.\r
       The variables also target a standalone exported SVG, whose\r
       root carries data-preset and data-theme directly.\r
       ========================================================== */\r
    [data-preset="signal-flow"][data-theme="dark"] {\r
      --bg: #030711;\r
      --grid: #15233a;\r
      --panel: rgba(6, 14, 28, 0.78);\r
      --panel-border: #1d3350;\r
      --lane-fill: rgba(9, 22, 40, 0.5);\r
      --lane-stroke: #2c4564;\r
      --text: #f5fbff;\r
      --text-muted: #9eb0c7;\r
      --text-dim: #52667f;\r
      --text-faint: #7890ad;\r
      --mask: #07101e;\r
      --frontend-fill: rgba(6, 182, 212, 0.14);\r
      --frontend-stroke: #67e8f9;\r
      --backend-fill: rgba(16, 185, 129, 0.14);\r
      --backend-stroke: #5eead4;\r
      --database-fill: rgba(139, 92, 246, 0.16);\r
      --database-stroke: #c4b5fd;\r
      --cloud-fill: rgba(245, 158, 11, 0.13);\r
      --cloud-stroke: #fcd34d;\r
      --security-fill: rgba(244, 63, 94, 0.13);\r
      --security-stroke: #fda4af;\r
      --messagebus-fill: rgba(249, 115, 22, 0.13);\r
      --messagebus-stroke: #fdba74;\r
      --external-fill: rgba(71, 85, 105, 0.24);\r
      --external-stroke: #a5b4c7;\r
      --arrow: #7890ad;\r
      --arrow-emphasis: #2dd4bf;\r
      --toolbar-bg: rgba(7, 16, 30, 0.86);\r
      --toolbar-border: #29415f;\r
      --toolbar-menu-bg: #07101e;\r
    }\r
\r
    [data-preset="signal-flow"][data-theme="light"] {\r
      --bg: #f4f9fc;\r
      --grid: #d4e5ee;\r
      --panel: rgba(255, 255, 255, 0.82);\r
      --panel-border: #bfd5e2;\r
      --lane-fill: rgba(232, 243, 248, 0.62);\r
      --lane-stroke: #a9c5d5;\r
      --text: #102638;\r
      --text-muted: #587287;\r
      --text-dim: #8aa2b4;\r
      --text-faint: #668397;\r
      --mask: #ffffff;\r
      --frontend-fill: rgba(6, 182, 212, 0.09);\r
      --frontend-stroke: #0789a1;\r
      --backend-fill: rgba(5, 150, 105, 0.09);\r
      --backend-stroke: #087f69;\r
      --database-fill: rgba(124, 58, 237, 0.09);\r
      --database-stroke: #7254c7;\r
      --cloud-fill: rgba(217, 119, 6, 0.08);\r
      --cloud-stroke: #b9670b;\r
      --security-fill: rgba(225, 29, 72, 0.08);\r
      --security-stroke: #c53a59;\r
      --messagebus-fill: rgba(234, 88, 12, 0.08);\r
      --messagebus-stroke: #c65f27;\r
      --external-fill: rgba(100, 116, 139, 0.1);\r
      --external-stroke: #607a8c;\r
      --arrow: #7b97aa;\r
      --arrow-emphasis: #0d9488;\r
    }\r
\r
    /* ==========================================================\r
       BLUEPRINT — a review-first drafting preset for deployment,\r
       infrastructure, and technical design documentation. It keeps\r
       the same semantic palette and geometry while trading glow for\r
       precise grid contrast, squared materials, and drafting marks.\r
       ========================================================== */\r
    [data-preset="blueprint"][data-theme="dark"] {\r
      --bg: #06131f;\r
      --grid: #17425a;\r
      --panel: rgba(7, 27, 43, 0.9);\r
      --panel-border: #27627f;\r
      --lane-fill: rgba(10, 43, 66, 0.36);\r
      --lane-stroke: #34799a;\r
      --text: #e3f6ff;\r
      --text-muted: #91b8ca;\r
      --text-dim: #557e92;\r
      --text-faint: #739caf;\r
      --mask: #0a2031;\r
      --frontend-fill: rgba(26, 157, 193, 0.14);\r
      --frontend-stroke: #66d9ef;\r
      --backend-fill: rgba(31, 155, 124, 0.13);\r
      --backend-stroke: #69dfbd;\r
      --database-fill: rgba(120, 105, 196, 0.14);\r
      --database-stroke: #b4a8ff;\r
      --cloud-fill: rgba(197, 145, 43, 0.13);\r
      --cloud-stroke: #ffd166;\r
      --security-fill: rgba(199, 76, 104, 0.13);\r
      --security-stroke: #ff8da1;\r
      --messagebus-fill: rgba(207, 112, 49, 0.13);\r
      --messagebus-stroke: #ffad66;\r
      --external-fill: rgba(84, 119, 139, 0.18);\r
      --external-stroke: #a7cad9;\r
      --arrow: #78a3b7;\r
      --arrow-emphasis: #64dfc1;\r
      --toolbar-bg: rgba(7, 28, 45, 0.92);\r
      --toolbar-border: #34799a;\r
      --toolbar-text: #d8f3ff;\r
      --toolbar-hover: rgba(18, 58, 83, 0.95);\r
      --toolbar-menu-bg: #0a2031;\r
    }\r
\r
    [data-preset="blueprint"][data-theme="light"] {\r
      --bg: #edf7fa;\r
      --grid: #b5d5e1;\r
      --panel: rgba(249, 253, 255, 0.94);\r
      --panel-border: #78aabd;\r
      --lane-fill: rgba(210, 232, 240, 0.42);\r
      --lane-stroke: #83b2c4;\r
      --text: #123344;\r
      --text-muted: #4e7486;\r
      --text-dim: #86a6b4;\r
      --text-faint: #668c9d;\r
      --mask: #f9fdff;\r
      --frontend-fill: rgba(8, 145, 178, 0.08);\r
      --frontend-stroke: #087f9c;\r
      --backend-fill: rgba(5, 128, 101, 0.08);\r
      --backend-stroke: #08755f;\r
      --database-fill: rgba(100, 75, 180, 0.08);\r
      --database-stroke: #6757a8;\r
      --cloud-fill: rgba(181, 120, 15, 0.08);\r
      --cloud-stroke: #a86609;\r
      --security-fill: rgba(190, 48, 80, 0.07);\r
      --security-stroke: #b32f50;\r
      --messagebus-fill: rgba(196, 81, 22, 0.07);\r
      --messagebus-stroke: #b65120;\r
      --external-fill: rgba(79, 112, 128, 0.08);\r
      --external-stroke: #506f7e;\r
      --arrow: #6d93a5;\r
      --arrow-emphasis: #087f69;\r
      --toolbar-bg: rgba(247, 252, 254, 0.94);\r
      --toolbar-border: #8ab5c5;\r
      --toolbar-text: #294f61;\r
      --toolbar-hover: #ffffff;\r
      --toolbar-menu-bg: #f9fdff;\r
    }\r
\r
    /* ==========================================================\r
       EDITORIAL — a warm, publication-minded preset for design\r
       reviews, launch notes, and documentation. The diagram keeps\r
       the same semantic palette and exact geometry, but trades\r
       software chrome for paper, ink, ruled structure, and one\r
       restrained vermilion accent.\r
       ========================================================== */\r
    [data-preset="editorial"][data-theme="dark"] {\r
      --bg: #181611;\r
      --grid: #39342a;\r
      --panel: rgba(35, 31, 24, 0.96);\r
      --panel-border: #625a4a;\r
      --lane-fill: rgba(52, 46, 35, 0.46);\r
      --lane-stroke: #726957;\r
      --text: #f4eddf;\r
      --text-muted: #b9ae9b;\r
      --text-dim: #776e60;\r
      --text-faint: #9d917e;\r
      --mask: #231f18;\r
      --frontend-fill: rgba(43, 133, 142, 0.16);\r
      --frontend-stroke: #7fc6c7;\r
      --backend-fill: rgba(63, 132, 92, 0.16);\r
      --backend-stroke: #8fc29e;\r
      --database-fill: rgba(117, 91, 141, 0.17);\r
      --database-stroke: #c0a4d0;\r
      --cloud-fill: rgba(170, 119, 49, 0.16);\r
      --cloud-stroke: #d8ad68;\r
      --security-fill: rgba(157, 69, 65, 0.17);\r
      --security-stroke: #df9085;\r
      --messagebus-fill: rgba(174, 79, 42, 0.16);\r
      --messagebus-stroke: #df946f;\r
      --external-fill: rgba(126, 115, 96, 0.18);\r
      --external-stroke: #b8ad99;\r
      --arrow: #948978;\r
      --arrow-emphasis: #dd6b3d;\r
      --toolbar-bg: rgba(35, 31, 24, 0.92);\r
      --toolbar-border: #625a4a;\r
      --toolbar-text: #eee5d5;\r
      --toolbar-hover: #302a20;\r
      --toolbar-menu-bg: #231f18;\r
    }\r
\r
    [data-preset="editorial"][data-theme="light"] {\r
      --bg: #f2eee5;\r
      --grid: #d8d0c2;\r
      --panel: rgba(251, 248, 241, 0.97);\r
      --panel-border: #c4b9a6;\r
      --lane-fill: rgba(229, 221, 207, 0.42);\r
      --lane-stroke: #b8aa94;\r
      --text: #242018;\r
      --text-muted: #6f6658;\r
      --text-dim: #a09788;\r
      --text-faint: #817767;\r
      --mask: #fbf8f1;\r
      --frontend-fill: rgba(31, 117, 126, 0.09);\r
      --frontend-stroke: #287e84;\r
      --backend-fill: rgba(42, 119, 75, 0.09);\r
      --backend-stroke: #397b53;\r
      --database-fill: rgba(105, 75, 130, 0.09);\r
      --database-stroke: #765d86;\r
      --cloud-fill: rgba(157, 103, 31, 0.1);\r
      --cloud-stroke: #9a671f;\r
      --security-fill: rgba(153, 58, 52, 0.09);\r
      --security-stroke: #9e463f;\r
      --messagebus-fill: rgba(182, 70, 27, 0.09);\r
      --messagebus-stroke: #ad4b25;\r
      --external-fill: rgba(101, 91, 75, 0.09);\r
      --external-stroke: #746b5e;\r
      --arrow: #8a806f;\r
      --arrow-emphasis: #bb4c23;\r
      --toolbar-bg: rgba(251, 248, 241, 0.94);\r
      --toolbar-border: #c4b9a6;\r
      --toolbar-text: #40392f;\r
      --toolbar-hover: #fffdf8;\r
      --toolbar-menu-bg: #fbf8f1;\r
    }\r
\r
    * { margin: 0; padding: 0; box-sizing: border-box; }\r
\r
    body {\r
      font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Consolas, 'DejaVu Sans Mono', 'Liberation Mono', 'Noto Sans Mono CJK SC', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', monospace;\r
      background: var(--bg);\r
      min-height: 100vh;\r
      padding: 2rem;\r
      color: var(--text);\r
      transition: background 0.2s ease, color 0.2s ease;\r
    }\r
\r
    html[data-preset="signal-flow"] body {\r
      background-image:\r
        radial-gradient(circle at 18% -8%, rgba(34, 211, 238, 0.14), transparent 34rem),\r
        radial-gradient(circle at 92% 18%, rgba(139, 92, 246, 0.12), transparent 30rem);\r
      background-attachment: fixed;\r
    }\r
    html[data-preset="signal-flow"][data-theme="light"] body {\r
      background-image:\r
        radial-gradient(circle at 18% -8%, rgba(6, 182, 212, 0.12), transparent 34rem),\r
        radial-gradient(circle at 92% 18%, rgba(139, 92, 246, 0.08), transparent 30rem);\r
    }\r
    html[data-preset="blueprint"] body {\r
      background-image:\r
        linear-gradient(var(--grid) 1px, transparent 1px),\r
        linear-gradient(90deg, var(--grid) 1px, transparent 1px);\r
      background-size: 32px 32px;\r
      background-position: -1px -1px;\r
      background-attachment: fixed;\r
    }\r
    html[data-preset="editorial"] body {\r
      background-image:\r
        linear-gradient(90deg, transparent 0, transparent 5.4rem, color-mix(in srgb, var(--security-stroke) 18%, transparent) 5.4rem, color-mix(in srgb, var(--security-stroke) 18%, transparent) calc(5.4rem + 1px), transparent calc(5.4rem + 1px)),\r
        repeating-linear-gradient(0deg, transparent 0, transparent 31px, color-mix(in srgb, var(--grid) 36%, transparent) 31px, color-mix(in srgb, var(--grid) 36%, transparent) 32px);\r
      background-attachment: fixed;\r
    }\r
\r
    /* Gallery/embed mode keeps the generated artifact as the source of truth\r
       while presenting only its diagram surface inside a proof card. */\r
    html[data-embed="true"] body {\r
      min-height: 0;\r
      padding: 0;\r
      overflow: hidden;\r
      background: var(--bg);\r
      background-image: none;\r
    }\r
    html[data-embed="true"] .toolbar,\r
    html[data-embed="true"] .header,\r
    html[data-embed="true"] .cards,\r
    html[data-embed="true"] .diagram-nav,\r
    html[data-embed="true"] .overview-map,\r
    html[data-embed="true"] .focus-chip,\r
    html[data-embed="true"] .route-probe,\r
    html[data-embed="true"] .semantic-lens,\r
    html[data-embed="true"] .diagram-guide,\r
    html[data-embed="true"] .node-finder,\r
    html[data-embed="true"] .guided-views { display: none !important; }\r
    html[data-embed="true"] .container { max-width: none; }\r
    html[data-embed="true"] .diagram-container {\r
      padding: 0.5rem;\r
      border: 0;\r
      border-radius: 0;\r
      box-shadow: none;\r
    }\r
    html[data-embed="true"] .diagram-container svg { min-width: 0; }\r
\r
    /* Share Chapter Cue lives in the HTML viewer layer, not inside the SVG.\r
       It gives one-shot embeds a title, authored note, truthful stop order,\r
       and lifecycle state while canonical diagram geometry stays untouched. */\r
    .share-chapter-cue { display: none; }\r
    html[data-embed="true"][data-share-playback="true"] .share-chapter-cue:not([hidden]),\r
    html[data-embed="true"][data-share-moment="true"] .share-chapter-cue:not([hidden]) {\r
      position: absolute;\r
      z-index: 18;\r
      top: 0.85rem;\r
      left: 50%;\r
      display: grid;\r
      grid-template-columns: auto minmax(9rem, 13.5rem) minmax(0, 1fr);\r
      align-items: center;\r
      gap: 0.45rem 0.85rem;\r
      width: min(52rem, calc(100% - 1.5rem));\r
      min-height: 3.35rem;\r
      padding: 0.55rem 0.75rem 0.65rem;\r
      overflow: hidden;\r
      border: 1px solid color-mix(in srgb, var(--frontend-stroke) 42%, var(--toolbar-border));\r
      border-radius: 0.75rem;\r
      background:\r
        linear-gradient(115deg, color-mix(in srgb, var(--frontend-fill) 52%, transparent), transparent 45%),\r
        color-mix(in srgb, var(--toolbar-menu-bg) 92%, transparent);\r
      color: var(--toolbar-text);\r
      box-shadow: 0 14px 42px rgba(0, 0, 0, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.045);\r
      backdrop-filter: blur(16px);\r
      pointer-events: none;\r
      animation: archify-share-cue-enter 280ms cubic-bezier(0.22, 1, 0.36, 1) both;\r
    }\r
    html[data-preset="blueprint"] .share-chapter-cue {\r
      border-radius: 0.2rem;\r
      background:\r
        linear-gradient(90deg, color-mix(in srgb, var(--frontend-fill) 46%, transparent), transparent 36%),\r
        var(--toolbar-menu-bg);\r
      box-shadow: 0 10px 28px rgba(0, 0, 0, 0.2);\r
      backdrop-filter: none;\r
    }\r
    html[data-preset="editorial"] .share-chapter-cue {\r
      border-color: var(--panel-border);\r
      background:\r
        linear-gradient(90deg, color-mix(in srgb, var(--security-fill) 58%, transparent), transparent 42%),\r
        var(--toolbar-menu-bg);\r
      box-shadow: 0 10px 30px color-mix(in srgb, #000 18%, transparent);\r
      backdrop-filter: none;\r
    }\r
    html[data-preset="editorial"] .share-chapter-state { color: var(--arrow-emphasis); }\r
    html[data-preset="editorial"] .share-chapter-state::before {\r
      border-radius: 0;\r
      box-shadow: none;\r
      transform: rotate(45deg) scale(0.8);\r
    }\r
    .share-chapter-index {\r
      display: grid;\r
      gap: 0.12rem;\r
      min-width: 5rem;\r
      padding-right: 0.75rem;\r
      border-right: 1px solid var(--toolbar-border);\r
    }\r
    .share-chapter-state {\r
      display: inline-flex;\r
      align-items: center;\r
      gap: 0.36rem;\r
      color: var(--frontend-stroke);\r
      font-size: 0.5rem;\r
      font-weight: 800;\r
      letter-spacing: 0.14em;\r
      text-transform: uppercase;\r
    }\r
    .share-chapter-state::before {\r
      width: 0.38rem;\r
      height: 0.38rem;\r
      border-radius: 50%;\r
      background: currentColor;\r
      box-shadow: 0 0 10px currentColor;\r
      content: '';\r
    }\r
    .share-chapter-cue[data-state="playing"] .share-chapter-state::before {\r
      animation: archify-share-cue-pulse 1.15s ease-in-out infinite;\r
    }\r
    .share-chapter-count {\r
      color: var(--text-faint);\r
      font-size: 0.5rem;\r
      font-weight: 700;\r
      letter-spacing: 0.08em;\r
      text-transform: uppercase;\r
    }\r
    .share-chapter-copy { min-width: 0; }\r
    .share-chapter-copy strong,\r
    .share-chapter-copy small,\r
    .share-chapter-route {\r
      display: block;\r
      overflow: hidden;\r
      text-overflow: ellipsis;\r
      white-space: nowrap;\r
    }\r
    .share-chapter-copy strong {\r
      color: var(--toolbar-text);\r
      font-size: 0.6875rem;\r
      line-height: 1.35;\r
    }\r
    .share-chapter-copy small {\r
      margin-top: 0.08rem;\r
      color: var(--text-muted);\r
      font-size: 0.5rem;\r
      line-height: 1.35;\r
    }\r
    .share-chapter-route {\r
      color: color-mix(in srgb, var(--frontend-stroke) 76%, var(--text-muted));\r
      font-size: 0.5625rem;\r
      font-weight: 650;\r
      letter-spacing: 0.015em;\r
      text-align: right;\r
    }\r
    .share-chapter-progress {\r
      position: absolute;\r
      right: 0;\r
      bottom: 0;\r
      left: 0;\r
      height: 2px;\r
      overflow: hidden;\r
      background: color-mix(in srgb, var(--toolbar-border) 72%, transparent);\r
    }\r
    .share-chapter-progress span {\r
      display: block;\r
      width: 100%;\r
      height: 100%;\r
      background: linear-gradient(90deg, var(--frontend-stroke), var(--database-stroke));\r
      box-shadow: 0 0 12px var(--frontend-stroke);\r
      transform: scaleX(0);\r
      transform-origin: left center;\r
    }\r
\r
    /* Presentation Stage is a viewer-only layer: it gives the live diagram\r
       the viewport while keeping guided views, theme, focus, and exports real.\r
       Embed mode wins when both query parameters are present. */\r
    html[data-present="true"]:not([data-embed="true"]) body {\r
      height: 100dvh;\r
      min-height: 0;\r
      padding: 1rem;\r
      overflow: hidden;\r
    }\r
    html[data-present="true"]:not([data-embed="true"]) .container {\r
      display: flex;\r
      flex-direction: column;\r
      gap: 0.75rem;\r
      width: 100%;\r
      max-width: none;\r
      height: calc(100dvh - 2rem);\r
    }\r
    html[data-present="true"]:not([data-embed="true"]) .header {\r
      flex: none;\r
      min-width: 0;\r
      margin: 0;\r
      padding-right: 23rem;\r
    }\r
    html[data-present="true"]:not([data-embed="true"]) .header-row { margin-bottom: 0.25rem; }\r
    html[data-present="true"]:not([data-embed="true"]) .subtitle {\r
      overflow: hidden;\r
      text-overflow: ellipsis;\r
      white-space: nowrap;\r
    }\r
    html[data-present="true"]:not([data-embed="true"]) .guided-views {\r
      flex: none;\r
      margin-bottom: 0;\r
    }\r
    html[data-present="true"]:not([data-embed="true"]) .diagram-container {\r
      display: flex;\r
      flex: 1 1 auto;\r
      align-items: center;\r
      justify-content: center;\r
      min-height: 0;\r
      padding: 0.75rem;\r
      padding-bottom: calc(0.75rem + var(--archify-nav-reserve));\r
    }\r
    html[data-present="true"]:not([data-embed="true"]) .diagram-container > svg {\r
      flex: 1 1 auto;\r
      height: 100%;\r
      min-height: 0;\r
      width: 100%;\r
      min-width: 0;\r
    }\r
    html[data-present="true"]:not([data-embed="true"]) .cards { display: none; }\r
    html[data-present="true"]:not([data-embed="true"]) #btn-present {\r
      border-color: var(--frontend-stroke);\r
      color: var(--frontend-stroke);\r
    }\r
\r
    /* The reader owns only the outer scale. Wide diagrams keep one authored\r
       SVG/viewBox while the runtime chooses a desktop width from the actual\r
       vertical budget. This avoids device-specific files and breakpoint\r
       jumps between a laptop and a tall monitor. */\r
    .container {\r
      width: 100%;\r
      max-width: var(--archify-reader-width, 1440px);\r
      margin: 0 auto;\r
    }\r
    @media (min-width: 768px) and (max-height: 920px) {\r
      .header { margin-bottom: 1rem; }\r
      .diagram-container { padding: 1rem; }\r
      .cards { margin-top: 1rem; }\r
      .card { padding: 1rem; }\r
    }\r
\r
    .header { margin-bottom: 1.5rem; padding-right: 29.5rem; }\r
\r
    html[data-preset="signal-flow"] .header,\r
    html[data-preset="blueprint"] .header,\r
    html[data-preset="editorial"] .header { padding-right: 29.5rem; }\r
\r
    .header-row {\r
      display: flex;\r
      align-items: center;\r
      gap: 1rem;\r
      margin-bottom: 0.5rem;\r
    }\r
\r
    .pulse-dot {\r
      width: 12px;\r
      height: 12px;\r
      background: var(--frontend-stroke);\r
      border-radius: 50%;\r
      animation: none;\r
    }\r
\r
    html[data-motion-capable="true"] .pulse-dot { animation: pulse 2s infinite; }\r
\r
    @keyframes pulse {\r
      0%, 100% { opacity: 1; }\r
      50% { opacity: 0.5; }\r
    }\r
\r
    h1 {\r
      font-size: 1.5rem;\r
      font-weight: 700;\r
      letter-spacing: -0.025em;\r
    }\r
\r
    .subtitle {\r
      color: var(--text-muted);\r
      font-size: 0.875rem;\r
      margin-left: 1.75rem;\r
    }\r
\r
    html[data-preset="signal-flow"] .header-row::after {\r
      content: attr(data-preset-badge-signal-flow);\r
      margin-left: auto;\r
      color: var(--frontend-stroke);\r
      border: 1px solid var(--frontend-stroke);\r
      border-radius: 999px;\r
      padding: 0.28rem 0.6rem;\r
      font-size: 0.625rem;\r
      letter-spacing: 0.12em;\r
      opacity: 0.82;\r
      box-shadow: 0 0 20px rgba(34, 211, 238, 0.12);\r
      white-space: nowrap;\r
    }\r
\r
    html[data-preset="blueprint"] .pulse-dot {\r
      width: 10px;\r
      height: 10px;\r
      border: 1px solid var(--frontend-stroke);\r
      border-radius: 1px;\r
      background: transparent;\r
      box-shadow: inset 0 0 0 2px var(--bg);\r
      transform: rotate(45deg);\r
      animation: none;\r
    }\r
    html[data-preset="blueprint"] .header-row::after {\r
      content: attr(data-preset-badge-blueprint);\r
      margin-left: auto;\r
      padding: 0.28rem 0.55rem;\r
      border-top: 1px solid var(--frontend-stroke);\r
      border-bottom: 1px solid var(--frontend-stroke);\r
      color: var(--frontend-stroke);\r
      font-size: 0.5625rem;\r
      font-weight: 700;\r
      letter-spacing: 0.14em;\r
      white-space: nowrap;\r
    }\r
\r
    html[data-preset="editorial"] h1,\r
    html[data-preset="editorial"] .card h3 {\r
      font-family: Georgia, 'Times New Roman', 'Songti SC', STSong, serif;\r
      letter-spacing: -0.02em;\r
    }\r
    html[data-preset="editorial"] h1 { font-size: 1.72rem; font-weight: 600; }\r
    html[data-preset="editorial"] .pulse-dot {\r
      width: 9px;\r
      height: 9px;\r
      border: 1px solid var(--arrow-emphasis);\r
      border-radius: 0;\r
      background: var(--arrow-emphasis);\r
      box-shadow: 0 0 0 3px color-mix(in srgb, var(--arrow-emphasis) 14%, transparent);\r
      transform: rotate(45deg);\r
      animation: none;\r
    }\r
    html[data-preset="editorial"] .header-row::after {\r
      content: attr(data-preset-badge-editorial);\r
      margin-left: auto;\r
      padding: 0.32rem 0 0.24rem;\r
      border-bottom: 2px solid var(--arrow-emphasis);\r
      color: var(--arrow-emphasis);\r
      font-family: Georgia, 'Times New Roman', serif;\r
      font-size: 0.625rem;\r
      font-style: italic;\r
      font-weight: 600;\r
      letter-spacing: 0.08em;\r
      white-space: nowrap;\r
    }\r
\r
    .diagram-container {\r
      --archify-nav-reserve: 0px;\r
      background: var(--panel);\r
      border-radius: 1rem;\r
      border: 1px solid var(--panel-border);\r
      padding: 1.5rem;\r
      padding-bottom: calc(1.5rem + var(--archify-nav-reserve));\r
      overflow: hidden;\r
      position: relative;\r
    }\r
\r
    html[data-preset="signal-flow"] .diagram-container {\r
      position: relative;\r
      overflow: hidden;\r
      background: linear-gradient(180deg, rgba(8, 20, 38, 0.82), rgba(3, 8, 18, 0.94));\r
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04), 0 28px 80px rgba(0, 0, 0, 0.34);\r
    }\r
    html[data-preset="signal-flow"][data-theme="light"] .diagram-container {\r
      background: linear-gradient(180deg, rgba(255, 255, 255, 0.9), rgba(237, 246, 250, 0.94));\r
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.72), 0 24px 60px rgba(45, 78, 99, 0.12);\r
    }\r
    html[data-preset="blueprint"] .diagram-container {\r
      border-color: var(--panel-border);\r
      border-radius: 0.35rem;\r
      background: var(--panel);\r
      box-shadow:\r
        inset 0 0 0 1px color-mix(in srgb, var(--panel-border) 34%, transparent),\r
        0 18px 48px rgba(0, 0, 0, 0.16);\r
    }\r
    html[data-preset="blueprint"] .diagram-container::after {\r
      content: "";\r
      position: absolute;\r
      z-index: 10;\r
      inset: 0.7rem;\r
      pointer-events: none;\r
      background:\r
        linear-gradient(var(--frontend-stroke), var(--frontend-stroke)) left top / 1.35rem 1px no-repeat,\r
        linear-gradient(var(--frontend-stroke), var(--frontend-stroke)) left top / 1px 1.35rem no-repeat,\r
        linear-gradient(var(--frontend-stroke), var(--frontend-stroke)) right top / 1.35rem 1px no-repeat,\r
        linear-gradient(var(--frontend-stroke), var(--frontend-stroke)) right top / 1px 1.35rem no-repeat,\r
        linear-gradient(var(--frontend-stroke), var(--frontend-stroke)) left bottom / 1.35rem 1px no-repeat,\r
        linear-gradient(var(--frontend-stroke), var(--frontend-stroke)) left bottom / 1px 1.35rem no-repeat,\r
        linear-gradient(var(--frontend-stroke), var(--frontend-stroke)) right bottom / 1.35rem 1px no-repeat,\r
        linear-gradient(var(--frontend-stroke), var(--frontend-stroke)) right bottom / 1px 1.35rem no-repeat;\r
      opacity: 0.58;\r
    }\r
    html[data-preset="editorial"] .diagram-container {\r
      overflow: hidden;\r
      border-color: var(--panel-border);\r
      border-radius: 0.38rem;\r
      background:\r
        linear-gradient(90deg, color-mix(in srgb, var(--security-fill) 58%, transparent), transparent 12%),\r
        var(--panel);\r
      box-shadow:\r
        0 1px 0 color-mix(in srgb, var(--text) 6%, transparent),\r
        0 18px 48px color-mix(in srgb, #000 19%, transparent);\r
    }\r
    html[data-preset="editorial"] .diagram-container::after {\r
      position: absolute;\r
      z-index: 10;\r
      top: 0.72rem;\r
      right: 1.25rem;\r
      padding: 0.2rem 0.52rem;\r
      border: 1px solid var(--panel-border);\r
      background: var(--panel);\r
      color: var(--arrow-emphasis);\r
      content: attr(data-preset-badge-editorial-plate);\r
      font-family: Georgia, 'Times New Roman', serif;\r
      font-size: 0.52rem;\r
      font-style: italic;\r
      font-weight: 600;\r
      letter-spacing: 0.09em;\r
      pointer-events: none;\r
    }\r
    html[data-embed="true"][data-preset="editorial"] .diagram-container::after { display: none; }\r
    html[data-motion-capable="true"][data-preset="signal-flow"][data-ambient-motion="running"] .diagram-container::before {\r
      content: "";\r
      position: absolute;\r
      inset: 0;\r
      pointer-events: none;\r
      background: linear-gradient(115deg, transparent 28%, rgba(103, 232, 249, 0.035) 48%, transparent 68%);\r
      transform: translateX(-70%);\r
      animation: archify-signal-scan 4.8s ease-in-out 1 both;\r
    }\r
\r
    /* Motion Governor gives the reader a real static state and gives the\r
       strongest semantic action the only motion budget. Atmosphere resets to\r
       its authored base instead of freezing mid-cycle. Static artifacts never\r
       start a decorative pulse or scan. */\r
    html:not([data-motion-capable="true"]) svg[data-animation="trace"] [data-animate] {\r
      animation: none !important;\r
    }\r
    html[data-motion="still"] .pulse-dot,\r
    html[data-motion="still"] .diagram-container::before,\r
    html[data-motion="still"] svg[data-animation="trace"] [data-animate],\r
    html[data-motion-owner] .pulse-dot,\r
    html[data-motion-owner] .diagram-container::before,\r
    html[data-motion-owner] svg[data-animation="trace"] [data-animate],\r
    html[data-embed="true"] .pulse-dot,\r
    html[data-embed="true"] .diagram-container::before,\r
    html[data-share-playback="true"] .pulse-dot,\r
    html[data-share-playback="true"] .diagram-container::before,\r
    html[data-document-hidden="true"] .pulse-dot,\r
    html[data-document-hidden="true"] .diagram-container::before,\r
    html[data-document-hidden="true"] svg[data-animation="trace"] [data-animate] {\r
      animation: none !important;\r
    }\r
    html[data-motion="still"] .diagram-container::before,\r
    html[data-motion-owner] .diagram-container::before,\r
    html[data-embed="true"] .diagram-container::before,\r
    html[data-share-playback="true"] .diagram-container::before {\r
      opacity: 0;\r
    }\r
    html[data-motion="still"] .guided-view-progress span,\r
    html[data-motion="still"] .guided-story-caption,\r
    html[data-motion="still"] .story-trail-flow,\r
    html[data-motion="still"] .intent-trace-flow,\r
    html[data-motion="still"] .route-probe-flow,\r
    html[data-motion="still"] .route-journey-flow,\r
    html[data-motion="still"] .semantic-lens-flow,\r
    html[data-motion="still"] .diagram-guide,\r
    html[data-motion="still"] [data-story-step],\r
    html[data-motion="still"] .overview-map-live,\r
    html[data-motion="still"] .guided-view-stop,\r
    html[data-motion="still"] .share-chapter-cue,\r
    html[data-motion="still"] .share-chapter-state::before,\r
    html[data-motion="still"] .share-chapter-progress span,\r
    html[data-document-hidden="true"] .guided-view-progress span,\r
    html[data-document-hidden="true"] .story-trail-flow,\r
    html[data-document-hidden="true"] .intent-trace-flow,\r
    html[data-document-hidden="true"] .route-probe-flow,\r
    html[data-document-hidden="true"] .route-journey-flow,\r
    html[data-document-hidden="true"] .semantic-lens-flow,\r
    html[data-document-hidden="true"] .diagram-guide,\r
    html[data-document-hidden="true"] [data-story-step],\r
    html[data-document-hidden="true"] .overview-map-live,\r
    html[data-document-hidden="true"] .guided-view-stop,\r
    html[data-document-hidden="true"] .share-chapter-cue,\r
    html[data-document-hidden="true"] .share-chapter-state::before,\r
    html[data-document-hidden="true"] .share-chapter-progress span {\r
      animation: none !important;\r
    }\r
    html[data-motion="still"] .guided-view-progress span {\r
      transform: scaleX(1) !important;\r
    }\r
    html[data-motion="still"] svg[data-story-playing="true"] .story-trail-flow {\r
      stroke-dasharray: none;\r
      stroke-dashoffset: 0;\r
      opacity: 0.55;\r
    }\r
    html[data-motion="still"] .intent-trace-flow,\r
    html[data-motion="still"] .route-probe-flow {\r
      stroke-dasharray: none;\r
      stroke-dashoffset: 0;\r
      opacity: 0.72;\r
    }\r
    html[data-motion="still"] .route-journey-overlay,\r
    html[data-document-hidden="true"] .route-journey-overlay { display: none !important; }\r
    html[data-motion="still"] .relationship-pulse-overlay,\r
    html[data-motion="still"] .story-carrier-overlay,\r
    html[data-document-hidden="true"] .story-carrier-overlay { display: none !important; }\r
    html[data-motion="still"] .chapter-handoff-overlay { display: none !important; }\r
    html[data-motion="still"] .chapter-handoff-anchor { animation: none !important; }\r
    html[data-motion="still"] .guided-view-chapter,\r
    html[data-motion="still"] svg [data-node-id],\r
    html[data-motion="still"] svg [data-edge-from],\r
    html[data-motion="still"] svg [data-detail],\r
    html[data-motion="still"] svg [data-detail-anchor],\r
    html[data-motion="still"] svg [data-legend-hit],\r
    html[data-motion="still"] svg {\r
      transition: none !important;\r
    }\r
\r
    svg {\r
      width: 100%;\r
      min-width: min(900px, 100%);\r
      display: block;\r
      transform-origin: 0 0;\r
      transition: transform 0.18s ease;\r
    }\r
\r
    .diagram-container.is-camera-moving svg {\r
      transition: transform 0.42s cubic-bezier(0.22, 1, 0.36, 1);\r
    }\r
    .diagram-container.is-camera-transaction svg { transition: none; }\r
    .diagram-container.is-pannable { cursor: grab; }\r
    .diagram-container.is-panning { cursor: grabbing; user-select: none; }\r
    .diagram-container.is-panning svg { transition: none; }\r
\r
    .diagram-nav {\r
      position: absolute;\r
      right: 1rem;\r
      bottom: 1rem;\r
      z-index: 12;\r
      display: inline-flex;\r
      align-items: center;\r
      max-width: calc(100% - 2rem);\r
      padding: 0.15rem;\r
      gap: 0;\r
      overflow-x: auto;\r
      border: 1px solid color-mix(in srgb, var(--toolbar-border) 48%, transparent);\r
      border-radius: 0.58rem;\r
      background: color-mix(in srgb, var(--toolbar-bg) 82%, transparent);\r
      box-shadow: 0 5px 14px rgba(0, 0, 0, 0.07);\r
      backdrop-filter: blur(10px);\r
      scrollbar-width: none;\r
    }\r
    .diagram-nav::-webkit-scrollbar { display: none; }\r
    .diagram-nav button,\r
    .focus-chip button,\r
    .guided-views button {\r
      border: 0;\r
      background: transparent;\r
      color: var(--toolbar-text);\r
      font: inherit;\r
      cursor: pointer;\r
    }\r
    .diagram-nav button {\r
      min-width: 2rem;\r
      height: 2rem;\r
      padding: 0 0.35rem;\r
      border-radius: 0.35rem;\r
      color: color-mix(in srgb, var(--toolbar-text) 68%, transparent);\r
      font-size: 0.56rem;\r
      font-weight: 600;\r
      letter-spacing: 0.02em;\r
      transition: background 0.15s, color 0.15s;\r
    }\r
    .diagram-nav button:hover,\r
    .diagram-nav button:focus-visible,\r
    .focus-chip button:hover,\r
    .focus-chip button:focus-visible,\r
    .guided-views button:hover,\r
    .guided-views button:focus-visible { background: var(--toolbar-hover); }\r
    .diagram-nav button:focus-visible,\r
    .focus-chip button:focus-visible,\r
    .guided-views button:focus-visible {\r
      outline: 2px solid var(--frontend-stroke);\r
      outline-offset: 1px;\r
    }\r
    .diagram-nav button:disabled { opacity: 0.38; cursor: default; }\r
    .diagram-nav button:disabled:hover { background: transparent; }\r
    .diagram-nav #btn-route-probe,\r
    .diagram-nav #btn-overview-map,\r
    .diagram-nav #btn-semantic-lens {\r
      min-width: auto;\r
      padding-inline: 0.5rem;\r
      color: color-mix(in srgb, var(--toolbar-text) 86%, transparent);\r
      font-weight: 650;\r
    }\r
    .diagram-nav #btn-node-finder,\r
    .diagram-nav [data-view="out"] {\r
      position: relative;\r
      margin-left: 0.25rem;\r
    }\r
    .diagram-nav #btn-node-finder::before,\r
    .diagram-nav [data-view="out"]::before {\r
      position: absolute;\r
      top: 0.4rem;\r
      bottom: 0.4rem;\r
      left: -0.13rem;\r
      width: 1px;\r
      background: color-mix(in srgb, var(--toolbar-border) 62%, transparent);\r
      content: "";\r
      pointer-events: none;\r
    }\r
    .diagram-nav-icon {\r
      display: block;\r
      width: 0.72rem;\r
      height: 0.72rem;\r
      margin: auto;\r
      background: currentColor;\r
      -webkit-mask-position: center;\r
      -webkit-mask-repeat: no-repeat;\r
      -webkit-mask-size: contain;\r
      mask-position: center;\r
      mask-repeat: no-repeat;\r
      mask-size: contain;\r
    }\r
    .diagram-nav-icon.find {\r
      -webkit-mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 20 20'%3E%3Ccircle cx='8.5' cy='8.5' r='4.5' fill='none' stroke='black' stroke-width='1.8'/%3E%3Cpath d='m12 12 4 4' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round'/%3E%3C/svg%3E");\r
      mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 20 20'%3E%3Ccircle cx='8.5' cy='8.5' r='4.5' fill='none' stroke='black' stroke-width='1.8'/%3E%3Cpath d='m12 12 4 4' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round'/%3E%3C/svg%3E");\r
    }\r
    .diagram-nav-icon.guide {\r
      -webkit-mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 20 20'%3E%3Ccircle cx='10' cy='10' r='7' fill='none' stroke='black' stroke-width='1.7'/%3E%3Cpath d='M7.8 7.3a2.4 2.4 0 014.6.9c0 1.8-2.4 2-2.4 3.7M10 14.9h.01' fill='none' stroke='black' stroke-width='1.7' stroke-linecap='round'/%3E%3C/svg%3E");\r
      mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 20 20'%3E%3Ccircle cx='10' cy='10' r='7' fill='none' stroke='black' stroke-width='1.7'/%3E%3Cpath d='M7.8 7.3a2.4 2.4 0 014.6.9c0 1.8-2.4 2-2.4 3.7M10 14.9h.01' fill='none' stroke='black' stroke-width='1.7' stroke-linecap='round'/%3E%3C/svg%3E");\r
    }\r
    .diagram-nav-icon.minus {\r
      -webkit-mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 20 20'%3E%3Cpath d='M5 10h10' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round'/%3E%3C/svg%3E");\r
      mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 20 20'%3E%3Cpath d='M5 10h10' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round'/%3E%3C/svg%3E");\r
    }\r
    .diagram-nav-icon.plus {\r
      -webkit-mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 20 20'%3E%3Cpath d='M10 5v10M5 10h10' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round'/%3E%3C/svg%3E");\r
      mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 20 20'%3E%3Cpath d='M10 5v10M5 10h10' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round'/%3E%3C/svg%3E");\r
    }\r
    .diagram-nav [data-view="reset"] {\r
      display: inline-flex;\r
      align-items: center;\r
      justify-content: center;\r
      gap: 0.2rem;\r
      min-width: 3.1rem;\r
      padding-inline: 0.35rem;\r
    }\r
    .diagram-nav [data-view="reset"][data-detail-visible] {\r
      min-width: 3.8rem;\r
    }\r
    .diagram-nav-detail {\r
      color: color-mix(in srgb, var(--toolbar-text) 52%, transparent);\r
      font-size: 0.44rem;\r
      font-weight: 700;\r
      line-height: 1;\r
      letter-spacing: 0.07em;\r
    }\r
    .diagram-nav-percent {\r
      color: color-mix(in srgb, var(--toolbar-text) 84%, transparent);\r
      font-size: 0.55rem;\r
      font-weight: 650;\r
      line-height: 1;\r
    }\r
    .diagram-container[data-camera-indicator="true"] .diagram-nav-detail,\r
    .diagram-container[data-camera-indicator="true"] .diagram-nav-percent { color: var(--frontend-stroke); }\r
    .diagram-nav #btn-diagram-guide[aria-expanded="true"] {\r
      color: var(--cloud-stroke);\r
      background: var(--toolbar-hover);\r
    }\r
\r
    /* Semantic Radar is a deliberately simplified, viewer-only overview. It\r
       uses authored node bounds and the live camera viewport rather than\r
       cloning the canonical SVG, so IDs, filters, animation, and export state\r
       stay singular and deterministic. */\r
    .overview-map {\r
      position: absolute;\r
      right: 1rem;\r
      bottom: calc(4.15rem + var(--archify-nav-reserve));\r
      z-index: 12;\r
      width: 11.25rem;\r
      overflow: hidden;\r
      border: 1px solid color-mix(in srgb, var(--frontend-stroke) 52%, var(--toolbar-border));\r
      border-radius: 0.78rem;\r
      background: var(--toolbar-menu-bg);\r
      color: var(--toolbar-text);\r
      box-shadow: 0 16px 42px rgba(0, 0, 0, 0.3);\r
      backdrop-filter: blur(16px);\r
      font-size: 0.625rem;\r
    }\r
    .overview-map[hidden] { display: none; }\r
    .overview-map[data-docked="true"] {\r
      position: fixed;\r
      right: var(--archify-radar-right, 1rem);\r
      top: var(--archify-radar-top, 1rem);\r
      bottom: auto;\r
    }\r
    .overview-map[data-docked="true"][data-dock-side="left"] {\r
      right: auto;\r
      left: var(--archify-radar-left, 1rem);\r
    }\r
    html[data-preset="blueprint"] .overview-map { border-radius: 0.28rem; }\r
    .overview-map-head {\r
      display: grid;\r
      grid-template-columns: auto minmax(0, 1fr) auto;\r
      align-items: center;\r
      gap: 0.45rem;\r
      min-height: 2.25rem;\r
      padding: 0.42rem 0.48rem 0.38rem 0.55rem;\r
      border-bottom: 1px solid var(--toolbar-border);\r
      background: linear-gradient(110deg, color-mix(in srgb, var(--frontend-fill) 45%, transparent), transparent 68%);\r
      cursor: grab;\r
      touch-action: none;\r
      user-select: none;\r
    }\r
    .overview-map[data-panel-dragging="true"] .overview-map-head { cursor: grabbing; }\r
    .overview-map[data-placement-invalid="true"] {\r
      border-color: var(--security-stroke);\r
      box-shadow: 0 0 0 2px color-mix(in srgb, var(--security-stroke) 34%, transparent), 0 16px 42px rgba(0, 0, 0, 0.3);\r
    }\r
    .overview-map[data-compact="true"] {\r
      width: 7.4rem;\r
    }\r
    .overview-map[data-compact="true"] .overview-map-head {\r
      grid-template-columns: minmax(0, 1fr) auto;\r
      gap: 0.24rem;\r
      min-height: 1.5rem;\r
      padding: 0.05rem 0.16rem 0.05rem 0.32rem;\r
      border-bottom: 0;\r
    }\r
    .overview-map[data-compact="true"] .overview-map-live,\r
    .overview-map[data-compact="true"] .overview-map-copy,\r
    .overview-map[data-compact="true"] .overview-map-surface,\r
    .overview-map[data-compact="true"] .overview-map-hint {\r
      display: none;\r
    }\r
    .overview-map[data-compact="true"] .overview-map-expand { display: inline-flex; }\r
    .overview-map[data-compact="true"] .overview-map-close {\r
      width: 1.15rem;\r
      height: 1.15rem;\r
      font-size: 0.72rem;\r
    }\r
    .overview-map-live {\r
      width: 0.42rem;\r
      height: 0.42rem;\r
      border-radius: 50%;\r
      background: var(--backend-stroke);\r
      box-shadow: 0 0 0 0 color-mix(in srgb, var(--backend-stroke) 52%, transparent);\r
      animation: archify-radar-live 2.4s ease-out infinite;\r
    }\r
    .overview-map-copy { min-width: 0; line-height: 1.1; }\r
    .overview-map-copy strong {\r
      display: block;\r
      overflow: hidden;\r
      color: var(--frontend-stroke);\r
      font-size: 0.59rem;\r
      letter-spacing: 0.12em;\r
      text-transform: uppercase;\r
      white-space: nowrap;\r
      text-overflow: ellipsis;\r
    }\r
    .overview-map-copy small {\r
      display: block;\r
      margin-top: 0.18rem;\r
      overflow: hidden;\r
      color: var(--text-faint);\r
      font-size: 0.52rem;\r
      letter-spacing: 0.04em;\r
      white-space: nowrap;\r
      text-overflow: ellipsis;\r
    }\r
    .overview-map-expand {\r
      display: none;\r
      align-items: center;\r
      justify-content: center;\r
      min-width: 0;\r
      height: 1.2rem;\r
      padding: 0 0.34rem;\r
      overflow: hidden;\r
      border: 0;\r
      border-radius: 0.3rem;\r
      background: transparent;\r
      color: var(--frontend-stroke);\r
      font: inherit;\r
      font-size: 0.49rem;\r
      font-weight: 700;\r
      letter-spacing: 0.06em;\r
      text-transform: uppercase;\r
      white-space: nowrap;\r
      cursor: pointer;\r
    }\r
    .overview-map-close {\r
      width: 1.55rem;\r
      height: 1.55rem;\r
      padding: 0;\r
      border: 0;\r
      border-radius: 0.34rem;\r
      background: transparent;\r
      color: var(--toolbar-text);\r
      font: inherit;\r
      font-size: 0.9rem;\r
      cursor: pointer;\r
    }\r
    .overview-map-expand:hover,\r
    .overview-map-expand:focus-visible,\r
    .overview-map-close:hover,\r
    .overview-map-close:focus-visible { background: var(--toolbar-hover); }\r
    .overview-map-expand:focus-visible,\r
    .overview-map-close:focus-visible,\r
    .overview-map-surface:focus-visible,\r
    .overview-map-node:focus-visible {\r
      outline: 2px solid var(--frontend-stroke);\r
      outline-offset: 1px;\r
    }\r
    .overview-map-surface {\r
      position: relative;\r
      height: 7rem;\r
      margin: 0.42rem;\r
      overflow: hidden;\r
      border: 1px solid color-mix(in srgb, var(--panel-border) 72%, transparent);\r
      border-radius: 0.42rem;\r
      background:\r
        linear-gradient(color-mix(in srgb, var(--panel-border) 26%, transparent) 1px, transparent 1px),\r
        linear-gradient(90deg, color-mix(in srgb, var(--panel-border) 26%, transparent) 1px, transparent 1px),\r
        color-mix(in srgb, var(--bg) 86%, transparent);\r
      background-size: 12px 12px;\r
      cursor: crosshair;\r
      touch-action: none;\r
    }\r
    html[data-preset="blueprint"] .overview-map-surface { border-radius: 0.1rem; }\r
    .overview-map-surface > svg {\r
      width: 100%;\r
      height: 100%;\r
      min-width: 0;\r
      transform: none !important;\r
      transition: none !important;\r
      display: block;\r
      overflow: visible;\r
    }\r
    .overview-map-node {\r
      fill: var(--backend-stroke);\r
      fill-opacity: 0.52;\r
      stroke: var(--backend-stroke);\r
      stroke-opacity: 0.86;\r
      vector-effect: non-scaling-stroke;\r
      cursor: pointer;\r
      transition: fill-opacity 140ms ease, stroke-width 140ms ease, filter 140ms ease;\r
    }\r
    .overview-map-node[data-kind="frontend"],\r
    .overview-map-node[data-kind="start"] { fill: var(--frontend-stroke); stroke: var(--frontend-stroke); }\r
    .overview-map-node[data-kind="database"],\r
    .overview-map-node[data-kind="success"] { fill: var(--database-stroke); stroke: var(--database-stroke); }\r
    .overview-map-node[data-kind="cloud"],\r
    .overview-map-node[data-kind="waiting"] { fill: var(--cloud-stroke); stroke: var(--cloud-stroke); }\r
    .overview-map-node[data-kind="messagebus"] { fill: var(--messagebus-stroke); stroke: var(--messagebus-stroke); }\r
    .overview-map-node[data-kind="security"],\r
    .overview-map-node[data-kind="decision"],\r
    .overview-map-node[data-kind="failure"] { fill: var(--security-stroke); stroke: var(--security-stroke); }\r
    .overview-map-node[data-kind="external"],\r
    .overview-map-node[data-kind="neutral"] { fill: var(--external-stroke); stroke: var(--external-stroke); }\r
    .overview-map-node[data-radar-active="true"],\r
    .overview-map-node:hover,\r
    .overview-map-node:focus-visible {\r
      fill-opacity: 0.92;\r
      stroke-width: 2.2;\r
      filter: drop-shadow(0 0 3px currentColor);\r
    }\r
    .overview-map-viewport {\r
      fill: color-mix(in srgb, var(--frontend-fill) 56%, transparent);\r
      stroke: var(--frontend-stroke);\r
      stroke-width: 2;\r
      vector-effect: non-scaling-stroke;\r
      pointer-events: none;\r
      filter: drop-shadow(0 0 3px color-mix(in srgb, var(--frontend-stroke) 54%, transparent));\r
    }\r
    .overview-map-hint {\r
      display: flex;\r
      justify-content: space-between;\r
      gap: 0.5rem;\r
      padding: 0 0.52rem 0.46rem;\r
      color: var(--text-faint);\r
      font-size: 0.49rem;\r
      letter-spacing: 0.06em;\r
      text-transform: uppercase;\r
    }\r
    .diagram-nav #btn-overview-map[aria-expanded="true"] {\r
      color: var(--frontend-stroke);\r
      background: var(--toolbar-hover);\r
    }\r
    .overview-map-feedback {\r
      position: absolute;\r
      right: 1rem;\r
      bottom: 4.15rem;\r
      z-index: 13;\r
      max-width: min(16rem, calc(100% - 2rem));\r
      padding: 0.38rem 0.55rem;\r
      border: 1px solid color-mix(in srgb, var(--frontend-stroke) 52%, var(--toolbar-border));\r
      border-radius: 0.5rem;\r
      background: var(--toolbar-menu-bg);\r
      color: var(--toolbar-text);\r
      box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);\r
      font-size: 0.52rem;\r
      line-height: 1.35;\r
      pointer-events: none;\r
    }\r
    .overview-map-feedback[hidden] { display: none; }\r
    .focus-chip[data-radar-yielded="true"] { display: none !important; }\r
    .diagram-nav #btn-route-probe[aria-pressed="true"] {\r
      color: var(--backend-stroke);\r
      background: var(--toolbar-hover);\r
    }\r
    .diagram-nav #btn-semantic-lens[aria-expanded="true"],\r
    .diagram-nav #btn-semantic-lens[aria-pressed="true"] {\r
      color: var(--database-stroke);\r
      background: var(--toolbar-hover);\r
    }\r
\r
    /* Semantic Lens turns the compiled node-kind palette into an analytical\r
       legend. One kind reveals its real traffic; two kinds compare only their\r
       direct authored relationships. Geometry and the canonical SVG stay put. */\r
    .semantic-lens {\r
      position: absolute;\r
      right: 1rem;\r
      bottom: calc(4.15rem + var(--archify-nav-reserve));\r
      z-index: 24;\r
      width: min(20rem, calc(100% - 2rem));\r
      overflow: hidden;\r
      border: 1px solid color-mix(in srgb, var(--database-stroke) 58%, var(--toolbar-border));\r
      border-radius: 0.82rem;\r
      background:\r
        linear-gradient(135deg, color-mix(in srgb, var(--database-fill) 34%, transparent), transparent 48%),\r
        var(--toolbar-menu-bg);\r
      color: var(--toolbar-text);\r
      box-shadow: 0 18px 52px rgba(0, 0, 0, 0.36);\r
      backdrop-filter: blur(18px);\r
      animation: archify-lens-in 180ms cubic-bezier(0.22, 1, 0.36, 1);\r
    }\r
    .semantic-lens[hidden] { display: none; }\r
    .semantic-lens[data-dock-side="left"] { left: 1rem; right: auto; }\r
    .semantic-lens[data-dock-side="right"] { left: auto; right: 1rem; }\r
    html[data-preset="blueprint"] .semantic-lens { border-radius: 0.28rem; }\r
    .semantic-lens-head {\r
      display: grid;\r
      grid-template-columns: minmax(0, 1fr) auto;\r
      align-items: start;\r
      gap: 0.75rem;\r
      padding: 0.72rem 0.78rem 0.62rem;\r
      border-bottom: 1px solid var(--toolbar-border);\r
    }\r
    .semantic-lens-eyebrow {\r
      display: block;\r
      color: var(--database-stroke);\r
      font-size: 0.5rem;\r
      font-weight: 800;\r
      letter-spacing: 0.16em;\r
      text-transform: uppercase;\r
    }\r
    .semantic-lens-title {\r
      display: block;\r
      margin-top: 0.16rem;\r
      color: var(--text);\r
      font-size: 0.82rem;\r
      letter-spacing: -0.02em;\r
    }\r
    .semantic-lens-close {\r
      width: 1.75rem;\r
      height: 1.75rem;\r
      padding: 0;\r
      border: 0;\r
      border-radius: 0.35rem;\r
      background: transparent;\r
      color: var(--toolbar-text);\r
      font: inherit;\r
      font-size: 1rem;\r
      cursor: pointer;\r
    }\r
    .semantic-lens-close:hover,\r
    .semantic-lens-close:focus-visible { background: var(--toolbar-hover); }\r
    .semantic-lens-instruction {\r
      margin: 0;\r
      padding: 0.52rem 0.78rem 0.48rem;\r
      color: var(--text-faint);\r
      font-size: 0.55rem;\r
      line-height: 1.45;\r
    }\r
    .semantic-lens-kinds {\r
      display: grid;\r
      grid-template-columns: 1fr 1fr;\r
      gap: 0.3rem;\r
      max-height: min(15rem, 40vh);\r
      padding: 0 0.5rem 0.5rem;\r
      overflow-y: auto;\r
      scrollbar-width: thin;\r
    }\r
    .semantic-lens-kind {\r
      --lens-color: var(--external-stroke);\r
      display: grid;\r
      grid-template-columns: auto minmax(0, 1fr) auto;\r
      align-items: center;\r
      gap: 0.42rem;\r
      min-width: 0;\r
      min-height: 2.15rem;\r
      padding: 0.35rem 0.42rem;\r
      border: 1px solid color-mix(in srgb, var(--lens-color) 24%, var(--toolbar-border));\r
      border-radius: 0.45rem;\r
      background: color-mix(in srgb, var(--panel) 76%, transparent);\r
      color: var(--toolbar-text);\r
      font: inherit;\r
      text-align: left;\r
      cursor: pointer;\r
      transition: border-color 140ms ease, background 140ms ease, opacity 140ms ease;\r
    }\r
    html[data-preset="blueprint"] .semantic-lens-kind { border-radius: 0.12rem; }\r
    .semantic-lens-kind[data-kind="frontend"],\r
    .semantic-lens-kind[data-kind="start"] { --lens-color: var(--frontend-stroke); }\r
    .semantic-lens-kind[data-kind="backend"],\r
    .semantic-lens-kind[data-kind="active"] { --lens-color: var(--backend-stroke); }\r
    .semantic-lens-kind[data-kind="database"],\r
    .semantic-lens-kind[data-kind="success"] { --lens-color: var(--database-stroke); }\r
    .semantic-lens-kind[data-kind="cloud"],\r
    .semantic-lens-kind[data-kind="waiting"] { --lens-color: var(--cloud-stroke); }\r
    .semantic-lens-kind[data-kind="messagebus"] { --lens-color: var(--messagebus-stroke); }\r
    .semantic-lens-kind[data-kind="security"],\r
    .semantic-lens-kind[data-kind="decision"],\r
    .semantic-lens-kind[data-kind="failure"] { --lens-color: var(--security-stroke); }\r
    .semantic-lens-kind:hover,\r
    .semantic-lens-kind:focus-visible,\r
    .semantic-lens-kind[aria-pressed="true"] {\r
      border-color: color-mix(in srgb, var(--lens-color) 78%, var(--toolbar-border));\r
      background: color-mix(in srgb, var(--lens-color) 11%, var(--panel));\r
    }\r
    .semantic-lens-kind:focus-visible,\r
    .semantic-lens-close:focus-visible,\r
    .semantic-lens-actions button:focus-visible {\r
      outline: 2px solid var(--database-stroke);\r
      outline-offset: 1px;\r
    }\r
    .semantic-lens-kind:disabled { opacity: 0.34; cursor: default; }\r
    .semantic-lens-swatch {\r
      width: 0.48rem;\r
      height: 0.48rem;\r
      border-radius: 50%;\r
      background: var(--lens-color);\r
      box-shadow: 0 0 8px color-mix(in srgb, var(--lens-color) 58%, transparent);\r
    }\r
    .semantic-lens-kind strong {\r
      overflow: hidden;\r
      color: var(--text);\r
      font-size: 0.61rem;\r
      text-overflow: ellipsis;\r
      white-space: nowrap;\r
    }\r
    .semantic-lens-kind em {\r
      color: var(--lens-color);\r
      font-size: 0.54rem;\r
      font-style: normal;\r
      font-weight: 800;\r
    }\r
    .semantic-lens-status {\r
      min-height: 2.5rem;\r
      margin: 0;\r
      padding: 0.55rem 0.78rem;\r
      border-top: 1px solid var(--toolbar-border);\r
      color: var(--text-faint);\r
      font-size: 0.55rem;\r
      line-height: 1.45;\r
    }\r
    .semantic-lens-status strong { color: var(--database-stroke); font-weight: 800; }\r
    .semantic-lens-actions {\r
      display: flex;\r
      justify-content: flex-end;\r
      gap: 0.28rem;\r
      padding: 0 0.62rem 0.62rem;\r
    }\r
    .semantic-lens-actions button {\r
      min-height: 1.8rem;\r
      padding: 0.28rem 0.48rem;\r
      border: 0;\r
      border-radius: 0.35rem;\r
      background: transparent;\r
      color: var(--toolbar-text);\r
      font: inherit;\r
      font-size: 0.56rem;\r
      cursor: pointer;\r
    }\r
    .semantic-lens-actions button:hover { background: var(--toolbar-hover); }\r
    .semantic-lens-actions #semantic-lens-copy { color: var(--database-stroke); }\r
    @keyframes archify-lens-in {\r
      from { opacity: 0; transform: translateY(5px) scale(0.985); }\r
      to { opacity: 1; transform: translateY(0) scale(1); }\r
    }\r
\r
    /* Route Probe answers a reader question over the compiled semantic graph:\r
       choose two stable nodes and reveal the shortest authored directed route.\r
       The receipt and signal live entirely in the viewer layer. */\r
    .route-probe {\r
      position: absolute;\r
      left: 1rem;\r
      bottom: calc(1rem + var(--archify-nav-reserve));\r
      z-index: 12;\r
      width: min(46rem, calc(100% - 25rem));\r
      min-width: 18rem;\r
      overflow: hidden;\r
      border: 1px solid color-mix(in srgb, var(--backend-stroke) 62%, var(--toolbar-border));\r
      border-radius: 0.82rem;\r
      background:\r
        linear-gradient(115deg, color-mix(in srgb, var(--backend-fill) 50%, transparent), transparent 62%),\r
        var(--toolbar-menu-bg);\r
      color: var(--toolbar-text);\r
      box-shadow: 0 18px 48px rgba(0, 0, 0, 0.3);\r
      backdrop-filter: blur(16px);\r
      font-size: 0.625rem;\r
    }\r
    .route-probe[hidden] { display: none; }\r
    .route-probe[data-route-dock="top"] {\r
      top: 1rem;\r
      bottom: auto;\r
    }\r
    html[data-preset="blueprint"] .route-probe { border-radius: 0.25rem; }\r
    .route-probe-head {\r
      display: grid;\r
      grid-template-columns: minmax(0, 1fr) auto;\r
      align-items: start;\r
      gap: 0.65rem;\r
      padding: 0.52rem 0.58rem 0.44rem;\r
      border-bottom: 1px solid color-mix(in srgb, var(--toolbar-border) 80%, transparent);\r
    }\r
    .route-probe-copy { min-width: 0; }\r
    .route-probe-eyebrow {\r
      display: block;\r
      color: var(--backend-stroke);\r
      font-size: 0.48rem;\r
      font-weight: 800;\r
      letter-spacing: 0.15em;\r
      text-transform: uppercase;\r
    }\r
    .route-probe-title {\r
      display: block;\r
      margin-top: 0.14rem;\r
      overflow: hidden;\r
      color: var(--toolbar-text);\r
      font-size: 0.72rem;\r
      line-height: 1.25;\r
      white-space: nowrap;\r
      text-overflow: ellipsis;\r
    }\r
    .route-probe-actions { display: flex; gap: 0.2rem; }\r
    .route-probe button {\r
      min-height: 1.55rem;\r
      padding: 0.25rem 0.42rem;\r
      border: 0;\r
      border-radius: 0.36rem;\r
      background: transparent;\r
      color: var(--toolbar-text);\r
      font: inherit;\r
      cursor: pointer;\r
    }\r
    .route-probe button:hover,\r
    .route-probe button:focus-visible { background: var(--toolbar-hover); }\r
    .route-probe button:focus-visible {\r
      outline: 2px solid var(--backend-stroke);\r
      outline-offset: 1px;\r
    }\r
    .route-probe-copy-link { color: var(--frontend-stroke) !important; }\r
    .route-probe-find { color: var(--backend-stroke) !important; }\r
    .route-probe-copy-link[hidden] { display: none; }\r
    .route-probe-find[hidden] { display: none; }\r
    .route-probe-path {\r
      display: flex;\r
      align-items: center;\r
      min-height: 2.2rem;\r
      padding: 0.42rem 0.58rem 0.24rem;\r
      overflow-x: auto;\r
      scrollbar-width: thin;\r
      white-space: nowrap;\r
    }\r
    .route-probe-node,\r
    .route-probe button.route-probe-node {\r
      flex: none;\r
      max-width: 9.5rem;\r
      overflow: hidden;\r
      min-height: 1.75rem !important;\r
      padding: 0.22rem 0.38rem;\r
      border: 1px solid color-mix(in srgb, var(--backend-stroke) 46%, var(--toolbar-border));\r
      border-radius: 999px;\r
      background: color-mix(in srgb, var(--backend-fill) 52%, transparent);\r
      color: var(--text);\r
      font-size: 0.56rem;\r
      font-weight: 700;\r
      text-overflow: ellipsis;\r
      white-space: nowrap;\r
    }\r
    .route-probe-node[data-endpoint="start"] {\r
      border-color: var(--frontend-stroke);\r
      color: var(--frontend-stroke);\r
    }\r
    .route-probe-node[data-endpoint="end"] {\r
      border-color: var(--security-stroke);\r
      color: var(--security-stroke);\r
    }\r
    .route-probe-node[data-route-journey-state="past"] { opacity: 0.66; }\r
    .route-probe-node[data-route-journey-state="future"] { opacity: 0.48; }\r
    .route-probe-node[aria-current="step"] {\r
      border-color: var(--backend-stroke);\r
      background: color-mix(in srgb, var(--backend-fill) 82%, var(--toolbar-menu-bg));\r
      color: var(--text);\r
      box-shadow: 0 0 0 1px color-mix(in srgb, var(--backend-stroke) 42%, transparent), 0 0 14px color-mix(in srgb, var(--backend-stroke) 34%, transparent);\r
      opacity: 1;\r
    }\r
    html[data-preset="blueprint"] .route-probe-node[aria-current="step"] {\r
      border-style: double;\r
      border-width: 3px;\r
      border-radius: 0.2rem;\r
      box-shadow: none;\r
    }\r
    .route-probe-arrow {\r
      flex: none;\r
      padding: 0 0.28rem;\r
      color: var(--text-faint);\r
      font-size: 0.65rem;\r
    }\r
    .route-probe-placeholder {\r
      color: var(--text-faint);\r
      font-size: 0.56rem;\r
      letter-spacing: 0.03em;\r
    }\r
    .route-probe-status {\r
      display: block;\r
      min-height: 1.45rem;\r
      padding: 0.08rem 0.58rem 0.44rem;\r
      color: var(--text-faint);\r
      font-size: 0.52rem;\r
      line-height: 1.35;\r
    }\r
    .route-journey-controls {\r
      display: grid;\r
      grid-template-columns: 2rem minmax(5.8rem, auto) 2rem minmax(4.8rem, auto);\r
      justify-content: start;\r
      gap: 0.22rem;\r
      padding: 0.08rem 0.58rem 0.28rem;\r
    }\r
    .route-journey-controls[hidden] { display: none; }\r
    .route-journey-controls button {\r
      min-height: 1.8rem;\r
      border: 1px solid color-mix(in srgb, var(--toolbar-border) 86%, transparent);\r
      background: color-mix(in srgb, var(--toolbar-bg) 72%, transparent);\r
      font-size: 0.54rem;\r
      font-weight: 700;\r
    }\r
    .route-journey-controls button:disabled {\r
      cursor: default;\r
      opacity: 0.34;\r
    }\r
    .route-journey-play { color: var(--backend-stroke) !important; }\r
    .route-journey-overview { color: var(--frontend-stroke) !important; }\r
    .route-journey-controls[data-playing="true"] .route-journey-play {\r
      border-color: color-mix(in srgb, var(--backend-stroke) 64%, var(--toolbar-border));\r
      background: color-mix(in srgb, var(--backend-fill) 62%, transparent);\r
    }\r
    .route-probe[data-state="error"] {\r
      border-color: color-mix(in srgb, var(--security-stroke) 72%, var(--toolbar-border));\r
    }\r
    .route-probe[data-state="error"] .route-probe-status { color: var(--security-stroke); }\r
\r
    .focus-chip {\r
      position: absolute;\r
      left: 1rem;\r
      top: 1rem;\r
      z-index: 12;\r
      display: block;\r
      width: min(22rem, calc(100% - 13rem));\r
      max-width: calc(100% - 13rem);\r
      overflow: hidden;\r
      border: 1px solid var(--frontend-stroke);\r
      border-radius: 0.85rem;\r
      background: var(--toolbar-menu-bg);\r
      color: var(--toolbar-text);\r
      box-shadow: 0 18px 48px rgba(0, 0, 0, 0.3);\r
      backdrop-filter: blur(16px);\r
      font-size: 0.6875rem;\r
    }\r
    .focus-chip[hidden] { display: none; }\r
    html[data-preset="blueprint"] .focus-chip { border-radius: 0.3rem; }\r
    .focus-chip button {\r
      flex: none;\r
      padding: 0.3rem 0.45rem;\r
      border-radius: 0.35rem;\r
      font-size: 0.625rem;\r
    }\r
    .relationship-lens-head {\r
      display: grid;\r
      grid-template-columns: minmax(0, 1fr) auto;\r
      align-items: start;\r
      gap: 0.75rem;\r
      padding: 0.7rem 0.75rem 0.65rem;\r
      border-bottom: 1px solid var(--toolbar-border);\r
      background: linear-gradient(120deg, color-mix(in srgb, var(--frontend-fill) 34%, transparent), transparent 72%);\r
    }\r
    .relationship-lens-copy { min-width: 0; }\r
    .relationship-lens-actions {\r
      display: flex;\r
      flex-direction: column;\r
      align-items: flex-end;\r
      gap: 0.18rem;\r
    }\r
    .relationship-lens-actions button { white-space: nowrap; }\r
    .relationship-lens-actions #btn-focus-clear {\r
      display: grid;\r
      width: 1.75rem;\r
      height: 1.75rem;\r
      padding: 0;\r
      place-items: center;\r
      color: var(--text-muted);\r
      font-size: 1rem;\r
      line-height: 1;\r
    }\r
    .relationship-lens-actions #btn-focus-clear:hover,\r
    .relationship-lens-actions #btn-focus-clear:focus-visible {\r
      background: var(--toolbar-hover);\r
      color: var(--text);\r
    }\r
    .relationship-lens-actions #btn-focus-copy { color: var(--frontend-stroke); }\r
    .relationship-lens-actions #btn-focus-relations { display: none; }\r
    .relationship-lens-eyebrow {\r
      display: block;\r
      margin-bottom: 0.18rem;\r
      color: var(--frontend-stroke);\r
      font-size: 0.5rem;\r
      font-weight: 800;\r
      letter-spacing: 0.14em;\r
      text-transform: uppercase;\r
    }\r
    .relationship-lens-title {\r
      display: block;\r
      overflow: hidden;\r
      color: var(--text);\r
      font-size: 0.8rem;\r
      line-height: 1.35;\r
      text-overflow: ellipsis;\r
      white-space: nowrap;\r
    }\r
    .semantic-passport-detail {\r
      display: block;\r
      margin-top: 0.12rem;\r
      overflow: hidden;\r
      color: var(--text-muted);\r
      font-size: 0.625rem;\r
      line-height: 1.4;\r
      text-overflow: ellipsis;\r
      white-space: nowrap;\r
    }\r
    .semantic-passport-detail[hidden] { display: none; }\r
    .semantic-passport-meta {\r
      display: flex;\r
      flex-wrap: wrap;\r
      gap: 0.24rem;\r
      margin-top: 0.42rem;\r
    }\r
    .semantic-passport-meta span,\r
    .semantic-passport-meta code {\r
      max-width: 100%;\r
      overflow: hidden;\r
      padding: 0.14rem 0.34rem;\r
      border: 1px solid color-mix(in srgb, var(--toolbar-border) 82%, transparent);\r
      border-radius: 999px;\r
      background: color-mix(in srgb, var(--panel) 68%, transparent);\r
      color: var(--text-faint);\r
      font: inherit;\r
      font-size: 0.5rem;\r
      letter-spacing: 0.04em;\r
      text-overflow: ellipsis;\r
      white-space: nowrap;\r
    }\r
    .semantic-passport-meta [data-passport="kind"] {\r
      border-color: color-mix(in srgb, var(--frontend-stroke) 50%, var(--toolbar-border));\r
      color: var(--frontend-stroke);\r
      font-weight: 800;\r
      text-transform: uppercase;\r
    }\r
    .semantic-passport-meta [data-passport="tag"] { color: var(--cloud-stroke); }\r
    .semantic-passport-meta [data-passport="brand"] {\r
      border-color: color-mix(in srgb, var(--messagebus-stroke) 52%, var(--toolbar-border));\r
      color: var(--messagebus-stroke);\r
      font-weight: 700;\r
    }\r
    .semantic-passport-meta [hidden] { display: none; }\r
    html[data-preset="blueprint"] .semantic-passport-meta span,\r
    html[data-preset="blueprint"] .semantic-passport-meta code { border-radius: 0.1rem; }\r
    .semantic-passport-evidence {\r
      margin-top: 0.52rem;\r
      padding: 0.5rem;\r
      border: 1px solid color-mix(in srgb, var(--backend-stroke) 32%, var(--toolbar-border));\r
      border-radius: 0.55rem;\r
      background: color-mix(in srgb, var(--backend-fill) 18%, var(--panel));\r
    }\r
    .semantic-passport-evidence[hidden] { display: none; }\r
    html[data-preset="blueprint"] .semantic-passport-evidence { border-radius: 0.18rem; }\r
    .semantic-passport-evidence-head {\r
      display: flex;\r
      align-items: center;\r
      justify-content: space-between;\r
      gap: 0.55rem;\r
      margin-bottom: 0.35rem;\r
    }\r
    .semantic-passport-evidence-status {\r
      display: inline-flex;\r
      align-items: center;\r
      gap: 0.28rem;\r
      color: var(--backend-stroke);\r
      font-size: 0.5rem;\r
      font-weight: 800;\r
      letter-spacing: 0.08em;\r
      text-transform: uppercase;\r
    }\r
    .semantic-passport-evidence-status::before {\r
      content: '';\r
      width: 0.38rem;\r
      height: 0.38rem;\r
      border-radius: 50%;\r
      background: var(--backend-stroke);\r
      box-shadow: 0 0 0 3px color-mix(in srgb, var(--backend-stroke) 14%, transparent);\r
    }\r
    .semantic-passport-repository {\r
      min-width: 0;\r
      overflow: hidden;\r
      color: var(--text-faint);\r
      font-size: 0.5rem;\r
      text-decoration: none;\r
      text-overflow: ellipsis;\r
      white-space: nowrap;\r
    }\r
    .semantic-passport-repository:hover,\r
    .semantic-passport-repository:focus-visible { color: var(--backend-stroke); }\r
    .semantic-passport-evidence-links { display: grid; gap: 0.22rem; }\r
    .semantic-passport-source {\r
      display: grid;\r
      grid-template-columns: minmax(0, 1fr) auto;\r
      gap: 0.15rem 0.45rem;\r
      align-items: center;\r
      padding: 0.34rem 0.4rem;\r
      border: 1px solid transparent;\r
      border-radius: 0.38rem;\r
      color: var(--text-muted);\r
      text-decoration: none;\r
    }\r
    a.semantic-passport-source:hover,\r
    a.semantic-passport-source:focus-visible {\r
      border-color: color-mix(in srgb, var(--backend-stroke) 42%, transparent);\r
      background: color-mix(in srgb, var(--backend-fill) 32%, transparent);\r
      color: var(--text);\r
    }\r
    .semantic-passport-source strong {\r
      overflow: hidden;\r
      font-size: 0.5625rem;\r
      text-overflow: ellipsis;\r
      white-space: nowrap;\r
    }\r
    .semantic-passport-source code {\r
      color: var(--backend-stroke);\r
      font: inherit;\r
      font-size: 0.5rem;\r
    }\r
    .semantic-passport-source small {\r
      grid-column: 1 / -1;\r
      overflow: hidden;\r
      color: var(--text-faint);\r
      font-size: 0.5rem;\r
      text-overflow: ellipsis;\r
      white-space: nowrap;\r
    }\r
    .relationship-lens-summary {\r
      display: block;\r
      margin-top: 0.12rem;\r
      color: var(--text-faint);\r
      font-size: 0.5625rem;\r
    }\r
    .semantic-passport-reach {\r
      display: grid;\r
      gap: 0.28rem;\r
      margin-top: 0.52rem;\r
      padding-top: 0.48rem;\r
      border-top: 1px solid color-mix(in srgb, var(--toolbar-border) 76%, transparent);\r
    }\r
    .semantic-passport-reach[hidden] { display: none; }\r
    .semantic-passport-reach-label {\r
      color: var(--text-faint);\r
      font-size: 0.5rem;\r
      font-weight: 800;\r
      letter-spacing: 0.1em;\r
      text-transform: uppercase;\r
    }\r
    .semantic-passport-reach-actions {\r
      display: grid;\r
      grid-template-columns: repeat(2, minmax(0, 1fr));\r
      gap: 0.25rem;\r
    }\r
    .semantic-passport-reach-actions button {\r
      display: flex;\r
      align-items: center;\r
      justify-content: space-between;\r
      gap: 0.5rem;\r
      min-width: 0;\r
      min-height: 2rem;\r
      padding: 0.32rem 0.42rem;\r
      border: 1px solid color-mix(in srgb, var(--toolbar-border) 86%, transparent);\r
      background: color-mix(in srgb, var(--panel) 70%, transparent);\r
      color: var(--text-muted);\r
      text-align: left;\r
    }\r
    .semantic-passport-reach-actions button:hover:not(:disabled),\r
    .semantic-passport-reach-actions button:focus-visible {\r
      border-color: color-mix(in srgb, var(--frontend-stroke) 62%, var(--toolbar-border));\r
      color: var(--text);\r
    }\r
    .semantic-passport-reach-actions button:focus-visible {\r
      outline: 2px solid var(--frontend-stroke);\r
      outline-offset: 1px;\r
    }\r
    .semantic-passport-reach-actions button:disabled {\r
      cursor: default;\r
      opacity: 0.5;\r
    }\r
    .semantic-passport-reach-actions button[aria-pressed="true"] {\r
      border-color: color-mix(in srgb, var(--reach-color, var(--frontend-stroke)) 72%, var(--toolbar-border));\r
      background: color-mix(in srgb, var(--reach-fill, var(--frontend-fill)) 48%, transparent);\r
      color: var(--text);\r
    }\r
    #btn-reach-upstream {\r
      --reach-color: var(--database-stroke);\r
      --reach-fill: var(--database-fill);\r
    }\r
    #btn-reach-downstream {\r
      --reach-color: var(--backend-stroke);\r
      --reach-fill: var(--backend-fill);\r
    }\r
    .semantic-passport-reach-actions strong {\r
      color: var(--reach-color, var(--frontend-stroke));\r
      font-size: 0.625rem;\r
    }\r
    .semantic-passport-reach-status {\r
      color: var(--text-faint);\r
      font-size: 0.525rem;\r
      line-height: 1.4;\r
    }\r
    .semantic-passport-reach-status[hidden] { display: none; }\r
    .relationship-lens-list {\r
      max-height: min(18rem, 46vh);\r
      overflow: auto;\r
      padding: 0.4rem;\r
      scrollbar-width: thin;\r
      scrollbar-color: var(--frontend-stroke) transparent;\r
    }\r
    .relationship-lens-list::-webkit-scrollbar { width: 4px; }\r
    .relationship-lens-list::-webkit-scrollbar-thumb {\r
      border-radius: 999px;\r
      background: color-mix(in srgb, var(--frontend-stroke) 68%, transparent);\r
    }\r
    .relationship-lens-group + .relationship-lens-group { margin-top: 0.35rem; }\r
    .relationship-lens-group-title {\r
      display: block;\r
      padding: 0.24rem 0.38rem 0.16rem;\r
      color: var(--text-faint);\r
      font-size: 0.5rem;\r
      font-weight: 800;\r
      letter-spacing: 0.12em;\r
      text-transform: uppercase;\r
    }\r
    .relationship-lens-row {\r
      display: grid;\r
      grid-template-columns: 2.1rem minmax(0, 1fr);\r
      gap: 0.06rem 0.45rem;\r
      width: 100%;\r
      padding: 0.45rem 0.5rem !important;\r
      text-align: left;\r
    }\r
    .relationship-lens-row:hover,\r
    .relationship-lens-row:focus-visible,\r
    .relationship-lens-row[data-preview-active="true"] {\r
      background: var(--toolbar-hover);\r
      box-shadow: inset 2px 0 0 var(--frontend-stroke);\r
    }\r
    .relationship-lens-row:focus-visible {\r
      outline: 2px solid var(--frontend-stroke);\r
      outline-offset: -2px;\r
    }\r
    .relationship-lens-direction {\r
      grid-row: 1 / 3;\r
      align-self: center;\r
      color: var(--frontend-stroke);\r
      font-size: 0.5rem;\r
      font-weight: 800;\r
      letter-spacing: 0.08em;\r
    }\r
    .relationship-lens-row[data-direction="in"] .relationship-lens-direction { color: var(--database-stroke); }\r
    .relationship-lens-row[data-direction="loop"] .relationship-lens-direction { color: var(--security-stroke); }\r
    .relationship-lens-row strong {\r
      overflow: hidden;\r
      color: var(--text);\r
      font-size: 0.6875rem;\r
      text-overflow: ellipsis;\r
      white-space: nowrap;\r
    }\r
    .relationship-lens-row small {\r
      overflow: hidden;\r
      color: var(--text-faint);\r
      font-size: 0.5625rem;\r
      text-overflow: ellipsis;\r
      white-space: nowrap;\r
    }\r
    .relationship-lens-empty {\r
      margin: 0;\r
      padding: 0.75rem;\r
      color: var(--text-faint);\r
      font-size: 0.625rem;\r
      text-align: center;\r
    }\r
\r
    /* Diagram Guide keeps the artifact's growing reader vocabulary\r
       discoverable without widening the permanent control bar. It derives\r
       honest counts at runtime and delegates every action to an existing\r
       production interaction instead of creating a second command system. */\r
    .diagram-guide {\r
      position: absolute;\r
      top: 1rem;\r
      right: 1rem;\r
      z-index: 26;\r
      width: min(32rem, calc(100% - 2rem));\r
      max-height: min(42rem, calc(100% - 2rem));\r
      overflow: auto;\r
      border: 1px solid color-mix(in srgb, var(--cloud-stroke) 58%, var(--toolbar-border));\r
      border-radius: 0.82rem;\r
      background:\r
        linear-gradient(135deg, color-mix(in srgb, var(--cloud-fill) 32%, transparent), transparent 42%),\r
        var(--toolbar-menu-bg);\r
      color: var(--toolbar-text);\r
      box-shadow: 0 22px 64px rgba(0, 0, 0, 0.4);\r
      backdrop-filter: blur(18px);\r
      animation: archify-guide-in 180ms cubic-bezier(0.22, 1, 0.36, 1);\r
    }\r
    .diagram-guide[hidden] { display: none; }\r
    html[data-preset="blueprint"] .diagram-guide { border-radius: 0.28rem; }\r
    .diagram-guide-head {\r
      display: grid;\r
      grid-template-columns: minmax(0, 1fr) auto;\r
      align-items: start;\r
      gap: 1rem;\r
      padding: 0.82rem 0.9rem 0.68rem;\r
      border-bottom: 1px solid var(--toolbar-border);\r
    }\r
    .diagram-guide-eyebrow {\r
      display: block;\r
      color: var(--cloud-stroke);\r
      font-size: 0.5rem;\r
      font-weight: 800;\r
      letter-spacing: 0.16em;\r
      text-transform: uppercase;\r
    }\r
    .diagram-guide-title {\r
      display: block;\r
      margin-top: 0.16rem;\r
      color: var(--text);\r
      font-size: 0.86rem;\r
      letter-spacing: -0.02em;\r
    }\r
    .diagram-guide-close {\r
      width: 1.8rem;\r
      height: 1.8rem;\r
      border: 0;\r
      border-radius: 0.35rem;\r
      background: transparent;\r
      color: var(--toolbar-text);\r
      font: inherit;\r
      font-size: 1rem;\r
      cursor: pointer;\r
    }\r
    .diagram-guide-close:hover,\r
    .diagram-guide-close:focus-visible { background: var(--toolbar-hover); }\r
    .diagram-guide-stats {\r
      display: flex;\r
      align-items: center;\r
      gap: 0.5rem;\r
      margin: 0;\r
      padding: 0.54rem 0.9rem;\r
      border-bottom: 1px solid color-mix(in srgb, var(--toolbar-border) 74%, transparent);\r
      color: var(--text-faint);\r
      font-size: 0.56rem;\r
      letter-spacing: 0.025em;\r
    }\r
    .diagram-guide-stats::before {\r
      content: '';\r
      width: 0.42rem;\r
      height: 0.42rem;\r
      flex: none;\r
      border-radius: 50%;\r
      background: var(--backend-stroke);\r
      box-shadow: 0 0 10px color-mix(in srgb, var(--backend-stroke) 72%, transparent);\r
    }\r
    .diagram-guide-actions {\r
      display: grid;\r
      grid-template-columns: 1fr 1fr;\r
      gap: 0.38rem;\r
      padding: 0.62rem;\r
    }\r
    .diagram-guide-action {\r
      --guide-accent: var(--frontend-stroke);\r
      display: grid;\r
      grid-template-columns: auto minmax(0, 1fr) auto;\r
      align-items: center;\r
      gap: 0.55rem;\r
      min-height: 4.15rem;\r
      padding: 0.55rem 0.58rem;\r
      border: 1px solid color-mix(in srgb, var(--guide-accent) 22%, var(--toolbar-border));\r
      border-radius: 0.55rem;\r
      background: color-mix(in srgb, var(--panel) 78%, transparent);\r
      color: var(--toolbar-text);\r
      font: inherit;\r
      text-align: left;\r
      cursor: pointer;\r
      transition: border-color 140ms ease, background 140ms ease, transform 140ms ease;\r
    }\r
    .diagram-guide-action[data-guide-action="route"] { --guide-accent: var(--backend-stroke); }\r
    .diagram-guide-action[data-guide-action="map"] { --guide-accent: var(--database-stroke); }\r
    .diagram-guide-action[data-guide-action="lens"] { --guide-accent: var(--messagebus-stroke); }\r
    .diagram-guide-action[data-guide-action="story"] { --guide-accent: var(--security-stroke); }\r
    .diagram-guide-action[data-guide-action="present"] {\r
      --guide-accent: var(--cloud-stroke);\r
    }\r
    .diagram-guide-action:hover,\r
    .diagram-guide-action:focus-visible {\r
      border-color: color-mix(in srgb, var(--guide-accent) 76%, var(--toolbar-border));\r
      background: color-mix(in srgb, var(--guide-accent) 9%, var(--panel));\r
      transform: translateY(-1px);\r
    }\r
    .diagram-guide-action:focus-visible,\r
    .diagram-guide-close:focus-visible {\r
      outline: 2px solid var(--cloud-stroke);\r
      outline-offset: 1px;\r
    }\r
    .diagram-guide-action:disabled {\r
      opacity: 0.42;\r
      cursor: default;\r
      transform: none;\r
    }\r
    .diagram-guide-index {\r
      display: grid;\r
      place-items: center;\r
      width: 1.65rem;\r
      height: 1.65rem;\r
      border: 1px solid color-mix(in srgb, var(--guide-accent) 64%, var(--toolbar-border));\r
      border-radius: 0.35rem;\r
      color: var(--guide-accent);\r
      font-size: 0.5rem;\r
      font-weight: 800;\r
      letter-spacing: 0.06em;\r
    }\r
    .diagram-guide-action-copy { min-width: 0; }\r
    .diagram-guide-action strong {\r
      display: block;\r
      overflow: hidden;\r
      color: var(--text);\r
      font-size: 0.66rem;\r
      text-overflow: ellipsis;\r
      white-space: nowrap;\r
    }\r
    .diagram-guide-action small {\r
      display: -webkit-box;\r
      margin-top: 0.18rem;\r
      overflow: hidden;\r
      color: var(--text-faint);\r
      font-size: 0.5rem;\r
      line-height: 1.35;\r
      -webkit-box-orient: vertical;\r
      -webkit-line-clamp: 2;\r
    }\r
    .diagram-guide kbd {\r
      align-self: start;\r
      min-width: 1.45rem;\r
      padding: 0.12rem 0.3rem;\r
      border: 1px solid var(--toolbar-border);\r
      border-radius: 0.25rem;\r
      color: var(--text-faint);\r
      font: inherit;\r
      font-size: 0.5rem;\r
      text-align: center;\r
    }\r
    .diagram-guide-shortcuts {\r
      display: flex;\r
      flex-wrap: wrap;\r
      gap: 0.34rem 0.62rem;\r
      padding: 0.58rem 0.9rem 0.68rem;\r
      border-top: 1px solid var(--toolbar-border);\r
      color: var(--text-faint);\r
      font-size: 0.5rem;\r
    }\r
    .diagram-guide-shortcuts span {\r
      display: inline-flex;\r
      align-items: center;\r
      gap: 0.28rem;\r
      white-space: nowrap;\r
    }\r
    .diagram-guide-feedback {\r
      min-height: 1rem;\r
      margin: -0.18rem 0.9rem 0.62rem;\r
      color: var(--security-stroke);\r
      font-size: 0.5rem;\r
    }\r
    .diagram-guide-feedback:empty { display: none; }\r
    @keyframes archify-guide-in {\r
      from { opacity: 0; transform: translateY(-5px) scale(0.985); }\r
      to { opacity: 1; transform: translateY(0) scale(1); }\r
    }\r
\r
    .node-finder {\r
      position: absolute;\r
      top: 1rem;\r
      left: 1rem;\r
      z-index: 24;\r
      display: flex;\r
      flex-direction: column;\r
      width: min(22rem, calc(100% - 2rem));\r
      max-height: calc(100% - 2rem);\r
      overflow: hidden;\r
      border: 1px solid var(--toolbar-border);\r
      border-radius: 0.85rem;\r
      background: var(--toolbar-menu-bg);\r
      color: var(--toolbar-text);\r
      box-shadow: 0 6px 8px rgba(0, 0, 0, 0.22);\r
      backdrop-filter: blur(16px);\r
    }\r
    .node-finder[hidden] { display: none; }\r
    .node-finder[data-context="route-source"] {\r
      border-color: color-mix(in srgb, var(--frontend-stroke) 68%, var(--toolbar-border));\r
    }\r
    .node-finder[data-context="route-target"] {\r
      border-color: color-mix(in srgb, var(--security-stroke) 68%, var(--toolbar-border));\r
    }\r
    html[data-preset="blueprint"] .node-finder { border-radius: 0.3rem; }\r
    .node-finder-head {\r
      display: flex;\r
      align-items: center;\r
      justify-content: space-between;\r
      gap: 1rem;\r
      padding: 0.7rem 0.8rem 0.45rem;\r
    }\r
    .node-finder-head strong {\r
      color: var(--text);\r
      font-size: 0.6875rem;\r
      letter-spacing: 0.08em;\r
      text-transform: uppercase;\r
    }\r
    .node-finder[data-context="route-source"] .node-finder-head strong { color: var(--frontend-stroke); }\r
    .node-finder[data-context="route-target"] .node-finder-head strong { color: var(--security-stroke); }\r
    .node-finder-close {\r
      width: 1.75rem;\r
      height: 1.75rem;\r
      border: 0;\r
      border-radius: 0.35rem;\r
      background: transparent;\r
      color: var(--toolbar-text);\r
      font: inherit;\r
      font-size: 1rem;\r
      cursor: pointer;\r
    }\r
    .node-finder-close:hover,\r
    .node-finder-close:focus-visible { background: var(--toolbar-hover); }\r
    .node-finder-close:focus-visible,\r
    .node-finder-result:focus-visible {\r
      outline: 2px solid var(--frontend-stroke);\r
      outline-offset: -2px;\r
    }\r
    .node-finder-search {\r
      display: grid;\r
      grid-template-columns: auto minmax(0, 1fr) auto;\r
      align-items: center;\r
      gap: 0.55rem;\r
      margin: 0 0.55rem 0.55rem;\r
      padding: 0 0.7rem;\r
      min-height: 2.6rem;\r
      border: 1px solid var(--toolbar-border);\r
      border-radius: 0.55rem;\r
      background: color-mix(in srgb, var(--panel) 78%, transparent);\r
      transition: border-color 160ms ease-out, box-shadow 160ms ease-out;\r
    }\r
    html[data-preset="blueprint"] .node-finder-search { border-radius: 0.18rem; }\r
    .node-finder-search > span { color: var(--frontend-stroke); font-size: 0.875rem; }\r
    .node-finder-search:focus-within {\r
      border-color: var(--frontend-stroke);\r
      box-shadow: 0 0 0 2px color-mix(in srgb, var(--frontend-stroke) 20%, transparent);\r
    }\r
    .node-finder-input {\r
      appearance: none;\r
      width: 100%;\r
      min-width: 0;\r
      border: 0;\r
      outline: 0;\r
      background: transparent;\r
      color: var(--text);\r
      font: inherit;\r
      font-size: 0.75rem;\r
    }\r
    .node-finder-input:focus-visible { outline: none; }\r
    .node-finder-input::placeholder { color: var(--text-faint); }\r
    .node-finder kbd {\r
      padding: 0.1rem 0.32rem;\r
      border: 1px solid var(--toolbar-border);\r
      border-radius: 0.25rem;\r
      color: var(--text-faint);\r
      font: inherit;\r
      font-size: 0.5625rem;\r
    }\r
    .node-finder-results {\r
      display: grid;\r
      flex: 1 1 auto;\r
      gap: 0;\r
      min-height: 0;\r
      max-height: min(18rem, 48vh);\r
      margin: 0 0.55rem 0.45rem;\r
      padding: 0;\r
      overflow-y: auto;\r
      overscroll-behavior: contain;\r
      border: 1px solid color-mix(in srgb, var(--toolbar-border) 78%, transparent);\r
      border-radius: 0.55rem;\r
      background: color-mix(in srgb, var(--panel) 54%, transparent);\r
      scroll-padding-block: 0.25rem;\r
      scrollbar-width: thin;\r
    }\r
    html[data-preset="blueprint"] .node-finder-results { border-radius: 0.18rem; }\r
    .node-finder-result {\r
      display: grid;\r
      grid-template-columns: minmax(0, 1fr) auto;\r
      gap: 0.2rem 0.75rem;\r
      width: 100%;\r
      min-height: 3.25rem;\r
      padding: 0.58rem 0.65rem;\r
      border: 0;\r
      border-radius: 0;\r
      background: transparent;\r
      color: var(--text);\r
      font: inherit;\r
      text-align: left;\r
      cursor: pointer;\r
      transition: background-color 160ms ease-out;\r
    }\r
    .node-finder-result:not(:last-child) {\r
      border-bottom: 1px solid color-mix(in srgb, var(--toolbar-border) 62%, transparent);\r
    }\r
    .node-finder-result:hover,\r
    .node-finder-result:focus-visible {\r
      position: relative;\r
      z-index: 1;\r
      background: color-mix(in srgb, var(--frontend-fill) 48%, var(--toolbar-hover));\r
    }\r
    .node-finder-result strong {\r
      overflow: hidden;\r
      font-size: 0.75rem;\r
      line-height: 1.25;\r
      text-overflow: ellipsis;\r
      white-space: nowrap;\r
    }\r
    .node-finder-result small {\r
      grid-column: 1 / -1;\r
      overflow: hidden;\r
      color: var(--text-faint);\r
      font-size: 0.5625rem;\r
      letter-spacing: 0.015em;\r
      text-overflow: ellipsis;\r
      white-space: nowrap;\r
    }\r
    .node-finder-result em {\r
      align-self: center;\r
      color: var(--frontend-stroke);\r
      font-size: 0.625rem;\r
      font-style: normal;\r
    }\r
    .node-finder[data-context^="route-"] .node-finder-result em {\r
      padding: 0.1rem 0.3rem;\r
      border: 1px solid color-mix(in srgb, currentColor 52%, transparent);\r
      border-radius: 999px;\r
      font-size: 0.5rem;\r
      font-weight: 800;\r
      letter-spacing: 0.05em;\r
      text-transform: uppercase;\r
    }\r
    .node-finder[data-context="route-target"] .node-finder-result em { color: var(--security-stroke); }\r
    .node-finder-empty {\r
      padding: 1.1rem 0.75rem 1.25rem;\r
      color: var(--text-faint);\r
      font-size: 0.6875rem;\r
      text-align: center;\r
    }\r
    .node-finder-status {\r
      margin: 0;\r
      padding: 0.1rem 0.8rem 0.65rem;\r
      color: var(--text-faint);\r
      font-size: 0.5625rem;\r
    }\r
\r
    .guided-views {\r
      display: grid;\r
      grid-template-columns: 2.75rem minmax(0, 1fr) 2.75rem auto;\r
      align-items: stretch;\r
      gap: 0.35rem;\r
      min-width: 0;\r
      margin: 0 0 0.75rem;\r
      padding: 0.35rem;\r
      border: 1px solid var(--toolbar-border);\r
      border-radius: 0.85rem;\r
      background: var(--toolbar-bg);\r
      background: linear-gradient(120deg, var(--toolbar-bg), color-mix(in srgb, var(--toolbar-bg) 82%, var(--frontend-fill)));\r
      box-shadow: 0 12px 36px rgba(0, 0, 0, 0.16);\r
      backdrop-filter: blur(12px);\r
    }\r
    .guided-views[hidden] { display: none; }\r
\r
    html[data-preset="blueprint"] .guided-views {\r
      border-color: var(--panel-border);\r
      border-radius: 0.35rem;\r
      background:\r
        linear-gradient(90deg, color-mix(in srgb, var(--frontend-fill) 36%, transparent), transparent 24%),\r
        var(--toolbar-bg);\r
      box-shadow: 0 12px 28px rgba(0, 0, 0, 0.12);\r
    }\r
    html[data-preset="blueprint"] .guided-views button { border-radius: 0.2rem; }\r
    html[data-preset="blueprint"] .guided-view-progress { border-radius: 0; }\r
    html[data-preset="blueprint"] .guided-view-progress span { border-radius: 0; }\r
    .guided-views button {\r
      min-width: 0;\r
      padding: 0.45rem 0.6rem;\r
      border-radius: 0.55rem;\r
      font-size: 0.75rem;\r
    }\r
    .guided-views > #guided-view-prev,\r
    .guided-views > #guided-view-next { min-width: 2.75rem; min-height: 2.75rem; }\r
    .guided-views button:disabled { opacity: 0.3; cursor: default; }\r
    .guided-view-copy {\r
      min-width: 0;\r
      padding: 0.2rem 0.5rem;\r
      border-left: 1px solid var(--toolbar-border);\r
      overflow: hidden;\r
    }\r
    .guided-view-meta {\r
      display: flex;\r
      align-items: center;\r
      gap: 0.5rem;\r
      min-height: 1rem;\r
      margin-bottom: 0.12rem;\r
      color: var(--frontend-stroke);\r
      font-size: 0.5625rem;\r
      font-weight: 700;\r
      letter-spacing: 0.12em;\r
      text-transform: uppercase;\r
    }\r
    .guided-view-handoff {\r
      box-sizing: border-box;\r
      height: 1rem;\r
      min-width: 0;\r
      max-width: 15rem;\r
      overflow: hidden;\r
      padding: 0 0.38rem;\r
      border: 1px solid color-mix(in srgb, var(--frontend-stroke) 46%, transparent);\r
      border-radius: 999px;\r
      color: var(--toolbar-text);\r
      background: color-mix(in srgb, var(--frontend-fill) 44%, transparent);\r
      font-size: 0.5rem;\r
      line-height: calc(1rem - 2px);\r
      letter-spacing: 0.06em;\r
      text-overflow: ellipsis;\r
      white-space: nowrap;\r
    }\r
    .guided-view-handoff[hidden] { display: none; }\r
    html[data-preset="blueprint"] .guided-view-handoff { border-radius: 0.15rem; }\r
    .chapter-handoff-overlay { pointer-events: none; }\r
    .chapter-handoff-anchor {\r
      fill: color-mix(in srgb, var(--frontend-fill) 10%, transparent);\r
      stroke: var(--frontend-stroke);\r
      stroke-width: 2;\r
      stroke-dasharray: 4 4;\r
      vector-effect: non-scaling-stroke;\r
      opacity: 0.96;\r
      animation: archify-chapter-anchor 0.42s cubic-bezier(0.22, 1, 0.36, 1) both;\r
    }\r
    svg[data-chapter-handoff] [data-node-id][data-chapter-role="stay"] { opacity: 1; }\r
    svg[data-chapter-handoff] [data-node-id][data-chapter-role="enter"] { opacity: 0.78; }\r
    svg[data-chapter-handoff] [data-node-id][data-chapter-role="leave"] { opacity: 0.26; }\r
    @keyframes archify-chapter-anchor {\r
      0% { opacity: 0.35; stroke-dashoffset: 8; }\r
      45% { opacity: 1; }\r
      100% { opacity: 0.72; stroke-dashoffset: 0; }\r
    }\r
    .guided-view-progress {\r
      width: 3.5rem;\r
      height: 2px;\r
      overflow: hidden;\r
      border-radius: 999px;\r
      background: var(--toolbar-border);\r
    }\r
    .guided-view-progress span {\r
      display: block;\r
      width: 100%;\r
      height: 100%;\r
      border-radius: inherit;\r
      background: var(--frontend-stroke);\r
      transform: scaleX(0);\r
      transform-origin: left center;\r
    }\r
    .guided-view-copy strong,\r
    .guided-view-copy small { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }\r
    .guided-view-copy strong { color: var(--toolbar-text); font-size: 0.75rem; line-height: 1.35; }\r
    .guided-view-copy small { margin-top: 0; color: var(--text-muted); font-size: 0.625rem; line-height: 1.35; }\r
    .guided-story-caption {\r
      display: grid;\r
      grid-template-columns: auto minmax(0, 1fr) auto;\r
      gap: 0.12rem 0.55rem;\r
      align-items: center;\r
      min-width: 0;\r
      margin-top: 0.18rem;\r
      padding: 0.3rem 0.5rem;\r
      overflow: hidden;\r
      border: 1px solid color-mix(in srgb, var(--frontend-stroke) 32%, var(--toolbar-border));\r
      border-radius: 0.58rem;\r
      background: color-mix(in srgb, var(--frontend-fill) 26%, transparent);\r
      animation: archify-story-caption-in 140ms cubic-bezier(0.22, 1, 0.36, 1) both;\r
    }\r
    .guided-story-caption[hidden] { display: none; }\r
    .guided-story-caption-index {\r
      grid-row: 1 / span 2;\r
      align-self: stretch;\r
      display: inline-grid;\r
      min-width: 3.3rem;\r
      place-items: center;\r
      padding-right: 0.52rem;\r
      border-right: 1px solid color-mix(in srgb, var(--frontend-stroke) 28%, var(--toolbar-border));\r
      color: var(--frontend-stroke);\r
      font-size: 0.5625rem;\r
      font-weight: 800;\r
      letter-spacing: 0.08em;\r
      text-transform: uppercase;\r
    }\r
    .guided-story-caption strong,\r
    .guided-story-caption small {\r
      display: block;\r
      min-width: 0;\r
      overflow: hidden;\r
      text-overflow: ellipsis;\r
      white-space: nowrap;\r
    }\r
    .guided-story-caption strong { color: var(--toolbar-text); font-size: 0.6875rem; line-height: 1.3; }\r
    .guided-story-caption small { color: var(--text-muted); font-size: 0.5625rem; line-height: 1.35; }\r
    .guided-story-caption-next {\r
      grid-column: 3;\r
      grid-row: 1 / span 2;\r
      display: grid;\r
      min-width: 6.4rem;\r
      max-width: 9.5rem;\r
      align-self: stretch;\r
      align-content: center;\r
      padding-left: 0.58rem;\r
      border-left: 1px solid color-mix(in srgb, var(--frontend-stroke) 22%, var(--toolbar-border));\r
    }\r
    .guided-story-caption-next[hidden] { display: none; }\r
    .guided-story-caption-next small {\r
      color: color-mix(in srgb, var(--frontend-stroke) 72%, var(--text-muted));\r
      font-weight: 800;\r
      letter-spacing: 0.09em;\r
      text-transform: uppercase;\r
    }\r
    .guided-story-caption-next strong { color: var(--text-muted); font-weight: 700; }\r
    html[data-preset="blueprint"] .guided-story-caption { border-radius: 0.2rem; }\r
    .guided-views[data-story-beat] .guided-view-copy > #guided-view-label,\r
    .guided-views[data-story-beat] .guided-view-copy > #guided-view-note { display: none; }\r
    @keyframes archify-story-caption-in {\r
      from { opacity: 0; transform: translateY(3px); }\r
      to { opacity: 1; transform: translateY(0); }\r
    }\r
    .guided-view-trail {\r
      display: flex;\r
      align-items: center;\r
      gap: 0.28rem;\r
      min-width: 0;\r
      min-height: 1.7rem;\r
      margin-top: 0;\r
      padding: 0;\r
      overflow-x: auto;\r
      color: var(--text-faint);\r
      overscroll-behavior-x: contain;\r
      touch-action: pan-x;\r
      scrollbar-width: none;\r
      white-space: nowrap;\r
    }\r
    .guided-view-trail[hidden] { display: none; }\r
    .guided-view-trail::-webkit-scrollbar { display: none; }\r
    .guided-view-trail .guided-view-stop {\r
      appearance: none;\r
      box-sizing: border-box;\r
      display: inline-flex;\r
      flex: 0 0 auto;\r
      align-items: center;\r
      gap: 0.28rem;\r
      min-height: 1.5rem;\r
      padding: 0.1rem 0.3rem 0.1rem 0.18rem;\r
      border: 1px solid transparent;\r
      border-radius: 999px;\r
      background: transparent;\r
      color: var(--text-muted);\r
      cursor: pointer;\r
      font-family: inherit;\r
      font-size: 0.5625rem;\r
      font-weight: 650;\r
      letter-spacing: 0.02em;\r
      line-height: 1;\r
      transition: background 140ms ease, border-color 140ms ease, color 140ms ease, opacity 140ms ease;\r
    }\r
    .guided-view-stop:hover {\r
      border-color: color-mix(in srgb, var(--frontend-stroke) 36%, transparent);\r
      background: color-mix(in srgb, var(--frontend-fill) 34%, transparent);\r
    }\r
    .guided-view-stop:focus-visible {\r
      outline: 2px solid var(--frontend-stroke);\r
      outline-offset: 1px;\r
    }\r
    .guided-view-stop:disabled { cursor: wait; }\r
    .guided-view-stop::before {\r
      display: inline-grid;\r
      width: 1rem;\r
      height: 1rem;\r
      place-items: center;\r
      border: 1px solid color-mix(in srgb, var(--frontend-stroke) 54%, var(--toolbar-border));\r
      border-radius: 50%;\r
      background: color-mix(in srgb, var(--frontend-fill) 58%, var(--toolbar-bg));\r
      color: var(--frontend-stroke);\r
      content: attr(data-story-number);\r
      font-size: 0.5rem;\r
      line-height: 1;\r
    }\r
    .guided-view-stop + .guided-view-stop::after {\r
      order: -1;\r
      color: color-mix(in srgb, var(--frontend-stroke) 58%, var(--text-faint));\r
      content: '\\00b7';\r
      font-size: 0.65rem;\r
    }\r
    .guided-view-stop[data-story-link="forward"]::after { content: '\\2192'; }\r
    .guided-view-stop[data-story-link="reverse"]::after { content: '\\2190'; }\r
    .guided-view-stop[data-story-link="multiple"]::after { content: '\\21c4'; }\r
    .guided-view-stop[data-story-beat-state="pending"] { opacity: 0.38; }\r
    .guided-view-stop[data-story-beat-state="next"] {\r
      border-style: dashed;\r
      border-color: color-mix(in srgb, var(--frontend-stroke) 42%, var(--toolbar-border));\r
      color: color-mix(in srgb, var(--toolbar-text) 68%, var(--text-muted));\r
      opacity: 0.58;\r
    }\r
    .guided-view-stop[data-story-beat-state="past"] { color: var(--text-muted); opacity: 0.76; }\r
    .guided-view-stop[data-story-beat-state="active"] {\r
      border-color: color-mix(in srgb, var(--frontend-stroke) 72%, var(--toolbar-border));\r
      background: color-mix(in srgb, var(--frontend-fill) 42%, transparent);\r
      color: var(--toolbar-text);\r
      font-weight: 800;\r
      opacity: 1;\r
    }\r
    .guided-view-stop[data-story-beat-state="active"]::before {\r
      border-color: var(--frontend-stroke);\r
      box-shadow: 0 0 10px color-mix(in srgb, var(--frontend-stroke) 54%, transparent);\r
    }\r
    html[data-preset="blueprint"] .guided-view-stop,\r
    html[data-preset="blueprint"] .guided-view-stop::before { border-radius: 0.1rem; }\r
    html[data-preset="blueprint"] .guided-view-stop[data-story-beat-state="active"]::before { box-shadow: none; }\r
    .guided-view-actions { display: flex; align-items: stretch; gap: 0.2rem; }\r
    .guided-view-actions button { white-space: nowrap; }\r
    .guided-view-play {\r
      display: inline-flex;\r
      align-items: center;\r
      justify-content: center;\r
      gap: 0.38rem;\r
      min-width: 6.25rem !important;\r
      color: var(--frontend-stroke) !important;\r
      font-size: 0.625rem !important;\r
    }\r
    .guided-view-play[aria-pressed="true"] { background: var(--toolbar-hover); }\r
    .guided-view-all { min-width: 3.25rem !important; color: var(--text-muted) !important; font-size: 0.625rem !important; }\r
    .guided-view-beat-link {\r
      display: inline-flex;\r
      align-items: center;\r
      justify-content: center;\r
      gap: 0.3rem;\r
      min-width: 5.4rem !important;\r
      min-height: 1.5rem;\r
      color: var(--text-muted) !important;\r
      font-size: 0.5625rem !important;\r
      letter-spacing: 0.025em;\r
      transition: background 140ms ease, border-color 140ms ease, color 140ms ease;\r
    }\r
    .guided-view-beat-link:not(:disabled):hover {\r
      border-color: color-mix(in srgb, var(--frontend-stroke) 52%, var(--toolbar-border));\r
      color: var(--frontend-stroke) !important;\r
    }\r
    .guided-view-beat-link[data-copy-state="copied"] {\r
      border-color: color-mix(in srgb, var(--backend-stroke) 58%, var(--toolbar-border));\r
      background: color-mix(in srgb, var(--backend-fill) 46%, transparent);\r
      color: var(--backend-stroke) !important;\r
    }\r
    .guided-view-index {\r
      grid-column: 1 / -1;\r
      min-width: 0;\r
      padding: 0.28rem 0.12rem 0.08rem;\r
      overflow: hidden;\r
      border-top: 1px solid color-mix(in srgb, var(--toolbar-border) 72%, transparent);\r
    }\r
    @media (min-width: 721px) {\r
      html[data-present="true"]:not([data-embed="true"]) .guided-views[data-playing="true"] .guided-view-index,\r
      html[data-present="true"]:not([data-embed="true"]) .guided-views[data-playing="true"] .guided-view-beat-link,\r
      html[data-present="true"]:not([data-embed="true"]) .guided-views[data-playing="true"] .guided-view-all,\r
      html[data-present="true"]:not([data-embed="true"]) .guided-views[data-playing="true"] .guided-view-trail,\r
      html[data-present="true"]:not([data-embed="true"]) .guided-views[data-playing="true"] .guided-view-copy > #guided-view-label,\r
      html[data-present="true"]:not([data-embed="true"]) .guided-views[data-playing="true"] .guided-view-copy > #guided-view-note { display: none; }\r
      html[data-present="true"]:not([data-embed="true"]) .guided-views[data-playing="true"] .guided-story-caption { margin-top: 0.08rem; }\r
    }\r
    .guided-view-chapters {\r
      display: flex;\r
      gap: 0.28rem;\r
      min-width: 0;\r
      margin: 0;\r
      padding: 0.08rem 0.05rem 0.2rem;\r
      overflow-x: auto;\r
      list-style: none;\r
      scroll-padding-inline: 0.05rem;\r
      scroll-snap-type: x proximity;\r
      scrollbar-width: none;\r
    }\r
    .guided-view-chapters::-webkit-scrollbar { display: none; }\r
    .guided-view-chapters li {\r
      display: flex;\r
      flex: 1 1 0;\r
      min-width: 9.5rem;\r
      scroll-snap-align: center;\r
    }\r
    .guided-view-chapter {\r
      position: relative;\r
      display: grid !important;\r
      grid-template-columns: 1.55rem minmax(0, 1fr) auto;\r
      align-items: center;\r
      width: 100%;\r
      min-height: 2.75rem;\r
      padding: 0.36rem 0.48rem !important;\r
      overflow: hidden;\r
      border: 1px solid color-mix(in srgb, var(--toolbar-border) 86%, transparent) !important;\r
      border-radius: 0.48rem !important;\r
      background: color-mix(in srgb, var(--toolbar-bg) 88%, transparent) !important;\r
      color: var(--text-muted) !important;\r
      text-align: left;\r
      transition: background 0.16s ease, border-color 0.16s ease, opacity 0.16s ease;\r
    }\r
    .guided-view-chapter:hover {\r
      border-color: color-mix(in srgb, var(--frontend-stroke) 58%, var(--toolbar-border)) !important;\r
      background: color-mix(in srgb, var(--frontend-fill) 42%, var(--toolbar-bg)) !important;\r
    }\r
    .guided-view-chapter:focus-visible {\r
      outline: 2px solid var(--frontend-stroke);\r
      outline-offset: 1px;\r
    }\r
    .guided-view-chapter-index {\r
      display: inline-grid;\r
      width: 1.32rem;\r
      height: 1.32rem;\r
      place-items: center;\r
      border: 1px solid color-mix(in srgb, var(--frontend-stroke) 48%, var(--toolbar-border));\r
      border-radius: 50%;\r
      color: var(--frontend-stroke);\r
      font-size: 0.5rem;\r
      font-weight: 800;\r
      letter-spacing: 0.03em;\r
    }\r
    .guided-view-chapter-title {\r
      min-width: 0;\r
      overflow: hidden;\r
      color: var(--toolbar-text);\r
      font-size: 0.625rem;\r
      font-weight: 700;\r
      line-height: 1.3;\r
      text-overflow: ellipsis;\r
      white-space: nowrap;\r
    }\r
    .guided-view-chapter-count {\r
      grid-column: 3;\r
      grid-row: 1;\r
      margin-left: 0.38rem;\r
      color: var(--text-faint);\r
      font-size: 0.5rem;\r
      font-style: normal;\r
      font-weight: 650;\r
      white-space: nowrap;\r
    }\r
    .guided-view-chapter-delta {\r
      display: inline-flex;\r
      grid-column: 3;\r
      grid-row: 1;\r
      align-items: center;\r
      gap: 0.22rem;\r
      margin-left: 0.38rem;\r
      color: var(--text-faint);\r
      font-size: 0.5rem;\r
      font-weight: 750;\r
      letter-spacing: 0.01em;\r
      white-space: nowrap;\r
    }\r
    .guided-view-chapter-delta[hidden] { display: none; }\r
    .guided-view-chapter-delta [data-delta-kind="stay"] { color: var(--text-muted); }\r
    .guided-view-chapter-delta [data-delta-kind="enter"] { color: var(--frontend-stroke); }\r
    .guided-view-chapter-delta [data-delta-kind="leave"] { color: var(--security-stroke); }\r
    .guided-view-chapter[data-preview-active="true"] {\r
      border-color: color-mix(in srgb, var(--frontend-stroke) 72%, var(--toolbar-border)) !important;\r
      background: color-mix(in srgb, var(--frontend-fill) 54%, var(--toolbar-bg)) !important;\r
    }\r
    .guided-view-chapter[data-chapter-position="current"] {\r
      border: 2px solid var(--frontend-stroke) !important;\r
      padding: calc(0.36rem - 1px) calc(0.48rem - 1px) !important;\r
      box-shadow: inset 3px 0 0 var(--frontend-stroke);\r
      color: var(--toolbar-text) !important;\r
    }\r
    .guided-view-chapter[data-chapter-position="current"] .guided-view-chapter-index {\r
      background: var(--frontend-stroke);\r
      color: var(--bg);\r
    }\r
    .guided-view-chapter[data-chapter-position="before"] {\r
      border-style: solid !important;\r
      opacity: 0.72;\r
    }\r
    .guided-view-chapter[data-chapter-position="after"] { border-style: dashed !important; }\r
    html[data-preset="signal-flow"] .guided-view-chapter[data-chapter-position="current"] {\r
      box-shadow: inset 3px 0 0 var(--frontend-stroke), 0 0 18px color-mix(in srgb, var(--frontend-stroke) 18%, transparent);\r
    }\r
    html[data-preset="blueprint"] .guided-view-chapter,\r
    html[data-preset="blueprint"] .guided-view-chapter-index { border-radius: 0.12rem !important; }\r
\r
    /* Story Shelf — keep every authored chapter and the Play action visible,\r
       but do not spend a second row on unavailable director controls before\r
       the reader enters a chapter. Existing data-active-view state expands\r
       the full guided surface without a new toggle or stored preference. */\r
    .guided-views[data-active-view="all"] {\r
      grid-template-columns: minmax(11rem, .72fr) auto minmax(0, 2fr);\r
      align-items: center;\r
      padding: 0.28rem 0.35rem;\r
    }\r
    .guided-views[data-active-view="all"] > #guided-view-prev,\r
    .guided-views[data-active-view="all"] > #guided-view-next,\r
    .guided-views[data-active-view="all"] .guided-view-beat-link,\r
    .guided-views[data-active-view="all"] .guided-view-all { display: none; }\r
    .guided-views[data-active-view="all"] .guided-view-copy {\r
      grid-column: 1;\r
      grid-row: 1;\r
      padding: 0.1rem 0.55rem;\r
    }\r
    .guided-views[data-active-view="all"] .guided-view-copy > #guided-view-note { display: none; }\r
    .guided-views[data-active-view="all"] .guided-view-actions {\r
      display: block;\r
      grid-column: 2;\r
      grid-row: 1;\r
    }\r
    .guided-views[data-active-view="all"] .guided-view-play { min-height: 2.75rem; }\r
    .guided-views[data-active-view="all"] .guided-view-index {\r
      grid-column: 3;\r
      grid-row: 1;\r
      padding: 0 0.08rem 0 0.42rem;\r
      border-top: 0;\r
      border-left: 1px solid color-mix(in srgb, var(--toolbar-border) 72%, transparent);\r
    }\r
    .guided-views[data-active-view="all"] .guided-view-chapters {\r
      gap: 0.3rem;\r
      padding: 0;\r
    }\r
\r
    .cards {\r
      display: grid;\r
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));\r
      gap: 1rem;\r
      margin-top: 2rem;\r
    }\r
\r
    .card {\r
      background: var(--panel);\r
      border-radius: 0.75rem;\r
      border: 1px solid var(--panel-border);\r
      padding: 1.25rem;\r
    }\r
\r
    html[data-preset="signal-flow"] .card {\r
      background: linear-gradient(145deg, rgba(10, 24, 43, 0.86), rgba(5, 12, 24, 0.92));\r
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.035);\r
    }\r
    html[data-preset="signal-flow"][data-theme="light"] .card {\r
      background: linear-gradient(145deg, rgba(255, 255, 255, 0.92), rgba(237, 246, 250, 0.9));\r
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.82), 0 12px 32px rgba(45, 78, 99, 0.08);\r
    }\r
\r
    /* Preserve the one-screen guarantee on ordinary laptop displays. The\r
       high-screen expansion above must not trade a fuller canvas for page\r
       scrolling at 900–1080px heights. */\r
    @media (min-width: 768px) and (max-height: 1100px) {\r
      .header { margin-bottom: 1rem; }\r
      .diagram-container {\r
        padding: 0.875rem;\r
        padding-bottom: calc(0.875rem + var(--archify-nav-reserve));\r
      }\r
      .cards { margin-top: 1rem; }\r
      .card { padding: 1rem; }\r
    }\r
    @media (min-width: 768px) and (max-height: 920px) {\r
      body { padding-block: 1.25rem; }\r
      .header { margin-bottom: 0.875rem; }\r
      .cards { margin-top: 0.75rem; }\r
      html[data-nav-stage-rail="true"] body { padding-block: 0.375rem; }\r
      html[data-nav-stage-rail="true"] .header { margin-bottom: 0.5rem; }\r
      html[data-nav-stage-rail="true"] .guided-views { margin-bottom: 0.375rem; }\r
      html[data-nav-stage-rail="true"] .diagram-container[data-nav-stage-rail="true"] { padding-top: 0.5rem; }\r
      html[data-nav-stage-rail="true"] .cards { margin-top: 0.375rem; }\r
    }\r
\r
    html[data-preset="blueprint"] .card {\r
      position: relative;\r
      border-color: var(--panel-border);\r
      border-radius: 0.3rem;\r
      background: var(--panel);\r
      box-shadow: none;\r
    }\r
    html[data-preset="blueprint"] .card::before {\r
      content: "";\r
      position: absolute;\r
      top: -1px;\r
      left: 1rem;\r
      width: 2.5rem;\r
      border-top: 2px solid var(--frontend-stroke);\r
    }\r
\r
    html[data-preset="editorial"] .card {\r
      position: relative;\r
      border-radius: 0.28rem;\r
      background: var(--panel);\r
      box-shadow: 0 10px 28px color-mix(in srgb, #000 10%, transparent);\r
    }\r
    html[data-preset="editorial"] .card::before {\r
      position: absolute;\r
      top: -1px;\r
      left: 1.25rem;\r
      width: 3.25rem;\r
      border-top: 3px solid var(--arrow-emphasis);\r
      content: "";\r
    }\r
    html[data-preset="editorial"] .card-dot { border-radius: 0; transform: rotate(45deg) scale(0.78); }\r
\r
    .card-header {\r
      display: flex;\r
      align-items: center;\r
      gap: 0.5rem;\r
      margin-bottom: 0.75rem;\r
    }\r
\r
    .card-dot {\r
      width: 8px;\r
      height: 8px;\r
      border-radius: 50%;\r
    }\r
\r
    .card-dot.cyan     { background: var(--frontend-stroke); }\r
    .card-dot.emerald  { background: var(--backend-stroke); }\r
    .card-dot.violet   { background: var(--database-stroke); }\r
    .card-dot.amber    { background: var(--cloud-stroke); }\r
    .card-dot.rose     { background: var(--security-stroke); }\r
    .card-dot.orange   { background: var(--messagebus-stroke); }\r
    .card-dot.slate    { background: var(--external-stroke); }\r
\r
    .card h3 { font-size: 0.875rem; font-weight: 600; color: var(--text); }\r
\r
    .card ul {\r
      list-style: none;\r
      color: var(--text-muted);\r
      font-size: 0.75rem;\r
    }\r
\r
    .card li { margin-bottom: 0.375rem; }\r
\r
    /* ==========================================================\r
       Print stylesheet — hide interactive controls, force light,\r
       drop the grid so the diagram doesn't waste ink, use landscape\r
       so wide diagrams fit, pack summary cards into 2 columns to\r
       avoid an orphan card on a trailing page.\r
       ========================================================== */\r
    @page { size: landscape; margin: 1.5cm; }\r
\r
    @media print {\r
      /* Force the FULL light palette — including component fills/strokes and\r
         lane/arrow colors — so printing from dark theme doesn't put neon\r
         strokes and translucent dark fills on white paper. */\r
      :root, [data-theme="dark"], [data-theme="light"] {\r
        --bg: #ffffff;\r
        --grid: transparent;\r
        --panel: #ffffff;\r
        --panel-border: #e2e8f0;\r
        --text: #0f172a;\r
        --text-muted: #475569;\r
        --text-dim: #94a3b8;\r
        --text-faint: #64748b;\r
        --mask: #ffffff;\r
        --lane-fill: rgba(248, 250, 252, 0.65);\r
        --lane-stroke: #cbd5e1;\r
        --arrow: #94a3b8;\r
        --arrow-emphasis: #059669;\r
        --frontend-fill:    rgba(34, 211, 238, 0.15);\r
        --frontend-stroke:  #0891b2;\r
        --backend-fill:     rgba(52, 211, 153, 0.18);\r
        --backend-stroke:   #059669;\r
        --database-fill:    rgba(167, 139, 250, 0.2);\r
        --database-stroke:  #7c3aed;\r
        --cloud-fill:       rgba(251, 191, 36, 0.18);\r
        --cloud-stroke:     #d97706;\r
        --security-fill:    rgba(251, 113, 133, 0.15);\r
        --security-stroke:  #e11d48;\r
        --messagebus-fill:  rgba(251, 146, 60, 0.15);\r
        --messagebus-stroke:#ea580c;\r
        --external-fill:    rgba(148, 163, 184, 0.18);\r
        --external-stroke:  #64748b;\r
      }\r
      body { background: #ffffff !important; padding: 0; }\r
      .container { max-width: none; }\r
      .toolbar, .diagram-nav, .focus-chip, .guided-views, .archify-toast, .no-print { display: none !important; }\r
      .chapter-handoff-overlay { display: none !important; }\r
      svg [data-node-id][data-chapter-role] { opacity: 1 !important; }\r
      svg[data-chapter-preview] [data-node-id],\r
      svg[data-chapter-preview] [data-edge-from] { opacity: 1 !important; filter: none !important; }\r
      .diagram-container, .card { box-shadow: none; border-color: #e2e8f0; }\r
      .diagram-container { --archify-nav-reserve: 0px !important; }\r
      html[data-preset="signal-flow"] .diagram-container,\r
      html[data-preset="signal-flow"] .card { background: #ffffff; }\r
      .cards { grid-template-columns: 1fr 1fr; }\r
      /* Ensure elements break sensibly across pages */\r
      .card { break-inside: avoid; page-break-inside: avoid; }\r
      .diagram-container { break-inside: avoid; page-break-inside: avoid; }\r
      .diagram-container svg [data-detail] {\r
        opacity: 1 !important;\r
        pointer-events: auto !important;\r
      }\r
      .diagram-container svg [data-detail-anchor] { transform: none !important; }\r
      .diagram-container svg[data-lens-active] [data-node-id],\r
      .diagram-container svg[data-lens-active] [data-edge-from],\r
      .diagram-container svg[data-legend-preview-active] [data-node-id],\r
      .diagram-container svg[data-legend-preview-active] [data-edge-from] {\r
        opacity: 1 !important;\r
        filter: none !important;\r
      }\r
      [data-legend-bridge-runtime] { display: none !important; }\r
      .semantic-lens-overlay { display: none !important; }\r
      .relationship-hit-overlay { display: none !important; }\r
      .relationship-pulse-overlay { display: none !important; }\r
      .route-probe-overlay, .route-journey-overlay { display: none !important; }\r
      .story-trail-overlay,\r
      .story-carrier-overlay { display: none !important; }\r
      .diagram-container svg[data-focus-active] [data-node-id],\r
      .diagram-container svg[data-focus-active] [data-edge-from],\r
      .diagram-container svg[data-reach-active] [data-node-id],\r
      .diagram-container svg[data-reach-active] [data-edge-from],\r
      .diagram-container svg[data-story-beat] [data-story-step],\r
      .diagram-container svg[data-story-beat] [data-edge-from][data-story-beat-step],\r
      .diagram-container svg[data-route-active] [data-node-id],\r
      .diagram-container svg[data-route-active] [data-edge-from] {\r
        opacity: 1 !important;\r
        filter: none !important;\r
        animation: none !important;\r
      }\r
      h1, .subtitle { color: #0f172a; }\r
    }\r
\r
    /* ==========================================================\r
       TOOLBAR (theme toggle + export menu)\r
       ========================================================== */\r
    .toolbar {\r
      position: fixed;\r
      top: 1rem;\r
      right: 1rem;\r
      display: flex;\r
      align-items: center;\r
      gap: 0.5rem;\r
      padding: 0;\r
      border: 0;\r
      background: transparent;\r
      box-shadow: none;\r
      z-index: 100;\r
    }\r
    .toolbar button {\r
      background: var(--toolbar-bg);\r
      color: var(--toolbar-text);\r
      border: 1px solid var(--toolbar-border);\r
      padding: 0.5rem 0.875rem;\r
      border-radius: 0.625rem;\r
      font-family: inherit;\r
      font-size: 0.75rem;\r
      font-weight: 500;\r
      cursor: pointer;\r
      white-space: nowrap;\r
      backdrop-filter: blur(10px);\r
      box-shadow: 0 4px 14px rgba(0, 0, 0, 0.08);\r
      transition: background 0.15s, border-color 0.15s, color 0.15s;\r
      display: inline-flex;\r
      align-items: center;\r
      gap: 0.375rem;\r
      min-height: 2.75rem;\r
    }\r
    .toolbar button:hover {\r
      background: var(--toolbar-hover);\r
      border-color: color-mix(in srgb, var(--arrow) 62%, var(--toolbar-border));\r
    }\r
    .toolbar button[aria-expanded="true"],\r
    .toolbar button[aria-pressed="true"]:not(#btn-theme) {\r
      background: color-mix(in srgb, var(--frontend-stroke) 10%, var(--toolbar-hover));\r
      border-color: color-mix(in srgb, var(--frontend-stroke) 48%, var(--toolbar-border));\r
    }\r
    .toolbar #btn-export {\r
      padding-right: 0.82rem;\r
      padding-left: 0.82rem;\r
    }\r
    .toolbar #btn-export:hover,\r
    .toolbar #btn-export[aria-expanded="true"] {\r
      color: var(--toolbar-text);\r
      background: color-mix(in srgb, var(--frontend-stroke) 10%, var(--toolbar-hover));\r
      border-color: color-mix(in srgb, var(--frontend-stroke) 54%, var(--toolbar-border));\r
    }\r
    .toolbar button:focus-visible {\r
      outline: 2px solid var(--frontend-stroke);\r
      outline-offset: 2px;\r
    }\r
    .toolbar #btn-motion[hidden] { display: none !important; }\r
    .toolbar #btn-motion { min-width: 4.4rem; }\r
    .toolbar #btn-motion:disabled { cursor: default; opacity: 0.58; }\r
    .toolbar .preset-wrap,\r
    .toolbar .export-wrap {\r
      position: relative;\r
    }\r
    .toolbar-icon {\r
      display: inline-block;\r
      width: 0.95rem;\r
      height: 0.95rem;\r
      flex: 0 0 auto;\r
      background: currentColor;\r
      -webkit-mask-position: center;\r
      -webkit-mask-repeat: no-repeat;\r
      -webkit-mask-size: contain;\r
      mask-position: center;\r
      mask-repeat: no-repeat;\r
      mask-size: contain;\r
    }\r
    .toolbar-chevron {\r
      width: 0.65rem;\r
      height: 0.65rem;\r
      transition: transform 0.15s ease;\r
    }\r
    [aria-expanded="true"] > .toolbar-chevron { transform: rotate(180deg); }\r
    [data-theme="light"] #theme-icon {\r
      -webkit-mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 20 20'%3E%3Cg fill='none' stroke='black' stroke-width='1.7' stroke-linecap='round'%3E%3Ccircle cx='10' cy='10' r='3.1'/%3E%3Cpath d='M10 2.2v1.4M10 16.4v1.4M2.2 10h1.4M16.4 10h1.4M4.5 4.5l1 1M14.5 14.5l1 1M15.5 4.5l-1 1M5.5 14.5l-1 1'/%3E%3C/g%3E%3C/svg%3E");\r
      mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 20 20'%3E%3Cg fill='none' stroke='black' stroke-width='1.7' stroke-linecap='round'%3E%3Ccircle cx='10' cy='10' r='3.1'/%3E%3Cpath d='M10 2.2v1.4M10 16.4v1.4M2.2 10h1.4M16.4 10h1.4M4.5 4.5l1 1M14.5 14.5l1 1M15.5 4.5l-1 1M5.5 14.5l-1 1'/%3E%3C/g%3E%3C/svg%3E");\r
    }\r
    [data-theme="dark"] #theme-icon {\r
      -webkit-mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 20 20'%3E%3Cpath d='M15.2 12.7A6.3 6.3 0 017.3 4.8a6.3 6.3 0 107.9 7.9Z' fill='none' stroke='black' stroke-width='1.7' stroke-linejoin='round'/%3E%3C/svg%3E");\r
      mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 20 20'%3E%3Cpath d='M15.2 12.7A6.3 6.3 0 017.3 4.8a6.3 6.3 0 107.9 7.9Z' fill='none' stroke='black' stroke-width='1.7' stroke-linejoin='round'/%3E%3C/svg%3E");\r
    }\r
    #btn-present[aria-pressed="false"] #present-icon {\r
      -webkit-mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 20 20'%3E%3Cpath d='M7.2 3.2h-4v4M12.8 3.2h4v4M7.2 16.8h-4v-4M12.8 16.8h4v-4' fill='none' stroke='black' stroke-width='1.7' stroke-linecap='round'/%3E%3C/svg%3E");\r
      mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 20 20'%3E%3Cpath d='M7.2 3.2h-4v4M12.8 3.2h4v4M7.2 16.8h-4v-4M12.8 16.8h4v-4' fill='none' stroke='black' stroke-width='1.7' stroke-linecap='round'/%3E%3C/svg%3E");\r
    }\r
    #btn-present[aria-pressed="true"] #present-icon {\r
      -webkit-mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 20 20'%3E%3Cpath d='M7.2 7.2h-4v-4M12.8 7.2h4v-4M7.2 12.8h-4v4M12.8 12.8h4v4' fill='none' stroke='black' stroke-width='1.7' stroke-linecap='round'/%3E%3C/svg%3E");\r
      mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 20 20'%3E%3Cpath d='M7.2 7.2h-4v-4M12.8 7.2h4v-4M7.2 12.8h-4v4M12.8 12.8h4v4' fill='none' stroke='black' stroke-width='1.7' stroke-linecap='round'/%3E%3C/svg%3E");\r
    }\r
    .toolbar-chevron {\r
      -webkit-mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 12 12'%3E%3Cpath d='m3 4.5 3 3 3-3' fill='none' stroke='black' stroke-width='1.7' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E");\r
      mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 12 12'%3E%3Cpath d='m3 4.5 3 3 3-3' fill='none' stroke='black' stroke-width='1.7' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E");\r
    }\r
    .toolbar #btn-preset { min-width: 5.4rem; }\r
    .preset-control-mark {\r
      width: 0.58rem;\r
      height: 0.58rem;\r
      flex: 0 0 auto;\r
      border: 1px solid var(--frontend-stroke);\r
      border-radius: 0.2rem;\r
      background: color-mix(in srgb, var(--frontend-stroke) 28%, transparent);\r
      transition: border-radius 0.15s, box-shadow 0.15s, transform 0.15s;\r
    }\r
    #btn-preset[data-preset-option="signal-flow"] .preset-control-mark {\r
      border-radius: 50%;\r
      box-shadow: 0 0 10px color-mix(in srgb, var(--frontend-stroke) 78%, transparent);\r
    }\r
    #btn-preset[data-preset-option="blueprint"] .preset-control-mark {\r
      border-radius: 0.06rem;\r
      background: transparent;\r
      box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--frontend-stroke) 32%, transparent);\r
      transform: rotate(45deg) scale(0.84);\r
    }\r
    #btn-preset[data-preset-option="editorial"] .preset-control-mark {\r
      border-color: var(--arrow-emphasis);\r
      border-radius: 0;\r
      background: var(--arrow-emphasis);\r
      box-shadow: 0 0 0 2px color-mix(in srgb, var(--arrow-emphasis) 14%, transparent);\r
      transform: rotate(45deg) scale(0.72);\r
    }\r
    .toolbar .preset-menu {\r
      position: absolute;\r
      top: calc(100% + 0.375rem);\r
      right: 0;\r
      display: none;\r
      width: 18.5rem;\r
      max-width: calc(100vw - 2rem);\r
      padding: 0.45rem;\r
      border: 1px solid var(--toolbar-border);\r
      border-radius: 0.875rem;\r
      background: var(--toolbar-menu-bg);\r
      box-shadow: 0 18px 48px rgba(0, 0, 0, 0.24);\r
    }\r
    .toolbar .preset-menu.open { display: block; }\r
    .toolbar .preset-menu.open,\r
    .toolbar .export-menu.open {\r
      animation: toolbar-menu-in 0.16s cubic-bezier(0.2, 0.8, 0.2, 1);\r
      transform-origin: top right;\r
    }\r
    @keyframes toolbar-menu-in {\r
      from { opacity: 0; transform: translateY(-0.25rem) scale(0.985); }\r
      to { opacity: 1; transform: translateY(0) scale(1); }\r
    }\r
    .preset-menu-heading {\r
      display: flex;\r
      align-items: baseline;\r
      justify-content: space-between;\r
      gap: 1rem;\r
      padding: 0.42rem 0.6rem 0.55rem;\r
      color: var(--text-faint);\r
      font-size: 0.56rem;\r
      letter-spacing: 0.13em;\r
      text-transform: uppercase;\r
    }\r
    .preset-menu-heading span:last-child {\r
      font-size: 0.52rem;\r
      letter-spacing: 0.04em;\r
      text-transform: none;\r
    }\r
    .toolbar .preset-option {\r
      display: grid;\r
      grid-template-columns: 2rem minmax(0, 1fr) 1rem;\r
      align-items: center;\r
      gap: 0.68rem;\r
      width: 100%;\r
      min-height: 3.35rem;\r
      padding: 0.5rem 0.62rem;\r
      border: 0;\r
      border-radius: 0.5rem;\r
      background: transparent;\r
      box-shadow: none;\r
      backdrop-filter: none;\r
      text-align: left;\r
    }\r
    .toolbar .preset-option:hover,\r
    .toolbar .preset-option:focus-visible { background: var(--toolbar-hover); }\r
    .toolbar .preset-option[aria-checked="true"] {\r
      background: color-mix(in srgb, var(--frontend-stroke) 9%, transparent);\r
      border-color: color-mix(in srgb, var(--frontend-stroke) 36%, transparent);\r
    }\r
    .preset-option-swatch {\r
      position: relative;\r
      width: 2rem;\r
      height: 1.55rem;\r
      overflow: hidden;\r
      border: 1px solid #64748b;\r
      border-radius: 0.24rem;\r
      background: #0f172a;\r
      box-shadow: inset 0 0 0 1px rgba(255,255,255,0.04);\r
    }\r
    .preset-option-swatch::before,\r
    .preset-option-swatch::after { position: absolute; content: ""; }\r
    .preset-option-swatch.classic::before {\r
      top: 0.42rem;\r
      right: 0.35rem;\r
      bottom: 0.42rem;\r
      left: 0.35rem;\r
      border: 1px solid #22d3ee;\r
      border-radius: 0.16rem;\r
      background: rgba(34, 211, 238, 0.14);\r
    }\r
    .preset-option-swatch.signal-flow {\r
      border-color: #29415f;\r
      background: linear-gradient(135deg, #07101e 10%, #10243c 100%);\r
    }\r
    .preset-option-swatch.signal-flow::before {\r
      top: 50%;\r
      right: 0.2rem;\r
      left: 0.2rem;\r
      height: 1px;\r
      background: linear-gradient(90deg, #67e8f9, #c4b5fd);\r
      box-shadow: 0 0 8px #67e8f9;\r
    }\r
    .preset-option-swatch.signal-flow::after {\r
      top: calc(50% - 0.13rem);\r
      right: 0.28rem;\r
      width: 0.26rem;\r
      height: 0.26rem;\r
      border-radius: 50%;\r
      background: #67e8f9;\r
      box-shadow: 0 0 7px #67e8f9;\r
    }\r
    .preset-option-swatch.blueprint {\r
      border-color: #34799a;\r
      border-radius: 0.08rem;\r
      background-color: #0a2031;\r
      background-image:\r
        linear-gradient(rgba(102, 217, 239, 0.18) 1px, transparent 1px),\r
        linear-gradient(90deg, rgba(102, 217, 239, 0.18) 1px, transparent 1px);\r
      background-size: 0.42rem 0.42rem;\r
    }\r
    .preset-option-swatch.blueprint::before {\r
      top: 0.34rem;\r
      right: 0.38rem;\r
      bottom: 0.34rem;\r
      left: 0.38rem;\r
      border: 1px solid #66d9ef;\r
    }\r
    .preset-option-swatch.editorial {\r
      border-color: #b8aa94;\r
      border-radius: 0.08rem;\r
      background: repeating-linear-gradient(0deg, #f2eee5 0 0.34rem, #d8d0c2 0.36rem, #f2eee5 0.38rem);\r
    }\r
    .preset-option-swatch.editorial::before {\r
      top: 0;\r
      bottom: 0;\r
      left: 0.42rem;\r
      width: 1px;\r
      background: #c9502d;\r
      opacity: 0.72;\r
    }\r
    .preset-option-swatch.editorial::after {\r
      top: 0.52rem;\r
      right: 0.45rem;\r
      width: 0.38rem;\r
      height: 0.38rem;\r
      background: #c9502d;\r
      transform: rotate(45deg);\r
    }\r
    .preset-option-copy { min-width: 0; }\r
    .preset-option-copy strong,\r
    .preset-option-copy small { display: block; }\r
    .preset-option-copy strong {\r
      color: var(--toolbar-text);\r
      font-size: 0.72rem;\r
      font-weight: 600;\r
    }\r
    .preset-option-copy small {\r
      margin-top: 0.16rem;\r
      overflow: hidden;\r
      color: var(--text-faint);\r
      font-size: 0.57rem;\r
      font-weight: 400;\r
      white-space: nowrap;\r
      text-overflow: ellipsis;\r
    }\r
    .preset-option-check {\r
      display: inline-block;\r
      width: 0.9rem;\r
      height: 0.9rem;\r
      color: var(--frontend-stroke);\r
      background: currentColor;\r
      -webkit-mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Cpath d='m3 8.5 3 3 7-7' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E");\r
      -webkit-mask-position: center;\r
      -webkit-mask-repeat: no-repeat;\r
      -webkit-mask-size: contain;\r
      mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Cpath d='m3 8.5 3 3 7-7' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E");\r
      mask-position: center;\r
      mask-repeat: no-repeat;\r
      mask-size: contain;\r
      opacity: 0;\r
    }\r
    .preset-option[aria-checked="true"] .preset-option-check { opacity: 1; }\r
    html[data-preset="editorial"] .toolbar button,\r
    html[data-preset="editorial"] .preset-menu,\r
    html[data-preset="editorial"] .export-menu,\r
    html[data-preset="editorial"] .overview-map,\r
    html[data-preset="editorial"] .semantic-lens,\r
    html[data-preset="editorial"] .route-probe,\r
    html[data-preset="editorial"] .focus-chip,\r
    html[data-preset="editorial"] .diagram-guide,\r
    html[data-preset="editorial"] .node-finder,\r
    html[data-preset="editorial"] .guided-views,\r
    html[data-preset="editorial"] .share-chapter-cue {\r
      border-radius: 0.3rem;\r
    }\r
    .motion-control-dot {\r
      width: 0.46rem;\r
      height: 0.46rem;\r
      flex: 0 0 auto;\r
      border: 1px solid var(--frontend-stroke);\r
      border-radius: 50%;\r
      background: var(--frontend-stroke);\r
      box-shadow: 0 0 9px color-mix(in srgb, var(--frontend-stroke) 72%, transparent);\r
    }\r
    #btn-motion[aria-pressed="false"] .motion-control-dot {\r
      background: transparent;\r
      box-shadow: none;\r
    }\r
    .toolbar .export-menu {\r
      position: absolute;\r
      top: calc(100% + 0.375rem);\r
      right: 0;\r
      background: var(--toolbar-menu-bg);\r
      border: 1px solid var(--toolbar-border);\r
      width: 19rem;\r
      max-width: calc(100vw - 2rem);\r
      max-height: calc(100vh - 5.5rem);\r
      overflow-y: auto;\r
      border-radius: 0.875rem;\r
      padding: 0.55rem;\r
      display: none;\r
      flex-direction: column;\r
      box-shadow: 0 18px 48px rgba(0,0,0,0.24);\r
    }\r
    .toolbar .export-menu.open { display: flex; }\r
    .export-menu-header {\r
      display: flex;\r
      align-items: flex-start;\r
      justify-content: space-between;\r
      gap: 1rem;\r
      padding: 0.5rem 0.55rem 0.72rem;\r
    }\r
    .export-menu-header strong,\r
    .export-menu-header span { display: block; }\r
    .export-menu-header strong {\r
      color: var(--toolbar-text);\r
      font-size: 0.78rem;\r
      font-weight: 650;\r
      letter-spacing: -0.015em;\r
    }\r
    .export-menu-header span {\r
      margin-top: 0.16rem;\r
      color: var(--text-faint);\r
      font-size: 0.56rem;\r
    }\r
    .export-menu-header kbd {\r
      padding: 0.16rem 0.36rem;\r
      border: 1px solid var(--toolbar-border);\r
      border-radius: 0.3rem;\r
      color: var(--text-faint);\r
      background: color-mix(in srgb, var(--toolbar-border) 16%, transparent);\r
      font-family: inherit;\r
      font-size: 0.54rem;\r
      font-weight: 600;\r
    }\r
    .export-menu-section {\r
      display: grid;\r
      grid-template-columns: minmax(0, 1fr);\r
      gap: 0.18rem;\r
    }\r
    .export-menu-section + .export-menu-section {\r
      margin-top: 0.42rem;\r
      padding-top: 0.42rem;\r
      border-top: 1px solid color-mix(in srgb, var(--toolbar-border) 68%, transparent);\r
    }\r
    .export-menu-heading {\r
      grid-column: 1 / -1;\r
      display: block;\r
      padding: 0.24rem 0.55rem 0.2rem;\r
      color: var(--text-faint);\r
      font-size: 0.54rem;\r
      font-weight: 600;\r
      letter-spacing: 0.12em;\r
      text-transform: uppercase;\r
    }\r
    .toolbar .export-menu button {\r
      display: grid;\r
      grid-template-columns: 1.15rem minmax(0, 1fr);\r
      align-items: center;\r
      column-gap: 0.52rem;\r
      background: transparent;\r
      border: 1px solid transparent;\r
      box-shadow: none;\r
      backdrop-filter: none;\r
      width: 100%;\r
      min-height: 3rem;\r
      text-align: left;\r
      padding: 0.48rem 0.55rem;\r
      border-radius: 0.5rem;\r
      white-space: nowrap;\r
    }\r
    .export-item-copy {\r
      display: block;\r
      min-width: 0;\r
    }\r
    .export-item-copy strong,\r
    .export-item-copy small { display: block; }\r
    .export-item-copy strong {\r
      overflow: hidden;\r
      color: inherit;\r
      font-size: 0.7rem;\r
      font-weight: 550;\r
      text-overflow: ellipsis;\r
    }\r
    .export-item-copy small {\r
      margin-top: 0.12rem;\r
      overflow: hidden;\r
      color: var(--text-faint);\r
      font-size: 0.55rem;\r
      font-weight: 450;\r
      text-overflow: ellipsis;\r
    }\r
    .toolbar .export-menu button::before {\r
      width: 1rem;\r
      height: 1rem;\r
      background: currentColor;\r
      content: "";\r
      opacity: 0.72;\r
      -webkit-mask-position: center;\r
      -webkit-mask-repeat: no-repeat;\r
      -webkit-mask-size: contain;\r
      mask-position: center;\r
      mask-repeat: no-repeat;\r
      mask-size: contain;\r
    }\r
    .toolbar .export-menu button[data-format="share-card"]::before,\r
    .toolbar .export-menu button[data-action="route-share-card"]::before,\r
    .toolbar .export-menu button[data-action="reach-share-card"]::before {\r
      -webkit-mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 20 20'%3E%3Cpath fill='none' stroke='black' stroke-width='1.7' d='M3 4.5h14v11H3zM6 12l2.5-2.5 2 2 1.5-1.5 2 2'/%3E%3Ccircle cx='13.8' cy='7.3' r='1.2' fill='black'/%3E%3C/svg%3E");\r
      mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 20 20'%3E%3Cpath fill='none' stroke='black' stroke-width='1.7' d='M3 4.5h14v11H3zM6 12l2.5-2.5 2 2 1.5-1.5 2 2'/%3E%3Ccircle cx='13.8' cy='7.3' r='1.2' fill='black'/%3E%3C/svg%3E");\r
    }\r
    .toolbar .export-menu button[data-action^="copy"]::before {\r
      -webkit-mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 20 20'%3E%3Crect x='6' y='6' width='10' height='10' rx='1.5' fill='none' stroke='black' stroke-width='1.7'/%3E%3Cpath d='M4 13H3.5A1.5 1.5 0 012 11.5v-8A1.5 1.5 0 013.5 2h8A1.5 1.5 0 0113 3.5V4' fill='none' stroke='black' stroke-width='1.7'/%3E%3C/svg%3E");\r
      mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 20 20'%3E%3Crect x='6' y='6' width='10' height='10' rx='1.5' fill='none' stroke='black' stroke-width='1.7'/%3E%3Cpath d='M4 13H3.5A1.5 1.5 0 012 11.5v-8A1.5 1.5 0 013.5 2h8A1.5 1.5 0 0113 3.5V4' fill='none' stroke='black' stroke-width='1.7'/%3E%3C/svg%3E");\r
    }\r
    .toolbar .export-menu button[data-format="png"]::before,\r
    .toolbar .export-menu button[data-format="jpeg"]::before,\r
    .toolbar .export-menu button[data-format="webp"]::before {\r
      -webkit-mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 20 20'%3E%3Cpath d='M5 2.5h7l3 3v12H5zM12 2.5v3h3' fill='none' stroke='black' stroke-width='1.7'/%3E%3Cpath d='M7.5 14l2-2 1.5 1.5 1.5-1.5' fill='none' stroke='black' stroke-width='1.7'/%3E%3C/svg%3E");\r
      mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 20 20'%3E%3Cpath d='M5 2.5h7l3 3v12H5zM12 2.5v3h3' fill='none' stroke='black' stroke-width='1.7'/%3E%3Cpath d='M7.5 14l2-2 1.5 1.5 1.5-1.5' fill='none' stroke='black' stroke-width='1.7'/%3E%3C/svg%3E");\r
    }\r
    .toolbar .export-menu button[data-format="svg"]::before,\r
    .toolbar .export-menu button[data-format="webm"]::before {\r
      -webkit-mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 20 20'%3E%3Cpath d='M10 2.5l7 4v7l-7 4-7-4v-7zM3 6.5l7 4 7-4M10 10.5v7' fill='none' stroke='black' stroke-width='1.7'/%3E%3C/svg%3E");\r
      mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 20 20'%3E%3Cpath d='M10 2.5l7 4v7l-7 4-7-4v-7zM3 6.5l7 4 7-4M10 10.5v7' fill='none' stroke='black' stroke-width='1.7'/%3E%3C/svg%3E");\r
    }\r
    .toolbar .export-menu button[data-format="share-card"],\r
    .toolbar .export-menu button[data-action="route-share-card"],\r
    .toolbar .export-menu button[data-action="reach-share-card"] {\r
      min-height: 3.35rem;\r
      color: var(--toolbar-text);\r
      background: color-mix(in srgb, var(--frontend-stroke) 8%, transparent);\r
      border-color: color-mix(in srgb, var(--frontend-stroke) 24%, var(--toolbar-border));\r
    }\r
    .toolbar .export-menu button[hidden] { display: none; }\r
    .toolbar .export-menu button:hover {\r
      background: var(--toolbar-hover);\r
    }\r
    .toolbar .export-menu button:focus-visible {\r
      background: var(--toolbar-hover);\r
      outline-offset: -2px;\r
    }\r
    .toolbar .export-menu button:disabled {\r
      color: var(--text-faint);\r
      background: color-mix(in srgb, var(--toolbar-border) 18%, transparent);\r
      cursor: not-allowed;\r
    }\r
    .toolbar .export-menu button:disabled:hover {\r
      border-color: transparent;\r
    }\r
    .toolbar .export-menu .hint {\r
      color: var(--text-faint);\r
      font-size: 0.55rem;\r
    }\r
\r
    /* Toast — brief feedback for actions like "copied" */\r
    .archify-toast {\r
      position: fixed;\r
      top: 1rem;\r
      left: 50%;\r
      transform: translateX(-50%) translateY(-8px);\r
      background: var(--toolbar-menu-bg);\r
      color: var(--text);\r
      border: 1px solid var(--toolbar-border);\r
      padding: 0.5rem 1rem;\r
      border-radius: 0.5rem;\r
      font-family: inherit;\r
      font-size: 0.75rem;\r
      opacity: 0;\r
      transition: opacity 0.2s, transform 0.2s;\r
      z-index: 200;\r
      pointer-events: none;\r
      box-shadow: 0 4px 20px rgba(0,0,0,0.25);\r
    }\r
    .archify-toast.show {\r
      opacity: 1;\r
      transform: translateX(-50%) translateY(0);\r
    }\r
\r
    @media (max-width: 720px) {\r
      body { padding: 1rem; }\r
      .toolbar .preset-menu,\r
      .toolbar .export-menu {\r
        position: fixed;\r
        top: 4.5rem;\r
        right: 1rem;\r
        left: 1rem;\r
        width: auto;\r
        max-width: none;\r
      }\r
      .toolbar {\r
        position: relative;\r
        justify-content: flex-end;\r
        width: max-content;\r
        max-width: 100%;\r
        margin-left: auto;\r
        margin-bottom: 1rem;\r
      }\r
      .header { margin-bottom: 1.25rem; padding-right: 0; }\r
      html[data-preset="signal-flow"] .header,\r
      html[data-preset="blueprint"] .header,\r
      html[data-preset="editorial"] .header { padding-right: 0; }\r
      .header-row {\r
        gap: 0.75rem;\r
        align-items: flex-start;\r
      }\r
      html[data-preset="signal-flow"] .header-row,\r
      html[data-preset="blueprint"] .header-row,\r
      html[data-preset="editorial"] .header-row { flex-wrap: wrap; }\r
      html[data-preset="signal-flow"] .header-row::after {\r
        margin-left: 0;\r
        order: 3;\r
      }\r
      html[data-preset="blueprint"] .header-row::after {\r
        margin-left: 0;\r
        order: 3;\r
      }\r
      html[data-preset="editorial"] .header-row::after {\r
        margin-left: 0;\r
        order: 3;\r
      }\r
      h1 {\r
        font-size: 1.25rem;\r
        line-height: 1.25;\r
      }\r
      .subtitle {\r
        margin-left: 0;\r
        font-size: 0.8125rem;\r
        line-height: 1.55;\r
      }\r
      .diagram-container {\r
        padding: 0.75rem;\r
        border-radius: 0.75rem;\r
      }\r
      html:not([data-embed="true"]) .diagram-container {\r
        padding: 0.75rem 0.75rem 4.25rem;\r
      }\r
      html:not([data-embed="true"]) .diagram-container[data-wide-diagram="true"] {\r
        overflow-x: auto;\r
        overflow-y: hidden;\r
        overscroll-behavior-x: contain;\r
        scrollbar-width: thin;\r
        scroll-behavior: smooth;\r
      }\r
      html:not([data-embed="true"]) .diagram-container[data-wide-diagram="true"] > svg {\r
        min-width: 720px;\r
      }\r
      html:not([data-embed="true"]) .diagram-container[data-wide-diagram="true"] .diagram-nav,\r
      html:not([data-embed="true"]) .diagram-container[data-wide-diagram="true"] .overview-map,\r
      html:not([data-embed="true"]) .diagram-container[data-wide-diagram="true"] .focus-chip,\r
      html:not([data-embed="true"]) .diagram-container[data-wide-diagram="true"] .route-probe,\r
      html:not([data-embed="true"]) .diagram-container[data-wide-diagram="true"] .semantic-lens,\r
      html:not([data-embed="true"]) .diagram-container[data-wide-diagram="true"] .diagram-guide,\r
      html:not([data-embed="true"]) .diagram-container[data-wide-diagram="true"] .node-finder {\r
        transform: translateX(var(--archify-scroll-x, 0px));\r
      }\r
      .diagram-nav { right: 0.5rem; bottom: 0.5rem; }\r
      .diagram-nav button {\r
        min-width: 2.75rem;\r
        height: 2.75rem;\r
      }\r
      .diagram-nav [data-view="reset"] { min-width: 3.75rem; }\r
      .diagram-nav [data-view="reset"][data-detail-visible] { min-width: 4.35rem; }\r
      .overview-map {\r
        right: 0.5rem;\r
        bottom: 3.7rem;\r
        width: min(10.25rem, calc(100% - 1rem));\r
      }\r
      .overview-map[data-docked="true"] {\r
        right: var(--archify-radar-right, 0.5rem);\r
        top: var(--archify-radar-top, 0.5rem);\r
        bottom: auto;\r
        transform: none !important;\r
      }\r
      .overview-map[data-docked="true"][data-dock-side="left"] {\r
        right: auto;\r
        left: var(--archify-radar-left, 0.5rem);\r
      }\r
      .overview-map-surface { height: 4rem; }\r
      .overview-map-feedback { right: 0.5rem; bottom: 3.7rem; }\r
      .semantic-lens {\r
        right: 0.5rem;\r
        bottom: 3.7rem;\r
        width: calc(100% - 1rem);\r
        max-height: calc(100% - 4.2rem);\r
      }\r
      .semantic-lens[data-dock-side] { left: auto; right: 0.5rem; }\r
      .semantic-lens-kinds { max-height: min(12rem, 34vh); }\r
      .focus-chip {\r
        left: 0.5rem;\r
        top: 0.5rem;\r
        width: calc(100% - 1rem);\r
        max-width: none;\r
      }\r
      .relationship-lens-list { max-height: min(12rem, 38vh); }\r
      .relationship-lens-actions #btn-focus-relations { display: block; color: var(--database-stroke); }\r
      .focus-chip:not([data-relations-expanded="true"]) .relationship-lens-head { border-bottom-color: transparent; }\r
      .focus-chip:not([data-relations-expanded="true"]) .relationship-lens-list { display: none; }\r
      /* While a mobile reader previews one relationship, turn the full Lens\r
         into a compact peek card. This keeps the exact source and target on\r
         canvas instead of covering them with a long, scrollable list. */\r
      .focus-chip[data-relationship-previewing="true"] .relationship-lens-list {\r
        max-height: none;\r
        padding: 0.35rem;\r
        overflow: hidden;\r
      }\r
      .focus-chip[data-relationship-previewing="true"] .relationship-lens-group { margin: 0; }\r
      .focus-chip[data-relationship-previewing="true"] .relationship-lens-group-title,\r
      .focus-chip[data-relationship-previewing="true"] .relationship-lens-row:not([data-preview-active="true"]) {\r
        display: none;\r
      }\r
      .node-finder {\r
        top: 0.5rem;\r
        left: 0.5rem;\r
        width: min(22rem, calc(100% - 1rem));\r
        max-height: calc(100% - 1rem);\r
      }\r
      .diagram-guide {\r
        top: 0.5rem;\r
        right: 0.5rem;\r
        left: 0.5rem;\r
        width: auto;\r
        max-height: calc(100% - 1rem);\r
      }\r
      .diagram-guide-head { padding: 0.62rem 0.7rem 0.52rem; }\r
      .diagram-guide-stats { padding: 0.42rem 0.7rem; }\r
      .diagram-guide-actions {\r
        grid-template-columns: 1fr;\r
        gap: 0.28rem;\r
        padding: 0.42rem;\r
      }\r
      .diagram-guide-action {\r
        min-height: 3.1rem;\r
        padding: 0.42rem 0.48rem;\r
      }\r
      .diagram-guide-action small {\r
        display: block;\r
        overflow: hidden;\r
        text-overflow: ellipsis;\r
        white-space: nowrap;\r
      }\r
      .diagram-guide-index {\r
        width: 1.5rem;\r
        height: 1.5rem;\r
      }\r
      .diagram-guide-shortcuts { padding: 0.46rem 0.7rem 0.52rem; }\r
      .diagram-guide-action[data-guide-action="present"] { grid-column: auto; }\r
      .route-probe[data-guide-open="true"] {\r
        visibility: hidden;\r
        pointer-events: none;\r
      }\r
      .node-finder-results { max-height: min(16rem, 38vh); }\r
      .route-probe {\r
        left: 0.5rem;\r
        bottom: 3.7rem;\r
        width: calc(100% - 1rem);\r
        min-width: 0;\r
      }\r
      .route-probe[data-route-dock="top"] {\r
        top: 0.5rem;\r
        bottom: auto;\r
      }\r
      .route-probe[data-finder-open="true"] {\r
        visibility: hidden;\r
        pointer-events: none;\r
      }\r
      .route-probe-head { padding: 0.45rem 0.48rem 0.38rem; }\r
      .route-probe-path { padding: 0.35rem 0.48rem 0.2rem; }\r
      .route-probe-node { min-height: 2.75rem !important; }\r
      .route-journey-controls {\r
        grid-template-columns: 2.75rem minmax(0, 1fr) 2.75rem minmax(0, 1fr);\r
        padding: 0.08rem 0.48rem 0.32rem;\r
      }\r
      .route-journey-controls button { min-height: 2.75rem; }\r
      .route-probe-status { padding: 0.05rem 0.48rem 0.38rem; }\r
      .route-probe-node { max-width: 7.5rem; }\r
      .guided-views {\r
        grid-template-columns: 2.75rem minmax(0, 1fr) 2.75rem;\r
        gap: 0.2rem;\r
        padding: 0.25rem;\r
      }\r
      .guided-view-actions {\r
        grid-column: 1 / -1;\r
        display: grid;\r
        grid-template-columns: repeat(3, minmax(0, 1fr));\r
      }\r
      .guided-views > #guided-view-prev,\r
      .guided-views > #guided-view-next {\r
        align-self: center;\r
        height: 2.75rem;\r
      }\r
      .guided-view-play,\r
      .guided-view-all,\r
      .guided-view-beat-link { min-height: 2.75rem; }\r
      .guided-view-copy small { white-space: normal; }\r
      .guided-story-caption { padding: 0.32rem 0.45rem; }\r
      .guided-story-caption-index { min-width: 2.9rem; padding-right: 0.42rem; }\r
      .guided-story-caption strong,\r
      .guided-story-caption small { white-space: normal; }\r
      .guided-story-caption-next { display: none; }\r
      .guided-view-trail { min-height: 2rem; }\r
      .guided-view-trail .guided-view-stop {\r
        min-height: 2rem;\r
        padding: 0.22rem 0.42rem 0.22rem 0.28rem;\r
      }\r
      .guided-view-handoff { max-width: min(9rem, 32vw); }\r
      .guided-view-index { padding-top: 0.35rem; }\r
      .guided-view-chapters {\r
        gap: 0.35rem;\r
        scroll-padding-inline: 0.2rem;\r
      }\r
      .guided-view-chapters li {\r
        flex: 0 0 min(14rem, 78vw);\r
        min-width: 0;\r
      }\r
      .guided-view-chapter { min-height: 2.75rem; }\r
      .guided-views[data-active-view="all"] {\r
        grid-template-columns: minmax(0, 1fr) auto;\r
        gap: 0.2rem;\r
        padding: 0.25rem;\r
      }\r
      .guided-views[data-active-view="all"] .guided-view-copy {\r
        grid-column: 1;\r
        grid-row: 1;\r
      }\r
      .guided-views[data-active-view="all"] .guided-view-actions {\r
        grid-column: 2;\r
        grid-row: 1;\r
      }\r
      .guided-views[data-active-view="all"] .guided-view-play {\r
        min-width: 6rem !important;\r
        min-height: 2.75rem;\r
      }\r
      .guided-views[data-active-view="all"] .guided-view-index {\r
        grid-column: 1 / -1;\r
        grid-row: 2;\r
        padding: 0.3rem 0.08rem 0;\r
        border-top: 1px solid color-mix(in srgb, var(--toolbar-border) 72%, transparent);\r
        border-left: 0;\r
      }\r
      html[data-embed="true"][data-share-playback="true"] .share-chapter-cue:not([hidden]),\r
      html[data-embed="true"][data-share-moment="true"] .share-chapter-cue:not([hidden]) {\r
        top: 0.5rem;\r
        grid-template-columns: auto minmax(0, 1fr);\r
        gap: 0.28rem 0.55rem;\r
        width: calc(100% - 1rem);\r
        min-height: 0;\r
        padding: 0.45rem 0.55rem 0.55rem;\r
      }\r
      html[data-embed="true"][data-share-playback="true"] .diagram-container {\r
        padding-top: 4.25rem;\r
      }\r
      html[data-embed="true"][data-share-moment="true"] .diagram-container {\r
        padding-top: 4.25rem;\r
      }\r
      .share-chapter-index {\r
        min-width: 4.4rem;\r
        padding-right: 0.5rem;\r
      }\r
      .share-chapter-copy small { font-size: 0.46rem; }\r
      .share-chapter-route {\r
        grid-column: 1 / -1;\r
        font-size: 0.5rem;\r
        text-align: left;\r
      }\r
      .cards {\r
        grid-template-columns: 1fr;\r
        margin-top: 1rem;\r
      }\r
      html[data-present="true"]:not([data-embed="true"]) body { padding: 0.5rem; }\r
      html[data-present="true"]:not([data-embed="true"]) .container {\r
        gap: 0.5rem;\r
        height: calc(100dvh - 1rem);\r
      }\r
      html[data-present="true"]:not([data-embed="true"]) .toolbar {\r
        position: fixed;\r
        top: 0.5rem;\r
        right: 0.5rem;\r
        margin: 0;\r
        gap: 0.25rem;\r
      }\r
      html[data-present="true"]:not([data-embed="true"]) .toolbar button {\r
        min-height: 2.75rem;\r
        padding: 0.42rem 0.58rem;\r
      }\r
      html[data-present="true"]:not([data-embed="true"]) .header {\r
        min-height: 2.25rem;\r
        padding: 3.5rem 0 0;\r
      }\r
      html[data-present="true"]:not([data-embed="true"]) .header-row {\r
        min-height: 2.25rem;\r
        margin: 0;\r
        align-items: center;\r
        flex-wrap: nowrap;\r
      }\r
      html[data-present="true"]:not([data-embed="true"]) .header-row::after,\r
      html[data-present="true"]:not([data-embed="true"]) .pulse-dot,\r
      html[data-present="true"]:not([data-embed="true"]) .subtitle { display: none; }\r
      html[data-present="true"]:not([data-embed="true"]) h1 {\r
        flex: 1 1 auto;\r
        min-width: 0;\r
        max-width: 100%;\r
        overflow: hidden;\r
        font-size: 0.875rem;\r
        text-overflow: ellipsis;\r
        white-space: nowrap;\r
      }\r
      html[data-present="true"]:not([data-embed="true"]) .guided-views {\r
        padding: 0.2rem;\r
      }\r
      html[data-present="true"]:not([data-embed="true"]) .guided-view-copy small { display: none; }\r
      html[data-present="true"]:not([data-embed="true"]) .guided-story-caption small { display: block; }\r
      html[data-present="true"]:not([data-embed="true"]) .diagram-container { padding: 0.5rem 0.5rem 3.75rem; }\r
      html[data-present="true"]:not([data-embed="true"]) .diagram-container[data-wide-diagram="true"] > svg {\r
        width: 720px;\r
        height: auto;\r
        min-width: 720px;\r
      }\r
    }\r
\r
    @media (max-width: 420px) {\r
      .export-menu-section { grid-template-columns: 1fr; }\r
      .export-menu-heading,\r
      .toolbar .export-menu button[data-format="share-card"],\r
      .toolbar .export-menu button[data-action="route-share-card"],\r
      .toolbar .export-menu button[data-action="reach-share-card"] { grid-column: 1; }\r
    }\r
\r
    @media (prefers-reduced-motion: reduce) {\r
      .guided-story-caption { animation: none !important; }\r
      .toolbar .preset-menu.open,\r
      .toolbar .export-menu.open { animation: none; }\r
      .toolbar-chevron { transition: none; }\r
    }\r
\r
    @media (max-width: 360px) {\r
      .toolbar { gap: 0.25rem; }\r
      .toolbar button { padding-right: 0.58rem; padding-left: 0.58rem; }\r
      .toolbar #btn-motion { min-width: 4.4rem; padding-right: 0.58rem; padding-left: 0.58rem; }\r
      #theme-label, #preset-label, #present-label { display: none; }\r
      .guided-view-handoff { max-width: 6.5rem; }\r
    }\r
\r
    /* ==========================================================\r
       SVG SEMANTIC CLASSES — use these instead of inline fill/stroke\r
       ========================================================== */\r
    .c-grid       { stroke: var(--grid); fill: none; }\r
    .c-mask       { fill: var(--mask); stroke: none; }\r
\r
    .c-frontend   { fill: var(--frontend-fill);   stroke: var(--frontend-stroke); }\r
    .c-backend    { fill: var(--backend-fill);    stroke: var(--backend-stroke); }\r
    .c-database   { fill: var(--database-fill);   stroke: var(--database-stroke); }\r
    .c-cloud      { fill: var(--cloud-fill);      stroke: var(--cloud-stroke); }\r
    .c-security   { fill: var(--security-fill);   stroke: var(--security-stroke); }\r
    .c-messagebus { fill: var(--messagebus-fill); stroke: var(--messagebus-stroke); }\r
    .c-external   { fill: var(--external-fill);   stroke: var(--external-stroke); }\r
\r
    /* Text helpers */\r
    .t-primary { fill: var(--text); }\r
    .t-muted   { fill: var(--text-muted); }\r
    .t-dim     { fill: var(--text-dim); }\r
    .t-frontend   { fill: var(--frontend-stroke); }\r
    .t-backend    { fill: var(--backend-stroke); }\r
    .t-database   { fill: var(--database-stroke); }\r
    .t-cloud      { fill: var(--cloud-stroke); }\r
    .t-security   { fill: var(--security-stroke); }\r
    .t-messagebus { fill: var(--messagebus-stroke); }\r
    .t-external   { fill: var(--external-stroke); }\r
\r
    /* Semantic Sigils are small authored role stamps, not icons from a brand\r
       pack and not viewer controls. Prefix selectors with svg so the canonical\r
       export's SVG-only stylesheet collector keeps them automatically. */\r
    svg .semantic-sigil {\r
      fill: none;\r
      stroke: currentColor;\r
      stroke-width: 1.35;\r
      stroke-linecap: round;\r
      stroke-linejoin: round;\r
      opacity: 0.76;\r
      pointer-events: none;\r
    }\r
    svg .semantic-sigil > * { vector-effect: non-scaling-stroke; }\r
    svg .semantic-sigil .sigil-fill { fill: currentColor; stroke: none; }\r
    svg .s-frontend   { color: var(--frontend-stroke); }\r
    svg .s-backend    { color: var(--backend-stroke); }\r
    svg .s-database   { color: var(--database-stroke); }\r
    svg .s-cloud      { color: var(--cloud-stroke); }\r
    svg .s-security   { color: var(--security-stroke); }\r
    svg .s-messagebus { color: var(--messagebus-stroke); }\r
    svg .s-external   { color: var(--external-stroke); }\r
\r
    /* Brand Marks are authored identity badges. Their color is contained\r
       inside one neutral plate so vendor color never replaces Archify's\r
       semantic node and relationship vocabulary. */\r
    svg .brand-mark { pointer-events: none; }\r
    svg .brand-mark-badge { fill: #fff; stroke: none; }\r
    svg .brand-mark-frame {\r
      fill: none;\r
      stroke: #cbd5e1;\r
      stroke-width: 0.8;\r
      vector-effect: non-scaling-stroke;\r
    }\r
    svg .brand-mark-fallback {\r
      fill: none;\r
      stroke: #475569;\r
      stroke-width: 1.15;\r
      stroke-linecap: round;\r
      stroke-linejoin: round;\r
    }\r
    svg[data-preset="blueprint"] .brand-mark-badge,\r
    svg[data-preset="blueprint"] .brand-mark-frame { rx: 1px; }\r
\r
    /* Reading Depth is a viewer-only level-of-detail layer. MAP preserves the\r
       authored structure and primary labels, READ restores relationship labels\r
       and node context, and FULL restores tags and fine annotations. Semantic\r
       intent can reveal the relevant detail without moving any geometry. */\r
    svg [data-detail] { transition: opacity 160ms ease; }\r
    svg [data-detail-anchor] {\r
      transform-box: fill-box;\r
      transform-origin: center;\r
      transition: transform 160ms ease;\r
    }\r
    .diagram-container[data-detail-level="map"] svg [data-detail="context"],\r
    .diagram-container[data-detail-level="map"] svg [data-detail="fine"],\r
    .diagram-container[data-detail-level="read"] svg [data-detail="fine"] {\r
      opacity: 0;\r
      pointer-events: none;\r
    }\r
    .diagram-container[data-detail-level="map"] svg [data-detail-anchor] {\r
      transform: translateY(8px);\r
    }\r
\r
    /* Focus, lens, preview, route, and story states are stronger reader intent than\r
       the global zoom level. Reveal only their exact semantic matches. */\r
    svg[data-focus-active] [data-focus-match][data-detail],\r
    svg[data-focus-active] [data-focus-match] [data-detail],\r
    svg[data-reach-active] [data-reach-match][data-detail],\r
    svg[data-reach-active] [data-reach-match] [data-detail],\r
    svg[data-lens-active] [data-lens-match][data-detail],\r
    svg[data-lens-active] [data-lens-match] [data-detail],\r
    svg[data-legend-preview-active] [data-legend-preview-match][data-detail],\r
    svg[data-legend-preview-active] [data-legend-preview-match] [data-detail],\r
    svg[data-intent-trace-active] [data-intent-trace-match][data-detail],\r
    svg[data-intent-trace-active] [data-intent-trace-match] [data-detail],\r
    svg[data-route-active] [data-route-match][data-detail],\r
    svg[data-route-active] [data-route-match] [data-detail],\r
    svg[data-story-active] [data-story-step][data-detail],\r
    svg[data-story-active] [data-story-step] [data-detail],\r
    svg[data-relationship-preview-active] [data-relationship-preview][data-detail],\r
    svg[data-relationship-preview-active] [data-relationship-preview] [data-detail],\r
    svg [data-node-id]:hover [data-detail],\r
    svg [data-node-id]:focus-visible [data-detail] {\r
      opacity: 1;\r
      pointer-events: auto;\r
    }\r
    svg[data-focus-active] [data-focus-match] [data-detail-anchor],\r
    svg[data-reach-active] [data-reach-match] [data-detail-anchor],\r
    svg[data-lens-active] [data-lens-match] [data-detail-anchor],\r
    svg[data-legend-preview-active] [data-legend-preview-match] [data-detail-anchor],\r
    svg[data-intent-trace-active] [data-intent-trace-match] [data-detail-anchor],\r
    svg[data-route-active] [data-route-match] [data-detail-anchor],\r
    svg[data-story-active] [data-story-step] [data-detail-anchor],\r
    svg [data-node-id]:hover [data-detail-anchor],\r
    svg [data-node-id]:focus-visible [data-detail-anchor] { transform: none; }\r
\r
    /* Arrows */\r
    .a-default   { stroke: var(--arrow); fill: none; }\r
    .a-emphasis  { stroke: var(--arrow-emphasis); fill: none; }\r
    .a-security  { stroke: var(--security-stroke); fill: none; stroke-dasharray: 5,5; }\r
    .a-dashed    { stroke: var(--database-stroke); fill: none; stroke-dasharray: 4,4; }\r
\r
    /* Arrowhead markers reference these */\r
    .m-default   { fill: var(--arrow); }\r
    .m-emphasis  { fill: var(--arrow-emphasis); }\r
    .m-security  { fill: var(--security-stroke); }\r
    .m-dashed    { fill: var(--database-stroke); }\r
\r
    /* Stable semantic exploration hooks emitted by every renderer. */\r
    svg [data-node-id] {\r
      cursor: pointer;\r
      transition: opacity 0.18s ease, filter 0.18s ease;\r
    }\r
    svg [data-edge-from] { transition: opacity 0.18s ease, filter 0.18s ease; }\r
    svg [data-node-id]:hover,\r
    svg [data-node-id]:focus-visible {\r
      filter: drop-shadow(0 0 7px var(--frontend-stroke));\r
      outline: none;\r
    }\r
    /* Verified Source Beacons are installed at runtime only for nodes whose\r
       repository evidence passed the local revision/blob/line checks. They\r
       live inside the owning node so every focus, route, story, and guided\r
       view keeps one coherent opacity state. Export serialization removes\r
       them before producing the canonical SVG or any derived visual. */\r
    .source-evidence-beacon {\r
      pointer-events: none;\r
      opacity: 0.76;\r
      transition: opacity 160ms ease, filter 160ms ease;\r
    }\r
    .source-evidence-beacon rect {\r
      fill: color-mix(in srgb, var(--mask) 92%, var(--backend-stroke));\r
      stroke: color-mix(in srgb, var(--backend-stroke) 82%, var(--panel-border));\r
      stroke-width: 1;\r
      vector-effect: non-scaling-stroke;\r
    }\r
    .source-evidence-beacon text {\r
      fill: var(--backend-stroke);\r
      font-size: 5.5px;\r
      font-weight: 800;\r
      letter-spacing: 0.06em;\r
      text-anchor: middle;\r
      text-transform: uppercase;\r
    }\r
    svg [data-node-id]:hover .source-evidence-beacon,\r
    svg [data-node-id]:focus-visible .source-evidence-beacon,\r
    svg [data-node-id][data-focus-selected] .source-evidence-beacon {\r
      opacity: 1;\r
      filter: drop-shadow(0 0 4px color-mix(in srgb, var(--backend-stroke) 72%, transparent));\r
    }\r
    svg[data-preset="signal-flow"] .source-evidence-beacon { opacity: 0.9; }\r
    svg[data-preset="blueprint"] .source-evidence-beacon rect {\r
      rx: 0.8px;\r
      filter: none;\r
    }\r
    svg [data-legend-kind][role="button"] { cursor: pointer; }\r
    svg [data-legend-kind]:focus { outline: none; }\r
    svg [data-legend-hit] {\r
      fill: transparent;\r
      stroke: transparent;\r
      stroke-width: 1.4;\r
      pointer-events: all;\r
      vector-effect: non-scaling-stroke;\r
      transition: stroke 150ms ease, stroke-width 150ms ease, filter 150ms ease;\r
    }\r
    svg [data-legend-count-badge] { pointer-events: none; }\r
    svg [data-legend-count-badge] rect {\r
      fill: var(--mask);\r
      stroke: var(--panel-border);\r
      stroke-width: 1;\r
      vector-effect: non-scaling-stroke;\r
    }\r
    svg [data-legend-count-badge] text {\r
      fill: var(--text-muted);\r
      font-size: 8px;\r
      font-weight: 700;\r
      text-anchor: middle;\r
    }\r
    svg [data-legend-kind][role="button"]:hover [data-legend-hit] {\r
      stroke: color-mix(in srgb, var(--database-stroke) 58%, transparent);\r
    }\r
    svg [data-legend-kind][role="button"]:focus-visible [data-legend-hit] {\r
      stroke: var(--frontend-stroke);\r
      stroke-width: 1.8;\r
      filter: drop-shadow(0 0 3px var(--frontend-stroke));\r
    }\r
    svg [data-legend-kind][data-legend-selected] [data-legend-hit] {\r
      stroke: var(--database-stroke);\r
      stroke-width: 2.2;\r
      stroke-dasharray: 3 2;\r
    }\r
    svg [data-legend-kind][data-legend-selected] [data-legend-count-badge] rect {\r
      stroke: var(--database-stroke);\r
      stroke-width: 1.8;\r
    }\r
    svg [data-legend-kind][data-legend-zero] { opacity: 0.44; }\r
    svg[data-preset="signal-flow"] [data-legend-kind][data-legend-selected] [data-legend-hit] {\r
      filter: drop-shadow(0 0 4px var(--database-stroke));\r
    }\r
    svg[data-preset="blueprint"] [data-legend-hit],\r
    svg[data-preset="blueprint"] [data-legend-count-badge] rect { rx: 0; filter: none; }\r
    svg[data-legend-preview-active] [data-node-id],\r
    svg[data-legend-preview-active] [data-edge-from] { opacity: 0.11; }\r
    svg[data-legend-preview-active] [data-legend-preview-match] { opacity: 1; }\r
    svg[data-legend-preview-active] [data-legend-preview-peer] { opacity: 0.62; }\r
    svg[data-legend-preview-active] [data-legend-preview-selected] {\r
      filter: drop-shadow(0 0 8px var(--database-stroke));\r
    }\r
    svg[data-lens-active] [data-node-id],\r
    svg[data-lens-active] [data-edge-from] { opacity: 0.11; }\r
    svg[data-lens-active] [data-lens-match] { opacity: 1; }\r
    svg[data-lens-active] [data-lens-peer] { opacity: 0.62; }\r
    svg[data-lens-active] [data-lens-selected] {\r
      filter: drop-shadow(0 0 10px var(--database-stroke));\r
    }\r
    .semantic-lens-overlay { pointer-events: none; }\r
    .semantic-lens-flow {\r
      fill: none;\r
      stroke-width: 3.05;\r
      stroke-linecap: round;\r
      stroke-dasharray: 0.075 0.925;\r
      stroke-dashoffset: 0;\r
      vector-effect: non-scaling-stroke;\r
      opacity: 0.9;\r
      animation: archify-semantic-lens-flow 1.35s linear 1 both;\r
      animation-delay: var(--lens-flow-delay, 0s);\r
    }\r
    .semantic-lens-flow[data-direction="out"],\r
    .semantic-lens-flow[data-direction="forward"] {\r
      stroke: var(--frontend-stroke);\r
      filter: drop-shadow(0 0 3px var(--frontend-stroke));\r
    }\r
    .semantic-lens-flow[data-direction="in"],\r
    .semantic-lens-flow[data-direction="reverse"] {\r
      stroke: var(--database-stroke);\r
      filter: drop-shadow(0 0 3px var(--database-stroke));\r
    }\r
    .semantic-lens-flow[data-direction="within"] {\r
      stroke: var(--messagebus-stroke);\r
      filter: drop-shadow(0 0 3px var(--messagebus-stroke));\r
    }\r
    svg[data-preset="signal-flow"] .semantic-lens-flow {\r
      stroke-width: 3.7;\r
      opacity: 1;\r
    }\r
    svg[data-preset="signal-flow"] .semantic-lens-flow[data-direction="out"],\r
    svg[data-preset="signal-flow"] .semantic-lens-flow[data-direction="forward"] {\r
      filter: drop-shadow(0 0 6px var(--frontend-stroke));\r
    }\r
    svg[data-preset="signal-flow"] .semantic-lens-flow[data-direction="in"],\r
    svg[data-preset="signal-flow"] .semantic-lens-flow[data-direction="reverse"] {\r
      filter: drop-shadow(0 0 6px var(--database-stroke));\r
    }\r
    svg[data-preset="signal-flow"] .semantic-lens-flow[data-direction="within"] {\r
      filter: drop-shadow(0 0 6px var(--messagebus-stroke));\r
    }\r
    svg[data-preset="blueprint"] .semantic-lens-flow {\r
      stroke-width: 2.45;\r
      stroke-linecap: square;\r
      filter: none;\r
      opacity: 0.78;\r
    }\r
    html[data-embed="true"] .semantic-lens-overlay { display: none; }\r
    svg[data-focus-active] [data-node-id],\r
    svg[data-focus-active] [data-edge-from] { opacity: 0.13; }\r
    svg[data-focus-active] [data-focus-match] { opacity: 1; }\r
    svg[data-focus-active] [data-focus-selected] {\r
      filter: drop-shadow(0 0 10px var(--frontend-stroke));\r
    }\r
\r
    /* Authored Reachability is a bounded graph query over the relationships\r
       already present in the artifact. Upstream walks incoming edges;\r
       downstream walks outgoing edges. It never claims runtime causality and\r
       changes only viewer emphasis, not canonical geometry or export bytes. */\r
    svg[data-reach-active] [data-node-id],\r
    svg[data-reach-active] [data-edge-from] { opacity: 0.09; }\r
    svg[data-reach-active] [data-reach-match] { opacity: 1; }\r
    svg[data-reach-active="upstream"] [data-reach-origin] {\r
      filter: drop-shadow(0 0 11px var(--database-stroke));\r
    }\r
    svg[data-reach-active="downstream"] [data-reach-origin] {\r
      filter: drop-shadow(0 0 11px var(--backend-stroke));\r
    }\r
    svg[data-reach-active="upstream"] [data-edge-from][data-reach-match] {\r
      filter: drop-shadow(0 0 4px color-mix(in srgb, var(--database-stroke) 72%, transparent));\r
    }\r
    svg[data-reach-active="downstream"] [data-edge-from][data-reach-match] {\r
      filter: drop-shadow(0 0 4px color-mix(in srgb, var(--backend-stroke) 72%, transparent));\r
    }\r
    svg[data-preset="blueprint"][data-reach-active] [data-reach-origin],\r
    svg[data-preset="blueprint"][data-reach-active] [data-edge-from][data-reach-match] {\r
      filter: none;\r
    }\r
\r
    /* Direct Relationship Explorer makes authored paths a real input surface\r
       without changing their visible stroke or canonical SVG. A transparent\r
       runtime rail supplies forgiving pointer geometry; the exact authored\r
       path and endpoints continue to carry every visible state. */\r
    .relationship-hit-overlay { pointer-events: none; }\r
    .relationship-hit-target { outline: none; }\r
    .relationship-hit-rail {\r
      fill: none;\r
      stroke: transparent;\r
      stroke-width: 24;\r
      stroke-linecap: round;\r
      stroke-linejoin: round;\r
      vector-effect: non-scaling-stroke;\r
      pointer-events: stroke;\r
      cursor: pointer;\r
    }\r
    .relationship-focus-rail {\r
      fill: none;\r
      stroke: color-mix(in srgb, var(--frontend-stroke) 34%, transparent);\r
      stroke-width: 6;\r
      stroke-dasharray: 2 4;\r
      stroke-linecap: round;\r
      stroke-linejoin: round;\r
      vector-effect: non-scaling-stroke;\r
      pointer-events: none;\r
      opacity: 0;\r
    }\r
    .relationship-hit-target:focus-visible .relationship-focus-rail {\r
      opacity: 1;\r
    }\r
    svg[data-preset="blueprint"] .relationship-hit-target:focus-visible .relationship-focus-rail {\r
      stroke-linecap: square;\r
      filter: none;\r
    }\r
    svg[data-relationship-direct-active] [data-node-id],\r
    svg[data-relationship-direct-active] [data-edge-from] { opacity: 0.16; }\r
    svg[data-relationship-direct-active] [data-relationship-preview],\r
    svg[data-relationship-direct-active] [data-relationship-preview-node] { opacity: 1; }\r
    svg[data-focus-active]:not([data-relationship-pin-active]) .relationship-hit-rail,\r
    svg[data-story-active] .relationship-hit-rail,\r
    svg[data-route-picking] .relationship-hit-rail,\r
    svg[data-route-active] .relationship-hit-rail,\r
    svg[data-lens-active] .relationship-hit-rail,\r
    svg[data-chapter-preview] .relationship-hit-rail { pointer-events: none; }\r
    html[data-embed="true"] .relationship-hit-overlay { display: none; }\r
    @media (hover: none), (pointer: coarse) {\r
      .relationship-hit-rail { stroke-width: 24; }\r
    }\r
\r
    /* Relationship Preview is temporary exploration state layered on top of\r
       neighborhood focus. It changes emphasis only; exported geometry and the\r
       relationship's original solid/dashed visual language stay untouched. */\r
    svg[data-relationship-preview-active] [data-focus-match] { opacity: 0.18; }\r
    svg[data-relationship-preview-active] [data-relationship-preview],\r
    svg[data-relationship-preview-active] [data-relationship-preview-node] { opacity: 1; }\r
    svg[data-relationship-preview-active] [data-relationship-preview] {\r
      filter: drop-shadow(0 0 5px var(--arrow-emphasis));\r
    }\r
    svg[data-relationship-preview-active] [data-relationship-preview] path,\r
    svg[data-relationship-preview-active] path[data-relationship-preview],\r
    svg[data-relationship-preview-active] [data-relationship-preview] line,\r
    svg[data-relationship-preview-active] line[data-relationship-preview],\r
    svg[data-relationship-preview-active] [data-relationship-preview] polyline,\r
    svg[data-relationship-preview-active] polyline[data-relationship-preview] {\r
      stroke-width: 2.75;\r
    }\r
    svg[data-relationship-preview-active] [data-relationship-preview-source] {\r
      filter: drop-shadow(0 0 7px var(--frontend-stroke));\r
    }\r
    svg[data-relationship-preview-active] [data-relationship-preview-target] {\r
      filter: drop-shadow(0 0 7px var(--database-stroke));\r
    }\r
    .relationship-pulse-overlay { pointer-events: none; }\r
    .relationship-flow-pulse {\r
      fill: none;\r
      stroke: var(--arrow-emphasis);\r
      stroke-width: 3.35;\r
      stroke-linecap: round;\r
      stroke-dasharray: 0.085 0.915;\r
      stroke-dashoffset: 0;\r
      vector-effect: non-scaling-stroke;\r
      opacity: 0;\r
      filter: drop-shadow(0 0 4px var(--arrow-emphasis));\r
      animation: archify-relationship-pulse 1.2s linear 1 both;\r
    }\r
    svg[data-preset="signal-flow"] .relationship-flow-pulse {\r
      stroke: var(--frontend-stroke);\r
      stroke-width: 3.85;\r
      filter: drop-shadow(0 0 7px var(--frontend-stroke));\r
    }\r
    svg[data-preset="blueprint"] .relationship-flow-pulse {\r
      stroke-width: 2.5;\r
      stroke-linecap: square;\r
      filter: none;\r
    }\r
    svg[data-preset="editorial"] .relationship-flow-pulse {\r
      stroke: var(--arrow-emphasis);\r
      stroke-width: 2.75;\r
      filter: none;\r
    }\r
    .semantic-flow-token {\r
      color: var(--frontend-stroke);\r
      opacity: 0;\r
      pointer-events: none;\r
    }\r
    .relationship-flow-token {\r
      animation: archify-relationship-token-life 1.2s linear 1 both;\r
    }\r
    .story-flow-token {\r
      animation: archify-relationship-token-life 0.78s linear 1 both;\r
    }\r
    .semantic-flow-token-halo {\r
      fill: var(--mask);\r
      stroke: currentColor;\r
      stroke-width: 1.1;\r
      vector-effect: non-scaling-stroke;\r
      opacity: 0.96;\r
    }\r
    .relationship-flow-token-shape {\r
      fill: var(--mask);\r
      stroke: currentColor;\r
      stroke-width: 1.35;\r
      stroke-linecap: round;\r
      stroke-linejoin: round;\r
      vector-effect: non-scaling-stroke;\r
    }\r
    .relationship-flow-token-ink {\r
      fill: none;\r
      stroke: currentColor;\r
      stroke-width: 1.05;\r
      stroke-linecap: round;\r
      vector-effect: non-scaling-stroke;\r
    }\r
    .relationship-flow-token-dot { fill: currentColor; stroke: none; }\r
    .semantic-flow-token[data-token-kind="data"] { color: var(--database-stroke); }\r
    .semantic-flow-token[data-token-kind="event"] { color: var(--messagebus-stroke); }\r
    .semantic-flow-token[data-token-kind="security"] { color: var(--security-stroke); }\r
    .semantic-flow-token[data-token-kind="state"] { color: var(--cloud-stroke); }\r
    svg[data-preset="signal-flow"] .semantic-flow-token {\r
      filter: drop-shadow(0 0 5px currentColor);\r
    }\r
    svg[data-preset="blueprint"] .semantic-flow-token { filter: none; }\r
    svg[data-preset="editorial"] .semantic-flow-token { filter: none; }\r
    html[data-embed="true"] .relationship-pulse-overlay { display: none; }\r
\r
    /* Intent Trace is a temporary, pre-click exploration layer. Related\r
       topology stays readable while a short viewer-only signal runs over\r
       cloned edge geometry; the authored edge remains untouched underneath. */\r
    svg[data-intent-trace-active] [data-node-id],\r
    svg[data-intent-trace-active] [data-edge-from] { opacity: 0.2; }\r
    svg[data-intent-trace-active] [data-intent-trace-match] { opacity: 1; }\r
    svg[data-intent-trace-active] [data-intent-trace-selected] {\r
      filter: drop-shadow(0 0 10px var(--frontend-stroke));\r
    }\r
    .intent-trace-overlay { pointer-events: none; }\r
    .intent-trace-flow {\r
      fill: none;\r
      stroke-width: 3.1;\r
      stroke-linecap: round;\r
      stroke-dasharray: 0.1 0.9;\r
      stroke-dashoffset: 0;\r
      vector-effect: non-scaling-stroke;\r
      opacity: 0.94;\r
      animation: archify-intent-trace-flow 1.15s linear 1 both;\r
    }\r
    /* Direction names describe each edge relative to the focused node only.\r
       The cloned geometry already runs from the authored source to target, so\r
       incoming and outgoing signals must share the same playback direction. */\r
    .intent-trace-flow[data-direction="out"] {\r
      stroke: var(--frontend-stroke);\r
      filter: drop-shadow(0 0 4px var(--frontend-stroke));\r
    }\r
    .intent-trace-flow[data-direction="in"] {\r
      stroke: var(--database-stroke);\r
      filter: drop-shadow(0 0 4px var(--database-stroke));\r
      animation-direction: normal;\r
    }\r
    .intent-trace-flow[data-direction="loop"] {\r
      stroke: var(--security-stroke);\r
      filter: drop-shadow(0 0 4px var(--security-stroke));\r
    }\r
    svg[data-preset="blueprint"] [data-intent-trace-selected],\r
    svg[data-preset="blueprint"] .intent-trace-flow {\r
      filter: none;\r
      stroke-linecap: square;\r
    }\r
    svg[data-preset="editorial"] [data-intent-trace-selected],\r
    svg[data-preset="editorial"] .intent-trace-flow { filter: none; }\r
    .intent-trace-status {\r
      position: absolute;\r
      width: 1px;\r
      height: 1px;\r
      padding: 0;\r
      margin: -1px;\r
      overflow: hidden;\r
      clip: rect(0, 0, 0, 0);\r
      clip-path: inset(50%);\r
      white-space: nowrap;\r
      border: 0;\r
    }\r
\r
    /* Route Probe separates a durable two-point query from selection and\r
       one-hop hover. Only the chosen shortest directed path stays prominent;\r
       the traveling signal is cloned viewer geometry and never authored SVG. */\r
    svg[data-route-picking="target"] [data-node-id] { opacity: 0.24; }\r
    svg[data-route-picking="target"] [data-route-candidate],\r
    svg[data-route-picking="target"] [data-route-start] { opacity: 1; }\r
    svg[data-route-picking] [data-node-id] { cursor: crosshair; }\r
    svg[data-route-picking] [data-route-start] {\r
      filter: drop-shadow(0 0 10px var(--frontend-stroke));\r
    }\r
    svg[data-route-active] [data-node-id],\r
    svg[data-route-active] [data-edge-from] { opacity: 0.11; }\r
    svg[data-route-active] [data-route-match] { opacity: 1; }\r
    svg[data-route-active] [data-route-start] {\r
      filter: drop-shadow(0 0 11px var(--frontend-stroke));\r
    }\r
    svg[data-route-active] [data-route-end] {\r
      filter: drop-shadow(0 0 11px var(--security-stroke));\r
    }\r
    svg[data-route-active] [data-route-step]:not([data-route-start]):not([data-route-end]) {\r
      filter: drop-shadow(0 0 7px var(--backend-stroke));\r
    }\r
    svg[data-route-journey] [data-route-match][data-route-journey-state="past"] { opacity: 0.62; }\r
    svg[data-route-journey] [data-route-match][data-route-journey-state="future"] { opacity: 0.34; }\r
    svg[data-route-journey] [data-route-match][data-route-journey-state="current"] { opacity: 1; }\r
    svg[data-route-journey] [data-node-id][data-route-journey-current] {\r
      filter: drop-shadow(0 0 10px var(--backend-stroke));\r
    }\r
    svg[data-route-journey] [data-edge-from][data-route-journey-current] {\r
      opacity: 1;\r
      filter: drop-shadow(0 0 6px var(--backend-stroke));\r
    }\r
    .route-probe-overlay { pointer-events: none; }\r
    .route-journey-overlay { pointer-events: none; }\r
    .route-probe-flow {\r
      fill: none;\r
      stroke: var(--backend-stroke);\r
      stroke-width: 3.25;\r
      stroke-linecap: round;\r
      stroke-dasharray: 0.085 0.915;\r
      stroke-dashoffset: 0;\r
      vector-effect: non-scaling-stroke;\r
      opacity: 0.96;\r
      filter: drop-shadow(0 0 5px var(--backend-stroke));\r
      animation: archify-route-probe-flow 1.1s cubic-bezier(0.22, 1, 0.36, 1) 1 both;\r
      animation-delay: calc(var(--route-step, 0) * 0.16s);\r
    }\r
    .route-journey-flow {\r
      fill: none;\r
      stroke: var(--backend-stroke);\r
      stroke-width: 3.5;\r
      stroke-linecap: round;\r
      stroke-dasharray: 0.1 0.9;\r
      stroke-dashoffset: 0;\r
      vector-effect: non-scaling-stroke;\r
      opacity: 0;\r
      filter: drop-shadow(0 0 6px var(--backend-stroke));\r
      animation: archify-route-journey-flow 780ms cubic-bezier(0.22, 1, 0.36, 1) 1 both;\r
    }\r
    svg[data-preset="blueprint"] [data-route-start],\r
    svg[data-preset="blueprint"] [data-route-end],\r
    svg[data-preset="blueprint"] [data-route-step],\r
    svg[data-preset="blueprint"] .route-probe-flow {\r
      filter: none;\r
      stroke-linecap: square;\r
    }\r
    svg[data-preset="blueprint"] .route-journey-flow {\r
      filter: none;\r
      stroke-linecap: square;\r
    }\r
    svg[data-preset="editorial"] [data-route-start],\r
    svg[data-preset="editorial"] [data-route-end],\r
    svg[data-preset="editorial"] [data-route-step],\r
    svg[data-preset="editorial"] .route-probe-flow,\r
    svg[data-preset="editorial"] .route-journey-flow { filter: none; }\r
\r
    svg[data-preset="editorial"] .c-grid {\r
      stroke-dasharray: 1 4;\r
      opacity: 0.48;\r
    }\r
    svg[data-preset="editorial"] .c-region {\r
      fill: color-mix(in srgb, var(--cloud-fill) 48%, transparent);\r
      stroke-dasharray: 9 4;\r
    }\r
    svg[data-preset="editorial"] [data-node-id]:hover,\r
    svg[data-preset="editorial"] [data-node-id]:focus-visible,\r
    svg[data-preset="editorial"][data-focus-active] [data-focus-selected] {\r
      filter: drop-shadow(0 2px 2px color-mix(in srgb, var(--text) 18%, transparent));\r
    }\r
\r
    svg[data-preset="blueprint"] .c-grid {\r
      stroke-dasharray: 1 3;\r
      opacity: 0.78;\r
    }\r
    svg[data-preset="blueprint"] .c-region {\r
      fill: color-mix(in srgb, var(--cloud-fill) 58%, transparent);\r
      stroke-dasharray: 12 4 2 4;\r
    }\r
    svg[data-preset="blueprint"] .c-security-group,\r
    svg[data-preset="blueprint"] .c-lane { stroke-dasharray: 7 3; }\r
    svg[data-preset="blueprint"] [data-node-id]:hover,\r
    svg[data-preset="blueprint"] [data-node-id]:focus-visible {\r
      filter: drop-shadow(0 0 3px var(--frontend-stroke));\r
    }\r
    svg[data-preset="blueprint"][data-focus-active] [data-focus-selected] {\r
      filter: drop-shadow(0 0 3px var(--frontend-stroke));\r
    }\r
    svg[data-preset="blueprint"][data-focus-active][data-reach-active] [data-focus-selected][data-reach-origin] {\r
      filter: none;\r
    }\r
    svg[data-preset="blueprint"][data-relationship-preview-active] [data-relationship-preview],\r
    svg[data-preset="blueprint"][data-relationship-preview-active] [data-relationship-preview-source],\r
    svg[data-preset="blueprint"][data-relationship-preview-active] [data-relationship-preview-target] {\r
      filter: drop-shadow(0 0 3px var(--frontend-stroke));\r
    }\r
\r
    /* Story Trail is a viewer-only overlay derived from the ordered focus IDs\r
       of the active guided view. The authored edge stays underneath with its\r
       original color, dash pattern, marker, and geometry intact. */\r
    .story-trail-overlay { pointer-events: none; }\r
    .story-carrier-overlay { pointer-events: none; }\r
    .story-trail-flow {\r
      fill: none;\r
      stroke: var(--frontend-stroke);\r
      stroke-width: 2.8;\r
      stroke-linecap: round;\r
      vector-effect: non-scaling-stroke;\r
      opacity: 0.34;\r
      filter: drop-shadow(0 0 2px var(--frontend-stroke));\r
    }\r
    svg[data-story-beat] [data-story-step] {\r
      opacity: 0.22;\r
      filter: saturate(0.42);\r
      transition: opacity 180ms ease, filter 180ms ease;\r
    }\r
    svg[data-story-beat] [data-story-step][data-story-beat-state="past"] {\r
      opacity: 0.72;\r
      filter: saturate(0.82);\r
    }\r
    svg[data-story-beat] [data-story-step][data-story-beat-state="next"] {\r
      opacity: 0.5;\r
      filter: saturate(0.66);\r
    }\r
    svg[data-story-beat] [data-story-step][data-story-beat-state="active"] {\r
      opacity: 1;\r
      filter: drop-shadow(0 0 7px var(--frontend-stroke));\r
      animation: archify-story-beat-node 360ms cubic-bezier(0.22, 1, 0.36, 1) both;\r
    }\r
    svg[data-story-beat] [data-edge-from][data-story-beat-step] {\r
      opacity: 0.16;\r
      transition: opacity 160ms ease;\r
    }\r
    svg[data-story-beat] [data-edge-from][data-story-beat-step][data-story-beat-state="past"] { opacity: 0.58; }\r
    svg[data-story-beat] [data-edge-from][data-story-beat-step][data-story-beat-state="next"] { opacity: 0.34; }\r
    svg[data-story-beat] [data-edge-from][data-story-beat-step][data-story-beat-state="active"] { opacity: 1; }\r
    svg[data-story-beat] .story-trail-flow { opacity: 0; transition: opacity 160ms ease; }\r
    svg[data-story-beat] .story-trail-flow[data-story-beat-state="past"] { opacity: 0.34; }\r
    svg[data-story-beat] .story-trail-flow[data-story-beat-state="next"] { opacity: 0.2; }\r
    svg[data-story-beat] .story-trail-flow[data-story-beat-state="active"] { opacity: 0.92; }\r
    svg[data-story-beat] .story-trail-flow[data-story-pulse="true"] {\r
      stroke-dasharray: 2 13;\r
      stroke-dashoffset: 30;\r
      opacity: 0.92;\r
      animation: archify-story-flow 0.78s linear 1 both;\r
    }\r
    svg[data-preset="blueprint"] .story-trail-flow {\r
      stroke-linecap: square;\r
      filter: none;\r
      opacity: 0.5;\r
    }\r
    svg[data-preset="blueprint"][data-story-beat] [data-story-step][data-story-beat-state="active"] {\r
      filter: none;\r
      animation: none;\r
    }\r
    svg[data-preset="editorial"] .story-trail-flow { filter: none; }\r
    svg[data-preset="editorial"][data-story-beat] [data-story-step][data-story-beat-state="active"] {\r
      filter: drop-shadow(0 2px 2px color-mix(in srgb, var(--text) 16%, transparent));\r
    }\r
\r
    /* Chapter Delta Preview is a static, pre-commit comparison between two\r
       chapter focus sets. Symbols in the rail carry the meaning without color;\r
       these SVG rules only make exact stable-ID membership easier to scan. */\r
    svg[data-chapter-preview] [data-node-id],\r
    svg[data-chapter-preview] [data-edge-from] {\r
      opacity: 0.1 !important;\r
      filter: none !important;\r
      transition: none !important;\r
    }\r
    svg[data-chapter-preview] .story-trail-overlay { opacity: 0.08 !important; }\r
    svg[data-chapter-preview] [data-node-id][data-chapter-preview-role="stay"] {\r
      opacity: 0.76 !important;\r
      filter: saturate(0.7) !important;\r
    }\r
    svg[data-chapter-preview] [data-node-id][data-chapter-preview-role="enter"] {\r
      opacity: 1 !important;\r
      filter: saturate(1.2) !important;\r
    }\r
    svg[data-chapter-preview] [data-node-id][data-chapter-preview-role="leave"] {\r
      opacity: 0.28 !important;\r
      filter: grayscale(0.72) !important;\r
    }\r
    svg[data-preset="blueprint"][data-chapter-preview] [data-node-id] { filter: none !important; }\r
\r
    /* Dashed boundary variants */\r
    .c-security-group { fill: transparent; stroke: var(--security-stroke); stroke-dasharray: 4,4; }\r
    .c-region         { fill: rgba(251, 191, 36, 0.05); stroke: var(--cloud-stroke); stroke-dasharray: 8,4; }\r
    .c-lane           { fill: var(--lane-fill); stroke: var(--lane-stroke); stroke-dasharray: 6,6; }\r
\r
    /* Optional trace animation, enabled only by meta.animation = "trace".\r
       The ordinary viewer performs one ambient pass and then restores the\r
       authored solid/security/async line language. WebM samples the same\r
       authored geometry into an explicit canvas timeline. */\r
    html[data-ambient-motion="running"] svg[data-animation="trace"] [data-animate="edge"] {\r
      animation: archify-edge-flow 2.4s linear 1;\r
      animation-delay: calc(var(--step, 0) * 160ms);\r
    }\r
    html[data-ambient-motion="running"] svg[data-animation="trace"] [data-animate="node"] {\r
      transform-box: fill-box;\r
      transform-origin: center;\r
      animation: archify-node-pulse 3.6s ease-in-out 1;\r
      animation-delay: calc(var(--step, 0) * 160ms);\r
    }\r
    svg[data-preset="signal-flow"][data-animation="trace"] [data-animate="edge"] {\r
      stroke-linecap: round;\r
      filter: drop-shadow(0 0 3px var(--arrow-emphasis));\r
      animation-duration: 1.75s;\r
    }\r
    svg[data-preset="signal-flow"][data-animation="trace"] [data-animate="node"] {\r
      animation-duration: 3.1s;\r
    }\r
    svg[data-preset="blueprint"][data-animation="trace"] [data-animate="edge"] {\r
      stroke-linecap: square;\r
      filter: none;\r
      animation-duration: 2.15s;\r
    }\r
    svg[data-preset="blueprint"][data-animation="trace"] [data-animate="node"] {\r
      animation-name: archify-blueprint-node-pulse;\r
      animation-duration: 3.8s;\r
    }\r
    svg[data-preset="editorial"][data-animation="trace"] [data-animate="edge"] {\r
      filter: none;\r
      animation-duration: 2.2s;\r
    }\r
    svg[data-preset="editorial"][data-animation="trace"] [data-animate="node"] {\r
      animation-name: archify-editorial-node-pulse;\r
      animation-duration: 3.5s;\r
    }\r
    /* Embedded proofs are static until a named Story Trail chapter is played.\r
       This keeps proof grids calm and ensures ?play=1 stops all viewer motion\r
       after one 3.2 second chapter instead of leaving ambient trace loops on. */\r
    html[data-embed="true"] svg[data-animation="trace"] [data-animate],\r
    html[data-share-playback="true"] svg[data-animation="trace"] [data-animate] {\r
      animation: none !important;\r
      stroke-dashoffset: 0;\r
    }\r
    @keyframes archify-edge-flow {\r
      0% { stroke-dasharray: 10 8; stroke-dashoffset: 54; opacity: 0.42; }\r
      88% { stroke-dasharray: 10 8; stroke-dashoffset: 0; opacity: 1; }\r
      99.9% { stroke-dasharray: 10 8; stroke-dashoffset: 0; opacity: 1; }\r
      100% { stroke-dashoffset: 0; opacity: 1; }\r
    }\r
    @keyframes archify-node-pulse {\r
      0%, 72%, 100% { filter: none; stroke-width: 1.5; }\r
      18%, 36% {\r
        filter: drop-shadow(0 0 8px var(--arrow-emphasis));\r
        stroke-width: 2.4;\r
      }\r
    }\r
    @keyframes archify-blueprint-node-pulse {\r
      0%, 72%, 100% { opacity: 1; filter: none; }\r
      18%, 36% { opacity: 0.72; filter: drop-shadow(0 0 2px var(--frontend-stroke)); }\r
    }\r
    @keyframes archify-editorial-node-pulse {\r
      0%, 72%, 100% { opacity: 1; filter: none; }\r
      18%, 36% { opacity: 0.78; filter: drop-shadow(0 2px 2px color-mix(in srgb, var(--text) 18%, transparent)); }\r
    }\r
    @keyframes archify-signal-scan {\r
      0%, 18% { opacity: 1; transform: translateX(-70%); }\r
      70% { opacity: 1; transform: translateX(70%); }\r
      100% { opacity: 0; transform: translateX(70%); }\r
    }\r
    @keyframes archify-radar-live {\r
      0% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--backend-stroke) 52%, transparent); }\r
      55%, 100% { box-shadow: 0 0 0 0.32rem transparent; }\r
    }\r
    @keyframes archify-guided-progress {\r
      from { transform: scaleX(var(--guided-progress-start, 0)); }\r
      to { transform: scaleX(1); }\r
    }\r
    @keyframes archify-story-flow {\r
      to { stroke-dashoffset: 0; }\r
    }\r
    @keyframes archify-intent-trace-flow {\r
      0% { opacity: 0.28; stroke-dashoffset: 0; }\r
      12%, 78% { opacity: 0.94; }\r
      100% { opacity: 0; stroke-dashoffset: -1; }\r
    }\r
    @keyframes archify-route-probe-flow {\r
      0% { stroke-dashoffset: 0; opacity: 0.96; }\r
      78% { stroke-dashoffset: -1; opacity: 0.96; }\r
      100% { stroke-dasharray: none; stroke-dashoffset: 0; opacity: 0.58; }\r
    }\r
    @keyframes archify-route-journey-flow {\r
      0% { opacity: 0.16; stroke-dashoffset: 0; }\r
      14%, 76% { opacity: 1; }\r
      100% { opacity: 0; stroke-dashoffset: -1; }\r
    }\r
    @keyframes archify-semantic-lens-flow {\r
      0% { opacity: 0.2; stroke-dashoffset: 0; }\r
      12%, 78% { opacity: 0.9; }\r
      100% { opacity: 0; stroke-dashoffset: -1; }\r
    }\r
    @keyframes archify-relationship-pulse {\r
      0% { opacity: 0.18; stroke-dashoffset: 0; }\r
      10%, 76% { opacity: 0.98; }\r
      100% { opacity: 0; stroke-dashoffset: -1; }\r
    }\r
    @keyframes archify-relationship-token-life {\r
      0%, 7% { opacity: 0; }\r
      13%, 82% { opacity: 1; }\r
      100% { opacity: 0; }\r
    }\r
    @keyframes archify-story-beat-node {\r
      from { opacity: 0.48; filter: saturate(0.6); }\r
      58% { opacity: 1; filter: drop-shadow(0 0 10px var(--frontend-stroke)); }\r
      to { opacity: 1; filter: drop-shadow(0 0 7px var(--frontend-stroke)); }\r
    }\r
    @keyframes archify-share-cue-enter {\r
      from { opacity: 0; transform: translate(-50%, -0.45rem); }\r
      to { opacity: 1; transform: translate(-50%, 0); }\r
    }\r
    @keyframes archify-share-cue-pulse {\r
      0%, 100% { opacity: 1; transform: scale(1); }\r
      50% { opacity: 0.48; transform: scale(0.78); }\r
    }\r
    @media (prefers-reduced-motion: reduce) {\r
      html[data-preset="signal-flow"] .diagram-container::before {\r
        animation: none !important;\r
      }\r
      .pulse-dot { animation: none !important; }\r
      svg[data-animation="trace"] [data-animate] {\r
        animation: none !important;\r
        stroke-dashoffset: 0;\r
      }\r
      .guided-view-progress span {\r
        animation: none !important;\r
        transform: scaleX(1) !important;\r
      }\r
      .story-trail-flow,\r
      .intent-trace-flow,\r
      .route-probe-flow,\r
      .semantic-lens,\r
      .diagram-guide,\r
      [data-story-step],\r
      .overview-map-live,\r
      .guided-view-stop,\r
      .share-chapter-cue,\r
      .chapter-handoff-anchor,\r
      .share-chapter-state::before,\r
      .share-chapter-progress span { animation: none !important; }\r
      .guided-view-chapter,\r
      svg[data-chapter-preview] [data-node-id],\r
      svg[data-chapter-preview] [data-edge-from] { transition: none !important; }\r
      svg[data-story-playing="true"] .story-trail-flow {\r
        stroke-dasharray: none;\r
        stroke-dashoffset: 0;\r
        opacity: 0.55;\r
      }\r
      .intent-trace-flow {\r
        animation: none !important;\r
        stroke-dasharray: none;\r
        stroke-dashoffset: 0;\r
        opacity: 0.72;\r
      }\r
      .route-probe-flow {\r
        animation: none !important;\r
        stroke-dasharray: none;\r
        stroke-dashoffset: 0;\r
        opacity: 0.78;\r
      }\r
      .route-journey-overlay,\r
      .story-carrier-overlay { display: none !important; }\r
      .semantic-lens-flow {\r
        animation: none !important;\r
        stroke-dasharray: none;\r
        stroke-width: 2.2;\r
        opacity: 0.34;\r
        filter: none;\r
      }\r
      .relationship-pulse-overlay { display: none !important; }\r
      .guided-view-chapter { transition: none !important; }\r
      .source-evidence-beacon,\r
      svg [data-node-id], svg [data-edge-from], svg [data-detail], svg [data-detail-anchor], svg [data-legend-hit], svg { transition: none !important; }\r
    }\r
  </style>\r
<style>__FLOWBD_CSS__</style></head>\r
<body>\r
  <!-- Toolbar: theme, live visual style, trace motion, presentation stage, and export.\r
       Motion appears only for trace-enabled artifacts and has no shortcut;\r
       Keyboard: T toggles theme, S cycles style, F toggles the stage, E opens export. -->\r
  <div class="toolbar" role="toolbar" aria-label="图表操作">\r
    <button id="btn-theme" type="button"\r
            title="切换主题（T）"\r
            aria-label="切换颜色主题"\r
            aria-pressed="false">\r
      <span id="theme-icon" class="toolbar-icon" aria-hidden="true"></span>\r
      <span id="theme-label">深色</span>\r
    </button>\r
    <div class="preset-wrap">\r
      <button id="btn-preset" type="button"\r
              title="选择视觉风格（S 循环切换）"\r
              aria-label="选择视觉风格"\r
              aria-haspopup="menu"\r
              aria-expanded="false"\r
              aria-controls="preset-menu"\r
              aria-keyshortcuts="S">\r
        <span class="preset-control-mark" aria-hidden="true"></span>\r
        <span id="preset-label">风格</span>\r
        <span class="toolbar-icon toolbar-chevron" aria-hidden="true"></span>\r
      </button>\r
      <div class="preset-menu" id="preset-menu" role="menu" aria-label="视觉风格">\r
        <div class="preset-menu-heading" role="presentation"><span>视觉表达</span><span>S 循环切换</span></div>\r
        <button class="preset-option" data-preset-value="classic" type="button" role="menuitemradio" aria-checked="false" tabindex="-1">\r
          <span class="preset-option-swatch classic" aria-hidden="true"></span>\r
          <span class="preset-option-copy"><strong>经典</strong><small>稳定的技术默认风格</small></span>\r
          <span class="preset-option-check" aria-hidden="true"></span>\r
        </button>\r
        <button class="preset-option" data-preset-value="signal-flow" type="button" role="menuitemradio" aria-checked="false" tabindex="-1">\r
          <span class="preset-option-swatch signal-flow" aria-hidden="true"></span>\r
          <span class="preset-option-copy"><strong>信号流</strong><small>突出动态流向</small></span>\r
          <span class="preset-option-check" aria-hidden="true"></span>\r
        </button>\r
        <button class="preset-option" data-preset-value="blueprint" type="button" role="menuitemradio" aria-checked="false" tabindex="-1">\r
          <span class="preset-option-swatch blueprint" aria-hidden="true"></span>\r
          <span class="preset-option-copy"><strong>蓝图</strong><small>工程评审</small></span>\r
          <span class="preset-option-check" aria-hidden="true"></span>\r
        </button>\r
        <button class="preset-option" data-preset-value="editorial" type="button" role="menuitemradio" aria-checked="false" tabindex="-1">\r
          <span class="preset-option-swatch editorial" aria-hidden="true"></span>\r
          <span class="preset-option-copy"><strong>编辑风格</strong><small>适合发布与上线说明</small></span>\r
          <span class="preset-option-check" aria-hidden="true"></span>\r
        </button>\r
      </div>\r
    </div>\r
    <button id="btn-motion" type="button" hidden\r
            title="暂停动效"\r
            aria-label="暂停动效"\r
            aria-pressed="true">\r
      <span class="motion-control-dot" aria-hidden="true"></span>\r
      <span id="motion-label">动态</span>\r
    </button>\r
    <button id="btn-present" type="button"\r
            title="演示模式（F）"\r
            aria-label="进入演示模式"\r
            aria-pressed="false">\r
      <span id="present-icon" class="toolbar-icon" aria-hidden="true"></span>\r
      <span id="present-label">演示</span>\r
    </button>\r
    <div class="export-wrap">\r
      <button id="btn-export" type="button"\r
              title="导出图表（E）"\r
              aria-label="导出图表"\r
              aria-haspopup="menu"\r
              aria-expanded="false"\r
              aria-controls="export-menu">\r
        导出 <span class="toolbar-icon toolbar-chevron" aria-hidden="true"></span>\r
      </button>\r
      <div class="export-menu" id="export-menu" role="menu" aria-label="导出">\r
        <div class="export-menu-header" role="presentation">\r
          <div><strong>导出图表</strong><span>便携、整洁的输出</span></div>\r
          <kbd>E</kbd>\r
        </div>\r
        <div class="export-menu-section" role="group" aria-label="分享">\r
          <span class="export-menu-heading" aria-hidden="true">分享</span>\r
          <button data-format="share-card" type="button" role="menuitem" tabindex="-1"><span class="export-item-copy"><strong>分享卡片</strong><small class="hint">1200&times;630 PNG</small></span></button>\r
          <button data-action="route-share-card" type="button" role="menuitem" tabindex="-1" hidden disabled><span class="export-item-copy"><strong>路径分享卡片</strong><small class="hint">1200&times;630 PNG</small></span></button>\r
          <button data-action="reach-share-card" type="button" role="menuitem" tabindex="-1" hidden disabled><span class="export-item-copy"><strong>可达范围分享卡片</strong><small class="hint">1200&times;630 PNG</small></span></button>\r
          <button data-action="copy-share-card" type="button" role="menuitem" tabindex="-1"><span class="export-item-copy"><strong>复制分享卡片</strong><small class="hint">复制 PNG 到剪贴板</small></span></button>\r
          <button data-action="copy" type="button" role="menuitem" tabindex="-1"><span class="export-item-copy"><strong>复制图表</strong><small class="hint">复制 PNG 到剪贴板</small></span></button>\r
        </div>\r
        <div class="export-menu-section" role="group" aria-label="位图">\r
          <span class="export-menu-heading" aria-hidden="true">图像</span>\r
          <button data-format="png" type="button" role="menuitem" tabindex="-1"><span class="export-item-copy"><strong>PNG</strong><small class="hint">无损图像</small></span></button>\r
          <button data-format="jpeg" type="button" role="menuitem" tabindex="-1"><span class="export-item-copy"><strong>JPEG</strong><small class="hint">紧凑图像</small></span></button>\r
          <button data-format="webp" type="button" role="menuitem" tabindex="-1"><span class="export-item-copy"><strong>WebP</strong><small class="hint">现代图像格式</small></span></button>\r
        </div>\r
        <div class="export-menu-section" role="group" aria-label="矢量与动效">\r
          <span class="export-menu-heading" aria-hidden="true">矢量与动效</span>\r
          <button data-format="svg" type="button" role="menuitem" tabindex="-1"><span class="export-item-copy"><strong>SVG</strong><small class="hint">可编辑矢量图</small></span></button>\r
          <button data-format="webm" type="button" role="menuitem" tabindex="-1"><span class="export-item-copy"><strong>WebM</strong><small class="hint">6 秒动效</small></span></button>\r
        </div>\r
      </div>\r
    </div>\r
  </div>\r
\r
  <div class="container">\r
    <!-- Header -->\r
    <div class="header">\r
      <div class="header-row"\r
           data-preset-badge-signal-flow="信号流"\r
           data-preset-badge-blueprint="蓝图 / 修订 01"\r
           data-preset-badge-editorial="编辑风格 / 现场笔记">\r
        <div class="pulse-dot"></div>\r
        <h1>__FLOWBD_TITLE__</h1>\r
      </div>\r
    </div>\r
\r
    <script id="archify-guided-views-data" type="application/json">__FLOWBD_GUIDES__<\/script>\r
\r
    <script id="archify-i18n-data" type="application/json">{"locale":"zh-CN","messages":{"viewer.kind.frontend":"前端","viewer.kind.backend":"后端","viewer.kind.database":"数据库","viewer.kind.cloud":"云服务","viewer.kind.security":"安全","viewer.kind.messagebus":"消息总线","viewer.kind.external":"外部系统","viewer.kind.neutral":"中性","viewer.kind.node":"节点","viewer.kind.start":"开始","viewer.kind.active":"活动","viewer.kind.waiting":"等待","viewer.kind.decision":"决策","viewer.kind.success":"成功","viewer.kind.failure":"失败","viewer.toolbar.actions":"图表操作","viewer.theme.toggle.title":"切换主题（T）","viewer.theme.toggle":"切换颜色主题","viewer.theme.dark":"深色","viewer.theme.light":"浅色","viewer.preset.choose.title":"选择视觉风格（S 循环切换）","viewer.preset.choose":"选择视觉风格","viewer.preset.style":"风格","viewer.preset.menu":"视觉风格","viewer.preset.identity":"视觉表达","viewer.preset.cycles":"S 循环切换","viewer.preset.classic":"经典","viewer.preset.classic.short":"经典","viewer.preset.classic.hint":"稳定的技术默认风格","viewer.preset.flow":"信号流","viewer.preset.flow.short":"流动","viewer.preset.flow.hint":"突出动态流向","viewer.preset.blueprint":"蓝图","viewer.preset.blueprint.hint":"工程评审","viewer.preset.editorial":"编辑风格","viewer.preset.editorial.hint":"适合发布与上线说明","viewer.preset.badge.signalFlow":"信号流","viewer.preset.badge.blueprint":"蓝图 / 修订 01","viewer.preset.badge.editorial":"编辑风格 / 现场笔记","viewer.preset.badge.editorialPlate":"FlowBD / 技术谱系","viewer.preset.current":"当前视觉风格：{style}。选择视觉风格","viewer.motion.live":"动态","viewer.motion.still":"静态","viewer.motion.pause":"暂停动效","viewer.motion.resume":"恢复动效","viewer.motion.reduced":"已根据减少动态效果偏好暂停动效","viewer.motion.hidden":"页面不可见时已暂停动效","viewer.motion.yielding":"暂停动效；当前让位于{owner}","viewer.motion.yielding.title":"动态预览已启用 · 正在让位于{owner}","viewer.owner.story":"引导故事","viewer.owner.chapter":"当前章节","viewer.owner.chapterPreview":"章节差异预览","viewer.owner.handoff":"章节交接","viewer.owner.route":"路径探测","viewer.owner.lens":"语义透镜","viewer.owner.relationship":"关系预览","viewer.owner.intent":"意图追踪","viewer.owner.focus":"语义聚焦","viewer.owner.legend":"图例预览","viewer.owner.reader":"读者交互","viewer.present.enter":"进入演示模式","viewer.present.enter.title":"演示模式（F）","viewer.present.exit":"退出演示模式","viewer.present.exit.title":"退出演示模式（F 或 Escape）","viewer.present.present":"演示","viewer.present.exit.label":"退出","viewer.export.button":"导出","viewer.export.button.title":"导出图表（E）","viewer.export.diagram":"导出图表","viewer.export.menu":"导出","viewer.export.subtitle":"便携、整洁的输出","viewer.export.share":"分享","viewer.export.shareCard":"分享卡片","viewer.export.routeShareCard":"路径分享卡片","viewer.export.reachShareCard":"可达范围分享卡片","viewer.export.copyShareCard":"复制分享卡片","viewer.export.copyDiagram":"复制图表","viewer.export.clipboardPng":"复制 PNG 到剪贴板","viewer.export.raster":"位图","viewer.export.image":"图像","viewer.export.lossless":"无损图像","viewer.export.compact":"紧凑图像","viewer.export.modern":"现代图像格式","viewer.export.vectorMotion":"矢量与动效","viewer.export.vectorMotion.heading":"矢量与动效","viewer.export.editable":"可编辑矢量图","viewer.export.motion6s":"6 秒动效","viewer.export.unsupported":"当前浏览器不支持","viewer.export.clipboardUnsupported":"当前浏览器不支持写入图片剪贴板","viewer.export.clipboardUnsupported.period":"当前浏览器不支持写入图片剪贴板。","viewer.export.clipboardUnsupported.short":"此浏览器不支持写入图片剪贴板。","viewer.export.motionUnavailable":"当前浏览器无法录制动效","viewer.export.webmUnavailable":"当前浏览器不支持 WebM","viewer.export.failed":"导出失败：{message}","viewer.export.unknownVariant":"未知的分享卡片类型：{variant}","viewer.export.routeRequired":"请先追踪路径，再导出路径分享卡片","viewer.export.reachRequired":"请先追踪直接演化可达范围，再导出可达范围分享卡片","viewer.export.unknown":"未知错误","viewer.export.routeFailed":"路径分享卡片导出失败：{message}","viewer.export.reachFailed":"可达范围分享卡片导出失败：{message}","viewer.export.copyFailed":"复制失败：{message}","viewer.export.copiedPng":"已将 PNG 复制到剪贴板","viewer.export.copiedShare":"已复制分享卡片","viewer.export.downloadedShare":"已下载分享卡片","viewer.export.downloadedRoute":"已下载路径分享卡片","viewer.export.downloadedReach":"已下载可达范围分享卡片","viewer.export.downloadedWebm":"已下载 WebM","viewer.export.recording":"正在录制 6 秒动效…","viewer.export.card.routeSummary.one":"路径：{source} → {target} · {count} 个有向跳转","viewer.export.card.routeSummary.other":"路径：{source} → {target} · {count} 个有向跳转","viewer.export.card.reachSummary":"从{origin}开始的编写{direction} · {nodes} · {links} · 最深 {hops}","viewer.export.card.node.one":"{count} 个节点","viewer.export.card.node.other":"{count} 个节点","viewer.export.card.link.one":"{count} 条连接","viewer.export.card.link.other":"{count} 条连接","viewer.export.card.hop.one":"{count} 跳","viewer.export.card.hop.other":"{count} 跳","viewer.export.card.routeBadge":"ARCHIFY · 路径 · {hops}","viewer.export.card.reachBadge":"ARCHIFY · {direction}可达范围","viewer.export.card.defaultBadge":"ARCHIFY · {preset} · {theme}","viewer.export.direction.upstream":"上游","viewer.export.direction.downstream":"下游","viewer.export.error.canvasUnavailable":"无法为{label}使用画布","viewer.export.error.contextUnavailable":"无法为{label}创建二维画布上下文","viewer.export.error.toBlobUnavailable":"{label}无法使用 canvas.toBlob","viewer.export.error.toBlobNull":"{label}的 canvas.toBlob 未返回数据","viewer.export.error.variantsCombined":"无法同时组合多种分享卡片类型","viewer.export.error.viewerState":"分享卡片导出无法移除临时 Viewer 状态","viewer.export.error.routeState":"路径卡片导出无法安全保留已解析路径","viewer.export.error.reachState":"可达范围卡片导出无法安全保留编写的可达范围","viewer.export.error.webmRequirements":"WebM 动效导出需要追踪动画及浏览器 MediaRecorder 支持","viewer.export.error.mediaRecorder":"MediaRecorder 录制失败","viewer.export.error.emptyWebm":"MediaRecorder 生成了空的 WebM","viewer.export.error.webmBackground":"无法为 WebM 导出加载 SVG 背景","viewer.guided.region":"图表引导视图","viewer.guided.previous":"上一个引导视图","viewer.guided.previous.title":"上一个引导视图（[）","viewer.guided.next":"下一个引导视图","viewer.guided.next.title":"下一个引导视图（]）","viewer.guided.views":"引导视图","viewer.guided.explore":"探索此系统","viewer.guided.intro":"沿精选路径逐步查看，而不改变源图表。","viewer.guided.trail":"故事轨迹","viewer.guided.beat":"节点","viewer.guided.nextBeat":"下一步","viewer.guided.play":"播放引导故事","viewer.guided.play.title":"播放引导故事（P）","viewer.guided.pause":"暂停引导故事","viewer.guided.pause.title":"暂停引导故事（P）","viewer.guided.replay":"重播引导故事","viewer.guided.replay.title":"重播引导故事（P）","viewer.guided.playStory":"播放故事","viewer.guided.pauseStory":"暂停","viewer.guided.replayStory":"重播故事","viewer.guided.motionUnavailable":"静态模式下无法播放故事","viewer.guided.enableMotion":"切换为动态模式以播放引导故事","viewer.guided.selectBeatLink":"选择故事节点以复制其精确链接","viewer.guided.copyMoment":"复制此刻","viewer.guided.momentCopied":"已复制时刻链接","viewer.guided.momentCopyFailed":"无法复制故事时刻链接","viewer.guided.copied":"已复制","viewer.guided.copyFailed":"复制失败","viewer.guided.showAll":"显示全部","viewer.guided.showAll.aria":"显示完整图表","viewer.guided.chapters":"故事章节","viewer.guided.storyTrail":"{label}的故事轨迹：{count} 个节点","viewer.guided.chapter.open":"打开第 {index}/{total} 章：{label}，{count} 个停靠点","viewer.guided.chapter.current":"当前第 {index}/{total} 章：{label}，{count} 个停靠点","viewer.guided.chapter.selectedNodes":"已选择 {count} 个节点","viewer.guided.chapter.stops":"{count} 个停靠点","viewer.guided.chapter.stop.one":"{count} 个停靠点","viewer.guided.chapter.stop.other":"{count} 个停靠点","viewer.guided.chapter.current.title":"{label} — 当前章节，{count} 个停靠点","viewer.guided.chapter.delta.expanded":"{stay} 个保留，{enter} 个进入，{leave} 个离开","viewer.guided.chapter.delta.aria":"打开第 {index}/{total} 章：{label}。章节聚焦差异：{delta}","viewer.guided.chapter.delta.title":"{label} — 章节聚焦 {delta}","viewer.guided.handoff":"{from} → {to} · 经由{label}","viewer.guided.share.chapter":"章节 {index} / {total}","viewer.guided.share.initial":"章节 01 / 01","viewer.guided.share.default":"引导章节","viewer.guided.state.ready":"就绪","viewer.guided.state.playing":"播放中","viewer.guided.state.settled":"已完成","viewer.guided.state.paused":"已暂停","viewer.guided.state.pinned":"已固定","viewer.guided.state.still":"静态","viewer.guided.share.step":"步骤 {index} / {total} · {label}","viewer.guided.share.staticMoment":"{step} · 静态时刻","viewer.guided.share.complete":"{count} 个步骤已完成 · {note}","viewer.guided.share.settled":"路径已稳定，可供阅读。","viewer.guided.share.staticPath":"{count} 个步骤 · 静态路径","viewer.guided.share.ready":"{count} 个步骤 · 就绪","viewer.guided.share.aria":"{state}，第 {index}/{total} 章：{label}。{beat}。{route}","viewer.guided.beat.start":"节点 {index} / {total} · {label} · 起点","viewer.guided.beat.forward":"节点 {index} / {total} · {from} → {to}","viewer.guided.beat.reverse":"节点 {index} / {total} · {from} → {to} · 反向编写连接","viewer.guided.beat.multiple":"节点 {index} / {total} · {from} ⇄ {to} · {count} 条编写连接","viewer.guided.beat.group":"节点 {index} / {total} · {from} · {to} · 分组 · 无直接连接","viewer.guided.beat.aria.prefix":"故事节点 {index}/{total}：{label}。","viewer.guided.beat.aria.start":"起点。","viewer.guided.beat.aria.forward":"从{from}经一条正向编写关系到达。","viewer.guided.beat.aria.reverse":"从{from}出发；编写关系实际由{to}指向{from}。","viewer.guided.beat.aria.multiple":"从{from}经 {count} 条编写关系到达；不使用任意动效。","viewer.guided.beat.aria.group":"与{from}分组展示，没有直接编写关系。","viewer.guided.caption.start":"起点","viewer.guided.caption.grouped":"分组过渡 · 无直接编写连接","viewer.guided.caption.more":" +另外 {count} 条","viewer.guided.caption.reverse":"反向编写关系","viewer.guided.caption.relationships":"{count} 条编写关系","viewer.guided.caption.relationship":"编写关系","viewer.guided.caption.direction":"编写方向：{from} → {to}","viewer.guided.caption.starting":"编写起点","viewer.guided.beatLink":"复制当前故事时刻链接：第 {index}/{total} 个节点：{label}","viewer.guided.noStory":"此图表没有编写引导故事。","viewer.guide.eyebrow":"图表指南","viewer.guide.close":"关闭图表指南","viewer.guide.inspecting":"正在检查已编译语义","viewer.guide.actions":"图表探索操作","viewer.guide.find":"查找任意节点","viewer.guide.find.hint":"搜索标签、职责、类型和稳定 ID。","viewer.guide.route":"追踪路径","viewer.guide.route.aria":"追踪有向路径","viewer.guide.route.hint":"查看两个语义节点如何按编写方向连接。","viewer.guide.map":"查看完整系统","viewer.guide.map.hint":"打开带实时视口和稳定节点的语义雷达。","viewer.guide.lens":"比较语义类型","viewer.guide.lens.hint":"统计角色、显示流量并比较直接编写的连接。","viewer.guide.story":"播放引导故事","viewer.guide.story.hint":"浏览已编写的章节和真实关系。","viewer.guide.present":"进入演示模式","viewer.guide.present.hint":"让实时图表占满视口，同时不改变导出。","viewer.guide.shortcuts":"其他键盘快捷键","viewer.guide.shortcut.export":"导出","viewer.guide.shortcut.theme":"主题","viewer.guide.shortcut.style":"风格","viewer.guide.shortcut.reset":"重置","viewer.guide.shortcut.zoomIn":"放大","viewer.guide.shortcut.zoomOut":"缩小","viewer.guide.shortcut.close":"关闭","viewer.guide.facts":"{nodes} · {relationships} · {views}","viewer.guide.fact.node.one":"{count} 个语义节点","viewer.guide.fact.node.other":"{count} 个语义节点","viewer.guide.fact.relationship.one":"{count} 条关系","viewer.guide.fact.relationship.other":"{count} 条关系","viewer.guide.fact.view.one":"{count} 个引导视图","viewer.guide.fact.view.other":"{count} 个引导视图","viewer.guide.story.available.one":"浏览 {count} 个已编写章节及其真实关系。","viewer.guide.story.available.other":"浏览 {count} 个已编写章节及其真实关系。","viewer.guide.story.unavailable":"此图表没有编写引导故事。","viewer.guide.open":"打开图表指南","viewer.guide.noStory":"此图表没有编写引导故事。","viewer.finder.title":"查找节点","viewer.finder.close":"关闭节点查找器","viewer.finder.placeholder":"搜索标签或 ID","viewer.finder.search":"搜索图表节点","viewer.finder.results":"图表节点","viewer.finder.empty":"没有匹配的节点","viewer.finder.result.focus":"聚焦{label}","viewer.finder.result.routeStart":"选择{label}作为路径起点","viewer.finder.result.routeTarget":"选择{label}作为路径终点，{links}","viewer.finder.status.empty":"没有匹配的节点","viewer.finder.status.count.one":"{count} 个匹配节点","viewer.finder.status.count.other":"{count} 个匹配节点","viewer.finder.noun.nodes":"个节点","viewer.finder.link.one":"{count} 条连接","viewer.finder.link.other":"{count} 条连接","viewer.finder.result.focus.one":"聚焦{label}，{count} 条相关连接","viewer.finder.result.focus.other":"聚焦{label}，{count} 条相关连接","viewer.finder.status.filtered":"{visible}/{available} {noun}","viewer.finder.status.all":"{available} {noun}","viewer.passport.eyebrow":"方法 / 材料与证据","viewer.passport.metadata":"节点元数据","viewer.passport.evidence":"已验证的源代码证据","viewer.passport.verified":"已验证来源","viewer.passport.verificationScope":"已按固定修订版本验证本地 Git 证据，未检查远程访问权限。","viewer.passport.reach":"直接演化可达范围","viewer.passport.reach.trace":"仅追踪直接演化关系","viewer.passport.upstream":"上游","viewer.passport.downstream":"下游","viewer.passport.upstream.trace":"追踪上游编写可达性","viewer.passport.downstream.trace":"追踪下游编写可达性","viewer.passport.close":"关闭方法 / 材料与证据","viewer.passport.copy":"复制链接","viewer.passport.copy.focus":"复制聚焦节点的链接","viewer.passport.relations":"关系","viewer.passport.relations.show":"显示关联关系","viewer.passport.relations.hide":"隐藏关联关系","viewer.passport.relations.list":"关联关系","viewer.passport.copyRelation":"复制关系","viewer.passport.copyNode":"复制节点","viewer.passport.copyPinned":"复制固定关系的链接","viewer.passport.copySource":"复制来源节点的链接","viewer.passport.copy.focused.success":"已复制聚焦节点链接","viewer.passport.copy.pinned.success":"已复制固定关系链接","viewer.passport.copy.focused.failed":"无法复制聚焦节点链接","viewer.passport.copy.pinned.failed":"无法复制固定关系链接","viewer.passport.relationship.none":"没有关联关系","viewer.passport.relationship.count.one":"{count} 条关系","viewer.passport.relationship.count.other":"{count} 条关系","viewer.passport.relationship.show.one":"显示 {count} 条关联关系","viewer.passport.relationship.show.other":"显示 {count} 条关联关系","viewer.passport.relationship.summary":"{out} 条出向 · {in} 条入向{loops}","viewer.passport.relationship.loops":" · {count} 条自环","viewer.passport.relationship.explorer":"直接关系浏览器","viewer.passport.relationship.help":"使用方向键浏览关系。按 Enter 或空格键固定详情；按 Escape 清除。","viewer.passport.relationship.loopsBack":"回环","viewer.passport.relationship.connectsTo":"连接到","viewer.passport.relationship.connectsFrom":"连接自","viewer.passport.relationship.pinned":"已固定关系 · {from} → {to} · {label}","viewer.passport.relationship.inspect":"检查第 {index}/{total} 条关系：{from} 到 {to}，{label}。按 Enter 查看详情。","viewer.passport.relationship.group.out":"出向","viewer.passport.relationship.group.in":"入向","viewer.passport.relationship.group.loop":"自环","viewer.passport.relationship.row":"{group}：{relationship}，{neighbor}","viewer.passport.relationship.direction.out":"出 →","viewer.passport.relationship.direction.in":"← 入","viewer.passport.relationship.direction.loop":"自环","viewer.passport.sourceCount.one":"{count} 个已验证来源引用","viewer.passport.sourceCount.other":"{count} 个已验证来源引用","viewer.passport.sourceMarker":"来源","viewer.passport.beacon.one":"{count} 个已验证来源；聚焦此节点以检查","viewer.passport.beacon.other":"{count} 个已验证来源；聚焦此节点以检查","viewer.passport.repository.open":"打开已验证的仓库修订版本 {revision}","viewer.passport.source.open":"打开修订版本 {revision} 中已验证的来源 {path}","viewer.passport.source.openLink":"打开 ↗","viewer.passport.reach.upstream.one":"追踪 {count} 个上游演化节点","viewer.passport.reach.upstream.other":"追踪 {count} 个上游演化节点","viewer.passport.reach.downstream.one":"追踪 {count} 个下游演化节点","viewer.passport.reach.downstream.other":"追踪 {count} 个下游演化节点","viewer.passport.reach.noUpstream":"没有上游演化节点","viewer.passport.reach.noDownstream":"没有下游演化节点","viewer.passport.reach.status":"{direction} · {nodes} 个节点 · {links} 条连接 · 最深 {hops} 跳","viewer.route.eyebrow":"路径探测","viewer.route.start":"选择起点节点","viewer.route.start.find":"查找起点","viewer.route.start.find.aria":"查找路径起点","viewer.route.copy":"复制链接","viewer.route.copy.aria":"复制已追踪路径的链接","viewer.route.clear":"清除","viewer.route.clear.aria":"清除路径探测","viewer.route.traced":"已追踪路径","viewer.route.pickTwo":"在图表中选择两个语义节点","viewer.route.pickOne":"在图表中选择一个语义节点","viewer.route.controls":"路径旅程控制","viewer.route.previous":"上一个路径位置","viewer.route.play":"播放路径旅程","viewer.route.pause":"暂停路径旅程","viewer.route.replay":"重播路径旅程","viewer.route.next":"下一个路径位置","viewer.route.journey":"旅程","viewer.route.pause.label":"暂停","viewer.route.replay.label":"重播","viewer.route.overview":"总览","viewer.route.overview.aria":"显示完整路径总览","viewer.route.instructions":"先选择来源，再选择目标；方向很重要。","viewer.route.destination":"选择从{label}出发的目标","viewer.route.destination.find":"查找目标","viewer.route.destination.find.aria":"查找可达的路径目标","viewer.route.differentDestination":"选择其他目标","viewer.route.distinct":"一条路径需要两个不同的语义节点。","viewer.route.unreachable":"没有通往{label}的有向路径","viewer.route.unreachable.detail":"从{source}无法到达{target}。请选择高亮的目标。","viewer.route.start.instructions":"选择来源。下一步只会显示有向可达的目标。","viewer.route.copy.success":"已复制路径链接","viewer.route.copy.failed":"无法复制路径链接","viewer.route.position":"路径位置 {index}/{total}：{label}","viewer.route.step":"第 {index}/{total} 步 · {phase} · {label}","viewer.route.motionRequired":"自动旅程需要动态模式","viewer.route.trigger.clear":"清除已追踪路径","viewer.route.overview.status":"{nodes} · {hops} · 最短编写路径","viewer.route.overview.node.one":"{count} 个节点","viewer.route.overview.node.other":"{count} 个节点","viewer.route.overview.hop.one":"{count} 个有向跳转","viewer.route.overview.hop.other":"{count} 个有向跳转","viewer.route.phase.playing":"播放中","viewer.route.phase.complete":"已完成","viewer.route.phase.inspecting":"检查中","viewer.route.destination.count.one":"有 {count} 个有向目标可用。请选择高亮节点。","viewer.route.destination.count.other":"有 {count} 个有向目标可用。请选择高亮节点。","viewer.route.noOutgoing":"此处没有可用的出向路径。请清除后选择其他来源。","viewer.route.result.title":"{source} 到 {target}","viewer.route.finder.source.title":"选择路径起点","viewer.route.finder.source.placeholder":"搜索路径来源","viewer.route.finder.source.empty":"没有匹配的路径来源","viewer.route.finder.source.results":"可作为路径起点的节点","viewer.route.finder.source.noun":"个路径来源","viewer.route.finder.source.badge":"起点","viewer.route.finder.target.title":"从{label}出发的目标","viewer.route.finder.target.placeholder":"搜索可达目标","viewer.route.finder.target.empty":"没有匹配的可达目标","viewer.route.finder.target.results":"可达路径目标","viewer.route.finder.target.noun":"个可达目标","viewer.route.hop.one":"{count} 跳","viewer.route.hop.other":"{count} 跳","viewer.lens.eyebrow":"语义透镜","viewer.lens.title":"比较系统角色","viewer.lens.close":"关闭语义透镜","viewer.lens.instruction":"最多选择两种语义类型。选择一种可显示其真实流量；选择两种只比较直接编写的关系。","viewer.lens.kinds":"语义类型","viewer.lens.choose":"选择一种类型以检查其节点和相连关系。","viewer.lens.copy":"复制语义透镜链接","viewer.lens.clear":"清除语义透镜","viewer.lens.open":"打开语义透镜","viewer.lens.openActive":"打开当前语义透镜","viewer.lens.legend":"语义图例","viewer.lens.legend.inspect.one":"检查{label}，{count} 个节点","viewer.lens.legend.inspect.other":"检查{label}，{count} 个节点","viewer.lens.kind.count.one":"{label}，{count} 个节点","viewer.lens.kind.count.other":"{label}，{count} 个节点","viewer.lens.compare.one":"{first} → {second}：{forward} · {second} → {first}：{reverse} · 共 {count} 条直接关系","viewer.lens.compare.other":"{first} → {second}：{forward} · {second} → {first}：{reverse} · 共 {count} 条直接关系","viewer.lens.single":"{nodes} · {relationships} · 已连接节点保持可见","viewer.lens.node.one":"{count} 个{label}节点","viewer.lens.node.other":"{count} 个{label}节点","viewer.lens.relationship.one":"{count} 条相连关系","viewer.lens.relationship.other":"{count} 条相连关系","viewer.radar.title":"语义雷达","viewer.radar.building":"正在构建总览","viewer.radar.openFull":"打开完整语义雷达","viewer.radar.open":"打开雷达","viewer.radar.close":"关闭语义雷达","viewer.radar.surface":"图表总览。点击节点进行聚焦，或使用方向键平移。","viewer.radar.click":"点击节点","viewer.radar.drag":"拖动平移","viewer.radar.space":"语义雷达需要更多地图可见空间。","viewer.radar.nodes":"语义图表雷达节点","viewer.radar.focus":"从语义雷达聚焦{label}","viewer.radar.status":"{count} 个节点 · {viewport}","viewer.radar.fullMap":"{count} 个节点 · 完整地图","viewer.radar.compacted":"已收紧雷达，避免遮挡方法 / 材料与证据或地图控件。","viewer.radar.cancelWaiting":"取消等待更多地图空间的语义雷达","viewer.radar.needsSpace":"语义雷达需要更多可见地图空间","viewer.radar.viewport.full":"完整地图","viewer.radar.viewport.width":"宽度 {percent}%","viewer.radar.viewport.scale":"视口 {percent}%","viewer.nav.controls":"图表视图控制","viewer.nav.route":"追踪有向路径","viewer.nav.route.title":"追踪路径（R）","viewer.nav.route.short":"路径","viewer.nav.radar":"打开语义雷达","viewer.nav.radar.title":"语义雷达（M）","viewer.nav.radar.short":"地图","viewer.nav.lens":"打开语义透镜","viewer.nav.lens.title":"语义透镜（L）","viewer.nav.lens.short":"透镜","viewer.nav.find":"查找节点","viewer.nav.find.title":"查找节点（/）","viewer.nav.guide":"打开图表指南","viewer.nav.guide.title":"图表指南（?）","viewer.nav.zoomOut":"缩小","viewer.nav.zoomOut.title":"缩小（-）","viewer.nav.reset":"重置图表视图","viewer.nav.reset.title":"重置视图（0）","viewer.nav.read":"阅读","viewer.nav.zoomIn":"放大","viewer.nav.zoomIn.title":"放大（+）","viewer.nav.camera":"{hint}。重置图表视图","viewer.nav.camera.title":"{semantic}{hint} · 重置视图（0）","viewer.nav.camera.semantic":"语义相机已启用 · ","viewer.nav.level.map":"概览","viewer.nav.level.read":"阅读","viewer.nav.level.full":"完整","viewer.nav.level.auto":"自动","viewer.nav.detail.map":"放大以显示关系标签和节点上下文","viewer.nav.detail.read":"再次放大以显示标签和注释","viewer.nav.detail.full":"完整图表详情","viewer.intent.summary":"{label}。{out} 条出向，{in} 条入向{loops}。共 {total} 条连接。按 Enter 查看详情。","viewer.intent.loops":"，{count} 条自环","viewer.common.copied":"已复制","viewer.common.copyFailed":"复制失败","viewer.common.copyLink":"复制链接","viewer.common.clear":"清除","viewer.common.close":"关闭"}}<\/script>\r
    <div class="guided-views no-print" id="guided-views" hidden aria-label="图表引导视图">\r
      <button id="guided-view-prev" type="button" aria-label="上一个引导视图" title="上一个引导视图（[）">&#8592;</button>\r
      <div class="guided-view-copy">\r
        <div class="guided-view-meta">\r
          <span>引导视图</span>\r
          <span id="guided-view-count"></span>\r
          <span class="guided-view-progress" aria-hidden="true"><span id="guided-view-progress-bar"></span></span>\r
          <span class="guided-view-handoff" id="guided-view-handoff" hidden aria-hidden="true"></span>\r
        </div>\r
        <strong id="guided-view-label">探索此系统</strong>\r
        <small id="guided-view-note" aria-live="polite" aria-atomic="true">沿精选路径逐步查看，而不改变源图表。</small>\r
        <div class="guided-view-trail" id="guided-view-trail" hidden role="group" aria-label="故事轨迹"></div>\r
        <div class="guided-story-caption" id="guided-story-caption" hidden aria-live="polite" aria-atomic="true">\r
          <span class="guided-story-caption-index" id="guided-story-caption-index">节点</span>\r
          <strong id="guided-story-caption-route"></strong>\r
          <small id="guided-story-caption-detail"></small>\r
          <span class="guided-story-caption-next" id="guided-story-caption-next" hidden aria-hidden="true">\r
            <small>下一步</small>\r
            <strong id="guided-story-caption-next-label"></strong>\r
          </span>\r
        </div>\r
      </div>\r
      <button id="guided-view-next" type="button" aria-label="下一个引导视图" title="下一个引导视图（]）">&#8594;</button>\r
      <div class="guided-view-actions">\r
        <button class="guided-view-play" id="guided-view-play" type="button" aria-label="播放引导故事" aria-pressed="false" title="播放引导故事（P）">\r
          <span id="guided-view-play-icon" aria-hidden="true">&#9654;</span>\r
          <span id="guided-view-play-label">播放故事</span>\r
        </button>\r
        <button class="guided-view-beat-link" id="guided-view-beat-link" type="button" aria-label="选择故事节点以复制其精确链接" title="选择故事节点以复制其精确链接" disabled>\r
          <span aria-hidden="true">&#35;</span>\r
          <span id="guided-view-beat-link-label">复制此刻</span>\r
        </button>\r
        <button class="guided-view-all" id="guided-view-all" type="button" aria-label="显示完整图表">显示全部</button>\r
      </div>\r
      <nav class="guided-view-index" id="guided-view-index" aria-label="故事章节">\r
        <ol class="guided-view-chapters" id="guided-view-chapters"></ol>\r
      </nav>\r
    </div>\r
\r
    <!-- Main Diagram -->\r
    <div class="diagram-container" data-detail-level="read"\r
         data-preset-badge-editorial-plate="FlowBD / 技术谱系">\r
      __FLOWBD_SVG__\r
      <p class="intent-trace-status no-print" id="intent-trace-status" role="status" aria-live="polite" aria-atomic="true"></p>\r
      <div class="share-chapter-cue no-print" id="share-chapter-cue" hidden role="status" aria-live="polite">\r
        <div class="share-chapter-index">\r
          <span class="share-chapter-state" id="share-chapter-state">就绪</span>\r
          <span class="share-chapter-count" id="share-chapter-count">章节 01 / 01</span>\r
        </div>\r
        <div class="share-chapter-copy">\r
          <strong id="share-chapter-label">引导章节</strong>\r
          <small id="share-chapter-note"></small>\r
        </div>\r
        <span class="share-chapter-route" id="share-chapter-route"></span>\r
        <span class="share-chapter-progress" aria-hidden="true"><span id="share-chapter-progress-bar"></span></span>\r
      </div>\r
      <div class="diagram-guide no-print" id="diagram-guide" hidden role="dialog" aria-modal="false" aria-labelledby="diagram-guide-title">\r
        <div class="diagram-guide-head">\r
          <span>\r
            <span class="diagram-guide-eyebrow">图表指南</span>\r
            <strong class="diagram-guide-title" id="diagram-guide-title">探索此系统</strong>\r
          </span>\r
          <button class="diagram-guide-close" id="diagram-guide-close" type="button" aria-label="关闭图表指南">&#215;</button>\r
        </div>\r
        <p class="diagram-guide-stats" id="diagram-guide-stats">正在检查已编译语义</p>\r
        <div class="diagram-guide-actions" id="diagram-guide-actions" role="group" aria-label="图表探索操作">\r
          <button class="diagram-guide-action" type="button" data-guide-action="find" aria-label="查找任意节点">\r
            <span class="diagram-guide-index" aria-hidden="true">01</span>\r
            <span class="diagram-guide-action-copy"><strong>查找任意节点</strong><small>搜索标签、职责、类型和稳定 ID。</small></span>\r
            <kbd aria-hidden="true">/</kbd>\r
          </button>\r
          <button class="diagram-guide-action" type="button" data-guide-action="route" aria-label="追踪有向路径">\r
            <span class="diagram-guide-index" aria-hidden="true">02</span>\r
            <span class="diagram-guide-action-copy"><strong>追踪路径</strong><small>查看两个语义节点如何按编写方向连接。</small></span>\r
            <kbd aria-hidden="true">R</kbd>\r
          </button>\r
          <button class="diagram-guide-action" type="button" data-guide-action="map" aria-label="查看完整系统">\r
            <span class="diagram-guide-index" aria-hidden="true">03</span>\r
            <span class="diagram-guide-action-copy"><strong>查看完整系统</strong><small>打开带实时视口和稳定节点的语义雷达。</small></span>\r
            <kbd aria-hidden="true">M</kbd>\r
          </button>\r
          <button class="diagram-guide-action" type="button" data-guide-action="lens" aria-label="比较语义类型">\r
            <span class="diagram-guide-index" aria-hidden="true">04</span>\r
            <span class="diagram-guide-action-copy"><strong>比较语义类型</strong><small>统计角色、显示流量并比较直接编写的连接。</small></span>\r
            <kbd aria-hidden="true">L</kbd>\r
          </button>\r
          <button class="diagram-guide-action" type="button" data-guide-action="story" aria-label="播放引导故事">\r
            <span class="diagram-guide-index" aria-hidden="true">05</span>\r
            <span class="diagram-guide-action-copy"><strong>播放引导故事</strong><small id="diagram-guide-story-copy">浏览已编写的章节和真实关系。</small></span>\r
            <kbd aria-hidden="true">P</kbd>\r
          </button>\r
          <button class="diagram-guide-action" type="button" data-guide-action="present" aria-label="进入演示模式">\r
            <span class="diagram-guide-index" aria-hidden="true">06</span>\r
            <span class="diagram-guide-action-copy"><strong>进入演示模式</strong><small>让实时图表占满视口，同时不改变导出。</small></span>\r
            <kbd aria-hidden="true">F</kbd>\r
          </button>\r
        </div>\r
        <div class="diagram-guide-shortcuts" aria-label="其他键盘快捷键">\r
          <span><kbd>E</kbd> 导出</span><span><kbd>T</kbd> 主题</span><span><kbd>S</kbd> 风格</span><span><kbd>0</kbd> 重置</span><span><kbd>+</kbd> 放大</span><span><kbd>-</kbd> 缩小</span><span><kbd>Esc</kbd> 关闭</span>\r
        </div>\r
        <p class="diagram-guide-feedback" id="diagram-guide-feedback" aria-live="polite"></p>\r
      </div>\r
      <div class="node-finder no-print" id="node-finder" hidden role="dialog" aria-modal="false" aria-labelledby="node-finder-title">\r
        <div class="node-finder-head">\r
          <strong id="node-finder-title">查找节点</strong>\r
          <button class="node-finder-close" id="node-finder-close" type="button" aria-label="关闭节点查找器">&#215;</button>\r
        </div>\r
        <div class="node-finder-search">\r
          <span aria-hidden="true">&#8981;</span>\r
          <input class="node-finder-input" id="node-finder-input" type="search" autocomplete="off" spellcheck="false" placeholder="搜索标签或 ID" aria-label="搜索图表节点" aria-describedby="node-finder-status">\r
          <kbd aria-hidden="true">/</kbd>\r
        </div>\r
        <div class="node-finder-results" id="node-finder-results" role="group" aria-label="图表节点"></div>\r
        <p class="node-finder-empty" id="node-finder-empty" hidden>没有匹配的节点</p>\r
        <p class="node-finder-status" id="node-finder-status" aria-live="polite"></p>\r
      </div>\r
      <div class="focus-chip relationship-lens no-print" id="focus-chip" hidden role="region" aria-labelledby="relationship-lens-title">\r
        <div class="relationship-lens-head">\r
          <div class="relationship-lens-copy">\r
            <span class="relationship-lens-eyebrow">方法 / 材料与证据</span>\r
            <strong class="relationship-lens-title" id="relationship-lens-title"><span id="focus-label"></span></strong>\r
            <span class="semantic-passport-detail" id="focus-detail" hidden></span>\r
            <div class="semantic-passport-meta" id="focus-passport-meta" aria-label="节点元数据">\r
              <span id="focus-kind" data-passport="kind"></span>\r
              <span id="focus-context" data-passport="context" hidden></span>\r
              <span id="focus-tag" data-passport="tag" hidden></span>\r
              <span id="focus-brand" data-passport="brand" hidden></span>\r
              <code id="focus-id" data-passport="id"></code>\r
            </div>\r
            <div class="semantic-passport-evidence" id="focus-evidence" hidden aria-label="已验证的源代码证据">\r
              <div class="semantic-passport-evidence-head">\r
                <span class="semantic-passport-evidence-status">已验证来源</span>\r
                <a class="semantic-passport-repository" id="focus-repository" target="_blank" rel="noopener noreferrer" referrerpolicy="no-referrer"></a>\r
              </div>\r
              <div class="semantic-passport-evidence-links" id="focus-evidence-links"></div>\r
            </div>\r
            <span class="relationship-lens-summary" id="focus-summary" aria-live="polite"></span>\r
            <div class="semantic-passport-reach" id="focus-reach" hidden>\r
              <span class="semantic-passport-reach-label">直接演化可达范围</span>\r
              <div class="semantic-passport-reach-actions" role="group" aria-label="仅追踪直接演化关系">\r
                <button id="btn-reach-upstream" type="button" aria-label="追踪上游编写可达性" aria-pressed="false">\r
                  <span>上游</span><strong id="focus-reach-upstream-count">0</strong>\r
                </button>\r
                <button id="btn-reach-downstream" type="button" aria-label="追踪下游编写可达性" aria-pressed="false">\r
                  <span>下游</span><strong id="focus-reach-downstream-count">0</strong>\r
                </button>\r
              </div>\r
              <small class="semantic-passport-reach-status" id="focus-reach-status" hidden aria-live="polite"></small>\r
            </div>\r
          </div>\r
          <div class="relationship-lens-actions">\r
            <button id="btn-focus-clear" type="button" aria-label="关闭方法 / 材料与证据" title="关闭">&#215;</button>\r
            <button id="btn-focus-copy" type="button" aria-label="复制聚焦节点的链接">复制链接</button>\r
            <button id="btn-focus-relations" type="button" aria-label="显示关联关系" aria-expanded="false" aria-controls="relationship-lens-list">关系</button>\r
          </div>\r
        </div>\r
        <div class="relationship-lens-list" id="relationship-lens-list" aria-label="关联关系"></div>\r
      </div>\r
      <div class="route-probe no-print" id="route-probe" hidden role="region" aria-labelledby="route-probe-title" data-state="idle">\r
        <div class="route-probe-head">\r
          <span class="route-probe-copy">\r
            <span class="route-probe-eyebrow">路径探测</span>\r
            <strong class="route-probe-title" id="route-probe-title">选择起点节点</strong>\r
          </span>\r
          <span class="route-probe-actions">\r
            <button class="route-probe-find" id="route-probe-find" type="button" aria-label="查找路径起点" data-node-finder-trigger>查找起点</button>\r
            <button class="route-probe-copy-link" id="route-probe-copy" type="button" aria-label="复制已追踪路径的链接" hidden>复制链接</button>\r
            <button id="route-probe-clear" type="button" aria-label="清除路径探测">清除</button>\r
          </span>\r
        </div>\r
        <div class="route-probe-path" id="route-probe-path" aria-label="已追踪路径">\r
          <span class="route-probe-placeholder">在图表中选择两个语义节点</span>\r
        </div>\r
        <div class="route-journey-controls" id="route-journey-controls" hidden role="group" aria-label="路径旅程控制" data-playing="false">\r
          <button id="route-journey-prev" type="button" aria-label="上一个路径位置" title="上一个路径位置">&#8592;</button>\r
          <button class="route-journey-play" id="route-journey-play" type="button" aria-label="播放路径旅程" aria-pressed="false" title="播放路径旅程">\r
            <span id="route-journey-play-icon" aria-hidden="true">&#9654;</span>\r
            <span id="route-journey-play-label">旅程</span>\r
          </button>\r
          <button id="route-journey-next" type="button" aria-label="下一个路径位置" title="下一个路径位置">&#8594;</button>\r
          <button class="route-journey-overview" id="route-journey-overview" type="button" aria-label="显示完整路径总览" title="显示完整路径总览">总览</button>\r
        </div>\r
        <small class="route-probe-status" id="route-probe-status" aria-live="polite">先选择来源，再选择目标；方向很重要。</small>\r
      </div>\r
      <div class="semantic-lens no-print" id="semantic-lens" hidden role="dialog" aria-modal="false" aria-labelledby="semantic-lens-title">\r
        <div class="semantic-lens-head">\r
          <span>\r
            <span class="semantic-lens-eyebrow">语义透镜</span>\r
            <strong class="semantic-lens-title" id="semantic-lens-title">比较系统角色</strong>\r
          </span>\r
          <button class="semantic-lens-close" id="semantic-lens-close" type="button" aria-label="关闭语义透镜">&#215;</button>\r
        </div>\r
        <p class="semantic-lens-instruction">最多选择两种语义类型。选择一种可显示其真实流量；选择两种只比较直接编写的关系。</p>\r
        <div class="semantic-lens-kinds" id="semantic-lens-kinds" role="group" aria-label="语义类型"></div>\r
        <p class="semantic-lens-status" id="semantic-lens-status" aria-live="polite">选择一种类型以检查其节点和相连关系。</p>\r
        <div class="semantic-lens-actions">\r
          <button id="semantic-lens-copy" type="button" aria-label="复制语义透镜链接" hidden>复制链接</button>\r
          <button id="semantic-lens-clear" type="button" aria-label="清除语义透镜">清除</button>\r
        </div>\r
      </div>\r
      <div class="overview-map no-print" id="overview-map" hidden role="region" aria-labelledby="overview-map-title">\r
        <div class="overview-map-head">\r
          <span class="overview-map-live" aria-hidden="true"></span>\r
          <span class="overview-map-copy">\r
            <strong id="overview-map-title">语义雷达</strong>\r
            <small id="overview-map-status" aria-live="polite">正在构建总览</small>\r
          </span>\r
          <button class="overview-map-expand" id="overview-map-expand" type="button" aria-label="打开完整语义雷达">打开雷达</button>\r
          <button class="overview-map-close" id="overview-map-close" type="button" aria-label="关闭语义雷达">&#215;</button>\r
        </div>\r
        <div class="overview-map-surface" id="overview-map-surface" tabindex="0" role="group" aria-label="图表总览。点击节点进行聚焦，或使用方向键平移。"></div>\r
        <div class="overview-map-hint" aria-hidden="true"><span>点击节点</span><span>拖动平移</span></div>\r
      </div>\r
      <p class="overview-map-feedback no-print" id="overview-map-feedback" role="status" aria-live="polite" hidden>语义雷达需要更多地图可见空间。</p>\r
      <div class="diagram-nav no-print" role="toolbar" aria-label="图表视图控制">\r
        <button id="btn-route-probe" type="button" aria-label="追踪有向路径" aria-pressed="false" aria-controls="route-probe" title="追踪路径（R）">路径</button>\r
        <button id="btn-overview-map" type="button" aria-label="打开语义雷达" aria-expanded="false" aria-controls="overview-map" title="语义雷达（M）">地图</button>\r
        <button id="btn-semantic-lens" type="button" aria-label="打开语义透镜" aria-haspopup="dialog" aria-expanded="false" aria-pressed="false" aria-controls="semantic-lens" title="语义透镜（L）">透镜</button>\r
        <button id="btn-node-finder" type="button" aria-label="查找节点" aria-haspopup="dialog" aria-expanded="false" aria-controls="node-finder" title="查找节点（/）" data-node-finder-trigger><span class="diagram-nav-icon find" aria-hidden="true"></span></button>\r
        <button id="btn-diagram-guide" type="button" aria-label="打开图表指南" aria-haspopup="dialog" aria-expanded="false" aria-controls="diagram-guide" title="图表指南（?）"><span class="diagram-nav-icon guide" aria-hidden="true"></span></button>\r
        <button data-view="out" type="button" aria-label="缩小" title="缩小（-）"><span class="diagram-nav-icon minus" aria-hidden="true"></span></button>\r
        <button data-view="reset" type="button" aria-label="重置图表视图" title="重置视图（0）"><span class="diagram-nav-detail" data-view-detail hidden>阅读</span><span class="diagram-nav-percent" data-view-percent>100%</span></button>\r
        <button data-view="in" type="button" aria-label="放大" title="放大（+）"><span class="diagram-nav-icon plus" aria-hidden="true"></span></button>\r
      </div>\r
    </div>\r
\r
    <!-- Info Cards -->\r
    <div class="cards">\r
\r
    </div>\r
\r
  </div>\r
\r
  <script id="flowbd-diagram-data" type="application/json">__FLOWBD_PAYLOAD__<\/script>\r
  <script>\r
    var Archify = {};\r
    var FlowBD = JSON.parse(document.getElementById('flowbd-diagram-data').textContent);\r
    var archifyI18nData = (function () {\r
      var node = document.getElementById('archify-i18n-data');\r
      try { return JSON.parse(node ? node.textContent : '{}'); }\r
      catch (_) { return { locale: 'en', messages: {} }; }\r
    })();\r
    Archify.locale = archifyI18nData.locale || 'en';\r
    Object.assign(archifyI18nData.messages, FlowBD.messages);\r
\r
    function viewerText(key, values) {\r
      var messages = archifyI18nData.messages || {};\r
      var template = Object.prototype.hasOwnProperty.call(messages, key) ? messages[key] : key;\r
      return String(template).replace(/\\{([a-zA-Z0-9_]+)\\}/g, function (match, name) {\r
        return values && Object.prototype.hasOwnProperty.call(values, name) ? String(values[name]) : match;\r
      });\r
    }\r
\r
    function viewerCount(key, count, values) {\r
      var suffix = Number(count) === 1 ? '.one' : '.other';\r
      var payload = Object.assign({}, values || {}, { count: count });\r
      return viewerText(key + suffix, payload);\r
    }\r
\r
    function viewerKindLabel(value) {\r
      var normalized = String(value || 'node').toLowerCase();\r
      var knownKey = 'viewer.kind.' + normalized;\r
      var known = viewerText(knownKey);\r
      if (known !== knownKey) return known;\r
      return normalized\r
        .replace(/messagebus/gi, 'message bus')\r
        .replace(/[-_]+/g, ' ')\r
        .replace(/\\b\\w/g, function (letter) { return letter.toUpperCase(); });\r
    }\r
\r
    function hasDrawableGeometry(element) {\r
      if (!element) return false;\r
      var geometries = /^(path|line|polyline)$/i.test(element.tagName)\r
        ? [element]\r
        : Array.prototype.slice.call(element.querySelectorAll('path, line, polyline'));\r
      return geometries.some(function (geometry) {\r
        var source = geometry.tagName.toLowerCase() === 'path'\r
          ? geometry.getAttribute('d')\r
          : geometry.tagName.toLowerCase() === 'polyline'\r
            ? geometry.getAttribute('points')\r
            : [geometry.getAttribute('x1'), geometry.getAttribute('y1'), geometry.getAttribute('x2'), geometry.getAttribute('y2')].join(' ');\r
        if (!source || /(?:^|[^a-z])(?:nan|infinity)(?:[^a-z]|$)/i.test(source) || typeof geometry.getTotalLength !== 'function') return false;\r
        try {\r
          var length = Number(geometry.getTotalLength());\r
          return Number.isFinite(length) && length > 0;\r
        } catch (_) {\r
          return false;\r
        }\r
      });\r
    }\r
\r
    /* ============================================================\r
       Visual style try-on — one topology, four bundled presets.\r
       The reader's choice is intentionally session-only: it updates the\r
       live page and canonical SVG together, but never rewrites the source,\r
       URL, or a later diagram's authored default.\r
       ============================================================ */\r
    Archify.preset = (function () {\r
      var PRESETS = ['classic', 'signal-flow', 'blueprint', 'editorial'];\r
      var LABELS = {\r
        classic: viewerText('viewer.preset.classic.short'),\r
        'signal-flow': viewerText('viewer.preset.flow.short'),\r
        blueprint: viewerText('viewer.preset.blueprint'),\r
        editorial: viewerText('viewer.preset.editorial')\r
      };\r
      var html = document.documentElement;\r
      var svg = document.querySelector('.diagram-container svg');\r
      var btn = document.getElementById('btn-preset');\r
      var label = document.getElementById('preset-label');\r
      var menu = document.getElementById('preset-menu');\r
      var options = function () {\r
        return Array.prototype.slice.call(menu.querySelectorAll('[data-preset-value]'));\r
      };\r
      var authored = PRESETS.indexOf(html.getAttribute('data-preset')) >= 0\r
        ? html.getAttribute('data-preset')\r
        : 'classic';\r
\r
      function current() {\r
        var value = html.getAttribute('data-preset');\r
        return PRESETS.indexOf(value) >= 0 ? value : authored;\r
      }\r
      function nextAfter(preset) {\r
        return PRESETS[(PRESETS.indexOf(preset) + 1) % PRESETS.length];\r
      }\r
      function apply(preset) {\r
        if (html.getAttribute('data-embed') === 'true') return false;\r
        if (PRESETS.indexOf(preset) < 0) return false;\r
        html.setAttribute('data-preset', preset);\r
        svg.setAttribute('data-preset', preset);\r
        btn.setAttribute('data-preset-option', preset);\r
        label.textContent = LABELS[preset];\r
        btn.setAttribute('aria-label', viewerText('viewer.preset.current', { style: LABELS[preset] }));\r
        btn.title = viewerText('viewer.preset.choose.title');\r
        options().forEach(function (option) {\r
          var selected = option.getAttribute('data-preset-value') === preset;\r
          option.setAttribute('aria-checked', String(selected));\r
        });\r
        return true;\r
      }\r
      function cycle() { return apply(nextAfter(current())); }\r
\r
      function isOpen() { return menu.classList.contains('open'); }\r
      function open(focusLast) {\r
        if (html.getAttribute('data-embed') === 'true') return false;\r
        if (Archify.exportMenu && Archify.exportMenu.isOpen()) Archify.exportMenu.close(false);\r
        menu.classList.add('open');\r
        btn.setAttribute('aria-expanded', 'true');\r
        var available = options();\r
        var selected = available.find(function (option) { return option.getAttribute('aria-checked') === 'true'; });\r
        var target = focusLast ? available[available.length - 1] : (selected || available[0]);\r
        if (target) target.focus();\r
        return true;\r
      }\r
      function close(focusTrigger) {\r
        menu.classList.remove('open');\r
        btn.setAttribute('aria-expanded', 'false');\r
        if (focusTrigger) btn.focus();\r
        return false;\r
      }\r
\r
      apply(authored);\r
      btn.addEventListener('click', function (e) {\r
        e.stopPropagation();\r
        if (isOpen()) close(false);\r
        else open(false);\r
      });\r
      btn.addEventListener('keydown', function (e) {\r
        if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {\r
          e.preventDefault();\r
          if (!isOpen()) open(e.key === 'ArrowUp');\r
        }\r
      });\r
      document.addEventListener('click', function (e) {\r
        if (!menu.contains(e.target) && e.target !== btn) close(false);\r
      });\r
      menu.addEventListener('click', function (e) {\r
        var option = e.target.closest('[data-preset-value]');\r
        if (!option || !menu.contains(option)) return;\r
        if (apply(option.getAttribute('data-preset-value'))) close(true);\r
      });\r
      menu.addEventListener('keydown', function (e) {\r
        if (e.key === 'Escape') { e.preventDefault(); close(true); return; }\r
        if (e.key === 'Tab') { close(false); return; }\r
        var available = options();\r
        var active = available.indexOf(document.activeElement);\r
        switch (e.key) {\r
          case 'ArrowDown':\r
            e.preventDefault();\r
            if (available.length) available[(active + 1 + available.length) % available.length].focus();\r
            break;\r
          case 'ArrowUp':\r
            e.preventDefault();\r
            if (available.length) available[(active - 1 + available.length) % available.length].focus();\r
            break;\r
          case 'Home':\r
            e.preventDefault();\r
            if (available[0]) available[0].focus();\r
            break;\r
          case 'End':\r
            e.preventDefault();\r
            if (available.length) available[available.length - 1].focus();\r
            break;\r
        }\r
      });\r
      return { cycle: cycle, apply: apply, current: current, authored: authored, open: open, close: close, isOpen: isOpen };\r
    })();\r
\r
    /* ============================================================\r
       Theme toggle — persists to localStorage, respects system pref\r
       ============================================================ */\r
\r
    Archify.theme = (function () {\r
      var STORAGE_KEY = 'flowbd-diagram-theme';\r
      var html = document.documentElement;\r
      var btn = document.getElementById('btn-theme');\r
      var label = document.getElementById('theme-label');\r
\r
      // localStorage can throw (blocked cookies, sandboxed iframes); the whole\r
      // script element dies on an uncaught error, so guard every access.\r
      function readStored() {\r
        try { return localStorage.getItem(STORAGE_KEY); } catch (_) { return null; }\r
      }\r
      function writeStored(value) {\r
        try { localStorage.setItem(STORAGE_KEY, value); } catch (_) {}\r
      }\r
      function urlOverride() {\r
        // URL param wins (useful for deterministic screenshots / share links)\r
        try {\r
          var param = new URLSearchParams(window.location.search).get('theme');\r
          if (param === 'light' || param === 'dark') return param;\r
        } catch (_) {}\r
        return null;\r
      }\r
\r
      function resolveInitial() {\r
        var fromUrl = urlOverride();\r
        if (fromUrl) return fromUrl;\r
        var saved = readStored();\r
        if (saved === 'light' || saved === 'dark') return saved;\r
        return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';\r
      }\r
\r
      function apply(theme) {\r
        html.setAttribute('data-theme', theme);\r
        label.textContent = viewerText(theme === 'dark' ? 'viewer.theme.dark' : 'viewer.theme.light');\r
        btn.setAttribute('aria-pressed', theme === 'light' ? 'true' : 'false');\r
      }\r
\r
      function toggle() {\r
        var next = html.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';\r
        apply(next);\r
        writeStored(next);\r
      }\r
\r
      apply(resolveInitial());\r
      btn.addEventListener('click', toggle);\r
\r
      // Follow live OS theme changes while the user has no explicit preference.\r
      try {\r
        var media = window.matchMedia('(prefers-color-scheme: light)');\r
        var onChange = function (e) {\r
          var saved = readStored();\r
          if (urlOverride() || saved === 'light' || saved === 'dark') return;\r
          apply(e.matches ? 'light' : 'dark');\r
        };\r
        if (media.addEventListener) media.addEventListener('change', onChange);\r
        else if (media.addListener) media.addListener(onChange);\r
      } catch (_) {}\r
\r
      return { toggle: toggle };\r
    })();\r
\r
    /* ============================================================\r
       Export — Share Card / PNG / JPEG / WebP / SVG / WebM and clipboard\r
\r
       Raster exports are always rendered at 4x source resolution for\r
       maximum sharpness. The trick: we set the serialized SVG's\r
       \`width\`/\`height\` to viewBox * 4 so the browser rasterizes the\r
       vectors at that resolution natively. drawImage then draws at\r
       the image's natural size (no upscaling = no blur).\r
\r
       JPEG/WebP paint the current theme's background explicitly since\r
       those formats have no alpha channel.\r
       ============================================================ */\r
    (function () {\r
      var RASTER_SCALE = 4;\r
      var MOTION_DURATION = 6000;\r
      var MOTION_FPS = 30;\r
      var SHARE_CARD_WIDTH = 1200;\r
      var SHARE_CARD_HEIGHT = 630;\r
      var SHARE_CARD_PADDING = 36;\r
      var SHARE_CARD_HEADER = 112;\r
\r
      function exportError(key, values) {\r
        var error = new Error(viewerText(key, values));\r
        error.archifyViewerMessage = true;\r
        return error;\r
      }\r
\r
      function exportMessage(error) {\r
        return error && error.archifyViewerMessage\r
          ? error.message\r
          : viewerText('viewer.export.unknown');\r
      }\r
\r
      function diagramFilename() {\r
        var title = (document.title || 'diagram')\r
          .replace(/\\s+Architecture(\\s+Diagram)?$/i, '')\r
          .replace(/\\s+Diagram$/i, '')\r
          .trim();\r
        return title.replace(/[^a-z0-9_\\-]+/gi, '-')\r
                    .toLowerCase()\r
                    .replace(/^-+|-+$/g, '') || 'diagram';\r
      }\r
\r
      function currentBg() {\r
        return getComputedStyle(document.body).backgroundColor || '#ffffff';\r
      }\r
\r
      function cleanExportClone(clone) {\r
        // View transforms and neighborhood focus are HTML exploration state,\r
        // never part of a downloaded full-diagram artifact.\r
        clone.style.removeProperty('transform');\r
        clone.style.removeProperty('clip-path');\r
        clone.removeAttribute('data-view-scale');\r
        clone.removeAttribute('data-focus-active');\r
        clone.removeAttribute('data-reach-active');\r
        clone.removeAttribute('data-lens-active');\r
        clone.removeAttribute('data-lens-flow-count');\r
        clone.removeAttribute('data-lens-flow-density');\r
        clone.removeAttribute('data-legend-preview-active');\r
        clone.removeAttribute('data-relationship-preview-active');\r
        clone.removeAttribute('data-relationship-direct-active');\r
        clone.removeAttribute('data-relationship-pin-active');\r
        clone.removeAttribute('data-intent-trace-active');\r
        clone.removeAttribute('data-route-picking');\r
        clone.removeAttribute('data-route-active');\r
        clone.removeAttribute('data-route-journey');\r
        clone.removeAttribute('data-share-route');\r
        clone.removeAttribute('data-share-reach');\r
        clone.removeAttribute('data-story-active');\r
        clone.removeAttribute('data-story-playing');\r
        clone.removeAttribute('data-story-beat');\r
        clone.removeAttribute('data-story-next');\r
        clone.removeAttribute('data-story-follow');\r
        clone.removeAttribute('data-chapter-handoff');\r
        clone.removeAttribute('data-chapter-anchor');\r
        clone.removeAttribute('data-chapter-preview');\r
        Array.prototype.forEach.call(clone.querySelectorAll('[data-chapter-handoff-overlay]'), function (el) {\r
          el.remove();\r
        });\r
        Array.prototype.forEach.call(clone.querySelectorAll('[data-chapter-role]'), function (el) {\r
          el.removeAttribute('data-chapter-role');\r
        });\r
        Array.prototype.forEach.call(clone.querySelectorAll('[data-chapter-preview-role]'), function (el) {\r
          el.removeAttribute('data-chapter-preview-role');\r
        });\r
        Array.prototype.forEach.call(clone.querySelectorAll('[data-story-overlay], [data-story-carrier-overlay]'), function (el) {\r
          el.remove();\r
        });\r
        Array.prototype.forEach.call(clone.querySelectorAll('[data-intent-trace-overlay]'), function (el) {\r
          el.remove();\r
        });\r
        Array.prototype.forEach.call(clone.querySelectorAll('[data-route-probe-overlay]'), function (el) {\r
          el.remove();\r
        });\r
        Array.prototype.forEach.call(clone.querySelectorAll('[data-route-journey-overlay]'), function (el) {\r
          el.remove();\r
        });\r
        Array.prototype.forEach.call(clone.querySelectorAll('[data-semantic-lens-overlay]'), function (el) {\r
          el.remove();\r
        });\r
        Array.prototype.forEach.call(clone.querySelectorAll('[data-legend-bridge-runtime]'), function (el) {\r
          el.remove();\r
        });\r
        Array.prototype.forEach.call(clone.querySelectorAll('[data-legend-kind]'), function (el) {\r
          el.removeAttribute('data-legend-kind');\r
          el.removeAttribute('data-legend-label');\r
          el.removeAttribute('data-legend-count');\r
          el.removeAttribute('data-legend-zero');\r
          el.removeAttribute('data-legend-selected');\r
          el.removeAttribute('role');\r
          el.removeAttribute('tabindex');\r
          el.removeAttribute('aria-label');\r
          el.removeAttribute('aria-pressed');\r
          el.removeAttribute('aria-haspopup');\r
          el.removeAttribute('aria-controls');\r
          el.removeAttribute('aria-expanded');\r
        });\r
        Array.prototype.forEach.call(clone.querySelectorAll('[data-legend-bridge]'), function (el) {\r
          el.removeAttribute('data-legend-bridge');\r
          el.removeAttribute('role');\r
          el.removeAttribute('aria-label');\r
        });\r
        Array.prototype.forEach.call(clone.querySelectorAll('[data-relationship-pulse-overlay]'), function (el) {\r
          el.remove();\r
        });\r
        Array.prototype.forEach.call(clone.querySelectorAll('[data-relationship-hit-overlay]'), function (el) {\r
          el.remove();\r
        });\r
        Array.prototype.forEach.call(clone.querySelectorAll('[data-source-evidence-beacon]'), function (el) {\r
          el.remove();\r
        });\r
        Array.prototype.forEach.call(clone.querySelectorAll('[data-source-evidence-count]'), function (el) {\r
          var originalLabel = el.getAttribute('data-source-evidence-original-label');\r
          if (originalLabel == null || originalLabel === '') el.removeAttribute('aria-label');\r
          else el.setAttribute('aria-label', originalLabel);\r
          el.removeAttribute('data-source-evidence-count');\r
          el.removeAttribute('data-source-evidence-original-label');\r
        });\r
        Array.prototype.forEach.call(clone.querySelectorAll('[data-story-step], [data-story-beat-state], [data-story-beat-step]'), function (el) {\r
          el.removeAttribute('data-story-step');\r
          el.removeAttribute('data-story-beat-state');\r
          el.removeAttribute('data-story-beat-step');\r
          el.style.removeProperty('--story-step');\r
        });\r
        Array.prototype.forEach.call(clone.querySelectorAll('[data-focus-match], [data-focus-selected]'), function (el) {\r
          el.removeAttribute('data-focus-match');\r
          el.removeAttribute('data-focus-selected');\r
        });\r
        Array.prototype.forEach.call(clone.querySelectorAll('[data-reach-match], [data-reach-origin], [data-reach-depth]'), function (el) {\r
          el.removeAttribute('data-reach-match');\r
          el.removeAttribute('data-reach-origin');\r
          el.removeAttribute('data-reach-depth');\r
        });\r
        Array.prototype.forEach.call(clone.querySelectorAll('[data-lens-match], [data-lens-selected], [data-lens-peer]'), function (el) {\r
          el.removeAttribute('data-lens-match');\r
          el.removeAttribute('data-lens-selected');\r
          el.removeAttribute('data-lens-peer');\r
        });\r
        Array.prototype.forEach.call(clone.querySelectorAll('[data-legend-preview-match], [data-legend-preview-selected], [data-legend-preview-peer]'), function (el) {\r
          el.removeAttribute('data-legend-preview-match');\r
          el.removeAttribute('data-legend-preview-selected');\r
          el.removeAttribute('data-legend-preview-peer');\r
        });\r
        Array.prototype.forEach.call(clone.querySelectorAll('[data-relationship-preview], [data-relationship-preview-node], [data-relationship-preview-source], [data-relationship-preview-target]'), function (el) {\r
          el.removeAttribute('data-relationship-preview');\r
          el.removeAttribute('data-relationship-preview-node');\r
          el.removeAttribute('data-relationship-preview-source');\r
          el.removeAttribute('data-relationship-preview-target');\r
        });\r
        Array.prototype.forEach.call(clone.querySelectorAll('[data-intent-trace-match], [data-intent-trace-selected]'), function (el) {\r
          el.removeAttribute('data-intent-trace-match');\r
          el.removeAttribute('data-intent-trace-selected');\r
        });\r
        Array.prototype.forEach.call(clone.querySelectorAll('[data-route-match], [data-route-start], [data-route-end], [data-route-step], [data-route-candidate], [data-route-journey-state], [data-route-journey-current]'), function (el) {\r
          el.removeAttribute('data-route-match');\r
          el.removeAttribute('data-route-start');\r
          el.removeAttribute('data-route-end');\r
          el.removeAttribute('data-route-step');\r
          el.removeAttribute('data-route-candidate');\r
          el.removeAttribute('data-route-journey-state');\r
          el.removeAttribute('data-route-journey-current');\r
          el.style.removeProperty('--route-step');\r
        });\r
        Array.prototype.forEach.call(clone.querySelectorAll('[data-share-route-match], [data-share-route-step], [data-share-route-start], [data-share-route-end], [data-share-route-middle]'), function (el) {\r
          el.removeAttribute('data-share-route-match');\r
          el.removeAttribute('data-share-route-step');\r
          el.removeAttribute('data-share-route-start');\r
          el.removeAttribute('data-share-route-end');\r
          el.removeAttribute('data-share-route-middle');\r
        });\r
        Array.prototype.forEach.call(clone.querySelectorAll('[data-share-reach-match], [data-share-reach-origin], [data-share-reach-depth]'), function (el) {\r
          el.removeAttribute('data-share-reach-match');\r
          el.removeAttribute('data-share-reach-origin');\r
          el.removeAttribute('data-share-reach-depth');\r
        });\r
        Array.prototype.forEach.call(clone.querySelectorAll('[data-detail], [data-detail-anchor]'), function (el) {\r
          el.removeAttribute('data-detail');\r
          el.removeAttribute('data-detail-anchor');\r
        });\r
        Array.prototype.forEach.call(clone.querySelectorAll('[data-node-id][aria-pressed]'), function (el) {\r
          el.setAttribute('aria-pressed', 'false');\r
        });\r
        return !clone.hasAttribute('data-view-scale') &&\r
          !clone.hasAttribute('data-focus-active') &&\r
          !clone.hasAttribute('data-reach-active') &&\r
          !clone.hasAttribute('data-lens-active') &&\r
          !clone.hasAttribute('data-lens-flow-count') &&\r
          !clone.hasAttribute('data-lens-flow-density') &&\r
          !clone.hasAttribute('data-legend-preview-active') &&\r
          !clone.hasAttribute('data-relationship-preview-active') &&\r
          !clone.hasAttribute('data-relationship-direct-active') &&\r
          !clone.hasAttribute('data-intent-trace-active') &&\r
          !clone.hasAttribute('data-route-picking') &&\r
          !clone.hasAttribute('data-route-active') &&\r
          !clone.hasAttribute('data-route-journey') &&\r
          !clone.hasAttribute('data-share-route') &&\r
          !clone.hasAttribute('data-share-reach') &&\r
          !clone.hasAttribute('data-story-active') &&\r
          !clone.hasAttribute('data-story-playing') &&\r
          !clone.hasAttribute('data-story-beat') &&\r
          !clone.hasAttribute('data-story-next') &&\r
          !clone.hasAttribute('data-story-follow') &&\r
          !clone.hasAttribute('data-chapter-handoff') &&\r
          !clone.hasAttribute('data-chapter-anchor') &&\r
          !clone.hasAttribute('data-chapter-preview') &&\r
          !clone.style.getPropertyValue('transform') &&\r
          !clone.style.getPropertyValue('clip-path') &&\r
          clone.querySelectorAll('[data-story-overlay], [data-story-carrier-overlay], [data-story-carrier-token], [data-story-step], [data-story-beat-state], [data-story-beat-step], [data-chapter-handoff-overlay], [data-chapter-role], [data-chapter-preview-role], [data-focus-match], [data-focus-selected], [data-reach-match], [data-reach-origin], [data-reach-depth], [data-semantic-lens-overlay], [data-lens-match], [data-lens-selected], [data-lens-peer], [data-legend-bridge], [data-legend-kind], [data-legend-bridge-runtime], [data-legend-count], [data-legend-zero], [data-legend-selected], [data-legend-preview-match], [data-legend-preview-selected], [data-legend-preview-peer], [data-relationship-hit-overlay], [data-relationship-pulse-overlay], [data-relationship-preview], [data-relationship-preview-node], [data-relationship-preview-source], [data-relationship-preview-target], [data-intent-trace-overlay], [data-intent-trace-match], [data-intent-trace-selected], [data-route-probe-overlay], [data-route-journey-overlay], [data-route-match], [data-route-start], [data-route-end], [data-route-step], [data-route-candidate], [data-route-journey-state], [data-route-journey-current], [data-share-route-match], [data-share-route-step], [data-share-route-start], [data-share-route-end], [data-share-route-middle], [data-share-reach-match], [data-share-reach-origin], [data-share-reach-depth], [data-source-evidence-beacon], [data-source-evidence-count], [data-source-evidence-original-label], [data-detail], [data-detail-anchor]').length === 0;\r
      }\r
\r
\r
      /**\r
       * Serialize the main SVG into a standalone document.\r
       *\r
       * Two modes:\r
       * - Default (opts.autoTheme=false) — locks the serialized SVG to the\r
       *   viewer's current theme. Used by the raster pipeline\r
       *   (PNG/JPEG/WebP/clipboard) because canvas rasterization needs\r
       *   deterministic colors; a raster cannot react to\r
       *   prefers-color-scheme after encoding.\r
       * - autoTheme=true — emits BOTH dark and light variable sets plus a\r
       *   \`@media (prefers-color-scheme)\` rule so the resulting SVG\r
       *   self-themes when embedded in GitHub READMEs or other hosts that\r
       *   expose a color scheme. Used for "Download SVG".\r
       */\r
      function applyRouteSnapshot(clone, snapshot) {\r
        if (!snapshot || !Array.isArray(snapshot.nodeIds) || !Array.isArray(snapshot.edges) ||\r
            snapshot.nodeIds.length < 2 || snapshot.edges.length !== snapshot.nodeIds.length - 1 ||\r
            snapshot.hops !== snapshot.edges.length ||\r
            !snapshot.source || !snapshot.target ||\r
            snapshot.source.id !== snapshot.nodeIds[0] ||\r
            snapshot.target.id !== snapshot.nodeIds[snapshot.nodeIds.length - 1]) return false;\r
\r
        clone.removeAttribute('data-animation');\r
        Array.prototype.forEach.call(clone.querySelectorAll('[data-animate]'), function (element) {\r
          element.removeAttribute('data-animate');\r
          element.style.removeProperty('--step');\r
        });\r
\r
        var cloneNodes = Array.prototype.slice.call(clone.querySelectorAll('[data-node-id]'));\r
        var cloneEdges = Array.prototype.slice.call(clone.querySelectorAll('[data-edge-key]'));\r
        var nodeIds = Object.create(null);\r
        var edgeKeys = Object.create(null);\r
        var nodeMatches = [];\r
        var edgeMatches = [];\r
\r
        for (var nodeIndex = 0; nodeIndex < snapshot.nodeIds.length; nodeIndex++) {\r
          var nodeId = snapshot.nodeIds[nodeIndex];\r
          if (typeof nodeId !== 'string' || !nodeId || nodeIds[nodeId]) return false;\r
          var matchedNodes = cloneNodes.filter(function (candidate) {\r
            return candidate.getAttribute('data-node-id') === nodeId;\r
          });\r
          if (matchedNodes.length !== 1) return false;\r
          nodeIds[nodeId] = true;\r
          nodeMatches.push(matchedNodes);\r
        }\r
\r
        for (var edgeIndex = 0; edgeIndex < snapshot.edges.length; edgeIndex++) {\r
          var edge = snapshot.edges[edgeIndex];\r
          var fromId = snapshot.nodeIds[edgeIndex];\r
          var toId = snapshot.nodeIds[edgeIndex + 1];\r
          if (!edge || typeof edge.key !== 'string' || !edge.key || edgeKeys[edge.key] ||\r
              edge.from !== fromId || edge.to !== toId) return false;\r
          var matchedEdges = cloneEdges.filter(function (candidate) {\r
            return candidate.getAttribute('data-edge-key') === edge.key;\r
          });\r
          var drawableMatches = matchedEdges.filter(hasDrawableGeometry);\r
          if (!matchedEdges.length || drawableMatches.length !== 1 || !matchedEdges.every(function (candidate) {\r
            return candidate.getAttribute('data-edge-from') === edge.from &&\r
              candidate.getAttribute('data-edge-to') === edge.to &&\r
              (candidate.getAttribute('data-edge-id') || '') === (edge.id || '');\r
          })) return false;\r
          edgeKeys[edge.key] = true;\r
          edgeMatches.push(matchedEdges);\r
        }\r
\r
        clone.setAttribute('data-share-route', '');\r
        nodeMatches.forEach(function (matches, step) {\r
          matches.forEach(function (element) {\r
            element.setAttribute('data-share-route-match', '');\r
            element.setAttribute('data-share-route-step', String(step));\r
            if (step === 0) element.setAttribute('data-share-route-start', '');\r
            else if (step === snapshot.nodeIds.length - 1) element.setAttribute('data-share-route-end', '');\r
            else element.setAttribute('data-share-route-middle', '');\r
          });\r
        });\r
        edgeMatches.forEach(function (matches, step) {\r
          matches.forEach(function (element) {\r
            element.setAttribute('data-share-route-match', '');\r
            element.setAttribute('data-share-route-step', String(step));\r
          });\r
        });\r
\r
        return clone.hasAttribute('data-share-route') &&\r
          !clone.hasAttribute('data-animation') &&\r
          !clone.hasAttribute('data-route-active') &&\r
          !clone.hasAttribute('data-route-journey') &&\r
          clone.querySelectorAll('[data-animate], [data-route-match], [data-route-step], [data-route-start], [data-route-end], [data-route-journey-state], [data-route-journey-current], [data-route-journey-overlay]').length === 0 &&\r
          clone.querySelectorAll('[data-share-route-match]').length ===\r
            nodeMatches.reduce(function (count, matches) { return count + matches.length; }, 0) +\r
            edgeMatches.reduce(function (count, matches) { return count + matches.length; }, 0);\r
      }\r
\r
      function applyReachSnapshot(clone, snapshot) {\r
        if (!snapshot || (snapshot.direction !== 'upstream' && snapshot.direction !== 'downstream') ||\r
            !snapshot.origin || typeof snapshot.origin.id !== 'string' || !snapshot.origin.id ||\r
            typeof snapshot.origin.label !== 'string' || !snapshot.origin.label.trim() ||\r
            !Array.isArray(snapshot.nodeIds) || snapshot.nodeIds.length < 2 ||\r
            !Array.isArray(snapshot.edges) || !snapshot.edges.length ||\r
            !snapshot.depths || typeof snapshot.depths !== 'object' ||\r
            !Number.isInteger(snapshot.maxDepth) || snapshot.maxDepth < 1 ||\r
            snapshot.nodeIds[0] !== snapshot.origin.id) return false;\r
\r
        clone.removeAttribute('data-animation');\r
        Array.prototype.forEach.call(clone.querySelectorAll('[data-animate]'), function (element) {\r
          element.removeAttribute('data-animate');\r
          element.style.removeProperty('--step');\r
        });\r
\r
        var cloneNodes = Array.prototype.slice.call(clone.querySelectorAll('[data-node-id]'));\r
        var cloneEdges = Array.prototype.slice.call(clone.querySelectorAll('[data-edge-key]'));\r
        var nodeIds = Object.create(null);\r
        var edgeKeys = Object.create(null);\r
        var nodeMatches = [];\r
        var edgeMatches = [];\r
        var measuredMaxDepth = 0;\r
\r
        for (var nodeIndex = 0; nodeIndex < snapshot.nodeIds.length; nodeIndex++) {\r
          var nodeId = snapshot.nodeIds[nodeIndex];\r
          var depth = snapshot.depths[nodeId];\r
          if (typeof nodeId !== 'string' || !nodeId || nodeIds[nodeId] ||\r
              !Number.isInteger(depth) || depth < 0 || depth > snapshot.maxDepth ||\r
              (nodeId === snapshot.origin.id ? depth !== 0 : depth < 1)) return false;\r
          var matchedNodes = cloneNodes.filter(function (candidate) {\r
            return candidate.getAttribute('data-node-id') === nodeId;\r
          });\r
          if (matchedNodes.length !== 1) return false;\r
          nodeIds[nodeId] = true;\r
          measuredMaxDepth = Math.max(measuredMaxDepth, depth);\r
          nodeMatches.push({ elements: matchedNodes, id: nodeId, depth: depth });\r
        }\r
        if (measuredMaxDepth !== snapshot.maxDepth) return false;\r
\r
        for (var edgeIndex = 0; edgeIndex < snapshot.edges.length; edgeIndex++) {\r
          var edge = snapshot.edges[edgeIndex];\r
          if (!edge || typeof edge.key !== 'string' || !edge.key || edgeKeys[edge.key] ||\r
              !nodeIds[edge.from] || !nodeIds[edge.to] ||\r
              !Number.isInteger(edge.depth) || edge.depth < 1 || edge.depth > snapshot.maxDepth ||\r
              edge.depth !== Math.max(snapshot.depths[edge.from], snapshot.depths[edge.to])) return false;\r
          var matchedEdges = cloneEdges.filter(function (candidate) {\r
            return candidate.getAttribute('data-edge-key') === edge.key;\r
          });\r
          var drawableMatches = matchedEdges.filter(hasDrawableGeometry);\r
          if (!matchedEdges.length || drawableMatches.length !== 1 || !matchedEdges.every(function (candidate) {\r
            return candidate.getAttribute('data-edge-from') === edge.from &&\r
              candidate.getAttribute('data-edge-to') === edge.to &&\r
              (candidate.getAttribute('data-edge-id') || '') === (edge.id || '');\r
          })) return false;\r
          edgeKeys[edge.key] = true;\r
          edgeMatches.push({ elements: matchedEdges, depth: edge.depth });\r
        }\r
\r
        clone.setAttribute('data-share-reach', snapshot.direction);\r
        nodeMatches.forEach(function (match) {\r
          match.elements.forEach(function (element) {\r
            element.setAttribute('data-share-reach-match', '');\r
            element.setAttribute('data-share-reach-depth', String(match.depth));\r
            if (match.id === snapshot.origin.id) element.setAttribute('data-share-reach-origin', '');\r
          });\r
        });\r
        edgeMatches.forEach(function (match) {\r
          match.elements.forEach(function (element) {\r
            element.setAttribute('data-share-reach-match', '');\r
            element.setAttribute('data-share-reach-depth', String(match.depth));\r
          });\r
        });\r
\r
        return clone.getAttribute('data-share-reach') === snapshot.direction &&\r
          !clone.hasAttribute('data-animation') &&\r
          !clone.hasAttribute('data-reach-active') &&\r
          clone.querySelectorAll('[data-animate], [data-reach-match], [data-reach-origin], [data-reach-depth]').length === 0 &&\r
          clone.querySelectorAll('[data-share-reach-origin]').length === 1 &&\r
          clone.querySelectorAll('[data-share-reach-match]').length ===\r
            nodeMatches.reduce(function (count, match) { return count + match.elements.length; }, 0) +\r
            edgeMatches.reduce(function (count, match) { return count + match.elements.length; }, 0);\r
      }\r
\r
      function serializeSvg(scale, opts) {\r
        // scale: integer multiplier for intrinsic SVG pixel dimensions used by\r
        // the raster path. Defaults to 1 (natural size) for SVG download.\r
        scale = scale || 1;\r
        opts = opts || {};\r
        var autoTheme = opts.autoTheme === true;\r
        var svg = document.querySelector('.diagram-container svg');\r
        var clone = svg.cloneNode(true);\r
\r
        var canonicalStateClean = cleanExportClone(clone);\r
\r
        var vb = svg.viewBox.baseVal;\r
        var finiteSvgDimensions = Number.isFinite(vb.x) && Number.isFinite(vb.y) &&\r
          Number.isFinite(vb.width) && Number.isFinite(vb.height) && vb.width > 0 && vb.height > 0;\r
        var routeStateClean = opts.routeSnapshot\r
          ? canonicalStateClean && finiteSvgDimensions && applyRouteSnapshot(clone, opts.routeSnapshot)\r
          : null;\r
        var reachStateClean = opts.reachSnapshot\r
          ? canonicalStateClean && finiteSvgDimensions && !opts.routeSnapshot && applyReachSnapshot(clone, opts.reachSnapshot)\r
          : null;\r
        // Scale width/height so the browser rasterizes the vectors at target\r
        // resolution directly. viewBox stays unchanged so coordinates don't\r
        // shift. This is the key to sharp rasters — do NOT scale later via\r
        // canvas upscaling.\r
        clone.setAttribute('width', vb.width * scale);\r
        clone.setAttribute('height', vb.height * scale);\r
        clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');\r
\r
        // Only the SVG-relevant rules: semantic classes, markers, and the\r
        // theme variable blocks. Toolbar/cards/print CSS can never apply\r
        // inside a standalone SVG and would only bloat the export.\r
        var hostStyle = (function () {\r
          var out = [];\r
          Array.prototype.forEach.call(document.styleSheets, function (sheet) {\r
            var rules;\r
            try { rules = sheet.cssRules; } catch (_) { return; } // cross-origin\r
            if (!rules) return;\r
            Array.prototype.forEach.call(rules, function (rule) {\r
              if (rule.type === 7 && /^archify-/.test(rule.name || '')) {\r
                out.push(rule.cssText);\r
                return;\r
              }\r
              if (rule.type !== 1) return; // plain style rules only\r
              var sel = rule.selectorText || '';\r
              if (/(^|,)\\s*(svg|:root|\\[data-theme|\\[data-preset|\\.c-|\\.t-|\\.a-|\\.m-)/.test(sel)) {\r
                out.push(rule.cssText);\r
              }\r
            });\r
          });\r
          return out.join('\\n');\r
        })();\r
\r
        // Derive the variable list from the stylesheet so newly added theme\r
        // variables can never be missed by the export pipeline again\r
        // (--lane-fill/--lane-stroke once were).\r
        var varNames = (function () {\r
          var seen = {};\r
          var names = [];\r
          (hostStyle.match(/--[a-zA-Z0-9-]+(?=\\s*:)/g) || []).forEach(function (n) {\r
            if (!seen[n]) { seen[n] = true; names.push(n); }\r
          });\r
          return names;\r
        })();\r
\r
        // Resolve the full variable set for a given data-theme via an\r
        // off-DOM probe, independent of what the viewer is currently set to.\r
        function resolveVars(themeAttr) {\r
          var probe = document.createElement('div');\r
          probe.setAttribute('data-theme', themeAttr);\r
          probe.setAttribute('data-preset', document.documentElement.getAttribute('data-preset') || 'classic');\r
          probe.style.cssText = 'position:absolute;width:0;height:0;visibility:hidden;';\r
          document.body.appendChild(probe);\r
          try {\r
            var c = getComputedStyle(probe);\r
            return varNames.map(function (n) {\r
              return n + ': ' + c.getPropertyValue(n).trim() + ';';\r
            }).join(' ');\r
          } finally {\r
            document.body.removeChild(probe);\r
          }\r
        }\r
\r
        // Keep the same font bytes, character coverage, and attribution in\r
        // standalone SVGs and the SVG images used by every raster export.\r
        var fontCss = document.getElementById('archify-fonts').textContent;\r
\r
        var style = document.createElementNS('http://www.w3.org/2000/svg', 'style');\r
        var bgRect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');\r
        bgRect.setAttribute('width', '100%');\r
        bgRect.setAttribute('height', '100%');\r
\r
        if (autoTheme) {\r
          // Dual-theme SVG. Dark is the default (so hosts without\r
          // prefers-color-scheme still render), light swaps in via media\r
          // query, and svg[data-theme="..."] still lets downstream\r
          // consumers force a specific theme.\r
          var darkVars = resolveVars('dark');\r
          var lightVars = resolveVars('light');\r
\r
          style.textContent =\r
            fontCss + "\\n" +\r
            "svg { font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Consolas, 'DejaVu Sans Mono', 'Liberation Mono', 'Noto Sans Mono CJK SC', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', monospace; }\\n" +\r
            hostStyle + "\\n" +\r
            ":root, svg { " + darkVars + " }\\n" +\r
            "@media (prefers-color-scheme: light) { :root, svg { " + lightVars + " } }\\n" +\r
            "svg[data-theme=\\"light\\"] { " + lightVars + " }\\n" +\r
            "svg[data-theme=\\"dark\\"] { " + darkVars + " }\\n" +\r
            "rect.c-bg-rect { fill: var(--bg); }\\n";\r
\r
          // Don't lock the serialized SVG to the viewer's current theme.\r
          clone.removeAttribute('data-theme');\r
          // Background follows the CSS variable, not a fixed color, so it\r
          // swaps with the media query.\r
          bgRect.setAttribute('class', 'c-bg-rect');\r
        } else {\r
          // Raster path: lock to the viewer's current theme.\r
          var theme = document.documentElement.getAttribute('data-theme') || 'dark';\r
          var themeHost = document.querySelector('[data-theme="' + theme + '"]') || document.documentElement;\r
          var computed = getComputedStyle(themeHost);\r
          var vars = varNames.map(function (n) {\r
            return n + ': ' + computed.getPropertyValue(n).trim() + ';';\r
          }).join(' ');\r
\r
          // IMPORTANT: inject the resolved variables AFTER hostStyle,\r
          // otherwise hostStyle's ":root, [data-theme=\\"dark\\"] { ... }" rule\r
          // overrides our chosen theme via later-in-cascade equal-specificity.\r
          // Keep this order.\r
          style.textContent =\r
            fontCss + "\\n" +\r
            "svg { font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Consolas, 'DejaVu Sans Mono', 'Liberation Mono', 'Noto Sans Mono CJK SC', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', monospace; }\\n" +\r
            hostStyle + "\\n" +\r
            ":root, svg { " + vars + " }\\n";\r
\r
          bgRect.setAttribute('fill', computed.getPropertyValue('--bg').trim() || '#ffffff');\r
        }\r
\r
        if (opts.routeSnapshot) {\r
          style.textContent += "\\nsvg[data-share-route] [data-node-id], svg[data-share-route] [data-edge-from] { opacity: 0.18; }\\n" +\r
            "svg[data-share-route] [data-share-route-match] { opacity: 1; }\\n" +\r
            "svg[data-share-route] [data-share-route-start] > :is(rect, circle, polygon):not(.c-mask) { stroke-width: 3; stroke-dasharray: 5 3; }\\n" +\r
            "svg[data-share-route] [data-share-route-middle] > :is(rect, circle, polygon):not(.c-mask) { stroke-width: 2.2; }\\n" +\r
            "svg[data-share-route] [data-share-route-end] > :is(rect, circle, polygon):not(.c-mask) { stroke-width: 3.4; stroke-dasharray: 1 0; }\\n";\r
        }\r
        if (opts.reachSnapshot) {\r
          style.textContent += "\\nsvg[data-share-reach] [data-node-id], svg[data-share-reach] [data-edge-from] { opacity: 0.14; }\\n" +\r
            "svg[data-share-reach] [data-share-reach-match] { opacity: 1; }\\n" +\r
            "svg[data-share-reach] [data-edge-from][data-share-reach-match] { stroke-width: 1.55; }\\n" +\r
            "svg[data-share-reach=\\"upstream\\"] [data-share-reach-origin] > :is(rect, circle, polygon):not(.c-mask) { stroke: var(--database-stroke); stroke-width: 3.4; stroke-dasharray: 5 3; }\\n" +\r
            "svg[data-share-reach=\\"downstream\\"] [data-share-reach-origin] > :is(rect, circle, polygon):not(.c-mask) { stroke: var(--backend-stroke); stroke-width: 3.4; stroke-dasharray: 1 0; }\\n" +\r
            "svg[data-preset=\\"blueprint\\"][data-share-reach] [data-share-reach-origin], svg[data-preset=\\"blueprint\\"][data-share-reach] [data-edge-from][data-share-reach-match] { filter: none; }\\n";\r
        }\r
\r
        clone.insertBefore(style, clone.firstChild);\r
        clone.insertBefore(bgRect, style.nextSibling);\r
\r
        // The XML declaration pins UTF-8: without it, consumers that guess an\r
        // encoding instead of defaulting to UTF-8 mangle non-ASCII text.\r
        return {\r
          svgString: '<?xml version="1.0" encoding="UTF-8"?>\\n' +\r
            new XMLSerializer().serializeToString(clone),\r
          width: vb.width * scale,\r
          height: vb.height * scale,\r
          canonicalStateClean: canonicalStateClean,\r
          routeStateClean: routeStateClean,\r
          reachStateClean: reachStateClean\r
        };\r
      }\r
\r
      function download(blob, filename) {\r
        var url = URL.createObjectURL(blob);\r
        var a = document.createElement('a');\r
        a.href = url;\r
        a.download = filename;\r
        document.body.appendChild(a);\r
        a.click();\r
        a.remove();\r
        setTimeout(function () { URL.revokeObjectURL(url); }, 1000);\r
      }\r
\r
      // Conservative upper bound on total canvas pixels. Older Safari on iOS\r
      // silently produces a blank canvas above ~16 Mpx; Chrome / Firefox /\r
      // desktop Safari are far higher but start failing on memory-constrained\r
      // devices. We pick the largest integer scale in {4,3,2,1} whose target\r
      // pixel count fits under this cap.\r
      var MAX_CANVAS_PIXELS = 16 * 1024 * 1024;\r
\r
      function pickSafeScale(vbW, vbH) {\r
        for (var s = RASTER_SCALE; s >= 1; s--) {\r
          if (vbW * s * vbH * s <= MAX_CANVAS_PIXELS) return s;\r
        }\r
        return 1;\r
      }\r
\r
      function rasterize(format) {\r
        // Serialize at a safe scale (RASTER_SCALE=4 by default, reduced if the\r
        // resulting canvas would exceed MAX_CANVAS_PIXELS). The SVG itself is\r
        // rasterized at target resolution natively; drawImage draws at natural\r
        // size — no upsampling blur.\r
        var svg = document.querySelector('.diagram-container svg');\r
        var vb = svg.viewBox.baseVal;\r
        var scale = pickSafeScale(vb.width, vb.height);\r
        var data = serializeSvg(scale);\r
        var svgBlob = new Blob([data.svgString], { type: 'image/svg+xml;charset=utf-8' });\r
        var svgUrl = URL.createObjectURL(svgBlob);\r
\r
        return new Promise(function (resolve, reject) {\r
          var img = new Image();\r
          img.onload = function () {\r
            try {\r
              var canvas = document.createElement('canvas');\r
              canvas.width = data.width;\r
              canvas.height = data.height;\r
              var ctx = canvas2dOrThrow(canvas, format);\r
              if (format === 'jpeg') {\r
                ctx.fillStyle = currentBg();\r
                ctx.fillRect(0, 0, canvas.width, canvas.height);\r
              }\r
              // Draw at natural size — SVG was already rasterized at target res.\r
              ctx.drawImage(img, 0, 0);\r
              URL.revokeObjectURL(svgUrl);\r
              var mime = format === 'jpeg' ? 'image/jpeg' :\r
                         format === 'webp' ? 'image/webp' : 'image/png';\r
              var quality = format === 'png' ? undefined : 0.95;\r
              canvas.toBlob(function (blob) {\r
                if (!blob) reject(exportError('viewer.export.error.toBlobNull', { label: format }));\r
                else resolve(blob);\r
              }, mime, quality);\r
            } catch (error) {\r
              URL.revokeObjectURL(svgUrl);\r
              reject(error);\r
            }\r
          };\r
          img.onerror = function (e) {\r
            URL.revokeObjectURL(svgUrl);\r
            reject(e);\r
          };\r
          img.src = svgUrl;\r
        });\r
      }\r
\r
      function fitCanvasText(ctx, text, maxWidth, startSize, minSize, weight) {\r
        var value = String(text || '').trim();\r
        var size = startSize;\r
        var family = "'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Consolas, monospace";\r
        while (size > minSize) {\r
          ctx.font = (weight || '600') + ' ' + size + 'px ' + family;\r
          if (ctx.measureText(value).width <= maxWidth) return value;\r
          size -= 1;\r
        }\r
        ctx.font = (weight || '600') + ' ' + minSize + 'px ' + family;\r
        if (ctx.measureText(value).width <= maxWidth) return value;\r
        var suffix = '\\u2026';\r
        while (value.length > 1 && ctx.measureText(value + suffix).width > maxWidth) {\r
          value = value.slice(0, -1);\r
        }\r
        return value + suffix;\r
      }\r
\r
      function canvas2dOrThrow(canvas, label) {\r
        if (!canvas || typeof canvas.getContext !== 'function') {\r
          throw exportError('viewer.export.error.canvasUnavailable', { label: label });\r
        }\r
        var ctx = canvas.getContext('2d');\r
        if (!ctx) throw exportError('viewer.export.error.contextUnavailable', { label: label });\r
        if (typeof canvas.toBlob !== 'function') throw exportError('viewer.export.error.toBlobUnavailable', { label: label });\r
        return ctx;\r
      }\r
\r
      function renderShareCard(options) {\r
        options = options || {};\r
        var routeSnapshot = options.routeSnapshot || null;\r
        var reachSnapshot = options.reachSnapshot || null;\r
        if (routeSnapshot && reachSnapshot) return Promise.reject(exportError('viewer.export.error.variantsCombined'));\r
        var svg = document.querySelector('.diagram-container svg');\r
        var vb = svg.viewBox.baseVal;\r
        var sourceScale = Math.min(2, pickSafeScale(vb.width, vb.height));\r
        var data = serializeSvg(sourceScale, { routeSnapshot: routeSnapshot, reachSnapshot: reachSnapshot });\r
        if (!data.canonicalStateClean) return Promise.reject(exportError('viewer.export.error.viewerState'));\r
        if (routeSnapshot && !data.routeStateClean) return Promise.reject(exportError('viewer.export.error.routeState'));\r
        if (reachSnapshot && !data.reachStateClean) return Promise.reject(exportError('viewer.export.error.reachState'));\r
        var svgBlob = new Blob([data.svgString], { type: 'image/svg+xml;charset=utf-8' });\r
        var svgUrl = URL.createObjectURL(svgBlob);\r
\r
        return new Promise(function (resolve, reject) {\r
          var img = new Image();\r
          img.onload = function () {\r
            try {\r
              var canvas = document.createElement('canvas');\r
              canvas.width = SHARE_CARD_WIDTH;\r
              canvas.height = SHARE_CARD_HEIGHT;\r
              var ctx = canvas2dOrThrow(canvas, viewerText('viewer.export.shareCard'));\r
              var computed = getComputedStyle(document.documentElement);\r
              var bg = computed.getPropertyValue('--bg').trim() || currentBg();\r
              var text = computed.getPropertyValue('--text').trim() || '#ffffff';\r
              var muted = computed.getPropertyValue('--text-muted').trim() || '#94a3b8';\r
              var border = computed.getPropertyValue('--panel-border').trim() || '#334155';\r
              var accentProperty = reachSnapshot\r
                ? (reachSnapshot.direction === 'upstream' ? '--database-stroke' : '--backend-stroke')\r
                : '--frontend-stroke';\r
              var accent = computed.getPropertyValue(accentProperty).trim() || '#22d3ee';\r
              var titleNode = document.querySelector('.header h1');\r
              var subtitleNode = document.querySelector('.header .subtitle');\r
              var title = titleNode ? titleNode.textContent : document.title;\r
              var directionLabel = reachSnapshot\r
                ? viewerText('viewer.export.direction.' + reachSnapshot.direction)\r
                : '';\r
              var subtitle = routeSnapshot\r
                ? viewerCount('viewer.export.card.routeSummary', routeSnapshot.hops, {\r
                    source: routeSnapshot.source.label,\r
                    target: routeSnapshot.target.label\r
                  })\r
                : reachSnapshot\r
                  ? viewerText('viewer.export.card.reachSummary', {\r
                      direction: directionLabel,\r
                      origin: reachSnapshot.origin.label,\r
                      nodes: viewerCount('viewer.export.card.node', reachSnapshot.nodeIds.length - 1),\r
                      links: viewerCount('viewer.export.card.link', reachSnapshot.edges.length),\r
                      hops: viewerCount('viewer.export.card.hop', reachSnapshot.maxDepth)\r
                    })\r
                  : subtitleNode ? subtitleNode.textContent : '';\r
              var preset = document.documentElement.getAttribute('data-preset') || 'classic';\r
              var theme = document.documentElement.getAttribute('data-theme') || 'dark';\r
              var presetKey = preset === 'signal-flow'\r
                ? 'viewer.preset.flow.short'\r
                : 'viewer.preset.' + preset;\r
              var presetLabel = viewerText(presetKey).toUpperCase();\r
              var themeLabel = viewerText('viewer.theme.' + theme).toUpperCase();\r
              var cardLabel = routeSnapshot\r
                ? viewerText('viewer.export.card.routeBadge', {\r
                    hops: viewerCount('viewer.export.card.hop', routeSnapshot.hops).toUpperCase()\r
                  })\r
                : reachSnapshot\r
                  ? viewerText('viewer.export.card.reachBadge', { direction: directionLabel.toUpperCase() })\r
                  : viewerText('viewer.export.card.defaultBadge', { preset: presetLabel, theme: themeLabel });\r
\r
              ctx.fillStyle = bg;\r
              ctx.fillRect(0, 0, SHARE_CARD_WIDTH, SHARE_CARD_HEIGHT);\r
\r
              ctx.fillStyle = accent;\r
              ctx.fillRect(SHARE_CARD_PADDING, 27, 42, 3);\r
\r
              ctx.textBaseline = 'alphabetic';\r
              ctx.fillStyle = text;\r
              var fittedTitle = fitCanvasText(ctx, title, SHARE_CARD_WIDTH - SHARE_CARD_PADDING * 2 - 330, 29, 18, '700');\r
              ctx.fillText(fittedTitle, SHARE_CARD_PADDING, 62);\r
\r
              ctx.fillStyle = muted;\r
              var fittedSubtitle = fitCanvasText(ctx, subtitle, SHARE_CARD_WIDTH - SHARE_CARD_PADDING * 2 - 280, 13, 11, '500');\r
              ctx.fillText(fittedSubtitle, SHARE_CARD_PADDING, 87);\r
\r
              ctx.font = "600 12px 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Consolas, monospace";\r
              ctx.textAlign = 'right';\r
              ctx.fillStyle = accent;\r
              ctx.fillText(cardLabel, SHARE_CARD_WIDTH - SHARE_CARD_PADDING, 50);\r
              ctx.textAlign = 'left';\r
\r
              var availableWidth = SHARE_CARD_WIDTH - SHARE_CARD_PADDING * 2;\r
              var availableHeight = SHARE_CARD_HEIGHT - SHARE_CARD_HEADER - SHARE_CARD_PADDING;\r
              var fit = Math.min(availableWidth / data.width, availableHeight / data.height);\r
              var drawWidth = data.width * fit;\r
              var drawHeight = data.height * fit;\r
              var drawX = SHARE_CARD_PADDING + (availableWidth - drawWidth) / 2;\r
              var drawY = SHARE_CARD_HEADER + (availableHeight - drawHeight) / 2;\r
\r
              ctx.strokeStyle = border;\r
              ctx.lineWidth = 1;\r
              ctx.strokeRect(drawX - 0.5, drawY - 0.5, drawWidth + 1, drawHeight + 1);\r
              ctx.drawImage(img, drawX, drawY, drawWidth, drawHeight);\r
              URL.revokeObjectURL(svgUrl);\r
\r
              canvas.toBlob(function (blob) {\r
                if (!blob) reject(exportError('viewer.export.error.toBlobNull', { label: viewerText('viewer.export.shareCard') }));\r
                else resolve(blob);\r
              }, 'image/png');\r
            } catch (error) {\r
              URL.revokeObjectURL(svgUrl);\r
              reject(error);\r
            }\r
          };\r
          img.onerror = function (e) {\r
            URL.revokeObjectURL(svgUrl);\r
            reject(e);\r
          };\r
          img.src = svgUrl;\r
        });\r
      }\r
\r
      function rasterizeShareCard(options) {\r
        options = options || {};\r
        if (!options.variant) return renderShareCard();\r
        if (options.variant !== 'route' && options.variant !== 'reach') {\r
          return Promise.reject(exportError('viewer.export.unknownVariant', { variant: options.variant }));\r
        }\r
        if (options.variant === 'route') {\r
          var routeSnapshot = Archify.routeProbe && Archify.routeProbe.exportSnapshot();\r
          if (!routeSnapshot) return Promise.reject(exportError('viewer.export.routeRequired'));\r
          return renderShareCard({ routeSnapshot: routeSnapshot });\r
        }\r
        var snapshot = Archify.focus && typeof Archify.focus.reachabilitySnapshot === 'function'\r
          ? Archify.focus.reachabilitySnapshot()\r
          : null;\r
        if (!snapshot) return Promise.reject(exportError('viewer.export.reachRequired'));\r
        return renderShareCard({ reachSnapshot: snapshot });\r
      }\r
\r
      function motionMimeType() {\r
        if (typeof MediaRecorder === 'undefined') return '';\r
        var candidates = [\r
          'video/webm;codecs=vp9',\r
          'video/webm;codecs=vp8',\r
          'video/webm'\r
        ];\r
        for (var i = 0; i < candidates.length; i++) {\r
          if (!MediaRecorder.isTypeSupported || MediaRecorder.isTypeSupported(candidates[i])) return candidates[i];\r
        }\r
        return '';\r
      }\r
\r
      function canRecordMotion() {\r
        var svg = document.querySelector('.diagram-container svg');\r
        return !!(svg && svg.getAttribute('data-animation') === 'trace' &&\r
          typeof MediaRecorder !== 'undefined' && motionMimeType() &&\r
          typeof HTMLCanvasElement !== 'undefined' &&\r
          typeof HTMLCanvasElement.prototype.captureStream === 'function');\r
      }\r
\r
      // Record the live CSS animation without Puppeteer, ffmpeg, or a network\r
      // dependency. SVG files loaded through Image are commonly rasterized as\r
      // one cached bitmap, so repeatedly drawing that Image does not reliably\r
      // advance its CSS animation. Keep one crisp static SVG background, then\r
      // render an explicit time-varying signal scene over the real authored\r
      // relationship geometry on every captured canvas frame.\r
      function recordWebm(options) {\r
        options = options || {};\r
        if (!canRecordMotion()) {\r
          return Promise.reject(exportError('viewer.export.error.webmRequirements'));\r
        }\r
        var duration = Math.max(250, Number(options.duration) || MOTION_DURATION);\r
        var fps = Math.max(1, Number(options.fps) || MOTION_FPS);\r
        var svg = document.querySelector('.diagram-container svg');\r
        var vb = svg.viewBox.baseVal;\r
        var scale = Math.min(1, 1280 / vb.width);\r
        var data = serializeSvg(scale);\r
        var sourceUrl = URL.createObjectURL(new Blob([data.svgString], { type: 'image/svg+xml;charset=utf-8' }));\r
\r
        function createMotionScene(root) {\r
          var rootMatrix = root.getCTM ? root.getCTM() : null;\r
\r
          function pointInRoot(element, point) {\r
            if (!rootMatrix || !element.getCTM || !point.matrixTransform) return { x: point.x, y: point.y };\r
            try {\r
              var elementMatrix = element.getCTM();\r
              if (!elementMatrix) return { x: point.x, y: point.y };\r
              var mapped = point.matrixTransform(rootMatrix.inverse().multiply(elementMatrix));\r
              return { x: mapped.x, y: mapped.y };\r
            } catch (_) {\r
              return { x: point.x, y: point.y };\r
            }\r
          }\r
\r
          function samplesFor(element) {\r
            if (typeof element.getTotalLength !== 'function' || typeof element.getPointAtLength !== 'function') return [];\r
            var length;\r
            try { length = element.getTotalLength(); } catch (_) { return []; }\r
            if (!Number.isFinite(length) || length <= 0) return [];\r
            var count = Math.max(12, Math.min(72, Math.ceil(length / 12)));\r
            var points = [];\r
            for (var i = 0; i <= count; i++) {\r
              points.push(pointInRoot(element, element.getPointAtLength(length * i / count)));\r
            }\r
            return points;\r
          }\r
\r
          function authoredStep(element, fallback) {\r
            var raw = element.style.getPropertyValue('--step') || getComputedStyle(element).getPropertyValue('--step');\r
            var value = Number(raw);\r
            return Number.isFinite(value) ? value : fallback;\r
          }\r
\r
          var edges = Array.prototype.slice.call(root.querySelectorAll('[data-animate="edge"]')).map(function (element, index) {\r
            var computed = getComputedStyle(element);\r
            return {\r
              points: samplesFor(element),\r
              color: computed.stroke && computed.stroke !== 'none' ? computed.stroke : '#22d3ee',\r
              width: Math.max(1.5, parseFloat(computed.strokeWidth) || 1.5),\r
              delay: Math.min(12, authoredStep(element, index)) * 0.16\r
            };\r
          }).filter(function (edge) { return edge.points.length > 1; });\r
\r
          var nodes = Array.prototype.slice.call(root.querySelectorAll('[data-node-id][data-animate="node"]')).map(function (element, index) {\r
            var box;\r
            try { box = element.getBBox(); } catch (_) { return null; }\r
            var painted = element.querySelector('[class*="c-"]') || element;\r
            var computed = getComputedStyle(painted);\r
            return {\r
              x: box.x,\r
              y: box.y,\r
              width: box.width,\r
              height: box.height,\r
              color: computed.stroke && computed.stroke !== 'none' ? computed.stroke : '#22d3ee',\r
              delay: Math.min(12, authoredStep(element, index)) * 0.16\r
            };\r
          }).filter(Boolean);\r
\r
          return { edges: edges, nodes: nodes, x: vb.x, y: vb.y, width: vb.width, height: vb.height };\r
        }\r
\r
        function pointAlong(points, progress) {\r
          var scaled = Math.max(0, Math.min(1, progress)) * (points.length - 1);\r
          var index = Math.min(points.length - 2, Math.floor(scaled));\r
          var mix = scaled - index;\r
          return {\r
            x: points[index].x + (points[index + 1].x - points[index].x) * mix,\r
            y: points[index].y + (points[index + 1].y - points[index].y) * mix\r
          };\r
        }\r
\r
        function roundedRectPath(ctx, x, y, width, height, radius) {\r
          var r = Math.max(0, Math.min(radius, width / 2, height / 2));\r
          ctx.beginPath();\r
          ctx.moveTo(x + r, y);\r
          ctx.lineTo(x + width - r, y);\r
          ctx.quadraticCurveTo(x + width, y, x + width, y + r);\r
          ctx.lineTo(x + width, y + height - r);\r
          ctx.quadraticCurveTo(x + width, y + height, x + width - r, y + height);\r
          ctx.lineTo(x + r, y + height);\r
          ctx.quadraticCurveTo(x, y + height, x, y + height - r);\r
          ctx.lineTo(x, y + r);\r
          ctx.quadraticCurveTo(x, y, x + r, y);\r
          ctx.closePath();\r
        }\r
\r
        function drawMotionFrame(ctx, backgroundImage, motionScene, elapsed) {\r
          ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);\r
          ctx.drawImage(backgroundImage, 0, 0, ctx.canvas.width, ctx.canvas.height);\r
          ctx.save();\r
          ctx.scale(ctx.canvas.width / motionScene.width, ctx.canvas.height / motionScene.height);\r
          ctx.translate(-motionScene.x, -motionScene.y);\r
\r
          motionScene.edges.forEach(function (edge) {\r
            var duration = 1.75;\r
            var progress = (elapsed - edge.delay) / duration;\r
            if (progress < 0 || progress > 1) return;\r
            var head = Math.max(0, Math.min(1, progress));\r
            var tail = Math.max(0, head - 0.24);\r
            var opacity = Math.sin(Math.PI * Math.min(1, progress));\r
\r
            ctx.save();\r
            ctx.strokeStyle = edge.color;\r
            ctx.fillStyle = edge.color;\r
            ctx.lineCap = 'round';\r
            ctx.lineJoin = 'round';\r
            ctx.lineWidth = Math.max(3.2, edge.width * 2.2);\r
            ctx.globalAlpha = 0.42 + opacity * 0.5;\r
            ctx.shadowColor = edge.color;\r
            ctx.shadowBlur = 10;\r
            ctx.beginPath();\r
            for (var i = 0; i <= 14; i++) {\r
              var trailPoint = pointAlong(edge.points, tail + (head - tail) * i / 14);\r
              if (i === 0) ctx.moveTo(trailPoint.x, trailPoint.y);\r
              else ctx.lineTo(trailPoint.x, trailPoint.y);\r
            }\r
            ctx.stroke();\r
\r
            var point = pointAlong(edge.points, head);\r
            ctx.globalAlpha = 0.95;\r
            ctx.beginPath();\r
            ctx.arc(point.x, point.y, 4.8, 0, Math.PI * 2);\r
            ctx.fill();\r
            ctx.restore();\r
          });\r
\r
          motionScene.nodes.forEach(function (node) {\r
            var progress = (elapsed - node.delay) / 2.6;\r
            if (progress < 0 || progress > 1) return;\r
            var pulse = Math.sin(Math.PI * progress);\r
            if (pulse <= 0.02) return;\r
            ctx.save();\r
            ctx.strokeStyle = node.color;\r
            ctx.lineWidth = 1.4 + pulse * 1.8;\r
            ctx.globalAlpha = pulse * 0.5;\r
            ctx.shadowColor = node.color;\r
            ctx.shadowBlur = 12 * pulse;\r
            var inset = 2 + pulse * 3;\r
            roundedRectPath(ctx, node.x - inset, node.y - inset, node.width + inset * 2, node.height + inset * 2, 8);\r
            ctx.stroke();\r
            ctx.restore();\r
          });\r
\r
          ctx.restore();\r
        }\r
\r
        var motionScene = createMotionScene(svg);\r
\r
        return new Promise(function (resolve, reject) {\r
          var backgroundImage = new Image();\r
          backgroundImage.onload = function () {\r
            var canvas = document.createElement('canvas');\r
            canvas.width = Math.max(2, Math.round(data.width / 2) * 2);\r
            canvas.height = Math.max(2, Math.round(data.height / 2) * 2);\r
            var ctx = canvas.getContext('2d');\r
            var stream = canvas.captureStream(fps);\r
            var mime = motionMimeType();\r
            var recorder;\r
            try {\r
              recorder = new MediaRecorder(stream, { mimeType: mime, videoBitsPerSecond: 6000000 });\r
            } catch (err) {\r
              URL.revokeObjectURL(sourceUrl);\r
              stream.getTracks().forEach(function (track) { track.stop(); });\r
              reject(err);\r
              return;\r
            }\r
            var chunks = [];\r
            var raf = 0;\r
            var stopped = false;\r
            var startedAt = performance.now();\r
            function cleanup() {\r
              if (stopped) return;\r
              stopped = true;\r
              cancelAnimationFrame(raf);\r
              URL.revokeObjectURL(sourceUrl);\r
              stream.getTracks().forEach(function (track) { track.stop(); });\r
            }\r
            function draw(now) {\r
              var elapsed = Math.max(0, ((Number(now) || performance.now()) - startedAt) / 1000);\r
              drawMotionFrame(ctx, backgroundImage, motionScene, elapsed);\r
              raf = requestAnimationFrame(draw);\r
            }\r
            recorder.ondataavailable = function (event) {\r
              if (event.data && event.data.size) chunks.push(event.data);\r
            };\r
            recorder.onerror = function (event) {\r
              cleanup();\r
              reject(event.error || exportError('viewer.export.error.mediaRecorder'));\r
            };\r
            recorder.onstop = function () {\r
              cleanup();\r
              var blob = new Blob(chunks, { type: recorder.mimeType || mime });\r
              if (!blob.size) reject(exportError('viewer.export.error.emptyWebm'));\r
              else resolve(blob);\r
            };\r
            drawMotionFrame(ctx, backgroundImage, motionScene, 0);\r
            recorder.start(250);\r
            startedAt = performance.now();\r
            raf = requestAnimationFrame(draw);\r
            setTimeout(function () {\r
              if (recorder.state === 'inactive') return;\r
              // Chromium normally emits the final chunk during stop(), but\r
              // some embedded browser shells need an explicit encoder flush\r
              // first. Keep the short grace window bounded and harmless for\r
              // browsers that already delivered timeslice chunks.\r
              try { recorder.requestData(); } catch (_) {}\r
              setTimeout(function () {\r
                if (recorder.state !== 'inactive') recorder.stop();\r
              }, 120);\r
            }, duration);\r
          };\r
          backgroundImage.onerror = function () {\r
            URL.revokeObjectURL(sourceUrl);\r
            reject(exportError('viewer.export.error.webmBackground'));\r
          };\r
          backgroundImage.src = sourceUrl;\r
        });\r
      }\r
\r
      var menu = document.getElementById('export-menu');\r
      var btn = document.getElementById('btn-export');\r
      var routeShareItem = menu.querySelector('button[data-action="route-share-card"]');\r
      var reachShareItem = menu.querySelector('button[data-action="reach-share-card"]');\r
      var items = function () {\r
        return Array.prototype.slice.call(menu.querySelectorAll('button[role="menuitem"]'));\r
      };\r
\r
      function syncRouteShareItem() {\r
        var snapshot = Archify.routeProbe && typeof Archify.routeProbe.exportSnapshot === 'function'\r
          ? Archify.routeProbe.exportSnapshot()\r
          : null;\r
        routeShareItem.hidden = !snapshot;\r
        routeShareItem.disabled = !snapshot;\r
        return snapshot;\r
      }\r
\r
      function syncReachShareItem() {\r
        var snapshot = Archify.focus && typeof Archify.focus.reachabilitySnapshot === 'function'\r
          ? Archify.focus.reachabilitySnapshot()\r
          : null;\r
        reachShareItem.hidden = !snapshot;\r
        reachShareItem.disabled = !snapshot;\r
        return snapshot;\r
      }\r
\r
      // ---- Clipboard support ----------------------------------------------\r
      function canCopyImage() {\r
        return typeof ClipboardItem !== 'undefined' &&\r
               navigator.clipboard &&\r
               typeof navigator.clipboard.write === 'function';\r
      }\r
\r
      // ---- Raster format detection ----------------------------------------\r
      // canvas.toBlob('image/webp') silently returns a PNG on browsers without\r
      // WebP encoding (older Safari), so detect explicitly.\r
      function supports(format) {\r
        if (format === 'share-card') return true;\r
        if (format === 'svg' || format === 'png') return true;\r
        if (format === 'webm') return canRecordMotion();\r
        var mime = format === 'jpeg' ? 'image/jpeg' : 'image/webp';\r
        try {\r
          var c = document.createElement('canvas');\r
          c.width = c.height = 2;\r
          return c.toDataURL(mime).indexOf('data:' + mime) === 0;\r
        } catch (_) { return false; }\r
      }\r
\r
      // Gray out unsupported items.\r
      items().forEach(function (it) {\r
        if (it.dataset.format && !supports(it.dataset.format)) {\r
          it.disabled = true;\r
          it.title = viewerText('viewer.export.unsupported');\r
        }\r
        if ((it.dataset.action === 'copy' || it.dataset.action === 'copy-share-card') && !canCopyImage()) {\r
          it.disabled = true;\r
          it.title = viewerText('viewer.export.clipboardUnsupported');\r
        }\r
      });\r
\r
      // ---- Toast ----------------------------------------------------------\r
      // A live region only announces CHANGES to an existing node, so the toast\r
      // element is created once up front and updated in place.\r
      var toastEl = document.createElement('div');\r
      toastEl.className = 'archify-toast';\r
      toastEl.setAttribute('role', 'status');\r
      document.body.appendChild(toastEl);\r
      var toastTimer = null;\r
\r
      function toast(msg) {\r
        toastEl.textContent = '';\r
        requestAnimationFrame(function () {\r
          toastEl.textContent = msg;\r
          toastEl.classList.add('show');\r
        });\r
        clearTimeout(toastTimer);\r
        toastTimer = setTimeout(function () { toastEl.classList.remove('show'); }, 1500);\r
      }\r
\r
      function open(focusLast) {\r
        if (Archify.preset && Archify.preset.isOpen()) Archify.preset.close(false);\r
        if (Archify.semanticLens && typeof Archify.semanticLens.clearPreview === 'function') Archify.semanticLens.clearPreview();\r
        if (Archify.semanticLens && Archify.semanticLens.isOpen()) Archify.semanticLens.close({ restoreFocus: false });\r
        syncRouteShareItem();\r
        syncReachShareItem();\r
        menu.classList.add('open');\r
        btn.setAttribute('aria-expanded', 'true');\r
        var available = items().filter(function (i) { return !i.hidden && !i.disabled; });\r
        var target = focusLast ? available[available.length - 1] : available[0];\r
        if (target) target.focus();\r
      }\r
      function close(focusTrigger) {\r
        menu.classList.remove('open');\r
        btn.setAttribute('aria-expanded', 'false');\r
        if (focusTrigger) btn.focus();\r
      }\r
      function isOpen() { return menu.classList.contains('open'); }\r
\r
      btn.addEventListener('click', function (e) {\r
        e.stopPropagation();\r
        if (isOpen()) close(false);\r
        else open();\r
      });\r
      // APG menu-button pattern: ArrowDown/ArrowUp on the trigger opens the menu.\r
      btn.addEventListener('keydown', function (e) {\r
        if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {\r
          e.preventDefault();\r
          if (!isOpen()) open(e.key === 'ArrowUp');\r
        }\r
      });\r
      document.addEventListener('click', function (e) {\r
        if (!menu.contains(e.target) && e.target !== btn) close(false);\r
      });\r
\r
      // Keyboard navigation inside the menu.\r
      //   Menu items: Up/Down, Home/End.\r
      //   Esc closes + returns focus to trigger; Tab closes.\r
      menu.addEventListener('keydown', function (e) {\r
        if (e.key === 'Escape') { e.preventDefault(); close(true); return; }\r
        if (e.key === 'Tab')    { close(false); return; }\r
\r
        var available = items().filter(function (i) { return !i.hidden && !i.disabled; });\r
        var current = available.indexOf(document.activeElement);\r
        switch (e.key) {\r
          case 'ArrowDown':\r
            e.preventDefault();\r
            if (available.length) available[(current + 1 + available.length) % available.length].focus();\r
            break;\r
          case 'ArrowUp':\r
            e.preventDefault();\r
            if (available.length) available[(current - 1 + available.length) % available.length].focus();\r
            break;\r
          case 'Home':\r
            e.preventDefault();\r
            if (available[0]) available[0].focus();\r
            break;\r
          case 'End':\r
            e.preventDefault();\r
            if (available.length) available[available.length - 1].focus();\r
            break;\r
        }\r
      });\r
\r
      function runExport(format) {\r
        var base = diagramFilename();\r
        close(true);\r
        clearExportReceipt();\r
        if (format === 'webm') toast(viewerText('viewer.export.recording'));\r
        return (format === 'share-card'\r
          ? rasterizeShareCard().then(function (blob) {\r
              recordExportReceipt('share-card', blob, true, { width: SHARE_CARD_WIDTH, height: SHARE_CARD_HEIGHT });\r
              download(blob, base + '-share-card.png');\r
              toast(viewerText('viewer.export.downloadedShare'));\r
            })\r
          : format === 'svg'\r
          ? Promise.resolve(serializeSvg(1, { autoTheme: true })).then(function (d) {\r
              var blob = new Blob([d.svgString], { type: 'image/svg+xml;charset=utf-8' });\r
              recordExportReceipt('svg', blob, d.canonicalStateClean);\r
              download(blob, base + '.svg');\r
            })\r
          : format === 'webm'\r
            ? recordWebm().then(function (blob) {\r
                document.documentElement.setAttribute('data-last-motion-bytes', String(blob.size));\r
                recordExportReceipt('webm', blob, true);\r
                download(blob, base + '.webm');\r
                toast(viewerText('viewer.export.downloadedWebm'));\r
              })\r
          : rasterize(format).then(function (blob) {\r
              recordExportReceipt(format, blob, true);\r
              download(blob, base + '.' + format);\r
            })\r
        ).catch(function (err) {\r
          console.error(err);\r
          var technicalMessage = err && err.message ? err.message : format;\r
          var message = exportMessage(err);\r
          document.documentElement.setAttribute('data-last-export-error-format', format);\r
          document.documentElement.setAttribute('data-last-export-error', technicalMessage);\r
          if (format === 'webm') {\r
            var motionItem = menu.querySelector('button[data-format="webm"]');\r
            if (motionItem) {\r
              motionItem.disabled = true;\r
              motionItem.title = viewerText('viewer.export.motionUnavailable');\r
              motionItem.style.opacity = '0.5';\r
            }\r
            toast(viewerText('viewer.export.webmUnavailable'));\r
            return;\r
          }\r
          alert(viewerText('viewer.export.failed', { message: message }));\r
        });\r
      }\r
\r
      function runRouteShareCard() {\r
        close(false);\r
        clearExportReceipt();\r
        var snapshot = Archify.routeProbe && Archify.routeProbe.exportSnapshot();\r
        var blobPromise = snapshot\r
          ? renderShareCard({ routeSnapshot: snapshot })\r
          : Promise.reject(exportError('viewer.export.routeRequired'));\r
        return blobPromise.then(function (blob) {\r
          recordExportReceipt('share-card', blob, false, { width: SHARE_CARD_WIDTH, height: SHARE_CARD_HEIGHT }, 'route', true);\r
          download(blob, diagramFilename() + '-route-share-card.png');\r
          toast(viewerText('viewer.export.downloadedRoute'));\r
          return blob;\r
        }).catch(function (err) {\r
          console.error(err);\r
          var technicalMessage = err && err.message ? err.message : 'share-card';\r
          var message = exportMessage(err);\r
          document.documentElement.setAttribute('data-last-export-error-format', 'share-card');\r
          document.documentElement.setAttribute('data-last-export-error', technicalMessage);\r
          alert(viewerText('viewer.export.routeFailed', { message: message }));\r
        });\r
      }\r
\r
      function runReachShareCard() {\r
        close(false);\r
        clearExportReceipt();\r
        var snapshot = Archify.focus && typeof Archify.focus.reachabilitySnapshot === 'function'\r
          ? Archify.focus.reachabilitySnapshot()\r
          : null;\r
        var blobPromise = snapshot\r
          ? renderShareCard({ reachSnapshot: snapshot })\r
          : Promise.reject(exportError('viewer.export.reachRequired'));\r
        return blobPromise.then(function (blob) {\r
          recordExportReceipt('share-card', blob, false, { width: SHARE_CARD_WIDTH, height: SHARE_CARD_HEIGHT }, 'reach', false, true);\r
          download(blob, diagramFilename() + '-' + snapshot.direction + '-reach-share-card.png');\r
          toast(viewerText('viewer.export.downloadedReach'));\r
          return blob;\r
        }).catch(function (err) {\r
          console.error(err);\r
          var technicalMessage = err && err.message ? err.message : 'share-card';\r
          var message = exportMessage(err);\r
          document.documentElement.setAttribute('data-last-export-error-format', 'share-card');\r
          document.documentElement.setAttribute('data-last-export-error', technicalMessage);\r
          alert(viewerText('viewer.export.reachFailed', { message: message }));\r
        });\r
      }\r
\r
      // A compact, machine-readable receipt for local QA and generated proof\r
      // galleries. It exposes no diagram contents, only the completed format,\r
      // byte count, and whether temporary viewer state was excluded.\r
      function recordExportReceipt(format, blob, canonical, dimensions, variant, routeStateClean, reachStateClean) {\r
        document.documentElement.setAttribute('data-last-export-format', format);\r
        document.documentElement.setAttribute('data-last-export-bytes', String(blob.size));\r
        document.documentElement.setAttribute('data-last-export-canonical', canonical ? 'true' : 'false');\r
        if (variant) {\r
          document.documentElement.setAttribute('data-last-export-variant', variant);\r
        } else {\r
          document.documentElement.removeAttribute('data-last-export-variant');\r
        }\r
        if (routeStateClean === true) {\r
          document.documentElement.setAttribute('data-last-export-route-state-clean', 'true');\r
        } else {\r
          document.documentElement.removeAttribute('data-last-export-route-state-clean');\r
        }\r
        if (reachStateClean === true) {\r
          document.documentElement.setAttribute('data-last-export-reach-state-clean', 'true');\r
        } else {\r
          document.documentElement.removeAttribute('data-last-export-reach-state-clean');\r
        }\r
        if (dimensions) {\r
          document.documentElement.setAttribute('data-last-export-width', String(dimensions.width));\r
          document.documentElement.setAttribute('data-last-export-height', String(dimensions.height));\r
        } else {\r
          document.documentElement.removeAttribute('data-last-export-width');\r
          document.documentElement.removeAttribute('data-last-export-height');\r
        }\r
      }\r
\r
      function clearExportReceipt() {\r
        document.documentElement.removeAttribute('data-last-export-format');\r
        document.documentElement.removeAttribute('data-last-export-bytes');\r
        document.documentElement.removeAttribute('data-last-export-canonical');\r
        document.documentElement.removeAttribute('data-last-export-width');\r
        document.documentElement.removeAttribute('data-last-export-height');\r
        document.documentElement.removeAttribute('data-last-export-variant');\r
        document.documentElement.removeAttribute('data-last-export-route-state-clean');\r
        document.documentElement.removeAttribute('data-last-export-reach-state-clean');\r
        document.documentElement.removeAttribute('data-last-export-error-format');\r
        document.documentElement.removeAttribute('data-last-export-error');\r
      }\r
\r
      function writePngToClipboard(blobPromise) {\r
        // WebKit requires ClipboardItem to be constructed synchronously inside\r
        // the user gesture. Chromium accepts the same pending Promise<Blob>;\r
        // engines that reject promise values fall back to an awaited Blob.\r
        try {\r
          return navigator.clipboard.write([new ClipboardItem({ 'image/png': blobPromise })]);\r
        } catch (_) {\r
          return blobPromise.then(function (blob) {\r
            return navigator.clipboard.write([new ClipboardItem({ 'image/png': blob })]);\r
          });\r
        }\r
      }\r
\r
      function runCopyShareCard() {\r
        close(true);\r
        clearExportReceipt();\r
        if (!canCopyImage()) {\r
          alert(viewerText('viewer.export.clipboardUnsupported.period'));\r
          return;\r
        }\r
        var blobPromise = rasterizeShareCard();\r
        return writePngToClipboard(blobPromise).then(function () {\r
          return blobPromise.then(function (blob) {\r
            recordExportReceipt('share-card', blob, true, { width: SHARE_CARD_WIDTH, height: SHARE_CARD_HEIGHT });\r
            toast(viewerText('viewer.export.copiedShare'));\r
          });\r
        }).catch(function (err) {\r
          console.error(err);\r
          var technicalMessage = err && err.message ? err.message : 'share-card';\r
          var message = exportMessage(err);\r
          document.documentElement.setAttribute('data-last-export-error-format', 'share-card');\r
          document.documentElement.setAttribute('data-last-export-error', technicalMessage);\r
          alert(viewerText('viewer.export.copyFailed', { message: message }));\r
        });\r
      }\r
\r
      function runCopy() {\r
        close(true);\r
        clearExportReceipt();\r
        if (!canCopyImage()) {\r
          alert(viewerText('viewer.export.clipboardUnsupported.short'));\r
          return;\r
        }\r
        var blobPromise = rasterize('png');\r
        return writePngToClipboard(blobPromise).then(function () {\r
          toast(viewerText('viewer.export.copiedPng'));\r
        }).catch(function (err) {\r
          console.error(err);\r
          alert(viewerText('viewer.export.copyFailed', {\r
            message: exportMessage(err)\r
          }));\r
        });\r
      }\r
\r
      menu.addEventListener('click', function (e) {\r
        var routeShareCardBtn = e.target.closest('button[data-action="route-share-card"]');\r
        if (routeShareCardBtn && !routeShareCardBtn.disabled && !routeShareCardBtn.hidden) { runRouteShareCard(); return; }\r
\r
        var reachShareCardBtn = e.target.closest('button[data-action="reach-share-card"]');\r
        if (reachShareCardBtn && !reachShareCardBtn.disabled && !reachShareCardBtn.hidden) { runReachShareCard(); return; }\r
\r
        var copyShareCardBtn = e.target.closest('button[data-action="copy-share-card"]');\r
        if (copyShareCardBtn && !copyShareCardBtn.disabled) { runCopyShareCard(); return; }\r
\r
        var copyBtn = e.target.closest('button[data-action="copy"]');\r
        if (copyBtn && !copyBtn.disabled) { runCopy(); return; }\r
\r
        var formatBtn = e.target.closest('button[data-format]');\r
        if (formatBtn && !formatBtn.disabled) { runExport(formatBtn.dataset.format); }\r
      });\r
\r
      Archify.motion = { canRecord: canRecordMotion, recordWebm: recordWebm };\r
      Archify.exportMenu = {\r
        open: open,\r
        close: close,\r
        isOpen: isOpen,\r
        run: runExport,\r
        shareCard: rasterizeShareCard,\r
        downloadRouteShareCard: runRouteShareCard,\r
        downloadReachShareCard: runReachShareCard,\r
        syncRouteShare: syncRouteShareItem,\r
        syncReachShare: syncReachShareItem,\r
        copyShareCard: runCopyShareCard\r
      };\r
\r
      // Auto-open on page load for demo/screenshot purposes: ?openExport=1\r
      // Wait for fonts (so the menu doesn't flash before typography lands)\r
      // and paint before opening. Fallback timeout for browsers without the\r
      // Font Loading API.\r
      try {\r
        if (new URLSearchParams(window.location.search).get('openExport') === '1') {\r
          var openWhenReady = function () {\r
            requestAnimationFrame(function () { requestAnimationFrame(open); });\r
          };\r
          if (document.fonts && document.fonts.ready) {\r
            document.fonts.ready.then(openWhenReady);\r
          } else {\r
            setTimeout(openWhenReady, 200);\r
          }\r
        }\r
      } catch (_) {}\r
    })();\r
\r
    /* ============================================================\r
       Motion Governor — one reader switch and one motion budget. Ambient\r
       trace yields to the strongest semantic owner; Still also parks bounded\r
       viewer signals without discarding their static meaning.\r
       ============================================================ */\r
    Archify.motionGovernor = (function () {\r
      var STORAGE_KEY = 'archify-motion';\r
      var html = document.documentElement;\r
      var svg = document.querySelector('.diagram-container svg');\r
      var btn = document.getElementById('btn-motion');\r
      var label = document.getElementById('motion-label');\r
      var motionQuery = window.matchMedia ? window.matchMedia('(prefers-reduced-motion: reduce)') : null;\r
      var capable = !!(svg && svg.getAttribute('data-animation') === 'trace');\r
      var readerPaused = false;\r
      var suspensions = Object.create(null);\r
      var explicitOwner = '';\r
      var owner = '';\r
      var ownerToken = 0;\r
      var ownerCleanup = null;\r
      var lastEffectivePaused = null;\r
      var ambientStarted = false;\r
      var ambientPending = new Set();\r
\r
      function detachAmbientBoundary() {\r
        if (!svg) return;\r
        svg.removeEventListener('animationend', onAmbientBoundary, true);\r
        svg.removeEventListener('animationcancel', onAmbientBoundary, true);\r
      }\r
      function settleAmbient(reason) {\r
        if (!capable) return false;\r
        ambientStarted = true;\r
        ambientPending.clear();\r
        detachAmbientBoundary();\r
        html.setAttribute('data-ambient-motion', 'settled');\r
        html.setAttribute('data-ambient-settle-reason', reason || 'complete');\r
        return true;\r
      }\r
      function onAmbientBoundary(event) {\r
        if (!ambientPending.has(event.target)) return;\r
        ambientPending.delete(event.target);\r
        if (!ambientPending.size) settleAmbient('complete');\r
      }\r
      function startAmbient() {\r
        if (ambientStarted || !capable) return false;\r
        ambientStarted = true;\r
        ambientPending = new Set(Array.prototype.slice.call(svg.querySelectorAll('[data-animate="edge"], [data-animate="node"]')));\r
        if (!ambientPending.size) return settleAmbient('empty');\r
        svg.addEventListener('animationend', onAmbientBoundary, true);\r
        svg.addEventListener('animationcancel', onAmbientBoundary, true);\r
        html.setAttribute('data-ambient-motion', 'running');\r
        html.removeAttribute('data-ambient-settle-reason');\r
        return true;\r
      }\r
\r
      function readStored() {\r
        try { return localStorage.getItem(STORAGE_KEY); } catch (_) { return null; }\r
      }\r
      function writeStored() {\r
        try {\r
          if (readerPaused) localStorage.setItem(STORAGE_KEY, 'still');\r
          else localStorage.removeItem(STORAGE_KEY);\r
        } catch (_) {}\r
      }\r
      function reducedMotion() {\r
        return !!(motionQuery && motionQuery.matches);\r
      }\r
      function hasSuspension() {\r
        return Object.keys(suspensions).length > 0;\r
      }\r
      function effectivePaused() {\r
        return readerPaused || reducedMotion() || hasSuspension();\r
      }\r
      function ownerLabel(value) {\r
        if (value === 'story') return viewerText('viewer.owner.story');\r
        if (value === 'chapter') return viewerText('viewer.owner.chapter');\r
        if (value === 'chapter-preview') return viewerText('viewer.owner.chapterPreview');\r
        if (value === 'handoff') return viewerText('viewer.owner.handoff');\r
        if (value === 'route') return viewerText('viewer.owner.route');\r
        if (value === 'lens') return viewerText('viewer.owner.lens');\r
        if (value === 'relationship') return viewerText('viewer.owner.relationship');\r
        if (value === 'intent') return viewerText('viewer.owner.intent');\r
        if (value === 'focus') return viewerText('viewer.owner.focus');\r
        if (value === 'legend') return viewerText('viewer.owner.legend');\r
        return viewerText('viewer.owner.reader');\r
      }\r
      function render() {\r
        if (!capable) return;\r
        var systemPaused = reducedMotion();\r
        var paused = effectivePaused();\r
        html.setAttribute('data-motion', paused ? 'still' : 'live');\r
        if (paused || owner || html.hasAttribute('data-embed') || html.hasAttribute('data-share-playback') || html.hasAttribute('data-document-hidden')) {\r
          settleAmbient('suppressed');\r
        } else if (!ambientStarted) {\r
          startAmbient();\r
        }\r
        btn.setAttribute('aria-pressed', paused ? 'false' : 'true');\r
        btn.disabled = systemPaused;\r
        label.textContent = viewerText(paused ? 'viewer.motion.still' : 'viewer.motion.live');\r
        if (paused && lastEffectivePaused !== true && Archify.guidedViews && Archify.guidedViews.isPlaying()) {\r
          Archify.guidedViews.pause();\r
        }\r
        if (paused && lastEffectivePaused !== true && Archify.guidedViews && Archify.guidedViews.settleHandoff) {\r
          Archify.guidedViews.settleHandoff(systemPaused ? 'reduced-motion' : (hasSuspension() ? 'hidden' : 'still'));\r
        }\r
        if (paused && lastEffectivePaused !== true && Archify.routeProbe && Archify.routeProbe.isJourneyPlaying && Archify.routeProbe.isJourneyPlaying()) {\r
          Archify.routeProbe.pauseJourney({ preserveElapsed: true, reason: systemPaused ? 'reduced-motion' : (hasSuspension() ? 'hidden' : 'still') });\r
        }\r
        lastEffectivePaused = paused;\r
        if (Archify.routeProbe && typeof Archify.routeProbe.syncMotion === 'function') Archify.routeProbe.syncMotion();\r
        if (systemPaused) {\r
          btn.setAttribute('aria-label', viewerText('viewer.motion.reduced'));\r
          btn.title = viewerText('viewer.motion.reduced');\r
        } else if (hasSuspension()) {\r
          btn.setAttribute('aria-label', viewerText('viewer.motion.hidden'));\r
          btn.title = viewerText('viewer.motion.hidden');\r
        } else if (paused) {\r
          btn.setAttribute('aria-label', viewerText('viewer.motion.resume'));\r
          btn.title = viewerText('viewer.motion.resume');\r
        } else if (owner) {\r
          btn.setAttribute('aria-label', viewerText('viewer.motion.yielding', { owner: ownerLabel(owner) }));\r
          btn.title = viewerText('viewer.motion.yielding.title', { owner: ownerLabel(owner) });\r
        } else {\r
          btn.setAttribute('aria-label', viewerText('viewer.motion.pause'));\r
          btn.title = viewerText('viewer.motion.pause');\r
        }\r
      }\r
      function setPaused(next, options) {\r
        options = options || {};\r
        readerPaused = !!next;\r
        if (options.persist !== false) writeStored();\r
        render();\r
        return readerPaused;\r
      }\r
      function publishOwner() {\r
        owner = explicitOwner || deriveOwner();\r
        if (owner) html.setAttribute('data-motion-owner', owner);\r
        else html.removeAttribute('data-motion-owner');\r
        render();\r
        return owner;\r
      }\r
      function deriveOwner() {\r
        if (!svg) return '';\r
        if (svg.hasAttribute('data-story-playing') || svg.hasAttribute('data-story-follow')) return 'story';\r
        if (svg.hasAttribute('data-story-active')) return 'chapter';\r
        if (svg.hasAttribute('data-route-picking') || svg.hasAttribute('data-route-active')) return 'route';\r
        if (svg.hasAttribute('data-lens-active')) return 'lens';\r
        if (svg.hasAttribute('data-relationship-preview-active')) return 'relationship';\r
        if (svg.hasAttribute('data-intent-trace-active')) return 'intent';\r
        if (svg.hasAttribute('data-focus-active')) return 'focus';\r
        if (svg.hasAttribute('data-legend-preview-active')) return 'legend';\r
        return '';\r
      }\r
      function clearClaim(preempted) {\r
        var cleanup = ownerCleanup;\r
        ownerCleanup = null;\r
        explicitOwner = '';\r
        if (preempted && cleanup) {\r
          try { cleanup(); } catch (_) {}\r
        }\r
      }\r
      function claim(next, cleanup) {\r
        if (!capable || !next) return 0;\r
        clearClaim(true);\r
        ownerToken += 1;\r
        explicitOwner = next;\r
        ownerCleanup = typeof cleanup === 'function' ? cleanup : null;\r
        publishOwner();\r
        return ownerToken;\r
      }\r
      function release(token) {\r
        if (!capable || token !== ownerToken || !explicitOwner) return false;\r
        clearClaim(false);\r
        ownerToken += 1;\r
        publishOwner();\r
        return true;\r
      }\r
      function suspend(reason) {\r
        var key = String(reason || 'runtime');\r
        var active = true;\r
        suspensions[key] = (suspensions[key] || 0) + 1;\r
        render();\r
        return function () {\r
          if (!active) return false;\r
          active = false;\r
          if (suspensions[key] > 1) suspensions[key] -= 1;\r
          else delete suspensions[key];\r
          render();\r
          return true;\r
        };\r
      }\r
      function syncVisibility() {\r
        if (document.hidden) {\r
          suspensions.visibility = true;\r
          html.setAttribute('data-document-hidden', 'true');\r
        } else {\r
          delete suspensions.visibility;\r
          html.removeAttribute('data-document-hidden');\r
        }\r
        render();\r
      }\r
\r
      if (!capable) {\r
        btn.hidden = true;\r
        html.removeAttribute('data-motion-capable');\r
        html.removeAttribute('data-motion');\r
        html.removeAttribute('data-motion-owner');\r
        html.removeAttribute('data-ambient-motion');\r
        html.removeAttribute('data-ambient-settle-reason');\r
        return {\r
          capable: false,\r
          pause: function () { return false; },\r
          resume: function () { return false; },\r
          toggle: function () { return false; },\r
          setMode: function () { return 'still'; },\r
          mode: function () { return 'still'; },\r
          claim: function () { return 0; },\r
          release: function () { return false; },\r
          suspend: function () { return function () { return false; }; },\r
          isPaused: function () { return true; },\r
          owner: function () { return ''; }\r
        };\r
      }\r
\r
      html.setAttribute('data-motion-capable', 'true');\r
      btn.hidden = false;\r
      readerPaused = readStored() === 'still';\r
      btn.addEventListener('click', function () { setPaused(!readerPaused); });\r
      if (motionQuery) {\r
        if (typeof motionQuery.addEventListener === 'function') motionQuery.addEventListener('change', render);\r
        else if (typeof motionQuery.addListener === 'function') motionQuery.addListener(render);\r
      }\r
      document.addEventListener('visibilitychange', syncVisibility);\r
      if (document.documentElement.getAttribute('data-embed') !== 'true' && typeof MutationObserver !== 'undefined' && typeof Node !== 'undefined' && svg instanceof Node) {\r
        var ownerObserver = new MutationObserver(function () { publishOwner(); });\r
        ownerObserver.observe(svg, {\r
          attributes: true,\r
          attributeFilter: [\r
            'data-story-playing', 'data-story-follow', 'data-story-active', 'data-route-picking', 'data-route-active',\r
            'data-lens-active', 'data-relationship-preview-active', 'data-intent-trace-active',\r
            'data-focus-active', 'data-legend-preview-active'\r
          ]\r
        });\r
      }\r
      syncVisibility();\r
      publishOwner();\r
      render();\r
\r
      return {\r
        capable: true,\r
        pause: function () { return setPaused(true); },\r
        resume: function () { return setPaused(false); },\r
        toggle: function () { return setPaused(!readerPaused); },\r
        setMode: function (next, options) {\r
          setPaused(next === 'still', options);\r
          return effectivePaused() ? 'still' : 'live';\r
        },\r
        mode: function () { return effectivePaused() ? 'still' : 'live'; },\r
        claim: claim,\r
        release: release,\r
        suspend: suspend,\r
        isPaused: effectivePaused,\r
        owner: function () { return owner; }\r
      };\r
    })();\r
\r
    /* Verified repository evidence is emitted only after the renderer checks\r
       the authored GitHub revision, source blobs, and optional line ranges\r
       against the explicit --repo-root. It remains outside the SVG so every\r
       canonical visual export stays free of repository paths. */\r
    Archify.sourceEvidence = (function () {\r
      var element = document.getElementById('archify-source-evidence-data');\r
      var payload = null;\r
      var svgNamespace = 'http://www.w3.org/2000/svg';\r
      if (element) {\r
        try {\r
          var parsed = JSON.parse(element.textContent || 'null');\r
          if (parsed && parsed.verified === true && parsed.repository && parsed.nodes) payload = parsed;\r
        } catch (_) {}\r
      }\r
      function installBeacons() {\r
        if (!payload) return 0;\r
        var svg = document.querySelector('.diagram-container svg');\r
        if (!svg) return 0;\r
        var installed = 0;\r
        Array.prototype.forEach.call(svg.querySelectorAll('[data-node-id]'), function (node) {\r
          var id = node.getAttribute('data-node-id');\r
          var sources = payload.nodes[id];\r
          if (!Array.isArray(sources) || !sources.length || node.querySelector('[data-source-evidence-beacon]')) return;\r
          var shape = node.querySelector('[data-animate="node"]') || node.querySelector('[class*="c-"]');\r
          var box;\r
          try { box = (shape || node).getBBox(); } catch (_) { return; }\r
          if (!box || !Number.isFinite(box.x) || !Number.isFinite(box.y) || !Number.isFinite(box.width) || box.width < 36) return;\r
\r
          var count = sources.length;\r
          var label = viewerCount('viewer.passport.beacon', count);\r
          var beacon = document.createElementNS(svgNamespace, 'g');\r
          beacon.classList.add('source-evidence-beacon');\r
          beacon.setAttribute('data-source-evidence-beacon', '');\r
          beacon.setAttribute('aria-hidden', 'true');\r
          var brandOffset = node.hasAttribute('data-node-brand') ? 24 : 0;\r
          beacon.setAttribute('transform', 'translate(' + (box.x + box.width - 35 - brandOffset) + ' ' + (box.y + 5) + ')');\r
          var title = document.createElementNS(svgNamespace, 'title');\r
          title.textContent = label;\r
          var plate = document.createElementNS(svgNamespace, 'rect');\r
          plate.setAttribute('width', '30');\r
          plate.setAttribute('height', '12');\r
          plate.setAttribute('rx', '6');\r
          var text = document.createElementNS(svgNamespace, 'text');\r
          text.setAttribute('x', '15');\r
          text.setAttribute('y', '8.25');\r
          text.textContent = viewerText('viewer.passport.sourceMarker') + ' ' + count;\r
          beacon.appendChild(title);\r
          beacon.appendChild(plate);\r
          beacon.appendChild(text);\r
          node.appendChild(beacon);\r
\r
          var originalLabel = node.getAttribute('aria-label') || '';\r
          node.setAttribute('data-source-evidence-count', String(count));\r
          node.setAttribute('data-source-evidence-original-label', originalLabel);\r
          node.setAttribute('aria-label', (originalLabel ? originalLabel + ', ' : '') + viewerCount('viewer.passport.sourceCount', count));\r
          installed += 1;\r
        });\r
        return installed;\r
      }\r
      return {\r
        available: function () { return Boolean(payload); },\r
        repository: function () { return payload ? payload.repository : null; },\r
        node: function (id) {\r
          var sources = payload && payload.nodes ? payload.nodes[id] : null;\r
          return Array.isArray(sources) ? sources.slice() : [];\r
        },\r
        installBeacons: installBeacons\r
      };\r
    })();\r
    Archify.sourceEvidence.installBeacons();\r
\r
    /* ============================================================\r
       Explore — stable-ID neighborhood focus + dependency-free pan/zoom.\r
       Renderer IDs become deep-linkable semantic hooks without turning the\r
       standalone artifact into a canvas editor.\r
       ============================================================ */\r
    Archify.focus = (function () {\r
      var html = document.documentElement;\r
      var container = document.querySelector('.diagram-container');\r
      var svg = container.querySelector('svg');\r
      var chip = document.getElementById('focus-chip');\r
      var label = document.getElementById('focus-label');\r
      var detail = document.getElementById('focus-detail');\r
      var kind = document.getElementById('focus-kind');\r
      var context = document.getElementById('focus-context');\r
      var tag = document.getElementById('focus-tag');\r
      var semanticId = document.getElementById('focus-id');\r
      var evidence = document.getElementById('focus-evidence');\r
      var repositoryLink = document.getElementById('focus-repository');\r
      var evidenceLinks = document.getElementById('focus-evidence-links');\r
      var summary = document.getElementById('focus-summary');\r
      var reachSection = document.getElementById('focus-reach');\r
      var reachStatus = document.getElementById('focus-reach-status');\r
      var upstreamBtn = document.getElementById('btn-reach-upstream');\r
      var downstreamBtn = document.getElementById('btn-reach-downstream');\r
      var upstreamCount = document.getElementById('focus-reach-upstream-count');\r
      var downstreamCount = document.getElementById('focus-reach-downstream-count');\r
      var relationshipList = document.getElementById('relationship-lens-list');\r
      var copyBtn = document.getElementById('btn-focus-copy');\r
      var relationsBtn = document.getElementById('btn-focus-relations');\r
      var clearBtn = document.getElementById('btn-focus-clear');\r
      var activeIds = [];\r
      var hoveredRelationship = null;\r
      var focusedRelationship = null;\r
      var pinnedRelationship = null;\r
      var pinnedRelationshipKey = null;\r
      var activeRelationshipPreview = null;\r
      var relationshipHitOverlay = null;\r
      var relationshipHitTargets = [];\r
      var directPreviewTimer = null;\r
      var reachabilityMode = null;\r
      var activeReachability = null;\r
      var svgNamespace = 'http://www.w3.org/2000/svg';\r
      var reducedMotionQuery = window.matchMedia ? window.matchMedia('(prefers-reduced-motion: reduce)') : null;\r
      var finePointerQuery = window.matchMedia ? window.matchMedia('(hover: hover) and (pointer: fine)') : null;\r
\r
      function nodes() {\r
        return Array.prototype.slice.call(svg.querySelectorAll('[data-node-id]'));\r
      }\r
      function edges() {\r
        return Array.prototype.slice.call(svg.querySelectorAll('[data-edge-from][data-edge-to]'));\r
      }\r
      function nodeLabel(node, fallback) {\r
        return node.getAttribute('data-node-label') || (node.getAttribute('aria-label') || fallback).replace(/^Focus\\s+/, '');\r
      }\r
      function reachabilityRelationships() {\r
        var seen = Object.create(null);\r
        var relationships = [];\r
        edges().filter(function (edge) { return edge.getAttribute('data-relation-class') === 'direct_evolution'; }).forEach(function (edge) {\r
          var from = edge.getAttribute('data-edge-from');\r
          var to = edge.getAttribute('data-edge-to');\r
          var key = edge.getAttribute('data-edge-key') || (from + '\\u0000' + to + '\\u0000' + (edge.getAttribute('data-edge-label') || ''));\r
          if (!from || !to || seen[key]) return;\r
          seen[key] = true;\r
          relationships.push({ key: key, from: from, to: to });\r
        });\r
        return relationships;\r
      }\r
      function computeReachability(originId, direction, relationships) {\r
        if (typeof originId !== 'string' || !originId ||\r
            (direction !== 'upstream' && direction !== 'downstream') ||\r
            !Array.isArray(relationships)) return null;\r
        var records = [];\r
        var seenKeys = Object.create(null);\r
        relationships.forEach(function (relationship, index) {\r
          if (!relationship || typeof relationship.from !== 'string' || !relationship.from ||\r
              typeof relationship.to !== 'string' || !relationship.to) return;\r
          var key = typeof relationship.key === 'string' && relationship.key\r
            ? relationship.key : String(index);\r
          if (seenKeys[key]) return;\r
          seenKeys[key] = true;\r
          records.push({ key: key, from: relationship.from, to: relationship.to });\r
        });\r
\r
        var depths = Object.create(null);\r
        var order = [];\r
        var queue = [originId];\r
        depths[originId] = 0;\r
        for (var cursor = 0; cursor < queue.length; cursor += 1) {\r
          var current = queue[cursor];\r
          records.forEach(function (relationship) {\r
            var next = null;\r
            if (direction === 'downstream' && relationship.from === current) next = relationship.to;\r
            else if (direction === 'upstream' && relationship.to === current) next = relationship.from;\r
            if (next == null || Object.prototype.hasOwnProperty.call(depths, next)) return;\r
            depths[next] = depths[current] + 1;\r
            queue.push(next);\r
          });\r
        }\r
        queue.forEach(function (id) { order.push(id); });\r
\r
        var edgeKeys = [];\r
        records.forEach(function (relationship) {\r
          if (Object.prototype.hasOwnProperty.call(depths, relationship.from) &&\r
              Object.prototype.hasOwnProperty.call(depths, relationship.to)) edgeKeys.push(relationship.key);\r
        });\r
        var maxDepth = order.reduce(function (maximum, id) {\r
          return Math.max(maximum, depths[id]);\r
        }, 0);\r
        return {\r
          direction: direction,\r
          originId: originId,\r
          nodeIds: order,\r
          edgeKeys: edgeKeys,\r
          depths: depths,\r
          maxDepth: maxDepth\r
        };\r
      }\r
      function reachabilityFor(id, direction) {\r
        return computeReachability(id, direction, reachabilityRelationships());\r
      }\r
      function resetReachabilityButtons() {\r
        upstreamBtn.setAttribute('aria-pressed', 'false');\r
        downstreamBtn.setAttribute('aria-pressed', 'false');\r
      }\r
      function clearReachability(options) {\r
        options = options || {};\r
        reachabilityMode = null;\r
        activeReachability = null;\r
        svg.removeAttribute('data-reach-active');\r
        chip.removeAttribute('data-reach-mode');\r
        nodes().forEach(function (node) {\r
          node.removeAttribute('data-reach-match');\r
          node.removeAttribute('data-reach-origin');\r
          node.removeAttribute('data-reach-depth');\r
        });\r
        edges().forEach(function (edge) {\r
          edge.removeAttribute('data-reach-match');\r
          edge.removeAttribute('data-reach-depth');\r
        });\r
        resetReachabilityButtons();\r
        reachStatus.textContent = '';\r
        reachStatus.hidden = true;\r
        if (Archify.exportMenu && typeof Archify.exportMenu.syncReachShare === 'function') {\r
          Archify.exportMenu.syncReachShare();\r
        }\r
        if (options.updateUrl === true && activeIds.length === 1) {\r
          try {\r
            history.replaceState(null, '', location.pathname + location.search + '#focus=' + encodeURIComponent(activeIds[0]));\r
          } catch (_) {}\r
        }\r
      }\r
      function renderReachabilityControls(id) {\r
        var upstream = reachabilityFor(id, 'upstream');\r
        var downstream = reachabilityFor(id, 'downstream');\r
        var upstreamReach = upstream ? Math.max(0, upstream.nodeIds.length - 1) : 0;\r
        var downstreamReach = downstream ? Math.max(0, downstream.nodeIds.length - 1) : 0;\r
        upstreamCount.textContent = String(upstreamReach);\r
        downstreamCount.textContent = String(downstreamReach);\r
        upstreamBtn.disabled = upstreamReach === 0;\r
        downstreamBtn.disabled = downstreamReach === 0;\r
        upstreamBtn.setAttribute('aria-label', upstreamReach\r
          ? viewerCount('viewer.passport.reach.upstream', upstreamReach)\r
          : viewerText('viewer.passport.reach.noUpstream'));\r
        downstreamBtn.setAttribute('aria-label', downstreamReach\r
          ? viewerCount('viewer.passport.reach.downstream', downstreamReach)\r
          : viewerText('viewer.passport.reach.noDownstream'));\r
        reachSection.hidden = false;\r
      }\r
      function applyReachability(direction, options) {\r
        options = options || {};\r
        if (activeIds.length !== 1 || (direction !== 'upstream' && direction !== 'downstream')) return false;\r
        if (reachabilityMode === direction && options.toggle !== false) {\r
          clearReachability({ updateUrl: options.updateUrl !== false });\r
          return true;\r
        }\r
        var result = reachabilityFor(activeIds[0], direction);\r
        if (!result || result.nodeIds.length <= 1) return false;\r
        if (Archify.guidedViews && typeof Archify.guidedViews.showAll === 'function') {\r
          Archify.guidedViews.showAll({ clearFocus: false, updateUrl: false, resetView: false });\r
        }\r
        clearRelationshipPreview({ clearPin: true });\r
        clearReachability({ updateUrl: false });\r
        reachabilityMode = direction;\r
        activeReachability = result;\r
        var edgeKeySet = Object.create(null);\r
        result.edgeKeys.forEach(function (key) { edgeKeySet[key] = true; });\r
        svg.setAttribute('data-reach-active', direction);\r
        chip.setAttribute('data-reach-mode', direction);\r
        nodes().forEach(function (node) {\r
          var id = node.getAttribute('data-node-id');\r
          if (!Object.prototype.hasOwnProperty.call(result.depths, id)) return;\r
          node.setAttribute('data-reach-match', '');\r
          node.setAttribute('data-reach-depth', String(result.depths[id]));\r
          if (id === result.originId) node.setAttribute('data-reach-origin', '');\r
        });\r
        edges().forEach(function (edge) {\r
          var key = edge.getAttribute('data-edge-key') || (\r
            edge.getAttribute('data-edge-from') + '\\u0000' +\r
            edge.getAttribute('data-edge-to') + '\\u0000' +\r
            (edge.getAttribute('data-edge-label') || '')\r
          );\r
          if (!edgeKeySet[key]) return;\r
          edge.setAttribute('data-reach-match', '');\r
          var fromDepth = result.depths[edge.getAttribute('data-edge-from')];\r
          var toDepth = result.depths[edge.getAttribute('data-edge-to')];\r
          edge.setAttribute('data-reach-depth', String(Math.max(fromDepth || 0, toDepth || 0)));\r
        });\r
        resetReachabilityButtons();\r
        var activeButton = direction === 'upstream' ? upstreamBtn : downstreamBtn;\r
        activeButton.setAttribute('aria-pressed', 'true');\r
        var reachableCount = result.nodeIds.length - 1;\r
        var directionLabel = viewerText(direction === 'upstream'\r
          ? 'viewer.passport.upstream'\r
          : 'viewer.passport.downstream');\r
        reachStatus.textContent = viewerText('viewer.passport.reach.status', {\r
          direction: directionLabel,\r
          nodes: reachableCount,\r
          links: result.edgeKeys.length,\r
          hops: result.maxDepth\r
        });\r
        reachStatus.hidden = false;\r
        if (Archify.exportMenu && typeof Archify.exportMenu.syncReachShare === 'function') {\r
          Archify.exportMenu.syncReachShare();\r
        }\r
        if (options.updateUrl !== false) {\r
          try {\r
            history.replaceState(null, '', location.pathname + location.search + '#focus=' +\r
              encodeURIComponent(activeIds[0]) + '&reach=' + direction);\r
          } catch (_) {}\r
        }\r
        if (options.reveal !== false && Archify.view && typeof Archify.view.reveal === 'function') {\r
          Archify.view.reveal(result.nodeIds, { includeNeighbors: false, reason: 'reachability' });\r
        }\r
        requestLensPlacement();\r
        return true;\r
      }\r
      function reachabilitySnapshot() {\r
        if (!activeReachability || activeIds.length !== 1 ||\r
            (reachabilityMode !== 'upstream' && reachabilityMode !== 'downstream') ||\r
            activeReachability.direction !== reachabilityMode ||\r
            activeReachability.originId !== activeIds[0] ||\r
            svg.getAttribute('data-reach-active') !== reachabilityMode) return null;\r
\r
        var originId = activeReachability.originId;\r
        var nodeIds = activeReachability.nodeIds.slice();\r
        var edgeKeys = activeReachability.edgeKeys.slice();\r
        if (nodeIds.length < 2 || nodeIds[0] !== originId || !edgeKeys.length ||\r
            !activeReachability.depths || !Number.isInteger(activeReachability.maxDepth) ||\r
            activeReachability.maxDepth < 1) return null;\r
\r
        var allNodes = nodes();\r
        var allEdges = edges();\r
        var seenNodeIds = Object.create(null);\r
        var seenEdgeKeys = Object.create(null);\r
        var nodeIdSet = Object.create(null);\r
        var depths = Object.create(null);\r
        var originNode = null;\r
        var measuredMaxDepth = 0;\r
\r
        if (nodeIds.some(function (id) {\r
          var depth = activeReachability.depths[id];\r
          var matches = allNodes.filter(function (node) {\r
            return node.getAttribute('data-node-id') === id;\r
          });\r
          if (typeof id !== 'string' || !id || seenNodeIds[id] || matches.length !== 1 ||\r
              !matches[0].hasAttribute('data-reach-match') ||\r
              !Number.isInteger(depth) || depth < 0 || depth > activeReachability.maxDepth ||\r
              (id === originId\r
                ? (!matches[0].hasAttribute('data-reach-origin') || depth !== 0)\r
                : depth < 1)) return true;\r
          seenNodeIds[id] = true;\r
          nodeIdSet[id] = true;\r
          depths[id] = depth;\r
          measuredMaxDepth = Math.max(measuredMaxDepth, depth);\r
          if (id === originId) originNode = matches[0];\r
          return false;\r
        }) || !originNode || measuredMaxDepth !== activeReachability.maxDepth ||\r
            allNodes.filter(function (node) { return node.hasAttribute('data-reach-match'); }).length !== nodeIds.length) return null;\r
\r
        var edgeRecords = [];\r
        if (edgeKeys.some(function (key) {\r
          if (typeof key !== 'string' || !key || seenEdgeKeys[key]) return true;\r
          var fragments = allEdges.filter(function (edge) {\r
            return edge.getAttribute('data-edge-key') === key;\r
          });\r
          var drawableFragments = fragments.filter(hasDrawableGeometry);\r
          if (!fragments.length || drawableFragments.length !== 1 ||\r
              !fragments.every(function (fragment) { return fragment.hasAttribute('data-reach-match'); })) return true;\r
          var first = fragments[0];\r
          var from = first.getAttribute('data-edge-from');\r
          var to = first.getAttribute('data-edge-to');\r
          var id = first.getAttribute('data-edge-id') || '';\r
          var labelValue = first.getAttribute('data-edge-label') || '';\r
          if (!nodeIdSet[from] || !nodeIdSet[to] || !fragments.every(function (fragment) {\r
            return fragment.getAttribute('data-edge-from') === from &&\r
              fragment.getAttribute('data-edge-to') === to &&\r
              (fragment.getAttribute('data-edge-id') || '') === id;\r
          })) return true;\r
          seenEdgeKeys[key] = true;\r
          edgeRecords.push({\r
            key: key,\r
            id: id,\r
            from: from,\r
            to: to,\r
            label: labelValue,\r
            depth: Math.max(depths[from], depths[to])\r
          });\r
          return false;\r
        })) return null;\r
\r
        var liveEdgeKeys = Object.create(null);\r
        if (allEdges.some(function (edge) {\r
          if (!edge.hasAttribute('data-reach-match')) return false;\r
          var key = edge.getAttribute('data-edge-key');\r
          if (!key || !seenEdgeKeys[key]) return true;\r
          liveEdgeKeys[key] = true;\r
          return false;\r
        }) || Object.keys(liveEdgeKeys).length !== edgeKeys.length) return null;\r
\r
        return {\r
          direction: reachabilityMode,\r
          origin: { id: originId, label: nodeLabel(originNode, originId) },\r
          nodeIds: nodeIds,\r
          depths: depths,\r
          maxDepth: activeReachability.maxDepth,\r
          edges: edgeRecords\r
        };\r
      }\r
      function setPassportValue(element, value) {\r
        var normalized = value == null ? '' : String(value).trim();\r
        element.textContent = normalized;\r
        element.hidden = !normalized;\r
      }\r
      function renderSourceEvidence(id) {\r
        evidenceLinks.textContent = '';\r
        repositoryLink.removeAttribute('href');\r
        repositoryLink.removeAttribute('aria-label');\r
        repositoryLink.textContent = '';\r
        var sources = Archify.sourceEvidence.node(id);\r
        var repository = Archify.sourceEvidence.repository();\r
        if (!repository || !sources.length) {\r
          evidence.hidden = true;\r
          return;\r
        }\r
        repositoryLink.textContent = repository.label + ' @ ' + repository.shortRevision;\r
        if (repository.href) {\r
          repositoryLink.href = repository.href;\r
          repositoryLink.setAttribute('aria-label', viewerText('viewer.passport.repository.open', { revision: repository.revision }));\r
        }\r
        evidence.title = viewerText('viewer.passport.verificationScope');\r
        sources.forEach(function (source) {\r
          var link = document.createElement(source.href ? 'a' : 'div');\r
          link.className = 'semantic-passport-source';\r
          if (source.href) {\r
            link.href = source.href;\r
            link.target = '_blank';\r
            link.rel = 'noopener noreferrer';\r
            link.referrerPolicy = 'no-referrer';\r
            link.setAttribute('aria-label', viewerText('viewer.passport.source.open', { path: source.path, revision: repository.shortRevision }));\r
          }\r
          var name = document.createElement('strong');\r
          name.textContent = source.label || source.path.split('/').pop() || source.path;\r
          var location = document.createElement('code');\r
          location.textContent = source.line\r
            ? 'L' + source.line + (source.endLine && source.endLine !== source.line ? '–' + source.endLine : '') + (source.href ? ' ↗' : '')\r
            : source.href ? viewerText('viewer.passport.source.openLink') : '';\r
          var sourcePath = document.createElement('small');\r
          sourcePath.textContent = source.path;\r
          link.appendChild(name);\r
          link.appendChild(location);\r
          link.appendChild(sourcePath);\r
          evidenceLinks.appendChild(link);\r
        });\r
        evidence.hidden = false;\r
      }\r
      function renderPassport(id, node) {\r
        setPassportValue(detail, node.getAttribute('data-node-sublabel'));\r
        setPassportValue(kind, viewerKindLabel(node.getAttribute('data-node-kind') || 'node'));\r
        setPassportValue(context, node.getAttribute('data-node-context'));\r
        setPassportValue(tag, node.getAttribute('data-node-tag'));\r
        setPassportValue(document.getElementById('focus-brand'), node.getAttribute('data-node-brand'));\r
        semanticId.textContent = id;\r
        semanticId.hidden = false;\r
        renderSourceEvidence(id);\r
      }\r
      function relationshipsFor(id, byId) {\r
        var seen = {};\r
        var relationships = [];\r
        edges().forEach(function (edge) {\r
          var from = edge.getAttribute('data-edge-from');\r
          var to = edge.getAttribute('data-edge-to');\r
          if (from !== id && to !== id) return;\r
          var edgeLabel = edge.getAttribute('data-edge-label') || '';\r
          var edgeKey = edge.getAttribute('data-edge-key') || (from + '\\u0000' + to + '\\u0000' + edgeLabel);\r
          var edgeId = edge.getAttribute('data-edge-id') || '';\r
          if (seen[edgeKey]) return;\r
          seen[edgeKey] = true;\r
          var direction = from === id && to === id ? 'loop' : (from === id ? 'out' : 'in');\r
          var neighborId = direction === 'in' ? from : to;\r
          var neighbor = byId[neighborId];\r
          relationships.push({\r
            key: edgeKey,\r
            id: edgeId,\r
            from: from,\r
            to: to,\r
            direction: direction,\r
            neighborId: neighborId,\r
            neighborLabel: neighbor ? nodeLabel(neighbor, neighborId) : neighborId,\r
            label: edgeLabel || viewerText(direction === 'loop'\r
              ? 'viewer.passport.relationship.loopsBack'\r
              : direction === 'out'\r
                ? 'viewer.passport.relationship.connectsTo'\r
                : 'viewer.passport.relationship.connectsFrom')\r
          });\r
        });\r
        return relationships;\r
      }\r
      function relationshipEdgeShapes(edge) {\r
        if (!edge) return [];\r
        if (/^(path|line|polyline)$/i.test(edge.tagName || '')) return [edge];\r
        return Array.prototype.slice.call(edge.querySelectorAll('path, line, polyline'));\r
      }\r
      function relationshipHitRecords() {\r
        var recordsByKey = {};\r
        var recordsById = Object.create(null);\r
        var byId = Object.create(null);\r
        nodes().forEach(function (node) { byId[node.getAttribute('data-node-id')] = node; });\r
        var records = [];\r
        edges().forEach(function (edge) {\r
          var shapes = relationshipEdgeShapes(edge);\r
          if (!shapes.length) return;\r
          var from = edge.getAttribute('data-edge-from');\r
          var to = edge.getAttribute('data-edge-to');\r
          var labelValue = edge.getAttribute('data-edge-label') || '';\r
          var edgeId = edge.getAttribute('data-edge-id') || '';\r
          var key = edge.getAttribute('data-edge-key') || (from + '\\u0000' + to + '\\u0000' + labelValue);\r
          var existing = recordsByKey[key];\r
          if (existing) {\r
            if (existing.from !== from || existing.to !== to || existing.labelValue !== labelValue || existing.id !== edgeId) {\r
              existing.invalid = true;\r
              return;\r
            }\r
            shapes.forEach(function (shape) {\r
              if (existing.shapes.indexOf(shape) === -1) existing.shapes.push(shape);\r
            });\r
            return;\r
          }\r
          var record = {\r
            key: key,\r
            id: edgeId,\r
            from: from,\r
            to: to,\r
            fromLabel: byId[from] ? nodeLabel(byId[from], from) : from,\r
            toLabel: byId[to] ? nodeLabel(byId[to], to) : to,\r
            labelValue: labelValue,\r
            label: labelValue || viewerText(from === to\r
              ? 'viewer.passport.relationship.loopsBack'\r
              : 'viewer.passport.relationship.connectsTo'),\r
            edge: edge,\r
            shapes: shapes,\r
            invalid: false\r
          };\r
          recordsByKey[key] = record;\r
          if (edgeId) {\r
            if (recordsById[edgeId]) {\r
              recordsById[edgeId].invalid = true;\r
              record.invalid = true;\r
            } else {\r
              recordsById[edgeId] = record;\r
            }\r
          }\r
          records.push(record);\r
        });\r
        return records.filter(function (record) { return !record.invalid && record.from && record.to; });\r
      }\r
      function relationshipRecordForKey(key) {\r
        return relationshipHitRecords().find(function (record) { return record.key === key; }) || null;\r
      }\r
      function pinnedRelationshipRecord() {\r
        return pinnedRelationshipKey ? relationshipRecordForKey(pinnedRelationshipKey) : null;\r
      }\r
      function renderRelationshipCopyAction() {\r
        var record = pinnedRelationshipRecord();\r
        if (record && record.id) {\r
          copyBtn.textContent = viewerText('viewer.passport.copyRelation');\r
          copyBtn.setAttribute('aria-label', viewerText('viewer.passport.copyPinned'));\r
        } else if (pinnedRelationshipKey) {\r
          copyBtn.textContent = viewerText('viewer.passport.copyNode');\r
          copyBtn.setAttribute('aria-label', viewerText('viewer.passport.copySource'));\r
        } else {\r
          copyBtn.textContent = viewerText('viewer.passport.copy');\r
          copyBtn.setAttribute('aria-label', viewerText('viewer.passport.copy.focus'));\r
        }\r
      }\r
      function relationshipHitGeometry(shape, className) {\r
        var clone = shape.cloneNode(false);\r
        clone.removeAttribute('id');\r
        clone.removeAttribute('class');\r
        clone.removeAttribute('style');\r
        clone.removeAttribute('filter');\r
        clone.removeAttribute('marker-start');\r
        clone.removeAttribute('marker-mid');\r
        clone.removeAttribute('marker-end');\r
        clone.removeAttribute('role');\r
        clone.removeAttribute('tabindex');\r
        clone.removeAttribute('aria-label');\r
        clone.removeAttribute('aria-labelledby');\r
        clone.removeAttribute('aria-hidden');\r
        clone.removeAttribute('data-animate');\r
        clone.removeAttribute('data-edge-from');\r
        clone.removeAttribute('data-edge-to');\r
        clone.removeAttribute('data-edge-key');\r
        clone.removeAttribute('data-edge-id');\r
        clone.removeAttribute('data-edge-label');\r
        clone.setAttribute('class', className || 'relationship-hit-rail');\r
        return clone;\r
      }\r
      function removeRelationshipPulse() {\r
        Array.prototype.forEach.call(svg.querySelectorAll('[data-relationship-pulse-overlay]'), function (element) {\r
          element.remove();\r
        });\r
      }\r
      function relationshipPulseGeometry(shape) {\r
        var clone = shape.cloneNode(false);\r
        clone.removeAttribute('id');\r
        clone.removeAttribute('class');\r
        clone.removeAttribute('style');\r
        clone.removeAttribute('transform');\r
        clone.removeAttribute('filter');\r
        clone.removeAttribute('marker-start');\r
        clone.removeAttribute('marker-mid');\r
        clone.removeAttribute('marker-end');\r
        clone.removeAttribute('role');\r
        clone.removeAttribute('tabindex');\r
        clone.removeAttribute('aria-label');\r
        clone.removeAttribute('aria-hidden');\r
        clone.removeAttribute('data-animate');\r
        clone.removeAttribute('data-edge-from');\r
        clone.removeAttribute('data-edge-to');\r
        clone.removeAttribute('data-edge-key');\r
        clone.removeAttribute('data-edge-id');\r
        clone.removeAttribute('data-edge-label');\r
        clone.removeAttribute('data-focus-match');\r
        clone.removeAttribute('data-relationship-preview');\r
        clone.setAttribute('class', 'relationship-flow-pulse');\r
        clone.setAttribute('pathLength', '1');\r
        return clone;\r
      }\r
      function relationshipTokenKind(edge) {\r
        var shapes = relationshipEdgeShapes(edge);\r
        var classEvidence = [edge.getAttribute('class') || ''].concat(shapes.map(function (shape) {\r
          return shape.getAttribute('class') || '';\r
        })).join(' ');\r
        var from = edge.getAttribute('data-edge-from') || '';\r
        var to = edge.getAttribute('data-edge-to') || '';\r
        var source = nodes().find(function (node) { return node.getAttribute('data-node-id') === from; });\r
        var target = nodes().find(function (node) { return node.getAttribute('data-node-id') === to; });\r
        var sourceKind = source ? source.getAttribute('data-node-kind') || 'neutral' : 'neutral';\r
        var targetKind = target ? target.getAttribute('data-node-kind') || 'neutral' : 'neutral';\r
        if (/\\ba-security\\b/.test(classEvidence) || sourceKind === 'security' || targetKind === 'security' || targetKind === 'failure') return 'security';\r
        if (/\\ba-dashed\\b/.test(classEvidence) || sourceKind === 'messagebus' || targetKind === 'messagebus') return 'event';\r
        if (sourceKind === 'database' || targetKind === 'database') return 'data';\r
        if (targetKind === 'waiting' || targetKind === 'success') return 'state';\r
        return 'call';\r
      }\r
      function relationshipTokenPath(shape) {\r
        if (!shape) return '';\r
        var tagName = String(shape.tagName || '').toLowerCase();\r
        if (tagName === 'path') return shape.getAttribute('d') || '';\r
        if (tagName === 'line') {\r
          return 'M ' + shape.getAttribute('x1') + ' ' + shape.getAttribute('y1') +\r
            ' L ' + shape.getAttribute('x2') + ' ' + shape.getAttribute('y2');\r
        }\r
        if (tagName === 'polyline' && shape.points && shape.points.numberOfItems > 1) {\r
          var commands = [];\r
          for (var i = 0; i < shape.points.numberOfItems; i += 1) {\r
            var point = shape.points.getItem(i);\r
            commands.push((i === 0 ? 'M ' : 'L ') + point.x + ' ' + point.y);\r
          }\r
          return commands.join(' ');\r
        }\r
        return '';\r
      }\r
      function relationshipTokenPart(tagName, className, attrs) {\r
        var part = document.createElementNS(svgNamespace, tagName);\r
        part.setAttribute('class', className);\r
        Object.keys(attrs || {}).forEach(function (name) { part.setAttribute(name, attrs[name]); });\r
        return part;\r
      }\r
      function relationshipTokenGeometry(shape, kind, key, options) {\r
        options = options || {};\r
        var pathData = relationshipTokenPath(shape);\r
        if (!pathData) return null;\r
        var token = document.createElementNS(svgNamespace, 'g');\r
        token.setAttribute('class', 'semantic-flow-token ' + (options.className || 'relationship-flow-token'));\r
        token.setAttribute('data-token-kind', kind);\r
        token.setAttribute('data-token-edge-key', key);\r
        token.setAttribute('aria-hidden', 'true');\r
        token.appendChild(relationshipTokenPart('circle', 'semantic-flow-token-halo', { cx: '0', cy: '0', r: '7' }));\r
        if (kind === 'data') {\r
          token.appendChild(relationshipTokenPart('rect', 'relationship-flow-token-shape', { x: '-5', y: '-4', width: '10', height: '8', rx: '2' }));\r
          token.appendChild(relationshipTokenPart('path', 'relationship-flow-token-ink', { d: 'M -2.8 -1.2 h 5.6 M -2.8 1.4 h 3.8' }));\r
        } else if (kind === 'event') {\r
          token.appendChild(relationshipTokenPart('rect', 'relationship-flow-token-shape', { x: '-7', y: '-3', width: '4', height: '6', rx: '1' }));\r
          token.appendChild(relationshipTokenPart('rect', 'relationship-flow-token-shape', { x: '-2', y: '-3', width: '4', height: '6', rx: '1' }));\r
          token.appendChild(relationshipTokenPart('rect', 'relationship-flow-token-shape', { x: '3', y: '-3', width: '4', height: '6', rx: '1' }));\r
        } else if (kind === 'security') {\r
          token.appendChild(relationshipTokenPart('path', 'relationship-flow-token-shape', { d: 'M 0 -5 L 4 -3.4 V 0 c 0 3 -1.6 4.5 -4 5.5 C -2.4 4.5 -4 3 -4 0 v -3.4 Z' }));\r
          token.appendChild(relationshipTokenPart('path', 'relationship-flow-token-ink', { d: 'm -2 .2 1.4 1.4 L 2 -1.4' }));\r
        } else if (kind === 'state') {\r
          token.appendChild(relationshipTokenPart('circle', 'relationship-flow-token-shape', { cx: '0', cy: '0', r: '5' }));\r
          token.appendChild(relationshipTokenPart('circle', 'relationship-flow-token-dot', { cx: '0', cy: '0', r: '1.35' }));\r
        } else {\r
          token.appendChild(relationshipTokenPart('path', 'relationship-flow-token-ink', { d: 'M -5 -3 L -1 0 L -5 3 M 0 -3 L 4 0 L 0 3' }));\r
        }\r
        var motion = document.createElementNS(svgNamespace, 'animateMotion');\r
        motion.setAttribute('path', pathData);\r
        motion.setAttribute('dur', options.duration || '1.2s');\r
        motion.setAttribute('begin', '0s');\r
        motion.setAttribute('fill', 'freeze');\r
        motion.setAttribute('rotate', 'auto');\r
        motion.setAttribute('calcMode', 'spline');\r
        motion.setAttribute('keyTimes', '0;1');\r
        motion.setAttribute('keySplines', '.2 0 .2 1');\r
        token.appendChild(motion);\r
        return token;\r
      }\r
      function createSemanticFlowToken(edge, shape, options) {\r
        if (!edge || !shape) return null;\r
        var key = edge.getAttribute('data-edge-key') || (\r
          edge.getAttribute('data-edge-from') + '\\u0000' +\r
          edge.getAttribute('data-edge-to') + '\\u0000' +\r
          (edge.getAttribute('data-edge-label') || '')\r
        );\r
        return relationshipTokenGeometry(shape, relationshipTokenKind(edge), key, options);\r
      }\r
      Archify.flowTokens = {\r
        create: createSemanticFlowToken,\r
        kind: function (edge) { return relationshipTokenKind(edge); },\r
        path: relationshipTokenPath\r
      };\r
      function renderRelationshipPulse(key) {\r
        removeRelationshipPulse();\r
        if (!key || document.documentElement.getAttribute('data-embed') === 'true') return false;\r
        if (document.hidden || (Archify.motionGovernor && Archify.motionGovernor.isPaused())) return false;\r
        if (reducedMotionQuery && reducedMotionQuery.matches) return false;\r
        var matchingEdges = edges().filter(function (edge) {\r
          return edge.getAttribute('data-edge-key') === key;\r
        });\r
        if (!matchingEdges.length) return false;\r
        var overlay = document.createElementNS(svgNamespace, 'g');\r
        overlay.setAttribute('class', 'relationship-pulse-overlay');\r
        overlay.setAttribute('data-relationship-pulse-overlay', '');\r
        overlay.setAttribute('data-relationship-pulse-key', key);\r
        overlay.setAttribute('aria-hidden', 'true');\r
        var tokenAdded = false;\r
        matchingEdges.forEach(function (edge) {\r
          var wrapper = document.createElementNS(svgNamespace, 'g');\r
          if (edge.hasAttribute('transform')) wrapper.setAttribute('transform', edge.getAttribute('transform'));\r
          var shapes = relationshipEdgeShapes(edge);\r
          shapes.forEach(function (shape) {\r
            wrapper.appendChild(relationshipPulseGeometry(shape));\r
          });\r
          if (!tokenAdded && shapes.length) {\r
            var tokenKind = relationshipTokenKind(edge);\r
            var token = relationshipTokenGeometry(shapes[0], tokenKind, key);\r
            if (token) {\r
              wrapper.appendChild(token);\r
              overlay.setAttribute('data-relationship-token-kind', tokenKind);\r
              tokenAdded = true;\r
            }\r
          }\r
          if (wrapper.childNodes.length) overlay.appendChild(wrapper);\r
        });\r
        if (!overlay.childNodes.length) return false;\r
        var finishPulse = function () {\r
          if (overlay.parentNode) overlay.remove();\r
        };\r
        overlay.addEventListener('animationend', finishPulse, { once: true });\r
        overlay.addEventListener('animationcancel', finishPulse, { once: true });\r
        var firstNode = svg.querySelector('[data-node-id]');\r
        if (firstNode) svg.insertBefore(overlay, firstNode);\r
        else svg.appendChild(overlay);\r
        return true;\r
      }\r
      function clearRelationshipPreview(options) {\r
        options = options || {};\r
        if (directPreviewTimer) window.clearTimeout(directPreviewTimer);\r
        directPreviewTimer = null;\r
        removeRelationshipPulse();\r
        activeRelationshipPreview = null;\r
        svg.removeAttribute('data-relationship-preview-active');\r
        svg.removeAttribute('data-relationship-direct-active');\r
        if (options.clearPin === true) {\r
          pinnedRelationship = null;\r
          pinnedRelationshipKey = null;\r
          svg.removeAttribute('data-relationship-pin-active');\r
        }\r
        chip.removeAttribute('data-relationship-previewing');\r
        edges().forEach(function (edge) { edge.removeAttribute('data-relationship-preview'); });\r
        nodes().forEach(function (node) {\r
          node.removeAttribute('data-relationship-preview-node');\r
          node.removeAttribute('data-relationship-preview-source');\r
          node.removeAttribute('data-relationship-preview-target');\r
        });\r
        Array.prototype.forEach.call(relationshipList.querySelectorAll('[data-preview-active]'), function (button) {\r
          button.removeAttribute('data-preview-active');\r
        });\r
        relationshipHitTargets.forEach(function (target) {\r
          target.setAttribute('aria-pressed', pinnedRelationshipKey && target.getAttribute('data-relationship-key') === pinnedRelationshipKey ? 'true' : 'false');\r
          target.removeAttribute('data-preview-active');\r
        });\r
        renderRelationshipCopyAction();\r
        requestLensPlacement();\r
      }\r
      function previewRelationship(button, options) {\r
        options = options || {};\r
        if (pinnedRelationshipKey && pinnedRelationship && button !== pinnedRelationship) return;\r
        clearRelationshipPreview();\r
        if (!button) return;\r
        var key = button.getAttribute('data-relationship-key');\r
        var from = button.getAttribute('data-relationship-from');\r
        var to = button.getAttribute('data-relationship-to');\r
        if (!key || !from || !to) return;\r
        svg.setAttribute('data-relationship-preview-active', key);\r
        if (options.direct === true) svg.setAttribute('data-relationship-direct-active', key);\r
        edges().forEach(function (edge) {\r
          if (edge.getAttribute('data-edge-key') === key) edge.setAttribute('data-relationship-preview', '');\r
        });\r
        nodes().forEach(function (node) {\r
          var id = node.getAttribute('data-node-id');\r
          if (id !== from && id !== to) return;\r
          node.setAttribute('data-relationship-preview-node', '');\r
          if (id === from) node.setAttribute('data-relationship-preview-source', '');\r
          if (id === to) node.setAttribute('data-relationship-preview-target', '');\r
        });\r
        button.setAttribute('data-preview-active', 'true');\r
        if (!chip.hidden && options.direct !== true) chip.setAttribute('data-relationship-previewing', 'true');\r
        activeRelationshipPreview = button;\r
        renderRelationshipPulse(key);\r
        requestLensPlacement();\r
      }\r
      function syncRelationshipPreview() {\r
        var next = pinnedRelationship || focusedRelationship || hoveredRelationship;\r
        if (next === activeRelationshipPreview) return;\r
        previewRelationship(next, { direct: !!(next && next.hasAttribute('data-relationship-hit-key')) });\r
      }\r
      function directRelationshipBlocked() {\r
        return html.getAttribute('data-embed') === 'true' ||\r
          html.getAttribute('data-guide-open') === 'true' ||\r
          container.classList.contains('is-panning') ||\r
          (activeIds.length > 0 && !pinnedRelationshipKey) ||\r
          svg.hasAttribute('data-story-active') ||\r
          svg.hasAttribute('data-route-picking') ||\r
          svg.hasAttribute('data-route-active') ||\r
          svg.hasAttribute('data-lens-active') ||\r
          svg.hasAttribute('data-chapter-preview');\r
      }\r
      function scheduleDirectRelationshipPreview(target) {\r
        if (directPreviewTimer) window.clearTimeout(directPreviewTimer);\r
        if (pinnedRelationshipKey) return;\r
        directPreviewTimer = window.setTimeout(function () {\r
          directPreviewTimer = null;\r
          if (pinnedRelationshipKey || hoveredRelationship !== target || directRelationshipBlocked()) return;\r
          previewRelationship(target, { direct: true });\r
        }, reducedMotionQuery && reducedMotionQuery.matches ? 0 : 90);\r
      }\r
      function relationshipHitTarget(key) {\r
        return relationshipHitTargets.find(function (target) {\r
          return target.getAttribute('data-relationship-key') === key;\r
        }) || null;\r
      }\r
      function revealPinnedRelationship(record) {\r
        function reveal() {\r
          if (!record || pinnedRelationshipKey !== record.key) return true;\r
          if (!Archify.view || typeof Archify.view.reveal !== 'function') return false;\r
          Archify.view.reveal([record.from, record.to], { reason: 'relationship-direct' });\r
          return true;\r
        }\r
        if (!reveal()) requestAnimationFrame(reveal);\r
      }\r
      function inspectRelationship(key, options) {\r
        options = options || {};\r
        if (html.getAttribute('data-embed') === 'true') return false;\r
        if (directPreviewTimer) window.clearTimeout(directPreviewTimer);\r
        directPreviewTimer = null;\r
        hoveredRelationship = null;\r
        focusedRelationship = null;\r
        if (pinnedRelationshipKey === key) {\r
          if (options.toggle === false) return true;\r
          clear({ updateUrl: options.updateUrl !== false });\r
          return true;\r
        }\r
        var record = relationshipRecordForKey(key);\r
        if (!record) return false;\r
        if (Archify.guidedViews && typeof Archify.guidedViews.showAll === 'function') {\r
          Archify.guidedViews.showAll({ clearFocus: false, updateUrl: false });\r
        }\r
        set(record.from, { toggle: false, updateUrl: false });\r
        var row = Array.prototype.slice.call(relationshipList.querySelectorAll('[data-relationship-key]')).find(function (candidate) {\r
          return candidate.getAttribute('data-relationship-key') === key;\r
        });\r
        if (!row) return false;\r
        previewRelationship(row);\r
        pinnedRelationship = row;\r
        pinnedRelationshipKey = key;\r
        svg.setAttribute('data-relationship-pin-active', key);\r
        var target = relationshipHitTarget(key);\r
        if (target) target.setAttribute('aria-pressed', 'true');\r
        renderRelationshipCopyAction();\r
        summary.textContent = viewerText('viewer.passport.relationship.pinned', {\r
          from: record.fromLabel,\r
          to: record.toLabel,\r
          label: record.label\r
        });\r
        revealPinnedRelationship(record);\r
        if (options.updateUrl !== false && record.id) {\r
          try { history.replaceState(null, '', location.pathname + location.search + '#relation=' + encodeURIComponent(record.id)); } catch (_) {}\r
        }\r
        return true;\r
      }\r
      function inspectRelationshipById(id, options) {\r
        var record = relationshipHitRecords().find(function (item) { return item.id === id; });\r
        return record ? inspectRelationship(record.key, options) : false;\r
      }\r
      function installRelationshipHitTargets() {\r
        if (html.getAttribute('data-embed') === 'true') return 0;\r
        var records = relationshipHitRecords();\r
        if (!records.length) return 0;\r
        relationshipHitOverlay = document.createElementNS(svgNamespace, 'g');\r
        relationshipHitOverlay.setAttribute('class', 'relationship-hit-overlay');\r
        relationshipHitOverlay.setAttribute('data-relationship-hit-overlay', '');\r
        relationshipHitOverlay.setAttribute('role', 'group');\r
        relationshipHitOverlay.setAttribute('aria-label', viewerText('viewer.passport.relationship.explorer'));\r
        var relationshipHelp = document.createElementNS(svgNamespace, 'desc');\r
        relationshipHelp.id = 'archify-relationship-help';\r
        relationshipHelp.textContent = viewerText('viewer.passport.relationship.help');\r
        relationshipHitOverlay.appendChild(relationshipHelp);\r
        records.forEach(function (record, index) {\r
          var target = document.createElementNS(svgNamespace, 'g');\r
          target.setAttribute('class', 'relationship-hit-target');\r
          target.setAttribute('data-relationship-hit-key', record.key);\r
          target.setAttribute('data-relationship-key', record.key);\r
          target.setAttribute('data-relationship-from', record.from);\r
          target.setAttribute('data-relationship-to', record.to);\r
          if (record.id) target.setAttribute('data-relationship-id', record.id);\r
          target.setAttribute('role', 'button');\r
          target.setAttribute('tabindex', index === 0 ? '0' : '-1');\r
          target.setAttribute('aria-pressed', 'false');\r
          target.setAttribute('aria-describedby', relationshipHelp.id);\r
          var description = viewerText('viewer.passport.relationship.inspect', {\r
            index: index + 1,\r
            total: records.length,\r
            from: record.fromLabel,\r
            to: record.toLabel,\r
            label: record.label\r
          });\r
          target.setAttribute('aria-label', description);\r
          var title = document.createElementNS(svgNamespace, 'title');\r
          title.textContent = record.fromLabel + ' \\u2192 ' + record.toLabel + ' \\u00b7 ' + record.label;\r
          target.appendChild(title);\r
          record.shapes.forEach(function (shape) {\r
            target.appendChild(relationshipHitGeometry(shape));\r
            target.appendChild(relationshipHitGeometry(shape, 'relationship-focus-rail'));\r
          });\r
          if (target.childNodes.length > 1) {\r
            relationshipHitTargets.push(target);\r
            relationshipHitOverlay.appendChild(target);\r
          }\r
        });\r
        if (!relationshipHitTargets.length) return 0;\r
        var firstNode = svg.querySelector('[data-node-id]');\r
        var nodeLayer = firstNode;\r
        while (nodeLayer && nodeLayer.parentNode && nodeLayer.parentNode !== svg) nodeLayer = nodeLayer.parentNode;\r
        if (nodeLayer && nodeLayer.parentNode === svg) svg.insertBefore(relationshipHitOverlay, nodeLayer);\r
        else svg.appendChild(relationshipHitOverlay);\r
\r
        relationshipHitOverlay.addEventListener('pointerdown', function (event) {\r
          if (event.target.closest('[data-relationship-hit-key]')) event.stopPropagation();\r
        });\r
        relationshipHitOverlay.addEventListener('pointerover', function (event) {\r
          if (event.pointerType === 'touch') return;\r
          if (finePointerQuery && !finePointerQuery.matches) return;\r
          var target = event.target.closest('[data-relationship-hit-key]');\r
          if (!target || directRelationshipBlocked() || pinnedRelationshipKey) return;\r
          if (event.relatedTarget && target.contains(event.relatedTarget)) return;\r
          hoveredRelationship = target;\r
          scheduleDirectRelationshipPreview(target);\r
        });\r
        relationshipHitOverlay.addEventListener('pointerout', function (event) {\r
          var target = event.target.closest('[data-relationship-hit-key]');\r
          if (!target || (event.relatedTarget && target.contains(event.relatedTarget))) return;\r
          if (hoveredRelationship === target) hoveredRelationship = null;\r
          syncRelationshipPreview();\r
        });\r
        relationshipHitOverlay.addEventListener('focusin', function (event) {\r
          var target = event.target.closest('[data-relationship-hit-key]');\r
          if (!target || directRelationshipBlocked()) return;\r
          focusedRelationship = target;\r
          if (!pinnedRelationshipKey) previewRelationship(target, { direct: true });\r
        });\r
        relationshipHitOverlay.addEventListener('focusout', function (event) {\r
          var target = event.target.closest('[data-relationship-hit-key]');\r
          if (!target || (event.relatedTarget && target.contains(event.relatedTarget))) return;\r
          if (focusedRelationship === target) focusedRelationship = null;\r
          syncRelationshipPreview();\r
        });\r
        relationshipHitOverlay.addEventListener('click', function (event) {\r
          var target = event.target.closest('[data-relationship-hit-key]');\r
          if (!target || directRelationshipBlocked()) return;\r
          event.preventDefault();\r
          event.stopPropagation();\r
          focusedRelationship = null;\r
          hoveredRelationship = null;\r
          inspectRelationship(target.getAttribute('data-relationship-key'));\r
        });\r
        relationshipHitOverlay.addEventListener('keydown', function (event) {\r
          var target = event.target.closest('[data-relationship-hit-key]');\r
          if (!target) return;\r
          if (event.key === 'Escape' && pinnedRelationshipKey) {\r
            event.preventDefault();\r
            clear({ updateUrl: false });\r
            return;\r
          }\r
          if (event.key === 'Enter' || event.key === ' ') {\r
            event.preventDefault();\r
            focusedRelationship = null;\r
            hoveredRelationship = null;\r
            inspectRelationship(target.getAttribute('data-relationship-key'));\r
            return;\r
          }\r
          if (event.key !== 'ArrowRight' && event.key !== 'ArrowLeft' && event.key !== 'ArrowDown' && event.key !== 'ArrowUp' && event.key !== 'Home' && event.key !== 'End') return;\r
          var index = relationshipHitTargets.indexOf(target);\r
          if (event.key === 'Home') index = 0;\r
          else if (event.key === 'End') index = relationshipHitTargets.length - 1;\r
          else if (event.key === 'ArrowRight' || event.key === 'ArrowDown') index = (index + 1) % relationshipHitTargets.length;\r
          else index = (index - 1 + relationshipHitTargets.length) % relationshipHitTargets.length;\r
          event.preventDefault();\r
          relationshipHitTargets.forEach(function (item, itemIndex) { item.setAttribute('tabindex', itemIndex === index ? '0' : '-1'); });\r
          try { relationshipHitTargets[index].focus({ preventScroll: true }); }\r
          catch (_) { try { relationshipHitTargets[index].focus(); } catch (_) {} }\r
        });\r
        return relationshipHitTargets.length;\r
      }\r
      function renderRelationshipLens(id, byId) {\r
        hoveredRelationship = null;\r
        focusedRelationship = null;\r
        clearRelationshipPreview({ clearPin: true });\r
        renderPassport(id, byId[id]);\r
        var relationships = relationshipsFor(id, byId);\r
        chip.removeAttribute('data-relations-expanded');\r
        relationsBtn.setAttribute('aria-expanded', 'false');\r
        relationsBtn.textContent = viewerCount('viewer.passport.relationship.count', relationships.length);\r
        relationsBtn.setAttribute('aria-label', viewerCount('viewer.passport.relationship.show', relationships.length));\r
        var counts = { out: 0, in: 0, loop: 0 };\r
        relationships.forEach(function (relationship) { counts[relationship.direction] += 1; });\r
        summary.textContent = viewerText('viewer.passport.relationship.summary', {\r
          out: counts.out,\r
          in: counts.in,\r
          loops: counts.loop ? viewerText('viewer.passport.relationship.loops', { count: counts.loop }) : ''\r
        });\r
        renderReachabilityControls(id);\r
        relationshipList.textContent = '';\r
        if (!relationships.length) {\r
          var empty = document.createElement('p');\r
          empty.className = 'relationship-lens-empty';\r
          empty.textContent = viewerText('viewer.passport.relationship.none');\r
          relationshipList.appendChild(empty);\r
          return;\r
        }\r
\r
        [\r
          { id: 'out', label: viewerText('viewer.passport.relationship.group.out') },\r
          { id: 'in', label: viewerText('viewer.passport.relationship.group.in') },\r
          { id: 'loop', label: viewerText('viewer.passport.relationship.group.loop') }\r
        ].forEach(function (group) {\r
          var items = relationships.filter(function (relationship) { return relationship.direction === group.id; });\r
          if (!items.length) return;\r
          var section = document.createElement('div');\r
          section.className = 'relationship-lens-group';\r
          var heading = document.createElement('span');\r
          heading.className = 'relationship-lens-group-title';\r
          heading.textContent = group.label + ' · ' + items.length;\r
          section.appendChild(heading);\r
          items.forEach(function (relationship) {\r
            var button = document.createElement('button');\r
            button.type = 'button';\r
            button.className = 'relationship-lens-row';\r
            button.setAttribute('data-direction', relationship.direction);\r
            button.setAttribute('data-relationship-target', relationship.neighborId);\r
            button.setAttribute('data-relationship-key', relationship.key);\r
            button.setAttribute('data-relationship-from', relationship.from);\r
            button.setAttribute('data-relationship-to', relationship.to);\r
            if (relationship.id) button.setAttribute('data-relationship-id', relationship.id);\r
            button.setAttribute('aria-label', viewerText('viewer.passport.relationship.row', {\r
              group: group.label,\r
              relationship: relationship.label,\r
              neighbor: relationship.neighborLabel\r
            }));\r
            var direction = document.createElement('span');\r
            direction.className = 'relationship-lens-direction';\r
            direction.setAttribute('aria-hidden', 'true');\r
            direction.textContent = viewerText(relationship.direction === 'out'\r
              ? 'viewer.passport.relationship.direction.out'\r
              : relationship.direction === 'in'\r
                ? 'viewer.passport.relationship.direction.in'\r
                : 'viewer.passport.relationship.direction.loop');\r
            var target = document.createElement('strong');\r
            target.textContent = relationship.neighborLabel;\r
            var relation = document.createElement('small');\r
            relation.textContent = relationship.label;\r
            button.appendChild(direction);\r
            button.appendChild(target);\r
            button.appendChild(relation);\r
            section.appendChild(button);\r
          });\r
          relationshipList.appendChild(section);\r
        });\r
      }\r
      var lensFrame = 0;\r
      function placeRelationshipLens() {\r
        lensFrame = 0;\r
        if (chip.hidden || activeIds.length !== 1) return;\r
        var node = svg.querySelector('[data-node-id="' + activeIds[0] + '"]');\r
        if (!node) return;\r
        var containerRect = container.getBoundingClientRect();\r
        var nodeRect = node.getBoundingClientRect();\r
        if (containerRect.bottom <= 0 || containerRect.top >= window.innerHeight) return;\r
        var padding = window.innerWidth <= 720 ? 8 : 16;\r
        var visibleTop = Math.max(padding, -containerRect.top + padding);\r
        var visibleBottom = Math.min(containerRect.height - padding, window.innerHeight - containerRect.top - padding);\r
        var maxTop = Math.max(padding, visibleBottom - chip.offsetHeight);\r
        var minTop = Math.min(visibleTop, maxTop);\r
        var nodeCenter = nodeRect.top - containerRect.top + nodeRect.height / 2;\r
        var mobile = window.innerWidth <= 720;\r
        var previewingOnMobile = mobile && chip.getAttribute('data-relationship-previewing') === 'true';\r
        var compactOnMobile = mobile && chip.getAttribute('data-relations-expanded') !== 'true';\r
        var preferred;\r
        if (compactOnMobile) {\r
          var nodeTop = nodeRect.top - containerRect.top;\r
          var nodeBottom = nodeRect.bottom - containerRect.top;\r
          var gap = 10;\r
          var above = nodeTop - chip.offsetHeight - gap;\r
          var below = nodeBottom + gap;\r
          if (above >= visibleTop) preferred = above;\r
          else if (below + chip.offsetHeight <= visibleBottom - 56) preferred = below;\r
          else preferred = nodeCenter < (visibleTop + visibleBottom) / 2\r
            ? Math.max(minTop, visibleBottom - chip.offsetHeight - 56)\r
            : visibleTop;\r
        } else if (previewingOnMobile) {\r
          var pinnedTop = visibleTop;\r
          var pinnedBottom = Math.max(minTop, visibleBottom - chip.offsetHeight - 56);\r
          preferred = nodeCenter < (visibleTop + visibleBottom) / 2 ? pinnedBottom : pinnedTop;\r
        } else {\r
          preferred = nodeCenter - chip.offsetHeight / 2;\r
        }\r
        var top = Math.max(minTop, Math.min(maxTop, preferred));\r
        var chipRect = chip.getBoundingClientRect();\r
        var safeGap = 10;\r
        var protectViewerChrome = !mobile || compactOnMobile || previewingOnMobile;\r
        var protectedRects = (protectViewerChrome\r
          ? [svg.querySelector('[data-legend]'), container.querySelector('.diagram-nav')]\r
          : [])\r
          .filter(function (element) {\r
            if (!element || element.hidden) return false;\r
            var style = window.getComputedStyle(element);\r
            return style.display !== 'none' && style.visibility !== 'hidden';\r
          })\r
          .map(function (element) { return element.getBoundingClientRect(); })\r
          .filter(function (rect) {\r
            return rect.width > 0 && rect.height > 0 &&\r
              chipRect.left < rect.right + safeGap && chipRect.right > rect.left - safeGap;\r
          });\r
        if (protectedRects.length) {\r
          var candidates = [top, minTop, maxTop];\r
          protectedRects.forEach(function (rect) {\r
            candidates.push(\r
              rect.top - containerRect.top - chip.offsetHeight - safeGap,\r
              rect.bottom - containerRect.top + safeGap\r
            );\r
          });\r
          var valid = candidates.map(function (candidate) {\r
            return Math.max(minTop, Math.min(maxTop, candidate));\r
          }).filter(function (candidate, index, all) {\r
            if (all.indexOf(candidate) !== index) return false;\r
            var candidateTop = containerRect.top + candidate;\r
            var candidateBottom = candidateTop + chip.offsetHeight;\r
            return protectedRects.every(function (rect) {\r
              return candidateBottom <= rect.top - safeGap || candidateTop >= rect.bottom + safeGap;\r
            });\r
          });\r
          valid.sort(function (first, second) {\r
            return Math.abs(first - preferred) - Math.abs(second - preferred);\r
          });\r
          if (valid.length) top = valid[0];\r
        }\r
        chip.style.top = Math.round(top) + 'px';\r
        if (Archify.radar && typeof Archify.radar.sync === 'function') Archify.radar.sync();\r
      }\r
      function requestLensPlacement() {\r
        if (lensFrame) return;\r
        lensFrame = requestAnimationFrame(placeRelationshipLens);\r
      }\r
      function clear(options) {\r
        options = options || {};\r
        var restoreNode = options.restoreFocus === true && activeIds.length === 1\r
          ? svg.querySelector('[data-node-id="' + activeIds[0] + '"]')\r
          : null;\r
        clearReachability({ updateUrl: false });\r
        if (Archify.intentTrace && typeof Archify.intentTrace.clear === 'function') {\r
          Archify.intentTrace.clear({ announce: false });\r
        }\r
        hoveredRelationship = null;\r
        focusedRelationship = null;\r
        clearRelationshipPreview({ clearPin: true });\r
        activeIds = [];\r
        svg.removeAttribute('data-focus-active');\r
        nodes().forEach(function (node) {\r
          node.removeAttribute('data-focus-match');\r
          node.removeAttribute('data-focus-selected');\r
          node.setAttribute('aria-pressed', 'false');\r
        });\r
        edges().forEach(function (edge) { edge.removeAttribute('data-focus-match'); });\r
        chip.hidden = true;\r
        label.textContent = '';\r
        detail.textContent = '';\r
        detail.hidden = true;\r
        kind.textContent = '';\r
        kind.hidden = true;\r
        context.textContent = '';\r
        context.hidden = true;\r
        tag.textContent = '';\r
        tag.hidden = true;\r
        semanticId.textContent = '';\r
        semanticId.hidden = true;\r
        evidence.hidden = true;\r
        evidenceLinks.textContent = '';\r
        repositoryLink.removeAttribute('href');\r
        repositoryLink.textContent = '';\r
        summary.textContent = '';\r
        reachSection.hidden = true;\r
        upstreamCount.textContent = '0';\r
        downstreamCount.textContent = '0';\r
        upstreamBtn.disabled = true;\r
        downstreamBtn.disabled = true;\r
        relationshipList.textContent = '';\r
        copyBtn.textContent = viewerText('viewer.passport.copy');\r
        copyBtn.setAttribute('aria-label', viewerText('viewer.passport.copy.focus'));\r
        relationsBtn.textContent = viewerText('viewer.passport.relations');\r
        relationsBtn.setAttribute('aria-label', viewerText('viewer.passport.relations.show'));\r
        relationsBtn.setAttribute('aria-expanded', 'false');\r
        chip.removeAttribute('data-relations-expanded');\r
        chip.style.removeProperty('top');\r
        if (options.preserveView !== true && Archify.view && typeof Archify.view.reset === 'function') {\r
          Archify.view.reset({ automatic: true });\r
        }\r
        if (options.updateUrl !== false) {\r
          try { history.replaceState(null, '', location.pathname + location.search); } catch (_) {}\r
        }\r
        if (restoreNode) {\r
          try { restoreNode.focus({ preventScroll: true }); }\r
          catch (_) { try { restoreNode.focus(); } catch (_) {} }\r
        }\r
      }\r
\r
      function setMany(ids, options) {\r
        options = options || {};\r
        if (Archify.semanticLens && typeof Archify.semanticLens.clearPreview === 'function') Archify.semanticLens.clearPreview();\r
        if (Archify.semanticLens && Archify.semanticLens.active()) {\r
          Archify.semanticLens.clear({ updateUrl: false, preserveView: true, closePanel: true });\r
        }\r
        if (options.preserveRoute !== true && Archify.routeProbe && typeof Archify.routeProbe.clear === 'function') {\r
          Archify.routeProbe.clear({ updateUrl: false, restoreFocus: false });\r
        }\r
        var nodeList = nodes();\r
        var byId = Object.create(null);\r
        nodeList.forEach(function (node) { byId[node.getAttribute('data-node-id')] = node; });\r
        var normalized = [];\r
        (ids || []).forEach(function (id) {\r
          if (byId[id] && normalized.indexOf(id) === -1) normalized.push(id);\r
        });\r
        if (!normalized.length) return false;\r
        if (normalized.length === activeIds.length && normalized.every(function (id, index) { return activeIds[index] === id; }) && options.toggle !== false) {\r
          clear();\r
          return true;\r
        }\r
\r
        clear({ updateUrl: false, preserveView: true });\r
        activeIds = normalized;\r
        var selected = Object.create(null);\r
        var related = Object.create(null);\r
        var seenEdges = {};\r
        var matchedEdges = 0;\r
        normalized.forEach(function (id) { selected[id] = true; related[id] = true; });\r
        var selectionMode = options.mode === 'selection' || normalized.length > 1;\r
\r
        edges().forEach(function (edge) {\r
          var from = edge.getAttribute('data-edge-from');\r
          var to = edge.getAttribute('data-edge-to');\r
          var match = selectionMode ? selected[from] && selected[to] : selected[from] || selected[to];\r
          if (!match) return;\r
          edge.setAttribute('data-focus-match', '');\r
          if (!selectionMode) { related[from] = true; related[to] = true; }\r
          var edgeKey = edge.getAttribute('data-edge-key') || (from + '\\u0000' + to + '\\u0000' + (edge.getAttribute('data-edge-label') || ''));\r
          if (!seenEdges[edgeKey]) { seenEdges[edgeKey] = true; matchedEdges += 1; }\r
        });\r
        nodeList.forEach(function (node) {\r
          var nodeId = node.getAttribute('data-node-id');\r
          if (related[nodeId]) node.setAttribute('data-focus-match', '');\r
          if (selected[nodeId]) {\r
            node.setAttribute('data-focus-selected', '');\r
            node.setAttribute('aria-pressed', 'true');\r
          }\r
        });\r
        svg.setAttribute('data-focus-active', normalized.join(' '));\r
        var defaultLabel = normalized.length === 1\r
          ? nodeLabel(byId[normalized[0]], normalized[0])\r
          : viewerText('viewer.guided.chapter.selectedNodes', { count: normalized.length });\r
        label.textContent = options.label || defaultLabel;\r
        chip.hidden = options.hideChip === true || normalized.length !== 1 || selectionMode;\r
        if (!chip.hidden) {\r
          renderRelationshipLens(normalized[0], byId);\r
          requestLensPlacement();\r
        }\r
        if (options.updateUrl !== false) {\r
          var key = options.urlKey || 'focus';\r
          var value = options.urlValue || normalized[0];\r
          try { history.replaceState(null, '', location.pathname + location.search + '#' + key + '=' + encodeURIComponent(value)); } catch (_) {}\r
        }\r
        return true;\r
      }\r
\r
      function set(id, options) {\r
        options = options || {};\r
        options.mode = 'neighborhood';\r
        return setMany([id], options);\r
      }\r
\r
      function fallbackCopy(value) {\r
        var field = document.createElement('textarea');\r
        field.value = value;\r
        field.setAttribute('readonly', '');\r
        field.style.position = 'fixed';\r
        field.style.opacity = '0';\r
        document.body.appendChild(field);\r
        field.select();\r
        var copied = false;\r
        try { copied = document.execCommand('copy'); } catch (_) {}\r
        field.remove();\r
        return copied;\r
      }\r
\r
      function copyFocusLink() {\r
        if (activeIds.length !== 1) return Promise.resolve(false);\r
        var record = pinnedRelationshipRecord();\r
        var relationId = record && record.id;\r
        var value = FlowBD.linkBase + (relationId\r
          ? '#relation=' + encodeURIComponent(relationId)\r
          : '#focus=' + encodeURIComponent(activeIds[0]) + (reachabilityMode ? '&reach=' + reachabilityMode : ''));\r
        var copy = navigator.clipboard && typeof navigator.clipboard.writeText === 'function'\r
          ? navigator.clipboard.writeText(value).then(function () { return true; }).catch(function () { return fallbackCopy(value); })\r
          : Promise.resolve(fallbackCopy(value));\r
        return copy.then(function (copied) {\r
          copyBtn.textContent = viewerText(copied ? 'viewer.common.copied' : 'viewer.common.copyFailed');\r
          copyBtn.setAttribute('aria-label', copied\r
            ? viewerText(relationId ? 'viewer.passport.copy.pinned.success' : 'viewer.passport.copy.focused.success')\r
            : viewerText(relationId ? 'viewer.passport.copy.pinned.failed' : 'viewer.passport.copy.focused.failed'));\r
          window.setTimeout(function () {\r
            renderRelationshipCopyAction();\r
          }, 1600);\r
          return copied;\r
        });\r
      }\r
\r
      svg.addEventListener('click', function (event) {\r
        if (container.getAttribute('data-just-panned') === 'true') return;\r
        var node = event.target.closest('[data-node-id]');\r
        if (node) {\r
          var id = node.getAttribute('data-node-id');\r
          set(id);\r
          if (activeIds.indexOf(id) !== -1 && Archify.view && typeof Archify.view.reveal === 'function') {\r
            Archify.view.reveal([id], { includeNeighbors: true, reason: 'focus' });\r
          }\r
        }\r
        else if (activeIds.length) clear();\r
      });\r
      svg.addEventListener('keydown', function (event) {\r
        var node = event.target.closest('[data-node-id]');\r
        if (!node || (event.key !== 'Enter' && event.key !== ' ')) return;\r
        event.preventDefault();\r
        var id = node.getAttribute('data-node-id');\r
        set(id);\r
        if (activeIds.indexOf(id) !== -1 && Archify.view && typeof Archify.view.reveal === 'function') {\r
          Archify.view.reveal([id], { includeNeighbors: true, reason: 'focus' });\r
        }\r
      });\r
      clearBtn.addEventListener('click', function () { clear({ restoreFocus: true }); });\r
      copyBtn.addEventListener('click', copyFocusLink);\r
      upstreamBtn.addEventListener('click', function () { applyReachability('upstream'); });\r
      downstreamBtn.addEventListener('click', function () { applyReachability('downstream'); });\r
      relationsBtn.addEventListener('click', function () {\r
        var expanded = chip.getAttribute('data-relations-expanded') === 'true';\r
        if (expanded) chip.removeAttribute('data-relations-expanded');\r
        else chip.setAttribute('data-relations-expanded', 'true');\r
        relationsBtn.setAttribute('aria-expanded', expanded ? 'false' : 'true');\r
        relationsBtn.setAttribute('aria-label', viewerText(expanded\r
          ? 'viewer.passport.relations.show'\r
          : 'viewer.passport.relations.hide'));\r
        requestLensPlacement();\r
      });\r
      relationshipList.addEventListener('click', function (event) {\r
        var button = event.target.closest('[data-relationship-target]');\r
        if (!button) return;\r
        var id = button.getAttribute('data-relationship-target');\r
        if (Archify.guidedViews && typeof Archify.guidedViews.showAll === 'function') {\r
          Archify.guidedViews.showAll({ clearFocus: false, updateUrl: false });\r
        }\r
        set(id, { toggle: false });\r
        if (Archify.view && typeof Archify.view.reveal === 'function') {\r
          Archify.view.reveal([id], { includeNeighbors: true, reason: 'relationship' });\r
        }\r
        var node = svg.querySelector('[data-node-id="' + id + '"]');\r
        if (node) {\r
          try { node.focus({ preventScroll: true }); } catch (_) { try { node.focus(); } catch (_) {} }\r
        }\r
      });\r
      relationshipList.addEventListener('pointerover', function (event) {\r
        if (event.pointerType === 'touch') return;\r
        if (finePointerQuery && !finePointerQuery.matches) return;\r
        var button = event.target.closest('[data-relationship-key]');\r
        if (!button || !relationshipList.contains(button)) return;\r
        if (event.relatedTarget && button.contains(event.relatedTarget)) return;\r
        hoveredRelationship = button;\r
        syncRelationshipPreview();\r
      });\r
      relationshipList.addEventListener('pointerout', function (event) {\r
        var button = event.target.closest('[data-relationship-key]');\r
        if (!button || (event.relatedTarget && button.contains(event.relatedTarget))) return;\r
        if (hoveredRelationship === button) hoveredRelationship = null;\r
        syncRelationshipPreview();\r
      });\r
      relationshipList.addEventListener('focusin', function (event) {\r
        var button = event.target.closest('[data-relationship-key]');\r
        if (!button) return;\r
        focusedRelationship = button;\r
        syncRelationshipPreview();\r
      });\r
      relationshipList.addEventListener('focusout', function (event) {\r
        var button = event.target.closest('[data-relationship-key]');\r
        if (!button || (event.relatedTarget && button.contains(event.relatedTarget))) return;\r
        if (focusedRelationship === button) focusedRelationship = null;\r
        syncRelationshipPreview();\r
      });\r
      relationshipList.addEventListener('keydown', function (event) {\r
        if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp' && event.key !== 'Home' && event.key !== 'End') return;\r
        var buttons = Array.prototype.slice.call(relationshipList.querySelectorAll('[data-relationship-target]'));\r
        if (!buttons.length) return;\r
        var index = buttons.indexOf(document.activeElement);\r
        if (event.key === 'Home') index = 0;\r
        else if (event.key === 'End') index = buttons.length - 1;\r
        else if (event.key === 'ArrowDown') index = Math.min(buttons.length - 1, Math.max(0, index + 1));\r
        else index = Math.max(0, index < 0 ? 0 : index - 1);\r
        event.preventDefault();\r
        buttons[index].focus();\r
      });\r
      document.addEventListener('click', function (event) {\r
        var target = event.target;\r
        if (chip.hidden || !target || typeof target.closest !== 'function' || chip.contains(target)) return;\r
        if (container.getAttribute('data-just-panned') === 'true') return;\r
        if (target.closest('[data-node-id], [data-relationship-hit-key], .overview-map')) return;\r
        clear();\r
      }, true);\r
      window.addEventListener('scroll', requestLensPlacement, { passive: true });\r
      window.addEventListener('resize', requestLensPlacement);\r
      container.addEventListener('scroll', requestLensPlacement, { passive: true });\r
      document.addEventListener('visibilitychange', function () {\r
        if (document.hidden) removeRelationshipPulse();\r
      });\r
      function syncRelationshipMotionPreference(event) {\r
        if (event.matches) removeRelationshipPulse();\r
      }\r
      if (reducedMotionQuery) {\r
        if (typeof reducedMotionQuery.addEventListener === 'function') {\r
          reducedMotionQuery.addEventListener('change', syncRelationshipMotionPreference);\r
        } else if (typeof reducedMotionQuery.addListener === 'function') {\r
          reducedMotionQuery.addListener(syncRelationshipMotionPreference);\r
        }\r
      }\r
\r
      installRelationshipHitTargets();\r
\r
      function syncFocusFromHash() {\r
        try {\r
          var params = new URLSearchParams(location.hash.replace(/^#/, ''));\r
          var relation = params.get('relation');\r
          var initial = params.get('focus');\r
          var reach = params.get('reach');\r
          if (relation) {\r
            if (html.getAttribute('data-embed') === 'true' ||\r
                !inspectRelationshipById(relation, { updateUrl: false, toggle: false })) clear({ updateUrl: false });\r
          }\r
          else if (initial) {\r
            if (set(initial, { updateUrl: false, toggle: false }) &&\r
                (reach === 'upstream' || reach === 'downstream')) {\r
              applyReachability(reach, { updateUrl: false, toggle: false, reveal: false });\r
            }\r
          }\r
          else if (!params.get('view')) clear({ updateUrl: false });\r
        } catch (_) {}\r
      }\r
\r
      window.addEventListener('hashchange', syncFocusFromHash);\r
      syncFocusFromHash();\r
\r
      return {\r
        set: set,\r
        setMany: setMany,\r
        clear: clear,\r
        copyLink: copyFocusLink,\r
        reach: applyReachability,\r
        clearReach: clearReachability,\r
        reachabilitySnapshot: reachabilitySnapshot,\r
        inspectRelationship: inspectRelationship,\r
        inspectRelationshipById: inspectRelationshipById,\r
        reposition: requestLensPlacement,\r
        relationship: function () {\r
          var record = pinnedRelationshipRecord();\r
          return record ? { id: record.id || null, key: record.key, from: record.from, to: record.to, label: record.label } : null;\r
        },\r
        reachability: function () {\r
          return activeReachability ? {\r
            direction: activeReachability.direction,\r
            originId: activeReachability.originId,\r
            nodeIds: activeReachability.nodeIds.slice(),\r
            edgeKeys: activeReachability.edgeKeys.slice(),\r
            maxDepth: activeReachability.maxDepth\r
          } : null;\r
        },\r
        active: function () { return activeIds.length === 0 ? null : (activeIds.length === 1 ? activeIds[0] : activeIds.slice()); }\r
      };\r
    })();\r
\r
    /* ============================================================\r
       Intent Trace — temporary one-hop topology before durable focus.\r
       Fine-pointer hover and keyboard focus share the same stable-ID preview;\r
       touch continues directly to the existing click-to-focus contract.\r
       ============================================================ */\r
    Archify.intentTrace = (function () {\r
      var html = document.documentElement;\r
      var container = document.querySelector('.diagram-container');\r
      var svg = container.querySelector(':scope > svg');\r
      var status = document.getElementById('intent-trace-status');\r
      var namespace = 'http://www.w3.org/2000/svg';\r
      var activeId = null;\r
      var hoveredNode = null;\r
      var focusedNode = null;\r
      var enterTimer = null;\r
\r
      function nodes() {\r
        return Array.prototype.slice.call(svg.querySelectorAll('[data-node-id]'));\r
      }\r
      function edges() {\r
        return Array.prototype.slice.call(svg.querySelectorAll('[data-edge-from][data-edge-to]'));\r
      }\r
      function nodeLabel(node, fallback) {\r
        return node.getAttribute('data-node-label') ||\r
          (node.getAttribute('aria-label') || fallback).replace(/^Focus\\s+/, '').split(',')[0];\r
      }\r
      function finePointer() {\r
        return !window.matchMedia || window.matchMedia('(hover: hover) and (pointer: fine)').matches;\r
      }\r
      function reducedMotion() {\r
        return !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);\r
      }\r
      function blocked() {\r
        return html.getAttribute('data-embed') === 'true' ||\r
          html.getAttribute('data-guide-open') === 'true' ||\r
          container.classList.contains('is-panning') ||\r
          svg.hasAttribute('data-lens-active') ||\r
          svg.hasAttribute('data-story-active') ||\r
          svg.hasAttribute('data-relationship-preview-active') ||\r
          !!(Archify.routeProbe && typeof Archify.routeProbe.active === 'function' && Archify.routeProbe.active()) ||\r
          !!(Archify.focus && typeof Archify.focus.active === 'function' && Archify.focus.active());\r
      }\r
      function edgeShapes(edge) {\r
        if (/^(path|line|polyline)$/i.test(edge.tagName)) return [edge];\r
        return Array.prototype.slice.call(edge.querySelectorAll('path, line, polyline'));\r
      }\r
      function removeOverlay() {\r
        Array.prototype.forEach.call(svg.querySelectorAll('[data-intent-trace-overlay]'), function (overlay) {\r
          overlay.remove();\r
        });\r
      }\r
      function clear(options) {\r
        options = options || {};\r
        if (enterTimer) window.clearTimeout(enterTimer);\r
        enterTimer = null;\r
        activeId = null;\r
        svg.removeAttribute('data-intent-trace-active');\r
        removeOverlay();\r
        nodes().forEach(function (node) {\r
          node.removeAttribute('data-intent-trace-match');\r
          node.removeAttribute('data-intent-trace-selected');\r
        });\r
        edges().forEach(function (edge) { edge.removeAttribute('data-intent-trace-match'); });\r
        if (options.announce !== false) status.textContent = '';\r
      }\r
      function traceGeometry(shape, direction) {\r
        var clone = shape.cloneNode(false);\r
        clone.removeAttribute('id');\r
        clone.removeAttribute('class');\r
        clone.removeAttribute('style');\r
        clone.removeAttribute('marker-start');\r
        clone.removeAttribute('marker-mid');\r
        clone.removeAttribute('marker-end');\r
        clone.removeAttribute('role');\r
        clone.removeAttribute('aria-label');\r
        clone.removeAttribute('aria-labelledby');\r
        clone.removeAttribute('data-animate');\r
        clone.removeAttribute('data-edge-from');\r
        clone.removeAttribute('data-edge-to');\r
        clone.removeAttribute('data-edge-key');\r
        clone.removeAttribute('data-edge-id');\r
        clone.removeAttribute('data-edge-label');\r
        clone.removeAttribute('data-intent-trace-match');\r
        clone.removeAttribute('data-intent-trace-selected');\r
        clone.setAttribute('class', 'intent-trace-flow');\r
        clone.setAttribute('data-direction', direction);\r
        clone.setAttribute('pathLength', '1');\r
        return clone;\r
      }\r
      function show(id, options) {\r
        options = options || {};\r
        if (!id || blocked()) {\r
          clear({ announce: false });\r
          return false;\r
        }\r
        if (activeId === id) return true;\r
        clear({ announce: false });\r
        var nodeList = nodes();\r
        var edgeList = edges();\r
        var byId = Object.create(null);\r
        nodeList.forEach(function (node) { byId[node.getAttribute('data-node-id')] = node; });\r
        var selected = byId[id];\r
        if (!selected) return false;\r
\r
        var overlay = document.createElementNS(namespace, 'g');\r
        overlay.setAttribute('class', 'intent-trace-overlay');\r
        overlay.setAttribute('data-intent-trace-overlay', '');\r
        overlay.setAttribute('aria-hidden', 'true');\r
        var related = Object.create(null);\r
        var seen = {};\r
        var counts = { out: 0, in: 0, loop: 0 };\r
        related[id] = true;\r
\r
        edgeList.forEach(function (edge) {\r
          var from = edge.getAttribute('data-edge-from');\r
          var to = edge.getAttribute('data-edge-to');\r
          if (from !== id && to !== id) return;\r
          var direction = from === id && to === id ? 'loop' : (from === id ? 'out' : 'in');\r
          var key = edge.getAttribute('data-edge-key') ||\r
            (from + '\\u0000' + to + '\\u0000' + (edge.getAttribute('data-edge-label') || ''));\r
          if (!seen[key]) {\r
            seen[key] = true;\r
            counts[direction] += 1;\r
          }\r
          related[from] = true;\r
          related[to] = true;\r
          edge.setAttribute('data-intent-trace-match', '');\r
          var wrapper = document.createElementNS(namespace, 'g');\r
          if (edge.hasAttribute('transform')) wrapper.setAttribute('transform', edge.getAttribute('transform'));\r
          edgeShapes(edge).forEach(function (shape) {\r
            wrapper.appendChild(traceGeometry(shape, direction));\r
          });\r
          if (wrapper.childNodes.length) overlay.appendChild(wrapper);\r
        });\r
\r
        nodeList.forEach(function (node) {\r
          var nodeId = node.getAttribute('data-node-id');\r
          if (related[nodeId]) node.setAttribute('data-intent-trace-match', '');\r
          if (nodeId === id) node.setAttribute('data-intent-trace-selected', '');\r
        });\r
        if (overlay.childNodes.length) {\r
          var firstEdge = edgeList[0];\r
          var firstNode = svg.querySelector('[data-node-id]');\r
          if (firstEdge && firstEdge.parentNode) firstEdge.parentNode.insertBefore(overlay, firstEdge);\r
          else if (firstNode) svg.insertBefore(overlay, firstNode);\r
          else svg.appendChild(overlay);\r
        }\r
        activeId = id;\r
        svg.setAttribute('data-intent-trace-active', id);\r
        if (options.announce === true) {\r
          var total = counts.out + counts.in + counts.loop;\r
          status.textContent = viewerText('viewer.intent.summary', {\r
            label: nodeLabel(selected, id),\r
            out: counts.out,\r
            in: counts.in,\r
            loops: counts.loop ? viewerText('viewer.intent.loops', { count: counts.loop }) : '',\r
            total: total\r
          });\r
        }\r
        return true;\r
      }\r
      function schedule(node) {\r
        if (enterTimer) window.clearTimeout(enterTimer);\r
        enterTimer = window.setTimeout(function () {\r
          enterTimer = null;\r
          if (hoveredNode === node) show(node.getAttribute('data-node-id'), { announce: false });\r
        }, reducedMotion() ? 0 : 90);\r
      }\r
      function sync() {\r
        var candidate = focusedNode || hoveredNode;\r
        if (!candidate) {\r
          clear();\r
          return;\r
        }\r
        show(candidate.getAttribute('data-node-id'), { announce: candidate === focusedNode });\r
      }\r
\r
      svg.addEventListener('pointerover', function (event) {\r
        var node = event.target.closest('[data-node-id]');\r
        if (!node || !finePointer() || event.pointerType === 'touch') return;\r
        if (event.relatedTarget && node.contains(event.relatedTarget)) return;\r
        hoveredNode = node;\r
        schedule(node);\r
      });\r
      svg.addEventListener('pointerout', function (event) {\r
        var node = event.target.closest('[data-node-id]');\r
        if (!node || (event.relatedTarget && node.contains(event.relatedTarget))) return;\r
        if (hoveredNode === node) hoveredNode = null;\r
        sync();\r
      });\r
      svg.addEventListener('focusin', function (event) {\r
        var node = event.target.closest('[data-node-id]');\r
        if (!node) return;\r
        focusedNode = node;\r
        show(node.getAttribute('data-node-id'), { announce: true });\r
      });\r
      svg.addEventListener('focusout', function (event) {\r
        var node = event.target.closest('[data-node-id]');\r
        if (!node || (event.relatedTarget && node.contains(event.relatedTarget))) return;\r
        if (focusedNode === node) focusedNode = null;\r
        sync();\r
      });\r
      container.addEventListener('pointerdown', function (event) {\r
        if (!event.target.closest('[data-node-id]')) clear({ announce: false });\r
      });\r
      window.addEventListener('blur', function () { clear({ announce: false }); });\r
\r
      return {\r
        show: show,\r
        clear: clear,\r
        active: function () { return activeId; }\r
      };\r
    })();\r
\r
    Archify.guidedViews = (function () {\r
      var data = document.getElementById('archify-guided-views-data');\r
      var panel = document.getElementById('guided-views');\r
      var prev = document.getElementById('guided-view-prev');\r
      var next = document.getElementById('guided-view-next');\r
      var all = document.getElementById('guided-view-all');\r
      var play = document.getElementById('guided-view-play');\r
      var playIcon = document.getElementById('guided-view-play-icon');\r
      var playLabel = document.getElementById('guided-view-play-label');\r
      var beatLink = document.getElementById('guided-view-beat-link');\r
      var beatLinkLabel = document.getElementById('guided-view-beat-link-label');\r
      var progressBar = document.getElementById('guided-view-progress-bar');\r
      var count = document.getElementById('guided-view-count');\r
      var handoffReceipt = document.getElementById('guided-view-handoff');\r
      var label = document.getElementById('guided-view-label');\r
      var note = document.getElementById('guided-view-note');\r
      var trail = document.getElementById('guided-view-trail');\r
      var storyCaption = document.getElementById('guided-story-caption');\r
      var storyCaptionIndex = document.getElementById('guided-story-caption-index');\r
      var storyCaptionRoute = document.getElementById('guided-story-caption-route');\r
      var storyCaptionDetail = document.getElementById('guided-story-caption-detail');\r
      var storyCaptionNext = document.getElementById('guided-story-caption-next');\r
      var storyCaptionNextLabel = document.getElementById('guided-story-caption-next-label');\r
      var chapterIndex = document.getElementById('guided-view-index');\r
      var chapterList = document.getElementById('guided-view-chapters');\r
      var shareCue = document.getElementById('share-chapter-cue');\r
      var shareCueState = document.getElementById('share-chapter-state');\r
      var shareCueCount = document.getElementById('share-chapter-count');\r
      var shareCueLabel = document.getElementById('share-chapter-label');\r
      var shareCueNote = document.getElementById('share-chapter-note');\r
      var shareCueRoute = document.getElementById('share-chapter-route');\r
      var shareCueProgress = document.getElementById('share-chapter-progress-bar');\r
      var svg = document.querySelector('.diagram-container svg');\r
      var views = [];\r
      var activeIndex = -1;\r
      var playing = false;\r
      var storyBeatTimer = null;\r
      var storyBeatIndex = -1;\r
      var storyBeatStartedAt = 0;\r
      var storyBeatElapsedMs = 0;\r
      var storyBeatDwellMs = 0;\r
      var storyPlaybackGeneration = 0;\r
      var storyFollowGeneration = 0;\r
      var storyPlaybackScope = 'story';\r
      var storyPlaybackComplete = false;\r
      var beatLinkFeedbackTimer = null;\r
      var momentRestoreGeneration = 0;\r
      var storySteps = [];\r
      var storyPulseOwnerToken = 0;\r
      var storyPulseGeneration = 0;\r
      var autoplayPending = false;\r
      var VIEW_INTERVAL_MS = 3200;\r
      var STORY_FOLLOW_MIN_DWELL_MS = 1100;\r
      var STORY_FOLLOW_DURATION_MS = 320;\r
      var chapterButtons = [];\r
      var handoffGeneration = 0;\r
      var currentHandoff = null;\r
      var previewGeneration = 0;\r
      var pointerPreviewIntent = null;\r
      var focusPreviewIntent = null;\r
      var activePreviewIndex = -1;\r
      var previewOwnerToken = 0;\r
\r
      try { views = JSON.parse(data.textContent || '[]'); } catch (_) { views = []; }\r
      if (!views.length) return { count: 0, active: function () { return null; } };\r
      var canonicalNodeIds = Object.create(null);\r
      Array.prototype.forEach.call(svg.querySelectorAll('[data-node-id]'), function (node) {\r
        canonicalNodeIds[node.getAttribute('data-node-id')] = true;\r
      });\r
      views.forEach(function (view) {\r
        var seen = Object.create(null);\r
        view.focus = (view.focus || []).filter(function (id) {\r
          if (!canonicalNodeIds[id] || seen[id]) return false;\r
          seen[id] = true;\r
          return true;\r
        });\r
      });\r
      // Establish the compact cold state before exposing the panel so the\r
      // full Director cannot flash during first paint. Hash restoration runs\r
      // in the same task and replaces this state before paint when valid.\r
      panel.setAttribute('data-active-view', 'all');\r
      panel.hidden = false;\r
      panel.setAttribute('data-view-interval-ms', String(VIEW_INTERVAL_MS));\r
      panel.setAttribute('data-story-follow-min-dwell-ms', String(STORY_FOLLOW_MIN_DWELL_MS));\r
      buildChapterIndex();\r
\r
      function reducedMotion() {\r
        return !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);\r
      }\r
\r
      function findNode(id) {\r
        return Array.prototype.find.call(svg.querySelectorAll('[data-node-id]'), function (node) {\r
          return node.getAttribute('data-node-id') === id;\r
        }) || null;\r
      }\r
\r
      function chapterDelta(previous, destination) {\r
        var previousFocus = previous ? previous.focus : [];\r
        var destinationFocus = destination ? destination.focus : [];\r
        var previousIds = Object.create(null);\r
        var destinationIds = Object.create(null);\r
        previousFocus.forEach(function (id) { previousIds[id] = true; });\r
        destinationFocus.forEach(function (id) { destinationIds[id] = true; });\r
        return {\r
          stay: previousFocus.filter(function (id) { return destinationIds[id]; }),\r
          enter: destinationFocus.filter(function (id) { return !previousIds[id]; }),\r
          leave: previousFocus.filter(function (id) { return !destinationIds[id]; })\r
        };\r
      }\r
\r
      function chapterAnchor(previous, destination, outgoingBeatIndex, delta) {\r
        if (!previous || !destination) return '';\r
        var stayIds = Object.create(null);\r
        delta.stay.forEach(function (id) { stayIds[id] = true; });\r
        var activeBeat = outgoingBeatIndex >= 0 ? previous.focus[outgoingBeatIndex] : '';\r
        if (activeBeat && stayIds[activeBeat]) return activeBeat;\r
        for (var index = previous.focus.length - 1; index >= 0; index -= 1) {\r
          if (stayIds[previous.focus[index]]) return previous.focus[index];\r
        }\r
        return '';\r
      }\r
\r
      function handoffMotionAllowed() {\r
        if (document.hidden || reducedMotion()) return false;\r
        if (document.documentElement.getAttribute('data-embed') === 'true') return false;\r
        if (window.matchMedia && window.matchMedia('print').matches) return false;\r
        return !(Archify.motionGovernor && Archify.motionGovernor.capable && Archify.motionGovernor.isPaused());\r
      }\r
\r
      function classifyHandoff(delta, anchor) {\r
        var roles = Object.create(null);\r
        delta.stay.forEach(function (id) { roles[id] = 'stay'; });\r
        delta.enter.forEach(function (id) { roles[id] = 'enter'; });\r
        delta.leave.forEach(function (id) { roles[id] = 'leave'; });\r
        Array.prototype.forEach.call(svg.querySelectorAll('[data-node-id]'), function (node) {\r
          var id = node.getAttribute('data-node-id');\r
          var role = roles[id] || '';\r
          if (role) node.setAttribute('data-chapter-role', role);\r
          else node.removeAttribute('data-chapter-role');\r
        });\r
        svg.setAttribute('data-chapter-handoff', anchor ? 'anchor' : 'no-anchor');\r
        if (anchor) svg.setAttribute('data-chapter-anchor', anchor);\r
        else svg.removeAttribute('data-chapter-anchor');\r
      }\r
\r
      function drawHandoffAnchor(id) {\r
        var node = findNode(id);\r
        if (!node) return null;\r
        var box;\r
        try { box = node.getBBox(); } catch (_) { return null; }\r
        var overlay = document.createElementNS('http://www.w3.org/2000/svg', 'g');\r
        var ring = document.createElementNS('http://www.w3.org/2000/svg', 'rect');\r
        overlay.setAttribute('class', 'chapter-handoff-overlay');\r
        overlay.setAttribute('data-chapter-handoff-overlay', '');\r
        overlay.setAttribute('aria-hidden', 'true');\r
        ring.setAttribute('class', 'chapter-handoff-anchor');\r
        ring.setAttribute('x', String(box.x - 8));\r
        ring.setAttribute('y', String(box.y - 8));\r
        ring.setAttribute('width', String(box.width + 16));\r
        ring.setAttribute('height', String(box.height + 16));\r
        ring.setAttribute('rx', '10');\r
        overlay.appendChild(ring);\r
        svg.appendChild(overlay);\r
        return overlay;\r
      }\r
\r
      function clearHandoffPresentation() {\r
        svg.removeAttribute('data-chapter-handoff');\r
        svg.removeAttribute('data-chapter-anchor');\r
        Array.prototype.forEach.call(svg.querySelectorAll('[data-chapter-handoff-overlay]'), function (overlay) { overlay.remove(); });\r
        Array.prototype.forEach.call(svg.querySelectorAll('[data-chapter-role]'), function (node) { node.removeAttribute('data-chapter-role'); });\r
        if (handoffReceipt) {\r
          handoffReceipt.hidden = true;\r
          handoffReceipt.textContent = '';\r
        }\r
      }\r
\r
      function completeHandoff(handoff, outcome) {\r
        if (!handoff || currentHandoff !== handoff) return false;\r
        if (handoff.holdTimer) clearTimeout(handoff.holdTimer);\r
        handoff.holdTimer = null;\r
        currentHandoff = null;\r
        clearHandoffPresentation();\r
        if (handoff.ownerToken && Archify.motionGovernor) Archify.motionGovernor.release(handoff.ownerToken);\r
        handoff.resolve({ id: handoff.id, state: outcome || 'complete', anchor: handoff.anchor || null });\r
        syncStoryControlsDisabled();\r
        syncChapterPreview();\r
        return true;\r
      }\r
\r
      function settleHandoff(reason) {\r
        var handoff = currentHandoff;\r
        if (!handoff) return false;\r
        if (handoff.holdTimer) clearTimeout(handoff.holdTimer);\r
        handoff.holdTimer = null;\r
        if (handoff.camera && handoff.camera.cancel) handoff.camera.cancel(reason || 'settled', true);\r
        else if (Archify.view && Archify.view.reveal) Archify.view.reveal(handoff.focus, { instant: true, reason: reason || 'settled' });\r
        completeHandoff(handoff, reason || 'settled');\r
        return true;\r
      }\r
\r
      function cancelHandoff(reason) {\r
        var handoff = currentHandoff;\r
        if (!handoff) return false;\r
        if (handoff.holdTimer) clearTimeout(handoff.holdTimer);\r
        handoff.holdTimer = null;\r
        if (handoff.camera && handoff.camera.cancel) handoff.camera.cancel(reason || 'manual', false);\r
        completeHandoff(handoff, reason || 'manual');\r
        return true;\r
      }\r
\r
      function afterHandoff(callback) {\r
        if (!currentHandoff) { callback(); return; }\r
        currentHandoff.finished.then(callback);\r
      }\r
\r
      function beginHandoff(previousIndex, nextIndex, previous, destination, outgoingBeatIndex, reason) {\r
        if (!Archify.view || !Archify.view.reveal) return null;\r
        if (!previous || previousIndex === nextIndex) {\r
          Archify.view.reveal(destination.focus, { reason: reason });\r
          return null;\r
        }\r
        var delta = chapterDelta(previous, destination);\r
        var anchor = chapterAnchor(previous, destination, outgoingBeatIndex, delta);\r
        if (!handoffMotionAllowed()) {\r
          Archify.view.reveal(destination.focus, { instant: true, reason: reason });\r
          return null;\r
        }\r
        var resolver;\r
        var handoff = {\r
          id: ++handoffGeneration,\r
          mode: anchor ? 'holding' : 'no-anchor',\r
          anchor: anchor,\r
          focus: destination.focus.slice(),\r
          holdTimer: null,\r
          camera: null,\r
          ownerToken: 0,\r
          finished: new Promise(function (resolve) { resolver = resolve; }),\r
          resolve: resolver\r
        };\r
        currentHandoff = handoff;\r
        classifyHandoff(delta, anchor);\r
        if (anchor) {\r
          drawHandoffAnchor(anchor);\r
          var node = findNode(anchor);\r
          var nodeLabel = node ? (node.getAttribute('data-node-label') || anchor) : anchor;\r
          handoffReceipt.textContent = viewerText('viewer.guided.handoff', {\r
            from: (previousIndex + 1 < 10 ? '0' : '') + (previousIndex + 1),\r
            to: (nextIndex + 1 < 10 ? '0' : '') + (nextIndex + 1),\r
            label: nodeLabel\r
          });\r
          handoffReceipt.hidden = false;\r
        }\r
        if (Archify.motionGovernor) {\r
          handoff.ownerToken = Archify.motionGovernor.claim('handoff', function () {\r
            if (currentHandoff === handoff) settleHandoff('preempted');\r
          });\r
        }\r
        var startCamera = function () {\r
          if (currentHandoff !== handoff) return;\r
          handoff.holdTimer = null;\r
          handoff.mode = 'settling';\r
          svg.setAttribute('data-chapter-handoff', anchor ? 'settling' : 'no-anchor');\r
          handoff.camera = Archify.view.reveal(destination.focus, { reason: reason, duration: 420 });\r
          if (handoff.camera && handoff.camera.finished) {\r
            handoff.camera.finished.then(function (outcome) {\r
              if (currentHandoff === handoff) completeHandoff(handoff, outcome && outcome.state || 'complete');\r
            });\r
          } else {\r
            completeHandoff(handoff, 'complete');\r
          }\r
        };\r
        if (anchor) handoff.holdTimer = setTimeout(startCamera, 110);\r
        else startCamera();\r
        return handoff;\r
      }\r
\r
      function centerChapterButton(button) {\r
        if (!button || !chapterList) return false;\r
        var target = Math.max(0, button.offsetLeft - (chapterList.clientWidth - button.offsetWidth) / 2);\r
        if (typeof chapterList.scrollTo === 'function') chapterList.scrollTo({ left: target, behavior: 'auto' });\r
        else chapterList.scrollLeft = target;\r
        return true;\r
      }\r
\r
      function focusChapterButton(index) {\r
        if (!chapterButtons.length) return false;\r
        index = Math.max(0, Math.min(chapterButtons.length - 1, index));\r
        chapterButtons.forEach(function (button, buttonIndex) {\r
          button.setAttribute('tabindex', buttonIndex === index ? '0' : '-1');\r
        });\r
        chapterButtons[index].focus();\r
        centerChapterButton(chapterButtons[index]);\r
        return true;\r
      }\r
\r
      function buildChapterIndex() {\r
        chapterButtons = [];\r
        chapterList.textContent = '';\r
        views.forEach(function (view, index) {\r
          var item = document.createElement('li');\r
          var button = document.createElement('button');\r
          button.type = 'button';\r
          button.className = 'guided-view-chapter';\r
          button.setAttribute('data-guided-view-id', view.id);\r
          button.setAttribute('aria-pressed', 'false');\r
          button.setAttribute('tabindex', index === 0 ? '0' : '-1');\r
          button.setAttribute('aria-label', viewerText('viewer.guided.chapter.open', {\r
            index: index + 1,\r
            total: views.length,\r
            label: view.label,\r
            count: view.focus.length\r
          }));\r
          button.title = view.label + ' — ' + (view.note || viewerText('viewer.guided.chapter.selectedNodes', { count: view.focus.length }));\r
          var position = document.createElement('span');\r
          position.className = 'guided-view-chapter-index';\r
          position.setAttribute('aria-hidden', 'true');\r
          position.textContent = (index + 1 < 10 ? '0' : '') + (index + 1);\r
          var title = document.createElement('span');\r
          title.className = 'guided-view-chapter-title';\r
          title.textContent = view.label;\r
          var stops = document.createElement('em');\r
          stops.className = 'guided-view-chapter-count';\r
          stops.textContent = viewerCount('viewer.guided.chapter.stop', view.focus.length);\r
          var delta = document.createElement('span');\r
          delta.className = 'guided-view-chapter-delta';\r
          delta.hidden = true;\r
          delta.setAttribute('aria-hidden', 'true');\r
          ['stay', 'enter', 'leave'].forEach(function (kind) {\r
            var value = document.createElement('span');\r
            value.setAttribute('data-delta-kind', kind);\r
            delta.appendChild(value);\r
          });\r
          button.appendChild(position);\r
          button.appendChild(title);\r
          button.appendChild(stops);\r
          button.appendChild(delta);\r
          item.appendChild(button);\r
          chapterList.appendChild(item);\r
          chapterButtons.push(button);\r
        });\r
      }\r
\r
      function syncChapterIndex() {\r
        chapterButtons.forEach(function (button, index) {\r
          var current = index === activeIndex;\r
          var stops = button.querySelector('.guided-view-chapter-count');\r
          var deltaLabel = button.querySelector('.guided-view-chapter-delta');\r
          var position = activeIndex < 0 ? 'available' : (current ? 'current' : (index < activeIndex ? 'before' : 'after'));\r
          button.setAttribute('data-chapter-position', position);\r
          button.setAttribute('aria-pressed', current ? 'true' : 'false');\r
          button.setAttribute('tabindex', current || (activeIndex < 0 && index === 0) ? '0' : '-1');\r
          if (current) {\r
            stops.hidden = false;\r
            deltaLabel.hidden = true;\r
            button.removeAttribute('data-chapter-delta');\r
            button.setAttribute('aria-label', viewerText('viewer.guided.chapter.current', {\r
              index: index + 1,\r
              total: views.length,\r
              label: views[index].label,\r
              count: views[index].focus.length\r
            }));\r
            button.title = viewerText('viewer.guided.chapter.current.title', {\r
              label: views[index].label,\r
              count: views[index].focus.length\r
            });\r
          } else {\r
            var delta = chapterDelta(activeIndex >= 0 ? views[activeIndex] : null, views[index]);\r
            var compact = '=' + delta.stay.length + ' +' + delta.enter.length + ' \\u2212' + delta.leave.length;\r
            var expanded = viewerText('viewer.guided.chapter.delta.expanded', {\r
              stay: delta.stay.length,\r
              enter: delta.enter.length,\r
              leave: delta.leave.length\r
            });\r
            stops.hidden = true;\r
            deltaLabel.hidden = false;\r
            deltaLabel.querySelector('[data-delta-kind="stay"]').textContent = '=' + delta.stay.length;\r
            deltaLabel.querySelector('[data-delta-kind="enter"]').textContent = '+' + delta.enter.length;\r
            deltaLabel.querySelector('[data-delta-kind="leave"]').textContent = '\\u2212' + delta.leave.length;\r
            button.setAttribute('data-chapter-delta', compact);\r
            button.setAttribute('aria-label', viewerText('viewer.guided.chapter.delta.aria', {\r
              index: index + 1,\r
              total: views.length,\r
              label: views[index].label,\r
              delta: expanded\r
            }));\r
            button.title = viewerText('viewer.guided.chapter.delta.title', {\r
              label: views[index].label,\r
              delta: compact\r
            });\r
          }\r
          if (current) button.setAttribute('aria-current', 'step');\r
          else button.removeAttribute('aria-current');\r
          if (button.parentElement) button.parentElement.setAttribute('data-chapter-position', position);\r
        });\r
        if (activeIndex >= 0) centerChapterButton(chapterButtons[activeIndex]);\r
      }\r
\r
      function chapterPreviewBlocked() {\r
        if (document.hidden || playing || currentHandoff) return true;\r
        if (document.documentElement.getAttribute('data-embed') === 'true') return true;\r
        if (window.matchMedia && window.matchMedia('print').matches) return true;\r
        if (svg.hasAttribute('data-route-picking') || svg.hasAttribute('data-route-active')) return true;\r
        if (svg.hasAttribute('data-lens-active') || svg.hasAttribute('data-legend-preview-active')) return true;\r
        if (svg.hasAttribute('data-relationship-preview-active') || svg.hasAttribute('data-intent-trace-active')) return true;\r
        return activeIndex < 0 && svg.hasAttribute('data-focus-active');\r
      }\r
\r
      function clearChapterPreviewPresentation() {\r
        svg.removeAttribute('data-chapter-preview');\r
        Array.prototype.forEach.call(svg.querySelectorAll('[data-chapter-preview-role]'), function (node) {\r
          node.removeAttribute('data-chapter-preview-role');\r
        });\r
        chapterButtons.forEach(function (button) { button.removeAttribute('data-preview-active'); });\r
        activePreviewIndex = -1;\r
        if (previewOwnerToken && Archify.motionGovernor) {\r
          var token = previewOwnerToken;\r
          previewOwnerToken = 0;\r
          Archify.motionGovernor.release(token);\r
        }\r
      }\r
\r
      function clearChapterPreview(options) {\r
        options = options || {};\r
        previewGeneration += 1;\r
        if (options.clearIntents !== false) {\r
          pointerPreviewIntent = null;\r
          focusPreviewIntent = null;\r
        }\r
        clearChapterPreviewPresentation();\r
        return true;\r
      }\r
\r
      function winningChapterPreviewIntent() {\r
        return [pointerPreviewIntent, focusPreviewIntent].filter(function (intent) {\r
          return intent && intent.index >= 0 && intent.index < views.length && intent.index !== activeIndex;\r
        }).sort(function (left, right) { return right.generation - left.generation; })[0] || null;\r
      }\r
\r
      function showChapterPreview(index) {\r
        if (index < 0 || index >= views.length || index === activeIndex || chapterPreviewBlocked()) {\r
          clearChapterPreviewPresentation();\r
          return false;\r
        }\r
        if (activePreviewIndex === index && svg.getAttribute('data-chapter-preview') === views[index].id) return true;\r
        clearChapterPreviewPresentation();\r
        var delta = chapterDelta(activeIndex >= 0 ? views[activeIndex] : null, views[index]);\r
        var roles = Object.create(null);\r
        delta.stay.forEach(function (id) { roles[id] = 'stay'; });\r
        delta.enter.forEach(function (id) { roles[id] = 'enter'; });\r
        delta.leave.forEach(function (id) { roles[id] = 'leave'; });\r
        Array.prototype.forEach.call(svg.querySelectorAll('[data-node-id]'), function (node) {\r
          var role = roles[node.getAttribute('data-node-id')];\r
          if (role) node.setAttribute('data-chapter-preview-role', role);\r
        });\r
        svg.setAttribute('data-chapter-preview', views[index].id);\r
        chapterButtons[index].setAttribute('data-preview-active', 'true');\r
        activePreviewIndex = index;\r
        if (Archify.motionGovernor && Archify.motionGovernor.capable) {\r
          previewOwnerToken = Archify.motionGovernor.claim('chapter-preview', function () {\r
            previewOwnerToken = 0;\r
            clearChapterPreviewPresentation();\r
          });\r
        }\r
        return true;\r
      }\r
\r
      function syncChapterPreview() {\r
        var intent = winningChapterPreviewIntent();\r
        if (!intent || chapterPreviewBlocked()) {\r
          clearChapterPreviewPresentation();\r
          return false;\r
        }\r
        return showChapterPreview(intent.index);\r
      }\r
\r
      function setChapterPreviewIntent(source, index) {\r
        var intent = { index: index, generation: ++previewGeneration };\r
        if (source === 'pointer') pointerPreviewIntent = intent;\r
        else focusPreviewIntent = intent;\r
        if (playing) pausePlayback();\r
        return syncChapterPreview();\r
      }\r
\r
      function clearChapterPreviewIntent(source, index) {\r
        var intent = source === 'pointer' ? pointerPreviewIntent : focusPreviewIntent;\r
        if (intent && (typeof index !== 'number' || intent.index === index)) {\r
          if (source === 'pointer') pointerPreviewIntent = null;\r
          else focusPreviewIntent = null;\r
          previewGeneration += 1;\r
        }\r
        return syncChapterPreview();\r
      }\r
\r
      function hoverCapable() {\r
        return !!(window.matchMedia && window.matchMedia('(hover: hover)').matches);\r
      }\r
\r
      function sharePlaybackRequested() {\r
        try { return new URLSearchParams(location.search).get('play') === '1'; }\r
        catch (_) { return false; }\r
      }\r
\r
      autoplayPending = sharePlaybackRequested();\r
      if (autoplayPending) {\r
        document.documentElement.setAttribute('data-share-playback', 'true');\r
        setAutoplayState('pending');\r
      }\r
\r
      function setAutoplayState(state) {\r
        if (state) panel.setAttribute('data-autoplay', state);\r
        else panel.removeAttribute('data-autoplay');\r
        renderShareCue();\r
      }\r
\r
      function shareCueStatus(state) {\r
        return {\r
          pending: viewerText('viewer.guided.state.ready'),\r
          playing: viewerText('viewer.guided.state.playing'),\r
          complete: viewerText('viewer.guided.state.settled'),\r
          interrupted: viewerText('viewer.guided.state.paused'),\r
          pinned: viewerText('viewer.guided.state.pinned'),\r
          'reduced-motion': viewerText('viewer.guided.state.still')\r
        }[state] || viewerText('viewer.guided.state.ready');\r
      }\r
\r
      function shareCueBeatCopy(state, view, stops) {\r
        var total = stops.length;\r
        var activeStop = storyBeatIndex >= 0 ? stops[storyBeatIndex] : null;\r
        if ((state === 'playing' || state === 'interrupted') && activeStop) {\r
          return viewerText('viewer.guided.share.step', {\r
            index: (storyBeatIndex + 1 < 10 ? '0' : '') + (storyBeatIndex + 1),\r
            total: (total < 10 ? '0' : '') + total,\r
            label: activeStop.textContent\r
          });\r
        }\r
        if (state === 'pinned' && activeStop) {\r
          return storyBeatCopy(storySteps[storyBeatIndex], total);\r
        }\r
        if (state === 'reduced-motion' && activeStop && hashBeatMatchesCurrent()) {\r
          return viewerText('viewer.guided.share.staticMoment', {\r
            step: viewerText('viewer.guided.share.step', {\r
              index: (storyBeatIndex + 1 < 10 ? '0' : '') + (storyBeatIndex + 1),\r
              total: (total < 10 ? '0' : '') + total,\r
              label: activeStop.textContent\r
            })\r
          });\r
        }\r
        if (state === 'complete') return viewerText('viewer.guided.share.complete', {\r
          count: total,\r
          note: view.note || viewerText('viewer.guided.share.settled')\r
        });\r
        if (state === 'reduced-motion') return viewerText('viewer.guided.share.staticPath', { count: total });\r
        if (state === 'pending') return viewerText('viewer.guided.share.ready', { count: total });\r
        return view.note || viewerText('viewer.guided.chapter.selectedNodes', { count: view.focus.length });\r
      }\r
\r
      function renderShareCue() {\r
        if (!shareCue) return;\r
        var view = activeIndex >= 0 ? views[activeIndex] : null;\r
        var shareMode = document.documentElement.getAttribute('data-share-playback') === 'true';\r
        var embedMode = document.documentElement.getAttribute('data-embed') === 'true';\r
        var pinnedMode = !shareMode && embedMode && hashBeatMatchesCurrent();\r
        if (pinnedMode) document.documentElement.setAttribute('data-share-moment', 'true');\r
        else document.documentElement.removeAttribute('data-share-moment');\r
        shareCue.hidden = !(embedMode && view && (shareMode || pinnedMode));\r
        if (shareCue.hidden) return;\r
        var state = pinnedMode ? 'pinned' : (panel.getAttribute('data-autoplay') || 'pending');\r
        var stops = Array.prototype.slice.call(trail.querySelectorAll('[data-story-node]'));\r
        var route = stops.map(function (stop, index) {\r
          if (index === 0) return stop.textContent;\r
          var kind = stop.getAttribute('data-story-link');\r
          var separator = kind === 'forward' ? '\\u2192' : (kind === 'reverse' ? '\\u2190' : (kind === 'multiple' ? '\\u21c4' : '\\u00b7'));\r
          return separator + ' ' + stop.textContent;\r
        }).join(' ');\r
        var beatCopy = shareCueBeatCopy(state, view, stops);\r
        shareCue.setAttribute('data-state', state);\r
        shareCue.setAttribute('aria-live', state === 'playing' ? 'off' : 'polite');\r
        shareCueState.textContent = shareCueStatus(state);\r
        shareCueCount.textContent = viewerText('viewer.guided.share.chapter', {\r
          index: (activeIndex + 1 < 10 ? '0' : '') + (activeIndex + 1),\r
          total: (views.length < 10 ? '0' : '') + views.length\r
        });\r
        shareCueLabel.textContent = view.label;\r
        shareCueNote.textContent = beatCopy;\r
        shareCueRoute.textContent = route;\r
        shareCue.setAttribute('aria-label', viewerText('viewer.guided.share.aria', {\r
          state: shareCueStatus(state),\r
          index: activeIndex + 1,\r
          total: views.length,\r
          label: view.label,\r
          beat: beatCopy,\r
          route: route\r
        }));\r
      }\r
\r
      function setShareCueProgress(fraction) {\r
        if (!shareCueProgress) return;\r
        shareCueProgress.style.animation = 'none';\r
        shareCueProgress.style.setProperty('--guided-progress-start', String(Math.max(0, Math.min(1, fraction))));\r
        shareCueProgress.style.transform = 'scaleX(' + Math.max(0, Math.min(1, fraction)) + ')';\r
      }\r
\r
      function startShareCueProgress(fraction, duration) {\r
        if (!shareCueProgress) return;\r
        setShareCueProgress(fraction || 0);\r
        void shareCueProgress.offsetWidth;\r
        shareCueProgress.style.animation = 'archify-guided-progress ' + Math.max(1, duration || VIEW_INTERVAL_MS) + 'ms linear forwards';\r
      }\r
\r
      function storyNodeLabel(node, fallback) {\r
        if (!node) return fallback;\r
        return node.getAttribute('data-node-label') ||\r
          (node.getAttribute('aria-label') || fallback).replace(/^Focus\\s+/, '');\r
      }\r
\r
      function storyEdgeKey(edge) {\r
        return edge.getAttribute('data-edge-key') || (\r
          edge.getAttribute('data-edge-from') + '\\u0000' +\r
          edge.getAttribute('data-edge-to') + '\\u0000' +\r
          (edge.getAttribute('data-edge-label') || '')\r
        );\r
      }\r
\r
      function uniqueStoryEdges(edgeList) {\r
        var positions = {};\r
        var unique = [];\r
        edgeList.forEach(function (edge) {\r
          var key = storyEdgeKey(edge);\r
          if (!Object.prototype.hasOwnProperty.call(positions, key)) {\r
            positions[key] = unique.length;\r
            unique.push(edge);\r
            return;\r
          }\r
          var index = positions[key];\r
          if (!storyGeometry(unique[index]).length && storyGeometry(edge).length) unique[index] = edge;\r
        });\r
        return unique;\r
      }\r
\r
      function storyStep(view, index, edgeList, byId) {\r
        var id = view.focus[index];\r
        var node = byId[id];\r
        var previousId = index > 0 ? view.focus[index - 1] : '';\r
        var forward = [];\r
        var reverse = [];\r
        if (previousId) {\r
          edgeList.forEach(function (edge) {\r
            var from = edge.getAttribute('data-edge-from');\r
            var to = edge.getAttribute('data-edge-to');\r
            if (from === previousId && to === id) forward.push(edge);\r
            else if (from === id && to === previousId) reverse.push(edge);\r
          });\r
        }\r
        forward = uniqueStoryEdges(forward);\r
        reverse = uniqueStoryEdges(reverse);\r
        var edges = forward.concat(reverse).sort(function (left, right) {\r
          return edgeList.indexOf(left) - edgeList.indexOf(right);\r
        });\r
        var relation = index === 0 ? 'start' : (!edges.length ? 'group' : (\r
          edges.length === 1 && forward.length === 1 ? 'forward' :\r
          (edges.length === 1 && reverse.length === 1 ? 'reverse' : 'multiple')\r
        ));\r
        return {\r
          index: index,\r
          nodeId: id,\r
          nodeLabel: storyNodeLabel(byId[id], id),\r
          previousId: previousId,\r
          previousLabel: previousId ? storyNodeLabel(byId[previousId], previousId) : '',\r
          relation: relation,\r
          edges: edges,\r
          edgeKeys: edges.map(storyEdgeKey),\r
          edgeLabels: edges.map(function (edge) { return edge.getAttribute('data-edge-label') || ''; }).filter(function (value, edgeIndex, values) {\r
            return value && values.indexOf(value) === edgeIndex;\r
          }),\r
          responsibility: node ? (node.getAttribute('data-node-sublabel') || '') : '',\r
          context: node ? (node.getAttribute('data-node-context') || '') : ''\r
        };\r
      }\r
\r
      function storyBeatCopy(step, total) {\r
        if (!step) return '';\r
        var position = (step.index + 1 < 10 ? '0' : '') + (step.index + 1);\r
        var countValue = (total < 10 ? '0' : '') + total;\r
        if (step.relation === 'start') return viewerText('viewer.guided.beat.start', { index: position, total: countValue, label: step.nodeLabel });\r
        if (step.relation === 'forward') return viewerText('viewer.guided.beat.forward', { index: position, total: countValue, from: step.previousLabel, to: step.nodeLabel });\r
        if (step.relation === 'reverse') return viewerText('viewer.guided.beat.reverse', { index: position, total: countValue, from: step.nodeLabel, to: step.previousLabel });\r
        if (step.relation === 'multiple') return viewerText('viewer.guided.beat.multiple', { index: position, total: countValue, from: step.previousLabel, to: step.nodeLabel, count: step.edges.length });\r
        return viewerText('viewer.guided.beat.group', { index: position, total: countValue, from: step.previousLabel, to: step.nodeLabel });\r
      }\r
\r
      function storyBeatAria(step, total) {\r
        var prefix = viewerText('viewer.guided.beat.aria.prefix', { index: step.index + 1, total: total, label: step.nodeLabel });\r
        if (step.relation === 'start') return prefix + viewerText('viewer.guided.beat.aria.start');\r
        if (step.relation === 'forward') return prefix + viewerText('viewer.guided.beat.aria.forward', { from: step.previousLabel });\r
        if (step.relation === 'reverse') return prefix + viewerText('viewer.guided.beat.aria.reverse', { from: step.previousLabel, to: step.nodeLabel });\r
        if (step.relation === 'multiple') return prefix + viewerText('viewer.guided.beat.aria.multiple', { from: step.previousLabel, count: step.edges.length });\r
        return prefix + viewerText('viewer.guided.beat.aria.group', { from: step.previousLabel });\r
      }\r
\r
      function storyCaptionRouteCopy(step) {\r
        if (step.relation === 'start') return step.nodeLabel + ' · ' + viewerText('viewer.guided.caption.start');\r
        if (step.relation === 'reverse') return step.previousLabel + ' ← ' + step.nodeLabel;\r
        if (step.relation === 'multiple') return step.previousLabel + ' ⇄ ' + step.nodeLabel;\r
        if (step.relation === 'group') return step.previousLabel + ' · ' + step.nodeLabel;\r
        return step.previousLabel + ' → ' + step.nodeLabel;\r
      }\r
\r
      function storyCaptionDetailCopy(step) {\r
        var facts = [];\r
        if (step.relation === 'group') facts.push(viewerText('viewer.guided.caption.grouped'));\r
        else if (step.edgeLabels.length) facts.push(step.edgeLabels.slice(0, 3).join(' + ') + (step.edgeLabels.length > 3 ? viewerText('viewer.guided.caption.more', { count: step.edgeLabels.length - 3 }) : ''));\r
        else if (step.relation === 'reverse') facts.push(viewerText('viewer.guided.caption.reverse'));\r
        else if (step.relation === 'multiple') facts.push(viewerText('viewer.guided.caption.relationships', { count: step.edges.length }));\r
        else if (step.relation !== 'start') facts.push(viewerText('viewer.guided.caption.relationship'));\r
        if (step.relation === 'reverse') facts.push(viewerText('viewer.guided.caption.direction', { from: step.nodeLabel, to: step.previousLabel }));\r
        if (step.responsibility) facts.push(step.responsibility);\r
        if (step.context) facts.push(step.context);\r
        if (!facts.length) facts.push(viewerText('viewer.guided.caption.starting'));\r
        return facts.join(' · ');\r
      }\r
\r
      function renderStoryCaption(step, total, nextStep) {\r
        if (!storyCaption) return;\r
        if (!step) {\r
          storyCaption.hidden = true;\r
          storyCaption.removeAttribute('data-story-caption');\r
          storyCaptionNext.hidden = true;\r
          storyCaptionNextLabel.textContent = '';\r
          return;\r
        }\r
        storyCaption.hidden = false;\r
        storyCaption.setAttribute('data-story-caption', step.relation);\r
        storyCaption.setAttribute('aria-live', playing ? 'off' : 'polite');\r
        storyCaptionIndex.textContent = (step.index + 1 < 10 ? '0' : '') + (step.index + 1) + ' / ' + (total < 10 ? '0' : '') + total;\r
        storyCaptionRoute.textContent = storyCaptionRouteCopy(step);\r
        storyCaptionDetail.textContent = storyCaptionDetailCopy(step);\r
        storyCaptionNext.hidden = !nextStep;\r
        storyCaptionNextLabel.textContent = nextStep\r
          ? ((nextStep.index + 1 < 10 ? '0' : '') + (nextStep.index + 1) + ' · ' + nextStep.nodeLabel)\r
          : '';\r
        storyCaption.style.animation = 'none';\r
        void storyCaption.offsetWidth;\r
        storyCaption.style.removeProperty('animation');\r
      }\r
\r
      function storyMomentLink() {\r
        var view = activeIndex >= 0 ? views[activeIndex] : null;\r
        var step = storyBeatIndex >= 0 ? storySteps[storyBeatIndex] : null;\r
        if (!view || !step) return '';\r
        var url = new URL(FlowBD.linkBase || location.href);\r
        url.searchParams.delete('play');\r
        url.hash = 'view=' + encodeURIComponent(view.id) + '&beat=' + encodeURIComponent(step.nodeId);\r
        return url.href;\r
      }\r
\r
      function fallbackCopyStoryMoment(value) {\r
        var field = document.createElement('textarea');\r
        field.value = value;\r
        field.setAttribute('readonly', '');\r
        field.style.position = 'fixed';\r
        field.style.opacity = '0';\r
        document.body.appendChild(field);\r
        field.select();\r
        var copied = false;\r
        try { copied = document.execCommand('copy'); } catch (_) {}\r
        field.remove();\r
        return copied;\r
      }\r
\r
      function resetBeatLinkFeedback() {\r
        if (beatLinkFeedbackTimer) clearTimeout(beatLinkFeedbackTimer);\r
        beatLinkFeedbackTimer = null;\r
        beatLink.removeAttribute('data-copy-state');\r
        beatLinkLabel.textContent = viewerText('viewer.guided.copyMoment');\r
      }\r
\r
      function syncBeatLink() {\r
        var step = storyBeatIndex >= 0 ? storySteps[storyBeatIndex] : null;\r
        var available = !!(activeIndex >= 0 && step && !currentHandoff);\r
        beatLink.disabled = !available;\r
        if (!beatLink.hasAttribute('data-copy-state')) beatLinkLabel.textContent = viewerText('viewer.guided.copyMoment');\r
        var description = available\r
          ? viewerText('viewer.guided.beatLink', { index: step.index + 1, total: storySteps.length, label: step.nodeLabel })\r
          : viewerText('viewer.guided.selectBeatLink');\r
        beatLink.setAttribute('aria-label', description);\r
        beatLink.title = description;\r
      }\r
\r
      function setBeatLinkFeedback(copied) {\r
        resetBeatLinkFeedback();\r
        beatLink.setAttribute('data-copy-state', copied ? 'copied' : 'failed');\r
        beatLinkLabel.textContent = viewerText(copied ? 'viewer.guided.copied' : 'viewer.guided.copyFailed');\r
        beatLink.setAttribute('aria-label', viewerText(copied ? 'viewer.guided.momentCopied' : 'viewer.guided.momentCopyFailed'));\r
        beatLinkFeedbackTimer = setTimeout(function () {\r
          resetBeatLinkFeedback();\r
          syncBeatLink();\r
        }, 1600);\r
      }\r
\r
      function copyStoryMomentLink() {\r
        if (playing) pausePlayback();\r
        var value = storyMomentLink();\r
        if (!value) return Promise.resolve(false);\r
        var copy = navigator.clipboard && typeof navigator.clipboard.writeText === 'function'\r
          ? navigator.clipboard.writeText(value).then(function () { return true; }).catch(function () { return fallbackCopyStoryMoment(value); })\r
          : Promise.resolve(fallbackCopyStoryMoment(value));\r
        return copy.then(function (copied) {\r
          setBeatLinkFeedback(copied);\r
          return copied;\r
        });\r
      }\r
\r
      function hashBeatMatchesCurrent() {\r
        var view = activeIndex >= 0 ? views[activeIndex] : null;\r
        var step = storyBeatIndex >= 0 ? storySteps[storyBeatIndex] : null;\r
        if (!view || !step) return false;\r
        try {\r
          var params = new URLSearchParams(location.hash.replace(/^#/, ''));\r
          return params.get('view') === view.id && params.get('beat') === step.nodeId;\r
        } catch (_) { return false; }\r
      }\r
\r
      function storyMotionAllowed() {\r
        if (document.hidden || reducedMotion()) return false;\r
        if (document.documentElement.getAttribute('data-motion') !== 'live') return false;\r
        if (document.documentElement.getAttribute('data-embed') === 'true' &&\r
            document.documentElement.getAttribute('data-share-playback') !== 'true') return false;\r
        if (window.matchMedia && window.matchMedia('print').matches) return false;\r
        return !(Archify.motionGovernor && Archify.motionGovernor.isPaused());\r
      }\r
\r
      function storyAutomaticPlaybackAllowed() {\r
        if (document.hidden || reducedMotion()) return false;\r
        if (window.matchMedia && window.matchMedia('print').matches) return false;\r
        if (Archify.motionGovernor && Archify.motionGovernor.capable) return !Archify.motionGovernor.isPaused();\r
        return true;\r
      }\r
\r
      function clearStoryPulse(options) {\r
        options = options || {};\r
        storyPulseGeneration += 1;\r
        Array.prototype.forEach.call(svg.querySelectorAll('.story-trail-flow[data-story-pulse]'), function (flow) {\r
          flow.removeAttribute('data-story-pulse');\r
        });\r
        Array.prototype.forEach.call(svg.querySelectorAll('[data-story-carrier-overlay]'), function (overlay) {\r
          overlay.remove();\r
        });\r
        if (storyPulseOwnerToken && options.release !== false && Archify.motionGovernor) {\r
          var token = storyPulseOwnerToken;\r
          storyPulseOwnerToken = 0;\r
          Archify.motionGovernor.release(token);\r
        } else if (options.release === false) storyPulseOwnerToken = 0;\r
      }\r
\r
      function pulseStoryStep(step) {\r
        clearStoryPulse();\r
        if (!step || (step.relation !== 'forward' && step.relation !== 'reverse') || step.edges.length !== 1 || !storyMotionAllowed()) return false;\r
        var flows = Array.prototype.slice.call(svg.querySelectorAll('.story-trail-flow[data-story-beat-step="' + step.index + '"]'));\r
        if (!flows.length) return false;\r
        var pulseGeneration = storyPulseGeneration;\r
        if (Archify.motionGovernor && Archify.motionGovernor.capable) {\r
          storyPulseOwnerToken = Archify.motionGovernor.claim('story', function () {\r
            clearStoryPulse({ release: false });\r
          });\r
        }\r
        flows.forEach(function (flow) { flow.setAttribute('data-story-pulse', 'true'); });\r
        if (Archify.flowTokens && typeof Archify.flowTokens.create === 'function') {\r
          var edge = step.edges[0];\r
          var shapes = storyGeometry(edge);\r
          var carrier = shapes.length ? Archify.flowTokens.create(edge, shapes[0], {\r
            className: 'story-flow-token',\r
            duration: '0.78s'\r
          }) : null;\r
          if (carrier) {\r
            var carrierOverlay = document.createElementNS('http://www.w3.org/2000/svg', 'g');\r
            var carrierWrapper = document.createElementNS('http://www.w3.org/2000/svg', 'g');\r
            carrierOverlay.setAttribute('class', 'story-carrier-overlay');\r
            carrierOverlay.setAttribute('data-story-carrier-overlay', '');\r
            carrierOverlay.setAttribute('aria-hidden', 'true');\r
            if (edge.hasAttribute('transform')) carrierWrapper.setAttribute('transform', edge.getAttribute('transform'));\r
            carrier.setAttribute('data-story-carrier-token', '');\r
            carrier.setAttribute('data-story-beat-step', String(step.index));\r
            carrierWrapper.appendChild(carrier);\r
            carrierOverlay.appendChild(carrierWrapper);\r
            var firstNode = svg.querySelector('[data-node-id]');\r
            while (firstNode && firstNode.parentNode !== svg) firstNode = firstNode.parentNode;\r
            if (firstNode) svg.insertBefore(carrierOverlay, firstNode);\r
            else svg.appendChild(carrierOverlay);\r
          }\r
        }\r
        void flows[0].getBoundingClientRect();\r
        flows[0].addEventListener('animationend', function () {\r
          if (pulseGeneration === storyPulseGeneration) clearStoryPulse();\r
        }, { once: true });\r
        return true;\r
      }\r
\r
      function stopStoryBeatTimer(options) {\r
        options = options || {};\r
        storyPlaybackGeneration += 1;\r
        if (storyBeatTimer && options.preserveElapsed === true && storyBeatStartedAt) {\r
          storyBeatElapsedMs = Math.min(storyBeatDwellMs, storyBeatElapsedMs + Math.max(0, Date.now() - storyBeatStartedAt));\r
        }\r
        if (storyBeatTimer) clearTimeout(storyBeatTimer);\r
        storyBeatTimer = null;\r
        storyBeatStartedAt = 0;\r
      }\r
\r
      function centerStoryStop(stop) {\r
        if (!stop || !trail) return false;\r
        var bounds = stop.getBoundingClientRect();\r
        var viewportLeft = trail.getBoundingClientRect().left + trail.clientLeft;\r
        var target = Math.max(0, trail.scrollLeft + bounds.left - viewportLeft - (trail.clientWidth - bounds.width) / 2);\r
        trail.scrollLeft = target;\r
        return true;\r
      }\r
\r
      function storyBeatDwell(total) {\r
        return Math.max(STORY_FOLLOW_MIN_DWELL_MS, VIEW_INTERVAL_MS / Math.max(1, total));\r
      }\r
\r
      function clearStoryFollow() {\r
        storyFollowGeneration += 1;\r
        svg.removeAttribute('data-story-follow');\r
        panel.removeAttribute('data-story-follow');\r
        panel.removeAttribute('data-story-follow-node');\r
      }\r
\r
      function storyFrameIds(step) {\r
        if (!step) return [];\r
        var ids = [];\r
        if (step.index > 0 && storySteps[step.index - 1]) ids.push(storySteps[step.index - 1].nodeId);\r
        ids.push(step.nodeId);\r
        if (step.index + 1 < storySteps.length) ids.push(storySteps[step.index + 1].nodeId);\r
        return ids;\r
      }\r
\r
      function followStoryStep(step, options) {\r
        options = options || {};\r
        if (!step || document.hidden) return false;\r
        if (!Archify.view || typeof Archify.view.reveal !== 'function') {\r
          var deferredIndex = step.index;\r
          var deferredGeneration = ++storyFollowGeneration;\r
          requestAnimationFrame(function () {\r
            if (deferredGeneration !== storyFollowGeneration || storyBeatIndex !== deferredIndex) return;\r
            if (Archify.view && typeof Archify.view.reveal === 'function') followStoryStep(step, options);\r
          });\r
          return true;\r
        }\r
        if (window.matchMedia && window.matchMedia('print').matches) return false;\r
        var embed = document.documentElement.getAttribute('data-embed') === 'true';\r
        var explicitEmbedPlayback = document.documentElement.getAttribute('data-share-playback') === 'true';\r
        if (embed && !explicitEmbedPlayback && options.linked !== true) return false;\r
        var ids = storyFrameIds(step);\r
        var generation = ++storyFollowGeneration;\r
        svg.setAttribute('data-story-follow', step.nodeId);\r
        panel.setAttribute('data-story-follow', 'moving');\r
        panel.setAttribute('data-story-follow-node', step.nodeId);\r
        var receipt = Archify.view.reveal(ids, {\r
          reason: options.manual === true ? 'story-beat' : 'story-follow',\r
          padding: 64,\r
          maxScale: 1.65,\r
          duration: STORY_FOLLOW_DURATION_MS,\r
          instant: options.instant === true || reducedMotion() || document.documentElement.getAttribute('data-motion') !== 'live'\r
        });\r
        if (receipt && receipt.finished && typeof receipt.finished.then === 'function') {\r
          receipt.finished.then(function (result) {\r
            if (generation !== storyFollowGeneration || storyBeatIndex !== step.index) return;\r
            svg.removeAttribute('data-story-follow');\r
            panel.setAttribute('data-story-follow', result && result.state === 'complete' ? 'settled' : 'interrupted');\r
          });\r
        } else if (generation === storyFollowGeneration) {\r
          panel.setAttribute('data-story-follow', 'settled');\r
        }\r
        return receipt;\r
      }\r
\r
      function setStoryBeat(index, options) {\r
        options = options || {};\r
        var stops = Array.prototype.slice.call(trail.querySelectorAll('[data-story-node]'));\r
        if (!stops.length) return false;\r
        resetBeatLinkFeedback();\r
        storyBeatIndex = Math.max(0, Math.min(stops.length - 1, index));\r
        var nextStep = storyBeatIndex + 1 < storySteps.length ? storySteps[storyBeatIndex + 1] : null;\r
        svg.setAttribute('data-story-beat', (storyBeatIndex + 1) + '/' + stops.length);\r
        panel.setAttribute('data-story-beat', (storyBeatIndex + 1) + '/' + stops.length);\r
        if (nextStep) {\r
          svg.setAttribute('data-story-next', nextStep.nodeId);\r
          panel.setAttribute('data-story-next', nextStep.nodeId);\r
        } else {\r
          svg.removeAttribute('data-story-next');\r
          panel.removeAttribute('data-story-next');\r
        }\r
        function storyBeatState(step) {\r
          if (step < storyBeatIndex) return 'past';\r
          if (step === storyBeatIndex) return 'active';\r
          if (step === storyBeatIndex + 1) return 'next';\r
          return 'pending';\r
        }\r
        Array.prototype.forEach.call(svg.querySelectorAll('[data-story-step]'), function (node) {\r
          var step = Number(node.getAttribute('data-story-step'));\r
          node.setAttribute('data-story-beat-state', storyBeatState(step));\r
        });\r
        Array.prototype.forEach.call(svg.querySelectorAll('[data-story-beat-step]'), function (edge) {\r
          var step = Number(edge.getAttribute('data-story-beat-step'));\r
          edge.setAttribute('data-story-beat-state', storyBeatState(step));\r
        });\r
        stops.forEach(function (stop, step) {\r
          stop.setAttribute('data-story-beat-state', storyBeatState(step));\r
          if (step === storyBeatIndex) stop.setAttribute('aria-current', 'step');\r
          else stop.removeAttribute('aria-current');\r
        });\r
        note.setAttribute('aria-live', 'off');\r
        note.textContent = storyBeatCopy(storySteps[storyBeatIndex], stops.length);\r
        renderStoryCaption(storySteps[storyBeatIndex], stops.length, nextStep);\r
        if (options.center === true) centerStoryStop(stops[storyBeatIndex]);\r
        if (options.pulse === true) pulseStoryStep(storySteps[storyBeatIndex]);\r
        else clearStoryPulse();\r
        if (options.follow === true) followStoryStep(storySteps[storyBeatIndex], {\r
          manual: options.manual === true,\r
          linked: options.linked === true,\r
          instant: options.followInstant === true\r
        });\r
        renderShareCue();\r
        syncBeatLink();\r
        return true;\r
      }\r
\r
      function settleStoryBeats() {\r
        stopStoryBeatTimer();\r
        clearStoryPulse();\r
        clearStoryFollow();\r
        resetBeatLinkFeedback();\r
        storyBeatIndex = -1;\r
        storyBeatElapsedMs = 0;\r
        storyBeatDwellMs = 0;\r
        svg.removeAttribute('data-story-beat');\r
        svg.removeAttribute('data-story-next');\r
        panel.removeAttribute('data-story-beat');\r
        panel.removeAttribute('data-story-next');\r
        Array.prototype.forEach.call(svg.querySelectorAll('[data-story-beat-state]'), function (el) {\r
          el.removeAttribute('data-story-beat-state');\r
        });\r
        Array.prototype.forEach.call(trail.querySelectorAll('[data-story-beat-state]'), function (stop) {\r
          stop.removeAttribute('data-story-beat-state');\r
          stop.removeAttribute('aria-current');\r
        });\r
        note.setAttribute('aria-live', 'polite');\r
        if (activeIndex >= 0) note.textContent = views[activeIndex].note || viewerText('viewer.guided.chapter.selectedNodes', { count: views[activeIndex].focus.length });\r
        renderStoryCaption(null, 0);\r
        renderShareCue();\r
        syncBeatLink();\r
      }\r
\r
      function clearStoryTrail() {\r
        stopStoryBeatTimer();\r
        clearStoryPulse();\r
        clearStoryFollow();\r
        resetBeatLinkFeedback();\r
        storyBeatIndex = -1;\r
        storyBeatElapsedMs = 0;\r
        storyBeatDwellMs = 0;\r
        storySteps = [];\r
        svg.removeAttribute('data-story-active');\r
        svg.removeAttribute('data-story-playing');\r
        svg.removeAttribute('data-story-beat');\r
        svg.removeAttribute('data-story-next');\r
        panel.removeAttribute('data-story-beat');\r
        panel.removeAttribute('data-story-next');\r
        Array.prototype.forEach.call(svg.querySelectorAll('[data-story-overlay]'), function (overlay) {\r
          overlay.remove();\r
        });\r
        Array.prototype.forEach.call(svg.querySelectorAll('[data-story-step], [data-story-beat-state]'), function (node) {\r
          node.removeAttribute('data-story-step');\r
          node.removeAttribute('data-story-beat-state');\r
          node.style.removeProperty('--story-step');\r
        });\r
        Array.prototype.forEach.call(svg.querySelectorAll('[data-edge-from][data-story-beat-step]'), function (edge) {\r
          edge.removeAttribute('data-story-beat-step');\r
          edge.removeAttribute('data-story-beat-state');\r
        });\r
        trail.textContent = '';\r
        trail.hidden = true;\r
        trail.removeAttribute('aria-label');\r
        renderStoryCaption(null, 0);\r
        syncBeatLink();\r
      }\r
\r
      function storyGeometry(edge) {\r
        if (/^(path|line|polyline)$/i.test(edge.tagName)) return [edge];\r
        return Array.prototype.slice.call(edge.querySelectorAll('path, line, polyline'));\r
      }\r
\r
      function renderStoryTrail(view) {\r
        if (Archify.semanticLens && typeof Archify.semanticLens.clearPreview === 'function') Archify.semanticLens.clearPreview();\r
        clearStoryTrail();\r
        if (!view) return;\r
\r
        var nodeList = Array.prototype.slice.call(svg.querySelectorAll('[data-node-id]'));\r
        var edgeList = Array.prototype.slice.call(svg.querySelectorAll('[data-edge-from][data-edge-to]'));\r
        var byId = Object.create(null);\r
        nodeList.forEach(function (node) { byId[node.getAttribute('data-node-id')] = node; });\r
        storySteps = view.focus.map(function (_, index) { return storyStep(view, index, edgeList, byId); });\r
        var labels = [];\r
        storySteps.forEach(function (step, index) {\r
          var id = step.nodeId;\r
          var node = byId[id];\r
          if (!node) return;\r
          node.setAttribute('data-story-step', String(index));\r
          node.style.setProperty('--story-step', String(index));\r
          var nodeLabel = step.nodeLabel;\r
          labels.push(nodeLabel);\r
          var stop = document.createElement('button');\r
          stop.type = 'button';\r
          stop.className = 'guided-view-stop';\r
          stop.setAttribute('data-story-node', id);\r
          stop.setAttribute('data-story-index', String(index));\r
          stop.setAttribute('data-story-relation', step.relation);\r
          stop.setAttribute('data-story-number', (index + 1 < 10 ? '0' : '') + (index + 1));\r
          if (index > 0) stop.setAttribute('data-story-link', step.relation);\r
          stop.style.setProperty('--story-step', String(index));\r
          stop.setAttribute('aria-label', storyBeatAria(step, storySteps.length));\r
          stop.title = storyBeatCopy(step, storySteps.length);\r
          stop.textContent = nodeLabel;\r
          trail.appendChild(stop);\r
        });\r
        trail.hidden = labels.length === 0;\r
        trail.setAttribute('aria-label', viewerText('viewer.guided.storyTrail', { label: view.label, count: labels.length }));\r
        trail.scrollLeft = 0;\r
        svg.setAttribute('data-story-active', view.id);\r
\r
        var overlay = document.createElementNS('http://www.w3.org/2000/svg', 'g');\r
        overlay.setAttribute('class', 'story-trail-overlay');\r
        overlay.setAttribute('data-story-overlay', '');\r
        overlay.setAttribute('aria-hidden', 'true');\r
        var copied = 0;\r
        storySteps.forEach(function (step) {\r
          step.edges.forEach(function (edge) {\r
            var edgeBeat = step.index;\r
            edge.setAttribute('data-story-beat-step', String(edgeBeat));\r
            var wrapper = document.createElementNS('http://www.w3.org/2000/svg', 'g');\r
            if (edge.hasAttribute('transform')) wrapper.setAttribute('transform', edge.getAttribute('transform'));\r
            storyGeometry(edge).forEach(function (shape) {\r
              var clone = shape.cloneNode(false);\r
              clone.removeAttribute('id');\r
              clone.removeAttribute('marker-start');\r
              clone.removeAttribute('marker-mid');\r
              clone.removeAttribute('marker-end');\r
              clone.removeAttribute('aria-label');\r
              clone.removeAttribute('role');\r
              clone.removeAttribute('data-animate');\r
              clone.removeAttribute('data-edge-from');\r
              clone.removeAttribute('data-edge-to');\r
              clone.removeAttribute('data-edge-key');\r
              clone.removeAttribute('data-edge-id');\r
              clone.removeAttribute('data-edge-label');\r
              clone.setAttribute('class', 'story-trail-flow');\r
              clone.setAttribute('data-story-beat-step', String(edgeBeat));\r
              clone.style.setProperty('--story-step', String(edgeBeat));\r
              wrapper.appendChild(clone);\r
              copied += 1;\r
            });\r
            if (wrapper.childNodes.length) overlay.appendChild(wrapper);\r
          });\r
        });\r
        if (copied) {\r
          var firstEdge = edgeList[0];\r
          if (firstEdge && firstEdge.parentNode) firstEdge.parentNode.insertBefore(overlay, firstEdge);\r
          else svg.insertBefore(overlay, svg.firstChild);\r
        }\r
      }\r
\r
      function syncStoryPlayback() {\r
        var shouldPlay = playing && activeIndex >= 0;\r
        if (shouldPlay && svg.getAttribute('data-story-playing') !== 'true') svg.setAttribute('data-story-playing', 'true');\r
        else if (!shouldPlay && svg.hasAttribute('data-story-playing')) svg.removeAttribute('data-story-playing');\r
      }\r
\r
      function resetProgress(fraction) {\r
        fraction = Math.max(0, Math.min(1, Number(fraction) || 0));\r
        progressBar.style.animation = 'none';\r
        progressBar.style.setProperty('--guided-progress-start', String(fraction));\r
        progressBar.style.transform = 'scaleX(' + fraction + ')';\r
      }\r
\r
      function startProgress(fraction, duration) {\r
        resetProgress(fraction);\r
        void progressBar.offsetWidth;\r
        progressBar.style.animation = 'archify-guided-progress ' + Math.max(1, duration || VIEW_INTERVAL_MS) + 'ms linear forwards';\r
      }\r
\r
      function currentStoryProgress() {\r
        var total = storySteps.length;\r
        if (!total || storyBeatIndex < 0) return 0;\r
        var elapsed = storyBeatElapsedMs;\r
        if (playing && storyBeatTimer && storyBeatStartedAt) elapsed += Math.max(0, Date.now() - storyBeatStartedAt);\r
        var dwell = storyBeatDwellMs || storyBeatDwell(total);\r
        return Math.max(0, Math.min(1, (storyBeatIndex + Math.min(1, elapsed / dwell)) / total));\r
      }\r
\r
      function renderPlayback() {\r
        var automaticPlaybackAllowed = storyAutomaticPlaybackAllowed();\r
        panel.setAttribute('data-playing', playing ? 'true' : 'false');\r
        syncStoryPlayback();\r
        play.disabled = !playing && !automaticPlaybackAllowed;\r
        play.setAttribute('aria-pressed', playing ? 'true' : 'false');\r
        play.setAttribute('aria-label', viewerText(playing\r
          ? 'viewer.guided.pause'\r
          : !automaticPlaybackAllowed\r
            ? 'viewer.guided.motionUnavailable'\r
            : storyPlaybackComplete\r
              ? 'viewer.guided.replay'\r
              : 'viewer.guided.play'));\r
        play.title = viewerText(playing\r
          ? 'viewer.guided.pause.title'\r
          : !automaticPlaybackAllowed\r
            ? 'viewer.guided.enableMotion'\r
            : storyPlaybackComplete\r
              ? 'viewer.guided.replay.title'\r
              : 'viewer.guided.play.title');\r
        playIcon.textContent = playing ? '\\u2016' : '\\u25b6';\r
        playLabel.textContent = viewerText(playing\r
          ? 'viewer.guided.pauseStory'\r
          : storyPlaybackComplete\r
            ? 'viewer.guided.replayStory'\r
            : 'viewer.guided.playStory');\r
        if (storyCaption && !storyCaption.hidden) storyCaption.setAttribute('aria-live', playing ? 'off' : 'polite');\r
      }\r
\r
      function render() {\r
        var view = views[activeIndex];\r
        count.textContent = activeIndex < 0 ? '0 / ' + views.length : (activeIndex + 1) + ' / ' + views.length;\r
        label.textContent = view ? view.label : viewerText('viewer.guided.explore');\r
        note.setAttribute('aria-live', storyBeatIndex >= 0 ? 'off' : 'polite');\r
        note.textContent = storyBeatIndex >= 0\r
          ? storyBeatCopy(storySteps[storyBeatIndex], storySteps.length)\r
          : (view\r
            ? (view.note || viewerText('viewer.guided.chapter.selectedNodes', { count: view.focus.length }))\r
            : viewerText('viewer.guided.intro'));\r
        prev.disabled = activeIndex < 0;\r
        next.disabled = activeIndex >= views.length - 1;\r
        all.disabled = activeIndex < 0;\r
        panel.setAttribute('data-active-view', view ? view.id : 'all');\r
        syncChapterIndex();\r
        renderShareCue();\r
        renderPlayback();\r
        syncBeatLink();\r
      }\r
\r
      function pausePlayback(options) {\r
        options = options || {};\r
        var progress = options.complete === true ? 1 : currentStoryProgress();\r
        if (panel.getAttribute('data-autoplay') === 'playing') {\r
          setShareCueProgress(progress);\r
          setAutoplayState(options.complete === true ? 'complete' : 'interrupted');\r
        }\r
        stopStoryBeatTimer({ preserveElapsed: options.complete !== true });\r
        clearStoryPulse();\r
        clearStoryFollow();\r
        playing = false;\r
        storyPlaybackComplete = options.complete === true;\r
        resetProgress(progress);\r
        renderPlayback();\r
        renderShareCue();\r
      }\r
\r
      function finishStoryChapter() {\r
        if (!playing) return false;\r
        if (storyPlaybackScope === 'chapter') {\r
          pausePlayback({ complete: true });\r
          return true;\r
        }\r
        if (activeIndex < views.length - 1) {\r
          var destinationIndex = activeIndex + 1;\r
          activate(destinationIndex, { playback: true });\r
          afterHandoff(function () {\r
            if (!playing || activeIndex !== destinationIndex) return;\r
            storyBeatElapsedMs = 0;\r
            setStoryBeat(0, { pulse: true, follow: true });\r
            scheduleStoryPlayback();\r
          });\r
          return true;\r
        }\r
        pausePlayback({ complete: true });\r
        return true;\r
      }\r
\r
      function scheduleStoryPlayback() {\r
        var total = storySteps.length;\r
        if (!playing || !total || reducedMotion()) {\r
          if (playing) pausePlayback();\r
          return false;\r
        }\r
        storyBeatDwellMs = storyBeatDwell(total);\r
        if (storyBeatIndex < 0) {\r
          storyBeatElapsedMs = 0;\r
          setStoryBeat(0, { pulse: true, follow: true });\r
        }\r
        storyBeatElapsedMs = Math.max(0, Math.min(storyBeatDwellMs, storyBeatElapsedMs));\r
        var remainingDwell = Math.max(1, storyBeatDwellMs - storyBeatElapsedMs);\r
        var progress = (storyBeatIndex + storyBeatElapsedMs / storyBeatDwellMs) / total;\r
        var remainingChapter = remainingDwell + Math.max(0, total - storyBeatIndex - 1) * storyBeatDwellMs;\r
        startProgress(progress, remainingChapter);\r
        if (panel.getAttribute('data-autoplay') === 'playing') startShareCueProgress(progress, remainingChapter);\r
        var generation = ++storyPlaybackGeneration;\r
        storyBeatStartedAt = Date.now();\r
        storyBeatTimer = setTimeout(function () {\r
          if (!playing || generation !== storyPlaybackGeneration) return;\r
          storyBeatTimer = null;\r
          storyBeatStartedAt = 0;\r
          storyBeatElapsedMs = 0;\r
          if (storyBeatIndex < total - 1) {\r
            setStoryBeat(storyBeatIndex + 1, { pulse: true, follow: true });\r
            scheduleStoryPlayback();\r
          } else finishStoryChapter();\r
        }, remainingDwell);\r
        return true;\r
      }\r
\r
      function startPlayback() {\r
        if (!storyAutomaticPlaybackAllowed()) {\r
          renderPlayback();\r
          return false;\r
        }\r
        autoplayPending = false;\r
        setAutoplayState(null);\r
        setShareCueProgress(0);\r
        document.documentElement.removeAttribute('data-share-playback');\r
        storyPlaybackScope = 'story';\r
        if (storyPlaybackComplete) showAll({ updateUrl: false });\r
        storyPlaybackComplete = false;\r
        if (activeIndex < 0) activate(0, { playback: true });\r
        playing = true;\r
        renderPlayback();\r
        afterHandoff(function () {\r
          if (!playing) return;\r
          if (storyBeatIndex >= 0) followStoryStep(storySteps[storyBeatIndex]);\r
          scheduleStoryPlayback();\r
        });\r
        return true;\r
      }\r
\r
      function startCurrentViewPlayback() {\r
        if (document.hidden) return false;\r
        autoplayPending = false;\r
        document.documentElement.setAttribute('data-share-playback', 'true');\r
        storyPlaybackScope = 'chapter';\r
        storyPlaybackComplete = false;\r
        if (activeIndex < 0) activate(0, { playback: true, updateUrl: false });\r
        if (!storyAutomaticPlaybackAllowed()) {\r
          var preserveMoment = hashBeatMatchesCurrent();\r
          setShareCueProgress(preserveMoment && storySteps.length ? (storyBeatIndex + 1) / storySteps.length : 1);\r
          setAutoplayState('reduced-motion');\r
          playing = false;\r
          if (preserveMoment) {\r
            clearStoryPulse();\r
            renderShareCue();\r
          } else settleStoryBeats();\r
          renderPlayback();\r
          return false;\r
        }\r
        playing = true;\r
        setAutoplayState('playing');\r
        renderPlayback();\r
        afterHandoff(function () {\r
          if (!playing) return;\r
          if (storyBeatIndex >= 0) followStoryStep(storySteps[storyBeatIndex]);\r
          scheduleStoryPlayback();\r
        });\r
        return true;\r
      }\r
\r
      function maybeStartSharePlayback() {\r
        if (!autoplayPending || document.hidden) return false;\r
        return startCurrentViewPlayback();\r
      }\r
\r
      function togglePlayback() {\r
        return playing ? (pausePlayback(), false) : startPlayback();\r
      }\r
\r
      function syncStoryControlsDisabled() {\r
        Array.prototype.forEach.call(trail.querySelectorAll('[data-story-node]'), function (stop) {\r
          stop.disabled = !!currentHandoff;\r
        });\r
        syncBeatLink();\r
      }\r
\r
      function selectStoryBeat(index) {\r
        if (currentHandoff || activeIndex < 0 || index < 0 || index >= storySteps.length) return false;\r
        momentRestoreGeneration += 1;\r
        clearChapterPreview({ clearIntents: true });\r
        if (playing) pausePlayback();\r
        else {\r
          stopStoryBeatTimer();\r
          clearStoryPulse();\r
        }\r
        storyPlaybackComplete = false;\r
        storyPlaybackScope = 'story';\r
        storyBeatElapsedMs = 0;\r
        storyBeatDwellMs = storyBeatDwell(storySteps.length);\r
        var view = views[activeIndex];\r
        Archify.focus.setMany(view.focus, {\r
          toggle: false,\r
          updateUrl: false,\r
          mode: 'selection',\r
          label: view.label,\r
          hideChip: true\r
        });\r
        setStoryBeat(index, { manual: true, center: true, pulse: true, follow: true });\r
        resetProgress(index / storySteps.length);\r
        renderPlayback();\r
        return true;\r
      }\r
\r
      function selectStoryBeatById(id, options) {\r
        options = options || {};\r
        var index = storySteps.findIndex(function (step) { return step.nodeId === id; });\r
        if (index < 0) return false;\r
        if (playing) pausePlayback();\r
        else {\r
          stopStoryBeatTimer();\r
          clearStoryPulse();\r
        }\r
        storyPlaybackComplete = false;\r
        storyPlaybackScope = 'story';\r
        storyBeatElapsedMs = 0;\r
        storyBeatDwellMs = storyBeatDwell(storySteps.length);\r
        setStoryBeat(index, {\r
          manual: false,\r
          center: true,\r
          pulse: false,\r
          follow: options.follow === true,\r
          linked: options.linked === true,\r
          followInstant: options.followInstant === true\r
        });\r
        resetProgress(index / storySteps.length);\r
        renderPlayback();\r
        return true;\r
      }\r
\r
      function updateUrl(view) {\r
        try {\r
          history.replaceState(null, '', location.pathname + location.search + (view ? '#view=' + encodeURIComponent(view.id) : ''));\r
        } catch (_) {}\r
      }\r
\r
      function showAll(options) {\r
        options = options || {};\r
        if (options.restore !== true) momentRestoreGeneration += 1;\r
        clearChapterPreview({ clearIntents: true });\r
        if (playing && options.playback !== true) pausePlayback();\r
        if (options.playback !== true) storyPlaybackComplete = false;\r
        cancelHandoff('overview');\r
        activeIndex = -1;\r
        renderStoryTrail(null);\r
        if (options.clearFocus !== false) Archify.focus.clear({ updateUrl: false });\r
        if (options.resetView !== false && Archify.view && typeof Archify.view.reset === 'function') {\r
          Archify.view.reset({ automatic: true });\r
        }\r
        render();\r
        if (options.updateUrl !== false) updateUrl(null);\r
      }\r
\r
      function activate(index, options) {\r
        options = options || {};\r
        if (options.restore !== true) momentRestoreGeneration += 1;\r
        if (playing && options.playback !== true) pausePlayback();\r
        if (options.playback !== true) storyPlaybackComplete = false;\r
        if (index < 0) { showAll(options); return true; }\r
        if (index >= views.length) return false;\r
        clearChapterPreview({ clearIntents: true });\r
        var previousIndex = activeIndex;\r
        var previous = previousIndex >= 0 ? views[previousIndex] : null;\r
        var outgoingBeatIndex = storyBeatIndex;\r
        cancelHandoff('replaced');\r
        activeIndex = index;\r
        var view = views[index];\r
        Archify.focus.setMany(view.focus, {\r
          toggle: false,\r
          updateUrl: false,\r
          mode: 'selection',\r
          label: view.label,\r
          hideChip: true\r
        });\r
        renderStoryTrail(view);\r
        beginHandoff(previousIndex, index, previous, view, outgoingBeatIndex, options.playback === true ? 'playback' : 'guided');\r
        syncStoryControlsDisabled();\r
        render();\r
        if (options.updateUrl !== false) updateUrl(view);\r
        return true;\r
      }\r
\r
      function activateById(id, options) {\r
        var index = views.findIndex(function (view) { return view.id === id; });\r
        return index >= 0 && activate(index, options);\r
      }\r
\r
      prev.addEventListener('click', function () { activate(activeIndex - 1); });\r
      next.addEventListener('click', function () { activate(activeIndex + 1); });\r
      all.addEventListener('click', function () { showAll(); });\r
      play.addEventListener('click', togglePlayback);\r
      beatLink.addEventListener('click', copyStoryMomentLink);\r
      trail.addEventListener('focusin', function (event) {\r
        if (!event.target.closest('[data-story-node]')) return;\r
        if (playing) pausePlayback();\r
      });\r
      trail.addEventListener('click', function (event) {\r
        var stop = event.target.closest('[data-story-node]');\r
        if (!stop || stop.disabled) return;\r
        selectStoryBeat(Number(stop.getAttribute('data-story-index')));\r
      });\r
      trail.addEventListener('keydown', function (event) {\r
        if (event.key !== 'Enter' && event.key !== ' ') return;\r
        var stop = event.target.closest('[data-story-node]');\r
        if (!stop || stop.disabled) return;\r
        event.preventDefault();\r
        selectStoryBeat(Number(stop.getAttribute('data-story-index')));\r
      });\r
      chapterList.addEventListener('click', function (event) {\r
        var button = event.target.closest('[data-guided-view-id]');\r
        if (!button) return;\r
        activateById(button.getAttribute('data-guided-view-id'));\r
      });\r
      chapterList.addEventListener('pointerover', function (event) {\r
        var button = event.target.closest('[data-guided-view-id]');\r
        if (!button || !hoverCapable() || event.pointerType === 'touch') return;\r
        if (event.relatedTarget && button.contains(event.relatedTarget)) return;\r
        setChapterPreviewIntent('pointer', chapterButtons.indexOf(button));\r
      });\r
      chapterList.addEventListener('pointerout', function (event) {\r
        var button = event.target.closest('[data-guided-view-id]');\r
        if (!button || (event.relatedTarget && button.contains(event.relatedTarget))) return;\r
        clearChapterPreviewIntent('pointer', chapterButtons.indexOf(button));\r
      });\r
      chapterIndex.addEventListener('focusin', function (event) {\r
        var button = event.target.closest('[data-guided-view-id]');\r
        if (!button) return;\r
        setChapterPreviewIntent('focus', chapterButtons.indexOf(button));\r
      });\r
      chapterIndex.addEventListener('focusout', function (event) {\r
        var button = event.target.closest('[data-guided-view-id]');\r
        if (!button || (event.relatedTarget && button.contains(event.relatedTarget))) return;\r
        clearChapterPreviewIntent('focus', chapterButtons.indexOf(button));\r
      });\r
      chapterList.addEventListener('keydown', function (event) {\r
        var button = event.target.closest('[data-guided-view-id]');\r
        var index = chapterButtons.indexOf(button);\r
        if (index < 0) return;\r
        var target = null;\r
        if (event.key === 'ArrowRight') target = Math.min(chapterButtons.length - 1, index + 1);\r
        else if (event.key === 'ArrowLeft') target = Math.max(0, index - 1);\r
        else if (event.key === 'Home') target = 0;\r
        else if (event.key === 'End') target = chapterButtons.length - 1;\r
        if (target === null) return;\r
        event.preventDefault();\r
        focusChapterButton(target);\r
      });\r
\r
      // A direct node exploration supersedes the curated view. Capture phase\r
      // releases the view before the focus explorer writes its own deep link.\r
      function releaseForNode(event) {\r
        if (activeIndex >= 0 && event.target.closest('[data-node-id]')) {\r
          pausePlayback();\r
          showAll({ clearFocus: false, updateUrl: false });\r
        }\r
      }\r
      svg.addEventListener('click', releaseForNode, true);\r
      svg.addEventListener('keydown', function (event) {\r
        if (event.key === 'Enter' || event.key === ' ') releaseForNode(event);\r
      }, true);\r
\r
      document.addEventListener('keydown', function (event) {\r
        if (event.metaKey || event.ctrlKey || event.altKey) return;\r
        if (document.documentElement.getAttribute('data-guide-open') === 'true') return;\r
        var target = event.target;\r
        if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable)) return;\r
        if (event.key === ']') {\r
          event.preventDefault();\r
          if (activeIndex < views.length - 1) activate(activeIndex + 1);\r
        } else if (event.key === '[') {\r
          event.preventDefault();\r
          if (activeIndex >= 0) activate(activeIndex - 1);\r
        } else if (event.key.toLowerCase() === 'p') {\r
          event.preventDefault();\r
          togglePlayback();\r
        } else if (event.key === 'Escape' && activePreviewIndex >= 0) {\r
          event.preventDefault();\r
          event.stopImmediatePropagation();\r
          clearChapterPreview({ clearIntents: true });\r
        } else if (event.key === 'Escape' && activeIndex >= 0) {\r
          event.preventDefault();\r
          showAll();\r
        }\r
      }, true);\r
\r
      function syncViewFromHash() {\r
        try {\r
          var params = new URLSearchParams(location.hash.replace(/^#/, ''));\r
          var initial = params.get('view');\r
          var requestedBeat = params.get('beat');\r
          var restoreGeneration = ++momentRestoreGeneration;\r
          if (initial) {\r
            var activated = activateById(initial, { updateUrl: false, restore: true });\r
            if (!activated) {\r
              showAll({ updateUrl: false, restore: true });\r
              return;\r
            }\r
            if (requestedBeat) afterHandoff(function () {\r
              if (restoreGeneration !== momentRestoreGeneration) return;\r
              var latest = new URLSearchParams(location.hash.replace(/^#/, ''));\r
              if (latest.get('view') !== initial || latest.get('beat') !== requestedBeat) return;\r
              if (activeIndex < 0 || views[activeIndex].id !== initial) return;\r
              selectStoryBeatById(requestedBeat, { linked: true, follow: true, followInstant: true });\r
            });\r
          } else if (params.get('focus') || params.get('relation')) {\r
            activeIndex = -1;\r
            render();\r
          } else {\r
            showAll({ updateUrl: false, restore: true });\r
          }\r
        } catch (_) { showAll({ updateUrl: false, restore: true }); }\r
      }\r
\r
      window.addEventListener('hashchange', syncViewFromHash);\r
      document.addEventListener('visibilitychange', function () {\r
        if (document.hidden) {\r
          clearChapterPreview({ clearIntents: true });\r
          if (playing) pausePlayback();\r
          else clearStoryPulse();\r
          settleHandoff('hidden');\r
        }\r
        else if (!document.hidden) maybeStartSharePlayback();\r
      });\r
      if (window.matchMedia) {\r
        var guidedMotionQuery = window.matchMedia('(prefers-reduced-motion: reduce)');\r
        var onGuidedMotionChange = function () {\r
          if (guidedMotionQuery.matches) {\r
            if (playing) pausePlayback();\r
            else clearStoryPulse();\r
            settleHandoff('reduced-motion');\r
          }\r
        };\r
        if (typeof guidedMotionQuery.addEventListener === 'function') guidedMotionQuery.addEventListener('change', onGuidedMotionChange);\r
        else if (typeof guidedMotionQuery.addListener === 'function') guidedMotionQuery.addListener(onGuidedMotionChange);\r
      }\r
      if (document.documentElement.getAttribute('data-embed') !== 'true' && typeof MutationObserver !== 'undefined' && typeof Node !== 'undefined' && svg instanceof Node && document.documentElement instanceof Node) {\r
        var chapterPreviewOwnerObserver = new MutationObserver(syncChapterPreview);\r
        chapterPreviewOwnerObserver.observe(svg, {\r
          attributes: true,\r
          attributeFilter: [\r
            'data-route-picking', 'data-route-active', 'data-lens-active',\r
            'data-legend-preview-active', 'data-relationship-preview-active',\r
            'data-intent-trace-active', 'data-focus-active'\r
          ]\r
        });\r
        var storyMotionObserver = new MutationObserver(function () {\r
          if (document.documentElement.getAttribute('data-motion') !== 'live') clearStoryPulse();\r
          renderPlayback();\r
        });\r
        storyMotionObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['data-motion'] });\r
      }\r
      if (typeof ResizeObserver === 'function') {\r
        var chapterViewportWidth = chapterList.clientWidth;\r
        var trailViewportWidth = trail.clientWidth;\r
        var storyScrollObserver = new ResizeObserver(function () {\r
          var chapterWidth = chapterList.clientWidth;\r
          var trailWidth = trail.clientWidth;\r
          if (chapterWidth !== chapterViewportWidth && activeIndex >= 0) centerChapterButton(chapterButtons[activeIndex]);\r
          if (trailWidth !== trailViewportWidth && storyBeatIndex >= 0) {\r
            centerStoryStop(trail.querySelectorAll('[data-story-node]')[storyBeatIndex]);\r
          }\r
          chapterViewportWidth = chapterWidth;\r
          trailViewportWidth = trailWidth;\r
        });\r
        storyScrollObserver.observe(chapterList);\r
        storyScrollObserver.observe(trail);\r
      }\r
      window.addEventListener('beforeprint', function () {\r
        clearChapterPreview({ clearIntents: true });\r
        if (playing) pausePlayback();\r
        else clearStoryPulse();\r
        settleHandoff('print');\r
      });\r
      syncViewFromHash();\r
      if (autoplayPending) {\r
        requestAnimationFrame(function () {\r
          requestAnimationFrame(maybeStartSharePlayback);\r
        });\r
      }\r
\r
      return {\r
        count: views.length,\r
        activate: activateById,\r
        showAll: showAll,\r
        play: startPlayback,\r
        playCurrent: startCurrentViewPlayback,\r
        pause: pausePlayback,\r
        beatLink: storyMomentLink,\r
        copyBeatLink: copyStoryMomentLink,\r
        cancelHandoff: cancelHandoff,\r
        settleHandoff: settleHandoff,\r
        clearPreview: function () { return clearChapterPreview({ clearIntents: true }); },\r
        isPlaying: function () { return playing; },\r
        handoff: function () {\r
          return currentHandoff ? { id: currentHandoff.id, mode: currentHandoff.mode, anchor: currentHandoff.anchor || null } : null;\r
        },\r
        active: function () { return activeIndex < 0 ? null : views[activeIndex].id; },\r
        preview: function () { return activePreviewIndex < 0 ? null : views[activePreviewIndex].id; },\r
        delta: function (id) {\r
          var index = views.findIndex(function (view) { return view.id === id; });\r
          if (index < 0) return null;\r
          var value = chapterDelta(activeIndex >= 0 ? views[activeIndex] : null, views[index]);\r
          return { stay: value.stay.slice(), enter: value.enter.slice(), leave: value.leave.slice() };\r
        },\r
        beat: function () {\r
          var step = storyBeatIndex >= 0 ? storySteps[storyBeatIndex] : null;\r
          return step ? {\r
            index: step.index,\r
            position: step.index + 1,\r
            total: storySteps.length,\r
            nodeId: step.nodeId,\r
            relation: step.relation,\r
            edgeKeys: step.edgeKeys.slice()\r
          } : null;\r
        },\r
        focus: function () { return activeIndex < 0 ? [] : views[activeIndex].focus.slice(); }\r
      };\r
    })();\r
\r
    /* ============================================================\r
       Adaptive Reader Shell — one diagram across laptop and monitor.\r
       The canonical SVG and viewBox never change. On ordinary desktop pages,\r
       wide diagrams receive only enough outer width to use the available\r
       height without pushing summary cards below the viewport. Mobile,\r
       embed, presentation, print, and non-wide diagrams retain their own\r
       established layout contracts.\r
       ============================================================ */\r
    Archify.waitForStableLayout = function (options) {\r
      options = options || {};\r
      var maximumFrames = Math.max(1, Number(options.maximumFrames) || 240);\r
      var fontsReady = document.fonts && document.fonts.ready\r
        ? document.fonts.ready.catch(function () {})\r
        : Promise.resolve();\r
      return fontsReady.then(function () {\r
        if (typeof options.schedule === 'function') options.schedule();\r
        return new Promise(function (resolve, reject) {\r
          var previous = '';\r
          var stableFrames = 0;\r
          var sampledFrames = 0;\r
          function sample() {\r
            sampledFrames += 1;\r
            if (typeof options.pending === 'function' && options.pending()) {\r
              previous = '';\r
              stableFrames = 0;\r
            } else {\r
              var current = typeof options.snapshot === 'function' ? options.snapshot() : '';\r
              if (current === previous) stableFrames += 1;\r
              else {\r
                previous = current;\r
                stableFrames = 0;\r
              }\r
              if (stableFrames >= 3) {\r
                resolve({ stable: true, snapshot: current, sampledFrames: sampledFrames });\r
                return;\r
              }\r
            }\r
            if (sampledFrames >= maximumFrames) {\r
              reject(new Error(options.timeoutMessage || 'Layout did not reach stable dimensions.'));\r
              return;\r
            }\r
            requestAnimationFrame(sample);\r
          }\r
          requestAnimationFrame(sample);\r
        });\r
      });\r
    };\r
\r
    Archify.readerLayout = (function () {\r
      var html = document.documentElement;\r
      var body = document.body;\r
      var shell = document.querySelector('.container');\r
      var diagram = document.querySelector('.diagram-container');\r
      var svg = diagram && diagram.querySelector(':scope > svg');\r
      var header = shell && shell.querySelector('.header');\r
      var guided = shell && shell.querySelector('.guided-views');\r
      var cards = shell && shell.querySelector('.cards');\r
      var viewBox = svg && svg.viewBox && svg.viewBox.baseVal;\r
      var ratio = viewBox && viewBox.height > 0 ? viewBox.width / viewBox.height : 0;\r
      var frame = 0;\r
      var settleFrame = 0;\r
      var lastWidth = 0;\r
      var WIDE_RATIO = 1.55;\r
      var MIN_DESKTOP_WIDTH = 1024;\r
      var MIN_READER_WIDTH = 960;\r
      var MAX_READER_WIDTH = 1920;\r
      var SAFE_BOTTOM_GAP = 12;\r
\r
      if (diagram && ratio >= WIDE_RATIO) {\r
        diagram.setAttribute('data-wide-diagram', 'true');\r
        html.setAttribute('data-diagram-shape', 'wide');\r
      }\r
\r
      function number(value) {\r
        var parsed = parseFloat(value);\r
        return Number.isFinite(parsed) ? parsed : 0;\r
      }\r
      function visible(element) {\r
        return Boolean(element && !element.hidden && window.getComputedStyle(element).display !== 'none');\r
      }\r
      function outerHeight(element) {\r
        if (!visible(element)) return 0;\r
        var style = window.getComputedStyle(element);\r
        return element.getBoundingClientRect().height + number(style.marginTop) + number(style.marginBottom);\r
      }\r
      function eligible() {\r
        return Boolean(\r
          shell && diagram && svg && ratio >= WIDE_RATIO &&\r
          window.innerWidth >= MIN_DESKTOP_WIDTH &&\r
          html.getAttribute('data-embed') !== 'true' &&\r
          html.getAttribute('data-present') !== 'true' &&\r
          (!window.matchMedia || !window.matchMedia('print').matches)\r
        );\r
      }\r
      function clear() {\r
        html.style.removeProperty('--archify-reader-width');\r
        html.removeAttribute('data-reader-layout');\r
        html.removeAttribute('data-reader-overflow');\r
        lastWidth = 0;\r
      }\r
      function chromeMetrics() {\r
        var bodyStyle = window.getComputedStyle(body);\r
        var diagramStyle = window.getComputedStyle(diagram);\r
        return {\r
          bodyX: number(bodyStyle.paddingLeft) + number(bodyStyle.paddingRight),\r
          bodyY: number(bodyStyle.paddingTop) + number(bodyStyle.paddingBottom),\r
          diagramX: number(diagramStyle.paddingLeft) + number(diagramStyle.paddingRight) +\r
            number(diagramStyle.borderLeftWidth) + number(diagramStyle.borderRightWidth),\r
          diagramY: number(diagramStyle.paddingTop) + number(diagramStyle.paddingBottom) +\r
            number(diagramStyle.borderTopWidth) + number(diagramStyle.borderBottomWidth)\r
        };\r
      }\r
      function applyWidth(width) {\r
        var rounded = Math.round(width);\r
        if (Math.abs(rounded - lastWidth) < 1) return false;\r
        lastWidth = rounded;\r
        html.style.setProperty('--archify-reader-width', rounded + 'px');\r
        html.setAttribute('data-reader-layout', 'adaptive');\r
        return true;\r
      }\r
      function settleOverflow(minWidth) {\r
        if (settleFrame) cancelAnimationFrame(settleFrame);\r
        settleFrame = requestAnimationFrame(function () {\r
          settleFrame = 0;\r
          if (!eligible() || !lastWidth) return;\r
          var overflow = Math.max(\r
            document.documentElement.scrollHeight,\r
            document.body.scrollHeight\r
          ) - window.innerHeight;\r
          if (overflow > 1 && lastWidth > minWidth) {\r
            applyWidth(Math.max(minWidth, lastWidth - overflow * ratio - 4));\r
            html.setAttribute('data-reader-overflow', 'reduced');\r
          } else if (overflow > 1) {\r
            html.setAttribute('data-reader-overflow', 'authored');\r
          } else {\r
            html.removeAttribute('data-reader-overflow');\r
          }\r
        });\r
      }\r
      function measure() {\r
        frame = 0;\r
        if (!eligible()) {\r
          clear();\r
          return null;\r
        }\r
        var chrome = chromeMetrics();\r
        var viewportCap = Math.max(0, window.innerWidth - chrome.bodyX);\r
        var minWidth = Math.min(MIN_READER_WIDTH, viewportCap);\r
        var maxWidth = Math.min(MAX_READER_WIDTH, viewportCap);\r
        var fixedHeight = chrome.bodyY + chrome.diagramY + SAFE_BOTTOM_GAP +\r
          outerHeight(header) + outerHeight(guided) + outerHeight(cards);\r
        var availableSvgHeight = Math.max(1, window.innerHeight - fixedHeight);\r
        var desiredWidth = availableSvgHeight * ratio + chrome.diagramX;\r
        var width = Math.max(minWidth, Math.min(maxWidth, desiredWidth));\r
        applyWidth(width);\r
        settleOverflow(minWidth);\r
        return {\r
          ratio: ratio,\r
          width: Math.round(width),\r
          availableSvgHeight: Math.round(availableSvgHeight),\r
          fixedHeight: Math.round(fixedHeight)\r
        };\r
      }\r
      function schedule() {\r
        if (frame) return;\r
        frame = requestAnimationFrame(measure);\r
      }\r
      function stableSnapshot() {\r
        var shellRect = shell ? shell.getBoundingClientRect() : { width: 0, height: 0 };\r
        var diagramRect = diagram ? diagram.getBoundingClientRect() : { width: 0, height: 0 };\r
        return [\r
          lastWidth,\r
          html.getAttribute('data-reader-layout') || '',\r
          html.getAttribute('data-reader-overflow') || '',\r
          Math.ceil(document.documentElement.scrollWidth),\r
          Math.ceil(document.documentElement.scrollHeight),\r
          Math.ceil(document.body.scrollWidth),\r
          Math.ceil(document.body.scrollHeight),\r
          Math.round(shellRect.width * 100) / 100,\r
          Math.round(shellRect.height * 100) / 100,\r
          Math.round(diagramRect.width * 100) / 100,\r
          Math.round(diagramRect.height * 100) / 100\r
        ].join('|');\r
      }\r
      function whenStable() {\r
        return Archify.waitForStableLayout({\r
          schedule: schedule,\r
          pending: function () { return Boolean(frame || settleFrame); },\r
          snapshot: stableSnapshot,\r
          timeoutMessage: 'Adaptive reader layout did not reach stable dimensions.'\r
        });\r
      }\r
\r
      window.addEventListener('resize', schedule, { passive: true });\r
      window.addEventListener('load', schedule, { once: true });\r
      if (document.fonts && document.fonts.ready) document.fonts.ready.then(schedule).catch(function () {});\r
      if (typeof ResizeObserver === 'function') {\r
        var resizeObserver = new ResizeObserver(schedule);\r
        [header, guided, cards].forEach(function (element) { if (element) resizeObserver.observe(element); });\r
      }\r
      if (typeof MutationObserver === 'function') {\r
        var contentObserver = new MutationObserver(schedule);\r
        if (guided) contentObserver.observe(guided, { attributes: true, childList: true, subtree: true });\r
        if (cards) contentObserver.observe(cards, { attributes: true, childList: true, subtree: true });\r
        contentObserver.observe(html, { attributes: true, attributeFilter: ['data-embed', 'data-present'] });\r
      }\r
      schedule();\r
\r
      return {\r
        measure: measure,\r
        schedule: schedule,\r
        whenStable: whenStable,\r
        active: function () { return html.getAttribute('data-reader-layout') === 'adaptive'; },\r
        receipt: function () { return { ratio: ratio, width: lastWidth }; }\r
      };\r
    })();\r
\r
    /* ============================================================\r
       Viewer Chrome Layout — keep HTML controls clear of the canonical SVG\r
       stage without changing authored geometry. The dock keeps its floating\r
       appearance while a small bottom stage rail becomes part of the reader\r
       budget whenever its zero-reserve position would enter the stage.\r
       ============================================================ */\r
    Archify.viewerChromeLayout = (function () {\r
      var html = document.documentElement;\r
      var container = document.querySelector('.diagram-container');\r
      var svg = container && container.querySelector(':scope > svg');\r
      var nav = container && container.querySelector('.diagram-nav');\r
      var legend = svg && svg.querySelector('[data-legend]');\r
      var frame = 0;\r
      var settleFrame = 0;\r
      var reserve = 0;\r
      var railLatched = false;\r
      var probingBaseline = false;\r
      var probePromise = null;\r
      var baselineIntersectionArea = 0;\r
      var baselineStageGap = null;\r
      var restorableReserve = 0;\r
      var probeFallbackReserve = 0;\r
      var lastReceipt = null;\r
      var SAFE_GAP = 10;\r
\r
      function visible(element) {\r
        if (!element || element.hidden) return false;\r
        var style = window.getComputedStyle(element);\r
        return style.display !== 'none' && style.visibility !== 'hidden';\r
      }\r
      function usable(rect) {\r
        return Boolean(rect && rect.width > 0 && rect.height > 0);\r
      }\r
      function intersectionArea(a, b) {\r
        var width = Math.max(0, Math.min(a.right, b.right) - Math.max(a.left, b.left));\r
        var height = Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top));\r
        return width * height;\r
      }\r
      function protectedStageRect() {\r
        if (!svg) return null;\r
        var rect = svg.getBoundingClientRect();\r
        var transform = '';\r
        try { transform = window.getComputedStyle(svg).transform || ''; } catch (_) {}\r
        var scaleX = 1;\r
        var scaleY = 1;\r
        var translateX = 0;\r
        var translateY = 0;\r
        var matrix = transform.match(/^matrix\\(([^)]+)\\)$/);\r
        var matrix3d = transform.match(/^matrix3d\\(([^)]+)\\)$/);\r
        if (matrix) {\r
          var values = matrix[1].split(',').map(Number);\r
          if (values.length === 6 && values.every(Number.isFinite)) {\r
            scaleX = Math.abs(values[0]) || 1;\r
            scaleY = Math.abs(values[3]) || 1;\r
            translateX = values[4];\r
            translateY = values[5];\r
          }\r
        } else if (matrix3d) {\r
          var values3d = matrix3d[1].split(',').map(Number);\r
          if (values3d.length === 16 && values3d.every(Number.isFinite)) {\r
            scaleX = Math.abs(values3d[0]) || 1;\r
            scaleY = Math.abs(values3d[5]) || 1;\r
            translateX = values3d[12];\r
            translateY = values3d[13];\r
          }\r
        }\r
        var width = rect.width / scaleX;\r
        var height = rect.height / scaleY;\r
        var left = rect.left - translateX;\r
        var top = rect.top - translateY;\r
        return {\r
          x: left,\r
          y: top,\r
          left: left,\r
          top: top,\r
          right: left + width,\r
          bottom: top + height,\r
          width: width,\r
          height: height\r
        };\r
      }\r
      function eligible() {\r
        return Boolean(\r
          container && svg && nav &&\r
          window.innerWidth > 720 &&\r
          html.getAttribute('data-embed') !== 'true' &&\r
          (!window.matchMedia || !window.matchMedia('print').matches) &&\r
          visible(nav)\r
        );\r
      }\r
      function cameraAtBaseline() {\r
        var scale = Number(svg && svg.getAttribute('data-view-scale'));\r
        return !Number.isFinite(scale) || Math.abs(scale - 1) < 0.001;\r
      }\r
      function writeReserve(next, options) {\r
        options = options || {};\r
        next = Math.max(0, Math.ceil(next));\r
        if (Math.abs(next - reserve) < 1) return false;\r
        reserve = next;\r
        if (reserve) {\r
          if (options.remember !== false) restorableReserve = reserve;\r
          container.style.setProperty('--archify-nav-reserve', reserve + 'px');\r
          container.setAttribute('data-nav-stage-rail', 'true');\r
          html.setAttribute('data-nav-stage-rail', 'true');\r
        } else {\r
          container.style.removeProperty('--archify-nav-reserve');\r
          container.removeAttribute('data-nav-stage-rail');\r
          html.removeAttribute('data-nav-stage-rail');\r
        }\r
        if (Archify.readerLayout && typeof Archify.readerLayout.schedule === 'function') {\r
          Archify.readerLayout.schedule();\r
        }\r
        if (options.quiet !== true) {\r
          if (settleFrame) cancelAnimationFrame(settleFrame);\r
          settleFrame = requestAnimationFrame(function () {\r
            settleFrame = 0;\r
            schedule();\r
          });\r
        }\r
        return true;\r
      }\r
      function clear(options) {\r
        options = options || {};\r
        railLatched = false;\r
        if (options.preserveBaseline !== true) {\r
          baselineIntersectionArea = 0;\r
          baselineStageGap = null;\r
          restorableReserve = 0;\r
        }\r
        writeReserve(0, { quiet: probingBaseline });\r
        lastReceipt = {\r
          eligible: false,\r
          active: false,\r
          reserve: 0,\r
          gap: SAFE_GAP,\r
          baselineStageGap: null,\r
          stageGap: null,\r
          stageIntersectionArea: 0,\r
          baselineIntersectionArea: 0,\r
          intersectionArea: 0\r
        };\r
        return lastReceipt;\r
      }\r
      function measure() {\r
        frame = 0;\r
        if (probingBaseline) return null;\r
        if (!eligible()) return clear({ preserveBaseline: !cameraAtBaseline() });\r
\r
        /* Camera transforms enlarge and translate authored paint inside the\r
           fixed, clipped root SVG viewport. They must not redefine the\r
           reader's baseline rail.\r
           Restore that baseline after temporary mobile/embed/print states.\r
           Camera Reset preserves the established rail while viewport, mode,\r
           and content changes remain responsible for baseline reprobes. */\r
        if (!cameraAtBaseline()) {\r
          if (reserve === 0 && restorableReserve > 0) {\r
            if (writeReserve(restorableReserve)) return null;\r
          }\r
          var cameraNavRect = nav.getBoundingClientRect();\r
          var cameraLegendRect = visible(legend) ? legend.getBoundingClientRect() : null;\r
          var cameraStageRect = protectedStageRect();\r
          var cameraIntersectionArea = usable(cameraLegendRect) && intersectionArea(cameraNavRect, cameraStageRect) > 0\r
            ? intersectionArea(cameraNavRect, cameraLegendRect)\r
            : 0;\r
          lastReceipt = {\r
            eligible: true,\r
            active: reserve > 0,\r
            reserve: reserve,\r
            gap: SAFE_GAP,\r
            baselineStageGap: baselineStageGap == null ? null : Math.round(baselineStageGap * 100) / 100,\r
            stageGap: Math.round((cameraNavRect.top - cameraStageRect.bottom) * 100) / 100,\r
            stageIntersectionArea: Math.round(intersectionArea(cameraNavRect, cameraStageRect) * 100) / 100,\r
            baselineIntersectionArea: Math.round(baselineIntersectionArea * 100) / 100,\r
            intersectionArea: Math.round(cameraIntersectionArea * 100) / 100\r
          };\r
          return lastReceipt;\r
        }\r
\r
        var navRect = nav.getBoundingClientRect();\r
        var legendRect = visible(legend) ? legend.getBoundingClientRect() : null;\r
        var stageRect = protectedStageRect();\r
        if (!usable(navRect) || !usable(stageRect)) return clear();\r
\r
        var actualIntersectionArea = usable(legendRect) ? intersectionArea(navRect, legendRect) : 0;\r
        var stageGap = navRect.top - stageRect.bottom;\r
        if (!railLatched && reserve === 0) {\r
          baselineIntersectionArea = actualIntersectionArea;\r
          baselineStageGap = stageGap;\r
          if (stageGap < SAFE_GAP) {\r
            railLatched = true;\r
            if (writeReserve(Math.max(0, SAFE_GAP - stageGap))) return null;\r
          }\r
        } else if (railLatched && reserve > 0 && stageGap < SAFE_GAP) {\r
          /* Keep the decision latched while Adaptive Reader incorporates the\r
             rail. Presentation and rounded layout values can require one\r
             bounded follow-up before the full stage gap is established. */\r
          var remaining = Math.max(1, SAFE_GAP - stageGap);\r
          if (writeReserve(reserve + remaining)) return null;\r
        }\r
\r
        navRect = nav.getBoundingClientRect();\r
        legendRect = visible(legend) ? legend.getBoundingClientRect() : null;\r
        stageRect = protectedStageRect();\r
        stageGap = navRect.top - stageRect.bottom;\r
        lastReceipt = {\r
          eligible: true,\r
          active: reserve > 0,\r
          reserve: reserve,\r
          gap: SAFE_GAP,\r
          baselineStageGap: baselineStageGap == null ? null : Math.round(baselineStageGap * 100) / 100,\r
          stageGap: Math.round(stageGap * 100) / 100,\r
          stageIntersectionArea: Math.round(intersectionArea(navRect, stageRect) * 100) / 100,\r
          baselineIntersectionArea: Math.round(baselineIntersectionArea * 100) / 100,\r
          intersectionArea: Math.round((usable(legendRect) ? intersectionArea(navRect, legendRect) : 0) * 100) / 100\r
        };\r
        return lastReceipt;\r
      }\r
      function reprobe() {\r
        if (probingBaseline) return probePromise || Promise.resolve(false);\r
        if (!cameraAtBaseline()) {\r
          schedule();\r
          return Promise.resolve(false);\r
        }\r
        if (!reserve && !railLatched && !restorableReserve) {\r
          schedule();\r
          return Promise.resolve(false);\r
        }\r
        probeFallbackReserve = restorableReserve || reserve;\r
        probingBaseline = true;\r
        railLatched = false;\r
        baselineIntersectionArea = 0;\r
        baselineStageGap = null;\r
        restorableReserve = 0;\r
        writeReserve(0, { quiet: true });\r
        var readerReady = Archify.readerLayout && typeof Archify.readerLayout.whenStable === 'function'\r
          ? Archify.readerLayout.whenStable().catch(function () {})\r
          : Promise.resolve();\r
        probePromise = readerReady.then(function () {\r
          probingBaseline = false;\r
          probePromise = null;\r
          if (!cameraAtBaseline() && probeFallbackReserve > 0) {\r
            restorableReserve = probeFallbackReserve;\r
          }\r
          probeFallbackReserve = 0;\r
          schedule();\r
          return true;\r
        });\r
        return probePromise;\r
      }\r
      function schedule() {\r
        if (frame) return;\r
        frame = requestAnimationFrame(measure);\r
      }\r
      function stableSnapshot() {\r
        var containerRect = container ? container.getBoundingClientRect() : { width: 0, height: 0 };\r
        var navRect = nav ? nav.getBoundingClientRect() : { top: 0, left: 0 };\r
        var legendRect = legend ? legend.getBoundingClientRect() : { top: 0, left: 0 };\r
        return [\r
          reserve,\r
          Math.round(containerRect.width * 100) / 100,\r
          Math.round(containerRect.height * 100) / 100,\r
          Math.round(navRect.left * 100) / 100,\r
          Math.round(navRect.top * 100) / 100,\r
          Math.round(legendRect.left * 100) / 100,\r
          Math.round(legendRect.top * 100) / 100,\r
          railLatched ? 'latched' : 'clear',\r
          lastReceipt ? lastReceipt.stageGap : ''\r
        ].join('|');\r
      }\r
      function whenStable() {\r
        return Archify.waitForStableLayout({\r
          schedule: schedule,\r
          pending: function () { return Boolean(frame || settleFrame || probingBaseline); },\r
          snapshot: stableSnapshot,\r
          timeoutMessage: 'Viewer chrome layout did not reach stable dimensions.'\r
        });\r
      }\r
\r
      window.addEventListener('resize', reprobe, { passive: true });\r
      window.addEventListener('load', schedule, { once: true });\r
      window.addEventListener('beforeprint', schedule);\r
      window.addEventListener('afterprint', reprobe);\r
      if (document.fonts && document.fonts.ready) document.fonts.ready.then(reprobe).catch(function () {});\r
      if (typeof ResizeObserver === 'function') {\r
        var resizeObserver = new ResizeObserver(schedule);\r
        [nav, svg, legend].forEach(function (element) { if (element) resizeObserver.observe(element); });\r
      }\r
      if (typeof MutationObserver === 'function') {\r
        var contentObserver = new MutationObserver(function (records) {\r
          var viewerModeChanged = records.some(function (record) { return record.target === html; });\r
          if (viewerModeChanged) reprobe();\r
          else schedule();\r
        });\r
        if (legend) contentObserver.observe(legend, { attributes: true, childList: true, subtree: true });\r
        contentObserver.observe(html, {\r
          attributes: true,\r
          attributeFilter: ['data-embed', 'data-present', 'data-preset', 'data-theme']\r
        });\r
      }\r
      schedule();\r
\r
      return {\r
        measure: measure,\r
        schedule: schedule,\r
        reprobe: reprobe,\r
        whenStable: whenStable,\r
        stageRect: protectedStageRect,\r
        active: function () { return reserve > 0; },\r
        receipt: function () { return lastReceipt || measure(); }\r
      };\r
    })();\r
\r
    Archify.view = (function () {\r
      var container = document.querySelector('.diagram-container');\r
      var svg = container.querySelector('svg');\r
      var outBtn = container.querySelector('[data-view="out"]');\r
      var resetBtn = container.querySelector('[data-view="reset"]');\r
      var resetDetailLabel = resetBtn.querySelector('[data-view-detail]');\r
      var resetPercentLabel = resetBtn.querySelector('[data-view-percent]');\r
      var inBtn = container.querySelector('[data-view="in"]');\r
      var state = { scale: 1, x: 0, y: 0, mode: 'overview' };\r
      var drag = null;\r
      var cameraTimer = null;\r
      var cameraFrame = null;\r
      var cameraGeneration = 0;\r
      var cameraTransaction = null;\r
      var clipFrame = 0;\r
      var resizeFrame = 0;\r
      var autoScrollUntil = 0;\r
\r
      var viewBox = svg.viewBox && svg.viewBox.baseVal;\r
\r
      function clamp() {\r
        var width = svg.clientWidth || 1;\r
        var height = svg.clientHeight || 1;\r
        state.x = Math.min(0, Math.max(width - width * state.scale, state.x));\r
        state.y = Math.min(0, Math.max(height - height * state.scale, state.y));\r
      }\r
      function reducedMotion() {\r
        return window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;\r
      }\r
      function contentMetrics() {\r
        if (!viewBox || viewBox.width <= 0 || viewBox.height <= 0) return null;\r
        var width = svg.clientWidth || 1;\r
        var height = svg.clientHeight || 1;\r
        var scale = Math.min(width / viewBox.width, height / viewBox.height);\r
        return {\r
          width: width,\r
          height: height,\r
          scale: scale,\r
          offsetX: (width - viewBox.width * scale) / 2,\r
          offsetY: (height - viewBox.height * scale) / 2\r
        };\r
      }\r
      function logicalViewport() {\r
        var metrics = contentMetrics();\r
        if (!metrics) return null;\r
        var x;\r
        var y;\r
        var width;\r
        var height;\r
        if (window.innerWidth <= 720 && container.hasAttribute('data-wide-diagram')) {\r
          x = viewBox.x + container.scrollLeft / metrics.scale;\r
          y = viewBox.y;\r
          width = Math.min(viewBox.width, Math.max(1, container.clientWidth / metrics.scale));\r
          height = viewBox.height;\r
        } else {\r
          x = viewBox.x + ((-state.x / state.scale) - metrics.offsetX) / metrics.scale;\r
          y = viewBox.y + ((-state.y / state.scale) - metrics.offsetY) / metrics.scale;\r
          width = Math.min(viewBox.width, metrics.width / state.scale / metrics.scale);\r
          height = Math.min(viewBox.height, metrics.height / state.scale / metrics.scale);\r
        }\r
        width = Math.max(1, Math.min(viewBox.width, width));\r
        height = Math.max(1, Math.min(viewBox.height, height));\r
        x = Math.max(viewBox.x, Math.min(viewBox.x + viewBox.width - width, x));\r
        y = Math.max(viewBox.y, Math.min(viewBox.y + viewBox.height - height, y));\r
        return { x: x, y: y, width: width, height: height, scale: state.scale };\r
      }\r
      function detailLevel() {\r
        if (state.mode === 'semantic') return 'full';\r
        if (state.scale >= 1.75) return 'full';\r
        if (state.scale >= 1) return 'read';\r
        return 'map';\r
      }\r
      function renderControls() {\r
        var semantic = state.mode === 'semantic' && state.scale > 1.01;\r
        var detail = detailLevel();\r
        var percent = Math.round(state.scale * 100) + '%';\r
        var levelLabel = viewerText('viewer.nav.level.' + detail);\r
        var detailHint = detail === 'map'\r
          ? viewerText('viewer.nav.detail.map')\r
          : detail === 'read'\r
            ? viewerText('viewer.nav.detail.read')\r
            : viewerText('viewer.nav.detail.full');\r
        var resolvedLevel = semantic ? viewerText('viewer.nav.level.auto') : levelLabel;\r
        var showDetailLevel = semantic || detail !== 'read';\r
        if (resetDetailLabel) {\r
          resetDetailLabel.textContent = resolvedLevel;\r
          resetDetailLabel.hidden = !showDetailLevel;\r
        }\r
        if (resetPercentLabel) resetPercentLabel.textContent = percent;\r
        resetBtn.toggleAttribute('data-detail-visible', showDetailLevel);\r
        resetBtn.title = viewerText('viewer.nav.camera.title', {\r
          semantic: semantic ? viewerText('viewer.nav.camera.semantic') : '',\r
          hint: detailHint\r
        });\r
        resetBtn.setAttribute('aria-label', viewerText('viewer.nav.camera', { hint: detailHint }));\r
        resetBtn.setAttribute('data-detail-level', detail);\r
        container.setAttribute('data-detail-level', detail);\r
        container.setAttribute('data-camera-mode', state.mode);\r
        container.setAttribute('data-camera-indicator', semantic ? 'true' : 'false');\r
      }\r
      function clipToViewport(camera) {\r
        camera = camera || state;\r
        if (camera.scale <= 1.001) {\r
          svg.style.removeProperty('clip-path');\r
          return;\r
        }\r
        var width = svg.clientWidth || 1;\r
        var height = svg.clientHeight || 1;\r
        var scale = camera.scale;\r
        var top = Math.max(0, Math.min(height, -camera.y / scale));\r
        var left = Math.max(0, Math.min(width, -camera.x / scale));\r
        var right = Math.max(0, Math.min(width, width - (width - camera.x) / scale));\r
        var bottom = Math.max(0, Math.min(height, height - (height - camera.y) / scale));\r
        svg.style.clipPath = 'inset(' + [top, right, bottom, left].map(function (value) {\r
          return Math.round(value * 1000) / 1000 + 'px';\r
        }).join(' ') + ')';\r
      }\r
      function cameraSettled(rendered) {\r
        return Math.abs(rendered.scale - state.scale) < 0.001 &&\r
          Math.abs(rendered.x - state.x) < 0.05 &&\r
          Math.abs(rendered.y - state.y) < 0.05;\r
      }\r
      function syncViewportClip() {\r
        if (clipFrame) cancelAnimationFrame(clipFrame);\r
        clipFrame = 0;\r
        function sample() {\r
          clipFrame = 0;\r
          var rendered = sampleRenderedState();\r
          clipToViewport(rendered);\r
          if (!cameraSettled(rendered)) clipFrame = requestAnimationFrame(sample);\r
        }\r
        sample();\r
      }\r
      function apply() {\r
        clamp();\r
        svg.style.transform = 'translate(' + state.x + 'px,' + state.y + 'px) scale(' + state.scale + ')';\r
        syncViewportClip();\r
        renderControls();\r
        outBtn.disabled = state.scale <= 1;\r
        inBtn.disabled = state.scale >= 3;\r
        container.classList.toggle('is-pannable', state.scale > 1);\r
        svg.setAttribute('data-view-scale', String(state.scale));\r
        if (Archify.radar && typeof Archify.radar.sync === 'function') Archify.radar.sync();\r
        if (Archify.viewerChromeLayout && typeof Archify.viewerChromeLayout.schedule === 'function') {\r
          Archify.viewerChromeLayout.schedule();\r
        }\r
      }\r
      function sampleRenderedState() {\r
        var transform = '';\r
        try { transform = getComputedStyle(svg).transform || ''; } catch (_) {}\r
        var match = transform.match(/^matrix\\(([^)]+)\\)$/);\r
        if (!match) return { scale: state.scale, x: state.x, y: state.y, mode: state.mode };\r
        var values = match[1].split(',').map(Number);\r
        if (values.length !== 6 || !values.every(Number.isFinite)) {\r
          return { scale: state.scale, x: state.x, y: state.y, mode: state.mode };\r
        }\r
        return { scale: values[0], x: values[4], y: values[5], mode: state.mode };\r
      }\r
      function finishCameraTransaction(transaction, outcome) {\r
        if (!transaction || transaction.settled) return false;\r
        transaction.settled = true;\r
        transaction.state = outcome || 'complete';\r
        if (transaction.frame) cancelAnimationFrame(transaction.frame);\r
        if (transaction.timer) clearTimeout(transaction.timer);\r
        transaction.frame = null;\r
        transaction.timer = null;\r
        if (cameraTransaction === transaction) cameraTransaction = null;\r
        cameraFrame = null;\r
        cameraTimer = null;\r
        container.classList.remove('is-camera-moving');\r
        container.classList.remove('is-camera-transaction');\r
        container.removeAttribute('data-camera-transaction');\r
        if (Archify.focus && Archify.focus.reposition) Archify.focus.reposition();\r
        transaction.resolve({ id: transaction.id, state: transaction.state });\r
        return true;\r
      }\r
      function cameraReceipt(target, options) {\r
        var resolver;\r
        var transaction = {\r
          id: ++cameraGeneration,\r
          state: 'running',\r
          target: target,\r
          settled: false,\r
          frame: null,\r
          timer: null,\r
          finished: new Promise(function (resolve) { resolver = resolve; }),\r
          resolve: resolver,\r
          cancel: function (reason, commitTarget) {\r
            if (transaction.settled) return false;\r
            if (commitTarget && transaction.target) {\r
              if (Object.prototype.hasOwnProperty.call(transaction.target, 'scrollLeft')) {\r
                container.scrollLeft = transaction.target.scrollLeft;\r
              } else {\r
                state = {\r
                  scale: transaction.target.scale,\r
                  x: transaction.target.x,\r
                  y: transaction.target.y,\r
                  mode: transaction.target.mode\r
                };\r
                apply();\r
              }\r
            }\r
            return finishCameraTransaction(transaction, reason || 'cancelled');\r
          }\r
        };\r
        return transaction;\r
      }\r
      function stopCameraMotion(reason, commitTarget) {\r
        if (cameraTransaction && !cameraTransaction.settled) {\r
          cameraTransaction.cancel(reason || 'cancelled', commitTarget === true);\r
          return;\r
        }\r
        if (cameraTimer) clearTimeout(cameraTimer);\r
        if (cameraFrame) cancelAnimationFrame(cameraFrame);\r
        cameraTimer = null;\r
        cameraFrame = null;\r
        container.classList.remove('is-camera-moving');\r
        container.classList.remove('is-camera-transaction');\r
        container.removeAttribute('data-camera-transaction');\r
      }\r
      function interruptCamera(reason) {\r
        if (Archify.guidedViews && Archify.guidedViews.cancelHandoff) {\r
          Archify.guidedViews.cancelHandoff(reason || 'manual');\r
        }\r
        var rendered = sampleRenderedState();\r
        stopCameraMotion(reason || 'manual', false);\r
        state = rendered;\r
        state.mode = 'manual';\r
        apply();\r
        renderControls();\r
        if (Archify.guidedViews && Archify.guidedViews.isPlaying && Archify.guidedViews.isPlaying()) {\r
          Archify.guidedViews.pause();\r
        }\r
        if (Archify.routeProbe && Archify.routeProbe.isJourneyPlaying && Archify.routeProbe.isJourneyPlaying()) {\r
          Archify.routeProbe.pauseJourney({ preserveElapsed: true, reason: reason || 'manual' });\r
        }\r
      }\r
      function zoom(next, options) {\r
        options = options || {};\r
        if (options.manual !== false) interruptCamera();\r
        var previous = state.scale;\r
        next = Math.max(1, Math.min(3, Math.round(next * 4) / 4));\r
        if (next === previous) return;\r
        var centerX = (svg.clientWidth || 1) / 2;\r
        var centerY = (svg.clientHeight || 1) / 2;\r
        var contentX = (centerX - state.x) / previous;\r
        var contentY = (centerY - state.y) / previous;\r
        state.scale = next;\r
        state.x = centerX - contentX * next;\r
        state.y = centerY - contentY * next;\r
        apply();\r
      }\r
      function reset(options) {\r
        options = options || {};\r
        if (options.automatic !== true) interruptCamera();\r
        else stopCameraMotion('reset', false);\r
        state = { scale: 1, x: 0, y: 0, mode: 'overview' };\r
        apply();\r
      }\r
      function centerAt(logicalX, logicalY, options) {\r
        options = options || {};\r
        logicalX = Number(logicalX);\r
        logicalY = Number(logicalY);\r
        var metrics = contentMetrics();\r
        if (!metrics || !Number.isFinite(logicalX) || !Number.isFinite(logicalY)) return false;\r
        interruptCamera();\r
        if (window.innerWidth <= 720 && container.hasAttribute('data-wide-diagram')) {\r
          state.scale = 1;\r
          state.x = 0;\r
          state.y = 0;\r
          state.mode = 'manual';\r
          apply();\r
          var mobileTarget = (logicalX - viewBox.x) * metrics.scale - container.clientWidth / 2;\r
          mobileTarget = Math.max(0, Math.min(svg.clientWidth - container.clientWidth, mobileTarget));\r
          autoScrollUntil = Date.now() + 80;\r
          try { container.scrollTo({ left: mobileTarget, behavior: options.instant ? 'auto' : 'smooth' }); }\r
          catch (_) { container.scrollLeft = mobileTarget; }\r
          return true;\r
        }\r
        var minimumScale = Math.max(1, Math.min(3, Number(options.minimumScale) || 1));\r
        var requestedScale = Number(options.scale);\r
        state.scale = Math.max(minimumScale, Math.min(3, Number.isFinite(requestedScale) ? requestedScale : state.scale));\r
        var contentX = metrics.offsetX + (logicalX - viewBox.x) * metrics.scale;\r
        var contentY = metrics.offsetY + (logicalY - viewBox.y) * metrics.scale;\r
        state.x = metrics.width / 2 - contentX * state.scale;\r
        state.y = metrics.height / 2 - contentY * state.scale;\r
        state.mode = 'manual';\r
        apply();\r
        if (Archify.focus && Archify.focus.reposition) Archify.focus.reposition();\r
        return true;\r
      }\r
      function semanticIds(ids, includeNeighbors) {\r
        var seeds = Object.create(null);\r
        var wanted = Object.create(null);\r
        (ids || []).forEach(function (id) { seeds[id] = true; wanted[id] = true; });\r
        if (includeNeighbors) {\r
          Array.prototype.forEach.call(svg.querySelectorAll('[data-edge-from][data-edge-to]'), function (edge) {\r
            var from = edge.getAttribute('data-edge-from');\r
            var to = edge.getAttribute('data-edge-to');\r
            if (seeds[from] || seeds[to]) { wanted[from] = true; wanted[to] = true; }\r
          });\r
        }\r
        return wanted;\r
      }\r
      function boxesFor(ids, includeNeighbors) {\r
        var wanted = semanticIds(ids, includeNeighbors);\r
        return Array.prototype.slice.call(svg.querySelectorAll('[data-node-id]'))\r
          .filter(function (node) { return wanted[node.getAttribute('data-node-id')]; })\r
          .map(function (node) {\r
            try { return node.getBBox(); } catch (_) { return null; }\r
          })\r
          .filter(Boolean);\r
      }\r
      function frameDesktop(ids, options) {\r
        options = options || {};\r
        var boxes = boxesFor(ids, options.includeNeighbors === true);\r
        if (!boxes.length || !viewBox || viewBox.width <= 0 || viewBox.height <= 0) return false;\r
        var svgWidth = svg.clientWidth || 1;\r
        var svgHeight = svg.clientHeight || 1;\r
        var contentScale = Math.min(svgWidth / viewBox.width, svgHeight / viewBox.height);\r
        var contentOffsetX = (svgWidth - viewBox.width * contentScale) / 2;\r
        var contentOffsetY = (svgHeight - viewBox.height * contentScale) / 2;\r
        var minX = Math.min.apply(Math, boxes.map(function (box) { return box.x; }));\r
        var minY = Math.min.apply(Math, boxes.map(function (box) { return box.y; }));\r
        var maxX = Math.max.apply(Math, boxes.map(function (box) { return box.x + box.width; }));\r
        var maxY = Math.max.apply(Math, boxes.map(function (box) { return box.y + box.height; }));\r
        var bounds = {\r
          x: contentOffsetX + minX * contentScale,\r
          y: contentOffsetY + minY * contentScale,\r
          width: Math.max(1, (maxX - minX) * contentScale),\r
          height: Math.max(1, (maxY - minY) * contentScale)\r
        };\r
        var padding = options.padding || 48;\r
        var left = padding;\r
        var right = svgWidth - padding;\r
        var top = padding;\r
        var bottom = svgHeight - Math.max(padding, 72);\r
        var containerRect = container.getBoundingClientRect();\r
        var visibleTop = Math.max(0, -containerRect.top);\r
        var visibleBottom = Math.min(svgHeight, window.innerHeight - containerRect.top);\r
        if (visibleBottom - visibleTop >= 240) {\r
          top = Math.max(top, visibleTop + padding);\r
          bottom = Math.min(bottom, visibleBottom - Math.max(padding, 72));\r
        }\r
        var chip = document.getElementById('focus-chip');\r
        if (chip && !chip.hidden) {\r
          var lensEnd = chip.offsetLeft + chip.offsetWidth + 24 - (svg.offsetLeft || 0);\r
          left = Math.max(left, Math.min(svgWidth * 0.42, lensEnd));\r
        }\r
        var routeReceipt = document.getElementById('route-probe');\r
        if (routeReceipt && !routeReceipt.hidden && routeReceipt.hasAttribute('data-route-journey')) {\r
          var receiptTop = routeReceipt.offsetTop;\r
          var receiptBottom = receiptTop + routeReceipt.offsetHeight;\r
          if (receiptTop < svgHeight / 2) top = Math.max(top, receiptBottom + 24);\r
          else bottom = Math.min(bottom, receiptTop - 24);\r
        }\r
        if (right <= left || bottom <= top) return false;\r
        var maxScale = options.maxScale || (options.includeNeighbors ? 1.9 : 2.15);\r
        var targetScale = Math.min((right - left) / bounds.width, (bottom - top) / bounds.height) * 0.9;\r
        targetScale = Math.max(1, Math.min(maxScale, targetScale));\r
        if (targetScale < 1.08) targetScale = 1;\r
        var target = {\r
          scale: Math.round(targetScale * 100) / 100,\r
          x: 0,\r
          y: 0,\r
          mode: 'semantic'\r
        };\r
        target.x = (left + right) / 2 - (bounds.x + bounds.width / 2) * target.scale;\r
        target.y = (top + bottom) / 2 - (bounds.y + bounds.height / 2) * target.scale;\r
        var start = sampleRenderedState();\r
        stopCameraMotion('replaced', false);\r
        var transaction = cameraReceipt(target, options);\r
        cameraTransaction = transaction;\r
        var instant = options.instant === true || reducedMotion() || document.hidden;\r
        if (instant) {\r
          state = target;\r
          apply();\r
          finishCameraTransaction(transaction, reducedMotion() ? 'reduced-motion' : (document.hidden ? 'hidden' : 'complete'));\r
          return transaction;\r
        }\r
        var duration = Math.max(180, Math.min(520, Number(options.duration) || 420));\r
        var startedAt = 0;\r
        state = start;\r
        state.mode = 'semantic';\r
        apply();\r
        container.classList.add('is-camera-moving');\r
        container.classList.add('is-camera-transaction');\r
        container.setAttribute('data-camera-transaction', String(transaction.id));\r
        var step = function (timestamp) {\r
          if (cameraTransaction !== transaction || transaction.settled) return;\r
          if (!startedAt) startedAt = timestamp;\r
          var fraction = Math.max(0, Math.min(1, (timestamp - startedAt) / duration));\r
          var eased = 1 - Math.pow(1 - fraction, 3);\r
          state = {\r
            scale: start.scale + (target.scale - start.scale) * eased,\r
            x: start.x + (target.x - start.x) * eased,\r
            y: start.y + (target.y - start.y) * eased,\r
            mode: 'semantic'\r
          };\r
          apply();\r
          if (fraction < 1) {\r
            transaction.frame = requestAnimationFrame(step);\r
            cameraFrame = transaction.frame;\r
          } else {\r
            state = target;\r
            apply();\r
            finishCameraTransaction(transaction, 'complete');\r
          }\r
        };\r
        transaction.frame = requestAnimationFrame(step);\r
        cameraFrame = transaction.frame;\r
        return transaction;\r
      }\r
      function reveal(ids, options) {\r
        options = options || {};\r
        if (window.innerWidth > 720) return frameDesktop(ids, options);\r
        stopCameraMotion('replaced', false);\r
        state.scale = 1;\r
        state.x = 0;\r
        state.y = 0;\r
        state.mode = 'semantic';\r
        apply();\r
        if (!container.hasAttribute('data-wide-diagram')) {\r
          var contained = cameraReceipt({ scale: 1, x: 0, y: 0, mode: 'semantic' }, options);\r
          cameraTransaction = contained;\r
          finishCameraTransaction(contained, 'complete');\r
          return contained;\r
        }\r
        var boxes = boxesFor(ids, options.includeNeighbors === true);\r
        if (!boxes.length || !viewBox || viewBox.width <= 0) return false;\r
        var minX = Math.min.apply(Math, boxes.map(function (box) { return box.x; }));\r
        var maxX = Math.max.apply(Math, boxes.map(function (box) { return box.x + box.width; }));\r
        var center = ((minX + maxX) / 2 / viewBox.width) * (svg.clientWidth || 1);\r
        var target = Math.max(0, Math.min(svg.clientWidth - container.clientWidth, center - container.clientWidth / 2));\r
        var transaction = cameraReceipt({ scrollLeft: target }, options);\r
        cameraTransaction = transaction;\r
        var instant = options.instant === true || reducedMotion() || document.hidden;\r
        autoScrollUntil = Date.now() + (instant ? 50 : 470);\r
        try { container.scrollTo({ left: target, behavior: instant ? 'auto' : 'smooth' }); }\r
        catch (_) { container.scrollLeft = target; }\r
        if (instant) finishCameraTransaction(transaction, reducedMotion() ? 'reduced-motion' : (document.hidden ? 'hidden' : 'complete'));\r
        else {\r
          transaction.timer = setTimeout(function () { finishCameraTransaction(transaction, 'complete'); }, 460);\r
          cameraTimer = transaction.timer;\r
          container.classList.add('is-camera-moving');\r
          container.setAttribute('data-camera-transaction', String(transaction.id));\r
        }\r
        return transaction;\r
      }\r
      function syncSemantic() {\r
        var guided = Archify.guidedViews && typeof Archify.guidedViews.focus === 'function'\r
          ? Archify.guidedViews.focus() : [];\r
        if (guided && guided.length) return reveal(guided, { reason: 'guided-sync' });\r
        var active = Archify.focus && typeof Archify.focus.active === 'function' ? Archify.focus.active() : null;\r
        if (typeof active === 'string') return reveal([active], { includeNeighbors: true, reason: 'focus-sync' });\r
        if (Array.isArray(active) && active.length) return reveal(active, { reason: 'selection-sync' });\r
        return false;\r
      }\r
      function pinControls() {\r
        container.style.setProperty('--archify-scroll-x', container.scrollLeft + 'px');\r
      }\r
      function onScroll() {\r
        pinControls();\r
        if (Archify.radar && typeof Archify.radar.sync === 'function') Archify.radar.sync();\r
        if (window.innerWidth <= 720 && container.hasAttribute('data-wide-diagram') && Date.now() > autoScrollUntil) {\r
          interruptCamera();\r
        }\r
      }\r
      function onPointerEnd(event) {\r
        if (!drag) return;\r
        var moved = drag.moved;\r
        drag = null;\r
        container.classList.remove('is-panning');\r
        try { container.releasePointerCapture(event.pointerId); } catch (_) {}\r
        if (moved) {\r
          container.setAttribute('data-just-panned', 'true');\r
          setTimeout(function () { container.removeAttribute('data-just-panned'); }, 80);\r
        }\r
      }\r
\r
      inBtn.addEventListener('click', function () { zoom(state.scale + 0.25); });\r
      outBtn.addEventListener('click', function () { zoom(state.scale - 0.25); });\r
      resetBtn.addEventListener('click', reset);\r
      container.addEventListener('pointerdown', function (event) {\r
        if (state.scale <= 1 || event.button !== 0 || event.target.closest('.diagram-nav, .focus-chip, .node-finder, .diagram-guide, .overview-map, .route-probe, .semantic-lens') || event.target.closest('[data-node-id]') || event.target.closest('[data-relationship-hit-key]')) return;\r
        interruptCamera();\r
        drag = { startX: event.clientX, startY: event.clientY, x: state.x, y: state.y, moved: false };\r
        container.classList.add('is-panning');\r
        try { container.setPointerCapture(event.pointerId); } catch (_) {}\r
      });\r
      container.addEventListener('pointermove', function (event) {\r
        if (!drag) return;\r
        var dx = event.clientX - drag.startX;\r
        var dy = event.clientY - drag.startY;\r
        if (Math.abs(dx) + Math.abs(dy) > 3) drag.moved = true;\r
        state.x = drag.x + dx;\r
        state.y = drag.y + dy;\r
        apply();\r
      });\r
      container.addEventListener('pointerup', onPointerEnd);\r
      container.addEventListener('pointercancel', onPointerEnd);\r
      container.addEventListener('scroll', onScroll, { passive: true });\r
      window.addEventListener('resize', function () {\r
        if (resizeFrame) cancelAnimationFrame(resizeFrame);\r
        resizeFrame = requestAnimationFrame(function () {\r
          resizeFrame = 0;\r
          if (state.mode === 'semantic') syncSemantic();\r
          else apply();\r
        });\r
      });\r
      window.addEventListener('hashchange', function () { requestAnimationFrame(syncSemantic); });\r
      apply();\r
      pinControls();\r
      requestAnimationFrame(syncSemantic);\r
\r
      return {\r
        zoomIn: function () { zoom(state.scale + 0.25); },\r
        zoomOut: function () { zoom(state.scale - 0.25); },\r
        reset: reset,\r
        reveal: reveal,\r
        centerAt: centerAt,\r
        logicalViewport: logicalViewport,\r
        sync: syncSemantic,\r
        state: function () { return { scale: state.scale, x: state.x, y: state.y, mode: state.mode }; }\r
      };\r
    })();\r
\r
    /* ============================================================\r
       Semantic Radar — simplified semantic bounds + live viewport.\r
       The radar is built at runtime so the checked artifact still contains\r
       one canonical SVG block, and export serialization remains untouched.\r
       ============================================================ */\r
    Archify.radar = (function () {\r
      var container = document.querySelector('.diagram-container');\r
      var diagram = container.querySelector(':scope > svg');\r
      var panel = document.getElementById('overview-map');\r
      var panelHead = panel.querySelector('.overview-map-head');\r
      var surface = document.getElementById('overview-map-surface');\r
      var status = document.getElementById('overview-map-status');\r
      var trigger = document.getElementById('btn-overview-map');\r
      var closeBtn = document.getElementById('overview-map-close');\r
      var expandBtn = document.getElementById('overview-map-expand');\r
      var feedback = document.getElementById('overview-map-feedback');\r
      var navigation = container.querySelector('.diagram-nav');\r
      var passport = document.getElementById('focus-chip');\r
      var namespace = 'http://www.w3.org/2000/svg';\r
      var viewBox = diagram.viewBox && diagram.viewBox.baseVal;\r
      var mapSvg = document.createElementNS(namespace, 'svg');\r
      var nodeLayer = document.createElementNS(namespace, 'g');\r
      var viewport = document.createElementNS(namespace, 'rect');\r
      var nodes = [];\r
      var viewportDrag = null;\r
      var panelDrag = null;\r
      var manualPosition = null;\r
      var lastPlacement = null;\r
      var requestedOpen = false;\r
      var passportYielded = false;\r
      var passportPreviousAriaHidden = null;\r
      var syncFrame = 0;\r
      var spaceRetryTimer = 0;\r
      var spaceRetryCount = 0;\r
      var placementGap = 16;\r
\r
      mapSvg.setAttribute('role', 'group');\r
      mapSvg.setAttribute('aria-label', viewerText('viewer.radar.nodes'));\r
      mapSvg.setAttribute('preserveAspectRatio', 'xMidYMid meet');\r
      nodeLayer.setAttribute('class', 'overview-map-nodes');\r
      viewport.setAttribute('class', 'overview-map-viewport');\r
      viewport.setAttribute('rx', '3');\r
      viewport.setAttribute('ry', '3');\r
      mapSvg.appendChild(nodeLayer);\r
      mapSvg.appendChild(viewport);\r
      surface.appendChild(mapSvg);\r
\r
      function nodeLabel(node, fallback) {\r
        return node.getAttribute('data-node-label') ||\r
          (node.getAttribute('aria-label') || fallback).replace(/^Focus\\s+/, '').split(',')[0];\r
      }\r
      function build() {\r
        if (!viewBox || viewBox.width <= 0 || viewBox.height <= 0) return false;\r
        mapSvg.setAttribute('viewBox', [viewBox.x, viewBox.y, viewBox.width, viewBox.height].join(' '));\r
        nodeLayer.textContent = '';\r
        nodes = [];\r
        Array.prototype.forEach.call(diagram.querySelectorAll('[data-node-id]'), function (node) {\r
          var box;\r
          try { box = node.getBBox(); } catch (_) { box = null; }\r
          if (!box || box.width <= 0 || box.height <= 0) return;\r
          var id = node.getAttribute('data-node-id');\r
          var rect = document.createElementNS(namespace, 'rect');\r
          rect.setAttribute('class', 'overview-map-node');\r
          rect.setAttribute('x', String(box.x));\r
          rect.setAttribute('y', String(box.y));\r
          rect.setAttribute('width', String(Math.max(3, box.width)));\r
          rect.setAttribute('height', String(Math.max(3, box.height)));\r
          rect.setAttribute('rx', String(Math.max(2, Math.min(8, Math.min(box.width, box.height) * 0.1))));\r
          rect.setAttribute('data-radar-node-id', id);\r
          rect.setAttribute('data-kind', node.getAttribute('data-node-kind') || 'neutral');\r
          rect.setAttribute('tabindex', '0');\r
          rect.setAttribute('role', 'button');\r
          rect.setAttribute('aria-label', viewerText('viewer.radar.focus', { label: nodeLabel(node, id) }));\r
          nodeLayer.appendChild(rect);\r
          nodes.push({ id: id, node: node, rect: rect });\r
        });\r
        status.textContent = viewerText('viewer.radar.fullMap', { count: nodes.length });\r
        return true;\r
      }\r
      function visibleRect(element) {\r
        if (!element || element.hidden) return null;\r
        var rect = element.getBoundingClientRect();\r
        if (rect.width <= 0 || rect.height <= 0 || rect.right <= 0 || rect.bottom <= 0 || rect.left >= window.innerWidth || rect.top >= window.innerHeight) return null;\r
        return { left: rect.left, top: rect.top, right: rect.right, bottom: rect.bottom, width: rect.width, height: rect.height };\r
      }\r
      function panelRectAt(position) {\r
        return {\r
          left: position.left,\r
          top: position.top,\r
          right: position.left + panel.offsetWidth,\r
          bottom: position.top + panel.offsetHeight,\r
          width: panel.offsetWidth,\r
          height: panel.offsetHeight\r
        };\r
      }\r
      function rectsIntersect(first, second, gap) {\r
        gap = Number(gap) || 0;\r
        return first.left < second.right + gap &&\r
          first.right > second.left - gap &&\r
          first.top < second.bottom + gap &&\r
          first.bottom > second.top - gap;\r
      }\r
      function intersectionArea(first, second) {\r
        var width = Math.max(0, Math.min(first.right, second.right) - Math.max(first.left, second.left));\r
        var height = Math.max(0, Math.min(first.bottom, second.bottom) - Math.max(first.top, second.top));\r
        return width * height;\r
      }\r
      function clamp(value, minimum, maximum) {\r
        if (maximum < minimum) return minimum;\r
        return Math.max(minimum, Math.min(maximum, value));\r
      }\r
      function placementContext() {\r
        var containerRect = visibleRect(container);\r
        if (!containerRect) return null;\r
        var controlRect = visibleRect(navigation);\r
        var left = Math.max(placementGap, containerRect.left + placementGap);\r
        var top = Math.max(placementGap, containerRect.top + placementGap);\r
        var right = Math.min(window.innerWidth - placementGap, containerRect.right - placementGap);\r
        var bottom = Math.min(window.innerHeight - placementGap, containerRect.bottom - placementGap);\r
        if (controlRect) bottom = Math.min(bottom, controlRect.top - placementGap);\r
        var lens = document.getElementById('focus-chip');\r
        var lensRect = visibleRect(lens);\r
        var legendRect = visibleRect(diagram.querySelector('[data-legend]'));\r
        var active = diagram.querySelector('[data-focus-selected]');\r
        var activeRect = visibleRect(active);\r
        return {\r
          bounds: { left: left, top: top, right: right, bottom: bottom },\r
          hardBlockers: [lensRect, controlRect, legendRect].filter(Boolean),\r
          softBlockers: [activeRect].filter(Boolean),\r
          preferredSide: !activeRect || activeRect.left + activeRect.width / 2 > window.innerWidth / 2 ? 'left' : 'right'\r
        };\r
      }\r
      function positionIsValid(position, context) {\r
        if (!position || !context) return false;\r
        var rect = panelRectAt(position);\r
        var bounds = context.bounds;\r
        if (rect.left < bounds.left || rect.top < bounds.top || rect.right > bounds.right || rect.bottom > bounds.bottom) return false;\r
        return context.hardBlockers.every(function (blocker) { return !rectsIntersect(rect, blocker, placementGap); });\r
      }\r
      function cornerCandidates(context) {\r
        var bounds = context.bounds;\r
        var left = bounds.left;\r
        var right = Math.max(left, bounds.right - panel.offsetWidth);\r
        var top = bounds.top;\r
        var bottom = Math.max(top, bounds.bottom - panel.offsetHeight);\r
        var preferredLeft = context.preferredSide === 'left' ? left : right;\r
        var alternateLeft = context.preferredSide === 'left' ? right : left;\r
        return [\r
          { left: preferredLeft, top: bottom },\r
          { left: alternateLeft, top: bottom },\r
          { left: preferredLeft, top: top },\r
          { left: alternateLeft, top: top }\r
        ].filter(function (candidate, index, all) {\r
          return all.findIndex(function (other) { return other.left === candidate.left && other.top === candidate.top; }) === index;\r
        });\r
      }\r
      function nearbyCandidates(context, reference) {\r
        var bounds = context.bounds;\r
        var maximumLeft = bounds.right - panel.offsetWidth;\r
        var maximumTop = bounds.bottom - panel.offsetHeight;\r
        var requested = reference ? {\r
          left: clamp(reference.left, bounds.left, maximumLeft),\r
          top: clamp(reference.top, bounds.top, maximumTop)\r
        } : null;\r
        var horizontal = [bounds.left, maximumLeft];\r
        var vertical = [bounds.top, maximumTop];\r
        if (requested) {\r
          horizontal.push(requested.left);\r
          vertical.push(requested.top);\r
        }\r
        context.hardBlockers.forEach(function (blocker) {\r
          horizontal.push(\r
            blocker.left - placementGap - panel.offsetWidth,\r
            blocker.right + placementGap\r
          );\r
          vertical.push(\r
            blocker.top - placementGap - panel.offsetHeight,\r
            blocker.bottom + placementGap\r
          );\r
        });\r
        horizontal = horizontal.map(function (left) { return clamp(left, bounds.left, maximumLeft); });\r
        vertical = vertical.map(function (top) { return clamp(top, bounds.top, maximumTop); });\r
        var candidates = [];\r
        horizontal.forEach(function (left) {\r
          vertical.forEach(function (top) { candidates.push({ left: left, top: top }); });\r
        });\r
        return candidates.filter(function (candidate, index, all) {\r
          return all.findIndex(function (other) { return other.left === candidate.left && other.top === candidate.top; }) === index;\r
        });\r
      }\r
      function placementScore(position, context, reference, softWeight) {\r
        var rect = panelRectAt(position);\r
        var referenceLeft = reference ? reference.left : (context.preferredSide === 'left' ? context.bounds.left : context.bounds.right - panel.offsetWidth);\r
        var referenceTop = reference ? reference.top : context.bounds.bottom - panel.offsetHeight;\r
        var distance = Math.pow(position.left - referenceLeft, 2) + Math.pow(position.top - referenceTop, 2);\r
        var softOverlap = context.softBlockers.reduce(function (total, blocker) { return total + intersectionArea(rect, blocker); }, 0);\r
        return distance + softOverlap * softWeight;\r
      }\r
      function chooseRadarPlacement(context, reference, options) {\r
        options = options || {};\r
        var softWeight = Number.isFinite(options.softWeight) ? options.softWeight : 100;\r
        var candidates = nearbyCandidates(context, reference).concat(cornerCandidates(context));\r
        var valid = candidates.filter(function (candidate) { return positionIsValid(candidate, context); });\r
        valid.sort(function (first, second) {\r
          return placementScore(first, context, reference, softWeight) - placementScore(second, context, reference, softWeight);\r
        });\r
        return valid.length ? valid[0] : null;\r
      }\r
      function applyPlacement(position, remember) {\r
        var useLeft = position.left + panel.offsetWidth / 2 <= window.innerWidth / 2;\r
        panel.setAttribute('data-docked', 'true');\r
        panel.setAttribute('data-dock-side', useLeft ? 'left' : 'right');\r
        if (useLeft) {\r
          panel.style.setProperty('--archify-radar-left', Math.round(position.left) + 'px');\r
          panel.style.removeProperty('--archify-radar-right');\r
        } else {\r
          panel.style.setProperty('--archify-radar-right', Math.round(window.innerWidth - position.left - panel.offsetWidth) + 'px');\r
          panel.style.removeProperty('--archify-radar-left');\r
        }\r
        panel.style.setProperty('--archify-radar-top', Math.round(position.top) + 'px');\r
        if (remember !== false) lastPlacement = { left: position.left, top: position.top };\r
      }\r
      function resetDockingStyles() {\r
        panel.removeAttribute('data-docked');\r
        panel.removeAttribute('data-dock-side');\r
        panel.removeAttribute('data-panel-dragging');\r
        panel.removeAttribute('data-placement-invalid');\r
        panel.removeAttribute('data-placement-degraded');\r
        panel.removeAttribute('data-placement-unavailable');\r
        panel.removeAttribute('data-compact');\r
        panel.removeAttribute('title');\r
        panel.style.removeProperty('visibility');\r
        panel.style.removeProperty('--archify-radar-right');\r
        panel.style.removeProperty('--archify-radar-left');\r
        panel.style.removeProperty('--archify-radar-top');\r
      }\r
      function updateDocking() {\r
        var options = arguments[0] || {};\r
        if (panel.hidden) return false;\r
        if (panelDrag) return true;\r
        panel.removeAttribute('data-compact');\r
        panel.removeAttribute('data-placement-degraded');\r
        panel.removeAttribute('data-placement-invalid');\r
        panel.removeAttribute('data-placement-unavailable');\r
        panel.removeAttribute('title');\r
        panel.style.removeProperty('visibility');\r
        var context = placementContext();\r
        if (!context) {\r
          resetDockingStyles();\r
          return false;\r
        }\r
        var reference = manualPosition || lastPlacement;\r
        var placementOptions = { softWeight: manualPosition ? 0 : 100 };\r
        var placement = manualPosition && positionIsValid(manualPosition, context)\r
          ? manualPosition\r
          : chooseRadarPlacement(context, reference, placementOptions);\r
        var compact = false;\r
        if (!placement && options.allowCompact !== false) {\r
          compact = true;\r
          panel.setAttribute('data-compact', 'true');\r
          panel.setAttribute('data-placement-degraded', 'true');\r
          panel.setAttribute('title', viewerText('viewer.radar.compacted'));\r
          context = placementContext();\r
          placement = chooseRadarPlacement(context, reference, placementOptions);\r
        }\r
        if (!placement) {\r
          resetDockingStyles();\r
          panel.setAttribute('data-placement-unavailable', 'true');\r
          return false;\r
        }\r
        if (manualPosition && !compact) manualPosition = { left: placement.left, top: placement.top };\r
        applyPlacement(placement, true);\r
        return true;\r
      }\r
      function clearSpaceRetry() {\r
        if (spaceRetryTimer) window.clearTimeout(spaceRetryTimer);\r
        spaceRetryTimer = 0;\r
      }\r
      function yieldPassport() {\r
        if (!passport || passport.hidden || passportYielded) return passportYielded;\r
        passportPreviousAriaHidden = passport.getAttribute('aria-hidden');\r
        passportYielded = true;\r
        passport.setAttribute('data-radar-yielded', 'true');\r
        passport.setAttribute('aria-hidden', 'true');\r
        return true;\r
      }\r
      function restorePassport() {\r
        if (!passport || !passportYielded) return;\r
        passportYielded = false;\r
        passport.removeAttribute('data-radar-yielded');\r
        if (passportPreviousAriaHidden === null) passport.removeAttribute('aria-hidden');\r
        else passport.setAttribute('aria-hidden', passportPreviousAriaHidden);\r
        passportPreviousAriaHidden = null;\r
      }\r
      function reflectVisible() {\r
        panel.hidden = false;\r
        panel.removeAttribute('data-placement-unavailable');\r
        trigger.setAttribute('aria-expanded', 'true');\r
        trigger.removeAttribute('data-radar-space-limited');\r
        trigger.setAttribute('aria-label', viewerText('viewer.radar.close'));\r
        trigger.title = viewerText('viewer.nav.radar.title');\r
        feedback.hidden = true;\r
      }\r
      function scheduleSpaceRetry() {\r
        if (!requestedOpen || spaceRetryTimer || spaceRetryCount >= 4) return;\r
        spaceRetryCount += 1;\r
        spaceRetryTimer = window.setTimeout(function () {\r
          spaceRetryTimer = 0;\r
          attemptRequestedOpen();\r
        }, 60);\r
      }\r
      function reflectUnavailable() {\r
        restorePassport();\r
        panel.hidden = true;\r
        panel.setAttribute('data-placement-unavailable', 'true');\r
        trigger.setAttribute('aria-expanded', 'false');\r
        trigger.setAttribute('aria-label', viewerText('viewer.radar.cancelWaiting'));\r
        trigger.setAttribute('data-radar-space-limited', 'true');\r
        trigger.title = viewerText('viewer.radar.needsSpace');\r
        feedback.hidden = false;\r
        scheduleSpaceRetry();\r
      }\r
      function attemptRequestedOpen(options) {\r
        options = options || {};\r
        if (!requestedOpen) return false;\r
        panel.hidden = false;\r
        if (!updateDocking(options)) {\r
          reflectUnavailable();\r
          return false;\r
        }\r
        clearSpaceRetry();\r
        spaceRetryCount = 0;\r
        reflectVisible();\r
        sync();\r
        if (options.focus === true && !panel.hasAttribute('data-compact')) surface.focus();\r
        return true;\r
      }\r
      function expandCompactRadar() {\r
        if (!requestedOpen || panel.hidden || !panel.hasAttribute('data-compact')) return false;\r
        yieldPassport();\r
        if (!updateDocking({ allowCompact: false })) {\r
          restorePassport();\r
          if (!updateDocking()) {\r
            reflectUnavailable();\r
            return false;\r
          }\r
        }\r
        reflectVisible();\r
        sync();\r
        if (!panel.hasAttribute('data-compact')) surface.focus();\r
        return !panel.hasAttribute('data-compact');\r
      }\r
      function syncNow() {\r
        syncFrame = 0;\r
        if (panel.hidden || !Archify.view || typeof Archify.view.logicalViewport !== 'function') return;\r
        if (!updateDocking()) {\r
          reflectUnavailable();\r
          return;\r
        }\r
        if (passportYielded && panel.hasAttribute('data-compact')) {\r
          restorePassport();\r
          if (!updateDocking()) {\r
            reflectUnavailable();\r
            return;\r
          }\r
        }\r
        reflectVisible();\r
        var visible = Archify.view.logicalViewport();\r
        if (!visible) return;\r
        viewport.setAttribute('x', String(visible.x));\r
        viewport.setAttribute('y', String(visible.y));\r
        viewport.setAttribute('width', String(visible.width));\r
        viewport.setAttribute('height', String(visible.height));\r
        var full = visible.width >= viewBox.width * 0.98 && visible.height >= viewBox.height * 0.98;\r
        var mobileWide = window.innerWidth <= 720 && container.hasAttribute('data-wide-diagram');\r
        var viewportCopy = full\r
          ? viewerText('viewer.radar.viewport.full')\r
          : (mobileWide\r
            ? viewerText('viewer.radar.viewport.width', { percent: Math.round(visible.width / viewBox.width * 100) })\r
            : viewerText('viewer.radar.viewport.scale', { percent: Math.round(visible.scale * 100) }));\r
        status.textContent = viewerText('viewer.radar.status', { count: nodes.length, viewport: viewportCopy });\r
        nodes.forEach(function (item) {\r
          var active = item.node.hasAttribute('data-focus-selected') ||\r
            item.node.getAttribute('data-story-beat-state') === 'active';\r
          if (active) item.rect.setAttribute('data-radar-active', 'true');\r
          else item.rect.removeAttribute('data-radar-active');\r
        });\r
      }\r
      function sync() {\r
        if (requestedOpen && panel.hidden) {\r
          attemptRequestedOpen();\r
          return;\r
        }\r
        if (syncFrame) return;\r
        syncFrame = requestAnimationFrame(syncNow);\r
      }\r
      function setOpen(next, options) {\r
        options = options || {};\r
        next = Boolean(next);\r
        if (next && Archify.semanticLens && typeof Archify.semanticLens.clearPreview === 'function') Archify.semanticLens.clearPreview();\r
        if (next && Archify.semanticLens && Archify.semanticLens.isOpen()) {\r
          Archify.semanticLens.close({ restoreFocus: false });\r
        }\r
        requestedOpen = next;\r
        if (next) {\r
          clearSpaceRetry();\r
          spaceRetryCount = 0;\r
          build();\r
          attemptRequestedOpen(options);\r
        } else {\r
          clearSpaceRetry();\r
          spaceRetryCount = 0;\r
          viewportDrag = null;\r
          panelDrag = null;\r
          container.classList.remove('is-panning');\r
          panel.hidden = true;\r
          resetDockingStyles();\r
          restorePassport();\r
          feedback.hidden = true;\r
          trigger.setAttribute('aria-expanded', 'false');\r
          trigger.removeAttribute('data-radar-space-limited');\r
          trigger.setAttribute('aria-label', viewerText('viewer.nav.radar'));\r
          trigger.title = viewerText('viewer.nav.radar.title');\r
          if (options.restoreFocus === true) trigger.focus();\r
        }\r
        return next;\r
      }\r
      function toggle() { return setOpen(!requestedOpen, { focus: false }); }\r
      function close(options) { return setOpen(false, options); }\r
      function bringNodeIntoWindow(node) {\r
        var delay = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 540;\r
        window.setTimeout(function () {\r
          var rect = node.getBoundingClientRect();\r
          var safeTop = 64;\r
          var safeBottom = window.innerHeight - 64;\r
          if (rect.top >= safeTop && rect.bottom <= safeBottom) return;\r
          var top = Math.max(0, window.scrollY + rect.top + rect.height / 2 - window.innerHeight / 2);\r
          try { window.scrollTo({ top: top, behavior: delay ? 'smooth' : 'auto' }); }\r
          catch (_) { window.scrollTo(0, top); }\r
        }, delay);\r
      }\r
      function focusNode(id) {\r
        var main = diagram.querySelector('[data-node-id="' + id + '"]');\r
        if (!main) return false;\r
        if (Archify.guidedViews && typeof Archify.guidedViews.showAll === 'function') {\r
          Archify.guidedViews.showAll({ clearFocus: false, updateUrl: false });\r
        }\r
        if (Archify.focus && typeof Archify.focus.set === 'function') {\r
          Archify.focus.set(id, { toggle: false });\r
        }\r
        if (Archify.view && typeof Archify.view.reveal === 'function') {\r
          Archify.view.reveal([id], { includeNeighbors: true, reason: 'radar' });\r
        }\r
        bringNodeIntoWindow(main);\r
        try { main.focus({ preventScroll: true }); } catch (_) { try { main.focus(); } catch (_) {} }\r
        sync();\r
        return true;\r
      }\r
      function diagramPoint(event) {\r
        var matrix = mapSvg.getScreenCTM();\r
        if (!matrix) return null;\r
        var point = mapSvg.createSVGPoint();\r
        point.x = event.clientX;\r
        point.y = event.clientY;\r
        return point.matrixTransform(matrix.inverse());\r
      }\r
      function navigate(event) {\r
        var point = diagramPoint(event);\r
        if (!point || !Archify.view || typeof Archify.view.centerAt !== 'function') return;\r
        Archify.view.centerAt(point.x, point.y, { minimumScale: 1.5, instant: true });\r
        sync();\r
      }\r
      function endViewportDrag(event) {\r
        if (!viewportDrag) return;\r
        viewportDrag = null;\r
        panel.removeAttribute('data-dragging');\r
        container.classList.remove('is-panning');\r
        try { surface.releasePointerCapture(event.pointerId); } catch (_) {}\r
      }\r
      function beginPanelDrag(event) {\r
        if (event.button !== 0 || event.target.closest('button, a, input, [role="button"]')) return;\r
        var context = placementContext();\r
        if (!context) return;\r
        var rect = panel.getBoundingClientRect();\r
        event.preventDefault();\r
        event.stopPropagation();\r
        panelDrag = {\r
          pointerId: event.pointerId,\r
          originX: event.clientX,\r
          originY: event.clientY,\r
          start: { left: rect.left, top: rect.top },\r
          current: { left: rect.left, top: rect.top },\r
          previousManual: manualPosition ? { left: manualPosition.left, top: manualPosition.top } : null\r
        };\r
        panel.setAttribute('data-panel-dragging', 'true');\r
        try { panelHead.setPointerCapture(event.pointerId); } catch (_) {}\r
      }\r
      function movePanelDrag(event) {\r
        if (!panelDrag || panelDrag.pointerId !== event.pointerId) return;\r
        var context = placementContext();\r
        if (!context) return;\r
        event.preventDefault();\r
        event.stopPropagation();\r
        var bounds = context.bounds;\r
        var position = {\r
          left: clamp(panelDrag.start.left + event.clientX - panelDrag.originX, bounds.left, bounds.right - panel.offsetWidth),\r
          top: clamp(panelDrag.start.top + event.clientY - panelDrag.originY, bounds.top, bounds.bottom - panel.offsetHeight)\r
        };\r
        panelDrag.current = position;\r
        if (positionIsValid(position, context)) panel.removeAttribute('data-placement-invalid');\r
        else panel.setAttribute('data-placement-invalid', 'true');\r
        applyPlacement(position, false);\r
      }\r
      function finishPanelDrag(event, cancel) {\r
        if (!panelDrag || panelDrag.pointerId !== event.pointerId) return;\r
        event.preventDefault();\r
        event.stopPropagation();\r
        var activeDrag = panelDrag;\r
        panelDrag = null;\r
        panel.removeAttribute('data-panel-dragging');\r
        panel.removeAttribute('data-placement-invalid');\r
        try { panelHead.releasePointerCapture(event.pointerId); } catch (_) {}\r
        var context = placementContext();\r
        if (!context) return;\r
        if (cancel) {\r
          manualPosition = activeDrag.previousManual;\r
          lastPlacement = { left: activeDrag.start.left, top: activeDrag.start.top };\r
          updateDocking();\r
          return;\r
        }\r
        var requested = activeDrag.current;\r
        manualPosition = { left: requested.left, top: requested.top };\r
        updateDocking();\r
      }\r
\r
      trigger.addEventListener('click', toggle);\r
      closeBtn.addEventListener('click', function () { close({ restoreFocus: true }); });\r
      expandBtn.addEventListener('click', expandCompactRadar);\r
      panelHead.addEventListener('pointerdown', beginPanelDrag);\r
      panelHead.addEventListener('pointermove', movePanelDrag);\r
      panelHead.addEventListener('pointerup', function (event) { finishPanelDrag(event, false); });\r
      panelHead.addEventListener('pointercancel', function (event) { finishPanelDrag(event, true); });\r
      surface.addEventListener('pointerdown', function (event) {\r
        if (event.button !== 0 || event.target.closest('[data-radar-node-id]')) return;\r
        event.preventDefault();\r
        viewportDrag = { pointerId: event.pointerId };\r
        panel.setAttribute('data-dragging', 'true');\r
        container.classList.add('is-panning');\r
        try { surface.setPointerCapture(event.pointerId); } catch (_) {}\r
        navigate(event);\r
      });\r
      surface.addEventListener('pointermove', function (event) {\r
        if (!viewportDrag || viewportDrag.pointerId !== event.pointerId) return;\r
        navigate(event);\r
      });\r
      surface.addEventListener('pointerup', endViewportDrag);\r
      surface.addEventListener('pointercancel', endViewportDrag);\r
      surface.addEventListener('click', function (event) {\r
        var node = event.target.closest('[data-radar-node-id]');\r
        if (node) focusNode(node.getAttribute('data-radar-node-id'));\r
      });\r
      surface.addEventListener('keydown', function (event) {\r
        if (event.key === 'Escape') {\r
          event.preventDefault();\r
          event.stopPropagation();\r
          close({ restoreFocus: true });\r
          return;\r
        }\r
        var node = event.target.closest('[data-radar-node-id]');\r
        if (node && (event.key === 'Enter' || event.key === ' ')) {\r
          event.preventDefault();\r
          focusNode(node.getAttribute('data-radar-node-id'));\r
          return;\r
        }\r
        if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight' && event.key !== 'ArrowUp' && event.key !== 'ArrowDown') return;\r
        var visible = Archify.view && Archify.view.logicalViewport ? Archify.view.logicalViewport() : null;\r
        if (!visible) return;\r
        event.preventDefault();\r
        var x = visible.x + visible.width / 2;\r
        var y = visible.y + visible.height / 2;\r
        var stepX = Math.max(12, visible.width * 0.24);\r
        var stepY = Math.max(12, visible.height * 0.24);\r
        if (event.key === 'ArrowLeft') x -= stepX;\r
        else if (event.key === 'ArrowRight') x += stepX;\r
        else if (event.key === 'ArrowUp') y -= stepY;\r
        else y += stepY;\r
        Archify.view.centerAt(x, y, { minimumScale: 1.5, instant: true });\r
        sync();\r
      });\r
      document.addEventListener('keydown', function (event) {\r
        if (!panelDrag || event.key !== 'Escape') return;\r
        finishPanelDrag({\r
          pointerId: panelDrag.pointerId,\r
          preventDefault: function () { event.preventDefault(); },\r
          stopPropagation: function () { event.stopPropagation(); }\r
        }, true);\r
      }, true);\r
      function reflow() {\r
        if (!requestedOpen) return;\r
        clearSpaceRetry();\r
        spaceRetryCount = 0;\r
        sync();\r
      }\r
      window.addEventListener('resize', reflow);\r
      window.addEventListener('scroll', reflow, { passive: true });\r
      if (typeof ResizeObserver === 'function') {\r
        var radarResizeObserver = new ResizeObserver(function (entries) {\r
          if (!requestedOpen) return;\r
          if (panel.hidden && entries.every(function (entry) { return entry.target === panel; })) return;\r
          reflow();\r
        });\r
        [container, navigation, document.getElementById('focus-chip'), panel].filter(Boolean).forEach(function (element) {\r
          radarResizeObserver.observe(element);\r
        });\r
      }\r
      requestAnimationFrame(build);\r
\r
      return {\r
        open: function () { return setOpen(true); },\r
        close: close,\r
        toggle: toggle,\r
        sync: sync,\r
        focus: focusNode,\r
        isOpen: function () { return requestedOpen; },\r
        count: function () { return nodes.length; }\r
      };\r
    })();\r
\r
    /* ============================================================\r
       Presentation Stage — a shareable, viewport-filling live view.\r
       It changes only HTML layout and URL state; SVG semantics and export\r
       serialization remain untouched. Escape first clears an active guided\r
       view/focus, then exits the stage.\r
       ============================================================ */\r
    Archify.presentation = (function () {\r
      var html = document.documentElement;\r
      var btn = document.getElementById('btn-present');\r
      var label = document.getElementById('present-label');\r
      var previousScrollY = 0;\r
\r
      function active() { return html.getAttribute('data-present') === 'true'; }\r
\r
      function updateUrl(next) {\r
        try {\r
          var url = new URL(window.location.href);\r
          if (next) url.searchParams.set('present', '1');\r
          else url.searchParams.delete('present');\r
          history.replaceState(null, '', url.pathname + url.search + url.hash);\r
        } catch (_) {}\r
      }\r
\r
      function render(next) {\r
        btn.setAttribute('aria-pressed', next ? 'true' : 'false');\r
        btn.setAttribute('aria-label', viewerText(next ? 'viewer.present.exit' : 'viewer.present.enter'));\r
        btn.title = viewerText(next ? 'viewer.present.exit.title' : 'viewer.present.enter.title');\r
        label.textContent = viewerText(next ? 'viewer.present.exit.label' : 'viewer.present.present');\r
      }\r
\r
      function setActive(next, options) {\r
        options = options || {};\r
        next = Boolean(next);\r
        if (next === active()) {\r
          render(next);\r
          return next;\r
        }\r
        if (next) {\r
          if (Archify.semanticLens && typeof Archify.semanticLens.clearPreview === 'function') Archify.semanticLens.clearPreview();\r
          previousScrollY = window.scrollY || 0;\r
          html.setAttribute('data-present', 'true');\r
          try { window.scrollTo(0, 0); } catch (_) {}\r
        } else {\r
          html.removeAttribute('data-present');\r
        }\r
        render(next);\r
        if (options.updateUrl !== false) updateUrl(next);\r
        requestAnimationFrame(function () {\r
          if (Archify.view && typeof Archify.view.reset === 'function') {\r
            Archify.view.reset({ automatic: true });\r
            requestAnimationFrame(function () {\r
              if (Archify.view && typeof Archify.view.sync === 'function') Archify.view.sync();\r
            });\r
          }\r
          if (!next && previousScrollY) {\r
            try { window.scrollTo(0, previousScrollY); } catch (_) {}\r
          }\r
        });\r
        return next;\r
      }\r
\r
      function toggle() { return setActive(!active()); }\r
\r
      render(active());\r
      btn.addEventListener('click', toggle);\r
\r
      return {\r
        enter: function () { return setActive(true); },\r
        exit: function () { return setActive(false); },\r
        toggle: toggle,\r
        active: active\r
      };\r
    })();\r
\r
    /* ============================================================\r
       Node Finder — stable-ID search over the existing semantic SVG.\r
       Search never changes the IR or SVG geometry: selecting a result resets\r
       the viewport, releases a guided view, and delegates to semantic focus.\r
       ============================================================ */\r
    Archify.finder = (function () {\r
      var html = document.documentElement;\r
      var container = document.querySelector('.diagram-container');\r
      var svg = container.querySelector('svg');\r
      var trigger = document.getElementById('btn-node-finder');\r
      var panel = document.getElementById('node-finder');\r
      var heading = document.getElementById('node-finder-title');\r
      var closeBtn = document.getElementById('node-finder-close');\r
      var input = document.getElementById('node-finder-input');\r
      var results = document.getElementById('node-finder-results');\r
      var empty = document.getElementById('node-finder-empty');\r
      var status = document.getElementById('node-finder-status');\r
      var visibleItems = [];\r
\r
      function defaultContext() {\r
        return {\r
          kind: 'focus',\r
          title: viewerText('viewer.finder.title'),\r
          placeholder: viewerText('viewer.finder.placeholder'),\r
          empty: viewerText('viewer.finder.empty'),\r
          resultsLabel: viewerText('viewer.finder.results'),\r
          availableNoun: viewerText('viewer.finder.noun.nodes'),\r
          allowedIds: null,\r
          badges: null\r
        };\r
      }\r
\r
      var context = defaultContext();\r
\r
      function semanticType(node) {\r
        var authored = node.getAttribute('data-node-kind');\r
        if (authored) return authored;\r
        var types = ['frontend', 'backend', 'database', 'cloud', 'security', 'messagebus', 'external'];\r
        return types.find(function (type) { return node.querySelector('.c-' + type); }) || 'node';\r
      }\r
\r
      function connectionsFor(id) {\r
        var count = 0;\r
        var seen = {};\r
        Array.prototype.forEach.call(svg.querySelectorAll('[data-edge-from][data-edge-to]'), function (edge) {\r
          var from = edge.getAttribute('data-edge-from');\r
          var to = edge.getAttribute('data-edge-to');\r
          var key = from + '\\u0000' + to;\r
          if ((from === id || to === id) && !seen[key]) {\r
            seen[key] = true;\r
            count += 1;\r
          }\r
        });\r
        return count;\r
      }\r
\r
      var items = Array.prototype.map.call(svg.querySelectorAll('[data-node-id]'), function (node) {\r
        var id = node.getAttribute('data-node-id');\r
        var label = node.getAttribute('data-node-label') || (node.getAttribute('aria-label') || id).replace(/^Focus\\s+/, '');\r
        var text = (node.textContent || '').replace(/\\s+/g, ' ').trim();\r
        var sublabel = node.getAttribute('data-node-sublabel') || '';\r
        var context = node.getAttribute('data-node-context') || '';\r
        var tag = node.getAttribute('data-node-tag') || '';\r
        var brand = node.getAttribute('data-node-brand') || '';\r
        var type = semanticType(node);\r
        var sources = Archify.sourceEvidence.node(id);\r
        var sourceSearch = sources.map(function (source) {\r
          return [source.path, source.label, source.line, source.endLine].filter(Boolean).join(' ');\r
        }).join(' ');\r
        return {\r
          id: id,\r
          label: label,\r
          type: type,\r
          sublabel: sublabel,\r
          context: context,\r
          tag: tag,\r
          brand: brand,\r
          sources: sources,\r
          links: connectionsFor(id),\r
          search: (id + ' ' + label + ' ' + type + ' ' + sublabel + ' ' + context + ' ' + tag + ' ' + sourceSearch + ' ' + text).toLowerCase() + ' ' + brand.toLowerCase(),\r
          node: node\r
        };\r
      });\r
\r
      function resultButtons() {\r
        return Array.prototype.slice.call(results.querySelectorAll('.node-finder-result'));\r
      }\r
\r
      function resolveContext(options) {\r
        var requested = options && options.context ? options.context : null;\r
        if (!requested && Archify.routeProbe && typeof Archify.routeProbe.finderContext === 'function') {\r
          requested = Archify.routeProbe.finderContext();\r
        }\r
        if (!requested) return defaultContext();\r
        var resolved = defaultContext();\r
        Object.keys(requested).forEach(function (key) { resolved[key] = requested[key]; });\r
        return resolved;\r
      }\r
\r
      function availableItems() {\r
        if (!context.allowedIds) return items.slice();\r
        return items.filter(function (item) { return context.allowedIds.indexOf(item.id) !== -1; });\r
      }\r
\r
      function applyContext() {\r
        panel.setAttribute('data-context', context.kind);\r
        heading.textContent = context.title;\r
        input.placeholder = context.placeholder;\r
        empty.textContent = context.empty;\r
        results.setAttribute('aria-label', context.resultsLabel);\r
      }\r
\r
      function select(id) {\r
        var item = items.find(function (candidate) { return candidate.id === id; });\r
        if (!item) return false;\r
        var routeSelection = context.kind === 'route-source' || context.kind === 'route-target';\r
        if (routeSelection) {\r
          if (!Archify.routeProbe || typeof Archify.routeProbe.choose !== 'function' || !Archify.routeProbe.choose(id)) return false;\r
          if (Archify.routeProbe.active() === 'target' && Archify.view && typeof Archify.view.reveal === 'function') {\r
            Archify.view.reveal([id], { includeNeighbors: true, reason: 'route-pick' });\r
          }\r
          close({ restoreFocus: false });\r
          try { item.node.focus({ preventScroll: true }); } catch (_) { try { item.node.focus(); } catch (_) {} }\r
          return true;\r
        }\r
        if (Archify.guidedViews && typeof Archify.guidedViews.showAll === 'function') {\r
          Archify.guidedViews.showAll({ clearFocus: false, updateUrl: false });\r
        }\r
        if (Archify.view && typeof Archify.view.reset === 'function') Archify.view.reset({ automatic: true });\r
        Archify.focus.set(id, { toggle: false });\r
        if (Archify.view && typeof Archify.view.reveal === 'function') {\r
          Archify.view.reveal([id], { includeNeighbors: true, reason: 'finder' });\r
        }\r
        close({ restoreFocus: false });\r
        try { item.node.focus({ preventScroll: true }); } catch (_) { try { item.node.focus(); } catch (_) {} }\r
        return true;\r
      }\r
\r
      function render(query) {\r
        query = (query || '').trim().toLowerCase();\r
        var available = availableItems();\r
        visibleItems = available.filter(function (item) { return !query || item.search.indexOf(query) !== -1; });\r
        results.textContent = '';\r
        visibleItems.forEach(function (item) {\r
          var button = document.createElement('button');\r
          button.type = 'button';\r
          button.className = 'node-finder-result';\r
          button.setAttribute('data-node-id', item.id);\r
          var badge = context.badges && context.badges[item.id]\r
            ? context.badges[item.id]\r
            : context.kind === 'focus'\r
              ? viewerCount('viewer.finder.link', item.links)\r
              : String(item.links);\r
          var action = context.kind === 'route-source'\r
            ? viewerText('viewer.finder.result.routeStart', { label: item.label })\r
            : context.kind === 'route-target'\r
              ? viewerText('viewer.finder.result.routeTarget', { label: item.label, links: badge })\r
              : viewerCount('viewer.finder.result.focus', item.links, { label: item.label });\r
          button.setAttribute('aria-label', action);\r
\r
          var name = document.createElement('strong');\r
          name.textContent = item.label;\r
          var links = document.createElement('em');\r
          links.textContent = badge;\r
          links.title = context.kind === 'focus' ? badge : action;\r
          var meta = document.createElement('small');\r
          meta.textContent = [viewerKindLabel(item.type), item.id, item.sublabel, item.tag].filter(Boolean).join(' \\u00b7 ');\r
          meta.title = [viewerKindLabel(item.type), item.id, item.context, item.sublabel, item.tag].filter(Boolean).join(' \\u00b7 ');\r
          button.appendChild(name);\r
          button.appendChild(links);\r
          button.appendChild(meta);\r
          button.addEventListener('click', function () { select(item.id); });\r
          results.appendChild(button);\r
        });\r
        empty.hidden = visibleItems.length !== 0;\r
        status.textContent = query\r
          ? viewerText('viewer.finder.status.filtered', {\r
              visible: visibleItems.length,\r
              available: available.length,\r
              noun: context.availableNoun\r
            })\r
          : viewerText('viewer.finder.status.all', { available: available.length, noun: context.availableNoun });\r
      }\r
\r
      function open(options) {\r
        if (html.getAttribute('data-embed') === 'true') return false;\r
        if (Archify.semanticLens && typeof Archify.semanticLens.clearPreview === 'function') Archify.semanticLens.clearPreview();\r
        if (Archify.exportMenu && Archify.exportMenu.isOpen()) Archify.exportMenu.close(false);\r
        if (Archify.semanticLens && Archify.semanticLens.isOpen()) Archify.semanticLens.close({ restoreFocus: false });\r
        context = resolveContext(options || {});\r
        applyContext();\r
        panel.hidden = false;\r
        trigger.setAttribute('aria-expanded', 'true');\r
        if (context.kind.indexOf('route-') === 0 && Archify.routeProbe && typeof Archify.routeProbe.finderOpening === 'function') {\r
          Archify.routeProbe.finderOpening();\r
        }\r
        input.value = '';\r
        render('');\r
        requestAnimationFrame(function () { input.focus(); });\r
        return true;\r
      }\r
\r
      function close(options) {\r
        options = options || {};\r
        var routeContext = context.kind.indexOf('route-') === 0;\r
        panel.hidden = true;\r
        trigger.setAttribute('aria-expanded', 'false');\r
        input.value = '';\r
        if (routeContext && Archify.routeProbe && typeof Archify.routeProbe.finderClosed === 'function') {\r
          Archify.routeProbe.finderClosed({ restoreFocus: options.restoreFocus !== false });\r
        } else if (options.restoreFocus !== false) {\r
          trigger.focus();\r
        }\r
      }\r
\r
      function toggle() { return panel.hidden ? open() : (close(), false); }\r
\r
      trigger.addEventListener('click', toggle);\r
      closeBtn.addEventListener('click', function () { close(); });\r
      input.addEventListener('input', function () { render(input.value); });\r
      input.addEventListener('keydown', function (event) {\r
        var buttons = resultButtons();\r
        if (event.key === 'ArrowDown' && buttons.length) {\r
          event.preventDefault();\r
          buttons[0].focus();\r
        } else if (event.key === 'Enter' && visibleItems.length) {\r
          event.preventDefault();\r
          select(visibleItems[0].id);\r
        }\r
      });\r
      results.addEventListener('keydown', function (event) {\r
        var buttons = resultButtons();\r
        var index = buttons.indexOf(document.activeElement);\r
        if (index < 0 || !buttons.length) return;\r
        var next = null;\r
        if (event.key === 'ArrowDown') next = (index + 1) % buttons.length;\r
        else if (event.key === 'ArrowUp') next = (index - 1 + buttons.length) % buttons.length;\r
        else if (event.key === 'Home') next = 0;\r
        else if (event.key === 'End') next = buttons.length - 1;\r
        if (next !== null) {\r
          event.preventDefault();\r
          buttons[next].focus();\r
        }\r
      });\r
      panel.addEventListener('keydown', function (event) {\r
        if (event.key !== 'Escape') return;\r
        event.preventDefault();\r
        event.stopPropagation();\r
        close();\r
      });\r
      document.addEventListener('click', function (event) {\r
        if (!panel.hidden && !panel.contains(event.target) && !event.target.closest('[data-node-finder-trigger]')) close({ restoreFocus: false });\r
      });\r
\r
      render('');\r
      return {\r
        open: open,\r
        close: close,\r
        toggle: toggle,\r
        select: select,\r
        isOpen: function () { return !panel.hidden; },\r
        context: function () { return context.kind; },\r
        count: items.length\r
      };\r
    })();\r
\r
    /* ============================================================\r
       Route Probe — shortest directed path over compiled semantics.\r
       The graph is read from renderer-owned stable IDs and relationship\r
       endpoints. BFS order follows authored DOM edge order, so equal-length\r
       choices are deterministic without adding weights or a graph runtime.\r
       ============================================================ */\r
    Archify.routeProbe = (function () {\r
      var html = document.documentElement;\r
      var container = document.querySelector('.diagram-container');\r
      var svg = container.querySelector(':scope > svg');\r
      var trigger = document.getElementById('btn-route-probe');\r
      var panel = document.getElementById('route-probe');\r
      var title = document.getElementById('route-probe-title');\r
      var path = document.getElementById('route-probe-path');\r
      var status = document.getElementById('route-probe-status');\r
      var findBtn = document.getElementById('route-probe-find');\r
      var copyBtn = document.getElementById('route-probe-copy');\r
      var clearBtn = document.getElementById('route-probe-clear');\r
      var journeyControls = document.getElementById('route-journey-controls');\r
      var journeyPrevBtn = document.getElementById('route-journey-prev');\r
      var journeyPlayBtn = document.getElementById('route-journey-play');\r
      var journeyPlayIcon = document.getElementById('route-journey-play-icon');\r
      var journeyPlayLabel = document.getElementById('route-journey-play-label');\r
      var journeyNextBtn = document.getElementById('route-journey-next');\r
      var journeyOverviewBtn = document.getElementById('route-journey-overview');\r
      var namespace = 'http://www.w3.org/2000/svg';\r
      var mode = 'idle';\r
      var startId = null;\r
      var endId = null;\r
      var activeNodeIds = [];\r
      var activeEdges = [];\r
      var journeyIndex = -1;\r
      var journeyPlaying = false;\r
      var journeyComplete = false;\r
      var journeyGeneration = 0;\r
      var journeyTimer = null;\r
      var journeyStartedAt = 0;\r
      var journeyElapsedMs = 0;\r
      var journeyOwnerToken = 0;\r
      var JOURNEY_DWELL_MS = 1100;\r
\r
      function nodes() {\r
        return Array.prototype.slice.call(svg.querySelectorAll('[data-node-id]'));\r
      }\r
      function edges() {\r
        return Array.prototype.slice.call(svg.querySelectorAll('[data-edge-from][data-edge-to][data-relation-class="direct_evolution"]'));\r
      }\r
      function nodesById() {\r
        var out = Object.create(null);\r
        nodes().forEach(function (node) { out[node.getAttribute('data-node-id')] = node; });\r
        return out;\r
      }\r
      function nodeLabel(node, fallback) {\r
        return node.getAttribute('data-node-label') ||\r
          (node.getAttribute('aria-label') || fallback).replace(/^Focus\\s+/, '').split(',')[0];\r
      }\r
      function exportSnapshot() {\r
        if (mode !== 'result' || activeNodeIds.length < 2 || activeEdges.length !== activeNodeIds.length - 1) return null;\r
        var allNodes = nodes();\r
        var byId = nodesById();\r
        var seenNodeIds = Object.create(null);\r
        var seenEdgeKeys = Object.create(null);\r
        if (startId !== activeNodeIds[0] || endId !== activeNodeIds[activeNodeIds.length - 1] ||\r
            activeNodeIds.some(function (id) {\r
              if (seenNodeIds[id] || allNodes.filter(function (node) {\r
                return node.getAttribute('data-node-id') === id;\r
              }).length !== 1) return true;\r
              seenNodeIds[id] = true;\r
              return !byId[id];\r
            }) ||\r
            activeEdges.some(function (edge, index) {\r
              if (!edge || !svg.contains(edge)) return true;\r
              var edgeKey = edge.getAttribute('data-edge-key');\r
              var edgeId = edge.getAttribute('data-edge-id') || '';\r
              if (!edgeKey || seenEdgeKeys[edgeKey]) return true;\r
              seenEdgeKeys[edgeKey] = true;\r
              var fragments = Array.prototype.slice.call(svg.querySelectorAll('[data-edge-key]')).filter(function (candidate) {\r
                return candidate.getAttribute('data-edge-key') === edgeKey;\r
              });\r
              var drawableFragments = fragments.filter(hasDrawableGeometry);\r
              return !fragments.length || !fragments.every(function (fragment) {\r
                return fragment.getAttribute('data-edge-from') === activeNodeIds[index] &&\r
                  fragment.getAttribute('data-edge-to') === activeNodeIds[index + 1] &&\r
                  (fragment.getAttribute('data-edge-id') || '') === edgeId;\r
              }) || drawableFragments.length !== 1 || drawableFragments[0] !== edge ||\r
                edge.getAttribute('data-edge-from') !== activeNodeIds[index] ||\r
                edge.getAttribute('data-edge-to') !== activeNodeIds[index + 1];\r
            })) return null;\r
        return {\r
          source: { id: startId, label: nodeLabel(byId[startId], startId) },\r
          target: { id: endId, label: nodeLabel(byId[endId], endId) },\r
          nodeIds: activeNodeIds.slice(),\r
          hops: activeEdges.length,\r
          edges: activeEdges.map(function (edge) {\r
            return {\r
              key: edge.getAttribute('data-edge-key'),\r
              id: edge.getAttribute('data-edge-id') || '',\r
              from: edge.getAttribute('data-edge-from'),\r
              to: edge.getAttribute('data-edge-to'),\r
              label: edge.getAttribute('data-edge-label') || ''\r
            };\r
          })\r
        };\r
      }\r
      function edgeShapes(edge) {\r
        if (/^(path|line|polyline)$/i.test(edge.tagName)) return [edge];\r
        return Array.prototype.slice.call(edge.querySelectorAll('path, line, polyline'));\r
      }\r
      function removeOverlay() {\r
        Array.prototype.forEach.call(svg.querySelectorAll('[data-route-probe-overlay]'), function (overlay) {\r
          overlay.remove();\r
        });\r
      }\r
      function removeJourneyPulse(options) {\r
        options = options || {};\r
        Array.prototype.forEach.call(svg.querySelectorAll('[data-route-journey-overlay]'), function (overlay) {\r
          overlay.remove();\r
        });\r
        if (journeyOwnerToken && options.release !== false && Archify.motionGovernor) {\r
          var token = journeyOwnerToken;\r
          journeyOwnerToken = 0;\r
          Archify.motionGovernor.release(token);\r
        }\r
      }\r
      function stopJourneyTimer(options) {\r
        options = options || {};\r
        journeyGeneration += 1;\r
        if (journeyTimer) {\r
          if (options.preserveElapsed === true && journeyStartedAt) {\r
            journeyElapsedMs = Math.min(JOURNEY_DWELL_MS, journeyElapsedMs + Math.max(0, Date.now() - journeyStartedAt));\r
          }\r
          window.clearTimeout(journeyTimer);\r
        }\r
        journeyTimer = null;\r
        journeyStartedAt = 0;\r
        if (options.preserveElapsed !== true) journeyElapsedMs = 0;\r
      }\r
      function clearJourneyPresentation(options) {\r
        options = options || {};\r
        removeJourneyPulse();\r
        svg.removeAttribute('data-route-journey');\r
        panel.removeAttribute('data-route-journey');\r
        nodes().forEach(function (node) {\r
          node.removeAttribute('data-route-journey-state');\r
          node.removeAttribute('data-route-journey-current');\r
        });\r
        edges().forEach(function (edge) {\r
          edge.removeAttribute('data-route-journey-state');\r
          edge.removeAttribute('data-route-journey-current');\r
        });\r
        Array.prototype.forEach.call(path.querySelectorAll('[data-route-journey-index]'), function (button, index) {\r
          button.removeAttribute('data-route-journey-state');\r
          button.removeAttribute('aria-current');\r
          button.setAttribute('tabindex', index === 0 ? '0' : '-1');\r
        });\r
        if (options.keepControls !== true) journeyControls.hidden = true;\r
        journeyControls.setAttribute('data-playing', 'false');\r
      }\r
      function resetJourneyState() {\r
        stopJourneyTimer();\r
        journeyPlaying = false;\r
        journeyComplete = false;\r
        journeyIndex = -1;\r
        clearJourneyPresentation();\r
      }\r
      function cleanSvgState() {\r
        resetJourneyState();\r
        svg.removeAttribute('data-route-picking');\r
        svg.removeAttribute('data-route-active');\r
        removeOverlay();\r
        nodes().forEach(function (node) {\r
          node.removeAttribute('data-route-match');\r
          node.removeAttribute('data-route-start');\r
          node.removeAttribute('data-route-end');\r
          node.removeAttribute('data-route-step');\r
          node.removeAttribute('data-route-candidate');\r
          node.style.removeProperty('--route-step');\r
        });\r
        edges().forEach(function (edge) {\r
          edge.removeAttribute('data-route-match');\r
          edge.removeAttribute('data-route-step');\r
          edge.style.removeProperty('--route-step');\r
        });\r
        panel.removeAttribute('data-route-dock');\r
      }\r
      function replaceRouteHash(value) {\r
        try {\r
          history.replaceState(null, '', location.pathname + location.search + (value ? '#route=' + value : ''));\r
        } catch (_) {}\r
      }\r
      function renderPlaceholder(copy) {\r
        path.textContent = '';\r
        var placeholder = document.createElement('span');\r
        placeholder.className = 'route-probe-placeholder';\r
        placeholder.textContent = copy;\r
        path.appendChild(placeholder);\r
      }\r
      function renderPath(ids, options) {\r
        options = options || {};\r
        var byId = nodesById();\r
        path.textContent = '';\r
        ids.forEach(function (id, index) {\r
          if (index) {\r
            var arrow = document.createElement('span');\r
            arrow.className = 'route-probe-arrow';\r
            arrow.setAttribute('aria-hidden', 'true');\r
            arrow.textContent = '\\u2192';\r
            path.appendChild(arrow);\r
          }\r
          var item = document.createElement(options.interactive === true ? 'button' : 'span');\r
          if (options.interactive === true) {\r
            item.type = 'button';\r
            item.setAttribute('data-route-journey-index', String(index));\r
            item.setAttribute('data-route-node-id', id);\r
            item.setAttribute('tabindex', index === 0 ? '0' : '-1');\r
            item.setAttribute('aria-label', viewerText('viewer.route.position', {\r
              index: index + 1,\r
              total: ids.length,\r
              label: nodeLabel(byId[id], id)\r
            }));\r
          }\r
          item.className = 'route-probe-node';\r
          item.textContent = nodeLabel(byId[id], id);\r
          item.title = nodeLabel(byId[id], id) + ' · ' + id;\r
          if (index === 0) item.setAttribute('data-endpoint', 'start');\r
          if (index === ids.length - 1 && ids.length > 1) item.setAttribute('data-endpoint', 'end');\r
          path.appendChild(item);\r
        });\r
      }\r
      function setTrigger(active) {\r
        trigger.setAttribute('aria-pressed', active ? 'true' : 'false');\r
        trigger.setAttribute('aria-label', viewerText(active ? 'viewer.route.trigger.clear' : 'viewer.guide.route.aria'));\r
      }\r
      function clear(options) {\r
        options = options || {};\r
        var wasActive = mode !== 'idle';\r
        if (Archify.finder && Archify.finder.isOpen() && typeof Archify.finder.context === 'function' && Archify.finder.context().indexOf('route-') === 0) {\r
          Archify.finder.close({ restoreFocus: false });\r
        }\r
        mode = 'idle';\r
        startId = null;\r
        endId = null;\r
        activeNodeIds = [];\r
        activeEdges = [];\r
        cleanSvgState();\r
        panel.hidden = true;\r
        panel.setAttribute('data-state', 'idle');\r
        panel.removeAttribute('data-finder-open');\r
        title.textContent = viewerText('viewer.route.start');\r
        renderPlaceholder(viewerText('viewer.route.pickTwo'));\r
        status.textContent = viewerText('viewer.route.instructions');\r
        findBtn.hidden = true;\r
        findBtn.textContent = viewerText('viewer.route.start.find');\r
        findBtn.setAttribute('aria-label', viewerText('viewer.route.start.find.aria'));\r
        copyBtn.hidden = true;\r
        copyBtn.textContent = viewerText('viewer.route.copy');\r
        if (Archify.exportMenu && typeof Archify.exportMenu.syncRouteShare === 'function') Archify.exportMenu.syncRouteShare();\r
        setTrigger(false);\r
        if (wasActive && options.preserveView !== true && Archify.view && typeof Archify.view.reset === 'function') {\r
          Archify.view.reset({ automatic: true });\r
        }\r
        if (options.updateUrl !== false) replaceRouteHash('');\r
        if (options.restoreFocus === true) trigger.focus();\r
      }\r
      function outgoingByNode() {\r
        var byId = nodesById();\r
        var outgoing = Object.create(null);\r
        edges().forEach(function (edge) {\r
          var from = edge.getAttribute('data-edge-from');\r
          var to = edge.getAttribute('data-edge-to');\r
          if (!byId[from] || !byId[to] || from === to) return;\r
          if (!outgoing[from]) outgoing[from] = [];\r
          outgoing[from].push({ edge: edge, to: to });\r
        });\r
        return outgoing;\r
      }\r
      function reachableFrom(source) {\r
        var outgoing = outgoingByNode();\r
        var reached = Object.create(null);\r
        var queue = [source];\r
        reached[source] = true;\r
        for (var cursor = 0; cursor < queue.length; cursor += 1) {\r
          var links = outgoing[queue[cursor]] || [];\r
          links.forEach(function (link) {\r
            if (reached[link.to]) return;\r
            reached[link.to] = true;\r
            queue.push(link.to);\r
          });\r
        }\r
        return reached;\r
      }\r
      function hopDistancesFrom(source) {\r
        var outgoing = outgoingByNode();\r
        var distances = Object.create(null);\r
        var queue = [source];\r
        distances[source] = 0;\r
        for (var cursor = 0; cursor < queue.length; cursor += 1) {\r
          var links = outgoing[queue[cursor]] || [];\r
          links.forEach(function (link) {\r
            if (Object.prototype.hasOwnProperty.call(distances, link.to)) return;\r
            distances[link.to] = distances[queue[cursor]] + 1;\r
            queue.push(link.to);\r
          });\r
        }\r
        return distances;\r
      }\r
      function shortestDirectedPath(source, target) {\r
        if (source === target) return null;\r
        var outgoing = outgoingByNode();\r
        var previous = Object.create(null);\r
        var queue = [source];\r
        previous[source] = null;\r
        for (var cursor = 0; cursor < queue.length && !Object.prototype.hasOwnProperty.call(previous, target); cursor += 1) {\r
          var links = outgoing[queue[cursor]] || [];\r
          links.some(function (link) {\r
            if (Object.prototype.hasOwnProperty.call(previous, link.to)) return false;\r
            previous[link.to] = { from: queue[cursor], edge: link.edge };\r
            queue.push(link.to);\r
            return link.to === target;\r
          });\r
        }\r
        if (!Object.prototype.hasOwnProperty.call(previous, target)) return null;\r
        var nodeIds = [target];\r
        var routeEdges = [];\r
        var current = target;\r
        while (current !== source) {\r
          var step = previous[current];\r
          if (!step) return null;\r
          routeEdges.unshift(step.edge);\r
          nodeIds.unshift(step.from);\r
          current = step.from;\r
        }\r
        return { nodes: nodeIds, edges: routeEdges };\r
      }\r
      function traceGeometry(shape, step) {\r
        var clone = shape.cloneNode(false);\r
        clone.removeAttribute('id');\r
        clone.removeAttribute('class');\r
        clone.removeAttribute('style');\r
        clone.removeAttribute('marker-start');\r
        clone.removeAttribute('marker-mid');\r
        clone.removeAttribute('marker-end');\r
        clone.removeAttribute('role');\r
        clone.removeAttribute('aria-label');\r
        clone.removeAttribute('aria-labelledby');\r
        clone.removeAttribute('data-animate');\r
        clone.removeAttribute('data-edge-from');\r
        clone.removeAttribute('data-edge-to');\r
        clone.removeAttribute('data-edge-key');\r
        clone.removeAttribute('data-edge-id');\r
        clone.removeAttribute('data-edge-label');\r
        clone.removeAttribute('data-route-match');\r
        clone.removeAttribute('data-route-step');\r
        clone.setAttribute('class', 'route-probe-flow');\r
        clone.setAttribute('pathLength', '1');\r
        clone.style.setProperty('--route-step', String(step));\r
        return clone;\r
      }\r
      function renderOverlay(routeEdges) {\r
        removeOverlay();\r
        if (!routeEdges.length) return;\r
        var overlay = document.createElementNS(namespace, 'g');\r
        overlay.setAttribute('class', 'route-probe-overlay');\r
        overlay.setAttribute('data-route-probe-overlay', '');\r
        overlay.setAttribute('aria-hidden', 'true');\r
        routeEdges.forEach(function (edge, step) {\r
          var wrapper = document.createElementNS(namespace, 'g');\r
          if (edge.hasAttribute('transform')) wrapper.setAttribute('transform', edge.getAttribute('transform'));\r
          edgeShapes(edge).forEach(function (shape) { wrapper.appendChild(traceGeometry(shape, step)); });\r
          if (wrapper.childNodes.length) overlay.appendChild(wrapper);\r
        });\r
        var firstNode = svg.querySelector('[data-node-id]');\r
        if (firstNode) svg.insertBefore(overlay, firstNode);\r
        else svg.appendChild(overlay);\r
      }\r
      function journeyButtons() {\r
        return Array.prototype.slice.call(path.querySelectorAll('[data-route-journey-index]'));\r
      }\r
      function journeyMotionAllowed() {\r
        return html.getAttribute('data-embed') !== 'true' &&\r
          !document.hidden &&\r
          Archify.motionGovernor &&\r
          Archify.motionGovernor.capable === true &&\r
          !Archify.motionGovernor.isPaused();\r
      }\r
      function routeOverviewStatus() {\r
        return viewerText('viewer.route.overview.status', {\r
          nodes: viewerCount('viewer.route.overview.node', activeNodeIds.length),\r
          hops: viewerCount('viewer.route.overview.hop', activeEdges.length)\r
        });\r
      }\r
      function centerJourneyButton(button) {\r
        if (!button) return;\r
        var target = button.offsetLeft - Math.max(0, (path.clientWidth - button.offsetWidth) / 2);\r
        path.scrollLeft = Math.max(0, target);\r
      }\r
      function focusJourneyButton(index) {\r
        var buttons = journeyButtons();\r
        if (!buttons.length) return false;\r
        var next = Math.max(0, Math.min(buttons.length - 1, index));\r
        buttons.forEach(function (button, buttonIndex) {\r
          button.setAttribute('tabindex', buttonIndex === next ? '0' : '-1');\r
        });\r
        try { buttons[next].focus({ preventScroll: true }); } catch (_) { buttons[next].focus(); }\r
        centerJourneyButton(buttons[next]);\r
        return true;\r
      }\r
      function renderJourneyControls() {\r
        var hasRoute = mode === 'result' && activeNodeIds.length > 1;\r
        var canPlay = hasRoute && journeyMotionAllowed();\r
        journeyControls.hidden = !hasRoute;\r
        journeyControls.setAttribute('data-playing', journeyPlaying ? 'true' : 'false');\r
        journeyPrevBtn.disabled = !hasRoute || journeyIndex <= 0;\r
        journeyNextBtn.disabled = !hasRoute || journeyIndex >= activeNodeIds.length - 1;\r
        journeyOverviewBtn.disabled = !hasRoute || journeyIndex < 0;\r
        journeyPlayBtn.disabled = !canPlay;\r
        journeyPlayBtn.setAttribute('aria-pressed', journeyPlaying ? 'true' : 'false');\r
        if (journeyPlaying) {\r
          journeyPlayIcon.textContent = '\\u275a\\u275a';\r
          journeyPlayLabel.textContent = viewerText('viewer.route.pause.label');\r
          journeyPlayBtn.setAttribute('aria-label', viewerText('viewer.route.pause'));\r
          journeyPlayBtn.title = viewerText('viewer.route.pause');\r
        } else if (journeyComplete || journeyIndex === activeNodeIds.length - 1) {\r
          journeyPlayIcon.textContent = '\\u21bb';\r
          journeyPlayLabel.textContent = viewerText('viewer.route.replay.label');\r
          journeyPlayBtn.setAttribute('aria-label', viewerText('viewer.route.replay'));\r
          journeyPlayBtn.title = viewerText(canPlay ? 'viewer.route.replay' : 'viewer.route.motionRequired');\r
        } else {\r
          journeyPlayIcon.textContent = '\\u25b6';\r
          journeyPlayLabel.textContent = viewerText('viewer.route.journey');\r
          journeyPlayBtn.setAttribute('aria-label', viewerText('viewer.route.play'));\r
          journeyPlayBtn.title = viewerText(canPlay ? 'viewer.route.play' : 'viewer.route.motionRequired');\r
        }\r
      }\r
      function journeyGeometry(shape) {\r
        var clone = shape.cloneNode(false);\r
        clone.removeAttribute('id');\r
        clone.removeAttribute('class');\r
        clone.removeAttribute('style');\r
        clone.removeAttribute('marker-start');\r
        clone.removeAttribute('marker-mid');\r
        clone.removeAttribute('marker-end');\r
        clone.removeAttribute('role');\r
        clone.removeAttribute('aria-label');\r
        clone.removeAttribute('aria-labelledby');\r
        clone.removeAttribute('data-animate');\r
        clone.removeAttribute('data-edge-from');\r
        clone.removeAttribute('data-edge-to');\r
        clone.removeAttribute('data-edge-key');\r
        clone.removeAttribute('data-edge-id');\r
        clone.removeAttribute('data-edge-label');\r
        clone.removeAttribute('data-route-match');\r
        clone.removeAttribute('data-route-step');\r
        clone.removeAttribute('data-route-journey-state');\r
        clone.removeAttribute('data-route-journey-current');\r
        clone.setAttribute('class', 'route-journey-flow');\r
        clone.setAttribute('pathLength', '1');\r
        return clone;\r
      }\r
      function renderJourneyPulse(edge) {\r
        removeJourneyPulse();\r
        if (!edge || !journeyMotionAllowed()) return false;\r
        var overlay = document.createElementNS(namespace, 'g');\r
        overlay.setAttribute('class', 'route-journey-overlay');\r
        overlay.setAttribute('data-route-journey-overlay', '');\r
        overlay.setAttribute('aria-hidden', 'true');\r
        var wrapper = document.createElementNS(namespace, 'g');\r
        if (edge.hasAttribute('transform')) wrapper.setAttribute('transform', edge.getAttribute('transform'));\r
        edgeShapes(edge).forEach(function (shape) { wrapper.appendChild(journeyGeometry(shape)); });\r
        if (!wrapper.childNodes.length) return false;\r
        overlay.appendChild(wrapper);\r
        var firstNode = svg.querySelector('[data-node-id]');\r
        if (firstNode) svg.insertBefore(overlay, firstNode);\r
        else svg.appendChild(overlay);\r
        if (Archify.motionGovernor && Archify.motionGovernor.capable) {\r
          var token = 0;\r
          token = Archify.motionGovernor.claim('route', function () {\r
            if (journeyOwnerToken === token) journeyOwnerToken = 0;\r
            removeJourneyPulse({ release: false });\r
          });\r
          journeyOwnerToken = token;\r
        }\r
        overlay.addEventListener('animationend', function () {\r
          if (overlay.isConnected) removeJourneyPulse();\r
        }, { once: true });\r
        window.setTimeout(function () {\r
          if (overlay.isConnected) removeJourneyPulse();\r
        }, 860);\r
        return true;\r
      }\r
      function applyJourneyState(index, options) {\r
        options = options || {};\r
        if (mode !== 'result' || !activeNodeIds.length) return false;\r
        var byId = nodesById();\r
        journeyIndex = Math.max(0, Math.min(activeNodeIds.length - 1, index));\r
        removeJourneyPulse();\r
        svg.setAttribute('data-route-journey', (journeyIndex + 1) + '/' + activeNodeIds.length);\r
        panel.setAttribute('data-route-journey', String(journeyIndex));\r
        activeNodeIds.forEach(function (id, step) {\r
          var node = byId[id];\r
          if (!node) return;\r
          var state = step < journeyIndex ? 'past' : (step === journeyIndex ? 'current' : 'future');\r
          node.setAttribute('data-route-journey-state', state);\r
          if (step === journeyIndex) node.setAttribute('data-route-journey-current', '');\r
          else node.removeAttribute('data-route-journey-current');\r
        });\r
        activeEdges.forEach(function (edge, step) {\r
          var destination = step + 1;\r
          var state = destination < journeyIndex ? 'past' : (destination === journeyIndex ? 'current' : 'future');\r
          edge.setAttribute('data-route-journey-state', state);\r
          if (destination === journeyIndex) edge.setAttribute('data-route-journey-current', '');\r
          else edge.removeAttribute('data-route-journey-current');\r
        });\r
        var buttons = journeyButtons();\r
        buttons.forEach(function (button, step) {\r
          var state = step < journeyIndex ? 'past' : (step === journeyIndex ? 'current' : 'future');\r
          button.setAttribute('data-route-journey-state', state);\r
          button.setAttribute('tabindex', step === journeyIndex ? '0' : '-1');\r
          if (step === journeyIndex) button.setAttribute('aria-current', 'step');\r
          else button.removeAttribute('aria-current');\r
        });\r
        if (options.center !== false) centerJourneyButton(buttons[journeyIndex]);\r
        var phase = viewerText(journeyPlaying\r
          ? 'viewer.route.phase.playing'\r
          : journeyComplete\r
            ? 'viewer.route.phase.complete'\r
            : 'viewer.route.phase.inspecting');\r
        status.textContent = viewerText('viewer.route.step', {\r
          index: journeyIndex + 1,\r
          total: activeNodeIds.length,\r
          phase: phase,\r
          label: nodeLabel(byId[activeNodeIds[journeyIndex]], activeNodeIds[journeyIndex])\r
        });\r
        if (options.pulse === true && journeyIndex > 0) renderJourneyPulse(activeEdges[journeyIndex - 1]);\r
        if (options.reveal !== false && Archify.view && typeof Archify.view.reveal === 'function') {\r
          Archify.view.reveal(activeNodeIds.slice(Math.max(0, journeyIndex - 1), Math.min(activeNodeIds.length, journeyIndex + 2)), {\r
            includeNeighbors: false,\r
            reason: 'route-journey',\r
            maxScale: 1.65,\r
            padding: 64,\r
            duration: 360,\r
            instant: !journeyMotionAllowed()\r
          });\r
        }\r
        renderJourneyControls();\r
        requestDocking();\r
        return true;\r
      }\r
      function pauseJourney(options) {\r
        options = options || {};\r
        if (!journeyPlaying && options.complete !== true) {\r
          renderJourneyControls();\r
          return false;\r
        }\r
        stopJourneyTimer({ preserveElapsed: options.complete !== true && options.preserveElapsed !== false });\r
        journeyPlaying = false;\r
        journeyComplete = options.complete === true;\r
        if (journeyComplete) journeyElapsedMs = 0;\r
        removeJourneyPulse();\r
        if (journeyIndex >= 0) applyJourneyState(journeyIndex, { center: false, pulse: false, reveal: false });\r
        else renderJourneyControls();\r
        return true;\r
      }\r
      function selectJourneyIndex(index) {\r
        if (mode !== 'result') return false;\r
        stopJourneyTimer();\r
        journeyPlaying = false;\r
        journeyComplete = false;\r
        return applyJourneyState(index, { pulse: true, reveal: true });\r
      }\r
      function showJourneyOverview(options) {\r
        options = options || {};\r
        if (mode !== 'result') return false;\r
        stopJourneyTimer();\r
        journeyPlaying = false;\r
        journeyComplete = false;\r
        journeyIndex = -1;\r
        clearJourneyPresentation({ keepControls: true });\r
        status.textContent = routeOverviewStatus();\r
        renderJourneyControls();\r
        if (options.reveal !== false && Archify.view && typeof Archify.view.reveal === 'function') {\r
          Archify.view.reveal(activeNodeIds, { includeNeighbors: false, reason: 'route', instant: !journeyMotionAllowed() });\r
        }\r
        requestDocking();\r
        return true;\r
      }\r
      function scheduleJourney() {\r
        if (!journeyPlaying || !journeyMotionAllowed()) {\r
          pauseJourney({ preserveElapsed: true });\r
          return false;\r
        }\r
        var generation = ++journeyGeneration;\r
        var remaining = Math.max(0, JOURNEY_DWELL_MS - journeyElapsedMs);\r
        journeyStartedAt = Date.now();\r
        journeyTimer = window.setTimeout(function () {\r
          if (generation !== journeyGeneration || !journeyPlaying) return;\r
          journeyTimer = null;\r
          journeyStartedAt = 0;\r
          journeyElapsedMs = 0;\r
          if (journeyIndex >= activeNodeIds.length - 1) {\r
            pauseJourney({ complete: true, preserveElapsed: false });\r
            return;\r
          }\r
          applyJourneyState(journeyIndex + 1, { pulse: true, reveal: true });\r
          // Camera and motion-owner handoff are allowed to synchronously\r
          // settle the previous step. The new step always starts with a fresh\r
          // dwell; never carry cleanup time into the next scheduler lease.\r
          journeyElapsedMs = 0;\r
          journeyStartedAt = 0;\r
          scheduleJourney();\r
        }, remaining);\r
        return true;\r
      }\r
      function playJourney() {\r
        if (mode !== 'result' || activeNodeIds.length < 2 || !journeyMotionAllowed()) {\r
          renderJourneyControls();\r
          return false;\r
        }\r
        if (journeyPlaying) return true;\r
        if (journeyComplete || journeyIndex >= activeNodeIds.length - 1) {\r
          journeyIndex = -1;\r
          journeyElapsedMs = 0;\r
          journeyComplete = false;\r
        }\r
        journeyPlaying = true;\r
        if (journeyIndex < 0) applyJourneyState(0, { pulse: false, reveal: true });\r
        else applyJourneyState(journeyIndex, { center: false, pulse: false, reveal: false });\r
        scheduleJourney();\r
        return true;\r
      }\r
      function toggleJourney() {\r
        return journeyPlaying ? pauseJourney({ preserveElapsed: true }) : playJourney();\r
      }\r
      function previousJourney() {\r
        return selectJourneyIndex(Math.max(0, journeyIndex < 0 ? 0 : journeyIndex - 1));\r
      }\r
      function nextJourney() {\r
        return selectJourneyIndex(Math.min(activeNodeIds.length - 1, journeyIndex + 1));\r
      }\r
      function overlapArea(a, b) {\r
        var width = Math.max(0, Math.min(a.right, b.right) - Math.max(a.left, b.left));\r
        var height = Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top));\r
        return width * height;\r
      }\r
      function updateDocking() {\r
        if (panel.hidden) {\r
          panel.removeAttribute('data-route-dock');\r
          return;\r
        }\r
        var containerRect = container.getBoundingClientRect();\r
        var width = panel.offsetWidth;\r
        var height = panel.offsetHeight;\r
        if (!width || !height) return;\r
        var currentRect = panel.getBoundingClientRect();\r
        var left = currentRect.left;\r
        var topCandidate = {\r
          left: left,\r
          right: left + width,\r
          top: containerRect.top + 8,\r
          bottom: containerRect.top + 8 + height\r
        };\r
        var nav = container.querySelector('.diagram-nav');\r
        var navRect = nav ? nav.getBoundingClientRect() : null;\r
        var bottom = navRect ? navRect.top - 9 : containerRect.bottom - 8;\r
        var bottomCandidate = {\r
          left: left,\r
          right: left + width,\r
          top: bottom - height,\r
          bottom: bottom\r
        };\r
        var byId = nodesById();\r
        var relevant = activeNodeIds.length ? activeNodeIds : (startId ? [startId] : []);\r
        var blockers = relevant.map(function (id) { return byId[id]; }).filter(Boolean).map(function (node) {\r
          return node.getBoundingClientRect();\r
        });\r
        function score(candidate) {\r
          var value = blockers.reduce(function (sum, rect) { return sum + overlapArea(candidate, rect); }, 0);\r
          if (navRect) value += overlapArea(candidate, navRect) * 4;\r
          if (candidate.top < containerRect.top || candidate.bottom > containerRect.bottom) value += 1000000;\r
          return value;\r
        }\r
        if (score(topCandidate) <= score(bottomCandidate)) panel.setAttribute('data-route-dock', 'top');\r
        else panel.setAttribute('data-route-dock', 'bottom');\r
      }\r
      function requestDocking() {\r
        requestAnimationFrame(updateDocking);\r
        window.setTimeout(updateDocking, 120);\r
        window.setTimeout(updateDocking, 560);\r
      }\r
      function chooseStart(id) {\r
        var byId = nodesById();\r
        if (!byId[id]) return false;\r
        cleanSvgState();\r
        startId = id;\r
        endId = null;\r
        mode = 'target';\r
        var reached = reachableFrom(id);\r
        byId[id].setAttribute('data-route-start', '');\r
        byId[id].setAttribute('data-route-match', '');\r
        Object.keys(reached).forEach(function (candidateId) {\r
          if (candidateId !== id && byId[candidateId]) byId[candidateId].setAttribute('data-route-candidate', '');\r
        });\r
        svg.setAttribute('data-route-picking', 'target');\r
        panel.setAttribute('data-state', 'target');\r
        title.textContent = viewerText('viewer.route.destination', { label: nodeLabel(byId[id], id) });\r
        renderPath([id]);\r
        var count = Math.max(0, Object.keys(reached).length - 1);\r
        status.textContent = count\r
          ? viewerCount('viewer.route.destination.count', count)\r
          : viewerText('viewer.route.noOutgoing');\r
        findBtn.hidden = false;\r
        findBtn.textContent = viewerText('viewer.route.destination.find');\r
        findBtn.setAttribute('aria-label', viewerText('viewer.route.destination.find.aria'));\r
        requestDocking();\r
        return true;\r
      }\r
      function showResult(result, options) {\r
        options = options || {};\r
        var byId = nodesById();\r
        cleanSvgState();\r
        mode = 'result';\r
        startId = result.nodes[0];\r
        endId = result.nodes[result.nodes.length - 1];\r
        activeNodeIds = result.nodes.slice();\r
        activeEdges = result.edges.slice();\r
        result.nodes.forEach(function (id, step) {\r
          var node = byId[id];\r
          if (!node) return;\r
          node.setAttribute('data-route-match', '');\r
          node.setAttribute('data-route-step', String(step));\r
          node.style.setProperty('--route-step', String(step));\r
          if (step === 0) node.setAttribute('data-route-start', '');\r
          if (step === result.nodes.length - 1) node.setAttribute('data-route-end', '');\r
        });\r
        result.edges.forEach(function (edge, step) {\r
          edge.setAttribute('data-route-match', '');\r
          edge.setAttribute('data-route-step', String(step));\r
          edge.style.setProperty('--route-step', String(step));\r
        });\r
        svg.setAttribute('data-route-active', startId + '~' + endId);\r
        renderOverlay(result.edges);\r
        renderPath(result.nodes, { interactive: true });\r
        panel.setAttribute('data-state', 'result');\r
        panel.hidden = false;\r
        title.textContent = viewerText('viewer.route.result.title', {\r
          source: nodeLabel(byId[startId], startId),\r
          target: nodeLabel(byId[endId], endId)\r
        });\r
        findBtn.hidden = true;\r
        copyBtn.hidden = false;\r
        setTrigger(true);\r
        if (Archify.exportMenu && typeof Archify.exportMenu.syncRouteShare === 'function') Archify.exportMenu.syncRouteShare();\r
        if (options.updateUrl !== false) {\r
          replaceRouteHash(encodeURIComponent(startId) + '~' + encodeURIComponent(endId));\r
        }\r
        showJourneyOverview({ reveal: false });\r
        if (Archify.view && typeof Archify.view.reveal === 'function') {\r
          Archify.view.reveal(result.nodes, { includeNeighbors: false, reason: 'route' });\r
        }\r
        return true;\r
      }\r
      function choose(id, options) {\r
        options = options || {};\r
        var byId = nodesById();\r
        if (!byId[id]) return false;\r
        if (mode === 'source') return chooseStart(id);\r
        if (mode !== 'target') return false;\r
        if (id === startId) {\r
          panel.setAttribute('data-state', 'error');\r
          title.textContent = viewerText('viewer.route.differentDestination');\r
          status.textContent = viewerText('viewer.route.distinct');\r
          return false;\r
        }\r
        var result = shortestDirectedPath(startId, id);\r
        if (!result) {\r
          panel.setAttribute('data-state', 'error');\r
          title.textContent = viewerText('viewer.route.unreachable', { label: nodeLabel(byId[id], id) });\r
          status.textContent = viewerText('viewer.route.unreachable.detail', {\r
            target: nodeLabel(byId[id], id),\r
            source: nodeLabel(byId[startId], startId)\r
          });\r
          return false;\r
        }\r
        return showResult(result, options);\r
      }\r
      function begin(options) {\r
        options = options || {};\r
        if (html.getAttribute('data-embed') === 'true') return false;\r
        if (Archify.semanticLens && typeof Archify.semanticLens.clearPreview === 'function') Archify.semanticLens.clearPreview();\r
        if (Archify.semanticLens && Archify.semanticLens.active()) {\r
          Archify.semanticLens.clear({ updateUrl: false, preserveView: true, closePanel: true });\r
        }\r
        var focused = options.source || (Archify.focus && typeof Archify.focus.active === 'function' ? Archify.focus.active() : null);\r
        if (Array.isArray(focused)) focused = null;\r
        clear({ updateUrl: false, preserveView: true, restoreFocus: false });\r
        if (Archify.intentTrace && typeof Archify.intentTrace.clear === 'function') Archify.intentTrace.clear({ announce: false });\r
        if (Archify.guidedViews && typeof Archify.guidedViews.showAll === 'function') {\r
          Archify.guidedViews.showAll({ clearFocus: false, updateUrl: false });\r
        }\r
        if (Archify.focus && typeof Archify.focus.clear === 'function') {\r
          Archify.focus.clear({ updateUrl: false, preserveView: true });\r
        }\r
        if (Archify.finder && Archify.finder.isOpen()) Archify.finder.close({ restoreFocus: false });\r
        if (Archify.radar && Archify.radar.isOpen()) Archify.radar.close({ restoreFocus: false });\r
        mode = 'source';\r
        panel.hidden = false;\r
        panel.setAttribute('data-state', 'source');\r
        svg.setAttribute('data-route-picking', 'source');\r
        title.textContent = viewerText('viewer.route.start');\r
        renderPlaceholder(viewerText('viewer.route.pickOne'));\r
        status.textContent = viewerText('viewer.route.start.instructions');\r
        findBtn.hidden = false;\r
        findBtn.textContent = viewerText('viewer.route.start.find');\r
        findBtn.setAttribute('aria-label', viewerText('viewer.route.start.find.aria'));\r
        copyBtn.hidden = true;\r
        setTrigger(true);\r
        if (focused && nodesById()[focused]) chooseStart(focused);\r
        if (options.focusNode === true && !focused) {\r
          var first = nodes()[0];\r
          if (first) {\r
            try { first.focus({ preventScroll: true }); } catch (_) { try { first.focus(); } catch (_) {} }\r
          }\r
        }\r
        return true;\r
      }\r
      function toggle(options) {\r
        if (mode !== 'idle') {\r
          clear({ restoreFocus: true });\r
          return false;\r
        }\r
        return begin(options);\r
      }\r
      function finderContext() {\r
        var byId = nodesById();\r
        if (mode === 'source') {\r
          var outgoing = outgoingByNode();\r
          var sourceIds = nodes().map(function (node) { return node.getAttribute('data-node-id'); }).filter(function (id) {\r
            return outgoing[id] && outgoing[id].length;\r
          });\r
          var sourceBadges = Object.create(null);\r
          sourceIds.forEach(function (id) { sourceBadges[id] = viewerText('viewer.route.finder.source.badge'); });\r
          return {\r
            kind: 'route-source',\r
            title: viewerText('viewer.route.finder.source.title'),\r
            placeholder: viewerText('viewer.route.finder.source.placeholder'),\r
            empty: viewerText('viewer.route.finder.source.empty'),\r
            resultsLabel: viewerText('viewer.route.finder.source.results'),\r
            availableNoun: viewerText('viewer.route.finder.source.noun'),\r
            allowedIds: sourceIds,\r
            badges: sourceBadges\r
          };\r
        }\r
        if (mode === 'target' && startId && byId[startId]) {\r
          var distances = hopDistancesFrom(startId);\r
          var targetIds = Object.keys(distances).filter(function (id) { return id !== startId && byId[id]; });\r
          var targetBadges = Object.create(null);\r
          targetIds.forEach(function (id) {\r
            targetBadges[id] = viewerCount('viewer.route.hop', distances[id]);\r
          });\r
          return {\r
            kind: 'route-target',\r
            title: viewerText('viewer.route.finder.target.title', { label: nodeLabel(byId[startId], startId) }),\r
            placeholder: viewerText('viewer.route.finder.target.placeholder'),\r
            empty: viewerText('viewer.route.finder.target.empty'),\r
            resultsLabel: viewerText('viewer.route.finder.target.results'),\r
            availableNoun: viewerText('viewer.route.finder.target.noun'),\r
            allowedIds: targetIds,\r
            badges: targetBadges\r
          };\r
        }\r
        return null;\r
      }\r
      function finderOpening() {\r
        panel.setAttribute('data-finder-open', 'true');\r
      }\r
      function finderClosed(options) {\r
        options = options || {};\r
        panel.removeAttribute('data-finder-open');\r
        requestDocking();\r
        if (options.restoreFocus === true && !findBtn.hidden) findBtn.focus();\r
      }\r
      function openFinder() {\r
        var context = finderContext();\r
        if (!context || !Archify.finder) return false;\r
        return Archify.finder.open({ context: context });\r
      }\r
      function fallbackCopy(value) {\r
        var field = document.createElement('textarea');\r
        field.value = value;\r
        field.setAttribute('readonly', '');\r
        field.style.position = 'fixed';\r
        field.style.opacity = '0';\r
        document.body.appendChild(field);\r
        field.select();\r
        var copied = false;\r
        try { copied = document.execCommand('copy'); } catch (_) {}\r
        field.remove();\r
        return copied;\r
      }\r
      function copyLink() {\r
        if (mode !== 'result') return Promise.resolve(false);\r
        var value = FlowBD.linkBase + '#route=' + encodeURIComponent(startId) + '~' + encodeURIComponent(endId);\r
        var copy = navigator.clipboard && typeof navigator.clipboard.writeText === 'function'\r
          ? navigator.clipboard.writeText(value).then(function () { return true; }).catch(function () { return fallbackCopy(value); })\r
          : Promise.resolve(fallbackCopy(value));\r
        return copy.then(function (copied) {\r
          copyBtn.textContent = viewerText(copied ? 'viewer.common.copied' : 'viewer.common.copyFailed');\r
          copyBtn.setAttribute('aria-label', viewerText(copied ? 'viewer.route.copy.success' : 'viewer.route.copy.failed'));\r
          window.setTimeout(function () {\r
            copyBtn.textContent = viewerText('viewer.route.copy');\r
            copyBtn.setAttribute('aria-label', viewerText('viewer.route.copy.aria'));\r
          }, 1600);\r
          return copied;\r
        });\r
      }\r
      function interceptSelection(event) {\r
        if (mode !== 'source' && mode !== 'target') return;\r
        if (container.getAttribute('data-just-panned') === 'true') return;\r
        var node = event.target.closest('[data-node-id]');\r
        if (!node) return;\r
        if (event.type === 'keydown' && event.key !== 'Enter' && event.key !== ' ') return;\r
        event.preventDefault();\r
        event.stopImmediatePropagation();\r
        choose(node.getAttribute('data-node-id'));\r
      }\r
      function syncFromHash() {\r
        try {\r
          var params = new URLSearchParams(location.hash.replace(/^#/, ''));\r
          var route = params.get('route');\r
          if (!route) {\r
            if (mode !== 'idle') clear({ updateUrl: false, restoreFocus: false });\r
            return;\r
          }\r
          var parts = route.split('~');\r
          if (parts.length !== 2) return;\r
          var byId = nodesById();\r
          if (!byId[parts[0]] || !byId[parts[1]]) return;\r
          begin({ source: parts[0], focusNode: false });\r
          choose(parts[1], { updateUrl: false });\r
        } catch (_) {}\r
      }\r
      function escapeRoute(options) {\r
        options = options || {};\r
        if (journeyPlaying) {\r
          pauseJourney({ preserveElapsed: true });\r
          if (options.restoreFocus === true) journeyPlayBtn.focus();\r
          return 'paused';\r
        }\r
        if (journeyIndex >= 0) {\r
          showJourneyOverview({ reveal: true });\r
          if (options.restoreFocus === true) journeyOverviewBtn.focus();\r
          return 'overview';\r
        }\r
        clear({ restoreFocus: options.restoreFocus === true });\r
        return 'cleared';\r
      }\r
      function syncJourneyMotion() {\r
        if (journeyPlaying && !journeyMotionAllowed()) pauseJourney({ preserveElapsed: true });\r
        renderJourneyControls();\r
        return journeyMotionAllowed();\r
      }\r
\r
      trigger.addEventListener('click', function () { toggle({ focusNode: false }); });\r
      findBtn.addEventListener('click', openFinder);\r
      clearBtn.addEventListener('click', function () { clear({ restoreFocus: true }); });\r
      copyBtn.addEventListener('click', copyLink);\r
      journeyPrevBtn.addEventListener('click', previousJourney);\r
      journeyPlayBtn.addEventListener('click', toggleJourney);\r
      journeyNextBtn.addEventListener('click', nextJourney);\r
      journeyOverviewBtn.addEventListener('click', function () { showJourneyOverview({ reveal: true }); });\r
      path.addEventListener('click', function (event) {\r
        var button = event.target.closest('[data-route-journey-index]');\r
        if (!button) return;\r
        selectJourneyIndex(Number(button.getAttribute('data-route-journey-index')));\r
      });\r
      path.addEventListener('focusin', function (event) {\r
        if (journeyPlaying && event.target.closest('[data-route-journey-index]')) pauseJourney({ preserveElapsed: true });\r
      });\r
      path.addEventListener('keydown', function (event) {\r
        var button = event.target.closest('[data-route-journey-index]');\r
        if (!button) return;\r
        var index = Number(button.getAttribute('data-route-journey-index'));\r
        var next = null;\r
        if (event.key === 'ArrowRight') next = Math.min(activeNodeIds.length - 1, index + 1);\r
        else if (event.key === 'ArrowLeft') next = Math.max(0, index - 1);\r
        else if (event.key === 'Home') next = 0;\r
        else if (event.key === 'End') next = activeNodeIds.length - 1;\r
        if (next !== null) {\r
          event.preventDefault();\r
          focusJourneyButton(next);\r
          return;\r
        }\r
        if (event.key === 'Enter' || event.key === ' ') {\r
          event.preventDefault();\r
          selectJourneyIndex(index);\r
        }\r
      });\r
      svg.addEventListener('click', interceptSelection, true);\r
      svg.addEventListener('keydown', interceptSelection, true);\r
      container.addEventListener('scroll', updateDocking, { passive: true });\r
      window.addEventListener('resize', requestDocking);\r
      window.addEventListener('beforeprint', function () {\r
        if (journeyPlaying) pauseJourney({ preserveElapsed: true, reason: 'print' });\r
        else removeJourneyPulse();\r
      });\r
      window.addEventListener('hashchange', function () { requestAnimationFrame(syncFromHash); });\r
      syncFromHash();\r
\r
      return {\r
        begin: begin,\r
        choose: choose,\r
        clear: clear,\r
        toggle: toggle,\r
        escape: escapeRoute,\r
        copyLink: copyLink,\r
        playJourney: playJourney,\r
        pauseJourney: pauseJourney,\r
        showOverview: showJourneyOverview,\r
        selectJourneyIndex: selectJourneyIndex,\r
        syncMotion: syncJourneyMotion,\r
        isJourneyPlaying: function () { return journeyPlaying; },\r
        finderContext: finderContext,\r
        finderOpening: finderOpening,\r
        finderClosed: finderClosed,\r
        openFinder: openFinder,\r
        exportSnapshot: exportSnapshot,\r
        active: function () { return mode === 'idle' ? null : mode; },\r
        result: function () {\r
          return mode === 'result'\r
            ? { source: startId, target: endId, nodes: activeNodeIds.slice(), hops: activeEdges.length, journey: journeyIndex, playing: journeyPlaying }\r
            : null;\r
        }\r
      };\r
    })();\r
\r
    /* ============================================================\r
       Semantic Lens — a counted, viewer-only legend over data-node-kind.\r
       One selected kind reveals every authored relationship touching it.\r
       Two selected kinds compare only direct cross-kind relationships while\r
       preserving the full diagram as a dimmed spatial reference.\r
       ============================================================ */\r
    Archify.semanticLens = (function () {\r
      var html = document.documentElement;\r
      var container = document.querySelector('.diagram-container');\r
      var svg = container.querySelector(':scope > svg');\r
      var trigger = document.getElementById('btn-semantic-lens');\r
      var panel = document.getElementById('semantic-lens');\r
      var closeBtn = document.getElementById('semantic-lens-close');\r
      var kindsRoot = document.getElementById('semantic-lens-kinds');\r
      var status = document.getElementById('semantic-lens-status');\r
      var copyBtn = document.getElementById('semantic-lens-copy');\r
      var clearBtn = document.getElementById('semantic-lens-clear');\r
      var legendBridge = svg.querySelector('[data-legend-bridge]');\r
      var legendEntries = [];\r
      var hoveredLegendEntry = null;\r
      var focusedLegendEntry = null;\r
      var activeLegendPreview = null;\r
      var lensOpener = trigger;\r
      var selectedKinds = [];\r
      var namespace = 'http://www.w3.org/2000/svg';\r
      var finePointerQuery = window.matchMedia ? window.matchMedia('(hover: hover) and (pointer: fine)') : null;\r
      var MAX_LENS_FLOW_EDGES = 24;\r
\r
      function nodesById() {\r
        var byId = Object.create(null);\r
        Array.prototype.forEach.call(svg.querySelectorAll('[data-node-id][data-node-kind]'), function (node) {\r
          var id = node.getAttribute('data-node-id');\r
          if (id && !byId[id]) byId[id] = node;\r
        });\r
        return byId;\r
      }\r
      function collectKinds() {\r
        var kinds = {};\r
        var byId = nodesById();\r
        Object.keys(byId).forEach(function (id) {\r
          var node = byId[id];\r
          var value = node.getAttribute('data-node-kind') || 'neutral';\r
          var kind = kinds[value] || (kinds[value] = { id: value, label: viewerKindLabel(value), nodes: [] });\r
          kind.nodes.push(node);\r
        });\r
        return Object.keys(kinds).map(function (key) { return kinds[key]; }).sort(function (a, b) {\r
          return b.nodes.length - a.nodes.length || a.label.localeCompare(b.label);\r
        });\r
      }\r
      function edgeGroups() {\r
        var groups = {};\r
        Array.prototype.forEach.call(svg.querySelectorAll('[data-edge-from][data-edge-to]'), function (edge) {\r
          var from = edge.getAttribute('data-edge-from');\r
          var to = edge.getAttribute('data-edge-to');\r
          var key = edge.getAttribute('data-edge-key') || [from, to, edge.getAttribute('data-edge-label') || ''].join('\\u0000');\r
          if (!groups[key]) groups[key] = { key: key, from: from, to: to, members: [] };\r
          groups[key].members.push(edge);\r
        });\r
        return Object.keys(groups).map(function (key) { return groups[key]; });\r
      }\r
      function edgeShapes(edge) {\r
        if (!edge) return [];\r
        if (/^(path|line|polyline)$/i.test(edge.tagName || '')) return [edge];\r
        return Array.prototype.slice.call(edge.querySelectorAll('path, line, polyline'));\r
      }\r
      function legendSourceBounds(entry) {\r
        var bounds = null;\r
        Array.prototype.forEach.call(entry.children, function (child) {\r
          if (child.hasAttribute('data-legend-bridge-runtime')) return;\r
          var box;\r
          try { box = child.getBBox(); } catch (_) { return; }\r
          if (!box || !Number.isFinite(box.x) || !Number.isFinite(box.y)) return;\r
          var next = { left: box.x, top: box.y, right: box.x + box.width, bottom: box.y + box.height };\r
          if (!bounds) bounds = next;\r
          else {\r
            bounds.left = Math.min(bounds.left, next.left);\r
            bounds.top = Math.min(bounds.top, next.top);\r
            bounds.right = Math.max(bounds.right, next.right);\r
            bounds.bottom = Math.max(bounds.bottom, next.bottom);\r
          }\r
        });\r
        return bounds;\r
      }\r
      function layoutLegendEntry(entry) {\r
        var bounds = legendSourceBounds(entry);\r
        var hit = entry.querySelector('[data-legend-hit]');\r
        var badge = entry.querySelector('[data-legend-count-badge]');\r
        if (!bounds || !hit || !badge) return false;\r
        var count = entry.getAttribute('data-legend-count') || '0';\r
        var centerY = (bounds.top + bounds.bottom) / 2;\r
        var badgeWidth = Math.max(14, count.length * 5 + 8);\r
        var badgeX = bounds.right + 3;\r
        var hitX = bounds.left - 5;\r
        var hitRight = badgeX + badgeWidth + 4;\r
        hit.setAttribute('x', hitX.toFixed(2));\r
        hit.setAttribute('y', (centerY - 12).toFixed(2));\r
        hit.setAttribute('width', Math.max(24, hitRight - hitX).toFixed(2));\r
        hit.setAttribute('height', '24');\r
        hit.setAttribute('rx', '4');\r
        var badgeRect = badge.querySelector('rect');\r
        var badgeText = badge.querySelector('text');\r
        badgeRect.setAttribute('x', badgeX.toFixed(2));\r
        badgeRect.setAttribute('y', (centerY - 7).toFixed(2));\r
        badgeRect.setAttribute('width', badgeWidth.toFixed(2));\r
        badgeRect.setAttribute('height', '14');\r
        badgeRect.setAttribute('rx', '7');\r
        badgeText.setAttribute('x', (badgeX + badgeWidth / 2).toFixed(2));\r
        badgeText.setAttribute('y', (centerY + 2.5).toFixed(2));\r
        return true;\r
      }\r
      function layoutLegendBridge() {\r
        legendEntries.forEach(layoutLegendEntry);\r
        if (!legendBridge) return;\r
        Array.prototype.forEach.call(legendBridge.querySelectorAll('[data-legend-zero]'), layoutLegendEntry);\r
      }\r
      function decorateLegendBridge() {\r
        legendEntries = [];\r
        if (!legendBridge || html.getAttribute('data-embed') === 'true') return false;\r
        var facts = {};\r
        collectKinds().forEach(function (kind) { facts[kind.id] = kind; });\r
        Array.prototype.forEach.call(legendBridge.querySelectorAll('[data-legend-kind]'), function (entry) {\r
          var kind = entry.getAttribute('data-legend-kind');\r
          var fact = facts[kind];\r
          var count = fact ? fact.nodes.length : 0;\r
          entry.setAttribute('data-legend-count', String(count));\r
          var hit = document.createElementNS(namespace, 'rect');\r
          hit.setAttribute('data-legend-bridge-runtime', '');\r
          hit.setAttribute('data-legend-hit', '');\r
          hit.setAttribute('aria-hidden', 'true');\r
          entry.insertBefore(hit, entry.firstChild);\r
          var badge = document.createElementNS(namespace, 'g');\r
          badge.setAttribute('data-legend-bridge-runtime', '');\r
          badge.setAttribute('data-legend-count-badge', '');\r
          badge.setAttribute('aria-hidden', 'true');\r
          badge.appendChild(document.createElementNS(namespace, 'rect'));\r
          var countText = document.createElementNS(namespace, 'text');\r
          countText.textContent = String(count);\r
          badge.appendChild(countText);\r
          entry.appendChild(badge);\r
          if (!fact || !count) {\r
            entry.setAttribute('data-legend-zero', '');\r
            return;\r
          }\r
          entry.setAttribute('role', 'button');\r
          entry.setAttribute('tabindex', legendEntries.length ? '-1' : '0');\r
          var visibleLabel = entry.getAttribute('data-legend-label') || fact.label;\r
          entry.setAttribute('aria-label', viewerCount('viewer.lens.legend.inspect', count, { label: visibleLabel }));\r
          entry.setAttribute('aria-pressed', 'false');\r
          entry.setAttribute('aria-haspopup', 'dialog');\r
          entry.setAttribute('aria-controls', 'semantic-lens');\r
          entry.setAttribute('aria-expanded', 'false');\r
          legendEntries.push(entry);\r
        });\r
        if (!legendEntries.length) return false;\r
        legendBridge.setAttribute('role', legendEntries.length >= 3 ? 'toolbar' : 'group');\r
        legendBridge.setAttribute('aria-label', viewerText('viewer.lens.legend'));\r
        syncLegendBridge();\r
        layoutLegendBridge();\r
        try {\r
          if (document.fonts && document.fonts.ready) document.fonts.ready.then(layoutLegendBridge);\r
        } catch (_) {}\r
        return true;\r
      }\r
      function syncLegendBridge() {\r
        legendEntries.forEach(function (entry) {\r
          var selected = selectedKinds.indexOf(entry.getAttribute('data-legend-kind')) >= 0;\r
          entry.setAttribute('aria-pressed', selected ? 'true' : 'false');\r
          entry.setAttribute('aria-expanded', !panel.hidden && lensOpener === entry ? 'true' : 'false');\r
          if (selected) entry.setAttribute('data-legend-selected', '');\r
          else entry.removeAttribute('data-legend-selected');\r
        });\r
      }\r
      function clearLegendPreview() {\r
        activeLegendPreview = null;\r
        svg.removeAttribute('data-legend-preview-active');\r
        Array.prototype.forEach.call(svg.querySelectorAll('[data-legend-preview-match], [data-legend-preview-selected], [data-legend-preview-peer]'), function (element) {\r
          element.removeAttribute('data-legend-preview-match');\r
          element.removeAttribute('data-legend-preview-selected');\r
          element.removeAttribute('data-legend-preview-peer');\r
        });\r
      }\r
      function strongerLegendOwnerActive() {\r
        return selectedKinds.length > 0 || !panel.hidden || html.getAttribute('data-present') === 'true' ||\r
          svg.hasAttribute('data-focus-active') || svg.hasAttribute('data-intent-trace-active') ||\r
          svg.hasAttribute('data-route-picking') || svg.hasAttribute('data-route-active') ||\r
          svg.hasAttribute('data-story-active') || svg.hasAttribute('data-relationship-preview-active');\r
      }\r
      function previewLegendKind(entry) {\r
        clearLegendPreview();\r
        if (!entry || strongerLegendOwnerActive()) return false;\r
        var kind = entry.getAttribute('data-legend-kind');\r
        var byId = nodesById();\r
        var matches = Object.keys(byId).filter(function (id) {\r
          return (byId[id].getAttribute('data-node-kind') || 'neutral') === kind;\r
        });\r
        if (!matches.length) return false;\r
        var chosen = Object.create(null);\r
        matches.forEach(function (id) {\r
          chosen[id] = true;\r
          byId[id].setAttribute('data-legend-preview-match', '');\r
          byId[id].setAttribute('data-legend-preview-selected', '');\r
        });\r
        edgeGroups().forEach(function (edge) {\r
          if (!chosen[edge.from] && !chosen[edge.to]) return;\r
          edge.members.forEach(function (member) { member.setAttribute('data-legend-preview-match', ''); });\r
          [edge.from, edge.to].forEach(function (id) {\r
            if (!byId[id] || chosen[id]) return;\r
            byId[id].setAttribute('data-legend-preview-match', '');\r
            byId[id].setAttribute('data-legend-preview-peer', '');\r
          });\r
        });\r
        svg.setAttribute('data-legend-preview-active', kind);\r
        activeLegendPreview = entry;\r
        return true;\r
      }\r
      function syncLegendPreview() {\r
        var next = focusedLegendEntry || hoveredLegendEntry;\r
        if (next === activeLegendPreview) return;\r
        clearLegendPreview();\r
        if (next) previewLegendKind(next);\r
      }\r
      function activateLegendEntry(entry) {\r
        if (!entry || entry.getAttribute('role') !== 'button') return false;\r
        clearLegendPreview();\r
        select(entry.getAttribute('data-legend-kind'));\r
        return open({ opener: entry });\r
      }\r
      function removeFlowOverlay() {\r
        Array.prototype.forEach.call(svg.querySelectorAll('[data-semantic-lens-overlay]'), function (element) {\r
          element.remove();\r
        });\r
        svg.removeAttribute('data-lens-flow-count');\r
        svg.removeAttribute('data-lens-flow-density');\r
      }\r
      function flowGeometry(shape, direction, step) {\r
        var clone = shape.cloneNode(false);\r
        clone.removeAttribute('id');\r
        clone.removeAttribute('class');\r
        clone.removeAttribute('style');\r
        clone.removeAttribute('marker-start');\r
        clone.removeAttribute('marker-mid');\r
        clone.removeAttribute('marker-end');\r
        clone.removeAttribute('role');\r
        clone.removeAttribute('aria-label');\r
        clone.removeAttribute('aria-hidden');\r
        clone.removeAttribute('data-animate');\r
        clone.removeAttribute('data-edge-from');\r
        clone.removeAttribute('data-edge-to');\r
        clone.removeAttribute('data-edge-key');\r
        clone.removeAttribute('data-edge-id');\r
        clone.removeAttribute('data-edge-label');\r
        clone.removeAttribute('data-lens-match');\r
        clone.setAttribute('class', 'semantic-lens-flow');\r
        clone.setAttribute('data-direction', direction);\r
        clone.setAttribute('pathLength', '1');\r
        clone.style.setProperty('--lens-flow-delay', (step * 0.08).toFixed(2) + 's');\r
        return clone;\r
      }\r
      function renderFlowOverlay(entries) {\r
        removeFlowOverlay();\r
        svg.setAttribute('data-lens-flow-count', String(entries.length));\r
        if (!entries.length || html.getAttribute('data-embed') === 'true') return false;\r
        if (entries.length > MAX_LENS_FLOW_EDGES) {\r
          svg.setAttribute('data-lens-flow-density', 'quiet');\r
          return false;\r
        }\r
        var overlay = document.createElementNS(namespace, 'g');\r
        overlay.setAttribute('class', 'semantic-lens-overlay');\r
        overlay.setAttribute('data-semantic-lens-overlay', '');\r
        overlay.setAttribute('aria-hidden', 'true');\r
        entries.forEach(function (entry, step) {\r
          var wrapper = document.createElementNS(namespace, 'g');\r
          if (entry.edge.members[0].hasAttribute('transform')) {\r
            wrapper.setAttribute('transform', entry.edge.members[0].getAttribute('transform'));\r
          }\r
          edgeShapes(entry.edge.members[0]).forEach(function (shape) {\r
            wrapper.appendChild(flowGeometry(shape, entry.direction, step));\r
          });\r
          if (wrapper.childNodes.length) overlay.appendChild(wrapper);\r
        });\r
        if (!overlay.childNodes.length) return false;\r
        var firstNode = svg.querySelector('[data-node-id]');\r
        if (firstNode) svg.insertBefore(overlay, firstNode);\r
        else svg.appendChild(overlay);\r
        return true;\r
      }\r
      function cleanSvgState() {\r
        removeFlowOverlay();\r
        svg.removeAttribute('data-lens-active');\r
        Array.prototype.forEach.call(svg.querySelectorAll('[data-lens-match], [data-lens-selected], [data-lens-peer]'), function (element) {\r
          element.removeAttribute('data-lens-match');\r
          element.removeAttribute('data-lens-selected');\r
          element.removeAttribute('data-lens-peer');\r
        });\r
      }\r
      function renderKinds() {\r
        kindsRoot.textContent = '';\r
        collectKinds().forEach(function (kind) {\r
          var button = document.createElement('button');\r
          button.type = 'button';\r
          button.className = 'semantic-lens-kind';\r
          button.setAttribute('data-kind', kind.id);\r
          button.setAttribute('aria-pressed', selectedKinds.indexOf(kind.id) >= 0 ? 'true' : 'false');\r
          button.setAttribute('aria-label', viewerCount('viewer.lens.kind.count', kind.nodes.length, { label: kind.label }));\r
          button.disabled = selectedKinds.length >= 2 && selectedKinds.indexOf(kind.id) === -1;\r
          var swatch = document.createElement('span');\r
          swatch.className = 'semantic-lens-swatch';\r
          swatch.setAttribute('aria-hidden', 'true');\r
          var label = document.createElement('strong');\r
          label.textContent = kind.label;\r
          var count = document.createElement('em');\r
          count.textContent = String(kind.nodes.length);\r
          button.appendChild(swatch);\r
          button.appendChild(label);\r
          button.appendChild(count);\r
          kindsRoot.appendChild(button);\r
        });\r
      }\r
      function updateHash() {\r
        try {\r
          var hash = selectedKinds.length\r
            ? '#lens=' + selectedKinds.map(encodeURIComponent).join('~')\r
            : '';\r
          history.replaceState(null, '', location.pathname + location.search + hash);\r
        } catch (_) {}\r
      }\r
      function updateTrigger() {\r
        var active = selectedKinds.length > 0;\r
        trigger.setAttribute('aria-pressed', active ? 'true' : 'false');\r
        trigger.setAttribute('aria-label', viewerText(active ? 'viewer.lens.openActive' : 'viewer.lens.open'));\r
        copyBtn.hidden = !active;\r
        syncLegendBridge();\r
      }\r
      function overlapArea(a, b) {\r
        var width = Math.max(0, Math.min(a.right, b.right) - Math.max(a.left, b.left));\r
        var height = Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top));\r
        return width * height;\r
      }\r
      function dockPanel(byId) {\r
        panel.removeAttribute('data-dock-side');\r
        if (panel.hidden || window.innerWidth <= 720) return 'right';\r
        var panelRect = panel.getBoundingClientRect();\r
        var containerRect = container.getBoundingClientRect();\r
        if (!panelRect.width || !panelRect.height) return 'right';\r
        var selectedRects = Object.keys(byId).filter(function (id) {\r
          return selectedKinds.indexOf(byId[id].getAttribute('data-node-kind') || 'neutral') >= 0;\r
        }).map(function (id) { return byId[id].getBoundingClientRect(); });\r
        var top = panelRect.top;\r
        var width = panelRect.width;\r
        var leftCandidate = { left: containerRect.left + 16, right: containerRect.left + 16 + width, top: top, bottom: panelRect.bottom };\r
        var rightCandidate = { left: containerRect.right - 16 - width, right: containerRect.right - 16, top: top, bottom: panelRect.bottom };\r
        var leftScore = selectedRects.reduce(function (score, rect) { return score + overlapArea(leftCandidate, rect); }, 0);\r
        var rightScore = selectedRects.reduce(function (score, rect) { return score + overlapArea(rightCandidate, rect); }, 0);\r
        var legend = svg.querySelector('[data-legend]');\r
        var nav = container.querySelector('.diagram-nav');\r
        var protectedRects = [legend, nav].filter(function (element) {\r
          return element && !element.hidden && window.getComputedStyle(element).display !== 'none';\r
        }).map(function (element) { return element.getBoundingClientRect(); });\r
        leftScore += protectedRects.reduce(function (score, rect) {\r
          return score + overlapArea(leftCandidate, rect) * 1000;\r
        }, 0);\r
        rightScore += protectedRects.reduce(function (score, rect) {\r
          return score + overlapArea(rightCandidate, rect) * 1000;\r
        }, 0);\r
        var side = leftScore < rightScore ? 'left' : 'right';\r
        panel.setAttribute('data-dock-side', side);\r
        return side;\r
      }\r
      function applySelection(options) {\r
        options = options || {};\r
        cleanSvgState();\r
        var byId = nodesById();\r
        var nodeKind = Object.create(null);\r
        Object.keys(byId).forEach(function (id) { nodeKind[id] = byId[id].getAttribute('data-node-kind') || 'neutral'; });\r
        if (!selectedKinds.length) {\r
          status.textContent = viewerText('viewer.lens.choose');\r
          updateTrigger();\r
          renderKinds();\r
          dockPanel(byId);\r
          if (options.updateUrl !== false) updateHash();\r
          return false;\r
        }\r
\r
        var chosen = {};\r
        selectedKinds.forEach(function (kind) { chosen[kind] = true; });\r
        Object.keys(byId).forEach(function (id) {\r
          if (!chosen[nodeKind[id]]) return;\r
          byId[id].setAttribute('data-lens-match', '');\r
          byId[id].setAttribute('data-lens-selected', '');\r
        });\r
\r
        var touching = 0;\r
        var forward = 0;\r
        var reverse = 0;\r
        var crossKind = selectedKinds.length === 2;\r
        var matchedFlow = [];\r
        edgeGroups().forEach(function (edge) {\r
          var fromKind = nodeKind[edge.from];\r
          var toKind = nodeKind[edge.to];\r
          var match = false;\r
          if (crossKind) {\r
            if (fromKind === selectedKinds[0] && toKind === selectedKinds[1]) { match = true; forward += 1; }\r
            if (fromKind === selectedKinds[1] && toKind === selectedKinds[0]) { match = true; reverse += 1; }\r
          } else if (fromKind === selectedKinds[0] || toKind === selectedKinds[0]) {\r
            match = true;\r
            touching += 1;\r
          }\r
          if (!match) return;\r
          var direction = 'within';\r
          if (crossKind) {\r
            direction = fromKind === selectedKinds[0] ? 'forward' : 'reverse';\r
          } else {\r
            direction = fromKind === selectedKinds[0] && toKind !== selectedKinds[0] ? 'out'\r
              : (toKind === selectedKinds[0] && fromKind !== selectedKinds[0] ? 'in' : 'within');\r
          }\r
          matchedFlow.push({ edge: edge, direction: direction });\r
          edge.members.forEach(function (member) { member.setAttribute('data-lens-match', ''); });\r
          if (!crossKind) {\r
            [edge.from, edge.to].forEach(function (id) {\r
              if (!byId[id]) return;\r
              byId[id].setAttribute('data-lens-match', '');\r
              if (!chosen[nodeKind[id]]) byId[id].setAttribute('data-lens-peer', '');\r
            });\r
          }\r
        });\r
\r
        svg.setAttribute('data-lens-active', selectedKinds.join(' '));\r
        renderFlowOverlay(matchedFlow);\r
        if (crossKind) {\r
          var total = forward + reverse;\r
          status.textContent = viewerCount('viewer.lens.compare', total, {\r
            first: viewerKindLabel(selectedKinds[0]),\r
            second: viewerKindLabel(selectedKinds[1]),\r
            forward: forward,\r
            reverse: reverse\r
          });\r
        } else {\r
          var nodeCount = collectKinds().filter(function (kind) { return kind.id === selectedKinds[0]; })[0].nodes.length;\r
          status.textContent = viewerText('viewer.lens.single', {\r
            nodes: viewerCount('viewer.lens.node', nodeCount, { label: viewerKindLabel(selectedKinds[0]) }),\r
            relationships: viewerCount('viewer.lens.relationship', touching)\r
          });\r
        }\r
        updateTrigger();\r
        renderKinds();\r
        dockPanel(byId);\r
        if (options.updateUrl !== false) updateHash();\r
        return true;\r
      }\r
      function prepareForLens() {\r
        clearLegendPreview();\r
        if (Archify.focus && typeof Archify.focus.clear === 'function') {\r
          Archify.focus.clear({ updateUrl: false, preserveView: true });\r
        }\r
        if (Archify.routeProbe && typeof Archify.routeProbe.clear === 'function') {\r
          Archify.routeProbe.clear({ updateUrl: false, restoreFocus: false });\r
        }\r
        if (Archify.guidedViews && typeof Archify.guidedViews.showAll === 'function') {\r
          Archify.guidedViews.showAll({ clearFocus: false, updateUrl: false });\r
        }\r
        if (Archify.intentTrace && typeof Archify.intentTrace.clear === 'function') {\r
          Archify.intentTrace.clear({ announce: false });\r
        }\r
      }\r
      function select(kind, options) {\r
        options = options || {};\r
        clearLegendPreview();\r
        var exists = collectKinds().some(function (entry) { return entry.id === kind; });\r
        if (!exists) return false;\r
        var index = selectedKinds.indexOf(kind);\r
        if (index >= 0) selectedKinds.splice(index, 1);\r
        else {\r
          if (selectedKinds.length >= 2) return false;\r
          if (!selectedKinds.length) prepareForLens();\r
          selectedKinds.push(kind);\r
        }\r
        return applySelection(options);\r
      }\r
      function close(options) {\r
        options = options || {};\r
        panel.hidden = true;\r
        trigger.setAttribute('aria-expanded', 'false');\r
        updateTrigger();\r
        if (options.restoreFocus !== false && lensOpener && typeof lensOpener.focus === 'function') lensOpener.focus();\r
        return false;\r
      }\r
      function open(options) {\r
        options = options || {};\r
        if (html.getAttribute('data-embed') === 'true') return false;\r
        lensOpener = options.opener || trigger;\r
        if (Archify.exportMenu && Archify.exportMenu.isOpen()) Archify.exportMenu.close(false);\r
        if (Archify.finder && Archify.finder.isOpen()) Archify.finder.close({ restoreFocus: false });\r
        if (Archify.radar && Archify.radar.isOpen()) Archify.radar.close({ restoreFocus: false });\r
        if (Archify.guide && Archify.guide.isOpen()) Archify.guide.close({ restoreFocus: false });\r
        renderKinds();\r
        panel.hidden = false;\r
        trigger.setAttribute('aria-expanded', 'true');\r
        updateTrigger();\r
        requestAnimationFrame(function () {\r
          dockPanel(nodesById());\r
          var activeButton = kindsRoot.querySelector('[aria-pressed="true"]');\r
          var firstButton = activeButton || kindsRoot.querySelector('button:not(:disabled)');\r
          if (firstButton) firstButton.focus();\r
        });\r
        return true;\r
      }\r
      function toggle() { return panel.hidden ? open({ opener: trigger }) : close(); }\r
      function clear(options) {\r
        options = options || {};\r
        selectedKinds = [];\r
        cleanSvgState();\r
        panel.removeAttribute('data-dock-side');\r
        updateTrigger();\r
        renderKinds();\r
        status.textContent = viewerText('viewer.lens.choose');\r
        if (options.updateUrl !== false) updateHash();\r
        if (options.preserveView !== true && Archify.view && typeof Archify.view.reset === 'function') {\r
          Archify.view.reset({ automatic: true });\r
        }\r
        if (options.closePanel === true) close({ restoreFocus: false });\r
        return false;\r
      }\r
      function fallbackCopy(value) {\r
        var field = document.createElement('textarea');\r
        field.value = value;\r
        field.setAttribute('readonly', '');\r
        field.style.position = 'fixed';\r
        field.style.opacity = '0';\r
        document.body.appendChild(field);\r
        field.select();\r
        var copied = false;\r
        try { copied = document.execCommand('copy'); } catch (_) {}\r
        field.remove();\r
        return copied;\r
      }\r
      function copyLink() {\r
        if (!selectedKinds.length) return Promise.resolve(false);\r
        var value = FlowBD.linkBase + '#lens=' + selectedKinds.map(encodeURIComponent).join('~');\r
        var copy = navigator.clipboard && typeof navigator.clipboard.writeText === 'function'\r
          ? navigator.clipboard.writeText(value).then(function () { return true; }).catch(function () { return fallbackCopy(value); })\r
          : Promise.resolve(fallbackCopy(value));\r
        return copy.then(function (copied) {\r
          copyBtn.textContent = viewerText(copied ? 'viewer.common.copied' : 'viewer.common.copyFailed');\r
          window.setTimeout(function () { copyBtn.textContent = viewerText('viewer.common.copyLink'); }, 1600);\r
          return copied;\r
        });\r
      }\r
      function syncFromHash() {\r
        try {\r
          var params = new URLSearchParams(location.hash.replace(/^#/, ''));\r
          var value = params.get('lens');\r
          if (!value) {\r
            if (selectedKinds.length) clear({ updateUrl: false, preserveView: true });\r
            return;\r
          }\r
          var available = collectKinds().map(function (kind) { return kind.id; });\r
          var requested = value.split('~').filter(function (kind, index, list) {\r
            return available.indexOf(kind) >= 0 && list.indexOf(kind) === index;\r
          }).slice(0, 2);\r
          if (!requested.length) return;\r
          prepareForLens();\r
          selectedKinds = requested;\r
          applySelection({ updateUrl: false });\r
        } catch (_) {}\r
      }\r
\r
      trigger.addEventListener('click', toggle);\r
      if (decorateLegendBridge()) {\r
        legendBridge.addEventListener('click', function (event) {\r
          var entry = event.target.closest('[data-legend-kind][role="button"]');\r
          if (entry) activateLegendEntry(entry);\r
        });\r
        legendBridge.addEventListener('pointerover', function (event) {\r
          if (event.pointerType === 'touch' || (finePointerQuery && !finePointerQuery.matches)) return;\r
          var entry = event.target.closest('[data-legend-kind][role="button"]');\r
          if (!entry || (event.relatedTarget && entry.contains(event.relatedTarget))) return;\r
          hoveredLegendEntry = entry;\r
          syncLegendPreview();\r
        });\r
        legendBridge.addEventListener('pointerout', function (event) {\r
          var entry = event.target.closest('[data-legend-kind][role="button"]');\r
          if (!entry || (event.relatedTarget && entry.contains(event.relatedTarget))) return;\r
          if (hoveredLegendEntry === entry) hoveredLegendEntry = null;\r
          syncLegendPreview();\r
        });\r
        legendBridge.addEventListener('focusin', function (event) {\r
          var entry = event.target.closest('[data-legend-kind][role="button"]');\r
          if (!entry) return;\r
          focusedLegendEntry = entry;\r
          legendEntries.forEach(function (candidate) {\r
            candidate.setAttribute('tabindex', candidate === entry ? '0' : '-1');\r
          });\r
          syncLegendPreview();\r
        });\r
        legendBridge.addEventListener('focusout', function (event) {\r
          var entry = event.target.closest('[data-legend-kind][role="button"]');\r
          if (!entry || (event.relatedTarget && entry.contains(event.relatedTarget))) return;\r
          if (focusedLegendEntry === entry) focusedLegendEntry = null;\r
          syncLegendPreview();\r
        });\r
        legendBridge.addEventListener('keydown', function (event) {\r
          var entry = event.target.closest('[data-legend-kind][role="button"]');\r
          if (!entry) return;\r
          if (event.key === 'Enter' || event.key === ' ') {\r
            event.preventDefault();\r
            activateLegendEntry(entry);\r
            return;\r
          }\r
          var index = legendEntries.indexOf(entry);\r
          var next = null;\r
          if (event.key === 'ArrowRight') next = (index + 1) % legendEntries.length;\r
          else if (event.key === 'ArrowLeft') next = (index - 1 + legendEntries.length) % legendEntries.length;\r
          else if (event.key === 'Home') next = 0;\r
          else if (event.key === 'End') next = legendEntries.length - 1;\r
          if (next === null) return;\r
          event.preventDefault();\r
          legendEntries.forEach(function (candidate, candidateIndex) {\r
            candidate.setAttribute('tabindex', candidateIndex === next ? '0' : '-1');\r
          });\r
          legendEntries[next].focus();\r
        });\r
      }\r
      closeBtn.addEventListener('click', function () { close(); });\r
      clearBtn.addEventListener('click', function () { clear({ preserveView: true }); });\r
      copyBtn.addEventListener('click', copyLink);\r
      kindsRoot.addEventListener('click', function (event) {\r
        var button = event.target.closest('[data-kind]');\r
        if (!button || button.disabled) return;\r
        select(button.getAttribute('data-kind'));\r
      });\r
      kindsRoot.addEventListener('keydown', function (event) {\r
        var buttons = Array.prototype.slice.call(kindsRoot.querySelectorAll('button:not(:disabled)'));\r
        var index = buttons.indexOf(document.activeElement);\r
        var next = null;\r
        if (index >= 0 && (event.key === 'ArrowRight' || event.key === 'ArrowDown')) next = (index + 1) % buttons.length;\r
        else if (index >= 0 && (event.key === 'ArrowLeft' || event.key === 'ArrowUp')) next = (index - 1 + buttons.length) % buttons.length;\r
        else if (event.key === 'Home' && buttons.length) next = 0;\r
        else if (event.key === 'End' && buttons.length) next = buttons.length - 1;\r
        if (next !== null) { event.preventDefault(); buttons[next].focus(); }\r
      });\r
      panel.addEventListener('keydown', function (event) {\r
        if (event.key !== 'Escape') return;\r
        event.preventDefault();\r
        event.stopPropagation();\r
        close();\r
      });\r
      document.addEventListener('click', function (event) {\r
        var eventPath = typeof event.composedPath === 'function' ? event.composedPath() : [];\r
        var clickedInside = eventPath.indexOf(panel) >= 0 || panel.contains(event.target);\r
        var clickedLauncher = event.target === trigger || legendEntries.some(function (entry) {\r
          return event.target === entry || entry.contains(event.target);\r
        });\r
        if (!panel.hidden && !clickedInside && !clickedLauncher) close({ restoreFocus: false });\r
      });\r
      window.addEventListener('hashchange', syncFromHash);\r
      window.addEventListener('resize', function () {\r
        if (!panel.hidden && selectedKinds.length) dockPanel(nodesById());\r
        layoutLegendBridge();\r
      });\r
      renderKinds();\r
      syncFromHash();\r
\r
      return {\r
        open: open,\r
        close: close,\r
        toggle: toggle,\r
        clear: clear,\r
        clearPreview: clearLegendPreview,\r
        select: select,\r
        copyLink: copyLink,\r
        isOpen: function () { return !panel.hidden; },\r
        active: function () { return selectedKinds.length ? selectedKinds.slice() : null; },\r
        kinds: function () { return collectKinds().map(function (kind) { return { id: kind.id, count: kind.nodes.length }; }); }\r
      };\r
    })();\r
\r
    /* ============================================================\r
       Diagram Guide — a factual command deck over existing interactions.\r
       Counts come from compiled semantics; actions delegate to Finder, Route\r
       Probe, Semantic Radar, Semantic Lens, Story Trail, Presentation, theme, export, and\r
       camera without adding a second command implementation or SVG state.\r
       ============================================================ */\r
    Archify.guide = (function () {\r
      var html = document.documentElement;\r
      var container = document.querySelector('.diagram-container');\r
      var svg = container.querySelector(':scope > svg');\r
      var trigger = document.getElementById('btn-diagram-guide');\r
      var panel = document.getElementById('diagram-guide');\r
      var closeBtn = document.getElementById('diagram-guide-close');\r
      var stats = document.getElementById('diagram-guide-stats');\r
      var actions = document.getElementById('diagram-guide-actions');\r
      var feedback = document.getElementById('diagram-guide-feedback');\r
      var storyBtn = actions.querySelector('[data-guide-action="story"]');\r
      var storyCopy = document.getElementById('diagram-guide-story-copy');\r
      var routePanel = document.getElementById('route-probe');\r
\r
      function viewCount() {\r
        return Archify.guidedViews && Number(Archify.guidedViews.count) || 0;\r
      }\r
      function relationshipCount() {\r
        var seen = {};\r
        Array.prototype.forEach.call(svg.querySelectorAll('[data-edge-from][data-edge-to]'), function (edge) {\r
          var key = edge.getAttribute('data-edge-key') || [\r
            edge.getAttribute('data-edge-from'),\r
            edge.getAttribute('data-edge-to'),\r
            edge.getAttribute('data-edge-label') || ''\r
          ].join('\\u0000');\r
          seen[key] = true;\r
        });\r
        return Object.keys(seen).length;\r
      }\r
      function renderFacts() {\r
        var nodes = svg.querySelectorAll('[data-node-id]').length;\r
        var relationships = relationshipCount();\r
        var views = viewCount();\r
        stats.textContent = viewerText('viewer.guide.facts', {\r
          nodes: viewerCount('viewer.guide.fact.node', nodes),\r
          relationships: viewerCount('viewer.guide.fact.relationship', relationships),\r
          views: viewerCount('viewer.guide.fact.view', views)\r
        });\r
        storyBtn.disabled = views === 0;\r
        storyBtn.setAttribute('aria-disabled', views === 0 ? 'true' : 'false');\r
        storyCopy.textContent = views\r
          ? viewerCount('viewer.guide.story.available', views)\r
          : viewerText('viewer.guide.story.unavailable');\r
      }\r
      function actionButtons() {\r
        return Array.prototype.slice.call(actions.querySelectorAll('.diagram-guide-action:not(:disabled)'));\r
      }\r
      function close(options) {\r
        options = options || {};\r
        panel.hidden = true;\r
        html.removeAttribute('data-guide-open');\r
        routePanel.removeAttribute('data-guide-open');\r
        trigger.setAttribute('aria-expanded', 'false');\r
        trigger.setAttribute('aria-label', viewerText('viewer.guide.open'));\r
        feedback.textContent = '';\r
        if (options.restoreFocus !== false) trigger.focus();\r
        return false;\r
      }\r
      function open() {\r
        if (html.getAttribute('data-embed') === 'true') return false;\r
        if (Archify.semanticLens && typeof Archify.semanticLens.clearPreview === 'function') Archify.semanticLens.clearPreview();\r
        if (Archify.exportMenu && Archify.exportMenu.isOpen()) Archify.exportMenu.close(false);\r
        if (Archify.finder && Archify.finder.isOpen()) Archify.finder.close({ restoreFocus: false });\r
        if (Archify.radar && Archify.radar.isOpen()) Archify.radar.close({ restoreFocus: false });\r
        if (Archify.semanticLens && Archify.semanticLens.isOpen()) Archify.semanticLens.close({ restoreFocus: false });\r
        if (Archify.guidedViews && Archify.guidedViews.isPlaying && Archify.guidedViews.isPlaying()) {\r
          Archify.guidedViews.pause();\r
        }\r
        if (Archify.routeProbe && Archify.routeProbe.isJourneyPlaying && Archify.routeProbe.isJourneyPlaying()) {\r
          Archify.routeProbe.pauseJourney({ preserveElapsed: true, reason: 'guide' });\r
        }\r
        renderFacts();\r
        panel.hidden = false;\r
        html.setAttribute('data-guide-open', 'true');\r
        routePanel.setAttribute('data-guide-open', 'true');\r
        trigger.setAttribute('aria-expanded', 'true');\r
        trigger.setAttribute('aria-label', viewerText('viewer.guide.close'));\r
        feedback.textContent = '';\r
        requestAnimationFrame(function () {\r
          var first = actionButtons()[0];\r
          if (first) first.focus();\r
        });\r
        return true;\r
      }\r
      function toggle() { return panel.hidden ? open() : close(); }\r
      function execute(action) {\r
        feedback.textContent = '';\r
        if (action === 'story' && !viewCount()) {\r
          feedback.textContent = viewerText('viewer.guide.noStory');\r
          return false;\r
        }\r
        close({ restoreFocus: false });\r
        if (action === 'find') return Archify.finder.open();\r
        if (action === 'route') return Archify.routeProbe.begin({ focusNode: true });\r
        if (action === 'map') return Archify.radar.open();\r
        if (action === 'lens') return Archify.semanticLens.open();\r
        if (action === 'story') return Archify.guidedViews.play();\r
        if (action === 'present') return Archify.presentation.enter();\r
        if (action === 'export') return Archify.exportMenu.open();\r
        if (action === 'theme') return Archify.theme.toggle();\r
        if (action === 'preset') return Archify.preset.cycle();\r
        if (action === 'reset') return Archify.view.reset();\r
        if (action === 'zoom-in') return Archify.view.zoomIn();\r
        if (action === 'zoom-out') return Archify.view.zoomOut();\r
        return false;\r
      }\r
      function actionForKey(key) {\r
        return {\r
          '/': 'find',\r
          r: 'route',\r
          m: 'map',\r
          l: 'lens',\r
          p: 'story',\r
          f: 'present',\r
          e: 'export',\r
          t: 'theme',\r
          s: 'preset',\r
          '0': 'reset',\r
          '+': 'zoom-in',\r
          '=': 'zoom-in',\r
          '-': 'zoom-out'\r
        }[key] || null;\r
      }\r
\r
      trigger.addEventListener('click', toggle);\r
      closeBtn.addEventListener('click', function () { close(); });\r
      actions.addEventListener('click', function (event) {\r
        var button = event.target.closest('[data-guide-action]');\r
        if (!button || button.disabled) return;\r
        event.stopPropagation();\r
        execute(button.getAttribute('data-guide-action'));\r
      });\r
      panel.addEventListener('keydown', function (event) {\r
        if (event.key === 'Escape' || event.key === '?') {\r
          event.preventDefault();\r
          event.stopPropagation();\r
          close();\r
          return;\r
        }\r
        var buttons = actionButtons();\r
        var index = buttons.indexOf(document.activeElement);\r
        var next = null;\r
        if (index >= 0 && event.key === 'ArrowRight') next = (index + 1) % buttons.length;\r
        else if (index >= 0 && event.key === 'ArrowDown') next = (index + 1) % buttons.length;\r
        else if (index >= 0 && event.key === 'ArrowLeft') next = (index - 1 + buttons.length) % buttons.length;\r
        else if (index >= 0 && event.key === 'ArrowUp') next = (index - 1 + buttons.length) % buttons.length;\r
        else if (event.key === 'Home' && buttons.length) next = 0;\r
        else if (event.key === 'End' && buttons.length) next = buttons.length - 1;\r
        if (next !== null) {\r
          event.preventDefault();\r
          event.stopPropagation();\r
          buttons[next].focus();\r
          return;\r
        }\r
        var action = actionForKey(event.key.length === 1 ? event.key.toLowerCase() : event.key);\r
        if (!action) return;\r
        event.preventDefault();\r
        event.stopPropagation();\r
        execute(action);\r
      });\r
      document.addEventListener('click', function (event) {\r
        if (!panel.hidden && !panel.contains(event.target) && event.target !== trigger) close({ restoreFocus: false });\r
      });\r
\r
      renderFacts();\r
      return {\r
        open: open,\r
        close: close,\r
        toggle: toggle,\r
        execute: execute,\r
        isOpen: function () { return !panel.hidden; },\r
        facts: function () {\r
          return {\r
            nodes: svg.querySelectorAll('[data-node-id]').length,\r
            relationships: relationshipCount(),\r
            views: viewCount()\r
          };\r
        }\r
      };\r
    })();\r
\r
    /* ============================================================\r
       Global keyboard shortcuts\r
       ? -> open Diagram Guide\r
       T -> toggle theme\r
       S -> cycle visual style\r
       E -> open export menu\r
         F -> toggle presentation stage\r
         M -> toggle Semantic Radar\r
         L -> toggle Semantic Lens\r
         R -> start/clear Route Probe\r
         / -> open node finder or the active route endpoint picker\r
         + / - -> zoom, 0 -> reset view\r
         Escape -> clear temporary trace/focus/view first, then exit presentation\r
       Ignored when focus is inside an input/textarea/contenteditable.\r
       ============================================================ */\r
    document.addEventListener('keydown', function (e) {\r
      if (e.metaKey || e.ctrlKey || e.altKey) return;\r
      if (e.defaultPrevented) return;\r
      var t = e.target;\r
      if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable)) return;\r
      if (Archify.preset && Archify.preset.isOpen() && e.key !== 'Escape' && e.key !== 's' && e.key !== 'S') {\r
        Archify.preset.close(false);\r
      }\r
      if (e.key === '?') {\r
        e.preventDefault();\r
        Archify.guide.toggle();\r
      } else if (e.key === '/') {\r
        e.preventDefault();\r
        Archify.finder.open();\r
      } else if (e.key === 't' || e.key === 'T') {\r
        e.preventDefault();\r
        Archify.theme.toggle();\r
      } else if (e.key === 's' || e.key === 'S') {\r
        e.preventDefault();\r
        Archify.preset.cycle();\r
      } else if (e.key === 'e' || e.key === 'E') {\r
        e.preventDefault();\r
        if (!Archify.exportMenu.isOpen()) Archify.exportMenu.open();\r
      } else if (e.key === 'f' || e.key === 'F') {\r
        e.preventDefault();\r
        Archify.presentation.toggle();\r
      } else if (e.key === 'm' || e.key === 'M') {\r
        e.preventDefault();\r
        Archify.radar.toggle();\r
      } else if (e.key === 'l' || e.key === 'L') {\r
        e.preventDefault();\r
        Archify.semanticLens.toggle();\r
      } else if (e.key === 'r' || e.key === 'R') {\r
        e.preventDefault();\r
        Archify.routeProbe.toggle({ focusNode: true });\r
      } else if (e.key === '+' || e.key === '=') {\r
        e.preventDefault();\r
        Archify.view.zoomIn();\r
      } else if (e.key === '-') {\r
        e.preventDefault();\r
        Archify.view.zoomOut();\r
      } else if (e.key === '0') {\r
        e.preventDefault();\r
        Archify.view.reset();\r
      } else if (e.key === 'Escape' && Archify.preset.isOpen()) {\r
        e.preventDefault();\r
        Archify.preset.close(true);\r
      } else if (e.key === 'Escape' && Archify.semanticLens.isOpen()) {\r
        e.preventDefault();\r
        Archify.semanticLens.close({ restoreFocus: true });\r
      } else if (e.key === 'Escape' && Archify.semanticLens.active()) {\r
        e.preventDefault();\r
        Archify.semanticLens.clear({ preserveView: true });\r
      } else if (e.key === 'Escape' && Archify.guide.isOpen()) {\r
        e.preventDefault();\r
        Archify.guide.close({ restoreFocus: true });\r
      } else if (e.key === 'Escape' && Archify.radar.isOpen()) {\r
        e.preventDefault();\r
        Archify.radar.close({ restoreFocus: true });\r
      } else if (e.key === 'Escape' && Archify.routeProbe.active()) {\r
        e.preventDefault();\r
        Archify.routeProbe.escape({ restoreFocus: true });\r
      } else if (e.key === 'Escape' && Archify.intentTrace.active()) {\r
        e.preventDefault();\r
        Archify.intentTrace.clear();\r
      } else if (e.key === 'Escape' && Archify.focus.active()) {\r
        e.preventDefault();\r
        Archify.focus.clear({ restoreFocus: true });\r
      } else if (e.key === 'Escape' && Archify.presentation.active()) {\r
        e.preventDefault();\r
        Archify.presentation.exit();\r
      }\r
    });\r
  <\/script>\r
<script>__FLOWBD_BRIDGE__<\/script></body>\r
</html>\r
`.replace(/__FLOWBD_(TITLE|SVG|GUIDES|PAYLOAD|BRIDGE|CSS)__/g,(e,t)=>h[t])}function u(e,t){let n=``,r=``;try{let e=new URL(window.top.location.href);r=e.hash,e.hash=``,e.searchParams.set(`page`,`lineage`),t.manifest?.case_id&&e.searchParams.set(`case`,t.manifest.case_id),n=e.href}catch{n=window.location.href.split(`#`)[0]}e.innerHTML=`<iframe class="lineage-diagram-frame" title="案例交互谱系图" allow="clipboard-write; fullscreen" allowfullscreen></iframe>`;let i=e.querySelector(`iframe`);i.srcdoc=l(t,{linkBase:n,initialHash:r})}export{u as mountDiagram};