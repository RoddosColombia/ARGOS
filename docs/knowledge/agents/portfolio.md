# docs/knowledge/agents/portfolio.md

# Portfolio Agent

Agente N2 de recomendación de portafolio. Su salida principal es responder a la pregunta: **¿qué SKUs deberíamos sourcear que hoy no tenemos?** y derivadas.

## Identidad

- Nivel: N2 (recomendación con consecuencia material · sourcing cuesta capital)
- Modelo LLM: Claude Sonnet 4.6 para síntesis de brief + Opus 4.7 para casos complejos
- Stack: Python + MongoDB + cross-source aggregation
- Persistencia: `portfolio_suggestions`
- Eventos producidos: `portfolio.suggestion.created`, `portfolio.brief.published`
- Eventos consumidos: salidas del Marketplace, Trends, Competitors, Account intel agents + read de `sismo_inventory` + `sismo_sales_daily`

## Misión

Cruzar **demanda de mercado** vs **stock RODDOS actual** vs **velocidad rotación competitiva** vs **margen estimado** y emitir 5 tipos de recomendación weekly:

1. **SKUs huérfanos** · alta demanda mercado, RODDOS no stockea. Ranked por revenue potencial mensual estimado.
2. **SKUs sub-stockeados** · los tenemos, rotamos lento vs mercado. Indica pricing alto, listing pobre o stock insuficiente.
3. **SKUs en deprecación** · demanda cayendo. Liberar capital de inventario.
4. **Categorías emergentes** · SKUs nuevos en MELI/competencia indicando nuevo modelo de moto entrando o nueva marca de repuesto.
5. **Cross-sell gaps** · clientes RODDOS que compran SKU A pero no SKU B típicamente complementario.

## Output

Brief weekly entregado simultáneamente a CEO + CGO (ROG-G1) los lunes 06:00 con el nombre `Portfolio Brief · YYYY-MM-DD`. Incluye:

- 10-20 SKUs huérfanos top-priorizados con: canonical_id, demanda inferida (volumen mensual estimado), competencia (top vendedor + precio), margen estimado, recomendación de cantidad inicial a sourcear, lead time típico
- 5-10 SKUs sub-stockeados con diagnóstico (pricing/listing/stock)
- 3-5 SKUs en deprecación con valor de capital inmovilizado
- 1-3 categorías emergentes con justificación
- 5-10 cross-sell opportunities con cohorte de clientes y SKU sugerido

Cada item del brief tiene: justificación + datos crudos linkeados (MELI listings, búsquedas Trends, listings competencia) para que CEO/CGO inspeccionen sin tomar al LLM en su palabra.

Approval flow:
- Adoptar nuevo SKU al portafolio = decisión Plano 3 (CEO) porque mueve capital
- Liquidar SKU en deprecación = decisión Plano 3 (CEO) por implicación operativa
- Cross-sell campaigns derivadas = Plano 2 (CGO)

## Tools permitidos

- mongodb.read.* (todas las colecciones de inteligencia)
- partners.sismo.read.* (inventory, sales, customer history)
- claude.sonnet.synthesize() (brief generation)
- claude.opus.reason() (casos complejos · ej. categoría emergente con datos ambiguos)
- embeddings.* (cluster de cohortes para cross-sell)

## Tools prohibidos

- Sourcing directo (no compra SKUs · solo recomienda)
- Modificación de stock SISMO
- Cualquier acción sobre clientes (mensaje proactivo es trabajo del WhatsApp Agent + Strategist)

## Frecuencia

- Brief weekly lunes 06:00 (snapshot fresco del mercado tras weekend)
- Recomputo on-demand cuando llega evento crítico (ej. `competitor.meli.new_listing` en categoría sin presencia RODDOS)

## Criterios de éxito

- Hit rate de SKUs sourcear adoptados que rotan en primeros 60 días ≥ 70%
- Capital liberado por SKUs en deprecación adoptados ≥ X COP/trimestre (validar con CEO)
- CGO + CEO consumen el brief en <15 min cada lunes

## ROGs relevantes

- ROG-A3, A6, A9, A12 (estándar)
- ROG-G1 brief unificado CEO + CGO
- ROG-G2 sourcing como Plano 3

## Tests

- PF-01: Brief generado los lunes 06:00 y persistido
- PF-02: SKUs huérfanos rankeados por revenue potencial estimado calculado correctamente
- PF-03: Cross-sell suggestion linkea cohorte ≥ 50 clientes para tener señal estadística
- PF-04: Brief NO incluye SKUs ya stockeados como "huérfanos" (cruza correctamente con sismo_inventory)
- PF-05: Brief enviado simultáneamente a CEO + CGO (ROG-G1)
- PF-06: SKUs en deprecación calculan capital inmovilizado correctamente

## Phase de construcción

**Capa 4 · semanas 17-21** del cronograma 2.1.

## Dependencias

- SKU canonicalizer (también Capa 4) debe estar funcionando para que las cruces hagan sentido
- Account intel agent (también Capa 4) provee mapa de competencia que Portfolio consume
- `sismo_inventory` y `sismo_sales_daily` deben estar sincronizando bien (ya lo están desde Phase 1)
