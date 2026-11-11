import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { randomBytes } from 'node:crypto'
import { once } from 'node:events'
import { readFileSync, readdirSync } from 'node:fs'
import { createServer } from 'node:http'
import { resolve } from 'node:path'
import test from 'node:test'
import { createServer as createViteServer, resolveConfig } from 'vite'
import { browser } from './browser.mjs'

// Local protocol tests only: all success payloads remain the pinned SYNTHETIC
// examples. Removing the transport marker tests compatibility, not live Oracle.
const fixtures = JSON.parse(readFileSync(new URL('../mock/b2/examples.json', import.meta.url), 'utf8'))
const byName = new Map(fixtures.cases.map(item => [item.name, item]))

test('D4: explicit live mode displays backend errors without mock fallback', { timeout: 120000 }, async (t) => {
  const apiKey = randomBytes(32).toString('hex')
  const names = ['TRACE_API_KEY', 'TRACE_API_TARGET', 'VITE_TRACE_API_MODE']
  const previous = new Map(names.map(name => [name, process.env[name]]))
  t.after(() => {
    for (const [name, value] of previous) {
      if (value === undefined) delete process.env[name]
      else process.env[name] = value
    }
  })
  process.env.VITE_TRACE_API_MODE = 'invalid'
  await assert.rejects(resolveConfig({ configFile: resolve('vite.config.mjs') }, 'build'), /must be mock or live/)
  process.env.VITE_TRACE_API_MODE = 'live'
  process.env.TRACE_API_KEY = apiKey

  let fault = 'source'
  const seen = []
  const sourceError = structuredClone(byName.get('error_SOURCE_UNAVAILABLE').response.body)
  sourceError.case_id = null
  sourceError.error.scope = null
  sourceError.error.message = 'A2 station adapter is not connected'
  const upstream = createServer(async (req, res) => {
    let body = ''
    for await (const chunk of req) body += chunk
    seen.push({ url: req.url, method: req.method, body, authenticated: req.headers['x-api-key'] === apiKey })
    assert.equal(req.headers['x-api-key'] === apiKey, true, 'The proxy must add the server key')
    if (fault === 'reset') { req.socket.destroy(); return }
    if (fault === 'html') {
      res.writeHead(503, { 'Content-Type': 'text/html' })
      res.end('<html>SYNTHETIC local protocol fault</html>')
      return
    }
    const fixture = req.url === '/api/v1/stations?limit=100'
      ? byName.get('list_stations')
      : fixtures.cases.find(item => item.path === req.url && item.method === req.method)
    assert.ok(fixture, 'Only documented routes may be requested')
    const payload = structuredClone(fault === 'source' ? sourceError : fixture.response.body)
    if (fault === 'metadata') { delete payload.request_id; delete payload.retrieved_at }
    if (fault === 'raw-fields') payload.data.raw_fields = {}
    if (fault === 'decimal') payload.data.findings[0].deviation = 0.5
    if (fault === 'marked-mock') res.setHeader('X-Trace-Mock', 'SYNTHETIC')
    res.writeHead(fault === 'source' ? 503 : 200, { 'Content-Type': 'application/json' })
    res.end(JSON.stringify(payload))
  })
  upstream.listen(0, '127.0.0.1')
  await once(upstream, 'listening')
  t.after(() => new Promise(done => upstream.close(done)))
  process.env.TRACE_API_TARGET = `http://127.0.0.1:${upstream.address().port}`
  const vite = await createViteServer({ configFile: resolve('vite.config.mjs'), server: { host: '127.0.0.1', port: 0, strictPort: false } })
  t.after(() => vite.close())
  await vite.listen()
  const pageUrl = `http://127.0.0.1:${vite.httpServer.address().port}`
  const { command, context, evaluate, wait } = await browser(t)
  const alert = 'main > section[role="alert"]'
  const select = async () => {
    await wait(`document.querySelector('#station option[value="SYNTHETIC-STATION"]')`)
    await evaluate(`document.querySelector('#station').value = 'SYNTHETIC-STATION'; document.querySelector('#station').dispatchEvent(new Event('change', { bubbles: true }))`)
    await wait(`!document.querySelector('button[type="submit"]').disabled`)
  }
  const open = async () => {
    await evaluate(`document.querySelector('button[type="submit"]').click()`)
    await wait(`document.querySelectorAll('.case-details > .table-scroll tbody tr').length === 3`)
  }
  const expectError = async (selector, message) => {
    await wait(`document.querySelector(${JSON.stringify(selector)})?.textContent.includes(${JSON.stringify(message)})`)
    assert.equal(await evaluate(`document.body.textContent.includes('Expected a SYNTHETIC mock response')`), false)
  }

  await t.test('unmarked HTTP 503 exposes SOURCE_UNAVAILABLE and the A2 blocker', async () => {
    await command('browsingContext.navigate', { context, url: pageUrl, wait: 'complete' })
    await expectError(alert, 'SOURCE_UNAVAILABLE: A2 station adapter is not connected')
    assert.equal(await evaluate(`document.querySelectorAll('#station option').length`), 1)
    assert.equal(await evaluate(`document.querySelector('button[type="submit"]').disabled`), true)
    assert.equal(await evaluate(`document.querySelector('.case-details') === null`), true)
    assert.equal(await evaluate(`document.querySelector('.synthetic-banner').textContent.includes('LIVE API mode')`), true)
    assert.equal(seen[0].url, '/api/v1/stations?limit=100')
  })

  await t.test('unmarked B2 successes preserve values, live labels and station-only scope', async () => {
    fault = null
    await evaluate(`document.querySelector('button.secondary').click()`)
    await select()
    await open()
    assert.deepEqual(JSON.parse(seen.find(item => item.method === 'POST').body), { station_number: 'SYNTHETIC-STATION' })
    const finding = byName.get('open_case').response.body.data.findings[0]
    const cells = JSON.parse(await evaluate(`JSON.stringify([...document.querySelector('.case-details tbody tr').cells].map(cell => cell.textContent))`))
    assert.deepEqual(cells.slice(1, 7), [finding.raw_value, finding.unit, finding.raw_lower, finding.raw_upper, finding.deviation, finding.range_status])
    await evaluate(`document.querySelector('.evidence-link').click(); document.querySelector('#handover-panel > button').click()`)
    await wait(`document.querySelector('#evidence-json') && document.querySelector('#handover-json')`)
    assert.deepEqual(JSON.parse(await evaluate(`document.querySelector('#evidence-json').textContent`)), byName.get('get_evidence_1').response.body.data)
    assert.deepEqual(JSON.parse(await evaluate(`document.querySelector('#handover-json').textContent`)), byName.get('get_handover').response.body.data)
    for (const selector of ['#findings-heading', '.case-details caption', '#evidence-heading', '#handover-heading']) {
      assert.equal(await evaluate(`document.querySelector(${JSON.stringify(selector)}).textContent.startsWith('LIVE API')`), true)
    }
    assert.equal(await evaluate(`document.body.textContent.includes('pinned mock supplies only')`), false)
    assert.equal(await evaluate(`document.body.textContent.includes('SYNTHETIC replay scope')`), false)
    const count = await evaluate(`document.querySelectorAll('.case-details tbody tr')[1].textContent`)
    assert.ok(count.includes('1001') && count.includes('WITHIN_RECORDED_BOUNDS') && !/\b(PASS|FAIL)\b/.test(count))
  })

  await t.test('live detail and case errors clear stale successful data', async () => {
    fault = 'source'
    const retrievedAt = await evaluate(`document.querySelector('#findings-heading + p code').textContent`)
    for (const [button, errorPanel, oldData] of [
      ['.evidence-link', '#evidence-panel [role="alert"]', '#evidence-json'],
      ['#handover-panel > button', '#handover-panel [role="alert"]', '#handover-details'],
    ]) {
      await evaluate(`document.querySelector(${JSON.stringify(button)}).click()`)
      await expectError(errorPanel, sourceError.error.message)
      assert.equal(await evaluate(`document.querySelector(${JSON.stringify(oldData)}) === null`), true)
      assert.equal(await evaluate(`document.querySelector('#findings-heading + p code').textContent`), retrievedAt)
    }
    await evaluate(`document.querySelector('button[type="submit"]').click()`)
    await expectError(alert, sourceError.error.message)
    assert.equal(await evaluate(`document.querySelector('.case-details') === null`), true)
    await evaluate(`document.querySelector('button.secondary').click()`)
    await expectError(alert, sourceError.error.message)
    assert.equal(await evaluate(`document.querySelectorAll('#station option').length`), 1)
  })

  // Exercise the shared API path for every operation without changing the UI or
  // introducing additional success fixtures. All calls still cross Vite.
  for (const variant of ['metadata', 'marked-mock', 'html', 'reset']) {
    await t.test(`live ${variant} responses remain errors on all four read workflows`, async () => {
      fault = variant
      const caseId = byName.get('open_case').response.body.case_id
      const evidenceId = byName.get('get_evidence_1').response.body.data.evidence_id
      const outcomes = JSON.parse(await evaluate(`(async () => {
        const api = await import('/src/api.ts');
        const calls = [() => api.listStations(), () => api.openCase('SYNTHETIC-STATION'),
          () => api.getEvidence(${JSON.stringify(caseId)}, ${JSON.stringify(evidenceId)}), () => api.getHandover(${JSON.stringify(caseId)})];
        const results = [];
        for (const call of calls) { try { await call(); results.push('UNEXPECTED SUCCESS'); } catch (error) { results.push(error.message); } }
        return JSON.stringify(results);
      })()`))
      const expected = { metadata: /Unexpected response envelope/, 'marked-mock': /Live mode rejected/, html: /HTTP 503.*non-JSON/, reset: /HTTP 500.*non-JSON/ }[variant]
      for (const outcome of outcomes) assert.match(outcome, expected)
    })
  }
  await t.test('live validation keeps Decimal and OBSERVED source-field checks', async () => {
    fault = 'decimal'
    assert.match(await evaluate(`(async () => { const api = await import('/src/api.ts'); try { await api.openCase('SYNTHETIC-STATION'); return 'UNEXPECTED SUCCESS'; } catch (error) { return error.message; } })()`), /Unexpected findings/)
    fault = 'raw-fields'
    const observed = byName.get('get_evidence_1').response.body
    assert.match(await evaluate(`(async () => { const api = await import('/src/api.ts'); try { await api.getEvidence(${JSON.stringify(observed.case_id)}, ${JSON.stringify(observed.data.evidence_id)}); return 'UNEXPECTED SUCCESS'; } catch (error) { return error.message; } })()`), /Unexpected evidence/)
    assert.ok(seen.every(item => item.authenticated && !item.url.includes('q=SYNTHETIC')))
    assert.equal(await evaluate(`document.body.textContent.includes(${JSON.stringify(apiKey)})`), false)
  })

  await t.test('live build and served modules contain no server credential', async () => {
    execFileSync('npm', ['run', 'build'], { encoding: 'utf8', env: { ...process.env, VITE_TRACE_API_MODE: 'live', TRACE_API_KEY: apiKey } })
    for (const dir of ['src', 'dist']) {
      for (const entry of readdirSync(dir, { recursive: true, withFileTypes: true })) {
        if (!entry.isFile()) continue
        const text = readFileSync(resolve(entry.parentPath, entry.name), 'utf8')
        assert.ok(!text.includes(apiKey) && !text.includes('TRACE_API_KEY'), 'Server credential must stay out of sources and bundle')
      }
    }
    for (const path of ['/', '/src/App.tsx', '/src/api.ts', '/src/api-mode.ts']) {
      const text = await (await fetch(pageUrl + path)).text()
      assert.ok(!text.includes(apiKey) && !text.includes('TRACE_API_KEY'))
    }
  })
})
