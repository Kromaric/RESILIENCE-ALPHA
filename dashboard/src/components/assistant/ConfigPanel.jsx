import { useState } from 'react'
import { Loader2, AlertTriangle } from 'lucide-react'
import Card from '../Card'
import { config } from '../../data/assistant'

export default function ConfigPanel() {
  const [reindexing, setReindexing] = useState(false)

  function reindex() {
    setReindexing(true)
    setTimeout(() => setReindexing(false), 1500) // simulation
  }

  return (
    <>
      <Card>
        <h3 className="mb-3 text-sm font-medium text-gray-100">Configuration</h3>
        <dl className="space-y-2 text-xs">
          {config.map(([key, value]) => (
            <div key={key} className="grid grid-cols-[100px_1fr] gap-2">
              <dt className="text-muted">{key}</dt>
              <dd className="font-mono text-gray-200">{value}</dd>
            </div>
          ))}
        </dl>
        <button
          onClick={reindex}
          disabled={reindexing}
          className="mt-4 flex w-full items-center justify-center gap-2 rounded-md border border-line py-2 text-xs text-gray-200 hover:bg-bg disabled:opacity-60"
        >
          {reindexing && <Loader2 size={12} className="animate-spin" />}
          {reindexing ? 'Réindexation…' : 'Réindexer la documentation'}
        </button>
      </Card>

      <div className="flex gap-2 rounded-lg border border-warn/40 bg-warn/10 p-3 text-xs text-gray-200">
        <AlertTriangle size={14} className="mt-0.5 shrink-0 text-warn" />
        <p>
          Accès séparé du moteur de remédiation : aucun droit sur Docker, Ansible ni Vault. Questions
          et réponses journalisées dans Loki.
        </p>
      </div>
    </>
  )
}