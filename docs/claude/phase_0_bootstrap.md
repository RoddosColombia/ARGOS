# Phase 0 — Bootstrap de infraestructura

## Objetivo declarado
Infraestructura base operativa + credenciales ARGOS creadas dentro de BM/MCC existentes de RODDOS + estructura de carpetas docs/canonicas + docs/claude + docs/knowledge creada y commiteada.

## Pre-requisitos
- 10 decisiones del CEO respondidas (ver Visión 2.0 sección 8)
- Cuentas creadas: Mercately access (vía SISMO ya existente), AUCO access (vía admin web ya existente), Wava (nueva), RiskSeal (nueva), Palenca (nueva), Anthropic, Apify, ProxyRack, TikHub, SerpAPI
- Dominio argos.roddos.com listo en GoDaddy
- MongoDB Atlas M2 cluster argos-prod creado
- Render workspace creado

## Builds incluidos en Phase 0
- Build 0.1 — Repo scaffold + estructura carpetas docs/ + CLAUDE.md raíz
- Build 0.2 — FastAPI base + JWT auth + endpoint /api/v1/health
- Build 0.3 — MongoDB connection + workspaces + users colecciones
- Build 0.4 — React 19 + Vite + estructura base frontend interno
- Build 0.5 — GitHub Actions CI/CD + autodeploy Render
- Build 0.6 — Dominio argos.roddos.com con SSL Let's Encrypt
- Build 0.7 — Langfuse self-hosted en Render para observabilidad LLM
- Build 0.8 — System User ARGOS en BM existente + Service Account ARGOS en MCC existente (credenciales separadas · preserva histórico · cumple ROG-A11 por aislamiento de credencial no de cuenta)
- Build 0.9 — Captura de baseline operativo desde SISMO V2

## Decisiones arquitectónicas tomadas

### Build 0.4 · React 19 + Vite + dashboard shell autenticado (2026-04-22)

- **Stack frontend elegido:** React 19.1 + Vite 6 + TypeScript 5.7 strict + Tailwind 4.1 (via `@tailwindcss/vite`, sin archivo `tailwind.config.js`) + react-router-dom 7 + TanStack Query 5 + react-hook-form 7 + zod 3 + Vitest 3. Notable: stack.md listaba Vite 5.x; elegí Vite 6 (estable, mantiene API del 5) para no arrastrar un bump forzado en Build 0.5. Tailwind 4 sin config es el default moderno — tokens de diseño viven en `@theme` dentro de `src/index.css`.
- **Sin shadcn/ui.** Lo dejé fuera para no introducir un generador de componentes en el scaffold inicial. Los componentes del Layout+Sidebar+LoginPage son HTML+Tailwind plano (~80 LOC combinados). Cuando haya formularios complejos (KYC en Build 3) evaluar shadcn o Ark UI. Deuda documental pequeña: alinear con `stack.md` que menciona shadcn.
- **Routing con `createBrowserRouter` (react-router v7 library mode).** 3 rutas: `/login` público, `/` protegido con Layout+Dashboard, `*` 404 también protegido. `ProtectedRoute` verifica `isSessionValid()` antes de renderizar · mismatch → `<Navigate to="/login" replace>`.
- **Sesión en localStorage.** Campos: `access_token`, `workspace_id`, `role`, `expires_at` (unix ms). Trade-off XSS documentado en `README.md` y en `lib/auth.ts`. Migración a httpOnly cookies cuando el backend emita refresh tokens (build futuro).
- **`api.ts` inyecta headers automáticamente.** Toda llamada a endpoints ARGOS incluye `Authorization: Bearer <jwt>` y `X-Workspace-Id: <ws>` (ROG-A3 desde el cliente). Opt-outs `skipAuth` / `skipWorkspace` explícitos para `/auth/login`. En 401 espontáneo: limpia la sesión silenciosamente · ProtectedRoute maneja la redirección en el siguiente render.
- **`useCurrentUser` con TanStack Query** habilitada sólo si la sesión es válida (`enabled: isSessionValid(readSession())`). Evita la llamada fantasma a `/auth/me` durante mount del Dashboard antes de que se redirija.
- **Sidebar con 6 módulos placeholder** etiquetados por phase (Briefing P1, Scoring P2, WhatsApp P3, Cobranza P4, Mantenimiento P5, Media Buyer P8). Dan dimensión visual del roadmap sin falsa promesa de funcionalidad — todos están `cursor-not-allowed` con tooltip "Disponible en Phase X".
- **Dashboard muestra estado vivo de Phase 0** (checkboxes ✅/⬜ por build) + grid de 6 próximos módulos con descripción corta. Reemplazable con widgets reales cuando lleguen.
- **Proxy Vite `/api` → `http://localhost:8000`** por default. Permite `npm run dev` sin CORS. En prod (Build 0.6 con argos.roddos.com) ambos servicios comparten origen y el proxy no aplica.
- **Tailwind tokens custom: `brand` (emerald), `ink` (slate).** Paletas reducidas (3-5 shades cada una) — suficientes para Phase 0 · se extenderán con design system consolidado cuando haya UI designer en loop.
- **TypeScript strict + `noUnusedLocals` + `noUnusedParameters`.** `npm run lint` = `tsc -b --noEmit`. Build (`tsc -b && vite build`) falla si hay cualquier error de tipos.
- **Tests con MemoryRouter y QueryClient aislado** para no depender del browser ni del servidor real. Mocks de `global.fetch` para verificar el contrato del cliente API sin necesidad de levantar el backend.

