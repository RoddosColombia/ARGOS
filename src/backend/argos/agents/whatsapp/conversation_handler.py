"""Conversation handler · responde mensajes inbound ARGOS (Build 3.2 + 3.3).

Recibe ClassificationResult + mensaje + phone y despacha la respuesta
según el intent. Envía respuestas vía MercatelyClient.send_text.

Intents manejados:
- cotizar_repuesto: busca catálogo + stock → responde con precio/disponibilidad
- consulta_general: Haiku genera respuesta amigable genérica
- cotizar_moto: placeholder (F2 es Capa 3)
- onboarding: registra contacto con opt-in
- consulta_credito: placeholder (F3 es Capa 3)
- confirmar_compra: crea orden Wava (Nequi) + persiste en wava_orders (Build 3.3)

Cada respuesta emite evento whatsapp.message.responded al bus (ROG-W7).

Refs: phase_3/build_3.2 · ROG-W6 · ROG-W7
"""
from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from argos.agents.whatsapp.catalog_search import search_catalog
from argos.agents.whatsapp.intent_classifier import ClassificationResult
from argos.db import collections as col
from argos.partners.mercately.client import MercatelyClient
from argos.partners.wava.client import WavaClient, WavaError, WavaShopper

logger = logging.getLogger("argos.agents.whatsapp.conversation_handler")

GENERAL_SYSTEM_PROMPT = """\
Eres el asistente de RODDOS, tienda especializada en repuestos para motos \
en Colombia. Responde de forma amigable, concisa y profesional.

Información de RODDOS:
- Especialistas en repuestos para motos en Bogotá
- Horarios: Lunes a Sábado 8am-6pm
- WhatsApp: este mismo canal
- Financiación disponible para clientes con historial

Responde en máximo 3 oraciones. No inventes precios ni disponibilidad.
Si el cliente pregunta por algo específico, sugiérele que nos diga el \
repuesto exacto y la referencia de su moto para cotizar.
"""


def _format_product_response(products: list[dict[str, Any]], query: str) -> str:
    if not products:
        return (
            f"No encontramos resultados para \"{query[:50]}\" en nuestro catálogo. "
            "¿Podrías decirnos el nombre exacto del repuesto y la referencia de tu moto? "
            "Así te ayudamos mejor."
        )

    lines = [f"Encontramos {len(products)} resultado(s) para tu búsqueda:\n"]
    for i, p in enumerate(products[:3], 1):
        nombre = p["nombre"][:80]
        precio = p.get("precio", 0)
        stock = p.get("stock", 0)
        stock_txt = f"{stock} uds" if stock > 0 else "agotado"
        lines.append(f"{i}. {nombre}")
        lines.append(f"   💰 ${precio:,.0f} COP · 📦 {stock_txt}")
        motos = p.get("compatible_motos", [])
        if motos:
            lines.append(f"   🏍️ {', '.join(motos[:3])}")

    lines.append("\n¿Te interesa alguno? Escríbenos el número para más detalles.")
    return "\n".join(lines)


def _format_moto_placeholder() -> str:
    return (
        "¡Gracias por tu interés en nuestras motos! 🏍️\n"
        "Estamos preparando nuestro catálogo de motos para WhatsApp. "
        "Por ahora, puedes visitarnos en tienda o escribirnos con la referencia "
        "que te interesa y te cotizamos directamente."
    )


def _format_credit_placeholder() -> str:
    return (
        "¡Claro! En RODDOS ofrecemos financiación para repuestos y motos. 💳\n"
        "Para darte información sobre crédito necesitamos:\n"
        "1. Tu nombre completo\n"
        "2. Número de cédula\n"
        "3. El producto que te interesa\n\n"
        "Un asesor se comunicará contigo pronto."
    )


def _format_onboarding() -> str:
    return (
        "¡Bienvenido a RODDOS! 🎉\n"
        "Te hemos registrado en nuestro sistema. "
        "Ahora puedes:\n"
        "• Cotizar repuestos directamente por aquí\n"
        "• Recibir alertas de ofertas\n"
        "• Consultar disponibilidad de productos\n\n"
        "¿En qué podemos ayudarte hoy?"
    )


