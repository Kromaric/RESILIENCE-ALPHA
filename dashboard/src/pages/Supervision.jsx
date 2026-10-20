import { useState, useMemo } from 'react'
import { ArrowUpRight } from 'lucide-react'
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
import { LatencyChart, AnomalyChart, TransactionsChart } from '../components/supervision/Charts'

export default function Supervision() {
  const [phase, setPhase] = useState('apres')
  const data = phases[phase]
  const series = useMemo(() => getSeries(phase), [phase])
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

      <SectionTitle>Indicateurs clés</SectionTitle>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        {data.kpis.map((kpi) => (
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
        <ChartPanel title="Transactions par minute" source="Prometheus">
          <TransactionsChart {...series} />
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