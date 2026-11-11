import { useEffect, useId, useRef, useState } from 'react'
import type { KeyboardEvent } from 'react'
import type { Station } from './api'

// Animated station list. Opens on hover (pointer devices), on click/tap and from the keyboard,
// so it never depends on hover alone. The native <select id="station"> stays in App as the
// single source of the value; this component only calls onChange.

type Props = {
  stations: Station[]
  value: string
  disabled: boolean
  onChange: (value: string) => void
}

const canHover = () => typeof window !== 'undefined' && window.matchMedia?.('(hover: hover)').matches

export default function StationPicker({ stations, value, disabled, onChange }: Props) {
  const [open, setOpen] = useState(false)
  const root = useRef<HTMLDivElement>(null)
  const trigger = useRef<HTMLButtonElement>(null)
  const items = useRef<(HTMLButtonElement | null)[]>([])
  const closeTimer = useRef<number | undefined>(undefined)
  const listId = useId()

  useEffect(() => {
    if (!open) return
    const outside = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('pointerdown', outside)
    return () => document.removeEventListener('pointerdown', outside)
  }, [open])

  useEffect(() => { if (disabled) setOpen(false) }, [disabled])
  useEffect(() => () => window.clearTimeout(closeTimer.current), [])

  function show() {
    window.clearTimeout(closeTimer.current)
    if (!disabled && stations.length) setOpen(true)
  }

  function hideSoon() {
    window.clearTimeout(closeTimer.current)
    closeTimer.current = window.setTimeout(() => setOpen(false), 180)
  }

  function choose(station: string) {
    onChange(station)
    setOpen(false)
    trigger.current?.focus()
  }

  function focusItem(index: number) {
    const count = stations.length
    items.current[(index + count) % count]?.focus()
  }

  function onTriggerKey(event: KeyboardEvent<HTMLButtonElement>) {
    if (['ArrowDown', 'ArrowUp'].includes(event.key)) {
      event.preventDefault()
      show()
      const selected = stations.findIndex((s) => s.station_number === value)
      requestAnimationFrame(() => focusItem(event.key === 'ArrowUp' ? stations.length - 1 : Math.max(selected, 0)))
    } else if (event.key === 'Escape') {
      setOpen(false)
    }
  }

  function onItemKey(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    const columns = 2
    const moves: Record<string, number> = { ArrowDown: columns, ArrowUp: -columns, ArrowRight: 1, ArrowLeft: -1 }
    if (event.key in moves) {
      event.preventDefault()
      focusItem(index + moves[event.key])
    } else if (event.key === 'Home' || event.key === 'End') {
      event.preventDefault()
      focusItem(event.key === 'Home' ? 0 : stations.length - 1)
    } else if (event.key === 'Escape') {
      event.preventDefault()
      setOpen(false)
      trigger.current?.focus()
    } else if (event.key === 'Tab') {
      setOpen(false)
    }
  }

  const label = value || 'Select a station'

  return (
    <div ref={root} className={`picker${open ? ' open' : ''}`}
      onMouseEnter={() => { if (canHover()) show() }}
      onMouseLeave={() => { if (canHover()) hideSoon() }}>
      <button ref={trigger} id="station-picker" type="button" className="picker-trigger" disabled={disabled}
        aria-haspopup="listbox" aria-expanded={open} aria-controls={listId}
        onClick={() => (open ? setOpen(false) : show())} onKeyDown={onTriggerKey}>
        <span className={value ? 'picker-value' : 'picker-placeholder'}>{label}</span>
        <svg className="picker-chevron" viewBox="0 0 20 20" aria-hidden="true" focusable="false">
          <path d="M5.5 7.5 10 12l4.5-4.5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>
      <div className="picker-panel" id={listId} role="listbox" aria-label="Stations" aria-hidden={!open}>
        <p className="picker-caption">{stations.length} stations · measurement rows in Oracle</p>
        <div className="picker-grid">
          {stations.map((station, index) => (
            <button key={station.station_number} ref={(element) => { items.current[index] = element }}
              type="button" role="option" aria-selected={station.station_number === value}
              tabIndex={open ? 0 : -1} className="picker-option"
              style={{ ['--i' as string]: Math.min(index, 16) }}
              onClick={() => choose(station.station_number)} onKeyDown={(event) => onItemKey(event, index)}>
              <span className="picker-option-name">{station.station_number}</span>
              <span className="picker-option-count">{station.record_count}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
