import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { saveSession } from "@/lib/auth";
import { MarketplacePage } from "@/pages/MarketplacePage";

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <MarketplacePage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

const SAMPLE = [
  {
    sku_normalizado: "meli:MCO-1",
    titulo: "Aceite Motul 4T 20W50",
    precio_actual: 45000,
    precio_promedio: 43000,
    fuente: "meli",
    cambio_precio_pct: 4.6,
    ultima_actualizacion: new Date().toISOString(),
    permalink: "https://meli.example/1",
  },
  {
    sku_normalizado: "fb_marketplace:FB-9",
    titulo: "Pastillas freno Pulsar 200",
    precio_actual: 50000,
    precio_promedio: 52000,
    fuente: "fb",
    cambio_precio_pct: -3.8,
    ultima_actualizacion: new Date().toISOString(),
    permalink: "https://fb.example/9",
  },
];

describe("MarketplacePage", () => {
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

  it("renderiza la tabla con datos de top-products", async () => {
    globalThis.fetch = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify(SAMPLE), { status: 200 })) as typeof fetch;

    renderPage();

    await waitFor(() => {
      expect(screen.getByTestId("marketplace-table")).toBeInTheDocument();
    });

    const table = screen.getByTestId("marketplace-table");
    expect(within(table).getByText("Aceite Motul 4T 20W50")).toBeInTheDocument();
    expect(within(table).getByText("Pastillas freno Pulsar 200")).toBeInTheDocument();
    // Badges dentro de la tabla · "MercadoLibre" también aparece en el <option> del dropdown
    expect(within(table).getByText("MercadoLibre")).toBeInTheDocument();
    expect(within(table).getByText("FB Marketplace")).toBeInTheDocument();
  });

  it("cambia el query param source al cambiar el filtro", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify([]), { status: 200 }));
    globalThis.fetch = fetchMock as typeof fetch;

    renderPage();

    // Espera a que el primer fetch (source=all) ocurra
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });
    const firstUrl = fetchMock.mock.calls[0][0] as string;
    expect(firstUrl).toContain("source=all");

    const select = screen.getByLabelText(/fuente/i) as HTMLSelectElement;
    const user = userEvent.setup();
    await user.selectOptions(select, "meli");

    await waitFor(() => {
      const lastCall = fetchMock.mock.calls[fetchMock.mock.calls.length - 1];
      const url = lastCall[0] as string;
      expect(url).toContain("source=meli");
    });
  });
});
