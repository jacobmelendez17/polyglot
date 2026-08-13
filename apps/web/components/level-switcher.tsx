"use client";

// Level switcher (by request). A dropdown of number icons, one per level —
// the way into a level's lesson page now, replacing the old "open lessons →"
// link that used to live inside the /levels index page's expanded cards.
// Locked levels show but don't navigate, same lock treatment as the index page.

import Link from "next/link";
import { useEffect, useState } from "react";
import { learn, type Level } from "@/lib/learn-api";

export function LevelSwitcher({
  current, label, triggerClassName, hideChevron,
}: { current?: number; label?: string; triggerClassName?: string; hideChevron?: boolean }) {
  const [levels, setLevels] = useState<Level[] | null>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    learn.levels().then(setLevels).catch(() => setLevels([]));
  }, []);

  return (
    <div className="relative inline-block">
      <button
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
        className={triggerClassName ?? "flex items-center gap-2 rounded-full bg-terraza-pill px-4 py-2 text-sm tracking-cozy"}
      >
        {label ?? (current ? `level ${current}` : "jump to a level")}
        {!hideChevron && (
          <span aria-hidden className="text-terraza-soft">{open ? "▲" : "▼"}</span>
        )}
      </button>

      {open && (
        <div
          role="menu"
          aria-label="Jump to a level"
          className="absolute left-1/2 z-20 mt-2 w-64 -translate-x-1/2 rounded-card border border-terraza-dash bg-terraza-card p-3 shadow-lg"
        >
          {levels === null ? (
            <p className="p-2 text-center font-empty italic text-terraza-soft">un momento ~</p>
          ) : levels.length === 0 ? (
            <p className="p-2 text-center font-empty italic text-terraza-soft">no levels yet ~</p>
          ) : (
            <div className="grid grid-cols-5 gap-2">
              {levels.map((l) => {
                const isCurrent = l.position === current;
                const locked = !l.unlocked;
                const base = "flex h-10 w-10 items-center justify-center rounded-full text-sm tracking-cozy transition-transform hover:-translate-y-0.5";
                if (locked) {
                  return (
                    <span
                      key={l.id}
                      role="menuitem"
                      aria-disabled="true"
                      title={`level ${l.position} — locked`}
                      className={`${base} cursor-not-allowed bg-terraza-pill text-terraza-soft opacity-50`}
                    >
                      {l.position}
                    </span>
                  );
                }
                return (
                  <Link
                    key={l.id}
                    href={`/levels/${l.position}`}
                    role="menuitem"
                    onClick={() => setOpen(false)}
                    aria-current={isCurrent ? "page" : undefined}
                    title={`level ${l.position} — ${l.title}`}
                    className={`${base} ${
                      isCurrent
                        ? "border-2 border-terraza-ink bg-terraza-accent text-terraza-accentInk"
                        : "bg-terraza-accent text-terraza-accentInk"
                    }`}
                  >
                    {l.position}
                  </Link>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
