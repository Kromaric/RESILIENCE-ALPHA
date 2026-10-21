import { useState, useMemo } from 'react'
import { ArrowUpRight, Check } from 'lucide-react'
import { useApi } from '../api/useApi'
import { formatInt, formatPercent } from '../api/format'
import { phases } from '../data/supervision'
import { getSeries, resources } from '../data/metrics'
import { getSteps, getLogs } from '../data/incident'
import Badge from '../components/Badge'
import SectionTitle from '../components/SectionTitle'
import PhaseToggle from '../components/supervision/PhaseToggle'
import IncidentBanner from '../components/supervision/IncidentBanner'
import KpiCard from '../components/supervision/KpiCard'
import ServiceCard from '../components/supervision/ServiceCard'
import ChartPanel from '../components/supervision/ChartPanel'
import ResourcesPanel from '../components/supervision/ResourcesPanel'
import RemediationChain from '../components/supervision/RemediationChain'
import LogViewer from '../components/supervision/LogViewer'
import LiveTag from '../components/supervision/LiveTag'
import { LatencyChart, AnomalyChart, TransactionsChart } from '../components/supervision/Charts'

// KPI alimentés par bo-api (GET /bo/data/summary), insérés parmi les KPI encore simulés
function liveKpis({ data, error }) {
  if (!data) {
    const pending = { value: error ? '—' : '…', sub: error ? error.message : 'Chargement…', tone: error ? 'warn' : undefined, live: true }
    return [
      { label: 'Taux de refus (24 h)', ...pending },
      { label: 'Transactions (24 h)', ...pending },
    ]
  }
  const ops = data.operations_24h
  const reason = ops.decline_reasons[0]
  return [
    {
      label: 'Taux de refus (24 h)',
      value: formatPercent(ops.decline_rate),
      sub: reason ? `Motif principal : ${reason.key}` : 'Aucun refus',
      live: true,
    },
    {
      label: 'Transactions (24 h)',
      value: formatInt(ops.count),
      sub: `${formatInt(data.operations_7d.count)} sur 7 jours`,
      live: true,
    },
  ]
}

// Contrôle de la partie double (GET /bo/data/ledger/check)
function LedgerBadge({ data, error }) {
  if (!data) return error ? <Badge tone="warn">Contrôle comptable indisponible</Badge> : null
  if (data.ok) return <Badge tone="ok" icon={Check}>Comptabilité cohérente</Badge>
  const anomalies =
    data.unbalanced_transactions.length +
    data.account_mismatches.length +
    data.negative_client_balances +
    data.entries_anomalies.length
  return <Badge tone="danger">{anomalies} anomalie(s) comptable(s)</Badge>
}

function PanelMessage({ error }) {
  return (
    <div className="flex h-full items-center justify-center text-center text-xs text-muted">
      {error ? error.message : 'Chargement…'}
    </div>
  )
}

export default function Supervision() {
  const [phase, setPhase] = useState('apres')
  const data = phases[phase]
  const series = useMemo(() => getSeries(phase), [phase])
  // Données réelles : elles ne dépendent pas de la phase simulée
  const summary = useApi('/bo/data/summary', { refreshMs: 5000 })
  const transactions = useApi('/bo/data/series?metric=transactions&interval=hour', { refreshMs: 30000 })
  const ledger = useApi('/bo/data/ledger/check', { refreshMs: 30000 })
  const kpis = [...data.kpis.slice(0, 2), ...liveKpis(summary), ...data.kpis.slice(2)]
  const logs = useMemo(() => getLogs(phase), [phase])

  return (
    <div className="mx-auto max-w-7xl">
      {/* En-tête */}
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-semibold text-gray-100">Supervision des services</h1>
            <Badge tone={data.status.tone}>{data.status.label}</Badge>
          </div>
          <p className="mt-1 text-xs text-muted">
            Plateforme de paiement Orbe · Mis à jour il y a 4 s · Source : Prometheus, Loki, moteur AIOps
          </p>
        </div>
        <div className="flex items-center gap-3">
          <PhaseToggle value={phase} onChange={setPhase} />
          <a
            href="http://localhost:3000"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-2 text-xs font-medium text-bg hover:brightness-110"
          >
            Ouvrir dans Grafana <ArrowUpRight size={14} />
          </a>
        </div>
      </header>

      <IncidentBanner {...data.banner} />

      <SectionTitle
        right={
          <span className="flex items-center gap-2">
            <LedgerBadge {...ledger} />
            <LiveTag />
          </span>
        }
      >
        Indicateurs clés
      </SectionTitle>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        {kpis.map((kpi) => (
          <KpiCard key={kpi.label} {...kpi} />
        ))}
      </div>

      <SectionTitle right="Docker Compose · 6 conteneurs surveillés">
        Services conteneurisés
      </SectionTitle>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {data.services.map((s) => (
          <ServiceCard key={s.name} {...s} />
        ))}
      </div>

      <SectionTitle right="Tableau « Resilience-Alpha / Paiement » · fenêtre 30 min · rafraîchi toutes les 5 s">
        Panneaux Grafana
      </SectionTitle>
      <div className="grid gap-3 lg:grid-cols-2">
        <ChartPanel title="Latence p95 — payment-api" source="Prometheus">
          <LatencyChart {...series} />
        </ChartPanel>
        <ChartPanel title="Score d'anomalie — modèle AIOps" source="Isolation Forest · seuil 0,80">
          <AnomalyChart {...series} />
        </ChartPanel>
        <ChartPanel title="Transactions par heure — 24 h" source="bo-api · base Orbe" live>
          {transactions.data ? (
            <TransactionsChart points={transactions.data.points} />
          ) : (
            <PanelMessage error={transactions.error} />
          )}
        </ChartPanel>
        <ChartPanel title="Ressources du PC Hôte" source="cAdvisor · node-exporter">
          <ResourcesPanel items={resources[phase]} />
        </ChartPanel>
      </div>

      <div className="mt-3 mb-8 grid gap-3 lg:grid-cols-2">
        <RemediationChain
          steps={getSteps(phase)}
          incidentId={phase === 'avant' ? null : 'INC-0007'}
        />
        <LogViewer logs={logs} />
      </div>
    </div>
  )
}