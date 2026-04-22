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

### Backend (Build 0.2+)

`pyproject.toml` vive en la raíz del repo · el paquete en `src/backend/argos/`.

```bash
# desde la raíz del repo
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env               # editar con credenciales locales
pytest tests/backend               # 27 tests (14 unit + 13 integración vs Atlas si hay URI)
uvicorn argos.main:app --reload --app-dir src/backend --port 8000
```

### Frontend (Build 0.4+)

```bash
cd src/frontend
npm install
cp .env.example .env.local         # opcional · default apunta a localhost:8000
npm run dev                        # http://localhost:5173 con proxy /api → backend
```

### Variables de entorno

| Variable | Dev local | Prod (Render) | Descripción |
|---|---|---|---|
| `ARGOS_ENV` | `dev` | `prod` | Ambiente |
| `JWT_SECRET` | generar · 64 chars | Render env | HS256 para JWT |
| `JWT_ACCESS_TOKEN_TTL_MINUTES` | `60` | `60` | TTL del access token |
| `MONGODB_URI` | Atlas dev URI | Render env | Cluster argos-prod |
| `MONGODB_DATABASE` | `argos` | `argos` | DB name |
| `ADMIN_EMAIL` | `ceo@roddos.com` | Render env | Email del CEO admin |
| `ADMIN_PASSWORD_HASH` | bcrypt hash local | Render env | Hash del password (seed lo persiste) |
| `ADMIN_ROLE` | `ceo` | `ceo` | Rol del admin bootstrap |
| `ADMIN_WORKSPACE_ID` | `RODDOS` | `RODDOS` | Workspace primario |
| `ARGOS_CORS_ORIGINS` | `http://localhost:5173` | `https://argos.roddos.com` | Origins permitidos |
| `VITE_ARGOS_API_URL` (frontend) | `http://localhost:8000` | `https://api.argos.roddos.com` | URL del backend |

Los secrets reales viven en Render. Localmente se usa `.env` (ignorado por git · ver [`.gitignore`](.gitignore)). Catálogo de credenciales en [`docs/knowledge/partners.md`](docs/knowledge/partners.md).

---

## Deploy a Render (Build 0.5+)

ARGOS se despliega en **Render con buildpack nativo** (sin Docker · paridad con SISMO V2). Dos servicios separados, configurados manualmente en la UI de Render. GitHub Actions corre CI en cada PR ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)); los deploys los dispara automáticamente la app de Render conectada al repo en cada push a `main`.

### Archivos en el repo

- [`Procfile`](Procfile) · start command del backend (`uvicorn` con `$PORT`)
- [`runtime.txt`](runtime.txt) · pin de Python 3.11.11
- [`pyproject.toml`](pyproject.toml) · detectado por Render como build manifest Python
- [`.github/workflows/ci.yml`](.github/workflows/ci.yml) · lint + tests + build en cada PR
- `src/frontend/package.json` · `build` command leído por Render Static Site

### Pasos manuales del CEO (una sola vez)

**1. Render · crear Web Service (backend)**

En <https://dashboard.render.com> → `New` → `Web Service` → conectar `RoddosColombia/ARGOS`:

| Campo | Valor |
|---|---|
| Name | `argos-backend` |
| Region | Oregon (o más cercana) |
| Branch | `main` |
| Root Directory | (dejar vacío · raíz del repo) |
| Runtime | Python 3 |
| Build Command | `pip install -e .` |
| Start Command | `uvicorn argos.main:app --host 0.0.0.0 --port $PORT --app-dir src/backend --proxy-headers --forwarded-allow-ips '*'` |
| Plan | Starter ($7/mes) |
| Health Check Path | `/api/v1/health` |

En `Environment` → setear las env vars listadas en la tabla de arriba (columna "Prod"). Los secrets (`JWT_SECRET`, `MONGODB_URI`, `ADMIN_EMAIL`, `ADMIN_PASSWORD_HASH`) se pegan directo, sin commitear en el repo.

**2. Render · crear Static Site (frontend)**

`New` → `Static Site` → mismo repo:

| Campo | Valor |
|---|---|
| Name | `argos-frontend` |
| Branch | `main` |
| Root Directory | `src/frontend` |
| Build Command | `npm ci && npm run build` |
| Publish Directory | `dist` |

En `Environment`:
- `VITE_ARGOS_API_URL=https://api.argos.roddos.com`

En `Redirects/Rewrites` (para que react-router maneje rutas client-side):
- Source: `/*` · Destination: `/index.html` · Action: `Rewrite`

**3. GoDaddy · DNS para argos.roddos.com**

| Tipo | Host | Apunta a | TTL |
|---|---|---|---|
| CNAME | `argos` | `argos-frontend.onrender.com` | 1h |
| CNAME | `api.argos` | `argos-backend.onrender.com` | 1h |

**4. Render · custom domains**

- `argos-frontend` → `Settings → Custom Domains` → agregar `argos.roddos.com`
- `argos-backend` → `Settings → Custom Domains` → agregar `api.argos.roddos.com`

Render emite SSL Let's Encrypt automático (~5 min post-propagación DNS).

**5. Validación**

```bash
curl https://api.argos.roddos.com/api/v1/health          # 200 OK
curl https://api.argos.roddos.com/api/v1/health/deep     # 200 con mongodb.state=ok
open https://argos.roddos.com                             # login
```

### Operación

- **Auto-deploy:** habilitado por default vía Render GitHub app · cada push a `main` despliega ambos servicios
- **Rollback:** Render dashboard → servicio → `Events` → deploy anterior → `Rollback`
- **Logs vivos:** `Logs` en cada servicio

### Deuda técnica aceptada

- Sin `Dockerfile` · sin IaC `render.yaml` · config vive en Render UI. Ver [`docs/claude/deuda_tecnica.md`](docs/claude/deuda_tecnica.md) DT-001 y DT-002 para el análisis y las señales que indicarían revisitarlo.

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
