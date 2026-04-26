export type RecommendationStatus =
  | "pendiente"
  | "aprobada"
  | "ejecutada"
  | "rechazada"
  | "rechazada_compliance"
  | "expirada"
  | "evaluada";

export interface ExpectedImpact {
  metric?: string;
  baseline?: string;
  target?: string;
  confidence?: number;
}

export interface ActualImpact {
  metric?: string;
  valor_real?: string;
  medido_at?: string;
}

export interface Recommendation {
  id: string;
  type: string;
  action_description: string;
  rationale: string;
  priority: "Alta" | "Media" | "Baja";
  priority_score: number;
  expected_impact: ExpectedImpact;
  actual_impact: ActualImpact | null;
  hit_rate_contribution: number | null;
  learning: string | null;
  status: RecommendationStatus;
  approved_by: string | null;
  approved_at: string | null;
  executed_at: string | null;
  fecha_briefing: string;
  shown_in_briefing: string[];
  created_at: string | null;
}

export interface HitRateResponse {
  days: number;
  evaluated_count: number;
  avg_hit_rate: number | null;
}
