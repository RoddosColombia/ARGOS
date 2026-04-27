# docs/canonicas/apis_externas.md

Mapa de integraciones con partners externos. Cada partner tiene endpoints, autenticación, rate limits, criticidad operativa, y comportamiento de fallback.

## Mercately (BSP de WhatsApp)

| Campo | Valor |
|-------|-------|
| Función | Business Solution Provider de WhatsApp Cloud API |
| Estado | Producción · ya integrado en SISMO Build 14 |
| Criticidad | Crítica |
| Auth | API Key + Webhook signature |
| Endpoints clave | `POST /api/messages/send` · `POST /webhook` (recibe mensajes entrantes) |
| Rate limit | Definido por Meta (100K msgs/día post-verificación) |
| Eventos producidos | whatsapp.message.received, whatsapp.message.sent |
| Costos | Ver Meta pricing 2026 · Colombia: marketing $0.0125 USD · utility $0.0008 USD · service window 24h gratis · CTW Free Entry Point 72h gratis |
| Fallback | Si cae: queue local de mensajes salientes con retry exponencial · alertar al CEO en /briefing |
| Dueño | Equipo SISMO V2 (instancia compartida con admin web) · ARGOS reusa misma cuenta WABA |

## Wava (pasarela de pago Nequi/Daviplata)

| Campo | Valor |
|-------|-------|
| Función | Pasarela para cobranza recurrente cuotas semanales + inicial moto + pagos repuestos |
| Estado | Nueva integración a construir |
| Criticidad | Crítica |
| Auth | API Key + HMAC en webhooks |
| Endpoints clave | `POST /api/links/create` (genera link de pago) · `POST /webhook` (recibe confirmación pago) · `GET /api/transactions/{id}` |
| Métodos soportados | Nequi · Daviplata · PSE · Tarjetas tokenizadas PCI |
| Settlement | Martes y viernes a cuenta bancaria configurada |
| Eventos producidos | cobro.link_generated, cobro.pago.recibido |
| Comisión | Por transacción · negociable según volumen · ~2.9% promedio |
| Fallback | Si Wava cae: cobranza queda pausada · ARGOS notifica al CEO · cliente recibe mensaje "estamos teniendo problemas técnicos, te contactamos en 1h" |
| Dueño | ARGOS (nueva integración Visión 2.0) |

## RiskSeal (digital footprint antifraude)

| Campo | Valor |
|-------|-------|
| Función | Antifraude primario para repuestos · digital credit score complementario para motos |
| Estado | Nueva integración a construir |
| Criticidad | Crítica para repuestos · Alta para motos |
| Auth | API Key (Bearer token) |
| Endpoints clave | `POST /api/v1/score` (envía email + phone + IP, recibe digital credit score + 400+ data points + flags fraude) |
| Latencia esperada | < 5 segundos |
| Cobertura | 200+ plataformas · 98% población underserved |
| Eventos producidos | score.partner.queried (con resultado RiskSeal) |
| Decisión soportada | Si RiskSeal flag fraude=true → ROG-S3 rechazo inmediato · si score digital RiskSeal < 30/100 + cliente nuevo → revisión manual |
| Costo | Por consulta · negociar paquete según volumen estimado |
| Fallback | Si RiskSeal cae: para repuestos cliente nuevo no-RODDOS bloquear venta crédito (cash sí permitido) · para motos enviar a revisión manual |
| Dueño | ARGOS (nueva integración Visión 2.0) |

## AUCO (biometría + validación documento)

| Campo | Valor |
|-------|-------|
| Función | Validación biométrica facial + verificación documento de identidad |
| Estado | Producción · ya en uso en onboarding del admin web |
| Criticidad | Crítica |
| Auth | API Key |
| Endpoints clave | `POST /api/biometric/validate` (recibe documento base64 + selfie base64) · `GET /api/biometric/{id}/status` |
| Output | score_biometrico (0-100) · documento_valido (bool) · datos extraídos del documento |
| Latencia esperada | < 30 segundos para validación completa |
| Eventos producidos | score.partner.queried (con resultado AUCO) |
| Decisión soportada | Si score < 70 → ROG-S3 bloqueo inmediato (no continuar evaluación) |
| Fallback | Si AUCO cae: solicitud queda en revisión manual · cliente notificado "validamos manualmente en 4h" |
| Dueño | ARGOS replica integración existente del admin web (clon · ROG-S1) |

