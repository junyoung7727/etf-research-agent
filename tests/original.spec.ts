import { test, expect } from '@playwright/test'

test('원본 모션이 실행되고 로그인 없이 선택한 ETF를 저장한다', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', e => errors.push(e.message))
  const external: string[] = []
  page.on('request', r => { if (!r.url().startsWith('http://127.0.0.1:8018')) external.push(r.url()) })
  await page.goto('/original')
  await expect(page.locator('[data-screen-label="온보딩 1 뉴스"]')).toBeVisible()
  const before = await page.evaluate(() => document.getAnimations().find(a => (a as CSSAnimation).animationName === 'obMarqueeA')?.currentTime)
  await page.waitForTimeout(120)
  const after = await page.evaluate(() => document.getAnimations().find(a => (a as CSSAnimation).animationName === 'obMarqueeA')?.currentTime)
  expect(Number(after)).toBeGreaterThan(Number(before))
  await page.getByText('다음', {exact:true}).click()
  await page.getByText('다음', {exact:true}).click()
  await page.getByText('내 ETF 고르기', {exact:true}).click()
  await page.getByText('AI·반도체', {exact:true}).click()
  await page.getByText('1개 테마 선택', {exact:true}).click()
  await page.locator('[data-etfk="AXAI"]').click()
  await page.getByText('1개 담고 시작하기', {exact:true}).click()
  await expect(page.locator('[data-screen-label="홈"]')).toBeVisible()
  await expect(page.locator('[data-demo-label]')).toContainText('예시')
  await expect(page.locator('[data-tab="community"]')).toBeVisible()
  await expect(page.getByText('로그인', {exact:true})).toHaveCount(0)
  await page.reload()
  await expect(page.locator('[data-screen-label="홈"]')).toBeVisible()
  const saved = await page.evaluate(() => JSON.parse(localStorage.getItem('edge.original.preferences.v1')!))
  expect(saved.watch).toEqual(['AXAI'])
  expect(saved.themeWatch).toContain('AI·반도체')
  await page.locator('[data-sc-name="IconButton"]').first().click()
  await page.locator('input').first().fill('반도체')
  await page.getByText('TIGER 반도체TOP10', {exact:true}).click()
  await expect(page.locator('[data-screen-label="ETF 상세"]')).toBeVisible()
  for (const tab of ['오늘 움직임','종목정보','AI 분석']) {
    await page.getByText(tab,{exact:true}).click()
    await expect(page.locator('[data-screen-label="ETF 상세"]')).toBeVisible()
  }
  await expect(page.locator('[data-st="comm"]')).toBeVisible()
  expect(errors).toEqual([])
  expect(external).toEqual([])
})

test('개인 설정은 이 기기에 저장되고 메뉴에서 제외 기능을 열 수 없다', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('edge.original.preferences.v1',JSON.stringify({onboarded:true,watch:['AXAI'],themeWatch:['AI·반도체']})))
  await page.goto('/original')
  await page.locator('[data-sc-name="IconButton"]').nth(1).click()
  await expect(page.locator('[data-screen-label="전체 메뉴"]')).toBeVisible()
  await expect(page.getByText('커뮤니티', {exact:true}).first()).toBeVisible()
  await expect(page.getByText('알림', {exact:true})).toHaveCount(0)
  await expect(page.getByText('로그인', {exact:true})).toHaveCount(0)
  await page.getByLabel('내 설정').fill('다니엘')
  await expect.poll(() => page.evaluate(() => JSON.parse(localStorage.getItem('edge.original.preferences.v1')!).meNick)).toBe('다니엘')
})

test('저장 실패를 성공으로 표시하지 않는다', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('edge.original.preferences.v1',JSON.stringify({onboarded:true,watch:['AXAI'],themeWatch:['AI·반도체']}))
    Storage.prototype.setItem = () => {throw new DOMException('full','QuotaExceededError')}
  })
  await page.goto('/original')
  await page.locator('[data-sc-name="IconButton"]').nth(1).click()
  await page.getByLabel('내 설정').fill('저장 확인')
  await expect(page.getByText('이 기기에 저장하지 못했어요. 새로고침하면 선택이 사라질 수 있어요.',{exact:true})).toBeVisible()
})

test('새 관심 그룹은 새로고침 뒤에도 남는다', async ({ page }) => {
  await page.addInitScript(() => {
    if (!localStorage.getItem('edge.original.preferences.v1')) localStorage.setItem('edge.original.preferences.v1',JSON.stringify({onboarded:true,watch:['AXAI'],themeWatch:['AI·반도체']}))
  })
  await page.goto('/original')
  await page.locator('[data-tab="discover"]').click()
  await page.getByText('그룹',{exact:true}).click()
  await page.getByPlaceholder('예: 연금계좌').fill('장기 ETF')
  await page.getByText('만들기',{exact:true}).click()
  await expect(page.getByText('장기 ETF',{exact:true})).toBeVisible()
  await page.reload()
  await expect(page.getByText('장기 ETF',{exact:true})).toBeVisible()
})

test('디자인 데모의 대화는 외부 Claude를 호출하거나 실제 AI 답변으로 표시하지 않는다', async ({ page }) => {
  await page.addInitScript(() => {
    Object.assign(window,{claude:{complete:()=>{throw new Error('Unexpected external model call')}}})
  })
  await page.goto('/original')
  await page.waitForFunction(()=>!!(window as any).__app)
  const reply = await page.evaluate(async()=>{
    const app = (window as any).__app
    await app.agentAsk('지금 사도 되나요?')
    return app.state.agentMsgs.at(-1).text as string
  })
  expect(reply).toMatch(/^예시 답변입니다\./)
})

test('원본 화면의 CSP가 외부 스크립트·eval을 허용하지 않고 nonce를 매번 바꾼다', async ({ request }) => {
  const a = await request.get('/original'), b = await request.get('/original')
  expect(a.status()).toBe(200)
  const csp = a.headers()['content-security-policy']
  expect(csp).toContain("script-src 'self';")
  expect(csp).not.toContain('unsafe-eval')
  const nonce = (await a.text()).match(/name="style-nonce" content="([^"]+)"/)![1]
  expect(csp).toContain(`'nonce-${nonce}'`)
  expect(b.headers()['content-security-policy']).not.toContain(nonce)
  expect((await request.get('/original-assets/.env')).status()).toBe(404)
})
