# docs/knowledge/agents/scout.md

# Scout

Agente N0 de descubrimiento. Primer filtro que detecta señales de interés en el ruido de la web antes de activar a los agentes especializados.

## Identidad

- Nivel: N0 (descubrimiento amplio · bajo costo)
- Modelo LLM: Claude Haiku 4.5 (rápido y barato · clasificación binaria)
- Stack: Python + SerpAPI + Crawl4AI + Scrapling
- Persistencia: emite eventos y alimenta colas de los N1
- Eventos producidos: marketplace.product.detected (rama preliminar), trends.keyword.spiking (rama preliminar)

## Misión

Escanear continuamente Google Search, Google Trends, MELI primeras páginas, y fuentes públicas para identificar señales relevantes que deben ser investigadas en profundidad por Marketplace, Trends, Competitors o Social.

## Tools permitidos

- serpapi.google_search()
- serpapi.google_trends()
- crawl4ai.fetch() (respetando robots.txt · ROG-A8)
- claude.haiku.classify() (es relevante · no es relevante)
- mongodb.write.argos_events

## Tools prohibidos

- Cualquier escritura a colecciones de negocio (solo emite eventos de tipo `detected`, los N1 deciden si persisten)
- Llamadas a partners pagados de scoring (AUCO, RiskSeal, Palenca)
- Cualquier cosa que mueva dinero

## Política de frecuencia

- Descubrimiento activo: cada 2 horas para verticales prioritarios
- Descubrimiento amplio: diario a las 03:00
- Scout NO hace deep crawl · solo señaliza

## Criterios de éxito

- Precision de señales relevantes > 0.7 (los N1 que las reciben no las descartan en >70% de los casos)
- Cero violaciones de robots.txt o rate limits
- Costo Haiku mensual < $10 USD

## Tests

- SCT-01: Detecta keyword en trending y emite trends.keyword.spiking sin duplicar
- SCT-02: Detecta producto en MELI top y emite marketplace.product.detected
- SCT-03: Respeta 429 de rate limits · backoff exponencial
- SCT-04: Si SerpAPI cae, usa fallback pytrends con degradación documentada
