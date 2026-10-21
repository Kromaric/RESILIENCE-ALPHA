# Catalogue des alertes d'Orbe

> Une fiche par alerte, sous le nom exact affiché dans Prometheus, Alertmanager et Grafana.
> Statut : **définie** = présente dans le cadrage ; **proposée** = à ajouter aux règles Prometheus ou Loki.

## PaymentAnomaly

- **Statut** : définie (`prometheus/rules/anomaly.yml`).
- **Expression** : `anomaly_score{target="payment-service"} > 0.7` pendant **10 s** (seuil à confirmer par `ml/evaluate.py`).
- **Labels** : `severity: critical`, `incident_type: resource_exhaustion`, `target: payment-service`.
- **Signification** : le modèle IsolationForest juge le comportement de payment-service très éloigné de la normale sur les 30 dernières secondes. Les variables responsables sont listées dans `top_deviations` (`GET /score` de detector-ml, panneau du dashboard).
- **Cause typique** : scénario SC-01 (afflux de paiements qui sature le pool de connexions).
- **Action automatique** : Alertmanager appelle `remediation-engine`, qui ouvre un incident `resource_exhaustion` et exécute `pb-contain-and-recover.yml` (contenir au WAF → redémarrer les instances dégradées → vérifier). Détail : `runbooks/sc01-epuisement-ressources.md`.
- **Vérification** : incident `verified` dans le dashboard ; `probe_transaction_success = 1` ; `anomaly_score` revenu sous le seuil ; `/api/status` à `operational`.
- **Faux positif possible** : pic de trafic légitime. Le modèle est entraîné pour le tolérer ; si l'alerte se déclenche sans 5xx ni saturation du pool, le signaler pour réentraîner le modèle.

## ProbeTransactionFailed

- **Statut** : proposée (filet de sécurité, complémentaire au modèle).
- **Expression proposée** : `probe_transaction_success == 0` pendant **20 s** (deux cycles de sonde).
- **Labels proposés** : `severity: critical`, `incident_type: resource_exhaustion`, `target: payment-service`.
- **Signification** : la sonde n'arrive plus à faire un paiement de bout en bout à travers le WAF. Un vrai client ne peut probablement plus payer non plus.
- **Causes possibles** : SC-01, payment-service arrêté, MariaDB indisponible, auth-service en échec (étape `login`), WAF qui bloque.
- **Diagnostic** : `probe_step_failures_total{step}` indique l'étape qui échoue (`login` → regarder auth-service ; `pay` → payment-service ou base ; `read` → payment-service).
- **Action automatique** : même politique que PaymentAnomaly ; la déduplication du moteur rattache les deux alertes au même incident.

## PaymentPoolSaturated

- **Statut** : proposée (alerte d'information pour le dashboard, non routée vers la remédiation).
- **Expression proposée** : `max(payment_db_pool_in_use / payment_db_pool_size) >= 1` pendant 10 s.
- **Signification** : au moins une instance de payment-service a utilisé ses 10 connexions. Les nouvelles requêtes attendent 2 s puis échouent en `503` (`db_pool_timeout`).
- **À regarder** : `payment_db_pool_timeouts_total`, `/health/ready` des instances (`pool: saturated`), IP sources dans les journaux du WAF.

## ServiceDown

- **Statut** : proposée.
- **Expression proposée** : `up{job=~"auth-service|payment-service"} == 0` pendant 15 s.
- **Signification** : Prometheus n'arrive plus à collecter les métriques du service : conteneur arrêté, planté, ou réseau `net-obs` coupé.
- **À regarder** : état du conteneur dans le dashboard ; journaux du conteneur dans Loki ; `restart: unless-stopped` le relance normalement seul.
- **Attention** : un conteneur qui redémarre n'est pas une preuve de reprise ; seule la sonde le prouve.

## AuthLoginFailureBurst (règle SOC)

- **Statut** : définie dans le SOC (règle Loki), routage vers la remédiation seulement si SC-02 est retenu.
- **Requête** : `count_over_time({service="auth-service"} |= "login_failed" [1m])` par IP au-dessus du seuil.
- **Signification** : rafale d'échecs de connexion depuis une même IP : force brute ou credential stuffing.
- **Défenses déjà actives** : blocage du compte 10 min après 5 échecs (`account_locked`), limitation par IP (`429`).
- **Action automatique si SC-02** : incident `compromise`, `pb-isolate-rotate-redeploy.yml`. Voir `runbooks/sc02-compromission-auth.md`.

## WafRuleTriggered (règle SOC)

- **Statut** : définie dans le SOC (panneau Grafana), pas de remédiation automatique.
- **Requête** : `{service="waf"} | json | modsec_rule_id != ""`.
- **Signification** : le WAF a reconnu et bloqué une requête malveillante (injection SQL, XSS, scanner…). La requête n'a pas atteint les services.
- **À regarder** : identifiant de règle, IP source, chemin visé. Une série de règles depuis une même IP indique une reconnaissance en cours.

## FaceInferenceSlow

- **Statut** : proposée.
- **Expression proposée** : p95 de `auth_face_inference_seconds` > 2 s pendant 30 s.
- **Signification** : l'analyse des visages ralentit, ce qui indique une possible tentative d'épuisement CPU sur auth-service (envoi massif d'images à `/login/face`).
- **À regarder** : limitation par IP (`429`), IP sources, CPU du conteneur auth-service.

## RemediationFailed

- **Statut** : proposée.
- **Expression proposée** : `increase(remediation_incidents_total{status="failed"}[5m]) > 0`.
- **Signification** : le moteur a épuisé tous les niveaux de sa politique sans réussir la vérification. **Une intervention humaine est nécessaire.**
- **À faire** : lire la frise de l'incident (étape en échec), suivre `runbooks/diagnostic-operateur.md`. En démonstration, une intervention manuelle annule le critère de remédiation autonome : on arrête la démo et on l'explique.
