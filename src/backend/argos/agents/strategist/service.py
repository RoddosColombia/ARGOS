"""Strategist Agent · Build 3.1 (Morning Briefing).

Recolecta señales de las últimas 24h del bus + colecciones, las pasa a Claude
Sonnet 4.6 con prompt cacheado, y devuelve un MorningBriefing JSON estructurado.

El Executive (otro agente) se encarga de persistir + emitir evento. Strategist
solo razona.
"""
from __future__ import annotations

import contextlib
import json
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from motor.motor_asyncio import AsyncIOMotorDatabase

from argos.db import collections as col

logger = logging.getLogger("argos.agents.strategist")

# Modelo pinned (modelos_llm.md) · cuando se promueva a Opus 4.7 cambiar aquí
SONNET_MODEL = "claude-sonnet-4-6-20260301"
MAX_OUTPUT_TOKENS = 1500

Prioridad = Literal["Alta", "Media", "Baja"]


@dataclass
class AccionRecomendada:
    accion: str
    justificacion: str
    impacto_esperado: str
    prioridad: Prioridad


@dataclass
class Mercado24h:
    nuevos_skus: int
    bajas_precio: int
    nuevas_promos: int


@dataclass
class MorningBriefing:
    fecha: str  # YYYY-MM-DD
    mercado_24h: Mercado24h
    acciones_del_dia: list[AccionRecomendada]
    estado_mercado: str
    modelo_usado: str = SONNET_MODEL
    tokens_input: int = 0
    tokens_output: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "fecha": self.fecha,
            "mercado_24h": asdict(self.mercado_24h),
            "acciones_del_dia": [asdict(a) for a in self.acciones_del_dia],
            "estado_mercado": self.estado_mercado,
            "modelo_usado": self.modelo_usado,
            "tokens_input": self.tokens_input,
            "tokens_output": self.tokens_output,
        }


