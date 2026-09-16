import { test, expect } from '@playwright/test'
import { readFileSync } from 'node:fs'
const fixtures=JSON.parse(readFileSync('public/demo-api.json','utf8'))

test.beforeEach(async({page})=>{
  await page.addInitScript(()=>{
    localStorage.setItem('edge.original.preferences.v1',JSON.stringify({onboarded:true,watch:['AXAI'],themeWatch:['AI·반도체']}))
    // Deterministic REST boundary tests. SSE is checked independently on the server.
    Object.assign(window,{EventSource:class{close(){}}})
  })
})
async function openEtf(page:any) {
  await page.goto('/original')
  await page.locator('[data-sc-name="IconButton"]').first().click()
  await page.locator('input').first().fill('반도체')
  await page.getByText('TIGER 반도체TOP10',{exact:true}).click()
}

test('API price and completed-bar chart replace the original synthetic ticking values',async({page})=>{
  const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message))
  await openEtf(page)
  const quote=page.locator('[data-screen-label="ETF 상세"]').getByText('₩12,806',{exact:true}).first()
  await expect(quote).toBeVisible()
  await page.waitForTimeout(3300)
  await expect(quote).toBeVisible()
  const data=await page.evaluate(()=>{const a=(window as any).__app;return {q:a.liveQuote('AXAI'),chart:a.artData('AXAI')}})
  expect(data.q.chg).toBe('+2.90%')
  expect(data.chart.candles).toHaveLength(25)
  expect(data.chart.ma20L).not.toBe('—')
  expect(errors).toEqual([])
})
test('a different ETF response is rejected; retry succeeds without a request loop',async({page})=>{
  let calls=0
  await page.route('**/api/etfs/396500',route=>route.fulfill({json:++calls===1?fixtures.details['449450']:fixtures.details['396500']}))
  await openEtf(page)
  await page.getByText('AI 분석',{exact:true}).click()
  await expect(page.getByText('요청한 ETF의 자료가 아니에요.',{exact:true})).toBeVisible()
  await page.waitForTimeout(2100)
  expect(calls).toBe(1)
  await page.getByRole('button',{name:'자료 다시 불러오기'}).click()
  await expect(page.getByRole('button',{name:'자료 다시 불러오기'})).toHaveCount(0)
  expect(calls).toBe(2)
})
test('dated API analysis, factors, sources and demo chat work through visible controls',async({page})=>{
  await openEtf(page)
  await page.getByText('AI 분석',{exact:true}).click()
  await page.getByText('연결된 분석·출처',{exact:true}).click()
  const sheet=page.locator('[data-screen-label="연결된 분석"]')
  await expect(sheet).toBeVisible()
  await expect(sheet.getByText(fixtures.details['396500'].analyses[0].headline,{exact:true})).toBeVisible()
  await expect(sheet.getByText('20일 이동평균',{exact:true})).toBeVisible()
  await sheet.locator('[data-ari="1"]').click()
  await expect(sheet.getByText(fixtures.details['396500'].analyses[1].headline,{exact:true})).toBeVisible()
  await sheet.getByRole('button',{name:'닫기',exact:true}).click()
  await page.getByRole('button',{name:'ETF AI에게 질문'}).click()
  await page.getByRole('textbox',{name:'ETF 질문'}).fill('어떤 근거를 확인하면 되나요?')
  const request=page.waitForRequest(r=>r.url().endsWith('/api/chat-jobs'))
  await page.getByRole('button',{name:'전송',exact:true}).click()
  expect((await request).postDataJSON()).toMatchObject({instrumentId:'396500',message:'어떤 근거를 확인하면 되나요?'})
  const chat=page.locator('[data-screen-label="ETF AI 대화"]')
  await expect(chat.getByText(/^예시 답변입니다\./)).toBeVisible()
  await expect(chat.getByText(fixtures.details['396500'].analyses[0].sources[0].title,{exact:true})).toBeVisible()
})
test('a live catalog never falls back to demo and missing analysis never becomes a forecast',async({page})=>{
  const live=structuredClone(fixtures.catalog);live.dataMode='REAL';live.analysisEnabled=false
  const d=structuredClone(fixtures.details['396500']);d.dataMode='REAL';d.analyses=[];d.holdings=[];d.residualWeight=1
  await page.route('**/api/catalog',route=>route.fulfill({json:live}))
  await page.route('**/api/etfs/396500',route=>route.fulfill({json:d}))
  await openEtf(page)
  await page.getByText('AI 분석',{exact:true}).click()
  await page.getByText('연결된 분석·출처',{exact:true}).click()
  await expect(page.locator('[data-screen-label="연결된 분석"]')).toContainText('아직 분석 자료가 없어요')
  const fallback=await page.evaluate(c=>{const a=(window as any).__app;a.acceptCatalog(c);return {mode:a._mode,error:a.state.apiError}},fixtures.catalog)
  expect(fallback.mode).toBe('REAL');expect(fallback.error).toContain('예시 가격으로 바꾸지 않았어요')
})
