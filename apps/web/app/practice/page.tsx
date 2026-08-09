"use client";

// Practice playground (by request). Grouped into categories — drills, testing,
// reading — so a learner can find what they want by section instead of reading
// every card. Testing and reading used to be separate header links; they're
// practice components now.

import Link from "next/link";
import { Header } from "@/components/header";
import { Protected } from "@/components/protected";
import { Card } from "@/components/ui";
import { PRACTICE_MODES } from "@/lib/learn-api";
import { TEST_MAPS } from "@/lib/testing-api";

const TEST_ICON: Record<string, string> = { cefr: "🎓", app: "📘", life: "🌍" };

export default function PracticeHub() {
  return (
    <Protected>
      <Header />
      <main className="mx-auto max-w-7xl px-4 py-8">
        <h1 className="mb-2 text-3xl lowercase tracking-cozy sm:text-4xl">practice</h1>
        <p className="mb-8 text-terraza-soft">
          the playground — extra reps, comprehension checks, and reading, all in one place.
          practice earns xp and builds mastery, but doesn&apos;t change your review schedule.
        </p>

        <Section
          tint="pink"
          label="drills"
          blurb="targeted reps from what you've already learned."
        >
          {PRACTICE_MODES.map((m) => (
            <Tile key={m.id} href={`/practice/${m.id}`} icon={m.icon} title={m.title} desc={m.desc} />
          ))}
          <Tile
            href="/practice/speaking"
            icon="🎙"
            title="speaking"
            desc="say phrases out loud — your device transcribes and scores them"
          />
        </Section>

        <Section
          tint="gold"
          label="test yourself"
          blurb="structured comprehension checks — pick a map."
        >
          {TEST_MAPS.map((m) => (
            <Tile key={m.id} href={`/tests/${m.id}`} icon={TEST_ICON[m.id] ?? "📝"} title={m.title} desc={m.blurb} />
          ))}
        </Section>

        <Section
          tint="green"
          label="read"
          blurb="short texts to read at your own pace."
        >
          <Tile
            href="/reading"
            icon="📖"
            title="reading library"
            desc="tap a word for its meaning, and highlight anything to leave yourself a note"
          />
        </Section>
      </main>
    </Protected>
  );
}

const TINT: Record<string, string> = {
  pink: "bg-terraza-pink/15",
  gold: "bg-terraza-gold/15",
  green: "bg-terraza-green/15",
};

function Section({
  tint, label, blurb, children,
}: {
  tint: "pink" | "gold" | "green"; label: string; blurb: string; children: React.ReactNode;
}) {
  return (
    <section className={`mb-6 rounded-card border border-terraza-dash p-5 ${TINT[tint]}`}>
      <h2 className="text-xs tracking-label text-terraza-soft">{label.toUpperCase()}</h2>
      <p className="mb-4 mt-1 text-sm text-terraza-soft">{blurb}</p>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {children}
      </div>
    </section>
  );
}

function Tile({
  href, icon, title, desc,
}: { href: string; icon: string; title: string; desc: string }) {
  return (
    <Link href={href}>
      <Card className="transition-transform hover:-translate-y-1">
        <div className="text-3xl text-terraza-accent">{icon}</div>
        <p className="mt-3 text-lg lowercase tracking-cozy">{title}</p>
        <p className="mt-1 text-sm text-terraza-soft">{desc}</p>
        <p className="mt-4 text-xs tracking-label text-terraza-accent">START →</p>
      </Card>
    </Link>
  );
}
