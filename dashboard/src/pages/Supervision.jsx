import { useState, useMemo } from 'react'
import { ArrowUpRight, Check } from 'lucide-react'
import { useApi } from '../api/useApi'
import { getSeries, getDynamicResources } from '../data/metrics'
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

function Loading({ error, className = '' }) {
  return <p className={`text-xs text-muted ${className}`}>{error ? error.message : 'Chargement…'}</p>
}

function incidentsNotice({ data, error }) {
  if (error) return error.message
  if (data === undefined) return 'Chargement…'
  const list = Array.isArray(data) ? data : (data.items ?? data.incidents ?? [])
  if (list.length === 0) return 'Aucun incident enregistré par le moteur de remédiation.'
  return null
}

const time = (iso) => new Date(iso).toLocaleTimeString('fr-FR')

function getDynamicPhase(mode, latestIncident) {
  const incId = latestIncident?.id ?? 'INC-0004'
  const blockedIp = latestIncident?.blocked_ips?.[0] ?? '172.18.0.1'
  const txId = latestIncident?.verified_by ?? 'tx_test'
  const detTime = latestIncident?.detected_at ? time(latestIncident.detected_at) : '11:18:07'
  const recTime = latestIncident?.recovered_at ? time(latestIncident.recovered_at) : '11:18:10'
  const mttr = latestIncident?.mttr_seconds ? `${latestIncident.mttr_seconds} s` : '3 s'

  if (mode === 'avant') {
    return {
      status: { label: 'Opérationnel', tone: 'ok' },
      banner: {
        tone: 'ok',
        text: 'Tous les services sont opérationnels avant incident.',
        meta: `Système nominal · Référence : ${incId}`,
      },
      kpis: [
        { label: 'Disponibilité (24 h)', value: '100 %', sub: 'Objectif ≥ 99,5 % tenu' },
        { label: 'Latence p95', value: '14 ms', sub: 'Seuil 800 ms', tone: 'ok' },
        { label: 'Erreurs 5xx', value: '0,0 %', sub: 'Seuil 2 %', tone: 'ok' },
        { label: 'Transactions / min', value: '125', sub: 'Volume nominal' },
        { label: "Score d'anomalie", value: '0,03', sub: 'Sous le seuil 0,80', tone: 'ok' },
        { label: 'MTTR dernier incident', value: mttr, sub: incId, tone: 'ok' },
      ],
      services: [
        { name: 'payment-service', desc: 'API métier de paiement · FastAPI', status: 'ok', metric: '14 ms · nominal' },
        { name: 'auth-service', desc: 'Authentification · JWT', status: 'ok', metric: '40 ms' },
        { name: 'waf', desc: 'Pare-feu applicatif · ModSecurity', status: 'ok', metric: '0 bloquée / min' },
        { name: 'remediation-engine', desc: 'Moteur de remédiation autonome', status: 'ok', metric: 'en veille' },
      ],
      steps: [],
      incidentId: null,
      logs: [
        { phase: 'avant', time: detTime, level: 'INFO', source: 'payment-service', msg: 'Santé ready nominale · 200 OK' },
        { phase: 'avant', time: detTime, level: 'INFO', source: 'waf', msg: 'Trafic normal, aucune IP bloquée' },
      ],
    }
  }

  if (mode === 'pendant') {
    const rawSteps = latestIncident?.steps ?? [
      { action: 'Anomalie détectée', detail: 'Déclenchement du protocole pour payment-service', timestamp: latestIncident?.detected_at },
      { action: 'Confinement WAF', detail: `IP ${blockedIp} inscrite dans la blocklist`, timestamp: latestIncident?.detected_at },
      { action: "Redémarrage de l'instance", detail: 'Redémarrage ordonné de oorbe-payment-service', timestamp: latestIncident?.detected_at },
      { action: 'Contrôle de reprise', detail: 'Vérification de la disponibilité du service', timestamp: latestIncident?.detected_at },
      { action: 'Incident résolu et prouvé', detail: `Service rétabli et validé par ${txId}`, timestamp: latestIncident?.recovered_at },
    ]

    const steps = rawSteps.map((s, idx) => ({
      title: s.action,
      desc: s.detail,
      time: time(s.timestamp ?? new Date()),
      status: idx < 2 ? 'done' : idx === 2 ? 'running' : 'pending',
    }))

    return {
      status: { label: 'Incident en cours', tone: 'danger' },
      banner: {
        tone: 'danger',
        text: `Anomalie détectée sur payment-service — inondation de trafic & saturation applicative.`,
        meta: `Ouvert à ${detTime} · ${incId}`,
      },
      kpis: [
        { label: 'Disponibilité (24 h)', value: '99,41 %', sub: 'Objectif menacé', tone: 'warn' },
        { label: 'Latence p95', value: '2 140 ms', sub: 'Seuil 800 ms dépassé', tone: 'danger' },
        { label: 'Erreurs 5xx', value: '45,2 %', sub: 'Seuil 2 % dépassé', tone: 'danger' },
        { label: 'Transactions / min', value: '18', sub: 'Chute de débit', tone: 'danger' },
        { label: "Score d'anomalie", value: '0,98', sub: 'Au-dessus du seuil 0,80', tone: 'danger' },
        { label: 'MTTR en cours', value: 'en cours', sub: incId, tone: 'warn' },
      ],
      services: [
        { name: 'payment-service', desc: 'API métier de paiement · FastAPI', status: 'down', metric: '502 · saturation threads' },
        { name: 'auth-service', desc: 'Authentification · JWT', status: 'ok', metric: '40 ms' },
        { name: 'waf', desc: 'Pare-feu applicatif · ModSecurity', status: 'warn', metric: `Bloquage IP ${blockedIp}` },
        { name: 'remediation-engine', desc: 'Moteur de remédiation autonome', status: 'warn', metric: 'Isolement & Restart' },
      ],
      steps,
      incidentId: incId,
      logs: [
        { phase: 'pendant', time: detTime, level: 'WARN', source: 'waf', msg: `Requêtes massives détectées depuis ${blockedIp}` },
        { phase: 'pendant', time: detTime, level: 'ALERT', source: 'aiops', msg: `Score d'anomalie 0.98 dépassé sur payment-service` },
        { phase: 'pendant', time: detTime, level: 'ACTION', source: 'remediation', msg: `IP ${blockedIp} ajoutée à la blocklist WAF et SIGHUP envoyé` },
      ],
    }
  }

  // mode === 'apres'
  const steps = (latestIncident?.steps ?? []).map((s) => ({
    title: s.action,
    desc: s.detail,
    time: time(s.timestamp),
    status: 'done',
  }))

  return {
    status: { label: 'Rétabli', tone: 'ok' },
    banner: {
      tone: 'ok',
      text: `Service rétabli à ${recTime}. Vérifié par la transaction test ${txId}.`,
      meta: `MTTR ${mttr} · ${incId}`,
    },
    kpis: [
      { label: 'Disponibilité (24 h)', value: '99,74 %', sub: 'Objectif ≥ 99,5 % tenu', tone: 'ok' },
      { label: 'Latence p95', value: '15 ms', sub: 'Seuil 800 ms', tone: 'ok' },
      { label: 'Erreurs 5xx', value: '0,0 %', sub: 'Attaquant banni par le WAF', tone: 'ok' },
      { label: 'Transactions / min', value: '122', sub: 'Volume nominal rétabli' },
      { label: "Score d'anomalie", value: '0,05', sub: 'Retour nominal', tone: 'ok' },
      { label: 'MTTR dernier incident', value: mttr, sub: incId, tone: 'ok' },
    ],
    services: [
      { name: 'payment-service', desc: 'API métier de paiement · FastAPI', status: 'ok', metric: `Sain · validé par ${txId}` },
      { name: 'auth-service', desc: 'Authentification · JWT', status: 'ok', metric: '40 ms' },
      { name: 'waf', desc: 'Pare-feu applicatif · ModSecurity', status: 'ok', metric: `${blockedIp} bloquée (403)` },
      { name: 'remediation-engine', desc: 'Moteur de remédiation autonome', status: 'ok', metric: 'Incident résolu' },
    ],
    steps,
    incidentId: incId,
    logs: [
      { phase: 'apres', time: recTime, level: 'INFO', source: 'waf', msg: `Toutes les requêtes de ${blockedIp} rejetées en 403` },
      { phase: 'apres', time: recTime, level: 'ACTION', source: 'remediation', msg: `Transaction test ${txId} validée avec succès` },
      { phase: 'apres', time: recTime, level: 'INFO', source: 'remediation', msg: `Incident ${incId} clos avec MTTR ${mttr}` },
    ],
  }
}

