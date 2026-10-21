# payment-service

Service FastAPI de paiement d'Orbe — port interne **8002**, déployé en **2 instances**.
Voir CADRAGE §4.3 et `docs/mcd.md`.

Un client envoie de l'argent à un autre client (email, téléphone, QR code ou contact) en payant avec
une **carte de test** ; le bénéficiaire est crédité sur son **compte Orbe**, qu'il peut rembourser ou
retirer vers l'un de ses **comptes liés**. Un client peut aussi **demander** de l'argent.

## Authentification
`Authorization: Bearer <JWT>` émis par auth-service, vérifié localement, et dont la **session doit être
active** (non révoquée ; statut lu en base avec un cache de 5 s). Toute opération qui déplace de
l'argent exige une session **confirmée par reconnaissance faciale** (`403 second_factor_required` sinon) ; la sonde
(application de type `service`) en est dispensée mais n'agit que sur les comptes de la sonde.

Les opérations qui déplacent de l'argent exigent `Idempotency-Key: <uuid>` : `201` à la création,
`200` si la même clé est rejouée, `409` si elle a servi à autre chose.

## Endpoints
| Endpoint | Rôle |
|---|---|
| `POST /pay` | Transfert par carte de test (`recipient`, `recipient_qr` ou `recipient_contact`), 500 € max |
| `GET /transactions` · `GET /transactions/{reference}` | Historique (`status`, `direction`, `limit`, `cursor`) |
| `POST /transactions/{reference}/refund` | Remboursement total par le bénéficiaire |
| `GET /account` | Solde et comptes liés |
| `GET/POST /payout-accounts` · `POST /payout-accounts/{id}/default` · `DELETE /payout-accounts/{id}` | Comptes liés (IBAN fictif contrôlé, 4 derniers caractères conservés) |
| `POST /payouts` | Retrait vers le compte lié choisi ou par défaut |
| `GET/POST /contacts` · `DELETE /contacts/{id}` | Carnet de contacts (clients Orbe uniquement) |
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

## Comptabilité en partie double
Chaque opération autorisée passe **deux écritures** de même montant (`app/ledger.py`) :

| Opération | Débit | Crédit |
|---|---|---|
| Paiement autorisé | contrepartie « Encaissements carte » | compte Orbe du bénéficiaire |
| Remboursement | compte Orbe du bénéficiaire | contrepartie « Encaissements carte » |
| Retrait | compte Orbe du client | contrepartie « Retraits » |

Contrôles de cohérence (`app/consistency.py::ledger_violations`, requêtes de référence pour la
remédiation) : opérations équilibrées, 2 écritures par opération réglée et aucune sinon, solde de
chaque compte = Σ crédits − Σ débits, aucun compte client négatif.

## Résilience
- Pool de 10 connexions, `max_overflow=0`, attente maximale 2 s : au-delà, `503 service_unavailable`
  avec `Retry-After: 2`. L'autorisation simulée (50–150 ms) **garde sa connexion**, ce qui fait du
  pool la ressource critique du scénario SC-01.
- `/health/ready` passe à `503` dès que le pool est saturé ou que la base ne répond plus.
- Réconciliation au démarrage puis toutes les 15 s : un paiement `pending` depuis plus de 30 s
  passe en `failed` (`recovery`) et libère la demande d'argent qu'il réservait.

## Configuration (préfixe `PAYMENT_`)
| Variable | Défaut |
|---|---|
| `PAYMENT_DB_HOST` / `PAYMENT_DB_PORT` / `PAYMENT_DB_NAME` / `PAYMENT_DB_USER` | `mariadb` / `3306` / `orbe` / `payment_svc` |
| `PAYMENT_DB_PASSWORD_FILE` | `/run/secrets/payment_db_password` |
| `PAYMENT_DB_POOL_SIZE` / `PAYMENT_DB_POOL_TIMEOUT` | `10` / `2.0` |
| `PAYMENT_JWT_PUBLIC_KEY_FILE` | `/run/secrets/jwt_public_key` |
| `PAYMENT_MAX_AMOUNT_CENTS` | `50000` (500 €) |
| `PAYMENT_PAY_RATE_PER_CLIENT` | `10` par minute (`0` = désactivé) — **à régler avec la Red Team** |
| `PAYMENT_SESSION_CACHE_SECONDS` | `5.0` (délai maximal de prise en compte d'une révocation) |
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
