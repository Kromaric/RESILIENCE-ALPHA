"""Supervision de la plateforme (`/bo/supervision`) : page « Supervision » du dashboard.

Sources : Prometheus (métriques des services, node-exporter, score d'anomalie publié par
detector-ml), Loki (journaux) et le moteur de remédiation (`GET /status`, état de
l'incident en cours, CADRAGE §4.6). Chaque source peut manquer : la donnée correspondante
est alors renvoyée « — » avec le ton `unknown`, sans faire échouer la réponse.

Formes calquées sur `dashboard/src/data/supervision.js`, `metrics.js` et `incident.js`.
"""

import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, Request

from app import fmt
from app.errors import ErrorOut, upstream_unavailable
from app.schemas import (
    Banner,
    IncidentWindow,
    Kpi,
    LogLine,
    LogsOut,
    Overview,
    Resource,
    ResourcesOut,
    SeriesMinute,
    ServiceCard,
    ServicesOut,
    StatusBadge,
    SupervisionSeries,
)
from app.security import Operator, require_role
from app.upstream import UpstreamDown

router = APIRouter(prefix="/bo/supervision", tags=["Supervision"])
logger = logging.getLogger("supervision")

RESPONSES = {401: {"model": ErrorOut, "description": "Jeton absent, invalide ou révoqué"}}

# États du moteur de remédiation (CADRAGE §4.6, `platform`)
PLATFORM = {
    "operational": ("Opérationnel", "ok"),
    "incident": ("Incident en cours", "danger"),
    "remediation": ("Remédiation en cours", "danger"),
    "recovered": ("Rétabli", "ok"),
}


def now_utc() -> datetime:
    return datetime.now(UTC)


