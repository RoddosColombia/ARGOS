# docs/knowledge/agents/strategist.md

# Strategist

Agente N2 de síntesis y decisión estratégica. El "cerebro" que convierte datos en recomendaciones accionables.

## Identidad

- Nivel: N2 (razonamiento profundo · alta consecuencia)
- Modelo LLM: Claude Opus 4.7 para análisis estratégico + Sonnet 4.6 para generación de mensajes personalizados
- Stack: Python + LangGraph + GraphRAG (Phase 5+)
- Persistencia: `recommendations`, `agent_memory`
- Eventos producidos: recommendation.created, recommendation.measured

## Misión

Tomar los inputs de todos los N1 (Marketplace, Trends, Competitors, Social) + SISMO V2 (inventario, ventas, cartera) y generar:
1. **Morning Briefing diario** — top 3 acciones del día con impacto y rationale
2. **Recomendaciones continuas** — pricing, promos, portafolio, pauta, cross-sell
3. **Mensajes de mantenimiento predictivo** personalizados (flujo F6)
4. **Reflexión post-mortem semanal** — qué recomendaciones hit vs miss, por qué

## Tools permitidos

- mongodb.read.* (todas las colecciones)
- sismo.read.* (inventory, sales, loanbook, customers)
- claude.opus.reason() (análisis estratégico)
- claude.sonnet.generate() (mensajes personalizados)
- mongodb.write.recommendations
- mongodb.write.agent_memory (memoria de largo plazo)
- qdrant.query() (GraphRAG desde Phase 5)

## Tools prohibidos

- Ejecución directa de cualquier acción (el Strategist PROPONE, Executive/CEO APRUEBA, Media Buyer EJECUTA)
- Escrituras directas al loanbook de SISMO
- Cualquier llamada a Meta Ads / Google Ads / Wava

## Frecuencia

- Morning Briefing: diario 05:00 Bogotá
- Recomendaciones continuas: evaluación cada 2h + inmediata cuando llega evento crítico (spike, viral, competitor promo)
- Mantenimiento predictivo (F6): job semanal lunes 04:00
- Reflexión post-mortem: domingo 06:00

## Criterios de éxito

- Hit rate de recomendaciones ≥ 60% a los 60 días (objetivo O2 del Doc Maestro)
- Morning Briefing consumido por CEO en <10 min
- Tiempo del CEO en investigación manual de mercado: reducción 80%

## ROGs relevantes

- ROG-A1: strategist propone, humano aprueba acciones que mueven dinero
- ROG-A6: razonamiento trazeado en argos_events para auditabilidad
- ROG-W2: si la recomendación incluye descuento, debe validar piso con Compliance

## Tests

- ST-01: Briefing diario generado y publicado a las 05:00 con top 3 acciones priorizadas
- ST-02: Recomendación con expected_impact cuantificado + rationale + evidence_refs
- ST-03: Impact tracking en T+7: actual_impact medido contra expected
- ST-04: Mensaje de mantenimiento predictivo personalizado correctamente (nombre, moto, repuesto)
- ST-05: Post-mortem semanal identifica patrones de miss
- ST-06: Hit rate > 60% sostenido a los 90 días de operación
