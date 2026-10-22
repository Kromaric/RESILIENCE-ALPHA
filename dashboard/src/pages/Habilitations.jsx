import { useCallback, useEffect, useState } from 'react'
import { KeyRound, Loader2, LogOut, Pencil, ScanFace, Trash2, Unlock, UserPlus, X } from 'lucide-react'
import { api } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import Badge from '../components/Badge'
import Card from '../components/Card'
import SectionTitle from '../components/SectionTitle'
import FaceCapture from '../components/camera/FaceCapture'

// Gestion des habilitations du back-office (rôle admin) : comptes, rôles, visages, sessions.
// Toutes les actions passent par bo-api (/bo/admin/operators) et sont journalisées par
// auth-service (administrateur, action, opérateur visé).

const ROLES = [
  ['viewer', 'Lecture'],
  ['operator', 'Opérateur'],
  ['admin', 'Administrateur'],
]
const BASE = '/bo/admin/operators'

const input =
  'mt-1 w-full rounded-md border border-line bg-bg px-3 py-2 text-sm outline-none placeholder:text-muted focus:border-accent'
const button =
  'inline-flex items-center gap-1.5 rounded-md border border-line px-2 py-1 text-xs text-gray-300 hover:bg-bg disabled:opacity-40'
const primary =
  'inline-flex items-center justify-center gap-2 rounded-md bg-accent px-3 py-2 text-sm font-medium text-bg hover:brightness-110 disabled:opacity-50'

function formatDate(iso) {
  return iso ? new Date(iso).toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' }) : '—'
}

function Modal({ title, onClose, children }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" role="dialog" aria-modal="true">
      <div className="max-h-[95vh] w-full max-w-md overflow-y-auto rounded-lg border border-line bg-surface p-5">
        <div className="mb-4 flex items-center justify-between gap-2">
          <h2 className="text-base font-semibold text-gray-100">{title}</h2>
          <button onClick={onClose} aria-label="Fermer" className="rounded-md p-1 text-muted hover:bg-bg hover:text-gray-200">
            <X size={16} />
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}

function CreateForm({ onDone, onError }) {
  const [form, setForm] = useState({ email: '', display_name: '', role: 'viewer', password: '' })
  const [busy, setBusy] = useState(false)
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value })

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    try {
      const created = await api(BASE, { method: 'POST', body: form })
      setForm({ email: '', display_name: '', role: 'viewer', password: '' })
      onDone(created)
    } catch (err) {
      onError(err)
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5 lg:items-end">
      <label className="text-xs text-muted">
        Email
        <input type="email" value={form.email} onChange={set('email')} className={input} required />
      </label>
      <label className="text-xs text-muted">
        Nom affiché
        <input value={form.display_name} onChange={set('display_name')} className={input} required minLength={2} />
      </label>
      <label className="text-xs text-muted">
        Rôle
        <select value={form.role} onChange={set('role')} className={input}>
          {ROLES.map(([value, label]) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>
      </label>
      <label className="text-xs text-muted">
        Mot de passe initial
        <input type="password" autoComplete="new-password" value={form.password} onChange={set('password')} className={input} required placeholder="12 caractères minimum" />
      </label>
      <button type="submit" disabled={busy} className={`${primary} h-[38px]`}>
        {busy ? <Loader2 size={14} className="animate-spin" /> : <UserPlus size={14} />}
        Créer
      </button>
    </form>
  )
}

function EnrollFace({ account, onDone, onError }) {
  const [consent, setConsent] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const onFrames = useCallback(
    async (frames) => {
      setBusy(true)
      setError(null)
      try {
        onDone(await api(`${BASE}/${account.operator_id}/face`, { method: 'POST', body: { consent: true, frames } }))
      } catch (err) {
        if (err.code === 'enrollment_failed') setError(err.message)
        else onError(err)
      } finally {
        setBusy(false)
      }
    },
    [account.operator_id, onDone, onError],
  )

  return (
    <>
      <p className="text-xs text-muted">
        {account.display_name} se place devant la caméra USB du poste. Son ancien visage, s'il en a un, sera remplacé.
      </p>
      <label className="my-4 flex items-start gap-2 text-xs text-gray-300">
        <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} className="mt-0.5" />
        L'opérateur a donné son consentement explicite à l'enregistrement de son visage (gabarits chiffrés, aucune image conservée, effaçables à sa demande).
      </label>
      {error && <p className="mb-3 rounded-md border border-danger/40 bg-danger/10 px-3 py-2 text-xs text-gray-200">{error}</p>}
      {consent && (
        <FaceCapture mode="sweep" frames={16} intervalMs={250} busy={busy} actionLabel="Enregistrer le visage" onFrames={onFrames} />
      )}
    </>
  )
}

