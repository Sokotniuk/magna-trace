import demoScope from './demo-scope.json'

export type Station = { station_number: string; record_count: number }
export type Finding = {
  measurement: string
  raw_value: string | null
  raw_lower: string | null
  raw_upper: string | null
  deviation: string | null
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

async function request(path: string, init?: RequestInit) {
  const response = await fetch(path, init)
  // D2 is deliberately limited to the local SYNTHETIC mock, not a live backend.
  if (response.headers.get('X-Trace-Mock') !== 'SYNTHETIC') {
    throw new ApiError('Expected a SYNTHETIC mock response. Check the local server and Vite proxy.')
  }
  let body: unknown
  try {
    body = await response.json()
  } catch {
    throw new ApiError(`HTTP ${response.status}: the mock returned a non-JSON response. No findings loaded.`)
  }
  if (!object(body)) throw new ApiError('Unexpected response format. No findings loaded.')
  if (!response.ok || body.status === 'error') {
    if (object(body.error) && typeof body.error.code === 'string' && typeof body.error.message === 'string') {
      throw new ApiError(body.error.message, body.error.code, body.error.scope)
    }
    throw new ApiError(`HTTP ${response.status}: request failed. No findings loaded.`)
  }
  if (body.status !== 'ok' || body.error !== null || !object(body.data)) {
    throw new ApiError('Unexpected response envelope. No findings loaded.')
  }
  return body
}

export async function listStations(signal?: AbortSignal): Promise<Station[]> {
  const body = await request('/api/v1/stations?q=SYNTHETIC&limit=20', { signal })
  if (body.case_id !== null || !object(body.data) || !Array.isArray(body.data.stations) ||
      !body.data.stations.every((station) => object(station) &&
        typeof station.station_number === 'string' && typeof station.record_count === 'number')) {
    throw new ApiError('Unexpected station response. No stations loaded.')
  }
  return body.data.stations as Station[]
}

export async function openCase(stationNumber: string): Promise<Snapshot> {
  const body = await request('/api/v1/cases', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ station_number: stationNumber, ...demoScope }),
  })
  const snapshot = body.data
  if (!object(snapshot) || typeof body.case_id !== 'string' ||
      !object(snapshot.scope) || snapshot.scope.station_number !== stationNumber ||
      !strings(snapshot.scope.coverage_warnings) || !strings(snapshot.warnings) ||
      typeof snapshot.observations_retrieved_at !== 'string' || !Array.isArray(snapshot.findings) ||
      !snapshot.findings.every((finding) => object(finding) &&
        ['measurement', 'evidence_id', 'calculation_evidence_id'].every((key) => typeof finding[key] === 'string') &&
        ['raw_value', 'raw_lower', 'raw_upper', 'deviation', 'unit', 'raw_fail_code'].every((key) => nullableString(finding[key])) &&
        typeof finding.range_status === 'string' &&
        ['ABOVE', 'BELOW', 'WITHIN_RECORDED_BOUNDS', 'NOT_EVALUABLE'].includes(finding.range_status) &&
        strings(finding.quality_flags))) {
    throw new ApiError('Unexpected findings response. No findings loaded.')
  }
  // Display-only validation: never parse, round or recalculate measurement values.
  return snapshot as Snapshot
}
