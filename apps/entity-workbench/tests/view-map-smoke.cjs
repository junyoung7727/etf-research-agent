const {chromium}=require('../../edge/node_modules/@playwright/test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
(async()=>{
 const browser=await chromium.launch({headless:true});
 const page=await browser.newPage({viewport:{width:1600,height:1100}});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 try{
  await page.goto('http://127.0.0.1:5186/view-design');
  await page.waitForSelector('[data-map-object]');
  await page.selectOption('#mapFocus','');
  await page.waitForFunction(()=>document.querySelector('#mapStatus').textContent.startsWith('전체 구조'));
  assert.equal(await page.locator('[data-map-object]').count(),23);
  assert.equal(await page.locator('[data-map-relation]').count(),37);
  assert.equal(await page.locator('[data-map-table]').count(),60);
  assert.equal(await page.locator('[data-map-fk]').count(),74);
  assert.equal(await page.locator('.map-edge.blocked').count(),2);
  const aspect=await page.locator('#mapScene').evaluate(el=>{const b=el.getBBox();return b.width/b.height;});
  assert(aspect>=1.2&&aspect<=3,'전체 ERD가 한 줄이나 세로 띠로 늘어지지 않아야 한다: '+aspect);
  const data=await (await page.request.get('http://127.0.0.1:5186/api/view-design')).json();
  const erd=await page.evaluate(()=>[...document.querySelectorAll('[data-map-table]')].map(t=>({id:t.dataset.mapTable,columns:[...t.querySelectorAll('[data-erd-column]')].map(c=>({name:c.dataset.erdColumn,key:c.dataset.key}))})));
  for(const table of [...data.objects,...data.relations]){
   const actual=erd.find(t=>t.id===table.id);
   assert.deepEqual(actual.columns.map(c=>c.name),table.columns.map(c=>c.column));
   const relational=data.relations.some(r=>r.id===table.id);
   assert.deepEqual(actual.columns.filter(c=>c.key==='PK').map(c=>c.name),[relational?'edge_id':'id']);
   assert.deepEqual(actual.columns.filter(c=>c.key==='FK').map(c=>c.name),relational?['source_id','target_id']:[]);
  }
  // Legibility: no overlapping table cards, diagonal segments, or lines through cards.
  const geometry=await page.evaluate(()=>{
   const cards=[...document.querySelectorAll('[data-map-table]')].map(el=>{
    const m=el.transform.baseVal[0].matrix,b=el.querySelector('rect');
    return {id:el.dataset.mapTable,x:m.e,y:m.f,w:+b.getAttribute('width'),h:+b.getAttribute('height')};
   });
   const problems=[];
   for(let i=0;i<cards.length;i++)for(let j=i+1;j<cards.length;j++){
    const a=cards[i],b=cards[j];if(a.x<b.x+b.w&&a.x+a.w>b.x&&a.y<b.y+b.h&&a.y+a.h>b.y)problems.push('card overlap');
   }
   for(const edge of document.querySelectorAll('[data-map-fk]')){
    const points=edge.querySelector('.map-edge-line').getAttribute('d').match(/[ML][^ML]+/g).map(s=>s.slice(1).split(' ').map(Number));
    for(let i=1;i<points.length;i++){
     const [x1,y1]=points[i-1],[x2,y2]=points[i];
     if(x1!==x2&&y1!==y2)problems.push('diagonal route');
     for(const c of cards){
      const horizontal=y1===y2&&y1>c.y+.1&&y1<c.y+c.h-.1&&Math.max(x1,x2)>c.x+.1&&Math.min(x1,x2)<c.x+c.w-.1;
      const vertical=x1===x2&&x1>c.x+.1&&x1<c.x+c.w-.1&&Math.max(y1,y2)>c.y+.1&&Math.min(y1,y2)<c.y+c.h-.1;
      if(horizontal||vertical)problems.push(edge.dataset.mapFk+' intersects '+c.id);
     }
    }
   }
   return problems;
  });
  assert.deepEqual(geometry,[]);
  await page.locator('.view-map').screenshot({path:'output/view-design-20261005/table-map-all.png'});
  // Verify each line starts at its FK row and ends at the referenced object's PK row.
  const endpoints=await page.evaluate(data=>{
   const failures=[];
   for(const r of data.relations)for(const [column,target] of [['source_id',r.source],['target_id',r.target]]){
    const edge=document.querySelector(`[data-map-fk="${r.id}:${column}"]`);
    const points=edge.querySelector('.map-edge-line').getAttribute('d').match(/[ML][^ML]+/g).map(s=>s.slice(1).split(' ').map(Number));
    const from=document.querySelector(`[data-map-table="${r.id}"]`),to=document.querySelector(`[data-map-table="${target}"]`);
    function point(t,col,right){const m=t.transform.baseVal[0].matrix,b=t.querySelector(`[data-erd-column="${col}"] rect`);return [m.e+(right?+t.querySelector('.map-card-bg').getAttribute('width'):0),m.f+(+b.getAttribute('y'))+(+b.getAttribute('height'))/2];}
    const expectedFrom=point(from,column,true),expectedTo=point(to,'id',false);
    if(points[0].some((v,i)=>Math.abs(v-expectedFrom[i])>.01)||points.at(-1).some((v,i)=>Math.abs(v-expectedTo[i])>.01))failures.push({id:r.id+':'+column,actual:[points[0],points.at(-1)],expected:[expectedFrom,expectedTo]});
   }
   return failures;
  },data);
  assert.deepEqual(endpoints,[]);
  const expected=data.relations.filter(r=>r.source==='ETFHolding'||r.target==='ETFHolding');
  await page.selectOption('#mapFocus','ETFHolding');
  await page.waitForFunction(()=>document.querySelector('#mapStatus').textContent.startsWith('ETFHolding 직접 연결'));
  assert.equal(await page.locator('[data-map-relation]').count(),expected.length);
  assert.equal(await page.locator('[data-map-object]').count(),new Set(['ETFHolding',...expected.flatMap(r=>[r.source,r.target])]).size);
  const holdingAspect=await page.locator('#mapScene').evaluate(el=>{const b=el.getBBox();return b.width/b.height;});
  assert(holdingAspect>=1.2&&holdingAspect<=3,'보유 구성종목 ERD도 가로 공간을 사용해야 한다: '+holdingAspect);
  await page.locator('[data-map-object="ETFHolding"]').focus();
  await page.keyboard.press('Enter');
  assert.equal(await page.locator('#viewName').innerText(),'ontology_view.etf_holding');
  const rel=expected[0];
  await page.locator(`[data-map-relation="${rel.id}"]`).focus();await page.keyboard.press('Enter');
  assert.equal(await page.locator('#viewName').innerText(),rel.viewName);
  const before=await page.locator('#mapZoom').innerText();await page.click('#mapPlus');
  assert.notEqual(await page.locator('#mapZoom').innerText(),before);await page.click('#mapFit');
  await page.locator('.view-map').screenshot({path:'output/view-design-20261005/table-map-holdings.png'});
  await page.setViewportSize({width:390,height:844});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  assert.deepEqual(errors,[]);
  fs.writeFileSync('output/view-design-20261005/map-verification.json',JSON.stringify({passed:true,objects:23,relationTables:37,fkReferences:74,geometryProblems:geometry,endpointProblems:endpoints,pageErrors:errors,checks:['all columns in table rows','PK and FK roles','exact FK to PK row endpoints','orthogonal routes','no card overlap or route intrusion','blocked relation','direct connections','object and relation detail navigation','keyboard selection','zoom and fit','mobile width']},null,2));
  console.log('view map checks passed');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
