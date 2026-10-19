"""Désignation d'un correspondant par email ou téléphone (CADRAGE §4.3)."""

import re
from dataclasses import dataclass
from typing import Literal

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_SEPARATORS = re.compile(r"[\s.\-()]")


@dataclass(frozen=True)
class Contact:
    kind: Literal["email", "phone"]
    value: str


def parse_contact(raw: str) -> Contact | None:
    """Normalise un email (minuscules) ou un téléphone (E.164). None si le format est invalide.

    '06 12 34 56 78', '0033 6 12 34 56 78' et '+33612345678' donnent tous '+33612345678'.
    """
    text = raw.strip()
    if "@" in text:
        email = text.lower()
        return Contact("email", email) if _EMAIL.fullmatch(email) else None

    digits = _PHONE_SEPARATORS.sub("", text)
    if digits.startswith("00"):
        digits = "+" + digits[2:]
    if re.fullmatch(r"0[1-9]\d{8}", digits):
        return Contact("phone", "+33" + digits[1:])
    if re.fullmatch(r"\+[1-9]\d{7,14}", digits):
        return Contact("phone", digits)
    return None
