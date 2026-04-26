import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { saveSession } from "@/lib/auth";
import { BriefingPage } from "@/pages/BriefingPage";

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <BriefingPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

const SAMPLE = {
  id: "doc-1",
  fecha: "2026-04-26",
  mercado_24h: { nuevos_skus: 5, bajas_precio: 2, nuevas_promos: 1 },
  acciones_del_dia: [
    {
      accion: "Bajar precio de Aceite Motul a $52K",
      justificacion: "3 sellers MELI bajaron 22%",
      impacto_esperado: "Recuperar share en aceites",
      prioridad: "Alta",
    },
    {
      accion: "Activar mensaje WhatsApp F6 a clientes con cupón -10%",
      justificacion: "Cohort de mototaxistas cambia aceite cada 4-5 semanas",
      impacto_esperado: "50-80 unidades vendidas en 48h",
      prioridad: "Media",
    },
    {
      accion: "Revisar inventario de pastillas freno",
      justificacion: "Lunes pico histórico",
      impacto_esperado: "Evitar stockout",
      prioridad: "Baja",
    },
  ],
  estado_mercado: "Día agresivo en aceites · respuesta competitiva requerida hoy.",
  modelo_usado: "claude-sonnet-4-6-20260301",
  tokens_input: 2400,
  tokens_output: 580,
  created_at: new Date().toISOString(),
};

describe("BriefingPage", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    saveSession({
      accessToken: "test-jwt",
      workspaceId: "RODDOS",
      role: "ceo",
      expiresAt: Date.now() + 60_000,
    });
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
    localStorage.clear();
  });

  it("renderiza las 3 secciones (mercado, acciones con prioridad, estado mercado)", async () => {
    globalThis.fetch = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify(SAMPLE), { status: 200 })) as typeof fetch;

    renderPage();

    await waitFor(() => {
      expect(screen.getByTestId("mercado-grid")).toBeInTheDocument();
    });

    // Mercado 24h · 3 metric cards
    const mercado = screen.getByTestId("mercado-grid");
    const cards = within(mercado).getAllByTestId("metric-card");
    expect(cards).toHaveLength(3);
    expect(within(mercado).getByText("5")).toBeInTheDocument();
    expect(within(mercado).getByText("2")).toBeInTheDocument();
    expect(within(mercado).getByText("1")).toBeInTheDocument();

    // 3 Acciones · cada una con prioridad badge
    const acciones = screen.getByTestId("acciones-list");
    const accionCards = within(acciones).getAllByTestId("accion-card");
    expect(accionCards).toHaveLength(3);
    expect(within(acciones).getByText(/Bajar precio de Aceite Motul/)).toBeInTheDocument();
    expect(within(acciones).getByText("Alta")).toBeInTheDocument();
    expect(within(acciones).getByText("Media")).toBeInTheDocument();
    expect(within(acciones).getByText("Baja")).toBeInTheDocument();

    // Estado del mercado
    const estado = screen.getByTestId("estado-mercado");
    expect(within(estado).getByText(/Día agresivo en aceites/)).toBeInTheDocument();
  });

  it("muestra empty state cuando el endpoint devuelve 404", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "Sin briefing para 2026-04-26" }), { status: 404 })
    ) as typeof fetch;

    renderPage();

    await waitFor(() => {
      expect(screen.getByTestId("briefing-empty-state")).toBeInTheDocument();
    });
    const empty = screen.getByTestId("briefing-empty-state");
    expect(within(empty).getByText(/Sin briefing del día/)).toBeInTheDocument();
    expect(within(empty).getByText(/06:45 UTC/)).toBeInTheDocument();
  });
});
