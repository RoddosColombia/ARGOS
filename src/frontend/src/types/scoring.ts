export type Producto = "credito_rdx_leasing" | "credito_rodante";
export type TipoEmpleo = "empleado" | "independiente" | "delivery" | "mototaxi";
export type UsoMoto = "personal" | "trabajo" | "ambos";
export type ScoreComportamental = "A+" | "A" | "B" | "C" | "D" | "E";
export type Decision =
  | "aprobado"
  | "rechazado"
  | "rechazado_regla_dura"
  | "revision_manual"
  | "no_configurado";

export interface ScoreEvaluatePayload {
  producto: Producto;
  cedula: string;
  nombre: string;
  ingreso_declarado: number;
  gastos_mensuales: number;
  tipo_empleo: TipoEmpleo;
  uso_moto: UsoMoto;
  score_comportamental?: ScoreComportamental | null;
  monto_solicitado: number;
}

/** Respuesta cruda del Score Engine externo · ARGOS solo hace pass-through. */
export interface ScoreEvaluateResponse {
  decision: Decision | string;
  score_final: number;
  solicitud_id: string;
  narrativa?: string;
  regla_dura_aplicada?: string | null;
  threshold_aplicado?: number;
  engine_version?: string;
  [key: string]: unknown;
}

export interface SolicitudListItem {
  id: string;
  solicitud_id: string;
  producto: string;
  score_final: number;
  decision: string;
  nombre: string;
  monto_solicitado: number;
  narrativa: string;
  regla_dura_aplicada: string | null;
  engine_version: string;
  created_at: string | null;
}

export interface ScoreConfig {
  score_engine_api_url: string | null;
  roddos_mongodb_configured: boolean;
}
