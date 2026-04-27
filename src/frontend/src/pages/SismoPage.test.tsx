import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { saveSession } from "@/lib/auth";
import { SismoPage } from "@/pages/SismoPage";

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <SismoPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

const ALL = {
  fecha_sync_date: "2026-04-26",
  type: "all",
  total: 2,
  items: [
    {
      sku: "FRENO-001",
      nombre: "Pastilla freno Pulsar",
      stock: 24,
      precio: 45000,
      costo: 28000,
      dias_inventario: 12,
      is_slow_mover: false,
      fecha_sync_date: "2026-04-26",
      fecha_sync: "2026-04-26T07:00:00Z",
    },
    {
      sku: "ACEITE-002",
      nombre: "Aceite Motul 4T",
      stock: 8,
      precio: 52000,
      costo: 36000,
      dias_inventario: 60,
      is_slow_mover: true,
      fecha_sync_date: "2026-04-26",
      fecha_sync: "2026-04-26T07:00:00Z",
    },
  ],
};

const SLOW = {
  fecha_sync_date: "2026-04-26",
  type: "slow_movers",
  total: 1,
  items: [ALL.items[1]],
};

describe("SismoPage", () => {
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

  it("renderiza tabla con SKU, stock y badge slow mover · cambia filtro a slow_movers", async () => {
    globalThis.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      const body = url.includes("type=slow_movers") ? SLOW : ALL;
      return new Response(JSON.stringify(body), { status: 200 });
    }) as typeof fetch;

    renderPage();

    await waitFor(() => {
      expect(screen.getByTestId("sismo-table")).toBeInTheDocument();
    });
    const table = screen.getByTestId("sismo-table");
    expect(within(table).getAllByTestId("sismo-row")).toHaveLength(2);
    expect(within(table).getByText("FRENO-001")).toBeInTheDocument();
    expect(within(table).getByText("ACEITE-002")).toBeInTheDocument();
    expect(within(table).getByText("slow mover")).toBeInTheDocument();

    // Click filtro slow_movers
    fireEvent.click(screen.getByRole("button", { name: /Slow movers/ }));

    await waitFor(() => {
      const tbl = screen.getByTestId("sismo-table");
      expect(within(tbl).getAllByTestId("sismo-row")).toHaveLength(1);
    });
    const t2 = screen.getByTestId("sismo-table");
    expect(within(t2).getByText("ACEITE-002")).toBeInTheDocument();
    expect(within(t2).queryByText("FRENO-001")).not.toBeInTheDocument();
  });

  it("tab Ventas renderiza totales + tabla de ventas", async () => {
    const SALES = {
      date: "2026-04-25",
      sku: null,
      items: [
        {
          sku: "FRENO-001",
          date: "2026-04-25",
          units_sold: 5,
          revenue: 225000,
          channel: "tienda",
          fecha_sync: "2026-04-26T01:00:00Z",
        },
        {
          sku: "ACEITE-002",
          date: "2026-04-25",
          units_sold: 3,
          revenue: 156000,
          channel: "whatsapp",
          fecha_sync: "2026-04-26T01:00:00Z",
        },
      ],
      totals: { units_sold: 8, revenue_cop: 381000, count: 2 },
    };

    globalThis.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/sismo/sales")) {
        return new Response(JSON.stringify(SALES), { status: 200 });
      }
      return new Response(JSON.stringify(ALL), { status: 200 });
    }) as typeof fetch;

    renderPage();

    // Cambiar a tab Ventas
    fireEvent.click(screen.getByRole("button", { name: /^Ventas$/ }));

    await waitFor(() => {
      expect(screen.getByTestId("sales-table")).toBeInTheDocument();
    });
    const totals = screen.getByTestId("sales-totals");
    expect(within(totals).getByText("2026-04-25")).toBeInTheDocument();
    expect(within(totals).getByText("8")).toBeInTheDocument();

    const table = screen.getByTestId("sales-table");
    expect(within(table).getAllByTestId("sales-row")).toHaveLength(2);
    expect(within(table).getByText("FRENO-001")).toBeInTheDocument();
    expect(within(table).getByText("whatsapp")).toBeInTheDocument();
  });
});
