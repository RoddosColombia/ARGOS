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
- Ninguno en Build 0.1. El scaffold no toca integraciones. Las canónicas `apis_externas.md`, `eventos.md`, `colecciones_mongo.md`, `integraciones_sismo.md` se entregaron pre-pobladas desde el paquete Visión 2.0 y se commitean tal cual.

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
- `/api/v1/health` responde 200: ✅ (Build 0.2 · verificado vía TestClient + 14/14 pytest)
- Login con workspace RODDOS funcional: ✅ (Build 0.2 · `EnvUserStore` · swap a Mongo en 0.3)
- System User + Service Account ARGOS creados con credenciales separadas: ⬜ (Build 0.8)
- Baseline operativo capturado: ⬜ (Build 0.9)

## Aprendizajes

- **Comparar tamaño en bytes no es una prueba de que un archivo cambió o no.** Cambios byte-neutros existen (reemplazo de líneas de largo similar). Verificar siempre con contenido específico o hash.
- **`git add` con paths explícitos > `git add -A` o `git add .`** para el commit inicial de un repo. Pasar la lista evita arrastrar accidentalmente archivos generados (`__pycache__`, `node_modules` antes de `.gitignore` maduro) o artefactos locales (`.claude/settings.local.json`, lockfiles de Word `~$*`).
- **Renombrar archivos con espacios o caracteres raros desde Windows Explorer es frágil.** CEO no pudo renombrar `DECISIONES_V5.md.txt` desde el explorador (Windows ocultaba la extensión). `mv` desde bash resolvió en 1 segundo.
- **Antes de correr `pandoc` en un entorno: verificar que esté instalado.** Saber los fallbacks (python-docx, unzip+XML) evita instalar dependencias y le da opciones al usuario. Tiempo ahorrado ~30 min.

## Cierre parcial · Phase 0 sigue abierta

### Build 0.2 · 2026-04-21
- Cerrado por: Andrés San Juan (CEO · approval pendiente) + Claude Code
- Rama: `phase-0/build-0.2-fastapi-auth` → PR a `main`
- Tests: 14/14 pasaron (`pytest tests/backend`)
- Lint: `ruff check` limpio
- Endpoints entregados: `GET /api/v1/health`, `GET /api/v1/health/deep`, `POST /api/v1/auth/login`, `GET /api/v1/auth/me`
- Próximo build: **0.3** — MongoDB connection + workspaces + users + argos_events + índices + seed

### Build 0.1 · 2026-04-21
- Cerrado por: Andrés San Juan (CEO) + Claude Code
- Commit: `23f7037` · `chore(infra): initial repo scaffold · phase_0/build_0.1`
- Bitácora: `d4ba259` · `docs(phase_0): bitácora Build 0.1 cerrado`
