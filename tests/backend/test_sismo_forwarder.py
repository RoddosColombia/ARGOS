"""Tests de SismoForwarder (Build 3.1 · Capa 1).

Valida: skip sin URL, forward exitoso, forward fallido non-blocking,
header X-Mercately-Secret, payload format.

Refs: phase_3/build_3.1 · ROG-A11
"""
from __future__ import annotations

import json
from unittest.mock import patch

import httpx
from argos.agents.whatsapp.sismo_forwarder import forward_to_sismo

SISMO_URL = "https://sismo.roddos.com/api/v1/whatsapp/inbound"


# ---------------------------------------------------------------------------
# Skip sin URL
# ---------------------------------------------------------------------------

async def test_skip_without_url() -> None:
    result = await forward_to_sismo(
        phone="573001234567",
        message_text="Quiero pagar mi cuota",
        intent="pago_cuota",
        confidence=0.88,
        sismo_webhook_url="",
    )
    assert result["forwarded"] is False
    assert result["reason"] == "no_sismo_webhook_url"


# ---------------------------------------------------------------------------
# Forward exitoso
# ---------------------------------------------------------------------------

async def test_forward_success() -> None:
    captured: dict = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["headers"] = dict(req.headers)
        captured["body"] = json.loads(req.content.decode("utf-8"))
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    mock_client = httpx.AsyncClient(transport=transport)

    with patch("argos.agents.whatsapp.sismo_forwarder.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value = mock_client

        result = await forward_to_sismo(
            phone="573001234567",
            message_text="Quiero pagar mi cuota",
            intent="pago_cuota",
            confidence=0.88,
            sismo_webhook_url=SISMO_URL,
            webhook_secret="secret123",
        )

    assert result["forwarded"] is True
    assert result["sismo_status"] == 200
    assert captured["headers"]["x-mercately-secret"] == "secret123"
    assert captured["body"]["phone"] == "573001234567"
    assert captured["body"]["intent"] == "pago_cuota"
    assert captured["body"]["source"] == "argos_inbound_poller"


# ---------------------------------------------------------------------------
# Forward fallido · non-blocking
# ---------------------------------------------------------------------------

async def test_forward_sismo_500_non_blocking() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error")

    transport = httpx.MockTransport(handler)
    mock_client = httpx.AsyncClient(transport=transport)

    with patch("argos.agents.whatsapp.sismo_forwarder.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value = mock_client

        result = await forward_to_sismo(
            phone="573001234567",
            message_text="Cuánto debo?",
            intent="consulta_mora",
            confidence=0.9,
            sismo_webhook_url=SISMO_URL,
        )

    assert result["forwarded"] is False
    assert result["sismo_status"] == 500


# ---------------------------------------------------------------------------
# Sin webhook secret · no envía header
# ---------------------------------------------------------------------------

async def test_no_secret_no_header() -> None:
    captured: dict = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["headers"] = dict(req.headers)
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    mock_client = httpx.AsyncClient(transport=transport)

    with patch("argos.agents.whatsapp.sismo_forwarder.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value = mock_client

        await forward_to_sismo(
            phone="573001234567",
            message_text="test",
            intent="pago_cuota",
            confidence=0.8,
            sismo_webhook_url=SISMO_URL,
            webhook_secret="",
        )

    assert "x-mercately-secret" not in captured["headers"]


# ---------------------------------------------------------------------------
# Payload truncation
# ---------------------------------------------------------------------------

async def test_message_truncated_at_4096() -> None:
    captured: dict = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(req.content.decode("utf-8"))
        return httpx.Response(200, json={})

    transport = httpx.MockTransport(handler)
    mock_client = httpx.AsyncClient(transport=transport)

    with patch("argos.agents.whatsapp.sismo_forwarder.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value = mock_client

        long_msg = "x" * 5000
        await forward_to_sismo(
            phone="573001234567",
            message_text=long_msg,
            intent="pago_cuota",
            confidence=0.8,
            sismo_webhook_url=SISMO_URL,
        )

    assert len(captured["body"]["message"]) == 4096
