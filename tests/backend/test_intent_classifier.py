"""Tests de IntentClassifier (Build 3.1 · Capa 1).

Valida: routing logic, confidence threshold, fallback sin API key,
intent sets, event emission.

Refs: phase_3/build_3.1 · ROG-W6
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from argos.agents.whatsapp.intent_classifier import (
    ALL_INTENTS,
    ARGOS_INTENTS,
    CONFIDENCE_THRESHOLD,
    SISMO_INTENTS,
    ClassificationResult,
    _determine_route,
    classify_intent,
)

# ---------------------------------------------------------------------------
# Intent sets
# ---------------------------------------------------------------------------

def test_argos_intents_defined() -> None:
    assert "cotizar_repuesto" in ARGOS_INTENTS
    assert "cotizar_moto" in ARGOS_INTENTS
    assert "consulta_credito" in ARGOS_INTENTS
    assert "consulta_general" in ARGOS_INTENTS
    assert "onboarding" in ARGOS_INTENTS


def test_sismo_intents_defined() -> None:
    assert "pago_cuota" in SISMO_INTENTS
    assert "consulta_mora" in SISMO_INTENTS
    assert "soporte_credito" in SISMO_INTENTS
    assert "comprobante_pago" in SISMO_INTENTS


def test_no_overlap_argos_sismo() -> None:
    assert set() == ARGOS_INTENTS & SISMO_INTENTS


def test_all_intents_is_union() -> None:
    assert ALL_INTENTS == ARGOS_INTENTS | SISMO_INTENTS


# ---------------------------------------------------------------------------
# _determine_route
# ---------------------------------------------------------------------------

def test_low_confidence_routes_argos() -> None:
    assert _determine_route("pago_cuota", 0.5) == "argos"


def test_high_confidence_sismo_intent_routes_sismo() -> None:
    assert _determine_route("pago_cuota", 0.9) == "sismo"


def test_high_confidence_argos_intent_routes_argos() -> None:
    assert _determine_route("cotizar_repuesto", 0.95) == "argos"


def test_threshold_boundary_routes_argos() -> None:
    assert _determine_route("pago_cuota", CONFIDENCE_THRESHOLD - 0.01) == "argos"


def test_threshold_exact_routes_sismo() -> None:
    assert _determine_route("pago_cuota", CONFIDENCE_THRESHOLD) == "sismo"


# ---------------------------------------------------------------------------
# classify_intent · sin API key
# ---------------------------------------------------------------------------

async def test_classify_no_api_key_returns_default() -> None:
    result = await classify_intent("Hola quiero un repuesto", anthropic_api_key="")
    assert result.intent == "consulta_general"
    assert result.confidence == 0.0
    assert result.route_to == "argos"


# ---------------------------------------------------------------------------
# classify_intent · con mock de Anthropic
# ---------------------------------------------------------------------------

async def test_classify_cotizar_repuesto() -> None:
    mock_response = MagicMock()
    mock_response.content = [
        MagicMock(text=json.dumps({"intent": "cotizar_repuesto", "confidence": 0.92}))
    ]

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    with patch("anthropic.AsyncAnthropic", return_value=mock_client):
        result = await classify_intent(
            "Cuánto vale un filtro de aceite para Pulsar NS200?",
            phone="573001234567",
            anthropic_api_key="test-key",
        )

    assert result.intent == "cotizar_repuesto"
    assert result.confidence == 0.92
    assert result.route_to == "argos"


async def test_classify_pago_cuota_routes_sismo() -> None:
    mock_response = MagicMock()
    mock_response.content = [
        MagicMock(text=json.dumps({"intent": "pago_cuota", "confidence": 0.88}))
    ]

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    with patch("anthropic.AsyncAnthropic", return_value=mock_client):
        result = await classify_intent(
            "Quiero pagar mi cuota de hoy",
            anthropic_api_key="test-key",
        )

    assert result.intent == "pago_cuota"
    assert result.route_to == "sismo"


async def test_classify_invalid_json_falls_back() -> None:
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="not valid json at all")]

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    with patch("anthropic.AsyncAnthropic", return_value=mock_client):
        result = await classify_intent(
            "asdfgh",
            anthropic_api_key="test-key",
        )

    assert result.intent == "consulta_general"
    assert result.confidence == 0.0
    assert result.route_to == "argos"


async def test_classify_unknown_intent_falls_back() -> None:
    mock_response = MagicMock()
    mock_response.content = [
        MagicMock(text=json.dumps({"intent": "invented_intent", "confidence": 0.99}))
    ]

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    with patch("anthropic.AsyncAnthropic", return_value=mock_client):
        result = await classify_intent(
            "blah",
            anthropic_api_key="test-key",
        )

    assert result.intent == "consulta_general"
    assert result.confidence == 0.0


# ---------------------------------------------------------------------------
# ClassificationResult
# ---------------------------------------------------------------------------

def test_classification_result_as_dict() -> None:
    r = ClassificationResult(
        intent="cotizar_repuesto",
        confidence=0.9,
        route_to="argos",
        raw_response="{}",
    )
    d = r.as_dict()
    assert d["intent"] == "cotizar_repuesto"
    assert d["route_to"] == "argos"


def test_classification_result_is_frozen() -> None:
    r = ClassificationResult(intent="x", confidence=0.5, route_to="argos")
    with pytest.raises(AttributeError):
        r.intent = "y"  # type: ignore[misc]