function ResetPassword({ account, onDone }) {
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await api(`${BASE}/${account.operator_id}/password`, { method: 'POST', body: { password } })
      onDone()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit}>
      <p className="text-xs text-muted">Ses sessions seront révoquées et un éventuel blocage levé.</p>
      {error && <p className="mt-3 rounded-md border border-danger/40 bg-danger/10 px-3 py-2 text-xs text-gray-200">{error}</p>}
      <label className="mt-4 block text-xs text-muted">
        Nouveau mot de passe
        <input type="password" autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} className={input} required placeholder="12 caractères minimum" autoFocus />
      </label>
      <button type="submit" disabled={busy} className={`${primary} mt-4 w-full`}>
        {busy && <Loader2 size={14} className="animate-spin" />}
        Enregistrer
      </button>
    </form>
  )
}

function Rename({ account, onDone }) {
  const [name, setName] = useState(account.display_name)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      onDone(await api(`${BASE}/${account.operator_id}`, { method: 'PATCH', body: { display_name: name.trim() } }))
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit}>
      {error && <p className="rounded-md border border-danger/40 bg-danger/10 px-3 py-2 text-xs text-gray-200">{error}</p>}
      <label className="mt-1 block text-xs text-muted">
        Nom affiché
        <input value={name} onChange={(e) => setName(e.target.value)} className={input} required minLength={2} maxLength={80} autoFocus />
      </label>
      <button type="submit" disabled={busy} className={`${primary} mt-4 w-full`}>
        {busy && <Loader2 size={14} className="animate-spin" />}
        Enregistrer
      </button>
    </form>
  )
}

