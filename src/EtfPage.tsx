import { useEffect, useState } from 'react'
import { getJson } from './api'
import { navigate } from './navigation'
import type { Catalog, EtfDetail, Factor, Instrument } from './domain'
import { percent, won } from './domain'
import { Change, Empty, FundIcon, Icon, Section, Sheet } from './ui'
import Chart from './Chart'

export default function EtfPage({
  id,
  catalog,
  onAssign,
  isWatched,
}: {
  id: string
  catalog: Catalog
  onAssign: (i: Instrument) => void
  isWatched: boolean
}) {
  const [detail, setDetail] = useState<EtfDetail | null>(null)
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)
  const [tab, setTab] = useState('analysis')
  const [dateIndex, setDateIndex] = useState(0)
  const [sheet, setSheet] = useState<
    'analysis' | 'sources' | 'holdings' | null
  >(null)
  const [factor, setFactor] = useState<Factor | null>(null)
  const [themeMode, setThemeMode] = useState(false)
  const [daily, setDaily] = useState(false)
  const [sort, setSort] = useState('weight')
  const [job, setJob] = useState('')
  useEffect(() => {
    const controller = new AbortController()
    setDetail(null)
    setError('')
    setDateIndex(0)
    getJson<EtfDetail>(`/api/etfs/${id}`, controller.signal)
      .then(setDetail)
      .catch((e) => {
        if (!controller.signal.aborted) setError(e.message)
      })
    return () => controller.abort()
  }, [id, retry])
  const cached = catalog.instruments.find((i) => i.id === id)
  const instrument = cached || detail?.instrument
  const analysis = detail?.analyses[dateIndex]
  const holdings = detail?.holdings || []
  const blocks = themeMode
    ? Object.entries(
        holdings.reduce<Record<string, number>>(
          (acc, h) => ({ ...acc, [h.theme]: (acc[h.theme] || 0) + h.weight }),
          {},
        ),
      ).map(([name, weight]) => ({
        name,
        weight,
        dayReturn: null,
        return20: null,
      }))
    : holdings
  const tiles = [
    ...blocks,
    {
      name: '미확인 구성',
      weight: detail?.residualWeight ?? 1,
      dayReturn: null,
      return20: null,
    },
  ].filter((x) => x.weight > 0)
  const split = Math.max(1, Math.floor(tiles.length / 2)),
    rows = [tiles.slice(0, split), tiles.slice(split)].filter(
      (row) => row.length,
    )
  const generate = async () => {
    setJob('분석 요청을 보내는 중이에요.')
    try {
      const response = await fetch('/api/analysis-jobs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ instrumentId: id }),
      })
      const body = await response.json()
      if (!response.ok)
        throw new Error(
          body.error?.message || body.detail || '분석 요청에 실패했어요.',
        )
      setJob(
        body.state === 'SUCCEEDED'
          ? '분석이 저장되었어요.'
          : '분석 중이에요. 잠시 후 분석 목록을 새로고침해 주세요.',
      )
    } catch (e) {
      setJob((e as Error).message)
    }
  }
  return (
    <>
      <header className="detail-nav">
        <button
          className="icon-button"
          aria-label="뒤로가기"
          onClick={() => (history.length > 1 ? history.back() : navigate('/'))}
        >
          <Icon name="back" />
        </button>
        <strong>{instrument?.shortName || 'ETF 상세'}</strong>
        <button
          className="icon-button"
          aria-label="검색"
          onClick={() => navigate('/search')}
        >
          <Icon name="search" />
        </button>
      </header>
      <main id="main">
        {instrument && (
          <div className="detail-quote">
            <FundIcon instrument={instrument} />
            <div className="fund-copy">
              <strong>{instrument.name}</strong>
              <span className="quote-line">
                {won(instrument.quote.price)}{' '}
                <Change value={instrument.quote.changeRatio} />
              </span>
              {instrument.quote.status === 'STALE' && (
                <small className="caption">
                  마지막 시세 ·{' '}
                  {new Date(instrument.quote.asOf).toLocaleString('ko-KR')}
                </small>
              )}
            </div>
            <button
              className={`heart-button ${isWatched ? 'saved' : ''}`}
              aria-label="관심 그룹에 담기"
              aria-pressed={isWatched}
              onClick={() => onAssign(instrument)}
            >
              <Icon name="heart" />
            </button>
          </div>
        )}
        <div className="detail-tabs" role="tablist" aria-label="ETF 정보">
          {[
            ['analysis', 'AI 분석'],
            ['market', '오늘 움직임'],
            ['holdings', '종목정보'],
          ].map(([key, title]) => (
            <button
              key={key}
              role="tab"
              aria-selected={tab === key}
              className={tab === key ? 'selected' : ''}
              onClick={() => setTab(key)}
            >
              {title}
            </button>
          ))}
        </div>
        {error ? (
          <Empty title="ETF 정보를 불러오지 못했어요">
            <p>{error}</p>
            <button
              className="soft-button"
              onClick={() => setRetry((n) => n + 1)}
            >
              다시 시도
            </button>
          </Empty>
        ) : !detail ? (
          <div className="loading" aria-busy="true">
            상세 정보를 불러오는 중
          </div>
        ) : tab === 'analysis' ? (
          <>
            <div className="date-strip">
              <button
                aria-label="이전 분석"
                disabled={dateIndex >= detail.analyses.length - 1}
                onClick={() => setDateIndex((i) => i + 1)}
              >
                ‹
              </button>
              {[...detail.analyses].reverse().map((a, i) => (
                <button
                  key={a.id}
                  className={a.id === analysis?.id ? 'selected' : ''}
                  aria-pressed={a.id === analysis?.id}
                  onClick={() => setDateIndex(detail.analyses.length - 1 - i)}
                >
                  <small>{a.asOf.slice(5, 7)}월</small>
                  <strong>{a.asOf.slice(8, 10)}</strong>
                </button>
              ))}
              <button
                aria-label="다음 분석"
                disabled={dateIndex === 0}
                onClick={() => setDateIndex((i) => i - 1)}
              >
                ›
              </button>
            </div>
            {analysis ? (
              <div className="page-pad analysis-body">
                <span className="eyebrow">
                  {analysis.dataMode === 'DEMO' ? '예시 분석' : '저장된 분석'}
                </span>
                <h1>{analysis.headline}</h1>
                <p className="caption">
                  EDGE AI · {new Date(analysis.asOf).toLocaleString('ko-KR')}
                </p>
                <div className="analysis-card">
                  <p className="caption">단기 전망</p>
                  <h2>판단 보류</h2>
                  <p>{analysis.summary}</p>
                  <div className="factor-buttons">
                    {analysis.factors.map((f) => (
                      <button key={f.kind} onClick={() => setFactor(f)}>
                        <span
                          className={f.status === 'READY' ? 'factor-ready' : ''}
                        >
                          {f.status === 'READY' ? '✓' : '—'}
                        </span>
                        {f.label}
                      </button>
                    ))}
                  </div>
                  <button
                    className="accent-button full"
                    onClick={() => setSheet('analysis')}
                  >
                    분석 자세히 보기 <Icon name="chevron" size={16} />
                  </button>
                </div>
                <details className="change-reason">
                  <summary>지난 분석과 무엇이 달라졌나요?</summary>
                  <p>{analysis.changeReason}</p>
                </details>
                <button
                  className="soft-button full"
                  onClick={() => setSheet('sources')}
                >
                  근거와 출처 보기
                </button>
              </div>
            ) : (
              <Empty title="저장된 분석이 없어요">
                <p>실제 근거를 수집한 분석이 준비되면 표시해요.</p>
              </Empty>
            )}
            {catalog.analysisEnabled && (
              <div className="page-pad">
                <button className="primary-button" onClick={generate}>
                  현재 자료로 분석 요청
                </button>
                <p role="status">{job}</p>
                <button
                  className="text-button"
                  onClick={() => setRetry((n) => n + 1)}
                >
                  분석 목록 새로고침
                </button>
              </div>
            )}
          </>
        ) : tab === 'market' ? (
          <>
            <Chart candles={detail.candles} />
            <Section
              title="왜 움직였을까?"
              aside={
                <span className="asof">
                  {detail.dataMode === 'DEMO' ? '예시 설명' : '근거 확인'}
                </span>
              }
            >
              <p className="prose">
                {analysis?.summary ||
                  '가격 변화만으로 원인을 확정할 수 없어요. 관련 공시와 뉴스가 확인되면 함께 살펴볼 수 있어요.'}
              </p>
              <button
                className="accent-button full"
                onClick={() => setTab('analysis')}
              >
                분석 자세히 보기 →
              </button>
            </Section>
          </>
        ) : (
          <>
            <div className="composition-note">
              구성비는 ETF가 어떤 자산에 얼마나 투자하는지 보여줘요. 확인하지
              못한 비중은 따로 남겨둬요.
            </div>
            <Section title="히트맵">
              <div className="chips">
                <button
                  className={!themeMode ? 'selected' : ''}
                  onClick={() => setThemeMode(false)}
                >
                  종목
                </button>
                <button
                  className={themeMode ? 'selected' : ''}
                  onClick={() => setThemeMode(true)}
                >
                  테마
                </button>
                <span className="chip-divider" />
                <button
                  className={!daily ? 'selected' : ''}
                  onClick={() => setDaily(false)}
                >
                  20일 흐름
                </button>
                <button
                  className={daily ? 'selected' : ''}
                  onClick={() => setDaily(true)}
                >
                  오늘 등락
                </button>
              </div>
              <p className="caption">
                면적: ETF 비중 · 색: {daily ? '일간' : '20거래일'} 수익률
              </p>
              <div className="treemap">
                {rows.map((row, idx) => (
                  <div
                    className="treemap-row"
                    key={idx}
                    style={{ flex: row.reduce((sum, h) => sum + h.weight, 0) }}
                  >
                    {row.map((h) => {
                      const value = daily ? h.dayReturn : h.return20
                      return (
                        <button
                          key={h.name}
                          onClick={() => setSheet('holdings')}
                          className={
                            value === null
                              ? 'unknown'
                              : value >= 0
                                ? 'positive'
                                : 'negative'
                          }
                          style={{ flex: h.weight }}
                        >
                          <span>{h.name}</span>
                          <strong>{(h.weight * 100).toFixed(2)}%</strong>
                          {value !== null && <small>{percent(value)}</small>}
                        </button>
                      )
                    })}
                  </div>
                ))}
              </div>
              <p className="caption">
                {detail.holdingsAsOf
                  ? `${detail.holdingsAsOf} 기준 · ${detail.dataMode === 'DEMO' ? '예시 구성비' : '공시 구성비'}`
                  : '구성 자료 없음'}
              </p>
            </Section>
            <Section
              title="구성 상태"
              aside={
                <select
                  aria-label="구성 정렬"
                  value={sort}
                  onChange={(e) => setSort(e.target.value)}
                >
                  <option value="weight">비중 순</option>
                  <option value="name">이름 순</option>
                </select>
              }
            >
              {[...holdings]
                .sort((a, b) =>
                  sort === 'weight'
                    ? b.weight - a.weight
                    : a.name.localeCompare(b.name, 'ko'),
                )
                .slice(0, 3)
                .map((h) => (
                  <div className="holding-row" key={h.name}>
                    <div>
                      <strong>{h.name}</strong>
                      <span className="caption">
                        {' '}
                        {(h.weight * 100).toFixed(2)}%
                      </span>
                      <p className="caption">
                        1일 {percent(h.dayReturn)} · 20일 {percent(h.return20)}
                      </p>
                    </div>
                  </div>
                ))}
              {!holdings.length && (
                <p className="muted">확인된 편입 내역이 없어요.</p>
              )}
              <button
                className="soft-button full"
                onClick={() => setSheet('holdings')}
              >
                전체 구성 보기
              </button>
            </Section>
            <Section title="기본 정보">
              <div className="metric-grid">
                {detail.fundamentals.map((f) => (
                  <div key={f.label}>
                    <small>{f.label}</small>
                    <strong>{f.value || '자료 없음'}</strong>
                  </div>
                ))}
              </div>
            </Section>
          </>
        )}
      </main>
      {sheet === 'analysis' && analysis && (
        <Sheet title="분석 자세히 보기" onClose={() => setSheet(null)}>
          <h2>{analysis.headline}</h2>
          <p className="prose">{analysis.summary}</p>
          {analysis.factors.map((f) => (
            <details key={f.kind} className="factor-detail" open>
              <summary>
                {f.label}{' '}
                <span className="caption">
                  {f.status === 'READY' ? '계산 자료 있음' : '자료 부족'}
                </span>
              </summary>
              <p>{f.explanation}</p>
              <dl>
                {f.metrics.map((m) => (
                  <div key={m.label}>
                    <dt>{m.label}</dt>
                    <dd>
                      {m.value === null
                        ? '자료 없음'
                        : `${Number(m.value).toLocaleString('ko-KR', { maximumFractionDigits: 2 })}${m.unit}`}
                    </dd>
                  </div>
                ))}
              </dl>
            </details>
          ))}
          <button
            className="soft-button full"
            onClick={() => setSheet('sources')}
          >
            출처 확인하기
          </button>
        </Sheet>
      )}
      {sheet === 'sources' && analysis && (
        <Sheet title="근거와 출처" onClose={() => setSheet(null)}>
          {analysis.sources.map((s) => (
            <article className="source" key={s.id}>
              <span className="caption">
                {s.publisher} · {s.publishedAt.slice(0, 10)}
              </span>
              <h3>{s.title}</h3>
              <p>{s.excerpt}</p>
              {s.url ? (
                <a href={s.url} target="_blank" rel="noopener noreferrer">
                  원문 보기 ↗
                </a>
              ) : (
                <span className="status-chip">실제 출처가 없는 예시</span>
              )}
            </article>
          ))}
        </Sheet>
      )}
      {sheet === 'holdings' && detail && (
        <Sheet title="전체 구성" onClose={() => setSheet(null)}>
          <p className="caption">
            {detail.dataMode === 'DEMO'
              ? '화면 검수용 예시 비중'
              : '확인된 구성비'}
          </p>
          {holdings.map((h) => (
            <div className="holding-row" key={h.name}>
              <strong>{h.name}</strong>
              <span>{(h.weight * 100).toFixed(2)}%</span>
            </div>
          ))}
          <div className="holding-row muted">
            <strong>미확인 구성</strong>
            <span>{(detail.residualWeight * 100).toFixed(2)}%</span>
          </div>
          <p className="caption">
            일부 구성만 알려져 있어도 이를 다시 100%로 늘리지 않아요.
          </p>
        </Sheet>
      )}
      {factor && (
        <Sheet title={`${factor.label} 기준`} onClose={() => setFactor(null)}>
          <div className="prose">
            <p>{factor.explanation}</p>
            <dl>
              {factor.metrics.map((m) => (
                <div key={m.label}>
                  <dt>{m.label}</dt>
                  <dd>
                    {m.value === null
                      ? '자료 없음'
                      : `${Number(m.value).toLocaleString('ko-KR', { maximumFractionDigits: 2 })}${m.unit}`}
                  </dd>
                </div>
              ))}
            </dl>
            <p className="caption">
              자료가 없는 항목은 중립이나 0점으로 취급하지 않아요.
            </p>
          </div>
        </Sheet>
      )}
    </>
  )
}
