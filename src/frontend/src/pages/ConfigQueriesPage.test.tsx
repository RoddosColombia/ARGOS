import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { saveSession } from "@/lib/auth";
import { ConfigQueriesPage } from "@/pages/ConfigQueriesPage";

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <ConfigQueriesPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

const QUERIES = [
  {
    id: "q1",
    query: "aceite moto",
    category: "repuestos_moto",
    origin: "manual",
    status: "active",
    priority: 1,
    source: "all",
    created_at: "2026-04-01T07:00:00Z",
  },
  {
    id: "q2",
    query: "casco modular smart",
    category: "accesorios_moto",
    origin: "suggested",
    status: "paused",
    priority: 2,
    source: "all",
    created_at: "2026-04-20T07:00:00Z",
  },
];

const CATEGORIES = [
  { slug: "repuestos_moto", label: "Repuestos para moto", active: true },
  { slug: "accesorios_moto", label: "Accesorios para moto", active: false },
];

const SUGGESTIONS = [
  {
    id: "s1",
    term: "kit arrastre 428H",
    category: "repuestos_moto",
    signal_type: "rising",
    confidence: 0.78,
    evidence: { metric: "new_listings_48h", value: 14, delta_pct: 60 },
    date: "2026-04-26",
    status: "pending",
  },
];

describe("ConfigQueriesPage", () => {
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

  it("renderiza tabla de queries con badges origin · cambia tab a sugerencias", async () => {
    globalThis.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/config/queries")) {
        return new Response(JSON.stringify(QUERIES), { status: 200 });
      }
      if (url.includes("/config/categories")) {
        return new Response(JSON.stringify(CATEGORIES), { status: 200 });
      }
      if (url.includes("/config/suggestions")) {
        return new Response(JSON.stringify(SUGGESTIONS), { status: 200 });
      }
      return new Response(JSON.stringify({}), { status: 200 });
    }) as typeof fetch;

    renderPage();

    await waitFor(() => {
      expect(screen.getByTestId("queries-table")).toBeInTheDocument();
    });
    const table = screen.getByTestId("queries-table");
    expect(within(table).getAllByTestId("query-row")).toHaveLength(2);
    expect(within(table).getByText("aceite moto")).toBeInTheDocument();
    expect(within(table).getByText("manual")).toBeInTheDocument();
    expect(within(table).getByText("suggested")).toBeInTheDocument();

    // Cambia a tab Sugerencias
    fireEvent.click(screen.getByRole("button", { name: /Sugerencias ARGOS/ }));

    await waitFor(() => {
      expect(screen.getByTestId("suggestions-list")).toBeInTheDocument();
    });
    const cards = screen.getAllByTestId("suggestion-card");
    expect(cards).toHaveLength(1);
    expect(screen.getByText("kit arrastre 428H")).toBeInTheDocument();
    expect(screen.getByText("rising")).toBeInTheDocument();
    expect(screen.getByText(/14 nuevas publicaciones/)).toBeInTheDocument();
  });
});
