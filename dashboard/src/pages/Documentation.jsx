import { useEffect, useState } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import { Check, Search } from 'lucide-react'
import { sections, pages, defaultPage, findPage, linkedPages } from '../data/docs'
import Badge from '../components/Badge'
import Card from '../components/Card'
import DocNav from '../components/docs/DocNav'
import MarkdownPage from '../components/docs/MarkdownPage'

export default function Documentation() {
  const [query, setQuery] = useState('')
  const path = useParams()['*']
  const { hash } = useLocation()
  const page = findPage(path) ?? defaultPage
  const related = linkedPages(page)

  // Nouvelle page : en haut, ou sur l'ancre demandée (#section, lien depuis l'assistant)
  useEffect(() => {
    const target = hash && document.getElementById(decodeURIComponent(hash.slice(1)))
    if (target) target.scrollIntoView()
    else window.scrollTo(0, 0)
  }, [page.path, hash])

  return (
    <div className="mx-auto max-w-7xl">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-gray-100">Documentation technique</h1>
          <p className="mt-1 text-xs text-muted">
            Dépôt Git · dossier /docs · {pages.length} pages · corpus indexé par l'assistant RAG
          </p>
        </div>
        <label className="w-full sm:w-80">
          <span className="mb-1 block text-xs text-muted">Rechercher dans la documentation</span>
          <div className="flex items-center gap-2 rounded-md border border-line bg-surface px-3 py-2 focus-within:border-accent">
            <Search size={14} className="text-muted" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="SC-01, PaymentAnomaly, Vault, RTO…"
              className="w-full bg-transparent text-sm outline-none placeholder:text-muted"
            />
          </div>
        </label>
      </header>

      <div className="mt-6 grid gap-4 lg:grid-cols-[220px_1fr] xl:grid-cols-[220px_1fr_220px]">
        <DocNav sections={sections} active={page.path} query={query} />

        <Card className="min-w-0 p-6 lg:p-8">
          <div className="mb-4 flex flex-wrap items-center gap-2">
            <p className="font-mono text-xs text-muted">docs/{page.path}</p>
            <Badge tone="ok" icon={Check}>Indexé dans l'assistant</Badge>
          </div>
          <MarkdownPage page={page} />
        </Card>

        <aside className="hidden space-y-4 xl:block xl:sticky xl:top-6 xl:self-start">
          {page.toc.length > 0 && (
            <div>
              <p className="mb-2 text-[11px] uppercase tracking-wider text-muted">Sur cette page</p>
              <ul className="space-y-1.5 text-xs">
                {page.toc.map((item) => (
                  <li key={item.id}>
                    <a href={`#${item.id}`} className="text-gray-400 hover:text-accent">
                      {item.title}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <Card>
            <p className="text-sm font-medium text-gray-100">Une question sur cette page ?</p>
            <p className="mt-1 text-xs text-muted">
              L'assistant répond à partir de la documentation et cite ses sources.
            </p>
            <Link
              to="/assistant"
              state={{ question: `À propos de « ${page.title} » : ` }}
              className="mt-3 block rounded-md bg-accent px-3 py-2 text-center text-xs font-medium text-bg hover:brightness-110"
            >
              Demander à l'assistant
            </Link>
          </Card>

          {related.length > 0 && (
            <Card>
              <p className="mb-2 text-sm font-medium text-gray-100">Pages liées</p>
              <ul className="space-y-1.5 text-xs">
                {related.slice(0, 6).map((p) => (
                  <li key={p.path}>
                    <Link to={`/docs/${p.path}`} className="text-accent hover:underline">
                      {p.title}
                    </Link>
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </aside>
      </div>
    </div>
  )
}
