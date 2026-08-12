"use client";

// Header language switcher (spec §32). The trigger shows just the flag of the
// active language (name kept as an accessible label, §29). The menu lists every
// enabled language by flag + name; languages without published curriculum yet
// (`ready === false`, e.g. Tagalog) are greyed out and show a "coming soon"
// tooltip on hover/focus and can't be selected. Closes on outside-click or Esc.
// Switching reloads so every content surface refetches under the new language.

import { useEffect, useRef, useState } from "react";
import { languages, type Language } from "@/lib/languages-api";

/** Map a language code to a flag emoji; falls back to the region, then a globe. */
export function flagFor(code: string): string {
  const c = (code || "").toLowerCase();
  const map: Record<string, string> = {
    "es-mx": "🇲🇽", "es-419": "🇲🇽", es: "🇪🇸", "es-es": "🇪🇸",
    tl: "🇵🇭", "tl-ph": "🇵🇭", fil: "🇵🇭",
    en: "🇺🇸", "en-us": "🇺🇸", "en-gb": "🇬🇧",
    pt: "🇧🇷", "pt-br": "🇧🇷", "pt-pt": "🇵🇹",
    fr: "🇫🇷", de: "🇩🇪", it: "🇮🇹", ja: "🇯🇵", ko: "🇰🇷",
    zh: "🇨🇳", ru: "🇷🇺", el: "🇬🇷", ar: "🇸🇦", nl: "🇳🇱",
  };
  if (map[c]) return map[c];
  const region = c.split(/[-_]/)[1];
  if (region && region.length === 2) {
    return String.fromCodePoint(
      ...[...region.toUpperCase()].map((ch) => 0x1f1e6 + ch.charCodeAt(0) - 65),
    );
  }
  return "🌐";
}

export function LanguageSwitcher() {
  const [open, setOpen] = useState(false);
  const [list, setList] = useState<Language[]>([]);
  const [active, setActive] = useState<Language | null>(null);
  const [busy, setBusy] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    languages.active().then(setActive).catch(() => setActive(null));
  }, []);

  useEffect(() => {
    if (!open) return;
    if (list.length === 0) languages.list().then(setList).catch(() => setList([]));
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open, list.length]);

  async function pick(l: Language) {
    if (l.ready === false) return; // not selectable yet
    if (active?.code === l.code) { setOpen(false); return; }
    setBusy(true);
    try {
      await languages.setActive(l.code);
      window.location.reload();
    } catch {
      setBusy(false);
      setOpen(false);
    }
  }

  if (!active) return null;

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        disabled={busy}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={`language: ${active.name}`}
        title={active.name}
        className="flex items-center gap-1 rounded-full bg-terraza-pill px-3 py-1 text-lg disabled:opacity-50"
      >
        <span aria-hidden="true">{flagFor(active.code)}</span>
        <span className="sr-only">{active.name}</span>
        <span aria-hidden="true" className="text-xs text-terraza-soft">▾</span>
      </button>

      {open && (
        <ul
          role="listbox"
          aria-label="choose language"
          className="absolute right-0 z-30 mt-1 w-52 overflow-hidden rounded-card border border-terraza-dash bg-terraza-bg py-1 shadow-lg"
        >
          {list.length === 0 ? (
            <li className="px-3 py-2 text-sm text-terraza-soft">un momento ~</li>
          ) : (
            list.map((l) => {
              const current = l.code === active.code;
              const notReady = l.ready === false;
              return (
                <li key={l.code} role="option" aria-selected={current}>
                  <div className="group relative">
                    <button
                      onClick={() => pick(l)}
                      aria-disabled={notReady}
                      className={`flex w-full items-center gap-2 px-3 py-2 text-left text-sm tracking-cozy ${
                        notReady
                          ? "cursor-not-allowed text-terraza-soft opacity-50"
                          : "hover:bg-terraza-pill"
                      } ${current ? "bg-terraza-pill" : ""}`}
                    >
                      <span aria-hidden="true" className="text-lg">{flagFor(l.code)}</span>
                      <span className="lowercase">{l.name}</span>
                      {current && <span aria-hidden="true" className="ml-auto text-terraza-accent">✓</span>}
                      {notReady && (
                        <span className="ml-auto text-[10px] uppercase tracking-label text-terraza-soft">
                          soon
                        </span>
                      )}
                    </button>
                    {notReady && (
                      <span
                        role="tooltip"
                        className="pointer-events-none absolute right-2 top-full z-40 mt-1 whitespace-nowrap rounded-[8px] bg-terraza-ink px-2 py-1 text-xs text-terraza-bg opacity-0 shadow-md transition-opacity duration-150 group-hover:opacity-100 group-focus-within:opacity-100 motion-reduce:transition-none"
                      >
                        coming soon
                      </span>
                    )}
                  </div>
                </li>
              );
            })
          )}
        </ul>
      )}
    </div>
  );
}
