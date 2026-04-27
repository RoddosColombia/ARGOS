import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { DashboardPage } from "@/pages/DashboardPage";
import { readSession, saveSession } from "@/lib/auth";

function renderApp() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/"]}>
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/login" element={<div>LoginPage stub</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("DashboardPage redirect on 401", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    saveSession({
      accessToken: "stale-jwt",
      workspaceId: "RODDOS",
      role: "ceo",
      expiresAt: Date.now() + 60_000, // local válido pero backend lo rechaza
    });
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
    localStorage.clear();
  });

  it("redirige a /login y limpia sesión cuando /auth/me responde 401", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "Token inválido" }), { status: 401 })
    ) as typeof fetch;

    renderApp();

    await waitFor(() => {
      expect(screen.getByText("LoginPage stub")).toBeInTheDocument();
    });
    // Verifica que NO se muestra el bug original
    expect(screen.queryByText(/Sesión inválida/i)).not.toBeInTheDocument();
    // Y la sesión local quedó limpia
    expect(readSession()).toBeNull();
  });
});
