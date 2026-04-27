export type QueryStatus = "active" | "paused";
export type QueryOrigin = "manual" | "suggested" | "auto_discovered";
export type SignalType = "trending" | "rising" | "liquidating" | "disappearing";
export type SuggestionStatus = "pending" | "accepted" | "dismissed";

export interface WatchQuery {
  id: string;
  query: string;
  category: string | null;
  origin: QueryOrigin;
  status: QueryStatus;
  priority: number;
  source: string;
  created_at: string | null;
}

export interface Category {
  slug: string;
  label: string;
  active: boolean;
}

export interface Suggestion {
  id: string;
  term: string;
  category: string;
  signal_type: SignalType;
  confidence: number;
  evidence: {
    metric?: string;
    value?: number | null;
    delta_pct?: number | null;
  };
  date: string;
  status: SuggestionStatus;
}
