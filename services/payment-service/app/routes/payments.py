from typing import Literal

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import payment_requests, payments
from app.db import get_session
from app.errors import api_error
from app.schemas import (
    AccountOut,
    ErrorOut,
    PayIn,
    PaymentOut,
    PayoutIn,
    PayoutOut,
    QrOut,
    RefundOut,
    RequestIn,
    RequestList,
    RequestOut,
    RequestPayIn,
    TransactionItem,
    TransactionList,
)
from app.security import current_client_id, idempotency_key

router = APIRouter()

# Réponses d'erreur documentées dans Swagger ; corps commun {"detail": {"code", "message"}}
_ERR = {"model": ErrorOut}
READ = {401: {**_ERR, "description": "Jeton absent, invalide ou expiré"}}
READ404 = {**READ, 404: {**_ERR, "description": "Introuvable pour ce client"}}
MONEY = {
    **READ,
    400: {**_ERR, "description": "Idempotency-Key absente ou invalide"},
    409: {**_ERR, "description": "Idempotency-Key déjà utilisée pour une autre requête"},
    422: {**_ERR, "description": "Données invalides, carte non acceptée, solde insuffisant…"},
    429: {**_ERR, "description": "Trop d'opérations par minute"},
    503: {**_ERR, "description": "Service saturé ou base indisponible (réessayer)"},
}
MONEY404 = {**MONEY, 404: {**_ERR, "description": "Introuvable pour ce client"}}

TransactionStatus = Literal["pending", "authorized", "declined", "failed", "refunded", "completed"]
RequestStatus = Literal["pending", "paid", "declined", "cancelled", "expired", "failed"]


def limit_rate(request: Request, client_id: str) -> None:
    limiter = request.app.state.pay_limiter
    if limiter is not None and not limiter.allow(client_id):
        raise api_error(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "too_many_payments",
            "Trop d'opérations en peu de temps. Réessayez dans une minute.",
            headers={"Retry-After": "60"},
        )


def created(response: Response, is_new: bool) -> None:
    """201 à la création, 200 quand une Idempotency-Key déjà utilisée est rejouée."""
    response.status_code = status.HTTP_201_CREATED if is_new else status.HTTP_200_OK


@router.post(
    "/pay",
    response_model=PaymentOut,
    status_code=201,
    tags=["Paiements"],
    summary="Envoyer de l'argent",
    responses=MONEY,
)
async def pay(
    body: PayIn,
    request: Request,
    response: Response,
    client_id: str = Depends(current_client_id),
    key: str = Depends(idempotency_key),
    session: AsyncSession = Depends(get_session),
) -> PaymentOut:
    limit_rate(request, client_id)
    tx, is_new = await payments.pay(request.app.state, session, client_id, body, key)
    created(response, is_new)
    return payments.payment_out(tx)


@router.get(
    "/transactions",
    response_model=TransactionList,
    tags=["Historique"],
    summary="Lister mes opérations",
    responses=READ,
)
async def list_transactions(
    status_filter: TransactionStatus | None = Query(default=None, alias="status"),
    direction: Literal["sent", "received"] | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = None,
    client_id: str = Depends(current_client_id),
    session: AsyncSession = Depends(get_session),
) -> TransactionList:
    return await payments.list_transactions(
        session, client_id, status=status_filter, direction=direction, limit=limit, cursor=cursor
    )


@router.get(
    "/transactions/{reference}",
    response_model=TransactionItem,
    tags=["Historique"],
    summary="Détail d'une opération",
    responses=READ404,
)
async def get_transaction(
    reference: str,
    client_id: str = Depends(current_client_id),
    session: AsyncSession = Depends(get_session),
) -> TransactionItem:
    return await payments.get_transaction(session, client_id, reference)


@router.post(
    "/transactions/{reference}/refund",
    response_model=RefundOut,
    status_code=201,
    tags=["Paiements"],
    summary="Rembourser un paiement reçu",
    responses=MONEY404,
)
async def refund(
    reference: str,
    response: Response,
    client_id: str = Depends(current_client_id),
    key: str = Depends(idempotency_key),
    session: AsyncSession = Depends(get_session),
) -> RefundOut:
    out, is_new = await payments.refund(session, client_id, reference, key)
    created(response, is_new)
    return out


