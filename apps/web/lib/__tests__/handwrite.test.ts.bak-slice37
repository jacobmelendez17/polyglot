/** Handwriting stroke timing — pure, deterministic scheduling. */
import {
  ERASE_RATIO,
  HOLD_MS,
  PEN_SPEED,
  cycleMs,
  eraseMs,
  strokeSchedule,
  writeMs,
} from "../handwrite";

describe("writeMs", () => {
  it("is length / pen speed", () => {
    expect(writeMs(190, 0.19)).toBeCloseTo(1000, 5);
  });
  it("is 0 for an empty word", () => {
    expect(writeMs(0)).toBe(0);
  });
  it("grows with length at constant speed", () => {
    expect(writeMs(100)).toBeLessThan(writeMs(300));
    // twice the ink → twice the time
    expect(writeMs(200)).toBeCloseTo(writeMs(100) * 2, 5);
  });
});

describe("eraseMs", () => {
  it("is a fraction of write time", () => {
    expect(eraseMs(200)).toBeCloseTo(writeMs(200) * ERASE_RATIO, 5);
    expect(eraseMs(200)).toBeLessThan(writeMs(200));
  });
});

describe("cycleMs", () => {
  it("is write + hold + erase", () => {
    const total = 200;
    expect(cycleMs(total)).toBeCloseTo(writeMs(total) + HOLD_MS + eraseMs(total), 5);
  });
  it("uses the shipped defaults", () => {
    expect(cycleMs(190)).toBeCloseTo(190 / PEN_SPEED + HOLD_MS + (190 / PEN_SPEED) * ERASE_RATIO, 5);
  });
});

describe("strokeSchedule", () => {
  it("gives each stroke a slice of time proportional to its length", () => {
    const s = strokeSchedule([100, 100], 1000);
    expect(s).toHaveLength(2);
    expect(s[0]).toEqual({ delay: 0, dur: 500 });
    expect(s[1]).toEqual({ delay: 500, dur: 500 });
  });

  it("keeps a constant pen speed with uneven letters", () => {
    // 1 : 3 length ratio → 1 : 3 time ratio, back to back.
    const s = strokeSchedule([50, 150], 800);
    expect(s[0].dur).toBeCloseTo(200, 5);
    expect(s[1].dur).toBeCloseTo(600, 5);
    expect(s[1].delay).toBeCloseTo(200, 5); // starts exactly when #0 ends
  });

  it("starts at 0 and each stroke follows the previous with no gap", () => {
    const s = strokeSchedule([30, 40, 50], 1200);
    expect(s[0].delay).toBe(0);
    for (let i = 1; i < s.length; i++) {
      expect(s[i].delay).toBeCloseTo(s[i - 1].delay + s[i - 1].dur, 2);
    }
  });

  it("the last stroke finishes exactly at totalMs", () => {
    const s = strokeSchedule([30, 40, 50], 1200);
    const last = s[s.length - 1];
    expect(last.delay + last.dur).toBeCloseTo(1200, 2);
  });

  it("degrades safely for empty / zero inputs", () => {
    expect(strokeSchedule([], 1000)).toEqual([]);
    expect(strokeSchedule([10, 20], 0)).toEqual([{ delay: 0, dur: 0 }, { delay: 0, dur: 0 }]);
    expect(strokeSchedule([0, 0], 1000)).toEqual([{ delay: 0, dur: 0 }, { delay: 0, dur: 0 }]);
  });
});