## Palenca (verificación ingresos delivery/mototaxi)

| Campo | Valor |
|-------|-------|
| Función | Verifica ingresos reales de trabajadores de Rappi, DiDi, Uber, etc. vía OAuth a la cuenta del trabajador en la app |
| Estado | Producción en admin web · replicar en ARGOS |
| Criticidad | Alta (solo aplica a segmento delivery/mototaxi · ~40% del cliente RODDOS) |
| Auth | API Key + OAuth de la plataforma destino |
| Endpoints clave | `GET /api/income/{user_id}` (después de OAuth con plataforma) |
| Output | activo_meses · ingresos_promedio_semanal · viajes_mes · rating |
| Plataformas soportadas | Rappi · DiDi · Uber · InDriver · Cabify |
| Latencia esperada | < 10 segundos |
| Eventos producidos | score.partner.queried (con resultado Palenca) |
| Decisión soportada | Para trabajadores delivery/mototaxi sustituye consulta a Datacrédito · es la fuente de ingresos verificada |
| Fallback | Si Palenca cae: cliente entra a revisión manual con ingresos auto-declarados |
| Dueño | ARGOS replica integración existente (clon · ROG-S1) |

## Datacrédito (Experian)

| Campo | Valor |
|-------|-------|
| Función | Historial crediticio bancario tradicional |
| Estado | NO automatizado · consulta manual del analista |
| Criticidad | Media |
| Auth | Web portal manual |
| Cuándo se usa | Solo en revisión manual cuando score automático queda en zona gris (450-649) o cuando hay alertas de RiskSeal/AUCO ambiguas |
| Output | Manual · analista lo registra en scoring_solicitudes campo `datacredito_manual_review` |
| Decisión soportada | Apoyo a decisión manual del analista, no automatizable |
| Fallback | N/A (proceso manual) |
| Dueño | Operación humana · admin del CEO/analista |

## process_document_chat (OCR + Claude para análisis de documentos)

| Campo | Valor |
|-------|-------|
| Función | OCR + análisis con Claude de desprendibles de nómina, extractos bancarios, estados de cuenta de billeteras |
| Estado | Producción · ya implementado en admin web |
| Criticidad | Alta (cuando aplica) |
| Auth | Internal · ya provisto por Anthropic API |
| Endpoints clave | Función Python `process_document_chat(documentos: list) -> dict` |
| Output | ingreso_verificado · gastos_verificados · señales_fraude (bool) · coherencia_con_declarado (0-1) |
| Eventos producidos | score.claude.adjusted |
| Fallback | Si Claude cae: usar solo datos auto-declarados con flag de menor confianza |
| Dueño | ARGOS replica integración existente (clon · ROG-S1) |

## MercadoLibre API

| Campo | Valor |
|-------|-------|
| Función | Datos de marketplace MELI Colombia para inteligencia de repuestos |
| Estado | Producción parcial desde Build 1.0 (search + item públicos · sin OAuth) |
| Criticidad | Alta |
| Auth | OAuth 2.0 (diferido · solo si se necesita seller data privada en builds futuros) |
| SDK | **Sin SDK oficial** en Build 1.0 · `httpx.AsyncClient` directo sobre endpoints públicos · revisar `mercadolibre/python-sdk` cuando se agregue OAuth |
| Endpoints clave | `GET /sites/MCO/search?q=&limit=&offset=` · `GET /items/{id}` · `GET /users/{seller_id}` (último no usado hasta OAuth) |
| Rate limit | No observado límite público hasta ~10 req/s · respetar (ROG-A8) con `asyncio.Semaphore(5)` en el cliente |
| Eventos producidos | `marketplace.product.detected` · `marketplace.price.changed` (threshold ≥ 5%) |
| Costo | Gratis (endpoints públicos) |
| Fallback | Si cae: scraping con Scrapling como respaldo (con respeto a robots.txt) |
| Dueño | ARGOS Phase 1 Build 1.0+ |
| Notas de implementación | `argos/partners/meli/client.py` · context-manager async · maneja 404 y 429 con `MeliError`. Consumido por `agents/marketplace/service.py::upsert_product` (normaliza y persiste en `products_catalog`). |

