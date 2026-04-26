"""Tests del endpoint /api/v1/marketplace/top-products contra Atlas real."""
from __future__ import annotations

import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime

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
    # 3 productos MELI con precios distintos + 2 FB Marketplace
    products = [
        {
            "workspace_id": "RODDOS",
            "sku_normalizado": f"meli:MCO-{i}",
            "source": "meli",
            "source_id": f"MCO-{i}",
            "nombre": f"Producto MELI {i}",
            "categoria": "",
            "compatible_motos": [],
            "precio_actual": 100000 + i * 1000,
            "stock_disponible": 5,
            "seller_id": "1",
            "imagen_url": "",
            "permalink": f"https://meli.example/{i}",
            "condition": "new",
            "categoria_meli_id": "",
            "created_at": now,
            "updated_at": now,
        }
        for i in range(3)
    ] + [
        {
            "workspace_id": "RODDOS",
            "sku_normalizado": f"fb_marketplace:FB-{i}",
            "source": "fb_marketplace",
            "source_id": f"FB-{i}",
            "nombre": f"Producto FB {i}",
            "categoria": "",
            "compatible_motos": [],
            "precio_actual": 50000 + i * 500,
            "stock_disponible": 1,
            "seller_id": "vendor",
            "imagen_url": "",
            "permalink": f"https://fb.example/{i}",
            "condition": "used",
            "categoria_meli_id": "",
            "created_at": now,
            "updated_at": now,
        }
        for i in range(2)
    ]
    await db[col.PRODUCTS_CATALOG].insert_many(products)
    try:
        yield db
    finally:
        for c in col.ALL_KNOWN:
            await db[c].drop()
        client.close()


def _ceo_token(workspace_id: str = "RODDOS") -> str:
    return create_access_token(subject="ceo@roddos.com", role="ceo", workspace_id=workspace_id)


async def _authed_client(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[httpx.AsyncClient]:
    """Crea TestClient async configurado contra el cluster real."""
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


async def test_top_products_returns_200_con_lista(
    seeded_db: AsyncIOMotorDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sin filtro: devuelve los 5 productos sembrados ordenados por precio_promedio desc."""
    headers = {"Authorization": f"Bearer {_ceo_token()}", "X-Workspace-Id": "RODDOS"}

    async for client in _authed_client(monkeypatch):
        resp = await client.get("/api/v1/marketplace/top-products", headers=headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert isinstance(body, list)
        assert len(body) == 5

        # Ordenado por precio_promedio desc · MELI=100K-102K, FB=50K-50.5K
        assert body[0]["fuente"] == "meli"
        assert body[-1]["fuente"] == "fb"

        # Schema correcto en cada item
        item = body[0]
        for key in (
            "sku_normalizado",
            "titulo",
            "fuente",
            "precio_actual",
            "precio_promedio",
            "cambio_precio_pct",
            "ultima_actualizacion",
        ):
            assert key in item

        # cambio_precio_pct = 0 cuando no hay history (precio_promedio = precio_actual)
        assert item["cambio_precio_pct"] == 0


async def test_top_products_filtra_por_source(
    seeded_db: AsyncIOMotorDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = {"Authorization": f"Bearer {_ceo_token()}", "X-Workspace-Id": "RODDOS"}

    async for client in _authed_client(monkeypatch):
        resp_meli = await client.get(
            "/api/v1/marketplace/top-products?source=meli", headers=headers
        )
        resp_fb = await client.get(
            "/api/v1/marketplace/top-products?source=fb", headers=headers
        )
        resp_all = await client.get(
            "/api/v1/marketplace/top-products?source=all", headers=headers
        )

        assert resp_meli.status_code == 200
        assert resp_fb.status_code == 200
        assert resp_all.status_code == 200

        meli_items = resp_meli.json()
        fb_items = resp_fb.json()
        all_items = resp_all.json()

        assert len(meli_items) == 3
        assert all(i["fuente"] == "meli" for i in meli_items)

        assert len(fb_items) == 2
        assert all(i["fuente"] == "fb" for i in fb_items)

        assert len(all_items) == 5