SYSTEM_PROMPT = """Eres el Strategist de ARGOS · sistema de inteligencia comercial de RODDOS S.A.S. (Bogotá, Colombia).

Tu rol: Director de Marketing Digital senior con 12+ años de experiencia en e-commerce y retail de repuestos para motocicletas en LATAM. Has trabajado para distribuidores grandes (TVS Motor Colombia, Bajaj Auto Colombia, Auteco Mobility) y conoces a fondo el mercado colombiano de motos: Pulsar, Discover, Boxer, TVS Raider 125, AKT, NKD, CB 110.

## Contexto operativo de RODDOS

- **Vertical primario:** REPUESTOS para motos (negocio recurrente · LTV 5 años por cliente)
- **Vertical secundario:** VENTA DE MOTOS (puerta de entrada al cliente)
- **Segmento principal del cliente:** mototaxistas y trabajadores delivery (Rappi/DiDi/Uber) · 70% del volumen · uso intensivo (2x-2.5x más rotación de repuestos que un motociclista promedio)
- **Producto financiero estrella:** Crédito Rodante (financia repuestos · cliente RODDOS con historial A+/A/B tiene bypass de scoring · aprobación en < 60 seg)
- **Canales:** WhatsApp comercial (frontend), web roddos.com (admin), futuro app móvil

## Productos canónicos del catálogo

Repuestos consumibles (los que rotan):
- **Aceites:** 4T 20W50, 10W40, semisintéticos · cambio cada 4-5 semanas en uso intensivo
- **Filtros:** aire, aceite, gasolina · 6-12 semanas
- **Pastillas freno:** delanteras + traseras · 6-12 semanas en delivery
- **Bujías:** NGK, Bosch, Champion · 8-12 meses
- **Cadena + piñones (kit arrastre):** 428H, 520 · 8-10 meses
- **Llantas:** delantera 80/100 R17, trasera 130/70 R17 · 10-12 meses
- **Baterías:** YTX7L-BS, YTZ7S · 18-24 meses
- **Amortiguadores, espejos, manijas, cubiertas:** rotación más lenta · 1-3 años

Marcas relevantes: Motul, Castrol, Mobil, Total (aceites) · Bajaj original, IRIS, JT Sprockets (cadenas) · NGK, Bosch (bujías) · Pirelli, Michelin, Maxxis, Kenda (llantas) · Yuasa, Mac, Willard (baterías)

## Competencia actual identificada

- **Marketplaces grandes:** Mercado Libre Colombia (vende repuestos a precios bajos · seller dominante en aceites y baterías) · Falabella, Linio, Éxito (canal secundario)
- **Especialistas web:** Sitios verticales de repuestos (RepuestosOnline, MotoMercados, Bermotos)
- **Físicos consolidados:** Cadenas como Roddos competidores · talleres barriales con stock limitado
- **FB Marketplace:** sellers individuales · precios irregulares · mercado gris en algunos casos
- **Ads digitales:** competidores corren ads en Meta y Google de manera intermitente · pocos sostienen >30 días

## Tu tarea diaria: Morning Briefing

Cada día a las 06:45 UTC el Executive Agent te pide un MorningBriefing. Recibes en el user message un JSON con todas las señales que ARGOS detectó en las últimas 24 horas:

- `new_products`: SKUs que el Scout encontró por primera vez
- `price_changes`: cambios de precio ≥ 5% en MELI/FB (positivos = subida, negativos = bajada)
- `price_alerts`: caídas de precio ≥ 15% en últimas 24h (señal fuerte)
- `spike_keywords`: keywords con interés Google Trends > 30% delta o > 80 absoluto
- `new_ads`: ads nuevos detectados en Meta Ad Library + Google Ads Transparency
- `new_social_accounts`: cuentas IG/TikTok del nicho que aparecieron en el catálogo

Tu output debe ser un **MorningBriefing JSON estricto** con esta forma exacta:

```json
{
  "fecha": "YYYY-MM-DD",
  "mercado_24h": {
    "nuevos_skus": 0,
    "bajas_precio": 0,
    "nuevas_promos": 0
  },
  "acciones_del_dia": [
    {
      "accion": "string corta · imperativo · qué hacer",
      "justificacion": "string · 1-2 frases · por qué basado en señales",
      "impacto_esperado": "string · 1 frase · qué métrica esperas mover",
      "prioridad": "Alta" | "Media" | "Baja"
    }
  ],
  "estado_mercado": "string · 2-3 frases · resumen ejecutivo del día"
}
```

## Reglas inamovibles

1. **MÁXIMO 3 acciones del día.** Si hay >3 candidatas, prioriza por impacto comercial inmediato. Mejor 3 acciones específicas que 10 genéricas.
2. **Cada acción debe ser ejecutable HOY** por el CEO con un solo botón/decisión. Evitar acciones tipo "investigar" o "considerar". Preferir verbos: "Bajar precio de X a $Y", "Activar campaña de Z", "Stockear N unidades de W antes del fin de mes", "Pausar promoción de V".
3. **Justificación basada en señales recibidas.** Si no hay señal que respalde la acción, NO la propongas. Cita el dato concreto: "porque el competidor X bajó precio 18%" o "porque el spike de keyword Y fue de 45% esta semana".
4. **Foco en repuestos.** Las acciones sobre VENTA de motos son secundarias y solo cuando hay señal muy fuerte (lanzamiento de modelo, ad blitz de un competidor de Pulsar/Raider).
5. **NO inventar datos.** Si los signals están vacíos, di que el día está estable y propone 0-1 acciones rutinarias (ej. "Revisar inventario de aceites antes del fin de semana").
6. **Estado de mercado** debe sintetizar: 1 frase "qué pasó", 1 frase "qué significa para RODDOS", opcional 1 frase "qué hay que vigilar mañana".

## Formato JSON · OBLIGATORIO

Responde EXCLUSIVAMENTE con el JSON `MorningBriefing`, sin markdown fences, sin texto antes o después. El consumidor es un parser estricto · cualquier prosa fuera del JSON rompe el flujo.

## Ejemplos de calibración

### Ejemplo 1 · Día con bajada agresiva de competidor

Input signals (resumido):
- 3 price_alerts: aceites 4T bajaron 22% en MELI (3 sellers diferentes)
- 0 new_ads
- 1 spike_keyword: "aceite moto barato" +45%

Output:
```json
{
  "fecha": "2026-04-15",
  "mercado_24h": {"nuevos_skus": 0, "bajas_precio": 3, "nuevas_promos": 0},
  "acciones_del_dia": [
    {
      "accion": "Bajar precio de Aceite Motul 4T 20W50 1L a $52.000 (de $58.000)",
      "justificacion": "3 sellers MELI bajaron aceites 22% en últimas 24h · keyword 'aceite moto barato' subió 45% · si no respondemos perdemos el ticket de aceite que es 30% de las ventas recurrentes",
      "impacto_esperado": "Recuperar share en aceites · proteger 12-15% del revenue mensual de repuestos",
      "prioridad": "Alta"
    },
    {
      "accion": "Activar mensaje WhatsApp F6 a clientes que compraron aceite hace ≥4 semanas con cupón -10%",
      "justificacion": "Cohort de mototaxistas/delivery cambia aceite cada 4-5 semanas · momento ideal · neutraliza bajada de competidores con engagement directo",
      "impacto_esperado": "Conversión 8-12% sobre cohorte · 50-80 unidades vendidas en 48h",
      "prioridad": "Media"
    }
  ],
  "estado_mercado": "Día agresivo en aceites · al menos 3 sellers MELI movieron precios a la baja simultáneamente y la demanda search confirma presión competitiva. Para RODDOS no es señal de crisis pero sí de que los próximos 7 días deciden si retenemos share o lo perdemos. Vigilar mañana si Mobil y Castrol también bajan."
}
```

### Ejemplo 2 · Día estable sin señales fuertes

Input signals (resumido):
- 1 new_product (filtro aire genérico)
- 0 price_alerts
- 0 spike_keywords
- 1 new_ad de competidor pequeño (durabilidad 1 día · probable test)

Output:
```json
{
  "fecha": "2026-04-16",
  "mercado_24h": {"nuevos_skus": 1, "bajas_precio": 0, "nuevas_promos": 0},
  "acciones_del_dia": [
    {
      "accion": "Revisar inventario de pastillas freno antes del fin de semana (pico de demanda lunes)",
      "justificacion": "Sin señales de mercado · acción rutinaria · los lunes históricamente aumenta 18% la demanda de pastillas en clientes delivery que rodaron fin de semana",
      "impacto_esperado": "Evitar stockout · recuperar 5-8 ventas potenciales perdidas por falta de stock",
      "prioridad": "Baja"
    }
  ],
  "estado_mercado": "Mercado estable · sin movimientos competitivos significativos. El único ad nuevo viene de un seller pequeño con probable test (1 día de durabilidad) · no requiere acción. Día para foco operacional interno."
}
```

Recordatorio final: **solo JSON, sin texto fuera del objeto**."""


