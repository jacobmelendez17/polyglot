/** Landing content — shape + coverage. */
import {
  GREETINGS,
  PRACTICE_FEATURES,
  SRS_STAGES,
  TESTIMONIALS,
} from "../landing-content";

describe("landing content", () => {
  it("has a broad, multilingual set of greetings", () => {
    expect(GREETINGS.length).toBeGreaterThanOrEqual(12);
    const langs = GREETINGS.map((g) => g.lang);
    expect(langs).toContain("español");
    expect(langs).toContain("tagalog");
    // every greeting has non-empty text + language label
    GREETINGS.forEach((g) => {
      expect(g.text.length).toBeGreaterThan(0);
      expect(g.lang.length).toBeGreaterThan(0);
    });
  });

  it("mirrors the app's five SRS tiers in order", () => {
    expect(SRS_STAGES.map((s) => s.name)).toEqual([
      "beginner", "familiar", "intermediate", "advanced", "fluent",
    ]);
  });

  it("covers the core practice surfaces", () => {
    const titles = PRACTICE_FEATURES.map((f) => f.title);
    for (const t of ["listening", "speaking", "reading", "writing", "verb conjugation"]) {
      expect(titles).toContain(t);
    }
    PRACTICE_FEATURES.forEach((f) => {
      expect(f.icon).toBeTruthy();
      expect(f.blurb.length).toBeGreaterThan(0);
    });
  });

  it("has sample testimonials with the fields the page renders", () => {
    expect(TESTIMONIALS.length).toBeGreaterThanOrEqual(3);
    TESTIMONIALS.forEach((t) => {
      expect(t.name).toBeTruthy();
      expect(t.role).toBeTruthy();
      expect(t.quote.length).toBeGreaterThan(0);
    });
  });
});
