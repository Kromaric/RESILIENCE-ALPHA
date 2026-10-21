"""Données applicatives pour le back-office (`/bo/data`), lues avec le compte bo_ro.

- Les comptes de la sonde (`is_probe`) sont exclus de tout ce qui concerne les clients et les
  opérations ; le contrôle comptable, lui, porte sur toute la base.
- Email et téléphone des clients sont masqués par la base (vue `bo_clients`) : bo-api ne les
  voit jamais en clair.
- Indicateurs agrégés : rôle `viewer`. Listes et fiches (données personnelles) : rôle
  `operator`, et chaque consultation est journalisée (qui, quoi, quand).
"""

import logging
from collections import Counter
from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import and_, case, false, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from app.db import (
    bo_clients,
    get_db,
    iso_utc,
    ledger_accounts,
    ledger_entries,
    payment_requests,
    payout_accounts,
    sessions,
    transactions,
    utcnow,
)
from app.errors import ErrorOut, error
from app.logging_setup import log_event
from app.schemas import (
    AccountMismatch,
    BalancesSummary,
    Card,
    ClientDetail,
    ClientItem,
    ClientPage,
    ClientsSummary,
    Count,
    EntriesAnomaly,
    LedgerCheck,
    LedgerLine,
    OperationsWindow,
    Party,
    PayoutAccount,
    RequestItem,
    RequestPage,
    RequestsSummary,
    Series,
    SeriesPoint,
    Summary,
    TransactionDetail,
    TransactionItem,
    TransactionPage,
)
from app.security import Operator, require_role

router = APIRouter(prefix="/bo/data", tags=["Données applicatives"])
logger = logging.getLogger("data")

AUTHORIZED = ("authorized", "completed", "refunded")  # paiement qui a déplacé de l'argent
PERSONAL = {
    401: {"model": ErrorOut, "description": "Jeton absent, invalide ou révoqué"},
    403: {"model": ErrorOut, "description": "Réservé au rôle « operator »"},
    503: {"model": ErrorOut, "description": "Base de données indisponible"},
}
AGGREGATED = {k: v for k, v in PERSONAL.items() if k != 403}

real_clients = select(bo_clients.c.id).where(bo_clients.c.is_probe == false())
payer = bo_clients.alias("payer")
recipient = bo_clients.alias("recipient")


def audit(operator: Operator, resource: str, **fields) -> None:
    """Trace de chaque consultation de données personnelles (Loki / SOC)."""
    log_event(
        logger,
        "personal_data_viewed",
        operator_id=operator.operator_id,
        operator_email=operator.email,
        resource=resource,
        **fields,
    )


def page_params(request: Request, page: int, size: int) -> tuple[int, int]:
    return page, min(size, request.app.state.settings.page_size_max)


async def paginate(db: AsyncSession, query: Select, page: int, size: int):
    total = await db.scalar(select(func.count()).select_from(query.order_by(None).subquery()))
    rows = (await db.execute(query.limit(size).offset((page - 1) * size))).mappings().all()
    return total or 0, rows


# --- Opérations : requête commune aux listes et aux fiches ----------------------------------


def transactions_query() -> Select:
    return (
        select(
            transactions,
            payer.c.display_name.label("payer_name"),
            recipient.c.display_name.label("recipient_name"),
        )
        .join(payer, payer.c.id == transactions.c.payer_id)
        .outerjoin(recipient, recipient.c.id == transactions.c.recipient_id)
        .where(payer.c.is_probe == false())
    )


def transaction_item(row) -> dict:
    return {
        "reference": row["reference"],
        "type": row["type"],
        "amount_cents": row["amount_cents"],
        "currency": row["currency"],
        "status": row["status"],
        "decline_reason": row["decline_reason"],
        "card": Card(brand=row["card_brand"], last4=row["card_last4"])
        if row["card_last4"]
        else None,
        "payer": Party(client_id=row["payer_id"], display_name=row["payer_name"]),
        "recipient": Party(client_id=row["recipient_id"], display_name=row["recipient_name"])
        if row["recipient_id"]
        else None,
        "description": row["description"],
        "created_at": iso_utc(row["created_at"]),
    }


# --- Indicateurs (viewer) --------------------------------------------------------------------


