const {chromium}=require('../../edge/node_modules/@playwright/test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const node=(type,id)=>({key:JSON.stringify([type,id]),type,id,label:id,properties:{amount:'9007199254740993.01'}});
const [a,b,c,d]=[node('Company','A'),node('Company','B'),node('SourceEvent','C'),node('Company','D')];
const edge=(id,source,target,role='')=>({key:id,type:source.type+'_ParticipatesIn_'+target.type,source:source.key,target:target.key,identity:[id],properties:{roleCode:role}});
const edges=[edge('a-c',a,c,'supplier'),edge('b-c',b,c,'supplier'),edge('a-c-buyer',a,c,'buyer'),edge('c-a',c,a),edge('a-b',a,b)];
const response=(nodes,edges,complete=false)=>({nodes,edges,complete,cursor:complete?'':'next',remainingRelations:1,checkedAt:new Date().toISOString()});
(async()=>{
 const browser=await chromium.launch({headless:true});
 const page=await browser.newPage({viewport:{width:1500,height:1000}});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 let calls=0;
 const ready=()=>page.waitForFunction(()=>document.querySelector('#graph').getAttribute('aria-busy')==='false'&&document.querySelector('.node'));
 const toggle=async type=>{const n=page.locator(`.type-node[data-type="${type}"]`);await n.focus();await n.press('Enter');};
 // Every loaded relationship must remain reachable exactly once, with its original identity.
 const preserved=async expected=>{
  const keys=await page.evaluate(()=>[...visibleEdges.values()].filter(e=>!e.membership).flatMap(e=>e.summary?e.originalKeys:[e.key]).sort());
  assert.deepEqual(keys,[...expected].sort());
 };
 try{
  await page.route('**/api/puppygraph/**',route=>{
   const url=new URL(route.request().url());let data;
   if(url.pathname.endsWith('/catalog'))data={objects:[{id:'Company',properties:[]},{id:'SourceEvent',properties:[]}],relations:[]};
   else if(url.pathname.endsWith('/search'))data={nodes:[a],checkedAt:new Date().toISOString()};
   else{calls++;data=url.searchParams.get('cursor')?response([d],[edge('d-c',d,c,'supplier')],true):response([a,b,c],edges);}
   return route.fulfill({json:data});
  });
  await page.goto('http://127.0.0.1:5186/puppygraph');await ready();
  assert.equal(await page.locator('.type-node').count(),2);
  assert.equal(await page.locator('.record-node').count(),0);
  await preserved(edges.map(e=>e.key));
  assert.equal(await page.locator('.summary-edge').count(),4,'Roles, direction and same-type relations must not merge together');
  await page.locator('.summary-edge').first().press('Enter');
  await page.locator('#properties .result').first().click();
  assert((await page.locator('#properties').innerText()).includes('supplier'));
  await page.locator('.type-node[data-type="Company"] .node-circle').click();
  assert.equal(await page.locator('.record-node').count(),2);
  assert.equal(await page.locator('.membership').count(),2);
  await preserved(edges.map(e=>e.key));
  await toggle('SourceEvent');
  assert.equal(await page.locator('.summary-edge').count(),0);
  await page.locator('.record-node[data-type="Company"]').first().press('Enter');
  assert((await page.locator('#properties').innerText()).includes('9007199254740993.01'));
  await toggle('Company');await toggle('Company');
  assert.equal(calls,1,'Folding is local and must not query or change scope');
  await page.locator('#more').click();await ready();
  assert.equal(await page.locator('.record-node[data-type="Company"]').count(),3,'Paging preserves expanded types');
  await preserved([...edges.map(e=>e.key),'d-c']);
  await page.locator('#query').fill('A');await page.locator('#searchButton').click();await ready();
  await page.locator('.result').click();await ready();
  assert.equal(await page.locator('.record-node').count(),1,'The selected center remains visible even when its type is folded');
  assert.equal(await page.locator('.record-node').getAttribute('data-key'),a.key);
  const root=page.locator('.record-node'),from=await root.locator('circle.node-circle').boundingBox(),to=await page.locator('.type-node[data-type="SourceEvent"] circle.node-circle').boundingBox();
  await page.mouse.move(from.x+from.width/2,from.y+from.height/2);await page.mouse.down();await page.mouse.move(to.x+to.width/2,to.y+to.height/2,{steps:5});await page.mouse.up();
  await root.locator('circle.node-circle').click({timeout:3000});
  assert.equal(await page.locator('#detail h2').innerText(),'A','A dragged record must remain clickable above overlapping type nodes');
  await toggle('Company');await toggle('Company');
  assert.equal(await page.locator('.record-node').count(),1);
  await preserved(edges.map(e=>e.key));
  await page.setViewportSize({width:390,height:844});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  assert.deepEqual(errors,[]);
  fs.mkdirSync('output/puppygraph-groups-20261005',{recursive:true});
  await page.screenshot({path:'output/puppygraph-groups-20261005/fixture-mobile.png',fullPage:true});
  console.log('Type grouping passed: identities, roles, direction, raw properties, fold/unfold, paging, center and mobile');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
