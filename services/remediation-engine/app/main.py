from __future__ import annotations

import logging

from fastapi import BackgroundTasks, FastAPI, HTTPException, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.config import Settings
from app.models import AlertmanagerPayload, Incident, PlatformStatus, PublicStatus
from app.remediator import RemediationEngine

logger = logging.getLogger("remediation-engine")


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = Settings()
    logging.basicConfig(level=settings.log_level, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    app = FastAPI(
        title="Orbe Remediation Engine",
        description="Moteur d'auto-remédiation autonome pour l'architecture résiliente d'Orbe",
        version="0.1.0",
    )

    engine = RemediationEngine(settings)
    app.state.engine = engine

    @app.get("/health/live", tags=["Health"])
    @app.get("/health/ready", tags=["Health"])
    @app.get("/health", tags=["Health"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "remediation-engine"}

    @app.get("/metrics", tags=["Interne"])
    async def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @app.post("/webhook/alert", status_code=status.HTTP_202_ACCEPTED, tags=["Alertmanager"])
    async def webhook_alert(payload: AlertmanagerPayload, background_tasks: BackgroundTasks) -> dict[str, str]:
        """Reçoit les alertes d'Alertmanager (ex: PaymentAnomaly) et déclenche l'action autonome."""
        logger.info("Alerte Alertmanager reçue : status=%s, nb_alertes=%d", payload.status, len(payload.alerts))
        if payload.status == "firing":
            for alert in payload.alerts:
                target = alert.labels.get("target", "payment-service")
                incident_type = alert.labels.get("incident_type", "resource_exhaustion")
                logger.warning("Déclenchement remédiation pour alerte '%s' sur cible '%s'", alert.labels.get("alertname"), target)
                background_tasks.add_task(engine.trigger_remediation, incident_type, target)
        return {"status": "accepted"}

    @app.post("/trigger", status_code=status.HTTP_202_ACCEPTED, tags=["Manuel / Test"])
    async def manual_trigger(background_tasks: BackgroundTasks, target: str = "payment-service", forced_ip: str | None = None, incident_type: str = "resource_exhaustion") -> dict[str, str]:
        """Déclencheur direct pour démonstration ou simulation manuelle."""
        logger.info("Déclencheur manuel activé pour cible=%s, forced_ip=%s", target, forced_ip)
        background_tasks.add_task(engine.trigger_remediation, incident_type, target, forced_ip)
        return {"status": "remediation_started", "target": target}

    @app.post("/reset", tags=["Manuel / Test"])
    async def reset() -> dict[str, str]:
        """Débloque toutes les adresses IP et réinitialise l'environnement pour un nouveau test."""
        logger.info("Réinitialisation de la blocklist demandée...")
        success = await engine.reset_blocklist()
        return {"status": "unblocked" if success else "failed"}

    @app.get("/status", response_model=PlatformStatus, tags=["Supervision"])
    async def get_status() -> PlatformStatus:
        """État agrégé complet interrogé par bo-api et le dashboard."""
        return engine.get_status()

    @app.get("/status/public", response_model=PublicStatus, tags=["Frontend"])
    async def get_public_status() -> PublicStatus:
        """État public exposé via le WAF sous /api/status pour l'interface client."""
        return engine.get_public_status()

    @app.get("/incidents", response_model=list[Incident], tags=["Incidents"])
    async def list_incidents(limit: int = 10) -> list[Incident]:
        """Historique des incidents récents."""
        return engine.get_incidents(limit=limit)

    @app.get("/incidents/{incident_id}", response_model=Incident, tags=["Incidents"])
    async def get_incident(incident_id: str) -> Incident:
        """Détail d'un incident spécifique."""
        inc = engine.get_incident(incident_id)
        if not inc:
            raise HTTPException(status_code=404, detail="Incident non trouvé")
        return inc

    return app
