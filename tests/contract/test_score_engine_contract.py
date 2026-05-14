"""Test de contrato vs Score Engine externo (roddos-scoring).

Lee schema canonical desde docs/canonicas/score_engine_contract.md, envía payload
de prueba al endpoint /v1/evaluate real, valida que el response cumple los campos
requeridos del schema v1. Si falla, el CI notifica antes de que un cambio breaking
del motor rompa producción.

Requiere env vars:
    SCORE_ENGINE_API_URL  — base URL del Score Engine (ej. https://roddos-scoring.onrender.com)
    SCORE_ENGINE_API_KEY  — Bearer token

Se salta automáticamente si las vars no están configuradas (útil en PR de feature).
Corre obligatoriamente en el workflow contract-tests.yml (lunes 06:00 UTC + on-demand).

Refs: phase_2.5/build_2.5.6 · ROG-S5 · docs/canonicas/score_engine_contract.md
"""
from __future__ import annotations

import os
import re

import httpx
import pytest

# ---------------------------------------------------------------------------
# Schema v1 · campos required con tipo esperado
# Sincronizado con docs/canonicas/score_engine_contract.md sección "Campos REQUIRED"
# ---------------------------------------------------------------------------
REQUIRED_FIELDS: dict[str, type | tuple[type, ...]] = {
    "decision": str,
    "score_final": (int, float),
    "solicitud_id": str,
    "engine_version": str,
    "evaluado_en": str,
}

VALID_DECISIONS = {"aprobado", "rechazado", "revision_manual"}

# Formato engine_version esperado: cualquier string non-empty.
# El contract test no valida el formato exacto (hash varía por deploy),
# solo que no venga vacío.
ENGINE_VERSION_MIN_LENGTH = 1

# ISO 8601 básico — valida que tenga forma YYYY-MM-DD al menos
ISO8601_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")

# Payload de prueba canónico · workspace CONTRACT_TEST · nunca genera registro real en RODDOS
_TEST_PAYLOAD = {
    "workspace_id": "CONTRACT_TEST",
    "origen": "argos_contract_test",
    "producto": "credito_repuestos",
    "monto_solicitado": 100_000,
    "datos_personales": {
        "nombre_completo": "Test User Argos Contract",
        "telefono": "+573001234567",
    },
    "context": {
        "es_cliente_roddos": False,
        "score_comportamental_argos": None,
    },
}


def _get_env() -> tuple[str, str]:
    """Devuelve (base_url, api_key) o salta el test si no están configuradas."""
    base_url = os.environ.get("SCORE_ENGINE_API_URL", "").rstrip("/")
    api_key = os.environ.get("SCORE_ENGINE_API_KEY", "")
    if not base_url or not api_key:
        pytest.skip("SCORE_ENGINE_API_URL / SCORE_ENGINE_API_KEY no configuradas · skip en CI de feature")
    return base_url, api_key


@pytest.mark.contract
def test_score_engine_response_fields_required() -> None:
    """Todos los campos required del schema v1 presentes y con tipo correcto."""
    base_url, api_key = _get_env()

    resp = httpx.post(
        f"{base_url}/v1/evaluate",
        json=_TEST_PAYLOAD,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=30.0,
    )

    # 200 = evaluación exitosa · 422 = regla de negocio violada.
    # Ambos son respuestas válidas para un test canónico; lo que validamos es el schema.
    assert resp.status_code in (200, 422), (
        f"Score Engine devolvió HTTP {resp.status_code} — "
        f"esperado 200 o 422. Body: {resp.text[:500]}"
    )

    data = resp.json()

    for field, expected_type in REQUIRED_FIELDS.items():
        assert field in data, (
            f"Campo required ausente: '{field}' · "
            f"Posible cambio breaking en roddos-scoring · "
            f"Response keys presentes: {list(data.keys())}"
        )
        assert isinstance(data[field], expected_type), (
            f"Campo '{field}' tipo incorrecto: "
            f"esperado {expected_type}, recibido {type(data[field]).__name__} "
            f"(valor: {data[field]!r})"
        )


@pytest.mark.contract
def test_score_engine_decision_enum() -> None:
    """El campo 'decision' pertenece al enum canónico."""
    base_url, api_key = _get_env()

    resp = httpx.post(
        f"{base_url}/v1/evaluate",
        json=_TEST_PAYLOAD,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=30.0,
    )
    assert resp.status_code in (200, 422)
    data = resp.json()

    if "decision" in data:
        assert data["decision"] in VALID_DECISIONS, (
            f"decision='{data['decision']}' fuera del enum "
            f"{VALID_DECISIONS}"
        )


@pytest.mark.contract
def test_score_engine_evaluado_en_iso8601() -> None:
    """El campo 'evaluado_en' tiene formato ISO 8601."""
    base_url, api_key = _get_env()

    resp = httpx.post(
        f"{base_url}/v1/evaluate",
        json=_TEST_PAYLOAD,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=30.0,
    )
    assert resp.status_code in (200, 422)
    data = resp.json()

    if "evaluado_en" in data:
        assert ISO8601_RE.match(str(data["evaluado_en"])), (
            f"evaluado_en='{data['evaluado_en']}' no tiene formato ISO 8601 "
            f"(esperado: YYYY-MM-DD...)"
        )


@pytest.mark.contract
def test_score_engine_engine_version_non_empty() -> None:
    """El campo 'engine_version' es un string non-empty."""
    base_url, api_key = _get_env()

    resp = httpx.post(
        f"{base_url}/v1/evaluate",
        json=_TEST_PAYLOAD,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=30.0,
    )
    assert resp.status_code in (200, 422)
    data = resp.json()

    if "engine_version" in data:
        assert len(str(data["engine_version"])) >= ENGINE_VERSION_MIN_LENGTH, (
            "engine_version está vacío · el Score Engine no reporta versión"
        )


@pytest.mark.contract
def test_score_engine_monto_aprobado_when_aprobado() -> None:
    """Si decision == 'aprobado', monto_aprobado debe estar presente y ser numérico."""
    base_url, api_key = _get_env()

    resp = httpx.post(
        f"{base_url}/v1/evaluate",
        json=_TEST_PAYLOAD,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=30.0,
    )
    assert resp.status_code in (200, 422)
    data = resp.json()

    if data.get("decision") == "aprobado":
        assert "monto_aprobado" in data, (
            "decision='aprobado' pero 'monto_aprobado' ausente del response"
        )
        assert isinstance(data["monto_aprobado"], (int, float)), (
            f"monto_aprobado debe ser numérico, recibido: {type(data['monto_aprobado']).__name__}"
        )
        assert data["monto_aprobado"] > 0, (
            f"monto_aprobado={data['monto_aprobado']} debe ser > 0 si decision=aprobado"
        )


@pytest.mark.contract
def test_score_engine_reachable() -> None:
    """El endpoint /v1/evaluate responde (no timeout, no 5xx no-retriable)."""
    base_url, api_key = _get_env()

    try:
        resp = httpx.post(
            f"{base_url}/v1/evaluate",
            json=_TEST_PAYLOAD,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30.0,
        )
    except httpx.TimeoutException as exc:
        pytest.fail(f"Score Engine no responde en 30s: {exc}")
    except httpx.ConnectError as exc:
        pytest.fail(f"Score Engine inalcanzable: {exc}")

    assert resp.status_code < 500, (
        f"Score Engine respondió HTTP {resp.status_code} — error interno del motor. "
        f"Body: {resp.text[:500]}"
    )
