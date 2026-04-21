# .planning/phase_0_prompt.md

# PROMPT DETALLADO PARA CLAUDE CODE — PHASE 0 ARGOS

Este es el primer prompt operativo del proyecto ARGOS para Claude Code.

---

## Contexto previo OBLIGATORIO de leer antes de empezar

Lee en este orden y en su totalidad:

1. `/CLAUDE.md` (raíz del repo) — todas las ROGs y reglas inamovibles
2. `/docs/canonicas/README.md` y luego todos los `.md` dentro de `/docs/canonicas/`
3. `/docs/knowledge/README.md` + `/docs/knowledge/stack.md` + `/docs/knowledge/partners.md`
4. `/docs/claude/README.md` + `/docs/claude/phase_0_bootstrap.md` + `/docs/claude/errores_recurrentes.md`
5. Visión 2.0 ejecutiva (documento de referencia maestro)

Si encuentras alguna ambigüedad entre esta especificación y los documentos anteriores, los documentos canónicos ganan. Detén el trabajo y pregunta al CEO.

---

## Objetivo de Phase 0

Dejar la infraestructura base de ARGOS operativa para que Phase 1 pueda comenzar el desarrollo funcional. Sin código de negocio en esta fase — solo plomería, estructura, setup de credenciales de partners, y solicitudes de extensión de permisos en Meta/Google si aplica.

**Criterio de cierre:** todos los items del checklist final marcados ✅.

---

## Builds incluidos en Phase 0

### Build 0.1 — Repo scaffold + estructura carpetas

**Tareas:**
- Crear repositorio `RoddosColombia/ARGOS` (privado) en GitHub
- Inicializar con la estructura de carpetas del CLAUDE.md sección 4
- Commitear los archivos `.md` del paquete Visión 2.0 que el CEO entregue
- Configurar `.gitignore` apropiado para Python + Node + IDE
- Configurar branch protection en `main`: requiere PR + CI verde + 1 approval
- README.md raíz con instrucciones de setup local

**Criterio de éxito:**
- `git clone` funciona
- Estructura de carpetas creada y poblada con los `.md` iniciales
- Branch protection activa en `main`

### Build 0.2 — FastAPI base + JWT auth + endpoint /api/v1/health

**Tareas:**
- Crear `src/` con scaffold FastAPI siguiendo convenciones de SISMO V2
- Configurar `pyproject.toml` con dependencias del stack pineadas (ver `/docs/knowledge/stack.md`)
- Endpoint `GET /api/v1/health` que responde `{"status": "ok", "version": "0.1.0"}`
- Endpoint `GET /api/v1/health/deep` que verifica conectividad con MongoDB
- Auth JWT con scope por rol (ceo, analista, sistema, cliente)
- Endpoint `POST /api/v1/auth/login` (email + password)
- Endpoint `GET /api/v1/auth/me` (datos del usuario autenticado)
- Middleware de validación de header `X-Workspace-Id` (ROG-A3)
- Estructura de logging JSON estructurado
- Tests unitarios mínimos: health, auth, middleware workspace

**Criterio de éxito:**
- `pytest` pasa todos los tests
- `/api/v1/health` responde 200 OK
- Login con credenciales del admin retorna JWT válido
- Llamada sin `X-Workspace-Id` retorna 400

### Build 0.3 — MongoDB connection + workspaces + users + argos_events colecciones

**Tareas:**
- Conectar a MongoDB Atlas M2 cluster `argos-prod` con Motor (async)
- Crear colecciones iniciales según `/docs/canonicas/colecciones_mongo.md`:
  - `workspaces`
  - `users`
  - `argos_events` (con índices completos)
  - `audit_log`
  - `system_health`
- Crear todos los índices listados en la canónica
- Seed inicial: workspace "RODDOS" + 1 user CEO con role `ceo`
- Helper `event_publisher` para emitir eventos al bus con schema validado
- Tests de integración con MongoDB

**Criterio de éxito:**
- Conexión a Atlas estable
- Colecciones creadas con índices
- Seed corre sin errores
- Emitir un evento de prueba se persiste con todos los campos requeridos del schema

