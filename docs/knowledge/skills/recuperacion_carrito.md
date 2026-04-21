# docs/knowledge/skills/recuperacion_carrito.md

# Skill: Recuperación de Carrito Abandonado

Cliente inició cotización, recibió precio, pero no completó la compra. WhatsApp Agent intenta recuperar la venta sin ser invasivo.

**Agente dueño:** WhatsApp Agent (orquestación) + Strategist (generación de mensaje personalizado)
**Trigger:** conversación con intent cotizar_repuesto u otro, sin outcome `vendio` al cabo de X horas

## Ventanas de recuperación

Basado en datos de conversacional commerce 2026: el sweet spot es temprano pero no atosigante.

| Tiempo desde cotización | Acción |
|-------------------------|--------|
| 0 - 2 horas | NO actuar (cliente puede estar decidiendo) |
| 2 - 24 horas | Mensaje 1: recordatorio suave dentro de ventana 24h (gratis al ser respuesta conversacional) |
| 1 - 3 días | Mensaje 2: oferta ligera (envío gratis, 3% off) vía utility template |
| 3 - 7 días | Mensaje 3 (último): oferta más fuerte dentro del cap |
| > 7 días | STOP · no insistir · eventualmente F6 retoma en 60+ días |

## Mensaje 1 (dentro de ventana 24h)

Tipo: free-form (respuesta conversacional · sin costo adicional)
Tono: casual · sin presión

```
"Hey [Nombre], ¿seguimos con [producto]? Si tienes alguna duda sobre
 [producto] o quieres que lo mandemos hoy mismo antes de las 4pm, dime 👍"
```

## Mensaje 2 (24-72 horas · utility template)

Tipo: utility template pre-aprobado por Meta · $0.0008 USD Colombia 2026
Tono: ofrecimiento sin presión

Template name: `cart_recovery_soft`

```
Hola {{nombre}},

Vi que te interesaron las {{producto}}. Sigo con ellas separadas si las quieres.

💰 Te incluyo envío GRATIS si cierras hoy
📦 Entrega mañana antes de las 12

Solo responde "Sí" y te mando el link de pago 👍
```

## Mensaje 3 (3-7 días · utility template · último intento)

Template name: `cart_recovery_final`

```
Hola {{nombre}}, última llamada por las {{producto}}.

📉 Te las dejo en {{precio_descontado}} (antes {{precio_original}})
📦 Envío gratis incluido

Si pasas, no hay problema 👍 si te interesan, responde aquí.
```

El descuento del mensaje 3 debe estar dentro del cap del SKU (ver skills/negociacion_margen.md). Compliance lo valida.

## Decisión de stop

Si el cliente:
- No responde mensaje 3 en 48h → marcar conversation.outcome = abandono · STOP
- Responde "no" / "ya no me interesa" / "no gracias" → STOP · no insistir
- Responde "después" / "luego" → W: "Vale, aquí estoy cuando decidas 👍" · STOP + recordar en agent_memory para posible F6 en 60 días

## Respeto de frecuencia (ROG-W5)

Si ya se envió un mensaje proactivo F6 (mantenimiento predictivo) al cliente en los últimos 14 días, la recuperación de carrito pasa a free-form dentro de ventana 24h solamente. No se envía utility template hasta que pase la ventana de 14 días.

## Métricas

- Tasa de conversión mensaje 1 → venta: target 30%+
- Tasa conversion mensaje 2 → venta: target 15%+
- Tasa de conversion mensaje 3 → venta: target 8%+
- % de cartos que se recuperan en total: target 35%+
- Cero quejas por spam / opt-out dispardos por esta skill

## Ejemplo de conversación recuperada exitosamente

```
Día 0, 14:35 → cliente cotizó pastillas $24.000 → no compró
Día 0, 16:35 → [no hacer nada · 2h]

Día 1, 08:00 → W (free-form dentro 24h):
"Hey Andrés, ¿seguimos con las pastillas Pulsar? Si pasas antes de las 4pm
 sale hoy y llega mañana 📦"

Día 1, 08:42 → Cliente: "sí me interesan pero está un poco caro"

Día 1, 08:42 → W (free-form · negociación dentro del cap):
"Te las dejo en $22.500 + envío gratis. Total $22.500 puesto en tu casa. ¿Va?"

Día 1, 08:45 → Cliente: "dale"

Día 1, 08:45 → W: "Listo 🔥 Paga aquí 👉 [link Wava]"
Día 1, 08:48 → Pago recibido → Venta cerrada
```
