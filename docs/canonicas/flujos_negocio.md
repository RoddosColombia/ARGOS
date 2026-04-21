# docs/canonicas/flujos_negocio.md

Los 6 flujos de negocio expresados como secuencias de eventos del bus argos_events.

Notación: `EventType{payload-key}` → siguiente paso

Convención de actores en pasos:
- C = Cliente (humano por WhatsApp)
- W = WhatsApp Agent
- S = Score Engine
- M = Marketplace Agent / Strategist
- R = RADAR (en SISMO V2)
- WA = Wava
- P = Partner externo (AUCO, Palenca, RiskSeal)
- CEO = Andrés (humano vía web /briefing)
- OP = Operador humano (handoff)

---

## F1 — Onboarding y clasificación de intent

Disparador: cliente envía primer mensaje a WhatsApp de RODDOS.
Foco: capturar opt-in + clasificar intent + ruteo al flujo correcto.
Duración objetivo: < 30 segundos hasta primera respuesta útil.

```
Paso 1: C envía mensaje (texto/voz/imagen)
        → Mercately webhook
        → whatsapp.message.received{phone, content, message_type}

Paso 2: W consulta contacts por phone
        Si NO existe contact:
          - W crea contact con datos mínimos (phone)
          - W envía template "saludo + opt-in" (single tap "Sí, quiero recibir info")
          - whatsapp.message.sent{template: opt_in_request}
          
        Si existe contact:
          - W carga histórico (conversaciones previas, score_comportamental, motos compradas)
          - W omite opt-in si ya está dado

Paso 3: C responde
        → whatsapp.opt_in.granted{phone, channel: whatsapp_first_message}
        → sismo_sync persiste opt_in en SISMO contacts

Paso 4: W procesa contenido (texto/voz/imagen) con Claude Sonnet 4.6 multimodal
        - Si voz: Whisper transcribe primero
        - Si imagen: Claude vision identifica producto y/o moto
        - W clasifica intent
        → whatsapp.intent.classified{intent_type, confidence}

Paso 5: Routing según intent_type:
        - cotizar_moto         → flujo F2
        - cotizar_repuesto     → cliente RODDOS? F3 : F4
        - pago_cuota           → flujo F5 (consulta de saldo)
        - mantenimiento_consulta → flujo F6
        - soporte general / queja / otro → handoff humano (ROG-W4)
        - intent_no_claro      → W pregunta clarificación (max 2 intentos)

Paso 6: ARGOS Strategist registra intent en agent_memory para personalización futura
```

Métricas clave: tasa de intent_classified con confidence > 0.85, % handoff sobre total, tiempo a primera respuesta útil.

---

## F2 — Venta de TVS Raider con Crédito RDX Leasing

Disparador: intent = cotizar_moto.
Foco: KYC conversacional + scoring + decisión + entrega.
Duración objetivo: < 5 min desde inicio scoring hasta resultado entregado.

