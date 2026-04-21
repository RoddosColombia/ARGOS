# Phase 3 — WhatsApp Agent + KYC Conversacional + Flujos F1/F2/F3/F4

## Objetivo declarado
Activar el canal WhatsApp como frontend comercial completo. Cliente puede iniciar conversación, cotizar moto o repuesto, hacer KYC conversacional, recibir aprobación de crédito, y pagar — todo sin salir de WhatsApp. Score Engine de Phase 2 se conecta al WhatsApp Agent.

## Pre-requisitos
- Phase 2 cerrada (Score Engine operativo)
- Wava onboarding completado (necesario para link de pago al cierre de venta)
- Mercately operativo y compartido con SISMO (ya estaba desde SISMO Build 14)

## Builds incluidos
- Build 3.1 — WhatsApp Agent base (Mercately webhook + outbound)
- Build 3.2 — Intent classifier con Haiku 4.5
- Build 3.3 — Skill cotizador_visual (imagen + audio con Whisper)
- Build 3.4 — Skill kyc_conversacional con WhatsApp Flows nativos
- Build 3.5 — Integración WhatsApp Agent ↔ Score Engine
- Build 3.6 — Integración Wava para link de pago de inicial moto y ventas repuestos
- Build 3.7 — Flujos F1, F2, F3, F4 end-to-end con tests
- Build 3.8 — Skill negociacion_margen con Compliance validando piso
- Build 3.9 — Dashboard /whatsapp con métricas de conversaciones

## Decisiones arquitectónicas · Cambios en canónicas · Errores · Deuda · Métricas · Aprendizajes
(a llenar durante ejecución)

## Métricas objetivo
- 20 conversaciones de prueba con outcome etiquetado (WA-10)
- KYC conversacional completado en < 6 min promedio
- Primera venta real de repuesto cerrada por WhatsApp
- Primer Crédito Rodante aprobado vía WhatsApp flujo F3

## Cierre
- Fecha: _pendiente_ · Cerrado por: _pendiente_ · PR final: _pendiente_
