from fastapi import APIRouter

router = APIRouter(prefix="/health", include_in_schema=False)


@router.get("/live")
async def live() -> dict[str, str]:
    """Le processus répond."""
    return {"status": "ok"}


@router.get("/ready")
async def ready() -> dict[str, str]:
    """bo-api n'a pas de dépendance bloquante : un service interrogé indisponible est signalé
    dans la réponse concernée, pas en rendant tout le back-office indisponible."""
    return {"status": "ok"}
