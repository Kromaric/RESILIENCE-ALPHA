# Observabilité d'Orbe — Prometheus, Loki, Grafana, Alertmanager

## Prometheus — collecte des métriques

- Intervalle de collecte et d'évaluation des règles : **5 s** (cible ; le dépôt est encore à 15 s).
- Cibles : auth-service, payment-service, probe, detector-ml, remediation-engine, mysqld-exporter, cAdvisor, Alertmanager.
- Accessible uniquement depuis le PC Hôte (aucune publication sur le hotspot).
- La métrique `up{job="..."}` vaut 0 quand une cible ne répond plus au scrape.

## Loki — centralisation des journaux

- Tous les services Python écrivent des journaux **JSON** : `ts`, `level`, `service`, `request_id`, `client_ip`, `method`, `path`, `status`, `duration_ms`, `msg`, et un champ `event` pour les événements métier.
- Le `request_id` est généré par le WAF (`X-Request-ID`) et propagé : il permet de suivre une requête du WAF jusqu'à la base.
- Les IP ne sont **pas** des labels Loki (cardinalité) : elles sont filtrées après le parseur `| json`.
- Rétention : 72 h.
- Collecteur : Grafana Alloy dans le cadrage (label `service`) ; Promtail dans le dépôt actuel (label `container`, par exemple `oorbe-payment-service`). Adapter les requêtes en conséquence.

## Grafana — tableaux de bord

- Accès : `http://127.0.0.1:3000` sur le PC Hôte.
- Tableaux provisionnés : métriques du nœud, journaux, **SOC**.
- Les panneaux sont intégrés au dashboard React (viewer anonyme en lecture seule sur une organisation dédiée).

## SOC intégré — règles de détection sur les journaux

| Règle | Requête LogQL (principe) |
|---|---|
| Rafale d'échecs d'authentification | `count_over_time({service="auth-service"} \|= "login_failed" [1m])` par IP > seuil |
| Règles WAF déclenchées | `{service="waf"} \| json \| modsec_rule_id != ""` |
| Actions de remédiation | `{service="remediation-engine"} \| json \| event="action"` |
| Alertes IDS *(si Snort)* | `{service="snort"}` |

Tableau de bord « SOC » : événements de sécurité, IP sources les plus actives, règles déclenchées,
chronologie des actions du moteur.

## Alertmanager — routage des alertes

Toutes les alertes partent vers le moteur de remédiation :

- `group_by: [alertname, target]`, `group_wait: 5s`, `group_interval: 30s`, `repeat_interval: 5m` ;
- webhook `http://remediation-engine:8003/webhook/alert`, authentifié par un jeton porteur lu dans un fichier de secret.

## Requêtes utiles pour un opérateur

| Question | Requête |
|---|---|
| Un paiement passe-t-il ? | `probe_transaction_success` |
| Le pool est-il saturé ? | `max(payment_db_pool_in_use / payment_db_pool_size)` |
| Taux d'erreurs 5xx | `sum(rate(http_requests_total{status=~"5.."}[1m])) / sum(rate(http_requests_total[1m]))` |
| Score d'anomalie | `anomaly_score{target="payment-service"}` |
| Quelles IP inondent le WAF ? | `topk(5, sum by (client_ip) (count_over_time({service="waf"} \| json [1m])))` |
| Qu'a fait le moteur ? | `{service="remediation-engine"} \| json \| event="action"` |
| Erreurs de pool | `{service="payment-service"} \|= "db_pool_timeout"` |
