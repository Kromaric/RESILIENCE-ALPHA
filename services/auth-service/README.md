# auth-service

Service FastAPI d'authentification d'Orbe — port interne **8001**. Voir CADRAGE §4.2 et `docs/mcd.md`.

## Connexion en deux étapes : mot de passe + visage

```
POST /login           email + mot de passe (+ X-Client-Id, X-API-Key pour un service)
  ├─ compte sans visage   → session « mot de passe seul » (consultation, enregistrement du visage)
  ├─ service (sonde)      → session active, comptes de la sonde uniquement
  └─ compte avec visage   → { mfa_required, session_id, face_challenge: { direction, frames } }
POST /login/face      images de la caméra, tête tournée du côté demandé → JWT (amr = pwd, face)
```

La reconnaissance faciale est faite **par auth-service** avec le modèle pré-entraîné InsightFace
`buffalo_s` (détection + embeddings ArcFace, CPU, embarqué dans l'image Docker). Le serveur ne garde
aucune image : seulement 3 à 5 gabarits par client, chiffrés en AES-256-GCM (`app/face/`).

| Endpoint | Rôle |
|---|---|
| `POST /register` | Création de compte (email, téléphone, nom, mot de passe) |
| `POST /login` · `POST /login/face` | Connexion (mot de passe, puis visage) |
| `POST /logout` | Révocation de la session |
| `POST /face/enroll` | Enregistrer ou remplacer son visage (consentement explicite) |
| `GET /face` · `DELETE /face` | État de l'enrôlement · droit à l'effacement |
| `GET /me` | Profil, facteurs de la session, visage enregistré ou non |
| `GET /verify` | Validation d'une clé d'API partenaire (`X-API-Key`) |
| `POST /operators/login` · `POST /operators/logout` · `GET /operators/me` | Opérateurs du back-office (mot de passe seul, JWT d'audience `orbe-bo`), relayés par bo-api |
| `GET /health/live` · `GET /health/ready` | Santé du processus · base joignable |
| `GET /metrics` | Métriques Prometheus |

Images : JPEG ou PNG encodés en base64, 400 Ko maximum chacune ; 8 à la connexion (12 au plus),
~16 à l'enrôlement en tournant lentement la tête de gauche à droite (20 au plus).

JWT RS256 de 15 min : `sub`, `email`, `jti` (= identifiant de session), `amr` (facteurs), `cid` / `cty`
(application cliente et son type). Chaque requête authentifiée vérifie que la session est **active en base**.

Erreurs : `{"detail": {"code": "...", "message": "..."}}` — `invalid_credentials`, `account_locked`
(423, `Retry-After`), `too_many_attempts`, `invalid_client`, `client_not_allowed`, `second_factor_failed`,
`liveness_failed`, `consent_required`, `enrollment_failed`, `face_confirmation_required`,
`invalid_frame`, `too_many_frames`, `frame_too_large`, `face_unavailable`, `invalid_token`,
`invalid_api_key`.

## Opérateurs du back-office

Comptes distincts des clients (tables `operators`, `operator_sessions`), sans inscription : ils
sont créés par `scripts/create_operator.py` (compte root de MariaDB ; `auth_svc` ne peut ni
créer d'opérateur ni changer un rôle). Mot de passe seul, mêmes protections que les clients
(blocage après 5 échecs, limitation par IP). JWT d'audience `orbe-bo` valable 1 h, avec `role`
(`viewer` ou `operator`) : un jeton client n'ouvre pas le back-office, et un jeton opérateur
n'est pas accepté par payment-service.

## Sécurité
- Mots de passe argon2id ; hachages et vérifications limités à 4 en parallèle (mémoire bornée).
- Inscription : 8 caractères minimum, mots de passe courants refusés, 5 inscriptions par minute
  et par IP ; insertion limitée aux colonnes autorisées (jamais de compte de sonde).
- 5 échecs (mot de passe **ou visage**) → compte bloqué 10 min ; 20 tentatives par minute et par IP.
- Visage : similarité cosinus ≥ 0,40 sur au moins 3 images ; détection du vivant par défi
  (tourner la tête dans un sens tiré au hasard : une photo figée échoue). Un échec ferme la session
  en attente ; une session ne sert qu'une fois.
- Gabarits chiffrés et liés à leur propriétaire (client_id en donnée authentifiée) ; clé dans un
  secret Docker ou Vault Transit. Un compte qui a un visage ne le remplace ou ne le supprime que
  depuis une session confirmée par ce visage.
- Aucun mot de passe, jeton, clé d'API, image ni gabarit dans les journaux.

## Configuration (préfixe `AUTH_`)
| Variable | Défaut |
|---|---|
| `AUTH_DB_HOST` / `AUTH_DB_PORT` / `AUTH_DB_NAME` / `AUTH_DB_USER` | `mariadb` / `3306` / `orbe` / `auth_svc` |
| `AUTH_DB_PASSWORD_FILE` | `/run/secrets/auth_db_password` |
| `AUTH_JWT_PRIVATE_KEY_FILE` | `/run/secrets/jwt_private_key` |
| `AUTH_JWT_TTL_SECONDS` | `900` |
| `AUTH_BO_JWT_AUDIENCE` / `AUTH_BO_JWT_TTL_SECONDS` | `orbe-bo` / `3600` |
| `AUTH_FACE_ENGINE` | `insightface` (`fake` : moteur simulé, tests et développement sans caméra) |
| `AUTH_FACE_MODEL` / `AUTH_FACE_THRESHOLD` | `buffalo_s` / `0.40` |
| `AUTH_LIVENESS_MIN_TURN_DEGREES` | `8.0` |
| `AUTH_FACE_CIPHER` | `local` (clé `AUTH_FACE_KEY_FILE`) ou `vault` (Transit, clé `orbe-face`) |
| `AUTH_FACE_KEY_FILE` | `/run/secrets/face_embedding_key` (64 caractères hexadécimaux) |
| `AUTH_PENDING_2FA_SECONDS` | `120` |
| `AUTH_LOCKOUT_THRESHOLD` / `AUTH_LOCKOUT_MINUTES` | `5` / `10` |
| `AUTH_LOGIN_RATE_PER_IP` / `AUTH_REGISTER_RATE_PER_IP` | `20` / `5` |
| `AUTH_VAULT_KV_PATH` | vide : secrets lus dans `/run/secrets/` ; démonstration : `secret/data/oorbe/config` |
| `AUTH_VAULT_ADDR` / `AUTH_VAULT_TOKEN_FILE` | `http://vault:8200` / `/run/secrets/auth_vault_token` (jeton en lecture seule) |
| `AUTH_VAULT_ROLE_ID_FILE` / `AUTH_VAULT_SECRET_ID_FILE` | AppRole, prioritaire sur le jeton s'ils existent |
| `AUTH_DB_PASSWORD_KEY` / `AUTH_FACE_KEY_NAME` | `auth_db_password` / `face_embedding_key` : noms de la clé dans Vault (repli : fichier de secret) |
| `AUTH_ENABLE_DOCS` | `false` (Swagger sur `/docs` si `true`) |

## Développement
```bash
py -3.13 -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
.venv/Scripts/python -m pytest
.venv/Scripts/python -m ruff check .
```
Les tests utilisent SQLite en mémoire et le moteur de visage simulé (`FakeFaceEngine`) ; ni
MariaDB, ni caméra, ni modèle ne sont nécessaires. Pour essayer le vrai modèle hors Docker :
`.venv/Scripts/python -m pip install -e ".[face]"`.

Clés JWT locales : `python scripts/gen_jwt_keys.py` à la racine du dépôt.
