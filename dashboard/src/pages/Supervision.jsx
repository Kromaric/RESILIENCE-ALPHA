import { useState, useMemo } from 'react'
import { ArrowUpRight, Check } from 'lucide-react'
import { useApi } from '../api/useApi'
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

function Loading({ error, className = '' }) {
  return <p className={`text-xs text-muted ${className}`}>{error ? error.message : 'Chargement…'}</p>
}

// La remédiation est relayée telle quelle par bo-api : son format n'est pas encore défini
// par le moteur, on n'affiche donc que l'état de la source.
function incidentsNotice({ data, error }) {
  if (error) return error.message
  if (data === undefined) return 'Chargement…'
  const list = Array.isArray(data) ? data : (data.items ?? data.incidents ?? [])
  if (list.length === 0) return 'Aucun incident enregistré par le moteur de remédiation.'
  return `${list.length} incident(s) enregistré(s). Le détail des étapes sera affiché quand le format du moteur sera fixé.`
}

const time = (iso) => new Date(iso).toLocaleTimeString('fr-FR')

export default function Supervision() {
  // « live » : données de bo-api ; « avant / pendant / apres » : démonstration simulée
  const [mode, setMode] = useState('live')
  const live = mode === 'live'
  const demo = phases[live ? 'apres' : mode]
  const demoSeries = useMemo(() => getSeries(live ? 'apres' : mode), [live, mode])
  const demoLogs = useMemo(() => getLogs(live ? 'apres' : mode), [live, mode])

  const on = (path) => (live ? path : null)
  const overview = useApi(on('/bo/supervision/overview'), { refreshMs: 5000 })
  const services = useApi(on('/bo/supervision/services'), { refreshMs: 5000 })
  const series = useApi(on('/bo/supervision/series?minutes=30'), { refreshMs: 30000 })
  const hostResources = useApi(on('/bo/supervision/resources'), { refreshMs: 30000 })
  const logs = useApi(on('/bo/supervision/logs?minutes=15&limit=100'), { refreshMs: 5000 })
  const incidents = useApi(on('/bo/incidents?limit=20'), { refreshMs: 10000 })
  const ledger = useApi(on('/bo/data/ledger/check'), { refreshMs: 30000 })
  const grafana = useApi('/bo/grafana')

  const grafanaUrl = grafana.data?.dashboards[0]?.url ?? grafana.data?.base_url
  const downSources = Object.entries(overview.data?.sources ?? {})
    .filter(([, state]) => state === 'down')
    .map(([name]) => name)
  // bo-api renvoie les journaux du plus récent au plus ancien ; le lecteur défile vers le bas
  const liveLogs = useMemo(() => [...(logs.data?.logs ?? [])].reverse(), [logs.data])

  return (
    <div className="mx-auto max-w-7xl">
      {/* En-tête */}
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-semibold text-gray-100">Supervision des services</h1>
            {live ? (
              overview.data && <Badge tone={overview.data.status.tone}>{overview.data.status.label}</Badge>
            ) : (
              <Badge tone={demo.status.tone}>{demo.status.label}</Badge>
            )}
          </div>
          <p className="mt-1 text-xs text-muted">
            {live ? (
              <>
                Plateforme de paiement Orbe ·{' '}
                {overview.data ? `Mis à jour à ${time(overview.data.updated_at)}` : 'Chargement…'} · Source :
                Prometheus, Loki, moteur de remédiation
                {downSources.length > 0 && (
                  <span className="text-warn"> · Indisponible : {downSources.join(', ')}</span>
                )}
              </>
            ) : (
              'Mode démonstration · données simulées de l’incident INC-0007'
            )}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <PhaseToggle value={mode} onChange={setMode} />
          {grafanaUrl && (
            <a
              href={grafanaUrl}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-2 text-xs font-medium text-bg hover:brightness-110"
            >
              Ouvrir dans Grafana <ArrowUpRight size={14} />
            </a>
          )}
        </div>
      </header>

      {live ? (
        overview.data ? (
          <IncidentBanner {...overview.data.banner} />
        ) : (
          <Loading error={overview.error} className="mt-6" />
        )
      ) : (
        <IncidentBanner {...demo.banner} />
      )}

      <SectionTitle
        right={
          live && (
            <span className="flex items-center gap-2">
              <LedgerBadge {...ledger} />
              <LiveTag />
            </span>
          )
        }
      >
        Indicateurs clés
      </SectionTitle>
      {live && !overview.data ? (
        <Loading error={overview.error} />
      ) : (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
          {(live ? overview.data.kpis : demo.kpis).map((kpi) => (
            <KpiCard key={kpi.key ?? kpi.label} {...kpi} />
          ))}
        </div>
      )}

      <SectionTitle right={live ? <LiveTag /> : 'Docker Compose · 6 conteneurs surveillés'}>
        Services conteneurisés
      </SectionTitle>
      {live && !services.data ? (
        <Loading error={services.error} />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {(live ? services.data.services : demo.services).map((s) => (
            <ServiceCard key={s.name} {...s} />
          ))}
        </div>
      )}

      <SectionTitle right="Fenêtre 30 min · une mesure par minute">Panneaux Grafana</SectionTitle>
      <div className="grid gap-3 lg:grid-cols-2">
        {[
          ['Latence p95 — payment-api', 'Prometheus', LatencyChart],
          ["Score d'anomalie — modèle AIOps", 'Isolation Forest · seuil 0,80', AnomalyChart],
          ['Transactions par minute', 'Prometheus', TransactionsChart],
        ].map(([title, source, Chart]) => (
          <ChartPanel key={title} title={title} source={source} live={live}>
            {live ? (
              series.data ? <Chart {...series.data} /> : <PanelMessage error={series.error} />
            ) : (
              <Chart {...demoSeries} />
            )}
          </ChartPanel>
        ))}
        <ChartPanel title="Ressources du PC Hôte" source="node-exporter" live={live}>
          {live ? (
            hostResources.data ? (
              <ResourcesPanel items={hostResources.data.resources} />
            ) : (
              <PanelMessage error={hostResources.error} />
            )
          ) : (
            <ResourcesPanel items={resources[mode]} />
          )}
        </ChartPanel>
      </div>

      <div className="mt-3 mb-8 grid gap-3 lg:grid-cols-2">
        {live ? (
          <RemediationChain steps={[]} incidentId={null} notice={incidentsNotice(incidents)} />
        ) : (
          <RemediationChain steps={getSteps(mode)} incidentId={mode === 'avant' ? null : 'INC-0007'} />
        )}
        {live ? (
          <LogViewer
            logs={liveLogs}
            empty={logs.error ? logs.error.message : logs.data ? 'Aucun journal sur les 15 dernières minutes.' : 'Chargement…'}
          />
        ) : (
          <LogViewer logs={demoLogs} />
        )}
      </div>
    </div>
  )
}
