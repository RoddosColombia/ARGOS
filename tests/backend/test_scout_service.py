from __future__ import annotations

import os
from collections.abc import AsyncIterator
from typing import Any

import pytest
import pytest_asyncio
from argos.agents.scout.service import tick
from argos.db import collections as col
from argos.db.indexes import ensure_indexes
from argos.partners.meli.client import MeliClient, MeliError
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from tests.backend.test_integration_mongo import REAL_URI

pytestmark = pytest.mark.skipif(
    not REAL_URI,
    reason="MONGODB_URI no disponible · integration tests saltados",
)


class _FakeMeliClient(MeliClient):
    """MeliClient mockeado para Scout tests · no toca red."""

    def __init__(self, responses: dict[str, list[dict[str, Any]]] | None = None, raise_on: set[str] | None = None):
        super().__init__()
        self._responses = responses or {}
        self._raise_on = raise_on or set()
        self.calls: list[str] = []

    async def __aenter__(self) -> _FakeMeliClient:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        return None

    async def search(self, query: str, **kwargs: Any) -> list[dict[str, Any]]:  # type: ignore[override]
        self.calls.append(query)
        if query in self._raise_on:
            raise MeliError(429, "Rate limited in fake")
        return list(self._responses.get(query, []))


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


def _item(id_: str, title: str, price: float) -> dict[str, Any]:
    return {
        "id": id_,
        "title": title,
        "price": price,
        "available_quantity": 3,
        "seller": {"id": 1},
        "thumbnail": "",
        "permalink": "",
        "category_id": "",
        "condition": "new",
    }


async def test_tick_procesa_queries_y_acumula_stats(indexed_db: AsyncIOMotorDatabase) -> None:
    fake = _FakeMeliClient(
        responses={
            "aceite moto": [_item("MCO-A1", "Aceite 20W50", 45000), _item("MCO-A2", "Aceite 10W40", 38000)],
            "filtro aire moto": [_item("MCO-F1", "Filtro aire universal", 15000)],
        }
    )
    stats = await tick(
        indexed_db,
        client=fake,
        queries=("aceite moto", "filtro aire moto"),
    )

    assert stats.queries_processed == 2
    assert stats.products_detected == 3
    assert stats.products_created == 3
    assert stats.products_price_changed == 0
    assert stats.errors == []


async def test_tick_aisla_error_en_una_query(indexed_db: AsyncIOMotorDatabase) -> None:
    fake = _FakeMeliClient(
        responses={"aceite moto": [_item("MCO-B1", "Aceite 20W50", 45000)]},
        raise_on={"batería moto"},
    )
    stats = await tick(
        indexed_db,
        client=fake,
        queries=("aceite moto", "batería moto"),
    )

    assert stats.queries_processed == 1  # solo la exitosa
    assert stats.products_detected == 1
    assert len(stats.errors) == 1
    assert stats.errors[0]["query"] == "batería moto"
    assert "meli_429" in stats.errors[0]["error"]


async def test_tick_detecta_price_change_en_segunda_pasada(indexed_db: AsyncIOMotorDatabase) -> None:
    fake_first = _FakeMeliClient(
        responses={"aceite moto": [_item("MCO-C1", "Aceite 20W50", 50000)]}
    )
    await tick(indexed_db, client=fake_first, queries=("aceite moto",))

    fake_second = _FakeMeliClient(
        responses={"aceite moto": [_item("MCO-C1", "Aceite 20W50", 60000)]}
    )
    stats = await tick(indexed_db, client=fake_second, queries=("aceite moto",))

    assert stats.products_price_changed == 1
    count = await indexed_db[col.PRODUCTS_CATALOG].count_documents({"source_id": "MCO-C1"})
    assert count == 1
