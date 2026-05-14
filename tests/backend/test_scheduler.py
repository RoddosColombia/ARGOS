"""Tests del scheduler · Build 2.5.7 (MongoDBJobStore).

No arrancan el event loop de APScheduler para evitar contaminación cross-test.
Usan `build_scheduler` para inspeccionar jobs registrados y configuración de jobstore.

Refs: phase_2.5/build_2.5.7 · DT-004
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from argos.scheduler import (
    MISFIRE_GRACE_DAILY,
    MISFIRE_GRACE_FREQUENT,
    build_scheduler,
)

# ---------------------------------------------------------------------------
# Tests de wiring · jobs registrados correctamente
# ---------------------------------------------------------------------------

def test_build_scheduler_registers_scout_tick_job() -> None:
    db = MagicMock()
    scheduler = build_scheduler(db, env="dev")
    job = scheduler.get_job("scout_tick")
    assert job is not None
    assert job.name.startswith("Scout tick")
    assert job.max_instances == 1
    assert job.coalesce is True


def test_build_scheduler_uses_24h_in_dev() -> None:
    db = MagicMock()
    scheduler = build_scheduler(db, env="dev")
    trigger = scheduler.get_job("scout_tick").trigger
    assert trigger.interval.total_seconds() == 24 * 3600


def test_build_scheduler_uses_6h_in_prod() -> None:
    db = MagicMock()
    scheduler = build_scheduler(db, env="prod")
    trigger = scheduler.get_job("scout_tick").trigger
    assert trigger.interval.total_seconds() == 6 * 3600


def test_build_scheduler_registers_all_expected_jobs() -> None:
    """Todos los jobs periódicos están registrados."""
    db = MagicMock()
    scheduler = build_scheduler(db, env="prod")
    expected_ids = {
        "scout_tick",
        "trends_refresh",
        "price_alert_check",
        "meta_ads_refresh",
        "google_ads_refresh",
        "social_refresh",
        "sismo_sync",
        "sismo_sales_sync",
        "discovery",
        "morning_briefing",
        "price_alert_whatsapp",
        "impact_evaluation",
        "memory_embed",
        "mercately_inbound_poll",
    }
    registered = {job.id for job in scheduler.get_jobs()}
    assert expected_ids == registered, (
        f"Jobs faltantes: {expected_ids - registered}, "
        f"extras: {registered - expected_ids}"
    )


def test_build_scheduler_misfire_grace_daily_jobs() -> None:
    """Jobs diarios tienen misfire_grace_time = MISFIRE_GRACE_DAILY."""
    db = MagicMock()
    scheduler = build_scheduler(db, env="prod")
    daily_job_ids = [
        "trends_refresh", "social_refresh", "sismo_sync", "sismo_sales_sync",
        "discovery", "morning_briefing", "impact_evaluation",
        "scout_tick", "meta_ads_refresh", "google_ads_refresh", "memory_embed",
    ]
    for job_id in daily_job_ids:
        job = scheduler.get_job(job_id)
        assert job is not None
        assert job.misfire_grace_time == MISFIRE_GRACE_DAILY, (
            f"Job '{job_id}' tiene misfire_grace_time={job.misfire_grace_time}, "
            f"esperado {MISFIRE_GRACE_DAILY}"
        )


def test_build_scheduler_misfire_grace_frequent_jobs() -> None:
    """Jobs frecuentes (1h o 30min) tienen misfire_grace_time = MISFIRE_GRACE_FREQUENT."""
    db = MagicMock()
    scheduler = build_scheduler(db, env="prod")
    frequent_job_ids = ["price_alert_check", "price_alert_whatsapp"]
    for job_id in frequent_job_ids:
        job = scheduler.get_job(job_id)
        assert job is not None
        assert job.misfire_grace_time == MISFIRE_GRACE_FREQUENT, (
            f"Job '{job_id}' tiene misfire_grace_time={job.misfire_grace_time}, "
            f"esperado {MISFIRE_GRACE_FREQUENT}"
        )


def test_build_scheduler_uses_memory_jobstore_without_uri() -> None:
    """Sin mongodb_uri el scheduler usa MemoryJobStore (seguro en dev/tests)."""
    from apscheduler.jobstores.memory import MemoryJobStore

    db = MagicMock()
    scheduler = build_scheduler(db, env="dev", mongodb_uri="")
    jobstore = scheduler._jobstores.get("default")
    assert isinstance(jobstore, MemoryJobStore), (
        f"Sin mongodb_uri se esperaba MemoryJobStore, recibido {type(jobstore)}"
    )


def test_build_scheduler_uses_mongo_jobstore_with_uri(monkeypatch: pytest.MonkeyPatch) -> None:
    """Con mongodb_uri válida el scheduler configura MongoDBJobStore.

    Usa una subclase stub de BaseJobStore para pasar el isinstance de APScheduler
    sin abrir conexión real a Mongo.
    """
    from apscheduler.jobstores.base import BaseJobStore, JobLookupError  # noqa: F401

    init_calls: list[dict] = []

    class StubMongoJobStore(BaseJobStore):
        def __init__(self, host: str, collection: str) -> None:
            init_calls.append({"host": host, "collection": collection})

        def lookup_job(self, job_id):  # type: ignore[override]
            raise JobLookupError(job_id)

        def get_due_jobs(self, now):  # type: ignore[override]
            return []

        def get_next_run_time(self):  # type: ignore[override]
            return None

        def get_all_jobs(self):  # type: ignore[override]
            return []

        def add_job(self, job) -> None:  # type: ignore[override]
            pass

        def update_job(self, job) -> None:  # type: ignore[override]
            pass

        def remove_job(self, job_id) -> None:  # type: ignore[override]
            pass

        def remove_all_jobs(self) -> None:  # type: ignore[override]
            pass

    import apscheduler.jobstores.mongodb as mongo_module
    monkeypatch.setattr(mongo_module, "MongoDBJobStore", StubMongoJobStore)

    db = MagicMock()
    build_scheduler(db, env="prod", mongodb_uri="mongodb://localhost:27017")

    assert len(init_calls) == 1
    assert init_calls[0] == {"host": "mongodb://localhost:27017", "collection": "apscheduler_jobs"}


# ---------------------------------------------------------------------------
# Test de módulo-level _db · jobs no reciben db como arg (picklable)
# ---------------------------------------------------------------------------

def test_jobs_take_no_db_argument() -> None:
    """Todos los job wrappers son callables sin argumentos posicionales de db.

    Garantiza que APScheduler puede serializar los jobs con MongoDBJobStore.
    Si un job recibe db como arg, el test falla porque add_job requería args=[db].
    """
    db = MagicMock()
    scheduler = build_scheduler(db, env="prod")
    for job in scheduler.get_jobs():
        assert job.args == (), (
            f"Job '{job.id}' tiene args={job.args} — "
            f"los jobs no deben recibir db como argumento (pickle compat)"
        )


# ---------------------------------------------------------------------------
# Test de comportamiento · error en job no propaga al scheduler
# ---------------------------------------------------------------------------

async def test_scout_tick_job_swallows_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """El wrapper del job nunca levanta al scheduler aunque tick falle."""
    from argos import scheduler as scheduler_module

    failing_tick = AsyncMock(side_effect=RuntimeError("boom"))
    monkeypatch.setattr(scheduler_module, "scout_tick", failing_tick)
    monkeypatch.setattr(scheduler_module, "_db", MagicMock())

    await scheduler_module._scout_tick_job()
    failing_tick.assert_awaited_once()


# ---------------------------------------------------------------------------
# Test de integración · jobs sobreviven restart (requiere MONGODB_URI real)
# ---------------------------------------------------------------------------

@pytest.mark.integration
async def test_jobs_survive_scheduler_restart(monkeypatch: pytest.MonkeyPatch) -> None:
    """Jobs persisten en MongoDB y se recuperan tras crear un nuevo scheduler.

    Requiere MONGODB_URI apuntando a un cluster real. Se salta automáticamente
    en entornos sin DB configurada.
    """
    import os

    from motor.motor_asyncio import AsyncIOMotorClient

    mongodb_uri = os.environ.get("MONGODB_URI", "")
    if not mongodb_uri:
        pytest.skip("MONGODB_URI no configurada · skip en entorno sin DB")

    test_db_name = "argos_test_scheduler_restart"

    client = AsyncIOMotorClient(mongodb_uri)
    db = client[test_db_name]

    from argos.scheduler import JOBSTORE_COLLECTION

    await db[JOBSTORE_COLLECTION].drop()

    try:
        # Primera instancia del scheduler
        s1 = build_scheduler(db, env="prod", mongodb_uri=mongodb_uri)
        s1.start()
        jobs_before = {j.id for j in s1.get_jobs()}
        s1.shutdown(wait=False)

        # Segunda instancia — debe recuperar los jobs de Mongo
        s2 = build_scheduler(db, env="prod", mongodb_uri=mongodb_uri)
        s2.start()
        jobs_after = {j.id for j in s2.get_jobs()}
        s2.shutdown(wait=False)

        assert jobs_before == jobs_after, (
            f"Jobs perdidos tras restart: {jobs_before - jobs_after}"
        )
    finally:
        await db[JOBSTORE_COLLECTION].drop()
        client.close()
