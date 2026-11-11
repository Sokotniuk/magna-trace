import { useEffect, useState } from 'react'
import { getStationOverview } from './api'
import type { Station, StationOverview } from './api'

// Shown before a case is opened. Steps are a static guide to the P0 journey; tiles list the
// stations as the API returned them. The outline uses the backend's out-of-range counts
// (GET /stations/overview, D37) as they are: nothing is derived or ranked in TypeScript.
const STEPS = [
  { title: 'Open a case', text: 'Pick a station. The backend reads its rows from Oracle.' },
  { title: 'Read findings', text: 'Values, bounds and statuses, each with an evidence ID.' },
  { title: 'Answer one question', text: 'In the chat. Your answer is stored as technician evidence.' },
  { title: 'Hand over', text: 'Summary for the next shift with open questions and gaps.' },
]

export default function Overview({ stations, selected, disabled, onOpen }: {
  stations: Station[]
  selected: string
  disabled: boolean
  onOpen: (station: string) => void
}) {
  const [counts, setCounts] = useState<Map<string, StationOverview> | null>(null)
  const [countsError, setCountsError] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    getStationOverview(controller.signal)
      .then((items) => setCounts(new Map(items.map((item) => [item.station_number, item]))))
      .catch(() => { if (!controller.signal.aborted) setCountsError(true) })
    return () => controller.abort()
  }, [])

  const flagged = counts ? [...counts.values()].filter((item) => item.above + item.below > 0).length : 0

  return (
    <section className="overview" aria-labelledby="overview-heading">
      <h3 id="overview-heading">How a diagnosis runs</h3>
      <ol className="journey">
        {STEPS.map((step, index) => (
          <li key={step.title} className={index === 0 ? 'current' : undefined}>
            <span className="journey-index" aria-hidden="true">{index + 1}</span>
            <span className="journey-title">{step.title}</span>
            <span className="journey-text">{step.text}</span>
          </li>
        ))}
      </ol>

      <h3 id="tiles-heading">Stations <span className="tiles-count">{stations.length} returned · click to open a case</span></h3>
      <p className="tiles-legend">
        {counts
          ? <><span className="legend-swatch" aria-hidden="true" /> {flagged} {flagged === 1 ? 'station has' : 'stations have'} recorded values outside their limits (outlined; “5 out” = five values). A count, not a diagnosis.</>
          : countsError ? 'Out-of-range counts are unavailable; stations are listed without them.' : 'Counting recorded range statuses…'}
      </p>
      {stations.length > 0 && <ul className="station-tiles" aria-labelledby="tiles-heading">
        {stations.map((station, index) => {
          const count = counts?.get(station.station_number)
          const out = count ? count.above + count.below : 0
          return (
            <li key={station.station_number} style={{ ['--i' as string]: index }}>
              <button type="button" className={`station-tile${out > 0 ? ' has-breach' : ''}`} disabled={disabled}
                aria-pressed={station.station_number === selected}
                aria-label={`Open a case for ${station.station_number}, ${station.record_count} records${out > 0 ? `, ${out} values outside recorded limits` : ''}`}
                onClick={() => onOpen(station.station_number)}>
                <span className="tile-number">{station.station_number}</span>
                <span className="tile-count">{station.record_count} records</span>
                {out > 0 && <span className="tile-breach" title={`${out} values outside recorded limits`}>{out} out</span>}
              </button>
            </li>
          )
        })}
      </ul>}
    </section>
  )
}
