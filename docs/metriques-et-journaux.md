# Métriques et événements de journal d'Orbe

> Noms relevés dans le code (`app/metrics.py`, `log_event`) pour auth-service et payment-service ;
> les autres composants sont marqués *(cible)*.

## Métriques HTTP communes (instrumentator FastAPI)

| Métrique | Sens |
|---|---|
| `http_requests_total{handler,method,status}` | Nombre de requêtes par route et code de réponse |
| `http_request_duration_seconds_bucket{handler}` | Histogramme des durées de réponse (latence p95) |
| `http_requests_inprogress` | Requêtes en cours de traitement |

## Métriques de payment-service

| Métrique | Sens | Lecture pendant SC-01 |
|---|---|---|
| `payment_transactions_total{type,status}` | Opérations traitées par type (`payment`, `refund`, `payout`) et statut | Les `authorized` s'effondrent |
| `payment_declines_total{reason}` | Paiements refusés par motif (`card_declined`, `recipient_not_found`…) | — |
| `payment_requests_total{status}` | Demandes d'argent | — |
| `payment_authorization_seconds` | Durée de l'autorisation simulée, connexion DB conservée | Normale : 50–150 ms |
| `payment_db_pool_in_use` | Connexions du pool utilisées | Monte à 10 |
| `payment_db_pool_size` | Taille du pool (10) | Fixe |
| `payment_db_pool_timeouts_total` | Requêtes refusées faute de connexion (→ `503`) | Augmente fortement |
| `payment_db_errors_total` | Erreurs de connexion à la base | Augmente si MariaDB tombe |
| `payment_reconciled_total` | Paiements `pending` passés en `failed` par la réconciliation | Peut augmenter après le redémarrage |

## Métriques d'auth-service

| Métrique | Sens |
|---|---|
| `auth_logins_total` | Connexions réussies |
| `auth_login_failures_total{reason}` | Échecs : `invalid_credentials`, `locked`, `rate_limited` |
| `auth_account_locks_total` | Comptes bloqués après 5 échecs |
| `auth_api_key_failures_total` | Clés d'API refusées |
| `auth_second_factor_total{result}` | Vérifications du visage : `recognized`, `liveness_failed`, `face_not_recognized` |
| `auth_face_enrollments_total{result}` | Enrôlements du visage |
| `auth_face_inference_seconds` | Durée d'analyse d'une série d'images |
| `auth_sessions_revoked_total{reason}` | Sessions révoquées |
| `auth_registrations_total{result}` | Inscriptions |

## Métriques des autres composants *(cible)*

| Métrique | Composant | Sens |
|---|---|---|
| `probe_transaction_success` | probe | 1 = un paiement de bout en bout passe ; 0 = échec |
| `probe_transaction_duration_seconds` | probe | Durée login → pay → lecture |
| `probe_step_failures_total{step}` | probe | Échecs par étape |
| `anomaly_score{target}` | detector-ml | Score d'anomalie entre 0 et 1 |
| `anomaly_detected{target}` | detector-ml | 1 si le score dépasse le seuil |
| `detector_inference_seconds` | detector-ml | Durée d'une inférence |
| `remediation_incidents_total{type,status}` | remediation-engine | Incidents par type et état final |
| `remediation_duration_seconds` | remediation-engine | Durée détection → vérification |
| `mysql_global_status_threads_connected` | mysqld-exporter | Connexions ouvertes sur MariaDB |
| `container_cpu_usage_seconds_total`, `container_memory_working_set_bytes` | cAdvisor | CPU et mémoire par conteneur |

## Événements de journal d'auth-service

Champ `event` des journaux JSON, interrogeable dans Loki.

| Événement | Signification |
|---|---|
| `login_succeeded` | Connexion réussie (mot de passe, ou mot de passe + visage) |
| `login_failed` | Mot de passe incorrect — base de la règle SOC de force brute |
| `login_refused` | Connexion refusée (compte bloqué, limitation) |
| `account_locked` | Compte bloqué 10 min après 5 échecs |
| `second_factor_requested` | Défi visage envoyé au client |
| `second_factor_failed` | Visage non reconnu ou vivant non détecté |
| `face_enrolled`, `face_erased` | Enrôlement ou effacement du visage |
| `session_revoked` | Session révoquée (déconnexion, remédiation) |
| `api_key_rejected` | Clé d'API invalide |
| `account_registered`, `registration_refused` | Inscription acceptée ou refusée |

## Événements de journal de payment-service

| Événement | Signification |
|---|---|
| `db_pool_timeout` | Aucune connexion disponible en 2 s : la requête a reçu `503`. Signe principal de SC-01 |
| `db_unavailable` | La base ne répond pas |
| `pending_reconciled` | La réconciliation a passé des paiements `pending` en `failed` (champ `count`) |

## Événements de journal du moteur de remédiation *(cible)*

`event="action"` pour chaque étape exécutée (blocage d'IP, redémarrage, vérification), avec l'identifiant
d'incident, la cible et le résultat.

## Données jamais journalisées

Numéro de carte complet, CVC, titulaire, mot de passe, images du visage, gabarits faciaux, jetons JWT.
Un filtre explicite dans le logger de payment-service retire les données de carte.
