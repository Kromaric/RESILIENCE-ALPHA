export default function SectionTitle({ children, right }) {
  return (
    <div className="mt-8 mb-3 flex flex-wrap items-baseline justify-between gap-2">
      <h2 className="text-base font-semibold text-gray-100">{children}</h2>
      {right && <div className="text-xs text-muted">{right}</div>}
    </div>
  )
}