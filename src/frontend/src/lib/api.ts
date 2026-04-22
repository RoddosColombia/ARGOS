import { clearSession, readSession } from "@/lib/auth";

const API_BASE = (import.meta.env.VITE_ARGOS_API_URL as string | undefined) ?? "";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: string,
    public readonly code?: string
  ) {
    super(`${status}: ${detail}`);
    this.name = "ApiError";
  }
}

interface RequestOpts {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  /** Fuerza omitir el header X-Workspace-Id · sólo útil para login. */
  skipWorkspace?: boolean;
  /** Fuerza omitir el header Authorization · sólo útil para login. */
  skipAuth?: boolean;
  signal?: AbortSignal;
}

export async function apiRequest<T>(path: string, opts: RequestOpts = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: "application/json",
  };

  const session = readSession();
  if (!opts.skipAuth && session) {
    headers.Authorization = `Bearer ${session.accessToken}`;
  }
  if (!opts.skipWorkspace && session) {
    headers["X-Workspace-Id"] = session.workspaceId;
  }

  const url = path.startsWith("http") ? path : `${API_BASE}${path}`;
  const resp = await fetch(url, {
    method: opts.method ?? "GET",
    headers,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
    signal: opts.signal,
  });

  if (resp.status === 401 && !opts.skipAuth) {
    // Token expirado o inválido · limpiar sesión · el ProtectedRoute redirige
    clearSession();
  }

  if (!resp.ok) {
    let detail = resp.statusText;
    let code: string | undefined;
    try {
      const body = (await resp.json()) as { detail?: string; code?: string };
      detail = body.detail ?? detail;
      code = body.code;
    } catch {
      // respuesta no-JSON · mantener statusText
    }
    throw new ApiError(resp.status, detail, code);
  }

  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}
