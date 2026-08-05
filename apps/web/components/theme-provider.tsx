"use client";

// Applies the learner's appearance settings app-wide (spec §16). On mount it paints
// the cached appearance immediately (no flash), then reconciles with /me/settings
// once auth is available. While the preference is "system", it follows OS
// light/dark changes live. Renders nothing — it only manages <html> attributes.

import { useEffect } from "react";
import { account } from "@/lib/account-api";
import { applyAppearance, loadAppearance } from "@/lib/appearance";

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    const cached = loadAppearance();
    if (cached) applyAppearance(cached);

    // Reconcile with the server (ignored if unauthenticated / offline).
    account.getSettings()
      .then((s) => applyAppearance({ theme: s.theme, font_size: s.font_size, color_theme: s.color_theme }))
      .catch(() => { /* keep the cached/default appearance */ });

    // Follow OS theme changes while the preference is "system".
    const mq = window.matchMedia?.("(prefers-color-scheme: dark)");
    const onChange = () => {
      const current = loadAppearance();
      if (current && current.theme === "system") applyAppearance(current);
    };
    mq?.addEventListener?.("change", onChange);
    return () => mq?.removeEventListener?.("change", onChange);
  }, []);

  return <>{children}</>;
}
