import { useState } from 'react'
import { FundIcon, Icon } from './ui'
import type { Instrument } from './domain'

export const themes = [
  'AI·반도체',
  '방산',
  '바이오',
  '친환경',
  '원자재',
  '국내주식',
  '배당·인프라',
  '채권',
]
export default function Onboarding({
  instruments,
  onFinish,
}: {
  instruments: Instrument[]
  onFinish: (themes: string[], items: string[]) => void
}) {
  const [step, setStep] = useState(0)
  const [selected, setSelected] = useState<string[]>([])
  const [items, setItems] = useState<string[]>([])
  const [query, setQuery] = useState('')
  const toggle = (id: string) =>
    setItems((old) =>
      old.includes(id) ? old.filter((i) => i !== id) : [...old, id],
    )
  return (
    <div className="onboarding">
      <header className="onboarding-nav">
        {step > 0 ? (
          <button
            className="icon-button"
            aria-label="이전 단계"
            onClick={() => setStep(step - 1)}
          >
            <Icon name="back" />
          </button>
        ) : (
          <span className="wordmark">
            EDGE<span>AI</span>
          </span>
        )}
        <button className="text-button" onClick={() => onFinish([], [])}>
          건너뛰기
        </button>
      </header>
      {step < 3 ? (
        <>
          <div className={`intro-art intro-${step}`}>
            {step === 0 && (
              <>
                <div className="news-cloud">
                  <span>뉴스</span>
                  <span>기업 공시</span>
                  <span>시장 지표</span>
                  <span>ETF 구성</span>
                  <span>금리·환율</span>
                  <span>실적 발표</span>
                </div>
                <div className="connector">↓</div>
                <div className="reader-pill">
                  <span className="ai-dot" />
                  EDGE AI <small>근거를 모아 설명해요</small>
                </div>
              </>
            )}
            {step === 1 && (
              <div className="intro-factor-card">
                <span className="eyebrow">하나의 숫자보다, 다섯 가지 근거</span>
                <h2>
                  내 ETF의 움직임을
                  <br />
                  여러 방향에서 읽어요.
                </h2>
                <div className="factor-preview">
                  {['이슈', '차트', '매크로', '밸류', '수급'].map((t) => (
                    <span key={t}>{t}</span>
                  ))}
                </div>
                <p>
                  자료가 부족하면
                  <br />
                  <strong>판단을 보류해요.</strong>
                </p>
              </div>
            )}
            {step === 2 && (
              <div className="intro-watch-card">
                <span className="eyebrow">나만의 관심 목록</span>
                {instruments.slice(0, 3).map((i) => (
                  <div className="intro-fund" key={i.id}>
                    <FundIcon instrument={i} />
                    <strong>{i.name}</strong>
                    <span className="purple">관심</span>
                  </div>
                ))}
              </div>
            )}
          </div>
          <div className="intro-copy">
            <h1>
              {[
                '흩어진 정보를\n이해할 수 있는 근거로',
                '오르내린 이유를\n하나씩 살펴보세요',
                '관심 있는 ETF만\n가까이 모아두세요',
              ][step]
                .split('\n')
                .map((t, i) => (
                  <span key={i}>
                    {t}
                    <br />
                  </span>
                ))}
            </h1>
            <p>
              {[
                '뉴스와 공시, 시장 데이터를 연결해\n내 ETF를 이해하는 데 필요한 근거를 정리해요.',
                '차트와 구성, 이슈의 기준일을 함께 확인해요.\n알 수 없는 것은 알 수 없다고 표시해요.',
                '테마를 고르고 ETF를 담으면\n나만의 브리핑을 시작할 수 있어요.',
              ][step]
                .split('\n')
                .map((t, i) => (
                  <span key={i}>
                    {t}
                    <br />
                  </span>
                ))}
            </p>
            <div className="step-dots" aria-label={`${step + 1}/3 단계`}>
              {[0, 1, 2].map((i) => (
                <span key={i} className={i === step ? 'active' : ''} />
              ))}
            </div>
          </div>
        </>
      ) : step === 3 ? (
        <div className="onboarding-select">
          <h1>관심 있는 테마를 골라주세요</h1>
          <p className="muted">고른 테마의 ETF를 먼저 보여드려요.</p>
          <h3>
            산업 <small className="muted">무엇이 성장하나</small>
          </h3>
          <div className="theme-grid">
            {themes.map((t, i) => (
              <button
                aria-pressed={selected.includes(t)}
                className={
                  selected.includes(t)
                    ? 'theme-choice selected'
                    : 'theme-choice'
                }
                key={t}
                onClick={() =>
                  setSelected((old) =>
                    old.includes(t) ? old.filter((x) => x !== t) : [...old, t],
                  )
                }
              >
                <img src={`/figma/theme-${i}.png`} alt="" />
                <span>{t}</span>
              </button>
            ))}
          </div>
        </div>
      ) : (
        <div className="onboarding-select">
          <h1>함께 살펴볼 ETF를 담아주세요</h1>
          <p className="muted">관심 목록은 이 브라우저에 저장돼요.</p>
          <label className="search-field">
            <Icon name="search" />
            <input
              aria-label="ETF 검색"
              placeholder="ETF 이름 또는 종목코드"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </label>
          {[...instruments]
            .sort(
              (a, b) =>
                Number(selected.includes(b.theme)) -
                Number(selected.includes(a.theme)),
            )
            .filter((i) =>
              `${i.name} ${i.id}`.toLowerCase().includes(query.toLowerCase()),
            )
            .map((i) => (
              <button
                className="select-fund"
                aria-pressed={items.includes(i.id)}
                key={i.id}
                onClick={() => toggle(i.id)}
              >
                <FundIcon instrument={i} />
                <span>
                  <strong>{i.name}</strong>
                  <small>
                    {i.id} · {i.theme}
                  </small>
                </span>
                <span
                  className={`check ${items.includes(i.id) ? 'checked' : ''}`}
                >
                  {items.includes(i.id) ? '✓' : '+'}
                </span>
              </button>
            ))}
        </div>
      )}
      <footer className="onboarding-footer">
        <button
          className="primary-button"
          onClick={() =>
            step === 4 ? onFinish(selected, items) : setStep(step + 1)
          }
        >
          {step === 4
            ? `${items.length ? items.length + '개 ETF와 ' : ''}시작하기`
            : step === 3
              ? 'ETF 고르기'
              : '다음'}
        </button>
      </footer>
    </div>
  )
}
