import { Link } from 'react-router-dom'
import { normalize } from '../../data/docs'

// Navigation des pages de docs/ ; la recherche porte sur le titre et le contenu
export default function DocNav({ sections, active, query }) {
  const q = normalize(query.trim())
  const filtered = sections
    .map((s) => ({
      ...s,
      pages: s.pages.filter((p) => !q || normalize(p.title).includes(q) || normalize(p.content).includes(q)),
    }))
    .filter((s) => s.pages.length > 0)

  return (
    <nav className="rounded-lg border border-line bg-surface p-3 lg:sticky lg:top-6 lg:max-h-[calc(100vh-3rem)] lg:self-start lg:overflow-y-auto">
      {filtered.length === 0 && <p className="p-2 text-xs text-muted">Aucun résultat</p>}
      {filtered.map((section) => (
        <div key={section.title} className="mb-4 last:mb-0">
          <p className="mb-1 px-2 text-[11px] uppercase tracking-wider text-muted">{section.title}</p>
          {section.pages.map((page) => (
            <Link
              key={page.path}
              to={`/docs/${page.path}`}
              className={`block rounded-md px-2 py-1.5 text-sm transition ${
                active === page.path ? 'bg-accent/15 text-accent' : 'text-gray-300 hover:bg-bg'
              }`}
            >
              {page.title}
            </Link>
          ))}
        </div>
      ))}
    </nav>
  )
}
