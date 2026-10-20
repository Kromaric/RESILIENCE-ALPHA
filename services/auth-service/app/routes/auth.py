import logging
import uuid
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy import case, func, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import passkeys as webauthn
from app.db import get_session, utcnow
from app.logging_setup import log_event
from app.metrics import (
    ACCOUNT_LOCKS,
    API_KEY_FAILURES,
    LOGIN_FAILURES,
    LOGINS,
    REGISTRATIONS,
    SECOND_FACTOR,
    SESSIONS_REVOKED,
)
from app.models import Client, ClientApi, Passkey, Session
from app.schemas import (
    ErrorOut,
    LoginRequest,
    LoginResponse,
    MeResponse,
    PasskeyLoginRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
    VerifyResponse,
    error,
)
from app.security import (
    hash_api_key,
    mask_phone,
    normalize_email,
    normalize_phone,
    password_problem,
    valid_email,
)
from app.sessions import current_session, open_session, resolve_client_api, token_for, unauthorized

router = APIRouter()
logger = logging.getLogger("auth")

INVALID_CREDENTIALS = error("invalid_credentials", "Email ou mot de passe incorrect.")
SECOND_FACTOR_FAILED = error("second_factor_failed", "Validation de la passkey refusée.")
CLIENT_NOT_ALLOWED = error("client_not_allowed", "Cette application ne peut pas ouvrir de session.")


def client_ip(request: Request) -> str:
    """IP d'origine transmise par le WAF (seul point d'entrée, CADRAGE §4.1)."""
    return request.headers.get("x-real-ip") or (request.client.host if request.client else "-")


def rate_limit(request: Request, ip: str) -> None:
    if not request.app.state.login_limiter.allow(ip):
        LOGIN_FAILURES.labels(reason="rate_limited").inc()
        log_event(logger, "login_failed", reason="rate_limited", client_ip=ip)
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail=error("too_many_attempts", "Trop de tentatives. Réessayez dans une minute."),
            headers={"Retry-After": "60"},
        )


async def register_failure(session: AsyncSession, client_id: str, request: Request) -> None:
    settings = request.app.state.settings
    reaches_threshold = Client.failed_logins + 1 >= settings.lockout_threshold
    lock_until = utcnow() + timedelta(minutes=settings.lockout_minutes)
    # Une seule requête atomique. locked_until est assigné avant failed_logins :
    # MariaDB évalue les affectations de gauche à droite.
    await session.execute(
        update(Client)
        .where(Client.id == client_id)
        .ordered_values(
            (Client.locked_until, case((reaches_threshold, lock_until), else_=Client.locked_until)),
            (Client.failed_logins, case((reaches_threshold, 0), else_=Client.failed_logins + 1)),
        )
    )
    await session.commit()


