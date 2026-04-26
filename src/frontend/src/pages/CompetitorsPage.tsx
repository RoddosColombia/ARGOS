import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { apiRequest } from "@/lib/api";
import type { CompetitorAd } from "@/types/competitors";

const REFRESH_MS = 10 * 60 * 1000; // 10 min
const COPY_TRUNCATE = 80;

const REL = new Intl.RelativeTimeFormat("es-CO", { numeric: "auto" });

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  const diffSec = (date.getTime() - Date.now()) / 1000;
  const abs = Math.abs(diffSec);
  if (abs < 86400) return REL.format(Math.round(diffSec / 3600), "hour");
  return REL.format(Math.round(diffSec / 86400), "day");
}

function ActivoBadge({ activo }: { activo: boolean }) {
  return activo ? (
    <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700">
      🟢 activo
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 rounded-full bg-ink-100 px-2 py-0.5 text-xs font-medium text-ink-500">
      ⚪ pausado
    </span>
  );
}

function FormatoBadge({ formato }: { formato: string }) {
  const styles: Record<string, string> = {
    video: "bg-purple-100 text-purple-800",
    image: "bg-blue-100 text-blue-800",
    carousel: "bg-pink-100 text-pink-800",
    unknown: "bg-ink-100 text-ink-500",
  };
  const cls = styles[formato] ?? styles.unknown;
  return (
    <span className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ${cls}`}>
      {formato}
    </span>
  );
}

function truncate(s: string, n: number): string {
  if (!s) return "";
  return s.length > n ? `${s.slice(0, n)}…` : s;
}

export function CompetitorsPage() {
  const [onlyActive, setOnlyActive] = useState(false);

  const query = useQuery<CompetitorAd[]>({
    queryKey: ["competitors", "ads", "meta", onlyActive],
    queryFn: () => {
      const qs = new URLSearchParams({
        source: "meta",
        limit: "50",
        only_active: String(onlyActive),
      });
      return apiRequest<CompetitorAd[]>(`/api/v1/competitors/ads?${qs.toString()}`);
    },
    refetchInterval: REFRESH_MS,
    refetchIntervalInBackground: false,
  });

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-ink-900">Competidores · Meta Ads</h1>
          <p className="mt-1 text-sm text-ink-500">
            Ads detectados en Meta Ad Library · refresh cada 12 h via Apify
          </p>
        </div>
        <label className="flex items-center gap-2 text-sm text-ink-700">
          <input
            type="checkbox"
            checked={onlyActive}
            onChange={(e) => setOnlyActive(e.target.checked)}
            className="size-4 accent-brand-600"
            data-testid="only-active-checkbox"
          />
          Solo activos
        </label>
      </header>

      <div className="overflow-hidden rounded-lg border border-ink-200 bg-white shadow-sm">
        {query.isLoading && (
          <div className="p-8 text-center text-sm text-ink-500">Cargando…</div>
        )}
        {query.isError && (
          <div className="p-8 text-center text-sm text-red-700">
            Error: {(query.error as Error).message}
          </div>
        )}
        {query.data && query.data.length === 0 && (
          <div className="p-8 text-center text-sm text-ink-500">
            Sin ads detectados todavía · próximo job meta_ads_refresh corre en máximo 12 h
          </div>
        )}
        {query.data && query.data.length > 0 && (
          <table className="w-full text-sm" data-testid="competitors-ads-table">
            <thead className="border-b border-ink-200 bg-ink-50 text-xs uppercase tracking-wider text-ink-500">
              <tr>
                <th className="px-4 py-2 text-left font-semibold">Anunciante</th>
                <th className="px-4 py-2 text-left font-semibold">Copy</th>
                <th className="px-4 py-2 text-right font-semibold">Días activo</th>
                <th className="px-4 py-2 text-left font-semibold">Formato</th>
                <th className="px-4 py-2 text-right font-semibold">Inicio</th>
                <th className="px-4 py-2 text-left font-semibold">Estado</th>
              </tr>
            </thead>
            <tbody>
              {query.data.map((a) => (
                <tr
                  key={a.id}
                  className="border-b border-ink-100 last:border-b-0 hover:bg-ink-50"
                >
                  <td className="px-4 py-2 font-medium text-ink-900">
                    {a.url_landing ? (
                      <a
                        href={a.url_landing}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="hover:underline"
                      >
                        {a.anunciante}
                      </a>
                    ) : (
                      a.anunciante
                    )}
                  </td>
                  <td className="max-w-md px-4 py-2 text-ink-700">
                    {a.copy_titulo && (
                      <div className="font-medium text-ink-900">{truncate(a.copy_titulo, 60)}</div>
                    )}
                    <div className="text-xs text-ink-500">{truncate(a.copy_texto, COPY_TRUNCATE)}</div>
                  </td>
                  <td className="px-4 py-2 text-right tabular-nums text-ink-900">
                    {a.durabilidad_dias} d
                  </td>
                  <td className="px-4 py-2">
                    <FormatoBadge formato={a.formato} />
                  </td>
                  <td className="px-4 py-2 text-right text-xs text-ink-500">
                    {formatDate(a.fecha_inicio)}
                  </td>
                  <td className="px-4 py-2">
                    <ActivoBadge activo={a.activo} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {query.data && query.data.length > 0 && (
        <p className="text-xs text-ink-500">
          {query.data.length} ad{query.data.length === 1 ? "" : "s"}
          {query.isFetching ? " · refrescando…" : ""}
        </p>
      )}
    </div>
  );
}
