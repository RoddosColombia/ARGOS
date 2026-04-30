"""Tests de brief delivery · ROG-G1 entrega simultánea CEO + CGO (Build 2.5.5).

Cubre:
- Validación inputs (workspace_id obligatorio, brief debe ser dict)
- list_leadership_emails: filtra por role ceo+cgo del workspace
- send_brief_to_leadership: skip silencioso si db None
- send_brief_to_leadership: warning si no hay leadership users
- send_brief_to_leadership: entrega simultánea a CEO+CGO con misma data
- Channels: DASHBOARD logs, WHATSAPP/EMAIL stubs
- audit_log emite un evento por recipient
- ROG-A3 multi-tenancy: brief de RODDOS no llega a TENANT_X
"""
from __future__ import annotations

import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from argos.db import collections as col
from argos.services.brief_delivery import (
    BriefChannel,
    BriefDeliveryError,
    BriefDeliveryResult,
    list_leadership_emails,
    send_brief_to_leadership,
)
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
    await db[col.USERS].drop()
    await db[col.AUDIT_LOG].drop()
    try:
        yield db
    finally:
        await db[col.USERS].drop()
        await db[col.AUDIT_LOG].drop()
        client.close()


async def _seed_users(db: AsyncIOMotorDatabase, *, workspace_id: str = "RODDOS") -> None:
    """Inserta CEO + CGO del workspace + un user de otro workspace para validar isolation."""
    now = datetime.now(tz=UTC)
    await db[col.USERS].insert_many([
        {
            "workspace_id": workspace_id,
            "email": "ceo@roddos.com",
            "password_hash": "fake-hash",
            "roles": ["ceo"],
            "created_at": now,
        },
        {
            "workspace_id": workspace_id,
            "email": "ivan@roddos.com",
            "password_hash": "fake-hash",
            "roles": ["cgo"],
            "created_at": now,
        },
        {
            "workspace_id": workspace_id,
            "email": "analyst@roddos.com",
            "password_hash": "fake-hash",
            "roles": ["analista"],   # no debe aparecer en leadership
            "created_at": now,
        },
        {
            "workspace_id": "TENANT_X",
            "email": "ceo@tenant-x.com",
            "password_hash": "fake-hash",
            "roles": ["ceo"],         # mismo role pero otro workspace
            "created_at": now,
        },
    ])


# ─── Validación inputs · sync ────────────────────────────────────────────


def test_send_brief_requires_workspace_id() -> None:
    import asyncio

    async def _attempt() -> None:
        await send_brief_to_leadership(
            db=None,
            workspace_id="",
            brief={"x": 1},
        )

    with pytest.raises(BriefDeliveryError, match="workspace_id"):
        asyncio.run(_attempt())


def test_send_brief_requires_dict() -> None:
    import asyncio

    async def _attempt() -> None:
        await send_brief_to_leadership(
            db=None,
            workspace_id="RODDOS",
            brief="not-a-dict",  # type: ignore[arg-type]
        )

    with pytest.raises(BriefDeliveryError, match="dict"):
        asyncio.run(_attempt())


# ─── Skip silencioso ────────────────────────────────────────────────────


async def test_send_brief_skips_when_db_is_none() -> None:
    result = await send_brief_to_leadership(
        db=None,
        workspace_id="RODDOS",
        brief={"estado_mercado": "test"},
    )
    assert isinstance(result, BriefDeliveryResult)
    assert result.delivered_to == ()
    assert result.skipped_reason == "no_db"


# ─── Integration · requieren Mongo real ─────────────────────────────────


async def test_list_leadership_returns_ceo_and_cgo_only(mongo_db: AsyncIOMotorDatabase) -> None:
    await _seed_users(mongo_db)
    recipients = await list_leadership_emails(mongo_db, workspace_id="RODDOS")
    emails = {r.email for r in recipients}
    roles = {r.role for r in recipients}
    assert emails == {"ceo@roddos.com", "ivan@roddos.com"}
    assert roles == {"ceo", "cgo"}
    # Analista NO debe aparecer
    assert "analyst@roddos.com" not in emails


