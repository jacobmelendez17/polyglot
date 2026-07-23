// Learning endpoints: levels, lessons, review sessions, stats.
import { getStoredToken } from "./admin-api";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface Level {
  id: string; position: number; title: string;
  vocab_count: number; grammar_count: number; unlocked: boolean;
  unlock_progress?: UnlockProgress | null;
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
  audio?: import('./speech').AudioRef | null;
}
export interface Prompt {
  item_type: string; item_id: string; direction: string;
  srs_stage: number; prompt_kind: string; shown: string;
  article?: string | null; part_of_speech?: string; hint?: string | null;
  audio?: import('./speech').AudioRef | null;
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
  xp_total: number; reviews_due: number; lessons_available: number;
  items_learned: number; items_fluent: number; leeches: number;
  stage_group_counts: Record<string, number>;
  stage_counts: { stage: number; name: string; count: number }[];
  forecast: { label: string; count: number }[];
  next_review_at: string | null;
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

// ---- Practice ----
export interface PracticePrompt {
  item_type: string; item_id: string; mode: string;
  shown: string; translation: string; tense?: string | null; person?: string | null;
  audio?: import('./speech').AudioRef | null;
}
export interface PracticeSession { session_id: string; mode: string; prompts: PracticePrompt[]; }
export interface PracticeGrade {
  correct: boolean; expected: string; warnings: string[];
  xp_awarded: number; practice_stage: number | null; perfect: boolean;
  perfect_overall: boolean;
}

export const practice = {
  start: (mode: string) =>
    req<PracticeSession>(`/api/v1/practice/sessions?mode=${mode}`, { method: "POST" }),
  answer: (sessionId: string, body: {
    item_type: string; item_id: string; mode: string; answer: string;
    tense?: string | null; person?: string | null; idempotency_key: string;
  }) => req<PracticeGrade>(`/api/v1/practice/sessions/${sessionId}/answers`,
    { method: "POST", body: JSON.stringify(body) }),
  finish: (sessionId: string) =>
    req<{ state: string }>(`/api/v1/practice/sessions/${sessionId}/complete`, { method: "POST" }),
};

export const PRACTICE_MODES = [
  { id: "fill_blank", title: "fill in the blank", desc: "complete sentences with the missing word", icon: "✎" },
  { id: "conjugation", title: "verb conjugation", desc: "conjugate verbs across tenses and persons", icon: "⇄" },
  { id: "weak_items", title: "weak items", desc: "drill the words that keep tripping you up", icon: "✦" },
  { id: "listening", title: "listening", desc: "hear a word and type what you heard", icon: "♪" },
] as const;

// ---- Lesson quiz ----
export interface QuizPrompt {
  item_type: string; item_id: string; shown: string; hint: string;
  audio?: import('./speech').AudioRef | null;
}
export interface QuizSession { session_id: string; prompts: QuizPrompt[]; }
export interface QuizAnswer {
  correct: boolean; expected: string; warnings: string[];
  typo_forgiven: boolean; already_recorded: boolean;
}

export const quiz = {
  start: (level: number, lesson: number) =>
    req<QuizSession>(`/api/v1/levels/${level}/lessons/${lesson}/quiz`, { method: "POST" }),
  answer: (sessionId: string, body: {
    item_type: string; item_id: string; answer: string; idempotency_key: string;
  }) => req<QuizAnswer>(`/api/v1/quiz/${sessionId}/answers`,
    { method: "POST", body: JSON.stringify(body) }),
};

export interface UnlockProgress {
  grammar_at_familiar: number; grammar_required: number; grammar_total: number;
  vocab_at_familiar: number; vocab_required: number; vocab_total: number;
  percent: number; remaining: number;
}

// ---- Item progress (SRS + practice stages + history) ----

export interface PracticeStage {
  category: string; stage: number; max_stage: number; stage_name: string;
  stage_reached_at: string | null; next_stage_at: string | null; live: boolean;
}
export interface ReviewHistoryEntry {
  answered_at: string | null; direction: string; prompt_kind: string;
  correct: boolean; undo_used: boolean;
  srs_stage_before: number | null; srs_stage_after: number | null;
}
export interface ItemProgress {
  item_type: string; item_id: string; term: string; translation: string;
  part_of_speech: string; level: number | null;
  audio?: import('./speech').AudioRef | null;
  srs_stage: number; srs_stage_name: string; next_review_at: string | null;
  total_reviews: number; total_incorrect: number; accuracy: number | null;
  leech_state: string; leech_score: number;
  unlocked_at: string | null; lesson_completed_at: string | null;
  fluent_at: string | null; perfect_at: string | null;
  practice_stages: PracticeStage[]; history: ReviewHistoryEntry[];
}
export interface ItemSummary {
  item_type: string; item_id: string; term: string; translation: string;
  level: number | null; srs_stage: number; srs_stage_name: string;
  next_review_at: string | null; leech_state: string;
  practice_stage: number; perfect: boolean;
}

export const items = {
  list: () => req<ItemSummary[]>("/api/v1/me/items"),
  progress: (type: string, id: string) =>
    req<ItemProgress>(`/api/v1/me/items/${type}/${id}/progress`),
};

export const CATEGORY_LABELS: Record<string, string> = {
  sentences: "sentences", listening: "listening", speaking: "speaking",
};
