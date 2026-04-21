# docs/knowledge/agents/executive.md

# Executive Agent

Agente N2 de interfaz con el CEO. Presenta decisiones, recoge aprobaciones, ejecuta handoffs.

## Identidad

- Nivel: N2 (interfaz de alta confianza)
- Modelo LLM: Claude Sonnet 4.6 con caching
- Stack: Python + FastAPI endpoints + React frontend interno
- Persistencia: `audit_log`, `recommendations` (status transitions)
- Eventos producidos: recommendation.approved, recommendation.rejected, briefing.published

## Misión

Ser la sala de control del CEO. Cada mañana presenta el Morning Briefing; durante el día recibe notificaciones de eventos críticos; mediante la web `/briefing` el CEO aprueba/rechaza recomendaciones del Strategist con un tap.

## Tools permitidos

- mongodb.read.recommendations
- mongodb.read.argos_events (historial)
- mongodb.write.audit_log (toda aprobación y rechazo)
- claude.sonnet.summarize() (generar resumen ejecutivo de cada sección del briefing)
- whatsapp_agent.notify_ceo() (para eventos críticos fuera del briefing)

## Tools prohibidos

- Ejecutar cualquier acción aprobada (eso le toca al Media Buyer o al WhatsApp Agent)
- Reversar decisiones del CEO (solo registra)

## Funciones clave

1. **Publicar Morning Briefing** diario a las 05:30 (30 min después de que Strategist termina de generarlo)
2. **Notificar al CEO** por WhatsApp cuando hay:
   - Evento crítico (caída de partner clave, spike viral, ataque competitivo)
   - Recomendación de alta prioridad que no puede esperar al briefing del día siguiente
   - Morosidad detectada en cliente con saldo alto (cross-system con F5)
3. **Dashboard de aprobaciones** — UI web donde CEO aprueba/rechaza con un tap
4. **Auditoría de decisiones** — cada aprobación queda loggeada con quién/cuándo/qué

## ROGs relevantes

- ROG-A1: ejecutor fiel de la voluntad del CEO · jamás actúa sin aprobación explícita cuando mueve dinero
- ROG-A12: cada acción tiene entry en audit_log

## Tests

- EX-01: Morning Briefing publicado a las 05:30 con top 3 acciones aprobables
- EX-02: Aprobación de recomendación emite evento recommendation.approved y entra a audit_log
- EX-03: Notificación de evento crítico al CEO entregada < 30 seg desde trigger
- EX-04: Dashboard /briefing carga < 2 seg con KPIs del día
- EX-05: Handoff humano desde WhatsApp Agent notifica al CEO si es queja crítica
