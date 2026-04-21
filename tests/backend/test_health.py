from __future__ import annotations

from argos import __version__
from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "version": __version__}


def test_health_does_not_require_workspace_header(client: TestClient) -> None:
    # ROG-A3 exime al endpoint de health del header X-Workspace-Id.
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200


def test_health_deep_returns_503_when_mongo_not_configured(client: TestClient) -> None:
    # MONGODB_URL está vacío en conftest · el endpoint debe marcar degraded.
    resp = client.get("/api/v1/health/deep")
    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["mongodb"]["state"] == "not_configured"
    assert body["version"] == __version__