export default function Habilitations() {
  const { operator, updateOperator } = useAuth()
  const [accounts, setAccounts] = useState(null)
  const [version, setVersion] = useState(0) // incrémenté pour relire la liste
  const [message, setMessage] = useState(null) // { tone, text }
  const [modal, setModal] = useState(null) // { type: 'face' | 'password' | 'rename', account }
  const [pending, setPending] = useState(null) // id de l'opérateur en cours de modification

  useEffect(() => {
    let cancelled = false
    api(BASE)
      .then((data) => {
        if (!cancelled) setAccounts(data)
      })
      .catch((err) => {
        if (!cancelled) setMessage({ tone: 'danger', text: err.message })
      })
    return () => {
      cancelled = true
    }
  }, [version])

  const fail = useCallback((err) => setMessage({ tone: 'danger', text: err.message }), [])
  const done = useCallback((text) => {
    setMessage({ tone: 'ok', text })
    setModal(null)
    setVersion((v) => v + 1)
  }, [])

  // Renvoie true si l'action a abouti
  async function act(account, request, text, confirmText) {
    if (confirmText && !window.confirm(confirmText)) return false
    setPending(account.operator_id)
    try {
      await request()
      done(text)
      return true
    } catch (err) {
      fail(err)
      return false
    } finally {
      setPending(null)
    }
  }

  const patch = (account, body) => () =>
    api(`${BASE}/${account.operator_id}`, { method: 'PATCH', body })

  async function changeRole(account, role) {
    const self = account.operator_id === operator.operator_id
    const leaving = self && role !== 'admin'
    const ok = await act(
      account,
      patch(account, { role }),
      `Rôle de ${account.display_name} modifié.`,
      leaving ? "Quitter le rôle administrateur ? Vous perdrez aussitôt l'accès aux habilitations." : null,
    )
    // RequireRole renvoie alors vers la supervision
    if (ok && self) updateOperator({ role })
  }

  return (
    <div className="mx-auto max-w-7xl">
      <header>
        <h1 className="text-2xl font-semibold text-gray-100">Habilitations</h1>
        <p className="mt-1 text-xs text-muted">
          Comptes du back-office, rôles et reconnaissance faciale · chaque action est journalisée pour le SOC
        </p>
      </header>

      {message && (
        <p
          role="status"
          className={`mt-4 flex items-center justify-between gap-2 rounded-md border px-3 py-2 text-xs text-gray-200 ${
            message.tone === 'ok' ? 'border-ok/40 bg-ok/10' : 'border-danger/40 bg-danger/10'
          }`}
        >
          {message.text}
          <button onClick={() => setMessage(null)} aria-label="Masquer" className="text-muted hover:text-gray-200">
            <X size={14} />
          </button>
        </p>
      )}

      <SectionTitle>Nouvel opérateur</SectionTitle>
      <Card>
        <CreateForm
          onDone={(created) => done(`${created.display_name} créé. Enregistrez maintenant son visage.`)}
          onError={fail}
        />
      </Card>

      <SectionTitle right={accounts ? `${accounts.length} compte(s)` : null}>Opérateurs</SectionTitle>
      <Card className="overflow-x-auto p-0">
        {!accounts ? (
          <p className="p-4 text-xs text-muted">Chargement…</p>
        ) : (
          <table className="w-full min-w-[860px] text-left text-xs">
            <thead className="border-b border-line text-[11px] uppercase tracking-wider text-muted">
              <tr>
                <th className="px-4 py-3 font-medium">Opérateur</th>
                <th className="px-4 py-3 font-medium">Rôle</th>
                <th className="px-4 py-3 font-medium">État</th>
                <th className="px-4 py-3 font-medium">Visage</th>
                <th className="px-4 py-3 font-medium">Dernière connexion</th>
                <th className="px-4 py-3 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {accounts.map((a) => {
                const self = a.operator_id === operator.operator_id
                const busy = pending === a.operator_id
                return (
                  <tr key={a.operator_id} className="border-b border-line/60 last:border-0 align-top">
                    <td className="px-4 py-3">
                      <p className="flex items-center gap-1.5 whitespace-nowrap text-sm text-gray-100">
                        {a.display_name}
                        {self && <span className="text-[11px] text-muted">(vous)</span>}
                        <button
                          disabled={busy}
                          onClick={() => setModal({ type: 'rename', account: a })}
                          aria-label={`Renommer ${a.display_name}`}
                          title="Renommer"
                          className="rounded p-0.5 text-muted hover:bg-bg hover:text-gray-200 disabled:opacity-40"
                        >
                          <Pencil size={12} />
                        </button>
                      </p>
                      <p className="text-muted">{a.email}</p>
                    </td>
                    <td className="px-4 py-3">
                      <select
                        value={a.role}
                        disabled={busy}
                        onChange={(e) => changeRole(a, e.target.value)}
                        className="rounded-md border border-line bg-bg px-2 py-1 text-xs outline-none focus:border-accent"
                      >
                        {ROLES.map(([value, label]) => (
                          <option key={value} value={value}>{label}</option>
                        ))}
                      </select>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-1.5">
                        {a.active ? <Badge tone="ok">Actif</Badge> : <Badge tone="unknown">Désactivé</Badge>}
                        {a.locked && <Badge tone="danger">Bloqué</Badge>}
                        {a.active_sessions > 0 && <Badge tone="accent">{a.active_sessions} session(s)</Badge>}
                      </div>
                      <button
                        className={`${button} mt-2`}
                        disabled={busy}
                        onClick={() =>
                          act(
                            a,
                            patch(a, { active: !a.active }),
                            a.active ? `${a.display_name} désactivé, sessions révoquées.` : `${a.display_name} réactivé.`,
                            !a.active
                              ? null
                              : self
                                ? 'Désactiver votre propre compte ? Vous serez aussitôt déconnecté.'
                                : `Désactiver ${a.display_name} ? Ses sessions seront révoquées.`,
                          )
                        }
                      >
                        {a.active ? 'Désactiver' : 'Réactiver'}
                      </button>
                    </td>
                    <td className="px-4 py-3">
                      {a.face_enrolled ? (
                        <Badge tone="ok" icon={ScanFace}>Enregistré · {a.face_templates} gabarits</Badge>
                      ) : (
                        <Badge tone="warn" icon={ScanFace}>Non enregistré</Badge>
                      )}
                      {a.biometric_consent_at && (
                        <p className="mt-1 text-[11px] text-muted">Consentement : {formatDate(a.biometric_consent_at)}</p>
                      )}
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        <button className={button} disabled={busy} onClick={() => setModal({ type: 'face', account: a })}>
                          <ScanFace size={12} /> {a.face_enrolled ? 'Remplacer' : 'Enregistrer'}
                        </button>
                        {a.face_enrolled && (
                          <button
                            className={button}
                            disabled={busy}
                            onClick={() =>
                              act(
                                a,
                                () => api(`${BASE}/${a.operator_id}/face`, { method: 'DELETE' }),
                                `Visage de ${a.display_name} effacé.`,
                                `Effacer le visage de ${a.display_name} ? Il ne pourra plus se connecter avant un nouvel enregistrement.`,
                              )
                            }
                          >
                            <Trash2 size={12} /> Effacer
                          </button>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-muted">{formatDate(a.last_login_at)}</td>
                    <td className="px-4 py-3">
                      <div className="flex flex-col items-start gap-1.5">
                        <button className={button} disabled={busy} onClick={() => setModal({ type: 'password', account: a })}>
                          <KeyRound size={12} /> Mot de passe
                        </button>
                        {a.locked && (
                          <button
                            className={button}
                            disabled={busy}
                            onClick={() => act(a, () => api(`${BASE}/${a.operator_id}/unlock`, { method: 'POST' }), `${a.display_name} débloqué.`)}
                          >
                            <Unlock size={12} /> Débloquer
                          </button>
                        )}
                        <button
                          className={button}
                          disabled={busy || a.active_sessions === 0}
                          onClick={() =>
                            act(
                              a,
                              () => api(`${BASE}/${a.operator_id}/sessions`, { method: 'DELETE' }),
                              `Sessions de ${a.display_name} révoquées.`,
                              self ? 'Révoquer vos propres sessions ? Vous serez déconnecté.' : null,
                            )
                          }
                        >
                          <LogOut size={12} /> Révoquer les sessions
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </Card>

      {modal?.type === 'face' && (
        <Modal title={`Visage de ${modal.account.display_name}`} onClose={() => setModal(null)}>
          <EnrollFace
            account={modal.account}
            onDone={() => done(`Visage de ${modal.account.display_name} enregistré.`)}
            onError={(err) => {
              setModal(null)
              fail(err)
            }}
          />
        </Modal>
      )}
      {modal?.type === 'password' && (
        <Modal title={`Mot de passe de ${modal.account.display_name}`} onClose={() => setModal(null)}>
          <ResetPassword
            account={modal.account}
            onDone={() => done(`Mot de passe de ${modal.account.display_name} modifié, sessions révoquées.`)}
          />
        </Modal>
      )}
      {modal?.type === 'rename' && (
        <Modal title={`Renommer ${modal.account.display_name}`} onClose={() => setModal(null)}>
          <Rename
            account={modal.account}
            onDone={(updated) => {
              if (updated.operator_id === operator.operator_id) updateOperator({ display_name: updated.display_name })
              done(`${modal.account.display_name} renommé en ${updated.display_name}.`)
            }}
          />
        </Modal>
      )}
    </div>
  )
}