@router.get(
    "/account",
    response_model=AccountOut,
    tags=["Compte"],
    summary="Solde et compte lié",
    responses=READ,
)
async def account(
    client_id: str = Depends(current_client_id), session: AsyncSession = Depends(get_session)
) -> AccountOut:
    return await payments.account(session, client_id)


@router.post(
    "/payouts",
    response_model=PayoutOut,
    status_code=201,
    tags=["Compte"],
    summary="Retirer vers le compte lié",
    responses=MONEY,
)
async def payout(
    body: PayoutIn,
    request: Request,
    response: Response,
    client_id: str = Depends(current_client_id),
    key: str = Depends(idempotency_key),
    session: AsyncSession = Depends(get_session),
) -> PayoutOut:
    out, is_new = await payments.payout(
        request.app.state, session, client_id, body.amount_cents, key
    )
    created(response, is_new)
    return out


@router.post(
    "/requests",
    response_model=RequestOut,
    status_code=201,
    tags=["Demandes d'argent"],
    summary="Demander de l'argent",
    responses=MONEY,
)
async def create_request(
    body: RequestIn,
    request: Request,
    response: Response,
    client_id: str = Depends(current_client_id),
    key: str = Depends(idempotency_key),
    session: AsyncSession = Depends(get_session),
) -> RequestOut:
    limit_rate(request, client_id)
    out, is_new = await payment_requests.create_request(
        request.app.state, session, client_id, body, key
    )
    created(response, is_new)
    return out


@router.get(
    "/requests",
    response_model=RequestList,
    tags=["Demandes d'argent"],
    summary="Lister mes demandes",
    responses=READ,
)
async def list_requests(
    role: Literal["incoming", "outgoing"] | None = None,
    status_filter: RequestStatus | None = Query(default=None, alias="status"),
    client_id: str = Depends(current_client_id),
    session: AsyncSession = Depends(get_session),
) -> RequestList:
    return await payment_requests.list_requests(session, client_id, role=role, status=status_filter)


@router.post(
    "/requests/{reference}/pay",
    response_model=PaymentOut,
    status_code=201,
    tags=["Demandes d'argent"],
    summary="Payer une demande reçue",
    responses=MONEY404,
)
async def pay_request(
    reference: str,
    body: RequestPayIn,
    request: Request,
    response: Response,
    client_id: str = Depends(current_client_id),
    key: str = Depends(idempotency_key),
    session: AsyncSession = Depends(get_session),
) -> PaymentOut:
    limit_rate(request, client_id)
    tx, is_new = await payment_requests.pay_request(
        request.app.state, session, client_id, reference, body, key
    )
    created(response, is_new)
    return payments.payment_out(tx)


@router.post(
    "/requests/{reference}/decline",
    response_model=RequestOut,
    tags=["Demandes d'argent"],
    summary="Refuser une demande reçue",
    responses=READ404,
)
async def decline_request(
    reference: str,
    client_id: str = Depends(current_client_id),
    session: AsyncSession = Depends(get_session),
) -> RequestOut:
    return await payment_requests.decline_request(session, client_id, reference)


@router.post(
    "/requests/{reference}/cancel",
    response_model=RequestOut,
    tags=["Demandes d'argent"],
    summary="Annuler une demande émise",
    responses=READ404,
)
async def cancel_request(
    reference: str,
    client_id: str = Depends(current_client_id),
    session: AsyncSession = Depends(get_session),
) -> RequestOut:
    return await payment_requests.cancel_request(session, client_id, reference)


@router.get(
    "/qr",
    response_model=QrOut,
    tags=["QR code"],
    summary="Mon QR « Recevoir »",
    responses=READ,
)
async def get_qr(
    client_id: str = Depends(current_client_id), session: AsyncSession = Depends(get_session)
) -> QrOut:
    return await payment_requests.get_qr(session, client_id)


@router.post(
    "/qr/rotate",
    response_model=QrOut,
    tags=["QR code"],
    summary="Renouveler mon QR",
    responses=READ,
)
async def rotate_qr(
    client_id: str = Depends(current_client_id), session: AsyncSession = Depends(get_session)
) -> QrOut:
    return await payment_requests.rotate_qr(session, client_id)