async def operations_window(db: AsyncSession, since: datetime) -> OperationsWindow:
    rows = (
        await db.execute(
            select(
                transactions.c.type,
                transactions.c.status,
                transactions.c.decline_reason,
                func.count().label("n"),
                func.coalesce(func.sum(transactions.c.amount_cents), 0).label("amount"),
            )
            .where(transactions.c.created_at >= since, transactions.c.payer_id.in_(real_clients))
            .group_by(transactions.c.type, transactions.c.status, transactions.c.decline_reason)
        )
    ).all()
    by_type: Counter[str] = Counter()
    by_status: Counter[str] = Counter()
    reasons: Counter[str] = Counter()
    amounts: Counter[str] = Counter()
    payments = declined = 0
    for type_, status_, reason, n, amount in rows:
        by_type[type_] += n
        by_status[status_] += n
        if type_ == "payment":
            payments += n
            if status_ in AUTHORIZED:
                amounts["payments"] += amount
            if status_ == "declined":
                declined += n
                reasons[reason or "unknown"] += n
        elif type_ == "refund" and status_ in AUTHORIZED:
            amounts["refunds"] += amount
        elif type_ == "payout" and status_ in AUTHORIZED:
            amounts["payouts"] += amount
    return OperationsWindow(
        count=sum(by_type.values()),
        by_type=dict(by_type),
        by_status=dict(by_status),
        payments_authorized_cents=amounts["payments"],
        refunds_cents=amounts["refunds"],
        payouts_cents=amounts["payouts"],
        decline_rate=round(declined / payments, 4) if payments else 0.0,
        decline_reasons=[Count(key=k, count=v) for k, v in reasons.most_common()],
    )


@router.get(
    "/summary",
    response_model=Summary,
    summary="Indicateurs de l'application",
    responses=AGGREGATED,
)
async def summary(
    _: Operator = Depends(require_role("viewer")), db: AsyncSession = Depends(get_db)
) -> Summary:
    """Clients, opérations des dernières 24 h et 7 jours, demandes d'argent, soldes.
    Hors comptes de la sonde."""
    now = utcnow()
    clients = (
        await db.execute(
            select(
                func.count(),
                func.coalesce(
                    func.sum(
                        case((bo_clients.c.created_at >= now - timedelta(days=7), 1), else_=0)
                    ),
                    0,
                ),
                func.coalesce(func.sum(case((bo_clients.c.face_enrolled, 1), else_=0)), 0),
                func.coalesce(func.sum(case((bo_clients.c.locked_until > now, 1), else_=0)), 0),
            ).where(bo_clients.c.is_probe == false())
        )
    ).one()
    pending, paid_7d = (
        await db.execute(
            select(
                func.coalesce(
                    func.sum(case((payment_requests.c.status == "pending", 1), else_=0)), 0
                ),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                and_(
                                    payment_requests.c.status == "paid",
                                    payment_requests.c.updated_at >= now - timedelta(days=7),
                                ),
                                1,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ),
            ).where(payment_requests.c.requester_id.in_(real_clients))
        )
    ).one()
    clients_total = await db.scalar(
        select(func.coalesce(func.sum(ledger_accounts.c.balance_cents), 0)).where(
            ledger_accounts.c.type == "client", ledger_accounts.c.client_id.in_(real_clients)
        )
    )
    counterparts = (
        await db.execute(
            select(ledger_accounts.c.code, ledger_accounts.c.balance_cents).where(
                ledger_accounts.c.type == "counterpart"
            )
        )
    ).all()
    return Summary(
        generated_at=iso_utc(now),
        clients=ClientsSummary(
            total=clients[0], new_7d=clients[1], face_enrolled=clients[2], locked=clients[3]
        ),
        operations_24h=await operations_window(db, now - timedelta(hours=24)),
        operations_7d=await operations_window(db, now - timedelta(days=7)),
        requests=RequestsSummary(pending=pending, paid_7d=paid_7d),
        balances=BalancesSummary(
            clients_total_cents=clients_total or 0,
            counterparts_cents={code: balance for code, balance in counterparts},
        ),
    )


