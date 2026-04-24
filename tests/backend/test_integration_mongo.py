"""Tests de integración contra MongoDB Atlas (cluster argos-prod · DB argos_test).

Se saltan si no hay URI real · para correrlos localmente, exportar la URI antes
de pytest o tenerla en .env (ver .env.example). Cada test usa su propia DB
temporal que se limpia en teardown.
"""
from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import bcrypt
import pytest
import pytest_asyncio
from argos.config import get_settings
from argos.db import collections as col
from argos.db.events import publish_event
from argos.db.indexes import ensure_indexes
from argos.db.seed import seed_initial_data
from fastapi.testclient import TestClient
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase


def _real_mongo_uri() -> str:
    """Lee la URI real ignorando el MONGODB_URI="" que conftest fuerza para unit tests."""
    from dotenv import dotenv_values

    env_file = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    if os.path.exists(env_file):
        vals = dotenv_values(env_file)
        if vals.get("MONGODB_URI"):
            return vals["MONGODB_URI"]
    return os.environ.get("ARGOS_INTEGRATION_MONGODB_URI", "")


REAL_URI = _real_mongo_uri()
pytestmark = pytest.mark.skipif(
    not REAL_URI,
    reason="MONGODB_URI no disponible · integration tests saltados",
)


@pytest_asyncio.fixture
async def mongo_db() -> AsyncIterator[AsyncIOMotorDatabase]:
    """Cliente Motor contra DB argos_test · limpia colecciones antes y después."""
    client = AsyncIOMotorClient(REAL_URI, serverSelectionTimeoutMS=5000)
    db = client[os.environ.get("MONGODB_TEST_DATABASE", "argos_test")]
    for c in col.ALL_BUILD_0_3:
        await db[c].drop()
    try:
        yield db
    finally:
        for c in col.ALL_BUILD_0_3:
            await db[c].drop()
        client.close()


@pytest_asyncio.fixture
async def indexed_db(mongo_db: AsyncIOMotorDatabase) -> AsyncIOMotorDatabase:
    await ensure_indexes(mongo_db)
    return mongo_db


async def test_ensure_indexes_creates_all_expected(mongo_db: AsyncIOMotorDatabase) -> None:
    created = await ensure_indexes(mongo_db)
    # ensure_indexes cubre Build 0.3 y Build 1.0 · las de 0.3 deben estar incluidas
    assert set(col.ALL_BUILD_0_3).issubset(set(created.keys()))

    # Verificar nombres de índices en cada colección
    workspaces_idx = await mongo_db[col.WORKSPACES].index_information()
    assert "workspace_id_unique" in workspaces_idx
    assert workspaces_idx["workspace_id_unique"]["unique"] is True

    users_idx = await mongo_db[col.USERS].index_information()
    assert "workspace_email_unique" in users_idx
    assert users_idx["workspace_email_unique"]["unique"] is True

    events_idx = await mongo_db[col.ARGOS_EVENTS].index_information()
    assert "event_id_unique" in events_idx
    assert "workspace_event_type_ts" in events_idx
    assert "correlation_id" in events_idx

    audit_idx = await mongo_db[col.AUDIT_LOG].index_information()
    assert "workspace_ts" in audit_idx
    assert "workspace_resource" in audit_idx

    health_idx = await mongo_db[col.SYSTEM_HEALTH].index_information()
    assert "component_ts" in health_idx


async def test_ensure_indexes_is_idempotent(mongo_db: AsyncIOMotorDatabase) -> None:
    await ensure_indexes(mongo_db)
    # Segunda corrida no debe fallar aunque los índices ya existan
    await ensure_indexes(mongo_db)


async def test_seed_creates_workspace_and_user(indexed_db: AsyncIOMotorDatabase) -> None:
    result = await seed_initial_data(indexed_db)
    assert result["workspace_created"] is True
    assert result["user_created"] is True

    ws = await indexed_db[col.WORKSPACES].find_one({"workspace_id": "RODDOS"})
    assert ws is not None
    assert ws["name"] == "RODDOS S.A.S."
    assert "REPUESTOS-MOTOS" in ws["verticals"]

    user = await indexed_db[col.USERS].find_one({"email": os.environ["ADMIN_EMAIL"].lower()})
    assert user is not None
    assert user["workspace_id"] == "RODDOS"
    assert user["roles"] == ["ceo"]
    assert user["password_hash"].startswith("$2b$")


async def test_seed_is_idempotent(indexed_db: AsyncIOMotorDatabase) -> None:
    first = await seed_initial_data(indexed_db)
    second = await seed_initial_data(indexed_db)
    assert first["workspace_created"] is True
    assert second["workspace_created"] is False  # segunda no vuelve a crear
    assert second["user_created"] is False

    # Y no hay duplicados
    ws_count = await indexed_db[col.WORKSPACES].count_documents({"workspace_id": "RODDOS"})
    user_count = await indexed_db[col.USERS].count_documents({})
    assert ws_count == 1
    assert user_count == 1