### Build 0.4 — React 19 + TypeScript + Vite frontend interno base

**Tareas:**
- Scaffold React 19 + TypeScript + Vite + Tailwind 4
- Estructura de carpetas: `src/pages/`, `src/components/`, `src/hooks/`, `src/lib/`, `src/types/`
- Setup TanStack Query para estado de servidor
- Setup react-hook-form + zod para validación
- Página de login funcional contra `/api/v1/auth/login`
- Layout base con sidebar (vacío por ahora · placeholder para módulos futuros)
- Sistema de diseño básico con Tailwind tokens (colores, tipografía) — definir desde branding RODDOS
- Tests con Vitest + React Testing Library

**Criterio de éxito:**
- `npm run dev` levanta sin errores
- Login funcional con usuario seed de Build 0.3
- Build de producción `npm run build` sin warnings críticos

### Build 0.5 — GitHub Actions CI/CD + autodeploy Render

**Tareas:**
- Workflow `.github/workflows/ci.yml`:
  - Lint (ruff + eslint)
  - Tests backend (pytest)
  - Tests frontend (vitest)
  - Build frontend
  - Coverage report
- Workflow `.github/workflows/deploy.yml`:
  - Trigger en push a `main`
  - Notifica a Render (autodeploy ya configurado en Render dashboard)
- Setup Render service para backend (Starter $7/mes)
- Setup Render Static Site para frontend
- Variables de entorno en Render para todos los secrets (ver `/docs/knowledge/partners.md`)
- Configurar GitHub Secrets para CI

**Criterio de éxito:**
- Push a `main` despliega automáticamente
- CI bloquea merge si tests fallan
- Backend accesible vía URL de Render

### Build 0.6 — Dominio argos.roddos.com con SSL

**Tareas:**
- Configurar CNAME `argos.roddos.com` → URL de Render en GoDaddy
- Configurar custom domain en Render (backend + frontend)
- Verificar SSL Let's Encrypt automático activo
- Verificar HTTPS redirect funcional
- Verificar que `argos.roddos.com` carga el frontend
- Verificar que `argos.roddos.com/api/v1/health` responde

**Criterio de éxito:**
- `https://argos.roddos.com` carga login en < 2 segundos
- SSL válido (sin warnings de browser)
- HTTP redirige a HTTPS

### Build 0.7 — Langfuse self-hosted + observabilidad LLM

**Tareas:**
- Deploy Langfuse en Render (Docker)
- Configurar PostgreSQL para Langfuse (puede usar Render PostgreSQL gratis o vincular a MongoDB? — investigar setup recomendado)
- Configurar SDK Langfuse en backend
- Endpoint test que hace una llamada Anthropic dummy y se registra en Langfuse
- Dashboard Langfuse accesible (URL interna o subdomain)

**Criterio de éxito:**
- Llamada de prueba al SDK aparece en Langfuse con costo y latencia

### Build 0.8 — Setup credenciales terceros + partners nuevos (en paralelo a builds técnicos)

**Tareas (acción humana del CEO con apoyo Claude Code para preparar materiales):**
- Crear System User dedicado ARGOS dentro del Business Manager RODDOS existente · token separado del admin web (cumple ROG-A11 por aislamiento de credencial, no de cuenta · preserva histórico pixel + learning)
- Crear Service Account dedicado ARGOS dentro de la MCC Google Ads RODDOS existente · credenciales separadas del Service Account del admin web · preserva histórico y quality scores
- Crear cuenta TikHub.io · obtener API key
- Crear cuenta Apify · obtener API token
- Crear cuenta ProxyRack · obtener credenciales
- Crear cuenta SerpAPI · obtener API key
- Crear cuenta Anthropic dedicada
- Solicitar PoC gratis a RiskSeal
- Iniciar contrato con Wava (alta nueva)
- Replicar credenciales AUCO + Palenca para ARGOS (separadas del admin web · ROG-A11)

**Criterio de éxito:**
- System User y Service Account ARGOS creados con tokens/credenciales separados · guardados en Render env vars
- Cuentas terceras creadas con credenciales en Render env vars
- PoC RiskSeal agendada
- Wava onboarding iniciado
- Si se requiere extensión de permisos en BM o MCC, solicitud enviada a Meta/Google (pueden tomar 1-2 semanas · mucho más corto que review de cuenta nueva que toma 4-6)

