"""Tests del Competitors Meta Ads service · contra Mongo real + Apify mockeado."""
from __future__ import annotations

import os
from collections.abc import AsyncIterator
from typing import Any

import pytest
import pytest_asyncio
from argos.agents.competitors.meta_ads_service import (
    parse_apify_ad_item,
    upsert_meta_ad,
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


def _ad(
    *,
    ad_id: str = "ARCHIVE-123",
    page: str = "Repuestos Bogotá Online",
    body: str = "Las mejores pastillas freno · envío gratis",
    title: str = "Pastillas freno Pulsar · 30% off",
    link_url: str = "https://repuestos-bogota.com/pastillas",
    start: str | None = "2026-04-01T00:00:00Z",
    stop: str | None = None,
    creative_type: str = "video",
) -> dict[str, Any]:
    return {
        "ad_archive_id": ad_id,
        "page_name": page,
        "ad_creative_body": body,
        "ad_creative_link_title": title,
        "ad_creative_link_url": link_url,
        "ad_delivery_start_time": start,
        "ad_delivery_stop_time": stop,
        "creative_type": creative_type,
    }


def test_parse_normaliza_apify_ad_a_schema_interno() -> None:
    parsed = parse_apify_ad_item(_ad())
    assert parsed is not None
    assert parsed["ad_id_externo"] == "ARCHIVE-123"
    assert parsed["anunciante"] == "Repuestos Bogotá Online"
    assert "pastillas" in parsed["copy_texto"].lower()
    assert parsed["url_landing"].startswith("https://")
    assert parsed["formato"] == "video"
    assert parsed["activo"] is True  # stop_time es None
    assert parsed["durabilidad_dias"] >= 1


def test_parse_marca_inactivo_cuando_hay_stop_time() -> None:
    raw = _ad(start="2026-04-01T00:00:00Z", stop="2026-04-15T00:00:00Z")
    parsed = parse_apify_ad_item(raw)
    assert parsed is not None
    assert parsed["activo"] is False
    assert parsed["durabilidad_dias"] == 14


def test_parse_devuelve_none_sin_id_o_pagina() -> None:
    no_id = _ad()
    no_id.pop("ad_archive_id")
    assert parse_apify_ad_item(no_id) is None

    no_page = _ad()
    no_page["page_name"] = ""
    assert parse_apify_ad_item(no_page) is None


def test_parse_detecta_formato_de_varios_aliases() -> None:
    assert parse_apify_ad_item(_ad(creative_type="VIDEO_CREATIVE"))["formato"] == "video"
    assert parse_apify_ad_item(_ad(creative_type="image"))["formato"] == "image"
    assert parse_apify_ad_item(_ad(creative_type="DCO_CAROUSEL"))["formato"] == "carousel"
    assert parse_apify_ad_item(_ad(creative_type="weird-type"))["formato"] == "unknown"


async def test_upsert_persiste_y_dedup_por_ad_id_externo(
    indexed_db: AsyncIOMotorDatabase,
) -> None:
    # Primera vez · created=True · emite evento
    created1, ad_id1 = await upsert_meta_ad(
        indexed_db, _ad(ad_id="UNIQ-1", body="copy v1"),
        workspace_id="RODDOS", fuente_query="pastillas freno moto",
    )
    assert created1 is True
    assert ad_id1 == "UNIQ-1"

    # Mismo ad con copy distinto · created=False · solo update
    created2, ad_id2 = await upsert_meta_ad(
        indexed_db, _ad(ad_id="UNIQ-1", body="copy v2 actualizado"),
        workspace_id="RODDOS", fuente_query="pastillas freno moto",
    )
    assert created2 is False
    assert ad_id2 == "UNIQ-1"

    count = await indexed_db[col.ADS_LIBRARY].count_documents({"ad_id_externo": "UNIQ-1"})
    assert count == 1
    doc = await indexed_db[col.ADS_LIBRARY].find_one({"ad_id_externo": "UNIQ-1"})
    assert doc["copy_texto"] == "copy v2 actualizado"

    # Solo se emitió 1 evento (en el create) · no en re-detection
    events_count = await indexed_db[col.ARGOS_EVENTS].count_documents(
        {"event_type": "competitors.ad.detected", "payload.ad_id_externo": "UNIQ-1"}
    )
    assert events_count == 1


async def test_upsert_devuelve_false_none_con_item_invalido(
    indexed_db: AsyncIOMotorDatabase,
) -> None:
    created, ad_id = await upsert_meta_ad(
        indexed_db, {"random_keys": "no_id"},
        workspace_id="RODDOS", fuente_query="x",
    )
    assert created is False
    assert ad_id is None
    count = await indexed_db[col.ADS_LIBRARY].count_documents({})
    assert count == 0
