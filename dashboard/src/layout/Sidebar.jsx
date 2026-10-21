import { NavLink, useLocation } from 'react-router-dom'
import { Activity, FileText, MessageSquare, ArrowUpRight } from 'lucide-react'
import { conversations } from '../data/assistant'

const espace = [
  { to: '/', label: 'Supervision', icon: Activity },
  { to: '/docs', label: 'Documentation', icon: FileText },
  { to: '/assistant', label: 'Assistant RAG', icon: MessageSquare },
]

const outils = [
  { label: 'Grafana', href: 'http://localhost:3000' },
  { label: 'Prometheus', href: 'http://localhost:9090' },
  { label: 'Loki — journaux', href: 'http://localhost:3100' },
]

function SectionLabel({ children }) {
  return (
    <p className="px-3 mt-6 mb-2 text-[11px] uppercase tracking-wider text-muted">
      {children}
    </p>
  )
}

export default function Sidebar() {
  const { pathname } = useLocation()
  const onAssistant = pathname === '/assistant'

  return (
    <aside className="hidden md:flex w-56 shrink-0 flex-col border-r border-line bg-bg p-4 md:sticky md:top-0 md:h-screen">
      <div className="px-1">
        <p className="text-2xl font-semibold text-accent">orbe</p>
        <p className="text-xs text-muted">Console équipe technique</p>
      </div>

      <SectionLabel>Espace</SectionLabel>
      <nav className="flex flex-col gap-1">
        {espace.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end
            className={({ isActive }) =>
              `flex items-center gap-2.5 rounded-md px-3 py-2 text-sm transition ${
                isActive ? 'bg-accent/15 text-accent' : 'text-gray-300 hover:bg-surface'
              }`
            }
          >
            <Icon size={16} />
            {label}
          </NavLink>
        ))}
      </nav>

      {onAssistant ? (
        <>
          <SectionLabel>Conversations</SectionLabel>
          <div className="flex flex-col gap-1">
            {conversations.map((c) => (
              <button
                key={c.id}
                className={`rounded-md px-3 py-2 text-left ${c.active ? 'bg-surface' : 'hover:bg-surface'}`}
              >
                <p className="text-xs text-gray-200">{c.title}</p>
                <p className="text-[11px] text-muted">{c.date}</p>
              </button>
            ))}
          </div>
        </>
      ) : (
        <>
          <SectionLabel>Outils</SectionLabel>
          <div className="flex flex-col gap-1">
            {outils.map(({ label, href }) => (
              <a
                key={label}
                href={href}
                target="_blank"
                rel="noreferrer"
                className="flex items-center justify-between rounded-md px-3 py-1.5 text-xs text-muted hover:bg-surface hover:text-gray-200"
              >
                {label}
                <ArrowUpRight size={12} />
              </a>
            ))}
          </div>
        </>
      )}

      <div className="mt-auto rounded-md border border-line p-3 text-xs">
        <p className="text-muted">Environnement de démo</p>
        <p className="mt-1 font-mono text-gray-200">PC Hôte · 192.168.137.1</p>
        <p className="mt-1 text-muted">Données fictives uniquement</p>
      </div>
    </aside>
  )
}