def iso(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class Queries:
    """Requêtes PromQL, construites à partir des noms de jobs configurés."""

    def __init__(self, settings) -> None:
        pay, auth = settings.payment_job, settings.auth_job
        self.availability = f'avg_over_time(up{{job="{pay}"}}[24h]) * 100'
        self.latency_p95_ms = self.p95(pay)
        self.auth_latency_p95_ms = self.p95(auth)
        self.error_rate = (
            # « or vector(0) » : sans aucune 5xx, la série n'existe pas ; le taux vaut alors 0
            f'(sum(rate(http_requests_total{{job="{pay}",status="5xx"}}[5m])) or vector(0))'
            f' / sum(rate(http_requests_total{{job="{pay}"}}[5m]))'
        )
        self.tx_per_min = "sum(rate(payment_transactions_total[5m])) * 60"
        self.tx_per_min_1m = "sum(rate(payment_transactions_total[1m])) * 60"
        self.anomaly = f'max(anomaly_score{{target="{settings.anomaly_target}"}})'
        self.up_pay = f'sum(up{{job="{pay}"}})'
        self.instances_pay = f'count(up{{job="{pay}"}})'
        self.up_auth = f'sum(up{{job="{auth}"}})'
        self.pool_in_use = "max(payment_db_pool_in_use)"
        self.pool_size = "max(payment_db_pool_size)"
        self.db_errors = "sum(rate(payment_db_errors_total[5m]))"
        self.cpu = '100 * (1 - avg(rate(node_cpu_seconds_total{mode="idle"}[1m])))'
        self.mem_total = "sum(node_memory_MemTotal_bytes)"
        self.mem_available = "sum(node_memory_MemAvailable_bytes)"
        disk = f'mountpoint="{settings.disk_mountpoint}"'
        self.disk_size = f"max(node_filesystem_size_bytes{{{disk}}})"
        self.disk_avail = f"max(node_filesystem_avail_bytes{{{disk}}})"
        self.net_in = (
            'sum(rate(node_network_receive_bytes_total{device!~"lo|veth.*|docker.*|br-.*"}[1m]))'
        )

    @staticmethod
    def p95(job: str, window: str = "5m") -> str:
        return (
            "1000 * histogram_quantile(0.95, sum by (le)"
            f'(rate(http_request_duration_highr_seconds_bucket{{job="{job}"}}[{window}])))'
        )


async def scalars(prometheus, exprs: dict[str, str]) -> tuple[dict[str, float | None], bool]:
    """Plusieurs requêtes en parallèle ; (valeurs, Prometheus joignable)."""
    keys = list(exprs)
    results = await asyncio.gather(
        *(prometheus.scalar(exprs[k]) for k in keys), return_exceptions=True
    )
    if all(isinstance(r, UpstreamDown) for r in results):
        return dict.fromkeys(keys), False
    values = {
        k: None if isinstance(r, Exception) else r for k, r in zip(keys, results, strict=True)
    }
    return values, True


async def platform_status(state) -> dict[str, Any] | None:
    """État publié par le moteur de remédiation, ou None s'il ne répond pas."""
    try:
        return await state.control_plane.remediation("/status")
    except UpstreamDown:
        return None


def tone_above(value: float | None, threshold: float, warn_ratio: float = 0.5) -> str | None:
    """`danger` au-dessus du seuil, `warn` au-delà de warn_ratio × seuil."""
    if value is None:
        return "unknown"
    if value > threshold:
        return "danger"
    if value > threshold * warn_ratio:
        return "warn"
    return None


def availability_kpi(value: float | None, objective: float) -> Kpi:
    sub = f"Objectif ≥ {fmt.number(objective, 1)} %"
    if value is None:
        tone = "unknown"
    elif value >= objective:
        sub, tone = sub + " tenu", None
    else:
        sub, tone = sub + " menacé", "warn"
    return Kpi(
        key="availability",
        label="Disponibilité (24 h)",
        value=fmt.percent(value, 2),
        raw=value,
        sub=sub,
        tone=tone,
    )


def threshold_kpi(
    key: str, label: str, value: float | None, shown: str, threshold: float, threshold_shown: str
) -> Kpi:
    exceeded = value is not None and value > threshold
    return Kpi(
        key=key,
        label=label,
        value=shown,
        raw=value,
        sub=f"Seuil {threshold_shown}" + (" dépassé" if exceeded else ""),
        tone=tone_above(value, threshold),
    )


def anomaly_kpi(value: float | None, threshold: float) -> Kpi:
    if value is None:
        sub, tone = "Détecteur sans données", "unknown"
    elif value >= threshold:
        sub, tone = f"Au-dessus du seuil {fmt.score(threshold)}", "danger"
    else:
        sub, tone = f"Sous le seuil {fmt.score(threshold)}", "ok"
    return Kpi(
        key="anomaly_score",
        label="Score d'anomalie",
        value=fmt.score(value),
        raw=value,
        sub=sub,
        tone=tone,
    )


def mttr_kpi(status, incident, detected, recovered, mttr) -> Kpi:
    if status is None:
        value, sub, tone = fmt.MISSING, "Moteur de remédiation injoignable", "unknown"
    elif detected and not recovered:
        value, sub, tone = "en cours", incident.get("id", ""), "warn"
    elif mttr is not None:
        value, sub, tone = fmt.duration(mttr), incident.get("id", ""), "ok"
    else:
        value, sub, tone = fmt.MISSING, "Aucun incident", None
    return Kpi(key="mttr", label="MTTR dernier incident", value=value, raw=mttr, sub=sub, tone=tone)


@router.get(
    "/overview", response_model=Overview, summary="État général et indicateurs", responses=RESPONSES
)
async def overview(request: Request, _: Operator = Depends(require_role("viewer"))) -> Overview:
    """Badge d'état, bannière et les 6 indicateurs de la page Supervision."""
    state = request.app.state
    settings = state.settings
    q = Queries(settings)
    values, prometheus_up = await scalars(
        state.prometheus,
        {
            "availability": q.availability,
            "latency": q.latency_p95_ms,
            "errors": q.error_rate,
            "tx": q.tx_per_min,
            "anomaly": q.anomaly,
            "up_pay": q.up_pay,
        },
    )
    status = await platform_status(state)

    incident = (status or {}).get("incident") or {}
    detected = parse_iso(incident.get("detected_at"))
    recovered = parse_iso(incident.get("recovered_at"))
    mttr = (recovered - detected).total_seconds() if detected and recovered else None
    kpis = [
        availability_kpi(values["availability"], settings.availability_objective_percent),
        threshold_kpi(
            "latency_p95",
            "Latence p95",
            values["latency"],
            fmt.ms(values["latency"]),
            settings.latency_threshold_ms,
            fmt.ms(settings.latency_threshold_ms),
        ),
        threshold_kpi(
            "error_rate",
            "Erreurs 5xx",
            values["errors"],
            fmt.percent(None if values["errors"] is None else values["errors"] * 100, 1),
            settings.error_rate_threshold,
            fmt.percent(settings.error_rate_threshold * 100, 0),
        ),
        Kpi(
            key="tx_per_min",
            label="Transactions / min",
            value=fmt.MISSING if values["tx"] is None else fmt.number(values["tx"]),
            raw=values["tx"],
            sub="Moyenne sur 5 min",
            tone="unknown" if values["tx"] is None else None,
        ),
        anomaly_kpi(values["anomaly"], settings.anomaly_threshold),
        mttr_kpi(status, incident, detected, recovered, mttr),
    ]

    badge, banner = status_and_banner(settings, status, values, prometheus_up, kpis, mttr)
    return Overview(
        updated_at=iso(now_utc()),
        status=badge,
        banner=banner,
        kpis=kpis,
        sources={
            "prometheus": "up" if prometheus_up else "down",
            "remediation": "down" if status is None else "up",
        },
    )


def status_and_banner(settings, status, values, prometheus_up, kpis, mttr):
    tz = settings.display_timezone
    if status and status.get("platform") in PLATFORM:
        label, tone = PLATFORM[status["platform"]]
        incident = status.get("incident") or {}
        detected = parse_iso(incident.get("detected_at"))
        recovered = parse_iso(incident.get("recovered_at"))
        ref = incident.get("id", "")
        if status["platform"] in ("incident", "remediation"):
            text = "Anomalie détectée — remédiation automatique en cours."
            meta = (
                f"Ouvert à {fmt.clock(detected, tz, True)} · {ref}".strip(" ·") if detected else ref
            )
        elif status["platform"] == "recovered" and recovered:
            verified = incident.get("verified_by")
            text = f"Service rétabli à {fmt.clock(recovered, tz, True)}." + (
                f" Vérifié par la transaction test {verified}." if verified else ""
            )
            meta = f"MTTR {fmt.duration(mttr)} · {ref}".strip(" ·")
        else:
            text, meta = "Tous les services sont opérationnels.", "Aucun incident ouvert"
        return StatusBadge(label=label, tone=tone), Banner(tone=tone, text=text, meta=meta)

    # Sans moteur de remédiation : état déduit des métriques
    if not prometheus_up:
        return (
            StatusBadge(label="État inconnu", tone="unknown"),
            Banner(
                tone="unknown",
                text="Métriques indisponibles : Prometheus ne répond pas.",
                meta="Moteur de remédiation injoignable" if status is None else "",
            ),
        )
    meta = "Moteur de remédiation injoignable : état déduit des métriques"
    if values["up_pay"] == 0:
        return (
            StatusBadge(label="Incident en cours", tone="danger"),
            Banner(tone="danger", text="payment-service ne répond plus.", meta=meta),
        )
    if any(k.tone == "danger" for k in kpis):
        return (
            StatusBadge(label="Dégradé", tone="warn"),
            Banner(
                tone="warn", text="Indicateurs au-delà des seuils sur payment-service.", meta=meta
            ),
        )
    return (
        StatusBadge(label="Opérationnel", tone="ok"),
        Banner(tone="ok", text="Tous les services surveillés répondent.", meta=meta),
    )


@router.get(
    "/services", response_model=ServicesOut, summary="État des services", responses=RESPONSES
)
async def services(request: Request, _: Operator = Depends(require_role("viewer"))) -> ServicesOut:
    """Une carte par service : `ok`, `warn`, `down`, `restored` (rétabli par la remédiation)
    ou `unknown` (pas de mesure)."""
    state = request.app.state
    settings = state.settings
    q = Queries(settings)
    values, _ = await scalars(
        state.prometheus,
        {
            "up_pay": q.up_pay,
            "instances_pay": q.instances_pay,
            "latency": q.latency_p95_ms,
            "errors": q.error_rate,
            "up_auth": q.up_auth,
            "auth_latency": q.auth_latency_p95_ms,
            "pool_in_use": q.pool_in_use,
            "pool_size": q.pool_size,
            "db_errors": q.db_errors,
            "anomaly": q.anomaly,
        },
    )
    status = await platform_status(state)
    remediation_states = {s.get("name"): s.get("state") for s in (status or {}).get("services", [])}

    def restored(name: str, card: ServiceCard) -> ServiceCard:
        if remediation_states.get(name) == "recovered" and card.status in ("ok", "warn"):
            card.status = "restored"
        return card

    cards = []
    up_pay, instances = values["up_pay"], values["instances_pay"]
    if up_pay is None:
        pay = ServiceCard(
            name="payment-service",
            desc="API de paiement · FastAPI",
            status="unknown",
            metric=fmt.MISSING,
        )
    else:
        degraded = (values["latency"] or 0) > settings.latency_threshold_ms or (
            values["errors"] or 0
        ) > settings.error_rate_threshold
        pay = ServiceCard(
            name="payment-service",
            desc="API de paiement · FastAPI",
            status="down" if up_pay == 0 else ("warn" if degraded else "ok"),
            metric=f"{int(up_pay)}/{int(instances or up_pay)} instance(s) · "
            f"{fmt.ms(values['latency'])}",
        )
    cards.append(restored("payment-service", pay))

    up_auth = values["up_auth"]
    cards.append(
        restored(
            "auth-service",
            ServiceCard(
                name="auth-service",
                desc="Authentification · mot de passe + visage",
                status="unknown" if up_auth is None else ("down" if up_auth == 0 else "ok"),
                metric=fmt.MISSING if up_auth is None else fmt.ms(values["auth_latency"]),
            ),
        )
    )

    in_use, size = values["pool_in_use"], values["pool_size"]
    if in_use is None or not size:
        db = ServiceCard(
            name="mariadb",
            desc="Base des clients et des opérations",
            status="unknown",
            metric=fmt.MISSING,
        )
    else:
        saturation = in_use / size
        db = ServiceCard(
            name="mariadb",
            desc="Base des clients et des opérations",
            status="warn" if saturation >= 0.8 or (values["db_errors"] or 0) > 0 else "ok",
            metric=f"pool {int(in_use)}/{int(size)} connexions",
        )
    cards.append(restored("mariadb", db))

    waf_state = remediation_states.get("waf")
    cards.append(
        ServiceCard(
            name="waf",
            desc="Pare-feu applicatif · SafeLine",
            status={"ok": "ok", "degraded": "warn", "down": "down", "recovered": "restored"}.get(
                waf_state, "unknown"
            ),
            metric="état publié par la remédiation" if waf_state else fmt.MISSING,
        )
    )

    incident = (status or {}).get("incident") or {}
    cards.append(
        ServiceCard(
            name="remediation-engine",
            desc="Moteur de remédiation · Ansible",
            status="unknown"
            if status is None
            else ("warn" if status.get("platform") in ("incident", "remediation") else "ok"),
            metric="injoignable"
            if status is None
            else (
                "playbook en cours"
                if status.get("platform") == "remediation"
                else ("dernier run OK" if incident.get("recovered_at") else "en veille")
            ),
        )
    )

    anomaly = values["anomaly"]
    cards.append(
        ServiceCard(
            name="detector-ml",
            desc="Détection d'anomalies · IsolationForest",
            status="unknown"
            if anomaly is None
            else ("warn" if anomaly >= settings.anomaly_threshold else "ok"),
            metric=fmt.MISSING if anomaly is None else f"score {fmt.score(anomaly)}",
        )
    )
    return ServicesOut(updated_at=iso(now_utc()), services=cards)


@router.get(
    "/series",
    response_model=SupervisionSeries,
    summary="Courbes : latence, score d'anomalie, transactions",
    responses=RESPONSES,
)
async def series(
    request: Request,
    minutes: int = Query(default=30, ge=5, le=360, description="fenêtre, une mesure par minute"),
    _: Operator = Depends(require_role("viewer")),
) -> SupervisionSeries:
    """Une mesure par minute. `incident` marque les minutes de l'incident en cours ou du
    dernier incident (bornes x1 / x2 pour la zone grisée des graphiques)."""
    state = request.app.state
    settings = state.settings
    q = Queries(settings)
    end = now_utc().replace(second=0, microsecond=0)
    start = end - timedelta(minutes=minutes - 1)

    async def fetch(expr: str) -> dict[int, float]:
        try:
            return await state.prometheus.range(expr, start, end, 60)
        except UpstreamDown:
            return {}

    latency, anomaly, tx = await asyncio.gather(
        fetch(Queries.p95(settings.payment_job, "1m")), fetch(q.anomaly), fetch(q.tx_per_min_1m)
    )
    status = await platform_status(state)
    incident = (status or {}).get("incident") or {}
    detected = parse_iso(incident.get("detected_at"))
    recovered = parse_iso(incident.get("recovered_at"))

    tz = settings.display_timezone
    points = []
    for i in range(minutes):
        moment = start + timedelta(minutes=i)
        ts = int(moment.timestamp())
        in_incident = bool(
            detected
            and detected <= moment + timedelta(minutes=1)
            and (recovered is None or moment <= recovered)
        )
        points.append(
            SeriesMinute(
                time=fmt.clock(moment, tz),
                ts=iso(moment),
                incident=in_incident,
                latency=None if ts not in latency else round(latency[ts]),
                anomaly=None if ts not in anomaly else round(anomaly[ts], 2),
                tx=None if ts not in tx else round(tx[ts]),
            )
        )
    window = None
    if detected and (recovered or end) >= start:
        window = IncidentWindow(
            x1=fmt.clock(max(detected, start), tz),
            x2=fmt.clock(min(recovered or end, end), tz),
        )
    return SupervisionSeries(points=points, incident=window)


@router.get(
    "/resources", response_model=ResourcesOut, summary="Ressources du PC Hôte", responses=RESPONSES
)
async def resources(
    request: Request, _: Operator = Depends(require_role("viewer"))
) -> ResourcesOut:
    """CPU, mémoire, disque et réseau entrant (node-exporter)."""
    state = request.app.state
    q = Queries(state.settings)
    v, _up = await scalars(
        state.prometheus,
        {
            "cpu": q.cpu,
            "mem_total": q.mem_total,
            "mem_available": q.mem_available,
            "disk_size": q.disk_size,
            "disk_avail": q.disk_avail,
            "net_in": q.net_in,
        },
    )
    out = [
        Resource(
            label="CPU",
            value=fmt.percent(v["cpu"], 0),
            percent=None if v["cpu"] is None else round(v["cpu"], 1),
        )
    ]
    if v["mem_total"] and v["mem_available"] is not None:
        used = v["mem_total"] - v["mem_available"]
        out.append(
            Resource(
                label="Mémoire",
                value=f"{fmt.size(used)} / {fmt.size(v['mem_total'], decimals=0)} Go",
                percent=round(100 * used / v["mem_total"], 1),
            )
        )
    else:
        out.append(Resource(label="Mémoire", value=fmt.MISSING, percent=None))
    if v["disk_size"] and v["disk_avail"] is not None:
        used = v["disk_size"] - v["disk_avail"]
        out.append(
            Resource(
                label="Disque",
                value=f"{fmt.size(used, decimals=0)} / {fmt.size(v['disk_size'], decimals=0)} Go",
                percent=round(100 * used / v["disk_size"], 1),
            )
        )
    else:
        out.append(Resource(label="Disque", value=fmt.MISSING, percent=None))
    reference = state.settings.network_reference_bytes_per_second
    out.append(
        Resource(
            label="Réseau entrant",
            value=fmt.rate_mb(v["net_in"]),
            percent=None
            if v["net_in"] is None
            else round(min(100, 100 * v["net_in"] / reference), 1),
        )
    )
    return ResourcesOut(resources=out)


# --- Journaux --------------------------------------------------------------------------------

LEVELS = {
    "debug": "DEBUG",
    "info": "INFO",
    "warning": "WARN",
    "error": "ERROR",
    "critical": "ERROR",
}
# Champs recopiés dans le message affiché ; tout le reste (identifiants, IP, emails) est retiré
SAFE_FIELDS = ("reason", "code", "status", "upstream", "result", "resource", "factors", "templates")
ACTION_EVENTS = ("session_revoked", "operator_session_revoked", "account_locked", "operator_locked")


def log_line(ts_ns: int, labels: dict[str, str], line: str, tz: str) -> LogLine | None:
    try:
        data = json.loads(line)
    except ValueError:
        return None
    if not isinstance(data, dict) or "msg" not in data:
        return None
    msg = str(data["msg"]).strip()
    if msg == "request":
        text = (
            f"{data.get('method', '')} {data.get('path', '')} → {data.get('status', '')}"
            f" · {data.get('duration_ms', '?')} ms"
        )
    else:
        extras = [f"{k}={data[k]}" for k in SAFE_FIELDS if k in data and data[k] is not None]
        text = msg + (" · " + " ".join(extras) if extras else "")
    level = LEVELS.get(str(data.get("level", "info")).lower(), "INFO")
    if msg in ACTION_EVENTS:
        level = "ACTION"
    moment = datetime.fromtimestamp(ts_ns / 1e9, UTC)
    source = data.get("service") or labels.get("container", "?")
    return LogLine(
        time=fmt.clock(moment, tz, True) + f".{int(ts_ns / 1e6) % 1000:03d}",
        ts=moment.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        level=level,
        source=str(source).removeprefix("oorbe-"),
        msg=text[:300],
    )


@router.get("/logs", response_model=LogsOut, summary="Derniers journaux", responses=RESPONSES)
async def logs(
    request: Request,
    level: Literal["all", "warn", "error"] = "all",
    source: str | None = Query(default=None, max_length=40, pattern=r"^[a-z0-9-]+$"),
    minutes: int = Query(default=15, ge=1, le=60),
    limit: int = Query(default=100, ge=1, le=200),
    hide_requests: bool = Query(default=True, description="masquer les journaux d'accès HTTP"),
    _: Operator = Depends(require_role("viewer")),
) -> LogsOut:
    """Journaux des services (Loki), plus récents d'abord. Les identifiants, adresses IP et
    emails sont retirés : seuls l'événement et quelques champs techniques sont affichés."""
    state = request.app.state
    settings = state.settings
    # Lignes JSON de nos services seulement (les journaux de Loki, Grafana… sont écartés par Loki)
    query = settings.loki_selector + ' | json | __error__="" | msg!=""'
    if level == "warn":
        query += ' | level=~"warning|error|critical"'
    elif level == "error":
        query += ' | level=~"error|critical"'
    if source:
        query += f' | service="{source}"'
    if hide_requests:
        query += ' | msg!="request"'
    end = now_utc()
    try:
        raw = await state.loki.lines(query, end - timedelta(minutes=minutes), end, limit)
    except UpstreamDown as exc:
        raise upstream_unavailable(exc.name) from None
    lines = [log_line(ts, labels, line, settings.display_timezone) for ts, labels, line in raw]
    return LogsOut(logs=[line for line in lines if line is not None])
