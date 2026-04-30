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

## Endpoints SISMO V2 que ARGOS escribe (escritura) · AMPLIADO Phase 2.5

> **Actualizado en Phase 2.5 · Build 2.5.1 (2026-04-29)** para automatización completa de venta de repuestos y motos. Spec de los 4 endpoints write que SISMO debe exponer en paralelo a Capa 0/1 de ARGOS. Coordinación con equipo SISMO arranca esta semana.

> Auth: Bearer **SISMO_TO_ARGOS_WRITE** (key separada de READ).
> Idempotency: todos los endpoints aceptan `Idempotency-Key` header. SISMO devuelve la misma response si el key se repite dentro de 24h.
> Retry: ARGOS reintenta con backoff exponencial (1s, 4s, 16s) en 5xx. En 4xx NO reintenta.

### 1. POST /api/sismo/invoices · facturación automática post-Wava

**Cuándo**: WhatsApp Agent recibe webhook Wava `payment.success` → ARGOS valida → llama a SISMO.

```
POST {SISMO_URL}/api/sismo/invoices
Authorization: Bearer SISMO_TO_ARGOS_WRITE
Idempotency-Key: payment_ref_wava (string, max 100 chars)
Content-Type: application/json
```

**Request body:**

```json
{
  "channel": "argos_whatsapp",
  "customer_id_sismo": "C-12345 | null si cliente nuevo",
  "customer_data_si_nuevo": {
    "phone": "+573001234567",
    "nombre": "string",
    "email": "string nullable",
    "ciudad": "string",
    "tipo_documento": "CC | CE",
    "numero_documento": "string"
  },
  "line_items": [
    {
      "sku": "PST-BJ-BX100-01",
      "nombre_descriptivo": "Pastillas freno Bajaj Boxer 100",
      "quantity": 1,
      "unit_price": 45000,
      "discount_pct": 0
    }
  ],
  "subtotal": 45000,
  "iva": 8550,
  "total": 53550,
  "payment_ref": {
    "provider": "wava",
    "transaction_id": "wva_tx_abc123",
    "metodo": "nequi | daviplata",
    "amount_received": 53550,
    "received_at": "ISO 8601 UTC"
  },
  "argos_metadata": {
    "conversation_id": "ULID",
    "recommendation_id_origen": "ULID nullable · si la venta vino de F6",
    "score_engine_solicitud_id": "SCR-ARGOS-... nullable · si fue venta a crédito"
  }
}
```

**SISMO valida**:
- Stock real disponible para todos los `sku` del `line_items` en bodega activa
- Precio vigente vs precio recibido (alertar si delta > 5% por security)
- Customer activo y no bloqueado
- `payment_ref.amount_received` == `total`
- Idempotency: si el `payment_ref.transaction_id` ya está facturado, devolver mismo `invoice_number` (no duplicar)

**Response success (201)**:

```json
{
  "invoice_number": "FAC-2026-001234",
  "customer_id_sismo": "C-12345 (creado si era nuevo)",
  "facturado_at": "ISO 8601 UTC",
  "stock_descontado": [{"sku": "...", "remaining_stock": 79}]
}
```

**Response error (4xx)**:

```json
{
  "error_code": "STOCK_INSUFFICIENT | PRICE_MISMATCH | CUSTOMER_BLOCKED | PAYMENT_AMOUNT_MISMATCH",
  "message": "string",
  "details": {}
}
```

**ARGOS comportamiento si falla**:
- 422 stock insuficiente: notificar al cliente "se agotó mientras procesábamos · te devolvemos el dinero" + cancelar Wava + audit_log
- 422 price mismatch: alerta operativa al CGO · NO facturar · NO devolver dinero (security incident)
- 5xx: queue persistida `pending_invoicing` con retry hasta 4h · si persiste, notificación al equipo

### 2. POST /api/sismo/customers/activate · activación cliente nuevo F4 cash

**Cuándo**: F4 venta cash a cliente nuevo no-RODDOS, después de RiskSeal antifraude OK pero ANTES de Wava (para que el customer exista en SISMO al momento de facturar).

```
POST {SISMO_URL}/api/sismo/customers/activate
Authorization: Bearer SISMO_TO_ARGOS_WRITE
Idempotency-Key: phone_number (string E.164)
```

