"use client";

// The customizable dashboard grid (PLANNING §15).
//
// Reordering works two ways on purpose. Pointer users drag a card; keyboard and
// screen-reader users get real ← → buttons on every card. The arrows are not a
// lesser fallback — they are the primary control, and dragging is the shortcut
// layered on top. Every move is announced in a live region, because a card
// silently changing position is invisible to anyone not watching the screen.
//
// Changes save immediately and optimistically. A failed save reverts the grid
// to what the server last confirmed rather than leaving the two out of step.

import { useCallback, useEffect, useRef, useState } from "react";
import {
  FluentWidget, ForecastWidget, LeechWidget, PracticeWidget,
  ProgressionWidget, WelcomeWidget, XpWidget,
} from "@/components/widgets";
import {
  LessonsReadyWidget, NextReviewWidget, StageDetailWidget,
} from "@/components/widgets-extra";
import { Card } from "@/components/ui";
import { dashboard, type CatalogEntry, type DashboardConfig } from "@/lib/dashboard-api";
import {
  addWidget, availableToAdd, moveAnnouncement, moveWidget, removeWidget,
  reorderWidget, type LayoutEntry,
} from "@/lib/widget-layout";

// Every catalog key on the server has a component here. A key with no entry
// renders a labelled placeholder rather than an empty hole, so a version skew
// between API and client is visible instead of mysterious.
const REGISTRY: Record<string, () => React.JSX.Element> = {
  welcome: WelcomeWidget,
  progression: ProgressionWidget,
  forecast: ForecastWidget,
  xp: XpWidget,
  fluent: FluentWidget,
  leech: LeechWidget,
  practice: PracticeWidget,
  next_review: NextReviewWidget,
  stage_detail: StageDetailWidget,
  lessons_ready: LessonsReadyWidget,
};

// Literal class strings so Tailwind keeps them; template literals get purged.
const SPAN_CLASS: Record<number, string> = {
  1: "md:col-span-1", 2: "md:col-span-2", 3: "md:col-span-3",
  4: "md:col-span-4", 5: "md:col-span-5", 6: "md:col-span-6",
};

type SaveState = "idle" | "saving" | "saved" | "error";

