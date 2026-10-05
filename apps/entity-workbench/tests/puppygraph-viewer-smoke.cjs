const {chromium}=require('../../edge/node_modules/@playwright/test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
(async()=>{
 const browser=await chromium.launch({headless:true}),page=await browser.newPage({viewport:{width:1700,height:1080}});
 page.setDefaultTimeout(180000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const out='output/puppygraph-instance-20261005';fs.mkdirSync(out,{recursive:true});
 const ready=()=>page.waitForFunction(()=>typeof state!=='undefined'&&state.catalog&&!state.busy&&graphNodes.length>0);
 const click=async key=>{
  await page.waitForTimeout(500);
  const point=await page.evaluate(key=>{network.stopSimulation();network.fit({animation:false});const p=network.canvasToDOM(network.getPosition(key)),r=document.querySelector('#graph').getBoundingClientRect();return {x:r.x+p.x,y:r.y+p.y};},key);
  await page.mouse.click(point.x,point.y);await ready();
 };
 const records=()=>page.evaluate(()=>[...visibleNodes.values()].filter(n=>!n.group).map(n=>n.key));
 try{
  await page.goto('http://127.0.0.1:5186/puppygraph');await ready();
  assert.equal(await page.locator('.view-modes button').count(),2);assert.equal(await page.locator('#graph canvas').count(),1);
  assert.deepEqual(await records(),[]);
  const initial=await page.evaluate(()=>({types:visibleNodes.size,records:state.nodes.size,relations:state.edges.size}));
  await page.screenshot({path:out+'/all-types.png',fullPage:true});
  await click(JSON.stringify(['type-group','NewsArticle']));assert.deepEqual(await records(),[]);
  await click(JSON.stringify(['type-group','Equity']));
  const seeds=await records();assert(seeds.length>0);
  assert(await page.evaluate(()=>[...visibleNodes.values()].filter(n=>!n.group).every(n=>n.type==='Equity')));
  const security=await page.evaluate(()=>{const e=[...state.edges.values()].find(e=>e.type==='NewsArticle_MentionsSecurity_Equity');return state.nodes.get(e.target);});
  await click(security.key);
  const newsCount=await page.evaluate(key=>{
   const scope=state.scopes.get(key),news=[...visibleNodes.values()].filter(n=>!n.group&&n.type==='NewsArticle');
   if(!scope)throw new Error('Selected security did not get an independent query scope');
   for(const n of news)if(![...scope.edgeKeys].some(id=>{const e=state.edges.get(id);return (e.source===key&&e.target===n.key)||(e.target===key&&e.source===n.key);}))throw new Error('Unrelated news leaked into the expanded security');
   return news.length;
  },security.key);assert(newsCount>0);
  await page.screenshot({path:out+'/security-news.png',fullPage:true});
  await click(security.key);assert.deepEqual((await records()).sort(),seeds.sort());
  await page.locator('#query').fill('449450');await page.locator('#searchButton').click();await ready();await page.locator('#results .result').click();await ready();
  assert.equal(await page.locator('#oneMode').getAttribute('aria-pressed'),'true');assert.equal((await records()).length,1);
  const root=await page.evaluate(()=>state.root);await click(root.key);
  const holding=await page.evaluate(()=>[...visibleNodes.values()].find(n=>!n.group&&n.type==='ETFHolding'));assert(holding);
  await click(holding.key);assert((await page.locator('#properties').innerText()).includes('securityName'));assert((await page.locator('#properties').innerText()).includes('displayTitle'));
  const before=await page.evaluate(()=>state.scopes.get(state.root.key).edgeKeys.size);
  await page.locator('#more').click();await ready();const after=await page.evaluate(()=>state.scopes.get(state.root.key).edgeKeys.size);assert(after>before);
  await page.waitForTimeout(500);await page.locator('#fit').click();await page.waitForTimeout(500);
  await page.screenshot({path:out+'/etf-expanded.png',fullPage:true});
  const beforeFailure=await page.evaluate(()=>graphNodes.getIds().sort());
  await page.route('**/api/puppygraph/connections?**',route=>route.fulfill({status:503,json:{error:'Expected connection failure'}}));
  await page.locator('#allMode').click();await ready();assert.deepEqual(await page.evaluate(()=>graphNodes.getIds().sort()),beforeFailure);assert.equal(await page.locator('#oneMode').getAttribute('aria-pressed'),'true');
  assert((await page.locator('#notice').innerText()).includes('Expected connection failure'));
  await page.setViewportSize({width:390,height:844});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.screenshot({path:out+'/live-mobile.png',fullPage:true});assert.deepEqual(errors,[]);
  const result={passed:true,initial,security:security.label,newsCount,root:root.label,before,after,errors};fs.writeFileSync(out+'/verification.json',JSON.stringify(result,null,2));console.log('Live instance exploration passed',result);
 }catch(error){console.error('Dashboard:',await page.locator('#notice').innerText().catch(()=>''),'Errors:',errors);await page.screenshot({path:out+'/failure.png',fullPage:true}).catch(()=>{});throw error;}
 finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
