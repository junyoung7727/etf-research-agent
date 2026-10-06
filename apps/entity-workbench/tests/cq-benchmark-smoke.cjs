const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'../../edge/node_modules/@playwright/test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const base=process.env.BENCHMARK_URL||'http://127.0.0.1:5188';
(async()=>{
 const browser=await chromium.launch({headless:true}),page=await browser.newPage({viewport:{width:1500,height:1050}});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 try{
  const response=await page.request.get(base+'/api/cq-benchmark'),catalog=await response.json();
  assert.match(catalog.cases.find(c=>c.id==='CQ01').scenario_question,/PLUS K방산과 KODEX 방산/);
  const latest=catalog.latest_cases.find(r=>r.case==='CQ05'),run=latest.run_id;
  await page.goto(base+'/benchmark?run_id='+run);
  await page.waitForSelector('#runSelect');
  await page.waitForSelector('.trend-version');
  const trendResponse=await page.request.get(base+'/api/cq-benchmark/trend'),trend=await trendResponse.json();
  assert.deepEqual(trend.points.map(p=>p.release),trend.points.map(p=>p.release).sort((a,b)=>a-b));
  assert.equal(await page.locator('.trend-version').count(),trend.points.length);
  assert.equal(trend.points.some(p=>p.id==='unversioned'),false);
  for(const point of trend.points){
    assert.equal(point.total.pass,point.common.pass+point.cq.pass);
    assert.equal(point.total.total,52);
  }
  assert.equal(await page.locator('.run').count(),13);
  assert.equal(await page.locator('#runSelect').inputValue(),run);
  assert.equal(await page.locator('#matrixTable tbody tr').count(),13);
  assert.equal(await page.locator('#versionSelect').inputValue(),'unversioned');
  const unrun=catalog.agent_versions.find(v=>v.run_count===0);
  assert.ok(unrun);
  await page.locator('#versionSelect').selectOption(unrun.id);
  await page.waitForFunction(()=>document.querySelector('#detail').textContent.includes('이 버전의 CQ 실행이 없습니다.'));
  assert.equal(await page.locator('#matrixTable tbody tr').count(),13);
  assert.equal(await page.locator('#matrixTable .matrix-cq:is(button)').count(),0);
  await page.reload();await page.waitForSelector('#matrixTable tbody tr');
  assert.equal(await page.locator('#versionSelect').inputValue(),unrun.id);
  await page.locator('#versionSelect').selectOption('unversioned');
  await page.waitForSelector('#runSelect');
  await page.locator('#matrixTable .matrix-cq').filter({hasText:'CQ05'}).click();
  await page.waitForFunction(id=>document.querySelector('#runSelect')?.value===id,run);
  assert.match(await page.locator('#detail').innerText(),/계산 재현 제외/);
  assert.match(await page.locator('#criteriaOverview').innerText(),/공통 기준/);
  assert.match(await page.locator('#criteriaOverview').innerText(),/CQ별 기준/);
  assert.doesNotMatch(await page.locator('#criteriaOverview').innerText(),/출력 구조·필수 답변/);
  const detailResponse=await page.request.get(base+'/api/cq-benchmark/detail?run_id='+run);
  const evaluated=(await detailResponse.json()).evaluation;
  assert.equal(evaluated.agent_checks.length,4);
  assert.deepEqual(await page.locator('#criteriaOverview thead tr:last-child th').allTextContents(),['사실 정확성','결론 타당성','조사 완결성','요구 충족']);
  assert.equal(await page.locator('#criteriaOverview tbody td').count(),4);
  assert.equal(await page.locator('#technicalChecks .check').count(),evaluated.code_checks.length);
  assert.equal(await page.locator('.status-chip').count(),0);
  assert.equal(await page.locator('#criteriaOverview').evaluate(n=>Boolean(n.compareDocumentPosition(document.querySelector('#runSelect'))&Node.DOCUMENT_POSITION_FOLLOWING)),true);
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
    for(const check of value.evaluation.agent_checks)check.status='pass';
    value.evaluation.agent_checks[1].status='unknown';
    const check=value.evaluation.agent_checks[0];
    Object.assign(check,{status:'fail',reason:'시험: 답변 기간과 근거 기간이 다릅니다.',
      answer_span:'시험용 문제 문장',evidence_ids:[value.tools[0].tool_run_id]});
    await route.fulfill({response,json:value});
  });
  await page.goto(base+'/benchmark?run_id='+run);await page.waitForSelector('.check.fail');
  assert.match(await page.locator('.check.fail').innerText(),/시험용 문제 문장/);
  assert.match(await page.locator('.verdict-link.fail').innerText(),/실패/);
  assert.equal(await page.locator('#qualityDetails .check.fail').evaluate(n=>n.open),true);
  assert.equal(await page.locator('#qualityDetails .check.unknown').evaluate(n=>n.open),true);
  assert.equal(await page.locator('#qualityDetails .check.pass').first().evaluate(n=>n.open),false);
  await page.locator('.verdict-link.pass').first().click();
  assert.equal(await page.locator('#qualityDetails .check.pass').first().evaluate(n=>n.open),true);
  await page.locator('.verdict-link.fail').click();
  assert.equal(await page.locator('.check.fail').evaluate(n=>document.activeElement===n),true);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  await page.locator('.check.fail .evidence-button').click();
  await page.waitForFunction(()=>document.querySelector('#evidenceBody').textContent.includes('tool_run_id'));
  await page.locator('#closeEvidence').click();
  await page.unroute('**/api/cq-benchmark/detail?*');
  // Display sample counts without saving synthetic evaluations to real runs.
  const sample=JSON.parse(JSON.stringify(trend));
  assert.ok(sample.points.length>=3);
  for(const [index,point] of sample.points.entries()){
    for(const group of ['common','cq','total'])point[group].plotted_pass=null;
    if(index!==0&&index!==sample.points.length-1)continue;
    point.executed_cqs=2;
    for(const [group,passed] of [['common',index===0?2:3],['cq',index===0?1:2],['total',index===0?3:5]]){
      Object.assign(point[group],{pass:passed,fail:0,unknown:0,not_run:0,not_evaluated:point[group].total-passed,plotted_pass:passed});
    }
  }
  await page.route('**/api/cq-benchmark/trend',route=>route.fulfill({json:sample}));
  await page.goto(base+'/benchmark?run_id='+run);await page.waitForSelector('#trendChart circle');
  assert.deepEqual(await page.locator('#trendChart circle[data-series=total]').evaluateAll(nodes=>nodes.map(n=>n.getAttribute('data-value'))),['3','5']);
  assert.equal(await page.locator('#trendChart polyline').count(),0); // No invented interpolation across missing evaluations.
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  await page.locator('.trend-version').last().click();
  await page.waitForFunction(id=>document.querySelector('#versionSelect').value===id,sample.points.at(-1).id);
  assert.equal(await page.locator('.trend-version').last().getAttribute('aria-pressed'),'true');
  await page.unroute('**/api/cq-benchmark/trend');
  const oldRun=catalog.latest_cases.find(r=>r.case==='CQ01').run_id;
  await page.goto(base+'/benchmark?run_id='+oldRun);await page.waitForSelector('#runSelect');
  assert.match(await page.locator('#currentQuestion').innerText(),/KODEX 방산/);
  assert.match(await page.locator('#scenarioNotice').innerText(),/수정 전 질문/);
  await page.getByText('이 실행의 실제 입력 질문',{exact:true}).click();
  assert.match(await page.locator('#detail .question').last().innerText(),/TIGER K방산&우주/);
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({passed:true,cqs:13,sameRunRoundTrip:true,trace:true,evidenceJsonColors:true,failureEvidence:true,mobile:true,errors}));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
