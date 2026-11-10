import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { randomBytes } from 'node:crypto'
import { once } from 'node:events'
import { mkdirSync, mkdtempSync, readFileSync, rmSync } from 'node:fs'
import { resolve } from 'node:path'
import test from 'node:test'
import { createServer as createViteServer } from 'vite'
import { createMockServer } from '../mock/server.mjs'

const fixtures = JSON.parse(readFileSync(new URL('../mock/b2/examples.json', import.meta.url), 'utf8'))
const byName = new Map(fixtures.cases.map((fixture) => [fixture.name, fixture]))

// Uses the installed Firefox and Node's WebSocket; no browser packages required.
async function browser(t) {
  mkdirSync('node_modules/.cache', { recursive: true })
  const profile = mkdtempSync(resolve('node_modules/.cache/d2-firefox-'))
  const firefox = spawn('firefox', ['--headless', '--no-remote', '--profile', profile, '--remote-debugging-port=0', 'about:blank'], {
    stdio: ['ignore', 'ignore', 'pipe'],
  })
  let socket
  t.after(async () => {
    socket?.close()
    if (firefox.exitCode === null && firefox.signalCode === null) {
      const exited = once(firefox, 'exit')
      firefox.kill('SIGTERM')
      await exited
    }
    rmSync(profile, { recursive: true, force: true })
  })
  const endpoint = await new Promise((resolveEndpoint, reject) => {
    let output = ''
    const timer = setTimeout(() => reject(new Error(`Firefox startup timed out: ${output}`)), 20000)
    firefox.once('error', (error) => { clearTimeout(timer); reject(error) })
    firefox.once('exit', (code) => { clearTimeout(timer); reject(new Error(`Firefox exited ${code}: ${output}`)) })
    firefox.stderr.on('data', (chunk) => {
      output += chunk.toString()
      const match = output.match(/WebDriver BiDi listening on (ws:\/\/\S+)/)
      if (match) { clearTimeout(timer); resolveEndpoint(match[1]) }
    })
  })
  socket = new WebSocket(`${endpoint}/session`)
  await once(socket, 'open')
  let sequence = 0
  const pending = new Map()
  socket.addEventListener('message', (event) => {
    const message = JSON.parse(event.data)
    const promise = pending.get(message.id)
    if (!promise) return
    pending.delete(message.id)
    clearTimeout(promise.timer)
    if (message.type === 'error') promise.reject(new Error(`${message.error}: ${message.message}`))
    else promise.resolve(message.result)
  })
  const command = (method, params) => new Promise((resolveCommand, reject) => {
    const id = ++sequence
    const timer = setTimeout(() => { pending.delete(id); reject(new Error(`BiDi timeout: ${method}`)) }, 15000)
    pending.set(id, { resolve: resolveCommand, reject, timer })
    socket.send(JSON.stringify({ id, method, params }))
  })
  await command('session.new', { capabilities: {} })
  const { context } = await command('browsingContext.create', { type: 'tab' })
  const evaluate = async (expression) => {
    const result = await command('script.evaluate', { expression, target: { context }, awaitPromise: true })
    assert.equal(result.type, 'success', JSON.stringify(result))
    return result.result.value
  }
  const wait = (expression) => evaluate(`(async () => {
    const end = Date.now() + 10000;
    while (!(${expression})) {
      if (Date.now() > end) throw new Error('Dashboard wait timed out: ' + ${JSON.stringify(expression)});
      await new Promise(resolve => setTimeout(resolve, 50));
    }
    return true;
  })()`)
  return { command, context, evaluate, wait }
}

