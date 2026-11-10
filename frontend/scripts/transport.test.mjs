import assert from 'node:assert/strict'
import { randomBytes } from 'node:crypto'
import { once } from 'node:events'
import { readFileSync } from 'node:fs'
import { createServer, request as httpRequest } from 'node:http'
import { resolve } from 'node:path'
import test from 'node:test'
import { createServer as createViteServer } from 'vite'
import { createMockServer } from '../mock/server.mjs'
import { browser } from './browser.mjs'

const fixtures = JSON.parse(readFileSync(new URL('../mock/b2/examples.json', import.meta.url), 'utf8'))
const byName = new Map(fixtures.cases.map(fixture => [fixture.name, fixture]))
const scope = JSON.parse(readFileSync(new URL('../src/demo-scope.json', import.meta.url), 'utf8'))

async function listen(server) {
  server.listen(0, '127.0.0.1')
  await once(server, 'listening')
  return `http://127.0.0.1:${server.address().port}`
}

// Deliberately invalid transport/protocol inputs, NOT new B2 fixtures or behavior.
const faults = [
  { name: 'upstream connection reset', reset: true, message: /SYNTHETIC mock response/ },
  { name: 'HTTP 500 HTML without mock header', status: 500, text: '<html>SYNTHETIC transport fault</html>', noLabel: true, message: /SYNTHETIC mock response/ },
  { name: 'HTTP 500 HTML with mock header', status: 500, text: '<html>SYNTHETIC transport fault</html>', message: /HTTP 500.*non-JSON/ },
  { name: 'HTTP 200 truncated JSON', text: '{"status":', message: /HTTP 200.*non-JSON/ },
  { name: 'HTTP 200 JSON null', text: 'null', message: /Unexpected response format/ },
  { name: 'HTTP 200 invalid envelope status', corrupt: body => { body.status = 'SYNTHETIC-invalid-status' }, message: /Unexpected response envelope/ },
  { name: 'HTTP 200 missing operation data', corrupt: body => { body.data = {} }, message: /Unexpected|does not match/ },
  { name: 'HTTP 500 with success-shaped JSON', status: 500, corrupt: () => {}, message: /HTTP 500.*request failed/ },
  { name: 'HTTP 200 missing required envelope metadata', corrupt: body => { delete body.request_id; delete body.retrieved_at }, message: /Unexpected|Invalid|missing/i },
]

