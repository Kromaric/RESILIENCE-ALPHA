from typing import Literal

from pydantic import BaseModel, Field, SecretStr, model_validator


class ErrorDetail(BaseModel):
    code: str = Field(examples=["insufficient_balance"])
    message: str = Field(examples=["Solde insuffisant."])


class ErrorOut(BaseModel):
    detail: ErrorDetail


class CardIn(BaseModel):
    # SecretStr : le numéro et le CVC n'apparaissent ni dans les repr ni dans les erreurs
    number: SecretStr
    exp_month: int = Field(ge=1, le=12)
    exp_year: int = Field(ge=2000, le=2100)
    cvc: SecretStr
    holder: str = Field(min_length=1, max_length=80)


class PayIn(BaseModel):
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "recipient": "06 12 34 56 77",
                    "amount_cents": 1250,
                    "currency": "EUR",
                    "description": "Ciné",
                    "card": {
                        "number": "4242 4242 4242 4242",
                        "exp_month": 12,
                        "exp_year": 2030,
                        "cvc": "123",
                        "holder": "Camille Test",
                    },
                }
            ]
        }
    }

    recipient: str | None = Field(default=None, min_length=3, max_length=254)
    recipient_qr: str | None = Field(default=None, min_length=16, max_length=64)
    recipient_contact: str | None = Field(
        default=None, min_length=36, max_length=36, description="client_id d'un de mes contacts"
    )
    amount_cents: int = Field(ge=1)
    currency: Literal["EUR"] = "EUR"
    description: str | None = Field(default=None, max_length=140)
    card: CardIn

    @model_validator(mode="after")
    def one_recipient(self) -> "PayIn":
        given = [self.recipient, self.recipient_qr, self.recipient_contact]
        if sum(value is not None for value in given) != 1:
            raise ValueError(
                "Indiquez un seul destinataire : recipient (email ou téléphone), "
                "recipient_qr ou recipient_contact."
            )
        return self


class CardOut(BaseModel):
    brand: str
    last4: str


class PaymentOut(BaseModel):
    reference: str
    status: str
    decline_reason: str | None
    amount_cents: int
    currency: str
    card: CardOut | None
    created_at: str


class TransactionItem(BaseModel):
    reference: str
    type: str
    direction: Literal["sent", "received"]
    counterparty: str
    description: str | None
    card_last4: str | None
    amount_cents: int
    currency: str
    status: str
    created_at: str


class TransactionList(BaseModel):
    items: list[TransactionItem]
    next_cursor: str | None


class RefundOut(BaseModel):
    reference: str
    status: str
    amount_cents: int
    refunded: str  # référence du paiement remboursé


class PayoutAccountOut(BaseModel):
    id: str
    label: str
    iban_last4: str
    is_default: bool


class PayoutAccountIn(BaseModel):
    model_config = {
        "json_schema_extra": {
            "examples": [{"label": "Banque Démo", "iban": "FR76 3000 6000 0112 3456 7890 189"}]
        }
    }

    label: str = Field(min_length=1, max_length=80)
    iban: str = Field(
        min_length=15,
        max_length=42,
        description="Fictif ; seuls les 4 derniers caractères sont conservés",
    )
    make_default: bool = False


class AccountOut(BaseModel):
    balance_cents: int
    currency: str = "EUR"
    payout_accounts: list[PayoutAccountOut]


class PayoutIn(BaseModel):
    amount_cents: int = Field(ge=1)
    payout_account_id: str | None = Field(
        default=None, description="Compte lié destinataire ; compte par défaut si absent"
    )


class PayoutOut(BaseModel):
    reference: str
    status: str
    amount_cents: int
    payout_account_id: str | None
    created_at: str


class ContactIn(BaseModel):
    contact: str = Field(min_length=3, max_length=254, description="Email ou téléphone")
    alias: str | None = Field(default=None, max_length=80)


class ContactOut(BaseModel):
    contact_id: str
    display_name: str
    alias: str | None
    added_at: str


class RequestIn(BaseModel):
    model_config = {
        "json_schema_extra": {
            "examples": [
                {"payer": "camille@orbe.test", "amount_cents": 800, "description": "Covoiturage"}
            ]
        }
    }

    payer: str = Field(min_length=3, max_length=254)
    amount_cents: int = Field(ge=1)
    description: str | None = Field(default=None, max_length=140)


class RequestPayIn(BaseModel):
    card: CardIn


class RequestOut(BaseModel):
    reference: str
    role: Literal["incoming", "outgoing"]
    counterparty: str
    amount_cents: int
    currency: str
    description: str | None
    status: str
    failure_reason: str | None
    created_at: str
    expires_at: str


class RequestList(BaseModel):
    items: list[RequestOut]


class QrOut(BaseModel):
    qr_token: str
    payload: str
    display_name: str
