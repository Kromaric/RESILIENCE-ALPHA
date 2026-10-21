# detector-ml — détection d'anomalies par machine learning *(cible)*

Port interne **8004**. Le modèle est entraîné dans `ml/`, le service le charge et publie un score.

## detector-ml — approche

Détection d'anomalies **non supervisée**, un modèle par service cible (d'abord payment-service).
Pipeline scikit-learn `StandardScaler` + `IsolationForest`, entraîné sur du **trafic normal uniquement**
(généré par Locust : nominal, pic légitime, heures creuses). Le modèle apprend ce qui est ordinaire ; tout
ce qui s'en écarte obtient un score élevé. Ce ne sont pas des seuils codés en dur.

## detector-ml — variables d'entrée (payment-service)

Calculées toutes les **5 s** sur une fenêtre glissante de **30 s** :

| Variable | Source |
|---|---|
| Débit de requêtes | Prometheus `http_requests_total` |
| Latence p95 | Prometheus `http_request_duration_seconds_bucket` |
| Taux de réponses 5xx | Prometheus |
| Saturation du pool | `payment_db_pool_in_use / payment_db_pool_size` |
| Connexions MariaDB | `mysql_global_status_threads_connected` |
| CPU et mémoire du conteneur | cAdvisor |
| Nombre d'IP sources distinctes | Loki, journaux du WAF |
| Concentration du trafic | Part de la première IP source dans le volume total |
| Part non authentifiée | Ratio de réponses `401` |

## detector-ml — score d'anomalie

- `anomaly_score{target="payment-service"}` : valeur entre **0 et 1** (`decision_function` normalisée sur les bornes du jeu d'entraînement). Plus il est haut, plus la situation est inhabituelle.
- `anomaly_detected{target}` : 1 si le score dépasse le seuil.
- Seuil indicatif **0,7**, à fixer définitivement par `ml/evaluate.py`.
- `GET /score` renvoie aussi `top_deviations` : les variables les plus éloignées de la normale (z-scores). C'est l'explication du score, affichée dans le dashboard, et elle sert à qualifier le type d'incident.

## detector-ml — comment lire `top_deviations`

| Variables en tête | Interprétation probable |
|---|---|
| Saturation du pool, latence p95, 5xx, concentration sur peu d'IP | Épuisement de ressources (SC-01) |
| Part non authentifiée (`401`), échecs de connexion | Attaque sur l'authentification (SC-02) |
| Débit élevé mais pool, latence et 5xx normaux, nombreuses IP | Pic légitime : ne doit pas dépasser le seuil |

## detector-ml — validation du modèle

`ml/evaluate.py` rejoue des épisodes étiquetés (nominal, pic légitime, SC-01) et mesure précision, rappel,
taux de faux positifs et **délai de détection**. Le test décisif : un **pic légitime doit rester sous le
seuil**. C'est la preuve que le modèle ne confond pas charge et attaque.

## detector-ml — si le détecteur tombe

Si detector-ml s'arrête, `anomaly_score` n'est plus publié et `PaymentAnomaly` ne peut plus se déclencher.
Le filet de sécurité est l'alerte simple sur `probe_transaction_success` (voir `alertes/catalogue-alertes.md`),
documentée comme complémentaire au modèle. La perte du détecteur fait partie des tests de chaos.