@dataclass
class _Signals:
    new_products: list[dict[str, Any]] = field(default_factory=list)
    price_changes: list[dict[str, Any]] = field(default_factory=list)
    price_alerts: list[dict[str, Any]] = field(default_factory=list)
    spike_keywords: list[dict[str, Any]] = field(default_factory=list)
    new_ads: list[dict[str, Any]] = field(default_factory=list)
    new_social_accounts: list[dict[str, Any]] = field(default_factory=list)
    # Build 3.2: enriquecimiento semántico desde Qdrant · si MemoryAgent está
    # disponible, contiene productos y ads similares a las señales detectadas.
    related_products: list[dict[str, Any]] = field(default_factory=list)
    related_ads: list[dict[str, Any]] = field(default_factory=list)
    # Build 4.1: contexto de inventario desde SISMO V2 (snapshot del día).
    inventory_summary: dict[str, Any] = field(default_factory=dict)
    slow_movers: list[dict[str, Any]] = field(default_factory=list)

    def to_user_payload(self) -> dict[str, Any]:
        return {
            "new_products": self.new_products,
            "price_changes": self.price_changes,
            "price_alerts": self.price_alerts,
            "spike_keywords": self.spike_keywords,
            "new_ads": self.new_ads,
            "new_social_accounts": self.new_social_accounts,
            "related_products": self.related_products,
            "related_ads": self.related_ads,
            "inventory_summary": self.inventory_summary,
            "slow_movers": self.slow_movers,
        }


