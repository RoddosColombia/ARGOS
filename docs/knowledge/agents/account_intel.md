# docs/knowledge/agents/account_intel.md

# Account Intel Agent

Agente N2 de competitive intelligence. Trackea continuamente las cuentas que dominan el ecosistema digital de motos/repuestos y extrae playbook semanal.

## Identidad

- Nivel: N2 (síntesis estratégica · alta consecuencia)
- Modelo LLM: Claude Sonnet 4.6 default · Opus 4.7 para extracción de playbook profundo
- Stack: Python + MongoDB + Apify/TikHub/MELI scrapers + LLM synthesis
- Persistencia: `competitor_profiles` (perfiles ricos por cuenta tracked)
- Eventos producidos: `competitor.meli.price_change`, `competitor.meli.new_listing`, `competitor.meli.review_drop`, `competitor.social.viral_post`, `competitor.social.cadence_change`, `competitor.social.product_pivot`, `account_intel.playbook.generated`
- Eventos consumidos: alimentado por scrapers de Marketplace + Social + Apify

## Misión

Conocer íntimamente cómo gana cada competidor relevante en MELI / TikTok / Instagram, qué hacen bien que vale la pena replicar adaptado, y qué errores cometen que vale la pena evitar.

Sub-servicios:

- **`meli_sellers`**: identifica top N (default 20) vendedores en categoría motos+repuestos en MELI rankeados por métrica compuesta (velocidad de reviews + SOV en MELI Ads + posición en ranking algorítmico + volumen de listings activos). Lista refresca semanal. Cada vendedor del top trackeado diariamente.
- **`social_accounts`**: identifica top N (default 30) cuentas en TikTok + Instagram que mueven categoría moto Colombia (por hashtag #motorepuestos, #bajaj, #mototaxi, #pulsar, etc., combinado con engagement absoluto). Lista refresca semanal. Cada cuenta trackeada con cadencia y movimientos.

## Datos por cuenta tracked

Schema `competitor_profiles`:

```
profile_id: string (ej. "meli:tiendaXYZ" | "tiktok:@motoshop_co")
canal: enum [meli, tiktok, instagram]
display_name: string
url_publica: string

snapshot_actual: {
  size_metric: int (followers o reviews/mes según canal),
  top_skus_or_topics: [...],
  pricing_model: enum [premium, dynamic, discount_aggressive, neutral],
  promo_cadence_days: int (cada cuántos días hace ofertas),
  creative_style: enum [video, static, carousel, mixed],
  audience_inferred: {demografia, interests, geo} (para social)
  geo_principal: string,
  badges: array [Mercado_Lider, Tienda_Oficial, Verified, etc.]
}

trayectoria: [
  {
    fecha: date,
    eventos: [{tipo, descripcion, datos}]  // append-only timeline
  }
]

playbook_extraido_actual: {
  generated_at: datetime,
  generated_by: "sonnet-4-6 | opus-4-7",
  movimientos_replicar: [{descripcion, justificacion, evidence_refs}],
  movimientos_evitar: [{descripcion, error_observado, evidence_refs}]
}

embeddings: vector  // para similarity search entre competidores
```

## Capa de extracción de playbook (job semanal)

Cada lunes 04:00 UTC, antes del brief de Strategist y Portfolio:

Por cada `profile_id` del top N tracked:
1. Cargar `trayectoria` últimas 12 semanas
2. Invocar Sonnet 4.6 con prompt: "este competidor opera así. Estos son sus movimientos últimas 12 semanas. ¿Qué patrones detectás? ¿Qué le funcionó? ¿Qué le falló observable?"
3. Output → `playbook_extraido_actual` persistido
4. Cambios significativos vs playbook semana anterior emiten `account_intel.playbook.changed` para alertar a Strategist

## Salida agregada al brief unificado

Cada lunes el brief CEO+CGO incluye sección **"Esta semana en el ecosistema"** con:

- Top 5-10 movimientos de competencia clasificados como **replicar** o **evitar** con justificación
- Alertas de movimientos de alto impacto (ej. top vendedor MELI lanza promo agresiva en SKU donde RODDOS también compite, viral inesperado de cuenta TikTok en categoría)
- Tendencias detectadas a través de múltiples cuentas (ej. "3 de 5 top vendedores subieron precio de pastillas Bajaj 8-15% esta semana")

Cuando el cambio es de alto impacto entre semanas (no esperar al lunes), emisión de alerta tactical a CEO + CGO simultáneamente.

## Tools permitidos

- mongodb.read/write.competitor_profiles
- partners.apify.scrape (MELI listings + competidor sites + IG cuentas)
- partners.tikhub.fetch_account / fetch_posts
- partners.meli.api (search + ads transparency)
- claude.sonnet.synthesize() / claude.opus.reason()
- embeddings.encode() (similarity entre competidores para detectar gemelos)

## Tools prohibidos

- Cualquier acción sobre cuentas competidoras (no comentar, no follow, no mensajes · scraping respetuoso ROG-A8 únicamente)
- Modificación de listings RODDOS (eso es Pricing engine + Media Buyer)
- Decisiones de pauta directa (eso es Media Buyer)

## Frecuencia

- **Identificación de top N**: weekly lunes 02:00 UTC (refresca rankings)
- **Tracking diario por cuenta**: rolling cada 6h para top 20 MELI · cada 12h para top 30 social
- **Extracción de playbook**: weekly lunes 04:00 UTC
- **Alertas tactical**: real-time cuando se detecta evento crítico (delta SOV >20%, viral inesperado, promo agresiva en SKU compartido)

## Criterios de éxito

- Recall ≥80% de los movimientos materiales de competidores top 20 capturados en < 24h
- Playbook brief consumido por CEO + CGO en <10 min cada lunes
- Al menos 1 movimiento "replicar" adoptado por mes que mueva métrica observable (CTR, share, conversion)
- Al menos 1 movimiento "evitar" prevenido por mes (no caer en error documentado)

## ROGs relevantes

- ROG-A3, A6, A12 (estándar)
- ROG-A8 scraping respetuoso · respetar robots.txt + rate limits + proxies residenciales
- ROG-A9 sin PII de clientes de terceros · solo agregados estadísticos y perfiles de cuenta pública (perfectamente legítimo)
- ROG-G1 brief unificado CEO + CGO

## Tests

- AI-01: Top N MELI sellers refrescado weekly con métrica compuesta correctamente calculada
- AI-02: Top N social accounts refrescado weekly por hashtag + engagement
- AI-03: Cambio de precio en SKU tracked → evento `competitor.meli.price_change` emitido en <6h
- AI-04: Viral post detectado (>X views threshold) → evento `competitor.social.viral_post` emitido
- AI-05: Playbook extraído tiene secciones "replicar" y "evitar" con justificación + evidence_refs
- AI-06: Alertas tactical reales (delta SOV >20%) emitidas a CEO + CGO simultáneamente

## Phase de construcción

**Capa 4 · semanas 17-21** del cronograma 2.1.

## Dependencias

- SKU canonicalizer (paralelo en Capa 4) para que cruzar SKUs entre fuentes haga sentido
- Marketplace + Social + Competitors agents (ya en Phase 1) proveen el sensing layer base que se extiende
- Apify, TikHub, SerpAPI, MELI API operativos (ya están)
