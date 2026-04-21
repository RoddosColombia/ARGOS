# Phase 1 — Marketplace MELI + Trends + Briefing v1 + SISMO Read + Impact Tracking

## Objetivo declarado
Primera fase funcional. Marketplace Agent consume MELI, Trends consume SerpAPI, Strategist genera briefing v1 diario, SISMO expuso 4 endpoints de lectura y ARGOS los consume. Impact tracking cierra el loop: recomendación aprobada hoy → medición automática en T+7 desde SISMO sales.

## Pre-requisitos
- Phase 0 cerrada con tag `phase-0-closed`
- SISMO V2 expuso endpoints /api/inventory/repuestos, /api/inventory/motos, /api/sales/daily, /api/loanbook/snapshot, /api/customers/{id}
- App reviews Meta y Google siguen en curso (no bloquean Phase 1)

## Builds incluidos
- Build 1.1 — Marketplace Agent con MELI SDK oficial
- Build 1.2 — Trends Agent con SerpAPI
- Build 1.3 — Scout Agent básico con Haiku 4.5
- Build 1.4 — Strategist Agent v1 (sin GraphRAG · eso llega Phase 5)
- Build 1.5 — Executive Agent + frontend /briefing
- Build 1.6 — Integración SISMO lectura · sync nightly
- Build 1.7 — Impact tracking · job que mide actual_impact en T+7 desde SISMO sales
- Build 1.8 — Morning Briefing diario v1 publicado a las 05:30
- Build 1.9 — Compliance Officer básico (solo caps spending · sin caps WhatsApp todavía)

## Decisiones arquitectónicas tomadas
(a llenar durante ejecución)

## Cambios en canónicas
(eventos, APIs, colecciones agregadas o modificadas)

## Errores cometidos y cómo se resolvieron

| Error | Causa raíz | Solución | Prevención futura |
| --- | --- | --- | --- |
| (vacío al iniciar) | | | |

## Deuda técnica generada
(a llenar)

## Métricas de la fase
- Briefing diario publicado 7/7 días consecutivos: ⬜
- SISMO sync nightly sin fallos durante una semana: ⬜
- Al menos 5 recomendaciones generadas · 3 aprobadas · 2 medidas con actual_impact: ⬜
- Hit rate inicial capturado (sample pequeño, pero baseline): ⬜

## Aprendizajes
(a llenar al cierre)

## Cierre
- Fecha cierre: _pendiente_
- Cerrado por: _pendiente_
- PR final: _pendiente_
