import Card from '../Card'
import LiveTag from './LiveTag'

export default function ChartPanel({ title, source, live = false, children }) {
  return (
    <Card>
      <div className="mb-3 flex items-baseline justify-between gap-2">
        <h3 className="flex items-center gap-2 text-sm font-medium text-gray-100">
          {title}
          {live && <LiveTag />}
        </h3>
        <p className="font-mono text-[11px] text-muted">{source}</p>
      </div>
      <div className="h-48">{children}</div>
    </Card>
  )
}
