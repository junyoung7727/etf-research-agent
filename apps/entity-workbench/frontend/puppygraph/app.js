'use strict';
const $=id=>document.getElementById(id), NS='http://www.w3.org/2000/svg';
const state={catalog:null,nodes:new Map(),edges:new Map(),selected:null,busy:false,mode:'all',root:null,cursor:'',scale:1,x:0,y:0,width:1,height:1};
const titles={Company:'회사',Equity:'주식',ETF:'ETF',Organization:'조직',ETFHolding:'보유 구성종목',DailyBar:'일봉',SourceEvent:'사건',NewsArticle:'뉴스',Disclosure:'공시',FinancialMetric:'재무지표',FinancialReportSnapshot:'보고서 수집본'};
const element=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;};
function svg(tag,attrs,text){const e=document.createElementNS(NS,tag);for(const [k,v] of Object.entries(attrs||{}))e.setAttribute(k,v);if(text!==undefined)e.textContent=text;return e;}
function notice(text,kind=''){$('notice').textContent=text;$('notice').className=kind;}
function busy(value){state.busy=value;for(const id of ['searchButton','allMode','oneMode','more'])$(id).disabled=value;$('focus').disabled=value||!state.nodes.has(state.selected);$('graph').setAttribute('aria-busy',String(value));}
async function api(path,params={}){const response=await fetch('/api/puppygraph/'+path+'?'+new URLSearchParams(params));const data=await response.json();if(!response.ok)throw new Error(data.error||'조회 실패');return data;}
function checked(data){$('connection').textContent='실데이터 연결됨';$('connection').className='connection live';$('checkedAt').textContent='마지막 조회 '+new Date(data.checkedAt).toLocaleString('ko-KR');}
function fail(error){notice(error.message,'error');$('connection').textContent='조회 실패';$('connection').className='connection failed';}
function properties(values,type){$('properties').replaceChildren(element('h3','속성'));const list=element('dl');const definition=state.catalog.objects.find(o=>o.id===type);for(const [key,value] of Object.entries(values)){const term=element('dt',key);const col=definition?.properties.find(c=>c.property===key);if(col)term.title=col.description;list.append(term);list.append(element('dd',value===null?'값 없음':typeof value==='object'?JSON.stringify(value,null,2):String(value)));}$('properties').append(list);}
function selectNode(key){const n=state.nodes.get(key);if(!n)return;state.selected=key;$('detail').replaceChildren(element('span',titles[n.type]||n.type,'type-badge'),element('h2',n.label),element('code',n.id));properties(n.properties,n.type);$('focus').disabled=state.busy;highlight();}
function selectEdge(key){const e=state.edges.get(key);state.selected=key;$('focus').disabled=true;const r=state.catalog.relations.find(r=>r.id===e.type);$('detail').replaceChildren(element('span','관계','type-badge'),element('h2',e.type.split('_')[1]),element('p',state.nodes.get(e.source).label+' → '+state.nodes.get(e.target).label),element('p',r?.description||'','muted'),element('code',e.type));properties({recordIds:e.identity,...e.properties});highlight();}
function highlight(){for(const n of document.querySelectorAll('.node,.edge'))n.classList.toggle('selected',n.dataset.key===state.selected);}
function transform(){$('scene').setAttribute('transform',`translate(${state.x},${state.y}) scale(${state.scale})`);$('zoom').textContent=Math.round(state.scale*100)+'%';}
function fit(){const w=$('graph').clientWidth,h=$('graph').clientHeight;state.scale=Math.min((w-50)/state.width,(h-50)/state.height,1.2);state.x=(w-state.width*state.scale)/2-(state.minX||0)*state.scale;state.y=(h-state.height*state.scale)/2-(state.minY||0)*state.scale;transform();}
function zoom(factor,cx=$('graph').clientWidth/2,cy=$('graph').clientHeight/2){const next=Math.max(.02,Math.min(3,state.scale*factor));state.x=cx-(cx-state.x)*next/state.scale;state.y=cy-(cy-state.y)*next/state.scale;state.scale=next;transform();}
const positions=new Map();
const colors={ETF:'#f7c75f',Company:'#70b5f7',Equity:'#7fcea4',Organization:'#b5a1ef',ETFHolding:'#f09b69',SourceEvent:'#d391d8',NewsArticle:'#a4bdde',Disclosure:'#95aec7',DailyBar:'#79cdd3',FinancialMetric:'#c6ce7e'};
let nodeDrag=null,suppressClick=false;
function nodeRadius(n){return n.type==='ETFHolding'?24:n.type==='ETF'?36:30;}
function settle(){
 const nodes=[...state.nodes.values()],index=new Map(nodes.map((n,i)=>[n.key,i]));
 const radius=Math.max(120,Math.sqrt(nodes.length)*50);
 nodes.forEach((n,i)=>{if(!positions.has(n.key)){const a=i*2.39996;const adjacent=[...state.edges.values()].find(e=>(e.source===n.key&&positions.has(e.target))||(e.target===n.key&&positions.has(e.source)));const origin=adjacent?positions.get(adjacent.source===n.key?adjacent.target:adjacent.source):{x:0,y:0};positions.set(n.key,{x:origin.x+Math.cos(a)*radius,y:origin.y+Math.sin(a)*radius,pinned:false});}});
 const links=[...state.edges.values()].map(e=>[index.get(e.source),index.get(e.target)]);
 for(let tick=0;tick<(nodes.length>150?60:240);tick++){
  const force=nodes.map(()=>({x:0,y:0})),alpha=.7*(1-tick/270);
  for(let i=0;i<nodes.length;i++)for(let j=i+1;j<nodes.length;j++){
   const a=positions.get(nodes[i].key),b=positions.get(nodes[j].key);let dx=b.x-a.x,dy=b.y-a.y;
   if(Math.abs(dx)+Math.abs(dy)<.01){dx=.1*(i+1);dy=.1*(j+1);}
   const d=Math.max(1,Math.hypot(dx,dy)),push=Math.min(18,7000/(d*d)+(d<100?(100-d)*.22:0));
   force[i].x-=dx/d*push;force[i].y-=dy/d*push;force[j].x+=dx/d*push;force[j].y+=dy/d*push;
  }
  for(const [i,j] of links){if(i===j)continue;const a=positions.get(nodes[i].key),b=positions.get(nodes[j].key),dx=b.x-a.x,dy=b.y-a.y,d=Math.max(1,Math.hypot(dx,dy)),pull=(d-165)*.025;force[i].x+=dx/d*pull;force[i].y+=dy/d*pull;force[j].x-=dx/d*pull;force[j].y-=dy/d*pull;}
  nodes.forEach((n,i)=>{const p=positions.get(n.key);if(!p.pinned){p.x+=Math.max(-14,Math.min(14,force[i].x-p.x*.0015))*alpha;p.y+=Math.max(-14,Math.min(14,force[i].y-p.y*.0015))*alpha;}});
 }
}
function networkBounds(){
 const points=[...state.nodes.keys()].map(k=>positions.get(k));
 const minX=Math.min(...points.map(p=>p.x),0)-100,minY=Math.min(...points.map(p=>p.y),0)-80;
 const maxX=Math.max(...points.map(p=>p.x),0)+100,maxY=Math.max(...points.map(p=>p.y),0)+100;
 state.minX=minX;state.minY=minY;state.width=maxX-minX;state.height=maxY-minY;
}
function drawNetwork(){
 const pairs=new Map();
 for(const e of state.edges.values()){const pair=JSON.stringify([e.source,e.target].sort());if(!pairs.has(pair))pairs.set(pair,[]);pairs.get(pair).push(e.key);}
 for(const group of $('scene').querySelectorAll('.edge')){
  const e=state.edges.get(group.dataset.key),a=positions.get(e.source),b=positions.get(e.target);
  const twins=pairs.get(JSON.stringify([e.source,e.target].sort())),offset=(twins.indexOf(e.key)-(twins.length-1)/2)*38;
  const dx=b.x-a.x,dy=b.y-a.y,d=Math.max(1,Math.hypot(dx,dy)),nx=dx/d,ny=dy/d;
  const ra=nodeRadius(state.nodes.get(e.source))+3,rb=nodeRadius(state.nodes.get(e.target))+7;
  let path,lx,ly,angle;
  if(e.source===e.target){const lift=115+twins.indexOf(e.key)*36;path=`M ${a.x-20} ${a.y-22} C ${a.x-95} ${a.y-lift},${a.x+95} ${a.y-lift},${a.x+20} ${a.y-28}`;lx=a.x;ly=a.y-lift*.75-6;angle=0;}
  else{const bend=offset*(e.source<e.target?1:-1);const cx=(a.x+b.x)/2-ny*bend,cy=(a.y+b.y)/2+nx*bend;path=`M ${a.x+nx*ra} ${a.y+ny*ra} Q ${cx} ${cy} ${b.x-nx*rb} ${b.y-ny*rb}`;lx=(a.x+b.x)/2-ny*bend/2;ly=(a.y+b.y)/2+nx*bend/2;angle=Math.atan2(dy,dx)*180/Math.PI;if(angle>90||angle<-90)angle+=180;}
  for(const p of group.querySelectorAll('path'))p.setAttribute('d',path);
  group.querySelector('.edge-caption').setAttribute('transform',`translate(${lx},${ly}) rotate(${angle})`);
 }
 for(const group of $('scene').querySelectorAll('.node')){const p=positions.get(group.dataset.key);group.setAttribute('transform',`translate(${p.x},${p.y})`);}
}
async function render(){
 settle();$('scene').replaceChildren();
 for(const e of state.edges.values()){
  const text=e.properties.roleCode||e.type.split('_')[1],width=Math.max(60,text.length*6+14);
  const group=svg('g',{class:'edge',tabindex:'0',role:'button','aria-label':text});group.dataset.key=e.key;
  group.append(svg('path',{class:'edge-hit'}),svg('path',{class:'edge-line','marker-end':'url(#arrow)'}));
  const caption=svg('g',{class:'edge-caption'});caption.append(svg('rect',{x:-width/2,y:-9,width,height:18,rx:3,class:'edge-label-bg'}),svg('text',{'text-anchor':'middle',y:4},text));group.append(caption);
  group.onclick=()=>selectEdge(e.key);group.onkeydown=event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();selectEdge(e.key);}};$('scene').append(group);
 }
 for(const n of state.nodes.values()){
  const r=nodeRadius(n),color=colors[n.type]||'#a1b8cb',group=svg('g',{class:'node',tabindex:'0',role:'button','aria-label':(titles[n.type]||n.type)+' '+n.label});group.dataset.key=n.key;group.dataset.type=n.type;
  group.append(svg('title',{},n.label+'\n'+n.type+'\n'+n.id),svg('circle',{r:r+6,class:'node-halo'}),svg('circle',{r,fill:color,class:'node-circle'}));
  const center=n.type==='ETFHolding'?(n.properties.weightRatio===null?'?':new Intl.NumberFormat('ko-KR',{style:'percent',maximumFractionDigits:1}).format(n.properties.weightRatio)):titles[n.type]||n.type;
  group.append(svg('text',{'text-anchor':'middle',y:4,class:'node-center'},center.length>9?center.slice(0,8):center));
  const label=n.type==='ETFHolding'?(n.properties.tradeDate||n.label):n.label;
  group.append(svg('text',{'text-anchor':'middle',y:r+23,class:'node-title'},label.length>17?label.slice(0,16)+'…':label));
  group.onclick=()=>{if(!suppressClick)selectNode(n.key);};
  group.ondblclick=()=>{if(!state.busy){selectNode(n.key);focus();}};
  group.onkeydown=event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();selectNode(n.key);if(event.shiftKey)focus();}};
  group.onpointerdown=event=>{if(event.button!==0)return;event.stopPropagation();const p=positions.get(n.key);nodeDrag={key:n.key,x:event.clientX,y:event.clientY,px:p.x,py:p.y,moved:false};suppressClick=false;group.setPointerCapture(event.pointerId);};
  group.onpointermove=event=>{if(!nodeDrag||nodeDrag.key!==n.key)return;const dx=event.clientX-nodeDrag.x,dy=event.clientY-nodeDrag.y;if(Math.hypot(dx,dy)>4)nodeDrag.moved=true;if(nodeDrag.moved){const p=positions.get(n.key);p.x=nodeDrag.px+dx/state.scale;p.y=nodeDrag.py+dy/state.scale;p.pinned=true;drawNetwork();}};
  group.onpointerup=group.onpointercancel=()=>{if(nodeDrag){suppressClick=nodeDrag.moved;nodeDrag=null;networkBounds();setTimeout(()=>suppressClick=false,0);}};
  $('scene').append(group);
 }
 drawNetwork();networkBounds();$('empty').hidden=state.nodes.size>0;$('counts').textContent=`객체 ${state.nodes.size} · 관계 ${state.edges.size}`;highlight();fit();
 $('legend').replaceChildren();for(const type of new Set([...state.nodes.values()].map(n=>n.type))){const chip=element('span',titles[type]||type);chip.style.setProperty('--node-color',colors[type]||'#a1b8cb');$('legend').append(chip);}
}

