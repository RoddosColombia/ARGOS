# docs/knowledge/

Configuraciones y skills de los agentes de ARGOS. Toda la "personalidad" técnica del sistema vive aquí.

## Estructura

```
knowledge/
├── README.md
├── agents/                  ← config de los 11 agentes
│   ├── scout.md
│   ├── marketplace.md
│   ├── trends.md
│   ├── competitors.md
│   ├── social.md
│   ├── strategist.md
│   ├── executive.md
│   ├── media_buyer.md
│   ├── compliance_officer.md
│   ├── whatsapp_agent.md
│   └── score_engine.md
├── skills/                  ← prompts y templates reusables
│   ├── morning_briefing.md
│   ├── kyc_conversacional.md
│   ├── negociacion_margen.md
│   ├── cotizador_visual.md
│   ├── recuperacion_carrito.md
│   └── mantenimiento_predictivo.md
├── stack.md                 ← stack tecnológico + versiones pineadas
├── modelos_llm.md           ← qué modelo Claude para qué agente, caching, prompts base
└── partners.md              ← config operativa de cada partner
```

## Reglas

1. Cada agente tiene su archivo .md con: rol, modelo LLM asignado, tools permitidos, tools prohibidos, system prompt base, ejemplos few-shot, criterios de éxito.
2. Cada skill es un módulo reusable que múltiples agentes pueden invocar.
3. Toda actualización de prompt requiere registro en bitácora docs/claude/phase_X.md y tests de regresión.
4. Versiones de modelos LLM pineadas (sonnet-4-6-2026XXXX, no sonnet-latest).
5. Caching activo en TODO system prompt > 1000 tokens (ROG implícita).
