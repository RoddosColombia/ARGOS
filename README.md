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

Los secrets reales viven en Render (Build 0.5+). Localmente se usa `.env` (ignorado por git · ver [`.gitignore`](.gitignore)). Catálogo de credenciales en [`docs/knowledge/partners.md`](docs/knowledge/partners.md).

| Variable | Dev local | Prod (Render) | Descripción |
|---|---|---|---|
| `ARGOS_ENV` | `dev` | `prod` | Ambiente |
| `JWT_SECRET` | generar · 64 chars | Render env (sync: false) | HS256 para JWT |
| `JWT_ACCESS_TOKEN_TTL_MINUTES` | `60` | `60` | TTL del access token |
| `MONGODB_URI` | Atlas dev URI | Render env (sync: false) | Cluster argos-prod |
| `MONGODB_DATABASE` | `argos` | `argos` | DB name |
| `ADMIN_EMAIL` | `ceo@roddos.com` | Render env (sync: false) | Email del CEO admin |
| `ADMIN_PASSWORD_HASH` | bcrypt hash local | Render env (sync: false) | Hash del password (seed lo persiste en users) |
| `ADMIN_ROLE` | `ceo` | `ceo` | Rol del admin bootstrap |
| `ADMIN_WORKSPACE_ID` | `RODDOS` | `RODDOS` | Workspace primario |
| `ARGOS_CORS_ORIGINS` | `http://localhost:5173` | `https://argos.roddos.com` | Origins permitidos |
| `VITE_ARGOS_API_URL` (frontend) | `http://localhost:8000` | `https://api.argos.roddos.com` | URL del backend |

---

## Deploy a Render (Build 0.5+)

ARGOS se despliega vía **Render Blueprint** (`render.yaml` en la raíz). Define dos servicios: `argos-backend` (Docker, plan Starter $7/mes) y `argos-frontend` (Static Site, gratis). CI corre en GitHub Actions (`.github/workflows/ci.yml`); los deploys los dispara la app de Render conectada al repo en cada push a `main`.

### Archivos de deploy

- [`render.yaml`](render.yaml) · IaC de Render (backend + frontend)
- [`Dockerfile`](Dockerfile) · imagen multi-stage del backend (python:3.11-slim, non-root, uvicorn)
- [`.dockerignore`](.dockerignore) · excluye tests/docs/secrets del build context
- [`.github/workflows/ci.yml`](.github/workflows/ci.yml) · lint + tests + build en cada PR
- [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml) · fallback opcional vía deploy hooks

### Pasos manuales del CEO (post-merge)

**1. Render · conectar el blueprint**

1. Ingresar a <https://dashboard.render.com> con la cuenta RODDOS
2. `New` → `Blueprint` → conectar el repo `RoddosColombia/ARGOS`
3. Render detecta `render.yaml` y aprovisiona `argos-backend` y `argos-frontend`
4. En el dashboard de `argos-backend`, setear en `Environment` los valores marcados `sync: false`:
   - `JWT_SECRET` → `python -c "import secrets; print(secrets.token_urlsafe(64))"`
   - `MONGODB_URI` → connection string de Atlas `argos-prod`
   - `ADMIN_EMAIL` → `ceo@roddos.com`
   - `ADMIN_PASSWORD_HASH` → `python -c "import bcrypt; print(bcrypt.hashpw(b'TU_PASSWORD', bcrypt.gensalt()).decode())"`
5. En `argos-frontend`, no hay secrets · `VITE_ARGOS_API_URL` ya está en el blueprint
6. Verificar primer deploy verde · curl `https://argos-backend.onrender.com/api/v1/health` debe devolver 200

**2. GoDaddy · DNS para argos.roddos.com**

En `DNS Management` del dominio `roddos.com`, crear dos registros CNAME:

| Tipo | Host | Apunta a | TTL |
|---|---|---|---|
| CNAME | `argos` | `argos-frontend.onrender.com` | 1h |
| CNAME | `api.argos` | `argos-backend.onrender.com` | 1h |

**3. Render · agregar custom domains**

En cada servicio: `Settings` → `Custom Domains`:

- `argos-frontend`: agregar `argos.roddos.com` · Render emite cert Let's Encrypt automático
- `argos-backend`: agregar `api.argos.roddos.com` · idem

**4. Validación end-to-end**

```bash
curl https://api.argos.roddos.com/api/v1/health          # 200 OK
curl https://api.argos.roddos.com/api/v1/health/deep     # 200 OK con mongodb.state=ok
open https://argos.roddos.com                             # login page
```

### Atajos útiles

- **Auto-deploy:** ya habilitado vía GitHub app de Render · cada push a `main` despliega ambos servicios
- **Deploy manual:** `Manual Deploy` → `Clear build cache & deploy` en el dashboard
- **Rollback:** `Events` → elegir deploy anterior → `Rollback`
- **Logs vivos:** `Logs` en cada servicio · también `render logs --service argos-backend --tail` con Render CLI

### Opcional · deploy hooks

Si preferís disparar deploys desde CI en vez de la app de Render, setea en `Settings → GitHub Secrets` del repo:
- `RENDER_DEPLOY_HOOK_BACKEND`
- `RENDER_DEPLOY_HOOK_FRONTEND`

El workflow `deploy.yml` los llama. Si no están definidos, el workflow es no-op.

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
