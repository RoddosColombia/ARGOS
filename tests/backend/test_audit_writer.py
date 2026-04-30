"""Tests del audit_log writer · cumple ROG-A12 (Build 2.5.2).

Cobertura de:
- Validación de campos requeridos (workspace_id, actor_type, actor_id, action, result, actor_role)
- Persistencia exitosa con todos los campos
- Skip silencioso cuando db es None
- Skip silencioso cuando insert_one falla
- Default result = success
- Metadata optional
- Enums (ActorType, ActorRole, ActionResult) válidos

Tests de integración con MongoDB real al final (auto-skip sin URI · siguiendo el
patrón de test_integration_mongo.py y test_score_engine.py).
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from argos.services.audit import (
    ActionResult,
    ActorRole,
    ActorType,
    AuditValidationError,
    audit_write,
)

# ─── Helpers ─────────────────────────────────────────────────────────────


def _make_fake_db(
    *,
    insert_should_raise: Exception | None = None,
    inserted_id: Any = "fake_id",
) -> tuple[MagicMock, AsyncMock]:
    """Construye un mock AsyncIOMotorDatabase compatible con `db[col].insert_one(doc)`.

    Devuelve (db_mock, insert_one_mock) para que el test pueda verificar el doc
    persistido o el comportamiento ante excepción.
    """
    insert_one_mock = AsyncMock()
    if insert_should_raise is not None:
        insert_one_mock.side_effect = insert_should_raise
    else:
        result_mock = MagicMock()
        result_mock.inserted_id = inserted_id
        insert_one_mock.return_value = result_mock

    collection_mock = MagicMock()
    collection_mock.insert_one = insert_one_mock

    db_mock = MagicMock()
    db_mock.__getitem__ = MagicMock(return_value=collection_mock)
    return db_mock, insert_one_mock


# ─── Validación ──────────────────────────────────────────────────────────


async def test_validates_empty_workspace_id_raises() -> None:
    db, _ = _make_fake_db()
    with pytest.raises(AuditValidationError, match="workspace_id es obligatorio"):
        await audit_write(
            db,
            workspace_id="",
            actor_type=ActorType.USER,
            actor_id="ceo@roddos.com",
            action="auth.login.success",
        )


async def test_validates_invalid_actor_type_raises() -> None:
    db, _ = _make_fake_db()
    with pytest.raises(AuditValidationError, match="actor_type inválido"):
        await audit_write(
            db,
            workspace_id="RODDOS",
            actor_type="hacker",
            actor_id="ceo@roddos.com",
            action="auth.login.success",
        )


async def test_validates_empty_actor_id_raises() -> None:
    db, _ = _make_fake_db()
    with pytest.raises(AuditValidationError, match="actor_id es obligatorio"):
        await audit_write(
            db,
            workspace_id="RODDOS",
            actor_type=ActorType.USER,
            actor_id="",
            action="auth.login.success",
        )


async def test_validates_action_must_have_dot_notation() -> None:
    db, _ = _make_fake_db()
    with pytest.raises(AuditValidationError, match="dot.notation"):
        await audit_write(
            db,
            workspace_id="RODDOS",
            actor_type=ActorType.USER,
            actor_id="ceo@roddos.com",
            action="loginsuccess",  # sin punto
        )


async def test_validates_invalid_result_raises() -> None:
    db, _ = _make_fake_db()
    with pytest.raises(AuditValidationError, match="result inválido"):
        await audit_write(
            db,
            workspace_id="RODDOS",
            actor_type=ActorType.USER,
            actor_id="ceo@roddos.com",
            action="auth.login.success",
            result="quizas",
        )


async def test_validates_invalid_actor_role_raises() -> None:
    db, _ = _make_fake_db()
    with pytest.raises(AuditValidationError, match="actor_role inválido"):
        await audit_write(
            db,
            workspace_id="RODDOS",
            actor_type=ActorType.USER,
            actor_id="ceo@roddos.com",
            action="auth.login.success",
            actor_role="dictator",
        )


# ─── Persistencia exitosa ────────────────────────────────────────────────


async def test_persists_full_doc_with_all_optional_fields() -> None:
    db, insert_mock = _make_fake_db(inserted_id="abc123")
    result = await audit_write(
        db,
        workspace_id="RODDOS",
        actor_type=ActorType.USER,
        actor_id="ceo@roddos.com",
        actor_role=ActorRole.CEO,
        action="recommendation.approved",
        resource_type="recommendation",
        resource_id="rec_xyz",
        result=ActionResult.SUCCESS,
        metadata={"source": "frontend", "priority": "Alta"},
        ip_address="192.0.2.1",
    )

    assert result is not None
    assert result["_id"] == "abc123"
    insert_mock.assert_awaited_once()
    persisted_doc = insert_mock.await_args.args[0]
    assert persisted_doc["workspace_id"] == "RODDOS"
    assert persisted_doc["actor_type"] == "user"
    assert persisted_doc["actor_id"] == "ceo@roddos.com"
    assert persisted_doc["actor_role"] == "ceo"
    assert persisted_doc["action"] == "recommendation.approved"
    assert persisted_doc["resource_type"] == "recommendation"
    assert persisted_doc["resource_id"] == "rec_xyz"
    assert persisted_doc["result"] == "success"
    assert persisted_doc["metadata"] == {"source": "frontend", "priority": "Alta"}
    assert persisted_doc["ip_address"] == "192.0.2.1"
    assert isinstance(persisted_doc["timestamp_utc"], datetime)
    assert persisted_doc["timestamp_utc"].tzinfo == UTC


async def test_persists_minimal_doc_with_defaults() -> None:
    db, insert_mock = _make_fake_db()
    result = await audit_write(
        db,
        workspace_id="RODDOS",
        actor_type=ActorType.SYSTEM,
        actor_id="argos.agents.scheduler",
        action="scheduler.tick.scout",
    )
    assert result is not None
    persisted_doc = insert_mock.await_args.args[0]
    assert persisted_doc["actor_role"] is None
    assert persisted_doc["resource_type"] is None
    assert persisted_doc["resource_id"] is None
    assert persisted_doc["result"] == "success"  # default
    assert persisted_doc["metadata"] == {}
    assert persisted_doc["ip_address"] is None


async def test_persists_failure_result_with_metadata() -> None:
    db, insert_mock = _make_fake_db()
    await audit_write(
        db,
        workspace_id="_unknown",
        actor_type=ActorType.USER,
        actor_id="someone@example.com",
        action="auth.login.failed",
        result=ActionResult.FAILURE,
        metadata={"reason": "invalid_credentials"},
        ip_address="203.0.113.42",
    )
    persisted_doc = insert_mock.await_args.args[0]
    assert persisted_doc["result"] == "failure"
    assert persisted_doc["metadata"]["reason"] == "invalid_credentials"


async def test_accepts_string_actor_type_and_role() -> None:
    """audit_write acepta strings además de enums (uso desde código que no importa los enums)."""
    db, insert_mock = _make_fake_db()
    await audit_write(
        db,
        workspace_id="RODDOS",
        actor_type="user",
        actor_id="cgo@roddos.com",
        actor_role="cgo",
        action="config.watch_query.created",
        result="success",
    )
    persisted_doc = insert_mock.await_args.args[0]
    assert persisted_doc["actor_type"] == "user"
    assert persisted_doc["actor_role"] == "cgo"
    assert persisted_doc["result"] == "success"


# ─── Skip silencioso ─────────────────────────────────────────────────────


async def test_skips_silently_when_db_is_none(caplog: pytest.LogCaptureFixture) -> None:
    """Si MongoDB no está conectado, audit_write no rompe el flujo."""
    import logging

    with caplog.at_level(logging.WARNING, logger="argos.services.audit"):
        result = await audit_write(
            None,
            workspace_id="RODDOS",
            actor_type=ActorType.USER,
            actor_id="ceo@roddos.com",
            action="auth.login.success",
        )
    assert result is None
    assert any("audit_write_skipped_no_db" in r.message for r in caplog.records)


async def test_handles_insert_exception_silently(caplog: pytest.LogCaptureFixture) -> None:
    """Si insert_one explota (red, timeout, schema), audit_write log warning y devuelve None."""
    import logging

    db, _ = _make_fake_db(insert_should_raise=RuntimeError("connection lost"))
    with caplog.at_level(logging.WARNING, logger="argos.services.audit"):
        result = await audit_write(
            db,
            workspace_id="RODDOS",
            actor_type=ActorType.USER,
            actor_id="ceo@roddos.com",
            action="auth.login.success",
        )
    assert result is None
    assert any("audit_write_failed" in r.message for r in caplog.records)


# ─── Enums ───────────────────────────────────────────────────────────────


def test_enum_actor_type_values() -> None:
    assert ActorType.USER == "user"
    assert ActorType.SYSTEM == "system"
    assert ActorType.AGENT == "agent"


def test_enum_actor_role_values() -> None:
    assert ActorRole.CEO == "ceo"
    assert ActorRole.CGO == "cgo"
    assert ActorRole.ANALISTA == "analista"
    assert ActorRole.SISTEMA == "sistema"
    assert ActorRole.CLIENTE == "cliente"


def test_enum_action_result_values() -> None:
    assert ActionResult.SUCCESS == "success"
    assert ActionResult.FAILURE == "failure"


# ─── Integration · auto-skip sin MONGODB_URI ─────────────────────────────


def _has_real_mongo() -> bool:
    """Detecta si existe configuración para correr integración real."""
    import os

    from dotenv import dotenv_values

    env_file = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    if os.path.exists(env_file):
        vals = dotenv_values(env_file)
        if vals.get("MONGODB_URI"):
            return True
    return bool(os.environ.get("ARGOS_INTEGRATION_MONGODB_URI"))


pytestmark_integration = pytest.mark.skipif(
    not _has_real_mongo(),
    reason="MONGODB_URI no disponible · integration test saltado",
)


@pytestmark_integration
async def test_integration_audit_persists_to_real_mongo() -> None:
    """End-to-end con Mongo real: audit_write → query la colección → verifica el doc."""
    import os

    from argos.db import collections as col
    from dotenv import dotenv_values
    from motor.motor_asyncio import AsyncIOMotorClient

    env_file = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    uri = ""
    if os.path.exists(env_file):
        vals = dotenv_values(env_file)
        uri = vals.get("MONGODB_URI", "") or ""
    uri = uri or os.environ.get("ARGOS_INTEGRATION_MONGODB_URI", "")

    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
    db = client["argos_test_audit"]
    await db[col.AUDIT_LOG].drop()
    try:
        result = await audit_write(
            db,
            workspace_id="RODDOS",
            actor_type=ActorType.USER,
            actor_id="ceo-test@roddos.com",
            actor_role=ActorRole.CEO,
            action="test.audit.integration",
            resource_type="test",
            resource_id="test_001",
            metadata={"test_run": True},
        )
        assert result is not None

        docs = await db[col.AUDIT_LOG].find({"workspace_id": "RODDOS"}).to_list(length=10)
        assert len(docs) == 1
        assert docs[0]["actor_id"] == "ceo-test@roddos.com"
        assert docs[0]["actor_role"] == "ceo"
        assert docs[0]["action"] == "test.audit.integration"
        assert docs[0]["metadata"]["test_run"] is True
    finally:
        await db[col.AUDIT_LOG].drop()
        client.close()
