# detector-ml

Service de détection d'anomalies — port interne **8004**. Voir CADRAGE §4.5 / §6.5 et
`ml/README.md` pour l'entraînement.

Toutes les 5 s : variables (Prometheus + Loki, requêtes de `ml/anomaly/features.py`) →
IsolationForest → métriques. Il ne déclenche aucune action : Prometheus évalue
`PaymentAnomaly` (`infra/prometheus-rules/anomaly.yml`), Alertmanager prévient le moteur.

| Endpoint | Contenu |
|---|---|
| `GET /score` | `{target, score, threshold, anomaly, features, top_deviations, evaluated_at}` |
| `GET /metrics` | `anomaly_score{target}`, `anomaly_threshold{target}`, `anomaly_detected{target}`, `anomaly_feature_value{target,feature}`, `anomaly_feature_zscore{target,feature}`, `detector_inference_seconds`, `detector_errors_total{reason}`, `detector_last_success_timestamp_seconds` |
| `GET /health/live` · `/health/ready` | prêt = une évaluation réussie depuis moins de ~20 s |

Si Prometheus ou Loki ne répond pas, `anomaly_score` vaut NaN (ni faux « tout va bien », ni
fausse alerte) et `DetectorDown` se déclenche. Les changements d'état sont journalisés
(`anomaly_detected` / `anomaly_cleared`, avec `top_deviations`) → visibles dans Loki.

## Configuration (variables d'environnement)

| Variable | Défaut |
|---|---|
| `DETECTOR_MODEL_PATH` | `/models/model-payment.joblib` (monté depuis `ml/models/`) |
| `DETECTOR_PROMETHEUS_URL` | `http://prometheus:9090` |
| `DETECTOR_LOKI_URL` | `http://loki:3100` (vide = sans Loki ; doit correspondre au modèle) |
| `DETECTOR_INTERVAL_SECONDS` | `5` |
| `DETECTOR_THRESHOLD` | seuil du modèle (surcharge ponctuelle) |

## Tests

```powershell
cd services/detector-ml
pip install -e ".[dev]"
python -m pytest
```
