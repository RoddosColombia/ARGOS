# docs/knowledge/stack.md

Stack tecnológico ARGOS Visión 2.0. Versiones pineadas o sus equivalentes a abril 2026.

## Backend

| Componente | Versión | Justificación |
|------------|---------|---------------|
| Python | 3.11.x | Estable · async maduro · alineado con SISMO V2 |
| FastAPI | 0.110+ | Estándar moderno · OpenAPI auto · async nativo |
| LangGraph | 0.2.x | Orquestador multi-agente · supervisor pattern · checkpointing |
| Anthropic SDK | últimas | Claude Sonnet 4.6 · Haiku 4.5 · Opus 4.7 con caching |
| Motor (MongoDB driver) | 3.5+ | Async MongoDB |
| httpx | 0.27+ | Cliente async para partners externos |
| Celery + Redis | 5.x | Cola de jobs distribuida |
| Scrapling | 0.x (más reciente) | Scraping con stealth + adaptive selectors + MCP |
| Crawl4AI | 0.x | Reemplazo de Firecrawl · Apache-2.0 · self-hostable |
| Playwright (vía Patchright) | última | Stealth browser para scraping cuando se necesita |
| scikit-learn + XGBoost | 2.x | Score Engine Capa 1 |
| joblib | 1.x | Serialización del modelo XGBoost · hash para versionado |
| openai (solo Whisper) | última | Transcripción de notas de voz WhatsApp |

## Frontend (web interno · CEO + analista)

| Componente | Versión | Notas |
|------------|---------|-------|
| React | 19.x | Estándar moderno |
| TypeScript | 5.x | Strict mode obligatorio |
| Vite | 5.x | Build tool |
| TanStack Query | 5.x | Estado de servidor · cache de llamadas API |
| TailwindCSS | 4.x | Sistema de diseño · provisto por CEO |
| Recharts | 2.x | Charts del dashboard |
| shadcn/ui | última | Componentes base |
| zod | 3.x | Validación de schemas |
| react-hook-form | 7.x | Formularios |

## Datos

| Componente | Notas |
|------------|-------|
| MongoDB Atlas | Inicia en M2 ($9/mes), promueve a M10 ($57/mes) en Phase 2 (FB Marketplace ingest) |
| Backups | Snapshots diarios nativos + Point-in-Time Recovery |
| Qdrant | Self-hosted en Render · vector DB para GraphRAG (Phase 5) |
| Redis | Self-hosted en Render · cola Celery + caché |
| Render Persistent Disk | Para creatives descargados, HTMLs scrapeados, modelos XGBoost serializados |

## Infraestructura

| Componente | Proveedor | Notas |
|------------|-----------|-------|
| Backend | Render Starter ($7/mes inicio · escala según carga) | Mismo patrón SISMO V2 · autodeploy desde GitHub |
| Frontend | Render Static Site | Gratis · autodeploy desde GitHub |
| DNS | GoDaddy · CNAME argos.roddos.com → Render | Existente |
| SSL | Let's Encrypt automático en Render | Gratis |
| CI/CD | GitHub Actions | Hasta 2000 min/mes gratis |
| Observabilidad LLM | Langfuse self-hosted en Render | Trazas, costos, debug de prompts |
| Logs aplicación | Render logs + structured JSON logging | |
| Secrets | Render env vars + GitHub Secrets | Rotación mensual de tokens críticos |

## Integraciones externas

Ver detalle completo en docs/canonicas/apis_externas.md y docs/knowledge/partners.md.

Resumen:
- **WhatsApp:** Mercately (BSP existente vía SISMO Build 14)
- **Pagos:** Wava (Nequi + Daviplata + PSE + tarjetas)
- **Antifraude / scoring:** RiskSeal
- **Biometría:** AUCO
- **Ingresos delivery/mototaxi:** Palenca
- **Datacrédito:** Manual (no API)
- **MELI:** SDK oficial mercadolibre/python-sdk
- **Meta Ads + Ad Library comercial:** OAuth + Apify
- **Google Ads + Transparency:** OAuth + SerpAPI
- **TikTok / IG / YouTube:** TikHub.io
- **Trends:** SerpAPI primario, pytrends fallback
- **LLMs:** Anthropic API

## Versiones de modelos LLM pineadas (ROG implícita · evita drift)

- Default: `claude-sonnet-4-6-20260301` (placeholder · pinear el real)
- Tareas simples: `claude-haiku-4-5-20251001`
- Strategist y casos críticos: `claude-opus-4-7-20260416`

Cualquier upgrade de modelo requiere canary contra dataset de evals (ROG en Phase 5 sistema de evals).

## Costos proyectados (USD/mes · operación normal post-Phase 5)

| Concepto | Costo |
|----------|-------|
| Render Starter backend | $7 |
| Render Static frontend | $0 |
| MongoDB Atlas M10 | $57 |
| Qdrant + Redis self-hosted | $0 (Render) |
| Render Persistent Disk | $10-20 |
| Anthropic API + caching | $130-180 (sube con WhatsApp Agent activo) |
| Mercately / WhatsApp Meta | variable según volumen · ver pricing en apis_externas.md |
| Wava | comisión por transacción ~2.9% · no fijo |
| RiskSeal | por consulta · negociar paquete |
| AUCO | por validación · negociar paquete |
| Palenca | por consulta · negociar paquete |
| Apify | $80-150 |
| ProxyRack | $80-120 |
| TikHub.io | $30-50 |
| SerpAPI | $50 |
| **Subtotal infra + APIs** | **~$650-850 USD/mes** |
| + Pauta digital ejecutada por Media Buyer | variable · es presupuesto de marketing, no infra |
| + Comisión Wava por transacción | variable · es costo de venta |

## Política de versionado del repo

- Semver para releases (`v1.2.3`)
- Tag por phase: `phase-X-closed` cuando se cierra una phase
- Ramas: `main` (producción) · `dev` (integración) · `feature/<phase-X-build-Y-descripcion>`
- Protección de main: requiere PR + CI verde + 1 approval (vía GitHub branch protection)
- Cada release notes debe linkear a la bitácora docs/claude/phase_X.md correspondiente
