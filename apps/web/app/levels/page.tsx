"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Header } from "@/components/header";
import { Footer } from "@/components/footer";
import { Protected } from "@/components/protected";
import { Card } from "@/components/ui";
import { items as itemsApi, type LevelProgress } from "@/lib/items-api";
import { learn, type Level } from "@/lib/learn-api";

// The levels page is now a grid of cards. Clicking a card expands it in place
// to show every vocabulary and grammar item in that level (fetched from the
// level-progress endpoint built in slice 8) — no navigation, so browsing the
// curriculum stays on one screen.

export default function LevelsPage() {
  return (
    <Protected>
      <Header />
      <main className="mx-auto max-w-7xl px-4 py-8">
        <h1 className="mb-1 text-2xl lowercase tracking-cozy">levels</h1>
        <p className="mb-6 text-terraza-soft">
          tap a level to see its words and grammar. tap again to start a lesson.
        </p>
        <LevelGrid />
      </main>
      <Footer />
    </Protected>
  );
}

function LevelGrid() {
  const [levels, setLevels] = useState<Level[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [openLevel, setOpenLevel] = useState<number | null>(null);

  useEffect(() => {
    learn.levels().then(setLevels).catch((e) => setError(e.message));
  }, []);

  if (error) return <Card><p role="alert" className="text-terraza-danger">{error}</p></Card>;
  if (!levels) {
    return <p className="font-empty italic text-terraza-soft">un momento ~</p>;
  }
  if (levels.length === 0) {
    return (
      <Card>
        <p className="text-center font-empty italic text-terraza-soft">
          no levels yet ~
        </p>
        <p className="mt-2 text-center text-sm text-terraza-soft">
          an admin needs to import and publish the curriculum.
        </p>
      </Card>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {levels.map((level) => (
        <LevelCard
          key={level.id}
          level={level}
          open={openLevel === level.position}
          onToggle={() =>
            setOpenLevel((cur) => (cur === level.position ? null : level.position))
          }
        />
      ))}
    </div>
  );
}

function LevelCard({
  level, open, onToggle,
}: { level: Level; open: boolean; onToggle: () => void }) {
  const locked = !level.unlocked;

  return (
    <div
      className={`rounded-card border bg-terraza-card transition-shadow ${
        open ? "border-terraza-accent shadow-md sm:col-span-2 lg:col-span-3"
             : "border-terraza-dash"
      }`}
    >
      <button
        onClick={onToggle}
        disabled={locked}
        aria-expanded={open}
        className="flex w-full items-center gap-4 p-5 text-left disabled:cursor-not-allowed"
      >
        <span
          className={`flex h-12 w-12 flex-none items-center justify-center rounded-full text-lg ${
            locked
              ? "bg-terraza-pill text-terraza-soft"
              : "bg-terraza-accent text-terraza-accentInk"
          }`}
        >
          {level.position}
        </span>
        <span className="mr-auto">
          <span className="block lowercase tracking-cozy">{level.title}</span>
          <span className="block text-sm text-terraza-soft">
            {level.vocab_count} words · {level.grammar_count} grammar
          </span>
        </span>
        {locked ? (
          <span className="text-sm text-terraza-soft">locked</span>
        ) : (
          <span aria-hidden="true" className="text-terraza-soft">
            {open ? "▲" : "▼"}
          </span>
        )}
      </button>

      {/* Locked levels show exactly how far off the previous level is. */}
      {locked && level.unlock_progress && (
        <div className="border-t border-terraza-dash px-5 pb-5 pt-3">
          <div className="flex items-baseline text-xs tracking-label text-terraza-soft">
            <span>REACH FAMILIAR 1 IN LEVEL {level.position - 1}</span>
            <span className="ml-auto">{level.unlock_progress.percent}%</span>
          </div>
          <div className="mt-2 h-2 overflow-hidden rounded-full bg-terraza-bg">
            <div className="h-full rounded-full bg-terraza-gold transition-all motion-reduce:transition-none"
                 style={{ width: `${level.unlock_progress.percent}%` }} />
          </div>
        </div>
      )}

      {open && !locked && <LevelContents level={level} />}
    </div>
  );
}

function LevelContents({ level }: { level: Level }) {
  const [data, setData] = useState<LevelProgress | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    itemsApi.levelProgress(level.position)
      .then((d) => { if (live) setData(d); })
      .catch((e) => { if (live) setError(e.message); });
    return () => { live = false; };
  }, [level.position]);

  if (error) {
    return <p className="px-5 pb-5 text-sm text-terraza-danger">{error}</p>;
  }
  if (!data) {
    return (
      <p className="px-5 pb-5 font-empty italic text-terraza-soft">un momento ~</p>
    );
  }

  const vocab = data.items.filter((i) => i.item_type === "vocabulary");
  const grammar = data.items.filter((i) => i.item_type === "grammar");

  return (
    <div className="border-t border-terraza-dash px-5 pb-5 pt-4">
      <div className="mb-4 flex flex-wrap gap-3">
        <Link
          href={`/levels/${level.position}`}
          className="rounded-full bg-terraza-accent px-5 py-2 text-sm tracking-cozy text-terraza-accentInk"
        >
          open lessons →
        </Link>
        <Link
          href={`/levels/${level.position}/progress`}
          className="rounded-full bg-terraza-pill px-5 py-2 text-sm tracking-cozy"
        >
          full progress →
        </Link>
      </div>

      {grammar.length > 0 && (
        <>
          <h3 className="mb-2 text-xs tracking-label text-terraza-soft">GRAMMAR</h3>
          <ItemChips items={grammar} />
        </>
      )}

      <h3 className="mb-2 mt-4 text-xs tracking-label text-terraza-soft">VOCABULARY</h3>
      <ItemChips items={vocab} />
    </div>
  );
}

function ItemChips({
  items,
}: { items: LevelProgress["items"] }) {
  if (items.length === 0) {
    return <p className="font-empty italic text-terraza-soft">nothing here yet ~</p>;
  }
  return (
    <ul className="flex flex-wrap gap-2">
      {items.map((item) => (
        <li key={`${item.item_type}:${item.item_id}`}>
          <Link
            href={`/items/${item.item_type}/${item.item_id}`}
            className={`inline-flex items-center gap-2 rounded-full px-3 py-1.5 text-sm transition-transform duration-200 hover:-translate-y-0.5 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-terraza-ink motion-reduce:transition-none motion-reduce:hover:translate-y-0 ${
              item.learned ? "bg-terraza-pill" : "bg-terraza-bg border border-terraza-dash"
            }`}
          >
            <span className="lowercase tracking-cozy">
              {item.article ? `${item.article} ` : ""}{item.term}
            </span>
            {item.perfect && <span aria-hidden="true" title="perfect">✦</span>}
          </Link>
        </li>
      ))}
    </ul>
  );
}
