"""Event publisher para el bus argos_events (ROG-A6 · append-only, inmutable).

Ver docs/canonicas/eventos.md para el schema base y el catálogo de event_types.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase
from ulid import ULID

from argos.db import collections as col

logger = logging.getLogger("argos.db.events")

EVENT_SCHEMA_VERSION = "1.0"


class EventValidationError(ValueError):
    """Raised cuando un evento no cumple el schema mínimo."""


def _validate(event_type: str, workspace_id: str, producer: str, payload: dict[str, Any]) -> None:
    if not event_type or "." not in event_type:
        raise EventValidationError("event_type debe usar dot.notation (ej: score.evaluated)")
    if not workspace_id:
        raise EventValidationError("workspace_id es obligatorio (ROG-A3)")
    if not producer:
        raise EventValidationError("producer es obligatorio")
    if not isinstance(payload, dict):
        raise EventValidationError("payload debe ser dict")


async def publish_event(
    db: AsyncIOMotorDatabase,
    *,
    event_type: str,
    workspace_id: str,
    producer: str,
    payload: dict[str, Any],
    correlation_id: str | None = None,
    causation_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    version: str = EVENT_SCHEMA_VERSION,
) -> dict[str, Any]:
    """Emite un evento al bus. Devuelve el documento persistido (con event_id ULID).

    Idempotencia: si dos emisiones usan el mismo event_id, la segunda fallará
    por el índice unique (event_id). Es responsabilidad del caller usar ULIDs
    frescos · en flujos con retry se debe cachear el event_id generado.
    """
    _validate(event_type, workspace_id, producer, payload)

    event_id = f"evt_{ULID()}"
    doc: dict[str, Any] = {
        "event_id": event_id,
        "event_type": event_type,
        "version": version,
        "workspace_id": workspace_id,
        "timestamp_utc": datetime.now(tz=UTC),
        "producer": producer,
        "correlation_id": correlation_id,
        "causation_id": causation_id,
        "payload": payload,
        "metadata": metadata or {},
    }
    await db[col.ARGOS_EVENTS].insert_one(doc)
    logger.info(
        "event_published",
        extra={"event_id": event_id, "event_type": event_type, "workspace_id": workspace_id},
    )
    return doc
