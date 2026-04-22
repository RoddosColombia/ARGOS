# docs/claude/errores_recurrentes.md

Catálogo de errores ya cometidos en ARGOS y sus prevenciones.

**Lectura obligatoria antes de cualquier nuevo build.** Si te toma 30+ minutos resolver un bug, registralo aquí.

## Formato

```markdown
## ER-XXX · Título corto del error

**Fase / Build donde ocurrió:** Phase X / Build Y
**Fecha:** YYYY-MM-DD
**Tiempo perdido:** N horas

### Síntoma
(qué se observaba)

### Causa raíz
(análisis técnico de por qué pasó)

### Solución aplicada
(cómo se resolvió)

### Prevención futura
(qué cambio en el código, en la canónica o en el proceso evita que vuelva a pasar)

### Tags
#scoring #whatsapp #sismo #wava #etc
```

---

## Errores heredados de SISMO V2 que NO se deben repetir en ARGOS

(a poblar con los errores conocidos del proyecto SISMO que aplican aquí)

## ER-001 · `.dockerignore` con `*.md` rompe `docker build` por excluir `README.md`

**Fase / Build donde ocurrió:** Phase 0 / Build 0.5 v1 (PR #4 cerrado sin mergear)
**Fecha:** 2026-04-22
**Tiempo perdido:** ~20 min (diagnóstico + fix) antes del cambio de estrategia a v2

### Síntoma

Job `CI / Backend · docker build smoke test (pull_request)` falla en ~16s mientras los otros 2 checks pasan. Log típico del error: `COPY failed: file not found in build context: README.md` en la línea `COPY pyproject.toml README.md ./` del Dockerfile.

### Causa raíz

El `.dockerignore` incluía un patrón genérico `*.md` para excluir `CLAUDE.md`, `DECISIONES_V5.md`, `docs/VISION_2_0.md` del build context. Ese patrón también excluye `README.md`. Pero:

1. El `Dockerfile` hace `COPY pyproject.toml README.md ./` antes del `pip install .`
2. `pyproject.toml` declara `readme = "README.md"` · setuptools lee el archivo durante generación de metadatos · sin él, el install falla

### Solución aplicada

En Build 0.5 v2 se eliminó el Dockerfile y `.dockerignore` por un cambio de estrategia (paridad con SISMO V2 · ver DT-001). De haberse mantenido el Dockerfile, la solución era añadir excepción `!README.md` tras `*.md` en `.dockerignore`.

### Prevención futura

1. **Revisar el `.dockerignore` cuando se toca el `Dockerfile`.** Checklist: cada `COPY` del Dockerfile debe tener sus targets presentes en el build context tras aplicar `.dockerignore`.
2. **Los patrones negativos (`!archivo`) son la herramienta correcta** para excluir todo con `*.ext` pero permitir archivos específicos.
3. **CI verde antes de merge** (CLAUDE.md §5.4) · smoke tests de build atrapan esto antes de prod · fix rule ayuda pero no sustituye al habit de reproducir el Dockerfile localmente.

### Tags

#infra #docker #ci

---


