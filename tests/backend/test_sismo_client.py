"""Tests del SismoClient · skip silencioso + parsing defensivo + httpx mock."""
from __future__ import annotations

import httpx
import pytest
from argos.partners.sismo.client import SismoClient, SismoError


async def test_skip_silencioso_sin_credenciales() -> None:
    """Sin URL+key, todas las queries devuelven [] sin tocar red."""
    client = SismoClient(base_url="", api_key="")
    assert client.enabled is False
    async with client:
        assert await client.get_inventory() == []
        assert await client.get_slow_movers() == []
        assert await client.get_daily_sales("2026-04-26") == []


async def test_parsing_acepta_lista_directa() -> None:
    transport = httpx.MockTransport(
        lambda req: httpx.Response(
            200,
            json=[
                {"sku": "FRENO-001", "stock": 12, "precio": 45000},
                {"sku": "FRENO-002", "stock": 0, "precio": 38000},
            ],
        )
    )
    client = SismoClient(base_url="https://sismo.test", api_key="key-test")
    client._client = httpx.AsyncClient(transport=transport, base_url="https://sismo.test")
    items = await client.get_inventory()
    assert len(items) == 2
    assert items[0]["sku"] == "FRENO-001"
    await client._client.aclose()


async def test_parsing_acepta_envoltura_items() -> None:
    transport = httpx.MockTransport(
        lambda req: httpx.Response(
            200,
            json={"items": [{"sku": "ACEITE-001", "dias_inventario": 60}]},
        )
    )
    client = SismoClient(base_url="https://sismo.test", api_key="key-test")
    client._client = httpx.AsyncClient(transport=transport, base_url="https://sismo.test")
    items = await client.get_slow_movers()
    assert len(items) == 1
    assert items[0]["sku"] == "ACEITE-001"
    await client._client.aclose()


async def test_401_levanta_sismo_error() -> None:
    transport = httpx.MockTransport(
        lambda req: httpx.Response(401, text="Unauthorized")
    )
    client = SismoClient(base_url="https://sismo.test", api_key="bad-key")
    client._client = httpx.AsyncClient(transport=transport, base_url="https://sismo.test")
    with pytest.raises(SismoError) as exc_info:
        await client.get_inventory()
    assert exc_info.value.status == 401
    await client._client.aclose()
