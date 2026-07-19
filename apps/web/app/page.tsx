"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/lib/auth-context";

export default function Landing() {
  const { user, loading } = useAuth();
  const router = useRouter();

  // Signed-in visitors go straight to their dashboard.
  useEffect(() => {
    if (!loading && user) router.replace("/dashboard");
  }, [user, loading, router]);

  return (
    <div className="min-h-screen">
      {/* Nav */}
      <header className="mx-auto flex max-w-5xl items-center px-6 py-5">
        <span className="mr-auto text-lg lowercase tracking-cozy">
          polyglot <span className="text-terraza-accent">✦</span>
        </span>
        <nav className="flex items-center gap-2">
          <Link href="/login" className="rounded-full px-4 py-2 text-terraza-soft hover:bg-terraza-pill">
            sign in
          </Link>
          <Link
            href="/signup"
            className="rounded-full bg-terraza-accent px-5 py-2 text-terraza-accentInk"
          >
            get started
          </Link>
        </nav>
      </header>

      {/* Hero */}
      <section className="mx-auto max-w-3xl px-6 pt-16 pb-10 text-center">
        <span className="inline-block rounded-full bg-terraza-pill px-4 py-1.5 text-xs tracking-label text-terraza-soft">
          ✦ SPANISH · LATIN AMERICAN · COZY
        </span>
        <h1 className="mt-6 text-4xl leading-tight lowercase tracking-cozy sm:text-5xl">
          learn spanish,<br />
          <span className="text-terraza-accent">one cozy review at a time</span>
        </h1>
        <p className="mx-auto mt-5 max-w-xl text-terraza-soft">
          a spaced-repetition journey from your first "hola" to real conversations —
          vocabulary, grammar, listening, writing, and speaking, all in one warm place.
        </p>
        <div className="mt-8 flex items-center justify-center gap-3">
          <Link
            href="/signup"
            className="rounded-full bg-terraza-accent px-7 py-3 tracking-cozy text-terraza-accentInk transition-transform hover:-translate-y-0.5"
          >
            start free →
          </Link>
          <Link
            href="/login"
            className="rounded-full bg-terraza-pill px-7 py-3 tracking-cozy text-terraza-ink"
          >
            i have an account
          </Link>
        </div>
      </section>

      {/* Feature cards */}
      <section className="mx-auto max-w-4xl px-6 py-10">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {[
            {
              t: "remember it for good",
              d: "a proven spaced-repetition system schedules each word right before you'd forget it — nine stages from beginner to fluent.",
            },
            {
              t: "more than flashcards",
              d: "grammar, listening, writing, speaking, and journaling — the four skills you actually need, woven into one journey.",
            },
            {
              t: "built for latin america",
              d: "mexican-first vocabulary and dialect, with regional notes so what you learn is what people actually say.",
            },
          ].map((f) => (
            <div
              key={f.t}
              className="rounded-card border border-terraza-dash bg-terraza-card p-6"
              style={{ boxShadow: "0 2px 0 var(--lg-dash)" }}
            >
              <div className="mb-3 h-2 w-8 rounded-full bg-terraza-accent" />
              <h3 className="lowercase tracking-cozy">{f.t}</h3>
              <p className="mt-2 text-sm text-terraza-soft">{f.d}</p>
            </div>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section className="mx-auto max-w-3xl px-6 py-10">
        <h2 className="text-center text-2xl lowercase tracking-cozy">how it works</h2>
        <ol className="mt-6 flex flex-col gap-4">
          {[
            ["learn a batch", "pick up 12 words or a set of grammar points in a themed lesson."],
            ["review on schedule", "each item comes back right when you need it — spanish→english and back."],
            ["grow every skill", "unlock listening, writing, and speaking practice as you level up."],
          ].map(([t, d], i) => (
            <li
              key={t}
              className="flex items-start gap-4 rounded-card border border-terraza-dash bg-terraza-card p-5"
            >
              <span className="flex h-8 w-8 flex-none items-center justify-center rounded-full bg-terraza-pill text-sm">
                {i + 1}
              </span>
              <div>
                <p className="lowercase tracking-cozy">{t}</p>
                <p className="mt-1 text-sm text-terraza-soft">{d}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      {/* Closing CTA */}
      <section className="mx-auto max-w-3xl px-6 py-16 text-center">
        <h2 className="text-2xl lowercase tracking-cozy">the first level is on us</h2>
        <p className="mx-auto mt-3 max-w-md text-terraza-soft">
          start learning today — no card, no catch. begin your journey through spanish.
        </p>
        <Link
          href="/signup"
          className="mt-6 inline-block rounded-full bg-terraza-accent px-7 py-3 tracking-cozy text-terraza-accentInk transition-transform hover:-translate-y-0.5"
        >
          create your account →
        </Link>
      </section>

      <footer className="mx-auto max-w-5xl border-t border-terraza-dash px-6 py-8 text-center text-sm text-terraza-soft">
        polyglot ✦ &nbsp;·&nbsp; a cozy way to learn spanish
      </footer>
    </div>
  );
}
