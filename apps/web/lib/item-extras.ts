// Item notes + review-time formatting (slice 44). Kept in its own module so the
// item page can import without pulling the whole items-api surface.
import { request } from "./http";

export const MAX_NOTE_WORDS = 250;

export interface ItemNote {
  body: string;
  updated_at: string | null;
}

export const itemNotes = {
  get: (type: string, id: string) =>
    request<ItemNote>(`/api/v1/items/${type}/${id}/note`),
  save: (type: string, id: string, body: string) =>
    request<ItemNote>(`/api/v1/items/${type}/${id}/note`, {
      method: "PUT",
      body: JSON.stringify({ body }),
    }),
};

export function countWords(text: string): number {
  const t = (text || "").trim();
  return t ? t.split(/\s+/).length : 0;
}

/**
 * "<time> until next review", rounded by month / week / day / hour, then
 * "less than an hour", and finally exact minutes in the last five minutes.
 * Returns a full subheader string, e.g. "4 minutes until next review" or
 * "review available now".
 */
export function timeUntilReview(iso: string | null, now: number = Date.now()): string {
  if (!iso) return "no review scheduled";
  const target = new Date(iso).getTime();
  if (Number.isNaN(target)) return "no review scheduled";
  const ms = target - now;
  if (ms <= 0) return "review available now";

  const mins = ms / 60000;
  const hours = ms / 3_600_000;
  const days = ms / 86_400_000;

  const plural = (n: number, unit: string) => `${n} ${unit}${n === 1 ? "" : "s"} until next review`;

  if (mins <= 5) return plural(Math.max(1, Math.round(mins)), "minute");
  if (mins < 60) return "less than an hour until next review";
  if (hours < 24) return plural(Math.round(hours), "hour");
  if (days < 7) return plural(Math.round(days), "day");
  if (days < 30) return plural(Math.max(1, Math.round(days / 7)), "week");
  return plural(Math.max(1, Math.round(days / 30)), "month");
}

/** "13 Aug 2026" style date, or "—" when absent. */
export function shortDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}
