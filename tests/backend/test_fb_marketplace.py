"""Tests de FB Marketplace (Apify) · client mockeado + parser + upsert real."""
from __future__ import annotations

import os
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
import pytest_asyncio
from argos.agents.marketplace.fb_service import parse_apify_fb_item, upsert_fb_product
from argos.db import collections as col
from argos.db.indexes import ensure_indexes
from argos.partners.apify.client import ApifyClient
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


def _fb_item(
    title: str = "Pastillas freno Pulsar 200",
    price: Any = "$ 50.000",
    item_id: str = "1234567890",
) -> dict[str, Any]:
    return {
        "title": title,
        "price": price,
        "currency": "COP",
        "url": f"https://www.facebook.com/marketplace/item/{item_id}/",
        "image": "https://scontent.fbog.fbcdn.net/img.jpg",
        "seller": "Repuestos Bogotá",
        "location": "Bogotá",
        "condition": "used",
    }


def test_parser_normaliza_item_de_apify() -> None:
    parsed = parse_apify_fb_item(_fb_item())
    assert parsed is not None
    assert parsed["source"] == "fb_marketplace"
    assert parsed["source_id"] == "1234567890"
    assert parsed["nombre"] == "Pastillas freno Pulsar 200"
    assert parsed["precio_actual"] == 50000.0
    assert parsed["seller_id"] == "Repuestos Bogotá"
    assert parsed["permalink"].startswith("https://www.facebook.com/marketplace/item/")


def test_parser_devuelve_none_sin_id() -> None:
    bad = {"title": "Algo", "price": "1000"}  # sin url ni id
    assert parse_apify_fb_item(bad) is None


def test_parser_devuelve_none_sin_titulo() -> None:
    bad = _fb_item(title="")
    bad["title"] = None
    assert parse_apify_fb_item(bad) is None


def test_parser_acepta_precio_numerico_o_string() -> None:
    p1 = parse_apify_fb_item(_fb_item(price=75000))
    p2 = parse_apify_fb_item(_fb_item(price="$ 75.000 COP"))
    assert p1 is not None and p2 is not None
    assert p1["precio_actual"] == 75000.0
    assert p2["precio_actual"] == 75000.0


def test_apify_client_disabled_sin_token() -> None:
    client = ApifyClient(api_token="")
    assert client.enabled is False


async def test_apify_client_skip_silencioso_sin_token() -> None:
    """fb_marketplace_search devuelve [] sin levantar excepción cuando no hay token."""
    async with ApifyClient(api_token="") as client:
        items = await client.fb_marketplace_search("aceite moto")
        assert items == []


async def test_apify_client_propaga_429_como_apify_error() -> None:
    from argos.partners.apify.client import ApifyError

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "rate_limited"})

    async with ApifyClient(api_token="fake-token") as client:
        # Inyectar un transport mockeado
        client._client = httpx.AsyncClient(
            base_url="https://api.apify.com",
            transport=httpx.MockTransport(handler),
        )
        with pytest.raises(ApifyError) as exc:
            await client.fb_marketplace_search("aceite moto")
        assert exc.value.status == 429


async def test_upsert_fb_product_persiste_en_products_catalog(
    indexed_db: AsyncIOMotorDatabase,
) -> None:
    result = await upsert_fb_product(indexed_db, _fb_item(), emit_events=False)
    assert result is not None
    assert result.created is True
    assert result.sku_normalizado == "fb_marketplace:1234567890"

    doc = await indexed_db[col.PRODUCTS_CATALOG].find_one(
        {"source": "fb_marketplace", "source_id": "1234567890"}
    )
    assert doc is not None
    assert doc["nombre"] == "Pastillas freno Pulsar 200"
    assert doc["precio_actual"] == 50000.0


async def test_upsert_fb_product_y_meli_no_colisionan(
    indexed_db: AsyncIOMotorDatabase,
) -> None:
    """Item con mismo source_id en MELI y FB son docs separados."""
    from argos.agents.marketplace.service import upsert_product

    # FB
    await upsert_fb_product(indexed_db, _fb_item(item_id="111"), emit_events=False)
    # MELI con mismo source_id "111"
    await upsert_product(
        indexed_db,
        {"id": "111", "title": "Otro producto MELI", "price": 99000, "available_quantity": 1},
        emit_events=False,
    )
    count = await indexed_db[col.PRODUCTS_CATALOG].count_documents({})
    assert count == 2  # son entradas distintas, dedupe es por (source, source_id)
