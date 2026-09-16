import { useEffect, useState } from 'react'
import { navigate } from './navigation'
import { getJson } from './api'
import type { Catalog, EtfDetail, Instrument } from './domain'
import { Empty, FundIcon, FundRow, Section } from './ui'
import { themes } from './Onboarding'

export default function Explore({
  path,
  catalog,
  watchedIds,
  onOpen,
}: {
  path: string
  catalog: Catalog
  watchedIds: string[]
  onOpen: (i: Instrument) => void
}) {
  const [view, setView] = useState('brief')
  const [onlyWatched, setOnlyWatched] = useState(false)
  const [detail, setDetail] = useState<EtfDetail | null>(null)
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)
  const issueId = path.match(/^\/issue\/([0-9A-Z]{6})$/)?.[1]
  const theme = path.startsWith('/theme/')
    ? decodeURIComponent(path.slice(7))
    : null
  const instruments = catalog.instruments.filter(
    (i) =>
      (!theme || i.theme === theme) &&
      (!onlyWatched || watchedIds.includes(i.id)),
  )
  useEffect(() => {
    if (!issueId) return
    const abort = new AbortController()
    setDetail(null)
    setError('')
    getJson<EtfDetail>(`/api/etfs/${issueId}`, abort.signal)
      .then(setDetail)
      .catch((e) => {
        if (!abort.signal.aborted) setError(e.message)
      })
    return () => abort.abort()
  }, [issueId, retry])
  if (issueId) {
    const analysis = detail?.analyses[0]
    return (
      <>
        <div className="page-heading">
          <h1>이슈</h1>
          <button className="text-button" onClick={() => navigate('/explore')}>
            목록으로
          </button>
        </div>
        {error ? (
          <Empty title="자료를 불러오지 못했어요">
            <p>{error}</p>
            <button
              className="soft-button"
              onClick={() => setRetry((n) => n + 1)}
            >
              다시 시도
            </button>
          </Empty>
        ) : !detail ? (
          <div className="loading">자료를 불러오는 중</div>
        ) : !analysis ? (
          <Empty title="확인된 이슈가 없어요">
            <p>실제 출처가 확보된 내용을 기다리고 있어요.</p>
          </Empty>
        ) : (
          <>
            <div className="page-pad">
              <span className="eyebrow">
                {analysis.dataMode === 'DEMO'
                  ? '예시 이슈 · 실제 뉴스가 아닙니다'
                  : analysis.asOf.slice(0, 10)}
              </span>
              <h1>{analysis.headline}</h1>
              <blockquote>
                {analysis.summary}
                <details>
                  <summary>주목할 포인트</summary>
                  <p>
                    원문의 시각과 ETF 편입 자산의 연관성을 확인해요. 같은 날
                    가격이 움직였다는 이유만으로 인과관계가 입증되지는 않아요.
                  </p>
                </details>
              </blockquote>
              <details className="source-list">
                <summary>출처 보기</summary>
                {analysis.sources.map((s) => (
                  <article key={s.id}>
                    <h3>{s.title}</h3>
                    <p>{s.excerpt}</p>
                    {s.url && (
                      <a href={s.url} target="_blank" rel="noopener noreferrer">
                        {s.publisher} 원문 ↗
                      </a>
                    )}
                  </article>
                ))}
              </details>
            </div>
            <Section title="어떤 영향을 줄까?">
              <p className="prose">{analysis.factors[0]?.explanation}</p>
              <details open>
                <summary>연관된 ETF</summary>
                <FundRow
                  instrument={detail.instrument}
                  onOpen={() => onOpen(detail.instrument)}
                />
              </details>
            </Section>
          </>
        )}
      </>
    )
  }
  if (theme)
    return (
      <>
        <div className="page-heading">
          <h1>테마 분석</h1>
          <button className="text-button" onClick={() => navigate('/explore')}>
            목록으로
          </button>
        </div>
        <div className="page-pad">
          <span className="eyebrow">테마 · {theme}</span>
          <h1>{theme}, 어떤 근거를 살펴볼까요?</h1>
          <p className="prose">
            테마가 같아도 ETF의 편입 자산과 투자 비중은 달라요. 실제 구성과
            지표의 기준 시점을 함께 확인해 보세요.
          </p>
        </div>
        <Section title="무엇이 중요한가">
          <div className="composition-note">
            테마 핵심 지표와 임계값은 아직 확정되지 않았어요. 자료가 준비되기
            전에는 임의의 성장률이나 전망을 표시하지 않아요.
          </div>
        </Section>
        <Section title="이 테마의 ETF">
          {instruments.map((i) => (
            <FundRow key={i.id} instrument={i} onOpen={() => onOpen(i)} />
          ))}
          {!instruments.length && (
            <Empty title="등록된 ETF가 없어요">
              <p>이 테마의 대상 ETF가 추가되면 표시해요.</p>
            </Empty>
          )}
        </Section>
      </>
    )
  return (
    <>
      <div className="page-heading">
        <h1>탐색</h1>
        <span className="asof">국내 ETF</span>
      </div>
      <div className="explore-tabs">
        {[
          ['brief', 'ETF 브리핑'],
          ['themes', '테마'],
          ['issues', '이슈'],
        ].map(([id, label]) => (
          <button
            key={id}
            onClick={() => setView(id)}
            className={view === id ? 'selected' : ''}
          >
            {label}
          </button>
        ))}
      </div>
      {view === 'themes' ? (
        <div className="page-pad">
          <div className="theme-grid">
            {themes.map((t, i) => (
              <button
                className="theme-choice"
                key={t}
                onClick={() => navigate(`/theme/${encodeURIComponent(t)}`)}
              >
                <img src={`/figma/theme-${i}.png`} alt="" />
                <span>{t}</span>
              </button>
            ))}
          </div>
        </div>
      ) : (
        <div className="page-pad">
          <div className="section-heading">
            <h2>
              {view === 'brief'
                ? 'ETF를 이해하는 오늘의 단서'
                : '함께 살펴볼 이슈'}
            </h2>
            <button
              className="text-button"
              aria-pressed={onlyWatched}
              onClick={() => setOnlyWatched(!onlyWatched)}
            >
              {onlyWatched ? '내 관심' : '전체'}
            </button>
          </div>
          <p className="caption">
            {catalog.dataMode === 'DEMO'
              ? '예시 브리핑 · 투자 순위가 아닌 등록 순서예요.'
              : '전망 순위는 평가 정책 확정 후 제공해요.'}
          </p>
          {instruments.map((i, n) => (
            <article className="briefing-row" key={i.id}>
              <div className="briefing-meta">
                <span className="rank">{n + 1}</span>
                <FundIcon instrument={i} />
                <span>{i.name}</span>
                <span className="status-chip">판단 보류</span>
              </div>
              <button
                className="briefing-title"
                onClick={() =>
                  view === 'issues' ? navigate(`/issue/${i.id}`) : onOpen(i)
                }
              >
                {i.shortName}, 가격의 움직임과 구성 자산을 함께 확인해요
              </button>
              <div className="chips">
                <button
                  onClick={() =>
                    navigate(`/theme/${encodeURIComponent(i.theme)}`)
                  }
                >
                  {i.theme}
                </button>
                <button onClick={() => navigate(`/issue/${i.id}`)}>
                  근거 확인
                </button>
              </div>
            </article>
          ))}
          {!instruments.length && (
            <Empty title="관심 ETF가 없어요">
              <p>관심 목록에 ETF를 담으면 모아서 볼 수 있어요.</p>
            </Empty>
          )}
        </div>
      )}
    </>
  )
}
