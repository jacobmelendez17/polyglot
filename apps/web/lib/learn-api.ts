// Learning endpoints: levels, lessons, review sessions, stats.
import { getStoredToken } from "./admin-api";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface Level {
  id: string; position: number; title: string;
  vocab_count: number; grammar_count: number; unlocked: boolean;
}
export interface Lesson {
  position: number; kind: string; title: string;
  item_count: number; completed: boolean;
}
export interface LessonItem {
  item_type: string; item_id: string; term: string; translation: string;
  pronunciation?: string; ipa?: string; part_of_speech?: string;
  meaning?: string; article?: string | null; gender?: string;
  structure?: string; explanation?: string;
}
export interface Prompt {
  item_type: string; item_id: string; direction: string;
  srs_stage: number; prompt_kind: string; shown: string;
  article?: string | null; part_of_speech?: string; hint?: string | null;
}
export interface Session { session_id: string; prompts: Prompt[]; }
export interface AnswerResult {
  original_correct: boolean; final_correct: boolean; warnings: string[];
  typo_forgiven: boolean; synonym_matched: boolean; expected: string;
  pair_resolved: boolean; srs_stage_before?: number | null;
  srs_stage_after?: number | null; xp_awarded: number;
  answer_id?: string | null; message?: string | null;
}
export interface Stats {
  xp_total: number; reviews_due: number; items_learned: number;
  items_fluent: number; leeches: number;
  forecast: { label: string; count: number }[];
}

async function req<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getStoredToken();
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init.headers ?? {}),
    },
  });
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new Error(data?.error?.message ?? "Request failed.");
  return data as T;
}

// A stable client-generated key so retries never double-count.
export function newKey(): string {
  return crypto.randomUUID();
}

export const learn = {
  levels: () => req<Level[]>("/api/v1/levels"),
  lessons: (level: number) => req<Lesson[]>(`/api/v1/levels/${level}/lessons`),
  lessonDetail: (level: number, lesson: number) =>
    req<{ position: number; title: string; items: LessonItem[] }>(
      `/api/v1/levels/${level}/lessons/${lesson}`,
    ),
  completeLesson: (level: number, lesson: number, key: string) =>
    req<{ xp_awarded: number; unlocked: number; already_completed: boolean }>(
      `/api/v1/levels/${level}/lessons/${lesson}/complete`,
      { method: "POST", body: JSON.stringify({ idempotency_key: key }) },
    ),
  startSession: () => req<Session>("/api/v1/reviews/sessions", { method: "POST" }),
  submit: (sessionId: string, body: {
    item_type: string; item_id: string; direction: string;
    answer: string; idempotency_key: string;
  }) => req<AnswerResult>(`/api/v1/reviews/sessions/${sessionId}/answers`,
    { method: "POST", body: JSON.stringify(body) }),
  undo: (answerId: string, reason?: string) =>
    req<{ already_undone: boolean }>(`/api/v1/reviews/answers/${answerId}/undo`,
      { method: "POST", body: JSON.stringify({ reason: reason ?? null }) }),
  finishSession: (sessionId: string, abandoned = false) =>
    req<{ state: string; items_resolved: number }>(
      `/api/v1/reviews/sessions/${sessionId}/complete?abandoned=${abandoned}`,
      { method: "POST" },
    ),
  stats: () => req<Stats>("/api/v1/me/stats"),
};

export const STAGE_NAMES: Record<number, string> = {
  1: "Beginner 1", 2: "Beginner 2", 3: "Beginner 3", 4: "Beginner 4",
  5: "Familiar 1", 6: "Familiar 2", 7: "Intermediate", 8: "Advanced", 9: "Fluent",
};
