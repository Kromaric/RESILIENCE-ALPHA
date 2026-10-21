import { useState, useRef, useEffect } from 'react'
import { ArrowRight, Lock } from 'lucide-react'
import { initialMessages, suggestions, mockAnswer } from '../data/assistant'
import Badge from '../components/Badge'
import ChatMessage from '../components/assistant/ChatMessage'
import SourcesPanel from '../components/assistant/SourcesPanel'
import ConfigPanel from '../components/assistant/ConfigPanel'

const now = () => new Date().toLocaleTimeString('fr-FR')

export default function Assistant() {
  const [messages, setMessages] = useState(initialMessages)
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const listRef = useRef(null)

  // Défile en bas à chaque nouveau message
  useEffect(() => {
    listRef.current.scrollTop = listRef.current.scrollHeight
  }, [messages, loading])

  function send(text) {
    const question = text.trim()
    if (!question || loading) return
    setMessages((m) => [...m, { role: 'user', time: now(), text: question }])
    setInput('')
    setLoading(true)
    setTimeout(() => {
      setMessages((m) => [...m, { role: 'assistant', time: now(), ...mockAnswer(question) }])
      setLoading(false)
    }, 1200)
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
          <Badge tone="ok">Modèle disponible</Badge>
          <Badge tone="accent" icon={Lock}>Lecture seule</Badge>
        </div>
      </header>

      <div className="mt-6 grid gap-4 xl:grid-cols-[1fr_320px]">
        {/* Chat */}
        <section className="flex h-[calc(100vh-9rem)] min-h-[560px] flex-col rounded-lg border border-line bg-surface">
          <div ref={listRef} className="flex-1 space-y-6 overflow-y-auto p-5">
            {messages.map((m, i) => (
              <ChatMessage key={i} message={m} />
            ))}
            {loading && <p className="pl-10 text-xs text-muted animate-pulse">L'assistant recherche dans la documentation…</p>}
          </div>

          <div className="border-t border-line p-4">
            <div className="flex flex-wrap gap-2">
              {suggestions.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="rounded-full border border-line px-3 py-1 text-xs text-gray-300 hover:border-accent hover:text-white"
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
                placeholder="Ex. : comment rejouer le playbook de remédiation à la main ?"
                className="flex-1 resize-none rounded-md border border-line bg-bg px-3 py-2 text-sm outline-none placeholder:text-muted focus:border-accent"
              />
              <button
                onClick={() => send(input)}
                disabled={loading || !input.trim()}
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
          <SourcesPanel />
          <ConfigPanel />
        </aside>
      </div>
    </div>
  )
}
