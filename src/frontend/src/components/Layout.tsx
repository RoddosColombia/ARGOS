import type { ReactNode } from "react";
import { Sidebar } from "@/components/Sidebar";
import { useCurrentUser, useLogout } from "@/hooks/useAuth";

interface Props {
  children: ReactNode;
}

export function Layout({ children }: Props) {
  const { data: user } = useCurrentUser();
  const logout = useLogout();

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 items-center justify-between border-b border-ink-200 bg-white px-6">
          <div className="text-sm text-ink-500">
            Workspace <span className="font-medium text-ink-900">{user?.workspace_id ?? "…"}</span>
          </div>
          <div className="flex items-center gap-4">
            <div className="text-right">
              <div className="text-sm font-medium text-ink-900">{user?.email ?? "Cargando…"}</div>
              <div className="text-xs uppercase tracking-wide text-ink-500">{user?.role ?? ""}</div>
            </div>
            <button
              type="button"
              onClick={logout}
              className="rounded-md border border-ink-200 bg-white px-3 py-1.5 text-sm font-medium text-ink-700 hover:bg-ink-100"
            >
              Salir
            </button>
          </div>
        </header>
        <main className="flex-1 p-8">{children}</main>
      </div>
    </div>
  );
}
