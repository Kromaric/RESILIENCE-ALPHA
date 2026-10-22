# ML — détection d'anomalies (IsolationForest)

Modèle non supervisé **par service cible** (CADRAGE §6.5), entraîné sur du trafic **normal
uniquement**, servi par `services/detector-ml`.

```
ml/
├── anomaly/            # code partagé avec detector-ml (copié dans son image)
│   ├── features.py     #   variables : requêtes PromQL / LogQL — source unique
│   ├── sources.py      #   lecture Prometheus + Loki (instant ou période)
│   └── model.py        #   StandardScaler + IsolationForest, score [0-1], z-scores
├── locustfile.py       # trafic légitime : profils nominal / peak / offpeak
├── collect.py          # Prometheus + Loki → CSV étiqueté (1 ligne / 5 s)
├── train.py            # → models/model-payment.joblib (+ .json lisible)
├── evaluate.py         # épisodes non vus → seuil, faux positifs, délai → reports/
└── tests/              # chaîne complète sur données synthétiques (test du code)
```

## Variables (payment-service, fenêtre 30 s)

| Variable | Source | Pourquoi |
|---|---|---|
| `req_rate` | Prometheus (instrumentator) | volume |
| `latency_p95` | Prometheus | dégradation ressentie |
| `error_5xx_ratio` | Prometheus | `503` quand le pool est épuisé |
| `client_4xx_ratio` | Prometheus | requêtes refusées (401/403/422/429 — statuts groupés) |
| `pool_saturation` | Prometheus (`payment_db_pool_*`) | ressource visée par SC-01 |
| `pool_timeouts_rate` | Prometheus | symptôme direct de l'épuisement |
| `container_cpu`, `container_mem_mib` | cAdvisor | supervision des conteneurs |
| `host_cpu` | node-exporter | supervision de la machine |
| `ip_distinct`, `ip_top_share` | Loki (`client_ip` du journal JSON) | concentration du trafic sur peu d'IP |
| `unauth_ratio` | Loki (`status` 401/403) | trafic non authentifié |

Une variable constante sur tout le jeu d'entraînement (source absente, ex. cAdvisor partiel
sous WSL2) est écartée automatiquement et listée dans `model-payment.json`.

## Procédure

Prérequis : `pip install -r ml/requirements.txt`, pile `infra/` démarrée, Prometheus
(`:9090`) et Loki (`:3100`) joignables depuis le poste. Pour Locust, auth-service avec
`AUTH_FACE_ENGINE=fake` (connexion simulée, comme `scripts/dev_token.py`).

```powershell
# 1. Trafic normal — plusieurs épisodes par profil ; en garder au moins un de chaque À PART
$env:PROFILE="nominal"; $env:DURATION_S="1800"; locust -f ml/locustfile.py --headless
python ml/collect.py --label nominal --since 30m
$env:PROFILE="peak";    locust -f ml/locustfile.py --headless
python ml/collect.py --label peak --since 30m

# 2. Attaques SC-01 (depuis le PC Attaquant), Locust nominal en fond — 3 épisodes ou plus.
#    --start = instant de lancement de l'attaque (le délai de détection est mesuré de là)
python ml/collect.py --label sc01 --start 2026-10-22T10:02:00 --end 2026-10-22T10:05:00

# 3. Répartir : ml/data/raw/ (entraînement) / ml/data/eval/ (épisodes jamais vus)
python ml/train.py "ml/data/raw/nominal-*.csv" "ml/data/raw/peak-*.csv"
python ml/evaluate.py "ml/data/eval/*.csv" --write
```

`evaluate.py --write` enregistre le seuil dans le modèle ; detector-ml le publie
(`anomaly_threshold`) et la règle Prometheus compare le score à cette métrique : pas de seuil
recopié à la main.

## Avant le déploiement : données fictives

Tant que payment-service ne reçoit pas de trafic, `ml/synth.py` simule des épisodes
cohérents avec la configuration du service (pool de 10, autorisation 50-150 ms, `pool_timeout`
2 s, CPU hôte mesuré sur le PC Hôte) : 6 épisodes normaux d'entraînement, 3 épisodes normaux
et 5 attaques SC-01 d'intensités variées pour l'évaluation.

```powershell
python ml/synth.py
python ml/train.py "ml/data/synth/raw/*.csv"
python ml/evaluate.py "ml/data/synth/eval/*.csv" --write
```

Sert à faire tourner detector-ml, l'alerte et la remédiation dès maintenant. Le modèle est
marqué `synthetic: true` (journal `model_trained_on_synthetic_data` au démarrage du
détecteur, bandeau dans le rapport) : **à réentraîner sur les données collectées** dès que
le service est déployé — les valeurs réelles (mémoire, latence, CPU hôte) ne seront pas celles
de la simulation et provoqueraient des fausses alertes.

## Score

`score = 0.5 × (médiane − decision_function) / (médiane − minimum)`, statistiques du jeu
d'entraînement : 0.5 = aussi atypique que le point le plus extrême vu en trafic normal.
Le seuil retenu = plus petit seuil sans fausse alerte (score soutenu 10 s) sur les épisodes
normaux d'évaluation + marge 0.05, borné à [0.5, 0.95].

## Limites connues (à reprendre dans le dossier technique)

- **IP sources** : `client_ip` vient de `X-Real-IP`, posé par le WAF. Si le WAF ne le
  transmet pas, toutes les requêtes ont la même IP et `ip_*` ne porte aucune information.
  Locust envoie un `X-Real-IP` par utilisateur virtuel (`SPOOF_IPS=1`), mais uniquement en
  direct sur le service : à travers le WAF, le trafic d'entraînement vient d'une seule IP.
  Pendant la démo, le trafic normal (sonde + quelques appareils) aussi → risque de fausse
  alerte si l'entraînement voyait 30 IP. Entraîner dans les conditions de la démo, ou
  `--no-loki`.
- **node-exporter** sans `network_mode: host` : les compteurs réseau sont ceux de son propre
  conteneur ; seules les variables CPU/mémoire de l'hôte sont utilisées.
- **Dérive** : un modèle entraîné sur une machine ne vaut pas pour une autre (CPU, latence de
  base) → recollecter sur le PC Hôte de la démo.
- **Une variable constante en trafic normal est invisible pour l'IsolationForest** (aucune
  coupure possible) : `error_5xx_ratio` et `pool_timeouts_rate` valent 0 en temps normal et
  sont donc écartées. L'attaque reste vue par la latence, la saturation du pool, le débit et
  les IP ; la règle complémentaire sur `probe_transaction_success` (CADRAGE §6.5) couvre ce cas.
- Le modèle détecte un écart au normal, il ne nomme pas l'attaque : `top_deviations` sert à
  qualifier l'incident, la décision reste au moteur de remédiation.
