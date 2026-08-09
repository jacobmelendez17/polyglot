"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Footer } from "@/components/footer";
import { Header } from "@/components/header";
import { IntermissionCard } from "@/components/intermission-modal";
import { Protected } from "@/components/protected";
import { SrsPill } from "@/components/progress-bits";
import { Card } from "@/components/ui";
import { decks, type DeckItem } from "@/lib/decks-api";
import { relativeTime } from "@/lib/items-api";

const PAGE = 40;

const TITLES: Record<string, string> = {
  vocabulary: "vocabulary",
  grammar: "grammar",
  intermissions: "intermissions",
};

export default function DeckPage() {
  return (
    <Protected>
      <Header />
      <main className="mx-auto max-w-5xl px-4 py-8">
        <DeckView />
      </main>
      <Footer />
    </Protected>
  );
}

function DeckView() {
  const params = useParams();
  const type = String(params.type);
  const [items, setItems] = useState<DeckItem[] | null>(null);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [reading, setReading] = useState<DeckItem | null>(null);

  const load = useCallback(async (offset: number) => {
    setLoading(true);
    setError(null);
    try {
      const page = await decks.items(type, PAGE, offset);
      setTotal(page.total);
      setItems((prev) => (offset === 0 ? page.items : [...(prev ?? []), ...page.items]));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load this deck.");
    } finally {
      setLoading(false);
    }
  }, [type]);

  useEffect(() => { setItems(null); load(0); }, [load]);

  const isIntermissions = type === "intermissions";

  return (
    <>
      <Link href="/decks" className="text-sm text-terraza-soft underline underline-offset-2">
        ← decks
      </Link>
      <h1 className="mb-1 mt-2 text-2xl lowercase tracking-cozy">
        {TITLES[type] ?? "deck"}
      </h1>
      <p className="mb-6 text-terraza-soft">{total} in this deck</p>

      {error && <Card><p role="alert" className="text-terraza-danger">{error}</p></Card>}

      {!items && !error && (
        <p className="font-empty italic text-terraza-soft">un momento ~</p>
      )}

      {items && items.length === 0 && (
        <Card>
          <p className="text-center font-empty italic text-terraza-soft">
            {isIntermissions
              ? "no readings collected yet ~"
              : "nothing unlocked yet ~"}
          </p>
        </Card>
      )}

      {items && items.length > 0 && (
        isIntermissions ? (
          <ul className="flex flex-col gap-3">
            {items.map((item) => (
              <li key={item.item_id}>
                <button
                  onClick={() => setReading(item)}
                  className="w-full rounded-card border border-terraza-dash bg-terraza-card p-5 text-left transition-transform duration-200 hover:-translate-y-0.5 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-terraza-ink motion-reduce:transition-none motion-reduce:hover:translate-y-0"
                >
                  <p className="text-xs tracking-label text-terraza-soft">
                    {(item.kind ?? "note").toUpperCase()}
                  </p>
                  <p className="mt-1 lowercase tracking-cozy">{item.term}</p>
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {items.map((item) => (
              <li key={item.item_id}>
                <Link
                  href={`/items/${item.item_type}/${item.item_id}`}
                  className="block h-full rounded-card border border-terraza-dash bg-terraza-card p-4 transition-transform duration-200 hover:-translate-y-0.5 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-terraza-ink motion-reduce:transition-none motion-reduce:hover:translate-y-0"
                >
                  <div className="flex items-start gap-2">
                    <div className="mr-auto min-w-0">
                      <p className="truncate lowercase tracking-cozy">
                        {item.article ? `${item.article} ` : ""}{item.term}
                      </p>
                      <p className="truncate text-sm text-terraza-soft">
                        {item.translation || "—"}
                      </p>
                    </div>
                    {item.level != null && (
                      <span className="text-xs text-terraza-soft">L{item.level}</span>
                    )}
                  </div>
                  <div className="mt-3 flex items-center gap-2">
                    <SrsPill
                      stage={item.srs_stage ?? 0}
                      name={item.learned ? (item.srs_stage_name ?? "") : "not started"}
                    />
                    {item.learned && item.next_review_at && (
                      <span className="ml-auto text-xs text-terraza-soft">
                        {relativeTime(item.next_review_at)}
                      </span>
                    )}
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )
      )}

      {items && items.length < total && (
        <button
          onClick={() => load(items.length)}
          disabled={loading}
          className="mt-4 rounded-full bg-terraza-pill px-5 py-2 text-sm tracking-cozy disabled:opacity-50"
        >
          {loading ? "loading…" : `show more (${total - items.length} left)`}
        </button>
      )}

      {reading && (
        <IntermissionCard
          intermission={{
            id: reading.item_id,
            title: reading.term,
            body: reading.body ?? "",
            kind: reading.kind ?? "note",
            trigger_description: "",
            viewed_at: reading.viewed_at ?? null,
          }}
          onClose={() => setReading(null)}
        />
      )}
    </>
  );
}
