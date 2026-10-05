import {layoutModel,edgePath,connectedModel,LINK_FONT} from './model-layout.mjs';
const $=s=>document.querySelector(s),$$=s=>[...document.querySelectorAll(s)];
const esc=v=>String(v??'NULL').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const state={model:{objects:[],relations:[]},revision:0,meta:null,token:'',selected:null,focus:null,dirty:false,zoom:1,pan:{x:30,y:30},preview:null,previewVersion:0,positions:new Map(),routes:new Map(),layout:null,layoutVersion:0};
const layoutEngine=new globalThis.ELK();
const labelMeasure=document.createElement('canvas').getContext('2d');labelMeasure.font=LINK_FONT;
async function api(path,body){const r=await fetch('/api/'+path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json','X-Workbench-Token':state.token},body:JSON.stringify(body)});const d=await r.json();if(!r.ok)throw Error(d.error||'요청 실패');return d;}
function message(text=''){$('#notice').textContent=text;}
function run(fn){return (...args)=>Promise.resolve().then(()=>fn(...args)).catch(e=>message(e.message));}
function current(){return state.model.objects.find(o=>o.id===state.selected);}
function sources(obj){const result={base:obj.table};for(const j of obj.joins){const fk=j.definition||state.meta.foreign_keys[j.fk];if(!fk)continue;result[j.id]=fk[j.reverse?'table':'target_table'];}return result;}
function options(values,selected){return values.map(v=>{const [value,label]=Array.isArray(v)?v:[v,v];return `<option value="${esc(value)}" ${value===selected?'selected':''}>${esc(label)}</option>`;}).join('');}
function columnOptions(table,value){return options((state.meta.schema[table]||[]).map(c=>[c.name,c.name+' · '+c.type]),value);}
function fieldOptions(obj,value){return options([['id','id · 객체 식별자'],...obj.properties.map(p=>[p.id,p.label+' · '+p.id])],value);}
function sourceOptions(obj,value){return options(Object.entries(sources(obj)).map(([a,t])=>[a,`${a} · ${t}`]),value);}
function svg(tag,attrs={},text){const node=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [k,v] of Object.entries(attrs))node.setAttribute(k,v);if(text!==undefined)node.textContent=text;return node;}
function box(obj){return state.positions.get(obj.id);}
function visibleModel(){return state.focus?connectedModel(state.model,state.focus):state.model;}
async function autoLayout(positions){
 const version=++state.layoutVersion;$('#autoLayout').disabled=true;$('#modelCanvas').setAttribute('aria-busy','true');
 try{
  const layout=await layoutModel(visibleModel(),{engine:layoutEngine,measureLabel:text=>labelMeasure.measureText(text).width,positions});
  if(version!==state.layoutVersion)return;
  state.layout=layout;state.positions=new Map(layout.nodes.map(n=>[n.id,n]));state.routes=new Map(layout.edges.map(e=>[e.id,e]));graph();if(!positions)fit();
 }finally{if(version===state.layoutVersion){$('#autoLayout').disabled=false;$('#modelCanvas').setAttribute('aria-busy','false');}}
}
function transform(){$('#modelScene').setAttribute('transform',`translate(${state.pan.x},${state.pan.y}) scale(${state.zoom})`);$('#modelZoom').textContent=Math.round(state.zoom*100)+'%';}
function highlightSelection(){
 const scene=$('#modelScene'),anchor=scene.querySelector('[data-object]');
 for(const node of scene.querySelectorAll('[data-object]'))node.classList.toggle('selected',node.dataset.object===state.selected);
 for(const rel of state.model.relations){
  const node=[...scene.querySelectorAll('[data-relation]')].find(n=>n.dataset.relation===rel.id);if(!node)continue;
  const selected=state.selected===rel.id,related=!state.selected||selected||(current()&&(rel.source===state.selected||rel.target===state.selected));
  node.classList.toggle('selected-link',selected);node.classList.toggle('dimmed-link',!related);
  if(related)scene.insertBefore(node,anchor);
 }
 $('#focusModel').disabled=!current();
}
function graph(){
 const scene=$('#modelScene');scene.replaceChildren();$('#emptyModel').hidden=state.model.objects.length>0;
 const model=visibleModel(),positions=new Map(model.objects.map(o=>[o.id,box(o)]));
 $('#graphScope').textContent=state.focus?`${state.focus} 직접 연결 · ${model.objects.length} / ${state.model.objects.length} types · ${model.relations.length} / ${state.model.relations.length} links`:'전체 구조 · 카드 더블클릭으로 직접 연결 보기';
 $('#focusModel').disabled=!current();
 const related=rel=>state.selected===rel.id||(!state.selected)||(current()&&(rel.source===state.selected||rel.target===state.selected));
 for(const rel of [...model.relations].sort((a,b)=>Number(related(a))-Number(related(b)))){
  if(drag?.obj&&moved&&(rel.source===drag.obj.id||rel.target===drag.obj.id))continue;
  const route=state.routes.get(rel.id);if(!route)continue;const d=edgePath(route.points),l=route.label;
  const g=svg('g',{'data-relation':rel.id,class:'relation '+(state.selected===rel.id?'selected-link ':'')+(!related(rel)?'dimmed-link ':'')+(['policyPending','mappingReview'].includes(rel.mappingStatus||rel.status)?'pending-link':'')});
  g.append(svg('title',{},`${rel.source} → ${rel.label} → ${rel.target}`),svg('path',{d,class:'link-halo'}),svg('path',{d,class:'model-link'}));
  const hit=svg('path',{d,class:'link-hit',tabindex:0,role:'button','aria-label':`${rel.source} ${rel.label} ${rel.target}`});
  const label=svg('g',{class:'link-caption'});label.append(svg('rect',{x:l.x,y:l.y,width:l.width,height:l.height,rx:5,class:'link-label-bg'}),svg('text',{x:l.x+l.width/2,y:l.y+17,class:'link-label','text-anchor':'middle'},l.text));
  const select=()=>{state.selected=rel.id;highlightSelection();editRelation(rel);};hit.onclick=select;label.onclick=select;hit.onkeydown=e=>{if(e.key==='Enter')select();};g.append(hit,label);scene.append(g);
 }
 for(const [index,obj] of model.objects.entries()){
  const b=positions.get(obj.id);if(!b)continue;
  const node=svg('g',{transform:`translate(${b.x},${b.y})`,class:'object-card'+(state.selected===obj.id?' selected':''),'data-object':obj.id,tabindex:0,role:'button','aria-label':obj.label});
  node.append(svg('rect',{width:b.width,height:b.height,rx:10,class:'card-bg'}),svg('text',{x:16,y:21,class:'meta'},obj.group||'Object type'),svg('text',{x:16,y:48,class:'title'},obj.label),svg('text',{x:16,y:68,class:'source'},'public.'+obj.table),svg('text',{x:16,y:88,class:'meta'},`${Object.keys(obj.propertyDefinitions||{}).length||obj.properties.length+1} properties · ${obj.preview?.available===false?'snapshot unavailable':'source preview'}`));
  node.onpointerdown=e=>startDrag(e,obj,index);node.onclick=()=>{if(!moved)selectObject(obj.id);};node.onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();if(e.shiftKey)run(()=>focusObject(obj.id))();else selectObject(obj.id);}};scene.append(node);
  const title=node.querySelector('.title');if(title.getComputedTextLength()>b.width-32){title.setAttribute('textLength',b.width-32);title.setAttribute('lengthAdjust','spacingAndGlyphs');}
 }
 transform();
}
function selectObject(id){state.selected=id;state.previewVersion++;state.preview=null;$('#previewTable').replaceChildren();$('#sourceRows').replaceChildren();const obj=current();$('#previewStats').textContent=obj?.preview?.available===false?obj.preview.reason+' '+obj.preview.missingTables.join(', '):'객체 데이터 조회를 누르면 현재 스냅샷의 실제 객체 JSON을 볼 수 있습니다.';$('#previewButton').disabled=obj?.preview?.available===false;$('#objectJump').value=id;highlightSelection();editObject(obj);}
async function focusObject(id){state.focus=id;selectObject(id);await autoLayout();}
function fit(){if(!state.model.objects.length||!state.layout)return;const {x,y,width,height}=state.layout.bounds,area=$('#modelCanvas');state.zoom=Math.max(.05,Math.min(1.15,(area.clientWidth-50)/width,(area.clientHeight-50)/height));state.pan={x:(area.clientWidth-width*state.zoom)/2-x*state.zoom,y:(area.clientHeight-height*state.zoom)/2-y*state.zoom};transform();}
// Logical property-graph contract. Persistence remains the local revision store.
function typeNode(obj){
 const tables=sources(obj);
 return {id:obj.id,labels:['ObjectType'],properties:{name:obj.id,displayName:obj.label,description:obj.note||''},
  instanceNodeLabel:obj.id,
  identity:{property:'id',sourceTable:obj.table,...(obj.identity||{sourceColumn:obj.key})},
  propertyDefinitions:obj.propertyDefinitions||obj.properties.map(p=>({name:p.id,displayName:p.label,source:{alias:p.source,table:tables[p.source],column:p.column}})),
  apiName:obj.apiName,displayName:obj.displayName,pluralDisplayName:obj.pluralDisplayName,
  implementedInterfaces:obj.implementedInterfaces||[],
  primaryKey:obj.primaryKey,titleProperty:obj.titleProperty,status:obj.status,visibility:obj.visibility,
  sourceConstraints:obj.sourceConstraints,dataIssues:obj.dataIssues,preview:obj.preview,
  sourceMapping:obj.sourceMapping||{baseTable:obj.table,filters:obj.filters||[],joins:obj.joins.map(j=>({...j,definition:j.definition||state.meta.foreign_keys[j.fk]}))}};
}
function typeEdge(rel){return {id:rel.id,type:rel.name||rel.id,from:rel.source,to:rel.target,
 properties:{displayName:rel.label,description:rel.note||'',cardinality:rel.cardinality},
 apiName:rel.apiName,inverse:rel.inverse,status:rel.status,mappingStatus:rel.mappingStatus,backing:rel.backing,
 sourceMapping:rel.sourceMapping,linkProperties:rel.linkProperties,
 instanceMatch:(!rel.sourceMapping||rel.sourceMapping.kind==='propertyMatch')?{fromProperty:rel.source_property,toProperty:rel.target_property,operator:'equals',nullsMatch:false}:undefined};}
