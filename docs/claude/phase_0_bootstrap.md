# Phase 0 — Bootstrap de infraestructura

## Objetivo declarado
Infraestructura base operativa + credenciales ARGOS creadas dentro de BM/MCC existentes de RODDOS + estructura de carpetas docs/canonicas + docs/claude + docs/knowledge creada y commiteada.

## Pre-requisitos
- 10 decisiones del CEO respondidas (ver Visión 2.0 sección 8)
- Cuentas creadas: Mercately access (vía SISMO ya existente), AUCO access (vía admin web ya existente), Wava (nueva), RiskSeal (nueva), Palenca (nueva), Anthropic, Apify, ProxyRack, TikHub, SerpAPI
- Dominio argos.roddos.com listo en GoDaddy
- MongoDB Atlas M2 cluster argos-prod creado
- Render workspace creado

## Builds incluidos en Phase 0
- Build 0.1 — Repo scaffold + estructura carpetas docs/ + CLAUDE.md raíz
- Build 0.2 — FastAPI base + JWT auth + endpoint /api/v1/health
- Build 0.3 — MongoDB connection + workspaces + users colecciones
- Build 0.4 — React 19 + Vite + estructura base frontend interno
- Build 0.5 — GitHub Actions CI/CD + autodeploy Render
- Build 0.6 — Dominio argos.roddos.com con SSL Let's Encrypt
- Build 0.7 — Langfuse self-hosted en Render para observabilidad LLM
- Build 0.8 — System User ARGOS en BM existente + Service Account ARGOS en MCC existente (credenciales separadas · preserva histórico · cumple ROG-A11 por aislamiento de credencial no de cuenta)
- Build 0.9 — Captura de baseline operativo desde SISMO V2

## Decisiones arquitectónicas tomadas
(a llenar durante la ejecución)

## Cambios en canónicas
(a llenar durante la ejecución)

## Errores cometidos y cómo se resolvieron
(a llenar durante la ejecución)

| Error | Causa raíz | Solución | Prevención futura |
| --- | --- | --- | --- |
| (vacío) | | | |

## Deuda técnica generada
(a llenar durante la ejecución)

## Métricas de la fase
- Deploy verde: ⬜
- Autodeploy en push a main < 5 min: ⬜
- /api/v1/health responde 200: ⬜
- Login con workspace RODDOS funcional: ⬜
- System User + Service Account ARGOS creados con credenciales separadas: ⬜
- Baseline operativo capturado: ⬜

## Aprendizajes
(a llenar al cierre)

## Cierre
- Fecha cierre: _pendiente_
- Cerrado por: _pendiente_
- PR final: _pendiente_
