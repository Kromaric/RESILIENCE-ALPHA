import Card from '../Card'
import LiveTag from './LiveTag'

const toneText = { ok: 'text-ok', danger: 'text-danger', warn: 'text-warn' }

export default function KpiCard({ label, value, sub, tone, live = false }) {
  return (
    <Card>
      <div className="flex items-start justify-between gap-2">
        <p className="text-xs text-muted">{label}</p>
        {live && <LiveTag />}
      </div>
      <p className={`mt-2 font-mono text-2xl ${tone === 'danger' ? 'text-danger' : 'text-gray-100'}`}>
        {value}
      </p>
      <p className={`mt-1 text-[11px] ${toneText[tone] ?? 'text-muted'}`}>{sub}</p>
    </Card>
  )
}
