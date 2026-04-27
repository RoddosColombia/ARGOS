export type InventoryType = "all" | "slow_movers";

export interface InventoryItem {
  sku: string;
  nombre: string;
  stock: number;
  precio: number;
  costo: number;
  dias_inventario: number;
  is_slow_mover: boolean;
  fecha_sync_date: string;
  fecha_sync: string | null;
}

export interface InventoryResponse {
  fecha_sync_date: string | null;
  type: InventoryType;
  items: InventoryItem[];
  total: number;
}
