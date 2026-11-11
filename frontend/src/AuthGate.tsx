import { useEffect, useState } from 'react'
import { SIGNED_OUT_EVENT, getSession, signOut } from './api'
import type { SignedIn } from './api'
import App from './App'
import Login from './Login'

// Live mode only: the dashboard opens after an employee signs in (D34).
export default function AuthGate() {
  const [session, setSession] = useState<SignedIn | null | undefined>(undefined)
  const [notice, setNotice] = useState('')

  useEffect(() => {
    const controller = new AbortController()
    getSession(controller.signal).then(setSession).catch(() => {
      if (!controller.signal.aborted) setSession(null)
    })
    const expired = () => {
      setSession(null)
      setNotice('Your session has ended. Sign in again.')
    }
    window.addEventListener(SIGNED_OUT_EVENT, expired)
    return () => {
      controller.abort()
      window.removeEventListener(SIGNED_OUT_EVENT, expired)
    }
  }, [])

  if (session === undefined) return <main className="login"><p className="login-checking" role="status">Checking sign-in…</p></main>
  if (session === null) {
    return <Login notice={notice} onSignedIn={(value) => { setNotice(''); setSession(value) }} />
  }
  return <App session={session} onSignOut={async () => {
    await signOut()
    setNotice('You have signed out.')
    setSession(null)
  }} />
}
