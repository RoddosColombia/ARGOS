# docs/knowledge/skills/negociacion_margen.md

# Skill: Negociación de Descuentos con Margen Protegido

Cuando un cliente regatea, el WhatsApp Agent necesita decidir rápido cuánto puede bajar sin violar el piso de margen, y qué alternativa ofrecer si el cliente sigue pidiendo más.

**Agente dueño:** WhatsApp Agent
**Validador:** Compliance Officer (en código · ROG-W2)
**Trigger:** cliente dice "está caro" / "¿cuánto lo último?" / "¿en cuánto me lo dejas?"

## Datos disponibles en tiempo real

```python
contexto = {
  "sku": "pastillas_pulsar_ns200_delantera",
  "precio_publico": 24000,
  "costo": 15000,
  "margen_actual_pct": 37.5,
  "piso_margen_autorizado_pct": 15,  # definido por CEO, validado en código
  "precio_competidor_cercano": 22500,  # Competitors agent
  "lifetime_value_cliente": 450000,  # SISMO
  "veces_compra_ultimo_ano": 4,
  "score_comportamental": "A",
  "stock_actual": 12,
  "dias_inventario": 15  # si >60 → margen para rematar
}
```

## Árbol de decisión

```
Cliente regatea
    │
    ▼
¿cuánto pide el cliente (precio_objetivo)?
    │
    ├── NO lo dice explícito → W pregunta: "¿en cuánto estabas pensando?"
    │
    └── Sí lo dice explícito
        │
        ▼
calcular_descuento_pct = (precio_publico - precio_objetivo) / precio_publico
    │
    ├── descuento_pct <= 3% → W aprueba directo
    │   "Te lo dejo en [precio_objetivo]. ¿Cerramos?"
    │
    ├── descuento_pct entre 3% y (margen_actual - piso_margen_autorizado)
    │     → W consulta Compliance
    │     → si Compliance OK: W ofrece con condición
    │       "Te lo dejo en [precio_objetivo] y te mando envío gratis. ¿Cerramos?"
    │     → si Compliance VETA: pasar a siguiente nivel
    │
    ├── descuento_pct > piso_margen_autorizado
    │     → W NO puede bajar el precio · ofrece ALTERNATIVAS:
    │
    │     Opciones (elegir 2 según contexto):
    │     A) "No puedo bajar más el precio, pero te mando envío gratis (ahorra $5K)"
    │     B) "Ese producto está a ese precio, pero tengo esta opción más económica
    │          [SKU alternativo de menor precio] que también es compatible con tu moto"
    │     C) "Te lo dejo al precio que me pides si llevas 2 (combo pastillas + aceite)"
    │     D) "Es nuestro mejor precio en este momento. ¿Cerramos o lo pensamos?"
    │
    └── descuento_pct > 30%
        → Cliente pide un precio absurdo → handoff al CEO o cierre amable
```

## Matriz de flexibilidad por cliente

| Segmento | Descuento directo autorizado | Condicionado (envío, combo) |
|----------|------------------------------|------------------------------|
| Cliente RODDOS A+ con LTV > $2M | hasta 7% | hasta 12% |
| Cliente RODDOS A / B | hasta 5% | hasta 10% |
| Cliente RODDOS C / D / E | 0% | hasta 5% |
| Cliente nuevo | 0% | hasta 5% (solo si RiskSeal limpio) |

Estos caps están en el código (no en prompt) y Compliance los valida.

## Slow mover dispara margen

Si `dias_inventario` del SKU > 60: el piso se relaja automáticamente hasta 8% (vs 15% default), porque es más urgente rotar que preservar margen. Strategist puede disparar una promo masiva de slow movers como recomendación en el briefing.

## Frases tipo (few-shot)

Aprobar directo con entusiasmo:
- "Listo, te lo dejo en $23.000. ¿Cerramos? Envío mañana antes de las 12 📦"

Condicionar con envío:
- "No puedo bajar más el precio, pero te incluyo envío gratis (valor $5K). Total $24.000 puesto en tu casa. ¿Va?"

Ofrecer alternativa más económica:
- "En ese precio tengo estas pastillas chinas ($18.000) que también funcionan. No son marca premium pero aguantan 6-8 meses. ¿Te sirve?"

Mantener precio con gracia:
- "Ese es nuestro mejor precio del día. Si quieres lo pensamos, aquí estoy cuando decidas 👍"

Cliente insiste más abajo del piso:
- "Ya llegué al límite de lo que puedo ofrecer yo. ¿Quieres que te comunique con mi equipo humano a ver si encuentran algo?" → handoff
