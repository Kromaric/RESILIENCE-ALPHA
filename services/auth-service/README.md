# auth-service

Service FastAPI d'authentification d'Orbe — port interne **8001**. Voir CADRAGE §4.2.

| Endpoint | Rôle |
|---|---|
| `POST /login` | Email + mot de passe → JWT RS256 valable 15 min |
| `GET /me` | Profil du client connecté (téléphone masqué) |
| `GET /verify` | Validation d'une clé d'API partenaire (`X-API-Key`) |
| `GET /health/live` · `GET /health/ready` | Santé du processus · base joignable |
| `GET /metrics` | Métriques Prometheus |

Erreurs : `{"detail": {"code": "...", "message": "..."}}` — codes `invalid_credentials` (401),
`account_locked` (423, en-tête `Retry-After`), `too_many_attempts` (429), `invalid_token` (401),
`invalid_api_key` (401).

## Sécurité
- Mots de passe hachés en argon2id ; vérifications limitées à 4 en parallèle (mémoire bornée).
- 5 échecs → compte bloqué 10 min ; 20 tentatives par minute et par IP.
- Email inconnu et mauvais mot de passe : même réponse, même temps de calcul.
- Aucun mot de passe, jeton ni clé d'API dans les journaux.

## Configuration (préfixe `AUTH_`)
| Variable | Défaut |
|---|---|
| `AUTH_DB_HOST` / `AUTH_DB_PORT` / `AUTH_DB_NAME` / `AUTH_DB_USER` | `mariadb` / `3306` / `orbe` / `auth_svc` |
| `AUTH_DB_PASSWORD_FILE` | `/run/secrets/auth_db_password` |
| `AUTH_JWT_PRIVATE_KEY_FILE` | `/run/secrets/jwt_private_key` |
| `AUTH_JWT_TTL_SECONDS` | `900` |
| `AUTH_LOCKOUT_THRESHOLD` / `AUTH_LOCKOUT_MINUTES` | `5` / `10` |
| `AUTH_LOGIN_RATE_PER_IP` | `20` |
| `AUTH_ENABLE_DOCS` | `false` (Swagger sur `/docs` si `true`) |

## Développement
```bash
py -3.13 -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
.venv/Scripts/python -m pytest
.venv/Scripts/python -m ruff check .
```
Les tests utilisent SQLite en mémoire ; aucun MariaDB n'est nécessaire.

Clés JWT locales : `python scripts/gen_jwt_keys.py` à la racine du dépôt.
