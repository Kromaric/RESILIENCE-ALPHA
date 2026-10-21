import { useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import { useAuth } from '../auth/AuthContext'

function errorMessage(err) {
  const minutes = err.retryAfter ? Math.ceil(Number(err.retryAfter) / 60) : null
  const wait = minutes ? ` Réessayez dans ${minutes} min.` : ''
  switch (err.code) {
    case 'invalid_credentials':
      return 'Email ou mot de passe incorrect.'
    case 'account_locked':
      return `Compte bloqué après plusieurs échecs.${wait}`
    case 'too_many_attempts':
      return `Trop de tentatives.${wait}`
    case 'validation_error':
      return 'Renseignez un email et un mot de passe.'
    default:
      return err.message
  }
}

export default function Login() {
  const { operator, login } = useAuth()
  const navigate = useNavigate()
  const from = useLocation().state?.from ?? '/'
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)

  if (operator) return <Navigate to={from} replace />

  async function submit(e) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      await login(email.trim(), password)
      navigate(from, { replace: true })
    } catch (err) {
      setError(errorMessage(err))
      setLoading(false)
    }
  }

  const input =
    'mt-1 w-full rounded-md border border-line bg-bg px-3 py-2 text-sm outline-none placeholder:text-muted focus:border-accent'

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <form onSubmit={submit} className="w-full max-w-sm rounded-lg border border-line bg-surface p-6">
        <p className="text-2xl font-semibold text-accent">orbe</p>
        <p className="text-xs text-muted">Console équipe technique</p>

        <h1 className="mt-6 text-lg font-semibold text-gray-100">Connexion opérateur</h1>

        <label className="mt-4 block text-xs text-muted">
          Email
          <input
            type="email"
            autoComplete="username"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className={input}
            required
          />
        </label>
        <label className="mt-3 block text-xs text-muted">
          Mot de passe
          <input
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className={input}
            required
          />
        </label>

        {error && (
          <p role="alert" className="mt-4 rounded-md border border-danger/40 bg-danger/10 px-3 py-2 text-xs text-gray-200">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={loading}
          className="mt-5 flex w-full items-center justify-center gap-2 rounded-md bg-accent py-2 text-sm font-medium text-bg hover:brightness-110 disabled:opacity-60"
        >
          {loading && <Loader2 size={14} className="animate-spin" />}
          Se connecter
        </button>
      </form>
    </div>
  )
}
