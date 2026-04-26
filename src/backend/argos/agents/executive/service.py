"""Executive Agent · Build 3.1 (Morning Briefing publisher).

Orquesta: pide briefing al Strategist · upsert en briefings · emite evento
`briefing.published`. Idempotente por (workspace_id, fecha) — re-runs del job
en el mismo día actualizan el briefing.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from argos.agents.strategist.recommendations import persist_recommendations_from_briefing
from argos.agents.strategist.service import MorningBriefing, StrategistAgent
from argos.config import get_settings
from argos.db import collections as col
from argos.db.events import publish_briefing_published

logger = logging.getLogger("argos.agents.executive")


@dataclass
class PublishResult:
    fecha: str
    created: bool
    num_acciones: int
    recommendations_created: int = 0


class ExecutiveAgent:
    """Persistencia + emisión de eventos sobre briefings."""

    async def publish_briefing(
        self,
        db: AsyncIOMotorDatabase,
        briefing: MorningBriefing,
        *,
        workspace_id: str,
    ) -> PublishResult:
        """Upsert idempotente por (workspace_id, fecha)."""
        now = datetime.now(tz=UTC)
        doc = briefing.as_dict()
        set_fields = {
            "workspace_id": workspace_id,
            "fecha": briefing.fecha,
            "mercado_24h": doc["mercado_24h"],
            "acciones_del_dia": doc["acciones_del_dia"],
            "estado_mercado": doc["estado_mercado"],
            "modelo_usado": briefing.modelo_usado,
            "tokens_input": briefing.tokens_input,
            "tokens_output": briefing.tokens_output,
            "updated_at": now,
        }
        set_on_insert = {"created_at": now}

        result = await db[col.BRIEFINGS].update_one(
            {"workspace_id": workspace_id, "fecha": briefing.fecha},
            {"$set": set_fields, "$setOnInsert": set_on_insert},
            upsert=True,
        )
        created = result.upserted_id is not None
        num_acciones = len(briefing.acciones_del_dia)

        # Build 3.3: resolver _id del briefing (upsert no lo expone si ya existía)
        briefing_doc = await db[col.BRIEFINGS].find_one(
            {"workspace_id": workspace_id, "fecha": briefing.fecha},
            {"_id": 1},
        )
        briefing_id = str(briefing_doc["_id"]) if briefing_doc else ""
        recs_created = 0
        if briefing_id:
            recs_created = await persist_recommendations_from_briefing(
                db, briefing, workspace_id=workspace_id, briefing_id=briefing_id
            )

        await publish_briefing_published(
            db,
            workspace_id=workspace_id,
            fecha=briefing.fecha,
            num_acciones=num_acciones,
            modelo_usado=briefing.modelo_usado,
        )

        logger.info(
            "briefing_published",
            extra={
                "workspace_id": workspace_id,
                "fecha": briefing.fecha,
                "was_created": created,  # `created` colisiona con LogRecord built-in
                "num_acciones": num_acciones,
                "recommendations_created": recs_created,
            },
        )
        return PublishResult(
            fecha=briefing.fecha,
            created=created,
            num_acciones=num_acciones,
            recommendations_created=recs_created,
        )


async def run_morning_briefing(
    db: AsyncIOMotorDatabase,
    *,
    workspace_id: str = "RODDOS",
    strategist: StrategistAgent | None = None,
    executive: ExecutiveAgent | None = None,
    use_memory: bool = True,
) -> dict[str, Any]:
    """Job entrypoint: Strategist genera + Executive publica · usado por scheduler.

    Build 3.2: si `use_memory=True` y MemoryAgent está habilitado (Qdrant + OpenAI
    configurados), el Strategist enriquece signals con productos/ads similares.
    """
    settings = get_settings()
    if strategist is None:
        if not settings.anthropic_api_key:
            logger.warning("morning_briefing_skipped_no_anthropic_key")
            return {"skipped": True, "reason": "no_anthropic_key"}
        strategist = StrategistAgent(api_key=settings.anthropic_api_key)
    if executive is None:
        executive = ExecutiveAgent()

    memory_agent = None
    if use_memory:
        # Lazy import · evita ciclo Strategist→Memory→Strategist
        from argos.agents.memory.service import _build_default_agent
        memory_agent = _build_default_agent()

    try:
        briefing = await strategist.generate_morning_briefing(
            db, workspace_id, memory_agent=memory_agent
        )
        result = await executive.publish_briefing(db, briefing, workspace_id=workspace_id)
        return {
            "fecha": result.fecha,
            "created": result.created,
            "num_acciones": result.num_acciones,
            "recommendations_created": result.recommendations_created,
            "modelo_usado": briefing.modelo_usado,
            "memory_enabled": memory_agent is not None and memory_agent.enabled,
        }
    finally:
        if memory_agent is not None:
            await memory_agent._qdrant.close()
