# Phase 5 — Mantenimiento Predictivo + Briefing v2 LLM + GraphRAG (Flujo F6)

## Objetivo declarado
Activar el motor de revenue recurrente. Job semanal lunes 04:00 cruza customer_history × tabla de vida útil × uso intensivo y genera recomendaciones personalizadas de recompra. Strategist v2 usa Opus 4.7 + GraphRAG con Qdrant para razonamiento con contexto histórico profundo. Sistema de evals del Strategist activo.

## Pre-requisitos
- Phase 4 cerrada (cliente ya puede comprar, pagar cuotas, recibir confirmaciones)
- Al menos 50 clientes con repuestos comprados + histórico de 30+ días en ARGOS
- Qdrant operativo self-hosted en Render

## Builds incluidos
- Build 5.1 — Qdrant + embeddings de productos, ads, conversaciones
- Build 5.2 — Strategist v2 con GraphRAG
- Build 5.3 — Skill mantenimiento_predictivo
- Build 5.4 — Morning Briefing v2 con Opus 4.7 + contexto GraphRAG
- Build 5.5 — Sistema de evals offline del Strategist (hit rate, calidad narrativa, cost/decision)
- Build 5.6 — Canary de nuevas versiones de modelos LLM contra eval set
- Build 5.7 — Tabla de vida útil de SKUs + UI de configuración para CEO

## Métricas objetivo
- Primer batch de mensajes F6 enviados a 50+ clientes
- Tasa de respuesta > 20%
- Tasa respuesta → venta > 10%
- Hit rate del Strategist medido sobre muestra
- Briefing diario con calidad medible superior al v1

## Cierre
- Fecha: _pendiente_ · Cerrado por: _pendiente_ · PR final: _pendiente_
