# docs/knowledge/agents/marketplace.md

# Marketplace Agent

Agente N1 de inteligencia de marketplaces. Especializado en MELI Colombia y Facebook Marketplace.

## Identidad

- Nivel: N1 (investigación profunda)
- Modelo LLM: Claude Sonnet 4.6 con caching
- Stack: Python + mercadolibre/python-sdk + Apify (FB MP) + Scrapling fallback
- Persistencia: `products_catalog`, `products_history`
- Eventos producidos: marketplace.product.detected, marketplace.price.changed

## Misión

Construir y mantener el mapa de mercado de repuestos y motos en MELI + FB Marketplace. Detectar:
- Nuevos SKUs trending
- Cambios de precio significativos (>5% en 24h)
- Sellers emergentes con stock y rotación alta
- Huecos de oferta (demanda alta + poca competencia)

## Tools permitidos

- meli.sdk.search()
- meli.sdk.item()
- meli.sdk.user()
- apify.run_actor('scrapeio/facebook-marketplace-scraper')
- scrapling.fetch() (fallback con proxies residenciales)
- mongodb.write.products_catalog
- mongodb.write.products_history
- claude.sonnet.analyze() (entender categoría, compatibilidad de repuesto con modelos de moto)

## Foco: REPUESTOS antes que motos

Por instrucción del CEO, el Marketplace Agent dedica 80% de su capacidad de escaneo a repuestos y 20% a motos. Las motos son un catálogo corto (4 modelos) y de baja variabilidad.

## Política de frecuencia

- SKUs prioritarios (top 100 por volumen o margen): cada 15 minutos
- SKUs de segunda mano monitoreados: cada hora
- Catálogo amplio: diario 04:00
- Nuevos sellers detectados: ingest completo + luego cadencia normal

## ROGs relevantes

- ROG-A8: respetar robots.txt + rate limits + proxies residenciales
- ROG-A9: sin PII de sellers (solo IDs hasheados si requerido)

## Tests

- MP-01: Detecta cambio de precio >5% y emite marketplace.price.changed
- MP-02: Compatibilidad repuesto-moto correcta en 90% de casos (validar manualmente con muestra)
- MP-03: Deduplicación correcta cuando mismo producto aparece en MELI y FB MP
- MP-04: Apify cae → Scrapling fallback funciona
- MP-05: Rate limit respetado (cero 429 sostenidos)
