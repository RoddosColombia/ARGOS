import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { apiRequest } from "@/lib/api";
import type { HitRateResponse, Recommendation } from "@/types/recommendations";

const REFRESH_MS = 60 * 1000;

const NUM = new Intl.NumberFormat("es-CO");
const PCT = new Intl.NumberFormat("es-CO", { style: "percent", maximumFractionDigits: 1 });

function PrioridadBadge({ prioridad }: { prioridad: Recommendation["priority"] }) {
  const styles: Record<Recommendation["priority"], string> = {
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

function StatusBadge({ status }: { status: Recommendation["status"] }) {
  const styles: Record<Recommendation["status"], string> = {
    pendiente: "bg-amber-100 text-amber-800 ring-amber-200",
    aprobada: "bg-blue-100 text-blue-700 ring-blue-200",
    ejecutada: "bg-indigo-100 text-indigo-700 ring-indigo-200",
    rechazada: "bg-ink-100 text-ink-700 ring-ink-200",
    rechazada_compliance: "bg-red-100 text-red-700 ring-red-200",
    expirada: "bg-ink-100 text-ink-500 ring-ink-200",
    evaluada: "bg-emerald-100 text-emerald-700 ring-emerald-200",
  };
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ${styles[status]}`}>
      {status}
    </span>
  );
}

function HitRateWidget() {
  const query = useQuery<HitRateResponse>({
    queryKey: ["recommendations", "hit-rate", 30],
    queryFn: () => apiRequest<HitRateResponse>("/api/v1/recommendations/hit-rate?days=30"),
    refetchInterval: REFRESH_MS,
  });

  return (
    <div className="rounded-lg border border-ink-200 bg-white p-5 shadow-sm" data-testid="hit-rate-widget">
      <div className="text-xs uppercase tracking-wider text-ink-500">Hit rate · últimos 30 días</div>
      {query.isLoading && <div className="mt-2 text-sm text-ink-500">Cargando…</div>}
      {query.data && (
        <>
          <div className="mt-2 text-3xl font-semibold tabular-nums text-ink-900">
            {query.data.avg_hit_rate === null ? "—" : PCT.format(query.data.avg_hit_rate)}
          </div>
          <div className="mt-1 text-xs text-ink-500">
            {NUM.format(query.data.evaluated_count)} recomendaciones evaluadas
          </div>
        </>
      )}
      {query.isError && (
        <div className="mt-2 text-sm text-red-700">Error: {(query.error as Error).message}</div>
      )}
    </div>
  );
}

function RecommendationCard({ rec }: { rec: Recommendation }) {
  const qc = useQueryClient();
  const [busy, setBusy] = useState<"approve" | "reject" | null>(null);

  const approveMut = useMutation({
    mutationFn: () =>
      apiRequest<Recommendation>(`/api/v1/recommendations/${rec.id}/approve`, { method: "POST" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["recommendations"] });
    },
    onSettled: () => setBusy(null),
  });

  const rejectMut = useMutation({
    mutationFn: (reason: string) =>
      apiRequest<Recommendation>(`/api/v1/recommendations/${rec.id}/reject`, {
        method: "POST",
        body: { reason },
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["recommendations"] });
    },
    onSettled: () => setBusy(null),
  });

  const onApprove = () => {
    setBusy("approve");
    approveMut.mutate();
  };
  const onReject = () => {
    const reason = window.prompt("Motivo del rechazo (opcional):") ?? "";
    setBusy("reject");
    rejectMut.mutate(reason);
  };

  return (
    <article
      className="flex flex-col gap-3 rounded-lg border border-ink-200 bg-white p-4 shadow-sm"
      data-testid="recommendation-card"
    >
      <div className="flex items-start justify-between gap-3">
        <h3 className="text-base font-semibold text-ink-900">{rec.action_description}</h3>
        <div className="flex shrink-0 gap-2">
          <PrioridadBadge prioridad={rec.priority} />
          <StatusBadge status={rec.status} />
        </div>
      </div>
      <p className="text-sm text-ink-700">{rec.rationale}</p>
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-500">
        <span>tipo: <code>{rec.type}</code></span>
        {rec.expected_impact?.target && <span>target: {rec.expected_impact.target}</span>}
        {rec.hit_rate_contribution !== null && (
          <span>hit_rate: <strong>{rec.hit_rate_contribution}</strong></span>
        )}
      </div>
      {rec.learning && (
        <p className="rounded-md bg-ink-50 p-3 text-xs italic text-ink-700">
          💡 {rec.learning}
        </p>
      )}
      {rec.status === "pendiente" && (
        <div className="flex gap-2 pt-1">
          <button
            type="button"
            onClick={onApprove}
            disabled={busy !== null}
            className="rounded-md bg-brand-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {busy === "approve" ? "Aprobando…" : "Aprobar"}
          </button>
          <button
            type="button"
            onClick={onReject}
            disabled={busy !== null}
            className="rounded-md border border-ink-300 bg-white px-3 py-1.5 text-sm font-medium text-ink-700 hover:bg-ink-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {busy === "reject" ? "Rechazando…" : "Rechazar"}
          </button>
        </div>
      )}
    </article>
  );
}

export function RecommendationsPage() {
  const query = useQuery<Recommendation[]>({
    queryKey: ["recommendations", "list"],
    queryFn: () => apiRequest<Recommendation[]>("/api/v1/recommendations?limit=20"),
    refetchInterval: REFRESH_MS,
  });

  return (
    <div className="mx-auto max-w-5xl space-y-8">
      <header>
        <h1 className="text-2xl font-semibold text-ink-900">Recomendaciones</h1>
        <p className="mt-1 text-sm text-ink-500">
          Acciones del Strategist · pendientes, aprobadas, ejecutadas y evaluadas.
        </p>
      </header>

      <section>
        <HitRateWidget />
      </section>

      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-ink-500">
          Recomendaciones recientes
        </h2>
        {query.isLoading && (
          <div className="rounded-lg border border-ink-200 bg-white p-12 text-center text-sm text-ink-500">
            Cargando recomendaciones…
          </div>
        )}
        {query.isError && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-12 text-center text-sm text-red-700">
            Error: {(query.error as Error).message}
          </div>
        )}
        {query.data && query.data.length === 0 && (
          <div
            className="rounded-lg border border-ink-200 bg-white p-12 text-center text-sm text-ink-500"
            data-testid="recommendations-empty"
          >
            Sin recomendaciones · esperá al próximo briefing.
          </div>
        )}
        {query.data && query.data.length > 0 && (
          <div className="grid gap-3" data-testid="recommendations-list">
            {query.data.map((r) => (
              <RecommendationCard key={r.id} rec={r} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
