"""Incidents (moteur de remédiation), assistant opérateur (RAG) et liens Grafana.

Le moteur de remédiation est la seule source des incidents : bo-api relaie ses routes en
lecture (`GET /incidents`, `GET /incidents/{id}`, CADRAGE §4.6) sans les transformer, et
n'a accès à aucune de ses routes d'écriture.
"""

import logging
from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status

from app.errors import ErrorOut, error, upstream_unavailable
from app.logging_setup import log_event
from app.schemas import AskRequest, AskResponse, GrafanaLink, GrafanaOut, GrafanaPanel
from app.security import Operator, require_role
from app.upstream import UpstreamDown

router = APIRouter(tags=["Incidents, assistant et Grafana"])
logger = logging.getLogger("control")

UNAVAILABLE = {
    401: {"model": ErrorOut, "description": "Jeton absent, invalide ou révoqué"},
    503: {"model": ErrorOut, "description": "Service interrogé indisponible"},
}

# Panneaux du tableau « Orbe — Supervision » (infra/grafana-provisioning/dashboards/
# orbe-supervision.json) : identifiants stables, à garder alignés avec ce fichier
GRAFANA_PANELS = [
    ("latency", 1, "Latence p95 de payment-service"),
    ("errors", 2, "Erreurs 5xx de payment-service"),
    ("transactions", 3, "Opérations par minute, par statut"),
    ("db_pool", 4, "Pool de connexions MariaDB"),
    ("logins", 5, "Connexions et échecs (auth-service)"),
    ("anomaly", 6, "Score d'anomalie (detector-ml)"),
    ("error_logs", 7, "Journaux d'erreur"),
]


@router.get(
    "/bo/incidents",
    summary="Incidents (moteur de remédiation)",
    responses=UNAVAILABLE,
)
async def incidents(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
    _: Operator = Depends(require_role("viewer")),
) -> Any:
    """Liste du moteur de remédiation, relayée telle quelle (format défini par le moteur)."""
    try:
        return await request.app.state.control_plane.remediation("/incidents", limit=limit)
    except UpstreamDown as exc:
        raise upstream_unavailable(exc.name) from None


@router.get(
    "/bo/incidents/{incident_id}",
    summary="Détail d'un incident : étapes, actions, vérification",
    responses={**UNAVAILABLE, 404: {"model": ErrorOut, "description": "Incident inconnu"}},
)
async def incident(
    request: Request,
    incident_id: str = Path(max_length=40, pattern=r"^[A-Za-z0-9_-]+$"),
    _: Operator = Depends(require_role("viewer")),
) -> Any:
    try:
        return await request.app.state.control_plane.remediation(f"/incidents/{incident_id}")
    except UpstreamDown as exc:
        if exc.status == 404:
            raise HTTPException(404, detail=error("not_found", "Incident inconnu.")) from None
        raise upstream_unavailable(exc.name) from None


@router.post(
    "/bo/assistant/ask",
    response_model=AskResponse,
    summary="Poser une question à l'assistant opérateur",
    responses={
        **UNAVAILABLE,
        403: {"model": ErrorOut, "description": "Réservé au rôle « viewer » ou supérieur"},
        429: {"model": ErrorOut, "description": "Trop de questions (en-tête Retry-After)"},
    },
)
async def ask(
    body: AskRequest,
    request: Request,
    operator: Operator = Depends(require_role("viewer")),
) -> AskResponse:
    """Relayée à assistant-rag (`POST /ask`), qui répond à partir de la documentation et
    cite ses sources. Peut prendre plusieurs secondes (modèle local)."""
    state = request.app.state
    if not state.ask_limiter.allow(operator.operator_id):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail=error("too_many_questions", "Trop de questions. Réessayez dans une minute."),
            headers={"Retry-After": "60"},
        )
    # La question n'est pas journalisée (elle peut contenir n'importe quoi) : seulement sa taille
    log_event(
        logger, "assistant_question", operator_id=operator.operator_id, length=len(body.question)
    )
    try:
        answer = await state.control_plane.ask(body.question)
    except UpstreamDown as exc:
        raise upstream_unavailable(exc.name) from None
    return AskResponse.model_validate(answer)


@router.get(
    "/bo/grafana",
    response_model=GrafanaOut,
    summary="Liens Grafana et panneaux à intégrer",
    responses={401: UNAVAILABLE[401]},
)
async def grafana(request: Request, _: Operator = Depends(require_role("viewer"))) -> GrafanaOut:
    """`panels[].embed_url` se place dans une `<iframe>` (Grafana autorise l'intégration et
    l'accès anonyme en lecture seule). `tools` remplace les liens codés en dur de la barre
    latérale."""
    settings = request.app.state.settings
    base = settings.grafana_public_url.rstrip("/")
    uid = settings.grafana_dashboard_uid

    def embed(panel_id: int) -> str:
        query = urlencode(
            {
                "orgId": 1,
                "panelId": panel_id,
                "theme": "dark",
                "refresh": "10s",
                "from": "now-30m",
                "to": "now",
            }
        )
        return f"{base}/d-solo/{uid}/orbe-supervision?{query}"

    return GrafanaOut(
        base_url=base,
        dashboards=[
            GrafanaLink(title="Orbe — Supervision", url=f"{base}/d/{uid}/orbe-supervision"),
            GrafanaLink(title="Journaux", url=f"{base}/dashboards?query=logs"),
        ],
        panels=[
            GrafanaPanel(key=key, title=title, embed_url=embed(pid))
            for key, pid, title in GRAFANA_PANELS
        ],
        tools=[
            GrafanaLink(title="Grafana", url=base),
            GrafanaLink(title="Prometheus", url=settings.prometheus_public_url),
            GrafanaLink(title="Loki — journaux", url=f"{base}/explore"),
        ],
    )
