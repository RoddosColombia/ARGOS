"""Tests del flujo cotización → confirmar → crear orden Wava (Build 3.3).

Valida: confirmar_compra dispatch, contacto no encontrado, datos incompletos,
wava no disponible, orden creada + persistida en wava_orders.

Refs: phase_3/build_3.3 · ROG-W7
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from argos.agents.whatsapp.conversation_handler import (
    _create_wava_order,
    _doc_type_to_wava_id,
    handle_message,
)
from argos.agents.whatsapp.intent_classifier import ClassificationResult
from argos.partners.wava.client import WavaClient, WavaError, WavaOrder

# ---------------------------------------------------------------------------
# _doc_type_to_wava_id
# ---------------------------------------------------------------------------

def test_doc_type_cc() -> None:
    assert _doc_type_to_wava_id("CC") == 1


def test_doc_type_ce() -> None:
    assert _doc_type_to_wava_id("CE") == 2


def test_doc_type_unknown_defaults_cc() -> None:
    assert _doc_type_to_wava_id("PASAPORTE") == 1


# ---------------------------------------------------------------------------
# handle_message · confirmar_compra · wava no disponible
# ---------------------------------------------------------------------------

async def test_handle_confirmar_compra_wava_disabled() -> None:
    db = MagicMock()
    db.__getitem__ = MagicMock(return_value=MagicMock(insert_one=AsyncMock()))

    mock_mercately = AsyncMock()
    mock_mercately.enabled = True
    mock_mercately.send_text = AsyncMock(return_value={})

    classification = ClassificationResult(
        intent="confirmar_compra", confidence=0.9, route_to="argos",
    )

    result = await handle_message(
        db,
        classification=classification,
        message_text="Sí quiero comprarlo",
        phone="573001234567",
        mercately_client=mock_mercately,
        wava_client=None,
    )

    assert result["outcome"] == "wava_no_disponible"
    sent_text = mock_mercately.send_text.call_args[0][1]
    assert "pasarela" in sent_text.lower() or "no está disponible" in sent_text.lower()


# ---------------------------------------------------------------------------
# handle_message · confirmar_compra · contacto no encontrado
# ---------------------------------------------------------------------------

async def test_handle_confirmar_compra_no_contact() -> None:
    db = MagicMock()

    contacts_mock = MagicMock()
    contacts_mock.find_one = AsyncMock(return_value=None)
    events_mock = MagicMock()
    events_mock.insert_one = AsyncMock()

    def get_collection(name):
        if name == "contacts":
            return contacts_mock
        return events_mock

    db.__getitem__ = MagicMock(side_effect=get_collection)

    mock_mercately = AsyncMock()
    mock_mercately.enabled = True
    mock_mercately.send_text = AsyncMock(return_value={})

    mock_wava = AsyncMock(spec=WavaClient)
    mock_wava.enabled = True

    classification = ClassificationResult(
        intent="confirmar_compra", confidence=0.88, route_to="argos",
    )

    result = await handle_message(
        db,
        classification=classification,
        message_text="Quiero comprar",
        phone="573001234567",
        mercately_client=mock_mercately,
        wava_client=mock_wava,
    )

    assert result["outcome"] == "contacto_no_encontrado"


# ---------------------------------------------------------------------------
# handle_message · confirmar_compra · datos incompletos (sin cédula)
# ---------------------------------------------------------------------------

async def test_handle_confirmar_compra_missing_cedula() -> None:
    db = MagicMock()

    contacts_mock = MagicMock()
    contacts_mock.find_one = AsyncMock(return_value={
        "phone": "573001234567",
        "nombre_completo": "Juan Pérez",
        "email": "juan@test.com",
        "numero_documento": "",
        "tipo_documento": "CC",
    })
    events_mock = MagicMock()
    events_mock.insert_one = AsyncMock()
    wava_orders_mock = MagicMock()
    wava_orders_mock.update_one = AsyncMock()

    def get_collection(name):
        if name == "contacts":
            return contacts_mock
        if name == "wava_orders":
            return wava_orders_mock
        return events_mock

    db.__getitem__ = MagicMock(side_effect=get_collection)

    mock_mercately = AsyncMock()
    mock_mercately.enabled = True
    mock_mercately.send_text = AsyncMock(return_value={})

    mock_wava = AsyncMock(spec=WavaClient)
    mock_wava.enabled = True

    classification = ClassificationResult(
        intent="confirmar_compra", confidence=0.9, route_to="argos",
    )

    result = await handle_message(
        db,
        classification=classification,
        message_text="Lo quiero",
        phone="573001234567",
        mercately_client=mock_mercately,
        wava_client=mock_wava,
    )

    assert result["outcome"] == "datos_incompletos"
    sent_text = mock_mercately.send_text.call_args[0][1]
    assert "cédula" in sent_text


# ---------------------------------------------------------------------------
# handle_message · confirmar_compra · orden creada
# ---------------------------------------------------------------------------

async def test_handle_confirmar_compra_order_created() -> None:
    db = MagicMock()

    contacts_mock = MagicMock()
    contacts_mock.find_one = AsyncMock(return_value={
        "phone": "573001234567",
        "nombre_completo": "Juan Pérez",
        "email": "juan@test.com",
        "numero_documento": "1234567890",
        "tipo_documento": "CC",
    })
    events_mock = MagicMock()
    events_mock.insert_one = AsyncMock()
    wava_orders_mock = MagicMock()
    wava_orders_mock.update_one = AsyncMock(return_value=MagicMock(upserted_id="new_order"))

    def get_collection(name):
        if name == "contacts":
            return contacts_mock
        if name == "wava_orders":
            return wava_orders_mock
        if name == "argos_events":
            return events_mock
        return MagicMock(insert_one=AsyncMock())

    db.__getitem__ = MagicMock(side_effect=get_collection)

    mock_mercately = AsyncMock()
    mock_mercately.enabled = True
    mock_mercately.send_text = AsyncMock(return_value={})

    mock_wava = AsyncMock(spec=WavaClient)
    mock_wava.enabled = True
    mock_wava.create_order = AsyncMock(return_value=WavaOrder(
        order_id="ord_999",
        status="pending",
        amount=25000,
    ))

    classification = ClassificationResult(
        intent="confirmar_compra", confidence=0.92, route_to="argos",
    )

    result = await handle_message(
        db,
        classification=classification,
        message_text="Sí, lo quiero comprar",
        phone="573001234567",
        mercately_client=mock_mercately,
        wava_client=mock_wava,
    )

    assert result["outcome"] == "orden_creada"
    assert result["responded"] is True
    sent_text = mock_mercately.send_text.call_args[0][1]
    assert "Nequi" in sent_text

    mock_wava.create_order.assert_called_once()
    wava_orders_mock.update_one.assert_called_once()
    call_args = wava_orders_mock.update_one.call_args
    upsert_set = call_args[0][1]["$set"]
    assert upsert_set["wava_order_id"] == "ord_999"
    assert upsert_set["status"] == "pending"


# ---------------------------------------------------------------------------
# handle_message · confirmar_compra · wava error
# ---------------------------------------------------------------------------

async def test_handle_confirmar_compra_wava_error() -> None:
    db = MagicMock()

    contacts_mock = MagicMock()
    contacts_mock.find_one = AsyncMock(return_value={
        "phone": "573001234567",
        "nombre_completo": "María López",
        "email": "maria@test.com",
        "numero_documento": "9876543210",
        "tipo_documento": "CC",
    })
    events_mock = MagicMock()
    events_mock.insert_one = AsyncMock()

    def get_collection(name):
        if name == "contacts":
            return contacts_mock
        return events_mock

    db.__getitem__ = MagicMock(side_effect=get_collection)

    mock_mercately = AsyncMock()
    mock_mercately.enabled = True
    mock_mercately.send_text = AsyncMock(return_value={})

    mock_wava = AsyncMock(spec=WavaClient)
    mock_wava.enabled = True
    mock_wava.create_order = AsyncMock(side_effect=WavaError(500, "Internal Server Error"))

    classification = ClassificationResult(
        intent="confirmar_compra", confidence=0.9, route_to="argos",
    )

    result = await handle_message(
        db,
        classification=classification,
        message_text="Confirmo la compra",
        phone="573001234567",
        mercately_client=mock_mercately,
        wava_client=mock_wava,
    )

    assert result["outcome"] == "wava_error"


# ---------------------------------------------------------------------------
# _create_wava_order · persiste en wava_orders
# ---------------------------------------------------------------------------

async def test_create_wava_order_persists_correctly() -> None:
    db = MagicMock()
    wava_orders_mock = MagicMock()
    wava_orders_mock.update_one = AsyncMock(return_value=MagicMock(upserted_id="id1"))
    db.__getitem__ = MagicMock(return_value=wava_orders_mock)

    mock_wava = AsyncMock(spec=WavaClient)
    mock_wava.create_order = AsyncMock(return_value=WavaOrder(
        order_id="ord_persist",
        status="pending",
        amount=50000,
    ))

    contact = {
        "phone": "573009876543",
        "nombre_completo": "Carlos Gómez",
        "email": "carlos@test.com",
        "numero_documento": "5555555555",
        "tipo_documento": "CE",
    }

    response_text, outcome = await _create_wava_order(
        db,
        phone="573009876543",
        contact=contact,
        workspace_id="RODDOS",
        wava_client=mock_wava,
    )

    assert outcome == "orden_creada"
    assert "Nequi" in response_text

    call_args = mock_wava.create_order.call_args
    assert call_args.kwargs.get("gateway_id") == 1 or call_args[1].get("gateway_id") == 1
    shopper = call_args[1].get("shopper") or call_args.kwargs.get("shopper")
    assert shopper.first_name == "Carlos"
    assert shopper.id_type == 2  # CE


# ---------------------------------------------------------------------------
# confirmar_compra is in intent classifier
# ---------------------------------------------------------------------------

def test_confirmar_compra_in_argos_intents() -> None:
    from argos.agents.whatsapp.intent_classifier import ARGOS_INTENTS
    assert "confirmar_compra" in ARGOS_INTENTS
