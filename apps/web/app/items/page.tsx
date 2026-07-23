"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Header } from "@/components/header";
import { Protected } from "@/components/protected";
import { Card } from "@/components/ui";
import { items, type ItemSummary } from "@/lib/learn-api";

const LEECH_META: Record<string, { label: string; bg: string }> = {
  critical: { label: "critical", bg: "bg-terraza-danger text-white" },
  leech: { label: "leech", bg: "bg-terraza-pink" },
  watch: { label: "watch", bg: "bg-terraza-gold" },
};

function PracticePips({ stage }: { stage: number }) {
  return (
    <span className="inline-flex gap-[3px]" aria-label={`practice stage ${stage} of 5`}>
      {Array.from({ length: 5 }, (_, i) => (
        <span
          key={i}
          className={`h-1.5 w-1.5 rounded-full ${i < stage ? "bg-terraza-accent" : "bg-terraza-pill"}`}
        />
      ))}
    </span>
  );
}

export default function ItemsPage() {
  const [rows, setRows] = useState<ItemSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    items.list().then(setRows).catch((e) => setError(e.message));
  }, []);

  return (
    <Protected>
      <Header />
      <main className="mx-auto max-w-3xl px-4 py-8">
        <h1 className="mb-1 text-2xl lowercase tracking-cozy">your items</h1>
        <p className="mb-6 text-sm text-terraza-soft">
          every word and grammar point you&apos;ve started — tricky items float to the top.
        </p>

        {error && <Card><p className="text-terraza-danger">{error}</p></Card>}
        {!rows && !error && (
          <p className="font-empty italic text-terraza-soft">un momento ~</p>
        )}
        {rows && rows.length === 0 && (
          <Card>
            <p className="text-center font-empty italic text-terraza-soft">
              nothing started yet — finish a lesson to see it here ~
            </p>
          </Card>
        )}

        <div className="flex flex-col gap-2">
          {rows?.map((r) => {
            const leech = LEECH_META[r.leech_state];
            return (
              <Link key={`${r.item_type}:${r.item_id}`} href={`/items/${r.item_type}/${r.item_id}`}>
                <Card className="transition-transform hover:-translate-y-0.5">
                  <div className="flex items-center gap-4">
                    <div className="mr-auto">
                      <div className="flex items-center gap-2">
                        <p className="lowercase tracking-cozy">{r.term}</p>
                        {r.perfect && <span title="perfect">✦</span>}
                        {leech && (
                          <span className={`rounded-full px-2 py-0.5 text-[10px] tracking-label ${leech.bg}`}>
                            {leech.label.toUpperCase()}
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-terraza-soft">
                        {r.translation} {r.level ? `· level ${r.level}` : ""}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-xs tracking-label text-terraza-soft">{r.srs_stage_name.toUpperCase()}</p>
                      <div className="mt-1"><PracticePips stage={r.practice_stage} /></div>
                    </div>
                  </div>
                </Card>
              </Link>
            );
          })}
        </div>
      </main>
    </Protected>
  );
}
