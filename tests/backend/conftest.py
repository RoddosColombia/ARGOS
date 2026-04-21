from __future__ import annotations

import os

# ─── Unit-test bootstrap ─────────────────────────────────────────────────
# Forzamos vars antes de importar argos.config para que las settings queden
# aisladas de cualquier .env local. Integration tests sobreescriben MONGODB_URI
# explícitamente en su propio fixture (ver test_integration_mongo.py).
os.environ["ARGOS_ENV"] = "dev"
os.environ["JWT_SECRET"] = "test-secret-only-for-pytest-never-in-prod"
os.environ["JWT_ALGORITHM"] = "HS256"
os.environ["JWT_ACCESS_TOKEN_TTL_MINUTES"] = "60"
os.environ["MONGODB_URI"] = ""
os.environ["MONGODB_DATABASE"] = "argos_test"
os.environ.setdefault("ADMIN_EMAIL", "ceo-test@roddos.com")
os.environ.setdefault("ADMIN_ROLE", "ceo")
os.environ.setdefault("ADMIN_WORKSPACE_ID", "RODDOS")

import bcrypt  # noqa: E402

TEST_PASSWORD = "test-password-123"
os.environ.setdefault(
    "ADMIN_PASSWORD_HASH",
    bcrypt.hashpw(TEST_PASSWORD.encode(), bcrypt.gensalt()).decode(),
)

import pytest  # noqa: E402
from argos.config import get_settings  # noqa: E402
from argos.main import create_app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def admin_credentials() -> dict[str, str]:
    return {"email": os.environ["ADMIN_EMAIL"], "password": TEST_PASSWORD}


@pytest.fixture
def admin_token(client: TestClient, admin_credentials: dict[str, str]) -> str:
    resp = client.post("/api/v1/auth/login", json=admin_credentials)
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]
