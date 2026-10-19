"""Cartes de test (CADRAGE §4.3). Aucune carte réelle n'est acceptée.

Le numéro complet et le CVC ne sortent jamais de ce module : seuls la marque et
les 4 derniers chiffres sont conservés.
"""

from dataclasses import dataclass
from datetime import date

# numéro → motif de refus (None = autorisée)
TEST_CARDS: dict[str, str | None] = {
    "4242424242424242": None,
    "4000000000000002": "card_declined",
    "4000000000000069": "card_expired",
    "4000000000009995": "insufficient_funds",
}


class CardError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class CardCheck:
    brand: str
    last4: str
    decline_reason: str | None


def luhn_valid(digits: str) -> bool:
    total = 0
    for position, char in enumerate(reversed(digits)):
        value = int(char)
        if position % 2 == 1:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0


def brand_of(digits: str) -> str:
    if digits.startswith("4"):
        return "visa"
    if digits[:2] in {"51", "52", "53", "54", "55"} or "2221" <= digits[:4] <= "2720":
        return "mastercard"
    if digits[:2] in {"34", "37"}:
        return "amex"
    return "card"


def check_card(number: str, exp_month: int, exp_year: int, cvc: str, today: date) -> CardCheck:
    digits = number.replace(" ", "").replace("-", "")
    if not digits.isdigit() or not 13 <= len(digits) <= 19 or not luhn_valid(digits):
        raise CardError("invalid_card", "Numéro de carte invalide.")
    if (exp_year, exp_month) < (today.year, today.month):
        raise CardError("invalid_card", "La date d'expiration est dépassée.")
    if not (cvc.isdigit() and len(cvc) in (3, 4)):
        raise CardError("invalid_card", "Cryptogramme invalide.")
    if digits not in TEST_CARDS:
        raise CardError("card_not_supported", "Seules les cartes de test sont acceptées.")
    return CardCheck(brand=brand_of(digits), last4=digits[-4:], decline_reason=TEST_CARDS[digits])
