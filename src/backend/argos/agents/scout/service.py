"""Scout Agent · tick periódico que escanea MELI vía Marketplace Agent.

Build 1.0: sin Haiku. Persiste todos los resultados de las WATCH_QUERIES.
Build 1.1 añade clasificación Haiku (relevante / no relevante) para filtrar.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from argos.agents.marketplace.service import upsert_product
from argos.agents.scout.watch_queries import WATCH_QUERIES
from argos.partners.meli.client import MeliClient, MeliError

logger = logging.getLogger("argos.agents.scout")

DEFAULT_RESULTS_PER_QUERY = 20


@dataclass
class ScoutTickStats:
    queries_processed: int = 0
    products_detected: int = 0
    products_created: int = 0
    products_price_changed: int = 0
    errors: list[dict[str, str]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "queries_processed": self.queries_processed,
            "products_detected": self.products_detected,
            "products_created": self.products_created,
            "products_price_changed": self.products_price_changed,
            "errors": list(self.errors),
        }


async def tick(
    db: AsyncIOMotorDatabase,
    *,
    workspace_id: str = "RODDOS",
    client: MeliClient | None = None,
    queries: tuple[str, ...] | None = None,
    results_per_query: int = DEFAULT_RESULTS_PER_QUERY,
) -> ScoutTickStats:
    """Ejecuta un tick · itera WATCH_QUERIES · upsert cada resultado MELI.

    Errores por query se capturan aislados · un query fallido no tumba el tick.
    """
    stats = ScoutTickStats()
    queries_to_run = queries if queries is not None else WATCH_QUERIES

    own_client = client is None
    if own_client:
        client = MeliClient()
        await client.__aenter__()

    try:
        for query in queries_to_run:
            try:
                items = await client.search(query=query, limit=results_per_query)
                for raw in items:
                    result = await upsert_product(db, raw, workspace_id=workspace_id)
                    if result is None:
                        continue
                    stats.products_detected += 1
                    if result.created:
                        stats.products_created += 1
                    if result.price_change_delta_pct is not None:
                        stats.products_price_changed += 1
                stats.queries_processed += 1
            except MeliError as exc:
                logger.warning("scout_query_meli_error", extra={"query": query, "status": exc.status})
                stats.errors.append({"query": query, "error": f"meli_{exc.status}"})
            except Exception as exc:  # noqa: BLE001 — aislar falla por query
                logger.exception("scout_query_failed", extra={"query": query})
                stats.errors.append({"query": query, "error": f"{type(exc).__name__}: {str(exc)[:180]}"})
    finally:
        if own_client and client is not None:
            await client.__aexit__(None, None, None)

    logger.info("scout_tick_done", extra=stats.as_dict())
    return stats
