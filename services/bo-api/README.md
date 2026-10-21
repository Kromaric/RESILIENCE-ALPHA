# bo-api

API du back-office d'Orbe : alimente le dashboard de supervision (`dashboard/`) — port interne
**8006**. **Lecture seule** : aucune route ne modifie la plateforme. Voir CADRAGE §4.7.

Le dashboard ne parle qu'à bo-api. bo-api relaie la connexion vers auth-service, lit la base
en lecture seule (compte `bo_ro`), Prometheus, Loki, Grafana et les services du plan de
contrôle (remédiation, détecteur, assistant). Il n'a pas accès au socket Docker.

## Connexion des opérateurs

Comptes **opérateurs**, distincts des clients Orbe, mot de passe seul (pas de visage) :

```
POST /bo/auth/login   { "email", "password" }  → { access_token, expires_in: 3600, role }
                      puis Authorization: Bearer <access_token> sur toutes les routes
GET  /bo/auth/me      → { operator_id, email, display_name, role }
POST /bo/auth/logout  → 204 (session révoquée)
```

| Rôle | Droits |
|---|---|
| `viewer` | consultation |
| `operator` | consultation + assistant |

Erreurs : `{"detail": {"code": "...", "message": "..."}}` — `invalid_credentials` (401),
`account_locked` (423, `Retry-After`), `too_many_attempts` (429), `invalid_token` (401 : jeton
absent, expiré ou session révoquée → retour à l'écran de connexion), `forbidden` (403),
`<service>_unavailable` (503 : service interrogé injoignable).

Chaque requête vérifie le jeton (signature, audience `orbe-bo`) puis la session auprès
d'auth-service, avec un cache de 5 s : une déconnexion ou un compte désactivé est pris en
compte en 5 s au plus. Un jeton client (application Orbe) est refusé, et un jeton opérateur
n'est pas accepté par payment-service.

Comptes de démo (pile de dev) : `ops@orbe.test` (operator) et `viewer@orbe.test` (viewer), mot
de passe `demo-password`. Créer un compte :

```bash
services/auth-service/.venv/Scripts/python scripts/create_operator.py prenom@orbe.test --name "Prénom Nom" --role operator
```

## Brancher le dashboard (pour le front)

- En développement : `docker compose -f docker-compose.dev.yml up -d`, puis le dashboard avec
  `npm run dev` ; appeler `http://localhost:8006` (CORS ouvert pour `http://localhost:5173`).
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

Routes de supervision (état, indicateurs, séries, ressources, journaux, incidents, Grafana,
assistant) : à venir, au format des fichiers `dashboard/src/data/*.js`.

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
| `BO_GRAFANA_PUBLIC_URL` | `http://localhost:3000` (adresse vue par le navigateur) |
| `BO_CORS_ORIGINS` | `[]` |
| `BO_ENABLE_DOCS` | `false` (Swagger sur `/docs` si `true`) |

## Développement
```bash
py -3.13 -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
.venv/Scripts/python -m pytest
.venv/Scripts/python -m ruff check .
```
Les tests simulent auth-service (`httpx.MockTransport`) et utilisent SQLite en mémoire ; le
masquage par la vue `bo_clients` se vérifie sur la pile de dev (MariaDB).
