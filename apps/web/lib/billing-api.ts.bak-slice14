// Subscriptions, billing, and the dev sandbox.
import { request } from "./http";

export interface Entitlement {
  status: string;
  full_access: boolean;
  max_free_level: number;
  access_until: string | null;
  cancel_at_period_end: boolean;
  price_interval: string | null;
  prices: Record<string, string>;
}

export interface DevState {
  dev_mode: boolean;
  srs_scale: number;
  srs_scale_description: string;
  presets: Record<string, number>;
}

export const subscription = {
  get: () => request<Entitlement>("/api/v1/me/subscription"),

  checkout: (interval: "month" | "year") =>
    request<{ url: string }>("/api/v1/me/subscription/checkout", {
      method: "POST",
      body: JSON.stringify({ interval }),
    }),

  portal: () =>
    request<{ url: string }>("/api/v1/me/subscription/portal", { method: "POST" }),
};

export const dev = {
  state: () => request<DevState>("/api/v1/dev/state"),

  setMode: (enabled: boolean, scale?: string) =>
    request<DevState>("/api/v1/dev/mode", {
      method: "PUT",
      body: JSON.stringify({ enabled, scale }),
    }),

  unlockAll: (upToLevel?: number) =>
    request<{ ok: boolean; detail: { unlocked: number } }>(
      "/api/v1/dev/unlock-all",
      { method: "POST", body: JSON.stringify({ up_to_level: upToLevel ?? null }) },
    ),

  makeReviewsDue: () =>
    request<{ ok: boolean; detail: { made_due: number } }>(
      "/api/v1/dev/make-reviews-due",
      { method: "POST" },
    ),

  setStage: (itemType: "vocabulary" | "grammar", itemId: string, stage: number) =>
    request<{ ok: boolean; detail: Record<string, unknown> }>(
      "/api/v1/dev/set-stage",
      { method: "POST", body: JSON.stringify({ item_type: itemType, item_id: itemId, stage }) },
    ),
};
