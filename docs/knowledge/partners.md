# docs/knowledge/partners.md

Configuración operativa de cada partner. Este archivo es complementario a docs/canonicas/apis_externas.md (que tiene endpoints) — aquí están los datos de cuenta, contactos comerciales, contratos, política de uso.

## Mercately

| Campo | Valor |
|-------|-------|
| Producto | BSP de WhatsApp Cloud API |
| Cuenta | Compartida con SISMO V2 (Build 14) — ARGOS reusa misma WABA |
| Número WhatsApp | (definir · separado del personal del CEO) |
| Plan | Definir según volumen proyectado |
| Contacto comercial | Definir |
| Política | Cero markup sobre rates Meta · oficial Tech Partner |
| Documentación interna | (linkear) |

## Wava

| Campo | Valor |
|-------|-------|
| Producto | Pasarela Nequi + Daviplata + PSE + Tarjetas tokenizadas |
| Cuenta | Nueva · a crear en Phase 4 |
| Régimen tributario RODDOS | (definir) |
| Documentos requeridos para alta | RUT · Cámara y comercio · Documento del representante legal · Certificado bancario |
| Settlement | Martes y viernes · cuenta bancaria de RODDOS (definir) |
| Comisión | Negociable según volumen · ~2.9% promedio referencia |
| Webhook URL ARGOS | https://argos.roddos.com/api/v1/cobranza/wava-webhook |
| HMAC secret | en secrets manager · rotación mensual |
| Contacto comercial | Definir |

## RiskSeal

| Campo | Valor |
|-------|-------|
| Producto | Digital footprint analysis · 400+ data points · 200+ plataformas |
| Cuenta | Nueva · a crear en Phase 2 |
| Plan | Negociar · solicitar PoC gratis primero |
| Modelo de cobro | Por consulta · negociar paquete |
| API base | https://api.riskseal.io/v1/ |
| API Key | en secrets manager |
| Política de uso ARGOS | Antifraude PRIMARIO para todas las solicitudes de Crédito Rodante (repuestos · ROG-S1) · score complementario para RDX Leasing (motos) |
| Compliance | Públicos signals + consented data sharing · GDPR + LFPDPPP compatible |
| Contacto comercial | Definir |

## AUCO

| Campo | Valor |
|-------|-------|
| Producto | Validación biométrica facial + verificación documento de identidad |
| Cuenta | Existente · ya usada en admin web |
| Documentación interna | (linkear desde admin web) |
| API Key | replicar en ARGOS secrets manager (separada de la del admin web · ROG-A11) |
| Webhook | si aplica |
| Contacto comercial | (heredar de admin web) |

## Palenca

| Campo | Valor |
|-------|-------|
| Producto | Verificación de ingresos para trabajadores delivery / mototaxi |
| Cuenta | Existente · usada en admin web |
| API Key | replicar en ARGOS (separada · ROG-A11) |
| Plataformas habilitadas | Rappi · DiDi · Uber · InDriver · Cabify (verificar cuáles están activas en cuenta RODDOS) |
| Flujo OAuth | Cliente da consentimiento OAuth a Palenca para que Palenca lea su cuenta de la plataforma origen |
| Política | Solo se ejecuta si tipo_empleo in [delivery, mototaxi] |
| Contacto comercial | (heredar de admin web) |

## Datacrédito (Experian)

| Campo | Valor |
|-------|-------|
| Producto | Historial crediticio bancario tradicional |
| Modo | MANUAL · NO API |
| Cuándo se usa | Solo en revisión manual del analista · zona gris del score (450-649) o señales ambiguas |
| Acceso | Portal web Datacrédito · cuenta del analista en RODDOS |
| Política | NO automatizable en flujo ARGOS |
| Contacto comercial | (existente RODDOS) |

## MercadoLibre

| Campo | Valor |
|-------|-------|
| Producto | API oficial MELI |
| Cuenta | Aplicación creada en MELI Developers |
| App ID + secret | en secrets manager |
| OAuth | Para acciones avanzadas (por ahora solo lectura pública) |
| Política | Respetar rate limits · actualizar cada 15 min para SKUs prioritarios |

## Meta (Marketing API + Ad Library + WhatsApp)

