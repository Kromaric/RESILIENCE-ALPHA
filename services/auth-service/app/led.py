"""LED bicolore (ESP8266) qui suit la connexion au back-office sur le PC Hôte.

| Étape de la connexion                         | LED                                         |
|-----------------------------------------------|---------------------------------------------|
| Au repos                                      | off                                         |
| Identifiant saisi et visage reconnu           | green_blink jusqu'au mot de passe           |
| Mot de passe correct                          | green_fixed 30 s, puis off (BO disponible)  |
| Mot de passe faux                             | red_blink 10 fois, puis off (retour à zéro) |
| Visage non reconnu                            | red_fixed 30 s, puis off (identifiant libre)|

Une seule LED pour le poste du back-office : l'état est global et tenu en mémoire (un
redémarrage d'auth-service éteint la LED). L'ESP8266 interroge `GET /devices/led` (clé
d'appareil) et joue lui-même le motif ; `seq` change à chaque nouvel état, pour qu'il
recommence un motif fini (les 10 clignotements) même si l'état est identique au précédent.
"""

import hmac
import logging
import time
from dataclasses import dataclass
from typing import Literal

from fastapi import APIRouter, Header, HTTPException, Request, status
from pydantic import BaseModel

from app.logging_setup import log_event
from app.schemas import ErrorOut, error

LedState = Literal["off", "green_blink", "green_fixed", "red_blink", "red_fixed"]
logger = logging.getLogger("led")


@dataclass
class _Current:
    state: LedState = "off"
    seq: int = 0
    until: float | None = None  # horloge monotone ; None : jusqu'au prochain changement
    blinks: int | None = None


class LedController:
    def __init__(self, blink_period_ms: int, clock=time.monotonic) -> None:
        self.blink_period_ms = blink_period_ms
        self._clock = clock
        self._current = _Current()
        # Après un visage non reconnu, l'identification est bloquée le temps du rouge fixe
        self._identification_locked_until = 0.0

    def _expire(self) -> None:
        current = self._current
        if current.until is not None and self._clock() >= current.until:
            self._current = _Current(seq=current.seq + 1)

    def set(self, state: LedState, *, seconds: float | None = None, blinks: int | None = None):
        self._expire()
        until = self._clock() + seconds if seconds is not None else None
        self._current = _Current(state, self._current.seq + 1, until, blinks)
        log_event(logger, "led_state", state=state, seconds=seconds, blinks=blinks)

    def off(self) -> None:
        if self.snapshot()["state"] != "off":
            self.set("off")

    def blink_red(self, blinks: int) -> None:
        self.set("red_blink", seconds=blinks * self.blink_period_ms / 1000, blinks=blinks)

    def snapshot(self) -> dict:
        self._expire()
        current = self._current
        remaining = None
        if current.until is not None:
            remaining = max(0, int((current.until - self._clock()) * 1000))
        return {
            "state": current.state,
            "seq": current.seq,
            "remaining_ms": remaining,
            "blinks": current.blinks,
            "blink_period_ms": self.blink_period_ms,
        }

    def lock_identification(self, seconds: float) -> None:
        self._identification_locked_until = self._clock() + seconds

    def identification_retry_after(self) -> int:
        """Secondes avant de pouvoir ressaisir un identifiant (0 : libre)."""
        return max(0, int(self._identification_locked_until - self._clock() + 0.999))


class LedOut(BaseModel):
    state: LedState
    seq: int
    remaining_ms: int | None
    blinks: int | None
    blink_period_ms: int


router = APIRouter(prefix="/devices", tags=["Objet connecté"])


@router.get(
    "/led",
    response_model=LedOut,
    summary="État de la LED du poste back-office (ESP8266)",
    responses={401: {"model": ErrorOut, "description": "Clé d'appareil absente ou invalide"}},
)
async def led(
    request: Request, x_device_key: str | None = Header(default=None, alias="X-Device-Key")
) -> LedOut:
    """À interroger toutes les 300 ms environ. Motifs : `off`, `green_fixed`, `red_fixed`,
    `green_blink` (période `blink_period_ms`), `red_blink` (`blinks` clignotements, puis éteinte).
    `remaining_ms` : durée restante de l'état, `null` s'il dure jusqu'au prochain changement."""
    expected = request.app.state.led_device_key
    if not expected or not x_device_key or not hmac.compare_digest(x_device_key, expected):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail=error("invalid_device", "Appareil inconnu.")
        )
    return LedOut(**request.app.state.led.snapshot())
