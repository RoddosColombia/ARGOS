"""Tests de ROG-A6 metadata mutation policy (Build 2.5.9).

Valida que solo los campos permitidos en ALLOWED_METADATA_MUTATIONS se pueden
mutar en argos_events. Cualquier campo fuera de la lista lanza
MetadataMutationError.

Refs: phase_2.5/build_2.5.9 · ROG-A6 · docs/canonicas/eventos.md
"""
from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest
from argos.db.events import (
    ALLOWED_METADATA_MUTATIONS,
    MetadataMutationError,
    validate_metadata_mutation,
)

# ---------------------------------------------------------------------------
# validate_metadata_mutation · comportamiento
# ---------------------------------------------------------------------------

def test_allowed_fields_pass() -> None:
    """Todos los campos de ALLOWED_METADATA_MUTATIONS pasan sin excepción."""
    fields = {field: True for field in ALLOWED_METADATA_MUTATIONS}
    validate_metadata_mutation(fields)


def test_single_allowed_field_passes() -> None:
    validate_metadata_mutation({"metadata.whatsapp_notified": True})


def test_single_illegal_field_raises() -> None:
    with pytest.raises(MetadataMutationError, match="ROG-A6 violation"):
        validate_metadata_mutation({"metadata.some_random_flag": True})


def test_payload_field_mutation_raises() -> None:
    """Mutar payload (no metadata) es violación absoluta de ROG-A6."""
    with pytest.raises(MetadataMutationError):
        validate_metadata_mutation({"payload.precio_actual": 50000})


def test_mixed_allowed_and_illegal_raises() -> None:
    """Una mezcla de campos permitidos e ilegales sigue siendo violación."""
    with pytest.raises(MetadataMutationError, match="metadata.hacked"):
        validate_metadata_mutation({
            "metadata.whatsapp_notified": True,
            "metadata.hacked": True,
        })


def test_empty_dict_passes() -> None:
    """Un $set vacío no viola nada."""
    validate_metadata_mutation({})


def test_error_message_lists_illegal_fields() -> None:
    with pytest.raises(MetadataMutationError) as exc_info:
        validate_metadata_mutation({
            "metadata.foo": 1,
            "metadata.bar": 2,
        })
    msg = str(exc_info.value)
    assert "metadata.bar" in msg
    assert "metadata.foo" in msg


def test_error_message_lists_allowed_fields() -> None:
    with pytest.raises(MetadataMutationError) as exc_info:
        validate_metadata_mutation({"metadata.illegal": True})
    msg = str(exc_info.value)
    assert "metadata.whatsapp_notified" in msg


# ---------------------------------------------------------------------------
# ALLOWED_METADATA_MUTATIONS · completitud
# ---------------------------------------------------------------------------

def test_allowed_set_contains_whatsapp_notified() -> None:
    assert "metadata.whatsapp_notified" in ALLOWED_METADATA_MUTATIONS


def test_allowed_set_contains_whatsapp_notified_at() -> None:
    assert "metadata.whatsapp_notified_at" in ALLOWED_METADATA_MUTATIONS


def test_allowed_set_contains_email_notified() -> None:
    assert "metadata.email_notified" in ALLOWED_METADATA_MUTATIONS


def test_allowed_set_contains_email_notified_at() -> None:
    assert "metadata.email_notified_at" in ALLOWED_METADATA_MUTATIONS


def test_allowed_set_contains_escalated() -> None:
    assert "metadata.escalated" in ALLOWED_METADATA_MUTATIONS


def test_allowed_set_contains_escalated_at() -> None:
    assert "metadata.escalated_at" in ALLOWED_METADATA_MUTATIONS


def test_allowed_set_is_frozen() -> None:
    """ALLOWED_METADATA_MUTATIONS es immutable · nadie puede añadir campos en runtime."""
    assert isinstance(ALLOWED_METADATA_MUTATIONS, frozenset)


# ---------------------------------------------------------------------------
# Static analysis guard · asegurar que el código real llama validate antes de mutar
# ---------------------------------------------------------------------------

def test_notifications_service_calls_validate_before_update() -> None:
    """notifications/service.py debe llamar validate_metadata_mutation antes de
    hacer update_one sobre argos_events.

    Este test parsea el AST del archivo para verificar que la llamada al guard
    existe. Si alguien remueve la validación, el test falla.
    """
    service_path = (
        Path(__file__).resolve().parents[2]
        / "src" / "backend" / "argos" / "agents" / "notifications" / "service.py"
    )
    source = service_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    has_validate_call = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == "validate_metadata_mutation":
                has_validate_call = True
                break
            if isinstance(func, ast.Attribute) and func.attr == "validate_metadata_mutation":
                has_validate_call = True
                break

    assert has_validate_call, (
        "notifications/service.py no llama validate_metadata_mutation() — "
        "ROG-A6 guard removido o no integrado"
    )


def test_notifications_service_imports_validate() -> None:
    """notifications/service.py importa validate_metadata_mutation de events."""
    from argos.agents.notifications import service as svc
    source = inspect.getsource(svc)
    assert "validate_metadata_mutation" in source