### Build 0.3 · MongoDB Atlas + colecciones + MongoUserStore + seed (2026-04-21)

- **Atlas M2 `argos-prod` conectado** desde dev vía `mongodb+srv://` · Mongo 8.0.21. DB `argos` (prod) vs `argos_test` (tests de integración · se limpia antes/después).
- **Rename `MONGODB_URL` → `MONGODB_URI`** por coherencia con la convención que el CEO usa al entregar connection strings. Impact: settings + config + conftest + tests actualizados. Mantener URI en todo lo siguiente.
- **Fail-fast en startup si Atlas no responde.** `connect_mongo(verify=True)` hace `ping` antes de dejar el cliente montado · si falla, cierra y re-lanza. Alternativa descartada: degradación silenciosa a `EnvUserStore`. Razón: ROG-A5 obliga a reportar estado verdadero · mejor no arrancar que arrancar en estado inconsistente.
- **Módulos de DB separados por responsabilidad:** `collections.py` (constantes de nombre) · `indexes.py` (`ensure_indexes`) · `seed.py` (`seed_initial_data`) · `events.py` (`publish_event`). Todos async · todos idempotentes · ninguno asume que la DB esté poblada.
- **Seed: `$setOnInsert` para `password_hash`, no `$set`.** Decisión explícita: si alguien rota `ADMIN_PASSWORD_HASH` en `.env` y restartea, el seed NO sobreescribe el hash en Mongo. Evita rotaciones silenciosas. Test `test_seed_does_not_rotate_password` lo verifica. Para rotar password intencional: `db.users.updateOne(...)` manual o CLI futuro.
- **Event publisher con ULID** (`python-ulid`) en vez de UUID. Razón: canónica `eventos.md` especifica `event_id: "evt_2026_xxxxxxxxx"` con formato ULID (lexicográficamente ordenable por timestamp, útil para queries `(workspace, timestamp)`). Prefijo `evt_` conservado.
- **`publish_event` valida schema mínimo** antes de insertar: `event_type` dot.notation, `workspace_id` no-vacío (ROG-A3), `producer` no-vacío, `payload` dict. `EventValidationError` se lanza antes de tocar DB. Schema completo del documento se construye internamente.
- **MongoUserStore query por email (no por `(workspace_id, email)`)** en Build 0.3. Razón: único workspace por ahora (RODDOS) · login no recibe workspace_id en request body. Cuando haya multi-tenant users, la firma de login cambia y este store se adapta. Índice `(workspace_id, email) unique` ya está creado para prevenir duplicados entre tenants.
- **`roles: [str]` en Mongo vs `role: str` en JWT.** MongoUserStore toma `roles[0]` como rol activo. Documentado en la canónica `colecciones_mongo.md` con la nota sobre escalamiento al CEO cuando se necesite RBAC multi-rol.
- **Canónica actualizada: Argon2 → bcrypt.** Conflicto descubierto entre `colecciones_mongo.md:31` (Argon2) y código de Build 0.2 (bcrypt). Escalé al CEO, decisión: opción B (alinear canónica a código). Ver nota ampliada en canónica con justificación del threat model.
- **TestClient con `with ...`** (context manager) en vez de `TestClient(app)` directo · así `lifespan` ejecuta startup+shutdown. Sin esto, Mongo no se conectaría durante tests y `MongoUserStore` nunca quedaría activo. Regresión en `conftest.py`.
- **Tests de integración usan DB `argos_test` (distinta de `argos`).** Limpian antes y después · son ~9 segundos end-to-end contra Atlas real (M2). CI corrido localmente pasa 27/27. En Build 0.5 (GitHub Actions) se evaluará si los integration tests corren en CI con secrets, o si se marcan opt-in para PRs que tocan DB.
- **`python-dotenv` añadido para que el test loader pueda leer `.env` e ignorar el `MONGODB_URI=""` que conftest fuerza.** Sin esto, los integration tests se saltan siempre porque conftest blanquea la URI antes de que pytest lea nada. La función `_real_mongo_uri()` lee `.env` directamente.

