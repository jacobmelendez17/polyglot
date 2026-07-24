// Dashboard layout + guided tour state.
import { request } from "./http";
import type { CatalogEntry, Layout, LayoutEntry } from "./widget-layout";

export type { CatalogEntry, Layout, LayoutEntry };

export interface DashboardConfig {
  layout: Layout;
  catalog: CatalogEntry[];
  grid_columns: number;
  max_widgets: number;
}

export interface TourState {
  tour_key: string;
  step_index: number;
  completed: boolean;
  skipped: boolean;
  completed_at: string | null;
}

export const dashboard = {
  get: () => request<DashboardConfig>("/api/v1/me/dashboard"),

  save: (widgets: LayoutEntry[]) =>
    request<DashboardConfig>("/api/v1/me/dashboard", {
      method: "PUT",
      body: JSON.stringify({ widgets, version: 1 }),
    }),

  reset: () =>
    request<DashboardConfig>("/api/v1/me/dashboard/reset", { method: "POST" }),
};

export const tours = {
  get: (key: string) => request<TourState>(`/api/v1/me/tours/${key}`),

  step: (key: string, stepIndex: number) =>
    request<TourState>(`/api/v1/me/tours/${key}/step`, {
      method: "POST",
      body: JSON.stringify({ step_index: stepIndex }),
    }),

  complete: (key: string, skipped: boolean) =>
    request<TourState>(`/api/v1/me/tours/${key}/complete`, {
      method: "POST",
      body: JSON.stringify({ skipped }),
    }),

  restart: (key: string) =>
    request<TourState>(`/api/v1/me/tours/${key}/restart`, { method: "POST" }),
};
