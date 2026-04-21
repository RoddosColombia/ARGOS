# Phase 4 — Cobranza Recurrente RADAR + Wava + WhatsApp (Flujo F5)

## Objetivo declarado
Cerrar el ciclo financiero. RADAR (en SISMO V2) genera cobros semanales; ARGOS recibe el trigger, llama a Wava para generar link Nequi/Daviplata, WhatsApp Agent lo envía al cliente, cliente paga, Wava notifica, ARGOS confirma al cliente, RADAR actualiza saldo en loanbook.

## Pre-requisitos
- Phase 3 cerrada (WhatsApp Agent + Wava integration para pagos ya funciona)
- SISMO V2 expuso endpoint POST /api/v1/cobranza/cobro + POST /api/v1/cobranza/pago-confirmado
- Al menos 1 cliente con crédito activo en SISMO (idealmente cliente de Phase 3)

## Builds incluidos
- Build 4.1 — Cobranza Orchestrator (recibe cobros de RADAR · dispara Wava · dispara WhatsApp)
- Build 4.2 — Templates Meta aprobados para recordatorios de cuota (suave, medio, firme)
- Build 4.3 — Webhook Wava → ARGOS con HMAC + confirmación a SISMO
- Build 4.4 — Escalamiento automático a operador humano en morosidad 5+ días
- Build 4.5 — Dashboard /cobranza con estado de cuotas por cliente
- Build 4.6 — Tests F5 end-to-end

## Métricas objetivo
- 100% de pagos recibidos por Wava confirmados a SISMO sin lag
- Recordatorio suave enviado 24h después de vencimiento
- Tasa de pago on-time capturada como baseline
- Cero pagos perdidos por errores de sincronización

## Cierre
- Fecha: _pendiente_ · Cerrado por: _pendiente_ · PR final: _pendiente_
