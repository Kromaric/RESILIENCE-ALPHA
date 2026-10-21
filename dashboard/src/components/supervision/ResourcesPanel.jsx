export default function ResourcesPanel({ items }) {
  return (
    <div className="flex h-full flex-col justify-between">
      {items.map(({ label, value, percent }) => (
        <div key={label}>
          <div className="mb-1 flex justify-between text-xs">
            <span className="text-muted">{label}</span>
            <span className="font-mono text-gray-200">{value}</span>
          </div>
          <div className="h-1.5 rounded-full bg-line">
            <div
              className={`h-full rounded-full transition-all duration-500 ${percent > 80 ? 'bg-danger' : 'bg-accent'}`}
              style={{ width: `${percent ?? 0}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  )
}