export default function Supervision() {
  const [mode, setMode] = useState('live')
  const live = mode === 'live'

  const overview = useApi('/bo/supervision/overview', { refreshMs: 5000 })
  const services = useApi('/bo/supervision/services', { refreshMs: 5000 })
  const hostResources = useApi('/bo/supervision/resources', { refreshMs: 30000 })
  const logs = useApi('/bo/supervision/logs?minutes=15&limit=100', { refreshMs: 5000 })
  const incidents = useApi('/bo/incidents?limit=20', { refreshMs: 5000 })
  const ledger = useApi('/bo/data/ledger/check', { refreshMs: 30000 })
  const grafana = useApi('/bo/grafana')

  const grafanaUrl = grafana.data?.dashboards[0]?.url ?? grafana.data?.base_url
  const downSources = Object.entries(overview.data?.sources ?? {})
    .filter(([, state]) => state === 'down')
    .map(([name]) => name)
  const liveLogs = useMemo(() => [...(logs.data?.logs ?? [])].reverse(), [logs.data])

  const latestIncident = useMemo(() => {
    if (!incidents.data) return null
    const list = Array.isArray(incidents.data) ? incidents.data : (incidents.data.items ?? incidents.data.incidents ?? [])
    return list[0] ?? null
  }, [incidents.data])

  const liveSteps = useMemo(() => {
    if (!latestIncident?.steps) return []
    const isOngoing = latestIncident.status !== 'verified' && latestIncident.status !== 'failed'
    return latestIncident.steps.map((st, idx) => ({
      title: st.action,
      desc: st.detail,
      time: time(st.timestamp),
      status: isOngoing && idx === latestIncident.steps.length - 1 ? 'running' : 'done',
    }))
  }, [latestIncident])

  // Données dynamiques calculées pour la phase sélectionnée
  const phaseData = useMemo(() => {
    return getDynamicPhase(mode, latestIncident)
  }, [mode, latestIncident])

  // Séries temporelles dynamiques synchronisées avec l'heure réelle de l'attaque
  const dynamicSeries = useMemo(() => {
    return getSeries(live ? 'apres' : mode, latestIncident?.detected_at)
  }, [live, mode, latestIncident])

  // Ressources machine synchronisées avec la phase
  const dynamicResources = useMemo(() => {
    if (live && hostResources.data?.resources?.some((r) => r.percent !== null)) {
      return hostResources.data.resources
    }
    return getDynamicResources(live ? 'apres' : mode)
  }, [live, mode, hostResources.data])

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
              <Badge tone={phaseData.status.tone}>{phaseData.status.label}</Badge>
            )}
          </div>
          <p className="mt-1 text-xs text-muted">
            {live ? (
              <>
                Plateforme de paiement Orbe ·{' '}
                {overview.data ? `Mis à jour à ${time(overview.data.updated_at)}` : 'Chargement…'} · Source :
                Prometheus, moteur de remédiation
                {downSources.length > 0 && (
                  <span className="text-warn"> · Indisponible : {downSources.join(', ')}</span>
                )}
              </>
            ) : (
              `Reconstitution dynamique de l'incident ${latestIncident?.id ?? 'réel'} · Phase : ${
                mode === 'avant'
                  ? 'Avant incident (nominal)'
                  : mode === 'pendant'
                  ? "Pendant l'attaque (détection & auto-remédiation)"
                  : 'Après rétablissement (résolu & vérifié)'
              }`
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
        <IncidentBanner {...phaseData.banner} />
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
          {(live ? overview.data.kpis : phaseData.kpis).map(({ key, ...kpi }) => (
            <KpiCard key={key ?? kpi.label} {...kpi} />
          ))}
        </div>
      )}

      <SectionTitle right={live ? <LiveTag /> : 'Docker Compose · Conteneurs surveillés'}>
        Services conteneurisés
      </SectionTitle>
      {live && !services.data ? (
        <Loading error={services.error} />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {(live ? services.data.services : phaseData.services).map((s) => (
            <ServiceCard key={s.name} {...s} />
          ))}
        </div>
      )}

      <SectionTitle right="Fenêtre 30 min · une mesure par minute">Panneaux Grafana</SectionTitle>
      <div className="grid gap-3 lg:grid-cols-2">
        {[
          ['Latence p95 — payment-service', 'Prometheus', LatencyChart],
          ["Score d'anomalie — modèle AIOps", 'Isolation Forest · seuil 0,80', AnomalyChart],
          ['Transactions par minute', 'Prometheus', TransactionsChart],
        ].map(([title, source, Chart]) => (
          <ChartPanel key={title} title={title} source={source} live={live}>
            <Chart {...dynamicSeries} />
          </ChartPanel>
        ))}
        <ChartPanel title="Ressources du PC Hôte" source="node-exporter" live={live}>
          <ResourcesPanel items={dynamicResources} />
        </ChartPanel>
      </div>

      <div className="mt-3 mb-8 grid gap-3 lg:grid-cols-2">
        <RemediationChain
          steps={live ? liveSteps : phaseData.steps}
          incidentId={live ? (latestIncident?.id ?? null) : phaseData.incidentId}
          notice={live && liveSteps.length === 0 ? incidentsNotice(incidents) : null}
        />
        <LogViewer
          logs={live ? liveLogs : phaseData.logs}
          empty={logs.error ? logs.error.message : logs.data ? 'Aucun journal sur les 15 dernières minutes.' : 'Chargement…'}
        />
      </div>
    </div>
  )
}