async def gather_signals(
    db: AsyncIOMotorDatabase,
    workspace_id: str,
    *,
    lookback_hours: int = 24,
    memory_agent: Any | None = None,
) -> _Signals:
    """Recolecta señales de las últimas `lookback_hours` para alimentar al Strategist."""
    cutoff = datetime.now(tz=UTC) - timedelta(hours=lookback_hours)
    s = _Signals()

    # Productos nuevos
    cursor = db[col.PRODUCTS_CATALOG].find(
        {"workspace_id": workspace_id, "created_at": {"$gte": cutoff}},
        {"sku_normalizado": 1, "nombre": 1, "precio_actual": 1, "source": 1, "_id": 0},
    ).limit(50)
    s.new_products = await cursor.to_list(length=50)

    # Cambios de precio (eventos)
    cursor = db[col.ARGOS_EVENTS].find(
        {
            "workspace_id": workspace_id,
            "event_type": "marketplace.price.changed",
            "timestamp_utc": {"$gte": cutoff},
        },
        {"_id": 0, "event_id": 0, "metadata": 0},
    ).sort("timestamp_utc", -1).limit(50)
    s.price_changes = [{"timestamp": d["timestamp_utc"].isoformat(), **d["payload"]} for d in await cursor.to_list(length=50)]

    # Price alerts (drops fuertes)
    cursor = db[col.ARGOS_EVENTS].find(
        {
            "workspace_id": workspace_id,
            "event_type": "marketplace.price.alert",
            "timestamp_utc": {"$gte": cutoff},
        },
        {"_id": 0},
    ).sort("timestamp_utc", -1).limit(20)
    s.price_alerts = [{"timestamp": d["timestamp_utc"].isoformat(), **d["payload"]} for d in await cursor.to_list(length=20)]

    # Spike keywords
    cursor = db[col.KEYWORDS].find(
        {"workspace_id": workspace_id, "spike_detected": True},
        {"_id": 0, "keyword": 1, "interest_over_time": 1, "growth_pct_7d": 1},
    ).limit(20)
    s.spike_keywords = await cursor.to_list(length=20)

    # Nuevos ads
    cursor = db[col.ADS_LIBRARY].find(
        {"workspace_id": workspace_id, "created_at": {"$gte": cutoff}},
        {"_id": 0, "plataforma": 1, "anunciante": 1, "copy_titulo": 1, "fuente_query": 1, "durabilidad_dias": 1, "formato": 1},
    ).limit(20)
    s.new_ads = await cursor.to_list(length=20)

    # Nuevas cuentas social
    cursor = db[col.SOCIAL_ACCOUNTS].find(
        {"workspace_id": workspace_id, "created_at": {"$gte": cutoff}},
        {"_id": 0, "plataforma": 1, "username": 1, "seguidores": 1, "relevancia_score": 1},
    ).sort("relevancia_score", -1).limit(10)
    s.new_social_accounts = await cursor.to_list(length=10)

    # Build 4.1 · contexto de inventario SISMO (snapshot del día actual)
    try:
        await _enrich_with_sismo_inventory(s, db, workspace_id)
    except Exception:  # noqa: BLE001
        logger.exception("strategist_sismo_enrich_failed")

    # Build 3.2 · enriquecimiento semántico via Qdrant si MemoryAgent disponible
    if memory_agent is not None:
        try:
            await _enrich_with_memory(s, memory_agent, workspace_id)
        except Exception:  # noqa: BLE001
            logger.exception("strategist_memory_enrich_failed")

    logger.info(
        "strategist_signals_gathered",
        extra={
            "new_products": len(s.new_products),
            "price_changes": len(s.price_changes),
            "price_alerts": len(s.price_alerts),
            "spike_keywords": len(s.spike_keywords),
            "new_ads": len(s.new_ads),
            "new_social_accounts": len(s.new_social_accounts),
            "related_products": len(s.related_products),
            "related_ads": len(s.related_ads),
            "inventory_total_skus": s.inventory_summary.get("total_skus", 0),
            "slow_movers": len(s.slow_movers),
        },
    )
    return s


