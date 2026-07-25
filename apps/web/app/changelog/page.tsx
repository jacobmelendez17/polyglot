"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Footer } from "@/components/footer";
import { renderEmphasis } from "@/components/intermission-modal";
import { Card } from "@/components/ui";
import {
  CHANGELOG_TYPE_LABEL, changelog, type ChangelogItem,
} from "@/lib/content-api";

const PAGE = 20;

const TYPE_TONE: Record<string, string> = {
  feature: "bg-terraza-accent text-terraza-accentInk",
  fix: "bg-terraza-gold",
  content: "bg-terraza-green",
  announcement: "bg-terraza-pink",
};

export default function ChangelogPage() {
  const [items, setItems] = useState<ChangelogItem[] | null>(null);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async (offset: number) => {
    setLoading(true);
    setError(null);
    try {
      const page = await changelog.list(PAGE, offset);
      setTotal(page.total);
      setItems((prev) =>
        offset === 0 ? page.items : [...(prev ?? []), ...page.items],
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load the changelog.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(0);
    // Opening the page counts as reading it. Fails quietly when signed out —
    // the changelog itself is public.
    changelog.markRead().catch(() => {});
  }, [load]);

  return (
    <div className="min-h-screen">
      <header className="mx-auto flex max-w-3xl items-center px-4 py-5">
        <Link href="/" className="mr-auto text-lg lowercase tracking-cozy">
          polyglot <span className="text-terraza-accent">✦</span>
        </Link>
        <Link href="/dashboard"
          className="text-sm text-terraza-soft underline underline-offset-2">
          dashboard
        </Link>
      </header>

      <main className="mx-auto max-w-3xl px-4 py-6">
        <h1 className="mb-1 text-2xl lowercase tracking-cozy">changelog</h1>
        <p className="mb-8 text-terraza-soft">
          what&apos;s new, what got fixed, and what&apos;s coming.
        </p>

        {error && <Card><p role="alert" className="text-terraza-danger">{error}</p></Card>}

        {!items && !error && (
          <p className="font-empty italic text-terraza-soft">un momento ~</p>
        )}

        {items && items.length === 0 && (
          <Card>
            <p className="text-center font-empty italic text-terraza-soft">
              nothing published yet ~
            </p>
          </Card>
        )}

        <ol className="flex flex-col gap-4">
          {items?.map((entry) => (
            <li key={entry.id}>
              <Card>
                <div className="flex flex-wrap items-baseline gap-3">
                  <span
                    className={`rounded-full px-3 py-1 text-xs tracking-label ${
                      TYPE_TONE[entry.type] ?? "bg-terraza-pill"
                    }`}
                  >
                    {(CHANGELOG_TYPE_LABEL[entry.type] ?? entry.type).toUpperCase()}
                  </span>
                  <h2 className="text-lg lowercase tracking-cozy">{entry.title}</h2>
                  <time
                    className="ml-auto text-xs tracking-label text-terraza-soft"
                    dateTime={entry.published_at ?? undefined}
                  >
                    {entry.published_at
                      ? new Date(entry.published_at).toLocaleDateString()
                      : ""}
                  </time>
                </div>
                {entry.body && (
                  <div className="mt-3 flex flex-col gap-2 text-terraza-soft">
                    {entry.body.split("\n\n").map((para, i) => (
                      <p key={i}>{renderEmphasis(para)}</p>
                    ))}
                  </div>
                )}
              </Card>
            </li>
          ))}
        </ol>

        {items && items.length < total && (
          <button
            onClick={() => load(items.length)}
            disabled={loading}
            className="mt-4 rounded-full bg-terraza-pill px-5 py-2 text-sm tracking-cozy disabled:opacity-50"
          >
            {loading ? "loading…" : `show more (${total - items.length} left)`}
          </button>
        )}
      </main>

      <Footer />
    </div>
  );
}
