# Deuda técnica · ARGOS

Registro vivo de decisiones conscientes de diferir trabajo. Cada entrada incluye owner, prioridad, y phase objetivo para resolver.

Formato:

```markdown
## DT-XXX · Título

**Creada:** YYYY-MM-DD (Phase X / Build Y)
**Prioridad:** baja / media / alta / crítica
**Owner:** @nombre
**Phase objetivo para resolver:** Phase Y+N
**Estado:** pendiente / en-progreso / resuelto

### Contexto
### Por qué se difirió
### Trade-off aceptado
### Señales para re-evaluar
### Tags
```

---

## DT-001 · Backend sin Dockerfile · deploy vía Render UI con pip+uvicorn

**Creada:** 2026-04-22 (Phase 0 / Build 0.5 v2)
**Prioridad:** baja
**Owner:** @CEO
**Phase objetivo para resolver:** Phase 5+ (cuando scale y GraphRAG justifiquen containerización)
**Estado:** pendiente

### Contexto

Build 0.5 v1 incluyó `Dockerfile` multi-stage (python:3.11-slim, builder+runtime) + `render.yaml` blueprint + `.dockerignore`. El PR #4 falló en CI porque `.dockerignore` excluía `README.md` (ver ER-001). Se decidió simplificar por paridad operativa con SISMO V2, que corre en Render con buildpack nativo (Python auto-detectado, sin Docker).

### Por qué se difirió

1. **Overhead sin beneficio inmediato.** Para Phase 0 el backend es FastAPI + Motor + bcrypt · Render ejecuta con su buildpack Python nativo en ~40s vs multi-stage Docker ~90s (primer build).
2. **Paridad con SISMO V2.** Mismo estilo de deploy reduce carga cognitiva al equipo y permite que scripts operativos (rollback, logs) funcionen idéntico en ambos proyectos.
3. **Blueprint IaC prematura.** `render.yaml` impone disciplina de IaC pero agrega otro archivo que mantener sincronizado con la realidad de Render UI. En Phase 0 con 2 servicios simples, el setup manual en UI lleva 10 min.
4. **Docker smoke test en CI fallando** reveló complejidad accidental (`.dockerignore` pattern quirks) que no paga en este momento.

### Trade-off aceptado

- Deploy config vive en la UI de Render, no en el repo · requiere documentación disciplinada en `README.md` para que el CEO reproduzca manualmente.
- Sin reproducibilidad IaC: si se pierde la config en Render, se reconfigura leyendo el README.
- Sin `Dockerfile`: no hay forma de correr el backend idéntico a prod en local (en dev se usa uvicorn directo).

### Señales para re-evaluar

- Añadir un 3er servicio (Langfuse, worker Celery, MongoDB reemplazado por clúster propio) → IaC empieza a pagar
- Scale horizontal donde la reproducibilidad inter-instancia importe
- Onboarding de un 2do dev que no quiera configurar Python 3.11 local
- Migración a un provider distinto de Render (AWS, Fly) donde Dockerfile es el lingua franca

### Tags

#infra #docker #deploy #render

---

## DT-002 · Sin GitHub Actions deploy workflow · Render GitHub app es single-point-of-trigger

**Creada:** 2026-04-22 (Phase 0 / Build 0.5 v2)
**Prioridad:** baja
**Owner:** @CEO
**Phase objetivo para resolver:** Phase 5+ si se necesita control de deploy más allá del auto-push

### Contexto

Build 0.5 v1 incluía `.github/workflows/deploy.yml` con fallback vía `RENDER_DEPLOY_HOOK_*` secrets. v2 lo elimina · deploy lo maneja 100% la GitHub app de Render que auto-deploya en cada push a `main`.

### Por qué se difirió

- La app de Render es suficiente para Phase 0 · auto-deploy es el comportamiento esperado del equipo
- Un workflow de deploy adicional sin secrets configurados es no-op · ruido en el repo
- Reintroducirlo cuando haya pipelines multi-etapa (preview → staging → prod con manual approval gate)

### Trade-off aceptado

- Un solo botón "Deploy" vive en Render, no en GitHub
- Si Render GitHub app se desconecta silenciosamente (rare), los deploys quedan en pausa hasta que alguien lo note

### Señales para re-evaluar

- Necesidad de preview environments por PR (staging effímero)
- Gate de deploy manual (dry-run en CI, humano aprueba, push a prod)
- Deploy coordinado cuando ARGOS + SISMO V2 + admin web tengan dependencias versionadas

### Tags

#ci #deploy #render

---

## DT-003 · Sin runtime pinning fino (patch de Python) más allá de runtime.txt

**Creada:** 2026-04-22 (Phase 0 / Build 0.5 v2)
**Prioridad:** baja
**Owner:** @CEO
**Phase objetivo para resolver:** Phase 5+ o antes si aparece CVE en runtime

### Contexto

`runtime.txt` pinea `python-3.11.11`. No hay mecanismo automático para detectar cuando Python 3.11.12+ esté disponible con security patches.

### Por qué se difirió

- Dependabot / Renovate no cubren runtime.txt nativamente
- Bump manual mensual es suficiente para Phase 0

### Trade-off aceptado

- Ventana de vulnerabilidad hasta bump manual
- Aceptable porque el backend no procesa input no-sanitizado de terceros en Phase 0

### Señales para re-evaluar

- CVE crítico en Python 3.11.11
- Phase 3+ (WhatsApp webhooks aceptan input de terceros)

### Tags

#infra #security #runtime
