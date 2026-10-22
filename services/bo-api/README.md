# bo-api

API du back-office d'Orbe : alimente le dashboard de supervision (`dashboard/`) — port interne
**8006**. **Lecture seule** : aucune route ne modifie la plateforme. Voir CADRAGE §4.7.

Le dashboard ne parle qu'à bo-api. bo-api relaie la connexion vers auth-service, lit la base
en lecture seule (compte `bo_ro`), Prometheus, Loki, Grafana et les services du plan de
contrôle (remédiation, détecteur, assistant). Il n'a pas accès au socket Docker.

## Connexion des opérateurs

Comptes **opérateurs**, distincts des clients. Sur le poste du PC Hôte, dans l'ordre imposé :
**identifiant → visage (caméra USB) → mot de passe**. auth-service pilote la LED de l'ESP8266 à
chaque étape ; détail et contrat de la LED : [docs/services/back-office-connexion.md](../../docs/services/back-office-connexion.md).

```
POST /bo/auth/identify  { "email" }                 → { session_id, step: "face", face_challenge }
POST /bo/auth/face      { session_id, frames }      → { step: "password" }         (LED verte clignotante)
POST /bo/auth/password  { session_id, password }    → { access_token, expires_in: 3600, role }
                        puis Authorization: Bearer <access_token> sur toutes les routes
GET  /bo/auth/me        → { operator_id, email, display_name, role }
POST /bo/auth/logout    → 204 (session révoquée)
POST /bo/auth/enroll-face  démarrage seulement (face_enrollment_required)
```

Pour le front : après un `401` au visage ou au mot de passe, éteindre la caméra et revenir à
l'identifiant (vidé). `429 identification_locked` : attendre `Retry-After` secondes avant de
réactiver la saisie.

| Rôle | Droits |
|---|---|
| `viewer` | indicateurs, supervision |
| `operator` | en plus : données personnelles, assistant |
| `admin` | en plus : habilitations (`/bo/admin/operators`) |

Habilitations (rôle `admin`) : `GET/POST /bo/admin/operators`, `PATCH /bo/admin/operators/{id}`
(nom, rôle, activation), `POST …/{id}/password`, `POST …/{id}/unlock`, `DELETE …/{id}/sessions`,
`POST …/{id}/face` (`{consent, frames}` : ~16 images, la personne devant la caméra),
`DELETE …/{id}/face`.

Erreurs : `{"detail": {"code": "...", "message": "..."}}` — `face_not_recognized`,
`liveness_failed`, `invalid_credentials` (401), `login_step_expired` (401), `identification_locked`
(429, `Retry-After`), `account_locked` (423), `invalid_token` (401 : retour à l'écran de connexion),
`forbidden` (403), `last_admin` (409), `<service>_unavailable` (503).

Chaque requête vérifie le jeton (signature, audience `orbe-bo`) puis la session auprès
d'auth-service, avec un cache de 5 s. Un jeton client (application Orbe) est refusé, et un jeton
opérateur n'est pas accepté par payment-service.

Comptes de démo (pile de dev) : `admin@orbe.test` (admin), `ops@orbe.test` (operator),
`viewer@orbe.test` (viewer), mot de passe `demo-password`, sans visage : `admin` enregistre d'abord le
sien (démarrage), puis ceux des autres depuis les habilitations.

## Brancher le dashboard (pour le front)

- En développement : `docker compose -f docker-compose.dev.yml --profile obs up -d` (le profil
  `obs` ajoute Prometheus, Loki, promtail, Grafana et node-exporter ; sans lui, la supervision
  répond « indisponible »), puis le dashboard avec `npm run dev` ; appeler
  `http://localhost:8006` (CORS ouvert pour `http://localhost:5173`). Grafana :
  http://localhost:3000 (admin : `secrets/grafana_admin_password`).
- Contrat complet et essais : http://localhost:8006/docs.
- En démonstration : le Nginx du dashboard relaie `/bo/` vers `oorbe-bo-api:8006` (même
  origine, pas de CORS).

## Données applicatives (`/bo/data`)

Lecture de la base avec le compte MariaDB **`bo_ro`** : lecture seule, colonnes utiles
uniquement. Les clients ne sont lisibles qu'à travers la vue `bo_clients`, où **email et
téléphone sont masqués par la base elle-même** (`c•••@orbe.test`, `+33 6 •• •• •• 78`) :
bo-api ne les voit jamais en clair. Jamais de hachage de mot de passe, de gabarit facial, de
jeton QR ni de clé d'idempotence. Les comptes de la sonde sont exclus (sauf du contrôle
comptable). Montants en **centimes**, dates en UTC (`2026-10-21T09:00:00Z`).

