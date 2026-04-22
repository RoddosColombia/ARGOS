export type Role = "ceo" | "analista" | "sistema" | "cliente";

export interface LoginRequest {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  role: Role;
  workspace_id: string;
}

export interface UserOut {
  email: string;
  role: Role;
  workspace_id: string;
}

export interface HealthResponse {
  status: "ok";
  version: string;
}
