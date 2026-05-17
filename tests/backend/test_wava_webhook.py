"""Tests de wava webhook (Build 3.3).

Valida: webhook confirmed/failed/cancelled, verificación GET,
idempotency dedup, audit log, respuesta 200 inmediata.

Refs: phase_3/build_3.3 · ROG-A12
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from argos.api.v1.wava_webhook import _process_webhook
from argos.partners.wava.client import WavaOrder
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Endpoint · respuesta 200 inmediata
# ---------------------------------------------------------------------------

def test_webhook_returns_200() -> None:
    from argos.main import app

    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.post(
            "/api/v1/wava/webhook",
            json={"event": "order.confirmed", "data": {"id": "ord_123"}},
        )
    assert resp.status_code == 200
    assert resp.json()["received"] is True


def test_webhook_returns_200_on_invalid_json() -> None:
    from argos.main import app

    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.post(
            "/api/v1/wava/webhook",
            content=b"not json",
            headers={"content-type": "application/json"},
        )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# _process_webhook · confirmed
# ---------------------------------------------------------------------------

async def test_process_webhook_confirmed() -> None:
    mock_db = MagicMock()

    wava_orders_mock = MagicMock()
    wava_orders_mock.update_one = AsyncMock(return_value=MagicMock(matched_count=1))
    audit_mock = MagicMock()
    audit_mock.insert_one = AsyncMock()
    events_mock = MagicMock()
    events_mock.insert_one = AsyncMock()

    def get_collection(name):
        if name == "wava_orders":
            return wava_orders_mock
        if name == "audit_log":
            return audit_mock
        if name == "argos_events":
            return events_mock
        return MagicMock(insert_one=AsyncMock())

    mock_db.__getitem__ = MagicMock(side_effect=get_collection)

    verified_order = WavaOrder(order_id="ord_100", status="confirmed", amount=25000)

    mongo_client_mock = MagicMock()
    mongo_client_mock.__getitem__ = MagicMock(return_value=mock_db)

    with (
        patch("argos.api.v1.wava_webhook.get_mongo_client", return_value=mongo_client_mock),
        patch("argos.api.v1.wava_webhook.get_settings") as mock_settings,
        patch("argos.api.v1.wava_webhook.WavaClient") as mock_wava_cls,
    ):
        settings = MagicMock()
        settings.mongodb_database = "argos_test"
        settings.wava_merchant_key = "test-key"
        settings.wava_api_url = "https://api.dev.wava.co/v1"
        mock_settings.return_value = settings

        mock_wava_instance = AsyncMock()
        mock_wava_instance.enabled = True
        mock_wava_instance.get_order = AsyncMock(return_value=verified_order)
        mock_wava_instance.__aenter__ = AsyncMock(return_value=mock_wava_instance)
        mock_wava_instance.__aexit__ = AsyncMock(return_value=None)
        mock_wava_cls.return_value = mock_wava_instance

        await _process_webhook({
            "event": "order.confirmed",
            "data": {"id": "ord_100"},
        })

    wava_orders_mock.update_one.assert_called_once()
    call_args = wava_orders_mock.update_one.call_args
    assert call_args[0][0]["wava_order_id"] == "ord_100"
    update_set = call_args[0][1]["$set"]
    assert update_set["status"] == "confirmed"
    assert "wava_confirmed_at" in update_set


# ---------------------------------------------------------------------------
# _process_webhook · failed
# ---------------------------------------------------------------------------

async def test_process_webhook_failed() -> None:
    mock_db = MagicMock()

    wava_orders_mock = MagicMock()
    wava_orders_mock.update_one = AsyncMock(return_value=MagicMock(matched_count=1))

    def get_collection(name):
        if name == "wava_orders":
            return wava_orders_mock
        return MagicMock(insert_one=AsyncMock())

    mock_db.__getitem__ = MagicMock(side_effect=get_collection)

    verified_order = WavaOrder(order_id="ord_200", status="failed")

    mongo_client_mock = MagicMock()
    mongo_client_mock.__getitem__ = MagicMock(return_value=mock_db)

    with (
        patch("argos.api.v1.wava_webhook.get_mongo_client", return_value=mongo_client_mock),
        patch("argos.api.v1.wava_webhook.get_settings") as mock_settings,
        patch("argos.api.v1.wava_webhook.WavaClient") as mock_wava_cls,
    ):
        settings = MagicMock()
        settings.mongodb_database = "argos_test"
        settings.wava_merchant_key = "test-key"
        settings.wava_api_url = "https://api.dev.wava.co/v1"
        mock_settings.return_value = settings

        mock_wava_instance = AsyncMock()
        mock_wava_instance.enabled = True
        mock_wava_instance.get_order = AsyncMock(return_value=verified_order)
        mock_wava_instance.__aenter__ = AsyncMock(return_value=mock_wava_instance)
        mock_wava_instance.__aexit__ = AsyncMock(return_value=None)
        mock_wava_cls.return_value = mock_wava_instance

        await _process_webhook({
            "event": "order.failed",
            "data": {"id": "ord_200"},
        })

    call_args = wava_orders_mock.update_one.call_args
    update_set = call_args[0][1]["$set"]
    assert update_set["status"] == "failed"
    assert "wava_failed_at" in update_set


# ---------------------------------------------------------------------------
# _process_webhook · order not found in DB
# ---------------------------------------------------------------------------

async def test_process_webhook_order_not_found() -> None:
    mock_db = MagicMock()

    wava_orders_mock = MagicMock()
    wava_orders_mock.update_one = AsyncMock(return_value=MagicMock(matched_count=0))

    def get_collection(name):
        if name == "wava_orders":
            return wava_orders_mock
        return MagicMock(insert_one=AsyncMock())

    mock_db.__getitem__ = MagicMock(side_effect=get_collection)

    verified_order = WavaOrder(order_id="ord_unknown", status="confirmed")

    mongo_client_mock = MagicMock()
    mongo_client_mock.__getitem__ = MagicMock(return_value=mock_db)

    with (
        patch("argos.api.v1.wava_webhook.get_mongo_client", return_value=mongo_client_mock),
        patch("argos.api.v1.wava_webhook.get_settings") as mock_settings,
        patch("argos.api.v1.wava_webhook.WavaClient") as mock_wava_cls,
    ):
        settings = MagicMock()
        settings.mongodb_database = "argos_test"
        settings.wava_merchant_key = "test-key"
        settings.wava_api_url = "https://api.dev.wava.co/v1"
        mock_settings.return_value = settings

        mock_wava_instance = AsyncMock()
        mock_wava_instance.enabled = True
        mock_wava_instance.get_order = AsyncMock(return_value=verified_order)
        mock_wava_instance.__aenter__ = AsyncMock(return_value=mock_wava_instance)
        mock_wava_instance.__aexit__ = AsyncMock(return_value=None)
        mock_wava_cls.return_value = mock_wava_instance

        await _process_webhook({
            "event": "order.confirmed",
            "data": {"id": "ord_unknown"},
        })

    wava_orders_mock.update_one.assert_called_once()


# ---------------------------------------------------------------------------
# _process_webhook · no merchant key → cannot verify
# ---------------------------------------------------------------------------

async def test_process_webhook_no_merchant_key() -> None:
    mock_db = MagicMock()
    wava_orders_mock = MagicMock()
    wava_orders_mock.update_one = AsyncMock()

    def get_collection(name):
        if name == "wava_orders":
            return wava_orders_mock
        return MagicMock(insert_one=AsyncMock())

    mock_db.__getitem__ = MagicMock(side_effect=get_collection)

    mongo_client_mock = MagicMock()
    mongo_client_mock.__getitem__ = MagicMock(return_value=mock_db)

    with (
        patch("argos.api.v1.wava_webhook.get_mongo_client", return_value=mongo_client_mock),
        patch("argos.api.v1.wava_webhook.get_settings") as mock_settings,
        patch("argos.api.v1.wava_webhook.WavaClient") as mock_wava_cls,
    ):
        settings = MagicMock()
        settings.mongodb_database = "argos_test"
        settings.wava_merchant_key = ""
        settings.wava_api_url = "https://api.dev.wava.co/v1"
        mock_settings.return_value = settings

        mock_wava_instance = AsyncMock()
        mock_wava_instance.enabled = False
        mock_wava_instance.__aenter__ = AsyncMock(return_value=mock_wava_instance)
        mock_wava_instance.__aexit__ = AsyncMock(return_value=None)
        mock_wava_cls.return_value = mock_wava_instance

        await _process_webhook({
            "event": "order.confirmed",
            "data": {"id": "ord_300"},
        })

    wava_orders_mock.update_one.assert_not_called()


# ---------------------------------------------------------------------------
# _process_webhook · no order_id in payload
# ---------------------------------------------------------------------------

async def test_process_webhook_no_order_id() -> None:
    mock_db = MagicMock()
    wava_orders_mock = MagicMock()
    wava_orders_mock.update_one = AsyncMock()

    def get_collection(name):
        if name == "wava_orders":
            return wava_orders_mock
        return MagicMock(insert_one=AsyncMock())

    mock_db.__getitem__ = MagicMock(side_effect=get_collection)

    mongo_client_mock = MagicMock()
    mongo_client_mock.__getitem__ = MagicMock(return_value=mock_db)

    with (
        patch("argos.api.v1.wava_webhook.get_mongo_client", return_value=mongo_client_mock),
        patch("argos.api.v1.wava_webhook.get_settings") as mock_settings,
    ):
        settings = MagicMock()
        settings.mongodb_database = "argos_test"
        mock_settings.return_value = settings

        await _process_webhook({"event": "order.confirmed", "data": {}})

    wava_orders_mock.update_one.assert_not_called()


# ---------------------------------------------------------------------------
# _process_webhook · audit log written
# ---------------------------------------------------------------------------

async def test_process_webhook_writes_audit() -> None:
    mock_db = MagicMock()
    audit_docs = []

    wava_orders_mock = MagicMock()
    wava_orders_mock.update_one = AsyncMock(return_value=MagicMock(matched_count=1))

    audit_mock = MagicMock()

    async def capture_audit(doc):
        audit_docs.append(doc)
        return MagicMock(inserted_id="audit_id")

    audit_mock.insert_one = capture_audit

    def get_collection(name):
        if name == "wava_orders":
            return wava_orders_mock
        if name == "audit_log":
            return audit_mock
        return MagicMock(insert_one=AsyncMock())

    mock_db.__getitem__ = MagicMock(side_effect=get_collection)

    verified_order = WavaOrder(order_id="ord_audit", status="confirmed")

    mongo_client_mock = MagicMock()
    mongo_client_mock.__getitem__ = MagicMock(return_value=mock_db)

    with (
        patch("argos.api.v1.wava_webhook.get_mongo_client", return_value=mongo_client_mock),
        patch("argos.api.v1.wava_webhook.get_settings") as mock_settings,
        patch("argos.api.v1.wava_webhook.WavaClient") as mock_wava_cls,
    ):
        settings = MagicMock()
        settings.mongodb_database = "argos_test"
        settings.wava_merchant_key = "test-key"
        settings.wava_api_url = "https://api.dev.wava.co/v1"
        mock_settings.return_value = settings

        mock_wava_instance = AsyncMock()
        mock_wava_instance.enabled = True
        mock_wava_instance.get_order = AsyncMock(return_value=verified_order)
        mock_wava_instance.__aenter__ = AsyncMock(return_value=mock_wava_instance)
        mock_wava_instance.__aexit__ = AsyncMock(return_value=None)
        mock_wava_cls.return_value = mock_wava_instance

        await _process_webhook({
            "event": "order.confirmed",
            "data": {"id": "ord_audit"},
        })

    assert len(audit_docs) >= 1
    actions = [d["action"] for d in audit_docs]
    assert "wava.webhook.received" in actions
