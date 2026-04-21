# docs/knowledge/skills/morning_briefing.md

# Skill: Morning Briefing

Generación diaria del briefing ejecutivo de 5-7 minutos de lectura para el CEO.

**Agente dueño:** Strategist
**Agente que lo publica:** Executive
**Frecuencia:** diaria 05:00 Bogotá (publicación 05:30)
**Canal:** web argos.roddos.com/briefing + notificación WhatsApp al CEO

## Estructura del briefing

Cada briefing tiene exactamente estas secciones:

### 1. Estado del negocio (30 segundos)
- Ventas de ayer (motos + repuestos)
- Cuotas cobradas vs programadas
- Conversaciones WhatsApp cerradas con outcome
- Solicitudes de crédito nuevas y su status

### 2. TOP 3 ACCIONES DEL DÍA (3 minutos)
Lo más importante del briefing. Cada acción incluye:
- **Título** corto (ej: "Bajar precio pastillas Pulsar NS200 6%")
- **Por qué** (evidencia: precio competencia + rotación actual + margen)
- **Impacto esperado** cuantificado
- **Botones [Aprobar] / [Rechazar] / [Postergar]**

Las 3 acciones se seleccionan por priority_score del Strategist (combinación de impacto × urgencia × confianza).

### 3. Alertas (1 minuto)
- Morosidades detectadas
- Fraudes detectados por RiskSeal
- Stocks críticos (slow movers que hay que rematar, quiebres de stock en productos top)
- Competidores con ad nuevo durable (>7 días activo)

### 4. Radar (2 minutos)
- Keywords en spike
- Reels virales relacionados con nuestro vertical
- Nuevos sellers emergentes en MELI

### 5. Hit rate de la semana (1 minuto)
- % recomendaciones aprobadas que dieron resultado
- Lecciones clave de la semana

## Tono

- Directo · sin paja · sin saludos
- Cada sección con bullet points
- Números siempre con contexto (delta vs ayer/semana pasada)
- Acciones con verbo infinitivo al inicio

## Generación técnica

```python
# Prompt base (cacheado)
SYSTEM_PROMPT = """
Eres Strategist, cerebro de ARGOS de RODDOS S.A.S.
Genera un briefing diario ejecutivo para Andrés, CEO.
Formato: markdown con secciones fijas.
Tono: directo, sin paja, números con contexto.
Objetivo: el CEO lee <10 min y aprueba/rechaza top 3 acciones.
Foco del negocio: REPUESTOS recurrente (80%) + motos puerta de entrada (20%).
"""

# Context (dinámico por día)
context = {
  "ventas_ayer": await sismo.sales.daily(yesterday),
  "cobros_ayer": await cobros.daily_stats(yesterday),
  "conversaciones_cerradas": await conversations.stats(yesterday),
  "solicitudes_credito": await scoring.stats(yesterday),
  "recomendaciones_pendientes_ranked": await strategist.top_recommendations(3),
  "alertas_activas": await alerts.current(),
  "keywords_spike": await trends.today_spikes(),
  "reels_virales": await social.weekly_virals(),
  "competitor_new_ads_durable": await competitors.recent_durable_ads(),
  "hit_rate_weekly": await recommendations.hit_rate(last_7_days)
}

briefing_md = await claude.opus.generate(
  system=SYSTEM_PROMPT,
  user=f"Genera el briefing del {today} con este contexto: {context}"
)
```

## Métricas

- Tiempo de generación < 60 seg
- Tiempo que el CEO dedica al briefing: target < 10 min
- % de top 3 acciones aprobadas: target > 50%
- % acciones aprobadas que dan hit en T+7: target > 60%
