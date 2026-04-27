import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { apiRequest } from "@/lib/api";
import type { Category, Suggestion, WatchQuery } from "@/types/config";

const REFRESH_MS = 60 * 1000;

type Tab = "mine" | "suggestions";

const SIGNAL_STYLE: Record<string, string> = {
  trending: "bg-emerald-100 text-emerald-700 ring-emerald-200",
  rising: "bg-blue-100 text-blue-700 ring-blue-200",
  liquidating: "bg-amber-100 text-amber-800 ring-amber-200",
  disappearing: "bg-red-100 text-red-700 ring-red-200",
};

function evidenceText(s: Suggestion): string {
  const ev = s.evidence;
  if (s.signal_type === "trending" && ev.value)
    return `${ev.value} menciones en productos detectados (7d)`;
  if (s.signal_type === "rising" && ev.value)
    return `${ev.value} nuevas publicaciones en 48h`;
  if (s.signal_type === "liquidating" && ev.value)
    return `↓${ev.value}% en precio del SKU`;
  if (s.signal_type === "disappearing" && ev.delta_pct)
    return `${ev.delta_pct}% menos publicaciones vs 7d atrás`;
  return JSON.stringify(ev);
}

function MineTab() {
  const qc = useQueryClient();
  const [showAdd, setShowAdd] = useState(false);
  const [newQ, setNewQ] = useState("");
  const [newCat, setNewCat] = useState<string>("");

  const queries = useQuery<WatchQuery[]>({
    queryKey: ["config", "queries"],
    queryFn: () => apiRequest<WatchQuery[]>("/api/v1/config/queries?limit=300"),
    refetchInterval: REFRESH_MS,
  });
  const cats = useQuery<Category[]>({
    queryKey: ["config", "categories"],
    queryFn: () => apiRequest<Category[]>("/api/v1/config/categories"),
  });

  const createMut = useMutation({
    mutationFn: (b: { query: string; category: string | null }) =>
      apiRequest<WatchQuery>("/api/v1/config/queries", { method: "POST", body: b }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["config", "queries"] });
      setShowAdd(false);
      setNewQ("");
    },
  });

  const patchMut = useMutation({
    mutationFn: (vars: { id: string; status: "active" | "paused" }) =>
      apiRequest<WatchQuery>(`/api/v1/config/queries/${vars.id}`, {
        method: "PATCH",
        body: { status: vars.status },
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["config", "queries"] }),
  });

  const delMut = useMutation({
    mutationFn: (id: string) =>
      apiRequest<void>(`/api/v1/config/queries/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["config", "queries"] }),
  });

  return (
    <>
      <div className="flex items-center justify-between" data-testid="mine-toolbar">
        <p className="text-sm text-ink-500">
          Términos que el Scout monitorea en marketplaces · ordenados por prioridad.
        </p>
        <button
          type="button"
          onClick={() => setShowAdd((v) => !v)}
          className="rounded-md bg-brand-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-700"
        >
          + Agregar query
        </button>
      </div>

      {showAdd && (
        <div
          className="rounded-lg border border-ink-200 bg-white p-4 shadow-sm"
          data-testid="add-query-form"
        >
          <div className="grid gap-2 sm:grid-cols-[1fr_auto_auto] sm:items-end">
            <label className="text-xs text-ink-500">
              Término
              <input
                type="text"
                value={newQ}
                onChange={(e) => setNewQ(e.target.value)}
                placeholder="ej. kit arrastre Pulsar 200"
                className="mt-1 block w-full rounded-md border border-ink-300 px-3 py-1.5 text-sm"
              />
            </label>
            <label className="text-xs text-ink-500">
              Categoría
              <select
                value={newCat}
                onChange={(e) => setNewCat(e.target.value)}
                className="mt-1 block w-full rounded-md border border-ink-300 px-3 py-1.5 text-sm"
              >
                <option value="">— sin categoría —</option>
                {cats.data?.map((c) => (
                  <option key={c.slug} value={c.slug}>{c.label}</option>
                ))}
              </select>
            </label>
            <button
              type="button"
              onClick={() => createMut.mutate({ query: newQ, category: newCat || null })}
              disabled={newQ.length < 2 || createMut.isPending}
              className="rounded-md bg-brand-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
            >
              {createMut.isPending ? "Guardando…" : "Crear"}
            </button>
          </div>
        </div>
      )}

      {queries.isLoading && (
        <div className="rounded-lg border border-ink-200 bg-white p-12 text-center text-sm text-ink-500">
          Cargando queries…
        </div>
      )}

      {queries.data && (
        <div className="overflow-hidden rounded-lg border border-ink-200 bg-white shadow-sm">
          <table className="w-full text-left text-sm" data-testid="queries-table">
            <thead className="bg-ink-50 text-xs uppercase tracking-wider text-ink-500">
              <tr>
                <th className="px-4 py-2.5">Término</th>
                <th className="px-4 py-2.5">Categoría</th>
                <th className="px-4 py-2.5">Origen</th>
                <th className="px-4 py-2.5">Estado</th>
                <th className="px-4 py-2.5"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ink-100">
              {queries.data.map((q) => (
                <tr key={q.id} data-testid="query-row">
                  <td className="px-4 py-2.5 text-ink-900">{q.query}</td>
                  <td className="px-4 py-2.5 text-ink-700">{q.category ?? "—"}</td>
                  <td className="px-4 py-2.5">
                    <span
                      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ${
                        q.origin === "manual"
                          ? "bg-ink-100 text-ink-700 ring-ink-200"
                          : q.origin === "suggested"
                          ? "bg-blue-100 text-blue-700 ring-blue-200"
                          : "bg-purple-100 text-purple-700 ring-purple-200"
                      }`}
                    >
                      {q.origin}
                    </span>
                  </td>
                  <td className="px-4 py-2.5">
                    <button
                      type="button"
                      onClick={() =>
                        patchMut.mutate({
                          id: q.id,
                          status: q.status === "active" ? "paused" : "active",
                        })
                      }
                      className={`text-xs font-medium ${
                        q.status === "active" ? "text-emerald-700" : "text-ink-500"
                      }`}
                    >
                      {q.status === "active" ? "● activo" : "○ pausado"}
                    </button>
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    <button
                      type="button"
                      onClick={() => delMut.mutate(q.id)}
                      className="text-xs text-red-700 hover:underline"
                    >
                      eliminar
                    </button>
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

function SuggestionsTab() {
  const qc = useQueryClient();
  const sugg = useQuery<Suggestion[]>({
    queryKey: ["config", "suggestions"],
    queryFn: () => apiRequest<Suggestion[]>("/api/v1/config/suggestions?status=pending&limit=50"),
    refetchInterval: REFRESH_MS,
  });

  const accept = useMutation({
    mutationFn: (id: string) =>
      apiRequest(`/api/v1/config/suggestions/${id}/accept`, {
        method: "POST",
        body: { source: "all" },
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["config", "suggestions"] });
      qc.invalidateQueries({ queryKey: ["config", "queries"] });
    },
  });

  const dismiss = useMutation({
    mutationFn: (id: string) =>
      apiRequest(`/api/v1/config/suggestions/${id}/dismiss`, {
        method: "POST",
        body: { reason: "" },
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["config", "suggestions"] }),
  });

  return (
    <>
      <p className="text-sm text-ink-500">
        Cards generadas por el DiscoveryAgent · revisadas por el CEO antes de tracking.
      </p>

      {sugg.isLoading && (
        <div className="rounded-lg border border-ink-200 bg-white p-12 text-center text-sm text-ink-500">
          Cargando sugerencias…
        </div>
      )}

      {sugg.data && sugg.data.length === 0 && (
        <div
          className="rounded-lg border border-ink-200 bg-white p-12 text-center text-sm text-ink-500"
          data-testid="suggestions-empty"
        >
          Sin sugerencias pendientes · el job corre 06:00 UTC.
        </div>
      )}

      {sugg.data && sugg.data.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2" data-testid="suggestions-list">
          {sugg.data.map((s) => (
            <article
              key={s.id}
              className="flex flex-col gap-3 rounded-lg border border-ink-200 bg-white p-4 shadow-sm"
              data-testid="suggestion-card"
            >
              <div className="flex items-start justify-between gap-2">
                <h3 className="text-sm font-semibold text-ink-900">{s.term}</h3>
                <span
                  className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ${
                    SIGNAL_STYLE[s.signal_type] ?? "bg-ink-100 text-ink-700 ring-ink-200"
                  }`}
                >
                  {s.signal_type}
                </span>
              </div>
              <p className="text-xs text-ink-700">{evidenceText(s)}</p>
              <p className="text-xs text-ink-500">
                Categoría: <code>{s.category}</code> · confianza{" "}
                {(s.confidence * 100).toFixed(0)}%
              </p>
              <div className="flex gap-2 pt-1">
                <button
                  type="button"
                  onClick={() => accept.mutate(s.id)}
                  className="rounded-md bg-brand-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-brand-700"
                >
                  Agregar a mis queries
                </button>
                <button
                  type="button"
                  onClick={() => dismiss.mutate(s.id)}
                  className="rounded-md border border-ink-300 bg-white px-3 py-1.5 text-xs font-medium text-ink-700 hover:bg-ink-50"
                >
                  Descartar
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
    </>
  );
}

export function ConfigQueriesPage() {
  const [tab, setTab] = useState<Tab>("mine");

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-ink-900">Queries e inteligencia</h1>
        <p className="mt-1 text-sm text-ink-500">
          Control manual de queries del Scout + sugerencias automáticas del DiscoveryAgent.
        </p>
      </header>

      <div className="border-b border-ink-200" data-testid="config-tabs">
        <nav className="-mb-px flex gap-6">
          <button
            type="button"
            onClick={() => setTab("mine")}
            className={`border-b-2 px-1 py-2.5 text-sm font-medium ${
              tab === "mine"
                ? "border-brand-500 text-brand-700"
                : "border-transparent text-ink-500 hover:border-ink-300 hover:text-ink-700"
            }`}
          >
            Mis queries
          </button>
          <button
            type="button"
            onClick={() => setTab("suggestions")}
            className={`border-b-2 px-1 py-2.5 text-sm font-medium ${
              tab === "suggestions"
                ? "border-brand-500 text-brand-700"
                : "border-transparent text-ink-500 hover:border-ink-300 hover:text-ink-700"
            }`}
          >
            Sugerencias ARGOS
          </button>
        </nav>
      </div>

      {tab === "mine" ? <MineTab /> : <SuggestionsTab />}
    </div>
  );
}