# Seules ces colonnes sont insérées (droit INSERT par colonne) : is_probe, le blocage et les
# compteurs prennent leur valeur par défaut, une inscription ne peut pas créer de compte de sonde
INSERT_CLIENT = text(
    "INSERT INTO clients (id, email, phone, display_name, password_hash) "
    "VALUES (:id, :email, :phone, :display_name, :password_hash)"
)


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=201,
    tags=["Authentification"],
    summary="Créer un compte",
    responses={
        409: {"model": ErrorOut, "description": "Email ou téléphone déjà utilisé"},
        422: {"model": ErrorOut, "description": "Email, téléphone ou mot de passe invalide"},
        429: {"model": ErrorOut, "description": "Trop d'inscriptions depuis cette IP"},
    },
)
async def register(
    body: RegisterRequest, request: Request, db: AsyncSession = Depends(get_session)
) -> RegisterResponse:
    """Crée un compte client. Étape suivante : `POST /login`, puis enregistrer une passkey.

    Hors périmètre du démonstrateur : vérification de l'email et du téléphone, KYC.
    """
    state = request.app.state
    ip = client_ip(request)
    if not state.register_limiter.allow(ip):
        REGISTRATIONS.labels(result="rate_limited").inc()
        log_event(logger, "registration_refused", reason="rate_limited", client_ip=ip)
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail=error("too_many_attempts", "Trop d'inscriptions. Réessayez dans une minute."),
            headers={"Retry-After": "60"},
        )

    email = normalize_email(body.email)
    phone = normalize_phone(body.phone)
    display_name = " ".join(body.display_name.split())
    if not valid_email(email):
        raise HTTPException(422, detail=error("invalid_email", "Adresse email invalide."))
    if phone is None:
        raise HTTPException(422, detail=error("invalid_phone", "Numéro de téléphone invalide."))
    if len(display_name) < 2:
        raise HTTPException(422, detail=error("invalid_display_name", "Nom trop court."))
    problem = password_problem(body.password, email)
    if problem:
        REGISTRATIONS.labels(result="weak_password").inc()
        raise HTTPException(422, detail=error("weak_password", problem))

    # Révèle qu'un compte existe : compromis assumé, freiné par la limitation de débit
    if await db.scalar(select(Client.id).where(Client.email == email)):
        REGISTRATIONS.labels(result="duplicate").inc()
        raise HTTPException(
            409, detail=error("email_taken", "Cette adresse email est déjà utilisée.")
        )
    if await db.scalar(select(Client.id).where(Client.phone == phone)):
        REGISTRATIONS.labels(result="duplicate").inc()
        raise HTTPException(409, detail=error("phone_taken", "Ce numéro est déjà utilisé."))

    client_id = str(uuid.uuid4())
    password_hash = await state.passwords.hash_async(body.password)
    try:
        await db.execute(
            INSERT_CLIENT,
            {
                "id": client_id,
                "email": email,
                "phone": phone,
                "display_name": display_name,
                "password_hash": password_hash,
            },
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()  # inscription simultanée avec le même email ou téléphone
        REGISTRATIONS.labels(result="duplicate").inc()
        raise HTTPException(
            409, detail=error("account_exists", "Un compte existe déjà avec ces informations.")
        ) from None

    REGISTRATIONS.labels(result="created").inc()
    log_event(logger, "account_registered", client_id=client_id, client_ip=ip)
    return RegisterResponse(
        client_id=client_id, email=email, phone_masked=mask_phone(phone), display_name=display_name
    )


@router.post(
    "/login",
    response_model=LoginResponse,
    tags=["Authentification"],
    summary="Se connecter — étape 1 : mot de passe",
    responses={
        401: {"model": ErrorOut, "description": "Identifiants ou application cliente invalides"},
        403: {"model": ErrorOut, "description": "Application non autorisée pour ce compte"},
        423: {"model": ErrorOut, "description": "Compte bloqué (en-tête Retry-After)"},
        429: {"model": ErrorOut, "description": "Trop de tentatives depuis cette IP"},
    },
)
async def login(
    body: LoginRequest,
    request: Request,
    x_client_id: str | None = Header(default=None, alias="X-Client-Id"),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_session),
) -> LoginResponse:
    state = request.app.state
    settings = state.settings
    ip = client_ip(request)
    rate_limit(request, ip)
    api = await resolve_client_api(db, x_client_id or settings.web_client_id, x_api_key)
    if api.type == "partner":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=CLIENT_NOT_ALLOWED)

    email = normalize_email(body.email)
    client = (await db.execute(select(Client).where(Client.email == email))).scalar_one_or_none()

    now = utcnow()
    if client and client.locked_until and client.locked_until > now:
        retry_after = int((client.locked_until - now).total_seconds()) + 1
        LOGIN_FAILURES.labels(reason="locked").inc()
        log_event(logger, "login_failed", reason="locked", client_id=client.id, client_ip=ip)
        raise HTTPException(
            status.HTTP_423_LOCKED,
            detail=error("account_locked", "Compte bloqué temporairement après trop d'échecs."),
            headers={"Retry-After": str(retry_after)},
        )

    if not await state.passwords.verify(client.password_hash if client else None, body.password):
        if client:
            will_lock = client.failed_logins + 1 >= settings.lockout_threshold
            await register_failure(db, client.id, request)
            if will_lock:
                ACCOUNT_LOCKS.inc()
                log_event(logger, "account_locked", client_id=client.id, client_ip=ip)
        LOGIN_FAILURES.labels(reason="invalid_credentials").inc()
        log_event(
            logger,
            "login_failed",
            reason="invalid_credentials",
            client_id=client.id if client else None,
            client_ip=ip,
        )
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail=INVALID_CREDENTIALS)

    # Exception documentée : un service (la sonde) se connecte sans passkey, mais
    # uniquement sur les comptes de la sonde
    if api.type == "service" and not client.is_probe:
        log_event(logger, "login_refused", reason="service_on_regular_account", client_id=client.id)
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=CLIENT_NOT_ALLOWED)

    if client.failed_logins or client.locked_until:
        await db.execute(
            update(Client).where(Client.id == client.id).values(failed_logins=0, locked_until=None)
        )
        await db.commit()

    registered = (
        (await db.execute(select(Passkey).where(Passkey.client_id == client.id))).scalars().all()
    )
    if api.type == "service" or not registered:
        session = await open_session(
            db, client, api, status_="active", factors=["pwd"], ttl_seconds=state.tokens.ttl, ip=ip
        )
        LOGINS.inc()
        log_event(logger, "login_succeeded", client_id=client.id, factors="pwd", client_ip=ip)
        return LoginResponse(
            mfa_required=False,
            session_id=session.id,
            token=token_for(request, client, session, api),
            passkey_enrollment_required=api.type != "service",
        )

    challenge = webauthn.login_challenge(settings, list(registered))
    session = await open_session(
        db,
        client,
        api,
        status_="pending_2fa",
        factors=["pwd"],
        ttl_seconds=settings.pending_2fa_seconds,
        ip=ip,
        challenge=challenge.challenge,
    )
    log_event(logger, "second_factor_requested", client_id=client.id, client_ip=ip)
    return LoginResponse(
        mfa_required=True, session_id=session.id, webauthn_options=challenge.options
    )


