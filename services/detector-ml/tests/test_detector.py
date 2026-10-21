"""detector-ml contre un faux Prometheus / Loki (httpx.MockTransport)."""

import asyncio
import math

import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient

from anomaly.features import feature_names, prometheus_features
from anomaly.model import AnomalyModel
from anomaly.sources import SourceError, Sources
from app.main import SCORE, Detector, Settings, create_app

NORMAL = dict(req_rate=2, latency_p95=0.08, error_5xx_ratio=0.0, client_4xx_ratio=0.05,
              pool_saturation=0.2, pool_timeouts_rate=0.0, container_cpu=0.1,
              container_mem_mib=120, host_cpu=0.2, ip_distinct=30, ip_top_share=0.08,
              unauth_ratio=0.02)
ATTACK = NORMAL | dict(req_rate=25, latency_p95=2.0, error_5xx_ratio=0.5, pool_saturation=1.0,
                       pool_timeouts_rate=8.0, container_cpu=0.9)


@pytest.fixture(scope="module")
def model():
    rng = np.random.default_rng(1)
    names = feature_names()
    X = np.array([[NORMAL[n] * (1 + rng.normal(0, 0.1)) + abs(rng.normal(0, 0.01))
                   for n in names] for _ in range(500)])
    m = AnomalyModel.fit(X, names)
    m.threshold = 0.6
    return m


def fake_backend(values: dict, fail: bool = False) -> httpx.AsyncClient:
    by_query = {f.query: f.name for f in prometheus_features()}

    def handler(request: httpx.Request) -> httpx.Response:
        if fail:
            return httpx.Response(503, text="down")
        if request.url.path == "/api/v1/query":
            name = by_query[request.url.params["query"]]
            result = [{"metric": {}, "value": [0, str(values[name])]}]
            return httpx.Response(200, json={"status": "success",
                                             "data": {"resultType": "vector", "result": result}})
        if request.url.path == "/loki/api/v1/query":  # IP dominante selon ip_top_share
            top = round(values["ip_top_share"] * 100)
            result = [{"metric": {"client_ip": "1.1.1.1", "status": "201"}, "value": [0, str(top)]},
                      {"metric": {"client_ip": "2.2.2.2", "status": "201"},
                       "value": [0, str(100 - top)]}]
            return httpx.Response(200, json={"status": "success",
                                             "data": {"resultType": "vector", "result": result}})
        return httpx.Response(404)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def detector(model, values, fail=False):
    sources = Sources("http://prom", "http://loki", client=fake_backend(values, fail))
    return Detector(Settings(), model, sources)


def test_normal_traffic_scores_low(model):
    result = asyncio.run(detector(model, NORMAL).evaluate())
    assert result["score"] < model.threshold
    assert result["anomaly"] is False


def test_attack_is_detected_and_explained(model):
    result = asyncio.run(detector(model, ATTACK).evaluate())
    assert result["anomaly"] is True
    assert result["top_deviations"][0]["feature"] in {
        "pool_timeouts_rate", "error_5xx_ratio", "latency_p95", "req_rate"}


def test_source_down_gives_no_score(model):
    det = detector(model, NORMAL, fail=True)
    with pytest.raises(SourceError):
        asyncio.run(det.evaluate())
    det.mark_unknown("source")
    assert math.isnan(SCORE.labels("payment-service")._value.get())


def test_http_endpoints(model):
    det = detector(model, ATTACK)
    with TestClient(create_app(Settings(interval_seconds=0.05), det)) as client:
        for _ in range(50):
            if det.last:
                break
            asyncio.run(asyncio.sleep(0.02))
        body = client.get("/score").json()
        assert body["anomaly"] is True and body["threshold"] == 0.6
        metrics = client.get("/metrics").text
        assert 'anomaly_threshold{target="payment-service"} 0.6' in metrics
        assert "anomaly_feature_zscore" in metrics
        assert client.get("/health/ready").status_code == 200
