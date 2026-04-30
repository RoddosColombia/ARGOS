# docs/knowledge/agents/pricing_engine.md

# Pricing Engine

Agente N2 dedicado a sugerir y (dentro de envelope) ejecutar ajustes de precio por SKU activo. Antes vivía implícito dentro del Strategist (Visión 2.0); en Visión 2.1 se eleva a agente de primera clase.

## Identidad

- Nivel: N2 (recomendación con ejecución autónoma dentro de envelope Plano 1)
- Modelo LLM: Claude Sonnet 4.6 para razonamiento competitivo · Haiku para ajustes simples regla-based
- Stack: Python + MongoDB + lectura del mapa competitivo de Account intel + Compliance Officer integration
- Persistencia: `pricing_suggestions`, ajustes ejecutados auditados en `audit_log`
- Eventos producidos: `pricing.suggestion.created`, `pricing.adjustment.executed` (dentro envelope), `pricing.adjustment.escalated` (fuera envelope)
- Eventos consumidos: lecturas del Account intel agent + Strategist + Portfolio + sismo_inventory + sismo_sales_daily

## Misión

Para cada SKU activo en el portafolio RODDOS, generar diariamente una **sugerencia de precio óptimo** justificada con:

- Precio actual RODDOS
- Precio promedio mercado (MELI top 5 vendedores · scraping competencia)
- Velocidad de rotación última semana RODDOS vs competencia
- Stock RODDOS actual (mucho stock + baja rotación = bajar precio · poco stock + alta demanda = subir/mantener)
- Margen actual vs piso definido por CEO
- Movimientos competitivos recientes (Account intel)
- Demanda spike (Trends agent)

Output: tabla diaria con N filas (una por SKU activo) ordenada por delta absoluto sugerido. Cada fila tiene: precio_actual, precio_sugerido, delta_pct, justificación, plano_required (1/2/3), envelope_check.

## Comportamiento por plano

- **Plano 1** (dentro de envelope `pricing.adjust_meli`, default ±5% sobre precio base): Pricing engine **ejecuta automáticamente** vía API MELI + actualiza catálogo SISMO · audit_log con justificación
- **Plano 2** (fuera de envelope hasta ±15%): genera recomendación, queda en cola del CGO, default rechazo en 24h
- **Plano 3** (>±15% o cambio de margen piso): solo recomendación al CEO

Compliance Officer es el gate. Pricing engine llama `compliance.validate_action(action_type="pricing.adjust_meli", params={sku, delta_pct})` antes de ejecutar.

## Tools permitidos

- mongodb.read.* (inventory, sales, products_catalog, competitor_profiles)
- partners.meli.update_listing (Plano 1 únicamente · validado por Compliance)
- partners.sismo.update_pricing (idem)
- claude.sonnet.reason()
- claude.haiku.classify() (ajustes simples)
- mongodb.write.pricing_suggestions
- compliance.validate_action()
- audit.write()

## Tools prohibidos

- Cambios de precio Plano 2/3 sin approval (Compliance Officer veta)
- Cambios fuera de envelope sin escalation
- Modificar precio piso (eso es Plano 3, decisión CEO con cambio de `compliance_envelope`)

## Frecuencia

- Análisis diario 05:00 UTC (antes del brief unificado · sus sugerencias entran al brief)
- Re-evaluación on-demand cuando llega evento crítico:
  - `competitor.meli.price_change` con delta >10% en SKU tracked
  - `trends.keyword.spike` en SKU compartido
  - `inventory.stockout.predicted` (precio puede subir si demanda > stock)

## Criterios de éxito

- Hit rate de sugerencias Plano 1 ejecutadas: si tras T+7 las ventas del SKU subieron o se mantuvieron con margen mejorado, +1. Si bajaron por desalineación competitiva, -1. Target ratio ≥ 0.6.
- Cobertura: ≥80% de SKUs activos reciben sugerencia diaria
- Latencia: análisis completo del catálogo en <30 min para 1000 SKUs

## ROGs relevantes

- ROG-A2 spending caps · pricing engine respeta envelope en código, no en prompt
- ROG-A6 ajustes auditados en bus + audit_log
- ROG-A12 cada ajuste tiene actor (Pricing engine como `sistema`), justificación, plano, evidence_refs
- ROG-G2 tres planos enforzados
- ROG-G4 envelope vive en `compliance_envelope`, cambios al envelope son Plano 3

## Tests

- PE-01: Análisis diario genera sugerencia por SKU activo con justificación y plano correcto
- PE-02: Plano 1 dentro envelope ejecuta automáticamente sin tap humano
- PE-03: Plano 2 escala a CGO con CTA en frontend
- PE-04: Plano 3 escala solo a CEO
- PE-05: Compliance veto bloquea ejecución (audit_log registra el veto)
- PE-06: Cambio de precio MELI propaga a SISMO en <60 seg con consistency

## Phase de construcción

**Capa 5 · semanas 22-27** del cronograma 2.1.

## Dependencias

- Compliance Officer maduro (Plano 1/2/3) operativo desde Capa 0 (versión Plano 1) y completo en Capa 5
- SKU canonicalizer (Capa 4) para asegurar que pricing por SKU canonical, no por listing duplicado
- Account intel + Portfolio (Capa 4) para razonamiento competitivo
- `compliance_envelope` poblado con valores definidos por CEO
