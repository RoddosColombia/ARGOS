export interface KeywordTrend {
  workspace_id: string;
  keyword: string;
  interest_over_time: number; // 0-100
  growth_pct_7d: number;
  spike_detected: boolean;
  vertical: string;
  updated_at: string | null;
}

export interface PriceAlert {
  event_id: string;
  timestamp_utc: string;
  sku_normalizado: string;
  titulo: string;
  precio_anterior: number;
  precio_actual: number;
  delta_pct: number;
  fuente: "meli" | "fb";
  competitor_url: string;
}
