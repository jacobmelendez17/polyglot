"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Footer } from "@/components/footer";
import { Header } from "@/components/header";
import { Protected } from "@/components/protected";
import { Card } from "@/components/ui";
import { decks, type DeckSummary } from "@/lib/account-api";

const DECK_GLYPH: Record<string, string> = {
  vocabulary: "✦",
  grammar: "❋",
  intermissions: "❍",
};

export default function DecksPage() {
  return (
    <Protected>
      <Header />
      <main className="mx-auto max-w-5xl px-4 py-8">
        <h1 className="mb-1 text-2xl lowercase tracking-cozy">decks</h1>
        <p className="mb-6 text-terraza-soft">
          browse what you&apos;ve unlocked — your words, your grammar, and the readings
          you&apos;ve come across.
        </p>
        <DeckGrid />
      </main>
      <Footer />
    </Protected>
  );
}

function DeckGrid() {
  const [list, setList] = useState<DeckSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    decks.list().then(setList).catch((e) => setError(e.message));
  }, []);

  if (error) return <Card><p role="alert" className="text-terraza-danger">{error}</p></Card>;
  if (!list) return <p className="font-empty italic text-terraza-soft">un momento ~</p>;

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
      {list.map((deck) => (
        <Link key={deck.type} href={`/decks/${deck.type}`}>
          <Card className="h-full transition-transform duration-200 hover:-translate-y-1 motion-reduce:transition-none motion-reduce:hover:translate-y-0">
            <div className="text-3xl text-terraza-accent">
              {DECK_GLYPH[deck.type] ?? "✦"}
            </div>
            <p className="mt-3 text-lg lowercase tracking-cozy">{deck.title}</p>
            <p className="mt-1 text-sm text-terraza-soft">{deck.description}</p>
            <p className="mt-4 text-xs tracking-label text-terraza-accent">
              {deck.count} {deck.count === 1 ? "CARD" : "CARDS"} →
            </p>
          </Card>
        </Link>
      ))}
    </div>
  );
}