```
Paso 1: W envía catálogo de motos vía WhatsApp Multi-Product Message
        Hoy: solo TVS Raider 125 (a futuro hasta 4 modelos)
        Cliente tap en TVS Raider 125

Paso 2: W presenta opciones con cuotas calculadas
        - Plan 9 meses: 39 cuotas semanales de $X
        - Plan 12 meses: 52 cuotas semanales de $Y
        - Plan 18 meses: 78 cuotas semanales de $Z (recomendado)
        Cliente elige plan

Paso 3: W abre KYC conversacional
        - W envía WhatsApp Flow nativo: nombre, documento, ciudad, dirección, ocupación
        - Si ocupación = empleado/independiente: pide rango salarial + tiempo en actividad
        - Si ocupación = delivery/mototaxi: pide plataforma (para Palenca)
        - Pide referencia: nombre + teléfono
        - Cliente envía documento + selfie (W solicita ambas imágenes)
        → score.solicitud.created{solicitud_id: SCR-ARGOS-2026-XXXX, producto: credito_moto}

Paso 4: W envía mensaje "estamos evaluando, máximo 5 minutos"
        Score Engine inicia evaluación

Paso 5: S consulta partners en paralelo:
        - AUCO con documento + selfie → score.partner.queried{partner: auco}
        - RiskSeal con email + phone + IP → score.partner.queried{partner: riskseal}
        - Si delivery/mototaxi: Palenca con OAuth → score.partner.queried{partner: palenca}
        - process_document_chat con extractos si cliente los adjuntó

Paso 6: S evalúa reglas duras (ROG-S3) ANTES de llamar a Claude:
        - AUCO score < 70 → rechazo inmediato → ir a paso 9
        - RiskSeal flag fraude=true → rechazo inmediato → ir a paso 9
        - Mora activa > $3M COP → rechazo inmediato → ir a paso 9
        - Si todas las reglas duras pasan → continuar
        → score.hard_rules.evaluated{rechazo_inmediato: false}

Paso 7: S calcula score_modelo (XGBoost si > 100 registros, sino scorecard manual)
        Features: score externo (RiskSeal o Palenca según corresponda),
                 capacidad_pago, estabilidad_laboral, score_comportamental (si cliente),
                 validacion_biometrica
        → score.ml.calculated{score_modelo, model_hash}

Paso 8: S llama a Claude Sonnet 4.6 para ajuste cualitativo:
        - Coherencia de datos KYC vs partners
        - Análisis de documentos adjuntos
        - Genera narrativa auditable de la decisión
        → score.claude.adjusted{ajuste, narrativa}

Paso 9: S calcula score_final = (0.7 × score_modelo + 0.3 × score_claude_ajustado) × 1000
        S aplica reglas de producto credito_moto:
        - Umbral aprobación: 650 (cliente RODDOS A+ baja a 600)
        - DTI máximo: 40%
        - Categoría: muy_bajo (800-1000) / bajo (650-799) / medio (450-649 → revision_manual) / alto/muy_alto (rechazado)
        → score.evaluated{score_final, decision, monto_aprobado}

Paso 10: S persiste en scoring_solicitudes
         S llama POST a SISMO /api/argos/score-result (para que SISMO registre en loanbook)
         S llama POST a SISMO /api/argos/customer si es cliente nuevo

Paso 11: W envía resultado por WhatsApp (ROG-S6: solo WhatsApp, NO email):
         - Si aprobado: "✅ ¡Aprobado! Score X/1000. Monto $Y. Próximo paso: paga inicial $Z"
                       + envía link Wava de inicial
         - Si rechazado: "📋 Hola, en este momento no podemos aprobar. Puedes volver a aplicar en 90 días"
         - Si revision_manual: "⏳ Tu solicitud está en revisión. Te notificamos en máximo 4h"
         → score.notified{delivered: true}

Paso 12 (solo si aprobado): C paga inicial vía link Wava
         → cobro.pago.recibido{tipo: inicial_moto}
         W envía: "Pago de inicial confirmado ✅. Te contactamos en 2h para coordinar entrega"
         W dispara handoff a operador humano para coordinación logística (entrega de la moto)
         R activa cronograma de cuotas semanales (entra a flujo F5)

Paso 13 (si revision_manual): Sistema notifica al analista en /briefing
         Analista revisa, consulta Datacrédito manualmente si necesita
         Analista resuelve vía PUT /api/v1/scoring/{id}/decision
         W notifica resultado al cliente por WhatsApp
```

Métricas clave: tiempo total < 300 seg, tasa de aprobación, score promedio, tasa de revisión manual, tasa de fraude detectado por RiskSeal.

---

## F3 — Venta de repuestos a cliente RODDOS con Crédito Rodante ⭐ FOCO

Este es el flujo central del negocio recurrente. El cliente ya es de RODDOS (compró moto o repuesto antes). Su score comportamental ya existe.

Disparador: intent = cotizar_repuesto, contact.es_cliente_roddos = true.
Foco: cierre rápido + bypass de KYC + pago en chat.
Duración objetivo: < 3 min desde cotización hasta pago confirmado.

