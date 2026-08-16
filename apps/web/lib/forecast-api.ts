// Review forecast for the dashboard graphs (slice 47).
import { request } from "./http";

export interface ForecastDay {
  offset: number;
  label: string;   // "today" | "fri" | ...
  date: string;    // ISO date
  count: number;
  hours: number[]; // 24 counts, indexed by hour-of-day
}

export interface ForecastHour {
  label: string;   // "14"
  count: number;
}

export interface ForecastPayload {
  days: ForecastDay[];        // 7
  next_24h: ForecastHour[];   // 24, rolling from the current hour
}

export const forecastApi = {
  get: () => request<ForecastPayload>("/api/v1/me/reviews/forecast"),
};
