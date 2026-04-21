# docs/knowledge/agents/social.md

# Social Agent

Agente N1 de social listening en IG, TikTok, YouTube Shorts.

## Identidad

- Nivel: N1
- Modelo LLM: Claude Sonnet 4.6 con vision para análisis de reels
- Stack: Python + TikHub.io
- Persistencia: `social_accounts`, `social_posts`
- Eventos producidos: social.account.viral_detected, social.reel.viral

## Misión

Detectar contenido viral en el mundo de motos, delivery y mototaxi en Colombia y LATAM:
- Cuentas de mototaxistas / deliverys influyentes
- Reels virales con repuestos o tips de mantenimiento
- Reviews de TVS Raider y otras motos del portafolio
- Tendencias estéticas (modificaciones, accesorios) que impactan demanda

## Tools permitidos

- tikhub.tiktok.* APIs
- tikhub.instagram.* APIs
- tikhub.youtube.shorts APIs
- mongodb.write.social_accounts
- mongodb.write.social_posts
- claude.sonnet.vision() (analizar frames de reel · identificar productos visibles)
- claude.sonnet.analyze() (extraer relacion entre post y SKUs)

## Política

- Refresh diario 07:00 de cuentas tracked
- Detección automática de virales (views > 100K en <7 días) → event social.reel.viral
- Sin interacción con posts (nunca like, comment, follow · ROG-A9)

## ROGs relevantes

- ROG-A9: cero PII de creadores (solo handles públicos y métricas agregadas)

## Tests

- SO-01: Detecta reel viral de TVS Raider y lo correlaciona con SKU moto
- SO-02: Identifica producto en reel usando vision en 80% de casos con producto visible
- SO-03: Sin interacciones en plataformas (ROG-A9)