@router.get(
    "/series",
    response_model=Series,
    summary="Évolution dans le temps",
    responses=AGGREGATED,
)
async def series(
    metric: Literal["transactions", "amount", "declines", "registrations"] = "transactions",
    interval: Literal["hour", "day"] = "hour",
    _: Operator = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
) -> Series:
    """`hour` : 24 dernières heures ; `day` : 30 derniers jours. `amount` = montants des
    paiements autorisés (centimes) ; `declines` = paiements refusés ; `transactions` = toutes
    les opérations ; `registrations` = inscriptions. Hors comptes de la sonde."""
    now = utcnow()
    if interval == "hour":
        current = now.replace(minute=0, second=0, microsecond=0)
        buckets = [current - timedelta(hours=i) for i in range(23, -1, -1)]
    else:
        current = now.replace(hour=0, minute=0, second=0, microsecond=0)
        buckets = [current - timedelta(days=i) for i in range(29, -1, -1)]

    def bucket(value: datetime) -> datetime:
        if interval == "hour":
            return value.replace(minute=0, second=0, microsecond=0)
        return value.replace(hour=0, minute=0, second=0, microsecond=0)

    if metric == "registrations":
        query = select(bo_clients.c.created_at, func.count()).where(
            bo_clients.c.is_probe == false(), bo_clients.c.created_at >= buckets[0]
        )
        rows = (await db.execute(query.group_by(bo_clients.c.created_at))).all()
    else:
        value = func.sum(transactions.c.amount_cents) if metric == "amount" else func.count()
        query = select(transactions.c.created_at, value).where(
            transactions.c.created_at >= buckets[0], transactions.c.payer_id.in_(real_clients)
        )
        if metric == "amount":
            query = query.where(
                transactions.c.type == "payment", transactions.c.status.in_(AUTHORIZED)
            )
        elif metric == "declines":
            query = query.where(
                transactions.c.type == "payment", transactions.c.status == "declined"
            )
        rows = (await db.execute(query.group_by(transactions.c.created_at))).all()

    totals: Counter[datetime] = Counter()
    for created_at, value_ in rows:
        totals[bucket(created_at)] += int(value_ or 0)
    return Series(
        metric=metric,
        interval=interval,
        points=[SeriesPoint(time=iso_utc(b), value=totals[b]) for b in buckets],
    )


@router.get(
    "/ledger/check",
    response_model=LedgerCheck,
    summary="Contrôle de cohérence comptable",
    responses=AGGREGATED,
)
async def ledger_check(
    _: Operator = Depends(require_role("viewer")), db: AsyncSession = Depends(get_db)
) -> LedgerCheck:
    """Partie double : chaque opération a autant de débits que de crédits, chaque solde est
    la somme de ses écritures, aucun client n'est à découvert, une opération autorisée a
    exactement 2 écritures et une opération refusée aucune. Porte sur toute la base."""
    debit = func.sum(
        case((ledger_entries.c.direction == "debit", ledger_entries.c.amount_cents), else_=0)
    )
    credit = func.sum(
        case((ledger_entries.c.direction == "credit", ledger_entries.c.amount_cents), else_=0)
    )
    unbalanced = (
        (
            await db.execute(
                select(transactions.c.reference)
                .join(ledger_entries, ledger_entries.c.transaction_id == transactions.c.id)
                .group_by(transactions.c.id, transactions.c.reference)
                .having(debit != credit)
            )
        )
        .scalars()
        .all()
    )

    computed = (
        select(
            ledger_entries.c.account_id,
            (credit - debit).label("computed"),
        )
        .group_by(ledger_entries.c.account_id)
        .subquery()
    )
    accounts = (
        await db.execute(
            select(
                ledger_accounts.c.id,
                ledger_accounts.c.label,
                ledger_accounts.c.type,
                ledger_accounts.c.balance_cents,
                func.coalesce(computed.c.computed, 0),
            ).outerjoin(computed, computed.c.account_id == ledger_accounts.c.id)
        )
    ).all()
    mismatches = [
        AccountMismatch(
            account_id=id_, label=label, balance_cents=balance, computed_cents=int(value)
        )
        for id_, label, _, balance, value in accounts
        if balance != int(value)
    ]
    negative = sum(1 for _, _, type_, balance, _ in accounts if type_ == "client" and balance < 0)

    entries_count = func.count(ledger_entries.c.id)
    anomalies = (
        await db.execute(
            select(transactions.c.reference, transactions.c.status, entries_count)
            .outerjoin(ledger_entries, ledger_entries.c.transaction_id == transactions.c.id)
            .group_by(transactions.c.id, transactions.c.reference, transactions.c.status)
            .having(
                or_(
                    and_(transactions.c.status.in_(AUTHORIZED), entries_count != 2),
                    and_(transactions.c.status.notin_(AUTHORIZED), entries_count != 0),
                )
            )
        )
    ).all()
    checked = await db.scalar(select(func.count()).select_from(transactions))
    return LedgerCheck(
        ok=not (unbalanced or mismatches or negative or anomalies),
        checked_at=iso_utc(utcnow()),
        transactions_checked=checked or 0,
        accounts_checked=len(accounts),
        unbalanced_transactions=list(unbalanced),
        account_mismatches=mismatches,
        negative_client_balances=negative,
        entries_anomalies=[
            EntriesAnomaly(reference=ref, status=status_, entries=n)
            for ref, status_, n in anomalies
        ],
    )


