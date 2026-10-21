# MariaDB — base de données d'Orbe

## MariaDB — rôle

Une seule base **`orbe`** (MariaDB 11.4), partagée par auth-service et payment-service. Chaque service
utilise son propre compte, limité aux tables et colonnes dont il a besoin. La base n'est joignable que sur
le réseau interne `net-app`. Modèle de données et règles de gestion : `docs/mcd.md`.

## MariaDB — tables principales

`clients`, `client_apis`, `client_face_templates`, `sessions`, `ledger_accounts`, `ledger_entries`,
`payout_accounts`, `contacts`, `transactions`, `payment_requests`. Schéma : `infra/mariadb/init/01-schema.sql`.

## MariaDB — comptes à moindre privilège

| Compte | Droits |
|---|---|
| `auth_svc` | `clients` (lecture, mise à jour de `failed_logins`, `locked_until`, `biometric_consent_at` ; insertion limitée à `id, email, phone, display_name, password_hash`), `client_apis` (lecture), `client_face_templates`, `sessions` |
| `payment_svc` | `clients` (lecture, mise à jour de `qr_token`), `sessions` (lecture de quelques colonnes), `ledger_accounts`, `ledger_entries` (lecture, insertion), `transactions`, `payment_requests`, `payout_accounts`, `contacts` |
| `remediation_ro` | Lecture seule de `transactions`, `ledger_entries`, `ledger_accounts` (contrôles de cohérence) |
| `exporter` | `PROCESS, REPLICATION CLIENT, SLAVE MONITOR` (métriques) |

Une inscription ne peut pas créer de compte de sonde : `auth_svc` n'a pas le droit d'écrire `is_probe`.

## MariaDB — connexions

`max_connections=60`. Chaque instance de payment-service ouvre au plus 10 connexions (pool sans
débordement). La métrique `mysql_global_status_threads_connected` suit le nombre de connexions ouvertes.

## MariaDB — sauvegarde et restauration

- `mariadb-dump` toutes les **5 minutes** vers un volume dédié, rétention **24 h** (RPO de 5 min).
- Playbooks `backup.yml` et `restore.yml`.
- Une restauration n'est pas nécessaire pour SC-01 : l'attaque ne corrompt pas les données, et la réconciliation traite les transactions `pending`.

## MariaDB — données de démo

Jeu fictif (Faker) : clients `@orbe.test`, téléphones `+33 6…`, comptes de retrait fictifs, historique
couvrant tous les statuts. Comptes de démo : `camille@orbe.test`, `lea@orbe.test`, `hugo@orbe.test`
(mot de passe commun de démo défini dans le README), comptes de sonde `probe@orbe.test` et
`probe-recipient@orbe.test`.
