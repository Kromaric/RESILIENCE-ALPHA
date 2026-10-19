import asyncio

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

router = APIRouter(prefix="/health", include_in_schema=False)


@router.get("/live")
async def live() -> dict[str, str]:
    """Le processus répond."""
    return {"status": "ok"}


@router.get("/ready")
async def ready(request: Request) -> JSONResponse:
    """Un paiement peut être traité : pool non saturé et base qui répond en moins de 2 s.

    C'est ce contrôle que la remédiation attend avant de vérifier la reprise (CADRAGE §7.4).
    """
    pool = request.app.state.engine.pool
    if hasattr(pool, "checkedout") and pool.checkedout() >= pool.size():
        return JSONResponse(
            status_code=503,
            content={
                "status": "unavailable",
                "checks": {"database": "unknown", "pool": "saturated"},
            },
        )

    async def check_database() -> None:
        async with request.app.state.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    try:
        await asyncio.wait_for(check_database(), timeout=2)
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "checks": {"database": "down", "pool": "ok"}},
        )
    return JSONResponse({"status": "ok", "checks": {"database": "up", "pool": "ok"}})
