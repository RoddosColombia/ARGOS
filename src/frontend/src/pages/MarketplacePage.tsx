import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { apiRequest } from "@/lib/api";
import type { MarketplaceSource, TopProduct } from "@/types/marketplace";

const REFRESH_INTERVAL_MS = 5 * 60 * 1000; // 5 min

const SOURCE_OPTIONS: { value: MarketplaceSource; label: string }[] = [
  { value: "all", label: "Todos" },
  { value: "meli", label: "MercadoLibre" },
  { value: "fb", label: "FB Marketplace" },
];

const COP_FORMATTER = new Intl.NumberFormat("es-CO", {
  style: "currency",
  currency: "COP",
  maximumFractionDigits: 0,
});

const RELATIVE_FORMATTER = new Intl.RelativeTimeFormat("es-CO", { numeric: "auto" });

function formatPrice(value: number): string {
  return COP_FORMATTER.format(value);
}

function formatRelative(iso: string | null): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  const diffSec = (date.getTime() - Date.now()) / 1000;
  const abs = Math.abs(diffSec);
  if (abs < 60) return RELATIVE_FORMATTER.format(Math.round(diffSec), "second");
  if (abs < 3600) return RELATIVE_FORMATTER.format(Math.round(diffSec / 60), "minute");
  if (abs < 86400) return RELATIVE_FORMATTER.format(Math.round(diffSec / 3600), "hour");
  return RELATIVE_FORMATTER.format(Math.round(diffSec / 86400), "day");
}

function DeltaBadge({ pct }: { pct: number }) {
  const rounded = Math.round(pct * 10) / 10;
  if (Math.abs(rounded) < 0.5) {
    return (
      <span className="inline-flex items-center rounded-full bg-ink-100 px-2 py-0.5 text-xs font-medium text-ink-500">
        sin cambio
      </span>
    );
  }
  if (rounded > 0) {
    return (
      <span className="inline-flex items-center rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700">
        +{rounded.toFixed(1)}%
      </span>
    );
  }
  return (
    <span className="inline-flex items-center rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700">
      {rounded.toFixed(1)}%
    </span>
  );
}

function SourceBadge({ fuente }: { fuente: "meli" | "fb" }) {
  const styles =
    fuente === "meli"
      ? "bg-yellow-100 text-yellow-800"
      : "bg-blue-100 text-blue-800";
  const label = fuente === "meli" ? "MercadoLibre" : "FB Marketplace";
  return (
    <span className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ${styles}`}>
      {label}
    </span>
  );
}

export function MarketplacePage() {
  const [source, setSource] = useState<MarketplaceSource>("all");

  const query = useQuery<TopProduct[]>({
    queryKey: ["marketplace", "top-products", source],
    queryFn: () =>
      apiRequest<TopProduct[]>(`/api/v1/marketplace/top-products?source=${source}`),
    refetchInterval: REFRESH_INTERVAL_MS,
    refetchIntervalInBackground: false,
  });

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-ink-900">Marketplace</h1>
          <p className="mt-1 text-sm text-ink-500">
            Top 50 repuestos detectados por el Scout · auto-refresh cada 5 min
          </p>
        </div>
        <div className="flex items-center gap-2">
          <label htmlFor="source-filter" className="text-xs font-medium text-ink-500">
            Fuente
          </label>
          <select
            id="source-filter"
            value={source}
            onChange={(e) => setSource(e.target.value as MarketplaceSource)}
            className="rounded-md border border-ink-200 bg-white px-3 py-1.5 text-sm text-ink-900 outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20"
          >
            {SOURCE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>
      </header>

      <div className="overflow-hidden rounded-lg border border-ink-200 bg-white shadow-sm">
        {query.isLoading && (
          <div className="p-8 text-center text-sm text-ink-500">Cargando…</div>
        )}
        {query.isError && (
          <div className="p-8 text-center text-sm text-red-700">
            Error al cargar: {(query.error as Error).message}
          </div>
        )}
        {query.data && query.data.length === 0 && (
          <div className="p-8 text-center text-sm text-ink-500">
            Sin productos para esta fuente · espera al próximo tick del Scout
          </div>
        )}
        {query.data && query.data.length > 0 && (
          <table className="w-full text-sm" data-testid="marketplace-table">
            <thead className="border-b border-ink-200 bg-ink-50 text-xs uppercase tracking-wider text-ink-500">
              <tr>
                <th className="px-4 py-2 text-left font-semibold">SKU</th>
                <th className="px-4 py-2 text-left font-semibold">Título</th>
                <th className="px-4 py-2 text-left font-semibold">Fuente</th>
                <th className="px-4 py-2 text-right font-semibold">Precio</th>
                <th className="px-4 py-2 text-right font-semibold">Variación</th>
                <th className="px-4 py-2 text-right font-semibold">Actualizado</th>
              </tr>
            </thead>
            <tbody>
              {query.data.map((p) => (
                <tr
                  key={p.sku_normalizado}
                  className="border-b border-ink-100 last:border-b-0 hover:bg-ink-50"
                >
                  <td className="px-4 py-2 font-mono text-xs text-ink-700">
                    {p.sku_normalizado}
                  </td>
                  <td className="max-w-md truncate px-4 py-2 text-ink-900">
                    {p.permalink ? (
                      <a
                        href={p.permalink}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="hover:underline"
                      >
                        {p.titulo}
                      </a>
                    ) : (
                      p.titulo
                    )}
                  </td>
                  <td className="px-4 py-2">
                    <SourceBadge fuente={p.fuente} />
                  </td>
                  <td className="px-4 py-2 text-right tabular-nums text-ink-900">
                    {formatPrice(p.precio_actual)}
                  </td>
                  <td className="px-4 py-2 text-right">
                    <DeltaBadge pct={p.cambio_precio_pct} />
                  </td>
                  <td className="px-4 py-2 text-right text-xs text-ink-500">
                    {formatRelative(p.ultima_actualizacion)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {query.data && query.data.length > 0 && (
        <p className="text-xs text-ink-500">
          {query.data.length} producto{query.data.length === 1 ? "" : "s"}
          {query.isFetching ? " · refrescando…" : ""}
        </p>
      )}
    </div>
  );
}
