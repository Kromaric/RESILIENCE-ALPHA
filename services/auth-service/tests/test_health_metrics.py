from sqlalchemy.ext.asyncio import create_async_engine


def test_live(client):
    assert client.get("/health/live").json() == {"status": "ok"}


def test_ready_when_the_database_answers(client):
    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json()["checks"]["database"] == "up"


def test_not_ready_when_the_database_is_unreachable(app, client):
    healthy_engine = app.state.engine
    app.state.engine = create_async_engine("sqlite+aiosqlite:////dossier-inexistant/orbe.db")
    try:
        response = client.get("/health/ready")
    finally:
        app.state.engine = healthy_engine

    assert response.status_code == 503
    assert response.json()["checks"]["database"] == "down"


def test_metrics_expose_login_failures(add_client, login, client):
    add_client()
    login(password="pas-le-bon")

    body = client.get("/metrics").text

    assert 'auth_login_failures_total{reason="invalid_credentials"}' in body
    assert "http_requests_total" in body


def test_request_id_is_propagated(client):
    response = client.get("/health/live", headers={"X-Request-ID": "req-123"})

    assert response.headers["X-Request-ID"] == "req-123"
