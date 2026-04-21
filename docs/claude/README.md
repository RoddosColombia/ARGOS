# docs/claude/

Bitácora arquitectónica del proyecto ARGOS. Una entrada por fase, una entrada por build crítico, y un catálogo de errores recurrentes que NO se deben volver a cometer.

Propósito: garantizar que cada decisión, cada error, cada solución quede registrado. Que el siguiente agente o desarrollador (humano o IA) que tome el proyecto pueda leer el contexto completo en orden y no repita errores ya resueltos.

## Archivos

| Archivo | Contenido |
|---------|-----------|
| README.md | Este archivo |
| phase_0_bootstrap.md | Bitácora de Phase 0: setup infraestructura |
| phase_1_marketplace.md | Bitácora de Phase 1: MELI scraping + briefing v1 + SISMO read + impact tracking |
| phase_2_score_engine.md | Bitácora de Phase 2: clonar Score Engine dentro de ARGOS |
| phase_3_whatsapp_kyc.md | Bitácora de Phase 3: WhatsApp Agent + KYC conversacional + flujos F1, F2, F3, F4 |
| phase_4_cobranza.md | Bitácora de Phase 4: Wava + RADAR + flujo F5 |
| phase_5_mantenimiento.md | Bitácora de Phase 5: flujo F6 + briefing v2 + GraphRAG |
| phase_6_fb_ads.md | Bitácora de Phase 6: FB Marketplace + Ad Intelligence |
| phase_7_social.md | Bitácora de Phase 7: Social Listening |
| phase_8_media_buyer.md | Bitácora de Phase 8: Media Buyer + CTW Ads + Compliance Officer en pauta |
| phase_9_comercial.md | Bitácora de Phase 9: comercialización a clientes externos |
| errores_recurrentes.md | Catálogo de errores cometidos + cómo NO repetirlos |

## Formato obligatorio de cada phase_X.md

Cada bitácora de fase sigue esta estructura:

```markdown
# Phase X — Título

## Objetivo declarado
(qué prometía esta fase al iniciarla)

## Pre-requisitos
(qué tenía que estar listo antes)

## Builds incluidos
- Build X.1: ...
- Build X.2: ...

## Decisiones arquitectónicas tomadas
(decisiones técnicas relevantes con justificación)

## Cambios en canónicas
(qué eventos, APIs, colecciones se agregaron o modificaron)

## Errores cometidos y cómo se resolvieron
| Error | Causa raíz | Solución | Prevención futura |

## Deuda técnica generada
(qué quedó pendiente conscientemente)

## Métricas de la fase
(KPIs efectivamente alcanzados vs declarados)

## Aprendizajes
(qué hacer diferente en próximas fases)

## Cierre
- Fecha cierre:
- Cerrado por:
- PR final:
```

## Reglas

1. **Cada PR que cierre un build actualiza la bitácora correspondiente en el mismo PR.** Sin excepciones.
2. **Los errores se registran inmediatamente, no a fin de fase.** Cuando un error cuesta >30 min de debug, se registra el mismo día.
3. **errores_recurrentes.md es la primera lectura de cualquier nuevo build.** Antes de empezar a codear, se lee este archivo para no repetir errores conocidos.
4. **Bitácora es WORM (write-once, read-many) en producción.** Cambios solo por PR aprobado. Nunca se reescribe historia.
5. **Las decisiones arquitectónicas se documentan con el formato:** problema → opciones consideradas → opción elegida → razón → trade-offs aceptados.
