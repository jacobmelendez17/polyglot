"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Card } from "./ui";
import { useAuth } from "@/lib/auth-context";
import { learn, type Stats } from "@/lib/learn-api";

function WidgetLabel({ children }: { children: React.ReactNode }) {
  return <div className="mb-3 text-xs tracking-label text-terraza-soft">{children}</div>;
}

function Empty({ children }: { children: React.ReactNode }) {
  return <p className="py-6 text-center font-empty italic text-terraza-soft">{children}</p>;
}

// Shared stats fetch. Each widget calls this; React batches the renders and the
// browser caches the request, so we don't hammer the endpoint.
function useStats() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let active = true;
    learn.stats()
      .then((s) => { if (active) setStats(s); })
      .catch(() => { if (active) setStats(null); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);
  return { stats, loading };
}

export function ProgressionWidget() {
  const { stats, loading } = useStats();
  const learned = stats?.items_learned ?? 0;
  const fluent = stats?.items_fluent ?? 0;
  const pct = learned > 0 ? Math.round((fluent / learned) * 100) : 0;
  return (
    <Card>
      <WidgetLabel>YOUR PROGRESS</WidgetLabel>
      {loading ? (
        <Empty>un momento ~</Empty>
      ) : learned === 0 ? (
        <Empty>your journey starts with your first lesson ~</Empty>
      ) : (
        <>
          <p className="text-lg lowercase tracking-cozy">
            {learned} items learned · {fluent} fluent
          </p>
          <div className="mt-3 h-3 overflow-hidden rounded-full bg-terraza-bg">
            <div className="h-full rounded-full bg-terraza-accent transition-all"
                 style={{ width: `${pct}%` }} />
          </div>
          <p className="mt-2 text-sm text-terraza-soft">{pct}% to fluency on learned items</p>
        </>
      )}
    </Card>
  );
}

export function ReviewsWidget() {
  const { stats, loading } = useStats();
  const due = stats?.reviews_due ?? 0;
  return (
    <Card>
      <WidgetLabel>REVIEWS</WidgetLabel>
      {loading ? (
        <Empty>un momento ~</Empty>
      ) : due === 0 ? (
        <Empty>nothing due right now ~<br />
          <span className="text-sm">reviews appear on a schedule</span></Empty>
      ) : (
        <div className="text-center">
          <p className="text-4xl lowercase tracking-cozy">{due}</p>
          <p className="mt-1 text-sm text-terraza-soft">
            {due === 1 ? "item" : "items"} ready to review
          </p>
          <Link href="/reviews"
            className="mt-4 inline-block rounded-full bg-terraza-accent px-5 py-2 tracking-cozy text-terraza-accentInk">
            start reviewing →
          </Link>
        </div>
      )}
    </Card>
  );
}

export function LessonWidget() {
  return (
    <Card>
      <WidgetLabel>LESSONS</WidgetLabel>
      <p className="text-terraza-soft">
        learn new words and grammar, then they flow into your reviews.
      </p>
      <Link href="/levels"
        className="mt-4 inline-block rounded-full bg-terraza-accent px-5 py-2 tracking-cozy text-terraza-accentInk">
        browse levels →
      </Link>
    </Card>
  );
}

export function XpWidget() {
  const { stats, loading } = useStats();
  const xp = stats?.xp_total ?? 0;
  const leeches = stats?.leeches ?? 0;
  return (
    <Card>
      <WidgetLabel>XP</WidgetLabel>
      <p className="text-3xl lowercase tracking-cozy">{loading ? "…" : xp.toLocaleString()}</p>
      <p className="mt-1 text-sm text-terraza-soft">
        {leeches > 0 ? `${leeches} tricky ${leeches === 1 ? "item" : "items"} to watch` : "total experience earned"}
      </p>
    </Card>
  );
}

export function ForecastWidget() {
  const { stats, loading } = useStats();
  const forecast = stats?.forecast ?? [];
  const max = Math.max(1, ...forecast.map((f) => f.count));
  return (
    <Card>
      <WidgetLabel>FORECAST</WidgetLabel>
      {loading ? (
        <Empty>un momento ~</Empty>
      ) : (
        forecast.map((r) => (
          <div key={r.label} className="mb-2 flex items-center gap-3 text-sm">
            <span className="w-16 text-terraza-soft">{r.label}</span>
            <div className="h-3 flex-1 overflow-hidden rounded-full bg-terraza-bg">
              <div className="h-full rounded-full bg-terraza-green transition-all"
                   style={{ width: `${(r.count / max) * 100}%` }} />
            </div>
            <span className="w-6 text-right text-terraza-soft">{r.count}</span>
          </div>
        ))
      )}
    </Card>
  );
}

export function WelcomeWidget() {
  const { user } = useAuth();
  // The name the user chose at signup (falls back to their email handle).
  const name = user?.name?.trim() || user?.email?.split("@")[0] || "amigo";
  return (
    <Card className="md:col-span-2">
      <WidgetLabel>¡HOLA!</WidgetLabel>
      <p className="text-2xl lowercase tracking-cozy">
        Welcome back, {name} <span className="text-terraza-accent">✦</span>
      </p>
      <p className="mt-2 text-terraza-soft">
        pick up where you left off — reviews first, then a new lesson.
      </p>
    </Card>
  );
}
