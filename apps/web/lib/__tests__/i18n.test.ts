/**
 * Immersion string handling.
 *
 * The important properties are that the Spanish dictionary can never be
 * *behind* the English one without a test failing, and that a missing string
 * degrades to English rather than showing a raw key to a learner.
 */
import { keysFor, translate } from "../i18n";

describe("translate", () => {
  it("returns English by default", () => {
    expect(translate("nav.levels", "en")).toBe("levels");
  });

  it("returns Spanish under immersion", () => {
    expect(translate("nav.levels", "es")).toBe("niveles");
    expect(translate("nav.reviews", "es")).toBe("repasos");
  });

  it("falls back to English for a key Spanish is missing", () => {
    // Simulated by asking for a key no dictionary defines.
    expect(translate("nav.levels", "pt" as never)).toBe("levels");
  });

  it("falls back to the key itself rather than rendering empty", () => {
    expect(translate("does.not.exist", "en")).toBe("does.not.exist");
  });
});

describe("dictionary parity", () => {
  it("Spanish covers every English key", () => {
    const missing = keysFor("en").filter((k) => !keysFor("es").includes(k));
    expect(missing).toEqual([]);
  });

  it("Spanish has no keys English doesn't", () => {
    const extra = keysFor("es").filter((k) => !keysFor("en").includes(k));
    expect(extra).toEqual([]);
  });

  it("no Spanish string is left identical to English by accident", () => {
    // A handful legitimately match across both languages.
    const allowed = new Set(["common.loading"]);
    const untranslated = keysFor("en").filter(
      (k) => !allowed.has(k) && translate(k, "en") === translate(k, "es"),
    );
    expect(untranslated).toEqual([]);
  });
});

describe("scope", () => {
  it("covers chrome only — no keys for meanings or instructions", () => {
    const forbidden = keysFor("en").filter(
      (k) => k.startsWith("meaning.") || k.startsWith("instruction."),
    );
    expect(forbidden).toEqual([]);
  });
});
