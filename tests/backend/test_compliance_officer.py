"""Tests del Compliance Officer · Plano 1 envelope (Build 2.5.4 · ROG-A2 + ROG-A10).

Cubre:
- Validación de inputs (workspace_id, action_type formato dot.notation)
- get_envelope: lectura, no encontrado
- is_within_envelope: pricing/bidding (delta_pct), ad_set.pause (ctr+hours),
  creative.suggest, action_type desconocido
- validate_action: dentro/fuera del envelope, no envelope (fail-safe Plano 3)
- upsert_envelope: crear nuevo, actualizar existente, validación de plano
- seed_default_envelopes: idempotente (no duplica)
- ComplianceDecision shape

Tests de integración con Mongo real al final (auto-skip sin URI).
"""
from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from argos.agents.compliance_officer import (
    DEFAULT_ENVELOPES,
    ComplianceDecision,
    ComplianceOfficer,
    Plano,
)
from argos.agents.compliance_officer.envelope import (
    EnvelopeDefinition,
    envelope_def_to_doc,
)
from argos.agents.compliance_officer.service import (
    ComplianceOfficerError,
    seed_default_envelopes,
)
from argos.db import collections as col
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

# ─── Helpers ─────────────────────────────────────────────────────────────


def _real_mongo_uri() -> str:
    from dotenv import dotenv_values

    env_file = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    if os.path.exists(env_file):
        vals = dotenv_values(env_file)
        if vals.get("MONGODB_URI"):
            return vals["MONGODB_URI"]
    return os.environ.get("ARGOS_INTEGRATION_MONGODB_URI", "")


REAL_URI = _real_mongo_uri()
pytestmark = pytest.mark.skipif(
    not REAL_URI,
    reason="MONGODB_URI no disponible · integration tests saltados",
)


@pytest_asyncio.fixture
async def mongo_db() -> AsyncIterator[AsyncIOMotorDatabase]:
    client = AsyncIOMotorClient(REAL_URI, serverSelectionTimeoutMS=5000)
    db = client[os.environ.get("MONGODB_TEST_DATABASE", "argos_test")]
    await db[col.COMPLIANCE_ENVELOPE].drop()
    try:
        yield db
    finally:
        await db[col.COMPLIANCE_ENVELOPE].drop()
        client.close()


# ─── Validación de inputs · sync · NO requieren Mongo ───────────────────


def test_validate_action_requires_workspace_id() -> None:
    import asyncio

    async def _attempt() -> None:
        officer = ComplianceOfficer(db=None)  # type: ignore[arg-type]
        await officer.validate_action(
            workspace_id="",
            action_type="pricing.adjust_meli",
            params={"delta_pct": 1.0},
        )

    with pytest.raises(ComplianceOfficerError, match="workspace_id"):
        asyncio.run(_attempt())


def test_validate_action_requires_dot_notation() -> None:
    import asyncio

    async def _attempt() -> None:
        officer = ComplianceOfficer(db=None)  # type: ignore[arg-type]
        await officer.validate_action(
            workspace_id="RODDOS",
            action_type="adjustprice",  # sin punto
        )

    with pytest.raises(ComplianceOfficerError, match="dot.notation"):
        asyncio.run(_attempt())


def test_upsert_envelope_validates_plano() -> None:
    import asyncio

    async def _attempt() -> None:
        officer = ComplianceOfficer(db=None)  # type: ignore[arg-type]
        await officer.upsert_envelope(
            workspace_id="RODDOS",
            action_type="pricing.adjust_meli",
            plano=99,  # inválido
            plano_if_outside=2,
            params_schema={},
            constraints={},
            description="x",
            approved_by="ceo@roddos.com",
        )

    with pytest.raises(ComplianceOfficerError, match="plano debe ser"):
        asyncio.run(_attempt())


# ─── DEFAULT_ENVELOPES · sanity checks sync ─────────────────────────────


