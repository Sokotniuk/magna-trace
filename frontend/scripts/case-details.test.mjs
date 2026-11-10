import assert from 'node:assert/strict'
import { randomBytes } from 'node:crypto'
import { once } from 'node:events'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import test from 'node:test'
import { createServer as createViteServer } from 'vite'
import { createMockServer } from '../mock/server.mjs'
import { browser } from './browser.mjs'

const fixtures = JSON.parse(readFileSync(new URL('../mock/b2/examples.json', import.meta.url), 'utf8'))
const byName = new Map(fixtures.cases.map((fixture) => [fixture.name, fixture]))

test('D3 browser: case-local evidence and exact B2 handover', { timeout: 120000 }, async (t) => {
  const apiKey = randomBytes(32).toString('hex')
  const traffic = []
  const mock = createMockServer({ apiKey })
  mock.on('request', (req) => traffic.push({ method: req.method, path: req.url }))
  mock.listen(0, '127.0.0.1')
  await once(mock, 'listening')
  t.after(() => new Promise(done => mock.close(done)))
  const oldKey = process.env.TRACE_API_KEY
  const oldTarget = process.env.TRACE_API_TARGET
  process.env.TRACE_API_KEY = apiKey
  process.env.TRACE_API_TARGET = `http://127.0.0.1:${mock.address().port}`
  t.after(() => {
    if (oldKey === undefined) delete process.env.TRACE_API_KEY
    else process.env.TRACE_API_KEY = oldKey
    if (oldTarget === undefined) delete process.env.TRACE_API_TARGET
    else process.env.TRACE_API_TARGET = oldTarget
  })
  const vite = await createViteServer({ configFile: resolve('vite.config.mjs'), server: { host: '127.0.0.1', port: 0, strictPort: false } })
  t.after(() => vite.close())
  await vite.listen()
  const { command, context, evaluate, wait } = await browser(t)
  await command('browsingContext.navigate', { context, url: `http://127.0.0.1:${vite.httpServer.address().port}`, wait: 'complete' })
  await wait(`document.querySelector('#station option[value="SYNTHETIC-STATION"]')`)
  const selectAndOpen = async () => {
    await evaluate(`document.querySelector('#station').value = 'SYNTHETIC-STATION'; document.querySelector('#station').dispatchEvent(new Event('change', { bubbles: true }))`)
    await wait(`!document.querySelector('button[type="submit"]').disabled`)
    await evaluate(`document.querySelector('button[type="submit"]').click()`)
    await wait(`document.querySelectorAll('.case-details > .table-scroll tbody tr').length === 3`)
  }
  await selectAndOpen()
  const clickReference = (id) => evaluate(`[...document.querySelectorAll('.evidence-link')].find(button => button.textContent === ${JSON.stringify(id)}).click()`)
  const jsonAt = async (selector) => JSON.parse(await evaluate(`document.querySelector(${JSON.stringify(selector)}).textContent`))
  for (let i = 1; i <= 6; i++) {
    const fixture = byName.get(`get_evidence_${i}`)
    const id = fixture.response.body.data.evidence_id
    await clickReference(id)
    await wait(`document.querySelector('#evidence-json')?.textContent.includes(${JSON.stringify(id)}) && !document.querySelector('#evidence-panel').matches('[aria-busy="true"]')`)
    assert.deepEqual(await jsonAt('#evidence-json'), fixture.response.body.data)
    assert.equal(await evaluate(`document.querySelector('.evidence-details h4').textContent`), fixture.response.body.data.classification)
    assert.ok(traffic.some(req => req.method === 'GET' && req.path === fixture.path))
  }
  // A calculated result links back to its captured observation.
  const calc = byName.get('get_evidence_2').response.body.data
  await clickReference(calc.evidence_id)
  await wait(`document.querySelector('#evidence-panel .evidence-link')`)
  await evaluate(`document.querySelector('#evidence-panel .evidence-link').click()`)
  await wait(`document.querySelector('.evidence-details h4')?.textContent === 'OBSERVED'`)
  assert.deepEqual(await jsonAt('#evidence-json'), byName.get('get_evidence_1').response.body.data)

  for (const name of ['error_EVIDENCE_NOT_FOUND', 'error_EVIDENCE_NOT_IN_CASE']) {
    const fixture = byName.get(name)
    const id = fixture.request.body.evidence_id
    await evaluate(`Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(document.querySelector('#evidence-id'), ${JSON.stringify(id)}); document.querySelector('#evidence-id').dispatchEvent(new Event('input', { bubbles: true }))`)
    await wait(`!document.querySelector('#evidence-panel button[type="submit"]').disabled`)
    await evaluate(`document.querySelector('#evidence-panel button[type="submit"]').click()`)
    await wait(`document.querySelector('#evidence-panel [role="alert"]')?.textContent.includes(${JSON.stringify(fixture.response.body.error.code)})`)
    assert.equal(await evaluate(`document.querySelector('#evidence-json') === null`), true)
    assert.equal(await evaluate(`document.querySelector('#evidence-panel [role="alert"]').textContent.includes(${JSON.stringify(fixture.response.body.error.message)})`), true)
    assert.ok(traffic.some(req => req.method === 'GET' && req.path === fixture.path))
  }

  // The unmodified fixture server intentionally has no pre-answer handover.
  await evaluate(`document.querySelector('#handover-panel > button').click()`)
  await wait(`document.querySelector('#handover-panel [role="alert"]')`)
  assert.equal(await evaluate(`document.querySelector('#handover-panel [role="alert"]').textContent.includes('HTTP 501')`), true)
  assert.equal(await evaluate(`document.querySelector('#handover-details') === null`), true)
  assert.ok(!traffic.some(req => req.method === 'POST' && req.path.endsWith('/answers')))

  // Test setup only: use the existing exact B2 answer fixture, not a D3 UI feature.
  const answer = byName.get('record_answer')
  assert.equal(await evaluate(`(async () => (await fetch(${JSON.stringify(answer.path)}, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: ${JSON.stringify(JSON.stringify(answer.request.body))} })).status)()`), 200)
  await evaluate(`document.querySelector('#handover-panel > button').click()`)
  await wait(`document.querySelector('#handover-json')`)
  const handover = byName.get('get_handover')
  assert.deepEqual(await jsonAt('#handover-json'), handover.response.body.data)
  assert.ok(traffic.some(req => req.method === 'GET' && req.path === handover.path))
  const handoverText = await evaluate(`document.querySelector('#handover-details').textContent`)
  assert.ok(handoverText.includes('Assessment: UNDETERMINED'))
  for (const text of [...handover.response.body.data.assessment.unknowns, ...handover.response.body.data.gaps,
    ...handover.response.body.data.assessment.hypotheses.flatMap(item => item.limitations), handover.response.body.data.next_action.text]) assert.ok(handoverText.includes(text))
  const report = byName.get('get_evidence_7')
  await clickReference(report.response.body.data.evidence_id)
  await wait(`document.querySelector('.evidence-details h4')?.textContent === 'TECHNICIAN_REPORTED'`)
  assert.deepEqual(await jsonAt('#evidence-json'), report.response.body.data)
  // Handover observation and next-action references are also resolvable.
  await evaluate(`document.querySelector('#handover-details .evidence-link').click()`)
  await wait(`document.querySelector('.evidence-details h4')?.textContent === 'OBSERVED'`)

  // A failed handover refresh must remove its previously displayed data.
  const originalFetchSetup = `window.d3OriginalFetch = window.fetch; window.fetch = (url, init) => window.d3OriginalFetch(typeof url === 'string' && url.endsWith('/handover') ? ${JSON.stringify(byName.get('error_CASE_NOT_FOUND_OR_EXPIRED').path)} : url, init)`
  await evaluate(originalFetchSetup)
  await evaluate(`document.querySelector('#handover-panel > button').click()`)
  await wait(`document.querySelector('#handover-panel [role="alert"]')?.textContent.includes('CASE_NOT_FOUND_OR_EXPIRED')`)
  assert.equal(await evaluate(`document.querySelector('#handover-json') === null`), true)
  await evaluate(`window.fetch = window.d3OriginalFetch`)

  assert.equal(await evaluate(`document.body.textContent.includes(${JSON.stringify(apiKey)})`), false)
  assert.ok(!traffic.some(req => req.path.includes('/comparisons')))
  // Changing/reopening the case clears all old details, even with reused mock IDs.
  await evaluate(`document.querySelector('button.secondary').click()`)
  await wait(`!document.querySelector('#station').disabled`)
  assert.equal(await evaluate(`document.querySelector('#evidence-panel') === null`), true)
  await selectAndOpen()
  assert.equal(await evaluate(`document.querySelector('#evidence-json') === null && document.querySelector('#handover-json') === null`), true)

  // A late request must not restore details after a case switch.
  const observation = byName.get('get_evidence_1')
  await evaluate(`window.fetch = async (url, init) => { const response = await window.d3OriginalFetch(url, init); if (typeof url === 'string' && url.includes('/evidence/')) await new Promise(resolve => setTimeout(resolve, 300)); return response; }`)
  await clickReference(observation.response.body.data.evidence_id)
  await wait(`document.querySelector('#evidence-panel').getAttribute('aria-busy') === 'true'`)
  await evaluate(`document.querySelector('#station').value = ''; document.querySelector('#station').dispatchEvent(new Event('change', { bubbles: true }))`)
  await evaluate(`new Promise(resolve => setTimeout(resolve, 500))`)
  assert.equal(await evaluate(`document.querySelector('#evidence-panel') === null`), true)
  console.log('D3 checks passed: all seven evidence snapshots, GET errors, post-answer handover fidelity, case reset and stale-request isolation.')
})
