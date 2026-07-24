// Item detail, review history, user synonyms, and level progression.
import type { AudioRef } from "./speech";
import { request } from "./http";

export const PRACTICE_CATEGORIES = ["sentences", "listening", "speaking"] as const;
export type PracticeCategory = (typeof PRACTICE_CATEGORIES)[number];

export const CATEGORY_LABELS: Record<PracticeCategory, string> = {
  sentences: "sentences",
  listening: "listening",
  speaking: "speaking",
};

export const MAX_PRACTICE_STAGE = 5;

export interface PracticeStage {
  category: PracticeCategory;
  stage: number;
  max_stage: number;
  label: string;
  complete: boolean;
  on_cooldown: boolean;
  next_available_at: string | null;
  stage_reached_at: string | null;
}

export interface PracticeSummary {
  stages: PracticeStage[];
  categories_complete: number;
  categories_total: number;
  completed_categories: string[];
  remaining_categories: string[];
  srs_fluent: boolean;
  perfect: boolean;
}

export interface ItemProgress {
  learned: boolean;
  srs_stage: number;
  srs_stage_name: string;
  next_review_at: string | null;
  unlocked_at: string | null;
  lesson_completed_at: string | null;
  fluent: boolean;
  fluent_at: string | null;
  perfect: boolean;
  perfect_at: string | null;
  total_reviews: number;
  total_incorrect: number;
  answers_total: number;
  answers_correct: number;
  accuracy: number | null;
  mistakes: number;
  leech_state: "none" | "watch" | "leech" | "critical";
  leech_score: number;
}

export interface ExampleSentence {
  id: string;
  text_es: string;
  text_en: string;
  difficulty: string;
  role: string;
  audio: AudioRef | null;
}

export interface UserSynonym {
  id: string;
  synonym: string;
}

export interface ItemDetail {
  item_type: "vocabulary" | "grammar";
  item_id: string;
  term: string;
  translation: string;
  part_of_speech: string;
  meaning: string;
  level: number;
  level_title: string;
  synonyms: string[];
  audio: AudioRef | null;
  examples: ExampleSentence[];
  user_synonyms: UserSynonym[];
  progress: ItemProgress;
  practice: PracticeSummary;
  // vocabulary only
  pronunciation?: string | null;
  ipa?: string | null;
  article?: string | null;
  gender?: string | null;
  variations?: string[] | null;
  castilian_variant?: string | null;
  latam_variant?: string | null;
  context?: unknown[] | null;
  // grammar only
  structure?: string | null;
  explanation?: string | null;
}

export interface HistoryEntry {
  id: string;
  direction: "es_to_en" | "en_to_es";
  prompt_kind: string;
  submitted_answer: string;
  original_correct: boolean;
  final_correct: boolean;
  typo_forgiven: boolean;
  synonym_matched: boolean;
  undo_used: boolean;
  warnings: string[];
  srs_stage_before: number | null;
  srs_stage_after: number | null;
  pair_incomplete: boolean;
  answered_at: string | null;
}

export interface HistoryPage {
  total: number;
  limit: number;
  offset: number;
  items: HistoryEntry[];
}

export interface LevelProgressItem {
  item_type: "vocabulary" | "grammar";
  item_id: string;
  term: string;
  translation: string;
  part_of_speech: string;
  article: string | null;
  learned: boolean;
  srs_stage: number;
  srs_stage_name: string;
  next_review_at: string | null;
  leech_state: "none" | "watch" | "leech" | "critical";
  practice_stages: Record<PracticeCategory, number>;
  practice_labels: Record<PracticeCategory, string>;
  categories_complete: number;
  perfect: boolean;
}

export interface LevelProgress {
  position: number;
  title: string;
  unlocked: boolean;
  totals: {
    items: number;
    learned: number;
    not_started: number;
    familiar_plus: number;
    fluent: number;
    perfect: number;
    leeches: number;
  };
  items: LevelProgressItem[];
}

export const items = {
  detail: (type: string, id: string) =>
    request<ItemDetail>(`/api/v1/items/${type}/${id}`),

  history: (type: string, id: string, limit = 20, offset = 0) =>
    request<HistoryPage>(
      `/api/v1/items/${type}/${id}/history?limit=${limit}&offset=${offset}`,
    ),

  addSynonym: (type: string, id: string, synonym: string) =>
    request<{ id: string; synonym: string; created: boolean }>(
      `/api/v1/items/${type}/${id}/synonyms`,
      { method: "POST", body: JSON.stringify({ synonym }) },
    ),

  removeSynonym: (synonymId: string) =>
    request<void>(`/api/v1/synonyms/${synonymId}`, { method: "DELETE" }),

  levelProgress: (level: number) =>
    request<LevelProgress>(`/api/v1/levels/${level}/progress`),
};

/** Human-readable "in 3 days" / "4 hours ago" for review timestamps. */
export function relativeTime(iso: string | null, now = new Date()): string {
  if (!iso) return "—";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "—";
  const diff = then - now.getTime();
  const abs = Math.abs(diff);
  const minute = 60_000;
  const hour = 60 * minute;
  const day = 24 * hour;

  const pick = (): [number, string] => {
    if (abs < hour) return [Math.max(1, Math.round(abs / minute)), "min"];
    if (abs < day) return [Math.round(abs / hour), "hr"];
    return [Math.round(abs / day), "day"];
  };
  const [value, unit] = pick();
  const plural = value === 1 ? "" : "s";
  return diff >= 0 ? `in ${value} ${unit}${plural}` : `${value} ${unit}${plural} ago`;
}
