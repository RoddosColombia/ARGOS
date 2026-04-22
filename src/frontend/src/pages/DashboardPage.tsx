import { useCurrentUser } from "@/hooks/useAuth";

interface ModuleCard {
  title: string;
  phase: string;
  description: string;
}

const UPCOMING: ModuleCard[] = [
  { title: "Briefing Matutino", phase: "Phase 1", description: "Morning briefing diario · top acciones aprobables con un tap." },
  { title: "Score Engine", phase: "Phase 2", description: "Motor de calificación crediticia · clon del admin web (ROG-S1)." },
  { title: "WhatsApp Agent", phase: "Phase 3", description: "Frontend conversacional · cotizador visual/voz + KYC + venta." },
  { title: "Cobranza", phase: "Phase 4", description: "RADAR + Wava · Nequi/Daviplata sin fricción." },
  { title: "Mantenimiento predictivo", phase: "Phase 5", description: "Job semanal · conversión proactiva > 12%." },
  { title: "Media Buyer", phase: "Phase 8", description: "Pauta Meta + Google + CTW Ads con Compliance Officer." },
];

export function DashboardPage() {
  const { data: user, isLoading, isError } = useCurrentUser();

  return (
    <div className="mx-auto max-w-5xl space-y-8">
      <section>
        <h1 className="text-2xl font-semibold text-ink-900">
          {isLoading ? "Cargando…" : isError ? "Sesión inválida" : `Bienvenido, ${user?.email}`}
        </h1>
        <p className="mt-1 text-sm text-ink-500">
          Este es el dashboard interno de ARGOS. Phase 0 está en curso — los módulos funcionales se activan en phases siguientes.
        </p>
      </section>

      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-ink-500">
          Próximos módulos
        </h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {UPCOMING.map((m) => (
            <div
              key={m.title}
              className="rounded-lg border border-ink-200 bg-white p-4 shadow-sm"
            >
              <div className="flex items-start justify-between gap-2">
                <h3 className="text-sm font-semibold text-ink-900">{m.title}</h3>
                <span className="rounded-full bg-ink-100 px-2 py-0.5 text-xs font-medium text-ink-700">
                  {m.phase}
                </span>
              </div>
              <p className="mt-2 text-xs leading-relaxed text-ink-500">{m.description}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="rounded-lg border border-ink-200 bg-white p-5 shadow-sm">
        <h2 className="text-sm font-semibold text-ink-900">Estado de Phase 0</h2>
        <ul className="mt-2 space-y-1 text-xs text-ink-500">
          <li>✅ Build 0.1 · Repo scaffold</li>
          <li>✅ Build 0.2 · FastAPI + JWT + /health</li>
          <li>✅ Build 0.3 · MongoDB + colecciones + seed</li>
          <li>🛠️ Build 0.4 · Frontend base (en curso)</li>
          <li>⬜ Build 0.5 · CI/CD + autodeploy Render</li>
          <li>⬜ Build 0.6 · Dominio argos.roddos.com + SSL</li>
          <li>⬜ Build 0.7 · Langfuse self-hosted</li>
          <li>⬜ Build 0.8 · Credenciales BM/MCC ARGOS</li>
          <li>⬜ Build 0.9 · Baseline operativo</li>
        </ul>
      </section>
    </div>
  );
}
