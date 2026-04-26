"""Recommendations: persistencia + impact tracking · Build 3.3.

Cuando el ExecutiveAgent publica un briefing, este módulo crea documentos
en `recommendations` (uno por accion_del_dia) con:

- expected_impact (hipótesis del Strategist)
- priority_score derivado de prioridad ("Alta"=0.9, "Media"=0.6, "Baja"=0.3)
- type heurístico desde el verbo de la acción ("bajar"/"subir" → pricing_change,
  "activar campaña" → ad_campaign, etc.) · default `pricing_change`
- status="pendiente"
- shown_in_briefing=[fecha]

Idempotencia: `(workspace_id, briefing_id, accion_index)` unique. Re-runs del
job mismo día actualizan el briefing pero NO crean nuevas recommendations
para acciones que ya existen (la unicidad protege).

Build 3.3: la transición a `ejecutada` la dispara el CEO desde la UI o
manual mongo update · esta build NO automatiza la ejecución de la acción.
"""
from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from argos.agents.strategist.service import AccionRecomendada, MorningBriefing
from argos.db import collections as col
from argos.db.events import publish_recommendation_created

logger = logging.getLogger("argos.agents.strategist.recommendations")

PRIORITY_TO_SCORE: dict[str, float] = {"Alta": 0.9, "Media": 0.6, "Baja": 0.3}

# Tipos canónicos · ver colecciones_mongo.md `recommendations.type`
_TYPE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("pricing_change", re.compile(r"\b(bajar|subir|ajustar)\s+(?:el\s+)?precio", re.IGNORECASE)),
    ("promo_launch", re.compile(r"\b(activar|lanzar|crear)\s+(?:promo|cupon|descuento|oferta)", re.IGNORECASE)),
    ("ad_campaign", re.compile(r"\b(activar|lanzar|pausar)\s+(?:campaña|ad)", re.IGNORECASE)),
    ("inventory_reorder", re.compile(r"\b(stockear|reordenar|comprar)\s+(?:inventario|stock|unidades)", re.IGNORECASE)),
    (
        "competitive_response",
        re.compile(r"\b(responder|igualar|matchear)\s+(?:competidor|al competidor)", re.IGNORECASE),
    ),
    ("portfolio_add", re.compile(r"\b(agregar|añadir)\s+(?:al?\s+(?:portafolio|catálogo))", re.IGNORECASE)),
    ("portfolio_drop", re.compile(r"\b(quitar|sacar|descontinuar)", re.IGNORECASE)),
]


def derive_type(action_text: str) -> str:
    for type_name, pattern in _TYPE_PATTERNS:
        if pattern.search(action_text):
            return type_name
    return "pricing_change"  # default


def build_expected_impact(accion: AccionRecomendada) -> dict[str, Any]:
    """Convierte el campo `impacto_esperado` (texto libre) en dict estructurado.

    Build 3.3: heurística simple · target=texto libre · confidence basado en
    prioridad (Alta=0.7, Media=0.5, Baja=0.3). Build 5+ puede pedir al
    Strategist devolver expected_impact ya estructurado en el JSON output.
    """
    confidence_by_prio = {"Alta": 0.7, "Media": 0.5, "Baja": 0.3}
    return {
        "metric": "qualitative",  # placeholder · Build 5+ extrae métrica concreta
        "baseline": "",
        "target": accion.impacto_esperado[:300],
        "confidence": confidence_by_prio.get(accion.prioridad, 0.5),
    }


async def persist_recommendations_from_briefing(
    db: AsyncIOMotorDatabase,
    briefing: MorningBriefing,
    *,
    workspace_id: str,
    briefing_id: str,
) -> int:
    """Crea (o actualiza) docs en recommendations · uno por accion_del_dia.

    Devuelve el número de recommendations CREADAS (no las re-detectadas).
    Idempotente vía índice unique (workspace, briefing_id, accion_index).
    """
    now = datetime.now(tz=UTC)
    created_count = 0

    for idx, accion in enumerate(briefing.acciones_del_dia):
        type_ = derive_type(accion.accion)
        expected = build_expected_impact(accion)
        set_fields: dict[str, Any] = {
            "workspace_id": workspace_id,
            "briefing_id": briefing_id,
            "accion_index": idx,
            "type": type_,
            "action_description": accion.accion,
            "rationale": accion.justificacion,
            "expected_impact": expected,
            "priority": accion.prioridad,
            "priority_score": PRIORITY_TO_SCORE.get(accion.prioridad, 0.5),
            "fecha_briefing": briefing.fecha,
            "updated_at": now,
        }
        set_on_insert: dict[str, Any] = {
            "status": "pendiente",
            "actual_impact": None,
            "hit_rate_contribution": None,
            "learning": None,
            "evidence_refs": [],
            # `shown_in_briefing` lo crea $addToSet abajo · evita conflict path 40
            "created_at": now,
        }

        result = await db[col.RECOMMENDATIONS].update_one(
            {
                "workspace_id": workspace_id,
                "briefing_id": briefing_id,
                "accion_index": idx,
            },
            {
                "$set": set_fields,
                "$setOnInsert": set_on_insert,
                "$addToSet": {"shown_in_briefing": briefing.fecha},
            },
            upsert=True,
        )
        if result.upserted_id is not None:
            created_count += 1
            await publish_recommendation_created(
                db,
                workspace_id=workspace_id,
                recommendation_id=str(result.upserted_id),
                type_=type_,
                priority=accion.prioridad,
                action_description=accion.accion,
                expected_impact=expected,
            )

    logger.info(
        "recommendations_persisted",
        extra={
            "briefing_id": briefing_id,
            "total_acciones": len(briefing.acciones_del_dia),
            "newly_created": created_count,
        },
    )
    return created_count
