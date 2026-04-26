import { useQuery } from "@tanstack/react-query";
import { ApiError, apiRequest } from "@/lib/api";
import type { AccionRecomendada, Briefing, Prioridad } from "@/types/briefing";

const REFRESH_MS = 15 * 60 * 1000; // 15 min

const NUM = new Intl.NumberFormat("es-CO");

function formatFecha(iso: string): string {
  const date = new Date(iso + "T00:00:00Z");
  if (Number.isNaN(date.getTime())) return iso;
  return new Intl.DateTimeFormat("es-CO", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(date);
}

function PrioridadBadge({ prioridad }: { prioridad: Prioridad }) {
  const styles: Record<Prioridad, string> = {
    Alta: "bg-red-100 text-red-700 ring-red-200",
    Media: "bg-amber-100 text-amber-800 ring-amber-200",
    Baja: "bg-ink-100 text-ink-700 ring-ink-200",
  };
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ${styles[prioridad]}`}>
      {prioridad}
    </span>
  );
}

function MetricCard({ label, value, emoji }: { label: string; value: number; emoji: string }) {
  return (
    <div className="rounded-lg border border-ink-200 bg-white p-4 shadow-sm" data-testid="metric-card">
      <div className="flex items-center gap-2">
        <span className="text-2xl" aria-hidden>{emoji}</span>
        <span className="text-xs uppercase tracking-wider text-ink-500">{label}</span>
      </div>
      <div className="mt-2 text-3xl font-semibold tabular-nums text-ink-900">{NUM.format(value)}</div>
    </div>
  );
}

function AccionCard({ accion, idx }: { accion: AccionRecomendada; idx: number }) {
  return (
    <article
      className="flex flex-col gap-2 rounded-lg border border-ink-200 bg-white p-4 shadow-sm"
      data-testid="accion-card"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="grid size-7 place-items-center rounded-full bg-brand-100 text-sm font-semibold text-brand-700">
            {idx + 1}
          </span>
          <h3 className="text-base font-semibold text-ink-900">{accion.accion}</h3>
        </div>
        <PrioridadBadge prioridad={accion.prioridad} />
      </div>
      <p className="text-sm text-ink-700">{accion.justificacion}</p>
      <p className="text-xs italic text-ink-500">
        <span className="font-medium not-italic">Impacto esperado:</span> {accion.impacto_esperado}
      </p>
    </article>
  );
}

export function BriefingPage() {
  const query = useQuery<Briefing>({
    queryKey: ["briefing", "today"],
    queryFn: () => apiRequest<Briefing>("/api/v1/briefing/today"),
    refetchInterval: REFRESH_MS,
    refetchIntervalInBackground: false,
    retry: false, // 404 cuando no hay briefing del día · no reintentar
  });

  const isNotFound = query.isError && query.error instanceof ApiError && query.error.status === 404;

  return (
    <div className="mx-auto max-w-5xl space-y-8">
      <header>
        <h1 className="text-2xl font-semibold text-ink-900">Morning Briefing</h1>
        <p className="mt-1 text-sm text-ink-500">
          {query.data
            ? formatFecha(query.data.fecha)
            : "Tu briefing diario · generado por Strategist 06:45 UTC"}
        </p>
      </header>

      {query.isLoading && (
        <div className="rounded-lg border border-ink-200 bg-white p-12 text-center text-sm text-ink-500">
          Cargando briefing…
        </div>
      )}

      {isNotFound && (
        <div
          className="rounded-lg border border-amber-200 bg-amber-50 p-12 text-center"
          data-testid="briefing-empty-state"
        >
          <div className="text-3xl" aria-hidden>☕</div>
          <h2 className="mt-2 text-lg font-semibold text-amber-900">Sin briefing del día</h2>
          <p className="mt-1 text-sm text-amber-800">
            El próximo job corre todos los días a las 06:45 UTC.
            <br />
            Si configuraste recientemente <code className="rounded bg-amber-100 px-1 py-0.5 text-xs">ANTHROPIC_API_KEY</code>,
            espera al próximo ciclo.
          </p>
        </div>
      )}

      {query.isError && !isNotFound && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-12 text-center text-sm text-red-700">
          Error: {(query.error as Error).message}
        </div>
      )}

      {query.data && (
        <>
          {/* Mercado 24h */}
          <section>
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-ink-500">
              Mercado 24h
            </h2>
            <div className="grid gap-3 sm:grid-cols-3" data-testid="mercado-grid">
              <MetricCard
                label="Nuevos SKUs"
                value={query.data.mercado_24h.nuevos_skus}
                emoji="📦"
              />
              <MetricCard
                label="Bajas de precio"
                value={query.data.mercado_24h.bajas_precio}
                emoji="📉"
              />
              <MetricCard
                label="Nuevas promos"
                value={query.data.mercado_24h.nuevas_promos}
                emoji="📢"
              />
            </div>
          </section>

          {/* Tus 3 Acciones Hoy */}
          <section>
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-ink-500">
              Tus {query.data.acciones_del_dia.length === 1 ? "acción" : `${query.data.acciones_del_dia.length} acciones`} hoy
            </h2>
            {query.data.acciones_del_dia.length === 0 ? (
              <div className="rounded-lg border border-ink-200 bg-white p-6 text-center text-sm text-ink-500">
                Sin acciones recomendadas hoy · día estable o briefing no se pudo generar
              </div>
            ) : (
              <div className="grid gap-3" data-testid="acciones-list">
                {query.data.acciones_del_dia.map((a, i) => (
                  <AccionCard key={`${a.accion}-${i}`} accion={a} idx={i} />
                ))}
              </div>
            )}
          </section>

          {/* Estado del Mercado */}
          <section>
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-ink-500">
              Estado del Mercado
            </h2>
            <div
              className="rounded-lg border border-ink-200 bg-white p-5 shadow-sm"
              data-testid="estado-mercado"
            >
              <p className="text-sm leading-relaxed text-ink-700">{query.data.estado_mercado}</p>
            </div>
          </section>

          <p className="text-xs text-ink-500">
            Modelo: {query.data.modelo_usado} · {NUM.format(query.data.tokens_input)} tokens in /{" "}
            {NUM.format(query.data.tokens_output)} out
          </p>
        </>
      )}
    </div>
  );
}
