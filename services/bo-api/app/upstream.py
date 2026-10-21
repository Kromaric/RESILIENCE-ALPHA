"""Clients des services interrogés par bo-api : Prometheus, Loki et le plan de contrôle.

Une panne d'un service interrogé ne doit pas rendre tout le dashboard indisponible : les
routes de supervision attrapent `UpstreamDown` et affichent la donnée comme « indisponible ».
"""

import logging
import math
from datetime import datetime
from typing import Any

import httpx

from app.logging_setup import log_event
from app.metrics import UPSTREAM_ERRORS

logger = logging.getLogger("upstream")


class UpstreamDown(Exception):
    """Service injoignable (status None) ou réponse en erreur (status HTTP)."""

    def __init__(self, name: str, status: int | None = None) -> None:
        super().__init__(name)
        self.name = name
        self.status = status


async def _get(http: httpx.AsyncClient, name: str, url: str, **kwargs) -> httpx.Response:
    try:
        response = await http.get(url, **kwargs)
    except httpx.HTTPError:
        UPSTREAM_ERRORS.labels(upstream=name).inc()
        log_event(logger, "upstream_unreachable", level=logging.WARNING, upstream=name)
        raise UpstreamDown(name) from None
    if response.status_code >= 400:
        UPSTREAM_ERRORS.labels(upstream=name).inc()
        log_event(
            logger,
            "upstream_error",
            level=logging.WARNING,
            upstream=name,
            status=response.status_code,
        )
        raise UpstreamDown(name, response.status_code)
    return response


class Prometheus:
    def __init__(self, http: httpx.AsyncClient, url: str) -> None:
        self._http = http
        self._url = url

    async def vector(self, expr: str) -> list[tuple[dict[str, str], float]]:
        """Requête instantanée : (labels, valeur) par série."""
        response = await _get(
            self._http, "prometheus", f"{self._url}/api/v1/query", params={"query": expr}
        )
        return [
            (item["metric"], float(item["value"][1])) for item in response.json()["data"]["result"]
        ]

    async def scalar(self, expr: str) -> float | None:
        """Première valeur d'une requête instantanée ; None s'il n'y a pas de série (ou NaN)."""
        result = await self.vector(expr)
        if not result:
            return None
        value = result[0][1]
        return value if math.isfinite(value) else None  # NaN : pas de données sur la fenêtre

    async def range(self, expr: str, start: datetime, end: datetime, step: int) -> dict[int, float]:
        """Série temporelle (première série) : horodatage Unix → valeur."""
        response = await _get(
            self._http,
            "prometheus",
            f"{self._url}/api/v1/query_range",
            params={
                "query": expr,
                "start": start.timestamp(),
                "end": end.timestamp(),
                "step": step,
            },
        )
        result = response.json()["data"]["result"]
        if not result:
            return {}
        points = {int(float(ts)): float(value) for ts, value in result[0]["values"]}
        return {ts: value for ts, value in points.items() if math.isfinite(value)}


class Loki:
    def __init__(self, http: httpx.AsyncClient, url: str) -> None:
        self._http = http
        self._url = url

    async def lines(
        self, query: str, start: datetime, end: datetime, limit: int
    ) -> list[tuple[int, dict[str, str], str]]:
        """Lignes de journal, plus récentes d'abord : (horodatage ns, labels, ligne)."""
        response = await _get(
            self._http,
            "loki",
            f"{self._url}/loki/api/v1/query_range",
            params={
                "query": query,
                "start": int(start.timestamp() * 1e9),
                "end": int(end.timestamp() * 1e9),
                "limit": limit,
                "direction": "backward",
            },
        )
        lines = [
            (int(ts), stream["stream"], line)
            for stream in response.json()["data"]["result"]
            for ts, line in stream["values"]
        ]
        return sorted(lines, key=lambda item: item[0], reverse=True)[:limit]


class ControlPlane:
    """Moteur de remédiation, détecteur et assistant : services du plan de contrôle."""

    def __init__(self, http: httpx.AsyncClient, settings) -> None:
        self._http = http
        self._settings = settings

    async def remediation(self, path: str, **params) -> Any:
        response = await _get(
            self._http, "remediation", f"{self._settings.remediation_url}{path}", params=params
        )
        return response.json()

    async def detector_score(self) -> dict[str, Any]:
        response = await _get(self._http, "detector", f"{self._settings.detector_url}/score")
        return response.json()

    async def ask(self, question: str) -> dict[str, Any]:
        try:
            response = await self._http.post(
                f"{self._settings.assistant_url}/ask",
                json={"question": question},
                timeout=self._settings.assistant_timeout_seconds,
            )
        except httpx.HTTPError:
            UPSTREAM_ERRORS.labels(upstream="assistant").inc()
            raise UpstreamDown("assistant") from None
        if response.status_code >= 400:
            UPSTREAM_ERRORS.labels(upstream="assistant").inc()
            raise UpstreamDown("assistant")
        return response.json()
