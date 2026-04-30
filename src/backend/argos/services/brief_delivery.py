"""Brief delivery · entrega simultánea CEO + CGO (Build 2.5.5 · ROG-G1).

ROG-G1: Output unificado CEO + CGO. Todos los reportes, briefs, dashboards y
notificaciones se entregan **simultáneamente, mismo formato, mismo contenido**
a CEO (Andrés San Juan) y CGO (Iván Echeverri). No hay versión cliente-side ni
delegación de información. Diferenciación SOLO en cola de approvals según role.

Este módulo expone:
- `list_leadership_emails(db, workspace_id)` · lectura de emails de los users
  con role `ceo` o `cgo` activos en el workspace.
- `send_brief_to_leadership(db, workspace_id, brief)` · entrega el brief a CEO
  + CGO simultáneamente. Hoy registra logs + audit_log; cuando entre Phase 3
  WhatsApp Agent y email integration, este helper se extiende para enviar por
  los canales activos (WhatsApp utility template + email + dashboard).

El brief mismo se persiste en colección `briefings` (Build 3.1) por separado.
Este helper solo se encarga de la entrega al leadership, no de la persistencia.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from argos.db import collections as col
from argos.services.audit import ActionResult, ActorType, audit_write

logger = logging.getLogger("argos.services.brief_delivery")


class BriefChannel(StrEnum):
    """Canales por los que un brief puede entregarse a leadership."""

    DASHBOARD = "dashboard"          # frontend siempre disponible · default
    WHATSAPP = "whatsapp"            # cuando entre Mercately (Phase 3+)
    EMAIL = "email"                  # cuando entre integración email
    LOG_ONLY = "log_only"            # dev/testing · solo loguea, no envía


@dataclass(frozen=True)
class BriefRecipient:
    """Un destinatario del brief · siempre uno por role activo."""

    email: str
    role: str                        # "ceo" o "cgo"


@dataclass(frozen=True)
class BriefDeliveryResult:
    """Resultado de send_brief_to_leadership."""

    delivered_to: tuple[BriefRecipient, ...]
    channels_used: tuple[str, ...]
    delivered_at: datetime
    brief_id: str | None             # id del brief en colección `briefings` si aplica
    skipped_reason: str | None       # populated si delivered_to está vacío


class BriefDeliveryError(Exception):
    """Error operativo de la entrega del brief."""


# ─── Lectura de leadership ──────────────────────────────────────────────


async def list_leadership_emails(
    db: AsyncIOMotorDatabase,
    *,
    workspace_id: str,
) -> list[BriefRecipient]:
    """Devuelve los users con role `ceo` o `cgo` activos en el workspace.

    Si no hay ningún user con esos roles, devuelve lista vacía. El caller decide
    si tratar eso como warning o como error de configuración.
    """
    if not workspace_id:
        raise BriefDeliveryError("workspace_id es obligatorio (ROG-A3)")

    cursor = db[col.USERS].find(
        {"workspace_id": workspace_id, "roles": {"$in": ["ceo", "cgo"]}},
        {"email": 1, "roles": 1, "_id": 0},
    )
    docs = await cursor.to_list(length=20)

    recipients: list[BriefRecipient] = []
    seen_emails: set[str] = set()
    for d in docs:
        email = (d.get("email") or "").lower()
        roles = d.get("roles") or []
        if not email or email in seen_emails:
            continue
        # Tomamos el primer role del array que sea ceo o cgo
        primary_role: str | None = None
        for r in roles:
            if r in ("ceo", "cgo"):
                primary_role = r
                break
        if primary_role is None:
            continue
        recipients.append(BriefRecipient(email=email, role=primary_role))
        seen_emails.add(email)

    return recipients


# ─── Entrega ────────────────────────────────────────────────────────────


async def send_brief_to_leadership(
    db: AsyncIOMotorDatabase | None,
    *,
    workspace_id: str,
    brief: dict[str, Any],
    channels: tuple[str, ...] = (BriefChannel.DASHBOARD.value,),
    brief_id: str | None = None,
) -> BriefDeliveryResult:
    """Entrega el brief a CEO + CGO simultáneamente · cumple ROG-G1.

    `brief` es un dict con el contenido sintetizado (típicamente lo que produce
    el Strategist + Executive). Este helper NO genera el brief; solo lo enruta.

    `channels` declara qué canales activar. Hoy soporta:
    - DASHBOARD: siempre se asume disponible · sólo loguea + audita.
    - LOG_ONLY: para dev/testing.
    - WHATSAPP: stub para Phase 3+ (cuando entre Mercately).
    - EMAIL: stub para integración futura.

    Audit: cada entrega genera un evento `brief.delivered.<role>` en audit_log
    por destinatario, lo que permite trazar quién recibió qué cuándo (ROG-G3).
    """
    if not workspace_id:
        raise BriefDeliveryError("workspace_id es obligatorio (ROG-A3)")
    if not isinstance(brief, dict):
        raise BriefDeliveryError("brief debe ser dict")

    delivered_at = datetime.now(tz=UTC)

    if db is None:
        # Skip silencioso · igual que audit_write y opt_in (consistencia repo)
        logger.warning(
            "brief_delivery_skipped_no_db",
            extra={"workspace_id": workspace_id},
        )
        return BriefDeliveryResult(
            delivered_to=(),
            channels_used=(),
            delivered_at=delivered_at,
            brief_id=brief_id,
            skipped_reason="no_db",
        )

    recipients = await list_leadership_emails(db, workspace_id=workspace_id)
    if not recipients:
        logger.warning(
            "brief_delivery_no_recipients",
            extra={"workspace_id": workspace_id},
        )
        return BriefDeliveryResult(
            delivered_to=(),
            channels_used=(),
            delivered_at=delivered_at,
            brief_id=brief_id,
            skipped_reason="no_leadership_users",
        )

    # ROG-G1 · entrega simultánea: todos los recipients reciben el mismo
    # contenido y los mismos canales. Ningún role recibe info "extra".
    channels_set = tuple(sorted(set(channels))) or (BriefChannel.DASHBOARD.value,)

    for recipient in recipients:
        # DASHBOARD: el frontend lo lee del endpoint /api/v1/briefing en cada
        # carga · no necesita "envío" activo · sólo log + audit.
        if BriefChannel.DASHBOARD.value in channels_set:
            logger.info(
                "brief_delivered_dashboard",
                extra={
                    "workspace_id": workspace_id,
                    "recipient_email": recipient.email,
                    "recipient_role": recipient.role,
                    "brief_id": brief_id,
                },
            )

        # WHATSAPP / EMAIL: stubs para integración futura · loguean intent
        if BriefChannel.WHATSAPP.value in channels_set:
            logger.info(
                "brief_delivery_whatsapp_pending",
                extra={
                    "workspace_id": workspace_id,
                    "recipient_email": recipient.email,
                    "note": "Mercately integration · Phase 3+",
                },
            )
        if BriefChannel.EMAIL.value in channels_set:
            logger.info(
                "brief_delivery_email_pending",
                extra={
                    "workspace_id": workspace_id,
                    "recipient_email": recipient.email,
                    "note": "Email integration · pendiente",
                },
            )

        # Audit por recipient · cumple ROG-G3 (trazabilidad por role)
        await audit_write(
            db,
            workspace_id=workspace_id,
            actor_type=ActorType.SYSTEM,
            actor_id="argos.services.brief_delivery",
            actor_role="sistema",
            action=f"brief.delivered.{recipient.role}",
            resource_type="brief",
            resource_id=brief_id,
            result=ActionResult.SUCCESS,
            metadata={
                "recipient_email": recipient.email,
                "recipient_role": recipient.role,
                "channels": list(channels_set),
                "brief_summary": (brief.get("estado_mercado") or "")[:300],
            },
        )

    logger.info(
        "brief_delivered_to_leadership",
        extra={
            "workspace_id": workspace_id,
            "recipients_count": len(recipients),
            "channels": list(channels_set),
            "brief_id": brief_id,
        },
    )
    return BriefDeliveryResult(
        delivered_to=tuple(recipients),
        channels_used=channels_set,
        delivered_at=delivered_at,
        brief_id=brief_id,
        skipped_reason=None,
    )


__all__ = [
    "BriefChannel",
    "BriefDeliveryError",
    "BriefDeliveryResult",
    "BriefRecipient",
    "list_leadership_emails",
    "send_brief_to_leadership",
]