| Route | Rôle | Contenu |
|---|---|---|
| `GET /bo/data/summary` | viewer | Clients (total, nouveaux 7 j, avec visage, bloqués), opérations 24 h et 7 j (par type, par statut, montants, taux et motifs de refus), demandes, soldes |
| `GET /bo/data/series?metric=transactions\|amount\|declines\|registrations&interval=hour\|day` | viewer | 24 points horaires ou 30 points journaliers `{time, value}` |
| `GET /bo/data/ledger/check` | viewer | Contrôle de la partie double : `ok`, opérations déséquilibrées, soldes faux, découverts, écritures anormales |
| `GET /bo/data/transactions?type&status&client_id&reference&date_from&date_to&page&size` | operator | Opérations, plus récentes d'abord |
| `GET /bo/data/transactions/{reference}` | operator | Détail : écritures, remboursement ou paiement d'origine, demande réglée, compte lié d'un retrait |
| `GET /bo/data/clients?q&locked&face_enrolled&page&size` | operator | Clients masqués, solde, nombre d'opérations ; `q` cherche dans le nom affiché |
| `GET /bo/data/clients/{client_id}` | operator | Fiche : comptes liés (4 derniers caractères de l'IBAN), sessions actives, demandes en attente, 20 dernières opérations |
| `GET /bo/data/requests?status&client_id&page&size` | operator | Demandes d'argent |

Listes paginées : `{ items, page, size, total }`, `page` à partir de 1, `size` 25 par défaut
et 100 au plus. Chaque appel d'une route `operator` est **journalisé** (`personal_data_viewed` :
opérateur, ressource, client), à destination du SOC. Base indisponible :
`503 database_unavailable`.

## Supervision (`/bo/supervision`, rôle viewer)

Mêmes formes que les données simulées du dashboard (`dashboard/src/data/supervision.js`,
`metrics.js`, `incident.js`) : les composants existants s'alimentent presque tels quels.
Sources : Prometheus, Loki et le moteur de remédiation (`GET /status`). Si une source manque,
la valeur vaut `"—"` avec le ton `unknown` : la page reste affichable.

| Route | Contenu | Données simulées remplacées |
|---|---|---|
| `GET /bo/supervision/overview` | `status` (badge), `banner`, `kpis` (6 indicateurs : `key`, `label`, `value` mis en forme, `raw`, `sub`, `tone`), `sources` | `phases[x].status`, `.banner`, `.kpis` |
| `GET /bo/supervision/services` | Cartes `{name, desc, status, metric}` ; `status` : `ok`, `warn`, `down`, `restored` ou **`unknown`** (nouveau) | `phases[x].services` |
| `GET /bo/supervision/series?minutes=30` | `points[]` `{time: "10:42", ts, incident, latency, anomaly, tx}` + `incident {x1, x2}` | `getSeries()` |
| `GET /bo/supervision/resources` | `[{label, value, percent}]` : CPU, mémoire, disque, réseau | `resources[x]` |
| `GET /bo/supervision/logs?level=all\|warn\|error&source&minutes&limit` | `logs[]` `{time, ts, level, source, msg}`, plus récents d'abord ; identifiants, IP et emails retirés | `getLogs()` |

Le bouton avant / pendant / après n'a plus d'objet avec des données réelles : il peut rester
comme mode démo, branché sur les données simulées.

## Incidents, assistant, Grafana

