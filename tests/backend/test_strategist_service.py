"""Tests del Strategist · Anthropic mockeado · sin llamadas reales."""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from argos.agents.strategist.service import (
    SONNET_MODEL,
    Mercado24h,
    StrategistAgent,
    _parse_briefing_response,
    _Signals,
)


def _mock_response(text: str, *, input_tokens: int = 1500, output_tokens: int = 400) -> SimpleNamespace:
    return SimpleNamespace(
        content=[SimpleNamespace(text=text)],
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
    )


def _mock_client(response_text: str) -> tuple[MagicMock, AsyncMock]:
    create_mock = AsyncMock(return_value=_mock_response(response_text))
    client = MagicMock()
    client.messages = MagicMock()
    client.messages.create = create_mock
    return client, create_mock


def test_strategist_raises_sin_api_key_ni_client_inyectado() -> None:
    with pytest.raises(RuntimeError) as exc:
        StrategistAgent()
    assert "ANTHROPIC_API_KEY" in str(exc.value)


async def test_generate_briefing_pasa_cache_control_y_modelo_correcto() -> None:
    sample_briefing = {
        "fecha": "2026-04-26",
        "mercado_24h": {"nuevos_skus": 5, "bajas_precio": 2, "nuevas_promos": 1},
        "acciones_del_dia": [
            {
                "accion": "Bajar aceite Motul a $52K",
                "justificacion": "competidor X bajó 22%",
                "impacto_esperado": "recuperar share aceite",
                "prioridad": "Alta",
            }
        ],
        "estado_mercado": "Día agresivo en aceites · respuesta requerida hoy.",
    }
    client, create_mock = _mock_client(json.dumps(sample_briefing))
    agent = StrategistAgent(anthropic_client=client)

    signals = _Signals()  # vacío · no hace gather, va directo
    briefing = await agent.generate_morning_briefing(db=MagicMock(), workspace_id="RODDOS", signals=signals)

    # Verifica llamada con cache_control en system + modelo correcto
    create_mock.assert_awaited_once()
    call = create_mock.await_args
    assert call.kwargs["model"] == SONNET_MODEL
    system_blocks = call.kwargs["system"]
    assert isinstance(system_blocks, list)
    assert system_blocks[0]["cache_control"] == {"type": "ephemeral"}
    assert "Strategist" in system_blocks[0]["text"]

    # Briefing parseado correctamente
    assert briefing.fecha == "2026-04-26"
    assert briefing.mercado_24h.nuevos_skus == 5
    assert len(briefing.acciones_del_dia) == 1
    assert briefing.acciones_del_dia[0].prioridad == "Alta"
    assert briefing.tokens_input == 1500
    assert briefing.tokens_output == 400
    assert briefing.modelo_usado == SONNET_MODEL


async def test_generate_briefing_handles_malformed_json_gracefully() -> None:
    """Si Claude devuelve texto no parseable, devuelve briefing degradado pero válido."""
    client, _ = _mock_client("Esto no es JSON · prosa libre")
    agent = StrategistAgent(anthropic_client=client)
    signals = _Signals()

    briefing = await agent.generate_morning_briefing(
        db=MagicMock(), workspace_id="RODDOS", signals=signals
    )

    assert briefing.acciones_del_dia == []
    assert "no se pudo generar" in briefing.estado_mercado.lower()
    assert isinstance(briefing.mercado_24h, Mercado24h)


async def test_generate_briefing_capa_a_3_acciones_max() -> None:
    """Si Claude devuelve 5 acciones, solo persistimos las primeras 3 (ROG inamovible)."""
    sample = {
        "fecha": "2026-04-26",
        "mercado_24h": {"nuevos_skus": 0, "bajas_precio": 0, "nuevas_promos": 0},
        "acciones_del_dia": [
            {"accion": f"Acción {i}", "justificacion": "x", "impacto_esperado": "y", "prioridad": "Media"}
            for i in range(5)
        ],
        "estado_mercado": "ok",
    }
    client, _ = _mock_client(json.dumps(sample))
    agent = StrategistAgent(anthropic_client=client)

    briefing = await agent.generate_morning_briefing(
        db=MagicMock(), workspace_id="RODDOS", signals=_Signals()
    )
    assert len(briefing.acciones_del_dia) == 3


def test_parse_strips_markdown_fences() -> None:
    """A veces Claude envuelve el JSON en ```json ... ``` aunque pidamos lo contrario."""
    payload = json.dumps({
        "fecha": "2026-04-26",
        "mercado_24h": {"nuevos_skus": 1, "bajas_precio": 0, "nuevas_promos": 0},
        "acciones_del_dia": [],
        "estado_mercado": "ok",
    })
    raw = f"```json\n{payload}\n```"
    briefing = _parse_briefing_response(raw, "2026-04-26")
    assert briefing.mercado_24h.nuevos_skus == 1
    assert briefing.estado_mercado == "ok"


def test_parse_normaliza_prioridad_invalida_a_media() -> None:
    raw = json.dumps({
        "fecha": "2026-04-26",
        "mercado_24h": {"nuevos_skus": 0, "bajas_precio": 0, "nuevas_promos": 0},
        "acciones_del_dia": [
            {"accion": "x", "justificacion": "y", "impacto_esperado": "z", "prioridad": "URGENTE"}
        ],
        "estado_mercado": "ok",
    })
    briefing = _parse_briefing_response(raw, "2026-04-26")
    assert briefing.acciones_del_dia[0].prioridad == "Media"
