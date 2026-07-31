// Community journals client.
import { request } from "./http";

export interface MyEntry {
  id: string; title: string; excerpt: string;
  shared: boolean; share_hidden: boolean; shared_at: string | null; feedback_count: number;
}
export interface FeedItem {
  id: string; author: string; title: string; excerpt: string;
  shared_at: string | null; feedback_count: number;
}
export interface Feedback {
  id: string; author: string; body: string; hidden: boolean; created_at: string | null;
}
export interface CommunityEntry {
  id: string; author: string; title: string; body: string;
  shared_at: string | null; share_hidden: boolean; is_owner: boolean; feedback: Feedback[];
}

export const communityJournals = {
  mine: () => request<MyEntry[]>("/api/v1/me/community-journals/mine"),
  share: (id: string) =>
    request<{ id: string; shared: boolean }>(`/api/v1/me/community-journals/${id}/share`, { method: "POST" }),
  unshare: (id: string) =>
    request<{ id: string; shared: boolean }>(`/api/v1/me/community-journals/${id}/unshare`, { method: "POST" }),
  feed: () => request<FeedItem[]>("/api/v1/community/journals"),
  entry: (id: string) => request<CommunityEntry>(`/api/v1/community/journals/${id}`),
  postFeedback: (id: string, body: string) =>
    request<Feedback>(`/api/v1/community/journals/${id}/feedback`,
      { method: "POST", body: JSON.stringify({ body }) }),
  hideFeedback: (id: string, hidden: boolean, reason?: string) =>
    request<{ id: string; hidden: boolean }>(`/api/v1/community/feedback/${id}/hide`,
      { method: "POST", body: JSON.stringify({ hidden, reason }) }),
  hideEntry: (id: string, hidden: boolean, reason?: string) =>
    request<{ id: string; share_hidden: boolean }>(`/api/v1/community/journals/${id}/hide`,
      { method: "POST", body: JSON.stringify({ hidden, reason }) }),
};
