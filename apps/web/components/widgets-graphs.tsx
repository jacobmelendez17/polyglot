"use client";

// Dashboard graph widgets (slice 47, corrects slice 46), Bunpro-style:
//
//   ForecastBarsWidget    — bars for today + the next 6 days (by weekday). Click
//                           a day to drill into its 24-hour forecast; a back
//                           button returns to the week.
//   ReviewActivityWidget  — a *forecast* line of upcoming review load over the
//                           NEXT 7 days / NEXT 24 hours. It's cumulative, so it
//                           always starts at y=0 and rises. The 7d/24h toggle
//                           MORPHS the same line (points spring to new spots)
//                           rather than wiping and redrawing.
//
// Both read GET /me/reviews/forecast. Motion drives the physics; reduced motion
// collapses everything to instant.

import { useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { Card } from "@/components/ui";
import { forecastApi, type ForecastPayload } from "@/lib/forecast-api";

function WidgetLabel({ children }: { children: React.ReactNode }) {
  return <div className="text-xs tracking-label text-terraza-soft">{children}</div>;
}

function useForecast() {
  const [data, setData] = useState<ForecastPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    forecastApi.get().then((d) => { if (live) setData(d); }).catch((e) => { if (live) setError(e.message); });
    return () => { live = false; };
  }, []);
  return { data, error };
}

// ---- forecast bars, with day → hour drill-down ---------------------------

export function ForecastBarsWidget() {
  const { data, error } = useForecast();
  const reduce = useReducedMotion();
  const [openDay, setOpenDay] = useState<number | null>(null);

  return (
    <Card>
      <div className="mb-3 flex items-center justify-between">
        <WidgetLabel>REVIEW FORECAST</WidgetLabel>
        {openDay !== null && (
          <button onClick={() => setOpenDay(null)}
            className="text-xs text-terraza-soft underline underline-offset-2 hover:text-terraza-accent">
            ← week
          </button>
        )}
      </div>

      {error ? (
        <p role="alert" className="py-6 text-center text-sm text-terraza-danger">{error}</p>
      ) : !data ? (
        <p className="py-6 text-center font-empty italic text-terraza-soft">un momento ~</p>
      ) : openDay === null ? (
        <Bars
          reduce={!!reduce}
          bars={data.days.map((d) => ({ label: d.label, count: d.count }))}
          onPick={(i) => setOpenDay(i)}
          labelEvery={1}
        />
      ) : (
        <>
          <p className="mb-1 text-sm text-terraza-soft">
            {data.days[openDay].label === "today" ? "today" : data.days[openDay].label} · by hour
          </p>
          <Bars
            reduce={!!reduce}
            bars={data.days[openDay].hours.map((c, h) => ({ label: `${h}`.padStart(2, "0"), count: c }))}
            labelEvery={6}
          />
        </>
      )}
    </Card>
  );
}

function Bars({
  bars, reduce, onPick, labelEvery,
}: {
  bars: { label: string; count: number }[];
  reduce: boolean;
  onPick?: (index: number) => void;
  labelEvery: number;
}) {
  const max = Math.max(1, ...bars.map((b) => b.count));
  return (
    <div className="flex items-end justify-between gap-1 pt-1" style={{ height: 120 }}>
      {bars.map((b, i) => {
        const bar = (
          <div className="flex w-full flex-1 flex-col items-center gap-1">
            <span className="text-[10px] text-terraza-soft">{b.count || ""}</span>
            <div className="flex w-full flex-1 items-end">
              <motion.div
                className="w-full origin-bottom rounded-t-[5px] bg-terraza-accent"
                style={{ height: `${(b.count / max) * 100}%`, minHeight: b.count ? 4 : 0 }}
                initial={reduce ? { scaleY: 1 } : { scaleY: 0 }}
                animate={{ scaleY: 1 }}
                transition={reduce ? { duration: 0 } : { type: "spring", stiffness: 260, damping: 18, delay: i * 0.03 }}
                aria-hidden="true"
              />
            </div>
            <span className="h-3 text-[9px] tracking-label text-terraza-soft">
              {i % labelEvery === 0 ? b.label : ""}
            </span>
          </div>
        );
        return onPick ? (
          <button key={i} onClick={() => onPick(i)} aria-label={`${b.label}: ${b.count} reviews — see hourly`}
            className="flex flex-1 rounded-[6px] hover:bg-terraza-pill/40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-terraza-ink">
            {bar}
          </button>
        ) : (
          <div key={i} className="flex flex-1">{bar}</div>
        );
      })}
    </div>
  );
}

