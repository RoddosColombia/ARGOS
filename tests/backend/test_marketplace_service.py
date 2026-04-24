"""Integración real contra Atlas (argos_test) · reusa fixture indexed_db de
test_integration_mongo.py via import directo.
"""
from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from argos.agents.marketplace.service import (
    PRICE_CHANGE_THRESHOLD_PCT,
    upsert_product,
)
from argos.db import collections as col
from argos.db.indexes import ensure_indexes
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


def _meli(id_: str, title: str, price: float, stock: int = 5) -> dict:
    return {
        "id": id_,
        "title": title,
        "price": price,
        "available_quantity": stock,
        "seller": {"id": 42},
        "thumbnail": "https://example.com/thumb.jpg",
        "permalink": "https://example.com/item",
        "category_id": "MCO1234",
        "condition": "new",
    }


async def test_upsert_creates_new_product(indexed_db: AsyncIOMotorDatabase) -> None:
    result = await upsert_product(indexed_db, _meli("MCO-100", "Aceite 20W50", 45000), emit_events=False)
    assert result is not None
    assert result.created is True
    assert result.sku_normalizado == "meli:MCO-100"
    assert result.price_change_delta_pct is None

    doc = await indexed_db[col.PRODUCTS_CATALOG].find_one({"source": "meli", "source_id": "MCO-100"})
    assert doc is not None
    assert doc["nombre"] == "Aceite 20W50"
    assert doc["precio_actual"] == 45000
    assert doc["categoria"] == ""  # Build 1.1 lo llena
    assert doc["categoria_meli_id"] == "MCO1234"


async def test_upsert_detects_price_change_above_threshold(indexed_db: AsyncIOMotorDatabase) -> None:
    await upsert_product(indexed_db, _meli("MCO-101", "Pastillas freno", 50000), emit_events=False)
    # Subida del 20% → debe marcar price change
    result = await upsert_product(indexed_db, _meli("MCO-101", "Pastillas freno", 60000), emit_events=False)

    assert result is not None
    assert result.created is False
    assert result.price_change_delta_pct is not None
    assert result.price_change_delta_pct == 20.0


async def test_upsert_ignores_small_price_change(indexed_db: AsyncIOMotorDatabase) -> None:
    await upsert_product(indexed_db, _meli("MCO-102", "Filtro aire", 10000), emit_events=False)
    # Subida del 3% < threshold 5% → NO marca price change
    result = await upsert_product(indexed_db, _meli("MCO-102", "Filtro aire", 10300), emit_events=False)

    assert result is not None
    assert result.price_change_delta_pct is None
    assert PRICE_CHANGE_THRESHOLD_PCT == 5.0  # guardrail del threshold


async def test_upsert_deduplicates_by_source_id(indexed_db: AsyncIOMotorDatabase) -> None:
    await upsert_product(indexed_db, _meli("MCO-103", "Bujía NGK", 15000), emit_events=False)
    await upsert_product(indexed_db, _meli("MCO-103", "Bujía NGK (v2)", 16000), emit_events=False)

    count = await indexed_db[col.PRODUCTS_CATALOG].count_documents({"source_id": "MCO-103"})
    assert count == 1
    doc = await indexed_db[col.PRODUCTS_CATALOG].find_one({"source_id": "MCO-103"})
    assert doc is not None
    assert doc["nombre"] == "Bujía NGK (v2)"  # últ update gana


async def test_upsert_detecta_compatible_motos(indexed_db: AsyncIOMotorDatabase) -> None:
    result = await upsert_product(
        indexed_db,
        _meli("MCO-104", "Kit arrastre TVS Raider 125 original", 120000),
        emit_events=False,
    )
    assert result is not None
    doc = await indexed_db[col.PRODUCTS_CATALOG].find_one({"source_id": "MCO-104"})
    assert doc is not None
    assert "TVS Raider 125" in doc["compatible_motos"]


async def test_upsert_emits_events_when_created_and_on_price_change(
    indexed_db: AsyncIOMotorDatabase,
) -> None:
    # Crear → emite marketplace.product.detected
    await upsert_product(indexed_db, _meli("MCO-200", "Cadena 428H", 80000), emit_events=True)
    detected = await indexed_db[col.ARGOS_EVENTS].find_one(
        {"event_type": "marketplace.product.detected", "payload.source_id": "MCO-200"}
    )
    assert detected is not None
    assert detected["payload"]["created"] is True

    # Price change ≥ 5% → emite marketplace.price.changed
    await upsert_product(indexed_db, _meli("MCO-200", "Cadena 428H", 90000), emit_events=True)
    changed = await indexed_db[col.ARGOS_EVENTS].find_one(
        {"event_type": "marketplace.price.changed", "payload.source_id": "MCO-200"}
    )
    assert changed is not None
    assert changed["payload"]["price_before"] == 80000
    assert changed["payload"]["price_after"] == 90000
    assert changed["payload"]["delta_pct"] == 12.5


async def test_upsert_writes_history_on_price_change(indexed_db: AsyncIOMotorDatabase) -> None:
    await upsert_product(indexed_db, _meli("MCO-300", "Llanta 130/70", 200000), emit_events=False)
    await upsert_product(indexed_db, _meli("MCO-300", "Llanta 130/70", 220000), emit_events=False)

    history = await indexed_db[col.PRODUCTS_HISTORY].count_documents({"source": "meli"})
    # 2 entries: created + price change
    assert history == 2


async def test_upsert_skips_invalid_item(indexed_db: AsyncIOMotorDatabase) -> None:
    result = await upsert_product(indexed_db, {"id": "X", "title": ""}, emit_events=False)
    assert result is None

    count = await indexed_db[col.PRODUCTS_CATALOG].count_documents({})
    assert count == 0
