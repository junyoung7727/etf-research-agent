import { useEffect, useRef, type ReactNode } from 'react'
import { percent, won, type Instrument } from './domain'

export function Icon({ name, size = 22 }: { name: string; size?: number }) {
  return (
    <img
      className="icon"
      src={`/figma/${name}.svg`}
      width={size}
      height={size}
      alt=""
    />
  )
}
export function FundIcon({ instrument }: { instrument: Instrument }) {
  return (
    <span className="fund-icon" style={{ backgroundColor: instrument.color }}>
      <Icon name={`fund-${instrument.icon}`} size={20} />
    </span>
  )
}
export function Change({ value }: { value: string | number | null }) {
  return (
    <span
      className={
        value === null
          ? 'muted'
          : Number(value) > 0
            ? 'up'
            : Number(value) < 0
              ? 'down'
              : 'muted'
      }
    >
      {percent(value)}
    </span>
  )
}
export function FundRow({
  instrument,
  onOpen,
  action,
}: {
  instrument: Instrument
  onOpen: () => void
  action?: ReactNode
}) {
  return (
    <div className="fund-row">
      <button className="fund-main" onClick={onOpen}>
        <FundIcon instrument={instrument} />
        <span className="fund-copy">
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
        </span>
      </button>
      {action || <span className="status-chip">판단 보류</span>}
    </div>
  )
}
export function Empty({
  title,
  children,
}: {
  title: string
  children?: ReactNode
}) {
  return (
    <div className="empty">
      <p className="empty-mark">—</p>
      <h3>{title}</h3>
      {children}
    </div>
  )
}
export function Sheet({
  title,
  onClose,
  children,
}: {
  title: string
  onClose: () => void
  children: ReactNode
}) {
  const ref = useRef<HTMLDialogElement>(null)
  useEffect(() => {
    const el = ref.current!
    el.showModal()
    return () => el.close()
  }, [])
  return (
    <dialog
      ref={ref}
      className="sheet"
      onCancel={onClose}
      onClick={(e) => {
        if (e.target === ref.current) onClose()
      }}
    >
      <div className="sheet-inner">
        <div className="sheet-handle" />
        <header className="sheet-header">
          <h2>{title}</h2>
          <button className="close-button" aria-label="닫기" onClick={onClose}>
            ×
          </button>
        </header>
        {children}
      </div>
    </dialog>
  )
}
export function Section({
  title,
  children,
  aside,
}: {
  title: string
  children: ReactNode
  aside?: ReactNode
}) {
  return (
    <section className="section">
      <div className="section-heading">
        <h2>{title}</h2>
        {aside}
      </div>
      {children}
    </section>
  )
}
