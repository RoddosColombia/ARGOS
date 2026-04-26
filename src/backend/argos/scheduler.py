"""Scheduler async (APScheduler) · jobs periódicos para Build 1.0.

Build 1.0: single-instance in-memory (AsyncIOScheduler). Suficiente para
Phase 1 en Render Starter (1 dyno). Ver DT-004 en deuda_tecnica.md para
la migración a Mongo-backed jobstore cuando se escale a N instancias.
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
from argos.agents.executive.service import run_morning_briefing
from argos.agents.scout.service import tick as scout_tick
from argos.agents.social.service import refresh_social
from argos.agents.trends.service import refresh_trends

logger = logging.getLogger("argos.scheduler")

_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler | None:
    return _scheduler


async def _scout_tick_job(db: AsyncIOMotorDatabase) -> None:
    """Wrapper del tick con manejo de errores · nunca levanta excepción al scheduler."""
    try:
        stats = await scout_tick(db)
        logger.info("scheduled_scout_tick", extra=stats.as_dict())
    except Exception:  # noqa: BLE001
        logger.exception("scheduled_scout_tick_failed")


async def _trends_refresh_job(db: AsyncIOMotorDatabase) -> None:
    try:
        stats = await refresh_trends(db)
        logger.info("scheduled_trends_refresh", extra=stats)
    except Exception:  # noqa: BLE001
        logger.exception("scheduled_trends_refresh_failed")


async def _price_alert_check_job(db: AsyncIOMotorDatabase) -> None:
    try:
        alerts = await check_price_drops(db)
        logger.info("scheduled_price_alert_check", extra={"alerts_emitted": len(alerts)})
    except Exception:  # noqa: BLE001
        logger.exception("scheduled_price_alert_check_failed")


async def _meta_ads_refresh_job(db: AsyncIOMotorDatabase) -> None:
    try:
        stats = await refresh_meta_ads(db)
        logger.info("scheduled_meta_ads_refresh", extra=stats.as_dict())
    except Exception:  # noqa: BLE001
        logger.exception("scheduled_meta_ads_refresh_failed")


async def _google_ads_refresh_job(db: AsyncIOMotorDatabase) -> None:
    try:
        stats = await refresh_google_ads(db)
        logger.info("scheduled_google_ads_refresh", extra=stats.as_dict())
    except Exception:  # noqa: BLE001
        logger.exception("scheduled_google_ads_refresh_failed")


async def _social_refresh_job(db: AsyncIOMotorDatabase) -> None:
    try:
        stats = await refresh_social(db)
        logger.info("scheduled_social_refresh", extra=stats.as_dict())
    except Exception:  # noqa: BLE001
        logger.exception("scheduled_social_refresh_failed")


async def _morning_briefing_job(db: AsyncIOMotorDatabase) -> None:
    try:
        result = await run_morning_briefing(db)
        logger.info("scheduled_morning_briefing", extra=result)
    except Exception:  # noqa: BLE001
        logger.exception("scheduled_morning_briefing_failed")


def build_scheduler(db: AsyncIOMotorDatabase, *, env: str) -> AsyncIOScheduler:
    """Construye el scheduler con sus jobs registrados SIN arrancarlo.

    Separado de `start_scheduler` para poder testear el wiring (job registrado,
    trigger correcto por env) sin iniciar el loop de APScheduler, que requiere
    un event loop vivo y contamina event loops entre tests de pytest-asyncio.
    """
    scheduler = AsyncIOScheduler(timezone="UTC")
    hours = 24 if env == "dev" else 6

    scheduler.add_job(
        _scout_tick_job,
        args=[db],
        trigger=IntervalTrigger(hours=hours),
        id="scout_tick",
        name="Scout tick · MELI search sobre WATCH_QUERIES",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    # Trends agent · diario a las 03:00 UTC
    scheduler.add_job(
        _trends_refresh_job,
        args=[db],
        trigger=CronTrigger(hour=3, minute=0),
        id="trends_refresh",
        name="Trends refresh · Google Trends sobre watch_queries source=all",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    # Alerts · cada hora detecta caídas de precio ≥ 15% en últimas 24h
    scheduler.add_job(
        _price_alert_check_job,
        args=[db],
        trigger=IntervalTrigger(hours=1),
        id="price_alert_check",
        name="Price alert check · drops ≥ 15% en últimas 24h",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    # Meta Ad Library · cada 12h scraping competidores activos
    scheduler.add_job(
        _meta_ads_refresh_job,
        args=[db],
        trigger=IntervalTrigger(hours=12),
        id="meta_ads_refresh",
        name="Meta Ads refresh · Apify FB Ad Library scraper",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    # Google Ads Transparency · cada 12h via SerpAPI
    scheduler.add_job(
        _google_ads_refresh_job,
        args=[db],
        trigger=IntervalTrigger(hours=12),
        id="google_ads_refresh",
        name="Google Ads refresh · SerpAPI google_ads_transparency_center",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    # Social listening · diario 04:00 UTC via TikHub
    scheduler.add_job(
        _social_refresh_job,
        args=[db],
        trigger=CronTrigger(hour=4, minute=0),
        id="social_refresh",
        name="Social refresh · TikHub IG/TikTok cuentas + posts virales",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    # Morning Briefing · diario 06:45 UTC (después de scout/trends/social/alerts)
    scheduler.add_job(
        _morning_briefing_job,
        args=[db],
        trigger=CronTrigger(hour=6, minute=45),
        id="morning_briefing",
        name="Morning Briefing · Strategist + Executive · Sonnet 4.6",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    return scheduler


def start_scheduler(db: AsyncIOMotorDatabase, *, env: str) -> AsyncIOScheduler:
    """Arranca el scheduler e instala el job `scout_tick`. Idempotente."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        return _scheduler

    scheduler = build_scheduler(db, env=env)
    scheduler.start()
    hours = 24 if env == "dev" else 6
    logger.info("scheduler_started", extra={"env": env, "scout_tick_hours": hours})

    _scheduler = scheduler
    return scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("scheduler_stopped")
    _scheduler = None
