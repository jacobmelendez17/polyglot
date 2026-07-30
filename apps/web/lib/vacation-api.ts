// Vacation / pause mode.
import { request } from "./http";

export interface VacationState {
  paused: boolean;
  since: string | null;
  days: number;
}

export interface ResumeResult extends VacationState {
  resumed: boolean;
  shifted: number;
  shift_seconds: number;
}

export const vacation = {
  state: () => request<VacationState>("/api/v1/me/vacation"),
  pause: () => request<VacationState>("/api/v1/me/vacation/pause", { method: "POST" }),
  resume: () => request<ResumeResult>("/api/v1/me/vacation/resume", { method: "POST" }),
};
