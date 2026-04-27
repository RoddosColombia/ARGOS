import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { apiRequest } from "@/lib/api";
import type {
  Decision,
  Producto,
  ScoreComportamental,
  ScoreResult,
  ScoreSolicitudRequest,
  SolicitudListItem,
  TipoEmpleo,
  UsoMoto,
} from "@/types/scoring";

const COP = new Intl.NumberFormat("es-CO", {
  style: "currency",
  currency: "COP",
  maximumFractionDigits: 0,
});

const DECISION_STYLE: Record<Decision, string> = {
  aprobado: "bg-emerald-100 text-emerald-700 ring-emerald-200",
  rechazado: "bg-red-100 text-red-700 ring-red-200",
  rechazado_regla_dura: "bg-red-100 text-red-800 ring-red-300",
  revision_manual: "bg-amber-100 text-amber-800 ring-amber-200",
};

type Tab = "evaluate" | "history";

const DEFAULT_FORM: ScoreSolicitudRequest = {
  producto: "credito_rodante",
  cedula: "",
  nombre: "",
  ingreso_declarado: 2_500_000,
  gastos_mensuales: 1_500_000,
  tipo_empleo: "delivery",
  uso_moto: "trabajo",
  score_comportamental: null,
  monto_solicitado: 800_000,
};

function ResultCard({ result }: { result: ScoreResult }) {
  return (
    <article
      className="rounded-lg border border-ink-200 bg-white p-6 shadow-sm"
      data-testid="score-result"
    >
      <div className="flex items-baseline justify-between gap-3">
        <div>
          <div className="text-xs uppercase tracking-wider text-ink-500">Score final</div>
          <div className="mt-1 text-5xl font-bold tabular-nums text-ink-900" data-testid="score-final">
            {result.score_final}
          </div>
          <div className="mt-1 text-xs text-ink-500">
            umbral aplicado: {result.threshold_aplicado}
          </div>
        </div>
        <span
          className={`inline-flex items-center rounded-full px-3 py-1 text-sm font-semibold ring-1 ${
            DECISION_STYLE[result.decision]
          }`}
          data-testid="score-decision"
        >
          {result.decision}
        </span>
      </div>

      {result.regla_dura_aplicada && (
        <div className="mt-4 rounded-md bg-red-50 p-3 text-sm text-red-800">
          ⛔ Rechazo automático por regla dura: <code>{result.regla_dura_aplicada}</code>
        </div>
      )}

      <div className="mt-4 grid gap-3 sm:grid-cols-3 text-xs text-ink-700">
        <div>
          <div className="text-ink-500">score_modelo</div>
          <div className="text-base font-semibold tabular-nums">{result.score_modelo.toFixed(3)}</div>
        </div>
        <div>
          <div className="text-ink-500">delta_claude</div>
          <div className="text-base font-semibold tabular-nums">
            {result.delta_claude >= 0 ? "+" : ""}
            {result.delta_claude.toFixed(3)}
          </div>
        </div>
        <div>
          <div className="text-ink-500">score_claude</div>
          <div className="text-base font-semibold tabular-nums">{result.score_claude.toFixed(3)}</div>
        </div>
      </div>

      {result.narrativa && (
        <p
          className="mt-4 rounded-md bg-ink-50 p-3 text-sm italic leading-relaxed text-ink-700"
          data-testid="score-narrativa"
        >
          💡 {result.narrativa}
        </p>
      )}

      <p className="mt-3 text-xs text-ink-500">
        engine: <code>{result.engine_version}</code> · solicitud: <code>{result.solicitud_id}</code>
      </p>
    </article>
  );
}

