"""Tests de WavaClient (Build 3.3).

Valida: create_order, get_order, get_gateways, submit_daviplata_otp,
skip sin merchant key, error handling, WavaOrder dataclass.

Refs: phase_3/build_3.3
"""
from __future__ import annotations

import httpx
import pytest
from argos.partners.wava.client import (
    WavaClient,
    WavaError,
    WavaOrder,
    WavaShopper,
)

# ---------------------------------------------------------------------------
# WavaShopper
# ---------------------------------------------------------------------------

def test_shopper_to_dict() -> None:
    shopper = WavaShopper(
        first_name="Juan",
        last_name="Pérez",
        email="juan@test.com",
        phone_number="+573001234567",
        id_number="1234567890",
        id_type=1,
    )
    d = shopper.to_dict()
    assert d["first_name"] == "Juan"
    assert d["country"] == "CO"
    assert d["id_type"] == 1


# ---------------------------------------------------------------------------
# WavaOrder.from_response
# ---------------------------------------------------------------------------

def test_order_from_response() -> None:
    data = {
        "id": "ord_123",
        "status": "pending",
        "amount": 25000,
        "currency": "COP",
        "description": "Compra repuesto",
        "payment_url": "https://pay.wava.co/ord_123",
        "order_key": "wa-RODDOS-573001234567-abc123",
    }
    order = WavaOrder.from_response(data)
    assert order.order_id == "ord_123"
    assert order.status == "pending"
    assert order.amount == 25000.0
    assert order.payment_url == "https://pay.wava.co/ord_123"
    assert order.order_key == "wa-RODDOS-573001234567-abc123"


def test_order_from_response_missing_fields() -> None:
    order = WavaOrder.from_response({})
    assert order.order_id == ""
    assert order.status == ""
    assert order.amount == 0.0


# ---------------------------------------------------------------------------
# WavaClient · enabled / skip
# ---------------------------------------------------------------------------

def test_client_enabled_with_key() -> None:
    client = WavaClient(merchant_key="test-key-123")
    assert client.enabled is True


def test_client_disabled_without_key() -> None:
    client = WavaClient(merchant_key="")
    assert client.enabled is False


async def test_client_skip_without_key() -> None:
    async with WavaClient(merchant_key="") as client:
        order = await client.create_order(
            amount=10000,
            description="test",
            shopper=WavaShopper(
                first_name="Test",
                last_name="User",
                email="test@test.com",
                phone_number="+573001234567",
            ),
        )
    assert order.order_id == ""


# ---------------------------------------------------------------------------
# WavaClient · context manager
# ---------------------------------------------------------------------------

async def test_context_manager_creates_httpx_client() -> None:
    async with WavaClient(merchant_key="test-key") as client:
        assert client._client is not None
        assert client._owns_client is True
    assert client._client is None


async def test_context_manager_no_client_without_key() -> None:
    async with WavaClient(merchant_key="") as client:
        assert client._client is None


# ---------------------------------------------------------------------------
# WavaClient · create_order
# ---------------------------------------------------------------------------

async def test_create_order_success() -> None:
    mock_response = httpx.Response(
        200,
        json={
            "id": "ord_456",
            "status": "pending",
            "amount": 25000,
            "currency": "COP",
            "description": "Compra WhatsApp",
            "payment_url": "https://pay.wava.co/ord_456",
        },
    )

    transport = httpx.MockTransport(lambda req: mock_response)

    async with WavaClient(merchant_key="test-key", base_url="https://api.dev.wava.co/v1") as client:
        client._client = httpx.AsyncClient(
            base_url="https://api.dev.wava.co/v1",
            transport=transport,
            headers={"merchant-key": "test-key"},
        )
        order = await client.create_order(
            amount=25000,
            description="Compra WhatsApp",
            shopper=WavaShopper(
                first_name="Juan",
                last_name="Pérez",
                email="juan@test.com",
                phone_number="+573001234567",
                id_number="1234567890",
            ),
            gateway_id=1,
            order_key="wa-test-123",
        )

    assert order.order_id == "ord_456"
    assert order.status == "pending"
    assert order.amount == 25000.0


