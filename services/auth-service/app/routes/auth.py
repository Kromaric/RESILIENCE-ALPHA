import logging
import uuid
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy import case, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session, utcnow
from app.face.decision import decide, main_face, random_direction
from app.face.service import analyze_frames, count_templates, decode_frames, load_templates
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
from app.models import Client, ClientApi, Session
from app.schemas import (
    ErrorOut,
    FaceChallenge,
    FaceLoginRequest,
    LoginRequest,
    LoginResponse,
    MeResponse,
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
SECOND_FACTOR_FAILED = error(
    "second_factor_failed", "Visage non reconnu. Recommencez la connexion."
)
LIVENESS_FAILED = error(
    "liveness_failed",
    "Mouvement de la tête non détecté dans le sens demandé. Recommencez la connexion.",
)
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


async def register_failure(
    session: AsyncSession, account_id: str, request: Request, model: type = Client
) -> None:
    """Compte un échec ; au seuil, bloque le compte (client ou opérateur)."""
    settings = request.app.state.settings
    reaches_threshold = model.failed_logins + 1 >= settings.lockout_threshold
    lock_until = utcnow() + timedelta(minutes=settings.lockout_minutes)
    # Une seule requête atomique. locked_until est assigné avant failed_logins :
    # MariaDB évalue les affectations de gauche à droite.
    await session.execute(
        update(model)
        .where(model.id == account_id)
        .ordered_values(
            (model.locked_until, case((reaches_threshold, lock_until), else_=model.locked_until)),
            (model.failed_logins, case((reaches_threshold, 0), else_=model.failed_logins + 1)),
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
    """Crée un compte client. Ensuite : `POST /login`, puis `POST /face/enroll` (visage).

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

    # Exception documentée : un service (la sonde) se connecte sans reconnaissance faciale,
    # mais uniquement sur les comptes de la sonde
    if api.type == "service" and not client.is_probe:
        log_event(logger, "login_refused", reason="service_on_regular_account", client_id=client.id)
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=CLIENT_NOT_ALLOWED)

    enrolled = await count_templates(db, client.id)
    if api.type == "service" or not enrolled:
        # Connexion complète dès le mot de passe : le compteur d'échecs repart à zéro. Avec un
        # visage enregistré, il n'est remis à zéro qu'après le visage (sinon, un mot de passe
        # connu permettrait de retenter le visage indéfiniment).
        if client.failed_logins or client.locked_until:
            await db.execute(
                update(Client)
                .where(Client.id == client.id)
                .values(failed_logins=0, locked_until=None)
            )
            await db.commit()
        session = await open_session(
            db, client, api, status_="active", factors=["pwd"], ttl_seconds=state.tokens.ttl, ip=ip
        )
        LOGINS.inc()
        log_event(logger, "login_succeeded", client_id=client.id, factors="pwd", client_ip=ip)
        return LoginResponse(
            mfa_required=False,
            session_id=session.id,
            token=token_for(request, client, session, api),
            face_enrollment_required=api.type != "service",
        )

    direction = random_direction()
    session = await open_session(
        db,
        client,
        api,
        status_="pending_2fa",
        factors=["pwd"],
        ttl_seconds=settings.pending_2fa_seconds,
        ip=ip,
        challenge=direction,
    )
    log_event(logger, "second_factor_requested", client_id=client.id, client_ip=ip)
    return LoginResponse(
        mfa_required=True,
        session_id=session.id,
        face_challenge=FaceChallenge(direction=direction, frames=settings.login_frames),
    )


@router.post(
    "/login/face",
    response_model=TokenResponse,
    tags=["Authentification"],
    summary="Se connecter — étape 2 : reconnaissance faciale",
    responses={
        401: {
            "model": ErrorOut,
            "description": "Visage non reconnu, test du vivant échoué ou session expirée",
        },
        422: {"model": ErrorOut, "description": "Images invalides"},
        429: {"model": ErrorOut, "description": "Trop de tentatives depuis cette IP"},
        503: {"model": ErrorOut, "description": "Reconnaissance faciale indisponible"},
    },
)
async def login_face(
    body: FaceLoginRequest, request: Request, db: AsyncSession = Depends(get_session)
) -> TokenResponse:
    """Images filmées pendant que la tête tourne dans le sens indiqué par `face_challenge`.

    Un échec clôt la tentative (il faut recommencer `POST /login`, avec une nouvelle consigne)
    et compte dans le blocage du compte, comme un mauvais mot de passe.
    """
    state = request.app.state
    settings = state.settings
    ip = client_ip(request)
    rate_limit(request, ip)

    session = await db.get(Session, body.session_id)
    if (
        session is None
        or session.status != "pending_2fa"
        or not session.challenge
        or session.expires_at <= utcnow()
    ):
        SECOND_FACTOR.labels(result="no_pending_session").inc()
        raise unauthorized(SECOND_FACTOR_FAILED)

    frames = decode_frames(
        body.frames, max_frames=settings.login_max_frames, max_bytes=settings.frame_max_bytes
    )
    templates = await load_templates(
        db, state.face_cipher, session.client_id, state.face_engine.model_name
    )
    per_frame = await analyze_frames(state.face_engine, frames)
    decision = decide(
        [main_face(faces) for faces in per_frame],
        templates,
        direction=session.challenge,
        threshold=settings.face_threshold,
        min_matching_frames=settings.face_min_matching_frames,
        min_turn_degrees=settings.liveness_min_turn_degrees,
        left_is_positive_yaw=settings.liveness_left_is_positive_yaw,
    )
    log_fields = {
        "client_id": session.client_id,
        "session_id": session.id,
        "best_score": decision.best_score,
        "matching_frames": decision.matching_frames,
        "faces_seen": decision.faces_seen,
        "head_turn": decision.head_turn,
        "client_ip": ip,
    }

    if not decision.recognized:
        # La tentative est close : une nouvelle connexion tire une nouvelle consigne
        await db.execute(
            update(Session)
            .where(Session.id == session.id, Session.status == "pending_2fa")
            .values(
                status="revoked",
                challenge=None,
                revoked_at=utcnow(),
                revocation_reason=decision.reason,
            )
        )
        await db.commit()
        await register_failure(db, session.client_id, request)
        SECOND_FACTOR.labels(result=decision.reason).inc()
        log_event(logger, "second_factor_failed", reason=decision.reason, **log_fields)
        # Le motif « test du vivant » ne dépend pas de l'identité : il peut être affiché
        detail = LIVENESS_FAILED if decision.reason == "liveness_failed" else SECOND_FACTOR_FAILED
        raise unauthorized(detail)

    activated = await db.execute(
        update(Session)
        .where(
            Session.id == session.id,
            Session.status == "pending_2fa",
            Session.challenge == session.challenge,
        )
        .values(
            status="active",
            factors="pwd,face",
            face_template_id=decision.template_id,
            face_score=decision.best_score,
            challenge=None,
            expires_at=utcnow() + timedelta(seconds=state.tokens.ttl),
        )
    )
    if activated.rowcount != 1:
        await db.rollback()
        SECOND_FACTOR.labels(result="no_pending_session").inc()
        raise unauthorized(SECOND_FACTOR_FAILED)
    await db.execute(
        update(Client)
        .where(Client.id == session.client_id)
        .values(failed_logins=0, locked_until=None)
    )
    await db.commit()
    await db.refresh(session)

    client = await db.get(Client, session.client_id)
    api = await db.get(ClientApi, session.client_api_id)
    SECOND_FACTOR.labels(result="recognized").inc()
    LOGINS.inc()
    log_event(logger, "login_succeeded", factors="pwd,face", **log_fields)
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
    return MeResponse(
        client_id=client.id,
        email=client.email,
        phone_masked=mask_phone(client.phone),
        display_name=client.display_name,
        factors=session.factor_list,
        face_enrolled=await count_templates(db, client.id) > 0,
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
