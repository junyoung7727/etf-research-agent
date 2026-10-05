const $ = id => document.getElementById(id);
const state = {data:null, kind:'objects', selected:null};
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const json = value => esc(JSON.stringify(value, null, 2));
const snake = value => value.replace(/([a-z0-9])([A-Z])/g,'$1_$2').replace(/([A-Z])([A-Z][a-z])/g,'$1_$2').toLowerCase();
const policy = {typed_null_pending:'의미·원본 확인 전 typed NULL',identity_encoding:'원본 키 · 기존 인코딩 유지',explicit_transform:'명시된 값 변환',source_value:'원본 값 유지',resolved_reference:'코드·판본을 객체 ID로 해소 · 다중 매칭 검증'};
const mappingNames={object_fk:'객체 뷰의 FK 재사용',resolved_fk:'객체 ID로 해소한 FK',connection_view:'공용 연결 뷰',existing_table:'기존 연결 테이블 재사용',blocked:'구현 보류'};
function sourceText(c){
  if(c.identity) return c.identity.columns.join(' + ')+' / '+c.identity.encoding;
  if(typeof c.source==='string') return c.source;
  if(c.source?.kind==='unmapped') return '연결된 원본 없음';
  if(c.source?.lookupProperty) return c.source.lookupProperty+'의 명시적 lookup';
  if(c.source?.table) return 'public.'+c.source.table+'.'+c.source.column+(c.source.alias?' ('+c.source.alias+')':'');
  return '아래 관계 식별·연결 규칙 참조';
}
function showIssues(ids){
  return state.data.issues.filter(i=>ids.includes(i.id)).map(i=>'<section class="issue"><span class="badge">'+esc(i.category)+'</span><h3>'+esc(i.title)+'</h3><p>'+esc(i.question)+'</p><p><b>설계안:</b> '+esc(i.proposal)+'</p></section>').join('');
}
function columns(view){
  return '<h3>반환 컬럼</h3><div class="table-wrap"><table id="columnTable"><thead><tr><th>뷰 컬럼 / 모델 속성</th><th>PostgreSQL 타입</th><th>원본과 반환 정책</th><th>의미</th></tr></thead><tbody>'+view.columns.map(c=>'<tr data-column="'+esc(c.column)+'"><td><code>'+esc(c.column)+'</code><small>'+esc(c.property||'관계 공통 필드')+'</small></td><td>'+esc(c.type)+'<small>'+(c.viewNullable?'NULL 허용':'NULL 불가 · 검증 대상')+'</small></td><td>'+esc(sourceText(c))+'<small>'+esc(policy[c.valuePolicy]||'관계 계약에 따름')+'</small>'+(c.source&&typeof c.source==='object'?'<details><summary>매핑 상세</summary><pre>'+json(c.source)+'</pre></details>':'')+'</td><td>'+esc(c.description)+'</td></tr>').join('')+'</tbody></table></div>';
}
function objectContract(v){
  const sm=v.sourceMapping;
  const joins=sm.joins.map(j=>'<li>LEFT JOIN public.'+esc(j.table)+' AS '+esc(j.alias)+' ON <code>'+esc(j.on.map(k=>j.from+'.'+k.source+' = '+j.alias+'.'+k.target).join(' AND '))+'</code><small> · '+esc(j.constraint)+'</small></li>').join('');
  return '<dl><dt>한 행의 의미</dt><dd>'+esc(v.grain)+'</dd><dt>기준 원본</dt><dd><code>public.'+esc(sm.baseTable)+' AS base</code></dd><dt>원본 식별 키</dt><dd>'+esc(v.identity.columns.join(' + '))+'</dd><dt>객체 ID</dt><dd>'+esc(v.identity.encoding)+' · 모델 id와 동일한 text</dd><dt>기간·판본</dt><dd>원본 전체 보존. 최신/as-of 선택은 명시적 호출 조건.</dd></dl><h3>조립 조인과 행 조건</h3>'+(joins?'<ul>'+joins+'</ul>':'<p>추가 조인 없음.</p>')+'<p>기준 행 조건: '+(sm.filters.length?'<code>'+esc(sm.filters.map(f=>f.column+' '+(f.operator==='in'?'IN '+JSON.stringify(f.values):'= '+JSON.stringify(f.value))).join(' AND '))+'</code>':'추가 필터 없음')+'</p>';
}
function relationContract(v){
  const sm=v.sourceMapping;
  const condition=sm.kind==='propertyMatch'?v.sourceView+'.'+snake(v.match.sourceProperty)+' = '+v.targetView+'.'+snake(v.match.targetProperty):'아래 원본 경로·코드 변환·판본 조건으로 해소';
  const joins=(v.joinContracts||[]).map(j=>'<li><code>'+esc(j.columns.map((c,i)=>j.table+'.'+c+' = '+j.target_table+'.'+j.target_columns[i]).join(' AND '))+'</code> · '+esc(j.constraint)+'</li>').join('');
  const m=v.physicalMapping;
  return '<dl><dt>관계 한 건의 의미</dt><dd>'+esc(v.grain)+'</dd><dt>방향</dt><dd>'+esc(v.source)+' → '+esc(v.target)+' · '+esc(v.cardinality)+'</dd><dt>역방향 이름</dt><dd>'+esc(v.inverse.displayName)+' — 같은 연결을 반대로 탐색</dd><dt>구현 방식</dt><dd>'+esc(mappingNames[m.kind])+'</dd><dt>엣지 원본</dt><dd>'+esc(v.viewName||'미구현 · 물리 원본 없음')+'</dd><dt>출발 키</dt><dd>'+esc(m.fromColumn||'미정')+' → '+esc(v.source)+'.id</dd><dt>도착 키</dt><dd>'+esc(m.toColumn||'미정')+' → '+esc(v.target)+'.id</dd><dt>엣지 식별 컬럼</dt><dd>'+esc(m.edgeIdColumns?.join(' + ')||'미정')+'</dd><dt>원래 모델의 연결 조건</dt><dd><code>'+esc(condition)+'</code></dd><dt>대상 해소</dt><dd>존재하는 해당 타입의 객체만 연결. NULL·미매칭·다중 매칭은 별도 검증.</dd></dl><details open><summary>물리 매핑 · 필터 · 관계 속성</summary><pre>'+json(m)+'</pre></details>'+(joins?'<h3>원본 FK 경로 — 조립 시 모든 열 사용</h3><ul>'+joins+'</ul>':'')+'<details><summary>관계 원본·필터·판본 선택 계약</summary><pre>'+json(sm)+'</pre></details>';
}
function renderDetail(){
  if(state.map) state.map.highlight();
  const v=state.data[state.kind].find(x=>x.id===state.selected);
  if(!v){$('detail').innerHTML='<p>표시할 항목이 없습니다.</p>';return;}
  if(state.kind==='issues'){
    $('detail').innerHTML='<p class="eyebrow">확인할 사항</p><h2>'+esc(v.title)+'</h2>'+showIssues([v.id])+'<h3>관련 객체</h3><p>'+esc(v.objects.join(', ')||'모든 복합 ID 객체')+'</p>';return;
  }
  const physical=state.data.physicalTables.find(t=>t.id===v.physicalMapping?.source);
  $('detail').innerHTML='<p class="eyebrow">'+(state.kind==='objects'?'OBJECT VIEW':'LINK MAPPING')+'</p><h2>'+esc(v.id)+'</h2><code id="viewName">'+esc(v.viewName||'물리 원본 미정')+'</code><p><span class="badge">'+(v.readiness==='blocked'?'구현 보류 · 입력 해소 미확정':'설계안 · 실행 검증 별도')+'</span></p><p>'+esc(v.description)+'</p>'+(state.kind==='objects'?objectContract(v):relationContract(v))+(state.kind==='objects'?columns(v):physical?columns(physical):'')+(v.issues.length?'<h3>확인할 사항</h3>'+showIssues(v.issues):'<p class="muted">개별 미결 사항 없음. 실제 SQL과 원본 대조 검증은 별도로 수행합니다.</p>')+'<h3>구현 시 통과해야 할 검사</h3><ul><li>원본 범위 대비 행 수·NULL ID·중복 ID·조인 누락과 다중 매칭 대조</li><li>복합 ID, 단위, 기간, 판본, 원본 값과 변환 결과 대조</li><li>미매핑 상태를 실제 0·빈 문자열·유효 업무 값으로 바꾸지 않는지 확인</li></ul>';
}
function renderList(){
  const query=$('search').value.toLowerCase().trim();
  const items=state.data[state.kind].filter(v=>[v.id,v.viewName,v.title,v.grain,v.description].some(s=>String(s||'').toLowerCase().includes(query)));
  $('list').innerHTML=items.map(v=>'<button class="item" data-id="'+esc(v.id)+'" aria-current="'+String(v.id===state.selected)+'">'+esc(v.title||v.id)+'<small>'+esc(v.viewName||v.category)+'</small></button>').join('')||'<p>검색 결과 없음</p>';
  $('list').querySelectorAll('button').forEach(b=>b.addEventListener('click',()=>{state.selected=b.dataset.id;history.replaceState(null,'','?'+(state.kind==='issues'?'issue':state.kind==='relations'?'relation':'object')+'='+encodeURIComponent(state.selected));renderList();renderDetail();}));
}
function selectTab(kind){
  state.kind=kind;state.selected=state.data[kind][0]?.id;
  for(const k of ['objects','relations','issues']) $(k+'Tab').setAttribute('aria-pressed',String(k===kind));
  renderList();renderDetail();
}
async function start(){
  try{
    const response=await fetch('/api/view-design');const data=await response.json();
    if(!response.ok)throw new Error(data.error||'설계 조회 실패');
    state.data=data;
    $('summary').textContent=data.objects.length+'개 객체 뷰 · '+data.relations.length+'개 논리 링크 · '+data.physicalTables.filter(t=>t.kind==='connection_view').length+'개 공용 연결 뷰 · '+data.physicalTables.filter(t=>t.kind==='existing_table').length+'개 기존 테이블 재사용 · 설계 v'+data.revision;
    if(data.modelChanged){$('stale').hidden=false;$('stale').textContent='모델 원본이 설계 검토 시점과 달라졌습니다. 아래는 현재 원본과 기존 설계안의 대조이며, 갱신 검토 전 구현 기준으로 확정하지 마세요.';}
    $('rules').innerHTML=data.rules.map(r=>'<li>'+esc(r)+'</li>').join('');
    for(const kind of ['objects','relations','issues']) $(kind+'Tab').addEventListener('click',()=>selectTab(kind));
    $('search').addEventListener('input',renderList);
    const q=new URLSearchParams(location.search);const requested=q.get('object')||q.get('relation')||q.get('issue');
    selectTab(q.has('relation')?'relations':q.has('issue')?'issues':'objects');
    if(requested&&data[state.kind].some(v=>v.id===requested)){state.selected=requested;renderList();renderDetail();}
    await mountViewMap(data);
  }catch(error){$('summary').textContent='설계를 불러오지 못했습니다: '+error.message;$('detail').textContent='정의와 설계의 일치 여부를 확인하세요. 미조회 상태를 빈 설계로 표시하지 않습니다.';}
}
start();