async def _enrich_with_sismo_inventory(
    s: _Signals, db: AsyncIOMotorDatabase, workspace_id: str
) -> None:
    """Lee el snapshot más reciente de `sismo_inventory` y agrega contexto.

    Build 4.1: aggregate sobre el último `fecha_sync_date` por workspace.
    `inventory_summary` resume totales (skus, stock_units, slow_count, valor inv).
    `slow_movers` top 10 SKUs con mayor `dias_inventario` (>= 45d) para que el
    Strategist genere acciones de liquidación o promo cuando aplique.
    """
    pipeline_latest = [
        {"$match": {"workspace_id": workspace_id}},
        {"$group": {"_id": None, "max_date": {"$max": "$fecha_sync_date"}}},
    ]
    latest_docs = await db[col.SISMO_INVENTORY].aggregate(pipeline_latest).to_list(length=1)
    if not latest_docs or not latest_docs[0].get("max_date"):
        return
    latest_date = latest_docs[0]["max_date"]

    summary_pipeline = [
        {"$match": {"workspace_id": workspace_id, "fecha_sync_date": latest_date}},
        {
            "$group": {
                "_id": None,
                "total_skus": {"$sum": 1},
                "stock_units": {"$sum": "$stock"},
                "slow_count": {"$sum": {"$cond": ["$is_slow_mover", 1, 0]}},
                "valor_inventario": {"$sum": {"$multiply": ["$stock", "$costo"]}},
            }
        },
    ]
    summary_docs = await db[col.SISMO_INVENTORY].aggregate(summary_pipeline).to_list(length=1)
    if summary_docs:
        d = summary_docs[0]
        s.inventory_summary = {
            "fecha_sync": latest_date,
            "total_skus": int(d.get("total_skus") or 0),
            "stock_units": int(d.get("stock_units") or 0),
            "slow_count": int(d.get("slow_count") or 0),
            "valor_inventario_cop": round(float(d.get("valor_inventario") or 0), 2),
        }

    cursor = db[col.SISMO_INVENTORY].find(
        {"workspace_id": workspace_id, "fecha_sync_date": latest_date, "is_slow_mover": True},
        {"_id": 0, "sku": 1, "nombre": 1, "stock": 1, "precio": 1, "dias_inventario": 1},
    ).sort("dias_inventario", -1).limit(10)
    s.slow_movers = await cursor.to_list(length=10)


async def _enrich_with_memory(s: _Signals, memory_agent: Any, workspace_id: str) -> None:
    """Para cada price_change y new_ad, busca top-3 items semánticamente similares.

    Útil cuando el Strategist necesita "qué otros productos del catálogo
    son comparables al que cambió de precio?" · "qué ads previos son parecidos
    al nuevo de la competencia?". Limita a top 2 señales para no inflar el
    contexto del LLM ni gastar embeddings en queries redundantes.
    """
    if not getattr(memory_agent, "enabled", False):
        return

    # Hasta 2 productos con price change reciente · top 3 similares cada uno
    seen_skus: set[str] = set()
    for change in s.price_changes[:2]:
        sku = change.get("sku_normalizado", "")
        if not sku or sku in seen_skus:
            continue
        seen_skus.add(sku)
        nombre = change.get("nombre") or sku
        hits = await memory_agent.search_similar_products(
            nombre, limit=3, workspace_id=workspace_id
        )
        for h in hits:
            payload = h.payload if hasattr(h, "payload") else h.get("payload") or {}
            score = h.score if hasattr(h, "score") else h.get("score") or 0
            s.related_products.append(
                {
                    "trigger_sku": sku,
                    "score": round(float(score), 4),
                    "sku_normalizado": payload.get("sku_normalizado", ""),
                    "nombre": payload.get("nombre", ""),
                    "source": payload.get("source", ""),
                }
            )

    # Hasta 2 ads nuevos · top 3 ads históricos similares cada uno
    seen_ad_ids: set[str] = set()
    for ad in s.new_ads[:2]:
        ad_titulo = ad.get("copy_titulo") or ad.get("anunciante", "")
        ad_key = ad.get("anunciante", "") + "|" + ad_titulo
        if ad_key in seen_ad_ids or not ad_titulo:
            continue
        seen_ad_ids.add(ad_key)
        hits = await memory_agent.search_similar_ads(
            ad_titulo, limit=3, workspace_id=workspace_id
        )
        for h in hits:
            payload = h.payload if hasattr(h, "payload") else h.get("payload") or {}
            score = h.score if hasattr(h, "score") else h.get("score") or 0
            s.related_ads.append(
                {
                    "trigger_titulo": ad_titulo[:80],
                    "score": round(float(score), 4),
                    "anunciante": payload.get("anunciante", ""),
                    "copy_titulo": payload.get("copy_titulo", ""),
                    "plataforma": payload.get("plataforma", ""),
                }
            )


def _strip_markdown_fences(text: str) -> str:
    return re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.MULTILINE).strip()


