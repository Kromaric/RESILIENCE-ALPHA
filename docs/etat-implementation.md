# État d'implémentation d'Orbe (mercredi 21 octobre 2026)

> Photographie du dépôt à la date indiquée, à mettre à jour à chaque jalon. Le cadrage décrit la **cible** ;
> ce fichier dit ce qui tourne réellement. Les autres documents décrivent la cible et signalent *(cible)*
> ce qui n'est pas encore livré.

## Composants livrés et testés

| Composant | État | Preuve |
|---|---|---|
| auth-service | Livré : inscription, connexion mot de passe + visage (InsightFace `buffalo_s`), sessions révocables, `/verify` par clé d'API, métriques | `services/auth-service/tests/` |
| payment-service | Livré : paiements, remboursements, retraits, demandes d'argent, QR, contacts, comptes liés, partie double, réconciliation, `/health/ready` | `services/payment-service/tests/` |
| MariaDB | Livré : schéma v2, comptes à moindre privilège, données de démo | `infra/mariadb/init/`, `seed/` |
| Documentation d'API | Livrée : OpenAPI exportés | `docs/api/` |
| Modèle de données | Livré | `docs/mcd.md` |
| assistant-rag + Ollama | Livré : conteneurs `ollama-init`, `ollama`, `assistant-rag` ; indexation de `docs/`, `/ask` avec citations, refus hors corpus, métriques | `services/assistant-rag/tests/`, `infra/docker-compose.rag.yml` |

## Composants à l'état de squelette (README seul)

| Composant | Ce qui manque |
|---|---|
| probe | Code de la sonde, métriques `probe_*`, `POST /run` |
| detector-ml | Service, et dans `ml/` : `collect.py`, `train.py`, `evaluate.py`, locustfile |
| remediation-engine | Service, machine à états, `policies.yml`, playbooks `infra/ansible/remediation/` |
| dashboard, frontend | Applications React (Dockerfiles présents, services commentés dans le compose) |
| redteam/sc01 | Script d'attaque |
| Ansible | `deploy.yml`, `verify.yml`, `reset.yml`, `backup.yml` / `restore.yml` |
| CI | `.github/workflows/ci.yml` (seul un README est présent) |

## Écarts entre `infra/docker-compose.yml` et le cadrage

| Sujet | Cadrage | Dépôt actuel | À trancher / corriger |
|---|---|---|---|
| WAF | Nginx + ModSecurity v3 + OWASP CRS 4 | **SafeLine** (`chaitin/safeline-tengine`) | Choix à acter et à reporter dans le cadrage ; la liste de blocage dynamique et les règles SOC dépendent du WAF retenu |
| Collecte des journaux | Grafana Alloy, label `service` | **Promtail**, label `container` (ex. `oorbe-payment-service`) | Les requêtes LogQL du cadrage utilisent `{service="…"}` : adapter en `{container="…"}` ou ajouter le label |
| Noms des conteneurs | `auth-service`, `payment-service-a/-b` | `oorbe-auth-service`, `oorbe-payment-service` (une seule instance) | Deuxième instance de paiement à ajouter (elle conditionne la continuité pendant le redémarrage) |
| Intervalle de scrape | 5 s | 15 s | Passer à 5 s, sinon le budget de détection de 15 s n'est pas tenable |
| Images | Tags épinglés | `:latest` partout sauf Vault | Épingler avant le gel du code |
| Exposition | Seul le 443 sur `192.168.137.1` | `3306`, `8200`, `9090`, `3100`, `3000`, `80`, `443` publiés sur toutes les interfaces | Retirer ou lier à `127.0.0.1` : la base et Vault ne doivent pas être joignables depuis le hotspot |
| Grafana | Viewer anonyme en lecture seule | `GF_SECURITY_ADMIN_PASSWORD=admin` | Mot de passe via secret |
| Vault | Serveur, TLS, AppRoles, amorçage SOPS | Serveur sans TLS, pas encore d'amorçage | Les services lisent encore leurs secrets en fichiers Docker |
| Promtail | — | Monte `/var/run/docker.sock` | Point à justifier ou à remplacer (accès en lecture à l'API Docker) |
| Métriques de nœud | cAdvisor | node-exporter | cAdvisor à ajouter pour les métriques par conteneur |
| Alertmanager, mysqld-exporter | Prévus | Absents | À ajouter |
| auth-service | `mem_limit` 256M | 1 Go (modèle de visage chargé) | Cohérent ; mettre à jour le budget mémoire |

## Points ouverts (CADRAGE §14)

- RAM du PC Hôte (16 ou 32 Go) et disponibilité d'un PC IA
- Modèle LLM définitif de l'assistant
- Seuil du score d'anomalie (après `ml/evaluate.py`)
- Liste minimale des droits du `socket-proxy`
- SC-02 : go / no-go
- Seuil de reconnaissance faciale mesuré sur l'équipe
- `orbe.test` et CA `mkcert` sur les appareils de démo
