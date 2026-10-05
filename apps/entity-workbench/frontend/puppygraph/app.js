'use strict';
const $=id=>document.getElementById(id);
const state={catalog:null,nodes:new Map(),edges:new Map(),scopes:new Map(),expanded:new Set(),rootsExpanded:new Set(),rootTypes:[],selected:null,busy:false,mode:'all',root:null,cursor:''};
const titles={Company:'회사',Equity:'주식',ETF:'ETF',Organization:'조직',ETFHolding:'보유 구성종목',DailyBar:'일봉',SourceEvent:'사건',NewsArticle:'뉴스',Disclosure:'공시',FinancialMetric:'재무지표',FinancialReportSnapshot:'보고서 수집본',DailyInvestorFlow:'일별 투자자 수급',DailyNAV:'일별 순자산가치',EventThread:'사건 흐름',ExchangeSecurityClassification:'거래소 증권 분류',IntradayInvestorFlow:'장중 투자자 수급',MarketCapitalization:'시가총액',ReportedBusinessSegment:'보고된 사업부문',SecurityIndustryClassification:'증권 업종 분류',SecurityListingSnapshot:'상장정보',Concept:'개념',MarketIndex:'시장 지수'};
const colors={ETF:'#f7c75f',Company:'#70b5f7',Equity:'#7fcea4',Organization:'#b5a1ef',ETFHolding:'#f09b69',SourceEvent:'#d391d8',NewsArticle:'#a4bdde',Disclosure:'#95aec7',DailyBar:'#79cdd3',FinancialMetric:'#c6ce7e'};
const element=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;};
const label=n=>n.group?(titles[n.type]||n.type):n.label;
const reducedMotion=matchMedia('(prefers-reduced-motion: reduce)').matches;
function notice(text,kind=''){$('notice').textContent=text;$('notice').className=kind;}
function busy(value){state.busy=value;for(const id of ['searchButton','allMode','oneMode','more'])$(id).disabled=value;$('focus').disabled=value||!state.nodes.has(state.selected);$('graph').setAttribute('aria-busy',String(value));}
async function api(path,params={}){const response=await fetch('/api/puppygraph/'+path+'?'+new URLSearchParams(params));const data=await response.json();if(!response.ok)throw new Error(data.error||'조회 실패');return data;}
function checked(data){$('connection').textContent='실데이터 연결됨';$('connection').className='connection live';$('checkedAt').textContent='마지막 조회 '+new Date(data.checkedAt).toLocaleString('ko-KR');}
function fail(error){notice(error.message,'error');$('connection').textContent='조회 실패';$('connection').className='connection failed';}
function properties(values,type){$('properties').replaceChildren(element('h3','속성'));const list=element('dl');const definition=state.catalog.objects.find(o=>o.id===type);for(const [key,value] of Object.entries(values)){const term=element('dt',key);const col=definition?.properties.find(c=>c.property===key);if(col)term.title=col.description;list.append(term,element('dd',value===null?'값 없음':typeof value==='object'?JSON.stringify(value,null,2):String(value)));}$('properties').append(list);}
function selectNode(key){
 const n=state.nodes.get(key);if(!n)return;state.selected=key;
 $('detail').replaceChildren(element('span',titles[n.type]||n.type,'type-badge'),element('h2',n.label),element('code',n.id));
 const scope=state.scopes.get(key),toggle=element('button',state.expanded.has(key)?'이 객체의 연결 접기':'이 객체의 연결 펼치기','branch-button');
 toggle.onclick=()=>toggleNode(key);toggle.disabled=state.busy;$('detail').append(toggle);
 if(scope){
  $('detail').append(element('p',scope.complete?`이 객체의 연결 ${scope.edgeKeys.size}개 조회 완료`:`이 객체의 연결 ${scope.edgeKeys.size}개 조회 · 남은 연결 있음`,'muted'));
  if(!scope.complete){const more=element('button','이 객체의 남은 연결 불러오기','branch-button');more.onclick=()=>loadBranch(key,true);more.disabled=state.busy;$('detail').append(more);}
 }else $('detail').append(element('p','이 객체를 클릭하면 실제로 연결된 데이터만 조회해 펼칩니다.','muted'));
 properties(n.properties,n.type);$('focus').disabled=state.busy;highlight();
}
function selectEdge(key){
 const e=state.edges.get(key);if(!e)return;state.selected=key;$('focus').disabled=true;const r=state.catalog.relations.find(r=>r.id===e.type);
 $('detail').replaceChildren(element('span','관계','type-badge'),element('h2',e.type.split('_')[1]),element('p',state.nodes.get(e.source).label+' → '+state.nodes.get(e.target).label),element('p',r?.description||'','muted'),element('code',e.type));properties({recordIds:e.identity,...e.properties});highlight();
}
let visibleNodes=new Map(),visibleEdges=new Map(),fitAfterLayout=false;
const graphNodes=new vis.DataSet(),graphEdges=new vis.DataSet();
const network=new vis.Network($('graph'),{nodes:graphNodes,edges:graphEdges},{
 layout:{randomSeed:24,improvedLayout:false},
 nodes:{shape:'dot',size:22,borderWidth:2,font:{color:'#dce8f3',size:13,face:'Malgun Gothic',strokeWidth:3,strokeColor:'#121a23'},widthConstraint:{maximum:180}},
 edges:{color:{color:'#627c75',highlight:'#f7c75f'},width:1.2,arrows:{to:{enabled:true,scaleFactor:.65}},font:{color:'#a4b9cc',size:10,face:'Consolas',strokeWidth:3,strokeColor:'#121a23',align:'middle'},smooth:{enabled:true,type:'continuous',roundness:.18}},
 interaction:{hover:true,tooltipDelay:250,keyboard:{enabled:true,bindToWindow:false},multiselect:false},
 physics:{solver:'barnesHut',barnesHut:{gravitationalConstant:-9000,centralGravity:.12,springLength:210,springConstant:.025,damping:.28,avoidOverlap:.7},stabilization:{enabled:true,iterations:180,fit:false},maxVelocity:30,minVelocity:.5},
});
function fit(){network.fit({animation:reducedMotion?false:{duration:400,easingFunction:'easeInOutQuad'}});}
function zoom(factor){network.moveTo({scale:Math.max(.05,Math.min(3,network.getScale()*factor)),animation:reducedMotion?false:{duration:200}});}
network.on('zoom',()=>{$('zoom').textContent=Math.round(network.getScale()*100)+'%';});
network.on('stabilized',()=>{if(fitAfterLayout){fitAfterLayout=false;fit();}$('zoom').textContent=Math.round(network.getScale()*100)+'%';});
network.on('click',event=>{if(event.nodes.length)activateNode(event.nodes[0]);else if(event.edges.length)selectVisibleEdge(event.edges[0]);});
network.on('hoverNode',()=>{$('graph').style.cursor='pointer';});network.on('blurNode',()=>{$('graph').style.cursor='grab';});
$('graph').addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){const key=network.getSelectedNodes()[0];if(key){event.preventDefault();activateNode(key);}}});
function highlight(){if(visibleNodes.has(state.selected))network.selectNodes([state.selected]);else if(visibleEdges.has(state.selected))network.selectEdges([state.selected]);else network.unselectAll();}
function render(anchor=null,reset=false){
 const projected=GraphExploration.project(state);visibleNodes=projected.nodes;visibleEdges=projected.edges;
 const origin=anchor&&graphNodes.get(anchor)?network.getPosition(anchor):{x:0,y:0};let added=0;
 graphEdges.remove(graphEdges.getIds().filter(key=>!visibleEdges.has(key)));graphNodes.remove(graphNodes.getIds().filter(key=>!visibleNodes.has(key)));
 const items=[...visibleNodes.values()].map(n=>{
  const color=colors[n.type]||'#a1b8cb',text=label(n),isOpen=n.group?state.rootsExpanded.has(n.type):state.expanded.has(n.key);
  const caption=n.group?`${text}\n${n.expandable?(isOpen?'−':'+'):'·'} ${n.count}`:text.length>52?text.slice(0,51)+'…':text;
  const item={id:n.key,label:caption,title:element('div',n.group?`${text} · ${n.expandable?'클릭하여 개별 객체 펼침·접힘':'구체적인 상위 객체를 클릭해 연결을 펼치세요'}`:`${n.label}\n${n.type}\n${n.id}`),shape:n.group?'box':'dot',size:state.root?.key===n.key?30:22,color:{background:n.group?'#203142':color,border:color,highlight:{background:n.group?'#334e64':color,border:'#f5f9ff'},hover:{background:n.group?'#30465a':color,border:'#ffffff'}},font:{color:'#dce8f3'},borderWidth:isOpen?3:1.5,shapeProperties:{borderDashes:n.group?[5,4]:false},margin:12};
  if(!graphNodes.get(n.key)){const angle=added++*2.39996;item.x=origin.x+Math.cos(angle)*140;item.y=origin.y+Math.sin(angle)*140;}
  return item;
 });
 graphNodes.update(items);
 const pairs=new Map();for(const e of visibleEdges.values()){const pair=JSON.stringify([e.source,e.target].sort());if(!pairs.has(pair))pairs.set(pair,[]);pairs.get(pair).push(e.key);}
 graphEdges.update([...visibleEdges.values()].map(e=>{
  const twins=pairs.get(JSON.stringify([e.source,e.target].sort())),index=twins.indexOf(e.key);
  return {id:e.key,from:e.source,to:e.target,label:e.membership?'':(e.properties.roleCode||e.type.split('_')[1])+(e.summary?' · '+e.originalKeys.length:''),dashes:!!e.membership,arrows:{to:{enabled:!e.membership}},color:{color:e.membership?'#394e62':'#627c94'},smooth:{enabled:true,type:twins.length>1?'curvedCW':'continuous',roundness:twins.length>1?.12+index*.12:.18},selfReference:{size:35+index*20}};
 }));
 fitAfterLayout=reset||added>0;network.startSimulation();highlight();
 $('empty').hidden=visibleNodes.size>0;$('counts').textContent=`실제 객체 ${[...visibleNodes.values()].filter(n=>!n.group).length}개 표시 · ${state.nodes.size}개 불러옴`;
 $('legend').replaceChildren();for(const type of new Set([...visibleNodes.values()].map(n=>n.type))){const chip=element('span',titles[type]||type);chip.style.setProperty('--node-color',colors[type]||'#a1b8cb');$('legend').append(chip);}
 $('graphList').replaceChildren();for(const n of visibleNodes.values()){const button=element('button',n.group?`${label(n)} · ${n.count}개 ${n.expandable?'펼침·접힘':'상위 객체 필요'}`:`${n.label} · 연결 펼침·접힘`,'result');button.onclick=()=>activateNode(n.key);if(n.group&&n.expandable)button.setAttribute('aria-expanded',String(state.rootsExpanded.has(n.type)));$('graphList').append(button);}
}
function activateNode(key){
 const n=visibleNodes.get(key);if(!n||state.busy)return;
 if(!n.group){toggleNode(key);return;}
 state.selected=key;$('focus').disabled=true;$('properties').replaceChildren();
 if(!n.expandable){$('detail').replaceChildren(element('span','접힌 데이터 타입','type-badge'),element('h2',label(n)),element('p','이 타입의 데이터를 전체 펼칠 수는 없습니다. 연결된 구체적인 회사·종목 등의 객체를 클릭하면 그 객체의 데이터만 펼쳐집니다.'));highlight();return;}
 if(state.rootsExpanded.has(n.type))state.rootsExpanded.delete(n.type);else state.rootsExpanded.add(n.type);
 render(key);$('detail').replaceChildren(element('span','탐색 시작 타입','type-badge'),element('h2',label(n)),element('p','개별 객체를 클릭하면 해당 객체의 실제 연결을 조회하고 펼칩니다.'));
}
function selectVisibleEdge(key){
 const e=visibleEdges.get(key);if(!e||e.membership)return;
 if(!e.summary){selectEdge(key);return;}
 state.selected=key;$('focus').disabled=true;
 $('detail').replaceChildren(element('span','접힌 실제 관계','type-badge'),element('h2',e.type.split('_')[1]),element('p',`${label(visibleNodes.get(e.source))} → ${label(visibleNodes.get(e.target))}`),element('p',`불러온 관계 ${e.originalKeys.length}개. 구체적인 객체를 클릭하면 해당 객체의 연결을 펼칩니다.`));
 $('properties').replaceChildren();for(const originalKey of e.originalKeys){const original=state.edges.get(originalKey),button=element('button',`${state.nodes.get(original.source).label} → ${state.nodes.get(original.target).label}`,'result');button.onclick=()=>selectEdge(originalKey);$('properties').append(button);}highlight();
}
function merge(data){for(const n of data.nodes)state.nodes.set(n.key,n);for(const e of data.edges)state.edges.set(e.key,e);}
function rememberScope(key,data,append=false){
 const previous=append?state.scopes.get(key)?.edgeKeys:[];
 state.scopes.set(key,{edgeKeys:new Set([...(previous||[]),...data.edges.map(e=>e.key)]),cursor:data.cursor,complete:data.complete});
}
async function toggleNode(key){
 if(state.busy)return;
 if(state.expanded.has(key)){state.expanded.delete(key);render(key);selectNode(key);return;}
 if(state.scopes.has(key)){state.expanded.add(key);render(key);selectNode(key);return;}
 await loadBranch(key);
}
async function loadBranch(key,more=false){
 if(state.busy)return;const n=state.nodes.get(key),scope=state.scopes.get(key);if(!n||(more&&(!scope||scope.complete)))return;
 busy(true);notice(`${n.label}에 직접 연결된 데이터를 조회하고 있습니다.`);
 try{
  const data=await api('connections',{kind:n.type,identifier:n.id,...(more?{cursor:scope.cursor}:{})});
  if(data.edges.some(e=>e.source!==key&&e.target!==key))throw new Error('선택한 객체와 무관한 연결이 반환되었습니다. 기존 화면을 유지합니다.');
  merge(data);rememberScope(key,data,more);state.expanded.add(key);render(key);checked(data);
  if(state.mode==='one'&&state.root?.key===key){state.cursor=data.cursor;$('more').hidden=data.complete;}
  notice(`${n.label} · 연결 ${state.scopes.get(key).edgeKeys.size}개 ${data.complete?'조회 완료':'일부 조회 · 상세 패널에서 남은 연결을 불러올 수 있습니다.'}`,data.complete?'':'warning');
 }catch(error){fail(error);}finally{busy(false);selectNode(key);}
}
function modes(){for(const mode of ['all','one'])$(mode+'Mode').setAttribute('aria-pressed',String(state.mode===mode));$('graphTitle').textContent=state.mode==='all'?'전체 연결':(state.root?.label||'중심 객체 선택')+' · 연결 탐색';}
async function load(reset=false,mode=state.mode,root=state.root){
 if(state.busy)return;busy(true);notice('실제 연결을 불러오고 있습니다. 잠시 기다려 주세요.');
 try{
  const params=mode==='one'?{kind:root.type,identifier:root.id}:{};if(!reset)params.cursor=state.cursor;
  const data=await api('connections',params);
  if(reset){state.nodes.clear();state.edges.clear();state.scopes.clear();state.expanded.clear();state.rootsExpanded.clear();state.selected=null;graphEdges.clear();graphNodes.clear();$('detail').replaceChildren(element('h2','타입을 펼친 뒤 개별 객체를 선택하세요.'));$('properties').replaceChildren();if(root&&mode==='one')state.nodes.set(root.key,root);}
  state.mode=mode;state.root=root;state.cursor=data.cursor;merge(data);
  if(root&&mode==='one')rememberScope(root.key,data,!reset);
  render(null,reset);modes();checked(data);$('more').hidden=data.complete;
  $('empty').replaceChildren(element('h3','조회된 연결이 없습니다.'));
  const blocked=state.catalog.relations.filter(r=>r.blocked&&(!root||mode==='all'||[r.source,r.target].includes(root.type))).length;
  notice((data.complete?'현재 조회 범위의 관계 조회 완료':'일부 연결 표시 중 · 남은 데이터는 이어보기로 불러오세요.')+` · 객체 ${state.nodes.size}개 / 연결 ${state.edges.size}개`+(blocked?` · 미구현 관계 ${blocked}종 제외`:''),data.complete?'':'warning');
 }catch(error){fail(error);}finally{busy(false);if(state.mode==='one'&&state.root)selectNode(state.root.key);}
}
async function focus(){const n=state.nodes.get(state.selected);if(n)await load(true,'one',n);}
async function search(event){event?.preventDefault();if(state.busy)return;busy(true);try{const data=await api('search',{kind:$('rootType').value,query:$('query').value.trim()});$('results').replaceChildren();for(const n of data.nodes){const b=element('button',undefined,'result');b.append(element('strong',n.label),element('small',n.type+' · '+n.id));b.onclick=()=>load(true,'one',n);$('results').append(b);}$('searchStatus').textContent=`${data.nodes.length}개 검색됨`+(data.truncated?' · 검색어를 좁혀 주세요.':'');checked(data);}catch(error){fail(error);}finally{busy(false);}}
$('searchForm').onsubmit=search;$('allMode').onclick=()=>load(true,'all',null);$('oneMode').onclick=()=>{const n=state.nodes.get(state.selected)||state.root;if(n)load(true,'one',n);else{notice('검색 결과나 그래프에서 중심 객체를 선택하세요.');$('query').focus();}};$('more').onclick=()=>load();$('focus').onclick=focus;
$('fit').onclick=fit;$('zoomIn').onclick=()=>zoom(1.25);$('zoomOut').onclick=()=>zoom(.8);
(async()=>{try{state.catalog=await api('catalog');state.rootTypes=state.catalog.rootTypes||['Company','Equity','ETF','Organization'];if(state.catalog.modelChanged)throw new Error('객체 모델 변경 후 그래프 매핑을 갱신해야 합니다.');await load(true);}catch(error){fail(error);}})();
