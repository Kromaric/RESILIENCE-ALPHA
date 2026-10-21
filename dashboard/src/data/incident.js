// Déroulé fictif de l'incident INC-0007
const order = { avant: 0, pendant: 1, apres: 2 }

const steps = [
  { title: 'Détection', time: '10:42:07', desc: 'Score 0,94 sur payment-api (latence, 5xx, débit entrant)' },
  { title: 'Décision', time: '10:42:09', desc: 'Règle R-03 : saturation applicative → redémarrage + limitation de débit WAF' },
  { title: 'Action', time: '10:42:11', desc: 'Playbook Ansible restart-payment.yml · règle WAF rate-limit appliquée' },
  { title: 'Vérification', time: '10:44:10', desc: 'Healthcheck OK puis transaction test tx_9c01e7aa autorisée' },
  { title: 'Clôture', time: '10:44:12', desc: 'Service rétabli · rapport envoyé au SIEM' },
]

// avant : rien n'a commencé · pendant : l'action est en cours · après : tout est fait
export function getSteps(phase) {
  return steps.map((step, i) => {
    let status = 'pending'
    if (phase === 'apres') status = 'done'
    if (phase === 'pendant') status = i < 2 ? 'done' : i === 2 ? 'running' : 'pending'
    return { ...step, status }
  })
}

const logs = [
  { phase: 'avant', time: '10:39:58.102', level: 'INFO', source: 'payment-api', msg: 'healthcheck /health · 3/3 réplicas OK' },
  { phase: 'avant', time: '10:40:30.441', level: 'INFO', source: 'waf', msg: '0 requête bloquée sur la dernière minute' },
  { phase: 'avant', time: '10:41:12.876', level: 'INFO', source: 'aiops', msg: 'score 0,09 · payment-api nominal' },
  { phase: 'pendant', time: '10:41:48.310', level: 'WARN', source: 'waf', msg: '286 requêtes bloquées / min depuis 203.0.113.42' },
  { phase: 'pendant', time: '10:42:01.552', level: 'ERROR', source: 'payment-api', msg: '502 Bad Gateway · upstream timeout (2 140 ms)' },
  { phase: 'pendant', time: '10:42:07.004', level: 'ALERT', source: 'aiops', msg: 'anomaly.payment-api · score 0,94' },
  { phase: 'pendant', time: '10:42:09.120', level: 'ACTION', source: 'remediation', msg: 'règle R-03 sélectionnée · décision journalisée dans le SIEM' },
  { phase: 'pendant', time: '10:42:11.044', level: 'ACTION', source: 'remediation', msg: 'ansible-playbook restart-payment.yml lancé' },
  { phase: 'apres', time: '10:43:58.611', level: 'INFO', source: 'payment-api', msg: 'healthcheck /health · 3/3 réplicas prêts' },
  { phase: 'apres', time: '10:44:10.227', level: 'INFO', source: 'remediation', msg: 'transaction test tx_9c01e7aa autorisée · 196 ms' },
  { phase: 'apres', time: '10:44:12.003', level: 'INFO', source: 'remediation', msg: 'INC-0007 clos · service rétabli et vérifié' },
  { phase: 'apres', time: '10:44:12.090', level: 'INFO', source: 'siem', msg: 'rapport INC-0007 archivé' },
]

// On affiche les journaux jusqu'à la phase choisie
export function getLogs(phase) {
  return logs.filter((log) => order[log.phase] <= order[phase])
}