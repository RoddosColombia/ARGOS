"""Tests del scheduler · no arrancan el event loop de APScheduler para evitar
contaminación cross-test. Usan `build_scheduler` para inspeccionar jobs.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from argos.scheduler import build_scheduler


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


async def test_scout_tick_job_swallows_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """El wrapper del job nunca levanta al scheduler aunque tick falle.

    Garantiza que APScheduler no pause el job por una excepción intermitente
    (ej. MELI 429 transitorio).
    """
    from argos import scheduler as scheduler_module

    failing_tick = AsyncMock(side_effect=RuntimeError("boom"))
    monkeypatch.setattr(scheduler_module, "scout_tick", failing_tick)

    db = MagicMock()
    # No debe levantar
    await scheduler_module._scout_tick_job(db)
    failing_tick.assert_awaited_once()
