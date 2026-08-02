// Analytics events (spec §27). Thin wrapper over Plausible's queue so calls are
// safe whether or not the script is loaded — when it isn't (dev, or a blocker),
// track() is a no-op. Use for the events the spec calls out: signup, lesson/review
// completion, practice usage, demo clicks.

type Props = Record<string, string | number | boolean>;

interface PlausibleWindow {
  plausible?: (event: string, opts?: { props?: Props }) => void;
}

export function track(event: string, props?: Props): void {
  if (typeof window === "undefined") return;
  const w = window as unknown as PlausibleWindow;
  try {
    if (typeof w.plausible === "function") {
      w.plausible(event, props ? { props } : undefined);
    }
    // If the script hasn't initialised yet, silently drop the event rather than
    // buffering — analytics must never affect the user experience.
  } catch {
    /* analytics failures are never surfaced to the user */
  }
}

// Named events used across the app, so call sites don't hand-type strings.
export const AnalyticsEvent = {
  Signup: "signup",
  LessonComplete: "lesson_complete",
  ReviewComplete: "review_complete",
  PracticeStart: "practice_start",
  DemoClick: "demo_click",
} as const;