def test_default_envelopes_cover_critical_action_types() -> None:
    action_types = {e.action_type for e in DEFAULT_ENVELOPES}
    expected = {
        "pricing.adjust_meli",
        "pricing.adjust_sismo",
        "bidding.adjust_meta",
        "bidding.adjust_google",
        "ad_set.pause",
        "creative.suggest",
        "campaign.budget_change",
        "compliance.envelope.update",
    }
    assert expected.issubset(action_types)


def test_default_envelopes_have_unique_action_types() -> None:
    action_types = [e.action_type for e in DEFAULT_ENVELOPES]
    assert len(action_types) == len(set(action_types)), "duplicates en defaults"


def test_default_pricing_envelope_is_5_percent() -> None:
    pricing = next(e for e in DEFAULT_ENVELOPES if e.action_type == "pricing.adjust_meli")
    assert pricing.plano == 1
    assert pricing.plano_if_outside == 2
    assert pricing.constraints["max_abs_delta_pct"] == 5.0


def test_default_compliance_envelope_update_is_plano_3() -> None:
    update = next(
        e for e in DEFAULT_ENVELOPES if e.action_type == "compliance.envelope.update"
    )
    assert update.plano == 3
    assert update.plano_if_outside == 3


def test_envelope_def_to_doc_shape() -> None:
    from datetime import UTC, datetime

    envelope_def = EnvelopeDefinition(
        action_type="pricing.adjust_meli",
        plano=1,
        plano_if_outside=2,
        params_schema={"delta_pct": "float"},
        constraints={"max_abs_delta_pct": 5.0},
        description="x",
    )
    now = datetime.now(tz=UTC)
    doc = envelope_def_to_doc(
        envelope_def,
        workspace_id="RODDOS",
        approved_by="ceo@roddos.com",
        now=now,
    )
    assert doc["workspace_id"] == "RODDOS"
    assert doc["action_type"] == "pricing.adjust_meli"
    assert doc["plano"] == 1
    assert doc["active"] is True
    assert doc["approved_by"] == "ceo@roddos.com"
    assert doc["created_at"] == now


# ─── Plano enum ──────────────────────────────────────────────────────────


def test_plano_enum_values() -> None:
    assert int(Plano.PLANO_1_AUTO) == 1
    assert int(Plano.PLANO_2_CGO) == 2
    assert int(Plano.PLANO_3_CEO) == 3


# ─── Integration · requieren Mongo real ─────────────────────────────────


async def test_validate_action_no_envelope_returns_plano_3(mongo_db: AsyncIOMotorDatabase) -> None:
    """Fail-safe: si no hay envelope para el action_type, escala a CEO."""
    officer = ComplianceOfficer(mongo_db)
    decision = await officer.validate_action(
        workspace_id="RODDOS",
        action_type="pricing.adjust_meli",
        params={"delta_pct": 2.0},
    )
    assert isinstance(decision, ComplianceDecision)
    assert decision.allowed is False
    assert decision.plano_required == 3
    assert decision.envelope_present is False
    assert "No hay envelope" in decision.reason


async def test_validate_action_within_envelope_plano_1(mongo_db: AsyncIOMotorDatabase) -> None:
    """Pricing dentro de ±5% → Plano 1 auto-execute."""
    await seed_default_envelopes(mongo_db, workspace_id="RODDOS", approved_by="seed:test")
    officer = ComplianceOfficer(mongo_db)
    decision = await officer.validate_action(
        workspace_id="RODDOS",
        action_type="pricing.adjust_meli",
        params={"delta_pct": 3.5},  # |3.5| ≤ 5 → dentro
    )
    assert decision.allowed is True
    assert decision.plano_required == 1
    assert decision.envelope_present is True


