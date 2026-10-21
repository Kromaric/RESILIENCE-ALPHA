// Données fictives des trois phases de l'incident INC-0007

function services({ payment, waf, remediation }) {
  return [
    { name: 'payment-api', desc: 'API métier de paiement · FastAPI', ...payment },
    { name: 'auth-service', desc: 'Authentification · JWT', status: 'ok', metric: '1 réplica · 40 ms' },
    { name: 'web-front', desc: 'Front de paiement · React', status: 'ok', metric: '200 OK' },
    { name: 'postgres', desc: 'Base de données des transactions', status: 'ok', metric: '14 connexions' },
    { name: 'waf', desc: 'Pare-feu applicatif · ModSecurity', status: 'ok', ...waf },
    { name: 'remediation-engine', desc: 'Moteur de remédiation · Ansible', status: 'ok', ...remediation },
  ]
}

export const phases = {
  avant: {
    status: { label: 'Opérationnel', tone: 'ok' },
    banner: {
      tone: 'ok',
      text: 'Tous les services sont opérationnels.',
      meta: 'Aucun incident ouvert',
    },
    kpis: [
      { label: 'Disponibilité (24 h)', value: '99,98 %', sub: 'Objectif ≥ 99,5 % tenu' },
      { label: 'Latence p95', value: '182 ms', sub: 'Seuil 800 ms' },
      { label: "Score d'anomalie", value: '0,09', sub: 'Sous le seuil 0,80', tone: 'ok' },
      { label: 'MTTR dernier incident', value: '3 min 40 s', sub: 'INC-0006', tone: 'ok' },
    ],
    services: services({
      payment: { status: 'ok', metric: '3/3 réplicas · 182 ms' },
      waf: { metric: '0 bloquée / min' },
      remediation: { metric: 'en veille' },
    }),
  },

  pendant: {
    status: { label: 'Incident en cours', tone: 'danger' },
    banner: {
      tone: 'danger',
      text: 'Anomalie détectée sur payment-api — remédiation automatique en cours.',
      meta: 'Ouvert à 10:42:07 · INC-0007',
    },
    kpis: [
      { label: 'Disponibilité (24 h)', value: '99,41 %', sub: 'Objectif ≥ 99,5 % menacé', tone: 'warn' },
      { label: 'Latence p95', value: '2 140 ms', sub: 'Seuil 800 ms dépassé', tone: 'danger' },
      { label: "Score d'anomalie", value: '0,94', sub: 'Au-dessus du seuil 0,80', tone: 'danger' },
      { label: 'MTTR dernier incident', value: 'en cours', sub: 'INC-0007', tone: 'warn' },
    ],
    services: services({
      payment: { status: 'down', metric: '502 · 2 140 ms' },
      waf: { status: 'warn', metric: '412 bloquées / min' },
      remediation: { status: 'warn', metric: 'playbook en cours' },
    }),
  },

  apres: {
    status: { label: 'Rétabli', tone: 'ok' },
    banner: {
      tone: 'ok',
      text: 'Service rétabli à 10:44:12. Vérifié par la transaction test tx_9c01e7aa.',
      meta: 'MTTR 2 min 05 s · INC-0007',
    },
    kpis: [
      { label: 'Disponibilité (24 h)', value: '99,69 %', sub: 'Objectif ≥ 99,5 % tenu' },
      { label: 'Latence p95', value: '196 ms', sub: 'Seuil 800 ms' },
      { label: "Score d'anomalie", value: '0,11', sub: 'Retour sous le seuil', tone: 'ok' },
      { label: 'MTTR dernier incident', value: '2 min 05 s', sub: 'INC-0007', tone: 'ok' },
    ],
    services: services({
      payment: { status: 'restored', metric: 'tx test OK · 196 ms' },
      waf: { metric: '3 bloquées / min' },
      remediation: { metric: 'dernier run OK' },
    }),
  },
}