"use client";

// First-time dashboard walkthrough (PLANNING §14).
//
// Speech bubbles point at real elements — the tour finds them by `data-tour`
// attributes rather than rendering fake screenshots, so it can never drift out
// of sync with the UI it is describing. If an anchor is missing (a widget the
// learner removed, say) that step still shows, centred, instead of pointing at
// nothing.
//
// Accessibility, since a modal overlay is easy to get wrong:
//   * the bubble is a labelled dialog and takes focus on every step
//   * Tab is trapped inside it, so you cannot wander into the dimmed page
//   * Escape skips, ← / → move, Enter advances
//   * the step counter is text, not just dots
//   * everything is transform/opacity and stops under prefers-reduced-motion
//   * skipping is always one keystroke or one click away

import { useCallback, useEffect, useRef, useState } from "react";
import { tours, type TourState } from "@/lib/dashboard-api";

export interface TourStep {
  /** The `data-tour` value of the element this step points at. */
  anchor: string;
  title: string;
  body: string;
}

export const DASHBOARD_TOUR: TourStep[] = [
  {
    anchor: "actions",
    title: "lessons and reviews",
    body: "these two buttons are the whole loop. lessons teach new words; reviews bring them back right before you'd forget them.",
  },
  {
    anchor: "widget-progression",
    title: "where everything stands",
    body: "your items spread across nine srs stages, beginner 1 through fluent. the bar fills up as things stick.",
  },
  {
    anchor: "widget-forecast",
    title: "what's coming",
    body: "reviews arriving over the next seven days, so you can see a heavy day before it lands on you.",
  },
  {
    anchor: "nav-levels",
    title: "your curriculum",
    body: "levels holds every word and grammar point, and each level has a progress page showing exactly what you know.",
  },
  {
    anchor: "customize",
    title: "make it yours",
    body: "add, remove, and rearrange these cards. drag them, or use the arrow buttons — either way it saves to your account.",
  },
];

interface Rect { top: number; left: number; width: number; height: number }

const GAP = 12;
const BUBBLE_WIDTH = 320;

function anchorRect(anchor: string): Rect | null {
  if (typeof document === "undefined") return null;
  const el = document.querySelector<HTMLElement>(`[data-tour="${anchor}"]`);
  if (!el) return null;
  const r = el.getBoundingClientRect();
  if (r.width === 0 && r.height === 0) return null;
  return { top: r.top, left: r.left, width: r.width, height: r.height };
}

