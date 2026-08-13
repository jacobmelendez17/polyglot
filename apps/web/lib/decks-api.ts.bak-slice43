// Decks — browsable, read-only view of unlocked content.
//
// Split out of account-api.ts (which is now the settings + profile client) so
// this doesn't collide with that file's purpose again.
import { request } from "./http";

export interface DeckSummary {
  type: "vocabulary" | "grammar" | "intermissions";
  title: string;
  description: string;
  count: number;
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
};
