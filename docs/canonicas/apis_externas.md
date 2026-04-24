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
| Estado | Tier starter ($49/mes base) |
| Criticidad | Alta |
| Auth | API Token |
| Actors clave | `igolaizola/facebook-ad-library-scraper` · `apify/facebook-marketplace-scraper` |
| Eventos producidos | marketplace.product.detected (rama FB MP), competitor.ad.detected |
| Costo | Pay-per-use · proyectado $80-150/mes en operación normal |
| Fallback | Si Apify cae: Scrapling propio con proxies residenciales como segunda línea |
| Dueño | ARGOS Phase 2 |

## TikHub.io

| Campo | Valor |
|-------|-------|
| Función | Datos sociales TikTok + IG + YouTube + X |
| Estado | Tier básico ($30-50/mes) |
| Criticidad | Media |
| Auth | API Token |
| Endpoints clave | 900+ APIs distintas · ver docs TikHub |
| Eventos producidos | social.account.viral_detected, social.reel.viral |
| Fallback | Si cae: posponer trends sociales hasta restauración |
| Dueño | ARGOS Phase 3 |

## SerpAPI

| Campo | Valor |
|-------|-------|
| Función | Google Trends + Google Search + Google Ads Transparency |
| Estado | 5K queries/mes (~$50/mes) |
| Criticidad | Media |
| Auth | API Key |
| Endpoints clave | `/search` (Google) · `/google_trends_*` (trends) · `/google_ads_transparency` |
| Eventos producidos | trends.keyword.spiking, competitor.ad.detected (rama Google) |
| Fallback | pytrends como secundario (inestable, solo last resort) |
| Dueño | ARGOS Phase 1 (trends), Phase 2 (Google transparency) |

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
