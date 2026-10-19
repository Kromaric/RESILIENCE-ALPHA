# detector-ml

Service de détection d'anomalies — port interne **8004**.
Charge le modèle entraîné dans `ml/`, interroge Prometheus et Loki, publie `anomaly_score`.
Voir CADRAGE §4.5 et §6.5.
