/**
 * Almacenamiento de sesión en localStorage.
 *
 * Trade-off conocido: localStorage es vulnerable a XSS. Mitigación en Build 0.4:
 * no hay rutas que admitan HTML del usuario y React escapa contenido por default.
 * Build futuro puede migrar a httpOnly cookies cuando el backend emita refresh
 * tokens y soporte el flujo SameSite (ver deuda técnica).
 */

const TOKEN_KEY = "argos.access_token";
const WORKSPACE_KEY = "argos.workspace_id";
const ROLE_KEY = "argos.role";
const EXPIRES_AT_KEY = "argos.expires_at";

export interface StoredSession {
  accessToken: string;
  workspaceId: string;
  role: string;
  expiresAt: number; // unix ms
}

export function saveSession(s: StoredSession): void {
  localStorage.setItem(TOKEN_KEY, s.accessToken);
  localStorage.setItem(WORKSPACE_KEY, s.workspaceId);
  localStorage.setItem(ROLE_KEY, s.role);
  localStorage.setItem(EXPIRES_AT_KEY, String(s.expiresAt));
}

export function readSession(): StoredSession | null {
  const token = localStorage.getItem(TOKEN_KEY);
  const workspaceId = localStorage.getItem(WORKSPACE_KEY);
  const role = localStorage.getItem(ROLE_KEY);
  const expiresAtStr = localStorage.getItem(EXPIRES_AT_KEY);
  if (!token || !workspaceId || !role || !expiresAtStr) return null;
  const expiresAt = Number(expiresAtStr);
  if (!Number.isFinite(expiresAt)) return null;
  return { accessToken: token, workspaceId, role, expiresAt };
}

export function clearSession(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(WORKSPACE_KEY);
  localStorage.removeItem(ROLE_KEY);
  localStorage.removeItem(EXPIRES_AT_KEY);
}

export function isSessionValid(s: StoredSession | null): s is StoredSession {
  if (!s) return false;
  return s.expiresAt > Date.now();
}