// ---- cumulative forecast line (morphs on toggle) -------------------------

type View = "7d" | "24h";
const W = 300, H = 96, PAD = 10, BASE = H - PAD, N = 25;

function buildPoints(counts: number[]) {
  const cum = [0];
  let sum = 0;
  for (const c of counts) { sum += c; cum.push(sum); }
  const total = Math.max(1, sum);
  const M = cum.length;
  const pts: { x: number; y: number }[] = [];
  for (let i = 0; i < N; i++) {
    const f = i / (N - 1);
    const pos = f * (M - 1);
    const lo = Math.floor(pos), hi = Math.min(M - 1, lo + 1), frac = pos - lo;
    const val = cum[lo] * (1 - frac) + cum[hi] * frac;
    pts.push({ x: PAD + f * (W - 2 * PAD), y: BASE - (val / total) * (H - 2 * PAD) });
  }
  return pts;
}
const pathOf = (pts: { x: number; y: number }[]) =>
  pts.map((p, i) => `${i ? "L" : "M"} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(" ");
const FLAT = pathOf(Array.from({ length: N }, (_, i) => ({ x: PAD + (i / (N - 1)) * (W - 2 * PAD), y: BASE })));

export function ReviewActivityWidget() {
  const { data, error } = useForecast();
  const reduce = useReducedMotion();
  const [view, setView] = useState<View>("7d");

  const counts = useMemo(() => {
    if (!data) return [] as number[];
    return view === "7d" ? data.days.map((d) => d.count) : data.next_24h.map((h) => h.count);
  }, [data, view]);
  const pts = useMemo(() => buildPoints(counts.length ? counts : [0]), [counts]);
  const d = pathOf(pts);
  const total = counts.reduce((s, c) => s + c, 0);
  const spring = reduce ? { duration: 0 } : { type: "spring", stiffness: 170, damping: 22 };

  return (
    <Card>
      <div className="mb-3 flex items-center justify-between">
        <WidgetLabel>UPCOMING REVIEWS</WidgetLabel>
        <div role="tablist" aria-label="forecast range" className="inline-flex rounded-full border border-terraza-dash p-0.5 text-xs">
          {(["7d", "24h"] as View[]).map((v) => (
            <button key={v} role="tab" aria-selected={view === v} onClick={() => setView(v)}
              className={`rounded-full px-2.5 py-1 tracking-cozy ${view === v ? "bg-terraza-accent text-terraza-accentInk" : "text-terraza-soft"}`}>
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
        <>
          <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} role="img"
            aria-label={`cumulative reviews coming due over the next ${view === "7d" ? "7 days" : "24 hours"}`}>
            <line x1={PAD} y1={BASE} x2={W - PAD} y2={BASE} stroke="var(--lg-dash, #d8cfc2)" strokeWidth="1" />
            <motion.path
              fill="none" stroke="var(--lg-accent, #4c8c7d)" strokeWidth="2"
              strokeLinejoin="round" strokeLinecap="round"
              initial={{ d: FLAT }}
              animate={{ d }}
              transition={spring}
            />
            {pts.map((p, i) => (
              <motion.circle
                key={i} cx={p.x} r={1.8} fill="var(--lg-accent, #4c8c7d)"
                initial={reduce ? { cy: p.y } : { cy: BASE }}
                animate={{ cy: p.y }}
                transition={reduce ? { duration: 0 } : { ...spring, delay: i * 0.006 }}
              />
            ))}
          </svg>
          <p className="mt-2 text-center text-sm text-terraza-soft">
            {total === 0
              ? (view === "7d" ? "nothing due in the next 7 days ~" : "nothing due in the next 24 hours ~")
              : `${total} ${total === 1 ? "review" : "reviews"} coming ${view === "7d" ? "this week" : "in 24 hours"}`}
          </p>
        </>
      )}
    </Card>
  );
}
