# probe — sonde de transaction synthétique d'Orbe *(cible)*

Port interne **8006**. Code à écrire (voir `etat-implementation.md`).

## probe — rôle

La sonde exécute **toutes les 10 secondes** une vraie transaction, en passant **par le WAF** comme un
utilisateur : `login` → `pay` (carte `4242 4242 4242 4242`, 1 €) → `GET /transactions/{reference}`.
Elle mesure si un paiement passe réellement, ce qu'un conteneur « up » ne garantit pas.

## probe — métriques

| Métrique | Sens |
|---|---|
| `probe_transaction_success` | 1 si la dernière transaction de bout en bout a réussi, 0 sinon |
| `probe_transaction_duration_seconds` | Durée totale login → pay → lecture |
| `probe_step_failures_total{step}` | Échecs par étape (`login`, `pay`, `read`) |

`probe_transaction_success = 0` est le signe le plus direct qu'un client ne peut plus payer.

## probe — vérification de reprise

`POST /run` lance une transaction immédiatement. Le moteur de remédiation l'appelle **3 fois de suite**
pour clôturer un incident : 3 succès consécutifs sont exigés.

## probe — comptes et exceptions

- Deux comptes dédiés : `probe@orbe.test` (payeur) et `probe-recipient@orbe.test` (bénéficiaire), marqués `is_probe`.
- Ses transactions sont **exclues** des historiques et soldes affichés aux clients.
- Elle s'authentifie par clé d'API (application cliente de type `service`), sans visage.
- Son IP est en **liste blanche** du blocage dynamique du WAF.
- La référence de la transaction de vérification apparaît dans le bandeau « Service rétabli » du frontend.
