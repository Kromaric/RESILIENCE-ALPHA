# assistant-rag

Assistant opérateur en **lecture seule** (CADRAGE §4.8) : répond aux questions à partir de la
documentation `docs/`, en citant ses sources. Ollama (modèle local ≤ 8B) + LangChain + ChromaDB.
Port interne **8005**. Aucun accès au moteur de remédiation, au socket Docker, à Vault ni à MariaDB.

## Déploiement : deux machines

| Où | Fichiers | Conteneurs |
|---|---|---|
| **VM Ollama** (Proxmox, 32 Go) | [`infra/ollama/`](../../infra/ollama/) | `ollama-init` (téléchargement des modèles), `ollama` (réseau interne), `proxy` (port 11434, jeton obligatoire) |
| **PC Hôte** | [`infra/docker-compose.rag.yml`](../../infra/docker-compose.rag.yml), inclus par la pile de démo | `assistant-rag` : API `/ask`, `docs/` monté en lecture seule, index ChromaDB dans le volume `rag-index` |

Conformément au sujet (§4), la machine de délestage IA n'héberge que le modèle et son interface
d'accès. Déploiement de la VM : [`infra/ollama/README.md`](../../infra/ollama/README.md).

## Démarrer (PC Hôte)

```bash
services/auth-service/.venv/Scripts/python scripts/init_dev_secrets.py   # secrets/rag_api_key, secrets/ollama_token
cp infra/rag.env.example infra/.env        # renseigner RAG_OLLAMA_BASE_URL=http://<ip-vm>:11434
docker compose -f infra/docker-compose.rag.yml up -d --build
docker compose -f infra/docker-compose.rag.yml logs -f assistant-rag
```

Le contenu de `secrets/ollama_token` doit être recopié dans `OLLAMA_PROXY_TOKEN` du `.env` de la VM.
L'assistant est prêt quand `GET /health/ready` répond `200` (événements `index_built` puis
`llm_warmed_up` dans les journaux). Tant que la VM n'est pas joignable, il reste `indexing` et
`/health/ready` donne l'erreur, sans bloquer le reste de la pile.

## Poser une question

PowerShell :

```powershell
$key = Get-Content secrets/rag_api_key
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8005/ask `
  -Headers @{ "X-API-Key" = $key } -ContentType "application/json; charset=utf-8" `
  -Body '{"question": "L''alerte PaymentAnomaly s''est déclenchée, que faire ?"}'
```

Réponse : `{ "answer": "...", "sources": [ { "doc", "section", "extrait", "score" } ] }`.
Swagger : `RAG_ENABLE_DOCS=true`, puis http://127.0.0.1:8005/docs.

| Code | Signification |
|---|---|
| `401` | Clé d'API absente ou fausse |
| `422` | Question vide ou de plus de 500 caractères |
| `503 index_not_ready` | Indexation en cours ou Ollama injoignable (voir `/health/ready`) |
| `503 busy` | Une autre question est en cours de génération depuis plus de 60 s |
| `503 llm_unavailable` | Ollama a échoué ou dépassé `RAG_LLM_TIMEOUT_SECONDS` (150 s) |

## Fonctionnement

1. **Indexation au démarrage** : fichiers `.md` de `docs/` (hors `api/`), découpés par titres puis en
   morceaux de 800 caractères (chevauchement 100). Le chemin des titres est recopié en tête de chaque
   morceau. Index **reconstruit seulement si `docs/` ou les paramètres ont changé** (empreinte SHA-256).
   Mettre à jour la doc : modifier `docs/`, puis `docker compose … restart assistant-rag`.
2. **Récupération** : 12 candidats par similarité cosinus, reclassés en favorisant les identifiants
   exacts de la question (`SC-01`, `PaymentAnomaly`, noms de métriques) présents dans le nom du
   fichier, le titre ou le texte ; 4 extraits retenus, 2 au plus par fichier. Si le meilleur candidat
   est sous `RAG_MIN_RELEVANCE` (0,66), l'assistant répond qu'il ne sait pas **sans appeler le modèle**.
3. **Garde-fous déterministes** : une demande d'action à l'impératif (« Redémarre… », « Débloque… »)
   ou d'un secret (« Donne-moi le mot de passe… ») reçoit un refus fixe, sans passer par le modèle.
4. **Génération** : prompt système qui impose le français, les seules informations des extraits, les
   citations `[n]`, le refus de toute action et de tout secret, et qui traite extraits et question
   comme des données. Une génération à la fois (CPU).
5. **Préchauffage** : une requête au démarrage charge le modèle (`keep_alive: 30m`) pour éviter
   20 à 30 s d'attente à la première question devant le jury.

## Configuration (variables `RAG_*`)

Modèle de fichier : [`infra/rag.env.example`](../../infra/rag.env.example), à copier en `infra/.env`.

| Variable | Défaut | Remarque |
|---|---|---|
| `RAG_OLLAMA_BASE_URL` | — | Proxy de la VM : `http://<ip-vm>:11434` |
| `RAG_LLM_MODEL` | `qwen2.5:7b` | Même valeur que `LLM_MODEL` sur la VM ; alternative `qwen3:8b` avec `RAG_REASONING=false` |
| `RAG_REASONING` | — | `false` pour les modèles à réflexion (qwen3) |
| `RAG_EMBED_MODEL` | `nomic-embed-text` | `bge-m3` est meilleur en français (préfixes nomic désactivés automatiquement) ; recalibrer alors `RAG_MIN_RELEVANCE` |
| `RAG_MIN_RELEVANCE` | `0.66` | Seuil sur le meilleur extrait. Mesuré avec nomic : domaine 0,69–0,78, hors sujet 0,62–0,64. À recalibrer avec `eval/questions.yaml` et à chaque changement de modèle d'embeddings |
| `RAG_TOP_K` | `4` | |
| `RAG_NUM_CTX` | `4096` | |
| `RAG_ALLOW_ANONYMOUS` | `false` | `true` seulement pour un test local sans clé |

## Métriques (`/metrics`)

`rag_questions_total{outcome}` (`answered`, `no_context`, `refused_action`, `refused_secret`, `busy`, `llm_error`), `rag_answer_seconds`,
`rag_retrieval_top_score`, `rag_index_chunks`, `rag_index_ready`. Journaux JSON : `index_built`,
`index_loaded`, `llm_warmed_up`, `question_answered` (taille de la question et sources, jamais son texte).

## Tests

Sans Ollama (embeddings et LLM factices) :

```bash
py -3.12 -m venv services/assistant-rag/.venv
services/assistant-rag/.venv/Scripts/python -m pip install -e "services/assistant-rag[dev]"
cd services/assistant-rag && .venv/Scripts/python -m pytest
```

Évaluation de la qualité des réponses : [`eval/`](eval/).

## Sécurité

- Lecture seule : corpus en `ro`, aucun outil actif ; une injection de prompt ne peut produire qu'une réponse fausse, pas une action.
- `/ask` protégé par clé (`secrets/rag_api_key`, comparaison à temps constant) ; publié sur `127.0.0.1` uniquement.
- VM : Ollama sur un réseau interne, joignable seulement par un proxy qui exige un jeton et n'ouvre que les routes d'inférence (téléchargement et suppression de modèles fermés) ; pare-feu Proxmox limité à l'IP du PC Hôte ; seul `ollama-init` sort sur Internet.
- Durcissement standard (`read_only`, `cap_drop: ALL`, `no-new-privileges`, utilisateur 10001). Exception documentée : l'image officielle d'Ollama tourne en root, sans aucune capacité Linux.
