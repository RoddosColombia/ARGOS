"""Scout Agent · tick periódico · lee watch queries de Mongo, clasifica con
Haiku y persiste en products_catalog (MELI + FB Marketplace).

Build 1.1: queries desde Mongo, classifier Haiku, FB Marketplace via Apify.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from argos.agents.classifier.service import (
    HaikuProductClassifier,
    NoOpClassifier,
)
from argos.agents.marketplace.fb_service import parse_apify_fb_item, upsert_fb_product
from argos.agents.marketplace.service import parse_meli_item, upsert_product
from argos.agents.scout.queries_repo import get_active_queries
from argos.config import get_settings
from argos.db.events import publish_scout_product_discarded
from argos.partners.apify.client import ApifyClient, ApifyError
from argos.partners.meli.client import MeliClient, MeliError

logger = logging.getLogger("argos.agents.scout")

DEFAULT_RESULTS_PER_QUERY = 20


@dataclass
class ScoutTickStats:
    queries_processed: int = 0
    products_detected: int = 0
    products_created: int = 0
    products_price_changed: int = 0
    products_discarded: int = 0
    classifier_cache_hits: int = 0
    errors: list[dict[str, str]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "queries_processed": self.queries_processed,
            "products_detected": self.products_detected,
            "products_created": self.products_created,
            "products_price_changed": self.products_price_changed,
            "products_discarded": self.products_discarded,
            "classifier_cache_hits": self.classifier_cache_hits,
            "errors": list(self.errors),
        }


def _build_default_classifier() -> HaikuProductClassifier | NoOpClassifier:
    settings = get_settings()
    if not settings.anthropic_api_key:
        logger.warning("classifier_disabled_no_anthropic_key")
        return NoOpClassifier()
    return HaikuProductClassifier(api_key=settings.anthropic_api_key)


async def _classify_or_skip(
    db: AsyncIOMotorDatabase,
    classifier: Any,
    parsed: dict[str, Any],
    watch_query: str,
    workspace_id: str,
    stats: ScoutTickStats,
) -> bool:
    """Devuelve True si el producto debe persistirse, False si fue descartado.

    Cuando False: emite scout.product.discarded y actualiza stats.
    """
    description = parsed.get("description") or ""
    classify = await classifier.classify(parsed["nombre"], description, watch_query)
    if classify.cached:
        stats.classifier_cache_hits += 1
    if classify.relevante:
        return True
    await publish_scout_product_discarded(
        db,
        workspace_id=workspace_id,
        source=parsed["source"],
        source_id=parsed["source_id"],
        title=parsed["nombre"],
        watch_query=watch_query,
        reason=classify.razon or "no_razon",
    )
    stats.products_discarded += 1
    return False


async def _process_meli_query(
    db: AsyncIOMotorDatabase,
    meli: MeliClient,
    classifier: Any,
    query: str,
    workspace_id: str,
    results_per_query: int,
    stats: ScoutTickStats,
) -> None:
    items = await meli.search(query=query, limit=results_per_query)
    for raw in items:
        parsed = parse_meli_item(raw)
        if parsed is None:
            continue
        if not await _classify_or_skip(db, classifier, parsed, query, workspace_id, stats):
            continue
        result = await upsert_product(db, raw, workspace_id=workspace_id)
        if result is None:
            continue
        stats.products_detected += 1
        if result.created:
            stats.products_created += 1
        if result.price_change_delta_pct is not None:
            stats.products_price_changed += 1


async def _process_fb_query(
    db: AsyncIOMotorDatabase,
    apify: ApifyClient,
    classifier: Any,
    query: str,
    workspace_id: str,
    results_per_query: int,
    stats: ScoutTickStats,
) -> None:
    items = await apify.fb_marketplace_search(query, max_items=results_per_query)
    for raw in items:
        parsed = parse_apify_fb_item(raw)
        if parsed is None:
            continue
        if not await _classify_or_skip(db, classifier, parsed, query, workspace_id, stats):
            continue
        result = await upsert_fb_product(db, raw, workspace_id=workspace_id)
        if result is None:
            continue
        stats.products_detected += 1
        if result.created:
            stats.products_created += 1
        if result.price_change_delta_pct is not None:
            stats.products_price_changed += 1


async def tick(
    db: AsyncIOMotorDatabase,
    *,
    workspace_id: str = "RODDOS",
    meli_client: MeliClient | None = None,
    apify_client: ApifyClient | None = None,
    classifier: Any | None = None,
    queries_override: list[dict[str, Any]] | None = None,
    results_per_query: int = DEFAULT_RESULTS_PER_QUERY,
) -> ScoutTickStats:
    """Ejecuta un tick. Lee watch queries de Mongo (o usa override), itera por
    cada query con sus sources configuradas (meli, fb_marketplace, all), pasa
    cada item por el classifier Haiku · persiste solo los relevantes.

    Errores aislados por query · un fallo en una no tumba el tick.
    """
    stats = ScoutTickStats()
    settings = get_settings()

    queries = queries_override
    if queries is None:
        queries = await get_active_queries(db, workspace_id)
    if not queries:
        logger.warning("scout_no_active_queries", extra={"workspace_id": workspace_id})
        return stats

    if classifier is None:
        classifier = _build_default_classifier()

    own_meli = meli_client is None
    if own_meli:
        meli_client = MeliClient()
        await meli_client.__aenter__()

    own_apify = apify_client is None
    if own_apify:
        apify_client = ApifyClient(api_token=settings.apify_api_token)
        await apify_client.__aenter__()

    try:
        for q in queries:
            query_str = q["query"]
            source = q.get("source", "all")
            sources_to_run = (
                ["meli", "fb_marketplace"] if source == "all" else [source]
            )

            try:
                for src in sources_to_run:
                    if src == "meli":
                        await _process_meli_query(
                            db, meli_client, classifier, query_str,
                            workspace_id, results_per_query, stats,
                        )
                    elif src == "fb_marketplace":
                        if not apify_client.enabled:
                            logger.info(
                                "scout_skipping_fb_no_apify_token",
                                extra={"query": query_str},
                            )
                            continue
                        try:
                            await _process_fb_query(
                                db, apify_client, classifier, query_str,
                                workspace_id, results_per_query, stats,
                            )
                        except ApifyError as exc:
                            logger.warning(
                                "scout_fb_apify_error",
                                extra={"query": query_str, "status": exc.status},
                            )
                            stats.errors.append(
                                {"query": f"{query_str}#fb", "error": f"apify_{exc.status}"}
                            )
                stats.queries_processed += 1
            except MeliError as exc:
                logger.warning("scout_query_meli_error", extra={"query": query_str, "status": exc.status})
                stats.errors.append({"query": query_str, "error": f"meli_{exc.status}"})
            except Exception as exc:  # noqa: BLE001 — aislar falla por query
                logger.exception("scout_query_failed", extra={"query": query_str})
                stats.errors.append(
                    {"query": query_str, "error": f"{type(exc).__name__}: {str(exc)[:180]}"}
                )
    finally:
        if own_meli and meli_client is not None:
            await meli_client.__aexit__(None, None, None)
        if own_apify and apify_client is not None:
            await apify_client.__aexit__(None, None, None)

    logger.info("scout_tick_done", extra=stats.as_dict())
    return stats
