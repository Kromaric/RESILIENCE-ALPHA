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
  // POST /bo/assistant/ask est réservé au rôle « operator »
  const canAsk = operator.role === 'operator'
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
    const started = performance.now()
    try {
      const { answer, sources } = await api('/bo/assistant/ask', { method: 'POST', body: { question } })
      const seconds = ((performance.now() - started) / 1000).toFixed(1).replace('.', ',')
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
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-gray-100">Assistant opérateur</h1>
          <p className="mt-1 text-xs text-muted">
            Répond à partir de la documentation technique et cite ses sources · Ollama + LangChain, exécuté en local
          </p>
        </div>
        <div className="flex gap-2">
          {!canAsk && <Badge tone="warn">Questions réservées au rôle operator</Badge>}
          <Badge tone="accent" icon={Lock}>Lecture seule</Badge>
        </div>
      </header>

      <div className="mt-6 grid gap-4 xl:grid-cols-[1fr_320px]">
        {/* Chat */}
        <section className="flex h-[calc(100vh-9rem)] min-h-[560px] flex-col rounded-lg border border-line bg-surface">
          <div ref={listRef} className="flex-1 space-y-6 overflow-y-auto p-5">
            {messages.length === 0 && (
              <p className="text-sm text-muted">
                Posez une question sur les procédures, la remédiation ou l'architecture : l'assistant répond à
                partir de la documentation et cite ses sources.
              </p>
            )}
            {messages.map((m, i) => (
              <ChatMessage key={i} message={m} />
            ))}
            {loading && <p className="pl-10 text-xs text-muted animate-pulse">L'assistant recherche dans la documentation… (jusqu'à une minute)</p>}
          </div>

          <div className="border-t border-line p-4">
            <div className="flex flex-wrap gap-2">
              {suggestions.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  disabled={!canAsk || loading}
                  className="rounded-full border border-line px-3 py-1 text-xs text-gray-300 hover:border-accent hover:text-white disabled:opacity-50"
                >
                  {s}
                </button>
              ))}
            </div>
            <label className="mt-3 block text-xs text-muted" htmlFor="question">Votre question</label>
            <div className="mt-1 flex items-end gap-2">
              <textarea
                id="question"
                rows={2}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={onKeyDown}
                disabled={!canAsk}
                placeholder={canAsk ? 'Ex. : comment rejouer le playbook de remédiation à la main ?' : 'Réservé au rôle operator'}
                className="flex-1 resize-none rounded-md border border-line bg-bg px-3 py-2 text-sm outline-none placeholder:text-muted focus:border-accent disabled:opacity-50"
              />
              <button
                onClick={() => send(input)}
                disabled={!canAsk || loading || input.trim().length < 3}
                className="inline-flex items-center gap-1.5 rounded-md bg-accent px-4 py-2.5 text-xs font-medium text-bg hover:brightness-110 disabled:opacity-50"
              >
                Envoyer <ArrowRight size={14} />
              </button>
            </div>
            <p className="mt-2 text-[11px] text-muted">
              L'assistant aide à comprendre et à consulter les procédures. Il n'exécute aucune action sur la plateforme.
            </p>
          </div>
        </section>

        {/* Colonne de droite */}
        <aside className="space-y-4">
          <SourcesPanel sources={sources} />
          <ConfigPanel />
        </aside>
      </div>
    </div>
  )
}
