export default function DocNav({ sections, active, onSelect, query }) {
  const q = query.trim().toLowerCase()
  const filtered = sections
    .map((s) => ({ ...s, pages: s.pages.filter((p) => p.title.toLowerCase().includes(q)) }))
    .filter((s) => s.pages.length > 0)

  return (
    <nav className="rounded-lg border border-line bg-surface p-3 lg:sticky lg:top-6 lg:self-start">
      {filtered.length === 0 && <p className="p-2 text-xs text-muted">Aucun résultat</p>}
      {filtered.map((section) => (
        <div key={section.title} className="mb-4 last:mb-0">
          <p className="mb-1 px-2 text-[11px] uppercase tracking-wider text-muted">{section.title}</p>
          {section.pages.map((page) => (
            <button
              key={page.slug}
              onClick={() => onSelect(page)}
              className={`block w-full rounded-md px-2 py-1.5 text-left text-sm transition ${
                active === page.slug ? 'bg-accent/15 text-accent' : 'text-gray-300 hover:bg-bg'
              }`}
            >
              {page.title}
            </button>
          ))}
        </div>
      ))}
    </nav>
  )
}