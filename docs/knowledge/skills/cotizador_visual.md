# docs/knowledge/skills/cotizador_visual.md

# Skill: Cotizador Visual y por Voz

Cliente manda foto de un repuesto roto o una nota de voz describiéndolo → WhatsApp Agent identifica SKU compatible con su moto y cotiza en <30 segundos.

**Agente dueño:** WhatsApp Agent
**Modelos usados:** Claude Sonnet 4.6 vision + Whisper
**Trigger:** mensaje entrante con imagen o audio

## Flujo imagen

```
1. Cliente envía foto del repuesto roto o que necesita reemplazar
2. W descarga imagen (Mercately webhook)
3. W llama a claude.vision() con prompt:
   "Identifica el repuesto de moto en esta imagen. Retorna JSON:
    {categoria: 'frenos/transmision/motor/etc',
     subcategoria: 'pastillas/disco/cadena/...',
     estado_aparente: 'nuevo/usado/roto',
     confidence: 0.0-1.0,
     descripcion: 'pastillas delanteras de moto, parecen gastadas'}"

4. Si confidence > 0.85:
   W consulta contact.moto_modelo (sabe que cliente tiene Pulsar NS200)
   W busca en products_catalog: categoria + subcategoria + compatible_con moto_modelo
   W selecciona mejor match por (rotación + margen + stock)

5. W responde con Multi-Product Message:
   [foto del SKU canónico]
   "Creo que necesitas pastillas delanteras para tu Pulsar NS200.
    Tengo estas:
    🟢 Premium marca Brembo → $34.000 (duran 8-10 meses)
    🟡 Estándar marca XYZ → $24.000 (duran 6-8 meses)
    🟠 Económica → $15.000 (duran 4-5 meses)
    
    ¿Cuál prefieres?"

6. Cliente tap en una → continúa a flujo F3 (venta)

7. Si confidence < 0.85:
   W pide clarificación:
   "Vi la foto pero no estoy 100% seguro de qué necesitas.
    ¿Me confirmas si es pastilla de freno delantera o de cadena?"
```

## Flujo audio

```
1. Cliente envía nota de voz: "Hola necesito las pastillas esas del freno
   de mi pulsar, las de adelante que ya están gastadas"

2. W usa Whisper para transcribir en español colombiano
   → "Hola necesito las pastillas esas del freno de mi pulsar,
      las de adelante que ya están gastadas"

3. W llama a claude.sonnet.extract_intent():
   "Extrae:
    - producto_buscado: pastillas freno delanteras
    - moto_referenciada: pulsar (cruzar con contact.moto_modelo si aplica)
    - confianza: 0-1"

4. W sigue el mismo árbol del flujo imagen desde paso 4

5. IMPORTANTE: W NO responde con audio (responde con texto)
   Razón: texto es más útil para el cliente (puede releer, copiar, guardar)
```

## Combinación imagen + voz

Si cliente manda imagen + audio simultáneos (o audio describiendo la imagen), ambos se procesan y se cruzan para mejorar confidence.

## Identificación de moto del cliente

| Situación | Acción |
|-----------|--------|
| Cliente tiene contact.moto_modelo en SISMO | W usa ese directamente · no pregunta |
| Cliente nuevo sin moto registrada | W pregunta: "¿Para qué moto es?" |
| Cliente tiene 2 motos registradas | W pregunta: "¿Es para tu Pulsar o tu TVS?" |
| Cliente responde "para cualquiera" | W ofrece universal si existe o alternativas por modelo |

## Caso borde: repuesto no identificable

Si confidence sigue bajo tras 2 intentos de clarificación: handoff humano con la imagen y la transcripción del audio como contexto.

## Métricas

- Tasa de identificación correcta al primer intento: target > 80%
- Tiempo desde imagen/audio hasta cotización: target < 30 seg
- Tasa de conversión visual/voz → venta: target > 25%
