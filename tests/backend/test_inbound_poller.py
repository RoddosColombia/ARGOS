"""Tests de InboundPoller (Build 3.1 · Capa 1).

Valida: extracción de mensajes inbound, filtrado por last_seen,
skip sin mercately, polling flow con mocks.

Refs: phase_3/build_3.1 · ROG-W1 (opt-in) · ROG-A3 (workspace_id)
"""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from argos.agents.whatsapp.inbound_poller import (
    _extract_inbound_messages,
    poll_inbound,
)

# ---------------------------------------------------------------------------
# _extract_inbound_messages
# ---------------------------------------------------------------------------

class TestExtractInboundMessages:
    def test_empty_response(self) -> None:
        assert _extract_inbound_messages({}, None) == []

    def test_filters_outbound(self) -> None:
        response = {
            "data": [{
                "messages": [
                    {"direction": "out", "body": "hi", "created_at": "2026-05-14T10:00:00Z"},
                    {"direction": "in", "body": "hello", "created_at": "2026-05-14T10:01:00Z"},
                ],
            }],
        }
        msgs = _extract_inbound_messages(response, None)
        assert len(msgs) == 1
        assert msgs[0]["body"] == "hello"

    def test_filters_by_last_seen(self) -> None:
        cutoff = datetime(2026, 5, 14, 10, 0, 0, tzinfo=UTC)
        response = {
            "data": [{
                "messages": [
                    {"direction": "in", "body": "old", "created_at": "2026-05-14T09:00:00Z"},
                    {"direction": "in", "body": "new", "created_at": "2026-05-14T11:00:00Z"},
                ],
            }],
        }
        msgs = _extract_inbound_messages(response, cutoff)
        assert len(msgs) == 1
        assert msgs[0]["body"] == "new"

    def test_sorts_by_time(self) -> None:
        response = {
            "data": [{
                "messages": [
                    {"direction": "in", "body": "second", "created_at": "2026-05-14T12:00:00Z"},
                    {"direction": "in", "body": "first", "created_at": "2026-05-14T10:00:00Z"},
                ],
            }],
        }
        msgs = _extract_inbound_messages(response, None)
        assert msgs[0]["body"] == "first"
        assert msgs[1]["body"] == "second"

    def test_skips_messages_without_timestamp(self) -> None:
        response = {
            "data": [{"messages": [{"direction": "in", "body": "no time"}]}],
        }
        assert _extract_inbound_messages(response, None) == []

    def test_conversations_key_fallback(self) -> None:
        response = {
            "conversations": [{
                "messages": [
                    {"direction": "in", "body": "hi", "created_at": "2026-05-14T10:00:00Z"},
                ],
            }],
        }
        msgs = _extract_inbound_messages(response, None)
        assert len(msgs) == 1


# ---------------------------------------------------------------------------
# poll_inbound · skip sin mercately
# ---------------------------------------------------------------------------

async def test_poll_skips_when_mercately_disabled() -> None:
    from argos.partners.mercately.client import MercatelyClient
    client = MercatelyClient(api_key="")
    db = MagicMock()
    stats = await poll_inbound(db, mercately_client=client)
    assert stats["phones_checked"] == 0


# ---------------------------------------------------------------------------
# poll_inbound · flujo completo con mocks
# ---------------------------------------------------------------------------

async def test_poll_full_flow() -> None:
    from argos.agents.whatsapp.intent_classifier import ClassificationResult
    from argos.partners.mercately.client import MercatelyClient

    mock_db = MagicMock()

    contacts_cursor = AsyncMock()
    contacts_cursor.to_list = AsyncMock(return_value=[
        {"phone": "573001234567"},
    ])
    mock_db.__getitem__ = MagicMock(return_value=MagicMock(
        find=MagicMock(return_value=contacts_cursor),
        find_one=AsyncMock(return_value=None),
        update_one=AsyncMock(),
    ))

    mock_client = AsyncMock(spec=MercatelyClient)
    mock_client.enabled = True
    mock_client.get_customer_messages = AsyncMock(return_value={
        "data": [{
            "messages": [{
                "direction": "in",
                "body": "Necesito un filtro de aceite",
                "created_at": "2026-05-14T10:00:00Z",
            }],
        }],
    })

    mock_result = ClassificationResult(
        intent="cotizar_repuesto",
        confidence=0.92,
        route_to="argos",
    )

    with patch(
        "argos.agents.whatsapp.inbound_poller.classify_intent",
        new_callable=AsyncMock,
        return_value=mock_result,
    ):
        stats = await poll_inbound(
            mock_db,
            mercately_client=mock_client,
            anthropic_api_key="test-key",
        )

    assert stats["phones_checked"] == 1
    assert stats["messages_found"] == 1
    assert stats["classified"] == 1
    assert stats["forwarded_sismo"] == 0


async def test_poll_forwards_sismo_intent() -> None:
    from argos.agents.whatsapp.intent_classifier import ClassificationResult
    from argos.partners.mercately.client import MercatelyClient

    mock_db = MagicMock()

    contacts_cursor = AsyncMock()
    contacts_cursor.to_list = AsyncMock(return_value=[
        {"phone": "573009999999"},
    ])
    mock_db.__getitem__ = MagicMock(return_value=MagicMock(
        find=MagicMock(return_value=contacts_cursor),
        find_one=AsyncMock(return_value=None),
        update_one=AsyncMock(),
    ))

    mock_client = AsyncMock(spec=MercatelyClient)
    mock_client.enabled = True
    mock_client.get_customer_messages = AsyncMock(return_value={
        "data": [{
            "messages": [{
                "direction": "in",
                "body": "Quiero pagar mi cuota",
                "created_at": "2026-05-14T10:00:00Z",
            }],
        }],
    })

    mock_result = ClassificationResult(
        intent="pago_cuota",
        confidence=0.88,
        route_to="sismo",
    )

    with (
        patch(
            "argos.agents.whatsapp.inbound_poller.classify_intent",
            new_callable=AsyncMock,
            return_value=mock_result,
        ),
        patch(
            "argos.agents.whatsapp.inbound_poller.forward_to_sismo",
            new_callable=AsyncMock,
            return_value={"forwarded": True},
        ) as mock_forward,
    ):
        stats = await poll_inbound(
            mock_db,
            mercately_client=mock_client,
            anthropic_api_key="test-key",
            sismo_webhook_url="https://sismo.roddos.com/webhook",
        )

    assert stats["forwarded_sismo"] == 1
    mock_forward.assert_called_once()
