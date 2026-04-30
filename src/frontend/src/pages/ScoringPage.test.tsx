import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { saveSession } from "@/lib/auth";
import { ScoringPage } from "@/pages/ScoringPage";

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <ScoringPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("ScoringPage", () => {
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

  it("muestra banner del Score Engine y forwardea POST /evaluate al motor externo", async () => {
    const fakeResult = {
      decision: "aprobado",
      score_final: 720,
      solicitud_id: "SCR-EXTERNAL-1",
      narrativa: "Evaluado por el motor externo de Iván",
      regla_dura_aplicada: null,
      threshold_aplicado: 400,
      engine_version: "ext_v1.0",
    };
    const fakeConfig = {
      score_engine_api_url: "https://score-engine.roddos.com",
      roddos_mongodb_configured: true,
    };

    let evaluateCalled = false;

    globalThis.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/score/config")) {
        return new Response(JSON.stringify(fakeConfig), { status: 200 });
      }
      if (url.includes("/score/evaluate")) {
        evaluateCalled = true;
        expect(init?.method).toBe("POST");
        return new Response(JSON.stringify(fakeResult), { status: 200 });
      }
      return new Response(JSON.stringify([]), { status: 200 });
    }) as typeof fetch;

    renderPage();

    // Banner muestra la URL configurada
    await waitFor(() => {
      expect(screen.getByTestId("score-config-banner")).toBeInTheDocument();
    });
    await waitFor(() => {
      const banner = screen.getByTestId("score-config-banner");
      expect(banner.textContent ?? "").toContain("score-engine.roddos.com");
    });

    // Llenar form mínimo
    const form = screen.getByTestId("score-form");
    const inputs = form.querySelectorAll('input[type="text"]');
    fireEvent.change(inputs[0] as HTMLInputElement, { target: { value: "Andrés San Juan" } });
    fireEvent.change(inputs[1] as HTMLInputElement, { target: { value: "80075452" } });

    fireEvent.click(within(form).getByRole("button", { name: /Evaluar/ }));

    await waitFor(() => {
      expect(evaluateCalled).toBe(true);
      expect(screen.getByTestId("score-result")).toBeInTheDocument();
    });
    expect(screen.getByTestId("score-final")).toHaveTextContent("720");
    expect(screen.getByTestId("score-decision")).toHaveTextContent("aprobado");
    expect(screen.getByTestId("score-narrativa")).toHaveTextContent(/motor externo/);
  });
});