function EvaluateTab() {
  const [form, setForm] = useState<ScoreSolicitudRequest>(DEFAULT_FORM);
  const [result, setResult] = useState<ScoreResult | null>(null);
  const qc = useQueryClient();

  const mut = useMutation({
    mutationFn: (b: ScoreSolicitudRequest) =>
      apiRequest<ScoreResult>("/api/v1/score/evaluate", { method: "POST", body: b }),
    onSuccess: (data) => {
      setResult(data);
      qc.invalidateQueries({ queryKey: ["score", "solicitudes"] });
    },
  });

  const update = <K extends keyof ScoreSolicitudRequest>(key: K, value: ScoreSolicitudRequest[K]) =>
    setForm((f) => ({ ...f, [key]: value }));

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <form
        className="space-y-3 rounded-lg border border-ink-200 bg-white p-5 shadow-sm"
        data-testid="score-form"
        onSubmit={(e) => {
          e.preventDefault();
          mut.mutate(form);
        }}
      >
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="text-xs text-ink-500">
            Producto
            <select
              value={form.producto}
              onChange={(e) => update("producto", e.target.value as Producto)}
              className="mt-1 block w-full rounded-md border border-ink-300 px-3 py-1.5 text-sm"
            >
              <option value="credito_rodante">Crédito Rodante (repuestos)</option>
              <option value="credito_rdx_leasing">RDX Leasing (moto)</option>
            </select>
          </label>
          <label className="text-xs text-ink-500">
            Score comportamental
            <select
              value={form.score_comportamental ?? ""}
              onChange={(e) =>
                update(
                  "score_comportamental",
                  (e.target.value || null) as ScoreComportamental | null,
                )
              }
              className="mt-1 block w-full rounded-md border border-ink-300 px-3 py-1.5 text-sm"
            >
              <option value="">— cliente nuevo —</option>
              <option value="A+">A+</option>
              <option value="A">A</option>
              <option value="B">B</option>
              <option value="C">C</option>
              <option value="D">D</option>
              <option value="E">E</option>
            </select>
          </label>
        </div>

        <label className="block text-xs text-ink-500">
          Nombre
          <input
            type="text"
            value={form.nombre}
            onChange={(e) => update("nombre", e.target.value)}
            placeholder="ej. Andrés San Juan"
            required
            minLength={2}
            className="mt-1 block w-full rounded-md border border-ink-300 px-3 py-1.5 text-sm"
          />
        </label>

        <label className="block text-xs text-ink-500">
          Cédula
          <input
            type="text"
            value={form.cedula}
            onChange={(e) => update("cedula", e.target.value)}
            placeholder="ej. 80075452"
            required
            minLength={4}
            className="mt-1 block w-full rounded-md border border-ink-300 px-3 py-1.5 text-sm"
          />
        </label>

        <div className="grid gap-3 sm:grid-cols-2">
          <label className="text-xs text-ink-500">
            Ingreso declarado (COP)
            <input
              type="number"
              value={form.ingreso_declarado}
              onChange={(e) => update("ingreso_declarado", Number(e.target.value))}
              className="mt-1 block w-full rounded-md border border-ink-300 px-3 py-1.5 text-sm"
            />
          </label>
          <label className="text-xs text-ink-500">
            Gastos mensuales (COP)
            <input
              type="number"
              value={form.gastos_mensuales}
              onChange={(e) => update("gastos_mensuales", Number(e.target.value))}
              className="mt-1 block w-full rounded-md border border-ink-300 px-3 py-1.5 text-sm"
            />
          </label>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <label className="text-xs text-ink-500">
            Tipo empleo
            <select
              value={form.tipo_empleo}
              onChange={(e) => update("tipo_empleo", e.target.value as TipoEmpleo)}
              className="mt-1 block w-full rounded-md border border-ink-300 px-3 py-1.5 text-sm"
            >
              <option value="empleado">Empleado</option>
              <option value="independiente">Independiente</option>
              <option value="delivery">Delivery</option>
              <option value="mototaxi">Mototaxi</option>
            </select>
          </label>
          <label className="text-xs text-ink-500">
            Uso moto
            <select
              value={form.uso_moto}
              onChange={(e) => update("uso_moto", e.target.value as UsoMoto)}
              className="mt-1 block w-full rounded-md border border-ink-300 px-3 py-1.5 text-sm"
            >
              <option value="personal">Personal</option>
              <option value="trabajo">Trabajo</option>
              <option value="ambos">Ambos</option>
            </select>
          </label>
        </div>

        <label className="block text-xs text-ink-500">
          Monto solicitado (COP)
          <input
            type="number"
            value={form.monto_solicitado}
            onChange={(e) => update("monto_solicitado", Number(e.target.value))}
            className="mt-1 block w-full rounded-md border border-ink-300 px-3 py-1.5 text-sm"
          />
        </label>

        <button
          type="submit"
          disabled={mut.isPending || form.cedula.length < 4 || form.nombre.length < 2}
          className="w-full rounded-md bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
        >
          {mut.isPending ? "Evaluando…" : "Evaluar"}
        </button>

        {mut.isError && (
          <div className="rounded-md bg-red-50 p-3 text-xs text-red-700">
            Error: {(mut.error as Error).message}
          </div>
        )}
      </form>

      <div>
        {result ? (
          <ResultCard result={result} />
        ) : (
          <div className="rounded-lg border border-dashed border-ink-200 bg-white p-12 text-center text-sm text-ink-500">
            Completa el formulario y presiona <strong>Evaluar</strong>.
          </div>
        )}
      </div>
    </div>
  );
}

