# docs/canonicas/integraciones_sismo.md

Mapa específico de la integración ARGOS ⇄ SISMO V2.

Principio: aislamiento de credenciales y blast radius (ROG-A11), comunicación vía APIs autenticadas con keys dedicadas por dirección de tráfico.

## Direcciones de tráfico

```
SISMO V2  ←  lectura  ←  ARGOS    (key: SISMO_TO_ARGOS_READ)
SISMO V2  ←  escritura ← ARGOS    (key: SISMO_TO_ARGOS_WRITE)
ARGOS     ←  webhook  ←  SISMO V2 (key: SISMO_OUTBOUND)
```

Cada key vive en secrets manager separado y rota mensualmente.

## Endpoints SISMO V2 que ARGOS consume (lectura)

Estos endpoints debe exponer SISMO V2 (trabajo paralelo a Phase 0 de ARGOS, ~2-3 días sobre el repo SISMO).

### Inventario de repuestos

```
GET /api/inventory/repuestos
Query params: ?categoria=&compatible_moto=&en_stock=true&page=&limit=
Response: {
  items: [{sku, nombre, categoria, stock, costo, precio, dias_inventario, compatible_motos}],
  pagination: {...}
}
Frecuencia: ARGOS sincroniza cada 15 min para SKUs activos, nightly full
Auth: Bearer SISMO_TO_ARGOS_READ
```

### Inventario de motos

```
GET /api/inventory/motos
Response: {
  items: [{modelo, marca, anio, color, stock, pvp, cuotas: {9: x, 12: y, 18: z}}],
  total: 4 max (foco TVS Raider, hasta 4 modelos a futuro)
}
Frecuencia: ARGOS sincroniza nightly
```

### Slow movers (repuestos sin rotación)

```
GET /api/inventory/slow_movers?dias_min=45
Response: {
  items: [{sku, nombre, dias_sin_rotacion, stock, valor_inmovilizado}]
}
Frecuencia: ARGOS sincroniza diaria (alimenta Strategist para promos)
```

### Ventas diarias

```
GET /api/sales/daily?date=YYYY-MM-DD
Response: {
  date,
  total_amount,
  ventas_motos: [{modelo, customer_id, monto, financiado: bool}],
  ventas_repuestos: [{sku, customer_id, monto, cantidad, financiado}]
}
Frecuencia: ARGOS sincroniza diaria a las 02:00 (hora Bogotá)
Uso: impact tracking de recomendaciones (campo actual_impact en collection recommendations)
```

### Historial de comportamiento de pago (para bypass F3)

```
GET /api/loanbook/comportamiento-pago/{customer_id}
Response: {
  customer_id,
  tiene_creditos_activos: bool,
  tiene_creditos_historicos: bool,
  total_cuotas_programadas,
  total_cuotas_pagadas_on_time,
  total_cuotas_pagadas_tardias,
  total_cuotas_vencidas_actualmente,
  dpd_actual,
  dpd_maximo_historico,
  score_comportamental_derivado: "A+" | "A" | "B" | "C" | "D" | "E",
  reglas_derivacion: string,  // explicación de cómo se derivó el score
  monto_total_pagado_historico,
  monto_en_mora_actual,
  fecha_primer_credito,
  fecha_ultima_cuota_pagada
}
Frecuencia: ARGOS consulta en tiempo real cuando WhatsApp Agent evalúa aplicar bypass en F3
Uso: Score Engine decide si aplicar umbral 400 (A+/A/B con bypass) o umbral 500 normal
Notas:
  - SISMO V2 deriva score_comportamental desde el historial de cuotas · NO es un score del motor de scoring
  - Reglas de derivación simples por ahora (ej: 0 cuotas tardías + 6+ pagadas = A+ · 1-2 tardías = A · 3+ tardías = B · cualquier default = C/D/E)
  - A medida que ARGOS acumule decisiones propias, Score Engine evaluará mejorar el score_comportamental con datos adicionales
```

### Motor de score · NO vive en SISMO V2

El motor de scoring (Build 20) vive en el admin web de www.roddos.com/admin. SISMO V2 es contabilidad/cartera/cobranza (loanbook + RADAR). ARGOS replica la lógica del motor del admin como clon independiente (ROG-S1). Ambos motores escriben el resultado final de su decisión a SISMO cuando la venta se concreta (vía POST /api/argos/score-result), pero el cálculo del score sucede en cada motor por separado.

### Promos vigentes

```
GET /api/promos/active
Response: {
  promos: [{promo_id, sku, descuento_pct, vigencia_desde, vigencia_hasta, condiciones}]
}
Frecuencia: ARGOS sincroniza cada hora
Uso: WhatsApp Agent las menciona al cotizar; Strategist las considera al recomendar
```

