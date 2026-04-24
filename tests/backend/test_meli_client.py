from __future__ import annotations

import httpx
import pytest
from argos.partners.meli.client import MeliClient, MeliError


def _mock_transport(handler):
    return httpx.MockTransport(handler)


async def test_search_returns_results() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/sites/MCO/search"
        assert request.url.params["q"] == "aceite moto"
        assert request.url.params["limit"] == "20"
        return httpx.Response(
            200,
            json={
                "results": [
                    {"id": "MCO-1", "title": "Aceite 20W50", "price": 45000},
                    {"id": "MCO-2", "title": "Aceite 10W40", "price": 38000},
                ]
            },
        )

    async with MeliClient() as meli:
        meli._client = httpx.AsyncClient(base_url="https://api.mercadolibre.com", transport=_mock_transport(handler))
        items = await meli.search("aceite moto", limit=20)

    assert len(items) == 2
    assert items[0]["id"] == "MCO-1"


async def test_item_404_raises_meli_error() -> None:
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": "not found"})

    async with MeliClient() as meli:
        meli._client = httpx.AsyncClient(base_url="https://api.mercadolibre.com", transport=_mock_transport(handler))
        with pytest.raises(MeliError) as exc:
            await meli.item("MCO-NOPE")
        assert exc.value.status == 404


async def test_search_429_raises_rate_limited() -> None:
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"message": "too many requests"})

    async with MeliClient() as meli:
        meli._client = httpx.AsyncClient(base_url="https://api.mercadolibre.com", transport=_mock_transport(handler))
        with pytest.raises(MeliError) as exc:
            await meli.search("aceite moto")
        assert exc.value.status == 429


async def test_client_outside_context_raises() -> None:
    meli = MeliClient()
    with pytest.raises(RuntimeError):
        await meli.search("aceite moto")