async def test_validate_action_outside_envelope_escalates_plano_2(mongo_db: AsyncIOMotorDatabase) -> None:
    """Pricing fuera de ±5% → escala a Plano 2 (CGO)."""
    await seed_default_envelopes(mongo_db, workspace_id="RODDOS", approved_by="seed:test")
    officer = ComplianceOfficer(mongo_db)
    decision = await officer.validate_action(
        workspace_id="RODDOS",
        action_type="pricing.adjust_meli",
        params={"delta_pct": 8.0},  # 8 > 5 → fuera
    )
    assert decision.allowed is False  # no auto-execute
    assert decision.plano_required == 2
    assert decision.envelope_present is True
    assert "envelope max" in decision.reason


async def test_validate_action_negative_delta_within_envelope(mongo_db: AsyncIOMotorDatabase) -> None:
    """delta_pct=-4.0 (bajada de precio 4%) está dentro de ±5%."""
    await seed_default_envelopes(mongo_db, workspace_id="RODDOS", approved_by="seed:test")
    officer = ComplianceOfficer(mongo_db)
    decision = await officer.validate_action(
        workspace_id="RODDOS",
        action_type="pricing.adjust_meli",
        params={"delta_pct": -4.0},
    )
    assert decision.allowed is True
    assert decision.plano_required == 1


async def test_validate_action_ad_set_pause_within(mongo_db: AsyncIOMotorDatabase) -> None:
    """ad_set.pause con CTR<0.5% durante ≥4h → Plano 1."""
    await seed_default_envelopes(mongo_db, workspace_id="RODDOS", approved_by="seed:test")
    officer = ComplianceOfficer(mongo_db)
    decision = await officer.validate_action(
        workspace_id="RODDOS",
        action_type="ad_set.pause",
        params={"ctr_pct": 0.3, "hours_below": 6},
    )
    assert decision.allowed is True
    assert decision.plano_required == 1


async def test_validate_action_ad_set_pause_insufficient_hours_escalates(mongo_db: AsyncIOMotorDatabase) -> None:
    """CTR bajo pero pocas horas → escala."""
    await seed_default_envelopes(mongo_db, workspace_id="RODDOS", approved_by="seed:test")
    officer = ComplianceOfficer(mongo_db)
    decision = await officer.validate_action(
        workspace_id="RODDOS",
        action_type="ad_set.pause",
        params={"ctr_pct": 0.2, "hours_below": 1},  # solo 1h, requiere 4
    )
    assert decision.allowed is False
    assert decision.plano_required == 2


async def test_validate_action_creative_suggest_always_plano_2(mongo_db: AsyncIOMotorDatabase) -> None:
    """creative.suggest siempre requiere CGO · nunca auto-execute."""
    await seed_default_envelopes(mongo_db, workspace_id="RODDOS", approved_by="seed:test")
    officer = ComplianceOfficer(mongo_db)
    decision = await officer.validate_action(
        workspace_id="RODDOS",
        action_type="creative.suggest",
        params={"creative_count": 3},
    )
    assert decision.allowed is False  # no auto
    assert decision.plano_required == 2


async def test_validate_action_compliance_envelope_update_always_plano_3(mongo_db: AsyncIOMotorDatabase) -> None:
    """compliance.envelope.update siempre requiere CEO."""
    await seed_default_envelopes(mongo_db, workspace_id="RODDOS", approved_by="seed:test")
    officer = ComplianceOfficer(mongo_db)
    decision = await officer.validate_action(
        workspace_id="RODDOS",
        action_type="compliance.envelope.update",
        params={},
    )
    assert decision.allowed is False
    assert decision.plano_required == 3


async def test_validate_action_invalid_delta_param(mongo_db: AsyncIOMotorDatabase) -> None:
    """delta_pct no numérico → escala fail-safe."""
    await seed_default_envelopes(mongo_db, workspace_id="RODDOS", approved_by="seed:test")
    officer = ComplianceOfficer(mongo_db)
    decision = await officer.validate_action(
        workspace_id="RODDOS",
        action_type="pricing.adjust_meli",
        params={"delta_pct": "no-numeric"},
    )
    assert decision.allowed is False
    assert decision.plano_required == 2
    assert "inválido" in decision.reason


