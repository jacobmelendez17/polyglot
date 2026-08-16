"use client";

// Spring-animated dashboard graph widgets (slice 46), Bunpro-style:
//   ForecastBarsWidget    — a bar graph of reviews arriving over the next 7 days
//   ReviewActivityWidget  — a line graph of how often you review, with a 7-day /
//                           24-hour toggle that springs between the two series
// Motion drives the physics; everything collapses to instant under reduced motion.

import { useEffect, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { Card } from "@/components/ui";
import { learn, type Stats } from "@/lib/learn-api";
import { activityApi, type ActivityBucket, type ActivitySeries } from "@/lib/activity-api";

function WidgetLabel({ children }: { children: React.ReactNode }) {
  return <div className="mb-3 text-xs tracking-label text-terraza-soft">{children}</div>;
}

// small shared stats cache (mirrors widgets-extra) so the graphs don't refetch
let statsCache: { at: number; stats: Stats } | null = null;
const CACHE_MS = 15_000;
function useStats() {
  const [stats, setStats] = useState<Stats | null>(statsCache?.stats ?? null);
  const [loading, setLoading] = useState(!statsCache);
  useEffect(() => {
    if (statsCache && Date.now() - statsCache.at < CACHE_MS) { setStats(statsCache.stats); setLoading(false); return; }
    let live = true;
    learn.stats().then((s) => { statsCache = { at: Date.now(), stats: s }; if (live) { setStats(s); setLoading(false); } })
      .catch(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, []);
  return { stats, loading };
}

// ---- forecast bars --------------------------------------------------------

export function ForecastBarsWidget() {
  const { stats, loading } = useStats();
  const reduce = useReducedMotion();
  const forecast = stats?.forecast ?? [];
  const max = Math.max(1, ...forecast.map((f) => f.count));

  return (
    <Card>
      <WidgetLabel>REVIEW FORECAST</WidgetLabel>
      {loading ? (
        <p className="py-4 font-empty italic text-terraza-soft">un momento ~</p>
      ) : (
        <div className="flex items-end justify-between gap-2 pt-2" style={{ height: 120 }}>
          {forecast.map((r, i) => (
            <div key={r.label} className="flex flex-1 flex-col items-center gap-1">
              <span className="text-xs text-terraza-soft">{r.count || ""}</span>
              <div className="flex w-full flex-1 items-end">
                <motion.div
                  className="w-full origin-bottom rounded-t-[6px] bg-terraza-accent"
                  style={{ height: `${(r.count / max) * 100}%`, minHeight: r.count ? 4 : 0 }}
                  initial={reduce ? { scaleY: 1 } : { scaleY: 0 }}
                  animate={{ scaleY: 1 }}
                  transition={reduce ? { duration: 0 } : { type: "spring", stiffness: 260, damping: 18, delay: i * 0.05 }}
                  aria-hidden="true"
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

// ---- review activity line + toggle ---------------------------------------

type View = "7d" | "24h";
const W = 300;
const H = 96;
const PAD = 10;

function pointsFor(series: ActivityBucket[]) {
  const max = Math.max(1, ...series.map((b) => b.count));
  const n = Math.max(1, series.length);
  return series.map((b, i) => ({
    x: PAD + (i * (W - 2 * PAD)) / (n - 1 || 1),
    y: H - PAD - (b.count / max) * (H - 2 * PAD),
    count: b.count,
    label: b.label,
  }));
}

function linePath(pts: { x: number; y: number }[]) {
  if (pts.length === 0) return "";
  return pts.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(" ");
}

export function ReviewActivityWidget() {
  const reduce = useReducedMotion();
  const [view, setView] = useState<View>("7d");
  const [data, setData] = useState<ActivitySeries | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    activityApi.get().then((d) => { if (live) setData(d); }).catch((e) => { if (live) setError(e.message); });
    return () => { live = false; };
  }, []);

  const spring = reduce ? { duration: 0 } : { type: "spring", stiffness: 200, damping: 22 };

  return (
    <Card>
      <div className="mb-3 flex items-center justify-between">
        <WidgetLabel>REVIEW ACTIVITY</WidgetLabel>
        <div role="tablist" aria-label="activity range" className="inline-flex rounded-full border border-terraza-dash p-0.5 text-xs">
          {(["7d", "24h"] as View[]).map((v) => (
            <button
              key={v}
              role="tab"
              aria-selected={view === v}
              onClick={() => setView(v)}
              className={`rounded-full px-2.5 py-1 tracking-cozy ${view === v ? "bg-terraza-accent text-terraza-accentInk" : "text-terraza-soft"}`}
            >
              {v === "7d" ? "7 days" : "24 hours"}
            </button>
          ))}
        </div>
      </div>

      {error ? (
        <p role="alert" className="py-6 text-center text-sm text-terraza-danger">{error}</p>
      ) : !data ? (
        <p className="py-6 text-center font-empty italic text-terraza-soft">un momento ~</p>
      ) : (
        <ActivityChart
          view={view}
          series={view === "7d" ? data.seven_day : data.twenty_four_hour}
          reduce={!!reduce}
          spring={spring}
        />
      )}
    </Card>
  );
}

function ActivityChart({
  view, series, reduce, spring,
}: {
  view: View;
  series: ActivityBucket[];
  reduce: boolean;
  spring: object;
}) {
  const pts = pointsFor(series);
  const total = series.reduce((s, b) => s + b.count, 0);
  const baseline = H - PAD;
  // sparse x labels so 24 buckets don't crowd
  const every = view === "24h" ? 6 : 1;

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={view}
        initial={reduce ? { opacity: 0 } : { opacity: 0, x: 24 }}
        animate={{ opacity: 1, x: 0 }}
        exit={reduce ? { opacity: 0 } : { opacity: 0, x: -24 }}
        transition={spring}
      >
        <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} role="img"
          aria-label={`reviews per ${view === "7d" ? "day over the last 7 days" : "hour over the last 24 hours"}`}>
          {/* baseline */}
          <line x1={PAD} y1={baseline} x2={W - PAD} y2={baseline} stroke="var(--lg-dash, #d8cfc2)" strokeWidth="1" />
          {/* line */}
          <motion.path
            d={linePath(pts)}
            fill="none"
            stroke="var(--lg-accent, #4c8c7d)"
            strokeWidth="2"
            strokeLinejoin="round"
            strokeLinecap="round"
            initial={reduce ? { pathLength: 1, opacity: 1 } : { pathLength: 0, opacity: 0 }}
            animate={{ pathLength: 1, opacity: 1 }}
            transition={reduce ? { duration: 0 } : { type: "spring", stiffness: 90, damping: 18 }}
          />
          {/* points rise from the baseline */}
          {pts.map((p, i) => (
            <motion.circle
              key={i}
              cx={p.x}
              r={p.count > 0 ? 2.6 : 1.6}
              fill="var(--lg-accent, #4c8c7d)"
              initial={reduce ? { cy: p.y, opacity: 1 } : { cy: baseline, opacity: 0 }}
              animate={{ cy: p.y, opacity: 1 }}
              transition={reduce ? { duration: 0 } : { type: "spring", stiffness: 300, damping: 20, delay: i * 0.015 }}
            />
          ))}
        </svg>
        <div className="mt-1 flex justify-between text-[10px] tracking-label text-terraza-soft">
          {series.map((b, i) => (
            <span key={i} className="flex-1 text-center">{i % every === 0 ? b.label : ""}</span>
          ))}
        </div>
        <p className="mt-2 text-center text-sm text-terraza-soft">
          {total === 0
            ? (view === "7d" ? "no reviews in the last 7 days ~" : "no reviews in the last 24 hours ~")
            : `${total} ${total === 1 ? "review" : "reviews"} ${view === "7d" ? "this week" : "today"}`}
        </p>
      </motion.div>
    </AnimatePresence>
  );
}