```
Paso 1: C envía solicitud (texto, voz o foto del repuesto)
        Ejemplos:
        - Texto: "necesito pastillas para mi pulsar"
        - Voz: nota de audio en lenguaje natural
        - Imagen: foto del repuesto roto

Paso 2: W identifica producto (super-poder cotizador visual/voz):
        - Si imagen: Claude vision identifica SKU
        - Si voz: Whisper transcribe + Claude extrae intent
        - W cruza con SISMO inventario para confirmar stock + precio
        - W cruza con products_catalog (MELI + FB MP) para validar precio competitivo

Paso 3: W envía cotización personalizada con Multi-Product Message:
        - Foto del producto
        - Precio: "$24.000"
        - Compatibilidad confirmada con la moto del cliente (sabe modelo de contacts)
        - Alternativas (si margen lo permite): producto premium o económico
        - Cliente puede tap "Comprar" o regatear

Paso 4 (caso A · cliente acepta sin regatear):
        Cliente tap "Comprar"
        Si monto < $500K Y cliente.score_comportamental in [A+, A, B]:
          → BYPASS de scoring full · aplicar Crédito Rodante express
          → score.solicitud.created{producto: credito_repuestos, bypass_reason: cliente_recurrente_buen_score}
          → S aplica reglas express:
            * RiskSeal SI se ejecuta (antifraude · ROG-S1)
            * AUCO NO se ejecuta (cliente ya validado biométricamente en compra anterior)
            * XGBoost calcula con features mínimas (es cliente conocido)
            * Umbral 400 (vs 500 normal · cliente con historial positivo)
          → Resultado en < 60 seg
          → score.evaluated{decision: aprobado, monto_aprobado: monto_solicitado}

        Si cliente.score_comportamental in [C, D, E] o monto >= $500K:
          → Aplicar scoring full (ir a F4 paso 5+)

Paso 5: W envía link Wava al cliente
        wava.link.create{monto, métodos: nequi+daviplata}
        → cobro.link_generated{wava_link}
        W envía: "Listo, paga aquí 👉 [link Wava]"

Paso 6: C abre link, paga con Nequi/Daviplata sin salir de WhatsApp (Wava in-chat)
        → cobro.pago.recibido{transaction_id, metodo}
        Wava webhook → ARGOS

Paso 7: W confirma:
        "✅ Pago recibido $24.000. Tu pedido sale hoy 4pm, llega mañana antes de las 12.
         Te aviso cuando salga 📦"
        S persiste en SISMO loanbook (es Crédito Rodante con plazo corto)
        Inventario SISMO se decrementa
        whatsapp.conversation.closed{outcome: vendio, value_usd}

Paso 8: Sistema agenda mantenimiento_predictivo en agent_memory:
        "pastillas compradas el 2026-04-21 para Pulsar NS200 → próxima revisión sugerida en 6 meses"
        (alimenta flujo F6)

Paso 4 (caso B · cliente regatea):
        Cliente: "está caro, ¿en cuánto me lo dejas?"
        W consulta:
          - Margen actual del SKU en SISMO
          - Precio competidor más cercano (Competitors agent)
          - Cliente.lifetime_value
        Compliance Officer valida piso autorizado (ROG-W2)
        W ofrece opciones dentro del piso:
          - Opción 1: bajar precio dentro del cap (ej. -7%)
          - Opción 2: precio original + envío gratis
          - Opción 3: precio original + regalo (guantes, llavero)
        Si cliente acepta una → continuar paso 5
        Si cliente pide más allá del cap → handoff al CEO o "lo siento, ese es nuestro mejor precio"
```

Métricas clave: tiempo a venta < 180 seg, % bypass aplicado (debería ser >70% en clientes recurrentes), % regateo cerrado dentro del cap, AOV repuestos.

---

## F4 — Venta de repuestos a cliente nuevo no-RODDOS

Disparador: intent = cotizar_repuesto, contact.es_cliente_roddos = false.
Foco: capturar lead + venta rápida cash + invitación a aplicar crédito moto.

