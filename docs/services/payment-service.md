# payment-service — service de paiement d'Orbe

Port interne **8002**, deux instances (`payment-service-a`, `payment-service-b`) derrière le WAF sous
`/api/payments/*`. Python 3.12 / FastAPI, SQLAlchemy async, MariaDB.

## payment-service — modèle métier

Un client envoie à un autre client le montant de son choix, ou lui **demande** de l'argent. Le payeur paie
avec une **carte de test** ; le bénéficiaire est crédité sur son **solde Orbe**, qu'il peut rembourser
ou retirer vers un **compte lié** fictif. Le bénéficiaire est désigné par email, téléphone ou QR code.
Aucune intégration bancaire réelle : tout est simulé.

## payment-service — principaux endpoints

| Endpoint | Rôle |
|---|---|
| `POST /pay` | Payer un bénéficiaire (en-tête `Idempotency-Key` obligatoire) |
| `GET /transactions`, `GET /transactions/{reference}` | Historique, détail |
| `POST /transactions/{reference}/refund` | Remboursement par le bénéficiaire |
| `GET /account` | Solde et compte lié |
| `POST /payouts` | Retrait vers le compte lié |
| `POST /requests`, `GET /requests`, `…/pay`, `…/decline`, `…/cancel` | Demandes d'argent |
| `GET /qr`, `POST /qr/rotate` | QR « Recevoir » |
| `GET/POST/DELETE /contacts`, `/payout-accounts` | Contacts, comptes liés |
| `GET /health/live`, `GET /health/ready`, `GET /metrics` | Santé, métriques |

Détail complet : `docs/api/payment-service.openapi.json`.

## payment-service — cartes de test

| Numéro | Résultat |
|---|---|
| `4242 4242 4242 4242` | `authorized` |
| `4000 0000 0000 0002` | `declined` — `card_declined` |
| `4000 0000 0000 0069` | `declined` — `card_expired` |
| `4000 0000 0000 9995` | `declined` — `insufficient_funds` |
| autre numéro, Luhn invalide ou date passée | `422` |

Seuls la marque et les 4 derniers chiffres sont stockés. Le numéro complet et le CVC ne sont jamais stockés
ni journalisés. Un refus de carte est une réponse `201` avec `status: "declined"` : la transaction existe,
elle est refusée.

## payment-service — règles de contrôle

- Montant entier en centimes, de 1 à **50 000 (500 €)**, devise `EUR` uniquement, frais nuls.
- Session active, non révoquée, confirmée par le visage (sinon `403 second_factor_required`).
- **10 paiements par minute et par client** au maximum.
- Remboursement : par le bénéficiaire uniquement, total, une seule fois, si son solde le permet.
- Retrait : montant ≤ solde.
- Bénéficiaire inconnu : réponse neutre `decline_reason: "recipient_not_found"` (anti-énumération).

## payment-service — idempotence

Chaque opération d'écriture exige un en-tête `Idempotency-Key` (UUID). Rejouer la même clé avec le même
corps renvoie `200` et la transaction d'origine ; la même clé avec un corps différent renvoie `409`.
Cela empêche un double débit si un client ou la sonde renvoie la requête pendant un incident.

## payment-service — comptabilité en partie double

Toute opération autorisée ou effectuée crée **exactement deux écritures** de même montant (un débit, un
crédit) dans la même transaction SQL. Une opération refusée, échouée ou en attente n'en crée aucune.

| Opération | Débit | Crédit |
|---|---|---|
| Paiement autorisé | « Encaissements carte » | compte Orbe du bénéficiaire |
| Remboursement | compte Orbe du bénéficiaire | « Encaissements carte » |
| Retrait | compte Orbe du client | « Retraits » |

## payment-service — pool de connexions, ressource critique

- Pool SQLAlchemy : `pool_size=10`, `max_overflow=0`, `pool_timeout=2s` par instance. MariaDB : `max_connections=60`.
- L'autorisation simulée dure 50–150 ms **en gardant la connexion ouverte** : un afflux de paiements sature vite le pool.
- Quand le pool est plein, une requête attend 2 s puis échoue en **`503`** (événement de journal `db_pool_timeout`, compteur `payment_db_pool_timeouts_total`).
- C'est la ressource visée par le scénario **SC-01**.

## payment-service — que vérifie `/health/ready`

`GET /health/ready` répond `200 {"status":"ok"}` seulement si :

1. le pool n'est **pas saturé** (connexions utilisées < taille du pool) ;
2. la base répond à `SELECT 1` en moins de **2 secondes**.

Sinon `503` avec le détail : `{"pool": "saturated"}` ou `{"database": "down"}`. C'est ce contrôle que le
moteur de remédiation utilise pour repérer une instance dégradée, puis pour attendre son retour.
`/health/live` indique seulement que le processus répond.

## payment-service — réconciliation après incident

Au démarrage puis toutes les **15 s**, toute transaction restée `pending` depuis plus de **30 s** passe en
`failed` avec le motif `recovery` (événement `pending_reconciled`, compteur `payment_reconciled_total`).
Cela couvre le cas d'une instance redémarrée au milieu d'un paiement : l'argent n'a pas bougé, aucune
écriture n'a été passée.

## payment-service — contrôles de cohérence

Fonction `ledger_violations` (fichier `app/consistency.py`), reprise par le moteur de remédiation :

1. pour chaque opération, somme des débits = somme des crédits (`unbalanced_operation`) ;
2. opération réglée → exactement 2 écritures, sinon aucune (`entry_count`) ;
3. pour chaque compte, solde = crédits − débits (`balance_mismatch`) ;
4. aucun compte client en solde négatif (`negative_client_balance`).

Zéro violation est une condition de clôture d'un incident.