### Customer profile

```
GET /api/customers/{customer_id}
Response: {
  customer_id, nombre, telefono, email, ciudad,
  primera_compra_at, ultima_compra_at,
  total_compras, total_gastado,
  motos_compradas: [{modelo, fecha, credito_id}],
  repuestos_comprados: [{sku, fecha, cantidad, monto}],
  score_comportamental: A+/A/B/C/D/E,
  cuotas_status: {al_dia: int, vencidas: int, total_credito: int},
  customer_lifetime_value: float
}
Uso: WhatsApp Agent personaliza atención · Score Engine consulta para bypass de umbral
```

## Endpoints SISMO V2 que ARGOS escribe (escritura)

Auth: Bearer SISMO_TO_ARGOS_WRITE (key separada de READ)

### Recomendaciones publicadas

```
POST /api/argos/recommendations
Body: {
  recommendation_id, type, sku_affected, action_description,
  rationale, expected_impact, priority_score
}
Response: 201 Created
Uso: SISMO V2 las muestra en su UI de operación · ROG-A12 audit
```

### Acciones ejecutadas

```
POST /api/argos/actions_executed
Body: {
  action_id, type: pricing_change/promo/campaign/...,
  sku_affected, executed_at, value, channel
}
Uso: trazabilidad para ROAS y CFO
```

### Resultado de Score Engine

```
POST /api/argos/score-result
Body: {
  solicitud_id_argos: 'SCR-ARGOS-2026-XXXX',
  customer_id (si nuevo, SISMO crea contact),
  origen: 'argos_whatsapp',
  producto, monto_solicitado, monto_aprobado,
  decision, score_final, categoria_riesgo,
  narrativa, evaluado_en, modelo_version_hash
}
Uso: SISMO V2 registra la solicitud en su loanbook si fue aprobada y se desembolsa
Notas: 
  - El motor del admin web hace exactamente la misma escritura con origen 'web' (clones)
  - SISMO mantiene ambos orígenes en el mismo loanbook (cartera unificada)
```

### Customer creation

```
POST /api/argos/customer
Body: {phone, nombre, email, ciudad, kyc_data...}
Response: {customer_id}
Uso: cuando WhatsApp Agent identifica un cliente nuevo no existente en SISMO
```

## Endpoints ARGOS que SISMO V2 consume (webhook entrante)

Auth: Bearer SISMO_OUTBOUND

### Cobro programado por RADAR

```
POST {ARGOS_URL}/api/v1/cobranza/cobro
Body: {
  customer_id_sismo,
  customer_phone,
  credito_id,
  cuota_numero,
  monto,
  fecha_vencimiento,
  producto: rdx_leasing/rodante
}
Response: 200 OK
Uso: ARGOS dispara generación de link Wava + envío WhatsApp
Frecuencia: cada cuota semanal por cada cliente activo
```

### Pago confirmado en RADAR (post Wava)

```
POST {ARGOS_URL}/api/v1/cobranza/pago-confirmado
Body: {customer_id_sismo, credito_id, cuota_numero, monto_recibido, transaction_id}
Uso: ARGOS notifica al cliente por WhatsApp (cierra el ciclo)
```

### Notificación de morosidad

```
POST {ARGOS_URL}/api/v1/cobranza/morosidad-detectada
Body: {customer_id_sismo, credito_id, days_overdue, monto_acumulado}
Uso: ARGOS escala caso, intensifica recordatorios, eventualmente pasa a operador humano
```

## Política de fallos cruzados

| Escenario | Comportamiento |
|-----------|----------------|
| SISMO V2 caído cuando ARGOS quiere leer inventario | ARGOS usa último snapshot cacheado · WhatsApp Agent advierte "stock no actualizado" antes de cerrar venta |
| SISMO V2 caído cuando ARGOS quiere escribir score-result | ARGOS encola el resultado en `pending_sismo_writes` con retry exponencial · cliente recibe respuesta WhatsApp normalmente |
| ARGOS caído cuando SISMO V2 quiere notificar cobro | SISMO V2 reintenta con backoff · si pasa 1h sin éxito, escala vía email al operador humano |
| ARGOS caído cuando SISMO quiere notificar pago | SISMO persiste el pago en su loanbook · cliente no recibe confirmación inmediata por WhatsApp pero sí en próxima sincronización |
| Wava caído | RADAR pausa generación de cobros · alertas al CEO |

## Política de versionado

Versionar TODAS las APIs cruzadas con prefijo `/api/v1/`. Cualquier cambio breaking: bump a `/api/v2/` con periodo de coexistencia mínimo de 30 días y migración documentada en docs/claude/ de ambos repos.