# ---------------------------------------------------------------------------
# WavaClient · get_order
# ---------------------------------------------------------------------------

async def test_get_order_success() -> None:
    mock_response = httpx.Response(
        200,
        json={
            "id": "ord_789",
            "status": "confirmed",
            "amount": 50000,
        },
    )
    transport = httpx.MockTransport(lambda req: mock_response)

    async with WavaClient(merchant_key="test-key") as client:
        client._client = httpx.AsyncClient(
            base_url="https://api.dev.wava.co/v1",
            transport=transport,
            headers={"merchant-key": "test-key"},
        )
        order = await client.get_order("ord_789")

    assert order.order_id == "ord_789"
    assert order.status == "confirmed"


# ---------------------------------------------------------------------------
# WavaClient · get_gateways
# ---------------------------------------------------------------------------

async def test_get_gateways() -> None:
    mock_response = httpx.Response(
        200,
        json={"data": [{"id": 1, "name": "Nequi"}, {"id": 2, "name": "Daviplata"}]},
    )
    transport = httpx.MockTransport(lambda req: mock_response)

    async with WavaClient(merchant_key="test-key") as client:
        client._client = httpx.AsyncClient(
            base_url="https://api.dev.wava.co/v1",
            transport=transport,
            headers={"merchant-key": "test-key"},
        )
        gateways = await client.get_gateways()

    assert len(gateways) == 2
    assert gateways[0]["name"] == "Nequi"


# ---------------------------------------------------------------------------
# WavaClient · error handling
# ---------------------------------------------------------------------------

async def test_create_order_http_error() -> None:
    mock_response = httpx.Response(400, text="Bad Request: missing amount")
    transport = httpx.MockTransport(lambda req: mock_response)

    async with WavaClient(merchant_key="test-key") as client:
        client._client = httpx.AsyncClient(
            base_url="https://api.dev.wava.co/v1",
            transport=transport,
            headers={"merchant-key": "test-key"},
        )
        with pytest.raises(WavaError) as exc_info:
            await client.create_order(
                amount=0,
                description="test",
                shopper=WavaShopper(
                    first_name="Test",
                    last_name="User",
                    email="t@t.com",
                    phone_number="+573001234567",
                ),
            )
    assert exc_info.value.status == 400


# ---------------------------------------------------------------------------
# WavaClient · submit_daviplata_otp
# ---------------------------------------------------------------------------

async def test_submit_daviplata_otp() -> None:
    mock_response = httpx.Response(200, json={"status": "otp_sent"})
    transport = httpx.MockTransport(lambda req: mock_response)

    async with WavaClient(merchant_key="test-key") as client:
        client._client = httpx.AsyncClient(
            base_url="https://api.dev.wava.co/v1",
            transport=transport,
            headers={"merchant-key": "test-key"},
        )
        result = await client.submit_daviplata_otp("ord_123", "654321")

    assert result["status"] == "otp_sent"


# ---------------------------------------------------------------------------
# WavaClient · merchant-key header
# ---------------------------------------------------------------------------

async def test_merchant_key_header_sent() -> None:
    captured_headers = {}

    def capture_transport(request: httpx.Request) -> httpx.Response:
        captured_headers.update(dict(request.headers))
        return httpx.Response(200, json={"id": "ord_test", "status": "pending"})

    transport = httpx.MockTransport(capture_transport)

    async with WavaClient(merchant_key="my-secret-key") as client:
        client._client = httpx.AsyncClient(
            base_url="https://api.dev.wava.co/v1",
            transport=transport,
            headers={"merchant-key": "my-secret-key"},
        )
        await client.get_order("ord_test")

    assert captured_headers.get("merchant-key") == "my-secret-key"
