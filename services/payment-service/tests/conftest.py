"""Fixtures de test : SQLite en mémoire à la place de MariaDB, JWT signés par une clé de test.

L'application est créée une seule fois (registre Prometheus global) ; la base, le limiteur
et l'autorisation simulée sont remis à zéro avant chaque test.
"""

import time
import uuid
from datetime import timedelta

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.db import utcnow
from app.main import create_app
from app.models import (
    Base,
    Client,
    Contact,
    LedgerAccount,
    LedgerEntry,
    PaymentRequest,
    PayoutAccount,
    Session,
    Transaction,
)
from app.payments import SimulatedAuthorizer
from app.ratelimit import SlidingWindowLimiter
from app.security import SessionGuard

OK_CARD = {
    "number": "4242 4242 4242 4242",
    "exp_month": 12,
    "exp_year": 2030,
    "cvc": "123",
    "holder": "Camille Test",
}
CARD_ACCOUNT = "00000000-0000-0000-0000-00000000c001"
PAYOUT_ACCOUNT = "00000000-0000-0000-0000-00000000c002"
# IBAN fictifs valides (clé mod 97 correcte)
IBAN_A = "FR76 3000 6000 0112 3456 7890 189"
IBAN_B = "DE89 3704 0044 0532 0130 00"


@pytest.fixture(scope="session")
def private_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="session")
def settings(tmp_path_factory, private_key):
    key_file = tmp_path_factory.mktemp("secrets") / "jwt_public_key.pem"
    key_file.write_bytes(
        private_key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
    )
    return Settings(
        database_url="sqlite+aiosqlite://",
        jwt_public_key_file=key_file,
        authorization_min_ms=0,
        authorization_max_ms=0,
        # La tâche de fond partagerait l'unique connexion SQLite des tests : la réconciliation
        # est testée directement (test_consistency_health.py)
        reconcile_enabled=False,
    )


@pytest.fixture(scope="session")
def app(settings):
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    return create_app(settings, engine=engine)


