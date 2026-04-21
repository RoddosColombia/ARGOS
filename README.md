# ARGOS

Cerebro de inteligencia comercial + frontend conversacional WhatsApp + motor de score crediticio de **RODDOS S.A.S.**

- **Vertical primario:** REPUESTOS para motos (negocio recurrente · LTV 5 años)
- **Vertical secundario:** VENTA DE MOTOS (puerta de entrada al cliente)
- **Arquitectura:** multi-tenant desde día 1 · multi-agente (11 agentes) sobre bus de eventos append-only
- **Stack:** Python 3.11 + FastAPI + LangGraph + React 19 + TypeScript + MongoDB Atlas + Render
- **Modelos LLM:** Claude Sonnet 4.6 (default) · Haiku 4.5 (intent, tareas simples) · Opus 4.7 (Strategist y casos críticos)

> La tesis, arquitectura y plan de 10 fases vive en [`docs/VISION_2_0.md`](docs/VISION_2_0.md) (fuente original: `ARGOS_VISION_2.0.docx`).

---

## Lectura obligatoria antes de tocar código

En este orden:

1. [`CLAUDE.md`](CLAUDE.md) — reglas inamovibles del repo (ROG-A1 a A12, ROG-W1 a W8, ROG-S1 a S6)
2. [`DECISIONES_V5.md`](DECISIONES_V5.md) — 10 decisiones del CEO ya respondidas
3. [`docs/VISION_2_0.md`](docs/VISION_2_0.md) — documento ejecutivo maestro
4. [`docs/canonicas/`](docs/canonicas/) — mapas de conexión (eventos, APIs, colecciones, flujos)
5. [`docs/knowledge/`](docs/knowledge/) — configuración de agentes, skills, stack, partners
6. [`docs/claude/errores_recurrentes.md`](docs/claude/errores_recurrentes.md) — errores ya conocidos · no repetir
7. [`.planning/phase_0_prompt.md`](.planning/phase_0_prompt.md) — prompt activo de la fase en curso

**Regla:** cada PR que toque una integración actualiza la canónica correspondiente en el mismo PR.

---

## Estructura

```
ARGOS/
├── CLAUDE.md                       ← reglas inamovibles (primera lectura)
├── DECISIONES_V5.md                ← decisiones del CEO
├── ARGOS_VISION_2.0.docx           ← documento ejecutivo (fuente)
├── docs/
│   ├── VISION_2_0.md               ← copia markdown del ejecutivo
│   ├── canonicas/                  ← mapas de conexión del sistema
│   ├── claude/                     ← bitácora arquitectónica por fase (WORM)
│   └── knowledge/                  ← agents/, skills/, stack, partners, modelos_llm
├── .planning/                      ← prompts secuenciales por fase
├── src/                            ← código backend + frontend (Build 0.2+)
└── tests/                          ← suite de tests
```

---

## Setup local (developer)

### Pre-requisitos

- Python 3.11 (exacto · versiones pineadas en `pyproject.toml` cuando exista)
- Node 20 LTS
- Git
- Cuenta MongoDB Atlas con acceso al cluster `argos-prod` (se provisiona en Build 0.3)

### Clonar y preparar

```bash
git clone https://github.com/RoddosColombia/ARGOS.git
cd ARGOS
```

### Backend (disponible desde Build 0.2)

```bash
cd src/backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env        # editar con credenciales locales
pytest
uvicorn argos.main:app --reload --port 8000
```

### Frontend (disponible desde Build 0.4)

```bash
cd src/frontend
npm install
npm run dev
```

### Variables de entorno

Los secrets reales viven en Render (variables de entorno del service). Localmente se usa `.env` (ignorado por git · ver [`.gitignore`](.gitignore)). El catálogo de credenciales requeridas está en [`docs/knowledge/partners.md`](docs/knowledge/partners.md).

---

## Convenciones de commits

**Conventional Commits con scope obligatorio** (ver `CLAUDE.md` §5.2):

```
<type>(<scope>): <subject>

[body opcional]

Refs: phase_X/build_Y
```

- **types:** `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `perf`, `ci`, `build`
- **scopes válidos:** `scoring`, `whatsapp`, `marketplace`, `trends`, `competitors`, `social`, `strategist`, `executive`, `media_buyer`, `compliance`, `scout`, `infra`, `docs`, `sismo`, `partner`

---

## Fase en curso

**Phase 0 · Bootstrap de infraestructura** (semana 1)

Ver [`.planning/phase_0_prompt.md`](.planning/phase_0_prompt.md) para builds y criterios de cierre. Bitácora activa en [`docs/claude/phase_0_bootstrap.md`](docs/claude/phase_0_bootstrap.md).

---

## Qué NO es ARGOS

- No es un CRM (eso es HubSpot)
- No es un ERP completo (eso es SISMO V2)
- No es un sistema contable
- No es un sistema de cobranza puro (eso es RADAR dentro de SISMO V2 · ARGOS dispara pero no procesa)
- No es un reemplazo del motor de score del admin web · es un **clon independiente** para el canal WhatsApp (ROG-S1)

---

**RODDOS S.A.S. · 2026** · Repo privado · Acceso restringido a equipo de producto
