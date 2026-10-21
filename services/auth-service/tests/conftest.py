"""Fixtures de test : SQLite en mémoire à la place de MariaDB, clé RSA générée à la volée.

L'application est créée une seule fois (registre Prometheus global) ; la base et le
limiteur sont remis à zéro avant chaque test.
"""

import base64
import uuid

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.face.engine import fake_frame
from app.main import create_app
from app.models import Base, Client, ClientApi, ClientFaceTemplate, Session
from app.ratelimit import SlidingWindowLimiter

PASSWORD = "demo-password"


@pytest.fixture(scope="session")
def private_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="session")
def settings(tmp_path_factory, private_key):
    secrets_dir = tmp_path_factory.mktemp("secrets")
    face_key = secrets_dir / "face_embedding_key"
    face_key.write_text("11" * 32)
    key_file = secrets_dir / "jwt_private_key.pem"
    key_file.write_bytes(
        private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    return Settings(
        database_url="sqlite+aiosqlite://",
        jwt_private_key_file=key_file,
        face_engine="fake",
        face_key_file=face_key,
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
        for model in (Session, ClientFaceTemplate, ClientApi, Client):
            await conn.execute(delete(model))
        await conn.execute(
            ClientApi.__table__.insert().values(
                id="orbe-web",
                name="Application Orbe (web)",
                type="application",
                scopes=["payments"],
            )
        )


@pytest.fixture(scope="session")
def client(app):
    with TestClient(app) as test_client:
        test_client.portal.call(_create_schema, app.state.engine)
        yield test_client


@pytest.fixture(autouse=True)
def clean_state(client, app):
    client.portal.call(_reset, app.state.engine)
    app.state.login_limiter = SlidingWindowLimiter(app.state.settings.login_rate_per_ip)
    app.state.register_limiter = SlidingWindowLimiter(app.state.settings.register_rate_per_ip)


@pytest.fixture
def db(client, app):
    """Accès direct à la base depuis les tests synchrones."""

    class Db:
        def add(self, obj):
            async def _add():
                async with app.state.sessionmaker() as session:
                    session.add(obj)
                    await session.commit()

            client.portal.call(_add)
            return obj

        def get(self, model, key):
            async def _get():
                async with app.state.sessionmaker() as session:
                    return await session.get(model, key)

            return client.portal.call(_get)

        def run(self, fn):
            async def _run():
                async with app.state.sessionmaker() as session:
                    result = await fn(session)
                    await session.commit()
                    return result

            return client.portal.call(_run)

        def count(self, model, *conditions):
            from sqlalchemy import func, select

            async def _count(session):
                return await session.scalar(
                    select(func.count()).select_from(model).where(*conditions)
                )

            return self.run(_count)

    return Db()


@pytest.fixture
def add_client(app, db):
    def _add(email="camille@orbe.test", password=PASSWORD, phone="+33612345678", **fields):
        return db.add(
            Client(
                id=str(uuid.uuid4()),
                email=email,
                phone=phone,
                display_name=fields.pop("display_name", "Camille Test"),
                password_hash=app.state.passwords.hash(password),
                **fields,
            )
        )

    return _add


@pytest.fixture
def login(client):
    def _login(email="camille@orbe.test", password=PASSWORD, **kwargs):
        return client.post("/login", json={"email": email, "password": password}, **kwargs)

    return _login


@pytest.fixture
def token(login):
    """Jeton d'une session ouverte au mot de passe seul (compte sans visage enregistré)."""

    def _token(**kwargs):
        response = login(**kwargs)
        assert response.status_code == 200, response.text
        return response.json()["token"]["access_token"]

    return _token


def bearer(access_token):
    return {"Authorization": f"Bearer {access_token}"}


def encode(frames):
    return [base64.b64encode(frame).decode() for frame in frames]


def enroll_frames(identity, count=16):
    """Images simulées d'enrôlement : la tête balaie de −30° à +30°."""
    return encode(fake_frame(identity, yaw=-30 + 60 * i / (count - 1), n=i) for i in range(count))


def login_frames(identity, direction, count=8, left_is_positive=True):
    """Images simulées de connexion : la tête tourne dans le sens demandé (0° → 20°)."""
    sign = 1 if (direction == "left") == left_is_positive else -1
    return encode(
        fake_frame(identity, yaw=sign * 20 * i / (count - 1), n=100 + i) for i in range(count)
    )


@pytest.fixture
def enroll(client, token):
    """Enrôle un visage simulé (identité = email par défaut) sur un compte sans visage."""

    def _enroll(identity="camille", **login_kwargs):
        headers = bearer(token(**login_kwargs))
        response = client.post(
            "/face/enroll",
            json={"consent": True, "frames": enroll_frames(identity)},
            headers=headers,
        )
        assert response.status_code == 201, response.text
        return identity

    return _enroll


@pytest.fixture
def face_login(client, login):
    """Connexion complète : mot de passe, puis visage simulé."""

    def _face_login(identity="camille", email="camille@orbe.test", **frame_kwargs):
        step1 = login(email=email).json()
        assert step1["mfa_required"] is True, step1
        direction = step1["face_challenge"]["direction"]
        frames = frame_kwargs.pop("frames", None) or login_frames(
            identity, direction, **frame_kwargs
        )
        return step1, client.post(
            "/login/face", json={"session_id": step1["session_id"], "frames": frames}
        )

    return _face_login
