# ARGOS Backend

FastAPI + Motor (MongoDB async) + JWT auth. Estado actual: **Build 0.2 · scaffold funcional con /health y /auth.**

## Estructura del paquete

```
src/backend/argos/
├── __init__.py           ← __version__
├── main.py               ← app factory + lifespan + wiring
├── config.py             ← Settings (pydantic-settings · lee .env)
├── logging_config.py     ← JSON structured logging
├── db/
│   └── mongo.py          ← Motor client lifecycle (usado por /health/deep)
├── auth/
│   ├── security.py       ← bcrypt + JWT encode/decode
│   ├── schemas.py        ← Pydantic: LoginRequest, TokenResponse, UserOut
│   ├── user_store.py     ← UserStore protocol + EnvUserStore impl
│   ├── deps.py           ← get_current_user, require_role
│   └── router.py         ← POST /auth/login, GET /auth/me
├── middleware/
│   ├── workspace.py      ← X-Workspace-Id check (ROG-A3)
│   └── request_logging.py
└── api/v1/
    └── health.py         ← GET /health, GET /health/deep
```

## Endpoints disponibles

| Método | Ruta | Auth | Workspace header | Descripción |
|---|---|---|---|---|
| GET | `/api/v1/health` | — | exento | Health básico · siempre 200 |
| GET | `/api/v1/health/deep` | — | exento | Verifica ping a MongoDB · 200 si OK, 503 si degraded |
| POST | `/api/v1/auth/login` | — | exento | Recibe `{email, password}` · devuelve JWT |
| GET | `/api/v1/auth/me` | Bearer JWT | requerido | Devuelve datos del usuario autenticado |

## Setup local

```bash
cd /  # raíz del repo
python -m venv .venv
source .venv/bin/activate              # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env                    # editar secrets
pytest                                  # corre tests backend
uvicorn argos.main:app --reload --app-dir src/backend --port 8000
```

## Notas de arquitectura

- **`EnvUserStore`** es bootstrap hasta Build 0.3 · ahí se reemplaza por `MongoUserStore` con la colección `users`.
- **`/health/deep`** ya cablea Motor client pero devuelve 503 si `MONGODB_URL` no está configurado · la colección `system_health` llega en Build 0.3.
- **Middleware de workspace (ROG-A3)** exime `/api/v1/health*`, `/api/v1/auth/login`, `/docs`, `/openapi.json`. Todo lo demás requiere `X-Workspace-Id`.
- **El header `X-Workspace-Id` debe coincidir con el claim `workspace_id` del JWT** — el mismatch retorna 403 en `auth/deps.py:get_current_user`.
- **Logs estructurados JSON** con `python-json-logger` · cada request loguea método, path, status, latencia y workspace_id.
