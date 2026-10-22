from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class IncidentStep(BaseModel):
    timestamp: str
    phase: Literal["detected", "containing", "recovering", "verifying", "verified", "failed"]
    action: str
    detail: str | None = None


class Incident(BaseModel):
    id: str
    type: str = "resource_exhaustion"
    target: str = "payment-service"
    status: Literal["detected", "containing", "recovering", "verifying", "verified", "failed"]
    detected_at: str
    recovered_at: str | None = None
    verified_by: str | None = None
    blocked_ips: list[str] = Field(default_factory=list)
    steps: list[IncidentStep] = Field(default_factory=list)


class ServiceState(BaseModel):
    name: str
    state: Literal["ok", "degraded", "remediation", "recovered"]


class PlatformStatus(BaseModel):
    platform: Literal["operational", "incident", "remediation", "recovered"]
    payments_enabled: bool
    updated_at: str
    services: list[ServiceState] = Field(default_factory=list)
    incident: dict[str, Any] | None = None


class PublicStatus(BaseModel):
    platform: Literal["operational", "incident", "remediation", "recovered"]
    payments_enabled: bool


# Alertmanager webhook payload models
class AlertItem(BaseModel):
    status: str
    labels: dict[str, str] = Field(default_factory=dict)
    annotations: dict[str, str] = Field(default_factory=dict)
    startsAt: str | None = None
    endsAt: str | None = None


class AlertmanagerPayload(BaseModel):
    version: str | None = None
    groupKey: str | None = None
    status: str
    receiver: str | None = None
    alerts: list[AlertItem] = Field(default_factory=list)
