"""Impact evaluation job · Build 3.3.

Job diario: por cada `recommendation` con status=ejecutada y executed_at
hace 7+ días, mide impacto real cruzando con events del bus + genera
narrativa de aprendizaje con Sonnet 4.6.

Heurística de hit_rate (Build 3.3 · placeholder · refinar Phase 5+):
- 1.0: target alcanzado · señal evidente en events post-ejecución
- 0.5: parcial · señal débil o mixta
- 0.0: fallido · sin señales en la ventana de evaluación

La señal por tipo de recomendación:
- `pricing_change`: contar marketplace.price.changed events del workspace en
  ventana de 7d post-ejecución · si delta_pct alineado con la dirección
  esperada (acción "bajar precio" → buscar deltas negativos) → 1.0
- `promo_launch` / `ad_campaign`: por ahora 0.5 default (sin datos de revenue
  todavía · llega Phase 4 con SISMO V2 read)
- otros: 0.5 default
"""
from __future__ import annotations

import contextlib
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from argos.agents.strategist.service import SONNET_MODEL
from argos.config import get_settings
from argos.db import collections as col
from argos.db.events import publish_recommendation_evaluated

logger = logging.getLogger("argos.agents.strategist.impact")

EVAL_WINDOW_DAYS = 7
LEARNING_MAX_TOKENS = 250

# Build 4.2: tipos que se evalúan con ventas reales de SISMO (no solo con events)
SALES_DRIVEN_TYPES = {"pricing_change", "promo_launch"}


async def _aggregate_real_sales_window(
    db: AsyncIOMotorDatabase,
    workspace_id: str,
    *,
    executed_at: datetime,
    window_days: int,
) -> dict[str, Any]:
    """Suma ventas del workspace en `[executed_at, executed_at+window]` desde sismo_sales_daily.

    Devuelve `{units_sold, revenue_cop, days_with_data, sku_count}`. Si no hay
    sismo_sales_daily poblada (Build 4.2 sin SISMO real o pre-Build), devuelve
    `{}` y el caller cae al heurístico clásico.
    """
    end = executed_at + timedelta(days=window_days)
    start_str = executed_at.strftime("%Y-%m-%d")
    end_str = end.strftime("%Y-%m-%d")

    pipeline = [
        {"$match": {
            "workspace_id": workspace_id,
            "date": {"$gte": start_str, "$lte": end_str},
        }},
        {"$group": {
            "_id": None,
            "units_sold": {"$sum": "$units_sold"},
            "revenue": {"$sum": "$revenue"},
            "days": {"$addToSet": "$date"},
            "skus": {"$addToSet": "$sku"},
        }},
    ]
    docs = await db[col.SISMO_SALES_DAILY].aggregate(pipeline).to_list(length=1)
    if not docs:
        return {}
    d = docs[0]
    return {
        "units_sold": int(d.get("units_sold") or 0),
        "revenue_cop": round(float(d.get("revenue") or 0), 2),
        "days_with_data": len(d.get("days") or []),
        "sku_count": len(d.get("skus") or []),
        "window_start": start_str,
        "window_end": end_str,
    }


def _heuristic_hit_rate(
    recommendation: dict[str, Any], events: list[dict[str, Any]]
) -> float:
    """Devuelve 1.0/0.5/0.0 según evidencia en events relacionados."""
    type_ = recommendation.get("type", "")
    action = (recommendation.get("action_description") or "").lower()

    if type_ == "pricing_change":
        # Buscar dirección en la acción · "bajar"=negativo, "subir"=positivo
        wants_lower = "bajar" in action or "reducir" in action
        wants_higher = "subir" in action or "aumentar" in action
        relevant = [e for e in events if e.get("event_type") == "marketplace.price.changed"]
        if not relevant:
            return 0.0
        # Avg delta de los events relevantes
        deltas = [float(e.get("payload", {}).get("delta_pct", 0)) for e in relevant]
        if not deltas:
            return 0.0
        avg = sum(deltas) / len(deltas)
        if wants_lower and avg < -2:
            return 1.0
        if wants_higher and avg > 2:
            return 1.0
        if abs(avg) > 1:
            return 0.5
        return 0.0

    # Otros tipos · default 0.5 hasta que Phase 4+ traiga datos de SISMO
    return 0.5


