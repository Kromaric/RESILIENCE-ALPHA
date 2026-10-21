# assistant-rag — assistant opérateur

Port interne **8005**, publié sur `127.0.0.1:8005` uniquement. Ollama + LangChain + ChromaDB.
Code : `services/assistant-rag/` ; conteneurs : `infra/docker-compose.rag.yml`.

## assistant-rag — conteneurs et machines

| Machine | Conteneur | Rôle |
|---|---|---|
| VM Ollama (Proxmox, 32 Go) | `ollama-init` | Télécharge les modèles une fois, puis s'arrête ; seul conteneur qui accède à Internet |
| VM Ollama | `ollama` | Sert le modèle de langage et les embeddings, sur un réseau interne sans port publié |
| VM Ollama | `proxy` | Seul port ouvert (11434) : exige un jeton et n'ouvre que les routes d'inférence |
| PC Hôte | `assistant-rag` | API `POST /ask` ; lit `docs/` en lecture seule ; index ChromaDB dans un volume |

Si l'assistant répond `503 index_not_ready`, l'indexation est en cours ou la VM Ollama n'est pas
joignable : `GET /health/ready` donne l'erreur. Vérifier alors la VM (`http://<ip-vm>:11434/health`),
le jeton et le pare-feu Proxmox.

## assistant-rag — rôle et limites

L'assistant aide un opérateur confronté à un incident à **comprendre** ce qui se passe et à **retrouver**
une procédure, à partir des documents de ce dossier `docs/`. Il ne remplace pas le moteur de remédiation :

- il ne reçoit pas les alertes et ne déclenche aucune action ;
- il n'a **aucun** accès au moteur de remédiation en écriture, au socket Docker, à Vault ni à la base ;
- s'il ne trouve rien de pertinent dans le corpus, il répond qu'il ne sait pas ;
- il cite toujours les documents utilisés.

## assistant-rag — utilisation

`POST /ask` avec l'en-tête `X-API-Key` et `{ "question": "..." }` → `{ "answer", "sources": [ { "doc", "section", "extrait", "score" } ] }`.

Exemples de questions utiles :
- « L'alerte PaymentAnomaly vient de se déclencher, qu'est-ce que ça veut dire ? »
- « Qu'a fait l'automate pendant SC-01 et comment vérifier que le paiement remarche ? »
- « Quel est le RTO du service de paiement ? »
- « Que signifie `pool: saturated` dans `/health/ready` ? »

## assistant-rag — fonctionnement technique

- Ingestion des fichiers Markdown de `docs/` : découpage par titres, puis en morceaux de 800 caractères avec un chevauchement de 100.
- Embeddings `nomic-embed-text` via Ollama, index ChromaDB persistant.
- Récupération des 4 extraits les plus proches (similarité cosinus) ; si même le meilleur extrait a un score inférieur à 0,66, l'assistant répond qu'il ne sait pas sans interroger le modèle. Les identifiants exacts de la question (SC-01, PaymentAnomaly, noms de métriques) sont favorisés dans le classement.
- Les demandes d'action (« Redémarre… ») et de secret (« Donne-moi le mot de passe… ») reçoivent un refus fixe, sans passer par le modèle.
- Réponse en français avec citations obligatoires ; l'index n'est reconstruit que si `docs/` a changé.
- Modèle de langage ≤ 8 milliards de paramètres (contrainte du sujet) : Qwen2.5 7B quantifié Q4 sur la VM Proxmox de 32 Go dédiée à l'assistant ; Qwen2.5 3B sur un PC Hôte de 16 Go. Profils : `infra/rag.env.example`.
- Une réponse prend de quelques secondes (refus, hors sujet : immédiats) à environ une minute sur CPU pour un modèle 7B.

## assistant-rag — VM Ollama et exposition du modèle

Conformément au sujet, la machine de délestage IA n'héberge que le modèle et son interface d'accès.
Sur la VM, Ollama n'est pas publié : seul un proxy l'est, sur le port 11434. Il exige l'en-tête
`Authorization: Bearer <jeton>` et n'ouvre que les routes d'inférence (`/api/chat`, `/api/embed`…) ;
le téléchargement, la création et la suppression de modèles sont fermés. Le pare-feu Proxmox
n'autorise le port 11434 que depuis l'IP du PC Hôte. Déploiement : `infra/ollama/README.md`.
