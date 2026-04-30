"""Opt-in registry service · cumple ROG-W1 preventivo (Build 2.5.3).

ROG-W1: opt-in explícito antes de cualquier mensaje proactivo. Sin opt-in
registrado en `contacts` con timestamp + canal de obtención no se envía nada.
Enforced en código.

Este módulo expone:
- `record_opt_in(...)`        upsert del flag de opt-in con audit trail
- `record_opt_out(...)`       cambia status a opted_out (preserva la huella original)
- `get_opt_status(...)`       lectura del estado vigente
- `can_send_proactive(...)`   gate que TODO outbound proactivo debe llamar antes de enviar

Schema persistido en colección `contacts`:

    {
        "_id":             ObjectId,
        "workspace_id":    str,                    # ROG-A3
        "phone_number":    str (E.164),            # unique por workspace
        "name":            str | None,
        "customer_id_sismo": str | None,           # FK al loanbook si aplica
        "opt_in_marketing": {
            "status":               "opted_in" | "opted_out" | "pending",
            "captured_at":          datetime UTC,
            "channel":              "sms" | "web" | "whatsapp_inbound" | "sales_call",
            "consent_text_version": str,
            "captured_by":          str,           # email del operador o "self_inbound"
            "history":              list[dict],    # append-only de cambios
        },
        "opt_in_utility":   { idem },
        "last_message_at":  datetime | None,
        "created_at":       datetime UTC,
        "updated_at":       datetime UTC,
    }

Cuando `can_send_proactive` retorna `(False, reason)`, el caller DEBE bloquear
el envío y loggear · no negociable. Esta es la barrera última de ROG-W1.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from argos.db import collections as col

logger = logging.getLogger("argos.services.opt_in")


class OptInType(StrEnum):
    MARKETING = "marketing"
    UTILITY = "utility"


class OptInStatus(StrEnum):
    OPTED_IN = "opted_in"
    OPTED_OUT = "opted_out"
    PENDING = "pending"


class OptInChannel(StrEnum):
    SMS = "sms"
    WEB = "web"
    WHATSAPP_INBOUND = "whatsapp_inbound"
    SALES_CALL = "sales_call"
    QR_EMPAQUE = "qr_empaque"


VALID_TYPES: frozenset[str] = frozenset(OptInType)
VALID_STATUSES: frozenset[str] = frozenset(OptInStatus)
VALID_CHANNELS: frozenset[str] = frozenset(OptInChannel)


class OptInValidationError(ValueError):
    """Raised cuando un campo de opt-in es inválido."""


def _field_for(opt_type: str) -> str:
    """Maps `marketing` → `opt_in_marketing`, `utility` → `opt_in_utility`."""
    if opt_type not in VALID_TYPES:
        raise OptInValidationError(f"opt_in type inválido · {opt_type!r} no en {sorted(VALID_TYPES)}")
    return f"opt_in_{opt_type}"


def _normalize_phone(phone_number: str) -> str:
    """E.164 mínimo: empieza con `+` seguido de dígitos. NO valida país; eso lo hace Mercately."""
    cleaned = phone_number.strip()
    if not cleaned.startswith("+") or not cleaned[1:].isdigit() or len(cleaned) < 8:
        raise OptInValidationError(
            f"phone_number debe ser E.164 (+57...) · recibido {phone_number!r}",
        )
    return cleaned


async def record_opt_in(
    db: AsyncIOMotorDatabase,
    *,
    workspace_id: str,
    phone_number: str,
    opt_type: str,
    channel: str,
    consent_text_version: str,
    captured_by: str,
    name: str | None = None,
) -> dict[str, Any]:
    """Registra opt-in · upsert el contact + setea `opt_in_<type>` con audit trail.

    Si el contact no existe, lo crea con phone + opt-in en una sola operación.
    Si existe y ya estaba opted_in, actualiza timestamps y agrega entry al history.
    """
    if not workspace_id:
        raise OptInValidationError("workspace_id es obligatorio (ROG-A3)")
    phone = _normalize_phone(phone_number)
    field = _field_for(opt_type)
    if channel not in VALID_CHANNELS:
        raise OptInValidationError(
            f"channel inválido · {channel!r} no en {sorted(VALID_CHANNELS)}",
        )
    if not consent_text_version:
        raise OptInValidationError("consent_text_version es obligatorio (auditabilidad)")
    if not captured_by:
        raise OptInValidationError("captured_by es obligatorio (responsabilidad)")

    now = datetime.now(tz=UTC)
    # Mongo error 40: `$set: {field: {...}}` + `$push: {field.history}` chocan
    # porque ambos atacan la raíz `field`. Solución: $set por sub-path (status,
    # captured_at, etc.) deja `field.history` libre para que $push lo extienda.
    update_doc: dict[str, Any] = {
        "$set": {
            f"{field}.status": OptInStatus.OPTED_IN.value,
            f"{field}.captured_at": now,
            f"{field}.channel": channel,
            f"{field}.consent_text_version": consent_text_version,
            f"{field}.captured_by": captured_by,
            "updated_at": now,
        },
        "$push": {
            f"{field}.history": {
                "status": OptInStatus.OPTED_IN.value,
                "at": now,
                "channel": channel,
                "captured_by": captured_by,
            },
        },
        "$setOnInsert": {
            "workspace_id": workspace_id,
            "phone_number": phone,
            "created_at": now,
            "name": name,
            "customer_id_sismo": None,
        },
    }

    await db[col.CONTACTS].update_one(
        {"workspace_id": workspace_id, "phone_number": phone},
        update_doc,
        upsert=True,
    )
    doc = await db[col.CONTACTS].find_one({"workspace_id": workspace_id, "phone_number": phone})
    logger.info(
        "opt_in_recorded",
        extra={
            "workspace_id": workspace_id,
            "phone_number": phone,
            "opt_type": opt_type,
            "channel": channel,
        },
    )
    return doc or {}


async def record_opt_out(
    db: AsyncIOMotorDatabase,
    *,
    workspace_id: str,
    phone_number: str,
    opt_type: str,
    captured_by: str,
    reason: str | None = None,
) -> dict[str, Any] | None:
    """Registra opt-out · cambia status a opted_out · preserva history.

    Devuelve None si el contact no existe (no se crea contact por opt-out).
    """
    if not workspace_id:
        raise OptInValidationError("workspace_id es obligatorio (ROG-A3)")
    phone = _normalize_phone(phone_number)
    field = _field_for(opt_type)
    if not captured_by:
        raise OptInValidationError("captured_by es obligatorio")

    now = datetime.now(tz=UTC)
    update_doc: dict[str, Any] = {
        "$set": {
            f"{field}.status": OptInStatus.OPTED_OUT.value,
            f"{field}.opted_out_at": now,
            f"{field}.opted_out_by": captured_by,
            "updated_at": now,
        },
        "$push": {
            f"{field}.history": {
                "status": OptInStatus.OPTED_OUT.value,
                "at": now,
                "captured_by": captured_by,
                "reason": (reason or "")[:200],
            },
        },
    }

    result = await db[col.CONTACTS].update_one(
        {"workspace_id": workspace_id, "phone_number": phone},
        update_doc,
    )
    if result.matched_count == 0:
        logger.info(
            "opt_out_no_contact",
            extra={"workspace_id": workspace_id, "phone_number": phone},
        )
        return None
    doc = await db[col.CONTACTS].find_one({"workspace_id": workspace_id, "phone_number": phone})
    logger.info(
        "opt_out_recorded",
        extra={
            "workspace_id": workspace_id,
            "phone_number": phone,
            "opt_type": opt_type,
        },
    )
    return doc


async def get_opt_status(
    db: AsyncIOMotorDatabase,
    *,
    workspace_id: str,
    phone_number: str,
) -> dict[str, Any] | None:
    """Devuelve el doc completo del contact o None si no existe."""
    if not workspace_id:
        raise OptInValidationError("workspace_id es obligatorio (ROG-A3)")
    phone = _normalize_phone(phone_number)
    return await db[col.CONTACTS].find_one(
        {"workspace_id": workspace_id, "phone_number": phone},
    )


async def can_send_proactive(
    db: AsyncIOMotorDatabase | None,
    *,
    workspace_id: str,
    phone_number: str,
    opt_type: str = OptInType.MARKETING.value,
) -> tuple[bool, str | None]:
    """Gate para TODO outbound proactivo · ROG-W1.

    Devuelve `(allowed, reason)`:
    - `(True, None)` si y solo si existe contact con `opt_in_<type>.status == "opted_in"`
    - `(False, "no_db")`             si MongoDB no está conectado (fail-safe: no enviar)
    - `(False, "contact_not_found")` si el phone no está en `contacts`
    - `(False, "no_opt_in")`         si nunca dio opt-in (status != opted_in)
    - `(False, "opted_out")`         si dio opt-out

    Caller debe loggear el reason cuando bloquea. Esta es la barrera última de ROG-W1.
    """
    if db is None:
        logger.warning(
            "can_send_proactive_no_db",
            extra={"workspace_id": workspace_id, "phone_number": phone_number, "opt_type": opt_type},
        )
        return False, "no_db"

    if opt_type not in VALID_TYPES:
        raise OptInValidationError(f"opt_type inválido · {opt_type!r}")

    phone = _normalize_phone(phone_number)
    field = _field_for(opt_type)

    doc = await db[col.CONTACTS].find_one(
        {"workspace_id": workspace_id, "phone_number": phone},
        {field: 1, "_id": 1},
    )
    if doc is None:
        return False, "contact_not_found"

    opt_in_block = doc.get(field) or {}
    status = opt_in_block.get("status")
    if status == OptInStatus.OPTED_IN.value:
        return True, None
    if status == OptInStatus.OPTED_OUT.value:
        return False, "opted_out"
    return False, "no_opt_in"
