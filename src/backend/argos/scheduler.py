"""Scheduler async (APScheduler) · jobs periódicos para Build 1.0.

Build 1.0: single-instance in-memory (AsyncIOScheduler). Suficiente para
Phase 1 en Render Starter (1 dyno). Ver DT-004 en deuda_tecnica.md para
la migración a Mongo-backed jobstore cuando se escale a N instancias.
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from motor.motor_asyncio import AsyncIOMotorDatabase

from argos.agents.scout.service import tick as scout_tick

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
