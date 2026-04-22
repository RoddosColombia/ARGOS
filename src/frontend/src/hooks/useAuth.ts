import { useQuery } from "@tanstack/react-query";
import { useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, apiRequest } from "@/lib/api";
import { clearSession, isSessionValid, readSession, saveSession } from "@/lib/auth";
import type { LoginRequest, TokenResponse, UserOut } from "@/types/api";

export function useLogin() {
  const navigate = useNavigate();

  return useCallback(
    async (credentials: LoginRequest): Promise<{ ok: true } | { ok: false; message: string }> => {
      try {
        const token = await apiRequest<TokenResponse>("/api/v1/auth/login", {
          method: "POST",
          body: credentials,
          skipAuth: true,
          skipWorkspace: true,
        });
        saveSession({
          accessToken: token.access_token,
          workspaceId: token.workspace_id,
          role: token.role,
          expiresAt: Date.now() + token.expires_in * 1000,
        });
        navigate("/", { replace: true });
        return { ok: true };
      } catch (err) {
        if (err instanceof ApiError) {
          const message = err.status === 401 ? "Credenciales inválidas" : err.detail;
          return { ok: false, message };
        }
        return { ok: false, message: "Error de red · reintenta" };
      }
    },
    [navigate]
  );
}

export function useLogout() {
  const navigate = useNavigate();
  return useCallback(() => {
    clearSession();
    navigate("/login", { replace: true });
  }, [navigate]);
}

export function useCurrentUser() {
  return useQuery<UserOut>({
    queryKey: ["auth", "me"],
    queryFn: () => apiRequest<UserOut>("/api/v1/auth/me"),
    enabled: isSessionValid(readSession()),
  });
}
