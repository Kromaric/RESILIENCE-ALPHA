import Card from '../Card'

// Extraits de documentation cités par la dernière réponse de l'assistant
export default function SourcesPanel({ sources }) {
  return (
    <Card>
      <div className="mb-3 flex items-baseline justify-between">
        <h3 className="text-sm font-medium text-gray-100">Extraits retrouvés</h3>
        {sources.length > 0 && <span className="font-mono text-[11px] text-muted">{sources.length}</span>}
      </div>
      {sources.length === 0 ? (
        <p className="text-xs text-muted">Les extraits utilisés pour la dernière réponse s'afficheront ici.</p>
      ) : (
        <div className="space-y-2">
          {sources.map((s, i) => (
            <div key={i} className="rounded-md border border-line bg-bg p-3">
              <p className="text-xs text-gray-100">
                <span className="font-mono text-accent">[{i + 1}]</span> {s.doc}
              </p>
              <p className="mt-1.5 text-[11px] text-muted">« {s.extrait} »</p>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}
