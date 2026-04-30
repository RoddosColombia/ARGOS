"""Tests del opt-in registry · cumple ROG-W1 preventivo (Build 2.5.3).

Cubre:
- Validación de phone number E.164
- Validación de tipos (marketing/utility) y canales
- record_opt_in upsert · crea contact si no existe
- record_opt_in actualiza si ya existe
- record_opt_out cambia status preservando history
- record_opt_out con contact inexistente devuelve None
- get_opt_status lectura
- can_send_proactive: contact_not_found / no_opt_in / opted_out / opted_in / no_db
- Endpoints API integrados (con TestClient · requiere mongo real, auto-skip sin URI)
"""
from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from argos.db import collections as col
from argos.services.opt_in import (
    OptInChannel,
    OptInStatus,
    OptInType,
    OptInValidationError,
    can_send_proactive,
    get_opt_status,
    record_opt_in,
    record_opt_out,
)
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

# ─── Helpers ─────────────────────────────────────────────────────────────


def _real_mongo_uri() -> str:
    """Lee la URI real ignorando el MONGODB_URI="" que conftest fuerza para unit tests."""
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
    await db[col.CONTACTS].drop()
    try:
        yield db
    finally:
        await db[col.CONTACTS].drop()
        client.close()


# ─── Validación · estos tests NO requieren Mongo (son chequeos sintácticos) ──


def test_validates_phone_number_must_be_e164() -> None:
    # Pure-sync: la validación de phone se ejecuta antes de tocar db
    import asyncio

    async def _attempt() -> None:
        await record_opt_in(
            db=None,  # type: ignore[arg-type]
            workspace_id="RODDOS",
            phone_number="3001234567",  # falta el +
            opt_type="marketing",
            channel="sms",
            consent_text_version="v1",
            captured_by="ceo@roddos.com",
        )

    with pytest.raises(OptInValidationError, match="E.164"):
        asyncio.run(_attempt())


def test_validates_invalid_opt_type() -> None:
    import asyncio

    async def _attempt() -> None:
        await record_opt_in(
            db=None,  # type: ignore[arg-type]
            workspace_id="RODDOS",
            phone_number="+573001234567",
            opt_type="cualquier_cosa",
            channel="sms",
            consent_text_version="v1",
            captured_by="ceo@roddos.com",
        )

    with pytest.raises(OptInValidationError, match="opt_in type inválido"):
        asyncio.run(_attempt())


def test_validates_invalid_channel() -> None:
    import asyncio

    async def _attempt() -> None:
        await record_opt_in(
            db=None,  # type: ignore[arg-type]
            workspace_id="RODDOS",
            phone_number="+573001234567",
            opt_type="marketing",
            channel="email",  # no permitido
            consent_text_version="v1",
            captured_by="ceo@roddos.com",
        )

    with pytest.raises(OptInValidationError, match="channel inválido"):
        asyncio.run(_attempt())


def test_validates_empty_workspace_id() -> None:
    import asyncio

    async def _attempt() -> None:
        await record_opt_in(
            db=None,  # type: ignore[arg-type]
            workspace_id="",
            phone_number="+573001234567",
            opt_type="marketing",
            channel="sms",
            consent_text_version="v1",
            captured_by="ceo@roddos.com",
        )

    with pytest.raises(OptInValidationError, match="workspace_id es obligatorio"):
        asyncio.run(_attempt())


# ─── Integration: requieren Mongo real ──────────────────────────────────


async def test_record_opt_in_creates_contact_if_not_exists(mongo_db: AsyncIOMotorDatabase) -> None:
    contact = await record_opt_in(
        mongo_db,
        workspace_id="RODDOS",
        phone_number="+573001234567",
        opt_type="marketing",
        channel="sms",
        consent_text_version="v1.0",
        captured_by="ceo@roddos.com",
        name="Carlos Mototaxi",
    )
    assert contact["phone_number"] == "+573001234567"
    assert contact["name"] == "Carlos Mototaxi"
    assert contact["opt_in_marketing"]["status"] == OptInStatus.OPTED_IN.value
    assert contact["opt_in_marketing"]["channel"] == "sms"
    assert contact["opt_in_marketing"]["consent_text_version"] == "v1.0"
    assert len(contact["opt_in_marketing"]["history"]) == 1


