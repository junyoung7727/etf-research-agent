import { useRef, useState } from 'react'
import type { Instrument } from './domain'
import { FundRow } from './ui'

export default function WatchRow({
  instrument,
  editing,
  index,
  count,
  onOpen,
  onMove,
  onMoveTo,
  onRemove,
}: {
  instrument: Instrument
  editing: boolean
  index: number
  count: number
  onOpen: () => void
  onMove: (delta: number) => void
  onMoveTo: (target: string) => void
  onRemove: () => void
}) {
  const dragging = useRef(false)
  const target = useRef<string | null>(null)
  const [active, setActive] = useState(false)
  const finish = () => {
    dragging.current = false
    target.current = null
    setActive(false)
  }
  return (
    <div data-etf-id={instrument.id} className={active ? 'dragging-row' : ''}>
      <FundRow
        instrument={instrument}
        onOpen={onOpen}
        action={
          editing ? (
            <div className="edit-actions">
              <button
                aria-label={`${instrument.name} 위로`}
                disabled={index === 0}
                onClick={() => onMove(-1)}
              >
                ↑
              </button>
              <button
                aria-label={`${instrument.name} 아래로`}
                disabled={index === count - 1}
                onClick={() => onMove(1)}
              >
                ↓
              </button>
              <button aria-label={`${instrument.name} 제거`} onClick={onRemove}>
                ×
              </button>
              <button
                className="drag-handle"
                aria-label={`${instrument.name} 끌어서 순서 이동`}
                onPointerDown={(event) => {
                  event.currentTarget.setPointerCapture(event.pointerId)
                  dragging.current = true
                  target.current = instrument.id
                  setActive(true)
                }}
                onPointerMove={(event) => {
                  if (dragging.current)
                    target.current =
                      document
                        .elementFromPoint(event.clientX, event.clientY)
                        ?.closest('[data-etf-id]')
                        ?.getAttribute('data-etf-id') || null
                }}
                onPointerUp={() => {
                  if (target.current && target.current !== instrument.id)
                    onMoveTo(target.current)
                  finish()
                }}
                onPointerCancel={finish}
              >
                이동
              </button>
            </div>
          ) : undefined
        }
      />
    </div>
  )
}
