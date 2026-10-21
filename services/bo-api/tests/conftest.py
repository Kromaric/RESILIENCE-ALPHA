"""Fixtures : auth-service simulé (httpx.MockTransport), JWT signés par une clé de test,
SQLite en mémoire à la place de MariaDB.

L'application est créée une seule fois (registre Prometheus global) ; l'auth-service simulé,
le cache des sessions et la base sont remis à zéro avant chaque test.

Dans SQLite, `bo_clients` est une table remplie avec des valeurs déjà masquées : le masquage
lui-même est fait par la vue MariaDB (infra/mariadb/init/01-schema.sql), vérifié de bout en bout.
"""

import time
import uuid

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.db import metadata
from app.main import create_app

AUTH = "http://auth.test"


class FakeAuthService:
    """Ce que bo-api attend d'auth-service : /operators/login, /logout et /me."""

    def __init__(self, private_key) -> None:
        self.private_key = private_key
        self.reset()

    def reset(self) -> None:
        self.operators = {
            "ops@orbe.test": {"id": str(uuid.uuid4()), "role": "operator", "name": "Opérateur"},
            "viewer@orbe.test": {"id": str(uuid.uuid4()), "role": "viewer", "name": "Lecture"},
        }
        self.sessions: dict[str, dict] = {}  # jti → opérateur
        self.me_calls = 0
        self.down = False
        self.last_login_headers: httpx.Headers | None = None

    def token(self, email="ops@orbe.test", *, audience="orbe-bo", typ="operator", ttl=3600):
        operator = self.operators[email]
        jti = str(uuid.uuid4())
        self.sessions[jti] = {**operator, "email": email}
        now = int(time.time())
        claims = {
            "sub": operator["id"],
            "email": email,
            "role": operator["role"],
            "typ": typ,
            "iss": "orbe-auth",
            "aud": audience,
            "iat": now,
            "nbf": now,
            "exp": now + ttl,
            "jti": jti,
            "amr": ["pwd"],
        }
        return jwt.encode(claims, self.private_key, algorithm="RS256")

    def _session(self, request: httpx.Request) -> tuple[str, dict] | None:
        token = request.headers.get("authorization", "").removeprefix("Bearer ")
        jti = jwt.decode(token, options={"verify_signature": False}).get("jti")
        return (jti, self.sessions[jti]) if jti in self.sessions else None

    def handler(self, request: httpx.Request) -> httpx.Response:
        if self.down:
            raise httpx.ConnectError("auth-service injoignable", request=request)
        path = request.url.path
        if path == "/operators/login":
            self.last_login_headers = request.headers
            body = __import__("json").loads(request.content)
            if body["email"] not in self.operators or body["password"] != "demo-password":
                return httpx.Response(
                    401,
                    json={"detail": {"code": "invalid_credentials", "message": "Incorrect."}},
                )
            role = self.operators[body["email"]]["role"]
            return httpx.Response(
                200,
                json={
                    "access_token": self.token(body["email"]),
                    "token_type": "bearer",
                    "expires_in": 3600,
                    "role": role,
                },
            )
        found = self._session(request)
        if found is None:
            return httpx.Response(401, json={"detail": {"code": "invalid_token", "message": "."}})
        jti, operator = found
        if path == "/operators/logout":
            del self.sessions[jti]
            return httpx.Response(204)
        if path == "/operators/me":
            self.me_calls += 1
            return httpx.Response(
                200,
                json={
                    "operator_id": operator["id"],
                    "email": operator["email"],
                    "display_name": operator["name"],
                    "role": operator["role"],
                    "session_id": jti,
                    "expires_at": "2099-01-01T00:00:00Z",
                },
            )
        return httpx.Response(404)


@pytest.fixture(scope="session")
def private_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="session")
def auth(private_key):
    return FakeAuthService(private_key)


@pytest.fixture(scope="session")
def app(tmp_path_factory, private_key, auth):
    key_file = tmp_path_factory.mktemp("secrets") / "jwt_public_key.pem"
    key_file.write_bytes(
        private_key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
    )
    settings = Settings(
        jwt_public_key_file=key_file,
        auth_url=AUTH,
        enable_docs=True,
        session_cache_seconds=60,
        page_size_max=3,
    )
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    return create_app(
        settings,
        http=httpx.AsyncClient(transport=httpx.MockTransport(auth.handler)),
        engine=engine,
    )


async def _reset_schema(engine):
    async with engine.begin() as conn:
        await conn.run_sync(metadata.drop_all)
        await conn.run_sync(metadata.create_all)


@pytest.fixture(scope="session")
def client(app):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def clean_state(app, auth, client):
    auth.reset()
    app.state.operator_sessions._cache.clear()
    client.portal.call(_reset_schema, app.state.engine)


@pytest.fixture
def db(app, client):
    """Exécute des requêtes sur la base de test depuis un test synchrone."""

    def run(*statements):
        async def _run():
            async with app.state.engine.begin() as conn:
                for statement in statements:
                    await conn.execute(statement)

        client.portal.call(_run)

    return run


def bearer(token):
    return {"Authorization": f"Bearer {token}"}
