"""Scheduler async (APScheduler) · jobs periódicos de ARGOS.

Build 2.5.7: migrado a MongoDBJobStore cuando MONGODB_URI está disponible.
Los jobs sobreviven restart del proceso (cierra DT-004).

Diseño:
- _db es variable de módulo para que los job wrappers no reciban db como arg.
  APScheduler 3.x serializa jobs con pickle; AsyncIOMotorDatabase NO es picklable,
  por lo que args=[db] rompería al intentar persistir en Mongo.
- MongoDBJobStore usa pymongo sync (distinto del motor async del backend).
  APScheduler lo gestiona internamente — no hay conflict de event loop.
- Si MONGODB_URI está vacío (dev sin DB), cae a MemoryJobStore automaticamente.

Refs: phase_2.5/build_2.5.7 · DT-004 · docs/canonicas/colecciones_mongo.md#apscheduler_jobs
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from motor.motor_asyncio import AsyncIOMotorDatabase

from argos.agents.alerts.service import check_price_drops
from argos.agents.competitors.google_ads_service import refresh_google_ads
from argos.agents.competitors.meta_ads_service import refresh_meta_ads
from argos.agents.discovery.service import run_discovery_job
from argos.agents.executive.service import run_morning_briefing
from argos.agents.memory.service import embed_pending_job
from argos.agents.notifications.service import notify_recent_price_alerts
from argos.agents.scout.service import tick as scout_tick
from argos.agents.sismo.service import (
    sync_sismo_inventory_job,
    sync_sismo_sales_daily_job,
)
from argos.agents.social.service import refresh_social
from argos.agents.strategist.impact import evaluate_pending_recommendations
from argos.agents.trends.service import refresh_trends
from argos.agents.whatsapp.inbound_poller import poll_inbound

logger = logging.getLogger("argos.scheduler")

_scheduler: AsyncIOScheduler | None = None
_db: AsyncIOMotorDatabase | None = None

JOBSTORE_COLLECTION = "apscheduler_jobs"
COALESCE_DEFAULT = True
MISFIRE_GRACE_DAILY = 60        # segundos · jobs que corren diario o más
MISFIRE_GRACE_FREQUENT = 300    # segundos · jobs que corren cada hora o menos


def get_scheduler() -> AsyncIOScheduler | None:
    return _scheduler


# ---------------------------------------------------------------------------
# Job wrappers · usan _db de módulo (no arg) para compatibilidad con pickle
# ---------------------------------------------------------------------------

async def _scout_tick_job() -> None:
    try:
        stats = await scout_tick(_db)
        logger.info("scheduled_scout_tick", extra=stats.as_dict())
    except Exception:  # noqa: BLE001
        logger.exception("scheduled_scout_tick_failed")


async def _trends_refresh_job() -> None:
    try:
        stats = await refresh_trends(_db)
        logger.info("scheduled_trends_refresh", extra=stats)
    except Exception:  # noqa: BLE001
        logger.exception("scheduled_trends_refresh_failed")


async def _price_alert_check_job() -> None:
    try:
        alerts = await check_price_drops(_db)
        logger.info("scheduled_price_alert_check", extra={"alerts_emitted": len(alerts)})
    except Exception:  # noqa: BLE001
        logger.exception("scheduled_price_alert_check_failed")


async def _meta_ads_refresh_job() -> None:
    try:
        stats = await refresh_meta_ads(_db)
        logger.info("scheduled_meta_ads_refresh", extra=stats.as_dict())
    except Exception:  # noqa: BLE001
        logger.exception("scheduled_meta_ads_refresh_failed")


async def _google_ads_refresh_job() -> None:
    try:
        stats = await refresh_google_ads(_db)
        logger.info("scheduled_google_ads_refresh", extra=stats.as_dict())
    except Exception:  # noqa: BLE001
        logger.exception("scheduled_google_ads_refresh_failed")


async def _social_refresh_job() -> None:
    try:
        stats = await refresh_social(_db)
        logger.info("scheduled_social_refresh", extra=stats.as_dict())
    except Exception:  # noqa: BLE001
        logger.exception("scheduled_social_refresh_failed")


async def _morning_briefing_job() -> None:
    try:
        result = await run_morning_briefing(_db)
        logger.info("scheduled_morning_briefing", extra=result)
    except Exception:  # noqa: BLE001
        logger.exception("scheduled_morning_briefing_failed")


async def _memory_embed_job() -> None:
    try:
        stats = await embed_pending_job(_db)
        logger.info("scheduled_memory_embed", extra=stats)
    except Exception:  # noqa: BLE001
        logger.exception("scheduled_memory_embed_failed")


async def _sismo_sync_job() -> None:
    try:
        stats = await sync_sismo_inventory_job(_db)
        logger.info("scheduled_sismo_sync", extra=stats.as_dict())
    except Exception:  # noqa: BLE001
        logger.exception("scheduled_sismo_sync_failed")


async def _sismo_sales_sync_job() -> None:
    try:
        stats = await sync_sismo_sales_daily_job(_db)
        logger.info("scheduled_sismo_sales_sync", extra=stats.as_dict())
    except Exception:  # noqa: BLE001
        logger.exception("scheduled_sismo_sales_sync_failed")


async def _discovery_job() -> None:
    try:
        result = await run_discovery_job(_db)
        logger.info("scheduled_discovery", extra={
            "categories": result.get("categories", 0),
            "stats_count": len(result.get("stats", [])),
        })
    except Exception:  # noqa: BLE001
        logger.exception("scheduled_discovery_failed")


async def _price_alert_whatsapp_job() -> None:
    try:
        stats = await notify_recent_price_alerts(_db)
        logger.info("scheduled_price_alert_whatsapp", extra=stats)
    except Exception:  # noqa: BLE001
        logger.exception("scheduled_price_alert_whatsapp_failed")


async def _impact_evaluation_job() -> None:
    try:
        stats = await evaluate_pending_recommendations(_db)
        logger.info("scheduled_impact_evaluation", extra=stats)
    except Exception:  # noqa: BLE001
        logger.exception("scheduled_impact_evaluation_failed")


async def _mercately_inbound_poll_job() -> None:
    try:
        from argos.config import get_settings
        from argos.partners.mercately.client import MercatelyClient
        from argos.partners.wava.client import WavaClient

        settings = get_settings()
        async with (
            MercatelyClient(api_key=settings.mercately_api_key) as client,
            WavaClient(
                merchant_key=settings.wava_merchant_key,
                base_url=settings.wava_api_url,
            ) as wava,
        ):
            stats = await poll_inbound(
                _db,
                mercately_client=client,
                anthropic_api_key=settings.anthropic_api_key,
                sismo_webhook_url=settings.sismo_inbound_webhook_url,
                webhook_secret=settings.mercately_webhook_secret,
                whatsapp_reply_enabled=settings.whatsapp_reply_enabled,
                wava_client=wava,
            )
        logger.info("scheduled_mercately_inbound_poll", extra=stats)
    except Exception:  # noqa: BLE001
        logger.exception("scheduled_mercately_inbound_poll_failed")


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

def build_scheduler(
    db: AsyncIOMotorDatabase,
    *,
    env: str,
    mongodb_uri: str = "",
) -> AsyncIOScheduler:
    """Construye el scheduler con sus jobs registrados SIN arrancarlo.

    Si `mongodb_uri` está presente, usa MongoDBJobStore (jobs sobreviven restart).
    Si no, usa MemoryJobStore (dev sin DB, tests unitarios).

    Separado de `start_scheduler` para poder testear el wiring sin iniciar el
    loop de APScheduler.
    """
    global _db
    _db = db

    from apscheduler.jobstores.memory import MemoryJobStore

    jobstores: dict = {"default": MemoryJobStore()}
    if mongodb_uri:
        try:
            from apscheduler.jobstores.mongodb import MongoDBJobStore
            jobstores["default"] = MongoDBJobStore(
                host=mongodb_uri,
                collection=JOBSTORE_COLLECTION,
            )
            logger.info("scheduler_jobstore_mongo", extra={"collection": JOBSTORE_COLLECTION})
        except Exception:  # noqa: BLE001
            logger.warning("scheduler_jobstore_mongo_failed_fallback_memory")

    scheduler = AsyncIOScheduler(jobstores=jobstores, timezone="UTC")
    hours = 24 if env == "dev" else 6

    scheduler.add_job(
        _scout_tick_job,
        trigger=IntervalTrigger(hours=hours),
        id="scout_tick",
        name="Scout tick · MELI search sobre WATCH_QUERIES",
        replace_existing=True,
        max_instances=1,
        coalesce=COALESCE_DEFAULT,
        misfire_grace_time=MISFIRE_GRACE_DAILY,
    )

    # Trends agent · diario a las 03:00 UTC
    scheduler.add_job(
        _trends_refresh_job,
        trigger=CronTrigger(hour=3, minute=0),
        id="trends_refresh",
        name="Trends refresh · Google Trends sobre watch_queries source=all",
        replace_existing=True,
        max_instances=1,
        coalesce=COALESCE_DEFAULT,
        misfire_grace_time=MISFIRE_GRACE_DAILY,
    )

    # Alerts · cada hora detecta caídas de precio ≥ 15% en últimas 24h
    scheduler.add_job(
        _price_alert_check_job,
        trigger=IntervalTrigger(hours=1),
        id="price_alert_check",
        name="Price alert check · drops ≥ 15% en últimas 24h",
        replace_existing=True,
        max_instances=1,
        coalesce=COALESCE_DEFAULT,
        misfire_grace_time=MISFIRE_GRACE_FREQUENT,
    )

    # Meta Ad Library · cada 12h scraping competidores activos
    scheduler.add_job(
        _meta_ads_refresh_job,
        trigger=IntervalTrigger(hours=12),
        id="meta_ads_refresh",
        name="Meta Ads refresh · Apify FB Ad Library scraper",
        replace_existing=True,
        max_instances=1,
        coalesce=COALESCE_DEFAULT,
        misfire_grace_time=MISFIRE_GRACE_DAILY,
    )

    # Google Ads Transparency · cada 12h via SerpAPI
    scheduler.add_job(
        _google_ads_refresh_job,
        trigger=IntervalTrigger(hours=12),
        id="google_ads_refresh",
        name="Google Ads refresh · SerpAPI google_ads_transparency_center",
        replace_existing=True,
        max_instances=1,
        coalesce=COALESCE_DEFAULT,
        misfire_grace_time=MISFIRE_GRACE_DAILY,
    )

    # Social listening · diario 04:00 UTC via TikHub
    scheduler.add_job(
        _social_refresh_job,
        trigger=CronTrigger(hour=4, minute=0),
        id="social_refresh",
        name="Social refresh · TikHub IG/TikTok cuentas + posts virales",
        replace_existing=True,
        max_instances=1,
        coalesce=COALESCE_DEFAULT,
        misfire_grace_time=MISFIRE_GRACE_DAILY,
    )

    # SISMO V2 inventory sync · cada 6h
    scheduler.add_job(
        _sismo_sync_job,
        trigger=IntervalTrigger(hours=6),
        id="sismo_sync",
        name="SISMO V2 sync · inventario read-only · upsert por (sku, fecha)",
        replace_existing=True,
        max_instances=1,
        coalesce=COALESCE_DEFAULT,
        misfire_grace_time=MISFIRE_GRACE_DAILY,
    )

    # SISMO V2 sales daily sync · diario 01:00 UTC
    scheduler.add_job(
        _sismo_sales_sync_job,
        trigger=CronTrigger(hour=1, minute=0),
        id="sismo_sales_sync",
        name="SISMO V2 sales daily · ventas del día anterior",
        replace_existing=True,
        max_instances=1,
        coalesce=COALESCE_DEFAULT,
        misfire_grace_time=MISFIRE_GRACE_DAILY,
    )

    # Discovery · diario 06:00 UTC (antes del Morning Briefing 06:45 UTC)
    scheduler.add_job(
        _discovery_job,
        trigger=CronTrigger(hour=6, minute=0),
        id="discovery",
        name="Discovery · trending/rising/liquidating/disappearing por categoría activa",
        replace_existing=True,
        max_instances=1,
        coalesce=COALESCE_DEFAULT,
        misfire_grace_time=MISFIRE_GRACE_DAILY,
    )

    # Morning Briefing · diario 11:00 UTC = 06:00 AM Bogotá (GMT-5)
    scheduler.add_job(
        _morning_briefing_job,
        trigger=CronTrigger(hour=11, minute=0),
        id="morning_briefing",
        name="Morning Briefing · Strategist + Executive + WhatsApp · 06:00 AM Bogotá",
        replace_existing=True,
        max_instances=1,
        coalesce=COALESCE_DEFAULT,
        misfire_grace_time=MISFIRE_GRACE_DAILY,
    )

    # Price alert WhatsApp · cada 30 min
    scheduler.add_job(
        _price_alert_whatsapp_job,
        trigger=IntervalTrigger(minutes=30),
        id="price_alert_whatsapp",
        name="Price alert WhatsApp · drops ≥ 15% via Twilio",
        replace_existing=True,
        max_instances=1,
        coalesce=COALESCE_DEFAULT,
        misfire_grace_time=MISFIRE_GRACE_FREQUENT,
    )

    # Impact evaluation · diario 07:00 UTC (después del morning briefing)
    scheduler.add_job(
        _impact_evaluation_job,
        trigger=CronTrigger(hour=7, minute=0),
        id="impact_evaluation",
        name="Impact evaluation · evalúa recomendaciones ejecutadas hace 7+ días",
        replace_existing=True,
        max_instances=1,
        coalesce=COALESCE_DEFAULT,
        misfire_grace_time=MISFIRE_GRACE_DAILY,
    )

    # Memory embeddings · cada 6h embed productos + ads pendientes
    scheduler.add_job(
        _memory_embed_job,
        trigger=IntervalTrigger(hours=6),
        id="memory_embed",
        name="Memory embed · OpenAI text-embedding-3-small + Qdrant upsert",
        replace_existing=True,
        max_instances=1,
        coalesce=COALESCE_DEFAULT,
        misfire_grace_time=MISFIRE_GRACE_DAILY,
    )

    # Mercately inbound poller · cada MERCATELY_POLL_INTERVAL_S (default 30s)
    from argos.config import get_settings as _gs
    poll_s = _gs().mercately_poll_interval_s
    if poll_s > 0:
        scheduler.add_job(
            _mercately_inbound_poll_job,
            trigger=IntervalTrigger(seconds=poll_s),
            id="mercately_inbound_poll",
            name="Mercately inbound poll · WhatsApp messages → intent classify → route",
            replace_existing=True,
            max_instances=1,
            coalesce=COALESCE_DEFAULT,
            misfire_grace_time=MISFIRE_GRACE_FREQUENT,
        )

    return scheduler


def start_scheduler(db: AsyncIOMotorDatabase, *, env: str) -> AsyncIOScheduler:
    """Arranca el scheduler con MongoDBJobStore si MONGODB_URI está configurado."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        return _scheduler

    from argos.config import get_settings
    settings = get_settings()

    scheduler = build_scheduler(db, env=env, mongodb_uri=settings.mongodb_uri)
    scheduler.start()
    hours = 24 if env == "dev" else 6
    jobstore_type = "mongo" if settings.mongodb_uri else "memory"
    logger.info(
        "scheduler_started",
        extra={"env": env, "scout_tick_hours": hours, "jobstore": jobstore_type},
    )

    _scheduler = scheduler
    return scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("scheduler_stopped")
    _scheduler = None
