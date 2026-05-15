"""Tests de conversation_handler (Build 3.2).

Valida: dispatch por intent, respuesta a cotización con/sin producto,
onboarding crea contacto, safety switch off, general response, event emission.

Refs: phase_3/build_3.2 · ROG-W6 · ROG-W7
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from argos.agents.whatsapp.conversation_handler import (
    _format_product_response,
    handle_message,
)
from argos.agents.whatsapp.intent_classifier import ClassificationResult

# ---------------------------------------------------------------------------
# _format_product_response
# ---------------------------------------------------------------------------

def test_format_with_products() -> None:
    products = [
        {"nombre": "Filtro Aceite NS200", "precio": 25000, "stock": 8, "compatible_motos": ["Pulsar NS200"]},
    ]
    text = _format_product_response(products, "filtro aceite")
    assert "Filtro Aceite NS200" in text
    assert "$25,000" in text
    assert "8 uds" in text


def test_format_empty_products() -> None:
    text = _format_product_response([], "xyz repuesto raro")
    assert "No encontramos" in text
    assert "xyz repuesto raro" in text


def test_format_out_of_stock() -> None:
    products = [
        {"nombre": "Kit Cadena", "precio": 120000, "stock": 0, "compatible_motos": []},
    ]
    text = _format_product_response(products, "kit cadena")
    assert "agotado" in text


# ---------------------------------------------------------------------------
# handle_message · cotizar_repuesto con resultado
# ---------------------------------------------------------------------------

async def test_handle_cotizar_repuesto_with_results() -> None:
    db = MagicMock()
    db.__getitem__ = MagicMock(return_value=MagicMock(
        insert_one=AsyncMock(),
    ))

    mock_client = AsyncMock()
    mock_client.enabled = True
    mock_client.send_text = AsyncMock(return_value={"status": "sent"})

    classification = ClassificationResult(
        intent="cotizar_repuesto",
        confidence=0.92,
        route_to="argos",
    )

    products = [
        {"nombre": "Filtro Aceite", "precio": 25000, "stock": 5, "stock_source": "sismo",
         "source": "meli", "categoria": "", "compatible_motos": [], "permalink": ""},
    ]

    with patch(
        "argos.agents.whatsapp.conversation_handler.search_catalog",
        new_callable=AsyncMock,
        return_value=products,
    ):
        result = await handle_message(
            db,
            classification=classification,
            message_text="filtro aceite pulsar",
            phone="573001234567",
            mercately_client=mock_client,
        )

    assert result["responded"] is True
    assert result["outcome"] == "cotizado"
    assert result["intent"] == "cotizar_repuesto"
    mock_client.send_text.assert_called_once()
    sent_text = mock_client.send_text.call_args[0][1]
    assert "Filtro Aceite" in sent_text


# ---------------------------------------------------------------------------
# handle_message · cotizar_repuesto sin resultado
# ---------------------------------------------------------------------------

async def test_handle_cotizar_repuesto_no_results() -> None:
    db = MagicMock()
    db.__getitem__ = MagicMock(return_value=MagicMock(insert_one=AsyncMock()))

    mock_client = AsyncMock()
    mock_client.enabled = True
    mock_client.send_text = AsyncMock(return_value={})

    classification = ClassificationResult(
        intent="cotizar_repuesto", confidence=0.85, route_to="argos",
    )

    with patch(
        "argos.agents.whatsapp.conversation_handler.search_catalog",
        new_callable=AsyncMock,
        return_value=[],
    ):
        result = await handle_message(
            db,
            classification=classification,
            message_text="repuesto raro inexistente",
            phone="573001234567",
            mercately_client=mock_client,
        )

    assert result["outcome"] == "sin_resultado"
    sent_text = mock_client.send_text.call_args[0][1]
    assert "No encontramos" in sent_text


# ---------------------------------------------------------------------------
# handle_message · consulta_general
# ---------------------------------------------------------------------------

async def test_handle_consulta_general_without_api_key() -> None:
    db = MagicMock()
    db.__getitem__ = MagicMock(return_value=MagicMock(insert_one=AsyncMock()))

    mock_client = AsyncMock()
    mock_client.enabled = True
    mock_client.send_text = AsyncMock(return_value={})

    classification = ClassificationResult(
        intent="consulta_general", confidence=0.8, route_to="argos",
    )

    result = await handle_message(
        db,
        classification=classification,
        message_text="Hola buenos días",
        phone="573001234567",
        mercately_client=mock_client,
        anthropic_api_key="",
    )

    assert result["outcome"] == "respondido_general"
    sent_text = mock_client.send_text.call_args[0][1]
    assert "RODDOS" in sent_text


# ---------------------------------------------------------------------------
# handle_message · onboarding crea contacto
# ---------------------------------------------------------------------------

async def test_handle_onboarding_creates_contact() -> None:
    db = MagicMock()

    contacts_mock = MagicMock()
    contacts_mock.update_one = AsyncMock(return_value=MagicMock(upserted_id="new_id"))
    events_mock = MagicMock()
    events_mock.insert_one = AsyncMock()

    def get_collection(name):
        if name == "contacts":
            return contacts_mock
        return events_mock

    db.__getitem__ = MagicMock(side_effect=get_collection)

    mock_client = AsyncMock()
    mock_client.enabled = True
    mock_client.send_text = AsyncMock(return_value={})

    classification = ClassificationResult(
        intent="onboarding", confidence=0.9, route_to="argos",
    )

    result = await handle_message(
        db,
        classification=classification,
        message_text="Quiero registrarme",
        phone="573001234567",
        mercately_client=mock_client,
    )

    assert result["outcome"] == "onboarding_nuevo"
    contacts_mock.update_one.assert_called_once()
    sent_text = mock_client.send_text.call_args[0][1]
    assert "Bienvenido" in sent_text


# ---------------------------------------------------------------------------
# handle_message · cotizar_moto placeholder
# ---------------------------------------------------------------------------

async def test_handle_cotizar_moto_placeholder() -> None:
    db = MagicMock()
    db.__getitem__ = MagicMock(return_value=MagicMock(insert_one=AsyncMock()))

    mock_client = AsyncMock()
    mock_client.enabled = True
    mock_client.send_text = AsyncMock(return_value={})

    classification = ClassificationResult(
        intent="cotizar_moto", confidence=0.88, route_to="argos",
    )

    result = await handle_message(
        db,
        classification=classification,
        message_text="Cuánto vale una Pulsar NS200?",
        phone="573001234567",
        mercately_client=mock_client,
    )

    assert result["outcome"] == "placeholder_moto"


# ---------------------------------------------------------------------------
# handle_message · consulta_credito placeholder
# ---------------------------------------------------------------------------

async def test_handle_consulta_credito_placeholder() -> None:
    db = MagicMock()
    db.__getitem__ = MagicMock(return_value=MagicMock(insert_one=AsyncMock()))

    mock_client = AsyncMock()
    mock_client.enabled = True
    mock_client.send_text = AsyncMock(return_value={})

    classification = ClassificationResult(
        intent="consulta_credito", confidence=0.85, route_to="argos",
    )

    result = await handle_message(
        db,
        classification=classification,
        message_text="Me interesa financiación",
        phone="573001234567",
        mercately_client=mock_client,
    )

    assert result["outcome"] == "placeholder_credito"
    sent_text = mock_client.send_text.call_args[0][1]
    assert "financiación" in sent_text or "crédito" in sent_text


# ---------------------------------------------------------------------------
# handle_message · mercately disabled no envía
# ---------------------------------------------------------------------------

async def test_handle_mercately_disabled_no_send() -> None:
    db = MagicMock()
    db.__getitem__ = MagicMock(return_value=MagicMock(insert_one=AsyncMock()))

    mock_client = AsyncMock()
    mock_client.enabled = False

    classification = ClassificationResult(
        intent="consulta_general", confidence=0.8, route_to="argos",
    )

    result = await handle_message(
        db,
        classification=classification,
        message_text="hola",
        phone="573001234567",
        mercately_client=mock_client,
    )

    assert result["responded"] is False
    mock_client.send_text.assert_not_called()


# ---------------------------------------------------------------------------
# Safety switch: whatsapp_reply_enabled=False en poller no llama handler
# ---------------------------------------------------------------------------

async def test_poller_does_not_respond_when_reply_disabled() -> None:
    """Verifica que poll_inbound NO llama handle_message cuando reply_enabled=False."""
    from argos.agents.whatsapp.inbound_poller import poll_inbound
    from argos.partners.mercately.client import MercatelyClient

    mock_db = MagicMock()

    contacts_cursor = AsyncMock()
    contacts_cursor.to_list = AsyncMock(return_value=[{"phone": "573001234567"}])
    mock_db.__getitem__ = MagicMock(return_value=MagicMock(
        find=MagicMock(return_value=contacts_cursor),
        find_one=AsyncMock(return_value=None),
        update_one=AsyncMock(),
    ))

    mock_client = AsyncMock(spec=MercatelyClient)
    mock_client.enabled = True
    mock_client.get_customer_messages = AsyncMock(return_value={
        "data": [{"messages": [{
            "direction": "in", "body": "hola", "created_at": "2026-05-15T10:00:00Z",
        }]}],
    })

    mock_classification = ClassificationResult(
        intent="consulta_general", confidence=0.8, route_to="argos",
    )

    with (
        patch(
            "argos.agents.whatsapp.inbound_poller.classify_intent",
            new_callable=AsyncMock,
            return_value=mock_classification,
        ),
        patch(
            "argos.agents.whatsapp.inbound_poller.handle_message",
            new_callable=AsyncMock,
        ) as mock_handle,
    ):
        stats = await poll_inbound(
            mock_db,
            mercately_client=mock_client,
            anthropic_api_key="test-key",
            whatsapp_reply_enabled=False,
        )

    mock_handle.assert_not_called()
    assert stats["responded_argos"] == 0
    assert stats["classified"] == 1


async def test_poller_responds_when_reply_enabled() -> None:
    """Verifica que poll_inbound SÍ llama handle_message cuando reply_enabled=True."""
    from argos.agents.whatsapp.inbound_poller import poll_inbound
    from argos.partners.mercately.client import MercatelyClient

    mock_db = MagicMock()

    contacts_cursor = AsyncMock()
    contacts_cursor.to_list = AsyncMock(return_value=[{"phone": "573001234567"}])
    mock_db.__getitem__ = MagicMock(return_value=MagicMock(
        find=MagicMock(return_value=contacts_cursor),
        find_one=AsyncMock(return_value=None),
        update_one=AsyncMock(),
    ))

    mock_client = AsyncMock(spec=MercatelyClient)
    mock_client.enabled = True
    mock_client.get_customer_messages = AsyncMock(return_value={
        "data": [{"messages": [{
            "direction": "in", "body": "filtro aceite", "created_at": "2026-05-15T10:00:00Z",
        }]}],
    })

    mock_classification = ClassificationResult(
        intent="cotizar_repuesto", confidence=0.9, route_to="argos",
    )

    with (
        patch(
            "argos.agents.whatsapp.inbound_poller.classify_intent",
            new_callable=AsyncMock,
            return_value=mock_classification,
        ),
        patch(
            "argos.agents.whatsapp.inbound_poller.handle_message",
            new_callable=AsyncMock,
            return_value={"responded": True, "intent": "cotizar_repuesto", "outcome": "cotizado"},
        ) as mock_handle,
    ):
        stats = await poll_inbound(
            mock_db,
            mercately_client=mock_client,
            anthropic_api_key="test-key",
            whatsapp_reply_enabled=True,
        )

    mock_handle.assert_called_once()
    assert stats["responded_argos"] == 1
