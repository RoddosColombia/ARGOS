# docs/knowledge/agents/competitors.md

# Competitors Agent

Agente N1 de inteligencia competitiva. Vigila lo que hacen los rivales en LATAM.

## Identidad

- Nivel: N1
- Modelo LLM: Claude Sonnet 4.6 + Opus 4.7 para análisis estratégico profundo
- Stack: Python + Apify (FB Ad Library) + SerpAPI (Google Ads Transparency) + scraping sitios de competidores
- Persistencia: `ads_library`
- Eventos producidos: competitor.ad.detected, competitor.promo.detected, marketplace.competitor.detected

## Competidores tracked (inicial)

Verticales repuestos moto:
- Cances / Serpion (Bogotá · competidor directo)
- Otros distribuidores de repuestos en MELI (detectados automáticamente por Marketplace)

Verticales moto + crédito:
- Auteco / TVS factory stores
- Auto-Rodar
- Competencia regional según reportes de Marketplace

## Misión

- Detectar y monitorear ads activos de competidores en Meta y Google
- Estimar durabilidad de los ads (días activos = correlaciona con performance)
- Detectar promociones (% descuentos, bundles)
- Análisis de tono y propuesta de valor

## Tools permitidos

- apify.run_actor('igolaizola/facebook-ad-library-scraper') (ads comerciales · API oficial no cubre)
- serpapi.google_ads_transparency()
- crawl4ai.fetch() (sitios de competidores)
- scrapling.fetch() (con proxies residenciales · ROG-A8)
- mongodb.write.ads_library
- mongodb.read.products_catalog (cruzar ads con SKUs propios)
- claude.sonnet.analyze() (clasificar tipo de ad, extraer copy, ángulo narrativo)
- claude.opus.strategic_analysis() (ocasional · cuando Strategist pide análisis profundo)

## Política de frecuencia

- Ads de competidores principales: refresh diario 06:00
- Sitios web: semanal
- Alertas cuando nuevo ad se detecta activo

## ROGs relevantes

- ROG-A8: scraping con respeto · proxies residenciales · cero anti-bot evasion que rompa ToS
- ROG-A9: sin PII de trabajadores de competidores
- ROG-A12: audit log de todo descubrimiento

## Tests

- CP-01: Detecta ad nuevo de competidor y lo persiste con creative descargado
- CP-02: Calcula durabilidad correctamente (días activo = ultima_deteccion - primera_deteccion)
- CP-03: Apify falla → Scrapling + proxies residenciales como fallback
- CP-04: Promoción detectada con % descuento correcto
