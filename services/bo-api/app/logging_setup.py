"""Journaux JSON sur stdout, collectés par Alloy puis envoyés dans Loki (CADRAGE §6.2)."""

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

_service_name = "bo-api"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname.lower(),
            "service": _service_name,
            "msg": record.getMessage(),
        }
        request_id = request_id_var.get()
        if request_id:
            data["request_id"] = request_id
        data.update(getattr(record, "fields", {}))
        if record.exc_info:
            data["exc"] = self.formatException(record.exc_info)
        return json.dumps(data, ensure_ascii=False, default=str)


def configure_logging(service_name: str, level: str) -> None:
    global _service_name
    _service_name = service_name
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())
    # Uvicorn passe par le même format ; son journal d'accès est remplacé par le nôtre
    for name in ("uvicorn", "uvicorn.error"):
        logging.getLogger(name).handlers = []
        logging.getLogger(name).propagate = True
    logging.getLogger("uvicorn.access").disabled = True


def log_event(logger: logging.Logger, msg: str, level: int = logging.INFO, **fields) -> None:
    """Journalise un événement avec des champs structurés.

    Ne jamais y passer de mot de passe, de jeton ni de clé d'API.
    """
    logger.log(level, msg, extra={"fields": fields})
