"""Test del endpoint GET /api/v1/competitors/ads."""
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
    ads = [
        {
            "workspace_id": "RODDOS",
            "plataforma": "meta",
            "ad_id_externo": f"AD-{i}",
            "anunciante": f"Vendor {i}",
            "copy_texto": f"copy {i}",
            "copy_titulo": f"titulo {i}",
            "url_landing": f"https://example.com/{i}",
            "fecha_inicio": now - timedelta(days=i),
            "fecha_fin": None,
            "durabilidad_dias": i,
            "formato": "video" if i % 2 == 0 else "image",
            "activo": True,
            "fuente_query": "pastillas freno moto",
            "primera_deteccion": now,
            "ultima_deteccion": now,
            "created_at": now,
            "updated_at": now,
        }
        for i in range(5)
    ]
    await db[col.ADS_LIBRARY].insert_many(ads)
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


async def test_endpoint_devuelve_ads_meta_ordenados_por_fecha_inicio_desc(
    seeded_db: AsyncIOMotorDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = {"Authorization": f"Bearer {_ceo_token()}", "X-Workspace-Id": "RODDOS"}
    async for client in _authed_client(monkeypatch):
        resp = await client.get("/api/v1/competitors/ads?source=meta&limit=10", headers=headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert len(body) == 5
        assert all(a["plataforma"] == "meta" for a in body)

        # Schema completo
        item = body[0]
        for key in (
            "ad_id_externo", "anunciante", "copy_texto", "copy_titulo",
            "url_landing", "fecha_inicio", "durabilidad_dias", "formato",
            "activo", "fuente_query",
        ):
            assert key in item

        # Sort fecha_inicio desc · "AD-0" más reciente, "AD-4" más antiguo
        ad_ids = [a["ad_id_externo"] for a in body]
        assert ad_ids == ["AD-0", "AD-1", "AD-2", "AD-3", "AD-4"]
