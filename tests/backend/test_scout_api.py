"""API tests para POST /api/v1/scout/trigger · usan unit-test harness (sin Mongo real)."""
from __future__ import annotations

import pytest
from argos.auth.security import create_access_token
from fastapi.testclient import TestClient


def _token(role: str = "ceo", workspace_id: str = "RODDOS", email: str = "u@roddos.com") -> str:
    return create_access_token(subject=email, role=role, workspace_id=workspace_id)


def test_trigger_requires_auth(client: TestClient) -> None:
    resp = client.post("/api/v1/scout/trigger", headers={"X-Workspace-Id": "RODDOS"})
    assert resp.status_code == 401


@pytest.mark.parametrize("role", ["analista", "cliente"])
def test_trigger_rejects_non_ceo_sistema(client: TestClient, role: str) -> None:
    token = _token(role=role)
    resp = client.post(
        "/api/v1/scout/trigger",
        headers={"Authorization": f"Bearer {token}", "X-Workspace-Id": "RODDOS"},
    )
    assert resp.status_code == 403


def test_trigger_returns_503_when_mongo_not_configured(client: TestClient) -> None:
    # Unit-test harness corre con MONGODB_URI="" · scout debe devolver 503
    token = _token(role="ceo")
    resp = client.post(
        "/api/v1/scout/trigger",
        headers={"Authorization": f"Bearer {token}", "X-Workspace-Id": "RODDOS"},
    )
    assert resp.status_code == 503
    assert "MongoDB" in resp.json()["detail"]
