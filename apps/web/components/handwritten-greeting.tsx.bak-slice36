"use client";

// HandwrittenGreeting (slice 35) — the hero's "say ___ to fluency" word.
//
// Each greeting is "written" (glyphs ink in one at a time, left→right, with a
// travelling pen nib and a hand-lettered UI font), held, then "erased" (a wipe
// sweeps the ink away as a little eraser slides across) before the next
// language takes its place. It cycles through every greeting in the list.
//
// Accessibility:
//   • The animated glyphs are aria-hidden; a stable, screen-reader-only word
//     (default "hello") keeps the headline reading "say hello to fluency" no
//     matter which language is on screen.
//   • Under prefers-reduced-motion there is NO writing/erasing — the plain word
//     is always fully visible and simply cross-rotates on a slow timer. The
//     word text never depends on an animation to be visible (the lesson from
//     slices 27–29: never hide content behind motion).
//   • RTL greetings (e.g. العربية) reveal right→left via the RTL keyframe.
//
// No new dependencies — all motion is CSS keyframes in globals.css referenced
// via inline `animation:` styles, plus the pure timing/text helpers in
// lib/handwrite.ts (which are unit-tested).

import { useEffect, useMemo, useRef, useState } from "react";
import type { Greeting } from "@/lib/landing-content";
import {
  DEFAULT_TIMING,
  charDelays,
  cycleMs,
  dirFor,
  graphemes,
  writeMs,
} from "@/lib/handwrite";

type Phase = "writing" | "holding" | "erasing";

// How fast the plain word rotates when motion is reduced.
const REDUCED_ROTATE_MS = 2600;

export function HandwrittenGreeting({
  greetings,
  label = "hello",
  className = "",
}: {
  greetings: Greeting[];
  /** Stable text read by screen readers in place of the animated word. */
  label?: string;
  className?: string;
}) {
  const [index, setIndex] = useState(0);
  const [phase, setPhase] = useState<Phase>("writing");
  const [reduced, setReduced] = useState(false);
  const timers = useRef<number[]>([]);

  const n = greetings.length;
  const g = greetings[index] ?? { text: "", lang: "" };
  const dir = useMemo(() => dirFor(g.text), [g.text]);
  const glyphs = useMemo(() => graphemes(g.text), [g.text]);
  const delays = useMemo(() => charDelays(glyphs.length), [glyphs.length]);

  // Watch the reduced-motion preference (and react if it changes at runtime).
  useEffect(() => {
    const mq = window.matchMedia?.("(prefers-reduced-motion: reduce)");
    if (!mq) return;
    const sync = () => setReduced(mq.matches);
    sync();
    mq.addEventListener?.("change", sync);
    return () => mq.removeEventListener?.("change", sync);
  }, []);

  // Reduced motion: no write/erase — just cross-rotate the plain word.
  useEffect(() => {
    if (!reduced || n <= 1) return;
    const id = window.setInterval(() => setIndex((i) => (i + 1) % n), REDUCED_ROTATE_MS);
    return () => window.clearInterval(id);
  }, [reduced, n]);

  // Full write → hold → erase → next cycle (re-armed whenever the word changes).
  useEffect(() => {
    if (reduced || n === 0) return;
    const clear = () => {
      timers.current.forEach((t) => window.clearTimeout(t));
      timers.current = [];
    };
    clear();
    setPhase("writing");
    const w = writeMs(glyphs.length);
    const at = (fn: () => void, ms: number) =>
      timers.current.push(window.setTimeout(fn, ms));
    at(() => setPhase("holding"), w);
    at(() => setPhase("erasing"), w + DEFAULT_TIMING.holdMs);
    at(() => setIndex((i) => (i + 1) % n), cycleMs(glyphs.length));
    return clear;
  }, [index, reduced, n, glyphs.length]);

  // ---- reduced-motion render (always-visible plain word) -----------------
  if (reduced) {
    return (
      <span className={`inline-block text-terraza-accent ${className}`}>
        <span aria-hidden lang={g.lang}>
          {g.text}
        </span>
        <span className="sr-only">{label}</span>
      </span>
    );
  }

  // ---- animated render ---------------------------------------------------
  const wWriteMs = writeMs(glyphs.length);

  return (
    <span className={`relative inline-flex items-end text-terraza-accent ${className}`}>
      <span
        key={index}
        aria-hidden
        lang={g.lang}
        dir={dir}
        className="relative inline-flex"
        style={
          phase === "erasing"
            ? { animation: `hw-erase ${DEFAULT_TIMING.eraseMs}ms ease-in forwards` }
            : undefined
        }
      >
        {glyphs.map((ch, i) => (
          <span
            key={i}
            className="inline-block"
            style={
              phase === "writing"
                ? {
                    animation: `${
                      dir === "rtl" ? "hw-write-in-rtl" : "hw-write-in"
                    } ${DEFAULT_TIMING.charMs}ms ease-out both`,
                    animationDelay: `${delays[i]}ms`,
                  }
                : undefined
            }
          >
            {ch === " " ? "\u00A0" : ch}
          </span>
        ))}

        {/* travelling pen nib while writing (LTR only, decorative) */}
        {phase === "writing" && dir === "ltr" && (
          <span
            aria-hidden
            className="pointer-events-none absolute select-none"
            style={{
              top: "-0.55em",
              left: "-0.1em",
              fontSize: "0.5em",
              animation: `hw-nib ${wWriteMs}ms linear forwards`,
            }}
          >
            ✒️
          </span>
        )}

        {/* eraser sliding across while erasing (decorative) */}
        {phase === "erasing" && (
          <span
            aria-hidden
            className="pointer-events-none absolute select-none"
            style={{
              top: "-0.2em",
              left: "-0.1em",
              fontSize: "0.5em",
              animation: `hw-eraser ${DEFAULT_TIMING.eraseMs}ms ease-in forwards`,
            }}
          >
            🧽
          </span>
        )}
      </span>

      {/* stable word for screen readers so the headline always makes sense */}
      <span className="sr-only">{label}</span>
    </span>
  );
}
