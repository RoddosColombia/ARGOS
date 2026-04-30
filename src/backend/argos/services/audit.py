"""Audit log writer · cumple ROG-A12 (toda acción auditable con quién/qué/cuándo/contexto).

Schema persistido en colección `audit_log` (ver docs/canonicas/colecciones_mongo.md):

    {
        "_id":           ObjectId,
        "workspace_id":  str,                   # ROG-A3
        "timestamp_utc": datetime UTC,
        "actor_type":    "user" | "system" | "agent",
        "actor_id":      str,                   # email | "sistema" | nombre del agente
        "actor_role":    str | None,            # ceo|cgo|analista|sistema|cliente · ROG-G3
        "action":        str,                   # dot.notation · ej "auth.login.success"
        "resource_type": str | None,            # tipo de recurso afectado
        "resource_id":   str | None,            # id del recurso
        "result":        "success" | "failure",
        "metadata":      dict,                  # contexto adicional (sin PII)
        "ip_address":    str | None,
    }

Reglas:
- ROG-A9 · NO persistir PII de terceros directamente. Si necesitas registrar
  actividad sobre datos sensibles, usa hash o referencia indirecta en metadata.
- ROG-A6 · este writer NUNCA toca `argos_events`. Es persistencia separada.
- Si MongoDB no está disponible, el writer falla silenciosamente con log warning
  y NO levanta excepción al caller. Es preferible perder un audit que romper
  el flujo de negocio. Esto es trade-off explícito documentado acá.

Uso típico desde un endpoint:

    from argos.services.audit import audit_write, ActorType, ActionResult

    await audit_write(
        db,
        workspace_id=user.workspace_id,
        actor_type=ActorType.USER,
        actor_id=user.email,
        actor_role=user.role,
        action="auth.login.success",
        result=ActionResult.SUCCESS,
        ip_address=request.client.host if request.client else None,
    )
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from argos.db import collections as col

logger = logging.getLogger("argos.services.audit")


class ActorType(StrEnum):
    USER = "user"
    SYSTEM = "system"
    AGENT = "agent"


class ActionResult(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"


class ActorRole(StrEnum):
    """Roles canónicos · alineados con users.role en MongoDB y JWT claims."""

    CEO = "ceo"
    CGO = "cgo"
    ANALISTA = "analista"
    SISTEMA = "sistema"
    CLIENTE = "cliente"


VALID_ACTOR_TYPES: frozenset[str] = frozenset(ActorType)
VALID_RESULTS: frozenset[str] = frozenset(ActionResult)
VALID_ROLES: frozenset[str] = frozenset(ActorRole)


class AuditValidationError(ValueError):
    """Raised cuando los campos requeridos del audit_write no son válidos."""


def _validate(
    workspace_id: str,
    actor_type: str,
    actor_id: str,
    action: str,
    actor_role: str | None,
    result: str,
) -> None:
    if not workspace_id:
        raise AuditValidationError("workspace_id es obligatorio (ROG-A3)")
    if actor_type not in VALID_ACTOR_TYPES:
        raise AuditValidationError(
            f"actor_type inválido · {actor_type!r} no en {sorted(VALID_ACTOR_TYPES)}",
        )
    if not actor_id:
        raise AuditValidationError("actor_id es obligatorio")
    if not action or "." not in action:
        raise AuditValidationError(
            "action debe usar dot.notation (ej 'auth.login.success')",
        )
    if result not in VALID_RESULTS:
        raise AuditValidationError(
            f"result inválido · {result!r} no en {sorted(VALID_RESULTS)}",
        )
    if actor_role is not None and actor_role not in VALID_ROLES:
        raise AuditValidationError(
            f"actor_role inválido · {actor_role!r} no en {sorted(VALID_ROLES)}",
        )


async def audit_write(
    db: AsyncIOMotorDatabase | None,
    *,
    workspace_id: str,
    actor_type: str | ActorType,
    actor_id: str,
    action: str,
    actor_role: str | ActorRole | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    result: str | ActionResult = ActionResult.SUCCESS,
    metadata: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> dict[str, Any] | None:
    """Persiste un evento auditable en `audit_log`.

    Devuelve el documento persistido (con `_id`) si fue exitoso.
    Devuelve `None` si MongoDB no está disponible (skip silencioso con log).

    Levanta `AuditValidationError` si los campos requeridos son inválidos
    (esto es bug del caller, no del entorno).
    """
    actor_type_str = str(actor_type)
    actor_role_str = str(actor_role) if actor_role is not None else None
    result_str = str(result)

    _validate(
        workspace_id=workspace_id,
        actor_type=actor_type_str,
        actor_id=actor_id,
        action=action,
        actor_role=actor_role_str,
        result=result_str,
    )

    if db is None:
        logger.warning(
            "audit_write_skipped_no_db",
            extra={"workspace_id": workspace_id, "action": action, "actor_id": actor_id},
        )
        return None

    doc: dict[str, Any] = {
        "workspace_id": workspace_id,
        "timestamp_utc": datetime.now(tz=UTC),
        "actor_type": actor_type_str,
        "actor_id": actor_id,
        "actor_role": actor_role_str,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "result": result_str,
        "metadata": metadata or {},
        "ip_address": ip_address,
    }

    try:
        result_op = await db[col.AUDIT_LOG].insert_one(doc)
    except Exception as exc:  # noqa: BLE001 · cualquier fallo de Mongo no debe romper el flujo
        logger.warning(
            "audit_write_failed",
            extra={
                "workspace_id": workspace_id,
                "action": action,
                "actor_id": actor_id,
                "error": str(exc)[:200],
            },
        )
        return None

    doc["_id"] = result_op.inserted_id
    logger.info(
        "audit_written",
        extra={
            "workspace_id": workspace_id,
            "action": action,
            "actor_id": actor_id,
            "result": result_str,
        },
    )
    return doc
