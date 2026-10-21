import { Check } from 'lucide-react'
import Card from '../Card'
import Badge from '../Badge'

const statusBadge = {
  ok: { tone: 'ok', label: 'Opérationnel' },
  restored: { tone: 'ok', label: 'Rétabli', icon: Check },
  warn: { tone: 'warn', label: 'Sollicité' },
  down: { tone: 'danger', label: 'Incident' },
  unknown: { tone: 'unknown', label: 'Sans mesure' },
}

export default function ServiceCard({ name, desc, status, metric }) {
  const badge = statusBadge[status]
  return (
    <Card className={status === 'down' ? 'border-danger/50' : ''}>
      <div className="flex items-start justify-between gap-2">
        <p className="font-mono text-sm font-medium text-gray-100">{name}</p>
        <Badge tone={badge.tone} icon={badge.icon}>{badge.label}</Badge>
      </div>
      <p className="mt-2 text-xs text-muted">{desc}</p>
      <p className="mt-3 font-mono text-[11px] text-gray-400">{metric}</p>
    </Card>
  )
}