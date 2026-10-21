# Runbook — diagnostic par un opérateur

> À utiliser pour comprendre un incident, ou quand le moteur a échoué (`failed`). En démonstration, toute
> intervention corrective manuelle annule le critère de remédiation autonome.

## Diagnostic — par où commencer

1. **Un paiement passe-t-il ?** `probe_transaction_success`. Si 1, le service métier fonctionne.
2. **Quelle étape échoue ?** `probe_step_failures_total{step}` : `login` → auth-service ; `pay` → payment-service ou base ; `read` → payment-service.
3. **Y a-t-il un incident en cours ?** Dashboard, liste des incidents : état et dernière étape.
4. **Pourquoi le modèle a-t-il alerté ?** `top_deviations` dans le dashboard.

## Diagnostic — payment-service répond en 503

- `/health/ready` de chaque instance : `pool: saturated` → pool plein (SC-01 ou lenteur de la base) ; `database: down` → MariaDB injoignable ou trop lente (> 2 s).
- Journaux : `db_pool_timeout` (pool) ou `db_unavailable` (base).
- Trafic : IP sources dans les journaux du WAF. Une IP très majoritaire indique une attaque.

## Diagnostic — paiement refusé avec 403

| Réponse | Cause |
|---|---|
| `403` renvoyé par le WAF | IP présente dans la liste de blocage (TTL 15 min) ou règle WAF déclenchée |
| `403 second_factor_required` | Session « mot de passe seul » : le visage n'est pas enregistré ou pas vérifié |
| `403` sur un remboursement | Seul le bénéficiaire peut rembourser |

## Diagnostic — la connexion échoue

- `401 second_factor_failed` : visage non reconnu (éclairage, cadrage). `401 liveness_failed` : tête pas assez tournée ou mauvais côté.
- `423` : compte bloqué 10 minutes après 5 échecs.
- `429` : limitation de débit par IP.

## Diagnostic — le moteur n'a pas réagi

- L'alerte est-elle *firing* dans Prometheus ? Sinon : score sous le seuil, ou detector-ml arrêté (`up{job="detector-ml"}`).
- Alertmanager a-t-il envoyé le webhook ? Journaux d'Alertmanager.
- Le moteur a-t-il reçu l'alerte mais ignoré l'action ? Cooldown de 120 s sur la cible, ou incident déjà ouvert (déduplication).
- Le moteur peut-il joindre Docker ? Il passe par `socket-proxy` ; une opération non autorisée par le proxy est refusée.

## Diagnostic — le moteur a échoué (`failed`)

Lire la frise : l'étape en échec indique la suite.

- Échec à « contenir » : le WAF n'a pas rechargé la liste de blocage (signal `HUP` refusé par le proxy, ou fichier non partagé).
- Échec à « rétablir » : `/health/ready` ne revient pas en 20 s. Vérifier MariaDB (`max_connections=60`, connexions ouvertes).
- Échec à « vérifier » : lire quel contrôle a échoué. Une violation de cohérence appelle un examen des transactions concernées, pas un redémarrage.

## Diagnostic — l'assistant ne répond pas ou répond lentement

Le premier appel après un démarrage charge le modèle en mémoire (20 à 30 s sur CPU). Si Ollama est sur le
PC IA, vérifier que le PC IA est sur le hotspot et que son pare-feu autorise l'IP du PC Hôte sur le port
11434.
