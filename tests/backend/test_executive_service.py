"""Tests del Executive · publica briefing en Mongo + emite evento."""
from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from argos.agents.executive.service import ExecutiveAgent
from argos.agents.strategist.service import (
    AccionRecomendada,
    Mercado24h,
    MorningBriefing,
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


def _briefing_fixture(fecha: str = "2026-04-26") -> MorningBriefing:
    return MorningBriefing(
        fecha=fecha,
        mercado_24h=Mercado24h(nuevos_skus=3, bajas_precio=2, nuevas_promos=1),
        acciones_del_dia=[
            AccionRecomendada(
                accion="Bajar aceite Motul",
                justificacion="competencia",
                impacto_esperado="share",
                prioridad="Alta",
            ),
            AccionRecomendada(
                accion="Stockear pastillas",
                justificacion="lunes pico",
                impacto_esperado="evitar stockout",
                prioridad="Media",
            ),
        ],
        estado_mercado="Día agresivo en aceites.",
        tokens_input=1500,
        tokens_output=400,
    )


async def test_publish_briefing_persiste_y_emite_evento(
    indexed_db: AsyncIOMotorDatabase,
) -> None:
    executive = ExecutiveAgent()
    briefing = _briefing_fixture()

    result = await executive.publish_briefing(indexed_db, briefing, workspace_id="RODDOS")

    assert result.created is True
    assert result.fecha == "2026-04-26"
    assert result.num_acciones == 2

    # Persistido en briefings
    doc = await indexed_db[col.BRIEFINGS].find_one(
        {"workspace_id": "RODDOS", "fecha": "2026-04-26"}
    )
    assert doc is not None
    assert doc["mercado_24h"]["nuevos_skus"] == 3
    assert len(doc["acciones_del_dia"]) == 2
    assert doc["acciones_del_dia"][0]["prioridad"] == "Alta"

    # Evento briefing.published emitido
    event = await indexed_db[col.ARGOS_EVENTS].find_one({"event_type": "briefing.published"})
    assert event is not None
    assert event["payload"]["fecha"] == "2026-04-26"
    assert event["payload"]["num_acciones"] == 2
    assert event["producer"] == "executive_agent"


async def test_publish_briefing_idempotente_por_fecha(
    indexed_db: AsyncIOMotorDatabase,
) -> None:
    """Re-run del job en el mismo día: upsert (update) · no duplica · no cuenta como created."""
    executive = ExecutiveAgent()
    first = await executive.publish_briefing(
        indexed_db, _briefing_fixture(), workspace_id="RODDOS"
    )
    assert first.created is True

    # Segunda corrida con briefing actualizado
    updated = _briefing_fixture()
    updated.estado_mercado = "Update · más data llegó tarde."
    second = await executive.publish_briefing(indexed_db, updated, workspace_id="RODDOS")
    assert second.created is False  # ya existía

    # Solo 1 doc en briefings
    count = await indexed_db[col.BRIEFINGS].count_documents({"workspace_id": "RODDOS"})
    assert count == 1
    doc = await indexed_db[col.BRIEFINGS].find_one({"workspace_id": "RODDOS"})
    assert "más data" in doc["estado_mercado"]