async function mountViewMap(data){
  const {edgePath}=await import('/model-layout.mjs');
  const engine=new globalThis.ELK();
  const measure=document.createElement('canvas').getContext('2d');measure.font='700 14px Consolas, monospace';
  const model={objects:data.objects,relations:data.relations.map(r=>({...r,label:r.id.slice(r.source.length+1,-r.target.length-1)}))};
  const objects=new Map(model.objects.map(o=>[o.id,o])),relations=new Map(model.relations.map(r=>[r.id,r]));
  const tables=new Map(data.physicalTables.map(t=>[t.id,t]));
  const references=new Map(data.references.map(r=>[r.id,r]));
  const HEADER=90,ROW=27;
  const area=$('viewMap'),scene=$('mapScene'),focus=$('mapFocus');
  let layout=null,zoom=1,pan={x:0,y:0},version=0,drag=null,moved=false;
  let hasSelection=new URLSearchParams(location.search).has('object')||new URLSearchParams(location.search).has('relation');
  const svg=(tag,attrs={},text)=>{const el=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [k,v] of Object.entries(attrs))el.setAttribute(k,v);if(text!==undefined)el.textContent=text;return el;};
  for(const o of tables.values()){const option=document.createElement('option');option.value=o.id;option.textContent=o.viewName.split('.')[1];focus.append(option);}
  const requested=new URLSearchParams(location.search).get('object')||new URLSearchParams(location.search).get('relation');
  focus.value=tables.has(requested)?requested:relations.get(requested)?.physicalMapping.source||'ETFHolding';
  function subset(){
    if(!focus.value)return {tables:[...tables.values()],references:data.references};
    const refs=data.references.filter(r=>r.table===focus.value||r.target===focus.value);
    const ids=new Set([focus.value,...refs.flatMap(r=>[r.table,r.target])]);
    return {tables:[...tables.values()].filter(t=>ids.has(t.id)),references:refs};
  }
  async function tableLayout(part){
    const children=part.tables.map(t=>({id:t.id,width:Math.max(410,Math.ceil(measure.measureText(t.viewName.split('.')[1]).width)+32),height:HEADER+t.columns.length*ROW+8,ports:[],layoutOptions:{'elk.portConstraints':'FIXED_POS'}}));
    const nodes=new Map(children.map(n=>[n.id,n]));
    const edges=[];
    for(const r of part.references){
      const from=nodes.get(r.table),to=nodes.get(r.target),id=r.id;
      const row=tables.get(r.table).columns.findIndex(c=>c.column===r.column),pk=tables.get(r.target).columns.findIndex(c=>c.column===r.targetColumn);
      if(row<0||pk<0)throw Error('참조 컬럼 또는 PK 없음: '+id);
      from.ports.push({id:id+':fk',x:from.width,y:HEADER+ROW*(row+.5),width:0,height:0,layoutOptions:{'elk.port.side':'EAST'}});
      to.ports.push({id:id+':pk',x:0,y:HEADER+ROW*(pk+.5),width:0,height:0,layoutOptions:{'elk.port.side':'WEST'}});
      edges.push({id,sources:[id+':fk'],targets:[id+':pk']});
    }
    const layerBound=Math.max(2,Math.round(Math.sqrt(children.length/1.4)));
    const result=await engine.layout({id:'view-tables',children,edges,layoutOptions:{'elk.algorithm':'layered','elk.direction':'RIGHT','elk.layered.layering.strategy':'COFFMAN_GRAHAM','elk.layered.layering.coffmanGraham.layerBound':String(layerBound),'elk.edgeRouting':'ORTHOGONAL','elk.randomSeed':'7','elk.padding':'[top=30,left=30,bottom=30,right=30]','elk.spacing.nodeNode':'40','elk.spacing.edgeNode':'26','elk.spacing.edgeEdge':'16','elk.layered.spacing.nodeNodeBetweenLayers':part.tables.length<=4?'180':'110','elk.layered.spacing.edgeNodeBetweenLayers':'30','elk.layered.spacing.edgeEdgeBetweenLayers':'18','elk.layered.mergeEdges':'false'}});
    return {nodes:result.children,edges:result.edges.map(e=>{if(e.sections?.length!==1)throw Error('참조 경로 없음: '+e.id);const s=e.sections[0];return {id:e.id,points:[s.startPoint,...(s.bendPoints||[]),s.endPoint]};}),bounds:{width:result.width,height:result.height}};
  }
  function transform(){scene.setAttribute('transform',`translate(${pan.x},${pan.y}) scale(${zoom})`);$('mapZoom').textContent=Math.round(zoom*100)+'%';}
  function fit(){if(!layout)return;zoom=Math.min(1,(area.clientWidth-60)/layout.bounds.width,(area.clientHeight-60)/layout.bounds.height);pan={x:(area.clientWidth-layout.bounds.width*zoom)/2,y:(area.clientHeight-layout.bounds.height*zoom)/2};transform();}
  function scale(factor,x=area.clientWidth/2,y=area.clientHeight/2){const next=Math.max(.05,Math.min(2.5,zoom*factor));pan={x:x-(x-pan.x)*next/zoom,y:y-(y-pan.y)*next/zoom};zoom=next;transform();}
  function highlight(){
    const object=hasSelection&&state.kind==='objects'?state.selected:null,relation=hasSelection&&state.kind==='relations'?state.selected:null;
    const selectedRelation=relations.get(relation);
    for(const el of scene.querySelectorAll('[data-map-table]'))el.classList.toggle('selected',el.dataset.mapTable===object||!!selectedRelation&&[selectedRelation.physicalMapping.source,selectedRelation.source,selectedRelation.target].includes(el.dataset.mapTable));
    for(const el of scene.querySelectorAll('[data-map-fk]')){
      const r=references.get(el.dataset.mapFk),active=r.relationIds.includes(relation)||!!object&&(r.table===object||r.target===object);
      el.classList.toggle('active',active);el.classList.toggle('faded',!!(object||relation)&&!active);
    }
  }
  function choose(kind,id){
    if(moved)return;
    state.kind=kind;state.selected=id;$('search').value='';
    for(const k of ['objects','relations','issues'])$(k+'Tab').setAttribute('aria-pressed',String(k===kind));
    history.replaceState(null,'','?'+(kind==='objects'?'object':'relation')+'='+encodeURIComponent(id));
    renderList();renderDetail();
    $('mapSelection').textContent=(kind==='objects'?objects:relations).get(id).viewName+' · 상세 설계 ↓';
  }
  function activate(el,fn){el.onclick=fn;el.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();moved=false;fn();}};}
  function render(){
    scene.replaceChildren();
    for(const route of layout.edges){
      const r=references.get(route.id),source=tables.get(r.table),target=tables.get(r.target);
      const g=svg('g',{'data-map-fk':route.id,'data-relation-id':r.relationIds[0],class:'map-edge',tabindex:0,role:'button','aria-label':source.viewName+'.'+r.column+' → '+target.viewName+'.id'});
      g.append(svg('title',{},source.viewName+'.'+r.column+' → '+target.viewName+'.id\n'+r.relationIds.join('\n')));
      g.append(svg('path',{d:edgePath(route.points),class:'map-edge-halo'}),svg('path',{d:edgePath(route.points),class:'map-edge-line','marker-end':'url(#mapArrow)'}),svg('path',{d:edgePath(route.points),class:'map-edge-hit'}));
      activate(g,()=>choose('relations',r.relationIds[0]));scene.append(g);
    }
    for(const b of layout.nodes){
      const o=tables.get(b.id),isRelation=o.kind!=='object_view',blocked=false;
      const g=svg('g',{'data-map-table':o.id,[isRelation?'data-map-relation':'data-map-object']:o.id,class:'map-card'+(isRelation?' relation-table':'')+(blocked?' blocked-table':''),transform:`translate(${b.x},${b.y})`,tabindex:0,role:'button','aria-label':o.viewName});
      g.append(svg('title',{},o.viewName+'\n'+o.grain),svg('rect',{width:b.width,height:b.height,rx:7,class:'map-card-bg'}),svg('text',{x:14,y:20,class:'map-card-meta'},({object_view:'OBJECT VIEW',connection_view:'SHARED CONNECTION VIEW',existing_table:'EXISTING TABLE'})[o.kind]),svg('text',{x:14,y:43,class:'map-card-title'},o.viewName.split('.')[1]),svg('text',{x:14,y:63,class:'map-card-meta'},'식별 키: '+o.primaryKey.join(' + ')));
      g.append(svg('text',{x:14,y:83,class:'map-card-meta'},'KEY'),svg('text',{x:57,y:83,class:'map-card-meta'},'COLUMN'),svg('text',{x:b.width-148,y:83,class:'map-card-meta'},'TYPE'),svg('text',{x:b.width-40,y:83,class:'map-card-meta'},'NULL'));
      o.columns.forEach((c,i)=>{
        const y=HEADER+i*ROW,pk=c.keyRoles.includes('PK'),fk=c.keyRoles.includes('FK'),key=c.keyRoles.join('/');
        const row=svg('g',{'data-erd-column':c.column,'data-key':key,class:'erd-row'+(pk?' pk-row':fk?' fk-row':'')});
        row.append(svg('rect',{x:1,y,width:b.width-2,height:ROW,class:'erd-row-bg'}),svg('line',{x1:1,y1:y,x2:b.width-1,y2:y,class:'erd-row-rule'}),svg('text',{x:8,y:y+18,class:pk?'erd-pk':fk?'erd-fk':'erd-key'},key),svg('text',{x:57,y:y+18,class:'erd-column'},c.column),svg('text',{x:b.width-148,y:y+18,class:'erd-type'},c.type),svg('text',{x:b.width-30,y:y+18,class:'erd-null'},c.viewNullable?'Y':'N'));
        row.append(svg('title',{},c.description+c.references.map(r=>'\n→ '+tables.get(r.target).viewName+'.id').join('')));
        g.append(row);
      });
      activate(g,()=>choose(isRelation?'relations':'objects',isRelation?model.relations.find(r=>r.physicalMapping.source===o.id).id:o.id));g.ondblclick=()=>{focus.value=o.id;arrange();};scene.append(g);
      for(const text of g.querySelectorAll('.erd-column'))if(text.getComputedTextLength()>b.width-218){text.setAttribute('textLength',b.width-218);text.setAttribute('lengthAdjust','spacingAndGlyphs');}
      const key=g.querySelectorAll('.map-card-meta')[1];if(key.getComputedTextLength()>b.width-28){key.setAttribute('textLength',b.width-28);key.setAttribute('lengthAdjust','spacingAndGlyphs');}
    }
    highlight();fit();
  }
  async function arrange(){
    const ticket=++version,part=subset();
    area.setAttribute('aria-busy','true');$('mapStatus').textContent='선과 테이블 위치를 정리하고 있습니다…';
    try{
      const result=await tableLayout(part);
      if(ticket!==version)return;layout=result;render();
      $('mapStatus').textContent=(focus.value?focus.value+' 직접 연결':'전체 구조')+' · '+part.tables.length+'개 물리 원본 · '+result.edges.length+'개 FK 참조 · 보류 링크는 물리 테이블로 표시하지 않음';
    }catch(error){if(ticket!==version)return;layout=null;scene.replaceChildren();$('mapStatus').textContent='관계도 배치 실패: '+error.message;}
    finally{if(ticket===version)area.setAttribute('aria-busy','false');}
  }
  area.onpointerdown=e=>{if(e.button!==0)return;moved=false;drag={x:e.clientX,y:e.clientY,pan:{...pan},id:e.pointerId};};
  area.onpointermove=e=>{if(!drag)return;const dx=e.clientX-drag.x,dy=e.clientY-drag.y;if(Math.abs(dx)+Math.abs(dy)>4){moved=true;area.setPointerCapture(e.pointerId);}if(moved){pan={x:drag.pan.x+dx,y:drag.pan.y+dy};transform();}};
  area.onpointerup=area.onpointercancel=()=>{drag=null;};
  area.addEventListener('wheel',e=>{e.preventDefault();const b=area.getBoundingClientRect();scale(Math.exp(-e.deltaY*.0015),e.clientX-b.left,e.clientY-b.top);},{passive:false});
  area.addEventListener('keydown',e=>{if(e.target!==area)return;const delta={ArrowLeft:[40,0],ArrowRight:[-40,0],ArrowUp:[0,40],ArrowDown:[0,-40]}[e.key];if(delta){e.preventDefault();pan.x+=delta[0];pan.y+=delta[1];transform();}});
  $('mapFit').onclick=fit;$('mapPlus').onclick=()=>scale(1.25);$('mapMinus').onclick=()=>scale(.8);$('mapReset').onclick=arrange;focus.onchange=arrange;
  new ResizeObserver(fit).observe(area);
  state.map={highlight(){hasSelection=true;highlight();}};await arrange();
}
