// Pure, deterministic timing for the "being written" hero greeting (slice 36).
//
// The greeting is drawn as real single-stroke handwriting: each stroke path is
// revealed with stroke-dashoffset, and the strokes fire in order at a CONSTANT
// pen speed, so the pen appears to travel across the word evenly regardless of
// how long each letter is. This module owns that scheduling maths (no DOM, no
// React) so it stays unit-testable; the SVG path data lives in hero-strokes.ts
// and the component in components/handwritten-greeting.tsx consumes both.

// Filler feel (§36) — tune freely; nothing else depends on the values.
/** Pen speed in stroke-length units per millisecond. Higher = faster writing. */
export const PEN_SPEED = 0.19;
/** How long the finished word rests before it starts to erase (ms). */
export const HOLD_MS = 1200;
/** Erase happens faster than writing — this is the multiplier on write time. */
export const ERASE_RATIO = 0.55;

/** Time to write a whole word of total stroke length `totalLen` (ms). */
export function writeMs(totalLen: number, speed: number = PEN_SPEED): number {
  if (totalLen <= 0) return 0;
  return totalLen / speed;
}

/** Time to erase a word (a fraction of its write time). */
export function eraseMs(totalLen: number, speed: number = PEN_SPEED): number {
  return writeMs(totalLen, speed) * ERASE_RATIO;
}

/** Full cycle for one greeting: write → hold → erase. */
export function cycleMs(
  totalLen: number,
  hold: number = HOLD_MS,
  speed: number = PEN_SPEED,
): number {
  return writeMs(totalLen, speed) + hold + eraseMs(totalLen, speed);
}

export interface StrokeSchedule {
  /** ms after the phase starts that this stroke begins animating. */
  delay: number;
  /** ms this stroke takes to draw (∝ its length → constant pen speed). */
  dur: number;
}

/**
 * Constant-speed schedule for a sequence of stroke lengths across `totalMs`.
 * Stroke i runs for (len_i / Σlen) * totalMs and starts when i-1 finishes, so
 * the pen never pauses and never races. Returned in the SAME order as `lens`
 * (writing draws start→end; erasing reuses this order start→end so the word
 * disappears left-to-right like a wipe).
 */
export function strokeSchedule(lens: number[], totalMs: number): StrokeSchedule[] {
  const sum = lens.reduce((a, l) => a + l, 0);
  if (sum <= 0 || totalMs <= 0) return lens.map(() => ({ delay: 0, dur: 0 }));
  const out: StrokeSchedule[] = [];
  let acc = 0;
  for (const len of lens) {
    const delay = (acc / sum) * totalMs;
    const dur = (len / sum) * totalMs;
    out.push({ delay: +delay.toFixed(2), dur: +dur.toFixed(2) });
    acc += len;
  }
  return out;
}
