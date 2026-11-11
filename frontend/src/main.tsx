import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import AuthGate from './AuthGate'
import { isMockMode } from './api-mode'
import './styles.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {/* Live mode asks for an employee sign-in first (D34); the SYNTHETIC mock stays open for D's tests. */}
    {isMockMode ? <App /> : <AuthGate />}
  </StrictMode>,
)
