// Données de la page Assistant que bo-api ne fournit pas : historique des conversations
// (simulé), configuration et suggestions (les réponses viennent de POST /bo/assistant/ask)
export const conversations = [
  { id: 1, title: '502 sur payment-api', date: "aujourd'hui · 10:43", active: true },
  { id: 2, title: 'Rotation des secrets Vault', date: 'hier' },
  { id: 3, title: 'Seuils du modèle AIOps', date: '16/10' },
]

// Valeurs de la pile de démo (infra/docker-compose.rag.yml) ; aucune route ne les expose
export const config = [
  ['Modèle', 'qwen2.5:7b · Ollama'],
  ['Hébergement', 'VM Ollama dédiée (délestage IA)'],
  ['Embeddings', 'nomic-embed-text'],
  ['Base vectorielle', 'ChromaDB'],
  ['Corpus', 'docs/ (Markdown, hors api/)'],
  ['Extraits', '4 par réponse, pertinence ≥ 0,66'],
]

// Questions du jeu d'évaluation de l'assistant (services/assistant-rag/eval/questions.yaml)
export const suggestions = [
  "L'alerte PaymentAnomaly vient de se déclencher, ça veut dire quoi ?",
  "Qu'a fait l'automate pendant l'attaque SC-01 ?",
  'Comment je vérifie que le paiement remarche après l\'incident ?',
]