### Build 0.2 · FastAPI + JWT + /api/v1/health (2026-04-21)

- **Layout del backend:** `pyproject.toml` en raíz del repo (no en `src/backend/`) para facilitar CI y monorepo · paquete Python en `src/backend/argos/` con `src-layout` · tests en `tests/backend/`. Trade-off: un comando `pytest` desde raíz corre todo sin `cd`.
- **Hashing de passwords: `bcrypt` directo, sin `passlib`.** Razón: passlib 1.7.4 tiene incompatibilidad conocida con bcrypt 4.x (requiere pinear `bcrypt==4.0.1`) · llamar bcrypt directo son 6 líneas y elimina la dependencia frágil. Verificable en `argos/auth/security.py`.
- **JWT library: `pyjwt[crypto]`, no `python-jose`.** Razón: pyjwt tiene mantenimiento más activo y API más simple. HS256 con secret de env var.
- **`EnvUserStore` como puente a Build 0.3.** El paquete define el protocolo `UserStore` y una implementación basada en env vars (`ADMIN_EMAIL`, `ADMIN_PASSWORD_HASH`) · Build 0.3 añade `MongoUserStore` que se enchufa vía `set_user_store()` sin tocar el router de auth. Permite que Build 0.2 tenga login funcional sin depender de la colección `users`.
- **`WorkspaceIdMiddleware` enforza ROG-A3 a nivel de capa.** Endpoints exentos (públicos): `/api/v1/health*`, `/api/v1/auth/login`, `/docs`, `/redoc`, `/openapi.json`. Todos los demás endpoints requieren `X-Workspace-Id` → 400 explícito con código `workspace_header_missing`.
- **Validación cruzada workspace ↔ JWT.** `auth.deps.get_current_user` compara `X-Workspace-Id` del header con `workspace_id` del JWT · mismatch → 403. Bloquea intentos de usar token legítimo contra otro tenant.
- **`/api/v1/health/deep` ya cablea Motor async pero permite `MONGODB_URL` vacío.** Cuando está vacío devuelve 503 con `{"mongodb": {"state": "not_configured"}}`. Previene que Build 0.2 dependa del cluster Atlas que todavía no existe.
- **Logging estructurado JSON con `python-json-logger`.** Import compatible con v2.x y v3.x (el módulo se renombró de `pythonjsonlogger.jsonlogger` a `pythonjsonlogger.json` en v3).
- **Branch feature: `phase-0/build-0.2-fastapi-auth` (con slash).** Nota: `stack.md` propone la convención `feature/<phase-X-build-Y-desc>`; el CEO prefirió `phase-X/build-Y-desc` para este build. Ajustar `stack.md` en un PR futuro o formalizar la nueva convención en CLAUDE.md §5 — deuda documental pequeña.
- **Scope de auth:** JWT access token (60 min TTL · config env var). No hay refresh token en Build 0.2 — se añade si/cuando sea necesario en un build posterior. KISS.

### Build 0.1 · Repo scaffold (2026-04-21)

