"""Tests del Alerts service · contra Mongo real."""
from __future__ import annotations

import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from argos.agents.alerts.service import check_price_drops
from argos.db import collections as col
from argos.db.indexes import ensure_indexes
from bson import ObjectId
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


async def _seed_product_with_drop(
    db: AsyncIOMotorDatabase,
    *,
    sku: str,
    first_price: float,
    last_price: float,
    source: str = "meli",
) -> ObjectId:
    now = datetime.now(tz=UTC)
    product_id = (
        await db[col.PRODUCTS_CATALOG].insert_one(
            {
                "workspace_id": "RODDOS",
                "sku_normalizado": sku,
                "source": source,
                "source_id": sku.split(":")[1] if ":" in sku else sku,
                "nombre": f"Producto {sku}",
                "categoria": "",
                "compatible_motos": [],
                "precio_actual": last_price,
                "stock_disponible": 1,
                "seller_id": "1",
                "imagen_url": "",
                "permalink": f"https://example.com/{sku}",
                "condition": "new",
                "categoria_meli_id": "",
                "created_at": now,
                "updated_at": now,
            }
        )
    ).inserted_id

    await db[col.PRODUCTS_HISTORY].insert_many(
        [
            {
                "workspace_id": "RODDOS",
                "product_id": product_id,
                "timestamp": now - timedelta(hours=12),
                "precio": first_price,
                "stock": 1,
                "source": source,
            },
            {
                "workspace_id": "RODDOS",
                "product_id": product_id,
                "timestamp": now - timedelta(minutes=10),
                "precio": last_price,
                "stock": 1,
                "source": source,
            },
        ]
    )
    return product_id


async def test_detecta_price_drop_15_pct(indexed_db: AsyncIOMotorDatabase) -> None:
    await _seed_product_with_drop(indexed_db, sku="meli:MCO-DROP", first_price=100000, last_price=80000)

    alerts = await check_price_drops(indexed_db, threshold_pct=15.0, emit_events=False)

    assert len(alerts) == 1
    a = alerts[0]
    assert a.sku_normalizado == "meli:MCO-DROP"
    assert a.precio_anterior == 100000.0
    assert a.precio_actual == 80000.0
    assert a.delta_pct == -20.0
    assert a.fuente == "meli"


async def test_no_alerta_si_drop_menor_a_threshold(indexed_db: AsyncIOMotorDatabase) -> None:
    # Drop del 10% (menor que threshold 15%)
    await _seed_product_with_drop(
        indexed_db, sku="meli:MCO-SMALL", first_price=100000, last_price=90000
    )
    alerts = await check_price_drops(indexed_db, threshold_pct=15.0, emit_events=False)
    assert alerts == []


async def test_emite_evento_con_schema_correcto(indexed_db: AsyncIOMotorDatabase) -> None:
    await _seed_product_with_drop(
        indexed_db,
        sku="fb_marketplace:FB-DROP",
        first_price=200000,
        last_price=160000,  # -20%
        source="fb_marketplace",
    )

    await check_price_drops(indexed_db, threshold_pct=15.0, emit_events=True)

    event = await indexed_db[col.ARGOS_EVENTS].find_one(
        {"event_type": "marketplace.price.alert"}
    )
    assert event is not None
    payload = event["payload"]
    assert payload["sku_normalizado"] == "fb_marketplace:FB-DROP"
    assert payload["precio_anterior"] == 200000
    assert payload["precio_actual"] == 160000
    assert payload["delta_pct"] == -20.0
    assert payload["fuente"] == "fb"  # mapeado fb_marketplace → fb
    assert payload["competitor_url"].startswith("https://")
    assert event["producer"] == "alerts_agent"
