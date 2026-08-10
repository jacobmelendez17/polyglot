/** Hero stroke data — shape + integrity of the generated handwriting paths. */
import { HERO_WORDS } from "../hero-strokes";

describe("HERO_WORDS", () => {
  it("leads with the app's own languages", () => {
    expect(HERO_WORDS.length).toBeGreaterThanOrEqual(6);
    expect(HERO_WORDS[0].text).toBe("hola");
    expect(HERO_WORDS[0].lang).toBe("español");
    expect(HERO_WORDS.map((w) => w.lang)).toContain("tagalog");
  });

  it("every word has a viewBox, a positive aspect, and strokes", () => {
    for (const w of HERO_WORDS) {
      expect(w.vb).toHaveLength(4);
      expect(w.vb[2]).toBeGreaterThan(0); // width
      expect(w.vb[3]).toBeGreaterThan(0); // height
      expect(w.aspect).toBeGreaterThan(0);
      expect(w.strokes.length).toBeGreaterThan(0);
    }
  });

  it("aspect matches the viewBox ratio (so sizing is correct)", () => {
    for (const w of HERO_WORDS) {
      expect(w.aspect).toBeCloseTo(w.vb[2] / w.vb[3], 2);
    }
  });

  it("totalLen equals the sum of the stroke lengths (constant-speed timing)", () => {
    for (const w of HERO_WORDS) {
      const sum = w.strokes.reduce((a, s) => a + s.len, 0);
      expect(w.totalLen).toBeCloseTo(sum, 0);
    }
  });

  it("every stroke has a non-empty path, a translate, and a positive length", () => {
    for (const w of HERO_WORDS) {
      for (const s of w.strokes) {
        expect(s.d.startsWith("M")).toBe(true);
        expect(s.t).toHaveLength(2);
        expect(s.len).toBeGreaterThan(0);
      }
    }
  });
});
