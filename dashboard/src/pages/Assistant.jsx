import { useState, useRef, useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import { ArrowRight, Lock } from 'lucide-react'
import { suggestions } from '../data/assistant'
import { api } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import Badge from '../components/Badge'
import ChatMessage from '../components/assistant/ChatMessage'
import SourcesPanel from '../components/assistant/SourcesPanel'
import ConfigPanel from '../components/assistant/ConfigPanel'

const now = () => new Date().toLocaleTimeString('fr-FR')

export default function Assistant() {
  const { operator } = useAuth()
  // Accessible à tous les utilisateurs authentifiés
  const canAsk = Boolean(operator)
  const [messages, setMessages] = useState([])
  const [sources, setSources] = useState([])
  const [input, setInput] = useState(useLocation().state?.question ?? '')
  const [loading, setLoading] = useState(false)
  const listRef = useRef(null)

  // Défile en bas à chaque nouveau message
  useEffect(() => {
    listRef.current.scrollTop = listRef.current.scrollHeight
  }, [messages, loading])

  async function send(text) {
    const question = text.trim()
    if (question.length < 3 || loading || !canAsk) return
    setMessages((m) => [...m, { role: 'user', time: now(), text: question }])
    setInput('')
    setLoading(true)
    // oxlint-disable-next-line react/purity
    const started = Date.now()
    try {
      const { answer, sources } = await api('/bo/assistant/ask', { method: 'POST', body: { question } })
      // oxlint-disable-next-line react/purity
      const seconds = ((Date.now() - started) / 1000).toFixed(1).replace('.', ',')
      setMessages((m) => [
        ...m,
        { role: 'assistant', time: now(), text: answer, sources, meta: `${sources.length} extrait(s) · ${seconds} s` },
      ])
      setSources(sources)
    } catch (err) {
      setMessages((m) => [...m, { role: 'assistant', time: now(), error: err.message }])
    } finally {
      setLoading(false)
    }
  }

  function onKeyDown(e) {
    // Entrée envoie, Maj + Entrée fait un retour à la ligne
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send(input)
    }
  }

  return (
    <div className="mx-auto max-w-7xl">
      <header className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-semibold text-gray-100">Assistant IA opérateur</h1>
            <Badge tone="accent">RAG local · Ollama</Badge>
          </div>
          <p className="mt-1 text-xs text-muted">
            Réponses fondées sur la documentation Orbe (architecture, runbooks, RGPD) · Aucun appel cloud
          </p>
        </div>
      </header>

      <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="flex flex-col rounded-lg border border-line bg-surface p-4 lg:col-span-2">
          {/* Fil de discussion */}
          <div ref={listRef} className="h-[480px] overflow-y-auto space-y-4 pr-2">
            {messages.length === 0 ? (
              <div className="flex h-full flex-col items-center justify-center text-center">
                <p className="text-sm text-gray-300">Posez une question technique ou opérationnelle sur Orbe.</p>
                <p className="mt-1 text-xs text-muted">L&apos;assistant répond à partir des runbooks et spécifications du dépôt.</p>
                <div className="mt-6 grid max-w-lg gap-2">
                  {suggestions.map((s) => (
                    <button
                      key={s}
                      onClick={() => send(s)}
                      disabled={!canAsk}
                      className="rounded-md border border-line bg-bg p-2 text-left text-xs text-gray-300 transition hover:border-accent hover:text-white disabled:opacity-50"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((m, i) => <ChatMessage key={i} {...m} />)
            )}
            {loading && (
              <div className="flex items-center gap-2 text-xs text-muted">
                <span className="inline-block h-2 w-2 animate-ping rounded-full bg-accent" />
                Interrogation du modèle local…
              </div>
            )}
          </div>

          {/* Saisie */}
          <div className="mt-4 border-t border-line pt-3">
            {canAsk ? (
              <div className="flex gap-2">
                <textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={onKeyDown}
                  placeholder="Posez votre question… (Entrée pour envoyer)"
                  rows={2}
                  className="flex-1 resize-none rounded-md border border-line bg-bg p-2 text-xs text-gray-100 placeholder-muted focus:border-accent focus:outline-none"
                />
                <button
                  onClick={() => send(input)}
                  disabled={loading || input.trim().length < 3}
                  className="flex items-center gap-1.5 self-end rounded-md bg-accent px-4 py-2 text-xs font-medium text-bg transition hover:brightness-110 disabled:opacity-50"
                >
                  Envoyer <ArrowRight size={14} />
                </button>
              </div>
            ) : (
              <p className="flex items-center gap-2 text-xs text-muted">
                <Lock size={14} /> Connexion requise pour poser des questions.
              </p>
            )}
          </div>
        </div>

        {/* Panneaux latéraux */}
        <div className="space-y-4">
          <SourcesPanel sources={sources} />
          <ConfigPanel />
        </div>
      </div>
    </div>
  )
}
