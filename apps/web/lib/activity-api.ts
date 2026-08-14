// Review-activity series for the dashboard line graph (slice 46).
import { request } from "./http";

export interface ActivityBucket {
  label: string;
  count: number;
  iso: string;
}

export interface ActivitySeries {
  seven_day: ActivityBucket[];
  twenty_four_hour: ActivityBucket[];
}

export const activityApi = {
  get: () => request<ActivitySeries>("/api/v1/me/reviews/activity"),
};
