"use client";

import { Card } from "./ui";
import { useAuth } from "@/lib/auth-context";

function WidgetLabel({ children }: { children: React.ReactNode }) {
  return <div className="mb-3 text-xs tracking-label text-terraza-soft">{children}</div>;
}

function Empty({ children }: { children: React.ReactNode }) {
  return <p className="py-6 text-center font-empty italic text-terraza-soft">{children}</p>;
}

export function ProgressionWidget() {
  return (
    <Card>
      <WidgetLabel>YOUR PROGRESS</WidgetLabel>
      <p className="text-lg lowercase tracking-cozy">level 1 · el comienzo</p>
      <div className="mt-3 h-3 overflow-hidden rounded-full bg-terraza-bg">
        <div className="h-full rounded-full bg-terraza-accent" style={{ width: "0%" }} />
      </div>
      <p className="mt-2 text-sm text-terraza-soft">0 / 48 words · 0 / 12 grammar</p>
    </Card>
  );
}

export function ReviewsWidget() {
  return (
    <Card>
      <WidgetLabel>REVIEWS</WidgetLabel>
      <Empty>nothing due yet ~<br /><span className="text-sm">reviews unlock after your first lesson</span></Empty>
    </Card>
  );
}

export function LessonWidget() {
  return (
    <Card>
      <WidgetLabel>NEXT LESSON</WidgetLabel>
      <p className="text-lg lowercase tracking-cozy">los números</p>
      <p className="mt-1 text-sm text-terraza-soft">12 words · level 1, lesson 1</p>
      <button
        disabled
        className="mt-4 rounded-full bg-terraza-pill px-5 py-2 tracking-cozy text-terraza-soft"
        title="Lessons arrive in the next slice"
      >
        start lesson (soon)
      </button>
    </Card>
  );
}

export function StreakWidget() {
  return (
    <Card>
      <WidgetLabel>STREAK</WidgetLabel>
      <p className="text-3xl lowercase tracking-cozy">0 días</p>
      <p className="mt-1 text-sm text-terraza-soft">complete a lesson to start your streak</p>
    </Card>
  );
}

export function ForecastWidget() {
  const rows = [
    { label: "today", pct: 0, n: 0 },
    { label: "mañana", pct: 0, n: 0 },
    { label: "lunes", pct: 0, n: 0 },
  ];
  return (
    <Card>
      <WidgetLabel>FORECAST</WidgetLabel>
      {rows.map((r) => (
        <div key={r.label} className="mb-2 flex items-center gap-3 text-sm">
          <span className="w-16 text-terraza-soft">{r.label}</span>
          <div className="h-3 flex-1 overflow-hidden rounded-full bg-terraza-bg">
            <div className="h-full rounded-full bg-terraza-green" style={{ width: `${r.pct}%` }} />
          </div>
          <span className="w-6 text-right text-terraza-soft">{r.n}</span>
        </div>
      ))}
    </Card>
  );
}

export function WelcomeWidget() {
  const { user } = useAuth();
  const name = user?.email?.split("@")[0] ?? "amigo";
  return (
    <Card className="md:col-span-2">
      <WidgetLabel>¡HOLA!</WidgetLabel>
      <p className="text-2xl lowercase tracking-cozy">
        welcome, {name} <span className="text-terraza-accent">✦</span>
      </p>
      <p className="mt-2 text-terraza-soft">
        your account is ready. lessons, reviews, and the full journey map arrive in the next
        updates — for now, this is your home base.
      </p>
    </Card>
  );
}
