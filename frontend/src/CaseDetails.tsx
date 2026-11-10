import { useEffect, useRef, useState } from 'react'
import { ApiError, getEvidence, getHandover } from './api'
import type { Evidence, Handover, Snapshot } from './api'
import { EvidenceReference, FindingsTable } from './FindingsTable'

function RequestError({ error }: { error: ApiError }) {
  return <div className="error-panel" role="alert">
    <p>{error.code && <strong>{error.code}: </strong>}{error.message}</p>
    {error.scope != null && <pre>{JSON.stringify(error.scope, null, 2)}</pre>}
    <p>No substitute data is shown for this request.</p>
  </div>
}

function StringList({ items }: { items: string[] }) {
  return items.length ? <ul>{items.map((item, index) => <li className="returned-text" key={index}>{item}</li>)}</ul> : <p>None returned.</p>
}

function EvidenceList({ ids, onEvidence }: { ids: string[]; onEvidence: (id: string) => void }) {
  return ids.length ? <ul>{ids.map((id) => <li key={id}><EvidenceReference id={id} onEvidence={onEvidence} /></li>)}</ul> : <p>No references returned.</p>
}

export function EvidenceDetails({ evidence, onEvidence }: { evidence: Evidence; onEvidence: (id: string) => void }) {
  return <article className="evidence-details">
    <h4>{evidence.classification}</h4>
    <p>Evidence ID: <code>{evidence.evidence_id}</code></p>
    <p>Immutable captured SYNTHETIC evidence; source timezone is not inferred. A row ordinal is a snapshot locator, not proof of a unique database key.</p>
    <pre className="returned-json" id="evidence-json">{JSON.stringify(evidence, null, 2)}</pre>
    {evidence.classification === 'CALCULATED' && <>
      <h4>Calculation inputs</h4>
      <EvidenceList ids={evidence.input_evidence_ids as string[]} onEvidence={onEvidence} />
    </>}
    {evidence.classification === 'TECHNICIAN_REPORTED' && <>
      <h4>Conflicting observations</h4>
      <EvidenceList ids={evidence.conflict_evidence_ids as string[]} onEvidence={onEvidence} />
    </>}
  </article>
}

export function HandoverDetails({ handover, onEvidence }: { handover: Handover; onEvidence: (id: string) => void }) {
  return <article id="handover-details">
    <h4>SYNTHETIC handover — {handover.scope.station_number}</h4>
    <p>Observations retrieved at: <code>{handover.observations_retrieved_at}</code></p>
    <h4>Queried scope and coverage</h4>
    <pre className="returned-json">{JSON.stringify(handover.scope, null, 2)}</pre>
    <h4>Observations</h4>
    {handover.observations.length ? <FindingsTable findings={handover.observations} onEvidence={onEvidence} /> : <p>No observations returned.</p>}
    <h4>Additional evidence</h4>
    <EvidenceList ids={handover.additional_evidence_ids} onEvidence={onEvidence} />
    <h4>Technician reports</h4>
    {handover.technician_reports.length ? handover.technician_reports.map((report) => <section key={report.evidence_id}>
      <EvidenceReference id={report.evidence_id} onEvidence={onEvidence} />
      <pre className="returned-json">{JSON.stringify(report, null, 2)}</pre>
    </section>) : <p>No technician reports returned.</p>}
    <h4>Assessment: {handover.assessment.label}</h4>
    <p>Hypotheses are unverified; they do not establish a physical cause.</p>
    {handover.assessment.hypotheses.map((hypothesis, index) => <section key={index}>
      <h5>{hypothesis.classification}</h5>
      <p className="returned-text">{hypothesis.description}</p>
      <h5>Supporting evidence</h5><EvidenceList ids={hypothesis.supporting_evidence_ids} onEvidence={onEvidence} />
      <h5>Counterevidence</h5><EvidenceList ids={hypothesis.counterevidence_ids} onEvidence={onEvidence} />
      <h5>Limitations</h5><StringList items={hypothesis.limitations} />
      <h5>Distinguishing evidence</h5><p className="returned-text">{hypothesis.distinguishing_evidence}</p>
    </section>)}
    <h4>Unknowns</h4><StringList items={handover.assessment.unknowns} />
    <h4>Open questions</h4><StringList items={handover.open_questions} />
    <h4>Gaps and warnings returned in gaps</h4><StringList items={handover.gaps} />
    <h4>Scope coverage warnings</h4><StringList items={handover.scope.coverage_warnings} />
    <h4>Next action: {handover.next_action.kind}</h4>
    <p className="returned-text">{handover.next_action.text}</p>
    {handover.next_action.question_id !== undefined && <p>Question ID: <code>{handover.next_action.question_id}</code></p>}
    <EvidenceList ids={handover.next_action.basis_evidence_ids} onEvidence={onEvidence} />
    <details><summary>Exact SYNTHETIC handover data</summary><pre className="returned-json" id="handover-json">{JSON.stringify(handover, null, 2)}</pre></details>
  </article>
}