## Meta Marketing API + Meta Ad Library

| Campo | Valor |
|-------|-------|
| Función | Lanzar pauta CTW + Click-to-WhatsApp ads + Ad Library para inteligencia competitiva (limitado a políticos vía API oficial) |
| Estado | System User ARGOS dedicado dentro de BM existente RODDOS · aprovecha app review ya otorgado · si requiere permisos adicionales se solicita extensión |
| Criticidad | Alta |
| Auth | OAuth 2.0 + Business Manager |
| Endpoints clave | `/act_{ad_account_id}/campaigns` · `/act_{ad_account_id}/adsets` · `/act_{ad_account_id}/ads` |
| Para ads comerciales | Apify actor (igolaizola/facebook-ad-library-scraper) — API oficial NO cubre comerciales |
| Eventos producidos | competitor.ad.detected, campaign.created, campaign.metrics.updated |
| Spending caps | Validados en código por Compliance Officer (ROG-A2) |
| Fallback | Si cae: pauta queda pausada, alerta CEO inmediata |
| Dueño | ARGOS Phase 5 |

## Google Ads API + Google Ads Transparency

| Campo | Valor |
|-------|-------|
| Función | Pauta search + transparencia de ads competidores |
| Estado | Service Account ARGOS dedicado dentro de MCC existente RODDOS · aprovecha app review ya otorgado |
| Criticidad | Alta |
| Auth | OAuth 2.0 + MCC |
| Para transparencia | SerpAPI (Google Ads Transparency Center) |
| Eventos producidos | competitor.ad.detected, campaign.created |
| Fallback | Si cae: pauta queda pausada |
| Dueño | ARGOS Phase 5 |

## Apify (scrapers FB Marketplace + FB Ads + IG)

| Campo | Valor |
|-------|-------|
| Función | Scraping FB Marketplace + Meta Ad Library comercial + IG profiles |
| Estado | Producción parcial desde Build 1.1 (FB Marketplace) y Build 2.1 (FB Ad Library) · sin token configurado todavía · skip silencioso |
| Criticidad | Alta |
| Auth | API Token (`APIFY_API_TOKEN` env var) |
| SDK | **Sin SDK oficial async** · `httpx.AsyncClient` directo sobre `/v2/acts/{actorId}/run-sync-get-dataset-items` |
| Actor Build 1.1 | `apify~facebook-marketplace-scraper` (FB Marketplace search por país + max items) |
| Actor Build 2.1 | `apify~facebook-ad-library-scraper` (Meta Ad Library · input `{searchTerms: [...], country: "CO", maxItems, adType: "all"}`) |
| Actors futuros | `apify/instagram-scraper` (Build 7 · social) |
| Endpoint genérico | `POST /v2/acts/{actor_id}/run-sync-get-dataset-items?token=...` body = actor_input |
| Rate limit | Por plan · starter ~10 actors paralelos · respetar (ROG-A8) |
| Eventos producidos | marketplace.product.detected (rama fb_marketplace) · competitors.ad.detected (Build 2.1) · scout.product.discarded (cuando classifier rechaza) |
| Costo | Pay-per-use · proyectado $80-150/mes en operación normal · Build 1.1 sin token = $0 |
| Fallback | Si Apify cae: Scrapling propio con proxies residenciales como segunda línea (Build 2+) |
| Dueño | ARGOS desde Build 1.1 |
| Notas de implementación | `argos/partners/apify/client.py` · `ApifyClient(api_token).enabled` indica si está configurado · `fb_marketplace_search()` devuelve `[]` silenciosamente sin token (no levanta) · 401/429 → `ApifyError` · Scout aísla fallos por query |

## TikHub.io

