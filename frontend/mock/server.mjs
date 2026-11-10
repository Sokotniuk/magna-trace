import { readFileSync } from 'node:fs'
import { createServer } from 'node:http'
import { isDeepStrictEqual } from 'node:util'
import { pathToFileURL } from 'node:url'

const fixtures = JSON.parse(readFileSync(new URL('./b2/examples.json', import.meta.url), 'utf8'))
const byName = new Map(fixtures.cases.map((fixture) => [fixture.name, fixture]))
const open = byName.get('open_case')
const answer = byName.get('record_answer')
const report = byName.get('get_evidence_7')

// This replays one SYNTHETIC fixture case; it is not a diagnostic backend.
export function createMockServer({ apiKey, scenario } = {}) {
  if (!apiKey) throw new Error('TRACE_API_KEY is required by the SYNTHETIC mock server')
  const forced = scenario ? byName.get(scenario) : null
  if (scenario && (!forced || !scenario.startsWith('error_') || scenario === 'error_NOT_COMPARABLE')) {
    throw new Error('TRACE_MOCK_SCENARIO must name a pinned P0 error fixture')
  }
  let opened = false
  let answered = false

  return createServer(async (req, res) => {
    res.setHeader('X-Trace-Mock', 'SYNTHETIC')
    res.setHeader('Cache-Control', 'no-store')

    const send = (fixture) => {
      res.writeHead(fixture.http_status, { 'Content-Type': 'application/json; charset=utf-8' })
      // No numeric conversion, generated IDs, extra envelope fields or computations.
      res.end(JSON.stringify(fixture.response.body))
    }
    const unsupported = () => {
      // Deliberately outside B2: do not invent an API envelope for unspecified inputs.
      res.writeHead(501, { 'Content-Type': 'text/plain; charset=utf-8' })
      res.end('SYNTHETIC fixture replay only: no pinned response for this request. See frontend/README.md.\n')
    }

    if (req.headers['x-api-key'] !== apiKey) return send(byName.get('error_UNAUTHORIZED'))
    const url = new URL(req.url, 'http://127.0.0.1')
    const path = url.pathname
    if (forced && req.method === forced.method && path === new URL(forced.path, url).pathname) {
      return send(forced)
    }

    let body
    if (req.method === 'POST') {
      try {
        const chunks = []
        for await (const chunk of req) chunks.push(chunk)
        body = JSON.parse(Buffer.concat(chunks).toString('utf8'))
      } catch {
        return send(byName.get('error_INVALID_SCOPE'))
      }
    }

    if (req.method === 'POST' && path === open.path && !url.search) {
      if (!isDeepStrictEqual(body, open.request.body)) return unsupported()
      opened = true
      answered = false
      return send(open)
    }

    if (req.method === 'GET' && path === '/api/v1/stations') {
      const entries = [...url.searchParams]
      if (entries.some(([key]) => !['q', 'limit'].includes(key))) return unsupported()
      if (new Set(entries.map(([key]) => key)).size !== entries.length) return unsupported()
      const q = url.searchParams.get('q')
      const limit = url.searchParams.get('limit')
      if ((q === null || q === 'SYNTHETIC') && (limit === null || limit === '20')) {
        return send(byName.get('list_stations'))
      }
      return unsupported()
    }

    const fixture = fixtures.cases.find((item) => item.method === req.method && item.path === req.url)
    if (!fixture) return unsupported()
    if (fixture.name === 'error_CASE_NOT_FOUND_OR_EXPIRED') return send(fixture)
    if (!opened) return unsupported()
    if (fixture.name === 'record_answer') {
      if (answered || body?.question_id !== answer.request.body.question_id) {
        return send(byName.get('error_stale_question'))
      }
      if (!isDeepStrictEqual(body, answer.request.body)) return unsupported()
      answered = true
      return send(answer)
    }
    if (fixture.name === 'get_handover' || fixture === report) {
      // B2 supplies only post-answer handover/report fixtures.
      if (!answered) return unsupported()
    }
    if (req.method === 'GET') return send(fixture)
    return unsupported()
  })
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const port = Number(process.env.TRACE_MOCK_PORT || 8001)
  if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error('Invalid TRACE_MOCK_PORT')
  const server = createMockServer({
    apiKey: process.env.TRACE_API_KEY,
    scenario: process.env.TRACE_MOCK_SCENARIO,
  })
  server.on('error', (error) => {
    console.error(`SYNTHETIC mock server error: ${error.code || 'startup failed'}`)
    process.exitCode = 1
  })
  server.listen(port, '127.0.0.1', () => {
    console.log(`SYNTHETIC B2 candidate fixture server: http://127.0.0.1:${port}`)
  })
}
