"""Tests del classifier Haiku · cliente Anthropic mockeado."""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from argos.agents.classifier.service import HaikuProductClassifier


def _mock_anthropic_response(text: str) -> SimpleNamespace:
    """Construye una respuesta tipo `messages.create` con un solo bloque de texto."""
    return SimpleNamespace(content=[SimpleNamespace(text=text)])


def _mock_client(response_text: str) -> tuple[MagicMock, AsyncMock]:
    """Crea un mock del cliente Anthropic con messages.create configurable."""
    create_mock = AsyncMock(return_value=_mock_anthropic_response(response_text))
    client = MagicMock()
    client.messages = MagicMock()
    client.messages.create = create_mock
    return client, create_mock


async def test_classify_relevant_returns_true() -> None:
    client, _ = _mock_client(json.dumps({"relevante": True, "razon": "es pastilla freno moto"}))
    classifier = HaikuProductClassifier(anthropic_client=client)

    result = await classifier.classify(
        title="Pastillas freno delantero Pulsar NS 200",
        description="",
        watch_query="pastillas freno moto",
    )
    assert result.relevante is True
    assert "pastilla" in result.razon.lower()
    assert result.cached is False


async def test_classify_not_relevant_returns_false() -> None:
    client, _ = _mock_client(
        json.dumps({"relevante": False, "razon": "aceite de oliva no es repuesto moto"})
    )
    classifier = HaikuProductClassifier(anthropic_client=client)

    result = await classifier.classify(
        title="Aceite de oliva extra virgen 1L",
        description="",
        watch_query="aceite moto",
    )
    assert result.relevante is False
    assert "oliva" in result.razon.lower()


async def test_classify_handles_malformed_json_gracefully() -> None:
    """Borderline: Haiku devuelve texto no parseable · classifier debe degradar a relevante=False."""
    client, _ = _mock_client("Esto no es JSON válido en absoluto · solo texto")
    classifier = HaikuProductClassifier(anthropic_client=client)

    result = await classifier.classify(
        title="Filtro raro",
        description="",
        watch_query="filtro aire moto",
    )
    assert result.relevante is False
    assert "parse" in result.razon.lower() or "error" in result.razon.lower()


async def test_cache_hit_avoids_second_api_call() -> None:
    client, create_mock = _mock_client(json.dumps({"relevante": True, "razon": "match"}))
    classifier = HaikuProductClassifier(anthropic_client=client)

    first = await classifier.classify("Aceite Motul 4T", "", "aceite moto")
    second = await classifier.classify("Aceite Motul 4T", "", "aceite moto")

    assert first.relevante is True
    assert first.cached is False
    assert second.relevante is True
    assert second.cached is True
    # Solo UNA llamada a la API · la segunda viene del cache local
    assert create_mock.await_count == 1


async def test_cache_key_normaliza_case_y_whitespace() -> None:
    client, create_mock = _mock_client(json.dumps({"relevante": True, "razon": "match"}))
    classifier = HaikuProductClassifier(anthropic_client=client)

    await classifier.classify("Aceite Motul", "", "aceite moto")
    # Mismo input con caja distinta y trailing spaces
    result = await classifier.classify("  ACEITE MOTUL  ", "", "Aceite Moto")

    assert result.cached is True
    assert create_mock.await_count == 1


async def test_classify_strips_markdown_fences() -> None:
    """Algunos modelos a veces devuelven JSON envuelto en ```json ... ```"""
    client, _ = _mock_client('```json\n{"relevante": true, "razon": "ok"}\n```')
    classifier = HaikuProductClassifier(anthropic_client=client)
    result = await classifier.classify("Bujía NGK CR8E moto", "", "bujía moto")
    assert result.relevante is True


async def test_classify_api_error_returns_safe_false() -> None:
    create_mock = AsyncMock(side_effect=RuntimeError("anthropic_503"))
    client = MagicMock()
    client.messages = MagicMock()
    client.messages.create = create_mock
    classifier = HaikuProductClassifier(anthropic_client=client)

    result = await classifier.classify("Algo", "", "algo")
    assert result.relevante is False
    assert "api_error" in result.razon
