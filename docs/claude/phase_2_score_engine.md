# Phase 2 — Score Engine Clonado dentro de ARGOS

## Objetivo declarado
Replicar dentro de ARGOS el motor de score del Build 20 del admin web (www.roddos.com). Misma lógica, mismos partners (AUCO, Palenca, RiskSeal nuevo, process_document_chat), mismos pesos del scorecard, misma salida 0-1000. Instancia totalmente separada (clon · ROG-S1). Loanbook SISMO compartido read-only para entrenamiento XGBoost (ROG-S2). **NO se conecta a WhatsApp todavía** (eso es Phase 3). En Phase 2 se expone vía API REST y se testea con solicitudes sintéticas + manuales desde el /dashboard.

## Pre-requisitos
- Phase 1 cerrada
- SISMO V2 endpoint /api/loanbook/snapshot operativo
- Cuenta RiskSeal creada + PoC ejecutada exitosamente
- Credenciales AUCO + Palenca replicadas (separadas del admin web · ROG-A11)
- Cuenta Wava onboarding completado (para Phase 3 no es bloqueante, pero bueno adelantar)

## Builds incluidos
- Build 2.1 — Integración RiskSeal (nueva)
- Build 2.2 — Integración AUCO (clonada del admin web · credenciales separadas)
- Build 2.3 — Integración Palenca (clonada)
- Build 2.4 — process_document_chat (clonada)
- Build 2.5 — Capa 1 XGBoost con scorecard manual fallback · entrenamiento weekly desde loanbook
- Build 2.6 — Capa 2 Claude Sonnet razonamiento cualitativo + narrativa auditable
- Build 2.7 — Endpoint /api/v1/scoring/solicitar + dashboard /scoring
- Build 2.8 — Reglas duras (ROG-S3) + reglas de producto (RDX Leasing 650, Rodante 500, bypass A+)
- Build 2.9 — Tests SC-01 a SC-19 pasando

## Decisiones arquitectónicas tomadas
(a llenar)

## Cambios en canónicas
(eventos Score Engine, colección scoring_solicitudes, apis_externas: RiskSeal/AUCO/Palenca · ya documentados como spec)

## Errores cometidos y cómo se resolvieron

| Error | Causa raíz | Solución | Prevención futura |
| --- | --- | --- | --- |
| (vacío) | | | |

## Deuda técnica generada

## Métricas de la fase
- 19 tests SC pasando: ⬜
- Tiempo evaluación < 300 seg en 10 solicitudes sintéticas: ⬜
- Dashboard /scoring carga con KPIs reales: ⬜
- Modelo XGBoost entrenado con cartera completa SISMO (snapshot inicial): ⬜
- Reglas duras funcionan (no llaman a Claude si AUCO<70 o RiskSeal fraud): ⬜

## Aprendizajes
(al cierre)

## Cierre
- Fecha cierre: _pendiente_
- Cerrado por: _pendiente_
- PR final: _pendiente_
