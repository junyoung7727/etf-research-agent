import { test, expect } from '@playwright/test'

test('온보딩 → 관심 설정 → 상세와 출처 → 새로고침 보존', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', (e) => errors.push(e.message))
  await page.goto('/')
  await expect(
    page.getByText('체험용 예시 데이터 · 실시간 시세가 아닙니다'),
  ).toBeVisible()
  for (let i = 0; i < 3; i++)
    await page.getByRole('button', { name: '다음', exact: true }).click()
  await page.getByRole('button', { name: 'AI·반도체', exact: true }).click()
  await page.getByRole('button', { name: 'ETF 고르기' }).click()
  await page.getByRole('button', { name: /TIGER 반도체TOP10/ }).click()
  await page.getByRole('button', { name: '1개 ETF와 시작하기' }).click()
  await expect(
    page.getByRole('heading', { name: '내 종목 브리핑' }),
  ).toBeVisible()
  await page.screenshot({ path: 'test-results/edge-home.png', fullPage: true })
  await page.getByRole('button', { name: /TIGER 반도체TOP10/ }).click()
  await expect(page.getByRole('tab', { name: 'AI 분석' })).toBeVisible()
  await page.getByRole('button', { name: '근거와 출처 보기' }).click()
  await expect(page.getByRole('dialog')).toContainText(
    '실제 기사·공시가 아닙니다',
  )
  await page.keyboard.press('Escape')
  await page.getByRole('tab', { name: '오늘 움직임' }).click()
  await expect(page.locator('canvas')).toBeVisible()
  await page.getByRole('button', { name: '60거래일' }).click()
  await page.screenshot({ path: 'test-results/edge-chart.png', fullPage: true })
  await page.getByRole('tab', { name: '종목정보' }).click()
  await page.getByRole('button', { name: '전체 구성 보기' }).click()
  await expect(page.getByRole('dialog')).toContainText('27.01%')
  await page.keyboard.press('Escape')
  await page
    .getByRole('navigation', { name: '주요 메뉴' })
    .getByRole('button', { name: '관심' })
    .click()
  await page.reload()
  await expect(
    page.getByRole('button', { name: /TIGER 반도체TOP10/ }),
  ).toBeVisible()
  await expect(
    page.getByRole('button', { name: /커뮤니티|로그인|알림/ }),
  ).toHaveCount(0)
  expect(errors).toEqual([])
})

test('그룹 편집·되돌리기와 별도 방문자 격리', async ({ page, browser }) => {
  await page.goto('/')
  await page.getByRole('button', { name: '건너뛰기' }).click()
  await page
    .getByRole('navigation')
    .getByRole('button', { name: '관심' })
    .click()
  await page.getByRole('button', { name: '+ 그룹', exact: true }).click()
  await page.getByLabel('그룹 이름').fill('장기 관심')
  await page.getByRole('button', { name: '그룹 만들기' }).click()
  await page.getByRole('button', { name: '+ 관심 ETF 추가' }).click()
  await page.getByLabel('ETF 검색').fill('396500')
  await expect(page.locator('.fund-row')).toHaveCount(1)
  await page.getByRole('button', { name: '담기', exact: true }).click()
  await page.getByRole('dialog').getByLabel('장기 관심').check()
  await page.getByRole('button', { name: '완료', exact: true }).click()
  await page
    .getByRole('navigation')
    .getByRole('button', { name: '관심' })
    .click()
  await page.getByRole('button', { name: '편집', exact: true }).click()
  await page.getByRole('button', { name: 'TIGER 반도체TOP10 제거' }).click()
  await expect(
    page.getByRole('heading', { name: '관심 ETF를 담아보세요' }),
  ).toBeVisible()
  await page.getByRole('button', { name: '되돌리기' }).click()
  await expect(
    page.getByRole('button', { name: 'TIGER 반도체TOP10 제거' }),
  ).toBeVisible()
  await page.getByRole('button', { name: '이 그룹 삭제', exact: true }).click()
  await page.getByRole('button', { name: '취소', exact: true }).click()
  await expect(
    page.getByRole('button', { name: '장기 관심', exact: true }),
  ).toBeVisible()
  const other = await browser.newContext()
  const otherPage = await other.newPage()
  await otherPage.goto('http://127.0.0.1:8018/watch')
  await expect(
    otherPage.getByRole('heading', { name: '관심 ETF를 담아보세요' }),
  ).toBeVisible()
  await other.close()
})

test('360·402·430px 직접 링크와 테마·이슈 탐색', async ({ page }) => {
  for (const width of [360, 402, 430]) {
    await page.setViewportSize({ width, height: 874 })
    await page.goto('/etf/396500')
    await expect(page.getByRole('tab', { name: 'AI 분석' })).toBeVisible()
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true)
  }
  await page
    .getByRole('navigation')
    .getByRole('button', { name: '탐색' })
    .click()
  await page.getByRole('button', { name: '테마', exact: true }).click()
  await page.getByRole('button', { name: 'AI·반도체', exact: true }).click()
  await expect(
    page.getByRole('heading', { name: '이 테마의 ETF' }),
  ).toBeVisible()
  await page.goto('/issue/396500')
  await page.getByText('출처 보기', { exact: true }).click()
  await expect(
    page.getByText('화면 검수용 예시 자료', { exact: true }),
  ).toBeVisible()
})

test('API 장애는 예시 값으로 바꿔 숨기지 않고 재시도 가능', async ({
  page,
}) => {
  await page.route('**/api/catalog', (route) =>
    route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({ detail: '공급자 연결 실패' }),
    }),
  )
  await page.goto('/watch')
  await expect(
    page.getByText('공급자 연결 실패', { exact: true }),
  ).toBeVisible()
  await page.unroute('**/api/catalog')
  await page.getByRole('button', { name: '다시 시도' }).click()
  await expect(
    page.getByRole('heading', { name: '관심', exact: true }),
  ).toBeVisible()
})

test('끌어서 재정렬한 ETF 순서가 새로고침 뒤에도 유지', async ({ page }) => {
  await page.addInitScript(() => {
    if (!localStorage.getItem('edge.preferences.v1'))
      localStorage.setItem(
        'edge.preferences.v1',
        JSON.stringify({
          version: 1,
          onboarded: true,
          themes: [],
          groups: [
            {
              id: 'default',
              name: '기본 관심',
              items: ['396500', '449450', '487230'],
            },
          ],
          activeGroup: 'default',
          displayName: '게스트',
          recentSearches: [],
        }),
      )
  })
  await page.goto('/watch')
  await page.getByRole('button', { name: '편집', exact: true }).click()
  const handle = await page
    .getByRole('button', { name: 'TIGER 반도체TOP10 끌어서 순서 이동' })
    .boundingBox()
  const target = await page.locator('[data-etf-id="487230"]').boundingBox()
  if (!handle || !target) throw new Error('Drag handle or target not visible')
  await page.mouse.move(
    handle.x + handle.width / 2,
    handle.y + handle.height / 2,
  )
  await page.mouse.down()
  await page.mouse.move(
    target.x + target.width / 2,
    target.y + target.height / 2,
    { steps: 10 },
  )
  await page.mouse.up()
  await page.reload()
  await expect(page.locator('[data-etf-id]').first()).toHaveAttribute(
    'data-etf-id',
    '449450',
  )
  await expect(page.locator('[data-etf-id]').last()).toHaveAttribute(
    'data-etf-id',
    '396500',
  )
})
