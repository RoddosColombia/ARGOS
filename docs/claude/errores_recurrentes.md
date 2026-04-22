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

## ER-001 · `.dockerignore` con `*.md` rompe docker build por excluir `README.md`

**Fase / Build donde ocurrió:** Phase 0 / Build 0.5
**Fecha:** 2026-04-22
**Tiempo perdido:** ~15 min

### Síntoma

Job `CI / Backend · docker build smoke test (pull_request)` falla en segundos mientras los otros 2 checks (lint+tests, frontend) pasan. El error en los logs del job es del tipo `COPY failed: file not found in build context: README.md` o similar, originado por la línea `COPY pyproject.toml README.md ./` del `Dockerfile`.

### Causa raíz

El `.dockerignore` tenía un patrón genérico `*.md` para excluir `CLAUDE.md`, `DECISIONES_V5.md` y otros markdowns del repo del build context. El patrón también excluye `README.md` por accidente. Pero:

1. El `Dockerfile` copia explícitamente `README.md` para que esté en el working directory del builder antes del `pip install .`.
2. `pyproject.toml` declara `readme = "README.md"` — setuptools lee el archivo durante la generación de metadatos. Si falta, el install falla.

Resultado: el `COPY` falla antes de llegar a `pip install`.

### Solución aplicada

Añadir una excepción explícita al patrón en `.dockerignore`:

```
*.md
!README.md
```

Comentario inline que explica por qué la excepción existe.

### Prevención futura

1. **Los patrones negativos (`!archivo`) en `.dockerignore` son la herramienta correcta** para permitir archivos específicos dentro de una exclusión amplia. Usarlos siempre que un `*.ext` cubra un archivo que el Dockerfile sí necesita.
2. **Revisión obligatoria del `.dockerignore` cuando se toca el Dockerfile.** Checklist mental: cada `COPY` del Dockerfile debe tener sus targets presentes en el build context tras aplicar el `.dockerignore`.
3. **Smoke test de docker build en CI** captura esto en el PR antes de merge — pero el gate solo funciona si la regla "CI verde antes de merge" se respeta (ver CLAUDE.md §5.4).

### Tags

#infra #docker #ci

---


