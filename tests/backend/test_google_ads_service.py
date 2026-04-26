"""Tests del Competitors Google Ads service · Mongo real + SerpAPI mockeado."""
from __future__ import annotations

import os
from collections.abc import AsyncIterator
from typing import Any

import pytest
import pytest_asyncio
from argos.agents.competitors.google_ads_service import (
    parse_serpapi_google_ad,
    refresh_google_ads,
    upsert_google_ad,
)
from argos.db import collections as col
from argos.db.indexes import ensure_indexes
from argos.partners.serpapi.client import SerpApiClient
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
    creative_id: str = "G-CREATIVE-123",
    advertiser: str = "Repuestos Online SAS",
    headline: str = "Aceite Motul al mejor precio",
    creative_text: str = "Envío a toda Colombia · garantía 90 días",
    landing: str = "https://repuestos-online.com/aceite",
    first: str = "2026-04-01",
    last: str | None = None,
    fmt: str = "RESPONSIVE_SEARCH_AD",
) -> dict[str, Any]:
    return {
        "creative_id": creative_id,
        "advertiser_name": advertiser,
        "headline": headline,
        "creative_text": creative_text,
        "destination_url": landing,
        "first_shown": first,
        "last_shown": last,
        "format": fmt,
    }


def test_parse_normaliza_serpapi_google_ad_a_schema() -> None:
    parsed = parse_serpapi_google_ad(_ad())
    assert parsed is not None
    assert parsed["ad_id_externo"] == "G-CREATIVE-123"
    assert parsed["anunciante"] == "Repuestos Online SAS"
    assert "Motul" in parsed["copy_titulo"]
    assert "garantía" in parsed["copy_texto"]
    assert parsed["url_landing"].startswith("https://")
    assert parsed["activo"] is True  # last_shown es None
    assert parsed["formato"] == "image"  # responsive search se renderiza visual


def test_parse_marca_inactivo_si_last_shown_es_viejo() -> None:
    raw = _ad(first="2026-01-01", last="2026-02-01")  # diff > 7 días
    parsed = parse_serpapi_google_ad(raw)
    assert parsed is not None
    assert parsed["activo"] is False
    assert parsed["durabilidad_dias"] == 31


def test_parse_devuelve_none_sin_id_o_advertiser() -> None:
    no_id = _ad()
    no_id.pop("creative_id")
    assert parse_serpapi_google_ad(no_id) is None

    no_adv = _ad()
    no_adv["advertiser_name"] = ""
    assert parse_serpapi_google_ad(no_adv) is None


def test_parse_detecta_formatos_google() -> None:
    assert parse_serpapi_google_ad(_ad(fmt="VIDEO_AD"))["formato"] == "video"
    assert parse_serpapi_google_ad(_ad(fmt="IMAGE_AD"))["formato"] == "image"
    assert parse_serpapi_google_ad(_ad(fmt="TEXT_AD"))["formato"] == "text"
    assert parse_serpapi_google_ad(_ad(fmt="UNKNOWN_TYPE"))["formato"] == "unknown"


async def test_upsert_persiste_y_acumula_keywords_pautadas(
    indexed_db: AsyncIOMotorDatabase,
) -> None:
    # Mismo ad detectado por dos queries distintas
    await upsert_google_ad(
        indexed_db, _ad(creative_id="G-X1"),
        workspace_id="RODDOS", fuente_query="aceite moto",
    )
    created2, _ = await upsert_google_ad(
        indexed_db, _ad(creative_id="G-X1"),
        workspace_id="RODDOS", fuente_query="aceite Motul",
    )
    assert created2 is False  # mismo ad

    doc = await indexed_db[col.ADS_LIBRARY].find_one(
        {"plataforma": "google", "ad_id_externo": "G-X1"}
    )
    assert doc is not None
    # keywords_pautadas acumula ambas queries
    assert sorted(doc["keywords_pautadas"]) == sorted(["aceite moto", "aceite Motul"])

    # Solo se emitió 1 evento (en el create)
    events = await indexed_db[col.ARGOS_EVENTS].count_documents(
        {"event_type": "competitors.ad.detected", "payload.ad_id_externo": "G-X1"}
    )
    assert events == 1


async def test_refresh_google_ads_skip_silencioso_sin_serpapi_key(
    indexed_db: AsyncIOMotorDatabase,
) -> None:
    """Sin SERPAPI_API_KEY el refresh termina con stats vacíos sin levantar."""
    # Agregar al menos una watch_query activa para no quedarse en early return
    await indexed_db[col.WATCH_QUERIES].insert_one(
        {
            "workspace_id": "RODDOS",
            "query": "aceite moto",
            "source": "all",
            "activa": True,
            "prioridad": 1,
        }
    )
    disabled_client = SerpApiClient(api_key="")  # disabled

    stats = await refresh_google_ads(indexed_db, serpapi_client=disabled_client)

    assert stats.queries_processed == 0
    assert stats.ads_detected == 0
    assert stats.errors == []