# --- Listes et fiches (operator, journalisées) ------------------------------------------------


@router.get(
    "/transactions",
    response_model=TransactionPage,
    summary="Opérations",
    responses=PERSONAL,
)
async def list_transactions(
    request: Request,
    type: Literal["payment", "refund", "payout"] | None = None,  # noqa: A002
    status: str | None = Query(default=None, max_length=16),
    client_id: str | None = Query(
        default=None, max_length=36, description="payeur ou bénéficiaire"
    ),
    reference: str | None = Query(default=None, max_length=11),
    date_from: datetime | None = Query(default=None, description="UTC, inclus"),
    date_to: datetime | None = Query(default=None, description="UTC, exclu"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=25, ge=1),
    operator: Operator = Depends(require_role("operator")),
    db: AsyncSession = Depends(get_db),
) -> TransactionPage:
    """Plus récentes d'abord. Hors comptes de la sonde."""
    page, size = page_params(request, page, size)
    query = transactions_query()
    if type:
        query = query.where(transactions.c.type == type)
    if status:
        query = query.where(transactions.c.status == status)
    if client_id:
        query = query.where(
            or_(transactions.c.payer_id == client_id, transactions.c.recipient_id == client_id)
        )
    if reference:
        query = query.where(transactions.c.reference == reference)
    if date_from:
        query = query.where(transactions.c.created_at >= date_from.replace(tzinfo=None))
    if date_to:
        query = query.where(transactions.c.created_at < date_to.replace(tzinfo=None))
    total, rows = await paginate(
        db, query.order_by(transactions.c.created_at.desc(), transactions.c.id), page, size
    )
    audit(operator, "transactions", count=len(rows), client_id=client_id)
    return TransactionPage(
        items=[TransactionItem(**transaction_item(row)) for row in rows],
        page=page,
        size=size,
        total=total,
    )


