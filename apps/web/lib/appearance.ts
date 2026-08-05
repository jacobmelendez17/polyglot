// Appearance application (spec §16). Turns saved settings into the two <html>
// attributes + font-size the theme CSS keys off. `resolveTheme` is pure and tested;
// `applyAppearance` touches the DOM and persists to localStorage so the next load
// paints the right theme immediately (before /me/settings returns).

export interface Appearance {
  theme: string;       // light | dark | system
  font_size: string;   // sm | md | lg | xl
  color_theme: string; // terraza | jacaranda | selva | playa
}

export const COLOR_THEMES = ["terraza", "jacaranda", "selva", "playa"] as const;

const KEY = "polyglot-appearance";

/** Resolve the effective light/dark theme, honouring the "system" preference. */
export function resolveTheme(theme: string, prefersDark: boolean): "light" | "dark" {
  if (theme === "dark") return "dark";
  if (theme === "light") return "light";
  return prefersDark ? "dark" : "light"; // "system" (or anything unknown)
}

function prefersDark(): boolean {
  return typeof window !== "undefined"
    && !!window.matchMedia
    && window.matchMedia("(prefers-color-scheme: dark)").matches;
}

export function applyAppearance(a: Appearance): void {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  root.setAttribute("data-theme", resolveTheme(a.theme, prefersDark()));
  root.setAttribute("data-color-theme",
    (COLOR_THEMES as readonly string[]).includes(a.color_theme) ? a.color_theme : "terraza");
  root.setAttribute("data-font-size", ["sm", "md", "lg", "xl"].includes(a.font_size) ? a.font_size : "md");
  try {
    localStorage.setItem(KEY, JSON.stringify(a));
  } catch {
    /* private mode / storage disabled — the attributes are still applied */
  }
}

export function loadAppearance(): Appearance | null {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as Appearance) : null;
  } catch {
    return null;
  }
}