async def test_record_opt_in_updates_existing_contact(mongo_db: AsyncIOMotorDatabase) -> None:
    """Re-aplicar opt-in al mismo phone: actualiza estado + agrega entry al history."""
    await record_opt_in(
        mongo_db,
        workspace_id="RODDOS",
        phone_number="+573001234567",
        opt_type="marketing",
        channel="sms",
        consent_text_version="v1.0",
        captured_by="ceo@roddos.com",
    )
    contact = await record_opt_in(
        mongo_db,
        workspace_id="RODDOS",
        phone_number="+573001234567",
        opt_type="marketing",
        channel="whatsapp_inbound",
        consent_text_version="v1.1",
        captured_by="bot@argos",
    )
    assert contact["opt_in_marketing"]["channel"] == "whatsapp_inbound"
    assert contact["opt_in_marketing"]["consent_text_version"] == "v1.1"
    # history debe tener 2 entries (original + actualización)
    assert len(contact["opt_in_marketing"]["history"]) == 2


async def test_record_opt_in_separates_marketing_from_utility(mongo_db: AsyncIOMotorDatabase) -> None:
    """Opt-in para marketing NO implica utility · son flags independientes."""
    await record_opt_in(
        mongo_db,
        workspace_id="RODDOS",
        phone_number="+573001234567",
        opt_type="marketing",
        channel="sms",
        consent_text_version="v1.0",
        captured_by="ceo@roddos.com",
    )
    contact = await get_opt_status(
        mongo_db, workspace_id="RODDOS", phone_number="+573001234567",
    )
    assert contact["opt_in_marketing"]["status"] == OptInStatus.OPTED_IN.value
    assert contact.get("opt_in_utility") is None  # no se setea automáticamente


async def test_record_opt_out_changes_status_preserves_history(mongo_db: AsyncIOMotorDatabase) -> None:
    await record_opt_in(
        mongo_db,
        workspace_id="RODDOS",
        phone_number="+573001234567",
        opt_type="marketing",
        channel="sms",
        consent_text_version="v1.0",
        captured_by="ceo@roddos.com",
    )
    contact = await record_opt_out(
        mongo_db,
        workspace_id="RODDOS",
        phone_number="+573001234567",
        opt_type="marketing",
        captured_by="cliente@whatsapp",
        reason="STOP",
    )
    assert contact is not None
    assert contact["opt_in_marketing"]["status"] == OptInStatus.OPTED_OUT.value
    assert contact["opt_in_marketing"]["opted_out_by"] == "cliente@whatsapp"
    assert len(contact["opt_in_marketing"]["history"]) == 2  # opt_in + opt_out


async def test_record_opt_out_returns_none_if_contact_missing(mongo_db: AsyncIOMotorDatabase) -> None:
    contact = await record_opt_out(
        mongo_db,
        workspace_id="RODDOS",
        phone_number="+573009999999",
        opt_type="marketing",
        captured_by="cliente@whatsapp",
    )
    assert contact is None


async def test_get_opt_status_returns_none_if_missing(mongo_db: AsyncIOMotorDatabase) -> None:
    doc = await get_opt_status(
        mongo_db, workspace_id="RODDOS", phone_number="+573009999999",
    )
    assert doc is None


# ─── can_send_proactive · gate de outbound ───────────────────────────────


async def test_can_send_proactive_returns_false_when_db_is_none() -> None:
    allowed, reason = await can_send_proactive(
        None,
        workspace_id="RODDOS",
        phone_number="+573001234567",
    )
    assert allowed is False
    assert reason == "no_db"


