"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { Header } from "@/components/header";
import { ItemTile } from "@/components/progress-bits";
import { Protected } from "@/components/protected";
import { Card } from "@/components/ui";
import { items, type LevelProgress, type LevelProgressItem } from "@/lib/items-api";

type Filter = "all" | "not_started" | "learning" | "familiar" | "tricky" | "perfect";

const FILTERS: { id: Filter; label: string; match: (i: LevelProgressItem) => boolean }[] = [
  { id: "all", label: "everything", match: () => true },
  { id: "not_started", label: "not started", match: (i) => !i.learned },
  { id: "learning", label: "learning", match: (i) => i.learned && i.srs_stage < 5 },
  { id: "familiar", label: "familiar+", match: (i) => i.srs_stage >= 5 },
  {
    id: "tricky", label: "tricky",
    match: (i) => i.leech_state === "leech" || i.leech_state === "critical",
  },
  { id: "perfect", label: "perfect", match: (i) => i.perfect },
];

export default function LevelProgressPage() {
  return (
    <Protected>
      <Header />
      <main className="mx-auto max-w-7xl px-4 py-8">
        <ProgressView />
      </main>
    </Protected>
  );
}

function ProgressView() {
  const params = useParams();
  const level = Number(params.level);
  const [data, setData] = useState<LevelProgress | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [query, setQuery] = useState("");

  useEffect(() => {
    if (!level) return;
    let cancelled = false;
    setData(null);
    setError(null);
    items.levelProgress(level)
      .then((d) => { if (!cancelled) setData(d); })
      .catch((e) => { if (!cancelled) setError(e.message); });
    return () => { cancelled = true; };
  }, [level]);

  const visible = useMemo(() => {
    if (!data) return [];
    const rule = FILTERS.find((f) => f.id === filter) ?? FILTERS[0];
    const needle = query.trim().toLowerCase();
    return data.items.filter(
      (i) =>
        rule.match(i) &&
        (!needle ||
          i.term.toLowerCase().includes(needle) ||
          i.translation.toLowerCase().includes(needle)),
    );
  }, [data, filter, query]);

  if (error) {
    return (
      <Card>
        <p role="alert" className="text-terraza-danger">{error}</p>
        <Link href="/levels" className="mt-4 inline-block underline underline-offset-2">
          back to levels
        </Link>
      </Card>
    );
  }
  if (!data) {
    return <p className="mt-10 text-center font-empty italic text-terraza-soft">un momento ~</p>;
  }

  const { totals } = data;

  return (
    <>
      <Link href={`/levels/${level}`} className="text-sm text-terraza-soft underline underline-offset-2">
        ← level {level}
      </Link>
      <h1 className="mb-1 mt-2 text-2xl lowercase tracking-cozy">
        {data.title} · progress
      </h1>
      <p className="text-terraza-soft">
        every word and grammar point in this level, and where you stand on each.
      </p>

      {/* ---- totals ---- */}
      <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <Stat label="ITEMS" value={totals.items} />
        <Stat label="LEARNED" value={totals.learned} />
        <Stat label="FAMILIAR+" value={totals.familiar_plus} />
        <Stat label="FLUENT" value={totals.fluent} />
        <Stat label="PERFECT" value={totals.perfect} />
        <Stat label="TRICKY" value={totals.leeches} />
      </div>

      {/* ---- filters ---- */}
      <div className="mt-6 flex flex-wrap items-center gap-2">
        <div role="group" aria-label="Filter items" className="flex flex-wrap gap-2">
          {FILTERS.map((f) => {
            const count = data.items.filter(f.match).length;
            const active = filter === f.id;
            return (
              <button
                key={f.id}
                onClick={() => setFilter(f.id)}
                aria-pressed={active}
                className={`rounded-full px-4 py-1.5 text-sm tracking-cozy transition-transform duration-200 hover:-translate-y-0.5 motion-reduce:transition-none motion-reduce:hover:translate-y-0 ${
                  active
                    ? "bg-terraza-accent text-terraza-accentInk"
                    : "bg-terraza-pill text-terraza-ink"
                }`}
              >
                {f.label} ({count})
              </button>
            );
          })}
        </div>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="search this level…"
          aria-label="Search items in this level"
          className="ml-auto w-full rounded-full border border-terraza-dash bg-terraza-bg px-4 py-1.5 text-sm outline-none focus-visible:ring-2 focus-visible:ring-terraza-accent sm:w-64"
        />
      </div>

      {/* ---- grid ---- */}
      {visible.length === 0 ? (
        <Card className="mt-6">
          <p className="text-center font-empty italic text-terraza-soft">
            nothing matches that ~
          </p>
        </Card>
      ) : (
        <ul
          className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4"
          aria-label={`${visible.length} items`}
        >
          {visible.map((item) => (
            <li key={`${item.item_type}:${item.item_id}`}>
              <ItemTile item={item} />
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <Card className="text-center">
      <p className="text-2xl tracking-cozy">{value}</p>
      <p className="mt-1 text-xs tracking-label text-terraza-soft">{label}</p>
    </Card>
  );
}
