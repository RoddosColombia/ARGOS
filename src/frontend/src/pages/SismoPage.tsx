import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { apiRequest } from "@/lib/api";
import type {
  InventoryResponse,
  InventoryType,
  SalesResponse,
} from "@/types/sismo";

const REFRESH_MS = 5 * 60 * 1000;

const NUM = new Intl.NumberFormat("es-CO");
const COP = new Intl.NumberFormat("es-CO", {
  style: "currency",
  currency: "COP",
  maximumFractionDigits: 0,
});

type Tab = "inventory" | "sales";

function InventoryTab() {
  const [type, setType] = useState<InventoryType>("all");

  const query = useQuery<InventoryResponse>({
    queryKey: ["sismo", "inventory", type],
    queryFn: () => apiRequest<InventoryResponse>(`/api/v1/sismo/inventory?type=${type}&limit=200`),
    refetchInterval: REFRESH_MS,
  });

  return (
    <>
      <div className="flex gap-2" data-testid="filter-toggle">
        <button
          type="button"
          onClick={() => setType("all")}
          className={`rounded-md px-3 py-1.5 text-sm font-medium ring-1 ${
            type === "all"
              ? "bg-brand-50 text-brand-700 ring-brand-200"
              : "bg-white text-ink-700 ring-ink-200 hover:bg-ink-50"
          }`}
        >
          Todos
        </button>
        <button
          type="button"
          onClick={() => setType("slow_movers")}
          className={`rounded-md px-3 py-1.5 text-sm font-medium ring-1 ${
            type === "slow_movers"
              ? "bg-amber-50 text-amber-800 ring-amber-200"
              : "bg-white text-ink-700 ring-ink-200 hover:bg-ink-50"
          }`}
        >
          Slow movers (≥45 días)
        </button>
      </div>

      {query.isLoading && (
        <div className="rounded-lg border border-ink-200 bg-white p-12 text-center text-sm text-ink-500">
          Cargando inventario…
        </div>
      )}

      {query.isError && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-12 text-center text-sm text-red-700">
          Error: {(query.error as Error).message}
        </div>
      )}

      {query.data && query.data.items.length === 0 && (
        <div
          className="rounded-lg border border-ink-200 bg-white p-12 text-center text-sm text-ink-500"
          data-testid="sismo-empty"
        >
          {query.data.fecha_sync_date === null
            ? "SISMO V2 todavía no se sincronizó · revisa SISMO_API_URL y SISMO_API_KEY."
            : "Sin SKUs que cumplan el filtro."}
        </div>
      )}

      {query.data && query.data.items.length > 0 && (
        <div
          className="overflow-hidden rounded-lg border border-ink-200 bg-white shadow-sm"
          data-testid="sismo-table-wrapper"
        >
          <table className="w-full text-left text-sm" data-testid="sismo-table">
            <thead className="bg-ink-50 text-xs uppercase tracking-wider text-ink-500">
              <tr>
                <th className="px-4 py-2.5">SKU</th>
                <th className="px-4 py-2.5">Nombre</th>
                <th className="px-4 py-2.5 text-right">Stock</th>
                <th className="px-4 py-2.5 text-right">Precio</th>
                <th className="px-4 py-2.5 text-right">Días inv.</th>
                <th className="px-4 py-2.5">Estado</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ink-100">
              {query.data.items.map((item) => (
                <tr key={`${item.sku}-${item.fecha_sync_date}`} data-testid="sismo-row">
                  <td className="px-4 py-2.5 font-mono text-xs text-ink-900">{item.sku}</td>
                  <td className="px-4 py-2.5 text-ink-700">{item.nombre}</td>
                  <td className="px-4 py-2.5 text-right tabular-nums">{NUM.format(item.stock)}</td>
                  <td className="px-4 py-2.5 text-right tabular-nums text-ink-700">
                    {COP.format(item.precio)}
                  </td>
                  <td className="px-4 py-2.5 text-right tabular-nums">{item.dias_inventario}</td>
                  <td className="px-4 py-2.5">
                    {item.is_slow_mover ? (
                      <span className="inline-flex items-center rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-semibold text-amber-800 ring-1 ring-amber-200">
                        slow mover
                      </span>
                    ) : (
                      <span className="text-xs text-ink-500">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

function SalesTab() {
  const query = useQuery<SalesResponse>({
    queryKey: ["sismo", "sales", "latest"],
    queryFn: () => apiRequest<SalesResponse>("/api/v1/sismo/sales?limit=100"),
    refetchInterval: REFRESH_MS,
  });

  return (
    <>
      {query.isLoading && (
        <div className="rounded-lg border border-ink-200 bg-white p-12 text-center text-sm text-ink-500">
          Cargando ventas…
        </div>
      )}

      {query.isError && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-12 text-center text-sm text-red-700">
          Error: {(query.error as Error).message}
        </div>
      )}

      {query.data && query.data.items.length === 0 && (
        <div
          className="rounded-lg border border-ink-200 bg-white p-12 text-center text-sm text-ink-500"
          data-testid="sales-empty"
        >
          {query.data.date === null
            ? "Aún no hay sync de ventas · el job corre 01:00 UTC todos los días."
            : "Sin ventas para esta fecha."}
        </div>
      )}

      {query.data && query.data.items.length > 0 && (
        <>
          <div className="grid gap-3 sm:grid-cols-3" data-testid="sales-totals">
            <div className="rounded-lg border border-ink-200 bg-white p-4 shadow-sm">
              <div className="text-xs uppercase tracking-wider text-ink-500">Fecha</div>
              <div className="mt-2 text-2xl font-semibold tabular-nums text-ink-900">
                {query.data.date}
              </div>
            </div>
            <div className="rounded-lg border border-ink-200 bg-white p-4 shadow-sm">
              <div className="text-xs uppercase tracking-wider text-ink-500">Unidades</div>
              <div className="mt-2 text-2xl font-semibold tabular-nums text-ink-900">
                {NUM.format(query.data.totals.units_sold)}
              </div>
            </div>
            <div className="rounded-lg border border-ink-200 bg-white p-4 shadow-sm">
              <div className="text-xs uppercase tracking-wider text-ink-500">Revenue</div>
              <div className="mt-2 text-2xl font-semibold tabular-nums text-ink-900">
                {COP.format(query.data.totals.revenue_cop)}
              </div>
            </div>
          </div>

          <div
            className="mt-4 overflow-hidden rounded-lg border border-ink-200 bg-white shadow-sm"
            data-testid="sales-table-wrapper"
          >
            <table className="w-full text-left text-sm" data-testid="sales-table">
              <thead className="bg-ink-50 text-xs uppercase tracking-wider text-ink-500">
                <tr>
                  <th className="px-4 py-2.5">SKU</th>
                  <th className="px-4 py-2.5 text-right">Unidades</th>
                  <th className="px-4 py-2.5 text-right">Revenue</th>
                  <th className="px-4 py-2.5">Canal</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-ink-100">
                {query.data.items.map((item) => (
                  <tr key={`${item.sku}-${item.date}`} data-testid="sales-row">
                    <td className="px-4 py-2.5 font-mono text-xs text-ink-900">{item.sku}</td>
                    <td className="px-4 py-2.5 text-right tabular-nums">
                      {NUM.format(item.units_sold)}
                    </td>
                    <td className="px-4 py-2.5 text-right tabular-nums text-ink-700">
                      {COP.format(item.revenue)}
                    </td>
                    <td className="px-4 py-2.5 text-ink-700">{item.channel}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </>
  );
}

export function SismoPage() {
  const [tab, setTab] = useState<Tab>("inventory");

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-ink-900">SISMO V2</h1>
        <p className="mt-1 text-sm text-ink-500">
          Inventario y ventas read-only desde el ERP de RODDOS.
        </p>
      </header>

      <div className="border-b border-ink-200" data-testid="sismo-tabs">
        <nav className="-mb-px flex gap-6">
          <button
            type="button"
            onClick={() => setTab("inventory")}
            className={`border-b-2 px-1 py-2.5 text-sm font-medium ${
              tab === "inventory"
                ? "border-brand-500 text-brand-700"
                : "border-transparent text-ink-500 hover:border-ink-300 hover:text-ink-700"
            }`}
          >
            Inventario
          </button>
          <button
            type="button"
            onClick={() => setTab("sales")}
            className={`border-b-2 px-1 py-2.5 text-sm font-medium ${
              tab === "sales"
                ? "border-brand-500 text-brand-700"
                : "border-transparent text-ink-500 hover:border-ink-300 hover:text-ink-700"
            }`}
          >
            Ventas
          </button>
        </nav>
      </div>

      {tab === "inventory" ? <InventoryTab /> : <SalesTab />}
    </div>
  );
}
