export type Producto = "credito_rdx_leasing" | "credito_rodante";
export type TipoEmpleo = "empleado" | "independiente" | "delivery" | "mototaxi";
export type UsoMoto = "personal" | "trabajo" | "ambos";
export type ScoreComportamental = "A+" | "A" | "B" | "C" | "D" | "E";
export type Decision =
  | "aprobado"
  | "rechazado"
  | "rechazado_regla_dura"
  | "revision_manual";

export interface ScoreSolicitudRequest {
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

export interface ScoreResult {
  solicitud_id: string;
  producto: string;
  score_final: number;
  score_modelo: number;
  score_claude: number;
  delta_claude: number;
  narrativa: string;
  decision: Decision;
  regla_dura_aplicada: string | null;
  fraude_detectado: boolean;
  threshold_aplicado: number;
  engine_version: string;
}

export interface SolicitudListItem extends ScoreResult {
  id: string;
  monto_solicitado: number;
  created_at: string | null;
}
