import { ArrowLeftIcon, LockKeyIcon } from '@phosphor-icons/react'
import { motion, useReducedMotion } from 'motion/react'
import { useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import { api, ApiError } from '../api'
import { Owl } from '../components/child'
import { Button } from '../components/ui'
import { getToken, setToken } from '../lib/auth'

/** Only same-app paths are allowed as the post-login destination (no open redirect). */
function safeNext(next: string | null): string {
  return next && next.startsWith('/') && !next.startsWith('//') ? next : '/teacher'
}

export default function Login() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const reduce = useReducedMotion()
  const next = safeNext(params.get('next'))
  const [pin, setPin] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [shake, setShake] = useState(0)

  if (getToken()) return <Navigate to={next} replace />

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const { token, expires_at } = await api.login(pin)
      setToken(token, expires_at)
      navigate(next, { replace: true })
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 429
          ? err.message
          : err instanceof ApiError && err.status === 401
            ? 'That PIN is not right. Check it and try again.'
            : 'Could not reach the Akshar server. Check that it is running.',
      )
      setShake((s) => s + 1)
      setPin('')
      setBusy(false)
    }
  }

  return (
    <main className="flex min-h-dvh items-center justify-center px-4 py-10">
      <div className="w-full max-w-sm">
        <Link to="/" className="mb-8 inline-flex items-center gap-2 text-sm font-bold text-primary">
          <ArrowLeftIcon size={16} aria-hidden /> Akshar home
        </Link>
        <motion.form
          key={shake}
          onSubmit={submit}
          animate={shake && !reduce ? { x: [0, -8, 8, -5, 5, 0] } : undefined}
          transition={{ duration: 0.35 }}
          className="rounded-[16px] border border-outline/60 bg-white p-6"
        >
          <div className="mb-6 flex items-center gap-3">
            <Owl size={48} />
            <div>
              <h1 className="font-display text-2xl font-semibold">Teacher sign in</h1>
              <p className="text-sm text-ink-muted">Reports and recordings are for teachers only.</p>
            </div>
          </div>
          <label htmlFor="pin" className="mb-2 block text-sm font-bold">
            School PIN
          </label>
          <div className="relative">
            <LockKeyIcon size={20} className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-ink-muted" aria-hidden />
            <input
              id="pin"
              type="password"
              inputMode="numeric"
              autoComplete="current-password"
              autoFocus
              required
              value={pin}
              onChange={(e) => setPin(e.target.value)}
              aria-invalid={!!error}
              aria-describedby={error ? 'pin-error' : 'pin-help'}
              className="tabular w-full rounded-[12px] border border-outline bg-white py-3 pr-3 pl-10 text-lg tracking-[0.3em] focus:border-primary"
            />
          </div>
          {error ? (
            <p id="pin-error" role="alert" className="mt-2 text-sm font-bold text-error">
              {error}
            </p>
          ) : (
            <p id="pin-help" className="mt-2 text-sm text-ink-muted">
              Set by your school in the Akshar server settings.
            </p>
          )}
          <Button type="submit" className="mt-6 w-full py-3" disabled={busy || !pin}>
            {busy ? 'Checking' : 'Sign in'}
          </Button>
        </motion.form>
      </div>
    </main>
  )
}
