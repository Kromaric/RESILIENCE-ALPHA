"""Fixtures : auth-service simulé (httpx.MockTransport), JWT signés par une clé de test,
SQLite en mémoire à la place de MariaDB.

L'application est créée une seule fois (registre Prometheus global) ; l'auth-service simulé,
le cache des sessions et la base sont remis à zéro avant chaque test.

Dans SQLite, `bo_clients` est une table remplie avec des valeurs déjà masquées : le masquage
lui-même est fait par la vue MariaDB (infra/mariadb/init/01-schema.sql), vérifié de bout en bout.
"""

import json
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
PROMETHEUS, LOKI = "http://prometheus.test", "http://loki.test"
REMEDIATION, ASSISTANT = "http://remediation.test", "http://assistant.test"


class FakeUpstreams:
    """Prometheus, Loki, moteur de remédiation et assistant simulés.

    - `prom` : sous-chaîne de la requête PromQL → valeur (la première qui correspond) ;
      une valeur None simule « aucune série ».
    - `down` : noms des services injoignables (prometheus, loki, remediation, assistant).
    """

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.prom: dict[str, float | None] = {}
        self.loki_lines: list[tuple[int, dict, str]] = []
        self.status: dict | None = None
        self.incidents: dict | list | None = None
        self.answer: dict | None = None
        self.down: set[str] = set()
        self.queries: list[str] = []
        self.assistant_keys: list[str | None] = []
        self.assistant_error: tuple[int, str] | None = None

    def _value(self, query: str) -> float | None:
        for key, value in self.prom.items():
            if key in query:
                return value
        return None

    def handler(self, request: httpx.Request) -> httpx.Response:
        host = request.url.host.split(".")[0]
        if host in self.down:
            raise httpx.ConnectError(f"{host} injoignable", request=request)
        path, params = request.url.path, request.url.params
        if host == "prometheus":
            query = params["query"]
            self.queries.append(query)
            value = self._value(query)
            if path.endswith("/query"):
                result = [] if value is None else [{"metric": {}, "value": [0, str(value)]}]
                return httpx.Response(
                    200, json={"data": {"resultType": "vector", "result": result}}
                )
            start, end, step = float(params["start"]), float(params["end"]), int(params["step"])
            values = [[t, str(value)] for t in range(int(start), int(end) + 1, step)]
            result = [] if value is None else [{"metric": {}, "values": values}]
            return httpx.Response(200, json={"data": {"resultType": "matrix", "result": result}})
        if host == "loki":
            self.queries.append(params["query"])
            streams = [
                {"stream": labels, "values": [[str(ts), line]]}
                for ts, labels, line in self.loki_lines
            ]
            return httpx.Response(200, json={"data": {"resultType": "streams", "result": streams}})
        if host == "remediation":
            if path == "/status" and self.status is not None:
                return httpx.Response(200, json=self.status)
            if path == "/incidents" and self.incidents is not None:
                return httpx.Response(200, json=self.incidents)
            if path.startswith("/incidents/") and isinstance(self.incidents, dict):
                found = [i for i in self.incidents["items"] if i["id"] == path.rsplit("/", 1)[1]]
                if found:
                    return httpx.Response(200, json=found[0])
            return httpx.Response(404, json={"detail": "not found"})
        if host == "assistant":
            self.queries.append(request.content.decode())
            self.assistant_keys.append(request.headers.get("x-api-key"))
            if self.assistant_error is not None:
                status_code, code = self.assistant_error
                return httpx.Response(status_code, json={"detail": {"code": code}})
            return httpx.Response(200, json=self.answer)
        return httpx.Response(404)


class FakeAuthService:
    """Ce que bo-api attend d'auth-service : /operators/login, /logout et /me."""

    def __init__(self, private_key) -> None:
        self.private_key = private_key
        self.reset()

    def reset(self) -> None:
        self.operators = {
            "ops@orbe.test": {"id": str(uuid.uuid4()), "role": "operator", "name": "Opérateur"},
            "viewer@orbe.test": {"id": str(uuid.uuid4()), "role": "viewer", "name": "Lecture"},
            "admin@orbe.test": {"id": str(uuid.uuid4()), "role": "admin", "name": "Admin"},
        }
        # Réponses des étapes de connexion : chemin → (code, corps, en-têtes)
        session_id = "00000000-0000-0000-0000-000000000001"
        self.replies = {
            "/operators/login/identify": (
                200,
                {
                    "session_id": session_id,
                    "step": "face",
                    "face_challenge": {"direction": "left", "frames": 12, "interval_ms": 300},
                    "face_enrollment_required": False,
                    "expires_in": 120,
                },
                {},
            ),
            "/operators/login/face": (
                200,
                {"session_id": session_id, "step": "password", "expires_in": 120},
                {},
            ),
        }
        self.calls: list[tuple[str, str, dict | None, httpx.Headers]] = []
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
        body = json.loads(request.content) if request.content else None
        self.calls.append((request.method, path, body, request.headers))
        if path in self.replies:
            status_code, payload, headers = self.replies[path]
            return httpx.Response(status_code, json=payload, headers=headers)
        if path == "/operators/login/password":
            if body["password"] != "demo-password":
                return httpx.Response(
                    401,
                    json={"detail": {"code": "invalid_credentials", "message": "Incorrect."}},
                )
            return httpx.Response(
                200,
                json={
                    "access_token": self.token("ops@orbe.test"),
                    "token_type": "bearer",
                    "expires_in": 3600,
                    "role": "operator",
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
                    "factors": ["face", "pwd"],
                },
            )
        if path.startswith("/operators/accounts"):
            if operator["role"] != "admin":
                return httpx.Response(403, json={"detail": {"code": "forbidden", "message": "."}})
            if request.method == "DELETE" and path.endswith("/sessions"):
                return httpx.Response(204)
            return httpx.Response(200, json={"path": path, "method": request.method, "body": body})
        return httpx.Response(404)


@pytest.fixture(scope="session")
def private_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="session")
def auth(private_key):
    return FakeAuthService(private_key)


@pytest.fixture(scope="session")
def upstreams():
    return FakeUpstreams()


@pytest.fixture(scope="session")
def app(tmp_path_factory, private_key, auth, upstreams):
    key_file = tmp_path_factory.mktemp("secrets") / "jwt_public_key.pem"
    key_file.write_bytes(
        private_key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
    )
    assistant_key_file = key_file.parent / "rag_api_key"
    assistant_key_file.write_text("cle-assistant-test")
    settings = Settings(
        jwt_public_key_file=key_file,
        auth_url=AUTH,
        prometheus_url=PROMETHEUS,
        loki_url=LOKI,
        remediation_url=REMEDIATION,
        assistant_url=ASSISTANT,
        grafana_public_url="http://grafana.test:3000",
        loki_selector='{container=~"orbe-.+"}',
        assistant_rate_per_operator=3,
        assistant_api_key_file=assistant_key_file,
        enable_docs=True,
        session_cache_seconds=60,
        page_size_max=3,
    )

    def dispatch(request: httpx.Request) -> httpx.Response:
        if request.url.host == "auth.test":
            return auth.handler(request)
        return upstreams.handler(request)

    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    return create_app(
        settings,
        http=httpx.AsyncClient(transport=httpx.MockTransport(dispatch)),
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
def clean_state(app, auth, upstreams, client):
    auth.reset()
    upstreams.reset()
    app.state.ask_limiter = type(app.state.ask_limiter)(
        app.state.settings.assistant_rate_per_operator
    )
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