@router.get(
    "/transactions/{reference}",
    response_model=TransactionDetail,
    summary="Détail d'une opération",
    responses={**PERSONAL, 404: {"model": ErrorOut, "description": "Opération inconnue"}},
)
async def transaction_detail(
    reference: str,
    operator: Operator = Depends(require_role("operator")),
    db: AsyncSession = Depends(get_db),
) -> TransactionDetail:
    """Avec ses écritures comptables, le paiement d'origine ou le remboursement, la demande
    d'argent réglée et le compte lié d'un retrait."""
    row = (
        (await db.execute(transactions_query().where(transactions.c.reference == reference)))
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise HTTPException(404, detail=error("not_found", "Opération inconnue."))

    parent_reference = (
        await db.scalar(
            select(transactions.c.reference).where(transactions.c.id == row["parent_id"])
        )
        if row["parent_id"]
        else None
    )
    refund_reference = await db.scalar(
        select(transactions.c.reference).where(transactions.c.parent_id == row["id"])
    )
    request_reference = await db.scalar(
        select(payment_requests.c.reference).where(payment_requests.c.transaction_id == row["id"])
    )
    payout = None
    if row["payout_account_id"]:
        account = (
            (
                await db.execute(
                    select(payout_accounts).where(payout_accounts.c.id == row["payout_account_id"])
                )
            )
            .mappings()
            .one_or_none()
        )
        if account:
            payout = PayoutAccount(
                label=account["label"],
                iban_last4=account["iban_last4"],
                is_default=account["is_default"],
            )
    entries = (
        await db.execute(
            select(
                ledger_entries.c.direction,
                ledger_entries.c.amount_cents,
                ledger_accounts.c.type,
                ledger_accounts.c.label,
            )
            .join(ledger_accounts, ledger_accounts.c.id == ledger_entries.c.account_id)
            .where(ledger_entries.c.transaction_id == row["id"])
            .order_by(ledger_entries.c.id)
        )
    ).all()
    audit(operator, "transaction", reference=reference)
    return TransactionDetail(
        **transaction_item(row),
        updated_at=iso_utc(row["updated_at"]),
        parent_reference=parent_reference,
        refund_reference=refund_reference,
        request_reference=request_reference,
        payout_account=payout,
        entries=[
            LedgerLine(direction=d, amount_cents=a, account_type=t, account_label=label)
            for d, a, t, label in entries
        ],
    )


def clients_query(now: datetime) -> Select:
    operations = (
        select(func.count())
        .where(
            or_(
                transactions.c.payer_id == bo_clients.c.id,
                transactions.c.recipient_id == bo_clients.c.id,
            )
        )
        .scalar_subquery()
    )
    return (
        select(
            bo_clients,
            func.coalesce(ledger_accounts.c.balance_cents, 0).label("balance_cents"),
            operations.label("operations_count"),
        )
        .outerjoin(
            ledger_accounts,
            and_(
                ledger_accounts.c.client_id == bo_clients.c.id, ledger_accounts.c.type == "client"
            ),
        )
        .where(bo_clients.c.is_probe == false())
    )


def client_item(row, now: datetime) -> dict:
    return {
        "client_id": row["id"],
        "display_name": row["display_name"],
        "email_masked": row["email_masked"],
        "phone_masked": row["phone_masked"],
        "created_at": iso_utc(row["created_at"]),
        "face_enrolled": bool(row["face_enrolled"]),
        "locked": bool(row["locked_until"] and row["locked_until"] > now),
        "balance_cents": row["balance_cents"],
        "operations_count": row["operations_count"],
    }


@router.get(
    "/clients",
    response_model=ClientPage,
    summary="Clients",
    responses=PERSONAL,
)
async def list_clients(
    request: Request,
    q: str | None = Query(default=None, max_length=80, description="nom affiché (contient)"),
    locked: bool | None = None,
    face_enrolled: bool | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=25, ge=1),
    operator: Operator = Depends(require_role("operator")),
    db: AsyncSession = Depends(get_db),
) -> ClientPage:
    """Email et téléphone toujours masqués. Recherche par nom seulement (pas par email ni
    téléphone : on ne pourrait pas s'en servir pour retrouver une valeur masquée). Plus récents
    d'abord, hors comptes de la sonde."""
    page, size = page_params(request, page, size)
    now = utcnow()
    query = clients_query(now)
    if q:
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.where(bo_clients.c.display_name.ilike(f"%{escaped}%", escape="\\"))
    if locked is not None:
        is_locked = and_(bo_clients.c.locked_until.is_not(None), bo_clients.c.locked_until > now)
        query = query.where(is_locked if locked else ~is_locked)
    if face_enrolled is not None:
        query = query.where(bo_clients.c.face_enrolled == face_enrolled)
    total, rows = await paginate(
        db, query.order_by(bo_clients.c.created_at.desc(), bo_clients.c.id), page, size
    )
    audit(operator, "clients", count=len(rows))
    return ClientPage(
        items=[ClientItem(**client_item(row, now)) for row in rows],
        page=page,
        size=size,
        total=total,
    )


