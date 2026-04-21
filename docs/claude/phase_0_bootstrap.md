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
- **Sin `.env.example` todavía.** El README lo menciona pero no existe. Se creará en Build 0.2 cuando entre el primer servicio FastAPI con variables reales (`MONGO_URI`, `JWT_SECRET`, etc.).
- **Sin `pyproject.toml` ni `package.json`.** Scaffold puro de carpetas · se crean en Build 0.2 y Build 0.4 respectivamente.

## Métricas de la fase
- Deploy verde: ⬜
- Autodeploy en push a main < 5 min: ⬜
- /api/v1/health responde 200: ⬜
- Login con workspace RODDOS funcional: ⬜
- System User + Service Account ARGOS creados con credenciales separadas: ⬜
- Baseline operativo capturado: ⬜

## Aprendizajes

- **Comparar tamaño en bytes no es una prueba de que un archivo cambió o no.** Cambios byte-neutros existen (reemplazo de líneas de largo similar). Verificar siempre con contenido específico o hash.
- **`git add` con paths explícitos > `git add -A` o `git add .`** para el commit inicial de un repo. Pasar la lista evita arrastrar accidentalmente archivos generados (`__pycache__`, `node_modules` antes de `.gitignore` maduro) o artefactos locales (`.claude/settings.local.json`, lockfiles de Word `~$*`).
- **Renombrar archivos con espacios o caracteres raros desde Windows Explorer es frágil.** CEO no pudo renombrar `DECISIONES_V5.md.txt` desde el explorador (Windows ocultaba la extensión). `mv` desde bash resolvió en 1 segundo.
- **Antes de correr `pandoc` en un entorno: verificar que esté instalado.** Saber los fallbacks (python-docx, unzip+XML) evita instalar dependencias y le da opciones al usuario. Tiempo ahorrado ~30 min.

## Cierre (Build 0.1 solamente · Phase 0 sigue abierta)
- Fecha cierre Build 0.1: 2026-04-21
- Cerrado por: Andrés San Juan (CEO) + Claude Code
- Commit: `23f7037` · `chore(infra): initial repo scaffold · phase_0/build_0.1`
- Pendiente: push a `origin/main` + branch protection en GitHub UI (CEO)
- Próximo build: **0.2** — FastAPI base + JWT auth + `/api/v1/health`
