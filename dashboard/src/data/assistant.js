export const conversations = [
  { id: 1, title: '502 sur payment-api', date: "aujourd'hui · 10:43", active: true },
  { id: 2, title: 'Rotation des secrets Vault', date: 'hier' },
  { id: 3, title: 'Seuils du modèle AIOps', date: '16/10' },
]

export const citationLabels = {
  1: 'Runbook remédiation payment-api §1–2',
  2: 'Playbooks Ansible · restart-payment.yml',
  3: 'PCA / PRA · scénario S2',
  4: 'Modèle AIOps · seuils',
}

export const sources = [
  { n: 1, title: 'Runbook payment-api', score: 0.91, quote: 'Le moteur choisit la règle applicable (R-01 à R-05) et journalise sa décision dans le SIEM…' },
  { n: 2, title: 'restart-payment.yml', score: 0.87, quote: 'Redémarrer le service de façon contrôlée… attendre le healthcheck, 12 essais toutes les 5 s.' },
  { n: 3, title: 'PCA / PRA', score: 0.82, quote: "Si trois tentatives échouent en 10 minutes, ouverture d'un incident de niveau 2…" },
  { n: 4, title: 'Modèle AIOps', score: 0.74, quote: "Seuil d'alerte fixé à 0,80 sur deux fenêtres consécutives de 30 s." },
]

export const config = [
  ['Modèle', '[MODÈLE ≤ 8B] · Ollama'],
  ['Hébergement', 'PC Hôte ou PC délestage IA'],
  ['Embeddings', "[MODÈLE D'EMBEDDING]"],
  ['Base vectorielle', '[CHROMA / FAISS]'],
  ['Corpus', '/docs · runbooks · architecture · PCA/PRA'],
  ['Indexation', '15/10/2026 09:12'],
]

export const suggestions = [
  'Rejouer le playbook à la main',
  "Où voir le score d'anomalie ?",
  'Seuils de détection actuels',
]

export const initialMessages = [
  {
    role: 'user',
    time: '10:43:05',
    text: 'payment-api renvoie des 502 depuis deux minutes. Que fait le moteur de remédiation et à quel moment dois-je intervenir ?',
  },
  {
    role: 'assistant',
    time: '10:43:08',
    paragraphs: [
      "Le moteur de remédiation a déjà pris l'incident en charge : le score d'anomalie a franchi 0,80 à 10:42:07, ce qui déclenche la règle R-03 (saturation applicative) [1].",
      'Il applique une limitation de débit au WAF sur la source suspecte, puis lance le playbook restart-payment.yml, qui redémarre payment-api et attend le healthcheck [1][2].',
      "Le service ne sera déclaré rétabli qu'après une transaction test autorisée. Vous n'intervenez que si trois tentatives échouent en 10 minutes : le moteur s'arrête alors et ouvre un incident de niveau 2 [3].",
    ],
    citations: [1, 2, 3],
    meta: '4 extraits · 2,4 s',
  },
]

// Réponse simulée : à remplacer par l'appel à l'API Ollama + LangChain
export function mockAnswer(question) {
  const q = question.toLowerCase()

  if (q.includes('playbook') || q.includes('main')) {
    return {
      paragraphs: [
        'Pour rejouer la remédiation à la main, lancez depuis le PC Hôte : ansible-playbook ansible/playbooks/restart-payment.yml [2].',
        'Le playbook limite le débit au WAF, redémarre payment-api puis attend le healthcheck (12 essais toutes les 5 s) [2].',
        "Ne déclarez le service rétabli qu'après une transaction test autorisée et une vérification de cohérence en base [1].",
      ],
      citations: [1, 2],
      meta: '3 extraits · 2,1 s',
    }
  }
  if (q.includes('seuil')) {
    return {
      paragraphs: [
        "Seuils actuels : score d'anomalie ≥ 0,80 sur deux fenêtres de 30 s, latence p95 > 800 ms sur 60 s, erreurs 5xx > 2 % sur 60 s, WAF > 300 requêtes bloquées / min / IP [1][4].",
      ],
      citations: [1, 4],
      meta: '2 extraits · 1,8 s',
    }
  }
  if (q.includes('score') || q.includes('anomalie')) {
    return {
      paragraphs: [
        "Le score d'anomalie est visible sur la page Supervision (panneau « Score d'anomalie — modèle AIOps ») et dans Grafana, tableau Resilience-Alpha / Paiement [4].",
        "Il est calculé par un modèle Isolation Forest à partir de la latence, du taux de 5xx et du débit entrant [4].",
      ],
      citations: [4],
      meta: '2 extraits · 1,6 s',
    }
  }
  return {
    paragraphs: [
      "Je n'ai pas trouvé de passage suffisamment proche dans la documentation indexée. Précisez le service ou la procédure concernés.",
    ],
    citations: [],
    meta: '0 extrait · 1,1 s',
  }
}