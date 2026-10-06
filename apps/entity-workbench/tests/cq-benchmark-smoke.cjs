const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'../../edge/node_modules/@playwright/test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const base=process.env.BENCHMARK_URL||'http://127.0.0.1:5186';
(async()=>{
 const browser=await chromium.launch({headless:true}),page=await browser.newPage({viewport:{width:1500,height:1050}});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 try{
  const response=await page.request.get(base+'/api/cq-benchmark'),catalog=await response.json();
  const latest=catalog.latest_cases.find(r=>r.case==='CQ05'),run=latest.run_id;
  await page.goto(base+'/benchmark?run_id='+run);
  await page.waitForSelector('#runSelect');
  assert.equal(await page.locator('.run').count(),13);
  assert.equal(await page.locator('#runSelect').inputValue(),run);
  assert.match(await page.locator('#detail').innerText(),/계산 재현 제외/);
  assert.match(await page.locator('#detail').innerText(),/01 코드 검사/);
  assert.match(await page.locator('#detail').innerText(),/03 종료조건/);
  assert.match(await page.locator('#detail').innerText(),/참조 호출/);
  assert.match(await page.locator('#detail').innerText(),/미설정/);
  await page.locator('.primary-link').click();
  await page.waitForSelector('.answer');
  assert.match(page.url(),new RegExp('/benchmark/analysis\\?run_id='+run));
  assert.match(await page.locator('.answer').innerText(),/PLUS K방산/);
  await page.locator('#tab-tools').click();
  await page.locator('.tool-row button').first().click();
  await page.waitForFunction(()=>document.querySelector('#evidenceBody').textContent.includes('tool_run_id'));
  assert.ok(await page.locator('#evidenceBody .json-key').count()>0);
  await page.locator('#closeEvidence').click();
  await page.locator('#tab-trace').click();
  await page.waitForSelector('.trace-event');
  await page.locator('.trace-event summary').first().click();
  await page.waitForFunction(()=>document.querySelector('.trace-event pre').textContent.length>0);
  assert.ok(await page.locator('#moreTrace').count()>0);
  await page.locator('#backBenchmark').click();
  await page.waitForSelector('#runSelect');
  assert.equal(await page.locator('#runSelect').inputValue(),run);
  await page.reload();await page.waitForSelector('#runSelect');
  assert.equal(await page.locator('#runSelect').inputValue(),run);
  fs.mkdirSync('output/cq-evaluation-dashboard',{recursive:true});
  await page.screenshot({path:'output/cq-evaluation-dashboard/desktop.png'});
  await page.setViewportSize({width:390,height:844});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  await page.screenshot({path:'output/cq-evaluation-dashboard/mobile.png'});
  await page.locator('.primary-link').click();await page.waitForSelector('.answer');
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  const invalid=await page.request.get(base+'/api/cq-benchmark/detail?run_id=..%2Fescape');
  assert.equal(invalid.status(),400);
  // Exercise the failure presentation independently of a stochastic judge's current verdict.
  await page.route('**/api/cq-benchmark/detail?*',async route=>{
    const response=await route.fetch(),value=await response.json();
    value.evaluation.overall='fail';
    const check=value.evaluation.agent_checks[0];
    Object.assign(check,{status:'fail',reason:'시험: 답변 기간과 근거 기간이 다릅니다.',
      answer_span:'시험용 문제 문장',evidence_ids:[value.tools[0].tool_run_id]});
    await route.fulfill({response,json:value});
  });
  await page.goto(base+'/benchmark?run_id='+run);await page.waitForSelector('.check.fail');
  assert.match(await page.locator('.check.fail').innerText(),/시험용 문제 문장/);
  await page.locator('.check.fail .evidence-button').click();
  await page.waitForFunction(()=>document.querySelector('#evidenceBody').textContent.includes('tool_run_id'));
  await page.locator('#closeEvidence').click();
  await page.unroute('**/api/cq-benchmark/detail?*');
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({passed:true,cqs:13,sameRunRoundTrip:true,trace:true,evidenceJsonColors:true,failureEvidence:true,mobile:true,errors}));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
