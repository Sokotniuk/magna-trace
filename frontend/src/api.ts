import demoScope from './demo-scope.json'
import { isMockMode } from './api-mode'

export type Station = { station_number: string; record_count: number }
export type Finding = {
  measurement: string
  raw_value: string | null
  raw_lower: string | null
  raw_upper: string | null
  deviation: string | null
  parsed_value: string | null
  unit: string | null
  range_status: 'ABOVE' | 'BELOW' | 'WITHIN_RECORDED_BOUNDS' | 'NOT_EVALUABLE'
  quality_flags: string[]
  raw_fail_code: string | null
  evidence_id: string
  calculation_evidence_id: string
}
export type Snapshot = {
  scope: { station_number: string; coverage_warnings: string[] }
  observations_retrieved_at: string
  findings: Finding[]
  warnings: string[]
  additional_evidence_ids: string[]
}
export type OpenedCase = { case_id: string; data: Snapshot }
export type Evidence = Record<string, unknown> & {
  evidence_id: string
  classification: 'OBSERVED' | 'CALCULATED' | 'TECHNICIAN_REPORTED'
}
export type Report = {
  evidence_id: string
  classification: 'TECHNICIAN_REPORTED'
  question_id: string
  answer_text: string
  reported_at: string
  attribution: string
  conflict_evidence_ids: string[]
}
type Hypothesis = {
  classification: 'HYPOTHESIS'
  description: string
  supporting_evidence_ids: string[]
  counterevidence_ids: string[]
  limitations: string[]
  distinguishing_evidence: string
}
export type Handover = {
  scope: Snapshot['scope']
  observations_retrieved_at: string
  observations: Finding[]
  additional_evidence_ids: string[]
  technician_reports: Report[]
  assessment: { label: 'UNDETERMINED'; hypotheses: Hypothesis[]; unknowns: string[] }
  open_questions: string[]
  gaps: string[]
  next_action: { kind: 'question' | 'data_check' | 'escalation'; text: string; basis_evidence_ids: string[]; question_id?: string }
}

export type Employee = { employee_id: string; username: string; name: string; role: string; shift: string }
export type SignedIn = { employee: Employee; company: string }

// Fired when the backend reports an ended session, so the sign-in screen can return (D34).
export const SIGNED_OUT_EVENT = 'trace:signed-out'
export function reportSignedOut(status: number, code: unknown) {
  if (!isMockMode && status === 401 && code === 'UNAUTHORIZED') window.dispatchEvent(new Event(SIGNED_OUT_EVENT))
}

export class ApiError extends Error {
  constructor(message: string, public code?: string, public scope?: unknown) {
    super(message)
  }
}

function object(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}
function strings(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === 'string')
}
function nullableString(value: unknown): value is string | null {
  return value === null || typeof value === 'string'
}

function validRawFields(value: unknown): boolean {
  if (!object(value)) return false
  // B2 requires these keys even when a recorded value is null.
  const required = [
    'MEASURE_VALUE', 'LOWER_LIMIT', 'UPPER_LIMIT', 'UNIT',
    'MEASURE_FAIL_CODE', 'station_number', 'serial_number', 'BOOK_STAMP',
  ]
  return required.every((key) => Object.hasOwn(value, key)) &&
    typeof value.station_number === 'string' && Object.values(value).every(nullableString)
}

function validFinding(finding: unknown): finding is Finding {
  return object(finding) &&
    ['measurement', 'evidence_id', 'calculation_evidence_id'].every((key) => typeof finding[key] === 'string') &&
    ['raw_value', 'raw_lower', 'raw_upper', 'parsed_value', 'deviation', 'unit', 'raw_fail_code'].every((key) => nullableString(finding[key])) &&
    typeof finding.range_status === 'string' &&
    ['ABOVE', 'BELOW', 'WITHIN_RECORDED_BOUNDS', 'NOT_EVALUABLE'].includes(finding.range_status) &&
    strings(finding.quality_flags)
}

