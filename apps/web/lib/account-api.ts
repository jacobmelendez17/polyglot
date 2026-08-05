// Settings + profile client.
import { request } from "./http";

export interface Settings {
  theme: string;
  font_size: string;
  color_theme: string;
  lesson_batch_size: number;
  review_order: string;
  curriculum_mode: string;
  back_to_back: boolean;
  back_to_back_order: string;
  show_srs_indicator: boolean;
  leech_threshold: number;
  review_batch_enabled: boolean;
  review_batch_size: number;
  reveal_full_answer: boolean;
  allow_cheating: boolean;
  allow_skipping: boolean;
  undo_enabled: boolean;
  accept_user_synonyms: boolean;
  intermissions_enabled: boolean;
  immersion_mode: boolean;
  dialect: string;
  audio_autoplay: boolean;
  audio_voice: string;
  audio_rate: number;
  immersion_unlocked: boolean;
}

export interface Profile {
  display_name: string;
  bio: string;
  timezone: string;
  email: string;
  role: string;
  xp_total: number;
  points_balance: number;
  rank_level: number;
  streak_current: number;
  streak_best: number;
  immersion_unlocked: boolean;
}

export const account = {
  getSettings: () => request<Settings>("/api/v1/me/settings"),
  updateSettings: (patch: Partial<Record<keyof Settings, unknown>>) =>
    request<Settings>("/api/v1/me/settings", { method: "PATCH", body: JSON.stringify(patch) }),
  getProfile: () => request<Profile>("/api/v1/me/profile"),
  updateProfile: (patch: { display_name?: string; bio?: string; timezone?: string }) =>
    request<Profile>("/api/v1/me/profile", { method: "PATCH", body: JSON.stringify(patch) }),
};
