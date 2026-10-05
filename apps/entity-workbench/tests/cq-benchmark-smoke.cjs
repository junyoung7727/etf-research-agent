const {chromium}=require('../../edge/node_modules/@playwright/test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
(async()=>{
 const browser=await chromium.launch({headless:true});
 const page=await browser.newPage({viewport:{width:1500,height:1050}});const errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 try{
  await page.goto('http://127.0.0.1:5186/benchmark');
  await page.waitForSelector('.run');
  const buttons=page.locator('.run');
  const pilot=buttons.filter({hasText:'CQ07-pilot'});await pilot.click();
  assert.match(await page.locator('#detail').innerText(),/개선 필요/);
  assert.match(await page.locator('.answer').innerText(),/PLUS K방산/);
  assert.match(await page.locator('#metrics').innerText(),/미측정/);
  await page.locator('#capabilities summary').click();
  assert.match(await page.locator('#capabilities').innerText(),/resolve_securities/);
  assert.equal(await page.locator('.latest-cases button').count(),13);
  await page.locator('#detail details summary').click();
  await page.locator('.claim button').first().click();
  await page.waitForFunction(()=>document.querySelector('#evidenceBody').textContent.includes('tool_run_id'));
  assert.equal(await page.locator('dialog').evaluate(n=>n.open),true);
  await page.locator('#closeEvidence').click();
  fs.mkdirSync('output/cq-tools-benchmark-20261005',{recursive:true});
  await page.screenshot({path:'output/cq-tools-benchmark-20261005/dashboard-desktop.png',fullPage:false});
  await page.setViewportSize({width:390,height:844});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  await page.screenshot({path:'output/cq-tools-benchmark-20261005/dashboard-mobile.png',fullPage:false});
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({passed:true,realAnswerVisible:true,evidenceVisible:true,unmeasuredCoverageHonest:true,browserErrors:errors}));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