```
Paso 1-3: Igual que F3 (identificación, cotización con Multi-Product)

Paso 4: W presenta dos opciones:
        - "Pago de contado" (la mayoría de clientes nuevos)
        - "Crédito Rodante (necesito KYC corto)"

Paso 4 (caso A · cash):
        Cliente elige cash → W genera link Wava sin scoring
        RiskSeal SE EJECUTA igual (antifraude primario para repuestos · ROG-S1)
        Si RiskSeal fraud_flag: W bloquea venta + handoff humano
        Si RiskSeal limpio: W envía link Wava
        → cobro.pago.recibido
        W confirma + pregunta: "¿Tienes moto? Te puedo ofrecer crédito para tu próximo repuesto sin papeleo"
        → si cliente dice sí → invita a F2 light (KYC corto para Crédito Rodante)

Paso 4 (caso B · pide crédito):
        W abre KYC corto (Rodante es producto menor riesgo)
        Aplica scoring full pero con umbral 500 y peso mayor de RiskSeal en scorecard:
          - score externo (RiskSeal predomina): 35%
          - capacidad_pago: 25%
          - estabilidad_laboral: 20%
          - score_comportamental: 0% (cliente nuevo, no aplica)
          - validacion_biometrica: 20%
        AUCO obligatorio (cliente nuevo)
        Documento + selfie obligatorios
        → score.solicitud.created{producto: credito_repuestos}
        → continuar como en F2 paso 5+
        Resultado en < 5 min

Paso 5: Si aprobado → cliente paga primera "cuota express" o el monto con Wava
        Si rechazado → W ofrece pago cash como alternativa

Paso 6: Cliente queda registrado en SISMO contacts con datos completos
        → próxima visita ya entra como F3 (cliente RODDOS)
```

Métricas clave: % nuevos que vuelven a comprar en 90 días, % conversión cash → crédito Rodante, fraud_rate detectado por RiskSeal.

---

## F5 — Cobranza recurrente vía RADAR + Wava + WhatsApp

Disparador: RADAR (en SISMO V2) genera cobros programados.
Foco: cobrar cuotas semanales sin fricción + recuperar morosos.

```
Paso 1: R en SISMO genera cobros del día (job nightly o por evento)
        Para cada cliente con cuota vencida HOY:
        SISMO POST → ARGOS /api/v1/cobranza/cobro
        → cobro.programado{customer_id, cuota_numero, monto, fecha_vencimiento}

Paso 2: ARGOS cobranza_orchestrator recibe el cobro
        Llama a Wava: WA.create_link({customer_id, monto, métodos: nequi+daviplata})
        → cobro.link_generated{wava_link, expira_en}

Paso 3: W envía mensaje al cliente (template aprobado por Meta · utility · $0.0008 USD):
        "Hola Andrés 👋 Tu cuota #12 de $35.000 vence hoy. Paga fácil aquí 👉 [link Wava]
         Métodos: Nequi · Daviplata · PSE"
        → cobro.notificacion.enviada

Paso 4 (caso A · cliente paga):
        C abre link, paga con Nequi (sin salir de WhatsApp)
        Wava webhook → ARGOS /api/v1/cobranza/wava-webhook
        → cobro.pago.recibido{transaction_id, metodo, monto}

Paso 5: ARGOS POST → SISMO /api/v1/cobranza/pago-confirmado (devuelve confirmación a RADAR)
        SISMO actualiza saldo del crédito
        SISMO POST → ARGOS notificando saldo actualizado
        → cobro.pago.confirmado

Paso 6: W confirma al cliente:
        "✅ Pago recibido. Te quedan 27 cuotas. Próxima: 28 abril por $35.000.
         ¡Gracias por estar al día! 🎉"

Paso 4 (caso B · cliente NO paga en 24h):
        cobranza_orchestrator detecta no-pago → cobro.recordatorio.disparado{intensidad: suave}
        W envía recordatorio amable (template utility):
        "Andrés, tu cuota de ayer aún está pendiente. Si tuviste algún problema, escríbenos.
         Link sigue activo 👉 [link Wava]"

Paso 5: Si pasa otras 24h sin pagar → cobro.recordatorio.disparado{intensidad: medio}
        W: "Tu cuota lleva 2 días vencida. Recuerda que afecta tu score crediticio interno.
            ¿Necesitas hablar con un asesor?"

Paso 6: 5 días vencido → cobro.morosidad.detectada
        Sistema escala: ARGOS notifica al CEO en /briefing + envía caso a operador humano
        OP toma el caso, llama, gestiona manualmente
        Si cliente entra a +30 días vencido → afecta score_comportamental en SISMO loanbook
        Esto a su vez afecta scoring de cualquier solicitud futura del cliente
```

Métricas clave: % pagos a tiempo (objetivo > 85%), días promedio vencimiento, tasa de morosidad +30, costo de cobranza por cuota.

---

## F6 — Mantenimiento predictivo + re-compra ⭐ FOCO

