import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiRequest } from "@/lib/api";
import { clearSession, saveSession } from "@/lib/auth";

describe("apiRequest", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    clearSession();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it("añade Authorization y X-Workspace-Id cuando hay sesión válida", async () => {
    saveSession({
      accessToken: "fake-jwt",
      workspaceId: "RODDOS",
      role: "ceo",
      expiresAt: Date.now() + 60_000,
    });

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "ok" }), { status: 200 })
    );
    globalThis.fetch = fetchMock as typeof fetch;

    await apiRequest<{ status: string }>("/api/v1/health");

    const [, init] = fetchMock.mock.calls[0];
    expect(init.headers["Authorization"]).toBe("Bearer fake-jwt");
    expect(init.headers["X-Workspace-Id"]).toBe("RODDOS");
  });

  it("omite Authorization y X-Workspace-Id cuando skipAuth+skipWorkspace", async () => {
    saveSession({
      accessToken: "fake-jwt",
      workspaceId: "RODDOS",
      role: "ceo",
      expiresAt: Date.now() + 60_000,
    });

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), { status: 200 })
    );
    globalThis.fetch = fetchMock as typeof fetch;

    await apiRequest("/api/v1/auth/login", {
      method: "POST",
      body: { email: "a@b.com", password: "x" },
      skipAuth: true,
      skipWorkspace: true,
    });

    const [, init] = fetchMock.mock.calls[0];
    expect(init.headers["Authorization"]).toBeUndefined();
    expect(init.headers["X-Workspace-Id"]).toBeUndefined();
    expect(init.method).toBe("POST");
    expect(init.body).toBe(JSON.stringify({ email: "a@b.com", password: "x" }));
  });

  it("lanza ApiError con detail del body en respuestas no-OK", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "Credenciales inválidas" }), { status: 401 })
    );
    globalThis.fetch = fetchMock as typeof fetch;

    await expect(
      apiRequest("/api/v1/auth/login", {
        method: "POST",
        body: {},
        skipAuth: true,
        skipWorkspace: true,
      })
    ).rejects.toMatchObject({
      name: "ApiError",
      status: 401,
      detail: "Credenciales inválidas",
    });
  });

  it("limpia la sesión en respuesta 401", async () => {
    saveSession({
      accessToken: "fake-jwt",
      workspaceId: "RODDOS",
      role: "ceo",
      expiresAt: Date.now() + 60_000,
    });

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "Token expirado" }), { status: 401 })
    );
    globalThis.fetch = fetchMock as typeof fetch;

    await expect(apiRequest("/api/v1/auth/me")).rejects.toBeInstanceOf(ApiError);
    expect(localStorage.getItem("argos.access_token")).toBeNull();
  });
});
