# docs/knowledge/skills/mantenimiento_predictivo.md

# Skill: Mantenimiento Predictivo + Re-compra Proactiva

El motor de revenue recurrente del negocio de repuestos. Anticipa la necesidad del cliente ANTES de que pregunte.

**Agentes dueños:** Strategist (análisis + generación) + WhatsApp Agent (entrega) + Compliance (validación)
**Ejecución:** job semanal lunes 04:00 Bogotá
**Flujo de negocio relacionado:** F6

## Tesis de negocio

Un cliente que compra una moto vive con RODDOS 5+ años. Durante ese tiempo necesita:
- Aceite cada 2-3 meses (6 x año)
- Filtros cada 6-12 meses
- Pastillas cada 6-12 meses
- Cadena cada 12-18 meses
- Llantas cada 18-24 meses
- Bujías cada 12 meses
- Revisiones cada 3-6 meses

Para un mototaxista o delivery (uso intensivo): la frecuencia es 1.5-2x mayor.

Cada mensaje proactivo que convierte = $20K-80K de ticket promedio. Con tasa de conversión 12% del mensaje → venta, y costo utility template $0.0008 USD, el ROI es enorme.

## Tabla de vida útil por SKU (configurada en `knowledge/skus_lifetime.md` · placeholder)

| Categoría | Uso normal | Uso intensivo (delivery/mototaxi) |
|-----------|------------|------------------------------------|
| Aceite | 3000 km / 3 meses | 1800 km / 1.5 meses |
| Filtro aceite | 6000 km / 6 meses | 3600 km / 3 meses |
| Pastillas delanteras | 15000 km / 10 meses | 9000 km / 6 meses |
| Pastillas traseras | 18000 km / 12 meses | 11000 km / 7 meses |
| Cadena | 25000 km / 18 meses | 15000 km / 10 meses |
| Bujía | 15000 km / 12 meses | 9000 km / 7 meses |
| Llanta delantera | 30000 km / 24 meses | 18000 km / 14 meses |
| Llanta trasera | 20000 km / 18 meses | 12000 km / 10 meses |

## Algoritmo

```python
# Ejecutar lunes 04:00
candidates = []

for customer in sismo.customers.active():
  uso_intensivo = customer.uso_moto in ['trabajo', 'mixto']
  
  for compra in customer.repuestos_comprados_24m:
    dias_desde_compra = (today - compra.fecha).days
    vida_util = get_vida_util(compra.sku_categoria, uso_intensivo)
    proximidad = dias_desde_compra / vida_util
    
    if 0.85 <= proximidad <= 1.05:
      # Ventana óptima de alerta
      candidates.append({
        customer_id: customer.id,
        sku_sugerido: compra.sku,
        dias_desde_compra,
        vida_util_estimada: vida_util,
        motivo: "proximidad temporal basado en lifetime"
      })

# Filtrar por frecuencia (ROG-W5)
for c in candidates:
  ultimo_mensaje_proactivo = await whatsapp.last_proactive(c.customer_id)
  if ultimo_mensaje_proactivo and (today - ultimo_mensaje_proactivo).days < 14:
    c.skip = True  # respetar cap

# Filtrar por opt-in (ROG-W1)
candidates = [c for c in candidates if customer.opt_in_marketing is True]

# Priorizar por LTV + score_comportamental
candidates.sort(key=lambda c: (
  c.customer.lifetime_value * weight_by_score(c.customer.score_comportamental)
), reverse=True)

# Top N por capacidad diaria (evitar inundar cola de Mercately)
top_candidates = candidates[:200]

for c in top_candidates:
  # Generar mensaje personalizado con Sonnet 4.6
  mensaje = await claude.sonnet.generate(
    system=MANTENIMIENTO_PROMPT_CACHED,
    user={
      nombre: c.customer.nombre,
      moto: c.customer.moto_modelo,
      repuesto: c.sku_sugerido,
      dias_desde_compra,
      uso: c.customer.uso_moto,
      score: c.customer.score_comportamental
    }
  )
  
  # Validar con Compliance (descuento, cap, opt-in)
  valid = await compliance.validate(c, mensaje)
  
  if valid:
    await whatsapp.send_utility_template('mantenimiento_predictivo', mensaje, c.customer.phone)
    await recommendations.create(type='cart_promo', customer_id=c.customer.id, ...)
```

## Ejemplos de mensaje generado

**Ejemplo 1 — mototaxista que compró pastillas hace 7 meses:**

```
Hola Carlos 👋

Hace 7 meses compraste pastillas delanteras para tu Pulsar NS200.
Como manejas como mototaxista, ya sería momento de revisar tensión
y pensar en cambio próximo.

🛠️ Te cotizo el kit nuevo con 10% OFF por cliente recurrente: $21.600
📅 Si prefieres revisión primero, te recomiendo taller aliado en Kennedy

¿Qué prefieres?

💬 Responde 1 (cotizar repuesto)
💬 Responde 2 (taller aliado)
💬 Responde 3 (ya lo cambié, no te preocupes)
```

**Ejemplo 2 — cliente casual que compró aceite hace 2.5 meses:**

```
Hey Juan 👋

Hace casi 3 meses cambiaste aceite para tu TVS Raider.
Ya va siendo hora del próximo cambio 🛢️

🔧 Aceite 20W-50 de siempre → $28.000
🎁 Si pides hoy, envío gratis

¿Te lo mando?
```

## Tratamiento de respuestas

| Respuesta del cliente | Acción del WhatsApp Agent |
|------------------------|--------------------------|
| "Sí cotízame" / "dale" / emoji 👍 | Entra a flujo F3 (cliente RODDOS · bypass aplicado) |
| "Ya lo cambié" / "no me interesa" | Actualiza `agent_memory`: "no recordar este SKU en 60 días" · W: "Perfecto, cuando necesites algo escríbeme 👍" |
| "Dame taller aliado" | W entrega lista de 2-3 talleres aliados en su ciudad |
| Sin respuesta en 7 días | Marca recommendation.measured con actual_impact=0 · STOP · no re-insistir en 60 días |

## Métricas

- Tasa de respuesta a mensaje proactivo: target > 25%
- Tasa respuesta → venta: target > 12%
- LTV uplift de cohorte con mantenimiento predictivo vs sin: target > 40%
- Cero quejas por spam / opt-out disparado por esta skill (si llega a >1%: revisar frecuencia)

## Postura cultural del skill

Este skill gana la relación con el cliente SOLO si se siente genuinamente útil. En el momento que el cliente lo perciba como spam, pierde. Por eso:

1. Frecuencia estricta (ROG-W5)
2. Personalización real (nombre + moto + repuesto + uso)
3. Siempre opción de "ya lo cambié, gracias"
4. Nunca presión · nunca urgencia falsa · nunca descuentos inventados
5. Si el cliente se queja, stop inmediato por 90 días
