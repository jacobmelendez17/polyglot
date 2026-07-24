"use client";

// Small progress primitives shared by the item detail page, the level
// progression page, and (later) the dashboard.
//
// Accessibility rules these all follow:
//   * never colour alone — every state also carries a word or a glyph
//   * every rail/bar exposes its value to assistive tech via role/aria
//   * transitions are transform/opacity only and disabled under
//     prefers-reduced-motion

import Link from "next/link";
import {
  CATEGORY_LABELS,
  MAX_PRACTICE_STAGE,
  PRACTICE_CATEGORIES,
  type LevelProgressItem,
  type PracticeCategory,
  type PracticeStage,
  relativeTime,
} from "@/lib/items-api";

// --- SRS ------------------------------------------------------------------

const STAGE_TONE: Record<string, string> = {
  beginner: "bg-terraza-pink",
  familiar: "bg-terraza-gold",
  intermediate: "bg-terraza-green",
  advanced: "bg-terraza-green",
  fluent: "bg-terraza-accent text-terraza-accentInk",
  none: "bg-terraza-pill",
};

export function stageTone(stage: number): string {
  if (stage <= 0) return STAGE_TONE.none;
  if (stage <= 4) return STAGE_TONE.beginner;
  if (stage <= 6) return STAGE_TONE.familiar;
  if (stage === 7) return STAGE_TONE.intermediate;
  if (stage === 8) return STAGE_TONE.advanced;
  return STAGE_TONE.fluent;
}

export function SrsPill({ stage, name }: { stage: number; name: string }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-3 py-1 text-xs tracking-label ${stageTone(stage)}`}
    >
      {name.toUpperCase()}
    </span>
  );
}

// --- leech ----------------------------------------------------------------

const LEECH_COPY: Record<string, { label: string; glyph: string; tone: string }> = {
  watch: { label: "keep an eye on this", glyph: "◐", tone: "bg-terraza-gold" },
  leech: { label: "tricky item", glyph: "◑", tone: "bg-terraza-pink" },
  critical: { label: "needs attention", glyph: "●", tone: "bg-terraza-danger/20" },
};

export function LeechPill({ state }: { state: string }) {
  const copy = LEECH_COPY[state];
  if (!copy) return null;
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs tracking-label ${copy.tone}`}
    >
      <span aria-hidden="true">{copy.glyph}</span>
      {copy.label}
    </span>
  );
}

// --- perfect --------------------------------------------------------------

export function PerfectBadge({
  perfect, ready,
}: { perfect: boolean; ready?: boolean }) {
  if (perfect) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-terraza-accent px-3 py-1 text-xs tracking-label text-terraza-accentInk">
        <span aria-hidden="true">✦</span> perfect
      </span>
    );
  }
  if (!ready) return null;
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-terraza-pill px-3 py-1 text-xs tracking-label text-terraza-soft">
      <span aria-hidden="true">✧</span> almost perfect
    </span>
  );
}

// --- practice stage rail --------------------------------------------------

export function StagePips({
  stage, max = MAX_PRACTICE_STAGE, label,
}: { stage: number; max?: number; label: string }) {
  return (
    <span
      role="img"
      aria-label={`${label}: ${stage} of ${max} stages`}
      className="inline-flex gap-1"
    >
      {Array.from({ length: max }, (_, i) => (
        <span
          key={i}
          aria-hidden="true"
          className={`h-2.5 w-2.5 rounded-full transition-transform duration-300 motion-reduce:transition-none ${
            i < stage
              ? "scale-100 bg-terraza-accent"
              : "scale-90 border border-terraza-dash bg-transparent"
          }`}
        />
      ))}
    </span>
  );
}

