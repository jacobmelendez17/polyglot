// Decks — browsable, read-only view of unlocked content, plus the unlock catalog
// and learner-built (custom) decks.
import { request } from "./http";

export interface DeckSummary {
  type: "vocabulary" | "grammar" | "intermissions";
  title: string;
  description: string;
  count: number;
}

// A deck as it appears in the catalog: always-on, threshold-gated, or custom.
export interface CatalogDeck {
  id: string;
  title: string;
  description: string;
  glyph: string;
  category: string;
  threshold: number;
  have: number;
  need: number;
  unlocked: boolean;
  custom: boolean;
  count?: number;
}

export interface DeckItem {
  item_type: "vocabulary" | "grammar" | "intermission";
  item_id: string;
  term: string;
  translation: string;
  part_of_speech?: string | null;
  article?: string | null;
  level?: number | null;
  learned?: boolean | null;
  srs_stage?: number | null;
  srs_stage_name?: string | null;
  next_review_at?: string | null;
  body?: string | null;
  kind?: string | null;
  viewed_at?: string | null;
}

export interface DeckPage {
  type: string;
  total: number;
  limit: number;
  offset: number;
  items: DeckItem[];
}

export const decks = {
  list: () => request<DeckSummary[]>("/api/v1/me/decks"),

  items: (type: string, limit = 50, offset = 0) =>
    request<DeckPage>(`/api/v1/me/decks/${type}?limit=${limit}&offset=${offset}`),

  // slice 43 — unlock catalog + custom decks
  catalog: () => request<CatalogDeck[]>("/api/v1/me/decks/catalog/all"),

  createCustom: (name: string, description = "") =>
    request<CatalogDeck>("/api/v1/me/decks/catalog/custom", {
      method: "POST",
      body: JSON.stringify({ name, description }),
    }),

  deleteCustom: (id: string) =>
    request<{ id: string; deleted: boolean }>(
      `/api/v1/me/decks/catalog/custom/${encodeURIComponent(id.replace(/^custom:/, ""))}`,
      { method: "DELETE" },
    ),
};