@router.post(
    "/login/passkey",
    response_model=TokenResponse,
    tags=["Authentification"],
    summary="Se connecter — étape 2 : passkey (Face ID, Windows Hello)",
    responses={
        401: {"model": ErrorOut, "description": "Passkey refusée ou session expirée"},
        429: {"model": ErrorOut, "description": "Trop de tentatives depuis cette IP"},
    },
)
async def login_passkey(
    body: PasskeyLoginRequest, request: Request, db: AsyncSession = Depends(get_session)
) -> TokenResponse:
    settings = request.app.state.settings
    ip = client_ip(request)
    rate_limit(request, ip)

    def refuse(reason: str) -> HTTPException:
        SECOND_FACTOR.labels(result="failed").inc()
        log_event(
            logger, "second_factor_failed", reason=reason, session_id=body.session_id, client_ip=ip
        )
        return unauthorized(SECOND_FACTOR_FAILED)

    session = await db.get(Session, body.session_id)
    if (
        session is None
        or session.status != "pending_2fa"
        or session.challenge_purpose != "login"
        or not session.webauthn_challenge
        or session.expires_at <= utcnow()
    ):
        raise refuse("no_pending_session")

    try:
        credential_id = webauthn.credential_id_of(body.credential)
    except webauthn.PasskeyError:
        raise refuse("malformed_credential") from None
    passkey = (
        await db.execute(
            select(Passkey).where(
                Passkey.credential_id == credential_id, Passkey.client_id == session.client_id
            )
        )
    ).scalar_one_or_none()
    if passkey is None:
        raise refuse("unknown_passkey")
    try:
        new_count = webauthn.verify_login(
            settings, body.credential, session.webauthn_challenge, passkey
        )
    except webauthn.PasskeyError as exc:
        raise refuse(str(exc)[:120]) from None

    # Défi à usage unique : seule la première réponse valide active la session
    activated = await db.execute(
        update(Session)
        .where(
            Session.id == session.id,
            Session.status == "pending_2fa",
            Session.webauthn_challenge == session.webauthn_challenge,
        )
        .values(
            status="active",
            factors="pwd,passkey",
            passkey_id=passkey.id,
            webauthn_challenge=None,
            challenge_purpose=None,
            expires_at=utcnow() + timedelta(seconds=request.app.state.tokens.ttl),
        )
    )
    if activated.rowcount != 1:
        await db.rollback()
        raise refuse("challenge_already_used")
    await db.execute(
        update(Passkey)
        .where(Passkey.id == passkey.id)
        .values(sign_count=new_count, last_used_at=utcnow())
    )
    await db.commit()
    await db.refresh(session)

    client = await db.get(Client, session.client_id)
    api = await db.get(ClientApi, session.client_api_id)
    SECOND_FACTOR.labels(result="succeeded").inc()
    LOGINS.inc()
    log_event(logger, "login_succeeded", client_id=client.id, factors="pwd,passkey", client_ip=ip)
    return token_for(request, client, session, api)


