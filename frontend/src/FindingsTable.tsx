import type { Finding } from './api'

export function EvidenceReference({ id, onEvidence }: { id: string; onEvidence?: (id: string) => void }) {
  return onEvidence
    ? <button type="button" className="evidence-link" aria-controls="evidence-panel" onClick={() => onEvidence(id)}><code>{id}</code></button>
    : <code>{id}</code>
}

function RawValue({ value }: { value: string | null }) {
  return value === null
    ? <span className="null-value" title="API null; no recorded value">null</span>
    : <span className="raw-value">{value}</span>
}

export function FindingsTable({ findings, onEvidence }: { findings: Finding[]; onEvidence?: (id: string) => void }) {
  return (
    <div className="table-scroll" role="region" aria-label="SYNTHETIC findings table" tabIndex={0}>
      <table>
        <caption>SYNTHETIC findings — values and statuses exactly as returned</caption>
        <thead>
          <tr>
            {['Measurement / evidence references', 'Value (raw)', 'Unit', 'Lower bound (raw)', 'Upper bound (raw)', 'Deviation', 'Range status', 'Quality flags', 'Raw fail code'].map((heading) => (
              <th scope="col" key={heading}>{heading}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {findings.map((finding) => (
            <tr key={finding.evidence_id}>
              <th scope="row">
                {finding.measurement}
                <small>Observed: <EvidenceReference id={finding.evidence_id} onEvidence={onEvidence} /></small>
                <small>Calculated: <EvidenceReference id={finding.calculation_evidence_id} onEvidence={onEvidence} /></small>
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
