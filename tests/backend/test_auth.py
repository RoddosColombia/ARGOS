from __future__ import annotations

from argos.auth.security import create_access_token, decode_access_token
from fastapi.testclient import TestClient


def test_login_returns_jwt(client: TestClient, admin_credentials: dict[str, str]) -> None:
    resp = client.post("/api/v1/auth/login", json=admin_credentials)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["role"] == "ceo"
    assert body["workspace_id"] == "RODDOS"
    assert body["expires_in"] == 60 * 60
    claims = decode_access_token(body["access_token"])
    assert claims["sub"] == admin_credentials["email"]
    assert claims["role"] == "ceo"
    assert claims["workspace_id"] == "RODDOS"


def test_login_rejects_bad_password(client: TestClient, admin_credentials: dict[str, str]) -> None:
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": admin_credentials["email"], "password": "wrong-password"},
    )
    assert resp.status_code == 401


def test_login_rejects_unknown_email(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@roddos.com", "password": "whatever"},
    )
    assert resp.status_code == 401


def test_me_returns_user(client: TestClient, admin_token: str) -> None:
    resp = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {admin_token}", "X-Workspace-Id": "RODDOS"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"].endswith("@roddos.com")
    assert body["role"] == "ceo"
    assert body["workspace_id"] == "RODDOS"


def test_me_rejects_workspace_mismatch(client: TestClient, admin_token: str) -> None:
    resp = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {admin_token}", "X-Workspace-Id": "OTRO_TENANT"},
    )
    assert resp.status_code == 403


def test_me_rejects_missing_token(client: TestClient) -> None:
    resp = client.get("/api/v1/auth/me", headers={"X-Workspace-Id": "RODDOS"})
    assert resp.status_code == 401


def test_me_rejects_expired_token(client: TestClient) -> None:
    token = create_access_token(
        subject="ceo-test@roddos.com",
        role="ceo",
        workspace_id="RODDOS",
        ttl_minutes=-1,
    )
    resp = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}", "X-Workspace-Id": "RODDOS"},
    )
    assert resp.status_code == 401
    assert "expirado" in resp.json()["detail"].lower()
