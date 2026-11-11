import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { createHash, randomBytes } from 'node:crypto'
import { readFileSync, readdirSync } from 'node:fs'
import { once } from 'node:events'
import { resolve } from 'node:path'
import test from 'node:test'
import { createServer as createViteServer } from 'vite'
import { createMockServer } from '../mock/server.mjs'

const fixtures = JSON.parse(readFileSync(new URL('../mock/b2/examples.json', import.meta.url), 'utf8'))
const schema = JSON.parse(readFileSync(new URL('../mock/b2/schemas.json', import.meta.url), 'utf8'))
const byName = new Map(fixtures.cases.map((fixture) => [fixture.name, fixture]))

async function listen(server) {
  server.listen(0, '127.0.0.1')
  await once(server, 'listening')
  return `http://127.0.0.1:${server.address().port}`
}

function filesUnder(dir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = resolve(dir, entry.name)
    return entry.isDirectory() ? filesUnder(path) : [path]
  })
}

test('SYNTHETIC B2 candidate: build, authenticated mock and Vite proxy', async (t) => {
  const pin = JSON.parse(readFileSync(new URL('../mock/b2/PINNED.json', import.meta.url), 'utf8'))
  assert.equal(pin.commit, '145652f917cd8b5ccda40f214a03ba45d490150d')
  for (const [name, sha] of Object.entries(pin.git_blobs)) {
    const bytes = readFileSync(new URL(`../mock/b2/${name}`, import.meta.url))
    const blobHash = createHash('sha1').update(`blob ${bytes.length}\0`).update(bytes).digest('hex')
    assert.equal(blobHash, sha, `Pinned B2 artifact changed: ${name}`)
  }
  const apiKey = randomBytes(32).toString('hex')
  assert.throws(() => createMockServer(), /TRACE_API_KEY is required/)
  assert.throws(() => createMockServer({ apiKey, scenario: 'error_NOT_COMPARABLE' }), /P0 error fixture/)

  // Build with a unique server-only key present, then search the actual bundle.
  const buildOutput = execFileSync('npm', ['run', 'build'], {
    cwd: new URL('..', import.meta.url),
    env: { ...process.env, TRACE_API_KEY: apiKey },
    encoding: 'utf8',
  })
  console.log(buildOutput.trim())
  for (const file of [...filesUnder('src'), ...filesUnder('dist')]) {
    const content = readFileSync(file, 'utf8')
    assert.ok(!content.includes(apiKey), `Credential leaked into ${file}`)
    assert.ok(!content.includes('TRACE_API_KEY'), `Server key configuration referenced in ${file}`)
  }

  const mock = createMockServer({ apiKey })
  t.after(() => new Promise((resolveClose) => mock.close(resolveClose)))
  const target = await listen(mock)
  const previousKey = process.env.TRACE_API_KEY
  const previousTarget = process.env.TRACE_API_TARGET
  process.env.TRACE_API_KEY = apiKey
  process.env.TRACE_API_TARGET = target
  t.after(() => {
    if (previousKey === undefined) delete process.env.TRACE_API_KEY
    else process.env.TRACE_API_KEY = previousKey
    if (previousTarget === undefined) delete process.env.TRACE_API_TARGET
    else process.env.TRACE_API_TARGET = previousTarget
  })
  const vite = await createViteServer({
    configFile: resolve('vite.config.mjs'),
    server: { host: '127.0.0.1', port: 0, strictPort: false, open: false },
  })
  t.after(() => vite.close())
  await vite.listen()
  const proxy = `http://127.0.0.1:${vite.httpServer.address().port}`
  const page = await fetch(proxy)
  assert.equal(page.status, 200)
  const html = await page.text()
  assert.ok(html.includes('MAGNA TRACE'))
  assert.ok(!html.includes(apiKey))
  const appSource = await (await fetch(`${proxy}/src/App.tsx`)).text()
  assert.ok(!appSource.includes(apiKey))

  const seen = []
  mock.on('request', (req) => seen.push({ path: req.url, key: req.headers['x-api-key'] }))

  async function request(base, fixture, key) {
    const headers = { 'Content-Type': 'application/json' }
    if (key !== undefined) headers['X-API-Key'] = key
    const response = await fetch(base + fixture.path, {
      method: fixture.method,
      headers,
      // B2 GET request.body contains path/query parameters, never a GET body.
      ...(fixture.method === 'POST' && fixture.request ? { body: JSON.stringify(fixture.request.body) } : {}),
    })
    assert.equal(response.headers.get('x-trace-mock'), 'SYNTHETIC')
    const text = await response.text()
    assert.ok(!text.includes(apiKey))
    return { response, body: JSON.parse(text) }
  }

  const successNames = ['open_case', 'get_evidence_1', 'record_answer', 'get_handover', 'list_stations']
  for (const name of successNames) {
    for (const key of [undefined, 'SYNTHETIC-invalid-key']) {
      const { response, body } = await request(target, byName.get(name), key)
      assert.equal(response.status, 401)
      assert.deepEqual(body, byName.get('error_UNAUTHORIZED').response.body)
    }
  }

  for (const name of successNames) {
    const fixture = byName.get(name)
    const { response, body } = await request(proxy, fixture, 'SYNTHETIC-browser-key-must-be-overwritten')
    assert.equal(response.status, fixture.http_status)
    assert.deepEqual(body, fixture.response.body)
    assert.equal(seen.at(-1).path, fixture.path)
    assert.equal(seen.at(-1).key, apiKey)
    if (name === 'record_answer') {
      assert.ok(!Object.hasOwn(body.data, 'snapshot'))
      assert.ok(body.data.report_evidence_id)
      assert.deepEqual(body.data.findings, byName.get('open_case').response.body.data.findings)
    }
    if (name === 'list_stations') assert.equal(body.case_id, null)
  }
  // A credential-free browser request also succeeds via the server-side proxy.
  const stations = await request(proxy, byName.get('list_stations'))
  assert.equal(stations.response.status, 200)
  assert.equal(seen.at(-1).key, apiKey)

  for (let i = 1; i <= 7; i++) {
    const fixture = byName.get(`get_evidence_${i}`)
    const { response, body } = await request(proxy, fixture)
    assert.equal(response.status, 200)
    assert.deepEqual(body, fixture.response.body)
  }
  for (const name of ['error_EVIDENCE_NOT_FOUND', 'error_EVIDENCE_NOT_IN_CASE', 'error_CASE_NOT_FOUND_OR_EXPIRED']) {
    const fixture = byName.get(name)
    assert.equal(fixture.method, 'GET')
    if (name.startsWith('error_EVIDENCE')) assert.ok(fixture.path.includes('/evidence/'))
    const { response, body } = await request(proxy, fixture)
    assert.equal(response.status, fixture.http_status)
    assert.deepEqual(body, fixture.response.body)
    assert.equal(body.data, null)
  }
  const repeated = await request(proxy, byName.get('record_answer'))
  assert.equal(repeated.response.status, 409)
  assert.deepEqual(repeated.body, byName.get('error_stale_question').response.body)
  await request(proxy, byName.get('open_case'))
  const staleFixture = structuredClone(byName.get('record_answer'))
  staleFixture.request.body.question_id = 'Q-SYNTHETIC-stale'
  const stale = await request(proxy, staleFixture)
  assert.equal(stale.response.status, 409)
  assert.deepEqual(stale.body, byName.get('error_stale_question').response.body)

  // Error selection is a mock process option, not an addition to the B2 API.
  for (const name of ['error_INVALID_SCOPE', 'error_NO_DATA', 'error_SOURCE_UNAVAILABLE', 'error_TIMEOUT']) {
    const fixture = byName.get(name)
    const errorServer = createMockServer({ apiKey, scenario: name })
    try {
      const errorTarget = await listen(errorServer)
      const { response, body } = await request(errorTarget, byName.get('open_case'), apiKey)
      assert.equal(response.status, fixture.http_status)
      assert.deepEqual(body, fixture.response.body)
      assert.equal(body.data, null)
    } finally {
      await new Promise((resolveClose) => errorServer.close(resolveClose))
    }
  }

  const findings = byName.get('open_case').response.body.data.findings
  for (const finding of findings) {
    assert.ok(finding.quality_flags.includes('SEMANTICS_UNKNOWN'))
    for (const key of ['parsed_value', 'deviation']) {
      assert.ok(finding[key] === null || typeof finding[key] === 'string')
    }
  }
  assert.equal(findings[1].raw_fail_code, '1001')
  assert.equal(findings[1].range_status, 'WITHIN_RECORDED_BOUNDS')
  assert.equal(findings[0].raw_fail_code, null)
  assert.equal(findings[0].range_status, 'ABOVE')
  assert.equal(findings[2].deviation, null)
  const decimal = schema.$defs.Finding.properties.parsed_value.anyOf
  const pattern = new RegExp(decimal.find((item) => item.type === 'string').pattern)
  for (const value of ['1E-21', '1e+3', '0.5']) {
    assert.ok(pattern.test(value))
    assert.equal(JSON.parse(JSON.stringify({ value })).value, value)
  }
  for (const value of ['NaN', 'Infinity', 'abc', '1,5']) assert.ok(!pattern.test(value))
  assert.deepEqual(decimal.map((item) => item.type), ['string', 'null'])
  assert.equal(schema.$defs.ListStationsResponse.properties.case_id.type, 'null')
  assert.equal(schema.$defs.RecordAnswerResponse.properties.data.$ref, '#/$defs/AnswerSnapshot')
  console.log('SYNTHETIC: five operations, seven evidence snapshots, auth, proxy overwrite, errors, stale answers, Decimal rules and key-leak checks passed.')
})
