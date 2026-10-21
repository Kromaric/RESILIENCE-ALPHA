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

## Sécurité
- Mots de passe argon2id ; hachages et vérifications limités à 4 en parallèle (mémoire bornée).
- Inscription : 8 caractères minimum, mots de passe courants refusés, 5 inscriptions par minute
  et par IP ; insertion limitée aux colonnes autorisées (jamais de compte de sonde).
- 5 échecs (mot de passe **ou visage**) → compte bloqué 10 min ; 20 tentatives par minute et par IP.
- Visage : similarité cosinus ≥ 0,40 sur au moins 3 images ; détection du vivant par défi
  (tourner la tête dans un sens tiré au hasard : une photo figée échoue). Un échec ferme la session
  en attente ; une session ne sert qu'une fois.
