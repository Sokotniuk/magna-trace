import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { ApiError, getCompany, signIn } from './api'
import type { SignedIn } from './api'

// Employee sign-in (D34). The backend checks the password and sets an HttpOnly session cookie;
// nothing secret is kept in the page or in browser storage.
export default function Login({ onSignedIn, notice }: { onSignedIn: (session: SignedIn) => void; notice?: string }) {
  const [company, setCompany] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [reveal, setReveal] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const userField = useRef<HTMLInputElement>(null)

  useEffect(() => {
    userField.current?.focus()
    void getCompany().then(setCompany)
  }, [])

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (busy || !username.trim() || !password) return
    setBusy(true)
    setError('')
    try {
      onSignedIn(await signIn(username.trim(), password))
    } catch (reason: unknown) {
      setError(reason instanceof ApiError ? reason.message : 'Could not reach the sign-in service. Check the backend and proxy.')
      setPassword('')
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="login">
      <section className="login-brand" aria-label="MAGNA TRACE">
        <span className="brand-mark" aria-hidden="true" />
        <h1>MAGNA TRACE</h1>
        <p className="login-tagline">Evidence-driven diagnostic assistant for test and maintenance technicians.</p>
        <ul className="login-points">
          <li>Every value comes from the line database, with an evidence ID.</li>
          <li>One clarifying question at a time; your answer is stored under your name.</li>
          <li>Handover summary for the next shift.</li>
        </ul>
        <p className="event-tag">MAGNA Hackathon · Košice 2026 · Task 9</p>
      </section>

      <section className="login-card" aria-labelledby="login-heading">
        <p className="login-company">{company || 'Employee access'}</p>
        <h2 id="login-heading">Employee sign-in</h2>
        {notice && <p className="login-notice" role="status">{notice}</p>}
        <form onSubmit={submit} noValidate aria-busy={busy}>
          <label htmlFor="login-username">Username</label>
          <input id="login-username" ref={userField} name="username" autoComplete="username" autoCapitalize="none"
            spellCheck={false} value={username} onChange={(event) => setUsername(event.target.value)}
            aria-invalid={error ? true : undefined} aria-describedby={error ? 'login-error' : undefined} />

          <label htmlFor="login-password">Password</label>
          <div className="password-field">
            <input id="login-password" name="password" type={reveal ? 'text' : 'password'} autoComplete="current-password"
              value={password} onChange={(event) => setPassword(event.target.value)}
              aria-invalid={error ? true : undefined} aria-describedby={error ? 'login-error' : undefined} />
            <button type="button" className="secondary" aria-pressed={reveal} aria-controls="login-password"
              onClick={() => setReveal((value) => !value)}>{reveal ? 'Hide' : 'Show'}</button>
          </div>

          {error && <p id="login-error" className="login-error" role="alert">{error}</p>}
          <button type="submit" disabled={busy || !username.trim() || !password}>{busy ? 'Signing in…' : 'Sign in'}</button>
        </form>
        <p className="login-footnote">Demo access list of a fictional company — not a corporate sign-in. Ask your team for a demo account.</p>
      </section>
    </main>
  )
}
