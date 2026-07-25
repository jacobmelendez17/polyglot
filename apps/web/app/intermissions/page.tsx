"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Footer } from "@/components/footer";
import { Header } from "@/components/header";
import { IntermissionCard } from "@/components/intermission-modal";
import { Protected } from "@/components/protected";
import { Card } from "@/components/ui";
import { intermissions, type Intermission } from "@/lib/content-api";

const PAGE = 20;

export default function IntermissionsPage() {
  return (
    <Protected>
      <Header />
      <main className="mx-auto max-w-3xl px-4 py-8">
        <Archive />
      </main>
      <Footer />
    </Protected>
  );
}

function Archive() {
  const [items, setItems] = useState<Intermission[] | null>(null);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState<Intermission | null>(null);

  const load = useCallback(async (offset: number) => {
    setLoading(true);
    setError(null);
    try {
      const page = await intermissions.history(PAGE, offset);
      setTotal(page.total);
      setItems((prev) =>
        offset === 0 ? page.items : [...(prev ?? []), ...page.items],
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load your intermissions.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(0); }, [load]);

  return (
    <>
      <Link href="/dashboard"
        className="text-sm text-terraza-soft underline underline-offset-2">
        ← dashboard
      </Link>
      <h1 className="mb-1 mt-2 text-2xl lowercase tracking-cozy">intermissions</h1>
      <p className="mb-6 text-terraza-soft">
        every short reading you&apos;ve come across, kept so you can go back to one.
      </p>

      {error && <Card><p role="alert" className="text-terraza-danger">{error}</p></Card>}

      {!items && !error && (
        <p className="font-empty italic text-terraza-soft">un momento ~</p>
      )}

      {items && items.length === 0 && (
        <Card>
          <p className="text-center font-empty italic text-terraza-soft">
            nothing here yet ~
          </p>
          <p className="mt-2 text-center text-sm text-terraza-soft">
            these appear between lessons. keep going and they&apos;ll collect here.
          </p>
        </Card>
      )}

      <ul className="flex flex-col gap-3">
        {items?.map((item) => (
          <li key={item.id}>
            <button
              onClick={() => setOpen(item)}
              className="w-full rounded-card border border-terraza-dash bg-terraza-card p-5 text-left transition-transform duration-200 hover:-translate-y-0.5 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-terraza-ink motion-reduce:transition-none motion-reduce:hover:translate-y-0"
            >
              <p className="text-xs tracking-label text-terraza-soft">
                {item.kind.toUpperCase()}
              </p>
              <p className="mt-1 lowercase tracking-cozy">{item.title}</p>
              <p className="mt-1 text-sm text-terraza-soft">
                {item.body.replace(/\*\*/g, "").slice(0, 140)}…
              </p>
            </button>
          </li>
        ))}
      </ul>

      {items && items.length < total && (
        <button
          onClick={() => load(items.length)}
          disabled={loading}
          className="mt-4 rounded-full bg-terraza-pill px-5 py-2 text-sm tracking-cozy disabled:opacity-50"
        >
          {loading ? "loading…" : `show more (${total - items.length} left)`}
        </button>
      )}

      {open && <IntermissionCard intermission={open} onClose={() => setOpen(null)} />}
    </>
  );
}
