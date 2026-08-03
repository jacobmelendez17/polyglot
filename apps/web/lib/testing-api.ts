// Testing-maps client.
import { request } from "./http";

export interface TestOption { text: string }
export interface TestQuestion {
  id: string; caption: string; stem: string; options: TestOption[];
  audio_asset_id: string | null;
}
export interface StartResult { attempt_id: string; map: string; questions: TestQuestion[] }
export interface AnswerResult {
  correct: boolean; correct_index: number; explanation: string;
  xp_awarded: number; already_answered: boolean;
}
export interface CompleteResult {
  map: string; score: number; total: number; answered: number; percentage: number;
}

export const testing = {
  start: (map: string, band = "") =>
    request<StartResult>(`/api/v1/tests/${map}/start${band ? `?band=${encodeURIComponent(band)}` : ""}`,
      { method: "POST" }),
  answer: (attemptId: string, questionId: string, chosenIndex: number, key: string) =>
    request<AnswerResult>(`/api/v1/tests/attempts/${attemptId}/answer`,
      { method: "POST", body: JSON.stringify({
        question_id: questionId, chosen_index: chosenIndex, idempotency_key: key }) }),
  complete: (attemptId: string) =>
    request<CompleteResult>(`/api/v1/tests/attempts/${attemptId}/complete`, { method: "POST" }),
};

export const TEST_MAPS = [
  { id: "cefr", title: "cefr", blurb: "standardized comprehension, A1 → C2 style" },
  { id: "app", title: "app", blurb: "only what you've covered in the curriculum" },
  { id: "life", title: "life", blurb: "casual real-world scenarios" },
] as const;
