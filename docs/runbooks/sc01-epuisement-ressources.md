# Runbook SC-01 — épuisement de ressources de payment-service

> Scénario principal de la démonstration. Réponse **automatique** par le moteur de remédiation ;
> ce runbook explique ce qui se passe et comment le vérifier. Aucune action manuelle n'est attendue.

## SC-01 — description de l'attaque

| Élément | Contenu |
|---|---|
| Catégorie | Disponibilité, couche applicative |
| Ressource visée | Pool de connexions MariaDB (10 par instance) et workers de payment-service |
| Chemin | PC Attaquant → hotspot → WAF :443 → `POST /api/payments/pay` |
| Outil | `redteam/sc01/`, script Python paramétrable (cible, durée, intensité), lancé **uniquement depuis le PC Attaquant** contre le WAF de l'équipe |

Chaque paiement garde sa connexion à la base pendant l'autorisation simulée (50–150 ms). Un grand nombre
de paiements simultanés occupe les 10 connexions du pool ; les requêtes suivantes attendent 2 s puis
échouent en `503`.

## SC-01 — symptômes observables

- `probe_transaction_success` passe à **0** : la sonde ne peut plus payer.
- `payment_db_pool_in_use` reste à 10, `payment_db_pool_timeouts_total` augmente.
- Latence p95 et taux de `503` en forte hausse.
- `/health/ready` d'une ou des deux instances renvoie `503` avec `pool: saturated`.
- Journaux payment-service : événements `db_pool_timeout` en série.
- Journaux WAF : trafic concentré sur une ou quelques IP (celle du PC Attaquant).
- Frontend : bandeau d'incident, bouton « Payer » désactivé (`payments_enabled: false`).

## SC-01 — détection

1. detector-ml calcule ses variables toutes les 5 s : saturation du pool, p95, 5xx et concentration sur peu d'IP s'écartent de la normale.
2. `anomaly_score{target="payment-service"}` dépasse le seuil (0,7 indicatif).
3. Après 10 s au-dessus du seuil, l'alerte **PaymentAnomaly** passe à l'état *firing*.
4. Alertmanager l'envoie au moteur (`POST /webhook/alert`).

Objectif : détection en **15 s au plus** après le début de l'effet.

## SC-01 — actions automatiques du moteur (`pb-contain-and-recover.yml`)

| Étape | Action | But |
|---|---|---|
| 1 | Requête Loki : IP sources qui contribuent le plus au trafic des 30 dernières secondes, hors liste blanche (sonde) | Cibler |
| 2 | Écriture de ces IP dans `blocklist.conf` (TTL 15 min) et signal `HUP` au WAF via le socket-proxy | **Contenir** : le trafic d'attaque est rejeté en `403` au WAF |
| 3 | Appel de `/health/ready` sur chaque instance `payment-*` | Diagnostiquer les instances dégradées |
| 4 | Redémarrage des instances dégradées ; l'instance saine continue de servir via le WAF | **Rétablir** |
| 5 | Attente de `/health/ready` OK sur les deux instances (20 s maximum) | Préparer |
| 6 | Vérification complète (voir `verification-reprise.md`) | **Prouver** |

L'ordre compte : on contient **avant** de redémarrer, sinon l'attaque saturerait à nouveau le pool dès le
redémarrage.

## SC-01 — escalade

Si la vérification échoue, le moteur passe au niveau 2, **`pb-redeploy-clean.yml`** : recréation des
conteneurs payment-service depuis l'image de référence étiquetée, puis nouvelle vérification. Si elle
échoue encore, l'incident passe à `failed` (alerte `RemediationFailed`).

## SC-01 — vérifier que le paiement remarche

1. Dashboard : frise de l'incident jusqu'à **`verified`**, avec les étapes horodatées.
2. `probe_transaction_success` revenu à **1**.
3. Bandeau du frontend « Service rétabli » avec la référence de la transaction de vérification.
4. Faire un paiement réel depuis l'application avec la carte `4242 4242 4242 4242` : réponse `authorized`.
5. Grafana SOC : actions `event="action"` du moteur (IP bloquée, redémarrage, vérification).

## SC-01 — données après la reprise

L'attaque ne corrompt pas les données. Les paiements interrompus pendant le redémarrage restés `pending`
plus de 30 s passent en `failed` (motif `recovery`) : aucune écriture comptable n'a été passée pour eux,
donc aucun argent n'a bougé. L'idempotence empêche qu'un paiement rejoué soit débité deux fois. Le
contrôle de cohérence de la vérification doit renvoyer **0 violation**.

## SC-01 — garde-fous techniques

- Limites `cpus`, `mem_limit` et `pids_limit` sur chaque conteneur : seul payment-service est affecté, la supervision et le moteur restent opérationnels.
- Deux instances de paiement et sortie automatique d'une instance en échec au WAF.
- Cooldown de 120 s par cible : le moteur ne redémarre pas en boucle.

## SC-01 — rejouer le scénario

Entre deux répétitions, exécuter `reset.yml` (`scripts/reset.ps1`) : vide la liste de blocage, archive les
incidents, relance les services. Sans cela, l'IP du PC Attaquant reste bloquée 15 minutes et le cooldown
du moteur peut empêcher une nouvelle action.
