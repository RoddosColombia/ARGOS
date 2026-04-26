"""Tests del MemoryAgent · Qdrant + OpenAI mockeados · sin red."""
from __future__ import annotations

import os
from collections.abc import AsyncIterator
from typing import Any

import pytest
import pytest_asyncio
from argos.agents.memory.service import (
    MemoryAgent,
    OpenAIEmbedder,
    embed_pending_job,
)
from argos.db import collections as col
from argos.db.indexes import ensure_indexes
from argos.partners.qdrant.client import (
    PRODUCTS_COLLECTION,
    QdrantBackend,
    QdrantHit,
)
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


class _FakeEmbedder(OpenAIEmbedder):
    """Embedder mockeado · vector sintético determinístico (1536 dim)."""

    def __init__(self, dim: int = 1536):
        super().__init__(api_key="fake-key")
        self._dim = dim
        self.calls: list[list[str]] = []

    @property
    def enabled(self) -> bool:
        return True

    async def embed(self, texts: list[str]) -> list[list[float]]:  # type: ignore[override]
        self.calls.append(list(texts))
        # Vector sintético basado en len(text) · suficiente para tests de wiring
        return [[float(i % 100) / 100.0] * self._dim for i, _ in enumerate(texts)]


class _FakeQdrant(QdrantBackend):
    """Qdrant mockeado · captura upserts en memoria · search retorna stub."""

    def __init__(self):
        super().__init__(url="http://fake-qdrant")
        self.upserts: list[dict[str, Any]] = []
        self.search_results: list[QdrantHit] = []

    @property
    def enabled(self) -> bool:
        return True

    async def ensure_collections(self) -> None:
        return None

    async def upsert_point(  # type: ignore[override]
        self, collection: str, *, point_id: str, vector: list[float], payload: dict[str, Any]
    ) -> bool:
        self.upserts.append(
            {"collection": collection, "point_id": point_id, "payload": payload, "vector_dim": len(vector)}
        )
        return True

    async def search(  # type: ignore[override]
        self, collection: str, *, query_vector: list[float], limit: int = 10, workspace_id: str = ""
    ) -> list[QdrantHit]:
        return list(self.search_results[:limit])

    async def close(self) -> None:
        return None


async def test_memory_embed_product_persiste_en_qdrant() -> None:
    qdrant = _FakeQdrant()
    embedder = _FakeEmbedder()
    agent = MemoryAgent(qdrant, embedder)

    fake_id = ObjectId()
    doc = {
        "_id": fake_id,
        "workspace_id": "RODDOS",
        "sku_normalizado": "meli:MCO-A",
        "nombre": "Aceite Motul 4T 20W50",
        "source": "meli",
        "precio_actual": 45000.0,
        "compatible_motos": ["TVS Raider 125", "Pulsar 200"],
        "categoria": "",
    }
    ok = await agent.embed_product(doc)
    assert ok is True
    assert len(qdrant.upserts) == 1
    upsert = qdrant.upserts[0]
    assert upsert["collection"] == PRODUCTS_COLLECTION
    assert upsert["point_id"] == str(fake_id)
    assert upsert["vector_dim"] == 1536
    assert upsert["payload"]["sku_normalizado"] == "meli:MCO-A"
    assert "TVS Raider 125" in upsert["payload"]["compatible_motos"]


async def test_memory_search_retorna_lista_vacia_sin_qdrant() -> None:
    """Sin Qdrant configurado · search debe devolver [] sin levantar 500."""
    qdrant = QdrantBackend(url="")  # disabled
    embedder = _FakeEmbedder()
    agent = MemoryAgent(qdrant, embedder)
    assert agent.enabled is False

    hits = await agent.search_similar_products("aceite moto", limit=5)
    assert hits == []


async def test_memory_search_retorna_hits_con_score() -> None:
    qdrant = _FakeQdrant()
    qdrant.search_results = [
        QdrantHit(point_id="p1", score=0.92, payload={"sku_normalizado": "meli:MCO-A", "nombre": "Aceite Motul"}),
        QdrantHit(point_id="p2", score=0.81, payload={"sku_normalizado": "meli:MCO-B", "nombre": "Aceite Mobil"}),
    ]
    embedder = _FakeEmbedder()
    agent = MemoryAgent(qdrant, embedder)

    hits = await agent.search_similar_products("aceite", limit=5, workspace_id="RODDOS")
    assert len(hits) == 2
    assert hits[0].score == 0.92
    assert hits[0].payload["sku_normalizado"] == "meli:MCO-A"
    # as_dict aplana payload + score
    flat = hits[0].as_dict()
    assert flat["score"] == 0.92
    assert flat["sku_normalizado"] == "meli:MCO-A"


async def test_embed_pending_job_solo_procesa_no_embedded(
    indexed_db: AsyncIOMotorDatabase,
) -> None:
    """Inserta 3 productos · 2 ya embedded · job procesa solo el pending."""
    qdrant = _FakeQdrant()
    embedder = _FakeEmbedder()
    agent = MemoryAgent(qdrant, embedder)

    from datetime import UTC, datetime
    now = datetime.now(tz=UTC)
    base = {
        "workspace_id": "RODDOS",
        "categoria": "",
        "compatible_motos": [],
        "stock_disponible": 1,
        "seller_id": "1",
        "imagen_url": "",
        "permalink": "",
        "condition": "new",
        "categoria_meli_id": "",
        "created_at": now,
        "updated_at": now,
    }

    # 2 ya embedded · 1 pending
    def _doc(sku: str, nombre: str, precio: float, embedded: bool) -> dict[str, Any]:
        d = {
            **base,
            "sku_normalizado": f"meli:{sku}",
            "source": "meli",
            "source_id": sku,
            "nombre": nombre,
            "precio_actual": precio,
        }
        if embedded:
            d["embedded_at"] = now
        return d

    await indexed_db[col.PRODUCTS_CATALOG].insert_many([
        _doc("A", "Aceite", 100, embedded=True),
        _doc("B", "Bujía", 200, embedded=True),
        _doc("C", "Cadena", 300, embedded=False),  # único pending
    ])

    stats = await embed_pending_job(indexed_db, agent=agent)
    assert stats["products_embedded"] == 1
    assert len(qdrant.upserts) == 1
    upsert = qdrant.upserts[0]
    assert upsert["payload"]["sku_normalizado"] == "meli:C"

    # El doc pending ahora tiene embedded_at
    doc = await indexed_db[col.PRODUCTS_CATALOG].find_one({"sku_normalizado": "meli:C"})
    assert doc["embedded_at"] is not None

    # Re-run del job: 0 pending nuevos
    qdrant.upserts.clear()
    stats2 = await embed_pending_job(indexed_db, agent=agent)
    assert stats2["products_embedded"] == 0
    assert qdrant.upserts == []
