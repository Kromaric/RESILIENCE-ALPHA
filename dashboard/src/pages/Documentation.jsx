import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Search } from 'lucide-react'
import { sections, runbookToc } from '../data/docs'
import Card from '../components/Card'
import DocNav from '../components/docs/DocNav'
import RunbookPayment from '../components/docs/RunbookPayment'

export default function Documentation() {
  const [query, setQuery] = useState('')
  const [page, setPage] = useState({ slug: 'runbook-payment', title: 'Runbook remédiation payment-api' })
  const isRunbook = page.slug === 'runbook-payment'

  return (
    <div className="mx-auto max-w-7xl">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-gray-100">Documentation technique</h1>
          <p className="mt-1 text-xs text-muted">
            Dépôt Git · dossier /docs · 38 pages · source indexée par l'assistant RAG
          </p>
        </div>
        <label className="w-full sm:w-80">
          <span className="mb-1 block text-xs text-muted">Rechercher dans la documentation</span>
          <div className="flex items-center gap-2 rounded-md border border-line bg-surface px-3 py-2 focus-within:border-accent">
            <Search size={14} className="text-muted" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="playbook, seuil, Vault, PRA…"
              className="w-full bg-transparent text-sm outline-none placeholder:text-muted"
            />
          </div>
        </label>
      </header>

      <div className="mt-6 grid gap-4 lg:grid-cols-[220px_1fr] xl:grid-cols-[220px_1fr_220px]">
        <DocNav sections={sections} active={page.slug} onSelect={setPage} query={query} />

        <Card className="p-6 lg:p-8">
          {isRunbook ? (
            <RunbookPayment />
          ) : (
            <div>
              <h1 className="text-2xl font-semibold text-gray-100">{page.title}</h1>
              <p className="mt-3 text-sm text-muted">
                Page en cours de rédaction. Elle sera reliée aux fichiers Markdown du dossier /docs.
              </p>
            </div>
          )}
        </Card>

        <aside className="hidden space-y-4 xl:block xl:sticky xl:top-6 xl:self-start">
          {isRunbook && (
            <div>
              <p className="mb-2 text-[11px] uppercase tracking-wider text-muted">Sur cette page</p>
              <ul className="space-y-1.5 text-xs">
                {runbookToc.map((item) => (
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
              className="mt-3 block rounded-md bg-accent px-3 py-2 text-center text-xs font-medium text-bg hover:brightness-110"
            >
              Demander à l'assistant
            </Link>
          </Card>

          <Card>
            <p className="mb-2 text-sm font-medium text-gray-100">Pages liées</p>
            <ul className="space-y-1.5 text-xs text-accent">
              <li>Observabilité : Prometheus, Grafana, Loki</li>
              <li>Modèle de détection AIOps</li>
              <li>PCA / PRA</li>
            </ul>
          </Card>
        </aside>
      </div>
    </div>
  )
}