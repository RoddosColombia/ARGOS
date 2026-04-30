# docs/knowledge/agents/sku_canonicalizer.md

# SKU Canonicalizer

Agente N1 (servicio) de normalización. Su única responsabilidad es resolver "qué SKU es este" entre fuentes heterogéneas.

## Identidad

- Nivel: N1 (servicio determinista con fallback LLM)
- Modelo LLM: Claude Haiku 4.5 para tie-breaking · embeddings cohere/local para clustering
- Stack: Python + sentence-transformers + MongoDB para alias table
- Persistencia: `sku_canonical_aliases`
- Eventos producidos: `sku.canonical.resolved`, `sku.canonical.created` (cuando emerge SKU nuevo)
- Eventos consumidos: `marketplace.product.detected` (resolución on-the-fly)

## Misión

Convertir cualquier identificador de producto que llega de cualquier fuente en un SKU canonical único interno de ARGOS. Sin esto, los streams de inteligencia (MELI + FB MP + scraping competencia + SISMO interno + social) son ruido aislado.

Ejemplo:
- MELI listing "Pastillas freno Bajaj Boxer 100cc original" → `repuesto.freno.pastilla.bajaj.boxer-100`
- FB Marketplace "Pastilla freno BX 100" → mismo canonical
- TikTok mention "tutorial pastillas Bajaj" sin SKU explícito → mismo canonical inferido por context
- SISMO interno `PST-BJ-BX100-01` → mismo canonical (alias table)

## Tools permitidos

- mongodb.read.products_catalog (consulta del catálogo SISMO)
- mongodb.read/write.sku_canonical_aliases (alias table)
- claude.haiku.classify() (tie-breaking entre candidatos)
- embeddings.encode() (sentence-transformer local · sin costo LLM por llamada)

## Tools prohibidos

- Mutar `products_catalog` (read-only sobre productos)
- Cualquier acción sobre clientes o ventas
- Cualquier interacción con WhatsApp o Score Engine

## Algoritmo

1. **Input**: `{source: meli/fb_mp/sismo/social/scraping, source_id: string, name: string, attributes: {marca, modelo, categoria_inferida}}`.
2. **Lookup directo en alias table** por `(source, source_id)` → si hit, devolver `canonical_id` cacheado. Stop.
3. **Embedding del nombre** + atributos. Buscar top-K (K=5) más cercanos en `sku_canonical_aliases` con coseno ≥ 0.85.
4. **Si hay match único > 0.92**: devolver canonical_id, agregar entry a alias table. Stop.
5. **Si hay múltiples candidatos 0.85-0.92**: invocar Claude Haiku con prompt "estos N candidatos son el mismo SKU?" → respuesta YES/NO + best_match. Persistir resolución.
6. **Si no hay match >= 0.85**: emitir evento `sku.canonical.created` con propuesta de canonical nuevo. Strategist (Capa 4) revisa y aprueba/rechaza inclusión al catálogo canonical (Plano 2 si vale añadir, Plano 3 si es categoría nueva).

## Schema `sku_canonical_aliases`

```
canonical_id: string (ej. "repuesto.freno.pastilla.bajaj.boxer-100")
canonical_name: string (display name)
canonical_attributes: {marca, modelo, categoria, compatible_motos[]}
aliases: [{source, source_id, name_observed, similarity, resolved_at, resolved_by: "auto" | "haiku" | "human"}]
embedding: vector (para similarity search)
created_at, updated_at
```

## Frecuencia

- Resolución on-demand (cada vez que un agente N1 ingesta producto nuevo)
- Re-cluster offline weekly (lunes 03:00 UTC) para detectar duplicados que se acumularon

## Criterios de éxito

- Recall ≥95% en SKUs ingeridos en última semana (validable con muestra manual)
- Precision ≥98% (false positive de unificación incorrecta = malo, contamina datos)
- Latencia P95 lookup directo ≤50ms · clustering ≤500ms · LLM tie-break ≤2s
- Costo Haiku por mes ≤ $20 USD (tie-break es ~5% de los lookups)

## ROGs relevantes

- ROG-A3: alias table multi-tenant (`workspace_id` por entry)
- ROG-A6: emisión de eventos al bus para auditabilidad
- ROG-A12: cada resolución registrada en audit_log si fue manual/humana

## Tests

- SC-01: Lookup directo `(meli, MCO-12345)` → canonical_id en <50ms
- SC-02: Match por embedding ≥ 0.92 → resolución auto sin LLM
- SC-03: Match ambiguo 0.85-0.92 → Haiku invocado con K candidatos
- SC-04: No-match → evento `sku.canonical.created` emitido con propuesta
- SC-05: Re-cluster weekly detecta duplicado y los unifica con audit_log

## Phase de construcción

Construido en **Capa 4 · semanas 17-21** del cronograma 2.1 (junto con Portfolio + Account intel).

## Dependencias

- `products_catalog` debe estar poblado por Phase 1 (ya implementado)
- Strategist (Capa 4 v2) debe consumir `sku.canonical.created` para decidir incorporación
