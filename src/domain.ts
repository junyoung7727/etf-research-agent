export type Mode = 'DEMO' | 'REAL'
export type Status = 'READY' | 'STALE' | 'MISSING' | 'ERROR' | 'UNSUPPORTED'
export interface Quote {
  price: string | null
  previousClose: string | null
  changeRatio: string | null
  asOf: string
  receivedAt: string
  status: Status
  snapshotId: string
  feedState: string
}
export interface Instrument {
  id: string
  name: string
  shortName: string
  theme: string
  color: string
  icon: number
  currency: 'KRW'
  quote: Quote
}
export interface Candle {
  date: string
  open: string
  high: string
  low: string
  close: string
  volume: number
  isComplete: boolean
}
export interface Holding {
  name: string
  weight: number
  dayReturn: number | null
  return20: number | null
  theme: string
}
export interface Source {
  id: string
  title: string
  publisher: string
  url: string | null
  publishedAt: string
  excerpt: string
}
export interface Factor {
  kind: string
  label: string
  status: Status
  explanation: string
  metrics: { label: string; value: string | null; unit: string }[]
}
export interface Analysis {
  id: string
  asOf: string
  headline: string
  summary: string
  factors: Factor[]
  sources: Source[]
  dataMode: Mode
  outlook: null
  changeReason: string
  modelId: string
}
export interface EtfDetail {
  instrument: Instrument
  candles: Candle[]
  holdings: Holding[]
  holdingsAsOf: string | null
  residualWeight: number
  holdingsStatus: Status
  fundamentals: { label: string; value: string | null }[]
  analyses: Analysis[]
  dataMode: Mode
}
export interface Catalog {
  instruments: Instrument[]
  dataMode: Mode
  asOf: string
  feedState: string
  analysisEnabled: boolean
}
export interface Group {
  id: string
  name: string
  items: string[]
}
export interface Preferences {
  version: 1
  onboarded: boolean
  themes: string[]
  groups: Group[]
  activeGroup: string
  displayName: string
  recentSearches: string[]
}
export const initialPreferences = (): Preferences => ({
  version: 1,
  onboarded: false,
  themes: [],
  groups: [{ id: 'default', name: '기본 관심', items: [] }],
  activeGroup: 'default',
  displayName: '게스트',
  recentSearches: [],
})

// Missing data must never become a zero return or a neutral outlook.
export function changeRatio(
  price: number | null,
  previous: number | null,
): number | null {
  return price === null ||
    previous === null ||
    previous <= 0 ||
    !Number.isFinite(price) ||
    !Number.isFinite(previous)
    ? null
    : price / previous - 1
}
export function groupReturn(items: Instrument[]): number | null {
  if (!items.length || items.some((i) => i.quote.changeRatio === null))
    return null
  return (
    items.reduce((sum, i) => sum + Number(i.quote.changeRatio), 0) /
    items.length
  )
}
export function addItem(group: Group, id: string): Group {
  if (group.items.includes(id)) return group
  if (group.items.length >= 100)
    throw new Error('한 그룹에는 ETF를 100개까지 담을 수 있어요.')
  return { ...group, items: [...group.items, id] }
}
export function moveItem(group: Group, id: string, delta: number): Group {
  const from = group.items.indexOf(id),
    to = from + delta
  if (from < 0 || to < 0 || to >= group.items.length) return group
  const items = [...group.items]
  items.splice(to, 0, items.splice(from, 1)[0])
  return { ...group, items }
}
export function parsePreferences(value: string | null): Preferences {
  if (!value) return initialPreferences()
  const x = JSON.parse(value) as Preferences
  if (
    x.version !== 1 ||
    !Array.isArray(x.groups) ||
    !x.groups.length ||
    x.groups.length > 20 ||
    !x.groups.some((g) => g.id === 'default') ||
    new Set(x.groups.map((g) => g.id)).size !== x.groups.length ||
    !x.groups.some((g) => g.id === x.activeGroup) ||
    x.groups.some(
      (g) =>
        typeof g.id !== 'string' ||
        typeof g.name !== 'string' ||
        !g.name.trim() ||
        g.name.length > 20 ||
        !Array.isArray(g.items) ||
        g.items.length > 100 ||
        new Set(g.items).size !== g.items.length ||
        g.items.some(
          (id) => typeof id !== 'string' || !/^[0-9A-Z]{6}$/.test(id),
        ),
    ) ||
    typeof x.onboarded !== 'boolean' ||
    typeof x.displayName !== 'string' ||
    x.displayName.length > 20 ||
    !Array.isArray(x.themes) ||
    x.themes.some((t) => typeof t !== 'string') ||
    !Array.isArray(x.recentSearches) ||
    x.recentSearches.some((t) => typeof t !== 'string')
  )
    throw new Error(
      '저장된 관심 설정을 읽을 수 없어요. 설정에서 초기화해 주세요.',
    )
  return x
}
export const percent = (value: number | string | null) =>
  value === null
    ? '자료 없음'
    : `${Number(value) > 0 ? '+' : ''}${(Number(value) * 100).toFixed(2)}%`
export const won = (value: string | null) =>
  value === null
    ? '시세 없음'
    : `₩${Number(value).toLocaleString('ko-KR', { maximumFractionDigits: 0 })}`
