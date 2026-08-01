"use client";

// Reading library (spec §7). Published texts only. Original texts open in the
// reader; external links open out. Loading / empty / error states throughout.

import Link from "next/link";
import { useEffect, useState } from "react";
import { Header } from "@/components/header";
import { Protected } from "@/components/protected";
import { Card } from "@/components/ui";
import { reading, type TextListItem } from "@/lib/reading-api";

export default function ReadingLibraryPage() {
  const [texts, setTexts] = useState<TextListItem[] | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    reading.library().then(setTexts).catch(() => setError(true));
  }, []);

  return (
    <Protected>
      <Header />
      <main className="mx-auto max-w-3xl px-4 py-8">
        <h1 className="text-2xl lowercase tracking-cozy">reading</h1>
        <p className="mt-1 mb-6 text-terraza-soft">
          short texts to read at your own pace. tap a word for its meaning, and highlight
          anything to leave yourself a note.
        </p>

        {error ? (
          <p role="alert" className="text-terraza-danger">couldn&apos;t load the library.</p>
        ) : texts === null ? (
          <p className="font-empty italic text-terraza-soft">un momento ~</p>
        ) : texts.length === 0 ? (
          <Card><p className="font-empty italic text-terraza-soft">
            no texts published yet — check back soon.
          </p></Card>
        ) : (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {texts.map((t) => {
              const inner = (
                <Card className="h-full transition-transform hover:-translate-y-0.5">
                  <div className="flex items-baseline justify-between gap-2">
                    <p className="truncate lowercase tracking-cozy">{t.title}</p>
                    <span className="shrink-0 text-xs text-terraza-soft">level {t.level}</span>
                  </div>
                  {t.author && <p className="text-xs text-terraza-soft">{t.author}</p>}
                  <p className="mt-2 line-clamp-3 text-sm text-terraza-soft">{t.summary || "—"}</p>
                  <p className="mt-3 text-xs tracking-label text-terraza-accent">
                    {t.source_type === "external" ? "OPEN LINK ↗" : "READ →"}
                  </p>
                </Card>
              );
              return t.source_type === "external" && t.external_url ? (
                <a key={t.id} href={t.external_url} target="_blank" rel="noopener noreferrer">{inner}</a>
              ) : (
                <Link key={t.id} href={`/reading/${t.id}`}>{inner}</Link>
              );
            })}
          </div>
        )}
      </main>
    </Protected>
  );
}