- **Branch default `main`** (no `master`). Razón: alineación con convención estándar GitHub post-2020 y con SISMO V2.
- **`.gitkeep` en `src/` y `tests/`** en lugar de scaffolds vacíos de FastAPI/Vite. Razón: Build 0.1 es solo plomería · el código funcional llega en Build 0.2 (backend) y Build 0.4 (frontend). No anticipar estructura de módulos sin requisito inmediato.
- **`docs/VISION_2_0.md` generado desde el .docx con python-docx** (no pandoc). Razón: pandoc no estaba instalado en el entorno y el docx es ZIP+XML · python-docx lee la estructura sin dependencias externas. Script preserva orden de párrafos y tablas mediante iteración sobre `body.iterchildren()`. Trade-off aceptado: formato no tan pulido como pandoc (no maneja estilos inline finos) · suficiente para documento de referencia commiteable.
- **README.md raíz reescrito en tono dev** (setup local + convenciones + estructura). La versión anterior eran instrucciones de empaque/onboarding del paquete · ya cumplida su función, inapropiada para un repo activo.
- **`.claude/settings.local.json` en `.gitignore`** (no el directorio `.claude/` completo). Razón: permite que configuración compartida de equipo entre en el repo si se crea en el futuro, pero mantiene settings locales por-máquina fuera.
- **Branch protection diferida a GitHub UI post-push.** Razón: CEO la configura manualmente · evita instalar `gh` CLI en el entorno local.

## Cambios en canónicas

### Build 0.3
- **`docs/canonicas/colecciones_mongo.md` · colección `users`:**
  - `password_hash`: **Argon2 → bcrypt (cost 12)** · añadida nota con justificación del threat model
  - `roles`: tipo `array` → `array of string` · añadida nota aclaratoria sobre `roles[0]` → JWT `role` y el escalamiento al CEO para RBAC múltiple

### Build 0.1
- Ninguno. El scaffold no toca integraciones. Las canónicas `apis_externas.md`, `eventos.md`, `colecciones_mongo.md`, `integraciones_sismo.md` se entregaron pre-pobladas desde el paquete Visión 2.0 y se commitean tal cual.

## Errores cometidos y cómo se resolvieron

| Error | Causa raíz | Solución | Prevención futura |
| --- | --- | --- | --- |
| Falsa alarma: sospecha de que el reemplazo de `CLAUDE.md` no se había guardado porque el tamaño en bytes no cambió (11.869 → 11.869) | Los cambios del CEO en CLAUDE.md fueron byte-neutros (reemplazo de líneas por otras de largo similar en líneas 32 y 75). El mtime "Apr 21 2026" en vez de hora exacta reforzó la sospecha sin ser evidencia real | Verificación con `Select-String` en PowerShell confirmó las correcciones · se procedió con el commit | Antes de sospechar que un archivo no se guardó: comparar hash (`git hash-object`) o contenido específico (grep de las líneas esperadas), no solo tamaño en bytes |
| Archivos `DECISIONES_V5.md.txt` y `ARGOS_VISION_2.0_1.docx` con nombres incorrectos al arrancar | Export desde Word/editor añadió `.txt` y sufijo `_1` automáticos que nadie limpió antes de apuntar el workspace a la carpeta | CEO renombró el .docx manualmente; Claude Code renombró el .md vía `mv` | Checklist de onboarding del repo: `ls` inicial para verificar nombres canónicos antes del primer commit |

## Deuda técnica generada

- **`docs/VISION_2_0.md` conversión cruda.** El markdown generado por python-docx preserva orden y tablas pero no reformatea bullets (se serializan como párrafos sueltos sin `-`). Legibilidad funcional · no bloquea. Prioridad baja · resolver cuando se edite el documento maestro por primera vez en un PR.
- ~~Sin `.env.example` todavía~~ → **resuelto en Build 0.2** (archivo creado en raíz con todas las vars del backend).
- ~~Sin `pyproject.toml` ni `package.json`~~ → **`pyproject.toml` resuelto en Build 0.2** · `package.json` pendiente para Build 0.4.
- **Sin suite de tests de middleware con app real de uvicorn.** Los tests usan `TestClient` (sincrono · wraps ASGI). Suficiente para 0.2, pero tests E2E reales con server corriendo llegan cuando Build 0.5 agrega CI.
- **Convención de ramas divergente entre CLAUDE.md/stack.md y uso real.** `stack.md` dice `feature/<phase-X-build-Y-desc>` · el uso real es `phase-X/build-Y-desc` (slash como separador, preferido por CEO). Resolver en PR documental que consolide la convención real.

