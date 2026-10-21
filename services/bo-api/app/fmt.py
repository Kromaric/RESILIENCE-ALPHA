"""Mise en forme française des valeurs affichées par le dashboard (« 2 140 ms », « 99,98 % »).

Chaque indicateur est renvoyé avec sa valeur brute (`raw`) et sa forme affichable (`value`) :
le front peut afficher la seconde telle quelle, ou mettre en forme la première lui-même.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

MISSING = "—"


def number(value: float, decimals: int = 0) -> str:
    text = f"{value:,.{decimals}f}"  # 2,140.50
    return text.replace(",", " ").replace(".", ",")  # 2 140,50


def percent(value: float | None, decimals: int = 1) -> str:
    return MISSING if value is None else f"{number(value, decimals)} %"


def ms(value: float | None) -> str:
    return MISSING if value is None else f"{number(value)} ms"


def score(value: float | None) -> str:
    return MISSING if value is None else number(value, 2)


def size(bytes_: float, unit_bytes: float = 1024**3, decimals: int = 1) -> str:
    return number(bytes_ / unit_bytes, decimals)


def rate_mb(bytes_per_second: float | None) -> str:
    return MISSING if bytes_per_second is None else f"{number(bytes_per_second / 1e6, 1)} Mo/s"


def duration(seconds: float | None) -> str:
    """125 → « 2 min 05 s »."""
    if seconds is None:
        return MISSING
    seconds = int(round(seconds))
    if seconds < 60:
        return f"{seconds} s"
    minutes, rest = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes} min {rest:02d} s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours} h {minutes:02d} min"


def clock(moment: datetime, tz: str, with_seconds: bool = False) -> str:
    """Heure locale affichée : « 10:42 » ou « 10:42:07 »."""
    local = moment.astimezone(ZoneInfo(tz))
    return local.strftime("%H:%M:%S" if with_seconds else "%H:%M")
