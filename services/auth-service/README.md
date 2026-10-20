# auth-service

Service FastAPI d'authentification d'Orbe — port interne **8001**. Voir CADRAGE §4.2 et `docs/mcd.md`.

## Connexion en deux étapes

```
POST /login           email + mot de passe (+ X-Client-Id, X-API-Key pour un service)
  ├─ compte sans passkey  → session « mot de passe seul » (consultation, enregistrement d'une passkey)
  ├─ service (sonde)      → session active, comptes de la sonde uniquement
  └─ compte avec passkey  → { mfa_required, session_id, webauthn_options }
POST /login/passkey   réponse de navigator.credentials.get() → JWT (amr = pwd, passkey)
```

La biométrie (Face ID, Windows Hello) est vérifiée **par l'appareil** ; le serveur ne stocke que la
clé publique de la passkey. Bibliothèque : `webauthn` (Duo Labs).

| Endpoint | Rôle |
|---|---|
| `POST /register` | Création de compte (email, téléphone, nom, mot de passe) |
| `POST /login` · `POST /login/passkey` | Connexion (mot de passe, puis passkey) |
| `POST /logout` | Révocation de la session |
| `POST /passkeys/register/options` · `POST /passkeys/register` | Enregistrer la passkey d'un appareil |
| `GET /passkeys` · `DELETE /passkeys/{id}` | Gérer ses appareils |
| `GET /me` | Profil, facteurs de la session, nombre de passkeys |
| `GET /verify` | Validation d'une clé d'API partenaire (`X-API-Key`) |
| `GET /health/live` · `GET /health/ready` | Santé du processus · base joignable |
| `GET /metrics` | Métriques Prometheus |

JWT RS256 de 15 min : `sub`, `email`, `jti` (= identifiant de session), `amr` (facteurs), `cid` / `cty`
(application cliente et son type). Chaque requête authentifiée vérifie que la session est **active en base**.

Erreurs : `{"detail": {"code": "...", "message": "..."}}` — `invalid_credentials`, `account_locked`
(423, `Retry-After`), `too_many_attempts`, `invalid_client`, `client_not_allowed`, `second_factor_failed`,
`passkey_confirmation_required`, `invalid_passkey`, `invalid_token`, `invalid_api_key`.

## Sécurité
- Mots de passe argon2id ; hachages et vérifications limités à 4 en parallèle (mémoire bornée).
- Inscription : 12 caractères minimum, mots de passe courants refusés, 5 inscriptions par minute
  et par IP ; insertion limitée aux colonnes autorisées (jamais de compte de sonde).
- 5 échecs → compte bloqué 10 min ; 20 tentatives par minute et par IP.
- Passkey : vérification utilisateur exigée, origine et identifiant de site contrôlés, défi à usage
  unique, compteur de signatures (une passkey clonée est refusée).
- Un compte qui a une passkey ne gère ses appareils que depuis une session confirmée par passkey.
- Aucun mot de passe, jeton, clé d'API ni défi WebAuthn dans les journaux.

## Configuration (préfixe `AUTH_`)
| Variable | Défaut |
|---|---|
| `AUTH_DB_HOST` / `AUTH_DB_PORT` / `AUTH_DB_NAME` / `AUTH_DB_USER` | `mariadb` / `3306` / `orbe` / `auth_svc` |
| `AUTH_DB_PASSWORD_FILE` | `/run/secrets/auth_db_password` |
| `AUTH_JWT_PRIVATE_KEY_FILE` | `/run/secrets/jwt_private_key` |
| `AUTH_JWT_TTL_SECONDS` | `900` |
| `AUTH_WEBAUTHN_RP_ID` / `AUTH_WEBAUTHN_ORIGINS` | `orbe.test` / `["https://orbe.test"]` |
| `AUTH_PENDING_2FA_SECONDS` | `300` |
| `AUTH_LOCKOUT_THRESHOLD` / `AUTH_LOCKOUT_MINUTES` | `5` / `10` |
| `AUTH_LOGIN_RATE_PER_IP` / `AUTH_REGISTER_RATE_PER_IP` | `20` / `5` |
| `AUTH_ENABLE_DOCS` | `false` (Swagger sur `/docs` si `true`) |

## Développement
```bash
py -3.13 -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
.venv/Scripts/python -m pytest
.venv/Scripts/python -m ruff check .
```
Les tests utilisent SQLite en mémoire et un authentificateur WebAuthn simulé
(`tests/soft_authenticator.py`) ; ni MariaDB ni téléphone ne sont nécessaires.

Clés JWT locales : `python scripts/gen_jwt_keys.py` à la racine du dépôt.