### Build 0.9 — Captura de baseline operativo desde SISMO V2

**Tareas (humano + apoyo de Claude Code):**
- Capturar baseline de las 6 métricas (ver Visión 2.0 sección Objetivos) desde reportes SISMO:
  - Ingreso mensual de repuestos (promedio últimos 3 meses)
  - Días promedio en inventario por SKU (top 100)
  - Margen bruto promedio en repuestos
  - ROAS actual de pauta digital
  - Horas/semana CEO en investigación de mercado (auto-reporte)
  - Tasa de éxito de decisiones (% compras que rotan en 60 días)
- Persistir baseline en colección `system_health` o documento dedicado
- Vista web `/baseline` (read-only) que muestra el baseline congelado
- Documentar en `/docs/claude/phase_0_bootstrap.md`

**Criterio de éxito:**
- Baseline visible en `argos.roddos.com/baseline`
- Documentado en bitácora

---

## Trabajo paralelo a coordinar (NO bloquea Phase 0 pero debe iniciar)

- Trabajo sobre el repo SISMO V2 para exponer los 4 endpoints de lectura listados en `/docs/canonicas/integraciones_sismo.md`. Esto es responsabilidad del equipo SISMO, no de ARGOS, pero coordinar fechas para que esté listo antes de Phase 1.

---

## Reglas de operación durante Phase 0

1. **Cada commit que toque una integración actualiza la canónica correspondiente en el mismo PR.**
2. **Cada error >30 min de debug se registra en `/docs/claude/errores_recurrentes.md` el mismo día.**
3. **Cada build cerrado actualiza `/docs/claude/phase_0_bootstrap.md` con: decisiones tomadas, errores resueltos, deuda generada.**
4. **Conventional Commits con scope obligatorio.** Ej: `feat(infra): add MongoDB connection pool` con `Refs: phase_0/build_0.3`
5. **Tests obligatorios para auth, scoring (cuando llegue), wava (cuando llegue), media buyer (cuando llegue).**
6. **NO escribir código de negocio en Phase 0.** Solo plomería. Si se siente la tentación → registrar en deuda_tecnica y seguir.

---

## Checklist final de Phase 0

- [ ] Repo `RoddosColombia/ARGOS` creado con estructura de carpetas + branch protection
- [ ] CLAUDE.md raíz commiteado
- [ ] Carpetas `/docs/canonicas/`, `/docs/claude/`, `/docs/knowledge/`, `/.planning/` pobladas con archivos iniciales del paquete Visión 2.0
- [ ] Backend FastAPI + Auth JWT + endpoint `/api/v1/health` funcionando
- [ ] MongoDB Atlas M2 conectado · colecciones base + índices · seed inicial
- [ ] Frontend React + login funcional contra backend
- [ ] CI/CD GitHub Actions activo · push a main despliega
- [ ] Dominio `argos.roddos.com` con SSL Let's Encrypt activo
- [ ] Langfuse operativo
- [ ] System User ARGOS en BM existente RODDOS + Service Account ARGOS en MCC existente · credenciales separadas del admin web
- [ ] Cuentas Apify, ProxyRack, TikHub, SerpAPI, Anthropic activas con secrets en Render
- [ ] Wava onboarding iniciado · RiskSeal PoC agendada
- [ ] AUCO + Palenca credenciales replicadas en ARGOS (separadas del admin web)
- [ ] Baseline operativo capturado en `argos.roddos.com/baseline`
- [ ] Bitácora `/docs/claude/phase_0_bootstrap.md` cerrada con decisiones, errores resueltos y aprendizajes
- [ ] Tag `phase-0-closed` en el repo

---

## Cuando Phase 0 esté cerrada

1. CEO revisa y confirma cierre
2. Claude.ai entrega `.planning/phase_1_prompt.md` (Marketplace MELI + Trends + briefing v1 + SISMO read + impact tracking)
3. Bitácora `/docs/claude/phase_1_marketplace.md` se inicializa vacía
4. Phase 1 inicia
