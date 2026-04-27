"""Tests del SismoAgent · sync job + endpoint /api/v1/sismo/inventory."""
from __future__ import annotations

import os
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
import pytest_asyncio
from argos.agents.sismo.service import SismoAgent, sync_sismo_inventory_job
from argos.auth.security import create_access_token
from argos.config import get_settings
from argos.db import collections as col
from argos.db.indexes import ensure_indexes
from argos.main import create_app
from argos.partners.sismo.client import SismoClient
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


def _mock_client_with(items: list[dict[str, Any]]) -> SismoClient:
    """Devuelve un SismoClient enchufado a httpx.MockTransport con items dados."""
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=items)

    client = SismoClient(base_url="https://sismo.test", api_key="key-test")
    transport = httpx.MockTransport(handler)
    client._client = httpx.AsyncClient(transport=transport, base_url="https://sismo.test")
    return client


async def test_sync_job_persiste_inventario_y_marca_slow_movers(
    indexed_db: AsyncIOMotorDatabase,
) -> None:
    items = [
        {
            "sku": "FRENO-001", "nombre": "Pastilla freno Pulsar",
            "stock": 24, "precio": 45000, "costo": 28000, "dias_inventario": 12,
        },
        {
            "sku": "ACEITE-002", "nombre": "Aceite Motul 4T",
            "stock": 8, "precio": 52000, "costo": 36000, "dias_inventario": 60,
        },
        {
            "sku": "BUJIA-003", "nombre": "Bujía NGK",
            "stock": 50, "precio": 18000, "costo": 9000, "dias_inventario": 5,
        },
    ]
    fake_client = _mock_client_with(items)
    agent = SismoAgent(client=fake_client)

    stats = await sync_sismo_inventory_job(indexed_db, workspace_id="RODDOS", agent=agent)

    assert stats.enabled is True
    assert stats.total_skus == 3
    assert stats.slow_count == 1  # solo ACEITE-002 con dias_inventario >= 45
    assert stats.inserted == 3

    docs = await indexed_db[col.SISMO_INVENTORY].find({"workspace_id": "RODDOS"}).to_list(length=10)
    assert len(docs) == 3
    aceite = next(d for d in docs if d["sku"] == "ACEITE-002")
    assert aceite["is_slow_mover"] is True
    assert aceite["dias_inventario"] == 60

    # Evento sismo.inventory.synced emitido
    event = await indexed_db[col.ARGOS_EVENTS].find_one(
        {"event_type": "sismo.inventory.synced"}
    )
    assert event is not None
    assert event["payload"]["total_skus"] == 3
    assert event["payload"]["slow_count"] == 1


async def test_sync_job_skip_silencioso_sin_credenciales(
    indexed_db: AsyncIOMotorDatabase,
) -> None:
    """Sin SISMO_API_URL/_KEY: stats vacías, no toca Mongo."""
    agent = SismoAgent(client=SismoClient(base_url="", api_key=""))
    stats = await sync_sismo_inventory_job(indexed_db, workspace_id="RODDOS", agent=agent)
    assert stats.enabled is False
    assert stats.total_skus == 0
    count = await indexed_db[col.SISMO_INVENTORY].count_documents({"workspace_id": "RODDOS"})
    assert count == 0


def _ceo_token() -> str:
    return create_access_token(subject="ceo@roddos.com", role="ceo", workspace_id="RODDOS")


async def _authed_client(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[httpx.AsyncClient]:
    monkeypatch.setenv("MONGODB_URI", REAL_URI)
    monkeypatch.setenv("MONGODB_DATABASE", os.environ.get("MONGODB_TEST_DATABASE", "argos_test"))
    monkeypatch.setenv("ARGOS_DISABLE_SCHEDULER", "true")
    get_settings.cache_clear()
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=transport, base_url="http://test") as client,
    ):
        yield client
    get_settings.cache_clear()


async def test_endpoint_inventory_filtra_por_type_slow_movers(
    indexed_db: AsyncIOMotorDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    items = [
        {"sku": "A", "nombre": "rapida", "stock": 10, "precio": 1000, "costo": 500, "dias_inventario": 10},
        {"sku": "B", "nombre": "lenta", "stock": 5, "precio": 2000, "costo": 1000, "dias_inventario": 90},
    ]
    fake_client = _mock_client_with(items)
    agent = SismoAgent(client=fake_client)
    await sync_sismo_inventory_job(indexed_db, workspace_id="RODDOS", agent=agent)

    headers = {"Authorization": f"Bearer {_ceo_token()}", "X-Workspace-Id": "RODDOS"}
    async for client in _authed_client(monkeypatch):
        resp_all = await client.get("/api/v1/sismo/inventory?type=all", headers=headers)
        assert resp_all.status_code == 200
        body_all = resp_all.json()
        assert body_all["total"] == 2

        resp_slow = await client.get("/api/v1/sismo/inventory?type=slow_movers", headers=headers)
        assert resp_slow.status_code == 200
        body_slow = resp_slow.json()
        assert body_slow["total"] == 1
        assert body_slow["items"][0]["sku"] == "B"
        assert body_slow["items"][0]["is_slow_mover"] is True
