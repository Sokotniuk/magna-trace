import { useState } from 'react'
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

// Text for the chat, built only from values the backend returned. The full calculation evidence ID
// comes first: pasted into the chat it opens that evidence and continues this case (D38).
function chatText(f: Finding): string {
  const unit = f.unit ? ` ${f.unit}` : ''
  return `${f.calculation_evidence_id} — where does this deviation come from? ${f.measurement} ${f.raw_value ?? 'null'}${unit} is ` +
    `${f.range_status} (recorded limits ${f.raw_lower ?? 'null'} – ${f.raw_upper ?? 'null'}, deviation ${f.deviation ?? 'null'}).`
}

function CopyForChat({ finding }: { finding: Finding }) {
  const [copied, setCopied] = useState<'idle' | 'ok' | 'failed'>('idle')
  async function copy() {
    const text = chatText(finding)
    // Also place the text in the chat field, so the demo never depends on clipboard permissions.
    window.dispatchEvent(new CustomEvent('trace:prefill-chat', { detail: text }))
    try {
      await navigator.clipboard.writeText(text)
      setCopied('ok')
    } catch {
      // Some embedded browsers block the async clipboard API; the selection-based copy still works.
      const area = document.createElement('textarea')
      area.value = text
      area.setAttribute('readonly', '')
      area.style.position = 'fixed'
      area.style.opacity = '0'
      document.body.appendChild(area)
      area.select()
      const ok = document.execCommand('copy')
      area.remove()
      setCopied(ok ? 'ok' : 'failed')
    }
    window.setTimeout(() => setCopied('idle'), 2000)
  }
  return <button type="button" className="copy-chat" onClick={() => void copy()}
    aria-label={`Copy ${finding.measurement} with evidence ${finding.calculation_evidence_id} for the chat`}>
    {copied === 'ok' ? 'Copied ✓ · in chat' : copied === 'failed' ? 'In chat field ✓' : 'Copy for chat'}
  </button>
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
            <tr key={finding.evidence_id} className={finding.range_status === 'ABOVE' || finding.range_status === 'BELOW' ? 'row-breach' : undefined}>
              <th scope="row">
                {finding.measurement}
                <small className="ref">obs <EvidenceReference id={finding.evidence_id} onEvidence={onEvidence} short /></small>
                <small className="ref"> · calc <EvidenceReference id={finding.calculation_evidence_id} onEvidence={onEvidence} short /></small>
                {(finding.range_status === 'ABOVE' || finding.range_status === 'BELOW') && <CopyForChat finding={finding} />}
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
