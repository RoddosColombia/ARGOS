"""Intent classifier · Haiku 4.5 clasifica mensajes inbound WhatsApp (Build 3.1).

Input: texto del mensaje + phone + contexto opcional.
Output: ClassificationResult con intent, confidence, route_to ("argos"|"sismo").

ARGOS intents: cotizar_repuesto, cotizar_moto, consulta_credito, consulta_general, onboarding.
SISMO intents: pago_cuota, consulta_mora, soporte_credito, comprobante_pago.

Confidence < 0.7 → default route_to "argos" (conservative routing).
Emite evento whatsapp.message.classified al bus.

Refs: phase_3/build_3.1 · ROG-W6 (cada conversación tiene goal medible)
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger("argos.agents.whatsapp.intent")

CLASSIFIER_MODEL = "claude-haiku-4-5-20251001"
CONFIDENCE_THRESHOLD = 0.7

ARGOS_INTENTS = frozenset({
    "cotizar_repuesto",
    "cotizar_moto",
    "consulta_credito",
    "consulta_general",
    "onboarding",
})

SISMO_INTENTS = frozenset({
    "pago_cuota",
    "consulta_mora",
    "soporte_credito",
    "comprobante_pago",
})

ALL_INTENTS = ARGOS_INTENTS | SISMO_INTENTS

SYSTEM_PROMPT = """\
Eres el clasificador de intención de ARGOS para mensajes WhatsApp de clientes \
de RODDOS (repuestos y motos en Colombia).

Clasifica el mensaje del cliente en UNA de estas intenciones:

ARGOS (repuestos, motos, crédito nuevo, consultas generales):
- cotizar_repuesto: cliente pregunta por precio/disponibilidad de repuesto
- cotizar_moto: cliente pregunta por precio/disponibilidad de moto
- consulta_credito: cliente pregunta por financiación o crédito nuevo
- consulta_general: saludo, pregunta general, catálogo, horarios
- onboarding: cliente nuevo que quiere registrarse

SISMO (cobranza, pagos, mora, soporte de crédito existente):
- pago_cuota: cliente quiere pagar cuota o informa de pago realizado
- consulta_mora: cliente pregunta por saldo pendiente o estado de mora
- soporte_credito: cliente con crédito activo tiene problema o consulta
- comprobante_pago: cliente envía comprobante de pago

Responde SOLO con JSON válido, sin markdown:
{"intent": "<intent>", "confidence": <0.0-1.0>}
"""


@dataclass(frozen=True, slots=True)
class ClassificationResult:
    intent: str
    confidence: float
    route_to: str
    raw_response: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _determine_route(intent: str, confidence: float) -> str:
    if confidence < CONFIDENCE_THRESHOLD:
        return "argos"
    if intent in SISMO_INTENTS:
        return "sismo"
    return "argos"


async def classify_intent(
    message_text: str,
    *,
    phone: str = "",
    context: str = "",
    anthropic_api_key: str = "",
    db: AsyncIOMotorDatabase | None = None,
    workspace_id: str = "RODDOS",
) -> ClassificationResult:
    """Clasifica intent de un mensaje inbound.

    Si no hay API key, devuelve consulta_general con confidence 0.0.
    """
    if not anthropic_api_key:
        logger.warning("intent_classifier_skipped_no_api_key")
        return ClassificationResult(
            intent="consulta_general",
            confidence=0.0,
            route_to="argos",
        )

    import anthropic

    client = anthropic.AsyncAnthropic(api_key=anthropic_api_key)

    user_msg = message_text[:2000]
    if context:
        user_msg = f"[Contexto: {context[:500]}]\n\nMensaje del cliente: {user_msg}"

    try:
        resp = await client.messages.create(
            model=CLASSIFIER_MODEL,
            max_tokens=100,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
    except anthropic.APIError as exc:
        logger.exception("intent_classifier_api_error", extra={"status": getattr(exc, "status_code", 0)})
        return ClassificationResult(
            intent="consulta_general",
            confidence=0.0,
            route_to="argos",
            raw_response=str(exc)[:200],
        )

    raw = resp.content[0].text.strip() if resp.content else ""

    try:
        parsed = json.loads(raw)
        intent = parsed.get("intent", "consulta_general")
        confidence = float(parsed.get("confidence", 0.0))
    except (json.JSONDecodeError, ValueError, TypeError):
        logger.warning("intent_classifier_parse_failed", extra={"raw": raw[:200]})
        intent = "consulta_general"
        confidence = 0.0

    if intent not in ALL_INTENTS:
        logger.warning("intent_classifier_unknown_intent", extra={"intent": intent})
        intent = "consulta_general"
        confidence = 0.0

    route_to = _determine_route(intent, confidence)

    if db is not None:
        from argos.db.events import publish_event
        try:
            await publish_event(
                db,
                event_type="whatsapp.message.classified",
                workspace_id=workspace_id,
                producer="intent_classifier",
                payload={
                    "phone_last4": phone[-4:] if phone else "",
                    "intent": intent,
                    "confidence": round(confidence, 3),
                    "route_to": route_to,
                    "message_length": len(message_text),
                },
            )
        except Exception:  # noqa: BLE001
            logger.exception("intent_classifier_event_publish_failed")

    logger.info(
        "intent_classified",
        extra={"intent": intent, "confidence": confidence, "route_to": route_to},
    )

    return ClassificationResult(
        intent=intent,
        confidence=confidence,
        route_to=route_to,
        raw_response=raw[:200],
    )
