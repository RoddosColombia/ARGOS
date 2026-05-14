"""Tests de MercatelyClient (Build 3.1 · Capa 1).

Valida: normalización de phone, skip silencioso, context manager,
send_template, send_text, get_customer_by_phone, get_customer_messages,
create_customer, error handling.

Refs: phase_3/build_3.1 · docs/canonicas/apis_externas.md
"""
from __future__ import annotations

import json

import httpx
import pytest
from argos.partners.mercately.client import (
    MERCATELY_BASE_URL,
    MercatelyClient,
    MercatelyError,
    normalize_phone,
)

# ---------------------------------------------------------------------------
# normalize_phone
# ---------------------------------------------------------------------------

class TestNormalizePhone:
    def test_10_digit_adds_57(self) -> None:
        assert normalize_phone("3001234567") == "573001234567"

    def test_12_digit_with_57_passthrough(self) -> None:
        assert normalize_phone("573001234567") == "573001234567"

    def test_plus_prefix_stripped(self) -> None:
        assert normalize_phone("+573001234567") == "573001234567"

    def test_leading_zero_stripped(self) -> None:
        assert normalize_phone("03001234567") == "573001234567"

    def test_spaces_and_dashes_stripped(self) -> None:
        assert normalize_phone("300 123 4567") == "573001234567"
        assert normalize_phone("300-123-4567") == "573001234567"

    def test_invalid_too_short(self) -> None:
        with pytest.raises(ValueError, match="Phone inválido"):
            normalize_phone("12345")

    def test_invalid_non_57(self) -> None:
        with pytest.raises(ValueError, match="Phone inválido"):
            normalize_phone("551234567890")


# ---------------------------------------------------------------------------
# MercatelyClient · skip silencioso
# ---------------------------------------------------------------------------

class TestMercatelyClientEnabled:
    def test_disabled_without_api_key(self) -> None:
        client = MercatelyClient(api_key="")
        assert not client.enabled

    def test_enabled_with_api_key(self) -> None:
        client = MercatelyClient(api_key="test-key")
        assert client.enabled


class TestMercatelyClientContextManager:
    async def test_disabled_client_no_http(self) -> None:
        client = MercatelyClient(api_key="")
        async with client as c:
            result = await c.send_text("3001234567", "hola")
            assert result == {}

    async def test_enabled_creates_http_client(self) -> None:
        client = MercatelyClient(api_key="test-key")
        async with client:
            assert client._client is not None
        assert client._client is None


# ---------------------------------------------------------------------------
# Helper · inyecta MockTransport en MercatelyClient
# ---------------------------------------------------------------------------

def _mock_mercately(
    *,
    status_code: int = 200,
    response_json: dict | None = None,
    response_text: str = "",
) -> MercatelyClient:
    captured: dict = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["url"] = str(req.url)
        captured["method"] = req.method
        captured["headers"] = dict(req.headers)
        captured["body"] = req.content.decode("utf-8") if req.content else ""
        if response_json is not None:
            return httpx.Response(status_code, json=response_json)
        return httpx.Response(status_code, text=response_text or "")

    client = MercatelyClient(api_key="my-secret-key")
    transport = httpx.MockTransport(handler)
    client._client = httpx.AsyncClient(
        transport=transport,
        base_url=MERCATELY_BASE_URL,
        headers={"api-key": "my-secret-key"},
    )
    client._captured = captured  # type: ignore[attr-defined]
    return client


# ---------------------------------------------------------------------------
# MercatelyClient · métodos con MockTransport
# ---------------------------------------------------------------------------

class TestMercatelyClientMethods:
    async def test_send_template_success(self) -> None:
        c = _mock_mercately(response_json={"status": "sent", "id": "msg_123"})
        result = await c.send_template("3001234567", "tmpl_1", ["param1"])
        assert result["status"] == "sent"
        body = json.loads(c._captured["body"])  # type: ignore[attr-defined]
        assert body["phone"] == "573001234567"
        assert body["template_id"] == "tmpl_1"
        assert body["params"] == ["param1"]

    async def test_send_text_success(self) -> None:
        c = _mock_mercately(response_json={"status": "sent"})
        result = await c.send_text("573001234567", "Hola, tenemos tu repuesto")
        assert result["status"] == "sent"

    async def test_get_customer_by_phone(self) -> None:
        c = _mock_mercately(response_json={"phone": "573001234567", "first_name": "Test"})
        result = await c.get_customer_by_phone("3001234567")
        assert result["phone"] == "573001234567"
        assert "/customers/573001234567" in c._captured["url"]  # type: ignore[attr-defined]

    async def test_get_customer_messages(self) -> None:
        c = _mock_mercately(response_json={"data": [{"messages": []}]})
        result = await c.get_customer_messages("3001234567")
        assert "data" in result
        url = c._captured["url"]  # type: ignore[attr-defined]
        assert "/customers/573001234567/whatsapp_conversations" in url

    async def test_create_customer(self) -> None:
        c = _mock_mercately(response_json={"id": 42, "phone": "573001234567"})
        result = await c.create_customer("3001234567", first_name="Test")
        assert result["id"] == 42

    async def test_http_400_raises_mercately_error(self) -> None:
        c = _mock_mercately(status_code=400, response_text="Bad Request")
        with pytest.raises(MercatelyError, match="400"):
            await c.get_customer_by_phone("3001234567")

    async def test_api_key_header_sent(self) -> None:
        c = _mock_mercately(response_json={})
        await c.get_customer_by_phone("3001234567")
        headers = c._captured["headers"]  # type: ignore[attr-defined]
        assert headers["api-key"] == "my-secret-key"
