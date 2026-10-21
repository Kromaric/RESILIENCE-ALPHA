# WAF — point d'entrée unique d'Orbe

> Cible du cadrage : Nginx + ModSecurity v3 + OWASP CRS 4. Le dépôt utilise actuellement SafeLine
> (voir `etat-implementation.md`). Les principes ci-dessous valent pour les deux.

## Rôle du WAF dans Orbe

Le WAF est le **seul** service publié sur le hotspot (`192.168.137.1:443`). Tout le trafic client, la sonde
et le PC Attaquant passent par lui. Il assure :

- la terminaison TLS pour `orbe.test` (certificat `mkcert`) ;
- le filtrage applicatif (règles OWASP CRS : injections, XSS, scanners…) ;
- le routage vers frontend, auth-service, payment-service et l'état public `/api/status` ;
- la **répartition** entre `payment-service-a` et `payment-service-b` ;
- une limitation de débit large par IP (`limit_req`) ;
- l'application de la **liste de blocage dynamique** écrite par le moteur de remédiation ;
- la génération du `X-Request-ID` propagé à tous les services (corrélation des journaux).

## WAF — sortie automatique d'une instance de paiement en échec

L'upstream `payment` est configuré avec `max_fails=2 fail_timeout=10s`. Après deux échecs, une instance
est écartée pendant 10 s et l'autre continue de servir. C'est ce qui permet au moteur de redémarrer une
instance dégradée sans couper complètement le paiement.

## WAF — liste de blocage dynamique (blocklist)

- Fichier `blocklist.conf` (directive `geo`) sur un volume partagé entre le WAF et `remediation-engine`.
- Le moteur y écrit les IP à bloquer avec un **TTL de 15 minutes**, puis envoie un signal `HUP` au WAF via le `socket-proxy` pour recharger la configuration sans coupure.
- L'IP de la sonde est en **liste blanche** : elle n'est jamais bloquée.
- Une IP bloquée reçoit un `403` du WAF ; ses requêtes n'atteignent plus payment-service.
- `reset.yml` vide la liste de blocage entre deux répétitions de la démo.

Le blocage ciblé est une **action de remédiation**, pas une règle statique : la limitation de débit de base
reste volontairement large pour ne pas gêner un pic de trafic légitime.

## WAF — comment savoir si une IP est bloquée

- Grafana, tableau de bord SOC, panneau « Actions de remédiation » : événement `action` avec l'IP bloquée.
- Journaux du WAF dans Loki : réponses `403` pour l'IP concernée.
- Incident dans le dashboard : l'étape « contenir » liste les IP bloquées.

## WAF — journaux

Journaux d'accès et d'audit au format **JSON** sur la sortie standard, collectés par Loki. Les règles CRS
déclenchées portent un identifiant de règle (`modsec_rule_id` avec ModSecurity), exploité par le SOC.
