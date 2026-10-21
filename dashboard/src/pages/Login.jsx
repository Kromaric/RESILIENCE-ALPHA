import { useCallback, useEffect, useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { CheckCircle2, Loader2 } from 'lucide-react'
import { useAuth } from '../auth/AuthContext'
import FaceCapture from '../components/camera/FaceCapture'

// Visage non reconnu : la consigne impose 30 s (LED rouge fixe) avant un nouvel identifiant
const FACE_FAILURE_LOCK_S = 30

const STEPS = [
  ['identify', 'Identifiant'],
  ['face', 'Visage'],
  ['password', 'Mot de passe'],
]

function errorMessage(err) {
  const minutes = err.retryAfter ? Math.ceil(Number(err.retryAfter) / 60) : null
  const wait = minutes ? ` Réessayez dans ${minutes} min.` : ''
  switch (err.code) {
    case 'face_not_recognized':
      return 'Visage non reconnu. Nouvel essai possible dans 30 secondes.'
    case 'liveness_failed':
      return "Mouvement de la tête non détecté dans le sens demandé. Nouvel essai possible dans 30 secondes."
    case 'invalid_credentials':
      return "Mot de passe incorrect. Recommencez l'identification."
    case 'login_step_expired':
      return "Délai dépassé. Recommencez l'identification."
    case 'identification_locked':
      return 'Visage non reconnu juste avant : patientez avant de ressaisir votre identifiant.'
    case 'account_locked':
      return `Compte bloqué après plusieurs échecs.${wait}`
    case 'too_many_attempts':
      return `Trop de tentatives.${wait}`
    case 'enrollment_failed':
    case 'consent_required':
      return err.message
    default:
      return err.message
  }
}

function Stepper({ step }) {
  const index = STEPS.findIndex(([key]) => key === step)
  return (
    <ol className="mt-5 flex items-center gap-2 text-[11px]">
      {STEPS.map(([key, label], i) => (
        <li key={key} className="flex items-center gap-2">
          <span
            className={`flex size-5 items-center justify-center rounded-full border text-[10px] ${
              i < index
                ? 'border-ok bg-ok/15 text-ok'
                : i === index
                  ? 'border-accent bg-accent/15 text-accent'
                  : 'border-line text-muted'
            }`}
          >
            {i + 1}
          </span>
          <span className={i === index ? 'text-gray-200' : 'text-muted'}>{label}</span>
          {i < STEPS.length - 1 && <span className="h-px w-4 bg-line" />}
        </li>
      ))}
    </ol>
  )
}

export default function Login() {
  const { operator, identify, verifyFace, submitPassword, enrollOwnFace } = useAuth()
  const navigate = useNavigate()
  const from = useLocation().state?.from ?? '/'

  const [step, setStep] = useState('identify') // identify | face | password | enroll | enrolled
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [session, setSession] = useState(null)
  const [enrollmentToken, setEnrollmentToken] = useState(null)
  const [consent, setConsent] = useState(false)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [lockedUntil, setLockedUntil] = useState(0)
  const [now, setNow] = useState(() => Date.now())

  const lockLeft = Math.max(0, Math.ceil((lockedUntil - now) / 1000))
  useEffect(() => {
    if (!lockLeft) return
    const timer = setInterval(() => setNow(Date.now()), 250)
    return () => clearInterval(timer)
  }, [lockLeft])

  // Retour à l'identifiant : identifiant vidé, caméra éteinte (elle ne s'affiche qu'à l'étape visage)
  const restart = useCallback((err, lockSeconds = 0) => {
    setStep('identify')
    setEmail('')
    setPassword('')
    setSession(null)
    setEnrollmentToken(null)
    setConsent(false)
    setBusy(false)
    setError(err ? errorMessage(err) : null)
    if (lockSeconds) {
      setNow(Date.now())
      setLockedUntil(Date.now() + lockSeconds * 1000)
    }
  }, [])

  const onFaceFrames = useCallback(
    async (frames) => {
      setBusy(true)
      setError(null)
      try {
        await verifyFace(session.session_id, frames)
        setStep('password')
        setBusy(false)
      } catch (err) {
        const failed = ['face_not_recognized', 'liveness_failed'].includes(err.code)
        restart(err, failed ? FACE_FAILURE_LOCK_S : 0)
      }
    },
    [restart, session, verifyFace],
  )

  const onEnrollFrames = useCallback(
    async (frames) => {
      setBusy(true)
      setError(null)
      try {
        await enrollOwnFace(enrollmentToken, frames)
        setStep('enrolled')
        setBusy(false)
      } catch (err) {
        if (err.code === 'enrollment_failed') {
          setError(errorMessage(err)) // on peut recommencer la capture
          setBusy(false)
        } else {
          restart(err)
        }
      }
    },
    [enrollOwnFace, enrollmentToken, restart],
  )

  if (operator) return <Navigate to={from} replace />

  async function submitIdentifier(e) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      const next = await identify(email.trim())
      setSession(next)
      setStep(next.step)
      setBusy(false)
    } catch (err) {
      const wait = err.code === 'identification_locked' ? Number(err.retryAfter) || 30 : 0
      restart(err, wait)
    }
  }

  async function submitSecret(e) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      const { enrollmentToken: token } = await submitPassword(session.session_id, password)
      if (token) {
        setEnrollmentToken(token)
        setPassword('')
        setStep('enroll')
        setBusy(false)
      } else {
        navigate(from, { replace: true })
      }
    } catch (err) {
      restart(err)
    }
  }

  const input =
    'mt-1 w-full rounded-md border border-line bg-bg px-3 py-2 text-sm outline-none placeholder:text-muted focus:border-accent disabled:opacity-50'
  const primary =
    'mt-5 flex w-full items-center justify-center gap-2 rounded-md bg-accent py-2 text-sm font-medium text-bg hover:brightness-110 disabled:opacity-50'

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <div className="w-full max-w-md rounded-lg border border-line bg-surface p-6">
        <p className="text-2xl font-semibold text-accent">orbe</p>
        <p className="text-xs text-muted">Console équipe technique · poste du PC Hôte</p>

        <h1 className="mt-6 text-lg font-semibold text-gray-100">
          {step === 'enroll' || step === 'enrolled' ? 'Enregistrer votre visage' : 'Connexion opérateur'}
        </h1>
        {['identify', 'face', 'password'].includes(step) && <Stepper step={step} />}

        {error && (
          <p role="alert" className="mt-4 rounded-md border border-danger/40 bg-danger/10 px-3 py-2 text-xs text-gray-200">
            {error}
          </p>
        )}

        {step === 'identify' && (
          <form onSubmit={submitIdentifier}>
            <label className="mt-4 block text-xs text-muted">
              Identifiant (email)
              <input
                type="email"
                autoComplete="username"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className={input}
                disabled={lockLeft > 0}
                autoFocus
                required
              />
            </label>
            <button type="submit" disabled={busy || lockLeft > 0} className={primary}>
              {busy && <Loader2 size={14} className="animate-spin" />}
              {lockLeft > 0 ? `Nouvel essai dans ${lockLeft} s` : 'Continuer'}
            </button>
          </form>
        )}

        {step === 'face' && session && (
          <div className="mt-4">
            <p className="mb-3 text-xs text-muted">
              Placez-vous face à la caméra USB. Après le compte à rebours, tournez nettement la tête
              dans le sens indiqué.
            </p>
            <FaceCapture
              direction={session.face_challenge.direction}
              frames={session.face_challenge.frames}
              intervalMs={session.face_challenge.interval_ms}
              busy={busy}
              onFrames={onFaceFrames}
            />
          </div>
        )}

        {step === 'password' && (
          <form onSubmit={submitSecret}>
            {session?.face_enrollment_required ? (
              <p className="mt-4 rounded-md border border-warn/40 bg-warn/10 px-3 py-2 text-xs text-gray-200">
                Aucun visage n'est encore enregistré sur la plateforme : après votre mot de passe,
                vous enregistrerez le vôtre.
              </p>
            ) : (
              <p className="mt-4 flex items-center gap-1.5 text-xs text-ok">
                <CheckCircle2 size={14} /> Visage reconnu
              </p>
            )}
            <label className="mt-4 block text-xs text-muted">
              Mot de passe
              <input
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className={input}
                autoFocus
                required
              />
            </label>
            <button type="submit" disabled={busy} className={primary}>
              {busy && <Loader2 size={14} className="animate-spin" />}
              Se connecter
            </button>
          </form>
        )}

        {step === 'enroll' && (
          <div className="mt-4">
            <label className="mb-4 flex items-start gap-2 text-xs text-gray-300">
              <input
                type="checkbox"
                checked={consent}
                onChange={(e) => setConsent(e.target.checked)}
                className="mt-0.5 accent-[var(--color-accent)]"
              />
              J'accepte que mon visage soit enregistré pour me connecter au back-office : seuls des
              gabarits chiffrés sont conservés (aucune image), effaçables à ma demande.
            </label>
            {consent && (
              <FaceCapture
                mode="sweep"
                frames={16}
                intervalMs={250}
                busy={busy}
                actionLabel="Enregistrer mon visage"
                onFrames={onEnrollFrames}
              />
            )}
          </div>
        )}

        {step === 'enrolled' && (
          <div className="mt-4">
            <p className="flex items-center gap-1.5 text-sm text-ok">
              <CheckCircle2 size={16} /> Visage enregistré.
            </p>
            <p className="mt-1 text-xs text-muted">Reconnectez-vous : cette fois avec votre visage.</p>
            <button type="button" onClick={() => restart(null)} className={primary}>
              Se reconnecter
            </button>
          </div>
        )}

        {['face', 'password', 'enroll'].includes(step) && (
          <button
            type="button"
            onClick={() => restart(null)}
            className="mt-3 w-full text-center text-xs text-muted hover:text-gray-200"
          >
            Annuler et recommencer
          </button>
        )}
      </div>
    </div>
  )
}