export function GuidedTour({
  tourKey = "dashboard",
  steps = DASHBOARD_TOUR,
}: { tourKey?: string; steps?: TourStep[] }) {
  const [state, setState] = useState<TourState | null>(null);
  const [running, setRunning] = useState(false);
  const [index, setIndex] = useState(0);
  const [rect, setRect] = useState<Rect | null>(null);
  const bubbleRef = useRef<HTMLDivElement>(null);

  // Decide whether to run at all. A finished tour never restarts on its own.
  useEffect(() => {
    let live = true;
    tours.get(tourKey)
      .then((s) => {
        if (!live) return;
        setState(s);
        if (!s.completed) {
          setIndex(Math.min(s.step_index, steps.length - 1));
          setRunning(true);
        }
      })
      .catch(() => { /* a tour is a nicety; never block the dashboard on it */ });
    return () => { live = false; };
  }, [tourKey, steps.length]);

  const step = steps[index];

  // Track the anchor through scrolls, resizes, and layout settling.
  useEffect(() => {
    if (!running || !step) return;
    const measure = () => setRect(anchorRect(step.anchor));
    measure();
    const timer = window.setTimeout(measure, 60);   // let widgets finish loading
    window.addEventListener("resize", measure);
    window.addEventListener("scroll", measure, true);
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener("resize", measure);
      window.removeEventListener("scroll", measure, true);
    };
  }, [running, step, index]);

  useEffect(() => {
    if (running) bubbleRef.current?.focus();
  }, [running, index]);

  const finish = useCallback((skipped: boolean) => {
    setRunning(false);
    tours.complete(tourKey, skipped).then(setState).catch(() => {});
  }, [tourKey]);

  const goTo = useCallback((next: number) => {
    if (next >= steps.length) { finish(false); return; }
    const clamped = Math.max(0, next);
    setIndex(clamped);
    tours.step(tourKey, clamped).catch(() => {});
  }, [steps.length, finish, tourKey]);

  // Keyboard: Escape skips, arrows move, Enter advances, Tab stays inside.
  useEffect(() => {
    if (!running) return;
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") { e.preventDefault(); finish(true); return; }
      if (e.key === "ArrowRight") { e.preventDefault(); goTo(index + 1); return; }
      if (e.key === "ArrowLeft") { e.preventDefault(); goTo(index - 1); return; }
      if (e.key === "Enter" && e.target === bubbleRef.current) {
        e.preventDefault(); goTo(index + 1); return;
      }
      if (e.key === "Tab") {
        const focusables = bubbleRef.current?.querySelectorAll<HTMLElement>(
          "button, [href], input, select, textarea, [tabindex]:not([tabindex='-1'])",
        );
        if (!focusables || focusables.length === 0) return;
        const first = focusables[0];
        const last = focusables[focusables.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault(); last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault(); first.focus();
        }
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [running, index, goTo, finish]);

  if (!running || !step) {
    // Once the tour is done, offer an explicit way back in. It never replays on
    // its own — but "I clicked through that too fast" deserves an answer.
    if (state?.completed) {
      return (
        <button
          onClick={() => {
            tours.restart(tourKey).then(() => {
              setIndex(0);
              setRunning(true);
            }).catch(() => {});
          }}
          className="text-xs tracking-label text-terraza-soft underline underline-offset-2"
        >
          replay the tour
        </button>
      );
    }
    return null;
  }

  const bubbleStyle = placeBubble(rect);

  return (
    <div className="fixed inset-0 z-50">
      {/* Dimmed backdrop. Clicking it skips — a common expectation, and it is
          never the only way out. */}
      <div
        className="absolute inset-0 bg-terraza-ink/40 transition-opacity duration-200 motion-reduce:transition-none"
        onClick={() => finish(true)}
        aria-hidden="true"
      />

      {/* Spotlight ring around the anchor. */}
      {rect && (
        <div
          aria-hidden="true"
          className="pointer-events-none absolute rounded-card border-2 border-terraza-accent transition-all duration-300 motion-reduce:transition-none"
          style={{
            top: rect.top - 6,
            left: rect.left - 6,
            width: rect.width + 12,
            height: rect.height + 12,
            boxShadow: "0 0 0 9999px rgba(0,0,0,0.28)",
          }}
        />
      )}

      <div
        ref={bubbleRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="tour-title"
        aria-describedby="tour-body"
        tabIndex={-1}
        style={bubbleStyle}
        className="absolute w-[320px] max-w-[calc(100vw-24px)] rounded-card border border-terraza-dash bg-terraza-card p-5 shadow-lg outline-none transition-all duration-300 motion-reduce:transition-none"
      >
        <p className="text-xs tracking-label text-terraza-soft">
          STEP {index + 1} OF {steps.length}
        </p>
        <h2 id="tour-title" className="mt-1 text-lg lowercase tracking-cozy">
          {step.title}
        </h2>
        <p id="tour-body" className="mt-2 text-sm text-terraza-soft">{step.body}</p>

        <div className="mt-4 flex items-center gap-2">
          <span className="flex gap-1" aria-hidden="true">
            {steps.map((s, i) => (
              <span
                key={s.anchor}
                className={`h-1.5 w-1.5 rounded-full ${
                  i === index ? "bg-terraza-accent" : "bg-terraza-pill"
                }`}
              />
            ))}
          </span>

          <button
            onClick={() => finish(true)}
            className="ml-auto rounded-full px-3 py-1.5 text-sm text-terraza-soft hover:bg-terraza-pill"
          >
            skip
          </button>
          {index > 0 && (
            <button
              onClick={() => goTo(index - 1)}
              className="rounded-full bg-terraza-pill px-4 py-1.5 text-sm tracking-cozy"
            >
              back
            </button>
          )}
          <button
            onClick={() => goTo(index + 1)}
            className="rounded-full bg-terraza-accent px-4 py-1.5 text-sm tracking-cozy text-terraza-accentInk"
          >
            {index === steps.length - 1 ? "done" : "next"}
          </button>
        </div>
      </div>
    </div>
  );
}

/** Put the bubble under the anchor, or above it when there's no room below. */
function placeBubble(rect: Rect | null): React.CSSProperties {
  if (typeof window === "undefined" || !rect) {
    return { top: "50%", left: "50%", transform: "translate(-50%, -50%)" };
  }
  const belowSpace = window.innerHeight - (rect.top + rect.height);
  const placeBelow = belowSpace > 220;
  const left = Math.max(
    12, Math.min(rect.left, window.innerWidth - BUBBLE_WIDTH - 12),
  );
  return placeBelow
    ? { top: rect.top + rect.height + GAP, left }
    : { top: Math.max(12, rect.top - 220 - GAP), left };
}