export default function CaseDetails({ caseId, snapshot }: { caseId: string; snapshot: Snapshot }) {
  const [evidenceId, setEvidenceId] = useState('')
  const [evidence, setEvidence] = useState<Evidence | null>(null)
  const [evidenceError, setEvidenceError] = useState<ApiError | null>(null)
  const [loadingEvidence, setLoadingEvidence] = useState(false)
  const [handover, setHandover] = useState<Handover | null>(null)
  const [handoverError, setHandoverError] = useState<ApiError | null>(null)
  const [loadingHandover, setLoadingHandover] = useState(false)
  const evidenceRequest = useRef<AbortController | null>(null)
  const handoverRequest = useRef<AbortController | null>(null)
  useEffect(() => () => {
    evidenceRequest.current?.abort()
    handoverRequest.current?.abort()
  }, [])

  async function loadEvidence(id: string) {
    evidenceRequest.current?.abort()
    const controller = new AbortController()
    evidenceRequest.current = controller
    setEvidenceId(id)
    setEvidence(null)
    setEvidenceError(null)
    setLoadingEvidence(true)
    try {
      const result = await getEvidence(caseId, id, controller.signal)
      if (!controller.signal.aborted) setEvidence(result)
    } catch (reason: unknown) {
      if (!controller.signal.aborted) setEvidenceError(reason instanceof ApiError ? reason : new ApiError('Could not reach the mock API. No evidence details loaded.'))
    } finally {
      if (!controller.signal.aborted) setLoadingEvidence(false)
    }
  }

  async function loadHandover() {
    handoverRequest.current?.abort()
    const controller = new AbortController()
    handoverRequest.current = controller
    setHandover(null)
    setHandoverError(null)
    setLoadingHandover(true)
    try {
      const result = await getHandover(caseId, controller.signal)
      if (!controller.signal.aborted) setHandover(result)
    } catch (reason: unknown) {
      if (!controller.signal.aborted) setHandoverError(reason instanceof ApiError ? reason : new ApiError('Could not reach the mock API. No handover loaded.'))
    } finally {
      if (!controller.signal.aborted) setLoadingHandover(false)
    }
  }

  return <div className="case-details">
    <p>Active SYNTHETIC case: <code>{caseId}</code></p>
    {snapshot.findings.length ? <FindingsTable findings={snapshot.findings} onEvidence={loadEvidence} /> : <p>No findings returned for this scope.</p>}
    {snapshot.additional_evidence_ids.length > 0 && <><h4>Additional evidence</h4><EvidenceList ids={snapshot.additional_evidence_ids} onEvidence={loadEvidence} /></>}
    <section id="evidence-panel" aria-labelledby="evidence-heading" aria-busy={loadingEvidence}>
      <h3 id="evidence-heading">SYNTHETIC evidence details</h3>
      <form onSubmit={(event) => { event.preventDefault(); if (evidenceId) void loadEvidence(evidenceId) }}>
        <label htmlFor="evidence-id">Evidence ID in the active case</label>
        <div className="station-controls">
          <input id="evidence-id" value={evidenceId} onChange={(event) => setEvidenceId(event.target.value)} />
          <button type="submit" disabled={!evidenceId || loadingEvidence}>Load evidence</button>
        </div>
      </form>
      {loadingEvidence && <p role="status">Loading SYNTHETIC evidence…</p>}
      {evidenceError && <RequestError error={evidenceError} />}
      {evidence && <EvidenceDetails evidence={evidence} onEvidence={loadEvidence} />}
    </section>
    <section id="handover-panel" aria-labelledby="handover-heading" aria-busy={loadingHandover}>
      <h3 id="handover-heading">SYNTHETIC handover</h3>
      <button type="button" disabled={loadingHandover} onClick={() => void loadHandover()}>Load handover</button>
      <p className="scope-note">The pinned mock supplies only a post-answer handover. If no answer has been recorded, its replay-limit error is shown; no summary is fabricated.</p>
      {loadingHandover && <p role="status">Loading SYNTHETIC handover…</p>}
      {handoverError && <RequestError error={handoverError} />}
      {handover && <HandoverDetails handover={handover} onEvidence={loadEvidence} />}
    </section>
  </div>
}
