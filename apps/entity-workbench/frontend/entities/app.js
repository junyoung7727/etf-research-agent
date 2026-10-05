import {CARD,displayCount,collectionLayout,visibleIndices,positionOf,indexedCatalog,nameGroup,dictionaryLayout} from './graph-layout.mjs';
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const S={meta:null,token:'',table:'company_profile',search:'',field:'',value:'',sort:'',direction:'asc',offset:0,rows:null,level:0,type:'COMPANY',selected:null,detail:null,vertical:true,zoom:60,pan:{x:0,y:0},reviews:[],phase:0,catalogs:new Map(),collection:null,collectionZoom:100,dictionary:true};
const phases=[['기업 기준 조회','기존 FK · 사용 가능','기업과 증권을 구분한 기존 FK를 조회합니다. 연결선은 DB의 외래키이며, 경제적 영향이나 기업 동일성에 대한 검증 완료를 뜻하지 않습니다.'],['외부 코드 · 별칭','DART 코드 + 기존 코드 사전','DART 코드는 DB 원본입니다. 별칭은 EDGE 소스의 기존 사전을 표시하며 DB 매핑 테이블은 아직 없습니다. 별칭의 확인 기록은 별도로 저장합니다.'],['동일 기업 · 관련 종목','사건 인자 · 개별 대조','event_argument의 mention_text와 entity_id를 대조하세요. 기사의 분석 대상 종목과 언급된 기업이 같다는 뜻은 아닙니다. 각 FK 값을 눌러 대상 행을 비교할 수 있습니다.'],['우선주 · 비상장 · 이력','확장 전 · 현황 점검','현재 적재 범위를 보여줍니다. 우선주·비상장 기업·식별자 이력의 신규 모델은 아직 적용하지 않았습니다. 검증 기록만으로 원본 매핑을 변경하지 않습니다.']];
const labels={entity:'모든 엔티티',actor:'행위자',company_profile:'기업',instrument:'증권',equity_profile:'주식 · 발행사',etf_profile:'ETF',document:'문서',document_entity:'문서 연결',event_argument:'사건 인자',source_event:'사건'};
const esc=s=>String(s??'NULL').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const short=s=>String(s??'NULL').length>28?String(s).slice(0,25)+'…':String(s??'NULL');
const fmt=n=>Number(n).toLocaleString('ko-KR');
async function api(path,body){const r=await fetch('/api/'+path,body?{method:'POST',headers:{'Content-Type':'application/json','X-Workbench-Token':S.token},body:JSON.stringify(body)}:{});const d=await r.json();if(!r.ok)throw Error(d.error||'요청 실패');return d;}
function toast(msg){$('#toast').textContent=msg;$('#toast').classList.add('show');clearTimeout(toast.timer);toast.timer=setTimeout(()=>$('#toast').classList.remove('show'),4500);}
function safe(fn){return (...a)=>Promise.resolve().then(()=>fn(...a)).catch(e=>toast(e.message));}
function debounce(fn,ms=250){let id;return(...a)=>{clearTimeout(id);id=setTimeout(safe(()=>fn(...a)),ms);};}
function fields(row,table,interactive=true){const fk=S.meta.foreign_keys.filter(f=>f.table===table);return '<div class="row-fields">'+Object.entries(row).map(([k,v])=>`<b>${esc(k)}</b>${interactive&&fk.some(f=>f.columns.includes(k))&&v!==null?`<button data-fk="${esc(k)}">${esc(v)} ↗</button>`:`<span>${esc(v)}</span>`}`).join('')+'</div>';}
async function hash(value){const canonical=x=>Array.isArray(x)?x.map(canonical):x&&typeof x==='object'?Object.fromEntries(Object.keys(x).sort().map(k=>[k,canonical(x[k])])):x;const bytes=new TextEncoder().encode(JSON.stringify(canonical(value)));return [...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(x=>x.toString(16).padStart(2,'0')).join('');}
function rowSource(table,row){
 const actual=Object.hasOwn(S.meta.tables,table);
 const ids=Object.entries(row).filter(([key])=>key.endsWith('_id'));
 return `<div class="row-source"><span>${actual?'원본 테이블':'코드 출처 · DB 행 아님'}</span><strong>${esc(actual?'public.'+table:table)}</strong>${ids.map(([k,v])=>`<small>${esc(k)} = ${esc(v)}</small>`).join('')}</div>`;
}
async function refreshReviews(){S.reviews=await api('reviews');renderReviews();}
function renderReviews(){const seen=new Set();const latest=S.reviews.filter(r=>{if(seen.has(r.edge_key))return false;seen.add(r.edge_key);return true;});$('#reviews').innerHTML=latest.length?latest.map(r=>`<div class="review-pill">${({confirmed:'✓ 확인',rejected:'✕ 불일치',needs_review:'◷ 보류'})[r.status]} <small title="${esc(r.edge_key)}">${esc(r.edge_key)}</small><small>${esc(r.note||'메모 없음')} · ${esc(r.recorded_at.slice(0,16))}</small></div>`).join(''):'아직 검증 기록이 없습니다. 연결을 선택해 첫 판정을 남겨보세요.';}
async function review(left,right,key,label,evidenceHash){
 const digest=evidenceHash||await hash([left.row,right.row]);
 const previous=S.reviews.find(r=>r.edge_key===key);const stale=previous&&previous.evidence_hash!==digest;
 $('#inspector').innerHTML=`<span class="eyebrow">COMPARE / ${esc(label)}</span><h3>연결 근거 대조</h3><div class="compare"><article>${rowSource(left.table,left.row)}${fields(left.row,left.table,false)}</article><article>${rowSource(right.table,right.row)}${fields(right.row,right.table,false)}</article></div><p>${stale?'⚠ 이전 검증 후 근거가 달라졌습니다. 다시 확인하세요.':previous?'이 근거의 최근 판정: '+esc(previous.status):'미검증 연결 · 아래 판정은 로컬 검증 장부에 저장됩니다.'}</p><textarea id="reviewNote" aria-label="검증 메모" placeholder="확인한 근거 또는 불일치 이유" maxlength="4000"></textarea><div class="review-actions"><button class="confirm" data-verdict="confirmed">✓ 확인</button><button data-verdict="rejected">✕ 불일치</button><button data-verdict="needs_review">◷ 보류</button></div>`;
 $$('#inspector [data-verdict]').forEach(b=>b.onclick=safe(async()=>{await api('reviews',{edge_key:key,evidence_hash:digest,status:b.dataset.verdict,note:$('#reviewNote').value});await refreshReviews();toast('검증 기록을 저장했습니다. 원본 DB는 변경하지 않습니다.');}));
}
async function inspect(row,table){
 $('#inspector').innerHTML=`<span class="eyebrow">ROW / ${esc(table)}</span><h3>${esc(row.display_name||row.mention_text||row.ticker||Object.values(row)[0])}</h3>${rowSource(table,row)}${fields(row,table)}<p>↗ 표시된 FK 값을 누르면 실제 대상 행을 대조합니다.</p>`;
 $$('#inspector [data-fk]').forEach(b=>b.onclick=safe(async()=>{const result=await api('fk?'+new URLSearchParams({table,column:b.dataset.fk,row:JSON.stringify(row)}));if(result.missing){toast('대상 행이 이 스냅샷에 없습니다. 부분 수집일 수 있으므로 FK 오류로 단정하지 마세요.');return;}await review(result.left,result.right,result.edge_key,result.label,result.evidence_hash);}));
}
let tableRequest=0;
async function loadRows(){if(!S.meta)return;const ticket=++tableRequest;const params={table:S.table,search:S.search,sort:S.sort,direction:S.direction,offset:S.offset,limit:40};if(S.field){params.field=S.field;params.value=S.value;}const result=await api('rows?'+new URLSearchParams(params));if(ticket!==tableRequest)return;S.rows=result;$('#tableSelect').value=S.table;$('#tableSource').textContent='public.'+S.table;const coverage=S.meta.tables[S.table];$('#scope').textContent=`${coverage.scope} · 수집 ${fmt(coverage.loaded)} / DB 전체 ${fmt(coverage.source_total)}행${coverage.complete?' · 전체 확보':' · 부분 스냅샷'}`;$('#filter').textContent=S.field?`${S.field} = ${S.value}`:'';
 $('#dataTable').innerHTML='<thead><tr>'+result.columns.map(c=>`<th data-sort="${esc(c)}" title="클릭하여 정렬">${esc(c)} ${S.sort===c?(S.direction==='asc'?'↑':'↓'):'↕'}</th>`).join('')+'</tr></thead><tbody>'+result.rows.map((r,i)=>`<tr data-row="${i}" tabindex="0">${result.columns.map(c=>`<td title="${esc(r[c])}">${esc(r[c])}</td>`).join('')}</tr>`).join('')+'</tbody>';
 if(!result.rows.length)$('#dataTable').insertAdjacentHTML('afterend','');
 $$('#dataTable th').forEach(th=>th.onclick=safe(async()=>{S.direction=S.sort===th.dataset.sort&&S.direction==='asc'?'desc':'asc';S.sort=th.dataset.sort;S.offset=0;await loadRows();}));
 $$('#dataTable tr[data-row]').forEach(tr=>{const select=safe(async()=>{$$('#dataTable tr').forEach(x=>x.classList.remove('selected'));tr.classList.add('selected');const row=result.rows[+tr.dataset.row];await inspect(row,S.table);if(S.table==='entity'){await selectEntity(row.entity_id,false);}else if(['company_profile','actor','instrument','equity_profile','etf_profile'].includes(S.table)){await selectEntity(row.actor_id||row.instrument_id,false);}});tr.onclick=select;tr.onkeydown=e=>{if(e.key==='Enter')select();};});
 $('#rowCount').textContent=`${fmt(result.total)}행 중 ${result.total?S.offset+1:0}–${Math.min(S.offset+40,result.total)}`;$('#page').textContent=Math.floor(S.offset/40)+1;$('#prev').disabled=!S.offset;$('#next').disabled=S.offset+40>=result.total;
}
async function table(table,field='',value=''){S.table=table;S.field=field;S.value=value;S.search='';S.sort='';S.offset=0;$('#rowSearch').value='';await loadRows();}
async function selectEntity(id,filter=true,view=null){const detail=await api('entity?'+new URLSearchParams({id}));S.detail=detail;S.selected=id;const type=detail.nodes.find(n=>n.table==='entity'&&n.row.entity_id===id)?.row.entity_type;S.type=detail.nodes.some(n=>n.table==='company_profile'&&n.row.actor_id===id)?'COMPANY':type||S.type;S.level=2;S.zoom=view?view.zoom:150;if(view){S.scale=view.scale;S.detail.expanded=true;}S.pan={x:0,y:0};await renderGraph();if(filter)await table('entity','entity_id',id);}
function svgEl(tag,attrs={},text){const el=document.createElementNS('http://www.w3.org/2000/svg',tag);Object.entries(attrs).forEach(([k,v])=>el.setAttribute(k,v));if(text!==undefined)el.textContent=text;return el;}
let clickTimer=0;
function activate(el,fn,doubleFn){
 el.setAttribute('tabindex','0');el.setAttribute('role','button');
 el.addEventListener('click',e=>{e.stopPropagation();if(!doubleFn)return safe(fn)();clearTimeout(clickTimer);if(e.detail<2)clickTimer=setTimeout(safe(fn),300);});
 if(doubleFn)el.addEventListener('dblclick',e=>{e.preventDefault();e.stopPropagation();clearTimeout(clickTimer);safe(doubleFn)();});
 el.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();safe(e.shiftKey&&doubleFn?doubleFn:fn)();}});
}
async function expandEntity(id){
 const view={scale:S.scale,zoom:S.zoom};
 await selectEntity(id,true,view);
 const results=await Promise.all(S.detail.nodes.map(n=>api('connections?'+new URLSearchParams({table:n.table,row:JSON.stringify(n.row)}))));
 await showConnections(results);
}
async function expandRow(node){
 const result=await api('connections?'+new URLSearchParams({table:node.table,row:JSON.stringify(node.row)}));
 await showConnections([result]);await inspect(node.row,node.table);
}
async function showConnections(results){
 const nodes=new Map(S.detail.nodes.map(n=>[n.id,n]));const edges=new Map(S.detail.edges.map(e=>[JSON.stringify([e.source,e.target,e.label]),e]));
 for(const result of results){result.nodes.forEach(n=>nodes.set(n.id,n));result.edges.forEach(e=>edges.set(JSON.stringify([e.source,e.target,e.label]),e));}
 S.detail={...S.detail,nodes:[...nodes.values()],edges:[...edges.values()],expanded:true};
 S.level=2;await renderGraph();
 $('#graphTitle').textContent='연결 전체 · '+fmt(edges.size)+'개';
 const partial=[...new Set(results.flatMap(r=>r.partial_tables))];
 const missing=results.reduce((n,r)=>n+r.missing.length,0);
 $('#breadcrumb').textContent=results[0].scope+(partial.length?' · 부분 수집: '+partial.join(', '):'')+(missing?' · 스냅샷 밖 대상 '+missing+'건':'');
 $('#breadcrumb').title=$('#breadcrumb').textContent;
 $('#graphHint').textContent='한 번 클릭: 원본 행 · 더블클릭 / Shift+Enter: 직접 연결 모두 확장';
}