function HistoryTab() {
  const list = useQuery<SolicitudListItem[]>({
    queryKey: ["score", "solicitudes"],
    queryFn: () => apiRequest<SolicitudListItem[]>("/api/v1/score/solicitudes?limit=20"),
    refetchInterval: 60_000,
  });

  return (
    <>
      {list.isLoading && (
        <div className="rounded-lg border border-ink-200 bg-white p-12 text-center text-sm text-ink-500">
          Cargando historial…
        </div>
      )}
      {list.data && list.data.length === 0 && (
        <div
          className="rounded-lg border border-ink-200 bg-white p-12 text-center text-sm text-ink-500"
          data-testid="history-empty"
        >
          Sin solicitudes evaluadas todavía.
        </div>
      )}
      {list.data && list.data.length > 0 && (
        <div
          className="overflow-hidden rounded-lg border border-ink-200 bg-white shadow-sm"
          data-testid="history-table-wrapper"
        >
          <table className="w-full text-left text-sm" data-testid="history-table">
            <thead className="bg-ink-50 text-xs uppercase tracking-wider text-ink-500">
              <tr>
                <th className="px-4 py-2.5">Solicitud</th>
                <th className="px-4 py-2.5">Producto</th>
                <th className="px-4 py-2.5 text-right">Monto</th>
                <th className="px-4 py-2.5 text-right">Score</th>
                <th className="px-4 py-2.5">Decisión</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ink-100">
              {list.data.map((s) => (
                <tr key={s.id} data-testid="history-row">
                  <td className="px-4 py-2.5 font-mono text-xs text-ink-900">{s.solicitud_id}</td>
                  <td className="px-4 py-2.5 text-ink-700">{s.producto}</td>
                  <td className="px-4 py-2.5 text-right tabular-nums text-ink-700">
                    {COP.format(s.monto_solicitado)}
                  </td>
                  <td className="px-4 py-2.5 text-right tabular-nums font-semibold">
                    {s.score_final}
                  </td>
                  <td className="px-4 py-2.5">
                    <span
                      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ${
                        DECISION_STYLE[s.decision]
                      }`}
                    >
                      {s.decision}
                    </span>
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

export function ScoringPage() {
  const [tab, setTab] = useState<Tab>("evaluate");

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-ink-900">Score Engine</h1>
        <p className="mt-1 text-sm text-ink-500">
          Motor crediticio interno · clon del Build 20 · ROG-S1 a S6.
        </p>
      </header>

      <div className="border-b border-ink-200" data-testid="scoring-tabs">
        <nav className="-mb-px flex gap-6">
          <button
            type="button"
            onClick={() => setTab("evaluate")}
            className={`border-b-2 px-1 py-2.5 text-sm font-medium ${
              tab === "evaluate"
                ? "border-brand-500 text-brand-700"
                : "border-transparent text-ink-500 hover:border-ink-300 hover:text-ink-700"
            }`}
          >
            Evaluar
          </button>
          <button
            type="button"
            onClick={() => setTab("history")}
            className={`border-b-2 px-1 py-2.5 text-sm font-medium ${
              tab === "history"
                ? "border-brand-500 text-brand-700"
                : "border-transparent text-ink-500 hover:border-ink-300 hover:text-ink-700"
            }`}
          >
            Historial
          </button>
        </nav>
      </div>

      {tab === "evaluate" ? <EvaluateTab /> : <HistoryTab />}
    </div>
  );
}
