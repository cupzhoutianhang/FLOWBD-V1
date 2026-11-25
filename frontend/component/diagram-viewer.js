/* Literature evidence is separate from Archify's verified-repository contract. */
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
  var fields = [['year_label','年份'],['branch_name','技术分支'],['source_paper','来源论文'],['source_authors','作者'],['verification_status','原始核验状态'],['evidence_level','证据层级'],['status','数据状态'],['confidence_llm','模型置信度（非人工确认）'],['source_scope','支持范围'],['relation_class','关系类别'],['relation_type','原关系类型'],['edge_scope','关系范围'],['count_in_dataset','计入语料统计'],['problem_solved','研究问题'],['method_or_material','方法或材料'],['key_performance','性能记录'],['evidence_location','原文位置'],['sentence_id','句子编号']];
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
    if(row.relation_class==='candidate_evolution')evidence.appendChild(element('p','自动候选承接；不参与事实演化路径或上下游推断。'));
    if(row.evidence_segments)row.evidence_segments.forEach(function(segment){evidence.appendChild(element('p',(segment.locatable?'片段可定位：':'片段待核：')+segment.text));});
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
