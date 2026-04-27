"""Tests del DiscoveryAgent · trending/rising/disappearing sobre products_catalog mock."""
from __future__ import annotations

import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from argos.agents.discovery.service import DiscoveryAgent, run_discovery_job
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


async def _seed_products(
    db: AsyncIOMotorDatabase,
    *,
    workspace_id: str,
    nombre: str,
    sku: str,
    count: int,
    when: datetime,
    precio: float = 50000,
) -> None:
    docs = []
    for i in range(count):
        docs.append(
            {
                "workspace_id": workspace_id,
                "sku_normalizado": sku,
                "source": "meli",
                "source_id": f"{sku}-{i}-{when.timestamp()}",
                "nombre": nombre,
                "categoria": "repuestos_moto",
                "precio_actual": precio + (i * 100),
                "created_at": when,
                "updated_at": when,
            }
        )
    if docs:
        await db[col.PRODUCTS_CATALOG].insert_many(docs)


async def test_discover_trending_filtra_terminos_existentes(
    indexed_db: AsyncIOMotorDatabase,
) -> None:
    now = datetime.now(tz=UTC)
    # SKU nuevo con muchas detecciones recientes
    await _seed_products(
        indexed_db, workspace_id="RODDOS",
        nombre="Casco modular smart helmet",
        sku="CASCO-MOD-001", count=12, when=now - timedelta(days=2),
    )
    # Y otro que YA está en watch_queries · debe filtrarse
    await indexed_db[col.WATCH_QUERIES].insert_one({
        "workspace_id": "RODDOS",
        "query": "filtro aire",
        "source": "all",
        "origin": "manual",
        "status": "active",
        "activa": True,
        "priority": 1,
        "created_at": now,
    })
    await _seed_products(
        indexed_db, workspace_id="RODDOS",
        nombre="filtro aire moto pulsar",
        sku="FIL-AIR-002", count=10, when=now - timedelta(days=1),
    )

    agent = DiscoveryAgent()
    suggestions = await agent.discover_trending(
        indexed_db, workspace_id="RODDOS", category="repuestos_moto"
    )
    # `casco modular smart` debería aparecer · `filtro aire` no
    terms = [s["term"] for s in suggestions]
    assert any("casco modular" in t for t in terms)
    assert not any("filtro aire" in t for t in terms)


async def test_discover_rising_detecta_burst_48h(
    indexed_db: AsyncIOMotorDatabase,
) -> None:
    now = datetime.now(tz=UTC)
    # >10 publicaciones en últimas 48h con precios bajando >15%
    await _seed_products(
        indexed_db, workspace_id="RODDOS",
        nombre="Aceite Castrol Power 1",
        sku="ACEITE-CAS-001", count=15, when=now - timedelta(hours=24),
        precio=70000,
    )
    # Y un SKU del mismo con precio mucho menor (señal liquidación)
    await indexed_db[col.PRODUCTS_CATALOG].insert_one({
        "workspace_id": "RODDOS",
        "sku_normalizado": "ACEITE-CAS-001",
        "source": "meli",
        "source_id": "liq-1",
        "nombre": "Aceite Castrol Power 1",
        "categoria": "repuestos_moto",
        "precio_actual": 50000,  # ~30% menos
        "created_at": now - timedelta(hours=12),
        "updated_at": now,
    })

    agent = DiscoveryAgent()
    suggestions = await agent.discover_rising_products(
        indexed_db, workspace_id="RODDOS", category="repuestos_moto"
    )
    assert any(s["signal_type"] == "liquidating" for s in suggestions)


async def test_run_discovery_job_emite_evento_y_persiste(
    indexed_db: AsyncIOMotorDatabase,
) -> None:
    now = datetime.now(tz=UTC)
    await indexed_db[col.CATEGORIES].insert_one({
        "workspace_id": "RODDOS",
        "slug": "repuestos_moto",
        "label": "Repuestos para moto",
        "active": True,
        "created_at": now,
    })
    await _seed_products(
        indexed_db, workspace_id="RODDOS",
        nombre="Pastilla freno Bajaj",
        sku="PAST-BAJ-001", count=15, when=now - timedelta(hours=20),
    )

    result = await run_discovery_job(indexed_db, workspace_id="RODDOS")
    assert result["categories"] == 1
    assert len(result["stats"]) >= 1

    # Sugerencias persistidas
    count = await indexed_db[col.DISCOVERY_SUGGESTIONS].count_documents(
        {"workspace_id": "RODDOS"}
    )
    assert count >= 1

    # Evento emitido
    event = await indexed_db[col.ARGOS_EVENTS].find_one(
        {"event_type": "discovery.suggestions.generated"}
    )
    assert event is not None
    assert event["payload"]["category"] == "repuestos_moto"
    assert event["producer"] == "discovery_agent"
