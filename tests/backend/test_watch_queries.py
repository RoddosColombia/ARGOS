"""Tests del seed + endpoint de watch queries · contra Mongo real."""
from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from argos.agents.scout.queries_repo import get_active_queries, list_all_queries
from argos.auth.security import create_access_token
from argos.db import collections as col
from argos.db.indexes import ensure_indexes
from argos.db.seed import seed_initial_data
from fastapi.testclient import TestClient
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from tests.backend.test_integration_mongo import REAL_URI

pytestmark = pytest.mark.skipif(
    not REAL_URI,
    reason="MONGODB_URI no disponible · integration tests saltados",
)


@pytest_asyncio.fixture
async def indexed_db() -> AsyncIterator[AsyncIOMotorDatabase]:
    client = AsyncIOMotorClient(REAL_URI, serverSelectionTimeoutMS=5000)
    db = client[os.environ.get("MONGODB_TEST_DATABASE", "argos_test")]
    for c in col.ALL_KNOWN:
        await db[c].drop()
    await ensure_indexes(db)
    try:
        yield db
    finally:
        for c in col.ALL_KNOWN:
            await db[c].drop()
        client.close()


async def test_seed_inserts_11_watch_queries_first_time(indexed_db: AsyncIOMotorDatabase) -> None:
    result = await seed_initial_data(indexed_db)
    assert result["watch_queries_inserted"] == 11

    queries = await list_all_queries(indexed_db, "RODDOS")
    assert len(queries) == 11
    query_strs = [q["query"] for q in queries]
    assert "aceite moto" in query_strs
    assert "repuestos TVS Raider 125" in query_strs

    # Todas activas, source=all, prioridad=1 por default
    for q in queries:
        assert q["activa"] is True
        assert q["source"] == "all"
        assert q["prioridad"] == 1


async def test_seed_is_idempotent_for_watch_queries(indexed_db: AsyncIOMotorDatabase) -> None:
    first = await seed_initial_data(indexed_db)
    second = await seed_initial_data(indexed_db)
    assert first["watch_queries_inserted"] == 11
    assert second["watch_queries_inserted"] == 0

    count = await indexed_db[col.WATCH_QUERIES].count_documents({"workspace_id": "RODDOS"})
    assert count == 11


async def test_seed_does_not_overwrite_manual_changes(indexed_db: AsyncIOMotorDatabase) -> None:
    await seed_initial_data(indexed_db)
    # CEO desactiva una query manualmente
    await indexed_db[col.WATCH_QUERIES].update_one(
        {"workspace_id": "RODDOS", "query": "bujía moto"},
        {"$set": {"activa": False, "source": "meli", "prioridad": 5}},
    )
    # Re-correr seed · NO debe revertir el toggle
    await seed_initial_data(indexed_db)
    doc = await indexed_db[col.WATCH_QUERIES].find_one(
        {"workspace_id": "RODDOS", "query": "bujía moto"}
    )
    assert doc is not None
    assert doc["activa"] is False
    assert doc["source"] == "meli"
    assert doc["prioridad"] == 5


async def test_get_active_queries_excludes_inactivas(indexed_db: AsyncIOMotorDatabase) -> None:
    await seed_initial_data(indexed_db)
    await indexed_db[col.WATCH_QUERIES].update_one(
        {"workspace_id": "RODDOS", "query": "aceite moto"},
        {"$set": {"activa": False}},
    )
    active = await get_active_queries(indexed_db, "RODDOS")
    assert len(active) == 10
    assert all(q["query"] != "aceite moto" for q in active)


def _ceo_token(workspace_id: str = "RODDOS", email: str = "ceo@roddos.com") -> str:
    return create_access_token(subject=email, role="ceo", workspace_id=workspace_id)


def test_get_watch_queries_endpoint_returns_503_without_mongo(client: TestClient) -> None:
    """Sin MONGODB_URI configurado en conftest, el endpoint devuelve 503."""
    token = _ceo_token()
    resp = client.get(
        "/api/v1/scout/watch-queries",
        headers={"Authorization": f"Bearer {token}", "X-Workspace-Id": "RODDOS"},
    )
    assert resp.status_code == 503


def test_get_watch_queries_requires_ceo_role(client: TestClient) -> None:
    token = create_access_token(subject="a@b.com", role="analista", workspace_id="RODDOS")
    resp = client.get(
        "/api/v1/scout/watch-queries",
        headers={"Authorization": f"Bearer {token}", "X-Workspace-Id": "RODDOS"},
    )
    assert resp.status_code == 403
