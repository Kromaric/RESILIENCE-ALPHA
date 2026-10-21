import { AlertTriangle } from 'lucide-react'
import Card from '../Card'
import { config } from '../../data/assistant'

export default function ConfigPanel() {
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
        {/* Pas de route de réindexation : l'index est reconstruit au démarrage si docs/ a changé */}
        <p className="mt-4 border-t border-line pt-3 text-[11px] text-muted">
          Index reconstruit au démarrage de l'assistant si la documentation a changé : modifier docs/, puis
          redémarrer le conteneur assistant-rag.
        </p>
      </Card>

      <div className="flex gap-2 rounded-lg border border-warn/40 bg-warn/10 p-3 text-xs text-gray-200">
        <AlertTriangle size={14} className="mt-0.5 shrink-0 text-warn" />
        <p>
          Lecture seule : aucun accès au moteur de remédiation, au socket Docker, à Vault ni à MariaDB. Les
          journaux gardent la taille de la question et les sources citées, jamais son texte.
        </p>
      </div>
    </>
  )
}
