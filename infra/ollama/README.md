# VM Ollama — délestage IA

Machine dédiée au modèle de langage de l'assistant opérateur (VM Proxmox, 32 Go). Conformément au
sujet (§4), elle **n'héberge que le modèle et son interface d'accès** ; `assistant-rag` (LangChain,
ChromaDB, API `/ask`) reste sur le PC Hôte et l'appelle à travers le réseau.

```
PC Hôte                                    VM Ollama (Proxmox)
┌───────────────────┐   HTTP + jeton    ┌────────────────────────────────────┐
│ assistant-rag     │ ────────────────► │ proxy :11434 ──► ollama (interne)  │
│ (LangChain, Chroma)│                   │ ollama-init (téléchargement, 1 fois)│
└───────────────────┘                   └────────────────────────────────────┘
```

## Conteneurs

| Conteneur | Réseau | Rôle |
|---|---|---|
| `ollama-init` | `egress` (Internet) | Télécharge `LLM_MODEL` et `EMBED_MODEL`, puis s'arrête ; ne retélécharge pas un modèle présent |
| `ollama` | `internal` (sans Internet, sans port) | Sert le LLM et les embeddings |
| `proxy` | `internal` + `public`, port 11434 | Exige `Authorization: Bearer <jeton>`, n'ouvre que les routes d'inférence |

Routes ouvertes par le proxy : `/api/chat`, `/api/generate`, `/api/embed`, `/api/embeddings`,
`/api/show`, `/api/tags`, `/api/version`, `/api/ps`. Fermées : téléchargement, création, copie,
suppression de modèles. `/health` répond sans jeton.

## Préparer la VM (Proxmox)

1. **Type de CPU : `host`** (Matériel → Processeurs). Avec le type par défaut, la VM ne voit pas
   AVX2 et l'inférence est plusieurs fois plus lente.
2. **vCPU = cœurs physiques** réservés à la VM (8 par exemple), 32 Go de RAM, ~30 Go de disque.
3. Debian ou Ubuntu Server + Docker Engine et le plugin Compose.
4. **Pare-feu Proxmox** de la VM (Pare-feu → Règles, puis activer le pare-feu sur la VM et son
   interface) : `ACCEPT tcp 11434` depuis l'IP du PC Hôte uniquement, SSH depuis l'IP
   d'administration, politique d'entrée `DROP`.
   Ne pas compter sur `ufw` dans la VM : les ports publiés par Docker le contournent.

## Déployer

Sur le PC Hôte, générer le jeton (une fois) :

```bash
services/auth-service/.venv/Scripts/python scripts/init_dev_secrets.py   # crée secrets/ollama_token
```

Sur la VM, copier ce dossier `infra/ollama/` (ou cloner le dépôt), puis :

```bash
cp .env.example .env
nano .env            # OLLAMA_PROXY_TOKEN = contenu de secrets/ollama_token du PC Hôte
docker compose up -d
docker compose logs -f ollama-init    # premier démarrage : ~5,5 Go (qwen2.5:7b + nomic-embed-text)
```

**Télécharger les modèles avant le jour J**, pas sur le hotspot du campus.

## Vérifier

Depuis le PC Hôte (PowerShell) :

```powershell
$t = Get-Content secrets/ollama_token
Invoke-RestMethod http://<ip-vm>:11434/health                                     # ok
Invoke-RestMethod http://<ip-vm>:11434/api/tags -Headers @{Authorization="Bearer $t"}   # modèles
Invoke-RestMethod http://<ip-vm>:11434/api/tags                                   # 401 attendu
Invoke-RestMethod -Method Post http://<ip-vm>:11434/api/pull -Headers @{Authorization="Bearer $t"}  # 404 attendu
```

Puis côté PC Hôte, renseigner `RAG_OLLAMA_BASE_URL=http://<ip-vm>:11434` dans `infra/.env` et
démarrer l'assistant : voir `services/assistant-rag/README.md`.

## Changer de modèle

Modifier `LLM_MODEL` dans `.env` puis `docker compose up -d` : `ollama-init` télécharge le nouveau
modèle. Côté PC Hôte, mettre la même valeur dans `RAG_LLM_MODEL` (et `RAG_REASONING=false` pour
qwen3). Un changement d'`EMBED_MODEL` doit aussi être reporté dans `RAG_EMBED_MODEL` : l'index est
alors reconstruit et `RAG_MIN_RELEVANCE` est à recalibrer.

## Réseau le jour de la démonstration

La VM doit être joignable depuis le PC Hôte sur le réseau de démonstration. Si le serveur Proxmox
n'est pas sur le hotspot de l'équipe, le moyen d'accès (VPN, etc.) est à décrire dans le dossier :
le sujet limite toute l'activité aux machines autorisées de l'équipe.
