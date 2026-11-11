import type { Finding } from './api'
import { sourceLabel } from './api-mode'

// Table cells show a visually shortened ID so the findings fit one screen. The DOM text, tooltip,
// accessible name and drill-down keep the full backend-issued ID; only CSS hides the middle.
function IdText({ id, short }: { id: string; short: boolean }) {
  // The hidden middle is the case ID, which is printed in full right above the table.
  const match = short ? /^(E-)([0-9a-f]{32})(-\d+)$/.exec(id) : null
  return match
    ? <code><span className="id-head">{match[1]}</span><span className="id-mid">{match[2]}</span>{match[3]}</code>
    : <code>{id}</code>
}

export function EvidenceReference({ id, onEvidence, short = false }: { id: string; onEvidence?: (id: string) => void; short?: boolean }) {
  return onEvidence
    ? <button type="button" className="evidence-link" aria-controls="evidence-panel" title={id} aria-label={`Evidence ${id}`} onClick={() => onEvidence(id)}><IdText id={id} short={short} /></button>
    : <span title={id}><IdText id={id} short={short} /></span>
}

function RawValue({ value }: { value: string | null }) {
  return value === null
    ? <span className="null-value" title="API null; no recorded value">null</span>
    : <span className="raw-value">{value}</span>
}

export function FindingsTable({ findings, onEvidence }: { findings: Finding[]; onEvidence?: (id: string) => void }) {
  return (
    <div className="table-scroll" role="region" aria-label={`${sourceLabel} findings table`} tabIndex={0}>
      <table>
        <caption>{sourceLabel} findings — raw values, bounds and codes exactly as returned</caption>
        <thead>
          <tr>
            {['Measurement · evidence', 'Value', 'Unit', 'Lower', 'Upper', 'Deviation', 'Range status', 'Quality flags', 'Fail code'].map((heading) => (
              <th scope="col" key={heading}>{heading}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {findings.map((finding) => (
            <tr key={finding.evidence_id}>
              <th scope="row">
                {finding.measurement}
                <small className="ref">obs <EvidenceReference id={finding.evidence_id} onEvidence={onEvidence} short /></small>
                <small className="ref"> · calc <EvidenceReference id={finding.calculation_evidence_id} onEvidence={onEvidence} short /></small>
              </th>
              <td><RawValue value={finding.raw_value} /></td>
              <td><RawValue value={finding.unit} /></td>
              <td><RawValue value={finding.raw_lower} /></td>
              <td><RawValue value={finding.raw_upper} /></td>
              <td><RawValue value={finding.deviation} /></td>
              <td><span className={`range-status range-${finding.range_status}`}>{finding.range_status}</span></td>
              <td>{finding.quality_flags.length
                ? <ul className="flags">{finding.quality_flags.map((flag) => <li key={flag}>{flag}</li>)}</ul>
                : <span className="muted">No flags returned</span>}</td>
              <td><RawValue value={finding.raw_fail_code} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
