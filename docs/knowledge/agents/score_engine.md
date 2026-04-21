# docs/knowledge/agents/score_engine.md

# Score Engine

Motor de calificación crediticia interno de ARGOS. Clon independiente del motor que vive en el admin de www.roddos.com (Build 20).

## Identidad

- Nivel: N3 (decisión)
- Modelo LLM (Capa 2 razonamiento): Claude Sonnet 4.6 con prompt caching
- Stack: Python 3.11 + scikit-learn XGBoost 2.x + joblib
- Persistencia: MongoDB collection `scoring_solicitudes`
- Eventos producidos: ver docs/canonicas/eventos.md sección Score Engine

## Principio inamovible (ROG-S1)

Score Engine es CLON del motor del admin web. Misma lógica, mismos pesos, mismos partners, instancia separada. Cero llamadas cruzadas en runtime entre los dos motores.

Razones del clon vs integración compartida:
1. Independencia operativa (si admin cae, ARGOS sigue vendiendo · y viceversa)
2. Preparación para giro volumétrico (a futuro WhatsApp captura 70-80% del volumen, motor de ARGOS pasará a ser el primario)
3. Aislamiento de blast radius

Lo que SÍ se comparte (ROG-S2):
- Loanbook de SISMO V2 read-only (entrenamiento del XGBoost de ambos motores con la misma cartera)

## Arquitectura del modelo (réplica fiel del Build 20)

### Capa 1 — Modelo estadístico

Algoritmo:
- XGBoost (default · mejor rendimiento en datos tabulares desbalanceados de crédito)
- Fallback a Regresión Logística si dataset < 500 registros
- Fallback a Scorecard manual ponderado si dataset < 100 registros (fase inicial)

Variable objetivo: `default_90d` (1 = mora >90 días o recuperación, 0 = pagó correctamente)

Features de entrenamiento (desde loanbook de SISMO):
- score_externo_originacion (RiskSeal o Palenca según corresponda)
- capacidad_pago_originacion ((ingresos - gastos) / cuota_semanal)
- estabilidad_laboral_originacion (tiempo_actividad_meses)
- score_comportamental (si ya era cliente RODDOS al originar)
- validacion_biometrica_originacion (AUCO score)
- producto (rdx_leasing / rodante)
- tipo_empleo, uso_moto, zona, ciudad
- dpd_maximo_historico, ptp_cumplido_ratio, no_contesto_ratio (si re-evaluación)

Output: probabilidad_default (0.0 → 1.0)

Re-entrenamiento: weekly desde snapshot de loanbook (lunes 04:00 hora Bogotá)

### Capa 2 — Claude Sonnet 4.6 (razonamiento)

Función:
- Analiza variables cualitativas que el modelo estadístico no captura
- Coherencia del KYC (¿la dirección que reportó coincide con la del documento?)
- Señales de fraude en documentos (extractos editados, desprendibles dudosos)
- Análisis de coherencia entre datos auto-declarados y datos de partners (Palenca vs declared income)
- Genera ajuste cualitativo: ±0.15 sobre probabilidad de default
- Genera narrativa de decisión auditable (ROG-S4)

Input al LLM:
- Resumen estructurado del KYC
- Resultados de partners (AUCO, RiskSeal, Palenca según aplique)
- score_modelo de Capa 1
- Documentos analizados (vía process_document_chat)
- Histórico del cliente si aplica

Output esperado:
```json
{
  "ajuste": -0.05,
  "narrativa": "Cliente reporta empleo en Rappi hace 18 meses. Palenca confirma 14 meses activos con ingresos consistentes pero menores al rango declarado (declaró 2-4 SMMLV, Palenca muestra promedio en rango 1-2 SMMLV). RiskSeal no detecta señales de fraude. AUCO biometría 89/100 OK. Capacidad de pago real más ajustada que la declarada, pero suficiente para Crédito Rodante. Aprobación con reducción del 20% sobre monto solicitado.",
  "señales_fraude": false,
  "coherencia_score": 0.78
}
```

Modelo pineado: `claude-sonnet-4-6-20260301` (nombre ejemplo · pinear el real)
Caching: system prompt cacheado (ahorra 90% en input)

### Score final

```python
score_combinado = (0.7 × score_modelo) + (0.3 × score_claude_ajustado)
score_final = int((1 - score_combinado) × 1000)  # invertir: alta probabilidad de default = score bajo
```

Escala 0-1000 con categorías:
- muy_bajo (800-1000) → aprobado automático
- bajo (650-799) → aprobado automático
- medio (450-649) → revisión manual
- alto (250-449) → rechazado
- muy_alto (0-249) → rechazado automático

## Reglas duras (ROG-S3)

Ejecutadas ANTES del cálculo del score. Si alguna se cumple, rechazo inmediato sin llamar a Claude:

| Regla | Umbral | Aplicación |
|-------|--------|------------|
| AUCO score biométrico | < 70 | Bloqueo + mensaje "documento no válido" |
| RiskSeal fraud_flag | == true | Bloqueo + alerta interna |
| Score Datacrédito | < 400 | Solo si NO es delivery/mototaxi (no aplica a ese segmento) |
| Mora activa en centrales | > $3M COP | Rechazo |
| DTI declarado | > 60% | Rechazo (no alcanza capacidad de pago) |
| Documento o desprendible adulterado | detectado por Claude | Rechazo + flag al analista |

## Reglas de producto

### Crédito RDX Leasing (moto)

| Parámetro | Valor |
|-----------|-------|
| Umbral aprobación | 650 |
| Umbral cliente RODDOS A+ | 600 |
| DTI máximo | 40% (cuota semanal / ingreso semanal) |
| Monto máximo | PVP moto - cuota inicial |
| Plazos disponibles | 9 / 12 / 18 meses (39 / 52 / 78 cuotas semanales) |

