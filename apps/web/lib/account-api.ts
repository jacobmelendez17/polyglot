// Password reset, email verification, and decks.
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

export const account = {
  forgotPassword: (email: string) =>
    request<{ ok: boolean; message: string }>("/api/v1/auth/forgot-password", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),

  resetPassword: (token: string, newPassword: string) =>
    request<{ ok: boolean; message: string }>("/api/v1/auth/reset-password", {
      method: "POST",
      body: JSON.stringify({ token, new_password: newPassword }),
    }),

  sendVerification: () =>
    request<{ ok: boolean; message: string }>("/api/v1/auth/send-verification", {
      method: "POST",
    }),

  verifyEmail: (token: string) =>
    request<{ verified: boolean; already_verified: boolean }>(
      "/api/v1/auth/verify-email",
      { method: "POST", body: JSON.stringify({ token }) },
    ),

  verificationStatus: () =>
    request<{ email: string; verified: boolean }>("/api/v1/auth/verification-status"),
};

export const decks = {
  list: () => request<DeckSummary[]>("/api/v1/me/decks"),

  items: (type: string, limit = 50, offset = 0) =>
    request<DeckPage>(`/api/v1/me/decks/${type}?limit=${limit}&offset=${offset}`),
};