test('D2 browser: select station, preserve findings, show warnings and errors', { timeout: 120000 }, async (t) => {
  const apiKey = randomBytes(32).toString('hex')
  const requests = []
  let mock = createMockServer({ apiKey })
  mock.on('request', (req) => requests.push(req.url))
  mock.listen(0, '127.0.0.1')
  await once(mock, 'listening')
  const port = mock.address().port
  t.after(() => new Promise((done) => mock.close(done)))
  const oldKey = process.env.TRACE_API_KEY
  const oldTarget = process.env.TRACE_API_TARGET
  process.env.TRACE_API_KEY = apiKey
  process.env.TRACE_API_TARGET = `http://127.0.0.1:${port}`
  t.after(() => {
    if (oldKey === undefined) delete process.env.TRACE_API_KEY
    else process.env.TRACE_API_KEY = oldKey
    if (oldTarget === undefined) delete process.env.TRACE_API_TARGET
    else process.env.TRACE_API_TARGET = oldTarget
  })
  const vite = await createViteServer({ configFile: resolve('vite.config.mjs'), server: { host: '127.0.0.1', port: 0, strictPort: true } })
  t.after(() => vite.close())
  await vite.listen()
  const demoScope = JSON.parse(readFileSync(new URL('../src/demo-scope.json', import.meta.url), 'utf8'))
  assert.deepEqual({ station_number: 'SYNTHETIC-STATION', ...demoScope }, byName.get('open_case').request.body)
  // Render-only inputs check all returned status labels and exact Decimal text.
  // They are not new API fixtures, calculations or source observations.
  const { FindingsTable } = await vite.ssrLoadModule('/src/App.tsx')
  const { createElement } = await import('react')
  const { renderToStaticMarkup } = await import('react-dom/server')
  for (const status of ['ABOVE', 'BELOW', 'WITHIN_RECORDED_BOUNDS', 'NOT_EVALUABLE']) {
    const markup = renderToStaticMarkup(createElement(FindingsTable, { findings: [{
      ...byName.get('open_case').response.body.data.findings[0],
      range_status: status,
      raw_value: ' 10.5000 ',
      deviation: '1E-21',
    }] }))
    assert.ok(markup.includes(`range-${status}`))
    assert.ok(markup.includes(' 10.5000 '))
    assert.ok(markup.includes('1E-21'))
  }
  const { command, context, evaluate, wait } = await browser(t)
  await command('browsingContext.navigate', { context, url: `http://127.0.0.1:${vite.httpServer.address().port}`, wait: 'complete' })
  await wait(`document.querySelector('#station option[value="SYNTHETIC-STATION"]')`)
  assert.equal(await evaluate(`document.querySelector('button[type="submit"]').disabled`), true)
  await evaluate(`document.querySelector('#station').value = 'SYNTHETIC-STATION'; document.querySelector('#station').dispatchEvent(new Event('change', { bubbles: true }))`)
  await wait(`!document.querySelector('button[type="submit"]').disabled`)
  await evaluate(`document.querySelector('button[type="submit"]').click()`)
  await wait(`document.querySelectorAll('tbody tr').length === 3`)
  assert.ok(requests.includes('/api/v1/stations?q=SYNTHETIC&limit=20'))
  assert.ok(requests.includes('/api/v1/cases'))
  const rows = JSON.parse(await evaluate(`JSON.stringify([...document.querySelectorAll('tbody tr')].map(row => [...row.cells].map(cell => cell.textContent)))`))
  const snapshot = byName.get('open_case').response.body.data
  snapshot.findings.forEach((finding, i) => {
    assert.ok(rows[i][0].includes(finding.measurement))
    assert.ok(rows[i][0].includes(finding.evidence_id))
    assert.deepEqual(rows[i].slice(1, 7), [finding.raw_value, finding.unit, finding.raw_lower, finding.raw_upper, finding.deviation, finding.range_status].map(value => value === null ? 'null' : value))
    for (const flag of finding.quality_flags) assert.ok(rows[i][7].includes(flag))
    assert.equal(rows[i][8], finding.raw_fail_code === null ? 'null' : finding.raw_fail_code)
  })
  assert.equal(rows[1][6], 'WITHIN_RECORDED_BOUNDS')
  assert.equal(rows[1][8], '1001')
  assert.ok(!/\b(PASS|FAIL)\b/.test(rows[1].join(' ')))
  for (const warning of snapshot.warnings) assert.equal(await evaluate(`document.querySelector('.warnings').textContent.includes(${JSON.stringify(warning)})`), true)
  assert.equal(await evaluate(`document.querySelector('.synthetic-banner').textContent.includes('SYNTHETIC')`), true)
  assert.equal(await evaluate(`document.body.textContent.includes(${JSON.stringify(apiKey)})`), false)
  assert.ok(!requests.some(path => path.includes('/evidence/') || path.includes('/comparisons')))

  for (const name of ['error_NO_DATA', 'error_SOURCE_UNAVAILABLE', 'error_TIMEOUT', 'error_INVALID_SCOPE']) {
    await new Promise(done => mock.close(done))
    mock = createMockServer({ apiKey, scenario: name })
    mock.listen(port, '127.0.0.1')
    await once(mock, 'listening')
    await evaluate(`document.querySelector('button[type="submit"]').click()`)
    const error = byName.get(name).response.body.error
    await wait(`document.querySelector('[role="alert"]')?.textContent.includes(${JSON.stringify(error.code)})`)
    assert.equal(await evaluate(`document.querySelectorAll('tbody tr').length`), 0)
    assert.equal(await evaluate(`document.querySelector('[role="alert"]').textContent.includes(${JSON.stringify(error.message)})`), true)
    if (error.scope) assert.deepEqual(JSON.parse(await evaluate(`document.querySelector('[role="alert"] pre').textContent`)), error.scope)
  }
  // Station-list auth errors do not leave selectable stations or stale findings.
  await new Promise(done => mock.close(done))
  mock = createMockServer({ apiKey: 'SYNTHETIC-wrong-key' })
  mock.listen(port, '127.0.0.1')
  await once(mock, 'listening')
  await evaluate(`document.querySelector('button.secondary').click()`)
  await wait(`document.querySelector('[role="alert"]')?.textContent.includes('UNAUTHORIZED')`)
  assert.equal(await evaluate(`document.querySelectorAll('#station option').length`), 1)
  assert.equal(await evaluate(`document.querySelector('button[type="submit"]').disabled`), true)
  console.log('D2 browser checks passed: station selection/opening, exact table values, in-range 1001, warnings, source errors and station-list 401.')
})
