# docs/canonicas/

Mapas de conexión del sistema ARGOS. Toda integración, ruta, evento o colección que sirva de interfaz entre módulos vive aquí.

Propósito: garantizar que todo nuevo desarrollo se conecte sobre líneas existentes y no abra rutas paralelas sin sentido. Antes de escribir cualquier código que conecte dos módulos, se consulta la canónica correspondiente. Si la conexión no existe, se agrega aquí primero, luego se implementa.

## Archivos

| Archivo | Contenido |
|---------|-----------|
| eventos.md | Bus argos_events: cada evento con productor, consumidor, schema, criticidad |
| apis_internas.md | Endpoints REST entre módulos ARGOS (entre agentes, frontend interno, etc.) |
| apis_externas.md | Integraciones con partners externos (Mercately, Wava, RiskSeal, AUCO, Palenca, MELI, Meta Ads, Google Ads, Apify, TikHub, SerpAPI) |
| colecciones_mongo.md | Cada colección MongoDB: schema, workspace_id, quién escribe, quién lee, índices |
| integraciones_sismo.md | Mapa específico ARGOS ⇄ SISMO V2: loanbook lectura/escritura, RADAR, inventario, ventas, eventos cruzados |
| flujos_negocio.md | Los 6 flujos de negocio expresados como secuencias de eventos canónicos |

## Reglas

1. Cada PR que afecte una integración debe actualizar la canónica correspondiente en el mismo PR. Sin excepciones.
2. Cada evento nuevo del bus se registra en eventos.md ANTES de ser emitido en código.
3. Cada partner externo nuevo se registra en apis_externas.md y en docs/knowledge/partners.md ANTES de la primera llamada.
4. Cada colección nueva se registra en colecciones_mongo.md con su schema completo.
5. Cualquier cambio breaking en una canónica requiere bump de versión y migración documentada.
