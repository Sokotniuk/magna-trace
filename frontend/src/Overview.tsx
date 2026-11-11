import type { Station } from './api'

// Shown before a case is opened. Steps are a static guide to the P0 journey; tiles list the
// stations exactly as the API returned them (number and record count). No health colour or
// ranking is derived here: the dashboard holds no diagnostic logic.
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
      {stations.length > 0 && <ul className="station-tiles" aria-labelledby="tiles-heading">
        {stations.map((station, index) => (
          <li key={station.station_number} style={{ ['--i' as string]: index }}>
            <button type="button" className="station-tile" disabled={disabled}
              aria-pressed={station.station_number === selected}
              aria-label={`Open a case for ${station.station_number}, ${station.record_count} records`}
              onClick={() => onOpen(station.station_number)}>
              <span className="tile-number">{station.station_number}</span>
              <span className="tile-count">{station.record_count} records</span>
            </button>
          </li>
        ))}
      </ul>}
    </section>
  )
}