export function WidgetGrid() {
  const [config, setConfig] = useState<DashboardConfig | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [announcement, setAnnouncement] = useState("");
  const [dragKey, setDragKey] = useState<string | null>(null);
  const confirmed = useRef<LayoutEntry[]>([]);

  useEffect(() => {
    let live = true;
    dashboard.get()
      .then((c) => {
        if (!live) return;
        setConfig(c);
        confirmed.current = c.layout.widgets;
      })
      .catch((e) => { if (live) setError(e.message); });
    return () => { live = false; };
  }, []);

  const persist = useCallback(async (widgets: LayoutEntry[]) => {
    setSaveState("saving");
    try {
      const saved = await dashboard.save(widgets);
      confirmed.current = saved.layout.widgets;
      // Trust the server's normalized result over the optimistic one.
      setConfig((c) => (c ? { ...c, layout: saved.layout } : c));
      setSaveState("saved");
    } catch (e) {
      setConfig((c) =>
        c ? { ...c, layout: { ...c.layout, widgets: confirmed.current } } : c,
      );
      setSaveState("error");
      setError(e instanceof Error ? e.message : "Could not save your layout.");
    }
  }, []);

  const apply = useCallback((next: LayoutEntry[], say?: string) => {
    setConfig((c) => (c ? { ...c, layout: { ...c.layout, widgets: next } } : c));
    if (say) setAnnouncement(say);
    persist(next);
  }, [persist]);

  if (error && !config) {
    return <Card><p role="alert" className="text-terraza-danger">{error}</p></Card>;
  }
  if (!config) {
    return (
      <p className="py-10 text-center font-empty italic text-terraza-soft">
        setting up your dashboard ~
      </p>
    );
  }

  const widgets = config.layout.widgets;
  const catalog = config.catalog;
  const addable = availableToAdd(widgets, catalog);
  const titleFor = (key: string) =>
    catalog.find((c) => c.key === key)?.title ?? key;

  function move(key: string, delta: number) {
    const next = moveWidget(widgets, key, delta);
    if (next === widgets) return;
    const index = next.findIndex((w) => w.key === key);
    apply(next, moveAnnouncement(titleFor(key), index, next.length));
  }

  function drop(targetIndex: number) {
    if (!dragKey) return;
    const next = reorderWidget(widgets, dragKey, targetIndex);
    const key = dragKey;
    setDragKey(null);
    if (next === widgets) return;
    apply(next, moveAnnouncement(titleFor(key), targetIndex, next.length));
  }

  return (
    <section aria-label="Dashboard widgets">
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <button
          data-tour="customize"
          onClick={() => { setEditing((e) => !e); setAnnouncement(""); }}
          aria-pressed={editing}
          className={`rounded-full px-5 py-2 text-sm tracking-cozy transition-transform duration-200 hover:-translate-y-0.5 motion-reduce:transition-none motion-reduce:hover:translate-y-0 ${
            editing ? "bg-terraza-accent text-terraza-accentInk" : "bg-terraza-pill"
          }`}
        >
          {editing ? "done customizing" : "customize dashboard"}
        </button>

        {editing && (
          <>
            <AddMenu
              options={addable}
              onAdd={(entry) =>
                apply(addWidget(widgets, entry), `${entry.title} added`)
              }
            />
            <button
              onClick={async () => {
                setSaveState("saving");
                try {
                  const reset = await dashboard.reset();
                  confirmed.current = reset.layout.widgets;
                  setConfig(reset);
                  setSaveState("saved");
                  setAnnouncement("Dashboard reset to the default layout");
                } catch {
                  setSaveState("error");
                }
              }}
              className="rounded-full bg-terraza-pill px-5 py-2 text-sm tracking-cozy"
            >
              reset to default
            </button>
          </>
        )}

        <span className="ml-auto text-xs tracking-label text-terraza-soft">
          {saveState === "saving" && "saving…"}
          {saveState === "saved" && "saved ✦"}
          {saveState === "error" && (
            <span className="text-terraza-danger">not saved</span>
          )}
        </span>
      </div>

      {editing && (
        <p className="mb-3 text-sm text-terraza-soft">
          drag a card to move it, or use the ← → buttons. changes save as you go.
        </p>
      )}

      {/* Live region: keyboard moves are otherwise invisible to a screen reader. */}
      <p aria-live="polite" className="sr-only">{announcement}</p>

      {widgets.length === 0 ? (
        <Card>
          <p className="text-center font-empty italic text-terraza-soft">
            your dashboard is empty ~
          </p>
          <p className="mt-2 text-center text-sm text-terraza-soft">
            use “customize dashboard” to add the cards you want back.
          </p>
        </Card>
      ) : (
        <ul className="grid grid-cols-1 gap-4 md:grid-cols-6" data-tour="widgets">
          {widgets.map((w, index) => {
            const Widget = REGISTRY[w.key];
            return (
              <li
                key={w.key}
                data-tour={`widget-${w.key}`}
                className={`${SPAN_CLASS[w.span] ?? SPAN_CLASS[2]} ${
                  dragKey === w.key ? "opacity-50" : ""
                }`}
                draggable={editing}
                onDragStart={() => setDragKey(w.key)}
                onDragEnd={() => setDragKey(null)}
                onDragOver={(e) => { if (editing && dragKey) e.preventDefault(); }}
                onDrop={(e) => { e.preventDefault(); drop(index); }}
              >
                {editing && (
                  <EditBar
                    title={titleFor(w.key)}
                    position={index}
                    total={widgets.length}
                    onMove={(delta) => move(w.key, delta)}
                    onRemove={() =>
                      apply(removeWidget(widgets, w.key), `${titleFor(w.key)} removed`)
                    }
                  />
                )}
                {Widget ? (
                  <Widget />
                ) : (
                  <Card>
                    <p className="font-empty italic text-terraza-soft">
                      “{w.key}” isn&apos;t available in this version ~
                    </p>
                  </Card>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

function EditBar({
  title, position, total, onMove, onRemove,
}: {
  title: string; position: number; total: number;
  onMove: (delta: number) => void; onRemove: () => void;
}) {
  return (
    <div className="mb-1 flex items-center gap-1 rounded-full bg-terraza-pill px-2 py-1">
      <span className="px-1 text-xs tracking-label text-terraza-soft">
        {title.toUpperCase()}
      </span>
      <span className="ml-auto flex items-center gap-1">
        <IconButton
          label={`Move ${title} earlier`}
          disabled={position === 0}
          onClick={() => onMove(-1)}
        >
          ←
        </IconButton>
        <IconButton
          label={`Move ${title} later`}
          disabled={position === total - 1}
          onClick={() => onMove(1)}
        >
          →
        </IconButton>
        <IconButton label={`Remove ${title}`} onClick={onRemove}>
          ×
        </IconButton>
      </span>
    </div>
  );
}

function IconButton({
  label, children, onClick, disabled = false,
}: {
  label: string; children: React.ReactNode;
  onClick: () => void; disabled?: boolean;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      disabled={disabled}
      onClick={onClick}
      className="flex h-6 w-6 items-center justify-center rounded-full bg-terraza-card text-sm disabled:opacity-30 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-terraza-ink"
    >
      {children}
    </button>
  );
}

function AddMenu({
  options, onAdd,
}: { options: CatalogEntry[]; onAdd: (entry: CatalogEntry) => void }) {
  const [open, setOpen] = useState(false);

  if (options.length === 0) {
    return (
      <span className="text-sm text-terraza-soft">every card is on your dashboard</span>
    );
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
        className="rounded-full bg-terraza-pill px-5 py-2 text-sm tracking-cozy"
      >
        add a card ({options.length})
      </button>
      {open && (
        <div
          role="menu"
          className="absolute left-0 z-20 mt-2 w-72 rounded-card border border-terraza-dash bg-terraza-card p-1 shadow-lg"
        >
          {options.map((o) => (
            <button
              key={o.key}
              role="menuitem"
              onClick={() => { onAdd(o); setOpen(false); }}
              className="block w-full rounded-[10px] px-3 py-2 text-left hover:bg-terraza-pill"
            >
              <span className="lowercase tracking-cozy">{o.title}</span>
              <span className="block text-xs text-terraza-soft">{o.description}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
