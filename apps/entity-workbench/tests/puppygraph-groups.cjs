const {chromium}=require('../../edge/node_modules/@playwright/test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const node=(type,id)=>({key:JSON.stringify([type,id]),type,id,label:id,properties:{amount:'9007199254740993.01'}});
const [a,b,na,nb,shared,event,extra]=[node('Equity','A stock'),node('Equity','B stock'),node('NewsArticle','A news'),node('NewsArticle','B news'),node('NewsArticle','shared news'),node('SourceEvent','A event'),node('NewsArticle','A next page')];
const edge=(id,source,target,role='')=>({key:id,type:source.type+'_Link_'+target.type,source:source.key,target:target.key,identity:[id],properties:{roleCode:role}});
const edges=[edge('a',na,a),edge('b',nb,b),edge('sa',shared,a),edge('sb',shared,b),edge('ev',na,event),edge('role',na,a,'buyer')];
const response=(nodes,edges,complete=false,cursor='next')=>({nodes,edges,complete,cursor:complete?'':cursor,remainingRelations:1,checkedAt:new Date().toISOString()});
(async()=>{
 const browser=await chromium.launch({headless:true});const page=await browser.newPage({viewport:{width:1650,height:1080}});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
 let calls=[],failB=false;
 const ready=()=>page.waitForFunction(()=>typeof state!=='undefined'&&!state.busy&&graphNodes.length>0);
 const click=async key=>{
  const point=await page.evaluate(key=>{network.stopSimulation();network.fit({animation:false});const p=network.canvasToDOM(network.getPosition(key)),r=document.querySelector('#graph').getBoundingClientRect();return {x:r.x+p.x,y:r.y+p.y};},key);
  await page.mouse.click(point.x,point.y);await ready();
 };
 const records=()=>page.evaluate(()=>[...visibleNodes.values()].filter(n=>!n.group).map(n=>n.key).sort());
 const expected=nodes=>nodes.map(n=>n.key).sort();
 try{
  await page.route('**/api/puppygraph/**',route=>{
   const url=new URL(route.request().url());let data;
   if(url.pathname.endsWith('/catalog'))data={rootTypes:['Equity'],objects:['Equity','NewsArticle','SourceEvent'].map(id=>({id,properties:[]})),relations:[]};
   else if(url.pathname.endsWith('/search'))data={nodes:[a],checkedAt:new Date().toISOString()};
   else{
    calls.push(Object.fromEntries(url.searchParams));const id=url.searchParams.get('identifier'),cursor=url.searchParams.get('cursor');
    if(id===b.id&&failB)return route.fulfill({status:503,json:{error:'Branch unavailable'}});
    if(id===a.id)data=cursor?response([extra,a],[edge('next',extra,a)],true):response([a,na,shared],edges.filter(e=>['a','sa','role'].includes(e.key)),false,'A-next');
    else if(id===b.id)data=response([b,nb,shared],edges.filter(e=>['b','sb'].includes(e.key)),true);
    else if(id===na.id)data=response([na,a,event],edges.filter(e=>['a','role','ev'].includes(e.key)),true);
    else data=response([a,b,na,nb,shared,event],edges);
   }
   return route.fulfill({json:data});
  });
  await page.goto('http://127.0.0.1:5186/puppygraph');await ready();
  assert.equal(await page.locator('#graph canvas').count(),1,'Use the actual vis-network canvas renderer');
  assert.equal(await page.locator('.view-modes button').count(),2);
  await click(JSON.stringify(['type-group','NewsArticle']));assert.deepEqual(await records(),[]);assert.equal(calls.length,1);
  await click(JSON.stringify(['type-group','Equity']));assert.deepEqual(await records(),expected([a,b]));
  await click(a.key);assert.deepEqual(await records(),expected([a,b,na,shared]));assert.equal(calls.at(-1).identifier,a.id);
  assert((await page.locator('#properties').innerText()).includes('9007199254740993.01'));
  const actual=await page.evaluate(()=>[graphEdges.get('a').from,graphEdges.get('a').to,graphEdges.get('role').label]);assert.deepEqual(actual,[na.key,a.key,'buyer']);
  await click(na.key);assert((await records()).includes(event.key));
  await click(a.key);assert.deepEqual(await records(),expected([a,b]),'An orphaned expanded descendant must disappear');
  failB=true;await click(b.key);assert.deepEqual(await records(),expected([a,b]));assert((await page.locator('#notice').innerText()).includes('Branch unavailable'));
  failB=false;await click(b.key);assert.deepEqual(await records(),expected([a,b,nb,shared]));
  const before=calls.length;await click(a.key);assert.equal(calls.length,before,'Cached branches reopen without another query');
  assert.equal((await records()).filter(key=>key===shared.key).length,1);
  await page.getByRole('button',{name:'이 객체의 남은 연결 불러오기',exact:true}).click();await ready();
  assert.equal(calls.at(-1).identifier,a.id);assert.equal(calls.at(-1).cursor,'A-next');assert((await records()).includes(extra.key));
  await click(a.key);assert.deepEqual(await records(),expected([a,b,nb,shared]));
  await click(b.key);assert.deepEqual(await records(),expected([a,b]));
  await page.locator('#more').click();await ready();assert.deepEqual(await records(),expected([a,b]));
  await page.locator('#query').fill(a.id);await page.locator('#searchButton').click();await ready();await page.locator('#results .result').click();await ready();
  assert.deepEqual(await records(),expected([a]));
  const beforeRoot=calls.length;await click(a.key);assert.equal(calls.length,beforeRoot);assert.deepEqual(await records(),expected([a,na,shared]));
  await page.getByRole('button',{name:'이 객체의 남은 연결 불러오기',exact:true}).click();await ready();
  assert.equal(await page.evaluate(()=>state.cursor),'');assert(await page.locator('#more').isHidden(),'Root paging controls must share the same cursor and completion state');
  // Dragging and zooming are library interactions, not a synthetic DOM-only test.
  await page.waitForTimeout(500); // Let the documented 400ms camera animation finish before pointer coordinates are sampled.
  const from=await page.evaluate(key=>{network.stopSimulation();network.fit({animation:false});const p=network.canvasToDOM(network.getPosition(key)),r=document.querySelector('#graph').getBoundingClientRect();return {x:r.x+p.x,y:r.y+p.y,position:network.getPosition(key)};},a.key);
  await page.mouse.move(from.x,from.y);await page.mouse.down();await page.mouse.move(from.x+80,from.y+40,{steps:8});await page.mouse.up();
  const moved=await page.evaluate(key=>network.getPosition(key),a.key);assert(Math.hypot(moved.x-from.position.x,moved.y-from.position.y)>20,JSON.stringify({from,moved}));
  const scale=await page.evaluate(()=>network.getScale());await page.locator('#zoomIn').click();await page.waitForFunction(scale=>network.getScale()>scale,scale);
  fs.mkdirSync('output/puppygraph-instance-20261005',{recursive:true});await page.screenshot({path:'output/puppygraph-instance-20261005/fixture-instance.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.screenshot({path:'output/puppygraph-instance-20261005/fixture-mobile.png',fullPage:true});
  // The deliberately injected 503 is expected; all renderer/script errors are failures.
  assert.deepEqual(errors.filter(e=>!e.includes('503')),[]);
  console.log('Instance browser checks passed: guarded types, scoped queries/paging, shared rows, descendant collapse, failure/retry, exact values, canvas drag/zoom and mobile');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
