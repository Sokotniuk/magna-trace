import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { ApiError, listStations, openCase } from './api'
import type { OpenedCase, Station } from './api'
import demoScope from './demo-scope.json'
import { apiLabel, isMockMode, sourceLabel } from './api-mode'
import CaseDetails from './CaseDetails'
export { FindingsTable } from './FindingsTable'

export default function App() {
  const [stations, setStations] = useState<Station[]>([])
  const [selectedStation, setSelectedStation] = useState('')
  const [loadingStations, setLoadingStations] = useState(true)
  const [opening, setOpening] = useState(false)
  const [activeCase, setActiveCase] = useState<OpenedCase | null>(null)
  const snapshot = activeCase?.data
  const [error, setError] = useState<ApiError | null>(null)
  const [reload, setReload] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    setLoadingStations(true)
    setStations([])
    setSelectedStation('')
    setActiveCase(null)
    setError(null)
    listStations(controller.signal).then((items) => {
      if (!controller.signal.aborted) setStations(items)
    }).catch((reason: unknown) => {
      if (!controller.signal.aborted) {
        setError(reason instanceof ApiError ? reason : new ApiError(`Could not reach the ${apiLabel}. Check the server and proxy.`))
      }
    }).finally(() => {
      if (!controller.signal.aborted) setLoadingStations(false)
    })
    return () => controller.abort()
  }, [reload])

  async function handleOpen(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!selectedStation || opening) return
    setOpening(true)
    setActiveCase(null)
    setError(null)
    try {
      setActiveCase(await openCase(selectedStation))
    } catch (reason: unknown) {
      setError(reason instanceof ApiError ? reason : new ApiError(`Could not reach the ${apiLabel}. No findings loaded.`))
    } finally {
      setOpening(false)
    }
  }

  return (
    <main className="dashboard">
      <header>
        <h1>MAGNA TRACE</h1>
        <h2>Diagnostic Dashboard</h2>
        <p className="synthetic-banner">{isMockMode
          ? 'SYNTHETIC ONLY — pinned B2 candidate fixtures. Backend integration pending.'
          : 'LIVE API mode — backend responses only. No mock fallback. Integration verification pending.'}</p>
      </header>

      <section aria-labelledby="station-heading">
        <h3 id="station-heading">Choose a station</h3>
        <form onSubmit={handleOpen} aria-busy={opening || loadingStations}>
          <label htmlFor="station">Station</label>
          <div className="station-controls">
            <select id="station" value={selectedStation} disabled={loadingStations || opening} onChange={(event) => {
              setSelectedStation(event.target.value)
              setActiveCase(null)
              setError(null)
            }}>
              <option value="">Select a station</option>
              {stations.map((station) => <option key={station.station_number} value={station.station_number}>{station.station_number}</option>)}
            </select>
            <button type="submit" disabled={!selectedStation || loadingStations || opening}>{opening ? 'Opening case…' : 'Open diagnostic case'}</button>
            <button type="button" className="secondary" disabled={loadingStations || opening} onClick={() => setReload((value) => value + 1)}>Reload stations</button>
          </div>
        </form>
        {isMockMode
          ? <p className="scope-note">SYNTHETIC replay scope: <code>{demoScope.from}</code> to <code>{demoScope.to}</code>. Source timezone unknown.</p>
          : <p className="scope-note">Live case scope: selected station; no time or serial filter supplied. Source timezone unknown.</p>}
        {loadingStations && <p role="status">Loading {sourceLabel} stations…</p>}
        {!loadingStations && !error && stations.length === 0 && <p role="status">No stations returned. No case has been opened.</p>}
      </section>

      {error && <section className="error-panel" role="alert" aria-labelledby="error-heading">
        <h3 id="error-heading">Request unsuccessful</h3>
        <p>{error.code && <strong>{error.code}: </strong>}{error.message}</p>
        {error.scope != null && <><p>Queried scope returned by API:</p><pre>{JSON.stringify(error.scope, null, 2)}</pre></>}
        <p>No findings are shown for this request.</p>
      </section>}

      {snapshot && <section aria-labelledby="findings-heading">
        <h3 id="findings-heading">{sourceLabel} findings — {snapshot.scope.station_number}</h3>
        <p>Observations retrieved at: <code>{snapshot.observations_retrieved_at}</code></p>
        <p className="scope-note">Range status, quality flags and raw fail code are independent. Code meanings are unknown; no quality certification is inferred. <code>null</code> denotes an absent API value.</p>
        <section className="warnings" aria-labelledby="warnings-heading">
          <h4 id="warnings-heading">Returned warnings</h4>
          {snapshot.warnings.length ? <ul>{snapshot.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul> : <p>No warnings returned.</p>}
          {snapshot.scope.coverage_warnings.length > 0 && <><h4>Scope coverage warnings</h4><ul>{snapshot.scope.coverage_warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul></>}
        </section>
        <CaseDetails caseId={activeCase!.case_id} snapshot={snapshot} />
      </section>}
    </main>
  )
}
