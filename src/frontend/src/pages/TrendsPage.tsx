import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "@/lib/api";
import type { KeywordTrend, PriceAlert } from "@/types/trends";

const TRENDS_REFETCH_MS = 10 * 60 * 1000; // 10 min
const ALERTS_REFETCH_MS = 5 * 60 * 1000; // 5 min

const COP = new Intl.NumberFormat("es-CO", {
  style: "currency",
  currency: "COP",
  maximumFractionDigits: 0,
});
const REL = new Intl.RelativeTimeFormat("es-CO", { numeric: "auto" });

function formatRelative(iso: string | null): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  const diffSec = (date.getTime() - Date.now()) / 1000;
  const abs = Math.abs(diffSec);
  if (abs < 60) return REL.format(Math.round(diffSec), "second");
  if (abs < 3600) return REL.format(Math.round(diffSec / 60), "minute");
  if (abs < 86400) return REL.format(Math.round(diffSec / 3600), "hour");
  return REL.format(Math.round(diffSec / 86400), "day");
}

function StatusBadge({ delta, spike }: { delta: number; spike: boolean }) {
  if (spike) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700">
        🔴 spike
      </span>
    );
  }
  if (delta < -10) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700">
        🔵 bajando
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700">
      🟢 estable
    </span>
  );
}

function FuenteBadge({ fuente }: { fuente: "meli" | "fb" }) {
  const styles =
    fuente === "meli" ? "bg-yellow-100 text-yellow-800" : "bg-blue-100 text-blue-800";
  const label = fuente === "meli" ? "MELI" : "FB";
  return (
    <span className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ${styles}`}>
      {label}
    </span>
  );
}

export function TrendsPage() {
  const trendsQ = useQuery<KeywordTrend[]>({
    queryKey: ["trends", "keywords"],
    queryFn: () => apiRequest<KeywordTrend[]>("/api/v1/trends/keywords"),
    refetchInterval: TRENDS_REFETCH_MS,
    refetchIntervalInBackground: false,
  });

  const alertsQ = useQuery<PriceAlert[]>({
    queryKey: ["alerts", "recent"],
    queryFn: () => apiRequest<PriceAlert[]>("/api/v1/alerts/recent?limit=20"),
    refetchInterval: ALERTS_REFETCH_MS,
    refetchIntervalInBackground: false,
  });

  return (
    <div className="mx-auto max-w-6xl space-y-8">
      <header>
        <h1 className="text-2xl font-semibold text-ink-900">Trends &amp; Alertas</h1>
        <p className="mt-1 text-sm text-ink-500">
          Interés Google Trends por keyword (refresh diario 03:00) · alertas de precio (refresh cada hora)
        </p>
      </header>

      {/* ─── Keywords ──────────────────────────────────────────────────── */}
      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-ink-500">
          Keywords tracked
        </h2>
        <div className="overflow-hidden rounded-lg border border-ink-200 bg-white shadow-sm">
          {trendsQ.isLoading && (
            <div className="p-8 text-center text-sm text-ink-500">Cargando…</div>
          )}
          {trendsQ.isError && (
            <div className="p-8 text-center text-sm text-red-700">
              Error: {(trendsQ.error as Error).message}
            </div>
          )}
          {trendsQ.data && trendsQ.data.length === 0 && (
            <div className="p-8 text-center text-sm text-ink-500">
              Sin keywords todavía · próximo job trends_refresh corre a las 03:00 UTC
            </div>
          )}
          {trendsQ.data && trendsQ.data.length > 0 && (
            <table className="w-full text-sm" data-testid="trends-keywords-table">
              <thead className="border-b border-ink-200 bg-ink-50 text-xs uppercase tracking-wider text-ink-500">
                <tr>
                  <th className="px-4 py-2 text-left font-semibold">Keyword</th>
                  <th className="px-4 py-2 text-right font-semibold">Interés (0-100)</th>
                  <th className="px-4 py-2 text-right font-semibold">Variación 7d</th>
                  <th className="px-4 py-2 text-left font-semibold">Estado</th>
                  <th className="px-4 py-2 text-right font-semibold">Actualizado</th>
                </tr>
              </thead>
              <tbody>
                {trendsQ.data.map((k) => (
                  <tr
                    key={k.keyword}
                    className="border-b border-ink-100 last:border-b-0 hover:bg-ink-50"
                  >
                    <td className="px-4 py-2 font-medium text-ink-900">{k.keyword}</td>
                    <td className="px-4 py-2 text-right tabular-nums text-ink-700">
                      {k.interest_over_time}
                    </td>
                    <td className="px-4 py-2 text-right tabular-nums text-ink-700">
                      {k.growth_pct_7d > 0 ? "+" : ""}
                      {k.growth_pct_7d.toFixed(1)}%
                    </td>
                    <td className="px-4 py-2">
                      <StatusBadge delta={k.growth_pct_7d} spike={k.spike_detected} />
                    </td>
                    <td className="px-4 py-2 text-right text-xs text-ink-500">
                      {formatRelative(k.updated_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </section>

      {/* ─── Alertas ───────────────────────────────────────────────────── */}
      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-ink-500">
          Alertas recientes (últimas 48h)
        </h2>
        <div className="overflow-hidden rounded-lg border border-ink-200 bg-white shadow-sm">
          {alertsQ.isLoading && (
            <div className="p-8 text-center text-sm text-ink-500">Cargando…</div>
          )}
          {alertsQ.isError && (
            <div className="p-8 text-center text-sm text-red-700">
              Error: {(alertsQ.error as Error).message}
            </div>
          )}
          {alertsQ.data && alertsQ.data.length === 0 && (
            <div className="p-8 text-center text-sm text-ink-500">
              Sin alertas en las últimas 48h
            </div>
          )}
          {alertsQ.data && alertsQ.data.length > 0 && (
            <ul data-testid="alerts-list" className="divide-y divide-ink-100">
              {alertsQ.data.map((a) => (
                <li key={a.event_id} className="flex items-center gap-4 px-4 py-3">
                  <FuenteBadge fuente={a.fuente} />
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-medium text-ink-900">
                      {a.competitor_url ? (
                        <a
                          href={a.competitor_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="hover:underline"
                        >
                          {a.titulo}
                        </a>
                      ) : (
                        a.titulo
                      )}
                    </div>
                    <div className="mt-0.5 text-xs text-ink-500 font-mono">
                      {a.sku_normalizado}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-sm tabular-nums text-ink-900">
                      <span className="text-ink-500 line-through">
                        {COP.format(a.precio_anterior)}
                      </span>{" "}
                      → <span className="font-medium">{COP.format(a.precio_actual)}</span>
                    </div>
                    <div className="mt-0.5 text-xs">
                      <span className="inline-flex items-center rounded-full bg-emerald-100 px-2 py-0.5 font-medium text-emerald-700">
                        {a.delta_pct.toFixed(1)}%
                      </span>
                      <span className="ml-2 text-ink-500">{formatRelative(a.timestamp_utc)}</span>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
    </div>
  );
}