@router.post(
    "/logout",
    status_code=204,
    tags=["Authentification"],
    summary="Se déconnecter (révoque la session)",
    responses={401: {"model": ErrorOut, "description": "Session invalide ou expirée"}},
)
async def logout(
    current: tuple[dict[str, Any], Session] = Depends(current_session),
    db: AsyncSession = Depends(get_session),
) -> Response:
    _, session = current
    await db.execute(
        update(Session)
        .where(Session.id == session.id)
        .values(status="revoked", revoked_at=utcnow(), revocation_reason="logout")
    )
    await db.commit()
    SESSIONS_REVOKED.labels(reason="logout").inc()
    log_event(logger, "session_revoked", reason="logout", session_id=session.id)
    return Response(status_code=204)


@router.get(
    "/me",
    response_model=MeResponse,
    tags=["Authentification"],
    summary="Mon profil",
    responses={401: {"model": ErrorOut, "description": "Jeton absent, invalide ou expiré"}},
)
async def me(
    current: tuple[dict[str, Any], Session] = Depends(current_session),
    db: AsyncSession = Depends(get_session),
) -> MeResponse:
    claims, session = current
    client = await db.get(Client, claims["sub"])
    if client is None:
        raise unauthorized()
    count = await db.scalar(
        select(func.count()).select_from(Passkey).where(Passkey.client_id == client.id)
    )
    return MeResponse(
        client_id=client.id,
        email=client.email,
        phone_masked=mask_phone(client.phone),
        display_name=client.display_name,
        factors=session.factor_list,
        passkey_count=count,
    )


@router.get(
    "/verify",
    response_model=VerifyResponse,
    tags=["Partenaires"],
    summary="Vérifier une clé d'API partenaire",
    responses={401: {"model": ErrorOut, "description": "Clé absente, inconnue ou désactivée"}},
)
async def verify_api_key(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_session),
) -> VerifyResponse:
    api = None
    if x_api_key:
        api = (
            await db.execute(
                select(ClientApi).where(
                    ClientApi.key_hash == hash_api_key(x_api_key), ClientApi.active.is_(True)
                )
            )
        ).scalar_one_or_none()
    if api is None:
        API_KEY_FAILURES.inc()
        log_event(logger, "api_key_rejected", client_ip=client_ip(request))
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail=error("invalid_api_key", "Clé d'API invalide.")
        )
    return VerifyResponse(partner=api.name, scopes=api.scopes)