test('D6: transport and malformed responses never become fresh diagnostic data', { timeout: 180000 }, async (t) => {
  const apiKey = randomBytes(32).toString('hex')
  const mock = createMockServer({ apiKey })
  const mockTarget = await listen(mock)
  t.after(() => new Promise(done => mock.close(done)))
  let fault = null
  let injected = 0
  // A transparent local relay keeps the original mock and pinned fixtures intact.
  const relay = createServer((req, res) => {
    if (fault && new URL(req.url, mockTarget).pathname === new URL(fault.fixture.path, mockTarget).pathname) {
      injected++
      req.resume()
      if (fault.reset) { req.socket.destroy(); return }
      const headers = { 'Content-Type': fault.text?.startsWith('<') ? 'text/html' : 'application/json' }
      if (!fault.noLabel) headers['X-Trace-Mock'] = 'SYNTHETIC'
      const body = structuredClone(fault.fixture.response.body)
      fault.corrupt?.(body)
      res.writeHead(fault.status || 200, headers)
      res.end(fault.text ?? JSON.stringify(body))
      return
    }
    const upstream = httpRequest(new URL(req.url, mockTarget), { method: req.method, headers: req.headers }, reply => {
      res.writeHead(reply.statusCode, reply.headers)
      reply.pipe(res)
    })
    upstream.on('error', () => res.destroy())
    req.pipe(upstream)
  })
  const relayTarget = await listen(relay)
  t.after(() => new Promise(done => relay.close(done)))
  const previousKey = process.env.TRACE_API_KEY
  const previousTarget = process.env.TRACE_API_TARGET
  process.env.TRACE_API_KEY = apiKey
  process.env.TRACE_API_TARGET = relayTarget
  t.after(() => {
    if (previousKey === undefined) delete process.env.TRACE_API_KEY
    else process.env.TRACE_API_KEY = previousKey
    if (previousTarget === undefined) delete process.env.TRACE_API_TARGET
    else process.env.TRACE_API_TARGET = previousTarget
  })
  const vite = await createViteServer({ configFile: resolve('vite.config.mjs'), server: { host: '127.0.0.1', port: 0, strictPort: true } })
  t.after(() => vite.close())
  await vite.listen()
  const pageUrl = `http://127.0.0.1:${vite.httpServer.address().port}`
  const { command, context, evaluate, wait } = await browser(t)
  const rows = () => evaluate(`JSON.stringify([...document.querySelectorAll('.case-details > .table-scroll tbody tr')].map(row => row.textContent))`)
  const observedAt = () => evaluate(`document.querySelector('section[aria-labelledby="findings-heading"] > p code')?.textContent`)
  const open = byName.get('open_case')
  const observed = byName.get('get_evidence_1')
  const calculated = byName.get('get_evidence_2')
  const handover = byName.get('get_handover')
  const operations = [
    { name: 'stations', fixture: byName.get('list_stations'), button: 'button.secondary', busy: 'form[aria-busy]', alert: 'main > section[role="alert"]' },
    { name: 'open case', fixture: open, button: 'button[type="submit"]', busy: 'form[aria-busy]', alert: 'main > section[role="alert"]' },
    { name: 'evidence', fixture: observed, button: '.case-details > .table-scroll .evidence-link', busy: '#evidence-panel', alert: '#evidence-panel [role="alert"]' },
    { name: 'handover', fixture: handover, button: '#handover-panel > button', busy: '#handover-panel', alert: '#handover-panel [role="alert"]' },
  ]

  async function seed() {
    fault = null
    await command('browsingContext.navigate', { context, url: pageUrl, wait: 'complete' })
    await wait(`document.querySelector('#station option[value="SYNTHETIC-STATION"]')`)
    await evaluate(`document.querySelector('#station').value = 'SYNTHETIC-STATION'; document.querySelector('#station').dispatchEvent(new Event('change', { bubbles: true }))`)
    await wait(`!document.querySelector('button[type="submit"]').disabled`)
    await evaluate(`document.querySelector('button[type="submit"]').click()`)
    await wait(`document.querySelectorAll('.case-details > .table-scroll tbody tr').length === 3`)
    const answer = byName.get('record_answer')
    assert.equal(await evaluate(`(async () => (await fetch(${JSON.stringify(answer.path)}, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: ${JSON.stringify(JSON.stringify(answer.request.body))} })).status)()`), 200)
    await evaluate(`document.querySelector('.case-details > .table-scroll .evidence-link').click(); document.querySelector('#handover-panel > button').click()`)
    await wait(`document.querySelector('#evidence-json') && document.querySelector('#handover-json')`)
    assert.deepEqual(JSON.parse(await evaluate(`document.querySelector('#evidence-json').textContent`)), observed.response.body.data)
    assert.deepEqual(JSON.parse(await evaluate(`document.querySelector('#handover-json').textContent`)), handover.response.body.data)
  }

  async function verifyFailure(operation, variant) {
    await seed()
    const oldRows = await rows()
    const oldRetrievedAt = await observedAt()
    fault = { ...variant, fixture: operation.fixture }
    const before = injected
    await evaluate(`document.querySelector(${JSON.stringify(operation.button)}).click()`)
    await wait(`document.querySelector(${JSON.stringify(operation.busy)})?.getAttribute('aria-busy') === 'false'`)
    assert.ok(injected > before, 'The intended negative response must actually reach the browser')
    const message = await evaluate(`document.querySelector(${JSON.stringify(operation.alert)})?.textContent || ''`)
    const visible = await evaluate(`JSON.stringify({
      stationOptions: document.querySelectorAll('#station option').length,
      caseVisible: !!document.querySelector('.case-details'),
      evidenceVisible: !!document.querySelector('#evidence-json'),
      handoverVisible: !!document.querySelector('#handover-details')
    })`)
    assert.ok(message.length > 0, `Malformed/failed requests must display a clear error, not a successful view; actual visibility: ${visible}`)
    assert.match(message, variant.message)
    if (operation.name === 'stations') {
      assert.equal(await evaluate(`document.querySelectorAll('#station option').length`), 1)
      assert.equal(await evaluate(`document.querySelector('button[type="submit"]').disabled`), true)
    }
    if (['stations', 'open case'].includes(operation.name)) {
      assert.equal(await evaluate(`document.querySelector('.case-details') === null`), true, 'Failed case/list requests must not retain diagnostic views')
      assert.equal(await evaluate(`document.querySelectorAll('tbody tr').length`), 0)
    } else {
      const selector = operation.name === 'evidence' ? '#evidence-json' : '#handover-details'
      assert.equal(await evaluate(`document.querySelector(${JSON.stringify(selector)}) === null`), true, 'A failed detail refresh must remove its old successful data')
      assert.equal(await rows(), oldRows, 'An error must not create or alter findings')
      assert.equal(await observedAt(), oldRetrievedAt, 'Earlier observations must retain their source retrieval time')
    }
    assert.equal(await evaluate(`document.body.textContent.includes(${JSON.stringify(apiKey)})`), false)
    fault = null
  }

  for (const operation of operations) {
    for (const variant of faults) {
      await t.test(`${operation.name}: ${variant.name}`, async () => {
        try { await verifyFailure(operation, variant) }
        finally { fault = null }
      })
    }
  }
  const decimalCases = [
    { operation: operations[1], corrupt: body => { body.data.findings[0].deviation = 0.5 } },
    { operation: { ...operations[2], fixture: calculated, button: '.case-details > .table-scroll tbody tr:first-child small:last-child .evidence-link' }, corrupt: body => { body.data.result.deviation = 0.5 } },
    { operation: operations[3], corrupt: body => { body.data.observations[0].deviation = 0.5 } },
  ]
  // Fixture-derived values are never recalculated.
  for (const { operation, corrupt } of decimalCases) {
    await t.test(`${operation.name}: numeric Decimal corruption`, async () => {
      try { await verifyFailure(operation, { corrupt, message: /Unexpected/ }) }
      finally { fault = null }
    })
  }
  await t.test('observed evidence: missing required raw source fields', async () => {
    try { await verifyFailure(operations[2], { corrupt: body => { body.data.raw_fields = {} }, message: /Unexpected/ }) }
    finally { fault = null }
  })

  await t.test('real browser connection loss: handover, evidence, case and stations', async () => {
    await seed()
    const oldRows = await rows()
    const oldRetrievedAt = await observedAt()
    await vite.close()
    for (const operation of [operations[3], operations[2], operations[1], operations[0]]) {
      await evaluate(`document.querySelector(${JSON.stringify(operation.button)}).click()`)
      await wait(`document.querySelector(${JSON.stringify(operation.alert)})?.textContent.includes('Could not reach the mock API')`)
      if (operation.name === 'handover') assert.equal(await evaluate(`document.querySelector('#handover-details') === null`), true)
      if (operation.name === 'evidence') assert.equal(await evaluate(`document.querySelector('#evidence-json') === null`), true)
      if (['evidence', 'handover'].includes(operation.name)) {
        assert.equal(await rows(), oldRows)
        assert.equal(await observedAt(), oldRetrievedAt)
      } else assert.equal(await evaluate(`document.querySelector('.case-details') === null`), true)
    }
    assert.equal(await evaluate(`document.querySelectorAll('#station option').length`), 1)
    assert.equal(await evaluate(`document.querySelector('button[type="submit"]').disabled`), true)
  })
})
