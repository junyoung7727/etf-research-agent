import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  changeRatio,
  groupReturn,
  addItem,
  moveItem,
  initialPreferences,
  parsePreferences,
} from './domain.ts'

test('가격이 100에서 103이면 수익률은 3%; 누락·0분모는 수익률이 아니다', () => {
  assert.ok(Math.abs(changeRatio(103, 100)! - 0.03) < 1e-12)
  assert.equal(changeRatio(null, 100), null)
  assert.equal(changeRatio(100, 0), null)
  assert.equal(changeRatio(100, null), null)
  assert.equal(groupReturn([]), null)
})
test('반복 관심 추가는 한 종목이며 100개 상한에서 기존 항목은 계속 허용', () => {
  let group = { id: 'default', name: '기본 관심', items: ['396500'] }
  assert.equal(addItem(group, '396500'), group)
  group = {
    ...group,
    items: Array.from({ length: 100 }, (_, i) => String(i).padStart(6, '0')),
  }
  assert.throws(() => addItem(group, '396500'), /100개/)
  assert.equal(addItem(group, '000001'), group)
})
test('재정렬은 항목을 잃지 않으며 경계 이동은 상태를 유지', () => {
  const group = {
    id: 'default',
    name: '기본 관심',
    items: ['396500', '449450', '487230'],
  }
  assert.deepEqual(moveItem(group, '396500', 1).items, [
    '449450',
    '396500',
    '487230',
  ])
  assert.equal(moveItem(group, '396500', -1), group)
})
test('잘못된 로컬 데이터로 기본 그룹·중복 제한을 우회할 수 없다', () => {
  const state = initialPreferences()
  assert.deepEqual(parsePreferences(JSON.stringify(state)), state)
  assert.throws(() =>
    parsePreferences(JSON.stringify({ ...state, groups: [] })),
  )
  state.groups[0].items = ['396500', '396500']
  assert.throws(() => parsePreferences(JSON.stringify(state)))
})
