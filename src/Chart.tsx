import { useEffect, useRef, useState } from 'react'
import type { Candle } from './domain'
import { won } from './domain'

export default function Chart({ candles }: { candles: Candle[] }) {
  const ref = useRef<HTMLCanvasElement>(null)
  const [range, setRange] = useState(20)
  const [selected, setSelected] = useState<number | null>(null)
  const visible = candles.slice(-range)
  const current = visible[selected ?? visible.length - 1]
  useEffect(() => {
    const canvas = ref.current
    if (!canvas || !visible.length) return
    const draw = () => {
      const ctx = canvas.getContext('2d')!,
        width = canvas.clientWidth,
        height = 275,
        scale = window.devicePixelRatio || 1
      canvas.width = width * scale
      canvas.height = height * scale
      ctx.scale(scale, scale)
      const values = visible.flatMap((c) => [Number(c.low), Number(c.high)])
      const low = Math.min(...values) * 0.985,
        high = Math.max(...values) * 1.015
      const y = (n: number) =>
        height - 25 - ((n - low) / (high - low || 1)) * (height - 45)
      const plot = width - 53,
        dx = plot / visible.length
      ctx.font = '10px Pretendard Variable'
      ctx.fillStyle = '#8994a3'
      ctx.strokeStyle = '#edf0f4'
      ctx.lineWidth = 1
      for (let i = 0; i <= 3; i++) {
        const value = low + ((high - low) * i) / 3
        ctx.beginPath()
        ctx.moveTo(0, y(value))
        ctx.lineTo(plot, y(value))
        ctx.stroke()
        ctx.fillText((value / 10000).toFixed(2) + '만', plot + 7, y(value) + 3)
      }
      visible.forEach((c, i) => {
        const x = (i + 0.5) * dx,
          open = Number(c.open),
          close = Number(c.close)
        ctx.fillStyle = ctx.strokeStyle = close >= open ? '#f04452' : '#3678ff'
        ctx.beginPath()
        ctx.moveTo(x, y(Number(c.high)))
        ctx.lineTo(x, y(Number(c.low)))
        ctx.stroke()
        ctx.fillRect(
          x - Math.max(2, dx * 0.27),
          Math.min(y(open), y(close)),
          Math.max(3, dx * 0.54),
          Math.max(1, Math.abs(y(close) - y(open))),
        )
      })
      for (const [period, color] of [
        [5, '#8994a3'],
        [20, '#eaa343'],
      ] as const) {
        ctx.strokeStyle = color
        ctx.lineWidth = 1.5
        ctx.beginPath()
        let started = false
        visible.forEach((c, i) => {
          const original = candles.findIndex((x) => x.date === c.date)
          if (original < period - 1) return
          const value =
            candles
              .slice(original - period + 1, original + 1)
              .reduce((sum, x) => sum + Number(x.close), 0) / period
          if (!started) {
            ctx.moveTo((i + 0.5) * dx, y(value))
            started = true
          } else ctx.lineTo((i + 0.5) * dx, y(value))
        })
        ctx.stroke()
      }
      ctx.fillStyle = '#8994a3'
      for (const i of [
        0,
        Math.floor((visible.length - 1) / 2),
        visible.length - 1,
      ])
        ctx.fillText(
          visible[i].date.slice(5).replace('-', '.'),
          Math.min(plot - 28, (i + 0.15) * dx),
          height - 5,
        )
      if (selected !== null && visible[selected]) {
        ctx.strokeStyle = '#3d34e0'
        ctx.setLineDash([3, 3])
        ctx.beginPath()
        ctx.moveTo((selected + 0.5) * dx, 10)
        ctx.lineTo((selected + 0.5) * dx, height - 25)
        ctx.stroke()
        ctx.setLineDash([])
      }
    }
    const observer = new ResizeObserver(draw)
    observer.observe(canvas)
    draw()
    return () => observer.disconnect()
  }, [candles, range, selected])
  if (!candles.length)
    return (
      <div className="empty">
        <h3>차트 자료가 없어요</h3>
        <p>일봉을 불러오면 표시할 수 있어요.</p>
      </div>
    )
  return (
    <div className="chart">
      <div className="chart-legend">
        <strong>
          {current?.date} · {won(current?.close ?? null)}
        </strong>
        <small>
          <span className="ma5">━ MA5</span>{' '}
          <span className="ma20">━ MA20</span>
        </small>
      </div>
      <canvas
        ref={ref}
        tabIndex={0}
        role="img"
        aria-label="일봉 차트. 좌우 화살표로 날짜를 이동할 수 있습니다. 상세 수치는 아래 표에서도 확인할 수 있습니다."
        onKeyDown={(e) => {
          if (['ArrowLeft', 'ArrowRight'].includes(e.key)) {
            e.preventDefault()
            setSelected((i) =>
              Math.max(
                0,
                Math.min(
                  visible.length - 1,
                  (i ?? visible.length - 1) + (e.key === 'ArrowLeft' ? -1 : 1),
                ),
              ),
            )
          }
        }}
        onPointerMove={(e) => {
          const box = e.currentTarget.getBoundingClientRect()
          setSelected(
            Math.max(
              0,
              Math.min(
                visible.length - 1,
                Math.floor(
                  ((e.clientX - box.left) / (box.width - 53)) * visible.length,
                ),
              ),
            ),
          )
        }}
      />
      <div className="segmented">
        {[20, 60, 250].map((n) => (
          <button
            key={n}
            aria-pressed={range === n}
            className={range === n ? 'selected' : ''}
            onClick={() => {
              setRange(n)
              setSelected(null)
            }}
          >
            {n === 250 ? '전체' : `${n}거래일`}
          </button>
        ))}
      </div>
      <details>
        <summary className="caption">차트 수치 보기 · 수정주가 기준</summary>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>날짜</th>
                <th>시가</th>
                <th>고가</th>
                <th>저가</th>
                <th>종가</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((c) => (
                <tr key={c.date}>
                  <td>{c.date}</td>
                  {[c.open, c.high, c.low, c.close].map((v, i) => (
                    <td key={i}>{Number(v).toLocaleString('ko-KR')}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  )
}
