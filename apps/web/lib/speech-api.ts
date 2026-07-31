// Speaking practice client. Only a text transcript is ever sent — never audio.
import { request } from "./http";

export interface SpeakingPrompt {
  idx: number;
  item_type: string;
  item_id: string;
  prompt: string;
  prompt_lang: string;
  hint: string;
}

export interface UtteranceScore {
  score: number;
  passed: boolean;
  expected: string;
  heard: string;
  words: { word: string; matched: boolean }[];
  missed: string[];
  extra: string[];
  xp_awarded: number;
  practice_stage: number | null;
  perfect: boolean;
  already_scored: boolean;
}

export const speaking = {
  start: () =>
    request<{ prompts: SpeakingPrompt[] }>("/api/v1/me/practice/speaking/start",
      { method: "POST" }),
  score: (body: {
    item_type: string; item_id: string; transcript: string; idempotency_key: string;
  }) =>
    request<UtteranceScore>("/api/v1/me/practice/speaking/score",
      { method: "POST", body: JSON.stringify(body) }),
};
