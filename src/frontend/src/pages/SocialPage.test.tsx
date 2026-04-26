import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { saveSession } from "@/lib/auth";
import { SocialPage } from "@/pages/SocialPage";

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <SocialPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

const ACCOUNTS = [
  {
    id: "a1",
    plataforma: "tiktok",
    username: "rappi_motos",
    seguidores: 80000,
    engagement_rate: 4.5,
    descripcion: "Repuestos motos · envío Bogotá",
    url_perfil: "https://tiktok.com/@rappi_motos",
    relevancia_score: 78.5,
    fuente_query: "repuestos moto",
  },
  {
    id: "a2",
    plataforma: "ig",
    username: "tvs_repuestos_co",
    seguidores: 25000,
    engagement_rate: 6.1,
    descripcion: "TVS Raider 125 specialists",
    url_perfil: "https://instagram.com/tvs_repuestos_co",
    relevancia_score: 65.2,
    fuente_query: "repuestos TVS Raider 125",
  },
];

const POSTS = [
  {
    id: "p1",
    plataforma: "tiktok",
    username: "rappi_motos",
    post_external_id: "post_viral_1",
    url_post: "https://tiktok.com/@rappi_motos/post_viral_1",
    descripcion: "Cómo cambiar pastillas freno · #moto #pastillas",
    vistas: 250000,
    likes: 8500,
    comentarios: 320,
    hashtags: ["moto", "pastillas"],
    fecha_publicacion: new Date(Date.now() - 3 * 86400_000).toISOString(),
  },
];

function fetchHandler(url: string) {
  if (url.includes("/api/v1/social/accounts")) {
    return new Response(JSON.stringify(ACCOUNTS), { status: 200 });
  }
  if (url.includes("/api/v1/social/posts")) {
    return new Response(JSON.stringify(POSTS), { status: 200 });
  }
  return new Response(JSON.stringify({ detail: "not found" }), { status: 404 });
}

describe("SocialPage", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    saveSession({
      accessToken: "test-jwt",
      workspaceId: "RODDOS",
      role: "ceo",
      expiresAt: Date.now() + 60_000,
    });
    globalThis.fetch = vi.fn().mockImplementation((url: string) =>
      Promise.resolve(fetchHandler(url))
    ) as typeof fetch;
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
    localStorage.clear();
  });

  it("renderiza la grid de Top Cuentas con tarjetas", async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.getByTestId("social-accounts-grid")).toBeInTheDocument();
    });

    const grid = screen.getByTestId("social-accounts-grid");
    expect(within(grid).getByText("@rappi_motos")).toBeInTheDocument();
    expect(within(grid).getByText("@tvs_repuestos_co")).toBeInTheDocument();
    // Plataformas badges
    expect(within(grid).getByText("TikTok")).toBeInTheDocument();
    expect(within(grid).getByText("Instagram")).toBeInTheDocument();
    // Formato de seguidores: 80K, 25K
    expect(within(grid).getByText("80.0K")).toBeInTheDocument();
    expect(within(grid).getByText("25.0K")).toBeInTheDocument();
  });

  it("renderiza la lista de Posts Virales con descripcion truncada y hashtags", async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.getByTestId("social-posts-list")).toBeInTheDocument();
    });

    const list = screen.getByTestId("social-posts-list");
    expect(within(list).getByText(/Cómo cambiar pastillas freno/)).toBeInTheDocument();
    // Hashtag chips · regex anclado a match exacto · evita colisión con texto de la descripción
    expect(within(list).getByText(/^#moto$/)).toBeInTheDocument();
    expect(within(list).getByText(/^#pastillas$/)).toBeInTheDocument();
    expect(within(list).getByText("250.0K")).toBeInTheDocument();
  });
});
