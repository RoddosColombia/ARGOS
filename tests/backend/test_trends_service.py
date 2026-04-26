"""Tests del Trends agent · SerpAPI mockeado."""
from __future__ import annotations

from argos.agents.trends.service import (
    SPIKE_THRESHOLD_PCT,
    TrendResult,
    TrendsAgent,
    _parse_serpapi_response,
)
from argos.partners.serpapi.client import SerpApiClient


def _serpapi_payload(values: list[int]) -> dict:
    """Construye un response SerpAPI de google_trends con los valores indicados."""
    return {
        "interest_over_time": {
            "timeline_data": [
                {"date": f"d{i}", "values": [{"extracted_value": v}]}
                for i, v in enumerate(values)
            ]
        }
    }


def test_parse_normaliza_serpapi_response_correctamente() -> None:
    raw = _serpapi_payload([20, 25, 30, 35, 40, 45, 50])
    result = _parse_serpapi_response("aceite moto", raw)
    assert isinstance(result, TrendResult)
    assert result.keyword == "aceite moto"
    assert result.interest_over_time == 50  # último punto del timeline
    assert result.delta_7d_pct == 150.0  # (50-20)/20 * 100
    assert result.pico_detectado is True  # delta > 30


def test_parse_marca_pico_cuando_delta_supera_threshold() -> None:
    raw = _serpapi_payload([10, 50])  # delta = 400%
    result = _parse_serpapi_response("repuestos TVS Raider 125", raw)
    assert result.pico_detectado is True
    assert result.delta_7d_pct > SPIKE_THRESHOLD_PCT


def test_parse_no_marca_pico_cuando_delta_es_pequeno() -> None:
    raw = _serpapi_payload([50, 55])  # delta = 10%
    result = _parse_serpapi_response("filtro aire moto", raw)
    assert result.pico_detectado is False
    assert result.interest_over_time == 55


def test_parse_response_vacio_devuelve_zeros() -> None:
    result = _parse_serpapi_response("nada", {})
    assert result.interest_over_time == 0
    assert result.delta_7d_pct == 0.0
    assert result.pico_detectado is False


async def test_trends_agent_skip_sin_api_key() -> None:
    """Sin API key → fetch_keyword_trends devuelve [] sin levantar."""
    client = SerpApiClient(api_key="")  # disabled
    async with TrendsAgent(client=client) as agent:
        results = await agent.fetch_keyword_trends(["aceite moto", "pastillas freno"])
    assert results == []


async def test_trends_agent_fetch_normaliza_lista() -> None:
    """Cliente mockeado · fetch sobre lista devuelve TrendResult por keyword."""

    class _FakeClient(SerpApiClient):
        def __init__(self):
            super().__init__(api_key="fake")

        @property
        def enabled(self) -> bool:
            return True

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_exc):
            return None

        async def google_trends(self, keyword, **_kwargs):  # type: ignore[override]
            return _serpapi_payload([10, 20, 30, 40, 50, 60, 70])

    fake = _FakeClient()
    async with TrendsAgent(client=fake) as agent:
        results = await agent.fetch_keyword_trends(["aceite moto", "pastillas"])

    assert len(results) == 2
    assert all(isinstance(r, TrendResult) for r in results)
    assert all(r.pico_detectado for r in results)  # delta = 600%
