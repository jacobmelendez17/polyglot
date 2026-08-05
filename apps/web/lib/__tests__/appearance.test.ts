/** Appearance — pure theme resolution + DOM application. */
import { applyAppearance, COLOR_THEMES, resolveTheme } from "../appearance";

describe("resolveTheme", () => {
  it("honours explicit light/dark", () => {
    expect(resolveTheme("dark", false)).toBe("dark");
    expect(resolveTheme("light", true)).toBe("light");
  });
  it("follows the system preference for 'system'", () => {
    expect(resolveTheme("system", true)).toBe("dark");
    expect(resolveTheme("system", false)).toBe("light");
  });
  it("treats unknown as system", () => {
    expect(resolveTheme("whatever", true)).toBe("dark");
  });
});

describe("applyAppearance", () => {
  beforeEach(() => {
    document.documentElement.removeAttribute("data-theme");
    document.documentElement.removeAttribute("data-color-theme");
    document.documentElement.removeAttribute("data-font-size");
    localStorage.clear();
  });

  it("sets the html attributes and persists", () => {
    applyAppearance({ theme: "light", font_size: "lg", color_theme: "selva" });
    const root = document.documentElement;
    expect(root.getAttribute("data-theme")).toBe("light");
    expect(root.getAttribute("data-color-theme")).toBe("selva");
    expect(root.getAttribute("data-font-size")).toBe("lg");
    expect(JSON.parse(localStorage.getItem("polyglot-appearance")!).color_theme).toBe("selva");
  });

  it("falls back to safe defaults for unknown values", () => {
    applyAppearance({ theme: "light", font_size: "huge", color_theme: "neon" });
    const root = document.documentElement;
    expect(root.getAttribute("data-color-theme")).toBe("terraza");
    expect(root.getAttribute("data-font-size")).toBe("md");
  });

  it("exposes the available color themes", () => {
    expect(COLOR_THEMES).toContain("terraza");
    expect(COLOR_THEMES).toContain("jacaranda");
    expect(COLOR_THEMES.length).toBeGreaterThanOrEqual(4);
  });
});
