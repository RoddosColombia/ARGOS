import { NavLink } from "react-router-dom";

interface NavItem {
  label: string;
  to: string;
  phase: string;
  enabled: boolean;
}

const NAV: NavItem[] = [
  { label: "Marketplace", to: "/marketplace", phase: "Phase 1", enabled: true },
  { label: "Trends & Alertas", to: "/trends", phase: "Phase 1", enabled: true },
  { label: "Competidores", to: "/competitors", phase: "Phase 2", enabled: true },
  { label: "Social Listening", to: "/social", phase: "Phase 2", enabled: true },
  { label: "Briefing", to: "/briefing", phase: "Phase 1", enabled: false },
  { label: "Scoring", to: "/scoring", phase: "Phase 2", enabled: false },
  { label: "WhatsApp", to: "/whatsapp", phase: "Phase 3", enabled: false },
  { label: "Cobranza", to: "/cobranza", phase: "Phase 4", enabled: false },
  { label: "Mantenimiento", to: "/mantenimiento", phase: "Phase 5", enabled: false },
  { label: "Media Buyer", to: "/media-buyer", phase: "Phase 8", enabled: false },
];

export function Sidebar() {
  return (
    <aside className="w-64 shrink-0 border-r border-ink-200 bg-white">
      <div className="flex h-14 items-center gap-2 border-b border-ink-200 px-5">
        <div className="grid size-8 place-items-center rounded-md bg-ink-900 text-brand-500 font-bold">
          A
        </div>
        <div>
          <div className="text-sm font-semibold text-ink-900">ARGOS</div>
          <div className="text-xs text-ink-500">RODDOS · v0.1.0</div>
        </div>
      </div>

      <nav className="p-3">
        <div className="px-2 py-1 text-xs font-semibold uppercase tracking-wider text-ink-500">
          Módulos
        </div>
        <ul className="mt-1 space-y-0.5">
          <li>
            <NavLink
              to="/"
              end
              className={({ isActive }) =>
                `block rounded-md px-3 py-2 text-sm ${
                  isActive
                    ? "bg-brand-50 font-medium text-brand-700"
                    : "text-ink-700 hover:bg-ink-100"
                }`
              }
            >
              Dashboard
            </NavLink>
          </li>

          {NAV.map((item) =>
            item.enabled ? (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  className={({ isActive }) =>
                    `block rounded-md px-3 py-2 text-sm ${
                      isActive
                        ? "bg-brand-50 font-medium text-brand-700"
                        : "text-ink-700 hover:bg-ink-100"
                    }`
                  }
                >
                  {item.label}
                </NavLink>
              </li>
            ) : (
              <li key={item.to}>
                <div
                  className="flex cursor-not-allowed items-center justify-between rounded-md px-3 py-2 text-sm text-ink-500"
                  aria-disabled
                  title={`Disponible en ${item.phase}`}
                >
                  <span>{item.label}</span>
                  <span className="text-xs text-ink-500/70">{item.phase}</span>
                </div>
              </li>
            )
          )}
        </ul>
      </nav>
    </aside>
  );
}
