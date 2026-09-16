import { useEffect, useState } from 'react'
import {
  addItem,
  groupReturn,
  initialPreferences,
  moveItem,
  parsePreferences,
  type Catalog,
  type Instrument,
  type Preferences,
} from './domain'
import { getJson } from './api'
import { Change, Empty, FundRow, Icon, Section, Sheet } from './ui'
import Onboarding from './Onboarding'
import EtfPage from './EtfPage'
import Explore from './Explore'
import { navigate } from './navigation'
import WatchRow from './WatchRow'

const STORAGE_KEY = 'edge.preferences.v1'

export default function App() {
  const [path, setPath] = useState(location.pathname)
  const [catalog, setCatalog] = useState<Catalog | null>(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [retry, setRetry] = useState(0)
  const [prefs, setPrefs] = useState<Preferences>(initialPreferences)
  const [loaded, setLoaded] = useState(false)
  const [sheet, setSheet] = useState<
    'menu' | 'group' | 'help' | 'deleteGroup' | null
  >(null)
  const [groupName, setGroupName] = useState('')
  const [edit, setEdit] = useState(false)
  const [query, setQuery] = useState('')
  const [undo, setUndo] = useState<Preferences | null>(null)
  const [assign, setAssign] = useState<Instrument | null>(null)

  useEffect(() => {
    const load = () => {
      try {
        setPrefs(parsePreferences(localStorage.getItem(STORAGE_KEY)))
      } catch (e) {
        setNotice((e as Error).message)
      }
      setLoaded(true)
    }
    const route = () => setPath(location.pathname)
    load()
    window.addEventListener('popstate', route)
    window.addEventListener('storage', load)
    return () => {
      window.removeEventListener('popstate', route)
      window.removeEventListener('storage', load)
    }
  }, [])
  useEffect(() => {
    const abort = new AbortController()
    setError('')
    getJson<Catalog>('/api/catalog', abort.signal)
      .then(setCatalog)
      .catch((e) => {
        if (!abort.signal.aborted) setError(e.message)
      })
    return () => abort.abort()
  }, [retry])
  useEffect(() => {
    if (catalog?.dataMode !== 'REAL') return
    let lastEvent = Date.now()
    const stale = () =>
      setCatalog((old) =>
        old
          ? {
              ...old,
              feedState: 'DISCONNECTED',
              instruments: old.instruments.map((i) => ({
                ...i,
                quote: {
                  ...i.quote,
                  status: i.quote.price === null ? 'MISSING' : 'STALE',
                  feedState: 'DISCONNECTED',
                },
              })),
            }
          : old,
      )
    const stream = new EventSource('/api/quotes/stream')
    stream.onmessage = (event) => {
      try {
        const next = JSON.parse(event.data) as Catalog
        if (next.dataMode !== 'REAL' || !Array.isArray(next.instruments))
          throw new Error('Invalid stream')
        setCatalog(next)
        lastEvent = Date.now()
      } catch {
        stale()
      }
    }
    stream.onerror = stale
    const watch = window.setInterval(() => {
      if (Date.now() - lastEvent > 10000) stale()
    }, 5000)
    return () => {
      stream.close()
      window.clearInterval(watch)
    }
  }, [catalog?.dataMode])
  const save = (next: Preferences) => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
      setPrefs(next)
      return true
    } catch {
      setNotice(
        '저장 공간을 사용할 수 없어 변경을 저장하지 못했어요. 브라우저 설정을 확인해 주세요.',
      )
      return false
    }
  }
  const open = (i: Instrument) => navigate(`/etf/${i.id}`)
  const group =
    prefs.groups.find((g) => g.id === prefs.activeGroup) || prefs.groups[0]
  const items = group.items
    .map((id) => catalog?.instruments.find((i) => i.id === id))
    .filter(Boolean) as Instrument[]
  const updateGroup = (items: string[]) =>
    save({
      ...prefs,
      groups: prefs.groups.map((g) =>
        g.id === group.id ? { ...g, items } : g,
      ),
    })
  const remove = (id: string) => {
    const previous = prefs
    if (updateGroup(group.items.filter((i) => i !== id))) setUndo(previous)
  }
  const createGroup = () => {
    const name = groupName.trim()
    if (!name || name.length > 20) {
      setNotice('그룹 이름을 1~20자로 입력해 주세요.')
      return
    }
    if (
      prefs.groups.length >= 20 ||
      prefs.groups.some((g) => g.name === name)
    ) {
      setNotice('같은 이름의 그룹이 있거나 최대 20개에 도달했어요.')
      return
    }
    const id = crypto.randomUUID()
    if (
      save({
        ...prefs,
        activeGroup: id,
        groups: [...prefs.groups, { id, name, items: [] }],
      })
    ) {
      setSheet(null)
      setGroupName('')
    }
  }
  const search =
    catalog?.instruments.filter((i) =>
      `${i.name} ${i.id} ${i.theme}`
        .toLowerCase()
        .includes(query.toLowerCase()),
    ) || []
  const tab =
    path === '/watch'
      ? 'watch'
      : path.startsWith('/explore') ||
          path.startsWith('/theme') ||
          path.startsWith('/issue')
        ? 'explore'
        : 'home'
  const searching = path === '/search'
  const detailId = path.match(/^\/etf\/([0-9A-Z]{6})$/)?.[1]

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">
        본문 바로가기
      </a>
      <div
        className={`mode-banner ${catalog?.dataMode === 'REAL' ? 'live' : ''}`}
        role="status"
      >
        {catalog
          ? catalog.dataMode === 'DEMO'
            ? '체험용 예시 데이터 · 실시간 시세가 아닙니다'
            : `실제 시세 · ${catalog.feedState === 'CONNECTED' ? '연결됨' : '연결 상태 확인 중'}`
          : 'EDGE · 국내 ETF 브리핑'}
      </div>
      {notice && (
        <div role="alert" className="notice">
          {notice}
          <button aria-label="안내 닫기" onClick={() => setNotice('')}>
            ×
          </button>
        </div>
      )}
      {error ? (
        <main id="main">
          <Empty title="데이터를 불러오지 못했어요">
            <p>{error}</p>
            <button
              className="primary-button"
              onClick={() => setRetry((n) => n + 1)}
            >
              다시 시도
            </button>
          </Empty>
        </main>
      ) : !catalog || !loaded ? (
        <main id="main" className="loading" aria-busy="true">
          <span className="loading-dot" />
          ETF 정보를 불러오는 중
        </main>
      ) : !prefs.onboarded && (path === '/' || path === '/legacy') ? (
        <Onboarding
          instruments={catalog.instruments}
          onFinish={(themes, items) => {
            save({
              ...prefs,
              onboarded: true,
              themes,
              groups: [{ id: 'default', name: '기본 관심', items }],
              activeGroup: 'default',
            })
          }}
        />
      ) : (
        <>
          {detailId ? (
            <EtfPage
              id={detailId}
              catalog={catalog}
              onAssign={setAssign}
              isWatched={prefs.groups.some((g) => g.items.includes(detailId))}
            />
          ) : (
            <>
              <header className="topbar">
                <button
                  className="wordmark"
                  onClick={() => navigate('/')}
                  aria-label="EDGE 홈"
                >
                  EDGE<span>AI</span>
                </button>
                <div className="top-actions">
                  <button
                    className="icon-button"
                    aria-label="검색"
                    onClick={() => navigate('/search')}
                  >
                    <Icon name="search" />
                  </button>
                  <button
                    className="icon-button"
                    aria-label="전체 메뉴"
                    onClick={() => setSheet('menu')}
                  >
                    <Icon name="menu" />
                  </button>
                </div>
              </header>
              <main id="main">
                {searching ? (
                  <>
                    <div className="page-heading">
                      <h1>ETF 검색</h1>
                      <button
                        className="text-button"
                        onClick={() => navigate('/')}
                      >
                        닫기
                      </button>
                    </div>
                    <div className="page-pad">
                      <label className="search-field">
                        <Icon name="search" />
                        <input
                          autoFocus
                          aria-label="ETF 검색"
                          placeholder="ETF 이름, 코드, 테마로 검색"
                          value={query}
                          onChange={(e) => setQuery(e.target.value)}
                        />
                        <button
                          aria-label="검색어 지우기"
                          onClick={() => setQuery('')}
                        >
                          ×
                        </button>
                      </label>
                      {!query && prefs.recentSearches.length > 0 && (
                        <div className="chips">
                          {prefs.recentSearches.map((q) => (
                            <button key={q} onClick={() => setQuery(q)}>
                              {q}
                            </button>
                          ))}
                          <button
                            onClick={() =>
                              save({ ...prefs, recentSearches: [] })
                            }
                          >
                            기록 지우기
                          </button>
                        </div>
                      )}
                      <p className="caption">국내 ETF {search.length}개</p>
                      {search.map((i) => (
                        <FundRow
                          key={i.id}
                          instrument={i}
                          onOpen={() => {
                            if (query.trim())
                              save({
                                ...prefs,
                                recentSearches: [
                                  ...new Set([
                                    query.trim(),
                                    ...prefs.recentSearches,
                                  ]),
                                ].slice(0, 5),
                              })
                            open(i)
                          }}
                          action={
                            <button
                              className="text-button purple"
                              onClick={() => setAssign(i)}
                            >
                              담기
                            </button>
                          }
                        />
                      ))}
                      {!search.length && (
                        <Empty title="검색 결과가 없어요">
                          <p>다른 이름이나 종목코드로 검색해 보세요.</p>
                        </Empty>
                      )}
                    </div>
                  </>
                ) : tab === 'explore' ? (
                  <Explore
                    path={path}
                    catalog={catalog}
                    watchedIds={prefs.groups.flatMap((g) => g.items)}
                    onOpen={open}
                  />
                ) : (
                  <>
                    <div className="page-heading">
                      <h1>{tab === 'home' ? '내 종목 브리핑' : '관심'}</h1>
                      <span className="asof">
                        {catalog.dataMode === 'DEMO'
                          ? '예시 · 09.04'
                          : new Date(catalog.asOf).toLocaleTimeString('ko-KR', {
                              hour: '2-digit',
                              minute: '2-digit',
                            })}
                      </span>
                    </div>
                    <div className="group-bar">
                      <div className="group-tabs">
                        {prefs.groups.map((g) => (
                          <button
                            key={g.id}
                            className={g.id === group.id ? 'selected' : ''}
                            aria-pressed={g.id === group.id}
                            onClick={() =>
                              save({ ...prefs, activeGroup: g.id })
                            }
                          >
                            {g.name}
                          </button>
                        ))}
                      </div>
                      <button
                        className="add-group"
                        onClick={() => setSheet('group')}
                      >
                        + 그룹
                      </button>
                      {tab === 'watch' && (
                        <button
                          className="text-button"
                          onClick={() => setEdit(!edit)}
                        >
                          {edit ? '완료' : '편집'}
                        </button>
                      )}
                    </div>
                    {tab === 'home' && (
                      <div className="brief-card">
                        <div>
                          <span className="caption">
                            {group.name} · 오늘 등락
                          </span>
                          <strong className="group-change">
                            <Change
                              value={
                                group.items.length === items.length
                                  ? groupReturn(items)
                                  : null
                              }
                            />
                          </strong>
                        </div>
                        <span className="status-chip">전망 판단 보류</span>
                        <p>
                          {items.length
                            ? `${items.length}개 ETF 등락률의 단순평균이에요.`
                            : '관심 ETF를 담으면 오늘의 흐름을 모아드려요.'}
                        </p>
                        <button
                          className="text-button"
                          onClick={() => setSheet('help')}
                        >
                          이 숫자는 어떻게 계산하나요?
                        </button>
                      </div>
                    )}
                    <div className="page-pad">
                      {group.items.length > items.length && (
                        <p className="caption" role="status">
                          목록의 일부 ETF는 현재 시세 제공 대상에 없어 그룹
                          등락을 계산하지 않아요.
                        </p>
                      )}
                      {items.map((i, index) => (
                        <WatchRow
                          key={i.id}
                          instrument={i}
                          editing={edit && tab === 'watch'}
                          index={index}
                          count={items.length}
                          onOpen={() => open(i)}
                          onMove={(delta) =>
                            updateGroup(moveItem(group, i.id, delta).items)
                          }
                          onMoveTo={(target) => {
                            const to = group.items.indexOf(target)
                            if (to >= 0)
                              updateGroup(
                                moveItem(
                                  group,
                                  i.id,
                                  to - group.items.indexOf(i.id),
                                ).items,
                              )
                          }}
                          onRemove={() => remove(i.id)}
                        />
                      ))}
                      {!items.length && (
                        <Empty title="관심 ETF를 담아보세요">
                          <p>궁금한 종목의 흐름을 한곳에서 살펴보세요.</p>
                        </Empty>
                      )}
                      <button
                        className="soft-button full"
                        onClick={() => navigate('/search')}
                      >
                        + 관심 ETF 추가
                      </button>
                      {edit && group.id !== 'default' && (
                        <button
                          className="text-button danger full"
                          onClick={() => setSheet('deleteGroup')}
                        >
                          이 그룹 삭제
                        </button>
                      )}
                    </div>
                    {tab === 'home' && (
                      <Section
                        title="관심 밖의 새로운 발견"
                        aside={
                          <button
                            className="text-button"
                            onClick={() => navigate('/explore')}
                          >
                            탐색하기 →
                          </button>
                        }
                      >
                        <p className="muted">
                          테마에서 출발해, ETF의 구성과 근거를 살펴보세요.
                        </p>
                        <div className="discovery-tiles">
                          {['AI·반도체', '방산', '바이오'].map((t, i) => (
                            <button
                              key={t}
                              onClick={() =>
                                navigate(`/theme/${encodeURIComponent(t)}`)
                              }
                            >
                              <img src={`/figma/theme-${i}.png`} alt="" />
                              <strong>{t}</strong>
                            </button>
                          ))}
                        </div>
                      </Section>
                    )}
                  </>
                )}
              </main>
            </>
          )}
          <nav className="bottom-nav" aria-label="주요 메뉴">
            {[
              ['home', '홈', '/'],
              ['watch', '관심', '/watch'],
              ['explore', '탐색', '/explore'],
            ].map(([id, label, url]) => (
              <button
                key={id}
                className={!detailId && tab === id ? 'active' : ''}
                aria-current={!detailId && tab === id ? 'page' : undefined}
                onClick={() => {
                  setEdit(false)
                  navigate(url)
                }}
              >
                <Icon name={id} />
                <span>{label}</span>
              </button>
            ))}
          </nav>
        </>
      )}
      {undo && (
        <div className="undo" role="status">
          관심 목록을 변경했어요.
          <button
            onClick={() => {
              save(undo)
              setUndo(null)
            }}
          >
            되돌리기
          </button>
          <button aria-label="닫기" onClick={() => setUndo(null)}>
            ×
          </button>
        </div>
      )}
      {assign && (
        <Sheet title="관심 그룹에 담기" onClose={() => setAssign(null)}>
          <p className="muted">{assign.name}</p>
          {prefs.groups.map((g) => (
            <label className="check-row" key={g.id}>
              <span>{g.name}</span>
              <input
                type="checkbox"
                checked={g.items.includes(assign.id)}
                onChange={(e) => {
                  try {
                    const next = e.target.checked
                      ? addItem(g, assign.id)
                      : { ...g, items: g.items.filter((i) => i !== assign.id) }
                    save({
                      ...prefs,
                      groups: prefs.groups.map((x) =>
                        x.id === g.id ? next : x,
                      ),
                    })
                  } catch (e) {
                    setNotice((e as Error).message)
                  }
                }}
              />
            </label>
          ))}
          <button className="primary-button" onClick={() => setAssign(null)}>
            완료
          </button>
        </Sheet>
      )}
      {sheet === 'group' && (
        <Sheet title="새 관심 그룹" onClose={() => setSheet(null)}>
          <form
            onSubmit={(e) => {
              e.preventDefault()
              createGroup()
            }}
          >
            <label className="field-label">
              그룹 이름
              <input
                autoFocus
                maxLength={20}
                value={groupName}
                onChange={(e) => setGroupName(e.target.value)}
                placeholder="예: 장기적으로 살펴볼 ETF"
              />
            </label>
            <button className="primary-button" type="submit">
              그룹 만들기
            </button>
          </form>
        </Sheet>
      )}
      {sheet === 'deleteGroup' && (
        <Sheet title="그룹을 삭제할까요?" onClose={() => setSheet(null)}>
          <p className="prose">
            {group.name} 그룹을 삭제해요. 다른 그룹에 담은 ETF는 유지돼요.
          </p>
          <div className="chips">
            <button onClick={() => setSheet(null)}>취소</button>
            <button
              onClick={() => {
                const previous = prefs
                if (
                  group.id !== 'default' &&
                  save({
                    ...prefs,
                    activeGroup: 'default',
                    groups: prefs.groups.filter((g) => g.id !== group.id),
                  })
                ) {
                  setUndo(previous)
                  setSheet(null)
                }
              }}
            >
              그룹 삭제
            </button>
          </div>
        </Sheet>
      )}
      {sheet === 'menu' && (
        <Sheet title="전체 메뉴" onClose={() => setSheet(null)}>
          <label className="field-label">
            내 이름
            <input
              maxLength={20}
              value={prefs.displayName}
              onChange={(e) => save({ ...prefs, displayName: e.target.value })}
            />
          </label>
          <button className="menu-row" onClick={() => setSheet('help')}>
            EDGE 사용 안내 <span>→</span>
          </button>
          <button
            className="menu-row"
            onClick={() => {
              setSheet(null)
              save({ ...prefs, onboarded: false })
              navigate('/')
            }}
          >
            시작 안내 다시 보기 <span>→</span>
          </button>
          <details className="reset-settings">
            <summary>개인 설정 초기화</summary>
            <p>이 브라우저의 관심 그룹과 선택한 테마가 지워져요.</p>
            <button
              className="soft-button"
              onClick={() => {
                if (save(initialPreferences())) {
                  setSheet(null)
                  setNotice('')
                  navigate('/')
                }
              }}
            >
              초기화하기
            </button>
          </details>
          <p className="caption">EDGE 0.1.0 · 국내 ETF 데모</p>
        </Sheet>
      )}
      {sheet === 'help' && (
        <Sheet title="EDGE를 읽는 방법" onClose={() => setSheet(null)}>
          <div className="prose">
            <h3>숫자와 판단을 나눠서 봐요</h3>
            <p>
              오늘 등락은 현재가 ÷ 전일 종가 − 1이에요. 100원에서 103원이 되면
              +3%예요.
            </p>
            <p>
              그룹 등락은 각 ETF 등락률의 단순평균이며 내 계좌 수익률은
              아니에요. 시세가 하나라도 빠지면 평균을 보여주지 않아요.
            </p>
            <h3>자료가 없으면 판단도 보류해요</h3>
            <p>
              자료 없음과 0은 달라요. 예시 데이터는 실제 시장 정보가 아니며, AI
              전망의 계산 정책은 아직 확정되지 않았어요.
            </p>
            <h3>내 관심 목록은 이 브라우저에 저장돼요</h3>
            <p>
              새로고침해도 유지되지만 다른 기기로 옮겨지지 않아요. 저장소를
              지우면 초기화돼요. 여러 탭에서 수정하면 마지막으로 저장한 설정을
              사용해요.
            </p>
          </div>
        </Sheet>
      )}
    </div>
  )
}
