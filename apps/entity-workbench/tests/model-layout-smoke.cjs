const {chromium}=require('../../edge/node_modules/@playwright/test');
const assert=require('node:assert/strict');
const fs=require('node:fs');

(async()=>{
 const browser=await chromium.launch({headless:true});
 const page=await browser.newPage({viewport:{width:1680,height:1120}});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const ready=()=>page.waitForFunction(()=>document.querySelector('#modelCanvas')?.getAttribute('aria-busy')==='false');
 const geometry=()=>page.evaluate(()=>{
  const rect=r=>({x:r.x,y:r.y,width:r.width,height:r.height});
  return {
   nodes:[...document.querySelectorAll('[data-object]')].map(g=>{const t=g.transform.baseVal.getItem(0).matrix,b=g.querySelector('rect').getBBox();return {id:g.dataset.object,x:t.e,y:t.f,width:b.width,height:b.height};}),
   edges:[...document.querySelectorAll('[data-relation]')].map(g=>{const values=g.querySelector('.model-link').getAttribute('d').match(/-?\d+(?:\.\d+)?(?:e[+-]?\d+)?/gi).map(Number);return {id:g.dataset.relation,points:Array.from({length:values.length/2},(_,i)=>({x:values[i*2],y:values[i*2+1]})),label:rect(g.querySelector('.link-label-bg').getBBox()),text:rect(g.querySelector('.link-label').getBBox())};}),
  };
 });
 function verify(view,relations){
  assert.deepEqual(view.edges.map(e=>e.id).sort(),relations.map(e=>e.id).sort(),'Every relationship in the scope must be drawn');
  const overlaps=(a,b)=>a.x<b.x+b.width&&a.x+a.width>b.x&&a.y<b.y+b.height&&a.y+a.height>b.y;
  for(const n of view.nodes)for(const other of view.nodes)if(n.id!==other.id)assert(!overlaps(n,other),`${n.id} covers ${other.id}`);
  for(const e of view.edges){
   const r=relations.find(r=>r.id===e.id);
   for(const [id,p] of [[r.source,e.points[0]],[r.target,e.points.at(-1)]]){
    const n=view.nodes.find(n=>n.id===id);assert(n&&p.x>=n.x-1&&p.x<=n.x+n.width+1&&p.y>=n.y-1&&p.y<=n.y+n.height+1,`${e.id} wrong arrow direction/endpoint`);
   }
   for(let i=1;i<e.points.length;i++){
    const a=e.points[i-1],b=e.points[i];assert(a.x===b.x||a.y===b.y);
    const segment={x:Math.min(a.x,b.x),y:Math.min(a.y,b.y),width:Math.abs(b.x-a.x),height:Math.abs(b.y-a.y)};
    for(const n of view.nodes)assert(!overlaps(segment,{x:n.x+1,y:n.y+1,width:n.width-2,height:n.height-2}),`${e.id} crosses ${n.id}`);
   }
   for(const n of view.nodes)assert(!overlaps(e.label,n),`${e.id} label covers ${n.id}`);
   for(const other of view.edges)if(other.id!==e.id)assert(!overlaps(e.label,other.label),`${e.id} label overlaps ${other.id}`);
   // The engine must reserve the actual browser font dimensions, including long labels.
   if(e.text.width)assert(e.text.x>=e.label.x-1&&e.text.x+e.text.width<=e.label.x+e.label.width+1,`${e.id} text exceeds reserved space`);
  }
  const segments=view.edges.flatMap(e=>e.points.slice(1).map((p,i)=>({id:e.id,a:e.points[i],b:p})));
  for(let i=0;i<segments.length;i++)for(let j=i+1;j<segments.length;j++){
   const a=segments[i],b=segments[j];if(a.id===b.id)continue;
   const horizontal=a.a.y===a.b.y;if(horizontal!==(b.a.y===b.b.y))continue;
   const axis=horizontal?'x':'y',fixed=horizontal?'y':'x';if(a.a[fixed]!==b.a[fixed])continue;
   const overlap=Math.min(Math.max(a.a[axis],a.b[axis]),Math.max(b.a[axis],b.b[axis]))-Math.max(Math.min(a.a[axis],a.b[axis]),Math.min(b.a[axis],b.b[axis]));
   assert(overlap<=.1,`${a.id} and ${b.id} share a line segment, making the relation ambiguous`);
  }
 }
 try{
  await page.goto('http://127.0.0.1:5186/modeler');await ready();
  const before=await (await page.request.get('http://127.0.0.1:5186/api/model')).json();
  await page.locator('#fitModel').click();await ready();
  const full=await geometry();verify(full,before.model.relations);assert.equal(full.nodes.length,before.model.objects.length);
  assert(await page.evaluate(()=>[...document.querySelectorAll('[data-object]')].every(g=>{const t=g.querySelector('.title').getBBox(),b=g.querySelector('.card-bg').getBBox();return t.x>=0&&t.x+t.width<=b.width;})),'Long object type names must remain inside their cards');
  await page.locator('.model-panel').screenshot({path:'output/entity-workbench/layout-overview.png'});
  await page.locator('[data-object="Company"]').dblclick();await ready();
  const companyLinks=before.model.relations.filter(r=>r.source==='Company'||r.target==='Company');
  assert((await page.locator('#graphScope').textContent()).includes('Company 직접 연결'),'Double-click should isolate the direct connections');
  verify(await geometry(),companyLinks);
  assert(parseInt(await page.locator('#modelZoom').textContent())>=55,'Connection focus must remain readable');
  await page.locator('.model-panel').screenshot({path:'output/entity-workbench/layout-company.png'});
  await page.locator('[data-relation="Company_Issues_Equity"] .link-caption').click();
  assert.equal(JSON.parse(await page.locator('#definitionJson').textContent()).type,'Issues','Relation labels must still open their definition');
  // Selecting a neighbor inspects it without unexpectedly replacing the focus scope.
  await page.locator('[data-object="Disclosure"]').click();
  assert((await page.locator('#graphScope').textContent()).includes('Company 직접 연결'));
  assert.equal(JSON.parse(await page.locator('#definitionJson').textContent()).id,'Disclosure');
  const card=await page.locator('[data-object="Company"] .card-bg').boundingBox();
  await page.mouse.move(card.x+30,card.y+30);await page.mouse.down();await page.mouse.move(card.x+80,card.y+100,{steps:5});await page.mouse.up();await ready();
  verify(await geometry(),companyLinks);
  await page.locator('#objectJump').selectOption('NewsArticle');await ready();
  verify(await geometry(),before.model.relations.filter(r=>r.source==='NewsArticle'||r.target==='NewsArticle'));
  assert((await page.locator('#graphScope').textContent()).includes('NewsArticle 직접 연결'));
  await page.locator('#fitModel').click();await ready();verify(await geometry(),before.model.relations);
  await page.locator('#autoLayout').click();await ready();assert.deepEqual(await geometry(),full,'Re-layout should be stable');
  // All arrows, including self loops, must fit inside the canvas along with their labels.
  assert(await page.evaluate(()=>{const a=document.querySelector('#modelCanvas').getBoundingClientRect(),b=document.querySelector('#modelScene').getBoundingClientRect();return b.left>=a.left&&b.right<=a.right&&b.top>=a.top&&b.bottom<=a.bottom;}));
  await page.setViewportSize({width:850,height:1100});await page.locator('#fitModel').click();await ready();
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.locator('#objectJump').selectOption('Company');await ready();
  verify(await geometry(),companyLinks);
  await page.locator('.model-panel').screenshot({path:'output/entity-workbench/layout-narrow.png'});
  // Middle-button panning and wheel zoom remain available after layout/focus.
  const canvas=await page.locator('#modelCanvas').boundingBox(),oldTransform=await page.locator('#modelScene').getAttribute('transform');
  await page.mouse.move(canvas.x+canvas.width/2,canvas.y+40);await page.mouse.down({button:'middle'});await page.mouse.move(canvas.x+canvas.width/2+80,canvas.y+80);await page.mouse.up({button:'middle'});
  assert.notEqual(await page.locator('#modelScene').getAttribute('transform'),oldTransform);
  const zoom=await page.locator('#modelZoom').textContent();await page.mouse.wheel(0,-100);await page.waitForFunction(old=>document.querySelector('#modelZoom').textContent!==old,zoom);
  const after=await (await page.request.get('http://127.0.0.1:5186/api/model')).json();assert.equal(after.revision,before.revision);assert.deepEqual(after.model,before.model);
  assert.deepEqual(errors,[]);
  const result={revision:after.revision,types:full.nodes.length,links:full.edges.length,cardOverlaps:0,cardIntersections:0,labelOverlaps:0,sharedLineSegments:0,checks:['all relation directions preserved','native double-click focus','single-click inspection','relation label opens definition','drag rerouting','self loops','stable auto layout','full graph restore','fit includes labels and loops','narrow view','middle-button pan','wheel zoom','stored model unchanged'],pageErrors:errors};
  fs.writeFileSync('output/entity-workbench/layout-verification.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
