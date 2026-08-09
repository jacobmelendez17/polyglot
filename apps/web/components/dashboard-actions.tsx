"use client";

// Dashboard lesson/review actions (§20, by request). The cards are no longer one big
// link — each carries explicit buttons: reviews → "start reviews"; lessons → "start
// lessons" + "customize lessons". Count-bearing, Terraza-styled, with honest empty
// states.
import Link from "next/link";
import { useEffect, useState } from "react";
import { Card } from "./ui";
import { learn, type Stats } from "@/lib/learn-api";

export function DashboardActions() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    learn.stats().then(setStats).catch(() => setStats(null)).finally(() => setLoading(false));
  }, []);

  const lessons = stats?.lessons_available ?? 0;
  const reviews = stats?.reviews_due ?? 0;
  const learned = stats?.items_learned ?? 0;
  const count = (n: number) => (loading ? "…" : n.toLocaleString());

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
      {/* lessons */}
      <Card className="flex flex-col bg-terraza-pink/40">
        <div className="flex items-baseline gap-3">
          <span className="text-5xl leading-none tracking-cozy">{count(lessons)}</span>
          <div>
            <p className="text-lg lowercase tracking-cozy">lessons</p>
            <p className="text-sm text-terraza-soft">learn new words &amp; grammar</p>
          </div>
        </div>
        <p className="mt-2 text-sm text-terraza-soft">
          {lessons > 0 ? "ready to learn"
            : learned > 0 ? "keep reviewing to unlock the next level"
            : "nothing available yet"}
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          <Link
            href="/levels"
            aria-disabled={lessons === 0}
            className={`rounded-full bg-terraza-accent px-5 py-2 tracking-cozy text-terraza-accentInk transition-transform hover:-translate-y-0.5 ${lessons === 0 ? "pointer-events-none opacity-40" : ""}`}
          >
            start lessons →
          </Link>
          <Link
            href="/lessons/customize"
            className="rounded-full bg-terraza-card px-5 py-2 tracking-cozy text-terraza-ink transition-transform hover:-translate-y-0.5"
          >
            customize lessons
          </Link>
        </div>
      </Card>

      {/* reviews */}
      <Card className="flex flex-col bg-terraza-accent/25">
        <div className="flex items-baseline gap-3">
          <span className="text-5xl leading-none tracking-cozy">{count(reviews)}</span>
          <div>
            <p className="text-lg lowercase tracking-cozy">reviews</p>
            <p className="text-sm text-terraza-soft">strengthen what you know</p>
          </div>
        </div>
        <p className="mt-2 text-sm text-terraza-soft">
          {reviews > 0 ? "waiting for you" : "nothing due right now ~"}
        </p>
        <div className="mt-4">
          <Link
            href="/reviews"
            aria-disabled={reviews === 0}
            className={`inline-block rounded-full bg-terraza-accent px-5 py-2 tracking-cozy text-terraza-accentInk transition-transform hover:-translate-y-0.5 ${reviews === 0 ? "pointer-events-none opacity-40" : ""}`}
          >
            start reviews →
          </Link>
        </div>
      </Card>
    </div>
  );
}
