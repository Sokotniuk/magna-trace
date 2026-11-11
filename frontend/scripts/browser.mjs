import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { once } from 'node:events'
import { mkdirSync, mkdtempSync, rmSync } from 'node:fs'
import { resolve } from 'node:path'

// Uses the installed Firefox and Node's WebSocket; no browser packages required.
export async function browser(t) {
  mkdirSync('node_modules/.cache', { recursive: true })
  const profile = mkdtempSync(resolve('node_modules/.cache/d2-firefox-'))
  const firefox = spawn('firefox', ['--headless', '--no-remote', '--profile', profile, '--remote-debugging-port=0', 'about:blank'], {
    stdio: ['ignore', 'ignore', 'pipe'],
    env: Object.fromEntries(Object.entries(process.env).filter(([name]) => name !== 'TRACE_API_KEY')),
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
