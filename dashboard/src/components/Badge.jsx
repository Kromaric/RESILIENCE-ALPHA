const tones = {
  ok: 'bg-ok/15 text-ok border-ok/30',
  danger: 'bg-danger/15 text-danger border-danger/30',
  warn: 'bg-warn/15 text-warn border-warn/30',
  accent: 'bg-accent/15 text-accent border-accent/30',
  unknown: 'bg-line/40 text-muted border-line',
}

export default function Badge({ tone = 'ok', icon: Icon, children }) {
  return (
    <span
      className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full border px-2 py-0.5 text-[11px] font-medium ${tones[tone]}`}
    >
      {Icon ? <Icon size={11} /> : <span className="size-1.5 rounded-full bg-current" />}
      {children}
    </span>
  )
}