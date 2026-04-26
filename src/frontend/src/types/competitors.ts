export type AdSource = "meta" | "google" | "all";

export interface CompetitorAd {
  id: string;
  plataforma: string;
  ad_id_externo: string;
  anunciante: string;
  copy_texto: string;
  copy_titulo: string;
  url_landing: string;
  fecha_inicio: string | null;
  durabilidad_dias: number;
  formato: string;
  activo: boolean;
  fuente_query: string;
  keywords_pautadas: string[];
}
