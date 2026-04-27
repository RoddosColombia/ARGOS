from __future__ import annotations

from fastapi.testclient import TestClient


def test_missing_workspace_header_returns_400(client: TestClient, admin_token: str) -> None:
    resp = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["code"] == "workspace_header_missing"
    assert "ROG-A3" in body["detail"]


def test_health_endpoint_is_exempt(client: TestClient) -> None:
    # Endpoints de health están exentos (necesarios para monitoreo externo).
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200


def test_login_endpoint_is_exempt(client: TestClient, admin_credentials: dict[str, str]) -> None:
    # El login es previo al conocimiento del workspace del usuario.
    resp = client.post("/api/v1/auth/login", json=admin_credentials)
    assert resp.status_code == 200


def test_docs_endpoint_is_exempt(client: TestClient) -> None:
    resp = client.get("/openapi.json")
    assert resp.status_code == 200


def test_options_preflight_passes_without_workspace_header(client: TestClient) -> None:
    """CORS preflight (OPTIONS) NO debe ser bloqueado por el middleware.

    El browser nunca envía X-Workspace-Id en preflights. Si lo bloqueamos,
    el preflight muere con 400 antes de llegar al CORSMiddleware y el
    browser nunca ve los headers Access-Control-*. Regression test del
    hotfix CORS de 2026-04-26.
    """
    resp = client.options(
        "/api/v1/auth/me",
        headers={
            "Origin": "https://argos.roddos.com",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization,x-workspace-id",
        },
    )
    # No debe ser 400 (workspace_header_missing). El CORSMiddleware responde 200.
    assert resp.status_code != 400
    assert resp.headers.get("access-control-allow-origin") is not None
