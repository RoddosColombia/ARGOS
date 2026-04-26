"""Tests del endpoint /api/v1/alerts/recent · contra Mongo real."""
from __future__ import annotations

import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import httpx
import pytest
import pytest_asyncio
from argos.auth.security import create_access_token
from argos.config import get_settings
from argos.db import collections as col
from argos.db.indexes import ensure_indexes
from argos.main import create_app
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from tests.backend.test_integration_mongo import REAL_URI

pytestmark = pytest.mark.skipif(
    not REAL_URI,
    reason="MONGODB_URI no disponible · integration tests saltados",
)


@pytest_asyncio.fixture
async def seeded_alerts_db() -> AsyncIterator[AsyncIOMotorDatabase]:
    client = AsyncIOMotorClient(REAL_URI, serverSelectionTimeoutMS=5000)
    db = client[os.environ.get("MONGODB_TEST_DATABASE", "argos_test")]
    for c in col.ALL_KNOWN:
        await db[c].drop()
    await ensure_indexes(db)

    now = datetime.now(tz=UTC)
    # 3 alertas dentro de la ventana 48h + 1 fuera (vieja)
    events = [
        # Reciente · 1h
        {
            "event_id": "evt_a1",
            "event_type": "marketplace.price.alert",
            "version": "1.0",
            "workspace_id": "RODDOS",
            "timestamp_utc": now - timedelta(hours=1),
            "producer": "alerts_agent",
            "correlation_id": None,
            "causation_id": None,
            "payload": {
                "sku_normalizado": "meli:MCO-A",
                "titulo": "Aceite caro",
                "precio_anterior": 100000,
                "precio_actual": 80000,
                "delta_pct": -20.0,
                "fuente": "meli",
                "competitor_url": "https://meli.example/a",
            },
            "metadata": {},
        },
        # Reciente · 24h
        {
            "event_id": "evt_a2",
            "event_type": "marketplace.price.alert",
            "version": "1.0",
            "workspace_id": "RODDOS",
            "timestamp_utc": now - timedelta(hours=24),
            "producer": "alerts_agent",
            "correlation_id": None,
            "causation_id": None,
            "payload": {
                "sku_normalizado": "meli:MCO-B",
                "titulo": "Pastillas",
                "precio_anterior": 50000,
                "precio_actual": 40000,
                "delta_pct": -20.0,
                "fuente": "meli",
                "competitor_url": "https://meli.example/b",
            },
            "metadata": {},
        },
        # Reciente · 47h
        {
            "event_id": "evt_a3",
            "event_type": "marketplace.price.alert",
            "version": "1.0",
            "workspace_id": "RODDOS",
            "timestamp_utc": now - timedelta(hours=47),
            "producer": "alerts_agent",
            "correlation_id": None,
            "causation_id": None,
            "payload": {
                "sku_normalizado": "fb_marketplace:FB-C",
                "titulo": "Cadena",
                "precio_anterior": 80000,
                "precio_actual": 60000,
                "delta_pct": -25.0,
                "fuente": "fb",
                "competitor_url": "https://fb.example/c",
            },
            "metadata": {},
        },
        # Vieja · 49h (fuera de la ventana 48h)
        {
            "event_id": "evt_a4_old",
            "event_type": "marketplace.price.alert",
            "version": "1.0",
            "workspace_id": "RODDOS",
            "timestamp_utc": now - timedelta(hours=49),
            "producer": "alerts_agent",
            "correlation_id": None,
            "causation_id": None,
            "payload": {
                "sku_normalizado": "meli:MCO-OLD",
                "titulo": "Vieja",
                "precio_anterior": 1,
                "precio_actual": 1,
                "delta_pct": -20.0,
                "fuente": "meli",
                "competitor_url": "",
            },
            "metadata": {},
        },
    ]
    await db[col.ARGOS_EVENTS].insert_many(events)
    try:
        yield db
    finally:
        for c in col.ALL_KNOWN:
            await db[c].drop()
        client.close()


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


async def test_endpoint_returns_200_con_lista(
    seeded_alerts_db: AsyncIOMotorDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = {"Authorization": f"Bearer {_ceo_token()}", "X-Workspace-Id": "RODDOS"}
    async for client in _authed_client(monkeypatch):
        resp = await client.get("/api/v1/alerts/recent", headers=headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert isinstance(body, list)

        # Schema correcto
        assert all("sku_normalizado" in a and "delta_pct" in a for a in body)


async def test_endpoint_filtra_por_48h_y_excluye_viejas(
    seeded_alerts_db: AsyncIOMotorDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = {"Authorization": f"Bearer {_ceo_token()}", "X-Workspace-Id": "RODDOS"}
    async for client in _authed_client(monkeypatch):
        resp = await client.get("/api/v1/alerts/recent?limit=10", headers=headers)
        body = resp.json()

        # 3 alertas dentro de 48h · 1 fuera · debe devolver exactamente 3
        assert len(body) == 3
        skus = {a["sku_normalizado"] for a in body}
        assert "meli:MCO-OLD" not in skus
        assert {"meli:MCO-A", "meli:MCO-B", "fb_marketplace:FB-C"} == skus

        # Ordenado por timestamp desc · más reciente primero
        timestamps = [a["timestamp_utc"] for a in body]
        assert timestamps == sorted(timestamps, reverse=True)
