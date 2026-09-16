import { chromium } from 'playwright'
import { mkdir, writeFile } from 'node:fs/promises'
import assert from 'node:assert/strict'

const output = 'artifacts/original-fidelity'
await mkdir(output,{recursive:true})
await writeFile(`${output}/run.json`,JSON.stringify({complete:false}))
const sourceUrl = process.env.ORIGINAL_URL || 'http://127.0.0.1:8020/MarketBrew%20App%20v188%20copy%202.dc.html'
const builtUrl = 'http://127.0.0.1:8018/original?fixture=original'
const cases = [
  ['intro-1',{screen:'onboarding',obStep:1},[0,210,420,1000,13000,26000]],
  ['intro-2',{screen:'onboarding',obStep:2},[0,80,150,360,550,800,1200]],
  ['intro-3',{screen:'onboarding',obStep:3},[0,210,1000]],
  ['themes-empty',{screen:'onboarding',obStep:4,obThemes:[]},[1000]],
  ['themes-selected',{screen:'onboarding',obStep:4,obThemes:['AI·반도체','방산']},[1000]],
  ['etfs-empty',{screen:'onboarding',obStep:5,obEtfs:[]},[1000]],
  ['etfs-selected',{screen:'onboarding',obStep:5,obEtfs:['AXAI','DEFN']},[1000]],
  ['etfs-search',{screen:'onboarding',obStep:5,obQuery:'반도체'},[1000]],
  ['etfs-no-results',{screen:'onboarding',obStep:5,obQuery:'없는종목xxx'},[1000]],
  ['home',{screen:'home'},[1000]],
  ['home-empty',{screen:'home',watch:[]},[1000]],
  ['watch',{screen:'discover'},[1000]],
  ['watch-edit',{screen:'watchEdit'},[1000]],
  ['watch-empty',{screen:'watchEdit',watch:[]},[1000]],
  ['search',{screen:'search'},[1000]],
  ['search-result',{screen:'search',query:'반도체'},[1000]],
  ['search-empty',{screen:'search',query:'없는종목xxx'},[1000]],
  ['stock-analysis',{screen:'stock',stockTab:'brief'},[1000]],
  ['stock-price',{screen:'stock',stockTab:'summary'},[1000]],
  ['stock-holdings',{screen:'stock',stockTab:'data'},[1000]],
  ['explore',{screen:'explore'},[1000]],
  ['themes',{screen:'themes'},[1000]],
  ['issues',{screen:'issueList'},[1000]],
  ['menu',{screen:'home',menuOpen:true},[0,130,260,1000]],
  ['analysis-sheet',{screen:'stock',daSheet:true},[0,140,280,1000]],
]
const browser = await chromium.launch()
const result = []
try {
  const targets=[['source',sourceUrl],['packaged',builtUrl]]
  if(process.env.SOURCE_REPEAT==='1') targets.push(['source-repeat',sourceUrl])
  for (const [name,url] of targets) {
    const page = await browser.newPage({viewport:{width:470,height:950},deviceScaleFactor:1})
    const errors=[]
    page.on('pageerror',e=>errors.push(e.message))
    page.on('console',m=>{if(m.type()==='error')errors.push(m.text())})
    // Hold JS interval-driven demonstration quotes at the same tick; CSS animations remain real.
    await page.addInitScript(()=>{
      const intervals = new Map(); let id=1
      window.setInterval=(fn,ms,...args)=>{const n=id++;intervals.set(n,()=>fn(...args));return n}
      window.clearInterval=n=>intervals.delete(n)
      window.__tickIntervals=()=>[...intervals.values()].forEach(fn=>fn())
    })
    await page.goto(url)
    await page.waitForFunction(()=>!!window.__app,{timeout:30000})
    await page.waitForLoadState('networkidle')
    await page.waitForFunction(()=>document.querySelectorAll('.sc-placeholder').length===0)
    await page.evaluate(()=>document.fonts.ready)
    const initial = await page.evaluate(()=>({...window.__app.state}))
    for (const [label,state,times] of cases) {
      await page.evaluate(async ({initial,state})=>{
        window.__app.state=structuredClone(initial)
        await new Promise(resolve=>window.__app.setState({screen:'__capture__'},resolve))
        await new Promise(resolve=>window.__app.setState({...initial,...state},resolve))
        window.__frameAnimations=document.getAnimations()
        for (const a of window.__frameAnimations) {a.pause();a.currentTime=0}
        await document.fonts.ready
        await Promise.all([...document.images].map(i=>i.decode().catch(()=>{})))
      },{initial,state})
      // The supplied runtime fetches components lazily. Compare after those source
      // components and CSS background images have loaded, without their placeholders.
      await page.waitForLoadState('networkidle')
      await page.waitForFunction(()=>document.querySelectorAll('.sc-placeholder').length===0,{},{timeout:15000})
      await page.evaluate(async()=>{
        await document.fonts.ready
        const urls=[...new Set([...document.querySelectorAll('*')].flatMap(e=>[...getComputedStyle(e).backgroundImage.matchAll(/url\("?([^"\)]+)"?\)/g)].map(m=>m[1])))];
        await Promise.all(urls.map(async url=>{const i=new Image();i.src=url;await i.decode()}))
        for(const a of document.getAnimations()) {
          if(!window.__frameAnimations.includes(a)) {a.pause();a.currentTime=0;window.__frameAnimations.push(a)}
        }
      })
      const motions = await page.evaluate(()=>window.__frameAnimations.map(a=>({name:a.animationName,timing:a.effect.getTiming(),keyframes:a.effect.getKeyframes()})))
      const screens = await page.locator('[data-screen-label]').evaluateAll(es=>es.map(e=>e.getAttribute('data-screen-label')))
      assert(screens.length, `${name}/${label}: expected a rendered screen`)
      for (const time of times) {
        await page.evaluate(t=>{for(const a of window.__frameAnimations)a.currentTime=t},time)
        await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))))
        await page.screenshot({path:`${output}/${name}-${label}-${time}.png`})
      }
      result.push({name,label,screens,motions,times,text:await page.locator('body').innerText()})
    }
    await writeFile(`${output}/${name}-errors.json`,JSON.stringify(errors,null,2))
    if(name==='packaged') assert.deepEqual(errors,[],'Packaged app must not introduce browser/CSP errors')
    await page.close()
  }
  const comparisons=cases.map(([label])=>{
    const a=result.find(r=>r.name==='source'&&r.label===label),b=result.find(r=>r.name==='packaged'&&r.label===label)
    return {label,screens:a.screens,textEqual:a.text===b.text,motionEqual:JSON.stringify(a.motions)===JSON.stringify(b.motions),frames:a.times.length}
  })
  await writeFile(`${output}/frames.json`,JSON.stringify(result,null,2))
  await writeFile(`${output}/checks.json`,JSON.stringify(comparisons,null,2))
  await writeFile(`${output}/run.json`,JSON.stringify({complete:true,viewport:{width:470,height:950},frames:comparisons.reduce((n,c)=>n+c.frames,0),capturedAt:new Date().toISOString()}))
  console.log(JSON.stringify(comparisons))
  assert(comparisons.every(c=>c.textEqual&&c.motionEqual),'Source text or motion differs; inspect checks.json')
} finally { await browser.close() }