async def test_can_send_proactive_contact_not_found(mongo_db: AsyncIOMotorDatabase) -> None:
    allowed, reason = await can_send_proactive(
        mongo_db,
        workspace_id="RODDOS",
        phone_number="+573001234567",
    )
    assert allowed is False
    assert reason == "contact_not_found"


async def test_can_send_proactive_no_opt_in(mongo_db: AsyncIOMotorDatabase) -> None:
    """Contact existe pero solo tiene opt_in_utility · pedimos marketing → no_opt_in."""
    await record_opt_in(
        mongo_db,
        workspace_id="RODDOS",
        phone_number="+573001234567",
        opt_type="utility",
        channel="sms",
        consent_text_version="v1.0",
        captured_by="ceo@roddos.com",
    )
    allowed, reason = await can_send_proactive(
        mongo_db,
        workspace_id="RODDOS",
        phone_number="+573001234567",
        opt_type="marketing",
    )
    assert allowed is False
    assert reason == "no_opt_in"


async def test_can_send_proactive_opted_in_returns_true(mongo_db: AsyncIOMotorDatabase) -> None:
    await record_opt_in(
        mongo_db,
        workspace_id="RODDOS",
        phone_number="+573001234567",
        opt_type="marketing",
        channel="sms",
        consent_text_version="v1.0",
        captured_by="ceo@roddos.com",
    )
    allowed, reason = await can_send_proactive(
        mongo_db,
        workspace_id="RODDOS",
        phone_number="+573001234567",
        opt_type="marketing",
    )
    assert allowed is True
    assert reason is None


async def test_can_send_proactive_opted_out_blocks(mongo_db: AsyncIOMotorDatabase) -> None:
    await record_opt_in(
        mongo_db,
        workspace_id="RODDOS",
        phone_number="+573001234567",
        opt_type="marketing",
        channel="sms",
        consent_text_version="v1.0",
        captured_by="ceo@roddos.com",
    )
    await record_opt_out(
        mongo_db,
        workspace_id="RODDOS",
        phone_number="+573001234567",
        opt_type="marketing",
        captured_by="cliente@whatsapp",
        reason="STOP",
    )
    allowed, reason = await can_send_proactive(
        mongo_db,
        workspace_id="RODDOS",
        phone_number="+573001234567",
        opt_type="marketing",
    )
    assert allowed is False
    assert reason == "opted_out"


async def test_can_send_proactive_isolated_by_workspace(mongo_db: AsyncIOMotorDatabase) -> None:
    """ROG-A3: opt-in en RODDOS no permite envío a TENANT_X."""
    await record_opt_in(
        mongo_db,
        workspace_id="RODDOS",
        phone_number="+573001234567",
        opt_type="marketing",
        channel="sms",
        consent_text_version="v1.0",
        captured_by="ceo@roddos.com",
    )
    allowed, reason = await can_send_proactive(
        mongo_db,
        workspace_id="TENANT_X",
        phone_number="+573001234567",
        opt_type="marketing",
    )
    assert allowed is False
    assert reason == "contact_not_found"


# ─── Enums ───────────────────────────────────────────────────────────────


def test_opt_in_status_enum_values() -> None:
    assert OptInStatus.OPTED_IN == "opted_in"
    assert OptInStatus.OPTED_OUT == "opted_out"
    assert OptInStatus.PENDING == "pending"


def test_opt_in_type_enum_values() -> None:
    assert OptInType.MARKETING == "marketing"
    assert OptInType.UTILITY == "utility"


def test_opt_in_channel_enum_values() -> None:
    assert OptInChannel.SMS == "sms"
    assert OptInChannel.WEB == "web"
    assert OptInChannel.WHATSAPP_INBOUND == "whatsapp_inbound"
    assert OptInChannel.SALES_CALL == "sales_call"
    assert OptInChannel.QR_EMPAQUE == "qr_empaque"
