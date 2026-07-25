"use client";

// The intermission popup (spec §17): a white, journal-style card that appears
// between lessons with a short reading.
//
// There is nothing to answer — viewing it is the whole interaction — so the
// dialog is deliberately easy to leave: Escape, the close button, or the
// backdrop. It marks itself viewed on dismissal, and a failed mark is swallowed
// rather than trapping the learner in a card that won't close.

import { useCallback, useEffect, useRef, useState } from "react";
import { intermissions, type Intermission, type IntermissionEvent } from "@/lib/content-api";

const KIND_LABEL: Record<string, string> = {
  rule: "a rule worth knowing",
  culture: "culture note",
  pronunciation: "how it sounds",
  tip: "a tip",
  regional: "in mexico",
  note: "a moment",
};

/** Fetches whatever is due for an event and shows each in turn. */
export function IntermissionGate({
  event, level, lesson, onFinished,
}: {
  event: IntermissionEvent;
  level?: number;
  lesson?: number;
  onFinished?: () => void;
}) {
  const [queue, setQueue] = useState<Intermission[] | null>(null);
  const finished = useRef(false);

  useEffect(() => {
    let live = true;
    intermissions.pending(event, level, lesson)
      .then((items) => { if (live) setQueue(items); })
      // An intermission that can't load must never block a lesson.
      .catch(() => { if (live) setQueue([]); });
    return () => { live = false; };
  }, [event, level, lesson]);

  useEffect(() => {
    if (queue && queue.length === 0 && !finished.current) {
      finished.current = true;
      onFinished?.();
    }
  }, [queue, onFinished]);

  if (!queue || queue.length === 0) return null;

  const [current, ...rest] = queue;
  return (
    <IntermissionCard
      intermission={current}
      remaining={rest.length}
      onClose={() => {
        intermissions.markViewed(current.id).catch(() => {});
        setQueue(rest);
      }}
    />
  );
}

export function IntermissionCard({
  intermission, remaining = 0, onClose,
}: { intermission: Intermission; remaining?: number; onClose: () => void }) {
  const cardRef = useRef<HTMLDivElement>(null);

  useEffect(() => { cardRef.current?.focus(); }, [intermission.id]);

  const close = useCallback(() => onClose(), [onClose]);

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") { e.preventDefault(); close(); }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [close]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div
        className="absolute inset-0 bg-terraza-ink/40 transition-opacity duration-200 motion-reduce:transition-none"
        onClick={close}
        aria-hidden="true"
      />

      <div
        ref={cardRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="intermission-title"
        tabIndex={-1}
        className="relative max-h-[80vh] w-full max-w-lg overflow-y-auto rounded-card bg-white p-8 text-terraza-ink shadow-xl outline-none transition-transform duration-300 motion-reduce:transition-none"
        style={{
          // Ruled-paper feel: the journal styling §17 asks for, done with a
          // gradient so there's no image to load and it scales with the text.
          backgroundImage:
            "repeating-linear-gradient(to bottom, transparent, transparent 31px, rgba(0,0,0,0.05) 32px)",
        }}
      >
        <p className="text-xs tracking-label text-terraza-soft">
          {(KIND_LABEL[intermission.kind] ?? KIND_LABEL.note).toUpperCase()}
        </p>
        <h2 id="intermission-title" className="mt-2 text-2xl lowercase tracking-cozy">
          {intermission.title}
        </h2>

        <div className="mt-4 flex flex-col gap-3 leading-relaxed">
          {intermission.body.split("\n\n").map((para, i) => (
            <p key={i}>{renderEmphasis(para)}</p>
          ))}
        </div>

        <div className="mt-7 flex items-center gap-3">
          {remaining > 0 && (
            <span className="text-xs tracking-label text-terraza-soft">
              {remaining} MORE
            </span>
          )}
          <button
            onClick={close}
            className="ml-auto rounded-full bg-terraza-accent px-6 py-2 tracking-cozy text-terraza-accentInk transition-transform duration-200 hover:-translate-y-0.5 motion-reduce:transition-none motion-reduce:hover:translate-y-0"
          >
            got it
          </button>
        </div>
      </div>
    </div>
  );
}

/**
 * Renders **bold** spans from the seed copy.
 *
 * This splits text into React nodes rather than setting innerHTML — the body is
 * admin-authored, but "trusted author" is exactly the assumption that turns one
 * compromised account into stored XSS. Everything else renders as plain text.
 */
export function renderEmphasis(text: string): React.ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*)/g).filter(Boolean).map((chunk, i) =>
    chunk.startsWith("**") && chunk.endsWith("**") ? (
      <strong key={i} className="tracking-cozy">{chunk.slice(2, -2)}</strong>
    ) : (
      <span key={i}>{chunk}</span>
    ),
  );
}
