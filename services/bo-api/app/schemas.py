"""Réponses des routes de données applicatives (`/bo/data`). Montants en centimes, dates UTC."""

from typing import Literal

from pydantic import BaseModel


class ClientsSummary(BaseModel):
    total: int
    new_7d: int
    face_enrolled: int
    locked: int


class Count(BaseModel):
    key: str
    count: int


class OperationsWindow(BaseModel):
    count: int
    by_type: dict[str, int]
    by_status: dict[str, int]
    payments_authorized_cents: int
    refunds_cents: int
    payouts_cents: int
    decline_rate: float  # refus / paiements tentés, entre 0 et 1
    decline_reasons: list[Count]


class RequestsSummary(BaseModel):
    pending: int
    paid_7d: int


class BalancesSummary(BaseModel):
    clients_total_cents: int
    counterparts_cents: dict[str, int]  # card_settlement, payouts


class Summary(BaseModel):
    generated_at: str
    clients: ClientsSummary
    operations_24h: OperationsWindow
    operations_7d: OperationsWindow
    requests: RequestsSummary
    balances: BalancesSummary


class SeriesPoint(BaseModel):
    time: str
    value: int


class Series(BaseModel):
    metric: Literal["transactions", "amount", "declines", "registrations"]
    interval: Literal["hour", "day"]
    points: list[SeriesPoint]


class AccountMismatch(BaseModel):
    account_id: str
    label: str
    balance_cents: int
    computed_cents: int


class EntriesAnomaly(BaseModel):
    reference: str
    status: str
    entries: int


class LedgerCheck(BaseModel):
    ok: bool
    checked_at: str
    transactions_checked: int
    accounts_checked: int
    unbalanced_transactions: list[str]
    account_mismatches: list[AccountMismatch]
    negative_client_balances: int
    entries_anomalies: list[EntriesAnomaly]


class Party(BaseModel):
    client_id: str
    display_name: str


class Card(BaseModel):
    brand: str | None
    last4: str


class TransactionItem(BaseModel):
    reference: str
    type: Literal["payment", "refund", "payout"]
    amount_cents: int
    currency: str
    status: str
    decline_reason: str | None
    card: Card | None
    payer: Party
    recipient: Party | None
    description: str | None
    created_at: str


class TransactionPage(BaseModel):
    items: list[TransactionItem]
    page: int
    size: int
    total: int


class LedgerLine(BaseModel):
    direction: Literal["debit", "credit"]
    amount_cents: int
    account_type: Literal["client", "counterpart"]
    account_label: str


class PayoutAccount(BaseModel):
    label: str
    iban_last4: str
    is_default: bool


class TransactionDetail(TransactionItem):
    updated_at: str
    parent_reference: str | None  # remboursement → paiement d'origine
    refund_reference: str | None  # paiement → son remboursement
    request_reference: str | None  # demande d'argent réglée par ce paiement
    payout_account: PayoutAccount | None
    entries: list[LedgerLine]


class ClientItem(BaseModel):
    client_id: str
    display_name: str
    email_masked: str
    phone_masked: str
    created_at: str
    face_enrolled: bool
    locked: bool
    balance_cents: int
    operations_count: int


class ClientPage(BaseModel):
    items: list[ClientItem]
    page: int
    size: int
    total: int


class ClientDetail(ClientItem):
    failed_logins: int
    active_sessions: int
    pending_requests: int
    payout_accounts: list[PayoutAccount]
    recent_transactions: list[TransactionItem]


class RequestItem(BaseModel):
    reference: str
    amount_cents: int
    currency: str
    status: str
    failure_reason: str | None
    requester: Party
    payer: Party | None
    transaction_reference: str | None
    description: str | None
    created_at: str
    expires_at: str


class RequestPage(BaseModel):
    items: list[RequestItem]
    page: int
    size: int
    total: int
