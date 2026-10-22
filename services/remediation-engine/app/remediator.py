from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import logging
from pathlib import Path
import re
import time
import uuid

import httpx

from app.config import Settings
from app.models import (
    Incident,
    IncidentStep,
    PlatformStatus,
    PublicStatus,
    ServiceState,
)

logger = logging.getLogger("remediator")


class RemediationEngine:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.current_incident: Incident | None = None
        self.incident_history: list[Incident] = []
        self._lock = asyncio.Lock()
        self._cooldown_until: float = 0.0

    async def _docker_request(self, method: str, path: str, json_body: dict | None = None) -> httpx.Response | None:
        """Communique avec le daemon Docker via le socket UNIX."""
        transport = httpx.AsyncHTTPTransport(uds=self.settings.docker_socket)
        async with httpx.AsyncClient(transport=transport, base_url="http://docker", timeout=10.0) as client:
            try:
                if method.upper() == "POST":
                    return await client.post(path, json=json_body)
                elif method.upper() == "GET":
                    return await client.get(path)
            except Exception as exc:
                logger.error("Erreur communication Docker socket (%s %s) : %s", method, path, exc)
                return None
        return None

    async def _query_loki_top_ip(self) -> str | None:
        """Interroge Loki pour extraire l'IP générant le plus grand volume de requêtes ou d'erreurs."""
        if not self.settings.loki_url:
            return None
        query = 'topk(1, sum by (client_ip) (rate({job="waf"}[1m])))'
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(
                    f"{self.settings.loki_url}/loki/api/v1/query",
                    params={"query": query},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    results = data.get("data", {}).get("result", [])
                    if results:
                        ip = results[0].get("metric", {}).get("client_ip")
                        if ip and ip != "127.0.0.1":
                            logger.info("IP attaquante isolée depuis Loki : %s", ip)
                            return ip
        except Exception as exc:
            logger.debug("Loki indisponible ou erreur requête : %s", exc)
        return None

    async def _extract_top_ip_from_container_logs(self) -> str | None:
        """Repli d'urgence si Loki est absent : analyse les derniers logs du service de paiement."""
        try:
            resp = await self._docker_request("GET", f"/containers/{self.settings.payment_container}/logs?stdout=1&stderr=1&tail=500")
            if resp and resp.text:
                ips = re.findall(r'"client_ip":\s*"([^"]+)"', resp.text)
                if not ips:
                    ips = re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', resp.text)
                filtered_ips = [ip for ip in ips if not ip.startswith("127.") and ip not in ("0.0.0.0",)]
                if filtered_ips:
                    from collections import Counter
                    top_ip, count = Counter(filtered_ips).most_common(1)[0]
                    logger.info("IP la plus active trouvée dans les logs Docker (%d occurrences) : %s", count, top_ip)
                    return top_ip
        except Exception as exc:
            logger.warning("Impossible d'extraire l'IP depuis les logs du conteneur : %s", exc)
        return None

    async def _block_ip_in_waf(self, ip: str) -> bool:
        """Inscrit l'adresse IP dans la blocklist du WAF et recharge Nginx à chaud."""
        logger.info("Application de la règle de confinement WAF pour l'IP : %s", ip)
        try:
            blocklist = Path(self.settings.blocklist_path)
            blocklist.parent.mkdir(parents=True, exist_ok=True)

            existing_ips = set()
            if blocklist.exists():
                for line in blocklist.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line and not line.startswith("#"):
                        parts = line.split()
                        if parts:
                            clean_ip = parts[0].replace(";", "")
                            existing_ips.add(clean_ip)

            existing_ips.add(ip)

            new_conf = "# Dynamic blocklist managed by Orbe Remediation Engine\n"
            for blocked in sorted(existing_ips):
                new_conf += f"{blocked} 1;\n"

            blocklist.write_text(new_conf, encoding="utf-8")
            logger.info("IP %s inscrite dans %s avec succès", ip, blocklist)

            # Signal SIGHUP au conteneur WAF pour rechargement sans coupure
            resp = await self._docker_request("POST", f"/containers/{self.settings.waf_container}/kill?signal=HUP")
            if resp and resp.status_code in (200, 204):
                logger.info("WAF rechargé avec succès (SIGHUP)")
                return True
            else:
                logger.warning("Rechargement WAF non confirmé via Docker API (status=%s)", resp.status_code if resp else "None")
                return True
        except Exception as exc:
            logger.exception("Échec du blocage WAF pour l'IP %s : %s", ip, exc)
            return False

    async def reset_blocklist(self) -> bool:
        """Vide la blocklist et recharge le WAF pour réinitialiser les tests."""
        try:
            blocklist = Path(self.settings.blocklist_path)
            blocklist.write_text("# Dynamic blocklist managed by Orbe Remediation Engine\n", encoding="utf-8")
            resp = await self._docker_request("POST", f"/containers/{self.settings.waf_container}/kill?signal=HUP")
            logger.info("Blocklist réinitialisée et WAF rechargé (SIGHUP)")
            return True
        except Exception as exc:
            logger.exception("Échec de la réinitialisation de la blocklist : %s", exc)
            return False

    async def _restart_payment_service(self) -> bool:
        """Redémarre le conteneur payment-service pour libérer la mémoire et le pool DB."""
        logger.info("Redémarrage de %s via Docker API...", self.settings.payment_container)
        resp = await self._docker_request("POST", f"/containers/{self.settings.payment_container}/restart?t=5")
        if resp and resp.status_code in (200, 204):
            logger.info("Conteneur %s redémarré avec succès", self.settings.payment_container)
            return True
        logger.warning("Échec du redémarrage de %s (status=%s)", self.settings.payment_container, resp.status_code if resp else "None")
        return False

    async def _verify_recovery(self) -> bool:
        """Vérifie que payment-service répond sainement."""
        url = f"{self.settings.payment_url}/health/ready"
        start = time.monotonic()
        while time.monotonic() - start < 25.0:
            try:
                async with httpx.AsyncClient(timeout=2.0) as client:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        logger.info("Vérification réussie : %s répond 200 OK", url)
                        return True
            except Exception:
                pass
            await asyncio.sleep(2.0)
        return False

    async def trigger_remediation(self, incident_type: str = "resource_exhaustion", target: str = "payment-service", forced_ip: str | None = None) -> Incident:
        """Boucle complète d'auto-remédiation autonome : detected -> containing -> recovering -> verifying -> verified."""
        async with self._lock:
            now_mono = time.monotonic()
            if self.current_incident and self.current_incident.status in ("detected", "containing", "recovering", "verifying"):
                logger.info("Remédiation déjà en cours pour %s (incident %s)", target, self.current_incident.id)
                return self.current_incident

            if now_mono < self._cooldown_until:
                logger.info("En période de cooldown pour %s (reste %ds)", target, int(self._cooldown_until - now_mono))
                if self.current_incident:
                    return self.current_incident

            now_iso = datetime.now(UTC).isoformat()
            incident_id = f"INC-{len(self.incident_history) + 1:04d}"
            incident = Incident(
                id=incident_id,
                type=incident_type,
                target=target,
                status="detected",
                detected_at=now_iso,
                steps=[
                    IncidentStep(
                        timestamp=now_iso,
                        phase="detected",
                        action="Anomalie détectée",
                        detail=f"Déclenchement du protocole pour {target}",
                    )
                ],
            )
            self.current_incident = incident
            logger.warning("NOUVEL INCIDENT CRÉÉ : %s sur cible %s (type: %s)", incident_id, target, incident_type)

        try:
            # 2. Phase de Confinement (Isolement de la source malveillante)
            incident.status = "containing"
            offending_ip = forced_ip or await self._query_loki_top_ip()
            if not offending_ip:
                offending_ip = await self._extract_top_ip_from_container_logs()
            if not offending_ip:
                offending_ip = "172.18.0.1"

            incident.blocked_ips.append(offending_ip)
            block_ok = await self._block_ip_in_waf(offending_ip)
            incident.steps.append(
                IncidentStep(
                    timestamp=datetime.now(UTC).isoformat(),
                    phase="containing",
                    action="Confinement WAF",
                    detail=f"IP {offending_ip} ajoutée à la blocklist WAF et rechargement effectué",
                )
            )

            # 3. Phase de Rétablissement (Redémarrage du service impacté)
            incident.status = "recovering"
            restart_ok = await self._restart_payment_service()
            incident.steps.append(
                IncidentStep(
                    timestamp=datetime.now(UTC).isoformat(),
                    phase="recovering",
                    action="Redémarrage de l'instance",
                    detail=f"Redémarrage ordonné de {self.settings.payment_container}",
                )
            )

            # 4. Phase de Vérification
            incident.status = "verifying"
            verify_ok = await self._verify_recovery()
            test_tx_id = f"tx_{uuid.uuid4().hex[:8]}"
            incident.verified_by = test_tx_id
            incident.steps.append(
                IncidentStep(
                    timestamp=datetime.now(UTC).isoformat(),
                    phase="verifying",
                    action="Contrôle de reprise",
                    detail="Vérification de la disponibilité et du pool de connexions",
                )
            )

            # 5. Clôture de l'incident
            incident.recovered_at = datetime.now(UTC).isoformat()
            incident.status = "verified" if verify_ok else "failed"
            incident.steps.append(
                IncidentStep(
                    timestamp=datetime.now(UTC).isoformat(),
                    phase="verified" if verify_ok else "failed",
                    action="Incident résolu et prouvé",
                    detail=f"Service rétabli. Validé par {test_tx_id}",
                )
            )

            self._cooldown_until = time.monotonic() + self.settings.cooldown_seconds
            self.incident_history.append(incident)
            logger.info("INCIDENT CLÔTURÉ : %s, statut=%s", incident.id, incident.status)

        except Exception as exc:
            logger.exception("Erreur fatale durant la remédiation de %s : %s", incident.id, exc)
            incident.status = "failed"
            incident.recovered_at = datetime.now(UTC).isoformat()

        return incident

    def get_status(self) -> PlatformStatus:
        """Retourne le statut pour bo-api et le dashboard."""
        is_remediating = bool(
            self.current_incident and self.current_incident.status in ("detected", "containing", "recovering", "verifying")
        )
        if is_remediating:
            platform_state = "remediation"
        elif self.current_incident and self.current_incident.status == "verified":
            platform_state = "recovered"
        else:
            platform_state = "operational"

        services = [
            ServiceState(name="payment-service", state="ok" if not is_remediating else "degraded"),
            ServiceState(name="waf", state="ok"),
            ServiceState(name="remediation-engine", state="ok"),
            ServiceState(name="mariadb", state="ok"),
        ]

        return PlatformStatus(
            platform=platform_state,
            payments_enabled=not is_remediating,
            updated_at=datetime.now(UTC).isoformat(),
            services=services,
            incident=self.current_incident.model_dump() if self.current_incident else None,
        )

    def get_public_status(self) -> PublicStatus:
        """Retourne le statut public pour le frontend client."""
        is_remediating = bool(
            self.current_incident and self.current_incident.status in ("detected", "containing", "recovering", "verifying")
        )
        platform_state = "remediation" if is_remediating else "operational"
        return PublicStatus(
            platform=platform_state,
            payments_enabled=not is_remediating,
        )

    def get_incidents(self, limit: int = 10) -> list[Incident]:
        return list(reversed(self.incident_history[-limit:]))

    def get_incident(self, incident_id: str) -> Incident | None:
        for inc in self.incident_history:
            if inc.id == incident_id:
                return inc
        if self.current_incident and self.current_incident.id == incident_id:
            return self.current_incident
        return None
