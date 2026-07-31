"use client";

import Link from "next/link";
import { Header } from "@/components/header";
import { Protected } from "@/components/protected";
import { Card } from "@/components/ui";
import { PRACTICE_MODES } from "@/lib/learn-api";

export default function PracticeHub() {
  return (
    <Protected>
      <Header />
      <main className="mx-auto max-w-7xl px-4 py-8">
        <h1 className="mb-2 text-2xl lowercase tracking-cozy">practice</h1>
        <p className="mb-6 text-terraza-soft">
          extra drilling from what you&apos;ve learned. practice earns XP and builds mastery,
          but doesn&apos;t change your review schedule.
        </p>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          {PRACTICE_MODES.map((m) => (
            <Link key={m.id} href={`/practice/${m.id}`}>
              <Card className="transition-transform hover:-translate-y-1">
                <div className="text-3xl text-terraza-accent">{m.icon}</div>
                <p className="mt-3 text-lg lowercase tracking-cozy">{m.title}</p>
                <p className="mt-1 text-sm text-terraza-soft">{m.desc}</p>
                <p className="mt-4 text-xs tracking-label text-terraza-accent">START →</p>
              </Card>
            </Link>
          ))}
        </div>
      </main>
    </Protected>
  );
}