**Request**:

```json
{
  "channel": "argos_whatsapp",
  "phone": "+573001234567",
  "nombre_completo": "string",
  "email": "string nullable",
  "ciudad": "string",
  "tipo_documento": "CC | CE",
  "numero_documento": "string",
  "fecha_nacimiento": "YYYY-MM-DD nullable",
  "ocupacion_tipo": "empleado | independiente | delivery | mototaxi | otro",
  "moto_modelo": "string nullable · si lo declaró",
  "moto_anio": "number nullable",
  "riskseal_validation": {
    "estado": "ok",
    "digital_score": 85,
    "fraud_flag": false,
    "consultado_at": "ISO 8601 UTC"
  },
  "argos_metadata": {
    "conversation_id": "ULID",
    "captured_via": "whatsapp_first_purchase"
  }
}
```

**Response success (201 nuevo · 200 ya existía)**:

```json
{
  "customer_id_sismo": "C-12345",
  "es_nuevo": true,
  "creado_at": "ISO 8601 UTC"
}
```

**Idempotency por phone**: si `phone` ya existe, devolver el `customer_id_sismo` existente con `es_nuevo: false`. NO duplicar.

### 3. POST /api/sismo/loans/initiate · iniciación de loan F2 motos

**Cuándo**: F2 venta de moto, después de Score Engine aprueba + Wava confirma cuota inicial. SISMO inicia el loan en su loanbook.

```
POST {SISMO_URL}/api/sismo/loans/initiate
Authorization: Bearer SISMO_TO_ARGOS_WRITE
Idempotency-Key: score_engine_solicitud_id
```

**Request**:

```json
{
  "channel": "argos_whatsapp",
  "score_engine_solicitud_id": "SCR-ARGOS-2026-1234",
  "customer_id_sismo": "C-12345",
  "producto": "rdx_leasing | rodante",
  "moto_modelo": "TVS Raider 125",
  "moto_pvp": 7800000,
  "monto_aprobado": 7800000,
  "plan_cuotas": {
    "numero_cuotas": 12,
    "valor_cuota": 720000,
    "frecuencia": "semanal | quincenal | mensual"
  },
  "cuota_inicial": {
    "monto": 1500000,
    "payment_ref": {
      "provider": "wava",
      "transaction_id": "wva_tx_xyz",
      "metodo": "nequi | daviplata",
      "received_at": "ISO 8601 UTC"
    }
  },
  "argos_metadata": {
    "conversation_id": "ULID",
    "kyc_completion_at": "ISO 8601 UTC",
    "auco_validation_score": 95
  }
}
```

**Response success (201)**:

```json
{
  "loan_id": "LN-2026-000456",
  "customer_id_sismo": "C-12345",
  "saldo_inicial": 6300000,
  "primera_cuota_vence": "YYYY-MM-DD",
  "iniciado_at": "ISO 8601 UTC",
  "logistics_task_id": "LOG-2026-789 · tarea creada en sistema interno para coordinación entrega"
}
```

**SISMO también dispara**:
- Notificación al equipo de logística (vía su propio canal interno) con `loan_id` + `customer_data` + `moto_data`
- Programación de cobranza en RADAR (porque cobranza vive en SISMO post-Visión 2.1)

ARGOS solo confirma a cliente vía WhatsApp + cierra conversación con `outcome: vendio_moto`.

### 4. POST /api/sismo/payments/confirm · confirmación de pago Wava (cobranza fuera de scope, pero F2/F3/F4 cuotas iniciales sí pasan por acá)

**Cuándo**: Wava webhook entra a ARGOS. ARGOS confirma a SISMO para que SISMO actualice el saldo del loan o registre el pago de la venta cash.

```
POST {SISMO_URL}/api/sismo/payments/confirm
Authorization: Bearer SISMO_TO_ARGOS_WRITE
Idempotency-Key: wava_transaction_id
```

**Request**:

```json
{
  "channel": "argos_whatsapp",
  "wava_transaction_id": "wva_tx_abc",
  "customer_id_sismo": "C-12345",
  "monto_recibido": 720000,
  "metodo": "nequi | daviplata",
  "concepto": "venta_repuesto | cuota_inicial_moto | cuota_loan_post_inicial",
  "referencia_relacionada": {
    "tipo": "invoice | loan",
    "id": "FAC-2026-001234 | LN-2026-000456"
  },
  "received_at": "ISO 8601 UTC"
}
```

**Response success (200)**:

```json
{
  "registrado": true,
  "nuevo_saldo": "number nullable · si era cuota de loan, saldo_actualizado",
  "estado_invoice": "string nullable · si era pago de venta directa, estado actualizado"
}
```

**Importante**: para **cuotas posteriores de un loan ya activo** (cobranza recurrente), este endpoint **NO se usa desde ARGOS**. Esa interacción es Wava → SISMO directamente, vivida íntegra dentro de SISMO (Visión 2.1 sec 4.7). ARGOS solo usa `/payments/confirm` para los 3 casos de cierre de venta inicial: venta cash repuestos, cuota inicial de moto, pago directo F3.

## Endpoints OBSOLETOS · Cobranza queda en SISMO (Visión 2.1)

> ⛔ **Movidos fuera de ARGOS**. SISMO maneja cobranza recurrente íntegra con su integración Mercately propia (Build 14) + Wava + RADAR. ARGOS no recibe estos webhooks.

```
POST {ARGOS_URL}/api/v1/cobranza/cobro                 ⛔ obsoleto
POST {ARGOS_URL}/api/v1/cobranza/pago-confirmado       ⛔ obsoleto
POST {ARGOS_URL}/api/v1/cobranza/morosidad-detectada   ⛔ obsoleto
```

Esto significa: SISMO V2 NO debería enviar más estos webhooks a ARGOS. Coordinación con equipo SISMO para deprecar el dispatcher.

## Política de fallos cruzados (actualizada)

| Escenario | Comportamiento |
|-----------|----------------|
| SISMO V2 caído cuando ARGOS quiere leer inventario | ARGOS usa último snapshot cacheado · WhatsApp Agent advierte "stock no actualizado" antes de cerrar venta |
| SISMO V2 caído cuando ARGOS quiere POST `/invoices` | Wava ya confirmó pago. ARGOS encola en `pending_invoicing` con retry exponencial. Cliente recibe respuesta WhatsApp "tu pago se recibió, factura en breve". Si falla 4h, notificación operativa. |
| SISMO V2 caído cuando ARGOS quiere POST `/loans/initiate` | Wava ya cobró cuota inicial. Idem queue retry. Notificación operativa después de 1h porque es venta de moto (alto stake). |
| SISMO V2 caído cuando ARGOS quiere POST `/customers/activate` | Bloquea continuación de F4. Cliente queda en estado "verificando, te confirmamos en minutos". Retry 15 minutos hasta 1h. |
| Cualquier write devuelve 422 PRICE_MISMATCH | Security alert al CGO + CEO. Cliente recibe handoff a operador humano. NO se factura ni devuelve dinero unilateralmente. |
| Wava caído | F2/F3/F4 quedan en queue de Wava. Cliente recibe "estamos generando tu link de pago, en minutos te llega". Si Wava no recupera en 30 min, fallback a transferencia manual + notificación operativa. |

## Política de versionado

Versionar TODAS las APIs cruzadas con prefijo `/api/sismo/v1/`. Cualquier cambio breaking: bump a `/api/sismo/v2/` con periodo de coexistencia mínimo de 30 días y migración documentada en docs/claude/ de ambos repos.

## Checklist coordinación con equipo SISMO (acción CEO esta semana)

- [ ] Kick-off meeting con líder técnico de SISMO V2
- [ ] Compartir esta canónica como spec de los 4 endpoints write
- [ ] Definir milestone de SISMO: 4 endpoints en producción dentro de 3 semanas (alineado con cierre de Capa 0 de ARGOS)
- [ ] Acordar setup de webhook signing key (`SISMO_TO_ARGOS_WRITE` y reciprocity)
- [ ] Coordinar deprecation de los 3 webhooks de cobranza (SISMO → ARGOS) que ya no se usan
- [ ] Acordar formato de Idempotency-Key (recomendado UUID v7 o ULID)
- [ ] Definir contact / canal de escalamiento para incidentes en producción

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