async function request(path: string, init?: RequestInit) {
  const response = await fetch(path, init)
  const mockMarker = response.headers.get('X-Trace-Mock')
  if (isMockMode && mockMarker !== 'SYNTHETIC') {
    throw new ApiError('Expected a SYNTHETIC mock response. Check the local server and Vite proxy.')
  }
  if (!isMockMode && mockMarker !== null) {
    throw new ApiError('Live mode rejected a response marked as mock. Check the Vite proxy target. No data loaded for this request.')
  }
  let body: unknown
  try {
    body = await response.json()
  } catch {
    throw new ApiError(`HTTP ${response.status}: the ${isMockMode ? 'mock' : 'API'} returned a non-JSON response. No data loaded for this request.`)
  }
  if (!object(body)) throw new ApiError('Unexpected response format. No data loaded for this request.')
  if (!response.ok || body.status === 'error') {
    if (object(body.error)) reportSignedOut(response.status, body.error.code)
    if (object(body.error) && typeof body.error.code === 'string' && typeof body.error.message === 'string') {
      throw new ApiError(body.error.message, body.error.code, body.error.scope)
    }
    throw new ApiError(`HTTP ${response.status}: request failed. No data loaded for this request.`)
  }
  if (body.status !== 'ok' || body.error !== null || !object(body.data) ||
      typeof body.request_id !== 'string' || typeof body.retrieved_at !== 'string') {
    throw new ApiError('Unexpected response envelope. No data loaded for this request.')
  }
  return body
}

export async function listStations(signal?: AbortSignal): Promise<Station[]> {
  // Live mode asks for the B2 maximum (100): the backend default of 20 hid stations (23 exist).
  const body = await request(isMockMode ? '/api/v1/stations?q=SYNTHETIC&limit=20' : '/api/v1/stations?limit=100', { signal })
  if (body.case_id !== null || !object(body.data) || !Array.isArray(body.data.stations) ||
      !body.data.stations.every((station) => object(station) &&
        typeof station.station_number === 'string' && typeof station.record_count === 'number')) {
    throw new ApiError('Unexpected station response. No stations loaded.')
  }
  return body.data.stations as Station[]
}

export async function openCase(stationNumber: string): Promise<OpenedCase> {
  const body = await request('/api/v1/cases', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(isMockMode ? { station_number: stationNumber, ...demoScope } : { station_number: stationNumber }),
  })
  const snapshot = body.data
  if (!object(snapshot) || typeof body.case_id !== 'string' ||
      !object(snapshot.scope) || snapshot.scope.station_number !== stationNumber ||
      !strings(snapshot.scope.coverage_warnings) || !strings(snapshot.warnings) ||
      !strings(snapshot.additional_evidence_ids) ||
      typeof snapshot.observations_retrieved_at !== 'string' || !Array.isArray(snapshot.findings) ||
      !snapshot.findings.every(validFinding)) {
    throw new ApiError('Unexpected findings response. No findings loaded.')
  }
  // Display-only validation: never parse, round or recalculate measurement values.
  return body as OpenedCase
}

function validReport(value: unknown): value is Report {
  return object(value) && value.classification === 'TECHNICIAN_REPORTED' &&
    ['evidence_id', 'question_id', 'answer_text', 'reported_at', 'attribution'].every((key) => typeof value[key] === 'string') &&
    strings(value.conflict_evidence_ids)
}

export async function getEvidence(caseId: string, evidenceId: string, signal?: AbortSignal): Promise<Evidence> {
  const body = await request(`/api/v1/cases/${encodeURIComponent(caseId)}/evidence/${encodeURIComponent(evidenceId)}`, { signal })
  const data = body.data
  if (body.case_id !== caseId || !object(data) || data.evidence_id !== evidenceId) {
    throw new ApiError('Evidence response does not match the requested case and ID.')
  }
  const valid = data.classification === 'OBSERVED'
    ? typeof data.source_table === 'string' && typeof data.measurement === 'string' && object(data.scope) &&
      validRawFields(data.raw_fields) &&
      typeof data.row_ordinal === 'number' && typeof data.retrieved_at === 'string'
    : data.classification === 'CALCULATED'
      ? strings(data.input_evidence_ids) && typeof data.rule === 'string' && typeof data.retrieved_at === 'string' &&
        object(data.result) && nullableString(data.result.parsed_value) && nullableString(data.result.deviation) &&
        typeof data.result.range_status === 'string' &&
        ['ABOVE', 'BELOW', 'WITHIN_RECORDED_BOUNDS', 'NOT_EVALUABLE'].includes(data.result.range_status) && strings(data.result.quality_flags)
      : validReport(data)
  if (!valid) throw new ApiError('Unexpected evidence response. No evidence details loaded.')
  return data as Evidence
}

