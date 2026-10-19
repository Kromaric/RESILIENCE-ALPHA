# payment-service

Service FastAPI de paiement d'Orbe — port interne **8002**, déployé en **2 instances**.
Voir CADRAGE §4.3 et §5.

Un client envoie de l'argent à un autre client (email, téléphone ou QR code) en payant avec une
**carte de test** ; le bénéficiaire est crédité sur son **solde Orbe**, qu'il peut rembourser
ou retirer vers son compte lié fictif. Un client peut aussi **demander** de l'argent.

## Endpoints

Tous exigent `Authorization: Bearer <JWT>` (vérifié localement avec la clé publique d'auth-service).
Les opérations qui déplacent de l'argent exigent `Idempotency-Key: <uuid>` :
`201` à la création, `200` si la même clé est rejouée, `409` si elle a servi à autre chose.

| Endpoint | Rôle |
|---|---|
| `POST /pay` | Transfert payé par carte de test (`recipient` ou `recipient_qr`) |
| `GET /transactions` · `GET /transactions/{reference}` | Historique (`status`, `direction`, `limit`, `cursor`) |
| `POST /transactions/{reference}/refund` | Remboursement total par le bénéficiaire |
| `GET /account` | Solde et compte lié |
| `POST /payouts` | Retrait vers le compte lié |
| `POST /requests` · `GET /requests` | Créer / lister les demandes d'argent |
| `POST /requests/{reference}/pay` · `/decline` · `/cancel` | Payer, refuser (payeur) ou annuler (demandeur) |
| `GET /qr` · `POST /qr/rotate` | Jeton du QR « Recevoir », renouvellement |
| `GET /health/live` · `GET /health/ready` | Processus · pool non saturé et base joignable |
| `GET /metrics` | Métriques Prometheus |

Erreurs : `{"detail": {"code": "...", "message": "..."}}`. Un refus de carte n'est **pas** une
erreur HTTP : `201` avec `status: "declined"` et `decline_reason`.

## Cartes de test
| Numéro | Résultat |
|---|---|
| `4242 4242 4242 4242` | `authorized` |
| `4000 0000 0000 0002` | `declined` — `card_declined` |
| `4000 0000 0000 0069` | `declined` — `card_expired` |
| `4000 0000 0000 9995` | `declined` — `insufficient_funds` |

Seuls la marque et les 4 derniers chiffres sont stockés ; le numéro complet et le CVC ne sont
jamais stockés, journalisés ni renvoyés dans les erreurs de validation.

## Résilience
- Pool de 10 connexions, `max_overflow=0`, attente maximale 2 s : au-delà, `503 service_unavailable`
  avec `Retry-After: 2`. L'autorisation simulée (50–150 ms) **garde sa connexion**, ce qui fait du
  pool la ressource critique du scénario SC-01.
- `/health/ready` passe à `503` dès que le pool est saturé ou que la base ne répond plus.
- Réconciliation au démarrage puis toutes les 15 s : un paiement `pending` depuis plus de 30 s
  passe en `failed` (`recovery`) et libère la demande d'argent qu'il réservait.
- Invariant des soldes (`app/consistency.py::balance_violations`) : requête de référence pour la
  vérification de la remédiation.

## Configuration (préfixe `PAYMENT_`)
| Variable | Défaut |
|---|---|
| `PAYMENT_DB_HOST` / `PAYMENT_DB_PORT` / `PAYMENT_DB_NAME` / `PAYMENT_DB_USER` | `mariadb` / `3306` / `orbe` / `payment_svc` |
| `PAYMENT_DB_PASSWORD_FILE` | `/run/secrets/payment_db_password` |
| `PAYMENT_DB_POOL_SIZE` / `PAYMENT_DB_POOL_TIMEOUT` | `10` / `2.0` |
| `PAYMENT_JWT_PUBLIC_KEY_FILE` | `/run/secrets/jwt_public_key` |
| `PAYMENT_MAX_AMOUNT_CENTS` | `500000` |
| `PAYMENT_PAY_RATE_PER_CLIENT` | `10` par minute (`0` = désactivé) — **à régler avec la Red Team** |
| `PAYMENT_AUTHORIZATION_MIN_MS` / `_MAX_MS` | `50` / `150` |
| `PAYMENT_RECONCILE_ENABLED` / `_AFTER_SECONDS` / `_INTERVAL_SECONDS` | `true` / `30` / `15` |
| `PAYMENT_ENABLE_DOCS` | `false` (Swagger sur `/docs` si `true`) |

## Développement
```bash
py -3.13 -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
.venv/Scripts/python -m pytest
.venv/Scripts/python -m ruff check .
```
Les tests utilisent SQLite en mémoire ; aucun MariaDB n'est nécessaire.