Este flujo es el motor de revenue recurrente. Convierte un cliente comprado-una-vez en un cliente que compra cada 3-6 meses por años.

Disparador: job semanal que cruza customer_history × tabla de vida útil de SKUs × estimado de uso.
Foco: anticipar la necesidad antes que el cliente.

```
Paso 1: Strategist (job semanal lunes 04:00) ejecuta:
        Para cada customer activo en SISMO:
          Para cada repuesto consumible comprado en los últimos 24 meses:
            calcular: dias_desde_compra
                     vida_util_estimada (de tabla por categoría)
                     uso_intensivo (mototaxi/delivery → vida útil × 0.6)
                     proximidad_recompra = (dias_desde_compra / vida_util_estimada)
            si proximidad_recompra in [0.85, 1.05] → candidato
        
        Lista de candidatos del día → Strategist evalúa con Compliance Officer (cap frecuencia ROG-W5)

Paso 2: Strategist genera mensaje personalizado con Sonnet 4.6:
        Input: customer (moto, lifetime_value, score_comportamental), repuesto, contexto temporal
        Output: mensaje natural conversacional (NO template estático)
        
        Ejemplo:
        "Hola Andrés 👋 hace 7 meses compraste un kit cadena Pulsar NS200.
         Por la fecha y porque manejas como mototaxista, ya sería buen momento
         para revisar tensión y empezar a pensar en cambio próximo.
         Te puedo cotizar el kit nuevo con 10% off por ser cliente recurrente
         o recomendarte taller aliado para diagnóstico. ¿Qué prefieres?"
        
        → Strategist crea recommendation con type: cart_promo
        → recommendation.created{type, sku, customer_id, expected_impact}

Paso 3: Compliance Officer valida cap de descuento (ROG-W2)
        → recommendation.compliance.validated

Paso 4: Como esto es marketing proactivo (no respuesta a cliente), entra utility template
        W envía mensaje vía template aprobado por Meta
        Costo: $0.0008 USD por mensaje (utility Colombia)
        → whatsapp.message.sent

Paso 5 (caso A · cliente responde "sí, cotízame"):
        Entra a flujo F3 (cliente RODDOS recurrente · bypass aplicado)
        Venta cerrada en < 3 min

Paso 5 (caso B · cliente responde "ya cambié" o "no me interesa"):
        W actualiza agent_memory: "no recordar esto en X días"
        W: "Perfecto, no te molesto más con esto. Si necesitas algo más, escríbeme cuando quieras"
        Strategist registra recommendation.measured{actual_impact: 0, learning: "ya había comprado en otra parte"}

Paso 5 (caso C · cliente no responde en 7 días):
        Strategist registra recommendation.measured{actual_impact: 0, learning: "no_response"}
        Sistema NO insiste por 60 días mínimo (ROG-W5 + experiencia)
```

Métricas clave: tasa de respuesta al mensaje proactivo (objetivo > 25%), conversion proactivo → venta (objetivo > 12%), uplift de LTV vs cohorte sin mantenimiento predictivo.

---

## Diagrama unificado de flujos

```
                    ┌──────────────────────┐
                    │ C envía 1er mensaje  │
                    └──────────┬───────────┘
                               │ F1 (clasificación intent)
            ┌──────────────────┼──────────────────┐
            │                  │                  │
        cotizar_moto      cotizar_repuesto   pago_cuota
            │                  │                  │
           F2              ┌───┴───┐             F5
        (TVS Raider     cliente?  no-cliente
         + RDX Leasing)    │         │
                          F3        F4
                       (cliente    (lead nuevo
                        recurrente   + RiskSeal
                        + bypass)    primario)
                          │         │
                          ▼         ▼
                      cobro.pago.recibido
                          │
                          ▼
                  Strategist agenda mantenimiento_predictivo
                          │
                          ▼ (en T+meses)
                          F6
                  (re-compra proactiva)
                          │
                          ▼
                   vuelve a F3
                  (loop infinito)
```

El loop F3 ↔ F6 es el motor de negocio. F2 alimenta el loop con clientes nuevos. F4 captura leads que no son de moto pero pueden serlo. F5 protege la salud financiera de la cartera. F1 es la puerta de entrada a todo.
