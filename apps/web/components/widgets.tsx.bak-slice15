"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Card } from "./ui";
import { useAuth } from "@/lib/auth-context";
import { learn, type Stats } from "@/lib/learn-api";

// ---- shared stats hook -------------------------------------------------
// One fetch, shared across widgets via a tiny module-level cache so the six
// widgets don't each hit the endpoint.
let _cache: { stats: Stats | null; at: number } | null = null;
let _inflight: Promise<Stats> | null = null;

function useStats() {
  const [stats, setStats] = useState<Stats | null>(_cache?.stats ?? null);
  const [loading, setLoading] = useState(!_cache);
  useEffect(() => {
    let active = true;
    const fresh = _cache && Date.now() - _cache.at < 5000;
    if (fresh) { setStats(_cache!.stats); setLoading(false); return; }
    _inflight = _inflight ?? learn.stats();
    _inflight
      .then((s) => { _cache = { stats: s, at: Date.now() }; _inflight = null;
        if (active) { setStats(s); } })
      .catch(() => { _inflight = null; if (active) setStats(null); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);
  return { stats, loading };
}

function WidgetLabel({ children }: { children: React.ReactNode }) {
  return <div className="mb-2 text-xs tracking-label text-terraza-soft">{children}</div>;
}

// ---- the hero: big lesson + review action buttons ----------------------
// This is the WaniKani/BunPro/KaniCompanion pattern — two prominent, count-bearing
// calls to action that are the first thing you see and the main thing you click.

export function ActionButtons() {
  const { stats, loading } = useStats();
  const lessons = stats?.lessons_available ?? 0;
  const reviews = stats?.reviews_due ?? 0;
  const learned = stats?.items_learned ?? 0;

  // When no lessons are available it's usually because the next level is still
  // locked — say so, rather than a bare "nothing right now".
  const lessonsEmpty =
    learned > 0
      ? "keep reviewing to unlock the next level"
      : "nothing available yet";

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
      <ActionButton
        href="/levels" kind="lessons" count={lessons} loading={loading}
        title="lessons" sub="learn new words & grammar"
        bg="bg-terraza-pink" ready="ready to learn" emptyText={lessonsEmpty}
      />
      <ActionButton
        href="/reviews" kind="reviews" count={reviews} loading={loading}
        title="reviews" sub="strengthen what you know"
        bg="bg-terraza-accent" ready="waiting for you"
        emptyText="nothing due right now ~"
        emphasize
      />
    </div>
  );
}

function ActionButton({
  href, count, loading, title, sub, bg, ready, emptyText, emphasize,
}: {
  href: string; kind: string; count: number; loading: boolean;
  title: string; sub: string; bg: string; ready: string;
  emptyText: string; emphasize?: boolean;
}) {
  const disabled = !loading && count === 0;
  const inner = (
    <div
      className={`relative flex h-full min-h-[140px] flex-col justify-between overflow-hidden rounded-card p-6 transition-transform ${
        disabled ? "opacity-70" : "hover:-translate-y-1"
      } ${emphasize ? "text-terraza-accentInk" : "text-terraza-ink"} ${bg}`}
      style={{ boxShadow: "0 3px 0 var(--lg-dash)" }}
    >
      <div className="flex items-baseline gap-3">
        <span className="text-6xl lowercase tracking-cozy leading-none">
          {loading ? "·" : count}
        </span>
        <span className="text-lg lowercase tracking-cozy">{title}</span>
      </div>
      <div>
        <p className="text-sm opacity-80">{sub}</p>
        <p className="mt-2 text-xs tracking-label">
          {loading ? "…" : disabled ? emptyText : ready.toUpperCase()}
        </p>
      </div>
      {/* subtle oversized glyph in the corner, WaniKani-ish flourish */}
      <span className="pointer-events-none absolute -right-4 -top-6 select-none text-[7rem] opacity-10">
        ✦
      </span>
    </div>
  );
  if (disabled) return inner;
  return <Link href={href} className="block">{inner}</Link>;
}

// ---- SRS progression: the signature WaniKani breakdown -----------------

const GROUP_META: { key: string; label: string; color: string }[] = [
  { key: "beginner", label: "beginner", color: "var(--lg-pink)" },
  { key: "familiar", label: "familiar", color: "var(--lg-gold)" },
  { key: "intermediate", label: "intermediate", color: "var(--lg-accent)" },
  { key: "advanced", label: "advanced", color: "var(--lg-green)" },
  { key: "fluent", label: "fluent", color: "var(--lg-ink)" },
];

export function ProgressionWidget() {
  const { stats, loading } = useStats();
  const groups = stats?.stage_group_counts ?? {};
  const total = Object.values(groups).reduce((a, b) => a + b, 0);

  return (
    <Card>
      <WidgetLabel>PROGRESSION</WidgetLabel>
      {loading ? (
        <p className="py-4 font-empty italic text-terraza-soft">un momento ~</p>
      ) : total === 0 ? (
        <p className="py-4 font-empty italic text-terraza-soft">
          your journey starts with your first lesson ~
        </p>
      ) : (
        <>
          {/* stacked proportion bar */}
          <div className="flex h-4 overflow-hidden rounded-full">
            {GROUP_META.map((g) => {
              const n = groups[g.key] ?? 0;
              if (n === 0) return null;
              return (
                <div key={g.key} style={{ width: `${(n / total) * 100}%`, background: g.color }}
                     title={`${g.label}: ${n}`} />
              );
            })}
          </div>
          {/* per-group counts */}
          <div className="mt-4 grid grid-cols-5 gap-2 text-center">
            {GROUP_META.map((g) => (
              <div key={g.key}>
                <div className="mx-auto mb-1 h-2 w-2 rounded-full" style={{ background: g.color }} />
                <p className="text-xl lowercase tracking-cozy">{groups[g.key] ?? 0}</p>
                <p className="text-[10px] tracking-label text-terraza-soft">
                  {g.label.toUpperCase()}
                </p>
              </div>
            ))}
          </div>
        </>
      )}
    </Card>
  );
}

// ---- forecast: 7-day bar row -------------------------------------------

export function ForecastWidget() {
  const { stats, loading } = useStats();
  const forecast = stats?.forecast ?? [];
  const max = Math.max(1, ...forecast.map((f) => f.count));
  return (
    <Card>
      <WidgetLabel>REVIEW FORECAST</WidgetLabel>
      {loading ? (
        <p className="py-4 font-empty italic text-terraza-soft">un momento ~</p>
      ) : (
        <div className="flex items-end justify-between gap-2 pt-2" style={{ height: 120 }}>
          {forecast.map((r) => (
            <div key={r.label} className="flex flex-1 flex-col items-center gap-1">
              <span className="text-xs text-terraza-soft">{r.count || ""}</span>
              <div className="flex w-full flex-1 items-end">
                <div
                  className="w-full rounded-t-[6px] bg-terraza-accent transition-all"
                  style={{ height: `${(r.count / max) * 100}%`, minHeight: r.count ? 4 : 0 }}
                />
              </div>
              <span className="text-[10px] tracking-label text-terraza-soft">{r.label}</span>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

// ---- small stat tiles --------------------------------------------------

export function XpWidget() {
  const { stats, loading } = useStats();
  const xp = stats?.xp_total ?? 0;
  return (
    <Card>
      <WidgetLabel>XP</WidgetLabel>
      <p className="text-3xl lowercase tracking-cozy">{loading ? "…" : xp.toLocaleString()}</p>
      <p className="mt-1 text-sm text-terraza-soft">total experience</p>
    </Card>
  );
}

export function FluentWidget() {
  const { stats, loading } = useStats();
  const fluent = stats?.items_fluent ?? 0;
  const learned = stats?.items_learned ?? 0;
  return (
    <Card>
      <WidgetLabel>FLUENT</WidgetLabel>
      <p className="text-3xl lowercase tracking-cozy">{loading ? "…" : fluent}</p>
      <p className="mt-1 text-sm text-terraza-soft">
        of {learned} learned {learned > 0 ? `· ${Math.round((fluent / learned) * 100)}%` : ""}
      </p>
    </Card>
  );
}

export function LeechWidget() {
  const { stats, loading } = useStats();
  const leeches = stats?.leeches ?? 0;
  return (
    <Link href="/items" className="block h-full">
      <Card className="transition-transform hover:-translate-y-0.5">
        <WidgetLabel>TRICKY ITEMS</WidgetLabel>
        <p className="text-3xl lowercase tracking-cozy">{loading ? "…" : leeches}</p>
        <p className="mt-1 text-sm text-terraza-soft">
          {leeches > 0 ? "items that keep tripping you up" : "nothing giving you trouble ~"}
        </p>
      </Card>
    </Link>
  );
}

// ---- welcome banner ----------------------------------------------------

export function PracticeWidget() {
  return (
    <Card>
      <WidgetLabel>PRACTICE</WidgetLabel>
      <p className="text-sm text-terraza-soft">
        drill weak items, fill-in-the-blank, or conjugate verbs — extra reps, no schedule.
      </p>
      <Link href="/practice"
        className="mt-4 inline-block rounded-full bg-terraza-pill px-5 py-2 tracking-cozy">
        open practice →
      </Link>
    </Card>
  );
}

export function WelcomeWidget() {
  const { user } = useAuth();
  const { stats } = useStats();
  const name = user?.name?.trim() || user?.email?.split("@")[0] || "amigo";
  const due = stats?.reviews_due ?? 0;
  const lessons = stats?.lessons_available ?? 0;

  const line =
    due > 0 ? `you have ${due} ${due === 1 ? "review" : "reviews"} waiting.`
    : lessons > 0 ? `ready to learn something new?`
    : `all caught up — nicely done.`;

  return (
    <Card>
      <WidgetLabel>¡HOLA!</WidgetLabel>
      <p className="text-2xl lowercase tracking-cozy">
        Welcome back, {name} <span className="text-terraza-accent">✦</span>
      </p>
      <p className="mt-2 text-terraza-soft">{line}</p>
    </Card>
  );
}
