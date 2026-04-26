import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { apiRequest } from "@/lib/api";
import type { AdSource, CompetitorAd } from "@/types/competitors";

const REFRESH_MS = 10 * 60 * 1000; // 10 min
const COPY_TRUNCATE = 80;

const SOURCE_OPTIONS: { value: AdSource; label: string }[] = [
  { value: "all", label: "Todos" },
  { value: "meta", label: "Meta" },
  { value: "google", label: "Google" },
];

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

function PlataformaBadge({ plataforma }: { plataforma: string }) {
  const styles: Record<string, string> = {
    meta: "bg-blue-100 text-blue-800",
    google: "bg-emerald-100 text-emerald-800",
    tiktok: "bg-pink-100 text-pink-800",
  };
  const cls = styles[plataforma] ?? "bg-ink-100 text-ink-500";
  const label =
    plataforma === "meta" ? "Meta" : plataforma === "google" ? "Google" : plataforma;
  return (
    <span className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ${cls}`}>
      {label}
    </span>
  );
}

function FormatoBadge({ formato }: { formato: string }) {
  const styles: Record<string, string> = {
    video: "bg-purple-100 text-purple-800",
    image: "bg-blue-100 text-blue-800",
    carousel: "bg-pink-100 text-pink-800",
    text: "bg-amber-100 text-amber-800",
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
  const [source, setSource] = useState<AdSource>("all");
  const [onlyActive, setOnlyActive] = useState(false);

  const query = useQuery<CompetitorAd[]>({
    queryKey: ["competitors", "ads", source, onlyActive],
    queryFn: () => {
      const qs = new URLSearchParams({
        source,
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
          <h1 className="text-2xl font-semibold text-ink-900">Competidores · Ads</h1>
          <p className="mt-1 text-sm text-ink-500">
            Meta Ad Library + Google Ads Transparency · refresh cada 12 h
          </p>
        </div>
        <div className="flex items-end gap-4">
          <div className="flex items-center gap-2">
            <label htmlFor="source-filter" className="text-xs font-medium text-ink-500">
              Fuente
            </label>
            <select
              id="source-filter"
              value={source}
              onChange={(e) => setSource(e.target.value as AdSource)}
              className="rounded-md border border-ink-200 bg-white px-3 py-1.5 text-sm text-ink-900 outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20"
            >
              {SOURCE_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
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
        </div>
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
            Sin ads detectados · próximo refresh en máximo 12 h
          </div>
        )}
        {query.data && query.data.length > 0 && (
          <table className="w-full text-sm" data-testid="competitors-ads-table">
            <thead className="border-b border-ink-200 bg-ink-50 text-xs uppercase tracking-wider text-ink-500">
              <tr>
                <th className="px-4 py-2 text-left font-semibold">Plataforma</th>
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
                  <td className="px-4 py-2">
                    <PlataformaBadge plataforma={a.plataforma} />
                  </td>
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