async def _generate_learning(
    recommendation: dict[str, Any],
    hit_rate: float,
    events_count: int,
    *,
    sales_metrics: dict[str, Any] | None = None,
    anthropic_client: Any | None = None,
) -> str:
    """Genera reflexión post-mortem corta con Sonnet 4.6 · ~50-80 palabras."""
    settings = get_settings()
    if anthropic_client is None:
        if not settings.anthropic_api_key:
            return f"Sin ANTHROPIC_API_KEY · evaluación heurística · hit_rate={hit_rate}"
        from anthropic import AsyncAnthropic
        anthropic_client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    outcome = "funcionó" if hit_rate >= 0.7 else "funcionó parcialmente" if hit_rate >= 0.4 else "no funcionó"
    sales_block = ""
    if sales_metrics:
        sales_block = (
            f"Ventas reales SISMO en ventana 7d post-ejecución:\n"
            f"  - units_sold: {sales_metrics.get('units_sold', 0)}\n"
            f"  - revenue COP: {sales_metrics.get('revenue_cop', 0)}\n"
            f"  - días con datos: {sales_metrics.get('days_with_data', 0)}/7\n"
            f"  - SKUs distintos: {sales_metrics.get('sku_count', 0)}\n"
        )
    user_message = (
        f"Recomendación: {recommendation.get('action_description', '')}\n"
        f"Tipo: {recommendation.get('type', 'pricing_change')}\n"
        f"Prioridad original: {recommendation.get('priority', 'Media')}\n"
        f"Justificación original: {recommendation.get('rationale', '')}\n"
        f"Hit rate medido: {hit_rate} · {outcome}\n"
        f"Eventos relacionados detectados en 7d post-ejecución: {events_count}\n"
        f"{sales_block}\n"
        "En 50-80 palabras, escribe una reflexión post-mortem para el CEO de RODDOS. "
        "Si hay datos de ventas, úsalos para argumentar (ej: \"vendieron X unidades vs el target Y\"). "
        "Si funcionó, qué condiciones del mercado lo facilitaron. Si no funcionó, qué "
        "señal del input fue malinterpretada. Sin markdown · texto plano."
    )
    try:
        response = await anthropic_client.messages.create(
            model=SONNET_MODEL,
            max_tokens=LEARNING_MAX_TOKENS,
            messages=[{"role": "user", "content": user_message}],
        )
        text = ""
        with contextlib.suppress(AttributeError, IndexError, TypeError):
            text = response.content[0].text or ""
        return text.strip()[:1000]
    except Exception as exc:  # noqa: BLE001
        logger.exception("learning_generation_failed")
        return f"Auto-evaluación fallida ({type(exc).__name__}) · hit_rate={hit_rate} · revisar logs."


async def evaluate_pending_recommendations(
    db: AsyncIOMotorDatabase,
    *,
    workspace_id: str = "RODDOS",
    anthropic_client: Any | None = None,
    eval_window_days: int = EVAL_WINDOW_DAYS,
) -> dict[str, int]:
    """Job: evalúa recomendaciones ejecutadas hace 7+ días sin actual_impact."""
    now = datetime.now(tz=UTC)
    cutoff = now - timedelta(days=eval_window_days)

    pending_filter = {
        "workspace_id": workspace_id,
        "status": "ejecutada",
        "executed_at": {"$lte": cutoff},
        "$or": [{"actual_impact": None}, {"actual_impact": {"$exists": False}}],
    }
    cursor = db[col.RECOMMENDATIONS].find(pending_filter)
    pending = await cursor.to_list(length=100)

    stats = {"evaluated": 0, "errors": 0}
    for rec in pending:
        try:
            executed_at = rec.get("executed_at")
            if not executed_at:
                continue
            window_end = executed_at + timedelta(days=eval_window_days)

            # Eventos del bus en la ventana 7d post-ejecución
            events_cursor = db[col.ARGOS_EVENTS].find(
                {
                    "workspace_id": workspace_id,
                    "timestamp_utc": {"$gte": executed_at, "$lte": window_end},
                    "event_type": {
                        "$in": [
                            "marketplace.price.changed",
                            "marketplace.price.alert",
                            "trends.keyword.spike",
                        ]
                    },
                },
                {"event_type": 1, "payload": 1, "timestamp_utc": 1},
            ).limit(200)
            events = await events_cursor.to_list(length=200)

            hit_rate = _heuristic_hit_rate(rec, events)

            # Build 4.2: cruce con ventas reales para pricing_change/promo_launch
            actual_impact: dict[str, Any] = {
                "metric": rec.get("expected_impact", {}).get("metric", "qualitative"),
                "valor_real": str(hit_rate),
                "medido_at": now,
            }
            sales_metrics: dict[str, Any] = {}
            if rec.get("type") in SALES_DRIVEN_TYPES:
                sales_metrics = await _aggregate_real_sales_window(
                    db, workspace_id,
                    executed_at=executed_at,
                    window_days=eval_window_days,
                )
                if sales_metrics:
                    actual_impact = {
                        "metric": "units_sold_and_revenue",
                        "units_sold": sales_metrics["units_sold"],
                        "revenue_cop": sales_metrics["revenue_cop"],
                        "days_with_data": sales_metrics["days_with_data"],
                        "window_start": sales_metrics["window_start"],
                        "window_end": sales_metrics["window_end"],
                        "hit_rate_heuristic": hit_rate,
                        "medido_at": now,
                    }

            learning = await _generate_learning(
                rec, hit_rate, len(events),
                sales_metrics=sales_metrics,
                anthropic_client=anthropic_client,
            )

            await db[col.RECOMMENDATIONS].update_one(
                {"_id": rec["_id"]},
                {
                    "$set": {
                        "status": "evaluada",
                        "actual_impact": actual_impact,
                        "hit_rate_contribution": hit_rate,
                        "learning": learning,
                        "evaluated_at": now,
                        "updated_at": now,
                    }
                },
            )
            await publish_recommendation_evaluated(
                db,
                workspace_id=workspace_id,
                recommendation_id=str(rec["_id"]),
                hit_rate_contribution=hit_rate,
            )
            stats["evaluated"] += 1
        except Exception:  # noqa: BLE001
            logger.exception("impact_evaluation_failed", extra={"recommendation_id": str(rec.get("_id"))})
            stats["errors"] += 1

    logger.info("impact_evaluation_done", extra=stats)
    return stats