| Campo | Valor |
|-------|-------|
| Producto | Pauta + scraping + WhatsApp |
| Business Manager | **Cuenta existente RODDOS** · se crea System User dedicado ARGOS dentro del BM con token propio separado del System User del admin web — cumple ROG-A11 sin duplicar cuenta |
| Razón del uso compartido | Preserva histórico del pixel, learning de conversiones, audiencias lookalike entrenadas (1-2+ años de data) · reportería unificada al CFO · evita app review duplicado · ahorra overhead administrativo |
| Blast radius aislado | Si el token del System User de ARGOS se compromete, se revoca ESE token sin afectar admin web · ROG-A11 se cumple por separación de credencial, no de cuenta |
| App review | Aprovecha el review ya otorgado al BM RODDOS · si ARGOS requiere permisos adicionales (ej: CTW ads), se solicita extensión sobre el BM existente |
| Número WhatsApp Business | El mismo de Mercately (compartido con admin web vía SISMO Build 14) |
| Tokens | OAuth 2.0 · cifrados AES-256 con KMS · rotación mensual (ROG-A4) · tokens de ARGOS separados de tokens del admin web |
| Cuándo considerar cuenta nueva | Solo si el BM RODDOS tiene policy violations históricas que pudieran comprometer reputación de ARGOS · o cuando ARGOS se comercialice como SaaS externo (Phase 9) |

## Google Ads

| Campo | Valor |
|-------|-------|
| Producto | Pauta search + display + transparencia |
| MCC | **MCC existente RODDOS** · se crea Service Account dedicado ARGOS con credenciales separadas del Service Account del admin web — cumple ROG-A11 sin duplicar MCC |
| Razón del uso compartido | Preserva histórico de conversiones, quality scores por keyword, audiencias, smart bidding entrenado · reportería unificada |
| Blast radius aislado | Si las credenciales del Service Account de ARGOS se comprometen, se revoca ese Service Account sin afectar admin web |
| App review | Aprovecha el de la MCC existente · si se requieren permisos adicionales se solicita extensión |
| OAuth / Credenciales | Service Account JSON cifrado at-rest con KMS · rotación trimestral |
| Cuándo considerar MCC nueva | Solo si la MCC existente tiene infracciones históricas o al comercializar ARGOS a terceros (Phase 9) |

## Apify

| Campo | Valor |
|-------|-------|
| Producto | Scrapers gestionados (FB MP, FB Ads, etc.) |
| Cuenta | Nueva tier Starter ($49/mes base) |
| API Token | en secrets manager |
| Actors confirmados | igolaizola/facebook-ad-library-scraper · scrapeio/facebook-marketplace-scraper |

## TikHub.io

| Campo | Valor |
|-------|-------|
| Producto | APIs sociales (TikTok, IG, YouTube, X) |
| Plan | Tier básico |
| API Token | en secrets manager |

## SerpAPI

| Campo | Valor |
|-------|-------|
| Producto | Google Search + Trends + Ads Transparency |
| Plan | 5K queries/mes |
| API Key | en secrets manager |

## ProxyRack

| Campo | Valor |
|-------|-------|
| Producto | Proxies residenciales |
| Plan | Inicial $50/mes · escala con uso |
| Credenciales | en secrets manager |
| Política | Rotación automática · IPs separadas para scraping vs APIs (ROG-R6) |

## Anthropic

| Campo | Valor |
|-------|-------|
| Producto | LLMs Claude |
| Cuenta | Nueva cuenta dedicada a RODDOS para ARGOS |
| API Key | en secrets manager |
| Caching | OBLIGATORIO en todo system prompt > 1000 tokens |
| Modelos pineados | sonnet-4-6-202603XX · haiku-4-5-20251001 · opus-4-7-20260416 |

## Política de rotación de credenciales

- Tokens OAuth (Meta, Google): rotación mensual automática
- API Keys de partners (RiskSeal, AUCO, Palenca, Apify, TikHub, SerpAPI, Wava, Anthropic): rotación trimestral salvo incidente
- HMAC secrets de webhooks: rotación mensual
- Nunca commitear secrets al repo · siempre vía Render env vars + GitHub Secrets
- Cada acceso a un secret se loguea en audit_log (ROG-A4)
