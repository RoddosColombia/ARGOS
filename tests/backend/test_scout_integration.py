"""Tests de integración del Scout · tick completo desde Mongo y resiliente a fallas."""
from __future__ import annotations

import os
from collections.abc import AsyncIterator
from typing import Any

import pytest
import pytest_asyncio
from argos.agents.classifier.service import ClassifyResult
from argos.agents.scout.service import tick
from argos.db import collections as col
from argos.db.indexes import ensure_indexes
from argos.db.seed import seed_initial_data
from argos.partners.apify.client import ApifyClient, ApifyError
from argos.partners.meli.client import MeliClient
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from tests.backend.test_integration_mongo import REAL_URI

pytestmark = pytest.mark.skipif(
    not REAL_URI,
    reason="MONGODB_URI no disponible · integration tests saltados",
)


@pytest_asyncio.fixture
async def seeded_db() -> AsyncIterator[AsyncIOMotorDatabase]:
    """DB con índices + seed completo (incluye 11 watch queries)."""
    client = AsyncIOMotorClient(REAL_URI, serverSelectionTimeoutMS=5000)
    db = client[os.environ.get("MONGODB_TEST_DATABASE", "argos_test")]
    for c in col.ALL_KNOWN:
        await db[c].drop()
    await ensure_indexes(db)
    await seed_initial_data(db)
    try:
        yield db
    finally:
        for c in col.ALL_KNOWN:
            await db[c].drop()
        client.close()


class _FakeClassifier:
    """Acepta todo · útil para aislar el tick de Anthropic."""

    async def classify(self, _title: str, _description: str, _watch_query: str) -> ClassifyResult:
        return ClassifyResult(relevante=True, razon="fake_accept", cached=False)


class _FakeMeli(MeliClient):
    def __init__(self, responses: dict[str, list[dict[str, Any]]]):
        super().__init__()
        self._responses = responses

    async def __aenter__(self) -> _FakeMeli:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        return None

    async def search(self, query: str, **_kwargs: Any) -> list[dict[str, Any]]:  # type: ignore[override]
        return list(self._responses.get(query, []))


class _FakeApifyOK(ApifyClient):
    def __init__(self):
        super().__init__(api_token="fake")

    @property
    def enabled(self) -> bool:
        return True

    async def __aenter__(self) -> _FakeApifyOK:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        return None

    async def fb_marketplace_search(self, _query: str, **_kwargs: Any) -> list[dict[str, Any]]:
        return []


class _FakeApifyDown(ApifyClient):
    def __init__(self):
        super().__init__(api_token="fake")

    @property
    def enabled(self) -> bool:
        return True

    async def __aenter__(self) -> _FakeApifyDown:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        return None

    async def fb_marketplace_search(self, _query: str, **_kwargs: Any) -> list[dict[str, Any]]:
        raise ApifyError(503, "FB scraper down")


def _meli(id_: str, title: str, price: float) -> dict[str, Any]:
    return {
        "id": id_,
        "title": title,
        "price": price,
        "available_quantity": 1,
        "seller": {"id": 1},
        "thumbnail": "",
        "permalink": "",
        "category_id": "",
        "condition": "new",
    }


async def test_tick_lee_queries_de_mongo_y_persiste_solo_relevantes(
    seeded_db: AsyncIOMotorDatabase,
) -> None:
    # Limitar a 1 query para acotar
    await seeded_db[col.WATCH_QUERIES].update_many(
        {"workspace_id": "RODDOS"}, {"$set": {"activa": False}}
    )
    await seeded_db[col.WATCH_QUERIES].update_one(
        {"workspace_id": "RODDOS", "query": "aceite moto"},
        {"$set": {"activa": True, "source": "meli"}},
    )

    fake_meli = _FakeMeli({
        "aceite moto": [
            _meli("MCO-X1", "Aceite Motul 4T 20W50", 45000),
            _meli("MCO-X2", "Aceite Motul 4T 10W40", 38000),
        ],
    })

    stats = await tick(
        seeded_db,
        meli_client=fake_meli,
        apify_client=_FakeApifyOK(),
        classifier=_FakeClassifier(),
    )

    assert stats.queries_processed == 1
    assert stats.products_detected == 2
    assert stats.products_created == 2
    assert stats.products_discarded == 0

    count = await seeded_db[col.PRODUCTS_CATALOG].count_documents({"source": "meli"})
    assert count == 2


async def test_tick_no_falla_si_fb_apify_explota(
    seeded_db: AsyncIOMotorDatabase,
) -> None:
    """Watch query con source='all' · MELI funciona, FB Apify devuelve error.
    El tick debe completar la parte MELI y registrar error de FB sin tumbar el resto."""
    await seeded_db[col.WATCH_QUERIES].update_many(
        {"workspace_id": "RODDOS"}, {"$set": {"activa": False}}
    )
    await seeded_db[col.WATCH_QUERIES].update_one(
        {"workspace_id": "RODDOS", "query": "pastillas freno moto"},
        {"$set": {"activa": True, "source": "all"}},
    )

    fake_meli = _FakeMeli({
        "pastillas freno moto": [_meli("MCO-Y1", "Pastillas freno Pulsar", 35000)],
    })

    stats = await tick(
        seeded_db,
        meli_client=fake_meli,
        apify_client=_FakeApifyDown(),
        classifier=_FakeClassifier(),
    )

    # MELI procesó 1 producto, FB falló pero no tumbó el query
    assert stats.products_created == 1
    assert any("pastillas freno moto#fb" in e["query"] for e in stats.errors)
    assert any("apify_503" in e["error"] for e in stats.errors)
    # La query se considera procesada (la parte MELI funcionó)
    assert stats.queries_processed == 1
