import { useState, type FormEvent } from 'react'
import { Boxes, Eye, EyeOff } from 'lucide-react'
import { ApiError, signIn } from '@/api/client'

type LoginScreenProps = { onSignedIn: () => void }

export function LoginScreen({ onSignedIn }: LoginScreenProps) {
  const [login, setLogin] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setBusy(true)
    try {
      await signIn(login.trim(), password)
      onSignedIn()
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : 'Sign-in did not complete. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="login-shell">
      <section className="login-card" aria-labelledby="login-title">
        <div className="brand">
          <span className="brand-mark"><Boxes size={20} strokeWidth={2.1} /></span>
          <span>
            <span className="brand-name">AutoStock AI</span>
            <span className="brand-caption" style={{ display: 'block' }}>Inventory intelligence</span>
          </span>
        </div>
        <h1 className="login-title" id="login-title">Welcome back</h1>
        <p className="login-copy">Sign in with your Odoo account to open your inventory workspace.</p>
        <form onSubmit={submit}>
          <label className="form-label" htmlFor="login">Email or username</label>
          <input
            className="login-input"
            id="login"
            name="username"
            type="text"
            autoComplete="username"
            autoFocus
            required
            value={login}
            onChange={(event) => setLogin(event.target.value)}
          />
          <label className="form-label" htmlFor="password">Password</label>
          <div style={{ position: 'relative' }}>
            <input
              className="login-input"
              id="password"
              name="password"
              type={showPassword ? 'text' : 'password'}
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              style={{ paddingRight: 42 }}
            />
            <button
              type="button"
              aria-label={showPassword ? 'Hide password' : 'Show password'}
              onClick={() => setShowPassword((value) => !value)}
              style={{ position: 'absolute', right: 7, top: 5, width: 32, height: 32, border: 0, background: 'transparent', color: '#8991a1' }}
            >
              {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </div>
          {error && <div className="login-error" role="alert">{error}</div>}
          <button className="login-submit" type="submit" disabled={busy}>
            {busy ? 'Connecting to Odoo…' : 'Continue'}
          </button>
        </form>
        <p className="login-foot">Your account and permissions are managed by Odoo.</p>
      </section>
    </main>
  )
}