async def test_list_leadership_isolates_by_workspace(mongo_db: AsyncIOMotorDatabase) -> None:
    """ROG-A3 · TENANT_X tiene su propio CEO, no debe mezclarse con RODDOS."""
    await _seed_users(mongo_db)
    rec_roddos = await list_leadership_emails(mongo_db, workspace_id="RODDOS")
    assert all(r.email != "ceo@tenant-x.com" for r in rec_roddos)

    rec_tenant = await list_leadership_emails(mongo_db, workspace_id="TENANT_X")
    assert {r.email for r in rec_tenant} == {"ceo@tenant-x.com"}


async def test_list_leadership_empty_when_no_users(mongo_db: AsyncIOMotorDatabase) -> None:
    """Sin users no rompe · devuelve lista vacía."""
    recipients = await list_leadership_emails(mongo_db, workspace_id="RODDOS")
    assert recipients == []


async def test_send_brief_delivers_to_both_simultaneously(mongo_db: AsyncIOMotorDatabase) -> None:
    """ROG-G1 · CEO y CGO reciben el mismo brief simultáneamente."""
    await _seed_users(mongo_db)

    brief = {
        "fecha": "2026-04-30",
        "estado_mercado": "test estado",
        "acciones_del_dia": [{"accion": "test", "prioridad": "Alta"}],
    }
    result = await send_brief_to_leadership(
        mongo_db,
        workspace_id="RODDOS",
        brief=brief,
        channels=(BriefChannel.DASHBOARD.value,),
        brief_id="brief_test_001",
    )

    assert result.skipped_reason is None
    assert len(result.delivered_to) == 2
    delivered_emails = {r.email for r in result.delivered_to}
    delivered_roles = {r.role for r in result.delivered_to}
    assert delivered_emails == {"ceo@roddos.com", "ivan@roddos.com"}
    assert delivered_roles == {"ceo", "cgo"}
    assert BriefChannel.DASHBOARD.value in result.channels_used


async def test_send_brief_audits_per_recipient(mongo_db: AsyncIOMotorDatabase) -> None:
    """ROG-G3 · audit_log debe tener 1 evento por recipient con su role."""
    await _seed_users(mongo_db)
    await send_brief_to_leadership(
        mongo_db,
        workspace_id="RODDOS",
        brief={"estado_mercado": "audit test"},
        channels=(BriefChannel.DASHBOARD.value,),
        brief_id="brief_audit_test",
    )

    audit_docs = await mongo_db[col.AUDIT_LOG].find(
        {"workspace_id": "RODDOS", "action": {"$regex": "^brief.delivered"}},
    ).to_list(length=10)
    assert len(audit_docs) == 2
    actions = {d["action"] for d in audit_docs}
    assert actions == {"brief.delivered.ceo", "brief.delivered.cgo"}
    # Ambos audit deben referenciar el mismo brief_id
    brief_ids = {d.get("resource_id") for d in audit_docs}
    assert brief_ids == {"brief_audit_test"}


async def test_send_brief_no_recipients_is_warning(mongo_db: AsyncIOMotorDatabase) -> None:
    """Si no hay leadership users, no rompe · skipped_reason='no_leadership_users'."""
    # NO seedeamos users
    result = await send_brief_to_leadership(
        mongo_db,
        workspace_id="RODDOS",
        brief={"estado_mercado": "x"},
    )
    assert result.delivered_to == ()
    assert result.skipped_reason == "no_leadership_users"


async def test_send_brief_supports_multiple_channels(mongo_db: AsyncIOMotorDatabase) -> None:
    """channels=(DASHBOARD, WHATSAPP) deja constancia en channels_used."""
    await _seed_users(mongo_db)
    result = await send_brief_to_leadership(
        mongo_db,
        workspace_id="RODDOS",
        brief={"estado_mercado": "multi"},
        channels=(BriefChannel.DASHBOARD.value, BriefChannel.WHATSAPP.value),
    )
    assert BriefChannel.DASHBOARD.value in result.channels_used
    assert BriefChannel.WHATSAPP.value in result.channels_used
