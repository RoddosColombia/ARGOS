export type MarketplaceSource = "meli" | "fb" | "all";

export interface TopProduct {
  sku_normalizado: string;
  titulo: string;
  precio_actual: number;
  precio_promedio: number;
  fuente: "meli" | "fb";
  cambio_precio_pct: number;
  ultima_actualizacion: string | null;
  permalink: string;
}
