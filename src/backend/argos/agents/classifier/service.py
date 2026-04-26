"""Classifier · Haiku 4.5 binario relevante/no-relevante para items de marketplace.

Ver docs/knowledge/modelos_llm.md (Scout · Haiku con caching).

Build 1.1: input = title + descripción (opcional) + watch_query · output =
ClassifyResult(relevante, razon, cached). Sin feedback loop todavía (DT-007).

Caching:
- A nivel API: el system prompt va con `cache_control: {"type": "ephemeral"}`
  para que Anthropic cachee los ~1.5K tokens del prompt entre llamadas.
- A nivel proceso: cache local en memoria por (title, description, watch_query)
  evita la llamada API completa cuando el mismo item se vuelve a clasificar
  dentro del mismo proceso (ej. dos ticks consecutivos del Scout).
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Protocol

logger = logging.getLogger("argos.agents.classifier")

# Pinear modelo (modelos_llm.md · regla inamovible · nunca *-latest en prod)
HAIKU_MODEL = "claude-haiku-4-5-20251001"
MAX_OUTPUT_TOKENS = 200

SYSTEM_PROMPT = """Eres un clasificador binario de productos de repuestos y accesorios para motos en marketplaces de Colombia (MercadoLibre, Facebook Marketplace).

Tu trabajo: dado el título de un listing y una "watch query" (consulta de búsqueda que el sistema ARGOS está monitoreando), decidir si el producto es **relevante** para esa query.

## Definición de relevante

Un producto es **relevante** si AL MENOS UNA de estas condiciones se cumple:

1. **Match semántico fuerte:** el título describe el mismo tipo de repuesto/accesorio que la watch query (aunque no sean palabras exactas). Ejemplos:
   - watch_query="aceite moto" + título="Aceite motor 4T 20W50 1L Castrol" → relevante
   - watch_query="pastillas freno moto" + título="Bandas de freno disco original Yamaha" → relevante (bandas y pastillas son sinónimos contextuales)
2. **Match de modelo de moto:** la watch query menciona un modelo de moto (TVS Raider 125, Pulsar 200, etc.) y el título también lo menciona, aunque el repuesto sea genérico. Ejemplos:
   - watch_query="repuestos TVS Raider 125" + título="Kit arrastre cadena piñon TVS Raider 125 2020-2024" → relevante
   - watch_query="llanta Pulsar 200" + título="Llanta trasera 130/70 R17 Pulsar NS 200" → relevante

## Definición de no-relevante

Marca como **no relevante** si:

1. **Diferente categoría:** el título es de un producto que NO es repuesto de moto.
   - watch_query="aceite moto" + título="Aceite de oliva extra virgen 1L" → no relevante
   - watch_query="batería moto" + título="Batería de cocina antiadherente" → no relevante
2. **Repuesto de carro, no moto:** explicitamente o por contexto.
   - watch_query="filtro aire moto" + título="Filtro aire K&N Mazda 3 2010" → no relevante
3. **Servicio, no producto físico:** taller, reparación, mano de obra.
   - watch_query="batería moto" + título="Servicio de cambio de batería a domicilio" → no relevante (es servicio, no producto)
4. **Marca incompatible inequívoca:** moto de otro tipo (eléctrica de niño, scooter Vespa antigua, moto de agua).
   - watch_query="cadena 428H moto" + título="Cadena de bicicleta MTB Shimano" → no relevante
5. **Listing de información, no de venta:** manuales, tutoriales, suscripciones.

## Casos borderline

Cuando hay duda razonable, prefiere **relevante=true** si el listing podría ser de interés para alguien comprando ese tipo de repuesto. ARGOS prefiere falsos positivos (revisión humana después) sobre falsos negativos (perder señales de mercado).

## Formato de respuesta · OBLIGATORIO

Responde EXCLUSIVAMENTE con un objeto JSON válido, sin markdown fences, sin texto antes o después. Esquema:

```
{"relevante": true|false, "razon": "máximo 30 palabras explicando el match o el rechazo"}
```

## Ejemplos de entrenamiento

Input:
  watch_query: "aceite moto"
  título: "Aceite Motul 5100 4T 10W40 1L moto MA2"
Output:
  {"relevante": true, "razon": "aceite específico para moto 4T, marca conocida en repuestos motos"}

Input:
  watch_query: "pastillas freno moto"
  título: "Pastillas freno delantero Pulsar NS 200 originales Bajaj"
Output:
  {"relevante": true, "razon": "pastillas de freno específicas para moto Pulsar NS 200"}

Input:
  watch_query: "filtro aire moto"
  título: "Filtro de aire universal cónico K&N negro deportivo"
Output:
  {"relevante": true, "razon": "filtro aire universal aplica a motos como mod común"}

Input:
  watch_query: "cadena 428H moto"
  título: "Cadena oro 18k para mujer 50cm"
