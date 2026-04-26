"""Tests de los endpoints /api/v1/briefing/today + /history."""
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
async def seeded_db() -> AsyncIterator[AsyncIOMotorDatabase]:
    client = AsyncIOMotorClient(REAL_URI, serverSelectionTimeoutMS=5000)
    db = client[os.environ.get("MONGODB_TEST_DATABASE", "argos_test")]
    for c in col.ALL_KNOWN:
        await db[c].drop()
    await ensure_indexes(db)

    now = datetime.now(tz=UTC)
    docs = [
        {
            "workspace_id": "RODDOS",
            "fecha": (now - timedelta(days=i)).strftime("%Y-%m-%d"),
            "mercado_24h": {"nuevos_skus": i, "bajas_precio": 0, "nuevas_promos": 0},
            "acciones_del_dia": [
                {
                    "accion": f"acción día -{i}",
                    "justificacion": "x",
                    "impacto_esperado": "y",
                    "prioridad": "Media",
                }
            ],
            "estado_mercado": f"Estado día -{i}",
            "modelo_usado": "claude-sonnet-4-6-20260301",
            "tokens_input": 1500,
            "tokens_output": 400,
            "created_at": now - timedelta(days=i),
            "updated_at": now - timedelta(days=i),
        }
        for i in range(8)  # 8 briefings · today + 7 anteriores
    ]
    await db[col.BRIEFINGS].insert_many(docs)
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


async def test_briefing_today_devuelve_briefing_de_hoy(
    seeded_db: AsyncIOMotorDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = {"Authorization": f"Bearer {_ceo_token()}", "X-Workspace-Id": "RODDOS"}
    today = datetime.now(tz=UTC).strftime("%Y-%m-%d")
    async for client in _authed_client(monkeypatch):
        resp = await client.get("/api/v1/briefing/today", headers=headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["fecha"] == today
        assert body["mercado_24h"]["nuevos_skus"] == 0  # día más reciente
        assert "acciones_del_dia" in body


async def test_briefing_history_limita_y_ordena_desc(
    seeded_db: AsyncIOMotorDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = {"Authorization": f"Bearer {_ceo_token()}", "X-Workspace-Id": "RODDOS"}
    async for client in _authed_client(monkeypatch):
        resp = await client.get("/api/v1/briefing/history?limit=7", headers=headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert len(body) == 7  # default limit · seeded 8 pero pide 7
        fechas = [b["fecha"] for b in body]
        assert fechas == sorted(fechas, reverse=True)