## Métricas de la fase
- Deploy verde: ⬜ (Build 0.5)
- Autodeploy en push a main < 5 min: ⬜ (Build 0.5)
- `/api/v1/health` responde 200: ✅ (Build 0.2 · verificado vía TestClient)
- `/api/v1/health/deep` con ping real a Atlas: ✅ (Build 0.3 · 200 OK con Mongo 8.0.21)
- Login con workspace RODDOS funcional: ✅ (Build 0.3 · `MongoUserStore` activo · seed creó user CEO)
- Colecciones + índices: ✅ (Build 0.3 · 5 colecciones, 15 índices, idempotente)
- System User + Service Account ARGOS creados con credenciales separadas: ⬜ (Build 0.8)
- Baseline operativo capturado: ⬜ (Build 0.9)
- **Tests totales:** 27 backend + 12 frontend = 39/39 passing
- **Lint:** ruff check limpio (backend) · tsc -b sin errores (frontend)
- **Frontend build:** 165 modules, 419 KB JS (129 KB gzip), sin warnings

## Aprendizajes

- **Comparar tamaño en bytes no es una prueba de que un archivo cambió o no.** Cambios byte-neutros existen (reemplazo de líneas de largo similar). Verificar siempre con contenido específico o hash.
- **`git add` con paths explícitos > `git add -A` o `git add .`** para el commit inicial de un repo. Pasar la lista evita arrastrar accidentalmente archivos generados (`__pycache__`, `node_modules` antes de `.gitignore` maduro) o artefactos locales (`.claude/settings.local.json`, lockfiles de Word `~$*`).
- **Renombrar archivos con espacios o caracteres raros desde Windows Explorer es frágil.** CEO no pudo renombrar `DECISIONES_V5.md.txt` desde el explorador (Windows ocultaba la extensión). `mv` desde bash resolvió en 1 segundo.
- **Antes de correr `pandoc` en un entorno: verificar que esté instalado.** Saber los fallbacks (python-docx, unzip+XML) evita instalar dependencias y le da opciones al usuario. Tiempo ahorrado ~30 min.

## Cierre parcial · Phase 0 sigue abierta

### Build 0.4 · 2026-04-22
- Cerrado por: Andrés San Juan (CEO · approval pendiente) + Claude Code
- Rama: `phase-0/build-0.4-frontend` → PR a `main`
- Tests: 12/12 frontend (3 archivos · Vitest 3 + Testing Library)
- Build: `tsc -b && vite build` · 165 modules, 419 KB JS, sin warnings
- Entregado: scaffold React 19 + login funcional + dashboard shell autenticado con sidebar placeholder de 6 módulos · `api.ts` con headers automáticos (ROG-A3) · sesión en localStorage · proxy Vite al backend local
- Próximo build: **0.5** — GitHub Actions CI/CD + autodeploy Render

### Build 0.3 · 2026-04-21 (mergeado con squash)
- PR #2 aprobado · commit en main: `79474e7 feat(db): MongoDB Atlas + colecciones + MongoUserStore + seed RODDOS (phase_0/build_0.3) (#2)`
- Entregado: Motor conectado a Atlas M2 · 5 colecciones · 15 índices · seed idempotente RODDOS+CEO · `MongoUserStore` · `publish_event` con ULIDs · canónica `colecciones_mongo.md` actualizada (Argon2→bcrypt)

### Build 0.2 · 2026-04-21 (mergeado con squash)
- PR #1 aprobado · commit en main: `dfaf852 feat: FastAPI + JWT auth + health endpoints (phase_0/build_0.2) (#1)`
- Endpoints entregados: `GET /api/v1/health`, `GET /api/v1/health/deep`, `POST /api/v1/auth/login`, `GET /api/v1/auth/me`

### Build 0.1 · 2026-04-21
- Cerrado por: Andrés San Juan (CEO) + Claude Code
- Commit: `23f7037` · `chore(infra): initial repo scaffold · phase_0/build_0.1`
- Bitácora: `d4ba259` · `docs(phase_0): bitácora Build 0.1 cerrado`
