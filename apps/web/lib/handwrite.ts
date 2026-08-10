// A tiny, dependency-free "handwriting" engine for the hero greeting (slice 35).
//
// This module is pure and deterministic — no DOM, no React — so the timing and
// text logic is unit-testable the same way `landing-content.ts` is. The React
// component in `components/handwritten-greeting.tsx` consumes these helpers to
// drive the write → hold → erase → next cycle.
//
// Why our own tiny library instead of an npm handwriting package (e.g. Vara):
// the hero greeting cycles through many scripts — español, tagalog, 日本語,
// 한국어, 中文, العربية, हिन्दी, ไทย … — and the popular handwriting libraries
// ship Latin-only stroke fonts, so the non-Latin greetings would simply not
// render. Reading glyph outlines at runtime (opentype.js) would cover them but
// needs a heavy multi-script font. A per-glyph "ink-in + wipe-erase" reveal, by
// contrast, is script-agnostic, dependency-free, and respects the codebase's
// "CSS-only animation, no new deps" convention. The seam is here if a true
// cursive stroke engine is ever wanted per-language.

export interface HandwriteTiming {
  /** ms between each glyph starting to "ink in" (the pen moving along). */
  staggerMs: number;
  /** ms each individual glyph takes to fully ink in. */
  charMs: number;
  /** ms the fully-written word rests before it starts to erase. */
  holdMs: number;
  /** ms the erase sweep takes. */
  eraseMs: number;
}

// Filler defaults (§36) — tune freely; nothing else depends on these values.
export const DEFAULT_TIMING: HandwriteTiming = {
  staggerMs: 55,
  charMs: 260,
  holdMs: 1100,
  eraseMs: 650,
};

// Runtimes that expose Intl.Segmenter (Node 16+, modern browsers) get correct
// grapheme splitting; others fall back to code-point splitting.
type SegmenterCtor = new (
  locales?: string | string[],
  options?: { granularity?: "grapheme" | "word" | "sentence" },
) => { segment(input: string): Iterable<{ segment: string }> };

/**
 * Split a string into user-perceived characters (graphemes) so multi-byte
 * scripts (你好, नमस्ते, emoji, combining marks) reveal one *visual* glyph at a
 * time instead of splitting surrogate pairs or detaching combining marks.
 * Uses Intl.Segmenter when available, else Array.from (code points).
 */
export function graphemes(text: string): string[] {
  const Seg = (Intl as unknown as { Segmenter?: SegmenterCtor }).Segmenter;
  if (typeof Seg === "function") {
    try {
      const seg = new Seg(undefined, { granularity: "grapheme" });
      return Array.from(seg.segment(text), (s) => s.segment);
    } catch {
      /* fall through to code-point split */
    }
  }
  return Array.from(text);
}

/** How long the writing pass takes for a word of `count` graphemes. */
export function writeMs(count: number, t: HandwriteTiming = DEFAULT_TIMING): number {
  if (count <= 0) return t.charMs;
  return (count - 1) * t.staggerMs + t.charMs;
}

/** Full cycle for one greeting: write → hold → erase. */
export function cycleMs(count: number, t: HandwriteTiming = DEFAULT_TIMING): number {
  return writeMs(count, t) + t.holdMs + t.eraseMs;
}

/**
 * Per-glyph ink-in delay in ms, indexed by DOM order. Visual direction is
 * handled by the `dir` attribute + the RTL keyframe in the component, so the
 * delay is simply `domIndex * stagger` for both scripts (for an RTL word the
 * first DOM child is the visually-rightmost glyph, which should ink first).
 */
export function charDelays(count: number, t: HandwriteTiming = DEFAULT_TIMING): number[] {
  const out: number[] = [];
  for (let i = 0; i < count; i++) out.push(i * t.staggerMs);
  return out;
}

// Hebrew + Arabic (and its supplements) — enough to reveal these the natural way.
const RTL_RE = /[\u0590-\u05FF\u0600-\u06FF\u0700-\u074F\u0750-\u077F\u08A0-\u08FF]/;

/** Rough script direction for a greeting. Decorative-only; defaults to ltr. */
export function dirFor(text: string): "ltr" | "rtl" {
  return RTL_RE.test(text) ? "rtl" : "ltr";
}
