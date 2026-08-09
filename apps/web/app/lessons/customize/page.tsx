"use client";

// Customize Lessons (§20, by request). Per-level sections; each item is a clickable
// chip you add to the batch. A filter next to each "level N" heading regroups items
// (grammar/vocabulary · theme · random) with a smooth position animation. A "begin
// lesson" bar sticks to the bottom (semi-transparent) until you reach the real one.
//
// First cut: "begin lesson" remembers your selection and enters the lessons flow.
// Binding the exact selection into a custom teach→quiz→SRS session is the next slice.

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { Header } from "@/components/header";
import { Protected } from "@/components/protected";
import { Card } from "@/components/ui";
import {
  customize, groupItems, itemKey,
  type GroupMode, type SelectableItem, type SelectableLevel,
} from "@/lib/customize-api";

const MODES: { key: GroupMode; label: string }[] = [
  { key: "type", label: "grammar / vocab" },
  { key: "theme", label: "theme" },
  { key: "random", label: "random" },
];

export default function CustomizePage() {
  return (
    <Protected>
      <Header />
      <Customize />
    </Protected>
  );
}

function Customize() {
  const router = useRouter();
  const [levels, setLevels] = useState<SelectableLevel[] | null>(null);
  const [error, setError] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const footerSentinel = useRef<HTMLDivElement>(null);
  const [footerStuck, setFooterStuck] = useState(true);

  useEffect(() => {
    customize.selectable().then((r) => setLevels(r.levels)).catch(() => setError(true));
  }, []);

  // The sticky bar detaches once the real (bottom) button scrolls into view.
  useEffect(() => {
    const el = footerSentinel.current;
    if (!el || !("IntersectionObserver" in window)) return;
    const io = new IntersectionObserver(
      ([e]) => setFooterStuck(!e.isIntersecting), { rootMargin: "0px 0px -8px 0px" });
    io.observe(el);
    return () => io.disconnect();
  }, [levels]);

  function toggle(i: SelectableItem) {
    const k = itemKey(i);
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(k) ? next.delete(k) : next.add(k);
      return next;
    });
  }

  function begin() {
    if (selected.size === 0) return;
    try {
      sessionStorage.setItem("polyglot-custom-lesson", JSON.stringify([...selected]));
    } catch { /* selection is best-effort */ }
    router.push("/levels");
  }

  if (error)
    return <Shell><Card><p role="alert" className="text-terraza-danger">couldn&apos;t load your items.</p></Card></Shell>;
  if (levels === null)
    return <Shell><p className="text-center font-empty italic text-terraza-soft">un momento ~</p></Shell>;
  if (levels.length === 0)
    return <Shell><Card><p className="font-empty italic text-terraza-soft">nothing left to add right now — you&apos;ve started everything available. ✦</p></Card></Shell>;

  return (
    <Shell>
      <div className="flex items-baseline justify-between">
        <h1 className="text-2xl lowercase tracking-cozy">customize your lesson</h1>
        <span className="text-sm text-terraza-soft" aria-live="polite">{selected.size} selected</span>
      </div>
      <p className="mt-1 mb-6 text-terraza-soft">tap items to add them to your batch, then begin.</p>

      <div className="flex flex-col gap-8 pb-28">
        {levels.map((lv) => (
          <LevelSection key={lv.level} level={lv} selected={selected} onToggle={toggle} />
        ))}
      </div>

      {/* the real button + a sentinel that turns off the sticky bar when reached */}
      <div ref={footerSentinel} className="flex justify-center py-6">
        <BeginButton n={selected.size} onClick={begin} />
      </div>

      {footerStuck && (
        <div className="fixed inset-x-0 bottom-0 z-20 flex justify-center border-t border-terraza-dash/50 bg-terraza-bg/70 py-3 backdrop-blur">
          <BeginButton n={selected.size} onClick={begin} />
        </div>
      )}
    </Shell>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return <main className="mx-auto max-w-4xl px-4 py-8">{children}</main>;
}

function BeginButton({ n, onClick }: { n: number; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      disabled={n === 0}
      className="rounded-full bg-terraza-accent px-8 py-3 tracking-cozy text-terraza-accentInk transition-transform hover:-translate-y-0.5 disabled:opacity-40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-terraza-ink"
    >
      begin lesson{n > 0 ? ` · ${n}` : ""}
    </button>
  );
}

function LevelSection({ level, selected, onToggle }: {
  level: SelectableLevel; selected: Set<string>; onToggle: (i: SelectableItem) => void;
}) {
  const [mode, setMode] = useState<GroupMode>("type");
  const groups = useMemo(() => groupItems(level.items, mode, level.level + 1), [level, mode]);

  return (
    <Card>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="lowercase tracking-cozy">
          level {level.level} <span className="text-terraza-soft">· {level.title}</span>
        </h2>
        <div className="flex gap-1" role="group" aria-label={`group level ${level.level} by`}>
          {MODES.map((m) => (
            <button
              key={m.key}
              onClick={() => setMode(m.key)}
              aria-pressed={mode === m.key}
              className={`rounded-full px-3 py-1 text-xs tracking-cozy transition-colors ${mode === m.key ? "bg-terraza-accent text-terraza-accentInk" : "bg-terraza-pill text-terraza-soft"}`}
            >
              {m.label}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-4 flex flex-col gap-4">
        {groups.map((g) => (
          <div key={g.name}>
            {groups.length > 1 && (
              <p className="mb-2 text-xs tracking-label text-terraza-soft">{g.name.toUpperCase()}</p>
            )}
            <div className="flex flex-wrap gap-2">
              {g.items.map((i) => {
                const on = selected.has(itemKey(i));
                return (
                  <button
                    key={itemKey(i)}
                    onClick={() => onToggle(i)}
                    aria-pressed={on}
                    // transition-all so items ease into their new position when the grouping changes
                    className={`transition-all duration-300 rounded-full border px-3 py-1.5 text-sm ${on ? "border-terraza-accent bg-terraza-green text-terraza-accentInk" : "border-terraza-dash bg-terraza-card text-terraza-ink hover:border-terraza-accent"}`}
                  >
                    <span aria-hidden className="mr-1">{on ? "✓" : "+"}</span>
                    <span className="tracking-cozy">{i.term}</span>
                    <span className="ml-2 text-xs text-terraza-soft">{i.translation}</span>
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}
