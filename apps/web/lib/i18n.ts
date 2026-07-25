"use client";

// Immersion mode: the app's own chrome in Spanish (spec §16).
//
// The scope is deliberately narrow. This dictionary covers navigation, buttons,
// widget labels — the furniture. It does NOT cover:
//
//   * item meanings and translations (translating the answer defeats the point)
//   * lesson and practice instructions (an instruction you can't read is a
//     locked door, not immersion)
//   * anything a user wrote — journals, forum posts, their own synonyms
//   * error messages that explain what went wrong
//
// Keys are English-ish so an untranslated string still reads sensibly, and
// `t()` falls back to English rather than showing a raw key.

import { useCallback, useEffect, useState } from "react";
import { immersion as immersionApi } from "./content-api";

export type Locale = "en" | "es";

type Dict = Record<string, string>;

const EN: Dict = {
  // nav
  "nav.levels": "levels",
  "nav.reviews": "reviews",
  "nav.practice": "practice",
  "nav.dashboard": "dashboard",
  "nav.account": "Account menu",
  "nav.profile": "profile",
  "nav.settings": "settings",
  "nav.admin": "admin",
  "nav.logout": "log out",
  // dashboard
  "dash.lessons": "lessons",
  "dash.reviews": "reviews",
  "dash.customize": "customize dashboard",
  "dash.done_customizing": "done customizing",
  "dash.add_card": "add a card",
  "dash.reset": "reset to default",
  "dash.saving": "saving…",
  "dash.saved": "saved",
  "dash.not_saved": "not saved",
  // common
  "common.start": "start",
  "common.continue": "continue",
  "common.back": "back",
  "common.next": "next",
  "common.skip": "skip",
  "common.close": "close",
  "common.loading": "un momento",
  "common.empty": "nothing here yet",
  // footer
  "footer.product": "Product",
  "footer.features": "features",
  "footer.how": "how it works",
  "footer.pricing": "pricing",
  "footer.changelog": "changelog",
  "footer.resources": "Resources",
  "footer.support": "support",
  "footer.faq": "about & faq",
  "footer.community": "community",
  "footer.intermissions": "intermissions",
  // intermissions
  "interm.title": "a moment",
  "interm.got_it": "got it",
  "interm.archive": "intermissions",
};

const ES: Dict = {
  "nav.levels": "niveles",
  "nav.reviews": "repasos",
  "nav.practice": "práctica",
  "nav.dashboard": "panel",
  "nav.account": "Menú de cuenta",
  "nav.profile": "perfil",
  "nav.settings": "ajustes",
  "nav.admin": "administración",
  "nav.logout": "cerrar sesión",
  "dash.lessons": "lecciones",
  "dash.reviews": "repasos",
  "dash.customize": "personalizar panel",
  "dash.done_customizing": "listo",
  "dash.add_card": "agregar tarjeta",
  "dash.reset": "restaurar",
  "dash.saving": "guardando…",
  "dash.saved": "guardado",
  "dash.not_saved": "no se guardó",
  "common.start": "empezar",
  "common.continue": "continuar",
  "common.back": "atrás",
  "common.next": "siguiente",
  "common.skip": "omitir",
  "common.close": "cerrar",
  "common.loading": "un momento",
  "common.empty": "nada por aquí todavía",
  "footer.product": "Producto",
  "footer.features": "funciones",
  "footer.how": "cómo funciona",
  "footer.pricing": "precios",
  "footer.changelog": "novedades",
  "footer.resources": "Recursos",
  "footer.support": "soporte",
  "footer.faq": "acerca de y preguntas",
  "footer.community": "comunidad",
  "footer.intermissions": "intermedios",
  "interm.title": "un momento",
  "interm.got_it": "entendido",
  "interm.archive": "intermedios",
};

const DICTS: Record<Locale, Dict> = { en: EN, es: ES };

/** Translate a key. Falls back to English, then to the key itself. */
export function translate(key: string, locale: Locale): string {
  return DICTS[locale]?.[key] ?? EN[key] ?? key;
}

/** Every key the English dictionary defines — used by the drift test. */
export function keysFor(locale: Locale): string[] {
  return Object.keys(DICTS[locale] ?? {});
}

// The immersion flag is fetched once per page load and cached at module level;
// it changes about as often as a user finishes level 10.
let cachedLocale: Locale | null = null;

export function useUiText(): { t: (key: string) => string; locale: Locale } {
  const [locale, setLocale] = useState<Locale>(cachedLocale ?? "en");

  useEffect(() => {
    if (cachedLocale !== null) return;
    let live = true;
    immersionApi.get()
      .then((state) => {
        const next: Locale = state.enabled ? "es" : "en";
        cachedLocale = next;
        if (live) setLocale(next);
      })
      // Immersion is a preference, not a requirement: English is a fine default.
      .catch(() => { cachedLocale = "en"; });
    return () => { live = false; };
  }, []);

  const t = useCallback((key: string) => translate(key, locale), [locale]);
  return { t, locale };
}

/** Called after toggling the setting so the next render picks it up. */
export function clearLocaleCache(): void {
  cachedLocale = null;
}
