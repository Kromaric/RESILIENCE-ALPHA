from fastapi import HTTPException


def api_error(
    status_code: int, code: str, message: str, headers: dict[str, str] | None = None
) -> HTTPException:
    """Erreur au format commun : {"detail": {"code", "message"}} — le front s'appuie sur code."""
    return HTTPException(status_code, detail={"code": code, "message": message}, headers=headers)
