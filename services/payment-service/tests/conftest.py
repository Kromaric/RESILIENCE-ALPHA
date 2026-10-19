"""Fixtures de test : SQLite en mémoire à la place de MariaDB, JWT signés par une clé de test.

L'application est créée une seule fois (registre Prometheus global) ; la base, le limiteur
et l'autorisation simulée sont remis à zéro avant chaque test.
"""

import time
import uuid

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.main import create_app
from app.models import Base, Client, PaymentRequest, PayoutAccount, Transaction
from app.payments import SimulatedAuthorizer
from app.ratelimit import SlidingWindowLimiter

OK_CARD = {
    "number": "4242 4242 4242 4242",
    "exp_month": 12,
    "exp_year": 2030,
    "cvc": "123",
    "holder": "Camille Test",
}


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
        for model in (PaymentRequest, Transaction, PayoutAccount, Client):
            await conn.execute(delete(model))


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

    return Db()


@pytest.fixture
def add_client(db):
    counter = iter(range(10, 100))

    def _add(name="Camille Test", *, balance=0, payout=True, **fields):
        n = next(counter)
        created = Client(
            id=str(uuid.uuid4()),
            email=fields.pop("email", f"client{n}@orbe.test"),
            phone=fields.pop("phone", f"+336123456{n}"),
            display_name=name,
            balance_cents=balance,
            **fields,
        )
        db.add(created)
        if payout:
            db.add(PayoutAccount(client_id=created.id, label="Banque Démo", iban_last4="0142"))
        return created

    return _add


@pytest.fixture
def auth(private_key):
    """En-têtes d'un client authentifié (JWT signé comme le ferait auth-service)."""

    def _auth(client, *, key=None, ttl=900):
        now = int(time.time())
        token = jwt.encode(
            {
                "sub": client.id,
                "email": client.email,
                "iss": "orbe-auth",
                "aud": "orbe",
                "iat": now,
                "exp": now + ttl,
            },
            private_key,
            algorithm="RS256",
        )
        headers = {"Authorization": f"Bearer {token}"}
        headers["Idempotency-Key"] = key or str(uuid.uuid4())
        return headers

    return _auth


@pytest.fixture
def pay(client, auth):
    def _pay(payer, recipient=None, *, to=None, amount=1250, card=None, key=None, **body):
        """Paie `recipient` (par son email) ou le contact brut `to`."""
        payload = {"amount_cents": amount, "card": card or OK_CARD, **body}
        if to is not None:
            payload["recipient"] = to
        elif recipient is not None:
            payload["recipient"] = recipient.email
        return client.post("/pay", json=payload, headers=auth(payer, key=key))

    return _pay