function modelGraphJson(){return {format:'orca-logical-property-graph-v1',graphLevel:'schema',
 persistence:{status:'library-and-drafts',graphDatabaseConnected:false},
  nodes:state.model.objects.map(typeNode),edges:state.model.relations.map(typeEdge)};}
function editObject(obj){
 if(!obj)return;
 $('#previewTitle').textContent=obj.label+' · 실제 객체';
 $('#editor').innerHTML='<span class="eyebrow">OBJECT TYPE / DEFINITION</span><h2>'+esc(obj.label)+'</h2><p>'+esc(obj.note)+'</p><p>모델 정의와 원본 제약 · 발행 v'+state.revision+'</p><div id="propertyContracts"></div><p class="warning">'+esc((obj.dataIssues||[]).join(' '))+'</p><details><summary>Published YAML</summary><p id="yamlFile"></p><pre id="definitionYaml"></pre></details><details><summary>Graph node JSON</summary><pre id="definitionJson"></pre></details><h3>Connected edge definitions</h3><pre id="relationsJson"></pre>';
 const props=obj.propertyDefinitions||{};
 const viewLink=document.createElement('a');viewLink.href='/view-design?object='+encodeURIComponent(obj.id);viewLink.textContent='이 객체의 SQL 뷰 설계 →';$('#propertyContracts').before(viewLink);
 const interfaces=document.createElement('p');interfaces.id='implementedInterfaces';interfaces.append('Implements: ');for(const name of obj.implementedInterfaces||[]){const a=document.createElement('a');a.href='/interfaces?interface='+encodeURIComponent(name);a.textContent=name+' ';interfaces.append(a);}if(!(obj.implementedInterfaces||[]).length)interfaces.append('없음');$('#propertyContracts').before(interfaces);
 $('#propertyContracts').insertAdjacentHTML('beforebegin','<dl id="objectMetadata"><dt>API name</dt><dd>'+esc(obj.apiName||obj.id)+'</dd><dt>Status</dt><dd>'+esc(obj.status||'experimental')+'</dd><dt>Primary key</dt><dd>'+esc(obj.primaryKey||'id')+'</dd><dt>Title property</dt><dd>'+esc(obj.titleProperty||'id')+'</dd></dl><h3>Properties</h3>');
 $('#propertyContracts').innerHTML=Object.entries(props).map(([name,p])=>{const c=p.sourceConstraints,m=obj.sourceMapping?.properties?.[name];const fk=c?.foreignKeys||[];return `<details class="property-contract" data-property="${esc(name)}"><summary><b>${esc(p.displayName||p.label||name)}</b><span>${esc(p.dataType||p.sourceDataType)} · ${p.nullable?'NULL 허용':'필수'}</span><span class="key-badges">${name===(obj.primaryKey||'id')?'Primary key ':c?.primaryKey?.length?'원본 PK ':''}${name===obj.titleProperty?'Title ':''}${fk.length?'원본 FK':''}${p.mappingStatus==='needsCorrection'?' 매핑 수정 필요':p.mappingStatus==='unmapped'?' 원본 연결 대기':''}</span></summary><p>API name: ${esc(p.apiName||name)} · Status: ${esc(p.status||'experimental')}</p><p>${esc(p.description)}</p><p>원본: ${m?.table?esc(m.schema||'public')+'.'+esc(m.table)+'.'+esc(m.column):m?.kind==='unmapped'?'연결된 원본 없음':'분류 사전'}<br>원본 자료형: ${esc(p.sourceDataType||(m?.kind==='unmapped'?'미매핑':'분류 사전'))}<br>원본 NULL: ${c?(c.nullable?'허용':'NOT NULL'):'DB 컬럼에 직접 대응하지 않음'}<br>모델 NULL: ${p.nullable?'허용':'허용하지 않음'}</p>${c?.primaryKey?.length?'<p>원본 PK 전체: '+esc(c.primaryKey.join(' + '))+'</p>':''}${fk.map(f=>'<p>원본 FK '+esc(f.constraint)+'<br>'+esc(f.columns.join(' + '))+' → public.'+esc(f.target_table)+' ('+esc(f.target_columns.join(' + '))+')</p>').join('')}${p.mappingNote?'<p class="warning">'+esc(p.mappingNote)+'</p>':''}</details>`;}).join('');
 const location=state.definitionSources?.locations['object_types/'+obj.sourceFile]; $('#yamlFile').textContent=obj.sourceFile?`${location==='library'?'라이브러리':'미반영 초안'} / object_types/${obj.sourceFile}`:'YAML 원문 없음';
 $('#definitionYaml').textContent=obj.definitionYaml||'현재 YAML을 발행한 뒤 최신 확인을 누르세요.';
 $('#definitionJson').textContent=JSON.stringify(typeNode(obj),null,2);
 $('#relationsJson').textContent=JSON.stringify(state.model.relations.filter(r=>r.source===obj.id||r.target===obj.id).map(typeEdge),null,2);
}
function editRelation(rel){if(!rel)return;state.previewVersion++;$('#previewButton').disabled=true;$('#editor').innerHTML='<span class="eyebrow">LINK TYPE / DEFINITION</span><h2>'+esc(rel.label)+'</h2><p>'+esc(rel.note)+'</p><div id="linkDirections"><p>'+esc(rel.source)+' → '+esc(rel.displayName||rel.label)+' → '+esc(rel.target)+'<br>API: '+esc(rel.apiName||rel.name)+'</p>'+(rel.inverse?'<p>'+esc(rel.target)+' → '+esc(rel.inverse.displayName)+' → '+esc(rel.source)+'<br>API: '+esc(rel.inverse.apiName)+'<br>'+esc(rel.inverse.description)+'</p>':'')+'</div><p>Cardinality: '+esc(rel.cardinality)+' · Status: '+esc(rel.status)+'</p><p>매핑 상태: '+esc(rel.mappingStatus||'defined')+' · Backing: '+esc(rel.backing?.type||'local mapping')+'</p><pre id="definitionJson"></pre>';$('#definitionJson').textContent=JSON.stringify(typeEdge(rel),null,2);if(rel.linkProperties){$('#definitionJson').insertAdjacentHTML('beforebegin','<h3>Link properties</h3>'+Object.entries(rel.linkProperties).map(([name,p])=>`<div class="property-contract" data-link-property="${esc(name)}"><b>${esc(p.displayName||name)}</b><p>${esc(p.description)}</p><p>${esc(p.dataType)} · ${p.nullable?'NULL 허용':'필수'} · ${esc(rel.sourceMapping.properties[name].table)}.${esc(rel.sourceMapping.properties[name].column)}</p></div>`).join(''));}}
async function preview(){const obj=current();if(!obj)return message('데이터를 검증할 객체 카드를 선택하세요.');if(obj.preview?.available===false)return message(obj.preview.reason);const version=state.previewVersion;$('#previewButton').disabled=true;message();try{const result=await api('model/preview',{revision:state.revision,object_id:obj.id,search:$('#previewSearch').value});if(version!==state.previewVersion)return;state.preview=result;const s=result.stats;$('#previewStats').innerHTML=`기준 행 <b>${s.base_rows.toLocaleString()}</b> · 조인 결과 <b>${s.joined_rows.toLocaleString()}</b> · <span class="${s.duplicate_ids||s.null_ids?'warning':''}">중복 ID ${s.duplicate_ids}개 · NULL ID ${s.null_ids}행</span> · 미매칭 ${Object.entries(s.missing_joins).map(([a,n])=>`${esc(a)} ${n}행`).join(', ')||'없음'}<br>${esc(result.scope)}${result.viewOnlyProperties?.length?' ? Live view only: '+esc(result.viewOnlyProperties.join(', ')):''}${result.truncated?' · 검색 결과 일부 표시':''}${result.partial_tables.length?' · 부분 수집: '+esc(result.partial_tables.join(', ')):''}`;const cols=['id',...obj.properties.map(p=>p.id)];$('#previewTable').innerHTML='<thead><tr>'+cols.map(c=>`<th>${esc(c)}</th>`).join('')+'</tr></thead><tbody>'+result.rows.map((r,i)=>`<tr data-preview="${i}" tabindex="0">${cols.map(c=>`<td title="${esc(r.values[c])}">${esc(r.values[c])}</td>`).join('')}</tr>`).join('')+'</tbody>';$$('[data-preview]').forEach(el=>{const select=()=>sourceRows(result.rows[+el.dataset.preview],result.sources);el.onclick=select;el.onkeydown=e=>{if(e.key==='Enter')select();};});if(result.rows.length)sourceRows(result.rows[0],result.sources);else $('#sourceRows').textContent='해당 조건의 데이터가 없습니다.';}finally{$('#previewButton').disabled=current()?.preview?.available===false||!current();}}
function sourceRows(row,sources){const pending=Object.entries(current().propertyDefinitions||{}).filter(([,p])=>['needsCorrection','unmapped'].includes(p.mappingStatus)).map(([name])=>name);$('#sourceRows').innerHTML=(pending.length?'<p class="warning">원본 매핑 확인이 필요한 속성은 값을 반환하지 않습니다: '+esc(pending.join(', '))+'</p>':'')+'<h3>객체 JSON · 현재 스냅샷에서 조회</h3><pre id="objectJson">'+esc(JSON.stringify({graphLevel:'instance',node:{id:row.values.id,labels:[current().id],properties:row.values}},null,2))+'</pre><h3>원본 행 출처</h3>'+Object.entries(row.sources).map(([alias,record])=>`<h3>public.${esc(sources[alias])} <small>· ${esc(alias)}</small></h3><dl>${Object.entries(record).map(([k,v])=>`<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join('')}</dl>`).join('');}
let drag=null,moved=false,lastClickedObject=null;
function startDrag(e,obj,index){if((e.button!==0&&e.button!==1)||$('#modelCanvas').getAttribute('aria-busy')==='true')return;e.preventDefault();e.stopPropagation();moved=false;const b=obj?box(obj,index):null;drag={x:e.clientX,y:e.clientY,obj:e.button===1?null:obj,origin:b,pan:{...state.pan}};$('#modelGraph').setPointerCapture(e.pointerId);}
$('#modelGraph').ondblclick=run(()=>{if(lastClickedObject)return focusObject(lastClickedObject);});
$('#modelGraph').onpointerdown=e=>{lastClickedObject=null;if(e.button===1||!e.target.closest('.object-card,.link-hit,.link-caption'))startDrag(e);};$('#modelGraph').onpointermove=e=>{if(!drag)return;const dx=e.clientX-drag.x,dy=e.clientY-drag.y;if(Math.abs(dx)+Math.abs(dy)<4&&!moved)return;moved=true;if(drag.obj){state.positions.set(drag.obj.id,{...drag.origin,x:drag.origin.x+dx/state.zoom,y:drag.origin.y+dy/state.zoom});graph();}else{state.pan={x:drag.pan.x+dx,y:drag.pan.y+dy};transform();}};$('#modelGraph').onpointerup=()=>{const selected=drag?.obj;drag=null;lastClickedObject=!moved?selected?.id:null;if(selected&&!moved)selectObject(selected.id);else if(selected)run(()=>autoLayout(state.positions))();};$('#modelGraph').onpointercancel=()=>{if(drag?.obj)state.positions.set(drag.obj.id,drag.origin);drag=null;moved=false;lastClickedObject=null;graph();};$('#modelGraph').onmousedown=e=>{if(e.button===1)e.preventDefault();};$('#modelGraph').onauxclick=e=>{if(e.button===1)e.preventDefault();};$('#modelGraph').addEventListener('wheel',e=>{e.preventDefault();const bounds=$('#modelGraph').getBoundingClientRect(),x=e.clientX-bounds.x,y=e.clientY-bounds.y,old=state.zoom;state.zoom=Math.max(.05,Math.min(2.5,old*(e.deltaY<0?1.1:1/1.1)));state.pan={x:x-(x-state.pan.x)*state.zoom/old,y:y-(y-state.pan.y)*state.zoom/old};transform();},{passive:false});
$('#fitModel').onclick=run(async()=>{const focused=state.focus;state.focus=null;state.selected=null;state.previewVersion++;$('#previewButton').disabled=true;$('#objectJump').value='';if(focused)await autoLayout();else{graph();fit();}});$('#focusModel').onclick=run(()=>{if(current())return focusObject(state.selected);});$('#autoLayout').onclick=run(()=>autoLayout());$('#objectJump').onchange=run(e=>{if(e.target.value)return focusObject(e.target.value);});$('#previewButton').onclick=run(preview);$('#previewSearch').onkeydown=e=>{if(e.key==='Enter')run(preview)();};
$('#exportModel').onclick=()=>{const blob=new Blob([JSON.stringify({revision:state.revision,snapshotAt:state.meta?.captured_at,...modelGraphJson()},null,2)],{type:'application/json'});const link=document.createElement('a');link.href=URL.createObjectURL(blob);link.download='ontology-schema-graph.json';link.click();setTimeout(()=>URL.revokeObjectURL(link.href),1000);};
async function loadModel(){const status=await api('status');if(!status.ready)throw Error('먼저 원본 DB 탐색 화면에서 스냅샷을 수집하세요.');state.token=status.token;const [meta,saved]=await Promise.all([api('meta'),api('model')]);state.meta=meta;state.model=saved.model;state.definitionSources=saved.definitionSources;const sources=saved.definitionSources;$('#definitionSources').textContent=`라이브러리 + 미반영 ${sources.pending.length}개 파일 · ${sources.libraryPath}`;$('#applyLibrary').disabled=!sources.pending.length;state.focus=null;state.revision=saved.revision;$('#modelCount').textContent=`${state.model.objects.length} types · ${state.model.relations.length} links`;$('#objectJump').innerHTML='<option value="">객체 찾기</option>'+options(state.model.objects.map(o=>[o.id,o.id]),state.selected);$('#saveState').textContent=saved.revision?`발행 v${saved.revision} · ${new Date(saved.saved_at).toLocaleString('ko-KR')} · ${saved.yaml_matches?'YAML 원본과 일치':'YAML 미발행 변경 또는 이전 형식'} · 확인 ${new Date(saved.checked_at).toLocaleTimeString('ko-KR')}`:'저장된 모델 없음';$('#modelStoreJson').textContent=JSON.stringify({definitionStorage:'Library + dashboard drafts',previewCache:'SQLite / models.sqlite3',revision:saved.revision,savedAt:saved.saved_at,...modelGraphJson()},null,2);await autoLayout();if(state.model.objects.length){$('#previewButton').disabled=false;selectObject(current()?.id||state.model.objects[0].id);fit();}else{$('#previewButton').disabled=true;}}
$('#reloadModel').onclick=run(loadModel);
run(loadModel)();

$('#applyLibrary').onclick=run(async()=>{ $('#applyLibrary').disabled=true; message('라이브러리에 반영 중…'); try { await api('model/apply',{sourceHash:state.definitionSources.sourceHash}); await loadModel(); message('라이브러리 파일에 반영했습니다. 반영된 초안은 제거했고 Git 커밋은 생성하지 않았습니다.'); } finally { $('#applyLibrary').disabled=!state.definitionSources?.pending.length; } });