async def _generate_general_response(
    message_text: str,
    anthropic_api_key: str,
) -> str:
    """Genera respuesta genérica con Haiku."""
    if not anthropic_api_key:
        return (
            "¡Hola! Somos RODDOS, especialistas en repuestos para motos en Bogotá. "
            "¿En qué podemos ayudarte? Puedes preguntarnos por precio y disponibilidad "
            "de cualquier repuesto."
        )

    import anthropic

    client = anthropic.AsyncAnthropic(api_key=anthropic_api_key)
    try:
        resp = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            system=GENERAL_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": message_text[:1000]}],
        )
        return resp.content[0].text.strip() if resp.content else ""
    except Exception:  # noqa: BLE001
        logger.exception("general_response_generation_failed")
        return (
            "¡Hola! Somos RODDOS, especialistas en repuestos para motos en Bogotá. "
            "¿En qué podemos ayudarte?"
        )


async def _register_contact(
    db: AsyncIOMotorDatabase,
    phone: str,
    workspace_id: str,
) -> bool:
    """Registra contacto con opt-in si no existe. Retorna True si fue creado."""
    now = datetime.now(tz=UTC)
    result = await db[col.CONTACTS].update_one(
        {"workspace_id": workspace_id, "phone": phone},
        {
            "$set": {
                "opt_in_whatsapp": True,
                "updated_at": now,
            },
            "$setOnInsert": {
                "workspace_id": workspace_id,
                "phone": phone,
                "created_at": now,
                "opt_in_marketing": {
                    "status": "opted_in",
                    "captured_at": now,
                    "channel": "whatsapp_inbound",
                    "consent_text_version": "auto_onboarding_v1",
                    "captured_by": "whatsapp_agent",
                    "history": [{
                        "status": "opted_in",
                        "at": now,
                        "channel": "whatsapp_inbound",
                        "captured_by": "whatsapp_agent",
                    }],
                },
            },
        },
        upsert=True,
    )
    return result.upserted_id is not None


async def _emit_response_event(
    db: AsyncIOMotorDatabase,
    *,
    phone: str,
    intent: str,
    outcome: str,
    workspace_id: str,
    products_found: int = 0,
) -> None:
    from argos.db.events import publish_event
    try:
        await publish_event(
            db,
            event_type="whatsapp.message.responded",
            workspace_id=workspace_id,
            producer="conversation_handler",
            payload={
                "phone_last4": phone[-4:] if phone else "",
                "intent": intent,
                "outcome": outcome,
                "products_found": products_found,
            },
        )
    except Exception:  # noqa: BLE001
        logger.exception("response_event_publish_failed")


async def _get_contact(
    db: AsyncIOMotorDatabase,
    phone: str,
    workspace_id: str,
) -> dict[str, Any] | None:
    """Lee datos del contacto para crear orden Wava."""
    return await db[col.CONTACTS].find_one(
        {"workspace_id": workspace_id, "phone": phone},
        {
            "phone": 1,
            "nombre_completo": 1,
            "email": 1,
            "numero_documento": 1,
            "tipo_documento": 1,
            "_id": 0,
        },
    )


def _doc_type_to_wava_id(tipo: str) -> int:
    mapping = {"CC": 1, "CE": 2, "TI": 3}
    return mapping.get(tipo, 1)


