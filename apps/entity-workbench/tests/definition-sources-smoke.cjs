const {chromium, expect} = require('../../edge/node_modules/@playwright/test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawn} = require('node:child_process');

(async () => {
  const root = path.resolve(__dirname, '../../..');
  const app = path.join(root, 'apps/entity-workbench');
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'orca-definition-sources-'));
  const library = path.join(temp, 'library');
  const configured = process.env.EDGE_ONTOLOGY_ROOT || JSON.parse(fs.readFileSync(path.join(app, 'data/library.json'))).libraryRoot;
  fs.cpSync(configured, library, {recursive:true});
  fs.cpSync(path.join(app,'ontology/metadata'), path.join(temp,'drafts'), {recursive:true});
  fs.mkdirSync(path.join(temp,'data'));
  fs.copyFileSync(path.join(root,'output/entity-workbench/snapshot.sqlite3'), path.join(temp,'data/snapshot.sqlite3'));
  const source = "import sys,threading;from pathlib import Path;sys.path.insert(0,'apps/entity-workbench');from backend import server as s;s.DATA=Path(sys.argv[1])/'data';s.METADATA=Path(sys.argv[1])/'drafts';http=s.ThreadingHTTPServer(('127.0.0.1',0),s.Handler);threading.Thread(target=http.serve_forever,daemon=True).start();print(http.server_port,flush=True);sys.stdin.readline();http.shutdown();http.server_close()";
  const server = spawn(path.join(root,'.cache/news-filter-benchmark/Scripts/python.exe'), ['-X','utf8','-c',source,temp],
    {cwd:root, env:{...process.env,EDGE_ONTOLOGY_ROOT:library}, windowsHide:true, stdio:['pipe','pipe','pipe']});
  let browser;
  try {
    const port = await new Promise((resolve,reject) => {
      let out=''; const timer=setTimeout(()=>reject(Error('Startup timed out')),20000);
      server.stdout.on('data',data=>{out+=data; if(/^\d+\s/.test(out)){clearTimeout(timer);resolve(Number(out.trim()));}});
      server.on('error',reject);
      server.stderr.on('data',data=>process.stderr.write(data));
    });
    browser = await chromium.launch({headless:true});
    const page = await browser.newPage({viewport:{width:1680,height:1120}});
    const errors=[]; page.on('pageerror',e=>errors.push(e.message));
    const base = `http://127.0.0.1:${port}`;
    await page.goto(base+'/modeler');
    await expect(page.locator('#applyLibrary')).toBeEnabled({timeout:30000});
    const before = await (await page.request.get(base+'/api/model')).json();
    const pending = before.definitionSources.pending;
    assert(pending.length > 0);
    // Guard the new write endpoint with the same local token as other writes.
    assert.equal((await page.request.post(base+'/api/model/apply',{data:{sourceHash:before.definitionSources.sourceHash}})).status(),403);
    await page.locator('#applyLibrary').click();
    await expect(page.locator('#notice')).toContainText('라이브러리 파일에 반영', {timeout:30000});
    await expect(page.locator('#applyLibrary')).toBeDisabled();
    const after = await (await page.request.get(base+'/api/model')).json();
    assert.deepEqual(after.model,before.model,'Applying definitions must preserve the complete graph');
    assert.deepEqual(after.definitionSources.pending,[]);
    for (const key of pending) {
      assert(fs.existsSync(path.join(library,'metadata',key)));
      assert(!fs.existsSync(path.join(temp,'drafts',key)));
    }
    await page.reload();
    await expect(page.locator('#definitionSources')).toContainText('미반영 0개');
    await page.locator('#objectJump').selectOption('Company');
    await expect(page.locator('#yamlFile')).toContainText('라이브러리');
    await page.screenshot({path:path.join(root,'output/entity-workbench/definition-sources-objects.png'),fullPage:true});

    await page.goto(base+'/value-types');
    await expect(page.locator('.type-item')).toHaveCount(8);
    await page.locator('#valueSearch').fill('COMPANY.CONTRACT.SIGNING');
    await page.locator('.value-item').click();
    await page.locator('#valueDefinition').fill('A verified supply contract event.');
    await page.locator('#save').click();
    await expect(page.locator('#applyLibrary')).toBeEnabled();
    await page.locator('#applyLibrary').click();
    await expect(page.locator('#notice')).toContainText('라이브러리 파일에 반영', {timeout:30000});
    await expect(page.locator('#sourceState')).toContainText('미반영 0개');
    await page.reload();
    await page.locator('#valueSearch').fill('COMPANY.CONTRACT.SIGNING');
    await page.locator('.value-item').click();
    await expect(page.locator('#valueDefinition')).toHaveValue('A verified supply contract event.');
    assert(fs.readFileSync(path.join(library,'metadata/value_types/event_types/company_deal.yaml'),'utf8').includes('A verified supply contract event.'));
    await page.screenshot({path:path.join(root,'output/entity-workbench/definition-sources-values.png'),fullPage:true});
    assert.deepEqual(errors,[]);
    console.log(JSON.stringify({objects:after.model.objects.length,links:after.model.relations.length,
      movedFiles:pending.length,valueTypeApply:true,tokenGuard:true,errors}));
  } finally {
    if(browser) await browser.close();
    server.stdin.end('\n');
    await new Promise(resolve=>server.once('exit',resolve));
    fs.rmSync(temp,{recursive:true,force:true});
  }
})().catch(error=>{console.error(error);process.exitCode=1;});