| Route | Rôle | Contenu |
|---|---|---|
| `GET /bo/incidents?limit` · `GET /bo/incidents/{id}` | viewer | Relayés tels quels depuis le moteur de remédiation (format défini par le moteur, CADRAGE §4.6) ; `503 remediation_unavailable` tant qu'il n'est pas déployé |
| `POST /bo/assistant/ask` `{question}` | operator | `{answer, sources: [{doc, extrait}]}` depuis assistant-rag ; 10 questions par minute ; jusqu'à 60 s de réponse |
| `GET /bo/grafana` | viewer | `panels[]` `{key, title, embed_url}` à mettre dans une `<iframe>` (latence, erreurs, transactions, pool MariaDB, connexions, score d'anomalie, journaux d'erreur), `dashboards[]`, `tools[]` (liens de la barre latérale) |

Grafana : tableau versionné `infra/grafana-provisioning/dashboards/orbe-supervision.json`
(uid `orbe-supervision`), intégration autorisée et lecture anonyme (rôle Viewer, port
publié sur 127.0.0.1 seulement).

Rafraîchissement conseillé : toutes les 2 à 5 s pour `overview`, `services` et `logs`,
toutes les 30 s pour `series`, `resources` et `/bo/data/*`.

## Configuration (préfixe `BO_`)
| Variable | Défaut |
|---|---|
| `BO_AUTH_URL` | `http://auth-service:8001` |
| `BO_JWT_PUBLIC_KEY_FILE` | `/run/secrets/jwt_public_key` |
| `BO_SESSION_CACHE_SECONDS` | `5` |
| `BO_DB_HOST` / `BO_DB_USER` / `BO_DB_PASSWORD_FILE` | `mariadb` / `bo_ro` / `/run/secrets/bo_db_password` |
| `BO_DB_POOL_SIZE` / `BO_PAGE_SIZE_MAX` | `3` / `100` |
| `BO_PROMETHEUS_URL` / `BO_LOKI_URL` | `http://prometheus:9090` / `http://loki:3100` |
| `BO_REMEDIATION_URL` / `BO_DETECTOR_URL` / `BO_ASSISTANT_URL` | ports 8003 / 8004 / 8005 |
| `BO_GRAFANA_PUBLIC_URL` / `BO_PROMETHEUS_PUBLIC_URL` | `http://localhost:3000` / `http://localhost:9090` (adresses vues par le navigateur) |
| `BO_LOKI_SELECTOR` | `{container=~"oorbe-.+"}` (dev : `{container=~"orbe-dev-.+"}`) |
| `BO_DISK_MOUNTPOINT` | `/` (Docker Desktop : `/var/lib`) |
| `BO_LATENCY_THRESHOLD_MS` / `BO_ERROR_RATE_THRESHOLD` / `BO_ANOMALY_THRESHOLD` | `800` / `0.02` / `0.80` |
| `BO_DISPLAY_TIMEZONE` | `Europe/Paris` (heures des courbes et des journaux) |
| `BO_CORS_ORIGINS` | `[]` |
| `BO_VAULT_KV_PATH` | vide : secrets lus dans `/run/secrets/` ; démonstration : `secret/data/oorbe/config` |
| `BO_VAULT_ADDR` / `BO_VAULT_TOKEN_FILE` | `http://vault:8200` / `/run/secrets/vault_token` (jeton en lecture seule) |
| `BO_VAULT_ROLE_ID_FILE` / `BO_VAULT_SECRET_ID_FILE` | AppRole, prioritaire sur le jeton s'ils existent |
| `BO_DB_PASSWORD_KEY` | `bo_db_password` : nom de la clé dans Vault (repli : fichier de secret) |
| `BO_ENABLE_DOCS` | `false` (Swagger sur `/docs` si `true`) |

## Développement
```bash
py -3.13 -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
.venv/Scripts/python -m pytest
.venv/Scripts/python -m ruff check .
```
Les tests simulent auth-service, Prometheus, Loki, le moteur de remédiation et l'assistant
(`httpx.MockTransport`) et utilisent SQLite en mémoire ; le
masquage par la vue `bo_clients` se vérifie sur la pile de dev (MariaDB).