async def _create_schema(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def _reset(engine):
    async with engine.begin() as conn:
        for model in (
            LedgerEntry,
            PaymentRequest,
            Transaction,
            Contact,
            PayoutAccount,
            LedgerAccount,
            Session,
            Client,
        ):
            await conn.execute(delete(model))
        await conn.execute(
            LedgerAccount.__table__.insert(),
            [
                {
                    "id": CARD_ACCOUNT,
                    "type": "counterpart",
                    "code": "card_settlement",
                    "label": "Encaissements carte",
                    "balance_cents": 0,
                },
                {
                    "id": PAYOUT_ACCOUNT,
                    "type": "counterpart",
                    "code": "payouts",
                    "label": "Retraits",
                    "balance_cents": 0,
                },
            ],
        )


@pytest.fixture(scope="session")
def client(app):
    with TestClient(app) as test_client:
        test_client.portal.call(_create_schema, app.state.engine)
        yield test_client


@pytest.fixture(autouse=True)
def clean_state(client, app, settings):
    client.portal.call(_reset, app.state.engine)
    app.state.pay_limiter = SlidingWindowLimiter(settings.pay_rate_per_client)
    app.state.authorizer = SimulatedAuthorizer(0, 0)
    # Pas de cache en test : une révocation est vue immédiatement
    app.state.sessions = SessionGuard(app.state.sessionmaker, ttl_seconds=0)


@pytest.fixture
def db(client, app):
    """Accès direct à la base depuis les tests synchrones."""

    class Db:
        def add(self, *objects):
            async def _add():
                async with app.state.sessionmaker() as session:
                    session.add_all(objects)
                    await session.commit()

            client.portal.call(_add)
            return objects[0] if len(objects) == 1 else objects

        def get(self, model, key):
            async def _get():
                async with app.state.sessionmaker() as session:
                    return await session.get(model, key)

            return client.portal.call(_get)

        def run(self, fn, *args):
            async def _run():
                async with app.state.sessionmaker() as session:
                    result = await fn(session, *args)
                    await session.commit()
                    return result

            return client.portal.call(_run)

        def call(self, coro_fn, *args):
            return client.portal.call(coro_fn, *args)

        def balance(self, client_row):
            async def _balance(session):
                account = (
                    await session.execute(
                        select(LedgerAccount).where(LedgerAccount.client_id == client_row.id)
                    )
                ).scalar_one_or_none()
                return account.balance_cents if account else 0

            return self.run(_balance)

        def count(self, model, *conditions):
            async def _count(session):
                return await session.scalar(
                    select(func.count()).select_from(model).where(*conditions)
                )

            return self.run(_count)

    return Db()


def _open_session(db, client_row, factors="pwd,face", client_api="orbe-web", status="active"):
    return db.add(
        Session(
            id=str(uuid.uuid4()),
            client_id=client_row.id,
            client_api_id=client_api,
            status=status,
            factors=factors,
            expires_at=utcnow() + timedelta(minutes=15),
        )
    )


@pytest.fixture
def fund(db):
    """Crédite le compte Orbe d'un client par un vrai paiement fictif (écritures comprises)."""
    state = {}

    def _fund(client_row, amount):
        if "funder" not in state:
            funder = db.add(
                Client(
                    id=str(uuid.uuid4()),
                    email="funder@orbe.test",
                    phone="+33600000000",
                    display_name="Alimentation de test",
                )
            )
            state["funder"] = funder
            state["session"] = _open_session(db, funder)

        async def _credit(session):
            account = (
                await session.execute(
                    select(LedgerAccount).where(LedgerAccount.client_id == client_row.id)
                )
            ).scalar_one_or_none()
            if account is None:
                account = LedgerAccount(
                    id=str(uuid.uuid4()),
                    type="client",
                    label="Compte Orbe",
                    client_id=client_row.id,
                    balance_cents=0,
                )
                session.add(account)
                await session.flush()
            tx = Transaction(
                id=str(uuid.uuid4()),
                reference=f"tx_{uuid.uuid4().hex[:8]}",
                type="payment",
                session_id=state["session"].id,
                payer_id=state["funder"].id,
                recipient_id=client_row.id,
                amount_cents=amount,
                currency="EUR",
                card_brand="visa",
                card_last4="4242",
                status="authorized",
                idempotency_key=str(uuid.uuid4()),
                request_hash="0" * 64,
            )
            session.add(tx)
            await session.flush()
            session.add_all(
                [
                    LedgerEntry(
                        transaction_id=tx.id,
                        account_id=CARD_ACCOUNT,
                        direction="debit",
                        amount_cents=amount,
                    ),
                    LedgerEntry(
                        transaction_id=tx.id,
                        account_id=account.id,
                        direction="credit",
                        amount_cents=amount,
                    ),
                ]
            )
            await session.execute(
                update(LedgerAccount)
                .where(LedgerAccount.id == CARD_ACCOUNT)
                .values(balance_cents=LedgerAccount.balance_cents - amount)
            )
            await session.execute(
                update(LedgerAccount)
                .where(LedgerAccount.id == account.id)
                .values(balance_cents=LedgerAccount.balance_cents + amount)
            )

        db.run(_credit)

    return _fund


@pytest.fixture
def add_client(db, fund):
    counter = iter(range(10, 100))

    def _add(name="Camille Test", *, balance=0, payout=True, **fields):
        n = next(counter)
        created = Client(
            id=str(uuid.uuid4()),
            email=fields.pop("email", f"client{n}@orbe.test"),
            phone=fields.pop("phone", f"+336123456{n}"),
            display_name=name,
            **fields,
        )
        db.add(created)
        if payout:
            db.add(
                PayoutAccount(
                    id=str(uuid.uuid4()),
                    client_id=created.id,
                    label="Banque Démo",
                    iban_last4="0142",
                    is_default=True,
                )
            )
        if balance:
            fund(created, balance)
        return created

    return _add


@pytest.fixture
def auth(private_key, db):
    """En-têtes d'un client authentifié : session ouverte en base + JWT signé comme le ferait
    auth-service. Par défaut, session confirmée par le visage."""

    def _auth(
        client_row,
        *,
        key=None,
        ttl=900,
        factors=("pwd", "face"),
        client_api="orbe-web",
        client_type="application",
        session=None,
    ):
        session = session or _open_session(db, client_row, ",".join(factors), client_api)
        now = int(time.time())
        token = jwt.encode(
            {
                "sub": client_row.id,
                "email": client_row.email,
                "iss": "orbe-auth",
                "aud": "orbe",
                "iat": now,
                "exp": now + ttl,
                "jti": session.id,
                "amr": list(factors),
                "cid": client_api,
                "cty": client_type,
            },
            private_key,
            algorithm="RS256",
        )
        return {"Authorization": f"Bearer {token}", "Idempotency-Key": key or str(uuid.uuid4())}

    return _auth


@pytest.fixture
def pay(client, auth):
    def _pay(
        payer, recipient=None, *, to=None, amount=1250, card=None, key=None, headers=None, **body
    ):
        """Paie `recipient` (par son email) ou le contact brut `to`."""
        payload = {"amount_cents": amount, "card": card or OK_CARD, **body}
        if to is not None:
            payload["recipient"] = to
        elif recipient is not None:
            payload["recipient"] = recipient.email
        return client.post("/pay", json=payload, headers=headers or auth(payer, key=key))

    return _pay
