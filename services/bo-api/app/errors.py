from fastapi import HTTPException, status
from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str = Field(examples=["invalid_token"])
    message: str = Field(examples=["Session invalide ou expirée."])


class ErrorOut(BaseModel):
    detail: ErrorDetail


def error(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def unauthorized() -> HTTPException:
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        detail=error("invalid_token", "Session invalide ou expirée."),
        headers={"WWW-Authenticate": "Bearer"},
    )


def upstream_unavailable(name: str) -> HTTPException:
    return HTTPException(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=error(f"{name}_unavailable", f"Service {name} momentanément indisponible."),
        headers={"Retry-After": "5"},
    )