async def _create_wava_order(
    db: AsyncIOMotorDatabase,
    *,
    phone: str,
    contact: dict[str, Any],
    workspace_id: str,
    wava_client: WavaClient,
) -> tuple[str, str]:
    """Crea orden Wava Nequi para la última cotización del contacto.

    Retorna (response_text, outcome).
    """
    nombre = contact.get("nombre_completo", "")
    parts = nombre.split(" ", 1) if nombre else ["Cliente", ""]
    first_name = parts[0] or "Cliente"
    last_name = parts[1] if len(parts) > 1 else ""
    email = contact.get("email", "")
    cedula = contact.get("numero_documento", "")
    tipo_doc = contact.get("tipo_documento", "CC")

    if not cedula:
        return (
            "Para procesar tu compra necesitamos tu número de cédula. "
            "¿Podrías compartirlo por favor?",
            "datos_incompletos",
        )

    phone_e164 = f"+{phone}" if not phone.startswith("+") else phone

    shopper = WavaShopper(
        first_name=first_name,
        last_name=last_name,
        email=email or f"{phone}@noreply.roddos.com",
        phone_number=phone_e164,
        country="CO",
        id_number=cedula,
        id_type=_doc_type_to_wava_id(tipo_doc),
    )

    order_key = f"wa-{workspace_id}-{phone}-{uuid.uuid4().hex[:12]}"

    # TODO: amount should come from the actual quoted product
    # For now we use a placeholder amount that will be replaced
    # when we implement the full quotation-to-order flow
    amount = 0

    try:
        wava_order = await wava_client.create_order(
            amount=amount,
            description=f"Compra WhatsApp · {phone}",
            shopper=shopper,
            gateway_id=1,
            order_key=order_key,
        )
    except WavaError:
        logger.exception("wava_order_creation_failed", extra={"phone": phone[-4:]})
        return (
            "Tuvimos un problema al generar tu solicitud de pago. "
            "Por favor intenta de nuevo en unos minutos.",
            "wava_error",
        )

    now = datetime.now(tz=UTC)
    await db[col.WAVA_ORDERS].update_one(
        {"workspace_id": workspace_id, "order_key": order_key},
        {
            "$set": {
                "wava_order_id": wava_order.order_id,
                "phone": phone,
                "amount": amount,
                "description": f"Compra WhatsApp · {phone}",
                "gateway": "nequi",
                "status": "pending",
                "updated_at": now,
            },
            "$setOnInsert": {
                "workspace_id": workspace_id,
                "order_key": order_key,
                "created_at": now,
            },
        },
        upsert=True,
    )

    return (
        "Te enviamos la solicitud de pago a tu Nequi. "
        "Apruébala en tu app para confirmar la compra. 📱✅",
        "orden_creada",
    )


async def handle_message(
    db: AsyncIOMotorDatabase,
    *,
    classification: ClassificationResult,
    message_text: str,
    phone: str,
    mercately_client: MercatelyClient,
    anthropic_api_key: str = "",
    workspace_id: str = "RODDOS",
    wava_client: WavaClient | None = None,
) -> dict[str, Any]:
    """Despacha respuesta según intent clasificado.

    Retorna: {responded: bool, intent, outcome, response_preview}.
    """
    intent = classification.intent
    response_text = ""
    outcome = "responded"
    products_found = 0

    if intent == "cotizar_repuesto":
        products = await search_catalog(db, message_text, workspace_id)
        products_found = len(products)
        response_text = _format_product_response(products, message_text)
        outcome = "cotizado" if products else "sin_resultado"

    elif intent == "consulta_general":
        response_text = await _generate_general_response(message_text, anthropic_api_key)
        outcome = "respondido_general"

    elif intent == "cotizar_moto":
        response_text = _format_moto_placeholder()
        outcome = "placeholder_moto"

    elif intent == "consulta_credito":
        response_text = _format_credit_placeholder()
        outcome = "placeholder_credito"

    elif intent == "onboarding":
        created = await _register_contact(db, phone, workspace_id)
        response_text = _format_onboarding()
        outcome = "onboarding_nuevo" if created else "onboarding_existente"

    elif intent == "confirmar_compra":
        if wava_client is None or not wava_client.enabled:
            response_text = (
                "La pasarela de pago no está disponible en este momento. "
                "Por favor intenta más tarde o visítanos en tienda."
            )
            outcome = "wava_no_disponible"
        else:
            contact = await _get_contact(db, phone, workspace_id)
            if not contact:
                response_text = (
                    "No encontramos tu información registrada. "
                    "¿Podrías decirnos tu nombre completo y número de cédula?"
                )
                outcome = "contacto_no_encontrado"
            else:
                response_text, outcome = await _create_wava_order(
                    db,
                    phone=phone,
                    contact=contact,
                    workspace_id=workspace_id,
                    wava_client=wava_client,
                )

    else:
        response_text = (
            "¡Hola! Somos RODDOS. ¿En qué podemos ayudarte? "
            "Puedes preguntarnos por repuestos, motos o crédito."
        )
        outcome = "fallback"

    sent = False
    if response_text and mercately_client.enabled:
        try:
            await mercately_client.send_text(phone, response_text)
            sent = True
        except Exception:  # noqa: BLE001
            logger.exception("mercately_send_failed", extra={"phone": phone[-4:]})
            outcome = "send_failed"

    await _emit_response_event(
        db,
        phone=phone,
        intent=intent,
        outcome=outcome,
        workspace_id=workspace_id,
        products_found=products_found,
    )

    logger.info(
        "message_handled",
        extra={"intent": intent, "outcome": outcome, "sent": sent},
    )

    return {
        "responded": sent,
        "intent": intent,
        "outcome": outcome,
        "response_preview": response_text[:100],
    }
