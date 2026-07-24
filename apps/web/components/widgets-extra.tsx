"use client";

// Three widgets added in slice 9 so the customizer has something to offer.
// All three read fields /me/stats already returns — no new backend data.
//
// They fetch through a small module-level cache rather than importing the
// hook inside components/widgets.tsx, so this file can be dropped in without
// touching that one. Unifying the two caches is a tidy-up for a later slice.

import Link from "next/link";
import { useEffect, useState } from "react";
import { Card } from "@/components/ui";
import { learn, STAGE_NAMES, type Stats } from "@/lib/learn-api";
import { relativeTime } from "@/lib/items-api";

let cached: { at: number; stats: Stats } | null = null;
const CACHE_MS = 15_000;

function useDashboardStats() {
  const [stats, setStats] = useState<Stats | null>(cached?.stats ?? null);
  const [loading, setLoading] = useState(!cached);

  useEffect(() => {
    if (cached && Date.now() - cached.at < CACHE_MS) {
      setStats(cached.stats);
      setLoading(false);
      return;
    }
    let live = true;
    learn.stats()
      .then((s) => {
        cached = { at: Date.now(), stats: s };
        if (live) { setStats(s); setLoading(false); }
      })
      .catch(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, []);

  return { stats, loading };
}

function WidgetLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="mb-3 text-xs tracking-label text-terraza-soft">{children}</div>
  );
}

export function NextReviewWidget() {
  const { stats, loading } = useDashboardStats();
  const due = stats?.reviews_due ?? 0;
  const next = stats?.next_review_at ?? null;

  return (
    <Card>
      <WidgetLabel>NEXT REVIEW</WidgetLabel>
      {loading ? (
        <p className="py-2 font-empty italic text-terraza-soft">un momento ~</p>
      ) : due > 0 ? (
        <>
          <p className="text-3xl lowercase tracking-cozy">now</p>
          <p className="mt-1 text-sm text-terraza-soft">
            {due} {due === 1 ? "review" : "reviews"} waiting
          </p>
          <Link href="/reviews"
            className="mt-4 inline-block rounded-full bg-terraza-accent px-5 py-2 text-sm tracking-cozy text-terraza-accentInk">
            start reviews →
          </Link>
        </>
      ) : next ? (
        <>
          <p className="text-3xl lowercase tracking-cozy">{relativeTime(next)}</p>
          <p className="mt-1 text-sm text-terraza-soft">
            nothing due until then — rest easy.
          </p>
        </>
      ) : (
        <p className="py-2 font-empty italic text-terraza-soft">
          no reviews scheduled yet ~
        </p>
      )}
    </Card>
  );
}

export function StageDetailWidget() {
  const { stats, loading } = useDashboardStats();
  const counts = stats?.stage_counts ?? [];
  const max = Math.max(1, ...counts.map((c) => c.count));

  return (
    <Card>
      <WidgetLabel>SRS STAGES</WidgetLabel>
      {loading ? (
        <p className="py-2 font-empty italic text-terraza-soft">un momento ~</p>
      ) : counts.length === 0 ? (
        <p className="py-2 font-empty italic text-terraza-soft">
          nothing in your queue yet ~
        </p>
      ) : (
        <ul className="flex flex-col gap-1.5">
          {counts.map((c) => (
            <li key={c.stage} className="flex items-center gap-3 text-sm">
              <span className="w-24 shrink-0 text-terraza-soft">
                {c.name ?? STAGE_NAMES[c.stage]}
              </span>
              <span
                className="h-2 rounded-full bg-terraza-accent transition-[width] duration-500 motion-reduce:transition-none"
                style={{ width: `${(c.count / max) * 60}%`, minWidth: c.count ? 6 : 0 }}
                aria-hidden="true"
              />
              <span className="ml-auto tabular-nums">{c.count}</span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

export function LessonsReadyWidget() {
  const { stats, loading } = useDashboardStats();
  const lessons = stats?.lessons_available ?? 0;

  return (
    <Card>
      <WidgetLabel>LESSONS READY</WidgetLabel>
      <p className="text-3xl lowercase tracking-cozy">{loading ? "…" : lessons}</p>
      <p className="mt-1 text-sm text-terraza-soft">
        {lessons > 0
          ? "items waiting to be learned"
          : "keep reviewing to unlock the next level"}
      </p>
      {lessons > 0 && (
        <Link href="/levels"
          className="mt-4 inline-block rounded-full bg-terraza-pill px-5 py-2 text-sm tracking-cozy">
          browse levels →
        </Link>
      )}
    </Card>
  );
}