/** One row per practice category, with its Uno–Cinco stage and cooldown state. */
export function PracticeStageRail({
  stages, compact = false,
}: { stages: PracticeStage[]; compact?: boolean }) {
  return (
    <ul className="flex flex-col gap-3">
      {stages.map((s) => (
        <li key={s.category} className="flex items-center gap-3">
          <span className="w-20 text-xs tracking-label text-terraza-soft">
            {CATEGORY_LABELS[s.category] ?? s.category}
          </span>
          <StagePips stage={s.stage} max={s.max_stage} label={s.category} />
          <span className="ml-auto text-right text-sm">
            <span className={s.complete ? "tracking-cozy" : "text-terraza-soft"}>
              {s.complete ? "✓ complete" : s.label.toLowerCase()}
            </span>
            {!compact && s.on_cooldown && (
              <span className="block text-xs text-terraza-soft">
                next stage {relativeTime(s.next_available_at)}
              </span>
            )}
          </span>
        </li>
      ))}
    </ul>
  );
}

/** The compact three-dot summary used on progression tiles. */
export function CategoryDots({
  stages,
}: { stages: Record<PracticeCategory, number> }) {
  const done = PRACTICE_CATEGORIES.filter(
    (c) => (stages[c] ?? 0) >= MAX_PRACTICE_STAGE,
  ).length;
  return (
    <span
      role="img"
      aria-label={`${done} of ${PRACTICE_CATEGORIES.length} practice categories complete`}
      className="inline-flex gap-1"
    >
      {PRACTICE_CATEGORIES.map((c) => {
        const stage = stages[c] ?? 0;
        return (
          <span
            key={c}
            aria-hidden="true"
            title={`${c}: stage ${stage}`}
            className={`h-1.5 w-4 rounded-full ${
              stage >= MAX_PRACTICE_STAGE
                ? "bg-terraza-accent"
                : stage > 0
                  ? "bg-terraza-gold"
                  : "bg-terraza-pill"
            }`}
          />
        );
      })}
    </span>
  );
}

// --- accuracy -------------------------------------------------------------

export function AccuracyBar({
  correct, total,
}: { correct: number; total: number }) {
  if (!total) {
    return (
      <p className="font-empty italic text-terraza-soft">no answers yet ~</p>
    );
  }
  const percent = Math.round((correct / total) * 100);
  return (
    <div>
      <div
        role="meter"
        aria-valuenow={percent}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`Accuracy: ${percent} percent, ${correct} of ${total} answers correct`}
        className="h-2 overflow-hidden rounded-full bg-terraza-pill"
      >
        <div
          className="h-full rounded-full bg-terraza-accent transition-[width] duration-500 motion-reduce:transition-none"
          style={{ width: `${percent}%` }}
        />
      </div>
      <p className="mt-1 text-sm text-terraza-soft">
        {percent}% · {correct} of {total} answers correct
      </p>
    </div>
  );
}

// --- progression tile -----------------------------------------------------

export function ItemTile({ item }: { item: LevelProgressItem }) {
  return (
    <Link
      href={`/items/${item.item_type}/${item.item_id}`}
      className="block rounded-card border border-terraza-dash bg-terraza-card p-4 transition-transform duration-200 hover:-translate-y-0.5 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-terraza-ink motion-reduce:transition-none motion-reduce:hover:translate-y-0"
    >
      <div className="flex items-start gap-2">
        <div className="mr-auto min-w-0">
          <p className="truncate lowercase tracking-cozy">
            {item.article ? `${item.article} ` : ""}{item.term}
          </p>
          <p className="truncate text-sm text-terraza-soft">
            {item.translation || "—"}
          </p>
        </div>
        {item.perfect && <span aria-hidden="true" title="perfect">✦</span>}
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <SrsPill
          stage={item.srs_stage}
          name={item.learned ? item.srs_stage_name : "not started"}
        />
        <LeechPill state={item.leech_state} />
      </div>

      <div className="mt-3 flex items-center gap-2">
        <CategoryDots stages={item.practice_stages} />
        <span className="ml-auto text-xs text-terraza-soft">
          {item.learned ? relativeTime(item.next_review_at) : "unlearned"}
        </span>
      </div>
    </Link>
  );
}
