// Forums / community.
import { request } from "./http";

export interface ForumCategory {
  id: string;
  slug: string;
  title: string;
  description: string;
  locked: boolean;
  thread_count: number;
}

export interface ThreadSummary {
  id: string;
  title: string;
  slug: string;
  author: string;
  reply_count: number;
  pinned: boolean;
  locked: boolean;
  hidden: boolean;
  created_at: string | null;
  last_activity_at: string | null;
}

export interface ThreadList {
  category: { slug: string; title: string; description: string; locked: boolean };
  total: number;
  limit: number;
  offset: number;
  threads: ThreadSummary[];
}

export interface ForumReply {
  id: string;
  body: string;
  author: string;
  hidden: boolean;
  created_at: string | null;
}

export interface ThreadDetail {
  id: string;
  title: string;
  body: string;
  author: string;
  category: { slug: string; title: string } | null;
  pinned: boolean;
  locked: boolean;
  hidden: boolean;
  created_at: string | null;
  reply_total: number;
  limit: number;
  offset: number;
  replies: ForumReply[];
}

export type ReportReason = "spam" | "abuse" | "off_topic" | "other";
export type ModAction = "hide" | "unhide" | "delete" | "restore";

export const forums = {
  postingState: () =>
    request<{ posting_enabled: boolean }>("/api/v1/forums/posting-state"),

  categories: () => request<ForumCategory[]>("/api/v1/forums/categories"),

  threads: (slug: string, limit = 20, offset = 0) =>
    request<ThreadList>(
      `/api/v1/forums/categories/${slug}/threads?limit=${limit}&offset=${offset}`,
    ),

  thread: (id: string, limit = 50, offset = 0) =>
    request<ThreadDetail>(
      `/api/v1/forums/threads/${id}?limit=${limit}&offset=${offset}`,
    ),

  createThread: (slug: string, title: string, body: string) =>
    request<ThreadSummary>(`/api/v1/forums/categories/${slug}/threads`, {
      method: "POST",
      body: JSON.stringify({ title, body }),
    }),

  createReply: (threadId: string, body: string) =>
    request<ForumReply>(`/api/v1/forums/threads/${threadId}/replies`, {
      method: "POST",
      body: JSON.stringify({ body }),
    }),

  report: (targetType: "thread" | "reply", targetId: string, reason: ReportReason) =>
    request<{ reported: boolean; already: boolean; auto_hidden: boolean }>(
      "/api/v1/forums/report",
      {
        method: "POST",
        body: JSON.stringify({ target_type: targetType, target_id: targetId, reason }),
      },
    ),

  moderate: (targetType: "thread" | "reply", targetId: string, action: ModAction) =>
    request<{ hidden: boolean; deleted: boolean }>("/api/v1/forums/moderation/act", {
      method: "POST",
      body: JSON.stringify({ target_type: targetType, target_id: targetId, action }),
    }),

  reportQueue: () =>
    request<
      { id: string; target_type: string; target_id: string; reason: string; detail: string }[]
    >("/api/v1/forums/moderation/reports"),
};
