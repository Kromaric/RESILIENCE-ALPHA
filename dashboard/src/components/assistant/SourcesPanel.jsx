import Card from '../Card'
import { sources } from '../../data/assistant'

export default function SourcesPanel() {
  return (
    <Card>
      <div className="mb-3 flex items-baseline justify-between">
        <h3 className="text-sm font-medium text-gray-100">Extraits retrouvés</h3>
        <span className="font-mono text-[11px] text-muted">top 4</span>
      </div>
      <div className="space-y-2">
        {sources.map((s) => (
          <div key={s.n} className="rounded-md border border-line bg-bg p-3">
            <div className="flex justify-between text-xs">
              <span className="text-gray-100">
                <span className="font-mono text-accent">[{s.n}]</span> {s.title}
              </span>
              <span className="font-mono text-muted">{s.score.toFixed(2).replace('.', ',')}</span>
            </div>
            <p className="mt-1.5 text-[11px] text-muted">« {s.quote} »</p>
            <div className="mt-2 h-1 rounded-full bg-line">
              <div className="h-full rounded-full bg-accent" style={{ width: `${s.score * 100}%` }} />
            </div>
          </div>
        ))}
      </div>
    </Card>
  )
}