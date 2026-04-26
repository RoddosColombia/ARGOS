import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { saveSession } from "@/lib/auth";
import { TrendsPage } from "@/pages/TrendsPage";

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <TrendsPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

const KEYWORDS_SAMPLE = [
  {
    workspace_id: "RODDOS",
    keyword: "aceite moto",
    interest_over_time: 85,
    growth_pct_7d: 42.5,
    spike_detected: true,
    vertical: "repuestos-motos",
    updated_at: new Date().toISOString(),
  },
  {
    workspace_id: "RODDOS",
    keyword: "filtro aire moto",
    interest_over_time: 30,
    growth_pct_7d: -5.2,
    spike_detected: false,
    vertical: "repuestos-motos",
    updated_at: new Date().toISOString(),
  },
];

const ALERTS_SAMPLE = [
  {
    event_id: "evt_1",
    timestamp_utc: new Date().toISOString(),
    sku_normalizado: "meli:MCO-1",
    titulo: "Pastillas freno Pulsar 200",
    precio_anterior: 50000,
    precio_actual: 40000,
    delta_pct: -20.0,
    fuente: "meli",
    competitor_url: "https://meli.example/1",
  },
];

function fetchHandler(url: string) {
  if (url.includes("/api/v1/trends/keywords")) {
    return new Response(JSON.stringify(KEYWORDS_SAMPLE), { status: 200 });
  }
  if (url.includes("/api/v1/alerts/recent")) {
    return new Response(JSON.stringify(ALERTS_SAMPLE), { status: 200 });
  }
  return new Response(JSON.stringify({ detail: "not found" }), { status: 404 });
}

describe("TrendsPage", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    saveSession({
      accessToken: "test-jwt",
      workspaceId: "RODDOS",
      role: "ceo",
      expiresAt: Date.now() + 60_000,
    });
    globalThis.fetch = vi.fn().mockImplementation((url: string) =>
      Promise.resolve(fetchHandler(url))
    ) as typeof fetch;
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
    localStorage.clear();
  });

  it("renderiza la tabla de keywords con datos", async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.getByTestId("trends-keywords-table")).toBeInTheDocument();
    });

    const table = screen.getByTestId("trends-keywords-table");
    expect(within(table).getByText("aceite moto")).toBeInTheDocument();
    expect(within(table).getByText("filtro aire moto")).toBeInTheDocument();
    // Spike badge para la primera keyword
    expect(within(table).getByText(/spike/i)).toBeInTheDocument();
  });

  it("renderiza la lista de alertas recientes", async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.getByTestId("alerts-list")).toBeInTheDocument();
    });

    const list = screen.getByTestId("alerts-list");
    expect(within(list).getByText("Pastillas freno Pulsar 200")).toBeInTheDocument();
    expect(within(list).getByText("meli:MCO-1")).toBeInTheDocument();
    expect(within(list).getByText(/-20\.0%/)).toBeInTheDocument();
  });
});
