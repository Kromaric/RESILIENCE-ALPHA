import { CheckCircle2, Loader2, Circle } from 'lucide-react'
import Card from '../Card'

const icons = {
  done: <CheckCircle2 size={18} className="text-ok" />,
  running: <Loader2 size={18} className="animate-spin text-warn" />,
  pending: <Circle size={18} className="text-line" />,
}

export default function RemediationChain({ steps, incidentId, notice }) {
  return (
    <Card>
      <div className="mb-4 flex items-baseline justify-between">
        <h3 className="text-sm font-medium text-gray-100">Chaîne de remédiation</h3>
        <p className="font-mono text-[11px] text-muted">{incidentId ?? 'aucun incident'}</p>
      </div>
      {notice && <p className="text-xs text-muted">{notice}</p>}
      <ol className="space-y-4">
        {steps.map((step) => (
          <li key={step.title} className={`flex gap-3 ${step.status === 'pending' ? 'opacity-40' : ''}`}>
            <span className="mt-0.5 shrink-0">{icons[step.status]}</span>
            <div>
              <p className="text-sm text-gray-100">
                {step.title}
                {step.status !== 'pending' && (
                  <span className="ml-2 font-mono text-[11px] text-muted">{step.time}</span>
                )}
              </p>
              <p className="mt-0.5 text-xs text-muted">{step.desc}</p>
            </div>
          </li>
        ))}
      </ol>
    </Card>
  )
}