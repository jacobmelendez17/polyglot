// Feedback / support + onboarding.
import { request } from "./http";

export type FeedbackCategory = "bug" | "feature" | "question" | "other";

export interface FeedbackTicket {
  id: string;
  category: string;
  body: string;
  route: string;
  browser: string;
  state: string;
  pinned: boolean;
  from_name: string;
  from_email: string;
  admin_response: string;
  responded_at: string | null;
  email_sent: boolean;
  created_at: string | null;
}

export interface FeedbackList {
  total: number;
  limit: number;
  offset: number;
  tickets: FeedbackTicket[];
  counts: { unanswered: number; answered: number; pinned: number };
}

export const feedback = {
  submit: (
    category: FeedbackCategory, body: string, route: string, browser: string,
  ) =>
    request<{ id: string; state: string }>("/api/v1/feedback", {
      method: "POST",
      body: JSON.stringify({ category, body, route, browser }),
    }),

  list: (state?: "unanswered" | "answered", pinned?: boolean) => {
    const q = new URLSearchParams();
    if (state) q.set("state", state);
    if (pinned !== undefined) q.set("pinned", String(pinned));
    const qs = q.toString();
    return request<FeedbackList>(`/api/v1/admin/feedback${qs ? `?${qs}` : ""}`);
  },

  respond: (id: string, response: string) =>
    request<FeedbackTicket>(`/api/v1/admin/feedback/${id}/respond`, {
      method: "POST",
      body: JSON.stringify({ response }),
    }),

  pin: (id: string, pinned: boolean) =>
    request<FeedbackTicket>(`/api/v1/admin/feedback/${id}/pin`, {
      method: "POST",
      body: JSON.stringify({ pinned }),
    }),
};

export const onboarding = {
  state: () => request<{ completed: boolean }>("/api/v1/me/onboarding"),
  complete: () =>
    request<{ completed: boolean }>("/api/v1/me/onboarding/complete", {
      method: "POST",
    }),
};
