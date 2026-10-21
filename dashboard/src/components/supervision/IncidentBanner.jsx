import { CheckCircle2, AlertTriangle } from 'lucide-react'

const styles = {
  ok: 'border-ok/40 bg-ok/10 text-ok',
  danger: 'border-danger/40 bg-danger/10 text-danger',
}

export default function IncidentBanner({ tone, text, meta }) {
  const Icon = tone === 'ok' ? CheckCircle2 : AlertTriangle
  return (
    <div className={`mt-6 flex flex-wrap items-center justify-between gap-2 rounded-lg border px-4 py-3 ${styles[tone]}`}>
      <p className="flex items-center gap-2 text-sm text-gray-100">
        <Icon size={16} className="shrink-0" />
        {text}
      </p>
      <p className="font-mono text-xs opacity-80">{meta}</p>
    </div>
  )
}