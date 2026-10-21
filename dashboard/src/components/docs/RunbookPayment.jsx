import { Check, Info } from 'lucide-react'
import Badge from '../Badge'
import CodeBlock from './CodeBlock'
import { playbook } from '../../data/docs'

const triggers = [
  ["Score d'anomalie", '≥ 0,80 pendant 2 fenêtres', 'aiops-detector'],
  ['Latence p95', '> 800 ms sur 60 s', 'Prometheus'],
  ['Erreurs 5xx', '> 2 % sur 60 s', 'Prometheus · Loki'],
  ['Requêtes bloquées WAF', '> 300 / min / IP', 'WAF · SIEM'],
]

function H2({ id, children }) {
  return (
    <h2 id={id} className="mt-8 mb-3 scroll-mt-6 text-lg font-semibold text-gray-100">
      {children}
    </h2>
  )
}

export default function RunbookPayment() {
  return (
    <article className="text-sm leading-relaxed text-gray-300">
      <p className="text-xs text-muted">Exploitation / Runbooks</p>
      <h1 className="mt-2 text-2xl font-semibold text-gray-100">
        Runbook — remédiation automatique de payment-api
      </h1>
      <p className="mt-2 text-xs text-muted">Version 1.3 · Mis à jour le 15/10/2026 · Rédigé par [NOM]</p>
      <div className="mt-2">
        <Badge tone="ok" icon={Check}>Indexé dans l'assistant</Badge>
      </div>

      <p className="mt-5">
        Ce runbook décrit la réponse automatique lorsque le modèle AIOps signale une anomalie sur
        payment-api. Le moteur de remédiation exécute la séquence sans intervention humaine ; ce
        document sert à comprendre, auditer et, en dernier recours, rejouer la procédure.
      </p>

      <H2 id="declencheurs">1. Déclencheurs</H2>
      <div className="overflow-x-auto rounded-lg border border-line">
        <table className="w-full text-left text-xs">
          <thead className="bg-bg text-muted">
            <tr>
              <th className="px-3 py-2 font-medium">Signal</th>
              <th className="px-3 py-2 font-medium">Seuil</th>
              <th className="px-3 py-2 font-medium">Source</th>
            </tr>
          </thead>
          <tbody>
            {triggers.map(([signal, seuil, source]) => (
              <tr key={signal} className="border-t border-line">
                <td className="px-3 py-2.5 text-gray-200">{signal}</td>
                <td className="px-3 py-2.5 font-mono">{seuil}</td>
                <td className="px-3 py-2.5 text-muted">{source}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <H2 id="sequence">2. Séquence automatique</H2>
      <ol className="list-decimal space-y-2 pl-5">
        <li>
          Le détecteur publie l'alerte{' '}
          <code className="rounded bg-bg px-1 font-mono text-xs text-accent">anomaly.payment-api</code>{' '}
          avec son score et ses variables explicatives.
        </li>
        <li>Le moteur de remédiation choisit la règle applicable (R-01 à R-05) et journalise sa décision dans le SIEM.</li>
        <li>Il applique une limitation de débit au WAF si la source est identifiée, puis lance le playbook Ansible.</li>
        <li>Il attend le healthcheck, puis exécute une transaction test avec une carte fictive.</li>
        <li>Il clôt l'incident seulement si la transaction test est autorisée et que les données sont cohérentes.</li>
      </ol>

      <H2 id="playbook">3. Playbook appelé</H2>
      <CodeBlock filename="ansible/playbooks/restart-payment.yml" code={playbook} />

      <H2 id="reprise">4. Critères de reprise</H2>
      <div className="flex gap-3 rounded-lg border border-blue-500/40 bg-blue-500/10 p-4 text-gray-200">
        <Info size={16} className="mt-0.5 shrink-0 text-blue-300" />
        <p>
          Un conteneur redémarré ne suffit pas. Le service n'est déclaré « Rétabli » qu'après une
          transaction test autorisée et une vérification de cohérence en base.
        </p>
      </div>

      <H2 id="escalade">5. Escalade manuelle</H2>
      <p>
        Si trois tentatives échouent en 10 minutes, le moteur s'arrête, ouvre un incident de niveau 2
        et notifie l'astreinte. Voir le{' '}
        <a href="#" className="text-accent underline underline-offset-2">PRA — scénario S2</a>.
      </p>
    </article>
  )
}