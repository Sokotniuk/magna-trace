import { useEffect, useState } from 'react'

type Status = { oracle: string; model: string }

const LABEL: Record<string, string> = {
  ok: 'OK', error: 'down', unused: 'ready', not_configured: 'not configured', checking: 'checking…',
}

// Readiness chip for the live header: Oracle via the backend's read-only count, the model from
// its last call (no extra model call). Text labels carry the meaning, colour only repeats it.
export default function SystemStatus() {
  const [status, setStatus] = useState<Status>({ oracle: 'checking', model: 'checking' })

  useEffect(() => {
    let alive = true
    const load = () => fetch('/api/v1/status')
      .then((response) => response.json())
      .then((body) => {
        if (alive && body?.status === 'ok' && typeof body.data?.oracle === 'string' && typeof body.data?.model === 'string') {
          setStatus({ oracle: body.data.oracle, model: body.data.model })
        } else if (alive) setStatus({ oracle: 'error', model: 'error' })
      })
      .catch(() => { if (alive) setStatus({ oracle: 'error', model: 'error' }) })
    void load()
    const timer = window.setInterval(load, 30000)
    window.addEventListener('focus', load)
    window.addEventListener('trace:chat-turn', load)
    return () => {
      alive = false
      window.clearInterval(timer)
      window.removeEventListener('focus', load)
      window.removeEventListener('trace:chat-turn', load)
    }
  }, [])

  return (
    <span className="system-status" role="status" aria-live="polite">
      {(['oracle', 'model'] as const).map((part) => {
        const value = status[part]
        const tone = value === 'ok' || value === 'unused' ? 'good' : value === 'checking' ? 'wait' : 'bad'
        return <span key={part} className={`status-item ${tone}`}>
          <span className="status-dot" aria-hidden="true" />
          {part === 'oracle' ? 'Oracle' : 'Model'} {LABEL[value] ?? value}
        </span>
      })}
    </span>
  )
}
