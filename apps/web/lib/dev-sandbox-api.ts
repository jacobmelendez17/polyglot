// Admin dev sandbox client (troubleshooting practices and reviews).
//
// Split out of billing-api.ts (which is now the billing/subscription client) so
// this doesn't collide with that file's purpose again. Every route it calls is
// gated server-side on the `dev_panel` capability.
import { request } from "./http";

export interface DevState {
  dev_mode: boolean;
  srs_scale: number;
  srs_scale_description: string;
  presets: Record<string, number>;
}

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

  resetProgress: () =>
    request<{ ok: boolean; detail: Record<string, unknown> }>(
      "/api/v1/dev/reset-progress",
      { method: "POST" },
    ),

  setStage: (itemType: "vocabulary" | "grammar", itemId: string, stage: number) =>
    request<{ ok: boolean; detail: Record<string, unknown> }>(
      "/api/v1/dev/set-stage",
      { method: "POST", body: JSON.stringify({ item_type: itemType, item_id: itemId, stage }) },
    ),
};
