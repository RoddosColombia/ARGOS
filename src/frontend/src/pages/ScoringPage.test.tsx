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

  it("submit del form llama POST /evaluate y muestra resultado con score + decisión", async () => {
    const fakeResult = {
      solicitud_id: "SCR-ARGOS-test",
      producto: "credito_rodante",
      score_final: 720,
      score_modelo: 0.7,
      score_claude: 0.75,
      delta_claude: 0.05,
      narrativa: "Cliente VIP con historial sólido en RODDOS",
      decision: "aprobado",
      regla_dura_aplicada: null,
      fraude_detectado: false,
      threshold_aplicado: 400,
      engine_version: "v0.1.0-manual",
    };

    globalThis.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/score/evaluate")) {
        expect(init?.method).toBe("POST");
        return new Response(JSON.stringify(fakeResult), { status: 200 });
      }
      return new Response(JSON.stringify([]), { status: 200 });
    }) as typeof fetch;

    renderPage();

    // Llenar form mínimo
    const form = screen.getByTestId("score-form");
    const cedulaInput = within(form).getAllByRole("textbox")[1];  // 0=nombre, 1=cedula? actually nombre is first
    // Use querySelector for inputs
    const nombre = form.querySelector('input[type="text"]') as HTMLInputElement;
    fireEvent.change(nombre, { target: { value: "Andrés San Juan" } });
    const inputs = form.querySelectorAll('input[type="text"]');
    fireEvent.change(inputs[1] as HTMLInputElement, { target: { value: "80075452" } });

    fireEvent.click(within(form).getByRole("button", { name: /Evaluar/ }));

    await waitFor(() => {
      expect(screen.getByTestId("score-result")).toBeInTheDocument();
    });
    expect(screen.getByTestId("score-final")).toHaveTextContent("720");
    expect(screen.getByTestId("score-decision")).toHaveTextContent("aprobado");
    expect(screen.getByTestId("score-narrativa")).toHaveTextContent(/Cliente VIP/);
  });
});