| Campo | Valor |
|-------|-------|
| Función | Datos sociales TikTok + IG + YouTube + X |
| Estado | Producción parcial desde Build 2.3 (TikTok + IG · sin token configurado · skip silencioso) |
| Criticidad | Media |
| Auth | API Token (`TIKHUB_API_KEY` env var) · header `Authorization: Bearer {token}` |
| Tier | básico $30-50/mes |
| SDK | **Sin SDK oficial async** · `httpx.AsyncClient` directo · base URL `https://api.tikhub.io` |
| Endpoints Build 2.3 (search users) | `/api/v1/tiktok/web/fetch_user_search_result?keyword=KEY` · `/api/v1/instagram/web/fetch_search_user?keyword=KEY` |
| Endpoints Build 2.3 (user posts) | `/api/v1/tiktok/web/fetch_user_post?secUid=XXX&count=N` (TikTok requiere `sec_uid` que viene del search) · `/api/v1/instagram/web/fetch_user_posts?username=XXX` |
| Endpoints futuros | YouTube Shorts (Phase 7) · X/Twitter (Phase 8+) |
| Aliases tolerados en parser | users: `data/users/user_list/results` · posts: `data/aweme_list/posts/items/media` (cliente abstrae la variabilidad) |
| Eventos producidos | `social.account.trending` (Build 2.3+) · `social.reel.viral` (futuro · cuando se agregue rank histórico) |
| Costo | Pay-per-call · paquete básico $30-50/mes alcanza para ~3K calls/día |
| Fallback | Si cae: posponer social refresh hasta restauración · job es non-blocking · errores aislados por keyword |
| Dueño | ARGOS desde Build 2.3 |
| Notas de implementación | `argos/partners/tikhub/client.py` · `enabled` por presencia de API key · `search_users(platform, query)` + `user_posts(platform, username, sec_uid)` métodos públicos · TikHubError para 401/429 · Consumido por `agents/social/service.py::SocialAgent` |

## SerpAPI

| Campo | Valor |
|-------|-------|
| Función | Google Trends + Google Search + Google Ads Transparency |
| Estado | Producción parcial desde Build 1.3 (Google Trends · sin key configurada por default · skip silencioso) |
| Criticidad | Media |
| Auth | API Key (`SERPAPI_API_KEY` env var) |
| Tier | 5K queries/mes (~$50/mes) |
| SDK | **Sin SDK oficial async** · `httpx.AsyncClient` directo sobre `/search.json` |
| Endpoint Build 1.3 | `GET /search.json?engine=google_trends&q=KEYWORD&geo=CO&date=now+7-d&api_key=...` |
| Endpoint Build 2.2 | `GET /search.json?engine=google_ads_transparency_center&text=KEYWORD&region=CO&api_key=...` (lista de `ad_creatives`) |
| Endpoints futuros | `/search.json?engine=google` (Build 1.4+) |
| Output `interest_over_time.timeline_data` | array de `{date, values: [{extracted_value: 0-100}]}` · TrendsAgent toma último valor + delta vs primero (ventana 7d) |
| Eventos producidos | `trends.keyword.spike` (delta 7d > 30% O interest ≥ 80) · `competitors.ad.detected` (rama Google · Build 2.2+) |
| Notas Build 2.2 | Wrapper `argos/partners/serpapi/google_ads.py::search_google_ads_transparency()` busca lista bajo aliases `ad_creatives/ads/creatives/text_ads`. Output schema toleranta variaciones del engine SerpAPI · campos esperados por ad: `creative_id`, `advertiser_name`, `headline`, `creative_text`, `destination_url`, `first_shown`, `last_shown`, `format` (`TEXT_AD/IMAGE_AD/VIDEO_AD/RESPONSIVE_SEARCH_AD`) |
| Fallback | pytrends como secundario (inestable, solo last resort) |
| Dueño | ARGOS desde Build 1.3 |
| Notas de implementación | `argos/partners/serpapi/client.py` · `enabled` indica configuración · `google_trends()` devuelve `{}` sin key (skip silencioso) · 401/429 → `SerpApiError`. Consumido por `agents/trends/service.py::TrendsAgent` |

## OpenAI (Build 3.2 · embeddings)

