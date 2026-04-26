import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { saveSession } from "@/lib/auth";
import { CompetitorsPage } from "@/pages/CompetitorsPage";

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <CompetitorsPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

const SAMPLE = [
  {
    id: "doc-1",
    plataforma: "meta",
    ad_id_externo: "ARCHIVE-1",
    anunciante: "Repuestos Bogotá Online",
    copy_texto: "Las mejores pastillas freno con envío gratis a toda Colombia",
    copy_titulo: "Pastillas freno Pulsar · 30% off",
    url_landing: "https://repuestos-bogota.com/pastillas",
    fecha_inicio: new Date(Date.now() - 5 * 86400_000).toISOString(),
    durabilidad_dias: 5,
    formato: "video",
    activo: true,
    fuente_query: "pastillas freno moto",
    keywords_pautadas: ["pastillas freno moto"],
  },
  {
    id: "doc-2",
    plataforma: "google",
    ad_id_externo: "G-CREATIVE-2",
    anunciante: "Motos & Repuestos JR",
    copy_texto: "Aceite Motul 4T 20W50 a domicilio",
    copy_titulo: "",
    url_landing: "https://example.com/aceite",
    fecha_inicio: new Date(Date.now() - 30 * 86400_000).toISOString(),
    durabilidad_dias: 30,
    formato: "image",
    activo: false,
    fuente_query: "aceite moto",
    keywords_pautadas: ["aceite moto", "aceite Motul"],
  },
];

describe("CompetitorsPage", () => {
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

  it("renderiza la tabla con anunciante, formato y estado activo/pausado", async () => {
    globalThis.fetch = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify(SAMPLE), { status: 200 })) as typeof fetch;

    renderPage();

    await waitFor(() => {
      expect(screen.getByTestId("competitors-ads-table")).toBeInTheDocument();
    });

    const table = screen.getByTestId("competitors-ads-table");
    expect(within(table).getByText("Repuestos Bogotá Online")).toBeInTheDocument();
    expect(within(table).getByText("Motos & Repuestos JR")).toBeInTheDocument();
    expect(within(table).getByText("video")).toBeInTheDocument();
    expect(within(table).getByText("image")).toBeInTheDocument();
    // Plataforma badges · ambas en la tabla
    expect(within(table).getByText("Meta")).toBeInTheDocument();
    expect(within(table).getByText("Google")).toBeInTheDocument();
    // Activo y pausado badges (texto exacto · "Días activo" del header se ignora)
    expect(within(table).getByText(/🟢 activo/)).toBeInTheDocument();
    expect(within(table).getByText(/⚪ pausado/)).toBeInTheDocument();
  });

  it("toggle 'Solo activos' agrega only_active=true al query param", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify([]), { status: 200 })
    );
    globalThis.fetch = fetchMock as typeof fetch;

    renderPage();

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const firstUrl = fetchMock.mock.calls[0][0] as string;
    expect(firstUrl).toContain("only_active=false");
    expect(firstUrl).toContain("source=all");

    const checkbox = screen.getByTestId("only-active-checkbox");
    await userEvent.setup().click(checkbox);

    await waitFor(() => {
      const lastUrl = fetchMock.mock.calls[fetchMock.mock.calls.length - 1][0] as string;
      expect(lastUrl).toContain("only_active=true");
    });
  });

  it("filtro por fuente cambia el source del query param", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify([]), { status: 200 })
    );
    globalThis.fetch = fetchMock as typeof fetch;

    renderPage();

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const firstUrl = fetchMock.mock.calls[0][0] as string;
    expect(firstUrl).toContain("source=all");

    const select = screen.getByLabelText(/fuente/i) as HTMLSelectElement;
    await userEvent.setup().selectOptions(select, "google");

    await waitFor(() => {
      const lastUrl = fetchMock.mock.calls[fetchMock.mock.calls.length - 1][0] as string;
      expect(lastUrl).toContain("source=google");
    });

    await userEvent.setup().selectOptions(select, "meta");
    await waitFor(() => {
      const lastUrl = fetchMock.mock.calls[fetchMock.mock.calls.length - 1][0] as string;
      expect(lastUrl).toContain("source=meta");
    });
  });
});