@router.get(
    "/clients/{client_id}",
    response_model=ClientDetail,
    summary="Fiche client",
    responses={**PERSONAL, 404: {"model": ErrorOut, "description": "Client inconnu"}},
)
async def client_detail(
    client_id: str,
    operator: Operator = Depends(require_role("operator")),
    db: AsyncSession = Depends(get_db),
) -> ClientDetail:
    """Comptes liés (4 derniers caractères de l'IBAN), sessions actives, demandes en attente
    et 20 dernières opérations."""
    now = utcnow()
    row = (
        (await db.execute(clients_query(now).where(bo_clients.c.id == client_id)))
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise HTTPException(404, detail=error("not_found", "Client inconnu."))

    active_sessions = await db.scalar(
        select(func.count()).where(
            sessions.c.client_id == client_id,
            sessions.c.status == "active",
            sessions.c.expires_at > now,
        )
    )
    pending_requests = await db.scalar(
        select(func.count()).where(
            payment_requests.c.status == "pending",
            or_(
                payment_requests.c.requester_id == client_id,
                payment_requests.c.payer_id == client_id,
            ),
        )
    )
    accounts = (
        (
            await db.execute(
                select(payout_accounts)
                .where(payout_accounts.c.client_id == client_id)
                .order_by(payout_accounts.c.created_at)
            )
        )
        .mappings()
        .all()
    )
    recent = (
        (
            await db.execute(
                transactions_query()
                .where(
                    or_(
                        transactions.c.payer_id == client_id,
                        transactions.c.recipient_id == client_id,
                    )
                )
                .order_by(transactions.c.created_at.desc(), transactions.c.id)
                .limit(20)
            )
        )
        .mappings()
        .all()
    )
    audit(operator, "client", client_id=client_id)
    return ClientDetail(
        **client_item(row, now),
        failed_logins=row["failed_logins"],
        active_sessions=active_sessions or 0,
        pending_requests=pending_requests or 0,
        payout_accounts=[
            PayoutAccount(label=a["label"], iban_last4=a["iban_last4"], is_default=a["is_default"])
            for a in accounts
        ],
        recent_transactions=[TransactionItem(**transaction_item(r)) for r in recent],
    )


@router.get(
    "/requests",
    response_model=RequestPage,
    summary="Demandes d'argent",
    responses=PERSONAL,
)
async def list_requests(
    request: Request,
    status: Literal["pending", "paid", "declined", "cancelled", "expired", "failed"] | None = None,
    client_id: str | None = Query(default=None, max_length=36, description="demandeur ou payeur"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=25, ge=1),
    operator: Operator = Depends(require_role("operator")),
    db: AsyncSession = Depends(get_db),
) -> RequestPage:
    """Plus récentes d'abord, hors comptes de la sonde."""
    page, size = page_params(request, page, size)
    requester = bo_clients.alias("requester")
    req_payer = bo_clients.alias("req_payer")
    settled = transactions.alias("settled")
    query = (
        select(
            payment_requests,
            requester.c.display_name.label("requester_name"),
            req_payer.c.display_name.label("payer_name"),
            settled.c.reference.label("transaction_reference"),
        )
        .join(requester, requester.c.id == payment_requests.c.requester_id)
        .outerjoin(req_payer, req_payer.c.id == payment_requests.c.payer_id)
        .outerjoin(settled, settled.c.id == payment_requests.c.transaction_id)
        .where(requester.c.is_probe == false())
    )
    if status:
        query = query.where(payment_requests.c.status == status)
    if client_id:
        query = query.where(
            or_(
                payment_requests.c.requester_id == client_id,
                payment_requests.c.payer_id == client_id,
            )
        )
    total, rows = await paginate(
        db, query.order_by(payment_requests.c.created_at.desc(), payment_requests.c.id), page, size
    )
    audit(operator, "requests", count=len(rows), client_id=client_id)
    return RequestPage(
        items=[
            RequestItem(
                reference=r["reference"],
                amount_cents=r["amount_cents"],
                currency=r["currency"],
                status=r["status"],
                failure_reason=r["failure_reason"],
                requester=Party(client_id=r["requester_id"], display_name=r["requester_name"]),
                payer=Party(client_id=r["payer_id"], display_name=r["payer_name"])
                if r["payer_id"]
                else None,
                transaction_reference=r["transaction_reference"],
                description=r["description"],
                created_at=iso_utc(r["created_at"]),
                expires_at=iso_utc(r["expires_at"]),
            )
            for r in rows
        ],
        page=page,
        size=size,
        total=total,
    )
