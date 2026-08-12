"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { Header } from "@/components/header";
import { Protected } from "@/components/protected";
import { Card } from "@/components/ui";
import { items, type LevelProgress, type LevelProgressItem } from "@/lib/items-api";

// The level page now shows the level's actual curriculum: every grammar point as
// a card, then every vocabulary word as a card. Each card links to that item's
// page (§20 — "displays all vocabulary and grammar for that level; clicking an
// item shows all information about it"). Lessons are still reachable from
// /levels (the "open lessons" flow) and each item's own page.

export default function LevelPage() {
  const params = useParams();
  const level = Number(params.level);
  const [data, setData] = useState<LevelProgress | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!level) return;
    let cancelled = false;
    setData(null);
    setError(null);
    items
      .levelProgress(level)
      .then((d) => { if (!cancelled) setData(d); })
      .catch((e) => { if (!cancelled) setError(e.message); });
    return () => { cancelled = true; };
  }, [level]);

  const grammar = data?.items.filter((i) => i.item_type === "grammar") ?? [];
  const vocab = data?.items.filter((i) => i.item_type === "vocabulary") ?? [];

  return (
    <Protected>
      <Header />
      <main className="mx-auto max-w-5xl px-4 py-8">
        <Link href="/levels" className="text-sm text-terraza-soft underline-offset-2 hover:underline">
          ← levels
        </Link>
        <div className="mb-8 mt-2 flex flex-wrap items-center gap-4">
          <h1 className="text-2xl lowercase tracking-cozy">level {level}</h1>
          <Link
            href={`/levels/${level}/progress`}
            className="ml-auto rounded-full bg-terraza-pill px-4 py-1.5 text-sm tracking-cozy transition-transform hover:-translate-y-0.5 motion-reduce:transform-none"
          >
            view progress →
          </Link>
        </div>

        {/* error */}
        {error && (
          <Card>
            <p role="alert" className="text-terraza-danger">{error}</p>
          </Card>
        )}

        {/* loading */}
        {!data && !error && (
          <p className="font-empty italic text-terraza-soft">un momento ~</p>
        )}

        {/* empty */}
        {data && grammar.length === 0 && vocab.length === 0 && (
          <Card>
            <p className="text-center font-empty italic text-terraza-soft">
              nothing in this level yet ~
            </p>
            <p className="mt-2 text-center text-sm text-terraza-soft">
              an admin needs to import and publish this level&rsquo;s curriculum.
            </p>
          </Card>
        )}

        {/* content */}
        {data && (grammar.length > 0 || vocab.length > 0) && (
          <div className="flex flex-col gap-10">
            {grammar.length > 0 && (
              <ItemSection title="grammar" count={grammar.length} items={grammar} level={level} />
            )}
            {vocab.length > 0 && (
              <ItemSection title="vocabulary" count={vocab.length} items={vocab} level={level} />
            )}
          </div>
        )}
      </main>
    </Protected>
  );
}

function ItemSection({
  title, count, items: rows, level,
}: {
  title: string;
  count: number;
  items: LevelProgressItem[];
  level: number;
}) {
  return (
    <section aria-labelledby={`sec-${title}`}>
      <h2 id={`sec-${title}`} className="mb-3 text-xs tracking-label text-terraza-soft">
        {title.toUpperCase()} · {count}
      </h2>
      <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {rows.map((item) => (
          <li key={`${item.item_type}:${item.item_id}`}>
            <ItemCard item={item} level={level} />
          </li>
        ))}
      </ul>
    </section>
  );
}

function ItemCard({ item, level }: { item: LevelProgressItem; level: number }) {
  const article = item.article && item.article !== "none" ? item.article : null;
  const status = item.perfect
    ? "perfect"
    : item.learned
      ? item.srs_stage_name.toLowerCase()
      : "not started";

  return (
    <Link
      href={`/items/${item.item_type}/${item.item_id}`}
      aria-label={`${item.term}${item.translation ? ` — ${item.translation}` : ""}, ${status}`}
      className="flex h-full flex-col rounded-card border border-terraza-dash bg-terraza-card p-4 transition-transform duration-200 hover:-translate-y-0.5 hover:shadow-md focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-terraza-ink motion-reduce:transition-none motion-reduce:hover:translate-y-0"
    >
      <div className="flex items-start gap-2">
        <p className="mr-auto text-lg lowercase tracking-cozy text-terraza-ink">
          {article && <span className="text-terraza-soft">{article} </span>}
          {item.term}
        </p>
        {item.perfect && (
          <span aria-hidden="true" title="perfect" className="text-terraza-accent">✦</span>
        )}
      </div>

      <p className="mt-1 text-sm text-terraza-soft">
        {item.translation || <span className="italic">no translation</span>}
      </p>

      <div className="mt-3 flex items-center gap-2 text-xs">
        {item.part_of_speech && (
          <span className="rounded-full bg-terraza-pill px-2 py-0.5 tracking-cozy text-terraza-ink">
            {item.part_of_speech}
          </span>
        )}
        <span
          className={`ml-auto rounded-full border px-2 py-0.5 tracking-cozy ${
            item.learned
              ? "border-terraza-dash text-terraza-soft"
              : "border-dashed border-terraza-dash text-terraza-soft"
          }`}
        >
          {status}
        </span>
      </div>
    </Link>
  );
}