function modes(){for(const mode of ['all','one'])$(mode+'Mode').setAttribute('aria-pressed',String(state.mode===mode));$('graphTitle').textContent=state.mode==='all'?'전체 연결':(state.root?.label||'중심 객체 선택')+' · 모든 연결';}
async function load(reset=false,mode=state.mode,root=state.root){
 if(state.busy)return;busy(true);notice('모든 관계 종류를 조회하고 있습니다. 잠시 기다려 주세요.');
 try{
  const params=mode==='one'?{kind:root.type,identifier:root.id}:{};
  if(!reset)params.cursor=state.cursor;
  const data=await api('connections',params);
  if(reset){state.nodes.clear();state.edges.clear();positions.clear();state.selected=null;$('detail').replaceChildren(element('h2','객체나 연결을 선택하세요.'));$('properties').replaceChildren();if(root&&mode==='one')state.nodes.set(root.key,root);}
  state.mode=mode;state.root=root;state.cursor=data.cursor;
  for(const n of data.nodes)state.nodes.set(n.key,n);for(const e of data.edges)state.edges.set(e.key,e);
  await render();modes();checked(data);$('more').hidden=data.complete;
  if(root&&mode==='one')selectNode(root.key);
  $('empty').replaceChildren(element('h3','조회된 연결이 없습니다.'));
  const blocked=state.catalog.relations.filter(r=>r.blocked&&(!root||mode==='all'||[r.source,r.target].includes(root.type))).length;
  notice((data.complete?'구현된 관계 조회 완료':'일부 연결 표시 중 · '+data.remainingRelations+'개 관계 종류에 남은 데이터가 있습니다. 이어보기로 계속 불러오세요.')+` · 객체 ${state.nodes.size}개 / 연결 ${state.edges.size}개`+(blocked?` · 미구현 관계 ${blocked}종은 제외`:''),data.complete?'':'warning');
 }catch(error){fail(error);}finally{busy(false);}
}
async function focus(){const n=state.nodes.get(state.selected);if(n)await load(true,'one',n);}
async function search(event){event?.preventDefault();if(state.busy)return;busy(true);try{const data=await api('search',{kind:$('rootType').value,query:$('query').value.trim()});$('results').replaceChildren();for(const n of data.nodes){const b=element('button',undefined,'result');b.append(element('strong',n.label),element('small',n.type+' · '+n.id));b.onclick=()=>load(true,'one',n);$('results').append(b);}$('searchStatus').textContent=`${data.nodes.length}개 검색됨`+(data.truncated?' · 검색어를 좁혀 주세요.':'');checked(data);}catch(error){fail(error);}finally{busy(false);}}
$('searchForm').onsubmit=search;$('allMode').onclick=()=>load(true,'all',null);$('oneMode').onclick=()=>{const n=state.nodes.get(state.selected)||state.root;if(n)load(true,'one',n);else{notice('검색 결과나 그래프에서 중심 객체를 선택하세요.');$('query').focus();}};$('more').onclick=()=>load();$('focus').onclick=focus;
$('fit').onclick=fit;$('zoomIn').onclick=()=>zoom(1.25);$('zoomOut').onclick=()=>zoom(.8);
let drag=null;$('graph').onpointerdown=e=>{if(e.target.closest('.node,.edge')||e.button!==0)return;drag={x:e.clientX,y:e.clientY,dx:state.x,dy:state.y};$('graph').setPointerCapture(e.pointerId);};$('graph').onpointermove=e=>{if(drag){state.x=drag.dx+e.clientX-drag.x;state.y=drag.dy+e.clientY-drag.y;transform();}};$('graph').onpointerup=$('graph').onpointercancel=()=>drag=null;$('graph').addEventListener('wheel',e=>{e.preventDefault();const r=$('graph').getBoundingClientRect();zoom(e.deltaY>0?.9:1.1,e.clientX-r.left,e.clientY-r.top);},{passive:false});window.addEventListener('resize',fit);
(async()=>{try{state.catalog=await api('catalog');if(state.catalog.modelChanged)throw new Error('객체 모델 변경 후 그래프 매핑을 갱신해야 합니다.');await load(true);}catch(error){fail(error);}})();