| Campo | Valor |
|-------|-------|
| Función | Generación de embeddings para vector search · text-embedding-3-small (1536 dim) |
| Estado | Producción parcial desde Build 3.2 (sin key configurada · MemoryAgent skip silencioso) |
| Criticidad | Media (degradación: el Strategist pierde enriquecimiento semántico pero sigue funcional) |
| Auth | API Key (`OPENAI_API_KEY` env var) |
| SDK | `openai>=1.50,<2.0` async · `AsyncOpenAI(api_key=...).embeddings.create(model=..., input=[...])` |
| Modelo Build 3.2 | `text-embedding-3-small` · 1536 dim · ~$0.02 por 1M tokens · soporta batch |
| Modelos futuros | Whisper (audio en WhatsApp Agent · Build 3.6) · GPT-4 vision como fallback de Sonnet (no planeado) |
| Eventos producidos | N/A (es runtime helper · no emite eventos) |
| Costo proyectado | <$10/mes en Build 3.2 (~5K productos × 1 embed + 1K ads × 1 embed = ~6M tokens iniciales · luego solo deltas) |
| Fallback | Sin key → `OpenAIEmbedder.enabled=False` · `embed()` devuelve `[]` · jobs no-op · search devuelve [] |
| Notas | Build 3.2 NO usa Voyage AI (`voyage-3` es 1024 dim · incompatible con colección 1536) · `VOYAGE_API_KEY` env reservada para futuro multi-provider con colecciones Qdrant separadas por dim |
| Dueño | ARGOS desde Build 3.2 |

## Qdrant (Build 3.2 · vector DB self-hosted)

| Campo | Valor |
|-------|-------|
| Función | Vector database para búsqueda semántica · GraphRAG del Strategist |
| Estado | Producción parcial desde Build 3.2 · self-hosted en Render (sin URL configurada · MemoryAgent skip silencioso) |
| Criticidad | Media (degradación: Strategist pierde enriquecimiento semántico) |
| Auth | URL + API Key opcional (`QDRANT_URL` + `QDRANT_API_KEY` env vars) |
| SDK | `qdrant-client>=1.10,<2.0` · `AsyncQdrantClient(url=..., api_key=...)` |
| Colecciones Build 3.2 | `products_embeddings` y `ads_embeddings` · ambas dim=1536 distance=COSINE |
| Operaciones usadas | `create_collection` (idempotente) · `upsert(PointStruct)` · `query_points` con filter por workspace_id |
| Filtro multi-tenant | Cada `search` aplica `Filter(must=[FieldCondition(key="workspace_id", match=MatchValue(value=...))])` (ROG-A3) |
| Costo proyectado | $0/mes (self-hosted gratis en Render · usa Persistent Disk) |
| Fallback | Sin URL → operations son no-op · search devuelve [] sin levantar |
| Notas | `argos/partners/qdrant/client.py::QdrantBackend` envuelve el cliente async con skip silencioso · `ensure_collections()` se llama en cada job para garantizar idempotencia · sin migraciones si dim/distance no cambian |
| Dueño | ARGOS desde Build 3.2 |

## Anthropic API (Claude)

| Campo | Valor |
|-------|-------|
| Función | LLM para todos los agentes que razonan: WhatsApp Agent, Score Engine (Capa 2), Strategist, Executive, Compliance Officer (parcial), Marketplace, Trends, Competitors, Social |
| Estado | Producción |
| Criticidad | Crítica |
| Auth | API Key |
| Modelos | Sonnet 4.6 (default · $3/$15 por MTok) · Haiku 4.5 (clasificación · $1/$5) · Opus 4.7 (Strategist y casos críticos · $5/$25) |
| Features clave | Prompt caching agresivo · Vision incluida · Batch API para reportes asincrónicos |
| Eventos producidos | N/A (es runtime, no genera eventos directamente) |
| Costo proyectado | $130-150 USD/mes en operación normal con caching activo |
| Fallback | Si cae: agentes pasan a modo degradado · Compliance Officer pausa todas las acciones que muevan dinero |
| Dueño | ARGOS desde Phase 0 |

## SISMO V2 (Build 4.1 · ERP RODDOS · read-only)

