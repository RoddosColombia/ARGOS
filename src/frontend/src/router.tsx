import { createBrowserRouter } from "react-router-dom";
import { Layout } from "@/components/Layout";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { BriefingPage } from "@/pages/BriefingPage";
import { CompetitorsPage } from "@/pages/CompetitorsPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { LoginPage } from "@/pages/LoginPage";
import { MarketplacePage } from "@/pages/MarketplacePage";
import { RecommendationsPage } from "@/pages/RecommendationsPage";
import { SismoPage } from "@/pages/SismoPage";
import { SocialPage } from "@/pages/SocialPage";
import { TrendsPage } from "@/pages/TrendsPage";

export const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  {
    path: "/",
    element: (
      <ProtectedRoute>
        <Layout>
          <DashboardPage />
        </Layout>
      </ProtectedRoute>
    ),
  },
  {
    path: "/marketplace",
    element: (
      <ProtectedRoute>
        <Layout>
          <MarketplacePage />
        </Layout>
      </ProtectedRoute>
    ),
  },
  {
    path: "/trends",
    element: (
      <ProtectedRoute>
        <Layout>
          <TrendsPage />
        </Layout>
      </ProtectedRoute>
    ),
  },
  {
    path: "/competitors",
    element: (
      <ProtectedRoute>
        <Layout>
          <CompetitorsPage />
        </Layout>
      </ProtectedRoute>
    ),
  },
  {
    path: "/social",
    element: (
      <ProtectedRoute>
        <Layout>
          <SocialPage />
        </Layout>
      </ProtectedRoute>
    ),
  },
  {
    path: "/briefing",
    element: (
      <ProtectedRoute>
        <Layout>
          <BriefingPage />
        </Layout>
      </ProtectedRoute>
    ),
  },
  {
    path: "/recommendations",
    element: (
      <ProtectedRoute>
        <Layout>
          <RecommendationsPage />
        </Layout>
      </ProtectedRoute>
    ),
  },
  {
    path: "/sismo",
    element: (
      <ProtectedRoute>
        <Layout>
          <SismoPage />
        </Layout>
      </ProtectedRoute>
    ),
  },
  // 404 fallback · protegido · si no hay sesión manda a login
  {
    path: "*",
    element: (
      <ProtectedRoute>
        <Layout>
          <div className="mx-auto max-w-md rounded-lg border border-ink-200 bg-white p-6 text-center shadow-sm">
            <h1 className="text-lg font-semibold text-ink-900">Ruta no encontrada</h1>
            <p className="mt-1 text-sm text-ink-500">Navega desde el sidebar.</p>
          </div>
        </Layout>
      </ProtectedRoute>
    ),
  },
]);
