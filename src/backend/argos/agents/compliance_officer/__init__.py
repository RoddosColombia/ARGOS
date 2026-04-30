"""Compliance Officer · agente N2 que enforza ROGs en código (Build 2.5.4).

Cumple ROG-A2 (spending caps en código), ROG-A10 (veto sobre Media Buyer y
otros agentes con acción Plano 1 fuera de envelope), ROG-G2 (3 planos de
approval enforzados), ROG-G4 (envelope vive en colección, cambios requieren
aprobación CEO).

Exporta:
- ComplianceOfficer: clase de servicio principal
- ComplianceDecision: result tipo de validate_action()
- DEFAULT_ENVELOPES: defaults canónicos para seed inicial
- Plano: enum de los 3 planos
"""
from argos.agents.compliance_officer.envelope import (
    DEFAULT_ENVELOPES,
    EnvelopeDefinition,
    serialize_envelope_doc,
)
from argos.agents.compliance_officer.service import (
    ComplianceDecision,
    ComplianceOfficer,
    ComplianceOfficerError,
    Plano,
    seed_default_envelopes,
)

__all__ = [
    "ComplianceDecision",
    "ComplianceOfficer",
    "ComplianceOfficerError",
    "DEFAULT_ENVELOPES",
    "EnvelopeDefinition",
    "Plano",
    "seed_default_envelopes",
    "serialize_envelope_doc",
]