def _parse_briefing_response(text: str, fecha: str) -> MorningBriefing:
    """Parsea el JSON · si falla devuelve briefing degradado conservador."""
    cleaned = _strip_markdown_fences(text)
    try:
        data = json.loads(cleaned)
        if not isinstance(data, dict):
            raise ValueError("response no es objeto")
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("strategist_parse_failed", extra={"error": str(exc), "preview": cleaned[:200]})
        return MorningBriefing(
            fecha=fecha,
            mercado_24h=Mercado24h(nuevos_skus=0, bajas_precio=0, nuevas_promos=0),
            acciones_del_dia=[],
            estado_mercado="Briefing no se pudo generar · respuesta del modelo no parseable. Revisar logs.",
        )

    mercado_raw = data.get("mercado_24h") or {}
    mercado = Mercado24h(
        nuevos_skus=int(mercado_raw.get("nuevos_skus") or 0),
        bajas_precio=int(mercado_raw.get("bajas_precio") or 0),
        nuevas_promos=int(mercado_raw.get("nuevas_promos") or 0),
    )

    acciones_raw = data.get("acciones_del_dia") or []
    acciones: list[AccionRecomendada] = []
    for a in acciones_raw[:3]:  # Cap a 3 según ROG
        if not isinstance(a, dict):
            continue
        prioridad = a.get("prioridad", "Media")
        if prioridad not in ("Alta", "Media", "Baja"):
            prioridad = "Media"
        acciones.append(
            AccionRecomendada(
                accion=str(a.get("accion") or "")[:300],
                justificacion=str(a.get("justificacion") or "")[:500],
                impacto_esperado=str(a.get("impacto_esperado") or "")[:300],
                prioridad=prioridad,  # type: ignore[arg-type]
            )
        )

    return MorningBriefing(
        fecha=str(data.get("fecha") or fecha),
        mercado_24h=mercado,
        acciones_del_dia=acciones,
        estado_mercado=str(data.get("estado_mercado") or "")[:1000],
    )


class StrategistAgent:
    """Genera el morning briefing con Claude Sonnet 4.6 · prompt cacheado."""

    def __init__(
        self,
        anthropic_client: Any | None = None,
        *,
        api_key: str = "",
        model: str = SONNET_MODEL,
    ) -> None:
        if anthropic_client is not None:
            self._client = anthropic_client
        elif api_key:
            from anthropic import AsyncAnthropic  # lazy import
            self._client = AsyncAnthropic(api_key=api_key)
        else:
            raise RuntimeError(
                "StrategistAgent requiere ANTHROPIC_API_KEY (env var) "
                "o un anthropic_client inyectado · sin uno no se puede generar briefing"
            )
        self._model = model

    async def generate_morning_briefing(
        self,
        db: AsyncIOMotorDatabase,
        workspace_id: str,
        *,
        signals: _Signals | None = None,
        memory_agent: Any | None = None,
    ) -> MorningBriefing:
        """Recolecta signals (o usa override), llama Claude, parsea, devuelve briefing.

        Si `memory_agent` se pasa (y está enabled), `gather_signals` enriquece
        con productos/ads semánticamente relacionados · Build 3.2.
        """
        if signals is None:
            signals = await gather_signals(db, workspace_id, memory_agent=memory_agent)

        fecha = datetime.now(tz=UTC).strftime("%Y-%m-%d")
        user_message = (
            f"Genera el Morning Briefing para RODDOS del {fecha}.\n\n"
            f"Workspace: {workspace_id}\n\n"
            f"Señales de las últimas 24 horas:\n```json\n"
            f"{json.dumps(signals.to_user_payload(), indent=2, default=str)}\n```\n\n"
            "Responde con el JSON MorningBriefing exacto."
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
        except Exception as exc:  # noqa: BLE001
            logger.exception("strategist_api_call_failed")
            return MorningBriefing(
                fecha=fecha,
                mercado_24h=Mercado24h(
                    nuevos_skus=len(signals.new_products),
                    bajas_precio=sum(1 for c in signals.price_changes if c.get("delta_pct", 0) < 0),
                    nuevas_promos=len(signals.new_ads),
                ),
                acciones_del_dia=[],
                estado_mercado=f"Briefing no generado · API error ({type(exc).__name__}). Revisar logs.",
            )

        text = ""
        with contextlib.suppress(AttributeError, IndexError, TypeError):
            text = response.content[0].text or ""

        briefing = _parse_briefing_response(text, fecha)
        usage = getattr(response, "usage", None)
        if usage is not None:
            briefing.tokens_input = int(getattr(usage, "input_tokens", 0) or 0)
            briefing.tokens_output = int(getattr(usage, "output_tokens", 0) or 0)
        briefing.modelo_usado = self._model
        return briefing