export async function getHandover(caseId: string, signal?: AbortSignal): Promise<Handover> {
  const body = await request(`/api/v1/cases/${encodeURIComponent(caseId)}/handover`, { signal })
  const data = body.data
  if (body.case_id !== caseId || !object(data) || !object(data.scope) ||
      typeof data.scope.station_number !== 'string' || !strings(data.scope.coverage_warnings) ||
      typeof data.observations_retrieved_at !== 'string' || !Array.isArray(data.observations) || !data.observations.every(validFinding) ||
      !strings(data.additional_evidence_ids) || !Array.isArray(data.technician_reports) ||
      !data.technician_reports.every(validReport) || !object(data.assessment) ||
      data.assessment.label !== 'UNDETERMINED' || !strings(data.assessment.unknowns) ||
      !Array.isArray(data.assessment.hypotheses) || !data.assessment.hypotheses.every((hypothesis) => object(hypothesis) &&
        hypothesis.classification === 'HYPOTHESIS' && typeof hypothesis.description === 'string' &&
        typeof hypothesis.distinguishing_evidence === 'string' && strings(hypothesis.limitations) &&
        strings(hypothesis.supporting_evidence_ids) && strings(hypothesis.counterevidence_ids)) ||
      !strings(data.open_questions) || !strings(data.gaps) || !object(data.next_action) ||
      !['question', 'data_check', 'escalation'].includes(data.next_action.kind as string) ||
      typeof data.next_action.text !== 'string' || !strings(data.next_action.basis_evidence_ids) ||
      (data.next_action.kind === 'question' && typeof data.next_action.question_id !== 'string')) {
    throw new ApiError('Unexpected handover response. No handover loaded.')
  }
  return data as Handover
}

function signedIn(body: Record<string, unknown>): SignedIn {
  const data = body.data
  if (!object(data) || typeof data.company !== 'string' || !object(data.employee) ||
      !['employee_id', 'username', 'name', 'role', 'shift'].every((key) => typeof (data.employee as Record<string, unknown>)[key] === 'string')) {
    throw new ApiError('Unexpected sign-in response.')
  }
  return data as SignedIn
}

// Session cookie is HttpOnly and set by the backend; the page never sees a token or key.
export async function getSession(signal?: AbortSignal): Promise<SignedIn | null> {
  const response = await fetch('/api/v1/auth/me', { signal })
  if (response.status === 401) return null
  const body = await response.json().catch(() => null)
  if (!response.ok || !object(body)) throw new ApiError(`HTTP ${response.status}: could not check the sign-in.`)
  return signedIn(body)
}

export async function getCompany(): Promise<string> {
  const body = await fetch('/api/v1/auth/info').then((response) => response.json()).catch(() => null)
  return object(body) && object(body.data) && typeof body.data.company === 'string' ? body.data.company : ''
}

export async function signIn(username: string, password: string): Promise<SignedIn> {
  const response = await fetch('/api/v1/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
  const body = await response.json().catch(() => null)
  if (!response.ok || !object(body) || body.status !== 'ok') {
    const message = object(body) && object(body.error) && typeof body.error.message === 'string'
      ? body.error.message : `HTTP ${response.status}: sign-in failed.`
    throw new ApiError(message, object(body) && object(body.error) ? String(body.error.code) : undefined)
  }
  return signedIn(body)
}

export async function signOut(): Promise<void> {
  await fetch('/api/v1/auth/logout', { method: 'POST' }).catch(() => undefined)
}
