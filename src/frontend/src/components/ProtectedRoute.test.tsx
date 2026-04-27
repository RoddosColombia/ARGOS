import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { saveSession } from "@/lib/auth";

function renderAtPath(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/login" element={<div>LoginPage stub</div>} />
        <Route
          path="/protected"
          element={
            <ProtectedRoute>
              <div>Contenido protegido</div>
            </ProtectedRoute>
          }
        />
      </Routes>
    </MemoryRouter>
  );
}

describe("ProtectedRoute", () => {
  beforeEach(() => {
    localStorage.clear();
  });
  afterEach(() => {
    localStorage.clear();
  });

  it("redirige a /login si no hay sesión", () => {
    renderAtPath("/protected");
    expect(screen.getByText("LoginPage stub")).toBeInTheDocument();
    expect(screen.queryByText("Contenido protegido")).not.toBeInTheDocument();
  });

  it("redirige a /login si la sesión existe pero está expirada", () => {
    saveSession({
      accessToken: "expired-jwt",
      workspaceId: "RODDOS",
      role: "ceo",
      expiresAt: Date.now() - 1000, // ya expirada
    });
    renderAtPath("/protected");
    expect(screen.getByText("LoginPage stub")).toBeInTheDocument();
    expect(screen.queryByText("Contenido protegido")).not.toBeInTheDocument();
  });

  it("renderiza children si la sesión es válida", () => {
    saveSession({
      accessToken: "valid-jwt",
      workspaceId: "RODDOS",
      role: "ceo",
      expiresAt: Date.now() + 60_000,
    });
    renderAtPath("/protected");
    expect(screen.getByText("Contenido protegido")).toBeInTheDocument();
  });
});
