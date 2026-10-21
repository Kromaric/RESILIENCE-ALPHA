// Données encore simulées : bo-api ne fournit ni l'historique des conversations ni la
// configuration de l'assistant (les réponses viennent de POST /bo/assistant/ask)
export const conversations = [
  { id: 1, title: '502 sur payment-api', date: "aujourd'hui · 10:43", active: true },
  { id: 2, title: 'Rotation des secrets Vault', date: 'hier' },
  { id: 3, title: 'Seuils du modèle AIOps', date: '16/10' },
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
