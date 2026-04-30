"""Compliance Officer · valida acciones contra envelope (Build 2.5.4).

Patrón de uso (TODO agente con acción Plano 1 debe hacer esto antes de ejecutar):

    from argos.agents.compliance_officer import ComplianceOfficer

    officer = ComplianceOfficer(db)
    decision = await officer.validate_action(
        workspace_id=user.workspace_id,
        action_type="pricing.adjust_meli",
        params={"delta_pct": 3.5},
        requested_by=user.email,
    )
    if decision.allowed and decision.plano_required == 1:
        # Ejecutar · auditar
        ...
    elif decision.plano_required == 2:
        # Escalar a CGO
        ...
    elif decision.plano_required == 3:
        # Escalar a CEO
        ...

ComplianceOfficer NO ejecuta acciones · sólo valida. Es el último filtro antes
de que cualquier agente con acción Plano 1 toque dinero o canal.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import IntEnum
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from argos.agents.compliance_officer.envelope import (
    DEFAULT_ENVELOPES,
    EnvelopeDefinition,
    envelope_def_to_doc,
)
from argos.db import collections as col

logger = logging.getLogger("argos.agents.compliance_officer")


class Plano(IntEnum):
    PLANO_1_AUTO = 1
    PLANO_2_CGO = 2
    PLANO_3_CEO = 3


@dataclass(frozen=True)
class ComplianceDecision:
    """Resultado de validate_action()."""

    allowed: bool                     # True = se puede ejecutar en el plano que indica plano_required
    plano_required: int               # 1, 2 o 3
    reason: str                       # explicación human-readable del veredicto
    action_type: str                  # eco del input
    envelope_present: bool            # si encontró envelope para este action_type


class ComplianceOfficerError(Exception):
    """Error operativo del Compliance Officer (no de validación de input)."""


class ComplianceOfficer:
    """Servicio de Compliance · stateless desde fuera (toda llamada lee envelope live)."""

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self._db = db

    async def get_envelope(
        self,
        *,
        workspace_id: str,
        action_type: str,
    ) -> dict[str, Any] | None:
        """Lectura del envelope vigente para un action_type del workspace.

        Devuelve None si no existe (acción no envelope-protected).
        """
        if not workspace_id:
            raise ComplianceOfficerError("workspace_id es obligatorio (ROG-A3)")
        return await self._db[col.COMPLIANCE_ENVELOPE].find_one(
            {"workspace_id": workspace_id, "action_type": action_type, "active": True},
        )

    async def list_envelopes(self, *, workspace_id: str) -> list[dict[str, Any]]:
        """Listado de envelopes activos del workspace."""
        if not workspace_id:
            raise ComplianceOfficerError("workspace_id es obligatorio (ROG-A3)")
        cursor = self._db[col.COMPLIANCE_ENVELOPE].find(
            {"workspace_id": workspace_id, "active": True},
        ).sort("action_type", 1)
        return await cursor.to_list(length=200)

    async def is_within_envelope(
        self,
        *,
        envelope: dict[str, Any],
        params: dict[str, Any],
    ) -> tuple[bool, str]:
        """Evalúa si los params caen dentro del envelope.

        Devuelve (within, reason). `within=True` significa que se puede ejecutar
        al plano declarado por el envelope. `within=False` significa que se
        debe escalar al `plano_if_outside`.

        La lógica es declarativa por action_type. Si llega un action_type
        nuevo sin lógica explícita acá, se considera siempre within=False
        (fail-safe: escala al plano_if_outside).
        """
        action_type = envelope.get("action_type", "")
        constraints = envelope.get("constraints") or {}

        if action_type in {
            "pricing.adjust_meli",
            "pricing.adjust_sismo",
            "bidding.adjust_meta",
            "bidding.adjust_google",
            "campaign.budget_change",
        }:
            try:
                delta = float(params.get("delta_pct", 0.0))
            except (TypeError, ValueError):
                return False, "param 'delta_pct' inválido (no numérico)"
            max_abs = float(constraints.get("max_abs_delta_pct", 0.0))
            if abs(delta) <= max_abs:
                return True, f"|delta_pct|={abs(delta):.2f}% ≤ {max_abs}%"
            return (
                False,
                f"|delta_pct|={abs(delta):.2f}% > envelope max {max_abs}%",
            )

        if action_type == "ad_set.pause":
            try:
                ctr = float(params.get("ctr_pct", 999.0))
                hours = int(params.get("hours_below", 0))
            except (TypeError, ValueError):
                return False, "params 'ctr_pct'/'hours_below' inválidos"
            max_ctr = float(constraints.get("max_ctr_pct", 0.0))
            min_hours = int(constraints.get("min_hours_below", 0))
            if ctr <= max_ctr and hours >= min_hours:
                return True, (
                    f"ctr_pct={ctr:.2f}% ≤ {max_ctr}% AND hours_below={hours} ≥ {min_hours}"
                )
            return False, (
                f"requiere ctr_pct≤{max_ctr}% Y hours_below≥{min_hours} · "
                f"obtuvo ctr_pct={ctr:.2f}% hours_below={hours}"
            )

        if action_type == "creative.suggest":
            # Siempre Plano 2 · no hay banda · within=True conceptualmente
            # (lo que cambia es que el plano declarado del envelope ya es 2)
            return True, "creative.suggest siempre requiere CGO · sin banda numérica"

        if action_type == "compliance.envelope.update":
            # Siempre Plano 3 · sin banda
            return True, "compliance.envelope.update siempre requiere CEO"

        # action_type desconocido → fail-safe
        return False, f"action_type {action_type!r} sin lógica de envelope · escala"

    async def validate_action(
        self,
        *,
        workspace_id: str,
        action_type: str,
        params: dict[str, Any] | None = None,
        requested_by: str = "sistema",
    ) -> ComplianceDecision:
        """Valida una acción · devuelve el plano requerido para aprobación.

        Este es el punto de entrada que TODO agente con acción Plano 1 debe
        llamar antes de ejecutar. Si retorna `plano_required > 1`, la acción
        NO se ejecuta · queda en cola del role indicado.
        """
        if not workspace_id:
            raise ComplianceOfficerError("workspace_id es obligatorio (ROG-A3)")
        if not action_type or "." not in action_type:
            raise ComplianceOfficerError(
                "action_type debe usar dot.notation (ej 'pricing.adjust_meli')",
            )
        params = params or {}

        envelope = await self.get_envelope(
            workspace_id=workspace_id, action_type=action_type,
        )

        if envelope is None:
            # No hay envelope configurado para este action_type
            # Política: fail-safe · se requiere Plano 3 (CEO) hasta que el envelope se defina
            logger.info(
                "compliance_no_envelope",
                extra={
                    "workspace_id": workspace_id,
                    "action_type": action_type,
                    "requested_by": requested_by,
                },
            )
            return ComplianceDecision(
                allowed=False,
                plano_required=int(Plano.PLANO_3_CEO),
                reason=(
                    f"No hay envelope activo para {action_type!r} · requiere CEO "
                    "definir el envelope antes de ejecutar"
                ),
                action_type=action_type,
                envelope_present=False,
            )

        within, reason = await self.is_within_envelope(envelope=envelope, params=params)
        plano_required = int(envelope.get("plano") or 2) if within else int(envelope.get("plano_if_outside") or 2)

        # Si el plano envelope es 1 y within=True, la acción se considera "allowed"
        # para ejecución automática. Cualquier otro caso requiere approval humano
        # del role correspondiente.
        allowed = within and plano_required == int(Plano.PLANO_1_AUTO)

        logger.info(
            "compliance_validated",
            extra={
                "workspace_id": workspace_id,
                "action_type": action_type,
                "plano_required": plano_required,
                "within": within,
                "allowed": allowed,
                "requested_by": requested_by,
            },
        )

        return ComplianceDecision(
            allowed=allowed,
            plano_required=plano_required,
            reason=reason,
            action_type=action_type,
            envelope_present=True,
        )

    async def upsert_envelope(
        self,
        *,
        workspace_id: str,
        action_type: str,
        plano: int,
        plano_if_outside: int,
        params_schema: dict[str, str],
        constraints: dict[str, Any],
        description: str,
        approved_by: str,
    ) -> dict[str, Any]:
        """Crea o actualiza un envelope · sólo CEO debería llamar esto.

        El endpoint API enforza que sea CEO. Este método no chequea role
        (asume que el caller ya validó). Audit log responsabilidad del caller.
        """
        if not workspace_id:
            raise ComplianceOfficerError("workspace_id es obligatorio (ROG-A3)")
        if plano not in (1, 2, 3):
            raise ComplianceOfficerError("plano debe ser 1, 2 o 3")
        if plano_if_outside not in (1, 2, 3):
            raise ComplianceOfficerError("plano_if_outside debe ser 1, 2 o 3")

        now = datetime.now(tz=UTC)

        # Actualiza el doc activo si existe; si no, inserta nuevo.
        update_doc = {
            "$set": {
                "plano": plano,
                "plano_if_outside": plano_if_outside,
                "params_schema": params_schema,
                "constraints": constraints,
                "description": description,
                "active": True,
                "approved_by": approved_by,
                "approved_at": now,
                "updated_at": now,
            },
            "$setOnInsert": {
                "workspace_id": workspace_id,
                "action_type": action_type,
                "created_at": now,
            },
        }
        await self._db[col.COMPLIANCE_ENVELOPE].update_one(
            {"workspace_id": workspace_id, "action_type": action_type, "active": True},
            update_doc,
            upsert=True,
        )
        doc = await self._db[col.COMPLIANCE_ENVELOPE].find_one(
            {"workspace_id": workspace_id, "action_type": action_type, "active": True},
        )
        return doc or {}


async def seed_default_envelopes(
    db: AsyncIOMotorDatabase,
    *,
    workspace_id: str,
    approved_by: str,
) -> int:
    """Idempotente: siembra los envelopes default si no existen.

    Devuelve el número de envelopes recién creados (no actualiza los existentes).
    """
    if not workspace_id:
        raise ComplianceOfficerError("workspace_id es obligatorio (ROG-A3)")

    now = datetime.now(tz=UTC)
    inserted = 0
    for envelope_def in DEFAULT_ENVELOPES:
        doc = envelope_def_to_doc(
            envelope_def,
            workspace_id=workspace_id,
            approved_by=approved_by,
            now=now,
        )
        result = await db[col.COMPLIANCE_ENVELOPE].update_one(
            {
                "workspace_id": workspace_id,
                "action_type": envelope_def.action_type,
                "active": True,
            },
            {"$setOnInsert": doc},
            upsert=True,
        )
        if result.upserted_id is not None:
            inserted += 1
    if inserted > 0:
        logger.info(
            "compliance_envelopes_seeded",
            extra={"workspace_id": workspace_id, "inserted": inserted},
        )
    return inserted


__all__ = [
    "ComplianceDecision",
    "ComplianceOfficer",
    "ComplianceOfficerError",
    "Plano",
    "seed_default_envelopes",
]


def _envelope_def_unused_marker() -> EnvelopeDefinition:
    """Marker · evita warning de import-not-used del re-export."""
    return DEFAULT_ENVELOPES[0]
