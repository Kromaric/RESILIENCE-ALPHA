"""detector-ml — publie toutes les 5 s le score d'anomalie de payment-service (CADRAGE §4.5).

Boucle : variables (Prometheus + Loki, mêmes requêtes qu'à l'entraînement) → modèle →
`anomaly_score{target}` / `anomaly_threshold{target}` scrapés par Prometheus. La règle
`PaymentAnomaly` (infra/prometheus-rules/anomaly.yml) compare les deux pendant 10 s puis
Alertmanager prévient le moteur de remédiation. Le détecteur ne décide d'aucune action.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from pydantic_settings import BaseSettings, SettingsConfigDict

from anomaly.model import AnomalyModel
from anomaly.sources import SourceError, Sources
from app.logging_setup import configure_logging, log_event

logger = logging.getLogger("detector")

SCORE = Gauge("anomaly_score", "Score d'anomalie normalisé [0-1]", ["target"])
THRESHOLD = Gauge("anomaly_threshold", "Seuil d'alerte calibré (ml/evaluate.py)", ["target"])
DETECTED = Gauge("anomaly_detected", "1 si score > seuil à la dernière évaluation", ["target"])
FEATURE = Gauge("anomaly_feature_value", "Valeur courante des variables", ["target", "feature"])
ZSCORE = Gauge("anomaly_feature_zscore", "Écart à la normale (z-score)", ["target", "feature"])
INFERENCE = Histogram(
    "detector_inference_seconds", "Collecte + inférence",
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 4),
)
ERRORS = Counter("detector_errors_total", "Évaluations impossibles", ["reason"])
LAST_SUCCESS = Gauge("detector_last_success_timestamp_seconds", "Dernière évaluation réussie")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DETECTOR_")

    target: str = "payment-service"
    model_path: Path = Path("/models/model-payment.joblib")
    prometheus_url: str = "http://prometheus:9090"
    loki_url: str | None = "http://loki:3100"  # vide → variables Prometheus seules
    interval_seconds: float = 5.0
    threshold: float | None = None  # surcharge ponctuelle du seuil du modèle
    log_level: str = "INFO"


class Detector:
    def __init__(self, settings: Settings, model: AnomalyModel, sources: Sources) -> None:
        self.settings = settings
        self.model = model
        self.sources = sources
        self.threshold = settings.threshold or model.threshold
        self.last: dict | None = None
        THRESHOLD.labels(settings.target).set(self.threshold)

    async def evaluate(self, now: float | None = None) -> dict:
        target = self.settings.target
        now = now or time.time()
        start = time.perf_counter()
        row = await self.sources.snapshot(now)
        score = float(self.model.score(self.model.vector(row))[0])
        INFERENCE.observe(time.perf_counter() - start)

        anomaly = score > self.threshold
        z = self.model.zscores(self.model.vector(row))[0]
        for name, value in zip(self.model.features, z, strict=True):
            FEATURE.labels(target, name).set(row.get(name, 0.0))
            ZSCORE.labels(target, name).set(float(value))
        SCORE.labels(target).set(score)
        DETECTED.labels(target).set(int(anomaly))
        LAST_SUCCESS.set(now)

        result = {
            "target": target,
            "score": round(score, 4),
            "threshold": self.threshold,
            "anomaly": anomaly,
            "features": {k: round(v, 4) for k, v in row.items() if k in self.model.features},
            "top_deviations": self.model.top_deviations(row),
            "evaluated_at": datetime.fromtimestamp(now, UTC).isoformat(timespec="seconds"),
        }
        was_anomaly = bool(self.last and self.last["anomaly"])
        if anomaly != was_anomaly:  # journalisé sur front seulement (pas 1 ligne / 5 s)
            log_event(
                logger,
                "anomaly_detected" if anomaly else "anomaly_cleared",
                level=logging.WARNING if anomaly else logging.INFO,
                target=target, score=result["score"], threshold=self.threshold,
                top_deviations=result["top_deviations"],
            )
        self.last = result
        return result

    def mark_unknown(self, reason: str) -> None:
        # Pas de données → pas de score : NaN plutôt qu'un 0 rassurant ou une fausse alerte
        ERRORS.labels(reason).inc()
        SCORE.labels(self.settings.target).set(float("nan"))
        DETECTED.labels(self.settings.target).set(0)

    async def run_forever(self) -> None:
        while True:
            started = time.monotonic()
            try:
                await self.evaluate()
            except SourceError as exc:
                self.mark_unknown("source")
                log_event(logger, "source_unavailable", level=logging.WARNING, error=str(exc))
            except Exception:  # la boucle ne doit jamais mourir
                self.mark_unknown("internal")
                logger.exception("evaluation_failed")
            elapsed = time.monotonic() - started
            await asyncio.sleep(max(0.0, self.settings.interval_seconds - elapsed))


def create_app(settings: Settings | None = None, detector: Detector | None = None) -> FastAPI:
    settings = settings or Settings()
    configure_logging("detector-ml", settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        nonlocal detector
        if detector is None:
            model = AnomalyModel.load(settings.model_path)
            sources = Sources(settings.prometheus_url, settings.loki_url or None)
            detector = Detector(settings, model, sources)
        app.state.detector = detector
        log_event(
            logger, "service_started", target=settings.target, threshold=detector.threshold,
            features=detector.model.features, trained_at=detector.model.meta.get("trained_at"),
            synthetic=detector.model.meta.get("synthetic", False),
        )
        if detector.model.meta.get("synthetic"):
            log_event(logger, "model_trained_on_synthetic_data", level=logging.WARNING)
        task = asyncio.create_task(detector.run_forever())
        yield
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        await detector.sources.aclose()

    app = FastAPI(title="detector-ml", version="0.1.0", lifespan=lifespan, docs_url=None,
                  redoc_url=None, openapi_url=None)

    @app.get("/score")
    async def score() -> JSONResponse:
        last = app.state.detector.last
        if last is None:
            return JSONResponse({"detail": "aucune évaluation pour l'instant"}, status_code=503)
        return JSONResponse(last)

    @app.get("/health/live")
    async def live() -> dict:
        return {"status": "ok"}

    @app.get("/health/ready")
    async def ready() -> JSONResponse:
        last = app.state.detector.last
        fresh = last is not None and (
            time.time() - datetime.fromisoformat(last["evaluated_at"]).timestamp()
            < 3 * settings.interval_seconds + 5
        )
        return JSONResponse({"ready": fresh}, status_code=200 if fresh else 503)

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app