| Campo | Valor |
|-------|-------|
| Función | Fuente de verdad de inventario (`/api/inventory/repuestos`, `/api/inventory/slow_movers`), ventas (`/api/sales/daily?date=YYYY-MM-DD`) y eventualmente loanbook · ARGOS solo CONSUME read-only |
| Estado | Build 4.1 lectura activa · escritura sigue siendo dominio del admin web (ROG-A11) |
| Criticidad | Alta (alimenta `Strategist.gather_signals` con contexto de inventario · sin sync el LLM no puede recomendar liquidaciones) |
| Auth | `Authorization: Bearer {SISMO_API_KEY}` · key con SCOPE READ-ONLY (CEO emite key dedicada para ARGOS · ROG-A11) |
| Base URL | `SISMO_API_URL` (variable env · ej. `https://sismo.roddos.internal`) |
| Endpoints consumidos | `GET /api/inventory/repuestos` → lista SKUs · `GET /api/inventory/slow_movers` → SKUs ≥45d sin rotación · `GET /api/sales/daily?date=YYYY-MM-DD` → ventas día por SKU |
| Cliente | `argos/partners/sismo/client.py` · `SismoClient` async context manager con httpx · skip silencioso si URL+KEY vacíos · parser defensivo acepta `[...]` directo o `{items|data|results: [...]}` |
| Persistencia | Snapshot diario en colección `sismo_inventory` · idempotente por `(workspace_id, sku, fecha_sync_date)` |
| Eventos producidos | `sismo.inventory.synced` (Build 4.1) tras cada sync exitoso |
| Rate limits | Documentados en lado SISMO · cliente aplica `timeout=30s` y propaga 429 como `SismoError(429)` |
| Fallback | Si SISMO cae: el job loguea `SismoError` y skipa el día · el último snapshot sigue siendo accesible vía `/api/v1/sismo/inventory` (read sobre Mongo, no llama SISMO en runtime) |
| Dueño | RODDOS S.A.S. (admin web) · ARGOS es consumidor |

## Score Engine externo (Phase 2 · repo independiente de Iván)

| Campo | Valor |
|-------|-------|
| Función | Motor crediticio que evalúa solicitudes (RiskSeal + AUCO + Palenca + XGBoost + Claude) y persiste resultados en MongoDB compartido. ARGOS NO ejecuta scores · es pass-through HTTP. |
| Estado | Phase 2 · ARGOS lo expone vía `POST /api/v1/score/evaluate` (forward) y `GET /api/v1/score/solicitudes` (lee desde shared DB). |
| Criticidad | Crítica para flujo de crédito · pero ARGOS sigue funcionando si está down (frontend muestra `decision="no_configurado"` o lista vacía) |
| Auth | `Authorization: Bearer {SCORE_ENGINE_API_KEY}` · key emitida por el repo de Iván · scope: solo `/v1/evaluate` |
| Base URL | `SCORE_ENGINE_API_URL` (env var · ej. `https://score-engine.roddos.internal`) |
| Endpoints consumidos | `POST /v1/evaluate` con payload KYC + partners → respuesta `{decision, score_final, solicitud_id, narrativa, ...}` |
| Cliente | `argos/agents/score/client.py` · `ScoreEngineClient` async (httpx) · timeout 10s · 1 retry en 5xx · skip silencioso sin URL → mock `decision="no_configurado"` |
| Persistencia | Score Engine escribe en `RODDOS_MONGODB_URI` DB `roddos_comercial` colección `scoring_solicitudes`. ARGOS lee con `ScoreReader` |
| Eventos producidos | `score.evaluated` lo emite el Score Engine en su propio bus interno · ARGOS no consume directamente del bus de Iván |
| Rate limits | Documentados en repo de Iván · cliente propaga 429 como `ScoreEngineError` |
| Fallback | Si Score Engine cae: ARGOS devuelve `502 Bad Gateway` con detalle del status upstream · frontend muestra error pero el dashboard sigue navegable |
| Dueño | Iván (RODDOS) · repo separado · ROG-S1 cero llamadas cruzadas en runtime · ARGOS solo HTTP/Mongo lectura |
