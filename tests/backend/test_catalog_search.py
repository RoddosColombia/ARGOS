"""Tests de catalog_search (Build 3.2).

Valida: búsqueda por keyword, sin resultados, enriquecimiento con stock SISMO,
regex building, edge cases.

Refs: phase_3/build_3.2
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from argos.agents.whatsapp.catalog_search import (
    _build_search_regex,
    search_catalog,
)

# ---------------------------------------------------------------------------
# _build_search_regex
# ---------------------------------------------------------------------------

def test_build_regex_single_word() -> None:
    regex = _build_search_regex("filtro")
    assert "filtro" in regex


def test_build_regex_multiple_words() -> None:
    regex = _build_search_regex("filtro aceite pulsar")
    assert "filtro" in regex
    assert "aceite" in regex
    assert "pulsar" in regex


def test_build_regex_short_words_ignored() -> None:
    regex = _build_search_regex("a de filtro")
    assert "filtro" in regex
    assert regex.count("|") == 0


def test_build_regex_empty() -> None:
    assert _build_search_regex("") == ""
    assert _build_search_regex("a b") == ""


# ---------------------------------------------------------------------------
# search_catalog · sin resultados
# ---------------------------------------------------------------------------

async def test_search_empty_query() -> None:
    db = MagicMock()
    results = await search_catalog(db, "", "RODDOS")
    assert results == []


async def test_search_no_matches() -> None:
    db = MagicMock()
    mock_cursor = AsyncMock()
    mock_cursor.to_list = AsyncMock(return_value=[])
    mock_cursor.sort = MagicMock(return_value=mock_cursor)
    mock_cursor.limit = MagicMock(return_value=mock_cursor)

    mock_collection = MagicMock()
    mock_collection.find = MagicMock(return_value=mock_cursor)

    db.__getitem__ = MagicMock(return_value=mock_collection)

    results = await search_catalog(db, "repuesto inexistente xyz", "RODDOS")
    assert results == []


# ---------------------------------------------------------------------------
# search_catalog · con resultados
# ---------------------------------------------------------------------------

async def test_search_finds_products() -> None:
    db = MagicMock()

    catalog_cursor = AsyncMock()
    catalog_cursor.to_list = AsyncMock(return_value=[
        {
            "nombre": "Filtro Aceite Pulsar NS200",
            "precio_actual": 25000,
            "stock_disponible": 10,
            "source": "meli",
            "categoria": "repuestos.aceite",
            "compatible_motos": ["Pulsar NS200"],
            "permalink": "https://meli.co/123",
        },
    ])
    catalog_cursor.sort = MagicMock(return_value=catalog_cursor)
    catalog_cursor.limit = MagicMock(return_value=catalog_cursor)

    sismo_agg_cursor = AsyncMock()
    sismo_agg_cursor.to_list = AsyncMock(return_value=[
        {"max_date": "2026-05-14"},
    ])

    sismo_stock_cursor = AsyncMock()
    sismo_stock_cursor.to_list = AsyncMock(return_value=[
        {"nombre": "Filtro Aceite Pulsar NS200", "stock": 8, "precio": 22000, "sku": "FA-NS200"},
    ])
    sismo_stock_cursor.limit = MagicMock(return_value=sismo_stock_cursor)

    def get_collection(name):
        mock = MagicMock()
        if name == "products_catalog":
            mock.find = MagicMock(return_value=catalog_cursor)
        elif name == "sismo_inventory":
            mock.aggregate = MagicMock(return_value=sismo_agg_cursor)
            mock.find = MagicMock(return_value=sismo_stock_cursor)
        return mock

    db.__getitem__ = MagicMock(side_effect=get_collection)

    results = await search_catalog(db, "filtro aceite pulsar", "RODDOS")

    assert len(results) == 1
    assert results[0]["nombre"] == "Filtro Aceite Pulsar NS200"
    assert results[0]["precio"] == 25000
    assert results[0]["stock"] == 8
    assert results[0]["stock_source"] == "sismo"


async def test_search_without_sismo_uses_catalog_stock() -> None:
    db = MagicMock()

    catalog_cursor = AsyncMock()
    catalog_cursor.to_list = AsyncMock(return_value=[
        {
            "nombre": "Pastillas Freno Delantero",
            "precio_actual": 35000,
            "stock_disponible": 5,
            "source": "meli",
            "categoria": "",
            "compatible_motos": [],
            "permalink": "",
        },
    ])
    catalog_cursor.sort = MagicMock(return_value=catalog_cursor)
    catalog_cursor.limit = MagicMock(return_value=catalog_cursor)

    sismo_agg_cursor = AsyncMock()
    sismo_agg_cursor.to_list = AsyncMock(return_value=[])

    def get_collection(name):
        mock = MagicMock()
        if name == "products_catalog":
            mock.find = MagicMock(return_value=catalog_cursor)
        elif name == "sismo_inventory":
            mock.aggregate = MagicMock(return_value=sismo_agg_cursor)
        return mock

    db.__getitem__ = MagicMock(side_effect=get_collection)

    results = await search_catalog(db, "pastillas freno", "RODDOS")

    assert len(results) == 1
    assert results[0]["stock"] == 5
    assert results[0]["stock_source"] == "catalog"
