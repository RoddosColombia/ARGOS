import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { saveSession } from "@/lib/auth";
import { RecommendationsPage } from "@/pages/RecommendationsPage";

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <RecommendationsPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

const HIT_RATE = { days: 30, evaluated_count: 4, avg_hit_rate: 0.75 };

const SAMPLE: Array<Record<string, unknown>> = [
  {
    id: "rec-1",
    type: "pricing_change",
    action_description: "Bajar precio de Aceite Motul a $52K",
    rationale: "3 sellers MELI bajaron 22%",
    priority: "Alta",
    priority_score: 0.9,
    expected_impact: { metric: "qualitative", target: "Recuperar share en aceites", confidence: 0.7 },
    actual_impact: null,
    hit_rate_contribution: null,
    learning: null,
    status: "pendiente",
    approved_by: null,
    approved_at: null,
    executed_at: null,
    fecha_briefing: "2026-04-26",
    shown_in_briefing: ["2026-04-26"],
    created_at: "2026-04-26T07:00:00Z",
  },
  {
    id: "rec-2",
    type: "promo_launch",
    action_description: "Activar campaña WhatsApp F6 con cupón -10%",
    rationale: "Cohort de mototaxistas",
    priority: "Media",
    priority_score: 0.6,
    expected_impact: { metric: "qualitative", target: "50 unidades", confidence: 0.5 },
    actual_impact: null,
    hit_rate_contribution: 1.0,
    learning: "Funcionó por timing de cohort",
    status: "evaluada",
    approved_by: "andres@roddos.com",
    approved_at: "2026-04-19T07:30:00Z",
    executed_at: "2026-04-19T08:00:00Z",
    fecha_briefing: "2026-04-19",
    shown_in_briefing: ["2026-04-19"],
    created_at: "2026-04-19T07:00:00Z",
  },
];

describe("RecommendationsPage", () => {
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

  function mockFetch(handler: (url: string, init?: RequestInit) => Response) {
    globalThis.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      return handler(url, init);
    }) as typeof fetch;
  }

  it("renderiza hit-rate widget + lista de recomendaciones", async () => {
    mockFetch((url) => {
      if (url.includes("/hit-rate")) {
        return new Response(JSON.stringify(HIT_RATE), { status: 200 });
      }
      return new Response(JSON.stringify(SAMPLE), { status: 200 });
    });

    renderPage();

    await waitFor(() => {
      expect(screen.getByTestId("hit-rate-widget")).toBeInTheDocument();
    });
    const widget = screen.getByTestId("hit-rate-widget");
    await waitFor(() => {
      expect(within(widget).getByText(/4 recomendaciones evaluadas/)).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(screen.getByTestId("recommendations-list")).toBeInTheDocument();
    });
    const cards = screen.getAllByTestId("recommendation-card");
    expect(cards).toHaveLength(2);
    expect(screen.getByText(/Bajar precio de Aceite Motul/)).toBeInTheDocument();
    expect(screen.getByText(/Activar campaña WhatsApp/)).toBeInTheDocument();
  });

  it("dispara POST /approve cuando se hace click en Aprobar de una pendiente", async () => {
    let approveCalled = false;
    mockFetch((url, init) => {
      if (url.includes("/hit-rate")) {
        return new Response(JSON.stringify(HIT_RATE), { status: 200 });
      }
      if (url.includes("/approve")) {
        approveCalled = true;
        expect(init?.method).toBe("POST");
        return new Response(JSON.stringify({ ...SAMPLE[0], status: "aprobada" }), { status: 200 });
      }
      return new Response(JSON.stringify(SAMPLE), { status: 200 });
    });

    renderPage();

    await waitFor(() => {
      expect(screen.getByTestId("recommendations-list")).toBeInTheDocument();
    });

    const approveBtn = screen.getByRole("button", { name: /Aprobar/ });
    fireEvent.click(approveBtn);

    await waitFor(() => {
      expect(approveCalled).toBe(true);
    });
  });
});