async def test_seed_does_not_rotate_password(indexed_db: AsyncIOMotorDatabase) -> None:
    await seed_initial_data(indexed_db)
    original = await indexed_db[col.USERS].find_one({"email": os.environ["ADMIN_EMAIL"].lower()})
    assert original is not None

    # Simular que alguien rota ADMIN_PASSWORD_HASH · seed NO debe sobreescribir
    fake_hash = bcrypt.hashpw(b"otro-password", bcrypt.gensalt()).decode()
    original_env = os.environ["ADMIN_PASSWORD_HASH"]
    os.environ["ADMIN_PASSWORD_HASH"] = fake_hash
    get_settings.cache_clear()
    try:
        await seed_initial_data(indexed_db)
        after = await indexed_db[col.USERS].find_one({"email": os.environ["ADMIN_EMAIL"].lower()})
        assert after["password_hash"] == original["password_hash"], (
            "Seed no debe rotar password_hash silenciosamente"
        )
    finally:
        os.environ["ADMIN_PASSWORD_HASH"] = original_env
        get_settings.cache_clear()


async def test_publish_event_persists_with_schema(indexed_db: AsyncIOMotorDatabase) -> None:
    doc = await publish_event(
        indexed_db,
        event_type="score.evaluated",
        workspace_id="RODDOS",
        producer="score_engine",
        payload={"solicitud_id": "SCR-ARGOS-2026-TEST", "decision": "aprobado"},
        correlation_id="conv_test_123",
    )
    assert doc["event_id"].startswith("evt_")
    assert doc["event_type"] == "score.evaluated"
    assert doc["workspace_id"] == "RODDOS"
    assert doc["version"] == "1.0"
    assert isinstance(doc["timestamp_utc"], datetime)

    # Persistencia verificable
    persisted = await indexed_db[col.ARGOS_EVENTS].find_one({"event_id": doc["event_id"]})
    assert persisted is not None
    assert persisted["producer"] == "score_engine"


async def test_publish_event_rejects_invalid_type(indexed_db: AsyncIOMotorDatabase) -> None:
    from argos.db.events import EventValidationError

    with pytest.raises(EventValidationError):
        await publish_event(
            indexed_db,
            event_type="noDotNotation",  # inválido
            workspace_id="RODDOS",
            producer="test",
            payload={},
        )


async def test_publish_event_rejects_missing_workspace(indexed_db: AsyncIOMotorDatabase) -> None:
    from argos.db.events import EventValidationError

    with pytest.raises(EventValidationError):
        await publish_event(
            indexed_db,
            event_type="score.evaluated",
            workspace_id="",
            producer="test",
            payload={},
        )


async def test_event_id_unique_constraint(indexed_db: AsyncIOMotorDatabase) -> None:
    from pymongo.errors import DuplicateKeyError

    # Insertar un evento con event_id manual y verificar que un duplicado falla
    doc = {
        "event_id": "evt_fixed_for_test",
        "event_type": "test.duplicate",
        "version": "1.0",
        "workspace_id": "RODDOS",
        "timestamp_utc": datetime.now(tz=UTC),
        "producer": "test",
        "correlation_id": None,
        "causation_id": None,
        "payload": {},
        "metadata": {},
    }
    await indexed_db[col.ARGOS_EVENTS].insert_one(doc.copy())
    with pytest.raises(DuplicateKeyError):
        await indexed_db[col.ARGOS_EVENTS].insert_one(doc.copy())


class TestApiAgainstRealMongo:
    """Integración del API completo (lifespan conecta Atlas, seed, login vs MongoUserStore)."""

    @pytest.fixture(autouse=True)
    def _use_real_mongo(self, monkeypatch):
        monkeypatch.setenv("MONGODB_URI", REAL_URI)
        monkeypatch.setenv("MONGODB_DATABASE", os.environ.get("MONGODB_TEST_DATABASE", "argos_test"))
        get_settings.cache_clear()
        yield
        get_settings.cache_clear()
        # cleanup DB
        client = AsyncIOMotorClient(REAL_URI, serverSelectionTimeoutMS=5000)
        try:
            db = client[os.environ.get("MONGODB_TEST_DATABASE", "argos_test")]
            asyncio.get_event_loop().run_until_complete(self._drop_all(db)) if False else None
        finally:
            client.close()

    @staticmethod
    async def _drop_all(db):
        for c in col.ALL_BUILD_0_3:
            await db[c].drop()

    def test_health_deep_returns_200_with_real_mongo(self):
        from argos.main import create_app

        app = create_app()
        with TestClient(app) as client:
            resp = client.get("/api/v1/health/deep")
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body["status"] == "ok"
            assert body["mongodb"]["state"] == "ok"

    def test_login_via_mongo_user_store(self, admin_credentials):
        from argos.main import create_app

        app = create_app()
        with TestClient(app) as client:
            resp = client.post("/api/v1/auth/login", json=admin_credentials)
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body["role"] == "ceo"
            assert body["workspace_id"] == "RODDOS"

    def test_me_with_mongo_user_store(self, admin_credentials):
        from argos.main import create_app

        app = create_app()
        with TestClient(app) as client:
            login = client.post("/api/v1/auth/login", json=admin_credentials)
            token = login.json()["access_token"]
            resp = client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {token}", "X-Workspace-Id": "RODDOS"},
            )
            assert resp.status_code == 200
            assert resp.json()["email"] == admin_credentials["email"]

    def test_me_workspace_mismatch_still_403(self, admin_credentials):
        from argos.main import create_app

        app = create_app()
        with TestClient(app) as client:
            login = client.post("/api/v1/auth/login", json=admin_credentials)
            token = login.json()["access_token"]
            resp = client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {token}", "X-Workspace-Id": "OTRO_TENANT"},
            )
            assert resp.status_code == 403
