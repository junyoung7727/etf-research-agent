import { test, expect } from '@playwright/test'

test.beforeEach(async ({page}) => {
  await page.addInitScript(() => {
    if (!localStorage.getItem('edge.original.preferences.v1')) localStorage.setItem('edge.original.preferences.v1',JSON.stringify({onboarded:true,watch:['AXAI'],themeWatch:['AI·반도체']}))
  })
  await page.goto('/original')
  await page.locator('[data-tab="community"]').click()
})

test('목 게시글에 좋아요·댓글·투표를 남기면 새로고침 뒤에도 유지된다', async ({page}) => {
  const errors:string[]=[]
  page.on('pageerror',error => errors.push(error.message))
  await expect(page.locator('[data-screen-label="커뮤니티"]')).toBeVisible()
  await page.getByText('산다',{exact:true}).click()
  const actions=page.locator('[data-sc-name="PostActions"]').first()
  const like=actions.locator('span').first()
  const count=Number(await like.innerText())
  await like.click()
  await expect(like).toHaveText(String(count+1))
  await actions.locator('span').filter({has:page.locator('svg')}).nth(1).click()
  await page.getByPlaceholder('답글 쓰기').fill('실적 발표일도 같이 확인해 볼게요.')
  await page.getByText('게시',{exact:true}).click()
  await expect(page.getByText('실적 발표일도 같이 확인해 볼게요.',{exact:true})).toBeVisible()
  const saved=await page.evaluate(()=>JSON.parse(localStorage.getItem('edge.original.preferences.v1')!))
  expect(saved.pollVotes.AXAI).toBe('buy')
  expect(Object.values(saved.commLikes)).toContain(true)
  const postId=Object.keys(saved.postReplies)[0]
  await page.reload()
  await page.locator('[data-tab="community"]').click()
  await page.locator(`[data-id="${postId}"]`).first().click()
  await expect(page.getByText('실적 발표일도 같이 확인해 볼게요.',{exact:true})).toBeVisible()
  expect(errors).toEqual([])
})

test('글쓰기와 삭제가 기기에 저장되고 다른 방문자에게 전파되지 않는다', async ({page,browser}) => {
  await page.locator('[data-sc-name="IconButton"]').last().click()
  await page.locator('textarea').fill('분산 비중을 먼저 확인해 보는 예시 글입니다.')
  await page.getByText('게시',{exact:true}).click()
  await expect(page.getByText('분산 비중을 먼저 확인해 보는 예시 글입니다.',{exact:true})).toBeVisible()
  await page.reload()
  await page.locator('[data-tab="community"]').click()
  await page.getByText('분산 비중을 먼저 확인해 보는 예시 글입니다.',{exact:true}).click()
  await page.getByText('삭제',{exact:true}).click()
  await page.getByText('지우기',{exact:true}).click()
  await expect(page.getByText('분산 비중을 먼저 확인해 보는 예시 글입니다.',{exact:true})).toHaveCount(0)
  const other=await browser.newContext()
  const otherPage=await other.newPage()
  await otherPage.goto('http://127.0.0.1:8018/original')
  expect(await otherPage.evaluate(()=>JSON.parse(localStorage.getItem('edge.original.preferences.v1')||'{}').commMine||{})).toEqual({})
  await other.close()
})