Output:
  {"relevante": false, "razon": "cadena de joyería no de transmisión"}

Input:
  watch_query: "batería moto"
  título: "Batería gel YTX7L-BS 12V 6Ah moto Pulsar/Discover"
Output:
  {"relevante": true, "razon": "batería gel específica para moto con modelos compatibles listados"}

Input:
  watch_query: "espejo retrovisor universal moto"
  título: "Par espejos retrovisores moto rosca M10 universales negro"
Output:
  {"relevante": true, "razon": "par de espejos retrovisores con rosca estándar moto"}

Input:
  watch_query: "repuestos TVS Raider 125"
  título: "Funda asiento moto impermeable talla universal"
Output:
  {"relevante": false, "razon": "accesorio universal sin mención específica TVS Raider 125"}

Input:
  watch_query: "kit arrastre TVS Raider"
  título: "Kit cadena + piñones IRIS para TVS Raider 125 NS125 2019-2024"
Output:
  {"relevante": true, "razon": "kit arrastre completo específico TVS Raider 125 marca IRIS"}

Recordatorio: solo JSON, sin texto adicional."""


@dataclass
class ClassifyResult:
    relevante: bool
    razon: str
    cached: bool = False  # True si vino del cache local · False si fue llamada API


class _AnthropicLike(Protocol):
    """Protocolo mínimo del cliente Anthropic async que usamos."""

    @property
    def messages(self) -> Any: ...  # noqa: D401


class NoOpClassifier:
    """Stub que marca todo como relevante=False con razón clara.

    Usado como fallback cuando ANTHROPIC_API_KEY no está configurado.
    Esto degrada Scout a "guarda nada" en vez de "guarda todo sin filtro" —
    decisión conservadora: si no hay clasificador, no contaminamos el catálogo.
    """

    async def classify(self, title: str, description: str, watch_query: str) -> ClassifyResult:
        return ClassifyResult(
            relevante=False,
            razon="classifier_unavailable_anthropic_api_key_missing",
            cached=False,
        )


class HaikuProductClassifier:
    """Clasificador real con Haiku 4.5 + cache local."""

    def __init__(
        self,
        anthropic_client: _AnthropicLike | None = None,
        *,
        api_key: str = "",
        model: str = HAIKU_MODEL,
    ) -> None:
        if anthropic_client is not None:
            self._client = anthropic_client
        elif api_key:
            from anthropic import AsyncAnthropic  # lazy import · solo cuando hay key
            self._client = AsyncAnthropic(api_key=api_key)
        else:
            raise ValueError("HaikuProductClassifier requiere anthropic_client o api_key")
        self._model = model
        self._cache: dict[tuple[str, str, str], ClassifyResult] = {}

    @staticmethod
    def _cache_key(title: str, description: str, watch_query: str) -> tuple[str, str, str]:
        return (title.strip().lower(), description.strip().lower(), watch_query.strip().lower())

    async def classify(self, title: str, description: str, watch_query: str) -> ClassifyResult:
        key = self._cache_key(title, description, watch_query)
        if key in self._cache:
            cached = self._cache[key]
            return ClassifyResult(cached.relevante, cached.razon, cached=True)

        user_message = (
            f"watch_query: {watch_query}\n"
            f"título: {title}\n"
            f"descripción: {description or '(sin descripción)'}"
        )

        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=MAX_OUTPUT_TOKENS,
                system=[
                    {
                        "type": "text",
                        "text": SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[{"role": "user", "content": user_message}],
            )
        except Exception as exc:  # noqa: BLE001 — failure of API → conservative discard
            logger.exception("classifier_api_call_failed", extra={"watch_query": watch_query})
            result = ClassifyResult(
                relevante=False,
                razon=f"api_error_{type(exc).__name__}",
                cached=False,
            )
            self._cache[key] = result
            return result

        text = self._extract_text(response)
        parsed = self._parse_json(text)
        result = ClassifyResult(
            relevante=bool(parsed.get("relevante", False)),
            razon=str(parsed.get("razon", ""))[:200],
            cached=False,
        )
        self._cache[key] = result
        return result

    @staticmethod
    def _extract_text(response: Any) -> str:
        try:
            content = response.content
            if not content:
                return ""
            block = content[0]
            return getattr(block, "text", "") or ""
        except (AttributeError, IndexError, TypeError):
            return ""

    @staticmethod
    def _parse_json(text: str) -> dict[str, Any]:
        if not text:
            return {"relevante": False, "razon": "empty_response"}
        # Strip markdown fences si Haiku los añadió por error
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.MULTILINE).strip()
        try:
            data = json.loads(cleaned)
            if not isinstance(data, dict):
                return {"relevante": False, "razon": "non_dict_response"}
            return data
        except json.JSONDecodeError:
            return {"relevante": False, "razon": "parse_error"}
