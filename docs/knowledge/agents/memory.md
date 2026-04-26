# MemoryAgent

Agente N3 (memoria/embeddings) responsable de mantener el contexto semántico de largo plazo de ARGOS · GraphRAG sobre catálogo de productos y librería de ads.

## Rol y responsabilidades

- **Embed productos** de `products_catalog` (texto: nombre + compatible_motos + categoria) en `products_embeddings` (Qdrant)
- **Embed ads** de `ads_library` (texto: anunciante + copy_titulo + copy_texto truncado) en `ads_embeddings`
- **Búsqueda semántica** sobre ambas colecciones con scope por `workspace_id` (ROG-A3 enforced en query filter)
- **Enriquecimiento del Strategist** · `gather_signals` recibe `memory_agent` opcional · si presente, busca top-3 productos similares a price_changes y top-3 ads similares a new_ads · adjunta a `_Signals` como `related_products` y `related_ads`

## Modelo y proveedor

| Componente | Modelo | Dim | Costo |
|---|---|---|---|
| Embedding (Build 3.2) | OpenAI `text-embedding-3-small` | 1536 | ~$0.02 / 1M tokens |
| Embedding alterno (DT futura) | Voyage `voyage-3-large` | 1024 | ~$0.18 / 1M tokens |

Build 3.2 usa SOLO OpenAI por consistencia de dimensión con Qdrant. Voyage queda como deuda técnica con `VOYAGE_API_KEY` env reservada · cuando se active requiere colecciones Qdrant separadas (1024 dim) y enrutamiento por workspace.

## Schema de payload Qdrant

### `products_embeddings`

```json
{
  "workspace_id": "RODDOS",
  "sku_normalizado": "meli:MCO-12345",
  "nombre": "Aceite Motul 4T 20W50",
  "source": "meli",
  "precio_actual": 45000.0,
  "compatible_motos": ["TVS Raider 125", "Pulsar 200"]
}
```

### `ads_embeddings`

```json
{
  "workspace_id": "RODDOS",
  "plataforma": "meta",
  "anunciante": "Repuestos Bogotá Online",
  "copy_titulo": "Pastillas freno · 30% off",
  "ad_id_externo": "ARCHIVE-12345",
  "fuente_query": "pastillas freno moto"
}
```

## Lifecycle

1. **Job `memory_embed_job`** corre cada 6h (APScheduler · IntervalTrigger)
2. Query a MongoDB: docs con `embedded_at=null` o ausente · batch size 50 por colección
3. Genera embedding via `OpenAIEmbedder.embed_one(text)` · texto se construye con `_build_product_text` o `_build_ad_text`
4. Upsert en Qdrant (`PointStruct(id=str(_id), vector, payload)`)
5. MongoDB `update_one` → `$set: {embedded_at: now}` para no re-procesar

## Skip silencioso (degradación graceful)

| Condición | Comportamiento |
|---|---|
| Sin `OPENAI_API_KEY` | `OpenAIEmbedder.enabled=False` · `embed()` devuelve `[]` |
| Sin `QDRANT_URL` | `QdrantBackend.enabled=False` · upserts no-op · search devuelve `[]` |
| Cualquiera de los dos faltante | `MemoryAgent.enabled=False` · job retorna `{skipped: 1}` · endpoint `/api/v1/memory/search` retorna `[]` con log warning |
| Error API en runtime | logged como exception · no levanta · job continúa con próximo doc |

## Endpoints

- `GET /api/v1/memory/search?q=texto&type=products|ads&limit=10` · rol ceo · returns `[{point_id, score, ...payload}]` o `[]`

## Caching

Por ahora no hay cache local del MemoryAgent. Cada llamada a `embed_one` pega contra OpenAI. Para queries repetidas (ej. el Strategist itera `gather_signals` 1×/día), el costo es despreciable. Si se vuelve un problema (Phase 5+ con más jobs), agregar cache LRU sobre el texto de input.

## Tests

- `test_memory_embed_product_persiste_en_qdrant` · embed + upsert con payload correcto
- `test_memory_search_retorna_lista_vacia_sin_qdrant` · skip silencioso
- `test_memory_search_retorna_hits_con_score` · search devuelve hits normalizados con score
- `test_embed_pending_job_solo_procesa_no_embedded` · idempotencia por `embedded_at` field

## ROGs aplicadas

- **ROG-A3** (multi-tenant): toda búsqueda incluye filter `workspace_id`. El payload de cada point lo persiste para auditoría.
- **ROG-A4** (credenciales cifradas): `OPENAI_API_KEY` y `QDRANT_API_KEY` viven solo en env vars · nunca en código ni logs.
