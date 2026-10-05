const {chromium}=require('../../edge/node_modules/@playwright/test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {spawn}=require('node:child_process');
(async()=>{
 const root=path.resolve('output/entity-workbench');
 const data=fs.mkdtempSync(path.join(root,'model-test-'));
 fs.linkSync(path.join(root,'snapshot.sqlite3'),path.join(data,'snapshot.sqlite3'));
 const server=spawn('.cache/news-filter-benchmark/Scripts/python.exe',['-X','utf8','-c',"import sys;from pathlib import Path;sys.path.insert(0,'apps/entity-workbench');from backend import server as workbench;workbench.DATA=Path(sys.argv[1]);workbench.ThreadingHTTPServer(('127.0.0.1',5187),workbench.Handler).serve_forever()",data],{windowsHide:true,stdio:'pipe'});
 let serverErrors='';server.stderr.on('data',d=>serverErrors+=d);
 const browser=await chromium.launch({headless:true});const page=await browser.newPage({viewport:{width:1680,height:1100}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 try{
  for(let n=0;n<30;n++){try{if((await fetch('http://127.0.0.1:5187/api/status')).ok)break;}catch{}await new Promise(r=>setTimeout(r,100));}
  await page.goto('http://127.0.0.1:5187/modeler');await page.waitForFunction(()=>document.querySelector('#saveState').textContent.includes('저장된 모델 없음'));
  assert(await page.locator('#emptyModel').isVisible());
  assert.equal(await page.locator('#saveModel,#addObject,#addRelation,#example').count(),0);
  const meta=await (await page.request.get('http://127.0.0.1:5187/api/meta')).json();
  const join=(from,table,target,id)=>({id,from,fk:meta.foreign_keys.findIndex(f=>f.table===table&&f.target_table===target),reverse:false});
  const model={objects:[{id:'Company',label:'저장된 회사 정의',table:'company_profile',key:'actor_id',note:'조회 테스트',joins:[join('base','company_profile','actor','j1'),join('j1','actor','entity','j2')],properties:[{id:'name',label:'회사명',source:'j2',column:'display_name'}]}],relations:[]};
  require('node:child_process').execFileSync('.cache/news-filter-benchmark/Scripts/python.exe',['-X','utf8','-c',"import sys,json,sqlite3;from pathlib import Path;sys.path.insert(0,'apps/entity-workbench');from backend.modeling import save_model;p=Path(sys.argv[1]);c=sqlite3.connect(p/'snapshot.sqlite3');m=json.loads(c.execute('select payload from _metadata').fetchone()[0]);c.close();save_model(p/'models.sqlite3',json.loads(sys.argv[2]),0,m)",data,JSON.stringify(model)]);
  await page.reload();await page.waitForSelector('[data-object="Company"]');
  assert.equal(await page.locator('#editor input,#editor select,#editor textarea').count(),0);
  assert.equal(JSON.parse(await page.locator('#definitionJson').textContent()).id,'Company');
  assert.equal(JSON.parse(await page.locator('#modelStoreJson').innerText()).revision,1);
  await page.locator('#previewSearch').fill('삼성전자');await page.locator('#previewButton').click();await page.waitForSelector('#objectJson');
  assert.equal(JSON.parse(await page.locator('#objectJson').innerText()).node.properties.name,'삼성전자');
  assert((await page.locator('#sourceRows').innerText()).includes('public.company_profile'));
  const status=await (await page.request.get('http://127.0.0.1:5187/api/status')).json();
  const denied=await page.request.post('http://127.0.0.1:5187/api/model',{headers:{'X-Workbench-Token':status.token},data:{model,revision:1}});assert.equal(denied.status(),405);
  const card=await page.locator('[data-object="Company"] .card-bg').boundingBox();
  await page.mouse.move(card.x+50,card.y+30);await page.mouse.down();await page.mouse.move(card.x+110,card.y+60,{steps:5});await page.mouse.up();
  const stored=await (await page.request.get('http://127.0.0.1:5187/api/model')).json();assert.deepEqual(stored.model,model);assert.equal(stored.revision,1);
  await page.screenshot({path:path.join(root,'modeler.png'),fullPage:true});
  await page.setViewportSize({width:850,height:1100});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  assert.deepEqual(errors,[]);assert.equal(serverErrors,'');console.log('Viewer passed: empty store, no edit controls, stored definition JSON, real object JSON, provenance, disabled writes, view-only drag, unchanged stored model, narrow layout.');
 }finally{
  await browser.close();server.kill();await new Promise(resolve=>{if(server.exitCode!==null)resolve();else server.once('exit',resolve);});
  // This uniquely created directory is within the test output root; never remove shared data.
  const relative=path.relative(root,path.resolve(data));if(relative.startsWith('model-test-')&&!relative.includes(path.sep))fs.rmSync(data,{recursive:true,force:true});
 }
})().catch(e=>{console.error(e);process.exitCode=1;});
