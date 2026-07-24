"use client";

// Enter twice: once to answer, once to move on.
//
// The first Enter is handled by the answer input itself (it submits). This hook
// covers the second: while the feedback panel is showing, Enter advances to the
// next prompt without reaching for the mouse.
//
// Three things it deliberately refuses to do:
//   * fire on key auto-repeat — holding Enter must not skip through a session
//   * fire on the same keypress that submitted — a short arming delay after the
//     feedback panel appears absorbs any event-ordering surprises
//   * double-fire when the Continue button has focus — the native click already
//     handles that, so keystrokes originating on a button/link are left alone
//
// The button stays visible and focusable throughout: the shortcut is an
// accelerator, never the only way through.

import { useEffect, useRef } from "react";

/** How long after the feedback panel appears before Enter is accepted. */
export const ENTER_ARM_DELAY_MS = 150;

export interface EnterAdvanceOptions {
  /** True while the "continue" step is on screen. */
  active: boolean;
  /** Called when Enter should advance to the next prompt. */
  onAdvance: () => void;
  /** Override the arming delay (tests use 0). */
  armDelayMs?: number;
}

export function useEnterAdvance({
  active,
  onAdvance,
  armDelayMs = ENTER_ARM_DELAY_MS,
}: EnterAdvanceOptions): void {
  const armedAt = useRef(0);
  const advance = useRef(onAdvance);
  advance.current = onAdvance;

  useEffect(() => {
    if (active) armedAt.current = Date.now();
  }, [active]);

  useEffect(() => {
    if (!active) return;

    function onKeyDown(event: KeyboardEvent) {
      if (event.key !== "Enter") return;
      if (event.repeat) return;
      if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
      if (Date.now() - armedAt.current < armDelayMs) return;

      const target = event.target as HTMLElement | null;
      if (target) {
        if (target.tagName === "TEXTAREA" || target.isContentEditable) return;
        if (typeof target.closest === "function"
            && target.closest("button, a, [role='button']")) {
          return; // the element's own activation handles it
        }
      }

      event.preventDefault();
      advance.current();
    }

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [active, armDelayMs]);
}
