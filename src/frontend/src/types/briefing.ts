export type Prioridad = "Alta" | "Media" | "Baja";

export interface AccionRecomendada {
  accion: string;
  justificacion: string;
  impacto_esperado: string;
  prioridad: Prioridad;
}

export interface Mercado24h {
  nuevos_skus: number;
  bajas_precio: number;
  nuevas_promos: number;
}

export interface Briefing {
  id: string;
  fecha: string;
  mercado_24h: Mercado24h;
  acciones_del_dia: AccionRecomendada[];
  estado_mercado: string;
  modelo_usado: string;
  tokens_input: number;
  tokens_output: number;
  created_at: string | null;
}
