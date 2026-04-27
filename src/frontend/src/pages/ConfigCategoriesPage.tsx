import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { apiRequest } from "@/lib/api";
import type { Category } from "@/types/config";

export function ConfigCategoriesPage() {
  const qc = useQueryClient();
  const [reqLabel, setReqLabel] = useState("");
  const [reqNote, setReqNote] = useState("");
  const [requested, setRequested] = useState(false);

  const cats = useQuery<Category[]>({
    queryKey: ["config", "categories"],
    queryFn: () => apiRequest<Category[]>("/api/v1/config/categories"),
  });

  const toggle = useMutation({
    mutationFn: (vars: { slug: string; active: boolean }) =>
      apiRequest<Category>(`/api/v1/config/categories/${vars.slug}`, {
        method: "PATCH",
        body: { active: vars.active },
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["config", "categories"] }),
  });

  const requestNew = useMutation({
    mutationFn: (b: { label: string; note: string }) =>
      apiRequest("/api/v1/config/categories/request", { method: "POST", body: b }),
    onSuccess: () => {
      setRequested(true);
      setReqLabel("");
      setReqNote("");
    },
  });

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-ink-900">Categorías</h1>
        <p className="mt-1 text-sm text-ink-500">
          Activa o desactiva las verticales que ARGOS rastrea. Cada categoría activa
          dispara discovery_job diariamente.
        </p>
      </header>

      <ul className="divide-y divide-ink-200 rounded-lg border border-ink-200 bg-white shadow-sm">
        {cats.data?.map((c) => (
          <li key={c.slug} className="flex items-center justify-between px-4 py-3" data-testid="category-row">
            <div>
              <div className="text-sm font-medium text-ink-900">{c.label}</div>
              <div className="text-xs text-ink-500"><code>{c.slug}</code></div>
            </div>
            <button
              type="button"
              onClick={() => toggle.mutate({ slug: c.slug, active: !c.active })}
              disabled={toggle.isPending}
              className={`rounded-md px-3 py-1.5 text-xs font-medium ring-1 ${
                c.active
                  ? "bg-emerald-50 text-emerald-700 ring-emerald-200"
                  : "bg-white text-ink-500 ring-ink-200 hover:bg-ink-50"
              }`}
            >
              {c.active ? "✓ activa" : "○ inactiva"}
            </button>
          </li>
        ))}
      </ul>

      <section className="rounded-lg border border-ink-200 bg-white p-5 shadow-sm">
        <h2 className="text-sm font-semibold text-ink-900">Solicitar nueva categoría</h2>
        <p className="mt-1 text-xs text-ink-500">
          Emite el evento <code>config.category.requested</code> al bus · el equipo de ARGOS la habilitará.
        </p>
        {requested && (
          <p className="mt-2 text-xs text-emerald-700" data-testid="request-confirmation">
            ✓ Solicitud enviada.
          </p>
        )}
        <div className="mt-3 grid gap-2 sm:grid-cols-[1fr_2fr_auto] sm:items-end">
          <input
            type="text"
            value={reqLabel}
            onChange={(e) => setReqLabel(e.target.value)}
            placeholder="ej. Cascos"
            className="rounded-md border border-ink-300 px-3 py-1.5 text-sm"
          />
          <input
            type="text"
            value={reqNote}
            onChange={(e) => setReqNote(e.target.value)}
            placeholder="Nota opcional · contexto"
            className="rounded-md border border-ink-300 px-3 py-1.5 text-sm"
          />
          <button
            type="button"
            onClick={() => requestNew.mutate({ label: reqLabel, note: reqNote })}
            disabled={reqLabel.length < 2 || requestNew.isPending}
            className="rounded-md bg-brand-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
          >
            {requestNew.isPending ? "Enviando…" : "Solicitar"}
          </button>
        </div>
      </section>
    </div>
  );
}
