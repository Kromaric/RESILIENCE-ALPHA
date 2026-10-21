# FAQ opérateur — questions fréquentes pendant un incident

## Qu'est-ce que l'alerte PaymentAnomaly ?

Le modèle de détection (IsolationForest) juge le comportement de payment-service anormal depuis au moins
10 s : `anomaly_score{target="payment-service"}` au-dessus du seuil (0,7 indicatif). Le moteur de
remédiation est déclenché automatiquement. Voir `alertes/catalogue-alertes.md`.

## Que fait l'automate pendant une attaque SC-01 ?

Il bloque au WAF les IP qui génèrent le plus de trafic (sauf la sonde), redémarre les instances de
payment-service dont `/health/ready` échoue, attend leur retour, puis vérifie la reprise. Voir
`runbooks/sc01-epuisement-ressources.md`.

## Comment vérifier que le paiement remarche ?

Incident `verified` dans le dashboard, `probe_transaction_success = 1`, bandeau « Service rétabli » sur
le frontend, et un paiement réel avec la carte `4242 4242 4242 4242`. Voir `runbooks/verification-reprise.md`.

## Combien de temps dure la reprise ?

Objectif de 40 secondes au plus entre l'effet de l'attaque et la vérification (critère T6), mesuré par
`remediation_duration_seconds`.

## Faut-il intervenir manuellement ?

Non, sauf si l'incident passe à `failed`. En démonstration, une intervention corrective humaine annule la
note de remédiation autonome.

## Pourquoi un client reçoit-il un 403 ?

Soit son IP est dans la liste de blocage du WAF (15 minutes), soit sa session n'a pas été confirmée par le
visage (`second_factor_required`). Voir `runbooks/diagnostic-operateur.md`.

## Pourquoi un client reçoit-il un 503 ?

Le pool de connexions de payment-service est saturé ou la base ne répond pas : signe typique de SC-01.

## Des paiements ont-ils été perdus ou débités deux fois ?

Non. Un paiement validé est écrit de manière atomique. Un paiement interrompu reste `pending` puis passe en
`failed` (motif `recovery`) sans qu'aucun argent ne bouge. L'`Idempotency-Key` empêche le double débit
d'une requête rejouée. Le contrôle de cohérence le vérifie à chaque reprise.

## Comment débloquer l'IP du PC Attaquant ?

Attendre la fin du TTL de 15 minutes, ou lancer `scripts/reset.ps1` entre deux répétitions.

## Quelle est la différence entre l'assistant et le moteur de remédiation ?

Le moteur **agit** : il reçoit les alertes et exécute les playbooks. L'assistant **explique** : il répond
aux questions à partir de la documentation, en lecture seule, sans aucun accès au moteur, à Docker ou à la base.

## Quel modèle utilise l'assistant ?

Un modèle local de 8 milliards de paramètres au plus, servi par Ollama : Qwen2.5 3B ou Llama 3.2 3B sur
le PC Hôte, ou Llama 3.1 8B quantifié sur le PC IA. Embeddings `nomic-embed-text`.

## Quel est le RTO et le RPO d'Orbe ?

RTO de 40 s pour le scénario SC-01 sur le démonstrateur. RPO nul pour les transactions validées, et de
5 minutes en cas de restauration (sauvegarde toutes les 5 minutes). Voir `gouvernance/pca-pra.md`.

## Quels ports sont ouverts sur le PC Hôte ?

Seul le 443 du WAF sur le hotspot (`192.168.137.1`). Grafana (3000) et le dashboard (8080) uniquement sur
`127.0.0.1`. Tout le reste est interne.

## Quelles cartes de test utiliser ?

`4242 4242 4242 4242` est acceptée. `…0002` refusée, `…0069` expirée, `…9995` fonds insuffisants.
