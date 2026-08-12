"use client";

// Header language switcher (spec §32). Lists the enabled languages and switches
// the learner's active one. After switching we reload so every content surface
// (levels, lessons, reading) refetches under the new language. Keyboard-operable;
// nothing relies on colour alone.

import { useEffect, useRef, useState } from "react";
import { languages, type Language } from "@/lib/languages-api";

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
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open, list.length]);

  async function pick(code: string) {
    if (active?.code === code) { setOpen(false); return; }
    setBusy(true);
    try {
      await languages.setActive(code);
      // full reload so all content refetches under the new language
      window.location.reload();
    } catch {
      setBusy(false);
      setOpen(false);
    }
  }

  // Nothing to switch to until we know the current language.
  if (!active) return null;

  return (
    <div ref={ref} className="relative">
      <button onClick={() => setOpen((o) => !o)} disabled={busy}
        aria-haspopup="listbox" aria-expanded={open}
        className="rounded-full bg-terraza-pill px-3 py-1 text-sm tracking-cozy disabled:opacity-50">
        🌐 {active.name.toLowerCase()}
        <span aria-hidden="true" className="ml-1 text-terraza-soft">▾</span>
      </button>
      {open && (
        <ul role="listbox" aria-label="choose language"
          className="absolute right-0 z-30 mt-1 w-44 overflow-hidden rounded-card border border-terraza-dash bg-terraza-bg shadow-lg">
          {list.length === 0 ? (
            <li className="px-3 py-2 text-sm text-terraza-soft">un momento ~</li>
          ) : (
            list.map((l) => {
              const current = l.code === active.code;
              return (
                <li key={l.code} role="option" aria-selected={current}>
                  <button onClick={() => pick(l.code)}
                    className={`flex w-full items-center justify-between px-3 py-2 text-left text-sm tracking-cozy hover:bg-terraza-pill ${current ? "font-medium" : ""}`}>
                    <span className="lowercase">{l.name}</span>
                    {current && <span aria-label="current" className="text-terraza-accent">✓</span>}
                  </button>
                </li>
              );
            })
          )}
        </ul>
      )}
    </div>
  );
}
