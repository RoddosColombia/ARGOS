# ARGOS Frontend

Web interna (CEO + analista). React 19 + Vite 6 + TypeScript 5 + Tailwind 4.

## Estructura

```
src/frontend/
├── package.json
├── tsconfig.{app,node}.json
├── vite.config.ts · vitest.config.ts · vitest.setup.ts
├── index.html
├── public/                   ← favicon
└── src/
    ├── main.tsx              ← entrypoint + QueryClient + RouterProvider
    ├── router.tsx            ← react-router-dom createBrowserRouter
    ├── index.css             ← @import "tailwindcss" + @theme tokens
    ├── lib/
    │   ├── api.ts            ← fetch wrapper + ApiError + headers automáticos
    │   ├── auth.ts           ← localStorage session (token, workspace, role, exp)
    │   └── queryClient.ts
    ├── types/api.ts          ← contratos del backend
    ├── hooks/useAuth.ts      ← useLogin, useLogout, useCurrentUser
    ├── components/
    │   ├── Layout.tsx        ← sidebar + header + main
    │   ├── Sidebar.tsx       ← 6 módulos placeholder por phase
    │   └── ProtectedRoute.tsx
    └── pages/
        ├── LoginPage.tsx     ← react-hook-form + zod
        └── DashboardPage.tsx ← estado de Phase 0 + módulos próximos
```

## Setup

```bash
cd src/frontend
npm install
cp .env.example .env.local    # opcional · proxy Vite usa 8000 por default
npm run dev                   # abre en http://localhost:5173
```

Backend debe estar corriendo en `http://localhost:8000` (ver `src/backend/README.md`).

## Scripts

- `npm run dev` · Vite dev server con proxy `/api` → backend
- `npm run build` · typecheck + Vite build a `dist/`
- `npm run preview` · sirve `dist/` localmente
- `npm run test` · Vitest en modo CI (una sola pasada)
- `npm run test:watch` · Vitest interactivo
- `npm run lint` · typecheck (tsc noEmit)

## Design tokens

Definidos en `src/index.css` via `@theme` (Tailwind 4):

- **brand** (emerald) · acentos de acción primaria
- **ink** (slate) · superficies y texto
- Fonts: system sans (Inter si está disponible) + JetBrains Mono
- No se usa shadcn/ui todavía · se puede integrar en un build posterior

## Auth flow

1. `LoginPage` → `POST /api/v1/auth/login` → guarda `access_token`, `workspace_id`, `role`, `expires_at` en localStorage
2. Navega a `/` (Dashboard protegido)
3. `ProtectedRoute` verifica expiración antes de renderizar
4. `useCurrentUser` (TanStack Query) consume `GET /api/v1/auth/me`
5. `api.ts` inyecta `Authorization: Bearer <jwt>` y `X-Workspace-Id: <ws>` automáticamente (ROG-A3)
6. Respuesta 401 limpia la sesión → `ProtectedRoute` redirige a `/login`
7. `useLogout` limpia sesión y navega a `/login`

## Deuda técnica conocida

- **localStorage para el JWT** es vulnerable a XSS. Mitigación: React escapa contenido por default y no hay entradas HTML del usuario. Build futuro: migrar a httpOnly cookie cuando el backend emita refresh tokens.
- **Sin refresh token**: sesión caduca a los 60 min · re-login manual. Aceptable para equipo interno pequeño.
- **Sin interceptor global de expiración**: un 401 espontáneo limpia la sesión pero el usuario no ve toast · basta la redirección a login. Mejorar cuando haya TanStack Query mutations más complejas.
