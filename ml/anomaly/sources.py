"""Lecture des variables dans Prometheus et Loki (requêtes instantanées ou sur une période)."""

from __future__ import annotations

import asyncio
from collections import defaultdict

import httpx

from anomaly.features import (
    LOKI_FEATURES,
    STEP_SECONDS,
    clean,
    loki_features_from_series,
    loki_query,
    prometheus_features,
)


class SourceError(RuntimeError):
    """Prometheus ou Loki injoignable / requête refusée."""


class Sources:
    def __init__(
        self,
        prometheus_url: str,
        loki_url: str | None,
        timeout: float = 4.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.prometheus_url = prometheus_url.rstrip("/")
        self.loki_url = loki_url.rstrip("/") if loki_url else None
        self.http = client or httpx.AsyncClient(timeout=timeout)

    async def aclose(self) -> None:
        await self.http.aclose()

    @property
    def use_loki(self) -> bool:
        return self.loki_url is not None

    async def _get(self, url: str, params: dict) -> dict:
        try:
            response = await self.http.get(url, params=params)
        except httpx.HTTPError as exc:
            raise SourceError(f"{url} : {exc}") from exc
        if response.status_code != 200:
            raise SourceError(f"{url} : HTTP {response.status_code} {response.text[:200]}")
        body = response.json()
        if body.get("status") != "success":
            raise SourceError(f"{url} : {body}")
        return body["data"]

    # --- Instant (inférence) -----------------------------------------------------------------
    async def _prom_instant(self, query: str, at: float) -> float | None:
        data = await self._get(
            f"{self.prometheus_url}/api/v1/query", {"query": query, "time": at}
        )
        result = data["result"]
        if data["resultType"] == "scalar":
            return float(result[1])
        return float(result[0]["value"][1]) if result else None

    async def _loki_instant(self, at: float) -> dict[str, float]:
        data = await self._get(
            f"{self.loki_url}/loki/api/v1/query",
            {"query": loki_query(), "time": int(at * 1e9)},
        )
        return loki_features_from_series(
            (item["metric"], float(item["value"][1])) for item in data["result"]
        )

    async def snapshot(self, at: float) -> dict[str, float]:
        """Vecteur de variables à l'instant `at` (secondes Unix)."""
        feats = prometheus_features()
        tasks = [self._prom_instant(f.query, at) for f in feats]
        if self.use_loki:
            tasks.append(self._loki_instant(at))
        results = await asyncio.gather(*tasks)
        row = {f.name: clean(v) for f, v in zip(feats, results, strict=False)}
        if self.use_loki:
            row |= results[-1]
        return row

    # --- Période (collecte) --------------------------------------------------------------------
    async def _prom_range(self, query: str, start: int, end: int) -> dict[int, float]:
        data = await self._get(
            f"{self.prometheus_url}/api/v1/query_range",
            {"query": query, "start": start, "end": end, "step": STEP_SECONDS},
        )
        values: dict[int, float] = {}
        for series in data["result"]:  # une seule série attendue (agrégats)
            for ts, v in series["values"]:
                values[round(float(ts))] = float(v)
        return values

    async def _loki_range(self, start: int, end: int) -> dict[int, dict[str, float]]:
        data = await self._get(
            f"{self.loki_url}/loki/api/v1/query_range",
            {
                "query": loki_query(),
                "start": start * 10**9,
                "end": end * 10**9,
                "step": f"{STEP_SECONDS}s",
            },
        )
        per_ts: dict[int, list] = defaultdict(list)
        for series in data["result"]:
            for ts, v in series["values"]:
                per_ts[round(float(ts))].append((series["metric"], float(v)))
        return {ts: loki_features_from_series(items) for ts, items in per_ts.items()}

    async def history(self, start: int, end: int) -> list[dict[str, float]]:
        """Une ligne toutes les STEP_SECONDS entre start et end (bornes alignées sur le pas)."""
        start -= start % STEP_SECONDS
        end -= end % STEP_SECONDS
        feats = prometheus_features()
        rows = {ts: {"ts": ts} for ts in range(start, end + 1, STEP_SECONDS)}
        prom = await asyncio.gather(*(self._prom_range(f.query, start, end) for f in feats))
        for f, values in zip(feats, prom, strict=True):
            for ts, row in rows.items():
                row[f.name] = clean(values.get(ts))
        if self.use_loki:
            loki = await self._loki_range(start, end)
            empty = dict.fromkeys(LOKI_FEATURES, 0.0)  # pas de journal = pas de trafic
            for ts, row in rows.items():
                row |= loki.get(ts, empty)
        return list(rows.values())
