"use client";

// HandwrittenGreeting (slice 36) — the hero's "say ___ to fluency" word,
// genuinely *drawn* like handwriting.
//
// Each greeting is a set of single-stroke cursive paths (lib/hero-strokes.ts).
// We reveal them with stroke-dashoffset, one stroke after another at a constant
// pen speed (lib/handwrite.ts), so the pen appears to travel across the word
// and write it. After a hold it erases (the strokes un-draw left→right, like a
// wipe) and the next language is written. No emojis, no font dependency — just
// static path data + CSS.
//
// Accessibility:
//   • The drawn SVG is aria-hidden; a stable screen-reader-only word ("hello")
//     keeps the headline reading "say hello to fluency" regardless of language.
//   • Under prefers-reduced-motion there is NO drawing/erasing: the word is
//     shown fully drawn (static) and simply swapped on a slow timer. Content is
//     never hidden behind motion (the slice 27–29 lesson).

import { useEffect, useMemo, useRef, useState } from "react";
import { HERO_WORDS, type HeroWord } from "@/lib/hero-strokes";
import {
  HOLD_MS,
  cycleMs,
  eraseMs,
  strokeSchedule,
  writeMs,
} from "@/lib/handwrite";

type Phase = "writing" | "holding" | "erasing";

const REDUCED_ROTATE_MS = 2800;

export function HandwrittenGreeting({
  words = HERO_WORDS,
  label = "hello",
  className = "",
  /** Cap height of the drawn word, in em relative to the headline font-size. */
  heightEm = 0.82,
}: {
  words?: HeroWord[];
  label?: string;
  className?: string;
  heightEm?: number;
}) {
  const [index, setIndex] = useState(0);
  const [phase, setPhase] = useState<Phase>("writing");
  const [reduced, setReduced] = useState(false);
  const timers = useRef<number[]>([]);

  const n = words.length;
  const word = words[index] ?? words[0];

  const lens = useMemo(() => word.strokes.map((s) => s.len), [word]);
  const wMs = useMemo(() => writeMs(word.totalLen), [word]);
  const eMs = useMemo(() => eraseMs(word.totalLen), [word]);
  const writeSched = useMemo(() => strokeSchedule(lens, wMs), [lens, wMs]);
  const eraseSched = useMemo(() => strokeSchedule(lens, eMs), [lens, eMs]);

  // Watch reduced-motion (and react if it changes at runtime).
  useEffect(() => {
    const mq = window.matchMedia?.("(prefers-reduced-motion: reduce)");
    if (!mq) return;
    const sync = () => setReduced(mq.matches);
    sync();
    mq.addEventListener?.("change", sync);
    return () => mq.removeEventListener?.("change", sync);
  }, []);

  // Reduced motion: no draw/erase — just swap the static word on a slow timer.
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
    const at = (fn: () => void, ms: number) =>
      timers.current.push(window.setTimeout(fn, ms));
    at(() => setPhase("holding"), wMs);
    at(() => setPhase("erasing"), wMs + HOLD_MS);
    at(() => setIndex((i) => (i + 1) % n), cycleMs(word.totalLen));
    return clear;
  }, [index, reduced, n, wMs, word.totalLen]);

  const [vx, vy, vw, vh] = word.vb;
  const svgStyle = {
    height: `${heightEm}em`,
    width: `${(heightEm * word.aspect).toFixed(3)}em`,
  } as const;

  // Shared path attrs.
  const commonPath = {
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.3,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    vectorEffect: "non-scaling-stroke" as const,
  };

  // ---- reduced-motion render: static, fully-drawn word -------------------
  if (reduced) {
    return (
      <span className={`inline-flex items-baseline text-terraza-accent ${className}`}>
        <svg
          key={index}
          aria-hidden
          viewBox={`${vx} ${vy} ${vw} ${vh}`}
          style={svgStyle}
          className="overflow-visible"
          role="presentation"
        >
          {word.strokes.map((s, i) => (
            <path key={i} d={s.d} transform={`translate(${s.t[0]} ${s.t[1]})`} {...commonPath} />
          ))}
        </svg>
        <span className="sr-only">{label}</span>
      </span>
    );
  }

  // ---- animated render: draw / hold / erase ------------------------------
  const drawing = phase === "writing";
  const erasing = phase === "erasing";

  return (
    <span className={`inline-flex items-baseline text-terraza-accent ${className}`}>
      <svg
        key={index}
        aria-hidden
        viewBox={`${vx} ${vy} ${vw} ${vh}`}
        style={svgStyle}
        className="overflow-visible"
        role="presentation"
      >
        {word.strokes.map((s, i) => {
          const sched = erasing ? eraseSched[i] : writeSched[i];
          // Base state per phase:
          //  • writing  → hidden (offset = len), animate to 0
          //  • holding  → fully drawn (offset 0), no animation
          //  • erasing  → drawn (offset 0), animate to len (un-draw)
          const baseOffset = drawing ? s.len : 0;
          const anim = drawing
            ? `hw-draw ${sched.dur}ms linear ${sched.delay}ms both`
            : erasing
              ? `hw-undraw ${sched.dur}ms linear ${sched.delay}ms both`
              : undefined;
          return (
            <path
              key={i}
              d={s.d}
              transform={`translate(${s.t[0]} ${s.t[1]})`}
              {...commonPath}
              style={{
                // custom prop consumed by the keyframes for the "to"/"from" len
                ["--len" as string]: `${s.len}`,
                strokeDasharray: `${s.len} ${s.len + 1}`,
                strokeDashoffset: baseOffset,
                animation: anim,
              }}
            />
          );
        })}
      </svg>
      <span className="sr-only">{label}</span>
    </span>
  );
}
