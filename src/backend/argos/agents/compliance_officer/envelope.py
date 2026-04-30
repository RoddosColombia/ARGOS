"""Defaults canónicos del envelope de Compliance Officer (Build 2.5.4).

Cada `EnvelopeDefinition` describe qué rangos son aceptables para una acción
específica del sistema. Si una acción cae dentro del envelope → Plano 1
(ejecución automática con audit_log). Si cae fuera → escala a Plano 2 (CGO
aprueba) o Plano 3 (CEO aprueba).

Estos defaults son conservadores y se siembran al crear el workspace. El CEO
puede ajustarlos vía POST /api/v1/compliance/envelope (Plano 3 · audit_log).

Convención de `params` por action_type:
- pricing.adjust_meli       · params = {"delta_pct": float}     · envelope: |delta| ≤ max_delta_pct
- pricing.adjust_sismo      · idem
- bidding.adjust_meta       · params = {"delta_pct": float}     · idem
- bidding.adjust_google     · idem
- ad_set.pause              · params = {"ctr_pct": float, "hours_below": int}
                            · envelope: ctr<max_ctr_pct AND hours_below≥min_hours
- creative.suggest          · siempre Plano 2 (Compliance no permite ejecución directa, sólo sugerencia)
- campaign.budget_change    · params = {"delta_pct": float}
- compliance.envelope.update · siempre Plano 3 (CEO)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class EnvelopeDefinition:
    action_type: str
    plano: int                        # plano default si la acción cae dentro del envelope
    params_schema: dict[str, str]     # nombre → tipo (descriptivo, no validador)
    constraints: dict[str, Any]       # criterios numéricos del envelope
    description: str
    plano_if_outside: int = 2         # si cae fuera del envelope, escala a este plano


# Defaults canónicos · sembrados al crear el workspace · ajustables por CEO via API.
DEFAULT_ENVELOPES: tuple[EnvelopeDefinition, ...] = (
    EnvelopeDefinition(
        action_type="pricing.adjust_meli",
        plano=1,
        plano_if_outside=2,
        params_schema={"delta_pct": "float (porcentaje · positivo o negativo)"},
        constraints={"max_abs_delta_pct": 5.0},
        description=(
            "Ajuste de precio MELI dentro de ±5% sobre precio base. "
            "Pricing engine ejecuta auto si dentro · escala a CGO si afuera."
        ),
    ),
    EnvelopeDefinition(
        action_type="pricing.adjust_sismo",
        plano=1,
        plano_if_outside=2,
        params_schema={"delta_pct": "float"},
        constraints={"max_abs_delta_pct": 5.0},
        description="Ajuste de precio en catálogo SISMO · misma banda que MELI.",
    ),
    EnvelopeDefinition(
        action_type="bidding.adjust_meta",
        plano=1,
        plano_if_outside=2,
        params_schema={"delta_pct": "float"},
        constraints={"max_abs_delta_pct": 10.0},
        description="Ajuste de bid Meta Ads dentro de ±10% sobre bid actual.",
    ),
    EnvelopeDefinition(
        action_type="bidding.adjust_google",
        plano=1,
        plano_if_outside=2,
        params_schema={"delta_pct": "float"},
        constraints={"max_abs_delta_pct": 10.0},
        description="Ajuste de bid Google Ads dentro de ±10% sobre bid actual.",
    ),
    EnvelopeDefinition(
        action_type="ad_set.pause",
        plano=1,
        plano_if_outside=2,
        params_schema={
            "ctr_pct": "float (CTR observado del ad set · porcentaje)",
            "hours_below": "int (horas que lleva debajo del threshold)",
        },
        constraints={"max_ctr_pct": 0.5, "min_hours_below": 4},
        description=(
            "Auto-pausa de ad set si CTR<0.5% durante ≥4 horas. "
            "Si parámetros no cumplen → escala a CGO."
        ),
    ),
    EnvelopeDefinition(
        action_type="creative.suggest",
        plano=2,
        plano_if_outside=2,
        params_schema={"creative_count": "int"},
        constraints={},
        description=(
            "Sugerencia de creative · NUNCA Plano 1 · siempre requiere CGO. "
            "Compliance no permite que ARGOS lance creatives nuevos sin aprobación."
        ),
    ),
    EnvelopeDefinition(
        action_type="campaign.budget_change",
        plano=2,
        plano_if_outside=3,
        params_schema={"delta_pct": "float"},
        constraints={"max_abs_delta_pct": 25.0},
        description=(
            "Cambio de presupuesto de campaña ±25% requiere CGO. "
            "Mayor a 25% requiere CEO."
        ),
    ),
    EnvelopeDefinition(
        action_type="compliance.envelope.update",
        plano=3,
        plano_if_outside=3,
        params_schema={},
        constraints={},
        description=(
            "Actualizar el envelope mismo es decisión estratégica · "
            "siempre CEO con audit_log."
        ),
    ),
)


def serialize_envelope_doc(doc: dict[str, Any]) -> dict[str, Any]:
    """Convierte un documento Mongo de compliance_envelope en JSON serializable."""
    return {
        "id": str(doc.get("_id")) if doc.get("_id") else None,
        "action_type": doc.get("action_type"),
        "plano": int(doc.get("plano") or 0),
        "plano_if_outside": int(doc.get("plano_if_outside") or 0),
        "params_schema": doc.get("params_schema") or {},
        "constraints": doc.get("constraints") or {},
        "description": doc.get("description"),
        "active": bool(doc.get("active", True)),
        "approved_by": doc.get("approved_by"),
        "approved_at": doc["approved_at"].isoformat() if doc.get("approved_at") else None,
        "created_at": doc["created_at"].isoformat() if doc.get("created_at") else None,
        "updated_at": doc["updated_at"].isoformat() if doc.get("updated_at") else None,
    }


def envelope_def_to_doc(
    envelope: EnvelopeDefinition,
    *,
    workspace_id: str,
    approved_by: str,
    now,
) -> dict[str, Any]:
    """Convierte un `EnvelopeDefinition` en doc Mongo listo para insert/upsert."""
    return {
        "workspace_id": workspace_id,
        "action_type": envelope.action_type,
        "plano": envelope.plano,
        "plano_if_outside": envelope.plano_if_outside,
        "params_schema": dict(envelope.params_schema),
        "constraints": dict(envelope.constraints),
        "description": envelope.description,
        "active": True,
        "approved_by": approved_by,
        "approved_at": now,
        "created_at": now,
        "updated_at": now,
    }


# Re-export útil
__all__ = [
    "DEFAULT_ENVELOPES",
    "EnvelopeDefinition",
    "envelope_def_to_doc",
    "serialize_envelope_doc",
]
# field is imported so dataclass(frozen=True, default_factory=...) is available downstream
_ = field
