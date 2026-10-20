import Card from '../Card'

const toneText = { ok: 'text-ok', danger: 'text-danger', warn: 'text-warn' }

export default function KpiCard({ label, value, sub, tone }) {
  return (
    <Card>
      <p className="text-xs text-muted">{label}</p>
      <p className={`mt-2 font-mono text-2xl ${tone === 'danger' ? 'text-danger' : 'text-gray-100'}`}>
        {value}
      </p>
      <p className={`mt-1 text-[11px] ${toneText[tone] ?? 'text-muted'}`}>{sub}</p>
    </Card>
  )
}