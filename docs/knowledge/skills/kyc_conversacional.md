# docs/knowledge/skills/kyc_conversacional.md

# Skill: KYC Conversacional vía WhatsApp

Recolectar los datos KYC del cliente a través de una conversación natural por WhatsApp, no un formulario web largo.

**Agentes dueños:** WhatsApp Agent (conversación) + Score Engine (consumidor)
**Trigger:** cliente expresa intent de cotizar moto o pedir crédito repuestos
**Output:** `scoring_solicitudes` document completo listo para evaluación

## Principio UX

Formulario web = 23 campos en una pantalla = tasa de abandono 60%+
KYC conversacional = 23 campos en 4-5 intercambios naturales = tasa de abandono < 15%

## Estrategia: WhatsApp Flow + chat intercalado

WhatsApp Flows nativos son formularios estructurados dentro del chat (introducidos por Meta en 2023, maduros en 2026). Tienen:
- Inputs validados del lado Meta
- UI nativa · cero fricción
- Respuesta estructurada que llega como JSON

Se usan para los **bloques densos** (datos personales, residencia). El chat libre se usa para los datos que requieren contexto o interpretación (documentos adjuntos, explicación del uso de la moto).

## Secuencia

```
Paso 1 (chat libre): W saluda y confirma el producto
  "Perfecto, vamos con el Crédito RDX Leasing para la TVS Raider 125.
   Te voy a pedir unos datos rápidos. Nada complicado. Primero, unos datos básicos 👇"

Paso 2 (Flow 1 — datos personales):
  Envía WhatsApp Flow con:
  - Nombre completo
  - Tipo de documento (select: CC/CE/Pasaporte)
  - Número de documento
  - Fecha de nacimiento (date picker)
  - Email
  Cliente completa en 30-60 segundos.

Paso 3 (chat libre): W confirma recepción y pide biometría
  "✅ Listo [Nombre]. Ahora necesito una foto tuya y una de tu documento.
   1️⃣ Una selfie tuya mirando al frente
   2️⃣ Foto del documento por ambos lados"

Paso 4 (imágenes): Cliente envía selfie + doc
  W captura ambas imágenes → AUCO para validación biométrica

Paso 5 (Flow 2 — actividad económica):
  - Tipo de empleo (select: empleado / independiente / delivery / mototaxi)
  - Si delivery/mototaxi: plataforma (select: Rappi / DiDi / Uber / Otro)
  - Rango salarial (select)
  - Gastos mensuales aproximados (numérico)
  - Tiempo en esta actividad (meses, numérico)

Paso 6 (chat libre si delivery):
  W pide autorización OAuth Palenca
  "Para verificar tus ingresos sin papeleo, ¿me autorizas consultar Rappi?
   Es un minuto. [link OAuth Palenca]"

Paso 7 (Flow 3 — residencia + referencia):
  - País · Departamento · Ciudad · Dirección · Zona (urbana/rural)
  - Uso que le darás a la moto (movilidad / trabajo / mixto)
  - Nombre de referencia personal
  - Teléfono de referencia
  - Dirección referencia

Paso 8 (chat libre): W pide documentos financieros (opcional)
  "Si tienes a mano un desprendible de nómina o extracto de Nequi/Daviplata,
   envíamelo y acelera tu evaluación. Si no, igual seguimos 👍"

Paso 9 (confirmación): W resume los datos capturados
  "Perfecto. Aquí tu resumen:
   👤 [Nombre] [Documento]
   💼 [Tipo empleo]
   📍 [Ciudad]
   💰 Rango salarial [X]
   
   ¿Todo correcto? [Sí, enviar] / [Corregir]"

Paso 10: Cliente confirma → score_engine.create_solicitud() → evaluación arranca
  W envía: "✅ Recibido. Estoy evaluando. Te respondo en máximo 5 minutos ⏳"
```

## Manejo de errores

| Escenario | Respuesta del WhatsApp Agent |
|-----------|------------------------------|
| Cliente abandona a mitad del Flow | Resume con: "¿Seguimos donde quedamos? Te quedaban [X] preguntas" después de 2h |
| Imagen del documento borrosa | "La foto quedó un poquito borrosa. ¿Me mandas una más clara?" |
| AUCO rechaza biometría | "Hubo un problema con la verificación. Déjame revisar y te contacto en unos minutos" + handoff |
| Cliente no quiere compartir algún dato | Handoff humano para que el operador decida |

## Criterios de éxito

- Tasa de finalización del KYC iniciado > 75% (vs 40% en formulario web)
- Tiempo promedio de completado: 4-6 minutos
- Cero campos obligatorios faltantes al llegar al Score Engine
- AUCO pass rate en primera vez > 90%
