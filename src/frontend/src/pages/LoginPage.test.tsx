import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { LoginPage } from "@/pages/LoginPage";

function renderLogin() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("LoginPage", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it("renderiza form con campos email y password", () => {
    renderLogin();
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /ingresar/i })).toBeInTheDocument();
  });

  it("valida email vacío y password vacío", async () => {
    const user = userEvent.setup();
    renderLogin();
    await user.click(screen.getByRole("button", { name: /ingresar/i }));
    expect(await screen.findByText(/email requerido/i)).toBeInTheDocument();
    expect(screen.getByText(/password requerido/i)).toBeInTheDocument();
  });

  it("muestra error 401 del servidor como 'Credenciales inválidas'", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "Credenciales inválidas" }), { status: 401 })
    ) as typeof fetch;

    const user = userEvent.setup();
    renderLogin();
    await user.type(screen.getByLabelText(/email/i), "ceo@roddos.com");
    await user.type(screen.getByLabelText(/password/i), "wrong");
    await user.click(screen.getByRole("button", { name: /ingresar/i }));

    expect(await screen.findByText(/credenciales inválidas/i)).toBeInTheDocument();
    expect(localStorage.getItem("argos.access_token")).toBeNull();
  });

  it("persiste la sesión en un login exitoso", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          access_token: "jwt-123",
          token_type: "bearer",
          expires_in: 3600,
          role: "ceo",
          workspace_id: "RODDOS",
        }),
        { status: 200 }
      )
    ) as typeof fetch;

    const user = userEvent.setup();
    renderLogin();
    await user.type(screen.getByLabelText(/email/i), "ceo@roddos.com");
    await user.type(screen.getByLabelText(/password/i), "correct-password");
    await user.click(screen.getByRole("button", { name: /ingresar/i }));

    // Esperar a que la sesión quede almacenada
    await vi.waitFor(() => {
      expect(localStorage.getItem("argos.access_token")).toBe("jwt-123");
    });
    expect(localStorage.getItem("argos.workspace_id")).toBe("RODDOS");
    expect(localStorage.getItem("argos.role")).toBe("ceo");
  });
});
