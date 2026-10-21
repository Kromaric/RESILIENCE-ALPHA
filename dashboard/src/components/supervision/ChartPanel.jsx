import Card from '../Card'

export default function ChartPanel({ title, source, children }) {
  return (
    <Card>
      <div className="mb-3 flex items-baseline justify-between gap-2">
        <h3 className="text-sm font-medium text-gray-100">{title}</h3>
        <p className="font-mono text-[11px] text-muted">{source}</p>
      </div>
      <div className="h-48">{children}</div>
    </Card>
  )
}