let graphRequest=0;
function collectionOff(){const area=$('#graphArea');area.classList.remove('collection');$('#graphExtent')?.remove();area.scrollLeft=0;area.scrollTop=0;$('#graphNav').hidden=true;S.collection=null;$('#nameIndex').hidden=true;}
async function renderCollection(ticket){
 const area=$('#graphArea');
 if(!S.catalogs.has(S.type))S.catalogs.set(S.type,indexedCatalog(await api('catalog?'+new URLSearchParams({kind:S.type}))));
 if(ticket!==graphRequest)return;
 const catalog=S.catalogs.get(S.type);
 // A dictionary needs every initial reachable at every zoom; only painting is viewport-limited.
 const count=S.dictionary?catalog.total:displayCount(catalog.total,S.zoom,area.clientWidth,area.clientHeight);
 const layout=S.dictionary?dictionaryLayout(count,catalog.groups):collectionLayout(count,area.clientWidth,area.clientHeight,false);
 const previous=S.collection;const changedType=previous?.kind!==S.type;
 S.collection={catalog,layout,kind:S.type};S.collectionZoom=S.zoom;
 S.scale=.65+Math.max(0,(S.zoom-85)/95)*.55;
 
 $$('[data-move="left"],[data-move="right"]').forEach(b=>b.hidden=false);
 area.classList.add('collection');$('#graphNav').hidden=false;
 let extent=$('#graphExtent');if(!extent){extent=document.createElement('div');extent.id='graphExtent';area.prepend(extent);}
 extent.style.width=Math.max(area.clientWidth,layout.width*S.scale)+'px';extent.style.height=Math.max(area.clientHeight,layout.height*S.scale)+'px';
 if(changedType){area.scrollLeft=0;area.scrollTop=0;}
 area.dataset.dictionary=String(S.dictionary);area.dataset.total=catalog.total;area.dataset.expanded=count;
 $('#graphTitle').textContent=(S.type==='COMPANY'?'한국 기업':S.type)+' · 전체 탐색';
 $('#breadcrumb').textContent=`entity / ${S.type} / ${fmt(count)}개 펼침 · 전체 ${fmt(catalog.total)}개`;
 $('#zoom').value=S.zoom;$('#zoomLabel').textContent=S.zoom+'%';
 $$('[data-level]').forEach(b=>b.classList.toggle('active',+b.dataset.level===1));
 renderNameIndex();paintCollection();
}
function renderNameIndex(){
 const nav=$('#nameIndex');nav.hidden=false;$('#dictionary').setAttribute('aria-pressed',String(S.dictionary));
 nav.innerHTML='<span class="index-caption">이름순 · 숫자 → A–Z → ㄱ–ㅎ · 글자를 누르면 해당 구간으로 이동</span>'+S.collection.catalog.groups.map(g=>`<button data-initial="${esc(g.label)}" title="${esc(g.label)} · ${fmt(g.count)}개" aria-pressed="false">${esc(g.label)}</button>`).join('');
 nav.querySelectorAll('button').forEach(b=>b.onclick=safe(async()=>{
  const group=S.collection.catalog.groups.find(g=>g.label===b.dataset.initial);
  if(group.index>=S.collection.layout.count){S.zoom=180;await renderGraph();}
  const p=positionOf(group.index,S.collection.layout);
  $('#graphArea').scrollTo(Math.max(0,p.x*S.scale-24),Math.max(0,p.y*S.scale-24));paintCollection();
 }));
}
function paintCollection(){
 if(S.level!==1||!S.collection)return;
 const area=$('#graphArea'),scene=$('#scene'),{catalog,layout}=S.collection;
 const left=area.scrollLeft,top=area.scrollTop,scale=S.scale;
 scene.replaceChildren();scene.setAttribute('transform',`translate(${-left},${-top}) scale(${scale})`);
 const indices=visibleIndices(layout,left,top,area.clientWidth,area.clientHeight,scale);
 const fragment=document.createDocumentFragment();const columns=new Map();
 indices.forEach(i=>{const p=positionOf(i,layout),col=i%layout.columns;columns.set(col,Math.max(columns.get(col)||0,p.y+36));});
 if(!layout.bands)for(const [column,bottom] of columns){const x=CARD.padding+column*CARD.stepX-12;fragment.append(svgEl('path',{d:`M${x},${Math.max(112,top/scale-80)} V${bottom}`,class:'edge classification','stroke-dasharray':'5 4'}));}
 if(layout.bands)for(const band of layout.bands){if(band.y+72<top/scale||band.y>(top+area.clientHeight)/scale)continue;fragment.append(svgEl('text',{x:left/scale+12,y:band.y+40,class:'dictionary-label'},band.label));}
 if(top<120*scale){const root=svgEl('g',{transform:'translate(28,25)',class:'node'});root.append(svgEl('rect',{width:340,height:72,rx:8}),svgEl('text',{x:15,y:28,'font-size':15},S.type+' · '+fmt(catalog.total)+'개'),svgEl('text',{x:15,y:52,class:'subtitle'},`${fmt(layout.count)}개 펼침 · 원본 스냅샷의 실제 엔티티`));fragment.append(root);}
 for(const i of indices){const row=catalog.rows[i],p=positionOf(i,layout);fragment.append(svgEl('path',{d:`M${p.x-12},${p.y+36} H${p.x}`,class:'edge classification','stroke-dasharray':'5 4'}));const node=svgEl('g',{transform:`translate(${p.x},${p.y})`,class:'node','data-entity-id':row.entity_id,'data-index':i,'aria-label':row.display_name});node.append(svgEl('title',{},row.display_name+' / '+row.entity_id),svgEl('rect',{width:CARD.width,height:CARD.height,rx:8}),svgEl('text',{x:13,y:17,class:'tag'},`${row.entity_type} · ${fmt(i+1)} / ${fmt(catalog.total)}`),svgEl('text',{x:13,y:37,'font-size':12},short(row.display_name)),svgEl('text',{x:13,y:57,class:'subtitle'},short(row.entity_id)));activate(node,()=>selectEntity(row.entity_id),()=>expandEntity(row.entity_id));fragment.append(node);}
 scene.append(fragment);area.dataset.visible=indices.length;
 const first=indices.find(i=>{const p=positionOf(i,layout);return p.x*scale>=left&&p.y*scale>=top;});
 const initial=first===undefined?'':nameGroup(catalog.rows[first].display_name);
 $$('#nameIndex button').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.initial===initial)));
 $('#graphHint').textContent=`${fmt(layout.count)} / ${fmt(catalog.total)}개 펼침 · 클릭: 상세 · 더블클릭: 연결 전체 · 휠 버튼 드래그: 이동`;
}
let paintFrame=0;$('#graphArea').addEventListener('scroll',()=>{if(!paintFrame)paintFrame=requestAnimationFrame(()=>{paintFrame=0;paintCollection();});});
async function renderGraph(){if(!S.meta)return;const ticket=++graphRequest;const scene=$('#scene');let nodes=[],edges=[];const counts=S.meta.tables;const add=(id,title,sub,level,action,tag='')=>nodes.push({id,title,sub,level,action,tag});
 if(S.level===1)return renderCollection(ticket);
 collectionOff();
 if(S.level===0){
  add('entity','Entity','공통 명부 · '+fmt(counts.entity.loaded),0,()=>table('entity'),'ROOT');
  for(const [id,title,tab] of [['ACTOR','Actor · 행위자','actor'],['INSTRUMENT','Instrument · 증권','instrument'],['CONCEPT','Concept · 개념','entity']]){add(id,title,id==='CONCEPT'?'제품 · 지역 · 개념':fmt(counts[tab].loaded)+'개',1,async()=>{S.type=id;S.level=1;S.zoom=100;await renderGraph();await table('entity','entity_type',id);},'TYPE');edges.push({source:'entity',target:id,label:'분류',dashed:true});}
  for(const [id,title,parent,tab,kind] of [['company','Company','ACTOR','company_profile','COMPANY'],['equity','Equity','INSTRUMENT','equity_profile','EQUITY'],['etf','ETF','INSTRUMENT','etf_profile','ETF']]){add(id,title,fmt(counts[tab].loaded)+'개',2,async()=>{S.type=kind;S.level=1;S.zoom=100;await renderGraph();await table(tab);},'PROFILE');edges.push({source:parent,target:id,label:'프로파일',dashed:true});}
 }else if(S.detail){
  const rank={entity:0,actor:1,instrument:1,company_profile:2,equity_profile:3,etf_profile:2};
  S.detail.nodes.forEach(n=>add(n.id,n.table,short(n.row.display_name||n.row.ticker||n.row.dart_corp_code||n.row.entity_id||n.row.actor_id||n.row.instrument_id),rank[n.table]??2,async()=>{const key=Object.keys(n.row)[0];await table(n.table,key,n.row[key]);await inspect(n.row,n.table);},'DB ROW'));
  edges=S.detail.edges.map(e=>({...e,action:()=>review(e.left,e.right,e.edge_key,e.label,e.evidence_hash)}));
 }else{S.level=1;S.zoom=100;toast('타입에서 엔티티 하나를 선택하면 실제 행이 펼쳐집니다.');return renderGraph();}
 if(ticket!==graphRequest)return;
 scene.replaceChildren();const groups={};nodes.forEach(n=>(groups[n.level]??=[]).push(n));
 // Compact wrapped ranks: cap cross-axis width at 3 cards; avoid one enormous sibling row.
 const cardW=196,cardH=72,gap=24;let depth=28;
 Object.keys(groups).sort((a,b)=>a-b).forEach(level=>{const row=groups[level];const columns=S.vertical?Math.min(3,row.length):Math.min(4,row.length);row.forEach((n,i)=>{if(S.vertical){n.x=28+(i%columns)*(cardW+gap);n.y=depth+Math.floor(i/columns)*(cardH+gap);}else{n.x=depth+Math.floor(i/columns)*(cardW+gap);n.y=28+(i%columns)*(cardH+gap);}});depth+=S.vertical?Math.ceil(row.length/columns)*(cardH+gap)+38:Math.ceil(row.length/columns)*(cardW+gap)+45;});
 let maxX=Math.max(...nodes.map(n=>n.x+cardW),400)+28,maxY=Math.max(...nodes.map(n=>n.y+cardH),240)+28;
 const positions=Object.fromEntries(nodes.map(n=>[n.id,n]));
 for(const edge of edges){const a=positions[edge.source],b=positions[edge.target];if(!a||!b)continue;const x1=a.x+cardW/2,y1=a.y+cardH,x2=b.x+cardW/2,y2=b.y;const d=S.vertical?`M${x1},${y1} C${x1},${(y1+y2)/2} ${x2},${(y1+y2)/2} ${x2},${y2}`:`M${a.x+cardW},${a.y+cardH/2} C${(a.x+cardW+b.x)/2},${a.y+cardH/2} ${(a.x+cardW+b.x)/2},${b.y+cardH/2} ${b.x},${b.y+cardH/2}`;
  const group=svgEl('g');const hit=svgEl('path',{d,class:'edge-hit','aria-label':edge.label});if(edge.action)activate(hit,edge.action);group.append(hit,svgEl('path',{d,class:'edge','stroke-dasharray':edge.dashed?'4 4':'none','pointer-events':'none','marker-end':edge.dashed?'none':'url(#arrow)'}));if(!edge.dashed)group.append(svgEl('text',{x:S.vertical?(x1+x2)/2+5:(a.x+cardW+b.x)/2,y:S.vertical?(y1+y2)/2:(a.y===b.y?a.y-12:(a.y+b.y)/2+cardH/2+22),class:'edge-label','text-anchor':S.vertical?'start':'middle'},edge.label));scene.append(group);
 }
 for(const n of nodes){const g=svgEl('g',{transform:`translate(${n.x},${n.y})`,class:'node','aria-label':n.title});const tint=n.title.includes('instrument')||n.title.includes('Instrument')?'#7295b2':n.title.includes('Concept')?'#b5a06b':'#73936a';g.append(svgEl('rect',{width:cardW,height:cardH,rx:9}),svgEl('rect',{x:0,y:16,width:3,height:39,rx:1,style:`fill:${tint};stroke:none`}),svgEl('text',{x:14,y:17,class:'tag'},n.tag),svgEl('text',{x:14,y:37,'font-size':12},short(n.title)),svgEl('text',{x:14,y:56,class:'subtitle'},n.sub));const source=S.detail?.nodes.find(row=>row.id===n.id);activate(g,n.action,S.level===2&&source?()=>expandRow(source):undefined);scene.append(g);}
 scene.querySelectorAll('.edge-label').forEach(label=>scene.append(label));
 S.bounds={w:maxX,h:maxY};S.pan={x:0,y:0};fitGraph();$('#graphTitle').textContent=['전체 구조',S.type+' · 엔티티', '실제 행과 FK'][S.level];$('#breadcrumb').textContent=S.selected&&S.level===2?'entity / '+S.selected:'entity / '+(S.level?S.type:'모든 대상');$('#graphHint').textContent=S.level===2?'노드: 원본 행 · 연결선: 양쪽 행 비교':S.level===1?'처음 12개 표시 · 전체 목록은 오른쪽 표에서 탐색':'분류 노드를 선택해 펼치기 · 휠로 확대';$('#zoom').value=S.zoom;$('#zoomLabel').textContent=S.zoom+'%';$$('[data-level]').forEach(b=>b.classList.toggle('active',+b.dataset.level===S.level));
}
function fitGraph(){if(S.level===1){$('#graphArea').scrollLeft=0;$('#graphArea').scrollTop=0;paintCollection();return;}if(!S.bounds)return;const area=$('#graphArea');const width=area.clientWidth,height=area.clientHeight;if(!(S.detail?.expanded&&S.level===2))S.scale=Math.min(width/S.bounds.w,height/S.bounds.h,.98);applyTransform();}
function applyTransform(){if(!S.bounds)return;$$('#scene .edge-label').forEach(label=>label.style.fontSize=Math.max(13,12/S.scale)+'px');const area=$('#graphArea');const expanded=S.detail?.expanded&&S.level===2;const x=(expanded?20:(area.clientWidth-S.bounds.w*S.scale)/2)+S.pan.x,y=(expanded?20:(area.clientHeight-S.bounds.h*S.scale)/2)+S.pan.y;$('#scene').setAttribute('transform',`translate(${x},${y}) scale(${S.scale})`);}
async function zoom(value){const next=Math.max(45,Math.min(180,value));const old=S.zoom;S.zoom=next;if(S.level===2){S.scale*=next/old;applyTransform();$('#zoom').value=next;$('#zoomLabel').textContent=next+'%';return;}const level=next<85?0:1;if(level===1||level!==S.level){S.level=level;await renderGraph();}else{S.scale*=next/old;applyTransform();$('#zoom').value=next;$('#zoomLabel').textContent=next+'%';}}
async function aliases(){$('#inspector').innerHTML='<span class="eyebrow">ALIAS / SOURCE CODE</span><h3>기존 별칭 사전</h3><p>DB 행이 아닌 EDGE 코드의 별칭입니다. 대상 이름을 기업 명부에서 대조합니다.</p><div class="alias-list">'+S.meta.aliases.map((a,i)=>`<button data-alias="${i}"><span>${esc(a.alias)}</span><span>→ ${esc(a.target_name)}</span></button>`).join('')+'</div>';
 $$('#inspector [data-alias]').forEach(b=>b.onclick=safe(async()=>{const a=S.meta.aliases[+b.dataset.alias];const r=await api('rows?'+new URLSearchParams({table:'entity',field:'display_name',value:a.target_name,limit:100}));const targets=r.rows.filter(r=>r.entity_type==='ACTOR');if(targets.length!==1)return toast('대상 기업이 없거나 여러 개입니다. 수동 검색으로 확인하세요.');await selectEntity(targets[0].entity_id);await review({table:'코드 별칭 (DB 아님)',row:a},{table:'entity',row:targets[0]},'alias:'+a.alias,'별칭 · 기존 코드');}));}
