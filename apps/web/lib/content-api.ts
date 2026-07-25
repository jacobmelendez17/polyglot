// Intermissions, changelog, and immersion mode.
import { request } from "./http";

export interface Intermission {
  id: string;
  title: string;
  body: string;
  kind: string;
  trigger_description: string;
  viewed_at: string | null;
}

export interface IntermissionHistory {
  total: number;
  limit: number;
  offset: number;
  items: Intermission[];
}

export type IntermissionEvent = "level_start" | "lesson_complete" | "progress";

export interface ChangelogItem {
  id: string;
  type: "feature" | "fix" | "content" | "announcement";
  title: string;
  body: string;
  published_at: string | null;
}

export interface ChangelogPage {
  total: number;
  limit: number;
  offset: number;
  items: ChangelogItem[];
}

export interface ImmersionState {
  unlocked: boolean;
  enabled: boolean;
  unlock_level: number;
  levels_completed: number;
  levels_remaining: number;
  never_translated: string[];
}

export const intermissions = {
  pending: (event: IntermissionEvent, level?: number, lesson?: number) => {
    const params = new URLSearchParams({ event });
    if (level != null) params.set("level", String(level));
    if (lesson != null) params.set("lesson", String(lesson));
    return request<Intermission[]>(`/api/v1/me/intermissions/pending?${params}`);
  },

  markViewed: (id: string) =>
    request<{ id: string; viewed_at: string | null }>(
      `/api/v1/me/intermissions/${id}/viewed`, { method: "POST" },
    ),

  history: (limit = 20, offset = 0) =>
    request<IntermissionHistory>(
      `/api/v1/me/intermissions/history?limit=${limit}&offset=${offset}`,
    ),
};

export const changelog = {
  list: (limit = 20, offset = 0) =>
    request<ChangelogPage>(`/api/v1/changelog?limit=${limit}&offset=${offset}`),

  unread: () =>
    request<{ unread: number; last_read_at: string | null }>(
      "/api/v1/me/changelog/unread",
    ),

  markRead: () =>
    request<{ unread: number; last_read_at: string | null }>(
      "/api/v1/me/changelog/mark-read", { method: "POST" },
    ),
};

export const immersion = {
  get: () => request<ImmersionState>("/api/v1/me/immersion"),

  set: (enabled: boolean) =>
    request<ImmersionState>("/api/v1/me/immersion", {
      method: "PUT",
      body: JSON.stringify({ enabled }),
    }),
};

export const CHANGELOG_TYPE_LABEL: Record<string, string> = {
  feature: "new",
  fix: "fixed",
  content: "content",
  announcement: "news",
};
