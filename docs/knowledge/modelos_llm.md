# docs/knowledge/modelos_llm.md

# Modelos LLM Asignados por Agente

Política de asignación de modelos Claude a cada agente, con justificación de costo/capacidad/latencia.

## Matriz de asignación

| Agente / Skill | Modelo primario | Modelo fallback | Caching | Justificación |
|----------------|-----------------|-----------------|---------|---------------|
| Scout | Haiku 4.5 | Haiku 4.5 | ✅ | Clasificación binaria · barato · volumen alto |
| Marketplace | Sonnet 4.6 | Sonnet 4.6 | ✅ | Análisis de compatibilidad repuesto-moto · requiere razonamiento |
| Trends | Sonnet 4.6 | Haiku 4.5 | ✅ | Correlación keyword-SKU · razonamiento moderado |
| Competitors | Sonnet 4.6 | Opus 4.7 (cuando Strategist pide análisis profundo) | ✅ | Análisis de ads y estrategia competitiva |
| Social | Sonnet 4.6 multimodal | Sonnet 4.6 | ✅ | Vision para reels · análisis de contenido |
| Strategist | **Opus 4.7** (análisis estratégico) + Sonnet 4.6 (generación personalizada) | Sonnet 4.6 | ✅ agresivo | Razonamiento profundo · decisiones de alto impacto |
| Executive | Sonnet 4.6 | Sonnet 4.6 | ✅ | Resumen + presentación · no crítico razonamiento |
| Media Buyer | Sonnet 4.6 | Sonnet 4.6 | ✅ | Optimización de copy de ads |
| Compliance Officer | Sonnet 4.6 (casos ambiguos · 90% es código) | Sonnet 4.6 | ✅ | Revisión legal/ética cuando aplica |
| WhatsApp Agent | **Sonnet 4.6 multimodal** | Sonnet 4.6 text-only | ✅ agresivo | Conversación + vision + audio · core del negocio |
| Score Engine Capa 2 | **Sonnet 4.6** | Sonnet 4.6 | ✅ | Razonamiento crediticio auditable |
| Skill: intent classification (WhatsApp) | Haiku 4.5 | Haiku 4.5 | ✅ | Clasificación rápida · bajo costo |
| Skill: briefing generation | Opus 4.7 | Sonnet 4.6 | ✅ | Calidad > velocidad en producto estrella diario del CEO |
| Skill: mantenimiento predictivo (generación) | Sonnet 4.6 | Sonnet 4.6 | ✅ | Personalización · volumen alto |

## Versiones pineadas (actualizar cuando Anthropic saca nuevos)

```
SONNET_MODEL = "claude-sonnet-4-6-20260301"      # placeholder · pinear el real
HAIKU_MODEL = "claude-haiku-4-5-20251001"
OPUS_MODEL = "claude-opus-4-7-20260416"
```

**Regla inamovible:** NUNCA `claude-sonnet-latest` o `claude-opus-latest` en código de producción. Cualquier upgrade de versión pasa por canary con dataset de evals + PR review.

## Prompt caching

OBLIGATORIO en todo system prompt > 1000 tokens. Esto aplica a:
- Todos los agentes N1, N2, N3 tienen system prompt grande cacheado
- Skills del WhatsApp Agent (kyc_conversacional, negociacion_margen, cotizador_visual, recuperacion_carrito, mantenimiento_predictivo)
- Skill morning_briefing

Ahorro proyectado: 80-90% en input tokens de prompts recurrentes.

## Costos proyectados (USD/mes · operación normal post-Phase 5)

Asumiendo:
- 200 conversaciones WhatsApp/día (Sonnet multimodal)
- 50 solicitudes de crédito/día (Score Engine · Sonnet para Capa 2)
- 5K señales scout/día (Haiku)
- 1 briefing/día (Opus)
- Análisis N1 continuos (Sonnet con caching agresivo)
- 200 mensajes F6 semanales (Sonnet)
- Caching reduce input tokens en 85% promedio

| Modelo | Uso | Costo estimado |
|--------|-----|----------------|
| Sonnet 4.6 | WhatsApp Agent + Score Engine + N1 agents + skills | $80-100 |
| Haiku 4.5 | Scout + intent classification | $8-12 |
| Opus 4.7 | Strategist + briefing diario | $30-50 |
| Vision / Whisper / audio | Multimodal en WhatsApp + Score | $15-20 |
| **Total Anthropic** | | **$130-180 USD/mes** |

## Batch API

Usar Batch API (50% descuento, 24h) para:
- Reportes post-mortem semanales (domingo 04:00 · no urgente · procesa en batch)
- Re-análisis masivo de conversaciones para calibrar prompts
- Scoring de cartera histórica para entrenamiento XGBoost (no requiere real-time)

NO usar Batch API para:
- Conversaciones WhatsApp en vivo (necesita real-time)
- Score Engine (tiene objetivo <5 min)
- Briefing diario (necesita a las 05:00)

## Monitoreo via Langfuse

Cada llamada LLM registra:
- Modelo utilizado
- Latencia
- Tokens input (cacheado y no cacheado)
- Tokens output
- Costo
- Agente invocador
- Trace hasta el evento que disparó la llamada

Dashboard Langfuse alerta si:
- Costo diario > 2x baseline
- Latencia p95 > umbral por modelo
- Rate de errores API > 1%
- Drift detectado en outputs estructurados (schema fails)