async def test_seed_default_envelopes_is_idempotent(mongo_db: AsyncIOMotorDatabase) -> None:
    """Re-seeding no duplica."""
    inserted_first = await seed_default_envelopes(
        mongo_db, workspace_id="RODDOS", approved_by="seed:1",
    )
    assert inserted_first == len(DEFAULT_ENVELOPES)

    inserted_second = await seed_default_envelopes(
        mongo_db, workspace_id="RODDOS", approved_by="seed:2",
    )
    assert inserted_second == 0  # ya existían

    # Verificar que solo hay un envelope active por action_type
    docs = await mongo_db[col.COMPLIANCE_ENVELOPE].find(
        {"workspace_id": "RODDOS", "active": True},
    ).to_list(length=100)
    assert len(docs) == len(DEFAULT_ENVELOPES)


async def test_upsert_envelope_creates_new(mongo_db: AsyncIOMotorDatabase) -> None:
    officer = ComplianceOfficer(mongo_db)
    doc = await officer.upsert_envelope(
        workspace_id="RODDOS",
        action_type="pricing.adjust_meli",
        plano=1,
        plano_if_outside=2,
        params_schema={"delta_pct": "float"},
        constraints={"max_abs_delta_pct": 7.0},
        description="custom",
        approved_by="ceo@roddos.com",
    )
    assert doc["constraints"]["max_abs_delta_pct"] == 7.0
    assert doc["approved_by"] == "ceo@roddos.com"
    assert doc["active"] is True


async def test_upsert_envelope_updates_existing(mongo_db: AsyncIOMotorDatabase) -> None:
    officer = ComplianceOfficer(mongo_db)
    await officer.upsert_envelope(
        workspace_id="RODDOS",
        action_type="pricing.adjust_meli",
        plano=1,
        plano_if_outside=2,
        params_schema={},
        constraints={"max_abs_delta_pct": 5.0},
        description="v1",
        approved_by="ceo@roddos.com",
    )
    doc = await officer.upsert_envelope(
        workspace_id="RODDOS",
        action_type="pricing.adjust_meli",
        plano=1,
        plano_if_outside=2,
        params_schema={},
        constraints={"max_abs_delta_pct": 8.0},  # cambia threshold
        description="v2",
        approved_by="ceo@roddos.com",
    )
    assert doc["constraints"]["max_abs_delta_pct"] == 8.0
    assert doc["description"] == "v2"

    # Asegurar que solo hay 1 active (no se duplicó)
    count = await mongo_db[col.COMPLIANCE_ENVELOPE].count_documents(
        {"workspace_id": "RODDOS", "action_type": "pricing.adjust_meli", "active": True},
    )
    assert count == 1


async def test_get_envelope_returns_none_if_missing(mongo_db: AsyncIOMotorDatabase) -> None:
    officer = ComplianceOfficer(mongo_db)
    doc = await officer.get_envelope(
        workspace_id="RODDOS", action_type="pricing.adjust_meli",
    )
    assert doc is None


async def test_list_envelopes_returns_only_active_for_workspace(mongo_db: AsyncIOMotorDatabase) -> None:
    """Multi-tenancy: listar de RODDOS no debe devolver TENANT_X."""
    await seed_default_envelopes(mongo_db, workspace_id="RODDOS", approved_by="seed:roddos")
    await seed_default_envelopes(mongo_db, workspace_id="TENANT_X", approved_by="seed:tenant_x")

    officer = ComplianceOfficer(mongo_db)
    docs = await officer.list_envelopes(workspace_id="RODDOS")
    assert all(d["workspace_id"] == "RODDOS" for d in docs)
    assert len(docs) == len(DEFAULT_ENVELOPES)