### Crédito Rodante (repuestos)

| Parámetro | Valor |
|-----------|-------|
| Umbral aprobación | 500 |
| Umbral cliente RODDOS con historial positivo | 400 |
| Ticket máximo primera solicitud | $500.000 COP |
| Bypass para clientes A+ / A / B | Sí (aplicar express en flujo F3) |
| Antifraude primario | RiskSeal (ROG-S1 — peso mayor que en RDX Leasing) |

## Pesos del Scorecard manual (cuando dataset < 100 registros)

```
score_externo:           30%   # RiskSeal o Palenca según el segmento
capacidad_pago:          25%   # (ingresos - gastos) / cuota semanal
estabilidad_laboral:     20%   # tiempo_actividad_meses
score_comportamental:    15%   # cliente RODDOS A+→E (0% si nuevo)
validacion_biometrica:   10%   # AUCO score
```

Para Crédito Rodante en cliente nuevo no-RODDOS, el peso de RiskSeal sube:
```
score_externo (RiskSeal): 35%
capacidad_pago:           25%
estabilidad_laboral:      20%
validacion_biometrica:    20%
score_comportamental:     0%
```

## Tools permitidos

- partners.auco.validate_biometric()
- partners.riskseal.get_digital_score()
- partners.palenca.get_income() (solo si delivery/mototaxi)
- partners.process_document_chat() (OCR + análisis Claude de adjuntos)
- sismo.read.loanbook_snapshot()
- sismo.read.customer_profile()
- mongodb.write.scoring_solicitudes
- mongodb.write.argos_events
- llm.claude_sonnet_4_6() con caching
- xgboost.predict()

## Tools prohibidos

- Cualquier endpoint de WhatsApp (notificación es responsabilidad del WhatsApp Agent · separación)
- Cualquier endpoint de Wava (cobro es responsabilidad del Cobranza Orchestrator)
- Cualquier endpoint de Media Buyer
- Cualquier integración de marketing/scraping
- Escritura directa al loanbook de SISMO (se usa el endpoint POST /api/argos/score-result que SISMO consume)

## Latencia objetivo

Tiempo total < 300 segundos (5 minutos) desde `score.solicitud.created` hasta `score.evaluated`.

Desglose objetivo:
- AUCO biometría: < 30 seg
- RiskSeal: < 5 seg
- Palenca (si aplica): < 10 seg
- process_document_chat: < 30 seg por documento
- XGBoost predict: < 1 seg
- Claude ajuste cualitativo: < 15 seg
- Persistencia + emisión eventos: < 5 seg
- **Total ideal:** ~95 seg
- **Buffer para variabilidad de partners:** 200 seg

## Dashboard métricas (consumido por executive web /scoring)

KPIs principales:
- Total solicitudes (filtros: período, origen argos/web, producto)
- Tasa de aprobación (%)
- Score promedio (filtros: producto, origen)
- Monto total aprobado
- Distribución por categoría de riesgo (gráfico de barras)
- Tiempo promedio de evaluación
- Tasa de fraude detectado por RiskSeal
- Tabla de solicitudes individuales con narrativa Claude
- Botón "Descargar Excel" (audit trail completo)

## Tests obligatorios de cierre (heredados del Build 20 con adaptaciones ARGOS)

- SC-01: POST /api/v1/scoring/solicitar → solicitud creada con ID único SCR-ARGOS-2026-XXXX
- SC-02: Flujo delivery completo: KYC + Palenca + AUCO + RiskSeal + score + WhatsApp → < 5 min
- SC-03: Flujo empleado completo: KYC + AUCO + RiskSeal + score + WhatsApp → < 5 min
- SC-04: AUCO score < 70 → bloqueo inmediato sin llamar Claude (ROG-S3)
- SC-05: RiskSeal fraud_flag → rechazo inmediato sin llamar Claude (ROG-S3)
- SC-06: Score 720 crédito moto → aprobado + monto calculado + WhatsApp enviado
- SC-07: Score 480 crédito repuestos → aprobado (umbral 500 repuestos)
- SC-08: Score 530 crédito moto → revision_manual + alerta al analista (sin email · ROG-S6)
- SC-09: Cliente RODDOS A+ con score 610 → aprobado moto (umbral baja a 600)
- SC-10: Cliente RODDOS B con monto $300K repuestos → bypass aplicado (flujo F3 express)
- SC-11: Si Palenca cae → fallback a revisión_manual (no crash)
- SC-12: Si AUCO cae → fallback a revisión_manual
- SC-13: Si RiskSeal cae para repuestos cliente nuevo → bloquea venta crédito (cash sí permitido)
- SC-14: Tiempo total evaluación < 300 segundos registrado en scoring_solicitudes
- SC-15: Notificación SOLO por WhatsApp · NO email (ROG-S6 — diferencia explícita vs admin web)
- SC-16: Modelo XGBoost actualizado weekly desde loanbook SISMO snapshot
- SC-17: Modelo hash registrado en argos_events.score.ml.calculated (ROG-S5)
- SC-18: Narrativa de decisión persiste con timestamp + versión prompt (ROG-S4)
- SC-19: Re-entrenamiento weekly genera nueva versión del modelo + canary contra dataset eval

## Referencias

- Build 20 original (admin web): RODDOS_SCORING_CLAUDE_EMERGENT.docx
- Canónicas relacionadas: docs/canonicas/eventos.md (Score Engine), apis_externas.md (AUCO, RiskSeal, Palenca), integraciones_sismo.md (loanbook + score-result)
- Skill relacionada: docs/knowledge/skills/kyc_conversacional.md