async function init(){S.catalogs.clear();const status=await api('status');S.token=status.token;if(!status.ready){$('#banner').textContent='아직 스냅샷이 없습니다. 오른쪽 위 DB 스냅샷 갱신을 눌러 수집하세요.';$('#banner').classList.add('visible');$('#connection').textContent='수집 대기';return;}S.meta=await api('meta');$('#connection').textContent='AWS 읽기 전용 스냅샷';$('#stamp').textContent=new Date(S.meta.captured_at).toLocaleString('ko-KR')+' · agent_ro';$('#coverageSummary').textContent='원본 변경 없음 · 검증 기록은 로컬 저장';$('#tableSelect').innerHTML=Object.keys(S.meta.tables).map(t=>`<option value="${esc(t)}">${esc(t)}</option>`).join('');const stats=[['기업',S.meta.tables.company_profile.loaded,'COMPANY PROFILE'],['증권',S.meta.tables.instrument.loaded,'EQUITY + ETF'],['엔티티',S.meta.tables.entity.loaded,'공통 명부 · 전체'],['원본 테이블',Object.keys(S.meta.tables).length,'일부 사건·문서는 범위 제한']];$('#stats').innerHTML=stats.map(([name,n,sub])=>`<div class="stat"><span>${name}</span><strong>${fmt(n)}</strong><small>${sub}</small></div>`).join('');$('#banner').classList.remove('visible');await Promise.all([loadRows(),renderGraph(),refreshReviews()]);}
$('#phases').innerHTML=phases.map((p,i)=>`<button class="phase ${i===0?'active':''}" data-phase="${i}"><b>0${i+1}</b><span>${p[0]}<small>${p[1]}</small></span></button>`).join('');$('#phaseNote').textContent=phases[0][2];
$$('[data-phase]').forEach(b=>b.onclick=safe(async()=>{S.phase=+b.dataset.phase;$$('[data-phase]').forEach(x=>x.classList.toggle('active',x===b));$('#phaseNote').textContent=phases[S.phase][2];if(S.phase===0){await table('company_profile');}if(S.phase===1){await table('company_profile');await aliases();}if(S.phase===2){await table('event_argument');}if(S.phase===3){await table('equity_profile');}}));
$$('[data-level]').forEach(b=>b.onclick=safe(async()=>{S.level=+b.dataset.level;S.zoom=[60,S.collectionZoom,150][S.level];await renderGraph();}));
$('#entitySearch').oninput=debounce(async()=>{const query=$('#entitySearch').value;if(!query){$('#searchResults').replaceChildren();return;}const result=await api('rows?'+new URLSearchParams({table:'entity',search:query,limit:8}));let rows=result.rows;if(!rows.length){const r=await api('rows?'+new URLSearchParams({table:'instrument',search:query,limit:8}));rows=r.rows.map(x=>({entity_id:x.instrument_id,display_name:x.ticker,entity_type:'INSTRUMENT'}));}if(!rows.length){const r=await api('rows?'+new URLSearchParams({table:'company_profile',search:query,limit:8}));rows=r.rows.map(x=>({entity_id:x.actor_id,display_name:x.dart_corp_code,entity_type:'ACTOR'}));}$('#searchResults').innerHTML=rows.map(r=>`<button data-entity="${esc(r.entity_id)}">${esc(r.display_name)}<small>${esc(r.entity_type)} · ${esc(short(r.entity_id))}</small></button>`).join('')||'<p>스냅샷에서 찾지 못했습니다.</p>';$$('[data-entity]').forEach(b=>b.onclick=safe(()=>selectEntity(b.dataset.entity)));});
$('#rowSearch').oninput=debounce(async()=>{S.search=$('#rowSearch').value;S.offset=0;await loadRows();});$('#tableSelect').onchange=safe(()=>table($('#tableSelect').value));$('#clearFilter').onclick=safe(()=>table(S.table));$('#prev').onclick=safe(async()=>{S.offset=Math.max(0,S.offset-40);await loadRows();});$('#next').onclick=safe(async()=>{S.offset+=40;await loadRows();});$('#orientation').onclick=safe(async()=>{S.vertical=!S.vertical;$('#orientation').textContent=S.vertical?'세로 배치 ↓':'가로 배치 →';await renderGraph();});$('#fit').onclick=()=>{S.pan={x:0,y:0};fitGraph();};$('#reset').onclick=safe(async()=>{S.selected=null;S.detail=null;S.level=0;S.zoom=60;$('#entitySearch').value='';$('#searchResults').replaceChildren();await renderGraph();await table('company_profile');});const zoomInput=debounce(value=>zoom(value),70);$('#zoom').oninput=e=>zoomInput(Number(e.target.value));$('#zoomIn').onclick=safe(()=>zoom(S.zoom+20));$('#zoomOut').onclick=safe(()=>zoom(S.zoom-20));
$('#graph').addEventListener('wheel',e=>{if(S.level===1&&!e.ctrlKey&&!e.metaKey)return;e.preventDefault();wheelZoom(e.deltaY);},{passive:false});const wheelZoom=debounce(d=>zoom(S.zoom+(d<0?8:-8)),40);
let drag=null;
$('#graph').onpointerdown=e=>{
 if(e.button!==0&&e.button!==1)return;
 if(e.button===0&&(e.target.closest('.node')||e.target.classList.contains('edge-hit')))return;
 e.preventDefault();
 drag={x:e.clientX,y:e.clientY,pan:{...S.pan},left:$('#graphArea').scrollLeft,top:$('#graphArea').scrollTop};
 $('#graph').classList.add('dragging');$('#graph').setPointerCapture(e.pointerId);
};
$('#graph').onpointermove=e=>{if(drag){if(S.level===1){$('#graphArea').scrollLeft=drag.left+drag.x-e.clientX;$('#graphArea').scrollTop=drag.top+drag.y-e.clientY;}else{S.pan={x:drag.pan.x+e.clientX-drag.x,y:drag.pan.y+e.clientY-drag.y};applyTransform();}}};
function endDrag(){drag=null;$('#graph').classList.remove('dragging');}
$('#graph').onpointerup=endDrag;$('#graph').onpointercancel=endDrag;$('#graph').onlostpointercapture=endDrag;
$('#graph').addEventListener('mousedown',e=>{if(e.button===1)e.preventDefault();});
$('#graph').addEventListener('auxclick',e=>{if(e.button===1)e.preventDefault();});
let resize=false;$('#divider').onpointerdown=e=>{resize=true;$('#divider').setPointerCapture(e.pointerId);};$('#divider').onpointermove=e=>{if(!resize)return;const box=$('#split').getBoundingClientRect();const percent=Math.max(30,Math.min(85,(e.clientX-box.left)/box.width*100));$('#split').style.gridTemplateColumns=`minmax(0,${percent}fr) 10px minmax(0,${100-percent}fr)`;fitGraph();};$('#divider').onpointerup=()=>resize=false;new ResizeObserver(debounce(()=>S.level===1?renderGraph():fitGraph(),80)).observe($('#graphArea'));
$('#refresh').onclick=safe(async()=>{await api('refresh',{});$('#refresh').disabled=true;$('#banner').textContent='AWS에서 읽기 전용 스냅샷을 수집하고 있습니다. 기존 화면은 계속 사용할 수 있습니다.';$('#banner').classList.add('visible');const timer=setInterval(safe(async()=>{const s=await api('status');if(s.refreshing)return;clearInterval(timer);$('#refresh').disabled=false;if(s.error){$('#banner').textContent=s.error;return;}S.detail=null;S.selected=null;S.level=0;S.zoom=60;await init();toast('새 스냅샷으로 갱신했습니다. 검증 기록은 보존했습니다.');}),2000);});
$('#export').onclick=safe(async()=>{const rows=await api('reviews');const blob=new Blob([JSON.stringify({exported_at:new Date().toISOString(),source_snapshot:S.meta?.captured_at,reviews:rows},null,2)],{type:'application/json'});const link=document.createElement('a');link.href=URL.createObjectURL(blob);link.download='entity-reviews.json';link.click();setTimeout(()=>URL.revokeObjectURL(link.href),1000);});
$('#companyDocs').onclick=safe(async()=>{if(!S.detail?.actor_id)return toast('먼저 기업 또는 주식 엔티티를 선택하세요.');const docs=S.detail.documents;$('#inspector').innerHTML='<span class="eyebrow">COMPANY EVIDENCE</span><h3>기업 기준 문서</h3><p>'+esc(S.detail.documents_scope)+' · 관련 문서 전체가 아닙니다.</p>'+ (docs.length?'<div class="alias-list">'+docs.map((d,i)=>`<button data-doc="${i}"><span>${esc(short(d.title))}</span><small>${esc(d.relation_kind)}</small></button>`).join('')+'</div>':'<p>수집 범위 안에 문서가 없습니다. 기업 관련 문서가 없다는 뜻은 아닙니다.</p>');$$('[data-doc]').forEach(b=>b.onclick=safe(async()=>{const d=docs[+b.dataset.doc];await table('document','document_id',d.document_id);await inspect(d,'document');}));});
$('#dictionary').onclick=safe(async()=>{S.dictionary=!S.dictionary;$('#dictionary').setAttribute('aria-pressed',String(S.dictionary));if(S.level!==1){S.level=1;S.zoom=S.collectionZoom;}await renderGraph();});
$('#expandAll').onclick=safe(async()=>{S.level=1;S.zoom=180;await renderGraph();});
$$('[data-move]').forEach(b=>b.onclick=()=>{const area=$('#graphArea');const move=b.dataset.move;if(move==='first'){area.scrollTo(0,0);}else if(move==='last'&&S.collection){const p=positionOf(Math.max(0,S.collection.layout.count-1),S.collection.layout);area.scrollTo(Math.max(0,(p.x+CARD.width)*S.scale-area.clientWidth+28),Math.max(0,(p.y+CARD.height)*S.scale-area.clientHeight+28));}else{area.scrollBy(({left:-1,right:1}[move]||0)*area.clientWidth*.8,({up:-1,down:1}[move]||0)*area.clientHeight*.8);}});
safe(init)();
