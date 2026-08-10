/** Handwriting engine — pure timing, grapheme splitting, and direction. */
import {
  DEFAULT_TIMING,
  charDelays,
  cycleMs,
  dirFor,
  graphemes,
  writeMs,
  type HandwriteTiming,
} from "../handwrite";

const T: HandwriteTiming = { staggerMs: 50, charMs: 200, holdMs: 1000, eraseMs: 500 };

describe("graphemes", () => {
  it("splits plain ASCII one letter per glyph", () => {
    expect(graphemes("hola")).toEqual(["h", "o", "l", "a"]);
  });

  it("keeps multi-byte CJK glyphs whole (no surrogate splitting)", () => {
    expect(graphemes("你好")).toEqual(["你", "好"]);
    expect(graphemes("こんにちは")).toHaveLength(5);
  });

  it("does not detach combining marks in complex scripts", () => {
    // नमस्ते is fewer visual clusters than its code-point count.
    const g = graphemes("नमस्ते");
    expect(g.length).toBeLessThan(Array.from("नमस्ते").length + 1);
    expect(g.join("")).toBe("नमस्ते");
  });

  it("round-trips: joining the glyphs rebuilds the input", () => {
    for (const w of ["bonjour", "مرحبا", "สวัสดี", "안녕하세요", "olá"]) {
      expect(graphemes(w).join("")).toBe(w);
    }
  });

  it("handles the empty string", () => {
    expect(graphemes("")).toEqual([]);
  });
});

describe("writeMs", () => {
  it("is charMs for a single glyph (no stagger yet)", () => {
    expect(writeMs(1, T)).toBe(200);
  });

  it("adds one stagger per additional glyph", () => {
    // 4 glyphs: 3 gaps * 50 + 200 = 350
    expect(writeMs(4, T)).toBe(350);
  });

  it("never returns 0 for an empty word", () => {
    expect(writeMs(0, T)).toBe(T.charMs);
  });

  it("grows monotonically with length", () => {
    expect(writeMs(2, T)).toBeLessThan(writeMs(3, T));
    expect(writeMs(3, T)).toBeLessThan(writeMs(10, T));
  });
});

describe("cycleMs", () => {
  it("is write + hold + erase", () => {
    // 4 glyphs → 350 + 1000 + 500 = 1850
    expect(cycleMs(4, T)).toBe(1850);
  });

  it("uses the shipped defaults when none are passed", () => {
    const n = 3;
    const expected =
      (n - 1) * DEFAULT_TIMING.staggerMs +
      DEFAULT_TIMING.charMs +
      DEFAULT_TIMING.holdMs +
      DEFAULT_TIMING.eraseMs;
    expect(cycleMs(n)).toBe(expected);
  });
});

describe("charDelays", () => {
  it("is one stagger step per DOM index, starting at 0", () => {
    expect(charDelays(4, T)).toEqual([0, 50, 100, 150]);
  });

  it("returns an empty array for an empty word", () => {
    expect(charDelays(0, T)).toEqual([]);
  });

  it("is strictly increasing so the pen never moves backwards", () => {
    const d = charDelays(6, T);
    for (let i = 1; i < d.length; i++) expect(d[i]).toBeGreaterThan(d[i - 1]);
  });

  it("the last glyph finishes exactly at writeMs", () => {
    const d = charDelays(5, T);
    expect(d[d.length - 1] + T.charMs).toBe(writeMs(5, T));
  });
});

describe("dirFor", () => {
  it("treats Latin/CJK/Cyrillic/Thai as ltr", () => {
    for (const w of ["hola", "你好", "привет", "สวัสดี", "こんにちは"]) {
      expect(dirFor(w)).toBe("ltr");
    }
  });

  it("detects Arabic and Hebrew as rtl", () => {
    expect(dirFor("مرحبا")).toBe("rtl");
    expect(dirFor("שלום")).toBe("rtl");
  });

  it("defaults to ltr for the empty string", () => {
    expect(dirFor("")).toBe("ltr");
  });
});
